"""MCP doorway auth (operator-mcp C1/C5).

The SDK's bearer middleware authenticates the transport with
:class:`OperatorTokenVerifier`; per-tool scope checks and actor synthesis
happen here, read from the SDK's auth context (populated per request, so
revocation takes effect on the next request).
"""

from __future__ import annotations

from typing import Any, Optional

from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.provider import AccessToken, TokenVerifier
from mcp.server.mcpserver.exceptions import ToolError as _SDKToolError

from ..auth import ROLE_ADMIN, ROLE_VIEWER, Actor
from ..operator_tokens import SCOPE_OPERATE, SCOPE_READ, scope_covers


class ToolError(_SDKToolError):
    """An anticipated tool failure with REST-equivalent meaning.

    Subclasses the SDK's ``ToolError`` so the message reaches the client in
    the ``is_error`` result (logged at INFO, no traceback): clients see
    ``Error executing tool {name}: {message} [{http_status}]``. Anything else
    raised is treated as a crash and its text stays on the server.
    """

    def __init__(self, message: str, http_status: int = 500) -> None:
        super().__init__(f"{message} [{http_status}]")
        self.http_status = http_status


class OperatorTokenVerifier(TokenVerifier):
    """SDK verifier backed by the operator token store (PBI-043).

    Never raises into the transport: any store trouble degrades to denial
    (None), never to access.
    """

    async def verify_token(self, token: str) -> AccessToken | None:
        import asyncio

        from .. import operator_tokens as tokens
        from ..db import get_engine

        try:
            actor = await asyncio.to_thread(tokens.verify_token, get_engine(), token)
        except Exception:
            return None
        if actor is None:
            return None
        return AccessToken(
            token=f"token:{actor.prefix}",
            client_id=f"token:{actor.prefix}",
            scopes=list(actor.scopes),
            subject=actor.created_by,
        )


def current_token() -> Optional[AccessToken]:
    """The verified token for this request, or None (defense in depth — the
    transport middleware guarantees presence before tools run)."""
    try:
        return get_access_token()
    except Exception:
        return None


def require_scope(scope: str) -> AccessToken:
    """Enforce one token scope inside a tool; 401/403 as ToolError."""
    token = current_token()
    if token is None:
        raise ToolError("Valid Bearer operator token required", 401)
    if not scope_covers(token.scopes, scope):
        raise ToolError(f"Token lacks required scope(s): {scope}", 403)
    return token


def tool_actor() -> Actor:
    """Synthesize the downstream actor after scope checks passed.

    Scope enforcement happens at the tool boundary (``require_scope``); the
    role below only satisfies the router functions' own role checks, which
    the scope check already subsumes: ``operate`` ≡ admin, ``read`` ≡ viewer.
    The user id names the token, never a human.
    """
    token = require_scope(SCOPE_READ)
    role = ROLE_ADMIN if scope_covers(token.scopes, SCOPE_OPERATE) else ROLE_VIEWER
    return Actor(user_id=token.client_id, email="", role=role)


def token_prefix() -> str:
    """Identification prefix of the calling token (audits carry this)."""
    token = current_token()
    if token is None:
        return "unknown"
    return token.client_id.removeprefix("token:")
