"""Domain explorer — bảng / cột / câu hỏi mẫu từ configs/*.json (không query DB)."""

from __future__ import annotations

from typing import Any


def build_domain_explore(domain_config: dict[str, Any]) -> dict[str, Any]:
    """
    Tóm tắt schema nghiệp vụ để user biết có thể hỏi gì.

    Nguồn: data_dictionary + few_shot_examples + column_labels (config).
    """
    domain_id = str(domain_config.get("domain_id") or "")
    domain_name = str(domain_config.get("domain_name") or domain_id)
    dictionary = domain_config.get("data_dictionary") or {}
    labels: dict[str, str] = domain_config.get("column_labels") or {}
    few_shots = domain_config.get("few_shot_examples") or []

    tables: list[dict[str, Any]] = []
    for table_name, cols in dictionary.items():
        if not isinstance(cols, dict):
            continue
        table_desc = ""
        columns: list[dict[str, str]] = []
        for col_name, col_desc in cols.items():
            if col_name == "_table":
                table_desc = str(col_desc)
                continue
            columns.append(
                {
                    "name": str(col_name),
                    "label": labels.get(str(col_name), str(col_name)),
                    "description": str(col_desc),
                }
            )
        tables.append(
            {
                "name": str(table_name),
                "description": table_desc,
                "columns": columns,
            }
        )

    sample_questions: list[str] = []
    for item in few_shots:
        if isinstance(item, dict):
            q = str(item.get("question") or "").strip()
            if q and q not in sample_questions:
                sample_questions.append(q)

    return {
        "domain_id": domain_id,
        "domain_name": domain_name,
        "table_count": len(tables),
        "tables": tables,
        "sample_questions": sample_questions[:12],
    }
