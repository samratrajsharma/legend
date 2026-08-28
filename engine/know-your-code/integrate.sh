#!/usr/bin/env bash
# integrate.sh — run from the legend/ module folder, against the parent Orchestraty repo.
# Copies files into the host's directories. It does NOT edit host files: apply the 4 wiring
# snippets from README.md by hand afterwards (~2 min).
set -euo pipefail

BACKEND_PKG="know_your_code"     # Python import path => core.modules.know_your_code  (underscores!)
FRONTEND_DIR="legend"    # Frontend folder name (hyphens; TS uses relative imports)
ROOT="$(cd .. && pwd)"

echo "▶ Integrating Legend into: $ROOT"
[ -f "$ROOT/app.py" ] || { echo "✗ $ROOT/app.py not found. Run this from legend/ inside ai-operating-system/."; exit 1; }

# 1. Backend -> core/modules/know_your_code/  (migrations excluded; they go to alembic)
mkdir -p "$ROOT/core/modules/$BACKEND_PKG"
[ -f "$ROOT/core/modules/__init__.py" ] || touch "$ROOT/core/modules/__init__.py"
cp -r backend/* "$ROOT/core/modules/$BACKEND_PKG/"
rm -rf "$ROOT/core/modules/$BACKEND_PKG/migrations"

# 2. Migrations -> alembic/versions/
mkdir -p "$ROOT/alembic/versions"
cp backend/migrations/*.py "$ROOT/alembic/versions/"

# 3. Frontend -> frontend/Frontend/src/modules/legend/
mkdir -p "$ROOT/frontend/Frontend/src/modules/$FRONTEND_DIR"
cp -r frontend/* "$ROOT/frontend/Frontend/src/modules/$FRONTEND_DIR/"

echo "✓ Files copied."
echo
echo "NEXT — apply the wiring snippets from README.md (exact code there):"
echo "  1. app.py ............... mount the router"
echo "  2. AppRouter.tsx ........ register kycRoutes under the protected /app route"
echo "  3. Navbar.tsx ........... add the 'Legend' nav item"
echo "  4. DashboardLayout.tsx .. add the sidebar entry"
echo "  5. the migration ........ set down_revision to your current head ('alembic heads')"
echo "  6. frontend deps ........ npm i d3-force prismjs   (dev: npm i -D @types/d3-force)"
echo "  (optional) backend ...... pip install tree_sitter tree_sitter_languages  # better parsing"
echo
echo "Then:"
echo "  cd \"$ROOT\" && alembic upgrade head && docker compose restart api celery-worker"
echo "  cd \"$ROOT/frontend/Frontend\" && npm install && npm run build"
