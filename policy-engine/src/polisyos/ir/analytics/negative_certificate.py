"""NegativeCertificate IR — constructive explanation of non-identifiability.

When the causal identification engine cannot identify a query, it produces
a NegativeCertificate that explains *why* identification failed and *what*
additional data or assumptions would be needed to resolve the blockage.

This is the public, JSON-serializable counterpart of the internal
``HedgeCertificate`` frozen dataclass in ``id_engine.py``.
"""
from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.ir.artifacts import ArtifactStore, InputRef, get_json_artifact, put_json_artifact
from polisyos.ir.canon import CanonSpec
from polisyos.ir.analytics.partial_identification import (
    BoundsBundle,
    PartialIdentificationResult,
    SensitivitySweepResult,
    bounds_bundle_from_partial_identification_result,
)
from polisyos.ir.refs import NegativeCertificateRef


class BlockingType(str, Enum):
    """Category of the identification barrier."""

    HEDGE_STRUCTURE = "hedge_structure"
    """A hedge structure (F, F') was found — the estimand is not nonparametrically identifiable."""

    S_NODE_UNRESOLVED = "s_node_unresolved"
    """One or more S-nodes (selection/context shift nodes) could not be resolved by any backend."""

    POSITIVITY_VIOLATION = "positivity_violation"
    """The positivity / overlap assumption is violated or near-violated in the data."""

    SUPPORT_MISMATCH = "support_mismatch"
    """The support of the target distribution does not overlap with the source distribution."""

    MISSING_DISTRIBUTION = "missing_distribution"
    """A required conditional distribution is not available in any dataset."""

    MISSINGNESS_NOT_RECOVERABLE = "missingness_not_recoverable"
    """The requested functional is blocked by the missingness graph."""

    SEMANTICS_NOT_WELL_DEFINED = "semantics_not_well_defined"
    """The cyclic or dynamic SCM does not yet have a certified intervention semantics."""

    COUPLING_NOT_IDENTIFIED = "coupling_not_identified"
    """Marginal counterfactual laws are available, but the joint/coupling object is not causally identified."""

    INTERVENTION_TYPECHECK = "intervention_typecheck"
    """The requested intervention expression or composition is ill-typed."""

    PROXIMAL_CONDITION_FAILED = "proximal_condition_failed"
    """A machine-checkable proximal identification condition failed."""

    OUT_OF_SCOPE_FOR_PROXIMAL_V1 = "out_of_scope_for_proximal_v1"
    """The query or graph is outside the conservative proximal v1 coverage."""


class SuggestedExperiment(BaseModel):
    """Structured description of an experiment or data collection strategy.

    Replaces the bare ``str`` in the old ``suggested_experiments: tuple[str, ...]``
    with a typed object that downstream tools (e.g. CausalQueryValidator) can
    inspect programmatically.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    required_variables: tuple[str, ...]
    """Variables that must be measured / intervened on in this experiment."""

    domain: str = "target"
    """Domain where the data should be collected ('target' | 'experimental' | 'source')."""

    design_type: str = "observational"
    """Study design: 'RCT' | 'natural_experiment' | 'IV' | 'observational' | 'DiD' | 'RDD'."""

    description: str = ""
    """Human-readable description of the experiment or data collection strategy."""


class EpistemicTier(str, Enum):
    """Epistemic strength of a fallback artifact."""

    EXACT_NONPARAMETRIC = "exact_nonparametric"
    PARTIAL_IDENTIFICATION = "partial_identification"
    ASSUMPTION_DEPENDENT = "assumption_dependent"
    DIAGNOSTIC_GUIDANCE = "diagnostic_guidance"


class ParametricRescueResult(BaseModel):
    """Assumption-dependent fallback artifact."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    assumption: str
    method: str = ""
    description: str = ""
    bounds: PartialIdentificationResult | None = None
    point_estimate: float | None = None
    standard_error: float | None = None
    estimand_formula: str | None = None
    supporting_variables: tuple[str, ...] = ()
    diagnostics: dict[str, Any] = Field(default_factory=dict)
    warnings: tuple[str, ...] = ()


