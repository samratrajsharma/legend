from __future__ import annotations
import math
import os
import re
from collections import Counter

_WORD = re.compile(r"[A-Za-z0-9]+")
_CAMEL = re.compile(r"[A-Z]+(?=[A-Z][a-z])|[A-Z][a-z]+|[a-z]+|[A-Z]+|\d+")


def _stem(t):
    if len(t) > 4 and t.endswith("ing"):
        return t[:-3]
    if len(t) > 4 and t.endswith("ed"):
        return t[:-2]
    if len(t) > 4 and t.endswith("es"):
        return t[:-2]
    if len(t) > 3 and t.endswith("s") and not t.endswith("ss"):
        return t[:-1]
    if len(t) > 4 and t.endswith("ly"):
        return t[:-2]
    return t


def tokenize(text):
    toks = []
    for raw in _WORD.findall(text or ""):
        for p in (_CAMEL.findall(raw) or [raw]):
            p = p.lower()
            if len(p) >= 2:
                toks.append(_stem(p))
    return toks


class BM25Retriever:
    """Pure-stdlib BM25. Always built (the lexical half of hybrid retrieval)."""
    name = "bm25"

    def __init__(self, k1=1.5, b=0.75):
        self.k1, self.b = k1, b
        self.chunks, self.docs, self.idf = [], [], {}
        self.avgdl, self.N = 0.0, 0

    def index(self, chunks):
        self.chunks = list(chunks)
        self.docs = [tokenize(c.text + " " + c.name) for c in self.chunks]
        self.N = len(self.docs)
        df = Counter()
        for d in self.docs:
            for t in set(d):
                df[t] += 1
        self.avgdl = (sum(len(d) for d in self.docs) / self.N) if self.N else 0.0
        self.idf = {t: math.log(1 + (self.N - n + 0.5) / (n + 0.5)) for t, n in df.items()}

    def search(self, query, k=6):
        q = tokenize(query)
        scored = []
        for i, d in enumerate(self.docs):
            if not d:
                continue
            tf = Counter(d)
            dl = len(d)
            s = 0.0
            for t in q:
                f = tf.get(t)
                if not f:
                    continue
                s += self.idf.get(t, 0.0) * (f * (self.k1 + 1)) / (
                    f + self.k1 * (1 - self.b + self.b * dl / (self.avgdl or 1)))
            if s > 0:
                scored.append((i, s))
        scored.sort(key=lambda x: x[1], reverse=True)
        return [(self.chunks[i], float(s)) for i, s in scored[:k]]


class ChromaRetriever:
    """Semantic retriever (chromadb local embeddings). Persists by signature and reuses
    an existing collection across launches instead of re-embedding."""
    name = "chroma"

    def __init__(self, data_dir, sig="default"):
        import chromadb
        os.makedirs(data_dir, exist_ok=True)
        self.client = chromadb.PersistentClient(path=os.path.join(data_dir, "chroma"))
        self.coll = f"knowit_{sig}"
        self.col = self.client.get_or_create_collection(self.coll)
        self.by_id = {}

    def index(self, chunks):
        self.by_id = {c.id: c for c in chunks}
        try:
            if len(chunks) and self.col.count() == len(chunks):
                return  # already embedded and persisted -> reuse
        except Exception:
            pass
        try:
            self.client.delete_collection(self.coll)
        except Exception:
            pass
        self.col = self.client.get_or_create_collection(self.coll)
        for i in range(0, len(chunks), 256):
            part = chunks[i:i + 256]
            self.col.add(ids=[c.id for c in part],
                         documents=[c.text for c in part],
                         metadatas=[{"file": c.file, "name": c.name,
                                     "node_id": c.node_id} for c in part])

    def search(self, query, k=6):
        res = self.col.query(query_texts=[query], n_results=k)
        ids = (res.get("ids") or [[]])[0]
        dists = (res.get("distances") or [[0.0] * len(ids)])[0]
        out = []
        for cid, dist in zip(ids, dists):
            c = self.by_id.get(cid)
            if c:
                out.append((c, 1.0 / (1.0 + float(dist))))
        return out
