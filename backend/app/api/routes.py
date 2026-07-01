"""
All API routes for AutoDev.
"""
import os
import shutil

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import require_api_key
from app.api.schemas import (
    AnalyzeRequest,
    AnalyzeResponse,
    DeleteResponse,
    IssueResponse,
    RefactorQueuedResponse,
    RefactorRequest,
    RefactorResponse,
    ReportResponse,
    ReportSummary,
    RepoResponse,
    StatsResponse,
    TaskStatusResponse,
)
from app.database import get_db
from app.models.analysis import AnalysisReport, CodeIssue, RefactorSuggestion, RefactorStatus
from app.models.repo import Repository, RepoStatus
from app.rate_limit import limiter
from app.services.task_service import get_task_status
from app.tasks.worker import task_full_pipeline, task_refactor_issue
import structlog

log = structlog.get_logger()

router = APIRouter(dependencies=[Depends(require_api_key)])


def _enum_str(value) -> str:
    return value.value if hasattr(value, "value") else str(value)


def _repo_response(repo: Repository) -> RepoResponse:
    return RepoResponse(
        id=repo.id,
        url=repo.url,
        owner=repo.owner,
        name=repo.name,
        status=_enum_str(repo.status),
        branch=repo.branch,
        created_at=repo.created_at,
        last_analyzed_at=repo.last_analyzed_at,
        task_id=repo.task_id,
        error_message=repo.error_message,
    )


# ── Analysis ──────────────────────────────────────────────────────────────────

@router.post("/analyze", response_model=AnalyzeResponse, tags=["Analysis"])
@limiter.limit("10/minute")
def analyze_repo(request: Request, req: AnalyzeRequest, db: Session = Depends(get_db)):
    """Queue full clone → analyze → refactor → validate → PR pipeline."""
    existing = db.query(Repository).filter(
        Repository.url == req.repo_url,
        Repository.status.in_([RepoStatus.CLONING, RepoStatus.ANALYZING]),
    ).first()
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"Repo already being processed: {existing.id}",
        )

    parts = req.repo_url.rstrip("/").split("/")
    owner = parts[-2] if len(parts) >= 2 else "unknown"
    name = parts[-1].replace(".git", "") if parts else "unknown"

    repo = Repository(
        url=req.repo_url,
        owner=owner,
        name=name,
        branch=req.branch,
        status=RepoStatus.PENDING,
    )
    db.add(repo)
    db.commit()
    db.refresh(repo)

    task = task_full_pipeline.delay(repo.id)
    repo.task_id = task.id
    db.commit()

    log.info("analyze.queued", repo_id=repo.id, url=req.repo_url, task_id=task.id)
    return AnalyzeResponse(
        repo_id=repo.id,
        task_id=task.id,
        status="queued",
        message="Repository queued for analysis.",
    )


@router.get("/tasks/{task_id}", response_model=TaskStatusResponse, tags=["Tasks"])
def task_status(task_id: str, db: Session = Depends(get_db)):
    """Poll Celery task state by ID (links repo_id when available)."""
    return get_task_status(task_id, db)


# ── Repositories ────────────────────────────────────────────────────────────────

