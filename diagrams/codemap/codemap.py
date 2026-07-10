#!/usr/bin/env python3
"""
codemap.py — interactive, drill-down architecture mindmap for ANY codebase.
===========================================================================
Point it at a repo; it statically reads the source (no importing, no deps),
groups files into AREAS by directory, works out which area imports which,
and writes ONE self-contained .html with THREE levels of zoom:

  1. AREA MINDMAP   nodes = areas (sized by lines, coloured by dependency layer),
                    edges = "imports from". Hover to trace, drag/scroll to move.
  2. AREA DRILL-IN  click an area -> it opens and lists every file inside.
  3. FILE VIEW      click a file -> source on the right, auto deep-dive on the
                    left (what it defines, how it wires in, classes & functions).

Languages: Python (.py) full AST; JS/TS best-effort regex; others listed.

USAGE
  python codemap.py <repo> [-o map.html] [--title T] [--depth N]
                    [--ext .py,.ts] [--md] [--open] [--no-src] [--max-src KB]
Stdlib only. Python 3.8+.
"""
from __future__ import annotations
import argparse, ast, json, os, re, webbrowser
from pathlib import Path

DEFAULT_EXT = {".py", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"}
JS_EXT = {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"}
SKIP_DIRS = {".git", "__pycache__", "node_modules", ".venv", "venv", "env",
             ".env", "build", "dist", ".next", ".nuxt", ".idea", ".vscode",
             "site-packages", ".mypy_cache", ".pytest_cache", "coverage",
             ".tox", ".gradle", "target", "vendor", "bower_components", ".cache"}

def first_para(doc, n=300):
    if not doc:
        return ""
    para = re.split(r"\n\s*\n", doc.strip(), 1)[0]
    para = re.sub(r"\s+", " ", para).strip()
    return (para[:n] + "…") if len(para) > n else para

def _sig(node):
    a = node.args
    parts = [ar.arg for ar in (getattr(a, "posonlyargs", []) + a.args)]
    if a.vararg: parts.append("*" + a.vararg.arg)
    elif a.kwonlyargs: parts.append("*")
    parts += [k.arg for k in a.kwonlyargs]
    if a.kwarg: parts.append("**" + a.kwarg.arg)
    return "(" + ", ".join(parts) + ")"

def analyze_py(src):
    info = {"lines": src.count("\n") + 1, "classes": [], "funcs": [],
            "imports": set(), "doc": "", "src": src, "ok": True}
    try:
        tree = ast.parse(src)
    except Exception:
        info["ok"] = False
        return info
    info["doc"] = ast.get_docstring(tree) or ""
    for nd in tree.body:
        if isinstance(nd, ast.ClassDef):
            meth = [m.name for m in nd.body if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))][:14]
            info["classes"].append({"n": nd.name, "doc": first_para(ast.get_docstring(nd), 180), "m": meth})
        elif isinstance(nd, (ast.FunctionDef, ast.AsyncFunctionDef)):
            info["funcs"].append({"n": nd.name, "sig": _sig(nd), "doc": first_para(ast.get_docstring(nd), 180)})
    for nd in ast.walk(tree):
        if isinstance(nd, ast.Import):
            for a in nd.names:
                info["imports"].add(("abs", a.name))
        elif isinstance(nd, ast.ImportFrom):
            info["imports"].add(("rel" if nd.level else "abs", "." * nd.level + (nd.module or "")))
    return info

JS_CLASS = re.compile(r"\bclass\s+([A-Za-z_$][\w$]*)")
JS_FUNC = re.compile(r"\bfunction\s+([A-Za-z_$][\w$]*)|\bexport\s+(?:default\s+)?function\s+([A-Za-z_$][\w$]*)|\b(?:export\s+)?const\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?\([^)]*\)\s*=>")
JS_IMP = re.compile(r"""\bimport\b[^'"]*?['"]([^'"]+)['"]|\brequire\(\s*['"]([^'"]+)['"]\s*\)|\bexport\b[^'"]*?\bfrom\s+['"]([^'"]+)['"]""")
def analyze_js(src):
    info = {"lines": src.count("\n") + 1, "classes": [], "funcs": [],
            "imports": set(), "doc": "", "src": src, "ok": True}
    m = re.match(r"\s*/\*\*?(.*?)\*/", src, re.S)
    if m:
        info["doc"] = re.sub(r"^\s*\*", "", m.group(1), flags=re.M).strip()
    info["classes"] = [{"n": x, "doc": "", "m": []} for x in JS_CLASS.findall(src)[:14]]
    info["funcs"] = [{"n": g, "sig": "()", "doc": ""} for tup in JS_FUNC.findall(src) for g in tup if g][:14]
    for tup in JS_IMP.findall(src):
        spec = next((g for g in tup if g), "")
        if spec.startswith("."):
            info["imports"].add(("path", spec))
    return info

