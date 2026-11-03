"""
Cedric AI - Settings
=====================

Centralizes every environment-variable-driven setting in one typed
object, instead of scattering `os.getenv("X")` calls across the
codebase. `pydantic-settings` reads from the process environment and
from a local `.env` file (via python-dotenv under the hood), and
validates types - e.g. `jwt_expire_minutes` really is an int, not a
string that happens to look like one.

WHY THIS MATTERS FOR SECURITY:
`jwt_secret_key` has no default value. If it's missing from `.env`,
Settings() raises an error at startup instead of silently falling
back to a hardcoded/guessable secret. A JWT signed with a weak or
predictable secret can be forged by anyone - failing loudly here is
much safer than failing silently later.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # SQLite by default for local development - zero setup required.
    # Swap this for a postgresql:// URL in .env once Postgres+pgvector
    # is introduced (Phase 6) - no application code needs to change.
    database_url: str = "sqlite:///./cedric.db"

    # Secret used to sign/verify JWTs. Required - see docstring above.
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    # How long an access token stays valid. 24h is a dev-friendly
    # default (you won't get logged out mid-session while testing).
    # This will be revisited in Phase 27 (security hardening), likely
    # in favor of a short-lived access token + refresh token pair.
    jwt_expire_minutes: int = 60 * 24

    # Phase 3: Gemini API key. Required for any endpoint that talks to
    # the model (chat, and every later AI feature). Kept optional here
    # (rather than required, like jwt_secret_key) so the rest of the
    # app - auth, health check - still runs without it during setup.
    gemini_api_key: str = ""
    # "-latest" alias tracks whatever Google currently considers the
    # best fast/cheap model, so this doesn't silently break when a
    # specific dated model version is retired. Override in .env if you
    # want to pin an exact version.
    gemini_model: str = "gemini-flash-latest"
    # Phase 6: text embedding model (turns text into a vector).
    gemini_embedding_model: str = "gemini-embedding-001"

    # Phase 4: document storage. Local disk for dev - swappable for
    # S3/cloud storage later by changing storage.py's implementation
    # behind the same save/read/delete interface, without touching the
    # API routes that call it.
    storage_dir: str = "storage"
    max_upload_size_mb: int = 20

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
