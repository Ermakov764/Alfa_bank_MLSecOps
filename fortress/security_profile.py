"""Security profile / G12 policy checks."""

from __future__ import annotations

import json
from typing import Any

from fortress.model_card import validate_card
from fortress.registry_policy import model_origin, ORIGIN_EXTERNAL, requires_mlsecops_approval

# Gates checked on uploaded model artifacts (at register / pre-deploy)
REQUIRED_UPLOAD = ["G5", "G6"]


def required_gates_for_model(model_name: str, tags: dict[str, str] | None = None) -> list[str]:
    tags = tags or {}
    if model_origin(tags, model_name) == ORIGIN_EXTERNAL:
        return list(REQUIRED_UPLOAD)
    return [
        "G0", "G1", "G2", "G3", "G3b", "G4", "G5", "G6", "G7",
        "G8", "G9", "G10", "G11", "G15",
    ]


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

    User-uploaded models (security.origin=external): model_card + scan + MLSecOps HITL.
    """
    card_raw = tags.get("model_card")
    if not card_raw:
        return False, "missing model_card tag"
    try:
        card = validate_card(json.loads(card_raw))
    except Exception as e:
        return False, f"invalid model_card: {e}"

    external = requires_mlsecops_approval(tags, model_name)

    if not external:
        missing = check_gate_tags(tags, required_gates_for_model(model_name, tags))
        if missing:
            detail = tags.get("security.last_failure", "")
            msg = f"missing passed gates: {', '.join(missing)}"
            if detail:
                msg += f" — {detail}"
            return False, msg
        if tags.get("security.signed") != "true":
            return False, "no valid attestation on this MLflow version (run pipeline first)"
    elif tags.get("security.scan_status") == "failed":
        return False, tags.get("security.last_failure", "security.scan_status failed")

    if tags.get("security.scan_status") not in ("passed", "pending") and not external:
        return False, tags.get("security.last_failure", "security.scan_status != passed")

    if external:
        if actor_role != "mlsecops":
            return False, (
                "uploaded model: deploy в Production только через MLSecOps "
                "(кнопка «Одобрить + Deploy»)"
            )
        if not tags.get("security.approved_by") and not approved_by:
            return False, "HITL required: MLSecOps must approve uploaded model"
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
