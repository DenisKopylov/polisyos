"""Twin-network IR types for Pearl counterfactual queries.

A twin network duplicates the SCM graph into two parallel worlds that share
the same exogenous noise (U) variables.  This enables computing the joint
distribution P(Y(x₀), Y(x₁)) and per-unit Individual Treatment Effects (ITE).

Pearl's three-step Abduction–Action–Prediction algorithm:
  1. Abduction  – infer U from factual observation (X=x₀, Y=y₀, …)
  2. Action     – apply counterfactual intervention do(X=x₁)
  3. Prediction – forward-simulate using the abducted U to get Y(x₁)

The factual and counterfactual worlds share the *same* U realisation,
which is what creates the individual-level correlation between Y(x₀) and Y(x₁).
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from polisyos.ir.analytics.uncertainty import (
    DistributionFamily,
    IntervalSemantics,
    PropagationMethod,
    UncertaintyEnvelope,
    UncertaintySource,
)
from polisyos.ir.artifacts import ArtifactStore, InputRef, get_json_artifact, put_json_artifact
from polisyos.ir.canon import CanonSpec
from polisyos.ir.refs import TwinNetworkResultRef

if TYPE_CHECKING:
    from polisyos.ir.analytics.causal_queries import InterventionSpec
else:
    from polisyos.ir.analytics.causal_queries import InterventionSpec


class TwinWorldSample(BaseModel):
    """One realisation of the factual + counterfactual world sharing the same U."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    factual_values: dict[str, float]
    """Node values in the factual world (do(X=x₀) with abducted noise)."""

    counterfactual_values: dict[str, float]
    """Node values in the counterfactual world (do(X=x₁) with the same noise)."""

    individual_treatment_effect: float
    """ITE = counterfactual_outcome − factual_outcome for the designated outcome."""

    @field_validator("individual_treatment_effect", mode="before")
    @classmethod
    def _coerce_ite(cls, value: Any) -> Any:
        casted = float(value)
        if not math.isfinite(casted):
            raise ValueError("individual_treatment_effect must be finite")
        return casted


