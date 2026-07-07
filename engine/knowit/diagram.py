"""Generate Mermaid diagrams from the code graph."""
from __future__ import annotations
import os
import re


def _safe(s):
    return "n_" + re.sub(r"[^0-9a-zA-Z]", "_", s)


def _label(s):
    return s.replace('"', "'")


def architecture_mermaid(idx, max_nodes=60):
    """File-level import/dependency graph (Mermaid flowchart, grouped by directory)."""
    g = idx.graph
    files = [nid for nid, n in g.nodes.items()
             if n["type"] == "file" and n["data"].get("language") == "python"]
    edges = []
    for f in files:
        for dst in g.successors(f, "imports"):
            d = g.get(dst)
            if d and d["type"] == "file":
                edges.append((f, dst))

    if len(files) > max_nodes:
        keep = {x for e in edges for x in e}
        files = [f for f in files if f in keep][:max_nodes]
        fset = set(files)
        edges = [(a, b) for a, b in edges if a in fset and b in fset]

    groups = {}
    for f in files:
        parts = f.replace("\\", "/").split("/")
        d = parts[0] if len(parts) > 1 else "(root)"
        groups.setdefault(d, []).append(f)

    lines = ["flowchart LR"]
    multi = len(groups) > 1
    for d, fs in sorted(groups.items()):
        if multi:
            lines.append(f'  subgraph {_safe(d)}["{_label(d)}/"]')
        for f in fs:
            nsym = len(g.successors(f, "contains"))
            lines.append(f'    {_safe(f)}["{_label(os.path.basename(f))} ({nsym})"]')
        if multi:
            lines.append("  end")
    for a, b in edges:
        lines.append(f"  {_safe(a)} --> {_safe(b)}")
    if not edges:
        lines.append("  %% no internal import edges detected")
    return "\n".join(lines)


def neighborhood_mermaid(idx, node_id, radius=1):
    """Call-graph neighborhood around a symbol (Mermaid flowchart)."""
    g = idx.graph
    if node_id not in g.nodes:
        return "flowchart LR\n  empty[\"(symbol not found)\"]"
    nodes = {node_id}
    frontier = {node_id}
    for _ in range(radius):
        nxt = set()
        for n in frontier:
            nxt.update(g.callees(n))
            nxt.update(g.callers(n))
        nodes |= nxt
        frontier = nxt

    lines = ["flowchart LR"]
    for n in nodes:
        data = g.get(n)["data"]
        focus = ":::focus" if n == node_id else ""
        lines.append(f'  {_safe(n)}["{_label(data.get("qualname", n))}"]{focus}')
    seen = set()
    for n in nodes:
        for c in g.callees(n):
            if c in nodes and (n, c) not in seen:
                seen.add((n, c))
                lines.append(f"  {_safe(n)} --> {_safe(c)}")
    lines.append("  classDef focus fill:#2E75B6,color:#ffffff,stroke:#1F3864;")
    return "\n".join(lines)


# ============================ Graphviz DOT (native render) ============================
_CODE_LANGS = ("python", "javascript", "typescript")


def architecture_dot(idx, max_nodes=80):
    """File dependency graph as Graphviz DOT (rendered natively by Streamlit)."""
    g = idx.graph
    files = [nid for nid, n in g.nodes.items()
             if n["type"] == "file" and n["data"].get("language") in _CODE_LANGS]
    edges = [(f, d) for f in files for d in g.successors(f, "imports")
             if g.get(d) and g.get(d)["type"] == "file"]
    if len(files) > max_nodes:
        keep = {x for e in edges for x in e}
        files = [f for f in files if f in keep][:max_nodes]
        fs = set(files)
        edges = [(a, b) for a, b in edges if a in fs and b in fs]
    groups = {}
    for f in files:
        parts = f.replace("\\", "/").split("/")
        groups.setdefault(parts[0] if len(parts) > 1 else "(root)", []).append(f)
    out = ['digraph G {', '  rankdir=LR;',
           '  node [shape=box style="rounded,filled" fillcolor="#EAF1FB" '
           'color="#2E75B6" fontname="Helvetica" fontsize=10];',
           '  edge [color="#9aa7b4"];']
    multi = len(groups) > 1
    for i, (d, fs) in enumerate(sorted(groups.items())):
        if multi:
            out.append(f'  subgraph cluster_{i} {{ label="{d}/"; style=rounded; color="#cccccc";')
        for f in fs:
            nsym = len(g.successors(f, "contains"))
            out.append(f'    "{f}" [label="{os.path.basename(f)}\\n({nsym})"];')
        if multi:
            out.append('  }')
    for a, b in edges:
        out.append(f'  "{a}" -> "{b}";')
    if not edges:
        out.append('  label="no internal import edges detected"; labelloc=b;')
    out.append('}')
    return "\n".join(out)


