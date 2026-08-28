"""Know Your Code testbed backend — thin FastAPI wrapper over the existing
KnowIT engine. Full surface: every Streamlit tab has a REST endpoint here.
"""
from __future__ import annotations

import os
import sys
import hashlib
import json
import threading
import traceback
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from pydantic import BaseModel

# ── Engine import ────────────────────────────────────────────────
HERE = Path(__file__).resolve().parent
ENGINE_ROOT = (HERE / ".." / ".." / "engine").resolve()
if str(ENGINE_ROOT) not in sys.path:
    sys.path.insert(0, str(ENGINE_ROOT))

# ── codemap import (separate standalone tool) ────────────────────
# Lives at <repo-root>/know-your-code/diagrams/codemap/codemap.py. We add its folder to
# sys.path so the script's top-level functions are importable.
CODEMAP_ROOT = (HERE / ".." / ".." / "diagrams" / "codemap").resolve()
if str(CODEMAP_ROOT) not in sys.path:
    sys.path.insert(0, str(CODEMAP_ROOT))

from knowit.config import Config         # type: ignore
from knowit.pipeline import build_index  # type: ignore
from knowit.retrieval import assemble_context  # type: ignore
from knowit import (                      # type: ignore
    insights, providers as engine_providers,
    teach, track, techdebt, engmemory, media, research,
    impact, coverage, config_map, eval_harness, progress as kyc_progress,
)

# codemap is a single-file stdlib script — defensive import in case the folder
# isn't present. We also stash the load error so the diagnostic endpoint can
# show it to the frontend.
_CODEMAP_LOAD_ERROR: Optional[str] = None
try:
    import codemap as cmap  # type: ignore
    # Sanity-check the API we depend on.
    if not (hasattr(cmap, "build") and hasattr(cmap, "render_html")):
        raise ImportError(
            f"codemap loaded from {getattr(cmap, '__file__', '?')} but is missing build() / render_html()."
        )
    CODEMAP_AVAILABLE = True
except Exception as _cmap_err:
    cmap = None
    CODEMAP_AVAILABLE = False
    _CODEMAP_LOAD_ERROR = (
        f"{type(_cmap_err).__name__}: {_cmap_err}\n"
        f"Searched path: {CODEMAP_ROOT} (exists={CODEMAP_ROOT.exists()})"
    )


# ── App + CORS ───────────────────────────────────────────────────
app = FastAPI(title="Know Your Code (testbed)", version="0.2.0")
# Host allowlist. Binding to 127.0.0.1 does NOT stop DNS rebinding: after the attacker's
# domain re-resolves to 127.0.0.1, the browser treats http://attacker.tld:8100 as
# same-origin and CORS never engages. Rejecting any Host header that isn't our own closes
# that whole class - a rebinding request arrives with Host: attacker.tld and is refused
# with 400 before any handler runs. (Audit critical #4.)
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["localhost", "127.0.0.1", "localhost:8100", "127.0.0.1:8100"],
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5273", "http://127.0.0.1:5273"],
    allow_credentials=False, allow_methods=["*"], allow_headers=["*"],
)

# ── In-memory repo registry ──────────────────────────────────────
_REPOS: dict[str, dict[str, Any]] = {}
_REPOS_LOCK = threading.Lock()

def _repo_id(source: str) -> str:
    return hashlib.sha1(source.encode("utf-8")).hexdigest()[:12]

def _engine_config() -> Config:
    data_dir = os.environ.get("KNOWIT_DATA_DIR", str(HERE / ".cache"))
    cfg = Config(data_dir=data_dir)
    provider = os.environ.get("KNOWIT_LLM_PROVIDER", "").strip()
    model    = os.environ.get("KNOWIT_LLM_MODEL", "").strip()
    base_url = os.environ.get("KNOWIT_LLM_BASE_URL", "").strip()
    if provider and model:
        full, extra = engine_providers.resolve(provider, model, base_url)
        cfg.llm_model = full; cfg.llm_kwargs = extra
    elif model:
        cfg.llm_model = model
    return cfg


def _sync_llm_config(idx) -> None:
    """Bridge the live LLM config into an already-built index. idx.config is
    captured when the repo is connected, so configuring a model afterwards (via
    the Settings page) would not reach Ask / Explain without this. Mutates in
    place so the next idx.ask() / explain uses the current provider+model."""
    try:
        live = _engine_config()
        idx.config.llm_model = live.llm_model
        idx.config.llm_kwargs = getattr(live, "llm_kwargs", {}) or {}
    except Exception:
        pass


# ── Schemas ──────────────────────────────────────────────────────
class ConnectRepoRequest(BaseModel): source: str
class ConnectRepoResponse(BaseModel):
    repo_id: str; name: str; commit: str; status: str
class RepoListItem(BaseModel):
    repo_id: str; name: str; commit: str; source: str; status: str
class AskRequest(BaseModel):
    question: str
    provider: str = ""
    model: str = ""
    base_url: str = ""
class EngMemoryAddRequest(BaseModel):
    kind: str          # decisions | errors | memory
    title: str
    body: str = ""
class FlashcardReviewRequest(BaseModel):
    card_id: str
    correct: bool
class SnapshotDiffRequest(BaseModel):
    base_commit: str
    head_commit: str
class EvalRequest(BaseModel):
    questions: list[dict]   # [{question, expected_keywords}]


# ── Helpers ──────────────────────────────────────────────────────
def _registry_source(rid: str) -> str:
    """Recover a repo's source (url/path) from repos.json, the on-disk registry."""
    try:
        data_dir = Path(os.environ.get("KNOWIT_DATA_DIR", str(HERE / ".cache")))
        rp = data_dir / "repos.json"
        if rp.exists():
            for e in json.loads(rp.read_text(encoding="utf-8")):
                src = (e.get("source") or "").strip()
                if src and _repo_id(src) == rid:
                    return src
    except Exception:
        pass
    return ""


def _rehydrate(rid: str) -> bool:
    """_REPOS lives in memory, so a backend restart silently unloads every repo -
    while Home keeps listing them, because Home reads the disk registry. Every tab
    behind _require_idx then 404s on a repo the user can plainly see. Rebuild it in
    the background instead (the parse/graph/chunks are cached, so this is quick)."""
    src = _registry_source(rid)
    if not src:
        return False
    with _REPOS_LOCK:
        if rid in _REPOS:
            return True
        _REPOS[rid] = {"source": src, "status": "indexing", "error": None, "pct": 0,
                       "message": "Reloading after restart...", "name": _name_from_source(src)}
    threading.Thread(target=_index_worker, args=(rid, src, _engine_config()), daemon=True).start()
    return True


def _memo(idx, key, compute):
    """Cache a pure analysis on the (immutable) index so repeated requests/callers do
    not recompute it. New index object on reconnect/recapture => fresh cache, no stale."""
    m = getattr(idx, "memo", None)
    if m is None:
        return compute()
    if key not in m:
        m[key] = compute()
    return m[key]


def _require_idx(rid: str):
    with _REPOS_LOCK:
        slot = _REPOS.get(rid)
    if not slot:
        if _rehydrate(rid):
            raise HTTPException(409, "This repo was unloaded when the backend restarted. "
                                     "It is being reloaded now - retry in a moment.")
        raise HTTPException(404, "Unknown repo_id")
    if slot.get("status") != "ready":
        raise HTTPException(409, f"Repo not ready (status={slot.get('status')})")
    idx = slot.get("idx")
    if not idx: raise HTTPException(500, "Index missing")
    return idx


# ── Routes: health, repos ───────────────────────────────────────
@app.get("/healthz")
def health() -> dict:
    return {"status": "ok", "engine_root": str(ENGINE_ROOT)}

@app.get("/api/v1/llm-status")
def llm_status() -> dict:
    cfg = _engine_config()
    return {
        "configured": bool(cfg.llm_model),
        "model": cfg.llm_model or None,
        "provider": os.environ.get("KNOWIT_LLM_PROVIDER", "") or None,
    }


# ── LLM configuration (in-app AI settings space) ─────────────────
class LlmConfigRequest(BaseModel):
    provider: str = ""
    model: str = ""
    base_url: str = ""
    api_key: str = ""   # optional; stored under the provider's key env


class LlmTestRequest(BaseModel):
    provider: str = ""
    model: str = ""
    base_url: str = ""
    api_key: str = ""


def _persist_env(updates: dict) -> None:
    """Upsert KEY=VALUE lines in backend/.env so config survives a restart."""
    env_path = HERE / ".env"
    lines = env_path.read_text(encoding="utf-8").splitlines() if env_path.exists() else []
    seen, out = set(), []
    for ln in lines:
        parts = ln.split("=", 1)
        if len(parts) == 2 and parts[0].strip() in updates:
            k = parts[0].strip()
            out.append(f"{k}={updates[k]}")
            seen.add(k)
        else:
            out.append(ln)
    for k, v in updates.items():
        if k not in seen:
            out.append(f"{k}={v}")
    env_path.write_text("\n".join(out).rstrip("\n") + "\n", encoding="utf-8")


