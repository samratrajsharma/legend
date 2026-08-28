"""Tests for legend.techdebt — dead code, duplicates, cycles, hotspots, god files."""
from __future__ import annotations

from legend.techdebt import (_normalize_py, complexity_hotspots, dead_code,
                             debt_summary, duplicate_pairs, god_files,
                             import_cycles, undocumented)

DUP_SRC = (
    "def f1(a, b):\n"
    "    total = 0\n"
    "    for i in range(a):\n"
    "        total = total + b\n"
    "        if total > 10:\n"
    "            total = total - 1\n"
    "    return total\n\n\n"
    "def f2(x, y):\n"
    '    """A completely different docstring."""\n'
    "    acc = 0\n"
    "    for j in range(x):\n"
    "        acc = acc + y\n"
    "        if acc > 10:\n"
    "            acc = acc - 1\n"
    "    return acc\n"
)


def test_dead_code(idx):
    dead = {d["symbol"] for d in dead_code(idx)}
    assert "cross_entropy" in dead         # never called anywhere
    assert "create_app" not in dead        # referenced by api.py's __main__
    assert "focal_loss" not in dead        # called by Detector.loss / train


def test_undocumented(idx):
    undoc = {d["symbol"] for d in undocumented(idx)}
    assert "Detector._build_backbone" in undoc   # no docstring
    assert "Detector.predict" not in undoc       # has a docstring


def test_complexity_hotspots_threshold(idx):
    assert complexity_hotspots(idx, threshold=10) == []   # sample is simple
    low = complexity_hotspots(idx, threshold=1)
    assert low and all(h["complexity"] >= 1 for h in low)
    # sorted by complexity descending
    cx = [h["complexity"] for h in low]
    assert cx == sorted(cx, reverse=True)


def test_god_files(idx):
    assert god_files(idx) == []                      # nothing huge by default
    flagged = {g["file"] for g in god_files(idx, sym_threshold=5)}
    assert "model.py" in flagged                     # Detector + 6 methods


def test_import_cycles_none_in_sample(idx):
    assert import_cycles(idx) == []


def test_import_cycles_detected(build_repo):
    repo = build_repo({
        "mod_a.py": "from mod_b import b\n\n\ndef a():\n    return b()\n",
        "mod_b.py": "from mod_a import a\n\n\ndef b():\n    return a()\n",
    })
    cycles = import_cycles(repo)
    assert cycles
    assert {"mod_a.py", "mod_b.py"} in [set(c) for c in cycles]


def test_duplicate_pairs_detected(build_repo):
    repo = build_repo({"dup.py": DUP_SRC})
    pairs = duplicate_pairs(repo)
    assert pairs
    top = pairs[0]
    assert top["similarity"] >= 0.75
    names = {top["a"].split()[0], top["b"].split()[0]}
    assert names == {"f1", "f2"}


def test_normalize_py_ignores_names_and_docstrings():
    a = _normalize_py("def f(x):\n    '''doc'''\n    return x + 1\n")
    b = _normalize_py("def g(y):\n    return y + 1\n")
    assert a == b and a is not None


def test_debt_summary_has_all_sections(idx):
    summary = debt_summary(idx)
    assert set(summary) == {"dead_code", "duplicates", "import_cycles",
                            "complexity_hotspots", "god_files", "undocumented"}
