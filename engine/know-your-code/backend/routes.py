"""Know Your Code API. Mounted by the host at /api/v1; this router's prefix is
/know-your-code. Every query is scoped to current_user.org_id (tenant isolation), and any
work over ~2s is queued to Celery."""
from __future__ import annotations
import os
import shutil

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from core.db.session import get_db
from core.auth.dependencies import get_current_user, require_role
from core.models.user import User

from .models import KYCRepo, KYCFile, KYCSymbol, KYCQASession, KYCQATurn, KYCTour
from . import schemas as S
from .services import repo_loader as RL, qa as qa_service
from .services.indexer import drop_collection
from .tasks import index_repo_task

router = APIRouter(prefix="/know-your-code")


async def _get_repo(db: AsyncSession, repo_id: str, user: User) -> KYCRepo:
    repo = (await db.execute(
        select(KYCRepo).where(KYCRepo.id == repo_id, KYCRepo.org_id == user.org_id)
    )).scalar_one_or_none()
    if not repo:
        raise HTTPException(status_code=404, detail="repository not found")
    return repo


@router.post("/repos", response_model=S.RepoOut)
async def create_repo(body: S.RepoCreate, db: AsyncSession = Depends(get_db),
                      user: User = Depends(get_current_user)):
    if body.source == "git" and not body.source_url:
        raise HTTPException(status_code=400, detail="source_url is required for a git source")
    repo = KYCRepo(owner_id=user.id, org_id=user.org_id, source=body.source,
                   source_url=body.source_url, name=body.name, status="indexing",
                   stats={}, progress={"step": "queued", "pct": 0})
    db.add(repo)
    await db.commit()
    await db.refresh(repo)
    if body.source == "git":
        index_repo_task.delay(repo.id)          # upload waits for the zip (see /upload)
    return repo


