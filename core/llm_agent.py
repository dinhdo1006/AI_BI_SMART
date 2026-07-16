"""Prompt builder & gọi Ollama để sinh SQL / insight."""

from __future__ import annotations

import json
import os
import re
from typing import Any

from core.ollama_client import make_ollama_llm
from langchain_ollama import OllamaLLM

from core.db_dialect import SqlDialect, detect_dialect, dialect_label
from core.insight_stats import compute_insight_stats

# Model local qua Ollama — SQL và Insight tách riêng (cấu hình qua .env)
_SQL_MODEL = os.getenv("SQL_MODEL", "sqlcoder:7b")
_INSIGHT_MODEL = os.getenv("INSIGHT_MODEL", "qwen2.5:14b")

# Loại bỏ markdown fence nếu LLM vẫn cố bọc ```sql ... ```
_MARKDOWN_FENCE: re.Pattern[str] = re.compile(
    r"```(?:sql)?\s*\n?(.*?)\n?```",
    re.IGNORECASE | re.DOTALL,
)

# SQLCoder hay echo lại header prompt tiếng Việt → syntax error near "BÁO"/"HỎI"
_SQL_NOISE_CUT: re.Pattern[str] = re.compile(
    r"(?is)\n\s*(?:"
    r"===|"
    r"---|"
    r"THÔNG\s*BÁO|"
    r"CÂU\s*HỎI|"
    r"SQL\s*BỊ|"
    r"LỊCH\s*SỬ|"
    r"ERROR\s*MESSAGE|"
    r"BROKEN\s*SQL|"
    r"CURRENT\s*QUESTION|"
    r"Explanation\s*:|"
    r"Note\s*:|"
    r"Hãy\s+"
    r")"
)

_SQL_START: re.Pattern[str] = re.compile(r"(?is)\b(WITH|SELECT)\b")


def _dialect_date_rules(dialect: SqlDialect) -> str:
    if dialect == "postgresql":
        return """=== CÚ PHÁP NGÀY THÁNG (PostgreSQL) ===
- Tuần gần đây: cột_ngày >= CURRENT_DATE - INTERVAL '7 days'
- Tháng hiện tại: cột_ngày >= date_trunc('month', CURRENT_DATE)
- Gom theo tháng: to_char(cột_ngày::date, 'YYYY-MM') AS thang_gd
- Gom theo quý: to_char(cột_ngày::date, 'YYYY') || '-Q' || EXTRACT(QUARTER FROM cột_ngày::date)::int
- Định dạng ngày text: cột_ngày::date"""
    return """=== CÚ PHÁP NGÀY THÁNG (SQLite) ===
- Tuần gần đây: cột_ngày >= date('now', '-7 day')
- Đầu tháng: cột_ngày >= date('now', 'start of month')
- Gom theo tháng: strftime('%Y-%m', cột_ngày) AS thang_gd
- Gom theo quý: strftime('%Y', cột_ngày) || '-Q' || ((CAST(strftime('%m', cột_ngày) AS INTEGER)-1)/3+1)"""


