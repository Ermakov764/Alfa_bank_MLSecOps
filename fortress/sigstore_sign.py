"""Cosign Sigstore blob signing for model artifacts (G7 when SIGNING_STRICT=true)."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KEY_DIR = Path(os.getenv("FORTRESS_KEY_DIR", str(ROOT / "artifacts" / "signing")))


def ensure_cosign_keypair() -> tuple[Path, Path]:
    KEY_DIR.mkdir(parents=True, exist_ok=True)
    priv = KEY_DIR / "cosign.key"
    pub = KEY_DIR / "cosign.pub"
    if priv.exists() and pub.exists():
        return priv, pub
    env = {**os.environ, "COSIGN_PASSWORD": os.getenv("COSIGN_PASSWORD", "")}
    subprocess.run(
        ["cosign", "generate-key-pair"],
        cwd=KEY_DIR,
        env=env,
        input=b"\n",
        check=True,
        timeout=60,
    )
    return priv, pub


def sign_blob(artifact: Path) -> Path:
    """Sign artifact with cosign; returns bundle path."""
    if not artifact.is_file():
        raise FileNotFoundError(artifact)
    priv, _ = ensure_cosign_keypair()
    bundle = artifact.with_suffix(artifact.suffix + ".cosign.bundle")
    env = {**os.environ, "COSIGN_PASSWORD": os.getenv("COSIGN_PASSWORD", "")}
    subprocess.run(
        [
            "cosign", "sign-blob",
            "--key", str(priv),
            "--bundle", str(bundle),
            str(artifact),
        ],
        check=True,
        capture_output=True,
        timeout=120,
        env=env,
    )
    return bundle


def verify_blob(artifact: Path) -> tuple[bool, str]:
    pub = KEY_DIR / "cosign.pub"
    bundle = artifact.with_suffix(artifact.suffix + ".cosign.bundle")
    if not pub.exists() or not bundle.exists():
        return False, "cosign bundle or public key missing"
    env = {**os.environ, "COSIGN_PASSWORD": os.getenv("COSIGN_PASSWORD", "")}
    try:
        subprocess.run(
            [
                "cosign", "verify-blob",
                "--key", str(pub),
                "--bundle", str(bundle),
                str(artifact),
            ],
            check=True,
            capture_output=True,
            timeout=60,
            env=env,
        )
        return True, "ok"
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        return False, str(exc)
