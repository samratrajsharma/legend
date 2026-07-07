from __future__ import annotations
import hashlib
import json
import os
import pickle
from collections import defaultdict

from .config import CONFIG
from .ingest import ingest
from .parsing import parse_file
from .graph import build_graph
from .chunking import make_chunks
from .index import BM25Retriever, ChromaRetriever
from .retrieval import hybrid_search, assemble_context
from .llm import synthesize


class RepoIndex:
    def __init__(self, meta, parsed_files, graph, chunks, lexical, dense, config):
        self.meta = meta
        self.parsed_files = parsed_files
        self.graph = graph
        self.chunks = chunks
        self.lexical = lexical
        self.dense = dense
        self.config = config
        self.chunks_by_id = {c.id: c for c in chunks}
        self.chunks_by_node = defaultdict(list)
        for c in chunks:
            self.chunks_by_node[c.node_id].append(c)

    def stats(self):
        s = self.graph.stats()
        return {
            "repo": self.meta.name, "commit": self.meta.commit[:12],
            "is_git": self.meta.is_git, "files_parsed": len(self.parsed_files),
            "python_files": sum(1 for p in self.parsed_files
                                if p.language in ("python", "javascript", "typescript")),
            "parse_errors": sum(1 for p in self.parsed_files if p.error),
            "symbols": s["node_types"].get("symbol", 0), "chunks": len(self.chunks),
            "graph_nodes": s["nodes"], "graph_edges": s["edges"],
            "edge_types": s["edge_types"],
            "retriever": "bm25 + chroma (hybrid RRF)" if self.dense is not None else "bm25",
        }

    def search(self, query):
        return hybrid_search(query, self.lexical, self.dense, self.graph,
                             self.chunks_by_node, k=self.config.top_k,
                             expand=self.config.graph_expand)

    def ask(self, query):
        retrieved = self.search(query)
        context = assemble_context(retrieved)
        answer, used = synthesize(query, context, self.config.llm_model,
                                  self.config.llm_kwargs)
        return {"question": query, "answer": answer, "used_llm": used,
                "retrieved": retrieved, "context": context}


# ---------------- cache + multi-repo registry ----------------
def _signature(meta, files):
    h = hashlib.sha1()
    h.update((meta.commit or "").encode())
    if meta.commit == "working-tree":
        for rel, ab in sorted(files):
            try:
                st = os.stat(ab)
                h.update(f"{rel}:{int(st.st_mtime)}:{st.st_size}".encode())
            except OSError:
                pass
    return h.hexdigest()[:16]


def _cache_file(data_dir, meta, sig):
    d = os.path.join(data_dir, "cache")
    os.makedirs(d, exist_ok=True)
    safe = "".join(ch if ch.isalnum() else "_" for ch in meta.name)[:40] or "repo"
    return os.path.join(d, f"{safe}_{sig}.pkl")


def _build_retrievers(chunks, backend, data_dir, sig):
    lexical = BM25Retriever()
    lexical.index(chunks)
    dense = None
    if backend in ("auto", "hybrid", "chroma"):
        try:
            dense = ChromaRetriever(data_dir, sig)
            dense.index(chunks)
        except Exception:
            if backend == "chroma":
                raise
            dense = None
    return lexical, dense


def record_repo(data_dir, source, meta):
    try:
        os.makedirs(data_dir, exist_ok=True)
        f = os.path.join(data_dir, "repos.json")
        reg = json.load(open(f)) if os.path.exists(f) else []
        reg = [e for e in reg if e.get("source") != source]
        reg.insert(0, {"source": source, "name": meta.name, "commit": meta.commit[:12]})
        json.dump(reg[:20], open(f, "w"), indent=2)
    except Exception:
        pass


def recent_repos(data_dir):
    try:
        f = os.path.join(data_dir, "repos.json")
        return json.load(open(f)) if os.path.exists(f) else []
    except Exception:
        return []


def build_index(source, config=CONFIG, progress=None, use_cache=None, register=True):
    def log(m):
        if progress:
            progress(m)

    if use_cache is None:
        use_cache = config.use_cache
    log("Ingesting repository ...")
    meta, code_files, doc_files = ingest(source, config.data_dir)
    files = code_files + doc_files
    sig = _signature(meta, files)
    cache = _cache_file(config.data_dir, meta, sig)

    parsed = graph = chunks = None
    if use_cache and os.path.exists(cache):
        try:
            log("Loading cached parse/graph/chunks ...")
            with open(cache, "rb") as fh:
                parsed, graph, chunks = pickle.load(fh)
        except Exception:
            parsed = graph = chunks = None

    if parsed is None:
        log(f"Parsing {len(code_files)} code + {len(doc_files)} doc files ...")
        parsed = [parse_file(rel, ab) for rel, ab in files]
        log("Building code graph ...")
        graph = build_graph(parsed)
        log("Chunking ...")
        chunks = make_chunks(parsed, meta.commit, config.chunk_max_lines)
        if use_cache:
            try:
                with open(cache, "wb") as fh:
                    pickle.dump((parsed, graph, chunks), fh)
            except Exception:
                pass

    log("Building retrievers ...")
    lexical, dense = _build_retrievers(chunks, config.embed_backend, config.data_dir, sig)
    if register:
        record_repo(config.data_dir, source, meta)
    log("Done.")
    return RepoIndex(meta, parsed, graph, chunks, lexical, dense, config)
