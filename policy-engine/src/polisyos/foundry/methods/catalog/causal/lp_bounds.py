"""Solve linear-program bounds for partially identified causal estimands."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from itertools import product
from typing import Any

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

from polisyos.ir.analytics.dual_certificate import (
    BoundsDualCertificateBundle,
    StratifiedLPDualCertificate,
    StratifiedLPDualCertificateBundle,
    build_response_function_dual_certificate_bundle,
)
from polisyos.ir.analytics.partial_identification import (
    BoundMethod,
    PartialIdentificationResult,
)

_MAX_EXACT_RESPONSE_TYPES = 5_000


class DiscretizedVariable(BaseModel):
    """Represent one discretized support axis used by the LP bounding problem."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    edges: tuple[float, ...]
    bin_lower: tuple[float, ...]
    bin_upper: tuple[float, ...]
    bin_mid: tuple[float, ...]
    bin_probabilities: tuple[float, ...]
    method: str
    n_bins: int = Field(ge=1)
    converged: bool = False


@dataclass(frozen=True)
class _LPResult:
    lower: float
    upper: float
    status: str
    dual_certificate_payload: dict[str, Any] | None = None


def _finite_values(values: np.ndarray) -> np.ndarray:
    arr = np.asarray(values, dtype=float).reshape(-1)
    return arr[np.isfinite(arr)]


def _normalize_probability_table(table: np.ndarray) -> np.ndarray:
    total = float(np.sum(table))
    if total <= 0.0:
        return np.zeros_like(table, dtype=float)
    return np.asarray(table, dtype=float) / total


def _unique_levels(values: np.ndarray, *, tol: float = 1e-9) -> np.ndarray:
    arr = _finite_values(values)
    if arr.size == 0:
        return np.array([], dtype=float)
    rounded = np.round(arr / tol) * tol
    return np.unique(rounded)


def _looks_discrete(values: np.ndarray, *, max_levels: int | None = None) -> bool:
    levels = _unique_levels(values)
    if levels.size == 0:
        return False
    if max_levels is not None and levels.size > max_levels:
        return False
    return bool(np.allclose(levels, np.round(levels), atol=1e-6) or levels.size <= 12)


def _ordered_levels(values: np.ndarray) -> np.ndarray:
    levels = _unique_levels(values)
    if levels.size:
        return np.sort(levels)
    return np.array([], dtype=float)


def _response_space_size(n_treatments: int, n_outcomes: int) -> int:
    if n_treatments <= 0 or n_outcomes <= 0:
        return 0
    return int(n_treatments * (n_outcomes**n_treatments))


def _empirical_joint(
    treatment: np.ndarray,
    outcome: np.ndarray,
    t_levels: np.ndarray,
    y_levels: np.ndarray,
) -> np.ndarray:
    joint = np.zeros((len(t_levels), len(y_levels)), dtype=float)
    if len(t_levels) == 0 or len(y_levels) == 0:
        return joint
    total = float(max(len(treatment), 1))
    for i, t_val in enumerate(t_levels):
        for j, y_val in enumerate(y_levels):
            joint[i, j] = (
                float(
                    np.sum(
                        np.isclose(treatment, t_val, atol=1e-9)
                        & np.isclose(outcome, y_val, atol=1e-9)
                    )
                )
                / total
            )
    return _normalize_probability_table(joint)


def _exact_joint_from_arrays(
    treatment: np.ndarray,
    outcome: np.ndarray,
    *,
    max_cardinality: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray] | None:
    t_levels = _ordered_levels(treatment)
    y_levels = _ordered_levels(outcome)
    if t_levels.size < 2 or y_levels.size < 2:
        return None
    if max_cardinality > 0 and (t_levels.size > max_cardinality or y_levels.size > max_cardinality):
        return None
    if not _looks_discrete(treatment) or not _looks_discrete(outcome):
        return None
    if _response_space_size(int(t_levels.size), int(y_levels.size)) > _MAX_EXACT_RESPONSE_TYPES:
        return None
    joint = _empirical_joint(treatment, outcome, t_levels, y_levels)
    return joint, t_levels, y_levels