def _load_model_profiles() -> list:
    """Saved model roster (list of {provider, model, base_url}) from env JSON."""
    import json as _json
    raw = os.environ.get("KNOWIT_LLM_MODELS", "").strip()
    if not raw:
        return []
    try:
        data = _json.loads(raw)
        return [m for m in data if isinstance(m, dict)] if isinstance(data, list) else []
    except Exception:
        return []


class ModelsSaveRequest(BaseModel):
    models: list = []          # [{provider, model, base_url, api_key?}]
    default_index: int = 0


@app.get("/api/v1/llm/models")
def llm_models() -> dict:
    """The saved model roster, for the per-run pickers and Settings."""
    cur_p = os.environ.get("KNOWIT_LLM_PROVIDER", "")
    cur_m = os.environ.get("KNOWIT_LLM_MODEL", "")
    out = []
    for m in _load_model_profiles():
        prov = (m.get("provider") or ""); mod = (m.get("model") or ""); bu = (m.get("base_url") or "")
        full, _extra = engine_providers.resolve(prov, mod, bu)
        label = (engine_providers.PROVIDERS.get(prov, {}).get("label") or prov or "?")
        out.append({
            "provider": prov, "model": mod, "base_url": bu, "full": full,
            "label": f"{label}: {mod}",
            "key_present": engine_providers.key_present(prov),
            "is_default": (prov == cur_p and mod == cur_m),
        })
    return {"models": out, "default": {"provider": cur_p or None, "model": cur_m or None}}


@app.post("/api/v1/llm/models")
def llm_save_models(req: ModelsSaveRequest) -> dict:
    """Replace the saved roster; store any provided keys per provider; set the
    default (which also drives _engine_config and anything not overridden)."""
    import json as _json
    clean, updates = [], {}
    for m in req.models:
        prov = (m.get("provider") or "").strip()
        mod = (m.get("model") or "").strip()
        bu = (m.get("base_url") or "").strip()
        if not (prov and mod):
            continue
        key = (m.get("api_key") or "").strip()
        pr = engine_providers.PROVIDERS.get(prov)
        if key and pr and pr.get("key_env"):
            updates[pr["key_env"]] = key
        clean.append({"provider": prov, "model": mod, "base_url": bu})
    updates["KNOWIT_LLM_MODELS"] = _json.dumps(clean, separators=(",", ":"))
    di = req.default_index if 0 <= req.default_index < len(clean) else 0
    if clean:
        d = clean[di]
        updates["KNOWIT_LLM_PROVIDER"] = d["provider"]
        updates["KNOWIT_LLM_MODEL"] = d["model"]
        updates["KNOWIT_LLM_BASE_URL"] = d.get("base_url", "")
    else:
        updates["KNOWIT_LLM_PROVIDER"] = ""
        updates["KNOWIT_LLM_MODEL"] = ""
        updates["KNOWIT_LLM_BASE_URL"] = ""
    for k, v in updates.items():
        if v:
            os.environ[k] = v
        else:
            os.environ.pop(k, None)
    _persist_env(updates)
    return llm_models()


@app.get("/api/v1/llm/providers")
def llm_providers() -> dict:
    """The provider registry, for the settings UI to render."""
    out = []
    for pid in engine_providers.ORDER:
        if not pid:
            continue
        pr = engine_providers.PROVIDERS.get(pid)
        if not pr:
            continue
        out.append({
            "id": pid,
            "label": pr["label"],
            "models": pr.get("models", []),
            "needs_base_url": bool(pr.get("base_url")),
            "default_base": pr.get("default_base", ""),
            "key_env": pr.get("key_env", ""),
            "key_present": engine_providers.key_present(pid),
        })
    return {
        "providers": out,
        "current": {
            "provider": os.environ.get("KNOWIT_LLM_PROVIDER", "") or None,
            "model": os.environ.get("KNOWIT_LLM_MODEL", "") or None,
            "base_url": os.environ.get("KNOWIT_LLM_BASE_URL", "") or None,
        },
    }


@app.get("/api/v1/llm/ollama-models")
def llm_ollama_models(base_url: str = "") -> dict:
    """List models actually installed in a local Ollama (its /api/tags)."""
    import json as _json
    import urllib.request
    base = (base_url or os.environ.get("KNOWIT_LLM_BASE_URL", "")
            or "http://localhost:11434").rstrip("/")
    try:
        with urllib.request.urlopen(base + "/api/tags", timeout=5) as resp:
            data = _json.loads(resp.read().decode("utf-8"))
        models = [m.get("name") for m in data.get("models", []) if m.get("name")]
        return {"ok": True, "base_url": base, "models": models}
    except Exception as exc:
        return {"ok": False, "base_url": base, "models": [],
                "error": f"{type(exc).__name__}: {exc}"}


@app.post("/api/v1/llm/test")
def llm_test(req: LlmTestRequest) -> dict:
    """Run a tiny round-trip to verify a provider/model (or the current config)."""
    provider, model = req.provider.strip(), req.model.strip()
    if model:
        pr = engine_providers.PROVIDERS.get(provider)
        if req.api_key.strip() and pr and pr.get("key_env"):
            os.environ[pr["key_env"]] = req.api_key.strip()
        full, extra = engine_providers.resolve(provider, model, req.base_url.strip())
    else:
        cfg = _engine_config()
        full, extra = cfg.llm_model, getattr(cfg, "llm_kwargs", {})
    if not full:
        return {"ok": False, "message": "No model configured", "model": None}
    ok, msg = engine_providers.test_connection(full, extra)
    return {"ok": ok, "message": msg, "model": full}


@app.post("/api/v1/llm/config")
def llm_set_config(req: LlmConfigRequest) -> dict:
    """Set the LLM config: apply at runtime AND persist to .env, then test."""
    provider, model, base_url = req.provider.strip(), req.model.strip(), req.base_url.strip()
    updates = {
        "KNOWIT_LLM_PROVIDER": provider,
        "KNOWIT_LLM_MODEL": model,
        "KNOWIT_LLM_BASE_URL": base_url,
    }
    pr = engine_providers.PROVIDERS.get(provider)
    if req.api_key.strip() and pr and pr.get("key_env"):
        updates[pr["key_env"]] = req.api_key.strip()
    # apply to the live process (so _engine_config picks it up with no restart)
    for k, v in updates.items():
        if v:
            os.environ[k] = v
        else:
            os.environ.pop(k, None)
    _persist_env(updates)
    full, extra = engine_providers.resolve(provider, model, base_url)
    ok, msg = engine_providers.test_connection(full, extra) if full else (False, "no model configured")
    cfg = _engine_config()
    return {
        "configured": bool(cfg.llm_model),
        "model": cfg.llm_model or None,
        "provider": provider or None,
        "test_ok": ok,
        "test_message": msg,
    }

def _name_from_source(src: str) -> str:
    s = src.rstrip("/").replace("\\", "/")
    name = s.split("/")[-1]
    return name[:-4] if name.endswith(".git") else (name or src)


def _pct_for(msg: str, cur: int) -> int:
    """Map an engine progress message to a rough %, monotonic (never goes back)."""
    m = (msg or "").lower()
    pct = cur
    for key, val in (
        ("ingest", 8), ("clon", 8), ("loading cached", 28),
        ("parsing", 38), ("graph", 60), ("chunk", 72),
        ("retriever", 88), ("done", 100),
    ):
        if key in m:
            pct = max(pct, val)
    return pct


def _index_worker(rid: str, src: str, cfg: Config) -> None:
    """Build the index in a background thread, streaming progress into _REPOS so
    GET /repos/{rid}/status can report it. Failures are recorded (status=error)
    rather than lost, so the UI can show why."""
    def prog(msg):
        with _REPOS_LOCK:
            s = _REPOS.get(rid)
            if s is not None:
                s["message"] = msg
                s["pct"] = _pct_for(msg, int(s.get("pct", 0)))
    try:
        idx = build_index(src, cfg, progress=prog)
        with _REPOS_LOCK:
            _REPOS[rid] = {"meta": idx.meta, "source": src, "status": "ready",
                           "error": None, "idx": idx, "pct": 100, "message": "Done"}
    except Exception as e:
        with _REPOS_LOCK:
            _REPOS[rid] = {"source": src, "status": "error", "error": str(e),
                           "pct": 0, "message": "Failed", "name": _name_from_source(src)}


@app.post("/api/v1/repos", response_model=ConnectRepoResponse)
def connect_repo(req: ConnectRepoRequest) -> ConnectRepoResponse:
    """Kick off indexing in the background and return immediately with
    status=indexing; the frontend polls GET /repos/{rid}/status. A repo that's
    already ready is returned instantly; an in-flight one is not restarted."""
    src = req.source.strip()
    if not src:
        raise HTTPException(400, "Provide a folder path or git URL.")
    rid = _repo_id(src)
    cfg = _engine_config()
    # Friendly pre-check for local paths (git URLs are fetched by the engine).
    is_remote = src.startswith(("http://", "https://", "git@")) or src.endswith(".git")
    if not is_remote and not Path(src).is_dir():
        raise HTTPException(
            400,
            f"That folder doesn't exist or isn't a directory — it may have been moved "
            f"or deleted. Check the path: {src}",
        )
    with _REPOS_LOCK:
        slot = _REPOS.get(rid)
        if slot and slot.get("status") == "ready" and slot.get("idx") is not None:
            meta = slot["idx"].meta
            return ConnectRepoResponse(repo_id=rid, name=meta.name,
                                       commit=(meta.commit or "")[:12], status="ready")
        if slot and slot.get("status") == "indexing":
            return ConnectRepoResponse(repo_id=rid, name=slot.get("name") or _name_from_source(src),
                                       commit="", status="indexing")
        _REPOS[rid] = {"source": src, "status": "indexing", "error": None,
                       "pct": 0, "message": "Queued…", "name": _name_from_source(src)}
    threading.Thread(target=_index_worker, args=(rid, src, cfg), daemon=True).start()
    return ConnectRepoResponse(repo_id=rid, name=_name_from_source(src),
                               commit="", status="indexing")


