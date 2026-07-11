from __future__ import annotations
from .models import Retrieved


def _rrf(rank_lists, kconst=60):
    scores, sources, by_id = {}, {}, {}
    for name, hits in rank_lists:
        for rank, (chunk, _s) in enumerate(hits):
            scores[chunk.id] = scores.get(chunk.id, 0.0) + 1.0 / (kconst + rank + 1)
            sources.setdefault(chunk.id, set()).add(name)
            by_id[chunk.id] = chunk
    return scores, sources, by_id


def hybrid_search(query, lexical, dense, graph, chunks_by_node, k=6, expand=1):
    """Reciprocal-Rank-Fusion of lexical (BM25) + dense (semantic), then graph expansion."""
    cand = max(k * 2, 10)
    lists = [("lexical", lexical.search(query, cand))]
    if dense is not None:
        try:
            lists.append(("semantic", dense.search(query, cand)))
        except Exception:
            pass
    scores, sources, by_id = _rrf(lists)

    results = {}
    for cid, sc in scores.items():
        srcs = sources[cid]
        via = "both" if len(srcs) > 1 else next(iter(srcs))
        results[cid] = Retrieved(chunk=by_id[cid], score=float(sc), via=via)

    if expand and graph is not None and results:
        top = sorted(results.values(), key=lambda r: r.score, reverse=True)[:k]
        maxs = top[0].score if top else 1.0
        for r in top:
            node = r.chunk.node_id
            neigh = set()
            neigh.update(graph.successors(node, "calls"))
            neigh.update(graph.predecessors(node, "calls"))
            neigh.update(graph.successors(node, "contains"))
            neigh.update(graph.successors(node, "imports"))
            for nb in neigh:
                for ch in chunks_by_node.get(nb, []):
                    if ch.id not in results:
                        results[ch.id] = Retrieved(chunk=ch, score=maxs * 0.3, via="graph")
                    else:
                        results[ch.id].score += maxs * 0.05
    ranked = sorted(results.values(), key=lambda r: r.score, reverse=True)
    return ranked[: k + (k // 2 if expand else 0)]


def assemble_context(retrieved, max_blocks=8, max_chars=6000):
    blocks, total = [], 0
    for r in retrieved[:max_blocks]:
        c = r.chunk
        block = f"[{c.file}:{c.start_line}-{c.end_line} :: {c.name}]\n{c.text}"
        if total + len(block) > max_chars:
            if not blocks:
                # The single top-ranked chunk is larger than the whole budget. Breaking
                # here returned EMPTY context, so Ask answered with no code at all - on
                # exactly the symbol the user asked about (QA finding E-06). Include a
                # truncated head instead. The head + marker stays within max_chars, so a
                # realistic 7000-vs-6000 case is served while a budget too small to hold
                # even the marker still yields "" (degenerate, preserves old contract).
                mark = "\n... (truncated)"
                room = max_chars - len(mark)
                if room > 0:
                    blocks.append(block[:room].rstrip() + mark)
            break
        blocks.append(block)
        total += len(block)
    return "\n\n".join(blocks)
