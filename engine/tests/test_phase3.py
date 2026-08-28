"""Phase 3 regressions — retrieval budgeting, BM25 inverted index, duplicate_pairs
memoisation/exactness, and per-request config isolation. All offline (BM25, no LLM)."""
from __future__ import annotations

from collections import Counter

from knowit.index import BM25Retriever, tokenize
from knowit.retrieval import assemble_context
from knowit import techdebt


class _C:
    def __init__(self, cid, text, name=""):
        self.id, self.text, self.name = cid, text, name


# ── P3-1: token-aware context budget ────────────────────────────────────────
class _Chunk:
    def __init__(self, i, text):
        self.file, self.start_line, self.end_line = f"f{i}.py", 1, 10
        self.name, self.text = f"sym{i}", text


class _R:
    def __init__(self, chunk):
        self.chunk = chunk


def test_assemble_context_char_path_unchanged():
    # No model + explicit max_chars => legacy character budget (existing contract).
    rs = [_R(_Chunk(i, "x" * 100)) for i in range(5)]
    assert assemble_context([]) == ""
    assert assemble_context(rs, max_blocks=8, max_chars=5) == ""     # first block alone > 5
    ctx = assemble_context(rs, max_blocks=3, max_chars=6000)
    assert ctx and ctx.splitlines()[0].startswith("[")


def test_assemble_context_token_budget_caps():
    # With an explicit token budget the packer measures in tokens and stays within it.
    rs = [_R(_Chunk(i, "word " * 200)) for i in range(6)]
    small = assemble_context(rs, max_tokens=50, model="gpt-3.5-turbo")
    big = assemble_context(rs, max_tokens=100000, model="gpt-3.5-turbo")
    assert isinstance(small, str) and isinstance(big, str)
    assert len(big) >= len(small)            # a larger budget fits at least as much
    # a tiny budget still yields a (possibly truncated) string, never a crash
    assert isinstance(assemble_context(rs, max_tokens=1, model="gpt-3.5-turbo"), str)


# ── P3-2: BM25 inverted index gives identical results, faster ───────────────
def _brute_bm25(r, query, k):
    q = tokenize(query)
    scored = []
    for i, d in enumerate(r.docs):
        if not d:
            continue
        tf, dl, s = Counter(d), len(d), 0.0
        for t in q:
            f = tf.get(t)
            if not f:
                continue
            s += r.idf.get(t, 0.0) * (f * (r.k1 + 1)) / (
                f + r.k1 * (1 - r.b + r.b * dl / (r.avgdl or 1)))
        if s > 0:
            scored.append((i, s))
    scored.sort(key=lambda x: x[1], reverse=True)
    return [(r.chunks[i].id, round(float(s), 9)) for i, s in scored[:k]]


def test_bm25_inverted_matches_bruteforce():
    docs = [
        "focal loss addresses class imbalance in dense detection",
        "load an image from disk into a raw array",
        "normalize and resize an image into a tensor for the model",
        "the detector predicts boxes and class scores",
        "focal loss again for the detector imbalance case",
    ]
    r = BM25Retriever()
    r.index([_C(str(i), t) for i, t in enumerate(docs)])
    # postings/tf/dl are precomputed at index time (not per query)
    assert r.postings and len(r.tf) == len(docs) and len(r.dl) == len(docs)
    for qy in ["focal loss imbalance", "detector boxes", "image tensor", "nonexistent zzz", "the"]:
        got = [(c.id, round(float(s), 9)) for c, s in r.search(qy, k=8)]
        assert got == _brute_bm25(r, qy, 8), f"mismatch for {qy!r}"


def test_bm25_empty_query():
    r = BM25Retriever()
    r.index([_C("1", "anything here")])
    assert r.search("", k=5) == []


# ── P3-3: duplicate_pairs memoised + exact on a clone cluster ───────────────
_CLONE = "def {n}(a, b):\n    t = 0\n    for i in range(a):\n        t = t + b\n        if t > 10:\n            t = t - 1\n    return t\n"


def test_duplicate_pairs_memoised(build_repo):
    repo = build_repo({"m.py": _CLONE.format(n="f1") + "\n\n" + _CLONE.format(n="f2")})
    first = techdebt.duplicate_pairs(repo)
    assert first and first[0]["similarity"] >= 0.75
    assert techdebt.duplicate_pairs(repo) is first          # cached on idx.memo


def test_duplicate_pairs_detects_clone_cluster(build_repo):
    # A cluster whose members' shingles are all shared cluster-wide must still be found
    # (the inverted-index candidate step must not drop large buckets).
    src = "\n\n".join(_CLONE.format(n=f"c{i}") for i in range(12))
    repo = build_repo({"cluster.py": src})
    pairs = techdebt.duplicate_pairs(repo)
    assert len(pairs) >= 10 and all(p["similarity"] >= 0.75 for p in pairs)


# ── P3-4: a per-request model override never mutates the shared index config ─
def test_ask_does_not_mutate_config(idx):
    before = idx.config.llm_model
    try:
        idx.ask("what does the detector do", model="gpt-4o-mini", llm_kwargs={"k": 1})
    except Exception:
        pass                                                # LLM may be unavailable; irrelevant here
    assert idx.config.llm_model == before                   # override stayed local (#49)
