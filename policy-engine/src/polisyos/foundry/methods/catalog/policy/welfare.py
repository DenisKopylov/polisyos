"""Public policy welfare module API."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import Any, ClassVar, TypedDict

import numpy as np

from polisyos.core.canon import CanonSpec, fingerprint
from polisyos.core.observability import DeterminismTier
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
from polisyos.ir.analytics.phase4_dynamics import Phase4DynamicsGate


def _result_slot() -> frozenset[SlotSpec]:
    return frozenset({SlotSpec("result", SlotType.SCALAR, Unit("result", "json"))})


def _values_payload(state: Any, *, key: str = "values") -> np.ndarray:
    if isinstance(state, Mapping):
        values = state.get(key)
    else:
        values = state
    arr = np.asarray(values, dtype=float)
    if arr.ndim != 1:
        raise ValueError(f"{key} must be a 1D vector")
    if arr.size == 0:
        raise ValueError(f"{key} must not be empty")
    return arr


_SOCIAL_WEIGHT_CANON = CanonSpec(forbid_floats=False)
_SOCIAL_WEIGHT_MANIFEST_REGISTRY: dict[str, SocialWeightManifest] = {}


class SocialWeightManifest(TypedDict, total=False):
    ref: str
    method_fqn: str
    normalization: str
    basis: dict[str, Any]
    regime_ids: list[str]
    state_keys: list[str]
    support: dict[str, Any]
    diagnostics: dict[str, float | int | bool | None]
    coefficients: list[float]
    income_grid: list[float]
    weights_on_grid: list[float]
    normalization_weights: list[float]
    weights_checksum: str


class WelfareBundle(TypedDict, total=False):
    welfare: float
    welfare_delta: float
    components: dict[str, float]
    n_agents: int
    mean_utility: float
    social_weight_ref: str | None
    diagnostics: dict[str, Any]


def _extract_social_weight_ref(state: Any, params: Mapping[str, Any]) -> str | None:
    param_ref = params.get("social_weight_ref")
    if isinstance(param_ref, str) and param_ref.strip():
        return param_ref.strip()
    if isinstance(state, Mapping):
        state_ref = state.get("social_weight_ref")
        if isinstance(state_ref, str) and state_ref.strip():
            return state_ref.strip()
    return None


def _attach_social_weight_ref(
    result: Mapping[str, Any],
    *,
    state: Any,
    params: Mapping[str, Any],
) -> dict[str, Any]:
    payload = dict(result)
    payload["social_weight_ref"] = payload.get("social_weight_ref") or _extract_social_weight_ref(
        state, params
    )
    return payload


def _coerce_vector_from_mapping(state: Mapping[str, Any], key: str) -> np.ndarray:
    arr = np.asarray(state[key], dtype=float)
    if arr.ndim != 1:
        raise ValueError(f"{key} must be a 1D vector")
    if arr.size == 0:
        raise ValueError(f"{key} must not be empty")
    return arr


def _coerce_matrix_from_mapping(state: Mapping[str, Any], key: str) -> np.ndarray:
    arr = np.asarray(state[key], dtype=float)
    if arr.ndim != 2:
        raise ValueError(f"{key} must be a 2D matrix")
    if arr.shape[0] == 0 or arr.shape[1] == 0:
        raise ValueError(f"{key} must not be empty")
    return arr


def _coerce_state_features(state: Mapping[str, Any], n_cells: int) -> np.ndarray:
    if "state_features" not in state:
        return np.zeros((n_cells, 0), dtype=float)
    arr = np.asarray(state["state_features"], dtype=float)
    if arr.ndim == 1:
        arr = arr[:, None]
    if arr.ndim != 2 or arr.shape[0] != n_cells:
        raise ValueError("state_features must be a 2D matrix aligned with income_grid")
    return arr


def _collapse_elasticities(state: Mapping[str, Any], n_regimes: int, n_cells: int) -> np.ndarray:
    arr = np.asarray(state["elasticities"], dtype=float)
    if arr.ndim == 2:
        collapsed = arr
    elif arr.ndim == 3:
        collapsed = np.mean(arr, axis=-1)
    else:
        raise ValueError("elasticities must be a matrix or tensor")
    if collapsed.shape != (n_regimes, n_cells):
        raise ValueError("elasticities must align with marginal_tax_rates and density")
    return collapsed


def _normalize_density_rows(density: np.ndarray) -> np.ndarray:
    clipped = np.clip(np.asarray(density, dtype=float), 0.0, None)
    row_sums = np.sum(clipped, axis=1, keepdims=True)
    if np.any(row_sums <= 1.0e-12):
        raise ValueError("density rows must contain positive mass")
    return clipped / row_sums


def _difference_penalty(n_features: int) -> np.ndarray:
    if n_features <= 1:
        return np.zeros((0, n_features), dtype=float)
    diff = np.zeros((n_features - 1, n_features), dtype=float)
    for idx in range(n_features - 1):
        diff[idx, idx] = -1.0
        diff[idx, idx + 1] = 1.0
    return diff


def _normalized_income(income_grid: np.ndarray) -> np.ndarray:
    grid = np.asarray(income_grid, dtype=float)
    span = float(np.max(grid) - np.min(grid))
    if span <= 1.0e-12:
        return np.zeros_like(grid)
    return (grid - float(np.min(grid))) / span


def _income_basis(income_grid: np.ndarray, n_income_basis: int) -> np.ndarray:
    n_basis = max(1, int(n_income_basis))
    x = _normalized_income(income_grid)
    if n_basis == 1:
        return np.ones((income_grid.shape[0], 1), dtype=float)
    basis = [np.ones_like(x), x]
    internal = max(0, n_basis - 2)
    if internal > 0:
        knots = np.linspace(0.0, 1.0, internal + 2, dtype=float)[1:-1]
        basis.extend(np.maximum(x - knot, 0.0) for knot in knots)
    return np.column_stack(basis[:n_basis]).astype(float, copy=False)


def _raw_basis(
    income_grid: np.ndarray,
    state_features: np.ndarray,
    n_state_basis: int,
) -> tuple[np.ndarray, dict[str, Any]]:
    x = _normalized_income(income_grid)
    selected = state_features[:, : max(0, min(int(n_state_basis), state_features.shape[1]))]
    columns: list[np.ndarray] = [np.ones_like(x), x]
    if selected.size > 0:
        columns.extend(selected[:, idx] for idx in range(selected.shape[1]))
        columns.extend(x * selected[:, idx] for idx in range(selected.shape[1]))
    basis = np.column_stack(columns).astype(float, copy=False)
    return basis, {
        "family": "raw",
        "n_income_basis": 2,
        "n_state_basis": int(selected.shape[1]),
        "n_features": int(basis.shape[1]),
    }


def _tensor_spline_basis(
    income_grid: np.ndarray,
    state_features: np.ndarray,
    n_income_basis: int,
    n_state_basis: int,
) -> tuple[np.ndarray, dict[str, Any]]:
    income_basis = _income_basis(income_grid, n_income_basis)
    if state_features.size == 0 or n_state_basis <= 0:
        state_basis = np.ones((income_grid.shape[0], 1), dtype=float)
        state_terms = 0
    else:
        selected = state_features[:, : min(int(n_state_basis), state_features.shape[1])]
        centered = selected - np.mean(selected, axis=0, keepdims=True)
        scale = np.std(centered, axis=0, keepdims=True)
        scale = np.where(scale > 1.0e-12, scale, 1.0)
        state_basis = np.column_stack(
            [np.ones(income_grid.shape[0], dtype=float), centered / scale]
        )
        state_terms = int(selected.shape[1])

    columns = [
        income_basis[:, income_idx] * state_basis[:, state_idx]
        for income_idx in range(income_basis.shape[1])
        for state_idx in range(state_basis.shape[1])
    ]
    basis = np.column_stack(columns).astype(float, copy=False)
    return basis, {
        "family": "tensor_spline",
        "n_income_basis": int(income_basis.shape[1]),
        "n_state_basis": state_terms,
        "n_features": int(basis.shape[1]),
    }


def _resolve_basis_matrix(
    state: Mapping[str, Any],
    params: Mapping[str, Any],
    income_grid: np.ndarray,
    state_features: np.ndarray,
) -> tuple[np.ndarray, dict[str, Any]]:
    if "basis_matrix" in state:
        basis = np.asarray(state["basis_matrix"], dtype=float)
        if basis.ndim != 2 or basis.shape[0] != income_grid.shape[0]:
            raise ValueError("basis_matrix must be 2D with one row per income cell")
        return basis, {
            "family": "precomputed",
            "n_features": int(basis.shape[1]),
        }

    family = str(params.get("basis_family", "tensor_spline"))
    n_income_basis = int(params.get("n_income_basis", 6))
    n_state_basis = int(params.get("n_state_basis", 2))
    if family == "cell":
        basis = np.eye(income_grid.shape[0], dtype=float)
        return basis, {
            "family": "cell",
            "n_features": int(basis.shape[1]),
        }
    if family == "raw":
        return _raw_basis(income_grid, state_features, n_state_basis)
    if family == "tensor_spline":
        return _tensor_spline_basis(income_grid, state_features, n_income_basis, n_state_basis)
    raise ValueError(f"Unsupported basis_family: {family}")


def _normalization_row(
    basis: np.ndarray,
    mean_density: np.ndarray,
    *,
    normalization: str,
    reference_index: int,
) -> np.ndarray:
    if normalization == "mean_one":
        return mean_density @ basis
    if normalization == "reference_cell":
        return basis[reference_index]
    raise ValueError(f"Unsupported normalization: {normalization}")


def _solve_weighted_ridge(
    design: np.ndarray,
    target: np.ndarray,
    obs_weights: np.ndarray,
    *,
    ridge: float,
    smoothing: float,
    anchor: np.ndarray | None,
    normalization_row: np.ndarray,
    normalization_target: float = 1.0,
    normalization_penalty: float = 1.0e3,
) -> np.ndarray:
    n_features = design.shape[1]
    sqrt_w = np.sqrt(np.clip(obs_weights, 0.0, None))
    weighted_design = design * sqrt_w[:, None]
    weighted_target = target * sqrt_w
    gram = weighted_design.T @ weighted_design
    rhs = weighted_design.T @ weighted_target

    if smoothing > 0.0:
        diff = _difference_penalty(n_features)
        if diff.size > 0:
            gram += smoothing * (diff.T @ diff)
    if ridge > 0.0:
        gram += ridge * np.eye(n_features, dtype=float)
        if anchor is not None:
            rhs += ridge * np.asarray(anchor, dtype=float)

    gram += normalization_penalty * np.outer(normalization_row, normalization_row)
    rhs += normalization_penalty * normalization_target * normalization_row

    try:
        return np.linalg.solve(gram, rhs)
    except np.linalg.LinAlgError:
        solution, *_ = np.linalg.lstsq(gram, rhs, rcond=None)
        return solution


def _fit_surface(
    basis: np.ndarray,
    surface: np.ndarray,
    *,
    ridge: float,
    smoothing: float,
    mean_density: np.ndarray,
    normalization: str,
    reference_index: int,
    normalization_target: float = 1.0,
) -> np.ndarray:
    obs_weights = np.ones(surface.shape[0], dtype=float) / max(surface.shape[0], 1)
    return _solve_weighted_ridge(
        basis,
        surface,
        obs_weights,
        ridge=ridge,
        smoothing=smoothing,
        anchor=None,
        normalization_row=_normalization_row(
            basis,
            mean_density,
            normalization=normalization,
            reference_index=reference_index,
        ),
        normalization_target=normalization_target,
    )


def _normalize_surface(
    surface: np.ndarray,
    mean_density: np.ndarray,
    *,
    normalization: str,
    reference_index: int,
) -> np.ndarray:
    arr = np.asarray(surface, dtype=float)
    if normalization == "reference_cell":
        scale = float(arr[reference_index])
    elif normalization == "mean_one":
        scale = float(np.dot(mean_density, arr))
    else:
        raise ValueError(f"Unsupported normalization: {normalization}")
    if abs(scale) <= 1.0e-12:
        return np.ones_like(arr, dtype=float)
    return arr / scale


def _project_surface(
    surface: np.ndarray,
    income_grid: np.ndarray,
    *,
    positivity: bool,
    monotone_income: bool,
) -> np.ndarray:
    projected = np.asarray(surface, dtype=float).copy()
    if positivity:
        projected = np.clip(projected, 0.0, None)
    if monotone_income:
        order = np.argsort(np.asarray(income_grid, dtype=float))
        monotone = np.minimum.accumulate(projected[order])
        projected[order] = monotone
    if np.sum(projected) <= 1.0e-12:
        projected = np.ones_like(projected, dtype=float)
    return projected


def _stack_design(
    basis: np.ndarray,
    targets: np.ndarray,
    obs_weights: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    n_regimes = targets.shape[0]
    design = np.tile(basis, (n_regimes, 1))
    target = targets.reshape(-1)
    weights = obs_weights.reshape(-1)
    return design, target, weights


def _moment_norm(
    design: np.ndarray, beta: np.ndarray, target: np.ndarray, obs_weights: np.ndarray
) -> float:
    residual = design @ beta - target
    return float(np.sqrt(np.sum(obs_weights * residual * residual)))


def _pareto_like_parameter(income_grid: np.ndarray, mass: np.ndarray) -> np.ndarray:
    positive_income = np.maximum(np.asarray(income_grid, dtype=float), 1.0)
    tail_mass = np.cumsum(mass[::-1])[::-1]
    return positive_income * mass / np.maximum(tail_mass, 1.0e-8)


def _inverse_targets(
    income_grid: np.ndarray,
    marginal_tax_rates: np.ndarray,
    density: np.ndarray,
    elasticities: np.ndarray,
    *,
    target_clip: float,
) -> tuple[np.ndarray, np.ndarray]:
    normalized_density = _normalize_density_rows(density)
    clipped_tau = np.clip(np.asarray(marginal_tax_rates, dtype=float), -0.95, 0.95)
    targets = np.zeros_like(clipped_tau, dtype=float)
    for regime_idx in range(clipped_tau.shape[0]):
        pareto_like = _pareto_like_parameter(income_grid, normalized_density[regime_idx])
        denom = np.maximum(1.0 - clipped_tau[regime_idx], 1.0e-6)
        target = 1.0 - (pareto_like * elasticities[regime_idx] * clipped_tau[regime_idx]) / denom
        targets[regime_idx] = np.clip(target, -target_clip, target_clip)
    return targets, normalized_density


def _leave_one_regime_out_error(
    basis: np.ndarray,
    targets: np.ndarray,
    obs_weights: np.ndarray,
    *,
    ridge: float,
    smoothing: float,
    mean_density: np.ndarray,
    normalization: str,
    reference_index: int,
    positivity: bool,
    monotone_income: bool,
    income_grid: np.ndarray,
) -> float | None:
    n_regimes = targets.shape[0]
    if n_regimes <= 1:
        return None

    errors: list[float] = []
    for holdout_idx in range(n_regimes):
        keep = [idx for idx in range(n_regimes) if idx != holdout_idx]
        train_targets = targets[keep]
        train_weights = obs_weights[keep]
        design, target, weights = _stack_design(basis, train_targets, train_weights)
        beta = _solve_weighted_ridge(
            design,
            target,
            weights,
            ridge=ridge,
            smoothing=smoothing,
            anchor=None,
            normalization_row=_normalization_row(
                basis,
                mean_density,
                normalization=normalization,
                reference_index=reference_index,
            ),
        )
        holdout_surface = basis @ beta
        holdout_surface = _project_surface(
            holdout_surface,
            income_grid,
            positivity=positivity,
            monotone_income=monotone_income,
        )
        holdout_surface = _normalize_surface(
            holdout_surface,
            mean_density,
            normalization=normalization,
            reference_index=reference_index,
        )
        error = np.sqrt(
            np.sum(obs_weights[holdout_idx] * (holdout_surface - targets[holdout_idx]) ** 2)
        )
        errors.append(float(error))
    return float(np.mean(errors)) if errors else None


def _sensitivity_distance(
    basis: np.ndarray,
    targets: np.ndarray,
    obs_weights: np.ndarray,
    mean_density: np.ndarray,
    *,
    ridge: float,
    smoothing: float,
    normalization: str,
    reference_index: int,
    positivity: bool,
    monotone_income: bool,
    income_grid: np.ndarray,
    baseline_surface: np.ndarray,
) -> float:
    design, target, weights = _stack_design(basis, targets, obs_weights)
    beta = _solve_weighted_ridge(
        design,
        target,
        weights,
        ridge=ridge,
        smoothing=smoothing,
        anchor=None,
        normalization_row=_normalization_row(
            basis,
            mean_density,
            normalization=normalization,
            reference_index=reference_index,
        ),
    )
    surface = basis @ beta
    surface = _project_surface(
        surface,
        income_grid,
        positivity=positivity,
        monotone_income=monotone_income,
    )
    surface = _normalize_surface(
        surface,
        mean_density,
        normalization=normalization,
        reference_index=reference_index,
    )
    return float(np.mean(np.abs(surface - baseline_surface)))


def build_social_weight_ref(manifest: Mapping[str, Any]) -> str:
    manifest_payload = {key: value for key, value in manifest.items() if key != "ref"}
    method_fqn = str(
        manifest_payload.get("method_fqn")
        or "policy.welfare.state_dependent_inverse_social_weights@1.0.0"
    )
    if "@" in method_fqn:
        method_path, version = method_fqn.rsplit("@", 1)
    else:
        method_path, version = method_fqn, "1.0.0"
    method_name = method_path.split(".")[-1]
    digest = fingerprint(manifest_payload, canon_spec=_SOCIAL_WEIGHT_CANON)
    return f"swr://policy.welfare/{method_name}@{version}#{digest}"


def register_social_weight_manifest(manifest: Mapping[str, Any]) -> SocialWeightManifest:
    payload = deepcopy(dict(manifest))
    ref = str(payload.get("ref") or build_social_weight_ref(payload))
    payload["ref"] = ref
    registered = SocialWeightManifest(**payload)
    _SOCIAL_WEIGHT_MANIFEST_REGISTRY[ref] = deepcopy(registered)
    return deepcopy(registered)


def resolve_social_weight_manifest(ref: str | None) -> SocialWeightManifest | None:
    if ref is None or not str(ref).strip():
        return None
    manifest = _SOCIAL_WEIGHT_MANIFEST_REGISTRY.get(str(ref).strip())
    if manifest is None:
        return None
    return deepcopy(manifest)


def clear_social_weight_manifest_registry() -> None:
    _SOCIAL_WEIGHT_MANIFEST_REGISTRY.clear()


def resolve_social_weight_schedule(
    social_weight_ref: str | None,
    *,
    social_weight_manifest: Mapping[str, Any] | None = None,
) -> dict[str, Any] | None:
    resolved: SocialWeightManifest | None = None
    if social_weight_manifest is not None:
        resolved = register_social_weight_manifest(social_weight_manifest)
        if social_weight_ref is not None and str(social_weight_ref).strip():
            expected_ref = str(social_weight_ref).strip()
            if resolved["ref"] != expected_ref:
                raise ValueError(
                    "social_weight_ref does not match the provided social_weight_manifest"
                )
    elif social_weight_ref is not None:
        resolved = resolve_social_weight_manifest(social_weight_ref)

    if resolved is None:
        return None

    income_grid = np.asarray(resolved.get("income_grid", ()), dtype=float)
    weights_on_grid = np.asarray(resolved.get("weights_on_grid", ()), dtype=float)
    if income_grid.ndim != 1 or income_grid.size == 0:
        return None
    if weights_on_grid.shape != income_grid.shape:
        return None
    order = np.argsort(income_grid)
    return {
        "ref": resolved["ref"],
        "income_grid": income_grid[order],
        "weights_on_grid": weights_on_grid[order],
        "normalization": resolved.get("normalization", "mean_one"),
    }


# ---------------------------------------------------------------------------
# Cost-Benefit Analysis
# ---------------------------------------------------------------------------


@foundry_method(
    namespace="policy.welfare",
    version="1.0.0",
    tags={"policy", "welfare", "cost-benefit", "structural"},
)
class CostBenefitAnalysisEstimator:
    """Compare policy costs and monetized benefits in one welfare ledger."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="cost_benefit_analysis",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    "benefits", SlotType.VECTOR, Unit("currency", "amount"), shape=("n_periods",)
                ),
                SlotSpec(
                    "costs", SlotType.VECTOR, Unit("currency", "amount"), shape=("n_periods",)
                ),
            }
        ),
        output_slots=_result_slot(),
        parameters=(
            ParameterSpec(name="discount_rate", default=0.03, bounds=(0.0, 1.0)),
            ParameterSpec(name="shadow_price_factor", default=1.0, bounds=(0.0, None)),
        ),
        fidelity=FidelityLevel.MEDIUM,
        complexity=ComplexityClass.O_N,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Cost-benefit analysis with NPV, BCR, IRR, and payback period.",
        tags=frozenset({"policy", "welfare", "cost-benefit", "npv", "structural"}),
        citations=("Boardman, A. et al. (2017). Cost-Benefit Analysis: Concepts and Practice.",),
        equations={
            "npv": "NPV = sum_t (B_t - C_t) / (1 + r)^t",
            "bcr": "BCR = PV(benefits) / PV(costs)",
        },
        assumptions={
            "discount_rate": "Constant social discount rate across periods",
            "finite_periods": "Benefits and costs vectors must have same length",
        },
        determinism_tier=DeterminismTier.LIBRARY_DETERMINISTIC,
        required_deps=("numpy",),
        when_to_use="Policy evaluation comparing all monetized costs and benefits; NPV of intervention",
        output_interpretation="NPV>0 = policy benefits exceed costs. BCR>1 = every $1 spent returns >$1 in benefits.",
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        benefits = np.asarray(state["benefits"], dtype=float)
        costs = np.asarray(state["costs"], dtype=float)
        if benefits.shape != costs.shape:
            raise ValueError("benefits and costs must have same length")

        discount_rate = float(params.get("discount_rate", 0.03))
        shadow = float(params.get("shadow_price_factor", 1.0))

        n = len(benefits)
        phase4_verdict = Phase4DynamicsGate().enforce(
            horizon=n,
            regime_bundle=params.get("regime_shift_forecast_bundle")
            or state.get("regime_shift_forecast_bundle"),
            regime_bundle_ref=params.get("regime_shift_forecast_bundle_ref")
            or state.get("regime_shift_forecast_bundle_ref"),
            artifact_store=params.get("artifact_store") or state.get("artifact_store"),
            metadata={
                "surface": "foundry.policy.welfare.cost_benefit_analysis",
                "method": "policy.welfare.cost_benefit_analysis",
            },
        )
        periods = np.arange(n, dtype=float)
        discount_factors = 1.0 / (1.0 + discount_rate) ** periods

        pv_benefits = float(np.sum(benefits * shadow * discount_factors))
        pv_costs = float(np.sum(costs * discount_factors))
        npv = pv_benefits - pv_costs
        bcr = pv_benefits / max(pv_costs, 1e-12)

        # IRR via bisection
        net_flows = benefits * shadow - costs
        irr_info = _compute_irr_diagnostics(net_flows)
        irr = irr_info["irr"]

        # Payback period
        cumulative = np.cumsum(net_flows)
        payback_indices = np.where(cumulative >= 0)[0]
        payback_period = int(payback_indices[0]) if len(payback_indices) > 0 else None

        return {
            "result": _attach_social_weight_ref(
                {
                    "npv": npv,
                    "bcr": bcr,
                    "irr": irr,
                    "irr_bracket": irr_info["bracket"],
                    "irr_iterations": irr_info["iterations"],
                    "irr_bracket_width": irr_info["bracket_width"],
                    "irr_npv_bracket": irr_info["npv_bracket"],
                    "irr_npv_residual": irr_info["npv_residual"],
                    "payback_period": payback_period,
                    "pv_benefits": pv_benefits,
                    "pv_costs": pv_costs,
                    "discount_rate": discount_rate,
                    "n_periods": n,
                    "phase4_gate_verdict": phase4_verdict.model_dump(mode="json"),
                },
                state=state,
                params=params,
            )
        }


