"""Tests for cost estimation model."""

from __future__ import annotations

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.contracts.foundry import (
    ProgramGraph,
    ProgramNode,
    ProgramOp,
)
from polisyos.foundry.methods.cost_model import CostBudget, CostModel
from polisyos.ir.kernel import DEFAULT_MECHANISM_REGISTRY


def _make_ir_ref() -> ArtifactRef:
    return ArtifactRef(
        artifact_id=ArtifactID.from_sha256_hex("0" * 64),
        kind="ir.trinity_bundle",
        media_type="application/json",
    )


def _make_graph_with_mechanisms(n_mechanisms: int) -> ProgramGraph:
    nodes = [
        ProgramNode(
            node_id=f"mech_{idx}",
            node_kind="op",
            mechanism_type="income_tax",
            op=ProgramOp(op_kind="apply_mechanism"),
        )
        for idx in range(n_mechanisms)
    ]
    return ProgramGraph(
        ir_ref=_make_ir_ref(),
        nodes=nodes,
        edges=[],
        entrypoints=[],
    )


class TestCostModelBasics:
    def test_estimate_returns_positive_values(self) -> None:
        model = CostModel()
        graph = _make_graph_with_mechanisms(3)

        estimate = model.estimate(graph, n_agents=1000, time_steps=10)

        assert estimate.estimated_compile_ms > 0
        assert estimate.estimated_run_ms > 0
        assert estimate.estimated_total_ms > 0
        assert estimate.estimated_memory_mb > 0

    def test_cost_scales_with_agents(self) -> None:
        model = CostModel()
        graph = _make_graph_with_mechanisms(2)

        estimate_1k = model.estimate(graph, n_agents=1000, time_steps=10)
        estimate_10k = model.estimate(graph, n_agents=10000, time_steps=10)

        ratio = estimate_10k.estimated_total_ms / estimate_1k.estimated_total_ms
        assert 5 < ratio < 15

    def test_cost_scales_with_time_steps(self) -> None:
        model = CostModel()
        graph = _make_graph_with_mechanisms(2)

        estimate_10 = model.estimate(graph, n_agents=1000, time_steps=10)
        estimate_100 = model.estimate(graph, n_agents=1000, time_steps=100)

        ratio = estimate_100.estimated_run_ms / estimate_10.estimated_run_ms
        assert 8 < ratio < 12

    def test_per_mechanism_breakdown(self) -> None:
        model = CostModel()
        graph = _make_graph_with_mechanisms(3)

        estimate = model.estimate(graph, n_agents=1000, time_steps=10)

        assert len(estimate.per_mechanism_costs) == 3
        assert all(cost > 0 for cost in estimate.per_mechanism_costs.values())

    def test_multiplier_keys_match_registry(self) -> None:
        registry_keys = set(DEFAULT_MECHANISM_REGISTRY.mechanisms.keys())
        multiplier_keys = set(CostModel.MECHANISM_MULTIPLIERS.keys())
        assert multiplier_keys.issubset(registry_keys)


class TestCostModelBudget:
    def test_within_budget(self) -> None:
        model = CostModel()
        graph = _make_graph_with_mechanisms(1)
        budget = CostBudget(max_total_ms=100_000)

        estimate = model.estimate(graph, n_agents=100, time_steps=10, budget=budget)

        assert estimate.exceeds_budget is False
        assert len(estimate.budget_violations) == 0
        assert estimate.budget_utilization < 1.0
        assert estimate.upper_bound() == estimate.estimated_total_ms
        assert estimate.compute_upper_bound() == estimate.estimated_total_ms
        assert estimate.supports_budget(budget)
        assert estimate.resource_vector()["total_ms_upper"] == estimate.estimated_total_ms

    def test_exceeds_budget(self) -> None:
        model = CostModel()
        graph = _make_graph_with_mechanisms(10)
        budget = CostBudget(max_total_ms=1)

        estimate = model.estimate(graph, n_agents=10000, time_steps=100, budget=budget)

        assert estimate.exceeds_budget is True
        assert len(estimate.budget_violations) > 0
        assert estimate.budget_utilization > 1.0
        assert not estimate.supports_budget(budget)


class TestCostModelCalibration:
    def test_update_from_telemetry(self) -> None:
        model = CostModel()

        graph = ProgramGraph(
            ir_ref=_make_ir_ref(),
            nodes=[
                ProgramNode(
                    node_id="mech_0",
                    node_kind="op",
                    mechanism_type="custom_mechanism",
                    op=ProgramOp(op_kind="apply_mechanism"),
                )
            ],
            edges=[],
            entrypoints=[],
        )

        estimate_before = model.estimate(graph, n_agents=1000, time_steps=1)

        model.update_from_telemetry("custom_mechanism", actual_ms=500.0)

        estimate_after = model.estimate(graph, n_agents=1000, time_steps=1)

        assert (
            estimate_after.per_mechanism_costs["mech_0"]
            > estimate_before.per_mechanism_costs["mech_0"]
        )

    def test_exponential_moving_average(self) -> None:
        model = CostModel()

        model.update_from_telemetry("test_mech", actual_ms=100.0)
        model.update_from_telemetry("test_mech", actual_ms=100.0)
        model.update_from_telemetry("test_mech", actual_ms=200.0)

        stats = model.export_historical_stats()
        assert 100 < stats["test_mech"] < 200

    def test_calibration_status(self) -> None:
        model = CostModel()
        model.update_from_telemetry("mech_a", 50.0)
        model.update_from_telemetry("mech_a", 55.0)
        model.update_from_telemetry("mech_b", 30.0)

        status = model.get_calibration_status()

        assert "mech_a" in status["calibrated_mechanisms"]
        assert "mech_b" in status["calibrated_mechanisms"]
        assert status["calibration_counts"]["mech_a"] == 2
        assert status["calibration_counts"]["mech_b"] == 1
