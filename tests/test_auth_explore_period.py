"""Tests auth, domain explorer, period MoM."""

from __future__ import annotations

from core.auth import auth_enabled, is_public_path
from core.config_loader import load_domain_config
from core.domain_explorer import build_domain_explore
from core.insight_stats import compute_insight_stats


def test_public_paths() -> None:
    assert is_public_path("/health")
    assert is_public_path("/api/v1/health/domains")
    assert is_public_path("/docs")
    assert not is_public_path("/api/v1/chat")
    assert not is_public_path("/api/v1/domains")


def test_auth_off_without_env(monkeypatch) -> None:
    monkeypatch.delenv("API_KEY", raising=False)
    assert auth_enabled() is False


def test_auth_on_with_env(monkeypatch) -> None:
    monkeypatch.setenv("API_KEY", "test-secret-key")
    assert auth_enabled() is True


def test_domain_explore_it() -> None:
    cfg = load_domain_config("it_deployment")
    explore = build_domain_explore(cfg)
    assert explore["domain_id"] == "it_deployment"
    assert explore["table_count"] >= 2
    names = {t["name"] for t in explore["tables"]}
    assert "projects" in names
    assert len(explore["sample_questions"]) >= 1


def test_period_mom_for_short_series() -> None:
    rows = [
        {"ngay_gd": "2024-01-05", "gia": 10.0},
        {"ngay_gd": "2024-01-20", "gia": 11.0},
        {"ngay_gd": "2024-02-05", "gia": 12.0},
        {"ngay_gd": "2024-02-20", "gia": 14.0},
        {"ngay_gd": "2024-03-05", "gia": 15.0},
        {"ngay_gd": "2024-03-20", "gia": 16.0},
    ]
    stats = compute_insight_stats(rows)
    pc = stats["period_comparison"]
    assert pc["mode"] == "MoM"
    assert pc["pct_change"] is not None
    assert pc["direction"] == "up"


if __name__ == "__main__":
    import os

    class _MP:
        def delenv(self, k, raising=False):
            os.environ.pop(k, None)

        def setenv(self, k, v):
            os.environ[k] = v

    mp = _MP()
    test_public_paths()
    test_auth_off_without_env(mp)
    test_auth_on_with_env(mp)
    test_domain_explore_it()
    test_period_mom_for_short_series()
    print("ALL PASSED")
