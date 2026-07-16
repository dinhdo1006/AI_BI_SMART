"""Resolve mã CK từ câu hỏi — đối chiếu DB thật, không whitelist cứng."""

from __future__ import annotations

import re
import time
import unicodedata
from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

# Cache: db_url → (expires_at, tickers)
_TICKER_CACHE: dict[str, tuple[float, frozenset[str]]] = {}
_CACHE_TTL_SEC = 3600.0

# Nhiễu tiếng Anh / chỉ số / từ nghiệp vụ — không phải mã CK
_STOPWORDS = frozenset({
    "TOP", "SQL", "AND", "THE", "FOR", "ALL", "MAX", "MIN", "AVG", "SUM",
    "HOSE", "HSX", "HNX", "UPCOM", "VN30", "VNINDEX", "VNI", "INDEX",
    "ROE", "ROA", "EPS", "GDP", "USD", "VND", "API", "CSV", "PDF", "JSON",
    "ASC", "DESC", "NULL", "TRUE", "FALSE", "LIMIT", "WHERE", "FROM",
    "JOIN", "WITH", "SELECT", "ORDER", "GROUP", "HAVING", "PE", "PB",
    "TTM", "OHLC", "YTD", "MTD", "QTD", "YOY", "QOQ",
    "PHIEN", "GAN", "NHAT", "MOI", "DANH", "SACH", "CONG", "TY",
    "DOANH", "NGHIEP", "THI", "TRUONG", "VON", "HOA", "CHI", "SO",
    "THANH", "PHAN", "DIEN", "BIEN", "TICH", "GIA", "CO", "PHIEU",
    "MA", "LON", "NHO", "CAO", "THAP", "THEO", "CUA", "CHO", "VE",
    "CAC", "TUNG", "NGAY", "THANG", "QUY", "NAM", "BAO", "CAO",
})

_TOKEN_RE = re.compile(r"\b([A-Z]{3}(?:[A-Z0-9]{1,2})?)\b")
_CTX_RE = re.compile(
    r"(?:ma\s*cp|ma\s+ck|ticker|symbol|co\s*phieu|gia(?:\s+dong\s+cua)?)"
    r"\s+([a-z]{3}(?:[a-z0-9]{0,2})?)\b",
    re.IGNORECASE,
)


def _normalize(text: str) -> str:
    lowered = (text or "").lower()
    nfd = unicodedata.normalize("NFD", lowered)
    return "".join(c for c in nfd if unicodedata.category(c) != "Mn")


def clear_ticker_cache() -> None:
    _TICKER_CACHE.clear()


def load_company_tickers(db_url: str) -> frozenset[str]:
    """Đọc companies.ticker từ DB (cache TTL). Rỗng nếu không kết nối được."""
    if not db_url:
        return frozenset()
    now = time.monotonic()
    cached = _TICKER_CACHE.get(db_url)
    if cached and cached[0] > now:
        return cached[1]

    tickers: frozenset[str] = frozenset()
    try:
        from core.db_engine import get_engine

        engine = get_engine(db_url)
        with engine.connect() as conn:
            rows = conn.execute(
                text("SELECT ticker FROM companies WHERE ticker IS NOT NULL")
            ).fetchall()
        tickers = frozenset(
            str(r[0]).upper().strip() for r in rows if r and r[0]
        )
    except (SQLAlchemyError, Exception):
        tickers = frozenset()

    _TICKER_CACHE[db_url] = (now + _CACHE_TTL_SEC, tickers)
    return tickers


def extract_ticker_candidates(query: str) -> list[str]:
    """Ứng viên mã từ câu hỏi (chưa xác thực DB)."""
    upper = (query or "").upper()
    norm = _normalize(query)
    found: list[str] = []
    seen: set[str] = set()

    def _add(token: str) -> None:
        t = (token or "").upper().strip()
        if len(t) < 3 or len(t) > 5:
            return
        if t in _STOPWORDS:
            return
        if not re.search(r"[A-Z]", t):
            return
        if t not in seen:
            seen.add(t)
            found.append(t)

    for m in _TOKEN_RE.finditer(upper):
        _add(m.group(1))
    for m in _CTX_RE.finditer(norm):
        _add(m.group(1))
    return found


def resolve_tickers(query: str, db_url: str | None = None) -> list[str]:
    """
    Mã CK thật trong câu hỏi.
    Có db_url → chỉ giữ mã tồn tại trong companies.
    Không DB → trả candidates đã lọc stopwords.
    """
    candidates = extract_ticker_candidates(query)
    if not candidates:
        return []
    if not db_url:
        return candidates
    known = load_company_tickers(db_url)
    if not known:
        return candidates
    return [t for t in candidates if t in known]


def format_entity_hint(tickers: list[str]) -> str:
    """Gợi ý gắn vào prompt LLM — không sinh SQL cứng."""
    if not tickers:
        return ""
    listed = ", ".join(tickers[:8])
    return (
        f"Detected tickers from database: {listed}. "
        f"Filter with companies.ticker (or financial_indicators.symbol) "
        f"using these exact codes."
    )


def resolve_query_entities(
    query: str, db_url: str | None = None
) -> dict[str, Any]:
    tickers = resolve_tickers(query, db_url)
    return {
        "tickers": tickers,
        "hint": format_entity_hint(tickers),
    }
