"""
Celery task status lookups.
"""
from typing import Optional

from celery.result import AsyncResult
from sqlalchemy.orm import Session

from app.api.schemas import TaskStatusResponse
from app.models.repo import Repository
from app.tasks.worker import celery_app


def get_task_status(task_id: str, db: Optional[Session] = None) -> TaskStatusResponse:
    async_result = AsyncResult(task_id, app=celery_app)
    ready = async_result.ready()
    successful: Optional[bool] = None
    result = None
    error: Optional[str] = None

    if ready:
        successful = async_result.successful()
        if successful:
            result = async_result.result
        else:
            error = str(async_result.result) if async_result.result else "Task failed"

    repo_id: Optional[str] = None
    if db is not None:
        repo = db.query(Repository).filter(Repository.task_id == task_id).first()
        if repo:
            repo_id = repo.id

    return TaskStatusResponse(
        task_id=task_id,
        status=async_result.status,
        ready=ready,
        successful=successful,
        result=result,
        error=error,
        repo_id=repo_id,
    )
