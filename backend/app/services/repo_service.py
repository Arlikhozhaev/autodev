"""
Repository Service
Handles cloning, updating, and managing local repo copies.
"""
import os
import shutil
from pathlib import Path
from datetime import datetime

import structlog
from git import Repo, GitCommandError
from sqlalchemy.orm import Session

from app.config import settings
from app.models.repo import Repository, RepoStatus

log = structlog.get_logger()


class RepoService:
    def __init__(self, db: Session):
        self.db = db
        self.base_path = Path(settings.REPOS_BASE_PATH)
        self.base_path.mkdir(parents=True, exist_ok=True)

    def get_local_path(self, repo: Repository) -> Path:
        return self.base_path / repo.id

    def clone(self, repo: Repository) -> Path:
        """Clone the remote repository to local disk. Idempotent."""
        local_path = self.get_local_path(repo)

        self._update_status(repo, RepoStatus.CLONING)

        if local_path.exists():
            log.info("repo.already_cloned", repo_id=repo.id, path=str(local_path))
            try:
                git_repo = Repo(str(local_path))
                git_repo.remotes.origin.pull()
                log.info("repo.pulled", repo_id=repo.id)
            except Exception as e:
                log.warning("repo.pull_failed", repo_id=repo.id, error=str(e))
                shutil.rmtree(str(local_path), ignore_errors=True)
                self._clone_fresh(repo, local_path)
        else:
            self._clone_fresh(repo, local_path)

        repo.local_path = str(local_path)
        self.db.commit()
        return local_path

    def _clone_fresh(self, repo: Repository, local_path: Path):
        log.info("repo.cloning", url=repo.url, path=str(local_path))
        try:
            clone_url = self._inject_token(repo.url)
            Repo.clone_from(
                clone_url,
                str(local_path),
                branch=repo.branch,
                depth=1,   # shallow clone — faster
            )
            log.info("repo.cloned", repo_id=repo.id)
        except GitCommandError as e:
            self._update_status(repo, RepoStatus.FAILED, str(e))
            raise

    def _inject_token(self, url: str) -> str:
        """Inject GitHub token into HTTPS URL for authenticated clone."""
        token = settings.GITHUB_TOKEN
        if not token:
            return url
        if url.startswith("https://"):
            return url.replace("https://", f"https://{token}@")
        return url

    def cleanup(self, repo: Repository):
        """Remove local clone (e.g. after PR is merged)."""
        local_path = self.get_local_path(repo)
        if local_path.exists():
            shutil.rmtree(str(local_path))
            log.info("repo.cleaned", repo_id=repo.id)

    def _update_status(self, repo: Repository, status: RepoStatus, error: str = None):
        repo.status = status
        if error:
            repo.error_message = error
        self.db.commit()
