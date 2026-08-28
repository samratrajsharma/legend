"""Fixtures for the backend API tests.

Runs the FastAPI app in-process via TestClient against an isolated temp data dir,
forcing the BM25 backend so the suite is offline, fast and deterministic (no
chromadb embedding, no network, no LLM). Nothing touches the real ./.cache.
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]                 # app/backend
ENGINE = (BACKEND / ".." / ".." / "engine").resolve()         # engine/
if str(ENGINE) not in sys.path:
    sys.path.insert(0, str(ENGINE))                           # so `import knowit...` resolves

# No model configured => Ask returns needs_llm without any network calls.
for k in ("KNOWIT_LLM_PROVIDER", "KNOWIT_LLM_MODEL", "KNOWIT_LLM_BASE_URL"):
    os.environ.pop(k, None)

SAMPLE_REPO = str((ENGINE / "sample_repo").resolve())


def _load_backend_app():
    """Load app/backend/app.py explicitly by path under the name `app`.

    The engine also ships an `engine/app.py` (a Streamlit app); when the whole repo's
    tests run together a bare `import app` can resolve to that one (module-name collision),
    which additionally fails if streamlit is mismatched in the env. Loading by file path and
    registering it in sys.modules makes `import app` in the tests return THIS module."""
    import importlib.util
    if "app" in sys.modules and getattr(sys.modules["app"], "__file__", "") == str(BACKEND / "app.py"):
        return sys.modules["app"]
    spec = importlib.util.spec_from_file_location("app", str(BACKEND / "app.py"))
    module = importlib.util.module_from_spec(spec)
    sys.modules["app"] = module                               # test_api.py's `import app` gets this
    spec.loader.exec_module(module)                           # app.py adds ENGINE_ROOT/CODEMAP_ROOT itself
    return module


@pytest.fixture(scope="session")
def client(tmp_path_factory):
    data_dir = tmp_path_factory.mktemp("kyc_backend_data")
    os.environ["KNOWIT_DATA_DIR"] = str(data_dir)
    from fastapi.testclient import TestClient
    backend = _load_backend_app()
    from knowit.config import Config
    # Force BM25 so indexing never reaches for chromadb during tests.
    backend._engine_config = lambda: Config(
        embed_backend="bm25", data_dir=str(data_dir),
        use_cache=False, llm_model="", llm_provider="",
    )
    # TrustedHostMiddleware only accepts localhost Host headers; TestClient otherwise sends
    # `Host: testserver`, which the middleware rejects with 400 before any route runs. Pin
    # the base_url to an allowed host so requests carry `Host: localhost:8100`.
    with TestClient(backend.app, base_url="http://localhost:8100") as c:
        yield c


@pytest.fixture
def ready_repo(client):
    """Connect the bundled sample_repo and poll until indexing reports ready."""
    r = client.post("/api/v1/repos", json={"source": SAMPLE_REPO})
    assert r.status_code == 200, r.text
    rid = r.json()["repo_id"]
    for _ in range(160):                         # up to ~40s
        s = client.get(f"/api/v1/repos/{rid}/status").json()
        if s["status"] == "ready":
            return rid
        if s["status"] == "error":
            pytest.fail(f"indexing failed: {s.get('error')}")
        time.sleep(0.25)
    pytest.fail("repo did not become ready in time")
