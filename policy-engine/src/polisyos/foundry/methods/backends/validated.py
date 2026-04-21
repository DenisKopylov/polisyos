"""Validated numerics helpers for boundary-sensitive Foundry method outputs."""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping, Protocol

import numpy as np

from polisyos.foundry.methods.base import MethodSignature
from polisyos.ir.analytics.uncertainty import (
    DistributionFamily,
    IntervalSemantics,
    PropagationMethod,
    UncertaintyEnvelope,
    UncertaintySource,
)

VALIDATED_EXECUTION_PARAM_NAMES = frozenset({"validated_mode", "validated_policy"})


class ValidatedMode(str, Enum):
    """Execution policy for validated numerics certification."""

    OFF = "off"
    AUTO = "auto"
    REQUIRED = "required"


class ValidatedStatus(str, Enum):
    """High-level certification status emitted by validated kernels."""

    RIGOROUS_ENCLOSURE = "rigorous_enclosure"
    RIGOROUS_UNIQUE_ROOT = "rigorous_unique_root"
    INDETERMINATE = "indeterminate"
    NOT_APPLICABLE = "not_applicable"


class ValidatedMethodFamily(str, Enum):
    """Validated numerics family used to build the certificate."""

    INTERVAL = "interval"
    BALL = "ball"
    TAYLOR = "taylor"
    CHEBYSHEV = "chebyshev"


ValidatedPayload = float | tuple[float, ...] | None


@dataclass(frozen=True, slots=True)
class ValidatedExecutionPolicy:
    """Execution-only validated numerics policy parsed from dispatch params."""

    mode: ValidatedMode = ValidatedMode.OFF
    policy: str | None = None


@dataclass(frozen=True, slots=True)
class ValidatedBound:
    """Proof-carrying numerical enclosure for one method output quantity."""

    status: ValidatedStatus
    quantity: str
    lower: ValidatedPayload
    upper: ValidatedPayload
    contains_point_estimate: bool | None
    method_family: ValidatedMethodFamily
    engine: str
    precision_bits: int | None = None
    polynomial_order: int | None = None
    subdivisions: int | None = None
    witness: Mapping[str, Any] = field(default_factory=dict)
    cost: Mapping[str, Any] = field(default_factory=dict)
    semantics: Mapping[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "quantity": self.quantity,
            "lower": _json_safe(self.lower),
            "upper": _json_safe(self.upper),
            "contains_point_estimate": self.contains_point_estimate,
            "method_family": self.method_family.value,
            "engine": self.engine,
            "precision_bits": self.precision_bits,
            "polynomial_order": self.polynomial_order,
            "subdivisions": self.subdivisions,
            "witness": _json_safe(dict(self.witness)),
            "cost": _json_safe(dict(self.cost)),
            "semantics": _json_safe(dict(self.semantics)),
        }


class ValidatedCertifier(Protocol):
    """Runtime certifier for one boundary-sensitive method."""

    def should_certify(
        self,
        *,
        state: Any,
        params: Mapping[str, Any],
        output: Any,
    ) -> bool:
        ...

    def certify(
        self,
        *,
        signature: MethodSignature,
        state: Any,
        params: Mapping[str, Any],
        output: Any,
    ) -> ValidatedBound:
        ...


def split_validated_execution_params(
    params: Mapping[str, Any] | None,
) -> tuple[dict[str, Any], ValidatedExecutionPolicy]:
    """Split execution-only validated params from method params."""

    payload = dict(params or {})
    raw_mode = payload.pop("validated_mode", ValidatedMode.OFF.value)
    raw_policy = payload.pop("validated_policy", None)
    return payload, ValidatedExecutionPolicy(
        mode=_coerce_validated_mode(raw_mode),
        policy=(None if raw_policy is None else str(raw_policy)),
    )


def maybe_certify(
    *,
    signature: MethodSignature,
    state: Any,
    params: Mapping[str, Any],
    output: Any,
    execution_policy: ValidatedExecutionPolicy,
) -> ValidatedBound | None:
    """Run a registered certifier when policy demands it."""

    if execution_policy.mode is ValidatedMode.OFF:
        return None

    certifier = _CERTIFIERS.get(signature.fqn)
    if certifier is None:
        if execution_policy.mode is ValidatedMode.REQUIRED:
            return ValidatedBound(
                status=ValidatedStatus.NOT_APPLICABLE,
                quantity=signature.fqn,
                lower=None,
                upper=None,
                contains_point_estimate=None,
                method_family=ValidatedMethodFamily.INTERVAL,
                engine="unregistered",
                semantics={
                    "validated_mode": execution_policy.mode.value,
                    "validated_policy": execution_policy.policy,
                    "reason": "no_certifier_registered",
                },
            )
        return None

    if (
        execution_policy.mode is ValidatedMode.AUTO
        and not certifier.should_certify(state=state, params=params, output=output)
    ):
        return None

    try:
        bound = certifier.certify(
            signature=signature,
            state=state,
            params=params,
            output=output,
        )
    except Exception as exc:
        if execution_policy.mode is not ValidatedMode.REQUIRED:
            return None
        return ValidatedBound(
            status=ValidatedStatus.INDETERMINATE,
            quantity=signature.fqn,
            lower=None,
            upper=None,
            contains_point_estimate=None,
            method_family=ValidatedMethodFamily.INTERVAL,
            engine="binary64.nextafter",
            semantics={
                "validated_mode": execution_policy.mode.value,
                "validated_policy": execution_policy.policy,
                "reason": "certifier_failed",
                "error_type": type(exc).__name__,
                "error_message": str(exc),
            },
        )

    semantics = dict(bound.semantics)
    semantics.setdefault("validated_mode", execution_policy.mode.value)
    if execution_policy.policy is not None:
        semantics.setdefault("validated_policy", execution_policy.policy)
    return ValidatedBound(
        status=bound.status,
        quantity=bound.quantity,
        lower=bound.lower,
        upper=bound.upper,
        contains_point_estimate=bound.contains_point_estimate,
        method_family=bound.method_family,
        engine=bound.engine,
        precision_bits=bound.precision_bits,
        polynomial_order=bound.polynomial_order,
        subdivisions=bound.subdivisions,
        witness=bound.witness,
        cost=bound.cost,
        semantics=semantics,
    )


def validated_bound_to_envelopes(
    bound: ValidatedBound,
) -> tuple[UncertaintyEnvelope, ...]:
    """Project a rigorous scalar/vector bound into deterministic envelopes."""

    if bound.status not in {
        ValidatedStatus.RIGOROUS_ENCLOSURE,
        ValidatedStatus.RIGOROUS_UNIQUE_ROOT,
    }:
        return ()

    lower = _payload_to_tuple(bound.lower)
    upper = _payload_to_tuple(bound.upper)
    if lower is None or upper is None or len(lower) != len(upper):
        return ()

    points = _payload_to_tuple(bound.witness.get("point_estimate"))
    envelopes: list[UncertaintyEnvelope] = []
    gate_eligible = bool(bound.semantics.get("gate_eligible", True))
    component_count = len(lower)
    for idx, (lo, hi) in enumerate(zip(lower, upper)):
        if not (math.isfinite(lo) and math.isfinite(hi)) or lo > hi:
            return ()

        if points is not None and idx < len(points):
            point = float(points[idx])
        else:
            point = float((lo + hi) / 2.0)
        if not (lo <= point <= hi):
            point = float((lo + hi) / 2.0)

        metadata = {
            "validated_quantity": bound.quantity,
            "validated_status": bound.status.value,
            "validated_engine": bound.engine,
            "validated_method_family": bound.method_family.value,
            "validated_component_index": idx,
            "validated_component_count": component_count,
            "validated_witness": _json_safe(dict(bound.witness)),
            "validated_cost": _json_safe(dict(bound.cost)),
            "validated_semantics": _json_safe(dict(bound.semantics)),
            "validated_source_kind": "validated_numerics",
        }
        envelopes.append(
            UncertaintyEnvelope(
                point_estimate=point,
                confidence_interval=(float(lo), float(hi)),
                confidence_level=None,
                distribution_family=DistributionFamily.UNKNOWN,
                source=UncertaintySource.MANUAL,
                propagation_method=PropagationMethod.NONE,
                interval_semantics=IntervalSemantics.DETERMINISTIC_BOUNDS,
                is_heuristic_ci=False,
                gate_eligible=gate_eligible,
                metadata=metadata,
            )
        )
    return tuple(envelopes)


def _coerce_validated_mode(value: Any) -> ValidatedMode:
    if isinstance(value, ValidatedMode):
        return value
    try:
        return ValidatedMode(str(value).strip().lower())
    except ValueError as exc:
        raise ValueError(
            "validated_mode must be one of {'off', 'auto', 'required'}"
        ) from exc


def _json_safe(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, np.generic):
        return value.item()
    return value


def _payload_to_tuple(value: Any) -> tuple[float, ...] | None:
    if value is None:
        return None
    if isinstance(value, np.ndarray):
        return tuple(float(item) for item in value.reshape(-1).tolist())
    if isinstance(value, (list, tuple)):
        return tuple(float(item) for item in value)
    return (float(value),)


def _resolve_declared_params(
    signature: MethodSignature,
    params: Mapping[str, Any],
) -> dict[str, Any]:
    resolved: dict[str, Any] = {}
    for param in signature.parameters:
        resolved[param.name] = params.get(param.name, param.default)
    return resolved