def analyze(path):
    src = path.read_text(encoding="utf-8", errors="replace")
    ext = path.suffix.lower()
    if ext == ".py":
        return analyze_py(src)
    if ext in JS_EXT:
        return analyze_js(src)
    return {"lines": src.count("\n") + 1, "classes": [], "funcs": [],
            "imports": set(), "doc": "", "src": src, "ok": True}

def discover(root, exts):
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
        for fn in filenames:
            if Path(fn).suffix.lower() not in exts or fn.endswith(".min.js"):
                continue
            p = Path(dirpath) / fn
            out.append((p, p.relative_to(root).as_posix()))
    return sorted(out, key=lambda x: x[1])

def area_for(rel, depth):
    parts = rel.split("/")
    return "(root)" if len(parts) == 1 else "/".join(parts[:min(depth, len(parts) - 1)])

def pick_depth(files, forced):
    if forced:
        return forced
    counts = {d: len({area_for(rel, d) for _p, rel in files}) for d in (1, 2, 3)}
    cand = [d for d in (3, 2, 1) if counts[d] <= 25]
    return cand[0] if cand else 1

def build(root, exts, depth):
    files = discover(root, exts)
    if not files:
        raise SystemExit("No source files (%s) found under %s" % (", ".join(sorted(exts)), root))
    depth = pick_depth(files, depth)
    mods, reg, pidx = {}, {}, {}
    for p, rel in files:
        info = analyze(p)
        info["area"] = area_for(rel, depth)
        info["name"] = Path(rel).name
        mods[rel] = info
        stem = Path(rel).stem
        reg.setdefault(stem, rel)
        reg.setdefault(Path(rel).parent.name + "." + stem, rel)
        reg.setdefault(rel[:-len(Path(rel).suffix)].replace("/", "."), rel)
        pidx[rel[:-len(Path(rel).suffix)]] = rel
        if rel.endswith("__init__.py"):
            reg.setdefault(Path(rel).parent.name, rel)

    def resolve(kind, spec, rel):
        if kind == "path":
            segs = []
            for s in (Path(rel).parent / spec).as_posix().split("/"):
                if s == "..":
                    if segs: segs.pop()
                elif s not in ("", "."):
                    segs.append(s)
            cand = "/".join(segs)
            for c in (cand, cand + "/index"):
                if c in pidx: return pidx[c]
            return None
        if kind == "rel":
            pkg = Path(rel).parent
            for _ in range(max(0, (len(spec) - len(spec.lstrip("."))) - 1)):
                pkg = pkg.parent
            tail = spec.lstrip(".")
            cand = (pkg / tail.replace(".", "/")).as_posix() if tail else pkg.as_posix() + "/__init__"
            for c in (cand, cand + "/__init__"):
                if c in pidx: return pidx[c]
            return reg.get(tail.split(".")[-1]) if tail else None
        for c in (spec, spec.split(".")[0], spec.split(".")[-1]):
            if c in reg: return reg[c]
        return None

    area_edges = set()
    for rel, info in mods.items():
        a = info["area"]; deps, fdeps = set(), set()
        for kind, spec in info["imports"]:
            tgt = resolve(kind, spec, rel)
            if tgt and tgt in mods and tgt != rel:
                deps.add(Path(tgt).stem); fdeps.add(tgt)
                if mods[tgt]["area"] != a:
                    area_edges.add((a, mods[tgt]["area"]))
        info["deps"] = sorted(deps); info["fdeps"] = sorted(fdeps)
    for info in mods.values():
        info["fused"] = []
    for rel, info in mods.items():
        for t in info["fdeps"]:
            mods[t]["fused"].append(rel)
    for info in mods.values():
        info["fused"] = sorted(set(info["fused"]))
    return mods, area_edges, depth

def layer(area_ids, edges):
    out = {a: set() for a in area_ids}
    for s, t in edges:
        out[s].add(t)
    memo = {}
    def height(a, stack):
        if a in memo: return memo[a]
        if a in stack: return 0
        stack.add(a); h = 0
        for b in out[a]:
            if b != a:
                h = max(h, 1 + height(b, stack))
        stack.discard(a); memo[a] = h; return h
    hs = {a: height(a, set()) for a in area_ids}
    mx = max(hs.values()) if hs else 0
    return {a: mx - hs[a] for a in area_ids}, mx + 1

