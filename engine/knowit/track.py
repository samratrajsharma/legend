"""Phase 4 — Track. Snapshot a repo at commits and diff the structure over time:
changelog, architecture delta, and learning delta. Uses git (worktrees) — works on any
git repo; structural by default, with optional LLM narration."""
from __future__ import annotations
import hashlib
import json
import os
import subprocess

from .config import CONFIG

CODE_LANGS = ("python", "javascript", "typescript")


def _git(args, cwd, timeout=120):
    # safe.directory: git refuses to touch a repo it thinks is owned by another
    #   user and exits non-zero ("detected dubious ownership") - common on Windows
    #   for folders written by a service/other shell. Our clones are ours; trust them.
    # core.longpaths: deep paths blow past Windows' 260-char limit.
    env = dict(os.environ)
    env["GIT_TERMINAL_PROMPT"] = "0"        # never block on a credential prompt
    return subprocess.run(
        ["git", "-c", "safe.directory=*", "-c", "core.longpaths=true"] + args,
        cwd=cwd, capture_output=True, text=True, timeout=timeout, env=env)


def git_probe(path):
    """(is_git, reason). Never answers 'not a git repo' when it actually means
    'git blew up and I threw the reason away' - that is indistinguishable to the
    user and sends them chasing the wrong problem."""
    if not path or not os.path.isdir(path):
        return False, "The working copy is not on disk any more: %s" % (path or "(empty path)")
    dotgit = os.path.join(path, ".git")
    has_dotgit = os.path.isdir(dotgit) or os.path.isfile(dotgit)   # worktrees use a file
    try:
        r = _git(["rev-parse", "--is-inside-work-tree"], path, timeout=30)
    except FileNotFoundError:
        return has_dotgit, "git is not installed, or not on PATH for the backend process."
    except subprocess.TimeoutExpired:
        return has_dotgit, "git did not respond within 30s."
    except Exception as e:
        return has_dotgit, "%s: %s" % (type(e).__name__, e)
    if r.returncode == 0 and r.stdout.strip() == "true":
        return True, ""
    err = (r.stderr or r.stdout or "").strip()
    if has_dotgit:
        # there IS a .git here - so this is a git failure, not a missing repo
        return True, err or "git rev-parse failed with no output."
    return False, err or "No .git directory found in %s" % path


def is_git(path):
    return git_probe(path)[0]


def git_log(path, n=30):
    # No separate is_git() probe: `git log` on a non-repo just fails and yields no
    # lines, so the pre-check was one extra subprocess for the same result.
    r = _git(["log", f"-n{n}", "--pretty=format:%H|%h|%an|%ad|%s", "--date=short"], path)
    if r.returncode != 0:
        return []
    out = []
    for line in r.stdout.splitlines():
        parts = line.split("|", 4)
        if len(parts) == 5:
            out.append({"sha": parts[0], "short": parts[1], "author": parts[2],
                        "date": parts[3], "subject": parts[4]})
    return out


def fingerprint(idx, commit):
    files, symbols = {}, {}
    for p in idx.parsed_files:
        if p.language in CODE_LANGS:
            files[p.file] = p.loc
            for sym in p.symbols:
                key = f"{sym.file}::{sym.qualname}"
                symbols[key] = {
                    "file": sym.file, "kind": sym.kind, "complexity": sym.complexity,
                    "hash": hashlib.sha1((sym.code or "").encode("utf-8", "replace")).hexdigest()[:12],
                }
    imports = sorted({(s, d) for s, d, _ in idx.graph.all_edges("imports")})
    calls = sorted({(s, d) for s, d, _ in idx.graph.all_edges("calls")})
    return {"commit": commit, "files": files, "symbols": symbols,
            "imports": imports, "calls": calls}


def snapshot(source_path, commit, config=CONFIG):
    """Build a structural fingerprint of the repo at `commit` (cached as JSON)."""
    from .pipeline import build_index
    snaps = os.path.join(config.data_dir, "snapshots")
    os.makedirs(snaps, exist_ok=True)
    cache = os.path.join(snaps, f"{commit[:12]}.json")
    if os.path.exists(cache):
        try:
            return json.load(open(cache))
        except Exception:
            pass
    # Absolute path: `git worktree add` runs with cwd=source_path, but build_index(wt)
    # below runs from the process cwd. A relative data_dir (e.g. "./.cache") would make
    # git create the worktree under source_path while build_index looks for it under the
    # process cwd -> "Not a directory". abspath keeps both in agreement.
    wt = os.path.abspath(os.path.join(config.data_dir, "worktrees", commit[:12]))
    add = _git(["worktree", "add", "--detach", "--force", wt, commit], source_path)
    if add.returncode != 0:
        raise RuntimeError(f"git worktree failed: {add.stderr.strip()[:300]}")
    try:
        idx = build_index(wt, config, use_cache=False, register=False)
        fp = fingerprint(idx, commit)
    finally:
        _git(["worktree", "remove", "--force", wt], source_path)
    try:
        json.dump(fp, open(cache, "w"))
    except Exception:
        pass
    return fp


