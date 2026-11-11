"""공지 본문에서 빠르게 읽을 수 있는 짧은 발췌 요약을 만든다."""

from __future__ import annotations

import re

MAX_SUMMARY_LENGTH = 260


def summarize_notice(content: str) -> str:
    """안내 문장과 번호가 붙은 핵심 항목을 골라 짧은 요약을 만든다."""
    text = re.sub(r"\s+", " ", content).strip()
    if not text:
        return ""

    # Keep numbered application details together, while splitting numbered sections.
    clauses = re.split(
        r"(?<!\d)\s+(?=(?:\d{1,2}\s*[.)]|[가-하]\s*[.)]|"
        r"(?:신청|접수|모집|지원|제출|문의|참여)\s*(?:기간|대상|방법|자격)?\s*[:：]))",
        text,
    )
    selected: list[str] = []
    for index, clause in enumerate(clauses):
        clause = clause.strip(" -•·\t")
        if len(clause) < 8 or clause in selected:
            continue
        if index < len(clauses) - 1 and re.match(r"관련\s*[:：]", clause):
            continue
        candidate = " ".join([*selected, clause])
        if len(candidate) > MAX_SUMMARY_LENGTH:
            if not selected:
                return clause[: MAX_SUMMARY_LENGTH - 1].rsplit(" ", 1)[0] + "…"
            break
        selected.append(clause)
        if len(selected) == 2:
            break

    summary = " ".join(selected) if selected else text
    if len(summary) > MAX_SUMMARY_LENGTH:
        summary = summary[: MAX_SUMMARY_LENGTH - 1].rsplit(" ", 1)[0] + "…"
    return summary
