"""Attestation sign/verify tests."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fortress.attestation import (  # noqa: E402
    build_attestation,
    ensure_keypair,
    sign_attestation,
    verify_attestation,
)


def test_sign_and_verify(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FORTRESS_KEY_DIR", str(tmp_path / "keys"))
    ensure_keypair(tmp_path / "keys")
    payload = build_attestation(
        "test-corr",
        {
            "data": {"status": "passed", "gates": ["DATA"]},
            "code": {"status": "passed", "gates": ["G0"]},
        },
    )
    signed = sign_attestation(payload, tmp_path / "keys")
    ok, msg = verify_attestation(signed, tmp_path / "keys")
    assert ok, msg


def test_verify_fails_on_bad_element(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FORTRESS_KEY_DIR", str(tmp_path / "keys"))
    ensure_keypair(tmp_path / "keys")
    payload = build_attestation("x", {"data": {"status": "failed", "gates": []}})
    signed = sign_attestation(payload, tmp_path / "keys")
    ok, _ = verify_attestation(signed, tmp_path / "keys")
    assert not ok
