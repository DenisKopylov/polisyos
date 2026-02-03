from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from .capabilities import Capability
from .ids import ComponentId


class ComponentMetadata(BaseModel):
    """Descriptive metadata for a component."""

    model_config = ConfigDict(extra="forbid")

    component_id: ComponentId
    display_name: str | None = None
    description: str | None = None
    domains: list[str] = Field(default_factory=list)
    jurisdictions: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    capabilities: Capability = Capability(0)
    provides: list[str] = Field(default_factory=list)
    depends_on: list[ComponentId | str] = Field(default_factory=list)
