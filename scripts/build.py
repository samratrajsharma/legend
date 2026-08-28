#!/usr/bin/env python3
"""Build the frontend and bundle it into the Legend wheel.

Runs `npm ci && npm run build` in app/frontend, then copies the output (app/frontend/dist)
to app/backend/web/ where the FastAPI app serves it. After this, `pip install .` (or
`python -m build`) produces a self-contained wheel that `uvx legend` can run.

Usage:
    python scripts/build.py

Note: stop any running `legend` server first — on Windows it holds web/assets open and this
script will refuse to package an incomplete UI rather than ship a blank page.
"""
from __future__ import annotations

import os
import shutil
import stat
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "app" / "frontend"
DIST = FRONTEND / "dist"
WEB = ROOT / "app" / "backend" / "web"


def run(cmd: list[str], cwd: Path) -> None:
    print("+", " ".join(cmd), f"(in {cwd})")
    subprocess.run(cmd, cwd=str(cwd), check=True, shell=(sys.platform == "win32"))


def _on_rm_error(func, path, _exc):
    # Clear the read-only bit and retry; handles Windows read-only files.
    try:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    except Exception:
        pass


def _clean_web() -> None:
    """Remove app/backend/web/ so we copy a clean bundle. If a file is locked (a running
    `legend` server holds web/assets open on Windows), fail loudly instead of leaving a
    half-emptied dir that would package into a broken wheel."""
    if not WEB.exists():
        return
    for _ in range(3):
        if sys.version_info >= (3, 12):
            shutil.rmtree(WEB, onexc=_on_rm_error)
        else:
            shutil.rmtree(WEB, onerror=_on_rm_error)
        if not WEB.exists():
            return
        time.sleep(0.5)
    if WEB.exists():
        print(f"\nerror: couldn't clear {WEB}", file=sys.stderr)
        print("A `legend` server is probably still running and holding these files open.",
              file=sys.stderr)
        print("Stop it (Ctrl+C in that window, or close it), then re-run this script.",
              file=sys.stderr)
        raise SystemExit(2)


def main() -> int:
    if not FRONTEND.is_dir():
        print(f"error: {FRONTEND} not found", file=sys.stderr)
        return 1
    run(["npm", "ci"], FRONTEND)
    run(["npm", "run", "build"], FRONTEND)
    if not DIST.is_dir() or not (DIST / "assets").is_dir():
        print(f"error: build produced no {DIST}\\assets", file=sys.stderr)
        return 1

    _clean_web()
    shutil.copytree(DIST, WEB)

    # Verify the JS/CSS bundle actually made it — this is the check that stops a blank-page wheel.
    assets = WEB / "assets"
    if not assets.is_dir() or not any(assets.iterdir()):
        print(f"error: no files under {assets} after copy — the UI bundle is missing", file=sys.stderr)
        return 1
    n_files = sum(1 for f in WEB.rglob("*") if f.is_file())
    n_assets = sum(1 for f in assets.iterdir() if f.is_file())
    print(f"\nBundled {DIST} -> {WEB}")
    print(f"  {n_files} files total, {n_assets} in web/assets/ (index.html + JS/CSS present)")
    print("Now build/install the wheel:")
    print("    pip install .        # local install; then `legend <repo>`")
    print("    python -m build      # produce dist/*.whl to publish for `uvx legend`")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