def _npv_at_rate(cash_flows: np.ndarray, rate: float) -> float:
    periods = np.arange(len(cash_flows), dtype=float)
    return float(np.sum(cash_flows / (1.0 + rate) ** periods))


def _compute_irr_diagnostics(
    cash_flows: np.ndarray,
    tol: float = 1e-8,
    max_iter: int = 200,
) -> dict[str, Any]:
    """Compute IRR via bisection and retain the terminal bracket."""

    lo, hi = -0.5, 5.0
    npv_lo = _npv_at_rate(cash_flows, lo)
    npv_hi = _npv_at_rate(cash_flows, hi)
    if npv_lo * npv_hi > 0:
        return {
            "irr": None,
            "bracket": None,
            "iterations": 0,
            "bracket_width": None,
            "npv_bracket": (float(npv_lo), float(npv_hi)),
            "npv_residual": None,
        }

    mid = float((lo + hi) / 2.0)
    npv_mid = _npv_at_rate(cash_flows, mid)
    iterations_run = 0
    for iteration in range(max_iter):
        mid = (lo + hi) / 2.0
        npv_mid = _npv_at_rate(cash_flows, mid)
        iterations_run = iteration + 1
        if abs(npv_mid) < tol:
            break
        if npv_lo * npv_mid < 0:
            hi = mid
            npv_hi = npv_mid
        else:
            lo = mid
            npv_lo = npv_mid
    irr = float((lo + hi) / 2.0)
    return {
        "irr": irr,
        "bracket": (float(lo), float(hi)),
        "iterations": iterations_run,
        "bracket_width": float(hi - lo),
        "npv_bracket": (float(npv_lo), float(npv_hi)),
        "npv_residual": float(npv_mid),
    }


