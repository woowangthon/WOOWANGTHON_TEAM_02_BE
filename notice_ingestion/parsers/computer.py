from pathlib import Path

from .base import BaseCrawler
from ..models import Notice


class ComputerEngineeringCrawler(BaseCrawler):
    department = "컴퓨터공학과"
    base_url = "https://computer.cbnu.ac.kr/"

    def parse_detail(self, source: Path | str | bytes, source_url: str | None = None) -> Notice:
        return self.common_detail(self.parse_html(source), source_url)
