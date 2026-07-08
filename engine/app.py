"""KnowIT — Streamlit harness (Phases 0–3 + Teach + deepened engine).

    streamlit run app.py

Auto-builds + disk-caches the index. Hybrid BM25+semantic (RRF) retrieval. Multi-provider
LLM (OpenAI/Anthropic/Groq/Ollama/OpenRouter/custom). Tabs: Overview, Files, Diagrams,
API & DB, Ask, Learn, Eval.
"""
import io
import os
import sys

import streamlit as st
import streamlit.components.v1 as components

try:
    import pandas as pd
except Exception:
    pd = None

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from knowit.config import Config                          # noqa: E402
from knowit.pipeline import build_index, recent_repos     # noqa: E402
from knowit.eval_harness import load_questions, run_eval  # noqa: E402
from knowit.retrieval import assemble_context             # noqa: E402
from knowit import insights, diagram, llm, providers, teach, track, techdebt, engmemory, media, research, portfolio  # noqa: E402
from knowit import progress, coverage, impact, config_map, export_site  # noqa: E402

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_REPO = os.environ.get("KNOWIT_REPO") or os.path.join(APP_DIR, "sample_repo")
DEFAULT_QUESTIONS = os.path.join(APP_DIR, "eval", "questions.example.json")
DATA_DIR = Config().data_dir
BACKENDS = ["auto", "hybrid", "bm25", "chroma"]
VIA = {"lexical": "🔤 keyword", "semantic": "🔎 semantic", "both": "🔎🔤 both", "graph": "🕸 graph"}
LANG_HL = {"python": "python", "javascript": "javascript", "typescript": "typescript", "markdown": "markdown"}

st.set_page_config(page_title="KnowIT", layout="wide")


@st.cache_resource(show_spinner=False)
def _build(source, backend):
    return build_index(source, Config(embed_backend=backend))


def get_index(source, backend, full_model, extra, topk):
    idx = _build(source, backend)
    idx.config.llm_model = full_model
    idx.config.llm_kwargs = extra or {}
    idx.config.top_k = topk
    return idx


def show_table(rows):
    if not rows:
        st.caption("— none —")
    elif pd is not None:
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.table(rows)


def show_graph(dot):
    try:
        st.graphviz_chart(dot, use_container_width=True)
    except Exception as e:
        st.warning(f"Couldn't render diagram ({type(e).__name__}); showing source.")
        st.code(dot, language="dot")


# ===================== sidebar =====================
with st.sidebar:
    st.header("KnowIT")
    source = st.text_input("Repo path or git URL", value=DEFAULT_REPO)
    rec = [r["source"] for r in recent_repos(DATA_DIR)]
    if rec:
        pick = st.selectbox("…or a recent repo", ["(keep above)"] + rec)
        if pick != "(keep above)":
            source = pick
    backend = st.selectbox("Retrieval", BACKENDS, index=0,
                           help="auto/hybrid = BM25 + semantic (Chroma) fused via RRF.")
    st.divider()
    st.subheader("LLM provider")
    plabels = {"": "(none — context only)"}
    plabels.update({k: providers.PROVIDERS[k]["label"] for k in providers.PROVIDERS})
    provider = st.selectbox("Provider", providers.ORDER, format_func=lambda x: plabels.get(x, x))
    model, base_url = "", ""
    if provider:
        p = providers.PROVIDERS[provider]
        if p["models"]:
            choice = st.selectbox("Model", p["models"] + ["(custom…)"])
            model = st.text_input("Custom model", "") if choice == "(custom…)" else choice
        else:
            model = st.text_input("Model", "")
        if p.get("base_url"):
            base_url = st.text_input("Base URL", value=p.get("default_base", ""))
        if not providers.key_present(provider):
            st.warning(f"Set `{p['key_env']}` in your environment / .env.")
    else:
        model = st.text_input("Raw litellm model (optional)", value=os.environ.get("KNOWIT_LLM_MODEL", ""))
    full_model, extra = providers.resolve(provider, model, base_url)
    if provider and model and st.button("Test connection"):
        with st.spinner("Pinging the model…"):
            ok, msg = providers.test_connection(full_model, extra)
        (st.success if ok else st.error)(msg)
    topk = st.slider("Top-k", 3, 15, 6)
    if st.button("Rebuild index"):
        _build.clear()
        st.rerun()
    st.caption("Index is disk-cached; relaunch is fast. Set KNOWIT_REPO to boot into your own repo.")

# ===================== build =====================
try:
    with st.spinner(f"Indexing {source} …"):
        idx = get_index(source, backend, full_model, extra, topk)
