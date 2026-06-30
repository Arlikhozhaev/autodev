"""
Refactor Service
Generates safe, validated refactors using Claude with an intelligent retry loop.

Pipeline per issue:
  1. Build a precise, constraint-rich prompt
  2. Call LLM → parse output
  3. Run fast in-memory validation (AST + syntax + diff)
  4. If validation fails → retry with exact error feedback (up to MAX_ATTEMPTS)
  5. On success → save to DB
  6. Never saves a suggestion that fails validation
"""
import ast
import subprocess
import tempfile
import os
import time
from typing import Optional

import anthropic
import structlog
from sqlalchemy.orm import Session

from app.config import settings
from app.models.analysis import CodeIssue, RefactorSuggestion, RefactorStatus, IssueType
from app.utils.diff_validator import DiffValidator

log = structlog.get_logger()

MAX_ATTEMPTS = 3


# ── Prompt templates ──────────────────────────────────────────────────────────

BASE_RULES = """
STRICT OUTPUT FORMAT:
- Output ONLY valid Python code first, then the separator, then explanation.
- NO markdown fences (no ```python). NO preamble. NO "Here is the refactored code:".
- All lines MUST be under 100 characters.
- The code MUST be syntactically valid Python (will be run through ast.parse).
- After the code, output exactly this separator on its own line: ### EXPLANATION ###
- After the separator, explain your changes as bullet points starting with "- ".

STRICT CODE RULES:
- Preserve ALL existing behavior exactly — same inputs produce same outputs.
- Keep ALL public function names and signatures IDENTICAL (unless the issue is long_params).
- Do NOT add comments, docstrings, or type hints unless they already exist.
- Do NOT introduce any third-party imports (stdlib like dataclasses, typing is OK).
- Helper functions you introduce MUST be defined BEFORE the main function.
- Every function you output MUST be complete — no ellipsis, no placeholders.
"""

PROMPTS = {
    IssueType.COMPLEXITY: """\
You are a senior Python engineer performing a surgical refactor.

ISSUE: Cyclomatic complexity is {metric_value} (threshold: 10). Reduce it below 6.

HOW TO FIX:
- Extract complex logic into small private helper functions (_name convention).
- Use early returns / guard clauses to flatten conditionals.
- Each helper should do ONE thing and have complexity ≤ 3.
{base_rules}
ORIGINAL CODE (replace this entire block):
{code}
""",

    IssueType.DEEP_NESTING: """\
You are a senior Python engineer performing a surgical refactor.

ISSUE: Nesting depth is {metric_value} (threshold: 3). Reduce it to ≤ 2.

HOW TO FIX:
- Use early returns / guard clauses to invert conditions.
- Extract deeply nested blocks into private helper functions.
- Never nest more than 2 levels in any function you output.
{base_rules}
ORIGINAL CODE (replace this entire block):
{code}
""",

    IssueType.LONG_FUNCTION: """\
You are a senior Python engineer performing a surgical refactor.

ISSUE: Function is {metric_value} lines (threshold: 50). Break it up.

HOW TO FIX:
- Extract cohesive blocks into well-named private helpers.
- The main function should read like a high-level summary of steps.
- Each helper should be ≤ 20 lines.
{base_rules}
ORIGINAL CODE (replace this entire block):
{code}
""",

    IssueType.LONG_PARAMS: """\
You are a senior Python engineer performing a surgical refactor.

ISSUE: Function has {metric_value} parameters (threshold: 6). Group them.

HOW TO FIX:
- Group related parameters into a @dataclass (from dataclasses import dataclass).
- The public function signature WILL change — this is expected and required.
- All existing callers would need to be updated (note this in explanation).
- Preserve all internal logic and return values exactly.
{base_rules}
ORIGINAL CODE (replace this entire block):
{code}
""",
}

DEFAULT_PROMPT = """\
You are a senior Python engineer performing a surgical refactor.

ISSUE: {issue_type} — {description}
{base_rules}
ORIGINAL CODE (replace this entire block):
{code}
"""

