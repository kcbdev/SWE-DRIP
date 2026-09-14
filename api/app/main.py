"""Control Panel API entrypoint.

PBI-002 ships only the health route; the app must import cleanly with no
database and no network access.
"""

from fastapi import FastAPI

from .config import settings
from .routers import approvals, analytics, audit, catalog, collections, dashboard, designs, me, runs, stream, users, webhooks

app = FastAPI(title=settings.app_name, version=settings.app_version)


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
