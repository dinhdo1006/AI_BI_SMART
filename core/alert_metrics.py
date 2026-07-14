"""Catalog metric an toàn cho Alert Engine — chỉ SQL template đã duyệt."""

from __future__ import annotations

import re
from typing import Any, Literal

from core.db_dialect import detect_dialect

Operator = Literal["gt", "gte", "lt", "lte", "eq"]

_OPS: dict[str, str] = {
    "gt": ">",
    "gte": "≥",
    "lt": "<",
    "lte": "≤",
    "eq": "=",
}

_TARGET_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 _.\-/]{0,63}$")


def sanitize_target(raw: str | None) -> str | None:
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    if not _TARGET_RE.match(text):
        raise ValueError(
            "Target không hợp lệ — chỉ chữ/số/dấu cách/._- (tối đa 64 ký tự)."
        )
    return text


def list_metrics(domain_id: str) -> list[dict[str, Any]]:
    """Danh sách metric có thể đặt alert theo domain."""
    catalog = _CATALOG.get(domain_id, [])
    return [
        {
            "key": m["key"],
            "label": m["label"],
            "unit": m.get("unit", ""),
            "needs_target": bool(m.get("needs_target")),
            "target_label": m.get("target_label", "Đối tượng"),
            "target_placeholder": m.get("target_placeholder", ""),
            "description": m.get("description", ""),
            "kind": m.get("kind", "threshold"),
            "default_threshold": m.get("default_threshold"),
            "default_operator": m.get("default_operator", "gt"),
        }
        for m in catalog
    ]


def get_metric(domain_id: str, metric_key: str) -> dict[str, Any] | None:
    for m in _CATALOG.get(domain_id, []):
        if m["key"] == metric_key:
            return m
    return None


def build_metric_sql(
    domain_id: str,
    metric_key: str,
    *,
    target: str | None,
    db_url: str,
) -> str:
    """
    Sinh SELECT … AS value (và label) từ template đã duyệt.
    Raises ValueError nếu metric/target không hợp lệ.
    """
    metric = get_metric(domain_id, metric_key)
    if not metric:
        raise ValueError(f"Metric '{metric_key}' không hỗ trợ cho domain '{domain_id}'.")

    clean_target = sanitize_target(target)
    if metric.get("needs_target") and not clean_target:
        raise ValueError(f"Metric '{metric_key}' cần target ({metric.get('target_label')}).")

    dialect = detect_dialect(db_url)
    builder = metric["sql"]
    return builder(clean_target or "", dialect)


def compare(value: float, operator: str, threshold: float) -> bool:
    if operator == "gt":
        return value > threshold
    if operator == "gte":
        return value >= threshold
    if operator == "lt":
        return value < threshold
    if operator == "lte":
        return value <= threshold
    if operator == "eq":
        return abs(value - threshold) < 1e-9
    raise ValueError(f"Operator không hỗ trợ: {operator}")


def op_symbol(operator: str) -> str:
    return _OPS.get(operator, operator)


def format_alert_message(
    *,
    rule_name: str,
    metric_label: str,
    operator: str,
    threshold: float,
    value: float,
    target: str | None,
    kind: str = "threshold",
) -> str:
    tgt = f" ({target})" if target else ""
    if kind == "anomaly":
        return (
            f"{rule_name}: {metric_label}{tgt} |z|={value:g} "
            f"(ngưỡng anomaly {op_symbol(operator)} {threshold:g}σ)"
        )
    return (
        f"{rule_name}: {metric_label}{tgt} = {value:g} "
        f"(ngưỡng {op_symbol(operator)} {threshold:g})"
    )


# --- SQL builders: luôn trả cột value + label ---


def _sql_finance_pe(target: str, dialect: str) -> str:
    t = target.upper().replace("'", "")
    if dialect == "postgresql":
        return (
            "SELECT fi.symbol AS label, fi.pe_ratio AS value "
            "FROM financial_indicators fi "
            f"WHERE fi.symbol = '{t}' "
            "ORDER BY fi.calc_date DESC LIMIT 1"
        )
    return (
        "SELECT c.ma_cp AS label, c.pe AS value "
        "FROM chi_so_tai_chinh c "
        f"WHERE c.ma_cp = '{t}' LIMIT 1"
    )


