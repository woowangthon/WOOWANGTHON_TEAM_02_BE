"""목록 HTML에서 반복되는 공지 행의 CSS 선택자를 추정한다."""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

from bs4 import BeautifulSoup, Tag

DATE_RE = re.compile(r"(?:20\d{2}[-./년]\s?\d{1,2}[-./월]\s?\d{1,2}(?:일)?|20\d{6})")
SAFE_CLASS_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_-]*$")
ROW_TAGS = {"tr", "li", "article", "div"}


def _selector(tag: Tag) -> str:
    classes = [name for name in tag.get("class", []) if SAFE_CLASS_RE.fullmatch(name)]
    return tag.name + ("." + ".".join(classes[:2]) if classes else "")


def suggest_selectors(html: str) -> dict[str, Any] | None:
    """날짜와 링크를 함께 가진 반복 행에서 보수적인 selector 후보를 만든다."""
    soup = BeautifulSoup(html, "html.parser")
    groups: dict[str, list[tuple[Tag, Tag, Tag]]] = defaultdict(list)
    for anchor in soup.select("a[href]"):
        if not anchor.get_text(" ", strip=True):
            continue
        row = anchor.parent
        while isinstance(row, Tag) and row.name not in ROW_TAGS:
            row = row.parent
        if not isinstance(row, Tag):
            continue
        date_node = next(
            (node for node in row.find_all(True) if DATE_RE.search(" ".join([
                node.get_text(" ", strip=True), str(node.get("datetime", ""))
            ]))),
            None,
        )
        if date_node is None:
            continue
        # 가장 가까운 공통 행을 우선해 상위 div 전체가 선택되는 일을 줄인다.
        groups[_selector(row)].append((row, anchor, date_node))
    candidates = [(key, rows) for key, rows in groups.items() if len(rows) >= 2]
    if not candidates:
        return None
    _, rows = max(candidates, key=lambda item: len(item[1]))
    row, anchor, date_node = rows[0]
    link_selector = _selector(anchor)
    date_selector = _selector(date_node)
    config: dict[str, Any] = {
        "item_selector": _selector(row),
        "title_selector": link_selector,
        "link_selector": link_selector,
        "date_selector": date_selector,
    }
    if date_node.get("datetime"):
        config["date_attribute"] = "datetime"
    return config
