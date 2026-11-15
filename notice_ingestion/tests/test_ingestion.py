import tempfile
import unittest
from pathlib import Path

from notice_ingestion.config import SAMPLE_FILES
from notice_ingestion.database import DatabaseManager
from notice_ingestion.main import ingest_local_html
from notice_ingestion.parsers import ComputerEngineeringCrawler, ElectricalEngineeringCrawler


class SampleParsingTests(unittest.TestCase):
    def test_computer_detail_sample(self):
        notice = ComputerEngineeringCrawler().parse_detail(SAMPLE_FILES["computer"])
        self.assertEqual(notice.department, "컴퓨터공학과")
        self.assertEqual(notice.post_number, "2792")
        self.assertTrue(notice.title)
        self.assertIn("영어캠프", notice.content)
        self.assertTrue(notice.attachments)

    def test_electrical_sample_has_detail_and_list(self):
        crawler = ElectricalEngineeringCrawler()
        notice = crawler.parse_detail(SAMPLE_FILES["electrical"])
        listed = crawler.list_notices(SAMPLE_FILES["electrical"])
        self.assertEqual(notice.post_number, "4396")
        self.assertTrue(notice.content)
        self.assertGreaterEqual(len(listed), 10)
        self.assertEqual(listed[0]["department"], "전기공학부")

    def test_sqlite_upsert_search_detail_and_export(self):
        notice = ComputerEngineeringCrawler().parse_detail(SAMPLE_FILES["computer"])
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as temp:
            db = DatabaseManager(Path(temp) / "notices.db")
            db.upsert(notice)
            db.upsert(notice)
            self.assertEqual(len(db.all()), 1)
            self.assertEqual(db.get(notice.department, notice.post_number)["title"], notice.title)
            self.assertTrue(db.search("영어캠프"))
            exported = Path(temp) / "export.json"
            db.export_json(exported)
            self.assertIn(notice.post_number, exported.read_text(encoding="utf-8"))

    def test_import_reports_new_posts_once_and_keeps_details(self):
        crawler = ElectricalEngineeringCrawler()
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as temp:
            db = DatabaseManager(Path(temp) / "notices.db")
            first = ingest_local_html(db, crawler, SAMPLE_FILES["electrical"])
            second = ingest_local_html(db, crawler, SAMPLE_FILES["electrical"])
            self.assertEqual(len(first["new_notices"]), 15)
            self.assertEqual(second["new_notices"], {})
            self.assertTrue(db.get("전기공학부", "4396")["content"])
            self.assertEqual(db.latest_by_department()[0]["post_number"], "4396")


if __name__ == "__main__":
    unittest.main()
