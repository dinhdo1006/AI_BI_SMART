"""Lưu bài báo tự động — JSON file data/auto_articles.json."""

from __future__ import annotations

import json
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_LOCK = threading.Lock()
_STORE_PATH = Path(__file__).resolve().parent.parent / "data" / "auto_articles.json"

_DEFAULT: dict[str, Any] = {
    "articles": [],
    "last_seen": {
        "max_trade_date": None,
        "max_fiscal_key": None,
        # Fingerprint để bắt cập nhật trong cùng ngày / cùng kỳ BCTC
        "market_fingerprint": None,
        "fiscal_fingerprint": None,
    },
    "meta": {
        "last_daily_key": None,
        "last_weekly_key": None,
    },
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _local_now_str() -> str:
    return datetime.now().strftime("%d/%m/%Y %H:%M")


def dedup_key(template_id: str, data_date: str) -> str:
    return f"{(template_id or '').strip()}:{(data_date or '').strip()}"


def _ensure_store() -> dict[str, Any]:
    _STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not _STORE_PATH.is_file():
        data = json.loads(json.dumps(_DEFAULT))
        _write_unlocked(data)
        return data
    try:
        with _STORE_PATH.open(encoding="utf-8") as fh:
            raw = json.load(fh)
    except (OSError, json.JSONDecodeError):
        data = json.loads(json.dumps(_DEFAULT))
        _write_unlocked(data)
        return data
    if not isinstance(raw, dict):
        data = json.loads(json.dumps(_DEFAULT))
        _write_unlocked(data)
        return data
    raw.setdefault("articles", [])
    raw.setdefault("last_seen", dict(_DEFAULT["last_seen"]))
    raw.setdefault("meta", dict(_DEFAULT["meta"]))
    if not isinstance(raw["articles"], list):
        raw["articles"] = []
    return raw


def _write_unlocked(data: dict[str, Any]) -> None:
    _STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = _STORE_PATH.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
    tmp.replace(_STORE_PATH)


def load_store() -> dict[str, Any]:
    with _LOCK:
        return _ensure_store()


def get_last_seen() -> dict[str, Any]:
    with _LOCK:
        data = _ensure_store()
        return dict(data.get("last_seen") or {})


def update_last_seen(
    *,
    max_trade_date: str | None = None,
    max_fiscal_key: str | None = None,
    market_fingerprint: str | None = None,
    fiscal_fingerprint: str | None = None,
) -> dict[str, Any]:
    with _LOCK:
        data = _ensure_store()
        seen = data.setdefault("last_seen", {})
        if max_trade_date is not None:
            seen["max_trade_date"] = max_trade_date
        if max_fiscal_key is not None:
            seen["max_fiscal_key"] = max_fiscal_key
        if market_fingerprint is not None:
            seen["market_fingerprint"] = market_fingerprint
        if fiscal_fingerprint is not None:
            seen["fiscal_fingerprint"] = fiscal_fingerprint
        _write_unlocked(data)
        return dict(seen)


def get_meta() -> dict[str, Any]:
    with _LOCK:
        data = _ensure_store()
        return dict(data.get("meta") or {})


def update_meta(**kwargs: Any) -> dict[str, Any]:
    with _LOCK:
        data = _ensure_store()
        meta = data.setdefault("meta", {})
        for k, v in kwargs.items():
            if v is not None:
                meta[k] = v
        _write_unlocked(data)
        return dict(meta)


def has_article(template_id: str, data_date: str) -> bool:
    key = dedup_key(template_id, data_date)
    with _LOCK:
        data = _ensure_store()
        for item in data.get("articles") or []:
            if not isinstance(item, dict):
                continue
            if dedup_key(str(item.get("template_id") or ""), str(item.get("data_date") or "")) == key:
                return True
    return False


def save_article(
    *,
    template_id: str,
    template_name: str,
    data_date: str,
    article_markdown: str,
    domain_id: str,
    question: str,
    trigger: str,
    word_count: int = 0,
    outline: dict[str, Any] | None = None,
    force: bool = False,
) -> dict[str, Any] | None:
    """
    Lưu bài. Trả None nếu trùng (template_id, data_date) và force=False.
    """
    key = dedup_key(template_id, data_date)
    with _LOCK:
        data = _ensure_store()
        articles: list[dict[str, Any]] = list(data.get("articles") or [])
        if not force:
            for item in articles:
                if (
                    dedup_key(
                        str(item.get("template_id") or ""),
                        str(item.get("data_date") or ""),
                    )
                    == key
                ):
                    return None

        # force: xóa bản cũ cùng key
        if force:
            articles = [
                a
                for a in articles
                if dedup_key(
                    str(a.get("template_id") or ""),
                    str(a.get("data_date") or ""),
                )
                != key
            ]

        generated_at = _local_now_str()
        record = {
            "id": uuid.uuid4().hex[:12],
            "dedup_key": key,
            "template_id": template_id,
            "template_name": template_name,
            "data_date": data_date,
            "domain_id": domain_id,
            "question": question,
            "trigger": trigger,
            "article_markdown": article_markdown,
            "word_count": int(word_count or 0),
            "outline": outline or {},
            "generated_at": generated_at,
            "created_at": _utc_now(),
        }
        articles.insert(0, record)
        # Giữ tối đa 200 bài gần nhất
        data["articles"] = articles[:200]
        _write_unlocked(data)
        return dict(record)


def get_article(article_id: str) -> dict[str, Any] | None:
    aid = (article_id or "").strip()
    with _LOCK:
        data = _ensure_store()
        for item in data.get("articles") or []:
            if isinstance(item, dict) and str(item.get("id") or "") == aid:
                return dict(item)
    return None


def list_articles(
    *,
    domain_id: str | None = None,
    limit: int = 30,
) -> list[dict[str, Any]]:
    limit = max(1, min(int(limit), 100))
    with _LOCK:
        data = _ensure_store()
        items = [a for a in (data.get("articles") or []) if isinstance(a, dict)]
    if domain_id:
        items = [a for a in items if str(a.get("domain_id") or "") == domain_id]
    # đã insert đầu danh sách = mới nhất
    return [dict(a) for a in items[:limit]]
