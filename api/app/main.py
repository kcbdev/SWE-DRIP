"""Control Panel API entrypoint.

PBI-002 ships only the health route; the app must import cleanly with no
database and no network access.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .routers import agents, approvals, analytics, audit, catalog, collections, dashboard, designs, me, runs, settings as settings_router, stream, users, webhooks

app = FastAPI(title=settings.app_name, version=settings.app_version)

# CORS — allow the Control Panel origin for cookie-based auth (credentials: include).
# In production the panel is served from swedrip-panel.kcb.ma; in dev from localhost:3000.
_origins = [
    "https://swedrip-panel.kcb.ma",
    "http://localhost:3000",
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
