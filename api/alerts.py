"""API Alert Engine — CRUD rules + chạy kiểm tra ngưỡng."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from core.alert_engine import evaluate_rule, run_alerts
from core.alert_metrics import get_metric, list_metrics, sanitize_target
from core.alert_scheduler import get_scheduler_status
from core.alert_store import (
    create_rule,
    delete_rule,
    get_rule,
    list_events,
    list_rules,
    update_rule,
)

router = APIRouter(prefix="/api/v1/alerts", tags=["alerts"])

Operator = Literal["gt", "gte", "lt", "lte", "eq"]


class AlertRuleCreate(BaseModel):
    domain_id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1, max_length=120)
    metric_key: str = Field(..., min_length=1)
    operator: Operator
    threshold: float
    target: str | None = None


class AlertRulePatch(BaseModel):
    enabled: bool | None = None
    name: str | None = Field(default=None, max_length=120)
    threshold: float | None = None


@router.get("/metrics")
def get_alert_metrics(domain_id: str) -> dict[str, Any]:
    """Catalog metric có thể đặt alert theo domain."""
    items = list_metrics(domain_id)
    if not items:
        raise HTTPException(
            status_code=404,
            detail=f"Domain '{domain_id}' chưa hỗ trợ alert metrics.",
        )
    return {"domain_id": domain_id, "metrics": items}


@router.get("/rules")
def get_alert_rules(domain_id: str | None = None) -> dict[str, Any]:
    return {"rules": list_rules(domain_id)}


@router.post("/rules")
def post_alert_rule(body: AlertRuleCreate) -> dict[str, Any]:
    metric = get_metric(body.domain_id, body.metric_key)
    if not metric:
        raise HTTPException(
            status_code=400,
            detail=f"Metric '{body.metric_key}' không hỗ trợ cho domain này.",
        )
    try:
        target = sanitize_target(body.target)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if metric.get("needs_target") and not target:
        raise HTTPException(
            status_code=400,
            detail=f"Metric này cần {metric.get('target_label', 'target')}.",
        )
    rule = create_rule(
        domain_id=body.domain_id,
        name=body.name,
        metric_key=body.metric_key,
        operator=body.operator,
        threshold=body.threshold,
        target=target,
    )
    return rule


@router.patch("/rules/{rule_id}")
def patch_alert_rule(rule_id: str, body: AlertRulePatch) -> dict[str, Any]:
    rule = update_rule(
        rule_id,
        enabled=body.enabled,
        name=body.name,
        threshold=body.threshold,
    )
    if not rule:
        raise HTTPException(status_code=404, detail="Rule không tồn tại")
    return rule


@router.delete("/rules/{rule_id}")
def remove_alert_rule(rule_id: str) -> dict[str, bool]:
    if not delete_rule(rule_id):
        raise HTTPException(status_code=404, detail="Rule không tồn tại")
    return {"ok": True}


@router.get("/scheduler")
def get_alert_scheduler() -> dict[str, Any]:
    """Trạng thái scheduler nền (ALERT_SCHEDULE_ENABLED)."""
    return get_scheduler_status()


@router.post("/run")
def run_alert_checks(domain_id: str | None = None) -> dict[str, Any]:
    """Kiểm tra tất cả rule (enabled). Có thể lọc theo domain_id."""
    return run_alerts(domain_id)


@router.post("/rules/{rule_id}/run")
def run_one_rule(rule_id: str) -> dict[str, Any]:
    rule = get_rule(rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule không tồn tại")
    return evaluate_rule(rule)


@router.get("/events")
def get_alert_events(
    domain_id: str | None = None,
    limit: int = 30,
) -> dict[str, Any]:
    return {"events": list_events(domain_id=domain_id, limit=limit)}
