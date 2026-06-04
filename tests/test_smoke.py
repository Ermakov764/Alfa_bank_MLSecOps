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


def test_g12_blocks_ds() -> None:
    tags = {
        "model_card": '{"name":"m","version":"1","tier":"HIGH","owner":"t","purpose":"ok","data_sources":"d"}',
        "security.scan_status": "passed",
        "security.G0": "passed",
        "security.G3": "passed",
        "security.G5": "passed",
        "security.G6": "passed",
        "security.G7": "passed",
        "security.G8": "passed",
        "security.G9": "passed",
        "security.approved_by": "mlsecops1",
    }
    ok, msg = check_promote_policy(tags, "credit-scoring-pd", actor_role="ds")
    assert not ok
    assert "mlsecops" in msg


def test_data_gate_poison(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    csv = tmp_path / "bad.csv"
    csv.write_text("a,poison_col\n1,1\n")
    sys.path.insert(0, str(ROOT))
    from scripts import data_gate  # noqa: E402

    monkeypatch.setattr(data_gate, "log_finding", lambda *a, **k: None)
    monkeypatch.setattr(data_gate, "log_event", lambda *a, **k: None)
    assert data_gate.run_gate(csv, ["a"], actor="test") == 1
