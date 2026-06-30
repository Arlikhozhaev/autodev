"""
All API routes for AutoDev.
"""
import os
import shutil

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.repo import Repository, RepoStatus
from app.models.analysis import AnalysisReport, CodeIssue, RefactorSuggestion, RefactorStatus
from app.tasks.worker import task_full_pipeline, task_refactor_issue
import structlog

log = structlog.get_logger()
router = APIRouter()


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class AnalyzeRequest(BaseModel):
    repo_url: str
    branch: str = "main"


class AnalyzeResponse(BaseModel):
    repo_id: str
    task_id: str
    status: str
    message: str


class RefactorRequest(BaseModel):
    issue_id: str


# ── Repo endpoints ────────────────────────────────────────────────────────────

@router.post("/analyze", response_model=AnalyzeResponse, tags=["Analysis"])
def analyze_repo(req: AnalyzeRequest, db: Session = Depends(get_db)):
    """
    Clone repository and kick off full analysis + refactor pipeline.
    Returns immediately; processing is async via Celery.
    """
    # Check if already being processed
    existing = db.query(Repository).filter(
        Repository.url == req.repo_url,
        Repository.status.in_([RepoStatus.CLONING, RepoStatus.ANALYZING])
    ).first()
    if existing:
        raise HTTPException(409, detail=f"Repo already being processed: {existing.id}")

    # Parse owner/name from URL
    parts = req.repo_url.rstrip("/").split("/")
    owner = parts[-2] if len(parts) >= 2 else "unknown"
    name  = parts[-1].replace(".git", "") if parts else "unknown"

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

    log.info("analyze.queued", repo_id=repo.id, url=req.repo_url)
    return AnalyzeResponse(
        repo_id=repo.id,
        task_id=task.id,
        status="queued",
        message="Repository queued for analysis.",
    )


@router.get("/repos", tags=["Repos"])
def list_repos(skip: int = 0, limit: int = 20, db: Session = Depends(get_db)):
    repos = db.query(Repository).order_by(Repository.created_at.desc()).offset(skip).limit(limit).all()
    return [
        {
            "id": r.id, "url": r.url, "owner": r.owner, "name": r.name,
            "status": r.status, "branch": r.branch,
            "created_at": r.created_at, "last_analyzed_at": r.last_analyzed_at,
        }
        for r in repos
    ]


@router.get("/repos/{repo_id}", tags=["Repos"])
def get_repo(repo_id: str, db: Session = Depends(get_db)):
    repo = db.query(Repository).filter(Repository.id == repo_id).first()
    if not repo:
        raise HTTPException(404, "Repository not found")
    return repo


@router.get("/repos/{repo_id}/report", tags=["Analysis"])
def get_report(repo_id: str, db: Session = Depends(get_db)):
    report = db.query(AnalysisReport).filter(
        AnalysisReport.repo_id == repo_id
    ).order_by(AnalysisReport.created_at.desc()).first()
    if not report:
        raise HTTPException(404, "No analysis report found for this repo")

    issues = db.query(CodeIssue).filter(CodeIssue.report_id == report.id).all()
    return {
        "report": {
            "id": report.id,
            "created_at": report.created_at,
            "total_files": report.total_files,
            "total_issues": report.total_issues,
            "avg_complexity": report.avg_complexity,
            "max_complexity": report.max_complexity,
            "security_issues": report.security_issues,
            "lint_errors": report.lint_errors,
        },
        "issues": [
            {
                "id": i.id,
                "file_path": i.file_path,
                "function_name": i.function_name,
                "issue_type": i.issue_type,
                "severity": i.severity,
                "description": i.description,
                "metric_value": i.metric_value,
                "line_start": i.line_start,
                "line_end": i.line_end,
                "original_code": i.original_code,
            }
            for i in issues
        ],
    }


