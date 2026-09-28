"""Authentication: team login, admin login, JWT issuance and dependencies.

JWT claims: {sub, role, team_id?, industry_id?}, HS256, 12h expiry.
SECRET_KEY comes from the environment.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .db import get_conn

log = logging.getLogger("topaz.auth")

SECRET_KEY = os.environ.get("SECRET_KEY", "change-me-dev-secret")
if os.environ.get("SECRET_KEY") is None:
    log.warning(
        "SECRET_KEY not set; using built-in dev secret. Set SECRET_KEY in production."
    )

TOKEN_TTL = timedelta(hours=12)
ALGORITHM = "HS256"

bearer_scheme = HTTPBearer(auto_error=False)


class AuthError(Exception):
    """Raised by auth dependencies; converted to {"error": ...} JSON in main.py."""

    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.message = message


def issue_token(*, sub: str, role: str, team_id: int | None = None,
                industry_id: int | None = None) -> str:
    now = datetime.now(timezone.utc)
    claims: dict = {
        "sub": sub,
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int((now + TOKEN_TTL).timestamp()),
    }
    if team_id is not None:
        claims["team_id"] = team_id
    if industry_id is not None:
        claims["industry_id"] = industry_id
    return jwt.encode(claims, SECRET_KEY, algorithm=ALGORITHM)


def _decode(token: str) -> dict:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise AuthError(401, "Token has expired. Please log in again.")
    except jwt.InvalidTokenError:
        raise AuthError(401, "Invalid token. Please log in again.")


def _require_bearer(creds: HTTPAuthorizationCredentials | None) -> dict:
    if creds is None or not creds.credentials:
        raise AuthError(401, "Not authenticated. Provide a Bearer token.")
    return _decode(creds.credentials)


def _safe_compare(a: str, b: str) -> bool:
    """Constant-time string comparison that never raises.

    hmac.compare_digest(str, str) throws TypeError when either side holds
    non-ASCII characters (e.g. a pasted en-dash in an identity number).
    A login attempt must fail closed with False -- never 500.
    """
    try:
        return hmac.compare_digest(a, b)
    except TypeError:
        return False


def verify_team_credentials(simulation_code: str, group_number: int,
                            company_number: int, identity_number: str) -> dict | None:
    """Return the team row dict on success, None on any mismatch.

    The lookup is by (simulation_code, group_number, company_number); the
    identity_number (the secret credential) is compared in constant time and
    the 401 message never reveals which field mismatched.
    """
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT t.*, i.id AS _industry_id, i.name AS _industry_name,
                   i.simulation_code AS _simulation_code, i.status AS _industry_status
            FROM teams t
            JOIN industries i ON i.id = t.industry_id
            WHERE i.simulation_code = %s
              AND t.group_number = %s
              AND t.company_number = %s
              AND t.active = true
            """,
            (simulation_code, group_number, company_number),
        ).fetchone()
    if row is None:
        # Constant-time dummy compare so a missing row is not distinguishable.
        _safe_compare("dummy-identity", identity_number)
        return None
    if not _safe_compare(str(row["identity_number"]), identity_number):
        return None
    return row


def verify_admin_credentials(username: str, password: str) -> dict | None:
    """Return the admin row on success, None otherwise.

    DEMO-GRADE: password is stored as a plain SHA256 hex digest (no salt).
    This is a deliberate, documented simplification for the university
    assignment -- production deployments MUST use bcrypt/argon2.
    """
    digest = hashlib.sha256(password.encode("utf-8")).hexdigest()
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM admins WHERE username = %s", (username,)
        ).fetchone()
    if row is None:
        hmac.compare_digest("dummy-hash", digest)
        return None
    if not hmac.compare_digest(str(row["password_hash"]), digest):
        return None
    return row


def get_current_team(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> dict:
    """Dependency: valid team JWT. 401 if missing/invalid, 403 if not a team."""
    payload = _require_bearer(creds)
    if payload.get("role") != "team":
        raise AuthError(403, "Team access required.")
    team_id = payload.get("team_id")
    industry_id = payload.get("industry_id")
    if team_id is None or industry_id is None:
        raise AuthError(401, "Invalid token claims. Please log in again.")
    with get_conn() as conn:
        team = conn.execute(
            "SELECT * FROM teams WHERE id = %s AND active = true", (team_id,)
        ).fetchone()
        industry = conn.execute(
            "SELECT * FROM industries WHERE id = %s", (industry_id,)
        ).fetchone()
    if team is None or industry is None:
        raise AuthError(401, "Account no longer valid. Please log in again.")
    return {"team": team, "industry": industry,
            "team_id": team_id, "industry_id": industry_id}


def get_current_admin(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> dict:
    """Dependency: valid admin JWT. 401 if missing/invalid, 403 if not an admin."""
    payload = _require_bearer(creds)
    if payload.get("role") != "admin":
        raise AuthError(403, "Admin access required.")
    username = payload.get("sub")
    with get_conn() as conn:
        admin = conn.execute(
            "SELECT * FROM admins WHERE username = %s", (username,)
        ).fetchone()
    if admin is None:
        raise AuthError(401, "Account no longer valid. Please log in again.")
    return {"admin": admin, "username": username}
