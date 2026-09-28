"""Pydantic request schemas for the Topaz-VBE API (SPEC section 4)."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class TeamLogin(BaseModel):
    simulation_code: str
    group_number: int
    company_number: int
    identity_number: str


class AdminLogin(BaseModel):
    username: str
    password: str


class DecisionPut(BaseModel):
    data: dict


class IndustryCreate(BaseModel):
    name: str = Field(min_length=1)
    simulation_code: str = Field(min_length=1)


class TeamCreate(BaseModel):
    name: str = Field(min_length=1)
    group_number: int
    company_number: int


class QuarterCreate(BaseModel):
    year: int = Field(ge=1)
    quarter: int = Field(ge=1, le=4)
    auto_pass_minutes: Optional[int] = Field(default=None, ge=0)


class ShockUpsert(BaseModel):
    year: int = Field(ge=1)
    quarter: int = Field(ge=1, le=4)
    inflation_pct: Optional[float] = None
    material_price_change_pct: Optional[float] = None
    recession: Optional[bool] = None
    note: Optional[str] = None


class RollQuarterRequest(BaseModel):
    force: bool = False
