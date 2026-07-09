"""Tests for knowit.eval_harness — question loading, scoring, and the gate."""
from __future__ import annotations

import json

from knowit.eval_harness import _kw_coverage, load_questions, run_eval
from knowit.models import Chunk, Retrieved


# --------------------------------------------------------------------------- #
# question loading
# --------------------------------------------------------------------------- #
def test_load_questions_example(project_root):
    qs = load_questions(str(project_root / "eval" / "questions.example.json"))
    assert isinstance(qs, list) and len(qs) == 10
    assert all("question" in q for q in qs)


def test_load_questions_unwraps_dict(tmp_path):
    p = tmp_path / "q.json"
    p.write_text(json.dumps({"questions": [{"question": "a"}]}), encoding="utf-8")
    assert load_questions(str(p)) == [{"question": "a"}]


def test_load_questions_bare_list(tmp_path):
    p = tmp_path / "q.json"
    p.write_text(json.dumps([{"question": "a"}, {"question": "b"}]), encoding="utf-8")
    assert len(load_questions(str(p))) == 2


# --------------------------------------------------------------------------- #
# keyword coverage
# --------------------------------------------------------------------------- #
def test_kw_coverage():
    assert _kw_coverage("foo and BAR", ["foo", "bar"]) == 1.0   # case-insensitive
    assert _kw_coverage("foo only", ["foo", "baz"]) == 0.5
    assert _kw_coverage("text", []) is None
    assert _kw_coverage("text", None) is None


# --------------------------------------------------------------------------- #
# scoring logic (deterministic stub index)
# --------------------------------------------------------------------------- #
def _retr(files):
    return [Retrieved(Chunk(id=str(i), file=f, kind="symbol", name=f, start_line=1,
                            end_line=1, text="", node_id=f, commit=""), 1.0, "lexical")
            for i, f in enumerate(files)]


class _StubIdx:
    def __init__(self, files, context, answer=None, used_llm=False):
        self._files, self._ctx = files, context
        self._answer, self._used = answer, used_llm

    def ask(self, q):
        return {"question": q, "answer": self._answer, "used_llm": self._used,
                "retrieved": _retr(self._files), "context": self._ctx}


def test_run_eval_pass_on_hit_and_keywords():
    stub = _StubIdx(files=["infer.py"], context="it calls predict and postprocess")
    qs = [{"id": "x", "question": "?", "expect_files": ["infer.py"],
           "expect_keywords": ["predict", "postprocess"]}]
    rows, summary = run_eval(stub, qs)
    assert rows[0]["retrieval_hit"] is True
    assert rows[0]["kw_coverage"] == 1.0
    assert rows[0]["passed"] is True
    assert summary["gate_pass"] is True


def test_run_eval_fail_on_missing_keywords():
    stub = _StubIdx(files=["infer.py"], context="nothing relevant here")
    qs = [{"question": "?", "expect_files": ["infer.py"],
           "expect_keywords": ["predict", "postprocess"]}]
    rows, summary = run_eval(stub, qs)
    assert rows[0]["passed"] is False
    assert summary["gate_pass"] is False


def test_run_eval_no_expectations_is_unscored():
    stub = _StubIdx(files=["infer.py"], context="x")
    rows, summary = run_eval(stub, [{"question": "no expectations"}])
    assert rows[0]["passed"] is None
    assert summary["scored"] == 0
    assert summary["total"] == 1


# --------------------------------------------------------------------------- #
# end-to-end against the real BM25 index
# --------------------------------------------------------------------------- #
def test_run_eval_real_index_passes_gate(idx, project_root):
    qs = load_questions(str(project_root / "eval" / "questions.example.json"))
    rows, summary = run_eval(idx, qs)
    assert summary["total"] == 10
    assert summary["scored"] == 10
    assert summary["gate_pass"] is True          # >= 80% on BM25-only retrieval
