"""robots.txt를 확인하고 설정된 게시판을 한 차례 수집하는 CLI."""

from __future__ import annotations

import argparse
import hashlib
import os
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urljoin, urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser

import httpx
import psycopg

from app.crawler.parser import (
    NoticeSummary,
    parse_next_page_url,
    parse_notice_content,
    parse_notice_list,
)
from app.tagging.rules import retag_notice
from app.notices.summarize import summarize_notice

USER_AGENT = "NoticeNotifierBot/0.1 (university notice aggregator)"
MIN_REQUEST_INTERVAL_SECONDS = 1.0
MAX_HTML_BYTES = 5 * 1024 * 1024


class CrawlError(RuntimeError):
    """수집을 안전하게 진행할 수 없다."""


@dataclass(frozen=True)
class FetchedNotice:
    summary: NoticeSummary
    content: str


class PoliteFetcher:
    """User-Agent, 사이트 robots 규칙, 요청 간격을 적용하는 HTTP fetcher."""

    def __init__(self, client: httpx.Client) -> None:
        self.client = client
        self.last_request_at: float | None = None

    def get(self, url: str, expected_origin: tuple[str, str, int]) -> httpx.Response:
        current_url = _validate_http_url(url)
        for _ in range(6):
            if _origin(current_url) != expected_origin:
                raise CrawlError("사이트 바깥으로 이동하는 URL은 수집하지 않습니다.")
            self._wait_for_slot()
            self.last_request_at = time.monotonic()
            response = self.client.get(current_url, follow_redirects=False)
            if response.is_redirect:
                location = response.headers.get("location")
                if not location:
                    raise CrawlError("리다이렉트에 Location이 없습니다.")
                current_url = _validate_http_url(urljoin(current_url, location))
                continue
            if 300 <= response.status_code < 400:
                raise CrawlError("지원하지 않는 HTTP 리다이렉트입니다.")
            response.raise_for_status()
            if len(response.content) > MAX_HTML_BYTES:
                raise CrawlError("HTML 응답이 5 MiB 제한을 넘었습니다.")
            return response
        raise CrawlError("리다이렉트 횟수 제한을 넘었습니다.")

    def _wait_for_slot(self) -> None:
        if self.last_request_at is None:
            return
        elapsed = time.monotonic() - self.last_request_at
        remaining = MIN_REQUEST_INTERVAL_SECONDS - elapsed
        if remaining > 0:
            time.sleep(remaining)


def _validate_http_url(url: str) -> str:
    parts = urlsplit(url)
    if parts.scheme not in {"http", "https"} or not parts.hostname:
        raise CrawlError("수집 URL은 http 또는 https 주소여야 합니다.")
    if parts.username or parts.password:
        raise CrawlError("인증 정보가 포함된 URL은 수집할 수 없습니다.")
    return url


def _origin(url: str) -> tuple[str, str, int]:
    parts = urlsplit(url)
    try:
        scheme = parts.scheme.lower()
        port = parts.port
        if port is None:
            port = 443 if scheme == "https" else 80
        return (scheme, (parts.hostname or "").lower(), port)
    except ValueError as exc:
        raise CrawlError("유효하지 않은 포트가 포함된 URL입니다.") from exc


def _load_robots(
    fetcher: PoliteFetcher,
    list_url: str,
    expected_origin: tuple[str, str, int],
) -> RobotFileParser:
    parts = urlsplit(list_url)
    robots_url = urlunsplit((parts.scheme, parts.netloc, "/robots.txt", "", ""))
    parser = RobotFileParser(robots_url)
    try:
        response = fetcher.get(robots_url, expected_origin)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            parser.parse([])
            return parser
        raise CrawlError("robots.txt를 확인할 수 없어 수집을 중단했습니다.") from exc
    parser.parse(response.text.splitlines())
    return parser


def _load_source(
    connection: psycopg.Connection[Any],
    source_id: int | None,
) -> list[tuple[Any, ...]]:
    cursor = connection.execute(
        """
        SELECT id, school_id, list_url, parser_config, source_type
        FROM notice_sources
        WHERE is_active
          AND source_type = 'school_website'
          AND (last_crawled_at IS NULL
               OR last_crawled_at <= now() - make_interval(mins => crawl_interval_minutes))
          AND id = COALESCE(%s::bigint, id)
        ORDER BY id
        """,
        (source_id,),
    )
    return cursor.fetchall()


