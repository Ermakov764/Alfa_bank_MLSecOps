"""Sigstore cosign signing (requires cosign binary)."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.skipif(shutil.which("cosign") is None, reason="cosign not installed")
def test_cosign_sign_and_verify_roundtrip(tmp_path: Path) -> None:
    artifact = tmp_path / "model.bin"
    artifact.write_bytes(b"test-model-payload")
    env = {**__import__("os").environ, "FORTRESS_KEY_DIR": str(tmp_path / "signing")}
    sign = subprocess.run(
        [__import__("sys").executable, "-c",
         "from pathlib import Path; from fortress.sigstore_sign import sign_blob, verify_blob; "
         f"p=Path('{artifact}'); sign_blob(p); ok,m=verify_blob(p); "
         "assert ok, m"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    assert sign.returncode == 0, sign.stderr + sign.stdout
