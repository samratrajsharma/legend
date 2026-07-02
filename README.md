# Know Your Code

Codebase intelligence that maps any repository, explains it file by file, answers
questions about it with your own LLM, and tracks how it changes over time.

It is built from three components that live side by side in this folder and wire
together by **relative path**:

| Folder | What it is |
|---|---|
| `app/` | The product — a React + FastAPI web app. The backend is a thin REST layer over the engine. |
| `engine/` | The analysis engine: the `knowit` Python package (indexing, retrieval, narration, over-time tracking). Imported by the app. |
| `diagrams/` | `codemap` — a standalone, stdlib-only script that renders interactive architecture mindmaps. Imported by the app. |

## How they wire together

`app/backend/app.py` adds the engine and the diagram tool to `sys.path` by
relative path:

- `../../engine` → imported as the `knowit.*` package
- `../../diagrams/codemap` → imported as the `codemap` module

Because those paths are relative, **the three folders must stay siblings inside
`know-your-code/`.** If you move one, update the two path constants at the top of
`app/backend/app.py`.

## Run it

```powershell
cd app
.\run.ps1      # installs deps, starts backend (:8100) + frontend (:5273)
.\stop.ps1     # stops both
```

See `app/README.md` for ports and per-page detail.
