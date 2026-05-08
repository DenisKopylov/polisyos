"""Mechanism-design contracts, certificates, and tractable Phase 3 verifiers."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from polisyos.ir.artifacts import ArtifactStore, InputRef, get_json_artifact, put_json_artifact
from polisyos.ir.model_layer.canon import CanonSpec
from polisyos.ir.governance.game_design import MechanismConstraintType
from polisyos.ir.registry.refs import (
    IncentiveCompatibilityCertificateRef,
    MechanismFamilySpecRef,
    MechanismWelfareLossBoundRef,
)

_MECHANISM_FAMILY_SPEC_SCHEMA_NAME = "ir.mechanism_family_spec"
_MECHANISM_FAMILY_SPEC_SCHEMA_VERSION = "1.0"
_IC_CERTIFICATE_SCHEMA_NAME = "ir.incentive_compatibility_certificate"
_IC_CERTIFICATE_SCHEMA_VERSION = "1.0"
_WELFARE_BOUND_SCHEMA_NAME = "ir.mechanism_welfare_loss_bound"
_WELFARE_BOUND_SCHEMA_VERSION = "1.0"


def _ensure_non_empty(value: str, *, field_name: str) -> str:
    candidate = str(value).strip()
    if not candidate:
        raise ValueError(f"{field_name} must be non-empty")
    return candidate


def _ensure_finite(value: float, *, field_name: str) -> float:
    numeric = float(value)
    if not math.isfinite(numeric):
        raise ValueError(f"{field_name} must be finite")
    return numeric


def _normalize_float_tuple(value: object, *, field_name: str) -> tuple[float, ...]:
    if value in (None, ""):
        return ()
    if not isinstance(value, (list, tuple)):
        raise ValueError(f"{field_name} must be a list or tuple")
    normalized = tuple(_ensure_finite(float(item), field_name=field_name) for item in value)
    return normalized


def _normalize_string_tuple(value: object, *, field_name: str) -> tuple[str, ...]:
    if value in (None, ""):
        return ()
    if not isinstance(value, (list, tuple, set)):
        raise ValueError(f"{field_name} must be a list/tuple/set of strings")
    return tuple(_ensure_non_empty(str(item), field_name=field_name) for item in value)


def _validate_strictly_increasing(values: Sequence[float], *, field_name: str) -> None:
    if len(values) < 1:
        raise ValueError(f"{field_name} must be non-empty")
    for idx in range(1, len(values)):
        if values[idx] <= values[idx - 1]:
            raise ValueError(f"{field_name} must be strictly increasing")


def _normalize_weights(
    weights: Sequence[float] | None,
    *,
    expected_len: int,
) -> tuple[float, ...] | None:
    if weights is None:
        return None
    normalized = _normalize_float_tuple(weights, field_name="weights")
    if len(normalized) != expected_len:
        raise ValueError("weights must match the grid length")
    if any(weight < 0.0 for weight in normalized):
        raise ValueError("weights must be non-negative")
    total = sum(normalized)
    if total <= 0.0:
        raise ValueError("weights must sum to a positive value")
    return tuple(weight / total for weight in normalized)


def _min_gap(values: Sequence[float]) -> float:
    if len(values) < 2:
        return math.inf
    return min(values[idx] - values[idx - 1] for idx in range(1, len(values)))


def _piecewise_linear_envelope_integral(
    theta0: float,
    theta1: float,
    y0: float,
    y1: float,
) -> float:
    if theta0 <= 0.0 or theta1 <= 0.0:
        raise ValueError("type_grid values must be strictly positive")
    slope = (y1 - y0) / (theta1 - theta0)
    intercept = y0 - slope * theta0
    return (
        0.5 * slope * slope * (theta1 - theta0)
        + slope * intercept * math.log(theta1 / theta0)
        + 0.5 * intercept * intercept * ((1.0 / theta0) - (1.0 / theta1))
    )


def _compute_tax_utilities_and_consumption(
    type_grid: Sequence[float],
    earnings_schedule: Sequence[float],
    *,
    u0: float,
) -> tuple[tuple[float, ...], tuple[float, ...]]:
    utilities = [float(u0)]
    for idx in range(1, len(type_grid)):
        utilities.append(
            utilities[-1]
            + _piecewise_linear_envelope_integral(
                type_grid[idx - 1],
                type_grid[idx],
                earnings_schedule[idx - 1],
                earnings_schedule[idx],
            )
        )
    consumption = tuple(
        utilities[idx] + (earnings_schedule[idx] ** 2) / (2.0 * type_grid[idx])
        for idx in range(len(type_grid))
    )
    return tuple(utilities), consumption


def _compute_tax_profitable_deviation_max(
    type_grid: Sequence[float],
    earnings_schedule: Sequence[float],
    consumption_schedule: Sequence[float],
) -> float:
    max_gain = 0.0
    for true_idx, theta in enumerate(type_grid):
        truthful = consumption_schedule[true_idx] - (earnings_schedule[true_idx] ** 2) / (
            2.0 * theta
        )
        best_report = max(
            consumption_schedule[report_idx] - (earnings_schedule[report_idx] ** 2) / (2.0 * theta)
            for report_idx in range(len(type_grid))
        )
        max_gain = max(max_gain, best_report - truthful)
    return max_gain


def _coerce_series_mapping(
    value: Mapping[str, Sequence[float]] | Sequence[float],
    *,
    expected_len: int,
    field_name: str,
) -> dict[str, tuple[float, ...]]:
    if isinstance(value, Mapping):
        mapping = {
            str(key): _normalize_float_tuple(item, field_name=f"{field_name}.{key}")
            for key, item in value.items()
        }
    else:
        mapping = {"default": _normalize_float_tuple(value, field_name=field_name)}
    if not mapping:
        raise ValueError(f"{field_name} must be non-empty")
    for key, series in mapping.items():
        if len(series) != expected_len:
            raise ValueError(f"{field_name}.{key} must match bid_grid length")
    return mapping


def _prepend_zero_if_needed(
    bid_grid: Sequence[float],
    values: Sequence[float],
) -> tuple[tuple[float, ...], tuple[float, ...]]:
    if bid_grid[0] == 0.0:
        return tuple(bid_grid), tuple(values)
    return (0.0, *tuple(bid_grid)), (0.0, *tuple(values))


def _payment_identity_expected(
    bid_grid: Sequence[float],
    allocation: Sequence[float],
) -> tuple[float, ...]:
    ext_bids, ext_alloc = _prepend_zero_if_needed(bid_grid, allocation)
    integral = [0.0] * len(ext_bids)
    for idx in range(1, len(ext_bids)):
        integral[idx] = integral[idx - 1] + ext_alloc[idx - 1] * (ext_bids[idx] - ext_bids[idx - 1])
    expected = tuple(ext_bids[idx] * ext_alloc[idx] - integral[idx] for idx in range(len(ext_bids)))
    if ext_bids[0] == 0.0 and bid_grid[0] != 0.0:
        return expected[1:]
    return expected


def _compute_license_profitable_deviation_max(
    bid_grid: Sequence[float],
    allocation: Sequence[float],
    payments: Sequence[float],
) -> float:
    max_gain = 0.0
    for true_idx, value in enumerate(bid_grid):
        truthful = value * allocation[true_idx] - payments[true_idx]
        best_report = max(
            value * allocation[report_idx] - payments[report_idx]
            for report_idx in range(len(bid_grid))
        )
        max_gain = max(max_gain, best_report - truthful)
    return max_gain


def _binomial_probability(n: int, k: int, p: float) -> float:
    return math.comb(n, k) * (p**k) * ((1.0 - p) ** (n - k))


def _binomial_cdf_less_than(n: int, cutoff: int, p: float) -> float:
    if cutoff <= 0:
        return 0.0
    return sum(_binomial_probability(n, j, p) for j in range(cutoff))


class MechanismFamily(str, Enum):
    """Supported tractable mechanism families for Phase 3 certificates."""

    TAX_AFFINE = "tax_affine"
    TAX_PIECEWISE_LINEAR = "tax_piecewise_linear"
    LICENSE_SCORING_RESERVE = "license_scoring_reserve"
    LICENSE_MYERSON_SCORE = "license_myerson_score"


class IncentiveCertificateStatus(str, Enum):
    """Certificate verdict for an IC verification attempt."""

    CERTIFIED = "certified"
    BOUNDED = "bounded"
    REJECTED = "rejected"


class ICVerificationMode(str, Enum):
    """Machine-checkable witness families used by the verifier."""

    MONOTONICITY_ENVELOPE = "monotonicity_envelope"
    MONOTONE_THRESHOLD = "monotone_threshold"


class MechanismWelfareBenchmark(str, Enum):
    """Benchmarks used to report welfare-loss upper bounds."""

    COMPLETE_INFORMATION_FIRST_BEST = "complete_information_first_best"
    RESERVE_FREE_EFFICIENT_ALLOCATION = "reserve_free_efficient_allocation"


class MechanismFamilySpec(BaseModel):
    """Persisted description of a tractable mechanism family and its assumptions."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    mechanism_id: str = Field(min_length=1)
    family: MechanismFamily
    verification_mode: ICVerificationMode
    parameterization: str = Field(min_length=1)
    tunable_parameters: tuple[str, ...] = ()
    assumptions: tuple[str, ...] = ()
    data_contract_refs: tuple[str, ...] = ()
    solver_config: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("mechanism_id", "parameterization")
    @classmethod
    def _validate_non_empty_string(cls, value: str) -> str:
        return _ensure_non_empty(value, field_name="mechanism family field")

    @field_validator("tunable_parameters", "assumptions", "data_contract_refs", mode="before")
    @classmethod
    def _normalize_string_fields(cls, value: object) -> tuple[str, ...]:
        return _normalize_string_tuple(value, field_name="mechanism_family_spec")


