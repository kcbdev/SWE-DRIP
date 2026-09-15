-- 0005_better_auth.sql — Better Auth core + admin-plugin tables.
--
-- Generated from the installed better-auth version's code-defined schema
-- (`getAuthTables` with emailAndPassword + admin plugin), translated to
-- Postgres DDL. Applied by `python -m api.app.migrations` at API startup,
-- so the Control Panel never needs `npx auth migrate` in production.
-- Idempotent. Contains no driver placeholders.
--
-- Column mapping: string -> TEXT, boolean -> BOOLEAN, date -> TIMESTAMPTZ.
-- required:true -> NOT NULL, defaultValue -> DEFAULT. `id` is generated
-- client-side by Better Auth (TEXT PRIMARY KEY, no DB default).

CREATE TABLE IF NOT EXISTS "user" (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    email           TEXT NOT NULL UNIQUE,
    "emailVerified" BOOLEAN NOT NULL DEFAULT FALSE,
    image           TEXT,
    "createdAt"     TIMESTAMPTZ NOT NULL,
    "updatedAt"     TIMESTAMPTZ NOT NULL,
    role            TEXT,
    banned          BOOLEAN DEFAULT FALSE,
    "banReason"     TEXT,
    "banExpires"    TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS session (
    id              TEXT PRIMARY KEY,
    "expiresAt"     TIMESTAMPTZ NOT NULL,
    token           TEXT NOT NULL UNIQUE,
    "createdAt"     TIMESTAMPTZ NOT NULL,
    "updatedAt"     TIMESTAMPTZ NOT NULL,
    "ipAddress"     TEXT,
    "userAgent"     TEXT,
    "userId"        TEXT NOT NULL REFERENCES "user" (id) ON DELETE CASCADE,
    "impersonatedBy" TEXT
);

CREATE TABLE IF NOT EXISTS account (
    id                      TEXT PRIMARY KEY,
    "accountId"             TEXT NOT NULL,
    "providerId"            TEXT NOT NULL,
    "userId"                TEXT NOT NULL REFERENCES "user" (id) ON DELETE CASCADE,
    "accessToken"           TEXT,
    "refreshToken"          TEXT,
    "idToken"               TEXT,
    "accessTokenExpiresAt"  TIMESTAMPTZ,
    "refreshTokenExpiresAt" TIMESTAMPTZ,
    scope                   TEXT,
    password                TEXT,
    "createdAt"             TIMESTAMPTZ NOT NULL,
    "updatedAt"             TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS verification (
    id           TEXT PRIMARY KEY,
    identifier   TEXT NOT NULL,
    value        TEXT NOT NULL,
    "expiresAt"  TIMESTAMPTZ NOT NULL,
    "createdAt"  TIMESTAMPTZ NOT NULL,
    "updatedAt"  TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_session_user ON session ("userId");
CREATE INDEX IF NOT EXISTS ix_account_user ON account ("userId");
CREATE INDEX IF NOT EXISTS ix_verification_identifier ON verification (identifier);