def _sql_finance_pb(target: str, dialect: str) -> str:
    t = target.upper().replace("'", "")
    if dialect == "postgresql":
        return (
            "SELECT fi.symbol AS label, fi.pb_ratio AS value "
            "FROM financial_indicators fi "
            f"WHERE fi.symbol = '{t}' "
            "ORDER BY fi.calc_date DESC LIMIT 1"
        )
    return (
        "SELECT c.ma_cp AS label, c.pb AS value "
        "FROM chi_so_tai_chinh c "
        f"WHERE c.ma_cp = '{t}' LIMIT 1"
    )


def _sql_finance_price_chg(target: str, dialect: str) -> str:
    """% đổi giá phiên mới nhất vs phiên trước."""
    t = target.upper().replace("'", "")
    if dialect == "postgresql":
        return (
            "SELECT c.ticker AS label, sp.change_percent AS value "
            "FROM stock_prices sp "
            "JOIN companies c ON c.id = sp.company_id "
            f"WHERE c.ticker = '{t}' "
            "ORDER BY sp.trade_date DESC LIMIT 1"
        )
    return (
        "WITH recent AS ("
        "  SELECT ma_cp, gia_dong_cua, ngay_gd "
        "  FROM gia_co_phieu_lich_su "
        f"  WHERE ma_cp = '{t}' "
        "  ORDER BY ngay_gd DESC LIMIT 2"
        ") "
        "SELECT ma_cp AS label, "
        "ROUND("
        "  (MAX(CASE WHEN rn = 1 THEN gia_dong_cua END) "
        "   - MAX(CASE WHEN rn = 2 THEN gia_dong_cua END)) "
        "  * 100.0 / NULLIF(MAX(CASE WHEN rn = 2 THEN gia_dong_cua END), 0)"
        ", 4) AS value "
        "FROM ("
        "  SELECT *, ROW_NUMBER() OVER (ORDER BY ngay_gd DESC) AS rn "
        "  FROM recent"
        ") x "
        "GROUP BY ma_cp"
    )


def _sql_finance_close_zscore(target: str, dialect: str) -> str:
    """
    |z-score| giá đóng cửa phiên mới nhất vs 20 phiên trước
    (baseline không gồm phiên mới nhất).
    """
    t = target.upper().replace("'", "")
    if dialect == "postgresql":
        return (
            "WITH hist AS ("
            "  SELECT sp.close_price AS v, sp.trade_date AS d, c.ticker AS ticker "
            "  FROM stock_prices sp "
            "  JOIN companies c ON c.id = sp.company_id "
            f"  WHERE c.ticker = '{t}' "
            "  ORDER BY sp.trade_date DESC LIMIT 21"
            "), "
            "latest AS ("
            "  SELECT v, ticker FROM hist ORDER BY d DESC LIMIT 1"
            "), "
            "base AS ("
            "  SELECT AVG(v) AS mu, STDDEV_POP(v) AS sigma "
            "  FROM ("
            "    SELECT v FROM hist ORDER BY d DESC OFFSET 1"
            "  ) x"
            ") "
            "SELECT latest.ticker AS label, "
            "ROUND(ABS((latest.v - base.mu) / NULLIF(base.sigma, 0))::numeric, 4) AS value "
            "FROM latest, base"
        )
    return (
        "WITH hist AS ("
        "  SELECT gia_dong_cua AS v, ngay_gd AS d, ma_cp AS ticker "
        "  FROM gia_co_phieu_lich_su "
        f"  WHERE ma_cp = '{t}' "
        "  ORDER BY ngay_gd DESC LIMIT 21"
        "), "
        "numbered AS ("
        "  SELECT v, d, ticker, ROW_NUMBER() OVER (ORDER BY d DESC) AS rn FROM hist"
        "), "
        "latest AS (SELECT v, ticker FROM numbered WHERE rn = 1), "
        "base AS ("
        "  SELECT AVG(v) AS mu, "
        "  CASE WHEN COUNT(*) > 1 THEN "
        "    SQRT(SUM((v - (SELECT AVG(v) FROM numbered WHERE rn > 1)) "
        "      * (v - (SELECT AVG(v) FROM numbered WHERE rn > 1))) / COUNT(*)) "
        "  ELSE NULL END AS sigma "
        "  FROM numbered WHERE rn > 1"
        ") "
        "SELECT latest.ticker AS label, "
        "ROUND(ABS((latest.v - base.mu) / NULLIF(base.sigma, 0)), 4) AS value "
        "FROM latest, base"
    )


