"""멱등 개발용 시드를 적용하는 CLI."""

from __future__ import annotations

import os
from pathlib import Path

import psycopg

SEEDS_DIR = Path(__file__).resolve().parents[2] / "db" / "seeds"


def run_seeds() -> None:
    """시드 SQL 파일을 이름 순서대로 한 트랜잭션으로 적용한다."""
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL 환경변수가 설정되지 않았습니다.")

    seed_files = sorted(SEEDS_DIR.glob("[0-9][0-9][0-9][0-9]_*.sql"))
    if not seed_files:
        print("적용할 시드 파일이 없습니다.")
        return

    with psycopg.connect(database_url) as conn:
        with conn.transaction():
            for seed_file in seed_files:
                conn.execute(seed_file.read_text(encoding="utf-8"))
                print(f"적용 완료: {seed_file.name}")


def main() -> None:
    run_seeds()


if __name__ == "__main__":
    main()
