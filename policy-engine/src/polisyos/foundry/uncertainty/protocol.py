"""Define the result and strategy contracts for Foundry uncertainty propagation."""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from inspect import Parameter, Signature, signature
from statistics import NormalDist
from typing import Any, Protocol

from polisyos.ir.analytics.uncertainty import (
    DistributionFamily,
    IntervalSemantics,
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
        metadata: Mapping[str, Any] | None = None,
    ) -> UncertaintyDecomposition:
        if not (0.0 < confidence_level < 1.0):
            raise ValueError("confidence_level must be in (0, 1)")
        epi = max(float(epistemic_std), 0.0)
        ale = max(float(aleatoric_std), 0.0)
        total_std = math.sqrt(epi * epi + ale * ale)
        base_metadata = dict(metadata or {})
        total = gaussian_uncertainty_envelope(
            point_estimate=point_estimate,
            std=total_std,
            confidence_level=confidence_level,
            source=source,
            distribution_family=distribution_family,
            propagation_method=propagation_method,
            metadata={**base_metadata, "component": "total"},
        )
        epistemic = gaussian_uncertainty_envelope(
            point_estimate=point_estimate,
            std=epi,
            confidence_level=confidence_level,
            source=source,
            distribution_family=distribution_family,
            propagation_method=propagation_method,
            metadata={**base_metadata, "component": "epistemic"},
        )
        aleatoric = gaussian_uncertainty_envelope(
            point_estimate=point_estimate,
            std=ale,
            confidence_level=confidence_level,
            source=source,
            distribution_family=distribution_family,
            propagation_method=propagation_method,
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
    metadata: Mapping[str, Any] | None = None,
) -> UncertaintyEnvelope:
    """Build a Gaussian envelope from a point estimate and one standard deviation."""

    if not (0.0 < confidence_level < 1.0):
        raise ValueError("confidence_level must be in (0, 1)")
    sigma = max(float(std), 0.0)
    z_value = NormalDist().inv_cdf((1.0 + confidence_level) / 2.0)
    lower = float(point_estimate) - z_value * sigma
    upper = float(point_estimate) + z_value * sigma
    if lower > upper:
        lower, upper = upper, lower
    return UncertaintyEnvelope(
        point_estimate=float(point_estimate),
        confidence_interval=(lower, upper),
        confidence_level=float(confidence_level),
        distribution_family=distribution_family,
        source=source,
        propagation_method=propagation_method,
        interval_semantics=IntervalSemantics.CREDIBLE_INTERVAL,
        sample_size=None,
        metadata=dict(metadata or {}),
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
