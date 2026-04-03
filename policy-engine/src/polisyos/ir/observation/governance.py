"""Public observation governance module API."""
from __future__ import annotations

from enum import Enum

from pydantic import Field, model_validator

from polisyos.ir.kernel.base import KernelModel
from polisyos.ir.observation.contracts import IdentificationMode, ObservationFamily

SCHEMA_VERSION_PATTERN = r"^\d+\.\d+$"


class GovernancePassAliasStatus(str, Enum):
    """Availability state for a governance pass alias."""

    RUNTIME = "runtime"
    DEFERRED = "deferred"


class GovernancePassAlias(KernelModel):
    """Canonical-to-runtime mapping for a governance pass.

    Alias entries decouple stable IR pass identifiers from the concrete pass
    names available in the current Scientist runtime.
    """

    canonical_pass_id: str = Field(..., min_length=1, max_length=120)
    runtime_pass_id: str | None = Field(None, min_length=1, max_length=120)
    status: GovernancePassAliasStatus
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_alias(self) -> "GovernancePassAlias":
        if self.status == GovernancePassAliasStatus.RUNTIME and self.runtime_pass_id is None:
            raise ValueError("runtime_pass_id is required for runtime alias entries")
        return self


class GovernancePassAliasRegistry(KernelModel):
    """Registry of governance pass aliases exposed to observation policies.

    The registry is used when observation-family policies and bundle manifests
    need to refer to governance checks without hard-coding runtime-specific
    pass identifiers.
    """

    schema_version: str = Field("1.0", pattern=SCHEMA_VERSION_PATTERN)
    aliases: dict[str, GovernancePassAlias] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_aliases(self) -> "GovernancePassAliasRegistry":
        for key, alias in self.aliases.items():
            if key != alias.canonical_pass_id:
                raise ValueError(
                    f"canonical alias key mismatch: '{key}' != '{alias.canonical_pass_id}'"
                )
        return self

    def resolve(self, canonical_pass_id: str) -> GovernancePassAlias | None:
        return self.aliases.get(canonical_pass_id)

    @classmethod
    def default(cls) -> "GovernancePassAliasRegistry":
        return cls(
            aliases={
                "budget": GovernancePassAlias(
                    canonical_pass_id="budget",
                    runtime_pass_id="budget",
                    status=GovernancePassAliasStatus.RUNTIME,
                ),
                "checkpoint": GovernancePassAlias(
                    canonical_pass_id="checkpoint",
                    runtime_pass_id="checkpoint",
                    status=GovernancePassAliasStatus.RUNTIME,
                ),
                "confidence": GovernancePassAlias(
                    canonical_pass_id="confidence",
                    runtime_pass_id="confidence",
                    status=GovernancePassAliasStatus.RUNTIME,
                ),
                "cross_graph_evidence": GovernancePassAlias(
                    canonical_pass_id="cross_graph_evidence",
                    runtime_pass_id="cross_graph_evidence",
                    status=GovernancePassAliasStatus.RUNTIME,
                ),
                "equity": GovernancePassAlias(
                    canonical_pass_id="equity",
                    runtime_pass_id="equity",
                    status=GovernancePassAliasStatus.RUNTIME,
                ),
                "freshness": GovernancePassAlias(
                    canonical_pass_id="freshness",
                    runtime_pass_id="freshness",
                    status=GovernancePassAliasStatus.RUNTIME,
                ),
                "privacy": GovernancePassAlias(
                    canonical_pass_id="privacy",
                    runtime_pass_id="privacy",
                    status=GovernancePassAliasStatus.RUNTIME,
                ),
                "refutation": GovernancePassAlias(
                    canonical_pass_id="refutation",
                    runtime_pass_id="refutation",
                    status=GovernancePassAliasStatus.RUNTIME,
                ),
                "strategic_gaming_adversarial": GovernancePassAlias(
                    canonical_pass_id="strategic_gaming_adversarial",
                    status=GovernancePassAliasStatus.DEFERRED,
                    notes=["Strategic-adversarial governance pass is reserved for later phases."],
                ),
                "sutva_check": GovernancePassAlias(
                    canonical_pass_id="sutva_check",
                    runtime_pass_id="sutva_check",
                    status=GovernancePassAliasStatus.RUNTIME,
                ),
                "transportability_required": GovernancePassAlias(
                    canonical_pass_id="transportability_required",
                    runtime_pass_id="transportability_required",
                    status=GovernancePassAliasStatus.RUNTIME,
                ),
            }
        )


