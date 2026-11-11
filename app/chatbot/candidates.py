"""로그인 사용자의 학교 안에서 챗봇 답변 후보 공지를 선별한다."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import psycopg

MAX_CANDIDATES = 5

CANDIDATES_SQL = """
WITH input AS (
    SELECT %s::text AS question
), me AS (
    SELECT id, school_id
    FROM users
    WHERE id = %s AND status = 'active'
), tag_matches AS (
    SELECT nt.notice_id,
           array_agg(DISTINCT tag.name ORDER BY tag.name) AS matched_tags,
           sum(keyword.weight)::real / 10.0 AS keyword_score
    FROM tag_keywords AS keyword
    JOIN tags AS tag ON tag.id = keyword.tag_id AND tag.is_active
    JOIN notice_tags AS nt ON nt.tag_id = tag.id
    JOIN notices AS n ON n.id = nt.notice_id AND n.status = 'active'
    JOIN notice_sources AS source ON source.id = n.source_id
    JOIN me ON me.school_id = source.school_id
    CROSS JOIN input
    WHERE position(lower(keyword.keyword) IN lower(input.question)) > 0
    GROUP BY nt.notice_id
), text_matches AS (
    SELECT n.id AS notice_id,
           greatest(similarity(n.title, input.question),
                    similarity(n.content, input.question)) AS text_score
    FROM notices AS n
    JOIN notice_sources AS source ON source.id = n.source_id
    JOIN me ON me.school_id = source.school_id
    CROSS JOIN input
    WHERE n.status = 'active'
      AND (
          n.title % input.question OR n.content % input.question
          OR position(lower(input.question) IN lower(n.title)) > 0
          OR position(lower(input.question) IN lower(n.content)) > 0
      )
), candidate_ids AS (
    SELECT notice_id FROM tag_matches
    UNION
    SELECT notice_id FROM text_matches
)
SELECT n.id, n.title, n.content, n.posted_at, n.original_url,
       coalesce(category.name, ''), source.name,
       coalesce(tag_matches.matched_tags, ARRAY[]::text[]),
       coalesce(tag_matches.keyword_score, 0) + coalesce(text_matches.text_score, 0)
FROM candidate_ids
JOIN notices AS n ON n.id = candidate_ids.notice_id AND n.status = 'active'
JOIN notice_sources AS source ON source.id = n.source_id
JOIN me ON me.school_id = source.school_id
LEFT JOIN notice_categories AS category ON category.id = n.category_id
LEFT JOIN tag_matches ON tag_matches.notice_id = n.id
LEFT JOIN text_matches ON text_matches.notice_id = n.id
ORDER BY 9 DESC, n.posted_at DESC, n.id DESC
LIMIT %s
"""


@dataclass(frozen=True)
class NoticeCandidate:
    """챗봇에 전달할 공지 근거와 선별 정보를 표현한다."""

    notice_id: int
    title: str
    content: str
    posted_at: Any
    original_url: str
    category_name: str | None
    source_name: str
    matched_tags: tuple[str, ...]
    relevance_score: float


def select_candidates(
    connection: psycopg.Connection[Any], user_id: int, question: str
) -> list[NoticeCandidate]:
    """질문에 맞는 내 학교 공지를 태그·trigram으로 최대 5건 선택한다."""
    normalized_question = question.strip()
    if not normalized_question:
        return []
    rows = connection.execute(
        CANDIDATES_SQL,
        (normalized_question, user_id, MAX_CANDIDATES),
    ).fetchall()
    return [
        NoticeCandidate(
            notice_id=row[0],
            title=row[1],
            content=row[2],
            posted_at=row[3],
            original_url=row[4],
            category_name=row[5] or None,
            source_name=row[6],
            matched_tags=tuple(row[7]),
            relevance_score=float(row[8]),
        )
        for row in rows
    ]
