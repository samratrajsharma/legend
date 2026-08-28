"""Tier-1 backend-robustness regressions (QA audit): index-worker resurrection, the
bounded/cleared codemap cache, and the /ask error contract. Offline (BM25, no LLM)."""
from __future__ import annotations

from pathlib import Path

SAMPLE_REPO = str((Path(__file__).resolve().parents[3] / "engine" / "sample_repo").resolve())


# ── T1-1: a DELETE mid-index must not be undone by the finishing worker ──────
def test_delete_during_index_does_not_resurrect(client):
    import app as backend
    rid = "resurrect0001"
    with backend._REPOS_LOCK:
        backend._REPOS[rid] = {"source": SAMPLE_REPO, "status": "indexing",
                               "error": None, "pct": 0, "message": "", "name": "x"}
    # user disconnects while the worker is still running
    with backend._REPOS_LOCK:
        backend._REPOS.pop(rid, None)
    # the worker finishes now and tries to write its terminal "ready" state
    backend._index_worker(rid, SAMPLE_REPO, backend._engine_config())
    with backend._REPOS_LOCK:
        assert rid not in backend._REPOS          # guarded: not resurrected


# ── T1-2: the codemap cache is bounded and evicts oldest first ──────────────
def test_codemap_cache_is_bounded():
    import app as backend
    c = backend._LruCache(maxsize=3)
    for i in range(5):
        c.put(f"k{i}", i)
    assert c.get("k0") is None and c.get("k1") is None   # evicted
    assert c.get("k2") == 2 and c.get("k4") == 4
    # re-access makes an entry recent, so it survives the next eviction
    c.get("k2")
    c.put("k5", 5)
    assert c.get("k2") == 2 and c.get("k3") is None


# ── T1-2/T1-3: disconnect frees this repo's codemap entries ─────────────────
def test_disconnect_clears_codemap_cache(client, ready_repo):
    import app as backend
    backend._CODEMAP_CACHE.put(f"{ready_repo}:data", {"stats": {}})
    backend._CODEMAP_CACHE.put(f"{ready_repo}:html:1", {"html": "x", "stats": {}})
    assert backend._CODEMAP_CACHE.get(f"{ready_repo}:data") is not None
    assert client.delete(f"/api/v1/repos/{ready_repo}").status_code == 204
    assert backend._CODEMAP_CACHE.get(f"{ready_repo}:data") is None
    assert backend._CODEMAP_CACHE.get(f"{ready_repo}:html:1") is None


# ── T1-4: an LLM failure is an error, not a 200 with the sentinel as answer ──
def test_ask_llm_failure_is_error_not_fake_answer(client, ready_repo, monkeypatch):
    from knowit.pipeline import RepoIndex
    # Simulate the LLM layer's graceful-degradation sentinel (used_llm False).
    monkeypatch.setattr(
        RepoIndex, "ask",
        lambda self, q, model=None, llm_kwargs=None: {
            "answer": "[LLM unavailable: RuntimeError: boom]", "used_llm": False, "retrieved": []},
    )
    # A model in the body gets us past the needs_llm gate without any network call.
    r = client.post(f"/api/v1/repos/{ready_repo}/ask",
                    json={"question": "hi", "provider": "openai", "model": "gpt-4o-mini"})
    assert r.status_code == 502
    assert "unavailable" in r.text.lower()