RETRY_PREFIX = """\
Your previous refactor attempt failed validation with this error:

ERROR: {error}

Fix ONLY this specific problem and output the complete corrected code.
Remember: all lines under 100 chars, valid Python syntax, no markdown fences.

### EXPLANATION ### separator required after the code.

ORIGINAL CODE (for reference):
{code}

YOUR PREVIOUS ATTEMPT (fix this):
{previous_code}
"""


class RefactorService:
    def __init__(self, db: Session):
        self.db = db
        self.client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        self.diff_validator = DiffValidator(max_size_change_pct=settings.MAX_FILE_SIZE_CHANGE_PCT)

    def refactor_issue(self, issue: CodeIssue) -> Optional[RefactorSuggestion]:
        if not issue.original_code or not issue.original_code.strip():
            log.warning("refactor.no_code", issue_id=issue.id)
            return None

        # Reuse or create suggestion record
        existing = self.db.query(RefactorSuggestion).filter(
            RefactorSuggestion.issue_id == issue.id
        ).first()
        suggestion = existing or RefactorSuggestion(
            issue_id=issue.id,
            repo_id=issue.repo_id,
        )

        # ── Retry loop ────────────────────────────────────────────────────────
        prompt          = self._build_prompt(issue)
        previous_code   = None
        last_error      = None
        total_tokens    = 0

        for attempt in range(1, MAX_ATTEMPTS + 1):
            log.info("refactor.attempt", issue_id=issue.id, attempt=attempt)

            if attempt > 1 and previous_code and last_error:
                prompt = RETRY_PREFIX.format(
                    error=last_error,
                    code=issue.original_code,
                    previous_code=previous_code,
                )

            code, explanation, tokens = self._call_llm(prompt, issue.id)
            total_tokens += tokens

            if not code:
                last_error = "LLM returned empty response"
                continue

            # Fast in-memory validation before saving
            error = self._quick_validate(code, issue)
            if error:
                log.warning("refactor.validation_failed",
                           issue_id=issue.id, attempt=attempt, error=error)
                last_error    = error
                previous_code = code
                continue

            # Passed — save and return
            suggestion.refactored_code  = code
            suggestion.explanation      = explanation
            suggestion.tokens_used      = total_tokens
            suggestion.status           = RefactorStatus.GENERATED
            suggestion.lines_before     = len(issue.original_code.splitlines())
            suggestion.lines_after      = len(code.splitlines())

            if issue.metric_value and issue.issue_type == IssueType.COMPLEXITY:
                suggestion.complexity_before = int(issue.metric_value)
                try:
                    from radon.complexity import cc_visit
                    blocks = cc_visit(code)
                    if blocks:
                        suggestion.complexity_after = max(b.complexity for b in blocks)
                except Exception:
                    pass

            self.db.add(suggestion)
            self.db.commit()
            log.info("refactor.generated", issue_id=issue.id,
                    attempt=attempt, tokens=total_tokens)
            return suggestion

        # All attempts failed
        log.error("refactor.all_attempts_failed",
                 issue_id=issue.id, last_error=last_error)
        suggestion.status         = RefactorStatus.FAILED
        suggestion.tokens_used    = total_tokens
        suggestion.validation_notes = f"All {MAX_ATTEMPTS} attempts failed. Last error: {last_error}"
        self.db.add(suggestion)
        self.db.commit()
        return suggestion

    def _quick_validate(self, code: str, issue: CodeIssue) -> Optional[str]:
        """
        Fast in-memory checks before saving. Returns error string or None if clean.
        These run BEFORE the full file splice validation in git_service.
        """
        # 1. AST syntax
        try:
            ast.parse(code)
        except SyntaxError as e:
            return f"SyntaxError at line {e.lineno}: {e.msg}"

        # 2. All lines under 100 chars
        for i, line in enumerate(code.splitlines(), 1):
            if len(line) > 100:
                return f"Line {i} is {len(line)} chars (max 100): {line[:60]}..."

        # 3. No incomplete functions (ellipsis placeholder)
        if "..." in code and "Ellipsis" not in code:
            try:
                tree = ast.parse(code)
                for node in ast.walk(tree):
                    if isinstance(node, ast.Expr) and isinstance(
                        getattr(node, 'value', None), ast.Constant
                    ) and node.value.value is ...:
                        return "Code contains '...' placeholder — function is incomplete"
            except Exception:
                pass

        # 4. Signature preservation (skip for long_params — changing sig is the whole point)
        if issue.issue_type != IssueType.LONG_PARAMS and issue.original_code:
            try:
                orig_tree = ast.parse(issue.original_code)
                new_tree  = ast.parse(code)
                orig_sigs = {
                    n.name: [a.arg for a in n.args.args]
                    for n in ast.walk(orig_tree)
                    if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and not n.name.startswith("_")
                }
                new_sigs = {
                    n.name: [a.arg for a in n.args.args]
                    for n in ast.walk(new_tree)
                    if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                }
                for name, sig in orig_sigs.items():
                    if name not in new_sigs:
                        return f"Public function '{name}' was removed"
                    if sig != new_sigs[name]:
                        return f"Signature of '{name}' changed from {sig} to {new_sigs[name]}"
            except SyntaxError:
                pass

        # 5. Ruff lint (non-blocking on tool absence)
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".py", delete=False
            ) as tmp:
                tmp.write(code)
                tmp_path = tmp.name
            try:
                result = subprocess.run(
                    ["ruff", "check", "--select=E,F", "--ignore=E501",
                     "--line-length=120", tmp_path],
                    capture_output=True, text=True, timeout=15
                )
                if result.returncode != 0:
                    # Only fail on real errors, not style
                    errors = [
                        l for l in result.stdout.splitlines()
                        if ": E" in l or ": F" in l
                    ]
                    if errors:
                        return f"Ruff: {'; '.join(errors[:3])}"
            finally:
                os.unlink(tmp_path)
        except Exception:
            pass  # non-blocking if ruff unavailable

        return None

    def _build_prompt(self, issue: CodeIssue) -> str:
        template = PROMPTS.get(issue.issue_type)
        if template:
            return template.format(
                metric_value=int(issue.metric_value) if issue.metric_value else "N/A",
                code=issue.original_code,
                base_rules=BASE_RULES,
            )
        return DEFAULT_PROMPT.format(
            issue_type=issue.issue_type,
            description=issue.description,
            code=issue.original_code,
            base_rules=BASE_RULES,
        )

    def _call_llm(self, prompt: str, issue_id: str):
        for attempt in range(settings.LLM_MAX_RETRIES):
            try:
                response = self.client.messages.create(
                    model=settings.LLM_MODEL,
                    max_tokens=settings.LLM_MAX_TOKENS,
                    temperature=settings.LLM_TEMPERATURE,
                    messages=[{"role": "user", "content": prompt}],
                )
                raw    = response.content[0].text.strip()
                tokens = response.usage.input_tokens + response.usage.output_tokens
                code, explanation = self._parse_response(raw)
                return code, explanation, tokens

            except anthropic.RateLimitError:
                wait = 2 ** attempt * 5
                log.warning("llm.rate_limited", wait=wait, issue_id=issue_id)
                time.sleep(wait)
            except anthropic.APITimeoutError:
                log.warning("llm.timeout", attempt=attempt, issue_id=issue_id)
                time.sleep(3)
            except Exception as e:
                log.error("llm.error", error=str(e), issue_id=issue_id)
                break

        return None, None, 0

    def _parse_response(self, raw: str):
        separator = "### EXPLANATION ###"
        if separator in raw:
            parts       = raw.split(separator, 1)
            code        = parts[0].strip()
            explanation = parts[1].strip() if len(parts) > 1 else ""
        else:
            code        = raw
            explanation = ""

        # Strip markdown fences
        if code.startswith("```"):
            lines = code.splitlines()
            end   = len(lines) - 1 if lines[-1].strip() == "```" else len(lines)
            code  = "\n".join(lines[1:end])

        code = code.strip()

        # Ensure single trailing newline
        code = code.rstrip("\n") + "\n"

        return code, explanation
