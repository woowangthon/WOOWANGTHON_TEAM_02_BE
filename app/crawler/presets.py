"""자주 쓰는 게시판 구조의 선택자 후보."""

from __future__ import annotations

from typing import Any

from bs4 import BeautifulSoup

PRESETS: tuple[tuple[str, str, dict[str, Any]], ...] = (
    (
        "gnuboard5",
        "#bo_list .bo_tit a",
        {
            "item_selector": "#bo_list tbody tr",
            "title_selector": ".bo_tit a",
            "link_selector": ".bo_tit a",
            "date_selector": ".td_datetime",
            "category_selector": ".bo_cate_link",
            "content_selector": "#bo_v_con",
        },
    ),
    (
        "kboard",
        ".kboard-list-item .kboard-list-title a",
        {
            "item_selector": ".kboard-list-item",
            "title_selector": ".kboard-list-title a",
            "link_selector": ".kboard-list-title a",
            "date_selector": ".kboard-list-date",
            "content_selector": ".kboard-content",
        },
    ),
    (
        "wordpress",
        "article .entry-title a",
        {
            "item_selector": "article",
            "title_selector": ".entry-title a",
            "link_selector": ".entry-title a",
            "date_selector": "time.entry-date",
            "date_attribute": "datetime",
            "content_selector": ".entry-content",
        },
    ),
)


def matching_presets(html: str) -> list[tuple[str, dict[str, Any]]]:
    """해당 게시판 계열의 구조 지표가 HTML에 있는 프리셋만 반환한다."""
    soup = BeautifulSoup(html, "html.parser")
    return [
        (name, config)
        for name, marker_selector, config in PRESETS
        if soup.select_one(marker_selector) is not None
    ]
