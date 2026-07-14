"""Tests Alert Engine — metrics, store, evaluate (finance domain)."""

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
from core.alert_store import (
    create_rule,
    delete_rule,
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
    assert len(items) >= 1
    assert all("key" in m and "label" in m for m in items)
    assert list_metrics("it_deployment") == []
    assert list_metrics("mining_geology") == []


def test_compare_ops() -> None:
    assert compare(21, "gt", 20) is True
    assert compare(20, "gte", 20) is True
    assert compare(19, "lt", 20) is True
    assert compare(20, "eq", 20) is True
    assert compare(21, "lt", 20) is False


def test_build_finance_sql() -> None:
    cfg = load_domain_config("finance_vnfdata")
    sql = build_metric_sql(
        "finance_vnfdata",
        "pe_ratio",
        target="FPT",
        db_url=cfg["db_url"],
    )
    assert "FPT" in sql.upper() or "fpt" in sql.lower()
    assert sql.strip().upper().startswith("SELECT")
    assert "value" in sql.lower()


def test_rule_lifecycle_and_run() -> None:
    """Evaluate dùng mock execute_query — không phụ thuộc DB live."""
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

    delete_rule(rule["id"])
    delete_rule(rule2["id"])


def test_api_router_import() -> None:
    from main import app

    paths = [
        getattr(r, "path", "")
        for r in app.routes
        if hasattr(r, "path")
    ]
    assert any("/api/v1/alerts/rules" in p for p in paths)
    assert any("/api/v1/alerts/run" in p for p in paths)


if __name__ == "__main__":
    pytest.main([__file__, "-q"])
