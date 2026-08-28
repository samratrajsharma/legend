"""`legend check` — fail CI when a change introduces a structural regression.

Compares the working tree against a base ref (default `main`) over the code graph and exits
non-zero if the change:
  * introduces a new import cycle,                       (blocking)
  * removes a public symbol (breaking the API surface), (blocking)
  * spikes a symbol's complexity past a threshold.      (warning; blocking with --strict)

    legend check --base main
    legend check --base origin/main --strict

Exit codes: 0 = clean, 1 = regression, 2 = error (e.g. base ref not found).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from .config import Config
from .pipeline import build_index
from . import track
from .mcp_server import _cycles_from_edges  # shared directed-cycle detection over import edges


def _symbol_name(key: str) -> str:
    # key is "<file>::<qualname>"; the symbol's own name is the last dotted segment
    return key.split("::")[-1].split(".")[-1]


def _is_public(key: str) -> bool:
    name = _symbol_name(key)
    file = key.split("::")[0].lower()
    if name.startswith("_"):
        return False
    if "test" in file or name.startswith("test_"):
        return False
    return True


def run_checks(idx, base: str, strict: bool = False, complexity_threshold: int = 5) -> dict:
    """Diff the current index against `base` and classify structural regressions."""
    base_fp = track.snapshot(idx.meta.path, base, idx.config)
    head_fp = track.fingerprint(idx, idx.meta.commit)
    delta = track.diff(base_fp, head_fp)

    base_cycles = {frozenset(c) for c in _cycles_from_edges(base_fp.get("imports", []))}
    head_cycles = {frozenset(c) for c in _cycles_from_edges(head_fp.get("imports", []))}
    cycles_introduced = sorted((sorted(c) for c in (head_cycles - base_cycles)), key=len)

    public_removed = sorted(k for k in delta.get("symbols_removed", []) if _is_public(k))

    complexity_regressions = sorted(
        ({"symbol": c["symbol"], "file": c["file"], "from": c["from"], "to": c["to"]}
         for c in delta.get("complexity_changes", [])
         if (c["to"] - c["from"]) >= complexity_threshold),
        key=lambda c: -(c["to"] - c["from"]),
    )

    blocking = bool(cycles_introduced) or bool(public_removed) or (strict and bool(complexity_regressions))
    return {
        "base": base, "head": head_fp.get("commit", "working-tree"),
        "cycles_introduced": cycles_introduced,
        "public_removed": public_removed,
        "complexity_regressions": complexity_regressions,
        "strict": strict,
        "failed": blocking,
    }


def _report(idx, res: dict) -> str:
    L = [f"legend check: {idx.meta.name}  base={res['base']}  head={res['head']}", ""]
    if res["cycles_introduced"]:
        L.append(f"FAIL  Import cycles introduced ({len(res['cycles_introduced'])}):")
        for c in res["cycles_introduced"]:
            L.append("        " + " -> ".join(c) + " -> " + c[0])
    if res["public_removed"]:
        L.append(f"FAIL  Public symbols removed ({len(res['public_removed'])}):")
        for k in res["public_removed"]:
            L.append(f"        {k}")
    if res["complexity_regressions"]:
        tag = "FAIL" if res["strict"] else "WARN"
        L.append(f"{tag}  Complexity regressions (+{'>='}{5}) ({len(res['complexity_regressions'])}):")
        for c in res["complexity_regressions"]:
            L.append(f"        {c['file']}::{c['symbol']}  {c['from']} -> {c['to']}")
    if not (res["cycles_introduced"] or res["public_removed"] or res["complexity_regressions"]):
        L.append(f"OK — no structural regressions vs {res['base']}.")
    L.append("")
    L.append("Result: " + ("FAIL" if res["failed"] else "PASS"))
    return "\n".join(L)


def main(argv=None) -> int:
    import argparse
    p = argparse.ArgumentParser(
        prog="legend check",
        description="Fail (exit non-zero) when a change introduces a structural regression vs a base ref.",
    )
    p.add_argument("--base", default="main", help="git ref to compare against (default: main)")
    p.add_argument("--repo", default=".", help="repo to check (default: current folder)")
    p.add_argument("--strict", action="store_true", help="also fail on complexity regressions")
    p.add_argument("--complexity-threshold", type=int, default=5,
                   help="min complexity increase to flag (default: 5)")
    p.add_argument("--data-dir", default=None, help="index cache dir (default: ~/.legend/cache)")
    args = p.parse_args(argv)

    repo = args.repo
    if repo != "." and "://" not in repo:
        repo = str(Path(repo).resolve())
    cfg = Config(
        embed_backend="bm25", llm_provider="", llm_model="",
        data_dir=args.data_dir or os.environ.get("LEGEND_DATA_DIR") or str(Path.home() / ".legend" / "cache"),
    )
    idx = build_index(repo, cfg, progress=lambda m: print(m, file=sys.stderr, flush=True), register=False)

    try:
        res = run_checks(idx, args.base, strict=args.strict, complexity_threshold=args.complexity_threshold)
    except Exception as e:  # noqa: BLE001 — base ref missing, not a git repo, etc.
        print(f"legend check: error — could not compare against {args.base!r}: {e}", file=sys.stderr)
        return 2

    print(_report(idx, res))
    return 1 if res["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
