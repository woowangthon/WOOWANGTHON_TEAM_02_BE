"""환경변수에서 애플리케이션 설정을 읽는다."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache


@dataclass(frozen=True)
class Settings:
    database_url: str
    jwt_secret: str
    ai_service_url: str
    ai_service_token: str | None
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
        ai_service_url=os.environ.get("AI_SERVICE_URL", "http://host.docker.internal:8001"),
        ai_service_token=os.environ.get("AI_SERVICE_TOKEN") or None,
        cookie_secure=os.environ.get("COOKIE_SECURE", "true").lower() == "true",
    )
