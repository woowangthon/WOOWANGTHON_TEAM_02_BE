"""PostgreSQL 연결 풀 생성 도구."""

from psycopg_pool import ConnectionPool


def create_pool(database_url: str) -> ConnectionPool:
    """앱 프로세스에서 공유할 연결 풀을 만든다."""
    return ConnectionPool(
        conninfo=database_url,
        min_size=1,
        max_size=10,
        timeout=5,
        open=False,
    )
