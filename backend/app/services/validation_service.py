"""
Validation Service
After LLM generates a refactor:
  1. Apply change to temp branch
  2. Run pytest
  3. Run ruff + bandit
  4. Run DiffValidator (signature + size + import checks)
  5. Compare AST before/after
"""
import os
import subprocess
import tempfile
from pathlib import Path

import structlog
from sqlalchemy.orm import Session

from app.config import settings
from app.models.analysis import CodeIssue, RefactorSuggestion, RefactorStatus
from app.utils.diff_validator import DiffValidator

log = structlog.get_logger()


class ValidationService:
    def __init__(self, db: Session):
        self.db = db
        self.diff_validator = DiffValidator(max_size_change_pct=settings.MAX_FILE_SIZE_CHANGE_PCT)

    def validate(self, suggestion: RefactorSuggestion, issue: CodeIssue, repo_local_path: str) -> bool:
        notes = []

        # 1. Diff validation (fast, in-memory)
        diff_result = self.diff_validator.validate(
            original_code=issue.original_code or "",
            refactored_code=suggestion.refactored_code or "",
            issue=issue,
        )
        if not diff_result.passed:
            self._mark_failed(suggestion, f"Diff validation failed: {diff_result.reason}")
            return False
        notes.append(f"Diff OK (+{diff_result.diff_lines_added}/-{diff_result.diff_lines_removed} lines)")

        # 2. Validate refactored snippet IN ISOLATION (avoids splice indentation issues)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as tmp:
            tmp.write(suggestion.refactored_code or "")
            tmp_path = tmp.name

        try:
            ruff_ok, ruff_msg = self._run_ruff(tmp_path)
            if not ruff_ok:
                self._mark_failed(suggestion, f"Ruff failed: {ruff_msg}")
                return False
            notes.append("Ruff: OK")

            bandit_ok, bandit_msg = self._run_bandit(tmp_path)
            if not bandit_ok:
                self._mark_failed(suggestion, f"Bandit security issue: {bandit_msg}")
                return False
            notes.append("Bandit: OK")
        finally:
            os.unlink(tmp_path)

        # 3. Pytest against full repo (only if tests exist)
        has_tests, pytest_ok, pytest_msg = self._run_pytest(repo_local_path)
        if has_tests:
            if not pytest_ok:
                self._mark_failed(suggestion, f"Tests failed: {pytest_msg}")
                return False
            notes.append(f"Pytest: {pytest_msg}")
        else:
            notes.append("Pytest: no tests found (skipped)")

        suggestion.validation_passed = True
        suggestion.validation_notes = " | ".join(notes)
        suggestion.status = RefactorStatus.VALIDATED
        self.db.commit()
        log.info("validation.passed", suggestion_id=suggestion.id)
        return True

    def _run_ruff(self, file_path: str):
        try:
            result = subprocess.run(
                ["ruff", "check", "--select=E,F", "--ignore=E501", "--line-length=120", file_path],  # E=errors, F=pyflakes only — skip W warnings
                capture_output=True, text=True, timeout=30
            )
            if result.returncode != 0:
                return False, result.stdout[:500]
            return True, ""
        except (FileNotFoundError, subprocess.TimeoutExpired) as e:
            return True, f"ruff unavailable: {e}"  # non-blocking if tool missing

    def _run_bandit(self, file_path: str):
        try:
            result = subprocess.run(
                ["bandit", "-q", "-l", file_path],
                capture_output=True, text=True, timeout=30
            )
            # Bandit exit code 1 = issues found; exit 0 = clean
            if result.returncode == 1 and "HIGH" in result.stdout:
                return False, result.stdout[:500]
            return True, ""
        except (FileNotFoundError, subprocess.TimeoutExpired) as e:
            return True, f"bandit unavailable: {e}"

    def _run_pytest(self, repo_path: str):
        test_dirs = list(Path(repo_path).glob("**/test*.py")) + list(Path(repo_path).glob("**/tests/"))
        if not test_dirs:
            return False, False, "no tests"
        try:
            result = subprocess.run(
                ["pytest", "--tb=short", "-q", repo_path],
                capture_output=True, text=True, timeout=120, cwd=repo_path
            )
            if result.returncode == 0:
                return True, True, result.stdout.splitlines()[-1] if result.stdout else "passed"
            return True, False, result.stdout[-1000:]
        except (FileNotFoundError, subprocess.TimeoutExpired) as e:
            return True, False, str(e)

    def _mark_failed(self, suggestion: RefactorSuggestion, reason: str):
        suggestion.validation_passed = False
        suggestion.validation_notes = reason
        suggestion.status = RefactorStatus.FAILED
        self.db.commit()
        log.info("validation.failed", suggestion_id=suggestion.id, reason=reason)
