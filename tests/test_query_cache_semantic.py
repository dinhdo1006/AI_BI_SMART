"""Tests semantic query cache."""

from __future__ import annotations

from pathlib import Path

import core.query_cache as qc


def test_semantic_tokens_drop_stopwords() -> None:
    a = qc.semantic_tokens("Cho tôi xem P/E của VNM hôm nay")
    b = qc.semantic_tokens("P/E VNM")
    assert "vnm" in a
    assert "pe" in a
    assert qc.jaccard_similarity(a, b) >= 0.5


def test_semantic_cache_hit_paraphrase(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(qc, "_CACHE_DIR", tmp_path)
    monkeypatch.setattr(qc, "_DB_PATH", tmp_path / "query_cache.db")
    monkeypatch.setenv("QUERY_CACHE_ENABLED", "true")
    monkeypatch.setenv("QUERY_CACHE_SEMANTIC", "true")
    monkeypatch.setenv("QUERY_CACHE_SEMANTIC_THRESHOLD", "0.6")

    domain = "finance_vnfdata"
    qc.set_cached_response(
        domain,
        "Cho tôi xem P/E của VNM",
        {"status": "success", "insight": "ok", "data": [{"pe": 15}]},
    )
    hit = qc.get_cached_response(domain, "P/E VNM giúp tôi với")
    assert hit is not None
    assert hit.get("from_cache") is True
    assert hit.get("cache_match") in ("exact", "semantic")
    assert hit.get("insight") == "ok"


def test_semantic_cache_miss_different_topic(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(qc, "_CACHE_DIR", tmp_path)
    monkeypatch.setattr(qc, "_DB_PATH", tmp_path / "query_cache.db")
    monkeypatch.setenv("QUERY_CACHE_ENABLED", "true")
    monkeypatch.setenv("QUERY_CACHE_SEMANTIC", "true")
    monkeypatch.setenv("QUERY_CACHE_SEMANTIC_THRESHOLD", "0.82")

    domain = "finance_vnfdata"
    qc.set_cached_response(
        domain,
        "Top cổ phiếu tăng giá hôm nay",
        {"status": "success", "insight": "gainers"},
    )
    miss = qc.get_cached_response(domain, "ROE của VNM quý gần nhất")
    assert miss is None


if __name__ == "__main__":
    import pytest

    raise SystemExit(pytest.main([__file__, "-q"]))
