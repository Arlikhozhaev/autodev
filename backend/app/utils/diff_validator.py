"""
Diff Validator — safety checks before accepting a refactor.
"""
import ast
import difflib
import inspect
from dataclasses import dataclass
from typing import Optional

import structlog

log = structlog.get_logger()


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
    ) -> ValidationResult:
        # 1. Syntax check
        syntax_ok, err = self._check_syntax(refactored_code)
        if not syntax_ok:
            return ValidationResult(passed=False, reason=f"Syntax error: {err}")

        # 2. Size change
        size_result = self._check_size_change(original_code, refactored_code)
        if not size_result.passed:
            return size_result

        # 3. Signature preservation
        sig_ok, sig_err = self._check_signatures(original_code, refactored_code)
        if not sig_ok:
            return ValidationResult(passed=False, reason=sig_err)

        # 4. New imports check
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
        added   = sum(1 for l in diff if l.startswith("+") and not l.startswith("+++"))
        removed = sum(1 for l in diff if l.startswith("-") and not l.startswith("---"))

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

    def _check_size_change(self, original: str, refactored: str) -> ValidationResult:
        orig_lines = len(original.splitlines())
        ref_lines  = len(refactored.splitlines())
        if orig_lines == 0:
            return ValidationResult(passed=True)
        change_pct = abs(ref_lines - orig_lines) / orig_lines
        if change_pct > self.max_size_change_pct:
            return ValidationResult(
                passed=False,
                reason=f"Size changed by {change_pct:.1%}, exceeds {self.max_size_change_pct:.0%} limit.",
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
        """Reject refactors that silently add new third-party imports."""
        try:
            orig_tree = ast.parse(original)
            ref_tree  = ast.parse(refactored)
        except SyntaxError:
            return True, None

        orig_imports = set(self._get_imports(orig_tree))
        ref_imports  = set(self._get_imports(ref_tree))
        new_imports  = ref_imports - orig_imports

        if allowed:
            allowed_set = set(allowed)
            new_imports -= allowed_set

        if new_imports:
            return False, f"Unexpected new imports introduced: {new_imports}"
        return True, None

    def _get_imports(self, tree: ast.AST):
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    yield alias.name
            elif isinstance(node, ast.ImportFrom):
                yield node.module or ""
