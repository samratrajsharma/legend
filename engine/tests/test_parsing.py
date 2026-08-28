"""Tests for legend.parsing — Python (ast) and JS/TS (regex) extraction."""
from __future__ import annotations

import os

from legend.parsing import parse_file, parse_js, parse_python


def _sym(pf, qualname):
    return next((s for s in pf.symbols if s.qualname == qualname), None)


# --------------------------------------------------------------------------- #
# Python
# --------------------------------------------------------------------------- #
def test_parse_python_symbols_and_kinds(sample_repo_path):
    pf = parse_file("model.py", os.path.join(sample_repo_path, "model.py"))
    assert pf.language == "python"
    assert pf.error == ""

    det = _sym(pf, "Detector")
    assert det is not None and det.kind == "class"

    init = _sym(pf, "Detector.__init__")
    assert init is not None
    assert init.kind == "method"
    assert init.parent == "Detector"

    # top-level function in losses, not a method
    lf = parse_file("losses.py", os.path.join(sample_repo_path, "losses.py"))
    assert _sym(lf, "focal_loss").kind == "function"
    assert _sym(lf, "focal_loss").parent is None


def test_parse_python_imports_sorted_unique(sample_repo_path):
    pf = parse_file("model.py", os.path.join(sample_repo_path, "model.py"))
    assert pf.imports == ["losses", "os"]  # sorted + de-duped


def test_parse_python_docstring_and_calls(sample_repo_path):
    pf = parse_file("model.py", os.path.join(sample_repo_path, "model.py"))
    loss = _sym(pf, "Detector.loss")
    assert "focal loss" in loss.docstring.lower()
    # call collection walks the whole function body
    assert "focal_loss" in loss.calls


def test_parse_python_complexity(sample_repo_path):
    pf = parse_file("model.py", os.path.join(sample_repo_path, "model.py"))
    # load_weights has a single `if` -> cyclomatic ~2
    assert _sym(pf, "Detector.load_weights").complexity >= 2
    # _decode is straight-line -> complexity 1
    assert _sym(pf, "Detector._decode").complexity == 1


def test_complexity_counts_branches_and_boolops():
    src = (
        "def f(x, y):\n"
        "    if x and y:\n"
        "        return 1\n"
        "    for i in range(3):\n"
        "        pass\n"
        "    return [i for i in range(2) if i]\n"
    )
    pf = parse_python("t.py", src)
    f = _sym(pf, "f")
    # base 1 + if(1) + and(1) + for(1) + comprehension(1) + comp-if(1) = 6
    assert f.complexity == 6


def test_class_complexity_is_sum_of_methods():
    src = (
        "class C:\n"
        "    def a(self):\n"
        "        if 1:\n"
        "            return 1\n"
        "    def b(self):\n"
        "        return 2\n"
    )
    pf = parse_python("t.py", src)
    c = _sym(pf, "C")
    # a -> 2, b -> 1, class complexity = sum = 3
    assert c.complexity == 3


def test_class_bases_captured():
    src = "import x\nclass Child(Base, x.Mixin):\n    pass\n"
    pf = parse_python("t.py", src)
    child = _sym(pf, "Child")
    assert child.bases == ["Base", "Mixin"]


def test_decorator_expression_not_counted_as_a_call(sample_repo_path):
    # `@app.get("/items")` is NOT a call the handler makes. Walking the decorator injected a
    # bogus `get` call/call-site and inflated complexity, which then manufactured phantom
    # call edges to any repo symbol named `get` (QA audit). Extraction is body-only now.
    pf = parse_python(
        "h.py",
        'import flask\napp = flask.Flask(__name__)\n\n'
        '@app.get("/items")\n'
        'def handler():\n    return "ok"\n',
    )
    h = _sym(pf, "handler")
    assert "get" not in h.calls
    assert all(name != "get" for _kind, name in h.call_sites)
    assert h.complexity == 1                      # not inflated by the decorator


def test_parse_python_syntax_error_is_captured():
    pf = parse_python("bad.py", "def broken(:\n    pass\n")
    assert pf.error.startswith("SyntaxError")
    assert pf.symbols == []
    assert pf.language == "python"


def test_nested_function_is_not_a_top_level_symbol(sample_repo_path):
    # api.create_app defines a nested `detect`; only create_app is a symbol.
    pf = parse_file("api.py", os.path.join(sample_repo_path, "api.py"))
    names = {s.qualname for s in pf.symbols}
    assert "create_app" in names
    assert "detect" not in names
    # but the nested call to run_inference is still collected on create_app
    assert "run_inference" in _sym(pf, "create_app").calls


# --------------------------------------------------------------------------- #
# JavaScript / TypeScript (regex, best-effort)
# --------------------------------------------------------------------------- #
JS_SRC = (
    'import { foo } from "./foo";\n'
    "const dep = require('./bar');\n"
    "export class Animal extends Base {\n"
    "  speak() { return 1; }\n"
    "}\n"
    "function compute(x) { return x; }\n"
    "export const arrow = (a, b) => a + b;\n"
)


def test_parse_js_symbols():
    pf = parse_js("m.js", JS_SRC, "javascript")
    assert pf.language == "javascript"
    names = {s.name: s.kind for s in pf.symbols}
    assert names.get("Animal") == "class"
    assert names.get("compute") == "function"
    assert names.get("arrow") == "function"
    # class methods ARE now captured (brace-matched parser, audit #16)
    assert names.get("speak") == "method"


def test_parse_js_imports_include_require():
    pf = parse_js("m.js", JS_SRC, "javascript")
    assert pf.imports == ["./bar", "./foo"]


def test_parse_js_extends_base():
    pf = parse_js("m.js", JS_SRC, "javascript")
    animal = next(s for s in pf.symbols if s.name == "Animal")
    assert animal.bases == ["Base"]


# --------------------------------------------------------------------------- #
# Dispatch by extension
# --------------------------------------------------------------------------- #
def test_dispatch_markdown_and_other(tmp_path):
    md = tmp_path / "doc.md"
    md.write_text("# Title\n", encoding="utf-8")
    assert parse_file("doc.md", str(md)).language == "markdown"

    other = tmp_path / "data.txt"
    other.write_text("hello\n", encoding="utf-8")
    assert parse_file("data.txt", str(other)).language == "other"


def test_dispatch_typescript(tmp_path):
    ts = tmp_path / "x.ts"
    ts.write_text("function t(): number { return 1; }\n", encoding="utf-8")
    pf = parse_file("x.ts", str(ts))
    assert pf.language == "typescript"
    assert any(s.name == "t" for s in pf.symbols)


def test_read_missing_file_is_graceful():
    # _read swallows errors -> empty source -> empty parse, no exception
    pf = parse_file("nope.py", "/path/does/not/exist.py")
    assert pf.language == "python"
    assert pf.symbols == []


def test_js_loc_matches_line_count():
    # loc must be count('\n')+1 (Python's convention), not len(splitlines())+1 (audit off-by-one).
    pf = parse_js("x.js", "const a=1;\nconst b=2;\nconst c=3;", "javascript")
    assert pf.loc == 3