def _build_response_types(
    t_levels: np.ndarray,
    y_lower: np.ndarray,
    y_upper: np.ndarray,
    *,
    monotone: bool = False,
    target_index: int = 1,
    reference_index: int = 0,
) -> tuple[list[tuple[int, tuple[int, ...]]], np.ndarray, np.ndarray]:
    response_types: list[tuple[int, tuple[int, ...]]] = []
    lower_effects: list[float] = []
    upper_effects: list[float] = []
    for t_obs in range(len(t_levels)):
        for response_vector in product(range(len(y_lower)), repeat=len(t_levels)):
            if monotone and response_vector[target_index] < response_vector[reference_index]:
                continue
            response_types.append((t_obs, tuple(int(v) for v in response_vector)))
            lower_effects.append(
                float(
                    y_lower[response_vector[target_index]]
                    - y_upper[response_vector[reference_index]]
                )
            )
            upper_effects.append(
                float(
                    y_upper[response_vector[target_index]]
                    - y_lower[response_vector[reference_index]]
                )
            )
    return (
        response_types,
        np.asarray(lower_effects, dtype=float),
        np.asarray(upper_effects, dtype=float),
    )


def build_response_function_constraints(
    joint: np.ndarray,
    t_levels: np.ndarray,
    y_levels: np.ndarray,
    *,
    y_lower: np.ndarray | None = None,
    y_upper: np.ndarray | None = None,
    monotone: bool = False,
    target_index: int = 1,
    reference_index: int = 0,
) -> tuple[np.ndarray, np.ndarray, list[tuple[int, tuple[int, ...]]], np.ndarray, np.ndarray]:
    """Build equality constraints for the response-function LP."""
    joint = np.asarray(joint, dtype=float)
    y_lower_arr = np.asarray(y_levels if y_lower is None else y_lower, dtype=float)
    y_upper_arr = np.asarray(y_levels if y_upper is None else y_upper, dtype=float)
    response_types, lower_effects, upper_effects = _build_response_types(
        t_levels,
        y_lower_arr,
        y_upper_arr,
        monotone=monotone,
        target_index=target_index,
        reference_index=reference_index,
    )
    n_types = len(response_types)
    rows: list[np.ndarray] = []
    rhs: list[float] = []
    for t_obs in range(len(t_levels)):
        for y_obs in range(len(y_levels)):
            row = np.zeros(n_types, dtype=float)
            for idx, (latent_t, response_vector) in enumerate(response_types):
                if latent_t == t_obs and response_vector[t_obs] == y_obs:
                    row[idx] = 1.0
            rows.append(row)
            rhs.append(float(joint[t_obs, y_obs]))
    rows.append(np.ones(n_types, dtype=float))
    rhs.append(1.0)
    return (
        np.asarray(rows, dtype=float),
        np.asarray(rhs, dtype=float),
        response_types,
        lower_effects,
        upper_effects,
    )


def build_query_objective(
    effect_values: np.ndarray,
    *,
    direction: str = "lower",
) -> np.ndarray:
    """Build query objective."""
    if direction == "lower":
        return np.asarray(effect_values, dtype=float)
    if direction == "upper":
        return -np.asarray(effect_values, dtype=float)
    raise ValueError("direction must be 'lower' or 'upper'")


