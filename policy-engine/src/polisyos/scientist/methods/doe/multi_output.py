"""Multi-output sensitivity analysis via PCA dimensionality reduction."""

from __future__ import annotations

from dataclasses import dataclass, field
from importlib.metadata import version
from typing import ClassVar, Literal

import numpy as np
from pydantic import ConfigDict

from .designs import (
    SensitivityPlan,
    SensitivityResult,
    _admit_sensitivity_analysis_plan,
    _derive_plan_seed,
    _request_rng_streams,
)


@dataclass
class MultiOutputSensitivityResult:
    """Result of multi-output sensitivity analysis.

    Contains per-principal-component results plus an aggregate ranking
    weighted by explained variance.
    """

    __pydantic_config__: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    per_component: list[SensitivityResult] = field(default_factory=list)
    explained_variance_ratio: list[float] = field(default_factory=list)
    aggregate_ranking: list[str] = field(default_factory=list)
    n_components_used: int = 0
    total_variance_explained: float = 0.0
    pca_variance_threshold: float = 0.95
    pca_variance_threshold_status: str = "met"
    metadata: dict[str, object] = field(default_factory=dict)


class MultiOutputAnalyzer:
    """Analyze multi-output sensitivity using PCA reduction.

    For each retained principal component, runs Sobol/Morris analysis,
    then combines the results weighted by explained variance to produce
    an aggregate parameter ranking.
    """

    def __init__(
        self,
        *,
        max_components: int | None = None,
        min_variance_explained: float = 0.95,
        svd_solver: Literal["auto", "full", "randomized"] = "auto",
        n_oversamples: int = 10,
        iterated_power: int = 7,
        power_iteration_normalizer: Literal["QR", "LU", "none", "auto"] = "QR",
        backend: Literal["auto", "sklearn", "numpy"] = "auto",
    ) -> None:
        """Configure bounded covariance PCA without selecting scientific metric units.

        Args:
            max_components: Optional positive cap, further bounded by centered rank.
            min_variance_explained: Requested retained variance fraction in ``(0, 1]``.
            svd_solver: Requested sklearn solver; actual resolution is recorded after fit.
            n_oversamples: Randomized solver oversampling width.
            iterated_power: Randomized solver power-iteration count.
            power_iteration_normalizer: Numerical normalization within those iterations.
            backend: Automatic import fallback or an explicitly recorded replay backend.

        Raises:
            ValueError: A cap, threshold or backend option is unsupported.
        """
        if max_components is not None and (type(max_components) is not int or max_components < 1):
            raise ValueError("max_components must be a positive integer")
        if not 0.0 < min_variance_explained <= 1.0:
            raise ValueError("min_variance_explained must be in (0, 1]")
        if svd_solver not in {"auto", "full", "randomized"}:
            raise ValueError("Unsupported PCA solver")
        if type(n_oversamples) is not int or n_oversamples < 1:
            raise ValueError("n_oversamples must be a positive integer")
        if type(iterated_power) is not int or iterated_power < 0:
            raise ValueError("iterated_power must be a nonnegative integer")
        if power_iteration_normalizer not in {"QR", "LU", "none", "auto"}:
            raise ValueError("Unsupported PCA power iteration normalizer")
        if backend not in {"auto", "sklearn", "numpy"}:
            raise ValueError("Unsupported PCA backend")
        self._max_components = max_components
        self._min_variance = min_variance_explained
        self._svd_solver = svd_solver
        self._n_oversamples = n_oversamples
        self._iterated_power = iterated_power
        self._power_iteration_normalizer = power_iteration_normalizer
        self._backend = backend

    def analyze(
        self,
        plan: SensitivityPlan,
        samples: np.ndarray,
        outputs: np.ndarray,
    ) -> MultiOutputSensitivityResult:
        """Prepare original runs, fit local-profile PCA and analyze its actual scores.

        Args:
            plan: Admitted method, parameter, failure-policy and request-stream contract.
            samples: Ordered sample array ``(n_samples, n_params)``.
            outputs: Paired output array ``(n_samples, n_outputs)`` or scalar fallback.

        Returns:
            Component results, variance-weighted ordinal ranking and explicit source,
            preprocessing and failure limitations; no empirical sensitivity authority.

        Raises:
            ValueError: Input dimensions, original support, geometry or PCA rank are invalid.
            ImportError: An explicitly selected backend is unavailable.
        """
        plan = _admit_sensitivity_analysis_plan(plan)
        from .analysis import _prepare_analysis_inputs, analyze_sensitivity

        if outputs.ndim == 1:
            single = analyze_sensitivity(plan, samples, outputs)
            return MultiOutputSensitivityResult(
                per_component=[single],
                explained_variance_ratio=[1.0],
                aggregate_ranking=list(single.ranking),
                n_components_used=1,
                total_variance_explained=1.0,
                pca_variance_threshold=self._min_variance,
                pca_variance_threshold_status="not_applicable",
                metadata=dict(single.metadata),
            )

        if outputs.ndim != 2:
            raise ValueError("outputs must be 1-D or 2-D")

        if samples.ndim != 2 or samples.shape[0] != outputs.shape[0]:
            raise ValueError("samples and outputs must have the same row count")

        # Apply the plan's failure policy to the original run matrix before
        # PCA.  In particular, complete-case filtering must not erase the
        # denominator or make FAIL_FAST/min_success_rate unreachable.
        prepared = _prepare_analysis_inputs(
            plan,
            np.asarray(samples, dtype=float),
            np.asarray(outputs, dtype=float),
        )
        clean_samples = prepared.samples
        clean_outputs = prepared.outputs

        if clean_outputs.shape[0] < 3:
            raise ValueError("Too few valid samples for multi-output analysis")

        # Check for zero-variance columns
        variances = np.var(clean_outputs, axis=0)
        nonzero_cols = variances > 0
        if not np.any(nonzero_cols):
            raise ValueError("All output columns have zero variance")

        active_outputs = clean_outputs[:, nonzero_cols]

        # PCA via sklearn (lazy import) or manual SVD fallback
        components, variance_ratio, pca_profile = self._fit_pca(
            active_outputs,
            random_seed=_derive_plan_seed(plan, "preprocess:pca:doe-pca-v1"),
        )
        pca_profile["active_output_columns"] = np.flatnonzero(nonzero_cols).astype(int).tolist()

        # Analyze each component
        per_component: list[SensitivityResult] = []
        total_variance_explained = float(sum(variance_ratio))
        variance_threshold_met = total_variance_explained + 1e-12 >= self._min_variance
        variance_threshold_status = "met" if variance_threshold_met else "unmet_limited"
        for i, pc_scores in enumerate(components):
            result = analyze_sensitivity(
                plan,
                clean_samples,
                pc_scores,
                preparation_context=prepared,
            )
            # The component is derived from the policy-prepared matrix, so
            # restore the original run accounting rather than reporting the
            # imputed/PCA representation as a fresh all-successful experiment.
            result.total_runs = int(outputs.shape[0])
            result.successful_runs = prepared.successful_runs
            result.failed_runs = prepared.failed_runs
            result.metadata.update(prepared.metadata)
            result.metadata.update(
                {
                    "pca_sample_count": int(clean_outputs.shape[0]),
                    "pca_output_count": int(active_outputs.shape[1]),
                    "pca_rank_cap": max(
                        min(clean_outputs.shape[0] - 1, active_outputs.shape[1]),
                        0,
                    ),
                    "pca_scientific_sufficiency": "not_established",
                    "pca_variance_explained": total_variance_explained,
                    "pca_variance_threshold": self._min_variance,
                    "pca_variance_threshold_status": variance_threshold_status,
                    "pca_profile": pca_profile,
                }
            )
            per_component.append(result)

        # Aggregate ranking weighted by explained variance
        aggregate = self._aggregate_rankings(per_component, variance_ratio, plan)
        metadata = dict(prepared.metadata)
        metadata.update(
            {
                "pca_sample_count": int(clean_outputs.shape[0]),
                "pca_output_count": int(active_outputs.shape[1]),
                "pca_rank_cap": max(
                    min(clean_outputs.shape[0] - 1, active_outputs.shape[1]),
                    0,
                ),
                "pca_scientific_sufficiency": "not_established",
                "pca_variance_explained": total_variance_explained,
                "pca_variance_threshold": self._min_variance,
                "pca_variance_threshold_status": variance_threshold_status,
                "pca_profile": pca_profile,
                "rng_streams": _request_rng_streams(plan),
                "reproducibility_status": (
                    "seeded_local_profile"
                    if plan.seed is not None
                    else "limited_unseeded_exploratory"
                ),
                "evaluator_randomness_status": "not_established",
                "pca_metric_convention": "raw_supplied_output_units_covariance",
                "aggregate_ranking_convention": "explained_variance_weighted_ordinal_ranks",
                "cross_metric_comparability": "not_established",
            }
        )
        metadata.update(_multi_output_identity(plan, samples, outputs, pca_profile))

        return MultiOutputSensitivityResult(
            per_component=per_component,
            explained_variance_ratio=variance_ratio,
            aggregate_ranking=aggregate,
            n_components_used=len(components),
            total_variance_explained=total_variance_explained,
            pca_variance_threshold=self._min_variance,
            pca_variance_threshold_status=variance_threshold_status,
            metadata=metadata,
        )

    def _run_pca(
        self,
        outputs: np.ndarray,
    ) -> tuple[list[np.ndarray], list[float]]:
        """Run legacy in-memory PCA without claiming a seeded request profile."""
        components, ratios, _ = self._fit_pca(outputs)
        return components, ratios

    def _fit_pca(
        self,
        outputs: np.ndarray,
        *,
        random_seed: int | None = None,
    ) -> tuple[list[np.ndarray], list[float], dict[str, object]]:
        """Fit the actual backend and return scores with its resolved local profile."""
        outputs = np.asarray(outputs, dtype=float)
        if outputs.ndim != 2 or not np.all(np.isfinite(outputs)):
            raise ValueError("PCA requires a finite two-dimensional matrix")
        if not np.any(np.var(outputs, axis=0) > 0):
            raise ValueError("All output columns have zero variance")
        n_outputs = outputs.shape[1]
        rank_cap = max(min(outputs.shape[0] - 1, n_outputs), 0)
        requested_components = self._max_components or n_outputs
        n_components = min(requested_components, n_outputs, rank_cap)
        if n_components < 1:
            raise ValueError("Too few valid samples for PCA")

        try:
            if self._backend == "numpy":
                raise ImportError("Explicit recorded NumPy PCA profile")
            from sklearn.decomposition import PCA  # type: ignore[import-untyped]

            pca = PCA(
                n_components=n_components,
                svd_solver=self._svd_solver,
                random_state=random_seed,
                n_oversamples=self._n_oversamples,
                iterated_power=self._iterated_power,
                power_iteration_normalizer=self._power_iteration_normalizer,
            )
            scores = pca.fit_transform(outputs)
            var_ratio = pca.explained_variance_ratio_.tolist()
            backend = "sklearn"
            backend_version = version("scikit-learn")
            resolved_solver = pca._fit_svd_solver
        except ImportError:
            if self._backend == "sklearn":
                raise
            # Manual SVD fallback
            centered = outputs - outputs.mean(axis=0)
            U, S, Vt = np.linalg.svd(centered, full_matrices=False)
            total_var = np.sum(S**2)
            var_ratio = (
                (S**2 / total_var).tolist() if total_var > 0 else [1.0 / n_outputs] * n_outputs
            )
            scores = U * S
            n_components = min(n_components, scores.shape[1])
            backend = "numpy"
            backend_version = np.__version__
            resolved_solver = "full"

        # Select components up to min_variance_explained
        cumulative = 0.0
        selected: list[np.ndarray] = []
        selected_var: list[float] = []
        for i in range(min(n_components, len(var_ratio))):
            selected.append(scores[:, i])
            selected_var.append(var_ratio[i])
            cumulative += var_ratio[i]
            if cumulative >= self._min_variance:
                break

        profile = {
            "profile_version": "doe-pca-v1",
            "backend": backend,
            "backend_version": backend_version,
            "requested_solver": self._svd_solver,
            "resolved_solver": resolved_solver,
            "random_seed": random_seed,
            "n_components_requested": self._max_components,
            "n_components_cap": n_components,
            "min_variance_explained": self._min_variance,
            "centering": "column_mean",
            "n_oversamples": self._n_oversamples,
            "iterated_power": self._iterated_power,
            "power_iteration_normalizer": self._power_iteration_normalizer,
        }
        return selected, selected_var, profile

    def _aggregate_rankings(
        self,
        results: list[SensitivityResult],
        weights: list[float],
        plan: SensitivityPlan,
    ) -> list[str]:
        """Compute variance-weighted aggregate ranking."""
        names = [p.name for p in plan.parameter_specs]
        scores: dict[str, float] = dict.fromkeys(names, 0.0)

        for result, weight in zip(results, weights):
            for rank_pos, name in enumerate(result.ranking):
                # Higher rank (lower position) → higher score
                rank_score = len(names) - rank_pos
                scores[name] += weight * rank_score

        return sorted(names, key=lambda n: scores.get(n, 0.0), reverse=True)


