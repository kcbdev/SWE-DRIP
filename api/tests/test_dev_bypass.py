"""Dev auth bypass contracts (PBI-057) — UI verification only, never production."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.app.auth import ROLE_ADMIN, get_current_actor
from api.app.config import settings
from api.app.dev_bypass import (
    DEV_BYPASS_USER_ID,
    enforce_dev_bypass_at_startup,
    resolve_dev_bypass,
)


class TestResolve:
    @pytest.mark.parametrize("raw", [None, "", "   ", "false", "FALSE", "False", " fAlSe "])
    def test_off_values(self, raw) -> None:
        assert resolve_dev_bypass(raw, "") is None
        assert resolve_dev_bypass(raw, "development") is None

    @pytest.mark.parametrize("email", ["dev@local", "khalid@kcb.ma", "a@b.c", "dev@localhost"])
    def test_email_enables(self, email) -> None:
        assert resolve_dev_bypass(email, "") == email
        assert resolve_dev_bypass(f"  {email}  ", "development") == email

    @pytest.mark.parametrize("raw", ["true", "1", "yes", "not-an-email", "a@b c", "@x", "a@", "a@@b.c"])
    def test_garbage_is_loud(self, raw) -> None:
        with pytest.raises(ValueError, match="must be empty"):
            resolve_dev_bypass(raw, "")

    def test_production_refuses(self) -> None:
        with pytest.raises(RuntimeError, match="refusing to boot"):
            resolve_dev_bypass("dev@local", "production")
        with pytest.raises(RuntimeError, match="refusing to boot"):
            resolve_dev_bypass("dev@local", " Production ")

    def test_production_without_bypass_is_fine(self) -> None:
        assert resolve_dev_bypass("", "production") is None
        assert resolve_dev_bypass("false", "production") is None


class TestEnforce:
    def test_misconfig_fails_fast(self, monkeypatch) -> None:
        monkeypatch.setattr(settings, "dev_auth_bypass", "dev@local")
        monkeypatch.setattr(settings, "app_env", "production")
        with pytest.raises(RuntimeError, match="refusing to boot"):
            enforce_dev_bypass_at_startup(settings)

    def test_clean_config_passes(self, monkeypatch) -> None:
        monkeypatch.setattr(settings, "dev_auth_bypass", "")
        monkeypatch.setattr(settings, "app_env", "")
        assert enforce_dev_bypass_at_startup(settings) is None


def _app() -> FastAPI:
    from fastapi import Depends, Request

    app = FastAPI()

    @app.get("/whoami")
    def whoami(actor=Depends(get_current_actor)):
        return {"user_id": actor.user_id, "email": actor.email, "role": actor.role}

    return app


class TestActor:
    def test_bypass_returns_marked_admin_without_cookie(self, monkeypatch) -> None:
        monkeypatch.setattr(settings, "dev_auth_bypass", "dev@local")
        monkeypatch.setattr(settings, "app_env", "")
        body = TestClient(_app()).get("/whoami").json()
        assert body == {"user_id": DEV_BYPASS_USER_ID, "email": "dev@local", "role": ROLE_ADMIN}

    def test_off_still_401s_without_session(self, monkeypatch) -> None:
        monkeypatch.setattr(settings, "dev_auth_bypass", "")
        monkeypatch.setattr(settings, "app_env", "")
        assert TestClient(_app()).get("/whoami").status_code == 401

    def test_prod_bypass_raises_loud(self, monkeypatch) -> None:
        monkeypatch.setattr(settings, "dev_auth_bypass", "dev@local")
        monkeypatch.setattr(settings, "app_env", "production")
        with pytest.raises(RuntimeError, match="refusing to boot"):
            TestClient(_app()).get("/whoami")