def _solve_response_lp(
    joint: np.ndarray,
    t_levels: np.ndarray,
    y_levels: np.ndarray,
    *,
    y_lower: np.ndarray | None = None,
    y_upper: np.ndarray | None = None,
    monotone: bool = False,
    target_index: int = 1,
    reference_index: int = 0,
) -> _LPResult:
    from scipy.optimize import linprog

    y_lower_arr = np.asarray(y_levels if y_lower is None else y_lower, dtype=float)
    y_upper_arr = np.asarray(y_levels if y_upper is None else y_upper, dtype=float)
    A_eq, b_eq, response_types, lower_effects, upper_effects = build_response_function_constraints(
        joint,
        t_levels,
        y_levels,
        y_lower=y_lower_arr,
        y_upper=y_upper_arr,
        monotone=monotone,
        target_index=target_index,
        reference_index=reference_index,
    )
    bounds = [(0.0, None)] * len(response_types)
    res_lo = linprog(
        build_query_objective(lower_effects, direction="lower"),
        A_eq=A_eq,
        b_eq=b_eq,
        bounds=bounds,
        method="highs",
    )
    res_hi = linprog(
        build_query_objective(upper_effects, direction="upper"),
        A_eq=A_eq,
        b_eq=b_eq,
        bounds=bounds,
        method="highs",
    )
    if res_lo.status == 0 and res_hi.status == 0:
        certificate_bundle = build_response_function_dual_certificate_bundle(
            joint=np.asarray(joint, dtype=float),
            treatment_levels=np.asarray(t_levels, dtype=float),
            outcome_levels=np.asarray(y_levels, dtype=float),
            outcome_lower=y_lower_arr,
            outcome_upper=y_upper_arr,
            monotone=bool(monotone),
            target_index=int(target_index),
            reference_index=int(reference_index),
            lower_result=res_lo,
            upper_result=res_hi,
        )
        return _LPResult(
            lower=float(res_lo.fun),
            upper=float(-res_hi.fun),
            status="optimal",
            dual_certificate_payload=certificate_bundle.model_dump(mode="json"),
        )
    if res_lo.status == 2 or res_hi.status == 2:
        status = f"infeasible(lo={res_lo.status},hi={res_hi.status})"
    elif res_lo.status == 3 or res_hi.status == 3:
        status = f"unbounded(lo={res_lo.status},hi={res_hi.status})"
    else:
        status = f"solver_failed(lo={res_lo.status},hi={res_hi.status})"
    if res_lo.status == 0:
        lo = float(res_lo.fun)
    else:
        lo = float(np.min(lower_effects)) if lower_effects.size else 0.0
    if res_hi.status == 0:
        hi = float(-res_hi.fun)
    else:
        hi = float(np.max(upper_effects)) if upper_effects.size else 0.0
    return _LPResult(lower=lo, upper=hi, status=status)


def _discretize_continuous_for_bounds(
    values: np.ndarray,
    *,
    variable: str,
    n_bins: int = 10,
    method: str = "equal_frequency",
) -> DiscretizedVariable:
    data = _finite_values(values)
    if data.size == 0:
        raise ValueError(f"{variable} has no finite observations")
    if n_bins < 1:
        raise ValueError("n_bins must be >= 1")

    lo = float(np.min(data))
    hi = float(np.max(data))
    if np.isclose(lo, hi):
        edges = np.array([lo, hi], dtype=float)
        return DiscretizedVariable(
            name=variable,
            edges=tuple(float(v) for v in edges),
            bin_lower=(lo,),
            bin_upper=(hi,),
            bin_mid=((lo + hi) / 2.0,),
            bin_probabilities=(1.0,),
            method=method,
            n_bins=1,
            converged=True,
        )

    if method == "equal_width":
        edges = np.linspace(lo, hi, n_bins + 1)
    else:
        quantiles = np.linspace(0.0, 1.0, n_bins + 1)
        edges = np.quantile(data, quantiles)
        edges = np.unique(edges)
        if edges.size < 2:
            edges = np.linspace(lo, hi, n_bins + 1)
    edges = np.unique(edges)
    if edges.size < 2:
        edges = np.array([lo, hi], dtype=float)

    bin_ids = np.digitize(data, edges[1:-1], right=True)
    n_bins_eff = max(int(edges.size - 1), 1)
    probs = np.array([float(np.mean(bin_ids == i)) for i in range(n_bins_eff)], dtype=float)
    lowers = tuple(float(edges[i]) for i in range(n_bins_eff))
    uppers = tuple(float(edges[i + 1]) for i in range(n_bins_eff))
    mids = tuple((low + high) / 2.0 for low, high in zip(lowers, uppers))
    return DiscretizedVariable(
        name=variable,
        edges=tuple(float(v) for v in edges),
        bin_lower=lowers,
        bin_upper=uppers,
        bin_mid=mids,
        bin_probabilities=tuple(float(v) for v in probs),
        method=method,
        n_bins=n_bins_eff,
        converged=False,
    )


