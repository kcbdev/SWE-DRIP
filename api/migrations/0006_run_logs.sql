-- 0006_run_logs.sql — per-node run logs (agent-control-plane C7).
--
-- Diagnostic surface ("what happened during a run"), NOT the audit trail:
-- append-only, no update/delete path. There is no retention/rotation policy
-- by design — reads are capped (QUERY_LIMIT in pipeline/runlog.py) and old
-- rows are simply never queried by the UI. Applied by
-- `python -m api.app.migrations` at API startup alongside the other files.

CREATE TABLE IF NOT EXISTS run_logs (
    id         BIGSERIAL PRIMARY KEY,
    run_id     VARCHAR(64)  NOT NULL,
    node       VARCHAR(64)  NOT NULL,
    level      VARCHAR(16)  NOT NULL DEFAULT 'info',
    message    TEXT         NOT NULL DEFAULT '',
    detail_json JSONB       NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_run_logs_run_created
    ON run_logs (run_id, created_at);
