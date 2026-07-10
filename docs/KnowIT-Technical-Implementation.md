---
title: "KnowIT — Technical Implementation Document"
subtitle: "A complete, ground-up explanation of how the system works"
author: "Thoughtrons · KnowIT Engineering"
date: "Version 1.0 — covering Phases 0–4"
toc-title: "Table of Contents"
---

# Contents {-}

- Preface
- 1. Introduction and Motivation
- 2. Core Concepts and Vocabulary
- 3. System Architecture and Data Flow
- 4. Configuration (`config.py`)
- 5. Data Models (`models.py`)
- 6. Ingestion (`ingest.py`)
- 7. Parsing (`parsing.py`)
- 8. The Code Graph (`graph.py`)
- 9. Chunking (`chunking.py`)
- 10. Indexing and Retrieval (`index.py`, `retrieval.py`)
- 11. The LLM Layer (`llm.py`, `providers.py`)
- 12. Pipeline, Caching, and Multi-Repo (`pipeline.py`)
- 13. Insights (`insights.py`)
- 14. Diagrams (`diagram.py`)
- 15. Teaching (`teach.py`)
- 16. Change Tracking (`track.py`)
- 17. Evaluation (`eval_harness.py`)
- 18. Engineering Intelligence (`techdebt.py`, `engmemory.py`)
- 19. Learning Media (`media.py`)
- 20. Research Mode (`research.py`)
- 21. Portfolio Mode (`portfolio.py`)
- 22. Beyond the Plan: Learning Retention and Engineering Add-ons
- 23. The Streamlit Application (`app.py`)
- 24. Running and Deploying KnowIT
- 25. Extending KnowIT
- 26. Testing, Verification, and Engineering Practices
- 27. Performance, Complexity, and Scaling
- 28. Security, Privacy, and Data Handling
- 29. Design Decisions and Trade-offs
- 30. Completion and Verification
- 31. Limitations and Roadmap
- Appendix A: Configuration and Environment Reference
- Appendix B: API Reference
- Appendix C: Data Model Reference
- Appendix D: Code-Graph Schema Reference
- Appendix E: Dependency Reference
- Appendix F: A Worked Example — Tracing a Question End to End
- Appendix G: Per-Tab Control Flow
- Appendix H: On-Disk Data Formats
- Appendix I: FAQ and Troubleshooting
- Appendix J: Glossary
- Appendix K: Complete Source Listing of the `knowit` Package

\newpage

# Preface {-}

## Who this document is for {-}

This document explains the complete technical workings of **KnowIT**, a system that ingests a software repository and helps a person *understand*, *learn*, *track*, and *explain* that codebase. It is written for a **technically literate reader who knows nothing about this project**: a software engineer, data scientist, or technical manager who is comfortable reading Python, understands basic data structures and HTTP, and has at least passing familiarity with large language models (LLMs) and information retrieval — but who has never seen KnowIT, does not know its vocabulary, and should not be expected to infer anything.