@app.get("/api/v1/repos/{rid}/status")
def repo_status(rid: str) -> dict:
    """Poll target for the connect flow: {status: indexing|ready|error, pct, message, error}."""
    with _REPOS_LOCK:
        slot = _REPOS.get(rid)
        if not slot:
            raise HTTPException(404, "Unknown repo_id")
        meta = slot.get("meta")
        return {
            "repo_id": rid,
            "status": slot.get("status", "unknown"),
            "pct": int(slot.get("pct", 0)),
            "message": slot.get("message", ""),
            "error": slot.get("error"),
            "name": (meta.name if meta else slot.get("name", "")),
            "commit": ((meta.commit or "")[:12] if meta else ""),
        }

@app.get("/api/v1/repos", response_model=list[RepoListItem])
def list_repos() -> list[RepoListItem]:
    out: list[RepoListItem] = []
    with _REPOS_LOCK:
        for rid, slot in _REPOS.items():
            meta = slot.get("meta")
            out.append(RepoListItem(
                repo_id=rid, name=(meta.name if meta else rid),
                commit=((meta.commit or "")[:12] if meta else ""),
                source=slot.get("source", ""), status=slot.get("status", "unknown")))
    return out


@app.delete("/api/v1/repos/{rid}", status_code=204, response_model=None)
def disconnect_repo(rid: str):
    """Remove a repo from the in-memory list (e.g. after its folder is gone)."""
    with _REPOS_LOCK:
        _REPOS.pop(rid, None)


# ── Overview, Files ─────────────────────────────────────────────
@app.get("/api/v1/repos/{rid}/overview")
def repo_overview(rid: str) -> dict:
    idx = _require_idx(rid)
    return _memo(idx, "overview", lambda: {
        "stats": idx.stats(),
        "insights": insights.repo_insights(idx),
        "languages": insights.language_breakdown(idx),
        "config_surface": config_map.config_surface(idx),
    })

@app.get("/api/v1/repos/{rid}/files")
def repo_files(rid: str) -> dict:
    idx = _require_idx(rid)
    def build():
        by_lang: dict[str, list] = {}
        for p in idx.parsed_files:               # single pass instead of one scan per language
            by_lang.setdefault(p.language, []).append(p.file)
        return {"files": [p.file for p in idx.parsed_files], "by_language": by_lang}
    return _memo(idx, "files", build)

def _find_parsed_file(idx, file: str):
    """Find a ParsedFile tolerant of path-format differences. The codemap tool
    and the engine can format the same file differently (separators, a leading
    ./, or a repo-name prefix), so exact == matching misses. Fall back to a
    normalized match, then a unique suffix/basename match."""
    if not file:
        return None
    def norm(s: str) -> str:
        return s.replace("\\", "/").lstrip("./")
    target = norm(file)
    files = idx.parsed_files
    for p in files:                              # exact
        if p.file == file:
            return p
    for p in files:                              # normalized exact
        if norm(p.file) == target:
            return p
    cands = [p for p in files                    # suffix, either direction
             if norm(p.file).endswith("/" + target) or target.endswith("/" + norm(p.file))]
    if len(cands) == 1:
        return cands[0]
    base = target.rsplit("/", 1)[-1]             # unique basename
    bcands = [p for p in files if norm(p.file).rsplit("/", 1)[-1] == base]
    if len(bcands) == 1:
        return bcands[0]
    return None


@app.get("/api/v1/repos/{rid}/files/summary")
def file_summary(rid: str, file: str) -> dict:
    idx = _require_idx(rid)
    pf = _find_parsed_file(idx, file)
    fs = insights.file_summary(idx, pf.file) if pf else None
    if not fs: raise HTTPException(404, "File not found in index")
    return fs

@app.get("/api/v1/repos/{rid}/files/content")
def file_content(rid: str, file: str) -> dict:
    idx = _require_idx(rid)
    pf = _find_parsed_file(idx, file)
    if not pf: raise HTTPException(404, "File not found in index")
    return {"file": pf.file, "language": pf.language, "loc": pf.loc, "text": pf.text}


# ── README (raw markdown for the Overview viewer) ────────────────
@app.get("/api/v1/repos/{rid}/readme")
def repo_readme(rid: str) -> dict:
    """The repo's top-level README (case-insensitive), if any, as raw markdown."""
    idx = _require_idx(rid)
    def build():
        cands = []
        for p in idx.parsed_files:
            base = p.file.replace("\\", "/").rsplit("/", 1)[-1].lower()
            if base == "readme" or base == "readme.md" or base.startswith("readme."):
                depth = p.file.replace("\\", "/").count("/")
                cands.append((depth, len(p.file), p))
        if not cands:
            return {"found": False, "file": None, "text": ""}
        cands.sort(key=lambda x: (x[0], x[1]))
        pf = cands[0][2]
        return {"found": True, "file": pf.file, "text": pf.text or ""}
    return _memo(idx, "readme", build)


# ── Full report: md / docx / pdf ─────────────────────────────────
def _report_sections(idx) -> list:
    """Format-agnostic report of everything the system knows about the repo;
    rendered to markdown / docx / pdf by the helpers below."""
    ins = insights.repo_insights(idx)
    langs = insights.language_breakdown(idx)
    debt = techdebt.debt_summary(idx)
    routes = insights.api_map(idx)
    models = insights.db_map(idx)
    cfg = config_map.config_surface(idx)
    st = idx.stats()
    secs = [{"h": "Overview", "kv": [
        ("Repository", st.get("repo", "")),
        ("Commit", str(st.get("commit", ""))),
        ("Source path", getattr(idx.meta, "path", "")),
        ("Retriever", st.get("retriever", "")),
        ("Code files", st.get("files_parsed", 0)),
        ("Symbols", st.get("symbols", 0)),
        ("Chunks", st.get("chunks", 0)),
        ("Total LOC", ins.get("loc_total", 0)),
        ("Avg complexity / function", ins.get("avg_complexity", 0)),
        ("Parse errors", st.get("parse_errors", 0)),
    ]}]
    if langs:
        secs.append({"h": "Languages", "table": {
            "cols": ["Language", "Files", "LOC", "Symbols"],
            "rows": [[l["language"], l["files"], l["loc"], l["symbols"]]
                     for l in sorted(langs, key=lambda x: -x["loc"])]}})
    if ins.get("entry_files"):
        secs.append({"h": "Entry points", "bullets": list(ins["entry_files"])})
    if ins.get("hub_files"):
        secs.append({"h": "Hub files", "table": {
            "cols": ["File", "Imported by", "Imports"],
            "rows": [[h["file"], h["imported_by"], h["imports"]] for h in ins["hub_files"]]}})
    if ins.get("complex_symbols"):
        secs.append({"h": "Most complex symbols", "table": {
            "cols": ["Symbol", "File", "Complexity"],
            "rows": [[c["symbol"], c["file"], c["complexity"]] for c in ins["complex_symbols"]]}})
    if routes:
        secs.append({"h": "HTTP routes (%d)" % len(routes), "table": {
            "cols": ["Method", "Path", "File"],
            "rows": [[r["method"], r["path"], r["file"]] for r in routes[:100]]}})
    if models:
        secs.append({"h": "Data models (%d)" % len(models), "table": {
            "cols": ["Model", "Table", "File"],
            "rows": [[m.get("model", ""), m.get("table", ""), m.get("file", "")] for m in models[:100]]}})
    if cfg:
        secs.append({"h": "Configuration surface", "table": {
            "cols": ["Source", "Kind", "Keys"],
            "rows": [[c["source"], c["kind"], ", ".join(c["items"][:20])] for c in cfg]}})
    secs.append({"h": "Tech debt summary", "kv": [
        ("Likely dead code", len(debt["dead_code"])),
        ("Complexity hotspots", len(debt["complexity_hotspots"])),
        ("God files", len(debt["god_files"])),
        ("Near-duplicate pairs", len(debt["duplicates"])),
        ("Import cycles", len(debt["import_cycles"])),
        ("Undocumented symbols", len(debt["undocumented"])),
    ]})
    if debt["dead_code"]:
        secs.append({"h": "Likely dead code (%d)" % len(debt["dead_code"]), "table": {
            "cols": ["Symbol", "File"],
            "rows": [[d.get("symbol", ""), d.get("file", "")] for d in debt["dead_code"][:50]]}})
    if debt["import_cycles"]:
        secs.append({"h": "Import cycles (%d)" % len(debt["import_cycles"]),
                     "bullets": [" -> ".join(c) for c in debt["import_cycles"][:30]]})
    files = [p.file for p in idx.parsed_files]
    secs.append({"h": "Indexed files (%d)" % len(files), "bullets": files[:250]})
    return secs


