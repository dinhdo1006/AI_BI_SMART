"""Factory Ollama LLM — dùng langchain-ollama (thay community deprecated)."""

from __future__ import annotations

import json
import logging
import os
import time
import urllib.error
import urllib.request

from langchain_ollama import OllamaLLM

_logger = logging.getLogger(__name__)

_FALLBACK_MODELS = (
    "qwen2.5:14b",
    "qwen2.5:14b-instruct-q4_K_M",
    "qwen2.5:7b",
    "qwen2.5:3b",
    "qwen2.5:latest",
    "qwen2.5",
)

# Cache TTL — không cache mãi danh sách rỗng khi Ollama tạm lỗi
_models_cache: frozenset[str] | None = None
_models_cache_at: float = 0.0
_MODELS_TTL_SEC = 60.0


def _ollama_base_url() -> str:
    """
    Chuẩn hóa OLLAMA_HOST cho client HTTP.
    Bind address 0.0.0.0 / :: không thể connect — đổi sang 127.0.0.1.
    """
    raw = (os.getenv("OLLAMA_HOST") or "http://127.0.0.1:11434").strip()
    if not raw:
        return "http://127.0.0.1:11434"
    # Thiếu scheme: "127.0.0.1:11434" hoặc "0.0.0.0:11434"
    if "://" not in raw:
        raw = f"http://{raw}"
    # 0.0.0.0 / [::] chỉ để bind server — client phải dùng loopback
    raw = raw.replace("://0.0.0.0", "://127.0.0.1")
    raw = raw.replace("://[::]", "://127.0.0.1")
    return raw.rstrip("/")


def _list_ollama_models() -> frozenset[str]:
    global _models_cache, _models_cache_at
    now = time.monotonic()
    if _models_cache is not None and (now - _models_cache_at) < _MODELS_TTL_SEC:
        return _models_cache

    host = _ollama_base_url()
    try:
        with urllib.request.urlopen(f"{host}/api/tags", timeout=3) as resp:
            payload = json.loads(resp.read().decode("utf-8", errors="replace"))
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        _logger.debug("Không liệt kê được model Ollama (%s): %s", host, exc)
        # Không cache thất bại lâu — lần sau thử lại
        return frozenset()

    names: set[str] = set()
    for item in payload.get("models") or []:
        name = str(item.get("name") or "").strip()
        if name:
            names.add(name)

    _models_cache = frozenset(names)
    _models_cache_at = now
    return _models_cache


def resolve_ollama_model(preferred: str) -> str:
    """
    Chọn model có sẵn trên Ollama.
    Nếu preferred thiếu → lần lượt fallback qwen2.5:14b / :7b / :3b / …
    """
    preferred = (preferred or "").strip() or "qwen2.5:14b"
    available = _list_ollama_models()
    if not available:
        return preferred
    if preferred in available:
        return preferred

    for candidate in (*_FALLBACK_MODELS,):
        if candidate in available:
            if candidate != preferred:
                _logger.warning(
                    "Model Ollama '%s' không có — dùng '%s'",
                    preferred,
                    candidate,
                )
            return candidate

    # Prefix match: preferred qwen2.5:7b, available qwen2.5:3b
    family = preferred.split(":", 1)[0]
    for name in sorted(available):
        if name == family or name.startswith(family + ":"):
            _logger.warning(
                "Model Ollama '%s' không có — dùng '%s'",
                preferred,
                name,
            )
            return name
    return preferred


def make_ollama_llm(
    *,
    model: str,
    temperature: float = 0.0,
    num_predict: int = 512,
    timeout: float = 150,
) -> OllamaLLM:
    """Khởi tạo OllamaLLM với timeout HTTP hợp lý."""
    resolved = resolve_ollama_model(model)
    return OllamaLLM(
        model=resolved,
        temperature=temperature,
        num_predict=num_predict,
        base_url=_ollama_base_url(),
        client_kwargs={"timeout": timeout},
    )
