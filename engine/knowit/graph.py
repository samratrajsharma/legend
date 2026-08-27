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


def _module_of(file_rel):
    """file path -> importable module name(s): 'a/b.py' -> {'a.b', 'b'}."""
    if not file_rel.endswith(".py"):
        base = file_rel.rsplit("/", 1)[-1].rsplit(os.sep, 1)[-1]
        return {base}
    stem = file_rel[:-3].replace(os.sep, ".").replace("/", ".")
    return {stem, stem.split(".")[-1]}


def build_graph(parsed_files):
    g = CodeGraph()
    name_index = defaultdict(list)          # base name -> [symbol_id]  (repo-wide)
    file_name_index = defaultdict(list)     # (file, name) -> [symbol_id]  (same-file)
    file_modules = {}                        # symbol_id -> {module names of its file}
    module_index = {}                        # module path -> file rel

    for pf in parsed_files:
        g.add_node(pf.file, "file", {"language": pf.language, "loc": pf.loc,
                                     "imports": pf.imports, "error": pf.error})
        if pf.file.endswith(".py"):
            mod_key = pf.file[:-3].replace(os.sep, ".").replace("/", ".")
            module_index[mod_key] = pf.file
            # a package dir maps by its package path too: a/b/__init__.py -> "a.b"
            if mod_key.endswith(".__init__"):
                module_index[mod_key[:-len(".__init__")]] = pf.file
        mods = _module_of(pf.file)
        for sym in pf.symbols:
            g.add_node(sym.id, "symbol", {
                "name": sym.name, "qualname": sym.qualname, "kind": sym.kind,
                "file": sym.file, "start": sym.start_line, "end": sym.end_line,
                "doc": sym.docstring, "complexity": sym.complexity,
                "bases": sym.bases,
            })
            g.add_edge(pf.file, sym.id, "contains")
            name_index[sym.name].append(sym.id)
            file_name_index[(pf.file, sym.name)].append(sym.id)
            file_modules[sym.id] = mods

    def resolve(caller_file, caller_imp_expanded, name, want_class=False):
        """Scope a bare callee/base name to real targets instead of every
        same-named symbol in the repo (the old behaviour, which manufactured
        phantom call/inherit edges). Order: unambiguous repo-wide -> same file
        -> a candidate whose module the caller imports. Anything still ambiguous
        is left UNRESOLVED, because a wrong edge is worse than a missing one -
        callers/callees, Impact and dead-code are all built on these."""
        cands = name_index.get(name, [])
        if want_class:
            cands = [c for c in cands if (g.get(c) or {}).get("data", {}).get("kind") == "class"]
        if not cands:
            return []
        if len(cands) == 1:
            return cands
        same = list(file_name_index.get((caller_file, name), []))
        if want_class:
            same = [c for c in same if (g.get(c) or {}).get("data", {}).get("kind") == "class"]
        if same:
            return same                          # local definition wins
        if caller_imp_expanded:
            hit = [c for c in cands if file_modules.get(c, set()) & caller_imp_expanded]
            if len(hit) == 1:
                return hit                       # exactly one imported match
        return []                                # ambiguous -> unresolved

    def resolve_call(kind, caller_file, caller_class, imports, name):
        """Dispatch by receiver kind (from Symbol.call_sites, QA #12):
          self  -> a method of the caller's own class or a resolved base (never repo-wide)
          attr  -> a same-file candidate only (obj.m() with an unknown receiver: don't guess
                   across files or on repo-wide-uniqueness - that is the phantom-edge source)
          bare  -> the scoped resolve() ladder (import/same-file/unambiguous)."""
        if kind == "self":
            out = []
            if caller_class:
                mid = f"{caller_file}::{caller_class}.{name}"
                if mid in g.nodes:
                    out.append(mid)
                cn = g.get(f"{caller_file}::{caller_class}")
                if cn:
                    for base in cn["data"].get("bases", []):
                        for bt in resolve(caller_file, imports, base, want_class=True):
                            bmid = f"{bt}.{name}"
                            if bmid in g.nodes:
                                out.append(bmid)
            return out
        # attr (unknown local receiver) and bare both use the scoped ladder; the phantom
        # source - imported-module receivers - was already dropped at parse (_call_site).
        return resolve(caller_file, imports, name)

    for pf in parsed_files:
        # expand the caller's imports ONCE per file (was rebuilt per call/base edge)
        imp_expanded = set(pf.imports) | {i.split(".")[-1] for i in pf.imports}
        for sym in pf.symbols:
            if sym.parent:
                parent_id = f"{pf.file}::{sym.parent}"
                if parent_id in g.nodes:
                    g.add_edge(sym.id, parent_id, "method_of")
            sites = getattr(sym, "call_sites", None)
            if not sites and sym.calls:
                sites = [("bare", c) for c in sym.calls]   # old-pickle fallback
            for kind, callee in (sites or []):
                for target in resolve_call(kind, pf.file, sym.parent, imp_expanded, callee):
                    if target != sym.id:
                        g.add_edge(sym.id, target, "calls")
            for base in sym.bases:
                for target in resolve(pf.file, imp_expanded, base, want_class=True):
                    if target != sym.id:
                        g.add_edge(sym.id, target, "inherits")

    import posixpath as _pp
    _JS_EXTS = (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs")
    files_norm = {pf.file.replace(os.sep, "/"): pf.file for pf in parsed_files}

    def _resolve_js_import(importer, spec):
        # only local (relative) specifiers resolve to a repo file; bare specs are npm pkgs
        if not spec.startswith("."):
            return None
        imp = importer.replace(os.sep, "/")
        base = imp.rsplit("/", 1)[0] if "/" in imp else ""
        target = _pp.normpath(_pp.join(base, spec))
        for c in [target] + [target + e for e in _JS_EXTS] +                  [target + "/index" + e for e in _JS_EXTS]:
            if c in files_norm:
                return files_norm[c]
        return None

    for pf in parsed_files:
        seen_imp = set()
        is_js = pf.language in ("javascript", "typescript")
        for imp in pf.imports:
            dst = _resolve_js_import(pf.file, imp) if is_js else module_index.get(imp)
            if dst and dst != pf.file and dst not in seen_imp:
                seen_imp.add(dst)
                g.add_edge(pf.file, dst, "imports")
    return g