def _report_md(name, secs) -> str:
    import datetime
    out = ["# Know Your Code - Report: %s" % name, "",
           "_Generated %s_" % datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), ""]
    for s in secs:
        out.append("## " + s["h"]); out.append("")
        if "kv" in s:
            for k, v in s["kv"]:
                out.append("- **%s:** %s" % (k, v))
            out.append("")
        if "bullets" in s:
            for b in s["bullets"]:
                out.append("- %s" % b)
            out.append("")
        if "table" in s:
            cols = s["table"]["cols"]
            out.append("| " + " | ".join(cols) + " |")
            out.append("| " + " | ".join(["---"] * len(cols)) + " |")
            for row in s["table"]["rows"]:
                out.append("| " + " | ".join(str(c).replace("|", "\\|") for c in row) + " |")
            out.append("")
    return "\n".join(out)


def _report_docx(name, secs) -> bytes:
    import io, datetime
    from docx import Document
    doc = Document()
    doc.add_heading("Know Your Code - Report: %s" % name, 0)
    doc.add_paragraph("Generated %s" % datetime.datetime.now().strftime("%Y-%m-%d %H:%M"))
    for s in secs:
        doc.add_heading(s["h"], level=1)
        if "kv" in s:
            for k, v in s["kv"]:
                p = doc.add_paragraph()
                p.add_run("%s: " % k).bold = True
                p.add_run(str(v))
        if "bullets" in s:
            for b in s["bullets"]:
                doc.add_paragraph(str(b), style="List Bullet")
        if "table" in s:
            cols = s["table"]["cols"]; rows = s["table"]["rows"]
            t = doc.add_table(rows=1, cols=len(cols))
            try:
                t.style = "Table Grid"
            except Exception:
                pass
            for i, c in enumerate(cols):
                t.rows[0].cells[i].text = str(c)
            for row in rows:
                cells = t.add_row().cells
                for i, c in enumerate(row):
                    cells[i].text = str(c)
    buf = io.BytesIO(); doc.save(buf); return buf.getvalue()


def _report_pdf(name, secs) -> bytes:
    import io, datetime, html as _html
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                     TableStyle, ListFlowable, ListItem)
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=18 * mm, bottomMargin=18 * mm,
                            leftMargin=16 * mm, rightMargin=16 * mm)
    ss = getSampleStyleSheet()
    def esc(x):
        return _html.escape(str(x))
    flow = [Paragraph("Know Your Code - Report: %s" % esc(name), ss["Title"]),
            Paragraph("Generated %s" % datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), ss["Normal"]),
            Spacer(1, 8)]
    for s in secs:
        flow.append(Spacer(1, 6))
        flow.append(Paragraph(esc(s["h"]), ss["Heading2"]))
        if "kv" in s:
            for k, v in s["kv"]:
                flow.append(Paragraph("<b>%s:</b> %s" % (esc(k), esc(v)), ss["Normal"]))
        if "bullets" in s:
            flow.append(ListFlowable(
                [ListItem(Paragraph(esc(b), ss["BodyText"])) for b in s["bullets"][:250]],
                bulletType="bullet"))
        if "table" in s:
            data = [[Paragraph(esc(c), ss["BodyText"]) for c in s["table"]["cols"]]]
            for row in s["table"]["rows"]:
                data.append([Paragraph(esc(c), ss["BodyText"]) for c in row])
            t = Table(data, repeatRows=1, hAlign="LEFT")
            t.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1DB954")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cccccc")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]))
            flow.append(t)
    doc.build(flow)
    return buf.getvalue()


@app.get("/api/v1/repos/{rid}/report")
def repo_report(rid: str, fmt: str = "md"):
    """Full analysis report as a download. fmt = md | docx | pdf."""
    import re as _re
    from fastapi.responses import Response
    idx = _require_idx(rid)
    fmt = (fmt or "md").lower().lstrip(".")
    name = idx.stats().get("repo", "repo") or "repo"
    safe = _re.sub(r"[^A-Za-z0-9_.-]+", "_", name) or "repo"
    secs = _report_sections(idx)
    if fmt == "md":
        data = _report_md(name, secs).encode("utf-8"); media = "text/markdown"; ext = "md"
    elif fmt == "docx":
        try:
            data = _report_docx(name, secs)
        except ImportError:
            raise HTTPException(503, "Word export needs python-docx (pip install python-docx).")
        media = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"; ext = "docx"
    elif fmt == "pdf":
        try:
            data = _report_pdf(name, secs)
        except ImportError:
            raise HTTPException(503, "PDF export needs reportlab (pip install reportlab).")
        media = "application/pdf"; ext = "pdf"
    else:
        raise HTTPException(400, "fmt must be md, docx, or pdf")
    return Response(content=data, media_type=media, headers={
        "Content-Disposition": 'attachment; filename="knowyourcode-report-%s.%s"' % (safe, ext)})


# ── Graph nodes ─────────────────────────────────────────────────
# Kept because the Intel/Impact subtab needs the list of symbols to populate
# its picker. The richer per-view diagram endpoints (mindmap / class / etc.)
# were removed — codemap is the only Diagrams visualization now.
@app.get("/api/v1/repos/{rid}/graph/nodes")
def graph_nodes(rid: str) -> dict:
    idx = _require_idx(rid)
    return {"nodes": list(idx.graph.nodes.keys())}


# ── codemap: rich interactive architecture HTML ──────────────────
# Per-repo cache so repeated views are instant. Re-generated on demand by
# adding ?refresh=1 to the URL.
_CODEMAP_CACHE: dict[str, dict[str, Any]] = {}


