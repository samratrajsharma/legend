"""Tests for knowit.graph — CodeGraph structure and build_graph relationships."""
from __future__ import annotations

from knowit.graph import CodeGraph, build_graph
from knowit.parsing import parse_python


def test_stats_match_sample_repo(idx):
    s = idx.graph.stats()
    assert s["nodes"] == 22          # 7 files (6 .py + README) + 15 symbols
    assert s["node_types"]["file"] == 7
    assert s["node_types"]["symbol"] == 15
    assert s["edge_types"]["contains"] == 15   # one per symbol
    assert s["edge_types"]["imports"] == 7
    assert s["edge_types"]["method_of"] == 6   # Detector's 6 methods
    assert s["edge_types"]["calls"] == 14
    assert s["edges"] == 42


def test_contains_edges(idx):
    g = idx.graph
    contained = set(g.successors("model.py", "contains"))
    assert "model.py::Detector" in contained
    assert "model.py::Detector.predict" in contained


def test_imports_edges_direction(idx):
    g = idx.graph
    # infer.py imports data.py and model.py
    assert set(g.successors("infer.py", "imports")) == {"data.py", "model.py"}
    # api.py imports infer.py -> infer.py has api.py as an import-predecessor
    assert "api.py" in g.predecessors("infer.py", "imports")


def test_calls_and_method_of_edges(idx):
    g = idx.graph
    # Detector.loss calls focal_loss
    assert "losses.py::focal_loss" in g.callees("model.py::Detector.loss")
    # focal_loss is called by Detector.loss (among others)
    assert "model.py::Detector.loss" in g.callers("losses.py::focal_loss")
    # methods point at their class via method_of
    assert "model.py::Detector" in g.successors("model.py::Detector.predict", "method_of")


def test_get_and_neighbors(idx):
    g = idx.graph
    node = g.get("model.py::Detector")
    assert node["type"] == "symbol"
    assert node["data"]["kind"] == "class"
    # neighbors is the undirected union and de-duplicated
    nb = g.neighbors("model.py::Detector")
    assert isinstance(nb, list)
    assert len(nb) == len(set(nb))


def test_all_edges_filter(idx):
    g = idx.graph
    only_imports = g.all_edges("imports")
    assert len(only_imports) == 7
    assert all(t == "imports" for _, _, t in only_imports)


def test_inherits_edge_built():
    src_a = "class Base:\n    pass\n"
    src_b = "class Sub(Base):\n    def m(self):\n        return 1\n"
    pa = parse_python("base.py", src_a)
    pb = parse_python("sub.py", src_b)
    g = build_graph([pa, pb])
    assert "base.py::Base" in g.successors("sub.py::Sub", "inherits")


def test_add_edge_requires_existing_nodes():
    g = CodeGraph()
    g.add_node("a", "file")
    # dst missing -> edge silently dropped (no exception, no edge)
    g.add_edge("a", "missing", "imports")
    assert g.successors("a", "imports") == []
    g.add_node("b", "file")
    g.add_edge("a", "b", "imports")
    assert g.successors("a", "imports") == ["b"]


def test_idempotent_add_node():
    g = CodeGraph()
    g.add_node("a", "file", {"v": 1})
    g.add_node("a", "file", {"v": 2})  # ignored once present
    assert g.get("a")["data"]["v"] == 1
