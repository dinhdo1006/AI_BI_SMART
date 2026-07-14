"""API key auth — bật khi set API_KEY trong .env; để trống = chỉ local/dev."""

from __future__ import annotations

import hmac
import os
from typing import Iterable

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

# Health / docs luôn mở — load balancer & Swagger không cần key
_PUBLIC_PREFIXES: tuple[str, ...] = (
    "/health",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/api/v1/health",
)


def get_expected_api_key() -> str:
    return os.getenv("API_KEY", "").strip()


def auth_enabled() -> bool:
    return bool(get_expected_api_key())


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


class ApiKeyMiddleware(BaseHTTPMiddleware):
    """Khi API_KEY được set — mọi request (trừ public) phải gửi X-API-Key hoặc Bearer."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        expected = get_expected_api_key()
        if not expected:
            return await call_next(request)

        # CORS preflight không mang API key
        if request.method.upper() == "OPTIONS":
            return await call_next(request)

        if is_public_path(request.url.path):
            return await call_next(request)

        if not _keys_equal(extract_api_key(request), expected):
            return JSONResponse(
                status_code=401,
                content={"detail": "Thiếu hoặc sai API key (header X-API-Key)."},
            )
        return await call_next(request)
