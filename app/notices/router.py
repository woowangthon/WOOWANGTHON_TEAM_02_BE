"""로그인한 사용자의 학교 공지 목록과 상세 조회 API."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from psycopg_pool import ConnectionPool

from app.auth.router import get_current_user

router = APIRouter(prefix="/api/notices", tags=["notices"])
PREVIEW_LENGTH = 120


def _pool(request: Request) -> ConnectionPool:
    return request.app.state.db_pool


@router.get("")
def list_notices(
    pool: Annotated[ConnectionPool, Depends(_pool)],
    user: Annotated[dict[str, Any], Depends(get_current_user)],
    page: Annotated[int, Query(ge=1)] = 1,
    per_page: Annotated[int, Query(ge=1, le=100)] = 20,
    category_id: Annotated[int | None, Query(gt=0)] = None,
    scope: Annotated[Literal["school", "department"] | None, Query()] = None,
) -> dict[str, Any]:
    """내 학교의 활성 공지를 최신순으로 페이지네이션해 반환한다."""
    where = ["s.school_id = %s", "n.status = 'active'"]
    parameters: list[Any] = [user["school_id"]]
    if scope is not None:
        where.append("COALESCE(s.parser_config->>'source_scope', 'school') = %s")
        parameters.append(scope)
    if category_id is not None:
        where.append("n.category_id = %s")
        parameters.append(category_id)
    where_sql = " AND ".join(where)
    offset = (page - 1) * per_page

    with pool.connection() as connection:
        total = connection.execute(
            f"""SELECT count(*)
                FROM notices AS n
                JOIN notice_sources AS s ON s.id = n.source_id
                WHERE {where_sql}""",
            parameters,
        ).fetchone()[0]
        rows = connection.execute(
            f"""SELECT n.id, n.title, n.posted_at, n.category_id,
                       c.name AS category_name, left(n.content, %s) AS preview,
                       n.original_url, s.name AS source_name, n.summary
                FROM notices AS n
                JOIN notice_sources AS s ON s.id = n.source_id
                LEFT JOIN notice_categories AS c ON c.id = n.category_id
                WHERE {where_sql}
                ORDER BY n.posted_at DESC, n.id DESC
                LIMIT %s OFFSET %s""",
            [PREVIEW_LENGTH, *parameters, per_page, offset],
        ).fetchall()

    items = [
        {
            "id": row[0],
            "title": row[1],
            "posted_at": row[2],
            "category_id": row[3],
            "category_name": row[4],
            "preview": row[5],
            "original_url": row[6],
            "source_name": row[7],
            "summary": row[8],
        }
        for row in rows
    ]
    return {
        "items": items,
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": (total + per_page - 1) // per_page,
    }


@router.get("/{notice_id}")
def get_notice(
    notice_id: int,
    pool: Annotated[ConnectionPool, Depends(_pool)],
    user: Annotated[dict[str, Any], Depends(get_current_user)],
) -> dict[str, Any]:
    """내 학교의 활성 공지 상세를 반환한다."""
    if notice_id < 1:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="notice not found")
    with pool.connection() as connection:
        row = connection.execute(
            """SELECT n.id, n.title, n.content, n.summary, n.posted_at, n.original_url,
                      n.category_id, c.name AS category_name, s.name AS source_name
               FROM notices AS n
               JOIN notice_sources AS s ON s.id = n.source_id
               LEFT JOIN notice_categories AS c ON c.id = n.category_id
               WHERE n.id = %s AND s.school_id = %s AND n.status = 'active'""",
            (notice_id, user["school_id"]),
        ).fetchone()

    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="notice not found")
    return {
        "id": row[0],
        "title": row[1],
        "content": row[2],
        "summary": row[3],
        "posted_at": row[4],
        "original_url": row[5],
        "category_id": row[6],
        "category_name": row[7],
        "source_name": row[8],
    }
