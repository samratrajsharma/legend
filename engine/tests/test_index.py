"""Tests for legend.index — tokenizer, stemmer, and the BM25 retriever."""
from __future__ import annotations

from legend.index import BM25Retriever, _stem, tokenize


def test_tokenize_splits_camel_and_snake():
    toks = tokenize("HelloWorld foo_bar")
    assert toks == ["hello", "world", "foo", "bar"]


def test_tokenize_drops_single_chars():
    assert tokenize("a bb c dd") == ["bb", "dd"]


def test_tokenize_empty_and_none():
    assert tokenize("") == []
    assert tokenize(None) == []


def test_stem_rules():
    assert _stem("running") == "runn"   # -ing
    assert _stem("classes") == "class"  # -es
    assert _stem("cats") == "cat"       # -s
    assert _stem("quickly") == "quick"  # -ly
    assert _stem("ss") == "ss"          # too short / -ss guard
    assert _stem("bus") == "bus"        # -ss guard keeps trailing s? (len<=3)


class _C:
    """Minimal chunk stand-in for the BM25 retriever (needs .text and .name)."""
    def __init__(self, cid, text, name=""):
        self.id, self.text, self.name = cid, text, name


def test_bm25_ranks_relevant_doc_first():
    chunks = [
        _C("1", "focal loss addresses class imbalance in dense detection"),
        _C("2", "load an image from disk into a raw array"),
        _C("3", "normalize and resize an image into a tensor"),
    ]
    r = BM25Retriever()
    r.index(chunks)
    hits = r.search("focal loss imbalance", k=3)
    assert hits, "no hits"
    assert hits[0][0].id == "1"
    # scores are positive and sorted descending
    scores = [s for _, s in hits]
    assert all(s > 0 for s in scores)
    assert scores == sorted(scores, reverse=True)


def test_bm25_empty_query_returns_nothing():
    r = BM25Retriever()
    r.index([_C("1", "anything at all here")])
    assert r.search("", k=5) == []


def test_bm25_respects_k():
    chunks = [_C(str(i), f"token{i} shared word") for i in range(10)]
    r = BM25Retriever()
    r.index(chunks)
    assert len(r.search("shared", k=3)) == 3


def test_bm25_over_sample_repo(idx):
    hits = idx.lexical.search("detector predict boxes", k=5)
    files = {c.file for c, _ in hits}
    assert "model.py" in files