def _codemap_html_for(idx, embed_src: bool = True, max_src_kb: int = 200) -> dict:
    """Run codemap on the indexed repo path. Returns
    {html, stats: {files, loc, areas, edges, depth}}.
    Any exception surfaces as a 5xx with the actual cause."""
    if not CODEMAP_AVAILABLE:
        raise HTTPException(503, f"codemap is not loadable. {_CODEMAP_LOAD_ERROR}")
    repo_path = Path(idx.meta.path)
    if not repo_path.exists():
        raise HTTPException(404, f"Repo path no longer exists on disk: {repo_path}")
    try:
        exts = set(cmap.DEFAULT_EXT)
        mods, edges, depth = cmap.build(repo_path, exts, 0)
        html, stats = cmap.render_html(
            mods, edges, depth, idx.meta.name,
            embed=embed_src, max_src=max_src_kb * 1000,
        )
        n_files, loc, n_areas, n_edges = stats
        return {
            "html": html,
            "stats": {
                "files": n_files, "loc": loc,
                "areas": n_areas, "edges": n_edges, "depth": depth,
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        # Echo the actual exception so the frontend can show it.
        raise HTTPException(500, f"codemap build failed: {type(e).__name__}: {e}")


def _codemap_data_for(idx) -> dict:
    """Return the codemap data structure as plain JSON-able dict.

    We piggyback on render_html() (which already assembles the data exactly
    how the standalone HTML uses it) and pull the embedded JSON back out by
    regex. Cheaper than duplicating its logic, and keeps codemap unmodified.
    """
    import re, json as _json
    out = _codemap_html_for(idx, embed_src=True)
    html = out["html"]
    # The HTML contains a line: const DATA={...};\n
    m = re.search(r"const\s+DATA\s*=\s*(.*?);\s*\nconst\s+", html, re.DOTALL)
    if not m:
        raise HTTPException(500, "Could not extract codemap data from HTML")
    try:
        data = _json.loads(m.group(1).strip())
    except Exception as e:
        raise HTTPException(500, f"codemap data JSON-decode failed: {e}")
    data["stats"] = out["stats"]
    return data


@app.get("/api/v1/repos/{rid}/codemap/data")
def codemap_data(rid: str, refresh: int = 0) -> dict:
    """Structured codemap data for the React three-layer UI.
    Same data the standalone HTML uses internally — areas, edges, file index,
    embedded source, descriptions, palette."""
    idx = _require_idx(rid)
    cache_key = (rid, "data")
    if not refresh and cache_key in _CODEMAP_CACHE:
        return _CODEMAP_CACHE[cache_key]
    data = _codemap_data_for(idx)
    _CODEMAP_CACHE[cache_key] = data
    return data


# ── LLM-powered file explanation (for the deep-dive's "LLM" tab) ──
def _detailed_explain(pf, summary: dict, model: str, extra: dict) -> str:
    """Produce an in-depth, sectioned walkthrough of one file. Sends the full
    source plus structured facts (symbols+complexity, imports, depends-on,
    used-by) and asks for plain-text sections that render well with pre-wrap."""
    import json as _json
    import litellm  # type: ignore
    facts = _json.dumps(summary, indent=2)[:6000]
    src = pf.text or ""
    truncated = len(src) > 14000
    code = src[:14000]
    system = (
        "You are a senior software engineer writing a precise, in-depth walkthrough of ONE "
        "source file for a teammate new to this codebase. Ground every statement in the actual "
        "code provided; never invent behaviour. Be specific — name the real functions, "
        "classes, variables, routes and types. Write information-dense PLAIN TEXT with NO "
        "Markdown symbols (no #, *, or backticks). Use these ALL-CAPS section headers, each on "
        "its own line, with a blank line between sections:\n"
        "PURPOSE — what this file is for and its role in the wider system.\n"
        "KEY COMPONENTS — each class/function: what it does, its inputs and outputs, and any "
        "non-trivial logic (one short paragraph or a dashed bullet per item).\n"
        "HOW IT WORKS — the main control/data flow through the file, step by step.\n"
        "DEPENDENCIES & CONNECTIONS — what it imports and relies on, and what depends on it.\n"
        "NOTABLE DETAILS — edge cases, error handling, complexity hot-spots, assumptions, "
        "risks or TODOs worth knowing.\n"
        "Skip a section only if there is genuinely nothing to say about it."
    )
    user = (
        f"FILE: {pf.file}  ({getattr(pf, 'language', '?')}, {getattr(pf, 'loc', '?')} LOC)\n\n"
        f"STRUCTURED FACTS (symbols with complexity, imports, depends-on, used-by):\n{facts}\n\n"
        f"SOURCE{' (truncated)' if truncated else ''}:\n{code}"
    )
    r = litellm.completion(
        model=model,
        messages=[{"role": "system", "content": system},
                  {"role": "user", "content": user}],
        temperature=0.2, timeout=300, **(extra or {}),
    )
    return r["choices"][0]["message"]["content"].strip()


@app.get("/api/v1/repos/{rid}/files/explain")
def file_explain(rid: str, file: str, provider: str = "", model: str = "", base_url: str = "") -> dict:
    """LLM explanation of one file. Uses engine's llm.explain_file() which
    sends a curated summary + source excerpt to the configured provider."""
    idx = _require_idx(rid)
    _sync_llm_config(idx)
    pf = _find_parsed_file(idx, file)
    if not pf:
        raise HTTPException(404, "File not found in index")
    if model.strip():
        full, extra = engine_providers.resolve(provider.strip(), model.strip(), base_url.strip())
    else:
        full, extra = idx.config.llm_model, getattr(idx.config, "llm_kwargs", {})
    if not full:
        return {
            "explanation": None,
            "used_llm": False,
            "reason": "Open AI settings (the sidebar status pill, or the Settings page) to connect a local Ollama model or a provider key, then re-open this tab.",
        }
    summary = insights.file_summary(idx, pf.file) or {}
    try:
        text = _detailed_explain(pf, summary, full, extra)
    except Exception as e:
        raise HTTPException(500, f"LLM explain failed: {type(e).__name__}: {e}")
    return {"explanation": text, "used_llm": True, "reason": None}


# ── LLM-powered single-function / symbol explanation ─────────────
def _find_symbol(pf, symbol: str):
    """Find a Symbol in a ParsedFile by qualname or name (tolerant of Class.method vs method)."""
    if not pf or not symbol:
        return None
    for s in pf.symbols:
        if s.qualname == symbol or s.name == symbol:
            return s
    tail = symbol.rsplit(".", 1)[-1]
    for s in pf.symbols:
        if s.name == tail or s.qualname.rsplit(".", 1)[-1] == tail:
            return s
    return None


def _explain_function(sym, pf, callers, callees, model, extra) -> str:
    """Send one symbol's source + its callers/callees to the model for a structured explanation."""
    import litellm  # type: ignore
    rel = ", ".join(c["name"] for c in callers) or "(none found)"
    cel = ", ".join(c["name"] for c in callees) or "(none found)"
    system = (
        "You explain ONE function, method, or class precisely for a developer new to this "
        "codebase. Ground every statement in the provided code; never invent behaviour. Write "
        "dense PLAIN TEXT with NO Markdown symbols (no #, *, or backticks). Use these ALL-CAPS "
        "section headers, each on its own line, with a blank line between sections:\n"
        "WHAT IT DOES — one or two sentences.\n"
        "PARAMETERS — each argument and what it means (write 'None' if it takes none).\n"
        "RETURNS — what it returns (write 'None' if it returns nothing).\n"
        "HOW IT WORKS — the step-by-step logic, 3 to 6 short points.\n"
        "EDGE CASES & NOTES — error handling, assumptions, gotchas, complexity worth knowing."
    )
    user = (
        f"SYMBOL: {sym.qualname}  ({sym.kind} in {pf.file}, {pf.language}, "
        f"lines {sym.start_line}-{sym.end_line}, complexity {getattr(sym, 'complexity', '?')})\n"
        f"CALLED BY: {rel}\n"
        f"CALLS: {cel}\n\n"
        f"SOURCE:\n{(getattr(sym, 'code', '') or '')[:5000]}"
    )
    r = litellm.completion(
        model=model,
        messages=[{"role": "system", "content": system},
                  {"role": "user", "content": user}],
        temperature=0.2, timeout=120, **(extra or {}),
    )
    return r["choices"][0]["message"]["content"].strip()


@app.get("/api/v1/repos/{rid}/functions/explain")
def function_explain(rid: str, file: str, symbol: str,
                     provider: str = "", model: str = "", base_url: str = "") -> dict:
    """LLM explanation of ONE function/method/class + its callers/callees from the code graph.
    Returns the symbol's code + relations even with no model configured (explanation=None)."""
    idx = _require_idx(rid)
    _sync_llm_config(idx)
    pf = _find_parsed_file(idx, file)
    if not pf:
        raise HTTPException(404, "File not found in index")
    sym = _find_symbol(pf, symbol)
    if not sym:
        raise HTTPException(404, f"Symbol '{symbol}' not found in {pf.file}")

    def _short(node_id: str) -> dict:
        f, _, q = node_id.partition("::")
        return {"id": node_id, "file": f, "name": q or f}
    try:
        callers = [_short(n) for n in idx.graph.callers(sym.id)]
        callees = [_short(n) for n in idx.graph.callees(sym.id)]
    except Exception:
        callers, callees = [], []

    payload = {
        "file": pf.file, "symbol": sym.qualname, "name": sym.name, "kind": sym.kind,
        "language": pf.language, "line_start": sym.start_line, "line_end": sym.end_line,
        "complexity": getattr(sym, "complexity", None),
        "docstring": getattr(sym, "docstring", "") or "",
        "code": getattr(sym, "code", "") or "",
        "callers": callers, "callees": callees,
    }

    if model.strip():
        full, extra = engine_providers.resolve(provider.strip(), model.strip(), base_url.strip())
    else:
        full, extra = idx.config.llm_model, getattr(idx.config, "llm_kwargs", {})
    if not full:
        payload.update({"explanation": None, "used_llm": False,
                        "reason": "Open AI settings to connect a local Ollama model or a provider key, then re-open."})
        return payload
    try:
        payload["explanation"] = _explain_function(sym, pf, callers, callees, full, extra)
        payload["used_llm"] = True
        payload["reason"] = None
    except Exception as e:
        raise HTTPException(500, f"LLM explain failed: {type(e).__name__}: {e}")
    return payload


@app.get("/api/v1/codemap/status")
def codemap_status() -> dict:
    """Tiny diagnostic the frontend can show to surface install issues."""
    return {
        "available": CODEMAP_AVAILABLE,
        "load_error": _CODEMAP_LOAD_ERROR,
        "expected_path": str(CODEMAP_ROOT),
        "expected_path_exists": CODEMAP_ROOT.exists(),
        "codemap_module_file": getattr(cmap, "__file__", None) if cmap else None,
    }


@app.get("/api/v1/repos/{rid}/codemap/stats")
def codemap_stats(rid: str, refresh: int = 0) -> dict:
    """Return just the codemap stats — used by the page header without
    re-downloading the full HTML."""
    idx = _require_idx(rid)
    cached = _CODEMAP_CACHE.get(rid)
    if cached and not refresh:
        return {"stats": cached["stats"], "available": CODEMAP_AVAILABLE}
    out = _codemap_html_for(idx)
    _CODEMAP_CACHE[rid] = out
    return {"stats": out["stats"], "available": CODEMAP_AVAILABLE}


@app.get("/api/v1/repos/{rid}/codemap", response_class=HTMLResponse)
def codemap_html(rid: str, refresh: int = 0, embed: int = 1) -> HTMLResponse:
    """Stream the self-contained codemap HTML for embedding in an iframe."""
    idx = _require_idx(rid)
    cached = _CODEMAP_CACHE.get(rid)
    if cached and not refresh and bool(cached.get("embed_src", True)) == bool(embed):
        return HTMLResponse(content=cached["html"])
    out = _codemap_html_for(idx, embed_src=bool(embed))
    out["embed_src"] = bool(embed)
    _CODEMAP_CACHE[rid] = out
    return HTMLResponse(content=out["html"])


# ── API & DB ─────────────────────────────────────────────────────
@app.get("/api/v1/repos/{rid}/api-db")
def api_db(rid: str) -> dict:
    idx = _require_idx(rid)
    return {"routes": insights.api_map(idx), "models": insights.db_map(idx)}


# ── Ask ─────────────────────────────────────────────────────────
@app.post("/api/v1/repos/{rid}/ask")
def ask(rid: str, req: AskRequest) -> dict:
    idx = _require_idx(rid)
    if not req.question.strip(): raise HTTPException(400, "Question is empty")
    _sync_llm_config(idx)
    # Resolve the effective model into LOCALS and pass them through - never write the
    # per-request override back onto the shared idx.config (concurrent-ask safety, #49).
    model, kwargs = idx.config.llm_model, getattr(idx.config, "llm_kwargs", {}) or {}
    if req.model.strip():
        model, kwargs = engine_providers.resolve(req.provider.strip(), req.model.strip(), req.base_url.strip())
    if not model:
        return {
            "question": req.question, "answer": None, "used_llm": False, "needs_llm": True,
            "reason": "Answers are generated by an LLM. Open AI settings to connect a local Ollama model or a provider key, then ask again.",
            "sources": [],
        }
    try:
        res = idx.ask(req.question, model=model, llm_kwargs=kwargs)
    except Exception as e:
        raise HTTPException(500, f"Ask failed: {type(e).__name__}: {e}")
    return {
        "question": req.question, "answer": res.get("answer"),
        "used_llm": res.get("used_llm", False),
        "sources": [
            {"file": r.chunk.file, "start_line": r.chunk.start_line,
             "end_line": r.chunk.end_line, "name": r.chunk.name,
             "via": r.via, "score": round(r.score, 4), "text": r.chunk.text}
            for r in (res.get("retrieved") or [])
        ],
    }


# ── Ask (streaming, SSE) ─────────────────────────────────────────
@app.post("/api/v1/repos/{rid}/ask/stream")
def ask_stream(rid: str, req: AskRequest):
    """Server-Sent-Events variant of /ask: streams the answer token-by-token.
    Emits a `sources` event first, then `token` events, then `done` (or `error`)."""
    import json
    idx = _require_idx(rid)
    if not req.question.strip():
        raise HTTPException(400, "Question is empty")
    _sync_llm_config(idx)
    # per-request model resolved into locals; shared idx.config is never mutated (#49)
    model, kwargs = idx.config.llm_model, getattr(idx.config, "llm_kwargs", {}) or {}
    if req.model.strip():
        model, kwargs = engine_providers.resolve(req.provider.strip(), req.model.strip(), req.base_url.strip())

    def sse(event, data):
        return f"event: {event}\ndata: {json.dumps(data)}\n\n"

    if not model:
        def _need():
            yield sse("needs_llm", {"needs_llm": True,
                      "reason": "Answers are generated by an LLM. Open AI settings to connect a "
                                "local Ollama model or a provider key, then ask again."})
        return StreamingResponse(_need(), media_type="text/event-stream")

    def event_gen():
        try:
            retrieved, context, tokens = idx.ask_stream(req.question, model=model, llm_kwargs=kwargs)
            sources = [
                {"file": r.chunk.file, "start_line": r.chunk.start_line,
                 "end_line": r.chunk.end_line, "name": r.chunk.name,
                 "via": r.via, "score": round(r.score, 4), "text": r.chunk.text}
                for r in (retrieved or [])
            ]
            yield sse("sources", sources)
            got = False
            for tok in tokens:
                got = True
                yield sse("token", {"t": tok})
            yield sse("done", {"used_llm": got})
        except Exception as e:
            yield sse("error", {"error": f"{type(e).__name__}: {e}"})

    return StreamingResponse(
        event_gen(), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )


# ── Track ───────────────────────────────────────────────────────
@app.get("/api/v1/repos/{rid}/track/commits")
def track_commits(rid: str, n: int = 30) -> dict:
    idx = _require_idx(rid)
    path = idx.meta.path
    ok, reason = track.git_probe(path)
    # `reason` is surfaced verbatim: "not a git repository" was previously shown for
    # git-missing / dubious-ownership / vanished-path alike, which is a lie the user
    # cannot debug.
    if not ok:
        return {"is_git": False, "commits": [], "reason": reason, "path": path}
    return {"is_git": True, "commits": track.git_log(path, n=n), "reason": reason, "path": path}

@app.post("/api/v1/repos/{rid}/track/diff")
def track_diff(rid: str, req: SnapshotDiffRequest) -> dict:
    idx = _require_idx(rid)
    if not track.is_git(idx.meta.path):
        raise HTTPException(400, "Repo is not a git repository")
    try:
        base = track.snapshot(idx.meta.path, req.base_commit, idx.config)
        head = track.snapshot(idx.meta.path, req.head_commit, idx.config)
    except Exception as e:
        raise HTTPException(500, f"Snapshot failed: {e}")
    d = track.diff(base, head)
    return {
        "diff": d,
        "changelog": track.changelog_text(d),
        "arch_delta_dot": track.architecture_delta_dot(base, head),
    }


# ── Timeline: over-time change tracking (one living state + an append-only log) ──
def _track_dir(rid: str) -> Path:
    d = Path(os.environ.get("KNOWIT_DATA_DIR", str(HERE / ".cache"))) / "tracked" / rid
    d.mkdir(parents=True, exist_ok=True)
    return d


_SIG_SKIP = {".git", "node_modules", ".venv", "venv", "__pycache__", ".cache", "dist",
             "build", ".next", ".idea", ".mypy_cache", ".pytest_cache", ".ruff_cache", "target"}


def _folder_signature(root: str) -> str:
    """Cheap change-detector: hash of (relpath, mtime, size) over source files.
    Stat-only, prunes heavy/hidden dirs, bounded — no parsing, so it is safe to
    poll. A changed hash means 'something changed; a real capture is worth it'."""
    import hashlib
    import os as _os
    if not _os.path.isdir(root):
        return ""
    h = hashlib.sha1()
    count = 0
    for dirpath, dirnames, filenames in _os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in _SIG_SKIP and not d.startswith(".")]
        for fn in sorted(filenames):
            fp = _os.path.join(dirpath, fn)
            try:
                st = _os.stat(fp)
                h.update(_os.path.relpath(fp, root).encode("utf-8", "ignore"))
                h.update(str(int(st.st_mtime)).encode())
                h.update(str(st.st_size).encode())
                count += 1
            except Exception:
                pass
        if count > 20000:
            break
    return h.hexdigest()


def _git_history(path: str, n: int = 80):
    """Recent commits as structured events via the git CLI (no GitPython dep).
    Returns None if not a git repo / git unavailable."""
    import os as _os
    import subprocess
    if not _os.path.isdir(_os.path.join(path, ".git")):
        return None
    RS, FS = chr(30), chr(31)
    fmt = RS + "%H" + FS + "%aI" + FS + "%an" + FS + "%s"
    try:
        # --diff-merges=separate: plain `git log --name-status` prints NO files for a merge,
        # so the Timeline "Details" panel was blank for every merge (~40% of commits on an
        # active repo). "separate" lists the files a merge changed vs EACH parent, so even a
        # sync merge (empty vs its first parent) shows what it brought in from the other. It
        # emits one log entry per parent, so the parser below dedups by sha and unions files.
        # Fall back to the plain form on older git that lacks the flag.
        base = ["git", "-C", path, "log", "-n", str(n), "--name-status", "--no-renames",
                "--pretty=format:" + fmt]
        res = subprocess.run(base[:4] + ["--diff-merges=separate"] + base[4:],
                             capture_output=True, text=True, timeout=40)
        if res.returncode != 0:
            res = subprocess.run(base, capture_output=True, text=True, timeout=40)
    except Exception:
        return None
    if res.returncode != 0:
        return None
    # "separate" emits one entry PER PARENT for a merge, so accumulate by full sha and
    # union the files (first-seen status wins) - one timeline event per commit, never blank.
    by_sha, order = {}, []
    for chunk in res.stdout.split(RS):
        chunk = chunk.strip("\n")
        if not chunk:
            continue
        lines = chunk.split("\n")
        head = lines[0].split(FS)
        if len(head) < 4:
            continue
        sha, date, author, subject = head[0], head[1], head[2], head[3]
        if sha not in by_sha:
            by_sha[sha] = {"sha": sha[:10], "ts": date, "author": author, "subject": subject,
                           "files_added": [], "files_removed": [], "files_modified": [],
                           "_seen": set()}
            order.append(sha)
        ev = by_sha[sha]
        seen = ev["_seen"]
        for ln in lines[1:]:
            ln = ln.strip()
            if not ln or "\t" not in ln:
                continue
            status, _sep, fpath = ln.partition("\t")
            if fpath in seen:
                continue
            seen.add(fpath)
            s0 = status[:1]
            if s0 == "A":
                ev["files_added"].append(fpath)
            elif s0 == "D":
                ev["files_removed"].append(fpath)
            else:
                ev["files_modified"].append({"file": fpath})
    commits = []
    for k in order:
        ev = by_sha[k]
        ev.pop("_seen", None)
        commits.append(ev)
    return commits


def _structural_fingerprint(idx) -> dict:
    """Compact structural state of the folder right now (no source kept)."""
    files = {}
    for pf in idx.parsed_files:
        syms = {s.qualname: {"kind": s.kind, "cx": int(s.complexity)} for s in pf.symbols}
        files[pf.file] = {
            "loc": int(getattr(pf, "loc", 0) or 0),
            "lang": getattr(pf, "language", ""),
            "cx_total": sum(int(s.complexity) for s in pf.symbols),
            "symbols": syms,
        }
    ins = insights.repo_insights(idx)
    metrics = {
        "files": len(idx.parsed_files),
        "symbols": int(ins.get("n_symbols", 0) or 0),
        "loc": int(ins.get("loc_total", 0) or 0),
        "avg_complexity": float(ins.get("avg_complexity", 0) or 0),
        "dead_code": len(ins.get("likely_unused", []) or []),
    }
    return {"files": files, "metrics": metrics}


def _diff_fingerprints(old: dict, new: dict) -> dict:
    of, nf = old.get("files", {}), new.get("files", {})
    files_added = sorted([f for f in nf if f not in of])
    files_removed = sorted([f for f in of if f not in nf])
    files_modified, sym_added, sym_removed, sym_changed = [], [], [], []
    for f in nf:
        if f not in of:
            for q, v in nf[f]["symbols"].items():
                sym_added.append({"file": f, "symbol": q, "kind": v["kind"], "cx": v["cx"]})
            continue
        o, n = of[f], nf[f]
        if o == n:
            continue
        os_, ns_ = o.get("symbols", {}), n.get("symbols", {})
        for q in ns_:
            if q not in os_:
                sym_added.append({"file": f, "symbol": q, "kind": ns_[q]["kind"], "cx": ns_[q]["cx"]})
            elif ns_[q] != os_[q]:
                sym_changed.append({"file": f, "symbol": q, "cx": ns_[q]["cx"], "cx_was": os_[q]["cx"]})
        for q in os_:
            if q not in ns_:
                sym_removed.append({"file": f, "symbol": q})
        files_modified.append({"file": f, "loc": n["loc"], "loc_was": o["loc"],
                               "cx_total": n["cx_total"], "cx_was": o["cx_total"]})
    om, nm = old.get("metrics", {}), new.get("metrics", {})
    metric_delta = {k: {"now": nm.get(k), "was": om.get(k),
                        "delta": round((nm.get(k, 0) or 0) - (om.get(k, 0) or 0), 2)} for k in nm}
    changed = bool(files_added or files_removed or files_modified or sym_added or sym_removed or sym_changed)
    return {"changed": changed, "files_added": files_added, "files_removed": files_removed,
            "files_modified": files_modified, "symbols_added": sym_added,
            "symbols_removed": sym_removed, "symbols_changed": sym_changed,
            "metric_delta": metric_delta}


def _delta_summary(d: dict) -> str:
    """Templated, no-LLM one-liner describing the change."""
    parts = []
    if d["files_added"]:    parts.append(f"{len(d['files_added'])} file(s) added")
    if d["files_modified"]: parts.append(f"{len(d['files_modified'])} modified")
    if d["files_removed"]:  parts.append(f"{len(d['files_removed'])} removed")
    if d["symbols_added"]:  parts.append(f"{len(d['symbols_added'])} new symbol(s)")
    if d["symbols_removed"]: parts.append(f"{len(d['symbols_removed'])} symbol(s) removed")
    cxd = (d.get("metric_delta", {}).get("avg_complexity", {}) or {}).get("delta", 0)
    if cxd:
        parts.append(f"avg complexity {'+' if cxd > 0 else ''}{cxd}")
    return "; ".join(parts) or "No structural changes"


@app.post("/api/v1/repos/{rid}/track/capture")
def track_capture(rid: str) -> dict:
    """Re-scan the folder now, diff against the last recorded state, append a
    change event. Stores ONE current state + the event log (no snapshot pile)."""
    import json
    from datetime import datetime
    with _REPOS_LOCK:
        slot = _REPOS.get(rid)
    if not slot:
        raise HTTPException(404, "Unknown repo_id")
    source = slot.get("source")
    cfg = _engine_config()
    try:
        idx = build_index(source, cfg)
    except Exception as e:
        raise HTTPException(400, f"Could not re-scan {source!r}: {e}")
    with _REPOS_LOCK:
        if rid in _REPOS:
            _REPOS[rid]["idx"] = idx
            _REPOS[rid]["meta"] = idx.meta
            _REPOS[rid]["status"] = "ready"
    new_fp = _structural_fingerprint(idx)
    tdir = _track_dir(rid)
    state_p, events_p = tdir / "state.json", tdir / "events.jsonl"
    repo_path = getattr(idx.meta, "path", source)
    try:
        (tdir / "meta.json").write_text(json.dumps(
            {"rid": rid, "source": source, "name": getattr(idx.meta, "name", source),
             "path": repo_path}), encoding="utf-8")
        (tdir / "sig.txt").write_text(_folder_signature(repo_path), encoding="utf-8")
    except Exception:
        pass
    now = datetime.utcnow().isoformat() + "Z"
    if not state_p.exists():
        state_p.write_text(json.dumps(new_fp), encoding="utf-8")
        event = {"ts": now, "kind": "baseline", "summary": "Baseline captured",
                 "metrics": new_fp["metrics"]}
        with events_p.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(event) + "\n")
        return {"baseline": True, "changed": True, "event": event}
    old_fp = json.loads(state_p.read_text(encoding="utf-8"))
    delta = _diff_fingerprints(old_fp, new_fp)
    if not delta["changed"]:
        return {"changed": False, "event": None, "metrics": new_fp["metrics"]}
    event = {"ts": now, "kind": "change", "summary": _delta_summary(delta),
             "metrics": new_fp["metrics"], **delta}
    with events_p.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(event) + "\n")
    state_p.write_text(json.dumps(new_fp), encoding="utf-8")
    return {"changed": True, "event": event}


