"""Application settings."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

_BACKEND_DIR = Path(__file__).resolve().parents[1]
load_dotenv(_BACKEND_DIR / ".env")
load_dotenv(_BACKEND_DIR.parent / ".env")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Local default: Docker Postgres on localhost (see backend/.env)
    database_url: str = "postgresql+psycopg://fss:fss%40123@localhost:5432/debating"
    # Cloud: set DATABASE_URL in .env to Supabase pooler/direct URL (see .env.example)

    cors_origins: str = "http://localhost:5173,http://localhost:3000"
    # Cloud: set CORS_ORIGIN_REGEX=https://.*\.vercel\.app in .env for Vercel previews
    cors_origin_regex: str | None = None
    default_max_turns: int = 25
    api_prefix: str = "/api"
    use_mock_llm: bool = False

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def repo_root(self) -> Path:
        return Path(__file__).resolve().parents[2]

    @property
    def seeded_data_dir(self) -> Path:
        return self.repo_root / "data" / "seeded"


@lru_cache
def get_settings() -> Settings:
    return Settings()
