"""Public doe analysis module API."""

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from dataclasses import dataclass
from importlib.metadata import version

import numpy as np

from .designs import (
    _DOE_DISTRIBUTION_SCHEMA_VERSION,
    _SALIB_BACKEND_ID,
    RunFailurePolicy,
    SensitivityMethod,
    SensitivityPlan,
    SensitivityResult,
    _admit_sensitivity_plan,
    _build_salib_problem,
    _derive_backend_seed,
)
from .morris_geometry import _validate_morris_plan_samples
from .sampling import _admit_sobol_input_law, generate_sensitivity_samples
from .uncertainty import (
    analyze_morris_trajectory_bootstrap,
    analyze_sobol_asymptotic_delta,
    analyze_sobol_paired_bootstrap,
    morris_elementary_effects_from_samples,
    sobol_blocks_from_salib_outputs,
)


def analyze_sensitivity(
    plan: SensitivityPlan,
    samples: np.ndarray,
    outputs: np.ndarray,
    *,
    preparation_context: _PreparedAnalysisInputs | None = None,
) -> SensitivityResult:
    """Summarize sampled runs into Morris, Sobol, or FAST sensitivity statistics."""
    plan = _admit_sensitivity_plan(plan)
    _admit_sobol_input_law(plan)
    if outputs.ndim != 1:
        raise ValueError("outputs must be a 1D array")
    if samples.ndim != 2:
        raise ValueError("samples must be a 2D array")
    if samples.shape[0] != outputs.shape[0]:
        raise ValueError("samples and outputs must have the same row count")

    raw_outputs = np.asarray(outputs, dtype=float)
    prepared = _prepare_analysis_inputs(
        plan,
        np.asarray(samples, dtype=float),
        raw_outputs,
    )
    accounting = preparation_context or prepared

    result = SensitivityResult(
        method=plan.method,
        parameter_names=[item.name for item in plan.parameter_specs],
        total_runs=int(accounting.metadata.get("original_total_runs", len(outputs))),
        successful_runs=accounting.successful_runs,
        failed_runs=accounting.failed_runs,
        metadata={
            "run_failure_policy": plan.run_failure_policy.value,
            "estimated_runs": plan.estimated_runs,
            "n_trajectories": plan.n_trajectories,
            "uncertainty_status": (
                "pending" if plan.uncertainty.enabled else "point_only_incomplete"
            ),
        },
    )
    result.metadata.update(prepared.metadata)
    if preparation_context is not None:
        # A derived PCA component is finite even when its source run was
        # rejected.  Carry the source preparation context before any
        # uncertainty producer decides whether it is eligible.
        result.metadata.update(preparation_context.metadata)

    problem, distribution_fingerprint = _build_salib_problem(plan)
    result.metadata.update(
        {
            "distribution_schema_version": _DOE_DISTRIBUTION_SCHEMA_VERSION,
            "distribution_mapping_fingerprint": distribution_fingerprint,
            "salib_backend": _SALIB_BACKEND_ID,
            "plan_seed": plan.seed,
        }
    )
    result.metadata.update(_analysis_identity(plan, samples, raw_outputs))
    names = result.parameter_names
    backend_seed = _derive_backend_seed(plan.seed, f"analysis:{plan.method.value}")

    if plan.method == SensitivityMethod.MORRIS:
        _validate_morris_plan_samples(plan, prepared.samples, problem)
        from SALib.analyze import morris as morris_analyzer  # type: ignore[import-not-found]

        salib_result = morris_analyzer.analyze(
            problem,
            prepared.samples,
            prepared.outputs,
            conf_level=plan.confidence_level,
            num_levels=plan.parameter_specs[0].num_levels,
            seed=backend_seed,
        )
        for idx, name in enumerate(names):
            result.mu_star[name] = float(salib_result["mu_star"][idx])
            result.sigma[name] = float(salib_result["sigma"][idx])
            conf = salib_result.get("mu_star_conf")
            if conf is not None:
                result.mu_star_conf[name] = [float(conf[idx])]
        result.ranking = sorted(names, key=lambda item: result.mu_star.get(item, 0.0), reverse=True)
        _attach_morris_uncertainty(result, plan, prepared.samples, prepared.outputs)
        return result

    if plan.method == SensitivityMethod.SOBOL:
        from SALib.analyze import sobol as sobol_analyzer  # type: ignore[import-not-found]

        salib_result = sobol_analyzer.analyze(
            problem,
            prepared.outputs,
            calc_second_order=True,
            conf_level=plan.confidence_level,
            seed=backend_seed,
        )
        for idx, name in enumerate(names):
            result.s1[name] = float(salib_result["S1"][idx])
            result.st[name] = float(salib_result["ST"][idx])
            result.s1_conf[name] = [float(salib_result["S1_conf"][idx])]
            result.st_conf[name] = [float(salib_result["ST_conf"][idx])]

        s2_matrix = salib_result.get("S2")
        if s2_matrix is not None:
            interaction_pairs: list[tuple[str, str, float]] = []
            for i, left in enumerate(names):
                interactions: dict[str, float] = {}
                for j, right in enumerate(names):
                    if i == j:
                        continue
                    value = float(s2_matrix[i][j])
                    if math.isnan(value):
                        continue
                    interactions[right] = value
                    if i < j:
                        interaction_pairs.append((left, right, value))
                if interactions:
                    result.s2[left] = interactions
            # Sort by absolute S2 value descending
            interaction_pairs.sort(key=lambda x: abs(x[2]), reverse=True)
            result.top_interactions = interaction_pairs
        result.ranking = sorted(names, key=lambda item: result.st.get(item, 0.0), reverse=True)
        _attach_sobol_uncertainty(result, plan, prepared.outputs)
        return result

    if plan.method == SensitivityMethod.FAST:
        if plan.seed is not None:
            raise ValueError(
                "FAST analysis is compatibility_pending for seeded plans: "
                "SALib 1.5.2 mutates process-global NumPy RNG"
            )
        from SALib.analyze import fast as fast_analyzer  # type: ignore[import-not-found]

        salib_result = fast_analyzer.analyze(problem, prepared.outputs)
        for idx, name in enumerate(names):
            result.s1[name] = float(salib_result["S1"][idx])
            result.st[name] = float(salib_result["ST"][idx])
        result.ranking = sorted(names, key=lambda item: result.st.get(item, 0.0), reverse=True)
        result.metadata["reproducibility_status"] = "compatibility_pending_fast_global_rng"
        if plan.uncertainty.enabled:
            _append_uncertainty_warning(result, "ci_unavailable_fast")
        return result

    raise ValueError(f"Unsupported sensitivity method: {plan.method}")


