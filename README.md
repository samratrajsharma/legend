<div align="center">

# Legend

**Local-first codebase intelligence.** Point Legend at any repository or folder and it maps the architecture, explains files, answers plain-English questions with your own LLM, and tracks how the code changes over time — all on your machine.

[![PyPI](https://img.shields.io/pypi/v/legend-lens?color=1ED760&label=legend-lens)](https://pypi.org/project/legend-lens/)
[![Website](https://img.shields.io/badge/website-live-1ED760)](https://samratrajsharma.github.io/legend/)
![Python](https://img.shields.io/badge/python-3.10+-3776AB)
![local-first](https://img.shields.io/badge/local--first-100%25-1ED760)
![License](https://img.shields.io/badge/license-MIT-blue)

### [→ Visit the live website](https://samratrajsharma.github.io/legend/)

**[Website](https://samratrajsharma.github.io/legend/)** · [PyPI](https://pypi.org/project/legend-lens/) · [Quick start](#quick-start) · [Report a bug](https://github.com/samratrajsharma/legend/issues)

</div>

---

Legend indexes a codebase **once** — symbols, a call/import graph, and searchable embeddings — then every view reads from that single in-memory index. It runs entirely on your machine: the only things that ever leave are the initial `git clone` and, if you choose to enable AI answers, calls to an LLM you configure. No account, no telemetry, no cloud.

> **Package name:** the PyPI project is **`legend-lens`** (PyPI reserves the bare name `legend`). The command it installs is just **`legend`**.

## Contents

- [Quick start](#quick-start)
- [Installation](#installation)
  - [Optional features (extras)](#optional-features-extras)
- [Using the `legend` command](#using-the-legend-command)
  - [Command-line options](#command-line-options)
  - [Examples](#examples)
- [Using the app](#using-the-app)
- [Use with coding agents (MCP)](#use-with-coding-agents-mcp)
- [Enabling AI answers (bring your own model)](#enabling-ai-answers-bring-your-own-model)
- [Configuration reference](#configuration-reference)
- [Where your data lives](#where-your-data-lives)
- [Updating & uninstalling](#updating--uninstalling)
- [Troubleshooting & FAQ](#troubleshooting--faq)
- [Language support](#language-support)
- [How it works](#how-it-works)
- [Privacy & security](#privacy--security)
- [Run from source (development)](#run-from-source-development)
- [Project structure](#project-structure)
- [License](#license)

## Quick start

If you have [`uv`](https://docs.astral.sh/uv/) installed, you don't need to install Legend at all:

```bash
uvx legend-lens .                                   # index the current folder
uvx legend-lens https://github.com/pallets/click    # or clone + index any repo
```

Legend starts, indexes the code, and opens `http://127.0.0.1:8100` in your browser. Structure, files, search, the graph, and metrics all work immediately — **no API key or configuration required**.

Don't have `uv`? Install it once with `pip install uv` (or see the [uv install guide](https://docs.astral.sh/uv/getting-started/installation/)), or use pip/pipx below.

## Installation

You need **Python 3.10+** and **git**. Pick whichever method suits you:

| Method | Command | Best for |
|--------|---------|----------|
| **uvx** (zero-install) | `uvx legend-lens <repo>` | Trying it instantly; always runs the latest version |
| **pipx** (isolated) | `pipx install legend-lens` | Keeping a permanent `legend` command without touching other environments |
| **pip** (into a venv) | `pip install legend-lens` | Adding Legend to a project/virtual environment |

```bash
# uvx — nothing to install; downloads and runs on demand
uvx legend-lens .

# pipx — installs the `legend` command globally, isolated
pipx install legend-lens
legend .

# pip — into your current (virtual) environment
pip install legend-lens
legend .
```

After a pip/pipx install you have two equivalent commands: **`legend`** (short) and **`legend-lens`**.

### Optional features (extras)

The base install is intentionally lean and fully offline. Heavier features are opt-in extras:

| Extra | Adds | Install |
|-------|------|---------|
| `semantic` | On-device semantic search (ChromaDB embeddings) for better "Ask" and search results | `pip install "legend-lens[semantic]"` |
| `llm` | AI answers & explanations (LiteLLM — routes to your chosen provider) | `pip install "legend-lens[llm]"` |
| `treesitter` | Deeper parsing for 10+ languages (Go, Java, Rust, C#, Ruby, PHP, C, C++, …) | `pip install "legend-lens[treesitter]"` |
| `export` | Download reports as Word (`.docx`) and PDF | `pip install "legend-lens[export]"` |
| `all` | Everything above | `pip install "legend-lens[all]"` |

With `uvx`, add extras via `--with`, e.g. `uvx --with "legend-lens[all]" legend-lens .` — or install the base and rely on the built-in BM25 search, which needs no extras.

> **Note:** AI answers require **both** the `llm` extra **and** a configured model (see [Enabling AI answers](#enabling-ai-answers-bring-your-own-model)). Without them, everything else still works — search just uses the built-in BM25 index instead of embeddings.

## Using the `legend` command

The command takes one optional argument — what to open:

```bash
legend .                                  # index the folder you're in
legend C:\path\to\project                 # index a specific local folder
legend https://github.com/user/repo       # clone + index a remote repo
legend                                     # just start the app; paste a repo in the browser
```

Whatever you pass, Legend launches the local web app on `http://127.0.0.1:8100` and opens your browser there. The repo appears in the sidebar and opens automatically once indexing finishes.

### Command-line options

```
legend [source] [options]
```

| Option | Default | Description |
|--------|---------|-------------|
| `source` | *(none)* | A git URL, a local folder, or `.` for the current folder. Omit to start the app with nothing loaded. |
| `--port <n>` | `8100` | Port to serve the app on. |
| `--host <addr>` | `127.0.0.1` | Address to bind. Keep it on loopback unless you know you want otherwise. |
| `--data-dir <path>` | `~/.legend/cache` | Where indexes and clones are cached between runs. |
| `--no-open` | *(off)* | Don't automatically open the browser. |
| `--help` | | Show all options and exit. |

### Examples

```bash
# Open the current project
legend .

# Analyze a public repo on a different port, without auto-opening the browser
legend https://github.com/pallets/flask --port 9000 --no-open
# then visit http://127.0.0.1:9000 yourself

# Keep each project's cache separate
legend C:\work\service-a --data-dir C:\work\service-a\.legend

# Start empty and paste a repo URL in the UI
legend
```

To stop Legend, press **Ctrl+C** in the terminal where it's running.

## Using the app

Once the browser is open, you'll find these tabs:

- **Overview** — the big picture: file and language counts, lines of code, hub files, entry points, most-complex symbols, likely-dead code, and the rendered README.
- **Files** — browse the file tree with a per-file summary and clickable symbol chips. Click a function to see its code alongside its callers and callees. Markdown files render formatted.
- **Ask** — type a plain-English question ("where is auth handled?", "what calls `build_index`?"). Answers stream in with cited source snippets. *(Requires a configured model — see below.)*
- **Insight Graph** — an interactive, pannable map that groups files into areas and draws their dependencies. Pan, zoom, and click nodes to explore.
- **API & DB** — auto-detected HTTP routes (FastAPI/Flask) and ORM/data models.
- **Timeline & Track** — a running, LLM-free record of what changed over time from structural fingerprints, plus on-demand structural diffs between any two commits.
- **Intel** — tech-debt analysis: dead code, import cycles, complexity hotspots, "god" files, near-duplicates, and undocumented symbols.
- **Settings** — configure your LLM provider/model and search backend live, without restarting.
- **Download report** — from any tab, export the full analysis as Markdown, or (with the `export` extra) Word/PDF.

## Use with coding agents (MCP)

Legend also runs as an [MCP](https://modelcontextprotocol.io) server, giving coding agents (Claude Code, Claude Desktop, Cursor, Windsurf, Zed, Continue, Cline — anything that speaks MCP) **deterministic** answers about your code's structure. These are the questions that otherwise cost an agent a dozen greps and tens of thousands of tokens to approximate — here they're one call each.

```bash
uvx --from "legend-lens[mcp]" legend mcp --repo .
# or, once installed:  pip install "legend-lens[mcp]"   then   legend mcp --repo .
```

Point your MCP client at it:

```json
{
  "mcpServers": {
    "legend": { "command": "uvx", "args": ["--from", "legend-lens[mcp]", "legend", "mcp", "--repo", "."] }
  }
}
```

Tools exposed (all read-only, one deterministic call each):

| Tool | Answers |
|------|---------|
| `blast_radius(symbol)` | Everything transitively affected if this symbol changes (callers + importers). |
| `callers_of` / `callees_of` | Resolved call edges (optionally transitive) — not text matches. |
| `impact_of_change(file)` | Blast radius of editing a whole file. |
| `structural_diff(base, head)` | Symbol/import/complexity changes between two git refs. |
| `routes_touched` / `models_touched` | HTTP routes / data models whose file is in a change set. |
| `cycles(base?)` | Import cycles — or only those introduced since a ref. |
| `architecture_map` / `public_surface` | Area dependencies; entry points, exports, cross-file API. |
| `find_symbol` / `overview` / `reindex` | Resolve a name; orient; refresh after edits. |

Drop [`skills/legend/SKILL.md`](skills/legend/SKILL.md) into your agent so it knows *when* to call them (e.g. `blast_radius` before editing a function, `cycles` before merging).

**Derived context file.** Generate an always-fresh `AGENTS.md` straight from the code graph — the real route table, module boundaries, entry points, hub files, public surface, and constraints (import cycles, complexity hotspots). These are the non-inferable specifics a hand-written context file gets wrong or lets go stale:

```bash
legend context --write AGENTS.md      # or: legend context   (prints to stdout)
```

It's *derived* context, not written context — regenerate it on each commit (e.g. a pre-commit hook) so it can never drift from the code.

**CI regression gate.** Fail a pull request when a change introduces a *structural* regression — a new import cycle, a removed public symbol, or a complexity spike. Run it at your repo's git root:

```bash
legend check --base main        # exit 0 = clean, 1 = regression, 2 = error
legend check --base origin/main --strict   # also fail on complexity spikes
```

Drop it into CI (needs full history so the base ref is present):

```yaml
# .github/workflows/legend-check.yml
name: legend check
on: pull_request
jobs:
  structure:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with: { fetch-depth: 0 }
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: pipx install legend-lens
      - run: legend check --base "origin/${{ github.base_ref }}"
```

## Enabling AI answers (bring your own model)

Indexing, structure, files, search, the graph, metrics, and tracking **all work offline with no model**. Only the **Ask** tab and per-function explanations call an LLM — and you bring your own.

To turn them on:

1. Install the AI extra: `pip install "legend-lens[llm]"` (or `[all]`).
2. Configure a provider, either way:
   - **In-app (easiest):** open the **Settings** tab, pick a provider, paste your key, choose a model. Takes effect immediately.
   - **Environment variables:** set them before launching `legend` (see the table below).

Supported providers:

| Provider | `LEGEND_LLM_PROVIDER` | Key variable | Notes |
|----------|----------------------|--------------|-------|
| OpenAI | `openai` | `OPENAI_API_KEY` | |
| Anthropic | `anthropic` | `ANTHROPIC_API_KEY` | |
| Google Gemini | `gemini` | `GEMINI_API_KEY` | |
| Groq | `groq` | `GROQ_API_KEY` | |
| OpenRouter | `openrouter` | `OPENROUTER_API_KEY` | Access many models via one key |
| Ollama | `ollama` | *(none)* | Local models; set `LEGEND_LLM_BASE_URL=http://localhost:11434` |
| Custom | `custom` | *(varies)* | Any OpenAI-compatible endpoint via `LEGEND_LLM_BASE_URL` |

Example (PowerShell):

```powershell
$env:LEGEND_LLM_PROVIDER = "openai"
$env:LEGEND_LLM_MODEL    = "gpt-4o-mini"
$env:OPENAI_API_KEY      = "sk-..."
legend .
```

Example (macOS/Linux):

```bash
LEGEND_LLM_PROVIDER=anthropic LEGEND_LLM_MODEL=claude-3-5-sonnet-latest ANTHROPIC_API_KEY=sk-ant-... legend .
```

Your key stays on your machine and is used only to call the provider you chose.

## Configuration reference

Everything is optional. Set these as environment variables before running `legend`, or use the Settings tab.

| Variable | Purpose |
|----------|---------|
| `LEGEND_LLM_PROVIDER` | `openai` \| `anthropic` \| `gemini` \| `groq` \| `ollama` \| `openrouter` \| `custom` |
| `LEGEND_LLM_MODEL` | Model name for the chosen provider |
| `LEGEND_LLM_BASE_URL` | Endpoint for Ollama (`http://localhost:11434`) or a custom provider |
| `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, `GROQ_API_KEY`, `OPENROUTER_API_KEY` | Set only the one you use |
| `LEGEND_EMBED_BACKEND` | `auto` \| `hybrid` \| `bm25` \| `chroma` — how search retrieves (defaults to the best available) |
| `LEGEND_DATA_DIR` | Where parsed indexes and clones are cached (same as `--data-dir`) |

## Where your data lives

Legend caches indexes and cloned repos under **`~/.legend/cache`** (override with `--data-dir` or `LEGEND_DATA_DIR`). Re-running on the same repo reuses the cache, so subsequent starts are fast.

To reset everything, delete that folder:

```powershell
Remove-Item -Recurse -Force $HOME\.legend        # Windows
```
```bash
rm -rf ~/.legend                                 # macOS/Linux
```

## Updating & uninstalling

```bash
# uvx always fetches the latest; force a refresh of its cache:
uvx --refresh legend-lens .

# pipx
pipx upgrade legend-lens
pipx uninstall legend-lens

# pip
pip install --upgrade legend-lens
pip uninstall legend-lens
```

## Troubleshooting & FAQ

**`uvx: command not found`** — install uv first: `pip install uv` (or the [official installer](https://docs.astral.sh/uv/getting-started/installation/)). `uvx` ships with uv, just like `npx` ships with Node.

**The browser didn't open.** Open `http://127.0.0.1:8100` manually (or your `--port`). Use `--no-open` if you prefer to open it yourself.

**Port already in use.** Another app (or a previous Legend) is on 8100 — run with `--port 9000` (any free port).

**The "Ask" tab says no model is configured.** Install the `llm` extra and set a provider — see [Enabling AI answers](#enabling-ai-answers-bring-your-own-model). Everything else works without it.

**Search feels shallow / I want semantic search.** Install the `semantic` extra (`pip install "legend-lens[semantic]"`). Without it, Legend uses a solid built-in BM25 keyword index.

**My language isn't fully analyzed.** Python has the deepest support (full AST). Install the `treesitter` extra for structural parsing of Go, Java, Rust, C#, Ruby, PHP, C, C++, and more. See [Language support](#language-support).

**First index of a big repo is slow.** Indexing walks the whole tree once; after that it's cached. Subsequent runs are fast.

**Is any of my code sent anywhere?** No — indexing/search/graph/metrics are fully local. The only outbound traffic is the initial `git clone` (for a URL you give) and, *if* you enable AI answers, calls to the provider you configured. See [Privacy & security](#privacy--security).

## Language support

- **Python** — full support via the standard-library AST (symbols, call/import graph, complexity, API/DB detection).
- **JavaScript / TypeScript** — best-effort structural parsing built in.
- **10+ more** (Go, Java, Rust, C#, Ruby, PHP, C, C++, …) — install the `treesitter` extra to enable tree-sitter-backed parsing.

Every language benefits from file/line metrics, search, the timeline, and reports even without deep parsing.

## How it works

Three components live side by side:

| Component | What it is |
|-----------|------------|
| `app/` | The product — a React + Vite frontend over a thin FastAPI backend. When installed, the backend serves the pre-built UI on one port. |
| `engine/` | The `legend` Python package: indexing, retrieval, graph, tracking, analysis. |
| `diagrams/` | `codemap` — a standalone, stdlib-only architecture-map generator. |

Indexing runs in six stages: **ingest/clone → parse (AST for Python, regex for JS/TS, tree-sitter for the rest) → build the code graph → chunk → build retrievers (BM25 + optional embeddings) → cache**. The result is an in-memory index that every feature reads from. A deeper walkthrough is in [`docs/how-it-works.html`](docs/how-it-works.html).

## Privacy & security

- **Local-first.** Your source is indexed, embedded, searched, graphed, tracked, and reported on entirely on your machine.
- **Minimal outbound traffic.** Only the initial `git clone` (for a URL you provide) and — if you enable a model — LLM API calls for answers and explanations.
- **Loopback by default.** The app binds to `127.0.0.1`.
- **Hardened cloning.** Clone URLs are transport-allowlisted (`http`/`https`/`ssh`/`git`) and argument-injection guarded.
- **XSS-safe UI.** Repository, LLM, and README content renders as text — an untrusted README can't run script.
- **No telemetry.** Legend collects nothing; on-device embedding telemetry is explicitly disabled.

## Run from source (development)

For contributors or anyone who wants the dev servers with hot reload. **Requirements:** Python 3.10+, Node.js 18+, git.

```bash
git clone https://github.com/samratrajsharma/legend.git
cd legend
```

**Windows (PowerShell):**

```powershell
cd app
.\run.ps1        # creates a venv, installs deps on first run, starts both servers
```

**Any OS (manual):**

```bash
# Backend  ->  http://localhost:8100
cd app/backend
pip install -r requirements.txt
python main.py

# Frontend ->  http://localhost:5273   (second terminal)
cd app/frontend
npm install
npm run dev
```

Then open **http://localhost:5273** and connect a repo. (In dev the UI runs on 5273 via Vite; the packaged `legend` command instead serves everything on 8100.)

**Windows launcher flags:**

| Command | Effect |
|---------|--------|
| `.\run.ps1` | Start backend (`:8100`) + frontend (`:5273`) |
| `.\run.ps1 -Fresh` | Wipe indexed repos, caches, and timeline history, then start |
| `.\run.ps1 -Fresh -Yes` | Same, without the confirmation prompt |
| `.\run.ps1 -Reload` | Start with backend hot-reload |
| `.\run.ps1 -Website` | Serve the marketing site only, on `:5300` |
| `.\stop.ps1` | Stop both servers |

**Build the distributable wheel** (bundles the frontend into the package):

```bash
python scripts/build.py      # npm build -> app/backend/web/
python -m build              # -> dist/legend_lens-*.whl
```

## Project structure

```
app/
  backend/     FastAPI REST + SSE layer over the engine; serves the built UI when packaged
  frontend/    React 19 + Vite + TypeScript UI
  run.ps1      dev launcher (backend + frontend)
engine/
  legend/      the analysis engine (ingest, parsing, graph, retrieval,
               llm, insights, techdebt, track, providers, ...)
  tests/       engine test suite
diagrams/
  codemap/     standalone architecture-map generator
scripts/
  build.py     bundles the frontend into the wheel
docs/          internals documentation
```

## License

Released under the **MIT License** — free to use, modify, and distribute. See [LICENSE](LICENSE) for the full text.

© 2026 Samrat Raj Sharma
