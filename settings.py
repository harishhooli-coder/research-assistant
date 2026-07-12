"""Centralised configuration shared across agent, bot, memory, api and db.

All secrets/connection strings are read from environment variables (or a local
``.env`` file). Nothing here requires real keys to import, so the code can be
imported and unit-tested fully offline.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

_PLACEHOLDER_SUFFIX = "..."
_MIN_ANTHROPIC_KEY_LEN = 30
_MIN_NVIDIA_KEY_LEN = 30
_MIN_TAVILY_KEY_LEN = 20
_MIN_AGENTMAIL_KEY_LEN = 20


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- LLM / tools -------------------------------------------------------
    llm_provider_setting: str = Field(default="", alias="LLM_PROVIDER")
    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")
    anthropic_model: str = Field(default="claude-sonnet-4-6", alias="ANTHROPIC_MODEL")
    nvidia_api_key: str = Field(default="", alias="NVIDIA_API_KEY")
    nvidia_model: str = Field(
        # llama-3.3-70b frequently queues/times out on the public NIM endpoint;
        # Nemotron Super is fast and reliable for tool-calling agent loops.
        default="nvidia/llama-3.3-nemotron-super-49b-v1",
        alias="NVIDIA_MODEL",
    )
    nvidia_base_url: str = Field(
        default="https://integrate.api.nvidia.com/v1",
        alias="NVIDIA_BASE_URL",
    )
    tavily_api_key: str = Field(default="", alias="TAVILY_API_KEY")

    # --- Telegram ----------------------------------------------------------
    telegram_bot_token: str = Field(default="", alias="TELEGRAM_BOT_TOKEN")

    # --- AgentMail (optional email delivery of research results) -----------
    agentmail_api_key: str = Field(default="", alias="AGENTMAIL_API_KEY")
    agentmail_inbox_id: str = Field(default="", alias="AGENTMAIL_INBOX_ID")

    # --- Redis (arq queue + pub/sub + episodic memory) ---------------------
    redis_url: str = Field(default="redis://localhost:6379", alias="REDIS_URL")

    # --- Database (Neon Postgres; local docker-compose Postgres optional) ---
    # async SQLAlchemy URL — must use postgresql+asyncpg:// (not sqlite) at runtime.
    database_url: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/research",
        alias="DATABASE_URL",
    )

    # --- HTTP / CORS -------------------------------------------------------
    # comma-separated list of allowed origins; "*" enables all (dev default)
    cors_allow_origins: str = Field(default="*", alias="CORS_ALLOW_ORIGINS")

    # --- Agent behaviour limits -------------------------------------------
    max_supervisor_steps: int = Field(default=5, alias="MAX_SUPERVISOR_STEPS")
    max_context_tokens: int = Field(default=8000, alias="MAX_CONTEXT_TOKENS")
    max_fetch_chars: int = Field(default=6000, alias="MAX_FETCH_CHARS")

    @property
    def cors_origins_list(self) -> list[str]:
        raw = (self.cors_allow_origins or "").strip()
        if raw in ("", "*"):
            return ["*"]
        return [o.strip() for o in raw.split(",") if o.strip()]

    @staticmethod
    def _looks_like_placeholder(value: str, *, min_len: int) -> bool:
        key = (value or "").strip()
        if not key:
            return True
        if key.endswith(_PLACEHOLDER_SUFFIX):
            return True
        return len(key) < min_len

    @property
    def resolved_llm_provider(self) -> str:
        explicit = (self.llm_provider_setting or "").strip().lower()
        if explicit in ("anthropic", "nvidia"):
            return explicit
        if not self._looks_like_placeholder(self.nvidia_api_key, min_len=_MIN_NVIDIA_KEY_LEN):
            return "nvidia"
        return "anthropic"

    @property
    def llm_provider(self) -> str:
        return self.resolved_llm_provider

    @property
    def anthropic_api_key_configured(self) -> bool:
        return not self._looks_like_placeholder(
            self.anthropic_api_key, min_len=_MIN_ANTHROPIC_KEY_LEN
        )

    @property
    def nvidia_api_key_configured(self) -> bool:
        return not self._looks_like_placeholder(
            self.nvidia_api_key, min_len=_MIN_NVIDIA_KEY_LEN
        )

    @property
    def tavily_api_key_configured(self) -> bool:
        return not self._looks_like_placeholder(
            self.tavily_api_key, min_len=_MIN_TAVILY_KEY_LEN
        )

    @property
    def agentmail_api_key_configured(self) -> bool:
        return not self._looks_like_placeholder(
            self.agentmail_api_key, min_len=_MIN_AGENTMAIL_KEY_LEN
        )

    def missing_llm_keys(self) -> list[str]:
        """Env vars for the configured LLM provider only."""
        missing: list[str] = []
        if self.resolved_llm_provider == "nvidia":
            if not self.nvidia_api_key_configured:
                missing.append("NVIDIA_API_KEY")
        elif not self.anthropic_api_key_configured:
            missing.append("ANTHROPIC_API_KEY")
        return missing

    def missing_runtime_keys(self) -> list[str]:
        """Return env var names that still hold example/placeholder values."""
        missing = self.missing_llm_keys()
        if not self.tavily_api_key_configured:
            missing.append("TAVILY_API_KEY")
        return missing

    def require_llm_keys(self) -> None:
        missing = self.missing_llm_keys()
        if not missing:
            return
        names = ", ".join(missing)
        raise RuntimeError(
            f"Missing or placeholder LLM API keys: {names}. "
            "Update .env (NVIDIA: https://build.nvidia.com, "
            "Anthropic: https://console.anthropic.com/settings/keys) "
            "and restart the API and worker."
        )

    def require_runtime_keys(self) -> None:
        missing = self.missing_runtime_keys()
        if not missing:
            return
        names = ", ".join(missing)
        raise RuntimeError(
            f"Missing or placeholder API keys: {names}. "
            "Update .env with real keys (NVIDIA: https://build.nvidia.com, "
            "Anthropic: https://console.anthropic.com/settings/keys, "
            "Tavily: https://tavily.com) — then restart the API and worker."
        )

    def require_postgres_database(self) -> None:
        url = (self.database_url or "").strip().lower()
        if url.startswith("sqlite"):
            raise RuntimeError(
                "SQLite is no longer supported. Set DATABASE_URL to your Neon "
                "Postgres URL (postgresql+asyncpg://...?ssl=require) in .env."
            )
        if not url.startswith("postgresql"):
            raise RuntimeError(
                "DATABASE_URL must be a Postgres async URL "
                "(postgresql+asyncpg://...)."
            )


@lru_cache
def get_settings() -> Settings:
    return Settings()
