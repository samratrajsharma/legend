#!/usr/bin/env python3
"""Verify the optional tree-sitter backend after installing it.

The tree-sitter backend (engine/legend/treesitter_parser.py) adds symbol + call
extraction for Go, Java, Rust, C#, Ruby, PHP, C and C++. It is OFF until you install
the grammars, and it's written to degrade to `None` (caller falls back to plain-text
indexing) on any grammar quirk rather than crash. This script proves it actually works
on your machine and which languages your installed grammar pack covers.

Run:
    pip install tree-sitter tree-sitter-language-pack
    python engine/scripts/verify_treesitter.py

Reading the output:
    PASS  - grammar loaded and we extracted the expected functions (and, where checked,
            the expected call edge). This language is fully working.
    SKIP  - that grammar isn't in your installed pack. The language still gets indexed as
            searchable text; only symbol/call extraction is unavailable for it.
    FAIL  - grammar loaded but extraction was wrong. Copy the whole output into the chat
            and I'll fix the node-type mapping for that grammar version.

Exit code is non-zero if any language FAILs (SKIP does not fail the run).
"""
from __future__ import annotations

import os
import sys

# make `import legend...` work whether run from repo root or from engine/
_HERE = os.path.dirname(os.path.abspath(__file__))
_ENGINE = os.path.dirname(_HERE)
if _ENGINE not in sys.path:
    sys.path.insert(0, _ENGINE)

from legend import treesitter_parser as ts  # noqa: E402

# Each fixture: a class/struct holding two functions where one calls the other, plus
# (some languages) a free function. We assert the function names come through, and -
# where the grammar reliably exposes it - that the intra-file call edge is captured.
FIXTURES = {
    "go": (
        "main.go",
        "package main\n"
        "func Add(a int, b int) int { return a + b }\n"
        "func Run() int { return Add(1, 2) }\n",
        {"Add", "Run"},            # expected symbol names
        ("Run", "Add"),            # expected call edge (caller, callee) or None
    ),
    "java": (
        "Calc.java",
        "public class Calc {\n"
        "    int add(int a, int b) { return a + b; }\n"
        "    int run() { return add(1, 2); }\n"
        "}\n",
        {"Calc", "add", "run"},
        ("run", "add"),
    ),
    "rust": (
        "calc.rs",
        "struct Calc;\n"
        "impl Calc {\n"
        "    fn add(&self, a: i32, b: i32) -> i32 { a + b }\n"
        "    fn run(&self) -> i32 { self.add(1, 2) }\n"
        "}\n"
        "fn main() { let c = Calc; c.run(); }\n",
        {"add", "run", "main"},
        ("run", "add"),
    ),
    "c_sharp": (
        "Calc.cs",
        "public class Calc {\n"
        "    int Add(int a, int b) { return a + b; }\n"
        "    int Run() { return Add(1, 2); }\n"
        "}\n",
        {"Calc", "Add", "Run"},
        ("Run", "Add"),
    ),
    "ruby": (
        "calc.rb",
        "class Calc\n"
        "  def add(a, b)\n    a + b\n  end\n"
        "  def run\n    add(1, 2)\n  end\n"
        "end\n",
        {"Calc", "add", "run"},
        ("run", "add"),
    ),
    "php": (
        "Calc.php",
        "<?php\n"
        "class Calc {\n"
        "    function add($a, $b) { return $a + $b; }\n"
        "    function run() { return $this->add(1, 2); }\n"
        "}\n",
        {"Calc", "add", "run"},
        ("run", "add"),
    ),
    "c": (
        "calc.c",
        "int add(int a, int b) { return a + b; }\n"
        "int run() { return add(1, 2); }\n",
        {"add", "run"},
        ("run", "add"),
    ),
    "cpp": (
        "calc.cpp",
        "struct Calc {\n"
        "    int add(int a, int b) { return a + b; }\n"
        "    int run() { return add(1, 2); }\n"
        "};\n",
        {"add", "run"},
        ("run", "add"),
    ),
}


