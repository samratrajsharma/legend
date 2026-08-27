# Know Your Code — Implementation Plan

**Goal:** ship Know Your Code as a credible **open-source** codebase-intelligence tool.
No commercialization, no pivot — the current feature set stays. This plan takes the
technical half of the August 2026 audit (Part I + Appendix D) and sequences it into
phases. The business half of the audit (Part III: wedges, market, the "agent gate"
pivot) is **out of scope** by decision.

Every item cites its audit finding number so the source is traceable.

---

## Guiding principles

1. **Correct beats broad.** An analyser that reports 51% false positives loses a user's
   trust faster than a missing feature. Fix what's wrong before adding what's new.
2. **Untrusted input.** A repo URL and a repo's file contents are attacker-controlled.
   The security items exist because of that, even for a local single-user tool.
3. **Test as we go.** Each fix ships with a regression test; that is how an OSS project
   stays fixed.
4. **Don't break working features.** Timeline, Ask, Overview, etc. work today — keep them.

---

## Phase 0 — Safe & publishable
*The minimum to put this on GitHub without embarrassment or hazard.*

### Security (untrusted-repo hardening)
- [ ] **P0-1 · Path traversal (CRITICAL #3).** `engine/knowit/ingest.py` — `name_from_url`
  passes `..` / `\` straight into `os.path.join`, so a crafted URL makes `_dest_for`
  resolve outside the cache and `_rm()` delete arbitrary folders. **Fix:** derive the
  clone folder from `sha1(canonical_url)`; keep the pretty name in metadata only; assert
  `os.path.commonpath` containment before any `_rm` or clone; add the same assertion
  inside `_rm()`.
- [ ] **P0-2 · Kill DNS-rebinding (CRITICAL #4, cheap half).** `app/backend/main.py` /
  `app.py` — add `TrustedHostMiddleware` allowing only `127.0.0.1:8100` / `localhost:8100`.
  One line, closes the drive-by class. (A full startup auth token is optional for a
  local tool; TrustedHost is the high-value part.)
- [ ] **P0-3 · Symlink escape (#4 fix-first, #52).** `list_files` — skip any path whose
  `os.path.realpath` escapes the repo root, so a malicious symlink can't read host files.
- [ ] **P0-4 · Codemap HTML escaping (#53).** `diagrams/codemap/` — escape repo-derived
  strings (docstrings, dir names) before they enter the generated HTML (stored XSS).
- [ ] **P0-5 · Regression tests for the clone hardening (CRITICAL #2).**
  `engine/tests/test_ingest_security.py` — assert `validate_git_url` rejects `ext::`,
  `file://`, leading-dash, and the traversal inputs from P0-1; assert `--` separator and
  `GIT_ALLOW_PROTOCOL`. Pure-function tests, no network.

### Open-source hygiene
- [ ] **P0-6 · Add a `LICENSE`** (audit: none exists; MIT is the conventional default).
- [ ] **P0-7 · Delete the dead code (#27).** Remove `engine/know-your-code/` (41 files,
  a Django/Celery/Qdrant fork that can't import) and `engine/knowit/portfolio.py` (#5,
  fabricates claims). Decide on `engine/app.py` (Streamlit) — keep only if maintained.
- [ ] **P0-8 · Fix broken references (#31, #32).** Either commit `knowyourcode-frontend/`
  and `docs/how-it-works.html`, or remove the `README.md` / `run.ps1 -Website` references
  to them.
- [ ] **P0-9 · De-brand from Orchestraty.** Replace `orchestraty-icon.svg`,
  `orc-spinner.ts`, and stray "orchestrat" strings with Know Your Code's own assets — this
  is an independent project now.
- [ ] **P0-10 · CI (#33, part of #1).** GitHub Actions running the existing 196 engine
  tests plus the new P0-5 security tests on every push.
- [ ] **P0-11 · Correct the README claims (#30).** Drop "any repository" and Express route
  detection where the code doesn't deliver; state Python-first honestly.

**Done when:** the repo is safe against a hostile repo URL, has a license, no dead trees,
green CI, and a README that doesn't overclaim.

---

## Phase 1 — Honest analysers
*Make the numbers the tool reports actually true (Python first).*

- [ ] **P1-1 · Dead-code framework entry points (#6, #7).** `techdebt.py` — 51% false
  positives because decorator-registered handlers, `__all__` exports, and test-discovered
  symbols look "uncalled." Teach the graph about real entry points; replace the
  `"__main__"` substring match with real detection.
- [ ] **P1-2 · Finish scoped call resolution (#12).** `graph.py` — the current
  "unambiguous repo-wide-unique" rule still manufactures an edge for `x.save()` when one
  unrelated `save` exists. Require a real binding (import, same-file, or `self`/class
  scope) instead of a bare-name repo-wide match; leave truly ambiguous calls unresolved.
- [ ] **P1-3 · Import graph correctness (#10, #18).** Handle `from . import x` and
  `from pkg import module` (currently produce no edges) and stop inventing edges from
  stdlib/third-party name collisions.
- [ ] **P1-4 · Chunk module-level code (#17).** Settings, route tables, constants and
  `__main__` blocks live outside any symbol and are never chunked — so Ask can't see them.
  Emit a module-body chunk.
- [ ] **P1-5 · `.cache` in `SKIP_DIRS` (#8).** The default data dir isn't skipped, so
  previously-cloned repos get re-indexed into the target.
- [ ] **P1-6 · Surface the 8,000-file truncation (#26, #7 fix-first).** Return the real
  count and show a banner instead of silently capping — otherwise every downstream number
  is confidently wrong.
- [ ] **P1-7 · api_map / db_map accuracy (#11).** Fix the route/model detection for the
  frameworks actually claimed.

**Done when:** on this repo's own backend, dead-code FP is near-zero and the graph edges
survive spot-checking.

---

## Phase 2 — Language coverage (tree-sitter)
*The single biggest quality lever for a multi-language OSS tool (#5 fix-first, P-1).*

- [ ] **P2-1 · Replace the regex JS/TS parser with tree-sitter** (#9, #15, #16). The regex
  misses `export const App: React.FC<Props> = () => {}`, generic functions, and all class
  methods, and invents symbols from comments. Everything downstream (graph, dead code,
  complexity, chunks, RAG) is wrong for JS/TS until this lands.
- [ ] **P2-2 · Real bodies & complexity for JS/TS** — remove the fixed 12-line stub; compute
  line ranges and complexity from the parse tree.
- [ ] **P2-3 · Add Go, Java, Rust, C#** via tree-sitter grammars for parity with peers.
  Make the parser dispatch pluggable so new languages are additive.
- [ ] **P2-4 · Guard minified/huge files (#13, #25).** Per-file size cap and a
  line-length guard so a single-line bundle can't cause quadratic blowup or `MemoryError`.

**Done when:** a real TypeScript repo produces correct symbols, call edges, and complexity.

---

## Phase 3 — Robustness, RAG quality, frontend
*Make it hold up under real use.*

- [ ] **P3-1 · Token-aware context budget (#44, #8 fix-first).** `retrieval.py` — replace
  the hardcoded 6,000-char cap with real token counting against the configured model's
  window.
- [ ] **P3-2 · BM25 inverted index (perf).** Stop re-`Counter`-ing the whole corpus per
  query; build per-doc term frequencies at index time.
- [ ] **P3-3 · Bound / memoise `duplicate_pairs` (#22, #9 fix-first).** O(n²), uncached, on
  a threadpool thread, on every Intel load and report export.
- [ ] **P3-4 · Stop mutating shared `idx.config` per request (#49).** Snapshot or thread
  the model override through instead of writing to the shared index.
- [ ] **P3-5 · Chroma collection churn (#48).** Reuse/evict collections instead of
  re-embedding the whole repo and orphaning the old collection on each edit.
- [ ] **P3-6 · Frontend resilience (#19, #34, #35, #36, #39).** Add an `ErrorBoundary`;
  reset selection and cancel in-flight requests on repo switch; abort the Ask SSE stream on
  navigation; surface backend-down instead of showing a fake empty state.
- [ ] **P3-7 · Accessibility (#40, #41, #42).** `:focus-visible` styles, dialog semantics +
  focus trap on modals, keyboard-navigable Insight Graph.

**Done when:** rapid repo-switching, a downed backend, and a mid-answer navigation all
behave; concurrent asks don't cross model config.

---

## Phase 4 — Test depth, packaging, contributor docs
*What makes it a project other people can run and contribute to.*

- [ ] **P4-1 · Backend test suite (CRITICAL #1).** `app/backend/tests/` with an
  httpx/TestClient suite: the `_require_idx` state machine (connect → indexing → ready →
  restart → rehydrate), 404/409 paths, one contract test per route, SSE, report export.
  Point pytest at both roots.
- [ ] **P4-2 · Packaging (#30).** Make `knowit` pip-installable (or remove the
  `pip install knowit` claim from the marketing copy).
- [ ] **P4-3 · Cross-platform launcher (#33).** A `run.sh` and a `Dockerfile` so the
  documented non-Windows path actually works.
- [ ] **P4-4 · Logging (#29).** Structured backend logging (currently 2 `print`s in
  1,777 LOC).
- [ ] **P4-5 · Move unused engine imports behind an optional path (#28).** A missing
  `python-pptx` shouldn't be able to affect startup.
- [ ] **P4-6 · Contributor docs.** `CONTRIBUTING.md`, architecture doc
  (`docs/how-it-works.html` already written), and issue/PR templates.

**Done when:** a stranger can clone, run on macOS/Linux, run the tests, and open a PR.

---

## Explicitly out of scope (by decision)

The audit's Part III strategy — the "agent merge gate," cross-agent conflict detection,
code-scoped permissions, entropy telemetry as a product, local-first-vs-fleet, and all
monetization — is **not** part of this plan. Know Your Code stays an open-source
codebase-understanding tool. Those directions remain available in the audit if that ever
changes.
