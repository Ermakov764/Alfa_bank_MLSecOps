"""Asymmetric attestation signing (Ed25519) for CI pipeline elements."""

from __future__ import annotations

import base64
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_KEY_DIR = ROOT / "artifacts" / "signing"


def _key_paths(key_dir: Path | None = None) -> tuple[Path, Path]:
    d = key_dir or Path(os.getenv("FORTRESS_KEY_DIR", str(DEFAULT_KEY_DIR)))
    d.mkdir(parents=True, exist_ok=True)
    return d / "signing.key", d / "signing.pub"


def ensure_keypair(key_dir: Path | None = None) -> Path:
    """Create Ed25519 keypair if missing (dev/CI). Returns private key path."""
    priv_path, pub_path = _key_paths(key_dir)
    if priv_path.exists() and pub_path.exists():
        return priv_path
    private_key = Ed25519PrivateKey.generate()
    priv_path.write_bytes(
        private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    pub_path.write_bytes(
        private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )
    return priv_path


def _load_private(key_dir: Path | None = None) -> Ed25519PrivateKey:
    env_pem = os.getenv("FORTRESS_SIGNING_PRIVATE_KEY")
    if env_pem:
        raw = base64.b64decode(env_pem) if not env_pem.startswith("-----") else env_pem.encode()
        return serialization.load_pem_private_key(raw, password=None)
    priv_path, _ = _key_paths(key_dir)
    if not priv_path.exists():
        ensure_keypair(key_dir)
    return serialization.load_pem_private_key(priv_path.read_bytes(), password=None)


def _load_public(key_dir: Path | None = None) -> Ed25519PublicKey:
    env_pem = os.getenv("FORTRESS_SIGNING_PUBLIC_KEY")
    if env_pem:
        raw = base64.b64decode(env_pem) if not env_pem.startswith("-----") else env_pem.encode()
        return serialization.load_pem_public_key(raw)
    _, pub_path = _key_paths(key_dir)
    if not pub_path.exists():
        ensure_keypair(key_dir)
    return serialization.load_pem_public_key(pub_path.read_bytes())


def build_attestation(
    correlation_id: str,
    elements: dict[str, Any],
    *,
    model_name: str | None = None,
    commit: str | None = None,
) -> dict[str, Any]:
    return {
        "schema": "fortress-attestation-v1",
        "correlation_id": correlation_id,
        "model_name": model_name,
        "commit": commit or os.getenv("GITHUB_SHA", "local"),
        "elements": elements,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def sign_attestation(payload: dict[str, Any], key_dir: Path | None = None) -> dict[str, Any]:
    private_key = _load_private(key_dir)
    body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    sig = private_key.sign(body)
    return {
        "payload": payload,
        "signature": base64.b64encode(sig).decode(),
        "algorithm": "ed25519",
    }


def verify_attestation(signed: dict[str, Any], key_dir: Path | None = None) -> tuple[bool, str]:
    try:
        public_key = _load_public(key_dir)
        payload = signed["payload"]
        sig = base64.b64decode(signed["signature"])
        body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        public_key.verify(sig, body)
    except Exception as e:
        return False, f"signature invalid: {e}"

    elements = payload.get("elements", {})
    for name, data in elements.items():
        if data.get("status") != "passed":
            return False, f"element {name} not passed"
    return True, "ok"


def save_signed(path: Path, signed: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(signed, indent=2), encoding="utf-8")


def load_signed(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def gates_from_attestation(signed: dict[str, Any]) -> list[str]:
    """Flatten gate IDs that passed across all elements."""
    gates: list[str] = []
    for el in signed.get("payload", {}).get("elements", {}).values():
        for g in el.get("gates", []):
            if g not in gates:
                gates.append(g)
    return gates
