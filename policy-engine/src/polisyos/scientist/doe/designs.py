from __future__ import annotations

from pydantic import BaseModel, Field


class ScenarioSweep(BaseModel):
    scenarios: list[dict] = Field(default_factory=list)


class AblationPlan(BaseModel):
    targets: list[str] = Field(default_factory=list)


class SensitivityPlan(BaseModel):
    parameters: list[str] = Field(default_factory=list)
