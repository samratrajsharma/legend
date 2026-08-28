"""Smoke tests: every module imports, and the non-importable entry points
(the Streamlit app, helper scripts) at least compile cleanly."""
from __future__ import annotations

import importlib
import py_compile

import pytest

LEGEND_MODULES = [
    "legend", "legend.config", "legend.models", "legend.providers",
    "legend.ingest", "legend.parsing", "legend.graph", "legend.chunking",
    "legend.index", "legend.retrieval", "legend.llm", "legend.insights",
    "legend.diagram", "legend.teach", "legend.track", "legend.techdebt",
    "legend.engmemory", "legend.media", "legend.pipeline", "legend.eval_harness",
]


@pytest.mark.parametrize("mod", LEGEND_MODULES)
def test_module_imports(mod):
    assert importlib.import_module(mod) is not None


@pytest.mark.parametrize("script", [
    "app.py",
    "scripts/run_eval.py",
    "scripts/make_demo_history.py",
])
def test_entrypoints_compile(project_root, script):
    path = project_root / script
    assert path.exists(), f"missing {script}"
    # raises py_compile.PyCompileError on a syntax error
    py_compile.compile(str(path), doraise=True)
