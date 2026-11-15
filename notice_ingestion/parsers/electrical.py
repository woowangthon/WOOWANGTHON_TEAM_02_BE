from pathlib import Path

from .base import BaseCrawler
from ..models import Notice


class ElectricalEngineeringCrawler(BaseCrawler):
    department = "전기공학부"
    base_url = "https://koamma.chungbuk.ac.kr/"

    def parse_detail(self, source: Path | str | bytes, source_url: str | None = None) -> Notice:
        return self.common_detail(self.parse_html(source), source_url)
