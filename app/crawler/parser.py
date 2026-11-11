"""CSS 선택자로 공지 목록 HTML을 파싱한다.

parser_config 필드: item_selector, title_selector, link_selector, date_selector.
선택 필드: id_attribute, id_selector, id_query_parameter, date_attribute,
category_selector, content_selector,
next_page_selector, max_pages, terms_checked, complete_snapshot.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import parse_qs, urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup, Tag

SEOUL_TZ = timezone(timedelta(hours=9), name="KST")
DATE_FORMATS = (
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%Y-%m-%d",
    "%Y. %m. %d. %H:%M:%S",
    "%Y. %m. %d. %H:%M",
    "%Y. %m. %d.",
    "%Y.%m.%d. %H:%M",
    "%Y.%m.%d.",
    "%Y.%m.%d",
    "%Y/%m/%d %H:%M",
    "%Y/%m/%d",
    "%Y%m%d",
)


class ParseError(ValueError):
    """필수 selector 또는 공지 필드를 해석할 수 없다."""


@dataclass(frozen=True)
class NoticeSummary:
    external_id: str
    title: str
    original_url: str
    posted_at: datetime
    category_name: str | None


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _select_one(element: Tag | BeautifulSoup, selector: str, field: str) -> Tag | None:
    try:
        return element.select_one(selector)
    except Exception as exc:
        raise ParseError(f"잘못된 CSS selector: {field}") from exc


def _posted_at(value: str) -> datetime:
    normalized = _clean_text(value)
    iso_value = normalized[:-1] + "+00:00" if normalized.endswith("Z") else normalized
    try:
        parsed = datetime.fromisoformat(iso_value)
    except ValueError:
        parsed = None

    if parsed is None:
        for date_format in DATE_FORMATS:
            try:
                parsed = datetime.strptime(normalized, date_format)
                break
            except ValueError:
                continue

    if parsed is None:
        raise ParseError("게시일 형식을 해석할 수 없습니다.")
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=SEOUL_TZ)
    return parsed


def parse_notice_list(
    html: str,
    list_url: str,
    parser_config: dict[str, Any],
) -> list[NoticeSummary]:
    """목록 HTML에서 제목, 원문 링크, 게시일과 분류를 추출한다."""
    item_selector = parser_config.get("item_selector")
    link_selector = parser_config.get("link_selector")
    date_selector = parser_config.get("date_selector")
    title_selector = parser_config.get("title_selector") or link_selector
    required_selectors = (item_selector, link_selector, date_selector)
    if not all(isinstance(value, str) and value.strip() for value in required_selectors):
        raise ParseError("item_selector, link_selector, date_selector를 설정해야 합니다.")

    soup = BeautifulSoup(html, "html.parser")
    try:
        items = soup.select(item_selector)
    except Exception as exc:
        raise ParseError("잘못된 CSS selector: item_selector") from exc
    if not items:
        raise ParseError("item_selector와 일치하는 공지 행이 없습니다.")

    id_attribute = parser_config.get("id_attribute")
    id_selector = parser_config.get("id_selector")
    id_query_parameter = parser_config.get("id_query_parameter")
    date_attribute = parser_config.get("date_attribute")
    category_selector = parser_config.get("category_selector")
    notices: list[NoticeSummary] = []
    seen_ids: set[str] = set()

    for index, item in enumerate(items, start=1):
        link = _select_one(item, link_selector, "link_selector")
        title_node = _select_one(item, title_selector, "title_selector")
        date_node = _select_one(item, date_selector, "date_selector")
        if link is None or title_node is None or date_node is None:
            raise ParseError(f"{index}번째 공지에서 제목·링크·게시일을 찾지 못했습니다.")

        title = _clean_text(title_node.get_text(" ", strip=True))
        href = link.get("href")
        if not title or not isinstance(href, str) or not href.strip():
            raise ParseError(f"{index}번째 공지의 제목 또는 링크가 비어 있습니다.")
        original_url = urljoin(list_url, href.strip())
        parsed_url = urlsplit(original_url)
        # Some CBNU links carry a per-session JSESSIONID in the path. It is
        # unnecessary for the public notice URL and must not become its ID.
        clean_path = re.sub(r";JSESSIONID=[^/?;]+", "", parsed_url.path, flags=re.IGNORECASE)
        original_url = urlunsplit(
            (parsed_url.scheme, parsed_url.netloc, clean_path, parsed_url.query, parsed_url.fragment)
        )
        try:
            url_parts = urlsplit(original_url)
            valid_http_url = (
                url_parts.scheme in {"http", "https"}
                and bool(url_parts.hostname)
                and not url_parts.username
                and not url_parts.password
            )
            _ = url_parts.port
        except ValueError:
            valid_http_url = False
        if not valid_http_url:
            raise ParseError(f"{index}번째 공지의 원문 링크가 올바른 HTTP URL이 아닙니다.")

        date_value = date_node.get(date_attribute) if date_attribute else None
        if not isinstance(date_value, str) or not date_value.strip():
            date_value = date_node.get_text(" ", strip=True)
        try:
            posted_at = _posted_at(date_value)
        except ParseError as exc:
            raise ParseError(f"{index}번째 공지의 게시일을 해석할 수 없습니다.") from exc

        external_id = None
        if isinstance(id_selector, str) and id_selector:
            id_node = _select_one(item, id_selector, "id_selector")
            if id_node is not None:
                id_value = _clean_text(id_node.get_text(" ", strip=True))
                if id_value:
                    external_id = id_value
        if isinstance(id_attribute, str) and id_attribute:
            id_value = item.get(id_attribute)
            if external_id is None and isinstance(id_value, str) and id_value.strip():
                external_id = id_value.strip()
        if external_id is None and isinstance(id_query_parameter, str) and id_query_parameter:
            id_values = parse_qs(urlsplit(original_url).query).get(id_query_parameter, [])
            if id_values and id_values[0].strip():
                external_id = id_values[0].strip()
        if external_id is None:
            external_id = hashlib.sha256(original_url.encode("utf-8")).hexdigest()
        if external_id in seen_ids:
            continue
        seen_ids.add(external_id)

        category_name = None
        if isinstance(category_selector, str) and category_selector:
            category_node = _select_one(item, category_selector, "category_selector")
            if category_node is not None:
                category_name = _clean_text(category_node.get_text(" ", strip=True)) or None

        notices.append(
            NoticeSummary(
                external_id=external_id,
                title=title,
                original_url=original_url,
                posted_at=posted_at,
                category_name=category_name,
            )
        )

    return notices


def parse_notice_content(html: str, content_selector: str) -> str:
    """상세 HTML에서 지정된 본문 영역의 텍스트를 추출한다."""
    if not content_selector.strip():
        raise ParseError("content_selector를 설정해야 합니다.")
    soup = BeautifulSoup(html, "html.parser")
    content_node = _select_one(soup, content_selector, "content_selector")
    if content_node is None:
        raise ParseError("content_selector와 일치하는 본문이 없습니다.")
    return _clean_text(content_node.get_text(" ", strip=True))


def parse_next_page_url(html: str, current_url: str, selector: str) -> str | None:
    """페이지 이동 링크가 있으면 절대 URL로 바꿔 반환한다."""
    if not selector.strip():
        raise ParseError("next_page_selector를 설정해야 합니다.")
    soup = BeautifulSoup(html, "html.parser")
    next_link = _select_one(soup, selector, "next_page_selector")
    if next_link is None:
        return None
    href = next_link.get("href")
    if not isinstance(href, str) or not href.strip():
        raise ParseError("다음 페이지 링크에 href가 없습니다.")
    return urljoin(current_url, href.strip())
