"""Typed contracts for W7.C method validity requirements."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class MethodIdentificationClass(str, Enum):
    """Identification obligation required before a claim may consume method output."""

    POINT = "point"
    PARTIAL = "partial"
    BOUNDS = "bounds"
    NEGATIVE_CERTIFICATE = "negative_certificate"


class MethodTransportabilityRequirement(str, Enum):
    """Transportability surface expected for a method requirement."""

    NONE = "none"
    TARGET_POPULATION_LIMITS = "target_population_limits"
    TRANSPORT_CERTIFICATE = "transport_certificate"
    DO_NOT_TRANSPORT = "do_not_transport"


class MethodUncertaintyClass(str, Enum):
    """Uncertainty surface expected from an admissible method."""

    NONE = "none"
    INTERVAL = "interval"
    BOUNDS = "bounds"
    DISTRIBUTION = "distribution"
    ROBUST_SET = "robust_set"


class FairnessDecompositionNeed(str, Enum):
    """Fairness or subgroup decomposition required for the claim."""

    NONE = "none"
    SUBGROUP = "subgroup"
    PROTECTED_CLASS = "protected_class"
    INTERSECTIONAL = "intersectional"


class StrategicResponseSensitivity(str, Enum):
    """Strategic-response sensitivity required for the claim."""

    NONE = "none"
    MONITOR = "monitor"
    SENSITIVITY = "sensitivity"
    GAME_THEORETIC = "game_theoretic"


class AssumptionValidationNeed(BaseModel):
    """One runtime assumption gate required before method output is authority-bearing."""

    model_config = ConfigDict(extra="forbid")

    assumption_id: str = Field(min_length=1)
    gate_required: bool = True
    required_statuses: list[str] = Field(default_factory=lambda: ["pass"])
    rationale: str = Field(default="", max_length=1000)

    @field_validator("required_statuses")
    @classmethod
    def _normalize_statuses(cls, values: list[str]) -> list[str]:
        normalized = _dedupe_strings(values)
        return normalized or ["pass"]


class SimulationDGPRequirement(BaseModel):
    """Simulation DGP, calibration, and lineage requirements."""

    model_config = ConfigDict(extra="forbid")

    required: bool = False
    dgp_lineage_required: bool = False
    calibration_required: bool = False
    behavioral_response_required: bool = False
    required_refs: list[str] = Field(default_factory=list)
    rationale: str = Field(default="", max_length=1000)


class MethodValidityRequirementSpec(BaseModel):
    """Claim-bound method validity requirement consumed by Foundry and IR bridges."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
    requirement_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    claim_id: str = Field(min_length=1)
    identification_class: MethodIdentificationClass
    transportability_requirement: MethodTransportabilityRequirement = (
        MethodTransportabilityRequirement.NONE
    )
    uncertainty_class: MethodUncertaintyClass = MethodUncertaintyClass.NONE
    fairness_decomposition_need: FairnessDecompositionNeed = FairnessDecompositionNeed.NONE
    strategic_response_sensitivity: StrategicResponseSensitivity = (
        StrategicResponseSensitivity.NONE
    )
    simulation_dgp_requirements: SimulationDGPRequirement = Field(
        default_factory=SimulationDGPRequirement
    )
    assumption_validation_needs: list[AssumptionValidationNeed] = Field(default_factory=list)
    method_expectations: list[str] = Field(default_factory=list)
    required_method_families: list[str] = Field(default_factory=list)
    facet_refs: list[str] = Field(default_factory=list)
    obligation_refs: list[str] = Field(default_factory=list)
    concept_spine_refs: list[str] = Field(default_factory=list)
    authority_profile_refs: list[str] = Field(default_factory=list)
    baseline_refs: list[str] = Field(default_factory=list)
    alternative_refs: list[str] = Field(default_factory=list)
    source_precondition_refs: list[str] = Field(default_factory=list)
    requires_ir_analytics: bool = True
    requires_runtime_assumption_gates: bool = True
    requires_uncertainty_envelope: bool = True
    requires_limitation_refs: bool = True
    requires_method_output: bool = True
    requires_negative_certificate: bool = False
    producer_ref: str = "polisyos.method_requirement.compiler"
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator(
        "method_expectations",
        "required_method_families",
        "facet_refs",
        "obligation_refs",
        "concept_spine_refs",
        "authority_profile_refs",
        "baseline_refs",
        "alternative_refs",
        "source_precondition_refs",
    )
    @classmethod
    def _normalize_string_lists(cls, values: list[str]) -> list[str]:
        return _dedupe_strings(values)

    @model_validator(mode="after")
    def _synchronize_negative_certificate_requirements(self) -> MethodValidityRequirementSpec:
        if self.identification_class is MethodIdentificationClass.NEGATIVE_CERTIFICATE:
            self.requires_negative_certificate = True
            self.requires_method_output = False
            self.requires_uncertainty_envelope = False
            self.requires_runtime_assumption_gates = False
            self.requires_limitation_refs = False
            self.uncertainty_class = MethodUncertaintyClass.NONE
        if not self.required_method_families:
            self.required_method_families = list(self.method_expectations)
        return self


class MethodValidityRequirementArtifact(BaseModel):
    """Persistable compiler output for one run's method requirements."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
    run_id: str = Field(min_length=1)
    requirements: list[MethodValidityRequirementSpec] = Field(default_factory=list)
    requirement_graph_ref: str | None = None
    capability_reality_label: Literal["implemented"] = "implemented"
    runtime_event_ref: str = Field(min_length=1)
    authority_boundary: dict[str, list[str]] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_requirement_run_ids(self) -> MethodValidityRequirementArtifact:
        if any(requirement.run_id != self.run_id for requirement in self.requirements):
            raise ValueError("method requirements must share artifact run_id")
        if not self.authority_boundary:
            self.authority_boundary = method_requirement_authority_boundary()
        return self


def method_requirement_authority_boundary() -> dict[str, list[str]]:
    """Return the W7.C authority boundary for method requirement artifacts."""

    return {
        "authoritative_for": [
            "method_validity_requirements",
            "method_selection_preconditions",
            "ir_analytics_requirement_binding",
        ],
        "may_not_use_for": [
            "legal_authority",
            "source_family_satisfaction",
            "academic_support_strength",
            "participation_representativeness",
            "closeout_pass",
        ],
    }


def normalize_method_requirements(
    requirements: Sequence[MethodValidityRequirementSpec | Mapping[str, Any]] | None,
) -> list[MethodValidityRequirementSpec]:
    """Validate a sequence of method requirement mappings or models."""

    output: list[MethodValidityRequirementSpec] = []
    for item in requirements or ():
        if isinstance(item, MethodValidityRequirementSpec):
            output.append(item)
        elif isinstance(item, Mapping):
            output.append(MethodValidityRequirementSpec.model_validate(dict(item)))
        else:
            raise TypeError("method requirements must be mappings or MethodValidityRequirementSpec")
    return output


def _dedupe_strings(values: Sequence[Any]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if not text:
            continue
        if text in seen:
            continue
        seen.add(text)
        output.append(text)
    return output


__all__ = [
    "AssumptionValidationNeed",
    "FairnessDecompositionNeed",
    "MethodIdentificationClass",
    "MethodTransportabilityRequirement",
    "MethodUncertaintyClass",
    "MethodValidityRequirementArtifact",
    "MethodValidityRequirementSpec",
    "SimulationDGPRequirement",
    "StrategicResponseSensitivity",
    "method_requirement_authority_boundary",
    "normalize_method_requirements",
]