def _build_system_prompt(domain_config: dict[str, Any]) -> str:
    """
    Ghép System Prompt từ Role + Schema + Dictionary + Few-shot.

    Prompt ép LLM chỉ trả về raw SQL, không giải thích, không markdown.
    """
    domain_name = domain_config.get("domain_name", "Unknown Domain")
    dialect: SqlDialect = domain_config.get("sql_dialect") or detect_dialect(
        domain_config.get("db_url", "")
    )
    db_label = dialect_label(dialect)
    ddl = domain_config["ddl_schema"]
    dictionary = json.dumps(
        domain_config["data_dictionary"], ensure_ascii=False, indent=2
    )
    rag_tables = domain_config.get("schema_rag_tables") or []
    rag_note = ""
    if rag_tables:
        rag_note = (
            f"\n(Lưu ý: Schema đã lọc theo câu hỏi — chỉ dùng các bảng: "
            f"{', '.join(rag_tables)}.)\n"
        )

    # Few-shot: ghép từng cặp Q → SQL
    examples_parts: list[str] = []
    for i, ex in enumerate(domain_config["few_shot_examples"], start=1):
        examples_parts.append(
            f"Ví dụ {i}:\n"
            f"Câu hỏi: {ex['question']}\n"
            f"SQL: {ex['sql']}"
        )
    examples_block = "\n\n".join(examples_parts)

    return f"""Bạn là SQL Expert chuyên nghiệp cho domain "{domain_name}".
Nhiệm vụ: chuyển câu hỏi tiếng Việt của người dùng thành đúng MỘT câu SQL ({db_label}).
{rag_note}
=== DDL SCHEMA ===
{ddl}

=== DATA DICTIONARY ===
{dictionary}

=== FEW-SHOT EXAMPLES ===
{examples_block}

{_dialect_date_rules(dialect)}

=== QUY TẮC BẮT BUỘC ===
1. CHỈ trả về duy nhất câu SQL thô (raw SQL).
2. TUYỆT ĐỐI KHÔNG bọc trong markdown (không dùng ```sql hoặc ```).
3. TUYỆT ĐỐI KHÔNG giải thích, không thêm chú thích, không thêm dòng trống thừa.
4. Chỉ dùng SELECT — không được sinh DROP/DELETE/UPDATE/INSERT/ALTER.
5. Chỉ truy vấn các bảng và cột CÓ THẬT trong schema (không bịa cột như updated_at_week_1).
6. Alias chỉ đặt SAU AS (vd: f.updated_at AS updated_at). Trong ORDER BY/WHERE/GROUP BY:
   dùng tên cột thật (f.updated_at) hoặc alias KHÔNG gắn tiền tố bảng (updated_at).
   CẤM viết f.updated_at_week_1 — đó không phải cột của bảng.
7. So sánh tuần/tháng: dùng cú pháp ngày tháng của {db_label} (xem mục CÚ PHÁP NGÀY THÁNG).
8. Đặt alias tiếng Anh rõ (avg_progress_pct, von_hoa, gia_dong_cua, khoi_luong_gd).
9. Nếu có Lịch sử Trò chuyện: hiểu ngữ cảnh, nhưng chỉ sinh SQL cho CÂU HỎI HIỆN TẠI.

=== QUY TẮC ORDER BY / GROUP BY / LIMIT (BẮT BUỘC CHO BIỂU ĐỒ) ===
10. ORDER BY thời gian (ngày_gd, updated_at, surveyed_at, start_date):
    - Xu hướng / diễn biến / theo thời gian → ORDER BY cột ngày ASC (cũ → mới).
    - N phiên / N ngày GẦN NHẤT: dùng ORDER BY ngày DESC LIMIT N (lấy N bản ghi mới nhất).
11. ORDER BY xếp hạng:
    - Top / cao nhất / lớn nhất / vốn hóa lớn → ORDER BY chỉ số chính DESC + LIMIT N (mặc định 5).
    - Thấp nhất / nhỏ nhất / chậm nhất → ORDER BY ASC + LIMIT N nếu cần.
12. GROUP BY khi câu hỏi yêu cầu tổng hợp:
    - "theo từng", "theo tháng/quý", "trung bình từng", "tổng theo" → GROUP BY đúng chiều.
    - Gom theo tháng: dùng quy tắc trong mục CÚ PHÁP NGÀY THÁNG.
    - Gom theo quý: ky_bc nếu có sẵn trong bảng BCTC, hoặc quy tắc quý trong CÚ PHÁP NGÀY THÁNG.
13. Luôn SELECT cột dimension + metric rõ ràng (vd: project_name + avg_progress_pct).
14. So sánh nhiều mã CP / nhiều dự án: dùng WHERE ... IN (...) hoặc JOIN, không bỏ sót mã user nêu.
15. Không SELECT * — liệt kê cột cần thiết với alias AS tên_cột (snake_case, khớp data_dictionary).
16. Nếu câu hỏi chỉ "danh sách / liệt kê" không có số so sánh: SELECT các cột mô tả, không cần GROUP BY.
17. Domain tài chính / VNFDATA (PostgreSQL):
    - stock_prices KHÔNG có symbol → JOIN companies c ON c.id = stock_prices.company_id, lọc c.ticker.
    - financial_statements dùng company_id → JOIN companies; cột net_revenue / net_income / fiscal_year / fiscal_quarter.
    - financial_indicators.symbol = companies.ticker; dùng pe_ratio, pb_ratio, eps_ttm (không pe/pb/eps).
    - index_constituents: cột group_code + ticker (CẤM index_symbol / stock_symbol / weight).
    - market_indices: cột code + name (CẤM symbol).
    - Diễn biến giá / OHLC: ưu tiên SELECT open_price, high_price, low_price, close_price, volume + trade_date (để vẽ nến/combo).
    - Cột numeric đã là numeric — CẤM to_number(...::text, ...).
    - Sàn HOSE/HSX: JOIN exchanges e ON e.id = companies.exchange_id WHERE UPPER(e.code) IN ('HOSE','HSX').
"""


