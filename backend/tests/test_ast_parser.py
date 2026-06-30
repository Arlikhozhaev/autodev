"""Tests for ASTParser and file collection utilities."""
import textwrap
from pathlib import Path

import pytest

from app.utils.ast_parser import ASTParser, collect_python_files


@pytest.fixture
def sample_py(tmp_path: Path) -> Path:
    content = textwrap.dedent(
        """
        import os
        from typing import List

        def shallow():
            return 1

        def deeply_nested():
            for i in range(3):
                if i > 0:
                    for j in range(2):
                        if j == 1:
                            return i + j
            return 0

        def many_params(a, b, c, d, e, f, g):
            return a
        """
    )
    file_path = tmp_path / "sample.py"
    file_path.write_text(content, encoding="utf-8")
    return file_path


class TestASTParser:
    def test_parse_file_extracts_functions(self, sample_py):
        result = ASTParser().parse_file(str(sample_py))
        assert result.parse_error is None
        names = {fn.name for fn in result.functions}
        assert names == {"shallow", "deeply_nested", "many_params"}

    def test_parse_file_extracts_imports(self, sample_py):
        result = ASTParser().parse_file(str(sample_py))
        assert "os" in result.imports
        assert any("typing" in imp for imp in result.imports)

    def test_nesting_depth_computed(self, sample_py):
        result = ASTParser().parse_file(str(sample_py))
        nested = next(fn for fn in result.functions if fn.name == "deeply_nested")
        assert nested.nesting_depth >= 3

    def test_param_count_computed(self, sample_py):
        result = ASTParser().parse_file(str(sample_py))
        many = next(fn for fn in result.functions if fn.name == "many_params")
        assert many.param_count == 7

    def test_source_code_captured(self, sample_py):
        result = ASTParser().parse_file(str(sample_py))
        shallow = next(fn for fn in result.functions if fn.name == "shallow")
        assert "return 1" in shallow.source_code

    def test_syntax_error_reported(self, tmp_path):
        bad_file = tmp_path / "bad.py"
        bad_file.write_text("def broken(\n", encoding="utf-8")
        result = ASTParser().parse_file(str(bad_file))
        assert result.parse_error is not None
        assert result.functions == []


class TestCollectPythonFiles:
    def test_collects_py_files(self, tmp_path):
        (tmp_path / "a.py").write_text("x = 1\n")
        (tmp_path / "b.txt").write_text("not python\n")
        sub = tmp_path / "pkg"
        sub.mkdir()
        (sub / "c.py").write_text("y = 2\n")
        files = collect_python_files(str(tmp_path))
        assert len(files) == 2
        assert any(f.endswith("a.py") for f in files)
        assert any(f.endswith("c.py") for f in files)

    def test_excludes_venv_and_cache(self, tmp_path):
        (tmp_path / "main.py").write_text("x = 1\n")
        venv = tmp_path / ".venv"
        venv.mkdir()
        (venv / "hidden.py").write_text("hidden\n")
        cache = tmp_path / "__pycache__"
        cache.mkdir()
        (cache / "cached.py").write_text("cached\n")
        files = collect_python_files(str(tmp_path))
        assert len(files) == 1
        assert files[0].endswith("main.py")