except Exception as e:
    st.title("KnowIT")
    st.error(f"Could not build the index for `{source}`.")
    st.exception(e)
    st.stop()

s = idx.stats()
st.title("KnowIT")
st.caption(f"**{s['repo']}** · commit `{s['commit']}` · retrieval **{s['retriever']}** · "
           f"answers: {('LLM (' + full_model + ')') if full_model else 'context-only'}")

tabs = st.tabs(["Overview", "Files", "Diagrams", "API & DB", "Ask", "Learn", "Track", "Intel", "Media", "Research", "Portfolio", "Eval"])
explored = st.session_state.setdefault("explored", set())
pstate = progress.load(idx.config, idx.meta.name)
explored |= set(pstate.get("explored", []))

# ---------------- Overview ----------------
with tabs[0]:
    c = st.columns(4)
    c[0].metric("Code files", s["python_files"])
    c[1].metric("Symbols", s["symbols"])
    c[2].metric("Graph edges", s["graph_edges"])
    c[3].metric("Chunks", s["chunks"])
    with st.expander("How KnowIT built this (the pipeline)"):
        st.markdown(
            f"1. **Ingest** — `{s['repo']}` @ `{s['commit']}`, {s['files_parsed']} files.\n"
            f"2. **Parse** → **{s['symbols']} symbols** (errors: {s['parse_errors']}).\n"
            f"3. **Code graph** — {s['graph_nodes']} nodes / {s['graph_edges']} edges: {s['edge_types']}.\n"
            f"4. **Chunk** — {s['chunks']} chunks tagged `{{graph node, commit}}` (disk-cached).\n"
            f"5. **Retrieve** — {s['retriever']} + one-hop graph expansion.")
    ins = insights.repo_insights(idx)
    st.subheader("Insights")
    m = st.columns(3)
    m[0].metric("Total LOC", ins["loc_total"])
    m[1].metric("Avg complexity / fn", ins["avg_complexity"])
    m[2].metric("Entry points", len(ins["entry_files"]))
    st.markdown("**Languages**")
    show_table(insights.language_breakdown(idx))
    cc = st.columns(2)
    with cc[0]:
        st.markdown("**🚪 Entry points**")
        st.write(ins["entry_files"] or "— none —")
        st.markdown("**🔗 Hub files**")
        show_table(ins["hub_files"])
    with cc[1]:
        st.markdown("**🧠 Most complex**")
        show_table(ins["complex_symbols"])
        st.markdown("**🧹 Likely unused**")
        show_table(ins["likely_unused"])

    with st.expander("⚙ Configuration surface"):
        cs = config_map.config_surface(idx)
        if cs:
            show_table([{"source": c["source"], "kind": c["kind"], "items": ", ".join(c["items"][:12])} for c in cs])
        else:
            st.caption("No config files / argparse / settings detected.")

# ---------------- Files ----------------
with tabs[1]:
    pfmap = {p.file: p for p in idx.parsed_files}
    left, right = st.columns([1, 2])
    with left:
        def _tree(files):
            tree = {}
            for f in files:
                parts = f.replace("\\", "/").split("/")
                node = tree
                for p in parts[:-1]:
                    node = node.setdefault(p + "/", {})
                node.setdefault("_f", []).append(parts[-1])
            out = []

            def walk(n, d):
                for k in sorted(k for k in n if k != "_f"):
                    out.append("  " * d + "📁 " + k)
                    walk(n[k], d + 1)
                for fn in sorted(n.get("_f", [])):
                    out.append("  " * d + "📄 " + fn)
            walk(tree, 0)
            return "\n".join(out)
        st.markdown("**File tree**")
        st.code(_tree(list(pfmap.keys())), language="text")
        sel = st.selectbox("Select a file", sorted(pfmap.keys()))
    explored.add(sel)  # browsing a file counts as exploring it
    pstate["explored"] = sorted(explored); progress.save(idx.config, idx.meta.name, pstate)
    with right:
        fs = insights.file_summary(idx, sel)
        st.markdown(f"### `{sel}`")
        st.caption(f"{fs['language']} · {fs['loc']} LOC · complexity {fs['complexity_total']} "
                   f"· imported by {fs['fan_in']} · imports {fs['fan_out']} internal")
        if fs["purpose"]:
            st.markdown(f"**Purpose** — {fs['purpose']}")
        if full_model and st.button("Explain this file with the LLM"):
            with st.spinner("Asking the model…"):
                st.info(llm.explain_file(fs, pfmap[sel].text, full_model, extra))
        d1, d2 = st.columns(2)
        d1.markdown("**Depends on (internal)**")
        d1.write(fs["internal_deps"] or "— none —")
        d2.markdown("**Used by**")
        d2.write(fs["dependents"] or "— none —")
        if fs["imports"]:
            st.caption("Imports: " + ", ".join(fs["imports"]))
        st.markdown("**Defines**")
        show_table(fs["defines"])
        if fs["public_api"]:
            st.markdown("**Public API**")
            show_table([{"symbol": a["symbol"], "used_by": ", ".join(a["used_by"])} for a in fs["public_api"]])
        with st.expander("Source"):
            st.code(pfmap[sel].text or "", language=LANG_HL.get(fs["language"], "text"))

