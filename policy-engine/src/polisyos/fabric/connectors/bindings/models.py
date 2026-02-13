"""Binding Profile models — reusable configurations mapping data schemas to Foundry input slots.

IMPORTANT: This module MUST NOT import jax, numpy, or any heavy foundry
execution code. It defines pure data models only.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

BindingStrategy = Literal["auto", "manual", "hybrid"]


class BindingTransformSpec(BaseModel):
    """Transform operation within a binding rule."""

    model_config = ConfigDict(extra="forbid")

    op: str = "identity"
    params: dict[str, Any] = Field(default_factory=dict)


class BindingRuleSpec(BaseModel):
    """A single rule within a binding profile.

    Analogous to FoundryInputBindingRule but without jax dependencies.
    """

    model_config = ConfigDict(extra="forbid")

    binding_id: str
    source_path: str
    target_slot_id: str
    required: bool = False
    default_value: Any = None
    transforms: list[BindingTransformSpec] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class BindingProfile(BaseModel):
    """A named, reusable configuration mapping normalized data to Foundry slots."""

    model_config = ConfigDict(extra="forbid")

    profile_id: str = Field(..., pattern=r"^[a-z][a-z0-9_]*$")
    display_name: str
    description: str = ""
    schema_family: str
    strategy: BindingStrategy = "auto"
    rules: list[BindingRuleSpec] = Field(default_factory=list)
    expected_columns: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


__all__ = ["BindingProfile", "BindingRuleSpec", "BindingStrategy", "BindingTransformSpec"]
