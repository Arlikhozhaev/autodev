"""
Analysis Service
Orchestrates all static analysis tools:
  - Radon  → cyclomatic complexity
  - Ruff   → lint errors
  - Bandit → security issues
  - AST    → structural metrics (long funcs, deep nesting, long params)
"""
import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import List

import structlog
from radon.complexity import cc_visit, cc_rank
from radon.metrics import mi_visit
from sqlalchemy.orm import Session

from app.config import settings
from app.models.repo import Repository, RepoStatus
from app.models.analysis import (
    AnalysisReport, CodeIssue, IssueType, IssueSeverity
)
from app.utils.ast_parser import ASTParser, collect_python_files

log = structlog.get_logger()


class AnalysisService:
    def __init__(self, db: Session):
        self.db = db
        self.ast_parser = ASTParser()

    def analyze(self, repo: Repository) -> AnalysisReport:
        repo.status = RepoStatus.ANALYZING
        self.db.commit()

        local_path = repo.local_path
        if not local_path or not Path(local_path).exists():
            raise ValueError(f"Repo not cloned: {repo.id}")

        py_files = collect_python_files(local_path)
        log.info("analysis.start", repo_id=repo.id, file_count=len(py_files))

        report = AnalysisReport(repo_id=repo.id, total_files=len(py_files))
        self.db.add(report)
        self.db.flush()

        all_issues: List[CodeIssue] = []
        total_complexity = []
        max_complexity = 0
        total_lines = 0

        for file_path in py_files:
            rel_path = str(Path(file_path).relative_to(local_path))

            # ── Cyclomatic complexity (Radon) ─────────────────────────────
            cc_issues, complexities = self._run_radon(file_path, rel_path, report.id, repo.id)
            all_issues.extend(cc_issues)
            total_complexity.extend(complexities)
            if complexities:
                max_complexity = max(max_complexity, max(complexities))

            # ── Lint errors (Ruff) ────────────────────────────────────────
            lint_issues = self._run_ruff(file_path, rel_path, report.id, repo.id)
            all_issues.extend(lint_issues)

            # ── Security (Bandit) ─────────────────────────────────────────
            sec_issues = self._run_bandit(file_path, rel_path, report.id, repo.id)
            all_issues.extend(sec_issues)

            # ── AST structural analysis ───────────────────────────────────
            ast_result = self.ast_parser.parse_file(file_path)
            ast_issues = self._analyze_ast(ast_result, rel_path, report.id, repo.id)
            all_issues.extend(ast_issues)

            # ── Line count ────────────────────────────────────────────────
            try:
                total_lines += len(Path(file_path).read_text(errors="ignore").splitlines())
            except Exception:
                pass

        # Bulk save issues
        self.db.add_all(all_issues)

        # Update report summary
        report.total_issues = len(all_issues)
        report.avg_complexity = (
            sum(total_complexity) / len(total_complexity) if total_complexity else 0.0
        )
        report.max_complexity = max_complexity
        report.total_lines = total_lines
        report.security_issues = sum(1 for i in all_issues if i.issue_type == IssueType.SECURITY)
        report.lint_errors = sum(1 for i in all_issues if i.issue_type == IssueType.LINT)

        repo.status = RepoStatus.DONE
        repo.last_analyzed_at = datetime.utcnow()
        self.db.commit()

        log.info(
            "analysis.complete",
            repo_id=repo.id,
            issues=len(all_issues),
            files=len(py_files),
        )
        return report

    # ── Radon ────────────────────────────────────────────────────────────────

    def _run_radon(self, file_path: str, rel_path: str, report_id: str, repo_id: str):
        issues = []
        complexities = []
        try:
            source = Path(file_path).read_text(errors="ignore")
            blocks = cc_visit(source)
            for block in blocks:
                complexities.append(block.complexity)
                if block.complexity > settings.MAX_CYCLOMATIC_COMPLEXITY:
                    severity = IssueSeverity.HIGH if block.complexity > 20 else IssueSeverity.MEDIUM
                    issues.append(CodeIssue(
                        report_id=report_id,
                        repo_id=repo_id,
                        file_path=rel_path,
                        function_name=block.name,
                        line_start=block.lineno,
                        line_end=getattr(block, "endline", block.lineno),
                        issue_type=IssueType.COMPLEXITY,
                        severity=severity,
                        description=f"Cyclomatic complexity {block.complexity} exceeds threshold {settings.MAX_CYCLOMATIC_COMPLEXITY}.",
                        metric_value=block.complexity,
                        original_code=self._extract_function_source(file_path, block.lineno),
                    ))
        except Exception as e:
            log.warning("radon.failed", file=rel_path, error=str(e))
        return issues, complexities

    # ── Ruff ─────────────────────────────────────────────────────────────────

    def _run_ruff(self, file_path: str, rel_path: str, report_id: str, repo_id: str):
        issues = []
        try:
            result = subprocess.run(
                ["ruff", "check", "--output-format=json", file_path],
                capture_output=True, text=True, timeout=30
            )
            if result.stdout:
                diagnostics = json.loads(result.stdout)
                for d in diagnostics[:20]:   # cap per file to avoid noise
                    issues.append(CodeIssue(
                        report_id=report_id,
                        repo_id=repo_id,
                        file_path=rel_path,
                        line_start=d.get("location", {}).get("row"),
                        issue_type=IssueType.LINT,
                        severity=IssueSeverity.LOW,
                        description=f"[{d.get('code')}] {d.get('message')}",
                        metric_value=None,
                    ))
        except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError) as e:
            log.warning("ruff.failed", file=rel_path, error=str(e))
        return issues

    # ── Bandit ───────────────────────────────────────────────────────────────

    def _run_bandit(self, file_path: str, rel_path: str, report_id: str, repo_id: str):
        issues = []
        try:
            result = subprocess.run(
                ["bandit", "-f", "json", "-q", file_path],
                capture_output=True, text=True, timeout=30
            )
            if result.stdout:
                data = json.loads(result.stdout)
                for r in data.get("results", []):
                    severity_map = {
                        "LOW": IssueSeverity.LOW,
                        "MEDIUM": IssueSeverity.MEDIUM,
                        "HIGH": IssueSeverity.HIGH,
                    }
                    issues.append(CodeIssue(
                        report_id=report_id,
                        repo_id=repo_id,
                        file_path=rel_path,
                        line_start=r.get("line_number"),
                        issue_type=IssueType.SECURITY,
                        severity=severity_map.get(r.get("issue_severity", "LOW"), IssueSeverity.LOW),
                        description=f"[{r.get('test_id')}] {r.get('issue_text')}",
                        metric_value=None,
                    ))
        except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError) as e:
            log.warning("bandit.failed", file=rel_path, error=str(e))
        return issues

    # ── AST structural ───────────────────────────────────────────────────────

    def _analyze_ast(self, ast_result, rel_path: str, report_id: str, repo_id: str):
        issues = []
        for fn in ast_result.functions:
            if fn.line_count > settings.MAX_FUNCTION_LINES:
                issues.append(CodeIssue(
                    report_id=report_id,
                    repo_id=repo_id,
                    file_path=rel_path,
                    function_name=fn.name,
                    line_start=fn.line_start,
                    line_end=fn.line_end,
                    issue_type=IssueType.LONG_FUNCTION,
                    severity=IssueSeverity.MEDIUM,
                    description=f"Function '{fn.name}' has {fn.line_count} lines (max {settings.MAX_FUNCTION_LINES}).",
                    metric_value=fn.line_count,
                    original_code=fn.source_code,
                ))
            if fn.nesting_depth > settings.MAX_NESTING_DEPTH:
                issues.append(CodeIssue(
                    report_id=report_id,
                    repo_id=repo_id,
                    file_path=rel_path,
                    function_name=fn.name,
                    line_start=fn.line_start,
                    line_end=fn.line_end,
                    issue_type=IssueType.DEEP_NESTING,
                    severity=IssueSeverity.MEDIUM,
                    description=f"Function '{fn.name}' has nesting depth {fn.nesting_depth} (max {settings.MAX_NESTING_DEPTH}).",
                    metric_value=fn.nesting_depth,
                    original_code=fn.source_code,
                ))
            if fn.param_count > settings.MAX_PARAMETERS:
                issues.append(CodeIssue(
                    report_id=report_id,
                    repo_id=repo_id,
                    file_path=rel_path,
                    function_name=fn.name,
                    line_start=fn.line_start,
                    line_end=fn.line_end,
                    issue_type=IssueType.LONG_PARAMS,
                    severity=IssueSeverity.LOW,
                    description=f"Function '{fn.name}' has {fn.param_count} parameters (max {settings.MAX_PARAMETERS}).",
                    metric_value=fn.param_count,
                    original_code=fn.source_code,
                ))
        return issues

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _extract_function_source(self, file_path: str, lineno: int) -> str:
        """Extract source lines around a function for LLM context."""
        try:
            lines = Path(file_path).read_text(errors="ignore").splitlines()
            start = max(0, lineno - 1)
            end   = min(len(lines), lineno + 80)
            return "\n".join(lines[start:end])
        except Exception:
            return ""