# ---------------- Diagrams (mind map + explorer) ----------------
with tabs[2]:
    st.subheader("Diagrams")
    G = idx.graph
    all_nodes = sorted(G.nodes.keys())

    def qual(n):
        nd = G.get(n)
        return (nd["data"].get("qualname") or n) if nd else n

    roles = diagram.node_roles(idx)
    view = st.radio("View", ["Mind map", "Graph explorer", "Whole-repo"], horizontal=True)

    if view == "Mind map":
        st.caption("A compact branching map. Pick a root, then set how deep and how wide it grows. "
                   "🟢 entry · 🔴 likely-unused")
        opts = ["\u2605 whole repo"] + all_nodes
        dft = st.session_state.get("focus_node")
        sel = st.selectbox("Root", opts, index=opts.index(dft) if dft in opts else 0,
                           format_func=lambda n: "\u2605 whole repo" if n.startswith("\u2605") else qual(n))
        root = "__repo__" if sel.startswith("\u2605") else sel
        if root != "__repo__":
            st.session_state["focus_node"] = root
        c = st.columns(3)
        depth = c[0].slider("Depth", 1, 3, 2)
        breadth = c[1].slider("Branches / node", 3, 10, 7)
        follow = c[2].multiselect("Follow", ["contains", "calls", "imports", "method_of"],
                                  default=["contains", "calls"])
        nodes, tree = diagram.mindmap_tree(idx, root, depth, tuple(follow) or ("contains", "calls"), breadth)
        st.caption(f"{len(nodes)} nodes")
        renderer = st.radio("Style", ["Clean (static)", "Draggable"], horizontal=True)
        rendered = False
        if renderer == "Draggable":
            html = diagram.pyvis_html(idx, None, nodes, [(a, b, "") for a, b in tree], roles, hierarchical=True)
            if html:
                components.html(html, height=560, scrolling=True); rendered = True
            else:
                st.caption("Install `pyvis` for the draggable version \u2014 showing the clean map.")
        if not rendered:
            show_graph(diagram.mindmap_dot(idx, root, nodes, tree, roles, idx.meta.name))
        branches = sorted(n for n in nodes if n != root and not n.startswith("__"))
        jump = st.selectbox("\u21aa Re-root the map on", ["(stay)"] + branches,
                            format_func=lambda n: n if n == "(stay)" else qual(n))
        if jump != "(stay)":
            st.session_state["focus_node"] = jump; st.rerun()
        if full_model and st.button("Explain this map"):
            efocus = root if root in G.nodes else next((n for n in nodes if G.get(n)), root)
            with st.spinner("Explaining\u2026"):
                st.info(diagram.explain_view_llm(idx, nodes, [(a, b, "") for a, b in tree], efocus, full_model, extra))

    elif view == "Graph explorer":
        st.caption("Neighbourhood graph around a focus node (all relationships, both directions).")
        dft = st.session_state.get("focus_node")
        if dft not in G.nodes:
            dft = "infer.py::run_inference" if "infer.py::run_inference" in G.nodes else all_nodes[0]
        c1, c2 = st.columns([3, 1])
        focus = c1.selectbox("Focus node", all_nodes, index=all_nodes.index(dft), format_func=qual)
        st.session_state["focus_node"] = focus
        depth = c2.slider("Depth", 1, 3, 1, key="ge_depth")
        etypes = st.multiselect("Relationships", list(diagram._EDGE_TYPES),
                                default=["calls", "imports", "contains"], key="ge_edges")
        nodes, edges = diagram.neighborhood(idx, focus, depth, tuple(etypes))
        show_graph(diagram.focused_dot(idx, focus, nodes, edges, roles))
        nb = sorted(n for n in nodes if n != focus)
        jump = st.selectbox("\u21aa Jump to", ["(stay)"] + nb,
                            format_func=lambda n: n if n == "(stay)" else qual(n), key="ge_jump")
        if jump != "(stay)":
            st.session_state["focus_node"] = jump; st.rerun()

    else:
        preset = st.radio("Preset", ["File dependencies", "Class diagram", "Knowledge graph"],
                          horizontal=True, key="preset_diag")
        if preset == "File dependencies":
            show_graph(diagram.architecture_dot(idx))
            st.download_button("Download Mermaid (.mmd)", diagram.architecture_mermaid(idx),
                               file_name="architecture.mmd")
        elif preset == "Class diagram":
            show_graph(diagram.class_dot(idx))
        else:
            show_graph(diagram.knowledge_dot(idx))