def _format_history(history: list[dict[str, str]] | None) -> str:
    """
    Chuyển history thành khối text nhúng vào prompt.
    Mỗi phần tử kỳ vọng: {"role": "user"|"assistant", "content": "..."}.
    """
    if not history:
        return "(Không có lịch sử — đây là câu hỏi đầu tiên.)"

    lines: list[str] = []
    for msg in history:
        role = msg.get("role", "user")
        label = "Người dùng" if role == "user" else "Trợ lý"
        content = (msg.get("content") or "").strip()
        if content:
            lines.append(f"{label}: {content}")
    return "\n".join(lines) if lines else "(Không có lịch sử — đây là câu hỏi đầu tiên.)"


def _clean_sql_output(raw: str) -> str:
    """Làm sạch output LLM: bỏ fence, cắt echo prompt, chỉ giữ SELECT/WITH."""
    cleaned = (raw or "").strip()
    fence_match = _MARKDOWN_FENCE.search(cleaned)
    if fence_match:
        cleaned = fence_match.group(1).strip()

    if cleaned.upper().startswith("SQL:"):
        cleaned = cleaned[4:].strip()

    start = _SQL_START.search(cleaned)
    if start:
        cleaned = cleaned[start.start() :]

    noise = _SQL_NOISE_CUT.search(cleaned)
    if noise:
        cleaned = cleaned[: noise.start()]

    # Bỏ phần sau dấu ; đầu tiên (LLM hay thêm giải thích phía sau)
    if ";" in cleaned:
        cleaned = cleaned.split(";", 1)[0]

    # Bỏ dòng comment / dòng toàn chữ Việt không phải SQL
    kept: list[str] = []
    for line in cleaned.splitlines():
        s = line.strip()
        if not s or s.startswith("--"):
            continue
        if re.search(
            r"[àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ]",
            s,
            re.IGNORECASE,
        ) and not re.search(r"\b(SELECT|FROM|WHERE|JOIN|AND|OR|ORDER|GROUP|LIMIT|AS|ON|WITH)\b", s, re.I):
            break
        kept.append(line.rstrip())
    cleaned = "\n".join(kept).strip()
    return cleaned.rstrip(";").strip()


def _get_llm(*, model: str, num_predict: int = 512) -> OllamaLLM:
    """Khởi tạo Ollama LLM — giới hạn num_predict để phản hồi nhanh hơn."""
    return make_ollama_llm(
        model=model,
        temperature=0.0,
        num_predict=num_predict,
        timeout=150,
    )


_SQL_NUM_PREDICT = 320
_INSIGHT_NUM_PREDICT = 1400
_MAX_INSIGHT_ROWS = 60


