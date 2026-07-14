"""Lưu alert rules + events — SQLite local trong .cache/."""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_LOCK = threading.Lock()
_DB_PATH = Path(__file__).resolve().parent.parent / ".cache" / "alerts.db"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _conn() -> sqlite3.Connection:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS alert_rules (
            id TEXT PRIMARY KEY,
            domain_id TEXT NOT NULL,
            name TEXT NOT NULL,
            metric_key TEXT NOT NULL,
            operator TEXT NOT NULL,
            threshold REAL NOT NULL,
            target TEXT,
            enabled INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            last_checked_at TEXT,
            last_value REAL,
            last_triggered INTEGER NOT NULL DEFAULT 0
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS alert_events (
            id TEXT PRIMARY KEY,
            rule_id TEXT NOT NULL,
            domain_id TEXT NOT NULL,
            triggered_at TEXT NOT NULL,
            value REAL NOT NULL,
            message TEXT NOT NULL,
            payload TEXT,
            FOREIGN KEY (rule_id) REFERENCES alert_rules(id) ON DELETE CASCADE
        )
        """
    )
    conn.commit()
    return conn


def _row_to_rule(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "domain_id": row["domain_id"],
        "name": row["name"],
        "metric_key": row["metric_key"],
        "operator": row["operator"],
        "threshold": float(row["threshold"]),
        "target": row["target"],
        "enabled": bool(row["enabled"]),
        "created_at": row["created_at"],
        "last_checked_at": row["last_checked_at"],
        "last_value": (
            float(row["last_value"]) if row["last_value"] is not None else None
        ),
        "last_triggered": bool(row["last_triggered"]),
    }


def create_rule(
    *,
    domain_id: str,
    name: str,
    metric_key: str,
    operator: str,
    threshold: float,
    target: str | None = None,
) -> dict[str, Any]:
    rule_id = uuid.uuid4().hex[:12]
    created = _utc_now()
    with _LOCK:
        conn = _conn()
        try:
            conn.execute(
                """
                INSERT INTO alert_rules
                (id, domain_id, name, metric_key, operator, threshold, target,
                 enabled, created_at, last_triggered)
                VALUES (?,?,?,?,?,?,?,1,?,0)
                """,
                (
                    rule_id,
                    domain_id,
                    name.strip() or "Alert",
                    metric_key,
                    operator,
                    float(threshold),
                    target,
                    created,
                ),
            )
            conn.commit()
        finally:
            conn.close()
    return get_rule(rule_id)  # type: ignore[return-value]


def get_rule(rule_id: str) -> dict[str, Any] | None:
    with _LOCK:
        conn = _conn()
        try:
            row = conn.execute(
                "SELECT * FROM alert_rules WHERE id = ?",
                (rule_id,),
            ).fetchone()
        finally:
            conn.close()
    return _row_to_rule(row) if row else None


def list_rules(domain_id: str | None = None) -> list[dict[str, Any]]:
    with _LOCK:
        conn = _conn()
        try:
            if domain_id:
                rows = conn.execute(
                    "SELECT * FROM alert_rules WHERE domain_id = ? "
                    "ORDER BY created_at DESC",
                    (domain_id,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM alert_rules ORDER BY created_at DESC"
                ).fetchall()
        finally:
            conn.close()
    return [_row_to_rule(r) for r in rows]


def update_rule(
    rule_id: str,
    *,
    enabled: bool | None = None,
    name: str | None = None,
    threshold: float | None = None,
) -> dict[str, Any] | None:
    rule = get_rule(rule_id)
    if not rule:
        return None
    fields: list[str] = []
    values: list[Any] = []
    if enabled is not None:
        fields.append("enabled = ?")
        values.append(1 if enabled else 0)
    if name is not None:
        fields.append("name = ?")
        values.append(name.strip() or rule["name"])
    if threshold is not None:
        fields.append("threshold = ?")
        values.append(float(threshold))
    if not fields:
        return rule
    values.append(rule_id)
    with _LOCK:
        conn = _conn()
        try:
            conn.execute(
                f"UPDATE alert_rules SET {', '.join(fields)} WHERE id = ?",
                values,
            )
            conn.commit()
        finally:
            conn.close()
    return get_rule(rule_id)


def delete_rule(rule_id: str) -> bool:
    with _LOCK:
        conn = _conn()
        try:
            conn.execute("DELETE FROM alert_events WHERE rule_id = ?", (rule_id,))
            cur = conn.execute("DELETE FROM alert_rules WHERE id = ?", (rule_id,))
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()


def mark_rule_checked(
    rule_id: str,
    *,
    value: float | None,
    triggered: bool,
) -> None:
    with _LOCK:
        conn = _conn()
        try:
            conn.execute(
                """
                UPDATE alert_rules
                SET last_checked_at = ?, last_value = ?, last_triggered = ?
                WHERE id = ?
                """,
                (_utc_now(), value, 1 if triggered else 0, rule_id),
            )
            conn.commit()
        finally:
            conn.close()


def add_event(
    *,
    rule_id: str,
    domain_id: str,
    value: float,
    message: str,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    event_id = uuid.uuid4().hex[:12]
    triggered_at = _utc_now()
    with _LOCK:
        conn = _conn()
        try:
            conn.execute(
                """
                INSERT INTO alert_events
                (id, rule_id, domain_id, triggered_at, value, message, payload)
                VALUES (?,?,?,?,?,?,?)
                """,
                (
                    event_id,
                    rule_id,
                    domain_id,
                    triggered_at,
                    float(value),
                    message,
                    json.dumps(payload or {}, ensure_ascii=False),
                ),
            )
            conn.commit()
        finally:
            conn.close()
    return {
        "id": event_id,
        "rule_id": rule_id,
        "domain_id": domain_id,
        "triggered_at": triggered_at,
        "value": float(value),
        "message": message,
        "payload": payload or {},
    }


def list_events(
    *,
    domain_id: str | None = None,
    limit: int = 30,
) -> list[dict[str, Any]]:
    limit = max(1, min(int(limit), 100))
    with _LOCK:
        conn = _conn()
        try:
            if domain_id:
                rows = conn.execute(
                    """
                    SELECT e.*, r.name AS rule_name, r.metric_key, r.operator,
                           r.threshold, r.target
                    FROM alert_events e
                    JOIN alert_rules r ON r.id = e.rule_id
                    WHERE e.domain_id = ?
                    ORDER BY e.triggered_at DESC
                    LIMIT ?
                    """,
                    (domain_id, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT e.*, r.name AS rule_name, r.metric_key, r.operator,
                           r.threshold, r.target
                    FROM alert_events e
                    JOIN alert_rules r ON r.id = e.rule_id
                    ORDER BY e.triggered_at DESC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
        finally:
            conn.close()

    out: list[dict[str, Any]] = []
    for row in rows:
        payload: dict[str, Any] = {}
        if row["payload"]:
            try:
                payload = json.loads(row["payload"])
            except json.JSONDecodeError:
                payload = {}
        out.append(
            {
                "id": row["id"],
                "rule_id": row["rule_id"],
                "rule_name": row["rule_name"],
                "domain_id": row["domain_id"],
                "triggered_at": row["triggered_at"],
                "value": float(row["value"]),
                "message": row["message"],
                "metric_key": row["metric_key"],
                "operator": row["operator"],
                "threshold": float(row["threshold"]),
                "target": row["target"],
                "payload": payload,
            }
        )
    return out
