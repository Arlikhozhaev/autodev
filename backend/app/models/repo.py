"""
Repository ORM model.
"""
import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base
from app.models.enums import pg_enum
import enum


class RepoStatus(str, enum.Enum):
    PENDING    = "pending"
    CLONING    = "cloning"
    ANALYZING  = "analyzing"
    REFACTORING = "refactoring"
    VALIDATING = "validating"
    DONE       = "done"
    FAILED     = "failed"


class Repository(Base):
    __tablename__ = "repositories"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    url: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    owner: Mapped[str] = mapped_column(String(255), nullable=True)
    name: Mapped[str]  = mapped_column(String(255), nullable=True)
    branch: Mapped[str] = mapped_column(String(255), default="main")
    local_path: Mapped[str] = mapped_column(String(1024), nullable=True)
    status: Mapped[RepoStatus] = mapped_column(
        pg_enum(RepoStatus, "repostatus"), default=RepoStatus.PENDING
    )
    error_message: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_analyzed_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    task_id: Mapped[str] = mapped_column(String(255), nullable=True)

    def __repr__(self) -> str:
        return f"<Repository {self.owner}/{self.name} [{self.status}]>"