def _multi_output_identity(
    plan: SensitivityPlan,
    samples: np.ndarray,
    outputs: np.ndarray,
    profile: dict[str, object],
) -> dict[str, object]:
    """Bind the complete ordered raw experiment and actual preprocessing profile."""
    import hashlib

    from polisyos.core.canon import CanonSpec, to_canonical_bytes

    from .analysis import _array_digest, _backend_identity

    sample_digest = _array_digest(samples)
    output_digest = _array_digest(outputs)
    backend = _backend_identity(plan)
    design_id = hashlib.sha256(
        to_canonical_bytes(
            {"plan": plan.model_dump(mode="python"), "ordered_samples_sha256": sample_digest},
            CanonSpec(forbid_floats=False, exclude_none=False),
        )
    ).hexdigest()
    analysis_id = hashlib.sha256(
        to_canonical_bytes(
            {
                "design_id": design_id,
                "outputs_sha256": output_digest,
                "backend": backend,
                "pca_profile": profile,
            },
            CanonSpec(forbid_floats=False, exclude_none=False),
        )
    ).hexdigest()
    return {
        "design_id": design_id,
        "analysis_id": analysis_id,
        "ordered_samples_sha256": sample_digest,
        "ordered_outputs_sha256": output_digest,
        "ordered_parameter_names": [p.name for p in plan.parameter_specs],
        "parameter_units": {p.name: p.unit for p in plan.parameter_specs},
        "backend_identity": backend,
        "authority_purpose": "exploratory_parameter_experiment",
        "population_law_status": "not_established",
    }


__all__ = [
    "MultiOutputAnalyzer",
    "MultiOutputSensitivityResult",
]