def _store_run_failure(
    connection: psycopg.Connection[Any], run_id: int, source_id: int, error: Exception
) -> None:
    # DB에는 요청 URL이나 응답 본문을 남기지 않고 예외 종류만 기록한다.
    error_message = f"{type(error).__name__}: 수집 실패"
    with connection.transaction():
        connection.execute(
            """
            UPDATE crawl_runs
            SET finished_at = now(), status = 'failed', error_message = %s
            WHERE id = %s
            """,
            (error_message, run_id),
        )
        connection.execute(
            "UPDATE notice_sources SET last_crawled_at = now() WHERE id = %s",
            (source_id,),
        )


def _fetch_notices(
    fetcher: PoliteFetcher,
    robots: RobotFileParser,
    list_url: str,
    parser_config: dict[str, Any],
) -> tuple[list[FetchedNotice], int, bool]:
    expected_origin = _origin(list_url)
    next_selector = parser_config.get("next_page_selector")
    if next_selector is not None and not isinstance(next_selector, str):
        raise CrawlError("next_page_selector는 문자열이어야 합니다.")
    max_pages = parser_config.get("max_pages", 1)
    if isinstance(max_pages, bool) or not isinstance(max_pages, int) or not 1 <= max_pages <= 100:
        raise CrawlError("max_pages는 1부터 100 사이 정수여야 합니다.")

    current_url = list_url
    summary_by_id: dict[str, NoticeSummary] = {}
    visited_pages = {current_url}
    snapshot_complete = False
    for page_number in range(max_pages):
        if not robots.can_fetch(USER_AGENT, current_url):
            raise CrawlError("robots.txt가 목록 URL 수집을 허용하지 않습니다.")
        response = fetcher.get(current_url, expected_origin)
        page_summaries = parse_notice_list(response.text, current_url, parser_config)
        for summary in page_summaries:
            summary_by_id.setdefault(summary.external_id, summary)

        if not next_selector:
            snapshot_complete = True
            break
        next_url = parse_next_page_url(response.text, current_url, next_selector)
        if next_url is None:
            snapshot_complete = True
            break
        if _origin(next_url) != expected_origin:
            raise CrawlError("다른 사이트로 이어지는 페이지는 수집하지 않습니다.")
        if next_url in visited_pages:
            raise CrawlError("페이지네이션 링크가 이미 방문한 페이지를 가리킵니다.")
        if page_number == max_pages - 1:
            break
        current_url = next_url
        visited_pages.add(current_url)

    summaries = list(summary_by_id.values())
    content_selector = parser_config.get("content_selector")
    if not isinstance(content_selector, str) or not content_selector.strip():
        return [FetchedNotice(summary, "") for summary in summaries], 0, snapshot_complete

    results: list[FetchedNotice] = []
    detail_failures = 0
    for summary in summaries:
        if _origin(summary.original_url) != expected_origin:
            detail_failures += 1
            results.append(FetchedNotice(summary, ""))
            continue
        if not robots.can_fetch(USER_AGENT, summary.original_url):
            detail_failures += 1
            results.append(FetchedNotice(summary, ""))
            continue
        try:
            detail_response = fetcher.get(summary.original_url, expected_origin)
            content = parse_notice_content(detail_response.text, content_selector)
        except (httpx.HTTPError, CrawlError, ValueError):
            detail_failures += 1
            content = ""
        results.append(FetchedNotice(summary, content))
    return results, detail_failures, snapshot_complete


def _save_notices(
    connection: psycopg.Connection[Any],
    source_id: int,
    school_id: int,
    parser_config: dict[str, Any],
    notices: list[FetchedNotice],
    snapshot_complete: bool,
) -> tuple[int, int]:
    category_ids = {
        name: category_id
        for category_id, name in connection.execute(
            "SELECT id, name FROM notice_categories WHERE source_id = %s",
            (source_id,),
        ).fetchall()
    }
    new_count = 0
    updated_count = 0
    external_ids: list[str] = []

    for fetched in notices:
        summary = fetched.summary
        external_ids.append(summary.external_id)
        content_hash = hashlib.sha256(
            f"{summary.title}\n{fetched.content}".encode("utf-8")
        ).hexdigest()
        existing = connection.execute(
            "SELECT content_hash, status FROM notices WHERE source_id = %s AND external_id = %s",
            (source_id, summary.external_id),
        ).fetchone()
        changed = existing is None or existing[0] != content_hash
        reactivated = existing is not None and existing[1] != "active"
        if existing is None:
            new_count += 1
        elif changed or reactivated:
            updated_count += 1

        notice_id = connection.execute(
            """
            INSERT INTO notices (
                source_id, category_id, external_id, title, content, summary,
                original_url, posted_at, content_hash, status, last_seen_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'active', now())
            ON CONFLICT (source_id, external_id) DO UPDATE SET
                category_id = EXCLUDED.category_id,
                title = EXCLUDED.title,
                content = EXCLUDED.content,
                summary = EXCLUDED.summary,
                original_url = EXCLUDED.original_url,
                posted_at = EXCLUDED.posted_at,
                content_hash = EXCLUDED.content_hash,
                status = 'active',
                last_seen_at = now()
            RETURNING id
            """,
            (
                source_id,
                category_ids.get(summary.category_name),
                summary.external_id,
                summary.title,
                fetched.content,
                summarize_notice(fetched.content),
                summary.original_url,
                summary.posted_at,
                content_hash,
            ),
        ).fetchone()[0]

        if changed:
            retag_notice(
                connection,
                notice_id,
                school_id,
                f"{summary.title}\n{fetched.content}",
                parser_config.get("target_department_name"),
            )

    if parser_config.get("complete_snapshot") is True and snapshot_complete and external_ids:
        connection.execute(
            """
            UPDATE notices
            SET status = 'removed'
            WHERE source_id = %s AND status = 'active' AND external_id <> ALL(%s)
            """,
            (source_id, external_ids),
        )

    return new_count, updated_count


