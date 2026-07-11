"""uvicorn launcher for the Know Your Code testbed backend."""
import os
from pathlib import Path

import uvicorn
from dotenv import load_dotenv

HERE = Path(__file__).resolve().parent


def _data_dir() -> Path:
    v = (os.environ.get("KNOWIT_DATA_DIR") or "").strip() or str(HERE / ".cache")
    p = Path(v)
    if not p.is_absolute():
        p = (HERE / p).resolve()
    return p


if __name__ == "__main__":
    load_dotenv()

    # ── Auto-reload is OFF by default, and that is deliberate. ────────────────
    #
    # uvicorn's reloader watches this directory and restarts on any *.py change.
    # The data dir (default ./.cache) sits INSIDE it. So:
    #
    #   * connecting a Python repo clones thousands of .py files into
    #     .cache/repos/<repo>/ -> the watcher fires -> the server restarts
    #     MID-CLONE. git is killed, which exits non-zero having printed nothing,
    #     and surfaces as "git clone failed: unknown git error".
    #   * `git worktree add` during a Track snapshot does exactly the same.
    #   * every restart wipes _REPOS (it is in memory), so repos silently become
    #     "Unknown repo_id" and every tab goes blank.
    #
    # This is why indexing "sometimes worked": a small repo could finish before
    # the watcher noticed. A big one never could.
    #
    # Set KNOWIT_RELOAD=1 for hot reload while editing the backend; the data dir
    # is excluded from the watcher when you do.
    reload_on = (os.environ.get("KNOWIT_RELOAD") or "").strip().lower() in ("1", "true", "yes", "on")
    data = _data_dir()

    kwargs = {"host": "127.0.0.1", "port": 8100, "reload": reload_on}
    if reload_on:
        kwargs["reload_dirs"] = [str(HERE)]
        kwargs["reload_excludes"] = [
            str(data / "*"),
            str(data / "**" / "*"),
            "*.pkl", "*.sqlite3", "*.jsonl",
        ]
        inside = False
        try:
            data.relative_to(HERE)
            inside = True
        except ValueError:
            pass
        if inside:
            print("[knowit] WARNING: KNOWIT_DATA_DIR is inside the reload watch path.")
            print("[knowit]          It is excluded, but if indexing still dies mid-run,")
            print("[knowit]          run without KNOWIT_RELOAD or move the data dir out.")

    print("[knowit] data dir : %s" % data)
    print("[knowit] reload   : %s" % ("ON (KNOWIT_RELOAD=1)" if reload_on else "OFF"))
    print("[knowit] listening: http://127.0.0.1:8100")
    uvicorn.run("app:app", **kwargs)
