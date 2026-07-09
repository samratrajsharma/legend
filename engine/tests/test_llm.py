"""Tests for knowit.llm — graceful degradation when no model is configured.

These deliberately avoid the network: every assertion targets a no-model / empty
short-circuit path so the suite stays offline and deterministic.
"""
from __future__ import annotations

from knowit.llm import explain_file, judge, synthesize


def test_synthesize_without_model():
    answer, used = synthesize("q?", "some context", model="")
    assert answer is None
    assert used is False


def test_judge_without_model_or_answer():
    assert judge("q?", "an answer", "ctx", model="") is None     # no model
    assert judge("q?", "", "ctx", model="some/model") is None    # no answer


def test_explain_file_without_model():
    assert explain_file({"file": "x.py"}, "code", model="") is None
