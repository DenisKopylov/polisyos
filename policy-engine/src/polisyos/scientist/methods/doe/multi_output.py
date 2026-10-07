"""Multi-output sensitivity analysis via PCA dimensionality reduction."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .designs import SensitivityPlan, SensitivityResult, _admit_sensitivity_plan


@dataclass
class MultiOutputSensitivityResult:
    """Result of multi-output sensitivity analysis.

    Contains per-principal-component results plus an aggregate ranking
    weighted by explained variance.
    """

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
    ) -> None:
        self._max_components = max_components
        self._min_variance = min_variance_explained

    def analyze(
        self,
        plan: SensitivityPlan,
        samples: np.ndarray,
        outputs: np.ndarray,
    ) -> MultiOutputSensitivityResult:
        """Run multi-output sensitivity analysis.

        Parameters
        ----------
        plan:
            Sensitivity plan (method, parameter_specs, etc.).
        samples:
            Sample array ``(n_samples, n_params)``.
        outputs:
            Output array ``(n_samples, n_outputs)``.  If 1-D, treated as
            single-output fallback.
        """
        plan = _admit_sensitivity_plan(plan)
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
        components, variance_ratio = self._run_pca(active_outputs)

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
            }
        )

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
        """Run PCA and return (list of score arrays, variance ratios)."""
        n_outputs = outputs.shape[1]
        rank_cap = max(min(outputs.shape[0] - 1, n_outputs), 0)
        requested_components = self._max_components or n_outputs
        n_components = min(requested_components, n_outputs, rank_cap)
        if n_components < 1:
            raise ValueError("Too few valid samples for PCA")

        try:
            from sklearn.decomposition import PCA  # type: ignore[import-untyped]

            pca = PCA(n_components=n_components)
            scores = pca.fit_transform(outputs)
            var_ratio = pca.explained_variance_ratio_.tolist()
        except ImportError:
            # Manual SVD fallback
            centered = outputs - outputs.mean(axis=0)
            U, S, Vt = np.linalg.svd(centered, full_matrices=False)
            total_var = np.sum(S**2)
            var_ratio = (
                (S**2 / total_var).tolist() if total_var > 0 else [1.0 / n_outputs] * n_outputs
            )
            scores = U * S
            n_components = min(n_components, scores.shape[1])

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

        return selected, selected_var

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


__all__ = [
    "MultiOutputAnalyzer",
    "MultiOutputSensitivityResult",
]