class IncentiveCompatibilityCertificate(BaseModel):
    """Machine-checkable IC/IR certificate for a concrete mechanism instance."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    mechanism_id: str = Field(min_length=1)
    family: MechanismFamily
    constraint_type: MechanismConstraintType
    verification_mode: ICVerificationMode
    certificate_type: str = Field(min_length=1)
    status: IncentiveCertificateStatus
    grid_role: Literal["type", "bid"]
    grid: tuple[float, ...]
    monotonicity_passed: bool
    monotonicity_margin: float | None = None
    envelope_residual_max: float | None = Field(default=None, ge=0.0)
    payment_residual_max: float | None = Field(default=None, ge=0.0)
    profitable_deviation_max: float | None = Field(default=None, ge=0.0)
    interim_ir_passed: bool | None = None
    budget_feasible: bool | None = None
    revenue_value: float | None = None
    revenue_floor: float | None = None
    tolerance: float = Field(default=1e-9, ge=0.0)
    assumptions_hash: str | None = None
    witness_summary: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("mechanism_id", "certificate_type")
    @classmethod
    def _validate_non_empty(cls, value: str) -> str:
        return _ensure_non_empty(value, field_name="certificate field")

    @field_validator("grid", mode="before")
    @classmethod
    def _normalize_grid(cls, value: object) -> tuple[float, ...]:
        grid = _normalize_float_tuple(value, field_name="grid")
        _validate_strictly_increasing(grid, field_name="grid")
        return grid

    @model_validator(mode="after")
    def _validate_consistency(self) -> IncentiveCompatibilityCertificate:
        if (
            self.verification_mode is ICVerificationMode.MONOTONICITY_ENVELOPE
            and self.envelope_residual_max is None
        ):
            raise ValueError("envelope verification requires envelope_residual_max")
        if (
            self.verification_mode is ICVerificationMode.MONOTONE_THRESHOLD
            and self.payment_residual_max is None
        ):
            raise ValueError("threshold verification requires payment_residual_max")
        if self.revenue_floor is not None and self.revenue_value is None:
            raise ValueError("revenue_floor requires revenue_value")
        return self


class MechanismWelfareLossBound(BaseModel):
    """Upper bound on welfare loss relative to a declared first-best benchmark."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    mechanism_id: str = Field(min_length=1)
    family: MechanismFamily
    benchmark: MechanismWelfareBenchmark
    bound_type: str = Field(min_length=1)
    upper_bound: float = Field(ge=0.0)
    observed_gap: float | None = Field(default=None, ge=0.0)
    expected_mechanism_welfare: float | None = None
    expected_benchmark_welfare: float | None = None
    assumptions_hash: str | None = None
    derivation_notes: tuple[str, ...] = ()
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("mechanism_id", "bound_type")
    @classmethod
    def _validate_required_strings(cls, value: str) -> str:
        return _ensure_non_empty(value, field_name="welfare bound field")

    @field_validator("derivation_notes", mode="before")
    @classmethod
    def _normalize_notes(cls, value: object) -> tuple[str, ...]:
        return _normalize_string_tuple(value, field_name="derivation_notes")


