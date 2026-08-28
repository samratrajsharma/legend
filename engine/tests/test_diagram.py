"""Tests for legend.diagram — Mermaid/Graphviz generators and graph views."""
from __future__ import annotations

from legend.diagram import (architecture_dot, architecture_mermaid, callflow_dot,
                            class_dot, explain_view_llm, focused_dot, knowledge_dot,
                            mindmap_dot, mindmap_tree, neighborhood,
                            neighborhood_mermaid, node_roles, path_between,
                            pyvis_html)

PREDICT = "model.py::Detector.predict"


def test_architecture_dot_has_import_edge(idx):
    out = architecture_dot(idx)
    assert out.startswith("digraph G {")
    assert '"infer.py" -> "data.py"' in out


def test_architecture_mermaid(idx):
    out = architecture_mermaid(idx)
    assert out.startswith("flowchart LR")
    assert "-->" in out


def test_class_dot_lists_methods(idx):
    out = class_dot(idx)
    assert "digraph" in out
    assert "Detector" in out
    assert "predict" in out          # a method of Detector


def test_callflow_dot(idx):
    out = callflow_dot(idx, PREDICT, depth=2)
    assert "digraph" in out
    assert "Detector._decode" in out  # predict() calls _decode()


def test_callflow_unknown_symbol(idx):
    assert "(symbol not found)" in callflow_dot(idx, "nope::nope")


def test_knowledge_dot(idx):
    out = knowledge_dot(idx)
    assert out.startswith("digraph G {")
    assert "shape=folder" in out


def test_neighborhood_mermaid(idx):
    out = neighborhood_mermaid(idx, PREDICT)
    assert out.startswith("flowchart LR")
    assert "classDef focus" in out


def test_neighborhood_mermaid_unknown(idx):
    assert "(symbol not found)" in neighborhood_mermaid(idx, "nope")


def test_node_roles(idx):
    roles = node_roles(idx)
    assert roles.get("api.py") == "entry"
    assert roles.get("losses.py::cross_entropy") == "unused"


def test_neighborhood_returns_nodes_and_edges(idx):
    nodes, edges = neighborhood(idx, "model.py::Detector", depth=1)
    assert "model.py::Detector" in nodes
    assert all(len(e) == 3 for e in edges)   # (src, dst, etype)


def test_neighborhood_unknown_focus(idx):
    assert neighborhood(idx, "missing") == (set(), [])


def test_focused_dot(idx):
    roles = node_roles(idx)
    nodes, edges = neighborhood(idx, PREDICT, depth=1)
    out = focused_dot(idx, PREDICT, nodes, edges, roles)
    assert out.startswith("digraph G {")
    assert "predict" in out


def test_path_between_via_imports(idx):
    path = path_between(idx, "api.py", "data.py")
    assert path[0] == "api.py" and path[-1] == "data.py"
    assert "infer.py" in path


def test_path_between_unknown_returns_empty(idx):
    assert path_between(idx, "api.py", "missing.py") == []


def test_pyvis_html_graceful_without_dependency(idx):
    roles = node_roles(idx)
    nodes, edges = neighborhood(idx, PREDICT, depth=1)
    out = pyvis_html(idx, PREDICT, nodes, edges, roles)
    # pyvis is optional: returns None when absent, HTML string when installed
    assert out is None or (isinstance(out, str) and "<html" in out.lower())


def test_mindmap_tree_repo_root(idx):
    nodes, tree = mindmap_tree(idx, "__repo__", depth=2)
    assert "__repo__" in nodes
    assert tree                      # repo -> files -> symbols


def test_mindmap_tree_symbol_root(idx):
    nodes, tree = mindmap_tree(idx, "model.py::Detector", depth=1,
                               etypes=("method_of",))
    # Detector's methods become children
    assert any(b.startswith("model.py::Detector.") for _, b in tree)


def test_mindmap_dot(idx):
    roles = node_roles(idx)
    nodes, tree = mindmap_tree(idx, "__repo__", depth=2)
    out = mindmap_dot(idx, "__repo__", nodes, tree, roles, repo_name="sample_repo")
    assert out.startswith("digraph G {")
    assert "sample_repo  (repo)" in out


def test_explain_view_llm_without_model(idx):
    nodes, edges = neighborhood(idx, PREDICT, depth=1)
    assert explain_view_llm(idx, nodes, edges, PREDICT, model="") is None
