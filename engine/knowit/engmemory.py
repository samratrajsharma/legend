"""Phase 5 — engineering memory. Per-repo persisted notes: architecture-decision records,
an error knowledge base, and a technical-memory log. Plain JSON under
`data_dir/eng/<repo>/`; optional LLM helpers to draft a decision or diagnose an error."""
from __future__ import annotations
import hashlib
import json
import os
import time

KINDS = ("decisions", "errors", "memory")


def _dir(config, repo_name):
    safe = "".join(c if c.isalnum() else "_" for c in (repo_name or "repo"))[:40] or "repo"
    d = os.path.join(config.data_dir, "eng", safe)
    os.makedirs(d, exist_ok=True)
    return d


def _path(config, repo_name, kind):
    return os.path.join(_dir(config, repo_name), f"{kind}.json")


def load(config, repo_name, kind):
    p = _path(config, repo_name, kind)
    try:
        if not os.path.exists(p):
            return []
        with open(p) as fh:
            return json.load(fh)
    except Exception:
        return []


def _save(config, repo_name, kind, items):
    try:
        with open(_path(config, repo_name, kind), "w") as fh:
            json.dump(items, fh, indent=2)
    except Exception:
        pass


def add(config, repo_name, kind, fields):
    items = load(config, repo_name, kind)
    eid = hashlib.sha1(f"{kind}{time.time()}{json.dumps(fields, sort_keys=True)}"
                       .encode()).hexdigest()[:8]
    entry = {"id": eid, "date": time.strftime("%Y-%m-%d %H:%M"), **fields}
    items.insert(0, entry)
    _save(config, repo_name, kind, items)
    return entry


def delete(config, repo_name, kind, eid):
    items = [e for e in load(config, repo_name, kind) if e.get("id") != eid]
    _save(config, repo_name, kind, items)
    return items


# ---------------- optional LLM helpers ----------------
def draft_decision_llm(title, context, model, extra=None):
    if not model:
        return None
    try:
        from . import llm
        prompt = (f"Draft a concise Architecture Decision Record titled: {title}\n"
                  f"Context / notes: {context}\n\n"
                  "Return four short sections: Decision, Alternatives considered, "
                  "Rationale, Consequences.")
        r = llm._complete(model, [
            {"role": "system", "content": "You write crisp architecture decision records."},
            {"role": "user", "content": prompt}], extra=extra, temperature=0.3, timeout=60)
        return r["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return f"[LLM unavailable: {type(e).__name__}: {e}]"


def diagnose_error_llm(traceback_text, repo_index, model, extra=None):
    if not model:
        return None
    try:
        from . import llm
        from .retrieval import assemble_context
        ctx = assemble_context(repo_index.search(traceback_text[:300])) if repo_index else ""
        prompt = ("Given this error/traceback and the relevant code, state a likely CAUSE "
                  "and a concrete FIX (2–4 sentences each).\n\n"
                  f"Error:\n{traceback_text[:2000]}\n\nCode context:\n{ctx}")
        r = llm._complete(model, [
            {"role": "system", "content": "You debug code precisely and concisely."},
            {"role": "user", "content": prompt}], extra=extra, temperature=0.2, timeout=60)
        return r["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return f"[LLM unavailable: {type(e).__name__}: {e}]"