class FallbackResult(BaseModel):
    """Typed hedge fallback chain output with explicit epistemic tiers."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: str = "1.0"
    bounds: PartialIdentificationResult | None = None
    bounds_tier: EpistemicTier | None = None
    parametric_rescue: ParametricRescueResult | None = None
    parametric_tier: EpistemicTier | None = None
    sensitivity_sweep: SensitivitySweepResult | None = None
    sensitivity_tier: EpistemicTier | None = None
    suggested_experiments: tuple[SuggestedExperiment, ...] = ()
    experiments_tier: EpistemicTier | None = None
    fallback_level: int = 0
    highest_tier_reached: EpistemicTier | None = None
    notes: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _derive_metadata(self) -> "FallbackResult":
        fallback_level = 0
        candidates: list[EpistemicTier] = []
        if self.bounds is not None and self.bounds_tier is not None:
            fallback_level = max(fallback_level, 1)
            candidates.append(self.bounds_tier)
        if self.parametric_rescue is not None and self.parametric_tier is not None:
            fallback_level = max(fallback_level, 2)
            candidates.append(self.parametric_tier)
        if self.sensitivity_sweep is not None and self.sensitivity_tier is not None:
            fallback_level = max(fallback_level, 3)
            candidates.append(self.sensitivity_tier)
        if self.suggested_experiments and self.experiments_tier is not None:
            fallback_level = max(fallback_level, 4)
            candidates.append(self.experiments_tier)

        object.__setattr__(self, "fallback_level", fallback_level)
        if candidates:
            rank = {
                EpistemicTier.EXACT_NONPARAMETRIC: 0,
                EpistemicTier.PARTIAL_IDENTIFICATION: 1,
                EpistemicTier.ASSUMPTION_DEPENDENT: 2,
                EpistemicTier.DIAGNOSTIC_GUIDANCE: 3,
            }
            object.__setattr__(self, "highest_tier_reached", min(candidates, key=rank.get))
        return self

    def to_diagnostics_dict(self) -> dict[str, Any]:
        """Flatten the fallback chain for legacy diagnostics consumers."""
        return {
            "fallback_level": self.fallback_level,
            "highest_tier_reached": (
                self.highest_tier_reached.value if self.highest_tier_reached is not None else None
            ),
            "bounds_tier": self.bounds_tier.value if self.bounds_tier is not None else None,
            "parametric_tier": (
                self.parametric_tier.value if self.parametric_tier is not None else None
            ),
            "sensitivity_tier": (
                self.sensitivity_tier.value if self.sensitivity_tier is not None else None
            ),
            "experiments_tier": (
                self.experiments_tier.value if self.experiments_tier is not None else None
            ),
            "sensitivity_curve": (
                list(
                    zip(
                        self.sensitivity_sweep.parameter_values,
                        self.sensitivity_sweep.lower_bounds,
                        self.sensitivity_sweep.upper_bounds,
                        strict=False,
                    )
                )
                if self.sensitivity_sweep is not None
                else []
            ),
            "parametric_assumption": (
                self.parametric_rescue.assumption if self.parametric_rescue is not None else None
            ),
            "parametric_method": (
                self.parametric_rescue.method if self.parametric_rescue is not None else None
            ),
            "parametric_point_estimate": (
                self.parametric_rescue.point_estimate
                if self.parametric_rescue is not None
                else None
            ),
            "parametric_standard_error": (
                self.parametric_rescue.standard_error
                if self.parametric_rescue is not None
                else None
            ),
            "parametric_formula": (
                self.parametric_rescue.estimand_formula
                if self.parametric_rescue is not None
                else None
            ),
            "parametric_supporting_variables": (
                list(self.parametric_rescue.supporting_variables)
                if self.parametric_rescue is not None
                else []
            ),
            "fallback_notes": list(self.notes),
        }


class RecoveryPlan(BaseModel):
    """Canonical next-step artifact for non-identification paths."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    blocking_reason: str
    candidate_actions: list[str] = Field(default_factory=list)
    minimal_oracle_sets: list[list[str]] = Field(default_factory=list)
    expected_width_reduction: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class NegativeCertificate(BaseModel):
    """Constructive certificate of non-identification.

    Explains why a causal query could not be identified and provides
    actionable guidance on what would be needed to proceed.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    blocking_type: BlockingType
    """Category of the identification barrier."""

    blocking_description: str
    """Human-readable description of what blocked identification."""

    technical_detail: str = ""
    """Formal / graph-theoretic description of the blocking structure."""

    required_distributions: tuple[dict[str, Any], ...] = ()
    """Serialized DistributionRef objects representing distributions that would
    be needed to achieve identification.

    Stored as dicts to avoid circular imports — use
    ``DistributionRef.model_validate(d)`` to reconstruct.
    """

    missing_dataset_refs: tuple[str, ...] = ()
    """Dataset identifiers that would need to be collected or provided."""

    suggested_experiments: tuple[SuggestedExperiment, ...] = ()
    """Structured experiment / data collection strategies that could
    provide the missing distributions."""

    partial_bounds: PartialIdentificationResult | None = None
    """Typed partial identification bounds if available (e.g. Manski or Balke-Pearl).

    None when no bounds could be computed. Use .to_ui_dict() for frontend rendering.
    """

    quantitative_diagnostics: dict[str, Any] = Field(default_factory=dict)
    """Quantitative diagnostic data, e.g. effective_sample_size, overlap_score,
    proxy_coverage_fraction, hedge_nodes_count."""

    constructive_message: str = ""
    """Actionable guidance: what to do next to unlock identification."""

    fallback_result: FallbackResult | None = None
    """Typed fallback chain artifact attached for hedge-style non-identification."""

    bounds_bundle: BoundsBundle | None = None
    """Canonical public bounds artifact. Auto-populated from transitional fields when possible."""

    recovery_plan: RecoveryPlan | None = None
    """Canonical next-step artifact. Auto-populated when omitted."""

    @model_validator(mode="after")
    def _populate_canonical_artifacts(self) -> "NegativeCertificate":
        if self.bounds_bundle is None:
            inferred = _infer_bounds_bundle(self.partial_bounds, self.fallback_result)
            if inferred is not None:
                object.__setattr__(self, "bounds_bundle", inferred)
        if self.recovery_plan is None:
            object.__setattr__(self, "recovery_plan", recovery_plan_from_negative_certificate(self))
        return self

    def has_partial_bounds(self) -> bool:
        """Return True if partial identification bounds are available."""
        return self.bounds_bundle is not None or self.partial_bounds is not None

    def to_summary(self) -> str:
        """Return a concise human-readable summary."""
        bounds_str = ""
        if self.bounds_bundle is not None:
            lo = self.bounds_bundle.lower_bound
            hi = self.bounds_bundle.upper_bound
            if lo is not None and hi is not None:
                bounds_str = f" bounds=[{lo:.3f}, {hi:.3f}]"
        elif self.partial_bounds is not None:
            lo = self.partial_bounds.lower_bound
            hi = self.partial_bounds.upper_bound
            bounds_str = f" bounds=[{lo:.3f}, {hi:.3f}]"
        return (
            f"NegativeCertificate[{self.blocking_type.value}]: "
            f"{self.blocking_description[:80]}"
            f"{bounds_str}"
        )

    @classmethod
    def auto_suggest_experiments(
        cls,
        blocking_type: BlockingType,
        missing_vars: tuple[str, ...] = (),
        missing_dataset_refs: tuple[str, ...] = (),
    ) -> tuple[SuggestedExperiment, ...]:
        """Generate suggested experiments based on the blocking type."""
        if blocking_type == BlockingType.HEDGE_STRUCTURE:
            return (
                SuggestedExperiment(
                    required_variables=missing_vars,
                    design_type="RCT",
                    description=(
                        "A randomised experiment on the treatment variable(s) would break "
                        "the hedge structure and enable non-parametric identification."
                    ),
                ),
            )
        if blocking_type in {
            BlockingType.MISSING_DISTRIBUTION,
            BlockingType.MISSINGNESS_NOT_RECOVERABLE,
        }:
            refs_str = ", ".join(missing_dataset_refs) if missing_dataset_refs else "unknown"
            if blocking_type is BlockingType.MISSINGNESS_NOT_RECOVERABLE:
                return (
                    SuggestedExperiment(
                        required_variables=missing_vars,
                        design_type="observational",
                        description=(
                            "Collect complete-case or auxiliary administrative data for "
                            f"variables {list(missing_vars)} to break the blocking "
                            "missingness path."
                        ),
                    ),
                )
            return (
                SuggestedExperiment(
                    required_variables=missing_vars,
                    design_type="observational",
                    description=(
                        f"Collect observational data containing variables {list(missing_vars)} "
                        f"from dataset(s): {refs_str}."
                    ),
                ),
            )
        if blocking_type == BlockingType.SEMANTICS_NOT_WELL_DEFINED:
            return (
                SuggestedExperiment(
                    required_variables=missing_vars,
                    design_type="observational",
                    description=(
                        "Provide a well-posedness witness for the cyclic fragment, such as a "
                        "linear unique-solution matrix, a contraction bound, or an explicitly "
                        "admissible loop mechanism."
                    ),
                ),
            )
        if blocking_type == BlockingType.COUPLING_NOT_IDENTIFIED:
            return (
                SuggestedExperiment(
                    required_variables=missing_vars,
                    design_type="observational",
                    description=(
                        "To identify the coupling or joint counterfactual law, collect panel-linked "
                        "outcomes across worlds if available, or add explicit cross-world assumptions "
                        "such as rank invariance, monotone response, or a justified transport model."
                    ),
                ),
            )
        if blocking_type == BlockingType.POSITIVITY_VIOLATION:
            return (
                SuggestedExperiment(
                    required_variables=missing_vars,
                    design_type="RCT",
                    description=(
                        "Positivity/overlap failure: consider random assignment to treatments, "
                        "or restrict analysis to the covariate region with common support."
                    ),
                ),
            )
        if blocking_type == BlockingType.S_NODE_UNRESOLVED:
            return (
                SuggestedExperiment(
                    required_variables=missing_vars,
                    domain="experimental",
                    design_type="natural_experiment",
                    description=(
                        "An unresolved S-node indicates a context/selection shift. "
                        "Collect data in the target domain or use a natural experiment "
                        "that spans source and target contexts."
                    ),
                ),
            )
        if blocking_type == BlockingType.PROXIMAL_CONDITION_FAILED:
            return (
                SuggestedExperiment(
                    required_variables=missing_vars,
                    design_type="observational",
                    description=(
                        "Provide valid treatment-inducing and outcome-inducing proxy "
                        "measurements that satisfy the proximal exclusion and latent "
                        "district relevance conditions."
                    ),
                ),
            )
        if blocking_type == BlockingType.OUT_OF_SCOPE_FOR_PROXIMAL_V1:
            return (
                SuggestedExperiment(
                    required_variables=missing_vars,
                    design_type="observational",
                    description=(
                        "Reformulate the query as a single-treatment, single-outcome "
                        "proximal query on a DAG/ADMG, or use a more general "
                        "identification backend."
                    ),
                ),
            )
        return ()

    @classmethod
    def from_mz_id_failure(
        cls,
        *,
        treatment: "frozenset[str]",
        outcome: "frozenset[str]",
        unresolved_s_nodes: "frozenset[str]",
        available_domains: "list[str]",
        missing_domains: "list[str] | None" = None,
        hedge_certificate: Any = None,
        partial_bounds: PartialIdentificationResult | None = None,
    ) -> "NegativeCertificate":
        """Build a NegativeCertificate for an mz-ID algorithm failure.

        Parameters
        ----------
        treatment          : treatment variable(s) that could not be identified
        outcome            : outcome variable(s) for the query
        unresolved_s_nodes : S-node variable names that could not be resolved
                             by any available source domain
        available_domains  : domain_id strings for all source domains that were tried
        missing_domains    : optional list of domain types or IDs that *would* resolve
                             the identification problem if collected
        hedge_certificate  : optional ``HedgeCertificate`` from id_engine (any type to
                             avoid circular import; inspected for description attribute)
        partial_bounds     : optional partial identification bounds
        """
        # Determine blocking type
        if unresolved_s_nodes:
            blocking_type = BlockingType.S_NODE_UNRESOLVED
        elif hedge_certificate is not None:
            blocking_type = BlockingType.HEDGE_STRUCTURE
        else:
            blocking_type = BlockingType.MISSING_DISTRIBUTION

        # Build human-readable description
        treatment_str = ", ".join(sorted(treatment))
        outcome_str = ", ".join(sorted(outcome))
        blocking_description = (
            f"mz-ID failed for P({outcome_str}|do({treatment_str})). "
        )
        if unresolved_s_nodes:
            blocking_description += (
                f"Unresolved S-nodes: {sorted(unresolved_s_nodes)}. "
                f"Tried {len(available_domains)} source domain(s): "
                f"{available_domains or ['(none)']}."
            )
        elif hedge_certificate is not None:
            hedge_desc = getattr(hedge_certificate, "description", "hedge structure found")
            blocking_description += f"Hedge structure: {hedge_desc}"
        else:
            blocking_description += "Required distributions are not available in any source domain."

        # Build technical detail
        technical_detail = ""
        if hedge_certificate is not None:
            hf = getattr(hedge_certificate, "hedge_forest", None)
            hr = getattr(hedge_certificate, "hedge_root", None)
            if hf is not None and hr is not None:
                technical_detail = f"Hedge: F={sorted(hf)}, F'={sorted(hr)}"

        # Constructive message
        parts: list[str] = []
        if unresolved_s_nodes:
            parts.append(
                f"To resolve S-nodes {sorted(unresolved_s_nodes)}, collect data in "
                "the target domain that covers these mechanism-shifted variables."
            )
        if missing_domains:
            parts.append(
                f"Additional source domains that would help: {missing_domains}."
            )
        if hedge_certificate is not None:
            minimal = getattr(hedge_certificate, "minimal_required_s_nodes", frozenset())
            if minimal:
                parts.append(
                    f"Breaking the hedge requires experimental data on: {sorted(minimal)}."
                )
        constructive_message = " ".join(parts) if parts else (
            "Provide additional source domains or experimental data to unlock identification."
        )

        # Suggested experiments
        suggested = cls.auto_suggest_experiments(
            blocking_type,
            missing_vars=tuple(sorted(unresolved_s_nodes)),
            missing_dataset_refs=tuple(missing_domains or []),
        )

        return cls(
            blocking_type=blocking_type,
            blocking_description=blocking_description,
            technical_detail=technical_detail,
            suggested_experiments=suggested,
            partial_bounds=partial_bounds,
            quantitative_diagnostics={
                "unresolved_s_node_count": len(unresolved_s_nodes),
                "available_domain_count": len(available_domains),
                "missing_domain_count": len(missing_domains or []),
            },
            constructive_message=constructive_message,
        )


def recovery_plan_from_negative_certificate(
    certificate: NegativeCertificate,
) -> RecoveryPlan:
    """Build a canonical recovery plan from a negative certificate and fallback chain."""
    actions: list[str] = []
    seen: set[str] = set()

    if certificate.constructive_message.strip():
        action = certificate.constructive_message.strip()
        actions.append(action)
        seen.add(action)

    for experiment in certificate.suggested_experiments:
        description = experiment.description.strip()
        if description and description not in seen:
            actions.append(description)
            seen.add(description)

    if certificate.bounds_bundle is not None and certificate.bounds_bundle.warnings:
        for warning in certificate.bounds_bundle.warnings:
            if warning not in seen:
                actions.append(warning)
                seen.add(warning)

    minimal_oracle_sets: list[list[str]] = []
    if certificate.missing_dataset_refs:
        minimal_oracle_sets.append(list(certificate.missing_dataset_refs))

    expected_width_reduction = None
    if certificate.bounds_bundle is not None:
        lo = certificate.bounds_bundle.lower_bound
        hi = certificate.bounds_bundle.upper_bound
        if lo is not None and hi is not None:
            expected_width_reduction = max(0.0, hi - lo)

    return RecoveryPlan(
        blocking_reason=certificate.blocking_description,
        candidate_actions=actions or ["Collect additional data or relax query assumptions."],
        minimal_oracle_sets=minimal_oracle_sets,
        expected_width_reduction=expected_width_reduction,
        metadata={
            "blocking_type": certificate.blocking_type.value,
            "suggested_experiment_count": len(certificate.suggested_experiments),
        },
    )


def negative_certificate_from_transport_result(
    *,
    result: Any,
    treatment: str,
    outcome: str,
) -> NegativeCertificate:
    """Build a canonical impossibility artifact from a transportability-style result."""
    blocking_s_nodes = list(getattr(result, "blocking_s_nodes", []) or [])
    blocking_type = (
        BlockingType.S_NODE_UNRESOLVED if blocking_s_nodes else BlockingType.MISSING_DISTRIBUTION
    )
    partial_bounds = getattr(result, "partial_identification_result", None)
    transport_reason = str(getattr(result, "unsupported_reason", "") or "transport_unsupported")
    suggested = NegativeCertificate.auto_suggest_experiments(
        blocking_type,
        missing_vars=tuple(getattr(node, "target_variable", str(node)) for node in blocking_s_nodes),
    )
    return NegativeCertificate(
        blocking_type=blocking_type,
        blocking_description=f"Could not identify transport query P*({outcome}|do({treatment})).",
        technical_detail=transport_reason,
        suggested_experiments=suggested,
        partial_bounds=partial_bounds if isinstance(partial_bounds, PartialIdentificationResult) else None,
        constructive_message=(
            "Provide additional target-domain evidence or use bounded transport assumptions."
        ),
        quantitative_diagnostics={
            "blocking_s_node_count": len(blocking_s_nodes),
            "transport_final_confidence": float(getattr(result, "final_confidence", 0.0) or 0.0),
        },
    )


def _infer_bounds_bundle(
    partial_bounds: PartialIdentificationResult | None,
    fallback_result: FallbackResult | None,
) -> BoundsBundle | None:
    if partial_bounds is not None:
        return bounds_bundle_from_partial_identification_result(partial_bounds)
    if fallback_result is not None and fallback_result.bounds is not None:
        return bounds_bundle_from_partial_identification_result(
            fallback_result.bounds,
            rescue_actions=[note for note in fallback_result.notes if isinstance(note, str)],
        )
    return None


def persist_negative_certificate(
    store: ArtifactStore,
    certificate: NegativeCertificate,
    *,
    inputs: list[InputRef] | None = None,
    schema_name: str = "ir.negative_certificate",
    schema_version: str = "1.0",
) -> NegativeCertificateRef:
    """Persist negative certificate helper."""
    ref = put_json_artifact(
        store,
        certificate.model_dump(mode="json"),
        kind="ir.negative_certificate",
        schema_name=schema_name,
        schema_version=schema_version,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return NegativeCertificateRef.model_validate(ref)


def load_negative_certificate(
    store: ArtifactStore,
    ref: NegativeCertificateRef,
) -> NegativeCertificate:
    """Load negative certificate."""
    payload = get_json_artifact(store, ref.artifact_id)
    return NegativeCertificate.model_validate(payload)


__all__ = [
    "BlockingType",
    "EpistemicTier",
    "FallbackResult",
    "NegativeCertificate",
    "ParametricRescueResult",
    "RecoveryPlan",
    "SuggestedExperiment",
    "load_negative_certificate",
    "negative_certificate_from_transport_result",
    "persist_negative_certificate",
    "recovery_plan_from_negative_certificate",
]