def diff(base, head):
    bf, hf = set(base["files"]), set(head["files"])
    bs, hs = base["symbols"], head["symbols"]
    bk, hk = set(bs), set(hs)
    modified = sorted(k for k in (bk & hk) if bs[k]["hash"] != hs[k]["hash"])
    complexity = [{"symbol": k.split("::")[-1], "file": bs[k]["file"],
                   "from": bs[k]["complexity"], "to": hs[k]["complexity"]}
                  for k in (bk & hk) if bs[k]["complexity"] != hs[k]["complexity"]]
    bi, hi = {tuple(x) for x in base["imports"]}, {tuple(x) for x in head["imports"]}
    return {
        "files_added": sorted(hf - bf), "files_removed": sorted(bf - hf),
        "symbols_added": sorted(hk - bk), "symbols_removed": sorted(bk - hk),
        "symbols_modified": modified,
        "imports_added": sorted(hi - bi), "imports_removed": sorted(bi - hi),
        "complexity_changes": complexity,
    }


def changelog_text(d):
    lines = []

    def section(title, items, fmt=lambda x: x):
        if items:
            lines.append(f"**{title}** ({len(items)})")
            lines.extend("  - " + fmt(i) for i in items[:25])

    section("Files added", d["files_added"])
    section("Files removed", d["files_removed"])
    section("Symbols added", [s.split("::")[-1] + f"  ({s.split('::')[0]})" for s in d["symbols_added"]])
    section("Symbols removed", [s.split("::")[-1] + f"  ({s.split('::')[0]})" for s in d["symbols_removed"]])
    section("Symbols modified", [s.split("::")[-1] + f"  ({s.split('::')[0]})" for s in d["symbols_modified"]])
    section("New imports", d["imports_added"], lambda e: f"{e[0]} → {e[1]}")
    section("Removed imports", d["imports_removed"], lambda e: f"{e[0]} → {e[1]}")
    section("Complexity changes",
            [f"{c['symbol']} ({c['file']}): {c['from']} → {c['to']}" for c in d["complexity_changes"]])
    return "\n".join(lines) if lines else "_No structural changes between these commits._"


def architecture_delta_dot(base, head):
    bi = {tuple(x) for x in base["imports"]}
    hi = {tuple(x) for x in head["imports"]}
    bf, hf = set(base["files"]), set(head["files"])
    nodes = bf | hf
    out = ["digraph G {", "  rankdir=LR;",
           '  node [shape=box style="rounded,filled" fontname="Helvetica" fontsize=10];']
    for f in sorted(nodes):
        if f in hf and f not in bf:
            out.append(f'  "{f}" [fillcolor="#DEF7E0" color="#2E8B57" label="{f} (new)"];')
        elif f in bf and f not in hf:
            out.append(f'  "{f}" [fillcolor="#FBE3E3" color="#C0392B" label="{f} (removed)"];')
        else:
            out.append(f'  "{f}" [fillcolor="#EAF1FB" color="#2E75B6"];')
    for s, d in sorted(hi - bi):
        out.append(f'  "{s}" -> "{d}" [color="#2E8B57" penwidth=2 label="+"];')
    for s, d in sorted(bi - hi):
        out.append(f'  "{s}" -> "{d}" [color="#C0392B" style=dashed label="-"];')
    for s, d in sorted(bi & hi):
        out.append(f'  "{s}" -> "{d}" [color="#bbbbbb"];')
    out.append('}')
    return "\n".join(out)


def learning_delta(d, explored):
    explored = set(explored)
    changed_files = set(d["files_added"]) | set(d["files_removed"])
    for key in d["symbols_modified"] + d["symbols_added"] + d["symbols_removed"]:
        changed_files.add(key.split("::")[0])
    return {
        "re_learn": sorted(explored & changed_files),     # you studied these and they changed
        "new_files": sorted(set(d["files_added"]) - explored),
        "removed_files": sorted(set(d["files_removed"]) & explored),
    }


def narrate_llm(d, model, extra=None):
    if not model:
        return None
    try:
        from . import llm
        prompt = ("Write a short, friendly changelog (5-8 bullets) describing how this "
                  "codebase changed, grouping related edits and noting likely intent.\n\n"
                  f"Structured diff:\n{json.dumps(d, indent=2)[:3500]}")
        r = llm._complete(model, [
            {"role": "system", "content": "You summarize code changes for engineers."},
            {"role": "user", "content": prompt}], extra=extra, temperature=0.3, timeout=60)
        return r["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return f"[LLM unavailable: {type(e).__name__}: {e}]"
