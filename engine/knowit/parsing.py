from __future__ import annotations
import ast
import os
import re
from .models import ParsedFile, Symbol

JS_EXTS = {".js", ".jsx", ".mjs", ".cjs"}
TS_EXTS = {".ts", ".tsx"}


def _read(abs_path):
    try:
        with open(abs_path, "r", encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except Exception:
        return ""


# ---------------- Python (stdlib ast) ----------------
def _callee_name(func):
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def _collect_calls(fn_node):
    out, seen = [], set()
    for n in ast.walk(fn_node):
        if isinstance(n, ast.Call):
            nm = _callee_name(n.func)
            if nm and nm not in seen:
                seen.add(nm)
                out.append(nm)
    return out


def _segment(lines, node):
    start = getattr(node, "lineno", 1)
    end = getattr(node, "end_lineno", start)
    return "\n".join(lines[start - 1:end]), start, end


def _complexity(node):
    c = 1
    for n in ast.walk(node):
        if isinstance(n, (ast.If, ast.For, ast.AsyncFor, ast.While,
                          ast.ExceptHandler, ast.IfExp, ast.Assert)):
            c += 1
        elif isinstance(n, ast.BoolOp):
            c += len(n.values) - 1
        elif isinstance(n, ast.comprehension):
            c += 1 + len(n.ifs)
    return c


def _bases(node):
    out = []
    for b in getattr(node, "bases", []):
        if isinstance(b, ast.Name):
            out.append(b.id)
        elif isinstance(b, ast.Attribute):
            out.append(b.attr)
    return out


# Module-level defs can hide inside compound statements - the classic case is a
# try/except import fallback, or an `if TYPE_CHECKING:` / `if sys.platform` guard.
# The old code only iterated tree.body, so those defs were invisible to the graph,
# search, Files "Defines", and Ask (QA finding G-01). Walk into block bodies, but
# stop at any def/class boundary (a class handles its own methods; functions' inner
# defs are locals, intentionally not indexed as top-level symbols).
_BLOCK_STMTS = (ast.If, ast.Try, ast.With, ast.AsyncWith,
                ast.For, ast.AsyncFor, ast.While)


def _block_suites(node):
    suites = []
    for attr in ("body", "orelse", "finalbody"):
        v = getattr(node, attr, None)
        if isinstance(v, list):
            suites.append(v)
    if isinstance(node, ast.Try):
        for h in node.handlers:
            suites.append(h.body)
    return suites


def _module_defs(body):
    """Yield top-level function/class defs, descending through compound statements
    but not into other defs/classes."""
    for node in body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            yield node
        elif isinstance(node, _BLOCK_STMTS):
            for suite in _block_suites(node):
                yield from _module_defs(suite)


def parse_python(rel_path, source):
    pf = ParsedFile(file=rel_path, language="python", text=source,
                    loc=source.count("\n") + 1)
    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        pf.error = f"SyntaxError: {e}"
        return pf
    lines = source.splitlines()

    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            for a in n.names:
                pf.imports.append(a.name)
        elif isinstance(n, ast.ImportFrom):
            if n.module:
                pf.imports.append(n.module)
    pf.imports = sorted(set(pf.imports))

    def add_symbol(node, qualprefix, parent):
        qual = f"{qualprefix}{node.name}"
        if isinstance(node, ast.ClassDef):
            kind = "class"
        elif parent:
            kind = "method"
        else:
            kind = "function"
        code, s, e = _segment(lines, node)
        pf.symbols.append(Symbol(
            id=f"{rel_path}::{qual}", name=node.name, qualname=qual, kind=kind,
            file=rel_path, start_line=s, end_line=e,
            docstring=(ast.get_docstring(node) or ""), code=code,
            calls=[] if isinstance(node, ast.ClassDef) else _collect_calls(node),
            parent=parent,
            complexity=0 if isinstance(node, ast.ClassDef) else _complexity(node),
            bases=_bases(node) if isinstance(node, ast.ClassDef) else [],
        ))
        if isinstance(node, ast.ClassDef):
            for b in node.body:
                if isinstance(b, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    add_symbol(b, qual + ".", parent=qual)

    for node in _module_defs(tree.body):
        add_symbol(node, "", parent=None)
    for cls in [x for x in pf.symbols if x.kind == "class"]:
        cls.complexity = sum(m.complexity for m in pf.symbols
                             if m.parent == cls.qualname) or 1
    return pf


# ---------------- JavaScript / TypeScript (best-effort regex) ----------------
_JS_IMPORT = re.compile(r"""import\s+(?:[^'"]+\s+from\s+)?['"]([^'"]+)['"]""")
_JS_REQUIRE = re.compile(r"""require\(\s*['"]([^'"]+)['"]\s*\)""")
_JS_CLASS = re.compile(r"\bclass\s+([A-Za-z_$][\w$]*)(?:\s+extends\s+([A-Za-z_$][\w$.]*))?")
_JS_FUNC = re.compile(r"\bfunction\s+([A-Za-z_$][\w$]*)\s*\(")
_JS_ARROW = re.compile(r"\b(?:export\s+)?(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?\([^)]*\)\s*=>")


def parse_js(rel_path, source, language):
    lines = source.splitlines()
    pf = ParsedFile(file=rel_path, language=language, text=source, loc=len(lines) + 1)

    imps = set()
    for m in _JS_IMPORT.finditer(source):
        imps.add(m.group(1))
    for m in _JS_REQUIRE.finditer(source):
        imps.add(m.group(1))
    pf.imports = sorted(imps)

    seen = set()

    def add(name, kind, pos, bases=None):
        if (name, kind) in seen:
            return
        seen.add((name, kind))
        start = source.count("\n", 0, pos) + 1
        end = min(start + 12, len(lines))
        code = "\n".join(lines[start - 1:end])
        pf.symbols.append(Symbol(
            id=f"{rel_path}::{name}", name=name, qualname=name, kind=kind,
            file=rel_path, start_line=start, end_line=end, docstring="", code=code,
            calls=[], parent=None, complexity=1, bases=bases or []))

    for m in _JS_CLASS.finditer(source):
        add(m.group(1), "class", m.start(), [m.group(2)] if m.group(2) else [])
    for m in _JS_FUNC.finditer(source):
        add(m.group(1), "function", m.start())
    for m in _JS_ARROW.finditer(source):
        add(m.group(1), "function", m.start())
    return pf


# ---------------- dispatch ----------------
def parse_file(rel_path, abs_path):
    ext = os.path.splitext(rel_path)[1].lower()
    src = _read(abs_path)
    if ext == ".py":
        return parse_python(rel_path, src)
    if ext in JS_EXTS:
        return parse_js(rel_path, src, "javascript")
    if ext in TS_EXTS:
        return parse_js(rel_path, src, "typescript")
    if ext in (".yaml", ".yml", ".toml", ".ini", ".cfg"):
        return ParsedFile(file=rel_path, language="config", text=src, loc=src.count("\n") + 1)
    lang = "markdown" if ext == ".md" else "other"
    return ParsedFile(file=rel_path, language=lang, text=src, loc=src.count("\n") + 1)