def certify_piecewise_linear_tax(
    *,
    mechanism_id: str,
    type_grid: Sequence[float],
    earnings_schedule: Sequence[float],
    u0: float = 0.0,
    prior_weights: Sequence[float] | None = None,
    revenue_floor: float | None = None,
    tolerance: float = 1e-9,
    assumptions_hash: str | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> tuple[IncentiveCompatibilityCertificate, MechanismWelfareLossBound]:
    """Certify a monotone piecewise-linear tax family via envelope construction."""

    mechanism_id = _ensure_non_empty(mechanism_id, field_name="mechanism_id")
    grid = _normalize_float_tuple(type_grid, field_name="type_grid")
    schedule = _normalize_float_tuple(earnings_schedule, field_name="earnings_schedule")
    _validate_strictly_increasing(grid, field_name="type_grid")
    if len(grid) != len(schedule):
        raise ValueError("earnings_schedule must match type_grid length")
    if any(theta <= 0.0 for theta in grid):
        raise ValueError("type_grid values must be strictly positive")
    if any(y < 0.0 for y in schedule):
        raise ValueError("earnings_schedule must be non-negative")

    weights = _normalize_weights(prior_weights, expected_len=len(grid))
    utilities, consumption = _compute_tax_utilities_and_consumption(grid, schedule, u0=float(u0))
    tax_schedule = tuple(schedule[idx] - consumption[idx] for idx in range(len(grid)))
    expected_revenue = (
        sum(weights[idx] * tax_schedule[idx] for idx in range(len(grid)))
        if weights is not None
        else None
    )
    monotonicity_margin = _min_gap(schedule)
    monotonicity_ok = monotonicity_margin >= -tolerance
    profitable_deviation_max = _compute_tax_profitable_deviation_max(grid, schedule, consumption)
    interim_ir_ok = utilities[0] >= -tolerance
    revenue_ok = (
        None
        if revenue_floor is None or expected_revenue is None
        else expected_revenue + tolerance >= float(revenue_floor)
    )
    status = (
        IncentiveCertificateStatus.CERTIFIED
        if monotonicity_ok and profitable_deviation_max <= tolerance and interim_ir_ok
        else IncentiveCertificateStatus.REJECTED
    )

    welfare_values = tuple(
        schedule[idx] - (schedule[idx] ** 2) / (2.0 * grid[idx]) for idx in range(len(grid))
    )
    first_best_values = tuple(theta / 2.0 for theta in grid)
    gap_values = tuple(
        ((grid[idx] - schedule[idx]) ** 2) / (2.0 * grid[idx]) for idx in range(len(grid))
    )
    max_eps = max(abs(grid[idx] - schedule[idx]) for idx in range(len(grid)))
    upper_bound = (max_eps**2) / (2.0 * grid[0])
    observed_gap = (
        sum(weights[idx] * gap_values[idx] for idx in range(len(grid)))
        if weights is not None
        else None
    )
    expected_mechanism_welfare = (
        sum(weights[idx] * welfare_values[idx] for idx in range(len(grid)))
        if weights is not None
        else None
    )
    expected_first_best_welfare = (
        sum(weights[idx] * first_best_values[idx] for idx in range(len(grid)))
        if weights is not None
        else None
    )

    certificate = IncentiveCompatibilityCertificate(
        mechanism_id=mechanism_id,
        family=MechanismFamily.TAX_PIECEWISE_LINEAR,
        constraint_type=MechanismConstraintType.BAYESIAN_IC,
        verification_mode=ICVerificationMode.MONOTONICITY_ENVELOPE,
        certificate_type="monotonicity_envelope_tax_v1",
        status=status,
        grid_role="type",
        grid=grid,
        monotonicity_passed=monotonicity_ok,
        monotonicity_margin=monotonicity_margin,
        envelope_residual_max=max(
            abs(consumption[idx] - (utilities[idx] + (schedule[idx] ** 2) / (2.0 * grid[idx])))
            for idx in range(len(grid))
        ),
        profitable_deviation_max=profitable_deviation_max,
        interim_ir_passed=interim_ir_ok,
        budget_feasible=revenue_ok,
        revenue_value=expected_revenue,
        revenue_floor=float(revenue_floor) if revenue_floor is not None else None,
        tolerance=float(tolerance),
        assumptions_hash=assumptions_hash,
        witness_summary={
            "type_grid": list(grid),
            "earnings_schedule": list(schedule),
            "utility_schedule": list(utilities),
            "consumption_schedule": list(consumption),
            "tax_schedule": list(tax_schedule),
        },
        metadata=dict(metadata or {}),
    )
    bound = MechanismWelfareLossBound(
        mechanism_id=mechanism_id,
        family=MechanismFamily.TAX_PIECEWISE_LINEAR,
        benchmark=MechanismWelfareBenchmark.COMPLETE_INFORMATION_FIRST_BEST,
        bound_type="quadratic_first_best_gap_v1",
        upper_bound=upper_bound,
        observed_gap=observed_gap,
        expected_mechanism_welfare=expected_mechanism_welfare,
        expected_benchmark_welfare=expected_first_best_welfare,
        assumptions_hash=assumptions_hash,
        derivation_notes=(
            "utility=c-y^2/(2*theta)",
            "first_best_earnings=theta",
            "upper_bound=eps^2/(2*theta_min)",
        ),
        metadata={
            "type_grid": list(grid),
            "earnings_schedule": list(schedule),
            "gap_values": list(gap_values),
            **dict(metadata or {}),
        },
    )
    return certificate, bound


def certify_affine_tax(
    *,
    mechanism_id: str,
    type_grid: Sequence[float],
    gamma: float,
    u0: float = 0.0,
    prior_weights: Sequence[float] | None = None,
    revenue_floor: float | None = None,
    tolerance: float = 1e-9,
    assumptions_hash: str | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> tuple[IncentiveCompatibilityCertificate, MechanismWelfareLossBound]:
    """Convenience wrapper for affine taxes expressed as earnings schedules."""

    gamma_value = _ensure_finite(float(gamma), field_name="gamma")
    if not (0.0 <= gamma_value <= 1.0):
        raise ValueError("gamma must lie in [0, 1]")
    schedule = tuple(gamma_value * float(theta) for theta in type_grid)
    certificate, bound = certify_piecewise_linear_tax(
        mechanism_id=mechanism_id,
        type_grid=type_grid,
        earnings_schedule=schedule,
        u0=u0,
        prior_weights=prior_weights,
        revenue_floor=revenue_floor,
        tolerance=tolerance,
        assumptions_hash=assumptions_hash,
        metadata={"gamma": gamma_value, **dict(metadata or {})},
    )
    return (
        certificate.model_copy(update={"family": MechanismFamily.TAX_AFFINE}),
        bound.model_copy(update={"family": MechanismFamily.TAX_AFFINE}),
    )


def certify_license_scoring_auction(
    *,
    mechanism_id: str,
    bid_grid: Sequence[float],
    allocation_rule: Mapping[str, Sequence[float]] | Sequence[float],
    payments: Mapping[str, Sequence[float]] | Sequence[float],
    reserve_price: float | Mapping[str, float] | None = None,
    constraint_type: MechanismConstraintType = MechanismConstraintType.DOMINANT_STRATEGY_IC,
    feasibility_family: str = "top_k",
    tolerance: float = 1e-9,
    assumptions_hash: str | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> IncentiveCompatibilityCertificate:
    """Certify a single-parameter scoring auction on a bid grid."""

    mechanism_id = _ensure_non_empty(mechanism_id, field_name="mechanism_id")
    grid = _normalize_float_tuple(bid_grid, field_name="bid_grid")
    _validate_strictly_increasing(grid, field_name="bid_grid")
    if any(bid < 0.0 for bid in grid):
        raise ValueError("bid_grid must be non-negative")
    allocations = _coerce_series_mapping(
        allocation_rule,
        expected_len=len(grid),
        field_name="allocation_rule",
    )
    payment_map = _coerce_series_mapping(
        payments,
        expected_len=len(grid),
        field_name="payments",
    )
    if set(payment_map) != set(allocations):
        raise ValueError("payments must match allocation_rule bidder classes exactly")

    reserve_map: dict[str, float] = {}
    if isinstance(reserve_price, Mapping):
        reserve_map = {
            str(key): _ensure_finite(float(value), field_name=f"reserve_price.{key}")
            for key, value in reserve_price.items()
        }
    elif reserve_price is not None:
        reserve_value = _ensure_finite(float(reserve_price), field_name="reserve_price")
        reserve_map = dict.fromkeys(allocations, reserve_value)
    else:
        reserve_map = dict.fromkeys(allocations, 0.0)
    if set(reserve_map) != set(allocations):
        raise ValueError("reserve_price mapping must match allocation_rule bidder classes exactly")

    monotonicity_margin = math.inf
    profitable_deviation_max = 0.0
    payment_residual_max = 0.0
    interim_ir_ok = True
    budget_ok = True
    class_summaries: dict[str, Any] = {}
    for bidder_class, allocation in allocations.items():
        payment_series = payment_map[bidder_class]
        margin = _min_gap(allocation)
        monotonicity_margin = min(monotonicity_margin, margin)
        expected_payments = _payment_identity_expected(grid, allocation)
        payment_residual_max = max(
            payment_residual_max,
            max(abs(payment_series[idx] - expected_payments[idx]) for idx in range(len(grid))),
        )
        profitable_deviation_max = max(
            profitable_deviation_max,
            _compute_license_profitable_deviation_max(grid, allocation, payment_series),
        )
        truthful_utilities = tuple(
            grid[idx] * allocation[idx] - payment_series[idx] for idx in range(len(grid))
        )
        interim_ir_ok = interim_ir_ok and all(
            utility >= -tolerance for utility in truthful_utilities
        )
        reserve_value = reserve_map[bidder_class]
        reserve_ok = all(
            not (
                grid[idx] + tolerance < reserve_value
                and (abs(allocation[idx]) > tolerance or abs(payment_series[idx]) > tolerance)
            )
            for idx in range(len(grid))
        )
        non_negative_payments = all(payment >= -tolerance for payment in payment_series)
        budget_ok = budget_ok and reserve_ok and non_negative_payments
        class_summaries[bidder_class] = {
            "allocation": list(allocation),
            "payments": list(payment_series),
            "expected_payments": list(expected_payments),
            "truthful_utilities": list(truthful_utilities),
            "reserve_price": reserve_value,
        }

    monotonicity_ok = monotonicity_margin >= -tolerance
    status = (
        IncentiveCertificateStatus.CERTIFIED
        if (
            monotonicity_ok
            and payment_residual_max <= tolerance
            and profitable_deviation_max <= tolerance
            and interim_ir_ok
        )
        else IncentiveCertificateStatus.REJECTED
    )
    return IncentiveCompatibilityCertificate(
        mechanism_id=mechanism_id,
        family=MechanismFamily.LICENSE_SCORING_RESERVE,
        constraint_type=constraint_type,
        verification_mode=ICVerificationMode.MONOTONE_THRESHOLD,
        certificate_type="monotone_threshold_license_v1",
        status=status,
        grid_role="bid",
        grid=grid,
        monotonicity_passed=monotonicity_ok,
        monotonicity_margin=monotonicity_margin,
        payment_residual_max=payment_residual_max,
        profitable_deviation_max=profitable_deviation_max,
        interim_ir_passed=interim_ir_ok,
        budget_feasible=budget_ok,
        tolerance=float(tolerance),
        assumptions_hash=assumptions_hash,
        witness_summary={
            "feasibility_family": feasibility_family,
            "classes": class_summaries,
        },
        metadata=dict(metadata or {}),
    )


def build_reserve_auction_welfare_loss_bound(
    *,
    mechanism_id: str,
    n_bidders: int,
    k_units: int,
    reserve_price: float,
    cdf_at_reserve: float,
    assumptions_hash: str | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> MechanismWelfareLossBound:
    """Upper bound the reserve-auction welfare loss by a binomial tail formula."""

    if n_bidders < 1:
        raise ValueError("n_bidders must be >= 1")
    if k_units < 1 or k_units > n_bidders:
        raise ValueError("k_units must lie in [1, n_bidders]")
    reserve = _ensure_finite(float(reserve_price), field_name="reserve_price")
    cdf_value = _ensure_finite(float(cdf_at_reserve), field_name="cdf_at_reserve")
    if not (0.0 <= cdf_value <= 1.0):
        raise ValueError("cdf_at_reserve must lie in [0, 1]")
    success_probability = 1.0 - cdf_value
    tail_terms = [
        _binomial_cdf_less_than(n_bidders, j, success_probability) for j in range(1, k_units + 1)
    ]
    upper_bound = reserve * sum(tail_terms)
    return MechanismWelfareLossBound(
        mechanism_id=_ensure_non_empty(mechanism_id, field_name="mechanism_id"),
        family=MechanismFamily.LICENSE_SCORING_RESERVE,
        benchmark=MechanismWelfareBenchmark.RESERVE_FREE_EFFICIENT_ALLOCATION,
        bound_type="reserve_binomial_tail_v1",
        upper_bound=upper_bound,
        assumptions_hash=assumptions_hash,
        derivation_notes=(
            "B_r~Bin(n,1-F(r))",
            "upper_bound=r*sum_{j=1}^k P(B_r<j)",
        ),
        metadata={
            "n_bidders": n_bidders,
            "k_units": k_units,
            "reserve_price": reserve,
            "cdf_at_reserve": cdf_value,
            "tail_terms": tail_terms,
            **dict(metadata or {}),
        },
    )


def persist_mechanism_family_spec(
    store: ArtifactStore,
    spec: MechanismFamilySpec,
    *,
    inputs: list[InputRef] | None = None,
) -> MechanismFamilySpecRef:
    """Persist a mechanism-family specification and return its typed ref."""

    ref = put_json_artifact(
        store,
        spec.model_dump(mode="json"),
        kind="ir.mechanism_family_spec",
        schema_name=_MECHANISM_FAMILY_SPEC_SCHEMA_NAME,
        schema_version=_MECHANISM_FAMILY_SPEC_SCHEMA_VERSION,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return MechanismFamilySpecRef.model_validate(ref)


def load_mechanism_family_spec(
    store: ArtifactStore,
    ref: MechanismFamilySpecRef,
) -> MechanismFamilySpec:
    """Load a persisted mechanism-family specification."""

    payload = get_json_artifact(store, ref.artifact_id)
    return MechanismFamilySpec.model_validate(payload)


def persist_incentive_compatibility_certificate(
    store: ArtifactStore,
    certificate: IncentiveCompatibilityCertificate,
    *,
    inputs: list[InputRef] | None = None,
) -> IncentiveCompatibilityCertificateRef:
    """Persist an IC certificate and return its typed ref."""

    ref = put_json_artifact(
        store,
        certificate.model_dump(mode="json"),
        kind="ir.incentive_compatibility_certificate",
        schema_name=_IC_CERTIFICATE_SCHEMA_NAME,
        schema_version=_IC_CERTIFICATE_SCHEMA_VERSION,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return IncentiveCompatibilityCertificateRef.model_validate(ref)


def load_incentive_compatibility_certificate(
    store: ArtifactStore,
    ref: IncentiveCompatibilityCertificateRef,
) -> IncentiveCompatibilityCertificate:
    """Load a persisted IC certificate."""

    payload = get_json_artifact(store, ref.artifact_id)
    return IncentiveCompatibilityCertificate.model_validate(payload)


def persist_mechanism_welfare_loss_bound(
    store: ArtifactStore,
    bound: MechanismWelfareLossBound,
    *,
    inputs: list[InputRef] | None = None,
) -> MechanismWelfareLossBoundRef:
    """Persist a welfare-loss bound and return its typed ref."""

    ref = put_json_artifact(
        store,
        bound.model_dump(mode="json"),
        kind="ir.mechanism_welfare_loss_bound",
        schema_name=_WELFARE_BOUND_SCHEMA_NAME,
        schema_version=_WELFARE_BOUND_SCHEMA_VERSION,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return MechanismWelfareLossBoundRef.model_validate(ref)


def load_mechanism_welfare_loss_bound(
    store: ArtifactStore,
    ref: MechanismWelfareLossBoundRef,
) -> MechanismWelfareLossBound:
    """Load a persisted welfare-loss bound."""

    payload = get_json_artifact(store, ref.artifact_id)
    return MechanismWelfareLossBound.model_validate(payload)


__all__ = [
    "ICVerificationMode",
    "IncentiveCertificateStatus",
    "IncentiveCompatibilityCertificate",
    "MechanismFamily",
    "MechanismFamilySpec",
    "MechanismWelfareBenchmark",
    "MechanismWelfareLossBound",
    "build_reserve_auction_welfare_loss_bound",
    "certify_affine_tax",
    "certify_license_scoring_auction",
    "certify_piecewise_linear_tax",
    "load_incentive_compatibility_certificate",
    "load_mechanism_family_spec",
    "load_mechanism_welfare_loss_bound",
    "persist_incentive_compatibility_certificate",
    "persist_mechanism_family_spec",
    "persist_mechanism_welfare_loss_bound",
]
