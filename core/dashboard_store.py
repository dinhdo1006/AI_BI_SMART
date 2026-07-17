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
    if "is_public" not in cols:
        conn.execute(
            "ALTER TABLE dashboards ADD COLUMN is_public INTEGER NOT NULL DEFAULT 0"
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
    is_public: bool = False,
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
        "is_public": is_public,
    }
    with _LOCK:
        conn = _conn()
        try:
            conn.execute(
                """
                INSERT INTO dashboards
                (id, title, domain_id, created_at, payload, tenant_id, is_public)
                VALUES (?,?,?,?,?,?,?)
                """,
                (
                    dash_id,
                    payload["title"],
                    domain_id,
                    created,
                    json.dumps(payload, ensure_ascii=False),
                    tenant_id,
                    1 if is_public else 0,
                ),
            )
            conn.commit()
        finally:
            conn.close()
    return {"id": dash_id, **payload}


def set_dashboard_public(dash_id: str, is_public: bool) -> bool:
    """Bật/tắt public embed cho dashboard. Trả True nếu cập nhật thành công."""
    with _LOCK:
        conn = _conn()
        try:
            # Cập nhật cả payload và cột is_public
            row = conn.execute(
                "SELECT payload FROM dashboards WHERE id = ?", (dash_id,)
            ).fetchone()
            if not row:
                return False
            try:
                data = json.loads(row[0])
            except json.JSONDecodeError:
                data = {}
            data["is_public"] = is_public
            conn.execute(
                "UPDATE dashboards SET is_public = ?, payload = ? WHERE id = ?",
                (1 if is_public else 0, json.dumps(data, ensure_ascii=False), dash_id),
            )
            conn.commit()
            return True
        finally:
            conn.close()


def get_dashboard(
    dash_id: str,
    *,
    tenant_id: str | None = None,
    allow_public: bool = False,
) -> dict[str, Any] | None:
    with _LOCK:
        conn = _conn()
        try:
            row = conn.execute(
                "SELECT payload, tenant_id, is_public FROM dashboards WHERE id = ?",
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
    is_pub = bool(row[2])

    # Public embed — không cần kiểm tra tenant
    if allow_public and is_pub:
        return data

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
