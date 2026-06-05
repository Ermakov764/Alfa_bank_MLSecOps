"""Model origin & promote policy: CI-trained vs external (MLflow tags as source of truth)."""

from __future__ import annotations

from typing import Any

# Models trained in our CI pipeline (demo registry; extend via MLflow tag security.origin)
CI_TRAINED_MODELS = frozenset({
    "credit-scoring-pd",
    "transaction-antifraud",
    "support-nlp",
})

ORIGIN_CI = "ci_trained"
ORIGIN_EXTERNAL = "external"

CI_MODEL_REGISTRY: list[dict[str, str]] = [
    {
        "key": "m1",
        "name": "credit-scoring-pd",
        "artifact": "models/m1_scoring/artifact",
        "card": "models/m1_scoring/model_card.yaml",
    },
    {
        "key": "m2",
        "name": "transaction-antifraud",
        "artifact": "artifacts/models/m2_antifraud",
        "card": "models/m2_antifraud/model_card.yaml",
    },
    {
        "key": "m3",
        "name": "support-nlp",
        "artifact": "models/m3_nlp/artifact",
        "card": "models/m3_nlp/model_card.yaml",
    },
]


def model_origin(tags: dict[str, str], model_name: str) -> str:
    origin = tags.get("security.origin", "").strip().lower()
    if origin in (ORIGIN_CI, ORIGIN_EXTERNAL):
        return origin
    if model_name in CI_TRAINED_MODELS:
        return ORIGIN_CI
    return ORIGIN_EXTERNAL


def requires_mlsecops_approval(tags: dict[str, str], model_name: str) -> bool:
    """External / vendor models (e.g. Opus) need MLSecOps HITL before Production."""
    return model_origin(tags, model_name) == ORIGIN_EXTERNAL


def approval_status(tags: dict[str, str], model_name: str, *, missing_gates: list[str]) -> str:
    """
    Human-readable status for UI / monitoring.
    ready_auto | needs_mlsecops | blocked | failed
    """
    if tags.get("security.scan_status") == "failed" or tags.get("security.last_failure"):
        return "failed"
    if missing_gates:
        return "blocked"
    if tags.get("security.signed") != "true":
        return "blocked"
    if requires_mlsecops_approval(tags, model_name):
        if tags.get("security.approved_by"):
            return "ready_auto"
        return "needs_mlsecops"
    return "ready_auto"


def approval_label(status: str) -> str:
    return {
        "ready_auto": "готова к prod (CI)",
        "needs_mlsecops": "нужно одобрение MLSecOps",
        "blocked": "не пройдены проверки",
        "failed": "уязвимость / атака",
    }.get(status, status)


def ci_registry_entry(model_name: str) -> dict[str, str] | None:
    for row in CI_MODEL_REGISTRY:
        if row["name"] == model_name:
            return row
    return None
