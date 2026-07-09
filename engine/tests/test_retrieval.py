"""Tests for knowit.retrieval — RRF fusion, hybrid search, context assembly."""
from __future__ import annotations

from knowit.models import Retrieved
from knowit.retrieval import _rrf, assemble_context, hybrid_search


class _Chunk:
    def __init__(self, cid, file="f.py", start=1, end=2, name="n", text="body"):
        self.id, self.file, self.start_line, self.end_line = cid, file, start, end
        self.name, self.text = name, text


def test_rrf_fuses_and_tracks_sources():
    a, b, c = _Chunk("a"), _Chunk("b"), _Chunk("c")
    lexical = [(a, 9.0), (b, 1.0)]
    semantic = [(a, 0.8), (c, 0.4)]
    scores, sources, by_id = _rrf([("lexical", lexical), ("semantic", semantic)])
    # 'a' appears in both lists -> highest fused score and two sources
    assert scores["a"] > scores["b"]
    assert scores["a"] > scores["c"]
    assert sources["a"] == {"lexical", "semantic"}
    assert by_id["a"] is a


def test_hybrid_search_bm25_only(idx):
    res = hybrid_search("inference flow preprocess predict", idx.lexical, None,
                        idx.graph, idx.chunks_by_node, k=6, expand=0)
    assert res and all(isinstance(r, Retrieved) for r in res)
    assert len(res) <= 6
    scores = [r.score for r in res]
    assert scores == sorted(scores, reverse=True)
    # with no dense retriever, nothing is tagged "semantic"/"both"
    assert all(r.via in ("lexical", "graph") for r in res)


def test_graph_expansion_adds_neighbors(idx):
    no_expand = hybrid_search("focal loss", idx.lexical, None, idx.graph,
                              idx.chunks_by_node, k=6, expand=0)
    expand = hybrid_search("focal loss", idx.lexical, None, idx.graph,
                           idx.chunks_by_node, k=6, expand=1)
    # expansion may surface additional graph-linked chunks and never fewer
    assert len(expand) >= len(no_expand)
    assert len(expand) <= 6 + 3   # k + k//2 cap


def test_assemble_context_format_and_caps(idx):
    res = idx.search("detector model")
    ctx = assemble_context(res, max_blocks=3, max_chars=6000)
    assert ctx
    # provenance header: [file:start-end :: name]
    first = ctx.splitlines()[0]
    assert first.startswith("[") and "::" in first


def test_assemble_context_respects_char_budget(idx):
    res = idx.search("detector model")
    tiny = assemble_context(res, max_blocks=8, max_chars=5)
    # the very first block already exceeds 5 chars -> nothing fits
    assert tiny == ""


def test_assemble_context_empty_input():
    assert assemble_context([]) == ""
