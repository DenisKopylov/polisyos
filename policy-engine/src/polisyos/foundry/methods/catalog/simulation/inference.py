"""Estimate simulation-output uncertainty with Monte Carlo, bootstrap, and permutation procedures."""

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
    namespace="simulation.inference",
    version="1.0.0",
    tags={"simulation", "inference", "monte-carlo", "structural"},
)
class MonteCarloEstimator:
    """Estimate output means/intervals by repeated stochastic simulation; avoid tiny replicate counts when tail risk matters."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="monte_carlo",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    "samples",
                    SlotType.MATRIX,
                    Unit("value", "amount"),
                    shape=("n_simulations", "n_outputs"),
                ),
            }
        ),
        output_slots=_result_slot(),
        parameters=(ParameterSpec(name="confidence_level", default=0.95, bounds=(0.5, 0.999)),),
        fidelity=FidelityLevel.MEDIUM,
        complexity=ComplexityClass.O_N,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Monte Carlo simulation summary: means, CIs, and convergence diagnostics.",
        tags=frozenset({"simulation", "inference", "monte-carlo", "structural"}),
        determinism_tier=DeterminismTier.STATISTICAL,
        required_deps=("numpy",),
        when_to_use="Parameter estimation for intractable likelihood models; calibrate simulation model to data",
        when_not_to_use="Likelihood is tractable; too slow model for required ABC tolerance",
        output_interpretation="Posterior distribution over simulation parameters. ABC posterior: parameters that reproduce observed statistics within tolerance.",
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        samples = np.asarray(state["samples"], dtype=float)
        if samples.ndim == 1:
            samples = samples[:, np.newaxis]
        if samples.ndim != 2:
            raise ValueError("samples must be 1D or 2D")

        conf = float(params.get("confidence_level", 0.95))
        alpha = (1.0 - conf) / 2.0
        lower_pct = alpha * 100
        upper_pct = (1.0 - alpha) * 100

        n_sim, n_out = samples.shape
        means = np.mean(samples, axis=0)
        stds = np.std(samples, axis=0, ddof=1) if n_sim > 1 else np.zeros(n_out)
        ci_lower = np.percentile(samples, lower_pct, axis=0)
        ci_upper = np.percentile(samples, upper_pct, axis=0)

        # Convergence: relative SE of mean
        se = stds / np.sqrt(max(n_sim, 1))
        rel_se = se / np.maximum(np.abs(means), 1e-12)

        return {
            "result": {
                "means": means.tolist(),
                "std_devs": stds.tolist(),
                "ci_lower": ci_lower.tolist(),
                "ci_upper": ci_upper.tolist(),
                "relative_se": rel_se.tolist(),
                "n_simulations": n_sim,
                "confidence_level": conf,
            }
        }


@foundry_method(
    namespace="simulation.inference",
    version="1.0.0",
    tags={"simulation", "inference", "bootstrap", "structural"},
)
class BootstrapInferenceEstimator:
    """Estimate sampling uncertainty with bootstrap resampling; avoid strongly dependent samples unless resampling respects dependence."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)
    _MAX_VECTOR_BATCH: ClassVar[int] = 512

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="bootstrap",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("data", SlotType.VECTOR, Unit("value", "amount"), shape=("n_obs",)),
            }
        ),
        output_slots=_result_slot(),
        parameters=(
            ParameterSpec(name="n_bootstrap", default=1000),
            ParameterSpec(name="confidence_level", default=0.95, bounds=(0.5, 0.999)),
            ParameterSpec(name="seed", default=42),
        ),
        fidelity=FidelityLevel.MEDIUM,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Nonparametric bootstrap inference for the sample mean.",
        tags=frozenset({"simulation", "inference", "bootstrap", "nonparametric", "structural"}),
        citations=(
            "Efron, B. (1979). Bootstrap Methods: Another Look at the Jackknife. Ann. Statist.",
        ),
        determinism_tier=DeterminismTier.STATISTICAL,
        required_deps=("numpy",),
        when_to_use="Bias-corrected model performance estimate; small samples where CV is noisy",
        typical_min_obs=30,
        output_interpretation="Bootstrap CI for sample mean. Bias = bootstrap mean - observed mean. Stable CI = sufficient bootstrap draws.",
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        data = np.asarray(state["data"], dtype=float)
        if data.ndim != 1 or data.size == 0:
            raise ValueError("data must be a non-empty 1D vector")

        n_boot = int(params.get("n_bootstrap", 1000))
        conf = float(params.get("confidence_level", 0.95))
        seed = int(params.get("seed", 42))

        rng = np.random.default_rng(seed)
        n = len(data)
        boot_means = np.empty(n_boot, dtype=float)
        batch_size = min(max(1, n_boot), BootstrapInferenceEstimator._MAX_VECTOR_BATCH)
        offset = 0
        while offset < n_boot:
            upper = min(offset + batch_size, n_boot)
            sample_index = rng.integers(0, n, size=(upper - offset, n))
            boot_means[offset:upper] = data[sample_index].mean(axis=1)
            offset = upper

        alpha = (1.0 - conf) / 2.0
        ci_lower = float(np.percentile(boot_means, alpha * 100))
        ci_upper = float(np.percentile(boot_means, (1.0 - alpha) * 100))

        return {
            "result": {
                "point_estimate": float(np.mean(data)),
                "bootstrap_mean": float(np.mean(boot_means)),
                "bootstrap_se": float(np.std(boot_means, ddof=1)),
                "ci_lower": ci_lower,
                "ci_upper": ci_upper,
                "bias": float(np.mean(boot_means) - np.mean(data)),
                "n_bootstrap": n_boot,
                "confidence_level": conf,
            }
        }


