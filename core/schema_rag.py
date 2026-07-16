"""RAG Schema — chọn bảng liên quan theo câu hỏi, thu gọn prompt LLM."""

from __future__ import annotations

import os
import re
import unicodedata
from typing import Any

from core.db_dialect import SqlDialect, detect_dialect
from core.schema_introspection import TableInfo, introspect_schema, tables_to_ddl

# Cache introspection theo db_url (schema ít đổi trong session)
_SCHEMA_CACHE: dict[str, dict[str, TableInfo]] = {}

# Partition / backup / ETL — không đưa vào prompt (VNFDATA ~240 bảng)
_NOISE_TABLE_RE = re.compile(
    r"("
    r"^sp_y\d{4}m\d{2}$|"
    r"_backup|"
    r"_pre_icb_|"
    r"^etl_|"
    r"^schema_migrations$|"
    r"^app_configs$|"
    r"^contact_messages$|"
    r"^realtime_ingestor|"
    r"^realtime_source_|"
    r"^stock_prices_pdefault$"
    r")",
    re.IGNORECASE,
)

# Gợi ý bảng từ từ khóa tiếng Việt (boost score)
_VI_TABLE_HINTS: list[tuple[tuple[str, ...], tuple[str, ...]]] = [
    (("doanh nghiep", "cong ty", "ma cp", "niêm yết", "niem yet"), ("companies", "stocks")),
    (("gia", "phien", "dong cua", "khoi luong", "ohlc", "dieu chinh"), ("stock_prices", "quotes_history")),
    (("intraday", "phut", "realtime", "thoi gian thuc"), ("quotes_intraday", "quotes_realtime", "stock_realtime")),
    (("bctc", "bao cao tai chinh", "doanh thu", "loi nhuan", "tai san"), ("financial_statements", "financial_statement_reports", "financial_statement_items")),
    (("pe", "pb", "eps", "roe", "roa", "von hoa", "chi so"), ("financial_indicators", "financial_ratios")),
    (("nganh", "sector", "icb"), ("sectors", "industries_icb", "sector_performance")),
    (("san", "hose", "hnx", "upcom", "exchange"), ("exchanges", "stocks")),
    (("index", "vnindex", "vn-index", "vn30", "thanh phan", "chi so thi truong"), ("market_indices", "index_constituents", "index_snapshots")),
    (("danh sach cong ty", "liet ke cong ty", "danh sach doanh nghiep"), ("companies", "exchanges")),
    (("khoi ngoai", "foreign"), ("foreign_trades",)),
    (("co dong", "so huu"), ("company_shareholders", "company_ownership_structure")),
    (("co tuc", "phat hanh", "corporate"), ("corporate_actions",)),
]


def _normalize(text: str) -> str:
    lowered = (text or "").lower()
    nfd = unicodedata.normalize("NFD", lowered)
    return "".join(c for c in nfd if unicodedata.category(c) != "Mn")


def _tokenize(text: str) -> set[str]:
    norm = _normalize(text)
    tokens = set(re.findall(r"[a-z0-9_]+", norm))
    return {t for t in tokens if len(t) >= 2}


def is_noise_table(table_name: str) -> bool:
    """True nếu bảng partition/backup/ETL — bỏ khỏi RAG."""
    return bool(_NOISE_TABLE_RE.search(table_name or ""))


def is_schema_rag_enabled() -> bool:
    return os.getenv("SCHEMA_RAG_ENABLED", "true").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def schema_rag_max_tables() -> int:
    try:
        return max(3, min(int(os.getenv("SCHEMA_RAG_MAX_TABLES", "15")), 40))
    except ValueError:
        return 15


def _get_cached_schema(db_url: str) -> dict[str, TableInfo]:
    if db_url not in _SCHEMA_CACHE:
        raw = introspect_schema(db_url)
        _SCHEMA_CACHE[db_url] = {
            k: v for k, v in raw.items() if not is_noise_table(k)
        }
    return _SCHEMA_CACHE[db_url]


def _hint_boost(table_name: str, query_norm: str) -> float:
    boost = 0.0
    for keywords, tables in _VI_TABLE_HINTS:
        if any(k in query_norm for k in keywords) and table_name in tables:
            boost += 4.0
    return boost


def _score_table(
    table_name: str,
    table: TableInfo,
    query_tokens: set[str],
    query_norm: str,
    dictionary: dict[str, Any],
) -> float:
    score = 0.0
    name_norm = _normalize(table_name)
    name_tokens = set(name_norm.replace("_", " ").split())

    for tok in query_tokens:
        if tok in name_norm or tok in name_tokens:
            score += 3.0
        for col in table.columns:
            col_norm = _normalize(col.name)
            if tok in col_norm:
                score += 2.0

    # data_dictionary mô tả nghiệp vụ
    table_dict = dictionary.get(table_name, {})
    if isinstance(table_dict, dict):
        blob = _normalize(
            " ".join(str(v) for v in table_dict.values())
            + " "
            + " ".join(str(k) for k in table_dict.keys())
        )
        for tok in query_tokens:
            if tok in blob:
                score += 1.5

    if table_name in dictionary:
        score += 0.5

    score += _hint_boost(table_name, query_norm)
    return score


