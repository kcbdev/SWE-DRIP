"""Scoped Bearer tokens for machine clients (operator-mcp C1).

Better Auth cookies serve browsers; MCP/CLI clients authenticate with
long-lived operator tokens instead. The plaintext (``sdr_`` + 32 random
bytes) is shown exactly once at issuance — at rest only ``sha256(salt +
token)`` is stored, with a per-token random salt. Verification is a
constant-time compare over the rows matching the token's prefix; revocation
is a timestamp flag (no hash update path, no delete path).

Scopes are exactly ``read`` and ``operate`` (``operate`` implies ``read``).
Token values never enter logs, errors, or audit rows — call sites carry the
``prefix`` (identification without disclosure).

Engine handling follows ``costs.py``: callers pass an engine in (the routers
pass ``api.app.db.get_engine()``), so unit tests inject fakes and stay
offline. ``require_token`` is the FastAPI dependency the MCP mount consumes.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from typing import Any, Callable, Optional

from fastapi import HTTPException, Request, status

SCOPE_READ = "read"
SCOPE_OPERATE = "operate"
SCOPES = (SCOPE_READ, SCOPE_OPERATE)

TOKEN_PREFIX = "sdr_"
PREFIX_CHARS = 12  # "sdr_" + 8 chars of the random part (identification only)


@dataclass(frozen=True)
class TokenActor:
    """The machine caller resolved from a Bearer token (MCP-side principal)."""

    token_id: int
    prefix: str
    name: str
    scopes: tuple[str, ...]
    created_by: str


def scope_covers(granted: tuple[str, ...] | list[str], required: str) -> bool:
    """True when ``granted`` satisfies ``required`` (operate implies read)."""
    if required == SCOPE_READ:
        return SCOPE_READ in granted or SCOPE_OPERATE in granted
    return required in granted


def _check_scopes(scopes: list[str]) -> tuple[str, ...]:
    unknown = [s for s in scopes if s not in SCOPES]
    if unknown:
        raise ValueError(f"unknown token scopes: {unknown!r} (allowed: {list(SCOPES)!r})")
    if not scopes:
        raise ValueError("at least one token scope is required")
    return tuple(dict.fromkeys(scopes))  # de-duplicated, order-stable


def _hash_token(plaintext: str, salt: str) -> str:
    return hashlib.sha256((salt + plaintext).encode("utf-8")).hexdigest()


def issue_token(
    engine: Any,
    *,
    name: str,
    scopes: list[str],
    actor_user_id: str,
) -> tuple[str, dict[str, Any]]:
    """Create a token row; return ``(plaintext, metadata)``.

    The plaintext is returned exactly once — callers show it at issuance and
    never persist or log it. Raises ``ValueError`` on bad scopes/names.
    """
    if not name or not name.strip():
        raise ValueError("token name is required")
    if not actor_user_id:
        raise ValueError("actor_user_id is required")
    checked = _check_scopes(list(scopes))
    plaintext = TOKEN_PREFIX + secrets.token_urlsafe(32)
    salt = secrets.token_hex(16)
    prefix = plaintext[:PREFIX_CHARS]
    with engine.begin() as conn:
        row = (
            conn.execute(
                _insert_statement(),
                {
                    "token_hash": _hash_token(plaintext, salt),
                    "salt": salt,
                    "prefix": prefix,
                    "name": name.strip(),
                    "scopes": ",".join(checked),
                    "created_by": actor_user_id,
                },
            )
            .mappings()
            .first()
        )
    meta = {
        "id": row["id"] if row else None,
        "prefix": prefix,
        "name": name.strip(),
        "scopes": list(checked),
        "created_by": actor_user_id,
    }
    return plaintext, meta


def _insert_statement() -> Any:
    from sqlalchemy import text

    return text(
        "INSERT INTO operator_tokens (token_hash, salt, prefix, name, scopes, created_by) "
        "VALUES (:token_hash, :salt, :prefix, :name, :scopes, :created_by) "
        "RETURNING id"
    )


def verify_token(engine: Any, plaintext: str) -> Optional[TokenActor]:
    """Resolve a presented token to its actor; None when unknown or revoked.

    Never raises on store trouble — callers treat None as unauthenticated
    (401), and store failures degrade to denial, never to access.
    """
    if not isinstance(plaintext, str) or not plaintext.startswith(TOKEN_PREFIX):
        return None
    prefix = plaintext[:PREFIX_CHARS]
    try:
        from sqlalchemy import text

        with engine.connect() as conn:
            rows = (
                conn.execute(
                    text(
                        "SELECT id, token_hash, salt, prefix, name, scopes, "
                        "created_by, revoked_at FROM operator_tokens "
                        "WHERE prefix = :prefix AND revoked_at IS NULL"
                    ),
                    {"prefix": prefix},
                )
                .mappings()
                .all()
            )
    except Exception:
        return None
    for row in rows:
        expected = row["token_hash"]
        if isinstance(expected, str) and hmac.compare_digest(
            expected, _hash_token(plaintext, str(row["salt"]))
        ):
            _touch_last_used(engine, row["id"])
            scopes = tuple(s for s in str(row["scopes"] or "").split(",") if s)
            return TokenActor(
                token_id=row["id"],
                prefix=str(row["prefix"]),
                name=str(row["name"]),
                scopes=scopes,
                created_by=str(row["created_by"]),
            )
    return None


def _touch_last_used(engine: Any, token_id: int) -> None:
    """Best-effort activity stamp — a failure here never breaks auth."""
    try:
        from sqlalchemy import text

        with engine.begin() as conn:
            conn.execute(
                text("UPDATE operator_tokens SET last_used_at = now() WHERE id = :id"),
                {"id": token_id},
            )
    except Exception:
        pass


def revoke_token(engine: Any, token_id: int) -> bool:
    """Flag a token revoked; True when a live row was flagged."""
    from sqlalchemy import text

    with engine.begin() as conn:
        result = conn.execute(
            text(
                "UPDATE operator_tokens SET revoked_at = now() "
                "WHERE id = :id AND revoked_at IS NULL"
            ),
            {"id": token_id},
        )
    return (result.rowcount or 0) > 0


def list_tokens(engine: Any) -> list[dict[str, Any]]:
    """Token metadata for admins — hashes never leave the store."""
    from sqlalchemy import text

    with engine.connect() as conn:
        rows = (
            conn.execute(
                text(
                    "SELECT id, prefix, name, scopes, created_by, "
                    "revoked_at IS NOT NULL AS revoked, last_used_at, created_at "
                    "FROM operator_tokens ORDER BY id ASC"
                )
            )
            .mappings()
            .all()
        )
    return [
        {
            "id": row["id"],
            "prefix": row["prefix"],
            "name": row["name"],
            "scopes": [s for s in str(row["scopes"] or "").split(",") if s],
            "created_by": row["created_by"],
            "revoked": bool(row["revoked"]),
            "last_used_at": row["last_used_at"],
            "created_at": row["created_at"],
        }
        for row in rows
    ]


def _bearer_token(request: Request) -> Optional[str]:
    header = request.headers.get("authorization", "")
    scheme, _, value = header.partition(" ")
    if scheme.lower() != "bearer" or not value.strip():
        return None
    return value.strip()


def require_token(*scopes: str) -> Callable[[Request], TokenActor]:
    """Build a dependency admitting callers whose token covers ``scopes``.

    No token / unknown / revoked → 401. Insufficient scope → 403. Cookie or
    session auth is never consulted here — machine clients only.
    """
    if not scopes:
        raise ValueError("require_token() needs at least one scope")
    for scope in scopes:
        if scope not in SCOPES:
            raise ValueError(f"unknown token scope: {scope!r}")

    def dependency(request: Request) -> TokenActor:
        from .db import get_engine

        plaintext = _bearer_token(request)
        actor = verify_token(get_engine(), plaintext or "")
        if actor is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Valid Bearer operator token required",
            )
        if not all(scope_covers(actor.scopes, scope) for scope in scopes):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Token lacks required scope(s): {', '.join(scopes)}",
            )
        return actor

    return dependency
