"""Public sensitivity screening module API."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, ClassVar

import numpy as np

from polisyos.core.observability.determinism import DeterminismTier
from polisyos.foundry.methods.base import (
    ComplexityClass,
    ComputeBackend,
    FidelityLevel,
    MethodMetadata,
    MethodSignature,
    ParameterSpec,
    SlotSpec,
    SlotType,
    Unit,
    foundry_method,
)


def _result_slot() -> frozenset[SlotSpec]:
    return frozenset({SlotSpec("result", SlotType.SCALAR, Unit("result", "json"))})


@foundry_method(
    namespace="sensitivity.global",
    version="1.0.0",
    tags={"sensitivity", "global", "morris", "screening", "tabular"},
)
class MorrisSensitivityEstimator:
    """Screen influential inputs with Morris elementary-effects analysis."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="morris",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    "model_outputs",
                    SlotType.MATRIX,
                    Unit("response", "value"),
                    shape=("n_trajectories", "n_factors_plus_1"),
                ),
                SlotSpec(
                    "parameter_levels",
                    SlotType.MATRIX,
                    Unit("level", "value"),
                    shape=("n_trajectories", "n_factors_plus_1", "n_factors"),
                ),
            }
        ),
        output_slots=_result_slot(),
        parameters=(),
        fidelity=FidelityLevel.LOW,
        complexity=ComplexityClass.O_N,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Morris one-at-a-time (OAT) elementary effects screening method.",
        tags=frozenset({"sensitivity", "global", "morris", "screening", "tabular"}),
        citations=(
            "Morris, M.D. (1991). Factorial Sampling Plans for Preliminary Computational Experiments. Technometrics.",
        ),
        equations={"ee": "EE_i = (f(x + delta*e_i) - f(x)) / delta"},
        determinism_tier=DeterminismTier.STATISTICAL,
        required_deps=("numpy",),
        when_to_use="Screening step before Sobol; identify influential inputs in high-dimensional model cheaply",
        when_not_to_use="Already run Sobol; fewer than 10 inputs",
        output_interpretation="mu* (mean |EE|): high = influential input. sigma: high = nonlinear or interaction present. Rank inputs by mu*.",
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        del params
        outputs = np.asarray(state["model_outputs"], dtype=float)
        levels = np.asarray(state["parameter_levels"], dtype=float)

        n_traj = outputs.shape[0]
        n_steps = outputs.shape[1]
        n_factors = levels.shape[2] if levels.ndim == 3 else n_steps - 1

        # Compute elementary effects per trajectory
        ees = np.zeros((n_traj, n_factors))
        for t in range(n_traj):
            for s in range(min(n_steps - 1, n_factors)):
                delta_y = outputs[t, s + 1] - outputs[t, s]
                if levels.ndim == 3:
                    delta_x = levels[t, s + 1] - levels[t, s]
                    changed = np.where(np.abs(delta_x) > 1e-12)[0]
                    if len(changed) > 0:
                        factor_idx = changed[0]
                        ees[t, factor_idx] = delta_y / delta_x[factor_idx]

        mu_star = np.mean(np.abs(ees), axis=0)
        sigma = np.std(ees, axis=0, ddof=1) if n_traj > 1 else np.zeros(n_factors)

        return {
            "result": {
                "mu_star": mu_star.tolist(),
                "sigma": sigma.tolist(),
                "mu": np.mean(ees, axis=0).tolist(),
                "n_trajectories": n_traj,
                "n_factors": n_factors,
            }
        }


