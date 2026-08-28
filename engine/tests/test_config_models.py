"""Tests for legend.config.Config and legend.models dataclasses."""
from __future__ import annotations

from legend.config import Config
from legend.models import Chunk, ParsedFile, RepoMeta, Retrieved, Symbol


def test_config_overrides_apply():
    cfg = Config(embed_backend="bm25", top_k=3, data_dir="x", use_cache=False)
    assert cfg.embed_backend == "bm25"
    assert cfg.top_k == 3
    assert cfg.data_dir == "x"
    assert cfg.use_cache is False
    # llm_kwargs has an independent default dict per instance
    assert Config().llm_kwargs is not Config().llm_kwargs


def test_symbol_defaults_are_independent():
    s1 = Symbol(id="a", name="a", qualname="a", kind="function",
                file="f.py", start_line=1, end_line=2)
    s2 = Symbol(id="b", name="b", qualname="b", kind="function",
                file="f.py", start_line=1, end_line=2)
    assert s1.docstring == "" and s1.code == ""
    assert s1.calls == [] and s1.bases == []
    assert s1.complexity == 0 and s1.parent is None
    # mutable defaults must not be shared between instances
    s1.calls.append("x")
    assert s2.calls == []


def test_parsedfile_defaults():
    pf = ParsedFile(file="f.py", language="python")
    assert pf.imports == [] and pf.symbols == []
    assert pf.loc == 0 and pf.text == "" and pf.error == ""


def test_chunk_defaults_symbol_id_none():
    c = Chunk(id="1", file="f.py", kind="module", name="f.py", start_line=1,
              end_line=5, text="t", node_id="f.py", commit="c")
    assert c.symbol_id is None


def test_repometa_defaults():
    m = RepoMeta(name="r", path="/p", commit="abc")
    assert m.branch == "" and m.is_git is False and m.n_commits == 0


def test_retrieved_fields():
    c = Chunk(id="1", file="f.py", kind="symbol", name="n", start_line=1,
              end_line=2, text="t", node_id="f.py::n", commit="c")
    r = Retrieved(chunk=c, score=0.5, via="both")
    assert r.chunk is c and r.score == 0.5 and r.via == "both"
