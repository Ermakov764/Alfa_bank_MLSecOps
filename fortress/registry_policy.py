"""Model origin & promote policy: uploaded models via MLflow (source of truth)."""

from __future__ import annotations

from typing import Any

ORIGIN_CI = "ci_trained"
ORIGIN_EXTERNAL = "external"

# Legacy alias — no built-in CI models; extend via MLflow tag security.origin=ci_trained if needed.
CI_TRAINED_MODELS = frozenset()


def model_origin(tags: dict[str, str], model_name: str) -> str:
    origin = tags.get("security.origin", "").strip().lower()
    if origin in (ORIGIN_CI, ORIGIN_EXTERNAL):
        return origin
    if model_name in CI_TRAINED_MODELS:
        return ORIGIN_CI
    return ORIGIN_EXTERNAL


def requires_mlsecops_approval(tags: dict[str, str], model_name: str) -> bool:
    """Uploaded / vendor models need MLSecOps HITL before Production."""
    return model_origin(tags, model_name) == ORIGIN_EXTERNAL


def approval_status(tags: dict[str, str], model_name: str, *, missing_gates: list[str]) -> str:
    if tags.get("security.scan_status") == "failed" or tags.get("security.last_failure"):
        return "failed"
    if missing_gates:
        return "blocked"
    if requires_mlsecops_approval(tags, model_name):
        if tags.get("security.approved_by"):
            return "ready_auto"
        return "needs_mlsecops"
    if tags.get("security.signed") != "true":
        return "blocked"
    return "ready_auto"


def approval_label(status: str) -> str:
    return {
        "ready_auto": "готова к prod",
        "needs_mlsecops": "нужно одобрение MLSecOps",
        "blocked": "не пройдены проверки",
        "failed": "уязвимость / атака",
    }.get(status, status)
