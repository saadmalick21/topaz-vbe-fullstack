"""Team + admin login endpoints."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from ..auth import issue_token, verify_admin_credentials, verify_team_credentials
from ..schemas import AdminLogin, TeamLogin

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login")
def team_login(body: TeamLogin):
    row = verify_team_credentials(
        body.simulation_code, body.group_number, body.company_number, body.identity_number
    )
    if row is None:
        return JSONResponse(
            status_code=401,
            content={
                "error": "Invalid team credentials. Check simulation code, "
                         "group/company numbers and identity number."
            },
        )
    token = issue_token(
        sub=str(row["id"]), role="team",
        team_id=row["id"], industry_id=row["industry_id"],
    )
    return {
        "token": token,
        "role": "team",
        "team": {
            "id": row["id"],
            "name": row["name"],
            "group_number": row["group_number"],
            "company_number": row["company_number"],
        },
        "industry": {
            "id": row["_industry_id"],
            "name": row["_industry_name"],
            "simulation_code": row["_simulation_code"],
        },
    }


@router.post("/admin-login")
def admin_login(body: AdminLogin):
    row = verify_admin_credentials(body.username, body.password)
    if row is None:
        return JSONResponse(
            status_code=401,
            content={"error": "Invalid admin credentials."},
        )
    token = issue_token(sub=row["username"], role="admin")
    return {"token": token, "role": "admin"}
