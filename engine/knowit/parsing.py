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


# ---------------- JavaScript / TypeScript (hand-written, brace-matched) ----------------
# A real extractor (not the old 12-line-stub regex): masks comments/strings so nothing is
# matched inside them, brace-matches bodies for true line ranges, finds class methods and
# typed/generic arrow components, and computes complexity, imports and calls so the graph,
# dead-code and RAG work for JS/TS (QA #9/#15/#16).

_JS_KEYWORDS = {"if", "for", "while", "switch", "catch", "return", "function", "class",
                "new", "typeof", "await", "yield", "case", "do", "else", "try", "throw",
                "const", "let", "var", "in", "of", "instanceof", "void", "delete", "super"}

_JS_IMPORT_FROM = re.compile(r"""\bimport\b[^;'"]*?from\s*['"]([^'"]+)['"]""")
_JS_IMPORT_BARE = re.compile(r"""\bimport\s*['"]([^'"]+)['"]""")
_JS_REQUIRE = re.compile(r"""\brequire\(\s*['"]([^'"]+)['"]\s*\)""")
_JS_IMPORT_NAMES = re.compile(r"""\bimport\s+(?:type\s+)?(.+?)\s+from\s*['"]""", re.S)

_JS_CLASS = re.compile(r"\b(?:export\s+)?(?:default\s+)?(?:abstract\s+)?class\s+([A-Za-z_$][\w$]*)"
                       r"(?:\s+extends\s+([A-Za-z_$][\w$.]*))?")
_JS_FUNC = re.compile(r"\b(?:export\s+)?(?:default\s+)?(?:async\s+)?function\s*\*?\s*([A-Za-z_$][\w$]*)")
# arrow const with optional type annotation, optional generic params, optional return type
_JS_ARROW = re.compile(
    r"\b(?:export\s+)?(?:default\s+)?(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*"
    r"(?::\s*[^=;]+?)?=\s*(?:async\s*)?(?:<[^>]*>\s*)?\([^)]*\)\s*(?::\s*[^={;]+?)?=>")
# a method inside a class body
_JS_METHOD = re.compile(
    r"(?:^|\n)\s*(?:public\s+|private\s+|protected\s+|readonly\s+|static\s+|async\s+|get\s+|set\s+)*"
    r"([A-Za-z_$][\w$]*)\s*(?:<[^>]*>)?\s*\([^)]*\)\s*(?::\s*[^={;]+?)?\{")


def _js_mask(source):
    """Replace string/comment CONTENT with spaces (newlines preserved) so declaration
    scanning never fires inside a comment or string literal, while byte offsets and line
    numbers stay exact."""
    out = list(source)
    i, n = 0, len(source)
    st = None  # None | "//" | "/*" | "'" | '"' | '`'
    while i < n:
        c = source[i]; nxt = source[i + 1] if i + 1 < n else ""
        if st is None:
            if c == "/" and nxt == "/":
                st = "//"; i += 2; continue
            if c == "/" and nxt == "*":
                st = "/*"; out[i] = out[i + 1] = " "; i += 2; continue
            if c in "'\"`":
                st = c; i += 1; continue
            i += 1; continue
        if st == "//":
            if c == "\n": st = None
            else: out[i] = " "
            i += 1; continue
        if st == "/*":
            if c == "*" and nxt == "/": out[i] = out[i + 1] = " "; st = None; i += 2; continue
            if c != "\n": out[i] = " "
            i += 1; continue
        # inside a string/template
        if c == "\\" and st in "'\"`":
            out[i] = " ";
            if i + 1 < n and source[i + 1] != "\n": out[i + 1] = " "
            i += 2; continue
        if c == st:
            st = None; i += 1; continue
        if c != "\n": out[i] = " "
        i += 1
    return "".join(out)


def _brace_span(masked, open_brace):
    """Index just past the '}' matching the '{' at open_brace (masked text)."""
    depth = 0
    for i in range(open_brace, len(masked)):
        ch = masked[i]
        if ch == "{": depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0: return i + 1
    return len(masked)


def _line_of(source, pos):
    return source.count("\n", 0, pos) + 1


def _js_complexity(masked_body):
    c = 1
    for kw in ("if", "for", "while", "case", "catch"):
        c += len(re.findall(r"\b" + kw + r"\b", masked_body))
    c += masked_body.count("&&") + masked_body.count("||") + masked_body.count("??")
    c += len(re.findall(r"(?<![?])\?(?![.?])", masked_body))   # ternary ?
    return max(1, c)


def _js_call_sites(masked_body, import_names, self_names=("this",)):
    sites, seen = [], set()
    for m in re.finditer(r"([A-Za-z_$][\w$.]*)\s*\(", masked_body):
        expr = m.group(1)
        parts = expr.split(".")
        name = parts[-1]
        if name in _JS_KEYWORDS or not name:
            continue
        if len(parts) == 1:
            cs = ("bare", name)
        else:
            root = parts[0]
            if root in self_names:
                cs = ("self", name)
            elif root in import_names:
                continue
            else:
                cs = ("attr", name)
        if cs not in seen:
            seen.add(cs); sites.append(cs)
    return sites


