"""Predicate registries for Fact Log and DataView resolution."""

from __future__ import annotations

from pydantic import Field, model_validator

from polisyos.ir.kernel.base import ID_PATTERN, KernelModel
from polisyos.ir.kernel.units import UnitRef


class ScalarPredicateSpec(KernelModel):
    """Scalar predicate spec data model."""
    predicate_id: str = Field(..., pattern=ID_PATTERN)
    slot_id: str = Field(..., pattern=ID_PATTERN)
    value_type: str
    unit: UnitRef | None = None
    default_resample: str | None = None
    default_agg: str | None = None
    notes: list[str] = Field(default_factory=list)


class EdgePredicateSpec(KernelModel):
    """Edge predicate spec data model."""
    predicate_id: str = Field(..., pattern=ID_PATTERN)
    src_entity_type: str
    dst_entity_type: str
    temporal_validity: str | None = None
    cardinality: str | None = None
    notes: list[str] = Field(default_factory=list)


class PredicateRegistry(KernelModel):
    """Predicate registry implementation."""
    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    scalars: dict[str, ScalarPredicateSpec] = Field(default_factory=dict)
    edges: dict[str, EdgePredicateSpec] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_predicates(self) -> "PredicateRegistry":
        for key, spec in self.scalars.items():
            if key != spec.predicate_id:
                raise ValueError(f"predicate_id mismatch: '{key}' != '{spec.predicate_id}'")
        for key, spec in self.edges.items():
            if key != spec.predicate_id:
                raise ValueError(f"edge predicate_id mismatch: '{key}' != '{spec.predicate_id}'")
        return self


class PrivacyPolicySpec(KernelModel):
    """Privacy policy spec data model."""
    policy_id: str = Field(..., pattern=ID_PATTERN)
    description: str | None = None
    notes: list[str] = Field(default_factory=list)


class PrivacyPolicyRegistry(KernelModel):
    """Privacy policy registry implementation."""
    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    policies: dict[str, PrivacyPolicySpec] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_policies(self) -> "PrivacyPolicyRegistry":
        for key, spec in self.policies.items():
            if key != spec.policy_id:
                raise ValueError(f"privacy policy id mismatch: '{key}' != '{spec.policy_id}'")
        return self
