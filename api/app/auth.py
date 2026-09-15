"""Better Auth session validation for FastAPI.

Single auth runtime (spec C1): Better Auth issues credentials and sessions in
the shared Postgres; FastAPI never issues credentials. For every request we:
  1. read the ``better-auth.session_token`` cookie (``<token>.<signature>``),
  2. verify the HMAC-SHA256 signature against ``BETTER_AUTH_SECRET``,
  3. look the raw token up in the ``session`` table, join ``user`` for the role.

The signature check is a pure function so it is unit-testable offline; the
session lookup is the only DB-touching step.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import unquote

from fastapi import HTTPException, Request, status
from sqlalchemy import text

from .config import settings
from .db import get_engine

SESSION_COOKIE = "better-auth.session_token"
# Better Auth prefixes cookie names with `__Secure-` when its baseURL is
# https (production) but not on http (local dev). Accept both so the same
# build validates sessions in every environment.
SECURE_SESSION_COOKIE = f"__Secure-{SESSION_COOKIE}"

# Roles are exact strings everywhere (DB, API, UI) — see spec C2.
ROLE_ADMIN = "admin"
ROLE_OPERATOR = "operator"
ROLE_VIEWER = "viewer"
ROLES = (ROLE_ADMIN, ROLE_OPERATOR, ROLE_VIEWER)


@dataclass(frozen=True)
class Actor:
    """The authenticated caller resolved from a Better Auth session."""

    user_id: str
    email: str
    role: str


def _b64decode(segment: str) -> bytes:
    pad = "=" * (-len(segment) % 4)
    return base64.urlsafe_b64decode(segment + pad)


def verify_session_cookie(cookie_value: Optional[str], secret: str) -> Optional[str]:
    """Return the raw session token iff ``cookie_value`` is a valid signed value.

    Format (Better Auth): ``<token>.<base64url HMAC-SHA256(secret, token)>``.
    The cookie value arrives percent-encoded on the wire (``=`` -> ``%3D``
    etc.), so it is unquoted before splitting. Returns ``None`` for any
    malformed, tampered, or wrongly-signed input.
    """
    if not cookie_value or not secret:
        return None
    value = unquote(cookie_value)
    if "." not in value:
        return None
    token, _, signature = value.rpartition(".")
    if not token or not signature:
        return None
    expected = hmac.new(secret.encode("utf-8"), token.encode("utf-8"), hashlib.sha256).digest()
    try:
        provided = _b64decode(signature)
    except (binascii.Error, ValueError):
        return None
    if hmac.compare_digest(expected, provided):
        return token
    return None


def resolve_session_token(token: str) -> Optional[Actor]:
    """Look the raw token up in ``session`` (joined to ``user``); None if absent/expired."""
    engine = get_engine()
    with engine.connect() as conn:
        row = conn.execute(
            text(
                'SELECT s."userId" AS user_id, s."expiresAt" AS expires_at, '
                "u.email AS email, u.role AS role "
                'FROM "session" s JOIN "user" u ON u.id = s."userId" '
                "WHERE s.token = :token"
            ),
            {"token": token},
        ).mappings().first()
    if row is None:
        return None
    expires_at = row["expires_at"]
    if expires_at is not None and expires_at <= datetime.now(timezone.utc):
        return None
    role = row["role"] or ROLE_VIEWER
    return Actor(user_id=str(row["user_id"]), email=row["email"], role=role)


def get_current_actor(request: Request) -> Actor:
    """FastAPI dependency: resolve the caller or raise 401."""
    raw_cookie = request.cookies.get(SECURE_SESSION_COOKIE)
    if raw_cookie is None:
        raw_cookie = request.cookies.get(SESSION_COOKIE)
    token = verify_session_cookie(raw_cookie, settings.better_auth_secret)
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Session"},
        )
    actor = resolve_session_token(token)
    if actor is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session not found or expired",
            headers={"WWW-Authenticate": "Session"},
        )
    return actor
