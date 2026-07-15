"""SQL đã duyệt theo từng template VNFDATA (PostgreSQL)."""

from __future__ import annotations

_SQL_BY_TEMPLATE: dict[str, str] = {
    # ===== MARKET =====
    "market_01": """
WITH idx AS (
  SELECT mi.code AS index_code,
         mi.name AS index_name,
         s.value AS index_value,
         s.change_percent AS index_change_pct,
         s.change_points AS index_change_points,
         s.total_value AS market_total_value,
         s.total_volume AS market_total_volume,
         s.advance_count,
         s.decline_count,
         s.no_change_count,
         (s.snapshot_time AT TIME ZONE 'Asia/Ho_Chi_Minh')::date AS trade_date
  FROM index_snapshots s
  JOIN market_indices mi ON mi.id = s.index_id
  WHERE mi.code = 'VNINDEX'
  ORDER BY s.snapshot_time DESC
  LIMIT 1
),
top_stocks AS (
  SELECT c.ticker,
         sp.trade_date,
         sp.close_price,
         sp.change_percent,
         sp.volume,
         sp.value
  FROM stock_prices sp
  JOIN companies c ON c.id = sp.company_id
  WHERE sp.trade_date = (SELECT MAX(trade_date) FROM stock_prices)
  ORDER BY sp.value DESC NULLS LAST
  LIMIT 40
)
SELECT t.ticker,
       t.trade_date,
       t.close_price,
       t.change_percent,
       t.volume,
       t.value,
       i.index_code,
       i.index_value,
       i.index_change_pct,
       i.index_change_points,
       i.market_total_value,
       i.advance_count,
       i.decline_count
FROM top_stocks t
CROSS JOIN idx i
ORDER BY t.value DESC NULLS LAST
""".strip(),
    "market_02": """
SELECT c.ticker,
       sp.trade_date,
       sp.close_price,
       sp.change_percent,
       sp.volume,
       sp.value
FROM stock_prices sp
JOIN companies c ON c.id = sp.company_id
WHERE sp.trade_date = (SELECT MAX(trade_date) FROM stock_prices)
  AND sp.change_percent IS NOT NULL
ORDER BY sp.change_percent DESC
LIMIT 15
""".strip(),
    "market_03": """
SELECT c.ticker,
       sp.trade_date,
       sp.close_price,
       sp.change_percent,
       sp.volume,
       sp.value
FROM stock_prices sp
JOIN companies c ON c.id = sp.company_id
WHERE sp.trade_date = (SELECT MAX(trade_date) FROM stock_prices)
  AND sp.change_percent IS NOT NULL
ORDER BY sp.change_percent ASC
LIMIT 15
""".strip(),
    "market_04": """
SELECT c.ticker,
       sp.trade_date,
       sp.close_price,
       sp.change_percent,
       sp.volume,
       sp.value
FROM stock_prices sp
JOIN companies c ON c.id = sp.company_id
WHERE sp.trade_date = (SELECT MAX(trade_date) FROM stock_prices)
ORDER BY sp.value DESC NULLS LAST
LIMIT 15
""".strip(),
    "market_05": """
SELECT fi.symbol AS ticker,
       fi.calc_date,
       fi.market_cap,
       fi.pe_ratio,
       fi.pb_ratio,
       fi.roe
FROM financial_indicators fi
WHERE fi.calc_date = (SELECT MAX(calc_date) FROM financial_indicators)
  AND fi.market_cap IS NOT NULL
ORDER BY fi.market_cap DESC
LIMIT 15
""".strip(),
    "market_06": """
SELECT mi.code AS index_code,
       mi.name AS index_name,
       s.snapshot_time,
       s.value AS index_value,
       s.change_percent,
       s.change_points,
       s.total_value,
       s.total_volume,
       s.advance_count,
       s.decline_count,
       s.no_change_count
FROM index_snapshots s
JOIN market_indices mi ON mi.id = s.index_id
WHERE mi.code IN ('VNINDEX', 'VN30', 'HNXINDEX', 'UPCOMINDEX')
  AND s.snapshot_time = (
    SELECT MAX(s2.snapshot_time)
    FROM index_snapshots s2
    JOIN market_indices mi2 ON mi2.id = s2.index_id
    WHERE mi2.code = mi.code
  )
ORDER BY CASE mi.code
  WHEN 'VNINDEX' THEN 1
  WHEN 'VN30' THEN 2
  WHEN 'HNXINDEX' THEN 3
  ELSE 4
END
""".strip(),
    "market_07": """
WITH daily AS (
  SELECT sp.trade_date,
         SUM(sp.value) AS total_value,
         SUM(sp.volume) AS total_volume,
         COUNT(*) AS stock_count
  FROM stock_prices sp
  WHERE sp.trade_date >= (
    SELECT MAX(trade_date) - INTERVAL '10 days' FROM stock_prices
  )
  GROUP BY sp.trade_date
)
SELECT d.trade_date,
       d.total_value,
       d.total_volume,
       d.stock_count,
       LAG(d.total_value) OVER (ORDER BY d.trade_date) AS prev_total_value,
       CASE
         WHEN LAG(d.total_value) OVER (ORDER BY d.trade_date) > 0
         THEN ROUND(
           ((d.total_value - LAG(d.total_value) OVER (ORDER BY d.trade_date))
            / LAG(d.total_value) OVER (ORDER BY d.trade_date)) * 100, 2
         )
       END AS value_change_pct
FROM daily d
ORDER BY d.trade_date DESC
LIMIT 12
""".strip(),
    "market_08": """
SELECT sp.trade_date,
       COUNT(*) AS total_codes,
       COUNT(*) FILTER (WHERE sp.change_percent > 0) AS advance_count,
       COUNT(*) FILTER (WHERE sp.change_percent < 0) AS decline_count,
       COUNT(*) FILTER (WHERE sp.change_percent = 0) AS unchanged_count,
       COUNT(*) FILTER (WHERE sp.change_percent >= 6.5) AS approx_ceiling,
       COUNT(*) FILTER (WHERE sp.change_percent <= -6.5) AS approx_floor,
       ROUND(AVG(sp.change_percent)::numeric, 3) AS avg_change_pct,
       SUM(sp.value) AS total_value
FROM stock_prices sp
WHERE sp.trade_date = (SELECT MAX(trade_date) FROM stock_prices)
GROUP BY sp.trade_date
""".strip(),
    "market_09": """
SELECT c.ticker,
       ft.trade_date,
       ft.buy_volume,
       ft.sell_volume,
       (COALESCE(ft.buy_volume, 0) - COALESCE(ft.sell_volume, 0)) AS net_volume,
       ft.buy_value,
       ft.sell_value,
       ft.net_value
FROM foreign_trades ft
JOIN companies c ON c.id = ft.company_id
WHERE ft.trade_date = (SELECT MAX(trade_date) FROM foreign_trades)
ORDER BY ABS(COALESCE(ft.net_value, 0)) DESC
LIMIT 30
""".strip(),
    "market_10": """
SELECT pt.ticker,
       pt.trade_date,
       pt.buy_volume,
       pt.sell_volume,
       pt.net_volume,
       pt.buy_value,
       pt.sell_value,
       pt.net_value
FROM proprietary_trades pt
WHERE pt.trade_date = (SELECT MAX(trade_date) FROM proprietary_trades)
  AND (
    COALESCE(ABS(pt.net_value), 0) > 0
    OR COALESCE(ABS(pt.net_volume), 0) > 0
  )
ORDER BY ABS(COALESCE(pt.net_value, 0)) DESC
LIMIT 30
""".strip(),
    "market_11": """
SELECT f.fund_code,
       f.short_name,
       f.name AS fund_name,
       f.fund_type,
       f.nav,
       f.nav_change_previous,
       f.nav_change_1m,
       f.nav_change_3m,
       f.nav_update_at,
       m.metric_date,
       m.etf_net_flow,
       m.foreign_net_flow,
       m.vnindex_value
FROM funds f
CROSS JOIN LATERAL (
  SELECT metric_date, etf_net_flow, foreign_net_flow, vnindex_value
  FROM market_valuation_metrics
  ORDER BY metric_date DESC
  LIMIT 1
) m
WHERE f.nav IS NOT NULL
  AND (
    f.fund_code ILIKE 'FUE%'
    OR f.short_name ILIKE '%ETF%'
    OR f.name ILIKE '%ETF%'
    OR f.fund_type ILIKE '%cổ phiếu%'
  )
ORDER BY f.nav DESC NULLS LAST
LIMIT 25
""".strip(),
    "market_12": """
WITH latest_sp AS (
  SELECT company_id, trade_date, close_price, change_percent, value
  FROM stock_prices
  WHERE trade_date = (SELECT MAX(trade_date) FROM stock_prices)
),
caps AS (
  SELECT symbol, market_cap
  FROM financial_indicators
  WHERE calc_date = (SELECT MAX(calc_date) FROM financial_indicators)
)
SELECT c.ticker,
       ls.trade_date,
       ls.close_price,
       ls.change_percent,
       ls.value,
       cap.market_cap,
       ROUND(
         (COALESCE(ls.change_percent, 0) * COALESCE(cap.market_cap, 0) / 100.0)::numeric,
         2
       ) AS approx_point_contribution
FROM latest_sp ls
JOIN companies c ON c.id = ls.company_id
LEFT JOIN caps cap ON cap.symbol = c.ticker
WHERE ls.change_percent IS NOT NULL
ORDER BY ABS(
  COALESCE(ls.change_percent, 0) * COALESCE(cap.market_cap, 0)
) DESC NULLS LAST
LIMIT 20
""".strip(),
    "market_13": """
SELECT sp.sector_code,
       sp.sector_name,
       sp.trade_date,
       sp.change_percent,
       sp.advance_count,
       sp.decline_count,
       sp.total_value
FROM sector_performance sp
WHERE sp.trade_date = (SELECT MAX(trade_date) FROM sector_performance)
ORDER BY sp.change_percent DESC NULLS LAST
LIMIT 25
""".strip(),
    "market_14": """
SELECT mi.code AS index_code,
       mi.name AS index_name,
       (s.snapshot_time AT TIME ZONE 'Asia/Ho_Chi_Minh')::date AS trade_date,
       s.value AS index_value,
       s.change_percent,
       s.total_value,
       s.advance_count,
       s.decline_count
FROM index_snapshots s
JOIN market_indices mi ON mi.id = s.index_id
WHERE mi.code = 'VNINDEX'
  AND s.snapshot_time >= (
    SELECT MAX(snapshot_time) - INTERVAL '35 days' FROM index_snapshots
  )
ORDER BY s.snapshot_time DESC
LIMIT 40
""".strip(),
    "market_15": """
SELECT fi.symbol AS ticker,
       fi.calc_date,
       fi.market_cap,
       fi.high_52w,
       fi.low_52w,
       sp.close_price,
       sp.change_percent,
       sp.volume,
       sp.value,
       CASE
         WHEN fi.high_52w > 0
         THEN ROUND((sp.close_price / fi.high_52w * 100)::numeric, 2)
       END AS pct_of_52w_high,
       fi.avg_volume_20d
FROM financial_indicators fi
JOIN companies c ON c.ticker = fi.symbol
JOIN stock_prices sp ON sp.company_id = c.id
  AND sp.trade_date = (SELECT MAX(trade_date) FROM stock_prices)
WHERE fi.calc_date = (SELECT MAX(calc_date) FROM financial_indicators)
  AND fi.high_52w IS NOT NULL
  AND sp.close_price IS NOT NULL
ORDER BY (sp.close_price / NULLIF(fi.high_52w, 0)) DESC NULLS LAST,
         sp.value DESC NULLS LAST
LIMIT 20
""".strip(),
    # ===== COMPANY =====
    "company_01": """
SELECT c.ticker,
       c.company_name,
       fs.fiscal_year,
       fs.fiscal_quarter,
       fs.report_type,
       fs.net_revenue,
       fs.net_income,
       fs.gross_profit,
       fs.operating_profit,
       CASE
         WHEN fs.net_revenue > 0
         THEN ROUND((fs.net_income / fs.net_revenue * 100)::numeric, 2)
       END AS net_margin_pct,
       fs.roe,
       fs.operating_cash_flow
FROM financial_statements fs
JOIN companies c ON c.id = fs.company_id
WHERE fs.fiscal_year = (SELECT MAX(fiscal_year) FROM financial_statements)
ORDER BY fs.net_income DESC NULLS LAST
LIMIT 40
""".strip(),
    "company_02": """
SELECT c.ticker,
       c.company_name,
       fs.fiscal_year,
       fs.fiscal_quarter,
       fs.net_revenue,
       fs.gross_profit,
       fs.operating_profit,
       fs.net_income,
       CASE
         WHEN fs.net_revenue > 0
         THEN ROUND((fs.gross_profit / fs.net_revenue * 100)::numeric, 2)
       END AS gross_margin_pct
FROM financial_statements fs
JOIN companies c ON c.id = fs.company_id
WHERE fs.fiscal_year = (SELECT MAX(fiscal_year) FROM financial_statements)
  AND fs.net_revenue IS NOT NULL
ORDER BY ABS(fs.net_revenue) DESC NULLS LAST
LIMIT 40
""".strip(),
    "company_03": """
SELECT c.ticker,
       c.company_name,
       fs.fiscal_year,
       fs.fiscal_quarter,
       fs.net_income,
       fs.net_revenue,
       fs.profit_before_tax,
       fs.operating_profit,
       fs.roe,
       fs.roa
FROM financial_statements fs
JOIN companies c ON c.id = fs.company_id
WHERE fs.fiscal_year = (SELECT MAX(fiscal_year) FROM financial_statements)
  AND fs.net_income IS NOT NULL
ORDER BY fs.net_income DESC NULLS LAST
LIMIT 40
""".strip(),
    "company_04": """
SELECT c.ticker,
       c.company_name,
       fs.fiscal_year,
       fs.fiscal_quarter,
       fs.net_income,
       fs.net_revenue,
       fs.roe
FROM financial_statements fs
JOIN companies c ON c.id = fs.company_id
WHERE fs.fiscal_year >= (SELECT MAX(fiscal_year) - 4 FROM financial_statements)
  AND fs.net_income IS NOT NULL
ORDER BY c.ticker, fs.fiscal_year DESC,
  CASE WHEN fs.fiscal_quarter IS NULL THEN 5 ELSE fs.fiscal_quarter END DESC
LIMIT 120
""".strip(),
    "company_05": """
WITH latest AS (
  SELECT company_id, fiscal_year, fiscal_quarter, net_revenue, net_income
  FROM financial_statements
  WHERE fiscal_year = (SELECT MAX(fiscal_year) FROM financial_statements)
),
prior AS (
  SELECT company_id, fiscal_year, fiscal_quarter, net_revenue, net_income
  FROM financial_statements
  WHERE fiscal_year = (SELECT MAX(fiscal_year) - 1 FROM financial_statements)
)
SELECT c.ticker,
       c.company_name,
       l.fiscal_year AS current_year,
       l.net_revenue AS current_revenue,
       l.net_income AS current_net_income,
       p.fiscal_year AS prior_year,
       p.net_revenue AS prior_revenue,
       p.net_income AS prior_net_income,
       CASE
         WHEN p.net_revenue > 0
         THEN ROUND((l.net_revenue / p.net_revenue * 100)::numeric, 2)
       END AS revenue_vs_prior_pct,
       CASE
         WHEN p.net_income > 0
         THEN ROUND((l.net_income / p.net_income * 100)::numeric, 2)
       END AS income_vs_prior_pct
FROM latest l
JOIN companies c ON c.id = l.company_id
LEFT JOIN prior p
  ON p.company_id = l.company_id
 AND (
   (p.fiscal_quarter IS NULL AND l.fiscal_quarter IS NULL)
   OR p.fiscal_quarter = l.fiscal_quarter
 )
WHERE l.net_income IS NOT NULL
ORDER BY ABS(COALESCE(l.net_income, 0)) DESC
LIMIT 40
""".strip(),
    "company_06": """
SELECT c.ticker,
       c.company_name,
       fs.fiscal_year,
       fs.fiscal_quarter,
       fs.net_income,
       fs.net_revenue,
       fs.roe,
       fs.operating_cash_flow
FROM financial_statements fs
JOIN companies c ON c.id = fs.company_id
WHERE fs.fiscal_year >= (SELECT MAX(fiscal_year) - 5 FROM financial_statements)
  AND fs.fiscal_quarter IS NULL
  AND fs.net_income IS NOT NULL
ORDER BY c.ticker, fs.fiscal_year DESC
LIMIT 150
""".strip(),
    "company_07": """
SELECT c.ticker,
       c.company_name,
       fs.fiscal_year,
       fs.fiscal_quarter,
       fs.net_revenue,
       fs.net_income,
       fs.gross_profit
FROM financial_statements fs
JOIN companies c ON c.id = fs.company_id
WHERE fs.fiscal_year = (SELECT MAX(fiscal_year) FROM financial_statements)
  AND fs.net_revenue IS NOT NULL
ORDER BY fs.net_revenue DESC NULLS LAST
LIMIT 15
""".strip(),
    "company_08": """
SELECT c.ticker,
       c.company_name,
       fs.fiscal_year,
       fs.fiscal_quarter,
       fs.net_income,
       fs.net_revenue,
       fs.roe
FROM financial_statements fs
JOIN companies c ON c.id = fs.company_id
WHERE fs.fiscal_year = (SELECT MAX(fiscal_year) FROM financial_statements)
  AND fs.net_income IS NOT NULL
ORDER BY fs.net_income DESC NULLS LAST
LIMIT 15
""".strip(),
    "company_09": """
SELECT fi.symbol AS ticker,
       c.company_name,
       fi.calc_date,
       fi.eps_ttm,
       fi.pe_ratio,
       fi.pb_ratio,
       fi.roe,
       fi.market_cap
FROM financial_indicators fi
LEFT JOIN companies c ON c.ticker = fi.symbol
WHERE fi.calc_date = (SELECT MAX(calc_date) FROM financial_indicators)
  AND fi.eps_ttm IS NOT NULL
ORDER BY fi.eps_ttm DESC NULLS LAST
LIMIT 20
""".strip(),
    "company_10": """
SELECT c.ticker,
       c.company_name,
       fs.fiscal_year,
       fs.fiscal_quarter,
       fs.net_revenue,
       fs.net_income,
       fs.operating_cash_flow,
       fs.gross_profit,
       CASE
         WHEN fs.net_revenue > 0
         THEN ROUND((fs.net_income / fs.net_revenue * 100)::numeric, 2)
       END AS net_margin_pct,
       CASE
         WHEN fs.net_income IS NOT NULL AND fs.operating_cash_flow IS NOT NULL
         THEN ROUND((fs.operating_cash_flow - fs.net_income)::numeric, 2)
       END AS cfo_minus_net_income
FROM financial_statements fs
JOIN companies c ON c.id = fs.company_id
WHERE fs.fiscal_year = (SELECT MAX(fiscal_year) FROM financial_statements)
  AND fs.net_income IS NOT NULL
ORDER BY ABS(COALESCE(fs.operating_cash_flow, 0) - COALESCE(fs.net_income, 0)) DESC
LIMIT 40
""".strip(),
    "company_11": """
SELECT c.ticker,
       c.company_name,
       fs.fiscal_year,
       fs.fiscal_quarter,
       fs.total_assets,
       fs.total_current_assets,
       fs.total_non_current_assets,
       fs.equity,
       fs.total_debt
FROM financial_statements fs
JOIN companies c ON c.id = fs.company_id
WHERE fs.fiscal_year = (SELECT MAX(fiscal_year) FROM financial_statements)
  AND fs.total_assets IS NOT NULL
ORDER BY fs.total_assets DESC NULLS LAST
LIMIT 40
""".strip(),
    "company_12": """
SELECT c.ticker,
       c.company_name,
       fs.fiscal_year,
       fs.fiscal_quarter,
       fs.total_debt,
       fs.equity,
       fs.de_ratio,
       fs.total_assets,
       CASE
         WHEN fs.equity > 0
         THEN ROUND((fs.total_debt / fs.equity)::numeric, 3)
       END AS debt_to_equity
FROM financial_statements fs
JOIN companies c ON c.id = fs.company_id
WHERE fs.fiscal_year = (SELECT MAX(fiscal_year) FROM financial_statements)
  AND fs.total_debt IS NOT NULL
ORDER BY fs.total_debt DESC NULLS LAST
LIMIT 40
""".strip(),
    "company_13": """
SELECT c.ticker,
       c.company_name,
       fs.fiscal_year,
       fs.fiscal_quarter,
       fs.total_debt,
       fs.short_term_borrowings,
       fs.finance_cost,
       fs.equity,
       fs.de_ratio,
       fs.cash_and_cash_equivalents,
       fs.net_income
FROM financial_statements fs
JOIN companies c ON c.id = fs.company_id
WHERE fs.fiscal_year = (SELECT MAX(fiscal_year) FROM financial_statements)
  AND fs.total_debt IS NOT NULL
ORDER BY fs.total_debt DESC NULLS LAST
LIMIT 40
""".strip(),
    "company_14": """
SELECT c.ticker,
       c.company_name,
       fs.fiscal_year,
       fs.fiscal_quarter,
       fs.cash_and_cash_equivalents,
       fs.short_term_investments,
       fs.ending_cash,
       fs.financial_revenue,
       fs.total_debt,
       fs.short_term_borrowings,
       fs.total_assets,
       CASE
         WHEN fs.total_assets > 0
         THEN ROUND(
           (fs.cash_and_cash_equivalents / fs.total_assets * 100)::numeric, 2
         )
       END AS cash_to_assets_pct
FROM financial_statements fs
JOIN companies c ON c.id = fs.company_id
WHERE fs.fiscal_year = (SELECT MAX(fiscal_year) FROM financial_statements)
  AND fs.cash_and_cash_equivalents IS NOT NULL
ORDER BY fs.cash_and_cash_equivalents DESC NULLS LAST
LIMIT 40
""".strip(),
    "company_15": """
SELECT c.ticker,
       c.company_name,
       fs.fiscal_year,
       fs.fiscal_quarter,
       fs.inventory,
       fs.net_revenue,
       fs.cost_of_goods_sold,
       fs.total_current_assets,
       CASE
         WHEN fs.inventory > 0 AND fs.cost_of_goods_sold > 0
         THEN ROUND((fs.cost_of_goods_sold / fs.inventory)::numeric, 2)
       END AS inventory_turnover_approx
FROM financial_statements fs
JOIN companies c ON c.id = fs.company_id
WHERE fs.fiscal_year = (SELECT MAX(fiscal_year) FROM financial_statements)
  AND fs.inventory IS NOT NULL
ORDER BY ABS(fs.inventory) DESC NULLS LAST
LIMIT 40
""".strip(),
    "company_16": """
SELECT c.ticker,
       c.company_name,
       fs.fiscal_year,
       fs.fiscal_quarter,
       fs.short_term_receivables,
       fs.loans_and_receivables,
       fs.net_revenue,
       fs.total_current_assets,
       fs.operating_cash_flow,
       CASE
         WHEN fs.net_revenue > 0
         THEN ROUND(
           (fs.short_term_receivables / fs.net_revenue * 100)::numeric, 2
         )
       END AS receivables_to_revenue_pct
FROM financial_statements fs
JOIN companies c ON c.id = fs.company_id
WHERE fs.fiscal_year = (SELECT MAX(fiscal_year) FROM financial_statements)
  AND fs.short_term_receivables IS NOT NULL
ORDER BY ABS(fs.short_term_receivables) DESC NULLS LAST
LIMIT 40
""".strip(),
    "company_17": """
SELECT c.ticker,
       c.company_name,
       fs.fiscal_year,
       fs.fiscal_quarter,
       fs.cash_and_cash_equivalents,
       fs.short_term_investments,
       fs.total_assets,
       CASE
         WHEN fs.total_assets > 0
         THEN ROUND(
           (fs.cash_and_cash_equivalents / fs.total_assets * 100)::numeric, 2
         )
       END AS cash_to_assets_pct
FROM financial_statements fs
JOIN companies c ON c.id = fs.company_id
WHERE fs.fiscal_year = (SELECT MAX(fiscal_year) FROM financial_statements)
  AND fs.cash_and_cash_equivalents IS NOT NULL
ORDER BY fs.cash_and_cash_equivalents DESC NULLS LAST
LIMIT 15
""".strip(),
    "company_18": """
SELECT c.ticker,
       c.company_name,
       fs.fiscal_year,
       fs.fiscal_quarter,
       fs.total_debt,
       fs.short_term_borrowings,
       fs.equity,
       fs.de_ratio,
       CASE
         WHEN fs.equity > 0
         THEN ROUND((fs.total_debt / fs.equity)::numeric, 3)
       END AS debt_to_equity
FROM financial_statements fs
JOIN companies c ON c.id = fs.company_id
WHERE fs.fiscal_year = (SELECT MAX(fiscal_year) FROM financial_statements)
  AND fs.total_debt IS NOT NULL
ORDER BY fs.total_debt DESC NULLS LAST
LIMIT 15
""".strip(),
    "company_19": """
SELECT c.ticker,
       c.company_name,
       fs.fiscal_year,
       fs.fiscal_quarter,
       fs.total_assets,
       fs.equity,
       fs.net_revenue,
       fs.net_income
FROM financial_statements fs
JOIN companies c ON c.id = fs.company_id
WHERE fs.fiscal_year = (SELECT MAX(fiscal_year) FROM financial_statements)
  AND fs.total_assets IS NOT NULL
ORDER BY fs.total_assets DESC NULLS LAST
LIMIT 15
""".strip(),
    "company_20": """
SELECT c.ticker,
       c.company_name,
       fs.fiscal_year,
       fs.fiscal_quarter,
       fs.total_assets,
       fs.equity,
       fs.total_debt,
       fs.cash_and_cash_equivalents,
       fs.total_current_assets,
       fs.short_term_borrowings,
       fs.operating_cash_flow,
       fs.de_ratio,
       fs.roe,
       fs.roa,
       CASE
         WHEN fs.short_term_borrowings > 0
         THEN ROUND(
           (fs.cash_and_cash_equivalents / fs.short_term_borrowings)::numeric, 3
         )
       END AS cash_cover_short_borrowings
FROM financial_statements fs
JOIN companies c ON c.id = fs.company_id
WHERE fs.fiscal_year = (SELECT MAX(fiscal_year) FROM financial_statements)
ORDER BY fs.total_assets DESC NULLS LAST
LIMIT 40
""".strip(),
}

_FALLBACK_MARKET_SQL = _SQL_BY_TEMPLATE["market_01"]
_FALLBACK_COMPANY_SQL = _SQL_BY_TEMPLATE["company_01"]


def sql_catalog_ids() -> list[str]:
    return sorted(_SQL_BY_TEMPLATE.keys())


def get_sql_for_template(template_id: str) -> str | None:
    tid = (template_id or "").strip()
    return _SQL_BY_TEMPLATE.get(tid)
