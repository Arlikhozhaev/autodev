"""
AST Parser — extracts structural metrics from Python files via the stdlib ast module.
"""
import ast
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

import structlog

log = structlog.get_logger()


@dataclass
class FunctionInfo:
    name: str
    file_path: str
    line_start: int
    line_end: int
    line_count: int
    param_count: int
    nesting_depth: int
    source_code: str


@dataclass
class FileASTResult:
    file_path: str
    functions: List[FunctionInfo] = field(default_factory=list)
    imports: List[str] = field(default_factory=list)
    parse_error: Optional[str] = None


class ASTParser:
    """Parse Python files and extract structural function information."""

    def parse_file(self, file_path: str) -> FileASTResult:
        result = FileASTResult(file_path=file_path)
        try:
            source = Path(file_path).read_text(encoding="utf-8", errors="ignore")
            tree = ast.parse(source)
            lines = source.splitlines()

            result.imports = self._extract_imports(tree)
            result.functions = self._extract_functions(tree, lines, file_path)
        except SyntaxError as e:
            result.parse_error = str(e)
            log.warning("ast.parse_error", file=file_path, error=str(e))
        except Exception as e:
            result.parse_error = str(e)
        return result

    def _extract_imports(self, tree: ast.AST) -> List[str]:
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                for alias in node.names:
                    imports.append(f"{module}.{alias.name}")
        return imports

    def _extract_functions(
        self, tree: ast.AST, lines: List[str], file_path: str
    ) -> List[FunctionInfo]:
        functions = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                line_start = node.lineno
                line_end = node.end_lineno or line_start
                source_lines = lines[line_start - 1 : line_end]
                source_code = "\n".join(source_lines)

                functions.append(
                    FunctionInfo(
                        name=node.name,
                        file_path=file_path,
                        line_start=line_start,
                        line_end=line_end,
                        line_count=line_end - line_start + 1,
                        param_count=len(node.args.args),
                        nesting_depth=self._max_nesting_depth(node),
                        source_code=source_code,
                    )
                )
        return functions

    def _max_nesting_depth(self, node: ast.AST, current: int = 0) -> int:
        """Recursively find max nesting depth of loops/conditionals."""
        max_depth = current
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.For, ast.While, ast.If, ast.With, ast.Try)):
                depth = self._max_nesting_depth(child, current + 1)
                max_depth = max(max_depth, depth)
            else:
                depth = self._max_nesting_depth(child, current)
                max_depth = max(max_depth, depth)
        return max_depth


def collect_python_files(base_path: str) -> List[str]:
    """Walk directory and return all .py files, excluding virtualenvs and caches."""
    EXCLUDED = {
        ".git", "__pycache__", ".venv", "venv", "env",
        "node_modules", ".mypy_cache", ".pytest_cache",
        "dist", "build", "*.egg-info",
    }
    py_files = []
    for root, dirs, files in os.walk(base_path):
        dirs[:] = [d for d in dirs if d not in EXCLUDED and not d.endswith(".egg-info")]
        for f in files:
            if f.endswith(".py"):
                py_files.append(os.path.join(root, f))
    return py_files
