"""Security profile / G12 policy checks."""

from __future__ import annotations

import json
from typing import Any

from fortress.model_card import ModelCard, validate_card  # noqa: E402 — repo package

# Required gates by model type
REQUIRED_CI = ["G0", "G1", "G3", "G3b"]
REQUIRED_REGISTER = ["G5", "G6", "G7"]
REQUIRED_M1_M2_VALIDATE = ["G8", "G9"]
REQUIRED_M3_VALIDATE = ["G10"]
REQUIRED_DEPLOY = ["G11"]


def required_gates_for_model(model_name: str) -> list[str]:
    base = REQUIRED_CI + REQUIRED_REGISTER + REQUIRED_DEPLOY
    if "nlp" in model_name or "support" in model_name:
        return base + REQUIRED_M3_VALIDATE
    return base + REQUIRED_M1_M2_VALIDATE


def check_gate_tags(tags: dict[str, str], gates: list[str]) -> list[str]:
    missing = []
    for g in gates:
        key = f"security.{g}"
        if tags.get(key) != "passed":
            missing.append(g)
    return missing


def check_promote_policy(
    tags: dict[str, str],
    model_name: str,
    *,
    actor_role: str,
    approved_by: str | None = None,
) -> tuple[bool, str]:
    """G12 meta-gate: all required tags + HITL for HIGH tier."""
    if actor_role != "mlsecops":
        return False, "only mlsecops role may promote to Production"

    card_raw = tags.get("model_card")
    if not card_raw:
        return False, "missing model_card tag"
    try:
        card = validate_card(json.loads(card_raw))
    except Exception as e:
        return False, f"invalid model_card: {e}"

    missing = check_gate_tags(tags, required_gates_for_model(model_name))
    if missing:
        return False, f"missing passed gates: {', '.join(missing)}"

    if tags.get("security.scan_status") != "passed":
        return False, "security.scan_status != passed"

    if card.tier == "HIGH":
        if not tags.get("security.approved_by") and not approved_by:
            return False, "HITL required: security.approved_by for tier HIGH"

    return True, "ok"


def build_profile_summary(tags: dict[str, str]) -> dict[str, Any]:
    gates = {}
    for k, v in tags.items():
        if k.startswith("security.") and k != "security.scan_status":
            gates[k.replace("security.", "")] = v
    return {
        "scan_status": tags.get("security.scan_status", "unknown"),
        "signed": tags.get("security.signed", "false"),
        "gates": gates,
    }
