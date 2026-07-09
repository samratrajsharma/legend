"""End-to-end UI smoke test driving the real Streamlit app via AppTest.

Streamlit renders the body of *every* tab on each run, so a single default run
exercises Overview/Files/Diagrams/API&DB/Learn/Track/Intel/Media against
sample_repo. Heavy/LLM actions are button-gated (off by default), so this stays
fast and offline. ChromaRetriever is disabled to force BM25-only (auto-fallback),
keeping the run deterministic without embeddings.
"""
from __future__ import annotations

import pytest


def _no_chroma(*args, **kwargs):
    raise RuntimeError("chroma disabled for the UI smoke test")


def test_app_renders_every_tab_without_error(project_root, monkeypatch):
    try:
        from streamlit.testing.v1 import AppTest
    except Exception:                       # pragma: no cover - very old streamlit
        pytest.skip("streamlit AppTest API not available")

    # Force BM25-only: build_index('auto') swallows the Chroma failure.
    import knowit.pipeline as pipeline
    monkeypatch.setattr(pipeline, "ChromaRetriever", _no_chroma)

    at = AppTest.from_file(str(project_root / "app.py"), default_timeout=120)
    at.run()

    # No uncaught exception and no st.exception element anywhere in the app.
    assert not at.exception, f"app raised during render: {list(at.exception)}"
    assert at.title[0].value == "KnowIT"
    # Overview renders a row of metrics -> confirms the tabs actually executed.
    assert len(at.metric) >= 4
