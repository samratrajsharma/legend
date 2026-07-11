from __future__ import annotations
import hashlib
import os
import re
import shutil
import stat
import subprocess
import time
from .models import RepoMeta

SKIP_DIRS = {".git", ".knowit_cache", "__pycache__", "node_modules", ".venv",
             "venv", "env", "ENV", "build", "dist", ".mypy_cache", ".pytest_cache",
             ".ruff_cache", "site-packages", ".ipynb_checkpoints", ".idea", ".vscode"}
CODE_EXTS = {".py", ".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx"}
DOC_EXTS = {".md"}
CONFIG_EXTS = {".yaml", ".yml", ".toml", ".ini", ".cfg"}

CLONE_TIMEOUT = 900          # 15 min hard ceiling on a single clone attempt
FETCH_TIMEOUT = 240          # refreshing an existing clone is best-effort

# github.com/owner/repo  (+ optional scheme, www, .git, /tree/<branch>, /blob/<path>, ?query, #frag)
_URL_RE = re.compile(
    r"^(?:https?://)?(?P<auth>[^/@\s]+@)?(?:www\.)?"
    r"(?P<host>github\.com|gitlab\.com|bitbucket\.org)/"
    r"(?P<owner>[^/\s]+)/(?P<repo>[^/\s#?]+?)(?:\.git)?(?:[/#?].*)?$",
    re.IGNORECASE,
)

# an embedded token is kept for cloning but ignored when comparing two urls
_AUTH_RE = re.compile(r"^(https?://)[^/@\s]+@", re.IGNORECASE)


def is_git_source(src):
    """True for anything we should clone rather than read off disk."""
    s = (src or "").strip()
    return (s.startswith(("http://", "https://", "git@"))
            or s.endswith(".git")
            or bool(_URL_RE.match(s)))


def normalize_git_url(url):
    """Canonicalise a pasted repo URL.

    Users paste all of these and every one of them used to be passed straight to
    `git clone`, where most of them fail:
        github.com/owner/repo                     (no scheme)
        https://github.com/owner/repo/            (trailing slash)
        https://github.com/owner/repo/tree/main   (copied from the branch view)
        https://github.com/owner/repo/blob/main/x.py
    All of the above normalise to https://github.com/owner/repo.git
    """
    u = (url or "").strip().rstrip("/")
    if u.startswith("git@"):
        return u
    m = _URL_RE.match(u)
    if m:
        return "https://%s%s/%s/%s.git" % (m.group("auth") or "", m.group("host").lower(),
                                           m.group("owner"), m.group("repo"))
    if u.startswith(("http://", "https://")) and not u.endswith(".git"):
        return u + ".git"
    return u


def name_from_url(url):
    m = _URL_RE.match((url or "").strip().rstrip("/"))
    if m:
        return m.group("repo")
    n = normalize_git_url(url).rstrip("/").split("/")[-1]
    n = n[:-4] if n.endswith(".git") else n
    return n or "repo"


def _rm(path):
    """Delete a tree even when git has left read-only objects in it.

    On Windows `.git/objects/**` is read-only, so a plain shutil.rmtree raises
    PermissionError and leaves a half-clone on disk. That leftover is what made
    the next connect silently reuse a broken folder.
    """
    if not os.path.exists(path):
        return
    def _fix(func, p, _exc):
        try:
            os.chmod(p, stat.S_IWRITE)
            func(p)
        except Exception:
            pass
    try:
        shutil.rmtree(path, onexc=_fix)          # py >= 3.12
    except TypeError:
        shutil.rmtree(path, onerror=_fix)        # py < 3.12
    except Exception:
        pass


def _git_env():
    env = dict(os.environ)
    env["GIT_TERMINAL_PROMPT"] = "0"   # fail fast instead of blocking on a login prompt
    env["GCM_INTERACTIVE"] = "never"   # don't pop the Windows credential dialog
    env["GIT_ASKPASS"] = "echo"
    env["GIT_CONFIG_NOSYSTEM"] = "0"
    return env


def _run_git(args, cwd=None, timeout=60):
    # core.longpaths: deep node_modules paths blow past Windows' 260-char limit
    return subprocess.run(["git", "-c", "core.longpaths=true"] + args, cwd=cwd,
                          capture_output=True, text=True, timeout=timeout, env=_git_env())


def _git(args, cwd):
    try:
        out = _run_git(args, cwd=cwd, timeout=15)
        if out.returncode == 0:
            return out.stdout.strip()
    except Exception:
        pass
    return ""


def _canon(u):
    """Comparison form of a url: scheme/case/token/.git-insensitive, so re-connecting
    the same repo with a different token doesn't look like a different repo."""
    u = normalize_git_url(u).lower().replace("git@github.com:", "https://github.com/")
    return _AUTH_RE.sub(r"\1", u).rstrip("/")


def _healthy_clone_of(dest, url):
    """A folder is only reusable if it is a real git repo, has objects, and points
    at THIS url. Anything else (half-clone, different repo, corrupt) is garbage."""
    if not os.path.isdir(os.path.join(dest, ".git")):
        return False
    if not _git(["rev-parse", "HEAD"], dest):
        return False
    origin = _git(["config", "--get", "remote.origin.url"], dest)
    return bool(origin) and _canon(origin) == _canon(url)


