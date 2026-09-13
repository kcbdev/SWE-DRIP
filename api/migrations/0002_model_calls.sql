-- 0002_model_calls.sql — per-call cost log (data spec §3).
-- Written by the pipeline via `pipeline/costs.py`; read by the dashboard for
-- the current-month spend vs the $130 cap. Append-only.

CREATE TABLE IF NOT EXISTS model_calls (
    id         BIGSERIAL PRIMARY KEY,
    node       VARCHAR(64) NOT NULL,
    model      VARCHAR(128) NOT NULL,
    tokens_in  INTEGER NOT NULL DEFAULT 0,
    tokens_out INTEGER NOT NULL DEFAULT 0,
    cost_usd   NUMERIC(12, 6) NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_model_calls_created ON model_calls (created_at);
CREATE INDEX IF NOT EXISTS ix_model_calls_node ON model_calls (node);
