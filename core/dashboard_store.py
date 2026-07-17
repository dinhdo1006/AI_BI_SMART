"""Lưu dashboard đã pin — SQLite local trong .cache/ (có tenant_id)."""

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
    cols = {
        str(r[1]) for r in conn.execute("PRAGMA table_info(dashboards)").fetchall()
    }
    if "tenant_id" not in cols:
        conn.execute(
            "ALTER TABLE dashboards ADD COLUMN tenant_id TEXT DEFAULT NULL"
        )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_dash_tenant ON dashboards(tenant_id)"
    )
    conn.commit()
    return conn


def create_dashboard(
    *,
    title: str,
    domain_id: str,
    reports: list[dict[str, Any]],
    tenant_id: str | None = None,
) -> dict[str, Any]:
    dash_id = uuid.uuid4().hex[:12]
    created = datetime.now(timezone.utc).isoformat()
    payload = {
        "id": dash_id,
        "title": title or "Dashboard",
        "domain_id": domain_id,
        "tenant_id": tenant_id,
        "created_at": created,
        "reports": reports,
    }
    with _LOCK:
        conn = _conn()
        try:
            conn.execute(
                """
                INSERT INTO dashboards
                (id, title, domain_id, created_at, payload, tenant_id)
                VALUES (?,?,?,?,?,?)
                """,
                (
                    dash_id,
                    payload["title"],
                    domain_id,
                    created,
                    json.dumps(payload, ensure_ascii=False),
                    tenant_id,
                ),
            )
            conn.commit()
        finally:
            conn.close()
    return {"id": dash_id, **payload}


def get_dashboard(
    dash_id: str,
    *,
    tenant_id: str | None = None,
) -> dict[str, Any] | None:
    with _LOCK:
        conn = _conn()
        try:
            row = conn.execute(
                "SELECT payload, tenant_id FROM dashboards WHERE id = ?",
                (dash_id,),
            ).fetchone()
        finally:
            conn.close()
    if not row:
        return None
    try:
        data = json.loads(row[0])
    except json.JSONDecodeError:
        return None
    owner = row[1] or data.get("tenant_id")
    # Cô lập tenant: nếu dashboard có owner và request có tenant khác → ẩn
    if (
        tenant_id
        and tenant_id not in ("platform",)
        and owner
        and owner != tenant_id
    ):
        return None
    return data
