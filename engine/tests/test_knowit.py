"""KnowIT regression suite — stdlib unittest only (no pytest, no network, no secrets).
Run from the repo root:  python -m unittest discover -s tests -v
"""
import io
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from knowit.config import Config
from knowit.pipeline import build_index
from knowit import (insights, diagram, teach, techdebt, engmemory, research,
                    portfolio, progress, coverage, impact, config_map, media,
                    export_site, providers)
from knowit.eval_harness import load_questions, run_eval

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAMPLE = os.path.join(ROOT, "sample_repo")

try:                       # python-pptx is an optional media dependency
    import pptx  # noqa: F401
    _HAS_PPTX = True
except Exception:
    _HAS_PPTX = False


def _write(d, rel, content):
    p = os.path.join(d, rel)
    os.makedirs(os.path.dirname(p) or ".", exist_ok=True)
    with open(p, "w") as fh:
        fh.write(content)


class SampleRepoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        cls.cfg = Config(embed_backend="bm25", data_dir=os.path.join(cls.tmp, "cache"))
        cls.idx = build_index(SAMPLE, cls.cfg)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_pipeline(self):
        s = self.idx.stats()
        self.assertGreaterEqual(s["symbols"], 10)
        self.assertGreater(s["graph_edges"], 0)
        self.assertGreater(len(self.idx.chunks), 0)

    def test_retrieval(self):
        res = self.idx.ask("how does inference flow?")
        self.assertTrue(res["retrieved"])
        self.assertIn("infer.py", [r.chunk.file for r in res["retrieved"]])

    def test_insights(self):
        ins = insights.repo_insights(self.idx)
        self.assertIn("api.py", ins["entry_files"])
        self.assertTrue(insights.file_summary(self.idx, "infer.py")["internal_deps"])

    def test_diagrams(self):
        self.assertTrue(diagram.architecture_dot(self.idx).startswith("digraph"))
        nodes, tree = diagram.mindmap_tree(self.idx, "__repo__", 2, ("contains",), 6)
        self.assertEqual(len(tree), len(nodes) - 1)   # single-parent tree
        self.assertTrue(diagram.mindmap_dot(self.idx, "__repo__", nodes, tree,
                                            diagram.node_roles(self.idx)).startswith("digraph"))

    def test_path_finding(self):
        p = diagram.path_between(self.idx, "api.py::create_app", "model.py::Detector.predict")
        self.assertGreaterEqual(len(p), 2)

    def test_teach(self):
        self.assertTrue(teach.learning_path(self.idx))
        self.assertTrue(teach.flashcards(self.idx))
        for lvl in ("beginner", "intermediate", "senior"):
            self.assertTrue(teach.quiz(self.idx, lvl, 3))
        self.assertIn("coverage", teach.learning_gaps(self.idx, ["model.py"]))

    def test_techdebt(self):
        self.assertIn("cross_entropy", [d["symbol"] for d in techdebt.dead_code(self.idx)])
        self.assertIsInstance(techdebt.import_cycles(self.idx), list)
        self.assertIsInstance(techdebt.secret_scan(self.idx), list)

    def test_media(self):
        if _HAS_PPTX:                       # .pptx export only when the optional dep is present
            buf = io.BytesIO()
            media.build_pptx(self.idx, "technical", buf)
            self.assertGreater(len(buf.getvalue()), 1000)
        self.assertGreaterEqual(len(media.audio_script(self.idx)), 4)

    def test_portfolio(self):
        for k in ("report", "blog", "resume", "linkedin", "paper"):
            self.assertGreater(len(portfolio.generate(self.idx, k)), 50)

    def test_export_html(self):
        h = export_site.export_html(self.idx)
        self.assertTrue(h.startswith("<!doctype html"))
        self.assertIn("</body></html>", h)

    def test_engmemory_crud(self):
        e = engmemory.add(self.cfg, "t", "decisions", {"title": "x"})
        self.assertTrue(engmemory.load(self.cfg, "t", "decisions"))
        engmemory.delete(self.cfg, "t", "decisions", e["id"])
        self.assertEqual(engmemory.load(self.cfg, "t", "decisions"), [])

    def test_progress_srs(self):
        st = progress.load(self.cfg, "t")
        cards = teach.flashcards(self.idx)
        self.assertEqual(len(progress.due_cards(st, cards)), len(cards))  # all new
        progress.review_card(st, cards[0], correct=True)
        self.assertFalse(progress.is_due(st, cards[0]))                   # scheduled forward
        progress.record_quiz(st, "beginner", 4, 5)
        progress.save(self.cfg, "t", st)
        st2 = progress.load(self.cfg, "t")                               # persisted
        self.assertEqual(len(st2["quizzes"]), 1)

    def test_eval_gate(self):
        rows, summ = run_eval(self.idx, load_questions(
            os.path.join(ROOT, "eval", "questions.example.json")))
        self.assertTrue(summ["gate_pass"])

    def test_providers_graceful(self):
        self.assertEqual(providers.resolve("groq", "m", "")[0], "groq/m")
        self.assertIsNone(research.comparison_matrix_llm("a,b", ""))   # no model -> None


class FixtureTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.cfg = Config(embed_backend="bm25", data_dir=os.path.join(self.tmp, "c"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_duplicate_detection(self):
        d = os.path.join(self.tmp, "dup")
        _write(d, "a.py", "def f(items):\n    t=0\n    for x in items:\n        if x>0:\n            t=t+x\n    return t\n")
        _write(d, "b.py", "def g(values):\n    t=0\n    for x in values:\n        if x>0:\n            t=t+x\n    return t\n")
        idx = build_index(d, self.cfg)
        self.assertTrue(techdebt.duplicate_pairs(idx, min_tokens=10))

    def test_coverage_and_impact(self):
        d = os.path.join(self.tmp, "cov")
        _write(d, "a.py", "def alpha(x):\n    return x+1\ndef beta(x):\n    return alpha(x)\ndef lonely(x):\n    return x\n")
        _write(d, "tests/test_a.py", "from a import alpha\ndef test_alpha():\n    assert alpha(1)==2\n")
        idx = build_index(d, self.cfg)
        cs = coverage.coverage_summary(idx)
        self.assertEqual(cs["n_test_files"], 1)
        self.assertIn("lonely", [u["symbol"] for u in cs["untested_complex"]])
        self.assertIn("beta", impact.impact_of(idx, "a.py::alpha")["symbols"])

    def test_config_surface(self):
        d = os.path.join(self.tmp, "cfg")
        _write(d, "config.yaml", "model: detr\nlr: 0.001\n")
        _write(d, "settings.py", "DATA_DIR='/d'\nMAX_STEPS=10\n")
        idx = build_index(d, self.cfg)
        kinds = {c["kind"] for c in config_map.config_surface(idx)}
        self.assertIn("yaml", kinds)
        self.assertIn("settings", kinds)

    def test_research_detection(self):
        d = os.path.join(self.tmp, "r")
        _write(d, "README.md", "Implements DETR (arXiv:2005.12872), doi:10.1109/ICCV.2017.324\n")
        idx = build_index(d, self.cfg)
        refs = [p["ref"] for p in research.find_papers(idx)]
        self.assertIn("arXiv:2005.12872", refs)
        atom = ('<feed xmlns="http://www.w3.org/2005/Atom"><entry>'
                '<title>X</title><summary>Y</summary></entry></feed>')
        self.assertEqual(len(research.parse_arxiv_atom(atom)), 1)

    def test_track_git(self):
        if not shutil.which("git"):
            self.skipTest("git not available")
        from knowit import track
        d = os.path.join(self.tmp, "g")
        os.makedirs(d)
        run = lambda *a: subprocess.run(["git", *a], cwd=d, capture_output=True)
        run("init"); run("config", "user.email", "t@t"); run("config", "user.name", "t")
        _write(d, "m.py", "def a():\n    return 1\n")
        run("add", "-A"); run("commit", "-m", "c1")
        _write(d, "m.py", "def a():\n    return 2\ndef b():\n    return 3\n")
        run("add", "-A"); run("commit", "-m", "c2")
        log = track.git_log(d)
        self.assertEqual(len(log), 2)
        base = track.snapshot(d, log[-1]["sha"], self.cfg)
        head = track.snapshot(d, log[0]["sha"], self.cfg)
        diff = track.diff(base, head)
        self.assertTrue(any("b" in s for s in diff["symbols_added"]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
