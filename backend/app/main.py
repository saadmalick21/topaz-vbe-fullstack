"""Topaz-VBE backend: FastAPI application entrypoint."""

from __future__ import annotations

import hashlib
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .auth import AuthError
from .db import get_conn
from .routers import admin, auth, decisions, reports

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("topaz.main")

ADMIN_USER = os.environ.get("ADMIN_USER", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")


def _bootstrap_admin() -> None:
    """Create the initial admin account if the admins table is empty.

    DEMO-GRADE SECURITY: the password is stored as a plain SHA256 hex digest
    (see auth.verify_admin_credentials). This is a deliberate simplification
    for the university assignment replica -- a production deployment MUST use
    bcrypt/argon2 with a per-user salt. If the database is unreachable (or the
    admins table does not exist yet -- migrations run separately), bootstrap
    is skipped with a warning and the app still starts.
    """
    try:
        with get_conn() as conn:
            count = conn.execute("SELECT COUNT(*) AS c FROM admins").fetchone()["c"]
            if int(count) == 0:
                digest = hashlib.sha256(ADMIN_PASSWORD.encode("utf-8")).hexdigest()
                conn.execute(
                    "INSERT INTO admins (username, password_hash) VALUES (%s, %s)",
                    (ADMIN_USER, digest),
                )
                log.warning(
                    "Admin bootstrap: created admin user '%s' with DEFAULT DEMO "
                    "credentials (SHA256 hex digest -- demo-grade, not production-safe). "
                    "Change ADMIN_USER/ADMIN_PASSWORD immediately.",
                    ADMIN_USER,
                )
            else:
                log.info("Admin bootstrap: admins table already populated; skipping.")
    except Exception as exc:  # DB down or migrations not run yet: start anyway.
        log.warning("Admin bootstrap skipped: %s", exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    _bootstrap_admin()
    yield


app = FastAPI(title="Topaz-VBE Backend", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "*"],
    allow_credentials=False,  # wildcard origin cannot be combined with credentials
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(AuthError)
async def auth_error_handler(request: Request, exc: AuthError):
    return JSONResponse(status_code=exc.status_code, content={"error": exc.message})


@app.get("/api/health")
def health():
    return {"ok": True}


app.include_router(auth.router)
app.include_router(decisions.router)
app.include_router(reports.router)
app.include_router(admin.router)


# Serve the React frontend (single-origin deploy: frontend + backend on one URL).
# The Docker image copies frontend/dist to /app/frontend-dist.
# API routes (/api/*) are matched first; everything else serves the SPA.
try:
    from fastapi.staticfiles import StaticFiles

    _FRONTEND_DIR = os.environ.get("FRONTEND_DIR", "/app/frontend-dist")
    if os.path.isdir(_FRONTEND_DIR):
        app.mount(
            "/",
            StaticFiles(directory=_FRONTEND_DIR, html=True),
            name="frontend",
        )
        log.info("Serving frontend from %s", _FRONTEND_DIR)
    else:
        log.info("Frontend dir %s not found; API-only mode.", _FRONTEND_DIR)
except Exception as exc:  # staticfiles not installed or other issue
    log.warning("Frontend static serving disabled: %s", exc)
