"""로그인한 사용자의 학교 공지 목록과 상세 조회 API."""

from __future__ import annotations

import hashlib
import re
from datetime import datetime
from typing import Annotated, Any, Literal
from urllib.parse import parse_qs, urlsplit
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from psycopg.types.json import Jsonb
from psycopg_pool import ConnectionPool

from app.auth.router import get_current_user
from app.notices.summarize import summarize_notice
from app.tagging.rules import retag_notice

router = APIRouter(prefix="/api/notices", tags=["notices"])
PREVIEW_LENGTH = 120
SEOUL_TZ = ZoneInfo("Asia/Seoul")


class ImportedAttachment(BaseModel):
    name: str = Field(min_length=1, max_length=300)
    url: str = Field(min_length=1, max_length=2048)


class ManualNoticeImport(BaseModel):
    department: Literal["computer", "electrical"]
    post_number: str = Field(pattern=r"^\d{1,20}$")
    title: str = Field(min_length=1, max_length=500)
    author: str = Field(default="", max_length=200)
    date: str = Field(min_length=4, max_length=40)
    url: str = Field(min_length=1, max_length=2048)
    content: str = Field(min_length=1, max_length=250_000)
    attachments: list[ImportedAttachment] = Field(default_factory=list, max_length=30)


MANUAL_IMPORT_DEPARTMENTS = {
    "computer": {
        "name": "컴퓨터공학과",
        "source_name": "컴퓨터공학과 브라우저 가져오기",
        "hosts": {"computer.cbnu.ac.kr", "computer.chungbuk.ac.kr"},
    },
    "electrical": {
        "name": "전기공학부",
        "source_name": "전기공학부 브라우저 가져오기",
        "hosts": {"koamma.cbnu.ac.kr", "koamma.chungbuk.ac.kr"},
    },
}


def _pool(request: Request) -> ConnectionPool:
    return request.app.state.db_pool


def _optional_user(
    request: Request,
    pool: Annotated[ConnectionPool, Depends(_pool)],
) -> dict[str, Any] | None:
    """Use the signed-in user's school, or show public CBNU notices to guests."""
    try:
        return get_current_user(request, pool)
    except HTTPException as exc:
        if exc.status_code == status.HTTP_401_UNAUTHORIZED:
            return None
        raise


def _parse_posted_at(value: str) -> datetime:
    normalized = value.strip().replace(".", "-").replace("/", "-")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="게시일 형식을 해석할 수 없습니다.") from exc
    return parsed.replace(tzinfo=SEOUL_TZ) if parsed.tzinfo is None else parsed


def _validate_import_url(payload: ManualNoticeImport) -> str:
    rules = MANUAL_IMPORT_DEPARTMENTS[payload.department]
    parts = urlsplit(payload.url)
    params = parse_qs(parts.query)
    if (parts.scheme != "https" or (parts.hostname or "").lower() not in rules["hosts"]
            or parts.path != "/bbs/bbs.php"
            or (params.get("task") or [""])[0] != "view"
            or (params.get("db") or [""])[0] != "notice"
            or (params.get("no") or [""])[0] != payload.post_number):
        raise HTTPException(status_code=422, detail="공지 원문 주소가 학과·게시글 정보와 일치하지 않습니다.")
    for attachment in payload.attachments:
        file_url = urlsplit(attachment.url)
        if (file_url.scheme != "https" or (file_url.hostname or "").lower() != parts.hostname
                or not file_url.path.endswith("/bbs/include/download.php")):
            raise HTTPException(status_code=422, detail="첨부파일 주소가 허용된 공지 사이트와 일치하지 않습니다.")
    return payload.url


