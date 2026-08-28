"""Impact analysis: what is affected by changing a symbol — transitive reverse-reachability
over `calls` (who calls it, who calls them, …) plus files that import its file. Pairs with
change-tracking for a 'what does this PR affect?' view."""
from __future__ import annotations


def impact_of(idx, node_id, max_depth=6):
    g = idx.graph
    if node_id not in g.nodes or g.get(node_id)["type"] != "symbol":
        return {"symbols": [], "files": []}
    # transitive callers
    affected, frontier = {node_id}, {node_id}
    for _ in range(max_depth):
        nxt = set()
        for n in frontier:
            for c in g.callers(n):
                if c not in affected:
                    affected.add(c)
                    nxt.add(c)
        if not nxt:
            break
        frontier = nxt
    affected.discard(node_id)
    sym_files = {g.get(s)["data"]["file"] for s in affected}
    # files importing this symbol's file
    home = g.get(node_id)["data"]["file"]
    importers = set(g.predecessors(home, "imports"))
    return {
        "symbols": sorted(g.get(s)["data"]["qualname"] for s in affected),
        "files": sorted(sym_files | importers),
    }


def diff_impact(idx, changed_symbol_ids):
    """Given changed symbol ids (e.g. from a track diff), summarise blast radius."""
    out = []
    for sid in changed_symbol_ids:
        imp = impact_of(idx, sid)
        out.append({"changed": idx.graph.get(sid)["data"]["qualname"] if sid in idx.graph.nodes else sid,
                    "affects_symbols": len(imp["symbols"]),
                    "affects_files": ", ".join(imp["files"]) or "—"})
    return sorted(out, key=lambda x: -x["affects_symbols"])
