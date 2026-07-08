from __future__ import annotations
import json


def load_questions(path):
    with open(path, "r", encoding="utf-8") as fh:
        if path.endswith((".yaml", ".yml")):
            try:
                import yaml
            except Exception as e:
                raise RuntimeError("PyYAML not installed; use a .json question set") from e
            data = yaml.safe_load(fh)
        else:
            data = json.load(fh)
    if isinstance(data, dict) and "questions" in data:
        return data["questions"]
    return data


def _kw_coverage(text, keywords):
    if not keywords:
        return None
    t = (text or "").lower()
    return sum(1 for k in keywords if k.lower() in t) / len(keywords)


def run_eval(repo_index, questions, judge_model="", kw_threshold=0.5):
    from .llm import judge
    rows = []
    for q in questions:
        res = repo_index.ask(q["question"])
        files = [r.chunk.file for r in res["retrieved"]]
        exp_files = q.get("expect_files") or []
        retr_hit = (any(any(ef in f for f in files) for ef in exp_files)
                    if exp_files else None)
        text_for_kw = res["answer"] if res["used_llm"] else res["context"]
        kw_cov = _kw_coverage(text_for_kw, q.get("expect_keywords"))
        jscore = judge(q["question"], res["answer"], res["context"], judge_model) if judge_model else None

        if jscore is not None:
            passed = jscore >= 0.7
        elif exp_files or q.get("expect_keywords"):
            ok_retr = (retr_hit is None) or retr_hit
            ok_kw = (kw_cov is None) or (kw_cov >= kw_threshold)
            passed = bool(ok_retr and ok_kw)
        else:
            passed = None   # no expectations => manual review

        rows.append({
            "id": q.get("id", ""), "question": q["question"],
            "retrieval_hit": retr_hit, "kw_coverage": kw_cov, "judge": jscore,
            "passed": passed, "top_files": files[:4], "used_llm": res["used_llm"],
            "answer": res["answer"],
        })

    scored = [r for r in rows if r["passed"] is not None]
    n_pass = sum(1 for r in scored if r["passed"])
    pass_rate = (n_pass / len(scored)) if scored else 0.0
    summary = {"total": len(rows), "scored": len(scored), "passed": n_pass,
               "pass_rate": pass_rate, "gate_pass": pass_rate >= 0.8}
    return rows, summary
