#!/usr/bin/env python3
"""Headless Legend Phase 0 eval runner.

Usage:
  python scripts/run_eval.py <repo_path_or_url> <questions.json> [--judge-model MODEL]
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from legend.pipeline import build_index          # noqa: E402
from legend.config import CONFIG                  # noqa: E402
from legend.eval_harness import load_questions, run_eval   # noqa: E402


def main():
    ap = argparse.ArgumentParser(description="Legend Phase 0 eval runner")
    ap.add_argument("repo", help="path or git URL of the repo to analyze")
    ap.add_argument("questions", help="path to questions .json / .yaml")
    ap.add_argument("--judge-model", default="",
                    help="LLM model for LLM-as-judge scoring (optional)")
    args = ap.parse_args()

    idx = build_index(args.repo, CONFIG, progress=lambda m: print("  ", m))
    print("\nStats:", json.dumps(idx.stats(), indent=2))

    qs = load_questions(args.questions)
    rows, summary = run_eval(idx, qs, judge_model=args.judge_model)
    print("\nPer-question:")
    for r in rows:
        mark = {True: "PASS", False: "FAIL", None: "MANUAL"}[r["passed"]]
        print(f"  [{mark}] {r['id']}: retrieval_hit={r['retrieval_hit']} "
              f"kw={r['kw_coverage']} files={r['top_files']}")
    print("\nSummary:", json.dumps(summary, indent=2))
    print("\nGATE (>=80% of scored questions):",
          "PASS" if summary["gate_pass"] else "NEEDS WORK")


if __name__ == "__main__":
    main()