# ---------------- API & DB ----------------
with tabs[3]:
    st.subheader("API endpoints")
    am = insights.api_map(idx)
    show_table(am) if am else st.caption("No FastAPI/Flask/Express-style routes detected.")
    st.subheader("Data models")
    dm = insights.db_map(idx)
    show_table(dm) if dm else st.caption("No ORM models / `__tablename__` detected.")

# ---------------- Ask ----------------
with tabs[4]:
    st.subheader("Ask anything about the repo")
    q = st.text_input("Question", value="How does the inference flow work?")
    if st.button("Ask", type="primary") and q:
        with st.spinner("Retrieving …"):
            res = idx.ask(q)
        if res["used_llm"]:
            st.markdown("### Answer")
            st.write(res["answer"])
        else:
            st.info("No LLM configured — showing the grounded context KnowIT retrieved. "
                    "Pick a provider in the sidebar for a written answer.")
        st.markdown(f"### Sources ({len(res['retrieved'])})")
        for r in res["retrieved"]:
            ch = r.chunk
            with st.expander(f"{ch.file}:{ch.start_line}-{ch.end_line} · {ch.name} · {VIA.get(r.via, r.via)} · score {r.score:.3f}"):
                st.code(ch.text, language="python")

# ---------------- Learn (Phase 2) ----------------
with tabs[5]:
    st.subheader("Teach Me This Repository")
    mode = st.radio("Mode", ["Learning path", "Flashcards", "Quiz", "Interview", "Progress", "Gaps"], horizontal=True)

    if mode == "Learning path":
        st.caption("A suggested route: entry points → hub files → the rest.")
        for i, stop in enumerate(teach.learning_path(idx)):
            with st.expander(f"{i + 1}. {stop['file']} — {stop['why']}"):
                st.write("**Key symbols:** " + (", ".join(stop["key_symbols"]) or "—"))
                if stop["depends_on"]:
                    st.caption("Depends on: " + ", ".join(stop["depends_on"]))
                if st.checkbox("I've studied this", key=f"std_{stop['file']}", value=stop["file"] in explored):
                    explored.add(stop["file"])

    elif mode == "Flashcards":
        cards = teach.flashcards(idx, limit=30)
        study = st.checkbox("Spaced-repetition study (show only cards due for review)")
        shown = progress.due_cards(pstate, cards) if study else cards
        st.caption(f"{len(shown)} card(s)" + (" due" if study else "") + " — click to reveal, then grade yourself.")
        for i, card in enumerate(shown):
            with st.expander(f"Q{i + 1}. {card['q']}"):
                st.write(card["a"])
                b1, b2 = st.columns(2)
                if b1.button("✓ Got it", key=f"fc_ok_{i}"):
                    progress.review_card(pstate, card, True)
                    progress.save(idx.config, idx.meta.name, pstate)
                    st.rerun()
                if b2.button("✗ Review again", key=f"fc_no_{i}"):
                    progress.review_card(pstate, card, False)
                    progress.save(idx.config, idx.meta.name, pstate)
                    st.rerun()
            explored.add(card["ref"])

    elif mode == "Quiz":
        cols = st.columns([1, 1, 2])
        level = cols[0].selectbox("Level", ["beginner", "intermediate", "senior"])
        nq = cols[1].slider("Questions", 3, 8, 5)
        qkey = (idx.meta.name, level, nq)
        if st.session_state.get("quiz_key") != qkey or cols[2].button("New quiz"):
            st.session_state["quiz"] = teach.quiz(idx, level, nq)
            st.session_state["quiz_key"] = qkey
        quiz = st.session_state.get("quiz", [])
        with st.form("quizform"):
            picks = [st.radio(f"{i + 1}. {qq['question']}", qq["options"], key=f"quiz{i}", index=None)
                     for i, qq in enumerate(quiz)]
            submitted = st.form_submit_button("Submit answers")
        if submitted:
            score = 0
            for i, qq in enumerate(quiz):
                correct = qq["options"][qq["answer"]]
                ok = picks[i] == correct
                score += ok
                st.write(("✅ " if ok else "❌ ") + f"**{qq['question']}** → {correct}  ·  {qq['explanation']}")
                explored.add(qq["ref"])
            st.metric("Score", f"{score}/{len(quiz)}")
            progress.record_quiz(pstate, level, score, len(quiz))
            progress.save(idx.config, idx.meta.name, pstate)

    elif mode == "Interview":
        st.caption("Senior-engineer-style questions about this repo." +
                   ("" if full_model else "  Set an LLM provider to get your answers graded."))
        for i, qq in enumerate(teach.interview(idx, n=5)):
            st.markdown(f"**Q{i + 1}. {qq['question']}**")
            ans = st.text_area("Your answer", key=f"iv{i}", label_visibility="collapsed")
            if full_model:
                if st.button("Grade my answer", key=f"grade{i}"):
                    with st.spinner("Grading…"):
                        ctx = assemble_context(idx.search(qq["question"]))
                        st.info(teach.grade_answer_llm(qq["question"], ans, qq["expected"], ctx, full_model, extra))
            else:
                with st.expander("What a strong answer covers"):
                    st.write(", ".join(map(str, qq["expected"])))
            explored.add(qq["ref"])

    elif mode == "Progress":
        all_cards = teach.flashcards(idx, limit=30)
        db = progress.dashboard(pstate, idx, all_cards)
        pm = st.columns(4)
        pm[0].metric("Files explored", f"{db['explored']}/{db['total_files']}")
        pm[1].metric("Coverage", f"{int(db['coverage'] * 100)}%")
        pm[2].metric("Cards mastered", f"{db['cards_mastered']}/{db['cards_total']}")
        pm[3].metric("Cards due", db["cards_due"])
        st.progress(db["coverage"])
        if db["quiz_by_level"]:
            st.markdown("**Quiz history (best score per level)**")
            show_table([{"level": k, "attempts": v["attempts"], "best": f"{v['best']}%"}
                        for k, v in db["quiz_by_level"].items()])
        st.download_button("Export flashcards for Anki (.tsv)",
                           progress.export_anki_tsv(all_cards),
                           file_name=f"{idx.meta.name}_flashcards.tsv")
        st.caption("Your progress — explored files, flashcard reviews, and quiz scores — "
                   "persists across sessions under the data directory.")
    else:  # Gaps
        g = teach.learning_gaps(idx, explored)
        st.metric("Coverage", f"{int(g['coverage'] * 100)}%   ({g['explored']}/{g['total']} files)")
        st.progress(g["coverage"])
        st.markdown("**What you haven't explored yet**")
        st.write(g["unexplored"] or "🎉 You've touched every file.")
        st.markdown("**Used but unexplored** — you rely on these but haven't studied them")
        st.write(g["used_but_unexplored"] or "—")
        st.caption("Exploration is tracked as you browse Files and use the Learn tab "
                   "(this session).")

