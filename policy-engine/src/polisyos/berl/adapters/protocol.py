"""Adapter contract shared by BERL explanation methods."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Mapping


class AdapterUnavailableError(RuntimeError):
    """Raised when an optional explanation backend is not installed."""


class ScalarModel(Protocol):
    """Callable scalar-output model interface used by local explanation adapters."""

    def __call__(self, features: Mapping[str, float]) -> float: ...


@dataclass(frozen=True, slots=True)
class ExplanationContext:
    """Runtime context that scopes an explanation claim."""

    feature_names: tuple[str, ...]
    output_scale: str
    perturbation_distribution: str
    feature_dependence_policy: str
    confidence: float = 0.95
    random_seed: int | None = None
    params: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class RawExplanation:
    """Adapter-native explanation payload before bundle validation."""

    method_id: str
    attributions: Mapping[str, float]
    group_attributions: Mapping[str, float] = field(default_factory=dict)
    params: Mapping[str, object] = field(default_factory=dict)
    assumptions: Mapping[str, object] = field(default_factory=dict)
    estimator_uncertainty: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class UncertaintyReport:
    """Method-estimator uncertainty report."""

    standard_errors: Mapping[str, float] = field(default_factory=dict)
    confidence_intervals: Mapping[str, tuple[float, float]] = field(default_factory=dict)
    diagnostic: str = "not_reported"

    def as_payload(self) -> dict[str, object]:
        """Return a JSON-friendly uncertainty payload."""

        return {
            "standard_errors": dict(self.standard_errors),
            "confidence_intervals": {
                feature: [lower, upper]
                for feature, (lower, upper) in self.confidence_intervals.items()
            },
            "diagnostic": self.diagnostic,
        }


@dataclass(frozen=True, slots=True)
class AssumptionReport:
    """Method-level assumption declaration."""

    output_scale: str
    perturbation_distribution: str
    feature_dependence_policy: str
    causal_claim_made: bool = False
    notes: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class UnavailableAdapter:
    """Fail-closed adapter base for optional explainer backends."""

    method_id: str
    diagnostic: str

    def explain(
        self,
        model: ScalarModel,
        x: Mapping[str, float],
        context: ExplanationContext,
    ) -> RawExplanation:
        del model, x, context
        raise AdapterUnavailableError(self.diagnostic)

    def reconstruct_delta(
        self,
        explanation: RawExplanation,
        perturbation: Mapping[str, float],
    ) -> float:
        del explanation, perturbation
        raise AdapterUnavailableError(self.diagnostic)

    def estimator_uncertainty(self, explanation: RawExplanation) -> UncertaintyReport:
        del explanation
        return UncertaintyReport(diagnostic="backend_unavailable")

    def assumptions(self, context: ExplanationContext) -> AssumptionReport:
        return AssumptionReport(
            output_scale=context.output_scale,
            perturbation_distribution=context.perturbation_distribution,
            feature_dependence_policy=context.feature_dependence_policy,
            causal_claim_made=False,
            notes=(self.diagnostic,),
        )


class ExplanationAdapter(Protocol):
    """Protocol every BERL explanation method adapter must implement."""

    method_id: str

    def explain(
        self,
        model: ScalarModel,
        x: Mapping[str, float],
        context: ExplanationContext,
    ) -> RawExplanation: ...

    def reconstruct_delta(
        self,
        explanation: RawExplanation,
        perturbation: Mapping[str, float],
    ) -> float: ...

    def estimator_uncertainty(self, explanation: RawExplanation) -> UncertaintyReport: ...

    def assumptions(self, context: ExplanationContext) -> AssumptionReport: ...
