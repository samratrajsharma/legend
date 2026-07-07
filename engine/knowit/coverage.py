"""Test-reference coverage: which symbols are referenced by test files, and which
(especially complex) symbols have no test. This is *reference* coverage — does a test
mention the symbol — not runtime line coverage; it needs no execution."""
from __future__ import annotations
import os
import re

_IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_TEST_NAME = re.compile(r"(^|[/\\])(test_.*|.*_test)\.(py|js|ts)$", re.I)


def is_test_file(rel):
    rel = rel.replace("\\", "/")
    return bool(_TEST_NAME.search(rel)) or "/tests/" in ("/" + rel + "/") or rel.startswith("tests/")


def test_files(idx):
    return [p.file for p in idx.parsed_files if is_test_file(p.file)]


def tested_symbols(idx):
    """Symbol ids whose name appears as an identifier in any test file."""
    tnames = set()
    tfiles = set(test_files(idx))
    for p in idx.parsed_files:
        if p.file in tfiles:
            tnames |= {m.lower() for m in _IDENT.findall(p.text or "")}
    out = set()
    for nid, n in idx.graph.nodes.items():
        if n["type"] == "symbol" and n["data"]["name"].lower() in tnames:
            out.add(nid)
    return out


def untested(idx):
    tfiles = set(test_files(idx))
    tested = tested_symbols(idx)
    out = []
    for nid, n in idx.graph.nodes.items():
        if n["type"] != "symbol":
            continue
        d = n["data"]
        if d["kind"] == "class" or d["file"] in tfiles:
            continue
        nm = d["name"]
        if nm.startswith("__") and nm.endswith("__"):
            continue
        if nid not in tested:
            out.append({"symbol": d["qualname"], "file": d["file"],
                        "complexity": d.get("complexity", 0)})
    return sorted(out, key=lambda x: -x["complexity"])


def coverage_summary(idx):
    tfiles = test_files(idx)
    funcs = [nid for nid, n in idx.graph.nodes.items()
             if n["type"] == "symbol" and n["data"]["kind"] != "class"
             and n["data"]["file"] not in set(tfiles)]
    tested = tested_symbols(idx) & set(funcs)
    ut = untested(idx)
    return {"test_files": tfiles, "n_test_files": len(tfiles),
            "tested": len(tested), "total": len(funcs),
            "coverage": round(len(tested) / len(funcs), 2) if funcs else 0.0,
            "untested_complex": ut[:15]}
