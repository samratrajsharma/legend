"""RAG question-answering over a repo's symbols: embed the question with the host embedding
service, retrieve nearest symbols from Qdrant, assemble cited context, and answer with the
host LLM service (`core.llm.service.complete`). Host primitives only — no direct SDK calls."""
from __future__ import annotations

from core.embeddings.service import embed_texts
from core.vector import qdrant_client
from core.llm.service import complete

from .indexer import collection_name

SYSTEM = ("You are Legend, a codebase assistant inside Orchestraty. Answer the question "
          "USING ONLY the provided code context. Cite sources as (path:line). If the answer "
          "is not present in the context, say what is missing rather than guessing. Be "
          "concise and precise.")


def retrieve(repo_id: str, question: str, k: int = 8):
    qv = embed_texts([question])[0]
    hits = qdrant_client.search(collection_name=collection_name(repo_id),
                                query_vector=qv, limit=k)
    out = []
    for h in hits:
        p = getattr(h, "payload", None) or {}
        out.append({"path": p.get("path", ""), "name": p.get("name", ""),
                    "kind": p.get("kind", ""), "signature": p.get("signature", ""),
                    "docstring": p.get("docstring", ""),
                    "line_start": p.get("line_start", 0), "line_end": p.get("line_end", 0)})
    return out


def assemble_context(hits, max_chars: int = 6000) -> str:
    blocks, total = [], 0
    for h in hits:
        block = (f"[{h['path']}:{h['line_start']}-{h['line_end']} :: {h['name']}]\n"
                 f"{h['signature']}\n{h['docstring']}")
        if total + len(block) > max_chars:
            break
        blocks.append(block)
        total += len(block)
    return "\n\n".join(blocks)


def _extract(resp):
    """Defensive extraction of (text, tokens) from the host LLM response."""
    try:
        return resp["choices"][0]["message"]["content"], (resp.get("usage") or {}).get("total_tokens", 0)
    except Exception:
        return (resp if isinstance(resp, str) else str(resp)), 0


def answer(repo_id: str, question: str, user=None, model=None) -> dict:
    hits = retrieve(repo_id, question)
    context = assemble_context(hits)
    messages = [{"role": "system", "content": SYSTEM},
                {"role": "user", "content": f"Question: {question}\n\nCode context:\n{context}"}]
    user_keys = getattr(user, "llm_keys", None) if user is not None else None
    resp = complete(messages=messages, model=model, user_keys=user_keys, max_tokens=800)
    text, tokens = _extract(resp)
    sources = [{"path": h["path"], "line_start": h["line_start"], "line_end": h["line_end"],
                "name": h["name"]} for h in hits[:6]]
    return {"answer": text.strip(), "sources": sources, "tokens_used": tokens}


# ---------------- onboarding tour (LLM) ----------------
def tour_context(repo_name, files, symbols):
    fl = ", ".join(getattr(f, "path", "") for f in files[:40])
    sy = "\n".join(f"{getattr(s,'kind','')} {getattr(s,'name','')} "
                   f"({(getattr(s,'signature','') or '')[:60]}) @ {getattr(s,'line_start',0)}"
                   for s in symbols[:50])
    return f"Repository: {repo_name}\nFiles: {fl}\n\nKey symbols:\n{sy}"


def generate_tour(context, user=None, model=None):
    import json
    import re
    messages = [
        {"role": "system", "content":
            "You design concise onboarding tours for codebases. Reply with ONLY a JSON array "
            "of 6-10 steps; each step is "
            '{"title": str, "description": str, "file_path": str|null, "line_range": str|null}. '
            "Order from entry points to core to periphery."},
        {"role": "user", "content": context}]
    user_keys = getattr(user, "llm_keys", None) if user is not None else None
    try:
        resp = complete(messages=messages, model=model, user_keys=user_keys, max_tokens=1200)
        text, _ = _extract(resp)
        m = re.search(r"\[.*\]", text, re.S)
        steps = json.loads(m.group(0) if m else text)
        out = []
        for s in steps[:10]:
            if isinstance(s, dict):
                out.append({"title": str(s.get("title", ""))[:120],
                            "description": str(s.get("description", ""))[:600],
                            "file_path": s.get("file_path"), "line_range": s.get("line_range")})
        return out or [{"title": "Overview", "description": context[:400],
                        "file_path": None, "line_range": None}]
    except Exception as e:
        return [{"title": "Overview", "description": "Tour generation unavailable: " + str(e)[:200],
                 "file_path": None, "line_range": None}]
