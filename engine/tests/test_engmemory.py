"""Tests for knowit.engmemory — decision/error/memory JSON store + LLM helpers."""
from __future__ import annotations

import glob
import os

from knowit import engmemory
from knowit.config import Config


def _cfg(tmp_path):
    return Config(data_dir=str(tmp_path / "data"))


def test_add_load_delete_round_trip(tmp_path):
    cfg = _cfg(tmp_path)
    entry = engmemory.add(cfg, "repo", "decisions",
                          {"title": "Use BM25", "decision": "ship it"})
    assert entry["id"] and entry["date"]
    assert entry["title"] == "Use BM25"

    items = engmemory.load(cfg, "repo", "decisions")
    assert any(i["id"] == entry["id"] for i in items)

    engmemory.delete(cfg, "repo", "decisions", entry["id"])
    assert all(i["id"] != entry["id"]
               for i in engmemory.load(cfg, "repo", "decisions"))


def test_load_missing_is_empty_list(tmp_path):
    assert engmemory.load(_cfg(tmp_path), "repo", "memory") == []


def test_kinds_are_isolated(tmp_path):
    cfg = _cfg(tmp_path)
    engmemory.add(cfg, "repo", "errors", {"error": "boom"})
    assert engmemory.load(cfg, "repo", "decisions") == []
    assert len(engmemory.load(cfg, "repo", "errors")) == 1


def test_newest_entry_first(tmp_path):
    cfg = _cfg(tmp_path)
    engmemory.add(cfg, "r", "memory", {"note": "first"})
    engmemory.add(cfg, "r", "memory", {"note": "second"})
    items = engmemory.load(cfg, "r", "memory")
    assert items[0]["note"] == "second"


def test_persisted_to_json_file(tmp_path):
    cfg = _cfg(tmp_path)
    engmemory.add(cfg, "my repo", "memory", {"type": "learned", "note": "n"})
    hits = glob.glob(os.path.join(cfg.data_dir, "eng", "*", "memory.json"))
    assert hits, "memory.json was not written"


def test_repo_name_sanitized_into_dir(tmp_path):
    cfg = _cfg(tmp_path)
    engmemory.add(cfg, "weird/name:v2", "memory", {"note": "x"})
    # non-alnum chars are replaced so the path is filesystem-safe
    dirs = os.listdir(os.path.join(cfg.data_dir, "eng"))
    assert dirs and all("/" not in d and ":" not in d for d in dirs)


def test_llm_helpers_without_model_return_none():
    assert engmemory.draft_decision_llm("title", "ctx", model="") is None
    assert engmemory.diagnose_error_llm("traceback", None, model="") is None
