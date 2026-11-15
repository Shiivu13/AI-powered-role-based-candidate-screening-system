#!/usr/bin/env bash
# Builds the whole app for Vercel with the Build Output API:
#   static/                     the Vite frontend
#   functions/api/index.func    the FastAPI backend as a Python 3.12 function
# so the frontend and /api are served from one deployment with no settings.
set -euo pipefail

HERE="$(cd "$(dirname "$0")/.." && pwd)"          # frontend/
BACKEND="$(cd "$HERE/../backend" && pwd)"
OUT="${BOA_OUT:-$HERE/.vercel/output}"
FUNC="$OUT/functions/api/index.func"

echo "==> Building frontend"
(cd "$HERE" && npx vite build)

rm -rf "$OUT"
mkdir -p "$OUT/static" "$FUNC/api"
cp -r "$HERE/dist/." "$OUT/static/"

echo "==> Bundling backend"
cp -r "$BACKEND/app" "$FUNC/app"
cp -r "$BACKEND/kb" "$FUNC/kb"
cp "$BACKEND/../docs/benchmarks/retrieval.json" "$FUNC/kb/retrieval_benchmark.json" 2>/dev/null || true
cp "$HERE/vercel/index.py" "$FUNC/api/index.py"
cp "$HERE/vercel/vc__handler__python.py" "$FUNC/vc__handler__python.py"

echo "==> Installing Python dependencies (manylinux, CPython 3.12)"
REQ="$BACKEND/requirements-vercel.txt"
PY="$(command -v python3.12 || command -v python3 || true)"
if [ -n "$PY" ] && "$PY" -m pip --version >/dev/null 2>&1; then
  "$PY" -m pip install --quiet --disable-pip-version-check --target "$FUNC" \
    --platform manylinux2014_x86_64 --platform manylinux_2_28_x86_64 --implementation cp --python-version 3.12 \
    --only-binary=:all: -r "$REQ"
elif command -v uv >/dev/null 2>&1; then
  uv pip install --quiet --target "$FUNC" --python-platform x86_64-manylinux2014 \
    --python-version 3.12 -r "$REQ"
else
  echo "No pip or uv available in the build image" >&2
  exit 1
fi
find "$FUNC" -name "__pycache__" -type d -prune -exec rm -rf {} +

cat > "$FUNC/.vc-config.json" <<'JSON'
{
  "runtime": "python3.12",
  "handler": "vc__handler__python.vc_handler",
  "maxDuration": 60
}
JSON

cat > "$OUT/config.json" <<'JSON'
{
  "version": 3,
  "routes": [
    { "handle": "filesystem" },
    { "src": "^/api(?:/(.*))?$", "dest": "/api/index", "check": true },
    { "src": "^(?:/(.*))$", "dest": "/index.html", "check": true }
  ]
}
JSON

echo "==> Done: $(du -sh "$FUNC" | cut -f1) function bundle"
