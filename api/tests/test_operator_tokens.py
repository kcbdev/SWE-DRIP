"""Operator token auth contracts (PBI-043, spec C1) — offline, fakes."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from api.app import operator_tokens as tokens
from api.app.audit import get_audit_writer
from api.app.auth import ROLE_ADMIN, ROLE_VIEWER, Actor, get_current_actor
from api.app.operator_tokens import (
    SCOPE_OPERATE,
    SCOPE_READ,
    TokenActor,
    issue_token,
    list_tokens,
    require_token,
    revoke_token,
    scope_covers,
    verify_token,
)
from api.app.routers import operator_tokens as tokens_router


# ---------------------------------------------------------------------------
# Fake token store (emulates the text() queries the module issues)
# ---------------------------------------------------------------------------

class FakeResult:
    def __init__(self, rows: list[dict[str, Any]], rowcount: int = 0) -> None:
        self._rows = rows
        self.rowcount = rowcount

    def mappings(self) -> "FakeResult":
        return self

    def first(self) -> Optional[dict[str, Any]]:
        return self._rows[0] if self._rows else None

    def all(self) -> list[dict[str, Any]]:
        return list(self._rows)


class FakeTokenDB:
    """Minimal operator_tokens table: keyed by id, honors revocation."""

    def __init__(self) -> None:
        self.rows: dict[int, dict[str, Any]] = {}
        self.next_id = 1
        self.calls: list[str] = []

    def __call__(self, stmt: Any, params: Optional[dict[str, Any]] = None) -> FakeResult:
        sql = str(stmt)
        params = dict(params or {})
        self.calls.append(sql.split("(")[0].strip()[:60])
        if sql.startswith("INSERT INTO operator_tokens"):
            row_id = self.next_id
            self.next_id += 1
            self.rows[row_id] = {"id": row_id, **params, "revoked_at": None,
                                 "last_used_at": None, "created_at": "2026-09-16T00:00:00+00:00"}
            return FakeResult([{"id": row_id}], rowcount=1)
        if "FROM operator_tokens WHERE prefix" in sql:
            out = [r for r in self.rows.values()
                   if r["prefix"] == params.get("prefix") and r["revoked_at"] is None]
            return FakeResult(out)
        if sql.startswith("UPDATE operator_tokens SET last_used_at"):
            return FakeResult([], rowcount=1)
        if sql.startswith("UPDATE operator_tokens SET revoked_at"):
            row = self.rows.get(params.get("id"))
            if row is not None and row["revoked_at"] is None:
                row["revoked_at"] = "2026-09-16T00:00:00+00:00"
                return FakeResult([], rowcount=1)
            return FakeResult([], rowcount=0)
        if sql.startswith("SELECT id, prefix, name"):
            return FakeResult([dict(r, revoked=r["revoked_at"] is not None) for r in self.rows.values()])
        if sql.startswith("SELECT prefix FROM operator_tokens"):
            row = self.rows.get(params.get("id"))
            return FakeResult([{"prefix": row["prefix"]}] if row else [])
        raise AssertionError(f"unexpected SQL in fake: {sql[:80]}")


class FakeConn:
    def __init__(self, db: FakeTokenDB) -> None:
        self._db = db

    def execute(self, stmt: Any, params: Optional[dict[str, Any]] = None) -> FakeResult:
        return self._db(stmt, params)

    def __enter__(self) -> "FakeConn":
        return self

    def __exit__(self, *args: Any) -> None:
        return None


class FakeEngine:
    def __init__(self, db: FakeTokenDB) -> None:
        self._db = db

    def begin(self) -> FakeConn:
        return FakeConn(self._db)

    def connect(self) -> FakeConn:
        return FakeConn(self._db)


def _engine() -> tuple[FakeEngine, FakeTokenDB]:
    db = FakeTokenDB()
    return FakeEngine(db), db


# ---------------------------------------------------------------------------
# Scope algebra + issuance validation
# ---------------------------------------------------------------------------

class TestScopes:
    def test_operate_implies_read(self) -> None:
        assert scope_covers(["operate"], "read") is True
        assert scope_covers(["operate"], "operate") is True
        assert scope_covers(["read"], "read") is True
        assert scope_covers(["read"], "operate") is False
        assert scope_covers([], "read") is False

    def test_unknown_scope_rejected(self) -> None:
        engine, _ = _engine()
        try:
            issue_token(engine, name="x", scopes=["root"], actor_user_id="u-9")
        except ValueError as exc:
            assert "unknown token scopes" in str(exc)
        else:
            raise AssertionError("expected ValueError")

    def test_empty_name_rejected(self) -> None:
        engine, _ = _engine()
        try:
            issue_token(engine, name="  ", scopes=["read"], actor_user_id="u-9")
        except ValueError:
            pass
        else:
            raise AssertionError("expected ValueError")


class TestIssueVerify:
    def test_round_trip(self) -> None:
        engine, _ = _engine()
        plaintext, meta = issue_token(engine, name="mcp-runner", scopes=["operate"],
                                      actor_user_id="u-9")
        assert plaintext.startswith("sdr_") and len(plaintext) > 20
        assert meta["prefix"] == plaintext[:12]
        assert meta["scopes"] == ["operate"]
        actor = verify_token(engine, plaintext)
        assert isinstance(actor, TokenActor)
        assert actor.scopes == ("operate",)
        assert actor.created_by == "u-9"

    def test_plaintext_never_stored(self) -> None:
        engine, db = _engine()
        plaintext, meta = issue_token(engine, name="m", scopes=["read"], actor_user_id="u-9")
        stored = [v for row in db.rows.values() for v in row.values() if isinstance(v, str)]
        assert plaintext not in stored  # no field equals the token…
        assert meta["prefix"] in stored  # …except the identification prefix, by design
        (row,) = db.rows.values()
        assert row["token_hash"] != plaintext and len(row["token_hash"]) == 64

    def test_unknown_token_is_none(self) -> None:
        engine, _ = _engine()
        assert verify_token(engine, "sdr_nonexistenttokenvalue") is None
        assert verify_token(engine, "not-a-token") is None
        assert verify_token(engine, "") is None

    def test_revoked_token_stops_verifying(self) -> None:
        engine, _ = _engine()
        plaintext, meta = issue_token(engine, name="m", scopes=["read"], actor_user_id="u-9")
        assert verify_token(engine, plaintext) is not None
        assert revoke_token(engine, meta["id"]) is True
        assert revoke_token(engine, meta["id"]) is False  # already revoked
        assert verify_token(engine, plaintext) is None

    def test_prefix_collision_authenticates_only_the_hash_match(self) -> None:
        import hashlib

        engine, db = _engine()
        good, _ = issue_token(engine, name="good", scopes=["read"], actor_user_id="u-9")
        prefix = good[:12]
        # A second row sharing the prefix but a different hash must not match.
        db.rows[999] = {"id": 999, "token_hash": hashlib.sha256(b"other").hexdigest(),
                        "salt": "pepper", "prefix": prefix, "name": "evil",
                        "scopes": "operate", "created_by": "mallory",
                        "revoked_at": None, "last_used_at": None,
                        "created_at": "2026-09-16T00:00:00+00:00"}
        actor = verify_token(engine, good)
        assert actor is not None and actor.name == "good"
        assert verify_token(engine, prefix + "wrong-body-payload") is None

    def test_hash_is_salted(self) -> None:
        engine, db = _engine()
        issue_token(engine, name="a", scopes=["read"], actor_user_id="u-9")
        issue_token(engine, name="b", scopes=["read"], actor_user_id="u-9")
        salts = {r["salt"] for r in db.rows.values()}
        assert len(salts) == 2


class TestListTokens:
    def test_lists_metadata_without_hashes(self) -> None:
        engine, _ = _engine()
        issue_token(engine, name="m", scopes=["read", "operate"], actor_user_id="u-9")
        (row,) = list_tokens(engine)
        assert row["name"] == "m" and row["scopes"] == ["read", "operate"]
        assert row["revoked"] is False
        assert "token_hash" not in row and "salt" not in row


# ---------------------------------------------------------------------------
# require_token dependency
# ---------------------------------------------------------------------------

def _token_app(*scopes: str) -> FastAPI:
    app = FastAPI()

    @app.get("/gated")
    def gated(actor: TokenActor = Depends(require_token(*scopes))) -> dict[str, Any]:
        return {"actor": actor.name, "scopes": list(actor.scopes)}

    return app


class TestRequireToken:
    def test_missing_header_401(self, monkeypatch) -> None:
        engine, _ = _engine()
        monkeypatch.setattr("api.app.db.get_engine", lambda: engine)
        resp = TestClient(_token_app("read")).get("/gated")
        assert resp.status_code == 401

    def test_unknown_token_401(self, monkeypatch) -> None:
        engine, _ = _engine()
        monkeypatch.setattr("api.app.db.get_engine", lambda: engine)
        resp = TestClient(_token_app("read")).get(
            "/gated", headers={"Authorization": "Bearer sdr_nope"})
        assert resp.status_code == 401

    def test_insufficient_scope_403(self, monkeypatch) -> None:
        engine, _ = _engine()
        plaintext, _ = issue_token(engine, name="r", scopes=["read"], actor_user_id="u-9")
        monkeypatch.setattr("api.app.db.get_engine", lambda: engine)
        resp = TestClient(_token_app("operate")).get(
            "/gated", headers={"Authorization": f"Bearer {plaintext}"})
        assert resp.status_code == 403

    def test_operate_token_passes(self, monkeypatch) -> None:
        engine, _ = _engine()
        plaintext, _ = issue_token(engine, name="o", scopes=["operate"], actor_user_id="u-9")
        monkeypatch.setattr("api.app.db.get_engine", lambda: engine)
        resp = TestClient(_token_app("operate")).get(
            "/gated", headers={"Authorization": f"Bearer {plaintext}"})
        assert resp.status_code == 200
        assert resp.json()["actor"] == "o"

    def test_operate_token_covers_read_scope(self, monkeypatch) -> None:
        engine, _ = _engine()
        plaintext, _ = issue_token(engine, name="o", scopes=["operate"], actor_user_id="u-9")
        monkeypatch.setattr("api.app.db.get_engine", lambda: engine)
        resp = TestClient(_token_app("read")).get(
            "/gated", headers={"Authorization": f"Bearer {plaintext}"})
        assert resp.status_code == 200

    def test_revoked_bearer_is_401_end_to_end(self, monkeypatch) -> None:
        engine, _ = _engine()
        plaintext, meta = issue_token(engine, name="r", scopes=["read"], actor_user_id="u-9")
        monkeypatch.setattr("api.app.db.get_engine", lambda: engine)
        client = TestClient(_token_app("read"))
        headers = {"Authorization": f"Bearer {plaintext}"}
        assert client.get("/gated", headers=headers).status_code == 200
        assert revoke_token(engine, meta["id"]) is True
        assert client.get("/gated", headers=headers).status_code == 401

    def test_bearer_edge_cases_are_401(self, monkeypatch) -> None:
        engine, _ = _engine()
        monkeypatch.setattr("api.app.db.get_engine", lambda: engine)
        client = TestClient(_token_app("read"))
        assert client.get("/gated", headers={"Authorization": "bearer"}).status_code == 401
        assert client.get("/gated", headers={"Authorization": "Bearer "}).status_code == 401
        assert client.get("/gated", headers={"Authorization": "Basic abc"}).status_code == 401

    def test_cookies_never_consulted(self, monkeypatch) -> None:
        engine, _ = _engine()
        monkeypatch.setattr("api.app.db.get_engine", lambda: engine)
        resp = TestClient(_token_app("read")).get(
            "/gated", cookies={"better-auth.session_token": "valid-looking"})
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Router: issue / list / revoke (Admin-only, audited)
# ---------------------------------------------------------------------------

class _NoopAudit:
    def record(self, **kwargs: Any) -> None:
        pass


def _router_client(role: str, engine: FakeEngine, monkeypatch) -> TestClient:
    import api.app.routers.operator_tokens as router_module

    app = FastAPI()
    app.include_router(tokens_router.router)
    app.dependency_overrides[get_current_actor] = lambda: Actor("u-9", "a@b.c", role)
    app.dependency_overrides[get_audit_writer] = lambda: _NoopAudit()
    monkeypatch.setattr(router_module, "get_engine", lambda: engine)
    return TestClient(app, raise_server_exceptions=False)


class TestRouter:
    def test_issue_returns_plaintext_once_and_audits(self, monkeypatch) -> None:
        from api.app.audit import get_audit_writer

        engine, db = _engine()
        calls: list[dict[str, Any]] = []

        class FakeAudit:
            def record(self, **kwargs: Any) -> None:
                calls.append(kwargs)

        import api.app.routers.operator_tokens as router_module

        app = FastAPI()
        app.include_router(tokens_router.router)
        app.dependency_overrides[get_current_actor] = lambda: Actor("u-9", "a@b.c", ROLE_ADMIN)
        app.dependency_overrides[get_audit_writer] = lambda: FakeAudit()
        monkeypatch.setattr(router_module, "get_engine", lambda: engine)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post("/api/operator-tokens",
                           json={"name": "ci", "scopes": ["read"]})
        assert resp.status_code == 201
        body = resp.json()
        assert body["token"].startswith("sdr_")
        assert len(db.rows) == 1
        assert len(calls) == 1 and calls[0]["action"] == "operator_token.issue"
        assert "token" not in calls[0]  # no top-level value key…
        assert body["token"] not in str(calls[0])  # …and the value itself never lands

    def test_list_hides_values(self, monkeypatch) -> None:
        engine, _ = _engine()
        issue_token(engine, name="m", scopes=["read"], actor_user_id="u-9")
        body = _router_client(ROLE_ADMIN, engine, monkeypatch).get("/api/operator-tokens").json()
        assert len(body["items"]) == 1
        assert "token" not in body["items"][0] and "token_hash" not in body["items"][0]

    def test_revoke_flow_and_errors(self, monkeypatch) -> None:
        engine, _ = _engine()
        plaintext, meta = issue_token(engine, name="m", scopes=["read"], actor_user_id="u-9")
        client = _router_client(ROLE_ADMIN, engine, monkeypatch)
        resp = client.post(f"/api/operator-tokens/{meta['id']}/revoke")
        assert resp.status_code == 200 and resp.json()["revoked"] is True
        assert verify_token(engine, plaintext) is None
        assert client.post(f"/api/operator-tokens/{meta['id']}/revoke").status_code == 409
        assert client.post("/api/operator-tokens/999/revoke").status_code == 404

    def test_viewer_cannot_manage(self, monkeypatch) -> None:
        engine, _ = _engine()
        client = _router_client(ROLE_VIEWER, engine, monkeypatch)
        assert client.post("/api/operator-tokens",
                           json={"name": "x", "scopes": ["read"]}).status_code == 403
        assert client.get("/api/operator-tokens").status_code == 403

    def test_operator_role_and_anonymous_cannot_manage(self, monkeypatch) -> None:
        from api.app.auth import ROLE_OPERATOR

        engine, _ = _engine()
        operator = _router_client(ROLE_OPERATOR, engine, monkeypatch)
        assert operator.post("/api/operator-tokens",
                             json={"name": "x", "scopes": ["read"]}).status_code == 403
        assert operator.get("/api/operator-tokens").status_code == 403
        import api.app.routers.operator_tokens as router_module

        app = FastAPI()
        app.include_router(tokens_router.router)
        monkeypatch.setattr(router_module, "get_engine", lambda: engine)
        anonymous = TestClient(app)
        assert anonymous.get("/api/operator-tokens").status_code == 401
        assert anonymous.post("/api/operator-tokens",
                              json={"name": "x", "scopes": ["read"]}).status_code == 401