@app.get("/api/v1/repos/{rid}/track/timeline")
def track_timeline(rid: str, limit: int = 100) -> dict:
    import json
    events_p = _track_dir(rid) / "events.jsonl"
    events = []
    if events_p.exists():
        for line in events_p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                try:
                    events.append(json.loads(line))
                except Exception:
                    pass
    events.sort(key=lambda e: e.get("ts", ""), reverse=True)
    return {"events": events[:limit], "count": len(events)}


@app.get("/api/v1/repos/{rid}/track/trends")
def track_trends(rid: str) -> dict:
    import json
    events_p = _track_dir(rid) / "events.jsonl"
    series = []
    if events_p.exists():
        for line in events_p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                e = json.loads(line)
                if e.get("metrics"):
                    series.append({"ts": e.get("ts"), **e["metrics"]})
            except Exception:
                pass
    return {"series": series}


class NarrateRequest(BaseModel):
    ts: str
    provider: str = ""
    model: str = ""
    base_url: str = ""


@app.post("/api/v1/repos/{rid}/track/narrate")
def track_narrate(rid: str, req: NarrateRequest) -> dict:
    """Optional, cheap LLM narration of ONE change event (only the small delta is
    sent, never the whole repo). Cached per event so it is paid for once."""
    import json
    tdir = _track_dir(rid)
    events_p, narr_p = tdir / "events.jsonl", tdir / "narrations.json"
    ev = None
    if events_p.exists():
        for line in events_p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                e = json.loads(line)
            except Exception:
                continue
            if e.get("ts") == req.ts:
                ev = e
                break
    if ev is None:
        raise HTTPException(404, "Change event not found")
    cache = {}
    if narr_p.exists():
        try:
            cache = json.loads(narr_p.read_text(encoding="utf-8"))
        except Exception:
            cache = {}
    if req.ts in cache and not req.model.strip():
        return {"narration": cache[req.ts], "cached": True}
    if req.model.strip():
        full, extra = engine_providers.resolve(req.provider.strip(), req.model.strip(), req.base_url.strip())
    else:
        cfg = _engine_config()
        full, extra = cfg.llm_model, getattr(cfg, "llm_kwargs", {})
    if not full:
        return {"narration": None, "needs_llm": True,
                "reason": "Connect a model in AI settings to narrate changes."}
    parts = []
    if ev.get("files_added"):
        parts.append("Files added: " + ", ".join(ev["files_added"][:25]))
    if ev.get("files_removed"):
        parts.append("Files removed: " + ", ".join(ev["files_removed"][:25]))
    if ev.get("files_modified"):
        parts.append("Files modified: " + ", ".join(f.get("file", "") for f in ev["files_modified"][:25]))
    if ev.get("symbols_added"):
        parts.append("Symbols added: " + ", ".join(x.get("symbol", "") for x in ev["symbols_added"][:30]))
    if ev.get("symbols_removed"):
        parts.append("Symbols removed: " + ", ".join(x.get("symbol", "") for x in ev["symbols_removed"][:30]))
    if ev.get("symbols_changed"):
        parts.append("Symbols changed: " + ", ".join(x.get("symbol", "") for x in ev["symbols_changed"][:30]))
    md = ev.get("metric_delta", {})
    if md:
        parts.append("Metrics: " + ", ".join(
            f"{k} {v.get('was')}->{v.get('now')}" for k, v in md.items()))
    diff_text = "\n".join(parts) or "No structural change."
    system = (
        "You summarise what changed in a codebase between two captures, for a developer "
        "keeping track of fast, often AI-assisted edits. Ground every claim in the diff "
        "below; do not invent. 2-4 sentences, plain text, no Markdown. Say what likely "
        "happened and what is worth double-checking."
    )
    try:
        import litellm
        r = litellm.completion(
            model=full,
            messages=[{"role": "system", "content": system},
                      {"role": "user", "content": f"Folder change diff:\n{diff_text}"}],
            temperature=0.2, timeout=120, **(extra or {}),
        )
        text = r["choices"][0]["message"]["content"].strip()
    except Exception as e:
        raise HTTPException(500, f"Narration failed: {type(e).__name__}: {e}")
    cache[req.ts] = text
    try:
        narr_p.write_text(json.dumps(cache), encoding="utf-8")
    except Exception:
        pass
    return {"narration": text, "cached": False}


