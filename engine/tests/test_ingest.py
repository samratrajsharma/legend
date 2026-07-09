"""Tests for knowit.ingest — repo metadata, file walking, and source resolution."""
from __future__ import annotations

import os

import pytest

from knowit.ingest import clone_or_local, ingest, list_files, repo_meta


def test_repo_meta_local_non_git(sample_repo_path):
    m = repo_meta(sample_repo_path)
    assert m.name == "sample_repo"
    assert m.commit == "working-tree"   # sample_repo is not a git checkout
    assert m.is_git is False
    assert m.n_commits == 0


def test_list_files_counts_and_sorting(sample_repo_path):
    code, docs = list_files(sample_repo_path)
    assert len(code) == 6
    assert len(docs) == 1
    assert all(rel.endswith(".py") for rel, _ in code)
    assert docs[0][0].endswith("README.md")
    rels = [rel for rel, _ in code]
    assert rels == sorted(rels)         # deterministic order


def test_list_files_skips_vendored_and_cache_dirs(tmp_path):
    (tmp_path / "keep.py").write_text("x = 1\n", encoding="utf-8")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "keep2.py").write_text("y = 2\n", encoding="utf-8")
    for junk in ("node_modules", "__pycache__", ".git", ".venv"):
        (tmp_path / junk).mkdir()
        (tmp_path / junk / "ignored.py").write_text("z = 3\n", encoding="utf-8")

    code, _ = list_files(str(tmp_path))
    rels = {rel.replace("\\", "/") for rel, _ in code}
    assert rels == {"keep.py", "sub/keep2.py"}


def test_clone_or_local_returns_absolute_path(sample_repo_path, tmp_path):
    p = clone_or_local(sample_repo_path, str(tmp_path))
    assert os.path.isabs(p)
    assert os.path.isdir(p)


def test_clone_or_local_missing_dir_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        clone_or_local(str(tmp_path / "does_not_exist"), str(tmp_path))


def test_ingest_returns_meta_and_files(sample_repo_path, tmp_path):
    meta, code, docs = ingest(sample_repo_path, str(tmp_path))
    assert meta.name == "sample_repo"
    assert len(code) == 6
    assert len(docs) == 1
