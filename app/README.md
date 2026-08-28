# Legend — app

A localhost-only React + FastAPI front-end for the `legend` engine. Fully
independent: its own ports, no auth, no database.

## Ports

| Service | Port |
|---|---|
| Frontend (Vite dev server) | http://localhost:5273 |
| Backend (FastAPI + uvicorn) | http://localhost:8100 |
| Backend API docs | http://localhost:8100/docs |

## Quick start

```powershell
.\run.ps1
```

Installs Python deps in `.venv/`, installs npm deps, and starts the backend and
frontend in two terminal windows. `Ctrl+C` in either, or `.\stop.ps1`, stops both.
First run takes a few minutes; later runs start in seconds.

## Layout

```
app/
├── backend/
│   ├── app.py            # FastAPI routes — thin wrappers over legend/*
│   ├── main.py           # uvicorn launcher
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── index.html
│   ├── public/           # icon + favicon
│   └── src/              # React 19 + Vite + TS (pages, layouts, components)
├── run.ps1
├── stop.ps1
└── README.md
```

The backend imports the engine from `../engine/legend/` and the codemap tool from
`../diagrams/codemap/` via `sys.path.insert`. If you move them, update the two path
constants at the top of `backend/app.py`.

## Use

1. `.\run.ps1` → browser opens http://localhost:5273.
2. On Home, paste a local repo path or a git URL, click **Connect**.
3. The backend runs `build_index()` and returns a repo id.
4. Browse Overview / Files / Ask / Timeline / Intel / etc. for that repo.
