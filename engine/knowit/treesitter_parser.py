"""Optional tree-sitter parsing backend for languages beyond Python and JS/TS.

This is OFF unless `tree-sitter` and a grammar pack are installed. It never replaces the
stdlib-`ast` Python parser (the most reliable one) and only serves as a fallback-capable
backend for other languages. Every extraction is wrapped so a grammar quirk degrades to
`None` (caller falls back) rather than crashing indexing.

Install (see engine/scripts/verify_treesitter.py to confirm it works):
    pip install tree-sitter tree-sitter-language-pack
"""
from __future__ import annotations

from .models import ParsedFile, Symbol

# ── grammar loader (tries the current pack, then the legacy one) ─────────────
_PARSERS: dict = {}
_LOADER = None            # callable(name) -> parser, or None if nothing is installed
_PROBED = False


def _find_loader():
    global _LOADER, _PROBED
    if _PROBED:
        return _LOADER
    _PROBED = True
    try:
        from tree_sitter_language_pack import get_parser as _gp   # modern (165+ grammars)
        _LOADER = _gp
        return _LOADER
    except Exception:
        pass
    try:
        from tree_sitter_languages import get_parser as _gp       # legacy
        _LOADER = _gp
        return _LOADER
    except Exception:
        _LOADER = None
    return _LOADER


def available() -> bool:
    return _find_loader() is not None


# language -> candidate grammar names (pack naming varies by version)
_GRAMMAR = {
    "javascript": ["javascript"], "typescript": ["typescript"], "tsx": ["tsx", "typescript"],
    "go": ["go"], "java": ["java"], "rust": ["rust"],
    "c_sharp": ["csharp", "c_sharp", "c-sharp"], "ruby": ["ruby"], "php": ["php"],
    "c": ["c"], "cpp": ["cpp", "c++"], "kotlin": ["kotlin"], "swift": ["swift"], "scala": ["scala"],
}


def _parser_for(lang):
    if lang in _PARSERS:
        return _PARSERS[lang]
    loader = _find_loader()
    p = None
    if loader:
        for name in _GRAMMAR.get(lang, [lang]):
            try:
                p = loader(name); break
            except Exception:
                continue
    _PARSERS[lang] = p
    return p


# ── node-type vocabulary (union across grammar versions, matched leniently) ──
_FUNC_TYPES = {
    "function_declaration", "function_definition", "function_item", "method_declaration",
    "method_definition", "constructor_declaration", "method", "singleton_method",
    "local_function_statement", "function", "arrow_function", "function_expression",
    "fn_item",
}
_CLASS_TYPES = {
    "class_declaration", "class_definition", "class_specifier", "class",
    "interface_declaration", "struct_item", "struct_specifier", "struct_declaration",
    "enum_declaration", "enum_item", "trait_item", "impl_item", "object_declaration",
    "type_declaration", "type_spec", "module", "namespace_declaration",
}
_CALL_TYPES = {"call_expression", "call", "method_invocation", "invocation_expression",
               "function_call_expression", "macro_invocation"}
_BRANCH_TYPES = {
    "if_statement", "if_expression", "for_statement", "for_expression", "for_in_statement",
    "while_statement", "while_expression", "do_statement", "case", "switch_section",
    "when_entry", "catch_clause", "rescue", "conditional_expression", "ternary_expression",
    "match_arm", "guard",
}
_NAME_NODE_TYPES = {"identifier", "type_identifier", "field_identifier", "property_identifier",
                    "name", "constant", "simple_identifier", "scoped_identifier"}


def _txt(src: bytes, node) -> str:
    try:
        return src[node.start_byte:node.end_byte].decode("utf-8", "replace")
    except Exception:
        return ""


_ID_TYPES = {"identifier", "type_identifier", "field_identifier", "property_identifier",
             "name", "constant", "simple_identifier", "scoped_identifier",
             "qualified_identifier", "destructor_name", "operator_name"}


def _name_of(src: bytes, node) -> str:
    # 1) the common case: a `name` field (Python-ish, Java, Rust, C#, Ruby, Go, ...)
    try:
        n = node.child_by_field_name("name")
        if n is not None:
            return _txt(src, n)
    except Exception:
        pass
    # 2) C / C++ / anything that hangs the name off a `declarator` chain:
    #    function_definition -> declarator(function_declarator) -> declarator(identifier)
    try:
        d = node.child_by_field_name("declarator")
    except Exception:
        d = None
    hops = 0
    while d is not None and hops < 8:
        if d.type in _ID_TYPES:
            return _txt(src, d)
        nxt = None
        try:
            nxt = d.child_by_field_name("declarator")
        except Exception:
            nxt = None
        if nxt is None:
            for ch in getattr(d, "named_children", []) or []:
                if ch.type in _ID_TYPES or ch.type.endswith("identifier"):
                    return _txt(src, ch)
            break
        d = nxt
        hops += 1
    # 3) last resort: first name-ish direct child
    for ch in getattr(node, "named_children", []) or []:
        if ch.type in _NAME_NODE_TYPES:
            return _txt(src, ch)
    return ""