class ObservationFamilyPolicy(KernelModel):
    """Identification and governance defaults for one observation family.

    Encodes the preferred identification mode, fallback conditions, and the
    mandatory governance passes that must clear before the family can be used
    in causal execution.
    """

    schema_version: str = Field("1.0", pattern=SCHEMA_VERSION_PATTERN)
    family: ObservationFamily
    primary_identification_mode: IdentificationMode
    fallback_identification_mode: IdentificationMode | None = None
    fallback_mode_annotation: str | None = Field(None, max_length=120)
    mandatory_governance_passes: list[str] = Field(default_factory=list, min_length=1)
    requires_proxy_check: bool = False
    requires_bounds_bundle: bool = False
    requires_interference_contract: bool = False
    requires_strategic_response_check: bool = False

    @model_validator(mode="after")
    def validate_policy(self) -> "ObservationFamilyPolicy":
        if len(set(self.mandatory_governance_passes)) != len(self.mandatory_governance_passes):
            raise ValueError("mandatory_governance_passes must be unique")
        return self


class ObservationFamilyPolicyRegistry(KernelModel):
    """Complete policy catalog covering every observation family."""

    schema_version: str = Field("1.0", pattern=SCHEMA_VERSION_PATTERN)
    policies: dict[str, ObservationFamilyPolicy] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_policies(self) -> "ObservationFamilyPolicyRegistry":
        for family in ObservationFamily:
            if family.value not in self.policies:
                raise ValueError(f"missing observation family policy: {family.value}")
        for key, policy in self.policies.items():
            if key != policy.family.value:
                raise ValueError(f"policy key mismatch: '{key}' != '{policy.family.value}'")
        return self

    def for_family(self, family: ObservationFamily) -> ObservationFamilyPolicy:
        return self.policies[family.value]

    def mandatory_pass_mapping(self) -> dict[str, list[str]]:
        return {
            family: list(policy.mandatory_governance_passes)
            for family, policy in self.policies.items()
        }

    @classmethod
    def default(cls) -> "ObservationFamilyPolicyRegistry":
        return cls(
            policies={
                ObservationFamily.BUDGET_FLOWS.value: ObservationFamilyPolicy(
                    family=ObservationFamily.BUDGET_FLOWS,
                    primary_identification_mode=IdentificationMode.POINT_IDENTIFIED,
                    fallback_identification_mode=IdentificationMode.BOUNDS_ONLY,
                    fallback_mode_annotation="wartime_censoring",
                    mandatory_governance_passes=[
                        "sutva_check",
                        "freshness",
                        "equity",
                        "cross_graph_evidence",
                    ],
                    requires_bounds_bundle=True,
                ),
                ObservationFamily.PROCUREMENT_FLOWS.value: ObservationFamilyPolicy(
                    family=ObservationFamily.PROCUREMENT_FLOWS,
                    primary_identification_mode=IdentificationMode.INTERFERENCE_AWARE,
                    fallback_identification_mode=IdentificationMode.BOUNDS_ONLY,
                    fallback_mode_annotation="wartime",
                    mandatory_governance_passes=[
                        "sutva_check",
                        "transportability_required",
                        "confidence",
                        "strategic_gaming_adversarial",
                    ],
                    requires_bounds_bundle=True,
                    requires_interference_contract=True,
                    requires_strategic_response_check=True,
                ),
                ObservationFamily.MACRO_STATE.value: ObservationFamilyPolicy(
                    family=ObservationFamily.MACRO_STATE,
                    primary_identification_mode=IdentificationMode.POINT_IDENTIFIED,
                    mandatory_governance_passes=["confidence", "freshness"],
                ),
                ObservationFamily.FIRM_FUNDAMENTALS.value: ObservationFamilyPolicy(
                    family=ObservationFamily.FIRM_FUNDAMENTALS,
                    primary_identification_mode=IdentificationMode.POINT_IDENTIFIED,
                    fallback_identification_mode=IdentificationMode.POINT_IDENTIFIED,
                    fallback_mode_annotation="selection_corrected",
                    mandatory_governance_passes=[
                        "refutation",
                        "freshness",
                        "cross_graph_evidence",
                    ],
                ),
                ObservationFamily.TRADE_EXPOSURE.value: ObservationFamilyPolicy(
                    family=ObservationFamily.TRADE_EXPOSURE,
                    primary_identification_mode=IdentificationMode.POINT_IDENTIFIED,
                    fallback_identification_mode=IdentificationMode.BOUNDS_ONLY,
                    fallback_mode_annotation="sanctions_regime",
                    mandatory_governance_passes=["transportability_required", "confidence"],
                    requires_bounds_bundle=True,
                ),
                ObservationFamily.LABOR_MARKET.value: ObservationFamilyPolicy(
                    family=ObservationFamily.LABOR_MARKET,
                    primary_identification_mode=IdentificationMode.PROXY_IDENTIFIED,
                    fallback_identification_mode=IdentificationMode.BOUNDS_ONLY,
                    fallback_mode_annotation="informal_sector",
                    mandatory_governance_passes=["equity", "sutva_check", "confidence"],
                    requires_proxy_check=True,
                    requires_bounds_bundle=True,
                ),
                ObservationFamily.HOUSEHOLD_DISTRIBUTION.value: ObservationFamilyPolicy(
                    family=ObservationFamily.HOUSEHOLD_DISTRIBUTION,
                    primary_identification_mode=IdentificationMode.PROXY_IDENTIFIED,
                    fallback_identification_mode=IdentificationMode.BOUNDS_ONLY,
                    fallback_mode_annotation="coverage_gaps",
                    mandatory_governance_passes=[
                        "equity",
                        "confidence",
                        "refutation",
                        "privacy",
                    ],
                    requires_proxy_check=True,
                    requires_bounds_bundle=True,
                ),
                ObservationFamily.DISTRESS_ENFORCEMENT.value: ObservationFamilyPolicy(
                    family=ObservationFamily.DISTRESS_ENFORCEMENT,
                    primary_identification_mode=IdentificationMode.PARTIALLY_IDENTIFIED,
                    fallback_identification_mode=IdentificationMode.PARTIALLY_IDENTIFIED,
                    fallback_mode_annotation="survival_censored",
                    mandatory_governance_passes=["refutation", "confidence"],
                ),
                ObservationFamily.SPATIAL_RASTER_EXOGENOUS.value: ObservationFamilyPolicy(
                    family=ObservationFamily.SPATIAL_RASTER_EXOGENOUS,
                    primary_identification_mode=IdentificationMode.POINT_IDENTIFIED,
                    mandatory_governance_passes=["freshness"],
                ),
                ObservationFamily.PUBLIC_SERVICE_DOMAIN_FLOWS.value: ObservationFamilyPolicy(
                    family=ObservationFamily.PUBLIC_SERVICE_DOMAIN_FLOWS,
                    primary_identification_mode=IdentificationMode.POINT_IDENTIFIED,
                    fallback_identification_mode=IdentificationMode.BOUNDS_ONLY,
                    fallback_mode_annotation="wartime",
                    mandatory_governance_passes=["sutva_check", "equity"],
                    requires_bounds_bundle=True,
                ),
                ObservationFamily.EDUCATION_HUMAN_CAPITAL_SUPPLY.value: ObservationFamilyPolicy(
                    family=ObservationFamily.EDUCATION_HUMAN_CAPITAL_SUPPLY,
                    primary_identification_mode=IdentificationMode.POINT_IDENTIFIED,
                    mandatory_governance_passes=["freshness"],
                ),
                ObservationFamily.CONSTRUCTION_CAPITAL_FORMATION.value: ObservationFamilyPolicy(
                    family=ObservationFamily.CONSTRUCTION_CAPITAL_FORMATION,
                    primary_identification_mode=IdentificationMode.POINT_IDENTIFIED,
                    fallback_identification_mode=IdentificationMode.BOUNDS_ONLY,
                    fallback_mode_annotation="permit_delays",
                    mandatory_governance_passes=["freshness"],
                    requires_bounds_bundle=True,
                ),
                ObservationFamily.LOGISTICS_FRICTION.value: ObservationFamilyPolicy(
                    family=ObservationFamily.LOGISTICS_FRICTION,
                    primary_identification_mode=IdentificationMode.PROXY_IDENTIFIED,
                    fallback_identification_mode=IdentificationMode.BOUNDS_ONLY,
                    mandatory_governance_passes=["transportability_required"],
                    requires_proxy_check=True,
                    requires_bounds_bundle=True,
                ),
            }
        )


