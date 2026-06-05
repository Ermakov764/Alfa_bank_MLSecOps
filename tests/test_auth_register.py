"""Registration validation (no live Keycloak required)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fortress.keycloak_admin import _validate_password, _validate_username  # noqa: E402


def test_username_rules() -> None:
    assert _validate_username("ab") is not None
    assert _validate_username("user_01") is None
    assert _validate_username("Bad!") is not None


def test_password_rules() -> None:
    assert _validate_password("short") is not None
    assert _validate_password("longenough") is None


def test_only_two_roles() -> None:
    from fortress.keycloak_admin import ALLOWED_ROLES

    assert ALLOWED_ROLES == frozenset({"ds", "mlsecops"})
