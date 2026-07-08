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
