"""Phase 8 — portfolio mode. Turn everything KnowIT knows about a repo into shareable
artifacts: a project report, a technical blog post, résumé bullets, a LinkedIn post, and a
research-paper skeleton. Structural drafts work offline; an LLM polishes them when set."""
from __future__ import annotations
import json

from . import teach, techdebt, research
from .insights import repo_insights, language_breakdown, file_summary


def _facts(idx):
    s = idx.stats()
    ins = repo_insights(idx)
    langs = language_breakdown(idx)
    lp = teach.learning_path(idx)
    hubs = [h["file"] for h in ins["hub_files"]][:5]
    key = []
    for f in (ins["entry_files"][:2] + hubs):
        if f in [k["file"] for k in key]:
            continue
        fs = file_summary(idx, f)
        if fs:
            purpose = (fs["purpose"].splitlines()[0] if fs["purpose"]
                       else "defines " + ", ".join(d["symbol"] for d in fs["defines"][:3]))
            key.append({"file": f, "purpose": purpose[:100]})
    return {
        "repo": s["repo"], "commit": s["commit"], "files": s["python_files"],
        "symbols": s["symbols"], "loc": ins["loc_total"],
        "languages": [l["language"] for l in langs],
        "entry_points": ins["entry_files"], "hubs": hubs, "key_files": key,
        "avg_complexity": ins["avg_complexity"],
        "complex_top": [(h["symbol"], h["complexity"])
                        for h in techdebt.complexity_hotspots(idx)[:5]],
        "dead": len(techdebt.dead_code(idx)), "cycles": len(techdebt.import_cycles(idx)),
        "papers": [p["ref"] for p in research.find_papers(idx)],
        "learning_path": [st["file"] for st in lp[:6]],
    }


def _report_md(f):
    langs = ", ".join(f["languages"]) or "code"
    md = [f"# {f['repo']} — Project Report", "", "## Overview", "",
          f"{f['repo']} is a {langs} project of {f['files']} source files, {f['symbols']} "
          f"symbols, and ~{f['loc']} lines of code.", "", "## Architecture", "",
          f"- Entry points: {', '.join(f['entry_points']) or '—'}",
          f"- Most-connected modules: {', '.join(f['hubs']) or '—'}",
          f"- Languages: {langs}", "", "## Key components", ""]
    md += [f"- **{k['file']}** — {k['purpose']}" for k in f["key_files"]] or ["- —"]
    md += ["", "## Technical health", "",
           f"- Average complexity per function: {f['avg_complexity']}",
           "- Complexity hotspots: " + (", ".join(f"{n} ({c})" for n, c in f["complex_top"]) or "none"),
           f"- Likely-unused symbols: {f['dead']}",
           f"- Import cycles: {f['cycles']}", ""]
    if f["papers"]:
        md += ["## Research basis", "", "- Referenced papers: " + ", ".join(f["papers"]), ""]
    md += ["## Getting started", "", "Suggested reading order:"]
    md += [f"{i}. {fp}" for i, fp in enumerate(f["learning_path"], 1)]
    return "\n".join(md)


def _resume_md(f):
    langs = "/".join(f["languages"][:3]) or "Python"
    bul = [
        f"Built **{f['repo']}**, a {langs} codebase-understanding system ({f['files']} files, "
        f"{f['symbols']} symbols) that ingests a repository and auto-generates explanations, "
        "interactive diagrams, quizzes, change tracking, and a tech-debt audit.",
        "Engineered a hybrid retrieval pipeline — BM25 + semantic embeddings fused with "
        "Reciprocal Rank Fusion, plus code-graph expansion — over provenance-tagged artifacts.",
        "Designed a dependency-light architecture with graceful fallbacks across the parsing, "
        "retrieval, LLM, and visualization layers, fully testable offline.",
        "Shipped a single-command Streamlit app spanning understanding, teaching, tracking, "
        "engineering-intelligence, media, and research features.",
    ]
    if f["papers"]:
        bul.append(f"Linked the implementation to {len(f['papers'])} research paper(s) with "
                   "comparison and implementation-planning tooling.")
    return "\n".join("- " + b for b in bul)


