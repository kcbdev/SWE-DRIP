"""Health-route contract tests (offline; no DB, no network)."""

from fastapi.testclient import TestClient

from api.app.main import app

client = TestClient(app)


def test_health_returns_exact_json() -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_app_import_path_is_stable() -> None:
    assert app.title.startswith("SWE Drip")
