"""Tính thống kê trước khi gọi LLM insight — báo cáo sâu hơn, ít hallucination."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

_ID_COLS = frozenset({"id", "project_id", "mine_id"})
_DATE_KEYWORDS = ("ngay", "date", "time", "updated", "surveyed", "start")
_ZSCORE_THRESHOLD = 3.5  # modified z-score (MAD)
_TOP_N = 3


def _is_id_col(name: str) -> bool:
    lower = name.lower()
    return lower in _ID_COLS or lower.endswith("_id")


def _is_date_col(name: str) -> bool:
    lower = name.lower()
    return any(k in lower for k in _DATE_KEYWORDS)


def _numeric_columns(df: pd.DataFrame) -> list[str]:
    cols: list[str] = []
    for col in df.columns:
        if _is_id_col(col):
            continue
        series = pd.to_numeric(df[col], errors="coerce")
        if series.notna().sum() >= max(1, len(df) // 3):
            cols.append(col)
    return cols


def _text_columns(df: pd.DataFrame, numeric: list[str]) -> list[str]:
    return [c for c in df.columns if c not in numeric and not _is_id_col(c)]


def _find_date_col(df: pd.DataFrame) -> str | None:
    for col in df.columns:
        if _is_date_col(col):
            return col
    return None


def _parse_dates(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="coerce")


def _compute_outliers(
    df: pd.DataFrame,
    numeric: list[str],
    text_cols: list[str],
) -> list[dict[str, Any]]:
    """Modified Z-score (MAD) — phát hiện outlier ổn định hơn mean/std."""
    if not numeric or len(df) < 3:
        return []
    metric = numeric[0]
    series = pd.to_numeric(df[metric], errors="coerce")
    valid = series.dropna()
    if len(valid) < 3:
        return []
    median = float(valid.median())
    mad = float((valid - median).abs().median())
    if mad <= 0:
        # Fallback: IQR nếu MAD = 0
        q1 = float(valid.quantile(0.25))
        q3 = float(valid.quantile(0.75))
        iqr = q3 - q1
        if iqr <= 0:
            return []
        low, high = q1 - 1.5 * iqr, q3 + 1.5 * iqr
        label_col = next(
            (c for c in text_cols if not _is_date_col(c)),
            text_cols[0] if text_cols else None,
        )
        outliers: list[dict[str, Any]] = []
        for idx, val in series.items():
            if pd.isna(val):
                continue
            v = float(val)
            if low <= v <= high:
                continue
            item: dict[str, Any] = {
                "metric": metric,
                "value": round(v, 4),
                "z_score": None,
                "method": "iqr",
                "direction": "high" if v > high else "low",
            }
            if label_col is not None:
                item["label"] = str(df.loc[idx, label_col])
            outliers.append(item)
        return outliers[:5]

    label_col = next(
        (c for c in text_cols if not _is_date_col(c)),
        text_cols[0] if text_cols else None,
    )
    outliers = []
    for idx, val in series.items():
        if pd.isna(val):
            continue
        # 0.6745 ≈ Φ^{-1}(0.75) — chuẩn hóa MAD về cùng thang sigma
        z = 0.6745 * (float(val) - median) / mad
        if abs(z) < _ZSCORE_THRESHOLD:
            continue
        item = {
            "metric": metric,
            "value": round(float(val), 4),
            "z_score": round(float(z), 3),
            "method": "modified_z",
            "direction": "high" if z > 0 else "low",
        }
        if label_col is not None:
            item["label"] = str(df.loc[idx, label_col])
        outliers.append(item)
    outliers.sort(key=lambda x: abs(float(x["z_score"] or 0)), reverse=True)
    return outliers[:5]


def _compute_trend(
    df: pd.DataFrame,
    numeric: list[str],
    date_col: str | None,
) -> dict[str, Any] | None:
    """Slope tuyến tính theo thời gian → tăng / giảm / ngang."""
    if not numeric or date_col is None or len(df) < 3:
        return None
    metric = numeric[0]
    work = df[[date_col, metric]].copy()
    work["_dt"] = _parse_dates(work[date_col])
    work["_m"] = pd.to_numeric(work[metric], errors="coerce")
    work = work.dropna(subset=["_dt", "_m"]).sort_values("_dt")
    if len(work) < 3:
        return None
    x = np.arange(len(work), dtype=float)
    y = work["_m"].to_numpy(dtype=float)
    slope = float(np.polyfit(x, y, 1)[0])
    y_mean = float(np.mean(np.abs(y))) or 1.0
    rel_slope = slope / y_mean
    if rel_slope > 0.02:
        direction = "up"
    elif rel_slope < -0.02:
        direction = "down"
    else:
        direction = "flat"
    return {
        "metric": metric,
        "date_col": date_col,
        "slope": round(slope, 6),
        "relative_slope": round(rel_slope, 6),
        "direction": direction,
        "points": int(len(work)),
        "from": str(work["_dt"].iloc[0].date()),
        "to": str(work["_dt"].iloc[-1].date()),
        "start_value": round(float(y[0]), 4),
        "end_value": round(float(y[-1]), 4),
    }


def _compute_top_bottom(
    df: pd.DataFrame,
    numeric: list[str],
    text_cols: list[str],
) -> dict[str, Any] | None:
    """Top N / Bottom N theo metric chính."""
    if not numeric or not text_cols:
        return None
    metric = numeric[0]
    label_col = next(
        (c for c in text_cols if not _is_date_col(c)),
        None,
    )
    if label_col is None:
        return None
    work = df[[label_col, metric]].copy()
    work["_m"] = pd.to_numeric(work[metric], errors="coerce")
    work = work.dropna(subset=["_m"])
    if work.empty:
        return None
    # Gom theo label nếu trùng
    grouped = work.groupby(label_col, as_index=False)["_m"].mean()
    top = grouped.nlargest(min(_TOP_N, len(grouped)), "_m")
    bottom = grouped.nsmallest(min(_TOP_N, len(grouped)), "_m")
    return {
        "metric": metric,
        "label_col": label_col,
        "top": [
            {"label": str(r[label_col]), "value": round(float(r["_m"]), 4)}
            for _, r in top.iterrows()
        ],
        "bottom": [
            {"label": str(r[label_col]), "value": round(float(r["_m"]), 4)}
            for _, r in bottom.iterrows()
        ],
    }


def _compute_period_comparison(
    df: pd.DataFrame,
    numeric: list[str],
    date_col: str | None,
) -> dict[str, Any] | None:
    """
    So sánh kỳ gần nhất vs kỳ trước (QoQ nếu có quý, ngược lại half-split YoY-like).
    """
    if not numeric or date_col is None or len(df) < 4:
        return None
    metric = numeric[0]
    work = df[[date_col, metric]].copy()
    work["_dt"] = _parse_dates(work[date_col])
    work["_m"] = pd.to_numeric(work[metric], errors="coerce")
    work = work.dropna(subset=["_dt", "_m"]).sort_values("_dt")
    if len(work) < 4:
        return None

    # Ưu tiên so sánh theo quý nếu span >= 2 quý
    work["_period"] = work["_dt"].dt.to_period("Q")
    periods = work["_period"].unique()
    mode = "QoQ"
    if len(periods) < 2:
        work["_period"] = work["_dt"].dt.to_period("Y")
        periods = work["_period"].unique()
        mode = "YoY"
    if len(periods) < 2:
        # Fallback: chia đôi theo thời gian
        mid = len(work) // 2
        first = work.iloc[:mid]["_m"]
        second = work.iloc[mid:]["_m"]
        prev_mean = float(first.mean())
        curr_mean = float(second.mean())
        mode = "half_split"
        prev_label = "nửa đầu"
        curr_label = "nửa sau"
    else:
        sorted_periods = sorted(periods)
        prev_p, curr_p = sorted_periods[-2], sorted_periods[-1]
        prev_mean = float(work.loc[work["_period"] == prev_p, "_m"].mean())
        curr_mean = float(work.loc[work["_period"] == curr_p, "_m"].mean())
        prev_label = str(prev_p)
        curr_label = str(curr_p)

    if prev_mean == 0:
        pct_change = None
    else:
        pct_change = round((curr_mean - prev_mean) / abs(prev_mean) * 100, 2)

    return {
        "metric": metric,
        "date_col": date_col,
        "mode": mode,
        "previous_period": prev_label,
        "current_period": curr_label,
        "previous_mean": round(prev_mean, 4),
        "current_mean": round(curr_mean, 4),
        "pct_change": pct_change,
        "direction": (
            "up"
            if curr_mean > prev_mean
            else ("down" if curr_mean < prev_mean else "flat")
        ),
    }


def _compute_correlation(
    df: pd.DataFrame,
    numeric: list[str],
) -> dict[str, Any] | None:
    """Pearson correlation giữa 2 metric số đầu tiên."""
    if len(numeric) < 2 or len(df) < 3:
        return None
    a, b = numeric[0], numeric[1]
    s_a = pd.to_numeric(df[a], errors="coerce")
    s_b = pd.to_numeric(df[b], errors="coerce")
    mask = s_a.notna() & s_b.notna()
    if mask.sum() < 3:
        return None
    corr = float(s_a[mask].corr(s_b[mask]))
    if pd.isna(corr):
        return None
    abs_c = abs(corr)
    if abs_c >= 0.7:
        strength = "strong"
    elif abs_c >= 0.4:
        strength = "moderate"
    else:
        strength = "weak"
    return {
        "metric_a": a,
        "metric_b": b,
        "pearson_r": round(corr, 4),
        "strength": strength,
        "direction": "positive" if corr >= 0 else "negative",
        "move_together": abs_c >= 0.4,
    }


def compute_insight_stats(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Tổng hợp stats từ kết quả SQL — gửi kèm LLM để viết báo cáo.

    Returns:
        Dict JSON-friendly: row_count, numeric, top categories, date range,
        outliers (z-score), trend, top_bottom, period_comparison, correlation.
    """
    if not rows:
        return {"row_count": 0}

    df = pd.DataFrame(rows)
    numeric = _numeric_columns(df)
    text_cols = _text_columns(df, numeric)
    date_col = _find_date_col(df)

    stats: dict[str, Any] = {
        "row_count": len(df),
        "column_count": len(df.columns),
    }

    num_stats: dict[str, dict[str, float | int]] = {}
    for col in numeric:
        series = pd.to_numeric(df[col], errors="coerce").dropna()
        if series.empty:
            continue
        num_stats[col] = {
            "count": int(series.count()),
            "sum": round(float(series.sum()), 4),
            "mean": round(float(series.mean()), 4),
            "median": round(float(series.median()), 4),
            "min": round(float(series.min()), 4),
            "max": round(float(series.max()), 4),
        }
        if len(series) >= 2:
            num_stats[col]["range"] = round(
                float(series.max() - series.min()), 4
            )
            num_stats[col]["std"] = round(float(series.std(ddof=0)), 4)

    if num_stats:
        stats["numeric"] = num_stats

    # Top giá trị cột phân loại đầu tiên (vd: ma_cp, project_name)
    for col in text_cols[:2]:
        if _is_date_col(col):
            continue
        counts = df[col].astype(str).value_counts().head(5)
        if not counts.empty:
            stats.setdefault("top_categories", {})[col] = {
                str(k): int(v) for k, v in counts.items()
            }

    # Khoảng thời gian nếu có cột ngày
    if date_col is not None:
        vals = df[date_col].dropna().astype(str)
        if len(vals) >= 2:
            sorted_vals = sorted(vals)
            stats["date_range"] = {
                date_col: {
                    "from": sorted_vals[0],
                    "to": sorted_vals[-1],
                    "span_records": len(vals),
                }
            }

    # Dòng min/max cho cột số chính (thường là metric)
    if numeric and text_cols:
        primary_metric = numeric[0]
        label_col = next(
            (c for c in text_cols if not _is_date_col(c)), text_cols[0]
        )
        series = pd.to_numeric(df[primary_metric], errors="coerce")
        valid = df.copy()
        valid["_m"] = series
        valid = valid.dropna(subset=["_m"])
        if not valid.empty:
            idx_max = valid["_m"].idxmax()
            idx_min = valid["_m"].idxmin()
            stats["highlights"] = {
                "metric": primary_metric,
                "highest": {
                    "label": str(valid.loc[idx_max, label_col]),
                    "value": round(float(valid.loc[idx_max, "_m"]), 4),
                },
                "lowest": {
                    "label": str(valid.loc[idx_min, label_col]),
                    "value": round(float(valid.loc[idx_min, "_m"]), 4),
                },
            }

    outliers = _compute_outliers(df, numeric, text_cols)
    if outliers:
        stats["outliers"] = outliers

    trend = _compute_trend(df, numeric, date_col)
    if trend:
        stats["trend"] = trend

    top_bottom = _compute_top_bottom(df, numeric, text_cols)
    if top_bottom:
        stats["top_bottom"] = top_bottom

    period = _compute_period_comparison(df, numeric, date_col)
    if period:
        stats["period_comparison"] = period

    correlation = _compute_correlation(df, numeric)
    if correlation:
        stats["correlation"] = correlation

    return stats
