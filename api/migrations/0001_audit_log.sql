-- 0001_audit_log.sql — append-only audit trail (spec audit-log C1/C2/C5).
-- Applied by `python -m api.app.migrations` (or any SQL runner) before the
-- first state-changing action. Idempotent.

CREATE TABLE IF NOT EXISTS audit_log (
    id            BIGSERIAL PRIMARY KEY,
    actor_user_id VARCHAR(128) NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    action        VARCHAR(64) NOT NULL,
    entity_type   VARCHAR(64) NOT NULL,
    entity_id     VARCHAR(128),
    before_json   JSONB,
    after_json    JSONB
);

CREATE INDEX IF NOT EXISTS ix_audit_log_actor ON audit_log (actor_user_id);
CREATE INDEX IF NOT EXISTS ix_audit_log_action ON audit_log (action);
CREATE INDEX IF NOT EXISTS ix_audit_log_entity ON audit_log (entity_type, entity_id);
CREATE INDEX IF NOT EXISTS ix_audit_log_created ON audit_log (created_at);