def _sql_finance_change_zscore(target: str, dialect: str) -> str:
    """|z-score| của % đổi giá phiên mới nhất vs 20 phiên trước."""
    t = target.upper().replace("'", "")
    if dialect == "postgresql":
        return (
            "WITH hist AS ("
            "  SELECT sp.change_percent AS v, sp.trade_date AS d, c.ticker AS ticker "
            "  FROM stock_prices sp "
            "  JOIN companies c ON c.id = sp.company_id "
            f"  WHERE c.ticker = '{t}' AND sp.change_percent IS NOT NULL "
            "  ORDER BY sp.trade_date DESC LIMIT 21"
            "), "
            "latest AS ("
            "  SELECT v, ticker FROM hist ORDER BY d DESC LIMIT 1"
            "), "
            "base AS ("
            "  SELECT AVG(v) AS mu, STDDEV_POP(v) AS sigma "
            "  FROM ("
            "    SELECT v FROM hist ORDER BY d DESC OFFSET 1"
            "  ) x"
            ") "
            "SELECT latest.ticker AS label, "
            "ROUND(ABS((latest.v - base.mu) / NULLIF(base.sigma, 0))::numeric, 4) AS value "
            "FROM latest, base"
        )
    return (
        "WITH ordered AS ("
        "  SELECT ma_cp, gia_dong_cua, ngay_gd, "
        "  ROW_NUMBER() OVER (ORDER BY ngay_gd DESC) AS rn "
        "  FROM gia_co_phieu_lich_su "
        f"  WHERE ma_cp = '{t}' "
        "), "
        "chgs AS ("
        "  SELECT a.ma_cp AS ticker, a.ngay_gd AS d, "
        "  (a.gia_dong_cua - b.gia_dong_cua) * 100.0 "
        "    / NULLIF(b.gia_dong_cua, 0) AS v, a.rn "
        "  FROM ordered a "
        "  JOIN ordered b ON b.rn = a.rn + 1 "
        "  WHERE a.rn <= 21"
        "), "
        "latest AS (SELECT v, ticker FROM chgs WHERE rn = 1), "
        "base AS ("
        "  SELECT AVG(v) AS mu, "
        "  CASE WHEN COUNT(*) > 1 THEN "
        "    SQRT(AVG((v - (SELECT AVG(v) FROM chgs WHERE rn > 1)) "
        "      * (v - (SELECT AVG(v) FROM chgs WHERE rn > 1)))) "
        "  ELSE NULL END AS sigma "
        "  FROM chgs WHERE rn > 1"
        ") "
        "SELECT latest.ticker AS label, "
        "ROUND(ABS((latest.v - base.mu) / NULLIF(base.sigma, 0)), 4) AS value "
        "FROM latest, base"
    )


_CATALOG: dict[str, list[dict[str, Any]]] = {
    "finance_vnfdata": [
        {
            "key": "pe_ratio",
            "label": "P/E",
            "unit": "x",
            "needs_target": True,
            "target_label": "Mã CK",
            "target_placeholder": "FPT",
            "description": "Hệ số P/E mới nhất của mã",
            "kind": "threshold",
            "sql": _sql_finance_pe,
        },
        {
            "key": "pb_ratio",
            "label": "P/B",
            "unit": "x",
            "needs_target": True,
            "target_label": "Mã CK",
            "target_placeholder": "VCB",
            "description": "Hệ số P/B mới nhất của mã",
            "kind": "threshold",
            "sql": _sql_finance_pb,
        },
        {
            "key": "price_change_pct",
            "label": "% đổi giá phiên",
            "unit": "%",
            "needs_target": True,
            "target_label": "Mã CK",
            "target_placeholder": "HPG",
            "description": "% thay đổi đóng cửa phiên mới nhất vs phiên trước",
            "kind": "threshold",
            "sql": _sql_finance_price_chg,
        },
        {
            "key": "close_zscore",
            "label": "Z-score giá đóng",
            "unit": "σ",
            "needs_target": True,
            "target_label": "Mã CK",
            "target_placeholder": "FPT",
            "description": (
                "Độ lệch |z| của giá đóng phiên mới so với 20 phiên trước "
                "(anomaly khi > 2–3σ)"
            ),
            "kind": "anomaly",
            "default_threshold": 2.5,
            "default_operator": "gt",
            "sql": _sql_finance_close_zscore,
        },
        {
            "key": "change_zscore",
            "label": "Z-score % đổi giá",
            "unit": "σ",
            "needs_target": True,
            "target_label": "Mã CK",
            "target_placeholder": "HPG",
            "description": (
                "Độ lệch |z| của % đổi giá phiên mới so với 20 phiên trước"
            ),
            "kind": "anomaly",
            "default_threshold": 2.5,
            "default_operator": "gt",
            "sql": _sql_finance_change_zscore,
        },
    ]
}
