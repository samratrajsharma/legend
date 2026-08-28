"""Legend MCP server — deterministic code-graph intelligence for coding agents.

Exposes the graph operations an agent *cannot* cheaply derive by grepping: reachability
(blast radius), resolved callers/callees, change impact, structural diffs between refs,
routes/models touched by a change, import cycles, the architecture map, and the public
surface. Every answer is one deterministic call instead of a dozen speculative searches.

Design notes:
* The tool *functions* are plain module-level callables with type hints + docstrings, so
  this module imports (and is testable) even when the optional ``mcp`` package is absent.
  Only ``build_server()`` / ``run()`` import ``mcp`` and wire the functions as MCP tools.
* All tools are READ-ONLY. Graph analysis needs only parse + graph (pure stdlib), so the
  index is built with the BM25 backend and no LLM — the server needs no chromadb/litellm.
* Never write to stdout: MCP stdio uses stdout for the JSON-RPC channel. Index-build
  progress is routed to stderr.
"""
from __future__ import annotations

import os
import sys
from collections import defaultdict
from pathlib import Path

from .config import Config
from .pipeline import build_index
from . import impact, insights, techdebt, track

# ── index lifecycle ────────────────────────────────────────────────────────────
_IDX = None
_IDX_REPO = None


def _repo_path() -> str:
    return os.environ.get("LEGEND_MCP_REPO") or os.getcwd()


def _log(msg: str) -> None:
    print(f"[legend-mcp] {msg}", file=sys.stderr, flush=True)


def _get_index():
    """Build (or reuse) the index for the target repo. BM25 backend, no LLM."""
    global _IDX, _IDX_REPO
    repo = _repo_path()
    if _IDX is None or _IDX_REPO != repo:
        cfg = Config(
            embed_backend="bm25",           # graph tools need no embeddings
            llm_provider="", llm_model="",   # ...and no model
            data_dir=os.environ.get("LEGEND_DATA_DIR") or str(Path.home() / ".legend" / "cache"),
        )
        _log(f"indexing {repo} …")
        _IDX = build_index(repo, cfg, progress=_log, register=False)
        _IDX_REPO = repo
        s = _IDX.stats()
        _log(f"ready: {s['files_parsed']} files, {s['symbols']} symbols, {s['graph_edges']} edges")
    return _IDX


# ── graph helpers ──────────────────────────────────────────────────────────────
def _short(idx, nid: str) -> dict:
    n = idx.graph.get(nid)
    if not n:
        return {"id": nid}
    if n["type"] == "symbol":
        d = n["data"]
        return {"id": nid, "name": d.get("name"), "qualname": d.get("qualname"),
                "file": d.get("file"), "kind": d.get("kind")}
    return {"id": nid, "type": "file", "file": nid}


def _resolve(idx, symbol: str) -> list[str]:
    """Resolve a bare name ('predict'), qualname ('Detector.predict'), or full id to node id(s)."""
    g = idx.graph
    n = g.get(symbol)
    if n and n["type"] == "symbol":
        return [symbol]
    hits = []
    for nid, node in g.nodes.items():
        if node["type"] != "symbol":
            continue
        d = node["data"]
        if d.get("qualname") == symbol or d.get("name") == symbol or nid.endswith("::" + symbol):
            hits.append(nid)
    return hits


def _bfs(step, root: str, max_depth: int) -> list[str]:
    seen, frontier, out = set(), [root], []
    for _ in range(max(1, max_depth)):
        nxt = []
        for nid in frontier:
            for m in step(nid):
                if m != root and m not in seen:
                    seen.add(m)
                    out.append(m)
                    nxt.append(m)
        if not nxt:
            break
        frontier = nxt
    return out


def _cycles_from_edges(edges) -> list[list[str]]:
    """Directed cycles over (src,dst) file-import pairs (used for base-ref fingerprints)."""
    adj = defaultdict(list)
    for pair in edges:
        adj[pair[0]].append(pair[1])
    WHITE, GRAY, BLACK = 0, 1, 2
    color = defaultdict(int)
    seen, cycles = set(), []

    def dfs(start):
        stack = [(start, iter(adj.get(start, [])))]
        path = [start]
        color[start] = GRAY
        while stack:
            node, it = stack[-1]
            advanced = False
            for v in it:
                if color[v] == GRAY:
                    i = path.index(v)
                    cyc = path[i:]
                    if len(cyc) > 1:
                        fs = frozenset(cyc)
                        if fs not in seen:
                            seen.add(fs)
                            cycles.append(list(cyc))
                elif color[v] == WHITE:
                    color[v] = GRAY
                    path.append(v)
                    stack.append((v, iter(adj.get(v, []))))
                    advanced = True
                    break
            if not advanced:
                color[node] = BLACK
                stack.pop()
                path.pop()

    for n in list(adj.keys()):
        if color[n] == WHITE:
            dfs(n)
    return cycles


