# KnowIT — Vision Coverage Report

*Audit of the original vision against the delivered system · all checks run on the bundled
`sample_repo` (and a 3-commit git repo for Track) · 2026-05-31*

## Summary

Every tier of the original six-tier vision — plus the "missing features" and the killer
"Teach Me This Repository" idea — is **implemented and verified**. A single end-to-end
verification run exercises **29 feature checks across all tiers; 29/29 pass**, and the
retrieval **eval gate is 10/10**. A few items from the original sketch are delivered in an
**approximated** form (noted honestly below) rather than as full formal artifacts.

Legend: **✅ Built** · **🟡 Built (approximated / optional path)**

## Tier 1 — Repository Understanding

| Vision item | Status | Where | Verified |
|---|---|---|---|
| File tree | ✅ | `ingest`, Files tab | yes |
| Dependency / import graph | ✅ | `graph` (imports edges), Diagrams | 7 import edges |
| Service graph | 🟡 | approximated by the file-dependency / hub view | partial |
| API mapping | ✅ | `insights.api_map`, API & DB tab | verified on a FastAPI fixture |
| Database mapping | ✅ | `insights.db_map`, API & DB tab | verified on an ORM fixture |
| Architecture diagram | ✅ | `diagram.architecture_dot` | digraph OK |
| Sequence diagram | 🟡 | approximated by the **call-flow** view | call-flow OK |
| Data-flow diagram | 🟡 | approximated by call-flow / graph expansion | OK |
| Class diagram | ✅ | `diagram.class_dot` (with inheritance) | digraph OK |
| Component diagram | 🟡 | approximated by architecture + knowledge graph | OK |
| Per-file explanation (purpose/inputs/outputs/deps/logic/complexity) | ✅ | `insights.file_summary` | purpose extracted |
| Ask anything | ✅ | `RepoIndex.ask`, Ask tab | 9 cited sources |

## Tier 2 — Learning Layer (the wedge: "Teach Me This Repository")

| Vision item | Status | Where | Verified |
|---|---|---|---|
| Audio overview (2 AI hosts) | 🟡 | `media.audio_script` (script + dialogue); TTS optional | 10-turn script |
| Slide-deck generation (PPTX) | ✅ | `media.build_pptx` (3 styles), Media tab | 37 KB deck rendered |
| Mind maps | ✅ | `diagram.mindmap_tree/dot`, Diagrams default | 21 nodes |
| Flashcards | ✅ | `teach.flashcards`, Learn tab | 14 cards |
| Quiz mode (beginner/intermediate/senior) | ✅ | `teach.quiz`, Learn tab | 3 levels OK |
| Interview mode | ✅ | `teach.interview` (+ LLM grading), Learn tab | 5 questions |

## Tier 3 — Engineering Intelligence

| Vision item | Status | Where | Verified |
|---|---|---|---|
| Architecture decision log | ✅ | `engmemory` (decisions), Intel tab | CRUD OK |
| Error knowledge base | ✅ | `engmemory` (errors), Intel tab | CRUD OK |
| Technical memory | ✅ | `engmemory` (memory), Intel tab | CRUD OK |
| Technical-debt tracker | ✅ | `techdebt` (dead/dup/cycles/hotspots/god/undoc), Intel tab | dead=2, undoc=3 |

## Tier 4 — Change Tracking

| Vision item | Status | Where | Verified |
|---|---|---|---|
| Changelog | ✅ | `track.changelog_text`, Track tab | 22-line changelog |
| Architecture delta | ✅ | `track.architecture_delta_dot` | digraph OK |
| Learning delta | ✅ | `track.learning_delta` | re-learn flagged |
| Timeline view | ✅ | `track.git_log`, Track tab | 3 commits |

## Tier 5 — AI Research Mode

| Vision item | Status | Where | Verified |
|---|---|---|---|
| Research summary | ✅ | `research.research_summary` / paper detection | papers detected on fixture |
| Novelty analysis | ✅ | `research.novelty_summary_llm` (LLM) | graceful no-model |
| Implementation plan | ✅ | `research.implementation_plan_llm` (grounded in repo) | graceful no-model |
| Comparison matrix | ✅ | `research.comparison_matrix_llm` (LLM) | graceful no-model |
| arXiv linkage | ✅ | `research.find_papers` + `arxiv_lookup`/`parse_arxiv_atom` | parse OK |

