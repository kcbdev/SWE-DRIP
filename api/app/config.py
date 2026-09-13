"""Environment-driven settings for the Control Panel API.

No side effects on import: nothing here opens a database connection or calls an
external service. Missing values fall back to empty strings so the health gate
runs fully offline.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration, sourced from the environment (and optional .env)."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Core
    app_name: str = "SWE Drip Control Panel API"
    app_version: str = "0.1.0"
    debug: bool = False

    # Datastores
    database_url: str = ""

    # Auth (Better Auth runtime; validated server-side by the API)
    better_auth_secret: str = ""
    better_auth_url: str = ""

    # Models
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"

    # Storefront (Fourthwall MCP)
    fourthwall_mcp_url: str = ""
    fourthwall_mcp_token: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
