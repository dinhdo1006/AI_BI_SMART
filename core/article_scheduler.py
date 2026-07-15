"""Scheduler nền — tự viết bài VNFDATA theo giờ cố định + polling DB."""

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
    "daily_enabled": True,
    "weekly_enabled": True,
    "daily_time": "15:20",
    "weekly_time": "08:30",
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
        mins = int(os.getenv("ARTICLE_POLL_MINUTES", "15"))
    except ValueError:
        mins = 15
    return max(1, min(mins, 24 * 60))


def _parse_hhmm(raw: str, fallback: str) -> tuple[int, int]:
    text = (raw or fallback).strip() or fallback
    try:
        hh_s, mm_s = text.split(":", 1)
        hh, mm = int(hh_s), int(mm_s)
        if 0 <= hh <= 23 and 0 <= mm <= 59:
            return hh, mm
    except (ValueError, TypeError):
        pass
    fb_h, fb_m = fallback.split(":")
    return int(fb_h), int(fb_m)


def get_scheduler_status() -> dict[str, Any]:
    return {
        "enabled": bool(_state["enabled"]),
        "interval_minutes": int(_state["interval_minutes"]),
        "running": bool(_state["running"]),
        "daily_enabled": bool(_state["daily_enabled"]),
        "weekly_enabled": bool(_state["weekly_enabled"]),
        "intraday_enabled": _env_bool("ARTICLE_INTRADAY_ENABLED", default=True),
        "daily_time": str(_state["daily_time"]),
        "weekly_time": str(_state["weekly_time"]),
        "last_run_at": _state["last_run_at"],
        "last_result": _state["last_result"],
        "last_error": _state["last_error"],
        "thread_alive": bool(_thread and _thread.is_alive()),
    }


def _in_time_window(now: datetime, hh: int, mm: int, window_minutes: int = 20) -> bool:
    """True nếu now nằm trong [target, target+window) cùng ngày."""
    target_mins = hh * 60 + mm
    now_mins = now.hour * 60 + now.minute
    return target_mins <= now_mins < target_mins + window_minutes


def run_scheduled_checks() -> dict[str, Any]:
    """
    Một tick: time-based (daily/weekly) + DB poll (market + BCTC).
    An toàn gọi từ API thủ công.
    """
    from core.article_job import (
        DOMAIN_ID,
        fetch_fiscal_watermark,
        fetch_market_watermark,
        fetch_max_trade_date,
        make_intraday_data_date,
        run_article_job,
    )
    from core.article_store import get_last_seen, get_meta, update_last_seen, update_meta

    now = datetime.now()
    jobs: list[dict[str, Any]] = []
    errors = 0

    daily_enabled = _env_bool("ARTICLE_DAILY_ENABLED", default=True)
    weekly_enabled = _env_bool("ARTICLE_WEEKLY_ENABLED", default=True)
    intraday_enabled = _env_bool("ARTICLE_INTRADAY_ENABLED", default=True)
    daily_hh, daily_mm = _parse_hhmm(
        os.getenv("ARTICLE_DAILY_TIME", "15:20"), "15:20"
    )
    weekly_hh, weekly_mm = _parse_hhmm(
        os.getenv("ARTICLE_WEEKLY_TIME", "08:30"), "08:30"
    )

    meta = get_meta()
    today_key = now.strftime("%Y-%m-%d")
    # ISO weekday: Mon=0 … Sun=6
    week_key = now.strftime("%G-W%V")

    # --- Daily schedule ---
    if daily_enabled and _in_time_window(now, daily_hh, daily_mm):
        if meta.get("last_daily_key") != today_key:
            trade_date = fetch_max_trade_date(DOMAIN_ID) or today_key
            result = run_article_job(
                template_id="market_01",
                domain_id=DOMAIN_ID,
                data_date=trade_date,
                trigger="schedule_daily",
            )
            jobs.append({"job": "daily_market_01", **result})
            if result.get("status") == "error":
                errors += 1
            if result.get("status") in {"ok", "skipped"}:
                update_meta(last_daily_key=today_key)

    # --- Weekly schedule (Monday) ---
    if (
        weekly_enabled
        and now.weekday() == 0
        and _in_time_window(now, weekly_hh, weekly_mm)
    ):
        if meta.get("last_weekly_key") != week_key:
            trade_date = fetch_max_trade_date(DOMAIN_ID) or today_key
            result = run_article_job(
                template_id="market_14",
                domain_id=DOMAIN_ID,
                data_date=f"week:{trade_date}",
                trigger="schedule_weekly",
            )
            jobs.append({"job": "weekly_market_14", **result})
            if result.get("status") == "error":
                errors += 1
            if result.get("status") in {"ok", "skipped"}:
                update_meta(last_weekly_key=week_key)

    # --- DB poll: stock prices (ngày mới + cập nhật trong ngày) ---
    seen = get_last_seen()
    market_wm = fetch_market_watermark(DOMAIN_ID)
    if market_wm:
        max_trade = str(market_wm["trade_date"])
        market_fp = str(market_wm["fingerprint"])
        prev_date = seen.get("max_trade_date")
        prev_fp = seen.get("market_fingerprint")
        market_changed = market_fp != prev_fp
        if market_changed:
            if max_trade != prev_date:
                # Phiên / ngày giao dịch mới
                data_date = max_trade
                force = False
                trigger = "db_poll"
            elif intraday_enabled:
                # Cùng ngày nhưng số liệu đã đổi (nạp thêm / sửa lệnh…)
                data_date = make_intraday_data_date(max_trade, now)
                force = True  # ghi đè bài cùng khung giờ nếu poll lại
                trigger = "db_poll_intraday"
            else:
                # Không viết lại trong ngày — vẫn cập nhật fingerprint để khỏi spam
                update_last_seen(
                    max_trade_date=max_trade,
                    market_fingerprint=market_fp,
                )
                data_date = ""
                force = False
                trigger = "db_poll"

            if data_date:
                result = run_article_job(
                    template_id="market_01",
                    domain_id=DOMAIN_ID,
                    data_date=data_date,
                    trigger=trigger,
                    force=force,
                )
                jobs.append({"job": "poll_market_01", **result})
                if result.get("status") == "error":
                    errors += 1
                else:
                    update_last_seen(
                        max_trade_date=max_trade,
                        market_fingerprint=market_fp,
                    )

    # --- DB poll: BCTC quý/năm (kỳ mới + nạp thêm DN trong kỳ) ---
    fiscal_wm = fetch_fiscal_watermark(DOMAIN_ID)
    if fiscal_wm:
        max_fiscal = str(fiscal_wm["fiscal_key"])
        fiscal_fp = str(fiscal_wm["fingerprint"])
        # Đọc lại sau khi market có thể vừa update last_seen
        seen = get_last_seen()
        prev_fiscal = seen.get("max_fiscal_key")
        prev_ffp = seen.get("fiscal_fingerprint")
        if fiscal_fp != prev_ffp:
            if max_fiscal != prev_fiscal:
                data_date = max_fiscal
                force = False
                trigger = "db_poll"
            elif intraday_enabled:
                data_date = f"{max_fiscal}T{now.strftime('%H')}"
                force = True
                trigger = "db_poll_intraday"
            else:
                update_last_seen(
                    max_fiscal_key=max_fiscal,
                    fiscal_fingerprint=fiscal_fp,
                )
                data_date = ""
                force = False
                trigger = "db_poll"

            if data_date:
                result = run_article_job(
                    template_id="company_01",
                    domain_id=DOMAIN_ID,
                    data_date=data_date,
                    trigger=trigger,
                    force=force,
                )
                jobs.append({"job": "poll_company_01", **result})
                if result.get("status") == "error":
                    errors += 1
                else:
                    update_last_seen(
                        max_fiscal_key=max_fiscal,
                        fiscal_fingerprint=fiscal_fp,
                    )

    ok_count = sum(1 for j in jobs if j.get("status") == "ok")
    skip_count = sum(1 for j in jobs if j.get("status") == "skipped")
    summary = {
        "checked": len(jobs),
        "ok_count": ok_count,
        "skipped_count": skip_count,
        "error_count": errors,
        "jobs": [
            {
                "job": j.get("job"),
                "status": j.get("status"),
                "template_id": j.get("template_id"),
                "data_date": j.get("data_date"),
                "message": j.get("message"),
                "article_id": (j.get("article") or {}).get("id")
                if isinstance(j.get("article"), dict)
                else None,
            }
            for j in jobs
        ],
    }
    return summary


