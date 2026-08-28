"""Repo-level insights and per-file structural explanations (stdlib only)."""
from __future__ import annotations
import ast


_ENTRY_NAMES = {"main.py", "manage.py", "wsgi.py", "asgi.py"}
# decorators that do NOT imply external invocation - everything else (route decorators,
# task decorators, fixtures, click commands, ...) marks a symbol as framework-reachable.
_INERT_DECORATORS = {"property", "cached_property", "staticmethod", "classmethod",
                     "abstractmethod", "abstractproperty", "override", "final",
                     "dataclass", "total_ordering", "wraps", "contextmanager"}


def _is_entry(pf):
    """A real entry point: a module with an actual `if __name__ == '__main__':` guard, or a
    conventionally-named launcher. The old test was `"__main__" in pf.text`, which flagged any
    file that merely MENTIONED the token in a comment, docstring or string literal (QA #6)."""
    if getattr(pf, "has_main", False):
        return True
    base = pf.file.replace("\\", "/").rsplit("/", 1)[-1].lower()
    return base in _ENTRY_NAMES


def _reachable_symbols(idx):
    """Symbol ids reachable for reasons the static call graph cannot see: decorated with a
    non-inert decorator (framework registration - @app.get, @task, @fixture, ...), exported
    via __all__, or a pytest test/fixture. Without this, dead-code flags an app's entire
    public surface (QA #7: 79% of a FastAPI backend's symbols reported dead)."""
    reach = set()
    for p in idx.parsed_files:
        exports = set(getattr(p, "exports", []) or [])
        for sym in p.symbols:
            decos = set(getattr(sym, "decorators", []) or [])
            if decos - _INERT_DECORATORS:
                reach.add(sym.id)
            elif sym.name in exports:
                reach.add(sym.id)
            elif sym.name.startswith("test_"):
                reach.add(sym.id)
            elif any("fixture" in d for d in decos):
                reach.add(sym.id)
    return reach


def repo_insights(idx):
    memo = getattr(idx, "memo", None)
    if memo is not None and "repo_insights" in memo:
        return memo["repo_insights"]
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

    reach = _reachable_symbols(idx)
    py_files = {p.file for p in py}
    dead = []
    for nid, n in g.nodes.items():
        if n["type"] != "symbol":
            continue
        d = n["data"]
        # only judge Python: JS/TS bodies aren't call-resolved yet, so every symbol there
        # would look uncalled (QA #7 correction c: 90 of 132 false positives were TypeScript)
        if d["file"] not in py_files:
            continue
        if d["kind"] == "class" or d["file"] in entry_set:
            continue
        nm = d["name"]
        if nm.startswith("__") and nm.endswith("__"):
            continue
        if nid in reach:
            continue
        if not g.callers(nid):
            dead.append({"symbol": d["qualname"], "file": d["file"]})
    dead.sort(key=lambda x: x["file"])

    comps = [d.get("complexity", 0) for d in syms if d.get("kind") != "class"]
    result = {
        "entry_files": sorted(entry_set),
        "hub_files": hubs[:8],
        "complex_symbols": complex_top,
        "likely_unused": dead[:15],
        "loc_total": sum(p.loc for p in py),
        "avg_complexity": round(sum(comps) / len(comps), 2) if comps else 0,
        "n_python": len(py),
        "n_symbols": len(syms),
    }
    if memo is not None:
        memo["repo_insights"] = result
    return result


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

# Python decorators: @app.get("/x") / @router.route("/x", methods=[...])
_PY_ROUTE = _re.compile(r'@(\w+)\.(get|post|put|delete|patch|route)\(\s*["\']([^"\']+)["\']([^)]*)', _re.I)
# JS/TS method calls (Express/Koa/Fastify/Nest): app.get("/x", ...) - no decorator, needs a string path
_JS_ROUTE = _re.compile(r'\b(\w+)\.(get|post|put|delete|patch|all|use)\(\s*["\'`]([^"\'`]+)', _re.I)
_METHODS = _re.compile(r'methods\s*=\s*[\[(]([^\])]*)', _re.I)
_QUOTED_WORD = _re.compile(r'["\']([A-Za-z]+)["\']')
_TABLE = _re.compile(r'__tablename__\s*=\s*["\']([^"\']+)')
_DB_BASES = {"base", "model", "declarativebase", "sqlmodel"}
_ORM_MARKERS = ("import sqlalchemy", "from sqlalchemy", "django.db", "sqlmodel",
                "import peewee", "from peewee", "tortoise")