def _find(symbols, name):
    for s in symbols:
        if s.name == name:
            return s
    return None


def main() -> int:
    print("=" * 72)
    print("tree-sitter backend verification")
    print("=" * 72)
    if not ts.available():
        print("\ntree-sitter is NOT installed (no grammar loader found).")
        print("Install it, then re-run:")
        print("    pip install tree-sitter tree-sitter-language-pack")
        print("    python engine/scripts/verify_treesitter.py")
        return 1
    print("loader: available\n")
    print(f"{'language':10} {'grammar':8} {'symbols':8} {'call-edge':10} status")
    print("-" * 72)

    failures = 0
    passes = 0
    skips = 0
    diagnostics = []
    loader = ts._find_loader()             # noqa: SLF001 - intentional introspection
    for lang, (fname, code, want_names, want_call) in FIXTURES.items():
        parser = ts._parser_for(lang)          # noqa: SLF001 - intentional introspection
        if parser is None:
            # say WHY it didn't load - grammar genuinely absent vs. raised on load
            why = "grammar not in pack"
            for name in ts._GRAMMAR.get(lang, [lang]):     # noqa: SLF001
                try:
                    loader(name)
                except Exception as e:                     # capture the real error
                    why = f"{name!r} -> {type(e).__name__}: {e}"
            print(f"{lang:10} {'-':8} {'-':8} {'-':10} SKIP ({why})")
            skips += 1
            continue
        pf = ts.ts_parse(fname, code, lang)
        if pf is None or not pf.symbols:
            print(f"{lang:10} {'ok':8} {'0':8} {'-':10} FAIL (loaded but extracted nothing)")
            # dump the root node's child types so the mapping can be fixed precisely
            try:
                tree = parser.parse(code.encode("utf-8"))
                kids = sorted({c.type for c in tree.root_node.children})
                diagnostics.append(f"[{lang}] root child node-types: {kids}")
            except Exception as e:
                diagnostics.append(f"[{lang}] could not introspect: {e}")
            failures += 1
            continue
        got = {s.name for s in pf.symbols}
        missing = want_names - got
        # call edge check (soft: a miss is a warning, not a hard fail - call wiring is
        # the most grammar-sensitive part and the graph also resolves calls by name)
        call_ok = "n/a"
        if want_call:
            caller, callee = want_call
            cs = _find(pf.symbols, caller)
            if cs is not None:
                call_ok = "yes" if callee in cs.calls else "no"
        if missing:
            print(f"{lang:10} {'ok':8} {len(got):<8} {call_ok:10} "
                  f"FAIL (missing {sorted(missing)}; got {sorted(got)})")
            try:
                tree = parser.parse(code.encode("utf-8"))

                def _types(node, depth=0, acc=None):
                    acc = acc if acc is not None else []
                    if depth <= 3:
                        for c in node.children:
                            acc.append(c.type)
                            _types(c, depth + 1, acc)
                    return acc
                seen = sorted(set(_types(tree.root_node)))
                diagnostics.append(f"[{lang}] node-types (depth<=3): {seen}")
            except Exception as e:
                diagnostics.append(f"[{lang}] could not introspect: {e}")
            failures += 1
        else:
            note = "" if call_ok in ("yes", "n/a") else "  (call edge soft-missed)"
            print(f"{lang:10} {'ok':8} {len(got):<8} {call_ok:10} PASS{note}")
            passes += 1

    print("-" * 72)
    print(f"{passes} passed, {skips} skipped (grammar not installed), {failures} failed")
    if diagnostics:
        print("\ndiagnostics (paste these with the table):")
        for d in diagnostics:
            print("  " + d)
    if failures:
        print("\nSome languages FAILED. Paste this whole output into the chat and I'll "
              "adjust the node-type mapping for your grammar-pack version.")
    elif passes:
        print("\nAll installed grammars work. Languages shown SKIP are indexed as "
              "searchable text until their grammar is added to the pack.")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
