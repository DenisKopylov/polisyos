from __future__ import annotations

from pydantic import BaseModel, Field


class GateRequest(BaseModel):
    run_id: str
    reason: str
    details: dict | None = None


class GateDecision(BaseModel):
    approved: bool
    actor: str | None = None
    reason_codes: list[str] = Field(default_factory=list)
    notes: str | None = None
