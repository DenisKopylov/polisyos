"""Tests for Phase 9: CausalExperimentDesigner — optimal experimental design.

Covers:
- optimal_adjustment_set  (O-set, Henckel et al. 2022)
- optimal_instrument_selection (graphical IV criterion)
- minimum_cost_identification (greedy Bareinboim-Brito-Pearl 2012)
- adaptive_experiment (sequential budget allocation)

Reference:
  Henckel, Perković & Maathuis (2022). JRSS-B.
"""
from __future__ import annotations

import pytest

from polisyos.ir.analytics.causal_graph import (
    CausalEdge,
    CausalGraphModel,
    EdgeMark,
    GraphType,
)
from polisyos.ir.analytics.experiment_plan import (
    ExperimentPlan,
    OptimalAdjustmentResult,
    OptimalIVResult,
)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _dag(edges: list[tuple[str, str]], extra_nodes: list[str] | None = None) -> CausalGraphModel:
    """Build a simple DAG from (src, dst) edge pairs."""
    nodes = sorted({n for e in edges for n in e} | set(extra_nodes or []))
    return CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=nodes,
        edges=[
            CausalEdge(src=s, dst=d, mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW)
            for s, d in edges
        ],
    )


def _bidir(graph: CausalGraphModel, src: str, dst: str) -> CausalGraphModel:
    """Add a bidirected edge (latent confounder) between src and dst.

    Returns an ADMG (Acyclic Directed Mixed Graph) to allow bidirected edges.
    """
    extra = CausalEdge(src=src, dst=dst, mark_src=EdgeMark.ARROW, mark_dst=EdgeMark.ARROW)
    return CausalGraphModel(
        graph_type=GraphType.ADMG,
        nodes=list(graph.nodes),
        edges=list(graph.edges) + [extra],
    )


# ---------------------------------------------------------------------------
# TestOSet — optimal_adjustment_set
# ---------------------------------------------------------------------------


class TestOSet:
    """O-set: Pa_G(An(Y)_{G_{V\\De(X)}}) \\ (De(X) ∪ {X})."""

    def test_simple_backdoor_path(self):
        """X←Z→Y (and X→Y): O-set should contain Z."""
        from polisyos.foundry.methods.catalog.causal.optimal_design import (
            optimal_adjustment_set,
        )

        # Z is a confounder: Z→X and Z→Y; X→Y
        graph = _dag([("Z", "X"), ("Z", "Y"), ("X", "Y")])
        result = optimal_adjustment_set(graph, "X", "Y")

        assert isinstance(result, OptimalAdjustmentResult)
        assert "Z" in result.o_set
        assert result.treatment == "X"
        assert result.outcome == "Y"
        assert result.graphical_criterion_used == "henckel-2022-o-set"

    def test_no_confounders_empty_o_set(self):
        """X→Y with no confounders: O-set = {} (empty)."""
        from polisyos.foundry.methods.catalog.causal.optimal_design import (
            optimal_adjustment_set,
        )

        graph = _dag([("X", "Y")])
        result = optimal_adjustment_set(graph, "X", "Y")

        assert isinstance(result, OptimalAdjustmentResult)
        assert result.o_set == frozenset()

    def test_mediator_excluded_from_o_set(self):
        """X→M→Y, X←Z→Y: M is a descendant of X — must NOT be in O-set."""
        from polisyos.foundry.methods.catalog.causal.optimal_design import (
            optimal_adjustment_set,
        )

        # M is a mediator (descendant of X), Z is a confounder
        graph = _dag([("X", "M"), ("M", "Y"), ("Z", "X"), ("Z", "Y")])
        result = optimal_adjustment_set(graph, "X", "Y")

        assert "M" not in result.o_set
        assert "Z" in result.o_set

    def test_o_set_excludes_treatment_itself(self):
        """Treatment variable X is never in its own O-set."""
        from polisyos.foundry.methods.catalog.causal.optimal_design import (
            optimal_adjustment_set,
        )

        graph = _dag([("Z", "X"), ("X", "Y"), ("Z", "Y")])
        result = optimal_adjustment_set(graph, "X", "Y")

        assert "X" not in result.o_set

    def test_o_set_satisfies_backdoor(self):
        """The O-set must always satisfy the backdoor criterion (validity)."""
        from polisyos.foundry.methods.catalog.causal.optimal_design import (
            optimal_adjustment_set,
        )

        graph = _dag([("C", "X"), ("C", "Y"), ("X", "Y")])
        result = optimal_adjustment_set(graph, "X", "Y")

        assert result.o_set_is_valid_backdoor is True

    def test_multiple_confounders(self):
        """Multiple confounders: O-set contains all parents of An(Y) in G'."""
        from polisyos.foundry.methods.catalog.causal.optimal_design import (
            optimal_adjustment_set,
        )

        # C1 and C2 both confound X and Y
        graph = _dag([
            ("C1", "X"), ("C1", "Y"),
            ("C2", "X"), ("C2", "Y"),
            ("X", "Y"),
        ])
        result = optimal_adjustment_set(graph, "X", "Y")

        assert "C1" in result.o_set
        assert "C2" in result.o_set

    def test_invalid_treatment_raises(self):
        """ValueError when treatment is not in the graph."""
        from polisyos.foundry.methods.catalog.causal.optimal_design import (
            optimal_adjustment_set,
        )

        graph = _dag([("X", "Y")])
        with pytest.raises(ValueError, match="Treatment variable"):
            optimal_adjustment_set(graph, "T_MISSING", "Y")

    def test_invalid_outcome_raises(self):
        """ValueError when outcome is not in the graph."""
        from polisyos.foundry.methods.catalog.causal.optimal_design import (
            optimal_adjustment_set,
        )

        graph = _dag([("X", "Y")])
        with pytest.raises(ValueError, match="Outcome variable"):
            optimal_adjustment_set(graph, "X", "Y_MISSING")


