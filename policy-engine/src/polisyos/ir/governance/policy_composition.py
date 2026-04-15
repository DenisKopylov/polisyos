"""Multi-level policy composition contracts for federal/state/local overrides."""
from __future__ import annotations

from enum import Enum

from pydantic import Field, model_validator

from polisyos.ir._validation import ensure_interval_monotonicity, ensure_unique_ids
from polisyos.ir.kernel.base import ID_PATTERN, KernelModel


class PolicyLayerLevel(str, Enum):
    """Supported override layers in a composed policy stack."""

    FEDERAL = "federal"
    STATE = "state"
    LOCAL = "local"
    ORGANIZATIONAL = "organizational"


class PolicyVersioningMode(str, Enum):
    """How versions are negotiated across composed layers."""

    LOCKSTEP = "lockstep"
    INDEPENDENT = "independent"
    EXPLICIT_NEGOTIATION = "explicit_negotiation"


class PolicyOverrideMode(str, Enum):
    """How a lower layer interacts with an inherited policy surface."""

    INHERIT = "inherit"
    APPEND = "append"
    REPLACE = "replace"
    DISABLE = "disable"


class PolicyCompatibilityMode(str, Enum):
    """Compatibility contract between stacked policy layers."""

    STRICT_SUBSET = "strict_subset"
    EXTENDS = "extends"
    REQUIRES_APPROVAL = "requires_approval"
    INCOMPATIBLE = "incompatible"


class PolicyLayerSpec(KernelModel):
    """One policy layer participating in a multi-jurisdiction composition."""

    layer_id: str = Field(..., pattern=ID_PATTERN)
    level: PolicyLayerLevel
    jurisdiction_id: str = Field(..., pattern=ID_PATTERN)
    policy_id: str = Field(..., pattern=ID_PATTERN)
    version_tag: str = Field(..., min_length=1, max_length=64)
    precedence: int = Field(..., ge=0)
    effective_from: str | None = Field(
        None,
        pattern=r"^\d{4}-\d{2}(-\d{2})?$",
    )
    effective_to: str | None = Field(
        None,
        pattern=r"^\d{4}-\d{2}(-\d{2})?$",
    )

    @model_validator(mode="after")
    def validate_interval(self) -> "PolicyLayerSpec":
        ensure_interval_monotonicity(
            self.effective_from,
            self.effective_to,
            label="policy layer effective interval",
            start_name="effective_from",
            end_name="effective_to",
        )
        return self


class PolicyOverrideRule(KernelModel):
    """Override applied by one policy layer to another."""

    override_id: str = Field(..., pattern=ID_PATTERN)
    source_layer_id: str = Field(..., pattern=ID_PATTERN)
    target_layer_id: str = Field(..., pattern=ID_PATTERN)
    target_intervention_id: str | None = Field(None, pattern=ID_PATTERN)
    target_constraint_id: str | None = Field(None, pattern=ID_PATTERN)
    mode: PolicyOverrideMode
    justification: str = Field(..., min_length=1, max_length=400)

    @model_validator(mode="after")
    def validate_target(self) -> "PolicyOverrideRule":
        if self.target_intervention_id is None and self.target_constraint_id is None:
            raise ValueError(
                "override rule must target an intervention_id or constraint_id"
            )
        return self


class PolicyCompatibilityConstraint(KernelModel):
    """Compatibility requirement between a higher and lower policy layer."""

    constraint_id: str = Field(..., pattern=ID_PATTERN)
    higher_layer_id: str = Field(..., pattern=ID_PATTERN)
    lower_layer_id: str = Field(..., pattern=ID_PATTERN)
    mode: PolicyCompatibilityMode
    required_policy_refs: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()


class PolicyCompositionPlan(KernelModel):
    """Versioned multi-level policy composition plan."""

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    composition_id: str = Field(..., pattern=ID_PATTERN)
    base_policy_id: str = Field(..., pattern=ID_PATTERN)
    versioning_mode: PolicyVersioningMode = PolicyVersioningMode.EXPLICIT_NEGOTIATION
    layers: list[PolicyLayerSpec] = Field(..., min_length=1, max_length=16)
    override_rules: list[PolicyOverrideRule] = Field(default_factory=list, max_length=64)
    compatibility_constraints: list[PolicyCompatibilityConstraint] = Field(
        default_factory=list,
        max_length=64,
    )

    @model_validator(mode="after")
    def validate_composition(self) -> "PolicyCompositionPlan":
        ensure_unique_ids(self.layers, key_fn=lambda item: item.layer_id, label="policy layer_id")
        ensure_unique_ids(
            self.layers,
            key_fn=lambda item: item.precedence,
            label="policy layer precedence",
        )
        ensure_unique_ids(
            self.override_rules,
            key_fn=lambda item: item.override_id,
            label="policy override_id",
        )
        ensure_unique_ids(
            self.compatibility_constraints,
            key_fn=lambda item: item.constraint_id,
            label="policy compatibility constraint_id",
        )
        layer_ids = {layer.layer_id for layer in self.layers}
        if self.base_policy_id not in {layer.policy_id for layer in self.layers}:
            raise ValueError("base_policy_id must match one of the declared layer policy_ids")
        for rule in self.override_rules:
            if rule.source_layer_id not in layer_ids:
                raise ValueError(
                    f"override rule '{rule.override_id}' references unknown source_layer_id"
                )
            if rule.target_layer_id not in layer_ids:
                raise ValueError(
                    f"override rule '{rule.override_id}' references unknown target_layer_id"
                )
        for constraint in self.compatibility_constraints:
            if constraint.higher_layer_id not in layer_ids:
                raise ValueError(
                    f"compatibility constraint '{constraint.constraint_id}' references "
                    "unknown higher_layer_id"
                )
            if constraint.lower_layer_id not in layer_ids:
                raise ValueError(
                    f"compatibility constraint '{constraint.constraint_id}' references "
                    "unknown lower_layer_id"
                )
        return self


__all__ = [
    "PolicyCompatibilityConstraint",
    "PolicyCompatibilityMode",
    "PolicyCompositionPlan",
    "PolicyLayerLevel",
    "PolicyLayerSpec",
    "PolicyOverrideMode",
    "PolicyOverrideRule",
    "PolicyVersioningMode",
]
