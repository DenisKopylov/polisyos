"""Public uncertainty analytical module API."""

from __future__ import annotations

import math
from collections.abc import Mapping
from statistics import NormalDist

import jax.numpy as jnp

from polisyos.ir.analytics.uncertainty import (
    CertificateKind,
    ComposedFlavour,
    DistributionFamily,
    ExactnessKind,
    IntervalSemantics,
    ParametricFitCarrier,
    PropagationMethod,
    UncertaintyEnvelope,
    UncertaintySource,
    _merge_certificate_kind,
    _merge_certificate_radii,
    _propagate_certificate_radius,
    _worst_exactness,
    build_composition_provenance,
)

from .covariance import build_covariance_matrix, has_unknown_dependency
from .protocol import PropagationResult


class AnalyticalPropagator:
    """Analytical propagator public type."""

    @property
    def method(self) -> PropagationMethod:
        return PropagationMethod.ANALYTICAL

    @staticmethod
    def is_applicable(input_envelopes: Mapping[str, UncertaintyEnvelope]) -> bool:
        return not has_unknown_dependency(input_envelopes) and all(
            env.distribution_family == DistributionFamily.NORMAL for env in input_envelopes.values()
        )

    @staticmethod
    def propagate_linear_combination(
        *,
        weights: Mapping[str, float],
        input_envelopes: Mapping[str, UncertaintyEnvelope],
        output_metric_id: str,
        confidence_level: float = 0.95,
        covariance: jnp.ndarray | None = None,
        use_full_covariance: bool = True,
    ) -> PropagationResult:
        param_names = sorted(input_envelopes)
        if covariance is None:
            covariance = build_covariance_matrix(
                param_names,
                input_envelopes,
                use_full_covariance=use_full_covariance,
                jitter=0.0,
            )

        mean = 0.0
        for name, weight in weights.items():
            env = input_envelopes[name]
            mean += float(weight) * float(env.point_estimate)

        weight_vector = jnp.asarray(
            [float(weights.get(name, 0.0)) for name in param_names],
            dtype=jnp.float32,
        )
        variance = float(weight_vector @ covariance @ weight_vector)
        variance = max(variance, 0.0)
        names = [name for name in param_names if name in weights]

        std_out = math.sqrt(max(variance, 0.0))
        z = NormalDist().inv_cdf((1.0 + confidence_level) / 2.0)
        lo = mean - z * std_out
        hi = mean + z * std_out
        ordered_inputs = tuple(input_envelopes[name] for name in param_names)
        lipschitz_bound = sum(abs(float(weight)) for weight in weights.values())
        exactness = _worst_exactness(ordered_inputs)
        if exactness is ExactnessKind.EXACT:
            certificate_kind = CertificateKind.EXACT
            certificate_radius: float | dict[str, float] | None = 0.0
        else:
            certificate_kind = _merge_certificate_kind(ordered_inputs)
            certificate_radius = _propagate_certificate_radius(
                _merge_certificate_radii(ordered_inputs),
                lipschitz_bound=lipschitz_bound,
            )

        envelope = UncertaintyEnvelope(
            point_estimate=float(mean),
            confidence_interval=(float(lo), float(hi)),
            confidence_level=confidence_level,
            distribution_family=DistributionFamily.NORMAL,
            distribution_payload=ParametricFitCarrier(
                family=DistributionFamily.NORMAL,
                parameters={"mean": float(mean), "std": float(std_out)},
            ),
            source=UncertaintySource.ENSEMBLE,
            propagation_method=PropagationMethod.ANALYTICAL,
            interval_semantics=IntervalSemantics.CONFIDENCE_INTERVAL,
            is_heuristic_ci=False,
            # Propagation cannot promote a non-gate-eligible input into a gate.
            gate_eligible=all(envelope.gate_eligible for envelope in ordered_inputs),
            metadata={
                "formula": "linear_combination_normal",
                "weights": dict(weights),
                "output_std": float(std_out),
                "used_full_covariance": use_full_covariance,
            },
            composition_provenance=build_composition_provenance(
                input_envelopes=ordered_inputs,
                op="push_forward",
                stage_name="foundry.analytical.linear_combination",
                output_flavour=ComposedFlavour.ANALYTICAL,
                exactness=exactness,
                certificate_kind=certificate_kind,
                certificate_radius=certificate_radius,
                confidence_level=confidence_level,
                scope=("expectation", "interval", "quantile", "cdf"),
                map_name="linear_combination",
                lipschitz_bound=float(lipschitz_bound),
                variance_bound=float(variance),
                assumptions=(
                    "linear_gaussian_push_forward",
                    "joint_covariance" if use_full_covariance else "diagonal_covariance",
                ),
                notes={
                    "weights": dict(weights),
                    "used_full_covariance": use_full_covariance,
                },
            ),
        )

        return PropagationResult(
            metric_id=output_metric_id,
            envelope=envelope,
            input_envelopes_used=names,
            method_used=PropagationMethod.ANALYTICAL,
            diagnostics={"output_variance": float(variance), "output_std": float(std_out)},
        )
