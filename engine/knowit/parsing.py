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


def _deco_name(d):
    """Last component of a decorator expression: @app.get(...) -> 'get', @property -> 'property'."""
    if isinstance(d, ast.Call):
        d = d.func
    if isinstance(d, ast.Attribute):
        return d.attr
    if isinstance(d, ast.Name):
        return d.id
    return ""


def _module_all(tree):
    """Names listed in a module-level __all__ = [...] / (...)."""
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == "__all__" for t in node.targets):
            if isinstance(node.value, (ast.List, ast.Tuple)):
                return [e.value for e in node.value.elts
                        if isinstance(e, ast.Constant) and isinstance(e.value, str)]
    return []


def _has_main_guard(tree):
    """True iff the module has a real `if __name__ == '__main__':` at top level - not just
    the string '__main__' somewhere in a comment or docstring."""
    for node in tree.body:
        if isinstance(node, ast.If) and isinstance(node.test, ast.Compare):
            t = node.test
            names = [t.left] + list(t.comparators)
            if any(isinstance(n, ast.Name) and n.id == "__name__" for n in names) and \
               any(isinstance(n, ast.Constant) and n.value == "__main__" for n in names):
                return True
    return False


def _collect_calls(fn_node):
    out, seen = [], set()
    for n in ast.walk(fn_node):
        if isinstance(n, ast.Call):
            nm = _callee_name(n.func)
            if nm and nm not in seen:
                seen.add(nm)
                out.append(nm)
    return out


def _receiver_root(node):
    """Leftmost Name of a receiver chain: os.path.join -> 'os', a.b.c() -> 'a'."""
    while isinstance(node, ast.Attribute):
        node = node.value
    if isinstance(node, ast.Call):
        return _receiver_root(node.func)
    return node.id if isinstance(node, ast.Name) else None


def _call_site(func, import_names):
    """Classify a call's receiver so the graph doesn't fabricate edges from bare attribute
    names (QA #12). Returns (kind, name) or None:
      bare  foo()             -> ("bare", "foo")   resolvable by import/same-file/unique
      self  self.m()/cls.m()  -> ("self", "m")     resolved within the class hierarchy
      attr  obj.m()           -> ("attr", "m")     resolved by the normal ladder
      import-rooted receiver (log.info(), os.path.join(), np.array()) -> None (external)."""
    if isinstance(func, ast.Name):
        return ("bare", func.id)
    if isinstance(func, ast.Attribute):
        recv = func.value
        if isinstance(recv, ast.Name) and recv.id in ("self", "cls"):
            return ("self", func.attr)
        root = _receiver_root(recv)
        if root is not None and root in import_names:
            return None                     # module/imported receiver -> not a repo edge
        return ("attr", func.attr)
    return None


def _calls_and_complexity(node, import_names=frozenset()):
    """Bare-name calls (compat) + receiver-classified call sites + cyclomatic complexity in
    ONE ast.walk of the subtree."""
    calls, sites, seen, seen_sites = [], [], set(), set()
    c = 1
    for n in ast.walk(node):
        if isinstance(n, ast.Call):
            nm = _callee_name(n.func)
            if nm and nm not in seen:
                seen.add(nm)
                calls.append(nm)
            cs = _call_site(n.func, import_names)
            if cs and cs not in seen_sites:
                seen_sites.add(cs)
                sites.append(cs)
        elif isinstance(n, (ast.If, ast.For, ast.AsyncFor, ast.While,
                            ast.ExceptHandler, ast.IfExp, ast.Assert)):
            c += 1
        elif isinstance(n, ast.BoolOp):
            c += len(n.values) - 1
        elif isinstance(n, ast.comprehension):
            c += 1 + len(n.ifs)
    return calls, sites, c


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

    # Resolve imports to absolute dotted module paths so the graph can match them to repo
    # files by FULL path (QA #10/#18). Relative imports (from . import x) were dropped
    # entirely, from-pkg-import-module produced no submodule candidate, and a bare-basename
    # fallback made `import logging` collide with a repo logging.py.
    pkg = rel_path[:-3].replace(os.sep, "/").split("/")[:-1] if rel_path.endswith(".py") else []
    cands = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            for a in n.names:
                cands.add(a.name)                       # absolute: import a.b.c -> "a.b.c"
        elif isinstance(n, ast.ImportFrom):
            level = getattr(n, "level", 0) or 0
            if level:                                    # relative: resolve against this pkg
                base = pkg[: len(pkg) - (level - 1)] if len(pkg) >= (level - 1) else []
            else:
                base = []
            mod_parts = base + (n.module.split(".") if n.module else [])
            if mod_parts:
                cands.add(".".join(mod_parts))          # the module/package itself
            for a in n.names:                            # each imported name may be a submodule
                if a.name != "*":
                    cands.add(".".join(mod_parts + [a.name]))
    pf.imports = sorted(c for c in cands if c)

    import_names = set()
    for _n in ast.walk(tree):
        if isinstance(_n, ast.Import):
            for a in _n.names:
                import_names.add((a.asname or a.name).split(".")[0])
        elif isinstance(_n, ast.ImportFrom):
            for a in _n.names:
                import_names.add(a.asname or a.name)

    def add_symbol(node, qualprefix, parent):
        qual = f"{qualprefix}{node.name}"
        if isinstance(node, ast.ClassDef):
            kind = "class"
        elif parent:
            kind = "method"
        else:
            kind = "function"
        code, s, e = _segment(lines, node)
        if isinstance(node, ast.ClassDef):
            calls, sites, cx = [], [], 0
        else:
            calls, sites, cx = _calls_and_complexity(node, import_names)
        pf.symbols.append(Symbol(
            id=f"{rel_path}::{qual}", name=node.name, qualname=qual, kind=kind,
            file=rel_path, start_line=s, end_line=e,
            docstring=(ast.get_docstring(node) or ""), code=code,
            calls=calls, parent=parent, complexity=cx,
            bases=_bases(node) if isinstance(node, ast.ClassDef) else [],
            decorators=[_deco_name(d) for d in getattr(node, "decorator_list", [])],
            call_sites=sites,
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
    pf.exports = _module_all(tree)
    pf.has_main = _has_main_guard(tree)
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
