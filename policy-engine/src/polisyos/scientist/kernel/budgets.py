"""Public kernel budgets module API."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ComputeBudget(BaseModel):
    """Compute budget public type."""
    model_config = ConfigDict(extra="forbid")

    max_llm_calls: float = Field(default=3.0, ge=0)
    max_sim_runs: float = Field(default=1.0, ge=0)
    max_wall_time_s: float = Field(default=120.0, ge=0)


class EvidenceBudget(BaseModel):
    """Evidence budget public type."""
    model_config = ConfigDict(extra="forbid")

    max_queries: int = Field(default=10, ge=0)


class LegitimacyBudget(BaseModel):
    """Legitimacy budget public type."""
    model_config = ConfigDict(extra="forbid")

    require_human_gate: bool = False
    notes: list[str] = Field(default_factory=list)


class ComplexityBudget(BaseModel):
    """Complexity budget public type."""
    model_config = ConfigDict(extra="forbid")

    max_interventions: int = Field(default=10, ge=0)
    max_scenarios: int = Field(default=10, ge=0)
