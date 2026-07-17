"""Enterprise API — login, me, tenants, users, keys, branding."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from core.auth import (
    auth_enabled,
    get_request_identity,
    require_permission,
)
from core.rbac import ROLES, normalize_role
from core.tenancy import (
    authenticate_user,
    create_api_key,
    create_tenant,
    create_user,
    ensure_default_tenant,
    get_tenant,
    is_multi_tenant_enabled,
    list_api_keys,
    list_tenants,
    list_users,
    update_tenant_branding,
)

router = APIRouter(prefix="/api/v1", tags=["enterprise"])


class LoginRequest(BaseModel):
    email: str = Field(..., min_length=3)
    password: str = Field(..., min_length=1)


class CreateTenantRequest(BaseModel):
    name: str = Field(..., min_length=1)
    slug: str | None = None


class CreateUserRequest(BaseModel):
    tenant_id: str
    email: str
    name: str = ""
    role: str = "analyst"
    password: str = Field(..., min_length=4)


class CreateKeyRequest(BaseModel):
    tenant_id: str
    name: str = "API key"
    role: str = "analyst"
    user_id: str | None = None


class BrandingUpdateRequest(BaseModel):
    product_name: str | None = None
    primary_color: str | None = None
    logo_url: str | None = None


def _identity(request: Request) -> dict[str, Any]:
    return get_request_identity(request)


@router.post("/auth/login")
def login(body: LoginRequest) -> dict[str, Any]:
    """Đăng nhập email/password → cấp API key session (Bearer)."""
    if is_multi_tenant_enabled():
        ensure_default_tenant()
    user = authenticate_user(body.email, body.password)
    if not user:
        raise HTTPException(status_code=401, detail="Email hoặc mật khẩu không đúng")
    key = create_api_key(
        tenant_id=str(user["tenant_id"]),
        name=f"login:{user['email']}",
        role=str(user["role"]),
        user_id=str(user["id"]),
    )
    tenant = get_tenant(str(user["tenant_id"])) or {}
    return {
        "ok": True,
        "api_key": key["api_key"],
        "role": user["role"],
        "user": user,
        "tenant": {
            "id": tenant.get("id"),
            "name": tenant.get("name"),
            "branding": tenant.get("branding") or {},
        },
    }


@router.get("/auth/me")
def auth_me(request: Request) -> dict[str, Any]:
    identity = _identity(request)
    return {
        "auth_enabled": auth_enabled(),
        "multi_tenant": is_multi_tenant_enabled(),
        "identity": identity,
        "roles": list(ROLES),
    }


@router.get("/tenant/branding")
def tenant_branding(request: Request, tenant_id: str | None = None) -> dict[str, Any]:
    """White-label — public-ish: có tenant_id hoặc lấy từ identity."""
    identity = _identity(request)
    tid = tenant_id or identity.get("tenant_id")
    if tid and tid != "platform":
        tenant = get_tenant(str(tid))
        if tenant:
            return {
                "tenant_id": tenant["id"],
                "tenant_name": tenant["name"],
                "branding": tenant.get("branding") or {},
            }
    # Fallback env / default
    import os

    return {
        "tenant_id": tid,
        "tenant_name": "AI BI Smart",
        "branding": {
            "product_name": os.getenv("BRAND_PRODUCT_NAME", "AI BI Smart"),
            "primary_color": os.getenv("BRAND_PRIMARY_COLOR", "#0f766e"),
            "logo_url": os.getenv("BRAND_LOGO_URL", ""),
        },
    }


@router.put("/tenant/branding")
def update_branding(body: BrandingUpdateRequest, request: Request) -> dict[str, Any]:
    require_permission(request, "admin.branding")
    identity = _identity(request)
    tid = identity.get("tenant_id")
    if not tid or tid == "platform":
        raise HTTPException(status_code=400, detail="Cần API key theo tenant để đổi branding")
    tenant = get_tenant(str(tid))
    if not tenant:
        raise HTTPException(status_code=404, detail="Không tìm thấy tenant")
    branding = dict(tenant.get("branding") or {})
    if body.product_name is not None:
        branding["product_name"] = body.product_name
    if body.primary_color is not None:
        branding["primary_color"] = body.primary_color
    if body.logo_url is not None:
        branding["logo_url"] = body.logo_url
    updated = update_tenant_branding(str(tid), branding)
    return {"ok": True, "tenant": updated}


@router.get("/admin/tenants")
def admin_list_tenants(request: Request) -> dict[str, Any]:
    require_permission(request, "admin.tenants")
    if is_multi_tenant_enabled():
        ensure_default_tenant()
    return {"tenants": list_tenants()}


@router.post("/admin/tenants")
def admin_create_tenant(body: CreateTenantRequest, request: Request) -> dict[str, Any]:
    require_permission(request, "admin.tenants")
    tenant = create_tenant(name=body.name, slug=body.slug)
    return {"ok": True, "tenant": tenant}


@router.get("/admin/users")
def admin_list_users(request: Request, tenant_id: str | None = None) -> dict[str, Any]:
    require_permission(request, "admin.users")
    identity = _identity(request)
    tid = tenant_id or identity.get("tenant_id")
    if not tid or tid == "platform":
        raise HTTPException(status_code=400, detail="Cần tenant_id")
    return {"users": list_users(str(tid))}


@router.post("/admin/users")
def admin_create_user(body: CreateUserRequest, request: Request) -> dict[str, Any]:
    require_permission(request, "admin.users")
    if normalize_role(body.role) not in ROLES:
        raise HTTPException(status_code=400, detail="Role không hợp lệ")
    user = create_user(
        tenant_id=body.tenant_id,
        email=body.email,
        name=body.name,
        role=body.role,
        password=body.password,
    )
    return {"ok": True, "user": user}


@router.get("/admin/api-keys")
def admin_list_keys(request: Request, tenant_id: str | None = None) -> dict[str, Any]:
    require_permission(request, "admin.keys")
    identity = _identity(request)
    tid = tenant_id or identity.get("tenant_id")
    if not tid or tid == "platform":
        raise HTTPException(status_code=400, detail="Cần tenant_id")
    return {"api_keys": list_api_keys(str(tid))}


@router.post("/admin/api-keys")
def admin_create_key(body: CreateKeyRequest, request: Request) -> dict[str, Any]:
    require_permission(request, "admin.keys")
    key = create_api_key(
        tenant_id=body.tenant_id,
        name=body.name,
        role=body.role,
        user_id=body.user_id,
    )
    return {"ok": True, "api_key": key}
