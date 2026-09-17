"""Dev auth bypass (PBI-057) — local UI verification only, never production.

``SWE_DRIP_DEV_AUTH_BYPASS`` resolves to a bypass email or ``None``:

- missing / empty / whitespace-only / ``false`` (any case) → ``None`` (off,
  zero behavior change);
- an email (``local@domain``, no spaces) → that identity, auto-authed admin;
- anything else → ``ValueError`` (loud misconfiguration, never guessed);
- bypass email + ``APP_ENV=production`` → ``RuntimeError`` (the API refuses
  to boot; enforced at startup AND per request).

The bypassed actor carries user id ``dev-bypass`` so audits stay traceable
and can never be mistaken for a real user.
"""

from __future__ import annotations

from typing import Optional

DEV_BYPASS_USER_ID = "dev-bypass"


def resolve_dev_bypass(raw: object, app_env: object) -> Optional[str]:
    """Parse the bypass env value (pure — unit-tested)."""
    value = raw.strip() if isinstance(raw, str) else ""
    if not value or value.lower() == "false":
        return None
    local, sep, domain = value.partition("@")
    if not sep or value.count("@") != 1 or not local or not domain:
        raise ValueError(
            "SWE_DRIP_DEV_AUTH_BYPASS must be empty, 'false', or an email"
            f" — got {value!r}"
        )
    if any(char.isspace() for char in value):
        raise ValueError(
            "SWE_DRIP_DEV_AUTH_BYPASS must be empty, 'false', or an email"
            f" — got {value!r}"
        )
    if str(app_env or "").strip().lower() == "production":
        raise RuntimeError(
            "SWE_DRIP_DEV_AUTH_BYPASS is set with APP_ENV=production"
            " — refusing to boot"
        )
    return value


def enforce_dev_bypass_at_startup(settings) -> None:
    """Fail fast on misconfiguration (called once from main; per-request
    resolution in auth.py stays authoritative at runtime)."""
    resolve_dev_bypass(settings.dev_auth_bypass, settings.app_env)
