"""Registration validation and Keycloak integration (if available)."""

from __future__ import annotations

import sys
import uuid
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fortress.keycloak_admin import (  # noqa: E402
    ALLOWED_ROLES,
    _validate_email,
    _validate_password,
    _validate_username,
    display_names,
    keycloak_reachable,
    register_user,
    repair_incomplete_account,
    verify_password_grant,
)
from fortress.auth import register_and_login  # noqa: E402


def test_username_rules() -> None:
    assert _validate_username("ab") is not None
    assert _validate_username("user_01") is None
    assert _validate_username("Bad!") is not None
    assert _validate_username("Rina") is None  # нормализуется в rina


def test_password_rules() -> None:
    assert _validate_password("short") is not None
    assert _validate_password("longenough") is None


def test_email_rules() -> None:
    assert _validate_email("bad") is not None
    assert _validate_email("user@mail.com") is None


def test_display_names_keycloak24() -> None:
    first, last = display_names("rina")
    assert first == "Rina"
    assert last == "User"
    f2, l2 = display_names("anna.petrova")
    assert f2 == "Anna"
    assert l2 == "Petrova"


def test_only_two_roles() -> None:
    assert ALLOWED_ROLES == frozenset({"ds", "mlsecops"})


def test_register_and_login_e2e() -> None:
    """Полный цикл: регистрация → password grant (если Keycloak доступен)."""
    import os

    if not os.getenv("KEYCLOAK_URL"):
        os.environ["KEYCLOAK_URL"] = "http://localhost:8080"
    if not keycloak_reachable():
        pytest.skip("Keycloak not running on localhost:8080")

    uname = f"test_{uuid.uuid4().hex[:8]}"
    password = "testpass123"
    ok, msg = register_user(uname, f"{uname}@test.local", password, "ds")
    assert ok, msg

    grant_ok, grant_err = verify_password_grant(uname, password)
    assert grant_ok, grant_err

    user, msg = register_and_login(
        f"dup_{uuid.uuid4().hex[:6]}",
        "dup@test.local",
        password,
        "ds",
    )
    assert user is not None, msg
    assert user.role == "ds"


def test_repair_incomplete_account() -> None:
    import os

    if not os.getenv("KEYCLOAK_URL"):
        os.environ["KEYCLOAK_URL"] = "http://localhost:8080"
    if not keycloak_reachable():
        pytest.skip("Keycloak not running")

    uname = f"broken_{uuid.uuid4().hex[:8]}"
    password = "brokenpass99"
    ok, _ = register_user(uname, f"{uname}@test.local", password, "ds")
    assert ok

    from fortress.keycloak_admin import _admin_token, _headers, KEYCLOAK_REALM, KEYCLOAK_URL, _find_user_id
    import requests

    token = _admin_token()
    base = f"{KEYCLOAK_URL}/admin/realms/{KEYCLOAK_REALM}"
    uid = _find_user_id(base, token, uname)
    requests.put(
        f"{base}/users/{uid}",
        headers=_headers(token),
        json={"firstName": "", "lastName": ""},
        timeout=15,
    ).raise_for_status()

    grant_ok, _ = verify_password_grant(uname, password)
    assert not grant_ok

    assert repair_incomplete_account(uname, password)
    grant_ok2, err2 = verify_password_grant(uname, password)
    assert grant_ok2, err2