Because of that audience, the document is deliberately self-contained. Every concept is defined before it is used. Every module is explained in terms of its inputs, outputs, the algorithm it runs, and the design reasons behind it. Where an algorithm has a precise mathematical form (such as the BM25 ranking function or Reciprocal Rank Fusion), the formula is given and explained. Where a design choice was contentious (such as using Python's standard-library parser instead of tree-sitter), the trade-off is laid out explicitly.

## How to read it {-}

The document is organised into five parts plus a set of reference appendices:

- **Part I — Orientation** gives you the problem KnowIT solves, the vocabulary you need, and a bird's-eye view of the architecture and the data that flows through it. Read this first; everything else assumes it.
- **Part II — The Engine** is a module-by-module deep dive into the core: configuration, data models, ingestion, parsing, the code graph, chunking, indexing and retrieval, the LLM layer, and the pipeline that ties them together. This is the heart of the system.
- **Part III — Knowledge & Learning Features** covers the things built on top of the engine: insights, the interactive diagrams, the teaching features (learning paths, flashcards, quizzes, interviews, gaps), change tracking, and evaluation.
- **Part IV — The Application** explains the Streamlit user interface: how the tabs are wired, how state and caching work, and how the UI calls into the engine.
- **Part V — Operations & Extension** tells you how to install, configure, and run the system, how to extend it (new languages, new LLM providers, new diagram types), how it is tested, and what its current limitations and roadmap are.
- **Appendices** are dense reference material: a complete configuration reference, an API reference for every public function, the data-model reference, the environment-variable reference, and a glossary.

If you only have an hour, read Chapters 1, 3, and 10 — that is the problem, the architecture, and the retrieval engine, which together convey the essence of the system.

## A note on the system's design temperament {-}

One idea recurs throughout this document, and it is worth stating up front because it explains a great many decisions: **KnowIT is dependency-light and degrades gracefully.** The entire core runs on the Python standard library. Heavier capabilities — semantic vector search, LLM answer synthesis, an interactive draggable graph canvas — are *optional accelerators* that activate automatically when their libraries are installed and silently fall back to a simpler, always-available implementation when they are not. This is not an accident or a limitation; it is a deliberate architectural stance that makes the system runnable anywhere, testable without secrets or network access, and resilient to the failure of any one external dependency. You will see this pattern in the parser (tree-sitter optional, `ast` always), the retriever (Chroma optional, BM25 always), the LLM layer (litellm optional, cited-context-only always), and the diagrams (pyvis optional, Graphviz always).

\newpage

# Introduction and Motivation

## The problem

Reading an unfamiliar codebase is one of the most common and most underserved tasks in software engineering. When an engineer joins a team, picks up an open-source project, or returns to their own code after six months, they face the same wall: thousands of lines spread across dozens of files, with the *structure* and the *intent* of the system encoded implicitly in import statements, call relationships, naming conventions, and tribal knowledge that lives in people's heads rather than in the repository.

The problem is especially acute for **machine-learning and research code**, which is KnowIT's initial focus. ML repositories tend to combine several hard-to-read sub-systems — data pipelines, model definitions, training loops, inference services, and evaluation harnesses — and they are frequently written quickly, by researchers, with sparse documentation and dense, idiom-heavy code. Understanding *why* a repository uses a particular architecture (a DETR-style detector rather than a YOLO one, focal loss rather than cross-entropy) often requires understanding the research literature behind it, not just the code.

There is no shortage of tools that help you *write* code (Copilot, Cursor) or *search* it (Sourcegraph, Greptile), and a recent class of tools will auto-generate documentation for a repository (Cognition's DeepWiki). What is conspicuously missing is a tool whose explicit goal is to make *you*, the human, understand and retain the system: to teach the repository the way a good senior engineer would, to test whether you actually understand it, and to track how both the codebase and your understanding of it change over time. That is the gap KnowIT targets.

## What KnowIT is

KnowIT is a single application — launched with one command, `streamlit run app.py` — that takes a repository (a local folder or a git URL) and turns it into an interactive understanding-and-learning environment. Concretely, it does the following, each of which is the subject of a later chapter:

- **Ingests** the repository, recording the exact git commit so that everything it produces can be traced back to a precise version of the code.
- **Parses** every source file into a structured representation of its symbols (functions, classes, methods), their imports, the calls between them, their inheritance relationships, and a complexity score for each.
- **Builds a code graph** — a directed graph whose nodes are files and symbols and whose edges are the *contains*, *calls*, *imports*, *method-of*, and *inherits* relationships among them. This graph is the structural backbone of everything else.
- **Chunks** the code into retrievable units, each tagged with the graph node and git commit it came from.
- **Retrieves** relevant code for any natural-language question using a hybrid of keyword search (BM25) and semantic vector search (embeddings), fused together and then expanded along the code graph.
- **Explains** the repository: per-file purpose and dependencies, repo-wide insights (entry points, hub files, complexity hotspots, likely-unused code), API and database maps, and a suite of **interactive diagrams**.
- **Teaches** the repository: a generated learning path, flashcards, multi-level quizzes, an interview mode, and a *learning-gaps tracker* that knows what you have and have not explored.
- **Tracks** the repository's evolution: it can snapshot the structure at any two commits and produce a changelog, an architecture delta, and a *learning delta* that flags the things you had already studied which have since changed.
- **Answers** free-form questions about the code, optionally synthesising a written answer with a large language model from any of several providers (OpenAI, Anthropic, Groq, Ollama, OpenRouter, or a custom endpoint).
- **Evaluates** its own retrieval quality against a question set, reporting a pass/fail gate.

## The bigger vision and what is built

KnowIT's full product vision is organised into six "tiers" of capability, from basic repository understanding up through a learning layer, engineering intelligence, change tracking, a research mode, and a portfolio mode. The implementation described in this document covers the first wave of that vision, delivered as a sequence of **phases**:

| Phase | Name | Status | What it delivered |
|---|---|---|---|
| 0 | Foundations & Retrieval | Built | Ingest, parse, code graph, chunking, hybrid retrieval, eval harness, the Streamlit shell |
| 1 | Understand | Built | Per-file explanations, repo insights, complexity, the first diagrams |
| 2 | Teach | Built | Learning path, flashcards, quizzes, interview mode, learning-gaps tracker |
| 3 | Deepen Understanding | Built | Multi-language (JS/TS), inheritance, all diagram types, API/DB maps, native rendering |
| 4 | Track | Built | Commit snapshots, changelog, architecture delta, learning delta |

In addition, a cross-cutting "deepened engine" iteration added hybrid retrieval with rank fusion, an on-disk cache, multi-repository support, a multi-provider LLM layer, and an interactive diagram explorer. Phases 5 through 8 (engineering intelligence, rich learning media, research mode, and portfolio mode) are planned but not yet built; they are described in the roadmap chapter so you understand where the current code is heading and why certain seams exist in the architecture.

## Design goals

Five goals shaped the implementation. They are referenced repeatedly later, so they are named here:

1. **Runs anywhere, immediately.** A new user should be able to clone the repository, install dependencies, run one command, and have a working system indexing a sample repository within seconds — with no API keys, no cloud services, and no network access required for the core experience.
2. **Graceful degradation.** Every external dependency is optional. The system detects what is installed and uses it; when something is missing, it falls back rather than failing.
3. **Provenance everywhere.** Every artifact the system generates — an explanation, a flashcard, a retrieved snippet — carries a reference to the graph node and the git commit it derived from. This is what makes change-tracking (Phase 4) cheap to add rather than a rewrite.
4. **Local-first and private by default.** The default configuration never sends your code anywhere. Semantic embeddings run on-device; LLM calls happen only when you explicitly configure a provider.
5. **Testable without secrets.** Because the core is dependency-light and deterministic, the whole pipeline can be exercised and verified headlessly — no GPU, no API key, no network — which is how the system was developed and validated.

\newpage
# Core Concepts and Vocabulary

Before the architecture will make sense, you need a small vocabulary. These terms are used precisely throughout the document; each is defined here once and then used without further explanation. Many are standard information-retrieval or compiler terms, but their *specific meaning inside KnowIT* matters.

## Repository, working tree, and commit

A **repository** (repo) is the unit KnowIT operates on: a directory of source files, usually under git version control. The **working tree** is the current on-disk state of those files. A **commit** is a specific, immutable snapshot of the repository identified by a 40-character SHA-1 hash; KnowIT records the commit (or the literal string `working-tree` when the directory is not a git repository) so that every downstream artifact is tied to an exact version of the code.

## Symbol

A **symbol** is a named, top-level-or-nested code definition: a function, a class, or a method. Symbols are the atoms of KnowIT's understanding. Each symbol has a stable identifier of the form `"<relative-path>::<qualified-name>"`, for example `model.py::Detector.predict`. The *qualified name* (qualname) includes the enclosing class for methods (`Detector.predict`) but is just the bare name for top-level functions (`run_inference`). A symbol also carries its kind (`function`, `method`, or `class`), its source line range, its docstring, its raw source code, the list of names it calls, its base classes (for inheritance), and a complexity score.

## Code graph

The **code graph** is a directed multigraph that captures the structure of the repository. Its **nodes** are of two types — *file* nodes (identified by their relative path) and *symbol* nodes (identified by the symbol id above). Its **edges** are typed:

| Edge type | Direction | Meaning |
|---|---|---|
| `contains` | file → symbol | the file defines this symbol |
| `method_of` | method → class | this method belongs to this class |
| `calls` | symbol → symbol | the source symbol calls the target symbol |
| `imports` | file → file | the source file imports the target file |
| `inherits` | class → class | the source class extends the target class |

The graph is the single source of structural truth. Retrieval expansion, diagrams, insights, teaching artifacts, and change-tracking are all computed from it.

## Chunk and provenance

A **chunk** is a unit of text submitted to the retrieval index. KnowIT produces three kinds of chunk: a *symbol* chunk (one function/class/method, with its docstring and code), a *module* chunk (a per-file summary listing imports and the symbols defined), and a *doc* chunk (the text of a Markdown file). The crucial property of every chunk is its **provenance**: it stores the `node_id` (the graph node it derived from) and the `commit` it was taken at. This `{graph node, commit}` pair is the thread that ties retrieval, diagrams, and change-tracking together; it is referred to throughout the document as *provenance tagging*.

## Retrieval, BM25, embeddings, and RRF

**Retrieval** is the act of, given a natural-language query, returning the chunks most relevant to it. KnowIT uses two complementary retrieval methods and fuses them:

- **BM25** (Best Matching 25) is a classical *lexical* ranking function: it scores a chunk by how often the query's words appear in it, weighted by how rare those words are across the corpus. It is exact-keyword-based, fast, and requires no model. It is KnowIT's always-available default.
- **Embeddings** (semantic / dense retrieval) convert text into vectors such that similar meanings map to nearby points; relevance is then vector similarity. This catches paraphrases that BM25 misses ("how is data prepared" matching a function whose docstring says "normalize and resize"). KnowIT obtains embeddings from **Chroma**, an embedded vector database whose default model runs on-device. This path is optional.
- **Reciprocal Rank Fusion (RRF)** is the method KnowIT uses to *combine* the two ranked lists into one. Rather than trying to reconcile incomparable scores, RRF combines *ranks*: a chunk's fused score is the sum, over each list it appears in, of `1 / (k + rank)`. This is robust, parameter-light, and is explained with its formula in Chapter 10.

## Graph expansion (GraphRAG)

Pure text retrieval returns chunks that *mention* the query terms, but the most relevant context for a code question often lies one hop away in the call or import graph. **Graph expansion** takes the top retrieved chunks, walks one hop out along the code graph (to callers, callees, imported files, and sibling symbols), and pulls in those neighbours' chunks as additional, slightly-down-weighted context. This hybrid of vector retrieval and graph traversal is commonly called **GraphRAG** (graph retrieval-augmented generation).

## Large language model (LLM) and litellm

A **large language model** is used — only when the user configures one — to synthesise written answers, explain files, grade interview answers, and narrate changelogs. KnowIT does not talk to any provider's SDK directly; it routes everything through **litellm**, a thin library that exposes one uniform `completion()` call and translates it to whichever provider a model string names (`gpt-4o-mini`, `groq/llama-3.3-70b-versatile`, `ollama/llama3.1`, and so on). This is what makes the multi-provider layer small.

## Snapshot, fingerprint, and delta

For change-tracking, a **snapshot** is the structural state of the repository at a particular commit, captured as a **fingerprint**: a compact dictionary of the files present, the symbols present (each with a hash of its source and its complexity), and the import and call edges. A **delta** is the difference between two fingerprints — which files and symbols were added, removed, or modified, which import edges changed, and how complexity shifted. The **learning delta** intersects that structural delta with the set of things the user has already studied.

## Insight, role, and gap

An **insight** is a derived, repo-wide observation: the entry points (files with a `__main__` block), the hub files (most-connected by imports), the most complex symbols, and the *likely-unused* symbols (defined but never called within the repo). A node's **role** (entry / hub / unused / normal) is used to colour it in the interactive diagrams. A **gap**, in the teaching sense, is a part of the repository the user has not yet explored; the gaps tracker reports both never-explored files and files the user *relies on* (imports from explored files) but has not studied.

## The eval gate

KnowIT ships an **evaluation harness**: a set of natural-language questions, each annotated with the file(s) and keyword(s) a correct retrieval/answer should surface. The harness scores retrieval-hit and keyword-coverage for each question and reports a **gate** — pass if at least 80% of the scored questions pass. This is the objective measure used to know whether the retrieval engine is working.

\newpage

# System Architecture and Data Flow

This chapter gives the bird's-eye view: the layers of the system, the path a request takes through them, the repository's physical layout, and the recurring "graceful degradation" pattern. Subsequent chapters zoom into each box named here.

## The layered architecture

KnowIT is organised into five logical layers. Reading bottom-up:

```
┌──────────────────────────────────────────────────────────────────────┐
│  PRESENTATION  —  app.py (Streamlit): 8 tabs, sidebar, session state   │
├──────────────────────────────────────────────────────────────────────┤
│  FEATURE       —  insights · diagram · teach · track · eval_harness    │
├──────────────────────────────────────────────────────────────────────┤
│  RETRIEVAL/LLM —  index (BM25/Chroma) · retrieval (RRF) · llm · provs  │
├──────────────────────────────────────────────────────────────────────┤
│  KNOWLEDGE     —  parsing · graph · chunking · models                  │
├──────────────────────────────────────────────────────────────────────┤
│  FOUNDATION    —  ingest · config · pipeline (orchestration + cache)   │
└──────────────────────────────────────────────────────────────────────┘
```

- The **Foundation layer** acquires the code (`ingest`), reads settings (`config`), and orchestrates everything (`pipeline`), including the on-disk cache and the multi-repo registry.
- The **Knowledge layer** turns raw files into structure: `parsing` extracts symbols, `graph` assembles the code graph, `chunking` produces retrievable units, and `models` defines the dataclasses they all exchange.
- The **Retrieval/LLM layer** answers questions: `index` holds the BM25 and Chroma retrievers, `retrieval` performs hybrid RRF fusion and graph expansion, and `llm`/`providers` synthesise answers through whichever LLM provider is configured.
- The **Feature layer** builds user-facing knowledge on top of the graph and retriever: `insights` (metrics and observations), `diagram` (Graphviz/pyvis visualisations), `teach` (learning artifacts), `track` (change tracking), and `eval_harness` (quality measurement).
- The **Presentation layer** is the single Streamlit application, which holds the built index in a per-session cache and exposes everything through eight tabs.

## The central object: `RepoIndex`

Everything the application does, it does through one object: a **`RepoIndex`**. Built once per repository (and cached), it bundles the repository metadata, the parsed files, the code graph, the chunks, the lexical and dense retrievers, and the active configuration. Its two important methods are `search(query)` (returns ranked, graph-expanded chunks) and `ask(query)` (search, assemble context, optionally synthesise an answer). Feature modules take a `RepoIndex` as their input. If you understand `RepoIndex`, you understand the system's runtime shape.

## End-to-end data flow

When a user points KnowIT at a repository and asks a question, data flows like this:

```
 source (path or git URL)
        │
        ▼
 [ingest]  clone/locate, walk files, read git commit  ──►  RepoMeta + file list
        │
        ▼
 [parse]   ast (Python) / regex (JS-TS) per file      ──►  list[ParsedFile]
        │                                                   (symbols, imports,
        │                                                    calls, complexity)
        ▼
 [graph]   resolve names → edges                       ──►  CodeGraph
        │
        ▼
 [chunk]   symbol/module/doc units + {node, commit}    ──►  list[Chunk]
        │
        ├──► [index: BM25]   tokenise + score            ─┐
        └──► [index: Chroma] embed + store (optional)    ─┤
                                                          ▼
 question ──► [retrieval]  BM25 ⊕ Chroma via RRF, then graph expansion
                                                          │
                                                          ▼
                                  assembled, cited context
                                                          │
                                        ┌─────────────────┴─────────────────┐
                                        ▼                                   ▼
                              [llm] synthesise answer            (no LLM) return context
                              (only if a provider is set)
```

The same `RepoIndex` — specifically its graph and chunks — also feeds the feature modules: `insights` reads the graph, `diagram` renders neighbourhoods of it, `teach` generates questions from it, and `track` compares two of its fingerprints across commits.

## The repository layout

The codebase is small and flat. Every module has a single clear responsibility:

```
KnowIT/
├── app.py                      Streamlit application (the only entry point)
├── requirements.txt            dependencies (most optional at runtime)
├── .env.example                template for provider keys / settings
├── knowit/                     the library
│   ├── __init__.py
│   ├── config.py               Config dataclass; reads environment / .env
│   ├── models.py               dataclasses: Symbol, ParsedFile, Chunk, RepoMeta, Retrieved
│   ├── ingest.py               locate/clone repo, walk files, read git metadata
│   ├── parsing.py              ast (Python) + regex (JS/TS) → ParsedFile
│   ├── graph.py                CodeGraph + build_graph + structural queries
│   ├── chunking.py             ParsedFile → list[Chunk] with provenance
│   ├── index.py                BM25Retriever + ChromaRetriever
│   ├── retrieval.py            hybrid RRF fusion + graph expansion + context
│   ├── llm.py                  litellm wrapper: synthesize / judge / explain_file
│   ├── providers.py            provider registry + model resolution + test
│   ├── insights.py             repo insights, per-file summaries, API/DB maps
│   ├── diagram.py              Graphviz/Mermaid + interactive explorer functions
│   ├── teach.py                learning path, flashcards, quizzes, interview, gaps
│   ├── track.py                snapshots, fingerprints, diff, deltas
│   ├── pipeline.py             build_index, RepoIndex, disk cache, repo registry
│   └── eval_harness.py         question loading, scoring, the gate
├── eval/
│   └── questions.example.json  sample evaluation questions
├── scripts/
│   ├── run_eval.py             headless eval runner
│   └── make_demo_history.py    generates a git-history repo to demo Track
└── sample_repo/                a tiny ML service used as fixture and demo
```

## The graceful-degradation pattern

The single most important architectural pattern is worth a precise statement, because it appears in five different modules and explains many "why is it written this way" questions.

Each optional capability is wrapped so that **importing the heavy library is attempted lazily, inside a `try/except`, and a fallback is selected at runtime.** The fallbacks are not toys; they are complete, correct, lower-fidelity implementations.

| Capability | Always-available default | Optional accelerator | Selection point |
|---|---|---|---|
| Python parsing | stdlib `ast` | (tree-sitter, future multi-lang) | `parsing.parse_file` |
| Retrieval | built-in **BM25** | **chromadb** semantic, fused via RRF | `pipeline._build_retrievers` |
| Answers / grading | cited context only | **litellm** synthesis | `llm.synthesize` |
| Diagrams | **Graphviz** (static, native) | **pyvis** (interactive, inlined) | `diagram.pyvis_html` |
| Tables in UI | `st.table` | **pandas** dataframes | `app.show_table` |
| Learning artifacts | generated from the graph | richer with an LLM | `teach.*` |

The consequences are profound for both users and developers. A user with no API key and no internet still gets ingestion, parsing, the full code graph, keyword retrieval, all the diagrams, all the insights, and all the learning artifacts. A developer can run the entire test suite — including the evaluation gate — with zero secrets and zero network calls, which is precisely how the system was built and validated. When the heavy libraries *are* present, the very same code paths transparently become semantically richer.

\newpage
# Configuration (`config.py`)

Configuration is centralised in a single immutable-by-convention dataclass, `Config`. There is one process-wide default instance, `CONFIG`, constructed at import time from environment variables (which `python-dotenv` populates from a `.env` file if present). The application constructs its own `Config` instances per build so that UI choices (such as the retrieval backend) feed the cache key cleanly.

## The `Config` dataclass

```python
@dataclass
class Config:
    # --- LLM (optional; resolved from provider + model in providers.py) ---
    llm_provider: str = os.getenv("KNOWIT_LLM_PROVIDER", "")
    llm_model:    str = os.getenv("KNOWIT_LLM_MODEL", "")
    llm_base_url: str = os.getenv("KNOWIT_LLM_BASE_URL", "")
    llm_kwargs:  dict = field(default_factory=dict)   # extra kwargs for litellm (e.g. api_base)
    # --- retrieval ---
    embed_backend:    str = os.getenv("KNOWIT_EMBED_BACKEND", "auto")  # auto|hybrid|bm25|chroma
    data_dir:         str = os.getenv("KNOWIT_DATA_DIR", ".knowit_cache")
    chunk_max_lines:  int = int(os.getenv("KNOWIT_CHUNK_MAX_LINES", "160"))
    top_k:            int = int(os.getenv("KNOWIT_TOP_K", "6"))
    graph_expand:     int = int(os.getenv("KNOWIT_GRAPH_EXPAND", "1"))
    use_cache:       bool = os.getenv("KNOWIT_USE_CACHE", "1") not in ("0", "false", "False")
```

## Field semantics

| Field | Default | Meaning |
|---|---|---|
| `llm_provider` | "" | Provider key (`openai`, `anthropic`, `groq`, `ollama`, `openrouter`, `custom`) or empty for none |
| `llm_model` | "" | The *resolved* litellm model string once a provider and model are chosen |
| `llm_base_url` | "" | Endpoint URL for `ollama`/`custom` providers |
| `llm_kwargs` | {} | Extra keyword arguments threaded into every litellm call, typically `{"api_base": ...}` |
| `embed_backend` | `auto` | Which retrievers to build: `auto`/`hybrid` build BM25+Chroma; `bm25` is lexical only; `chroma` forces semantic |
| `data_dir` | `.knowit_cache` | Root for all on-disk state: cache, snapshots, worktrees, clones, the repo registry |
| `chunk_max_lines` | 160 | A symbol's code is truncated to this many lines in its chunk |
| `top_k` | 6 | How many results retrieval returns before graph expansion |
| `graph_expand` | 1 | Hops of graph expansion (0 disables it) |
| `use_cache` | true | Whether to read/write the on-disk parse/graph/chunk cache |

## Why a dataclass and not a settings framework

The choice of a plain dataclass over a configuration framework (Pydantic Settings, Dynaconf, Hydra) is deliberate and consistent with the dependency-light goal. The configuration surface is small and flat; a dataclass with `os.getenv` defaults is zero-dependency, trivially testable (you can construct a `Config(embed_backend="bm25")` in a test with no environment at all), and easy to serialise. The `llm_kwargs` dict is the one field that is *not* environment-derived; it is filled in at runtime by the provider-resolution step (Chapter 11) and threaded through to litellm so that, for example, Ollama's local endpoint URL reaches the HTTP call.

\newpage

# Data Models (`models.py`)

All inter-module data is exchanged as standard-library `@dataclass` objects. There are no ORMs, no schemas, no serialisation framework — dataclasses pickle cleanly (which the cache relies on) and read clearly. There are five.

## `Symbol`

```python
@dataclass
class Symbol:
    id: str               # "<rel_path>::<qualname>", e.g. "model.py::Detector.predict"
    name: str             # bare name, e.g. "predict"
    qualname: str         # qualified name, e.g. "Detector.predict"
    kind: str             # "function" | "method" | "class"
    file: str             # repo-relative path
    start_line: int
    end_line: int
    docstring: str = ""
    code: str = ""        # the symbol's raw source
    calls: list[str] = field(default_factory=list)   # callee base-names found in the body
    parent: Optional[str] = None                      # enclosing class qualname, for methods
    complexity: int = 0   # cyclomatic-ish score (functions/methods); summed for classes
    bases: list[str] = field(default_factory=list)    # base-class names (for inheritance)
```

A `Symbol` is the richest object in the system. Note that `calls` holds *base names* (`predict`, not a resolved id) — name resolution to actual symbol ids happens later, in the graph builder, where the full repository name index is available. The `code` field is what makes symbol chunks self-contained and what `track` hashes to detect modification.

## `ParsedFile`

```python
@dataclass
class ParsedFile:
    file: str
    language: str        # "python" | "javascript" | "typescript" | "markdown" | "other"
    imports: list[str] = field(default_factory=list)
    symbols: list[Symbol] = field(default_factory=list)
    loc: int = 0
    text: str = ""       # the full source text (used for docstrings, doc chunks, source view)
    error: str = ""      # non-empty if parsing failed (e.g. a SyntaxError message)
```

One `ParsedFile` is produced per source file. The `error` field is how parse failures are made non-fatal: a file that fails to parse still becomes a `ParsedFile` (with an error message and an empty symbol list) rather than crashing the build, and it is surfaced honestly in the UI's parse-error count.

## `Chunk`

```python
@dataclass
class Chunk:
    id: str              # short content hash
    file: str
    kind: str            # "symbol" | "module" | "doc"
    name: str
    start_line: int
    end_line: int
    text: str            # what is embedded / scored
    node_id: str         # the graph node this chunk derives from   ──┐  provenance
    commit: str          # the commit it was taken at                ──┘  (load-bearing)
    symbol_id: Optional[str] = None
```

The two provenance fields, `node_id` and `commit`, are the architectural keystone described in Chapter 2. Because every chunk knows exactly which graph node and which commit it came from, the system can (a) expand retrieval along the graph by looking up a chunk's neighbours' chunks, and (b) compute change deltas across commits without re-deriving anything.

## `RepoMeta` and `Retrieved`

```python
@dataclass
class RepoMeta:
    name: str
    path: str            # absolute path to the working copy
    commit: str          # 40-char SHA, or "working-tree"
    branch: str = ""
    is_git: bool = False
    n_commits: int = 0

@dataclass
class Retrieved:
    chunk: Chunk
    score: float
    via: str             # "lexical" | "semantic" | "both" | "graph"  — how it was found
```

`Retrieved` wraps a chunk with its fused score and a `via` tag recording *how* it surfaced — by keyword match, by semantic similarity, by both, or by graph expansion. The UI uses `via` to label each source so the user can see why a snippet was retrieved, which is itself a small but real teaching aid.

\newpage

# Ingestion (`ingest.py`)

Ingestion is the first stage: it turns a user-supplied *source* (a local path or a git URL) into a concrete working copy on disk, reads its git metadata, and enumerates the files worth parsing.

## Locating or cloning the repository

```python
def clone_or_local(source, data_dir):
    if source.startswith(("http://", "https://", "git@")) or source.endswith(".git"):
        repos = os.path.join(data_dir, "repos"); os.makedirs(repos, exist_ok=True)
        name = source.rstrip("/").split("/")[-1]
        if name.endswith(".git"): name = name[:-4]
        dest = os.path.join(repos, name)
        if not os.path.isdir(dest):
            r = subprocess.run(["git", "clone", "--depth", "200", source, dest], ...)
            if r.returncode != 0:
                raise RuntimeError(f"git clone failed: {r.stderr.strip()[:500]}")
        return os.path.abspath(dest)
    path = os.path.abspath(os.path.expanduser(source))
    if not os.path.isdir(path):
        raise FileNotFoundError(f"Not a directory: {path}")
    return path
```

A URL is shallow-cloned (`--depth 200`, enough history for change-tracking without pulling the entire past) into `data_dir/repos/<name>`, and re-used on subsequent runs if already present. A local path is simply resolved to an absolute path. The function returns the path to a real on-disk directory either way, which is all the rest of the pipeline needs.

## Reading git metadata

```python
def repo_meta(path):
    is_git = os.path.isdir(os.path.join(path, ".git"))
    commit = _git(["rev-parse", "HEAD"], path) if is_git else ""
    branch = _git(["rev-parse", "--abbrev-ref", "HEAD"], path) if is_git else ""
    n      = _git(["rev-list", "--count", "HEAD"], path) if is_git else ""
    return RepoMeta(name=os.path.basename(path.rstrip("/")) or path, path=path,
                    commit=commit or "working-tree", branch=branch, is_git=is_git,
                    n_commits=int(n) if n.isdigit() else 0)
```

`_git` is a small helper that shells out to git with a timeout and returns stdout (or an empty string on any failure). The key design point is that **git is optional**: a directory that is not under version control still ingests fine, with its commit recorded as the sentinel `"working-tree"`. That sentinel later tells the cache layer to fingerprint file modification times instead of trusting a commit hash, and tells the Track feature that history is unavailable.

## Enumerating files

```python
SKIP_DIRS = {".git", ".knowit_cache", "__pycache__", "node_modules", ".venv", "venv",
             "env", "ENV", "build", "dist", ".mypy_cache", ".pytest_cache", ".ruff_cache",
             "site-packages", ".ipynb_checkpoints", ".idea", ".vscode"}
CODE_EXTS = {".py", ".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx"}
DOC_EXTS  = {".md"}

def list_files(path, max_files=8000):
    code, docs = [], []
    for root, dirs, files in os.walk(path):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]   # prune in place
        for f in files:
            ext = os.path.splitext(f)[1].lower()
            rel = os.path.relpath(os.path.join(root, f), path)
            if   ext in CODE_EXTS: code.append((rel, os.path.join(root, f)))
            elif ext in DOC_EXTS:  docs.append((rel, os.path.join(root, f)))
        if len(code) + len(docs) > max_files: break
    return sorted(code), sorted(docs)
```

Two details matter. First, `dirs[:] = [...]` mutates the walk list *in place*, which is the idiomatic way to prune entire subtrees (virtual environments, caches, vendored dependencies) from an `os.walk` cheaply — you never descend into them. Second, code files and documentation files are returned separately, because the parser treats them differently: code files are parsed for structure, while Markdown files become doc chunks for conceptual questions ("what is this project?") without contributing symbols.

\newpage

# Parsing (`parsing.py`)

Parsing converts each source file into a `ParsedFile`: its symbols, their imports, the calls between them, a complexity score, and (for classes) their base classes. KnowIT parses two language families with two strategies.

## Python via the standard-library `ast`

The headline design decision is that **Python is parsed with the standard library's `ast` module, not tree-sitter.** This was a conscious trade-off. tree-sitter is the right long-term choice for multi-language support and remains in the dependency list for that future, but for Python specifically `ast` is zero-dependency, always correct for the running interpreter's syntax, immune to the version-mismatch pitfalls that plague tree-sitter's grammar bindings, and entirely sufficient to extract everything KnowIT needs. Choosing it kept the core testable with no installation step and removed an entire class of first-run failures.

The parser walks the AST and emits a `Symbol` for every `FunctionDef`, `AsyncFunctionDef`, and `ClassDef`, recursing into class bodies to capture methods:

```python
def parse_python(rel_path, source):
    pf = ParsedFile(file=rel_path, language="python", text=source, loc=source.count("\n") + 1)
    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        pf.error = f"SyntaxError: {e}"      # non-fatal: file kept, no symbols
        return pf
    lines = source.splitlines()
    # imports
    for n in ast.walk(tree):
        if   isinstance(n, ast.Import):     pf.imports += [a.name for a in n.names]
        elif isinstance(n, ast.ImportFrom): pf.imports += ([n.module] if n.module else [])
    pf.imports = sorted(set(pf.imports))

    def add_symbol(node, qualprefix, parent):
        qual = f"{qualprefix}{node.name}"
        kind = "class" if isinstance(node, ast.ClassDef) else ("method" if parent else "function")
        code, s, e = _segment(lines, node)
        pf.symbols.append(Symbol(
            id=f"{rel_path}::{qual}", name=node.name, qualname=qual, kind=kind,
            file=rel_path, start_line=s, end_line=e,
            docstring=ast.get_docstring(node) or "", code=code,
            calls=[] if isinstance(node, ast.ClassDef) else _collect_calls(node),
            parent=parent,
            complexity=0 if isinstance(node, ast.ClassDef) else _complexity(node),
            bases=_bases(node) if isinstance(node, ast.ClassDef) else []))
        if isinstance(node, ast.ClassDef):
            for b in node.body:
                if isinstance(b, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    add_symbol(b, qual + ".", parent=qual)
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            add_symbol(node, "", parent=None)
    for cls in [x for x in pf.symbols if x.kind == "class"]:
        cls.complexity = sum(m.complexity for m in pf.symbols if m.parent == cls.qualname) or 1
    return pf
```

### Call extraction

`_collect_calls` walks a function body and records the *base name* of every call site. For a direct call `bar(x)` the name is `bar`; for an attribute call `model.predict(x)` it is the attribute `predict`. This deliberately ignores the receiver, because at parse time the receiver's type is unknown; resolving `predict` to `Detector.predict` happens in the graph builder by matching names across the repository.

```python
def _callee_name(func):
    if isinstance(func, ast.Name):      return func.id      # bar(...)        -> "bar"
    if isinstance(func, ast.Attribute): return func.attr    # model.predict() -> "predict"
    return None
```

### Cyclomatic complexity

Each function or method gets a complexity score approximating cyclomatic complexity: one plus the number of decision points in its body.

```python
def _complexity(node):
    c = 1
    for n in ast.walk(node):
        if isinstance(n, (ast.If, ast.For, ast.AsyncFor, ast.While,
                          ast.ExceptHandler, ast.IfExp, ast.Assert)):     c += 1
        elif isinstance(n, ast.BoolOp):       c += len(n.values) - 1   # each and/or branch
        elif isinstance(n, ast.comprehension): c += 1 + len(n.ifs)      # the loop + its filters
    return c
```

A class's complexity is the sum of its methods' complexities (or 1 if it has none). This single number drives the "most complex symbols" insight, the senior-level quiz questions, and the complexity-change view in change tracking — a good example of one cheap structural signal being reused across several features.

### Inheritance

`_bases` extracts base-class names from a `ClassDef` (`ast.Name` bases like `Base`, and `ast.Attribute` bases like `nn.Module`, recording the final attribute). These names are later resolved to `inherits` edges in the graph if the base class is defined within the repository.

## JavaScript and TypeScript via regular expressions

Multi-language support (Phase 3) added a **best-effort regex parser** for JS/TS. This is explicitly a lighter-fidelity path than `ast`: regular expressions cannot truly parse a programming language, but they can reliably extract the three things KnowIT needs from typical JS/TS — imports, function definitions, and class definitions — well enough to populate the graph and make non-Python files first-class citizens in the file tree, retrieval, and diagrams.

```python
_JS_IMPORT  = re.compile(r"""import\s+(?:[^'"]+\s+from\s+)?['"]([^'"]+)['"]""")
_JS_REQUIRE = re.compile(r"""require\(\s*['"]([^'"]+)['"]\s*\)""")
_JS_CLASS   = re.compile(r"\bclass\s+([A-Za-z_$][\w$]*)(?:\s+extends\s+([A-Za-z_$][\w$.]*))?")
_JS_FUNC    = re.compile(r"\bfunction\s+([A-Za-z_$][\w$]*)\s*\(")
_JS_ARROW   = re.compile(r"\b(?:export\s+)?(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?\([^)]*\)\s*=>")
```

The parser finds classes (capturing an `extends` clause for inheritance), `function` declarations, and arrow-function constants, recording each as a `Symbol` with a small surrounding code excerpt. Call-graph extraction is not attempted for JS/TS — the regex approach cannot do it reliably — so JS/TS symbols appear in the graph with `contains` and `inherits` edges but not `calls`. This is an honest, documented limitation, and exactly the kind of thing tree-sitter would later improve.

## Dispatch

```python
def parse_file(rel_path, abs_path):
    ext = os.path.splitext(rel_path)[1].lower()
    src = _read(abs_path)
    if ext == ".py":          return parse_python(rel_path, src)
    if ext in JS_EXTS:        return parse_js(rel_path, src, "javascript")
    if ext in TS_EXTS:        return parse_js(rel_path, src, "typescript")
    lang = "markdown" if ext == ".md" else "other"
    return ParsedFile(file=rel_path, language=lang, text=src, loc=src.count("\n") + 1)
```

The dispatcher is the single place new languages plug in. Adding a language means adding an extractor and a branch here; the rest of the system consumes `ParsedFile` uniformly regardless of source language.

\newpage
# The Code Graph (`graph.py`)

The code graph is the structural heart of KnowIT. This chapter explains the data structure, how it is built (especially the *name resolution* that turns un-typed call names into real edges), and the queries the rest of the system runs against it.

## The `CodeGraph` data structure

The graph is a small, pure-Python directed multigraph — no `networkx`, no graph database. The decision to hand-roll it follows the dependency-light goal: the operations KnowIT needs (add node, add edge, successors/predecessors by edge type, neighbours) are a few dozen lines, fully testable, and trivially picklable for the cache.

```python
class CodeGraph:
    def __init__(self):
        self.nodes = {}                 # id -> {"type": "file"|"symbol", "data": {...}}
        self._out  = defaultdict(list)  # id -> [(dst, etype), ...]
        self._in   = defaultdict(list)  # id -> [(src, etype), ...]

    def add_node(self, nid, ntype, data=None):
        if nid not in self.nodes:
            self.nodes[nid] = {"type": ntype, "data": data or {}}
        return nid

    def add_edge(self, src, dst, etype):
        if src in self.nodes and dst in self.nodes:
            self._out[src].append((dst, etype))
            self._in[dst].append((src, etype))

    def successors(self, nid, etype=None):
        return [d for d, t in self._out.get(nid, []) if etype is None or t == etype]

    def predecessors(self, nid, etype=None):
        return [s for s, t in self._in.get(nid, []) if etype is None or t == etype]

    def callees(self, sym_id):  return self.successors(sym_id, "calls")
    def callers(self, sym_id):  return self.predecessors(sym_id, "calls")

    def all_edges(self, etype=None):
        return [(s, d, t) for s, lst in self._out.items()
                for d, t in lst if etype is None or t == etype]
```

Adjacency is stored twice — outgoing in `_out`, incoming in `_in` — so that both "what does this call?" (`successors`/`callees`) and "what calls this?" (`predecessors`/`callers`) are O(degree) without scanning the whole graph. The `all_edges` accessor (added for change-tracking) yields every edge as a `(src, dst, type)` triple and is used by the diagram and track modules.

## Building the graph

`build_graph` consumes the list of `ParsedFile`s and runs in three passes.

### Pass 1 — nodes and the name index

```python
for pf in parsed_files:
    g.add_node(pf.file, "file", {"language": pf.language, "loc": pf.loc,
                                 "imports": pf.imports, "error": pf.error})
    if pf.file.endswith(".py"):
        mod_key = pf.file[:-3].replace(os.sep, ".").replace("/", ".")
        module_index[mod_key] = pf.file                  # "pkg.mod" -> "pkg/mod.py"
        module_index[mod_key.split(".")[-1]] = pf.file   # bare "mod" -> file too
    for sym in pf.symbols:
        g.add_node(sym.id, "symbol", {... "complexity": sym.complexity, "bases": sym.bases})
        g.add_edge(pf.file, sym.id, "contains")
        name_index[sym.name].append(sym.id)              # base name -> [symbol ids]
```

Two indices are built alongside the nodes: a **name index** mapping each bare symbol name to the list of symbol ids that share it, and a **module index** mapping importable module paths to files. These power the resolution in the next passes.

### Pass 2 — `method_of` and `calls` edges

```python
for pf in parsed_files:
    for sym in pf.symbols:
        if sym.parent:                                   # a method
            parent_id = f"{pf.file}::{sym.parent}"
            if parent_id in g.nodes: g.add_edge(sym.id, parent_id, "method_of")
        for callee in sym.calls:                         # un-typed call names
            for target in name_index.get(callee, []):    # resolve by name
                if target != sym.id: g.add_edge(sym.id, target, "calls")
        for base in sym.bases:                            # inheritance
            for target in name_index.get(base, []):
                tn = g.get(target)
                if target != sym.id and tn and tn["data"].get("kind") == "class":
                    g.add_edge(sym.id, target, "inherits")
```

This is where the parser's deliberately-unresolved call names become real edges. Recall that the parser recorded `predict` as a call name without knowing the receiver's type. Here, `predict` is looked up in the name index; if exactly one symbol named `predict` exists, the call edge is unambiguous; if several exist, an edge is drawn to each. This **name-based resolution** is a heuristic — it can over-connect when two unrelated functions share a name — but in practice it is accurate enough for the graph's purposes (retrieval expansion, call-flow diagrams, "what calls X"), and it is cheap and language-agnostic. A precise, type-aware call graph would require full semantic analysis (or a language server), which is out of scope for the current phases and would violate the dependency-light constraint.

### Pass 3 — `imports` edges

```python
for pf in parsed_files:
    for imp in pf.imports:
        dst = module_index.get(imp) or module_index.get(imp.split(".")[-1])
        if dst and dst != pf.file: g.add_edge(pf.file, dst, "imports")
```

Each import string is resolved against the module index to an internal file, when possible. Imports of third-party libraries (`numpy`, `torch`) simply do not resolve and produce no edge — the import graph is intentionally *internal*, showing how the repository's own files depend on each other, which is what the architecture diagram needs.

## Statistics and queries

`stats()` returns node and edge counts broken down by type — the numbers shown on the Overview tab. The rest of the system queries the graph through `successors`, `predecessors`, `callees`, `callers`, `neighbors`, and `all_edges`. Crucially, no feature module ever re-parses the code: once the graph exists, "what calls `run_inference`?", "what does `model.py` import?", and "what is the inheritance hierarchy?" are all simple graph lookups.

\newpage

# Chunking (`chunking.py`)

Chunking decides what units of text the retrieval index sees. The quality of retrieval depends heavily on chunk granularity: too coarse (a whole file) and a hit drowns the relevant lines in noise; too fine (a single line) and context is lost. KnowIT chunks at the level of *symbols*, with two supporting chunk types.

## The three chunk kinds

For each parsed code file, chunking emits:

1. A **module chunk** — a compact per-file summary: the file path, its imports, and the names of the symbols it defines. This is what answers file-level and "where is X" questions.
2. A **symbol chunk** per function/class/method — the symbol's qualname and kind, its docstring, and its (possibly truncated) source code. This is the workhorse: most useful retrievals are symbol chunks.

For Markdown files, chunking emits a **doc chunk** containing the document text, so conceptual questions can be answered from prose.

```python
def make_chunks(parsed_files, commit, max_lines=160):
    chunks = []
    for pf in parsed_files:
        if pf.language in ("python", "javascript", "typescript"):
            header = (f"FILE {pf.file} ({pf.language})\n"
                      f"imports: {', '.join(pf.imports) or 'none'}\n"
                      f"defines: {', '.join(s.qualname for s in pf.symbols) or '(none)'}")
            chunks.append(Chunk(id=_hash(pf.file, "module"), file=pf.file, kind="module",
                                name=pf.file, start_line=1, end_line=pf.loc, text=header,
                                node_id=pf.file, commit=commit))
            for s in pf.symbols:
                text = (f"{pf.file} :: {s.qualname}  [{s.kind}]\n{s.docstring}\n"
                        f"{_truncate(s.code, max_lines)}").strip()
                chunks.append(Chunk(id=_hash(s.id), file=pf.file, kind="symbol",
                                    name=s.qualname, start_line=s.start_line,
                                    end_line=s.end_line, text=text,
                                    node_id=s.id, commit=commit, symbol_id=s.id))
        elif pf.text.strip():
            chunks.append(Chunk(id=_hash(pf.file, "doc"), file=pf.file, kind="doc",
                                name=pf.file, start_line=1, end_line=pf.loc,
                                text=_truncate(pf.text, max_lines * 2),
                                node_id=pf.file, commit=commit))
    return chunks
```

## Provenance and identity

Two things deserve emphasis. First, **every chunk's `node_id` points at a real graph node** — a symbol chunk's `node_id` is the symbol's id, a module/doc chunk's `node_id` is the file path. This is precisely what lets retrieval expand along the graph: given a retrieved chunk, the system looks up its `node_id`, finds that node's neighbours in the graph, and pulls in *their* chunks via a `chunks_by_node` index. Second, each chunk's `id` is a short SHA-1 of its identity, which makes chunk ids **stable across rebuilds** as long as the code is unchanged — important for the Chroma retriever, which reuses a persisted collection when the chunk ids match.

## Why symbol-level

Chunking at the symbol level (rather than fixed-size windows) means a retrieved unit is a *semantically complete* thing — a whole function with its docstring — which produces far better LLM answers and far more useful "sources" in the UI than an arbitrary 500-character slice would. It also aligns the retrieval unit with the graph node, which is what makes graph expansion and provenance coherent. The `chunk_max_lines` truncation caps very long functions so a single giant symbol cannot dominate a chunk's token budget.

\newpage
# Indexing and Retrieval (`index.py`, `retrieval.py`)

This is the chapter to read if you read only one in Part II. Retrieval is what turns "a pile of chunks" into "the right answer to a question," and KnowIT's retrieval is a hybrid of two methods fused by rank, then expanded along the graph. Each piece is explained with its algorithm.

## The lexical retriever: BM25

BM25 (Best Matching 25) is the always-available default. It ranks a chunk by how well its words match the query, with two refinements that make it far better than naive word-counting: rare words count for more, and long documents are penalised so they cannot win simply by being long.

### Tokenisation and stemming

Before scoring, both chunks and queries are tokenised. Code identifiers are the interesting case: `run_inference`, `runInference`, and `RunInference` should all match a query word "inference." The tokeniser therefore splits on non-alphanumeric characters, then splits each token on camelCase boundaries, lowercases, and applies a light suffix-stripping stemmer so that `preprocessing`, `preprocessed`, and `preprocess` collapse to one term.

```python
_WORD  = re.compile(r"[A-Za-z0-9]+")
_CAMEL = re.compile(r"[A-Z]+(?=[A-Z][a-z])|[A-Z][a-z]+|[a-z]+|[A-Z]+|\d+")

def _stem(t):
    if len(t) > 4 and t.endswith("ing"): return t[:-3]
    if len(t) > 4 and t.endswith("ed"):  return t[:-2]
    if len(t) > 4 and t.endswith("es"):  return t[:-2]
    if len(t) > 3 and t.endswith("s") and not t.endswith("ss"): return t[:-1]
    if len(t) > 4 and t.endswith("ly"):  return t[:-2]
    return t

def tokenize(text):
    toks = []
    for raw in _WORD.findall(text or ""):
        for p in (_CAMEL.findall(raw) or [raw]):
            p = p.lower()
            if len(p) >= 2: toks.append(_stem(p))
    return toks
```

The stemmer is deliberately conservative and applied *symmetrically* to documents and queries, so that whatever transformation a query word undergoes, the same transformation has been applied to the indexed terms. This single addition measurably improved retrieval on paraphrase-style questions during development.

### The BM25 scoring function

Let a query be a set of terms. For a term *t* and a chunk (document) *d*, BM25 scores:

```
                                  f(t,d) · (k1 + 1)
  score(t, d) = IDF(t) · ─────────────────────────────────────────
                          f(t,d) + k1 · (1 − b + b · |d| / avgdl)
```

where:

- `f(t,d)` is the term frequency: how many times *t* appears in *d*.
- `|d|` is the document length in tokens; `avgdl` is the average document length across the corpus.
- `k1 = 1.5` controls term-frequency saturation (so the tenth occurrence of a word adds little over the second).
- `b = 0.75` controls length normalisation (how strongly long documents are penalised).
- `IDF(t)` is the inverse document frequency, computed as

```
  IDF(t) = ln( 1 + (N − n(t) + 0.5) / (n(t) + 0.5) )
```

with `N` the number of chunks and `n(t)` the number of chunks containing *t*. A chunk's total score for a query is the sum of `score(t, d)` over the query's terms. The implementation precomputes IDF and average length at index time, so each query is a single linear scan:

```python
def search(self, query, k=6):
    q = tokenize(query); scored = []
    for i, d in enumerate(self.docs):
        if not d: continue
        tf = Counter(d); dl = len(d); s = 0.0
        for t in q:
            f = tf.get(t)
            if not f: continue
            s += self.idf.get(t, 0.0) * (f * (self.k1 + 1)) / (
                 f + self.k1 * (1 - self.b + self.b * dl / (self.avgdl or 1)))
        if s > 0: scored.append((i, s))
    scored.sort(key=lambda x: x[1], reverse=True)
    return [(self.chunks[i], float(s)) for i, s in scored[:k]]
```

BM25 is strong on exact identifiers and terminology, weak on paraphrase. That weakness is exactly what the semantic retriever covers.

## The semantic retriever: Chroma

When `chromadb` is installed, KnowIT also builds a dense retriever. Chroma is an embedded vector database; its default embedding function runs a small model on-device (no API key, no network after the one-time model download), so semantic search stays consistent with the local-first goal.

```python
class ChromaRetriever:
    def __init__(self, data_dir, sig="default"):
        import chromadb
        self.client = chromadb.PersistentClient(path=os.path.join(data_dir, "chroma"))
        self.coll = f"knowit_{sig}"
        self.col = self.client.get_or_create_collection(self.coll)
    def index(self, chunks):
        self.by_id = {c.id: c for c in chunks}
        if len(chunks) and self.col.count() == len(chunks):
            return                       # already embedded & persisted -> reuse
        ... delete + re-add documents in batches ...
    def search(self, query, k=6):
        res = self.col.query(query_texts=[query], n_results=k)
        return [(self.by_id[cid], 1.0 / (1.0 + float(dist)))
                for cid, dist in zip(res["ids"][0], res["distances"][0])
                if cid in self.by_id]
```

Two performance details: the collection is named by the build *signature* (`knowit_<sig>`) so that an unchanged repository reuses its already-embedded collection across launches rather than re-embedding (the `count() == len(chunks)` short-circuit); and distances are converted to a `1/(1+distance)` similarity so they can be ranked alongside BM25 scores. Because the retrievers are *fused by rank* rather than by raw score (next section), the exact scale of these numbers does not matter — only their order does.

## Fusing the two: Reciprocal Rank Fusion

KnowIT does not pick one retriever; it runs both and fuses their ranked lists with **Reciprocal Rank Fusion (RRF)**. RRF is the right tool precisely because BM25 scores and embedding similarities are *incomparable* — they live on different scales. RRF ignores the scores and combines *ranks*. A chunk that appears at rank *r* in a list contributes `1 / (k + r)` to its fused score, summed over every list it appears in:

```
  RRF(chunk) = Σ   1 / (k_const + rank_in_list)
             lists
```

with `k_const = 60` (a standard, robust default) and rank counted from 1. A chunk that ranks well in *both* lists accumulates the most; a chunk that only one method found still contributes. The implementation also records *which* lists found each chunk, producing the `via` tag (`lexical`, `semantic`, or `both`):

```python
def _rrf(rank_lists, kconst=60):
    scores, sources, by_id = {}, {}, {}
    for name, hits in rank_lists:                 # ("lexical", [...]) , ("semantic", [...])
        for rank, (chunk, _s) in enumerate(hits):
            scores[chunk.id] = scores.get(chunk.id, 0.0) + 1.0 / (kconst + rank + 1)
            sources.setdefault(chunk.id, set()).add(name)
            by_id[chunk.id] = chunk
    return scores, sources, by_id
```

When only BM25 is available (Chroma not installed), the fusion degenerates gracefully to "BM25 alone," so the same code path serves both the lean and the full configurations.

## Graph expansion

After fusion, KnowIT performs one hop of **graph expansion**. The top fused chunks are taken, and for each, the code graph is consulted for its neighbours — the symbols it calls, the symbols that call it, the file's contained symbols, and the files it imports. Those neighbours' chunks are pulled into the result set with a down-weighted score and a `via = "graph"` tag (or a small boost if they were already present). This is the "GraphRAG" step, and it is what lets KnowIT answer a question like "how does inference flow?" with the *whole call chain* — `run_inference → load_image → preprocess → predict → postprocess` — even though a plain text search would only have matched the one function whose docstring says "inference."

```python
def hybrid_search(query, lexical, dense, graph, chunks_by_node, k=6, expand=1):
    lists = [("lexical", lexical.search(query, max(k * 2, 10)))]
    if dense is not None:
        try: lists.append(("semantic", dense.search(query, max(k * 2, 10))))
        except Exception: pass
    scores, sources, by_id = _rrf(lists)
    results = {cid: Retrieved(by_id[cid], sc,
                              "both" if len(sources[cid]) > 1 else next(iter(sources[cid])))
               for cid, sc in scores.items()}
    if expand and graph is not None and results:
        top = sorted(results.values(), key=lambda r: r.score, reverse=True)[:k]
        maxs = top[0].score if top else 1.0
        for r in top:
            for nb in (graph.successors(r.chunk.node_id, "calls")
                       + graph.predecessors(r.chunk.node_id, "calls")
                       + graph.successors(r.chunk.node_id, "contains")
                       + graph.successors(r.chunk.node_id, "imports")):
                for ch in chunks_by_node.get(nb, []):
                    if ch.id not in results:
                        results[ch.id] = Retrieved(ch, maxs * 0.3, "graph")
                    else:
                        results[ch.id].score += maxs * 0.05
    return sorted(results.values(), key=lambda r: r.score, reverse=True)[: k + (k // 2 if expand else 0)]
```

## Context assembly

Finally, the ranked `Retrieved` objects are assembled into a single text *context* for the LLM (or for direct display). Each block is headed by a citation — `[file:start-end :: name]` — so that whether an LLM uses it or the user reads it raw, the source is explicit. Assembly respects a character budget so the context cannot overflow a model's input window:

```python
def assemble_context(retrieved, max_blocks=8, max_chars=6000):
    blocks, total = [], 0
    for r in retrieved[:max_blocks]:
        c = r.chunk
        block = f"[{c.file}:{c.start_line}-{c.end_line} :: {c.name}]\n{c.text}"
        if total + len(block) > max_chars: break
        blocks.append(block); total += len(block)
    return "\n\n".join(blocks)
```

The result is a compact, citation-rich bundle of the most relevant code for a question — the input to the LLM layer, or, when no LLM is configured, the answer shown directly to the user.

\newpage
# The LLM Layer (`llm.py`, `providers.py`)

KnowIT uses a large language model for exactly four jobs — synthesising answers, explaining files, grading interview answers, and narrating changelogs — and **only when the user has configured one**. This chapter explains the thin abstraction over litellm and the provider registry that makes "use Groq" or "use a local Ollama model" a one-line choice.

## Everything goes through litellm

KnowIT never imports a provider's SDK directly. Instead it calls **litellm**, whose `completion()` function takes a model *string* and routes to the right provider. `gpt-4o-mini` goes to OpenAI; `anthropic/claude-3-5-sonnet-latest` to Anthropic; `groq/llama-3.3-70b-versatile` to Groq; `ollama/llama3.1` to a local Ollama server; `openrouter/...` to OpenRouter. This is the single design decision that makes the multi-provider layer small: there is no per-provider client code, only a mapping from a friendly choice to a litellm model string plus, for local/custom endpoints, an `api_base`.

The core helper centralises the call and threads through any extra kwargs (such as `api_base`):

```python
def _complete(model, messages, extra=None, **kw):
    import litellm
    return litellm.completion(model=model, messages=messages, **(extra or {}), **kw)
```

The import is *inside* the function, not at module top — so a system with no litellm installed imports `llm.py` fine and only fails (gracefully, caught) if it actually tries to call a model.

## Graceful synthesis

`synthesize` is the answer generator. Its contract is the embodiment of graceful degradation: given no model, it returns `(None, False)` — the caller then shows the retrieved context directly. Given a model, it calls litellm with a strict grounding system prompt and returns the answer; on *any* error (missing key, network failure, bad model name) it returns a readable error string and `False`, never raising.

```python
SYSTEM = ("You are KnowIT, a codebase explainer. Answer the question USING ONLY the "
          "provided code context. Ground every claim in the snippets and cite sources "
          "inline as (path:line). ... If the answer is not present in the context, say "
          "exactly what is missing rather than guessing. Be concise.")

def synthesize(question, context, model, extra=None):
    if not model: return (None, False)
    try:
        r = _complete(model, [{"role": "system", "content": SYSTEM},
                              {"role": "user", "content": f"Question: {question}\n\n"
                                                          f"Code context:\n{context}"}],
                      extra=extra, temperature=0.1, timeout=60)
        return (r["choices"][0]["message"]["content"].strip(), True)
    except Exception as e:
        return (f"[LLM unavailable: {type(e).__name__}: {e}]", False)
```

The system prompt is doing real work: it forbids ungrounded claims, mandates `(path:line)` citations, and instructs the model to *say what is missing* rather than hallucinate — which, combined with the citation-rich context, keeps answers tethered to the actual code. `explain_file` and `judge` (the interview grader) and `narrate_llm` (the changelog narrator) follow the identical pattern: optional, low-temperature, fully guarded.

## The provider registry

`providers.py` is a declarative table. Each provider entry says how to turn a bare model name into a litellm string (its `prefix`), which environment variable holds its key, whether it needs a base URL, and a few example models:

```python
PROVIDERS = {
  "openai":     {"label": "OpenAI",    "key_env": "OPENAI_API_KEY",  "prefix": "",
                 "models": ["gpt-4o-mini", "gpt-4o"]},
  "anthropic":  {"label": "Anthropic", "key_env": "ANTHROPIC_API_KEY","prefix": "anthropic/",
                 "models": ["claude-3-5-haiku-latest", "claude-3-5-sonnet-latest"]},
  "groq":       {"label": "Groq",      "key_env": "GROQ_API_KEY",    "prefix": "groq/",
                 "models": ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"]},
  "ollama":     {"label": "Ollama (local)", "key_env": "", "prefix": "ollama/", "base_url": True,
                 "default_base": "http://localhost:11434", "models": ["llama3.1", "qwen2.5-coder:7b"]},
  "openrouter": {"label": "OpenRouter","key_env": "OPENROUTER_API_KEY","prefix": "openrouter/", ...},
  "custom":     {"label": "Custom (OpenAI-compatible)", "key_env": "OPENAI_API_KEY",
                 "prefix": "openai/", "base_url": True, "default_base": "http://localhost:8000/v1"},
}
```

### Resolution

`resolve(provider, model, base_url)` turns a UI choice into the pair litellm needs:

```python
def resolve(provider, model, base_url=""):
    if not model:    return ("", {})
    if not provider: return (model, {})        # treat as a raw litellm string
    p = PROVIDERS[provider]
    full = p["prefix"] + model                 # "groq/" + "llama-3.3-70b-versatile"
    extra = {}
    if p.get("base_url"):
        bu = base_url or p.get("default_base", "")
        if bu: extra["api_base"] = bu          # ollama / custom endpoints
    return (full, extra)
```

So choosing Groq + `llama-3.3-70b-versatile` yields `("groq/llama-3.3-70b-versatile", {})`; choosing Ollama + `llama3.1` yields `("ollama/llama3.1", {"api_base": "http://localhost:11434"})`. The returned `extra` dict is exactly what gets stored in `Config.llm_kwargs` and threaded through `_complete`.

### Availability and connection test

Two small helpers complete the layer. `key_present(provider)` checks whether the provider's key is in the environment (used to warn the user in the sidebar). `test_connection(full_model, extra)` makes a tiny real round-trip ("reply with: ok") to verify that the provider, model, and key all work — the "Test connection" button — returning `(ok, message)` and, again, never raising.

## Why this shape

The layer is perhaps fifty lines of substance, yet it supports six provider families plus arbitrary OpenAI-compatible endpoints, local and remote, with a connection test and graceful failure throughout. That economy comes entirely from (a) delegating transport to litellm and (b) modelling providers as data rather than code. Adding a seventh provider is a dictionary entry, not a class.

\newpage

# Pipeline, Caching, and Multi-Repo (`pipeline.py`)

`pipeline.py` is the conductor. It defines `build_index` (the function that runs the whole foundation-and-knowledge pipeline and returns a `RepoIndex`), the `RepoIndex` class itself, the on-disk cache that makes relaunches instant, and the multi-repository registry.

## `RepoIndex`

`RepoIndex` is the runtime object every feature consumes. It holds the metadata, parsed files, graph, chunks, the two retrievers, and the config; it precomputes a `chunks_by_node` index (used by graph expansion); and it exposes `stats()`, `search()`, and `ask()`.

```python
class RepoIndex:
    def __init__(self, meta, parsed_files, graph, chunks, lexical, dense, config):
        self.meta, self.parsed_files, self.graph = meta, parsed_files, graph
        self.chunks, self.lexical, self.dense, self.config = chunks, lexical, dense, config
        self.chunks_by_id = {c.id: c for c in chunks}
        self.chunks_by_node = defaultdict(list)
        for c in chunks: self.chunks_by_node[c.node_id].append(c)

    def search(self, query):
        return hybrid_search(query, self.lexical, self.dense, self.graph,
                             self.chunks_by_node, k=self.config.top_k,
                             expand=self.config.graph_expand)

    def ask(self, query):
        retrieved = self.search(query)
        context = assemble_context(retrieved)
        answer, used = synthesize(query, context, self.config.llm_model, self.config.llm_kwargs)
        return {"question": query, "answer": answer, "used_llm": used,
                "retrieved": retrieved, "context": context}
```

`ask` is the complete question-answering path in seven lines: search, assemble, synthesise (or not), return everything (answer, whether an LLM was used, the retrieved sources, and the raw context) so the UI can render appropriately.

## `build_index`

`build_index` runs the pipeline end to end, with the cache check in the middle:

```python
def build_index(source, config=CONFIG, progress=None, use_cache=None, register=True):
    meta, code_files, doc_files = ingest(source, config.data_dir)
    files = code_files + doc_files
    sig = _signature(meta, files)                        # cache key
    cache = _cache_file(config.data_dir, meta, sig)
    parsed = graph = chunks = None
    if use_cache and os.path.exists(cache):
        parsed, graph, chunks = pickle.load(open(cache, "rb"))   # fast path
    if parsed is None:
        parsed = [parse_file(rel, ab) for rel, ab in files]      # slow path
        graph  = build_graph(parsed)
        chunks = make_chunks(parsed, meta.commit, config.chunk_max_lines)
        if use_cache: pickle.dump((parsed, graph, chunks), open(cache, "wb"))
    lexical, dense = _build_retrievers(chunks, config.embed_backend, config.data_dir, sig)
    if register: record_repo(config.data_dir, source, meta)
    return RepoIndex(meta, parsed, graph, chunks, lexical, dense, config)
```

The expensive work — parsing, graph building, chunking — is what gets cached; retrievers are rebuilt from the (cheap to re-load) chunks, with the Chroma collection itself persisting separately. The `register` flag exists so that the change-tracking feature, which builds throw-away indexes of historical commits, does not pollute the recent-repositories list with temporary worktree paths.

## The cache signature

The cache key must change exactly when the code changes. For a committed state, the commit hash alone suffices. For an uncommitted working tree (`commit == "working-tree"`), the signature additionally folds in each file's modification time and size, so editing a file invalidates the cache:

```python
def _signature(meta, files):
    h = hashlib.sha1(); h.update((meta.commit or "").encode())
    if meta.commit == "working-tree":
        for rel, ab in sorted(files):
            st = os.stat(ab)
            h.update(f"{rel}:{int(st.st_mtime)}:{st.st_size}".encode())
    return h.hexdigest()[:16]
```

The result is a 16-hex-character signature; the cache file is `data_dir/cache/<repo-name>_<sig>.pkl`. This is why a second launch on an unchanged repository loads in well under a second — the entire parse/graph/chunk product is read straight from the pickle.

## Building the retrievers

```python
def _build_retrievers(chunks, backend, data_dir, sig):
    lexical = BM25Retriever(); lexical.index(chunks)          # always
    dense = None
    if backend in ("auto", "hybrid", "chroma"):
        try:
            dense = ChromaRetriever(data_dir, sig); dense.index(chunks)
        except Exception:
            if backend == "chroma": raise                    # explicit request -> surface error
            dense = None                                     # auto/hybrid -> silently fall back
    return lexical, dense
```

This is the graceful-degradation selection point for retrieval, stated in code. BM25 is always built. The dense retriever is attempted for `auto`, `hybrid`, and `chroma`; if Chroma is not installed, `auto`/`hybrid` silently proceed with BM25 only, while an explicit `chroma` request surfaces the error so the user knows their choice could not be honoured.

## The multi-repository registry

Finally, `pipeline.py` maintains a tiny JSON registry of recently indexed repositories (`data_dir/repos.json`), updated on every build (unless `register=False`). The sidebar reads it to offer a "recent repos" switcher. Combined with the on-disk cache, switching between several repositories is near-instant after the first index of each — the foundation of KnowIT's multi-repo support.

```python
def record_repo(data_dir, source, meta):
    f = os.path.join(data_dir, "repos.json")
    reg = json.load(open(f)) if os.path.exists(f) else []
    reg = [e for e in reg if e.get("source") != source]
    reg.insert(0, {"source": source, "name": meta.name, "commit": meta.commit[:12]})
    json.dump(reg[:20], open(f, "w"), indent=2)
```

\newpage
# Insights (`insights.py`)

The insights module computes the repo-wide observations and per-file summaries shown on the Overview and Files tabs, plus the API and database maps. Everything here is a pure function of the already-built graph and parsed files — no LLM, no extra parsing — which is why these views are instant and always available.

## Repo insights

`repo_insights(idx)` returns a dictionary of derived facts:

- **Entry points** — files containing a `__main__` block (detected by scanning the file text for `"__main__"`). These are where execution begins.
- **Hub files** — files ranked by import degree (incoming + outgoing import edges). A file that many others import, or that imports many others, is structurally central; hubs are where understanding pays off most.
- **Most complex symbols** — symbols sorted by the cyclomatic complexity computed during parsing.
- **Likely-unused symbols** — functions/methods with *no callers in the graph*, excluding dunder methods (`__init__` and friends) and symbols defined in entry-point files (whose top-level functions are typically invoked from the `__main__` block, which the name-based call graph does not capture). This heuristic surfaces genuinely dead code — in the sample repository it correctly flags a `cross_entropy` that is defined but never used.

```python
dead = []
for nid, n in g.nodes.items():
    if n["type"] != "symbol": continue
    d = n["data"]
    if d["kind"] == "class" or d["file"] in entry_set: continue
    if d["name"].startswith("__") and d["name"].endswith("__"): continue
    if not g.callers(nid): dead.append({"symbol": d["qualname"], "file": d["file"]})
```

It also returns total lines of code, average complexity per function, and the counts used as headline metrics.

## Per-file summary

`file_summary(idx, file)` produces the per-file explanation: the module docstring as the file's "purpose" (extracted with `ast.get_docstring`), the internal files it depends on and the files that depend on it (both read straight from the import edges), the symbols it defines (with kinds and complexities), and its **public API** — the symbols in this file that are called from *other* files. The public-API computation is a nice illustration of the graph paying off: for each symbol, look at its callers; keep those whose file differs from this one.

```python
api = []
for s in pf.symbols:
    ext = sorted({g.get(c)["data"]["file"] for c in g.callers(s.id)
                  if g.get(c) and g.get(c)["data"].get("file") != file_rel})
    if ext: api.append({"symbol": s.qualname, "used_by": ext})
```

## API and database maps

Two lightweight detectors round out the module, both regex-based over file text:

- `api_map(idx)` finds web routes by matching decorator patterns like `@app.get("/path")`, `@router.post("/path")`, and Flask's `@app.route("/path")`, returning a list of `{method, path, file}`. It covers the common FastAPI/Flask/Express idioms; repositories that register routes some other way simply produce no entries.
- `db_map(idx)` finds ORM models two ways: classes whose base classes include a known ORM base (`Base`, `Model`, `DeclarativeBase`, `SQLModel`), read from the graph's recorded `bases`; and `__tablename__` assignments, matched by regex. It returns `{model, file, table}`.

`language_breakdown(idx)` aggregates files, lines, and symbol counts per language for the Overview tab. These detectors are intentionally heuristic — they trade completeness for zero configuration and zero dependencies, and they degrade to "nothing detected" rather than to errors.

\newpage

# Diagrams (`diagram.py`)

Diagrams are how KnowIT makes structure *visible*. This module went through a significant evolution: it began as static Graphviz pictures, and was rebuilt into an interactive explorer after the static diagrams proved too inert to actually teach anything. This chapter covers both the rendering strategy (and the hard-won lesson behind it) and the interactive explorer.

## The rendering lesson: why native Graphviz, then inlined pyvis

The first diagrams were generated as **Mermaid** and rendered by loading the Mermaid JavaScript library from a CDN inside a Streamlit `components.html` iframe. This failed in practice: the ES-module import did not reliably execute against the injected DOM, and the diagram frequently rendered blank. The fix was to abandon CDN-loaded JavaScript for the default renderer and use **Streamlit's native `st.graphviz_chart`**, which renders DOT server-side with no external assets and is completely reliable.

That experience set a firm rule for the later interactive upgrade: **no CDN dependencies.** When a draggable, zoomable canvas was added, it was built on **pyvis** configured with `cdn_resources="in_line"`, which *inlines* the vis-network JavaScript into the generated HTML rather than fetching it from a CDN. So the interactive canvas is self-contained, and — crucially — if pyvis is not installed at all, the explorer falls back to the reliable native Graphviz renderer. Interactivity never comes at the cost of reliability.

## Diagram generators

The module emits several diagram types as Graphviz DOT (rendered natively) and a Mermaid variant for export:

- `architecture_dot` — the file dependency graph: file nodes grouped into directory clusters, import edges between them.
- `class_dot` — a UML-ish class diagram: each class as a record node listing its methods, with `inherits` edges drawn as open arrows.
- `callflow_dot` — the downstream call flow from a chosen symbol (a breadth-first walk over `calls` edges), approximating a sequence/data-flow view.
- `knowledge_dot` — a compact knowledge graph of files (as folders) and the symbols they contain, with call edges between symbols.

Each is a deterministic string-building function over the graph; for example, the architecture diagram quotes file paths as DOT node ids (so special characters are safe) and labels each file with its symbol count.

## The interactive explorer

The explorer is the centrepiece of the diagrams upgrade. Rather than one frozen picture, it lets the user *navigate*: focus a node, expand the neighbourhood, filter relationships, hover for detail, and click through to adjacent nodes. It rests on a handful of functions.

### Neighbourhood extraction

`neighborhood(idx, focus, depth, etypes)` returns the set of nodes and edges within *depth* hops of a focus node, restricted to the chosen edge types. This is the data both renderers draw.

```python
def neighborhood(idx, focus, depth=1, etypes=_EDGE_TYPES):
    g = idx.graph
    nodes, frontier = {focus}, {focus}
    for _ in range(max(1, depth)):
        nxt = set()
        for n in list(frontier):
            for d, t in g._out.get(n, []):
                if t in etypes: nxt.add(d)
            for s, t in g._in.get(n, []):
                if t in etypes: nxt.add(s)
        nodes |= nxt; frontier = nxt
    edges = [(s, d, t) for s, d, t in g.all_edges() if t in etypes and s in nodes and d in nodes]
    return nodes, edges
```

### Roles and colour

`node_roles(idx)` tags nodes by role — entry, hub, likely-unused — derived from the insights, and the renderers colour accordingly (green entry, blue hub, red unused, purple focus). This turns the diagram into a *legible* map where structure reads at a glance, rather than a uniform blob.

### Tooltips, path-finding, and explanation

`focused_dot` builds DOT for the neighbourhood with each node carrying a `tooltip` attribute — which Graphviz renders into the SVG as a hover title, so even the "static" view has hover detail (purpose and complexity). `path_between(idx, a, b)` runs a breadth-first search over `calls` and `imports` to find and highlight the route from one symbol to another ("how does `create_app` reach `Detector.predict`?" → `create_app → run_inference → Detector.predict`). `explain_view_llm` optionally asks the configured LLM to describe the focused subgraph in plain language.

### The interactive canvas

`pyvis_html(idx, focus, nodes, edges, roles)` builds the draggable canvas — but returns `None` if pyvis is not installed, which is the signal for the app to fall back to Graphviz:

```python
def pyvis_html(idx, focus, nodes, edges, roles, height=540):
    try:
        from pyvis.network import Network
    except Exception:
        return None                                  # -> caller uses focused_dot instead
    net = Network(height=f"{height}px", width="100%", directed=True,
                  cdn_resources="in_line", bgcolor="#ffffff")   # inlined: no CDN
    net.barnes_hut(spring_length=120)
    for n in nodes:
        nd = g.get(n)
        net.add_node(n, label=..., title=_tooltip(nd),
                     color=ROLE_COLOR.get("focus" if n == focus else roles.get(n, "normal")))
    for s, d, t in edges:
        if s in nodes and d in nodes: net.add_edge(s, d, title=t)
    return net.generate_html(notebook=False)
```

The pedagogical payoff is real: a learner starts at an entry point, sees it call into a few functions, clicks one to recenter, follows the chain, and builds a mental model by *traversing* the system rather than staring at it. The role colours and tooltips mean they always know what kind of thing they are looking at and why it matters.

\newpage
## The mind map (default view)

The Diagrams tab now opens on a **mind map** rather than the neighbourhood graph, because a force-directed neighbourhood of a real repository quickly becomes a sprawling, unreadable blob. `mindmap_tree` builds a **single-parent breadth-first tree** from a chosen root — a file, a symbol, or the synthetic whole-repo root — capped in both depth and branches-per-node, so the result is a clean hierarchy rather than a tangled graph (the first time a node is discovered fixes its single parent). `mindmap_dot` renders it left-to-right, coloured by branch depth with entry/unused role colours, and the view is *re-rootable*: selecting any branch recenters the map on it. The neighbourhood graph remains available as "Graph explorer," and the file-dependency / class / knowledge presets under "Whole-repo."

\newpage

# Teaching (`teach.py`)

The teaching module is KnowIT's differentiator — the "Teach Me This Repository" experience. Its defining design property is that **every learning artifact is generated structurally from the code graph, so it works with no LLM at all**, and is merely *enriched* when a model is configured. This chapter covers the five generators and the algorithms behind them.

## Learning path

`learning_path(idx)` produces a suggested route through the repository, ordered by pedagogical priority: entry points first (where execution begins), then hub files (structurally central), then the remainder. For each stop it lists the file's key symbols (sorted by complexity) and its internal dependencies.

```python
def learning_path(idx):
    ins = repo_insights(idx)
    entry = ins["entry_files"]; hubs = [h["file"] for h in ins["hub_files"]]
    files = _code_files(idx)
    ordered, seen = [], set()
    for f in entry + hubs + sorted(files):
        if f in files and f not in seen: seen.add(f); ordered.append(f)
    ...
```

The ordering is a deliberate teaching sequence: understand where the program starts, then the pieces everything depends on, then the periphery.

## Flashcards

`flashcards(idx)` generates spaced-recall cards grounded in real code: for each symbol, a card asking what it does (answer: its docstring plus the names it calls plus its location); for each class, a "what is this class" card; for each file with internal dependencies, a "what does this file depend on" card. Because the answers are drawn from docstrings, call edges, and locations, the cards are factual and verifiable, not invented.

## Quizzes: three difficulty levels with distractors

`quiz(idx, level, n)` is the most algorithmically interesting generator. It produces multiple-choice questions, and the three difficulty levels ask structurally different things:

- **Beginner** — "Which file defines `focal_loss`?" Tests basic orientation (where things live).
- **Intermediate** — "Which function does `train` call?" Tests understanding of call relationships.
- **Senior** — "Which symbol has the highest cyclomatic complexity?", "Which file is an entry point?", "Which symbol is defined but never called in-repo?" Tests architectural and quality reasoning.

The clever part is **distractor generation** — a multiple-choice question is only as good as its wrong answers. KnowIT builds each question from a correct answer plus three plausible distractors drawn from the same pool (other files for a "which file" question, other functions for a "which call" question), shuffled so the answer position is random:

```python
def mc(question, correct, pool, ref, expl):
    distract = [x for x in dict.fromkeys(pool) if x != correct]
    rng.shuffle(distract)
    opts = [correct] + distract[:3]
    rng.shuffle(opts)
    return {"question": question, "options": opts, "answer": opts.index(correct),
            "explanation": expl, "ref": ref}
```

Because the distractors are *real* symbols and files from the same repository, the questions are genuinely discriminating — you cannot answer them without knowing the codebase. A fixed random seed makes a given quiz reproducible, which matters for testing.

## Interview mode

`interview(idx)` generates open-ended, senior-engineer-style prompts about *this* repository, each with a list of "expected points" derived structurally:

- "Walk through, end to end, what happens when `<entry>` runs." — expected points are the call chain from the entry file's symbols.
- "Explain the responsibility of `<most complex symbol>`."
- "`<unused symbol>` is defined but never called — why, and what would you do?"
- "What depends on `<hub file>`, and what breaks if its interface changes?" — expected points are its dependents.

When an LLM is configured, `grade_answer_llm` feeds the question, the candidate's typed answer, the expected points, and retrieved code context to the model, which returns brief feedback ending in a score out of ten. Without an LLM, the UI simply reveals the expected points as a self-check. This is the one teaching feature where the LLM materially upgrades the experience (from self-assessment to graded feedback), and it degrades cleanly.

## Learning-gaps tracker

`learning_gaps(idx, explored)` is the feature the project's vision singled out as most valuable. Given the set of files the user has *explored* (tracked by the app as they browse the Files tab and use the Learn tab), it reports three things: coverage (fraction of code files explored), the never-explored files, and — most usefully — the **used-but-unexplored** files: files that the user's explored files *import*, but which the user has not themselves studied.

```python
def learning_gaps(idx, explored_files):
    files = set(_code_files(idx)); explored = set(explored_files) & files
    used = set()
    for f in explored:
        for d in idx.graph.successors(f, "imports"):
            if d in files and d not in explored: used.add(d)
    return {"total": len(files), "explored": len(explored),
            "coverage": round(len(explored) / len(files), 2) if files else 0.0,
            "unexplored": sorted(files - explored),
            "used_but_unexplored": sorted(used)}
```

"You rely on `losses.py` but have never looked at it" is exactly the kind of blind spot a learner cannot see for themselves, and it falls straight out of intersecting the exploration set with the import graph.

\newpage

# Change Tracking (`track.py`)

Tracking is the longitudinal feature: it compares the repository's structure across two commits and reports what changed — including how the changes intersect with what the user has learned. It is built directly on two things established earlier: the `{graph node, commit}` provenance tagging, and git. This chapter explains snapshots, fingerprints, the diff, and the three deltas.

## Snapshots via git worktrees

To analyse the repository as it was at a past commit *without disturbing the user's current checkout*, KnowIT uses **git worktrees**. A worktree is a second working directory attached to the same repository but checked out at a different commit. `snapshot` creates a detached worktree at the target commit, builds a throw-away index of it, extracts a fingerprint, and removes the worktree:

```python
def snapshot(source_path, commit, config=CONFIG):
    cache = os.path.join(config.data_dir, "snapshots", f"{commit[:12]}.json")
    if os.path.exists(cache): return json.load(open(cache))      # cached
    wt = os.path.join(config.data_dir, "worktrees", commit[:12])
    _git(["worktree", "add", "--detach", "--force", wt, commit], source_path)
    try:
        idx = build_index(wt, config, use_cache=False, register=False)
        fp = fingerprint(idx, commit)
    finally:
        _git(["worktree", "remove", "--force", wt], source_path)
    json.dump(fp, open(cache, "w"))
    return fp
```

This is non-destructive (the user's working tree is untouched), cached (each commit's fingerprint is stored as JSON, so re-comparing the same pair is instant), and reuses the entire `build_index` pipeline — a snapshot is just an index built at a worktree, reduced to a fingerprint. Note `register=False`, so temporary worktrees never appear in the recent-repos list, and `use_cache=False`, because the fingerprint JSON is the relevant cache here.

## Fingerprints

A **fingerprint** is the compact structural signature the diff operates on: the files present (with line counts), the symbols present (each with a *hash of its source code* and its complexity), and the import and call edges.

```python
def fingerprint(idx, commit):
    files, symbols = {}, {}
    for p in idx.parsed_files:
        if p.language in CODE_LANGS:
            files[p.file] = p.loc
            for sym in p.symbols:
                symbols[f"{sym.file}::{sym.qualname}"] = {
                    "file": sym.file, "kind": sym.kind, "complexity": sym.complexity,
                    "hash": hashlib.sha1((sym.code or "").encode()).hexdigest()[:12]}
    imports = sorted({(s, d) for s, d, _ in idx.graph.all_edges("imports")})
    calls   = sorted({(s, d) for s, d, _ in idx.graph.all_edges("calls")})
    return {"commit": commit, "files": files, "symbols": symbols,
            "imports": imports, "calls": calls}
```

The source hash is what makes *modification* detectable: a symbol present in both commits but with a different code hash has been modified, even though its name and location are unchanged.

## The diff

`diff(base, head)` is pure set arithmetic over two fingerprints:

```python
def diff(base, head):
    bf, hf = set(base["files"]), set(head["files"])
    bs, hs = base["symbols"], head["symbols"]
    bk, hk = set(bs), set(hs)
    modified = sorted(k for k in (bk & hk) if bs[k]["hash"] != hs[k]["hash"])
    complexity = [{"symbol": k.split("::")[-1], "file": bs[k]["file"],
                   "from": bs[k]["complexity"], "to": hs[k]["complexity"]}
                  for k in (bk & hk) if bs[k]["complexity"] != hs[k]["complexity"]]
    bi, hi = {tuple(x) for x in base["imports"]}, {tuple(x) for x in head["imports"]}
    return {"files_added": sorted(hf - bf), "files_removed": sorted(bf - hf),
            "symbols_added": sorted(hk - bk), "symbols_removed": sorted(bk - hk),
            "symbols_modified": modified,
            "imports_added": sorted(hi - bi), "imports_removed": sorted(bi - hi),
            "complexity_changes": complexity}
```

Set differences give added/removed files and symbols; the hash comparison gives modifications; the import-edge differences give the architecture change; the complexity comparison gives the quality drift.

## The three outputs

From a diff, KnowIT produces three views:

1. **Changelog** (`changelog_text`) — a plain-language, grouped summary: files added/removed, symbols added/removed/modified, new and removed imports, complexity changes. When an LLM is configured, `narrate_llm` additionally writes a friendly prose changelog grouping related edits.
2. **Architecture delta** (`architecture_delta_dot`) — a Graphviz diagram of the import graph across both commits, colour-coded: added files and import edges in green, removed ones in red and dashed, unchanged ones in grey. This makes a structural change — "`model.py` stopped importing `data.py` and now imports `losses.py`" — visible at a glance.
3. **Learning delta** (`learning_delta`) — the feature that ties tracking back to teaching. It intersects the changed files with the user's *explored* set: the files the user had studied that have since changed (and therefore need re-learning), the new files they have not yet seen, and any explored files that were removed.

```python
def learning_delta(d, explored):
    changed = set(d["files_added"]) | set(d["files_removed"])
    for key in d["symbols_modified"] + d["symbols_added"] + d["symbols_removed"]:
        changed.add(key.split("::")[0])
    return {"re_learn": sorted(set(explored) & changed),
            "new_files": sorted(set(d["files_added"]) - set(explored)),
            "removed_files": sorted(set(d["files_removed"]) & set(explored))}
```

The learning delta is the clearest demonstration of why the provenance and exploration-tracking decisions made earlier were worth it: "you studied `model.py`; it changed; here is what to re-learn" requires nothing more than a set intersection because the groundwork — tagging artifacts with commits and tracking exploration — was laid in earlier phases.

\newpage

# Evaluation (`eval_harness.py`)

KnowIT measures its own retrieval quality with an evaluation harness, so that "is retrieval working?" has an objective, reproducible answer rather than a vibe. This is the mechanism that gated each phase during development.

## Question sets

An evaluation is a list of questions, each optionally annotated with the files and keywords a correct response should surface:

```json
{"id": "q1", "question": "How does the inference flow work end to end?",
 "expect_files": ["infer.py"], "expect_keywords": ["preprocess", "predict", "postprocess"]}
```

Questions load from JSON (always, via the standard library) or YAML (if `PyYAML` is installed) — another instance of the optional-dependency pattern.

## Scoring and the gate

For each question, `run_eval` calls `RepoIndex.ask`, then scores two things automatically: **retrieval hit** (did any expected file appear among the retrieved sources?) and **keyword coverage** (what fraction of the expected keywords appear in the answer, or in the retrieved context when no LLM is configured). A question passes if retrieval hit and keyword coverage clear their thresholds. Optionally, if a judge model is configured, an LLM-as-judge scores correctness and groundedness instead.

The harness aggregates a pass rate and a **gate**: pass if at least 80% of the scored questions pass.

```python
scored = [r for r in rows if r["passed"] is not None]
pass_rate = sum(1 for r in scored if r["passed"]) / len(scored) if scored else 0.0
summary = {"total": len(rows), "scored": len(scored),
           "passed": sum(1 for r in scored if r["passed"]),
           "pass_rate": pass_rate, "gate_pass": pass_rate >= 0.8}
```

## Why it matters

Two properties make this harness valuable. First, the automatic checks (retrieval hit, keyword coverage) require *no LLM and no secrets*, so the gate runs headlessly in CI or on a developer's laptop — the bundled sample repository scores 10/10 on the built-in BM25 retriever, which is the regression check run after every engine change in this project. Second, the optional LLM-as-judge path is available for richer correctness scoring when desired, without making the basic gate depend on it. The harness is also exposed as a headless script, `scripts/run_eval.py`, so the gate can be checked from the command line against any repository and question set.

\newpage
# Engineering Intelligence (`techdebt.py`, `engmemory.py`)

Phase 5 turns KnowIT into engineering memory: an automated technical-debt audit and a persisted record of decisions, errors, and learnings. Both are pure functions of the already-built graph (plus a small JSON store), so the analysis is instant and offline.

## The tech-debt analysers

`techdebt.py` computes six signals, each a structural query:

- **Dead code** — a function or method with no in-repo callers *whose name is not referenced in any entry file's code tokens*. The "code tokens" qualifier matters: entry identifiers are collected with Python's tokenizer (NAME tokens only), so a symbol invoked from a `__main__` block is not flagged, while a word that merely appears in a docstring cannot suppress a real flag.
- **Near-duplicates** — clone detection that first *normalises structure*: each Python symbol is tokenised with the standard-library `tokenize`, identifiers become `ID`, numbers become `LIT`, and string/docstring tokens are dropped; the normalised token stream is then compared by 4-shingle Jaccard. Because identifiers are erased, copy-paste clones are caught even when variables were renamed and the docstring removed.
- **Import cycles** — a depth-first search over the file import graph reporting strongly-connected file groups (mutual-import coupling).
- **Complexity hotspots**, **god-files** (many symbols or high total complexity), and **undocumented** symbols round out the audit.

```python
def dead_code(idx):
    entry_names = _entry_code_names(idx, set(repo_insights(idx)["entry_files"]))
    out = []
    for nid, n in idx.graph.nodes.items():
        if n["type"] != "symbol" or n["data"]["kind"] == "class":
            continue
        nm = n["data"]["name"]
        if (nm.startswith("__") and nm.endswith("__")) or idx.graph.callers(nid) \
                or nm.lower() in entry_names:
            continue
        out.append({"symbol": n["data"]["qualname"], "file": n["data"]["file"]})
    return out
```

## Engineering memory

`engmemory.py` is a per-repo JSON store under `data_dir/eng/<repo>/` for three kinds — `decisions` (architecture decision records), `errors` (an error → cause → fix knowledge base), and `memory` (a learned/failed/improved log). It exposes `add`, `load`, and `delete`, plus optional `draft_decision_llm` and `diagnose_error_llm` helpers that, when a provider is configured, draft a decision record from notes or diagnose a pasted traceback against the repo's code. Everything degrades gracefully without an LLM. Surfaced in the **Intel** tab.

\newpage

# Learning Media (`media.py`)

Phase 6 produces the high-engagement, shareable formats: slide decks, an audio overview, and a text mind-map outline.

## Slide decks

`slide_outline(idx, style)` assembles deck content from the insights, learning path, and tech-debt audit for one of three audiences — *technical*, *executive*, *architecture*. `build_pptx` then renders it with **python-pptx** into a genuinely designed deck (not default placeholders): a dark navy title slide with an accent rule, big stat callouts (files / symbols / lines / languages), and accent-bar bullet slides, using a consistent palette. The function accepts a path or an in-memory buffer, so the app can offer a one-click download. If python-pptx is absent the feature reports that clearly; the outline itself is always available as a preview.

## Audio overview

`audio_script(idx, model)` generates a NotebookLM-style **two-host dialogue** (Maya, a curious host, and Dev, an engineer) walking through what the repo is, how it's structured, the main flow, and its risks — built from the repo facts, and rewritten into a more natural conversation when an LLM is configured. `script_to_text` renders a transcript, and `synthesize_audio` is a best-effort, optional TTS step that tries edge-tts (two voices), then pyttsx3, then gTTS, returning a clear message if none is installed. The transcript is the primary artifact; audio is the optional accelerator.

## Mind-map outline

`mindmap_markdown` emits the mind-map tree as an indented Markdown outline — a text companion to the visual mind map, exportable as `.md`. All three live in the **Media** tab.

\newpage

# Research Mode (`research.py`)

Phase 7 links the code to the research literature — especially valuable for the ML beachhead, where understanding a repository often means understanding the papers behind it.

## Detecting and looking up papers

`find_papers` scans every file's text for **arXiv ids, arXiv URLs, and DOIs**, returning each reference with the files that cite it — a fully offline, regex-based step. `parse_arxiv_atom` parses the arXiv API's Atom response with the standard-library XML parser (offline-testable), and `arxiv_lookup` performs the actual fetch over `urllib` with a timeout, returning the paper's title, authors, date, and abstract — or a graceful error if offline.

```python
_ARXIV_ID  = re.compile(r'arxiv[:\s/]+\s*(\d{4}\.\d{4,5})(?:v\d+)?', re.I)
_ARXIV_URL = re.compile(r'arxiv\.org/(?:abs|pdf)/(\d{4}\.\d{4,5})', re.I)
_DOI       = re.compile(r'\b(10\.\d{4,9}/[-._;()/:A-Za-z0-9]+)\b')
```

## LLM-backed analysis

Three optional, graceful features use the configured LLM: `comparison_matrix_llm` builds a Markdown comparison table of named approaches (e.g. YOLO vs DETR vs DINO); `implementation_plan_llm` produces a plan *grounded in the repo* by retrieving relevant code as context; and `novelty_summary_llm` notes what the repo implements, what is standard, and what may be novel. Surfaced in the **Research** tab.

\newpage

# Portfolio Mode (`portfolio.py`)

Phase 8 turns everything KnowIT knows into shareable artifacts. A single `_facts(idx)` aggregator gathers the repo's metrics, languages, entry points, hubs, key files (with purposes), complexity, tech-debt counts, referenced papers, and learning path. Five generators then shape those facts into a **project report**, a **technical blog post**, **résumé bullets**, a **LinkedIn post**, and a **research-paper skeleton**. `generate(idx, kind, model)` returns the structural draft offline and, when a provider is set, refines it with the LLM (the structural draft is passed in as scaffolding so the model stays grounded in the facts). Output is Markdown, downloadable from the **Portfolio** tab.

```python
def generate(idx, kind, model="", extra=None):
    facts = _facts(idx)
    draft = _KINDS.get(kind, _report_md)(facts)   # always-available structural draft
    if not model:
        return draft
    # else: LLM refines the draft using the facts (grounded), falling back to draft on error
```

\newpage

# Beyond the Plan: Learning Retention and Engineering Add-ons

After the nine-phase plan was complete, a set of features was added to close the gap between the system's thesis — *teach and track understanding over time* — and its earlier reality, in which learning state was session-only. None of them required a new tab or a new dependency; each slots into an existing tab and the standard library.

## Persistent learning and spaced repetition (`progress.py`)

The most consequential add-on. Per-repo state — the files you've explored, your flashcard review history, and your quiz scores — persists to `data_dir/progress/<repo>/state.json`, so learning survives restarts. Flashcards are scheduled with a **Leitner box** system: a correct review promotes a card to a longer interval, a miss resets it to box 0.

```python
INTERVALS = [0, 1, 3, 7, 16, 35]   # review gap (days) by box

def review_card(state, card, correct):
    c = state["cards"].get(card_id(card), {"box": 0, "reps": 0})
    c["box"] = min(c["box"] + 1, len(INTERVALS) - 1) if correct else 0
    c["due"] = _today() + INTERVALS[c["box"]]
    state["cards"][card_id(card)] = c
    return state
```

`due_cards` selects what to review, `dashboard` reports coverage, mastery, and due counts plus quiz history, and `export_anki_tsv` exports cards for Anki. It is wired into the Learn tab as a **Progress** mode, with ✓/✗ grading on flashcards and automatic quiz-score recording; exploration is captured as a side effect of browsing the Files tab and persisted. This is the feature that turns one-off study into durable, tracked learning — the moat the strategy describes.

## Test-reference coverage (`coverage.py`)

Detects test files (by name and path), maps which symbols those tests reference, and flags untested functions ranked by complexity (so "untested *and* complex" surfaces first). This is *reference* coverage — whether a test mentions a symbol — not runtime line coverage, so it needs no execution. Surfaced in **Intel → Coverage**.

## Impact analysis (`impact.py`)

`impact_of(node)` computes the blast radius of changing a symbol: transitive reverse-reachability over `calls` edges (its callers, their callers, and so on) plus the files that import the symbol's file. It pairs with change tracking to answer "what would this change affect?" and is surfaced in the **Track** tab.

## Configuration surface (`config_map.py`)

Static parsing misses the configuration and hyperparameters that actually drive behaviour, especially in ML repositories. Ingestion now also reads `yaml`/`toml`/`ini`/`cfg` files, and `config_surface` extracts their keys, `argparse` CLI flags, and UPPER_CASE settings — surfaced in **Overview**.

## Portable understanding export (`export_site.py`)

Generates a single self-contained HTML page (inline CSS, no external assets) bundling the overview, insights, per-file explanations, learning path, and mind-map outline — so the understanding KnowIT built can be shared without running it. Surfaced in **Portfolio**.

## Secret scanning (`techdebt.secret_scan`)

A regex pass flags likely hardcoded credentials — AWS access keys, private-key blocks, Slack tokens, and generic `api_key`/`secret`/`token`/`password` assignments — folded into the Intel tech-debt audit.

## A runnable test suite (`tests/test_knowit.py`)

Finally, a **19-test standard-library `unittest` suite** codifies the verification: it exercises the pipeline, retrieval, insights, diagrams (including the mind map's single-parent property), teach, tech-debt, engineering memory, research, portfolio, the spaced-repetition scheduler, coverage, impact, the configuration map, and the eval gate — all offline, with fixtures created in temporary directories. Run it with `python -m unittest tests.test_knowit`. It needs no network and no secrets, so it is suitable for continuous integration.

\newpage

# The Streamlit Application (`app.py`)

`app.py` is the single entry point and the only user interface. It is deliberately *thin*: it owns no business logic, delegating everything to the `knowit` library, and concerns itself only with layout, state, caching, and wiring user actions to library calls. This chapter explains its structure.

## One command, immediately running

The application is launched with `streamlit run app.py`, and it is designed to be *useful on launch with no further action*. On startup it auto-builds the index for a default repository — the bundled `sample_repo`, or whatever the `KNOWIT_REPO` environment variable points to — so the user lands on a populated, working system rather than an empty form.

## Caching the index across reruns

Streamlit re-executes the entire script on every interaction, which would mean rebuilding the index on every click. KnowIT prevents this with `st.cache_resource`, which memoises the built `RepoIndex` keyed on the inputs that affect the build:

```python
@st.cache_resource(show_spinner=False)
def _build(source, backend):
    return build_index(source, Config(embed_backend=backend))

def get_index(source, backend, full_model, extra, topk):
    idx = _build(source, backend)
    idx.config.llm_model = full_model      # applied at ask-time; no rebuild
    idx.config.llm_kwargs = extra or {}
    idx.config.top_k = topk
    return idx
```

The cache key is `(source, backend)` — the two things that change the *build*. The LLM model, extra kwargs, and top-k are applied to the cached index's config *after* retrieval, because they affect only how questions are answered, not how the index is built; changing the model therefore does not trigger a rebuild. This in-memory cache complements the on-disk cache (Chapter 12): the disk cache makes the *first* build of a session fast across restarts, while `cache_resource` makes *subsequent interactions* within a session instant. A "Rebuild index" button calls `_build.clear()` to force a fresh build.

## The sidebar

The sidebar holds all configuration: the repository path (plus a recent-repos switcher read from the registry), the retrieval backend, and the LLM provider/model selection. The provider UI is generated from the `providers.PROVIDERS` table — choosing a provider populates a model dropdown with that provider's example models (plus a custom-entry option) and, for Ollama/custom, a base-URL field. A "Test connection" button calls `providers.test_connection`. The resolved `(full_model, extra)` pair from `providers.resolve` is threaded into every feature that can use an LLM.

## The eight tabs

The body is eight tabs, each a thin view over a feature module:

| Tab | Backed by | What it shows |
|---|---|---|
| Overview | `pipeline.stats`, `insights` | headline metrics, a pipeline explainer, insights, language breakdown |
| Files | `insights.file_summary` | file tree, per-file explanation, source view |
| Diagrams | `diagram` | the interactive explorer + whole-repo presets |
| API & DB | `insights.api_map/db_map` | detected routes and data models |
| Ask | `RepoIndex.ask` | grounded answer (or context) with source tags |
| Learn | `teach` | learning path, flashcards, quiz, interview, gaps |
| Track | `track` | timeline, commit pickers, changelog/architecture/learning deltas |
| Eval | `eval_harness` | the scored ≥80% gate |

## Session state and exploration tracking

The application uses Streamlit's `st.session_state` for two things. First, the diagram explorer's focus node is stored there, so "jump to a connected node" can recenter the graph by updating the focus and calling `st.rerun()`. Second — and this is what powers the learning-gaps feature — an `explored` set accumulates every file the user opens in the Files tab and every file referenced by a Learn-tab activity. The Gaps view reads this set to compute coverage. Exploration is thus tracked implicitly as a side effect of normal use, with no explicit "mark as read" required (though the learning path also offers a checkbox).

## Rendering helpers and graceful UI

Two helpers keep the views robust. `show_table` renders a pandas DataFrame if pandas is installed and falls back to `st.table` otherwise. `show_graph` wraps `st.graphviz_chart` in a `try/except` so that a single malformed diagram degrades to showing its DOT source rather than blanking the tab. The Diagrams tab additionally tries `diagram.pyvis_html` first and falls back to `show_graph(diagram.focused_dot(...))` when pyvis is absent. The graceful-degradation philosophy thus extends all the way into the presentation layer.

\newpage

# Running and Deploying KnowIT

This chapter is the practical guide: how to install, configure, and run the system, and how to use each LLM provider.

## Installation

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows  (source .venv/bin/activate on macOS/Linux)
pip install -r requirements.txt
```

Python 3.10 or newer is required. The core runs on the standard library; `requirements.txt` pins the optional accelerators (Streamlit, chromadb, litellm, pyvis, pandas, GitPython, tree-sitter) so that a full install gives the complete experience. A minimal install with only Streamlit would still run, using the BM25/Graphviz/context-only fallbacks throughout.

## Configuration via `.env`

Copy `.env.example` to `.env` and fill in what you need. All settings are optional:

```bash
KNOWIT_LLM_PROVIDER=          # openai | anthropic | groq | ollama | openrouter | custom
KNOWIT_LLM_MODEL=
KNOWIT_LLM_BASE_URL=          # ollama: http://localhost:11434 ; or a custom endpoint
# OPENAI_API_KEY=...  ANTHROPIC_API_KEY=...  GROQ_API_KEY=...  OPENROUTER_API_KEY=...
KNOWIT_EMBED_BACKEND=auto     # auto | hybrid | bm25 | chroma
KNOWIT_DATA_DIR=.knowit_cache
KNOWIT_USE_CACHE=1
# KNOWIT_REPO=C:/path/to/your/repo   # boot straight into your own repo
```

## Running

```bash
streamlit run app.py
```

The application opens in a browser, auto-builds the bundled sample repository (or `KNOWIT_REPO`), and presents the eight tabs. To analyse your own code, type its path or git URL in the sidebar and the index rebuilds.

## Using the LLM providers

- **Groq** — set provider `groq`, model e.g. `llama-3.3-70b-versatile`, and `GROQ_API_KEY`.
- **Ollama (local)** — run `ollama serve`, set provider `ollama`, model e.g. `llama3.1`, base URL `http://localhost:11434`; no key needed, and nothing leaves the machine.
- **OpenAI / Anthropic / OpenRouter** — set the provider and the matching API key.
- **Custom** — point provider `custom` at any OpenAI-compatible server via its base URL.

Use the "Test connection" button to confirm the provider, model, and key work before relying on them.

## Headless evaluation

The retrieval gate can be checked from the command line, with no UI and no secrets:

```bash
python scripts/run_eval.py sample_repo eval/questions.example.json
python scripts/run_eval.py /path/to/your/repo eval/questions.example.json
```

## Trying change-tracking

The Track tab needs a git repository with history. Either point KnowIT at one of your own repositories, or generate a demo with `python scripts/make_demo_history.py`, which builds a small three-commit repository you can open in the sidebar.

\newpage

# Extending KnowIT

KnowIT's seams are deliberate. This chapter shows how to extend it along its four most likely axes; each is small because the architecture anticipated it.

## Adding a language

Implement an extractor that returns a `ParsedFile` (symbols, imports, optionally calls and bases) and add a branch to `parsing.parse_file` for the new extension. Everything downstream — graph, chunking, retrieval, diagrams, insights — consumes `ParsedFile` uniformly, so no other module changes. The JS/TS regex parser is the worked example; a tree-sitter-based extractor would slot in the same way with higher fidelity (and would be the place to add real call-graph extraction for non-Python languages).

## Adding an LLM provider

Add one entry to `providers.PROVIDERS` giving the provider's label, key environment variable, litellm prefix, and a couple of example models (and `base_url: True` with a `default_base` if it needs an endpoint). Because everything routes through litellm and resolution is data-driven, no code changes — the sidebar, resolution, connection test, and all four LLM features pick up the new provider automatically.

## Adding a diagram

Write a function that returns a Graphviz DOT string from the graph (following `architecture_dot` as a template) and add a branch in the Diagrams tab to render it with `show_graph`. If you want it interactive, express it as a neighbourhood and reuse `focused_dot`/`pyvis_html`.

## Adding an evaluation set or a quiz type

A new evaluation set is just another JSON file of questions with `expect_files`/`expect_keywords`; point `run_eval` at it. A new quiz type is a new branch in `teach.quiz` producing question dictionaries in the same shape (question, options, answer index, explanation, ref); the UI renders any question of that shape.

\newpage

# Testing, Verification, and Engineering Practices

This chapter documents how the system is verified, because the testing strategy is itself a consequence of the architecture.

## Verifiability without secrets

The defining testing property is that the **entire core is exercisable headlessly** — no GPU, no API key, no network. This falls directly out of the dependency-light, graceful-degradation design: because BM25, the `ast` parser, the pure-Python graph, and all the structural generators (insights, teach, track, diagrams) require nothing external, the whole pipeline can be built and queried in a plain Python process. Throughout development, every module's behaviour was validated this way — building the sample repository's index and asserting on the graph, the retrieval results, the generated quizzes, the fingerprint diffs, and so on.

## The regression gate

The evaluation harness is the standing regression test. After any change to parsing, the graph, chunking, or retrieval, the gate is re-run against the sample repository; it must remain at 10/10. This caught real regressions during development and is the objective definition of "retrieval still works."

## What is and is not verified in a sandbox

It is worth being precise about the limits. The structural and lexical paths — parsing, graph, BM25, RRF fusion, insights, teach, track (including git worktree snapshots, since git needs no network), the diagram DOT generators, provider *resolution* — are all fully verified. The paths that require a network or a heavy optional library — Chroma's embeddings, litellm's calls to a provider, pyvis's rendered HTML — are written carefully and guarded, but are first exercised in a real environment with those dependencies installed. The "Test connection" button exists precisely so a user can confirm the LLM path in their own environment in one click.

## Coding practices

The codebase favours small, single-responsibility modules; pure functions over stateful objects wherever possible (the feature modules are almost entirely pure functions of a `RepoIndex`); explicit, narrow data contracts (the five dataclasses); and defensive boundaries around every optional dependency. There is no global mutable state except the process-wide `CONFIG` default and Streamlit's per-session state.

\newpage

# Performance, Complexity, and Scaling

This chapter analyses what each stage costs, how the caching layers interact, where the system is fast, and where it will eventually strain. The numbers are asymptotic; concrete timings are given qualitatively because they depend on repository size and hardware.

## Per-stage cost

Let *F* be the number of source files, *L* the total lines of code, *S* the number of symbols, *E* the number of graph edges, *C* the number of chunks (note *C ≈ S + F*), *T* the total number of tokens across all chunks, and *Q* the number of terms in a query.

| Stage | Cost | Notes |
|---|---|---|
| Ingestion (file walk) | O(F) | plus a shallow git clone for URLs |
| Parsing | O(L) | one AST/regex pass per file |
| Graph build, pass 1 | O(S) | nodes + name/module indices |
| Graph build, pass 2 | O(Σ calls · collisions) | name resolution; collisions usually ≈ 1 |
| Graph build, pass 3 | O(Σ imports) | import resolution |
| Chunking | O(S) | one chunk per symbol + per file |
| BM25 index | O(T) | term frequencies + IDF |
| BM25 query | O(C · Q) | linear scan of chunks per query |
| RRF fusion | O(candidates) | typically a few dozen |
| Graph expansion | O(top_k · avg-degree) | one hop |
| Context assembly | O(top_k) | bounded by the character budget |

The dominant build cost is parsing (O(L)) and the dominant query cost is the BM25 scan (O(C·Q)). Both are linear and, for the small-to-medium repositories KnowIT targets, complete in well under a second.

## The three caching layers

KnowIT layers three caches, each addressing a different repetition:

1. **In-memory (`st.cache_resource`)** — caches the built `RepoIndex` for the duration of a Streamlit session, keyed on `(source, backend)`. This makes every interaction *after* the first build instantaneous, because no rebuild occurs when the user clicks around, changes the LLM model, or adjusts top-k.
2. **On-disk parse cache (pickle)** — caches the parse/graph/chunk product keyed on `repo+commit+file-signature`, so that *relaunching the application* on an unchanged repository skips parsing entirely and loads the pickle in well under a second.
3. **Chroma collection persistence** — the embedded vector store persists its embeddings under `data_dir/chroma`, keyed by the build signature, so that re-embedding (the most expensive optional step) is skipped when the chunk set is unchanged.

A fourth, narrower cache — `data_dir/snapshots/<commit>.json` — memoises change-tracking fingerprints so that re-comparing the same pair of commits is instant.

The interaction is worth internalising: the in-memory cache eliminates *intra-session* rebuilds; the disk caches eliminate *inter-session* recomputation. Together they mean that the only time a user pays full build cost is the very first time a particular repository at a particular state is seen.

## Memory footprint

At runtime the system holds, in memory: the list of `ParsedFile`s (including each file's full source text), the `CodeGraph` (nodes plus dual adjacency), the list of `Chunk`s (each with its text), and the BM25 index (tokenised documents plus an IDF table). For a medium repository this is a few tens of megabytes — comfortably in RAM. The `ParsedFile.text` and `Symbol.code` fields are the largest contributors; they are retained because they back the source view, docstring extraction, and the fingerprint hashing.

## Where it scales and where it strains

KnowIT is comfortable on small-to-medium repositories (hundreds of files, tens of thousands of lines) — its target. Two characteristics bound very large repositories. First, the BM25 query is a linear scan over all chunks; at hundreds of thousands of chunks this would become noticeable and would motivate an inverted index. Second, the entire graph and chunk set live in memory; a multi-million-line monorepo would strain that. The on-disk cache mitigates *rebuild* cost but not *steady-state* memory. The roadmap's "incremental re-index on file changes" and a future inverted index are the natural responses; neither is needed at the current scale, and adding them prematurely would have violated the simplicity goal.

## Cold start versus warm start

A *cold* start — first sight of a repository — pays ingestion, parsing, graph building, chunking, and (if Chroma is enabled) embedding. A *warm* start — relaunch on the same unchanged repository — pays only the pickle load and BM25 reconstruction (fast) plus Chroma collection reuse (no re-embedding). The difference is dramatic and is the entire point of the cache design: the user experiences "instant" on every launch after the first.

# Security, Privacy, and Data Handling

KnowIT analyses source code, which is often proprietary, so its data-handling posture is a first-class design concern rather than an afterthought. This chapter states precisely what the system does and does not do with your code and secrets.

## The local-first guarantee

In its default configuration, **KnowIT sends nothing off the machine.** Ingestion reads local files (or clones a repository you named). Parsing, the graph, BM25 retrieval, all diagrams, all insights, and all learning artifacts are computed locally with no network access. Semantic embeddings, when enabled, run *on-device* via Chroma's local model. No telemetry is collected. The only ways data leaves the machine are explicit and opt-in, described next.

## What leaves the machine, and when

There are exactly three network interactions, all optional and all user-initiated:

1. **Cloning a git URL.** If you give the sidebar a URL rather than a local path, git clones it. If you only ever use local paths, no clone occurs.
2. **A one-time Chroma model download.** The first time semantic retrieval is enabled, Chroma downloads its small embedding model; thereafter it runs offline. If you stay on the BM25 backend, this never happens.
3. **LLM calls.** Only when you configure a provider, and only for the four LLM features (answers, file explanations, interview grading, changelog narration). What is sent is the *question (or task) plus the assembled, retrieved context* — that is, the relevant snippets, not your whole repository — to the provider you chose. Choosing **Ollama** keeps even this fully local: the model runs on your machine and nothing is transmitted externally.

There is no background processing: every LLM call is the direct result of a click (Ask, Explain, Grade, Narrate, or Test connection).

## Untrusted code is parsed, not executed

A subtle but important safety property: KnowIT **never executes the code it analyses.** Python files are parsed with `ast.parse`, which builds a syntax tree *without running* the module — module-level code, decorators, and imports in the target repository are read as text, not evaluated. The JS/TS parser is pure regex. `build_index` never imports or runs anything from the target. This means pointing KnowIT at an unfamiliar or untrusted repository does not run that repository's code, which is a meaningful safety guarantee that many "run the tests to understand it" approaches cannot offer. (Cloning a URL does run git, and a malicious repository could in principle exploit a git vulnerability, but the code itself is never executed by KnowIT.)

## Secrets handling

API keys are read from environment variables (optionally via a `.env` file) and are never written to disk by KnowIT, never logged, and never included in any generated artifact. The repository's `.gitignore` explicitly excludes `.env` (while keeping `.env.example` tracked) so keys cannot be accidentally committed. The "Test connection" feature is the only place a key is exercised outside a feature action, and it sends a five-token "reply with: ok" probe.

## On-disk state and how to clear it

All persistent state lives under `data_dir` (default `.knowit_cache`), which the `.gitignore` excludes from version control. It contains: `cache/` (pickled parse products), `chroma/` (embeddings), `snapshots/` (change-tracking fingerprints), `worktrees/` (transient, removed after each snapshot), `repos/` (clones of git URLs), and `repos.json` (the recent-repos registry). Deleting `data_dir` resets everything; it will be rebuilt on demand. Because all of this is regenerable, none of it belongs in git, and the corrected `.gitignore` ensures it stays out.

## git worktree safety

Change-tracking creates temporary git worktrees to read historical commits. Worktrees are *non-destructive*: they are separate directories that never touch your current checkout, and `track.snapshot` removes each worktree in a `finally` block so a failure mid-snapshot still cleans up. The worktrees live under `data_dir/worktrees` and are therefore also outside version control.

\newpage

# Design Decisions and Trade-offs

This chapter consolidates the consequential engineering decisions in one place, each stated as the context that forced a choice, the choice made, the alternatives weighed, and the consequence. Together they explain the system's character.

**1. A dependency-light core with graceful fallbacks.** *Context:* the system needs parsing, a graph, retrieval, embeddings, an LLM, and visualisation — each with a "best" heavyweight library. *Decision:* make the core standard-library-only and treat every heavyweight library as an optional accelerator behind a fallback. *Alternatives:* depend on the best tool for each job. *Consequence:* the system runs anywhere with no secrets or network, is fully testable headlessly, and survives any one dependency being absent — at the cost of writing the fallbacks. This single decision shapes the whole codebase.

**2. Standard-library `ast` for Python, not tree-sitter.** *Context:* Phase 0 is Python-first. *Decision:* parse Python with `ast`. *Alternatives:* tree-sitter from the start. *Consequence:* zero install friction, no grammar-version pitfalls, always correct for the running interpreter — while keeping tree-sitter in the dependency list for the eventual multi-language upgrade. The cost is that multi-language today is best-effort regex.

**3. A hand-rolled pure-Python code graph, not networkx or a graph database.** *Context:* the graph operations needed are few and simple. *Decision:* a ~90-line `CodeGraph`. *Alternatives:* networkx (a dependency) or Neo4j (a service). *Consequence:* zero dependencies, trivially picklable for the cache, fully testable; the cost is that advanced graph algorithms would have to be written by hand if ever needed.

**4. BM25 default, Chroma optional, fused by Reciprocal Rank Fusion.** *Context:* lexical and semantic retrieval have complementary strengths and incomparable score scales. *Decision:* always run BM25, add Chroma when present, fuse by *rank* (RRF) not score. *Alternatives:* pick one retriever; fuse by normalised score; add a cross-encoder re-ranker. *Consequence:* robust hybrid retrieval that degrades cleanly to BM25-only; RRF's rank basis sidesteps the score-scale problem entirely. A cross-encoder is on the roadmap as a further re-rank.

**5. Symbol-level chunking, not fixed-size windows.** *Context:* chunk granularity drives retrieval and answer quality. *Decision:* one chunk per function/class/method, plus per-file and per-doc chunks. *Alternatives:* fixed character/line windows. *Consequence:* retrieved units are semantically complete and align with graph nodes (enabling expansion and provenance); very long functions are truncated to a line budget.

**6. Name-based call resolution, not type-aware analysis.** *Context:* building a call graph without a type system. *Decision:* resolve callees by matching names across the repository. *Alternatives:* full semantic/type analysis or a language server. *Consequence:* a cheap, language-agnostic, good-enough call graph; the cost is occasional over-connection when names collide, and no resolution of dynamic dispatch.

**7. litellm plus a data-driven provider registry.** *Context:* support many LLM providers without bloat. *Decision:* route everything through litellm and model providers as a dictionary. *Alternatives:* per-provider SDKs and client code. *Consequence:* six provider families plus arbitrary endpoints in ~50 lines, where adding a provider is a dictionary entry rather than a class.

**8. Provenance tagging from day one.** *Context:* change-tracking (Phase 4) was planned but not built early. *Decision:* tag every chunk with `{graph node, commit}` from Phase 0. *Alternatives:* add tracking metadata later. *Consequence:* the learning delta and change tracking became a set-intersection rather than a rewrite — the clearest payoff of designing for a known future.

**9. An on-disk pickle cache keyed by a content signature.** *Context:* re-parsing on every launch is wasteful. *Decision:* pickle the parse/graph/chunk product keyed by `repo+commit+file-signature`. *Alternatives:* a database, or no cache. *Consequence:* near-instant warm starts with a few lines of code; the signature folds in file mtimes for uncommitted trees so edits invalidate it correctly.

**10. git worktrees for historical snapshots.** *Context:* analysing a past commit without disturbing the user's checkout. *Decision:* create a detached worktree, build a throw-away index, remove it. *Alternatives:* `git show` per file (needs an in-memory parse path) or `git checkout` (destructive). *Consequence:* non-destructive, reuses the whole pipeline unchanged, and cleans up in a `finally`.

**11. Structural-first learning artifacts.** *Context:* flashcards and quizzes are "naturally" LLM-generated. *Decision:* generate them from the code graph so they work offline, and merely enrich with an LLM. *Alternatives:* LLM-only generation. *Consequence:* the entire Teach experience works with no API key, is deterministic and testable, and is grounded in real code (quiz distractors are real symbols) rather than invented.

**12. Native Graphviz, then inlined pyvis — never a CDN.** *Context:* an early CDN-loaded Mermaid renderer failed in the iframe. *Decision:* default to server-side Graphviz; for interactivity use pyvis with inlined assets. *Alternatives:* CDN-loaded JavaScript libraries. *Consequence:* diagrams always render; interactivity is added without reintroducing the CDN failure mode, and falls back to Graphviz if pyvis is absent.

**13. A single thin Streamlit file, not a separate frontend and backend.** *Context:* the project is a research preview built solo. *Decision:* one `app.py` over the `knowit` library, with no business logic in the UI. *Alternatives:* a web frontend plus an API service. *Consequence:* one command runs everything, the library stays UI-agnostic and reusable (and testable without Streamlit), at the cost of the scaling ceiling a dedicated backend would raise.

\newpage

# Completion and Verification

All nine phases of the build plan (Phase 0 through Phase 8) are implemented: foundations and retrieval, understanding, teaching, deepened understanding, change tracking, engineering intelligence, learning media, research mode, and portfolio mode. This chapter records how that completeness was verified.

## The verification run

A single script builds the bundled `sample_repo` index and a three-commit git repository, then calls the public entry point of every feature and asserts on its output — **29 checks** spanning all six tiers, the "missing features" (timeline, knowledge graph, tech-debt, learning gaps), the architecture layers (multi-provider LLM resolution, multi-repo registry), and the retrieval gate. **All 29 pass**, the eval gate is **10/10**, and all modules compile. A standard-library **`unittest` suite** (`tests/test_knowit.py`, 19 tests) now codifies the offline checks for repeatable regression. Features whose triggers are absent from the sample (web routes, ORM models, paper references) were verified on dedicated fixtures: a FastAPI route file, an ORM model with `__tablename__`, a file citing arXiv ids and a DOI, a renamed-clone pair, and a mutual-import cycle.

## What is and is not network-verified

The structural and git paths — parsing, the code graph, BM25 retrieval, RRF fusion, insights, diagrams (including the mind map), teach, track via git worktrees, tech-debt, engineering memory, slide-deck generation via python-pptx, paper detection, arXiv-Atom parsing, and all portfolio artifacts — are verified offline. The paths that require a network or a heavy optional library — Chroma's embeddings, litellm's provider calls, TTS audio, and the live arXiv fetch — are written defensively and degrade gracefully; they are exercised first in a fully-installed environment via the in-app "Test connection" and the optional-dependency fallbacks.

## Honest approximations

A handful of original-vision items are delivered in an approximated form rather than as full formal artifacts, each a deliberate scoping choice with a clear upgrade path: sequence and data-flow diagrams are approximated by the call-flow view; service and component diagrams by the file-dependency and knowledge graphs; the audio overview produces the two-host script (audio needs an optional TTS backend); the research-paper draft is a structured skeleton refined by the LLM; and JavaScript/TypeScript parsing is best-effort regex without a call graph (tree-sitter is the intended upgrade). The companion **Vision Coverage Report** tabulates every vision item against its implementation status, location, and verification.

\newpage

# Limitations and Roadmap

An honest accounting of what the current implementation does *not* do, and where it is going.

## Known limitations

- **Call-graph precision.** The Python call graph resolves callees by *name*, not type, so two functions sharing a name can be over-connected, and dynamic dispatch is approximate. JS/TS has no call graph at all (the regex parser does not extract calls). A type-aware analysis (or language servers) would improve this but at a dependency cost.
- **Multi-language depth.** JS/TS support is best-effort regex; tree-sitter is the intended upgrade for full multi-language parsing including calls.
- **Heuristic detectors.** API and database maps cover common framework idioms (FastAPI/Flask/Express decorators, ORM base classes, `__tablename__`) and silently miss unconventional registration.
- **Retrieval is symbol-granular.** Very large monolithic functions are truncated in their chunk; extremely large repositories will stress the in-memory graph and BM25 index (though the disk cache mitigates rebuild cost).
- **Network-dependent paths are user-verified.** As noted, the Chroma, litellm, and pyvis paths are exercised first in the user's environment.

## Roadmap

The implemented phases (0–4) cover understanding, teaching, deepening, and tracking. The vision continues:

- **Phase 5 — Engineering Intelligence**: a technical-debt tracker (dead/duplicate code, complexity hotspots — partly present already via insights), an architecture-decision log, and an error knowledge base.
- **Phase 6 — Rich Learning Media**: a NotebookLM-style two-host audio overview, auto-generated slide decks, and mind maps.
- **Phase 7 — Research Mode**: linking code to the research literature (papers ↔ implementations), comparison matrices, implementation plans.
- **Phase 8 — Portfolio Mode**: auto-generated project reports, blog posts, and résumé bullets.
- **Engine**: a cross-encoder re-ranking stage after RRF, cross-repository querying, and incremental re-indexing on file changes.

The architecture was built to make these additive rather than disruptive: provenance tagging already supports longitudinal features, the provider layer already supports any LLM-driven generation, and the `ParsedFile`/graph contracts already support new languages and analyses.

\newpage
# Appendix A: Configuration and Environment Reference {-}

Every setting, its environment variable, default, and effect. All are optional.

| Environment variable | `Config` field | Default | Effect |
|---|---|---|---|
| `KNOWIT_LLM_PROVIDER` | `llm_provider` | "" | Provider key, or empty for no LLM |
| `KNOWIT_LLM_MODEL` | `llm_model` | "" | Model name (resolved against the provider) |
| `KNOWIT_LLM_BASE_URL` | `llm_base_url` | "" | Endpoint for ollama/custom providers |
| `KNOWIT_EMBED_BACKEND` | `embed_backend` | `auto` | `auto`/`hybrid` = BM25+Chroma; `bm25` lexical only; `chroma` forces semantic |
| `KNOWIT_DATA_DIR` | `data_dir` | `.knowit_cache` | Root for cache, snapshots, worktrees, clones, registry |
| `KNOWIT_CHUNK_MAX_LINES` | `chunk_max_lines` | 160 | Max lines of a symbol's code per chunk |
| `KNOWIT_TOP_K` | `top_k` | 6 | Results before graph expansion |
| `KNOWIT_GRAPH_EXPAND` | `graph_expand` | 1 | Hops of graph expansion (0 disables) |
| `KNOWIT_USE_CACHE` | `use_cache` | 1 | Read/write the on-disk parse cache |
| `KNOWIT_REPO` | — (app) | sample_repo | Repository the app boots into |
| `OPENAI_API_KEY` | — (env) | — | OpenAI / custom-endpoint key |
| `ANTHROPIC_API_KEY` | — (env) | — | Anthropic key |
| `GROQ_API_KEY` | — (env) | — | Groq key |
| `OPENROUTER_API_KEY` | — (env) | — | OpenRouter key |

# Appendix B: API Reference {-}

The public surface of each module. Signatures are simplified for clarity; consult the source for exact defaults.

## `config` {-}

- `Config` — dataclass of all settings (see Appendix A).
- `CONFIG` — the process-wide default `Config` instance.

## `models` {-}

- `Symbol` — a function/class/method: `id, name, qualname, kind, file, start_line, end_line, docstring, code, calls, parent, complexity, bases`.
- `ParsedFile` — a parsed source file: `file, language, imports, symbols, loc, text, error`.
- `Chunk` — a retrievable unit: `id, file, kind, name, start_line, end_line, text, node_id, commit, symbol_id`.
- `RepoMeta` — repository metadata: `name, path, commit, branch, is_git, n_commits`.
- `Retrieved` — a scored result: `chunk, score, via`.

## `ingest` {-}

- `clone_or_local(source, data_dir) -> str` — returns a local working-copy path; clones git URLs into `data_dir/repos`.
- `repo_meta(path) -> RepoMeta` — reads git commit/branch/count, or marks `working-tree`.
- `list_files(path, max_files=8000) -> (code, docs)` — walks the tree, pruning ignored directories; returns code and doc file lists.
- `ingest(source, data_dir) -> (RepoMeta, code, docs)` — the full ingestion step.

## `parsing` {-}

- `parse_python(rel_path, source) -> ParsedFile` — AST-based extraction of symbols, imports, calls, complexity, bases.
- `parse_js(rel_path, source, language) -> ParsedFile` — regex-based JS/TS extraction of functions, classes, imports.
- `parse_file(rel_path, abs_path) -> ParsedFile` — dispatches on file extension.

## `graph` {-}

- `CodeGraph` — the directed multigraph. Methods: `add_node, add_edge, successors(nid, etype), predecessors(nid, etype), neighbors(nid), callees(sym), callers(sym), get(nid), all_edges(etype), stats()`.
- `build_graph(parsed_files) -> CodeGraph` — builds nodes, the name and module indices, and the `contains`/`method_of`/`calls`/`imports`/`inherits` edges.

## `chunking` {-}

- `make_chunks(parsed_files, commit, max_lines=160) -> list[Chunk]` — emits module, symbol, and doc chunks with provenance.

## `index` {-}

- `tokenize(text) -> list[str]` — camelCase/snake split, lowercase, conservative stem.
- `BM25Retriever` — `index(chunks)`, `search(query, k) -> [(Chunk, score)]`.
- `ChromaRetriever(data_dir, sig)` — persistent semantic retriever; `index`, `search`; reuses an embedded collection across launches.

## `retrieval` {-}

- `hybrid_search(query, lexical, dense, graph, chunks_by_node, k, expand) -> list[Retrieved]` — RRF fusion of lexical+dense, then graph expansion.
- `assemble_context(retrieved, max_blocks=8, max_chars=6000) -> str` — citation-headed, budgeted context for the LLM/UI.

## `llm` {-}

- `synthesize(question, context, model, extra) -> (answer|None, used_llm)` — grounded answer or graceful no-op.
- `judge(question, answer, context, model, extra) -> float|None` — LLM-as-judge score in [0,1].
- `explain_file(summary, code_excerpt, model, extra) -> str|None` — natural-language file explanation.

## `providers` {-}

- `PROVIDERS` — the provider registry dict; `ORDER` — display order.
- `resolve(provider, model, base_url) -> (litellm_model, extra)` — maps a UI choice to a litellm call.
- `key_present(provider) -> bool` — is the provider's key set?
- `test_connection(full_model, extra) -> (ok, message)` — a tiny live round-trip.

## `insights` {-}

- `repo_insights(idx) -> dict` — entry points, hub files, complex symbols, likely-unused, LOC, average complexity.
- `file_summary(idx, file) -> dict` — purpose, dependencies in/out, defines, public API, complexity, fan-in/out.
- `api_map(idx) -> list` — detected web routes.
- `db_map(idx) -> list` — detected ORM models / tables.
- `language_breakdown(idx) -> list` — per-language file/LOC/symbol counts.

## `diagram` {-}

- `architecture_dot(idx)`, `class_dot(idx)`, `callflow_dot(idx, node)`, `knowledge_dot(idx)` — whole-repo DOT diagrams.
- `architecture_mermaid(idx)` — Mermaid export of the file dependency graph.
- `neighborhood(idx, focus, depth, etypes) -> (nodes, edges)` — the explorer's data.
- `node_roles(idx) -> dict` — entry/hub/unused tags for colouring.
- `focused_dot(idx, focus, nodes, edges, roles, path) -> str` — neighbourhood DOT with tooltips/roles/path highlight.
- `pyvis_html(idx, focus, nodes, edges, roles) -> str|None` — interactive inlined canvas, or None if pyvis absent.
- `path_between(idx, a, b, etypes) -> list` — BFS path over calls/imports.
- `explain_view_llm(idx, nodes, edges, focus, model, extra) -> str|None` — LLM walkthrough of a subgraph.

## `teach` {-}

- `learning_path(idx) -> list` — ordered stops (entry → hub → rest) with key symbols and deps.
- `flashcards(idx, limit) -> list` — grounded Q/A cards.
- `quiz(idx, level, n, seed) -> list` — 3-level MCQs with distractors.
- `interview(idx, n) -> list` — open prompts with expected points.
- `grade_answer_llm(question, answer, expected, context, model, extra) -> str|None` — LLM feedback + score.
- `learning_gaps(idx, explored) -> dict` — coverage, unexplored, used-but-unexplored.

## `track` {-}

- `is_git(path) -> bool`, `git_log(path, n) -> list` — git availability and commit timeline.
- `fingerprint(idx, commit) -> dict` — structural signature (files, symbols+hash, edges).
- `snapshot(source_path, commit, config) -> dict` — fingerprint at a commit via worktree (cached).
- `diff(base, head) -> dict` — added/removed/modified files, symbols, imports, complexity.
- `changelog_text(diff) -> str` — plain-language changelog.
- `architecture_delta_dot(base, head) -> str` — colour-coded import-graph delta.
- `learning_delta(diff, explored) -> dict` — re-learn / new / removed relative to explored.
- `narrate_llm(diff, model, extra) -> str|None` — LLM prose changelog.

## `pipeline` {-}

- `RepoIndex` — the runtime bundle: `stats()`, `search(query)`, `ask(query)`.
- `build_index(source, config, progress, use_cache, register) -> RepoIndex` — the full pipeline with caching.
- `recent_repos(data_dir) -> list`, `record_repo(...)` — the multi-repo registry.

## `eval_harness` {-}

- `load_questions(path) -> list` — JSON (always) or YAML (if PyYAML present).
- `run_eval(repo_index, questions, judge_model) -> (rows, summary)` — scores and the gate.

\newpage
# Appendix C: Data Model Reference {-}

Complete field listings for the five dataclasses.

**`Symbol`** — `id` (str, "path::qualname"), `name` (bare name), `qualname` (qualified), `kind` ("function"/"method"/"class"), `file` (rel path), `start_line`/`end_line` (int), `docstring` (str), `code` (str, raw source), `calls` (list[str], callee base names), `parent` (str|None, enclosing class), `complexity` (int), `bases` (list[str], base-class names).

**`ParsedFile`** — `file` (rel path), `language` (str), `imports` (list[str]), `symbols` (list[Symbol]), `loc` (int), `text` (str, full source), `error` (str, parse error or "").

**`Chunk`** — `id` (str, content hash), `file`, `kind` ("symbol"/"module"/"doc"), `name`, `start_line`/`end_line`, `text` (indexed text), `node_id` (graph node provenance), `commit` (commit provenance), `symbol_id` (str|None).

**`RepoMeta`** — `name`, `path` (absolute), `commit` (SHA or "working-tree"), `branch`, `is_git` (bool), `n_commits` (int).

**`Retrieved`** — `chunk` (Chunk), `score` (float, fused), `via` ("lexical"/"semantic"/"both"/"graph").

# Appendix D: Code-Graph Schema Reference {-}

**Node types** — `file` (id = relative path; data: language, loc, imports, error) and `symbol` (id = "path::qualname"; data: name, qualname, kind, file, start, end, doc, complexity, bases).

**Edge types** —

| Type | From → To | Built in pass | Source of truth |
|---|---|---|---|
| `contains` | file → symbol | 1 | parser symbol list |
| `method_of` | method → class | 2 | symbol `parent` |
| `calls` | symbol → symbol | 2 | symbol `calls`, resolved by name index |
| `inherits` | class → class | 2 | symbol `bases`, resolved by name index |
| `imports` | file → file | 3 | file `imports`, resolved by module index |

# Appendix E: Dependency Reference {-}

What each dependency is for and whether it is required.

| Package | Role | Required? | Fallback if absent |
|---|---|---|---|
| streamlit | the application/UI | required to run the app | — (the library works without it) |
| chromadb | semantic embeddings (dense retrieval) | optional | BM25 only |
| litellm | LLM transport for all providers | optional | cited-context-only |
| pyvis | interactive draggable diagram canvas | optional | native Graphviz |
| pandas | dataframe tables in the UI | optional | `st.table` |
| GitPython | (git operations are mostly via subprocess) | optional | subprocess git |
| tree-sitter | reserved for richer multi-language parsing | optional | stdlib `ast` (Python), regex (JS/TS) |
| python-dotenv | load `.env` | optional | environment only |
| PyYAML | YAML eval question sets | optional | JSON question sets |
| graphviz (system) | native diagram rendering | provided by Streamlit frontend | — |

The standard library provides everything else: `ast` (parsing), `hashlib` (chunk ids, fingerprints), `pickle`/`json` (cache, registry, snapshots), `subprocess` (git), `re`/`math`/`collections` (BM25, tokenisation, the graph).

# Appendix F: A Worked Example — Tracing a Question End to End {-}

To consolidate the whole document, here is the complete path of one question — "How does the inference flow work?" — through the system, on the bundled `sample_repo`.

**1. Build.** On launch the app calls `get_index("sample_repo", "auto", ...)`, which calls `build_index`. Ingestion lists six Python files and one Markdown file. Parsing produces seven `ParsedFile`s and ~15 symbols. `build_graph` assembles 22 nodes and ~42 edges; among them, `infer.py::run_inference` has `calls` edges to `load_image`, `preprocess`, `Detector.predict`, and `postprocess` (resolved by name from the parser's call list). Chunking emits 22 chunks, each tagged with its node id and the commit. A `BM25Retriever` indexes them; if chromadb is installed, a `ChromaRetriever` indexes them too. The resulting `RepoIndex` is cached in memory and on disk.

**2. Ask.** The user types the question in the Ask tab, which calls `idx.ask(...)` → `idx.search(...)` → `hybrid_search(...)`.

**3. Retrieve.** BM25 tokenises the question to `["how", "doe", "the", "inference", "flow", "work"]` (after stemming) and scores every chunk; the `run_inference` symbol chunk ranks highly because its docstring contains "inference flow." If Chroma is present, it independently returns semantically similar chunks. RRF fuses the two ranked lists; `run_inference` accumulates the top fused score and is tagged `both` (or `lexical` in the BM25-only configuration).

**4. Expand.** Graph expansion takes the top fused chunks and walks one hop. From `run_inference`'s node it pulls in its callees' chunks — `load_image`, `preprocess`, `Detector.predict`, `postprocess` — tagging them `graph`. The result is the *entire inference call chain*, not just the one function the text search matched.

**5. Assemble.** `assemble_context` formats the ranked chunks into citation-headed blocks within the character budget.

**6. Answer.** If a provider is configured, `synthesize` sends the grounded context to the model with the strict grounding prompt and returns a written answer citing `(infer.py:8)` and the functions it calls. If no provider is configured, the UI shows the assembled, cited context directly — still a complete, source-tagged answer, just not prose.

**7. Display.** The Ask tab renders the answer (or context) and, beneath it, each retrieved source with its `via` tag and score, so the user sees both the answer and exactly where it came from.

The same `RepoIndex` simultaneously backs every other tab: the Diagrams explorer can focus `run_inference` and show this very call chain interactively; the Files tab explains `infer.py`; the Learn tab can quiz on it; and, if the repository has history, the Track tab can show whether this flow changed between commits and whether it intersects what the user has studied.

# Appendix G: Per-Tab Control Flow {-}

For each tab: what triggers work, which library functions it calls, what session state it touches, and what it renders.

**Overview** — on render, calls `idx.stats()` and `insights.repo_insights(idx)` and `insights.language_breakdown(idx)`. No state written. Renders metrics, the pipeline explainer, and the insight tables.

**Files** — a `selectbox` chooses a file; the chosen file is added to `session_state["explored"]`. Calls `insights.file_summary(idx, file)`; optionally `llm.explain_file(...)` on a button. Renders the file tree, the summary, and the source.

**Diagrams** — a focus `selectbox`, a depth slider, and an edge-type multiselect drive `diagram.neighborhood(...)`; `diagram.node_roles(...)` colours nodes; `diagram.pyvis_html(...)` (or `diagram.focused_dot(...)` as fallback) renders; an optional path target calls `diagram.path_between(...)`. The focus node lives in `session_state["focus_node"]`; "jump to" updates it and calls `st.rerun()`. Whole-repo presets call `architecture_dot`/`class_dot`/`knowledge_dot`.

**API & DB** — calls `insights.api_map(idx)` and `insights.db_map(idx)`. Stateless. Renders two tables (or "none detected").

**Ask** — a text box and a button call `idx.ask(query)`. Renders the answer (if an LLM is configured) or the grounded context, then each retrieved source with its `via` tag and score.

**Learn** — a mode radio selects one of five generators: `teach.learning_path`, `teach.flashcards`, `teach.quiz` (with level + count; the quiz lives in `session_state["quiz"]`), `teach.interview` (+ `teach.grade_answer_llm` on a button), or `teach.learning_gaps(idx, explored)`. Activities add their referenced files to `session_state["explored"]`.

**Track** — `track.git_log(path)` populates the timeline and two commit pickers; "Compare" calls `track.snapshot` twice, then `track.diff`, then renders `track.changelog_text`, `track.architecture_delta_dot`, the complexity table, and `track.learning_delta(diff, explored)`. Optionally `track.narrate_llm` when an LLM is set.

**Eval** — a "Run eval" button calls `eval_harness.load_questions` and `eval_harness.run_eval(idx, ...)`. Renders the pass count, pass rate, gate status, and a per-question table.

# Appendix H: On-Disk Data Formats {-}

All persistent state under `data_dir` (default `.knowit_cache`).

```
.knowit_cache/
├── cache/<repo-name>_<sig>.pkl     pickled (parsed_files, graph, chunks) tuple
├── chroma/                         Chroma persistent embedding store
├── snapshots/<commit12>.json       change-tracking fingerprint (see below)
├── worktrees/<commit12>/           transient git worktree (removed after use)
├── repos/<name>/                   clone of a git-URL source
└── repos.json                      recent-repos registry (see below)
```

**Parse cache (`cache/*.pkl`).** A Python pickle of the 3-tuple `(parsed_files, graph, chunks)`. The signature `<sig>` is a 16-hex SHA-1 of the commit (and, for a working tree, each file's mtime+size). Loading it reconstructs everything except the retrievers, which are rebuilt from the chunks.

**Snapshot fingerprint (`snapshots/<commit>.json`).** Shape:

```json
{ "commit": "<sha>",
  "files":   { "model.py": 37, "data.py": 12 },
  "symbols": { "model.py::Detector.predict":
                 { "file": "model.py", "kind": "method", "complexity": 3, "hash": "1a2b3c4d5e6f" } },
  "imports": [ ["model.py", "losses.py"] ],
  "calls":   [ ["infer.py::run_inference", "model.py::Detector.predict"] ] }
```

**Registry (`repos.json`).** A list of recently indexed repositories, most-recent first, capped at 20:

```json
[ { "source": "/path/or/url", "name": "repo", "commit": "abc123def456" } ]
```

**Evaluation question set (JSON).** A list (or `{"questions": [...]}`) of:

```json
{ "id": "q1", "question": "How does the inference flow work?",
  "expect_files": ["infer.py"], "expect_keywords": ["preprocess", "predict", "postprocess"] }
```

`expect_files` and `expect_keywords` are optional; a question with neither is reported as "manual" (un-scored).

# Appendix I: FAQ and Troubleshooting {-}

**The Diagrams tab shows a static image, not a draggable one.** Install `pyvis` (`pip install -r requirements.txt`) and restart. Without pyvis, the explorer falls back to native Graphviz, which is still interactive through the focus/depth/filter/jump controls.

**The Ask tab shows code blocks but no written answer.** No LLM is configured — that is the default, offline behaviour. Choose a provider and model in the sidebar (and set the matching API key, or use Ollama locally) to get synthesised answers. The cited context shown is itself a complete, source-tagged answer.

**The Track tab says it needs a git repository.** Track requires history. Point KnowIT at a git repository with at least two commits, or run `python scripts/make_demo_history.py` and open the folder it prints.

**Retrieval feels keyword-only / misses paraphrases.** The semantic half (Chroma) is not active — either `chromadb` is not installed or the backend is set to `bm25`. Install chromadb and set the backend to `auto`/`hybrid`; the first semantic build downloads a small model once.

**The first build is slow on a large repository.** That is the cold-start cost (parsing + optional embedding). Subsequent launches load from the disk cache and are fast. Ensure `KNOWIT_USE_CACHE=1` (the default).

**"Test connection" fails.** The provider, model name, or key is wrong, or (for Ollama) the local server is not running (`ollama serve`) or the base URL is incorrect. The error message names the exception type to help diagnose.

**How do I reset everything?** Delete the `.knowit_cache` directory; all of it is regenerable.

**Can I analyse a private repository safely?** Yes — KnowIT never executes the code it analyses (it only parses it), and in the default configuration nothing leaves your machine. If you enable an LLM provider, only the retrieved context for your specific questions is sent to that provider (or stays local with Ollama).

\newpage

# Appendix J: Glossary {-}

**`ast`** — Python's standard-library Abstract Syntax Tree module, used to parse Python.

**BM25** — a classical lexical ranking function scoring documents by weighted term frequency; KnowIT's default retriever.

**Chunk** — a unit of text submitted to the retrieval index (symbol, module, or doc), carrying provenance.

**Chroma (chromadb)** — an embedded vector database providing optional on-device semantic search.

**Code graph** — the directed multigraph of files and symbols with typed edges; the structural backbone.

**Complexity** — a cyclomatic-style score (1 + decision points) per function, summed for classes.

**Cyclomatic complexity** — a measure of the number of independent paths through code.

**Delta** — the difference between two fingerprints (change tracking).

**Dense retrieval** — retrieval by embedding-vector similarity (semantic), as opposed to lexical.

**Fingerprint** — a compact structural signature of a repository at a commit.

**Gate** — the eval harness's pass/fail threshold (≥80% of scored questions pass).

**Graceful degradation** — the pattern of optional dependencies with always-available fallbacks.

**GraphRAG** — retrieval augmented by traversing a graph (here, expanding retrieved chunks along the code graph).

**Hub file** — a file central in the import graph (high in/out degree).

**IDF (inverse document frequency)** — a term's rarity weight in BM25.

**Learning delta** — the intersection of a change delta with the user's explored set.

**litellm** — the library routing one uniform `completion()` call to any LLM provider.

**LLM** — large language model; used only when a provider is configured.

**Provenance** — a chunk's `{graph node, commit}` tag, tying artifacts to exact code.

**pyvis** — the library providing the optional interactive, inlined (no-CDN) graph canvas.

**RepoIndex** — the central runtime object bundling graph, chunks, retrievers, and config.

**RRF (Reciprocal Rank Fusion)** — the rank-based method fusing the lexical and semantic result lists.

**Snapshot** — the structural state of the repository at a commit (a fingerprint), built via a git worktree.

**Symbol** — a function, class, or method; the atom of KnowIT's understanding.

**Worktree** — a second git working directory at a different commit, used for non-destructive snapshots.

**Working tree** — the current on-disk state of the repository; the sentinel commit value when not under git.

\newpage

# Appendix K: Complete Source Listing of the `knowit` Package {-}

The full, delivered source of every module, for reference. Read alongside the corresponding chapter in Part II and Part III.


## `knowit/__init__.py` {-}

~~~python
"""KnowIT — Phase 0: ingest → parse → code graph → retrieval → eval.

Dependency-light core (stdlib only). Optional accelerators activate when installed:
  - chromadb  → semantic embeddings (else built-in BM25)
  - litellm   → LLM answer synthesis (else returns retrieved context only)
"""
__version__ = "0.0.1-phase0"
~~~


## `knowit/config.py` {-}

~~~python
from __future__ import annotations
import os
from dataclasses import dataclass, field

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass


@dataclass
class Config:
    # --- LLM (optional; resolved from provider + model in providers.py) ---
    llm_provider: str = os.getenv("KNOWIT_LLM_PROVIDER", "")   # openai|anthropic|groq|ollama|openrouter|custom
    llm_model: str = os.getenv("KNOWIT_LLM_MODEL", "")         # full litellm model string once resolved
    llm_base_url: str = os.getenv("KNOWIT_LLM_BASE_URL", "")   # for ollama / custom endpoints
    llm_kwargs: dict = field(default_factory=dict)            # extra kwargs passed to litellm (e.g. api_base)
    # --- retrieval ---
    embed_backend: str = os.getenv("KNOWIT_EMBED_BACKEND", "auto")  # auto|hybrid|bm25|chroma
    data_dir: str = os.getenv("KNOWIT_DATA_DIR", ".knowit_cache")
    chunk_max_lines: int = int(os.getenv("KNOWIT_CHUNK_MAX_LINES", "160"))
    top_k: int = int(os.getenv("KNOWIT_TOP_K", "6"))
    graph_expand: int = int(os.getenv("KNOWIT_GRAPH_EXPAND", "1"))
    use_cache: bool = os.getenv("KNOWIT_USE_CACHE", "1") not in ("0", "false", "False")


CONFIG = Config()
~~~


## `knowit/models.py` {-}

~~~python
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Symbol:
    id: str                 # stable id: "<rel_path>::<qualname>"
    name: str
    qualname: str           # e.g. "Detector.predict"
    kind: str               # "function" | "method" | "class"
    file: str               # repo-relative path
    start_line: int
    end_line: int
    docstring: str = ""
    code: str = ""
    calls: list[str] = field(default_factory=list)   # callee base-names found in body
    parent: Optional[str] = None                      # enclosing class qualname
    complexity: int = 0                               # cyclomatic-ish (functions/methods)
    bases: list[str] = field(default_factory=list)    # base classes (inheritance)


@dataclass
class ParsedFile:
    file: str
    language: str
    imports: list[str] = field(default_factory=list)
    symbols: list[Symbol] = field(default_factory=list)
    loc: int = 0
    text: str = ""
    error: str = ""


@dataclass
class Chunk:
    id: str
    file: str
    kind: str               # "symbol" | "module" | "doc"
    name: str
    start_line: int
    end_line: int
    text: str
    node_id: str            # graph node this chunk derives from (load-bearing provenance)
    commit: str             # {graph node, commit} — enables Phase 4 deltas later
    symbol_id: Optional[str] = None


@dataclass
class RepoMeta:
    name: str
    path: str
    commit: str
    branch: str = ""
    is_git: bool = False
    n_commits: int = 0


@dataclass
class Retrieved:
    chunk: Chunk
    score: float
    via: str                # "semantic" | "graph" | "both"
~~~


## `knowit/ingest.py` {-}

~~~python
from __future__ import annotations
import os
import subprocess
from .models import RepoMeta

SKIP_DIRS = {".git", ".knowit_cache", "__pycache__", "node_modules", ".venv",
             "venv", "env", "ENV", "build", "dist", ".mypy_cache", ".pytest_cache",
             ".ruff_cache", "site-packages", ".ipynb_checkpoints", ".idea", ".vscode"}
CODE_EXTS = {".py", ".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx"}
DOC_EXTS = {".md"}


def _git(args, cwd):
    try:
        out = subprocess.run(["git"] + args, cwd=cwd, capture_output=True,
                             text=True, timeout=15)
        if out.returncode == 0:
            return out.stdout.strip()
    except Exception:
        pass
    return ""


def clone_or_local(source, data_dir):
    """Return an absolute path to a local working copy; clone git URLs on demand."""
    if source.startswith(("http://", "https://", "git@")) or source.endswith(".git"):
        repos = os.path.join(data_dir, "repos")
        os.makedirs(repos, exist_ok=True)
        name = source.rstrip("/").split("/")[-1]
        if name.endswith(".git"):
            name = name[:-4]
        dest = os.path.join(repos, name)
        if not os.path.isdir(dest):
            r = subprocess.run(["git", "clone", "--depth", "200", source, dest],
                               capture_output=True, text=True, timeout=600)
            if r.returncode != 0:
                raise RuntimeError(f"git clone failed: {r.stderr.strip()[:500]}")
        return os.path.abspath(dest)
    path = os.path.abspath(os.path.expanduser(source))
    if not os.path.isdir(path):
        raise FileNotFoundError(f"Not a directory: {path}")
    return path


def repo_meta(path):
    is_git = os.path.isdir(os.path.join(path, ".git"))
    commit = _git(["rev-parse", "HEAD"], path) if is_git else ""
    branch = _git(["rev-parse", "--abbrev-ref", "HEAD"], path) if is_git else ""
    n = _git(["rev-list", "--count", "HEAD"], path) if is_git else ""
    return RepoMeta(
        name=os.path.basename(path.rstrip("/")) or path,
        path=path,
        commit=commit or "working-tree",
        branch=branch,
        is_git=is_git,
        n_commits=int(n) if n.isdigit() else 0,
    )


def list_files(path, max_files=8000):
    code, docs = [], []
    for root, dirs, files in os.walk(path):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for f in files:
            ext = os.path.splitext(f)[1].lower()
            abs_p = os.path.join(root, f)
            rel = os.path.relpath(abs_p, path)
            if ext in CODE_EXTS:
                code.append((rel, abs_p))
            elif ext in DOC_EXTS:
                docs.append((rel, abs_p))
        if len(code) + len(docs) > max_files:
            break
    code.sort()
    docs.sort()
    return code, docs


def ingest(source, data_dir):
    """source -> (RepoMeta, list[(rel, abs)] code files, list[(rel, abs)] doc files)."""
    path = clone_or_local(source, data_dir)
    meta = repo_meta(path)
    code, docs = list_files(path)
    return meta, code, docs
~~~


## `knowit/parsing.py` {-}

~~~python
from __future__ import annotations
import ast
import os
import re
from .models import ParsedFile, Symbol

JS_EXTS = {".js", ".jsx", ".mjs", ".cjs"}
TS_EXTS = {".ts", ".tsx"}


def _read(abs_path):
    try:
        with open(abs_path, "r", encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except Exception:
        return ""


# ---------------- Python (stdlib ast) ----------------
def _callee_name(func):
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def _collect_calls(fn_node):
    out, seen = [], set()
    for n in ast.walk(fn_node):
        if isinstance(n, ast.Call):
            nm = _callee_name(n.func)
            if nm and nm not in seen:
                seen.add(nm)
                out.append(nm)
    return out


def _segment(lines, node):
    start = getattr(node, "lineno", 1)
    end = getattr(node, "end_lineno", start)
    return "\n".join(lines[start - 1:end]), start, end


def _complexity(node):
    c = 1
    for n in ast.walk(node):
        if isinstance(n, (ast.If, ast.For, ast.AsyncFor, ast.While,
                          ast.ExceptHandler, ast.IfExp, ast.Assert)):
            c += 1
        elif isinstance(n, ast.BoolOp):
            c += len(n.values) - 1
        elif isinstance(n, ast.comprehension):
            c += 1 + len(n.ifs)
    return c


def _bases(node):
    out = []
    for b in getattr(node, "bases", []):
        if isinstance(b, ast.Name):
            out.append(b.id)
        elif isinstance(b, ast.Attribute):
            out.append(b.attr)
    return out


def parse_python(rel_path, source):
    pf = ParsedFile(file=rel_path, language="python", text=source,
                    loc=source.count("\n") + 1)
    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        pf.error = f"SyntaxError: {e}"
        return pf
    lines = source.splitlines()

    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            for a in n.names:
                pf.imports.append(a.name)
        elif isinstance(n, ast.ImportFrom):
            if n.module:
                pf.imports.append(n.module)
    pf.imports = sorted(set(pf.imports))

    def add_symbol(node, qualprefix, parent):
        qual = f"{qualprefix}{node.name}"
        if isinstance(node, ast.ClassDef):
            kind = "class"
        elif parent:
            kind = "method"
        else:
            kind = "function"
        code, s, e = _segment(lines, node)
        pf.symbols.append(Symbol(
            id=f"{rel_path}::{qual}", name=node.name, qualname=qual, kind=kind,
            file=rel_path, start_line=s, end_line=e,
            docstring=(ast.get_docstring(node) or ""), code=code,
            calls=[] if isinstance(node, ast.ClassDef) else _collect_calls(node),
            parent=parent,
            complexity=0 if isinstance(node, ast.ClassDef) else _complexity(node),
            bases=_bases(node) if isinstance(node, ast.ClassDef) else [],
        ))
        if isinstance(node, ast.ClassDef):
            for b in node.body:
                if isinstance(b, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    add_symbol(b, qual + ".", parent=qual)

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            add_symbol(node, "", parent=None)
    for cls in [x for x in pf.symbols if x.kind == "class"]:
        cls.complexity = sum(m.complexity for m in pf.symbols
                             if m.parent == cls.qualname) or 1
    return pf


# ---------------- JavaScript / TypeScript (best-effort regex) ----------------
_JS_IMPORT = re.compile(r"""import\s+(?:[^'"]+\s+from\s+)?['"]([^'"]+)['"]""")
_JS_REQUIRE = re.compile(r"""require\(\s*['"]([^'"]+)['"]\s*\)""")
_JS_CLASS = re.compile(r"\bclass\s+([A-Za-z_$][\w$]*)(?:\s+extends\s+([A-Za-z_$][\w$.]*))?")
_JS_FUNC = re.compile(r"\bfunction\s+([A-Za-z_$][\w$]*)\s*\(")
_JS_ARROW = re.compile(r"\b(?:export\s+)?(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?\([^)]*\)\s*=>")


def parse_js(rel_path, source, language):
    lines = source.splitlines()
    pf = ParsedFile(file=rel_path, language=language, text=source, loc=len(lines) + 1)

    imps = set()
    for m in _JS_IMPORT.finditer(source):
        imps.add(m.group(1))
    for m in _JS_REQUIRE.finditer(source):
        imps.add(m.group(1))
    pf.imports = sorted(imps)

    seen = set()

    def add(name, kind, pos, bases=None):
        if (name, kind) in seen:
            return
        seen.add((name, kind))
        start = source.count("\n", 0, pos) + 1
        end = min(start + 12, len(lines))
        code = "\n".join(lines[start - 1:end])
        pf.symbols.append(Symbol(
            id=f"{rel_path}::{name}", name=name, qualname=name, kind=kind,
            file=rel_path, start_line=start, end_line=end, docstring="", code=code,
            calls=[], parent=None, complexity=1, bases=bases or []))

    for m in _JS_CLASS.finditer(source):
        add(m.group(1), "class", m.start(), [m.group(2)] if m.group(2) else [])
    for m in _JS_FUNC.finditer(source):
        add(m.group(1), "function", m.start())
    for m in _JS_ARROW.finditer(source):
        add(m.group(1), "function", m.start())
    return pf


# ---------------- dispatch ----------------
def parse_file(rel_path, abs_path):
    ext = os.path.splitext(rel_path)[1].lower()
    src = _read(abs_path)
    if ext == ".py":
        return parse_python(rel_path, src)
    if ext in JS_EXTS:
        return parse_js(rel_path, src, "javascript")
    if ext in TS_EXTS:
        return parse_js(rel_path, src, "typescript")
    lang = "markdown" if ext == ".md" else "other"
    return ParsedFile(file=rel_path, language=lang, text=src, loc=src.count("\n") + 1)
~~~


## `knowit/graph.py` {-}

~~~python
from __future__ import annotations
import os
from collections import defaultdict


class CodeGraph:
    """Pure-Python directed multigraph of code structure.

    Node ids:
      - file node:   repo-relative path, e.g. "infer.py"
      - symbol node: "<rel_path>::<qualname>", e.g. "model.py::Detector.predict"
    Edge types: contains, method_of, calls, imports
    """

    def __init__(self):
        self.nodes = {}                  # id -> {"type":..., "data":...}
        self._out = defaultdict(list)    # id -> [(dst, etype)]
        self._in = defaultdict(list)     # id -> [(src, etype)]

    def add_node(self, nid, ntype, data=None):
        if nid not in self.nodes:
            self.nodes[nid] = {"type": ntype, "data": data or {}}
        return nid

    def add_edge(self, src, dst, etype):
        if src in self.nodes and dst in self.nodes:
            self._out[src].append((dst, etype))
            self._in[dst].append((src, etype))

    def successors(self, nid, etype=None):
        return [d for d, t in self._out.get(nid, []) if etype is None or t == etype]

    def predecessors(self, nid, etype=None):
        return [s for s, t in self._in.get(nid, []) if etype is None or t == etype]

    def neighbors(self, nid):
        return list({d for d, _ in self._out.get(nid, [])}
                    | {s for s, _ in self._in.get(nid, [])})

    def callees(self, sym_id):
        return self.successors(sym_id, "calls")

    def callers(self, sym_id):
        return self.predecessors(sym_id, "calls")

    def get(self, nid):
        return self.nodes.get(nid)

    def all_edges(self, etype=None):
        return [(src, dst, t) for src, lst in self._out.items()
                for dst, t in lst if etype is None or t == etype]

    def stats(self):
        et = defaultdict(int)
        for lst in self._out.values():
            for _, t in lst:
                et[t] += 1
        nt = defaultdict(int)
        for v in self.nodes.values():
            nt[v["type"]] += 1
        return {"nodes": len(self.nodes), "edges": sum(et.values()),
                "node_types": dict(nt), "edge_types": dict(et)}


def build_graph(parsed_files):
    g = CodeGraph()
    name_index = defaultdict(list)   # base name -> [symbol_id]
    module_index = {}                # module path -> file rel

    for pf in parsed_files:
        g.add_node(pf.file, "file", {"language": pf.language, "loc": pf.loc,
                                     "imports": pf.imports, "error": pf.error})
        if pf.file.endswith(".py"):
            mod_key = pf.file[:-3].replace(os.sep, ".").replace("/", ".")
            module_index[mod_key] = pf.file
            module_index[mod_key.split(".")[-1]] = pf.file
        for sym in pf.symbols:
            g.add_node(sym.id, "symbol", {
                "name": sym.name, "qualname": sym.qualname, "kind": sym.kind,
                "file": sym.file, "start": sym.start_line, "end": sym.end_line,
                "doc": sym.docstring, "complexity": sym.complexity,
                "bases": sym.bases,
            })
            g.add_edge(pf.file, sym.id, "contains")
            name_index[sym.name].append(sym.id)

    for pf in parsed_files:
        for sym in pf.symbols:
            if sym.parent:
                parent_id = f"{pf.file}::{sym.parent}"
                if parent_id in g.nodes:
                    g.add_edge(sym.id, parent_id, "method_of")
            for callee in sym.calls:
                for target in name_index.get(callee, []):
                    if target != sym.id:
                        g.add_edge(sym.id, target, "calls")
            for base in sym.bases:
                for target in name_index.get(base, []):
                    tn = g.get(target)
                    if target != sym.id and tn and tn["data"].get("kind") == "class":
                        g.add_edge(sym.id, target, "inherits")

    for pf in parsed_files:
        for imp in pf.imports:
            dst = module_index.get(imp) or module_index.get(imp.split(".")[-1])
            if dst and dst != pf.file:
                g.add_edge(pf.file, dst, "imports")
    return g
~~~


## `knowit/chunking.py` {-}

~~~python
from __future__ import annotations
import hashlib
from .models import Chunk


def _hash(*parts):
    return hashlib.sha1("||".join(parts).encode("utf-8", "replace")).hexdigest()[:16]


def _truncate(text, max_lines):
    lines = text.splitlines()
    if len(lines) <= max_lines:
        return text
    return "\n".join(lines[:max_lines]) + f"\n# ... ({len(lines) - max_lines} more lines truncated)"


def make_chunks(parsed_files, commit, max_lines=160):
    chunks = []
    for pf in parsed_files:
        if pf.language in ("python", "javascript", "typescript"):
            sym_names = ", ".join(s.qualname for s in pf.symbols) or "(no top-level symbols)"
            header = (f"FILE {pf.file} (python)\n"
                      f"imports: {', '.join(pf.imports) or 'none'}\n"
                      f"defines: {sym_names}")
            chunks.append(Chunk(
                id=_hash(pf.file, "module"), file=pf.file, kind="module", name=pf.file,
                start_line=1, end_line=pf.loc, text=header,
                node_id=pf.file, commit=commit, symbol_id=None,
            ))
            for s in pf.symbols:
                body = _truncate(s.code, max_lines)
                text = (f"{pf.file} :: {s.qualname}  [{s.kind}]\n{s.docstring}\n{body}").strip()
                chunks.append(Chunk(
                    id=_hash(s.id), file=pf.file, kind="symbol", name=s.qualname,
                    start_line=s.start_line, end_line=s.end_line, text=text,
                    node_id=s.id, commit=commit, symbol_id=s.id,
                ))
        elif pf.text.strip():
            chunks.append(Chunk(
                id=_hash(pf.file, "doc"), file=pf.file, kind="doc", name=pf.file,
                start_line=1, end_line=pf.loc, text=_truncate(pf.text, max_lines * 2),
                node_id=pf.file, commit=commit, symbol_id=None,
            ))
    return chunks
~~~


## `knowit/index.py` {-}

~~~python
from __future__ import annotations
import math
import os
import re
from collections import Counter

_WORD = re.compile(r"[A-Za-z0-9]+")
_CAMEL = re.compile(r"[A-Z]+(?=[A-Z][a-z])|[A-Z][a-z]+|[a-z]+|[A-Z]+|\d+")


def _stem(t):
    if len(t) > 4 and t.endswith("ing"):
        return t[:-3]
    if len(t) > 4 and t.endswith("ed"):
        return t[:-2]
    if len(t) > 4 and t.endswith("es"):
        return t[:-2]
    if len(t) > 3 and t.endswith("s") and not t.endswith("ss"):
        return t[:-1]
    if len(t) > 4 and t.endswith("ly"):
        return t[:-2]
    return t


def tokenize(text):
    toks = []
    for raw in _WORD.findall(text or ""):
        for p in (_CAMEL.findall(raw) or [raw]):
            p = p.lower()
            if len(p) >= 2:
                toks.append(_stem(p))
    return toks


class BM25Retriever:
    """Pure-stdlib BM25. Always built (the lexical half of hybrid retrieval)."""
    name = "bm25"

    def __init__(self, k1=1.5, b=0.75):
        self.k1, self.b = k1, b
        self.chunks, self.docs, self.idf = [], [], {}
        self.avgdl, self.N = 0.0, 0

    def index(self, chunks):
        self.chunks = list(chunks)
        self.docs = [tokenize(c.text + " " + c.name) for c in self.chunks]
        self.N = len(self.docs)
        df = Counter()
        for d in self.docs:
            for t in set(d):
                df[t] += 1
        self.avgdl = (sum(len(d) for d in self.docs) / self.N) if self.N else 0.0
        self.idf = {t: math.log(1 + (self.N - n + 0.5) / (n + 0.5)) for t, n in df.items()}

    def search(self, query, k=6):
        q = tokenize(query)
        scored = []
        for i, d in enumerate(self.docs):
            if not d:
                continue
            tf = Counter(d)
            dl = len(d)
            s = 0.0
            for t in q:
                f = tf.get(t)
                if not f:
                    continue
                s += self.idf.get(t, 0.0) * (f * (self.k1 + 1)) / (
                    f + self.k1 * (1 - self.b + self.b * dl / (self.avgdl or 1)))
            if s > 0:
                scored.append((i, s))
        scored.sort(key=lambda x: x[1], reverse=True)
        return [(self.chunks[i], float(s)) for i, s in scored[:k]]


class ChromaRetriever:
    """Semantic retriever (chromadb local embeddings). Persists by signature and reuses
    an existing collection across launches instead of re-embedding."""
    name = "chroma"

    def __init__(self, data_dir, sig="default"):
        import chromadb
        os.makedirs(data_dir, exist_ok=True)
        self.client = chromadb.PersistentClient(path=os.path.join(data_dir, "chroma"))
        self.coll = f"knowit_{sig}"
        self.col = self.client.get_or_create_collection(self.coll)
        self.by_id = {}

    def index(self, chunks):
        self.by_id = {c.id: c for c in chunks}
        try:
            if len(chunks) and self.col.count() == len(chunks):
                return  # already embedded and persisted -> reuse
        except Exception:
            pass
        try:
            self.client.delete_collection(self.coll)
        except Exception:
            pass
        self.col = self.client.get_or_create_collection(self.coll)
        for i in range(0, len(chunks), 256):
            part = chunks[i:i + 256]
            self.col.add(ids=[c.id for c in part],
                         documents=[c.text for c in part],
                         metadatas=[{"file": c.file, "name": c.name,
                                     "node_id": c.node_id} for c in part])

    def search(self, query, k=6):
        res = self.col.query(query_texts=[query], n_results=k)
        ids = (res.get("ids") or [[]])[0]
        dists = (res.get("distances") or [[0.0] * len(ids)])[0]
        out = []
        for cid, dist in zip(ids, dists):
            c = self.by_id.get(cid)
            if c:
                out.append((c, 1.0 / (1.0 + float(dist))))
        return out
~~~


## `knowit/retrieval.py` {-}

~~~python
from __future__ import annotations
from .models import Retrieved


def _rrf(rank_lists, kconst=60):
    scores, sources, by_id = {}, {}, {}
    for name, hits in rank_lists:
        for rank, (chunk, _s) in enumerate(hits):
            scores[chunk.id] = scores.get(chunk.id, 0.0) + 1.0 / (kconst + rank + 1)
            sources.setdefault(chunk.id, set()).add(name)
            by_id[chunk.id] = chunk
    return scores, sources, by_id


def hybrid_search(query, lexical, dense, graph, chunks_by_node, k=6, expand=1):
    """Reciprocal-Rank-Fusion of lexical (BM25) + dense (semantic), then graph expansion."""
    cand = max(k * 2, 10)
    lists = [("lexical", lexical.search(query, cand))]
    if dense is not None:
        try:
            lists.append(("semantic", dense.search(query, cand)))
        except Exception:
            pass
    scores, sources, by_id = _rrf(lists)

    results = {}
    for cid, sc in scores.items():
        srcs = sources[cid]
        via = "both" if len(srcs) > 1 else next(iter(srcs))
        results[cid] = Retrieved(chunk=by_id[cid], score=float(sc), via=via)

    if expand and graph is not None and results:
        top = sorted(results.values(), key=lambda r: r.score, reverse=True)[:k]
        maxs = top[0].score if top else 1.0
        for r in top:
            node = r.chunk.node_id
            neigh = set()
            neigh.update(graph.successors(node, "calls"))
            neigh.update(graph.predecessors(node, "calls"))
            neigh.update(graph.successors(node, "contains"))
            neigh.update(graph.successors(node, "imports"))
            for nb in neigh:
                for ch in chunks_by_node.get(nb, []):
                    if ch.id not in results:
                        results[ch.id] = Retrieved(chunk=ch, score=maxs * 0.3, via="graph")
                    else:
                        results[ch.id].score += maxs * 0.05
    ranked = sorted(results.values(), key=lambda r: r.score, reverse=True)
    return ranked[: k + (k // 2 if expand else 0)]


def assemble_context(retrieved, max_blocks=8, max_chars=6000):
    blocks, total = [], 0
    for r in retrieved[:max_blocks]:
        c = r.chunk
        block = f"[{c.file}:{c.start_line}-{c.end_line} :: {c.name}]\n{c.text}"
        if total + len(block) > max_chars:
            break
        blocks.append(block)
        total += len(block)
    return "\n\n".join(blocks)
~~~


## `knowit/llm.py` {-}

~~~python
"""Optional LLM layer (via litellm). Degrades gracefully with no model/key."""
from __future__ import annotations

SYSTEM = (
    "You are KnowIT, a codebase explainer. Answer the question USING ONLY the provided "
    "code context. Ground every claim in the snippets and cite sources inline as "
    "(path:line). Prefer specifics (function/class names) over generalities. If the "
    "answer is not present in the context, say exactly what is missing rather than "
    "guessing. Be concise."
)


def _complete(model, messages, extra=None, **kw):
    import litellm
    return litellm.completion(model=model, messages=messages, **(extra or {}), **kw)


def synthesize(question, context, model, extra=None):
    """Return (answer_text|None, used_llm: bool)."""
    if not model:
        return (None, False)
    try:
        r = _complete(model, [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": f"Question: {question}\n\nCode context:\n{context}"},
        ], extra=extra, temperature=0.1, timeout=60)
        return (r["choices"][0]["message"]["content"].strip(), True)
    except Exception as e:
        return (f"[LLM unavailable: {type(e).__name__}: {e}]", False)


def judge(question, answer, context, model, extra=None):
    if not model or not answer:
        return None
    try:
        import re
        r = _complete(model, [{"role": "user", "content": (
            "Score 0-100 how correct and grounded this answer is given the code context. "
            "Reply with ONLY the integer.\n\n"
            f"Question: {question}\nAnswer: {answer}\n\nContext:\n{context[:4000]}")}],
            extra=extra, temperature=0, timeout=60)
        m = re.search(r"\d+", r["choices"][0]["message"]["content"])
        return (min(100, int(m.group())) / 100.0) if m else None
    except Exception:
        return None


def explain_file(summary, code_excerpt, model, extra=None):
    if not model:
        return None
    try:
        import json
        prompt = (
            "Explain this source file for a new engineer in <150 words. Cover: purpose, "
            "key inputs/outputs, main dependencies, and the most important logic.\n\n"
            f"Structured facts:\n{json.dumps(summary, indent=2)[:2500]}\n\n"
            f"Code excerpt:\n{code_excerpt[:3000]}")
        r = _complete(model, [
            {"role": "system", "content": "You explain code precisely and concisely."},
            {"role": "user", "content": prompt}], extra=extra, temperature=0.2, timeout=60)
        return r["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return f"[LLM unavailable: {type(e).__name__}: {e}]"
~~~


## `knowit/providers.py` {-}

~~~python
"""LLM provider registry. Everything routes through litellm, so adding a provider is
just a model-string prefix (+ optional api_base). Keys are read from the environment."""
from __future__ import annotations
import os

PROVIDERS = {
    "openai":     {"label": "OpenAI",                 "key_env": "OPENAI_API_KEY",
                   "prefix": "",            "base_url": False,
                   "models": ["gpt-4o-mini", "gpt-4o"]},
    "anthropic":  {"label": "Anthropic",              "key_env": "ANTHROPIC_API_KEY",
                   "prefix": "anthropic/",  "base_url": False,
                   "models": ["claude-3-5-haiku-latest", "claude-3-5-sonnet-latest"]},
    "groq":       {"label": "Groq",                   "key_env": "GROQ_API_KEY",
                   "prefix": "groq/",       "base_url": False,
                   "models": ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"]},
    "ollama":     {"label": "Ollama (local)",         "key_env": "",
                   "prefix": "ollama/",     "base_url": True,
                   "default_base": "http://localhost:11434",
                   "models": ["llama3.1", "qwen2.5-coder:7b", "mistral"]},
    "openrouter": {"label": "OpenRouter",             "key_env": "OPENROUTER_API_KEY",
                   "prefix": "openrouter/", "base_url": False,
                   "models": ["meta-llama/llama-3.1-70b-instruct", "google/gemini-flash-1.5"]},
    "custom":     {"label": "Custom (OpenAI-compatible)", "key_env": "OPENAI_API_KEY",
                   "prefix": "openai/",     "base_url": True,
                   "default_base": "http://localhost:8000/v1", "models": []},
}
ORDER = ["", "openai", "anthropic", "groq", "ollama", "openrouter", "custom"]


def resolve(provider, model, base_url=""):
    """Return (litellm_model_string, extra_kwargs) for a provider + model."""
    if not model:
        return ("", {})
    if not provider:
        return (model, {})                     # treat model as a raw litellm string
    p = PROVIDERS.get(provider)
    if not p:
        return (model, {})
    full = p["prefix"] + model
    extra = {}
    if p.get("base_url"):
        bu = base_url or p.get("default_base", "")
        if bu:
            extra["api_base"] = bu
    return (full, extra)


def key_present(provider):
    p = PROVIDERS.get(provider)
    if not p:
        return True
    env = p.get("key_env")
    return (not env) or bool(os.getenv(env))


def test_connection(full_model, extra=None):
    """Tiny round-trip to verify the provider/model/key work. Graceful if litellm absent."""
    if not full_model:
        return (False, "no model configured")
    try:
        import litellm
        r = litellm.completion(
            model=full_model,
            messages=[{"role": "user", "content": "Reply with exactly: ok"}],
            max_tokens=5, timeout=30, **(extra or {}))
        return (True, r["choices"][0]["message"]["content"].strip()[:60])
    except Exception as e:
        return (False, f"{type(e).__name__}: {e}")
~~~


## `knowit/insights.py` {-}

~~~python
"""Repo-level insights and per-file structural explanations (stdlib only)."""
from __future__ import annotations
import ast


def _is_entry(pf):
    return "__main__" in (pf.text or "")


def repo_insights(idx):
    g = idx.graph
    py = [p for p in idx.parsed_files if p.language == "python"]
    entry_set = {p.file for p in py if _is_entry(p)}

    hubs = []
    for nid, n in g.nodes.items():
        if n["type"] != "file":
            continue
        fan_out = len(g.successors(nid, "imports"))
        fan_in = len(g.predecessors(nid, "imports"))
        if fan_in + fan_out:
            hubs.append({"file": nid, "imported_by": fan_in, "imports": fan_out,
                         "degree": fan_in + fan_out})
    hubs.sort(key=lambda x: (x["degree"], x["imported_by"]), reverse=True)

    syms = [n["data"] for n in g.nodes.values() if n["type"] == "symbol"]
    complex_top = [{"symbol": d["qualname"], "file": d["file"],
                    "complexity": d.get("complexity", 0)}
                   for d in sorted(syms, key=lambda d: d.get("complexity", 0),
                                   reverse=True)[:8]]

    dead = []
    for nid, n in g.nodes.items():
        if n["type"] != "symbol":
            continue
        d = n["data"]
        if d["kind"] == "class" or d["file"] in entry_set:
            continue
        nm = d["name"]
        if nm.startswith("__") and nm.endswith("__"):
            continue
        if not g.callers(nid):
            dead.append({"symbol": d["qualname"], "file": d["file"]})
    dead.sort(key=lambda x: x["file"])

    comps = [d.get("complexity", 0) for d in syms if d.get("kind") != "class"]
    return {
        "entry_files": sorted(entry_set),
        "hub_files": hubs[:8],
        "complex_symbols": complex_top,
        "likely_unused": dead[:15],
        "loc_total": sum(p.loc for p in py),
        "avg_complexity": round(sum(comps) / len(comps), 2) if comps else 0,
        "n_python": len(py),
        "n_symbols": len(syms),
    }


def file_summary(idx, file_rel):
    g = idx.graph
    pf = next((p for p in idx.parsed_files if p.file == file_rel), None)
    if pf is None:
        return None
    try:
        purpose = ast.get_docstring(ast.parse(pf.text)) or ""
    except Exception:
        purpose = ""
    defines = [{"symbol": s.qualname, "kind": s.kind, "complexity": s.complexity,
                "lines": f"{s.start_line}-{s.end_line}", "calls": len(s.calls)}
               for s in pf.symbols]
    internal_deps = sorted(g.successors(file_rel, "imports"))
    dependents = sorted(g.predecessors(file_rel, "imports"))
    api = []
    for s in pf.symbols:
        ext = sorted({g.get(c)["data"]["file"] for c in g.callers(s.id)
                      if g.get(c) and g.get(c)["data"].get("file") != file_rel})
        if ext:
            api.append({"symbol": s.qualname, "used_by": ext})
    return {
        "file": file_rel, "language": pf.language, "loc": pf.loc, "purpose": purpose,
        "imports": pf.imports, "internal_deps": internal_deps, "dependents": dependents,
        "defines": defines, "public_api": api, "error": pf.error,
        "complexity_total": sum(s.complexity for s in pf.symbols),
        "fan_in": len(dependents), "fan_out": len(internal_deps),
    }


# ---------------- Phase 3: language breakdown, API & DB maps ----------------
import re as _re
from collections import defaultdict as _dd

_ROUTE = _re.compile(r'@(\w+)\.(get|post|put|delete|patch|route)\(\s*["\']([^"\']+)', _re.I)
_TABLE = _re.compile(r'__tablename__\s*=\s*["\']([^"\']+)')
_DB_BASES = {"base", "model", "declarativebase", "sqlmodel"}


def language_breakdown(idx):
    sym_by_file = _dd(int)
    for n in idx.graph.nodes.values():
        if n["type"] == "symbol":
            sym_by_file[n["data"]["file"]] += 1
    agg = _dd(lambda: {"files": 0, "loc": 0, "symbols": 0})
    for p in idx.parsed_files:
        a = agg[p.language]
        a["files"] += 1
        a["loc"] += p.loc
        a["symbols"] += sym_by_file.get(p.file, 0)
    return [{"language": k, **v} for k, v in
            sorted(agg.items(), key=lambda x: -x[1]["loc"])]


def api_map(idx):
    out = []
    for p in idx.parsed_files:
        if p.language not in ("python", "javascript", "typescript"):
            continue
        for m in _ROUTE.finditer(p.text or ""):
            verb = m.group(2).upper()
            out.append({"method": "ANY" if verb == "ROUTE" else verb,
                        "path": m.group(3), "file": p.file})
    return out


def db_map(idx):
    out = []
    for n in idx.graph.nodes.values():
        if n["type"] == "symbol" and n["data"]["kind"] == "class":
            bs = [b.split(".")[-1].lower() for b in n["data"].get("bases", [])]
            if any(b in _DB_BASES for b in bs):
                out.append({"model": n["data"]["qualname"], "file": n["data"]["file"],
                            "table": ""})
    for p in idx.parsed_files:
        for m in _TABLE.finditer(p.text or ""):
            out.append({"model": "(table)", "file": p.file, "table": m.group(1)})
    return out
~~~


## `knowit/diagram.py` {-}

~~~python
"""Generate Mermaid diagrams from the code graph."""
from __future__ import annotations
import os
import re


def _safe(s):
    return "n_" + re.sub(r"[^0-9a-zA-Z]", "_", s)


def _label(s):
    return s.replace('"', "'")


def architecture_mermaid(idx, max_nodes=60):
    """File-level import/dependency graph (Mermaid flowchart, grouped by directory)."""
    g = idx.graph
    files = [nid for nid, n in g.nodes.items()
             if n["type"] == "file" and n["data"].get("language") == "python"]
    edges = []
    for f in files:
        for dst in g.successors(f, "imports"):
            d = g.get(dst)
            if d and d["type"] == "file":
                edges.append((f, dst))

    if len(files) > max_nodes:
        keep = {x for e in edges for x in e}
        files = [f for f in files if f in keep][:max_nodes]
        fset = set(files)
        edges = [(a, b) for a, b in edges if a in fset and b in fset]

    groups = {}
    for f in files:
        parts = f.replace("\\", "/").split("/")
        d = parts[0] if len(parts) > 1 else "(root)"
        groups.setdefault(d, []).append(f)

    lines = ["flowchart LR"]
    multi = len(groups) > 1
    for d, fs in sorted(groups.items()):
        if multi:
            lines.append(f'  subgraph {_safe(d)}["{_label(d)}/"]')
        for f in fs:
            nsym = len(g.successors(f, "contains"))
            lines.append(f'    {_safe(f)}["{_label(os.path.basename(f))} ({nsym})"]')
        if multi:
            lines.append("  end")
    for a, b in edges:
        lines.append(f"  {_safe(a)} --> {_safe(b)}")
    if not edges:
        lines.append("  %% no internal import edges detected")
    return "\n".join(lines)


def neighborhood_mermaid(idx, node_id, radius=1):
    """Call-graph neighborhood around a symbol (Mermaid flowchart)."""
    g = idx.graph
    if node_id not in g.nodes:
        return "flowchart LR\n  empty[\"(symbol not found)\"]"
    nodes = {node_id}
    frontier = {node_id}
    for _ in range(radius):
        nxt = set()
        for n in frontier:
            nxt.update(g.callees(n))
            nxt.update(g.callers(n))
        nodes |= nxt
        frontier = nxt

    lines = ["flowchart LR"]
    for n in nodes:
        data = g.get(n)["data"]
        focus = ":::focus" if n == node_id else ""
        lines.append(f'  {_safe(n)}["{_label(data.get("qualname", n))}"]{focus}')
    seen = set()
    for n in nodes:
        for c in g.callees(n):
            if c in nodes and (n, c) not in seen:
                seen.add((n, c))
                lines.append(f"  {_safe(n)} --> {_safe(c)}")
    lines.append("  classDef focus fill:#2E75B6,color:#ffffff,stroke:#1F3864;")
    return "\n".join(lines)


# ============================ Graphviz DOT (native render) ============================
_CODE_LANGS = ("python", "javascript", "typescript")


def architecture_dot(idx, max_nodes=80):
    """File dependency graph as Graphviz DOT (rendered natively by Streamlit)."""
    g = idx.graph
    files = [nid for nid, n in g.nodes.items()
             if n["type"] == "file" and n["data"].get("language") in _CODE_LANGS]
    edges = [(f, d) for f in files for d in g.successors(f, "imports")
             if g.get(d) and g.get(d)["type"] == "file"]
    if len(files) > max_nodes:
        keep = {x for e in edges for x in e}
        files = [f for f in files if f in keep][:max_nodes]
        fs = set(files)
        edges = [(a, b) for a, b in edges if a in fs and b in fs]
    groups = {}
    for f in files:
        parts = f.replace("\\", "/").split("/")
        groups.setdefault(parts[0] if len(parts) > 1 else "(root)", []).append(f)
    out = ['digraph G {', '  rankdir=LR;',
           '  node [shape=box style="rounded,filled" fillcolor="#EAF1FB" '
           'color="#2E75B6" fontname="Helvetica" fontsize=10];',
           '  edge [color="#9aa7b4"];']
    multi = len(groups) > 1
    for i, (d, fs) in enumerate(sorted(groups.items())):
        if multi:
            out.append(f'  subgraph cluster_{i} {{ label="{d}/"; style=rounded; color="#cccccc";')
        for f in fs:
            nsym = len(g.successors(f, "contains"))
            out.append(f'    "{f}" [label="{os.path.basename(f)}\\n({nsym})"];')
        if multi:
            out.append('  }')
    for a, b in edges:
        out.append(f'  "{a}" -> "{b}";')
    if not edges:
        out.append('  label="no internal import edges detected"; labelloc=b;')
    out.append('}')
    return "\n".join(out)


def class_dot(idx, max_classes=40):
    """UML-ish class diagram with methods and inheritance edges."""
    g = idx.graph
    classes = [(nid, n["data"]) for nid, n in g.nodes.items()
               if n["type"] == "symbol" and n["data"]["kind"] == "class"][:max_classes]
    out = ['digraph G {', '  rankdir=BT;',
           '  node [shape=record fontname="Helvetica" fontsize=10 style=filled '
           'fillcolor="#F3F7FC" color="#2E75B6"];']
    present = {nid for nid, _ in classes}
    for nid, d in classes:
        methods = [g.get(m)["data"]["name"] for m in g.predecessors(nid, "method_of")]
        body = "\\l".join(methods) + "\\l" if methods else ""
        label = d["qualname"] + ("|" + body if body else "")
        out.append(f'  "{nid}" [label="{{{label}}}"];')
    for nid, d in classes:
        for base in g.successors(nid, "inherits"):
            if base in present:
                out.append(f'  "{nid}" -> "{base}" [arrowhead=onormal];')
    if not classes:
        out.append('  label="no classes found"; labelloc=b;')
    out.append('}')
    return "\n".join(out)


def callflow_dot(idx, node_id, depth=3, max_nodes=40):
    """Downstream call flow from a symbol (approximates a sequence/data-flow view)."""
    g = idx.graph
    if node_id not in g.nodes:
        return 'digraph G { "n" [label="(symbol not found)"]; }'
    nodes, edges, frontier = {node_id}, set(), [node_id]
    for _ in range(depth):
        nxt = []
        for n in frontier:
            for c in g.callees(n):
                edges.add((n, c))
                if c not in nodes and len(nodes) < max_nodes:
                    nodes.add(c)
                    nxt.append(c)
        frontier = nxt
    out = ['digraph G {', '  rankdir=LR;',
           '  node [shape=box style="rounded,filled" fillcolor="#F3F7FC" '
           'color="#2E75B6" fontname="Helvetica" fontsize=10];']
    for n in nodes:
        d = g.get(n)["data"]
        foc = ' fillcolor="#2E75B6" fontcolor="white"' if n == node_id else ''
        out.append(f'  "{n}" [label="{d.get("qualname", n)}"{foc}];')
    for a, b in edges:
        if a in nodes and b in nodes:
            out.append(f'  "{a}" -> "{b}";')
    out.append('}')
    return "\n".join(out)


def knowledge_dot(idx, max_nodes=70):
    """Files + their symbols + relationships — a compact knowledge graph."""
    g = idx.graph
    out = ['digraph G {', '  rankdir=LR;', '  node [fontname="Helvetica" fontsize=9];']
    count = 0
    sym_nodes = set()
    for nid, n in g.nodes.items():
        if count >= max_nodes:
            break
        if n["type"] == "file" and n["data"].get("language") in _CODE_LANGS:
            out.append(f'  "{nid}" [shape=folder fillcolor="#FFF3D6" style=filled color="#C9A227"];')
            count += 1
            for sym in g.successors(nid, "contains")[:8]:
                if count >= max_nodes:
                    break
                d = g.get(sym)["data"]
                out.append(f'  "{sym}" [shape=ellipse label="{d["name"]}" '
                           f'fillcolor="#F3F7FC" style=filled color="#2E75B6"];')
                out.append(f'  "{nid}" -> "{sym}" [color="#cccccc" arrowhead=none];')
                sym_nodes.add(sym)
                count += 1
    for a in list(sym_nodes):
        for b in g.callees(a):
            if b in sym_nodes:
                out.append(f'  "{a}" -> "{b}" [color="#2E75B6"];')
    out.append('}')
    return "\n".join(out)


# ============================ Interactive explorer ============================
ROLE_COLOR = {"entry": "#2E8B57", "hub": "#2E75B6", "unused": "#C0392B",
              "focus": "#7E3FF2", "normal": "#EAF1FB"}
_EDGE_TYPES = ("calls", "imports", "contains", "method_of", "inherits")


def _tooltip(node):
    d = node["data"]
    if node["type"] == "file":
        return f"{d.get('language', 'file')} · {d.get('loc', 0)} LOC".replace('"', "'")
    doc = (d.get("doc") or "").splitlines()
    doc = doc[0] if doc else ""
    return (f"{d.get('qualname', '')} · {d.get('kind', '')} · "
            f"cx {d.get('complexity', 0)} · {doc}").replace('"', "'").replace("\n", " ")[:150]


def node_roles(idx):
    from .insights import repo_insights
    ins = repo_insights(idx)
    roles = {}
    for f in ins["entry_files"]:
        roles[f] = "entry"
    for h in ins["hub_files"][:5]:
        roles.setdefault(h["file"], "hub")
    for u in ins["likely_unused"]:
        roles[f"{u['file']}::{u['symbol']}"] = "unused"
    return roles


def neighborhood(idx, focus, depth=1, etypes=_EDGE_TYPES):
    g = idx.graph
    if focus not in g.nodes:
        return set(), []
    etypes = tuple(etypes) or _EDGE_TYPES
    nodes, frontier = {focus}, {focus}
    for _ in range(max(1, depth)):
        nxt = set()
        for n in list(frontier):
            for d, t in g._out.get(n, []):
                if t in etypes:
                    nxt.add(d)
            for srcn, t in g._in.get(n, []):
                if t in etypes:
                    nxt.add(srcn)
        nodes |= nxt
        frontier = nxt
    edges = [(s, d, t) for s, d, t in g.all_edges()
             if t in etypes and s in nodes and d in nodes]
    return nodes, edges


def focused_dot(idx, focus, nodes, edges, roles, path=()):
    g = idx.graph
    pset = set(path)
    out = ["digraph G {", "  rankdir=LR;",
           '  node [shape=box style="rounded,filled" fontname="Helvetica" fontsize=10 color="#2E75B6"];']
    for n in nodes:
        nd = g.get(n)
        if not nd:
            continue
        d = nd["data"]
        label = d.get("qualname") or os.path.basename(n)
        role = "focus" if n == focus else roles.get(n, "normal")
        fill = ROLE_COLOR.get(role, "#EAF1FB")
        fc = "#ffffff" if role in ("entry", "hub", "unused", "focus") else "#000000"
        pen = " penwidth=3" if n in pset else ""
        out.append(f'  "{n}" [label="{label}" fillcolor="{fill}" fontcolor="{fc}" '
                   f'tooltip="{_tooltip(nd)}"{pen}];')
    for s, d, t in edges:
        col = "#7E3FF2" if (s in pset and d in pset) else "#9aa7b4"
        out.append(f'  "{s}" -> "{d}" [color="{col}" tooltip="{t}"];')
    out.append("}")
    return "\n".join(out)


def pyvis_html(idx, focus, nodes, edges, roles, height=540):
    """Interactive draggable/zoom/hover canvas via pyvis with INLINED assets (no CDN).
    Returns HTML string, or None if pyvis isn't installed."""
    try:
        from pyvis.network import Network
    except Exception:
        return None
    g = idx.graph
    net = Network(height=f"{height}px", width="100%", directed=True,
                  cdn_resources="in_line", bgcolor="#ffffff", font_color="#222222")
    net.barnes_hut(spring_length=120)
    for n in nodes:
        nd = g.get(n)
        if not nd:
            continue
        role = "focus" if n == focus else roles.get(n, "normal")
        net.add_node(n, label=(nd["data"].get("qualname") or os.path.basename(n)),
                     title=_tooltip(nd), color=ROLE_COLOR.get(role, "#EAF1FB"),
                     size=26 if role == "focus" else 15)
    for s, d, t in edges:
        if s in nodes and d in nodes:
            net.add_edge(s, d, title=t)
    try:
        return net.generate_html(notebook=False)
    except Exception:
        try:
            return net.generate_html()
        except Exception:
            return None


def path_between(idx, a, b, etypes=("calls", "imports")):
    from collections import deque
    g = idx.graph
    if a not in g.nodes or b not in g.nodes:
        return []
    prev, q = {a: None}, deque([a])
    while q:
        n = q.popleft()
        if n == b:
            break
        for d, t in g._out.get(n, []):
            if t in etypes and d not in prev:
                prev[d] = n
                q.append(d)
    if b not in prev:
        return []
    path, cur = [], b
    while cur is not None:
        path.append(cur)
        cur = prev[cur]
    return list(reversed(path))


def explain_view_llm(idx, nodes, edges, focus, model, extra=None):
    if not model:
        return None
    try:
        from . import llm
        g = idx.graph
        nn = [g.get(n)["data"].get("qualname", n) for n in list(nodes)[:30]]
        ee = [f"{g.get(s)['data'].get('qualname', s)} -{t}-> {g.get(d)['data'].get('qualname', d)}"
              for s, d, t in edges[:40]]
        prompt = ("Explain this part of a codebase to a new engineer in <120 words. "
                  f"Focus: {g.get(focus)['data'].get('qualname', focus)}.\n"
                  f"Components: {nn}\nRelationships: {ee}")
        r = llm._complete(model, [
            {"role": "system", "content": "You teach codebases clearly and concisely."},
            {"role": "user", "content": prompt}], extra=extra, temperature=0.2, timeout=60)
        return r["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return f"[LLM unavailable: {type(e).__name__}: {e}]"
~~~


## `knowit/teach.py` {-}

~~~python
"""Phase 2 — Teach. Learning artifacts generated from the code graph (work offline);
LLM enrichment (richer cards, answer grading) when a provider is configured."""
from __future__ import annotations
import random

from .insights import repo_insights


def _symbols(idx):
    return [(nid, n["data"]) for nid, n in idx.graph.nodes.items() if n["type"] == "symbol"]


def _code_files(idx):
    return [p.file for p in idx.parsed_files
            if p.language in ("python", "javascript", "typescript")]


# ---------------- learning path ----------------
def learning_path(idx):
    g = idx.graph
    ins = repo_insights(idx)
    entry = list(ins["entry_files"])
    hubs = [h["file"] for h in ins["hub_files"]]
    files = _code_files(idx)
    ordered, seen = [], set()
    for f in entry + hubs + sorted(files):
        if f in files and f not in seen:
            seen.add(f)
            ordered.append(f)
    stops = []
    for f in ordered:
        syms = [d for _, d in _symbols(idx) if d["file"] == f]
        syms.sort(key=lambda d: -d.get("complexity", 0))
        why = ("entry point — start here" if f in entry else
               "hub — many files depend on it" if f in hubs[:5] else "supporting module")
        stops.append({"file": f, "why": why,
                      "key_symbols": [s["qualname"] for s in syms[:5]],
                      "depends_on": sorted(g.successors(f, "imports"))})
    return stops


# ---------------- flashcards (structural) ----------------
def flashcards(idx, limit=14):
    g = idx.graph
    cards = []
    for nid, d in _symbols(idx):
        loc = f"{d['file']}:{d['start']}"
        if d["kind"] == "class":
            cards.append({"q": f"What is class `{d['qualname']}`?",
                          "a": (d.get("doc") or "No docstring.") + f"  [{loc}]",
                          "ref": d["file"]})
        else:
            callees = [g.get(c)["data"]["name"] for c in g.callees(nid)]
            a = (d.get("doc") or "No docstring.")
            if callees:
                a += f" Calls: {', '.join(callees[:6])}."
            cards.append({"q": f"What does `{d['qualname']}` do?  ({d['file']})",
                          "a": a + f"  [{loc}]", "ref": d["file"]})
    for f in _code_files(idx):
        deps = sorted(g.successors(f, "imports"))
        if deps:
            cards.append({"q": f"What does `{f}` depend on internally?",
                          "a": ", ".join(deps), "ref": f})
    return cards[:limit]


# ---------------- quiz (3 levels, MCQ with distractors) ----------------
def quiz(idx, level="beginner", n=5, seed=None):
    rng = random.Random(seed)
    g = idx.graph
    syms = [d for _, d in _symbols(idx)]
    qualnames = [d["qualname"] for d in syms]
    funcnames = [d["name"] for d in syms if d["kind"] != "class"]
    files = _code_files(idx)
    ins = repo_insights(idx)
    qs = []

    def mc(question, correct, pool, ref, expl):
        distract = [x for x in dict.fromkeys(pool) if x != correct]
        rng.shuffle(distract)
        opts = [correct] + distract[:3]
        rng.shuffle(opts)
        return {"question": question, "options": opts, "answer": opts.index(correct),
                "explanation": expl, "ref": ref}

    if level == "beginner":
        for d in syms:
            if d["kind"] != "class":
                qs.append(mc(f"Which file defines `{d['qualname']}`?", d["file"], files,
                             d["file"], f"`{d['qualname']}` lives in {d['file']}."))
    elif level == "intermediate":
        for nid, d in _symbols(idx):
            cs = g.callees(nid)
            if cs:
                cn = g.get(cs[0])["data"]["name"]
                qs.append(mc(f"Which function does `{d['qualname']}` call?", cn, funcnames,
                             d["file"], f"`{d['qualname']}` calls `{cn}`."))
    else:  # senior
        if ins["complex_symbols"]:
            t = ins["complex_symbols"][0]
            qs.append(mc("Which symbol has the highest cyclomatic complexity?",
                         t["symbol"], qualnames, t["file"],
                         f"`{t['symbol']}` (complexity {t['complexity']})."))
        for ef in ins["entry_files"][:1]:
            qs.append(mc("Which file is an entry point?", ef, files, ef,
                         "It contains a __main__ / app bootstrap."))
        if ins["likely_unused"]:
            u = ins["likely_unused"][0]
            qs.append(mc("Which symbol is defined but never called in-repo?",
                         u["symbol"], qualnames, u["file"], "No in-repo callers found."))
        for h in ins["hub_files"][:2]:
            deps = g.predecessors(h["file"], "imports")
            if deps:
                dn = g.get(deps[0])["data"] if False else deps[0]
                qs.append(mc(f"Which file imports `{h['file']}`?", dn, files, h["file"],
                             f"{dn} depends on {h['file']}."))
    rng.shuffle(qs)
    return qs[:n]


# ---------------- interview (structural prompts + expected points) ----------------
def interview(idx, n=5):
    g = idx.graph
    ins = repo_insights(idx)
    qs = []
    for ef in ins["entry_files"][:2]:
        callees = []
        for nid, d in _symbols(idx):
            if d["file"] == ef:
                callees += [g.get(c)["data"]["qualname"] for c in g.callees(nid)]
        qs.append({"question": f"Walk through, end to end, what happens when `{ef}` runs.",
                   "expected": callees[:6] or ["the main flow"], "ref": ef})
    if ins["complex_symbols"]:
        c = ins["complex_symbols"][0]
        qs.append({"question": f"Explain the responsibility and logic of `{c['symbol']}` "
                   f"(the most complex symbol).", "expected": [c["symbol"], c["file"]],
                   "ref": c["file"]})
    if ins["likely_unused"]:
        u = ins["likely_unused"][0]
        qs.append({"question": f"`{u['symbol']}` is defined but never called in-repo. Why "
                   "might that be, and what would you do?",
                   "expected": ["unused / dead code", "remove or wire it up"], "ref": u["file"]})
    for h in ins["hub_files"][:2]:
        deps = sorted(g.predecessors(h["file"], "imports"))
        qs.append({"question": f"What depends on `{h['file']}`, and what breaks if its "
                   "interface changes?", "expected": deps or ["its dependents"], "ref": h["file"]})
    return qs[:n]


def grade_answer_llm(question, answer, expected, context, model, extra=None):
    """LLM feedback on an interview answer; None if no model, graceful on error."""
    if not model:
        return None
    try:
        from . import llm
        prompt = (f"Interview question: {question}\n"
                  f"Points a strong answer should mention: {expected}\n"
                  f"Candidate answer: {answer}\n\nCode context:\n{context[:3000]}\n\n"
                  "Give brief feedback (2–4 sentences): what's correct, what's missing, "
                  "and end with 'Score: X/10'.")
        r = llm._complete(model, [
            {"role": "system", "content": "You are a senior engineer running a code interview."},
            {"role": "user", "content": prompt}], extra=extra, temperature=0.2, timeout=60)
        return r["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return f"[LLM unavailable: {type(e).__name__}: {e}]"


# ---------------- learning gaps ----------------
def learning_gaps(idx, explored_files):
    g = idx.graph
    files = _code_files(idx)
    fset = set(files)
    explored = set(explored_files) & fset
    used = set()
    for f in explored:
        for d in g.successors(f, "imports"):
            if d in fset and d not in explored:
                used.add(d)
    return {"total": len(files), "explored": len(explored),
            "coverage": round(len(explored) / len(files), 2) if files else 0.0,
            "unexplored": sorted(fset - explored),
            "used_but_unexplored": sorted(used)}
~~~


## `knowit/track.py` {-}

~~~python
"""Phase 4 — Track. Snapshot a repo at commits and diff the structure over time:
changelog, architecture delta, and learning delta. Uses git (worktrees) — works on any
git repo; structural by default, with optional LLM narration."""
from __future__ import annotations
import hashlib
import json
import os
import subprocess

from .config import CONFIG

CODE_LANGS = ("python", "javascript", "typescript")


def _git(args, cwd, timeout=120):
    return subprocess.run(["git"] + args, cwd=cwd, capture_output=True, text=True,
                          timeout=timeout)


def is_git(path):
    try:
        return _git(["rev-parse", "--is-inside-work-tree"], path).returncode == 0
    except Exception:
        return False


def git_log(path, n=30):
    if not is_git(path):
        return []
    r = _git(["log", f"-n{n}", "--pretty=format:%H|%h|%an|%ad|%s", "--date=short"], path)
    out = []
    for line in r.stdout.splitlines():
        parts = line.split("|", 4)
        if len(parts) == 5:
            out.append({"sha": parts[0], "short": parts[1], "author": parts[2],
                        "date": parts[3], "subject": parts[4]})
    return out


def fingerprint(idx, commit):
    files, symbols = {}, {}
    for p in idx.parsed_files:
        if p.language in CODE_LANGS:
            files[p.file] = p.loc
            for sym in p.symbols:
                key = f"{sym.file}::{sym.qualname}"
                symbols[key] = {
                    "file": sym.file, "kind": sym.kind, "complexity": sym.complexity,
                    "hash": hashlib.sha1((sym.code or "").encode("utf-8", "replace")).hexdigest()[:12],
                }
    imports = sorted({(s, d) for s, d, _ in idx.graph.all_edges("imports")})
    calls = sorted({(s, d) for s, d, _ in idx.graph.all_edges("calls")})
    return {"commit": commit, "files": files, "symbols": symbols,
            "imports": imports, "calls": calls}


def snapshot(source_path, commit, config=CONFIG):
    """Build a structural fingerprint of the repo at `commit` (cached as JSON)."""
    from .pipeline import build_index
    snaps = os.path.join(config.data_dir, "snapshots")
    os.makedirs(snaps, exist_ok=True)
    cache = os.path.join(snaps, f"{commit[:12]}.json")
    if os.path.exists(cache):
        try:
            return json.load(open(cache))
        except Exception:
            pass
    wt = os.path.join(config.data_dir, "worktrees", commit[:12])
    add = _git(["worktree", "add", "--detach", "--force", wt, commit], source_path)
    if add.returncode != 0:
        raise RuntimeError(f"git worktree failed: {add.stderr.strip()[:300]}")
    try:
        idx = build_index(wt, config, use_cache=False, register=False)
        fp = fingerprint(idx, commit)
    finally:
        _git(["worktree", "remove", "--force", wt], source_path)
    try:
        json.dump(fp, open(cache, "w"))
    except Exception:
        pass
    return fp


def diff(base, head):
    bf, hf = set(base["files"]), set(head["files"])
    bs, hs = base["symbols"], head["symbols"]
    bk, hk = set(bs), set(hs)
    modified = sorted(k for k in (bk & hk) if bs[k]["hash"] != hs[k]["hash"])
    complexity = [{"symbol": k.split("::")[-1], "file": bs[k]["file"],
                   "from": bs[k]["complexity"], "to": hs[k]["complexity"]}
                  for k in (bk & hk) if bs[k]["complexity"] != hs[k]["complexity"]]
    bi, hi = {tuple(x) for x in base["imports"]}, {tuple(x) for x in head["imports"]}
    return {
        "files_added": sorted(hf - bf), "files_removed": sorted(bf - hf),
        "symbols_added": sorted(hk - bk), "symbols_removed": sorted(bk - hk),
        "symbols_modified": modified,
        "imports_added": sorted(hi - bi), "imports_removed": sorted(bi - hi),
        "complexity_changes": complexity,
    }


def changelog_text(d):
    lines = []

    def section(title, items, fmt=lambda x: x):
        if items:
            lines.append(f"**{title}** ({len(items)})")
            lines.extend("  - " + fmt(i) for i in items[:25])

    section("Files added", d["files_added"])
    section("Files removed", d["files_removed"])
    section("Symbols added", [s.split("::")[-1] + f"  ({s.split('::')[0]})" for s in d["symbols_added"]])
    section("Symbols removed", [s.split("::")[-1] + f"  ({s.split('::')[0]})" for s in d["symbols_removed"]])
    section("Symbols modified", [s.split("::")[-1] + f"  ({s.split('::')[0]})" for s in d["symbols_modified"]])
    section("New imports", d["imports_added"], lambda e: f"{e[0]} → {e[1]}")
    section("Removed imports", d["imports_removed"], lambda e: f"{e[0]} → {e[1]}")
    section("Complexity changes",
            [f"{c['symbol']} ({c['file']}): {c['from']} → {c['to']}" for c in d["complexity_changes"]])
    return "\n".join(lines) if lines else "_No structural changes between these commits._"


def architecture_delta_dot(base, head):
    bi = {tuple(x) for x in base["imports"]}
    hi = {tuple(x) for x in head["imports"]}
    bf, hf = set(base["files"]), set(head["files"])
    nodes = bf | hf
    out = ["digraph G {", "  rankdir=LR;",
           '  node [shape=box style="rounded,filled" fontname="Helvetica" fontsize=10];']
    for f in sorted(nodes):
        if f in hf and f not in bf:
            out.append(f'  "{f}" [fillcolor="#DEF7E0" color="#2E8B57" label="{f} (new)"];')
        elif f in bf and f not in hf:
            out.append(f'  "{f}" [fillcolor="#FBE3E3" color="#C0392B" label="{f} (removed)"];')
        else:
            out.append(f'  "{f}" [fillcolor="#EAF1FB" color="#2E75B6"];')
    for s, d in sorted(hi - bi):
        out.append(f'  "{s}" -> "{d}" [color="#2E8B57" penwidth=2 label="+"];')
    for s, d in sorted(bi - hi):
        out.append(f'  "{s}" -> "{d}" [color="#C0392B" style=dashed label="-"];')
    for s, d in sorted(bi & hi):
        out.append(f'  "{s}" -> "{d}" [color="#bbbbbb"];')
    out.append('}')
    return "\n".join(out)


def learning_delta(d, explored):
    explored = set(explored)
    changed_files = set(d["files_added"]) | set(d["files_removed"])
    for key in d["symbols_modified"] + d["symbols_added"] + d["symbols_removed"]:
        changed_files.add(key.split("::")[0])
    return {
        "re_learn": sorted(explored & changed_files),     # you studied these and they changed
        "new_files": sorted(set(d["files_added"]) - explored),
        "removed_files": sorted(set(d["files_removed"]) & explored),
    }


def narrate_llm(d, model, extra=None):
    if not model:
        return None
    try:
        from . import llm
        prompt = ("Write a short, friendly changelog (5-8 bullets) describing how this "
                  "codebase changed, grouping related edits and noting likely intent.\n\n"
                  f"Structured diff:\n{json.dumps(d, indent=2)[:3500]}")
        r = llm._complete(model, [
            {"role": "system", "content": "You summarize code changes for engineers."},
            {"role": "user", "content": prompt}], extra=extra, temperature=0.3, timeout=60)
        return r["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return f"[LLM unavailable: {type(e).__name__}: {e}]"
~~~


## `knowit/pipeline.py` {-}

~~~python
from __future__ import annotations
import hashlib
import json
import os
import pickle
from collections import defaultdict

from .config import CONFIG
from .ingest import ingest
from .parsing import parse_file
from .graph import build_graph
from .chunking import make_chunks
from .index import BM25Retriever, ChromaRetriever
from .retrieval import hybrid_search, assemble_context
from .llm import synthesize


class RepoIndex:
    def __init__(self, meta, parsed_files, graph, chunks, lexical, dense, config):
        self.meta = meta
        self.parsed_files = parsed_files
        self.graph = graph
        self.chunks = chunks
        self.lexical = lexical
        self.dense = dense
        self.config = config
        self.chunks_by_id = {c.id: c for c in chunks}
        self.chunks_by_node = defaultdict(list)
        for c in chunks:
            self.chunks_by_node[c.node_id].append(c)

    def stats(self):
        s = self.graph.stats()
        return {
            "repo": self.meta.name, "commit": self.meta.commit[:12],
            "is_git": self.meta.is_git, "files_parsed": len(self.parsed_files),
            "python_files": sum(1 for p in self.parsed_files
                                if p.language in ("python", "javascript", "typescript")),
            "parse_errors": sum(1 for p in self.parsed_files if p.error),
            "symbols": s["node_types"].get("symbol", 0), "chunks": len(self.chunks),
            "graph_nodes": s["nodes"], "graph_edges": s["edges"],
            "edge_types": s["edge_types"],
            "retriever": "bm25 + chroma (hybrid RRF)" if self.dense is not None else "bm25",
        }

    def search(self, query):
        return hybrid_search(query, self.lexical, self.dense, self.graph,
                             self.chunks_by_node, k=self.config.top_k,
                             expand=self.config.graph_expand)

    def ask(self, query):
        retrieved = self.search(query)
        context = assemble_context(retrieved)
        answer, used = synthesize(query, context, self.config.llm_model,
                                  self.config.llm_kwargs)
        return {"question": query, "answer": answer, "used_llm": used,
                "retrieved": retrieved, "context": context}


# ---------------- cache + multi-repo registry ----------------
def _signature(meta, files):
    h = hashlib.sha1()
    h.update((meta.commit or "").encode())
    if meta.commit == "working-tree":
        for rel, ab in sorted(files):
            try:
                st = os.stat(ab)
                h.update(f"{rel}:{int(st.st_mtime)}:{st.st_size}".encode())
            except OSError:
                pass
    return h.hexdigest()[:16]


def _cache_file(data_dir, meta, sig):
    d = os.path.join(data_dir, "cache")
    os.makedirs(d, exist_ok=True)
    safe = "".join(ch if ch.isalnum() else "_" for ch in meta.name)[:40] or "repo"
    return os.path.join(d, f"{safe}_{sig}.pkl")


def _build_retrievers(chunks, backend, data_dir, sig):
    lexical = BM25Retriever()
    lexical.index(chunks)
    dense = None
    if backend in ("auto", "hybrid", "chroma"):
        try:
            dense = ChromaRetriever(data_dir, sig)
            dense.index(chunks)
        except Exception:
            if backend == "chroma":
                raise
            dense = None
    return lexical, dense


def record_repo(data_dir, source, meta):
    try:
        os.makedirs(data_dir, exist_ok=True)
        f = os.path.join(data_dir, "repos.json")
        reg = json.load(open(f)) if os.path.exists(f) else []
        reg = [e for e in reg if e.get("source") != source]
        reg.insert(0, {"source": source, "name": meta.name, "commit": meta.commit[:12]})
        json.dump(reg[:20], open(f, "w"), indent=2)
    except Exception:
        pass


def recent_repos(data_dir):
    try:
        f = os.path.join(data_dir, "repos.json")
        return json.load(open(f)) if os.path.exists(f) else []
    except Exception:
        return []


def build_index(source, config=CONFIG, progress=None, use_cache=None, register=True):
    def log(m):
        if progress:
            progress(m)

    if use_cache is None:
        use_cache = config.use_cache
    log("Ingesting repository ...")
    meta, code_files, doc_files = ingest(source, config.data_dir)
    files = code_files + doc_files
    sig = _signature(meta, files)
    cache = _cache_file(config.data_dir, meta, sig)

    parsed = graph = chunks = None
    if use_cache and os.path.exists(cache):
        try:
            log("Loading cached parse/graph/chunks ...")
            with open(cache, "rb") as fh:
                parsed, graph, chunks = pickle.load(fh)
        except Exception:
            parsed = graph = chunks = None

    if parsed is None:
        log(f"Parsing {len(code_files)} code + {len(doc_files)} doc files ...")
        parsed = [parse_file(rel, ab) for rel, ab in files]
        log("Building code graph ...")
        graph = build_graph(parsed)
        log("Chunking ...")
        chunks = make_chunks(parsed, meta.commit, config.chunk_max_lines)
        if use_cache:
            try:
                with open(cache, "wb") as fh:
                    pickle.dump((parsed, graph, chunks), fh)
            except Exception:
                pass

    log("Building retrievers ...")
    lexical, dense = _build_retrievers(chunks, config.embed_backend, config.data_dir, sig)
    if register:
        record_repo(config.data_dir, source, meta)
    log("Done.")
    return RepoIndex(meta, parsed, graph, chunks, lexical, dense, config)
~~~


## `knowit/eval_harness.py` {-}

~~~python
from __future__ import annotations
import json


def load_questions(path):
    with open(path, "r", encoding="utf-8") as fh:
        if path.endswith((".yaml", ".yml")):
            try:
                import yaml
            except Exception as e:
                raise RuntimeError("PyYAML not installed; use a .json question set") from e
            data = yaml.safe_load(fh)
        else:
            data = json.load(fh)
    if isinstance(data, dict) and "questions" in data:
        return data["questions"]
    return data


def _kw_coverage(text, keywords):
    if not keywords:
        return None
    t = (text or "").lower()
    return sum(1 for k in keywords if k.lower() in t) / len(keywords)


def run_eval(repo_index, questions, judge_model="", kw_threshold=0.5):
    from .llm import judge
    rows = []
    for q in questions:
        res = repo_index.ask(q["question"])
        files = [r.chunk.file for r in res["retrieved"]]
        exp_files = q.get("expect_files") or []
        retr_hit = (any(any(ef in f for f in files) for ef in exp_files)
                    if exp_files else None)
        text_for_kw = res["answer"] if res["used_llm"] else res["context"]
        kw_cov = _kw_coverage(text_for_kw, q.get("expect_keywords"))
        jscore = judge(q["question"], res["answer"], res["context"], judge_model) if judge_model else None

        if jscore is not None:
            passed = jscore >= 0.7
        elif exp_files or q.get("expect_keywords"):
            ok_retr = (retr_hit is None) or retr_hit
            ok_kw = (kw_cov is None) or (kw_cov >= kw_threshold)
            passed = bool(ok_retr and ok_kw)
        else:
            passed = None   # no expectations => manual review

        rows.append({
            "id": q.get("id", ""), "question": q["question"],
            "retrieval_hit": retr_hit, "kw_coverage": kw_cov, "judge": jscore,
            "passed": passed, "top_files": files[:4], "used_llm": res["used_llm"],
            "answer": res["answer"],
        })

    scored = [r for r in rows if r["passed"] is not None]
    n_pass = sum(1 for r in scored if r["passed"])
    pass_rate = (n_pass / len(scored)) if scored else 0.0
    summary = {"total": len(rows), "scored": len(scored), "passed": n_pass,
               "pass_rate": pass_rate, "gate_pass": pass_rate >= 0.8}
    return rows, summary
~~~
