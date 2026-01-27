from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    from polisyos.core.contracts.foundry import ProgramGraph, ProgramNode


class CostEstimate(BaseModel):
    """Estimated execution cost with confidence metrics."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    estimated_compile_ms: int = Field(
        ..., ge=0, description="Estimated JAX/XLA compilation time"
    )
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


@dataclass
class CostBudget:
    """Budget constraints for cost gating."""

    max_total_ms: int = 60_000
    max_memory_mb: int = 8_192
    max_compile_ms: int = 30_000
    max_per_mechanism_ms: int = 10_000


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
        program_graph: "ProgramGraph",
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
            "high"
            if calibrated_ratio > 0.8
            else "medium"
            if calibrated_ratio > 0.3
            else "low"
        )

        return CostEstimate(
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
        )

    def _is_mechanism_node(self, node: "ProgramNode") -> bool:
        if node.node_kind == "mechanism":
            return True
        if node.node_kind == "op" and node.op and node.op.op_kind == "apply_mechanism":
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
