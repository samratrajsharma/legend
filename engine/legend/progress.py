"""Persistent learning profile + spaced repetition. State lives per-repo under
`data_dir/progress/<repo>/state.json`, so what you explored, the flashcards you've
reviewed, and your quiz history survive restarts. Leitner-box scheduling drives reviews."""
from __future__ import annotations
import datetime
import hashlib
import json
import os

# Leitner intervals (days) by box; box 0 = new/failed, higher = longer gaps.
INTERVALS = [0, 1, 3, 7, 16, 35]
MASTERED_BOX = 4


def _today():
    return datetime.date.today().toordinal()


def _dir(config, repo):
    safe = "".join(c if c.isalnum() else "_" for c in (repo or "repo"))[:40] or "repo"
    d = os.path.join(config.data_dir, "progress", safe)
    os.makedirs(d, exist_ok=True)
    return d


def _path(config, repo):
    return os.path.join(_dir(config, repo), "state.json")


def load(config, repo):
    try:
        p = _path(config, repo)
        if os.path.exists(p):
            with open(p) as fh:
                s = json.load(fh)
        else:
            s = {}
    except Exception:
        s = {}
    s.setdefault("explored", [])
    s.setdefault("cards", {})      # card_id -> {box, reps, last, due}
    s.setdefault("quizzes", [])    # [{date, level, score, total}]
    return s


def save(config, repo, state):
    try:
        with open(_path(config, repo), "w") as fh:
            json.dump(state, fh, indent=2)
    except Exception:
        pass


def card_id(card):
    return hashlib.sha1(card["q"].encode("utf-8", "replace")).hexdigest()[:12]


def mark_explored(state, files):
    state["explored"] = sorted(set(state["explored"]) | set(files))
    return state


def review_card(state, card, correct):
    cid = card_id(card)
    c = state["cards"].get(cid, {"box": 0, "reps": 0})
    c["box"] = min(c["box"] + 1, len(INTERVALS) - 1) if correct else 0
    c["reps"] = c.get("reps", 0) + 1
    c["last"] = _today()
    c["due"] = _today() + INTERVALS[c["box"]]
    state["cards"][cid] = c
    return state


def is_due(state, card):
    c = state["cards"].get(card_id(card))
    return (c is None) or (c.get("due", 0) <= _today())


def due_cards(state, cards):
    return [c for c in cards if is_due(state, c)]


def record_quiz(state, level, score, total):
    state["quizzes"].insert(0, {"date": datetime.date.today().isoformat(),
                                "level": level, "score": score, "total": total})
    state["quizzes"] = state["quizzes"][:50]
    return state


def dashboard(state, idx, all_cards):
    code_files = [p.file for p in idx.parsed_files
                  if p.language in ("python", "javascript", "typescript")]
    explored = set(state["explored"]) & set(code_files)
    seen = sum(1 for c in all_cards if card_id(c) in state["cards"])
    mastered = sum(1 for c in all_cards
                   if state["cards"].get(card_id(c), {}).get("box", 0) >= MASTERED_BOX)
    due = len(due_cards(state, all_cards))
    by_level = {}
    for q in state["quizzes"]:
        b = by_level.setdefault(q["level"], {"attempts": 0, "best": 0})
        b["attempts"] += 1
        b["best"] = max(b["best"], round(100 * q["score"] / q["total"]) if q["total"] else 0)
    return {
        "coverage": round(len(explored) / len(code_files), 2) if code_files else 0.0,
        "explored": len(explored), "total_files": len(code_files),
        "cards_total": len(all_cards), "cards_seen": seen,
        "cards_mastered": mastered, "cards_due": due,
        "quiz_attempts": len(state["quizzes"]), "quiz_by_level": by_level,
    }


def export_anki_tsv(cards):
    """Tab-separated front/back — importable into Anki (Notes in Plain Text)."""
    return "\n".join(c["q"].replace("\t", " ") + "\t" + c["a"].replace("\t", " ").replace("\n", "<br>")
                     for c in cards)
