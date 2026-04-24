"""Public optimization protocols module API."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, ClassVar, Literal, Protocol, runtime_checkable

from polisyos.core.observability import get_metrics
from polisyos.foundry.methods.backends.protocol import SolverStatus
from polisyos.ir.analytics.uncertainty import UncertaintyEnvelope


def _jsonable(value: Any) -> Any:
    """Convert nested protocol payloads into JSON-compatible primitives."""

    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, tuple | list):
        return [_jsonable(item) for item in value]
    if hasattr(value, "to_payload") and callable(value.to_payload):
        return value.to_payload()
    return value


def _as_float_tuple(values: Any, *, name: str) -> tuple[float, ...]:
    if not isinstance(values, (list, tuple)):
        raise ValueError(f"{name} must be a list or tuple")
    return tuple(float(item) for item in values)


def _as_matrix_tuple(values: Any, *, name: str) -> tuple[tuple[float, ...], ...]:
    if not isinstance(values, (list, tuple)):
        raise ValueError(f"{name} must be a list or tuple of rows")
    matrix = tuple(_as_float_tuple(row, name=f"{name} row") for row in values)
    if matrix:
        width = len(matrix[0])
        if any(len(row) != width for row in matrix):
            raise ValueError(f"{name} rows must all have the same length")
    return matrix


def _as_int_tuple(values: Any, *, name: str) -> tuple[int, ...]:
    if not isinstance(values, (list, tuple)):
        raise ValueError(f"{name} must be a list or tuple")
    return tuple(int(item) for item in values)


def _as_str_tuple(values: Any, *, name: str) -> tuple[str, ...]:
    if not isinstance(values, (list, tuple)):
        raise ValueError(f"{name} must be a list or tuple")
    return tuple(str(item) for item in values)


def _as_float_mapping(values: Any, *, name: str) -> Mapping[str, float]:
    if values is None:
        return {}
    if not isinstance(values, Mapping):
        raise ValueError(f"{name} must be a mapping")
    return {str(key): float(value) for key, value in values.items()}


def _as_binary_hits_mapping(values: Any, *, name: str) -> Mapping[str, tuple[int, ...]]:
    if values is None:
        return {}
    if not isinstance(values, Mapping):
        raise ValueError(f"{name} must be a mapping")
    output: dict[str, tuple[int, ...]] = {}
    for key, raw_hits in values.items():
        hits = _as_int_tuple(raw_hits, name=f"{name}.{key}")
        if any(hit not in {0, 1} for hit in hits):
            raise ValueError(f"{name}.{key} must contain only 0/1 indicators")
        output[str(key)] = hits
    return output


def _require_choice(value: str, *, name: str, allowed: set[str]) -> str:
    if value not in allowed:
        allowed_list = ", ".join(sorted(allowed))
        raise ValueError(f"{name} must be one of {allowed_list}")
    return value


@dataclass(frozen=True, slots=True)
class AllocationItem:
    """Single allocation decision variable."""

    item_id: str
    cost: float
    benefit: float
    min_units: int = 0
    max_units: int = 1
    is_integer: bool = True
    category: str | None = None

    def __post_init__(self) -> None:
        if not self.item_id:
            raise ValueError("item_id must be non-empty")
        if self.max_units < self.min_units:
            raise ValueError("max_units must be >= min_units")


@dataclass(frozen=True, slots=True)
class ResourceConstraint:
    """Linear resource constraint over allocation items."""

    constraint_id: str
    coefficients: Mapping[str, float]
    bound: float
    sense: str = "<="

    def __post_init__(self) -> None:
        if not self.constraint_id:
            raise ValueError("constraint_id must be non-empty")
        if self.sense not in {"<=", ">=", "=="}:
            raise ValueError("sense must be one of <=, >=, ==")


@dataclass(frozen=True, slots=True)
class OptimizationProblem:
    """Canonical optimization problem payload for MILP/LP methods."""

    contract_id: ClassVar[str] = "foundry.optimization.problem.v1"
    problem_id: str
    items: tuple[AllocationItem, ...]
    constraints: tuple[ResourceConstraint, ...] = ()
    objective: str = "maximize"
    budget: float | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.problem_id:
            raise ValueError("problem_id must be non-empty")
        if self.objective not in {"maximize", "minimize"}:
            raise ValueError("objective must be 'maximize' or 'minimize'")
        if not self.items:
            raise ValueError("items must be non-empty")

        seen: set[str] = set()
        for item in self.items:
            if item.item_id in seen:
                raise ValueError(f"duplicate item_id: {item.item_id}")
            seen.add(item.item_id)

        for constraint in self.constraints:
            for item_id in constraint.coefficients:
                if item_id not in seen:
                    raise ValueError(
                        f"constraint '{constraint.constraint_id}' references "
                        f"unknown item '{item_id}'"
                    )

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> OptimizationProblem:
        items_raw = payload.get("items")
        if not isinstance(items_raw, list):
            raise ValueError("problem payload must include list field 'items'")
        constraints_raw = payload.get("constraints")
        if constraints_raw is None:
            constraints_raw = []
        if not isinstance(constraints_raw, list):
            raise ValueError("problem payload field 'constraints' must be a list")

        items = tuple(AllocationItem(**item) for item in items_raw)
        constraints = tuple(ResourceConstraint(**ct) for ct in constraints_raw)
        return cls(
            problem_id=str(payload.get("problem_id", "problem")),
            items=items,
            constraints=constraints,
            objective=str(payload.get("objective", "maximize")),
            budget=float(payload["budget"]) if payload.get("budget") is not None else None,
            metadata=(
                payload.get("metadata", {}) if isinstance(payload.get("metadata", {}), dict) else {}
            ),
        )


@dataclass(frozen=True, slots=True)
class MomentBound:
    """Single declared moment or moment-derived bound in a DRO certificate."""

    name: str
    order: int
    estimator: str
    point_estimate: Any
    lower: float | None = None
    upper: float | None = None
    confidence: float = 0.95
    regime: str | None = None
    sample_size: int | None = None
    effective_sample_size: float | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("MomentBound.name must be non-empty")
        if self.order < 1:
            raise ValueError("MomentBound.order must be >= 1")
        if not self.estimator:
            raise ValueError("MomentBound.estimator must be non-empty")
        if not 0.0 < float(self.confidence) <= 1.0:
            raise ValueError("MomentBound.confidence must be in (0, 1]")
        if self.sample_size is not None and int(self.sample_size) < 0:
            raise ValueError("MomentBound.sample_size must be >= 0")

    def to_payload(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "order": int(self.order),
            "estimator": self.estimator,
            "point_estimate": _jsonable(self.point_estimate),
            "lower": self.lower,
            "upper": self.upper,
            "confidence": float(self.confidence),
            "regime": self.regime,
            "sample_size": self.sample_size,
            "effective_sample_size": self.effective_sample_size,
            "metadata": _jsonable(self.metadata),
        }

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> MomentBound:
        return cls(
            name=str(payload.get("name", "")),
            order=int(payload.get("order", 1)),
            estimator=str(payload.get("estimator", "")),
            point_estimate=payload.get("point_estimate"),
            lower=(None if payload.get("lower") is None else float(payload["lower"])),
            upper=(None if payload.get("upper") is None else float(payload["upper"])),
            confidence=float(payload.get("confidence", 0.95)),
            regime=(None if payload.get("regime") is None else str(payload["regime"])),
            sample_size=(
                None if payload.get("sample_size") is None else int(payload["sample_size"])
            ),
            effective_sample_size=(
                None
                if payload.get("effective_sample_size") is None
                else float(payload["effective_sample_size"])
            ),
            metadata=(
                payload.get("metadata", {})
                if isinstance(payload.get("metadata", {}), Mapping)
                else {}
            ),
        )


@dataclass(frozen=True, slots=True)
class ConstraintCertificate:
    """Per-constraint ambiguity certificate for stochastic optimization."""

    name: str
    constraint_class: Literal["budget", "capacity", "equity", "revenue"]
    formulation: str
    exactness: str
    worst_case_bound: float
    threshold: float
    slack: float
    solver_family: Literal["LP", "SOCP", "SDP", "MISOCP", "MomentSOS"]
    epsilon: float | None = None
    violation_probability_bound: float | None = None
    duality_gap: float | None = None
    theorem_refs: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("ConstraintCertificate.name must be non-empty")
        _require_choice(
            str(self.constraint_class),
            name="ConstraintCertificate.constraint_class",
            allowed={"budget", "capacity", "equity", "revenue"},
        )
        _require_choice(
            str(self.solver_family),
            name="ConstraintCertificate.solver_family",
            allowed={"LP", "SOCP", "SDP", "MISOCP", "MomentSOS"},
        )
        if self.epsilon is not None and not 0.0 < float(self.epsilon) < 1.0:
            raise ValueError("ConstraintCertificate.epsilon must be in (0, 1)")

    def to_payload(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "constraint_class": str(self.constraint_class),
            "formulation": self.formulation,
            "exactness": self.exactness,
            "worst_case_bound": float(self.worst_case_bound),
            "threshold": float(self.threshold),
            "slack": float(self.slack),
            "solver_family": str(self.solver_family),
            "epsilon": self.epsilon,
            "violation_probability_bound": self.violation_probability_bound,
            "duality_gap": self.duality_gap,
            "theorem_refs": list(self.theorem_refs),
            "metadata": _jsonable(self.metadata),
        }

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> ConstraintCertificate:
        theorem_refs_raw = payload.get("theorem_refs", ())
        theorem_refs = (
            tuple(str(item) for item in theorem_refs_raw)
            if isinstance(theorem_refs_raw, (list, tuple))
            else ()
        )
        return cls(
            name=str(payload.get("name", "")),
            constraint_class=str(payload.get("constraint_class", "budget")),  # type: ignore[arg-type]
            formulation=str(payload.get("formulation", "")),
            exactness=str(payload.get("exactness", "")),
            worst_case_bound=float(payload.get("worst_case_bound", 0.0)),
            threshold=float(payload.get("threshold", 0.0)),
            slack=float(payload.get("slack", 0.0)),
            solver_family=str(payload.get("solver_family", "SOCP")),  # type: ignore[arg-type]
            epsilon=(None if payload.get("epsilon") is None else float(payload["epsilon"])),
            violation_probability_bound=(
                None
                if payload.get("violation_probability_bound") is None
                else float(payload["violation_probability_bound"])
            ),
            duality_gap=(
                None if payload.get("duality_gap") is None else float(payload["duality_gap"])
            ),
            theorem_refs=theorem_refs,
            metadata=(
                payload.get("metadata", {})
                if isinstance(payload.get("metadata", {}), Mapping)
                else {}
            ),
        )


@dataclass(frozen=True, slots=True)
class DiagnosticResult:
    """Diagnostic emitted during ambiguity-set validation."""

    test_name: str
    status: Literal["pass", "warn", "fail"]
    message: str
    statistic: float | None = None
    p_value: float | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.test_name:
            raise ValueError("DiagnosticResult.test_name must be non-empty")
        _require_choice(
            str(self.status),
            name="DiagnosticResult.status",
            allowed={"pass", "warn", "fail"},
        )
        if not self.message:
            raise ValueError("DiagnosticResult.message must be non-empty")

    def to_payload(self) -> dict[str, Any]:
        return {
            "test_name": self.test_name,
            "status": str(self.status),
            "message": self.message,
            "statistic": self.statistic,
            "p_value": self.p_value,
            "metadata": _jsonable(self.metadata),
        }

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> DiagnosticResult:
        return cls(
            test_name=str(payload.get("test_name", "")),
            status=str(payload.get("status", "warn")),  # type: ignore[arg-type]
            message=str(payload.get("message", "")),
            statistic=(None if payload.get("statistic") is None else float(payload["statistic"])),
            p_value=(None if payload.get("p_value") is None else float(payload["p_value"])),
            metadata=(
                payload.get("metadata", {})
                if isinstance(payload.get("metadata", {}), Mapping)
                else {}
            ),
        )


@dataclass(frozen=True, slots=True)
class AmbiguityCertificate:
    """Typed ambiguity certificate attached to a stochastic optimization result."""

    certificate_version: str = "1.0"
    ambiguity_set_type: Literal[
        "moment_mean_cov",
        "moment_mean_cov_support",
        "moment_higher_order",
        "robust_box",
        "robust_ellipsoid",
        "robust_set",
        "wasserstein",
        "phi_divergence",
        "hybrid",
    ] = "moment_mean_cov"
    confidence_level: float = 0.95
    overall_status: Literal["pass", "warn", "fail"] = "warn"
    support_description: str | None = None
    regime_model: str | None = None
    moment_bounds: tuple[MomentBound, ...] = ()
    per_constraint: tuple[ConstraintCertificate, ...] = ()
    diagnostics: tuple[DiagnosticResult, ...] = ()
    price_of_ambiguity: float | None = None
    price_of_robustness: float | None = None
    solver_runtime_ms: float | None = None
    solver_backend: str | None = None
    reproducibility: Mapping[str, Any] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.certificate_version:
            raise ValueError("AmbiguityCertificate.certificate_version must be non-empty")
        _require_choice(
            str(self.overall_status),
            name="AmbiguityCertificate.overall_status",
            allowed={"pass", "warn", "fail"},
        )
        if not 0.0 < float(self.confidence_level) <= 1.0:
            raise ValueError("AmbiguityCertificate.confidence_level must be in (0, 1]")

    def to_payload(self) -> dict[str, Any]:
        return {
            "certificate_version": self.certificate_version,
            "ambiguity_set_type": str(self.ambiguity_set_type),
            "confidence_level": float(self.confidence_level),
            "overall_status": str(self.overall_status),
            "support_description": self.support_description,
            "regime_model": self.regime_model,
            "moment_bounds": [item.to_payload() for item in self.moment_bounds],
            "per_constraint": [item.to_payload() for item in self.per_constraint],
            "diagnostics": [item.to_payload() for item in self.diagnostics],
            "price_of_ambiguity": self.price_of_ambiguity,
            "price_of_robustness": self.price_of_robustness,
            "solver_runtime_ms": self.solver_runtime_ms,
            "solver_backend": self.solver_backend,
            "reproducibility": _jsonable(self.reproducibility),
            "metadata": _jsonable(self.metadata),
        }

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> AmbiguityCertificate:
        moment_bounds_raw = payload.get("moment_bounds", ())
        per_constraint_raw = payload.get("per_constraint", ())
        diagnostics_raw = payload.get("diagnostics", ())
        return cls(
            certificate_version=str(payload.get("certificate_version", "1.0")),
            ambiguity_set_type=str(payload.get("ambiguity_set_type", "moment_mean_cov")),  # type: ignore[arg-type]
            confidence_level=float(payload.get("confidence_level", 0.95)),
            overall_status=str(payload.get("overall_status", "warn")),  # type: ignore[arg-type]
            support_description=(
                None
                if payload.get("support_description") is None
                else str(payload["support_description"])
            ),
            regime_model=(
                None if payload.get("regime_model") is None else str(payload["regime_model"])
            ),
            moment_bounds=tuple(
                MomentBound.from_mapping(item)
                for item in moment_bounds_raw
                if isinstance(item, Mapping)
            ),
            per_constraint=tuple(
                ConstraintCertificate.from_mapping(item)
                for item in per_constraint_raw
                if isinstance(item, Mapping)
            ),
            diagnostics=tuple(
                DiagnosticResult.from_mapping(item)
                for item in diagnostics_raw
                if isinstance(item, Mapping)
            ),
            price_of_ambiguity=(
                None
                if payload.get("price_of_ambiguity") is None
                else float(payload["price_of_ambiguity"])
            ),
            price_of_robustness=(
                None
                if payload.get("price_of_robustness") is None
                else float(payload["price_of_robustness"])
            ),
            solver_runtime_ms=(
                None
                if payload.get("solver_runtime_ms") is None
                else float(payload["solver_runtime_ms"])
            ),
            solver_backend=(
                None if payload.get("solver_backend") is None else str(payload["solver_backend"])
            ),
            reproducibility=(
                payload.get("reproducibility", {})
                if isinstance(payload.get("reproducibility", {}), Mapping)
                else {}
            ),
            metadata=(
                payload.get("metadata", {})
                if isinstance(payload.get("metadata", {}), Mapping)
                else {}
            ),
        )


@dataclass(frozen=True, slots=True)
class AuctionReserveProblem:
    """Canonical robust public-reserve auction payload."""

    contract_id: ClassVar[str] = "foundry.optimization.auction_reserve_problem.v1"

    reserve_grid: tuple[float, ...]
    scenario_revenues: tuple[tuple[float, ...], ...] | None = None
    valuation_scenarios: tuple[tuple[tuple[float, ...], ...], ...] | None = None
    scenario_probabilities: tuple[float, ...] | None = None
    seller_value: float = 0.0
    reserve_visibility: Literal["public", "secret"] = "public"
    reserve_timing: Literal["pre_commit", "revisable"] = "pre_commit"
    value_model: Literal[
        "independent_private_values",
        "common_value",
        "interdependent_values",
    ] = "independent_private_values"
    bidder_risk: Literal["risk_neutral", "risk_averse"] = "risk_neutral"
    prior_regime: Literal["symmetric", "heterogeneous"] = "symmetric"
    entry_regime: Literal["fixed", "endogenous"] = "fixed"
    supported_formats: tuple[str, ...] = (
        "second_price",
        "english",
        "first_price",
        "dutch",
    )
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.reserve_grid:
            raise ValueError("AuctionReserveProblem.reserve_grid must be non-empty")

        if (self.scenario_revenues is None) == (self.valuation_scenarios is None):
            raise ValueError(
                "exactly one of scenario_revenues or valuation_scenarios must be provided"
            )

        scenario_count: int
        width = len(self.reserve_grid)
        if self.scenario_revenues is not None:
            if not self.scenario_revenues:
                raise ValueError("scenario_revenues must be non-empty")
            if any(len(row) != width for row in self.scenario_revenues):
                raise ValueError("scenario_revenues rows must match reserve_grid length")
            scenario_count = len(self.scenario_revenues)
        else:
            assert self.valuation_scenarios is not None
            if not self.valuation_scenarios:
                raise ValueError("valuation_scenarios must be non-empty")
            bidder_count: int | None = None
            for scenario in self.valuation_scenarios:
                if not scenario:
                    raise ValueError("each valuation scenario must include at least one profile")
                for profile in scenario:
                    if not profile:
                        raise ValueError("each valuation profile must include at least one bidder")
                    if bidder_count is None:
                        bidder_count = len(profile)
                    elif len(profile) != bidder_count:
                        raise ValueError(
                            "valuation_scenarios must have a consistent bidder dimension"
                        )
            scenario_count = len(self.valuation_scenarios)

        if self.scenario_probabilities is not None:
            if len(self.scenario_probabilities) != scenario_count:
                raise ValueError("scenario_probabilities must match the number of scenarios")
            if any(float(prob) < 0.0 for prob in self.scenario_probabilities):
                raise ValueError("scenario_probabilities must be non-negative")
            if sum(float(prob) for prob in self.scenario_probabilities) <= 0.0:
                raise ValueError("scenario_probabilities must have positive total mass")

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> AuctionReserveProblem:
        reserve_grid_raw = payload.get("reserve_grid")
        if not isinstance(reserve_grid_raw, (list, tuple)):
            raise ValueError("auction payload must include sequence field 'reserve_grid'")

        scenario_revenues_raw = payload.get("scenario_revenues")
        valuation_scenarios_raw = payload.get("valuation_scenarios")
        probabilities_raw = payload.get("scenario_probabilities")
        supported_formats_raw = payload.get(
            "supported_formats",
            ["second_price", "english", "first_price", "dutch"],
        )

        if scenario_revenues_raw is not None and not isinstance(
            scenario_revenues_raw, (list, tuple)
        ):
            raise ValueError("auction payload field 'scenario_revenues' must be a sequence")
        if valuation_scenarios_raw is not None and not isinstance(
            valuation_scenarios_raw, (list, tuple)
        ):
            raise ValueError("auction payload field 'valuation_scenarios' must be a sequence")
        if probabilities_raw is not None and not isinstance(probabilities_raw, (list, tuple)):
            raise ValueError("auction payload field 'scenario_probabilities' must be a sequence")
        if not isinstance(supported_formats_raw, (list, tuple)):
            raise ValueError("auction payload field 'supported_formats' must be a sequence")

        return cls(
            reserve_grid=_as_float_tuple(reserve_grid_raw, name="reserve_grid"),
            scenario_revenues=(
                _as_matrix_tuple(scenario_revenues_raw, name="scenario_revenues")
                if scenario_revenues_raw is not None
                else None
            ),
            valuation_scenarios=(
                tuple(
                    _as_matrix_tuple(scenario, name="valuation_scenarios")
                    for scenario in valuation_scenarios_raw
                )
                if valuation_scenarios_raw is not None
                else None
            ),
            scenario_probabilities=(
                _as_float_tuple(probabilities_raw, name="scenario_probabilities")
                if probabilities_raw is not None
                else None
            ),
            seller_value=float(payload.get("seller_value", 0.0)),
            reserve_visibility=str(payload.get("reserve_visibility", "public")),  # type: ignore[arg-type]
            reserve_timing=str(payload.get("reserve_timing", "pre_commit")),  # type: ignore[arg-type]
            value_model=str(payload.get("value_model", "independent_private_values")),  # type: ignore[arg-type]
            bidder_risk=str(payload.get("bidder_risk", "risk_neutral")),  # type: ignore[arg-type]
            prior_regime=str(payload.get("prior_regime", "symmetric")),  # type: ignore[arg-type]
            entry_regime=str(payload.get("entry_regime", "fixed")),  # type: ignore[arg-type]
            supported_formats=tuple(str(item) for item in supported_formats_raw),
            metadata=(
                payload.get("metadata", {})
                if isinstance(payload.get("metadata", {}), Mapping)
                else {}
            ),
        )


@dataclass(frozen=True, slots=True)
class AuctionFormatRecommendation:
    """Typed recommendation contract for auction format under reserve uncertainty."""

    contract_id: ClassVar[str] = "foundry.optimization.auction_format_recommendation.v1"

    uncertainty_regime: Literal["low", "moderate", "high"]
    recommended_format: str
    reserve_policy: str
    reserve_visibility: Literal["public", "secret", "revisable"]
    revenue_equivalence_holds: bool
    rationale: str
    compared_formats: tuple[str, ...] = ()
    blockers: tuple[str, ...] = ()
    diagnostics: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_choice(
            str(self.uncertainty_regime),
            name="AuctionFormatRecommendation.uncertainty_regime",
            allowed={"low", "moderate", "high"},
        )
        _require_choice(
            str(self.reserve_visibility),
            name="AuctionFormatRecommendation.reserve_visibility",
            allowed={"public", "secret", "revisable"},
        )
        if not self.recommended_format:
            raise ValueError("AuctionFormatRecommendation.recommended_format must be non-empty")
        if not self.reserve_policy:
            raise ValueError("AuctionFormatRecommendation.reserve_policy must be non-empty")
        if not self.rationale:
            raise ValueError("AuctionFormatRecommendation.rationale must be non-empty")

    def to_payload(self) -> dict[str, Any]:
        return {
            "uncertainty_regime": str(self.uncertainty_regime),
            "recommended_format": self.recommended_format,
            "reserve_policy": self.reserve_policy,
            "reserve_visibility": str(self.reserve_visibility),
            "revenue_equivalence_holds": bool(self.revenue_equivalence_holds),
            "rationale": self.rationale,
            "compared_formats": list(self.compared_formats),
            "blockers": list(self.blockers),
            "diagnostics": _jsonable(self.diagnostics),
        }

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> AuctionFormatRecommendation:
        compared_formats_raw = payload.get("compared_formats", ())
        blockers_raw = payload.get("blockers", ())
        return cls(
            uncertainty_regime=str(payload.get("uncertainty_regime", "moderate")),  # type: ignore[arg-type]
            recommended_format=str(payload.get("recommended_format", "")),
            reserve_policy=str(payload.get("reserve_policy", "")),
            reserve_visibility=str(payload.get("reserve_visibility", "public")),  # type: ignore[arg-type]
            revenue_equivalence_holds=bool(payload.get("revenue_equivalence_holds", False)),
            rationale=str(payload.get("rationale", "")),
            compared_formats=tuple(str(item) for item in compared_formats_raw)
            if isinstance(compared_formats_raw, (list, tuple))
            else (),
            blockers=tuple(str(item) for item in blockers_raw)
            if isinstance(blockers_raw, (list, tuple))
            else (),
            diagnostics=(
                payload.get("diagnostics", {})
                if isinstance(payload.get("diagnostics", {}), Mapping)
                else {}
            ),
        )


@dataclass(frozen=True, slots=True)
class MomentDROConstraint:
    """Scalarized stochastic constraint used by moment-constrained DRO."""

    name: str
    constraint_class: Literal["budget", "capacity", "equity"]
    nominal_coefficients: tuple[float, ...]
    shock_matrix: tuple[tuple[float, ...], ...]
    threshold: float
    epsilon: float
    intercept: float = 0.0
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("MomentDROConstraint.name must be non-empty")
        _require_choice(
            str(self.constraint_class),
            name="MomentDROConstraint.constraint_class",
            allowed={"budget", "capacity", "equity"},
        )
        if not self.nominal_coefficients:
            raise ValueError("MomentDROConstraint.nominal_coefficients must be non-empty")
        if not self.shock_matrix:
            raise ValueError("MomentDROConstraint.shock_matrix must be non-empty")
        if any(len(row) != len(self.nominal_coefficients) for row in self.shock_matrix):
            raise ValueError(
                "MomentDROConstraint.shock_matrix row width must match nominal_coefficients"
            )
        if not 0.0 < float(self.epsilon) < 1.0:
            raise ValueError("MomentDROConstraint.epsilon must be in (0, 1)")

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> MomentDROConstraint:
        return cls(
            name=str(payload.get("name", "")),
            constraint_class=str(payload.get("constraint_class", "budget")),  # type: ignore[arg-type]
            nominal_coefficients=_as_float_tuple(
                payload.get("nominal_coefficients", ()),
                name="nominal_coefficients",
            ),
            shock_matrix=_as_matrix_tuple(
                payload.get("shock_matrix", ()),
                name="shock_matrix",
            ),
            threshold=float(payload.get("threshold", 0.0)),
            epsilon=float(payload.get("epsilon", 0.05)),
            intercept=float(payload.get("intercept", 0.0)),
            metadata=(
                payload.get("metadata", {})
                if isinstance(payload.get("metadata", {}), Mapping)
                else {}
            ),
        )


@dataclass(frozen=True, slots=True)
class MomentDROProblem:
    """Canonical problem contract for moment-constrained DRO optimization."""

    contract_id: ClassVar[str] = "foundry.optimization.moment_dro_problem.v1"
    problem_id: str
    objective_vector: tuple[float, ...]
    shock_mean: tuple[float, ...] = ()
    shock_covariance: tuple[tuple[float, ...], ...] = ()
    constraints: tuple[MomentDROConstraint, ...] = ()
    objective: Literal["minimize", "maximize"] = "minimize"
    bounds: tuple[tuple[float, float], ...] = ()
    deterministic_constraint_matrix: tuple[tuple[float, ...], ...] = ()
    deterministic_constraint_rhs: tuple[float, ...] = ()
    gamma_mean: float = 0.0
    gamma_covariance: float = 1.0
    confidence_level: float = 0.95
    ambiguity_set_type: Literal[
        "moment_mean_cov",
        "moment_mean_cov_support",
        "moment_higher_order",
        "wasserstein",
        "phi_divergence",
        "hybrid",
    ] = "moment_mean_cov"
    support_description: str | None = None
    moment_estimator: str = "sample_mean"
    covariance_estimator: str = "sample_covariance"
    sample_size: int | None = None
    effective_sample_size: float | None = None
    regime_model: str | None = None
    historical_shocks: tuple[tuple[float, ...], ...] = ()
    regime_ids: tuple[str, ...] = ()
    regime_probabilities: Mapping[str, float] = field(default_factory=dict)
    higher_moment_orders: tuple[int, ...] = ()
    backtest_hits: Mapping[str, tuple[int, ...]] = field(default_factory=dict)
    tail_fraction: float = 0.1
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.problem_id:
            raise ValueError("MomentDROProblem.problem_id must be non-empty")
        if not self.objective_vector:
            raise ValueError("MomentDROProblem.objective_vector must be non-empty")
        _require_choice(
            str(self.objective),
            name="MomentDROProblem.objective",
            allowed={"minimize", "maximize"},
        )
        historical_width = 0
        if self.historical_shocks:
            historical_width = len(self.historical_shocks[0])
            if historical_width == 0:
                raise ValueError("historical_shocks rows must be non-empty")
            if any(len(row) != historical_width for row in self.historical_shocks):
                raise ValueError("historical_shocks rows must all have the same length")
            if self.regime_ids and len(self.regime_ids) != len(self.historical_shocks):
                raise ValueError("regime_ids must match historical_shocks row count")

        if not self.shock_mean and not self.historical_shocks:
            raise ValueError("MomentDROProblem requires shock_mean or historical_shocks")
        n_shocks = len(self.shock_mean) if self.shock_mean else historical_width
        if self.shock_mean and historical_width and len(self.shock_mean) != historical_width:
            raise ValueError("shock_mean dimension must match historical_shocks width")
        if self.shock_covariance:
            if len(self.shock_covariance) != n_shocks:
                raise ValueError("MomentDROProblem.shock_covariance must match shock dimension")
            if any(len(row) != n_shocks for row in self.shock_covariance):
                raise ValueError("MomentDROProblem.shock_covariance must be square")
        elif not self.historical_shocks:
            raise ValueError("MomentDROProblem requires shock_covariance or historical_shocks")
        if not self.constraints:
            raise ValueError("MomentDROProblem.constraints must be non-empty")
        n_vars = len(self.objective_vector)
        for constraint in self.constraints:
            if len(constraint.nominal_coefficients) != n_vars:
                raise ValueError("constraint nominal_coefficients must match n_vars")
            if len(constraint.shock_matrix) != n_shocks:
                raise ValueError("constraint shock_matrix must match shock dimension")
        if self.bounds and len(self.bounds) != n_vars:
            raise ValueError("MomentDROProblem.bounds must match n_vars")
        if any(len(row) != 2 for row in self.bounds):
            raise ValueError("MomentDROProblem.bounds rows must have width 2")
        if self.deterministic_constraint_matrix:
            if len(self.deterministic_constraint_matrix) != len(self.deterministic_constraint_rhs):
                raise ValueError(
                    "deterministic_constraint_matrix row count must equal deterministic_constraint_rhs length"
                )
            if any(len(row) != n_vars for row in self.deterministic_constraint_matrix):
                raise ValueError("deterministic_constraint_matrix row width must match n_vars")
        if self.gamma_mean < 0.0 or self.gamma_covariance < 0.0:
            raise ValueError("gamma_mean and gamma_covariance must be >= 0")
        if not 0.0 < float(self.confidence_level) <= 1.0:
            raise ValueError("confidence_level must be in (0, 1]")
        if self.sample_size is not None and int(self.sample_size) < 0:
            raise ValueError("sample_size must be >= 0")
        if self.regime_probabilities:
            if any(float(value) < 0.0 for value in self.regime_probabilities.values()):
                raise ValueError("regime_probabilities must be non-negative")
            if sum(float(value) for value in self.regime_probabilities.values()) <= 0.0:
                raise ValueError("regime_probabilities must have positive mass")
        if any(int(order) < 3 for order in self.higher_moment_orders):
            raise ValueError("higher_moment_orders must contain orders >= 3")
        if not 0.0 < float(self.tail_fraction) < 1.0:
            raise ValueError("tail_fraction must be in (0, 1)")
        for name, hits in self.backtest_hits.items():
            if any(hit not in {0, 1} for hit in hits):
                raise ValueError(f"backtest_hits[{name}] must contain only 0/1 indicators")

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> MomentDROProblem:
        constraints_raw = payload.get("constraints")
        if not isinstance(constraints_raw, list):
            raise ValueError("MomentDROProblem payload must include list field 'constraints'")
        return cls(
            problem_id=str(payload.get("problem_id", "moment_dro_problem")),
            objective_vector=_as_float_tuple(
                payload.get("objective_vector", ()),
                name="objective_vector",
            ),
            shock_mean=_as_float_tuple(payload.get("shock_mean", ()), name="shock_mean"),
            shock_covariance=_as_matrix_tuple(
                payload.get("shock_covariance", ()),
                name="shock_covariance",
            ),
            constraints=tuple(
                MomentDROConstraint.from_mapping(item)
                for item in constraints_raw
                if isinstance(item, Mapping)
            ),
            objective=str(payload.get("objective", "minimize")),  # type: ignore[arg-type]
            bounds=_as_matrix_tuple(payload.get("bounds", ()), name="bounds"),
            deterministic_constraint_matrix=_as_matrix_tuple(
                payload.get("deterministic_constraint_matrix", ()),
                name="deterministic_constraint_matrix",
            ),
            deterministic_constraint_rhs=_as_float_tuple(
                payload.get("deterministic_constraint_rhs", ()),
                name="deterministic_constraint_rhs",
            ),
            gamma_mean=float(payload.get("gamma_mean", 0.0)),
            gamma_covariance=float(payload.get("gamma_covariance", 1.0)),
            confidence_level=float(payload.get("confidence_level", 0.95)),
            ambiguity_set_type=str(payload.get("ambiguity_set_type", "moment_mean_cov")),  # type: ignore[arg-type]
            support_description=(
                None
                if payload.get("support_description") is None
                else str(payload["support_description"])
            ),
            moment_estimator=str(payload.get("moment_estimator", "sample_mean")),
            covariance_estimator=str(payload.get("covariance_estimator", "sample_covariance")),
            sample_size=(
                None if payload.get("sample_size") is None else int(payload["sample_size"])
            ),
            effective_sample_size=(
                None
                if payload.get("effective_sample_size") is None
                else float(payload["effective_sample_size"])
            ),
            regime_model=(
                None if payload.get("regime_model") is None else str(payload["regime_model"])
            ),
            historical_shocks=_as_matrix_tuple(
                payload.get("historical_shocks", ()),
                name="historical_shocks",
            ),
            regime_ids=_as_str_tuple(payload.get("regime_ids", ()), name="regime_ids"),
            regime_probabilities=_as_float_mapping(
                payload.get("regime_probabilities"),
                name="regime_probabilities",
            ),
            higher_moment_orders=_as_int_tuple(
                payload.get("higher_moment_orders", ()),
                name="higher_moment_orders",
            ),
            backtest_hits=_as_binary_hits_mapping(
                payload.get("backtest_hits"),
                name="backtest_hits",
            ),
            tail_fraction=float(payload.get("tail_fraction", 0.1)),
            metadata=(
                payload.get("metadata", {})
                if isinstance(payload.get("metadata", {}), Mapping)
                else {}
            ),
        )


@dataclass(frozen=True, slots=True)
class OptimizationAmbiguityCertificate:
    """Typed ambiguity payload for optimization outputs that must avoid false precision."""

    mode: Literal[
        "none",
        "leader_objective_bounds",
        "optimistic_exact",
        "pessimistic_exact",
    ] = "none"
    incumbent_lower: float | None = None
    incumbent_upper: float | None = None
    optimistic_value: float | None = None
    pessimistic_value: float | None = None
    delta_near_opt: float | None = None
    follower_global_gap: float | None = None
    trigger: str | None = None
    witness_count: int = 0
    note: str = ""

    def to_payload(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "incumbent_lower": self.incumbent_lower,
            "incumbent_upper": self.incumbent_upper,
            "optimistic_value": self.optimistic_value,
            "pessimistic_value": self.pessimistic_value,
            "delta_near_opt": self.delta_near_opt,
            "follower_global_gap": self.follower_global_gap,
            "trigger": self.trigger,
            "witness_count": int(self.witness_count),
            "note": self.note,
        }


@dataclass(frozen=True, slots=True)
class OptimizationResult:
    """Unified result contract for optimization methods."""

    contract_id: ClassVar[str] = "foundry.optimization.result.v1"
    status: SolverStatus
    objective_value: float | None
    variables: Mapping[str, float]
    constraints_satisfied: Mapping[str, bool]
    solver_iterations: int
    solver_gap: float | None
    solver_time_seconds: float
    uncertainty: UncertaintyEnvelope | None = None
    ambiguity_certificate: AmbiguityCertificate | OptimizationAmbiguityCertificate | None = None
    format_recommendation: AuctionFormatRecommendation | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @property
    def is_optimal(self) -> bool:
        return self.status is SolverStatus.OPTIMAL

    @property
    def is_feasible(self) -> bool:
        return self.status in {SolverStatus.OPTIMAL, SolverStatus.FEASIBLE}

    def to_payload(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "objective_value": self.objective_value,
            "variables": {k: float(v) for k, v in sorted(self.variables.items())},
            "constraints_satisfied": {
                k: bool(v) for k, v in sorted(self.constraints_satisfied.items())
            },
            "solver_iterations": int(self.solver_iterations),
            "solver_gap": self.solver_gap,
            "solver_time_seconds": float(self.solver_time_seconds),
            "uncertainty": (
                self.uncertainty.model_dump(mode="python", exclude_none=True)
                if self.uncertainty is not None
                else None
            ),
            "ambiguity_certificate": (
                self.ambiguity_certificate.to_payload()
                if self.ambiguity_certificate is not None
                else None
            ),
            "format_recommendation": (
                self.format_recommendation.to_payload()
                if self.format_recommendation is not None
                else None
            ),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True, slots=True)
class IOModelResult:
    """Result payload for Leontief input-output modeling."""

    contract_id: ClassVar[str] = "foundry.optimization.io_result.v1"
    status: SolverStatus
    output_vector: tuple[float, ...]
    multipliers: tuple[float, ...]
    leontief_inverse: tuple[tuple[float, ...], ...]
    sector_names: tuple[str, ...]
    total_output: float
    direct_requirements: tuple[tuple[float, ...], ...]
    is_productive: bool
    uncertainty: UncertaintyEnvelope | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def to_payload(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "output_vector": [float(v) for v in self.output_vector],
            "multipliers": [float(v) for v in self.multipliers],
            "leontief_inverse": [[float(v) for v in row] for row in self.leontief_inverse],
            "sector_names": list(self.sector_names),
            "total_output": float(self.total_output),
            "direct_requirements": [[float(v) for v in row] for row in self.direct_requirements],
            "is_productive": bool(self.is_productive),
            "uncertainty": (
                self.uncertainty.model_dump(mode="python", exclude_none=True)
                if self.uncertainty is not None
                else None
            ),
            "metadata": dict(self.metadata),
        }


@runtime_checkable
class OptimizationMethod(Protocol):
    """Optimization method public type."""

    def solve(self, problem: OptimizationProblem) -> OptimizationResult: ...


@runtime_checkable
class InputOutputMethod(Protocol):
    """Input output method public type."""

    def solve(
        self,
        technical_coefficients: Any,
        final_demand: Any,
        sector_names: list[str] | None = None,
    ) -> IOModelResult: ...


def parse_optimization_problem(state: Any) -> OptimizationProblem:
    """Parse optimization problem helper."""
    if isinstance(state, OptimizationProblem):
        return state
    if isinstance(state, Mapping):
        if "problem" in state and isinstance(state["problem"], Mapping):
            return OptimizationProblem.from_mapping(state["problem"])
        return OptimizationProblem.from_mapping(state)
    raise TypeError("state must be OptimizationProblem or mapping")


def parse_auction_reserve_problem(state: Any) -> AuctionReserveProblem:
    """Parse auction reserve optimization payloads."""

    if isinstance(state, AuctionReserveProblem):
        return state
    if isinstance(state, Mapping):
        if "auction_reserve_problem" in state and isinstance(
            state["auction_reserve_problem"],
            Mapping,
        ):
            return AuctionReserveProblem.from_mapping(state["auction_reserve_problem"])
        if "problem" in state and isinstance(state["problem"], Mapping):
            return AuctionReserveProblem.from_mapping(state["problem"])
        return AuctionReserveProblem.from_mapping(state)
    raise TypeError("state must be AuctionReserveProblem or mapping")


def parse_moment_dro_problem(state: Any) -> MomentDROProblem:
    """Parse moment-constrained DRO problem helper."""

    if isinstance(state, MomentDROProblem):
        return state
    if isinstance(state, Mapping):
        if "moment_dro_problem" in state:
            payload = state["moment_dro_problem"]
            if isinstance(payload, MomentDROProblem):
                return payload
            if isinstance(payload, Mapping):
                return MomentDROProblem.from_mapping(payload)
        if "problem" in state:
            payload = state["problem"]
            if isinstance(payload, MomentDROProblem):
                return payload
            if isinstance(payload, Mapping):
                return MomentDROProblem.from_mapping(payload)
        return MomentDROProblem.from_mapping(state)
    raise TypeError("state must be MomentDROProblem or mapping")


def emit_optimization_metrics(
    *,
    method: str,
    status: SolverStatus,
    duration_seconds: float,
) -> None:
    """Emit optimization metrics helper."""
    metrics = get_metrics()
    helper = getattr(metrics, "record_optimization_solve", None)
    if callable(helper):
        helper(
            method=method,
            status=status.value,
            duration_seconds=float(duration_seconds),
        )
        return
    hist = getattr(metrics, "optimization_solve_duration_seconds", None)
    if hist is not None and hasattr(hist, "record"):
        hist.record(float(duration_seconds), {"method": method, "status": status.value})
    counter = getattr(metrics, "optimization_solve_status", None)
    if counter is not None and hasattr(counter, "add"):
        counter.add(1, {"method": method, "status": status.value})


__all__ = [
    "AllocationItem",
    "AmbiguityCertificate",
    "AuctionFormatRecommendation",
    "AuctionReserveProblem",
    "ConstraintCertificate",
    "DiagnosticResult",
    "IOModelResult",
    "InputOutputMethod",
    "MomentBound",
    "MomentDROConstraint",
    "MomentDROProblem",
    "OptimizationAmbiguityCertificate",
    "OptimizationMethod",
    "OptimizationProblem",
    "OptimizationResult",
    "ResourceConstraint",
    "emit_optimization_metrics",
    "parse_auction_reserve_problem",
    "parse_moment_dro_problem",
    "parse_optimization_problem",
]