@router.post("/manual-import")
def manual_import_notice(
    payload: ManualNoticeImport,
    pool: Annotated[ConnectionPool, Depends(_pool)],
    user: Annotated[dict[str, Any], Depends(get_current_user)],
) -> dict[str, Any]:
    """현재 브라우저에서 사용자가 선택한 공지 상세를 DB에 저장한다."""
    if user["school"] != "충북대학교":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="충북대학교 계정만 공지를 가져올 수 있습니다.")
    _validate_import_url(payload)
    config = MANUAL_IMPORT_DEPARTMENTS[payload.department]
    list_url = f"manual://browser-import/{payload.department}"
    posted_at = _parse_posted_at(payload.date)
    content = payload.content.strip()
    title = payload.title.strip()
    content_hash = hashlib.sha256(f"{title}\n{content}".encode("utf-8")).hexdigest()
    parser_config = {
        "source_scope": "department",
        "target_department_name": config["name"],
        "manual_import_only": True,
    }

    with pool.connection() as connection:
        with connection.transaction():
            # If this post already came from the regular department crawler,
            # enrich that same row instead of creating a duplicate manual-import row.
            existing = connection.execute(
                """SELECT n.id, n.source_id, n.category_id
                   FROM notices n JOIN notice_sources s ON s.id=n.source_id
                   WHERE s.school_id=%s
                     AND s.parser_config->>'target_department_name'=%s
                     AND n.external_id=%s AND n.status='active'
                   ORDER BY CASE WHEN s.source_type='school_website' THEN 0 ELSE 1 END, n.id
                   LIMIT 1""",
                (user["school_id"], config["name"], payload.post_number),
            ).fetchone()
            if existing:
                source_id = existing[1]
                category_id = existing[2]
                notice_id = existing[0]
            else:
                source = connection.execute(
                    "SELECT id FROM notice_sources WHERE school_id=%s AND list_url=%s",
                    (user["school_id"], list_url),
                ).fetchone()
                if source:
                    source_id = source[0]
                else:
                    source_id = connection.execute(
                        """INSERT INTO notice_sources
                           (school_id,name,source_type,list_url,parser_config,is_active)
                           VALUES (%s,%s,'custom_url',%s,%s,FALSE) RETURNING id""",
                        (user["school_id"], config["source_name"], list_url, Jsonb(parser_config)),
                    ).fetchone()[0]
                category_id = connection.execute(
                    """INSERT INTO notice_categories (source_id,name) VALUES (%s,'브라우저 가져오기')
                       ON CONFLICT (source_id,name) DO UPDATE SET name=EXCLUDED.name RETURNING id""",
                    (source_id,),
                ).fetchone()[0]
                notice_id = None
            notice_id = connection.execute(
                """INSERT INTO notices
                   (source_id,category_id,external_id,title,author,content,summary,original_url,
                    posted_at,content_hash,status,last_seen_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'active',now())
                   ON CONFLICT (source_id,external_id) DO UPDATE SET
                     category_id=EXCLUDED.category_id,title=EXCLUDED.title,author=EXCLUDED.author,
                     content=EXCLUDED.content,summary=EXCLUDED.summary,original_url=EXCLUDED.original_url,
                     posted_at=EXCLUDED.posted_at,content_hash=EXCLUDED.content_hash,status='active',last_seen_at=now()
                RETURNING id""",
                (source_id, category_id, payload.post_number, title, payload.author.strip(), content,
                 summarize_notice(content), payload.url, posted_at, content_hash),
            ).fetchone()[0]
            connection.execute("DELETE FROM notice_attachments WHERE notice_id=%s", (notice_id,))
            for attachment in payload.attachments:
                connection.execute(
                    """INSERT INTO notice_attachments (notice_id,kind,file_name,file_url)
                       VALUES (%s,'file',%s,%s)""",
                    (notice_id, attachment.name, attachment.url),
                )
            retag_notice(
                connection, notice_id, user["school_id"], f"{title}\n{content}", title=title
            )

    return {
        "id": notice_id,
        "created": existing is None,
        "department": config["name"],
        "post_number": payload.post_number,
        "title": title,
    }