def generate_sql(
    domain_config: dict[str, Any],
    user_query: str,
    history: list[dict[str, str]] | None = None,
    entity_hint: str | None = None,
) -> str:
    """
    Gọi Ollama để sinh SQL từ câu hỏi người dùng (có ngữ cảnh history).

    Args:
        domain_config: Dict config đã load từ configs/{domain}.json.
        user_query: Câu hỏi tiếng Việt hiện tại của user.
        history: Lịch sử trò chuyện gần đây (role + content), có thể rỗng.
        entity_hint: Gợi ý entity đã resolve từ DB (mã CK…), không bắt buộc.

    Returns:
        Chuỗi SQL thô (không markdown). Guardrail SELECT-only vẫn áp dụng ở db_executor.
    """
    system_prompt = _build_system_prompt(domain_config)
    history_block = _format_history(history)
    hint_block = ""
    if entity_hint and entity_hint.strip():
        hint_block = f"=== ENTITY HINTS ===\n{entity_hint.strip()}\n\n"

    # Header tiếng Anh — giảm nguy cơ SQLCoder echo chữ Việt vào SQL
    full_prompt = (
        f"{system_prompt}\n\n"
        f"=== CHAT HISTORY ===\n"
        f"Use chat history for context (pronouns like 'it'), "
        f"but your ONLY task is to write SQL for the CURRENT QUESTION.\n\n"
        f"{history_block}\n\n"
        f"{hint_block}"
        f"=== CURRENT QUESTION ===\n"
        f"{user_query}\n\n"
        f"SQL:"
    )

    raw_output: str = _get_llm(
        model=_SQL_MODEL, num_predict=_SQL_NUM_PREDICT
    ).invoke(full_prompt)
    sql = _clean_sql_output(raw_output)
    if sql:
        return sql

    # Retry tự động khi LLM trả rỗng / chỉ giải thích — không hardcode SQL
    retry_prompt = (
        f"{system_prompt}\n\n"
        f"{hint_block}"
        f"=== CURRENT QUESTION ===\n{user_query}\n\n"
        f"IMPORTANT: Previous attempt produced NO SQL. "
        f"Output exactly ONE PostgreSQL SELECT starting with SELECT or WITH. "
        f"No markdown, no Vietnamese explanation.\n\n"
        f"SQL:"
    )
    raw_retry: str = _get_llm(
        model=_SQL_MODEL, num_predict=_SQL_NUM_PREDICT
    ).invoke(retry_prompt)
    return _clean_sql_output(raw_retry)


def repair_sql(
    domain_config: dict[str, Any],
    user_query: str,
    broken_sql: str,
    error_message: str,
    history: list[dict[str, str]] | None = None,
    entity_hint: str | None = None,
) -> str:
    """
    Sửa SQL khi thực thi lỗi (1 lần). Gửi lỗi DB + SQL cũ cho LLM viết lại.
    """
    dialect: SqlDialect = domain_config.get("sql_dialect") or detect_dialect(
        domain_config.get("db_url", "")
    )
    db_label = dialect_label(dialect)
    system_prompt = _build_system_prompt(domain_config)
    history_block = _format_history(history)
    hint_block = ""
    if entity_hint and entity_hint.strip():
        hint_block = f"=== ENTITY HINTS ===\n{entity_hint.strip()}\n\n"
    # Header tiếng Anh — tránh SQLCoder echo "THÔNG BÁO"/"CÂU HỎI" vào SQL
    prompt = (
        f"{system_prompt}\n\n"
        f"=== CHAT HISTORY ===\n{history_block}\n\n"
        f"{hint_block}"
        f"=== CURRENT QUESTION ===\n{user_query}\n\n"
        f"=== BROKEN SQL ===\n{broken_sql}\n\n"
        f"=== ERROR MESSAGE ===\n{error_message}\n\n"
        f"Rewrite ONE valid {db_label} SELECT that answers the question. "
        f"Use only real columns from schema. Output raw SQL only — no explanation.\n\n"
        f"SQL:"
    )
    return _clean_sql_output(
        _get_llm(model=_SQL_MODEL, num_predict=_SQL_NUM_PREDICT).invoke(prompt)
    )


def _rename_row_keys(
    rows: list[dict[str, Any]], labels: dict[str, str]
) -> list[dict[str, Any]]:
    if not labels:
        return rows
    return [{labels.get(k, k): v for k, v in row.items()} for row in rows]


