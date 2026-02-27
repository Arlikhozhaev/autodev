"""
Analysis & Refactor ORM models.
"""
import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, Text, Integer, Float, Boolean, ForeignKey, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base
import enum


class IssueSeverity(str, enum.Enum):
    LOW      = "low"
    MEDIUM   = "medium"
    HIGH     = "high"
    CRITICAL = "critical"


class IssueType(str, enum.Enum):
    COMPLEXITY      = "complexity"
    LONG_FUNCTION   = "long_function"
    DEEP_NESTING    = "deep_nesting"
    DUPLICATE_CODE  = "duplicate_code"
    UNUSED_IMPORT   = "unused_import"
    LONG_PARAMS     = "long_params"
    SECURITY        = "security"
    LINT            = "lint"


class RefactorStatus(str, enum.Enum):
    PENDING    = "pending"
    GENERATED  = "generated"
    VALIDATED  = "validated"
    FAILED     = "failed"
    PR_OPENED  = "pr_opened"
    REJECTED   = "rejected"


class AnalysisReport(Base):
    __tablename__ = "analysis_reports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    repo_id: Mapped[str] = mapped_column(String(36), ForeignKey("repositories.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    total_files: Mapped[int] = mapped_column(Integer, default=0)
    total_issues: Mapped[int] = mapped_column(Integer, default=0)
    avg_complexity: Mapped[float] = mapped_column(Float, default=0.0)
    max_complexity: Mapped[int] = mapped_column(Integer, default=0)
    total_lines: Mapped[int] = mapped_column(Integer, default=0)
    security_issues: Mapped[int] = mapped_column(Integer, default=0)
    lint_errors: Mapped[int] = mapped_column(Integer, default=0)

    issues: Mapped[list["CodeIssue"]] = relationship("CodeIssue", back_populates="report", cascade="all, delete-orphan")


class CodeIssue(Base):
    __tablename__ = "code_issues"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    report_id: Mapped[str] = mapped_column(String(36), ForeignKey("analysis_reports.id"), nullable=False)
    repo_id: Mapped[str] = mapped_column(String(36), ForeignKey("repositories.id"), nullable=False)

    file_path: Mapped[str] = mapped_column(String(1024))
    function_name: Mapped[str] = mapped_column(String(512), nullable=True)
    line_start: Mapped[int] = mapped_column(Integer, nullable=True)
    line_end: Mapped[int] = mapped_column(Integer, nullable=True)
    issue_type: Mapped[IssueType] = mapped_column(SAEnum(IssueType))
    severity: Mapped[IssueSeverity] = mapped_column(SAEnum(IssueSeverity), default=IssueSeverity.MEDIUM)
    description: Mapped[str] = mapped_column(Text)
    metric_value: Mapped[float] = mapped_column(Float, nullable=True)   # e.g. complexity = 18
    original_code: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    report: Mapped["AnalysisReport"] = relationship("AnalysisReport", back_populates="issues")
    refactor: Mapped["RefactorSuggestion"] = relationship("RefactorSuggestion", back_populates="issue", uselist=False)


class RefactorSuggestion(Base):
    __tablename__ = "refactor_suggestions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    issue_id: Mapped[str] = mapped_column(String(36), ForeignKey("code_issues.id"), nullable=False, unique=True)
    repo_id: Mapped[str] = mapped_column(String(36), ForeignKey("repositories.id"), nullable=False)

    refactored_code: Mapped[str] = mapped_column(Text, nullable=True)
    explanation: Mapped[str] = mapped_column(Text, nullable=True)
    complexity_before: Mapped[int] = mapped_column(Integer, nullable=True)
    complexity_after: Mapped[int] = mapped_column(Integer, nullable=True)
    lines_before: Mapped[int] = mapped_column(Integer, nullable=True)
    lines_after: Mapped[int] = mapped_column(Integer, nullable=True)
    status: Mapped[RefactorStatus] = mapped_column(SAEnum(RefactorStatus), default=RefactorStatus.PENDING)
    validation_passed: Mapped[bool] = mapped_column(Boolean, nullable=True)
    validation_notes: Mapped[str] = mapped_column(Text, nullable=True)
    pr_url: Mapped[str] = mapped_column(String(512), nullable=True)
    pr_number: Mapped[int] = mapped_column(Integer, nullable=True)
    branch_name: Mapped[str] = mapped_column(String(255), nullable=True)
    tokens_used: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    issue: Mapped["CodeIssue"] = relationship("CodeIssue", back_populates="refactor")
