"""Tests for G12 promote policy (no MLflow network)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fortress.security_profile import check_promote_policy  # noqa: E402


def _base_tags(*, origin: str = "ci_trained", approved: bool = False) -> dict[str, str]:
    tags = {
        "model_card": (
            '{"name":"m","version":"1","tier":"HIGH","owner":"u",'
            '"purpose":"production model","data_sources":"internal","limitations":"none"}'
        ),
        "security.origin": origin,
        "security.scan_status": "passed",
        "security.signed": "true",
        "security.G0": "passed",
        "security.G1": "passed",
        "security.G2": "passed",
        "security.G4": "passed",
        "security.G3": "passed",
        "security.G3b": "passed",
        "security.G5": "passed",
        "security.G6": "passed",
        "security.G7": "passed",
        "security.G8": "passed",
        "security.G9": "passed",
        "security.G11": "passed",
        "security.G15": "passed",
    }
    if approved:
        tags["security.approved_by"] = "mlsecops-user"
    return tags


def test_ds_can_promote_ci_trained_legacy() -> None:
    ok, msg = check_promote_policy(_base_tags(), "legacy-ci-model", actor_role="ds")
    assert ok, msg


def test_ds_blocked_on_external() -> None:
    ok, msg = check_promote_policy(
        _base_tags(origin="external", approved=True),
        "vendor-opus",
        actor_role="ds",
    )
    assert not ok
    assert "external" in msg.lower() or "mlsecops" in msg.lower()


def test_mlsecops_needs_approval_external() -> None:
    ok, msg = check_promote_policy(
        _base_tags(origin="external"),
        "vendor-opus",
        actor_role="mlsecops",
    )
    assert not ok
    assert "hitl" in msg.lower() or "approve" in msg.lower()
