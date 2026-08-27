"""Phase 5 — technical-debt analysis. Pure structural functions over a RepoIndex:
dead code, near-duplicates (normalized structural shingles), import cycles, complexity
hotspots, god-files, and undocumented symbols. No external dependencies; fully offline."""
from __future__ import annotations
import io
import keyword
import re
import textwrap
import tokenize as pytok

from .index import tokenize
from .insights import repo_insights, _reachable_symbols

_IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def _symbols(idx):
    return [(nid, n["data"]) for nid, n in idx.graph.nodes.items() if n["type"] == "symbol"]


def _code_by_id(idx):
    out = {}
    for p in idx.parsed_files:
        for s in p.symbols:
            out[s.id] = s.code
    return out


def _entry_code_names(idx, entry_files):
    """Identifiers used in CODE (not strings/comments) of the entry files — so a symbol
    invoked from a __main__ block or re-exported is not mistaken for dead code, while a
    word that only appears in a docstring does not suppress a real flag."""
    names = set()
    for p in idx.parsed_files:
        if p.file not in entry_files:
            continue
        if p.language == "python":
            try:
                for t in pytok.generate_tokens(io.StringIO(p.text).readline):
                    if t.type == pytok.NAME:
                        names.add(t.string.lower())
                continue
            except Exception:
                pass
        names |= {m.lower() for m in _IDENT.findall(p.text or "")}
    return names


# ---------------- dead code (conservative, name-aware) ----------------
def dead_code(idx):
    """A Python function/method with no in-repo caller that is also not framework-reachable
    (decorated, exported via __all__, a test/fixture) and not defined in an entry file, and
    whose name is not invoked from an entry file's code. Static call graph only: dynamic
    dispatch (getattr/importlib/registries beyond decorators) is not modelled - so treat the
    result as 'likely unused, verify before deleting', not a proof."""
    g = idx.graph
    entry = set(repo_insights(idx)["entry_files"])
    entry_names = _entry_code_names(idx, entry)
    reach = _reachable_symbols(idx)
    py_files = {p.file for p in idx.parsed_files if p.language == "python"}
    out = []
    for nid, n in g.nodes.items():
        if n["type"] != "symbol":
            continue
        d = n["data"]
        if d["file"] not in py_files:          # only judge Python (JS/TS not call-resolved)
            continue
        if d["kind"] == "class" or d["file"] in entry:
            continue
        nm = d["name"]
        if nm.startswith("__") and nm.endswith("__"):
            continue
        if nid in reach or g.callers(nid) or nm.lower() in entry_names:
            continue
        out.append({"symbol": d["qualname"], "file": d["file"]})
    return sorted(out, key=lambda x: x["file"])


def undocumented(idx):
    out = [{"symbol": d["qualname"], "file": d["file"], "kind": d["kind"]}
           for _, d in _symbols(idx) if not d.get("doc")]
    return sorted(out, key=lambda x: x["file"])


def complexity_hotspots(idx, threshold=10):
    out = [{"symbol": d["qualname"], "file": d["file"], "complexity": d.get("complexity", 0)}
           for _, d in _symbols(idx)
           if d["kind"] != "class" and d.get("complexity", 0) >= threshold]
    return sorted(out, key=lambda x: -x["complexity"])


def god_files(idx, sym_threshold=12, cx_threshold=40):
    by_file = {}
    for _, d in _symbols(idx):
        f = by_file.setdefault(d["file"], {"symbols": 0, "complexity": 0})
        f["symbols"] += 1
        f["complexity"] += d.get("complexity", 0)
    out = [{"file": f, **v} for f, v in by_file.items()
           if v["symbols"] >= sym_threshold or v["complexity"] >= cx_threshold]
    return sorted(out, key=lambda x: -x["complexity"])


# ---------------- near-duplicate detection ----------------
def _normalize_py(code):
    """Tokenise Python source into a structural sequence: identifiers -> ID, literals ->
    LIT, keywords/operators kept. Identifier renaming and docstrings no longer matter."""
    try:
        src = textwrap.dedent(code)
        out = []
        for t in pytok.generate_tokens(io.StringIO(src).readline):
            if t.type == pytok.NAME:
                out.append(t.string if keyword.iskeyword(t.string) else "ID")
            elif t.type == pytok.NUMBER:
                out.append("LIT")
            # STRING tokens (including docstrings) are dropped, so clones that differ
            # only in their strings/docstrings still match
            elif t.type == pytok.OP:
                out.append(t.string)
        return out
    except Exception:
        return None


