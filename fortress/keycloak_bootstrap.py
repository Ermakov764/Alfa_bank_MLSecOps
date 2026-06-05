"""Идемпотентная настройка Keycloak: клиенты MLflow/FORTRESS и маппер ролей."""

from __future__ import annotations

import os
from typing import Any

import requests

from fortress.keycloak_admin import (
    KEYCLOAK_REALM,
    KEYCLOAK_URL,
    _admin_token,
    _headers,
    keycloak_reachable,
)

MLFLOW_CLIENT_ID = "mlflow-oauth"
FORTRESS_CLIENT_ID = "fortress-ui"
MLFLOW_SECRET = os.getenv("MLFLOW_OAUTH_SECRET", "mlflow-oauth-dev-secret")
DASHBOARD_PORT = os.getenv("DASHBOARD_PORT", "8502")


def _client_by_id(base: str, token: str, client_id: str) -> dict[str, Any] | None:
    r = requests.get(
        f"{base}/clients",
        headers=_headers(token),
        params={"clientId": client_id},
        timeout=15,
    )
    r.raise_for_status()
    items = r.json()
    return items[0] if items else None


def _upsert_client(base: str, token: str, payload: dict[str, Any]) -> str:
    client_id = payload["clientId"]
    existing = _client_by_id(base, token, client_id)
    body = {k: v for k, v in payload.items() if k != "secret"}
    if existing:
        internal_id = existing["id"]
        r = requests.put(
            f"{base}/clients/{internal_id}",
            headers=_headers(token),
            json=body,
            timeout=15,
        )
        r.raise_for_status()
    else:
        create_body = dict(body)
        if payload.get("secret") and not payload.get("publicClient"):
            create_body["secret"] = payload["secret"]
        r = requests.post(f"{base}/clients", headers=_headers(token), json=create_body, timeout=15)
        r.raise_for_status()
        created = _client_by_id(base, token, client_id)
        if not created:
            raise RuntimeError(f"client {client_id} not found after create")
        internal_id = created["id"]

    if not payload.get("publicClient") and payload.get("secret"):
        sr = requests.get(
            f"{base}/clients/{internal_id}/client-secret",
            headers=_headers(token),
            timeout=15,
        )
        if sr.status_code == 200 and sr.json().get("value") != payload["secret"]:
            requests.post(
                f"{base}/clients/{internal_id}/client-secret",
                headers=_headers(token),
                timeout=15,
            ).raise_for_status()

    return internal_id


def _scope_by_name(base: str, token: str, name: str) -> dict[str, Any] | None:
    r = requests.get(
        f"{base}/client-scopes",
        headers=_headers(token),
        params={"search": name},
        timeout=15,
    )
    r.raise_for_status()
    for item in r.json():
        if item.get("name") == name:
            return item
    return None


def _ensure_groups_client_scope(base: str, token: str) -> str:
    """
    Client scope `groups` — oauth2-proxy запрашивает scope groups;
    без него Keycloak отвечает invalid_scope.
    """
    existing = _scope_by_name(base, token, "groups")
    if existing:
        scope_id = existing["id"]
    else:
        r = requests.post(
            f"{base}/client-scopes",
            headers=_headers(token),
            json={
                "name": "groups",
                "protocol": "openid-connect",
                "attributes": {"include.in.token.scope": "true"},
            },
            timeout=15,
        )
        r.raise_for_status()
        created = _scope_by_name(base, token, "groups")
        if not created:
            raise RuntimeError("groups client scope not found after create")
        scope_id = created["id"]

    mr = requests.get(
        f"{base}/client-scopes/{scope_id}/protocol-mappers/models",
        headers=_headers(token),
        timeout=15,
    )
    mr.raise_for_status()
    if not any(m.get("name") == "realm-roles-groups" for m in mr.json()):
        requests.post(
            f"{base}/client-scopes/{scope_id}/protocol-mappers/models",
            headers=_headers(token),
            json={
                "name": "realm-roles-groups",
                "protocol": "openid-connect",
                "protocolMapper": "oidc-usermodel-realm-role-mapper",
                "consentRequired": False,
                "config": {
                    "multivalued": "true",
                    "userinfo.token.claim": "true",
                    "id.token.claim": "true",
                    "access.token.claim": "true",
                    "claim.name": "groups",
                    "jsonType.label": "String",
                },
            },
            timeout=15,
        ).raise_for_status()

    return scope_id


def _attach_default_scope(base: str, token: str, client_internal_id: str, scope_id: str) -> None:
    dr = requests.get(
        f"{base}/clients/{client_internal_id}/default-client-scopes",
        headers=_headers(token),
        timeout=15,
    )
    dr.raise_for_status()
    if any(s.get("id") == scope_id for s in dr.json()):
        return
    requests.put(
        f"{base}/clients/{client_internal_id}/default-client-scopes/{scope_id}",
        headers=_headers(token),
        timeout=15,
    ).raise_for_status()


def ensure_keycloak_clients(*, retries: int = 12, delay_sec: float = 5.0) -> tuple[bool, str]:
    """
    Создать/обновить клиенты fortress-ui и mlflow-oauth.
    Нужно, если realm уже существовал до импорта realm-export.json.
    """
    import time

    for attempt in range(retries):
        if keycloak_reachable():
            break
        if attempt < retries - 1:
            time.sleep(delay_sec)
    else:
        return False, "Keycloak недоступен"

    try:
        token = _admin_token()
    except requests.RequestException as exc:
        return False, f"Keycloak admin: {exc}"

    base = f"{KEYCLOAK_URL}/admin/realms/{KEYCLOAK_REALM}"
    mlflow_redirect = [
        "http://localhost:5000/oauth2/callback",
        "http://localhost:5000/*",
    ]
    fortress_redirect = [
        f"http://localhost:{DASHBOARD_PORT}/*",
        "http://localhost:5000/*",
    ]

    try:
        _upsert_client(base, token, {
            "clientId": FORTRESS_CLIENT_ID,
            "name": "FORTRESS Security Center",
            "enabled": True,
            "publicClient": True,
            "directAccessGrantsEnabled": True,
            "standardFlowEnabled": True,
            "redirectUris": fortress_redirect,
            "webOrigins": ["+"],
            "protocol": "openid-connect",
        })

        mlflow_internal = _upsert_client(base, token, {
            "clientId": MLFLOW_CLIENT_ID,
            "name": "MLflow UI",
            "enabled": True,
            "publicClient": False,
            "secret": MLFLOW_SECRET,
            "directAccessGrantsEnabled": False,
            "standardFlowEnabled": True,
            "redirectUris": mlflow_redirect,
            "webOrigins": ["http://localhost:5000", "+"],
            "protocol": "openid-connect",
            "fullScopeAllowed": True,
        })
        groups_scope_id = _ensure_groups_client_scope(base, token)
        _attach_default_scope(base, token, mlflow_internal, groups_scope_id)
    except requests.RequestException as exc:
        return False, f"ошибка настройки клиентов: {exc}"

    return True, "Keycloak clients OK (fortress-ui, mlflow-oauth)"
