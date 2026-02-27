"""
Refactor Service
Uses Claude to generate safe, explainable refactors for detected issues.
Implements retry logic, token tracking, and structured prompt engineering.
"""
import time
from typing import Optional

import anthropic
import structlog
from sqlalchemy.orm import Session

from app.config import settings
from app.models.analysis import CodeIssue, RefactorSuggestion, RefactorStatus, IssueType

log = structlog.get_logger()

# ── Prompt templates per issue type ──────────────────────────────────────────

PROMPTS: dict[str, str] = {
    IssueType.COMPLEXITY: """You are a senior staff software engineer performing a precise, safe refactor.

The Python function below has HIGH CYCLOMATIC COMPLEXITY (score: {metric_value}).

STRICT RULES:
1. Reduce complexity by extracting helper functions or simplifying conditional logic.
2. Preserve ALL existing behavior exactly — do not change logic.
3. Keep all public function names and signatures identical.
4. Do NOT introduce new third-party dependencies.
5. Do NOT add any comments or docstrings unless they already exist.

Return ONLY:
- The refactored Python code (no markdown fences, no preamble).
- Then a separator line: ### EXPLANATION ###
- Then bullet-point reasoning (each starting with "- ").

Original code:
{code}""",

    IssueType.LONG_FUNCTION: """You are a senior staff software engineer performing a precise, safe refactor.

The Python function below is TOO LONG ({metric_value} lines).

STRICT RULES:
1. Break it into smaller, well-named helper functions.
2. Preserve ALL existing behavior exactly.
3. Keep the original public function name and signature.
4. Do NOT introduce new third-party dependencies.

Return ONLY:
- The refactored Python code (no markdown fences, no preamble).
- Then a separator: ### EXPLANATION ###
- Then bullet-point reasoning.

Original code:
{code}""",

    IssueType.DEEP_NESTING: """You are a senior staff software engineer performing a precise, safe refactor.

The Python function below has DEEP NESTING (depth: {metric_value}).

STRICT RULES:
1. Flatten nesting using early returns, guard clauses, or extracted helpers.
2. Preserve ALL existing behavior exactly.
3. Keep public function names and signatures identical.
4. Do NOT introduce new third-party dependencies.

Return ONLY:
- The refactored Python code (no markdown fences, no preamble).
- Then a separator: ### EXPLANATION ###
- Then bullet-point reasoning.

Original code:
{code}""",

    IssueType.LONG_PARAMS: """You are a senior staff software engineer performing a precise, safe refactor.

The Python function below has TOO MANY PARAMETERS ({metric_value}).

STRICT RULES:
1. Group related parameters into a dataclass or TypedDict.
2. Preserve ALL existing behavior exactly.
3. Keep the original function name.
4. Do NOT introduce new third-party dependencies beyond Python stdlib.

Return ONLY:
- The refactored Python code (no markdown fences, no preamble).
- Then a separator: ### EXPLANATION ###
- Then bullet-point reasoning.

Original code:
{code}""",
}

DEFAULT_PROMPT = """You are a senior staff software engineer.

Refactor the following Python code to improve quality.
Preserve all existing behavior. Keep public function signatures unchanged.
Do NOT introduce new third-party dependencies.

Return ONLY:
- The refactored Python code (no markdown fences, no preamble).
- Then a separator: ### EXPLANATION ###
- Then bullet-point reasoning.

Original code:
{code}"""


class RefactorService:
    def __init__(self, db: Session):
        self.db = db
        self.client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

    def refactor_issue(self, issue: CodeIssue) -> Optional[RefactorSuggestion]:
        if not issue.original_code or not issue.original_code.strip():
            log.warning("refactor.no_code", issue_id=issue.id)
            return None

        # Check for existing suggestion
        existing = self.db.query(RefactorSuggestion).filter(
            RefactorSuggestion.issue_id == issue.id
        ).first()
        suggestion = existing or RefactorSuggestion(
            issue_id=issue.id,
            repo_id=issue.repo_id,
        )

        prompt = self._build_prompt(issue)
        refactored_code, explanation, tokens = self._call_llm(prompt, issue.id)

        if not refactored_code:
            suggestion.status = RefactorStatus.FAILED
            self.db.add(suggestion)
            self.db.commit()
            return suggestion

        suggestion.refactored_code = refactored_code
        suggestion.explanation = explanation
        suggestion.tokens_used = tokens
        suggestion.status = RefactorStatus.GENERATED

        # Complexity metrics
        if issue.metric_value and issue.issue_type == IssueType.COMPLEXITY:
            suggestion.complexity_before = int(issue.metric_value)
            suggestion.lines_before = len(issue.original_code.splitlines())
            suggestion.lines_after  = len(refactored_code.splitlines())
            # Estimate complexity after (lightweight — full radon runs in validation)
            try:
                from radon.complexity import cc_visit
                blocks = cc_visit(refactored_code)
                if blocks:
                    suggestion.complexity_after = max(b.complexity for b in blocks)
            except Exception:
                pass
        else:
            suggestion.lines_before = len(issue.original_code.splitlines())
            suggestion.lines_after  = len(refactored_code.splitlines())

        self.db.add(suggestion)
        self.db.commit()
        log.info("refactor.generated", issue_id=issue.id, tokens=tokens)
        return suggestion

    def _build_prompt(self, issue: CodeIssue) -> str:
        template = PROMPTS.get(issue.issue_type, DEFAULT_PROMPT)
        return template.format(
            code=issue.original_code,
            metric_value=issue.metric_value or "N/A",
        )

    def _call_llm(self, prompt: str, issue_id: str):
        """Call Claude with retry logic and timeout."""
        for attempt in range(settings.LLM_MAX_RETRIES):
            try:
                response = self.client.messages.create(
                    model=settings.LLM_MODEL,
                    max_tokens=settings.LLM_MAX_TOKENS,
                    temperature=settings.LLM_TEMPERATURE,
                    messages=[{"role": "user", "content": prompt}],
                )
                raw = response.content[0].text.strip()
                tokens = response.usage.input_tokens + response.usage.output_tokens
                refactored, explanation = self._parse_response(raw)
                return refactored, explanation, tokens

            except anthropic.RateLimitError:
                wait = 2 ** attempt * 5
                log.warning("llm.rate_limited", attempt=attempt, wait=wait, issue_id=issue_id)
                time.sleep(wait)
            except anthropic.APITimeoutError:
                log.warning("llm.timeout", attempt=attempt, issue_id=issue_id)
                time.sleep(3)
            except Exception as e:
                log.error("llm.error", error=str(e), issue_id=issue_id)
                break

        return None, None, 0

    def _parse_response(self, raw: str):
        """Split response into code and explanation sections."""
        separator = "### EXPLANATION ###"
        if separator in raw:
            parts = raw.split(separator, 1)
            code  = parts[0].strip()
            explanation = parts[1].strip() if len(parts) > 1 else ""
        else:
            # LLM didn't follow format — treat entire response as code
            code = raw
            explanation = ""

        # Strip accidental markdown fences
        if code.startswith("```"):
            lines = code.splitlines()
            code  = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

        return code, explanation