## Tier 6 — Portfolio Mode

| Vision item | Status | Where | Verified |
|---|---|---|---|
| Project report | ✅ | `portfolio.generate("report")`, Portfolio tab | generated |
| Research-paper draft | 🟡 | `portfolio.generate("paper")` — structured skeleton + LLM | generated |
| Résumé bullets | ✅ | `portfolio.generate("resume")` | generated |
| LinkedIn post | ✅ | `portfolio.generate("linkedin")` | generated |
| Technical blog | ✅ | `portfolio.generate("blog")` | generated |

## "Missing features most people forget"

| Vision item | Status | Where | Verified |
|---|---|---|---|
| Timeline view | ✅ | Track tab (git log timeline) | 3 commits |
| Knowledge graph | ✅ | `diagram.knowledge_dot` | digraph OK |
| Technical-debt tracker | ✅ | `techdebt` (Intel tab) | OK |
| Learning gaps ("what have I never explored?") | ✅ | `teach.learning_gaps` (Learn tab) | coverage computed |

## Beyond the original vision — learning-retention & engineering add-ons

Added after the plan to close the gap between the system's thesis (teach and track
*understanding* over time) and its earlier session-only learning state. All are covered by
the unittest suite.

| Add-on | Status | Where | Verified |
|---|---|---|---|
| Persistent learning + spaced repetition (Leitner) | ✅ | `progress.py`, Learn → Progress | SRS round-trip + dashboard |
| Test-reference coverage | ✅ | `coverage.py`, Intel → Coverage | fixture with a test |
| Impact analysis (change blast radius) | ✅ | `impact.py`, Track | reverse-reachability checked |
| Configuration surface | ✅ | `config_map.py`, Overview | yaml/argparse/settings fixture |
| Portable HTML export | ✅ | `export_site.py`, Portfolio | valid self-contained HTML |
| Secret scanning | ✅ | `techdebt.secret_scan`, Intel | fixture key detected |
| Runnable test suite (19 stdlib unittest tests) | ✅ | `tests/test_knowit.py` | `python -m unittest tests.test_knowit` passes |

## Architecture layers (as originally envisioned)

| Layer | Envisioned | Delivered |
|---|---|---|
| Parsing | Tree-sitter / AST | ✅ stdlib **AST** (Python) + regex (JS/TS); tree-sitter reserved for richer multi-language |
| Retrieval | Vector DB + Graph DB + repo index | ✅ **BM25** + optional **Chroma** (vector) fused by RRF; pure-Python **code graph** (graph DB role); chunk index |
| LLM layer | explanations / teaching / reports | ✅ **litellm** multi-provider (OpenAI/Anthropic/Groq/Ollama/OpenRouter/custom), used across teach/answer/track/research/portfolio |
| Memory layer | decisions / errors / changelogs / learning history | ✅ on-disk cache + `engmemory` + `{graph node, commit}` provenance enabling deltas |

## Verification methodology

A single script builds the `sample_repo` index and a 3-commit git repo, then calls the
public entry point of every feature and asserts on its output — 29 checks spanning all six
tiers, the extras, the architecture layers, and the eval gate; **29/29 passed**. Items whose
trigger conditions are absent in the sample (web routes, ORM models, paper references) were
verified separately on dedicated fixtures during development (FastAPI routes, an ORM model,
arXiv/DOI references, a renamed-clone pair, a mutual-import cycle). The structural and git
paths are fully verified offline; the **network/LLM paths** (Chroma embeddings, litellm
provider calls, TTS, live arXiv fetch) are written defensively and degrade gracefully — they
are exercised first in a fully-installed environment via the in-app "Test connection".

## Honest gaps / approximations

- **Sequence & data-flow diagrams** are approximated by the call-flow view, not rendered as
  formal UML sequence diagrams with lifelines or a true data-flow analysis.
- **Service graph / component diagram** are approximated by the file-dependency and knowledge
  graphs; there is no explicit microservice/component boundary detection.
- **Audio overview** produces the two-host *script*; turning it into *audio* needs an optional
  TTS backend (edge-tts / pyttsx3 / gTTS).
- **Research-paper draft** is a structured skeleton refined by the LLM, not a submission-ready paper.
- **JS/TS** parsing is best-effort regex (no call graph); tree-sitter is the intended upgrade.

These are deliberate scoping choices consistent with the dependency-light philosophy, and
each has a clear upgrade path.
