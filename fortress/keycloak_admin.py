"""Keycloak Admin API — регистрация пользователей с выбором роли."""

from __future__ import annotations

import os
import re
from typing import Any

import requests

KEYCLOAK_URL = os.getenv("KEYCLOAK_URL", "http://keycloak:8080").rstrip("/")
KEYCLOAK_REALM = os.getenv("KEYCLOAK_REALM", "mlsecops")
KEYCLOAK_CLIENT = os.getenv("KEYCLOAK_CLIENT_ID", "fortress-ui")
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


def _token_url() -> str:
    return f"{KEYCLOAK_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/token"


def display_names(username: str) -> tuple[str, str]:
    """Keycloak 24 требует firstName/lastName для password grant."""
    uname = username.strip().lower()
    display = uname.replace(".", " ").replace("_", " ").replace("-", " ")
    parts = [p for p in display.split() if p]
    first_name = parts[0].capitalize() if parts else uname.capitalize()
    last_name = parts[-1].capitalize() if len(parts) > 1 else "User"
    return first_name, last_name


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


def _validate_email(email: str) -> str | None:
    e = email.strip().lower()
    if not e or "@" not in e or "." not in e.split("@")[-1]:
        return "укажите корректный email"
    return None


def verify_password_grant(username: str, password: str) -> tuple[bool, str]:
    """Проверить, что пользователь может войти (password grant)."""
    try:
        r = requests.post(
            _token_url(),
            data={
                "grant_type": "password",
                "client_id": KEYCLOAK_CLIENT,
                "username": username.strip().lower(),
                "password": password,
            },
            timeout=10,
        )
        if r.status_code == 200 and r.json().get("access_token"):
            return True, ""
        desc = ""
        try:
            desc = r.json().get("error_description", "")
        except Exception:
            desc = r.text[:200]
        return False, desc or f"HTTP {r.status_code}"
    except requests.RequestException as exc:
        return False, str(exc)


def _find_user_id(base: str, token: str, username: str) -> str | None:
    sr = requests.get(
        f"{base}/users",
        headers=_headers(token),
        params={"username": username, "exact": "true"},
        timeout=15,
    )
    sr.raise_for_status()
    users = sr.json()
    return users[0]["id"] if users else None


def _finalize_user(
    base: str,
    token: str,
    user_id: str,
    *,
    username: str,
    email: str,
    first_name: str,
    last_name: str,
    role: str,
    password: str,
) -> None:
    """Профиль + пароль + сброс required actions (Keycloak 24)."""
    payload: dict[str, Any] = {
        "username": username,
        "email": email,
        "firstName": first_name,
        "lastName": last_name,
        "emailVerified": True,
        "enabled": True,
        "requiredActions": [],
        "attributes": {"self_selected_role": [role]},
    }
    r = requests.put(
        f"{base}/users/{user_id}",
        headers=_headers(token),
        json=payload,
        timeout=15,
    )
    r.raise_for_status()

    pw_r = requests.put(
        f"{base}/users/{user_id}/reset-password",
        headers=_headers(token),
        json={"type": "password", "value": password, "temporary": False},
        timeout=15,
    )
    pw_r.raise_for_status()


def _assign_role(base: str, token: str, user_id: str, role: str) -> None:
    role_r = requests.get(f"{base}/roles/{role}", headers=_headers(token), timeout=15)
    role_r.raise_for_status()
    map_r = requests.post(
        f"{base}/users/{user_id}/role-mappings/realm",
        headers=_headers(token),
        json=[role_r.json()],
        timeout=15,
    )
    map_r.raise_for_status()


