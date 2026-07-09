"""Tests for knowit.teach — learning path, flashcards, quizzes, interview, gaps."""
from __future__ import annotations

from knowit.teach import (flashcards, interview, learning_gaps, learning_path,
                          quiz)


def test_learning_path_starts_at_entry_points(idx):
    stops = learning_path(idx)
    assert len(stops) == 6                       # all code files appear once
    files = [s["file"] for s in stops]
    assert len(files) == len(set(files))         # no duplicates
    assert stops[0]["file"] in ("api.py", "train.py")
    assert "entry point" in stops[0]["why"]
    for s in stops:
        assert {"file", "why", "key_symbols", "depends_on"} <= set(s)


def test_flashcards_shape_and_limit(idx):
    cards = flashcards(idx, limit=10)
    assert 0 < len(cards) <= 10
    for c in cards:
        assert set(c) == {"q", "a", "ref"}
    assert any("Detector" in c["q"] for c in cards)


def test_quiz_is_deterministic_with_seed(idx):
    q1 = quiz(idx, level="beginner", n=5, seed=7)
    q2 = quiz(idx, level="beginner", n=5, seed=7)
    assert q1 == q2


def test_quiz_options_are_well_formed(idx):
    qs = quiz(idx, level="beginner", n=5, seed=3)
    assert 0 < len(qs) <= 5
    for q in qs:
        assert {"question", "options", "answer", "explanation", "ref"} <= set(q)
        assert 2 <= len(q["options"]) <= 4
        assert 0 <= q["answer"] < len(q["options"])


def test_quiz_all_levels_produce_questions(idx):
    for level in ("beginner", "intermediate", "senior"):
        qs = quiz(idx, level=level, n=5, seed=1)
        assert isinstance(qs, list)
        assert qs, f"level {level} produced no questions"


def test_interview_questions(idx):
    qs = interview(idx, n=5)
    assert qs
    for q in qs:
        assert {"question", "expected", "ref"} <= set(q)
    assert any("Walk through" in q["question"] for q in qs)


def test_learning_gaps(idx):
    gaps = learning_gaps(idx, explored_files=["model.py"])
    assert gaps["total"] == 6
    assert gaps["explored"] == 1
    assert gaps["coverage"] == round(1 / 6, 2)
    assert "model.py" not in gaps["unexplored"]
    # model.py imports losses.py, which has not been explored
    assert "losses.py" in gaps["used_but_unexplored"]


def test_learning_gaps_ignores_unknown_files(idx):
    gaps = learning_gaps(idx, explored_files=["not_a_real_file.py"])
    assert gaps["explored"] == 0
    assert gaps["coverage"] == 0.0
