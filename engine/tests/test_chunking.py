"""Tests for knowit.chunking — provenance chunks for code / module / doc."""
from __future__ import annotations

from knowit.chunking import _truncate, make_chunks
from knowit.parsing import parse_file, parse_js


def test_chunk_kinds_and_counts(idx):
    kinds = [c.kind for c in idx.chunks]
    assert kinds.count("module") == 6   # one per code file
    assert kinds.count("symbol") == 15  # one per symbol
    assert kinds.count("doc") == 1      # README.md
    assert len(idx.chunks) == 22


def test_chunk_ids_unique(idx):
    ids = [c.id for c in idx.chunks]
    assert len(ids) == len(set(ids))


def test_symbol_chunks_carry_symbol_id(idx):
    for c in idx.chunks:
        if c.kind == "symbol":
            assert c.symbol_id is not None
            assert c.node_id == c.symbol_id
        else:
            assert c.symbol_id is None


def test_commit_propagated_to_chunks(sample_repo_path):
    pf = parse_file("losses.py", f"{sample_repo_path}/losses.py")
    chunks = make_chunks([pf], commit="deadbeef")
    assert chunks and all(c.commit == "deadbeef" for c in chunks)


def test_module_header_reflects_language():
    """The module chunk header must name the file's real language, not always
    'python' (regression: header was hardcoded to '(python)')."""
    js = (
        'import { x } from "./x";\n'
        "export function go() { return 1; }\n"
    )
    pf = parse_js("widget.js", js, "javascript")
    chunks = make_chunks([pf], commit="c")
    mod = next(c for c in chunks if c.kind == "module")
    assert mod.text.startswith("FILE widget.js (javascript)")
    assert "(python)" not in mod.text


def test_truncate_marks_dropped_lines():
    text = "\n".join(f"line{i}" for i in range(50))
    out = _truncate(text, max_lines=10)
    assert out.splitlines()[:10] == [f"line{i}" for i in range(10)]
    assert "40 more lines truncated" in out


def test_truncate_keeps_short_text_verbatim():
    text = "a\nb\nc"
    assert _truncate(text, max_lines=10) == text


def test_doc_chunk_for_markdown(idx):
    docs = [c for c in idx.chunks if c.kind == "doc"]
    assert len(docs) == 1
    assert docs[0].file.endswith("README.md")