def _array_digest(values: np.ndarray) -> str:
    """Bind dimensions and ordered float64 values without changing their support."""
    canonical = np.asarray(values, dtype="<f8", order="C")
    digest = hashlib.sha256(json.dumps(list(canonical.shape)).encode("ascii"))
    digest.update(canonical.tobytes(order="C"))
    return digest.hexdigest()


def _analysis_identity(
    plan: SensitivityPlan, samples: np.ndarray, outputs: np.ndarray
) -> dict[str, object]:
    """Record actual ordered design, outcomes and estimator identity."""
    plan = _admit_sensitivity_plan(plan, actual_run_count=int(samples.shape[0]))
    if plan.method == SensitivityMethod.SOBOL:
        if plan.seed is None:
            raise ValueError("Sobol analysis requires a seed to reconcile its ordered design")
        expected = generate_sensitivity_samples(plan)
        _admit_sobol_sample_blocks(plan, samples, expected)
    sample_digest = _array_digest(samples)
    output_digest = _array_digest(outputs)
    design_payload = {
        "plan": plan.model_dump(mode="json"),
        "ordered_samples_sha256": sample_digest,
    }
    design_id = hashlib.sha256(
        json.dumps(design_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    analyzer = f"SALib@{version('SALib')}:{plan.method.value}"
    analysis_id = hashlib.sha256(f"{design_id}:{output_digest}:{analyzer}".encode()).hexdigest()
    return {
        "design_id": design_id,
        "analysis_id": analysis_id,
        "ordered_samples_sha256": sample_digest,
        "ordered_outputs_sha256": output_digest,
        "ordered_parameter_names": [spec.name for spec in plan.parameter_specs],
        "parameter_units": {spec.name: spec.unit for spec in plan.parameter_specs},
        "analyzer": analyzer,
        "analyzer_seed": _derive_backend_seed(plan.seed, f"analysis:{plan.method.value}"),
        "input_law": plan.input_law,
        "input_law_basis": "consumer_asserted",
        "authority_purpose": "exploratory_parameter_experiment",
        "population_law_status": "not_established",
        "point_effect_scale": (
            "unit_coordinate_full_range"
            if plan.method == SensitivityMethod.MORRIS
            else "variance_fraction"
        ),
        "design_order_basis": (
            "recomputed"
            if plan.method == SensitivityMethod.SOBOL
            else "geometry_validated_provenance_not_established"
        ),
    }


def _admit_sobol_sample_blocks(
    plan: SensitivityPlan, samples: np.ndarray, expected: np.ndarray
) -> None:
    """Reconcile the complete canonical Saltelli blocks, preserving each role's order.

    Permuting complete A/AB/BA/B blocks preserves the Sobol estimands. Actual
    row order still belongs to the content identity; no sorted representation
    replaces the stored samples or paired outputs. Membership is checked with
    exact float64 block bytes and multiplicity, never a geometry-only proxy.
    """
    if np.array_equal(samples, expected):
        return
    if samples.shape == expected.shape:
        block_size = 2 * plan.num_parameters + 2
        actual = np.asarray(samples, dtype="<f8", order="C")
        canonical = np.asarray(expected, dtype="<f8", order="C")
        actual_blocks = Counter(
            block.tobytes(order="C")
            for block in actual.reshape(-1, block_size, plan.num_parameters)
        )
        expected_blocks = Counter(
            block.tobytes(order="C")
            for block in canonical.reshape(-1, block_size, plan.num_parameters)
        )
        if actual_blocks == expected_blocks:
            return
    raise ValueError(
        "Sobol samples do not match the canonical seeded ordered design "
        "(only complete Saltelli block permutations are admitted)"
    )


@dataclass(frozen=True)
class _PreparedAnalysisInputs:
    """Prepared arrays plus original-run accounting for one sensitivity analysis."""

    samples: np.ndarray
    outputs: np.ndarray
    successful_runs: int
    failed_runs: int
    metadata: dict[str, object]


def _prepare_analysis_inputs(
    plan: SensitivityPlan,
    samples: np.ndarray,
    outputs: np.ndarray,
) -> _PreparedAnalysisInputs:
    plan = _admit_sensitivity_plan(plan)
    if outputs.ndim not in {1, 2}:
        raise ValueError("outputs must be 1-D or 2-D")
    if samples.ndim != 2 or samples.shape[0] != outputs.shape[0]:
        raise ValueError("samples and outputs must have the same row count")

    plan = _admit_sensitivity_plan(plan, actual_run_count=int(outputs.shape[0]))

    sample_valid = np.all(np.isfinite(samples), axis=1)
    if outputs.ndim == 1:
        output_valid = np.isfinite(outputs)
    else:
        output_valid = np.all(np.isfinite(outputs), axis=1)
    valid_mask = sample_valid & output_valid

    success_count = int(np.sum(valid_mask))
    failed_count = int(outputs.shape[0] - success_count)
    min_success = int(math.ceil(outputs.shape[0] * plan.min_success_rate))
    failed_row_indices = np.flatnonzero(~valid_mask).astype(int).tolist()
    failed_row_reasons: list[dict[str, object]] = []
    for row_index in failed_row_indices:
        input_invalid = not bool(sample_valid[row_index])
        output_invalid = not bool(output_valid[row_index])
        if input_invalid and output_invalid:
            reason = "nonfinite_input_and_output"
        elif input_invalid:
            reason = "nonfinite_input"
        else:
            reason = "nonfinite_output"
        failed_row_reasons.append({"row_index": row_index, "reason": reason})
    metadata: dict[str, object] = {
        "original_total_runs": int(outputs.shape[0]),
        "failed_row_indices": failed_row_indices,
        "failed_row_reasons": failed_row_reasons,
        "effective_run_count": int(outputs.shape[0]),
    }

    trajectory_size = plan.num_parameters + 1
    trajectory_count: int | None = None
    if plan.method == SensitivityMethod.MORRIS and trajectory_size > 0:
        metadata["morris_trajectory_size"] = trajectory_size
        if outputs.shape[0] % trajectory_size == 0:
            trajectory_count = outputs.shape[0] // trajectory_size
            metadata["original_trajectory_ids"] = list(range(trajectory_count))

    if success_count < min_success:
        raise ValueError(
            "Sensitivity analysis aborted: successful runs below min_success_rate "
            f"({success_count}/{outputs.shape[0]} < {min_success})."
        )

    if failed_count == 0:
        if trajectory_count is not None:
            metadata["effective_trajectory_ids"] = list(range(trajectory_count))
        return _PreparedAnalysisInputs(
            samples=samples,
            outputs=outputs,
            successful_runs=success_count,
            failed_runs=failed_count,
            metadata=metadata,
        )

    if plan.run_failure_policy == RunFailurePolicy.FAIL_FAST:
        raise ValueError(
            "Sensitivity analysis aborted: failed simulation runs detected "
            f"({failed_count}/{outputs.shape[0]})."
        )

    if plan.run_failure_policy == RunFailurePolicy.DROP_FAILED:
        if plan.method != SensitivityMethod.MORRIS:
            raise ValueError(
                "DROP_FAILED is only supported for MORRIS; use IMPUTE_BASELINE for "
                "structured SOBOL/FAST designs to preserve SALib sample geometry."
            )
        if trajectory_count is None:
            raise ValueError(
                "DROP_FAILED requires complete Morris trajectory blocks; "
                f"{outputs.shape[0]} rows cannot be partitioned into blocks of {trajectory_size}."
            )
        block_valid = valid_mask.reshape(trajectory_count, trajectory_size).all(axis=1)
        effective_trajectory_ids = np.flatnonzero(block_valid).astype(int).tolist()
        dropped_trajectory_ids = np.flatnonzero(~block_valid).astype(int).tolist()
        prepared_mask = np.repeat(block_valid, trajectory_size)
        prepared_samples = samples[prepared_mask]
        prepared_outputs = outputs[prepared_mask]
        metadata.update(
            {
                "effective_trajectory_ids": effective_trajectory_ids,
                "dropped_trajectory_ids": dropped_trajectory_ids,
                "effective_run_count": int(prepared_outputs.shape[0]),
            }
        )
        if dropped_trajectory_ids:
            metadata.update(
                {
                    "analysis_posture": "limited",
                    "selection_bias_status": "not_established",
                    "warnings": ["drop_failed_selection_bias_not_established"],
                }
            )
        return _PreparedAnalysisInputs(
            samples=prepared_samples,
            outputs=prepared_outputs,
            successful_runs=success_count,
            failed_runs=failed_count,
            metadata=metadata,
        )

    # IMPUTE_BASELINE
    if not np.all(sample_valid):
        raise ValueError(
            "IMPUTE_BASELINE cannot repair nonfinite input samples; "
            "retry the failed runs or use a complete design"
        )
    if outputs.ndim == 1:
        if success_count == 0:
            imputed = np.zeros_like(outputs)
        else:
            baseline = float(np.nanmedian(outputs[valid_mask]))
            imputed = outputs.copy()
            imputed[~valid_mask] = baseline
    else:
        imputed = outputs.copy()
        if success_count == 0:
            imputed[~valid_mask, :] = 0.0
        else:
            baselines = np.nanmedian(outputs[valid_mask], axis=0)
            imputed[~valid_mask, :] = baselines
    if trajectory_count is not None:
        metadata["effective_trajectory_ids"] = list(range(trajectory_count))
    return _PreparedAnalysisInputs(
        samples=samples,
        outputs=imputed,
        successful_runs=success_count,
        failed_runs=failed_count,
        metadata=metadata,
    )


def _plan_to_salib_problem(plan: SensitivityPlan) -> dict:
    problem, _ = _build_salib_problem(plan)
    return problem


def _attach_sobol_uncertainty(
    result: SensitivityResult,
    plan: SensitivityPlan,
    outputs: np.ndarray,
) -> None:
    if not plan.uncertainty.enabled:
        return
    try:
        blocks = sobol_blocks_from_salib_outputs(
            outputs,
            result.parameter_names,
            calc_second_order=True,
        )
        if plan.uncertainty.method.lower() in {"asymptotic", "asymptotic_delta"}:
            result.uncertainty = analyze_sobol_asymptotic_delta(blocks, plan.uncertainty)
        else:
            result.uncertainty = analyze_sobol_paired_bootstrap(blocks, plan.uncertainty)
        result.metadata["uncertainty_status"] = "ok"
    except Exception as exc:
        _append_uncertainty_warning(result, f"sobol_uncertainty_unavailable:{exc}")


def _attach_morris_uncertainty(
    result: SensitivityResult,
    plan: SensitivityPlan,
    samples: np.ndarray,
    outputs: np.ndarray,
) -> None:
    if not plan.uncertainty.enabled:
        return
    if result.metadata.get("selection_bias_status") == "not_established":
        _append_uncertainty_warning(
            result,
            "morris_uncertainty_unavailable:drop_failed_selection_bias_not_established",
        )
        return
    if any(spec.distribution.value != "uniform" for spec in plan.parameter_specs):
        _append_uncertainty_warning(
            result,
            "morris_uncertainty_unavailable:unsupported_coordinate_transform",
        )
        return
    try:
        parameter_bounds = {
            spec.name: (spec.lower_bound, spec.upper_bound) for spec in plan.parameter_specs
        }
        elementary_effects = morris_elementary_effects_from_samples(
            samples,
            outputs,
            result.parameter_names,
            parameter_bounds=parameter_bounds,
            num_levels=plan.parameter_specs[0].num_levels,
        )
        result.uncertainty = analyze_morris_trajectory_bootstrap(
            elementary_effects,
            result.parameter_names,
            plan.uncertainty,
        )
        result.metadata["uncertainty_status"] = "ok"
    except Exception as exc:
        _append_uncertainty_warning(result, f"morris_uncertainty_unavailable:{exc}")


def _append_uncertainty_warning(result: SensitivityResult, warning: str) -> None:
    result.metadata["uncertainty_status"] = "unavailable"
    warnings = result.metadata.setdefault("warnings", [])
    if isinstance(warnings, list):
        warnings.append(warning)