def _crawl_source(
    connection: psycopg.Connection[Any],
    fetcher: PoliteFetcher,
    source: tuple[Any, ...],
) -> None:
    source_id, school_id, list_url, parser_config, _source_type = source
    run_id = connection.execute(
        "INSERT INTO crawl_runs (source_id) VALUES (%s) RETURNING id",
        (source_id,),
    ).fetchone()[0]
    connection.commit()

    try:
        if not isinstance(parser_config, dict):
            raise CrawlError("parser_config이 JSON object가 아닙니다.")
        # This operator-directed feature is limited to public pages permitted by robots.txt.
        public_content_pilot = parser_config.get("operator_directed_public_content") is True
        if parser_config.get("terms_checked") is not True and not public_content_pilot:
            raise CrawlError("사이트 이용약관을 확인한 출처만 수집할 수 있습니다.")

        expected_origin = _origin(list_url)
        robots = _load_robots(fetcher, list_url, expected_origin)
        notices, detail_failures, snapshot_complete = _fetch_notices(
            fetcher,
            robots,
            list_url,
            parser_config,
        )

        with connection.transaction():
            new_count, updated_count = _save_notices(
                connection,
                source_id,
                school_id,
                parser_config,
                notices,
                snapshot_complete,
            )
            list_truncated = bool(parser_config.get("next_page_selector")) and not snapshot_complete
            status_value = "partial" if detail_failures or list_truncated else "success"
            warnings = []
            if detail_failures:
                warnings.append(f"상세 본문 실패 {detail_failures}건")
            if list_truncated:
                warnings.append("max_pages에 도달해 목록이 일부만 수집됨")
            error_message = "; ".join(warnings) or None
            connection.execute(
                """
                UPDATE crawl_runs
                SET finished_at = now(), status = %s, fetched_count = %s,
                    new_count = %s, updated_count = %s, error_message = %s
                WHERE id = %s
                """,
                (status_value, len(notices), new_count, updated_count, error_message, run_id),
            )
            connection.execute(
                "UPDATE notice_sources SET last_crawled_at = now() WHERE id = %s",
                (source_id,),
            )
        print(
            f"source_id={source_id} status={status_value} fetched={len(notices)} "
            f"new={new_count} updated={updated_count} detail_errors={detail_failures}"
        )
    except Exception as exc:
        _store_run_failure(connection, run_id, source_id, exc)
        print(f"source_id={source_id} status=failed error={type(exc).__name__}")


def run(source_id: int | None = None) -> None:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL 환경변수가 설정되지 않았습니다.")

    with httpx.Client(
        timeout=20,
        headers={"User-Agent": USER_AGENT},
        follow_redirects=False,
    ) as client, psycopg.connect(database_url) as connection:
        fetcher = PoliteFetcher(client)
        sources = _load_source(connection, source_id)
        connection.commit()
        if not sources:
            print("수집할 활성 출처가 없습니다.")
            return
        for source in sources:
            _crawl_source(connection, fetcher, source)


def main() -> None:
    parser = argparse.ArgumentParser(description="등록된 공지 출처를 한 차례 수집합니다.")
    parser.add_argument("--source-id", type=int, help="특정 공지 출처 ID만 수집")
    args = parser.parse_args()
    run(args.source_id)


if __name__ == "__main__":
    main()
