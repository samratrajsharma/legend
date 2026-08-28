"""Celery tasks for Legend — run on the host's existing Celery app. Long-running
work (cloning, parsing, embedding) lives here; routes only enqueue."""
from __future__ import annotations
import asyncio
import os
import uuid

from sqlalchemy import select, delete, update

from core.tasks.app import celery_app
from core.db.session import async_session_factory

from .models import KYCRepo, KYCFile, KYCSymbol
from .services import repo_loader as RL, parser as P, graph as G, indexer


def _workdir(repo_id: str) -> str:
    return os.path.join(os.environ.get("KYC_WORKDIR", "/data/kyc"), repo_id)


@celery_app.task(name="kyc.index_repo")
def index_repo_task(repo_id: str, upload_path: str | None = None):
    asyncio.run(_index_repo(repo_id, upload_path))


@celery_app.task(name="kyc.refresh_graph")
def refresh_graph_task(repo_id: str):
    asyncio.run(_refresh_graph(repo_id))


async def _set(db, repo_id, **fields):
    await db.execute(update(KYCRepo).where(KYCRepo.id == repo_id).values(**fields))
    await db.commit()


async def _index_repo(repo_id: str, upload_path=None):
    async with async_session_factory() as db:
        repo = (await db.execute(select(KYCRepo).where(KYCRepo.id == repo_id))).scalar_one_or_none()
        if not repo:
            return
        try:
            await _set(db, repo_id, status="indexing", progress={"step": "cloning", "pct": 5})
            root = RL.clone_or_extract(repo.source, repo.source_url, _workdir(repo_id), upload_path)
            await _set(db, repo_id, progress={"step": "walking", "pct": 20})
            files = RL.walk_files(root)

            await db.execute(delete(KYCSymbol).where(KYCSymbol.repo_id == repo_id))
            await db.execute(delete(KYCFile).where(KYCFile.repo_id == repo_id))
            await db.commit()

            parsed, langs, loc, all_syms, total = [], set(), 0, [], len(files)
            for i, f in enumerate(files):
                lang = f["language"]
                text = RL.read_text(f["abs"]) if lang in RL.CODE_LANGS else ""
                fobj = KYCFile(repo_id=repo_id, path=f["path"], language=lang,
                               size_bytes=f["size"], sha256=RL.sha256_of(text) if text else "")
                db.add(fobj)
                await db.flush()  # populate fobj.id
                if lang in RL.CODE_LANGS and text:
                    langs.add(lang)
                    loc += text.count("\n") + 1
                    pf = P.parse_file(f["path"], text, lang)
                    parsed.append(pf)
                    for s in pf["symbols"]:
                        db.add(KYCSymbol(repo_id=repo_id, file_id=fobj.id, kind=s["kind"],
                                         name=s["name"], signature=s["signature"],
                                         line_start=s["line_start"], line_end=s["line_end"],
                                         docstring=s["docstring"]))
                        all_syms.append({**s, "path": f["path"]})
                if i % 50 == 0:
                    await _set(db, repo_id, progress={"step": "parsing",
                                                      "pct": 20 + int(45 * i / max(total, 1))})
            await db.commit()

            embed_error = ""
            await _set(db, repo_id, progress={"step": "embedding", "pct": 75})
            try:
                indexer.index_symbols(repo_id, all_syms)
            except Exception as e:   # QA degrades gracefully if vectors fail; structure still works
                embed_error = str(e)[:200]

            arch = G.architecture_json(G.build_graph(parsed))
            stats = {"files": total, "loc": loc, "langs": sorted(langs),
                     "symbols": len(all_syms), "root": root, "architecture": arch}
            if embed_error:
                stats["embed_error"] = embed_error
            await _set(db, repo_id, status="ready", stats=stats, progress={"step": "done", "pct": 100})
        except Exception as e:
            await _set(db, repo_id, status="failed",
                       progress={"step": "error", "pct": 0, "error": str(e)[:300]})


async def _refresh_graph(repo_id: str):
    async with async_session_factory() as db:
        repo = (await db.execute(select(KYCRepo).where(KYCRepo.id == repo_id))).scalar_one_or_none()
        if not repo:
            return
        root = (repo.stats or {}).get("root")
        if not root or not os.path.isdir(root):
            return
        parsed = []
        for f in RL.walk_files(root):
            if f["language"] in RL.CODE_LANGS:
                parsed.append(P.parse_file(f["path"], RL.read_text(f["abs"]), f["language"]))
        arch = G.architecture_json(G.build_graph(parsed))
        stats = dict(repo.stats or {})
        stats["architecture"] = arch
        await _set(db, repo_id, stats=stats)
