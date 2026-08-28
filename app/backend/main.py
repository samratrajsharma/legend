"""uvicorn launcher for the Know Your Code testbed backend."""
import logging
import os
from pathlib import Path

import uvicorn
from dotenv import load_dotenv

HERE = Path(__file__).resolve().parent
log = logging.getLogger("knowit.server")


def _data_dir() -> Path:
    v = (os.environ.get("KNOWIT_DATA_DIR") or "").strip() or str(HERE / ".cache")
    p = Path(v)
    if not p.is_absolute():
        p = (HERE / p).resolve()
    return p


if __name__ == "__main__":
    load_dotenv()
    # Structured logging, level via KNOWIT_LOG_LEVEL (default INFO). Configures the root
    # logger so the engine and request handlers log through the same handler (QA #29).
    logging.basicConfig(
        level=(os.environ.get("KNOWIT_LOG_LEVEL") or "INFO").upper(),
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    )

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

    # Bind 127.0.0.1 by default; KNOWIT_HOST=0.0.0.0 lets the Docker image expose it.
    host = (os.environ.get("KNOWIT_HOST") or "127.0.0.1").strip()
    kwargs = {"host": host, "port": 8100, "reload": reload_on}
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
            log.warning("KNOWIT_DATA_DIR is inside the reload watch path. It is excluded, "
                        "but if indexing still dies mid-run, run without KNOWIT_RELOAD or "
                        "move the data dir out.")

    log.info("data dir : %s", data)
    log.info("reload   : %s", "ON (KNOWIT_RELOAD=1)" if reload_on else "OFF")
    log.info("listening: http://%s:8100", host)
    uvicorn.run("app:app", **kwargs)