@foundry_method(
    namespace="simulation.inference",
    version="1.0.0",
    tags={"simulation", "inference", "permutation", "randomization", "structural"},
)
class PermutationTestEstimator:
    """Estimate a null p-value by label permutation under exchangeability; avoid blocked/time-dependent data without constrained permutations."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)
    _MAX_VECTOR_BATCH: ClassVar[int] = 256

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="permutation_test",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("group_a", SlotType.VECTOR, Unit("value", "amount"), shape=("n_a",)),
                SlotSpec("group_b", SlotType.VECTOR, Unit("value", "amount"), shape=("n_b",)),
            }
        ),
        output_slots=_result_slot(),
        parameters=(
            ParameterSpec(name="n_permutations", default=5000),
            ParameterSpec(name="seed", default=42),
        ),
        fidelity=FidelityLevel.MEDIUM,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Two-sample permutation test for difference in means (Fisher exact).",
        tags=frozenset(
            {"simulation", "inference", "permutation", "randomization", "fisher", "structural"}
        ),
        citations=("Fisher, R.A. (1935). The Design of Experiments.",),
        determinism_tier=DeterminismTier.STATISTICAL,
        required_deps=("numpy",),
        when_to_use="Exact hypothesis test for difference in means without distributional assumptions; small samples or non-normal data",
        output_interpretation="p-value: fraction of permuted differences as extreme as observed. p < 0.05 rejects H0 of no group difference.",
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        a = np.asarray(state["group_a"], dtype=float)
        b = np.asarray(state["group_b"], dtype=float)
        if a.ndim != 1 or b.ndim != 1:
            raise ValueError("group_a and group_b must be 1D")

        n_perm = int(params.get("n_permutations", 5000))
        seed = int(params.get("seed", 42))
        rng = np.random.default_rng(seed)

        observed_diff = float(np.mean(a) - np.mean(b))
        combined = np.concatenate([a, b])
        n_a = len(a)

        count_extreme = 0
        batch_size = min(max(1, n_perm), PermutationTestEstimator._MAX_VECTOR_BATCH)
        offset = 0
        while offset < n_perm:
            upper = min(offset + batch_size, n_perm)
            permuted = np.tile(combined, (upper - offset, 1))
            permuted = rng.permuted(permuted, axis=1)
            perm_diffs = permuted[:, :n_a].mean(axis=1) - permuted[:, n_a:].mean(axis=1)
            count_extreme += int(np.count_nonzero(np.abs(perm_diffs) >= abs(observed_diff)))
            offset = upper

        p_value = (count_extreme + 1) / (n_perm + 1)

        return {
            "result": {
                "observed_difference": observed_diff,
                "p_value": float(p_value),
                "n_permutations": n_perm,
                "n_extreme": count_extreme,
                "n_a": len(a),
                "n_b": len(b),
            }
        }


__all__ = [
    "BootstrapInferenceEstimator",
    "MonteCarloEstimator",
    "PermutationTestEstimator",
]
