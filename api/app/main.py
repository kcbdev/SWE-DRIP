"""Control Panel API entrypoint.

PBI-002 ships only the health route; the app must import cleanly with no
database and no network access.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .dev_bypass import enforce_dev_bypass_at_startup
from .routers import agents, approvals, analytics, audit, catalog, collections, dashboard, designs, me, runs, settings as settings_router, stream, users, webhooks, operator_tokens, inspiration, research, styles as styles_router

# Fail fast on auth misconfiguration (PBI-057): a dev bypass left enabled
# under APP_ENV=production refuses to boot instead of serving open admin.
enforce_dev_bypass_at_startup(settings)

app = FastAPI(title=settings.app_name, version=settings.app_version)

# CORS — allow the Control Panel origin for cookie-based auth (credentials: include).
# In production the panel is served from swedrip-panel.kcb.ma; in dev from localhost:3000
# (and :3001 when :3000 is taken by another app — loopback only, same trust).
_origins = [
    "https://swedrip-panel.kcb.ma",
    "http://localhost:3000",
    "http://localhost:3001",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict[str, str]:
    """Liveness probe. Intentionally free of database/external dependencies."""
    return {"status": "ok"}


app.include_router(me.router)
app.include_router(users.router)
app.include_router(audit.router)
app.include_router(dashboard.router)
app.include_router(collections.router)
app.include_router(designs.router)
app.include_router(runs.router)
app.include_router(catalog.router)
app.include_router(analytics.router)
app.include_router(approvals.router)
app.include_router(stream.router)
app.include_router(webhooks.router)
app.include_router(agents.router)
app.include_router(settings_router.router)
app.include_router(operator_tokens.router)
app.include_router(inspiration.router)
app.include_router(research.router)
app.include_router(styles_router.router)

# Operator MCP doorway (specs/operator-mcp): same deployable, Bearer tokens.
from .mcp.server import mount_operator_mcp

mount_operator_mcp(app)
