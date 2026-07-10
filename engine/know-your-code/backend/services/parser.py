"""Multi-language symbol + import extraction. Prefers tree-sitter (Python/JS/TS/Go/Java) when
its grammars are installed (the Orchestraty host ships them), and falls back to the stdlib
`ast` for Python or a lightweight regex pass otherwise. Pure-Python; no host imports."""
from __future__ import annotations
import ast as _ast
import re

_CONTAINER = {"python": {"class_definition"}, "javascript": {"class_declaration"},
              "typescript": {"class_declaration"},
              "java": {"class_declaration", "interface_declaration", "enum_declaration"},
              "go": {"type_declaration"}}
_CALLABLE = {"python": {"function_definition"},
             "javascript": {"function_declaration", "method_definition"},
             "typescript": {"function_declaration", "method_definition"},
             "java": {"method_declaration", "constructor_declaration"},
             "go": {"function_declaration", "method_declaration"}}


# ---------------- tree-sitter (preferred when grammars are present) ----------------
def _get_ts_parser(language):
    try:
        from tree_sitter_languages import get_parser
        return get_parser(language)
    except Exception:
        pass
    try:
        import importlib
        from tree_sitter import Language, Parser
        mod = importlib.import_module("tree_sitter_" + language)
        lang = Language(mod.language())
        try:
            return Parser(lang)
        except Exception:
            p = Parser()
            p.language = lang
            return p
    except Exception:
        return None


def _ts_symbols(language, source):
    parser = _get_ts_parser(language)
    if parser is None:
        return None
    srcb = source.encode("utf-8", "replace")
    tree = parser.parse(srcb)
    containers, callables = _CONTAINER.get(language, set()), _CALLABLE.get(language, set())

    def text(node):
        return srcb[node.start_byte:node.end_byte].decode("utf-8", "replace")

    def name_of(node):
        nm = node.child_by_field_name("name")
        if nm is not None:
            return text(nm)
        for c in node.children:
            if "identifier" in c.type:
                return text(c)
        return ""

    out = []

    def walk(node, in_class):
        is_c, is_f = node.type in containers, node.type in callables
        if is_c or is_f:
            sig = (text(node).splitlines() or [""])[0].strip()[:200]
            out.append({"kind": "class" if is_c else ("method" if in_class else "function"),
                        "name": name_of(node), "signature": sig,
                        "line_start": node.start_point[0] + 1,
                        "line_end": node.end_point[0] + 1, "docstring": ""})
        nin = in_class or is_c
        for c in node.children:
            walk(c, nin)

    walk(tree.root_node, False)
    return [s for s in out if s["name"]]


# ---------------- Python stdlib ast (tested fallback) ----------------
def _py_symbols(source):
    try:
        tree = _ast.parse(source)
    except SyntaxError:
        return []
    lines = source.splitlines()
    out = []

    def emit(node, parent):
        kind = "class" if isinstance(node, _ast.ClassDef) else ("method" if parent else "function")
        s = getattr(node, "lineno", 1)
        e = getattr(node, "end_lineno", s)
        sig = lines[s - 1].strip()[:200] if s - 1 < len(lines) else node.name
        out.append({"kind": kind, "name": node.name, "signature": sig,
                    "line_start": s, "line_end": e,
                    "docstring": (_ast.get_docstring(node) or "")[:500]})
        if isinstance(node, _ast.ClassDef):
            for b in node.body:
                if isinstance(b, (_ast.FunctionDef, _ast.AsyncFunctionDef)):
                    emit(b, node.name)

    for n in tree.body:
        if isinstance(n, (_ast.FunctionDef, _ast.AsyncFunctionDef, _ast.ClassDef)):
            emit(n, None)
    return out


# ---------------- regex fallback (js/ts/go/java when no tree-sitter) ----------------
_RX = {
    "javascript": [("class", re.compile(r"\bclass\s+([A-Za-z_$][\w$]*)")),
                   ("function", re.compile(r"\bfunction\s+([A-Za-z_$][\w$]*)")),
                   ("function", re.compile(r"\b(?:export\s+)?(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?\([^)]*\)\s*=>"))],
    "go": [("class", re.compile(r"\btype\s+([A-Za-z_]\w*)\s+(?:struct|interface)\b")),
           ("function", re.compile(r"\bfunc\s+(?:\([^)]*\)\s*)?([A-Za-z_]\w*)\s*\("))],
    "java": [("class", re.compile(r"\b(?:class|interface|enum)\s+([A-Za-z_]\w*)")),
             ("method", re.compile(r"(?:public|private|protected|static|\s)+[\w<>\[\]]+\s+([A-Za-z_]\w*)\s*\([^)]*\)\s*\{"))],
}
_RX["typescript"] = _RX["javascript"]


def _regex_symbols(language, source):
    rules = _RX.get(language)
    if not rules:
        return []
    out, seen = [], set()
    for kind, pat in rules:
        for m in pat.finditer(source):
            nm = m.group(1)
            if (nm, kind) in seen:
                continue
            seen.add((nm, kind))
            line = source.count("\n", 0, m.start()) + 1
            out.append({"kind": kind, "name": nm,
                        "signature": source.splitlines()[line - 1].strip()[:200] if line - 1 < len(source.splitlines()) else nm,
                        "line_start": line, "line_end": line, "docstring": ""})
    return out


def parse_symbols(source, language):
    if language not in ("python", "javascript", "typescript", "go", "java"):
        return []
    ts = _ts_symbols(language, source)
    if ts is not None:
        return ts
    return _py_symbols(source) if language == "python" else _regex_symbols(language, source)


# ---------------- imports ----------------
_IMP = {
    "javascript": [re.compile(r"""import\s+(?:[^'"]+\s+from\s+)?['"]([^'"]+)['"]"""),
                   re.compile(r"""require\(\s*['"]([^'"]+)['"]\s*\)""")],
    "go": [re.compile(r'"([^"]+)"')],
    "java": [re.compile(r"\bimport\s+(?:static\s+)?([\w.]+)\s*;")],
}
_IMP["typescript"] = _IMP["javascript"]


def parse_imports(source, language):
    if language == "python":
        out = []
        try:
            for n in _ast.walk(_ast.parse(source)):
                if isinstance(n, _ast.Import):
                    out += [a.name for a in n.names]
                elif isinstance(n, _ast.ImportFrom) and n.module:
                    out.append(n.module)
        except SyntaxError:
            return []
        return sorted(set(out))
    pats = _IMP.get(language, [])
    out = set()
    for p in pats:
        for m in p.finditer(source):
            out.add(m.group(1))
    return sorted(out)


def parse_file(rel_path, source, language):
    return {"path": rel_path, "language": language,
            "symbols": parse_symbols(source, language),
            "imports": parse_imports(source, language)}
