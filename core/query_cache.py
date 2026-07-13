"""Cache kết quả chat theo (domain_id, câu hỏi) — tránh gọi LLM/DB lặp lại."""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

_CACHE_DIR = Path(__file__).resolve().parent.parent / ".cache"
_DB_PATH = _CACHE_DIR / "query_cache.db"
_LOCK = threading.Lock()

_DEFAULT_TTL_SEC = 1800  # 30 phút
_MAX_ENTRIES = 500


def _ttl_seconds() -> int:
    raw = os.getenv("QUERY_CACHE_TTL_SECONDS", str(_DEFAULT_TTL_SEC))
    try:
        return max(60, int(raw))
    except ValueError:
        return _DEFAULT_TTL_SEC


def is_query_cache_enabled() -> bool:
    return os.getenv("QUERY_CACHE_ENABLED", "true").strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )


def _normalize_query(query: str) -> str:
    return " ".join(query.strip().casefold().split())


def make_cache_key(domain_id: str, query: str) -> str:
    """Khóa cache: domain + câu hỏi chuẩn hóa (không phụ thuộc lịch sử chat)."""
    payload = f"{domain_id}\0{_normalize_query(query)}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _connect() -> sqlite3.Connection:
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(_DB_PATH, timeout=10.0)
    conn.row_factory = sqlite3.Row
    return conn


def _init_db(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS query_cache (
            cache_key TEXT PRIMARY KEY,
            domain_id TEXT NOT NULL,
            query_text TEXT NOT NULL,
            response_json TEXT NOT NULL,
            created_at REAL NOT NULL,
            expires_at REAL NOT NULL
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_query_cache_expires ON query_cache(expires_at)"
    )
    conn.commit()


def _prune_expired(conn: sqlite3.Connection) -> None:
    now = time.time()
    conn.execute("DELETE FROM query_cache WHERE expires_at <= ?", (now,))
    conn.commit()


def _enforce_max_entries(conn: sqlite3.Connection) -> None:
    row = conn.execute("SELECT COUNT(*) AS c FROM query_cache").fetchone()
    count = int(row["c"]) if row else 0
    if count <= _MAX_ENTRIES:
        return
    overflow = count - _MAX_ENTRIES
    conn.execute(
        """
        DELETE FROM query_cache
        WHERE cache_key IN (
            SELECT cache_key FROM query_cache
            ORDER BY created_at ASC
            LIMIT ?
        )
        """,
        (overflow,),
    )
    conn.commit()


def get_cached_response(domain_id: str, query: str) -> dict[str, Any] | None:
    """Trả response dict nếu còn hạn; None nếu miss hoặc cache tắt."""
    if not is_query_cache_enabled():
        return None

    key = make_cache_key(domain_id, query)
    now = time.time()

    with _LOCK:
        conn = _connect()
        try:
            _init_db(conn)
            _prune_expired(conn)
            row = conn.execute(
                """
                SELECT response_json, expires_at
                FROM query_cache
                WHERE cache_key = ?
                """,
                (key,),
            ).fetchone()
            if not row:
                return None
            if float(row["expires_at"]) <= now:
                conn.execute("DELETE FROM query_cache WHERE cache_key = ?", (key,))
                conn.commit()
                return None
            data = json.loads(row["response_json"])
            if isinstance(data, dict):
                data["from_cache"] = True
                return data
            return None
        finally:
            conn.close()


def _json_default(obj: Any) -> Any:
    """Fallback khi payload còn Decimal/date (Postgres) — tránh crash cache."""
    from datetime import date, datetime
    from decimal import Decimal
    from uuid import UUID

    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, UUID):
        return str(obj)
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def set_cached_response(domain_id: str, query: str, response: dict[str, Any]) -> None:
    """Lưu response thành công / empty (không lưu lỗi)."""
    if not is_query_cache_enabled():
        return

    status = response.get("status")
    if status not in ("success", "empty"):
        return
    if response.get("viz_only"):
        return

    key = make_cache_key(domain_id, query)
    now = time.time()
    ttl = _ttl_seconds()
    payload = {k: v for k, v in response.items() if k != "from_cache"}
    payload["from_cache"] = False

    with _LOCK:
        conn = _connect()
        try:
            _init_db(conn)
            conn.execute(
                """
                INSERT INTO query_cache (
                    cache_key, domain_id, query_text, response_json, created_at, expires_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(cache_key) DO UPDATE SET
                    response_json = excluded.response_json,
                    created_at = excluded.created_at,
                    expires_at = excluded.expires_at
                """,
                (
                    key,
                    domain_id,
                    query.strip(),
                    json.dumps(payload, ensure_ascii=False, default=_json_default),
                    now,
                    now + ttl,
                ),
            )
            conn.commit()
            _enforce_max_entries(conn)
        finally:
            conn.close()


def clear_query_cache(domain_id: str | None = None) -> int:
    """Xóa cache (toàn bộ hoặc theo domain). Trả số dòng đã xóa."""
    with _LOCK:
        conn = _connect()
        try:
            _init_db(conn)
            if domain_id:
                cur = conn.execute(
                    "DELETE FROM query_cache WHERE domain_id = ?", (domain_id,)
                )
            else:
                cur = conn.execute("DELETE FROM query_cache")
            conn.commit()
            return cur.rowcount
        finally:
            conn.close()