@router.get("/repos", response_model=list[RepoResponse], tags=["Repos"])
def list_repos(skip: int = 0, limit: int = 20, db: Session = Depends(get_db)):
    repos = (
        db.query(Repository)
        .order_by(Repository.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return [_repo_response(r) for r in repos]


@router.get("/repos/{repo_id}", response_model=RepoResponse, tags=["Repos"])
def get_repo(repo_id: str, db: Session = Depends(get_db)):
    repo = db.query(Repository).filter(Repository.id == repo_id).first()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    return _repo_response(repo)


@router.delete("/repos/{repo_id}", response_model=DeleteResponse, tags=["Repos"])
def delete_repo(repo_id: str, db: Session = Depends(get_db)):
    repo = db.query(Repository).filter(Repository.id == repo_id).first()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")

    db.query(RefactorSuggestion).filter(RefactorSuggestion.repo_id == repo_id).delete()
    db.query(CodeIssue).filter(CodeIssue.repo_id == repo_id).delete()
    db.query(AnalysisReport).filter(AnalysisReport.repo_id == repo_id).delete()
    db.delete(repo)
    db.commit()

    if repo.local_path and os.path.exists(repo.local_path):
        try:
            shutil.rmtree(repo.local_path)
        except OSError:
            pass

    return DeleteResponse(deleted=repo_id)


# ── Reports & refactors ───────────────────────────────────────────────────────

@router.get("/repos/{repo_id}/report", response_model=ReportResponse, tags=["Analysis"])
def get_report(repo_id: str, db: Session = Depends(get_db)):
    report = (
        db.query(AnalysisReport)
        .filter(AnalysisReport.repo_id == repo_id)
        .order_by(AnalysisReport.created_at.desc())
        .first()
    )
    if not report:
        raise HTTPException(status_code=404, detail="No analysis report found for this repo")

    issues = db.query(CodeIssue).filter(CodeIssue.report_id == report.id).all()
    return ReportResponse(
        report=ReportSummary(
            id=report.id,
            created_at=report.created_at,
            total_files=report.total_files,
            total_issues=report.total_issues,
            avg_complexity=report.avg_complexity,
            max_complexity=report.max_complexity,
            security_issues=report.security_issues,
            lint_errors=report.lint_errors,
        ),
        issues=[
            IssueResponse(
                id=i.id,
                file_path=i.file_path,
                function_name=i.function_name,
                issue_type=_enum_str(i.issue_type),
                severity=_enum_str(i.severity),
                description=i.description,
                metric_value=i.metric_value,
                line_start=i.line_start,
                line_end=i.line_end,
                original_code=i.original_code,
            )
            for i in issues
        ],
    )


@router.get("/repos/{repo_id}/refactors", response_model=list[RefactorResponse], tags=["Refactors"])
def list_refactors(repo_id: str, db: Session = Depends(get_db)):
    suggestions = db.query(RefactorSuggestion).filter(
        RefactorSuggestion.repo_id == repo_id
    ).all()
    result = []
    for s in suggestions:
        issue = db.query(CodeIssue).filter(CodeIssue.id == s.issue_id).first()
        result.append(
            RefactorResponse(
                id=s.id,
                issue_id=s.issue_id,
                status=_enum_str(s.status),
                complexity_before=s.complexity_before,
                complexity_after=s.complexity_after,
                lines_before=s.lines_before,
                lines_after=s.lines_after,
                validation_passed=s.validation_passed,
                validation_notes=s.validation_notes,
                pr_url=s.pr_url,
                pr_number=s.pr_number,
                tokens_used=s.tokens_used or 0,
                branch_name=s.branch_name,
                explanation=s.explanation,
                refactored_code=s.refactored_code,
                original_code=issue.original_code if issue else None,
                function_name=issue.function_name if issue else None,
                file_path=issue.file_path if issue else None,
                created_at=s.created_at,
            )
        )
    return result


@router.post("/refactor", response_model=RefactorQueuedResponse, tags=["Refactors"])
def trigger_refactor(req: RefactorRequest, db: Session = Depends(get_db)):
    issue = db.query(CodeIssue).filter(CodeIssue.id == req.issue_id).first()
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")
    task = task_refactor_issue.delay(req.issue_id)
    return RefactorQueuedResponse(task_id=task.id, message="Refactor queued")


# ── Dashboard ─────────────────────────────────────────────────────────────────

@router.get("/stats", response_model=StatsResponse, tags=["Dashboard"])
def global_stats(db: Session = Depends(get_db)):
    try:
        total_repos = db.query(func.count(Repository.id)).scalar() or 0
        total_issues = db.query(func.count(CodeIssue.id)).scalar() or 0
        prs_opened = (
            db.query(func.count(RefactorSuggestion.id))
            .filter(RefactorSuggestion.status == RefactorStatus.PR_OPENED.value)
            .scalar()
            or 0
        )
        validated = (
            db.query(func.count(RefactorSuggestion.id))
            .filter(RefactorSuggestion.validation_passed.is_(True))
            .scalar()
            or 0
        )

        avg_before = float(db.query(func.avg(RefactorSuggestion.complexity_before)).scalar() or 0)
        avg_after = float(db.query(func.avg(RefactorSuggestion.complexity_after)).scalar() or 0)

        return StatsResponse(
            total_repos=total_repos,
            total_issues=total_issues,
            prs_opened=prs_opened,
            validated_refactors=validated,
            avg_complexity_before=round(avg_before, 2),
            avg_complexity_after=round(avg_after, 2),
            complexity_reduction_pct=round((1 - avg_after / avg_before) * 100 if avg_before else 0, 1),
        )
    except Exception as exc:
        log.exception("stats.failed", error=str(exc))
        raise HTTPException(status_code=500, detail="Failed to load dashboard stats") from exc
