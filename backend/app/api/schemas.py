"""
Pydantic request/response schemas for the AutoDev API.
"""
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


# ── Requests ──────────────────────────────────────────────────────────────────

class AnalyzeRequest(BaseModel):
    repo_url: str
    branch: str = "main"


class RefactorRequest(BaseModel):
    issue_id: str


# ── Responses ─────────────────────────────────────────────────────────────────

class AnalyzeResponse(BaseModel):
    repo_id: str
    task_id: str
    status: str
    message: str


class RefactorQueuedResponse(BaseModel):
    task_id: str
    message: str


class DeleteResponse(BaseModel):
    deleted: str


class RepoResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    url: str
    owner: Optional[str] = None
    name: Optional[str] = None
    status: str
    branch: str
    created_at: datetime
    last_analyzed_at: Optional[datetime] = None
    task_id: Optional[str] = None
    error_message: Optional[str] = None


class ReportSummary(BaseModel):
    id: str
    created_at: datetime
    total_files: int
    total_issues: int
    avg_complexity: float
    max_complexity: int
    security_issues: int
    lint_errors: int


class IssueResponse(BaseModel):
    id: str
    file_path: str
    function_name: Optional[str] = None
    issue_type: str
    severity: str
    description: str
    metric_value: Optional[float] = None
    line_start: Optional[int] = None
    line_end: Optional[int] = None
    original_code: Optional[str] = None


class ReportResponse(BaseModel):
    report: ReportSummary
    issues: list[IssueResponse]


class RefactorResponse(BaseModel):
    id: str
    issue_id: str
    status: str
    complexity_before: Optional[int] = None
    complexity_after: Optional[int] = None
    lines_before: Optional[int] = None
    lines_after: Optional[int] = None
    validation_passed: Optional[bool] = None
    validation_notes: Optional[str] = None
    pr_url: Optional[str] = None
    pr_number: Optional[int] = None
    tokens_used: int = 0
    branch_name: Optional[str] = None
    explanation: Optional[str] = None
    refactored_code: Optional[str] = None
    original_code: Optional[str] = None
    function_name: Optional[str] = None
    file_path: Optional[str] = None
    created_at: datetime


class StatsResponse(BaseModel):
    total_repos: int
    total_issues: int
    prs_opened: int
    validated_refactors: int
    avg_complexity_before: float
    avg_complexity_after: float
    complexity_reduction_pct: float


class TaskStatusResponse(BaseModel):
    task_id: str
    status: str = Field(description="Celery state: PENDING, STARTED, SUCCESS, FAILURE, RETRY, REVOKED")
    ready: bool
    successful: Optional[bool] = None
    result: Optional[Any] = None
    error: Optional[str] = None
    repo_id: Optional[str] = Field(None, description="Linked repository when task is a pipeline job")


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorDetail
