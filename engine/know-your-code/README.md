# Legend — Orchestraty module

Plug-and-play **codebase intelligence** for Orchestraty. Connect a Git repo or a zip, the
module indexes it (symbols + embeddings), and users can **ask questions** (RAG with cited
sources), browse **files**, view the **architecture** dependency graph, and generate an
**onboarding tour** — all inside the existing dashboard shell, sharing the host's auth/RBAC.

It reuses the host's primitives (auth, DB, Celery, embeddings, Qdrant, LLM) and never rolls
its own. Backend is FastAPI + SQLAlchemy 2.x async; frontend is React 19 + Vite + TS with the
host's CSS classes and design tokens.

---

## 1. Drop in

From inside `ai-operating-system/`:

```bash
cp -r /path/to/legend .
cd legend
./integrate.sh
```

`integrate.sh` copies (it does **not** edit host files):

| From (this module)        | To (host)                                         |
|---------------------------|---------------------------------------------------|
| `backend/*` (no `migrations/`) | `core/modules/know_your_code/`  ← underscores, Python pkg |
| `backend/migrations/*.py` | `alembic/versions/`                               |
| `frontend/*`              | `frontend/Frontend/src/modules/legend/`   |

> The **backend** folder is `know_your_code` (underscores) so `core.modules.know_your_code`
> imports work. The **frontend** folder is `legend` (hyphens) and uses relative TS
> imports. `integrate.sh` handles both.

---

## 2. Wire it in (4 edits + 2 setup steps, ~2 min)

### 2a. Mount the backend router

In `ai-operating-system/app.py`, with the other router imports:

```python
from core.modules.know_your_code.routes import router as know_your_code_router
```

In the route-mounting section:

```python
app.include_router(know_your_code_router, prefix="/api/v1", tags=["legend"])
```

### 2b. Register the frontend routes

In `frontend/Frontend/src/AppRouter.tsx`:

```tsx
import { kycRoutes } from './modules/legend/routes';
```

Inside the **protected `/app` route**'s children (next to the other module routes):

```tsx
{kycRoutes.map((r) => <Route key={r.path} path={r.path} element={r.element} />)}
```

### 2c. Add the navbar item

In `frontend/Frontend/src/components/Navbar/Navbar.tsx`, in the products dropdown (match the
existing item markup):

```tsx
<Link to="/app/legend" className="nav-dropdown__item">Legend</Link>
```

### 2d. Add the sidebar entry

In `frontend/Frontend/src/layouts/DashboardLayout.tsx`, in the sidebar items list (match the
existing entry shape — icon optional):

```tsx
{ label: 'Legend', to: '/app/legend' },
```

### 2e. Chain the migration

Open the copied `alembic/versions/0001_kyc_init.py` and set `down_revision` to your current
head:

```bash
alembic heads          # copy the printed revision id
# then in 0001_kyc_init.py:  down_revision = "<that id>"
```

### 2f. Add the frontend deps

```bash
cd frontend/Frontend
npm i d3-force prismjs
npm i -D @types/d3-force        # types; prismjs ships its own
```

---

## 3. Apply & restart

```bash
cd ai-operating-system
alembic upgrade head
docker compose restart api celery-worker
cd frontend/Frontend && npm install && npm run build      # or your dev server
```

Log in as any non-superadmin user → the **Legend** item appears in the navbar →
clicking it lands on the module home inside the existing dashboard chrome.

---

## 4. Host primitives this module imports