@foundry_method(
    namespace="sensitivity.global",
    version="1.0.0",
    tags={"sensitivity", "global", "fast", "tabular"},
)
class FASTEstimator:
    """Screen influential inputs with Fourier amplitude sensitivity testing."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="fast",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    "model_outputs",
                    SlotType.VECTOR,
                    Unit("response", "value"),
                    shape=("n_samples",),
                ),
            }
        ),
        output_slots=_result_slot(),
        parameters=(
            ParameterSpec(name="n_factors", default=3),
            ParameterSpec(name="harmonic_max", default=4),
        ),
        fidelity=FidelityLevel.MEDIUM,
        complexity=ComplexityClass.O_N,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Fourier Amplitude Sensitivity Test (FAST) for first-order sensitivity indices.",
        tags=frozenset({"sensitivity", "global", "fast", "fourier", "tabular"}),
        citations=(
            "Cukier, R.I. et al. (1973). Study of the sensitivity of coupled reaction systems.",
        ),
        equations={"fast": "S_i = sum_{p=1}^{M} (A_p^2 + B_p^2) / V(Y)"},
        determinism_tier=DeterminismTier.LIBRARY_DETERMINISTIC,
        required_deps=("numpy",),
        when_to_use="Efficient first-order sensitivity indices via Fourier decomposition; cheaper than Sobol for many factors",
        when_not_to_use="Need total-order indices (use Sobol); highly non-smooth model response",
        output_interpretation="First-order indices via spectral decomposition. Analogous to Sobol S1. Sum should be ≤ 1.",
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        outputs = np.asarray(state["model_outputs"], dtype=float)
        n_factors = int(params.get("n_factors", 3))
        m = int(params.get("harmonic_max", 4))

        n = len(outputs)
        variance = float(np.var(outputs, ddof=1))
        if variance <= 0:
            return {"result": {"first_order_indices": [0.0] * n_factors, "variance": 0.0}}

        # Compute Fourier coefficients
        fft_vals = np.fft.fft(outputs)
        power = np.abs(fft_vals) ** 2 / n

        # First-order indices via FAST frequency assignment
        indices = []
        for i in range(n_factors):
            omega = i + 1
            partial_var = 0.0
            for p in range(1, m + 1):
                freq_idx = p * omega
                if freq_idx < n // 2:
                    partial_var += float(power[freq_idx])
            indices.append(partial_var / (variance * n) * 2.0)

        # Clip to [0, 1]
        indices = [max(0.0, min(1.0, s)) for s in indices]

        return {
            "result": {
                "first_order_indices": indices,
                "variance": variance,
                "n_factors": n_factors,
            }
        }


@foundry_method(
    namespace="sensitivity.global",
    version="1.0.0",
    tags={"sensitivity", "global", "pawn", "distribution-based", "tabular"},
)
class PAWNEstimator:
    """Screen input influence with distribution-based PAWN sensitivity statistics."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="pawn",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    "inputs_matrix",
                    SlotType.MATRIX,
                    Unit("parameter", "value"),
                    shape=("n_samples", "n_factors"),
                ),
                SlotSpec(
                    "outputs", SlotType.VECTOR, Unit("response", "value"), shape=("n_samples",)
                ),
            }
        ),
        output_slots=_result_slot(),
        parameters=(ParameterSpec(name="n_bins", default=10),),
        fidelity=FidelityLevel.MEDIUM,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="PAWN distribution-based sensitivity index using KS statistic.",
        tags=frozenset({"sensitivity", "global", "pawn", "distribution-based", "ks", "tabular"}),
        citations=(
            "Pianosi, F. & Wagener, T. (2015). A simple and efficient method for global sensitivity analysis. Environmental Modelling & Software.",
        ),
        equations={"pawn": "T_i = max_v KS(F(Y), F(Y|X_i=v))"},
        determinism_tier=DeterminismTier.LIBRARY_DETERMINISTIC,
        required_deps=("numpy",),
        when_to_use="Distribution-based sensitivity when output variance is not an adequate summary (e.g., skewed, bounded outputs)",
        when_not_to_use="Normal symmetric output where variance-based Sobol is sufficient",
        output_interpretation="PAWN index in [0,1]: high value = fixing this input greatly changes output distribution. Rank inputs by PAWN index.",
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        inputs = np.asarray(state["inputs_matrix"], dtype=float)
        outputs = np.asarray(state["outputs"], dtype=float)
        n_bins = int(params.get("n_bins", 10))

        if inputs.ndim != 2 or outputs.ndim != 1:
            raise ValueError("inputs_matrix must be 2D and outputs must be 1D")
        n_samples, n_factors = inputs.shape

        # Unconditional CDF of Y
        sorted_y = np.sort(outputs)

        pawn_indices = []
        for i in range(n_factors):
            x_col = inputs[:, i]
            bin_edges = np.linspace(np.min(x_col), np.max(x_col), n_bins + 1)
            ks_stats = []
            for b in range(n_bins):
                mask = (x_col >= bin_edges[b]) & (x_col < bin_edges[b + 1])
                if b == n_bins - 1:
                    mask = (x_col >= bin_edges[b]) & (x_col <= bin_edges[b + 1])
                if np.sum(mask) < 2:
                    continue
                conditional_y = np.sort(outputs[mask])
                # KS statistic: max |F_unconditional - F_conditional|
                all_vals = np.unique(np.concatenate([sorted_y, conditional_y]))
                uncond_cdf = np.searchsorted(sorted_y, all_vals, side="right") / n_samples
                cond_cdf = np.searchsorted(conditional_y, all_vals, side="right") / len(
                    conditional_y
                )
                ks = float(np.max(np.abs(uncond_cdf - cond_cdf)))
                ks_stats.append(ks)
            pawn_indices.append(float(np.median(ks_stats)) if ks_stats else 0.0)

        return {
            "result": {
                "pawn_indices": pawn_indices,
                "n_factors": n_factors,
                "n_bins": n_bins,
            }
        }


__all__ = [
    "FASTEstimator",
    "MorrisSensitivityEstimator",
    "PAWNEstimator",
]