def class_dot(idx, max_classes=40):
    """UML-ish class diagram with methods and inheritance edges."""
    g = idx.graph
    classes = [(nid, n["data"]) for nid, n in g.nodes.items()
               if n["type"] == "symbol" and n["data"]["kind"] == "class"][:max_classes]
    out = ['digraph G {', '  rankdir=BT;',
           '  node [shape=record fontname="Helvetica" fontsize=10 style=filled '
           'fillcolor="#F3F7FC" color="#2E75B6"];']
    present = {nid for nid, _ in classes}
    for nid, d in classes:
        methods = [g.get(m)["data"]["name"] for m in g.predecessors(nid, "method_of")]
        body = "\\l".join(methods) + "\\l" if methods else ""
        label = d["qualname"] + ("|" + body if body else "")
        out.append(f'  "{nid}" [label="{{{label}}}"];')
    for nid, d in classes:
        for base in g.successors(nid, "inherits"):
            if base in present:
                out.append(f'  "{nid}" -> "{base}" [arrowhead=onormal];')
    if not classes:
        out.append('  label="no classes found"; labelloc=b;')
    out.append('}')
    return "\n".join(out)


def callflow_dot(idx, node_id, depth=3, max_nodes=40):
    """Downstream call flow from a symbol (approximates a sequence/data-flow view)."""
    g = idx.graph
    if node_id not in g.nodes:
        return 'digraph G { "n" [label="(symbol not found)"]; }'
    nodes, edges, frontier = {node_id}, set(), [node_id]
    for _ in range(depth):
        nxt = []
        for n in frontier:
            for c in g.callees(n):
                edges.add((n, c))
                if c not in nodes and len(nodes) < max_nodes:
                    nodes.add(c)
                    nxt.append(c)
        frontier = nxt
    out = ['digraph G {', '  rankdir=LR;',
           '  node [shape=box style="rounded,filled" fillcolor="#F3F7FC" '
           'color="#2E75B6" fontname="Helvetica" fontsize=10];']
    for n in nodes:
        d = g.get(n)["data"]
        foc = ' fillcolor="#2E75B6" fontcolor="white"' if n == node_id else ''
        out.append(f'  "{n}" [label="{d.get("qualname", n)}"{foc}];')
    for a, b in edges:
        if a in nodes and b in nodes:
            out.append(f'  "{a}" -> "{b}";')
    out.append('}')
    return "\n".join(out)


def knowledge_dot(idx, max_nodes=70):
    """Files + their symbols + relationships — a compact knowledge graph."""
    g = idx.graph
    out = ['digraph G {', '  rankdir=LR;', '  node [fontname="Helvetica" fontsize=9];']
    count = 0
    sym_nodes = set()
    for nid, n in g.nodes.items():
        if count >= max_nodes:
            break
        if n["type"] == "file" and n["data"].get("language") in _CODE_LANGS:
            out.append(f'  "{nid}" [shape=folder fillcolor="#FFF3D6" style=filled color="#C9A227"];')
            count += 1
            for sym in g.successors(nid, "contains")[:8]:
                if count >= max_nodes:
                    break
                d = g.get(sym)["data"]
                out.append(f'  "{sym}" [shape=ellipse label="{d["name"]}" '
                           f'fillcolor="#F3F7FC" style=filled color="#2E75B6"];')
                out.append(f'  "{nid}" -> "{sym}" [color="#cccccc" arrowhead=none];')
                sym_nodes.add(sym)
                count += 1
    for a in list(sym_nodes):
        for b in g.callees(a):
            if b in sym_nodes:
                out.append(f'  "{a}" -> "{b}" [color="#2E75B6"];')
    out.append('}')
    return "\n".join(out)


# ============================ Interactive explorer ============================
ROLE_COLOR = {"entry": "#2E8B57", "hub": "#2E75B6", "unused": "#C0392B",
              "focus": "#7E3FF2", "normal": "#EAF1FB"}
_EDGE_TYPES = ("calls", "imports", "contains", "method_of", "inherits")