def parse_js(rel_path, source, language):
    lines = source.splitlines()
    pf = ParsedFile(file=rel_path, language=language, text=source, loc=len(lines) + 1)

    # P2-4: skip minified / generated blobs - deep parsing them is quadratic and useless
    longest = max((len(l) for l in lines), default=0)
    if len(source) > 2_000_000 or longest > 50_000:
        pf.error = "skipped: minified or oversized file"
        return pf

    masked = _js_mask(source)

    imps = set()
    for rx in (_JS_IMPORT_FROM, _JS_IMPORT_BARE, _JS_REQUIRE):
        for m in rx.finditer(masked):
            # match position is comment-free (masked), but the path is a string literal
            # (masked to spaces) - read it from the ORIGINAL source at the captured span
            imps.add(source[m.start(1):m.end(1)])
    pf.imports = sorted(i for i in imps if i.strip())

    # local names bound by imports (for receiver classification: axios.get() is external)
    import_names = set()
    for m in _JS_IMPORT_NAMES.finditer(masked):
        clause = m.group(1)
        mstar = re.search(r"\*\s+as\s+([A-Za-z_$][\w$]*)", clause)
        if mstar:
            import_names.add(mstar.group(1))
        mdef = re.match(r"\s*([A-Za-z_$][\w$]*)", clause)
        if mdef and mdef.group(1) not in ("type",):
            import_names.add(mdef.group(1))
        for nm in re.findall(r"[A-Za-z_$][\w$]*", clause.split("{")[-1].split("}")[0] if "{" in clause else ""):
            import_names.add(nm)
    for m in re.finditer(r"\b(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*require\(", masked):
        import_names.add(m.group(1))

    symbols = []
    class_spans = []

    # classes + their methods
    for m in _JS_CLASS.finditer(masked):
        cname = m.group(1); bases = [m.group(2)] if m.group(2) else []
        brace = masked.find("{", m.end())
        if brace == -1:
            continue
        body_end = _brace_span(masked, brace)
        class_spans.append((m.start(), body_end))
        s0, s1 = _line_of(source, m.start()), _line_of(source, body_end)
        body_masked = masked[brace:body_end]
        symbols.append(Symbol(
            id=f"{rel_path}::{cname}", name=cname, qualname=cname, kind="class",
            file=rel_path, start_line=s0, end_line=s1, docstring="",
            code="\n".join(lines[s0 - 1:s1]), calls=[], call_sites=[], parent=cname,
            complexity=0, bases=bases))
        # methods within the class body
        inner = masked[brace + 1:body_end - 1]
        for mm in _JS_METHOD.finditer(inner):
            mname = mm.group(1)
            if mname in _JS_KEYWORDS:
                continue
            mpos = brace + 1 + mm.start(1)
            mbrace = brace + 1 + mm.end() - 1     # the '{' captured at end of _JS_METHOD
            mend = _brace_span(masked, mbrace)
            ms0, ms1 = _line_of(source, mpos), _line_of(source, mend)
            mbody = masked[mbrace:mend]
            sites = _js_call_sites(mbody, import_names)
            symbols.append(Symbol(
                id=f"{rel_path}::{cname}.{mname}", name=mname, qualname=f"{cname}.{mname}",
                kind="method", file=rel_path, start_line=ms0, end_line=ms1, docstring="",
                code="\n".join(lines[ms0 - 1:ms1]), calls=[n for _, n in sites],
                call_sites=sites, parent=cname, complexity=_js_complexity(mbody), bases=[]))

    def _in_class(pos):
        return any(a <= pos < b for a, b in class_spans)

    # top-level function declarations
    for m in _JS_FUNC.finditer(masked):
        if _in_class(m.start()):
            continue
        name = m.group(1)
        brace = masked.find("{", m.end())
        if brace == -1 or brace - m.end() > 400:
            continue
        bend = _brace_span(masked, brace)
        s0, s1 = _line_of(source, m.start()), _line_of(source, bend)
        body = masked[brace:bend]
        sites = _js_call_sites(body, import_names)
        symbols.append(Symbol(
            id=f"{rel_path}::{name}", name=name, qualname=name, kind="function",
            file=rel_path, start_line=s0, end_line=s1, docstring="",
            code="\n".join(lines[s0 - 1:s1]), calls=[n for _, n in sites],
            call_sites=sites, parent=None, complexity=_js_complexity(body), bases=[]))

    # top-level arrow-function consts (incl. typed React.FC and generics)
    for m in _JS_ARROW.finditer(masked):
        if _in_class(m.start()):
            continue
        name = m.group(1)
        arrow = masked.find("=>", m.start())
        after = masked.find("{", arrow) if arrow != -1 else -1
        if after != -1 and masked[arrow + 2:after].strip() == "":
            bend = _brace_span(masked, after)       # block body
        else:
            semi = masked.find(";", arrow); nl = masked.find("\n", arrow)
            cand = [x for x in (semi, nl) if x != -1]
            bend = min(cand) if cand else len(masked)   # expression body
        s0, s1 = _line_of(source, m.start()), _line_of(source, bend)
        body = masked[m.start():bend]
        sites = _js_call_sites(body, import_names)
        symbols.append(Symbol(
            id=f"{rel_path}::{name}", name=name, qualname=name, kind="function",
            file=rel_path, start_line=s0, end_line=s1, docstring="",
            code="\n".join(lines[s0 - 1:s1]), calls=[n for _, n in sites],
            call_sites=sites, parent=None, complexity=_js_complexity(body), bases=[]))

    # de-dup by id (keep first)
    byid = {}
    for s in symbols:
        byid.setdefault(s.id, s)
    pf.symbols = list(byid.values())
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