def _extract_result_mapping(output: Any) -> Mapping[str, Any] | None:
    if isinstance(output, Mapping):
        result = output.get("result")
        if isinstance(result, Mapping):
            return result
        if result is not None and hasattr(result, "items"):
            return dict(result.items())
    return None


def _extract_income(state: Any) -> np.ndarray:
    if isinstance(state, Mapping):
        income = state.get("market_income")
    else:
        income = getattr(state, "market_income", None)
    if income is None:
        raise ValueError("state does not expose market_income")
    arr = np.asarray(income, dtype=float)
    if arr.ndim != 1:
        raise ValueError("market_income must be a 1D vector")
    if not np.all(np.isfinite(arr)):
        raise ValueError("market_income must be finite")
    return arr


def _as_finite_vector(value: Any, *, name: str) -> np.ndarray:
    arr = np.asarray(value, dtype=float)
    if arr.ndim != 1:
        raise ValueError(f"{name} must be a 1D vector")
    if not np.all(np.isfinite(arr)):
        raise ValueError(f"{name} must be finite")
    return arr


def _as_finite_matrix(value: Any, *, name: str) -> np.ndarray:
    arr = np.asarray(value, dtype=float)
    if arr.ndim != 2:
        raise ValueError(f"{name} must be a 2D matrix")
    if not np.all(np.isfinite(arr)):
        raise ValueError(f"{name} must be finite")
    return arr


