"""Auth — global API key + multi-tenant API keys + rate limit."""

from __future__ import annotations

import hmac
import os
import time
from collections import defaultdict, deque
from typing import Any, Iterable

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from core.rbac import has_permission, normalize_role
from core.tenancy import (
    is_multi_tenant_enabled,
    resolve_api_key,
)

# Health / docs luôn mở — load balancer & Swagger không cần key
_PUBLIC_PREFIXES: tuple[str, ...] = (
    "/health",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/api/v1/health",
    "/api/v1/auth/login",
    "/api/v1/tenant/branding",
    "/api/v1/sso",        # SSO login / callback / metadata
    "/api/v1/embed/",     # Public embed dashboard
)

_RATE_BUCKETS: dict[str, deque[float]] = defaultdict(deque)


def get_expected_api_key() -> str:
    return os.getenv("API_KEY", "").strip()


def auth_enabled() -> bool:
    return bool(get_expected_api_key()) or is_multi_tenant_enabled()


def extract_api_key(request: Request) -> str:
    header_key = (request.headers.get("x-api-key") or "").strip()
    if header_key:
        return header_key
    auth = (request.headers.get("authorization") or "").strip()
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return ""


def _keys_equal(provided: str, expected: str) -> bool:
    if not provided or not expected:
        return False
    if len(provided) != len(expected):
        return False
    return hmac.compare_digest(provided, expected)


def is_public_path(path: str, extra_public: Iterable[str] = ()) -> bool:
    if path.rstrip("/") == "":
        return True
    for prefix in (*_PUBLIC_PREFIXES, *extra_public):
        if path == prefix or path.startswith(prefix.rstrip("/") + "/"):
            return True
        if path.rstrip("/") == prefix.rstrip("/"):
            return True
    return False


def _rate_limit_max() -> int:
    raw = os.getenv("API_RATE_LIMIT_PER_MINUTE", "120")
    try:
        return max(10, int(raw))
    except ValueError:
        return 120


def _check_rate_limit(bucket_key: str) -> bool:
    """True = ok; False = vượt hạn."""
    limit = _rate_limit_max()
    now = time.time()
    window = 60.0
    q = _RATE_BUCKETS[bucket_key]
    while q and now - q[0] > window:
        q.popleft()
    if len(q) >= limit:
        return False
    q.append(now)
    return True


def resolve_identity(raw_key: str) -> dict[str, Any] | None:
    """
    Ưu tiên: tenant API key → global API_KEY (platform admin).
    """
    if not raw_key:
        return None

    tenant_id_ctx = resolve_api_key(raw_key)
    if tenant_id_ctx:
        return tenant_id_ctx

    expected = get_expected_api_key()
    if expected and _keys_equal(raw_key, expected):
        return {
            "key_id": "global",
            "tenant_id": "platform",
            "tenant_name": "Platform",
            "user_id": None,
            "role": "admin",
            "name": "Global API key",
            "branding": {
                "product_name": os.getenv("BRAND_PRODUCT_NAME", "AI BI Smart"),
                "primary_color": os.getenv("BRAND_PRIMARY_COLOR", "#0f766e"),
                "logo_url": os.getenv("BRAND_LOGO_URL", ""),
            },
            "auth_mode": "global_key",
        }
    return None


def get_request_identity(request: Request) -> dict[str, Any]:
    identity = getattr(request.state, "identity", None)
    if isinstance(identity, dict):
        return identity
    return {
        "tenant_id": None,
        "role": "admin" if not auth_enabled() else "viewer",
        "auth_mode": "open",
    }


def require_permission(request: Request, permission: str) -> None:
    from fastapi import HTTPException

    identity = get_request_identity(request)
    role = normalize_role(str(identity.get("role") or "viewer"))
    if not auth_enabled():
        return
    if not has_permission(role, permission):
        raise HTTPException(
            status_code=403,
            detail=f"Không đủ quyền ({role}) cho thao tác «{permission}».",
        )


class ApiKeyMiddleware(BaseHTTPMiddleware):
    """
    Auth:
    - Dev open: không API_KEY và AUTH_MULTI_TENANT=false → cho qua
    - Global API_KEY và/hoặc tenant keys
    Gắn request.state.identity + rate limit theo key/IP.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        if request.method.upper() == "OPTIONS":
            return await call_next(request)

        path = request.url.path
        if is_public_path(path):
            request.state.identity = {
                "tenant_id": None,
                "role": "viewer",
                "auth_mode": "public",
            }
            return await call_next(request)

        raw = extract_api_key(request)
        enabled = auth_enabled()

        if not enabled:
            request.state.identity = {
                "tenant_id": None,
                "role": "admin",
                "auth_mode": "open",
            }
            return await call_next(request)

        identity = resolve_identity(raw) if raw else None
        if not identity:
            return JSONResponse(
                status_code=401,
                content={
                    "detail": "Thiếu hoặc sai API key (header X-API-Key / Bearer).",
                },
            )

        client = request.client.host if request.client else "unknown"
        bucket = f"{identity.get('key_id') or raw[:12]}:{client}"
        if not _check_rate_limit(bucket):
            return JSONResponse(
                status_code=429,
                content={"detail": "Vượt rate limit — thử lại sau 1 phút."},
            )

        request.state.identity = identity
        return await call_next(request)
