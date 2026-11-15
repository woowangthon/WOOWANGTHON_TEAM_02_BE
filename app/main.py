"""FastAPI 앱과 기본 상태 확인 엔드포인트."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
import logging
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import psycopg
from psycopg_pool import PoolTimeout

from app.auth.router import router as auth_router
from app.auth.router import _registration_options
from app.config import get_settings
from app.db.pool import create_pool
from app.notices.router import router as notices_router
from app.notices.recommendations import router as recommendations_router
from app.chatbot.router import router as assistant_router

logger = logging.getLogger(__name__)
CRAWLER_POLL_SECONDS = 300


async def _crawl_periodically() -> None:
    """Check registered sources periodically; source intervals limit requests."""
    from app.crawler.run import run as run_crawler

    while True:
        await asyncio.sleep(CRAWLER_POLL_SECONDS)
        try:
            await asyncio.to_thread(run_crawler)
        except Exception:
            logger.exception("Scheduled notice crawl failed")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    pool = create_pool(settings.database_url)
    pool.open(wait=True, timeout=10)
    app.state.db_pool = pool
    crawler_task = asyncio.create_task(_crawl_periodically())
    try:
        yield
    finally:
        crawler_task.cancel()
        try:
            await crawler_task
        except asyncio.CancelledError:
            pass
        pool.close()


app = FastAPI(title="공지사항 알리미", lifespan=lifespan)
static_dir = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=static_dir), name="static")
app.include_router(auth_router)
app.include_router(notices_router)
app.include_router(recommendations_router)
app.include_router(assistant_router)
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent / "templates"))


@app.get("/", tags=["pages"], response_class=HTMLResponse)
def home(request: Request) -> Any:
    registration_options = _registration_options(request.app.state.db_pool)
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context=registration_options,
    )


@app.get("/extension-import", tags=["pages"], response_class=HTMLResponse)
def extension_import_page(request: Request) -> Any:
    """확장 기능에서 전달한 공지 상세를 확인하고 저장하는 화면."""
    return templates.TemplateResponse(
        request=request,
        name="extension_import.html",
        context={},
    )


@app.get("/health", tags=["health"])
def health(request: Request) -> dict[str, str]:
    """앱과 데이터베이스 연결 상태를 확인한다."""
    pool = request.app.state.db_pool
    try:
        with pool.connection(timeout=2) as conn:
            conn.execute("SELECT 1")
    except (psycopg.Error, PoolTimeout) as exc:
        raise HTTPException(status_code=503, detail="database unavailable") from exc

    return {"status": "ok"}
