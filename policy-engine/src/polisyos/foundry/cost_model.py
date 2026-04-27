"""Public foundry cost model module API."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, Field

from polisyos.common.timestamps import utc_now

if TYPE_CHECKING:
    from polisyos.core.contracts.foundry import ProgramGraph, ProgramNode


class CostEstimate(BaseModel):
    """Estimated execution cost with confidence metrics."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    point: float | None = Field(
        default=None,
        ge=0.0,
        description="Optional scalar point estimate in the declared unit.",
    )
    unit: str = Field(default="ms", min_length=1, description="Scalar estimate unit.")
    components: dict[str, float] = Field(
        default_factory=dict,
        description="Named scalar cost components in the declared unit.",
    )

    estimated_compile_ms: int = Field(..., ge=0, description="Estimated JAX/XLA compilation time")
    estimated_run_ms: int = Field(..., ge=0, description="Estimated execution time per call")
    estimated_total_ms: int = Field(..., ge=0, description="Total estimated time")

    estimated_memory_mb: int = Field(..., ge=0, description="Peak memory usage estimate")
    estimated_flops: int = Field(..., ge=0, description="Floating point operations estimate")

    per_mechanism_costs: dict[str, int] = Field(
        default_factory=dict,
        description="mechanism_node_id -> estimated_ms",
    )

    exceeds_budget: bool = Field(default=False, description="True if estimate exceeds any budget")
    budget_utilization: float = Field(
        default=0.0,
        ge=0.0,
        description="Fraction of budget consumed (0.0 to 1.0+)",
    )
    budget_violations: list[str] = Field(
        default_factory=list,
        description="List of violated budget constraints",
    )

    confidence: str = Field(
        default="low",
        pattern=r"^(low|medium|high)$",
        description="Estimate confidence based on historical calibration",
    )
    lower: float | None = Field(default=None, ge=0.0, description="Optional scalar lower bound.")
    upper: float | None = Field(default=None, ge=0.0, description="Optional scalar upper bound.")
    coverage_confidence: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Coverage confidence for calibrated probabilistic bounds.",
    )
    delta: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Tail probability associated with probabilistic bounds.",
    )
    bound_type: str = Field(
        default="HEURISTIC_POINT_ESTIMATE",
        pattern=r"^(EXACT_BOUND|CALIBRATED_PROBABILISTIC_BOUND|HEURISTIC_POINT_ESTIMATE|UNKNOWN)$",
        description="Semantics of lower/upper bounds for certificate generation.",
    )
    calibration_scope: str | None = Field(
        default=None,
        description="Domain where the calibration claim is valid.",
    )
    estimator_version: str = Field(
        default="foundry.cost_model.v1",
        description="Version label for the estimator that produced this estimate.",
    )
    estimator_hash: str | None = Field(default=None, description="Optional estimator artifact hash.")
    assumptions: list[str] = Field(
        default_factory=list,
        description="Assumptions required for the estimate or bound claim.",
    )
    valid_for: dict[str, Any] = Field(
        default_factory=dict,
        description="Input/task/method domain where this estimate is intended to apply.",
    )
    includes_advisor_overhead: bool = Field(
        default=False,
        description="Whether advisor and feature extraction overhead are included.",
    )
    created_at: datetime = Field(default_factory=utc_now)

    def upper_bound(self, delta: float | None = None) -> float:
        """Return the scalar upper cost bound used for budget feasibility checks."""
        del delta
        if self.upper is not None:
            return float(self.upper)
        if self.point is not None:
            return float(self.point)
        return float(self.estimated_total_ms)

    def lower_bound(self, delta: float | None = None) -> float:
        """Return the scalar lower cost bound when available, else the point estimate."""
        del delta
        if self.lower is not None:
            return float(self.lower)
        if self.point is not None:
            return float(self.point)
        return float(self.estimated_total_ms)

    def compute_upper_bound(self, delta: float | None = None) -> float:
        """Return an execution-time upper bound in milliseconds."""
        if self.unit == "ms":
            return self.upper_bound(delta=delta)
        return float(self.estimated_total_ms)

    def resource_vector(self, delta: float | None = None) -> dict[str, float]:
        """Return machine-readable resource costs for multi-resource budget checks."""
        vector = {
            "compile_ms": float(self.estimated_compile_ms),
            "run_ms": float(self.estimated_run_ms),
            "total_ms": float(self.estimated_total_ms),
            "memory_mb": float(self.estimated_memory_mb),
            "flops": float(self.estimated_flops),
        }
        vector.update({str(key): float(value) for key, value in self.components.items()})
        vector["total_ms_upper"] = float(self.compute_upper_bound(delta))
        return vector

    def supports_budget(self, budget: Any, delta: float | None = None) -> bool:
        """Return whether the estimate satisfies a CostBudget/BudgetSpec-like object."""
        vector = self.resource_vector(delta)
        max_total_ms = _budget_value(
            budget,
            "max_total_ms",
            "max_wall_time_ms",
            "spend_limit",
            "compute_limit",
        )
        max_memory_mb = _budget_value(budget, "max_memory_mb")
        max_compile_ms = _budget_value(budget, "max_compile_ms")
        if max_total_ms is not None and vector["total_ms_upper"] > max_total_ms:
            return False
        if max_memory_mb is not None and vector["memory_mb"] > max_memory_mb:
            return False
        if max_compile_ms is not None and vector["compile_ms"] > max_compile_ms:
            return False
        return True


