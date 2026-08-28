# Contributing to Know Your Code

Thanks for your interest in improving Know Your Code. It's a local-first codebase-intelligence
tool: point it at a repository and it parses the code, builds a symbol/call/import graph, and
answers questions over it with hybrid (BM25 + semantic) retrieval. This guide gets you from a
fresh clone to a passing test run and an open pull request.

## Project layout

```
engine/          the KnowIT engine — a pure-stdlib-core Python library (package: knowit)
  knowit/          parsing, graph, chunking, retrieval, insights, techdebt, ...
  tests/           pytest suite over a bundled sample_repo (BM25-only, offline)
  sample_repo/     tiny fixture repo the tests build an index over
  pyproject.toml   packaging (pip install -e engine)
app/
  backend/         FastAPI wrapper over the engine (main.py launches uvicorn on :8100)
    tests/           httpx/TestClient contract tests for the API
  frontend/        React + Vite single-page app (dev server on :5273)
  run.ps1 / run.sh Windows / macOS-Linux launchers (start backend + frontend together)
diagrams/codemap/  standalone HTML architecture map the backend serves
Dockerfile         backend API image
```

## Prerequisites

Python 3.10+ (3.12 recommended), Node 18+, and `git` on your PATH (repo ingestion shells out
to `git clone`).

## Getting started

The fastest path is the launcher, which installs dependencies on first run and starts both
processes:

```bash
# macOS / Linux
./app/run.sh

# Windows (PowerShell)
.\app\run.ps1
```

Then open http://localhost:5273. The backend API and its interactive docs are at
http://localhost:8100/docs.

To set up the pieces manually instead:

```bash
# engine (editable install exposes the `knowit` package everywhere)
pip install -e engine

# backend
pip install -r app/backend/requirements.txt
cd app/backend && python main.py        # serves :8100

# frontend
cd app/frontend && npm install && npm run dev   # serves :5273
```

Optional engine features live behind extras and are lazy-imported, so a missing one degrades
that one feature instead of breaking startup: `pip install -e "engine[all]"` pulls semantic
retrieval (chromadb), LLM answers (litellm), multi-language parsing (tree-sitter), and report
export (docx/pdf/pptx). Install just what you need, e.g. `engine[semantic,llm]`.

## Running the tests

The engine and backend suites run independently (both are offline and deterministic — BM25
only, no network, no LLM):

```bash
# engine
cd engine && python -m pytest -q

# backend API (needs fastapi + httpx; installed via app/backend/requirements.txt)
cd app/backend && python -m pytest -q

# frontend type-check + build
cd app/frontend && npm run build
```

CI runs the engine suite on Python 3.10–3.12 and the backend suite on every push and pull
request; please make sure all three pass locally before opening a PR.

## Making a change

Every fix should ship with a regression test — that's how an OSS project stays fixed. Add or
extend a test under `engine/tests/` (pure engine behavior) or `app/backend/tests/` (an API
contract), and keep the change focused.

We use a short-lived branch per change, merged into `main`:

```bash
git checkout -b feat/short-description main
# ... make the change + its test ...
git commit -m "feat: what changed and why"
git checkout main
git merge --no-ff feat/short-description -m "Merge feat/short-description"
git branch -d feat/short-description
git push
```

Write clear commit messages (a `type: summary` subject, e.g. `fix:`, `feat:`, `docs:`,
`test:`, `chore:`). In the PR description, say what changed, why, and how you verified it.

## Style

Match the surrounding code. Python targets 3.10+ and the engine core stays dependency-free
(keep heavy imports lazy). The frontend is TypeScript with `strict` on — `npm run build` must
type-check clean. Prefer a correct, well-tested small change over a broad one.

## Reporting bugs and requesting features

Open an issue using the templates. For bugs, include the repo you pointed it at (or a minimal
one), what you expected, what happened, and any backend log output (`KNOWIT_LOG_LEVEL=DEBUG`
for more detail).