def _compute_irr(cash_flows: np.ndarray, tol: float = 1e-8, max_iter: int = 200) -> float | None:
    """Compute IRR via bisection on NPV(r)=0."""
    return _compute_irr_diagnostics(cash_flows, tol=tol, max_iter=max_iter)["irr"]


# ---------------------------------------------------------------------------
# Cost-Effectiveness Analysis
# ---------------------------------------------------------------------------


@foundry_method(
    namespace="policy.welfare",
    version="1.0.0",
    tags={"policy", "welfare", "cost-effectiveness", "structural"},
)
class CostEffectivenessEstimator:
    """Compare policy costs against non-monetary outcome gains."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="cost_effectiveness",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    "costs", SlotType.VECTOR, Unit("currency", "amount"), shape=("n_alternatives",)
                ),
                SlotSpec(
                    "effects", SlotType.VECTOR, Unit("effect", "units"), shape=("n_alternatives",)
                ),
            }
        ),
        output_slots=_result_slot(),
        parameters=(ParameterSpec(name="baseline_index", default=0),),
        fidelity=FidelityLevel.MEDIUM,
        complexity=ComplexityClass.O_N,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Cost-effectiveness analysis with ICER and CE frontier.",
        tags=frozenset({"policy", "welfare", "cost-effectiveness", "icer", "structural"}),
        citations=(
            "Drummond, M. et al. (2015). Methods for the Economic Evaluation of Health Care Programmes.",
        ),
        equations={"icer": "ICER = (C_1 - C_0) / (E_1 - E_0)"},
        assumptions={"monotone_effects": "Higher effects are preferred"},
        determinism_tier=DeterminismTier.LIBRARY_DETERMINISTIC,
        required_deps=("numpy",),
        when_to_use="Health/education policy; non-monetizable outcomes; QALY, DALY comparisons",
        output_interpretation="Cost-per-unit-outcome (e.g., cost per QALY gained). Lower = more cost-effective.",
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        costs = np.asarray(state["costs"], dtype=float)
        effects = np.asarray(state["effects"], dtype=float)
        if costs.shape != effects.shape or costs.ndim != 1:
            raise ValueError("costs and effects must be 1D with same length")

        baseline = int(params.get("baseline_index", 0))
        n = len(costs)

        # ICERs relative to baseline
        delta_c = costs - costs[baseline]
        delta_e = effects - effects[baseline]
        icers = np.full(n, np.nan)
        for i in range(n):
            if i != baseline and abs(delta_e[i]) > 1e-12:
                icers[i] = delta_c[i] / delta_e[i]

        # CE frontier: sort by effect, compute incremental ICERs
        order = np.argsort(effects)
        frontier_indices: list[int] = [int(order[0])]
        for idx in order[1:]:
            while len(frontier_indices) > 1:
                prev = frontier_indices[-1]
                prev2 = frontier_indices[-2]
                icer_new = (costs[idx] - costs[prev]) / max(effects[idx] - effects[prev], 1e-12)
                icer_old = (costs[prev] - costs[prev2]) / max(effects[prev] - effects[prev2], 1e-12)
                if icer_new <= icer_old:
                    frontier_indices.pop()
                else:
                    break
            frontier_indices.append(int(idx))

        return {
            "result": _attach_social_weight_ref(
                {
                    "icers": [None if np.isnan(v) else float(v) for v in icers],
                    "frontier_indices": frontier_indices,
                    "costs": costs.tolist(),
                    "effects": effects.tolist(),
                    "baseline_index": baseline,
                },
                state=state,
                params=params,
            )
        }


# ---------------------------------------------------------------------------
# Social Welfare Functions
# ---------------------------------------------------------------------------


@foundry_method(
    namespace="policy.welfare",
    version="1.0.0",
    tags={"policy", "welfare", "swf", "utilitarian", "structural"},
)
class UtilitarianSWFEstimator:
    """Evaluate policies by aggregate utility or welfare gains."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="utilitarian_swf",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("values", SlotType.VECTOR, Unit("value", "amount"), shape=("n_agents",)),
            }
        ),
        output_slots=_result_slot(),
        parameters=(ParameterSpec(name="weights", default=None),),
        fidelity=FidelityLevel.MEDIUM,
        complexity=ComplexityClass.O_N,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Utilitarian social welfare function: W = sum of (weighted) utilities.",
        tags=frozenset({"policy", "welfare", "swf", "utilitarian", "structural"}),
        citations=(
            "Bentham, J. (1789). An Introduction to the Principles of Morals and Legislation.",
        ),
        equations={"swf": "W = sum_i w_i * u(x_i)"},
        assumptions={"additive": "Individual utilities are additively separable"},
        determinism_tier=DeterminismTier.LIBRARY_DETERMINISTIC,
        required_deps=("numpy",),
        when_to_use="Welfare economics evaluation; comparing distributional consequences of policies under different social preferences",
        output_interpretation="Social welfare value. Higher = better welfare outcome under chosen SWF.",
    )

    @staticmethod
    def pure_step(state: Any, params: Mapping[str, Any]) -> dict[str, Any]:
        values = _values_payload(state)
        weights_raw = params.get("weights")
        if weights_raw is not None:
            weights = np.asarray(weights_raw, dtype=float)
        else:
            weights = np.ones_like(values)
        welfare = float(np.sum(weights * values))
        return {
            "result": _attach_social_weight_ref(
                {
                    "welfare": welfare,
                    "mean_utility": float(np.mean(values)),
                    "n_agents": len(values),
                },
                state=state,
                params=params,
            )
        }


