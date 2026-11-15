import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from ..models import Notice


class DatabaseManager:
    def __init__(self, db_path: Path | str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as conn:
            conn.executescript(Path(__file__).with_name("schema.sql").read_text(encoding="utf-8"))

    @contextmanager
    def connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def upsert(self, notice: Notice) -> None:
        collected = notice.collected_at or datetime.now(timezone.utc).isoformat(timespec="seconds")
        with self.connect() as conn:
            conn.execute("""INSERT INTO notices
                (department,post_number,title,author,date,url,content,attachments,collected_at)
                VALUES (?,?,?,?,?,?,?,?,?)
                ON CONFLICT(department,post_number) DO UPDATE SET
                title=excluded.title,
                author=CASE WHEN excluded.author<>'' THEN excluded.author ELSE notices.author END,
                date=CASE WHEN excluded.date<>'' THEN excluded.date ELSE notices.date END,
                url=excluded.url,
                content=CASE WHEN excluded.content<>'' THEN excluded.content ELSE notices.content END,
                attachments=CASE WHEN excluded.attachments<>'[]' THEN excluded.attachments ELSE notices.attachments END,
                collected_at=excluded.collected_at""",
                (notice.department, notice.post_number, notice.title, notice.author, notice.date,
                 notice.url, notice.content,
                 json.dumps([a.__dict__ for a in notice.attachments], ensure_ascii=False), collected))

    def exists(self, department: str, post_number: str) -> bool:
        with self.connect() as conn:
            row = conn.execute("SELECT 1 FROM notices WHERE department=? AND post_number=?",
                               (department, post_number)).fetchone()
        return row is not None

    def all(self, department: str | None = None) -> list[dict]:
        with self.connect() as conn:
            rows = conn.execute("SELECT * FROM notices" + (" WHERE department=?" if department else "") +
                                " ORDER BY date DESC, id DESC", (department,) if department else ()).fetchall()
        return [self._row(row) for row in rows]

    def latest_by_department(self) -> list[dict]:
        latest = {}
        for notice in self.all():
            department = notice["department"]
            current = latest.get(department)
            post_number = int(notice["post_number"]) if notice["post_number"].isdigit() else -1
            current_number = int(current["post_number"]) if current and current["post_number"].isdigit() else -1
            if current is None or (notice["date"], post_number) > (current["date"], current_number):
                latest[department] = notice
        return list(latest.values())

    def search(self, query: str) -> list[dict]:
        pattern = f"%{query}%"
        with self.connect() as conn:
            rows = conn.execute("SELECT * FROM notices WHERE title LIKE ? OR content LIKE ? ORDER BY date DESC", (pattern, pattern)).fetchall()
        return [self._row(row) for row in rows]

    def get(self, department: str, post_number: str) -> dict | None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM notices WHERE department=? AND post_number=?", (department, post_number)).fetchone()
        return self._row(row) if row else None

    def export_json(self, destination: Path | str) -> None:
        Path(destination).parent.mkdir(parents=True, exist_ok=True)
        Path(destination).write_text(json.dumps(self.all(), ensure_ascii=False, indent=2), encoding="utf-8")

    @staticmethod
    def _row(row):
        result = dict(row)
        result["attachments"] = json.loads(result["attachments"])
        return result
