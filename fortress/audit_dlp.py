"""DLP layer for audit — redact PII before persistence."""

from __future__ import annotations

from typing import Any

from fortress.pii_scanner import redact_text

_SENSITIVE_KEYS = frozenset({
    "email", "password", "token", "secret", "prompt", "message", "text", "body",
})


def sanitize_details(details: dict[str, Any] | None) -> dict[str, Any]:
    if not details:
        return {}
    out: dict[str, Any] = {}
    for key, val in details.items():
        kl = key.lower()
        if isinstance(val, str):
            out[key] = redact_text(val) if (
                kl in _SENSITIVE_KEYS or "@" in val or len(val) > 40
            ) else val
        elif isinstance(val, dict):
            out[key] = sanitize_details(val)
        elif isinstance(val, list):
            out[key] = [
                redact_text(x) if isinstance(x, str) else x for x in val
            ]
        else:
            out[key] = val
    return out