@router.get("")
def list_notices(
    pool: Annotated[ConnectionPool, Depends(_pool)],
    user: Annotated[dict[str, Any] | None, Depends(_optional_user)],
    page: Annotated[int, Query(ge=1)] = 1,
    per_page: Annotated[int, Query(ge=1, le=100)] = 20,
    category_id: Annotated[int | None, Query(gt=0)] = None,
    scope: Annotated[Literal["school", "department", "other_department"] | None, Query()] = None,
) -> dict[str, Any]:
    """공개 방문자에게 충북대 공지를, 로그인 사용자에게 소속 학교 공지를 반환한다."""
    if user is not None:
        school_id = user["school_id"]
    else:
        with pool.connection() as connection:
            school_row = connection.execute(
                "SELECT id FROM schools WHERE name = %s AND is_active",
                ("충북대학교",),
            ).fetchone()
        if school_row is None:
            return {"items": [], "total": 0, "page": page, "per_page": per_page, "pages": 0}
        school_id = school_row[0]

    where = ["s.school_id = %s", "n.status = 'active'"]
    parameters: list[Any] = [school_id]
    if scope is not None:
        where.append("COALESCE(s.parser_config->>'source_scope', 'school') = %s")
        parameters.append("department" if scope in {"department", "other_department"} else scope)
        if scope in {"department", "other_department"}:
            if user is None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="로그인 후 학과별 공지를 확인할 수 있습니다.",
                )
            else:
                is_other = scope == "other_department"
                where.append(
                    "(s.parser_config->>'target_department_name' IS DISTINCT FROM %s) = %s"
                )
                parameters.extend([user["department"], is_other])
                if is_other:
                    # The source department identifies where a notice came from;
                    # only explicit audience matches make it relevant elsewhere.
                    where.append(
                        "EXISTS (WITH RECURSIVE my_depts AS ("
                        "SELECT id, parent_id FROM departments WHERE id = %s UNION ALL "
                        "SELECT p.id, p.parent_id FROM departments p "
                        "JOIN my_depts d ON d.parent_id = p.id) "
                        "SELECT 1 FROM notice_targets t WHERE t.notice_id = n.id "
                        "AND (t.department_id IS NULL OR t.department_id IN (SELECT id FROM my_depts)) "
                        "AND (t.grade IS NULL OR t.grade = %s))"
                    )
                    parameters.extend([user["department_id"], user["grade"]])
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
                       n.original_url, s.name AS source_name, n.summary,
                       s.parser_config->>'target_department_name' AS department_name,
                       length(regexp_replace(coalesce(n.content, ''), '[[:space:]]', '', 'g')) AS content_length,
                       COALESCE((
                           SELECT array_agg(tag.name ORDER BY tag.sort_order, tag.name)
                           FROM notice_tags AS notice_tag
                           JOIN tags AS tag ON tag.id = notice_tag.tag_id AND tag.is_active
                           WHERE notice_tag.notice_id = n.id
                       ), ARRAY[]::text[]) AS tags,
                       EXISTS (
                           SELECT 1 FROM user_saved_notices AS saved
                           WHERE saved.notice_id = n.id AND saved.user_id = %s
                       ) AS is_saved
                FROM notices AS n
                JOIN notice_sources AS s ON s.id = n.source_id
                LEFT JOIN notice_categories AS c ON c.id = n.category_id
                WHERE {where_sql}
                ORDER BY n.posted_at DESC, n.id DESC
                LIMIT %s OFFSET %s""",
            [PREVIEW_LENGTH, user["id"] if user else None, *parameters, per_page, offset],
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
            "department_name": row[9],
            "content_length": row[10],
            "tags": row[11],
            "is_saved": row[12],
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


@router.get("/saved")
def list_saved_notices(
    pool: Annotated[ConnectionPool, Depends(_pool)],
    user: Annotated[dict[str, Any], Depends(get_current_user)],
) -> dict[str, Any]:
    """로그인한 사용자가 저장한 학교 공지 목록을 반환한다."""
    with pool.connection() as connection:
        rows = connection.execute(
            """SELECT n.id, n.title, n.posted_at, n.category_id,
                      c.name AS category_name, left(n.content, %s) AS preview,
                      n.original_url, s.name AS source_name, n.summary,
                      s.parser_config->>'target_department_name' AS department_name,
                      length(regexp_replace(coalesce(n.content, ''), '[[:space:]]', '', 'g')) AS content_length,
                      COALESCE((
                          SELECT array_agg(tag.name ORDER BY tag.sort_order, tag.name)
                          FROM notice_tags AS notice_tag
                          JOIN tags AS tag ON tag.id=notice_tag.tag_id AND tag.is_active
                          WHERE notice_tag.notice_id=n.id
                      ), ARRAY[]::text[]) AS tags
               FROM user_saved_notices AS saved
               JOIN notices AS n ON n.id=saved.notice_id AND n.status='active'
               JOIN notice_sources AS s ON s.id=n.source_id AND s.school_id=%s
               LEFT JOIN notice_categories AS c ON c.id=n.category_id
               WHERE saved.user_id=%s
               ORDER BY saved.saved_at DESC, n.posted_at DESC, n.id DESC
               LIMIT 200""",
            (PREVIEW_LENGTH, user["school_id"], user["id"]),
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
            "department_name": row[9],
            "content_length": row[10],
            "tags": row[11],
            "is_saved": True,
        }
        for row in rows
    ]
    return {"items": items, "total": len(items)}


@router.put("/{notice_id}/saved")
def save_notice(
    notice_id: int,
    pool: Annotated[ConnectionPool, Depends(_pool)],
    user: Annotated[dict[str, Any], Depends(get_current_user)],
) -> dict[str, Any]:
    """공지 하나를 로그인한 사용자의 저장 목록에 추가한다."""
    with pool.connection() as connection:
        with connection.transaction():
            exists = connection.execute(
                """SELECT 1 FROM notices n JOIN notice_sources s ON s.id=n.source_id
                   WHERE n.id=%s AND n.status='active' AND s.school_id=%s""",
                (notice_id, user["school_id"]),
            ).fetchone()
            if exists is None:
                raise HTTPException(status_code=404, detail="공지를 찾을 수 없습니다.")
            connection.execute(
                """INSERT INTO user_saved_notices (user_id, notice_id)
                   VALUES (%s,%s) ON CONFLICT (user_id, notice_id) DO NOTHING""",
                (user["id"], notice_id),
            )
    return {"id": notice_id, "is_saved": True}


@router.delete("/{notice_id}/saved")
def unsave_notice(
    notice_id: int,
    pool: Annotated[ConnectionPool, Depends(_pool)],
    user: Annotated[dict[str, Any], Depends(get_current_user)],
) -> dict[str, Any]:
    """로그인한 사용자의 저장 목록에서 공지를 제거한다."""
    with pool.connection() as connection:
        connection.execute(
            "DELETE FROM user_saved_notices WHERE user_id=%s AND notice_id=%s",
            (user["id"], notice_id),
        )
    return {"id": notice_id, "is_saved": False}


@router.get("/{notice_id}")
def get_notice(
    notice_id: int,
    pool: Annotated[ConnectionPool, Depends(_pool)],
    user: Annotated[dict[str, Any] | None, Depends(_optional_user)],
) -> dict[str, Any]:
    """활성 공지 상세를 반환하며, 비회원은 충북대 공지만 볼 수 있다."""
    if notice_id < 1:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="notice not found")
    if user is not None:
        school_id = user["school_id"]
    else:
        with pool.connection() as connection:
            school_row = connection.execute(
                "SELECT id FROM schools WHERE name = %s AND is_active", ("충북대학교",)
            ).fetchone()
        if school_row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="notice not found")
        school_id = school_row[0]
    with pool.connection() as connection:
        row = connection.execute(
            """SELECT n.id, n.title, n.author, n.content, n.summary, n.posted_at, n.original_url,
                      n.category_id, c.name AS category_name, s.name AS source_name
               FROM notices AS n
               JOIN notice_sources AS s ON s.id = n.source_id
               LEFT JOIN notice_categories AS c ON c.id = n.category_id
               WHERE n.id = %s AND s.school_id = %s AND n.status = 'active'""",
            (notice_id, school_id),
        ).fetchone()
        attachment_rows = connection.execute(
            "SELECT file_name, file_url FROM notice_attachments WHERE notice_id=%s ORDER BY id",
            (notice_id,),
        ).fetchall() if row is not None else []

    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="notice not found")
    return {
        "id": row[0],
        "title": row[1],
        "author": row[2],
        "content": row[3],
        "summary": row[4],
        "posted_at": row[5],
        "original_url": row[6],
        "category_id": row[7],
        "category_name": row[8],
        "source_name": row[9],
        "attachments": [{"name": item[0] or "", "url": item[1]} for item in attachment_rows],
    }
