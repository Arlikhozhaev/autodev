"""Tests for DiffValidator safety checks."""
from types import SimpleNamespace

import pytest

from app.models.analysis import IssueType
from app.utils.diff_validator import DiffValidator, _is_long_params_issue


@pytest.fixture
def validator():
    return DiffValidator(max_size_change_pct=0.30)


class TestIsLongParamsIssue:
    def test_enum_value(self):
        issue = SimpleNamespace(issue_type=IssueType.LONG_PARAMS)
        assert _is_long_params_issue(issue) is True

    def test_string_value(self):
        issue = SimpleNamespace(issue_type="long_params")
        assert _is_long_params_issue(issue) is True

    def test_other_type(self):
        issue = SimpleNamespace(issue_type=IssueType.COMPLEXITY)
        assert _is_long_params_issue(issue) is False

    def test_none_issue(self):
        assert _is_long_params_issue(None) is False


class TestDiffValidator:
    def test_valid_refactor_passes(self, validator):
        original = "def add(a, b):\n    return a + b\n"
        refactored = "def add(a, b):\n    result = a + b\n    return result\n"
        result = validator.validate(original, refactored)
        assert result.passed is True
        assert result.diff_lines_added > 0

    def test_syntax_error_fails(self, validator):
        result = validator.validate("def f():\n    pass\n", "def f(\n")
        assert result.passed is False
        assert "Syntax error" in (result.reason or "")

    def test_size_change_exceeds_limit(self, validator):
        original = "x = 1\n"
        refactored = "\n".join(f"x{i} = {i}" for i in range(20)) + "\n"
        result = validator.validate(original, refactored)
        assert result.passed is False
        assert "Size changed" in (result.reason or "")

    def test_signature_change_fails(self, validator):
        original = "def compute(x, y):\n    return x + y\n"
        refactored = "def compute(x, y, z):\n    return x + y + z\n"
        issue = SimpleNamespace(issue_type=IssueType.COMPLEXITY)
        result = validator.validate(original, refactored, issue=issue)
        assert result.passed is False
        assert "Signature" in (result.reason or "")

    def test_long_params_allows_signature_change(self, validator):
        original = "def process(a, b, c, d, e, f, g):\n    return a\n"
        refactored = (
            "def process(a, b, c, d, e, f):\n"
            "    return process_all(a, b, c, d, e, f)\n"
        )
        issue = SimpleNamespace(issue_type=IssueType.LONG_PARAMS)
        result = validator.validate(original, refactored, issue=issue)
        assert result.passed is True

    def test_unexpected_third_party_import_fails(self, validator):
        original = "def f():\n    return 1\n"
        refactored = "import requests\n\ndef f():\n    return 1\n"
        result = validator.validate(original, refactored)
        assert result.passed is False
        assert "imports" in (result.reason or "").lower()

    def test_stdlib_import_allowed(self, validator):
        original = "def f():\n    return 1\n"
        refactored = "from dataclasses import dataclass\n\ndef f():\n    return 1\n"
        result = validator.validate(original, refactored)
        assert result.passed is True

    def test_removed_public_function_fails(self, validator):
        original = "def keep():\n    pass\n\ndef remove_me():\n    pass\n"
        refactored = "def keep():\n    pass\n"
        result = validator.validate(original, refactored)
        assert result.passed is False
        assert "remove_me" in (result.reason or "")