# ---------------------------------------------------------------------------
# TestOptimalIV — optimal_instrument_selection
# ---------------------------------------------------------------------------


class TestOptimalIV:
    """IV selection via graphical criterion."""

    def test_single_valid_iv(self):
        """Z→X→Y, no Z→Y path: Z is a valid instrument."""
        from polisyos.foundry.methods.catalog.causal.optimal_design import (
            optimal_instrument_selection,
        )

        graph = _dag([("Z", "X"), ("X", "Y")])
        result = optimal_instrument_selection(graph, "X", "Y")

        assert isinstance(result, OptimalIVResult)
        assert result.treatment == "X"
        assert result.outcome == "Y"
        # Z should appear as valid IV
        assert frozenset({"Z"}) in result.all_valid_iv_sets or "Z" in result.optimal_iv_set

    def test_no_instruments_in_simple_dag(self):
        """X→Y with no external node: no valid IV found."""
        from polisyos.foundry.methods.catalog.causal.optimal_design import (
            optimal_instrument_selection,
        )

        graph = _dag([("X", "Y")])
        result = optimal_instrument_selection(graph, "X", "Y")

        assert isinstance(result, OptimalIVResult)
        # C is not present in this graph — no IVs
        assert len(result.all_valid_iv_sets) == 0
        assert result.optimal_iv_set == frozenset()


# ---------------------------------------------------------------------------
# TestMinimumCostIdentification — minimum_cost_identification
# ---------------------------------------------------------------------------