def _tooltip(node):
    d = node["data"]
    if node["type"] == "file":
        return f"{d.get('language', 'file')} · {d.get('loc', 0)} LOC".replace('"', "'")
    doc = (d.get("doc") or "").splitlines()
    doc = doc[0] if doc else ""
    return (f"{d.get('qualname', '')} · {d.get('kind', '')} · "
            f"cx {d.get('complexity', 0)} · {doc}").replace('"', "'").replace("\n", " ")[:150]


def node_roles(idx):
    from .insights import repo_insights
    ins = repo_insights(idx)
    roles = {}
    for f in ins["entry_files"]:
        roles[f] = "entry"
    for h in ins["hub_files"][:5]:
        roles.setdefault(h["file"], "hub")
    for u in ins["likely_unused"]:
        roles[f"{u['file']}::{u['symbol']}"] = "unused"
    return roles


def neighborhood(idx, focus, depth=1, etypes=_EDGE_TYPES):
    g = idx.graph
    if focus not in g.nodes:
        return set(), []
    etypes = tuple(etypes) or _EDGE_TYPES
    nodes, frontier = {focus}, {focus}
    for _ in range(max(1, depth)):
        nxt = set()
        for n in list(frontier):
            for d, t in g._out.get(n, []):
                if t in etypes:
                    nxt.add(d)
            for srcn, t in g._in.get(n, []):
                if t in etypes:
                    nxt.add(srcn)
        nodes |= nxt
        frontier = nxt
    edges = [(s, d, t) for s, d, t in g.all_edges()
             if t in etypes and s in nodes and d in nodes]
    return nodes, edges


def focused_dot(idx, focus, nodes, edges, roles, path=()):
    g = idx.graph
    pset = set(path)
    out = ["digraph G {", "  rankdir=LR;",
           '  node [shape=box style="rounded,filled" fontname="Helvetica" fontsize=10 color="#2E75B6"];']
    for n in nodes:
        nd = g.get(n)
        if not nd:
            continue
        d = nd["data"]
        label = d.get("qualname") or os.path.basename(n)
        role = "focus" if n == focus else roles.get(n, "normal")
        fill = ROLE_COLOR.get(role, "#EAF1FB")
        fc = "#ffffff" if role in ("entry", "hub", "unused", "focus") else "#000000"
        pen = " penwidth=3" if n in pset else ""
        out.append(f'  "{n}" [label="{label}" fillcolor="{fill}" fontcolor="{fc}" '
                   f'tooltip="{_tooltip(nd)}"{pen}];')
    for s, d, t in edges:
        col = "#7E3FF2" if (s in pset and d in pset) else "#9aa7b4"
        out.append(f'  "{s}" -> "{d}" [color="{col}" tooltip="{t}"];')
    out.append("}")
    return "\n".join(out)


def pyvis_html(idx, focus, nodes, edges, roles, height=540, hierarchical=False):
    """Interactive draggable/zoom/hover canvas via pyvis with INLINED assets (no CDN).
    Returns HTML string, or None if pyvis isn't installed."""
    try:
        from pyvis.network import Network
    except Exception:
        return None
    g = idx.graph
    net = Network(height=f"{height}px", width="100%", directed=True,
                  cdn_resources="in_line", bgcolor="#ffffff", font_color="#222222")
    if hierarchical:
        net.set_options('{"layout":{"hierarchical":{"enabled":true,"direction":"LR",'
                        '"levelSeparation":170,"nodeSpacing":120,"sortMethod":"directed"}},'
                        '"physics":{"enabled":false}}')
    else:
        net.barnes_hut(spring_length=120)
    for n in nodes:
        nd = g.get(n)
        if not nd:
            continue
        role = "focus" if n == focus else roles.get(n, "normal")
        net.add_node(n, label=(nd["data"].get("qualname") or os.path.basename(n)),
                     title=_tooltip(nd), color=ROLE_COLOR.get(role, "#EAF1FB"),
                     size=26 if role == "focus" else 15)
    for s, d, t in edges:
        if s in nodes and d in nodes:
            net.add_edge(s, d, title=t)
    try:
        return net.generate_html(notebook=False)
    except Exception:
        try:
            return net.generate_html()
        except Exception:
            return None


def path_between(idx, a, b, etypes=("calls", "imports")):
    from collections import deque
    g = idx.graph
    if a not in g.nodes or b not in g.nodes:
        return []
    prev, q = {a: None}, deque([a])
    while q:
        n = q.popleft()
        if n == b:
            break
        for d, t in g._out.get(n, []):
            if t in etypes and d not in prev:
                prev[d] = n
                q.append(d)
    if b not in prev:
        return []
    path, cur = [], b
    while cur is not None:
        path.append(cur)
        cur = prev[cur]
    return list(reversed(path))


