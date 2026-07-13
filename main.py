"""Entry point — khởi tạo FastAPI app và chạy Uvicorn."""

from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import router
from core.schema_rag import is_schema_rag_enabled

app = FastAPI(
    title="Multi-domain Conversational BI",
    description="Text-to-SQL cục bộ với Ollama — hỗ trợ SQLite/PostgreSQL + RAG Schema.",
    version="1.1.0",
)

_cors_origins = [
    o.strip()
    for o in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:3010,http://127.0.0.1:3010",
    ).split(",")
    if o.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Gắn router /api/v1/*
app.include_router(router)


@app.get("/health")
def health() -> dict[str, str | bool]:
    """Health-check — gọi /api/v1/health/domains để kiểm tra DB từng domain."""
    return {
        "status": "ok",
        "schema_rag_enabled": is_schema_rag_enabled(),
    }


@app.get("/health")
def health() -> dict[str, str | bool]:
    """Health-check — gọi /api/v1/health/domains để kiểm tra DB từng domain."""
    return {
        "status": "ok",
        "schema_rag_enabled": is_schema_rag_enabled(),
    }
