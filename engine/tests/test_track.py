"""Tests for knowit.track — git log, structural snapshots, and diffs over commits.

Uses the synthetic two-commit ``git_repo`` fixture; skips if git is unavailable.
"""
from __future__ import annotations

from knowit import track
from knowit.config import Config


def _cfg(tmp_path):
    return Config(embed_backend="bm25", data_dir=str(tmp_path / "data"),
                  use_cache=False, llm_model="")


def test_is_git(git_repo, tmp_path):
    assert track.is_git(git_repo["path"]) is True
    assert track.is_git(str(tmp_path)) is False


def test_git_log(git_repo):
    log = track.git_log(git_repo["path"])
    assert len(log) >= 2
    for c in log:
        assert {"sha", "short", "author", "date", "subject"} <= set(c)
    assert log[0]["subject"] == "head"          # most recent first


def test_snapshot_fingerprint_shape(git_repo, tmp_path):
    fp = track.snapshot(git_repo["path"], git_repo["base"], _cfg(tmp_path))
    assert {"commit", "files", "symbols", "imports", "calls"} <= set(fp)
    assert "a.py" in fp["files"] and "b.py" in fp["files"]
    assert "a.py::alpha" in fp["symbols"]


def test_diff_detects_changes(git_repo, tmp_path):
    cfg = _cfg(tmp_path)
    base = track.snapshot(git_repo["path"], git_repo["base"], cfg)
    head = track.snapshot(git_repo["path"], git_repo["head"], cfg)
    d = track.diff(base, head)

    assert "c.py" in d["files_added"]
    assert any(s.endswith("::gamma") for s in d["symbols_added"])
    assert any(s.endswith("::delta") for s in d["symbols_added"])
    assert "a.py::alpha" in d["symbols_modified"]
    # alpha grew an extra branch -> complexity rose
    alpha_cx = next(c for c in d["complexity_changes"] if c["symbol"] == "alpha")
    assert alpha_cx["from"] < alpha_cx["to"]


def test_changelog_text(git_repo, tmp_path):
    cfg = _cfg(tmp_path)
    d = track.diff(track.snapshot(git_repo["path"], git_repo["base"], cfg),
                   track.snapshot(git_repo["path"], git_repo["head"], cfg))
    text = track.changelog_text(d)
    assert "Files added" in text
    assert "c.py" in text


def test_changelog_text_empty_diff():
    empty = track.diff({"files": {}, "symbols": {}, "imports": []},
                       {"files": {}, "symbols": {}, "imports": []})
    assert "No structural changes" in track.changelog_text(empty)


def test_architecture_delta_dot(git_repo, tmp_path):
    cfg = _cfg(tmp_path)
    base = track.snapshot(git_repo["path"], git_repo["base"], cfg)
    head = track.snapshot(git_repo["path"], git_repo["head"], cfg)
    dot = track.architecture_delta_dot(base, head)
    assert dot.startswith("digraph G {")
    assert "c.py" in dot                       # newly added file node


def test_learning_delta(git_repo, tmp_path):
    cfg = _cfg(tmp_path)
    d = track.diff(track.snapshot(git_repo["path"], git_repo["base"], cfg),
                   track.snapshot(git_repo["path"], git_repo["head"], cfg))
    ld = track.learning_delta(d, explored=["a.py"])
    assert "a.py" in ld["re_learn"]            # studied & it changed
    assert "c.py" in ld["new_files"]


def test_narrate_llm_without_model():
    assert track.narrate_llm({"files_added": []}, model="") is None