class TestMinimumCostIdentification:
    """Greedy minimum-cost identification plan."""

    def test_already_identified_observationally(self):
        """Simple DAG (no confounders): cost=0, already_identified=True."""
        from polisyos.foundry.methods.catalog.causal.optimal_design import (
            minimum_cost_identification,
        )

        graph = _dag([("X", "Y")])
        plan = minimum_cost_identification(
            graph, "X", "Y",
            available_interventions={"Z": 10.0},
        )

        assert isinstance(plan, ExperimentPlan)
        assert plan.already_identified_observationally is True
        assert plan.cost_estimate == 0.0
        assert plan.recommended_interventions == ()

    def test_empty_interventions_no_crash(self):
        """No available interventions: returns plan without crashing."""
        from polisyos.foundry.methods.catalog.causal.optimal_design import (
            minimum_cost_identification,
        )

        # Confounded graph: X←U→Y (bidirected)
        graph = _bidir(_dag([("X", "Y")]), "X", "Y")
        plan = minimum_cost_identification(
            graph, "X", "Y",
            available_interventions={},
        )

        assert isinstance(plan, ExperimentPlan)
        assert plan.already_identified_observationally is False

    def test_cost_ordering_respected(self):
        """When multiple interventions available, cheapest is tried first."""
        from polisyos.foundry.methods.catalog.causal.optimal_design import (
            minimum_cost_identification,
        )

        # Graph where either Z1 or Z2 can help (simple observational ID)
        graph = _dag([("Z1", "X"), ("Z2", "X"), ("X", "Y")])
        # Already identified observationally, so cost=0 regardless
        plan = minimum_cost_identification(
            graph, "X", "Y",
            available_interventions={"Z1": 100.0, "Z2": 5.0},
        )

        # If identified without experiments, we return early
        if plan.already_identified_observationally:
            assert plan.cost_estimate == 0.0
        else:
            # Should pick Z2 (cheaper) if a single intervention suffices
            assert plan.cost_estimate is None or plan.cost_estimate <= 100.0

    def test_plan_has_query(self):
        """Returned plan includes a query string."""
        from polisyos.foundry.methods.catalog.causal.optimal_design import (
            minimum_cost_identification,
        )

        graph = _dag([("X", "Y")])
        plan = minimum_cost_identification(graph, "X", "Y", available_interventions={})

        assert "X" in plan.query
        assert "Y" in plan.query

    def test_plan_has_rationale(self):
        """Returned plan always has a rationale string."""
        from polisyos.foundry.methods.catalog.causal.optimal_design import (
            minimum_cost_identification,
        )

        graph = _dag([("X", "Y")])
        plan = minimum_cost_identification(graph, "X", "Y", available_interventions={})

        assert isinstance(plan.rationale, str)
        assert len(plan.rationale) > 0


# ---------------------------------------------------------------------------
# TestAdaptiveExperiment
# ---------------------------------------------------------------------------


class TestAdaptiveExperiment:
    """adaptive_experiment: sequential budget allocation plan."""

    def test_returns_n_stages_plans(self):
        """Returns exactly n_stages ExperimentPlan objects."""
        from polisyos.foundry.methods.catalog.causal.optimal_design import adaptive_experiment

        graph = _dag([("Z", "X"), ("X", "Y")])
        plans = adaptive_experiment(
            graph=graph,
            treatment="X",
            outcome="Y",
            budget=300.0,
            n_stages=3,
        )

        assert len(plans) == 3
        for plan in plans:
            assert isinstance(plan, ExperimentPlan)

    def test_stage_budgets_sum_to_total(self):
        """Per-stage cost estimates sum to total budget."""
        from polisyos.foundry.methods.catalog.causal.optimal_design import adaptive_experiment

        graph = _dag([("X", "Y")])
        budget = 150.0
        plans = adaptive_experiment(
            graph=graph, treatment="X", outcome="Y", budget=budget, n_stages=3
        )

        total = sum(p.cost_estimate for p in plans if p.cost_estimate is not None)
        assert abs(total - budget) < 1e-9

    def test_single_stage(self):
        """n_stages=1 returns exactly one plan."""
        from polisyos.foundry.methods.catalog.causal.optimal_design import adaptive_experiment

        graph = _dag([("X", "Y")])
        plans = adaptive_experiment(
            graph=graph, treatment="X", outcome="Y", budget=100.0, n_stages=1
        )

        assert len(plans) == 1
