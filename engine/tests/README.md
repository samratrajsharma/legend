# KnowIT test suite

A `pytest` suite covering the full `knowit/` library, the headless eval harness,
and the Streamlit UI. **177 tests, fully offline and deterministic** — no network,
no LLM, no embeddings required.

## Run

```bash
pip install -r requirements.txt        # pytest + pytest-asyncio are included
python -m pytest                       # from the repo root
python -m pytest tests/test_graph.py   # a single module
python -m pytest -k retrieval          # by keyword
```

Config lives in `pytest.ini` (collection is scoped to `tests/`).

## Design

- **One shared fixture, BM25-only.** `conftest.py` builds a single session-scoped
  `RepoIndex` over the bundled `sample_repo` with `embed_backend="bm25"`,
  `use_cache=False`, and no LLM. This keeps the suite fast (~3.5s) and removes the
  three sources of nondeterminism in the system: chromadb embeddings, the LLM
  layer, and the disk cache.
- **Grounded invariants.** `sample_repo` is small and fixed, so assertions use
  exact counts derived from its structure: 7 graph file-nodes + 15 symbols = 22
  nodes; contains=15 / imports=7 / method_of=6 / calls=14 = 42 edges; 22 chunks.
- **Synthetic fixtures for what `sample_repo` doesn't cover.** `build_repo` writes
  an ad-hoc mini-repo (HTTP routes, ORM models, import cycles, near-duplicate
  functions); `git_repo` creates a real two-commit git repo for the Track feature
  (skips if `git` is absent).
- **Optional dependencies are tested on their degradation path.** pyvis, python-pptx,
  and the TTS backends are not installed here, so those tests assert the documented
  graceful behaviour (return `None` / raise `ImportError` / report "no backend").
- **UI smoke test.** `test_app_ui.py` drives `app.py` through Streamlit's `AppTest`.
  Streamlit executes every `with tabs[i]:` block on each run, so one default render
  exercises Overview, Files, Diagrams, API&DB, Learn, Track, Intel, and Media
  end-to-end. ChromaRetriever is monkeypatched to raise so the build falls back to
  BM25 (`embed_backend="auto"` swallows the failure) — keeping it offline.

## Coverage map

| Test file | Module(s) under test |
|---|---|
| `test_parsing.py` | `knowit/parsing.py` (Python ast + JS/TS regex) |
| `test_graph.py` | `knowit/graph.py` |
| `test_chunking.py` | `knowit/chunking.py` |
| `test_index.py` | `knowit/index.py` (tokenizer, stemmer, BM25) |
| `test_retrieval.py` | `knowit/retrieval.py` (RRF, hybrid, context) |
| `test_pipeline.py` | `knowit/pipeline.py` (build_index, cache, registry) |
| `test_insights.py` | `knowit/insights.py` |
| `test_teach.py` | `knowit/teach.py` |
| `test_techdebt.py` | `knowit/techdebt.py` |
| `test_track.py` | `knowit/track.py` (git snapshots + diff) |
| `test_diagram.py` | `knowit/diagram.py` |
| `test_media.py` | `knowit/media.py` |
| `test_ingest.py` | `knowit/ingest.py` |
| `test_engmemory.py` | `knowit/engmemory.py` |
| `test_providers.py` | `knowit/providers.py` |
| `test_llm.py` | `knowit/llm.py` (no-model paths) |
| `test_eval_harness.py` | `knowit/eval_harness.py` |
| `test_config_models.py` | `knowit/config.py`, `knowit/models.py` |
| `test_smoke.py` | every module imports; `app.py` + scripts compile |
| `test_app_ui.py` | `app.py` end-to-end via Streamlit AppTest |
