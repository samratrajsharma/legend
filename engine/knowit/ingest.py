from __future__ import annotations
import os
import shutil
import subprocess
from .models import RepoMeta

SKIP_DIRS = {".git", ".knowit_cache", "__pycache__", "node_modules", ".venv",
             "venv", "env", "ENV", "build", "dist", ".mypy_cache", ".pytest_cache",
             ".ruff_cache", "site-packages", ".ipynb_checkpoints", ".idea", ".vscode"}
CODE_EXTS = {".py", ".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx"}
DOC_EXTS = {".md"}
CONFIG_EXTS = {".yaml", ".yml", ".toml", ".ini", ".cfg"}


def _git(args, cwd):
    try:
        out = subprocess.run(["git"] + args, cwd=cwd, capture_output=True,
                             text=True, timeout=15)
        if out.returncode == 0:
            return out.stdout.strip()
    except Exception:
        pass
    return ""


def clone_or_local(source, data_dir):
    """Return an absolute path to a local working copy; clone git URLs on demand."""
    if source.startswith(("http://", "https://", "git@")) or source.endswith(".git"):
        repos = os.path.join(data_dir, "repos")
        os.makedirs(repos, exist_ok=True)
        name = source.rstrip("/").split("/")[-1]
        if name.endswith(".git"):
            name = name[:-4]
        dest = os.path.join(repos, name)
        if not os.path.isdir(dest):
            # --single-branch + --no-tags keep large clones lean; depth 200 is
            # still enough history for the over-time tracking feature.
            try:
                r = subprocess.run(
                    ["git", "clone", "--depth", "200", "--single-branch", "--no-tags", source, dest],
                    capture_output=True, text=True, timeout=900,
                )
            except subprocess.TimeoutExpired:
                shutil.rmtree(dest, ignore_errors=True)   # don't leave a half-clone behind
                raise RuntimeError(
                    "git clone timed out (15 min). The repo may be very large — "
                    "clone it locally and connect the folder path instead."
                )
            if r.returncode != 0:
                shutil.rmtree(dest, ignore_errors=True)   # so a retry starts clean
                err = (r.stderr or "").strip()
                low = err.lower()
                if any(k in low for k in ("authentication", "could not read username", "permission denied", "403")):
                    hint = ("Authentication failed. For a private repo, put a token in the URL "
                            "(https://<token>@github.com/owner/repo.git) or connect a local clone.")
                elif any(k in low for k in ("not found", "404")):
                    hint = "Repository not found — check the URL and that you have access."
                elif any(k in low for k in ("could not resolve host", "unable to access", "timed out", "network")):
                    hint = "Network error reaching the remote — check your connection/VPN, then retry."
                else:
                    hint = err[:400] or "unknown git error"
                raise RuntimeError(f"git clone failed: {hint}")
        return os.path.abspath(dest)
    path = os.path.abspath(os.path.expanduser(source))
    if not os.path.isdir(path):
        raise FileNotFoundError(f"Not a directory: {path}")
    return path


def repo_meta(path):
    is_git = os.path.isdir(os.path.join(path, ".git"))
    commit = _git(["rev-parse", "HEAD"], path) if is_git else ""
    branch = _git(["rev-parse", "--abbrev-ref", "HEAD"], path) if is_git else ""
    n = _git(["rev-list", "--count", "HEAD"], path) if is_git else ""
    return RepoMeta(
        name=os.path.basename(path.rstrip("/")) or path,
        path=path,
        commit=commit or "working-tree",
        branch=branch,
        is_git=is_git,
        n_commits=int(n) if n.isdigit() else 0,
    )


def list_files(path, max_files=8000):
    code, docs = [], []
    for root, dirs, files in os.walk(path):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for f in files:
            ext = os.path.splitext(f)[1].lower()
            abs_p = os.path.join(root, f)
            rel = os.path.relpath(abs_p, path)
            if ext in CODE_EXTS:
                code.append((rel, abs_p))
            elif ext in DOC_EXTS or ext in CONFIG_EXTS:
                docs.append((rel, abs_p))
        if len(code) + len(docs) > max_files:
            break
    code.sort()
    docs.sort()
    return code, docs


def ingest(source, data_dir):
    """source -> (RepoMeta, list[(rel, abs)] code files, list[(rel, abs)] doc files)."""
    path = clone_or_local(source, data_dir)
    meta = repo_meta(path)
    code, docs = list_files(path)
    return meta, code, docs
