"""Coverage for the backend route families the original suite didn't touch (QA audit T2):
files, readme, graph, functions/explain, codemap/status, intel/*, track/*, workspace, llm/*.
All offline over the bundled sample_repo (BM25, no LLM). Assertions favor shape/status over
stateful values so tests don't couple through the shared session data dir."""
from __future__ import annotations


# ── Files / README / graph ──────────────────────────────────────
def test_readme(client, ready_repo):
    j = client.get(f"/api/v1/repos/{ready_repo}/readme").json()
    assert j["found"] is True and j["text"]           # sample_repo ships a README


def test_file_summary_and_content(client, ready_repo):
    s = client.get(f"/api/v1/repos/{ready_repo}/files/summary", params={"file": "model.py"})
    assert s.status_code == 200 and s.json()["language"] == "python"
    c = client.get(f"/api/v1/repos/{ready_repo}/files/content", params={"file": "model.py"})
    assert c.status_code == 200 and "class Detector" in c.json()["text"]


def test_file_content_unknown_file_404(client, ready_repo):
    r = client.get(f"/api/v1/repos/{ready_repo}/files/content", params={"file": "nope_xyz.py"})
    assert r.status_code == 404


def test_graph_nodes(client, ready_repo):
    nodes = client.get(f"/api/v1/repos/{ready_repo}/graph/nodes").json()["nodes"]
    assert "model.py::Detector" in nodes


def test_functions_explain_without_model(client, ready_repo):
    r = client.get(f"/api/v1/repos/{ready_repo}/functions/explain",
                   params={"file": "model.py", "symbol": "Detector.predict"})
    assert r.status_code == 200
    j = r.json()
    assert j["name"] == "predict" and j["code"]        # code + relations returned regardless
    assert j["used_llm"] is False and j["explanation"] is None  # no model configured


def test_functions_explain_unknown_symbol_404(client, ready_repo):
    r = client.get(f"/api/v1/repos/{ready_repo}/functions/explain",
                   params={"file": "model.py", "symbol": "does_not_exist"})
    assert r.status_code == 404


# ── codemap status (doesn't need codemap to be generatable) ─────
def test_codemap_status(client):
    j = client.get("/api/v1/codemap/status").json()
    assert {"available", "load_error"} <= set(j)


# ── Intel family ────────────────────────────────────────────────
def test_intel_techdebt(client, ready_repo):
    j = client.get(f"/api/v1/repos/{ready_repo}/intel/techdebt").json()
    assert {"dead_code", "near_duplicates", "import_cycles", "complexity_hotspots",
            "god_files", "undocumented"} <= set(j)


def test_intel_coverage(client, ready_repo):
    r = client.get(f"/api/v1/repos/{ready_repo}/intel/coverage")
    assert r.status_code == 200 and isinstance(r.json(), dict)


def test_intel_impact(client, ready_repo):
    r = client.get(f"/api/v1/repos/{ready_repo}/intel/impact",
                   params={"symbol": "model.py::Detector.predict"})
    assert r.status_code == 200 and isinstance(r.json(), dict)


def test_intel_memory_crud(client, ready_repo):
    base = f"/api/v1/repos/{ready_repo}/intel/memory"
    add = client.post(f"{base}/add", json={"kind": "decisions", "title": "T", "body": "B"})
    assert add.status_code == 200 and add.json()["ok"] is True
    eid = add.json()["entry"].get("id")
    listed = client.get(base).json()["decisions"]
    assert any(e.get("id") == eid for e in listed)
    assert client.delete(f"{base}/decisions/{eid}").status_code == 200
    assert all(e.get("id") != eid for e in client.get(base).json()["decisions"])


def test_intel_memory_bad_kind_400(client, ready_repo):
    r = client.post(f"/api/v1/repos/{ready_repo}/intel/memory/add",
                    json={"kind": "bogus", "title": "x", "body": ""})
    assert r.status_code == 400


# ── Track family (sample_repo is not a git repo, but these degrade gracefully) ──
def test_track_timeline_shape(client, ready_repo):
    j = client.get(f"/api/v1/repos/{ready_repo}/track/timeline").json()
    assert isinstance(j["events"], list) and isinstance(j["count"], int)


def test_track_dirty_shape(client, ready_repo):
    j = client.get(f"/api/v1/repos/{ready_repo}/track/dirty").json()
    assert {"trackable", "dirty", "has_baseline"} <= set(j)


def test_track_capture(client, ready_repo):
    r = client.post(f"/api/v1/repos/{ready_repo}/track/capture")
    assert r.status_code == 200
    assert ("baseline" in r.json()) or ("changed" in r.json())


def test_workspace(client):
    j = client.get("/api/v1/workspace").json()
    assert isinstance(j["folders"], list)


# ── LLM registry / graceful failure ─────────────────────────────
def test_llm_providers(client):
    j = client.get("/api/v1/llm/providers").json()
    assert isinstance(j["providers"], list) and len(j["providers"]) > 0


def test_ollama_models_unreachable_is_graceful(client):
    # Points at a closed port: must return ok=False, not raise/hang (also the SSRF endpoint).
    j = client.get("/api/v1/llm/ollama-models", params={"base_url": "http://127.0.0.1:1"}).json()
    assert j["ok"] is False
