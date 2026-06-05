"""Auth: Keycloak OIDC + регистрация через Admin API."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import requests

KEYCLOAK_URL = os.getenv("KEYCLOAK_URL", "http://keycloak:8080").rstrip("/")
KEYCLOAK_REALM = os.getenv("KEYCLOAK_REALM", "mlsecops")
KEYCLOAK_CLIENT = os.getenv("KEYCLOAK_CLIENT_ID", "fortress-ui")
KEYCLOAK_PUBLIC_URL = os.getenv("KEYCLOAK_PUBLIC_URL", "http://localhost:8080").rstrip("/")


@dataclass
class SessionUser:
    username: str
    role: str
    email: str = ""
    token: str | None = None

    @property
    def can_deploy(self) -> bool:
        return self.role in ("ds", "mlsecops")

    @property
    def can_approve_external(self) -> bool:
        return self.role == "mlsecops"

    @property
    def can_train(self) -> bool:
        return self.role in ("ds", "mlsecops")


def _token_url() -> str:
    return f"{KEYCLOAK_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/token"


def _keycloak_token(username: str, password: str) -> dict[str, Any] | None:
    try:
        r = requests.post(
            _token_url(),
            data={
                "grant_type": "password",
                "client_id": KEYCLOAK_CLIENT,
                "username": username,
                "password": password,
            },
            timeout=10,
        )
        if r.status_code != 200:
            return None
        return r.json()
    except requests.RequestException:
        return None


def _decode_jwt_payload(access_token: str) -> dict[str, Any]:
    import base64
    import json

    payload_b64 = access_token.split(".")[1]
    payload_b64 += "=" * (-len(payload_b64) % 4)
    return json.loads(base64.urlsafe_b64decode(payload_b64))


def _role_from_token(payload: dict[str, Any]) -> str:
    realm_roles: list[str] = []
    ra = payload.get("realm_access") or {}
    if isinstance(ra, dict):
        realm_roles.extend(ra.get("roles") or [])
    for priority in ("mlsecops", "ds"):
        if priority in realm_roles:
            return priority
    attrs = payload.get("self_selected_role") or payload.get("attributes", {}).get("self_selected_role")
    if isinstance(attrs, list) and attrs:
        return str(attrs[0])
    return "ds"


def authenticate(username: str, password: str) -> SessionUser | None:
    username = username.strip().lower()
    if not username or not password:
        return None

    tok = _keycloak_token(username, password)
    if not tok or not tok.get("access_token"):
        return None

    try:
        payload = _decode_jwt_payload(tok["access_token"])
        role = _role_from_token(payload)
        email = payload.get("email", "")
    except Exception:
        role = "ds"
        email = ""

    return SessionUser(
        username=username,
        role=role,
        email=email,
        token=tok["access_token"],
    )


def register(username: str, email: str, password: str, role: str) -> tuple[bool, str]:
    from fortress.keycloak_admin import register_user

    return register_user(username, email, password, role)


def mlflow_public_url() -> str:
    return os.getenv("MLFLOW_PUBLIC_URI", "http://localhost:5000")


def keycloak_account_url() -> str:
    return f"{KEYCLOAK_PUBLIC_URL}/realms/{KEYCLOAK_REALM}/account"
