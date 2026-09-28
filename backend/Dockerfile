# Topaz-VBE backend image.
#
# Build context: ~/workspace/topaz-vbe  (so both engine/ and backend/ are visible)
#   docker build -f backend/Dockerfile -t topaz-vbe-backend .
#
# Run (compose or plain docker):
#   docker run -p 8000:8000 \
#     -e DATABASE_URL=postgresql://user:pass@db:5432/topaz \
#     -e SECRET_KEY=... -e ADMIN_USER=... -e ADMIN_PASSWORD=... \
#     topaz-vbe-backend
#
# Engine subprocesses run as: python -m topaz_engine.cli --industry I --year Y --quarter Q
# with cwd=/app/engine and DATABASE_URL passed through from this container's env.

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/engine:/app/backend \
    ENGINE_DIR=/app/engine

WORKDIR /app

# Copy the simulation engine (built by the engine builder) and the backend.
COPY engine/ /app/engine/
COPY backend/ /app/backend/

RUN pip install --no-cache-dir -r /app/backend/requirements.txt

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--app-dir", "/app/backend", "--host", "0.0.0.0", "--port", "8000"]
