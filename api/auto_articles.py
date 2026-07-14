"""API Auto Articles — danh sách bài tự động + chạy job thủ công."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from core.article_job import DOMAIN_ID, run_article_job
from core.article_scheduler import get_scheduler_status, run_scheduled_checks
from core.article_store import get_article, list_articles
from core.article_templates import get_template, list_templates

router = APIRouter(prefix="/api/v1/auto_articles", tags=["auto_articles"])


class AutoArticleRunRequest(BaseModel):
    template_id: str = Field(..., min_length=1, description="ID template VNFDATA")
    data_date: str = Field(
        ...,
        min_length=1,
        description="Kỳ dữ liệu (vd: 2026-07-14 hoặc 2025-Q2)",
    )
    domain_id: str = Field(default=DOMAIN_ID)
    force: bool = Field(default=False, description="Ghi đè nếu đã có bài cùng key")
    question: str = Field(default="", description="Override câu hỏi (optional)")


@router.get("")
def get_auto_articles(
    domain_id: str | None = None,
    limit: int = 30,
) -> dict[str, Any]:
    return {"articles": list_articles(domain_id=domain_id, limit=limit)}


@router.get("/scheduler")
def get_auto_article_scheduler() -> dict[str, Any]:
    return get_scheduler_status()


@router.get("/templates")
def get_auto_article_templates() -> dict[str, Any]:
    items = [
        {
            "id": t.get("id"),
            "name": t.get("name"),
            "category": t.get("category"),
            "cycle": t.get("cycle"),
            "word_count": t.get("word_count"),
        }
        for t in list_templates()
    ]
    return {"templates": items}


@router.get("/{article_id}")
def get_auto_article(article_id: str) -> dict[str, Any]:
    item = get_article(article_id)
    if not item:
        raise HTTPException(status_code=404, detail="Bài không tồn tại")
    return item


@router.post("/run")
def post_run_auto_article(body: AutoArticleRunRequest) -> dict[str, Any]:
    """Chạy 1 job thủ công theo template + data_date."""
    if not get_template(body.template_id):
        raise HTTPException(
            status_code=400,
            detail=f"Template '{body.template_id}' không tồn tại",
        )
    result = run_article_job(
        template_id=body.template_id,
        domain_id=body.domain_id or DOMAIN_ID,
        data_date=body.data_date,
        trigger="manual",
        force=body.force,
        question=body.question or None,
    )
    if result.get("status") == "error":
        raise HTTPException(
            status_code=502,
            detail=str(result.get("message") or "Lỗi chạy job"),
        )
    return result


@router.post("/run_checks")
def post_run_scheduled_checks() -> dict[str, Any]:
    """Chạy một tick schedule/poll ngay (không chờ interval)."""
    try:
        return run_scheduled_checks()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=502,
            detail=f"Lỗi scheduled checks: {exc}",
        ) from exc
