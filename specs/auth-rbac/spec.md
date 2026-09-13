# Spec: Auth & RBAC

## Goal

Give the Control Panel multi-user, session-based authentication with three roles (Admin, Operator, Viewer) enforced server-side, per PRD §2 — the traceability and approval features are meaningless if any session can silently act as any role. Better Auth is the single auth runtime (founder stack consistency); FastAPI is a strict validator of its sessions.

## Scope

- In scope: Better Auth (Next.js) setup with Postgres adapter; invite-only users (no public signup); session validation in FastAPI; role model + RBAC dependency for every API route; login/logout; Users & Roles management (list, invite, role change, deactivate).
- Out of scope: SSO/social providers, self-service password reset/email flows (invite-only at v1), audit rows for auth events (audit-log spec), session UI for device management.

## Contracts (success criteria)

- **C1 — Single auth runtime**: Better Auth owns credential storage and session lifecycle in the shared Postgres (`user`/`session`/`account` tables); FastAPI never issues credentials; a request's actor (`user_id`) and role are resolvable server-side from the session cookie.
- **C2 — RBAC is server-side**: roles `admin | operator | viewer` match the PRD permission matrix; every API route carries a role check; no session → 401; insufficient role → 403 regardless of UI state.
- **C3 — User management is Admin-only**: list users, invite (create) user, change role, deactivate; Operator/Viewer receive 403 on all of them.
- **C4 — Sessions are short-lived with refresh; logout revokes** server-side; no public signup route is enabled.
- **C5 — A1 evidence**: deterministic tests/scripts prove allow/deny per role on representative endpoints (e.g. Admin ✓ user management; Operator ✓ approvals action / ✗ user management; Viewer ✗ approvals action).

## Anti-patterns

- Hiding controls in the UI while the API stays open (role checks must exist server-side).
- Introducing a second auth system (Python-native sessions/JWT) alongside Better Auth.
- Trusting client-supplied role/identity headers or tokens.
- Enabling public signup or long-lived sessions without refresh.
- Logging secrets or session tokens.

## Decisions

- ADR-003 — auth architecture: Better Auth in `control-panel/` as sole runtime; FastAPI validates `better-auth.session_token` (HMAC signature + `session` row lookup); browser traffic same-origin `/api/*` (dev: Next rewrite; prod: Traefik path routing).
