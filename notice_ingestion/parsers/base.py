from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
import re
from urllib.parse import parse_qs, urlencode, urljoin, urlparse, urlunparse

from bs4 import BeautifulSoup, NavigableString, Tag

from ..models import Attachment, Notice


class BaseCrawler(ABC):
    department = ""
    base_url = ""

    def parse_html(self, source: Path | str | bytes) -> BeautifulSoup:
        if isinstance(source, Path):
            raw = source.read_bytes()
        elif isinstance(source, bytes):
            raw = source
        else:
            raw = source.encode("utf-8")
        # These saved pages declare EUC-KR in their legacy metadata but the
        # supplied files are UTF-8. Prefer valid UTF-8, then honor the page's
        # declared encoding for locally saved originals.
        try:
            decoded = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            decoded = raw.decode("euc-kr", errors="replace")
        return BeautifulSoup(decoded, "html.parser")

    def list_notices(self, source: Path | str | bytes) -> list[dict]:
        soup = self.parse_html(source)
        found: dict[str, dict] = {}
        for link in soup.select('a[href*="task=view"]'):
            parsed = urlparse(link.get("href", ""))
            params = parse_qs(parsed.query)
            number = (params.get("no") or [""])[0]
            title = " ".join(link.stripped_strings)
            if number and title:
                row = link.find_parent("tr")
                cells = [" ".join(cell.stripped_strings) for cell in row.find_all(["td", "th"], recursive=False)] if row else []
                row_text = " | ".join(cells)
                author = ""
                date = ""
                if row:
                    table = row.find_parent("table")
                    header = table.find("tr") if table else None
                    headings = [" ".join(cell.stripped_strings) for cell in header.find_all(["td", "th"], recursive=False)] if header else []
                    for index, heading in enumerate(headings):
                        if index >= len(cells):
                            continue
                        if "작성자" in heading or "작성" == heading.strip():
                            author = cells[index]
                        if "날짜" in heading or "등록일" in heading or "작성일" in heading:
                            date = cells[index]
                if not date:
                    date_match = re.search(r"\b\d{4}[-./]\d{1,2}[-./]\d{1,2}\b", row_text)
                    date = date_match.group(0) if date_match else ""
                found[number] = {
                    "department": self.department,
                    "post_number": number,
                    "title": title,
                    "author": author,
                    "date": date,
                    "url": self.canonical_notice_url(number),
                }
        return list(found.values())

    def canonical_notice_url(self, number: str) -> str:
        return urljoin(self.base_url, "/bbs/bbs.php?" + urlencode({"task": "view", "db": "notice", "no": number}))

    @abstractmethod
    def parse_detail(self, source: Path | str | bytes, source_url: str | None = None) -> Notice:
        raise NotImplementedError

    def common_detail(self, soup: BeautifulSoup, source_url: str | None):
        title_node = soup.select_one(".view_subject")
        article = soup.select_one("div#articles")
        if not title_node or not article:
            raise ValueError("상세 페이지 필수 요소(.view_subject 또는 div#articles)를 찾지 못했습니다.")
        title = " ".join(title_node.stripped_strings)
        author_node = soup.select_one(".view_name")
        author = " ".join(author_node.stripped_strings) if author_node else ""
        date = ""
        for node in soup.select(".view_text"):
            text = " ".join(node.stripped_strings)
            if "작성일" in text:
                date = text.split(":", 1)[-1].strip()
                break
        # Preserve paragraph and line boundaries for downstream retrieval.
        body = extract_text(article)
        attachments = self.extract_attachments(soup)
        number = self.extract_number(soup, source_url, attachments)
        if not number:
            raise ValueError("게시글 번호를 HTML에서 확인할 수 없습니다.")
        return Notice(self.department, number, title, author, date, self.canonical_notice_url(number), body, attachments,
                      datetime.now(timezone.utc).isoformat(timespec="seconds"))

    def extract_number(self, soup: BeautifulSoup, source_url: str | None, attachments: list[Attachment]) -> str:
        candidates = [source_url or ""]
        candidates.extend(a.get("href", "") for a in soup.select('a[href*="task=view"]'))
        candidates.extend(a.url for a in attachments)
        for candidate in candidates:
            number = (parse_qs(urlparse(candidate).query).get("no") or [""])[0]
            if number.isdigit():
                return number
        return ""

    def extract_attachments(self, soup: BeautifulSoup) -> list[Attachment]:
        result = []
        seen = set()
        for anchor in soup.select('a[href*="download.php"]'):
            href = anchor.get("href", "")
            parsed = urlparse(href)
            params = parse_qs(parsed.query)
            # The board listing has icon-only download links; keep only files
            # from this detail post when its number is known.
            name = " ".join(anchor.stripped_strings)
            if not name:
                image = anchor.find("img")
                name = (image.get("alt", "") or image.get("title", "")) if image else ""
            if not name:
                continue
            absolute = urljoin(self.base_url, href)
            if absolute not in seen:
                result.append(Attachment(name, absolute))
                seen.add(absolute)
        return result


def extract_text(node: Tag) -> str:
    clone = BeautifulSoup(str(node), "html.parser").select_one("#articles")
    if not clone:
        return ""
    for unwanted in clone.select("script,style,iframe,object,embed"):
        unwanted.decompose()
    for br in clone.select("br"):
        br.replace_with(NavigableString("\n"))
    for block in clone.select("p,div,li,tr"):
        block.append(NavigableString("\n"))
    lines = [" ".join(line.split()) for line in clone.get_text().replace("\xa0", " ").splitlines()]
    return "\n".join(line for line in lines if line).strip()
