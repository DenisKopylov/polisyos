"""Public uncertainty analytical module API."""

from __future__ import annotations

import math
from collections.abc import Mapping
from statistics import NormalDist

import jax.numpy as jnp
import numpy as np

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
from .sampling_admission import admit_float32_range, admit_sampling_support


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
        """Push a Gaussian law forward; supplied covariance uses sorted input order."""
        param_names = sorted(input_envelopes)
        admit_sampling_support(input_envelopes)
        if not param_names or any(
            env.distribution_family is not DistributionFamily.NORMAL
            for env in input_envelopes.values()
        ):
            raise ValueError("analytical Gaussian propagation requires nonempty normal inputs")
        if not set(weights).issubset(input_envelopes):
            raise ValueError("analytical weights reference an unknown input")
        admit_float32_range(list(weights.values()))
        declared_covariance = any(
            "covariance_row" in env.metadata or "covariance_params" in env.metadata
            for env in input_envelopes.values()
        )
        use_full_covariance = use_full_covariance or declared_covariance
        if declared_covariance:
            admitted_covariance = build_covariance_matrix(
                param_names,
                input_envelopes,
                use_full_covariance=True,
                jitter=0.0,
                preserve_singular=True,
            )
            if covariance is not None and not np.allclose(
                np.asarray(covariance),
                np.asarray(admitted_covariance),
                rtol=1e-7,
                atol=1e-10,
            ):
                raise ValueError("supplied covariance differs from the declared joint law")
            covariance = admitted_covariance
        if covariance is not None:
            supplied = admit_float32_range(covariance)
            if supplied.shape != (len(param_names), len(param_names)):
                raise ValueError("supplied covariance has the wrong dimension")
            # Direct callers enter the same marginal/axis/PSD admission as the
            # metadata producer. A raw array is not a prevalidated law.
            supplied_inputs = {
                name: input_envelopes[name].model_copy(
                    update={
                        "metadata": {
                            **input_envelopes[name].metadata,
                            "covariance_row": supplied[index].tolist(),
                            "covariance_params": param_names,
                        }
                    }
                )
                for index, name in enumerate(param_names)
            }
            covariance = build_covariance_matrix(
                param_names,
                supplied_inputs,
                use_full_covariance=True,
                jitter=0.0,
                preserve_singular=True,
            )
            use_full_covariance = True
        elif has_unknown_dependency(input_envelopes):
            raise ValueError("joint input law is unknown; missing covariance is not independence")
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
            gate_eligible=False,
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
