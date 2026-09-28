# Topaz-VBE combined image: React frontend (served by FastAPI) + backend + engine.
#
# Single-origin deploy: the frontend calls /api (same host), so no VITE_API_URL
# is needed. The backend serves frontend/dist via StaticFiles (see main.py).
#
# Build context: ~/workspace/topaz-vbe
#   docker build -f Dockerfile.combined -t topaz-vbe-combined .

# ---- Stage 1: build the React frontend ----
FROM node:20-slim AS frontend-build
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci --no-audit --no-fund 2>&1 | tail -2
COPY frontend/ ./
# No VITE_API_URL: api.js falls back to relative "/api" (same origin).
RUN npm run build

# ---- Stage 2: Python backend + engine + frontend dist ----
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/engine:/app/backend \
    ENGINE_DIR=/app/engine \
    FRONTEND_DIR=/app/frontend-dist

WORKDIR /app

COPY engine/ /app/engine/
COPY backend/ /app/backend/
COPY db/ /app/db/
COPY --from=frontend-build /build/dist/ /app/frontend-dist/

RUN pip install --no-cache-dir -r /app/backend/requirements.txt

EXPOSE 8000

# Migrations run on startup (tracked, safe to re-run), then uvicorn.
# Uses $PORT if set (Hugging Face, Koyeb, Render), else 8000.
CMD ["sh", "-c", "python /app/db/migrate.py && uvicorn app.main:app --app-dir /app/backend --host 0.0.0.0 --port ${PORT:-8000}"]
