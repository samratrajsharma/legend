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
    # 14: the two `model.predict()` / `_MODEL.predict()` edges resolve because the receivers
    # are typed (`model = Detector()`), NOT by guessing on repo-wide name-uniqueness. An
    # UNKNOWN receiver (`d = {}; d.get()`) is left unresolved so it can't phantom-link to a
    # lone same-named symbol - the ~half-the-graph phantom bug the QA audit found.
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


def test_attr_call_does_not_phantom_resolve_cross_file(build_repo):
    # The core audit finding: `obj.method()` on an unknown receiver was resolved to ANY
    # repo-unique symbol of that name, so a plain `dict.get()` linked to a lone `Store.get`
    # in another file (~half of all call edges on a real repo were such phantoms). attr calls
    # must resolve same-file only — a missing edge beats a wrong one.
    repo = build_repo({
        "store.py": "class Store:\n    def get(self, k):\n        return k\n",
        "user.py":  "def lookup():\n    d = {}\n    return d.get('x')\n",
    })
    g = repo.graph
    assert "store.py::Store.get" not in g.callees("user.py::lookup")
    assert all(not t.startswith("store.py") for t in g.callees("user.py::lookup"))


def test_attr_call_resolves_within_same_file(build_repo):
    # Same-file `obj.method()` where the method is defined in that file SHOULD still resolve.
    repo = build_repo({
        "svc.py": (
            "class Helper:\n    def run(self):\n        return 1\n\n"
            "def handler():\n    h = Helper()\n    return h.run()\n"
        ),
    })
    g = repo.graph
    assert "svc.py::Helper.run" in g.callees("svc.py::handler")


def test_typed_receiver_resolves_cross_file(build_repo):
    # When the receiver's class is known (`obj = Cls()` or a `obj: Cls` param annotation),
    # obj.method() resolves to that class's method even across files - precisely, without the
    # name-uniqueness guessing. Both an instance and an annotated-param receiver.
    repo = build_repo({
        "engine.py": "class Engine:\n    def run(self):\n        return 1\n",
        "app.py": (
            "from engine import Engine\n\n"
            "def viainstance():\n    e = Engine()\n    return e.run()\n\n"
            "def viaparam(e: Engine):\n    return e.run()\n"
        ),
    })
    g = repo.graph
    assert "engine.py::Engine.run" in g.callees("app.py::viainstance")
    assert "engine.py::Engine.run" in g.callees("app.py::viaparam")


def test_decorated_handler_no_phantom_call_edge(build_repo):
    # End-to-end guard for the decorator-walk bug: a decorated handler in a repo that also
    # defines a symbol named `get` must NOT gain a phantom edge to it.
    repo = build_repo({
        "cache.py": "class Cache:\n    def get(self, k):\n        return k\n",
        "routes.py": (
            "import flask\napp = flask.Flask(__name__)\n\n"
            '@app.get("/items")\n'
            "def handler():\n    return []\n"
        ),
    })
    g = repo.graph
    assert "cache.py::Cache.get" not in g.callees("routes.py::handler")


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
