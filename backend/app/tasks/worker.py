"""
Celery Worker — Async task definitions.
Each task handles one step of the pipeline. 
The full pipeline task orchestrates all steps end-to-end.
"""
from celery import Celery
from celery.utils.log import get_task_logger

from app.config import settings
from app.database import SessionLocal
from app.models.repo import Repository, RepoStatus
from app.models.analysis import CodeIssue, RefactorSuggestion, IssueType

import structlog
log = structlog.get_logger()

celery_app = Celery(
    "autodev",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,   # one task at a time per worker
    task_time_limit=600,            # 10 min hard limit
    task_soft_time_limit=540,
)

# Issue types we auto-refactor (skip lint/security for safety)
REFACTORABLE_TYPES = {
    IssueType.COMPLEXITY,
    IssueType.LONG_FUNCTION,
    IssueType.DEEP_NESTING,
    IssueType.LONG_PARAMS,
}


@celery_app.task(bind=True, max_retries=2, name="tasks.full_pipeline")
def task_full_pipeline(self, repo_id: str):
    """
    End-to-end pipeline:
      clone → analyze → refactor → validate → PR
    """
    db = SessionLocal()
    try:
        repo = db.query(Repository).filter(Repository.id == repo_id).first()
        if not repo:
            log.error("pipeline.repo_not_found", repo_id=repo_id)
            return

        # Phase 1: Clone
        from app.services.repo_service import RepoService
        repo_svc = RepoService(db)
        repo_svc.clone(repo)
        log.info("pipeline.cloned", repo_id=repo_id)

        # Phase 2: Analyze
        from app.services.analysis_service import AnalysisService
        analysis_svc = AnalysisService(db)
        report = analysis_svc.analyze(repo)
        log.info("pipeline.analyzed", repo_id=repo_id, issues=report.total_issues)

        # Phase 3 + 4 + 5: Refactor → Validate → PR
        # Only process high-value, refactorable issues (cap at 10 per run)
        issues = (
            db.query(CodeIssue)
            .filter(
                CodeIssue.report_id == report.id,
                CodeIssue.issue_type.in_(list(REFACTORABLE_TYPES)),
            )
            .order_by(CodeIssue.metric_value.desc())   # worst issues first
            .limit(10)
            .all()
        )

        log.info("pipeline.refactoring", repo_id=repo_id, count=len(issues))

        from app.services.refactor_service import RefactorService
        from app.services.validation_service import ValidationService
        from app.services.git_service import GitService

        refactor_svc   = RefactorService(db)
        validation_svc = ValidationService(db)
        git_svc        = GitService(db)

        for issue in issues:
            try:
                # Refactor
                suggestion = refactor_svc.refactor_issue(issue)
                if not suggestion or not suggestion.refactored_code:
                    continue

                # Validate
                valid = validation_svc.validate(suggestion, issue, repo.local_path)
                if not valid:
                    log.info("pipeline.validation_failed", issue_id=issue.id)
                    continue

                # PR
                git_svc.create_pr(repo, suggestion, issue)

            except Exception as e:
                log.error("pipeline.issue_failed", issue_id=issue.id, error=str(e))
                continue

        log.info("pipeline.complete", repo_id=repo_id)

    except Exception as e:
        log.error("pipeline.failed", repo_id=repo_id, error=str(e))
        repo = db.query(Repository).filter(Repository.id == repo_id).first()
        if repo:
            repo.status = RepoStatus.FAILED
            repo.error_message = str(e)
            db.commit()
        raise self.retry(exc=e, countdown=30)
    finally:
        db.close()


@celery_app.task(bind=True, max_retries=1, name="tasks.analyze_repo")
def task_analyze_repo(self, repo_id: str):
    """Standalone analysis task (no refactor)."""
    db = SessionLocal()
    try:
        repo = db.query(Repository).filter(Repository.id == repo_id).first()
        if not repo:
            return
        from app.services.repo_service import RepoService
        from app.services.analysis_service import AnalysisService
        RepoService(db).clone(repo)
        AnalysisService(db).analyze(repo)
    finally:
        db.close()


@celery_app.task(bind=True, max_retries=1, name="tasks.refactor_issue")
def task_refactor_issue(self, issue_id: str):
    """Manually triggered single-issue refactor + validate + PR."""
    db = SessionLocal()
    try:
        issue = db.query(CodeIssue).filter(CodeIssue.id == issue_id).first()
        if not issue:
            return
        repo = db.query(Repository).filter(Repository.id == issue.repo_id).first()
        if not repo:
            return

        from app.services.refactor_service import RefactorService
        from app.services.validation_service import ValidationService
        from app.services.git_service import GitService

        suggestion = RefactorService(db).refactor_issue(issue)
        if not suggestion or not suggestion.refactored_code:
            return

        valid = ValidationService(db).validate(suggestion, issue, repo.local_path)
        if valid:
            GitService(db).create_pr(repo, suggestion, issue)
    except Exception as e:
        log.error("task.refactor_issue.failed", issue_id=issue_id, error=str(e))
        raise
    finally:
        db.close()
