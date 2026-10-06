"""Bridge from autotune search space to DOE sensitivity analysis."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, Literal, cast

if TYPE_CHECKING:
    from polisyos.core.artifacts import ArtifactRef, ArtifactStore
    from polisyos.scientist.methods.doe.designs import SensitivityPlan, SensitivityResult

logger = logging.getLogger(__name__)


def _try_import_doe():
    """Lazy import of DOE analysis module."""
    try:
        import numpy as np

        from polisyos.scientist.methods.doe.analysis import analyze_sensitivity
        from polisyos.scientist.methods.doe.designs import (
            ParameterSpec,
            SensitivityMethod,
            SensitivityPlan,
        )
        from polisyos.scientist.methods.doe.sampling import generate_sensitivity_samples

        return (
            analyze_sensitivity,
            ParameterSpec,
            SensitivityMethod,
            SensitivityPlan,
            generate_sensitivity_samples,
            np,
        )
    except ImportError:
        return None


class SensitivityBridge:
    """Bridges autotune search space bounds to DOE sensitivity analysis.

    Converts search-space parameter bounds into ``ParameterSpec`` objects
    and calls ``analyze_sensitivity`` to rank parameter importance.
    """

    def analyze_search_space(
        self,
        bounds: list[dict[str, Any]],
        evaluator: Callable[[dict[str, float]], float],
        *,
        method: str = "morris",
        n_trajectories: int = 10,
        n_levels: int = 4,
        seed: int | None = None,
        input_law: Literal["unknown", "independent", "dependent"] = "unknown",
        store: ArtifactStore | None = None,
        max_estimated_runs: int = 1000,
    ) -> dict[str, Any]:
        """Run sensitivity analysis over a search space.

        Parameters
        ----------
        bounds:
            List of dicts with keys: name, lower, upper.
        evaluator:
            Callable(params_dict) -> float.
        method:
            "morris" or "sobol".
        n_trajectories:
            Number of trajectories / sample sets.
        n_levels:
            Grid levels for Morris method.

        Returns
        -------
        Dict with keys: ranking (list[str]), result (SensitivityResult), method.
        """
        deps = _try_import_doe()
        if deps is None:
            raise ImportError("DOE analysis module not available")

        (
            analyze_sensitivity,
            ParameterSpec,
            SensitivityMethod,
            SensitivityPlan,
            generate_sensitivity_samples,
            np,
        ) = deps

        sa_method = SensitivityMethod(method)

        if not bounds:
            return {"ranking": [], "result": None, "method": method}

        param_specs = [
            ParameterSpec(
                name=b["name"],
                lower_bound=b.get("lower", 0.0),
                upper_bound=b.get("upper", 1.0),
                num_levels=n_levels,
                distribution=b.get("distribution", "uniform"),
                distribution_spec=b.get("distribution_spec"),
                unit=b.get("unit", "unspecified"),
            )
            for b in bounds
        ]

        plan = SensitivityPlan(
            method=sa_method,
            parameter_specs=param_specs,
            n_trajectories=n_trajectories,
            seed=seed,
            input_law=input_law,
            max_estimated_runs=max_estimated_runs,
        )
        if store is not None and seed is None:
            raise ValueError("Persisted DOE analysis requires an explicit replay seed")
        samples = generate_sensitivity_samples(plan)

        # Evaluate
        outputs = np.array(
            [
                evaluator({p.name: samples[i, j] for j, p in enumerate(param_specs)})
                for i in range(samples.shape[0])
            ]
        )

        result = analyze_sensitivity(plan, samples, outputs)

        # DOE now exposes normalized method-specific maps plus a canonical ranking.
        if result.ranking:
            ranking = list(result.ranking)
        else:
            scores = result.mu_star or result.st or result.s1
            ranking = sorted(
                result.parameter_names,
                key=lambda name: abs(float(scores.get(name, 0.0))),
                reverse=True,
            )

        answer = {"ranking": ranking, "result": result, "method": method}
        if store is not None:
            from polisyos.core.artifacts.manifest_profile import artifact_manifest_profile_sha256
            from polisyos.scientist.methods.doe._receipt import _persist_analysis

            ref = _persist_analysis(store, plan, samples, outputs, result)
            snapshot = store.get_verified_snapshot(ref)
            answer["analysis_ref"] = ref.model_copy(
                update={
                    "manifest_profile_sha256": artifact_manifest_profile_sha256(snapshot.manifest)
                }
            )
        return answer


class _AnalysisSnapshotReader:
    """Supply the existing E reader one canonical immutable CAS byte/manifest pair."""

    def __init__(self, ref: ArtifactRef, snapshot: Any):
        self._ref = ref
        self._snapshot = snapshot

    def _check(self, ref: ArtifactRef) -> None:
        if ref != self._ref:
            raise ValueError("Sensitivity reader cannot substitute an artifact reference")

    def get_manifest(self, ref: ArtifactRef) -> Any:
        self._check(ref)
        return self._snapshot.manifest

    def get_bytes(self, ref: ArtifactRef) -> bytes:
        self._check(ref)
        return self._snapshot.data

    def verify(self, ref: ArtifactRef) -> Any:
        self._check(ref)
        return self._snapshot.verification_report(ref.artifact_id)


def read_search_analysis(
    store: ArtifactStore, ref: ArtifactRef, *, require_selected_profile: bool = True
) -> tuple[SensitivityResult, SensitivityPlan]:
    """Recompute the E analysis from one full-reference B verified snapshot.

    The returned units and distribution are the actual persisted experimental
    declarations. Neither the reader nor this exploratory port authorizes their
    institutional truth or a population-independence claim.
    """
    from polisyos.core.artifacts import ArtifactRef
    from polisyos.core.canon import from_canonical_bytes
    from polisyos.scientist.methods.doe._receipt import _AnalysisReceipt, _load_analysis

    ref = ArtifactRef.model_validate(ref)
    if require_selected_profile and ref.manifest_profile_sha256 is None:
        raise ValueError("Sensitivity consumption requires the full selected manifest reference")
    snapshot = store.get_verified_snapshot(ref)
    reader = _AnalysisSnapshotReader(ref, snapshot)
    result = _load_analysis(cast("ArtifactStore", reader), ref)
    receipt = _AnalysisReceipt.model_validate(from_canonical_bytes(snapshot.data))
    return result, receipt.plan
