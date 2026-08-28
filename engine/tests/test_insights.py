"""Tests for knowit.insights — repo insights, file summaries, language/API/DB maps."""
from __future__ import annotations

from knowit.insights import (api_map, db_map, file_summary, language_breakdown,
                             repo_insights)


def test_repo_insights_core_fields(idx):
    ins = repo_insights(idx)
    assert ins["entry_files"] == ["api.py", "train.py"]   # both have __main__
    assert ins["n_python"] == 6
    assert ins["n_symbols"] == 15
    assert ins["loc_total"] > 0
    assert isinstance(ins["avg_complexity"], (int, float))
    assert ins["hub_files"] and all(
        {"file", "imported_by", "imports", "degree"} <= set(h) for h in ins["hub_files"])


def test_repo_insights_dead_code_detection(idx):
    unused = {d["symbol"] for d in repo_insights(idx)["likely_unused"]}
    assert "cross_entropy" in unused          # defined, never called in-repo
    assert "create_app" not in unused         # lives in an entry file -> excluded


def test_file_summary(idx):
    fs = file_summary(idx, "model.py")
    assert fs["language"] == "python"
    assert "object detection" in fs["purpose"].lower()
    assert fs["imports"] == ["losses", "os"]
    assert "losses.py" in fs["internal_deps"]
    assert set(fs["dependents"]) == {"infer.py", "train.py"}
    assert fs["fan_in"] == 2 and fs["fan_out"] == 1
    symbols = {d["symbol"] for d in fs["defines"]}
    assert "Detector" in symbols
    # public_api: Detector.predict is called from other files
    used = {a["symbol"]: a["used_by"] for a in fs["public_api"]}
    assert "Detector.predict" in used
    assert "infer.py" in used["Detector.predict"]


def test_file_summary_missing_file_returns_none(idx):
    assert file_summary(idx, "does_not_exist.py") is None


def test_language_breakdown(idx):
    lb = {row["language"]: row for row in language_breakdown(idx)}
    assert lb["python"]["files"] == 6
    assert lb["markdown"]["files"] == 1
    assert lb["python"]["symbols"] == 15


def test_api_map_empty_for_sample(idx):
    assert api_map(idx) == []


def test_api_map_detects_routes(build_repo):
    repo = build_repo({"server.py": (
        "import flask\n"
        "app = flask.Flask(__name__)\n\n\n"
        '@app.get("/users")\n'
        "def users():\n    return []\n\n\n"
        '@app.route("/health")\n'
        "def health():\n    return 'ok'\n"
    )})
    routes = api_map(repo)
    by_path = {r["path"]: r["method"] for r in routes}
    assert by_path.get("/users") == "GET"
    assert by_path.get("/health") == "GET"   # bare @app.route defaults to GET in Flask


def test_db_map_detects_models_and_tables(build_repo):
    repo = build_repo({"models.py": (
        "class Base:\n    pass\n\n\n"
        "class User(Base):\n"
        '    __tablename__ = "users"\n'
        "    pass\n"
    )})
    dbm = db_map(repo)
    assert any(m["model"] == "User" for m in dbm)
    assert any(m["table"] == "users" for m in dbm)


# ── QA audit: api_map / db_map false positives ──────────────────────────────
def test_api_map_ignores_http_client_calls(build_repo):
    # axios.get('/x') is a CLIENT call, not a server route (audit).
    repo = build_repo({"server.js": (
        "const express = require('express'); const app = express();\n"
        "app.get('/users', h);\n"
        "const axios = require('axios');\n"
        "axios.get('/api/remote');\n"
        "axios.post('/api/login', d);\n"
    )})
    routes = {(r["method"], r["path"]) for r in api_map(repo)}
    assert ("GET", "/users") in routes
    assert ("GET", "/api/remote") not in routes
    assert ("POST", "/api/login") not in routes


def test_api_map_ignores_non_web_decorators(build_repo):
    # @cache.get("k") is a caching decorator, not a route.
    repo = build_repo({"svc.py": (
        "import flask\napp = flask.Flask(__name__)\n"
        "@cache.get('user_profile')\ndef cached():\n    pass\n"
        "@app.get('/real')\ndef real():\n    return []\n"
    )})
    paths = {r["path"] for r in api_map(repo)}
    assert "/real" in paths and "user_profile" not in paths


def test_db_map_ignores_markers_in_comments(build_repo):
    # A `mapped_column()` mentioned in a comment must not make a plain class an ORM model.
    repo = build_repo({"m.py": "class Note(Base):\n    # we used mapped_column() once\n    pass\n"})
    assert not any(m["model"] == "Note" for m in db_map(repo))
