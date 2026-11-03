"""Define the result and strategy contracts for Foundry uncertainty propagation."""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from inspect import Parameter, Signature, signature
from statistics import NormalDist
from typing import Any, Protocol

from polisyos.ir.analytics.uncertainty import (
    CompositionProvenance,
    DistributionFamily,
    IntervalSemantics,
    NumericPolicySpec,
    NumericToleranceMode,
    PropagationMethod,
    UncertaintyEnvelope,
    UncertaintySource,
)


@dataclass(frozen=True)
class PropagationResult:
    """Capture one propagated envelope plus the diagnostics needed for replay and audit."""

    metric_id: str
    envelope: UncertaintyEnvelope
    input_envelopes_used: list[str]
    method_used: PropagationMethod
    diagnostics: dict[str, Any]


@dataclass(frozen=True)
class UncertaintyDecomposition:
    """Separate total uncertainty into epistemic and aleatoric components."""

    metric_id: str
    total: UncertaintyEnvelope
    epistemic: UncertaintyEnvelope | None = None
    aleatoric: UncertaintyEnvelope | None = None
    diagnostics: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "metric_id": self.metric_id,
            "total": self.total.model_dump(mode="python"),
            "epistemic": (
                None if self.epistemic is None else self.epistemic.model_dump(mode="python")
            ),
            "aleatoric": (
                None if self.aleatoric is None else self.aleatoric.model_dump(mode="python")
            ),
            "diagnostics": dict(self.diagnostics),
        }

    @classmethod
    def from_gaussian_components(
        cls,
        *,
        metric_id: str,
        point_estimate: float,
        confidence_level: float,
        epistemic_std: float,
        aleatoric_std: float,
        source: UncertaintySource = UncertaintySource.CALIBRATION,
        distribution_family: DistributionFamily = DistributionFamily.NORMAL,
        propagation_method: PropagationMethod = PropagationMethod.MONTE_CARLO,
        interval_semantics: IntervalSemantics = IntervalSemantics.CREDIBLE_INTERVAL,
        is_heuristic_ci: bool = False,
        gate_eligible: bool = True,
        composition_provenance: CompositionProvenance | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> UncertaintyDecomposition:
        if not (0.0 < confidence_level < 1.0):
            raise ValueError("confidence_level must be in (0, 1)")
        supplied_epi = float(epistemic_std)
        supplied_ale = float(aleatoric_std)
        if not math.isfinite(supplied_epi) or not math.isfinite(supplied_ale):
            raise ValueError("Gaussian component scales must be finite")
        epi = max(supplied_epi, 0.0)
        ale = max(supplied_ale, 0.0)
        total_std = math.hypot(epi, ale)
        base_metadata = dict(metadata or {})
        total = gaussian_uncertainty_envelope(
            point_estimate=point_estimate,
            std=total_std,
            confidence_level=confidence_level,
            source=source,
            distribution_family=distribution_family,
            propagation_method=propagation_method,
            interval_semantics=interval_semantics,
            is_heuristic_ci=is_heuristic_ci,
            gate_eligible=gate_eligible,
            composition_provenance=composition_provenance,
            metadata={**base_metadata, "component": "total"},
        )
        epistemic = gaussian_uncertainty_envelope(
            point_estimate=point_estimate,
            std=epi,
            confidence_level=confidence_level,
            source=source,
            distribution_family=distribution_family,
            propagation_method=propagation_method,
            interval_semantics=interval_semantics,
            is_heuristic_ci=is_heuristic_ci,
            gate_eligible=gate_eligible,
            composition_provenance=composition_provenance,
            metadata={**base_metadata, "component": "epistemic"},
        )
        aleatoric = gaussian_uncertainty_envelope(
            point_estimate=point_estimate,
            std=ale,
            confidence_level=confidence_level,
            source=source,
            distribution_family=distribution_family,
            propagation_method=propagation_method,
            interval_semantics=interval_semantics,
            is_heuristic_ci=is_heuristic_ci,
            gate_eligible=gate_eligible,
            composition_provenance=composition_provenance,
            metadata={**base_metadata, "component": "aleatoric"},
        )
        return cls(
            metric_id=metric_id,
            total=total,
            epistemic=epistemic,
            aleatoric=aleatoric,
            diagnostics={
                "confidence_level": confidence_level,
                "epistemic_std": epi,
                "aleatoric_std": ale,
                "total_std": total_std,
            },
        )


def gaussian_uncertainty_envelope(
    *,
    point_estimate: float,
    std: float,
    confidence_level: float,
    source: UncertaintySource,
    distribution_family: DistributionFamily = DistributionFamily.NORMAL,
    propagation_method: PropagationMethod = PropagationMethod.MONTE_CARLO,
    interval_semantics: IntervalSemantics = IntervalSemantics.CREDIBLE_INTERVAL,
    is_heuristic_ci: bool = False,
    gate_eligible: bool = True,
    composition_provenance: CompositionProvenance | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> UncertaintyEnvelope:
    """Build a Gaussian envelope from a point estimate and one standard deviation."""

    if not (0.0 < confidence_level < 1.0):
        raise ValueError("confidence_level must be in (0, 1)")
    semantics = IntervalSemantics(interval_semantics)
    if semantics is IntervalSemantics.DETERMINISTIC_BOUNDS:
        raise ValueError("Gaussian quantiles do not establish deterministic bounds")
    point = float(point_estimate)
    supplied_sigma = float(std)
    if not math.isfinite(point) or not math.isfinite(supplied_sigma):
        raise ValueError("Gaussian point and scale must be finite")
    sigma = max(supplied_sigma, 0.0)
    z_value = NormalDist().inv_cdf((1.0 + confidence_level) / 2.0)
    lower = point - z_value * sigma
    upper = point + z_value * sigma
    if lower > upper:
        lower, upper = upper, lower
    if not math.isfinite(lower) or not math.isfinite(upper):
        raise ValueError("Gaussian interval bounds must be finite")
    if sigma > 0.0 and not lower < point < upper:
        raise ValueError("binary64 cannot represent the nonzero Gaussian interval")
    numeric_policy = NumericPolicySpec()
    canonical_point = numeric_policy.canonicalize(point)
    canonical_lower = numeric_policy.canonicalize(lower)
    canonical_upper = numeric_policy.canonicalize(upper)
    assert canonical_point is not None
    assert canonical_lower is not None
    assert canonical_upper is not None
    if sigma > 0.0 and not canonical_lower < canonical_point < canonical_upper:
        # Keep the existing compact profile unless it would erase a real bound.
        numeric_policy = NumericPolicySpec(mode=NumericToleranceMode.DECIMAL_EXACT)
    envelope_metadata = dict(metadata or {})
    statistical = semantics in {
        IntervalSemantics.CONFIDENCE_INTERVAL,
        IntervalSemantics.CREDIBLE_INTERVAL,
    }
    if not statistical:
        envelope_metadata["gaussian_reference_level"] = float(confidence_level)
    return UncertaintyEnvelope(
        numeric_policy=numeric_policy,
        point_estimate=point,
        confidence_interval=(lower, upper),
        confidence_level=float(confidence_level) if statistical else None,
        distribution_family=distribution_family,
        source=source,
        propagation_method=propagation_method,
        interval_semantics=semantics,
        is_heuristic_ci=is_heuristic_ci,
        gate_eligible=gate_eligible,
        composition_provenance=composition_provenance,
        sample_size=None,
        metadata=envelope_metadata,
    )


class PropagationStrategy(Protocol):
    """Protocol implemented by uncertainty backends that propagate input envelopes forward."""

    @property
    def method(self) -> PropagationMethod: ...

    def propagate(
        self,
        simulation_fn: Callable[..., Mapping[str, float]],
        nominal_params: Mapping[str, float],
        input_envelopes: Mapping[str, UncertaintyEnvelope],
        output_metric_ids: list[str],
    ) -> list[PropagationResult]: ...


def _validate_effective_inputs(
    simulation_fn: Callable[..., Mapping[str, float]],
    nominal_params: Mapping[str, float],
    input_param_names: list[str],
) -> None:
    """Validate the complete evaluator binding before any propagation calls.

    Uncertain coordinates must have an explicit nominal point. Fixed coordinates may be
    supplied in ``nominal_params`` or intentionally resolved by a callable default. Opaque
    callables require an inspectable adapter before they can be evaluated.

    Args:
        simulation_fn: Evaluator that will receive the effective input mapping.
        nominal_params: Fixed inputs plus nominal points for uncertain coordinates.
        input_param_names: Names of the uncertain coordinates.

    Raises:
        ValueError: If an uncertain coordinate has no nominal point or the effective mapping
            leaves a required evaluator input unresolved.
    """
    missing_nominal = sorted(set(input_param_names).difference(nominal_params))
    if missing_nominal:
        raise ValueError(
            "uncertain parameters require nominal values: " + ", ".join(missing_nominal)
        )

    try:
        fn_signature = signature(simulation_fn)
    except (TypeError, ValueError) as exc:
        raise ValueError("evaluator requires an inspectable signature or adapter") from exc

    try:
        fn_signature.bind(**nominal_params)
    except TypeError as exc:
        unresolved = _required_unbound_parameters(fn_signature, nominal_params)
        if unresolved:
            raise ValueError(
                "effective inputs leave required parameters unresolved: " + ", ".join(unresolved)
            ) from exc
        raise ValueError(f"effective inputs do not bind the evaluator: {exc}") from exc


def _required_unbound_parameters(
    fn_signature: Signature,
    nominal_params: Mapping[str, float],
) -> list[str]:
    """Return required named inputs absent from an effective input mapping."""
    return [
        name
        for name, parameter in fn_signature.parameters.items()
        if parameter.default is Parameter.empty
        and parameter.kind in (Parameter.POSITIONAL_OR_KEYWORD, Parameter.KEYWORD_ONLY)
        and name not in nominal_params
    ]


__all__ = [
    "PropagationResult",
    "PropagationStrategy",
    "UncertaintyDecomposition",
    "gaussian_uncertainty_envelope",
]