@foundry_method(
    namespace="policy.welfare",
    version="1.0.0",
    tags={"policy", "welfare", "swf", "rawlsian", "structural"},
)
class RawlsianSWFEstimator:
    """Evaluate policies by outcomes for the worst-off group under a Rawlsian rule."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="rawlsian_swf",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("values", SlotType.VECTOR, Unit("value", "amount"), shape=("n_agents",)),
            }
        ),
        output_slots=_result_slot(),
        parameters=(),
        fidelity=FidelityLevel.MEDIUM,
        complexity=ComplexityClass.O_N,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Rawlsian maximin social welfare function: W = min(u_i).",
        tags=frozenset({"policy", "welfare", "swf", "rawlsian", "maximin", "structural"}),
        citations=("Rawls, J. (1971). A Theory of Justice.",),
        equations={"swf": "W = min_i u(x_i)"},
        assumptions={"ordinal": "Only the worst-off individual matters"},
        determinism_tier=DeterminismTier.LIBRARY_DETERMINISTIC,
        required_deps=("numpy",),
        when_to_use="Welfare economics evaluation; comparing distributional consequences of policies under different social preferences",
        output_interpretation="Social welfare value. Higher = better welfare outcome under chosen SWF.",
    )

    @staticmethod
    def pure_step(state: Any, params: Mapping[str, Any]) -> dict[str, Any]:
        values = _values_payload(state)
        min_val = float(np.min(values))
        return {
            "result": _attach_social_weight_ref(
                {
                    "welfare": min_val,
                    "min_value": min_val,
                    "min_index": int(np.argmin(values)),
                    "n_agents": len(values),
                },
                state=state,
                params=params,
            )
        }


@foundry_method(
    namespace="policy.welfare",
    version="1.0.0",
    tags={"policy", "welfare", "swf", "atkinson", "structural"},
)
class AtkinsonSWFEstimator:
    """Evaluate policies with an Atkinson welfare function sensitive to inequality aversion."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="atkinson_swf",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("values", SlotType.VECTOR, Unit("value", "amount"), shape=("n_agents",)),
            }
        ),
        output_slots=_result_slot(),
        parameters=(ParameterSpec(name="epsilon", default=0.5, bounds=(0.0, 10.0)),),
        fidelity=FidelityLevel.MEDIUM,
        complexity=ComplexityClass.O_N,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Atkinson social welfare function with inequality aversion parameter.",
        tags=frozenset({"policy", "welfare", "swf", "atkinson", "structural"}),
        citations=("Atkinson, A.B. (1970). On the Measurement of Inequality.",),
        equations={
            "ede": "x_ede = (mean(x^(1-e)))^(1/(1-e)) for e != 1",
            "swf": "W = n * x_ede",
        },
        assumptions={"non_negative": "Values must be non-negative"},
        determinism_tier=DeterminismTier.LIBRARY_DETERMINISTIC,
        required_deps=("numpy",),
        when_to_use="Welfare economics evaluation; comparing distributional consequences of policies under different social preferences",
        output_interpretation="Social welfare value. Higher = better welfare outcome under chosen SWF.",
    )

    @staticmethod
    def pure_step(state: Any, params: Mapping[str, Any]) -> dict[str, Any]:
        values = _values_payload(state)
        if np.any(values < 0):
            raise ValueError("atkinson_swf requires non-negative values")
        epsilon = float(params.get("epsilon", 0.5))
        shifted = np.maximum(values, 1e-12)
        n = len(values)
        if abs(epsilon - 1.0) < 1e-9:
            ede = float(np.exp(np.mean(np.log(shifted))))
        else:
            ede = float(np.mean(shifted ** (1.0 - epsilon)) ** (1.0 / (1.0 - epsilon)))
        welfare = n * ede
        return {
            "result": _attach_social_weight_ref(
                {
                    "welfare": welfare,
                    "ede_income": ede,
                    "mean_income": float(np.mean(values)),
                    "epsilon": epsilon,
                    "n_agents": n,
                },
                state=state,
                params=params,
            )
        }


