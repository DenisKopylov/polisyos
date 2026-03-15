from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, ClassVar, Mapping, Protocol, runtime_checkable

from polisyos.core.observability import get_metrics
from polisyos.foundry.methods.backends.protocol import SolverStatus
from polisyos.ir.analytics.uncertainty import UncertaintyEnvelope


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
                        (
                            f"constraint '{constraint.constraint_id}' references "
                            f"unknown item '{item_id}'"
                        )
                    )

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "OptimizationProblem":
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
                payload.get("metadata", {})
                if isinstance(payload.get("metadata", {}), dict)
                else {}
            ),
        )


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
    def solve(self, problem: OptimizationProblem) -> OptimizationResult:
        ...


@runtime_checkable
class InputOutputMethod(Protocol):
    def solve(
        self,
        technical_coefficients: Any,
        final_demand: Any,
        sector_names: list[str] | None = None,
    ) -> IOModelResult:
        ...


def parse_optimization_problem(state: Any) -> OptimizationProblem:
    if isinstance(state, OptimizationProblem):
        return state
    if isinstance(state, Mapping):
        if "problem" in state and isinstance(state["problem"], Mapping):
            return OptimizationProblem.from_mapping(state["problem"])
        return OptimizationProblem.from_mapping(state)
    raise TypeError("state must be OptimizationProblem or mapping")


def emit_optimization_metrics(
    *,
    method: str,
    status: SolverStatus,
    duration_seconds: float,
) -> None:
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
    "IOModelResult",
    "InputOutputMethod",
    "OptimizationMethod",
    "OptimizationProblem",
    "OptimizationResult",
    "ResourceConstraint",
    "emit_optimization_metrics",
    "parse_optimization_problem",
]