def _area(fid: str) -> str:
    p = fid.replace("\\", "/")
    return p.split("/")[0] if "/" in p else "(root)"


def _changed_files(idx, files, base) -> set[str]:
    if files:
        return set(files)
    if base:
        b = track.snapshot(idx.meta.path, base, idx.config)
        h = track.fingerprint(idx, idx.meta.commit)
        d = track.diff(b, h)
        cf = set(d.get("files_added", [])) | set(d.get("files_removed", []))
        for key in d.get("symbols_added", []) + d.get("symbols_removed", []) + d.get("symbols_modified", []):
            cf.add(key.split("::")[0])
        return cf
    return set()


# ── tools ───────────────────────────────────────────────────────────────────────
def overview() -> dict:
    """Orient in an unfamiliar repo: size, entry points, hub files, and the most complex
    symbols. Call this first — it's the cheap map before you dive in."""
    idx = _get_index()
    s = idx.stats()
    ins = insights.repo_insights(idx)
    return {
        "repo": s["repo"], "commit": s["commit"],
        "files": s["files_parsed"], "symbols": s["symbols"],
        "graph_nodes": s["graph_nodes"], "graph_edges": s["graph_edges"], "edge_types": s["edge_types"],
        "loc_total": ins["loc_total"], "avg_complexity": ins["avg_complexity"],
        "entry_points": ins["entry_files"],
        "hub_files": ins["hub_files"][:10],
        "most_complex": ins["complex_symbols"][:10],
    }


def find_symbol(name: str) -> dict:
    """Resolve a symbol name to its graph node(s). Accepts a bare name ('refund'), a
    qualified name ('RefundService.refund'), or a full id ('api/refunds.py::RefundService.refund')."""
    idx = _get_index()
    hits = _resolve(idx, name)
    if not hits:
        return {"query": name, "matches": [], "hint": "no match — check spelling or call overview()"}
    return {"query": name, "matches": [_short(idx, h) for h in hits]}


def callers_of(symbol: str, transitive: bool = False, max_depth: int = 6) -> dict:
    """Who calls this symbol, from resolved call edges (not text matches). transitive=True
    walks callers-of-callers up to max_depth."""
    idx = _get_index()
    hits = _resolve(idx, symbol)
    if not hits:
        return {"error": f"symbol not found: {symbol!r}", "hint": "call find_symbol(name) to see options"}
    if len(hits) > 1:
        return {"ambiguous": [_short(idx, h) for h in hits], "hint": "pass a qualified name or full id"}
    root = hits[0]
    ids = _bfs(idx.graph.callers, root, max_depth) if transitive else idx.graph.callers(root)
    return {"symbol": _short(idx, root), "transitive": transitive,
            "count": len(ids), "callers": [_short(idx, c) for c in ids]}


def callees_of(symbol: str, transitive: bool = False, max_depth: int = 6) -> dict:
    """What this symbol calls, from resolved call edges. transitive=True walks callees-of-callees."""
    idx = _get_index()
    hits = _resolve(idx, symbol)
    if not hits:
        return {"error": f"symbol not found: {symbol!r}", "hint": "call find_symbol(name) to see options"}
    if len(hits) > 1:
        return {"ambiguous": [_short(idx, h) for h in hits], "hint": "pass a qualified name or full id"}
    root = hits[0]
    ids = _bfs(idx.graph.callees, root, max_depth) if transitive else idx.graph.callees(root)
    return {"symbol": _short(idx, root), "transitive": transitive,
            "count": len(ids), "callees": [_short(idx, c) for c in ids]}