def _tables_from_few_shot(few_shot_examples: list[dict[str, str]]) -> set[str]:
    found: set[str] = set()
    for ex in few_shot_examples:
        sql = ex.get("sql", "")
        for m in re.finditer(r"\b(?:FROM|JOIN)\s+([a-zA-Z_][a-zA-Z0-9_]*)", sql, re.I):
            found.add(m.group(1))
    return found


def select_relevant_tables(
    db_url: str,
    user_query: str,
    data_dictionary: dict[str, Any],
    few_shot_examples: list[dict[str, str]] | None = None,
    *,
    max_tables: int | None = None,
) -> list[str]:
    """
    Chọn top-K bảng liên quan nhất với câu hỏi.
    Luôn ưu tiên bảng xuất hiện trong few-shot SQL của domain.
    """
    live = _get_cached_schema(db_url)
    domain_tables = set(data_dictionary.keys())
    if not live:
        return sorted(domain_tables)

    # Allowlist dictionary ∩ live; nếu lệch schema (mock→Postgres) dùng live đã lọc noise
    schema = {k: v for k, v in live.items() if k in domain_tables}
    if not schema:
        schema = dict(live)

    limit = max_tables or schema_rag_max_tables()
    query_tokens = _tokenize(user_query)
    query_norm = _normalize(user_query)
    few_shot_tables = {
        t for t in _tables_from_few_shot(few_shot_examples or []) if t in schema
    }

    scored: list[tuple[float, str]] = []
    for name, table in schema.items():
        s = _score_table(name, table, query_tokens, query_norm, data_dictionary)
        if name in few_shot_tables:
            s += 10.0
        scored.append((s, name))

    scored.sort(key=lambda x: (-x[0], x[1]))

    selected: list[str] = []
    for s, name in scored:
        if s <= 0 and name not in few_shot_tables:
            continue
        if name not in selected:
            selected.append(name)
        if len(selected) >= limit:
            break

    if not selected:
        # Ưu tiên bảng trong dictionary / few-shot
        preferred = [t for t in domain_tables if t in schema]
        preferred += [t for t in few_shot_tables if t not in preferred]
        selected = (preferred or list(schema.keys()))[:limit]

    if len(schema) <= limit:
        return sorted(schema.keys())

    return selected


def build_rag_schema_context(
    domain_config: dict[str, Any],
    user_query: str,
) -> dict[str, Any]:
    """
    Trả về bản copy domain_config với ddl_schema + data_dictionary đã thu gọn.
    Thêm sql_dialect và schema_rag_tables để debug.
    """
    db_url = domain_config["db_url"]
    dialect: SqlDialect = detect_dialect(db_url)
    out = dict(domain_config)
    out["sql_dialect"] = dialect

    if not is_schema_rag_enabled():
        from core.few_shot_retriever import rank_few_shots

        few_shot = domain_config.get("few_shot_examples") or []
        if few_shot:
            out["few_shot_examples"] = rank_few_shots(user_query, list(few_shot))
        out["schema_rag_tables"] = []
        return out

    dictionary: dict[str, Any] = domain_config.get("data_dictionary", {})
    few_shot = domain_config.get("few_shot_examples", [])

    live_schema = _get_cached_schema(db_url)
    if not live_schema:
        # Không introspect được → giữ config tĩnh
        out["schema_rag_tables"] = list(dictionary.keys())
        return out

    selected = select_relevant_tables(
        db_url,
        user_query,
        dictionary,
        few_shot,
    )
    out["schema_rag_tables"] = selected

    # Đưa few-shot liên quan lên đầu prompt (tự động theo câu hỏi)
    from core.few_shot_retriever import rank_few_shots

    if few_shot:
        out["few_shot_examples"] = rank_few_shots(user_query, list(few_shot))

    subset = {k: live_schema[k] for k in selected if k in live_schema}
    rag_ddl = tables_to_ddl(subset, dialect)
    if rag_ddl:
        out["ddl_schema"] = rag_ddl

    # Dictionary: giữ mô tả bảng đã chọn; cột thiếu thì thêm stub từ live DDL
    slim_dict: dict[str, Any] = {}
    for name in selected:
        if name in dictionary:
            slim_dict[name] = dictionary[name]
        elif name in live_schema:
            slim_dict[name] = {
                c.name: f"Cột {c.name} ({c.type_sql})"
                for c in live_schema[name].columns[:40]
            }
    out["data_dictionary"] = slim_dict

    return out


def invalidate_schema_cache(db_url: str | None = None) -> None:
    """Xóa cache introspection (khi đổi DB hoặc migrate)."""
    if db_url:
        _SCHEMA_CACHE.pop(db_url, None)
    else:
        _SCHEMA_CACHE.clear()
