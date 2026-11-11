"""환경변수에서 애플리케이션 설정을 읽는다."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache


@dataclass(frozen=True)
class Settings:
    database_url: str
    jwt_secret: str
    llm_provider: str
    llm_api_key: str | None
    llm_model: str
    llm_base_url: str | None
    cookie_secure: bool


@lru_cache
def get_settings() -> Settings:
    """비밀값을 포함한 설정을 환경변수에서 한 번 읽는다."""
    return Settings(
        database_url=os.environ.get(
            "DATABASE_URL",
            "postgresql://notice_notifier:local_dev_only@localhost:5432/notice_notifier",
        ),
        jwt_secret=os.environ.get("JWT_SECRET", ""),
        llm_provider=os.environ.get("LLM_PROVIDER", "anthropic"),
        llm_api_key=os.environ.get("LLM_API_KEY") or None,
        llm_model=os.environ.get("LLM_MODEL", "claude-haiku-5-5"),
        llm_base_url=os.environ.get("LLM_BASE_URL") or None,
        cookie_secure=os.environ.get("COOKIE_SECURE", "true").lower() == "true",
    )
