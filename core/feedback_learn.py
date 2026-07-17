"""
Học từ feedback người dùng (👍/👎).

👍 + SQL hợp lệ → lưu few-shot động (ưu tiên trong prompt lần sau).
👎 → blacklist semantic (chặn cache tương tự) + gỡ few-shot đã học trùng câu.
"""

from __future__ import annotations

import sqlite3
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from core.query_cache import jaccard_similarity, semantic_fingerprint, semantic_tokens

_LOCK = threading.Lock()
_DB_PATH = Path(__file__).resolve().parent.parent / ".cache" / "feedback_learn.db"

_MAX_LEARNED = 200
_MAX_BLACKLIST = 500
_BLACKLIST_JACCARD = 0.72


def _connect() -> sqlite3.Connection:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS learned_examples (
            id TEXT PRIMARY KEY,
            domain_id TEXT NOT NULL,
            tenant_id TEXT,
            query_text TEXT NOT NULL,
            sql_text TEXT NOT NULL,
            created_at REAL NOT NULL,
            artifact_id TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS semantic_blacklist (
            id TEXT PRIMARY KEY,
            domain_id TEXT NOT NULL,
            tenant_id TEXT,
            query_text TEXT NOT NULL,
            semantic_fp TEXT NOT NULL,
            created_at REAL NOT NULL,
            artifact_id TEXT
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_learned_domain "
        "ON learned_examples(domain_id, created_at DESC)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_blacklist_domain "
        "ON semantic_blacklist(domain_id, semantic_fp)"
    )
    conn.commit()
    return conn


def _tenant_match_sql(tenant_id: str | None) -> tuple[str, tuple[Any, ...]]:
    if tenant_id:
        return "(tenant_id IS NULL OR tenant_id = ?)", (tenant_id,)
    return "1=1", ()


def record_upvote(
    *,
    domain_id: str,
    query: str,
    sql_query: str,
    tenant_id: str | None = None,
    artifact_id: str | None = None,
) -> bool:
    """Lưu SQL đạt 👍 làm few-shot động. Trả True nếu đã ghi."""
    q = (query or "").strip()
    sql = (sql_query or "").strip()
    if not q or not sql or sql.startswith("("):
        return False
    # Bỏ SQL lỗi / placeholder
    low = sql.lower()
    if low in ("", "n/a") or "error" in low[:40]:
        return False

    now = time.time()
    row_id = uuid.uuid4().hex[:12]
    with _LOCK:
        conn = _connect()
        try:
            # Tránh trùng exact query+sql
            existing = conn.execute(
                """
                SELECT id FROM learned_examples
                WHERE domain_id = ? AND query_text = ? AND sql_text = ?
                LIMIT 1
                """,
                (domain_id, q, sql),
            ).fetchone()
            if existing:
                return False
            conn.execute(
                """
                INSERT INTO learned_examples
                (id, domain_id, tenant_id, query_text, sql_text, created_at, artifact_id)
                VALUES (?,?,?,?,?,?,?)
                """,
                (row_id, domain_id, tenant_id, q, sql, now, artifact_id),
            )
            # Giữ tối đa N bản ghi mới nhất / domain
            conn.execute(
                """
                DELETE FROM learned_examples
                WHERE domain_id = ? AND id NOT IN (
                    SELECT id FROM learned_examples
                    WHERE domain_id = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                )
                """,
                (domain_id, domain_id, _MAX_LEARNED),
            )
            conn.commit()
            return True
        finally:
            conn.close()


def record_downvote(
    *,
    domain_id: str,
    query: str,
    tenant_id: str | None = None,
    artifact_id: str | None = None,
) -> dict[str, int]:
    """
    Blacklist semantic + gỡ few-shot đã học trùng/gần câu hỏi.
    Trả {"blacklisted": 0|1, "examples_removed": n}.
    """
    q = (query or "").strip()
    if not q:
        return {"blacklisted": 0, "examples_removed": 0}

    now = time.time()
    fp = semantic_fingerprint(q)
    q_toks = semantic_tokens(q)
    removed = 0
    blacklisted = 0

    with _LOCK:
        conn = _connect()
        try:
            # Gỡ learned examples trùng hoặc gần semantic
            rows = conn.execute(
                """
                SELECT id, query_text FROM learned_examples
                WHERE domain_id = ?
                """,
                (domain_id,),
            ).fetchall()
            drop_ids: list[str] = []
            for row in rows:
                cand = str(row["query_text"])
                if cand.strip().lower() == q.lower():
                    drop_ids.append(row["id"])
                    continue
                if q_toks and jaccard_similarity(q_toks, semantic_tokens(cand)) >= _BLACKLIST_JACCARD:
                    drop_ids.append(row["id"])
            for did in drop_ids:
                conn.execute("DELETE FROM learned_examples WHERE id = ?", (did,))
            removed = len(drop_ids)

            # Thêm blacklist nếu chưa có fingerprint
            exists = conn.execute(
                """
                SELECT id FROM semantic_blacklist
                WHERE domain_id = ? AND semantic_fp = ?
                LIMIT 1
                """,
                (domain_id, fp),
            ).fetchone()
            if not exists:
                conn.execute(
                    """
                    INSERT INTO semantic_blacklist
                    (id, domain_id, tenant_id, query_text, semantic_fp, created_at, artifact_id)
                    VALUES (?,?,?,?,?,?,?)
                    """,
                    (
                        uuid.uuid4().hex[:12],
                        domain_id,
                        tenant_id,
                        q,
                        fp,
                        now,
                        artifact_id,
                    ),
                )
                blacklisted = 1
                conn.execute(
                    """
                    DELETE FROM semantic_blacklist
                    WHERE domain_id = ? AND id NOT IN (
                        SELECT id FROM semantic_blacklist
                        WHERE domain_id = ?
                        ORDER BY created_at DESC
                        LIMIT ?
                    )
                    """,
                    (domain_id, domain_id, _MAX_BLACKLIST),
                )
            conn.commit()
        finally:
            conn.close()

    return {"blacklisted": blacklisted, "examples_removed": removed}


def is_query_blacklisted(
    domain_id: str,
    query: str,
    tenant_id: str | None = None,
) -> bool:
    """True nếu câu hỏi khớp blacklist (exact fingerprint hoặc Jaccard cao)."""
    q = (query or "").strip()
    if not q:
        return False
    fp = semantic_fingerprint(q)
    q_toks = semantic_tokens(q)
    where_t, t_args = _tenant_match_sql(tenant_id)

    with _LOCK:
        conn = _connect()
        try:
            row = conn.execute(
                f"""
                SELECT 1 FROM semantic_blacklist
                WHERE domain_id = ? AND semantic_fp = ? AND {where_t}
                LIMIT 1
                """,
                (domain_id, fp, *t_args),
            ).fetchone()
            if row:
                return True
            if not q_toks:
                return False
            rows = conn.execute(
                f"""
                SELECT query_text FROM semantic_blacklist
                WHERE domain_id = ? AND {where_t}
                ORDER BY created_at DESC
                LIMIT 80
                """,
                (domain_id, *t_args),
            ).fetchall()
            for r in rows:
                if jaccard_similarity(q_toks, semantic_tokens(str(r["query_text"]))) >= _BLACKLIST_JACCARD:
                    return True
            return False
        finally:
            conn.close()


def list_learned_examples(
    domain_id: str,
    *,
    tenant_id: str | None = None,
    limit: int = 40,
) -> list[dict[str, str]]:
    """Few-shot động dạng {question, sql} — mới nhất trước."""
    limit = max(1, min(int(limit), 100))
    where_t, t_args = _tenant_match_sql(tenant_id)
    with _LOCK:
        conn = _connect()
        try:
            rows = conn.execute(
                f"""
                SELECT query_text, sql_text FROM learned_examples
                WHERE domain_id = ? AND {where_t}
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (domain_id, *t_args, limit),
            ).fetchall()
        finally:
            conn.close()
    return [
        {"question": str(r["query_text"]), "sql": str(r["sql_text"])}
        for r in rows
    ]


def merge_few_shot_examples(
    static_examples: list[dict[str, Any]],
    domain_id: str,
    *,
    tenant_id: str | None = None,
) -> list[dict[str, Any]]:
    """Ghép few-shot config + learned (learned lên đầu, tránh trùng question)."""
    learned = list_learned_examples(domain_id, tenant_id=tenant_id)
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for ex in learned + list(static_examples or []):
        q = str(ex.get("question") or "").strip().lower()
        if not q or q in seen:
            continue
        seen.add(q)
        out.append(ex)
    return out


def apply_feedback(
    *,
    domain_id: str,
    query: str,
    vote: str,
    sql_query: str = "",
    tenant_id: str | None = None,
    artifact_id: str | None = None,
) -> dict[str, Any]:
    """API tiện ích cho endpoint feedback."""
    if vote == "up":
        learned = record_upvote(
            domain_id=domain_id,
            query=query,
            sql_query=sql_query,
            tenant_id=tenant_id,
            artifact_id=artifact_id,
        )
        return {
            "learned": learned,
            "blacklisted": 0,
            "examples_removed": 0,
        }
    if vote == "down":
        stats = record_downvote(
            domain_id=domain_id,
            query=query,
            tenant_id=tenant_id,
            artifact_id=artifact_id,
        )
        return {
            "learned": False,
            "blacklisted": stats["blacklisted"],
            "examples_removed": stats["examples_removed"],
        }
    return {"learned": False, "blacklisted": 0, "examples_removed": 0}