def _refresh(dest):
    """Pull the latest commits into an existing clone. Best-effort: a failure here
    (offline, rate-limited) just means we index the cached copy."""
    try:
        _run_git(["fetch", "--depth", "200", "--no-tags", "origin"], cwd=dest, timeout=FETCH_TIMEOUT)
        br = _git(["rev-parse", "--abbrev-ref", "HEAD"], dest)
        if br and br != "HEAD":
            _run_git(["reset", "--hard", "origin/" + br], cwd=dest, timeout=60)
    except Exception:
        pass


# errors where retrying is pointless — bail immediately with a useful message
_FATAL = ("authentication failed", "could not read username", "permission denied",
          "403", "not found", "404", "does not exist", "access denied",
          "invalid username or password", "support for password authentication was removed")


def _hint(err):
    low = (err or "").lower()
    if any(k in low for k in ("authentication", "could not read username", "permission denied", "403")):
        return ("Authentication failed. For a private repo, put a token in the URL "
                "(https://<token>@github.com/owner/repo.git) or connect a local clone.")
    if any(k in low for k in ("not found", "404", "repository does not exist")):
        return "Repository not found — check the URL and that you have access."
    if "filename too long" in low:
        return ("A path in the repo is too long for Windows. Run "
                "`git config --system core.longpaths true` and retry.")
    if any(k in low for k in ("could not resolve host", "unable to access", "timed out",
                              "connection", "network", "ssl", "tls", "eof")):
        return "Network error reaching the remote — check your connection/VPN, then retry."
    return (err or "unknown git error")[:400]


def _dest_for(repos, url, name):
    """Pick the folder this url lives in.

    Keeps the pretty name (repos/<repo>) in the normal case, but if that folder is
    already a *different* repo with the same basename (owner-a/utils vs owner-b/utils)
    it falls back to a url-keyed folder instead of silently indexing the wrong code.
    """
    primary = os.path.join(repos, name)
    if not os.path.isdir(primary):
        return primary
    if _healthy_clone_of(primary, url):
        return primary
    if os.path.isdir(os.path.join(primary, ".git")):
        key = hashlib.sha1(_canon(url).encode("utf-8")).hexdigest()[:8]
        return os.path.join(repos, "%s-%s" % (name, key))
    _rm(primary)          # not a git repo at all: leftover half-clone, reclaim the name
    return primary


def clone_or_local(source, data_dir):
    """Return an absolute path to a local working copy; clone git URLs on demand."""
    src = (source or "").strip()
    if is_git_source(src):
        url = normalize_git_url(src)
        repos = os.path.join(data_dir, "repos")
        os.makedirs(repos, exist_ok=True)
        dest = _dest_for(repos, url, name_from_url(url))

        if os.path.isdir(dest) and _healthy_clone_of(dest, url):
            _refresh(dest)                       # cached, but bring it up to date
            return os.path.abspath(dest)
        _rm(dest)                                # anything else on that path is junk

        # progressively cheaper strategies: a shallow single-branch clone is what we
        # want, but some remotes/proxies choke on it — fall back rather than fail.
        strategies = [
            ["--depth", "200", "--single-branch", "--no-tags"],
            ["--depth", "1", "--single-branch", "--no-tags"],
            [],                                  # last resort: plain full clone
        ]
        last = ""
        for args in strategies:
            for _attempt in (1, 2):              # one retry absorbs transient blips
                try:
                    r = _run_git(["clone"] + args + [url, dest], timeout=CLONE_TIMEOUT)
                except subprocess.TimeoutExpired:
                    _rm(dest)
                    raise RuntimeError(
                        "git clone timed out (15 min). The repo may be very large — "
                        "clone it locally and connect the folder path instead.")
                except FileNotFoundError:
                    raise RuntimeError("git is not installed or not on PATH.")
                if r.returncode == 0 and _healthy_clone_of(dest, url):
                    return os.path.abspath(dest)
                last = (r.stderr or r.stdout or "").strip()
                _rm(dest)                        # never leave a partial clone behind
                if any(k in last.lower() for k in _FATAL):
                    raise RuntimeError("git clone failed: " + _hint(last))
                time.sleep(1.5)
        raise RuntimeError("git clone failed: " + _hint(last))

    path = os.path.abspath(os.path.expanduser(src))
    if not os.path.isdir(path):
        raise FileNotFoundError("Not a directory: %s" % path)
    return path


def repo_meta(path, name=None):
    is_git = os.path.isdir(os.path.join(path, ".git"))
    commit = _git(["rev-parse", "HEAD"], path) if is_git else ""
    branch = _git(["rev-parse", "--abbrev-ref", "HEAD"], path) if is_git else ""
    n = _git(["rev-list", "--count", "HEAD"], path) if is_git else ""
    return RepoMeta(
        name=name or os.path.basename(path.rstrip("/\\")) or path,
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
    # for a URL the folder may be name-keyed; the display name comes from the url
    name = name_from_url(source) if is_git_source(source) else None
    meta = repo_meta(path, name=name)
    code, docs = list_files(path)
    return meta, code, docs
