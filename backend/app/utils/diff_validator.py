"""
Diff Validator — safety checks before accepting a refactor.
"""
import ast
import difflib
from dataclasses import dataclass
from typing import Optional

import structlog

from app.models.analysis import IssueType

log = structlog.get_logger()

# LLM structural refactors (extract helpers) may legitimately grow snippet size.
STRUCTURAL_REFACTOR_MAX_SIZE_CHANGE_PCT = 2.0


@dataclass
class ValidationResult:
    passed: bool
    reason: Optional[str] = None
    diff_lines_added: int = 0
    diff_lines_removed: int = 0
    size_change_pct: float = 0.0


class DiffValidator:
    """
    Validate that an LLM-generated refactor is safe to apply.
    Checks:
      1. Code is syntactically valid Python
      2. File size change < threshold
      3. Public function signatures are preserved
      4. No unexpected new imports
    """

    def __init__(self, max_size_change_pct: float = 0.30):
        self.max_size_change_pct = max_size_change_pct

    def validate(
        self,
        original_code: str,
        refactored_code: str,
        original_imports: Optional[list] = None,
        issue=None,
    ) -> ValidationResult:
        # 1. Syntax check
        syntax_ok, err = self._check_syntax(refactored_code)
        if not syntax_ok:
            return ValidationResult(passed=False, reason=f"Syntax error: {err}")

        # 2. Size change — structural refactors may add helper functions / dataclasses
        size_result = self._check_size_change(
            original_code,
            refactored_code,
            max_pct=STRUCTURAL_REFACTOR_MAX_SIZE_CHANGE_PCT,
        )
        if not size_result.passed:
            return size_result

        # 3. Signature preservation — skip for long_params (fixing it requires changing signature)
        if not _is_long_params_issue(issue):
            sig_ok, sig_err = self._check_signatures(original_code, refactored_code)
            if not sig_ok:
                return ValidationResult(passed=False, reason=sig_err)
        # 4. New imports check — only block third-party, allow stdlib
        import_ok, import_err = self._check_new_imports(
            original_code, refactored_code, original_imports
        )
        if not import_ok:
            return ValidationResult(passed=False, reason=import_err)

        # Compute diff stats
        diff = list(
            difflib.unified_diff(
                original_code.splitlines(), refactored_code.splitlines()
            )
        )
        added   = sum(1 for line in diff if line.startswith("+") and not line.startswith("+++"))
        removed = sum(1 for line in diff if line.startswith("-") and not line.startswith("---"))

        return ValidationResult(
            passed=True,
            diff_lines_added=added,
            diff_lines_removed=removed,
            size_change_pct=size_result.size_change_pct,
        )

    def _check_syntax(self, code: str):
        try:
            ast.parse(code)
            return True, None
        except SyntaxError as e:
            return False, str(e)

    def _check_size_change(self, original: str, refactored: str, max_pct: float = None) -> ValidationResult:
        limit = max_pct if max_pct is not None else self.max_size_change_pct
        orig_lines = len(original.splitlines())
        ref_lines  = len(refactored.splitlines())
        if orig_lines == 0:
            return ValidationResult(passed=True)
        change_pct = abs(ref_lines - orig_lines) / orig_lines
        if change_pct > limit:
            return ValidationResult(
                passed=False,
                reason=f"Size changed by {change_pct:.1%}, exceeds {limit:.0%} limit.",
                size_change_pct=change_pct,
            )
        return ValidationResult(passed=True, size_change_pct=change_pct)

    def _check_signatures(self, original: str, refactored: str):
        """Ensure all public functions in the original still exist with same signature."""
        try:
            orig_tree = ast.parse(original)
            ref_tree  = ast.parse(refactored)
        except SyntaxError:
            return True, None   # already caught in syntax check

        orig_sigs = self._extract_signatures(orig_tree)
        ref_sigs  = self._extract_signatures(ref_tree)

        for name, sig in orig_sigs.items():
            if name.startswith("_"):
                continue  # private — allow renaming
            if name not in ref_sigs:
                return False, f"Public function '{name}' was removed."
            if sig != ref_sigs[name]:
                return False, (
                    f"Signature of '{name}' changed: "
                    f"was {sig}, now {ref_sigs[name]}"
                )
        return True, None

    def _extract_signatures(self, tree: ast.AST) -> dict:
        sigs = {}
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                args = [a.arg for a in node.args.args]
                sigs[node.name] = args
        return sigs

    def _check_new_imports(self, original: str, refactored: str, allowed: Optional[list]):
        """Reject refactors that add new THIRD-PARTY imports. stdlib is always allowed."""
        import sys
        stdlib = set(sys.stdlib_module_names) if hasattr(sys, "stdlib_module_names") else {
            "dataclasses", "typing", "collections", "functools", "itertools",
            "pathlib", "os", "sys", "re", "abc", "enum", "contextlib",
            "datetime", "math", "string", "copy", "io", "json",
        }
        try:
            orig_tree = ast.parse(original)
            ref_tree  = ast.parse(refactored)
        except SyntaxError:
            return True, None

        orig_imports = set(self._get_imports(orig_tree))
        ref_imports  = set(self._get_imports(ref_tree))
        new_imports  = ref_imports - orig_imports

        # Remove stdlib and explicitly allowed
        new_imports -= stdlib
        if allowed:
            new_imports -= set(allowed)

        if new_imports:
            return False, f"Unexpected new third-party imports: {new_imports}"
        return True, None

    def _get_imports(self, tree: ast.AST):
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    yield alias.name
            elif isinstance(node, ast.ImportFrom):
                yield node.module or ""


def _is_long_params_issue(issue) -> bool:
    """Return True when the issue type is LONG_PARAMS (enum or string value)."""
    if issue is None:
        return False
    issue_type = getattr(issue, "issue_type", None)
    if issue_type is None:
        return False
    if issue_type == IssueType.LONG_PARAMS:
        return True
    return isinstance(issue_type, str) and issue_type == IssueType.LONG_PARAMS.value