# ---------------- Track (Phase 4) ----------------
with tabs[6]:
    st.subheader("Track evolution")
    path = idx.meta.path
    log = track.git_log(path, 40)
    if len(log) < 2:
        st.info("Track needs a **git repo with at least two commits**. Point the sidebar / "
                "`KNOWIT_REPO` at a git repository, or run "
                "`python scripts/make_demo_history.py` and open the folder it prints.")
    else:
        with st.expander("Recent commits"):
            show_table([{"commit": c["short"], "date": c["date"], "author": c["author"],
                         "subject": c["subject"]} for c in log])
        labels = [f"{c['short']} · {c['date']} · {c['subject'][:48]}" for c in log]
        col = st.columns(2)
        base_i = col[0].selectbox("Base (older)", range(len(log)),
                                  index=min(len(log) - 1, 5), format_func=lambda i: labels[i])
        head_i = col[1].selectbox("Head (newer)", range(len(log)), index=0,
                                  format_func=lambda i: labels[i])
        if st.button("Compare", type="primary"):
            try:
                with st.spinner("Snapshotting both commits…"):
                    base = track.snapshot(path, log[base_i]["sha"], idx.config)
                    head = track.snapshot(path, log[head_i]["sha"], idx.config)
                d = track.diff(base, head)
                mc = st.columns(4)
                mc[0].metric("Files +/−", f"+{len(d['files_added'])} / −{len(d['files_removed'])}")
                mc[1].metric("Symbols +/−", f"+{len(d['symbols_added'])} / −{len(d['symbols_removed'])}")
                mc[2].metric("Modified", len(d["symbols_modified"]))
                mc[3].metric("Imports +/−", f"+{len(d['imports_added'])} / −{len(d['imports_removed'])}")
                st.markdown("### Changelog")
                st.markdown(track.changelog_text(d))
                if full_model:
                    with st.spinner("Narrating…"):
                        st.markdown("**LLM summary**")
                        st.write(track.narrate_llm(d, full_model, extra))
                st.markdown("### Architecture delta")
                st.caption("Green = added · red dashed = removed.")
                show_graph(track.architecture_delta_dot(base, head))
                if d["complexity_changes"]:
                    st.markdown("### Complexity changes")
                    show_table(d["complexity_changes"])
                st.markdown("### Learning delta")
                ld = track.learning_delta(d, explored)
                st.write("**Re-learn** (you studied these and they changed): "
                         + (", ".join(ld["re_learn"]) or "—"))
                st.write("**New since** (added, not yet explored): "
                         + (", ".join(ld["new_files"]) or "—"))
                if ld["removed_files"]:
                    st.warning("Removed files you had explored: " + ", ".join(ld["removed_files"]))
            except Exception as e:
                st.exception(e)

    st.divider()
    st.subheader("Impact analysis")
    _isyms = sorted(n for n, nn in idx.graph.nodes.items() if nn["type"] == "symbol")
    if _isyms:
        tgt = st.selectbox("If I change…", _isyms,
                           format_func=lambda n: idx.graph.get(n)["data"]["qualname"], key="impact_sym")
        imp = impact.impact_of(idx, tgt)
        st.write(f"**Affected symbols ({len(imp['symbols'])}):** " + (", ".join(imp["symbols"]) or "— nothing calls it"))
        st.write("**Affected files:** " + (", ".join(imp["files"]) or "—"))

