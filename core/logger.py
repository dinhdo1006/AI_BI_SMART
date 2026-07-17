"""Structured JSON logging + audit trail cho luồng chat BI."""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

_LOGGER_NAME = "ai_bi.chat"
_configured = False

_LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
_FEEDBACK_FILE = _LOG_DIR / "feedback.jsonl"
_AUDIT_FILE = _LOG_DIR / "audit.jsonl"

FeedbackVote = Literal["up", "down"]


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


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    _LOG_DIR.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")


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
    intent: str | None = None,
    request_id: str | None = None,
    client_ip: str | None = None,
    tenant_id: str | None = None,
) -> None:
    """Ghi stdout + logs/audit.jsonl cho mỗi request /api/v1/chat."""
    payload: dict[str, Any] = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "event": "chat_request",
        "domain_id": domain_id,
        "query": query[:500],
        "status": status,
        "sql_source": sql_source,
        "row_count": row_count,
        "latency_total_ms": round(latency_total_ms, 1),
        "viz_only": viz_only,
        "from_cache": from_cache,
    }
    if tenant_id:
        payload["tenant_id"] = tenant_id
    if request_id:
        payload["request_id"] = request_id
    if client_ip:
        payload["client_ip"] = client_ip
    if intent:
        payload["intent"] = intent
    if sql_query:
        payload["sql_query"] = sql_query[:800]
    if latency_llm_ms is not None:
        payload["latency_llm_ms"] = round(latency_llm_ms, 1)
    if latency_db_ms is not None:
        payload["latency_db_ms"] = round(latency_db_ms, 1)
    if error:
        payload["error"] = error[:300]

    line = json.dumps(payload, ensure_ascii=False)
    _ensure_configured().info(line)
    _append_jsonl(_AUDIT_FILE, payload)


def log_feedback(
    *,
    domain_id: str,
    query: str,
    vote: FeedbackVote,
    sql_query: str = "",
    sql_source: str | None = None,
    status: str | None = None,
) -> None:
    """Ghi feedback user (👍/👎) ra stdout + logs/feedback.jsonl."""
    payload: dict[str, Any] = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "event": "feedback",
        "domain_id": domain_id,
        "query": query[:500],
        "vote": vote,
    }
    if sql_source:
        payload["sql_source"] = sql_source
    if status:
        payload["status"] = status
    if sql_query:
        payload["sql_query"] = sql_query[:500]

    line = json.dumps(payload, ensure_ascii=False)
    _ensure_configured().info(line)
    _append_jsonl(_FEEDBACK_FILE, payload)
