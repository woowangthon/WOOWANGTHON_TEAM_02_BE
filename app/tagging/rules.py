"""공지 제목·본문에서 관심 태그와 대상 학과·학년을 규칙으로 찾는다."""

from __future__ import annotations

import re

from psycopg import Connection

GRADE_PATTERN = re.compile(r"(?<!\d)([1-6])\s*학년")
ALL_DEPARTMENTS_PATTERN = re.compile(
    r"(?:전체|전|모든)\s*학과|타\s*학과|타학과|전교생|재학생\s*전체"
)


def retag_notice(
    connection: Connection,
    notice_id: int,
    school_id: int,
    text: str,
    target_department_name: str | None = None,
    title: str | None = None,
) -> None:
    """공지의 기존 규칙 태그·대상을 지우고 현재 텍스트 기준으로 다시 만든다."""
    corpus = text.casefold()
    title_corpus = (title or "").casefold()
    scholarship_title = any(
        marker in title_corpus for marker in ("장학", "장학생", "장학금")
    )
    connection.execute(
        "DELETE FROM notice_tags WHERE notice_id = %s AND origin = 'rule'",
        (notice_id,),
    )
    connection.execute(
        "DELETE FROM notice_targets WHERE notice_id = %s AND origin = 'rule'",
        (notice_id,),
    )

    keyword_rows = connection.execute(
        """
        SELECT t.id, t.code, k.keyword
        FROM tags AS t
        JOIN tag_keywords AS k ON k.tag_id = t.id
        WHERE t.is_active
        """
    ).fetchall()
    matched_tag_ids = {
        tag_id
        for tag_id, code, keyword in keyword_rows
        if keyword.casefold() in corpus
        and not (
            code == "contest"
            and scholarship_title
            and keyword.casefold() not in title_corpus
        )
    }
    if matched_tag_ids:
        with connection.cursor() as cursor:
            cursor.executemany(
                """
                INSERT INTO notice_tags (notice_id, tag_id, origin)
                VALUES (%s, %s, 'rule')
                ON CONFLICT DO NOTHING
                """,
                [(notice_id, tag_id) for tag_id in matched_tag_ids],
            )

    department_rows = connection.execute(
        "SELECT id, name FROM departments WHERE school_id = %s",
        (school_id,),
    ).fetchall()
    matched_department_ids = {
        department_id
        for department_id, name in department_rows
        if name and name.casefold() in corpus
    }
    if ALL_DEPARTMENTS_PATTERN.search(corpus):
        matched_department_ids.update(department_id for department_id, _ in department_rows)
    # A source's department is its origin, not the notice's eligibility.
    # Only names actually present in the notice body/title become audience tags.
    if matched_department_ids:
        with connection.cursor() as cursor:
            cursor.executemany(
                """
                INSERT INTO notice_targets (notice_id, department_id, origin)
                VALUES (%s, %s, 'rule')
                ON CONFLICT DO NOTHING
                """,
                [(notice_id, department_id) for department_id in matched_department_ids],
            )

    matched_grades = {int(match) for match in GRADE_PATTERN.findall(corpus)}
    if matched_grades:
        with connection.cursor() as cursor:
            cursor.executemany(
                """
                INSERT INTO notice_targets (notice_id, grade, origin)
                VALUES (%s, %s, 'rule')
                ON CONFLICT DO NOTHING
                """,
                [(notice_id, grade) for grade in matched_grades],
            )
