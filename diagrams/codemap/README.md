# codemap — interactive, drill-down architecture mindmaps for any codebase

One stdlib-only Python script that turns *any* source folder into a single,
self-contained, interactive HTML with **three levels of zoom**:

1. **Area mindmap** — areas are nodes (sized by lines, coloured by dependency
   layer), edges are "imports-from". Hover to trace, drag/scroll to move.
2. **Area drill-in** — click an area → it opens and lists every file inside,
   each with its classes, functions and import counts.
3. **File view** — click a file → it opens full-screen with the **source on the
   right** and an auto **deep-dive on the left**: what it defines, how it wires
   in (depends-on / used-by, both clickable to hop file-to-file), and every
   class and function with signatures + docstrings.

No installation, no dependencies, nothing to import from the target project. It
reads the code statically, so it works even when the project can't run.

## Use it
```bash
python codemap.py <path-to-repo>           # -> <repo>_architecture.html
python codemap.py ./proj --title "Proj" --open
python codemap.py ./proj -o docs/arch.html --md
python codemap.py ./proj --depth 2          # force grouping depth (0 = auto)
python codemap.py ./proj --ext .py,.ts      # restrict languages
python codemap.py ./proj --no-src           # smaller html, no code in file view
python codemap.py ./proj --max-src 120      # cap embedded KB per file (default 200)
```

## How it decides things
- **Areas** = directories (depth auto-chosen to keep ~5–25 areas, or `--depth N`).
- **Layers** = dependency depth, so entry-points sit on top and leaf utilities at
  the bottom. Cycles are handled.
- **Explanations** come from the code's own docstrings (Python module/class/
  function docstrings; leading `/** … */` in JS/TS). No docstring → an auto
  summary from the file's classes/functions. The file-view "role" line
  (entry-point / hub / leaf / mid-chain) is inferred from the import graph.

## Languages
- **Python** — full AST (classes + methods, functions + signatures, imports, docstrings).
- **JS / TS** (`.js .jsx .ts .tsx .mjs .cjs`) — best-effort regex (classes,
  functions, relative imports).
- Anything added with `--ext` is listed with line counts.

Skips noise dirs (`.git`, `node_modules`, `venv`, `build`, `dist`, …) without
descending into them. **Tip:** if your repo also holds a giant non-code folder
(datasets, image dumps), point codemap at the source subfolder, or add that
folder name to `SKIP_DIRS` at the top of the script, so the walk stays fast.

## Notes & limits
- Edges are import-level, not call-level. Third-party/stdlib imports are ignored
  (they aren't part of *your* architecture).
- The whole repo's source is embedded so the file view works offline; for very
  large repos use `--no-src` or `--max-src` to keep the html small.
- Re-run any time the code changes — the map regenerates from scratch.
