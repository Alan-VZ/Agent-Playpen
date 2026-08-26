# Guardrails (guardrails.py)
import re
from dataclasses import dataclass


@dataclass
class GuardrailResult:
    passed: bool
    reason: str = ""
    modified_text: str = ""


# ---- Input Guardrails ----

PROMPT_INJECTION_PATTERNS = [
    r"ignore\s+previous\s+instructions",
    r"disregard\s+all\s+prior",
    r"you\s+are\s+now\s+DAN",
    r"jailbreak",
    r"pretend\s+you\s+are\s+not",
]

PII_PATTERNS = {
    "email":  r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
    "phone":  r"\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b",
    "ssn":    r"\b\d{3}-\d{2}-\d{4}\b",
}


def check_prompt_injection(text: str) -> GuardrailResult:
    for pattern in PROMPT_INJECTION_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return GuardrailResult(
                passed=False,
                reason=f"Prompt injection pattern detected: '{pattern}'",
            )
    return GuardrailResult(passed=True)


def check_pii(text: str) -> GuardrailResult:
    found = []
    for pii_type, pattern in PII_PATTERNS.items():
        if re.search(pattern, text):
            found.append(pii_type)
    if found:
        return GuardrailResult(
            passed=False,
            reason=f"PII detected: {', '.join(found)}",
        )
    return GuardrailResult(passed=True)


# ---- Output Guardrails ----

BLOCKED_OUTPUT_KEYWORDS = [
    "I cannot help with that",
    "I'm unable to assist",
]


def check_output_length(text: str, max_chars: int = 8000) -> GuardrailResult:
    if len(text) > max_chars:
        return GuardrailResult(
            passed=True,
            reason=f"Truncated from {len(text)} to {max_chars} chars.",
            modified_text=text[:max_chars],
        )
    return GuardrailResult(passed=True, modified_text=text)


def check_safety_keywords(text: str) -> GuardrailResult:
    for kw in BLOCKED_OUTPUT_KEYWORDS:
        if kw.lower() in text.lower():
            return GuardrailResult(
                passed=False,
                reason=f"Blocked keyword in output: '{kw}'",
            )
    return GuardrailResult(passed=True, modified_text=text)


class Guardrails:
    """Apply all configured input and output guardrails."""

    def check_input(self, text: str) -> GuardrailResult:
        for fn in [check_prompt_injection, check_pii]:
            result = fn(text)
            if not result.passed:
                return result
        return GuardrailResult(passed=True)

    def check_output(self, text: str, max_chars: int = 8000) -> GuardrailResult:
        length_result = check_output_length(text, max_chars)
        text = length_result.modified_text or text
        safety_result = check_safety_keywords(text)
        if not safety_result.passed:
            return safety_result
        return GuardrailResult(passed=True, modified_text=text)
    