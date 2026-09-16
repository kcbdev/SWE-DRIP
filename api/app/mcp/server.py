"""Operator MCP server (modelcontextprotocol/python-sdk, server-side use new).

``build_server()`` assembles one ``MCPServer`` with the SDK bearer transport
auth backed by the operator token store (PBI-043) and registers the tool set.
``mount_operator_mcp(app)`` mounts it at ``/mcp`` with the session lifespan
attached (mounted sub-app lifespans do not cascade in this stack — without
the outer lifespan every request 500s).

Transport posture (deliberate, documented): stateless Streamable HTTP with
single-JSON responses. Every tool is a quick query — no long-lived sessions
to manage, and the whole doorway stays drivable offline in tests. Auth is
re-verified per request by the SDK middleware, so revocation bites on the
next call without session teardown.
"""

from __future__ import annotations

import os
from typing import Any

from mcp.server.auth.settings import AuthSettings
from mcp.server.mcpserver import MCPServer

from .auth import OperatorTokenVerifier
from .tools_graph import graph_inspect
from .tools_reads import READ_TOOLS
from .tools_writes import WRITE_TOOLS

SERVER_NAME = "swe-drip-operator"

SERVER_INSTRUCTIONS = (
    "SWE Drip operator doorway: runs, run logs, approvals queue, agents "
    "roster, model catalog, prompt metadata, collections, audit log, "
    "calibration, and locked graph structure (reads); run start, approval "
    "decisions, agent config, and replay (operate scope, audited). "
    "Structural graph changes are never offered."
)


def _issuer_host() -> str:
    """Public API hostname (drives metadata URLs and the Host allowlist)."""
    from urllib.parse import urlparse

    base = os.environ.get("MCP_ISSUER_URL", "https://swedrip-api.kcb.ma").rstrip("/")
    return urlparse(base).hostname or "swedrip-api.kcb.ma"


def _auth_settings() -> AuthSettings:
    # Metadata only (issuer shown on the SDK's auth discovery document; no
    # OAuth round-trip exists — tokens are issued by POST /api/operator-tokens).
    # Per-tool scopes are enforced in the tools themselves, not here.
    base = os.environ.get("MCP_ISSUER_URL", "https://swedrip-api.kcb.ma").rstrip("/")
    return AuthSettings(
        issuer_url=base,
        resource_server_url=f"{base}/mcp",
        # Our tokens are single-purpose with no audience field; the verifier
        # authenticates the store hash, not a resource indicator.
        validate_token_resource=False,
    )


def _transport_security() -> Any:
    """DNS-rebinding guard that admits the public host (live-proven need).

    The SDK defaults the allowlist to localhost only, which 421s every
    request behind the production reverse proxy (verified live: valid token
    got "Invalid Host header"). The issuer hostname plus loopback entries
    keeps the rebinding protection meaningful in every environment.
    """
    from mcp.server.transport_security import TransportSecuritySettings

    host = _issuer_host()
    return TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=[host, f"{host}:*", "127.0.0.1:*", "localhost:*", "[::1]:*"],
        allowed_origins=[f"https://{host}", "http://127.0.0.1:*", "http://localhost:*"],
    )


def build_server() -> MCPServer:
    """Assemble the operator server (fresh instance per call — tests isolated)."""
    server = MCPServer(
        name=SERVER_NAME,
        instructions=SERVER_INSTRUCTIONS,
        token_verifier=OperatorTokenVerifier(),
        auth=_auth_settings(),
    )
    for tool_fn in (*READ_TOOLS, graph_inspect, *WRITE_TOOLS):
        server.tool()(tool_fn)
    return server


def mount_operator_mcp(app: Any) -> MCPServer:
    """Mount the doorway at ``/mcp`` with its session lifespan attached.

    Mounted sub-app lifespans do NOT cascade in this stack (verified by
    probe: the flag stayed off), so the StreamableHTTP session manager is
    entered on the OUTER app lifespan here — otherwise every /mcp request
    fails with "Task group is not initialized". Any pre-existing outer
    lifespan is chained, not replaced.
    """
    from contextlib import asynccontextmanager

    server = build_server()
    app.mount(
        "/mcp",
        server.streamable_http_app(
            streamable_http_path="/",
            stateless_http=True,
            json_response=True,
            transport_security=_transport_security(),
        ),
    )
    manager = server.session_manager
    previous = app.router.lifespan_context

    @asynccontextmanager
    async def _lifespan(app: Any) -> Any:
        if previous is not None:
            async with previous(app):
                async with manager.run():
                    yield
        else:
            async with manager.run():
                yield

    app.router.lifespan_context = _lifespan
    return server
