"""Entry point — khởi tạo FastAPI app và chạy Uvicorn."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import router
from api.alerts import router as alerts_router
from api.auto_articles import router as auto_articles_router
from core.alert_scheduler import start_scheduler, stop_scheduler
from core.article_scheduler import (
    start_scheduler as start_article_scheduler,
    stop_scheduler as stop_article_scheduler,
)
from core.auth import ApiKeyMiddleware, auth_enabled
from core.schema_rag import is_schema_rag_enabled


@asynccontextmanager
async def lifespan(_app: FastAPI):
    start_scheduler()
    start_article_scheduler()
    try:
        yield
    finally:
        stop_scheduler()
        stop_article_scheduler()


app = FastAPI(
    title="Multi-domain Conversational BI",
    description="Text-to-SQL cục bộ với Ollama — hỗ trợ SQLite/PostgreSQL + RAG Schema.",
    version="1.5.0",
    lifespan=lifespan,
)

_cors_origins = [
    o.strip()
    for o in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:3010,http://127.0.0.1:3010",
    ).split(",")
    if o.strip()
]
# Auth trước — CORS outermost (add sau) để preflight OPTIONS không bị 401
app.add_middleware(ApiKeyMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
app.include_router(alerts_router)
app.include_router(auto_articles_router)


@app.get("/health")
def health() -> dict[str, str | bool]:
    """Health-check — gọi /api/v1/health/domains để kiểm tra DB từng domain."""
    return {
        "status": "ok",
        "schema_rag_enabled": is_schema_rag_enabled(),
        "auth_required": auth_enabled(),
    }
