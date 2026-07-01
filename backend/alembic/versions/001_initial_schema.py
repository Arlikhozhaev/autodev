"""Initial AutoDev schema — repositories, analysis reports, issues, refactors."""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

repo_status = postgresql.ENUM(
    "pending", "cloning", "analyzing", "refactoring", "validating", "done", "failed",
    name="repostatus",
    create_type=False,
)
issue_type = postgresql.ENUM(
    "complexity", "long_function", "deep_nesting", "duplicate_code",
    "unused_import", "long_params", "security", "lint",
    name="issuetype",
    create_type=False,
)
issue_severity = postgresql.ENUM(
    "low", "medium", "high", "critical",
    name="issueseverity",
    create_type=False,
)
refactor_status = postgresql.ENUM(
    "pending", "generated", "validated", "failed", "pr_opened", "rejected",
    name="refactorstatus",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    repo_status.create(bind, checkfirst=True)
    issue_type.create(bind, checkfirst=True)
    issue_severity.create(bind, checkfirst=True)
    refactor_status.create(bind, checkfirst=True)

    op.create_table(
        "repositories",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("url", sa.String(length=512), nullable=False),
        sa.Column("owner", sa.String(length=255), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column("branch", sa.String(length=255), nullable=True),
        sa.Column("local_path", sa.String(length=1024), nullable=True),
        sa.Column("status", repo_status, nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("last_analyzed_at", sa.DateTime(), nullable=True),
        sa.Column("task_id", sa.String(length=255), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_repositories_url"), "repositories", ["url"], unique=False)

    op.create_table(
        "analysis_reports",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("repo_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("total_files", sa.Integer(), nullable=False),
        sa.Column("total_issues", sa.Integer(), nullable=False),
        sa.Column("avg_complexity", sa.Float(), nullable=False),
        sa.Column("max_complexity", sa.Integer(), nullable=False),
        sa.Column("total_lines", sa.Integer(), nullable=False),
        sa.Column("security_issues", sa.Integer(), nullable=False),
        sa.Column("lint_errors", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["repo_id"], ["repositories.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "code_issues",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("report_id", sa.String(length=36), nullable=False),
        sa.Column("repo_id", sa.String(length=36), nullable=False),
        sa.Column("file_path", sa.String(length=1024), nullable=False),
        sa.Column("function_name", sa.String(length=512), nullable=True),
        sa.Column("line_start", sa.Integer(), nullable=True),
        sa.Column("line_end", sa.Integer(), nullable=True),
        sa.Column("issue_type", issue_type, nullable=False),
        sa.Column("severity", issue_severity, nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("metric_value", sa.Float(), nullable=True),
        sa.Column("original_code", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["report_id"], ["analysis_reports.id"]),
        sa.ForeignKeyConstraint(["repo_id"], ["repositories.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "refactor_suggestions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("issue_id", sa.String(length=36), nullable=False),
        sa.Column("repo_id", sa.String(length=36), nullable=False),
        sa.Column("refactored_code", sa.Text(), nullable=True),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("complexity_before", sa.Integer(), nullable=True),
        sa.Column("complexity_after", sa.Integer(), nullable=True),
        sa.Column("lines_before", sa.Integer(), nullable=True),
        sa.Column("lines_after", sa.Integer(), nullable=True),
        sa.Column("status", refactor_status, nullable=False),
        sa.Column("validation_passed", sa.Boolean(), nullable=True),
        sa.Column("validation_notes", sa.Text(), nullable=True),
        sa.Column("pr_url", sa.String(length=512), nullable=True),
        sa.Column("pr_number", sa.Integer(), nullable=True),
        sa.Column("branch_name", sa.String(length=255), nullable=True),
        sa.Column("tokens_used", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("applied_commit_sha", sa.String(length=40), nullable=True),
        sa.Column("source_file_hash", sa.String(length=64), nullable=True),
        sa.ForeignKeyConstraint(["issue_id"], ["code_issues.id"]),
        sa.ForeignKeyConstraint(["repo_id"], ["repositories.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("issue_id"),
    )


def downgrade() -> None:
    op.drop_table("refactor_suggestions")
    op.drop_table("code_issues")
    op.drop_table("analysis_reports")
    op.drop_index(op.f("ix_repositories_url"), table_name="repositories")
    op.drop_table("repositories")

    bind = op.get_bind()
    refactor_status.drop(bind, checkfirst=True)
    issue_severity.drop(bind, checkfirst=True)
    issue_type.drop(bind, checkfirst=True)
    repo_status.drop(bind, checkfirst=True)
