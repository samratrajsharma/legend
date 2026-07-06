"""Optional LLM layer (via litellm). Degrades gracefully with no model/key."""
from __future__ import annotations

SYSTEM = (
    "You are KnowIT, a codebase explainer. Answer the question USING ONLY the provided "
    "code context. Ground every claim in the snippets and cite sources inline as "
    "(path:line). Prefer specifics (function/class names) over generalities. If the "
    "answer is not present in the context, say exactly what is missing rather than "
    "guessing. Be concise."
)


def _complete(model, messages, extra=None, **kw):
    import litellm
    return litellm.completion(model=model, messages=messages, **(extra or {}), **kw)


def synthesize(question, context, model, extra=None):
    """Return (answer_text|None, used_llm: bool)."""
    if not model:
        return (None, False)
    try:
        r = _complete(model, [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": f"Question: {question}\n\nCode context:\n{context}"},
        ], extra=extra, temperature=0.1, timeout=60)
        return (r["choices"][0]["message"]["content"].strip(), True)
    except Exception as e:
        return (f"[LLM unavailable: {type(e).__name__}: {e}]", False)


def judge(question, answer, context, model, extra=None):
    if not model or not answer:
        return None
    try:
        import re
        r = _complete(model, [{"role": "user", "content": (
            "Score 0-100 how correct and grounded this answer is given the code context. "
            "Reply with ONLY the integer.\n\n"
            f"Question: {question}\nAnswer: {answer}\n\nContext:\n{context[:4000]}")}],
            extra=extra, temperature=0, timeout=60)
        m = re.search(r"\d+", r["choices"][0]["message"]["content"])
        return (min(100, int(m.group())) / 100.0) if m else None
    except Exception:
        return None


def explain_file(summary, code_excerpt, model, extra=None):
    if not model:
        return None
    try:
        import json
        prompt = (
            "Explain this source file for a new engineer in <150 words. Cover: purpose, "
            "key inputs/outputs, main dependencies, and the most important logic.\n\n"
            f"Structured facts:\n{json.dumps(summary, indent=2)[:2500]}\n\n"
            f"Code excerpt:\n{code_excerpt[:3000]}")
        r = _complete(model, [
            {"role": "system", "content": "You explain code precisely and concisely."},
            {"role": "user", "content": prompt}], extra=extra, temperature=0.2, timeout=60)
        return r["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return f"[LLM unavailable: {type(e).__name__}: {e}]"
