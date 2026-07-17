"""Cache kết quả chat theo (domain_id, câu hỏi) — tránh gọi LLM/DB lặp lại."""

from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import threading
import time
import unicodedata
from pathlib import Path
from typing import Any

_CACHE_DIR = Path(__file__).resolve().parent.parent / ".cache"
_DB_PATH = _CACHE_DIR / "query_cache.db"
_LOCK = threading.Lock()

_DEFAULT_TTL_SEC = 1800  # 30 phút
_MAX_ENTRIES = 500
_SEMANTIC_SCAN_LIMIT = 80
_DEFAULT_JACCARD = 0.82

_STOPWORDS = frozenset(
    {
        "a",
        "an",
        "the",
        "of",
        "to",
        "for",
        "va",
        "và",
        "cua",
        "của",
        "cho",
        "toi",
        "tôi",
        "ban",
        "bạn",
        "hay",
        "hãy",
        "giup",
        "giúp",
        "xem",
        "voi",
        "với",
        "mot",
        "một",
        "cac",
        "các",
        "nhung",
        "những",
        "la",
        "là",
        "duoc",
        "được",
        "trong",
        "nay",
        "này",
        "hom",
        "hôm",
        "làm",
        "lam",
        "sao",
        "thế",
        "nao",
        "nào",
        "đi",
        "di",
        "nhé",
        "nhe",
        "ạ",
        "ơi",
        "oi",
        "xin",
        "vui",
        "long",
        "lòng",
    }
)

_SYNONYMS = {
    "cophieu": "cổphiếu",
    "cp": "cổphiếu",
    "pe": "pe",
    "pb": "pb",
    "roe": "roe",
    "vonhoa": "vốnhoá",
    "bieudo": "biểuđồ",
    "chart": "biểuđồ",
    "tang": "tăng",
    "giam": "giảm",
    "homnay": "hômnay",
    "thang": "tháng",
    "quy": "quý",
    "nam": "năm",
}


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


def is_semantic_cache_enabled() -> bool:
    return os.getenv("QUERY_CACHE_SEMANTIC", "true").strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )


def _semantic_jaccard_threshold() -> float:
    raw = os.getenv("QUERY_CACHE_SEMANTIC_THRESHOLD", str(_DEFAULT_JACCARD))
    try:
        return min(0.99, max(0.5, float(raw)))
    except ValueError:
        return _DEFAULT_JACCARD


def _strip_diacritics(text: str) -> str:
    norm = unicodedata.normalize("NFD", text)
    return "".join(ch for ch in norm if unicodedata.category(ch) != "Mn")


def semantic_tokens(query: str) -> frozenset[str]:
    """Chuẩn hóa câu hỏi thành tập token nội dung (bỏ stopword, map synonym)."""
    text = _normalize_query(query)
    text = re.sub(r"\bp\s*/\s*e\b", " pe ", text)
    text = re.sub(r"\bp\s*/\s*b\b", " pb ", text)
    text = text.replace("/", " ")
    text = re.sub(r"[^\w\s%.+-]", " ", text, flags=re.UNICODE)
    tokens: set[str] = set()
    for raw in text.split():
        tok = raw.strip(".-_\\")
        if len(tok) < 2 or tok in _STOPWORDS:
            continue
        flat = _strip_diacritics(tok)
        mapped = _SYNONYMS.get(flat, flat)
        if mapped in _STOPWORDS or len(mapped) < 2:
            continue
        tokens.add(mapped)
    return frozenset(tokens)


def semantic_fingerprint(query: str) -> str:
    toks = sorted(semantic_tokens(query))
    return " ".join(toks)


def jaccard_similarity(a: frozenset[str], b: frozenset[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    if inter == 0:
        return 0.0
    return inter / float(len(a | b))


def _normalize_query(query: str) -> str:
    return " ".join(query.strip().casefold().split())


def make_cache_key(domain_id: str, query: str) -> str:
    """Khóa cache: domain + câu hỏi chuẩn hóa (không phụ thuộc lịch sử chat)."""
    payload = f"{domain_id}\0{_normalize_query(query)}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def make_semantic_key(domain_id: str, query: str) -> str:
    """Khóa semantic: domain + fingerprint token (câu diễn đạt khác nhau cùng ý)."""
    payload = f"{domain_id}\0sem\0{semantic_fingerprint(query)}"
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
    cols = {
        str(r["name"])
        for r in conn.execute("PRAGMA table_info(query_cache)").fetchall()
    }
    if "semantic_key" not in cols:
        conn.execute("ALTER TABLE query_cache ADD COLUMN semantic_key TEXT")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_query_cache_expires ON query_cache(expires_at)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_query_cache_domain_sem "
        "ON query_cache(domain_id, semantic_key)"
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


def _load_response(row: sqlite3.Row, *, semantic: bool) -> dict[str, Any] | None:
    data = json.loads(row["response_json"])
    if not isinstance(data, dict):
        return None
    data["from_cache"] = True
    data["cache_match"] = "semantic" if semantic else "exact"
    return data


def get_cached_response(domain_id: str, query: str) -> dict[str, Any] | None:
    """Trả response dict nếu còn hạn; None nếu miss hoặc cache tắt."""
    if not is_query_cache_enabled():
        return None

    key = make_cache_key(domain_id, query)
    sem_key = make_semantic_key(domain_id, query)
    now = time.time()
    q_tokens = semantic_tokens(query)
    threshold = _semantic_jaccard_threshold()

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
            if row and float(row["expires_at"]) > now:
                return _load_response(row, semantic=False)
            if row:
                conn.execute("DELETE FROM query_cache WHERE cache_key = ?", (key,))
                conn.commit()

            if not is_semantic_cache_enabled() or not q_tokens:
                return None

            row = conn.execute(
                """
                SELECT response_json, expires_at, query_text
                FROM query_cache
                WHERE domain_id = ? AND semantic_key = ?
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (domain_id, sem_key),
            ).fetchone()
            if row and float(row["expires_at"]) > now:
                return _load_response(row, semantic=True)

            rows = conn.execute(
                """
                SELECT response_json, expires_at, query_text
                FROM query_cache
                WHERE domain_id = ? AND expires_at > ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (domain_id, now, _SEMANTIC_SCAN_LIMIT),
            ).fetchall()
            best: tuple[float, sqlite3.Row] | None = None
            for cand in rows:
                score = jaccard_similarity(
                    q_tokens, semantic_tokens(str(cand["query_text"]))
                )
                if score < threshold:
                    continue
                if best is None or score > best[0]:
                    best = (score, cand)
            if best:
                return _load_response(best[1], semantic=True)
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
    sem_key = make_semantic_key(domain_id, query)
    now = time.time()
    ttl = _ttl_seconds()
    payload = {
        k: v
        for k, v in response.items()
        if k not in ("from_cache", "cache_match")
    }
    payload["from_cache"] = False

    with _LOCK:
        conn = _connect()
        try:
            _init_db(conn)
            conn.execute(
                """
                INSERT INTO query_cache (
                    cache_key, domain_id, query_text, response_json,
                    created_at, expires_at, semantic_key
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(cache_key) DO UPDATE SET
                    response_json = excluded.response_json,
                    created_at = excluded.created_at,
                    expires_at = excluded.expires_at,
                    semantic_key = excluded.semantic_key,
                    query_text = excluded.query_text
                """,
                (
                    key,
                    domain_id,
                    query.strip(),
                    json.dumps(payload, ensure_ascii=False, default=_json_default),
                    now,
                    now + ttl,
                    sem_key,
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
