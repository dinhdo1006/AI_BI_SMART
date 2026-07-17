"""Peer-group + Technical Analysis SQL helpers cho VNFDATA (Postgres)."""

from __future__ import annotations

import re
import unicodedata
from typing import Any

from core.entity_resolver import resolve_tickers

_PEER_RE = re.compile(
    r"("
    r"c[uù]ng\s*ng[aà]nh|"
    r"peer\s*group|peers?\b|"
    r"so\s*s[aá]nh\s*(c[uù]ng\s*)?(ng[aà]nh|sector)|"
    r"c[aá]c\s*m[aã]\s*(c[uù]ng|trong)\s*ng[aà]nh|"
    r"ng[aà]nh\s*(c[uù]a|v[ớơ]i)\s*"
    r")",
    re.IGNORECASE,
)

_TA_RE = re.compile(
    r"("
    r"\brsi\b|\bmacd\b|bollinger|bolinger|"
    r"ch[ỉi]\s*b[aá]o\s*k[ỹy]\s*thu[ậa]t|"
    r"technical\s*analysis|\bta\b|"
    r"\bma\s*20\b|\bma\s*50\b|\bma\s*200\b|"
    r"\batr\b|\badx\b|stochastic|"
    r"đ[ươuo]ờng\s*trung\s*b[ìi]nh\s*(đ[ộngong]|ma)"
    r")",
    re.IGNORECASE,
)

_VP_RE = re.compile(
    r"("
    r"volume\s*profile|ph[aâ]n\s*b[ốo]\s*kh[ốo]i\s*l[ươu][ợo]ng|"
    r"kh[ốo]i\s*l[ươu][ợo]ng\s*theo\s*gi[aá]|"
    r"gi[aá]\s*c[ốo]\s*kh[ốo]i\s*l[ươu][ợo]ng\s*l[ớo]n|"
    r"poc\b|value\s*area|vah\b|val\b|hvn\b|lvn\b"
    r")",
    re.IGNORECASE,
)


def _normalize(text: str) -> str:
    lowered = (text or "").lower()
    nfd = unicodedata.normalize("NFD", lowered)
    return "".join(c for c in nfd if unicodedata.category(c) != "Mn")


def is_peer_group_query(query: str) -> bool:
    return bool(_PEER_RE.search(query or ""))


def is_technical_analysis_query(query: str) -> bool:
    return bool(_TA_RE.search(query or ""))


def is_volume_profile_query(query: str) -> bool:
    return bool(_VP_RE.search(query or ""))


