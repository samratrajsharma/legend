# Legend

Ingest a codebase, understand it, learn it, and track how it evolves.
See `Legend-Plan.md` (strategy), `Legend-Phased-Plan.docx` (build plan), and
`Legend-Technical-Implementation.docx` / `docs/` (the ~116-page technical reference).

Implemented: **Phases 0–8** (the full roadmap) — Foundations, Understand, Teach, Deepen Understanding, Track,
Engineering Intelligence, **Learning Media**, **Research Mode**, and **Portfolio Mode** — on a hybrid retrieval engine with
multi-provider LLMs and a disk cache.

## What it does today

`repo → ingest → parse → code graph → chunk → hybrid retrieval → understand / teach / track / analyse / present → eval`

- **Ingest** local path or git URL; commit-tagged artifacts (`{graph node, commit}`).
- **Parse** — Python via `ast`; JS/TS via regex (symbols, imports, calls, inheritance, complexity).
- **Code graph** — `files → symbols` with contains / method_of / calls / imports / inherits.
- **Hybrid retrieval** — BM25 + semantic (Chroma) fused with RRF, then graph expansion.
- **Understand** — per-file explanations, insights, language breakdown.
- **Diagrams** — a **mind map** (root + depth + branch controls, re-rootable, depth-colored),
  a graph explorer, and whole-repo presets; Graphviz default, draggable pyvis when installed.
- **API & DB maps** — routes; ORM models / `__tablename__`.
- **Teach** — learning path, flashcards, 3-level quizzes, interview mode, learning-gaps.
- **Track** — snapshot across commits → changelog, architecture delta, learning delta.
- **Engineering Intelligence** — tech-debt tracker (dead code, near-duplicates, import cycles,
  complexity hotspots, god-files, undocumented) + decision log, error KB, technical memory.
- **Learning Media** — auto **slide decks** (.pptx, three audiences), a NotebookLM-style
  **two-host audio overview** (script + optional TTS), and a **Markdown mind-map outline**.
- **Research Mode** — detects papers the repo references (arXiv ids / DOIs), looks up arXiv
  metadata, and (with an LLM) builds comparison matrices, repo-grounded implementation plans,
  and novelty notes.
- **Portfolio Mode** — generates shareable artifacts from everything Legend knows: a project
  report, a technical blog post, résumé bullets, a LinkedIn post, and a paper draft (.md).
- **Eval harness** — scores a question set, reports the **≥80% gate**.

### Graceful, dependency-light by design

Runs fully offline on BM25 + cited context + structural artifacts. **chromadb** (semantic),
**litellm** (answers/grading), **pyvis** (interactive diagrams), **python-pptx** (decks), and
TTS libs (audio) auto-activate when installed.

### Beyond the plan — learning & engineering add-ons

- **Persistent learning + spaced repetition** — explored files, flashcard reviews (Leitner
  scheduling), and quiz scores persist across sessions; a **Progress** view shows mastery,
  due cards, and quiz history, with **Anki (.tsv)** export. (Learn tab)
- **Test-reference coverage** — which functions tests mention, and untested-by-complexity. (Intel)
- **Secret scanning** — flags likely hardcoded keys/tokens. (Intel)
- **Impact analysis** — what changing a symbol affects (reverse call/import reachability). (Track)
- **Configuration surface** — config files, CLI args, settings. (Overview)
- **Portable HTML export** — a self-contained understanding page. (Portfolio)

## Testing

```bash
python -m unittest tests.test_legend       # Legend's 19-test suite; offline, no secrets
# (if you use pytest, `pytest tests/` runs this plus any pytest-style tests)
```

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows  (source .venv/bin/activate elsewhere)
pip install -r requirements.txt
cp .env.example .env              # optional: pick a provider + key for answers
```

## Run — one command starts everything

```bash
streamlit run app.py
```

Auto-builds (and disk-caches) the index on launch (bundled `sample_repo`, or `LEGEND_REPO`).
Tabs: Overview, Files, Diagrams, API & DB, Ask, Learn, Track, Intel, Media, Research, **Portfolio**, Eval.

## Headless eval

```bash
python scripts/run_eval.py sample_repo eval/questions.example.json   # 10/10 (BM25)
```

## Layout

```
app.py                       Streamlit harness (single entry point)
legend/
  config.py  models.py       settings + dataclasses
  providers.py               LLM provider registry + resolve + connection test
  ingest.py  parsing.py      load/walk/git ; ast (Python) + regex (JS/TS)
  graph.py                   pure-Python CodeGraph + structural queries
  chunking.py  index.py      provenance chunks ; BM25 + (persistent) Chroma
  retrieval.py  llm.py        hybrid RRF fusion + graph ; litellm answers/explanations
  insights.py  diagram.py     insights, API/DB maps ; Graphviz/pyvis mind map + explorer
  teach.py                   learning path, flashcards, quizzes, interview, gaps
  track.py                   snapshots, diff, changelog, architecture/learning deltas
  techdebt.py  engmemory.py   tech-debt analysis ; decision log / error KB / tech memory
  media.py                   slide decks (.pptx), audio overview script + TTS, mind-map outline
  research.py                paper detection, arXiv lookup, comparison/plan/novelty
  portfolio.py               project report / blog / résumé / LinkedIn / paper drafts
  pipeline.py  eval_harness.py   build_index()/ask() + cache + registry ; gate
docs/  eval/  scripts/  sample_repo/   tech doc, questions, runners, demo fixture
```

## Status

All nine phases (0–8) of the build plan are implemented. See
`docs/Vision-Coverage-Report.md` for a feature-by-feature audit against the original vision.

## Possible next steps (beyond the plan)

- Engine: cross-encoder re-rank, cross-repo querying, incremental re-index on file changes.
- Richer multi-language parsing via tree-sitter (calls for JS/TS).