def blast_radius(symbol: str) -> dict:
    """Everything transitively affected if this symbol changes: all upstream callers
    (recursively) plus files that import its home file. One deterministic call instead of
    ~15 greps. Call this BEFORE editing any function."""
    idx = _get_index()
    hits = _resolve(idx, symbol)
    if not hits:
        return {"error": f"symbol not found: {symbol!r}", "hint": "call find_symbol(name) to see options"}
    if len(hits) > 1:
        return {"ambiguous": [_short(idx, h) for h in hits], "hint": "pass a qualified name or full id"}
    res = impact.impact_of(idx, hits[0])
    return {"symbol": _short(idx, hits[0]),
            "affected_symbols": res["symbols"], "affected_files": res["files"],
            "counts": {"symbols": len(res["symbols"]), "files": len(res["files"])}}


def impact_of_change(file: str) -> dict:
    """Blast radius of editing a whole file: the union of the impact of every symbol it
    defines, plus the files that depend on it. Use a repo-relative path (see overview)."""
    idx = _get_index()
    syms = [nid for nid, n in idx.graph.nodes.items()
            if n["type"] == "symbol" and n["data"].get("file") == file]
    if not syms:
        return {"error": f"no symbols found for file: {file!r}",
                "hint": "use a repo-relative path exactly as returned by find_symbol/overview"}
    aff_syms, aff_files = set(), set()
    for s in syms:
        r = impact.impact_of(idx, s)
        aff_syms.update(r["symbols"])
        aff_files.update(r["files"])
    fs = insights.file_summary(idx, file) or {}
    return {"file": file, "defines": len(syms),
            "affected_symbols": sorted(aff_syms), "affected_files": sorted(aff_files),
            "dependents": fs.get("dependents", []), "fan_in": fs.get("fan_in")}


def structural_diff(base: str, head: str = "HEAD") -> dict:
    """What changed STRUCTURALLY between two git refs — symbols/imports added, removed, or
    modified, plus complexity deltas — not a line diff. Refs are anything git accepts
    (SHA, branch, tag, HEAD~5). Legend indexes history; most tools only see HEAD."""
    idx = _get_index()
    try:
        b = track.snapshot(idx.meta.path, base, idx.config)
        h = track.fingerprint(idx, idx.meta.commit) if head == "HEAD" else track.snapshot(idx.meta.path, head, idx.config)
    except Exception as e:  # noqa: BLE001 — surface git/worktree failures to the agent
        return {"error": f"could not snapshot refs ({base}..{head}): {e}"}
    d = track.diff(b, h)
    return {"base": base, "head": head, "delta": d, "changelog": track.changelog_text(d)}


def routes_touched(files: list[str] | None = None, base: str | None = None) -> dict:
    """HTTP routes whose defining file is in the change set. Pass files=[...] you're about to
    edit, or base=<ref> to derive the change set from a structural diff against HEAD."""
    idx = _get_index()
    changed = _changed_files(idx, files, base)
    if not changed:
        return {"error": "provide files=[...] or base=<ref>"}
    routes = [r for r in insights.api_map(idx) if r["file"] in changed]
    return {"changed_files": sorted(changed), "routes": routes, "count": len(routes)}


def models_touched(files: list[str] | None = None, base: str | None = None) -> dict:
    """Data models / ORM tables whose defining file is in the change set. Pass files=[...] or
    base=<ref> (structural diff against HEAD)."""
    idx = _get_index()
    changed = _changed_files(idx, files, base)
    if not changed:
        return {"error": "provide files=[...] or base=<ref>"}
    models = [m for m in insights.db_map(idx) if m["file"] in changed]
    return {"changed_files": sorted(changed), "models": models, "count": len(models)}


def cycles(base: str | None = None) -> dict:
    """Import cycles in the repo (deterministic graph cycle detection). With base=<ref>,
    returns only the cycles INTRODUCED since that ref — call before merging."""
    idx = _get_index()
    current = techdebt.import_cycles(idx)
    if not base:
        return {"cycles": current, "count": len(current)}
    try:
        b = track.snapshot(idx.meta.path, base, idx.config)
    except Exception as e:  # noqa: BLE001
        return {"error": f"could not snapshot base ref {base!r}: {e}", "current_cycles": current}
    base_cycles = _cycles_from_edges(b.get("imports", []))
    cur_norm = {frozenset(c) for c in current}
    base_norm = {frozenset(c) for c in base_cycles}
    introduced = [sorted(c) for c in (cur_norm - base_norm)]
    return {"introduced": introduced, "count": len(introduced),
            "current": current, "in_base": [sorted(c) for c in base_norm]}