def repair_incomplete_account(username: str, password: str) -> bool:
    """
    Починить аккаунты Keycloak 24 без firstName/lastName (ошибка «Account is not fully set up»).
    Вызывается при входе, если password верный, но профиль неполный.
    """
    uname = username.strip().lower()
    if not uname or not password:
        return False
    try:
        token = _admin_token()
    except requests.RequestException:
        return False

    base = f"{KEYCLOAK_URL}/admin/realms/{KEYCLOAK_REALM}"
    user_id = _find_user_id(base, token, uname)
    if not user_id:
        return False

    try:
        ur = requests.get(f"{base}/users/{user_id}", headers=_headers(token), timeout=15)
        ur.raise_for_status()
        data = ur.json()
        email = data.get("email") or f"{uname}@fortress.local"
        role = "ds"
        attrs = data.get("attributes") or {}
        if attrs.get("self_selected_role"):
            role = str(attrs["self_selected_role"][0])
        first_name, last_name = display_names(uname)
        if data.get("firstName"):
            first_name = data["firstName"]
        if data.get("lastName"):
            last_name = data["lastName"]
        if not data.get("firstName") or not data.get("lastName"):
            first_name, last_name = display_names(uname)

        _finalize_user(
            base, token, user_id,
            username=uname, email=email,
            first_name=first_name, last_name=last_name,
            role=role, password=password,
        )
        ok, _ = verify_password_grant(uname, password)
        return ok
    except requests.RequestException:
        return False


def register_user(
    username: str,
    email: str,
    password: str,
    role: str,
) -> tuple[bool, str]:
    """
    Создать пользователя в Keycloak, назначить роль и проверить вход.
    Регистрация считается успешной только если password grant работает.
    """
    role = role.strip().lower()
    if role not in ALLOWED_ROLES:
        return False, f"роль должна быть одна из: {', '.join(sorted(ALLOWED_ROLES))}"

    err = (
        _validate_username(username)
        or _validate_password(password)
        or _validate_email(email)
    )
    if err:
        return False, err

    uname = username.strip().lower()
    email_norm = email.strip().lower()
    first_name, last_name = display_names(uname)

    try:
        token = _admin_token()
    except requests.RequestException as exc:
        return False, f"Keycloak недоступен: {exc}"

    base = f"{KEYCLOAK_URL}/admin/realms/{KEYCLOAK_REALM}"
    user_payload: dict[str, Any] = {
        "username": uname,
        "email": email_norm,
        "firstName": first_name,
        "lastName": last_name,
        "emailVerified": True,
        "enabled": True,
        "requiredActions": [],
        "attributes": {"self_selected_role": [role]},
        "credentials": [
            {"type": "password", "value": password, "temporary": False},
        ],
    }

    try:
        r = requests.post(f"{base}/users", headers=_headers(token), json=user_payload, timeout=15)
        if r.status_code == 409:
            return False, "пользователь с таким логином уже существует — войдите или выберите другой логин"
        r.raise_for_status()

        user_id = r.headers.get("Location", "").rstrip("/").split("/")[-1]
        if not user_id:
            user_id = _find_user_id(base, token, uname)
        if not user_id:
            return False, "пользователь создан, но id не найден — обратитесь к администратору"

        _finalize_user(
            base, token, user_id,
            username=uname, email=email_norm,
            first_name=first_name, last_name=last_name,
            role=role, password=password,
        )
        _assign_role(base, token, user_id, role)

        ok, grant_err = verify_password_grant(uname, password)
        if not ok:
            # повторная финализация и вторая попытка
            _finalize_user(
                base, token, user_id,
                username=uname, email=email_norm,
                first_name=first_name, last_name=last_name,
                role=role, password=password,
            )
            ok, grant_err = verify_password_grant(uname, password)
        if not ok:
            return False, (
                f"аккаунт создан, но вход не работает: {grant_err}. "
                "Попробуйте другой логин или обратитесь к администратору."
            )

    except requests.HTTPError as exc:
        body = ""
        if exc.response is not None:
            body = exc.response.text[:300]
        return False, f"ошибка Keycloak: {exc} {body}"
    except requests.RequestException as exc:
        return False, f"сеть Keycloak: {exc}"

    return True, (
        f"Аккаунт «{uname}» создан и проверен. "
        "Войдите тем же логином в FORTRESS и MLflow."
    )


def keycloak_reachable() -> bool:
    try:
        r = requests.get(f"{KEYCLOAK_URL}/realms/{KEYCLOAK_REALM}", timeout=5)
        return r.status_code == 200
    except requests.RequestException:
        return False
