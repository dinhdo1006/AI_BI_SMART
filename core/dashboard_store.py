"""Lưu dashboard đã pin — SQLite local trong .cache/."""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_LOCK = threading.Lock()
_DB_PATH = Path(__file__).resolve().parent.parent / ".cache" / "dashboards.db"


def _conn() -> sqlite3.Connection:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS dashboards (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            domain_id TEXT NOT NULL,
            created_at TEXT NOT NULL,
            payload TEXT NOT NULL
        )
        """
    )
    conn.commit()
    return conn


def create_dashboard(
    *,
    title: str,
    domain_id: str,
    reports: list[dict[str, Any]],
) -> dict[str, Any]:
    dash_id = uuid.uuid4().hex[:12]
    created = datetime.now(timezone.utc).isoformat()
    payload = {
        "id": dash_id,
        "title": title or "Dashboard",
        "domain_id": domain_id,
        "created_at": created,
        "reports": reports,
    }
    with _LOCK:
        conn = _conn()
        try:
            conn.execute(
                "INSERT INTO dashboards (id, title, domain_id, created_at, payload) VALUES (?,?,?,?,?)",
                (dash_id, payload["title"], domain_id, created, json.dumps(payload, ensure_ascii=False)),
            )
            conn.commit()
        finally:
            conn.close()
    return {"id": dash_id, **payload}


def get_dashboard(dash_id: str) -> dict[str, Any] | None:
    with _LOCK:
        conn = _conn()
        try:
            row = conn.execute(
                "SELECT payload FROM dashboards WHERE id = ?",
                (dash_id,),
            ).fetchone()
        finally:
            conn.close()
    if not row:
        return None
    try:
        return json.loads(row[0])
    except json.JSONDecodeError:
        return None