def _rename_stats_keys(stats: dict[str, Any], labels: dict[str, str]) -> dict[str, Any]:
    if not labels:
        return stats
    out = dict(stats)
    if "numeric" in out:
        out["numeric"] = {labels.get(k, k): v for k, v in out["numeric"].items()}
    if "top_categories" in out:
        out["top_categories"] = {
            labels.get(k, k): v for k, v in out["top_categories"].items()
        }
    if "date_range" in out:
        out["date_range"] = {labels.get(k, k): v for k, v in out["date_range"].items()}
    if "highlights" in out:
        h = dict(out["highlights"])
        if "metric" in h:
            h["metric"] = labels.get(str(h["metric"]), h["metric"])
        out["highlights"] = h
    if "outliers" in out:
        renamed_outliers: list[dict[str, Any]] = []
        for item in out["outliers"]:
            row = dict(item)
            if "metric" in row:
                row["metric"] = labels.get(str(row["metric"]), row["metric"])
            renamed_outliers.append(row)
        out["outliers"] = renamed_outliers
    if "trend" in out:
        t = dict(out["trend"])
        if "metric" in t:
            t["metric"] = labels.get(str(t["metric"]), t["metric"])
        if "date_col" in t:
            t["date_col"] = labels.get(str(t["date_col"]), t["date_col"])
        out["trend"] = t
    if "top_bottom" in out:
        tb = dict(out["top_bottom"])
        if "metric" in tb:
            tb["metric"] = labels.get(str(tb["metric"]), tb["metric"])
        if "label_col" in tb:
            tb["label_col"] = labels.get(str(tb["label_col"]), tb["label_col"])
        out["top_bottom"] = tb
    if "period_comparison" in out:
        pc = dict(out["period_comparison"])
        if "metric" in pc:
            pc["metric"] = labels.get(str(pc["metric"]), pc["metric"])
        if "date_col" in pc:
            pc["date_col"] = labels.get(str(pc["date_col"]), pc["date_col"])
        out["period_comparison"] = pc
    if "forecast" in out:
        fc = dict(out["forecast"])
        if "metric" in fc:
            fc["metric"] = labels.get(str(fc["metric"]), fc["metric"])
        if "date_col" in fc:
            fc["date_col"] = labels.get(str(fc["date_col"]), fc["date_col"])
        out["forecast"] = fc
    if "correlation" in out:
        corr = dict(out["correlation"])
        for key in ("metric_a", "metric_b"):
            if key in corr:
                corr[key] = labels.get(str(corr[key]), corr[key])
        out["correlation"] = corr
    return out


