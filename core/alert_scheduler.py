"""Scheduler nền — chạy Alert Engine định kỳ khi FastAPI sống."""

from __future__ import annotations

import logging
import os
import threading
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

_stop = threading.Event()
_thread: threading.Thread | None = None
_state: dict[str, Any] = {
    "enabled": False,
    "interval_minutes": 15,
    "running": False,
    "last_run_at": None,
    "last_result": None,
    "last_error": None,
}


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _interval_minutes() -> int:
    try:
        mins = int(os.getenv("ALERT_SCHEDULE_MINUTES", "15"))
    except ValueError:
        mins = 15
    return max(1, min(mins, 24 * 60))


def get_scheduler_status() -> dict[str, Any]:
    return {
        "enabled": bool(_state["enabled"]),
        "interval_minutes": int(_state["interval_minutes"]),
        "running": bool(_state["running"]),
        "last_run_at": _state["last_run_at"],
        "last_result": _state["last_result"],
        "last_error": _state["last_error"],
        "thread_alive": bool(_thread and _thread.is_alive()),
    }


def _tick() -> None:
    from core.alert_engine import run_alerts

    try:
        result = run_alerts()
        _state["last_run_at"] = datetime.now(timezone.utc).isoformat()
        _state["last_result"] = {
            "checked": result.get("checked", 0),
            "triggered_count": result.get("triggered_count", 0),
            "new_event_count": result.get("new_event_count", 0),
            "error_count": result.get("error_count", 0),
        }
        _state["last_error"] = None
        logger.info(
            "Alert schedule: checked=%s new_events=%s errors=%s",
            result.get("checked"),
            result.get("new_event_count"),
            result.get("error_count"),
        )
    except Exception as exc:  # noqa: BLE001 — không làm chết thread
        _state["last_error"] = str(exc)[:240]
        logger.exception("Alert schedule failed: %s", exc)


def _loop(interval_sec: float) -> None:
    # Chạy một lần sau khi start (đợi ngắn) rồi lặp theo interval
    if _stop.wait(5.0):
        return
    while not _stop.is_set():
        _tick()
        if _stop.wait(interval_sec):
            break


def start_scheduler() -> dict[str, Any]:
    """Bật background thread nếu ALERT_SCHEDULE_ENABLED=true."""
    global _thread
    enabled = _env_bool("ALERT_SCHEDULE_ENABLED", default=False)
    minutes = _interval_minutes()
    _state["enabled"] = enabled
    _state["interval_minutes"] = minutes
    _state["last_error"] = None

    if not enabled:
        _state["running"] = False
        logger.info("Alert scheduler tắt (ALERT_SCHEDULE_ENABLED≠true)")
        return get_scheduler_status()

    if _thread and _thread.is_alive():
        return get_scheduler_status()

    _stop.clear()
    _thread = threading.Thread(
        target=_loop,
        args=(float(minutes * 60),),
        name="alert-scheduler",
        daemon=True,
    )
    _thread.start()
    _state["running"] = True
    logger.info("Alert scheduler bật — mỗi %s phút", minutes)
    return get_scheduler_status()


def stop_scheduler() -> None:
    global _thread
    _stop.set()
    if _thread and _thread.is_alive():
        _thread.join(timeout=2.0)
    _thread = None
    _state["running"] = False
