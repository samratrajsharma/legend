"""Contract + state-machine tests for the FastAPI backend (QA CRITICAL #1).

Covers health, the connect -> indexing -> ready -> 404/409 lifecycle, the main read
endpoints, the no-model Ask paths (plain + SSE), report export, and disconnect. All
offline (BM25, no LLM).
"""
from __future__ import annotations


# ── health / status ─────────────────────────────────────────────
def test_healthz(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_llm_status_shape(client):
    j = client.get("/api/v1/llm-status").json()
    assert {"configured", "model", "provider"} <= set(j)
    assert j["configured"] is False           # no model configured in tests


# ── _require_idx state machine ──────────────────────────────────
def test_unknown_repo_status_is_404(client):
    assert client.get("/api/v1/repos/deadbeef0000/status").status_code == 404


def test_unknown_repo_read_is_404(client):
    assert client.get("/api/v1/repos/deadbeef0000/overview").status_code == 404


def test_not_ready_repo_is_409(client):
    # Inject an 'indexing' slot to hit the not-ready branch deterministically.
    import app as backend
    rid = "pending000000"
    with backend._REPOS_LOCK:
        backend._REPOS[rid] = {"source": "x", "status": "indexing", "error": None,
                               "pct": 0, "message": "", "name": "x"}
    try:
        assert client.get(f"/api/v1/repos/{rid}/overview").status_code == 409
    finally:
        with backend._REPOS_LOCK:
            backend._REPOS.pop(rid, None)


# ── connect validation ──────────────────────────────────────────
def test_connect_empty_source_is_400(client):
    assert client.post("/api/v1/repos", json={"source": "   "}).status_code == 400


def test_connect_missing_dir_is_400(client):
    assert client.post("/api/v1/repos", json={"source": "/no/such/dir/xyzzy"}).status_code == 400


# ── full lifecycle over the bundled sample_repo ─────────────────
def test_overview_and_files(client, ready_repo):
    ov = client.get(f"/api/v1/repos/{ready_repo}/overview")
    assert ov.status_code == 200
    assert "stats" in ov.json()

    files = client.get(f"/api/v1/repos/{ready_repo}/files").json()
    assert any(f.endswith("model.py") for f in files["files"])


def test_api_db_shape(client, ready_repo):
    j = client.get(f"/api/v1/repos/{ready_repo}/api-db").json()
    assert "routes" in j and "models" in j


def test_repo_appears_in_list(client, ready_repo):
    assert any(x["repo_id"] == ready_repo for x in client.get("/api/v1/repos").json())


def test_ask_without_model_returns_needs_llm(client, ready_repo):
    a = client.post(f"/api/v1/repos/{ready_repo}/ask", json={"question": "what is this repo"}).json()
    assert a.get("needs_llm") is True
    assert a.get("answer") is None


def test_ask_stream_without_model_emits_needs_llm(client, ready_repo):
    r = client.post(f"/api/v1/repos/{ready_repo}/ask/stream", json={"question": "hello"})
    assert r.status_code == 200
    assert "needs_llm" in r.text               # SSE event, no LLM required


def test_report_markdown_export(client, ready_repo):
    r = client.get(f"/api/v1/repos/{ready_repo}/report", params={"fmt": "md"})
    assert r.status_code == 200
    assert len(r.text) > 0


def test_disconnect_then_404(client, ready_repo):
    assert client.delete(f"/api/v1/repos/{ready_repo}").status_code == 204
    assert client.get(f"/api/v1/repos/{ready_repo}/status").status_code == 404
