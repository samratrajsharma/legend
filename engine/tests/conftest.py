"""Shared pytest fixtures for the KnowIT test suite.

The fixtures build a real RepoIndex over the bundled ``sample_repo`` using a
**BM25-only** config so the suite is fast, fully offline, and deterministic
(no chromadb embedding, no network, no LLM). Optional-dependency code paths are
tested separately for their graceful-degradation behaviour.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

# Make the project root importable regardless of how pytest is invoked.
ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "sample_repo"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from knowit.config import Config          # noqa: E402
from knowit.pipeline import build_index   # noqa: E402


@pytest.fixture(scope="session")
def project_root() -> Path:
    return ROOT


@pytest.fixture(scope="session")
def sample_repo_path() -> str:
    assert SAMPLE.is_dir(), f"sample_repo missing at {SAMPLE}"
    return str(SAMPLE)


@pytest.fixture(scope="session")
def bm25_config(tmp_path_factory) -> Config:
    """A BM25-only, no-cache, no-LLM config writing into a throwaway data dir."""
    data_dir = tmp_path_factory.mktemp("knowit_data")
    return Config(embed_backend="bm25", data_dir=str(data_dir),
                  use_cache=False, llm_model="", llm_provider="")


@pytest.fixture(scope="session")
def idx(sample_repo_path, bm25_config):
    """A built RepoIndex over sample_repo (BM25 lexical only, dense=None)."""
    return build_index(sample_repo_path, config=bm25_config, register=False)


@pytest.fixture
def build_repo(tmp_path_factory):
    """Factory: write a dict of {relpath: source} to a temp dir and build a
    BM25-only RepoIndex over it. Useful for exercising features that sample_repo
    does not cover (HTTP routes, ORM models, import cycles, near-duplicates)."""
    def _make(files, name="synthetic"):
        d = tmp_path_factory.mktemp(name)
        for rel, content in files.items():
            p = d / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
        cfg = Config(embed_backend="bm25", data_dir=str(d / "_data"),
                     use_cache=False, llm_model="")
        return build_index(str(d), config=cfg, register=False)
    return _make


# --------------------------------------------------------------------------- #
# Synthetic git repo for the Track (snapshot/diff) feature.
# --------------------------------------------------------------------------- #
def _git(args, cwd):
    return subprocess.run(["git"] + args, cwd=cwd, capture_output=True, text=True)


@pytest.fixture(scope="session")
def git_repo(tmp_path_factory):
    """A tiny 2-commit git repo. Returns {'path', 'base', 'head'}.

    Skips if git is not on PATH.
    """
    if shutil.which("git") is None:
        pytest.skip("git not available on PATH")

    repo = tmp_path_factory.mktemp("git_repo")
    _git(["init", "-q"], repo)
    # Local identity so commits succeed in CI / clean environments.
    _git(["config", "user.email", "test@example.com"], repo)
    _git(["config", "user.name", "KnowIT Test"], repo)
    _git(["config", "commit.gpgsign", "false"], repo)

    # --- base commit ---
    (repo / "a.py").write_text(
        "def alpha(x):\n"
        "    if x > 0:\n"
        "        return x\n"
        "    return -x\n",
        encoding="utf-8",
    )
    (repo / "b.py").write_text(
        "from a import alpha\n\n\ndef beta():\n    return alpha(1)\n",
        encoding="utf-8",
    )
    _git(["add", "-A"], repo)
    _git(["commit", "-q", "-m", "base"], repo)
    base = _git(["rev-parse", "HEAD"], repo).stdout.strip()

    # --- head commit: add a file, grow a.alpha's complexity, add a symbol ---
    (repo / "a.py").write_text(
        "def alpha(x):\n"
        "    if x > 0:\n"
        "        return x\n"
        "    elif x == 0:\n"
        "        return 1\n"
        "    return -x\n\n\n"
        "def gamma():\n    return 42\n",
        encoding="utf-8",
    )
    (repo / "c.py").write_text("def delta():\n    return 0\n", encoding="utf-8")
    _git(["add", "-A"], repo)
    _git(["commit", "-q", "-m", "head"], repo)
    head = _git(["rev-parse", "HEAD"], repo).stdout.strip()

    return {"path": str(repo), "base": base, "head": head}
