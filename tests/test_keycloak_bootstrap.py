"""Keycloak bootstrap (live if Keycloak up)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fortress.keycloak_admin import _admin_token, _headers, KEYCLOAK_REALM, KEYCLOAK_URL  # noqa: E402
from fortress.keycloak_bootstrap import ensure_keycloak_clients  # noqa: E402
from fortress.keycloak_admin import keycloak_reachable  # noqa: E402


def test_ensure_clients_idempotent() -> None:
    if not os.getenv("KEYCLOAK_URL"):
        os.environ["KEYCLOAK_URL"] = "http://localhost:8080"
    if not keycloak_reachable():
        pytest.skip("Keycloak not running")

    ok1, _ = ensure_keycloak_clients()
    ok2, _ = ensure_keycloak_clients()
    assert ok1 and ok2

    import requests

    token = _admin_token()
    r = requests.get(
        f"{KEYCLOAK_URL}/admin/realms/{KEYCLOAK_REALM}/clients",
        headers=_headers(token),
        params={"clientId": "mlflow-oauth"},
        timeout=10,
    )
    assert r.json(), "mlflow-oauth client must exist"
