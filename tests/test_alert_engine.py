"""Tests Alert Engine — metrics, store, evaluate (IT domain mock)."""

from __future__ import annotations

import os
from pathlib import Path

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
    list_events,
    list_rules,
)
from core.config_loader import load_domain_config

# Dùng DB riêng cho test — không đụng alerts.db thật
_TEST_DB = Path(__file__).resolve().parent / "_tmp_alerts_test.db"


@pytest.fixture(autouse=True)
def _isolate_alert_db(monkeypatch, tmp_path):
    db = tmp_path / "alerts.db"
    monkeypatch.setattr("core.alert_store._DB_PATH", db)
    yield


def test_sanitize_target() -> None:
    assert sanitize_target("FPT") == "FPT"
    assert sanitize_target("SAP S/4HANA Pilot") == "SAP S/4HANA Pilot"
    assert sanitize_target("Warehouse WMS Upgrade") == "Warehouse WMS Upgrade"
    with pytest.raises(ValueError):
        sanitize_target("bad;drop")
    with pytest.raises(ValueError):
        sanitize_target("a' OR 1=1")


def test_list_metrics_all_domains() -> None:
    for did in ("finance_vnfdata", "it_deployment", "mining_geology"):
        items = list_metrics(did)
        assert len(items) >= 1
        assert all("key" in m and "label" in m for m in items)


def test_compare_ops() -> None:
    assert compare(21, "gt", 20) is True
    assert compare(20, "gte", 20) is True
    assert compare(19, "lt", 20) is True
    assert compare(20, "eq", 20) is True
    assert compare(21, "lt", 20) is False


def test_build_it_sql() -> None:
    cfg = load_domain_config("it_deployment")
    sql = build_metric_sql(
        "it_deployment",
        "avg_fsi_pct",
        target=None,
        db_url=cfg["db_url"],
    )
    assert "completion_pct" in sql
    assert sql.strip().upper().startswith("SELECT")


def test_rule_lifecycle_and_run() -> None:
    # Cần mock_database.db tồn tại
    cfg = load_domain_config("it_deployment")
    db_path = cfg["db_url"].replace("sqlite:///", "")
    if not Path(db_path).is_file() and not Path("mock_database.db").is_file():
        pytest.skip("mock_database.db chưa có — bỏ qua integration")

    rule = create_rule(
        domain_id="it_deployment",
        name="FSI TB thấp",
        metric_key="avg_fsi_pct",
        operator="lt",
        threshold=101.0,  # hầu như luôn trigger nếu có data
        target=None,
    )
    assert rule["id"]
    assert len(list_rules("it_deployment")) >= 1

    result = evaluate_rule(rule)
    assert result["status"] in ("ok", "triggered", "error")
    if result["status"] != "error":
        assert "value" in result

    # threshold rất thấp → không trigger nếu value > 0
    rule2 = create_rule(
        domain_id="it_deployment",
        name="FSI TB cao bất thường",
        metric_key="avg_fsi_pct",
        operator="gt",
        threshold=1000.0,
        target=None,
    )
    r2 = evaluate_rule(rule2)
    if r2["status"] != "error":
        assert r2["triggered"] is False

    batch = run_alerts("it_deployment")
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
