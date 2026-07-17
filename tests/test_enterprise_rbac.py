"""Tests RBAC + tenancy + auth resolve."""

from __future__ import annotations

from pathlib import Path

import core.tenancy as tenancy
from core.auth import resolve_identity
from core.rbac import has_permission, normalize_role


def test_rbac_roles() -> None:
    assert has_permission("viewer", "chat")
    assert not has_permission("viewer", "article.write")
    assert has_permission("analyst", "article.write")
    assert has_permission("admin", "admin.users")
    assert normalize_role("ADMIN") == "admin"


def test_tenant_seed_and_api_key(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(tenancy, "_DB_PATH", tmp_path / "tenancy.db")
    monkeypatch.setenv("DEFAULT_ADMIN_EMAIL", "boss@acme.test")
    monkeypatch.setenv("DEFAULT_ADMIN_PASSWORD", "secret99")
    seeded = tenancy.ensure_default_tenant()
    assert seeded["api_key"].startswith("abi_")
    ident = tenancy.resolve_api_key(seeded["api_key"])
    assert ident is not None
    assert ident["role"] == "admin"
    assert ident["tenant_id"] == "tenant_default"

    user = tenancy.authenticate_user("boss@acme.test", "secret99")
    assert user is not None
    assert user["email"] == "boss@acme.test"


def test_resolve_identity_global_key(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(tenancy, "_DB_PATH", tmp_path / "tenancy2.db")
    monkeypatch.setenv("API_KEY", "global-secret-key")
    ident = resolve_identity("global-secret-key")
    assert ident is not None
    assert ident["auth_mode"] == "global_key"
    assert ident["role"] == "admin"


def test_dashboard_tenant_isolation(tmp_path: Path, monkeypatch) -> None:
    import core.dashboard_store as dash

    monkeypatch.setattr(dash, "_DB_PATH", tmp_path / "dash.db")
    a = dash.create_dashboard(
        title="A", domain_id="finance_vnfdata", reports=[{"q": 1}], tenant_id="t1"
    )
    assert dash.get_dashboard(a["id"], tenant_id="t1") is not None
    assert dash.get_dashboard(a["id"], tenant_id="t2") is None
