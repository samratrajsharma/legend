from __future__ import annotations
import os
from collections import defaultdict


class CodeGraph:
    """Pure-Python directed multigraph of code structure.

    Node ids:
      - file node:   repo-relative path, e.g. "infer.py"
      - symbol node: "<rel_path>::<qualname>", e.g. "model.py::Detector.predict"
    Edge types: contains, method_of, calls, imports
    """

    def __init__(self):
        self.nodes = {}                  # id -> {"type":..., "data":...}
        self._out = defaultdict(list)    # id -> [(dst, etype)]
        self._in = defaultdict(list)     # id -> [(src, etype)]

    def add_node(self, nid, ntype, data=None):
        if nid not in self.nodes:
            self.nodes[nid] = {"type": ntype, "data": data or {}}
        return nid

    def add_edge(self, src, dst, etype):
        if src in self.nodes and dst in self.nodes:
            self._out[src].append((dst, etype))
            self._in[dst].append((src, etype))

    def successors(self, nid, etype=None):
        return [d for d, t in self._out.get(nid, []) if etype is None or t == etype]

    def predecessors(self, nid, etype=None):
        return [s for s, t in self._in.get(nid, []) if etype is None or t == etype]

    def neighbors(self, nid):
        return list({d for d, _ in self._out.get(nid, [])}
                    | {s for s, _ in self._in.get(nid, [])})

    def callees(self, sym_id):
        return self.successors(sym_id, "calls")

    def callers(self, sym_id):
        return self.predecessors(sym_id, "calls")

    def get(self, nid):
        return self.nodes.get(nid)

    def all_edges(self, etype=None):
        return [(src, dst, t) for src, lst in self._out.items()
                for dst, t in lst if etype is None or t == etype]

    def stats(self):
        et = defaultdict(int)
        for lst in self._out.values():
            for _, t in lst:
                et[t] += 1
        nt = defaultdict(int)
        for v in self.nodes.values():
            nt[v["type"]] += 1
        return {"nodes": len(self.nodes), "edges": sum(et.values()),
                "node_types": dict(nt), "edge_types": dict(et)}


def build_graph(parsed_files):
    g = CodeGraph()
    name_index = defaultdict(list)   # base name -> [symbol_id]
    module_index = {}                # module path -> file rel

    for pf in parsed_files:
        g.add_node(pf.file, "file", {"language": pf.language, "loc": pf.loc,
                                     "imports": pf.imports, "error": pf.error})
        if pf.file.endswith(".py"):
            mod_key = pf.file[:-3].replace(os.sep, ".").replace("/", ".")
            module_index[mod_key] = pf.file
            module_index[mod_key.split(".")[-1]] = pf.file
        for sym in pf.symbols:
            g.add_node(sym.id, "symbol", {
                "name": sym.name, "qualname": sym.qualname, "kind": sym.kind,
                "file": sym.file, "start": sym.start_line, "end": sym.end_line,
                "doc": sym.docstring, "complexity": sym.complexity,
                "bases": sym.bases,
            })
            g.add_edge(pf.file, sym.id, "contains")
            name_index[sym.name].append(sym.id)

    for pf in parsed_files:
        for sym in pf.symbols:
            if sym.parent:
                parent_id = f"{pf.file}::{sym.parent}"
                if parent_id in g.nodes:
                    g.add_edge(sym.id, parent_id, "method_of")
            for callee in sym.calls:
                for target in name_index.get(callee, []):
                    if target != sym.id:
                        g.add_edge(sym.id, target, "calls")
            for base in sym.bases:
                for target in name_index.get(base, []):
                    tn = g.get(target)
                    if target != sym.id and tn and tn["data"].get("kind") == "class":
                        g.add_edge(sym.id, target, "inherits")

    for pf in parsed_files:
        for imp in pf.imports:
            dst = module_index.get(imp) or module_index.get(imp.split(".")[-1])
            if dst and dst != pf.file:
                g.add_edge(pf.file, dst, "imports")
    return g
