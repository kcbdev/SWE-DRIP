-- 0007_operator_tokens.sql — scoped Bearer tokens for machine clients (operator-mcp C1).
--
-- Better Auth cookies do not serve MCP/CLI clients, so operator tokens fill
-- the gap: append-only rows plus a revocation flag (no hash update path).
-- The plaintext appears exactly once (issuance response); only the salted
-- hash rests here. Applied by `python -m api.app.migrations` at API startup
-- alongside the other files.

CREATE TABLE IF NOT EXISTS operator_tokens (
    id         BIGSERIAL PRIMARY KEY,
    token_hash VARCHAR(128) NOT NULL UNIQUE,
    salt       VARCHAR(64)  NOT NULL,
    prefix     VARCHAR(32)  NOT NULL,
    name       VARCHAR(128) NOT NULL,
    scopes     TEXT         NOT NULL DEFAULT 'read',
    created_by VARCHAR(128) NOT NULL DEFAULT '',
    revoked_at TIMESTAMPTZ,
    last_used_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_operator_tokens_prefix
    ON operator_tokens (prefix);