@app.get("/api/v1/workspace")
def workspace() -> dict:
    """All folders we have history for (persisted), with their latest change —
    the multi-folder home. Survives restarts (reads disk, not just memory)."""
    import json
    data_dir = Path(os.environ.get("KNOWIT_DATA_DIR", str(HERE / ".cache")))
    base = data_dir / "tracked"
    # Older tracked folders have no meta.json, so their name/source is unknown. The connect
    # registry (repos.json) records {source, name} for everything ever connected, and a folder
    # id is sha1(source)[:12] — so we can recover the real name by matching ids.
    registry: dict[str, dict] = {}
    try:
        rp = data_dir / "repos.json"
        if rp.exists():
            for e in json.loads(rp.read_text(encoding="utf-8")):
                src = (e.get("source") or "").strip()
                if src:
                    registry[_repo_id(src)] = {"name": e.get("name") or _name_from_source(src),
                                               "source": src}
    except Exception:
        registry = {}
    out = []
    if base.exists():
        for d in sorted(base.iterdir()):
            if not d.is_dir():
                continue
            rid = d.name
            meta = {}
            mp = d / "meta.json"
            if mp.exists():
                try:
                    meta = json.loads(mp.read_text(encoding="utf-8"))
                except Exception:
                    meta = {}
            events = []
            ep = d / "events.jsonl"
            if ep.exists():
                for line in ep.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if line:
                        try:
                            events.append(json.loads(line))
                        except Exception:
                            pass
            last = events[-1] if events else None
            with _REPOS_LOCK:
                connected = rid in _REPOS and _REPOS[rid].get("status") == "ready"
            fb = registry.get(rid, {})
            source = meta.get("source") or fb.get("source") or ""
            name = meta.get("name") or fb.get("name") or ""
            if not name or name == rid:
                name = _name_from_source(source) if source else rid
            out.append({
                "rid": rid,
                "name": name,
                "source": source,
                "captures": len(events),
                "last_ts": last.get("ts") if last else None,
                "last_summary": last.get("summary") if last else None,
                "metrics": last.get("metrics") if last else None,
                "connected": connected,
            })
    out.sort(key=lambda x: x.get("last_ts") or "", reverse=True)
    return {"folders": out}