class TwinNetworkResult(BaseModel):
    """Output of a twin-network joint counterfactual query."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    outcome_variable: str

    factual_intervention: InterventionSpec
    """The intervention applied in the factual world (x₀)."""

    counterfactual_intervention: InterventionSpec
    """The intervention applied in the counterfactual world (x₁)."""

    # ── Potential outcome marginals ────────────────────────────────────────────
    po_factual_mean: float
    """E[Y(x₀)] — marginal mean of the factual potential outcome."""

    po_factual_std: float = Field(ge=0.0)
    """Std dev of Y(x₀)."""

    po_counter_mean: float
    """E[Y(x₁)] — marginal mean of the counterfactual potential outcome."""

    po_counter_std: float = Field(ge=0.0)
    """Std dev of Y(x₁)."""

    # ── Individual Treatment Effect ────────────────────────────────────────────
    ite_mean: float
    """E[Y(x₁) − Y(x₀)] = E[ITE].  Equals the ATE under the abduction condition."""

    ite_std: float = Field(ge=0.0)
    """Std dev of the ITE distribution — non-zero when individual responses vary."""

    ite_ci: tuple[float, float]
    """Percentile confidence interval for the ITE."""

    # ── Dependence between potential outcomes ──────────────────────────────────
    po_correlation: float = Field(ge=-1.0, le=1.0)
    """Corr(Y(x₀), Y(x₁)).

    Key twin-network quantity: positive when shared noise drives both potential
    outcomes in the same direction.  Values near 1 indicate near-deterministic
    individual responses (small ITE variance); values near 0 indicate that the
    treatment effect is highly heterogeneous across units.
    """

    # ── Optional full distributions (omit to save memory) ─────────────────────
    ite_distribution: list[float] | None = None
    po_factual_distribution: list[float] | None = None
    po_counter_distribution: list[float] | None = None

    # ── Diagnostics ───────────────────────────────────────────────────────────
    computation_time_seconds: float = Field(default=0.0, ge=0.0)
    abduction_warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    # ── Validators ────────────────────────────────────────────────────────────

    @field_validator(
        "po_factual_mean",
        "po_factual_std",
        "po_counter_mean",
        "po_counter_std",
        "ite_mean",
        "ite_std",
        "computation_time_seconds",
        mode="before",
    )
    @classmethod
    def _coerce_scalar(cls, value: Any) -> Any:
        casted = float(value)
        if not math.isfinite(casted):
            raise ValueError("numeric fields must be finite")
        return casted

    @field_validator("ite_ci", mode="before")
    @classmethod
    def _coerce_ci(cls, value: Any) -> Any:
        if not isinstance(value, (tuple, list)) or len(value) != 2:
            raise ValueError("ite_ci must be a 2-element tuple/list")
        lo = float(value[0])
        hi = float(value[1])
        if not math.isfinite(lo) or not math.isfinite(hi):
            raise ValueError("ite_ci bounds must be finite")
        return (lo, hi)

    @field_validator("po_correlation", mode="before")
    @classmethod
    def _coerce_correlation(cls, value: Any) -> Any:
        casted = float(value)
        if not math.isfinite(casted):
            raise ValueError("po_correlation must be finite")
        return float(max(-1.0, min(1.0, casted)))

    @field_validator(
        "ite_distribution", "po_factual_distribution", "po_counter_distribution", mode="before"
    )
    @classmethod
    def _coerce_distribution(cls, value: Any) -> Any:
        if value is None:
            return None
        if not isinstance(value, list):
            raise ValueError("distribution fields must be lists of floats")
        normalized: list[float] = []
        for item in value:
            casted = float(item)
            if not math.isfinite(casted):
                raise ValueError("distribution values must be finite")
            normalized.append(casted)
        return normalized

    @model_validator(mode="after")
    def _validate_result(self) -> TwinNetworkResult:
        lo, hi = self.ite_ci
        if lo > hi:
            raise ValueError("ite_ci lower cannot exceed upper")
        if not math.isfinite(self.po_correlation):
            raise ValueError("po_correlation must be finite")
        return self

    # ── Integration with uncertainty system ───────────────────────────────────

    def to_uncertainty_envelope(self) -> UncertaintyEnvelope:
        """Convert ITE summary to a standard UncertaintyEnvelope."""
        ci_lo, ci_hi = self.ite_ci
        return UncertaintyEnvelope(
            point_estimate=float(self.ite_mean),
            confidence_interval=(float(ci_lo), float(ci_hi)),
            confidence_level=0.95,
            distribution_family=DistributionFamily.BOOTSTRAP,
            source=UncertaintySource.CAUSAL,
            propagation_method=PropagationMethod.MONTE_CARLO,
            interval_semantics=IntervalSemantics.CONFIDENCE_INTERVAL,
            sample_size=len(self.ite_distribution) if self.ite_distribution is not None else 0,
            is_heuristic_ci=False,
            gate_eligible=True,
            metadata={
                "query_type": "twin_network",
                "outcome_variable": self.outcome_variable,
                "ite_std": self.ite_std,
                "po_correlation": self.po_correlation,
                **dict(self.metadata),
            },
        )


# ── Persistence helpers ────────────────────────────────────────────────────────


def persist_twin_network_result(
    store: ArtifactStore,
    result: TwinNetworkResult,
    *,
    inputs: list[InputRef] | None = None,
    schema_name: str = "ir.twin_network_result",
    schema_version: str = "1.0",
) -> TwinNetworkResultRef:
    """Persist a TwinNetworkResult to the artifact store."""
    ref = put_json_artifact(
        store,
        result.model_dump(mode="json"),
        kind="ir.twin_network_result",
        schema_name=schema_name,
        schema_version=schema_version,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return TwinNetworkResultRef.model_validate(ref)


def load_twin_network_result(
    store: ArtifactStore,
    ref: TwinNetworkResultRef,
) -> TwinNetworkResult:
    """Load a TwinNetworkResult from the artifact store."""
    payload = get_json_artifact(store, ref.artifact_id)
    return TwinNetworkResult.model_validate(payload)


__all__ = [
    "TwinNetworkResult",
    "TwinWorldSample",
    "load_twin_network_result",
    "persist_twin_network_result",
]
