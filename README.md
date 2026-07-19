<div align="center">

# Know Your Code

**Local-first codebase intelligence.** Point it at any repository or folder and it maps the architecture, explains files, answers questions with your own LLM, and tracks how the code changes over time — all on your machine.

![Python](https://img.shields.io/badge/python-3.10+-3776AB)
![React](https://img.shields.io/badge/react-19-149ECA)
![FastAPI](https://img.shields.io/badge/backend-FastAPI-009688)
![local-first](https://img.shields.io/badge/local--first-100%25-1ED760)

</div>

---

Know Your Code (engine name `knowit`) turns an unfamiliar codebase into something you can actually navigate. Connect a Git URL or a local folder; it indexes the code once — symbols, a call/import graph, and searchable embeddings — and every view after that reads from that single in-memory index. It runs entirely on your machine: the only things that ever leave are the initial `git clone` and, if you choose, calls to an LLM you configure.

## Features

- **Ask your codebase** — plain-English questions answered with retrieval-augmented generation. Hybrid search (BM25 + on-device semantic embeddings, fused with Reciprocal Rank Fusion) is expanded through the call graph, so answers pull in related code you didn't name. Responses stream token-by-token with cited sources.
- **Overview** — files, languages, lines of code, hub files, entry points, most-complex symbols, likely-dead code, and the rendered README at a glance.
- **Files** — browse the tree with per-file summaries and clickable symbol chips; a per-function explainer shows code plus callers and callees. Markdown files render as formatted markdown.
- **Insight Graph** — an interactive, pannable architecture map that groups files into areas and draws their dependencies.
- **API & DB** — auto-detected HTTP routes (FastAPI, Flask, Express, …) and ORM/data models.
- **Timeline & Track** — a living, LLM-free record of what changed over time via structural fingerprint diffs, plus on-demand structural diffs between any two commits. Git history is imported merge-aware, so every commit shows its files.
- **Intel** — tech-debt analysis: dead code, import cycles, complexity hotspots, god files, near-duplicates, and undocumented symbols.
- **Download report** — export a full analysis of any repo as Markdown, Word (`.docx`), or PDF, from any tab.
- **Bring your own model** — OpenAI, Anthropic, Google Gemini, Groq, OpenRouter, local Ollama, or any OpenAI-compatible endpoint. No key required: indexing, search, structure, and tracking all work offline; only synthesized answers and explanations need a model.

## How it works

Three components live side by side and wire together by relative path:

| Component | What it is |
|-----------|------------|
| `app/` | The product — a React + Vite frontend over a thin FastAPI backend. |
| `engine/` | The `knowit` Python package: indexing, retrieval, graph, tracking, analysis. |
| `diagrams/` | `codemap` — a standalone, stdlib-only architecture-map generator. |

Indexing runs in six stages: **ingest/clone → parse (AST for Python, regex for JS/TS) → build the code graph → chunk → build retrievers (BM25 + optional Chroma embeddings) → cache**. The result is an in-memory `RepoIndex`; every feature is a pure read over it. A full internals walkthrough lives in [`docs/how-it-works.html`](docs/how-it-works.html).

## Quick start

**Requirements:** Python 3.10+ and Node.js 18+.

```bash
git clone https://github.com/samratrajsharma/knowyourcode.git
cd knowyourcode
```

### Windows (PowerShell)

```powershell
cd app
.\run.ps1
```

`run.ps1` creates a virtual environment, installs backend and frontend dependencies on first run, and launches both servers.

### Any OS (manual)

```bash
# Backend  ->  http://localhost:8100
cd app/backend
pip install -r requirements.txt
python main.py

# Frontend ->  http://localhost:5273   (in a second terminal)
cd app/frontend
npm install
npm run dev
```

Open **http://localhost:5273**, paste a Git URL or a local folder path, and connect.

### Launcher flags (Windows)

| Command | Effect |
|---------|--------|
| `.\run.ps1` | Start backend (`:8100`) + frontend (`:5273`) |
| `.\run.ps1 -Fresh` | Wipe all indexed repos, caches, and timeline history, then start |
| `.\run.ps1 -Fresh -Yes` | Same, without the confirmation prompt |
| `.\run.ps1 -Reload` | Start with backend hot-reload enabled |
| `.\run.ps1 -Website` | Serve the marketing site only, on `:5300` |
| `.\stop.ps1` | Stop both servers |

## Configuration

All configuration is optional and lives in `app/backend/.env` (copy from `.env.example`). The app runs fully without any of it.

| Variable | Purpose |
|----------|---------|
| `KNOWIT_LLM_PROVIDER` | `openai` \| `anthropic` \| `gemini` \| `groq` \| `ollama` \| `openrouter` \| `custom` |
| `KNOWIT_LLM_MODEL` | Model name for the chosen provider |
| `KNOWIT_LLM_BASE_URL` | Endpoint for Ollama (`http://localhost:11434`) or a custom provider |
| `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, `GROQ_API_KEY`, `OPENROUTER_API_KEY` | Set only the one you use |
| `KNOWIT_EMBED_BACKEND` | `auto` \| `hybrid` \| `bm25` \| `chroma` (retrieval mode) |
| `KNOWIT_DATA_DIR` | Where parsed indexes and clones are cached |

Providers and models can also be configured live from the in-app **Settings** tab.

## Project structure

```
app/
  backend/     FastAPI REST + SSE layer over the engine (main.py -> :8100)
  frontend/    React 19 + Vite + TypeScript UI (:5273)
  run.ps1      dev launcher (backend + frontend)
engine/
  knowit/      the analysis engine (ingest, parsing, graph, retrieval,
               llm, insights, techdebt, track, providers, ...)
  tests/       engine test suite
diagrams/
  codemap/     standalone architecture-map generator
docs/          internals documentation
```

## Tech stack

**Backend:** FastAPI · Uvicorn · Pydantic · LiteLLM (provider-agnostic LLM routing) · ChromaDB (on-device embeddings) · python-docx / reportlab (report export).
**Frontend:** React 19 · Vite · TypeScript.
**Engine:** pure Python — stdlib `ast` parsing, a hand-rolled code graph, and a stdlib BM25 implementation, so the core has no heavy dependencies.

## Privacy & security

- **Local-first.** Your source is indexed, embedded, searched, graphed, tracked, and reported on entirely on your machine. The only outbound traffic is the initial `git clone` and — if you configure a model — LLM API calls for answers and explanations.
- **Loopback only.** The backend binds to `127.0.0.1`; the browser reaches it through the Vite proxy.
- **Hardened cloning.** Clone URLs are transport-allowlisted (`http`/`https`/`ssh`/`git` only) and argument-injection guarded.
- **XSS-safe UI.** All repository, LLM, and README content renders as text — no raw HTML injection — so an untrusted README cannot run script.

## Requirements

- Python 3.10 or newer
- Node.js 18 or newer
- Git

## License

No license file is currently included. Add a `LICENSE` before public distribution.