def _linkedin_md(f):
    return (f"🚀 I've been building **{f['repo']}** — a tool that takes any codebase and helps "
            f"you *understand, learn, and track* it.\n\nIt parses a repo into a code graph "
            f"({f['symbols']} symbols across {f['files']} files), then generates per-file "
            "explanations, an interactive mind map, flashcards & quizzes, change/learning "
            "deltas across commits, a tech-debt audit, slide decks, and even a two-host audio "
            "overview — all from one app.\n\nBuilt dependency-light, so the core runs fully "
            "offline and upgrades automatically when richer libraries are present.\n\n"
            "#MachineLearning #DeveloperTools #AI #SoftwareEngineering")


def _blog_md(f):
    return "\n".join([
        f"# Teaching a Machine to Teach You a Codebase: Inside {f['repo']}", "",
        "## The problem", "",
        "Reading an unfamiliar codebase is one of the most common — and least supported — "
        "tasks in software. Tools help you *write* or *search* code; few help *you* understand "
        "and retain a system.", "",
        "## What I built", "",
        f"{f['repo']} ingests a repository, builds a code graph ({f['symbols']} symbols across "
        f"{f['files']} files), and layers understanding, teaching, tracking, and research "
        "features on top.", "",
        "## How it works", "",
        "- Parse → code graph → provenance-tagged chunks",
        "- Hybrid retrieval (BM25 + embeddings, fused by RRF) with one-hop graph expansion",
        "- Mind maps, per-file explanations, multi-level quizzes, change/learning deltas, "
        "a tech-debt audit, and auto slide decks", "",
        "## Design philosophy", "",
        "Dependency-light with graceful fallbacks — the whole core runs offline, and heavy "
        "libraries (semantic search, LLMs, interactive canvas) are optional accelerators.", "",
        "## What's next", "",
        "Cross-encoder re-ranking, cross-repository querying, and richer multi-language parsing."])


def _paper_md(f):
    refs = "\n".join(f"- {p}" for p in f["papers"]) or "- (none detected)"
    return "\n".join([
        f"# {f['repo']}: Understanding, Learning, and Tracking Codebases", "",
        "## Abstract", "",
        f"We present {f['repo']}, a system that ingests a software repository and produces an "
        "interactive environment for understanding, learning, and tracking it. The system "
        "builds a code graph, performs hybrid lexical-semantic retrieval with graph expansion, "
        "and generates structural learning and engineering-intelligence artifacts. (Draft.)", "",
        "## 1. Introduction", "Codebase comprehension is common yet underserved by existing "
        "tools, which focus on writing or searching code.", "",
        "## 2. System Overview", "ingest → parse → code graph → chunk → hybrid retrieval → "
        "understanding / teaching / tracking / research features.", "",
        "## 3. Method", "- Code-graph construction (files, symbols, calls, imports, inheritance)",
        "- Hybrid retrieval: BM25 + dense embeddings fused by Reciprocal Rank Fusion",
        "- Graph-augmented context assembly",
        "- Provenance tagging enabling longitudinal change/learning deltas", "",
        "## 4. Implementation", "A dependency-light core with graceful degradation across "
        "parsing, retrieval, LLM, and visualization layers.", "",
        "## 5. Limitations and Future Work", "Name-based call resolution; best-effort "
        "multi-language parsing; cross-encoder re-ranking as future work.", "",
        "## References", "", refs])


_KINDS = {"report": _report_md, "résumé": _resume_md, "resume": _resume_md,
          "linkedin": _linkedin_md, "blog": _blog_md, "paper": _paper_md}


def generate(idx, kind, model="", extra=None):
    f = _facts(idx)
    struct = _KINDS.get(kind, _report_md)(f)
    if not model:
        return struct
    try:
        from . import llm
        user = (f"Using ONLY these facts about a software project, write a polished {kind}. "
                "Do not invent specifics. Refine this structural draft:\n\n" + struct +
                "\n\nFacts JSON: " + json.dumps(f))
        r = llm._complete(model, [
            {"role": "system", "content": "You are a skilled technical writer."},
            {"role": "user", "content": user}], extra=extra, temperature=0.4, timeout=120)
        return r["choices"][0]["message"]["content"].strip()
    except Exception:
        return struct
