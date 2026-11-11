"""번호가 붙은 SQL 마이그레이션을 적용하는 CLI."""

from __future__ import annotations

import os
from pathlib import Path

import psycopg

MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "db" / "migrations"


def run_migrations() -> None:
    """아직 기록되지 않은 마이그레이션을 파일명 순서대로 적용한다."""
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL 환경변수가 설정되지 않았습니다.")

    migration_files = sorted(MIGRATIONS_DIR.glob("[0-9][0-9][0-9][0-9]_*.sql"))

    with psycopg.connect(database_url) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version TEXT PRIMARY KEY,
                applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )
        conn.commit()

        for migration_file in migration_files:
            version = migration_file.name
            with conn.transaction():
                already_applied = conn.execute(
                    "SELECT EXISTS (SELECT 1 FROM schema_migrations WHERE version = %s)",
                    (version,),
                ).fetchone()[0]
                if already_applied:
                    continue

                conn.execute(migration_file.read_text(encoding="utf-8"))
                conn.execute(
                    "INSERT INTO schema_migrations (version) VALUES (%s)",
                    (version,),
                )
            print(f"적용 완료: {version}")


def main() -> None:
    run_migrations()


if __name__ == "__main__":
    main()
