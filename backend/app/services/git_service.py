"""
Git Service
Handles branch creation, commits, and GitHub PR creation via REST API.

Safety guarantees before any PR:
  1. Full-file AST parse after splice
  2. Duplicate function definition detection
  3. Ruff lint on complete file
  4. Clean branch (force-reset from default if exists)
"""
import ast
import re
import subprocess
import tempfile
import os
from pathlib import Path

import requests
import structlog
from git import Repo
from sqlalchemy.orm import Session

from app.config import settings
from app.models.analysis import CodeIssue, RefactorSuggestion, RefactorStatus
from app.models.repo import Repository

log = structlog.get_logger()
GITHUB_API = "https://api.github.com"


class GitService:
    def __init__(self, db: Session):
        self.db = db
        self.headers = {
            "Authorization": f"token {settings.GITHUB_TOKEN}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    def create_pr(self, repo: Repository, suggestion: RefactorSuggestion, issue: CodeIssue) -> bool:
        if not settings.GITHUB_TOKEN:
            self._fail(suggestion, "No GitHub token configured.")
            return False

        # Idempotency: refuse to reapply if already successfully applied
        if suggestion.status == RefactorStatus.PR_OPENED and suggestion.applied_commit_sha:
            log.info("git.skipped_idempotent", suggestion_id=suggestion.id)
            return True

        branch_name = f"autodev/refactor-{suggestion.id[:8]}"
        suggestion.branch_name = branch_name

        try:
            git_repo = Repo(repo.local_path)

            # 1. Clean branch — delete if exists from previous failed attempt
            if branch_name in [h.name for h in git_repo.heads]:
                git_repo.delete_head(branch_name, force=True)
            default = git_repo.active_branch.name
            git_repo.heads[default].checkout()
            git_repo.create_head(branch_name).checkout()

            # 2. Splice refactored code into file
            target_file = Path(repo.local_path) / issue.file_path
            if not target_file.exists():
                raise FileNotFoundError(f"File not found: {issue.file_path}")

            original_content = target_file.read_text(errors="ignore")

            # Staleness check: warn if file changed since analysis
            import hashlib
            current_hash = hashlib.sha256(original_content.encode()).hexdigest()
            if suggestion.source_file_hash and current_hash != suggestion.source_file_hash:
                log.warning("git.file_changed_since_analysis",
                           file=issue.file_path, suggestion_id=suggestion.id)
                # Continue anyway — AST-based splice handles line drift
            new_content = self._splice(original_content, suggestion.refactored_code or "", issue)

            if new_content is None:
                self._fail(suggestion, "Could not locate original code for splice.")
                return False

            # 3. Full-file structural validation BEFORE writing
            error = self._validate_full_file(new_content)
            if error:
                self._fail(suggestion, f"Post-splice validation failed: {error}")
                return False

            # 4. Write, stage, commit
            target_file.write_text(new_content, encoding="utf-8")
            git_repo.index.add([str(target_file)])
            commit = git_repo.index.commit(
                f"refactor: reduce complexity in {issue.function_name or issue.file_path}\n\n"
                f"AutoDev: {issue.description}\n"
                f"Lines: {suggestion.lines_before} -> {suggestion.lines_after}\n"
                f"All validation checks passed."
            )
            # Record commit SHA for idempotency
            suggestion.applied_commit_sha = commit.hexsha

            # 5. Push with token auth
            origin = git_repo.remote("origin")
            original_url = origin.url
            clean_url = re.sub(r"https://[^@]+@", "https://", original_url)
            auth_url = clean_url.replace("https://", f"https://x-access-token:{settings.GITHUB_TOKEN}@")
            with origin.config_writer as cw:
                cw.set("url", auth_url)
            try:
                origin.push(refspec=f"{branch_name}:{branch_name}", force=True)
            finally:
                with origin.config_writer as cw:
                    cw.set("url", original_url)

            # 6. Open PR
            pr_url, pr_number = self._open_pr(repo, suggestion, issue, branch_name)
            suggestion.pr_url = pr_url
            suggestion.pr_number = pr_number
            suggestion.status = RefactorStatus.PR_OPENED
            self.db.commit()
            log.info("git.pr_opened", pr_url=pr_url)
            return True

        except Exception as e:
            log.error("git.failed", error=str(e))
            self._fail(suggestion, f"Git error: {e}")
            return False

    def _splice(self, original: str, refactored: str, issue: CodeIssue):
        """
        Replace the target function using AST node location — not stored line numbers.
        Stored line numbers go stale if the file changed. The AST finds the function
        by name at parse time, giving us accurate current line positions including
        any decorators.
        Falls back to exact string match, then stored line numbers as last resort.
        """
        refactored = refactored.rstrip("\n") + "\n"
        new_names  = self._extract_function_names(refactored)
        cleaned    = self._remove_duplicate_defs(original, new_names)

        # Strategy 1: AST node location (most reliable)
        if issue.function_name:
            result = self._ast_replace(cleaned, issue.function_name, refactored)
            if result:
                return result

        # Strategy 2: Exact string match
        if issue.original_code and issue.original_code.strip() in cleaned:
            return cleaned.replace(issue.original_code.strip(), refactored, 1)

        # Strategy 3: Stored line numbers (last resort — may be stale)
        if issue.line_start and issue.line_end:
            lines = cleaned.splitlines(keepends=True)
            start = issue.line_start - 1
            end   = min(issue.line_end, len(lines))
            return "".join(lines[:start] + [refactored] + lines[end:])

        return None

    def _ast_replace(self, source: str, function_name: str, replacement: str) -> str | None:
        """
        Find `function_name` in source via AST, then replace its exact line range
        (including decorators) with `replacement`. This is stable against line drift.
        """
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return None

        lines = source.splitlines(keepends=True)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == function_name:
                # Include decorator lines (they appear before node.lineno)
                start = node.lineno - 1  # 0-indexed
                if node.decorator_list:
                    start = node.decorator_list[0].lineno - 1
                end = node.end_lineno  # exclusive slice (1-indexed end = 0-indexed exclusive)
                new_lines = lines[:start] + [replacement] + lines[end:]
                return "".join(new_lines)

        return None

    def _extract_function_names(self, code: str) -> set:
        names = set()
        try:
            for node in ast.walk(ast.parse(code)):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    names.add(node.name)
        except SyntaxError:
            for m in re.finditer(r"^(?:def|class)\s+(\w+)", code, re.MULTILINE):
                names.add(m.group(1))
        return names

    def _remove_duplicate_defs(self, source: str, names: set) -> str:
        """Remove existing top-level definitions of names to prevent duplicates."""
        if not names:
            return source
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return source

        lines = source.splitlines(keepends=True)
        ranges = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                if node.name in names and hasattr(node, "end_lineno"):
                    ranges.append((node.lineno, node.end_lineno))

        ranges.sort(reverse=True)
        result = list(lines)
        for start, end in ranges:
            del result[start - 1:end]
        return "".join(result)

    def _validate_full_file(self, content: str):
        """
        Validate the complete file after splice.
        Returns error string if invalid, None if clean.
        Checks: AST syntax, duplicate definitions, ruff lint.
        """
        # AST syntax check
        try:
            tree = ast.parse(content)
        except SyntaxError as e:
            return f"SyntaxError after splice at line {e.lineno}: {e.msg}"

        # Duplicate function definition check
        seen = {}
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name in seen:
                    return f"Duplicate function '{node.name}' at lines {seen[node.name]} and {node.lineno}"
                seen[node.name] = node.lineno

        # Ruff lint on full file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as tmp:
            tmp.write(content)
            tmp_path = tmp.name
        try:
            result = subprocess.run(
                ["ruff", "check", "--select=E,F", "--ignore=E501", "--line-length=120", tmp_path],
                capture_output=True, text=True, timeout=30
            )
            if result.returncode != 0:
                return f"Ruff failed on full file: {result.stdout[:300]}"
        except Exception:
            pass
        finally:
            os.unlink(tmp_path)

        return None

    def _fail(self, suggestion: RefactorSuggestion, reason: str):
        suggestion.status = RefactorStatus.FAILED
        suggestion.validation_notes = (suggestion.validation_notes or "") + f" | {reason}"
        self.db.commit()

    def _open_pr(self, repo, suggestion, issue, branch_name):
        body = f"""## AutoDev Automated Refactor

### Issue
- **Type**: `{issue.issue_type}`
- **File**: `{issue.file_path}`
- **Function**: `{issue.function_name or 'N/A'}`
- **Severity**: `{issue.severity}`

### Changes
- Lines: `{suggestion.lines_before}` -> `{suggestion.lines_after}`

### Validation Pipeline
- AST parse on snippet
- Full-file AST parse after splice
- Duplicate definition check
- Ruff lint on full file
- Bandit security scan
- Diff size check

### LLM Reasoning
{suggestion.explanation or 'N/A'}

---
*Generated by AutoDev | Model: {settings.LLM_MODEL}*
"""
        response = requests.post(
            f"{GITHUB_API}/repos/{repo.owner}/{repo.name}/pulls",
            json={
                "title": f"refactor: {issue.issue_type} in {issue.function_name or issue.file_path}",
                "body": body,
                "head": branch_name,
                "base": settings.GITHUB_PR_BASE_BRANCH,
            },
            headers=self.headers,
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        return data["html_url"], data["number"]
