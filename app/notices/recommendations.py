"""사용자 학과·학년·관심 태그 기반 공지 추천 API."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request
from psycopg_pool import ConnectionPool

from app.auth.router import get_current_user
from app.notices.router import PREVIEW_LENGTH

router = APIRouter(prefix="/api/recommendations", tags=["recommendations"])
RECOMMENDATION_LIMIT = 20

RECOMMENDATIONS_SQL = """
WITH RECURSIVE me AS (
    SELECT id, school_id, department_id, grade
    FROM users
    WHERE id = %s AND status = 'active'
), my_depts AS (
    SELECT d.id, d.parent_id
    FROM departments AS d
    JOIN me ON me.department_id = d.id
    UNION
    SELECT parent.id, parent.parent_id
    FROM departments AS parent
    JOIN my_depts AS child ON child.parent_id = parent.id
), eligible AS (
    SELECT n.id, n.source_id, n.category_id, n.title, n.content, n.posted_at,
           n.original_url, s.name AS source_name,
           c.name AS category_name,
           EXISTS (
               SELECT 1 FROM notice_targets AS target
               JOIN me ON target.grade IS NULL OR target.grade = me.grade
               WHERE target.notice_id = n.id
                 AND target.department_id IN (SELECT id FROM my_depts)
           ) AS department_match,
           EXISTS (
               SELECT 1 FROM notice_targets AS target
               JOIN me ON target.grade = me.grade
               WHERE target.notice_id = n.id
                 AND (target.department_id IS NULL
                      OR target.department_id IN (SELECT id FROM my_depts))
           ) AS grade_match,
           COALESCE((
               SELECT array_agg(tag.name ORDER BY tag.sort_order, tag.name)
               FROM notice_tags AS notice_tag
               JOIN user_interests AS interest
                 ON interest.tag_id = notice_tag.tag_id AND interest.user_id = %s
               JOIN tags AS tag ON tag.id = notice_tag.tag_id
               WHERE notice_tag.notice_id = n.id
           ), ARRAY[]::text[]) AS matched_interests
    FROM notices AS n
    JOIN notice_sources AS s ON s.id = n.source_id
    JOIN me ON me.school_id = s.school_id
    LEFT JOIN notice_categories AS c ON c.id = n.category_id
    WHERE n.status = 'active'
      AND (
          NOT EXISTS (
              SELECT 1 FROM notice_targets AS target WHERE target.notice_id = n.id
          )
          OR EXISTS (
              SELECT 1 FROM notice_targets AS target
              WHERE target.notice_id = n.id
                AND (target.department_id IS NULL
                     OR target.department_id IN (SELECT id FROM my_depts))
                AND (target.grade IS NULL OR target.grade = me.grade)
          )
      )
)
SELECT id, title, posted_at, category_id, category_name,
       left(content, %s) AS preview, original_url, source_name,
       (3 * department_match::int
        + 2 * grade_match::int
        + 2 * cardinality(matched_interests)) AS score,
       matched_interests, department_match, grade_match
FROM eligible
ORDER BY score DESC, posted_at DESC, id DESC
LIMIT %s
"""


def _pool(request: Request) -> ConnectionPool:
    return request.app.state.db_pool


@router.get("")
def recommended_notices(
    pool: Annotated[ConnectionPool, Depends(_pool)],
    user: Annotated[dict[str, Any], Depends(get_current_user)],
) -> dict[str, Any]:
    """사용자에게 노출 가능한 공지 중 점수가 높은 20개와 추천 이유를 반환한다."""
    with pool.connection() as connection:
        rows = connection.execute(
            RECOMMENDATIONS_SQL,
            (user["id"], user["id"], PREVIEW_LENGTH, RECOMMENDATION_LIMIT),
        ).fetchall()

    items = []
    for row in rows:
        reasons: list[str] = []
        if row[10]:
            reasons.append("내 학과 대상")
        if row[11]:
            reasons.append("내 학년 대상")
        if row[9]:
            reasons.append("관심 분야 " + ", ".join(f"‘{name}’" for name in row[9]) + " 관련")
        items.append(
            {
                "id": row[0],
                "title": row[1],
                "posted_at": row[2],
                "category_id": row[3],
                "category_name": row[4],
                "preview": row[5],
                "original_url": row[6],
                "source_name": row[7],
                "score": row[8],
                "matched_interests": row[9],
                "reasons": reasons or ["전체 공개 공지"],
            }
        )
    return {"items": items, "limit": RECOMMENDATION_LIMIT}