PALETTE = ["#a855f7", "#3b82f6", "#14b8a6", "#22c55e", "#f59e0b", "#ef4444", "#ec4899", "#84cc16"]

def render_html(mods, area_edges, depth, title, embed, max_src):
    by_area = {}
    for rel, info in mods.items():
        by_area.setdefault(info["area"], []).append((rel, info))
    area_ids = sorted(by_area)
    bands, nbands = layer(area_ids, area_edges)
    colors = [PALETTE[b % len(PALETTE)] for b in range(nbands)]
    bandname = [("LAYER 0 · entry / top-level" if b == 0 else
                 ("LAYER %d · foundation" % b if b == nbands - 1 else "LAYER %d" % b))
                for b in range(nbands)]
    short = lambda a: a if a == "(root)" else "/".join(a.split("/")[-2:])
    areas = [{"id": a, "name": short(a), "files": len(by_area[a]),
              "lines": sum(i["lines"] for _r, i in by_area[a]), "band": bands[a]} for a in area_ids]
    areas.sort(key=lambda x: (x["band"], -x["lines"]))
    AREAFILES = {a: [rel for rel, _ in sorted(by_area[a])] for a in area_ids}
    FILEINDEX, SRC = {}, {}
    for a in area_ids:
        for rel, info in sorted(by_area[a]):
            FILEINDEX[rel] = {"n": info["name"], "area": a, "l": info["lines"],
                              "c": info.get("classes", []), "f": info.get("funcs", []),
                              "deps": info.get("fdeps", []), "used": info.get("fused", []),
                              "doc": info.get("doc", ""), "ok": info.get("ok", True)}
            if embed and info.get("src") is not None:
                s = info["src"]
                SRC[rel] = (s[:max_src] + "\n\n… [truncated in map — open the file for the rest]") if len(s) > max_src else s
    AREADESC = {}
    for a in area_ids:
        init = next((i for _r, i in by_area[a] if _r.endswith("__init__.py") and i.get("doc")), None)
        AREADESC[a] = first_para(init["doc"]) if init else \
            ("%d files · %s lines under “%s”." % (len(by_area[a]), format(sum(i['lines'] for _r,i in by_area[a]), ','), a))
    total = len(mods); loc = sum(i["lines"] for i in mods.values())
    sub = "%d modules · %s lines · %d areas · grouped by directory (depth %d)" % (total, format(loc, ","), len(area_ids), depth)
    data = dict(areas=areas, E=sorted([list(e) for e in area_edges]), AREAFILES=AREAFILES,
                FILEINDEX=FILEINDEX, SRC=SRC, AREADESC=AREADESC, BANDNAME=bandname,
                COLORS=colors, EMBED=embed)
    # escape </ so an embedded source containing "</script>" cannot close the <script> block
    payload = "const DATA=" + json.dumps(data).replace("</", "<\\/") + ";"
    html = HTML_TEMPLATE.replace("/*__DATA__*/", payload)
    return html.replace("__TITLE__", title).replace("__SUB__", sub), (total, loc, len(area_ids), len(area_edges))

def render_md(mods, area_edges):
    by_area = {}
    for rel, info in mods.items():
        by_area.setdefault(info["area"], []).append((rel, info))
    out = ["# Architecture map", ""]
    for a in sorted(by_area):
        out += ["## " + a, "| Module | Lines | Classes | Functions | Imports |", "|---|--:|---|---|---|"]
        for rel, info in sorted(by_area[a]):
            cls = ", ".join(c["n"] for c in info["classes"][:6]) or "—"
            fns = ", ".join(fn["n"] for fn in info["funcs"][:5]) or "—"
            out.append("| `%s` | %d | %s | %s | %s |" % (info["name"], info["lines"], cls, fns, ", ".join(info["deps"][:8]) or "—"))
        out.append("")
    return "\n".join(out)