# ---------------- Intel (Phase 5) ----------------
with tabs[7]:
    st.subheader("Engineering intelligence")
    sub = st.radio("View", ["Tech debt", "Coverage", "Decisions", "Errors", "Memory"], horizontal=True)
    if sub == "Tech debt":
        dead = techdebt.dead_code(idx); dups = techdebt.duplicate_pairs(idx)
        cycles = techdebt.import_cycles(idx); hots = techdebt.complexity_hotspots(idx)
        gods = techdebt.god_files(idx); undoc = techdebt.undocumented(idx)
        m = st.columns(5)
        m[0].metric("Dead code", len(dead)); m[1].metric("Duplicate pairs", len(dups))
        m[2].metric("Import cycles", len(cycles)); m[3].metric("Hotspots", len(hots))
        m[4].metric("Undocumented", len(undoc))
        st.markdown("**🧹 Likely dead code** — no callers and not referenced by an entry point")
        show_table(dead)
        st.markdown("**👯 Near-duplicate code** — structurally similar (rename-insensitive)")
        show_table(dups)
        st.markdown("**🔁 Import cycles**")
        if cycles:
            for c in cycles: st.write(" ↔ ".join(c))
        else: st.caption("— none —")
        st.markdown("**🔥 Complexity hotspots** (cyclomatic ≥ 10)")
        show_table(hots)
        st.markdown("**🏟 God files** (many symbols / high total complexity)")
        show_table(gods)
        secs = techdebt.secret_scan(idx)
        if secs:
            st.markdown("**🔐 Possible hardcoded secrets**")
            show_table(secs)
        with st.expander(f"Undocumented symbols ({len(undoc)})"):
            show_table(undoc)
    elif sub == "Coverage":
        cov = coverage.coverage_summary(idx)
        mc = st.columns(3)
        mc[0].metric("Test files", cov["n_test_files"])
        mc[1].metric("Functions referenced by tests", f"{cov['tested']}/{cov['total']}")
        mc[2].metric("Test-reference coverage", f"{int(cov['coverage']*100)}%")
        st.caption("Reference coverage — whether a test *mentions* the symbol; not runtime line coverage.")
        st.markdown("**Untested functions, by complexity**")
        show_table(cov["untested_complex"])
    else:
        kind = {"Decisions": "decisions", "Errors": "errors", "Memory": "memory"}[sub]
        repo, cfg = idx.meta.name, idx.config
        if sub == "Decisions":
            with st.form("dec_form"):
                title = st.text_input("Title")
                decision = st.text_area("Decision")
                alt = st.text_input("Alternatives considered")
                rat = st.text_area("Rationale")
                if st.form_submit_button("Add decision") and title:
                    engmemory.add(cfg, repo, kind, {"title": title, "decision": decision,
                                  "alternatives": alt, "rationale": rat, "status": "accepted"})
                    st.rerun()
            if full_model:
                dctx = st.text_input("Draft with the LLM — notes/context", key="dctx")
                if st.button("Draft a decision record") and dctx:
                    st.info(engmemory.draft_decision_llm(dctx[:80], dctx, full_model, extra))
        elif sub == "Errors":
            with st.form("err_form"):
                err = st.text_area("Error / traceback")
                cause = st.text_input("Cause")
                fix = st.text_area("Fix")
                if st.form_submit_button("Add error") and err:
                    engmemory.add(cfg, repo, kind, {"error": err[:200], "cause": cause, "fix": fix})
                    st.rerun()
            if full_model:
                tb = st.text_area("Diagnose with the LLM — paste a traceback", key="tb")
                if st.button("Diagnose") and tb:
                    st.info(engmemory.diagnose_error_llm(tb, idx, full_model, extra))
        else:
            with st.form("mem_form"):
                mtype = st.selectbox("Type", ["learned", "failed", "improved"])
                note = st.text_area("Note")
                if st.form_submit_button("Add entry") and note:
                    engmemory.add(cfg, repo, kind, {"type": mtype, "note": note})
                    st.rerun()
        st.markdown(f"**Saved {sub.lower()}**")
        items = engmemory.load(cfg, repo, kind)
        if not items:
            st.caption("— none yet —")
        for e in items:
            label = e.get("title") or e.get("error") or e.get("type", "entry")
            with st.expander(f"{e.get('date', '')} · {label}"):
                st.json({k: v for k, v in e.items() if k != "id"})
                if st.button("Delete", key="del_" + e["id"]):
                    engmemory.delete(cfg, repo, kind, e["id"]); st.rerun()

