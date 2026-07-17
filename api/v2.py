"""
API v2 router — pagination, versioning rõ ràng.

Mọi endpoint /api/v2/... đều:
- Trả envelope chuẩn: {ok, data, meta}
- Hỗ trợ pagination: ?page=1&page_size=20
- Gắn X-API-Version: 2 vào response header
- Backward-compatible: v1 vẫn hoạt động song song
"""

from __future__ import annotations

import math
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from core.alert_store import list_events, list_rules
from core.auth import get_request_identity, require_permission
from core.config_loader import list_available_domains, load_domain_config
from core.dashboard_store import get_dashboard
from core.tenancy import is_multi_tenant_enabled, list_tenants, list_users

router = APIRouter(prefix="/api/v2", tags=["v2"])

# ---------------------------------------------------------------------------
# Envelope helpers
# ---------------------------------------------------------------------------

def _page(
    items: list[Any],
    page: int,
    page_size: int,
) -> dict[str, Any]:
    """Cắt danh sách theo trang, trả envelope chuẩn."""
    total = len(items)
    page = max(1, page)
    page_size = max(1, min(page_size, 200))
    total_pages = max(1, math.ceil(total / page_size))
    start = (page - 1) * page_size
    end = start + page_size
    return {
        "ok": True,
        "data": items[start:end],
        "meta": {
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": total_pages,
            "has_next": page < total_pages,
            "has_prev": page > 1,
        },
    }


def _ok(data: Any) -> dict[str, Any]:
    return {"ok": True, "data": data, "meta": {}}


class V2Response(JSONResponse):
    def __init__(self, content: Any, **kwargs: Any) -> None:
        super().__init__(content=content, **kwargs)
        self.headers["X-API-Version"] = "2"


# ---------------------------------------------------------------------------
# Domains
# ---------------------------------------------------------------------------

@router.get("/domains")
def v2_list_domains(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> V2Response:
    """Danh sách domain có sẵn."""
    domains = [
        {"domain_id": d}
        for d in list_available_domains()
    ]
    return V2Response(_page(domains, page, page_size))


# ---------------------------------------------------------------------------
# Dashboards
# ---------------------------------------------------------------------------

@router.get("/dashboards/{dash_id}")
def v2_get_dashboard(dash_id: str, request: Request) -> V2Response:
    identity = get_request_identity(request)
    tid = identity.get("tenant_id")
    data = get_dashboard(dash_id, tenant_id=str(tid) if tid else None)
    if not data:
        raise HTTPException(status_code=404, detail="Dashboard không tồn tại")
    return V2Response(_ok(data))


# ---------------------------------------------------------------------------
# Alerts
# ---------------------------------------------------------------------------

@router.get("/alerts/rules")
def v2_list_rules(
    request: Request,
    domain_id: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> V2Response:
    identity = get_request_identity(request)
    tid = identity.get("tenant_id") or None
    if tid in ("platform", ""):
        tid = None
    rules = list_rules(domain_id=domain_id, tenant_id=tid)
    return V2Response(_page(rules, page, page_size))


@router.get("/alerts/events")
def v2_list_events(
    request: Request,
    domain_id: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    limit: int = Query(100, ge=1, le=500),
) -> V2Response:
    events = list_events(domain_id=domain_id, limit=limit)
    return V2Response(_page(events, page, page_size))


# ---------------------------------------------------------------------------
# Tenants / Users (admin only)
# ---------------------------------------------------------------------------

@router.get("/admin/tenants")
def v2_list_tenants(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> V2Response:
    require_permission(request, "admin.tenants")
    tenants = list_tenants()
    return V2Response(_page(tenants, page, page_size))


@router.get("/admin/users")
def v2_list_users(
    request: Request,
    tenant_id: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> V2Response:
    require_permission(request, "admin.users")
    identity = get_request_identity(request)
    tid = tenant_id or identity.get("tenant_id") or None
    if tid in ("platform", ""):
        raise HTTPException(status_code=400, detail="Cần tenant_id")
    users = list_users(str(tid))
    return V2Response(_page(users, page, page_size))


# ---------------------------------------------------------------------------
# Version info
# ---------------------------------------------------------------------------

@router.get("/version")
def v2_version() -> V2Response:
    return V2Response(_ok({
        "api_version": "2",
        "features": [
            "pagination",
            "tenant_isolation",
            "sso",
            "cross_domain_join",
            "volume_profile",
            "pdf_upload",
            "confidence_labels",
        ],
    }))
