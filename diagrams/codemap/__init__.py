"""codemap — standalone architecture-map generator.

Re-exports the public API from codemap.py so `import codemap; codemap.build(...)` works both
in dev (codemap.py found directly on sys.path) and when installed as a package in the wheel.
"""
from .codemap import DEFAULT_EXT, build, render_html  # noqa: F401
