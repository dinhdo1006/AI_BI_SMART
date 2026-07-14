"""Tests cho insight_stats nâng cấp + router heuristic."""

from __future__ import annotations

from core.insight_stats import compute_insight_stats
from core.router import (
    INTENT_CHITCHAT,
    INTENT_FOLLOWUP,
    INTENT_OOS,
    INTENT_SQL,
    INTENT_VIZ,
    classify_intent,
)


def test_stats_basic_and_top_bottom() -> None:
    rows = [
        {"ma_cp": "VCB", "gia_dong_cua": 100.0},
        {"ma_cp": "SSI", "gia_dong_cua": 50.0},
        {"ma_cp": "TCB", "gia_dong_cua": 80.0},
        {"ma_cp": "MBB", "gia_dong_cua": 60.0},
    ]
    stats = compute_insight_stats(rows)
    assert stats["row_count"] == 4
    assert "numeric" in stats
    assert "top_bottom" in stats
    assert len(stats["top_bottom"]["top"]) >= 1
    assert stats["highlights"]["highest"]["label"] == "VCB"


def test_stats_trend_and_period() -> None:
    rows = [
        {"ngay_gd": "2024-01-01", "gia": 10.0},
        {"ngay_gd": "2024-02-01", "gia": 12.0},
        {"ngay_gd": "2024-03-01", "gia": 14.0},
        {"ngay_gd": "2024-04-01", "gia": 16.0},
        {"ngay_gd": "2024-05-01", "gia": 18.0},
        {"ngay_gd": "2024-06-01", "gia": 20.0},
    ]
    stats = compute_insight_stats(rows)
    assert stats.get("trend", {}).get("direction") == "up"
    assert "period_comparison" in stats


def test_stats_forecast_linear() -> None:
    rows = [
        {"ngay_gd": "2024-01-01", "gia": 10.0},
        {"ngay_gd": "2024-02-01", "gia": 12.0},
        {"ngay_gd": "2024-03-01", "gia": 14.0},
        {"ngay_gd": "2024-04-01", "gia": 16.0},
        {"ngay_gd": "2024-05-01", "gia": 18.0},
        {"ngay_gd": "2024-06-01", "gia": 20.0},
    ]
    stats = compute_insight_stats(rows)
    fc = stats.get("forecast")
    assert fc is not None
    assert fc["direction"] == "up"
    assert fc["horizon"] == 3
    assert len(fc["points"]) == 3
    assert fc["points"][0]["value"] < fc["points"][-1]["value"]
    assert fc["points"][0]["date"] > "2024-06-01"


def test_stats_forecast_missing_without_dates() -> None:
    rows = [
        {"ma_cp": "VCB", "gia": 100.0},
        {"ma_cp": "FPT", "gia": 90.0},
        {"ma_cp": "HPG", "gia": 80.0},
    ]
    stats = compute_insight_stats(rows)
    assert "forecast" not in stats


def test_stats_outlier_and_correlation() -> None:
    rows = [
        {"ten": "A", "x": 10.0, "y": 20.0},
        {"ten": "B", "x": 11.0, "y": 22.0},
        {"ten": "C", "x": 12.0, "y": 24.0},
        {"ten": "D", "x": 13.0, "y": 26.0},
        {"ten": "E", "x": 1000.0, "y": 2000.0},  # outlier rõ
    ]
    stats = compute_insight_stats(rows)
    assert "outliers" in stats
    assert stats["outliers"][0]["direction"] == "high"
    assert "correlation" in stats
    assert stats["correlation"]["move_together"] is True


def test_router_heuristics() -> None:
    assert (
        classify_intent("Xin chào", use_llm=False) == INTENT_CHITCHAT
    )
    assert (
        classify_intent("Viết giúp tôi hàm Python sort", use_llm=False)
        == INTENT_OOS
    )
    assert (
        classify_intent(
            "Vẽ biểu đồ đường",
            has_reuse_data=True,
            use_llm=False,
        )
        == INTENT_VIZ
    )
    assert (
        classify_intent(
            "Liệt kê top 5 dự án",
            use_llm=False,
        )
        == INTENT_SQL
    )
    assert (
        classify_intent(
            "Còn dự án đó thì sao?",
            has_history=True,
            use_llm=False,
        )
        == INTENT_FOLLOWUP
    )


if __name__ == "__main__":
    test_stats_basic_and_top_bottom()
    test_stats_trend_and_period()
    test_stats_outlier_and_correlation()
    test_router_heuristics()
    print("ALL PASSED")
