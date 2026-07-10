"""Dependency-graph builder over parsed files. Pure-Python directed graph (no networkx).
Produces the architecture JSON (file nodes coloured by language + import edges)."""
from __future__ import annotations
import os


def build_graph(parsed_files):
    files = {pf["path"]: pf for pf in parsed_files}
    module_index = {}
    for path, pf in files.items():
        if path.endswith(".py"):
            key = path[:-3].replace("/", ".")
            module_index[key] = path
            module_index[key.split(".")[-1]] = path
        base = os.path.splitext(os.path.basename(path))[0]
        module_index.setdefault(base, path)
    edges = set()
    for path, pf in files.items():
        for imp in pf.get("imports", []):
            tail = imp.replace("\\", "/").split("/")[-1]
            cand = (module_index.get(imp) or module_index.get(imp.split(".")[-1])
                    or module_index.get(tail) or module_index.get(os.path.splitext(tail)[0]))
            if cand and cand != path:
                edges.add((path, cand))
    return {"files": files, "import_edges": sorted(edges)}


def architecture_json(graph, max_nodes=400):
    files = graph["files"]
    nodes = [{"id": p, "label": os.path.basename(p), "kind": "file",
              "language": files[p]["language"]} for p in list(files)[:max_nodes]]
    keep = {n["id"] for n in nodes}
    edges = [{"source": s, "target": t, "type": "imports"}
             for s, t in graph["import_edges"] if s in keep and t in keep]
    return {"nodes": nodes, "edges": edges}
