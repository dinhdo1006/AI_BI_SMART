"""Factory Ollama LLM — dùng langchain-ollama (thay community deprecated)."""

from __future__ import annotations

from langchain_ollama import OllamaLLM


def make_ollama_llm(
    *,
    model: str,
    temperature: float = 0.0,
    num_predict: int = 512,
    timeout: float = 150,
) -> OllamaLLM:
    """Khởi tạo OllamaLLM với timeout HTTP hợp lý."""
    return OllamaLLM(
        model=model,
        temperature=temperature,
        num_predict=num_predict,
        client_kwargs={"timeout": timeout},
    )
