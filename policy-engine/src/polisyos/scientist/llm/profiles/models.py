"""Model profile models for runtime LLM selection."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ModelProfile(BaseModel):
    """Named model profile used by runtime control API."""

    model_config = ConfigDict(extra="forbid")

    profile_id: str = Field(..., pattern=r"^[a-z][a-z0-9_]*$")
    display_name: str
    description: str = ""
    provider: str
    model_id: str
    base_url: str
    tags: list[str] = Field(default_factory=list)
    capabilities: list[str] = Field(default_factory=list)
    input_cost_per_mtoken_usd: float | None = Field(default=None, ge=0.0)
    output_cost_per_mtoken_usd: float | None = Field(default=None, ge=0.0)
    enabled: bool = True


__all__ = ["ModelProfile"]
