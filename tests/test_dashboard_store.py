"""Tests dashboard list / delete."""

from __future__ import annotations

from pathlib import Path

import core.dashboard_store as ds


def _patch(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(ds, "_DB_PATH", tmp_path / "dashboards.db")


def test_list_and_delete_dashboard(tmp_path: Path, monkeypatch) -> None:
    _patch(tmp_path, monkeypatch)
    created = ds.create_dashboard(
        title="Test dash",
        domain_id="finance_vnfdata",
        reports=[{"query": "P/E VNM", "data": []}],
        tenant_id="t1",
    )
    items = ds.list_dashboards(domain_id="finance_vnfdata", tenant_id="t1")
    assert len(items) == 1
    assert items[0]["id"] == created["id"]
    assert items[0]["report_count"] == 1

    # Tenant khác không xóa được
    assert ds.delete_dashboard(created["id"], tenant_id="other") is False
    assert ds.delete_dashboard(created["id"], tenant_id="t1") is True
    assert ds.list_dashboards(domain_id="finance_vnfdata") == []
