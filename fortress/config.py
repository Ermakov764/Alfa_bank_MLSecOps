"""Публичные URL и пути runtime (env-driven)."""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def public_url(env_key: str, default: str) -> str:
    return os.getenv(env_key, default).rstrip("/")


def mlflow_public_url() -> str:
    return public_url("MLFLOW_PUBLIC_URI", "http://localhost:5000")


def keycloak_public_url() -> str:
    return public_url("KEYCLOAK_PUBLIC_URL", "http://localhost:8080")


def m1_api_url() -> str:
    return public_url("M1_API_URL", "http://localhost:8001")


def m2_api_url() -> str:
    return public_url("M2_API_URL", "http://localhost:8002")


def m3_api_url() -> str:
    return public_url("M3_API_URL", "http://localhost:4000")


def artifacts_dir() -> Path:
    return Path(os.getenv("ARTIFACTS_DIR", str(ROOT / "artifacts")))


def attestation_path() -> Path:
    return Path(os.getenv(
        "FORTRESS_ATTESTATION_PATH",
        str(artifacts_dir() / "attestation" / "fortress-attestation.signed.json"),
    ))


def strict_audit() -> bool:
    return os.getenv("FORTRESS_STRICT_AUDIT", "true").lower() in ("1", "true", "yes")
