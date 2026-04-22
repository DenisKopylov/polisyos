"""Define family-level governance policy and pass-alias registries.

This module sits one layer above raw observations: it tells Scientist which
governance passes are mandatory for each observation family and how stable IR
pass identifiers map onto concrete runtime pass names. The resolved mapping is
embedded into bundle manifests before causal-readiness or execution stages run.
"""
from __future__ import annotations

from enum import Enum

from pydantic import Field, model_validator

from polisyos.ir._validation import ensure_unique_ids
from polisyos.ir.kernel.base import KernelModel
from polisyos.ir.observation.contracts import IdentificationMode, ObservationFamily

SCHEMA_VERSION_PATTERN = r"^\d+\.\d+$"


class GovernancePassAliasStatus(str, Enum):
    """Declare whether a canonical pass can execute in the current Scientist runtime.

    ``RUNTIME`` means the alias resolves to a concrete pass id and may be
    scheduled immediately; ``DEFERRED`` means policy metadata can reference the
    pass, but readiness/execution layers must treat it as unavailable for now.
    """

    RUNTIME = "runtime"
    DEFERRED = "deferred"


class GovernancePassAlias(KernelModel):
    """Map a stable IR pass id to the runtime-specific governance pass id.

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
    """Store the pass-alias catalog used when emitting bundle-friendly mappings.

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
        """Return the alias entry for a canonical pass id, if registered."""
        return self.aliases.get(canonical_pass_id)

    @classmethod
    def default(cls) -> "GovernancePassAliasRegistry":
        """Build the built-in alias table for currently known governance passes."""
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
                "causal_frontier_leakage": GovernancePassAlias(
                    canonical_pass_id="causal_frontier_leakage",
                    runtime_pass_id="causal_frontier_leakage",
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
    """Declare default identification semantics and mandatory passes for one family.

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
        ensure_unique_ids(
            self.mandatory_governance_passes,
            key_fn=lambda item: item,
            label="mandatory_governance_passes",
        )
        return self


class ObservationFamilyPolicyRegistry(KernelModel):
    """Provide total family coverage for observation governance defaults.

    Validators require one policy entry per :class:`ObservationFamily`, so
    routing code can rely on deterministic lookup without ad-hoc fallback logic.
    """

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
        """Return the governance policy for ``family``.

        Args:
            family: Observation family whose default identification and mandatory
                passes should be retrieved.

        Returns:
            The configured family policy.
        """
        return self.policies[family.value]

    def mandatory_pass_mapping(self) -> dict[str, list[str]]:
        """Export only family -> mandatory pass ids for bundle manifests."""
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
    """Materialize family-to-pass routing for readiness and execution manifests.

    This is the bundle-friendly form of the family policy registry: it keeps
    only the pass requirements that must be enforced globally or per family.
    """

    schema_version: str = Field("1.0", pattern=SCHEMA_VERSION_PATTERN)
    global_mandatory_passes: list[str] = Field(default_factory=list, min_length=1)
    family_passes: dict[str, list[str]] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_mapping(self) -> "GovernancePassMappingRegistry":
        ensure_unique_ids(
            self.global_mandatory_passes,
            key_fn=lambda item: item,
            label="global_mandatory_passes",
        )
        known_families = {family.value for family in ObservationFamily}
        for family in ObservationFamily:
            if family.value not in self.family_passes:
                raise ValueError(f"missing governance mapping for family: {family.value}")
        for family_key, passes in self.family_passes.items():
            if family_key not in known_families:
                raise ValueError(f"unknown observation family in mapping: {family_key}")
            ensure_unique_ids(
                passes,
                key_fn=lambda item: item,
                label=f"family pass mapping for {family_key}",
            )
        return self

    def for_family(self, family: ObservationFamily, *, include_global: bool = False) -> list[str]:
        """Return pass ids required for one family, optionally including global passes."""
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
        """Build a bundle-friendly pass mapping from a family policy registry."""
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