# ---------------- Media (Phase 6) ----------------
with tabs[8]:
    st.subheader("Learning media")
    mmode = st.radio("Make", ["Slide deck", "Audio overview", "Mind-map outline"], horizontal=True)
    if mmode == "Slide deck":
        style = st.selectbox("Audience", ["technical", "executive", "architecture"])
        if st.button("Generate deck (.pptx)", type="primary"):
            try:
                buf = io.BytesIO()
                media.build_pptx(idx, style, buf)
                st.download_button("Download deck (.pptx)", buf.getvalue(),
                                   file_name=f"{idx.meta.name}_{style}.pptx",
                                   mime="application/vnd.openxmlformats-officedocument.presentationml.presentation")
                st.success(f"{len(media.slide_outline(idx, style))} slides generated.")
            except Exception as e:
                st.error("Deck generation needs python-pptx (pip install python-pptx).")
                st.exception(e)
        with st.expander("Preview outline"):
            for sp in media.slide_outline(idx, style):
                st.markdown(f"**{sp['title']}**")
                if sp["type"] == "bullets":
                    for b in (sp["bullets"] or []):
                        st.caption("• " + str(b))
    elif mmode == "Audio overview":
        st.caption("A two-host (Maya & Dev) walkthrough." +
                   ("" if full_model else "  Set an LLM provider for a richer dialogue."))
        if "ascript" not in st.session_state or st.button("Generate script"):
            st.session_state["ascript"] = media.audio_script(idx, full_model, extra)
        sc = st.session_state.get("ascript", [])
        for t in sc:
            st.markdown(f"**{t['speaker']}:** {t['text']}")
        if sc:
            st.download_button("Download transcript (.txt)", media.script_to_text(sc),
                               file_name=f"{idx.meta.name}_overview.txt")
            if st.button("Export audio (.mp3)"):
                out = os.path.join(idx.config.data_dir, "overview.mp3")
                path, msg = media.synthesize_audio(sc, out)
                if path:
                    st.audio(path); st.caption("Voiced via " + msg)
                else:
                    st.info(msg)
    else:
        opts = ["(whole repo)"] + sorted(idx.graph.nodes.keys())
        def _q(n):
            nd = idx.graph.get(n)
            return n if n == "(whole repo)" else ((nd["data"].get("qualname") or n) if nd else n)
        root = st.selectbox("Root", opts, format_func=_q)
        r = "__repo__" if root == "(whole repo)" else root
        depth = st.slider("Depth", 1, 4, 3)
        md = media.mindmap_markdown(idx, r, depth)
        st.code(md, language="markdown")
        st.download_button("Download outline (.md)", md, file_name=f"{idx.meta.name}_mindmap.md")