# Receivers that are HTTP CLIENTS, not servers: `axios.get('/x')` defines no route (QA audit).
_JS_CLIENT_RECV = {"axios", "fetch", "http", "https", "got", "ky", "request", "superagent",
                   "xhr", "instance", "client", "api"}
# Decorator receivers that aren't web routers: `@cache.get("k")` is not a route.
_PY_NON_ROUTE_RECV = {"cache", "lru_cache", "functools", "memoize", "redis"}
_PY_COMMENT = _re.compile(r"#[^\n]*")


def _strip_py_comments(s: str) -> str:
    """Blank out `# ...` line comments (newlines kept, so line numbers are preserved) so ORM
    markers mentioned in a comment don't count as real declarations (QA audit)."""
    return _PY_COMMENT.sub("", s or "")


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
    """HTTP routes for the frameworks we claim to support (QA #11): FastAPI/Flask
    decorators (with Flask methods= parsed) and Express/Koa/Nest method calls."""
    out = []
    for p in idx.parsed_files:
        txt = p.text or ""
        if p.language == "python":
            for m in _PY_ROUTE.finditer(txt):
                if m.group(1).lower() in _PY_NON_ROUTE_RECV:
                    continue                            # @cache.get(...) etc., not a route
                verb, path, rest = m.group(2).lower(), m.group(3), (m.group(4) or "")
                if verb == "route":
                    mm = _METHODS.search(rest)
                    verbs = [v.upper() for v in _QUOTED_WORD.findall(mm.group(1))] if mm else []
                    for v in (verbs or ["GET"]):        # Flask defaults to GET
                        out.append({"method": v, "path": path, "file": p.file})
                else:
                    out.append({"method": verb.upper(), "path": path, "file": p.file})
        elif p.language in ("javascript", "typescript"):
            for m in _JS_ROUTE.finditer(txt):
                if m.group(1).lower() in _JS_CLIENT_RECV:
                    continue                            # axios.get(...) is a client call, not a route
                verb = m.group(2).upper()
                verb = "ANY" if verb in ("USE", "ALL") else verb
                out.append({"method": verb, "path": m.group(3), "file": p.file})
    seen, uniq = set(), []
    for r in out:
        k = (r["method"], r["path"], r["file"])
        if k not in seen:
            seen.add(k); uniq.append(r)
    return uniq


def db_map(idx):
    """ORM models, one row per class with its __tablename__ joined in (QA #11). Tightened
    so `class LlamaModel(Model)` in an ML repo is not reported as a database model: the
    file must look like an ORM file or the class must declare Column/mapped_column/db.*."""
    orm_files = {p.file for p in idx.parsed_files
                 if any(k in (p.text or "").lower() for k in _ORM_MARKERS)}
    tables_by_file = {}
    for p in idx.parsed_files:
        clean = _strip_py_comments(p.text or "")     # a __tablename__ in a comment isn't a table
        occ = []
        for m in _TABLE.finditer(clean):
            occ.append((clean[:m.start()].count("\n") + 1, m.group(1)))
        if occ:
            tables_by_file[p.file] = occ
    out = []
    for p in idx.parsed_files:
        for s2 in p.symbols:
            if s2.kind != "class":
                continue
            bs = [b.split(".")[-1].lower() for b in (s2.bases or [])]
            if not any(b in _DB_BASES for b in bs):
                continue
            body = _strip_py_comments(s2.code or "")   # markers in comments don't count (audit)
            # __tablename__ is an unambiguous ORM declaration on its own - accept regardless
            # of imports. Column/mapped_column/db. are strong too. Only the weak base-name
            # signal (class ...(Model)) needs an ORM-looking file to avoid ML false positives.
            has_table = "__tablename__" in body
            has_cols = ("Column(" in body or "mapped_column(" in body
                        or "models." in body or "= db." in body)
            if p.file not in orm_files and not has_cols and not has_table:
                continue                                 # a plain class named ...Model - skip
            table = ""
            for ln, tv in tables_by_file.get(p.file, []):
                if s2.start_line <= ln <= s2.end_line:
                    table = tv; break
            out.append({"model": s2.qualname, "file": s2.file, "table": table})
    return out
