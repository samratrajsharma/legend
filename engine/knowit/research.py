"""Phase 7 — research mode. Link code to the literature: detect paper references in the
repo, look up arXiv metadata, and (with an LLM) produce comparison matrices, implementation
plans grounded in the repo, and novelty notes. Detection + parsing are offline/testable;
the live arXiv fetch and LLM features degrade gracefully."""
from __future__ import annotations
import re
import urllib.request
import xml.etree.ElementTree as ET

_ARXIV_ID = re.compile(r'arxiv[:\s/]+\s*(\d{4}\.\d{4,5})(?:v\d+)?', re.I)
_ARXIV_URL = re.compile(r'arxiv\.org/(?:abs|pdf)/(\d{4}\.\d{4,5})', re.I)
_DOI = re.compile(r'\b(10\.\d{4,9}/[-._;()/:A-Za-z0-9]+)\b')


def _add(found, ref, kind, file):
    e = found.setdefault(ref, {"kind": kind, "files": set()})
    e["files"].add(file)


def find_papers(idx):
    """Scan repo text for arXiv ids/URLs and DOIs; return refs with the files that cite them."""
    found = {}
    for p in idx.parsed_files:
        txt = p.text or ""
        for m in _ARXIV_ID.finditer(txt):
            _add(found, "arXiv:" + m.group(1), "arxiv", p.file)
        for m in _ARXIV_URL.finditer(txt):
            _add(found, "arXiv:" + m.group(1), "arxiv", p.file)
        for m in _DOI.finditer(txt):
            _add(found, m.group(1).rstrip(".,);"), "doi", p.file)
    return sorted(({"ref": k, "kind": v["kind"], "files": sorted(v["files"])}
                   for k, v in found.items()), key=lambda x: x["ref"])


def parse_arxiv_atom(xml_text):
    """Parse the arXiv API's Atom response into a list of paper dicts (offline-testable)."""
    ns = {"a": "http://www.w3.org/2005/Atom"}
    root = ET.fromstring(xml_text)
    out = []
    for e in root.findall("a:entry", ns):
        title = (e.findtext("a:title", default="", namespaces=ns) or "").strip()
        summary = (e.findtext("a:summary", default="", namespaces=ns) or "").strip()
        published = (e.findtext("a:published", default="", namespaces=ns) or "")[:10]
        idu = (e.findtext("a:id", default="", namespaces=ns) or "").strip()
        authors = [a.findtext("a:name", default="", namespaces=ns)
                   for a in e.findall("a:author", ns)]
        out.append({"title": re.sub(r"\s+", " ", title),
                    "summary": re.sub(r"\s+", " ", summary),
                    "authors": [x for x in authors if x], "published": published, "url": idu})
    return out


def arxiv_lookup(arxiv_id, timeout=15):
    """Fetch arXiv metadata for an id. Network; returns the paper dict, None, or {'error': ...}."""
    aid = arxiv_id.replace("arXiv:", "").replace("arxiv:", "").strip()
    url = "http://export.arxiv.org/api/query?id_list=" + aid
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:   # noqa: S310 (trusted host)
            data = r.read().decode("utf-8", "replace")
        res = parse_arxiv_atom(data)
        return res[0] if res else None
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}


def research_summary(idx):
    """Offline summary: detected papers + what the repo defines (no LLM)."""
    papers = find_papers(idx)
    classes = [n["data"]["qualname"] for n in idx.graph.nodes.values()
               if n["type"] == "symbol" and n["data"]["kind"] == "class"]
    return {"papers": papers, "n_papers": len(papers), "classes": classes[:20]}


# ---------------- LLM features (graceful) ----------------
def comparison_matrix_llm(approaches, model, extra=None):
    if not model:
        return None
    try:
        from . import llm
        prompt = (f"Build a concise comparison table in Markdown of these approaches: "
                  f"{approaches}.\nColumns: Approach | Core idea | Architecture | Strengths | "
                  "Weaknesses | Best for. Be accurate and brief; one row per approach.")
        r = llm._complete(model, [
            {"role": "system", "content": "You are a precise ML research analyst."},
            {"role": "user", "content": prompt}], extra=extra, temperature=0.2, timeout=90)
        return r["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return f"[LLM unavailable: {type(e).__name__}: {e}]"


def implementation_plan_llm(topic, repo_index, model, extra=None):
    if not model:
        return None
    try:
        from . import llm
        from .retrieval import assemble_context
        ctx = assemble_context(repo_index.search(topic)) if repo_index else ""
        prompt = (f"Produce a concrete implementation plan for: {topic}\n"
                  "Ground it in the existing codebase where relevant (reference the modules "
                  "shown). Give: goal, ordered steps, which existing files to touch or extend, "
                  "and the main risks.\n\nRelevant code:\n" + ctx)
        r = llm._complete(model, [
            {"role": "system", "content": "You are a senior ML engineer writing an implementation plan."},
            {"role": "user", "content": prompt}], extra=extra, temperature=0.3, timeout=90)
        return r["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return f"[LLM unavailable: {type(e).__name__}: {e}]"


def novelty_summary_llm(idx, model, extra=None):
    if not model:
        return None
    try:
        from . import llm
        rs = research_summary(idx)
        papers = ", ".join(p["ref"] for p in rs["papers"]) or "none detected"
        prompt = ("Given the papers this repo references and the components it defines, write a "
                  "short note (<150 words) on what the repo implements, what looks standard, and "
                  "what may be novel.\n\n"
                  f"Referenced papers: {papers}\nKey classes: {rs['classes']}")
        r = llm._complete(model, [
            {"role": "system", "content": "You assess ML research code crisply."},
            {"role": "user", "content": prompt}], extra=extra, temperature=0.3, timeout=90)
        return r["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return f"[LLM unavailable: {type(e).__name__}: {e}]"
