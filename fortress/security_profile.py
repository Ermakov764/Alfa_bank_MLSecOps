"""Security profile / G12 policy checks."""

from __future__ import annotations

import json
from typing import Any

from fortress.model_card import ModelCard, validate_card  # noqa: E402 — repo package
from fortress.registry_policy import requires_mlsecops_approval  # noqa: E402

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
    """
    G12 meta-gate (MLflow tags = source of truth).

    - CI-trained + signed attestation + all gates → DS may promote without MLSecOps.
    - External models (vendor / not in our pipeline) → only MLSecOps after HITL.
    """
    card_raw = tags.get("model_card")
    if not card_raw:
        return False, "missing model_card tag"
    try:
        card = validate_card(json.loads(card_raw))
    except Exception as e:
        return False, f"invalid model_card: {e}"

    missing = check_gate_tags(tags, required_gates_for_model(model_name))
    if missing:
        detail = tags.get("security.last_failure", "")
        msg = f"missing passed gates: {', '.join(missing)}"
        if detail:
            msg += f" — {detail}"
        return False, msg

    if tags.get("security.scan_status") != "passed":
        reason = tags.get("security.last_failure", "security.scan_status != passed")
        return False, reason

    if tags.get("security.signed") != "true":
        return False, "no valid attestation on this MLflow version (run pipeline first)"

    external = requires_mlsecops_approval(tags, model_name)
    if external:
        if actor_role != "mlsecops":
            return False, (
                "external model requires MLSecOps approval "
                "(register in MLflow with security.origin=external)"
            )
        if not tags.get("security.approved_by") and not approved_by:
            return False, "HITL required: MLSecOps must approve external model"
    elif actor_role not in ("ds", "mlsecops"):
        return False, f"role {actor_role} may not promote (only ds or mlsecops)"

    if card.tier == "HIGH" and external and not tags.get("security.approved_by") and not approved_by:
        return False, "HITL required for external HIGH-tier model"

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
