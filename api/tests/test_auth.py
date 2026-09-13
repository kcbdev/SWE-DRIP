"""Auth & RBAC contract tests (offline).

Signature verification is a pure function; the role matrix is exercised with a
dependency override so no database is required. The DB-backed session lookup is
covered only when ``DATABASE_URL`` is present (integration).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from api.app.auth import Actor, ROLE_ADMIN, ROLE_OPERATOR, ROLE_VIEWER, get_current_actor, verify_session_cookie
from api.app.rbac import require_role

SECRET = "test-secret-do-not-use-in-prod"


def sign(token: str, secret: str = SECRET) -> str:
    digest = hmac.new(secret.encode(), token.encode(), hashlib.sha256).digest()
    return f"{token}.{base64.urlsafe_b64encode(digest).decode().rstrip('=')}"


# --------------------------------------------------------------- signature


def test_valid_cookie_returns_raw_token() -> None:
    assert verify_session_cookie(sign("tok-123"), SECRET) == "tok-123"


def test_tampered_token_is_rejected() -> None:
    _, _, signature = sign("tok-123").rpartition(".")
    assert verify_session_cookie(f"tok-999.{signature}", SECRET) is None


def test_wrong_secret_is_rejected() -> None:
    assert verify_session_cookie(sign("tok-123", "other-secret"), SECRET) is None


@pytest.mark.parametrize("bad", ["", "no-dot", ".", "tok.", "tok.sig.extra.bad"])
def test_malformed_cookies_are_rejected(bad: str) -> None:
    assert verify_session_cookie(bad, SECRET) is None


# -------------------------------------------------------------- role matrix


def _admin_only_app() -> FastAPI:
    app = FastAPI()

    @app.get("/admin-only")
    def admin_only(actor: Actor = Depends(require_role(ROLE_ADMIN))) -> dict[str, str]:
        return {"role": actor.role}

    return app


@pytest.mark.parametrize(
    ("role", "expected"),
    [(ROLE_ADMIN, 200), (ROLE_OPERATOR, 403), (ROLE_VIEWER, 403)],
)
def test_admin_only_route_matrix(role: str, expected: int) -> None:
    app = _admin_only_app()
    app.dependency_overrides[get_current_actor] = lambda: Actor("u-1", "a@b.c", role)
    assert TestClient(app).get("/admin-only").status_code == expected


def test_missing_session_is_401_without_db() -> None:
    # No cookie -> rejected before any DB access.
    assert TestClient(_admin_only_app()).get("/admin-only").status_code == 401


def test_me_endpoint_returns_actor() -> None:
    from api.app.main import app as main_app

    main_app.dependency_overrides[get_current_actor] = lambda: Actor("u-9", "x@y.z", ROLE_OPERATOR)
    try:
        response = TestClient(main_app).get("/api/me")
    finally:
        main_app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json() == {"user_id": "u-9", "email": "x@y.z", "role": "operator"}


# ---------------------------------------------------- integration (DB-gated)


@pytest.mark.skipif(not os.environ.get("DATABASE_URL"), reason="requires DATABASE_URL")
def test_session_row_lookup_against_db() -> None:  # pragma: no cover - integration
    from api.app.auth import resolve_session_token

    # A token that cannot exist resolves to None; proves the query path runs.
    assert resolve_session_token("definitely-not-a-real-token") is None
