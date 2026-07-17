"""
Monitoring — đọc audit.jsonl và tính metrics tổng hợp.

Metrics:
  - total_requests: tổng request chat
  - success_rate: % status=success
  - cache_hit_rate: % from_cache=true
  - avg_latency_ms, p95_latency_ms, p99_latency_ms
  - sql_source_breakdown: phân bổ theo sql_source
  - intent_breakdown: phân bổ theo intent
  - error_rate: % status != success
  - requests_by_hour: histogram 24h gần nhất
  - top_queries: câu hỏi nhiều nhất
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

_LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
_AUDIT_FILE = _LOG_DIR / "audit.jsonl"


def _read_audit_events(
    *,
    hours: int = 24,
    tenant_id: str | None = None,
    domain_id: str | None = None,
    limit: int = 50_000,
) -> list[dict[str, Any]]:
    """Đọc events từ audit.jsonl, lọc theo khoảng thời gian + tenant."""
    if not _AUDIT_FILE.exists():
        return []

    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    events: list[dict[str, Any]] = []

    try:
        with _AUDIT_FILE.open("r", encoding="utf-8") as f:
            for line in f:
                if len(events) >= limit:
                    break
                line = line.strip()
                if not line:
                    continue
                try:
                    ev = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if ev.get("event") != "chat_request":
                    continue
                # Lọc thời gian
                ts_str = ev.get("ts", "")
                try:
                    ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                    if ts < cutoff:
                        continue
                except (ValueError, AttributeError):
                    pass
                # Lọc tenant
                if tenant_id and ev.get("tenant_id") != tenant_id:
                    continue
                # Lọc domain
                if domain_id and ev.get("domain_id") != domain_id:
                    continue
                events.append(ev)
    except OSError:
        pass

    return events


def _percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    sorted_v = sorted(values)
    idx = int(len(sorted_v) * p / 100)
    idx = min(idx, len(sorted_v) - 1)
    return round(sorted_v[idx], 1)


def compute_metrics(
    *,
    hours: int = 24,
    tenant_id: str | None = None,
    domain_id: str | None = None,
) -> dict[str, Any]:
    """
    Tính metrics từ audit.jsonl trong khoảng `hours` giờ gần nhất.
    """
    events = _read_audit_events(hours=hours, tenant_id=tenant_id, domain_id=domain_id)
    total = len(events)

    if total == 0:
        return {
            "total_requests": 0,
            "hours": hours,
            "success_rate": 0.0,
            "error_rate": 0.0,
            "cache_hit_rate": 0.0,
            "avg_latency_ms": 0.0,
            "p95_latency_ms": 0.0,
            "p99_latency_ms": 0.0,
            "sql_source_breakdown": {},
            "intent_breakdown": {},
            "requests_by_hour": {},
            "top_queries": [],
        }

    success = sum(1 for e in events if e.get("status") == "success")
    cached = sum(1 for e in events if e.get("from_cache"))
    latencies = [
        float(e["latency_total_ms"])
        for e in events
        if isinstance(e.get("latency_total_ms"), (int, float))
    ]

    sql_source_cnt: Counter[str] = Counter(
        str(e.get("sql_source") or "unknown") for e in events
    )
    intent_cnt: Counter[str] = Counter(
        str(e.get("intent") or "unknown") for e in events if e.get("intent")
    )

    # Histogram theo giờ (24 giờ gần nhất)
    by_hour: dict[str, int] = defaultdict(int)
    now = datetime.now(timezone.utc)
    for e in events:
        ts_str = e.get("ts", "")
        try:
            ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            hour_key = ts.strftime("%Y-%m-%dT%H:00")
            by_hour[hour_key] += 1
        except (ValueError, AttributeError):
            pass

    # Top queries (bỏ câu quá ngắn)
    query_cnt: Counter[str] = Counter(
        str(e.get("query", ""))[:120]
        for e in events
        if len(str(e.get("query", ""))) > 5
    )
    top_queries = [
        {"query": q, "count": c}
        for q, c in query_cnt.most_common(10)
    ]

    return {
        "total_requests": total,
        "hours": hours,
        "success_rate": round(success / total * 100, 1),
        "error_rate": round((total - success) / total * 100, 1),
        "cache_hit_rate": round(cached / total * 100, 1),
        "avg_latency_ms": round(sum(latencies) / len(latencies), 1) if latencies else 0.0,
        "p95_latency_ms": _percentile(latencies, 95),
        "p99_latency_ms": _percentile(latencies, 99),
        "sql_source_breakdown": dict(sql_source_cnt.most_common(15)),
        "intent_breakdown": dict(intent_cnt.most_common(10)),
        "requests_by_hour": dict(sorted(by_hour.items())),
        "top_queries": top_queries,
    }
