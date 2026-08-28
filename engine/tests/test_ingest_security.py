"""Security regression tests for the git-ingest hardening (audit criticals #2, #3, #52).

Pure-function tests: no network, no git invocation, no filesystem writes outside tmp.
These guard the transport allowlist (blocks ext:: RCE / file:// SSRF), the argument-
injection '--' separator, the path-traversal-safe hashed clone destination, and the
symlink-escape filter in list_files. A refactor that reopens any of these should turn
this file red.
"""
import os
import tempfile

import pytest

from legend import ingest


# ── transport allowlist (blocks ext:: RCE, file:// SSRF, arg injection) ──────────
@pytest.mark.parametrize("bad", [
    'ext::sh -c "id"',
    'ext::sh -c id x.git',
    'file:///etc/passwd',
    'file:///C:/Windows/System32',
    'fd::7/foo.git',
    '-u./payload',
    '--upload-pack=touch /tmp/x',
])
def test_validate_git_url_rejects_dangerous(bad):
    with pytest.raises(ValueError):
        ingest.validate_git_url(ingest.normalize_git_url(bad))


@pytest.mark.parametrize("ok", [
    "https://github.com/o/r.git",
    "http://example.com/o/r.git",
    "git@github.com:o/r.git",
    "ssh://git@host/o/r.git",
    "git://host/o/r.git",
])
def test_validate_git_url_accepts_allowed(ok):
    assert ingest.validate_git_url(ingest.normalize_git_url(ok))


# ── hardened git environment ─────────────────────────────────────────────────────
def test_git_env_sets_protection():
    env = ingest._git_env()
    assert env.get("GIT_ALLOW_PROTOCOL") == "http:https:ssh:git"
    assert env.get("GIT_TERMINAL_PROMPT") == "0"


# ── argument-injection '--' separator in the clone argv ──────────────────────────
def test_clone_argv_has_double_dash(monkeypatch):
    captured = {}

    class Fake:
        returncode, stdout, stderr = 0, "", ""

    def fake_run(argv, **kw):
        captured["argv"] = argv
        return Fake()

    monkeypatch.setattr(ingest.subprocess, "run", fake_run)
    # make _probe report the clone as usable so clone_or_local returns after one call
    monkeypatch.setattr(ingest, "_probe", lambda dest, url: ("ok", ""))
    ingest.clone_or_local("https://github.com/o/r.git", tempfile.mkdtemp())
    argv = captured["argv"]
    assert "clone" in argv
    assert "--" in argv and argv.index("--") < argv.index("https://github.com/o/r.git")


# ── path traversal: the clone destination can never escape the cache (#3) ────────
@pytest.mark.parametrize("evil", [
    "https://evil.io/a\\..\\..\\..\\..\\..\\Startup.git",
    "https://github.com/owner/..",
    "https://h/x/..%2f..%2f..",
])
def test_dest_for_is_contained(evil):
    repos = tempfile.mkdtemp()
    url = ingest.validate_git_url(ingest.normalize_git_url(evil))
    dest = ingest._dest_for(repos, url)
    real_dest, real_repos = os.path.realpath(dest), os.path.realpath(repos)
    assert real_dest != real_repos
    assert os.path.commonpath([real_dest, real_repos]) == real_repos
    # the folder name is a hex hash, never attacker text
    assert os.path.basename(dest).isalnum()


def test_dest_for_stable_and_distinct():
    repos = tempfile.mkdtemp()
    a = ingest._dest_for(repos, ingest.normalize_git_url("https://github.com/nv/PiD"))
    a2 = ingest._dest_for(repos, ingest.normalize_git_url("https://github.com/nv/PiD.git"))
    b = ingest._dest_for(repos, ingest.normalize_git_url("https://github.com/other/PiD"))
    assert a == a2 and a != b


# ── _rm refuses catastrophic paths ───────────────────────────────────────────────
def test_rm_refuses_root_and_home():
    for danger in (os.path.realpath(os.sep), os.path.expanduser("~")):
        with pytest.raises(RuntimeError):
            ingest._rm(danger)


# ── list_files skips symlinks that escape the repo root (#52) ────────────────────
def test_list_files_skips_escaping_symlink():
    repo = tempfile.mkdtemp()
    with open(os.path.join(repo, "real.py"), "w") as fh:
        fh.write("x = 1\n")
    secret = tempfile.mkdtemp()
    with open(os.path.join(secret, "secret.txt"), "w") as fh:
        fh.write("SECRET\n")
    try:
        os.symlink(os.path.join(secret, "secret.txt"), os.path.join(repo, "leak.py"))
    except OSError:
        pytest.skip("symlinks not permitted on this platform/user")
    code, docs = ingest.list_files(repo)
    names = [r for r, _ in code + docs]
    assert "real.py" in names
    assert "leak.py" not in names
