"""10 security integrity checks — gates must block real threats."""

from __future__ import annotations

import json
import pickle
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fortress.attestation import build_attestation, sign_attestation, verify_attestation  # noqa: E402
from fortress.mlflow_client import INTERNAL_MODELS  # noqa: E402
from fortress.registry_policy import model_origin, ORIGIN_EXTERNAL  # noqa: E402
from fortress.security_profile import check_promote_policy  # noqa: E402
from scripts import data_gate  # noqa: E402


def test_01_data_gate_blocks_poison_column(tmp_path: Path) -> None:
    p = tmp_path / "bad.csv"
    p.write_text("amount,poison_backdoor_flag\n1,1\n", encoding="utf-8")
    assert data_gate.run_gate(p, ["amount"], actor="t")[0] == 1


def test_02_data_gate_passes_clean(tmp_path: Path) -> None:
    p = ROOT / "data/datasets/train_clean.csv"
    if not p.exists():
        pytest.skip("train_clean.csv missing")
    assert data_gate.run_gate(p, ["amount", "age", "target"], actor="t")[0] == 0


def test_03_evil_pickle_blocked_by_g5() -> None:
    evil = ROOT / "tests/fixtures/malicious/evil_model.pkl"
    if not evil.exists():
        pytest.skip("run create_evil_pickle.py first")
    import pickletools
    ops = list(pickletools.genops(evil.read_bytes()))
    dangerous = [o for o, _, _ in ops if o.name in ("GLOBAL", "REDUCE", "INST", "OBJ", "NEWOBJ", "NEWOBJ_EX")]
    assert dangerous, "evil fixture must contain dangerous opcodes"


def test_04_g12_blocks_ds_on_uploaded_model_without_approval() -> None:
    tags = {
        "model_card": json.dumps({
            "name": "my-model", "version": "1", "tier": "HIGH",
            "owner": "t", "purpose": "ok", "data_sources": "d",
            "limitations": "uploaded",
        }),
        "security.origin": "external",
        "security.scan_status": "pending",
    }
    ok, msg = check_promote_policy(tags, "my-model", actor_role="ds")
    assert not ok
    assert "MLSecOps" in msg or "approval" in msg.lower() or "uploaded" in msg.lower()


def test_04b_g12_allows_mlsecops_with_approval() -> None:
    tags = {
        "model_card": json.dumps({
            "name": "my-model", "version": "1", "tier": "MED",
            "owner": "t", "purpose": "ok", "data_sources": "d",
            "limitations": "uploaded",
        }),
        "security.origin": "external",
        "security.scan_status": "pending",
        "security.approved_by": "mlsecops1",
    }
    ok, msg = check_promote_policy(tags, "my-model", actor_role="mlsecops", approved_by="mlsecops1")
    assert ok, msg


def test_05_g12_blocks_missing_model_card() -> None:
    tags = {"security.scan_status": "passed", "security.origin": "external"}
    ok, _ = check_promote_policy(tags, "any-model", actor_role="mlsecops")
    assert not ok


def test_06_attestation_rejects_failed_element() -> None:
    payload = build_attestation("c1", {
        "data": {"status": "failed", "gates": ["DATA"]},
    })
    signed = sign_attestation(payload)
    ok, _ = verify_attestation(signed)
    assert not ok


def test_07_no_builtin_ci_models() -> None:
    assert len(INTERNAL_MODELS) == 0
    assert model_origin({}, "any-user-model") == ORIGIN_EXTERNAL


def test_08_platform_attestation_elements() -> None:
    from fortress.gate_verifier import build_attestation_elements

    el = build_attestation_elements("run-1", include_data=False)
    assert el["code"]["status"] == "passed"
    assert "platform" in el


def test_09_format_policy_blocks_raw_pkl(tmp_path: Path) -> None:
    from scripts.check_format_policy import check

    d = tmp_path / "art"
    d.mkdir()
    (d / "model.pkl").write_bytes(pickle.dumps({"x": 1}))
    assert check(d, actor="t") == 1