def _shingles(tokens, k=4):
    if len(tokens) < k:
        return {tuple(tokens)} if tokens else set()
    return {tuple(tokens[i:i + k]) for i in range(len(tokens) - k + 1)}


def duplicate_pairs(idx, min_tokens=15, threshold=0.75, max_pairs=50):
    code = _code_by_id(idx)
    lang = {p.file: p.language for p in idx.parsed_files}
    sh = {}
    for nid, d in _symbols(idx):
        if d["kind"] == "class":
            continue
        c = code.get(nid, "")
        toks = _normalize_py(c) if lang.get(d["file"]) == "python" else tokenize(c)
        if not toks or len(toks) < min_tokens:
            continue
        sh[nid] = (d, _shingles(toks, 4))
    ids = list(sh)
    out = []
    for i in range(len(ids)):
        da, sa = sh[ids[i]]
        for j in range(i + 1, len(ids)):
            db, sb = sh[ids[j]]
            uni = len(sa | sb)
            jac = len(sa & sb) / uni if uni else 0.0
            if jac >= threshold:
                out.append({"a": f"{da['qualname']} ({da['file']})",
                            "b": f"{db['qualname']} ({db['file']})",
                            "similarity": round(jac, 2)})
    return sorted(out, key=lambda x: -x["similarity"])[:max_pairs]


# ---------------- import cycles ----------------
def import_cycles(idx):
    g = idx.graph
    files = [nid for nid, n in g.nodes.items() if n["type"] == "file"]
    adj = {f: list(g.successors(f, "imports")) for f in files}
    color = {f: 0 for f in files}
    cycles, seen = [], set()

    # Iterative three-colour DFS. The recursive version blew Python's stack on a deep
    # import chain (~1000+), raising RecursionError -> 500 on /intel/techdebt -> the
    # Tech-debt tab hung forever (QA finding G-06). Same semantics, explicit stack.
    for root in files:
        if color[root] != 0:
            continue
        path = [root]
        pos = {root: 0}                       # node -> index in path, O(1) vs path.index
        frames = [(root, iter(adj.get(root, ())))]
        color[root] = 1
        while frames:
            u, it = frames[-1]
            advanced = False
            for v in it:
                cv = color.get(v, 0)
                if cv == 1:
                    if v in pos:
                        cyc = path[pos[v]:]
                        key = frozenset(cyc)
                        if len(cyc) > 1 and key not in seen:
                            seen.add(key)
                            cycles.append(list(cyc))
                elif cv == 0:
                    color[v] = 1
                    pos[v] = len(path)
                    path.append(v)
                    frames.append((v, iter(adj.get(v, ()))))
                    advanced = True
                    break
            if not advanced:
                color[u] = 2
                frames.pop()
                if path and path[-1] == u:
                    pos.pop(path.pop(), None)
    return cycles


def debt_summary(idx):
    return {"dead_code": dead_code(idx), "duplicates": duplicate_pairs(idx),
            "import_cycles": import_cycles(idx), "complexity_hotspots": complexity_hotspots(idx),
            "god_files": god_files(idx), "undocumented": undocumented(idx)}


# ---------------- secret scanning ----------------
_SECRET_PATTERNS = [
    ("AWS access key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("Private key block", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("Slack token", re.compile(r"xox[baprs]-[0-9A-Za-z-]{10,}")),
    ("Hardcoded secret", re.compile(r"(?i)(api[_-]?key|secret|token|password|passwd)\s*[=:]\s*[\"\'][^\"\']{8,}[\"\']")),
]


def secret_scan(idx):
    out = []
    for p in idx.parsed_files:
        for i, line in enumerate((p.text or "").splitlines(), 1):
            for name, pat in _SECRET_PATTERNS:
                if pat.search(line):
                    out.append({"file": p.file, "line": i, "kind": name,
                                "snippet": line.strip()[:80]})
                    break
    return out[:50]
