"""Pydantic v2 request/response models for the Legend routes."""
from __future__ import annotations
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class RepoCreate(BaseModel):
    source: Literal["git", "upload"]
    source_url: Optional[str] = None
    name: str = Field(min_length=1)


class RepoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    source: str
    source_url: Optional[str] = None
    status: str
    stats: dict = {}
    progress: dict = {}
    created_at: datetime


class FileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    path: str
    language: str
    size_bytes: int


class FileContentOut(BaseModel):
    path: str
    language: str
    content: str


class SymbolOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    kind: str
    name: str
    signature: str
    line_start: int
    line_end: int
    docstring: str


class QARequest(BaseModel):
    question: str = Field(min_length=1)
    session_id: Optional[str] = None


class QASource(BaseModel):
    path: str
    line_start: int = 0
    line_end: int = 0
    name: Optional[str] = None


class QAResponse(BaseModel):
    session_id: str
    question: str
    answer: str
    sources: list[QASource] = []
    tokens_used: int = 0


class QATurnOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    question: str
    answer: str
    sources: list = []
    created_at: datetime


class GraphNode(BaseModel):
    id: str
    label: str
    kind: str                      # 'file' | 'symbol'
    language: Optional[str] = None


class GraphEdge(BaseModel):
    source: str
    target: str
    type: str                      # 'imports' | 'calls' | 'contains'


class ArchitectureOut(BaseModel):
    nodes: list[GraphNode] = []
    edges: list[GraphEdge] = []


class TourStep(BaseModel):
    title: str
    description: str
    file_path: Optional[str] = None
    line_range: Optional[str] = None


class TourOut(BaseModel):
    id: Optional[str] = None
    generated_at: Optional[datetime] = None
    steps: list[TourStep] = []
