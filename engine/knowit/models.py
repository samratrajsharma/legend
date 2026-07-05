from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Symbol:
    id: str                 # stable id: "<rel_path>::<qualname>"
    name: str
    qualname: str           # e.g. "Detector.predict"
    kind: str               # "function" | "method" | "class"
    file: str               # repo-relative path
    start_line: int
    end_line: int
    docstring: str = ""
    code: str = ""
    calls: list[str] = field(default_factory=list)   # callee base-names found in body
    parent: Optional[str] = None                      # enclosing class qualname
    complexity: int = 0                               # cyclomatic-ish (functions/methods)
    bases: list[str] = field(default_factory=list)    # base classes (inheritance)


@dataclass
class ParsedFile:
    file: str
    language: str
    imports: list[str] = field(default_factory=list)
    symbols: list[Symbol] = field(default_factory=list)
    loc: int = 0
    text: str = ""
    error: str = ""


@dataclass
class Chunk:
    id: str
    file: str
    kind: str               # "symbol" | "module" | "doc"
    name: str
    start_line: int
    end_line: int
    text: str
    node_id: str            # graph node this chunk derives from (load-bearing provenance)
    commit: str             # {graph node, commit} — enables Phase 4 deltas later
    symbol_id: Optional[str] = None


@dataclass
class RepoMeta:
    name: str
    path: str
    commit: str
    branch: str = ""
    is_git: bool = False
    n_commits: int = 0


@dataclass
class Retrieved:
    chunk: Chunk
    score: float
    via: str                # "semantic" | "graph" | "both"