@dataclass
class CostBudget:
    """Budget constraints for cost gating."""

    max_total_ms: int = 60_000
    max_memory_mb: int = 8_192
    max_compile_ms: int = 30_000
    max_per_mechanism_ms: int = 10_000


def _budget_value(budget: Any, *names: str) -> float | None:
    if budget is None:
        return None
    for name in names:
        if isinstance(budget, dict):
            value = budget.get(name)
        else:
            value = getattr(budget, name, None)
        if value is not None:
            return float(value)
    return None


class CostModel:
    """
    Heuristic cost estimator with self-calibration capability.

    Initial estimates use static heuristics. Over time, telemetry from
    actual executions updates the model for improved accuracy.
    """

    DEFAULT_COSTS = {
        "mechanism_base": 10,
        "agent_per_1000": 50,
        "timestep_overhead": 5,
        "vmap_overhead": 20,
        "scan_overhead": 10,
        "merge_overhead": 2,
        "compile_ratio": 0.15,
    }
    MECHANISM_MULTIPLIERS = {
        "income_tax": 1.0,
        "tax_subsidy": 0.8,
        "labor_market": 1.2,
        "queue": 0.6,
        "adaptive_agent": 3.0,
    }

    BYTES_PER_FLOAT = 8
    SLOTS_PER_AGENT = 50

    def __init__(
        self,
        historical_stats: dict[str, float] | None = None,
        costs: dict[str, float] | None = None,
    ):
        self._historical: dict[str, float] = dict(historical_stats or {})
        self._costs = {**self.DEFAULT_COSTS, **(costs or {})}
        self._calibration_count: dict[str, int] = {}

    def estimate(
        self,
        program_graph: ProgramGraph,
        n_agents: int,
        time_steps: int,
        *,
        budget: CostBudget | None = None,
    ) -> CostEstimate:
        budget = budget or CostBudget()

        per_mechanism: dict[str, int] = {}
        mechanism_total_ms = 0
        merge_node_count = 0
        mechanism_count = 0

        for node in program_graph.nodes:
            if self._is_mechanism_node(node):
                mechanism_count += 1
                mechanism_type = node.mechanism_type or "unknown"
                if mechanism_type in self._historical:
                    cost_ms = int(self._historical[mechanism_type])
                else:
                    cost_ms = self._estimate_mechanism_cost(mechanism_type, n_agents)
                per_mechanism[node.node_id] = cost_ms
                mechanism_total_ms += cost_ms
                continue
            if node.node_kind == "op" and node.op and node.op.op_kind == "merge_state":
                merge_node_count += 1

        overhead_ms = (
            merge_node_count * self._costs["merge_overhead"]
            + self._costs["vmap_overhead"]
            + self._costs["scan_overhead"]
        )
        run_ms = (mechanism_total_ms + overhead_ms) * time_steps
        run_ms += time_steps * self._costs["timestep_overhead"]

        compile_ms = int(run_ms * self._costs["compile_ratio"])
        total_ms = compile_ms + run_ms

        memory_bytes = n_agents * self.SLOTS_PER_AGENT * self.BYTES_PER_FLOAT
        memory_mb = max(memory_bytes // (1024 * 1024), 100)

        flops = n_agents * time_steps * mechanism_count * 1000

        violations: list[str] = []
        if total_ms > budget.max_total_ms:
            violations.append(f"total_ms ({total_ms}) > max ({budget.max_total_ms})")
        if memory_mb > budget.max_memory_mb:
            violations.append(f"memory_mb ({memory_mb}) > max ({budget.max_memory_mb})")
        if compile_ms > budget.max_compile_ms:
            violations.append(f"compile_ms ({compile_ms}) > max ({budget.max_compile_ms})")
        for node_id, cost in per_mechanism.items():
            if cost * time_steps > budget.max_per_mechanism_ms:
                violations.append(
                    f"mechanism {node_id} ({cost * time_steps}ms) > "
                    f"max ({budget.max_per_mechanism_ms})"
                )

        utilization = total_ms / budget.max_total_ms if budget.max_total_ms > 0 else 0.0
        calibrated_ratio = len(self._historical) / max(mechanism_count, 1)
        confidence = (
            "high" if calibrated_ratio > 0.8 else "medium" if calibrated_ratio > 0.3 else "low"
        )

        return CostEstimate(
            point=float(total_ms),
            components={
                "compile_ms": float(compile_ms),
                "run_ms": float(run_ms),
                "total_ms": float(total_ms),
                "memory_mb": float(memory_mb),
            },
            estimated_compile_ms=compile_ms,
            estimated_run_ms=run_ms,
            estimated_total_ms=total_ms,
            estimated_memory_mb=memory_mb,
            estimated_flops=flops,
            per_mechanism_costs=per_mechanism,
            exceeds_budget=len(violations) > 0,
            budget_utilization=utilization,
            budget_violations=violations,
            confidence=confidence,
            lower=float(total_ms),
            upper=float(total_ms),
            bound_type="HEURISTIC_POINT_ESTIMATE",
            assumptions=["Static heuristic estimate; no calibrated coverage guarantee."],
            includes_advisor_overhead=False,
        )

    def _is_mechanism_node(self, node: ProgramNode) -> bool:
        if node.node_kind in {"mechanism", "method"}:
            return True
        if (
            node.node_kind == "op"
            and node.op
            and node.op.op_kind
            in {
                "apply_mechanism",
                "apply_method",
            }
        ):
            return True
        return False

    def _estimate_mechanism_cost(self, mechanism_type: str, n_agents: int) -> int:
        base = self._costs["mechanism_base"]
        agent_cost = (n_agents / 1000) * self._costs["agent_per_1000"]
        multiplier = self.MECHANISM_MULTIPLIERS.get(mechanism_type, 1.0)
        return int((base + agent_cost) * multiplier)

    def update_from_telemetry(
        self,
        mechanism_type: str,
        actual_ms: float,
        n_agents: int | None = None,
    ) -> None:
        if n_agents and n_agents > 0:
            actual_ms = actual_ms * (1000 / n_agents)

        alpha = 0.3
        if mechanism_type not in self._historical:
            self._historical[mechanism_type] = actual_ms
            self._calibration_count[mechanism_type] = 1
        else:
            self._historical[mechanism_type] = (
                alpha * actual_ms + (1 - alpha) * self._historical[mechanism_type]
            )
            self._calibration_count[mechanism_type] = (
                self._calibration_count.get(mechanism_type, 0) + 1
            )

    def get_calibration_status(self) -> dict[str, object]:
        return {
            "calibrated_mechanisms": list(self._historical.keys()),
            "calibration_counts": dict(self._calibration_count),
            "total_calibration_points": sum(self._calibration_count.values()),
        }

    def export_historical_stats(self) -> dict[str, float]:
        return dict(self._historical)


def create_cost_model(historical_stats: dict[str, float] | None = None) -> CostModel:
    """Factory function for CostModel creation."""
    return CostModel(historical_stats=historical_stats)