def _tick() -> None:
    try:
        result = run_scheduled_checks()
        _state["last_run_at"] = datetime.now(timezone.utc).isoformat()
        _state["last_result"] = {
            "checked": result.get("checked", 0),
            "ok_count": result.get("ok_count", 0),
            "skipped_count": result.get("skipped_count", 0),
            "error_count": result.get("error_count", 0),
        }
        _state["last_error"] = None
        logger.info(
            "Article schedule: checked=%s ok=%s skipped=%s errors=%s",
            result.get("checked"),
            result.get("ok_count"),
            result.get("skipped_count"),
            result.get("error_count"),
        )
    except Exception as exc:  # noqa: BLE001
        _state["last_error"] = str(exc)[:240]
        logger.exception("Article schedule failed: %s", exc)


def _loop(interval_sec: float) -> None:
    if _stop.wait(8.0):
        return
    while not _stop.is_set():
        _tick()
        if _stop.wait(interval_sec):
            break


def start_scheduler() -> dict[str, Any]:
    """Bật background thread nếu ARTICLE_SCHEDULE_ENABLED=true."""
    global _thread
    enabled = _env_bool("ARTICLE_SCHEDULE_ENABLED", default=False)
    minutes = _interval_minutes()
    _state["enabled"] = enabled
    _state["interval_minutes"] = minutes
    _state["daily_enabled"] = _env_bool("ARTICLE_DAILY_ENABLED", default=True)
    _state["weekly_enabled"] = _env_bool("ARTICLE_WEEKLY_ENABLED", default=True)
    _state["daily_time"] = (os.getenv("ARTICLE_DAILY_TIME") or "15:20").strip()
    _state["weekly_time"] = (os.getenv("ARTICLE_WEEKLY_TIME") or "08:30").strip()
    _state["last_error"] = None

    if not enabled:
        _state["running"] = False
        logger.info("Article scheduler tắt (ARTICLE_SCHEDULE_ENABLED≠true)")
        return get_scheduler_status()

    if _thread and _thread.is_alive():
        return get_scheduler_status()

    _stop.clear()
    _thread = threading.Thread(
        target=_loop,
        args=(float(minutes * 60),),
        name="article-scheduler",
        daemon=True,
    )
    _thread.start()
    _state["running"] = True
    logger.info("Article scheduler bật — mỗi %s phút", minutes)
    return get_scheduler_status()


def stop_scheduler() -> None:
    global _thread
    _stop.set()
    if _thread and _thread.is_alive():
        _thread.join(timeout=2.0)
    _thread = None
    _state["running"] = False