def architecture_map() -> dict:
    """Modules grouped into areas (by top-level directory) with area→area import
    dependencies — the onboarding view. Derived from resolved import edges."""
    idx = _get_index()
    areas = defaultdict(list)
    edges = set()
    for nid, n in idx.graph.nodes.items():
        if n["type"] == "file":
            areas[_area(nid)].append(nid)
    for src, dst, _et in idx.graph.all_edges("imports"):
        a1, a2 = _area(src), _area(dst)
        if a1 != a2:
            edges.add((a1, a2))
    return {
        "area_count": len(areas),
        "areas": [{"area": a, "files": sorted(fs), "count": len(fs)} for a, fs in sorted(areas.items())],
        "dependencies": [{"from": a, "to": b} for a, b in sorted(edges)],
    }


def public_surface(file: str | None = None) -> dict:
    """The repo's public/reachable surface: entry points, __all__ exports, and symbols
    called from OTHER files. Pass file=<rel path> for just that file's cross-file API."""
    idx = _get_index()
    if file:
        fs = insights.file_summary(idx, file)
        if not fs:
            return {"error": f"file not found: {file!r}"}
        exports = next((list(p.exports) for p in idx.parsed_files if p.file == file and getattr(p, "exports", None)), [])
        return {"file": file, "public_api": fs.get("public_api", []), "exports": exports}
    ins = insights.repo_insights(idx)
    cross = []
    for nid, n in idx.graph.nodes.items():
        if n["type"] != "symbol":
            continue
        home = n["data"].get("file")
        ext = sorted({
            idx.graph.get(c)["data"].get("file")
            for c in idx.graph.callers(nid)
            if idx.graph.get(c) and idx.graph.get(c)["type"] == "symbol"
            and idx.graph.get(c)["data"].get("file") != home
        })
        if ext:
            cross.append({"symbol": n["data"].get("qualname"), "file": home, "used_by": ext})
    exports = [{"file": p.file, "exports": list(p.exports)} for p in idx.parsed_files if getattr(p, "exports", None)]
    return {
        "entry_points": ins["entry_files"],
        "exports": exports,
        "cross_file_symbols": sorted(cross, key=lambda r: -len(r["used_by"]))[:100],
    }


def reindex() -> dict:
    """Rebuild the index from disk after code changes, so subsequent tool calls are current."""
    global _IDX
    _IDX = None
    idx = _get_index()
    s = idx.stats()
    return {"reindexed": True, "repo": s["repo"], "files": s["files_parsed"], "symbols": s["symbols"]}


# All tools, in registration order. Every one is read-only.
TOOLS = [
    overview, find_symbol, callers_of, callees_of, blast_radius, impact_of_change,
    structural_diff, routes_touched, models_touched, cycles, architecture_map,
    public_surface, reindex,
]


# ── MCP wiring (imports `mcp` only here) ─────────────────────────────────────────
def build_server():
    """Construct the FastMCP server with all tools registered. Requires the ``mcp`` package."""
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as e:
        raise SystemExit(
            "Legend's MCP server needs the 'mcp' package, which isn't installed.\n"
            "Install it with:  pip install \"legend-lens[mcp]\"\n"
            "or run directly:  uvx --with \"legend-lens[mcp]\" legend mcp"
        ) from e

    server = FastMCP("legend")
    for fn in TOOLS:
        server.tool()(fn)
    return server


def run() -> None:
    """Serve MCP over stdio. The index builds lazily on the first tool call — tool listing
    needs no index — so the client connects instantly even on a large repo."""
    _log(f"legend MCP server ready; will index {_repo_path()} on first tool call")
    build_server().run()


def main(argv=None) -> int:
    import argparse
    p = argparse.ArgumentParser(
        prog="legend mcp",
        description="Legend MCP server — deterministic code-graph tools for agents, over stdio.",
    )
    p.add_argument("--repo", default=None, help="repo (or git URL) to index (default: current folder)")
    p.add_argument("--data-dir", default=None, help="index cache dir (default: ~/.legend/cache)")
    args = p.parse_args(argv)
    if args.repo:
        src = args.repo
        os.environ["LEGEND_MCP_REPO"] = src if "://" in src else str(Path(src).resolve())
    if args.data_dir:
        os.environ["LEGEND_DATA_DIR"] = args.data_dir
    run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