def _escape_ticker(ticker: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", (ticker or "").upper())[:10]


def build_peer_group_sql(ticker: str, *, limit: int = 12) -> str:
    """So sánh chỉ số định giá của mã neo với các mã cùng sector_id."""
    t = _escape_ticker(ticker)
    n = max(3, min(int(limit), 20))
    return f"""
WITH anchor AS (
  SELECT c.id, c.ticker, c.sector_id
  FROM companies c
  WHERE UPPER(c.ticker) = '{t}'
  LIMIT 1
),
latest AS (
  SELECT MAX(calc_date) AS d FROM financial_indicators
)
SELECT
  c.ticker AS ticker,
  c.company_name AS company_name,
  s.name AS sector_name,
  fi.pe_ratio AS pe_ratio,
  fi.pb_ratio AS pb_ratio,
  fi.roe AS roe,
  fi.roa AS roa,
  fi.market_cap AS market_cap,
  fi.eps_ttm AS eps_ttm,
  fi.calc_date AS calc_date,
  CASE WHEN UPPER(c.ticker) = '{t}' THEN TRUE ELSE FALSE END AS is_anchor
FROM companies c
JOIN anchor a ON a.sector_id IS NOT NULL AND c.sector_id = a.sector_id
LEFT JOIN sectors s ON s.id = c.sector_id
JOIN financial_indicators fi ON fi.symbol = c.ticker
JOIN latest l ON fi.calc_date = l.d
ORDER BY fi.market_cap DESC NULLS LAST
LIMIT {n}
""".strip()


def build_technical_analysis_sql(
    ticker: str,
    *,
    days: int = 60,
    interval: str = "1d",
) -> str:
    """Chuỗi chỉ báo kỹ thuật (RSI/MACD/MA/Bollinger) theo ngày."""
    t = _escape_ticker(ticker)
    n = max(20, min(int(days), 180))
    iv = re.sub(r"[^a-z0-9]", "", (interval or "1d").lower()) or "1d"
    inner = f"""
SELECT
  ti.ticker AS ticker,
  ti.calc_date AS calc_date,
  ti.interval AS interval,
  ti.rsi AS rsi,
  ti.macd AS macd,
  ti.signal_line AS signal_line,
  ti.histogram AS histogram,
  ti.ma20 AS ma20,
  ti.ma50 AS ma50,
  ti.ma200 AS ma200,
  ti.bollinger_upper AS bollinger_upper,
  ti.bollinger_lower AS bollinger_lower,
  ti.atr AS atr,
  ti.adx AS adx
FROM technical_indicators ti
WHERE UPPER(ti.ticker) = '{t}'
  AND ti.interval = '{iv}'
ORDER BY ti.calc_date DESC
LIMIT {n}
""".strip()
    return (
        f"SELECT * FROM ({inner}) AS _ta "
        f"ORDER BY calc_date ASC"
    )


def build_volume_profile_sql(ticker: str, *, days: int = 60, buckets: int = 20) -> str:
    """
    Volume Profile: gom khối lượng giao dịch theo dải giá (price bucket).
    Trả (price_bucket, total_volume, trade_count) sắp xếp từ giá thấp → cao.
    Dùng bảng price_history (trade_date, ticker, close_price, volume).
    """
    t = _escape_ticker(ticker)
    n = max(10, min(int(days), 252))
    b = max(5, min(int(buckets), 50))
    return f"""
WITH recent AS (
  SELECT
    close_price,
    volume
  FROM price_history
  WHERE UPPER(ticker) = '{t}'
    AND trade_date >= CURRENT_DATE - INTERVAL '{n} days'
    AND close_price > 0
    AND volume > 0
),
bounds AS (
  SELECT MIN(close_price) AS lo, MAX(close_price) AS hi FROM recent
),
bucketed AS (
  SELECT
    ROUND(
      bounds.lo + (bounds.hi - bounds.lo) * (
        FLOOR({b} * (r.close_price - bounds.lo) / NULLIF(bounds.hi - bounds.lo, 0))
        / {b}.0
      ),
      2
    ) AS price_bucket,
    r.volume
  FROM recent r, bounds
)
SELECT
  price_bucket,
  SUM(volume)          AS total_volume,
  COUNT(*)             AS trade_count
FROM bucketed
GROUP BY price_bucket
ORDER BY price_bucket ASC
""".strip()


def try_finance_analytics_sql(
    user_query: str,
    *,
    db_url: str | None = None,
) -> dict[str, Any] | None:
    """
    Trả {sql, kind, ticker} nếu nhận diện peer/TA; None nếu không khớp.
    """
    q = (user_query or "").strip()
    if not q:
        return None

    tickers = resolve_tickers(q, db_url)
    ticker = tickers[0] if tickers else None

    if is_peer_group_query(q):
        if not ticker:
            return None
        return {
            "kind": "peer_group",
            "ticker": ticker,
            "sql": build_peer_group_sql(ticker),
        }

    if is_technical_analysis_query(q):
        if not ticker:
            return None
        days = 60
        m = re.search(r"(\d+)\s*(phiên|phien|ngày|ngay|day|days)", _normalize(q))
        if m:
            days = max(20, min(int(m.group(1)), 180))
        return {
            "kind": "technical_analysis",
            "ticker": ticker,
            "sql": build_technical_analysis_sql(ticker, days=days),
        }

    if is_volume_profile_query(q):
        if not ticker:
            return None
        days = 60
        m = re.search(r"(\d+)\s*(phiên|phien|ngày|ngay|day|days)", _normalize(q))
        if m:
            days = max(10, min(int(m.group(1)), 252))
        buckets = 20
        mb = re.search(r"(\d+)\s*(bucket|d[aả]i|mức|thanh)", _normalize(q))
        if mb:
            buckets = max(5, min(int(mb.group(1)), 50))
        return {
            "kind": "volume_profile",
            "ticker": ticker,
            "sql": build_volume_profile_sql(ticker, days=days, buckets=buckets),
        }

    return None