def _nextafter_interval(values: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    arr = np.asarray(values, dtype=float)
    return (
        np.nextafter(arr, -np.inf),
        np.nextafter(arr, np.inf),
    )


def _scalar_interval(value: float) -> tuple[float, float]:
    scalar = float(value)
    return (
        math.nextafter(scalar, -math.inf),
        math.nextafter(scalar, math.inf),
    )


def _interval_add(
    a_lo: np.ndarray | float,
    a_hi: np.ndarray | float,
    b_lo: np.ndarray | float,
    b_hi: np.ndarray | float,
) -> tuple[np.ndarray, np.ndarray]:
    return (
        np.nextafter(np.asarray(a_lo) + np.asarray(b_lo), -np.inf),
        np.nextafter(np.asarray(a_hi) + np.asarray(b_hi), np.inf),
    )


def _interval_sub(
    a_lo: np.ndarray | float,
    a_hi: np.ndarray | float,
    b_lo: np.ndarray | float,
    b_hi: np.ndarray | float,
) -> tuple[np.ndarray, np.ndarray]:
    return (
        np.nextafter(np.asarray(a_lo) - np.asarray(b_hi), -np.inf),
        np.nextafter(np.asarray(a_hi) - np.asarray(b_lo), np.inf),
    )


def _interval_mul(
    a_lo: np.ndarray | float,
    a_hi: np.ndarray | float,
    b_lo: np.ndarray | float,
    b_hi: np.ndarray | float,
) -> tuple[np.ndarray, np.ndarray]:
    left_lo = np.asarray(a_lo, dtype=float)
    left_hi = np.asarray(a_hi, dtype=float)
    right_lo = np.asarray(b_lo, dtype=float)
    right_hi = np.asarray(b_hi, dtype=float)
    candidates = np.stack(
        (
            left_lo * right_lo,
            left_lo * right_hi,
            left_hi * right_lo,
            left_hi * right_hi,
        ),
        axis=0,
    )
    return (
        np.nextafter(np.min(candidates, axis=0), -np.inf),
        np.nextafter(np.max(candidates, axis=0), np.inf),
    )


def _interval_sum(
    lower: np.ndarray,
    upper: np.ndarray,
    *,
    axis: int | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    return (
        np.nextafter(np.sum(lower, axis=axis), -np.inf),
        np.nextafter(np.sum(upper, axis=axis), np.inf),
    )


def _matrix_vector_product_interval(
    matrix: np.ndarray,
    vector: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    matrix_lo, matrix_hi = _nextafter_interval(matrix)
    vector_lo, vector_hi = _nextafter_interval(vector)
    products_lo, products_hi = _interval_mul(
        matrix_lo,
        matrix_hi,
        vector_lo[None, :],
        vector_hi[None, :],
    )
    return _interval_sum(products_lo, products_hi, axis=1)


def _project_feasible_point(
    x_in: np.ndarray,
    matrix: np.ndarray,
    rhs: np.ndarray,
) -> np.ndarray:
    x_out = x_in.copy()
    violations = matrix @ x_out - rhs
    for idx in range(len(rhs)):
        if violations[idx] > 0:
            row = matrix[idx]
            norm_sq = float(row @ row)
            if norm_sq > 1e-12:
                x_out -= (violations[idx] / norm_sq) * row
    return np.maximum(x_out, 0.0)


def _extract_runtime_marginal_rates(output: Any) -> np.ndarray | None:
    if not isinstance(output, Mapping):
        return None
    result = output.get("result")
    if result is not None and hasattr(result, "marginal_tax_rate"):
        return np.asarray(getattr(result, "marginal_tax_rate"), dtype=float)
    if isinstance(result, Mapping) and "marginal_tax_rate" in result:
        return np.asarray(result["marginal_tax_rate"], dtype=float)
    if "marginal_tax_rate" in output:
        return np.asarray(output["marginal_tax_rate"], dtype=float)
    return None


def _extract_bilevel_problem(
    state: Mapping[str, Any],
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    c_u = _as_finite_vector(state["c_upper"], name="c_upper")
    c_l = _as_finite_vector(state["c_lower"], name="c_lower")
    A_u = _as_finite_matrix(state["A_upper"], name="A_upper")
    b_u = _as_finite_vector(state["b_upper"], name="b_upper")
    A_l = _as_finite_matrix(state["A_lower"], name="A_lower")
    b_l = _as_finite_vector(state["b_lower"], name="b_lower")
    n = c_u.size
    if c_l.size != n:
        raise ValueError("c_upper and c_lower must have identical length")
    if A_u.shape[1] != n or A_l.shape[1] != n:
        raise ValueError("constraint matrices must align with variable dimension")
    if A_u.shape[0] != b_u.size or A_l.shape[0] != b_l.size:
        raise ValueError("constraint matrices and rhs vectors must align")
    return c_u, c_l, A_u, b_u, A_l, b_l


def _extract_welfare_problem(
    state: Mapping[str, Any],
) -> tuple[np.ndarray, np.ndarray]:
    benefits = _as_finite_vector(state["benefits"], name="benefits")
    costs = _as_finite_vector(state["costs"], name="costs")
    if benefits.shape != costs.shape:
        raise ValueError("benefits and costs must have same length")
    return benefits, costs


def _discount_factor_interval_from_bounds(
    rate_lower: float,
    rate_upper: float,
    periods: np.ndarray,
    *,
    exponent_shift: int = 0,
) -> tuple[np.ndarray, np.ndarray]:
    base_lower = 1.0 + float(rate_lower)
    base_upper = 1.0 + float(rate_upper)
    if base_lower <= 0.0:
        raise ValueError("discount rate interval crosses the singularity at -1")
    lower = np.ones(periods.shape, dtype=float)
    upper = np.ones(periods.shape, dtype=float)
    exponents = periods + int(exponent_shift)
    mask = exponents > 0
    if np.any(mask):
        lower[mask] = np.nextafter(base_upper ** (-exponents[mask]), -np.inf)
        upper[mask] = np.nextafter(base_lower ** (-exponents[mask]), np.inf)
    return lower, upper


def _discount_factor_interval(
    discount_rate: float,
    n_periods: int,
    *,
    exponent_shift: int = 0,
) -> tuple[np.ndarray, np.ndarray]:
    rate_lower, rate_upper = _scalar_interval(discount_rate)
    periods = np.arange(n_periods, dtype=int)
    return _discount_factor_interval_from_bounds(
        rate_lower,
        rate_upper,
        periods,
        exponent_shift=exponent_shift,
    )


def _discounted_sum_interval(
    values_lower: np.ndarray,
    values_upper: np.ndarray,
    discount_lower: np.ndarray,
    discount_upper: np.ndarray,
) -> tuple[float, float]:
    term_lower, term_upper = _interval_mul(
        values_lower,
        values_upper,
        discount_lower,
        discount_upper,
    )
    total_lower, total_upper = _interval_sum(term_lower, term_upper)
    return float(total_lower), float(total_upper)


def _npv_interval_at_rate_bounds(
    cash_flows: np.ndarray,
    rate_lower: float,
    rate_upper: float,
) -> tuple[float, float]:
    cash_lower, cash_upper = _nextafter_interval(cash_flows)
    discount_lower, discount_upper = _discount_factor_interval_from_bounds(
        rate_lower,
        rate_upper,
        np.arange(cash_flows.size, dtype=int),
    )
    return _discounted_sum_interval(
        cash_lower,
        cash_upper,
        discount_lower,
        discount_upper,
    )


def _npv_derivative_interval_at_rate_bounds(
    cash_flows: np.ndarray,
    rate_lower: float,
    rate_upper: float,
) -> tuple[float, float]:
    periods = np.arange(cash_flows.size, dtype=float)
    coeffs = -(periods * cash_flows)
    coeffs_lower, coeffs_upper = _nextafter_interval(coeffs)
    discount_lower, discount_upper = _discount_factor_interval_from_bounds(
        rate_lower,
        rate_upper,
        np.arange(cash_flows.size, dtype=int),
        exponent_shift=1,
    )
    return _discounted_sum_interval(
        coeffs_lower,
        coeffs_upper,
        discount_lower,
        discount_upper,
    )


class _TaxBenefitMarginalRateCertifier:
    """Certify tax-rate branch selection around statutory thresholds."""

    quantity = "marginal_tax_rate"

    def should_certify(
        self,
        *,
        state: Any,
        params: Mapping[str, Any],
        output: Any,
    ) -> bool:
        del output
        income = _extract_income(state)
        allowance = float(params.get("allowance", 10000.0))
        threshold_1 = float(params.get("threshold_1", 25000.0))
        threshold_2 = float(params.get("threshold_2", 60000.0))
        boundaries = np.asarray([allowance, threshold_1, threshold_2], dtype=float)
        if not np.all(np.isfinite(boundaries)):
            return True
        scale = np.maximum(
            np.abs(np.spacing(income[:, None])),
            np.abs(np.spacing(boundaries[None, :])),
        )
        distance = np.abs(income[:, None] - boundaries[None, :])
        return bool(np.any(distance <= (4.0 * scale)))

    def certify(
        self,
        *,
        signature: MethodSignature,
        state: Any,
        params: Mapping[str, Any],
        output: Any,
    ) -> ValidatedBound:
        resolved = _resolve_declared_params(signature, params)
        income = _extract_income(state)
        allowance = float(resolved["allowance"])
        threshold_1 = float(resolved["threshold_1"])
        threshold_2 = float(resolved["threshold_2"])
        rate_1 = float(resolved["rate_1"])
        rate_2 = float(resolved["rate_2"])
        rate_3 = float(resolved["rate_3"])

        if not np.all(
            np.isfinite(
                [allowance, threshold_1, threshold_2, rate_1, rate_2, rate_3]
            )
        ):
            return ValidatedBound(
                status=ValidatedStatus.INDETERMINATE,
                quantity=self.quantity,
                lower=None,
                upper=None,
                contains_point_estimate=None,
                method_family=ValidatedMethodFamily.INTERVAL,
                engine="binary64.nextafter",
                semantics={"reason": "non_finite_policy_parameters"},
            )

        if not (allowance <= threshold_1 <= threshold_2):
            return ValidatedBound(
                status=ValidatedStatus.INDETERMINATE,
                quantity=self.quantity,
                lower=None,
                upper=None,
                contains_point_estimate=None,
                method_family=ValidatedMethodFamily.INTERVAL,
                engine="binary64.nextafter",
                semantics={
                    "reason": "non_monotone_thresholds",
                    "allowance": allowance,
                    "threshold_1": threshold_1,
                    "threshold_2": threshold_2,
                },
            )

        income_lower, income_upper = _nextafter_interval(income)
        allowance_lower, allowance_upper = _scalar_interval(allowance)
        threshold_1_lower, threshold_1_upper = _scalar_interval(threshold_1)
        threshold_2_lower, threshold_2_upper = _scalar_interval(threshold_2)

        possible_zero = income_lower <= allowance_upper
        possible_rate_1 = (income_upper > allowance_lower) & (
            income_lower <= threshold_1_upper
        )
        possible_rate_2 = (income_upper > threshold_1_lower) & (
            income_lower <= threshold_2_upper
        )
        possible_rate_3 = income_upper > threshold_2_lower

        lower = np.full(income.shape, np.inf, dtype=float)
        upper = np.full(income.shape, -np.inf, dtype=float)
        for rate, mask in (
            (0.0, possible_zero),
            (rate_1, possible_rate_1),
            (rate_2, possible_rate_2),
            (rate_3, possible_rate_3),
        ):
            lower = np.where(mask, np.minimum(lower, rate), lower)
            upper = np.where(mask, np.maximum(upper, rate), upper)

        if np.any(~np.isfinite(lower)) or np.any(~np.isfinite(upper)):
            return ValidatedBound(
                status=ValidatedStatus.INDETERMINATE,
                quantity=self.quantity,
                lower=None,
                upper=None,
                contains_point_estimate=None,
                method_family=ValidatedMethodFamily.INTERVAL,
                engine="binary64.nextafter",
                semantics={"reason": "failed_to_construct_enclosure"},
            )

        runtime_point = _extract_runtime_marginal_rates(output)
        if runtime_point is None:
            runtime_point = np.where(
                income <= allowance,
                0.0,
                np.where(
                    income <= threshold_1,
                    rate_1,
                    np.where(income <= threshold_2, rate_2, rate_3),
                ),
            )
        runtime_point = np.asarray(runtime_point, dtype=float)
        if runtime_point.shape != income.shape:
            raise ValueError("runtime marginal tax rates do not align with market_income")

        ambiguous_mask = lower < upper
        point_inside = bool(np.all((runtime_point >= lower) & (runtime_point <= upper)))
        return ValidatedBound(
            status=ValidatedStatus.RIGOROUS_ENCLOSURE,
            quantity=self.quantity,
            lower=tuple(float(value) for value in lower.tolist()),
            upper=tuple(float(value) for value in upper.tolist()),
            contains_point_estimate=point_inside,
            method_family=ValidatedMethodFamily.INTERVAL,
            engine="binary64.nextafter",
            precision_bits=53,
            witness={
                "point_estimate": tuple(float(value) for value in runtime_point.tolist()),
                "ambiguous_count": int(np.sum(ambiguous_mask)),
                "ambiguous_indices_preview": [
                    int(index) for index in np.flatnonzero(ambiguous_mask)[:32]
                ],
                "certified_unique_count": int(np.sum(~ambiguous_mask)),
                "policy_thresholds": {
                    "allowance": [allowance_lower, allowance_upper],
                    "threshold_1": [threshold_1_lower, threshold_1_upper],
                    "threshold_2": [threshold_2_lower, threshold_2_upper],
                },
            },
            cost={
                "n_obs": int(income.size),
                "kernel": "tax_threshold_branch_certifier",
            },
            semantics={
                "branch_certification": True,
                "interval_semantics": "deterministic_rigorous_bound",
                "is_heuristic_ci": False,
                "gate_eligible": True,
            },
        )


class _BilevelResidualCertifier:
    """Certify the residual and feasibility of a bilevel fixed-point candidate."""

    quantity = "bilevel_fixed_point_residual_inf"
    auto_residual_tolerance = 1e-6
    auto_slack_tolerance = 1e-5
    residual_tolerance = 1e-8
    feasibility_tolerance = 1e-9

    def should_certify(
        self,
        *,
        state: Any,
        params: Mapping[str, Any],
        output: Any,
    ) -> bool:
        del state, params
        result = _extract_result_mapping(output)
        if result is None:
            return True
        try:
            residual = float(result.get("fixed_point_residual_inf", math.inf))
            min_upper = float(result.get("min_upper_slack", math.inf))
            min_lower = float(result.get("min_lower_slack", math.inf))
        except (TypeError, ValueError):
            return True
        if not np.all(np.isfinite([residual, min_upper, min_lower])):
            return True
        return (
            residual <= self.auto_residual_tolerance
            or min(min_upper, min_lower) <= self.auto_slack_tolerance
        )

    def certify(
        self,
        *,
        signature: MethodSignature,
        state: Any,
        params: Mapping[str, Any],
        output: Any,
    ) -> ValidatedBound:
        del signature
        result = _extract_result_mapping(output)
        if result is None:
            raise ValueError("bilevel output does not expose a result mapping")
        c_u, c_l, A_u, b_u, A_l, b_l = _extract_bilevel_problem(state)
        solution = _as_finite_vector(result["solution"], name="solution")
        if solution.size != c_u.size:
            raise ValueError("solution dimension does not match bilevel problem")
        step_size = float(params.get("step_size", 0.1))
        if not math.isfinite(step_size) or step_size <= 0.0:
            return ValidatedBound(
                status=ValidatedStatus.INDETERMINATE,
                quantity=self.quantity,
                lower=None,
                upper=None,
                contains_point_estimate=None,
                method_family=ValidatedMethodFamily.INTERVAL,
                engine="binary64.nextafter",
                semantics={"reason": "invalid_step_size"},
            )

        x_lower = _project_feasible_point(solution - step_size * c_l, A_l, b_l)
        x_next = _project_feasible_point(x_lower - step_size * c_u, A_u, b_u)
        residual_vector = x_next - solution
        residual_vector_lower, residual_vector_upper = _nextafter_interval(residual_vector)
        residual_norm = float(np.max(np.abs(residual_vector)))
        residual_norm_lower, residual_norm_upper = _scalar_interval(residual_norm)

        upper_dot_lower, upper_dot_upper = _matrix_vector_product_interval(A_u, solution)
        lower_dot_lower, lower_dot_upper = _matrix_vector_product_interval(A_l, solution)
        b_u_lower, b_u_upper = _nextafter_interval(b_u)
        b_l_lower, b_l_upper = _nextafter_interval(b_l)
        upper_slack_lower, upper_slack_upper = _interval_sub(
            b_u_lower,
            b_u_upper,
            upper_dot_lower,
            upper_dot_upper,
        )
        lower_slack_lower, lower_slack_upper = _interval_sub(
            b_l_lower,
            b_l_upper,
            lower_dot_lower,
            lower_dot_upper,
        )
        min_upper_slack = float(np.min(upper_slack_lower))
        min_lower_slack = float(np.min(lower_slack_lower))
        converged = bool(result.get("converged", False))
        iterations_run = int(result.get("iterations_run", 0))

        certified = (
            residual_norm_upper <= self.residual_tolerance
            and min_upper_slack >= -self.feasibility_tolerance
            and min_lower_slack >= -self.feasibility_tolerance
        )
        return ValidatedBound(
            status=(
                ValidatedStatus.RIGOROUS_ENCLOSURE
                if certified
                else ValidatedStatus.INDETERMINATE
            ),
            quantity=self.quantity,
            lower=float(residual_norm_lower),
            upper=float(residual_norm_upper),
            contains_point_estimate=(
                residual_norm_lower <= residual_norm <= residual_norm_upper
            ),
            method_family=ValidatedMethodFamily.INTERVAL,
            engine="binary64.nextafter",
            precision_bits=53,
            witness={
                "point_estimate": residual_norm,
                "solution": solution.tolist(),
                "fixed_point_residual_interval": {
                    "lower": residual_vector_lower.tolist(),
                    "upper": residual_vector_upper.tolist(),
                },
                "upper_constraint_slack_interval": {
                    "lower": upper_slack_lower.tolist(),
                    "upper": upper_slack_upper.tolist(),
                },
                "lower_constraint_slack_interval": {
                    "lower": lower_slack_lower.tolist(),
                    "upper": lower_slack_upper.tolist(),
                },
                "converged": converged,
                "iterations_run": iterations_run,
                "residual_tolerance": self.residual_tolerance,
                "feasibility_tolerance": self.feasibility_tolerance,
            },
            cost={
                "n_vars": int(solution.size),
                "n_upper_constraints": int(b_u.size),
                "n_lower_constraints": int(b_l.size),
                "kernel": "bilevel_residual_certifier",
            },
            semantics={
                "fixed_point_residual_certification": True,
                "interval_semantics": "deterministic_rigorous_bound",
                "is_heuristic_ci": False,
                "gate_eligible": certified,
            },
        )


class _CostBenefitAnalysisCertifier:
    """Certify discounted welfare sums and expose a root witness for IRR."""

    quantity = "net_present_value"

    def should_certify(
        self,
        *,
        state: Any,
        params: Mapping[str, Any],
        output: Any,
    ) -> bool:
        del state, params
        result = _extract_result_mapping(output)
        if result is None:
            return True
        try:
            irr = result.get("irr")
            npv = float(result.get("npv", math.inf))
            pv_benefits = float(result.get("pv_benefits", 0.0))
            pv_costs = float(result.get("pv_costs", 0.0))
        except (TypeError, ValueError):
            return True
        scale = max(abs(pv_benefits) + abs(pv_costs), 1.0)
        near_boundary = abs(npv) <= (1e-6 * scale)
        return irr is not None or near_boundary

    def certify(
        self,
        *,
        signature: MethodSignature,
        state: Any,
        params: Mapping[str, Any],
        output: Any,
    ) -> ValidatedBound:
        resolved = _resolve_declared_params(signature, params)
        benefits, costs = _extract_welfare_problem(state)
        discount_rate = float(resolved["discount_rate"])
        shadow = float(resolved["shadow_price_factor"])
        if not math.isfinite(discount_rate) or not math.isfinite(shadow):
            return ValidatedBound(
                status=ValidatedStatus.INDETERMINATE,
                quantity=self.quantity,
                lower=None,
                upper=None,
                contains_point_estimate=None,
                method_family=ValidatedMethodFamily.INTERVAL,
                engine="binary64.nextafter",
                semantics={"reason": "non_finite_discount_parameters"},
            )
        if discount_rate <= -1.0:
            return ValidatedBound(
                status=ValidatedStatus.INDETERMINATE,
                quantity=self.quantity,
                lower=None,
                upper=None,
                contains_point_estimate=None,
                method_family=ValidatedMethodFamily.INTERVAL,
                engine="binary64.nextafter",
                semantics={"reason": "discount_rate_crosses_singularity"},
            )

        n_periods = benefits.size
        benefits_lower, benefits_upper = _nextafter_interval(benefits)
        costs_lower, costs_upper = _nextafter_interval(costs)
        shadow_lower, shadow_upper = _scalar_interval(shadow)
        scaled_benefits_lower, scaled_benefits_upper = _interval_mul(
            benefits_lower,
            benefits_upper,
            shadow_lower,
            shadow_upper,
        )
        discount_lower, discount_upper = _discount_factor_interval(discount_rate, n_periods)
        pv_benefits_lower, pv_benefits_upper = _discounted_sum_interval(
            scaled_benefits_lower,
            scaled_benefits_upper,
            discount_lower,
            discount_upper,
        )
        pv_costs_lower, pv_costs_upper = _discounted_sum_interval(
            costs_lower,
            costs_upper,
            discount_lower,
            discount_upper,
        )
        npv_lower, npv_upper = _interval_sub(
            pv_benefits_lower,
            pv_benefits_upper,
            pv_costs_lower,
            pv_costs_upper,
        )
        npv_lower = float(npv_lower)
        npv_upper = float(npv_upper)

        result = _extract_result_mapping(output) or {}
        npv_point = float(result.get("npv", (pv_benefits_lower + pv_benefits_upper) / 2.0))
        irr_witness: dict[str, Any] | None = None
        net_flows = benefits * shadow - costs
        irr_value = result.get("irr")
        irr_bracket = result.get("irr_bracket")
        if (
            irr_value is not None
            and isinstance(irr_bracket, (list, tuple))
            and len(irr_bracket) == 2
        ):
            bracket_lower = math.nextafter(float(irr_bracket[0]), -math.inf)
            bracket_upper = math.nextafter(float(irr_bracket[1]), math.inf)
            npv_at_lower = _npv_interval_at_rate_bounds(
                net_flows,
                *_scalar_interval(float(irr_bracket[0])),
            )
            npv_at_upper = _npv_interval_at_rate_bounds(
                net_flows,
                *_scalar_interval(float(irr_bracket[1])),
            )
            derivative_lower, derivative_upper = _npv_derivative_interval_at_rate_bounds(
                net_flows,
                bracket_lower,
                bracket_upper,
            )
            sign_change_certified = (
                npv_at_lower[1] < 0.0 < npv_at_upper[0]
                or npv_at_upper[1] < 0.0 < npv_at_lower[0]
            )
            monotone = derivative_upper < 0.0 or derivative_lower > 0.0
            irr_status = (
                ValidatedStatus.RIGOROUS_UNIQUE_ROOT
                if sign_change_certified and monotone
                else (
                    ValidatedStatus.RIGOROUS_ENCLOSURE
                    if sign_change_certified
                    else ValidatedStatus.INDETERMINATE
                )
            )
            irr_witness = {
                "status": irr_status.value,
                "point_estimate": float(irr_value),
                "interval": [bracket_lower, bracket_upper],
                "contains_point_estimate": bracket_lower <= float(irr_value) <= bracket_upper,
                "npv_at_interval_endpoints": {
                    "lower_rate": list(npv_at_lower),
                    "upper_rate": list(npv_at_upper),
                },
                "derivative_interval": [derivative_lower, derivative_upper],
            }

        point_inside = npv_lower <= npv_point <= npv_upper
        return ValidatedBound(
            status=ValidatedStatus.RIGOROUS_ENCLOSURE,
            quantity=self.quantity,
            lower=npv_lower,
            upper=npv_upper,
            contains_point_estimate=point_inside,
            method_family=ValidatedMethodFamily.INTERVAL,
            engine="binary64.nextafter",
            precision_bits=53,
            witness={
                "point_estimate": npv_point,
                "pv_benefits_interval": [pv_benefits_lower, pv_benefits_upper],
                "pv_costs_interval": [pv_costs_lower, pv_costs_upper],
                "discount_rate_interval": list(_scalar_interval(discount_rate)),
                "shadow_price_interval": list(_scalar_interval(shadow)),
                "irr_certificate": irr_witness,
            },
            cost={
                "n_periods": int(n_periods),
                "kernel": "welfare_discounted_ledger_certifier",
            },
            semantics={
                "discounted_sum_certification": True,
                "interval_semantics": "deterministic_rigorous_bound",
                "is_heuristic_ci": False,
                "gate_eligible": True,
                "secondary_root_certificate": (
                    None if irr_witness is None else irr_witness["status"]
                ),
            },
        )


_CERTIFIERS: dict[str, ValidatedCertifier] = {
    "microsim.policy.tax_benefit_calculator@1.0.0": _TaxBenefitMarginalRateCertifier(),
    "optimization.bilevel.bilevel@1.0.0": _BilevelResidualCertifier(),
    "policy.welfare.cost_benefit_analysis@1.0.0": _CostBenefitAnalysisCertifier(),
}


__all__ = [
    "VALIDATED_EXECUTION_PARAM_NAMES",
    "ValidatedBound",
    "ValidatedExecutionPolicy",
    "ValidatedMethodFamily",
    "ValidatedMode",
    "ValidatedStatus",
    "maybe_certify",
    "split_validated_execution_params",
    "validated_bound_to_envelopes",
]
