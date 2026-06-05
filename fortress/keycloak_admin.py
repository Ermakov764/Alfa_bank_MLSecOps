"""Keycloak Admin API — регистрация пользователей с выбором роли."""

from __future__ import annotations

import os
import re
from typing import Any

import requests

KEYCLOAK_URL = os.getenv("KEYCLOAK_URL", "http://keycloak:8080").rstrip("/")
KEYCLOAK_REALM = os.getenv("KEYCLOAK_REALM", "mlsecops")
ADMIN_USER = os.getenv("KEYCLOAK_ADMIN", "admin")
ADMIN_PASSWORD = os.getenv("KEYCLOAK_ADMIN_PASSWORD", "changeme")

ALLOWED_ROLES = frozenset({"ds", "mlsecops"})
ROLE_LABELS = {
    "ds": "Data Scientist — обучение моделей, deploy CI-моделей в prod",
    "mlsecops": "MLSecOps — одобрение внешних моделей, аудит, архив",
}


def _admin_token() -> str:
    url = f"{KEYCLOAK_URL}/realms/master/protocol/openid-connect/token"
    r = requests.post(
        url,
        data={
            "grant_type": "password",
            "client_id": "admin-cli",
            "username": ADMIN_USER,
            "password": ADMIN_PASSWORD,
        },
        timeout=15,
    )
    r.raise_for_status()
    return r.json()["access_token"]


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _validate_username(username: str) -> str | None:
    u = username.strip().lower()
    if len(u) < 3:
        return "логин минимум 3 символа"
    if not re.match(r"^[a-z0-9._-]+$", u):
        return "логин: только латиница, цифры, . _ -"
    return None


def _validate_password(password: str) -> str | None:
    if len(password) < 8:
        return "пароль минимум 8 символов"
    return None


def register_user(
    username: str,
    email: str,
    password: str,
    role: str,
) -> tuple[bool, str]:
    """
    Создать пользователя в Keycloak и назначить realm-роль.
    Возвращает (ok, message).
    """
    role = role.strip().lower()
    if role not in ALLOWED_ROLES:
        return False, f"роль должна быть одна из: {', '.join(sorted(ALLOWED_ROLES))}"

    err = _validate_username(username) or _validate_password(password)
    if err:
        return False, err

    email = email.strip()
    if not email or "@" not in email:
        return False, "укажите корректный email"

    try:
        token = _admin_token()
    except requests.RequestException as exc:
        return False, f"Keycloak недоступен: {exc}"

    base = f"{KEYCLOAK_URL}/admin/realms/{KEYCLOAK_REALM}"
    user_payload: dict[str, Any] = {
        "username": username.strip().lower(),
        "email": email,
        "emailVerified": True,
        "enabled": True,
        "attributes": {"self_selected_role": [role]},
    }

    try:
        r = requests.post(f"{base}/users", headers=_headers(token), json=user_payload, timeout=15)
        if r.status_code == 409:
            return False, "пользователь с таким логином уже существует"
        r.raise_for_status()
        user_id = r.headers.get("Location", "").rstrip("/").split("/")[-1]
        if not user_id:
            # fallback search
            sr = requests.get(
                f"{base}/users",
                headers=_headers(token),
                params={"username": user_payload["username"], "exact": "true"},
                timeout=15,
            )
            sr.raise_for_status()
            users = sr.json()
            if not users:
                return False, "пользователь создан, но id не найден"
            user_id = users[0]["id"]

        pw_r = requests.put(
            f"{base}/users/{user_id}/reset-password",
            headers=_headers(token),
            json={"type": "password", "value": password, "temporary": False},
            timeout=15,
        )
        pw_r.raise_for_status()

        role_r = requests.get(f"{base}/roles/{role}", headers=_headers(token), timeout=15)
        role_r.raise_for_status()
        role_repr = role_r.json()

        map_r = requests.post(
            f"{base}/users/{user_id}/role-mappings/realm",
            headers=_headers(token),
            json=[role_repr],
            timeout=15,
        )
        map_r.raise_for_status()
    except requests.HTTPError as exc:
        body = ""
        if exc.response is not None:
            body = exc.response.text[:200]
        return False, f"ошибка Keycloak: {exc} {body}"
    except requests.RequestException as exc:
        return False, f"сеть Keycloak: {exc}"

    return True, f"аккаунт {username} создан. Войдите тем же логином в FORTRESS и MLflow."


def keycloak_reachable() -> bool:
    try:
        r = requests.get(f"{KEYCLOAK_URL}/realms/{KEYCLOAK_REALM}", timeout=5)
        return r.status_code == 200
    except requests.RequestException:
        return False