# ---------------- Research (Phase 7) ----------------
with tabs[9]:
    st.subheader("Research mode")
    rmode = st.radio("View", ["Papers", "Compare approaches", "Implementation plan", "Summary"],
                     horizontal=True)
    if rmode == "Papers":
        papers = research.find_papers(idx)
        st.caption(f"{len(papers)} reference(s) detected in the repo (arXiv ids / DOIs).")
        show_table([{"ref": p["ref"], "kind": p["kind"], "cited in": ", ".join(p["files"])}
                    for p in papers])
        arxiv_refs = [p["ref"] for p in papers if p["kind"] == "arxiv"]
        choice = st.selectbox("Look up an arXiv paper", ["(pick or type below)"] + arxiv_refs)
        manual = st.text_input("…or an arXiv id", value="")
        aid = manual.strip() or ("" if choice.startswith("(") else choice)
        if aid and st.button("Look up"):
            with st.spinner("Querying arXiv…"):
                res = research.arxiv_lookup(aid)
            if not res:
                st.warning("No result.")
            elif res.get("error"):
                st.info("arXiv lookup unavailable (offline?): " + res["error"])
            else:
                st.markdown(f"### {res['title']}")
                st.caption(", ".join(res["authors"][:8]) +
                           (f"  ·  {res['published']}" if res["published"] else ""))
                st.write(res["summary"])
                if res.get("url"):
                    st.markdown(f"[arXiv]({res['url']})")
    elif rmode == "Compare approaches":
        approaches = st.text_input("Approaches (comma-separated)", value="YOLO, DETR, DINO")
        if st.button("Build comparison matrix"):
            if not full_model:
                st.info("Set an LLM provider in the sidebar to generate a comparison.")
            else:
                with st.spinner("Comparing…"):
                    st.markdown(research.comparison_matrix_llm(approaches, full_model, extra))
    elif rmode == "Implementation plan":
        topic = st.text_input("What do you want to implement?", value="Add a DINO-style backbone")
        if st.button("Draft a plan"):
            if not full_model:
                st.info("Set an LLM provider to generate a plan grounded in this repo.")
            else:
                with st.spinner("Planning…"):
                    st.markdown(research.implementation_plan_llm(topic, idx, full_model, extra))
    else:
        rs = research.research_summary(idx)
        st.markdown(f"**Papers referenced:** {rs['n_papers']}")
        show_table([{"ref": p["ref"], "kind": p["kind"]} for p in rs["papers"]])
        st.caption("Key classes: " + (", ".join(rs["classes"]) or "—"))
        if full_model and st.button("Novelty analysis"):
            with st.spinner("Analysing…"):
                st.info(research.novelty_summary_llm(idx, full_model, extra))

# ---------------- Portfolio (Phase 8) ----------------
with tabs[10]:
    st.subheader("Portfolio")
    st.caption("Turn what KnowIT knows into shareable artifacts." +
               ("" if full_model else "  Set an LLM provider for polished prose; "
                "otherwise you get a solid structural draft."))
    labels = {"report": "Project report", "blog": "Blog post", "resume": "Résumé bullets",
              "linkedin": "LinkedIn post", "paper": "Paper draft"}
    kind = st.radio("Artifact", list(labels), horizontal=True, format_func=lambda k: labels[k])
    if st.button("Generate", type="primary"):
        with st.spinner("Writing…"):
            st.session_state["pf_md"] = portfolio.generate(idx, kind, full_model, extra)
            st.session_state["pf_kind"] = kind
    md = st.session_state.get("pf_md")
    if md:
        st.markdown(md)
        st.download_button("Download (.md)", md,
                           file_name=f"{idx.meta.name}_{st.session_state.get('pf_kind', 'artifact')}.md")

    st.divider()
    if st.button("Export understanding as a shareable HTML page"):
        _html = export_site.export_html(idx)
        st.download_button("Download understanding.html", _html,
                           file_name=f"{idx.meta.name}_understanding.html", mime="text/html")
        st.success("Generated a self-contained HTML page (no external assets).")

# ---------------- Eval ----------------
with tabs[11]:
    st.subheader("Evaluation harness")
    st.caption("Scores retrieval hit + keyword coverage (optional LLM-as-judge); ≥80% gate.")
    qpath = st.text_input("Questions file", value=DEFAULT_QUESTIONS)
    judge = st.text_input("Judge model (optional, raw litellm string)", value="")
    if st.button("Run eval"):
        try:
            with st.spinner("Running eval …"):
                rows, summary = run_eval(idx, load_questions(qpath), judge_model=judge)
            mm = st.columns(3)
            mm[0].metric("Passed", f"{summary['passed']}/{summary['scored']}")
            mm[1].metric("Pass rate", f"{summary['pass_rate']*100:.0f}%")
            mm[2].metric("Gate ≥80%", "✅ PASS" if summary["gate_pass"] else "⚠ NEEDS WORK")
            show_table([
                {"id": r["id"], "passed": r["passed"], "retrieval_hit": r["retrieval_hit"],
                 "kw_coverage": r["kw_coverage"], "judge": r["judge"],
                 "top_files": ", ".join(r["top_files"]), "question": r["question"]}
                for r in rows])
        except Exception as e:
            st.exception(e)
