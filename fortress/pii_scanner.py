"""Presidio-based PII + prompt-injection detection for DATA gate and audit DLP."""

from __future__ import annotations

import re
from functools import lru_cache
from typing import Any

PROMPT_INJECTION = re.compile(
    r"(ignore\s+previous\s+instructions|reveal\s+(the\s+)?system\s+prompt|bypass\s+safety|jailbreak)",
    re.I,
)

PII_ENTITY_TYPES = frozenset({
    "CREDIT_CARD",
    "EMAIL_ADDRESS",
    "PHONE_NUMBER",
    "US_SSN",
    "US_PASSPORT",
    "US_DRIVER_LICENSE",
    "IP_ADDRESS",
    "IBAN_CODE",
    "PERSON",
})


@lru_cache(maxsize=1)
def _analyzer():
    from presidio_analyzer import AnalyzerEngine

    return AnalyzerEngine()


def scan_text(value: str, *, languages: tuple[str, ...] = ("en",)) -> list[dict[str, Any]]:
    """Return Presidio hits (entity_type, score, start, end)."""
    text = (value or "").strip()
    if len(text) < 3:
        return []
    analyzer = _analyzer()
    hits: list[dict[str, Any]] = []
    for lang in languages:
        for r in analyzer.analyze(text=text, language=lang):
            if r.entity_type in PII_ENTITY_TYPES and r.score >= 0.35:
                hits.append({
                    "entity_type": r.entity_type,
                    "score": round(float(r.score), 3),
                    "start": r.start,
                    "end": r.end,
                })
    return hits


def scan_cell(value: str) -> tuple[bool, str | None]:
    """True if cell contains PII or prompt-injection."""
    text = str(value or "")
    if PROMPT_INJECTION.search(text):
        return True, "prompt-injection pattern in dataset text"
    hits = scan_text(text)
    if hits:
        kinds = ", ".join(sorted({h["entity_type"] for h in hits}))
        return True, f"Presidio PII detected: {kinds}"
    return False, None


@lru_cache(maxsize=1)
def _anonymizer():
    from presidio_anonymizer import AnonymizerEngine

    return AnonymizerEngine()


def redact_text(value: str) -> str:
    """DLP: anonymize PII in free text (audit logs)."""
    text = str(value or "")
    if len(text) < 3:
        return text
    try:
        from presidio_anonymizer.entities import OperatorConfig

        analyzer = _analyzer()
        anonymizer = _anonymizer()
        results = analyzer.analyze(text=text, language="en")
        if not results:
            return PROMPT_INJECTION.sub("<REDACTED>", text)
        op = OperatorConfig("replace", {"new_value": "<REDACTED>"})
        operators = {r.entity_type: op for r in results}
        return anonymizer.anonymize(
            text=text,
            analyzer_results=results,
            operators=operators,
        ).text
    except Exception:
        return PROMPT_INJECTION.sub("<REDACTED>", text)