@foundry_method(
    namespace="policy.welfare",
    version="1.0.0",
    tags={"policy", "welfare", "swf", "sen", "structural"},
)
class SenCapabilityEstimator:
    """Evaluate policies against capability-oriented welfare dimensions."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="sen_capability",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("values", SlotType.VECTOR, Unit("value", "amount"), shape=("n_agents",)),
            }
        ),
        output_slots=_result_slot(),
        parameters=(),
        fidelity=FidelityLevel.MEDIUM,
        complexity=ComplexityClass.O_N,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Sen welfare index: W = mean * (1 - Gini).",
        tags=frozenset({"policy", "welfare", "swf", "sen", "capability", "structural"}),
        citations=("Sen, A. (1976). Real National Income. Review of Economic Studies.",),
        equations={"swf": "W = mu * (1 - G)"},
        assumptions={"non_negative": "Values must be non-negative"},
        determinism_tier=DeterminismTier.LIBRARY_DETERMINISTIC,
        required_deps=("numpy",),
        when_to_use="Welfare economics evaluation; comparing distributional consequences of policies under different social preferences",
        output_interpretation="Social welfare value. Higher = better welfare outcome under chosen SWF.",
    )

    @staticmethod
    def pure_step(state: Any, params: Mapping[str, Any]) -> dict[str, Any]:
        values = _values_payload(state)
        if np.any(values < 0):
            raise ValueError("sen_capability requires non-negative values")
        mean_val = float(np.mean(values))
        n = len(values)
        sorted_v = np.sort(values)
        if mean_val <= 0.0:
            gini = 0.0
        else:
            indices = np.arange(1, n + 1, dtype=float)
            gini = float(
                (2.0 * np.sum(indices * sorted_v) - (n + 1) * np.sum(sorted_v))
                / (n * np.sum(sorted_v))
            )
            gini = max(0.0, min(1.0, gini))
        welfare = mean_val * (1.0 - gini)
        return {
            "result": _attach_social_weight_ref(
                {
                    "welfare": welfare,
                    "mean": mean_val,
                    "gini": gini,
                    "n_agents": n,
                },
                state=state,
                params=params,
            )
        }


@foundry_method(
    namespace="policy.welfare",
    version="1.0.0",
    tags={"policy", "welfare", "inverse-optimum", "state-dependent", "frontier", "structural"},
)
class StateDependentInverseSocialWeightsEstimator:
    """Recover a state-dependent social weight surface from observed tax regimes."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="state_dependent_inverse_social_weights",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    "income_grid", SlotType.VECTOR, Unit("income", "amount"), shape=("n_cells",)
                ),
                SlotSpec(
                    "marginal_tax_rates",
                    SlotType.MATRIX,
                    Unit("tax", "rate"),
                    shape=("n_regimes", "n_cells"),
                ),
                SlotSpec(
                    "density",
                    SlotType.MATRIX,
                    Unit("probability", "mass"),
                    shape=("n_regimes", "n_cells"),
                ),
                SlotSpec(
                    "elasticities",
                    SlotType.TENSOR,
                    Unit("elasticity", "value"),
                    shape=("n_regimes", "n_cells", "n_elasticities"),
                ),
                SlotSpec(
                    "state_features",
                    SlotType.MATRIX,
                    Unit("state", "feature"),
                    shape=("n_cells", "n_state_features"),
                ),
            }
        ),
        output_slots=_result_slot(),
        parameters=(
            ParameterSpec("basis_family", default="tensor_spline"),
            ParameterSpec("n_income_basis", default=6),
            ParameterSpec("n_state_basis", default=2),
            ParameterSpec("normalization", default="mean_one"),
            ParameterSpec("reference_index", default=0),
            ParameterSpec("smoothing", default=1.0e-3, bounds=(0.0, None)),
            ParameterSpec("ridge", default=1.0e-6, bounds=(0.0, None)),
            ParameterSpec("max_iter", default=200, bounds=(1, 5000)),
            ParameterSpec("tol", default=1.0e-8, bounds=(1.0e-12, 1.0)),
            ParameterSpec("damping", default=0.5, bounds=(1.0e-4, 1.0)),
            ParameterSpec("positivity", default=True),
            ParameterSpec("monotone_income", default=False),
            ParameterSpec("solver_mode", default="batch"),
            ParameterSpec("forgetting_factor", default=1.0, bounds=(1.0e-6, 1.0)),
            ParameterSpec("elasticity_sensitivity", default=0.2, bounds=(0.0, 1.0)),
            ParameterSpec("target_clip", default=5.0, bounds=(1.0e-3, None)),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Inverse-optimum recovery of state-dependent generalized social welfare weights under observed tax regimes.",
        tags=frozenset(
            {"policy", "welfare", "inverse-optimum", "state-dependent", "frontier", "structural"}
        ),
        citations=(
            "Saez, E. (2001). Using elasticities to derive optimal income tax rates.",
            "Saez, E. & Stantcheva, S. (2016). Generalized social marginal welfare weights for optimal tax theory.",
            "Hendren, N. (2020). Measuring welfare in policy analysis.",
        ),
        when_to_use="Need an implied social-weight surface that rationalizes observed tax/transfer schedules across multiple regimes without solving a full Mirrlees model.",
        when_not_to_use="Need exact general-equilibrium welfare weights, unrestricted preference recovery, or a regime-specific surface that is allowed to drift freely over time.",
        typical_min_obs=4,
        output_interpretation="weights_on_grid is the recovered normalized social-weight schedule; social_weight_ref is a stable manifest handle for provenance and downstream propagation.",
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        income_grid = _coerce_vector_from_mapping(state, "income_grid")
        marginal_tax_rates = _coerce_matrix_from_mapping(state, "marginal_tax_rates")
        density = _coerce_matrix_from_mapping(state, "density")
        if marginal_tax_rates.shape != density.shape:
            raise ValueError("marginal_tax_rates and density must have the same shape")

        n_regimes, n_cells = marginal_tax_rates.shape
        if income_grid.shape[0] != n_cells:
            raise ValueError("income_grid must align with marginal_tax_rates columns")

        elasticities = _collapse_elasticities(state, n_regimes, n_cells)
        state_features = _coerce_state_features(state, n_cells)
        basis, basis_spec = _resolve_basis_matrix(state, params, income_grid, state_features)

        if basis.ndim != 2 or basis.shape[0] != n_cells:
            raise ValueError("basis matrix must be 2D with one row per income cell")

        normalization = str(params.get("normalization", "mean_one"))
        reference_index = int(params.get("reference_index", 0))
        if not 0 <= reference_index < n_cells:
            raise ValueError("reference_index must refer to a valid income cell")

        ridge = float(params.get("ridge", 1.0e-6))
        smoothing = float(params.get("smoothing", 1.0e-3))
        max_iter = int(params.get("max_iter", 200))
        tol = float(params.get("tol", 1.0e-8))
        damping = float(params.get("damping", 0.5))
        positivity = bool(params.get("positivity", True))
        monotone_income = bool(params.get("monotone_income", False))
        solver_mode = str(params.get("solver_mode", "batch")).strip().lower()
        forgetting_factor = float(params.get("forgetting_factor", 1.0))
        elasticity_sensitivity = float(params.get("elasticity_sensitivity", 0.2))
        target_clip = float(params.get("target_clip", 5.0))

        targets, normalized_density = _inverse_targets(
            income_grid,
            marginal_tax_rates,
            density,
            elasticities,
            target_clip=target_clip,
        )
        mean_density = np.mean(normalized_density, axis=0)
        mean_density = mean_density / np.maximum(np.sum(mean_density), 1.0e-12)

        design, target_vec, obs_weights = _stack_design(basis, targets, normalized_density)
        norm_row = _normalization_row(
            basis,
            mean_density,
            normalization=normalization,
            reference_index=reference_index,
        )
        n_features = basis.shape[1]

        beta_prev_raw = state.get("previous_coefficients")
        if beta_prev_raw is not None:
            beta = np.asarray(beta_prev_raw, dtype=float)
            if beta.shape != (n_features,):
                raise ValueError("previous_coefficients must align with the basis dimension")
        else:
            beta = _fit_surface(
                basis,
                np.ones(n_cells, dtype=float),
                ridge=max(ridge, 1.0e-8),
                smoothing=smoothing,
                mean_density=mean_density,
                normalization=normalization,
                reference_index=reference_index,
            )

        iterations = 0
        converged_iter = False
        precision_matrix: np.ndarray | None = None

        if solver_mode == "online":
            precision_raw = state.get("previous_precision")
            if precision_raw is None:
                precision = np.eye(n_features, dtype=float) / max(ridge, 1.0e-3)
            else:
                precision = np.asarray(precision_raw, dtype=float)
                if precision.shape != (n_features, n_features):
                    raise ValueError("previous_precision must be square with basis dimension")
            beta_online = beta.copy()
            sqrt_w = np.sqrt(np.clip(obs_weights, 0.0, None))
            for row_idx in range(design.shape[0]):
                x_row = design[row_idx] * sqrt_w[row_idx]
                y_row = target_vec[row_idx] * sqrt_w[row_idx]
                denom = forgetting_factor + float(x_row @ precision @ x_row)
                if denom <= 1.0e-12:
                    continue
                gain = (precision @ x_row) / denom
                beta_online = beta_online + gain * (y_row - float(x_row @ beta_online))
                precision = (precision - np.outer(gain, x_row) @ precision) / max(
                    forgetting_factor, 1.0e-6
                )
            precision_matrix = precision
            beta = beta_online
            iterations = 1
            converged_iter = True
        else:
            previous_norm = np.inf
            for iteration_idx in range(max_iter):
                beta_raw = _solve_weighted_ridge(
                    design,
                    target_vec,
                    obs_weights,
                    ridge=ridge,
                    smoothing=smoothing,
                    anchor=beta,
                    normalization_row=norm_row,
                )
                surface_raw = basis @ beta_raw
                surface_projected = _project_surface(
                    surface_raw,
                    income_grid,
                    positivity=positivity,
                    monotone_income=monotone_income,
                )
                surface_projected = _normalize_surface(
                    surface_projected,
                    mean_density,
                    normalization=normalization,
                    reference_index=reference_index,
                )
                beta_projected = _fit_surface(
                    basis,
                    surface_projected,
                    ridge=max(ridge, 1.0e-8),
                    smoothing=smoothing,
                    mean_density=mean_density,
                    normalization=normalization,
                    reference_index=reference_index,
                )
                beta_next = (1.0 - damping) * beta + damping * beta_projected
                surface_next = basis @ beta_next
                surface_next = _project_surface(
                    surface_next,
                    income_grid,
                    positivity=positivity,
                    monotone_income=monotone_income,
                )
                surface_next = _normalize_surface(
                    surface_next,
                    mean_density,
                    normalization=normalization,
                    reference_index=reference_index,
                )
                beta_next = _fit_surface(
                    basis,
                    surface_next,
                    ridge=max(ridge, 1.0e-8),
                    smoothing=smoothing,
                    mean_density=mean_density,
                    normalization=normalization,
                    reference_index=reference_index,
                )
                current_norm = _moment_norm(design, beta_next, target_vec, obs_weights)
                iterations = iteration_idx + 1
                if np.max(np.abs(beta_next - beta)) < tol and current_norm <= previous_norm + tol:
                    beta = beta_next
                    converged_iter = True
                    break
                beta = beta_next
                previous_norm = current_norm

        weights_on_grid = basis @ beta
        weights_on_grid = _project_surface(
            weights_on_grid,
            income_grid,
            positivity=positivity,
            monotone_income=monotone_income,
        )
        weights_on_grid = _normalize_surface(
            weights_on_grid,
            mean_density,
            normalization=normalization,
            reference_index=reference_index,
        )
        beta = _fit_surface(
            basis,
            weights_on_grid,
            ridge=max(ridge, 1.0e-8),
            smoothing=smoothing,
            mean_density=mean_density,
            normalization=normalization,
            reference_index=reference_index,
        )

        residual_matrix = targets - weights_on_grid[None, :]
        regime_ids_raw = state.get("regime_ids")
        if regime_ids_raw is None:
            regime_ids = [f"r{idx}" for idx in range(n_regimes)]
        else:
            regime_ids = [str(item) for item in regime_ids_raw]
            if len(regime_ids) != n_regimes:
                raise ValueError("regime_ids must align with the number of regimes")

        state_keys_raw = state.get("state_keys")
        if state_keys_raw is None:
            state_keys = [f"state_{idx}" for idx in range(state_features.shape[1])]
        else:
            state_keys = [str(item) for item in state_keys_raw]

        regime_residual_norms = {
            regime_ids[idx]: float(
                np.sqrt(np.sum(normalized_density[idx] * residual_matrix[idx] ** 2))
            )
            for idx in range(n_regimes)
        }

        shape_violations = 0
        if positivity:
            shape_violations += int(np.sum(weights_on_grid < -1.0e-9))
        if monotone_income:
            order = np.argsort(income_grid)
            shape_violations += int(np.sum(np.diff(weights_on_grid[order]) > 1.0e-8))

        normalized_design = design * np.sqrt(np.clip(obs_weights, 0.0, None))[:, None]
        stacked_identification = np.vstack([normalized_design, norm_row[None, :]])
        singular_values = np.linalg.svd(stacked_identification, compute_uv=False)
        identified_rank = int(np.linalg.matrix_rank(stacked_identification))
        condition_number = (
            float(np.inf)
            if singular_values.size == 0
            else float(singular_values[0] / max(singular_values[-1], 1.0e-12))
        )
        rank_deficient = identified_rank < basis.shape[1]
        normalization_error = float(
            abs(np.dot(mean_density, weights_on_grid) - 1.0)
            if normalization == "mean_one"
            else abs(weights_on_grid[reference_index] - 1.0)
        )
        max_abs_residual = float(np.max(np.abs(residual_matrix)))
        moment_norm = float(np.sqrt(np.sum(normalized_density * residual_matrix * residual_matrix)))
        leave_one_regime_out_error = _leave_one_regime_out_error(
            basis,
            targets,
            normalized_density,
            ridge=ridge,
            smoothing=smoothing,
            mean_density=mean_density,
            normalization=normalization,
            reference_index=reference_index,
            positivity=positivity,
            monotone_income=monotone_income,
            income_grid=income_grid,
        )

        sensitivity_low_targets, _ = _inverse_targets(
            income_grid,
            marginal_tax_rates,
            density,
            elasticities * max(1.0 - elasticity_sensitivity, 0.0),
            target_clip=target_clip,
        )
        sensitivity_high_targets, _ = _inverse_targets(
            income_grid,
            marginal_tax_rates,
            density,
            elasticities * (1.0 + elasticity_sensitivity),
            target_clip=target_clip,
        )
        sensitivity_to_elasticity_low = _sensitivity_distance(
            basis,
            sensitivity_low_targets,
            normalized_density,
            mean_density,
            ridge=ridge,
            smoothing=smoothing,
            normalization=normalization,
            reference_index=reference_index,
            positivity=positivity,
            monotone_income=monotone_income,
            income_grid=income_grid,
            baseline_surface=weights_on_grid,
        )
        sensitivity_to_elasticity_high = _sensitivity_distance(
            basis,
            sensitivity_high_targets,
            normalized_density,
            mean_density,
            ridge=ridge,
            smoothing=smoothing,
            normalization=normalization,
            reference_index=reference_index,
            positivity=positivity,
            monotone_income=monotone_income,
            income_grid=income_grid,
            baseline_surface=weights_on_grid,
        )

        diagnostics: dict[str, float | int | bool | None] = {
            "identified_rank": identified_rank,
            "condition_number": condition_number,
            "moment_norm": moment_norm,
            "max_abs_residual": max_abs_residual,
            "leave_one_regime_out_error": leave_one_regime_out_error,
            "shape_violations": shape_violations,
            "normalization_error": normalization_error,
            "sensitivity_to_elasticity_low": sensitivity_to_elasticity_low,
            "sensitivity_to_elasticity_high": sensitivity_to_elasticity_high,
            "converged": bool(converged_iter and not rank_deficient),
            "iterations": iterations,
            "rank_deficient": rank_deficient,
        }

        manifest: SocialWeightManifest = {
            "method_fqn": "policy.welfare.state_dependent_inverse_social_weights@1.0.0",
            "normalization": normalization,
            "basis": basis_spec,
            "regime_ids": regime_ids,
            "state_keys": state_keys,
            "support": {
                "n_regimes": n_regimes,
                "n_cells": n_cells,
                "income_min": float(np.min(income_grid)),
                "income_max": float(np.max(income_grid)),
            },
            "coefficients": [float(value) for value in beta],
            "income_grid": [float(value) for value in income_grid],
            "weights_on_grid": [float(value) for value in weights_on_grid],
            "normalization_weights": [float(value) for value in mean_density],
            "weights_checksum": fingerprint(
                [float(value) for value in weights_on_grid],
                canon_spec=_SOCIAL_WEIGHT_CANON,
            ),
            "diagnostics": diagnostics,
        }
        social_weight_ref = build_social_weight_ref(manifest)
        manifest["ref"] = social_weight_ref
        manifest = register_social_weight_manifest(manifest)
        social_weight_ref = manifest["ref"]

        result: dict[str, Any] = {
            "social_weight_ref": social_weight_ref,
            "weights_on_grid": [float(value) for value in weights_on_grid],
            "coefficients": [float(value) for value in beta],
            "normalization": normalization,
            "identified_rank": identified_rank,
            "condition_number": condition_number,
            "converged": bool(converged_iter and not rank_deficient),
            "iterations": iterations,
            "rank_deficient": rank_deficient,
            "solver_mode": solver_mode,
            "regime_residual_norms": regime_residual_norms,
            "moment_norm": moment_norm,
            "max_abs_residual": max_abs_residual,
            "leave_one_regime_out_error": leave_one_regime_out_error,
            "shape_violations": shape_violations,
            "normalization_error": normalization_error,
            "sensitivity_to_elasticity_low": sensitivity_to_elasticity_low,
            "sensitivity_to_elasticity_high": sensitivity_to_elasticity_high,
            "manifest": manifest,
        }
        if precision_matrix is not None:
            result["precision_matrix"] = np.asarray(precision_matrix, dtype=float).tolist()
        return {"result": result}


__all__ = [
    "AtkinsonSWFEstimator",
    "CostBenefitAnalysisEstimator",
    "CostEffectivenessEstimator",
    "RawlsianSWFEstimator",
    "SenCapabilityEstimator",
    "SocialWeightManifest",
    "StateDependentInverseSocialWeightsEstimator",
    "UtilitarianSWFEstimator",
    "WelfareBundle",
    "build_social_weight_ref",
    "clear_social_weight_manifest_registry",
    "register_social_weight_manifest",
    "resolve_social_weight_manifest",
    "resolve_social_weight_schedule",
]