@router.post("/repos/{repo_id}/upload", response_model=S.RepoOut)
async def upload_repo_zip(repo_id: str, file: UploadFile = File(...),
                          db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    repo = await _get_repo(db, repo_id, user)
    base = os.environ.get("KYC_WORKDIR", "/data/kyc")
    os.makedirs(base, exist_ok=True)
    zip_path = os.path.join(base, f"{repo_id}.zip")
    with open(zip_path, "wb") as fh:
        fh.write(await file.read())
    index_repo_task.delay(repo_id, zip_path)
    return repo


@router.get("/repos", response_model=list[S.RepoOut])
async def list_repos(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    rows = (await db.execute(
        select(KYCRepo).where(KYCRepo.org_id == user.org_id).order_by(KYCRepo.created_at.desc())
    )).scalars().all()
    return rows


@router.get("/repos/{repo_id}", response_model=S.RepoOut)
async def get_repo(repo_id: str, db: AsyncSession = Depends(get_db),
                   user: User = Depends(get_current_user)):
    return await _get_repo(db, repo_id, user)


@router.delete("/repos/{repo_id}")
async def delete_repo(repo_id: str, db: AsyncSession = Depends(get_db),
                      user: User = Depends(require_role("admin"))):
    repo = (await db.execute(
        select(KYCRepo).where(KYCRepo.id == repo_id, KYCRepo.org_id == user.org_id)
    )).scalar_one_or_none()
    if not repo:
        raise HTTPException(status_code=404, detail="repository not found")
    try:
        drop_collection(repo_id)
    except Exception:
        pass
    # remove the on-disk working copy so source isn't retained after delete (privacy)
    workdir = os.path.join(os.environ.get("KYC_WORKDIR", "/data/kyc"), repo_id)
    shutil.rmtree(workdir, ignore_errors=True)
    try:
        os.remove(workdir + ".zip")
    except OSError:
        pass
    await db.execute(delete(KYCRepo).where(KYCRepo.id == repo_id))
    await db.commit()
    return {"deleted": repo_id}


@router.get("/repos/{repo_id}/files", response_model=list[S.FileOut])
async def list_files(repo_id: str, db: AsyncSession = Depends(get_db),
                     user: User = Depends(get_current_user)):
    await _get_repo(db, repo_id, user)
    rows = (await db.execute(
        select(KYCFile).where(KYCFile.repo_id == repo_id).order_by(KYCFile.path)
    )).scalars().all()
    return rows


@router.get("/repos/{repo_id}/files/{file_id}/content", response_model=S.FileContentOut)
async def file_content(repo_id: str, file_id: str, db: AsyncSession = Depends(get_db),
                       user: User = Depends(get_current_user)):
    repo = await _get_repo(db, repo_id, user)
    f = (await db.execute(
        select(KYCFile).where(KYCFile.id == file_id, KYCFile.repo_id == repo_id)
    )).scalar_one_or_none()
    if not f:
        raise HTTPException(status_code=404, detail="file not found")
    content, root = "", (repo.stats or {}).get("root")
    if root:
        root_real = os.path.realpath(root)
        ab = os.path.realpath(os.path.join(root_real, f.path))   # resolves symlinks too
        if ab == root_real or ab.startswith(root_real + os.sep):  # path-traversal guard
            content = RL.read_text(ab)
    return S.FileContentOut(path=f.path, language=f.language, content=content)


@router.post("/repos/{repo_id}/qa", response_model=S.QAResponse)
async def ask_question(repo_id: str, body: S.QARequest, db: AsyncSession = Depends(get_db),
                       user: User = Depends(get_current_user)):
    repo = await _get_repo(db, repo_id, user)
    if repo.status != "ready":
        raise HTTPException(status_code=409, detail="repository is still indexing")
    session_id = body.session_id
    if session_id:
        ok = (await db.execute(select(KYCQASession).where(
            KYCQASession.id == session_id, KYCQASession.repo_id == repo_id,
            KYCQASession.user_id == user.id))).scalar_one_or_none()
        session_id = session_id if ok else None
    if not session_id:
        sess = KYCQASession(repo_id=repo_id, user_id=user.id)
        db.add(sess)
        await db.commit()
        await db.refresh(sess)
        session_id = sess.id
    result = qa_service.answer(repo_id, body.question, user=user)
    db.add(KYCQATurn(session_id=session_id, question=body.question, answer=result["answer"],
                     sources=result["sources"], tokens_used=result["tokens_used"]))
    await db.commit()
    return S.QAResponse(session_id=session_id, question=body.question, **result)


@router.get("/repos/{repo_id}/qa-history", response_model=list[S.QATurnOut])
async def qa_history(repo_id: str, db: AsyncSession = Depends(get_db),
                     user: User = Depends(get_current_user)):
    await _get_repo(db, repo_id, user)
    rows = (await db.execute(
        select(KYCQATurn).join(KYCQASession, KYCQATurn.session_id == KYCQASession.id)
        .where(KYCQASession.repo_id == repo_id, KYCQASession.user_id == user.id)
        .order_by(KYCQATurn.created_at.desc()).limit(100)
    )).scalars().all()
    return rows


@router.get("/repos/{repo_id}/architecture", response_model=S.ArchitectureOut)
async def architecture(repo_id: str, db: AsyncSession = Depends(get_db),
                       user: User = Depends(get_current_user)):
    repo = await _get_repo(db, repo_id, user)
    return (repo.stats or {}).get("architecture") or {"nodes": [], "edges": []}


@router.post("/repos/{repo_id}/tour", response_model=S.TourOut)
async def make_tour(repo_id: str, db: AsyncSession = Depends(get_db),
                    user: User = Depends(get_current_user)):
    repo = await _get_repo(db, repo_id, user)
    if repo.status != "ready":
        raise HTTPException(status_code=409, detail="repository is still indexing")
    syms = (await db.execute(select(KYCSymbol).where(KYCSymbol.repo_id == repo_id).limit(60))).scalars().all()
    files = (await db.execute(select(KYCFile).where(KYCFile.repo_id == repo_id))).scalars().all()
    steps = qa_service.generate_tour(qa_service.tour_context(repo.name, files, syms), user=user)
    tour = KYCTour(repo_id=repo_id, steps=steps)
    db.add(tour)
    await db.commit()
    await db.refresh(tour)
    return S.TourOut(id=tour.id, generated_at=tour.generated_at, steps=steps)


@router.get("/repos/{repo_id}/tour", response_model=S.TourOut)
async def get_tour(repo_id: str, db: AsyncSession = Depends(get_db),
                   user: User = Depends(get_current_user)):
    await _get_repo(db, repo_id, user)
    tour = (await db.execute(
        select(KYCTour).where(KYCTour.repo_id == repo_id)
        .order_by(KYCTour.generated_at.desc()).limit(1)
    )).scalar_one_or_none()
    if not tour:
        return S.TourOut(steps=[])
    return S.TourOut(id=tour.id, generated_at=tour.generated_at, steps=tour.steps)
