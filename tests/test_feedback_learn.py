"""Tests feedback learning (few-shot + semantic blacklist)."""

from __future__ import annotations

from pathlib import Path

import core.feedback_learn as fl
import core.query_cache as qc


def _patch_db(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(fl, "_DB_PATH", tmp_path / "feedback_learn.db")
    monkeypatch.setattr(qc, "_CACHE_DIR", tmp_path)
    monkeypatch.setattr(qc, "_DB_PATH", tmp_path / "query_cache.db")
    monkeypatch.setenv("QUERY_CACHE_ENABLED", "true")
    monkeypatch.setenv("QUERY_CACHE_SEMANTIC", "true")
    monkeypatch.setenv("QUERY_CACHE_SEMANTIC_THRESHOLD", "0.6")


def test_upvote_adds_learned_few_shot(tmp_path: Path, monkeypatch) -> None:
    _patch_db(tmp_path, monkeypatch)
    domain = "finance_vnfdata"
    ok = fl.record_upvote(
        domain_id=domain,
        query="P/E của VNM",
        sql_query="SELECT pe FROM stocks WHERE symbol='VNM'",
    )
    assert ok is True
    examples = fl.list_learned_examples(domain)
    assert len(examples) == 1
    assert "VNM" in examples[0]["question"]
    merged = fl.merge_few_shot_examples(
        [{"question": "Top vốn hóa", "sql": "SELECT 1"}],
        domain,
    )
    assert merged[0]["question"] == "P/E của VNM"
    assert any(ex["question"] == "Top vốn hóa" for ex in merged)


def test_downvote_blacklists_and_blocks_similar(tmp_path: Path, monkeypatch) -> None:
    _patch_db(tmp_path, monkeypatch)
    domain = "finance_vnfdata"
    fl.record_upvote(
        domain_id=domain,
        query="P/E của VNM hôm nay",
        sql_query="SELECT pe FROM stocks WHERE symbol='VNM'",
    )
    stats = fl.record_downvote(domain_id=domain, query="P/E của VNM hôm nay")
    assert stats["blacklisted"] == 1
    assert stats["examples_removed"] >= 1
    assert fl.is_query_blacklisted(domain, "P/E của VNM hôm nay") is True
    assert fl.is_query_blacklisted(domain, "Cho tôi xem P/E VNM") is True
    assert fl.is_query_blacklisted(domain, "Top cổ phiếu tăng giá") is False


def test_downvote_skips_cache_via_blacklist(tmp_path: Path, monkeypatch) -> None:
    _patch_db(tmp_path, monkeypatch)
    domain = "finance_vnfdata"
    qc.set_cached_response(
        domain,
        "P/E của VNM",
        {"status": "success", "insight": "bad", "data": []},
    )
    fl.record_downvote(domain_id=domain, query="P/E của VNM")
    assert fl.is_query_blacklisted(domain, "P/E VNM giúp tôi") is True