def _coarsen_variable(
    values: np.ndarray,
    *,
    variable: str,
    target_bins: int,
) -> DiscretizedVariable | None:
    levels = _ordered_levels(values)
    if (
        levels.size >= 2
        and levels.size <= target_bins
        and _looks_discrete(values, max_levels=target_bins)
    ):
        return None
    return _discretize_continuous_for_bounds(
        values,
        variable=variable,
        n_bins=max(2, target_bins),
        method="adaptive",
    )


def _coarsened_joint(
    treatment: np.ndarray,
    outcome: np.ndarray,
    *,
    treatment_disc: DiscretizedVariable | None,
    outcome_disc: DiscretizedVariable | None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    if treatment_disc is None:
        t_levels = _ordered_levels(treatment)
        t_idx = np.zeros(len(treatment), dtype=int)
        for i, value in enumerate(t_levels):
            t_idx[np.isclose(treatment, value, atol=1e-9)] = i
        t_labels = t_levels
    else:
        t_levels = np.arange(treatment_disc.n_bins, dtype=float)
        t_idx = np.digitize(
            np.asarray(treatment, dtype=float), np.asarray(treatment_disc.edges)[1:-1], right=True
        )
        t_labels = np.asarray(treatment_disc.bin_mid, dtype=float)

    if outcome_disc is None:
        y_levels = _ordered_levels(outcome)
        y_idx = np.zeros(len(outcome), dtype=int)
        for j, value in enumerate(y_levels):
            y_idx[np.isclose(outcome, value, atol=1e-9)] = j
        y_lower = y_levels
        y_upper = y_levels
    else:
        y_levels = np.arange(outcome_disc.n_bins, dtype=float)
        y_idx = np.digitize(
            np.asarray(outcome, dtype=float), np.asarray(outcome_disc.edges)[1:-1], right=True
        )
        y_lower = np.asarray(outcome_disc.bin_lower, dtype=float)
        y_upper = np.asarray(outcome_disc.bin_upper, dtype=float)

    joint = np.zeros((len(t_levels), len(y_levels)), dtype=float)
    total = float(max(len(treatment), 1))
    for i in range(len(t_levels)):
        for j in range(len(y_levels)):
            joint[i, j] = float(np.sum((t_idx == i) & (y_idx == j))) / total
    return (
        _normalize_probability_table(joint),
        np.asarray(t_labels, dtype=float),
        np.asarray(y_levels, dtype=float),
        y_lower,
        y_upper,
    )


def _exact_no_assumption_bounds(
    treatment: np.ndarray,
    outcome: np.ndarray,
    *,
    max_cardinality: int,
    monotone: bool = False,
    target_treatment: float = 1.0,
    reference_treatment: float = 0.0,
) -> tuple[PartialIdentificationResult, dict[str, Any]] | None:
    observed = _exact_joint_from_arrays(
        treatment,
        outcome,
        max_cardinality=max_cardinality,
    )
    if observed is None:
        return None

    joint, t_levels, y_levels = observed
    target_idx = int(np.argmin(np.abs(t_levels - target_treatment)))
    reference_idx = int(np.argmin(np.abs(t_levels - reference_treatment)))
    lp = _solve_response_lp(
        joint,
        t_levels,
        y_levels,
        monotone=monotone,
        target_index=target_idx,
        reference_index=reference_idx,
    )
    result = PartialIdentificationResult(
        method=BoundMethod.GENERAL_LP_BOUNDS,
        lower_bound=lp.lower,
        upper_bound=lp.upper,
        confidence=0.95 if lp.status == "optimal" else 0.6,
        assumptions_used=[
            "response_function_lp",
            "exact_discrete_support",
            *(["monotone_treatment_response"] if monotone else ["no_assumptions_on_selection"]),
        ],
        display_label="Exact response-function LP bounds",
        bounds_type="sharp_lp",
        relaxation_gap=0.0,
        discretization_method="exact",
        n_bins_final=int(max(len(t_levels), len(y_levels))),
        discretization_converged=True,
        n_refinement_steps=0,
    )
    return result, {
        "solver_status": lp.status,
        "t_levels": tuple(float(v) for v in t_levels),
        "y_levels": tuple(float(v) for v in y_levels),
        "response_space_size": _response_space_size(len(t_levels), len(y_levels)),
        "dual_certificate_payload": lp.dual_certificate_payload,
    }


def _adaptive_grid_refinement(
    *,
    treatment: np.ndarray,
    outcome: np.ndarray,
    max_cardinality: int,
    monotone: bool = False,
    target_treatment: float = 1.0,
    reference_treatment: float = 0.0,
    initial_bins: int = 10,
    max_bins: int = 100,
    convergence_tol: float = 0.01,
) -> tuple[PartialIdentificationResult, dict[str, Any]]:
    n_bins = max(2, initial_bins)
    previous_bounds: tuple[float, float] | None = None
    last_lp: _LPResult | None = None
    last_treatment_disc: DiscretizedVariable | None = None
    last_outcome_disc: DiscretizedVariable | None = None
    last_labels: np.ndarray | None = None
    step = 0

    while n_bins <= max_bins:
        step += 1
        treatment_disc = _coarsen_variable(
            treatment,
            variable="treatment",
            target_bins=min(max_cardinality, max(2, min(8, n_bins))),
        )
        outcome_disc = _coarsen_variable(
            outcome,
            variable="outcome",
            target_bins=min(max(2, n_bins), max_bins),
        )
        joint, t_labels, y_levels, y_lower, y_upper = _coarsened_joint(
            treatment,
            outcome,
            treatment_disc=treatment_disc,
            outcome_disc=outcome_disc,
        )
        if len(t_labels) < 2 or len(y_levels) < 2:
            raise RuntimeError(
                "outer approximation requires at least two treatment and outcome support points"
            )

        target_idx = int(np.argmin(np.abs(t_labels - target_treatment)))
        reference_idx = int(np.argmin(np.abs(t_labels - reference_treatment)))
        lp = _solve_response_lp(
            joint,
            t_labels,
            y_levels,
            y_lower=y_lower,
            y_upper=y_upper,
            monotone=monotone,
            target_index=target_idx,
            reference_index=reference_idx,
        )

        current_bounds = (lp.lower, lp.upper)
        if previous_bounds is not None:
            delta = max(
                abs(current_bounds[0] - previous_bounds[0]),
                abs(current_bounds[1] - previous_bounds[1]),
            )
            if delta < convergence_tol:
                result = PartialIdentificationResult(
                    method=BoundMethod.GENERAL_LP_BOUNDS,
                    lower_bound=lp.lower,
                    upper_bound=lp.upper,
                    confidence=0.7 if lp.status == "optimal" else 0.45,
                    assumptions_used=[
                        "response_function_outer_relaxation",
                        "adaptive_refinement",
                        *(
                            ["treatment_quantization"]
                            if treatment_disc is not None
                            else ["exact_treatment_support"]
                        ),
                        *(
                            ["outcome_quantization"]
                            if outcome_disc is not None
                            else ["exact_outcome_support"]
                        ),
                        *(
                            ["monotone_treatment_response"]
                            if monotone
                            else ["no_assumptions_on_selection"]
                        ),
                    ],
                    display_label="Adaptive outer-approximation bounds",
                    bounds_type="relaxed_polynomial",
                    relaxation_gap=float(delta),
                    discretization_method="adaptive",
                    n_bins_final=int(
                        max(
                            outcome_disc.n_bins if outcome_disc is not None else len(y_levels),
                            treatment_disc.n_bins if treatment_disc is not None else len(t_labels),
                        )
                    ),
                    discretization_converged=True,
                    n_refinement_steps=step,
                )
                return result, {
                    "solver_status": lp.status,
                    "treatment_discretization": None
                    if treatment_disc is None
                    else treatment_disc.model_dump(mode="json"),
                    "outcome_discretization": None
                    if outcome_disc is None
                    else outcome_disc.model_dump(mode="json"),
                    "previous_bounds": previous_bounds,
                    "response_space_size": _response_space_size(len(t_labels), len(y_levels)),
                }

        previous_bounds = current_bounds
        last_lp = lp
        last_treatment_disc = treatment_disc
        last_outcome_disc = outcome_disc
        last_labels = t_labels
        if n_bins == max_bins:
            break
        n_bins = min(max_bins, n_bins * 2)

    if last_lp is None:
        raise RuntimeError("adaptive refinement failed to produce a result")
    last_label_count = 0 if last_labels is None else len(last_labels)
    result = PartialIdentificationResult(
        method=BoundMethod.GENERAL_LP_BOUNDS,
        lower_bound=last_lp.lower,
        upper_bound=last_lp.upper,
        confidence=0.6 if last_lp.status == "optimal" else 0.35,
        assumptions_used=[
            "response_function_outer_relaxation",
            "adaptive_refinement",
            *(
                ["treatment_quantization"]
                if last_treatment_disc is not None
                else ["exact_treatment_support"]
            ),
            *(
                ["outcome_quantization"]
                if last_outcome_disc is not None
                else ["exact_outcome_support"]
            ),
            *(["monotone_treatment_response"] if monotone else ["no_assumptions_on_selection"]),
        ],
        display_label="Adaptive outer-approximation bounds",
        bounds_type="relaxed_polynomial",
        relaxation_gap=None,
        discretization_method="adaptive",
        n_bins_final=int(
            max(
                last_outcome_disc.n_bins if last_outcome_disc is not None else 0,
                last_treatment_disc.n_bins if last_treatment_disc is not None else last_label_count,
            )
        ),
        discretization_converged=False,
        n_refinement_steps=step,
    )
    return result, {
        "solver_status": last_lp.status,
        "treatment_discretization": None
        if last_treatment_disc is None
        else last_treatment_disc.model_dump(mode="json"),
        "outcome_discretization": None
        if last_outcome_disc is None
        else last_outcome_disc.model_dump(mode="json"),
        "previous_bounds": previous_bounds,
        "response_space_size": _response_space_size(
            int(
                last_treatment_disc.n_bins if last_treatment_disc is not None else last_label_count
            ),
            int(last_outcome_disc.n_bins if last_outcome_disc is not None else 0),
        ),
    }


def _delegate_to_iv_bounds(
    *,
    treatment: np.ndarray,
    outcome: np.ndarray,
    instrument: np.ndarray,
    target_treatment: float,
    reference_treatment: float,
) -> tuple[PartialIdentificationResult | None, dict[str, Any]]:
    from polisyos.foundry.methods.catalog.causal.bounds import (
        BalkePearlBoundsEstimator,
        GeneralBalkePearlBoundsEstimator,
    )

    state = {"outcome": outcome, "treatment": treatment, "instrument": instrument}
    t_levels = _ordered_levels(treatment)
    y_levels = _ordered_levels(outcome)
    if t_levels.size < 2 or y_levels.size < 2:
        return None, {}
    is_binary = (
        t_levels.size <= 2 and y_levels.size <= 2 and _looks_discrete(instrument, max_levels=2)
    )
    if is_binary:
        out = BalkePearlBoundsEstimator.pure_step(state, {"clip_probs": True})
    else:
        out = GeneralBalkePearlBoundsEstimator.pure_step(
            state,
            {
                "treatment_target": int(round(target_treatment)),
                "treatment_ref": int(round(reference_treatment)),
                "max_response_fns": _MAX_EXACT_RESPONSE_TYPES,
            },
        )
    pid = out.get("result", {}).get("partial_id_result")
    if pid is None:
        return None, {}
    result = PartialIdentificationResult.model_validate(pid)
    metadata: dict[str, Any] = {}
    solver_status = out.get("result", {}).get("solver_status")
    if solver_status is not None:
        metadata["solver_status"] = str(solver_status)
    certificate_payload = out.get("result", {}).get("dual_certificate_payload")
    if isinstance(certificate_payload, dict):
        metadata["dual_certificate_payload"] = certificate_payload
    return (
        result.model_copy(
            update={
                "bounds_type": "sharp_lp",
                "relaxation_gap": 0.0,
                "discretization_method": "instrument_exact",
                "n_bins_final": int(max(t_levels.size, y_levels.size)),
                "discretization_converged": True,
                "n_refinement_steps": 0,
            }
        ),
        metadata,
    )


def auto_bounds_with_metadata(
    outcome: np.ndarray,
    treatment: np.ndarray,
    *,
    instrument: np.ndarray | None = None,
    target_treatment: float = 1.0,
    reference_treatment: float = 0.0,
    constraints: Mapping[str, Any] | None = None,
    max_cardinality: int = 8,
    initial_bins: int = 10,
    max_bins: int = 100,
    convergence_tol: float = 0.01,
) -> tuple[PartialIdentificationResult, dict[str, Any]]:
    """Compute partial-identification bounds with exact and conservative relaxed paths.

    The exact path solves a response-function LP whenever the observed support is
    genuinely discrete and the response-function space remains tractable.
    Harder discrete and continuous cases use adaptive coarsening plus
    interval-valued objectives, which is an outer approximation and is labelled
    accordingly in the returned metadata.
    """

    y = _finite_values(np.asarray(outcome, dtype=float))
    t = _finite_values(np.asarray(treatment, dtype=float))
    if y.size == 0 or t.size == 0 or y.size != t.size:
        raise ValueError(
            "outcome and treatment must be same-length arrays with finite observations"
        )
    z = None if instrument is None else _finite_values(np.asarray(instrument, dtype=float))
    if z is not None and z.size != y.size:
        raise ValueError("instrument must match outcome/treatment length")

    monotone = bool((constraints or {}).get("monotone") or (constraints or {}).get("mtr"))

    if z is not None:
        delegated, delegated_metadata = _delegate_to_iv_bounds(
            treatment=t,
            outcome=y,
            instrument=z,
            target_treatment=target_treatment,
            reference_treatment=reference_treatment,
        )
        if delegated is not None:
            return delegated, delegated_metadata

    exact = _exact_no_assumption_bounds(
        treatment=t,
        outcome=y,
        max_cardinality=max_cardinality,
        monotone=monotone,
        target_treatment=target_treatment,
        reference_treatment=reference_treatment,
    )
    if exact is not None:
        return exact

    relaxed, diagnostics = _adaptive_grid_refinement(
        treatment=t,
        outcome=y,
        max_cardinality=max_cardinality,
        monotone=monotone,
        target_treatment=target_treatment,
        reference_treatment=reference_treatment,
        initial_bins=initial_bins,
        max_bins=max_bins,
        convergence_tol=convergence_tol,
    )
    return relaxed, diagnostics


def conditional_auto_bounds_with_metadata(
    outcome: np.ndarray,
    treatment: np.ndarray,
    conditioning: np.ndarray,
    *,
    target_treatment: float = 1.0,
    reference_treatment: float = 0.0,
    constraints: Mapping[str, Any] | None = None,
    max_cardinality: int = 8,
    max_strata: int = 12,
    min_stratum_n: int = 2,
) -> tuple[PartialIdentificationResult, dict[str, Any]] | None:
    """Compute certified bounds by conditioning on one finite stratum variable.

    The returned certificate is an aggregate of per-stratum exact LP
    certificates plus the deterministic weighted-sum rule.
    """

    y_raw = np.asarray(outcome, dtype=float).reshape(-1)
    t_raw = np.asarray(treatment, dtype=float).reshape(-1)
    w_raw = np.asarray(conditioning, dtype=float).reshape(-1)
    if y_raw.size != t_raw.size or y_raw.size != w_raw.size:
        raise ValueError("outcome, treatment, and conditioning must be same-length finite arrays")
    finite = np.isfinite(y_raw) & np.isfinite(t_raw) & np.isfinite(w_raw)
    y = y_raw[finite]
    t = t_raw[finite]
    w = w_raw[finite]
    if y.size == 0:
        raise ValueError("outcome, treatment, and conditioning must contain finite observations")
    strata = _ordered_levels(w)
    if strata.size < 2 or strata.size > max_strata:
        return None
    if not _looks_discrete(w, max_levels=max_strata):
        return None

    monotone = bool((constraints or {}).get("monotone") or (constraints or {}).get("mtr"))
    stratum_certs: list[StratifiedLPDualCertificate] = []
    lower = 0.0
    upper = 0.0
    total_n = float(len(w))
    for stratum in strata:
        mask = np.isclose(w, stratum, atol=1e-9)
        n_stratum = int(np.sum(mask))
        if n_stratum < min_stratum_n:
            return None
        exact = _exact_no_assumption_bounds(
            treatment=t[mask],
            outcome=y[mask],
            max_cardinality=max_cardinality,
            monotone=monotone,
            target_treatment=target_treatment,
            reference_treatment=reference_treatment,
        )
        if exact is None:
            return None
        result, metadata = exact
        payload = metadata.get("dual_certificate_payload")
        if not isinstance(payload, dict):
            return None
        certificate = BoundsDualCertificateBundle.model_validate(payload)
        weight = float(n_stratum / total_n)
        lower += weight * float(result.lower_bound)
        upper += weight * float(result.upper_bound)
        stratum_certs.append(
            StratifiedLPDualCertificate(
                stratum_id=str(float(stratum)),
                weight=weight,
                lower_bound=float(result.lower_bound),
                upper_bound=float(result.upper_bound),
                certificate=certificate,
            )
        )

    cert_bundle = StratifiedLPDualCertificateBundle(
        strata=tuple(stratum_certs),
        aggregate_lower_bound=float(lower),
        aggregate_upper_bound=float(upper),
    )
    result = PartialIdentificationResult(
        method=BoundMethod.GENERAL_LP_BOUNDS,
        lower_bound=float(lower),
        upper_bound=float(upper),
        confidence=0.95,
        assumptions_used=[
            "response_function_lp",
            "exact_discrete_support",
            "conditioning_weighted_aggregation",
            *(["monotone_treatment_response"] if monotone else ["no_assumptions_on_selection"]),
        ],
        display_label="Conditioned response-function LP bounds",
        bounds_type="sharp_lp",
        relaxation_gap=0.0,
        discretization_method="conditioning_exact",
        n_bins_final=int(strata.size),
        discretization_converged=True,
        n_refinement_steps=0,
    )
    return result, {
        "solver_status": "optimal",
        "conditioning_levels": tuple(float(value) for value in strata),
        "dual_certificate_payload": cert_bundle.model_dump(mode="json"),
    }


def auto_bounds(
    outcome: np.ndarray,
    treatment: np.ndarray,
    *,
    instrument: np.ndarray | None = None,
    target_treatment: float = 1.0,
    reference_treatment: float = 0.0,
    constraints: Mapping[str, Any] | None = None,
    max_cardinality: int = 8,
    initial_bins: int = 10,
    max_bins: int = 100,
    convergence_tol: float = 0.01,
) -> PartialIdentificationResult:
    """Compute partial-identification bounds with exact and conservative relaxed paths."""

    result, _ = auto_bounds_with_metadata(
        outcome=outcome,
        treatment=treatment,
        instrument=instrument,
        target_treatment=target_treatment,
        reference_treatment=reference_treatment,
        constraints=constraints,
        max_cardinality=max_cardinality,
        initial_bins=initial_bins,
        max_bins=max_bins,
        convergence_tol=convergence_tol,
    )
    return result


__all__ = [
    "DiscretizedVariable",
    "auto_bounds",
    "auto_bounds_with_metadata",
    "build_query_objective",
    "build_response_function_constraints",
    "conditional_auto_bounds_with_metadata",
]
