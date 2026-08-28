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


def _count_tokens(text, model):
    """Real token count for `model` when litellm can provide one; a ~4-chars/token
    estimate otherwise (litellm absent, or an unknown/local model)."""
    try:
        import litellm
        return int(litellm.token_counter(model=model or "gpt-3.5-turbo", text=text))
    except Exception:
        return max(1, len(text) // 4)


def _context_token_budget(model):
    """Half the model's context window, floored, leaving room for the system prompt,
    the question and the generated answer. Falls back to a conservative 8k window."""
    win = None
    try:
        import litellm
        win = litellm.get_max_tokens(model)
    except Exception:
        win = None
    if not win or win <= 0:
        win = 8192
    return max(512, int(win * 0.5))


def _truncate_to_tokens(text, token_budget, model):
    """Largest character prefix of `text` whose token count is within `token_budget`."""
    if token_budget <= 0:
        return ""
    if _count_tokens(text, model) <= token_budget:
        return text
    lo, hi = 0, len(text)
    while lo < hi:                                   # binary search on prefix length
        mid = (lo + hi + 1) // 2
        if _count_tokens(text[:mid], model) <= token_budget:
            lo = mid
        else:
            hi = mid - 1
    return text[:lo]


def assemble_context(retrieved, max_blocks=8, max_chars=6000, model=None, max_tokens=None):
    """Pack retrieved chunks into a context string within a budget.

    When a `model` (or explicit `max_tokens`) is given, the budget is measured in real
    tokens against that model's context window (QA #44) instead of the old fixed 6,000
    characters. With neither, it falls back to the character budget so existing callers
    and tests are unaffected."""
    token_mode = bool(model or max_tokens)
    if token_mode:
        budget = max_tokens or _context_token_budget(model)
        mark = "\n... (truncated)"
        blocks, total = [], 0
        for r in retrieved[:max_blocks]:
            c = r.chunk
            block = f"[{c.file}:{c.start_line}-{c.end_line} :: {c.name}]\n{c.text}"
            bl = _count_tokens(block, model)
            if total + bl > budget:
                if not blocks:                      # single oversized top chunk: keep a head
                    head = _truncate_to_tokens(block, budget - _count_tokens(mark, model), model)
                    if head:
                        blocks.append(head.rstrip() + mark)
                break
            blocks.append(block)
            total += bl
        return "\n\n".join(blocks)

    # ---- character-budget path (unchanged; default when no model is known) ----
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
