"""Repo-level insights and per-file structural explanations (stdlib only)."""
from __future__ import annotations
import ast


def _is_entry(pf):
    return "__main__" in (pf.text or "")


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
