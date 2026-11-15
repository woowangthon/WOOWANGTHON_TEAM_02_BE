"""독립 AI 서비스에 답변·요약·selector 제안을 요청하는 내부 HTTP 클라이언트."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

import httpx

from app.chatbot.candidates import NoticeCandidate
from app.config import Settings, get_settings

AI_TIMEOUT_SECONDS = 60.0


class AIServiceError(RuntimeError):
    """AI 서비스 요청 또는 응답에 실패했다."""


class AIServiceClient:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    @property
    def is_configured(self) -> bool:
        return bool(self.settings.ai_service_url and self.settings.ai_service_token)

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        if not self.is_configured:
            raise AIServiceError("AI_SERVICE_URL과 AI_SERVICE_TOKEN을 설정해야 합니다.")
        try:
            response = httpx.post(
                f"{self.settings.ai_service_url.rstrip('/')}{path}",
                json=payload,
                headers={"X-AI-Service-Token": self.settings.ai_service_token or ""},
                timeout=AI_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            result = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise AIServiceError("AI 서비스 요청에 실패했습니다.") from exc
        if not isinstance(result, dict):
            raise AIServiceError("AI 서비스 응답 형식이 올바르지 않습니다.")
        return result

    @staticmethod
    def _evidence(candidate: NoticeCandidate) -> dict[str, str]:
        posted_at = candidate.posted_at
        if isinstance(posted_at, (datetime, date)):
            posted_at = posted_at.isoformat()
        return {
            "id": str(candidate.notice_id),
            "title": candidate.title,
            "content": candidate.content[:20_000],
            "source": candidate.source_name,
            "posted_at": str(posted_at or ""),
            "url": candidate.original_url,
        }

    def answer(self, question: str, candidates: list[NoticeCandidate]) -> str:
        result = self._post(
            "/v1/answer",
            {"question": question, "evidence": [self._evidence(item) for item in candidates[:5]]},
        )
        answer = result.get("answer")
        if not isinstance(answer, str) or not answer.strip():
            raise AIServiceError("AI 서비스가 빈 답변을 반환했습니다.")
        return answer.strip()

    def summarize(self, candidate: NoticeCandidate) -> str:
        result = self._post("/v1/summarize", {"notice": self._evidence(candidate)})
        summary = result.get("summary")
        if not isinstance(summary, str) or not summary.strip():
            raise AIServiceError("AI 서비스가 빈 요약을 반환했습니다.")
        return summary.strip()

    def suggest_parser(self, html: str) -> dict[str, Any]:
        result = self._post("/v1/suggest-parser", {"html": html[:20_000]})
        config = result.get("config")
        if not isinstance(config, dict):
            raise AIServiceError("AI 서비스가 올바르지 않은 selector 설정을 반환했습니다.")
        return config


def is_ai_service_configured(settings: Settings | None = None) -> bool:
    return AIServiceClient(settings).is_configured