HTML_TEMPLATE = r"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>__TITLE__ — Architecture</title>
<style>
 :root{--bg:#0b1220;--panel:#111c30;--line:#1e2d45;--txt:#e6eefb;--mut:#8aa0c0}
 *{box-sizing:border-box} html,body{margin:0;height:100%}
 body{background:var(--bg);color:var(--txt);font:14px/1.5 -apple-system,Segoe UI,Roboto,sans-serif;display:flex;flex-direction:column}
 header{padding:14px 20px;border-bottom:1px solid var(--line)} header h1{margin:0;font-size:18px} header p{margin:4px 0 0;color:var(--mut);font-size:12px}
 .legend{display:flex;gap:14px;flex-wrap:wrap;margin-top:8px;font-size:12px} .legend span{display:inline-flex;align-items:center;gap:6px;color:var(--mut)}
 .dot{width:11px;height:11px;border-radius:3px;display:inline-block}
 .wrap{flex:1;display:flex;min-height:0} .stage{flex:1;position:relative;overflow:hidden}
 svg{width:100%;height:100%;display:block;cursor:grab} svg.drag{cursor:grabbing}
 .node rect{stroke:#0b1220;stroke-width:1.5;transition:opacity .12s} .node text{fill:#08101e;font-weight:600;pointer-events:none}
 .node .sub{fill:#0b1424;font-weight:500;opacity:.78} .node{cursor:pointer}
 .edge{fill:none;transition:stroke-opacity .12s,stroke-width .12s} .node.dim rect{opacity:.18} .node.dim text{opacity:.25}
 aside{width:320px;border-left:1px solid var(--line);background:var(--panel);padding:16px 18px;overflow:auto}
 aside h2{margin:.2em 0;font-size:15px} aside .tag{font-size:11px;color:var(--mut)} aside .meta{color:var(--mut);font-size:12px;margin:6px 0 12px}
 aside h3{font-size:12px;text-transform:uppercase;letter-spacing:.04em;color:var(--mut);margin:14px 0 5px}
 .pill{display:inline-block;font-size:11px;padding:2px 8px;border-radius:999px;margin:2px 4px 2px 0;cursor:pointer}
 .hint{color:var(--mut);font-size:12px} .cta{margin-top:12px;padding:8px 10px;border:1px dashed var(--line);border-radius:8px;color:var(--mut);font-size:12px}
 .ov{position:fixed;inset:0;background:rgba(6,10,20,.62);display:none;z-index:20} .ov.open{display:block}
 .sheet{position:absolute;top:0;right:0;height:100%;width:min(940px,94vw);background:var(--bg);border-left:1px solid var(--line);box-shadow:-30px 0 60px rgba(0,0,0,.5);display:flex;flex-direction:column}
 .sheet header{display:flex;align-items:flex-start;gap:14px;border-bottom:1px solid var(--line)} .sheet header .x{margin-left:auto;cursor:pointer;font-size:22px;color:var(--mut);padding:2px 6px}
 .bartag{display:inline-block;font-size:11px;font-weight:700;padding:2px 9px;border-radius:6px;color:#08101e} .sheet .role{color:var(--mut);font-size:13px;margin:6px 0 0;max-width:72ch}
 .conns{display:flex;gap:18px;flex-wrap:wrap;padding:10px 20px;border-bottom:1px solid var(--line);font-size:12px} .conns b{color:var(--mut);font-weight:600;text-transform:uppercase;font-size:11px;margin-right:6px}
 .filter{padding:10px 20px;border-bottom:1px solid var(--line)} .filter input{width:100%;background:#0c1626;border:1px solid var(--line);border-radius:8px;color:var(--txt);padding:8px 11px;font-size:13px}
 .files{flex:1;overflow:auto;padding:16px 20px;display:grid;grid-template-columns:repeat(auto-fill,minmax(290px,1fr));gap:14px;align-content:start}
 .card{background:var(--panel);border:1px solid var(--line);border-radius:11px;padding:13px 14px;cursor:pointer;transition:border-color .12s} .card:hover{border-color:#3b6ea5}
 .card .fn{font-family:ui-monospace,Consolas,monospace;font-size:13.5px;font-weight:700;color:#cfe0ff} .card .ln{float:right;color:var(--mut);font-size:11px;font-weight:600}
 .card .x{font-size:12.5px;color:#aebbd4;margin:7px 0 0} .card .cnt{margin-top:8px;font-size:11px;color:var(--mut)} .card .open{color:#3b82f6}
 .fov{position:fixed;inset:0;background:rgba(6,10,20,.72);display:none;z-index:30} .fov.open{display:flex}
 .fwin{margin:auto;width:96vw;height:94vh;background:var(--bg);border:1px solid var(--line);border-radius:12px;display:flex;flex-direction:column;overflow:hidden;box-shadow:0 30px 80px rgba(0,0,0,.6)}
 .fwin>.fh{display:flex;align-items:center;gap:12px;padding:11px 16px;border-bottom:1px solid var(--line)}
 .fwin>.fh .ffn{font-family:ui-monospace,monospace;font-weight:700;color:#cfe0ff;font-size:15px} .fwin>.fh .x{margin-left:auto;cursor:pointer;font-size:22px;color:var(--mut);padding:0 8px}
 .fbody{flex:1;display:flex;min-height:0} .fleft{width:40%;max-width:540px;overflow:auto;padding:16px 18px;border-right:1px solid var(--line)} .fright{flex:1;display:flex;min-height:0;background:#0a111f}
 .fleft h3{font-size:11px;text-transform:uppercase;color:var(--mut);letter-spacing:.04em;margin:16px 0 6px} .fleft p{font-size:13px;color:#d4e0f5;margin:6px 0}
 .rolebox{background:#0c1626;border:1px solid var(--line);border-left:3px solid #3b82f6;border-radius:8px;padding:9px 11px;font-size:12.5px;color:#cfe0ff}
 .member{border-left:2px solid var(--line);padding:1px 0 1px 10px;margin:7px 0} .member .mn{font-family:ui-monospace,monospace;color:#cfe0ff;font-size:12.5px} .member .md{color:var(--mut);font-size:12px;margin-top:2px}
 .meth{display:inline-block;font-family:ui-monospace,monospace;font-size:10.5px;color:#9fb6d8;background:#0c1626;border:1px solid var(--line);border-radius:4px;padding:0 5px;margin:3px 3px 0 0}
 .fchip{display:inline-block;font-size:11px;font-family:ui-monospace,monospace;background:#3b82f622;color:#9dc1ff;border:1px solid #3b82f655;border-radius:5px;padding:1px 6px;margin:2px 3px 0 0;cursor:pointer}
 .code{display:flex;flex:1;overflow:auto;font-family:ui-monospace,Consolas,monospace;font-size:12.5px;line-height:1.55}
 .code .gut{padding:12px 8px 12px 12px;text-align:right;color:#3f5170;user-select:none;white-space:pre}
 .code .src{padding:12px 16px 12px 8px;white-space:pre;color:#c8d6ee;flex:1;tab-size:4}
 .none{color:var(--mut);font-size:11.5px}
</style></head><body>
<header><h1>__TITLE__ — Architecture Mindmap</h1>
 <p>__SUB__ · hover to trace · <b>click an area → its files → a file → its source + deep-dive</b> · drag/scroll to pan &amp; zoom</p>
 <div class="legend" id="legend"></div></header>
<div class="wrap"><div class="stage"><svg id="svg" viewBox="0 0 1480 880" preserveAspectRatio="xMidYMid meet">
 <defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="#5b6f93"/></marker>
 <marker id="arrowhi" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="#cfe0ff"/></marker></defs>
 <g id="edges"></g><g id="nodes"></g></svg></div><aside id="panel"></aside></div>
<div class="ov" id="ov"><div class="sheet" id="sheet"></div></div>
<div class="fov" id="fov"><div class="fwin" id="fwin"></div></div>
<script>
/*__DATA__*/
const areas=DATA.areas,E=DATA.E,AREAFILES=DATA.AREAFILES,FI=DATA.FILEINDEX,SRC=DATA.SRC,AREADESC=DATA.AREADESC,BANDNAME=DATA.BANDNAME,COLORS=DATA.COLORS;
const C={}; COLORS.forEach((c,i)=>C[i]=c);
const M=Object.fromEntries(areas.map(a=>[a.id,a]));
const esc=s=>(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
const escA=s=>esc(s).replace(/"/g,'&quot;').replace(/'/g,'&#39;');
const base=r=>r.split('/').pop();
document.getElementById('legend').innerHTML=BANDNAME.map((b,i)=>`<span><i class="dot" style="background:${COLORS[i]}"></i>${b}</span>`).join('');
const NB=BANDNAME.length,W=1480,top=64,bot=812,clamp=(a,v,b)=>Math.max(a,Math.min(b,v));
const bandsY=[];for(let i=0;i<NB;i++)bandsY.push(NB<2?440:top+i*(bot-top)/(NB-1));
const maxLines=Math.max(...areas.map(a=>a.lines),1);
[...Array(NB).keys()].forEach(bi=>{const ns=areas.filter(a=>a.band===bi),n=ns.length;
 ns.forEach((a,i)=>{a.w=clamp(122,118+a.lines/maxLines*150,210);a.h=clamp(40,38+a.lines/maxLines*54,92);
  a.cx=n===1?W/2:110+i*(W-220)/(n-1);a.cy=bandsY[bi]+a.h/2;});});
const adj={};areas.forEach(a=>adj[a.id]={out:[],in:[]});
E.forEach(([s,t])=>{if(adj[s]&&adj[t]){adj[s].out.push(t);adj[t].in.push(s);}});
const gE=document.getElementById('edges'),gN=document.getElementById('nodes');
const epath=(s,t)=>{const a=M[s],b=M[t],my=(a.cy+b.cy)/2;return `M${a.cx},${a.cy} C${a.cx},${my} ${b.cx},${my} ${b.cx},${b.cy}`;};
const eEls=E.filter(([s,t])=>M[s]&&M[t]).map(([s,t])=>{const p=document.createElementNS('http://www.w3.org/2000/svg','path');
 p.setAttribute('d',epath(s,t));p.setAttribute('class','edge');p.setAttribute('stroke',C[M[s].band]);
 p.setAttribute('stroke-opacity','.13');p.setAttribute('stroke-width','1.2');p.setAttribute('marker-end','url(#arrow)');p.dataset.s=s;p.dataset.t=t;gE.appendChild(p);return p;});
const nEls={};
areas.forEach(a=>{const g=document.createElementNS('http://www.w3.org/2000/svg','g');g.setAttribute('class','node');
 const r=document.createElementNS('http://www.w3.org/2000/svg','rect');r.setAttribute('x',a.cx-a.w/2);r.setAttribute('y',a.cy-a.h/2);r.setAttribute('width',a.w);r.setAttribute('height',a.h);r.setAttribute('rx',9);r.setAttribute('fill',C[a.band]);g.appendChild(r);
 const t1=document.createElementNS('http://www.w3.org/2000/svg','text');t1.setAttribute('x',a.cx);t1.setAttribute('y',a.cy-2);t1.setAttribute('text-anchor','middle');t1.setAttribute('font-size','12.5');t1.textContent=a.name;g.appendChild(t1);
 const t2=document.createElementNS('http://www.w3.org/2000/svg','text');t2.setAttribute('x',a.cx);t2.setAttribute('y',a.cy+13);t2.setAttribute('text-anchor','middle');t2.setAttribute('font-size','10');t2.setAttribute('class','sub');t2.textContent=a.files+' files · '+a.lines.toLocaleString()+' ln';g.appendChild(t2);
 g.addEventListener('mouseenter',()=>focus(a.id));g.addEventListener('mouseleave',()=>blur());g.addEventListener('click',()=>openArea(a.id));gN.appendChild(g);nEls[a.id]=g;});
function focus(id){const nbs=new Set([id,...adj[id].out,...adj[id].in]);areas.forEach(a=>nEls[a.id].classList.toggle('dim',!nbs.has(a.id)));
 eEls.forEach(p=>{const hit=p.dataset.s===id||p.dataset.t===id;p.setAttribute('stroke-opacity',hit?'.95':'.03');p.setAttribute('stroke-width',hit?'2.4':'1');p.setAttribute('marker-end',hit?'url(#arrowhi)':'url(#arrow)');p.setAttribute('stroke',hit?'#cfe0ff':C[M[p.dataset.s].band]);});side(id);}
function blur(){areas.forEach(a=>nEls[a.id].classList.remove('dim'));eEls.forEach(p=>{p.setAttribute('stroke-opacity','.13');p.setAttribute('stroke-width','1.2');p.setAttribute('marker-end','url(#arrow)');p.setAttribute('stroke',C[M[p.dataset.s].band]);});}
const achip=d=>M[d]?`<span class="pill" style="background:${C[M[d].band]}22;color:${C[M[d].band]};border:1px solid ${C[M[d].band]}55" data-area="${escA(d)}">${M[d].name}</span>`:'';
function side(id){const a=M[id];document.getElementById('panel').innerHTML=
  `<div class="tag">${BANDNAME[a.band]}</div><h2>${a.name}</h2><div class="meta">${a.id} · ${a.files} files · ${a.lines.toLocaleString()} lines</div>
   <p class="hint">${AREADESC[id]||''}</p><h3>Depends on (${adj[id].out.length})</h3>${adj[id].out.map(achip).join('')||'<span class="hint">— leaf</span>'}
   <h3>Used by (${adj[id].in.length})</h3>${adj[id].in.map(achip).join('')||'<span class="hint">— entry point</span>'}
   <div class="cta">Click the node to open it and read every file inside.</div>`;}
if(areas.length)side(areas[0].id);
function shortDoc(F){if(F.doc)return esc(F.doc.split(/\n\s*\n/)[0].replace(/\s+/g,' ').trim()).slice(0,160);
 const b=[];if(F.c.length)b.push(F.c.length+' class'+(F.c.length>1?'es':''));if(F.f.length)b.push(F.f.length+' function'+(F.f.length>1?'s':''));
 return b.length?'Defines '+b.join(' · ')+'.':F.n+' — '+F.l+' lines.';}
const ov=document.getElementById('ov');
function fcard(rel){const F=FI[rel];return `<div class="card" data-file="${escA(rel)}">
   <span class="ln">${F.l} ln</span><span class="fn">${F.n}</span><div class="x">${shortDoc(F)}</div>
   <div class="cnt">${F.c.length} classes · ${F.f.length} functions · imports ${F.deps.length} · used by ${F.used.length} &nbsp;<span class="open">open ▸</span></div></div>`;}
function openArea(id){const a=M[id],rels=AREAFILES[id]||[];document.getElementById('sheet').innerHTML=
 `<header style="padding:16px 20px"><div><span class="bartag" style="background:${C[a.band]}">${BANDNAME[a.band]}</span>
   <h2 style="margin:8px 0 0;font-size:19px">${a.name}</h2><div class="meta" style="margin:3px 0 0">${a.id} · ${a.files} files · ${a.lines.toLocaleString()} lines</div>
   <p class="role">${AREADESC[id]||''}</p></div><div class="x" onclick="closeOv()">&times;</div></header>
  <div class="conns"><div><b>Depends on</b>${adj[id].out.map(achip).join('')||'<span class="none">leaf</span>'}</div><div><b>Used by</b>${adj[id].in.map(achip).join('')||'<span class="none">entry point</span>'}</div></div>
  <div class="filter"><input placeholder="Filter ${rels.length} files…" oninput="filt(this.value)"></div>
  <div class="files" id="filegrid">${rels.map(fcard).join('')}</div>`;ov.classList.add('open');}
function filt(q){q=q.trim().toLowerCase();document.querySelectorAll('#filegrid .card').forEach(c=>{c.style.display=(!q||c.textContent.toLowerCase().includes(q))?'':'none';});}
function closeOv(){ov.classList.remove('open');}
ov.addEventListener('click',e=>{if(e.target===ov)closeOv();});
const fov=document.getElementById('fov');
function narrative(F){const d=F.deps.length,u=F.used.length;
 if(!u&&d)return `<b>Entry point.</b> Nothing else in the repo imports this; it pulls together ${d} module(s). Typically an app, script, or test you run directly.`;
 if(!d&&u)return `<b>Foundational leaf.</b> It imports nothing else in-repo, yet ${u} module(s) depend on it — a shared building block. Changing its public surface ripples outward; treat it as stable.`;
 if(u>=5)return `<b>Hub.</b> ${u} modules import it (and it imports ${d}). High blast radius — changes here touch a lot of the system.`;
 if(!d&&!u)return `<b>Standalone.</b> No in-repo imports either way — self-contained (or wired only via dynamic/third-party paths the static scan cannot see).`;
 return `It imports ${d} in-repo module(s) and is used by ${u}. A mid-chain module — depends on what is below it and supports what is above.`;}
function fchip(rel){return FI[rel]?`<span class="fchip" title="${escA(rel)}" data-file="${escA(rel)}">${base(rel)}</span>`:'';}
function codeHtml(rel){const s=SRC[rel];if(s===undefined)return `<div class="code"><div class="src none" style="padding:16px">Source not embedded (--no-src, or file exceeded the size cap). Open ${esc(rel)} directly.</div></div>`;
 const lines=s.split('\n');const gut=lines.map((_,i)=>i+1).join('\n');return `<div class="code"><div class="gut">${gut}</div><div class="src">${esc(s)}</div></div>`;}
function openFile(rel){const F=FI[rel];if(!F)return;
 const cls=F.c.length?`<h3>Classes (${F.c.length})</h3>`+F.c.map(c=>`<div class="member"><div class="mn">class ${c.n}</div>${c.doc?`<div class="md">${esc(c.doc)}</div>`:''}${c.m&&c.m.length?c.m.map(m=>`<span class="meth">${m}()</span>`).join(''):''}</div>`).join(''):'';
 const fns=F.f.length?`<h3>Functions (${F.f.length})</h3>`+F.f.map(fn=>`<div class="member"><div class="mn">${fn.n}${fn.sig||'()'}</div>${fn.doc?`<div class="md">${esc(fn.doc)}</div>`:''}</div>`).join(''):'';
 const depc=F.deps.length?F.deps.map(fchip).join(''):'<span class="none">— none in-repo (a leaf)</span>';
 const usec=F.used.length?F.used.map(fchip).join(''):'<span class="none">— none (entry point / not imported)</span>';
 document.getElementById('fwin').innerHTML=`
  <div class="fh"><span class="bartag" style="background:${C[M[F.area].band]}">${F.area}</span><span class="ffn">${F.n}</span>
    <span class="meta" style="color:var(--mut);font-size:12px">${F.l} lines</span><div class="x" onclick="closeFov()">&times;</div></div>
  <div class="fbody"><div class="fleft">
     <div class="rolebox">${narrative(F)}</div>
     <h3>Overview</h3><p>${F.doc?esc(F.doc):'<span class="none">No docstring in the file. '+esc(shortDoc(F))+'</span>'}</p>
     <h3>Depends on (${F.deps.length})</h3>${depc}
     <h3>Used by (${F.used.length})</h3>${usec}
     ${cls}${fns}
   </div><div class="fright">${codeHtml(rel)}</div></div>`;
 fov.classList.add('open');}
function closeFov(){fov.classList.remove('open');}
fov.addEventListener('click',e=>{if(e.target===fov)closeFov();});
document.addEventListener('click',e=>{const fc=e.target.closest&&e.target.closest('[data-file]');if(fc){openFile(fc.dataset.file);return;}const ac=e.target.closest&&e.target.closest('[data-area]');if(ac){openArea(ac.dataset.area);}});
window.addEventListener('keydown',e=>{if(e.key==='Escape'){if(fov.classList.contains('open'))closeFov();else closeOv();}});
const svg=document.getElementById('svg');let vb=[0,0,1480,880],down=null;
svg.addEventListener('wheel',e=>{e.preventDefault();const k=e.deltaY>0?1.1:.9,r=svg.getBoundingClientRect();const mx=vb[0]+(e.clientX-r.left)/r.width*vb[2],my=vb[1]+(e.clientY-r.top)/r.height*vb[3];vb[2]*=k;vb[3]*=k;vb[0]=mx-(e.clientX-r.left)/r.width*vb[2];vb[1]=my-(e.clientY-r.top)/r.height*vb[3];svg.setAttribute('viewBox',vb.join(' '));},{passive:false});
svg.addEventListener('mousedown',e=>{down=[e.clientX,e.clientY,vb[0],vb[1]];svg.classList.add('drag');});
window.addEventListener('mousemove',e=>{if(!down)return;const r=svg.getBoundingClientRect();vb[0]=down[2]-(e.clientX-down[0])/r.width*vb[2];vb[1]=down[3]-(e.clientY-down[1])/r.height*vb[3];svg.setAttribute('viewBox',vb.join(' '));});
window.addEventListener('mouseup',()=>{down=null;svg.classList.remove('drag');});
svg.addEventListener('dblclick',()=>{vb=[0,0,1480,880];svg.setAttribute('viewBox',vb.join(' '));});
</script></body></html>"""

def main():
    ap = argparse.ArgumentParser(description="Interactive architecture mindmap for any codebase.")
    ap.add_argument("root")
    ap.add_argument("-o", "--out", default=None)
    ap.add_argument("--title", default=None)
    ap.add_argument("--depth", type=int, default=0, help="dir depth for grouping (0=auto)")
    ap.add_argument("--ext", default=None, help="comma list e.g. .py,.ts")
    ap.add_argument("--md", action="store_true", help="also write a Markdown index")
    ap.add_argument("--open", action="store_true", help="open the html when done")
    ap.add_argument("--no-src", action="store_true", help="do not embed source")
    ap.add_argument("--max-src", type=int, default=200, help="max KB of source per file (default 200)")
    ap.add_argument("--exclude", default=None, help="comma dir names to skip (merged into SKIP_DIRS), e.g. data,build")
    a = ap.parse_args()
    if a.exclude:
        SKIP_DIRS.update(e.strip() for e in a.exclude.split(",") if e.strip())
    root = Path(a.root).resolve()
    if not root.exists():
        raise SystemExit("path not found: " + str(root))
    exts = {e if e.startswith(".") else "." + e for e in a.ext.split(",")} if a.ext else set(DEFAULT_EXT)
    title = a.title or root.name
    out = Path(a.out) if a.out else (root.parent / (root.name + "_architecture.html"))
    mods, edges, depth = build(root, exts, a.depth or 0)
    html, (n, loc, na, ne) = render_html(mods, edges, depth, title, embed=not a.no_src, max_src=a.max_src * 1000)
    out.write_text(html, encoding="utf-8")
    print("[codemap] %d files · %s lines · %d areas · %d edges · depth %d" % (n, format(loc, ","), na, ne, depth))
    print("[codemap] wrote %s  (%d KB)" % (out, out.stat().st_size // 1024))
    if a.md:
        mp = out.with_suffix(".md"); mp.write_text(render_md(mods, edges), encoding="utf-8"); print("[codemap] wrote " + str(mp))
    if a.open:
        webbrowser.open(out.as_uri())

if __name__ == "__main__":
    main()
