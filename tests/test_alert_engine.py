"""Tests Alert Engine — metrics, store, evaluate, scheduler (finance)."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from core.alert_engine import evaluate_rule, run_alerts
from core.alert_metrics import (
    build_metric_sql,
    compare,
    list_metrics,
    sanitize_target,
)
from core.alert_scheduler import get_scheduler_status, start_scheduler, stop_scheduler
from core.alert_store import (
    create_rule,
    delete_rule,
    list_events,
    list_rules,
)
from core.config_loader import load_domain_config


@pytest.fixture(autouse=True)
def _isolate_alert_db(monkeypatch, tmp_path):
    db = tmp_path / "alerts.db"
    monkeypatch.setattr("core.alert_store._DB_PATH", db)
    yield


def test_sanitize_target() -> None:
    assert sanitize_target("FPT") == "FPT"
    assert sanitize_target("VNM Corp") == "VNM Corp"
    with pytest.raises(ValueError):
        sanitize_target("bad;drop")
    with pytest.raises(ValueError):
        sanitize_target("a' OR 1=1")


def test_list_metrics_finance() -> None:
    items = list_metrics("finance_vnfdata")
    assert len(items) >= 5
    keys = {m["key"] for m in items}
    assert "close_zscore" in keys
    assert "change_zscore" in keys
    z = next(m for m in items if m["key"] == "close_zscore")
    assert z["kind"] == "anomaly"
    assert z["default_threshold"] == 2.5


def test_compare_ops() -> None:
    assert compare(21, "gt", 20) is True
    assert compare(20, "gte", 20) is True
    assert compare(19, "lt", 20) is True
    assert compare(20, "eq", 20) is True
    assert compare(21, "lt", 20) is False


def test_build_finance_and_anomaly_sql() -> None:
    cfg = load_domain_config("finance_vnfdata")
    sql = build_metric_sql(
        "finance_vnfdata",
        "pe_ratio",
        target="FPT",
        db_url=cfg["db_url"],
    )
    assert "FPT" in sql.upper() or "fpt" in sql.lower()
    assert sql.strip().upper().startswith("SELECT")

    zsql = build_metric_sql(
        "finance_vnfdata",
        "close_zscore",
        target="FPT",
        db_url=cfg["db_url"],
    )
    assert "STDDEV" in zsql.upper() or "stddev" in zsql.lower() or "SQRT" in zsql.upper()
    assert "value" in zsql.lower()


def test_rising_edge_no_spam_events() -> None:
    rule = create_rule(
        domain_id="finance_vnfdata",
        name="P/E FPT cao",
        metric_key="pe_ratio",
        operator="gt",
        threshold=10.0,
        target="FPT",
    )
    with patch(
        "core.alert_engine.execute_query",
        return_value=[{"label": "FPT", "value": 21.5}],
    ):
        r1 = evaluate_rule(rule)
        assert r1["triggered"] is True
        assert r1["new_event"] is True
        assert len(list_events(domain_id="finance_vnfdata")) == 1

        r2 = evaluate_rule(rule)
        assert r2["triggered"] is True
        assert r2["new_event"] is False
        assert len(list_events(domain_id="finance_vnfdata")) == 1

    delete_rule(rule["id"])


def test_rule_lifecycle_and_run() -> None:
    rule = create_rule(
        domain_id="finance_vnfdata",
        name="P/E FPT cao",
        metric_key="pe_ratio",
        operator="gt",
        threshold=10.0,
        target="FPT",
    )
    assert rule["id"]
    assert len(list_rules("finance_vnfdata")) >= 1

    with patch(
        "core.alert_engine.execute_query",
        return_value=[{"label": "FPT", "value": 21.5}],
    ):
        result = evaluate_rule(rule)
        assert result["status"] == "triggered"
        assert result["triggered"] is True
        assert result["value"] == 21.5

        rule2 = create_rule(
            domain_id="finance_vnfdata",
            name="P/E FPT thấp bất thường",
            metric_key="pe_ratio",
            operator="gt",
            threshold=1000.0,
            target="FPT",
        )
        r2 = evaluate_rule(rule2)
        assert r2["status"] == "ok"
        assert r2["triggered"] is False

        batch = run_alerts("finance_vnfdata")
        assert batch["checked"] >= 2
        assert "new_event_count" in batch

    delete_rule(rule["id"])
    delete_rule(rule2["id"])


def test_scheduler_disabled_by_default(monkeypatch) -> None:
    stop_scheduler()
    monkeypatch.delenv("ALERT_SCHEDULE_ENABLED", raising=False)
    monkeypatch.setenv("ALERT_SCHEDULE_MINUTES", "15")
    status = start_scheduler()
    assert status["enabled"] is False
    assert status["running"] is False
    assert get_scheduler_status()["enabled"] is False
    stop_scheduler()


def test_api_router_import() -> None:
    from main import app

    paths = [
        getattr(r, "path", "")
        for r in app.routes
        if hasattr(r, "path")
    ]
    assert any("/api/v1/alerts/rules" in p for p in paths)
    assert any("/api/v1/alerts/run" in p for p in paths)
    assert any("/api/v1/alerts/scheduler" in p for p in paths)


if __name__ == "__main__":
    pytest.main([__file__, "-q"])
