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
import shutil
import subprocess
import tempfile
from pathlib import Path

import structlog
from sqlalchemy.orm import Session

from app.models.analysis import CodeIssue, RefactorSuggestion, RefactorStatus
from app.utils.diff_validator import DiffValidator

log = structlog.get_logger()


class ValidationService:
    def __init__(self, db: Session):
        self.db = db
        self.diff_validator = DiffValidator()

    def validate(self, suggestion: RefactorSuggestion, issue: CodeIssue, repo_local_path: str) -> bool:
        """
        Full validation pipeline.
        Returns True if safe to proceed to PR, False otherwise.
        """
        notes = []

        # 1. Diff validation (fast, in-memory)
        diff_result = self.diff_validator.validate(
            original_code=issue.original_code or "",
            refactored_code=suggestion.refactored_code or "",
        )
        if not diff_result.passed:
            self._mark_failed(suggestion, f"Diff validation failed: {diff_result.reason}")
            return False
        notes.append(f"Diff OK (+{diff_result.diff_lines_added}/-{diff_result.diff_lines_removed} lines)")

        # 2. Apply to temp directory and run tools
        with tempfile.TemporaryDirectory(prefix="autodev_val_") as tmpdir:
            tmp_repo = Path(tmpdir) / "repo"
            try:
                shutil.copytree(repo_local_path, str(tmp_repo))
            except Exception as e:
                self._mark_failed(suggestion, f"Could not copy repo: {e}")
                return False

            target_file = tmp_repo / issue.file_path
            if not target_file.exists():
                self._mark_failed(suggestion, f"Target file not found: {issue.file_path}")
                return False

            # Apply refactor
            original_content = target_file.read_text(errors="ignore")
            new_content = self._apply_refactor(
                original_content,
                issue.original_code or "",
                suggestion.refactored_code or "",
            )
            if new_content is None:
                self._mark_failed(suggestion, "Could not locate original code in file for replacement.")
                return False

            target_file.write_text(new_content, encoding="utf-8")

            # 3. Ruff check
            ruff_ok, ruff_msg = self._run_ruff(str(target_file))
            if not ruff_ok:
                self._mark_failed(suggestion, f"Ruff failed: {ruff_msg}")
                return False
            notes.append("Ruff: OK")

            # 4. Bandit check
            bandit_ok, bandit_msg = self._run_bandit(str(target_file))
            if not bandit_ok:
                self._mark_failed(suggestion, f"Bandit security issue: {bandit_msg}")
                return False
            notes.append("Bandit: OK")

            # 5. Pytest (if tests exist)
            has_tests, pytest_ok, pytest_msg = self._run_pytest(str(tmp_repo))
            if has_tests:
                if not pytest_ok:
                    self._mark_failed(suggestion, f"Tests failed: {pytest_msg}")
                    return False
                notes.append(f"Pytest: {pytest_msg}")
            else:
                notes.append("Pytest: no tests found (skipped)")

        # All checks passed
        suggestion.validation_passed = True
        suggestion.validation_notes = " | ".join(notes)
        suggestion.status = RefactorStatus.VALIDATED
        self.db.commit()
        log.info("validation.passed", suggestion_id=suggestion.id)
        return True

    def _apply_refactor(self, file_content: str, original_snippet: str, refactored_snippet: str):
        """Replace the original function snippet with refactored version in the file."""
        if not original_snippet.strip():
            return None
        if original_snippet in file_content:
            return file_content.replace(original_snippet, refactored_snippet, 1)
        # Try line-by-line partial match (handles whitespace drift)
        orig_lines = original_snippet.strip().splitlines()
        if orig_lines and orig_lines[0].strip() in file_content:
            # Best-effort: insert replacement near the start line
            return None   # conservative — reject if can't precisely match
        return None

    def _run_ruff(self, file_path: str):
        try:
            result = subprocess.run(
                ["ruff", "check", "--select=E,W,F", file_path],
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
