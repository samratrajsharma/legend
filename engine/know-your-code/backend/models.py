"""SQLAlchemy models for the Know Your Code module.

Tables are prefixed `kyc_` and share the host's declarative `Base`, so the host's Alembic
autogeneration / our migration sees them. Every top-level table carries owner_id + org_id
for tenant isolation (always filter list queries by current_user.org_id).
"""
from __future__ import annotations
import uuid
from datetime import datetime

from sqlalchemy import String, Integer, Text, DateTime, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column

from core.db.base import Base  # host declarative Base (shared metadata)


def _uuid() -> str:
    return str(uuid.uuid4())


class KYCRepo(Base):
    __tablename__ = "kyc_repos"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    org_id: Mapped[str] = mapped_column(ForeignKey("orgs.id", ondelete="CASCADE"), index=True)
    source: Mapped[str] = mapped_column(String)               # 'git' | 'upload'
    source_url: Mapped[str | None] = mapped_column(String, nullable=True)
    name: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="indexing")  # indexing|ready|failed
    stats: Mapped[dict] = mapped_column(JSON, default=dict)   # {files, loc, langs, symbols}
    progress: Mapped[dict] = mapped_column(JSON, default=dict)  # {step, pct, eta}
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class KYCFile(Base):
    __tablename__ = "kyc_files"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    repo_id: Mapped[str] = mapped_column(ForeignKey("kyc_repos.id", ondelete="CASCADE"), index=True)
    path: Mapped[str] = mapped_column(String)
    language: Mapped[str] = mapped_column(String, default="other")
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    sha256: Mapped[str] = mapped_column(String, default="")


class KYCSymbol(Base):
    __tablename__ = "kyc_symbols"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    repo_id: Mapped[str] = mapped_column(ForeignKey("kyc_repos.id", ondelete="CASCADE"), index=True)
    file_id: Mapped[str] = mapped_column(ForeignKey("kyc_files.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String)                 # function|class|method
    name: Mapped[str] = mapped_column(String)
    signature: Mapped[str] = mapped_column(Text, default="")
    line_start: Mapped[int] = mapped_column(Integer, default=0)
    line_end: Mapped[int] = mapped_column(Integer, default=0)
    docstring: Mapped[str] = mapped_column(Text, default="")


class KYCQASession(Base):
    __tablename__ = "kyc_qa_sessions"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    repo_id: Mapped[str] = mapped_column(ForeignKey("kyc_repos.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class KYCQATurn(Base):
    __tablename__ = "kyc_qa_turns"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    session_id: Mapped[str] = mapped_column(ForeignKey("kyc_qa_sessions.id", ondelete="CASCADE"), index=True)
    question: Mapped[str] = mapped_column(Text)
    answer: Mapped[str] = mapped_column(Text, default="")
    sources: Mapped[list] = mapped_column(JSON, default=list)   # [{path, line_start, line_end, name}]
    tokens_used: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class KYCTour(Base):
    __tablename__ = "kyc_tours"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    repo_id: Mapped[str] = mapped_column(ForeignKey("kyc_repos.id", ondelete="CASCADE"), index=True)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    steps: Mapped[list] = mapped_column(JSON, default=list)     # [{title, description, file_path, line_range}]
