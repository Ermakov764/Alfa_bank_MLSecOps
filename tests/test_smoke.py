"""Smoke tests without full stack."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fortress.model_card import ModelCard, validate_card  # noqa: E402
from fortress.security_profile import check_promote_policy  # noqa: E402


def test_model_card_rejects_todo() -> None:
    with pytest.raises(Exception):
        validate_card({
            "name": "x",
            "version": "1",
            "owner": "team",
            "purpose": "TODO",
        })


def test_model_card_valid() -> None:
    card = ModelCard(
        name="credit-scoring-pd",
        version="1.0",
        owner="team",
        purpose="scoring",
    )
    assert card.tier == "HIGH"


def _full_gate_tags() -> dict[str, str]:
    return {
        "model_card": (
            '{"name":"vendor-model","version":"1","tier":"HIGH","owner":"t",'
            '"purpose":"external vendor model","data_sources":"vendor","limitations":"none"}'
        ),
        "security.origin": "external",
        "security.scan_status": "passed",
        "security.G0": "passed",
        "security.G1": "passed",
        "security.G3": "passed",
        "security.G3b": "passed",
        "security.G5": "passed",
        "security.G6": "passed",
        "security.G7": "passed",
        "security.G8": "passed",
        "security.G9": "passed",
        "security.G11": "passed",
        "security.signed": "true",
        "security.approved_by": "mlsecops1",
    }


def test_g12_blocks_ds_on_external() -> None:
    tags = _full_gate_tags()
    ok, msg = check_promote_policy(tags, "vendor-opus", actor_role="ds")
    assert not ok
    assert "mlsecops" in msg.lower() or "external" in msg.lower()


def test_g12_allows_ds_on_ci_trained() -> None:
    tags = _full_gate_tags()
    tags["security.origin"] = "ci_trained"
    tags["model_card"] = (
        '{"name":"credit-scoring-pd","version":"1","tier":"HIGH","owner":"t",'
        '"purpose":"ci trained scoring","data_sources":"internal","limitations":"none"}'
    )
    ok, msg = check_promote_policy(tags, "credit-scoring-pd", actor_role="ds")
    assert ok, msg


def test_data_gate_poison(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    csv = tmp_path / "bad.csv"
    csv.write_text("a,poison_col\n1,1\n")
    from fortress import data_gate  # noqa: E402

    monkeypatch.setattr(data_gate, "log_finding", lambda *a, **k: None)
    monkeypatch.setattr(data_gate, "log_event", lambda *a, **k: None)
    assert data_gate.run_gate(csv, ["a"], actor="test")[0] == 1