def explain_view_llm(idx, nodes, edges, focus, model, extra=None):
    if not model:
        return None
    try:
        from . import llm
        g = idx.graph
        nn = [g.get(n)["data"].get("qualname", n) for n in list(nodes)[:30]]
        ee = [f"{g.get(s)['data'].get('qualname', s)} -{t}-> {g.get(d)['data'].get('qualname', d)}"
              for s, d, t in edges[:40]]
        prompt = ("Explain this part of a codebase to a new engineer in <120 words. "
                  f"Focus: {g.get(focus)['data'].get('qualname', focus)}.\n"
                  f"Components: {nn}\nRelationships: {ee}")
        r = llm._complete(model, [
            {"role": "system", "content": "You teach codebases clearly and concisely."},
            {"role": "user", "content": prompt}], extra=extra, temperature=0.2, timeout=60)
        return r["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return f"[LLM unavailable: {type(e).__name__}: {e}]"


# ============================ Mind map (compact branching tree) ============================
_DEPTH_FILL = ["#1F3864", "#2E75B6", "#5B9BD5", "#9DC3E6", "#CFE0F1"]


def _mm_children(g, node, etypes):
    """Outward children for the mind map, by node type."""
    if node == "__repo__":
        return [nid for nid, n in g.nodes.items()
                if n["type"] == "file" and n["data"].get("language") in _CODE_LANGS]
    nd = g.get(node)
    if not nd:
        return []
    out = []
    if nd["type"] == "file":
        if "contains" in etypes:
            out += g.successors(node, "contains")
        if "imports" in etypes:
            out += g.successors(node, "imports")
    else:
        if "calls" in etypes:
            out += g.callees(node)
        if "method_of" in etypes:
            out += g.predecessors(node, "method_of")   # a class's methods
    return out


def mindmap_tree(idx, root, depth=2, etypes=("contains", "calls"), max_children=7):
    """Single-parent BFS tree (first discovery wins) with capped depth and breadth, so
    the result is a clean mind map rather than a tangled graph."""
    g = idx.graph
    if root != "__repo__" and root not in g.nodes:
        return {root}, []
    nodes, tree, frontier = {root}, [], [root]
    for _ in range(max(1, depth)):
        nxt = []
        for n in frontier:
            count = 0
            for c in _mm_children(g, n, etypes):
                if c in nodes:
                    continue
                nodes.add(c)
                tree.append((n, c))
                nxt.append(c)
                count += 1
                if count >= max_children:
                    break
        frontier = nxt
    return nodes, tree


def mindmap_dot(idx, root, nodes, tree, roles, repo_name="repo"):
    g = idx.graph
    from collections import defaultdict, deque
    kids = defaultdict(list)
    for a, b in tree:
        kids[a].append(b)
    depth = {root: 0}
    q = deque([root])
    while q:
        u = q.popleft()
        for v in kids[u]:
            if v not in depth:
                depth[v] = depth[u] + 1
                q.append(v)
    out = ["digraph G {", "  rankdir=LR;",
           '  graph [splines=curved nodesep=0.22 ranksep=0.65 bgcolor="transparent"];',
           '  node [shape=box style="rounded,filled" fontname="Helvetica" fontsize=10 penwidth=0];',
           '  edge [arrowsize=0.5 penwidth=1.3];']
    for n in nodes:
        d = depth.get(n, 1)
        fill = _DEPTH_FILL[min(d, len(_DEPTH_FILL) - 1)]
        fc = "#ffffff" if d <= 1 else "#15243b"
        if roles.get(n) == "unused":
            fill, fc = "#C0392B", "#ffffff"
        elif roles.get(n) == "entry" and n != root:
            fill, fc = "#2E8B57", "#ffffff"
        if n == "__repo__":
            label = repo_name + "  (repo)"
        else:
            nd = g.get(n)
            label = (nd["data"].get("qualname") or os.path.basename(n)) if nd else n
        big = " fontsize=13" if n == root else ""
        out.append(f'  "{n}" [label="{_label(label)}" fillcolor="{fill}" fontcolor="{fc}"{big}];')
    for a, b in tree:
        col = _DEPTH_FILL[min(depth.get(b, 1), len(_DEPTH_FILL) - 1)]
        out.append(f'  "{a}" -> "{b}" [color="{col}"];')
    if len(nodes) == 1:
        out.append('  label="(no outgoing relationships of the selected kinds)"; labelloc=b;')
    out.append("}")
    return "\n".join(out)