def generate_insight(
    user_query: str,
    raw_json_data: list[dict[str, Any]],
    column_labels: dict[str, str] | None = None,
    precomputed_stats: dict[str, Any] | None = None,
) -> str:
    """
    Phân tích kết quả truy vấn và viết báo cáo chi tiết bằng tiếng Việt.

    Args:
        user_query: Câu hỏi gốc của người dùng.
        raw_json_data: Mảng dict trả về từ db_executor (chỉ số liệu thật).
        precomputed_stats: Stats đã tính (tránh compute_insight_stats 2 lần).

    Returns:
        Đoạn insight tiếng Việt — không bịa số ngoài JSON.
    """
    # Không có dữ liệu → trả insight cố định, không gọi LLM
    if not raw_json_data:
        return (
            "Không có bản ghi nào khớp với câu hỏi. "
            "Hãy thử điều chỉnh điều kiện hoặc kiểm tra lại domain."
        )

    rows_for_insight = _rename_row_keys(
        raw_json_data[:_MAX_INSIGHT_ROWS], column_labels or {}
    )
    data_json = json.dumps(rows_for_insight, ensure_ascii=False, indent=2)
    raw_stats = precomputed_stats if precomputed_stats is not None else (
        compute_insight_stats(raw_json_data)
    )
    stats = _rename_stats_keys(raw_stats, column_labels or {})
    stats_json = json.dumps(stats, ensure_ascii=False, indent=2)
    truncated_note = ""
    if len(raw_json_data) > _MAX_INSIGHT_ROWS:
        truncated_note = (
            f"\n(Lưu ý: mẫu JSON chỉ gồm {_MAX_INSIGHT_ROWS} dòng đầu / "
            f"{len(raw_json_data)} dòng tổng — thống kê tổng hợp đã tính trên toàn bộ.)\n"
        )

    prompt = f"""Bạn là chuyên gia phân tích dữ liệu BI (Business Intelligence).
Nhiệm vụ: đọc câu hỏi, THỐNG KÊ TỔNG HỢP (đã tính sẵn) và mẫu JSON, rồi viết
một BÁO CÁO PHÂN TÍCH chi tiết, đầy đủ bằng tiếng Việt (khoảng 400–700 từ).

=== CÂU HỎI NGƯỜI DÙNG ===
{user_query}

=== THỐNG KÊ TỔNG HỢP (đã tính bằng code — ưu tiên dùng các số này) ===
{stats_json}

=== MẪU DỮ LIỆU JSON (tham chiếu chi tiết từng dòng) ===
{data_json}{truncated_note}

=== CẤU TRÚC BÁO CÁO (bắt buộc — viết đủ tất cả mục) ===
Bắt đầu NGAY bằng dòng **Tóm tắt:** — không thêm tiêu đề hay đoạn mở đầu khác.

- **Tóm tắt:** 2–3 câu nêu kết luận chính, có số liệu cụ thể từ THỐNG KÊ.

- **Điểm nổi bật:** 5–8 bullet — cao nhất/thấp nhất, chênh lệch lớn, outlier,
  top category (nếu có top_categories), highlights (nếu có).

- **Phân tích chi tiết:** 4–6 câu so sánh cụ thể giữa các đối tượng/nhóm trong data;
  nêu tên đối tượng và con số; so sánh với trung bình hoặc median khi có trong THỐNG KÊ.

- **Xu hướng & biến động:** 2–4 câu — nếu có date_range thì mô tả diễn biến theo thời gian;
  nếu có forecast thì nêu hướng + giá trị dự báo ngắn hạn và nhắc đây là ước lượng tuyến tính
  (không phải cam kết chính thức); nếu không có cột ngày thì ghi rõ "Không đủ dữ liệu thời gian
  để đánh giá xu hướng" và phân tích phân bố/chênh lệch thay thế.

- **Phát hiện bất thường:** 2–3 bullet — giá trị lệch xa trung bình, khoảng cách min–max lớn,
  nhóm chiếm tỷ trọng bất thường (chỉ dựa trên số có sẵn).

- **Rủi ro & giới hạn dữ liệu:** 1–2 câu — số dòng ít, thiếu kỳ so sánh, hoặc metric chưa đủ
  để kết luận dài hạn (nếu áp dụng).

- **Gợi ý theo dõi:** 2–3 câu hành động/khía cạnh cần drill-down tiếp (chỉ dựa trên data có sẵn).

=== QUY TẮC BẮT BUỘC ===
1. Ưu tiên số liệu trong THỐNG KÊ TỔNG HỢP; mẫu JSON để minh họa và bổ sung chi tiết.
2. TUYỆT ĐỐI KHÔNG bịa số ngoài THỐNG KÊ và JSON.
3. Mỗi mục phải có ít nhất một con số cụ thể (tên chỉ số + giá trị).
4. Dùng markdown (in đậm tiêu đề mục), tiếng Việt chuyên nghiệp, dễ đọc.
5. Không nhắc SQL, LLM hay kỹ thuật backend.
6. Không lặp lại cùng một số liệu quá 2 lần trong toàn báo cáo.
7. Khi nhắc chỉ số/cột: CHỈ dùng tên hiển thị tiếng Việt trong JSON (không dùng snake_case như gia_mo).
8. Mỗi tiêu đề mục (Tóm tắt, Điểm nổi bật, …) chỉ xuất hiện ĐÚNG MỘT LẦN ở đầu dòng;
   không lặp từ "xu hướng", "bất thường" như tiêu đề trong thân câu.
"""

    llm = _get_llm(model=_INSIGHT_MODEL, num_predict=_INSIGHT_NUM_PREDICT)
    insight: str = llm.invoke(prompt)
    return insight.strip()
