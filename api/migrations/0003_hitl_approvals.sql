-- 0003_hitl_approvals.sql — approvals index (data spec §1.2, hitl-approvals C1).
--
-- This is an INDEX for querying/filtering, not a second approval model: the
-- LangGraph interrupt remains the source of truth for gate state (spec
-- Decisions, NFR-1). Rows are created pending per open (run_id, node) gate
-- and transition to a terminal status exactly once (claim pattern in
-- `api/app/hitl.py`). Idempotent.

CREATE TABLE IF NOT EXISTS hitl_approvals (
    id               BIGSERIAL PRIMARY KEY,
    run_id           VARCHAR(128) NOT NULL,
    node             VARCHAR(64) NOT NULL,
    status           VARCHAR(32) NOT NULL DEFAULT 'pending'
                     CHECK (status IN ('pending', 'approved', 'rejected', 'regenerate_requested')),
    reviewer_user_id VARCHAR(128),
    note             TEXT,
    decided_at       TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS ix_hitl_approvals_status ON hitl_approvals (status);
CREATE INDEX IF NOT EXISTS ix_hitl_approvals_run ON hitl_approvals (run_id);

-- Exactly one open row per gate: concurrent ensures collapse into one row.
CREATE UNIQUE INDEX IF NOT EXISTS uq_hitl_approvals_open
    ON hitl_approvals (run_id, node) WHERE status = 'pending';