@router.get("/repos/{repo_id}/refactors", tags=["Refactors"])
def list_refactors(repo_id: str, db: Session = Depends(get_db)):
    suggestions = db.query(RefactorSuggestion).filter(
        RefactorSuggestion.repo_id == repo_id
    ).all()
    result = []
    for s in suggestions:
        issue = db.query(CodeIssue).filter(CodeIssue.id == s.issue_id).first()
        result.append({
            "id": s.id,
            "issue_id": s.issue_id,
            "status": s.status,
            "complexity_before": s.complexity_before,
            "complexity_after": s.complexity_after,
            "lines_before": s.lines_before,
            "lines_after": s.lines_after,
            "validation_passed": s.validation_passed,
            "validation_notes": s.validation_notes,
            "pr_url": s.pr_url,
            "pr_number": s.pr_number,
            "tokens_used": s.tokens_used,
            "branch_name": s.branch_name,
            "explanation": s.explanation,
            "refactored_code": s.refactored_code,
            "original_code": issue.original_code if issue else None,
            "function_name": issue.function_name if issue else None,
            "file_path": issue.file_path if issue else None,
            "created_at": s.created_at,
        })
    return result


@router.post("/refactor", tags=["Refactors"])
def trigger_refactor(req: RefactorRequest, db: Session = Depends(get_db)):
    """Manually trigger refactor for a specific issue."""
    issue = db.query(CodeIssue).filter(CodeIssue.id == req.issue_id).first()
    if not issue:
        raise HTTPException(404, "Issue not found")
    task = task_refactor_issue.delay(req.issue_id)
    return {"task_id": task.id, "message": "Refactor queued"}


@router.delete("/repos/{repo_id}", tags=["Repos"])
def delete_repo(repo_id: str, db: Session = Depends(get_db)):
    """Delete a repository and all its associated data."""
    repo = db.query(Repository).filter(Repository.id == repo_id).first()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")

    # Delete in strict dependency order (child before parent)
    # 1. RefactorSuggestions reference CodeIssues — must go first
    db.query(RefactorSuggestion).filter(RefactorSuggestion.repo_id == repo_id).delete()
    # 2. CodeIssues reference AnalysisReports
    db.query(CodeIssue).filter(CodeIssue.repo_id == repo_id).delete()
    # 3. AnalysisReports reference Repository
    db.query(AnalysisReport).filter(AnalysisReport.repo_id == repo_id).delete()
    # 4. Finally the repo itself
    db.delete(repo)
    db.commit()

    # Clean up local clone if it exists
    if repo.local_path and os.path.exists(repo.local_path):
        try:
            shutil.rmtree(repo.local_path)
        except Exception:
            pass

    return {"deleted": repo_id}


@router.get("/stats", tags=["Dashboard"])
def global_stats(db: Session = Depends(get_db)):
    """Dashboard-level aggregate stats."""
    from sqlalchemy import func
    total_repos = db.query(func.count(Repository.id)).scalar()
    total_issues = db.query(func.count(CodeIssue.id)).scalar()
    prs_opened = db.query(func.count(RefactorSuggestion.id)).filter(
        RefactorSuggestion.status == RefactorStatus.PR_OPENED
    ).scalar()
    validated = db.query(func.count(RefactorSuggestion.id)).filter(
        RefactorSuggestion.validation_passed.is_(True)
    ).scalar()

    avg_before = db.query(func.avg(RefactorSuggestion.complexity_before)).scalar() or 0
    avg_after  = db.query(func.avg(RefactorSuggestion.complexity_after)).scalar() or 0

    return {
        "total_repos": total_repos,
        "total_issues": total_issues,
        "prs_opened": prs_opened,
        "validated_refactors": validated,
        "avg_complexity_before": round(float(avg_before), 2),
        "avg_complexity_after": round(float(avg_after), 2),
        "complexity_reduction_pct": round(
            (1 - avg_after / avg_before) * 100 if avg_before else 0, 1
        ),
    }