These are the **only** names that must match your host. If any differ, adjust the imports in
`core/modules/know_your_code/` (they're isolated to a handful of files):

| Import                                            | Used for                                  |
|---------------------------------------------------|-------------------------------------------|
| `core.db.base.Base`                               | shared declarative Base (models.py)       |
| `core.db.session.get_db`                          | request-scoped `AsyncSession` (routes)    |
| `core.db.session.async_session_factory`           | Celery task sessions (tasks.py)           |
| `core.auth.dependencies.get_current_user`         | JWT → `User` (all routes)                 |
| `core.auth.dependencies.require_role`             | RBAC for `DELETE /repos/{id}` (admin+)    |
| `core.models.user.User` (`.id`, `.org_id`, opt. `.llm_keys`) | tenant scoping + per-user LLM keys |
| `core.tasks.app.celery_app`                       | `@celery_app.task` (tasks.py)             |
| `core.embeddings.service.embed_texts(List[str])`  | symbol + query embeddings                 |
| `core.vector.qdrant_client`                       | per-repo collection `kyc_<repo_id>`       |
| `core.llm.service.complete(messages, model, user_keys, max_tokens)` | Q&A + tour generation |

The LLM response is read defensively as `resp["choices"][0]["message"]["content"]` with a
string fallback — adjust `services/qa.py:_extract` if your `complete()` returns a different
shape.

### Environment

| Var          | Default     | Purpose                                                        |
|--------------|-------------|----------------------------------------------------------------|
| `KYC_WORKDIR`| `/data/kyc` | where repos are cloned/extracted and read for file content. **Mount a persistent volume** shared by `api` + `celery-worker`. |

### Optional backend deps (better parsing)

Parsing prefers **tree-sitter** for Python/JS/TS/Go/Java and falls back to stdlib `ast`
(Python) or regex (others) when grammars aren't installed — so it works either way. For full
fidelity:

```bash
pip install tree_sitter tree_sitter_languages
```

---

## 5. API surface (mounted at `/api/v1/legend`)

```
POST   /repos                          create + queue indexing (git starts immediately)
POST   /repos/{id}/upload              multipart zip upload → queues indexing  (upload flow)
GET    /repos                          list (scoped to org)
GET    /repos/{id}                     detail + status + progress  (poll every 2s while indexing)
DELETE /repos/{id}                     delete (admin / superadmin only)
GET    /repos/{id}/files               file tree
GET    /repos/{id}/files/{fid}/content raw text (path-traversal guarded)
POST   /repos/{id}/qa                  ask a question (RAG → cited answer)
GET    /repos/{id}/qa-history          past turns (this user)
GET    /repos/{id}/architecture        dependency graph JSON (nodes + edges)
POST   /repos/{id}/tour                generate onboarding tour (LLM)
GET    /repos/{id}/tour                fetch saved tour
```

`/repos/{id}/upload` is an addition to the brief's table — it's the second half of the
`source: 'upload'` flow (create the row, then stream the zip). `kycApi.uploadZip()` calls it.

### Data model (tables prefixed `kyc_`)

`kyc_repos`, `kyc_files`, `kyc_symbols`, `kyc_qa_sessions`, `kyc_qa_turns`, `kyc_tours`.
Every list/detail query is scoped by `current_user.org_id`. Vectors live in Qdrant
collection `kyc_<repo_id>`, one point per symbol.

---

## 6. Acceptance checklist mapping

1. **`./integrate.sh` copies cleanly** — yes; no host files touched.
2. **4 wiring snippets < 2 min** — §2a–2d above, copy-paste.
3. **`alembic upgrade head` creates tables, no conflicts** — `0001_kyc_init.py`, all `kyc_*`.
4. **Restart brings module up** — router + Celery tasks register on import.
5. **Non-superadmin sees navbar item → module home in existing chrome** — §2c/2d; pages use host classes.
6. **List endpoints exclude other orgs** — every query filters `org_id == current_user.org_id`.
7. **Long ops show live progress** — indexing runs in Celery; UI polls `GET /repos/{id}` every 2s and renders the `progress-bar`.
8. **Visual rhythm matches host** — host CSS classes (`page-header`, `card`, `tabs`, `chip`, `progress-bar`, …), host tokens (`--dash-*`, `--brand-*`), `<orc-spinner>`, no Tailwind/UI kit.

---

## 7. Verification status

- **Backend**: every module byte-compiles; the host-independent services
  (`repo_loader`, `parser`, `graph`) are unit-tested (symbol extraction + dependency graph
  on a real sample repo). The host-coupled paths (`indexer`, `qa`, `routes`, `tasks`, the
  migration) are syntax-verified — they import `core.*`, so they execute only inside
  Orchestraty.
- **Frontend**: written to the host's documented patterns; type-check/build happens in the
  host toolchain after `npm i d3-force prismjs`.
- **Screen recording**: capture the 30-second clip after integration in your environment
  (it needs the running host). A quick smoke path: log in → Legend → *Connect a Git
  repo* → watch the progress bar → Overview/Files/Q&A/Architecture/Tour.
---

## 8. Security posture

Hardening applied to the untrusted inputs (a clone URL and an uploaded zip):

- **Clone URL allow-list** — only `http`/`https`/`ssh`/`git` transports (blocks `ext::` RCE and
  `file://` local-file SSRF), enforced both in code and via `GIT_ALLOW_PROTOCOL`. If you need
  another transport, edit `ALLOWED_GIT_SCHEMES` in `services/repo_loader.py`.
- **Argument-injection guard** — clone runs `git clone … -- <url> <dir>`; URLs starting with
  `-` are rejected, so a URL can't smuggle a git option.
- **No credential prompts** — `GIT_TERMINAL_PROMPT=0`; embedded credentials are redacted out of
  any stored error message.
- **Safe zip extraction** — skips entries that escape the target dir (zip-slip) and symlink
  entries, and aborts past `MAX_ARCHIVE_BYTES` uncompressed (zip-bomb).
- **Symlink-safe reads** — indexing skips symlinks; `…/files/{id}/content` resolves real paths
  and refuses anything outside the repo root.
- **Tenant isolation** — every query filters `org_id == current_user.org_id`; cross-org access
  returns 404. `DELETE` is admin/superadmin only and also drops the Qdrant collection **and the
  on-disk clone** (source is not retained after delete).

Residual items to consider for your environment: cap the multipart upload size at the gateway
(the zip-bomb guard covers extraction, not the initial upload), and run the Celery worker that
clones untrusted repos with limited network egress.
