# Know Your Code — Standalone Testbed

A localhost-only React + FastAPI front-end for the existing KnowIT engine. Same
visual design language as Orchestraty (Montserrat font, indigo/violet palette,
dashboard layout, card patterns) — but a fully independent system with its own
ports, no auth, no database.

This is **not** the Orchestraty module. It's a testbed so you can exercise
KnowIT end-to-end without touching the live Orchestraty system.

## Ports

| Service | Port |
|---|---|
| Frontend (Vite dev server) | http://localhost:5273 |
| Backend (FastAPI + uvicorn) | http://localhost:8100 |
| Backend API docs | http://localhost:8100/docs |

These were picked to avoid clashing with Orchestraty (5173/5174/8000) and
SecureCode (5373/8200).

## Quick start

```powershell
# From this folder
.\run.ps1
```

That installs Python deps in a `.venv/`, installs npm deps, and starts both
the backend and frontend in two visible terminal windows. Hit `Ctrl+C` in
either to stop, or run `.\stop.ps1` to kill both.

First run takes a few minutes. Subsequent runs start in seconds.

## Layout

```
know-your-code/app/
├── backend/
│   ├── app.py            # FastAPI routes — thin wrappers over knowit/*
│   ├── main.py           # uvicorn launcher
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── index.html
│   ├── package.json
│   ├── vite.config.ts
│   ├── tsconfig.json
│   ├── public/           # logo + favicon (copied from Orchestraty)
│   └── src/
│       ├── main.tsx
│       ├── App.tsx
│       ├── index.css     # Orchestraty design tokens (copied)
│       ├── api/client.ts
│       ├── components/
│       ├── layouts/
│       └── pages/        # 12 pages, one per KnowIT tab
├── run.ps1
├── stop.ps1
└── README.md
```

The backend imports the engine from
`../engine/knowit/` via a `sys.path.insert`, and the codemap diagram tool from
`../diagrams/codemap/`. Both sit next to this folder under `know-your-code/`; if
you move them, update the two path constants at the top of `backend/app.py`.

## How to use

1. Run `.\run.ps1`.
2. Browser opens to http://localhost:5273.
3. On the Home page, paste a local repo path (e.g. `C:\\Users\\prave\\some-repo`)
   or a git URL, and click **Connect**.
4. The backend runs `build_index()` and returns a repo ID.
5. Navigate to Overview / Files / Ask / etc. for that repo.

## Status (session 1)

- ✅ Foundation: backend + frontend skeletons + design system + run scripts
- ✅ Pages built end-to-end: Home, Overview, Ask
- ⏳ Stubbed pages: Files, Diagrams, API & DB, Learn, Track, Intel, Media, Research, Portfolio, Eval
  (sidebar links work; pages show a "Coming in next session" placeholder)

The remaining pages will be built in subsequent sessions following the same
pattern as the three completed ones.
