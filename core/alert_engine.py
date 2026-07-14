"""Đánh giá alert rules — chạy metric catalog, ghi event khi vượt ngưỡng."""

from __future__ import annotations

from typing import Any

from core.alert_metrics import (
    build_metric_sql,
    compare,
    format_alert_message,
    get_metric,
)
from core.alert_store import add_event, get_rule, list_rules, mark_rule_checked
from core.config_loader import load_domain_config
from core.db_executor import DbQueryError, execute_query


def _read_metric_value(rows: list[dict[str, Any]]) -> tuple[float | None, str | None]:
    if not rows:
        return None, None
    row = rows[0]
    raw = row.get("value")
    if raw is None:
        return None, str(row.get("label") or "") or None
    try:
        return float(raw), str(row.get("label") or "") or None
    except (TypeError, ValueError):
        return None, str(row.get("label") or "") or None


def evaluate_rule(rule: dict[str, Any]) -> dict[str, Any]:
    """
    Chạy 1 rule. Trả về status: ok | triggered | error | skipped.

    Event chỉ ghi khi có rising edge (chưa triggered → triggered) để
    scheduler không spam khi metric vẫn vượt ngưỡng.
    """
    if not rule.get("enabled", True):
        return {
            "rule_id": rule["id"],
            "status": "skipped",
            "triggered": False,
            "message": "Rule đang tắt",
        }

    # Đọc trạng thái mới nhất từ DB (rising edge)
    fresh = get_rule(rule["id"]) or rule
    was_triggered = bool(fresh.get("last_triggered"))

    domain_id = rule["domain_id"]
    metric = get_metric(domain_id, rule["metric_key"])
    if not metric:
        return {
            "rule_id": rule["id"],
            "status": "error",
            "triggered": False,
            "message": f"Metric không hỗ trợ: {rule['metric_key']}",
        }

    kind = str(metric.get("kind") or "threshold")

    try:
        cfg = load_domain_config(domain_id)
        sql = build_metric_sql(
            domain_id,
            rule["metric_key"],
            target=rule.get("target"),
            db_url=cfg["db_url"],
        )
        rows = execute_query(cfg["db_url"], sql)
        value, label = _read_metric_value(rows)
    except (ValueError, DbQueryError, FileNotFoundError) as exc:
        mark_rule_checked(rule["id"], value=None, triggered=False)
        return {
            "rule_id": rule["id"],
            "status": "error",
            "triggered": False,
            "message": str(exc)[:240],
        }

    if value is None:
        mark_rule_checked(rule["id"], value=None, triggered=False)
        return {
            "rule_id": rule["id"],
            "status": "error",
            "triggered": False,
            "message": "Không lấy được giá trị metric (thiếu dữ liệu).",
        }

    triggered = compare(value, rule["operator"], float(rule["threshold"]))
    mark_rule_checked(rule["id"], value=value, triggered=triggered)

    msg = format_alert_message(
        rule_name=rule["name"],
        metric_label=str(metric["label"]),
        operator=rule["operator"],
        threshold=float(rule["threshold"]),
        value=value,
        target=rule.get("target") or label,
        kind=kind,
    )

    result: dict[str, Any] = {
        "rule_id": rule["id"],
        "rule_name": rule["name"],
        "domain_id": domain_id,
        "metric_key": rule["metric_key"],
        "metric_kind": kind,
        "value": value,
        "threshold": float(rule["threshold"]),
        "operator": rule["operator"],
        "target": rule.get("target"),
        "triggered": triggered,
        "status": "triggered" if triggered else "ok",
        "message": msg,
        "new_event": False,
    }

    # Rising edge: chỉ tạo event khi vừa chuyển sang trạng thái kích hoạt
    if triggered and not was_triggered:
        event = add_event(
            rule_id=rule["id"],
            domain_id=domain_id,
            value=value,
            message=msg,
            payload={
                "label": label,
                "metric_label": metric["label"],
                "kind": kind,
            },
        )
        result["event_id"] = event["id"]
        result["new_event"] = True
    elif triggered and was_triggered:
        result["message"] = msg + " (đã cảnh báo trước — không tạo event mới)"

    return result


def run_alerts(domain_id: str | None = None) -> dict[str, Any]:
    """Chạy mọi rule (enabled) — có thể lọc theo domain."""
    rules = list_rules(domain_id)
    results = [evaluate_rule(r) for r in rules]
    triggered = [r for r in results if r.get("triggered")]
    new_events = [r for r in results if r.get("new_event")]
    errors = [r for r in results if r.get("status") == "error"]
    return {
        "checked": len(results),
        "triggered_count": len(triggered),
        "new_event_count": len(new_events),
        "error_count": len(errors),
        "results": results,
        "triggered": triggered,
    }
