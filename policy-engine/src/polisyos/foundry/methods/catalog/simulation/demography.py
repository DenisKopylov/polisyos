"""Static aging with demographic consistency orchestration."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, ClassVar, Literal

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator

from polisyos.core.observability.determinism import DeterminismTier
from polisyos.foundry.methods.base import (
    ComplexityClass,
    ComputeBackend,
    FidelityLevel,
    MethodKind,
    MethodMetadata,
    MethodSignature,
    ParameterSpec,
    SlotSpec,
    SlotType,
    Unit,
    foundry_method,
)
from polisyos.foundry.methods.catalog._phase1_artifacts import resolve_artifact_store
from polisyos.foundry.methods.catalog.survey.demographic_consistency import (
    DemographicConsistencyEstimator,
    DemographicConsistencyResult,
)
from polisyos.ir.analytics.microsim_calibration import load_microsim_calibration_report
from polisyos.ir.refs import MicrosimCalibrationReportRef


def _result_slot() -> frozenset[SlotSpec]:
    return frozenset(
        {
            SlotSpec(
                "result",
                SlotType.SCALAR,
                Unit("demography", "json"),
                contract_id=StaticAgingResult.contract_id,
            )
        }
    )


def _to_numpy(value: Any, *, dtype: Any = float) -> np.ndarray:
    if isinstance(value, np.ndarray):
        return value.astype(dtype, copy=False)
    return np.asarray(value, dtype=dtype)


def _vector(state: Mapping[str, Any], key: str, *, dtype: Any = float) -> np.ndarray:
    arr = _to_numpy(state[key], dtype=dtype)
    if arr.ndim != 1:
        raise ValueError(f"{key} must be a 1D vector")
    if dtype in (float, np.float64) and not np.all(np.isfinite(arr)):
        raise ValueError(f"{key} must contain only finite values")
    return arr


def _index_vector(
    state: Mapping[str, Any], key: str, *, expected_length: int | None = None
) -> np.ndarray:
    raw = state[key]
    arr = np.asarray(raw)
    if arr.ndim != 1:
        raise ValueError(f"{key} must be a 1D vector")
    if expected_length is not None and arr.shape[0] != expected_length:
        raise ValueError(f"{key} must have length {expected_length}")
    try:
        coerced = arr.astype(np.int64, copy=False)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{key} must contain integer-like values") from exc
    if not np.allclose(arr, coerced, atol=0.0):
        raise ValueError(f"{key} must contain integer-like values")
    return coerced


def _optional_vector(
    state: Mapping[str, Any],
    key: str,
    *,
    dtype: Any = float,
    expected_length: int | None = None,
) -> np.ndarray | None:
    raw = state.get(key)
    if raw is None:
        return None
    arr = _to_numpy(raw, dtype=dtype)
    if arr.ndim != 1:
        raise ValueError(f"{key} must be a 1D vector")
    if expected_length is not None and arr.shape[0] != expected_length:
        raise ValueError(f"{key} must have length {expected_length}")
    if dtype in (float, np.float64) and not np.all(np.isfinite(arr)):
        raise ValueError(f"{key} must contain only finite values")
    return arr


def _optional_index_vector(
    state: Mapping[str, Any],
    key: str,
    *,
    expected_length: int | None = None,
) -> np.ndarray | None:
    if key not in state:
        return None
    return _index_vector(state, key, expected_length=expected_length)


def _matrix(state: Mapping[str, Any], key: str, *, dtype: Any = float) -> np.ndarray:
    arr = _to_numpy(state[key], dtype=dtype)
    if arr.ndim != 2:
        raise ValueError(f"{key} must be a 2D matrix")
    if dtype in (float, np.float64) and not np.all(np.isfinite(arr)):
        raise ValueError(f"{key} must contain only finite values")
    return arr


def _require_microsim_gate(
    state: Mapping[str, Any],
    *,
    artifact_store: Any | None,
) -> dict[str, Any]:
    report = state.get("microsim_calibration_report")
    if isinstance(report, dict):
        if not bool(report.get("can_run_microsim", False)):
            reason = ", ".join(report.get("blocking_reasons", ())) or str(
                report.get("compatibility_status", "blocked")
            )
            raise ValueError(f"static_aging refused to run: {reason}")
        return report
    ref_payload = state.get("microsim_calibration_report_ref")
    if isinstance(ref_payload, dict) and artifact_store is not None:
        ref = MicrosimCalibrationReportRef.model_validate(ref_payload)
        report = load_microsim_calibration_report(artifact_store, ref).model_dump(mode="json")
        if not bool(report.get("can_run_microsim", False)):
            reason = ", ".join(report.get("blocking_reasons", ())) or str(
                report.get("compatibility_status", "blocked")
            )
            raise ValueError(f"static_aging refused to run: {reason}")
        return report
    raise ValueError(
        "static_aging requires microsim_calibration_report or microsim_calibration_report_ref; "
        "uncertified base_weights are not allowed"
    )


class StaticAgingResult(BaseModel):
    """Materialized aged sample with deterministic flows and optional stochastic draws."""

    contract_id: ClassVar[str] = "foundry.simulation.static_aging_result.v1"
    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)

    mode: Literal["deterministic", "integerized", "stochastic"]
    survivor_record_index: Any
    survivor_origin_state_index: Any | None = None
    survivor_destination_state_index: Any
    survivor_weights: Any
    entrant_record_index: Any | None = None
    entrant_state_index: Any | None = None
    entrant_weights: Any | None = None
    aged_state_totals: Any
    transition_matrix: Any | None = None
    stochastic_draws: list[dict[str, Any]] = Field(default_factory=list)
    flow_result: dict[str, Any]
    diagnostics: dict[str, Any] = Field(default_factory=dict)

    @field_validator(
        "survivor_record_index",
        "survivor_origin_state_index",
        "survivor_destination_state_index",
        "survivor_weights",
        "entrant_record_index",
        "entrant_state_index",
        "entrant_weights",
        "aged_state_totals",
        "transition_matrix",
        mode="before",
    )
    @classmethod
    def _coerce_numpy(cls, value: Any) -> Any:
        if value is None:
            return None
        return np.asarray(value)

    @field_serializer(
        "survivor_record_index",
        "survivor_origin_state_index",
        "survivor_destination_state_index",
        "survivor_weights",
        "entrant_record_index",
        "entrant_state_index",
        "entrant_weights",
        "aged_state_totals",
        "transition_matrix",
        mode="plain",
        when_used="json",
    )
    def _serialize_numpy(self, value: Any) -> Any:
        if isinstance(value, np.ndarray):
            return value.tolist()
        return value


def _build_sparse_candidates(
    base_weights: np.ndarray,
    origin_state_index: np.ndarray,
    target_state_totals: np.ndarray,
    transition_prior_matrix: np.ndarray,
    *,
    allowed_transition_mask: np.ndarray | None,
    top_k_destinations: int | None,
    min_transition_prior: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    n_records = base_weights.shape[0]
    n_states = target_state_totals.shape[0]
    if origin_state_index.shape[0] != n_records:
        raise ValueError("origin_state_index must align with base_weights")
    if np.any(origin_state_index < 0) or np.any(
        origin_state_index >= transition_prior_matrix.shape[0]
    ):
        raise ValueError("origin_state_index contains out-of-range ids")
    if transition_prior_matrix.shape[1] != n_states:
        raise ValueError("transition_prior_matrix columns must match target_state_totals")
    if np.any(transition_prior_matrix < 0.0):
        raise ValueError("transition_prior_matrix must be non-negative")
    if (
        allowed_transition_mask is not None
        and allowed_transition_mask.shape != transition_prior_matrix.shape
    ):
        raise ValueError("allowed_transition_mask must match transition_prior_matrix")

    top_k = None if top_k_destinations in {None, 0} else max(1, int(top_k_destinations))
    per_origin_destinations: dict[int, np.ndarray] = {}
    per_origin_priors: dict[int, np.ndarray] = {}

    for origin in np.unique(origin_state_index):
        row = transition_prior_matrix[int(origin)].astype(float, copy=True)
        if allowed_transition_mask is not None:
            row *= allowed_transition_mask[int(origin)].astype(float)
        if min_transition_prior > 0.0:
            row = np.where(row >= min_transition_prior, row, 0.0)
        positive = np.flatnonzero(row > 0.0)
        if positive.size == 0:
            raise ValueError(f"origin state {origin} has no admissible destination states")
        if top_k is not None and positive.size > top_k:
            order = np.argsort(row[positive])[::-1][:top_k]
            positive = positive[order]
        weights = row[positive]
        weights /= max(float(np.sum(weights)), 1e-12)
        per_origin_destinations[int(origin)] = positive.astype(np.int64, copy=False)
        per_origin_priors[int(origin)] = weights.astype(float, copy=False)

    record_index_parts: list[np.ndarray] = []
    state_index_parts: list[np.ndarray] = []
    prior_parts: list[np.ndarray] = []
    for record_idx, origin in enumerate(origin_state_index):
        dest = per_origin_destinations[int(origin)]
        priors = per_origin_priors[int(origin)]
        record_index_parts.append(np.full(dest.shape[0], record_idx, dtype=np.int64))
        state_index_parts.append(dest)
        prior_parts.append(priors)

    return (
        np.concatenate(record_index_parts, dtype=np.int64),
        np.concatenate(state_index_parts, dtype=np.int64),
        np.concatenate(prior_parts, dtype=float),
    )


def _scale_donor_pool(
    donor_weights: np.ndarray,
    donor_state_index: np.ndarray,
    entrant_state_totals: np.ndarray,
    *,
    donor_record_index: np.ndarray | None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    if donor_weights.shape[0] != donor_state_index.shape[0]:
        raise ValueError("donor_weights and donor_state_index must align")
    if donor_record_index is None:
        donor_record_index = np.arange(donor_weights.shape[0], dtype=np.int64)
    if donor_record_index.shape[0] != donor_weights.shape[0]:
        raise ValueError("donor_record_index must align with donor_weights")

    n_states = entrant_state_totals.shape[0]
    if np.any(donor_state_index < 0) or np.any(donor_state_index >= n_states):
        raise ValueError("donor_state_index contains out-of-range ids")
    donor_mass_by_state = np.bincount(
        donor_state_index,
        weights=donor_weights,
        minlength=n_states,
    ).astype(float, copy=False)
    positive_entrant_states = np.flatnonzero(entrant_state_totals > 0.0)
    missing = positive_entrant_states[donor_mass_by_state[positive_entrant_states] <= 0.0]
    if missing.size:
        preview = ", ".join(map(str, missing[:5]))
        raise ValueError(
            f"entrant states require donor mass but donor pool is empty for states: {preview}"
        )

    scale = np.ones(n_states, dtype=float)
    positive = donor_mass_by_state > 0.0
    scale[positive] = entrant_state_totals[positive] / donor_mass_by_state[positive]
    entrant_weights = donor_weights * scale[donor_state_index]
    keep = entrant_weights > 0.0
    return donor_record_index[keep], donor_state_index[keep], entrant_weights[keep]


def _integerize_weights(
    weights: np.ndarray, *, unit_weight: float, rng: np.random.Generator
) -> np.ndarray:
    if unit_weight <= 0.0:
        raise ValueError("unit_weight must be positive")
    scaled = np.maximum(weights / unit_weight, 0.0)
    floor_units = np.floor(scaled).astype(np.int64)
    residual = scaled - floor_units
    target_units = int(np.rint(np.sum(scaled)))
    current_units = int(np.sum(floor_units))
    extra_units = max(0, target_units - current_units)
    if extra_units > 0:
        positive = np.flatnonzero(residual > 1e-12)
        if positive.size == 0:
            return floor_units.astype(float) * unit_weight
        probs = residual[positive] / np.sum(residual[positive])
        chosen = rng.choice(
            positive,
            size=min(extra_units, positive.size),
            replace=False,
            p=probs,
        )
        floor_units[chosen] += 1
    return floor_units.astype(float) * unit_weight


def _draw_integerized_sample(
    survivor_state_index: np.ndarray,
    survivor_weights: np.ndarray,
    entrant_state_index: np.ndarray | None,
    entrant_weights: np.ndarray | None,
    *,
    unit_weight: float,
    seed: int,
    draw_index: int,
    n_states: int,
) -> dict[str, Any]:
    rng = np.random.default_rng(seed + draw_index)
    int_survivors = _integerize_weights(survivor_weights, unit_weight=unit_weight, rng=rng)
    if entrant_weights is None or entrant_state_index is None:
        int_entrants = np.zeros(0, dtype=float)
        entrant_state_totals = np.zeros(n_states, dtype=float)
    else:
        int_entrants = _integerize_weights(entrant_weights, unit_weight=unit_weight, rng=rng)
        entrant_state_totals = np.bincount(
            entrant_state_index,
            weights=int_entrants,
            minlength=n_states,
        ).astype(float, copy=False)
    survivor_state_totals = np.bincount(
        survivor_state_index,
        weights=int_survivors,
        minlength=n_states,
    ).astype(float, copy=False)
    state_totals = survivor_state_totals + entrant_state_totals
    return {
        "draw_index": int(draw_index),
        "survivor_weights": int_survivors.tolist(),
        "entrant_weights": int_entrants.tolist(),
        "state_totals": state_totals.tolist(),
    }


@foundry_method(
    namespace="simulation.demography",
    version="1.0.0",
    tags={"simulation", "demography", "microsim", "static-aging"},
)
class StaticAgingSimulationEstimator:
    """Orchestrate deterministic or integerized static aging from macro priors and targets."""

    method_kind: ClassVar[MethodKind] = MethodKind.SIMULATION
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="static_aging",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    "base_weights", SlotType.VECTOR, Unit("weight", "mass"), shape=("n_records",)
                ),
                SlotSpec(
                    "origin_state_index",
                    SlotType.VECTOR,
                    Unit("state", "index"),
                    shape=("n_records",),
                ),
                SlotSpec(
                    "target_state_totals",
                    SlotType.VECTOR,
                    Unit("state_total", "mass"),
                    shape=("n_states",),
                ),
                SlotSpec(
                    "transition_prior_matrix",
                    SlotType.MATRIX,
                    Unit("transition", "mass"),
                    shape=("n_origin_states", "n_states"),
                ),
            }
        ),
        output_slots=_result_slot(),
        parameters=(
            ParameterSpec(name="mode", default="deterministic"),
            ParameterSpec(name="max_iterations", default=250),
            ParameterSpec(name="tolerance", default=1e-8),
            ParameterSpec(name="reconciliation_mode", default="scale_survivor_targets"),
            ParameterSpec(name="top_k_destinations", default=4),
            ParameterSpec(name="min_transition_prior", default=0.0),
            ParameterSpec(name="soft_iterations", default=6),
            ParameterSpec(name="soft_tolerance", default=1e-4),
            ParameterSpec(name="soft_step_size", default=0.25),
            ParameterSpec(name="seed", default=0),
            ParameterSpec(name="unit_weight", default=1.0),
            ParameterSpec(name="n_draws", default=1),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description=(
            "Static aging wrapper that turns origin-state transition priors and macro targets "
            "into a deterministic aged sample plus optional integerized draws."
        ),
        tags=frozenset({"simulation", "demography", "microsim", "static-aging"}),
        when_to_use=(
            "One-step demographic aging with cohort-component accounting, donor entrants, "
            "and optional integerized outputs for downstream agent-style execution."
        ),
        citations=DemographicConsistencyEstimator.metadata.citations,
        output_interpretation=(
            "The deterministic result is canonical. Integerized or stochastic draws are "
            "derived approximations for downstream discrete simulations."
        ),
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        artifact_store = resolve_artifact_store(state, params)
        calibration_gate = _require_microsim_gate(state, artifact_store=artifact_store)
        base_weights = _vector(state, "base_weights", dtype=float)
        target_state_totals = _vector(state, "target_state_totals", dtype=float)
        n_states = target_state_totals.shape[0]
        origin_state_index = _optional_index_vector(
            state,
            "origin_state_index",
            expected_length=base_weights.shape[0],
        )
        mode = str(params.get("mode", "deterministic")).strip().lower()
        if mode not in {"deterministic", "integerized", "stochastic"}:
            raise ValueError("mode must be one of deterministic, integerized, stochastic")

        if "candidate_record_index" in state and "candidate_state_index" in state:
            candidate_record_index = _index_vector(state, "candidate_record_index")
            candidate_state_index = _index_vector(
                state,
                "candidate_state_index",
                expected_length=candidate_record_index.shape[0],
            )
            prior_flows = _vector(state, "prior_flows", dtype=float)
        else:
            if origin_state_index is None:
                raise ValueError(
                    "origin_state_index is required when sparse candidate edges are not supplied"
                )
            transition_prior_matrix = _matrix(state, "transition_prior_matrix", dtype=float)
            allowed_transition_mask = state.get("allowed_transition_mask")
            if allowed_transition_mask is not None:
                allowed_transition_mask = np.asarray(allowed_transition_mask, dtype=bool)
            candidate_record_index, candidate_state_index, prior_flows = _build_sparse_candidates(
                base_weights,
                origin_state_index,
                target_state_totals,
                transition_prior_matrix,
                allowed_transition_mask=allowed_transition_mask,
                top_k_destinations=params.get("top_k_destinations", 4),
                min_transition_prior=max(0.0, float(params.get("min_transition_prior", 0.0))),
            )

        survey_state: dict[str, Any] = {
            "base_weights": base_weights,
            "candidate_record_index": candidate_record_index,
            "candidate_state_index": candidate_state_index,
            "prior_flows": prior_flows,
            "target_state_totals": target_state_totals,
        }
        for optional_key in (
            "exit_weights",
            "entrant_state_totals",
            "soft_constraint_matrix",
            "soft_target_totals",
            "soft_constraint_weights",
            "structural_zero_mask",
        ):
            if optional_key in state:
                survey_state[optional_key] = state[optional_key]

        flow_result = DemographicConsistencyEstimator.pure_step(
            survey_state,
            {
                "max_iterations": int(params.get("max_iterations", 250)),
                "tolerance": float(params.get("tolerance", 1e-8)),
                "reconciliation_mode": params.get("reconciliation_mode", "scale_survivor_targets"),
                "require_convergence": True,
                "soft_iterations": int(params.get("soft_iterations", 6)),
                "soft_tolerance": float(params.get("soft_tolerance", 1e-4)),
                "soft_step_size": float(params.get("soft_step_size", 0.25)),
            },
        )["result"]
        if not isinstance(flow_result, DemographicConsistencyResult):
            raise TypeError("demographic consistency core returned an unexpected result payload")

        survivor_record_index = np.asarray(flow_result.candidate_record_index, dtype=np.int64)
        survivor_destination_state_index = np.asarray(
            flow_result.candidate_state_index, dtype=np.int64
        )
        survivor_weights = np.asarray(flow_result.calibrated_flows, dtype=float)

        if origin_state_index is not None:
            survivor_origin_state_index = origin_state_index[survivor_record_index]
            n_origin_states = int(np.max(origin_state_index, initial=-1)) + 1
            transition_matrix = np.zeros((n_origin_states, n_states), dtype=float)
            np.add.at(
                transition_matrix,
                (survivor_origin_state_index, survivor_destination_state_index),
                survivor_weights,
            )
        else:
            survivor_origin_state_index = None
            transition_matrix = None

        entrant_state_totals = np.asarray(flow_result.entrant_state_totals, dtype=float)
        donor_weights = _optional_vector(state, "donor_weights", dtype=float)
        donor_state_index = _optional_index_vector(state, "donor_state_index")
        donor_record_index = _optional_index_vector(state, "donor_record_index")
        if float(np.sum(entrant_state_totals)) > 0.0:
            if donor_weights is None or donor_state_index is None:
                raise ValueError(
                    "positive entrant_state_totals require donor_weights and donor_state_index"
                )
            entrant_record_index, entrant_state_index, entrant_weights = _scale_donor_pool(
                donor_weights,
                donor_state_index,
                entrant_state_totals,
                donor_record_index=donor_record_index,
            )
        else:
            entrant_record_index = np.zeros(0, dtype=np.int64)
            entrant_state_index = np.zeros(0, dtype=np.int64)
            entrant_weights = np.zeros(0, dtype=float)

        aged_state_totals = np.asarray(flow_result.achieved_state_totals, dtype=float)
        stochastic_draws: list[dict[str, Any]] = []
        if mode in {"integerized", "stochastic"}:
            n_draws = 1 if mode == "integerized" else max(1, int(params.get("n_draws", 1)))
            seed = int(params.get("seed", 0))
            unit_weight = float(params.get("unit_weight", 1.0))
            stochastic_draws = [
                _draw_integerized_sample(
                    survivor_destination_state_index,
                    survivor_weights,
                    entrant_state_index,
                    entrant_weights,
                    unit_weight=unit_weight,
                    seed=seed,
                    draw_index=draw_index,
                    n_states=n_states,
                )
                for draw_index in range(n_draws)
            ]

        diagnostics = dict(flow_result.diagnostics)
        diagnostics.update(
            {
                "mode": mode,
                "survivor_edge_count": int(survivor_weights.shape[0]),
                "entrant_record_count": int(entrant_weights.shape[0]),
                "deterministic_survivor_mass": float(np.sum(survivor_weights)),
                "deterministic_entrant_mass": float(np.sum(entrant_weights)),
                "stochastic_draw_count": len(stochastic_draws),
                "microsim_calibration_decision": calibration_gate.get("decision"),
            }
        )
        if donor_weights is not None and entrant_weights.shape[0] > 0:
            diagnostics["donor_positive_share"] = float(
                np.mean((entrant_weights > 0.0).astype(float))
            )

        result = StaticAgingResult(
            mode=mode,
            survivor_record_index=survivor_record_index,
            survivor_origin_state_index=survivor_origin_state_index,
            survivor_destination_state_index=survivor_destination_state_index,
            survivor_weights=survivor_weights,
            entrant_record_index=entrant_record_index,
            entrant_state_index=entrant_state_index,
            entrant_weights=entrant_weights,
            aged_state_totals=aged_state_totals,
            transition_matrix=transition_matrix,
            stochastic_draws=stochastic_draws,
            flow_result=flow_result.model_dump(mode="json"),
            diagnostics=diagnostics,
        )
        return {"result": result}


__all__ = ["StaticAgingResult", "StaticAgingSimulationEstimator"]