def _complexity(node) -> int:
    c = 1
    stack = [node]
    while stack:
        n = stack.pop()
        for ch in n.children:
            if ch.type in _BRANCH_TYPES:
                c += 1
            stack.append(ch)
    return c


def _callee_name(src, call_node):
    try:
        fn = call_node.child_by_field_name("function") or call_node.child_by_field_name("name")
    except Exception:
        fn = None
    node = fn or (call_node.named_children[0] if call_node.named_children else None)
    if node is None:
        return None, None
    t = _txt(src, node)
    if not t:
        return None, None
    parts = t.replace("->", ".").replace("::", ".").split(".")
    name = parts[-1].split("(")[0].strip()
    if not name or not name.replace("_", "").isalnum():
        return None, None
    if len(parts) == 1:
        return "bare", name
    root = parts[0].strip()
    if root in ("self", "this", "cls", "Self"):
        return "self", name
    return "attr", name


def _collect_calls(src, node):
    sites, seen = [], set()
    stack = [node]
    while stack:
        n = stack.pop()
        for ch in n.children:
            if ch.type in _CALL_TYPES:
                kind, name = _callee_name(src, ch)
                if name and (kind, name) not in seen:
                    seen.add((kind, name)); sites.append((kind, name))
            # don't descend into nested named functions (their calls are theirs)
            if ch.type not in _FUNC_TYPES:
                stack.append(ch)
    return sites


def _walk(src, node, rel_path, parent_class, out, lines):
    for ch in node.children:
        t = ch.type
        is_class = t in _CLASS_TYPES
        is_func = t in _FUNC_TYPES and t not in ("arrow_function", "function_expression")
        if is_class:
            name = _name_of(src, ch)
            if name:
                s0, s1 = ch.start_point[0] + 1, ch.end_point[0] + 1
                out.append(Symbol(
                    id=f"{rel_path}::{name}", name=name, qualname=name, kind="class",
                    file=rel_path, start_line=s0, end_line=s1, docstring="",
                    code="\n".join(lines[s0 - 1:s1]), calls=[], call_sites=[],
                    parent=name, complexity=0, bases=[]))
                _walk(src, ch, rel_path, name, out, lines)
            else:
                _walk(src, ch, rel_path, parent_class, out, lines)
        elif is_func:
            name = _name_of(src, ch)
            if name:
                s0, s1 = ch.start_point[0] + 1, ch.end_point[0] + 1
                qual = f"{parent_class}.{name}" if parent_class else name
                sites = _collect_calls(src, ch)
                out.append(Symbol(
                    id=f"{rel_path}::{qual}", name=name, qualname=qual,
                    kind="method" if parent_class else "function",
                    file=rel_path, start_line=s0, end_line=s1, docstring="",
                    code="\n".join(lines[s0 - 1:s1]), calls=[n for _, n in sites],
                    call_sites=sites, parent=parent_class, complexity=_complexity(ch), bases=[]))
            # still descend (nested defs / local functions)
            _walk(src, ch, rel_path, parent_class, out, lines)
        else:
            _walk(src, ch, rel_path, parent_class, out, lines)


def ts_parse(rel_path, source, lang):
    """Parse `source` for `lang` via tree-sitter. Returns a ParsedFile, or None to signal
    the caller to fall back (grammar missing, parse error, or nothing extracted)."""
    parser = _parser_for(lang)
    if parser is None:
        return None
    try:
        src_bytes = source.encode("utf-8", "replace")
        # guard against minified / giant blobs (same policy as the JS parser)
        lines = source.splitlines()
        if len(source) > 2_000_000 or max((len(l) for l in lines), default=0) > 50_000:
            return ParsedFile(file=rel_path, language=lang, text=source,
                              loc=len(lines) + 1, error="skipped: minified or oversized file")
        tree = parser.parse(src_bytes)
        pf = ParsedFile(file=rel_path, language=lang, text=source, loc=len(lines) + 1)
        symbols = []
        _walk(src_bytes, tree.root_node, rel_path, None, symbols, lines)
        byid = {}
        for s in symbols:
            byid.setdefault(s.id, s)
        pf.symbols = list(byid.values())
        return pf
    except Exception:
        return None