@app.get("/api/v1/repos/{rid}/track/dirty")
def track_dirty(rid: str) -> dict:
    """Cheap check: has the folder changed since the last capture? (no parse)"""
    import json
    import os as _os
    tdir = _track_dir(rid)
    meta_p, sig_p = tdir / "meta.json", tdir / "sig.txt"
    path = ""
    if meta_p.exists():
        try:
            path = json.loads(meta_p.read_text(encoding="utf-8")).get("path", "")
        except Exception:
            path = ""
    if not path:
        with _REPOS_LOCK:
            slot = _REPOS.get(rid)
        if slot and slot.get("idx"):
            path = getattr(slot["idx"].meta, "path", "")
    if not path or not _os.path.isdir(path):
        return {"trackable": False, "dirty": False, "has_baseline": False}
    cur = _folder_signature(path)
    old = sig_p.read_text(encoding="utf-8").strip() if sig_p.exists() else ""
    return {"trackable": True, "has_baseline": bool(old), "dirty": bool(old) and cur != old}


@app.post("/api/v1/repos/{rid}/track/import-git")
def track_import_git(rid: str, n: int = 500) -> dict:
    """Rebuild the commit portion of the timeline from git.

    Commit events are a projection of git history, so we regenerate them from git (the
    source of truth) rather than append-and-dedup. That way improvements to how commits
    are read - notably giving merge commits their file list via --diff-merges - reach
    timelines that were first imported by an older version, which a dedup-by-sha append
    could never do. Capture/baseline events are NOT derivable from git, so they are
    preserved untouched, and any older commit beyond the fetch window is kept so history
    is never lost. The rewrite is atomic (temp + replace) so a torn write can't corrupt
    the log."""
    import json
    import os as _os
    tdir = _track_dir(rid)
    path = ""
    with _REPOS_LOCK:
        slot = _REPOS.get(rid)
    if slot and slot.get("idx"):
        path = getattr(slot["idx"].meta, "path", "")
    if not path:
        mp = tdir / "meta.json"
        if mp.exists():
            try:
                path = json.loads(mp.read_text(encoding="utf-8")).get("path", "")
            except Exception:
                path = ""
    if not path or not _os.path.isdir(path):
        return {"is_git": False, "imported": 0}
    commits = _git_history(path, n)
    if commits is None:
        return {"is_git": False, "imported": 0}

    events_p = tdir / "events.jsonl"
    preserved, old_commits = [], []          # non-commit events; prior commit events
    if events_p.exists():
        for line in events_p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                e = json.loads(line)
            except Exception:
                continue
            (old_commits if e.get("kind") == "commit" else preserved).append(e)

    fresh = [{
        "ts": c["ts"], "kind": "commit", "sha": c["sha"], "author": c["author"],
        "summary": c["subject"], "files_added": c["files_added"],
        "files_removed": c["files_removed"], "files_modified": c["files_modified"],
    } for c in commits]
    fresh_shas = {c["sha"] for c in commits}
    prev_shas = {e.get("sha") for e in old_commits}
    # keep any older commit the fetch window did not cover, so nothing is dropped
    kept = [e for e in old_commits if e.get("sha") not in fresh_shas]
    newly = sum(1 for sha in fresh_shas if sha not in prev_shas)

    tmp = events_p.with_name(events_p.name + ".tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        for e in preserved:
            fh.write(json.dumps(e) + "\n")
        for e in fresh:
            fh.write(json.dumps(e) + "\n")
        for e in kept:
            fh.write(json.dumps(e) + "\n")
    tmp.replace(events_p)
    return {"is_git": True, "imported": newly, "commits": len(fresh)}


# ── Intel: tech debt, decisions, errors, memory, impact, coverage ──
@app.get("/api/v1/repos/{rid}/intel/techdebt")
def intel_techdebt(rid: str) -> dict:
    idx = _require_idx(rid)
    return {
        "dead_code": techdebt.dead_code(idx),
        "undocumented": techdebt.undocumented(idx),
        "complexity_hotspots": techdebt.complexity_hotspots(idx),
        "god_files": techdebt.god_files(idx),
        "near_duplicates": techdebt.duplicate_pairs(idx),
        "import_cycles": techdebt.import_cycles(idx),
    }

@app.get("/api/v1/repos/{rid}/intel/memory")
def intel_memory(rid: str) -> dict:
    idx = _require_idx(rid)
    return {
        "decisions": engmemory.load(idx.config, idx.meta.name, "decisions"),
        "errors":    engmemory.load(idx.config, idx.meta.name, "errors"),
        "memory":    engmemory.load(idx.config, idx.meta.name, "memory"),
    }

@app.post("/api/v1/repos/{rid}/intel/memory/add")
def intel_memory_add(rid: str, req: EngMemoryAddRequest) -> dict:
    idx = _require_idx(rid)
    if req.kind not in ("decisions", "errors", "memory"):
        raise HTTPException(400, "kind must be decisions|errors|memory")
    entry = engmemory.add(idx.config, idx.meta.name, req.kind,
                           {"title": req.title, "body": req.body})
    return {"ok": True, "entry": entry}

@app.delete("/api/v1/repos/{rid}/intel/memory/{kind}/{eid}")
def intel_memory_del(rid: str, kind: str, eid: str) -> dict:
    idx = _require_idx(rid)
    if kind not in ("decisions", "errors", "memory"):
        raise HTTPException(400, "kind must be decisions|errors|memory")
    engmemory.delete(idx.config, idx.meta.name, kind, eid)
    return {"ok": True}

@app.get("/api/v1/repos/{rid}/intel/impact")
def intel_impact(rid: str, symbol: str) -> dict:
    idx = _require_idx(rid)
    try:
        # Engine API: impact_of(idx, node_id) — node_id is the full graph node id
        # (e.g. "model.py::Detector.predict"). The frontend already passes that.
        return impact.impact_of(idx, symbol)
    except Exception as e:
        raise HTTPException(500, f"Impact analysis failed: {type(e).__name__}: {e}")

@app.get("/api/v1/repos/{rid}/intel/coverage")
def intel_coverage(rid: str) -> dict:
    idx = _require_idx(rid)
    try:
        # Engine API: coverage_summary(idx) — returns test files, tested/total
        # counts, ratio, and a top-N untested-by-complexity list.
        return coverage.coverage_summary(idx)
    except Exception as e:
        raise HTTPException(500, f"Coverage analysis failed: {type(e).__name__}: {e}")