class GovernancePassMappingRegistry(KernelModel):
    """Resolved mapping from observation families to governance pass ids.

    This is the bundle-friendly form of the family policy registry: it keeps
    only the pass requirements that must be enforced globally or per family.
    """

    schema_version: str = Field("1.0", pattern=SCHEMA_VERSION_PATTERN)
    global_mandatory_passes: list[str] = Field(default_factory=list, min_length=1)
    family_passes: dict[str, list[str]] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_mapping(self) -> "GovernancePassMappingRegistry":
        if len(set(self.global_mandatory_passes)) != len(self.global_mandatory_passes):
            raise ValueError("global_mandatory_passes must be unique")
        known_families = {family.value for family in ObservationFamily}
        for family in ObservationFamily:
            if family.value not in self.family_passes:
                raise ValueError(f"missing governance mapping for family: {family.value}")
        for family_key, passes in self.family_passes.items():
            if family_key not in known_families:
                raise ValueError(f"unknown observation family in mapping: {family_key}")
            if len(set(passes)) != len(passes):
                raise ValueError(f"family pass mapping must be unique for {family_key}")
        return self

    def for_family(self, family: ObservationFamily, *, include_global: bool = False) -> list[str]:
        passes = list(self.family_passes[family.value])
        if not include_global:
            return passes
        return [*self.global_mandatory_passes, *passes]

    @classmethod
    def from_policy_registry(
        cls,
        policy_registry: ObservationFamilyPolicyRegistry,
        *,
        global_mandatory_passes: list[str] | None = None,
    ) -> "GovernancePassMappingRegistry":
        return cls(
            global_mandatory_passes=list(
                global_mandatory_passes or ["budget", "confidence", "freshness", "checkpoint"]
            ),
            family_passes=policy_registry.mandatory_pass_mapping(),
        )


DEFAULT_GOVERNANCE_PASS_ALIAS_REGISTRY = GovernancePassAliasRegistry.default()
DEFAULT_OBSERVATION_FAMILY_POLICY_REGISTRY = ObservationFamilyPolicyRegistry.default()
DEFAULT_GOVERNANCE_PASS_MAPPING_REGISTRY = GovernancePassMappingRegistry.from_policy_registry(
    DEFAULT_OBSERVATION_FAMILY_POLICY_REGISTRY
)

__all__ = [
    "DEFAULT_GOVERNANCE_PASS_ALIAS_REGISTRY",
    "DEFAULT_GOVERNANCE_PASS_MAPPING_REGISTRY",
    "DEFAULT_OBSERVATION_FAMILY_POLICY_REGISTRY",
    "GovernancePassAlias",
    "GovernancePassAliasRegistry",
    "GovernancePassAliasStatus",
    "GovernancePassMappingRegistry",
    "ObservationFamilyPolicy",
    "ObservationFamilyPolicyRegistry",
]
