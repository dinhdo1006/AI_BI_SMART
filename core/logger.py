"""Structured JSON logging cho luồng chat BI."""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any

_LOGGER_NAME = "ai_bi.chat"
_configured = False


def _ensure_configured() -> logging.Logger:
    global _configured
    logger = logging.getLogger(_LOGGER_NAME)
    if not _configured:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
        _configured = True
    return logger


def log_chat_event(
    *,
    domain_id: str,
    query: str,
    status: str,
    sql_source: str,
    sql_query: str = "",
    row_count: int = 0,
    latency_total_ms: float = 0.0,
    latency_llm_ms: float | None = None,
    latency_db_ms: float | None = None,
    viz_only: bool = False,
    error: str | None = None,
    from_cache: bool = False,
) -> None:
    """Ghi một dòng JSON cho mỗi request /api/v1/chat."""
    payload: dict[str, Any] = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "event": "chat_request",
        "domain_id": domain_id,
        "query": query,
        "status": status,
        "sql_source": sql_source,
        "row_count": row_count,
        "latency_total_ms": round(latency_total_ms, 1),
        "viz_only": viz_only,
        "from_cache": from_cache,
    }
    if sql_query:
        payload["sql_query"] = sql_query[:500]
    if latency_llm_ms is not None:
        payload["latency_llm_ms"] = round(latency_llm_ms, 1)
    if latency_db_ms is not None:
        payload["latency_db_ms"] = round(latency_db_ms, 1)
    if error:
        payload["error"] = error[:300]

    _ensure_configured().info(json.dumps(payload, ensure_ascii=False))
