# Topaz-VBE engine-worker image.
#
# Build context: ~/workspace/topaz-vbe  (so engine/ is visible)
#   docker build -f engine/Dockerfile -t topaz-vbe-worker .
#
# Run (compose or plain docker):
#   docker run -e DATABASE_URL=<redacted> \
#              -e WORKER_POLL_SECONDS=5 \
#              topaz-vbe-worker
#
# The worker polls the quarter_jobs table and runs the deterministic batch
# (topaz_engine.runner.run_quarter) for each claimed job. It is the
# event-driven counterpart of the backend's QUARTER_ROLL_MODE=queue mode.
# Any number of replicas may run: jobs are claimed with
# SELECT ... FOR UPDATE SKIP LOCKED.

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

COPY engine/topaz_engine/ /app/topaz_engine/

# engine/requirements.txt pins the runtime deps (psycopg[binary]).
COPY engine/requirements.txt /tmp/engine-requirements.txt
RUN pip install --no-cache-dir -r /tmp/engine-requirements.txt

CMD ["python", "-m", "topaz_engine.worker"]
