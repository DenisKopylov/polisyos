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

from pydantic import BaseModel, ConfigDict, Field

from polisyos.ir.analytics.partial_identification import PartialIdentificationResult


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

    def has_partial_bounds(self) -> bool:
        """Return True if partial identification bounds are available."""
        return self.partial_bounds is not None

    def to_summary(self) -> str:
        """Return a concise human-readable summary."""
        bounds_str = ""
        if self.partial_bounds is not None:
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
        if blocking_type == BlockingType.MISSING_DISTRIBUTION:
            refs_str = ", ".join(missing_dataset_refs) if missing_dataset_refs else "unknown"
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


__all__ = ["BlockingType", "NegativeCertificate", "SuggestedExperiment"]
