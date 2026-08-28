"""`legend` command — the zero-install entry point.

    legend .                     index the current folder and open it
    legend https://github/x/y    clone + index a repo and open it
    legend                       just start the app (paste a repo in the browser)

Runs the FastAPI app (which serves the bundled UI) on 127.0.0.1:8100 and opens your browser.
No API key or account needed — structure, files, graph, search, and metrics all work offline;
only the AI "Ask"/explanations need a model you configure in Settings.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import threading
import time
import webbrowser
from pathlib import Path


def _repo_id(source: str) -> str:
    return hashlib.sha1(source.encode("utf-8")).hexdigest()[:12]


def main(argv=None) -> int:
    import sys
    _argv = list(sys.argv[1:] if argv is None else argv)
    # `legend mcp [...]` -> the MCP server (graph tools over stdio for coding agents)
    if _argv and _argv[0] == "mcp":
        from legend.mcp_server import main as _mcp_main
        return _mcp_main(_argv[1:])

    p = argparse.ArgumentParser(
        prog="legend",
        description="Legend — point it at a codebase and explore it in your browser. "
                    "Use `legend mcp` to serve graph tools to coding agents over MCP.",
    )
    p.add_argument("source", nargs="?", default="",
                   help="a git URL or a local folder to open (omit to just start the app)")
    p.add_argument("--host", default="127.0.0.1", help="bind host (default 127.0.0.1)")
    p.add_argument("--port", type=int, default=8100, help="bind port (default 8100)")
    p.add_argument("--data-dir", default=None,
                   help="where to cache indexes (default: ~/.legend/cache)")
    p.add_argument("--no-open", action="store_true", help="don't open the browser")
    args = p.parse_args(argv)

    # Cache indexes in a stable per-user dir by default (persists across runs).
    os.environ.setdefault(
        "LEGEND_DATA_DIR",
        args.data_dir or str(Path.home() / ".legend" / "cache"),
    )
    if args.data_dir:
        os.environ["LEGEND_DATA_DIR"] = args.data_dir

    # Let the app auto-connect the given repo on startup.
    source = (args.source or "").strip()
    if source == ".":
        source = str(Path.cwd())
    if source:
        os.environ["LEGEND_OPEN_REPO"] = source

    # TrustedHost only accepts an allow-listed Host header; make sure the chosen host:port is on it.
    os.environ["LEGEND_ALLOWED_HOSTS"] = ",".join({
        f"{args.host}:{args.port}", f"localhost:{args.port}", f"127.0.0.1:{args.port}",
        args.host, "localhost", "127.0.0.1",
    })

    url = f"http://{args.host if args.host != '0.0.0.0' else 'localhost'}:{args.port}"
    if not args.no_open:
        def _open():
            time.sleep(2.0)           # give uvicorn a moment to bind
            try:
                webbrowser.open(url)
            except Exception:
                pass
        threading.Thread(target=_open, daemon=True).start()

    import uvicorn
    print(f"\n  Legend is running at {url}")
    if source:
        print(f"  Indexing {source} … it will appear in the sidebar, then open when ready.")
    print("  Press Ctrl+C to stop.\n")
    uvicorn.run("legend_app.app:app", host=args.host, port=args.port, log_level="warning")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
