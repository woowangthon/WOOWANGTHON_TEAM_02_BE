"""공지 접근 권한과 근거 선별을 담당하는 채팅·요약 API."""

from __future__ import annotations

import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from psycopg_pool import ConnectionPool

from app.auth.router import get_current_user
from app.chatbot.ai_service import AIServiceClient, AIServiceError, is_ai_service_configured
from app.chatbot.candidates import NoticeCandidate, select_candidates

router = APIRouter(prefix="/api/assistant", tags=["notice assistant"])
logger = logging.getLogger(__name__)


class ChatRequest(BaseModel):
    question: str = Field(min_length=2, max_length=500)


def _pool(request: Request) -> ConnectionPool:
    return request.app.state.db_pool


def _public_candidate(candidate: NoticeCandidate) -> dict[str, Any]:
    posted_at = candidate.posted_at
    if hasattr(posted_at, "isoformat"):
        posted_at = posted_at.isoformat()
    return {
        "id": candidate.notice_id,
        "title": candidate.title,
        "posted_at": posted_at,
        "source_name": candidate.source_name,
        "original_url": candidate.original_url,
        "preview": candidate.content[:240],
    }


@router.post("/chat")
def ask_notices(
    payload: ChatRequest,
    request: Request,
    user: Annotated[dict[str, Any], Depends(get_current_user)],
    pool: Annotated[ConnectionPool, Depends(_pool)],
) -> dict[str, Any]:
    question = payload.question.strip()
    if len(question) < 2:
        raise HTTPException(status_code=422, detail="질문을 두 글자 이상 입력해 주세요.")
    with pool.connection() as connection:
        candidates = select_candidates(connection, user["id"], question)

    if not candidates:
        return {
            "answer": "질문과 관련된 공지를 찾지 못했어요. 장학금, 수강, 행사처럼 주제를 조금 더 구체적으로 적어 주세요.",
            "notices": [], "ai_enabled": False, "ai_failed": False, "no_matches": True,
        }

    configured = is_ai_service_configured()
    ai_enabled = configured
    ai_failed = False
    answer = "관련 공지를 찾았어요. 아래 공지의 제목과 미리보기를 확인해 주세요. 공지를 누르면 상세 내용을 확인할 수 있습니다."
    if configured:
        try:
            answer = AIServiceClient().answer(question, candidates)
        except AIServiceError:
            logger.exception("Notice assistant AI service request failed")
            answer = "공지 검색은 완료했지만 AI 답변을 만들지 못했어요. 아래 관련 공지를 확인해 주세요."
            ai_enabled = False
            ai_failed = True
    return {
        "answer": answer,
        "notices": [_public_candidate(item) for item in candidates],
        "ai_enabled": ai_enabled,
        "ai_failed": ai_failed,
        "no_matches": False,
    }


@router.post("/notices/{notice_id}/summary")
def summarize_notice(
    notice_id: int,
    request: Request,
    user: Annotated[dict[str, Any], Depends(get_current_user)],
    pool: Annotated[ConnectionPool, Depends(_pool)],
) -> dict[str, Any]:
    if not is_ai_service_configured():
        raise HTTPException(status_code=503, detail="AI 요약 서비스를 설정한 뒤 사용할 수 있습니다.")
    with pool.connection() as connection:
        row = connection.execute(
            """SELECT n.id, n.title, n.content, n.posted_at, n.original_url,
                      c.name, s.name
               FROM notices n JOIN notice_sources s ON s.id = n.source_id
               LEFT JOIN notice_categories c ON c.id = n.category_id
               WHERE n.id = %s AND n.status = 'active' AND s.school_id = %s""",
            (notice_id, user["school_id"]),
        ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="공지 내용을 찾을 수 없습니다.")
    candidate = NoticeCandidate(
        notice_id=row[0], title=row[1], content=row[2], posted_at=row[3],
        original_url=row[4], category_name=row[5], source_name=row[6],
        matched_tags=(), relevance_score=1.0,
    )
    try:
        summary = AIServiceClient().summarize(candidate)
    except AIServiceError as exc:
        logger.exception("Notice summary AI service request failed")
        raise HTTPException(status_code=503, detail="AI 요약을 만들지 못했습니다. 잠시 후 다시 시도해 주세요.") from exc
    return {"summary": summary, "summary_type": "ai"}
