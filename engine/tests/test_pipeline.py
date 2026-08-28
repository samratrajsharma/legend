"""Tests for legend.pipeline — build_index, RepoIndex, cache, and registry."""
from __future__ import annotations

import os

from legend.config import Config
from legend.pipeline import (RepoIndex, _signature, build_index, recent_repos,
                             record_repo)


def test_stats(idx):
    s = idx.stats()
    assert s["repo"] == "sample_repo"
    assert s["files_parsed"] == 7
    assert s["python_files"] == 6
    assert s["parse_errors"] == 0
    assert s["symbols"] == 15
    assert s["chunks"] == 22
    assert s["retriever"] == "bm25"          # BM25-only config => dense is None
    assert idx.dense is None


def test_chunks_by_node_and_id_maps(idx):
    # every chunk is indexed by id and grouped by node
    assert len(idx.chunks_by_id) == len(idx.chunks)
    det_chunks = idx.chunks_by_node["model.py::Detector"]
    assert det_chunks and all(c.node_id == "model.py::Detector" for c in det_chunks)


def test_search_returns_ranked_relevant_results(idx):
    res = idx.search("how does the inference flow work end to end")
    assert res, "search returned no results"
    files = [r.chunk.file for r in res]
    assert "infer.py" in files
    # scores are sorted descending
    scores = [r.score for r in res]
    assert scores == sorted(scores, reverse=True)


def test_ask_without_llm_returns_context_only(idx):
    out = idx.ask("where is the model initialized")
    assert out["used_llm"] is False
    assert out["answer"] is None            # no model configured
    assert out["retrieved"]
    assert isinstance(out["context"], str) and out["context"]
    # context blocks carry file:line provenance headers
    assert "::" in out["context"]


def test_build_index_is_deterministic(sample_repo_path, bm25_config):
    a = build_index(sample_repo_path, config=bm25_config, register=False)
    b = build_index(sample_repo_path, config=bm25_config, register=False)
    assert a.stats() == b.stats()
    assert {c.id for c in a.chunks} == {c.id for c in b.chunks}


def test_cache_round_trip(sample_repo_path, tmp_path):
    cfg = Config(embed_backend="bm25", data_dir=str(tmp_path / "cache_dir"),
                 use_cache=True, llm_model="")
    # first build writes the pickle cache
    build_index(sample_repo_path, config=cfg, use_cache=True, register=False)
    cache_dir = os.path.join(cfg.data_dir, "cache")
    files = os.listdir(cache_dir)
    assert any(f.endswith(".pkl") for f in files)
    # second build loads it and yields identical structure
    again = build_index(sample_repo_path, config=cfg, use_cache=True, register=False)
    assert again.stats()["symbols"] == 15


def test_registry_record_and_recent(tmp_path):
    cfg = Config(data_dir=str(tmp_path / "reg"))

    class _Meta:
        name = "demo"
        commit = "0123456789abcdef"

    record_repo(cfg.data_dir, "some/source", _Meta())
    rec = recent_repos(cfg.data_dir)
    assert rec and rec[0]["source"] == "some/source"
    assert rec[0]["name"] == "demo"
    assert rec[0]["commit"] == "0123456789ab"   # truncated to 12

    # re-recording the same source de-dupes and moves it to the front
    record_repo(cfg.data_dir, "other", _Meta())
    record_repo(cfg.data_dir, "some/source", _Meta())
    rec2 = recent_repos(cfg.data_dir)
    sources = [e["source"] for e in rec2]
    assert sources[0] == "some/source"
    assert sources.count("some/source") == 1


def test_recent_repos_missing_file_is_empty(tmp_path):
    assert recent_repos(str(tmp_path / "nonexistent")) == []


def test_signature_stable_for_same_inputs(idx):
    sig1 = _signature(idx.meta, [(p.file, os.path.join(idx.meta.path, p.file))
                                 for p in idx.parsed_files])
    sig2 = _signature(idx.meta, [(p.file, os.path.join(idx.meta.path, p.file))
                                 for p in idx.parsed_files])
    assert sig1 == sig2 and len(sig1) == 16


def test_repoindex_is_constructible_directly(idx):
    # sanity: the public dataclass-ish wrapper exposes the documented attributes
    assert isinstance(idx, RepoIndex)
    for attr in ("meta", "parsed_files", "graph", "chunks", "lexical", "config"):
        assert hasattr(idx, attr)
