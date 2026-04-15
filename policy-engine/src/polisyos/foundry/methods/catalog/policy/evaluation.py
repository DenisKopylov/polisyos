"""Public policy evaluation module API."""
from __future__ import annotations

from typing import Any, ClassVar, Mapping

import numpy as np

from polisyos.core.observability.determinism import DeterminismTier
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


def _result_slot() -> frozenset[SlotSpec]:
    return frozenset({SlotSpec("result", SlotType.SCALAR, Unit("result", "json"))})


# ---------------------------------------------------------------------------
# Budget Impact Analysis
# ---------------------------------------------------------------------------


@foundry_method(
    namespace="policy.evaluation",
    version="1.0.0",
    tags={"policy", "evaluation", "budget-impact", "fiscal", "structural"},
)
class BudgetImpactEstimator:
    """Estimate the fiscal budget impact of a proposed policy change."""
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="budget_impact",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("revenue_effects", SlotType.VECTOR, Unit("currency", "amount"), shape=("n_periods",)),
                SlotSpec("expenditure_effects", SlotType.VECTOR, Unit("currency", "amount"), shape=("n_periods",)),
            }
        ),
        output_slots=_result_slot(),
        parameters=(
            ParameterSpec(name="discount_rate", default=0.03, bounds=(0.0, 1.0)),
        ),
        fidelity=FidelityLevel.MEDIUM,
        complexity=ComplexityClass.O_N,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Budget impact analysis: net fiscal position from revenue and expenditure effects.",
        tags=frozenset({"policy", "evaluation", "budget-impact", "fiscal", "structural"}),
        assumptions={"additive": "Revenue and expenditure effects are additive"},
        determinism_tier=DeterminismTier.LIBRARY_DETERMINISTIC,
        required_deps=("numpy",),
        when_to_use="Fiscal analysis; estimate total cost/savings of policy over budget horizon",
        output_interpretation="Total direct cost to government. Positive = net spending, negative = net saving.",
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        revenue = np.asarray(state["revenue_effects"], dtype=float)
        expenditure = np.asarray(state["expenditure_effects"], dtype=float)
        if revenue.shape != expenditure.shape or revenue.ndim != 1:
            raise ValueError("revenue_effects and expenditure_effects must be 1D with same length")

        discount_rate = float(params.get("discount_rate", 0.03))
        n = len(revenue)
        discount_factors = 1.0 / (1.0 + discount_rate) ** np.arange(n, dtype=float)

        net_fiscal = revenue - expenditure
        pv_revenue = float(np.sum(revenue * discount_factors))
        pv_expenditure = float(np.sum(expenditure * discount_factors))
        pv_net = pv_revenue - pv_expenditure
        cumulative_net = np.cumsum(net_fiscal)

        return {
            "result": {
                "pv_net_fiscal_position": pv_net,
                "pv_revenue": pv_revenue,
                "pv_expenditure": pv_expenditure,
                "annual_net_fiscal": net_fiscal.tolist(),
                "cumulative_net_fiscal": cumulative_net.tolist(),
                "n_periods": n,
            }
        }


# ---------------------------------------------------------------------------
# Policy Scorecard
# ---------------------------------------------------------------------------


@foundry_method(
    namespace="policy.evaluation",
    version="1.0.0",
    tags={"policy", "evaluation", "scorecard", "structural"},
)
class PolicyScorecardEstimator:
    """Build multi-metric scorecards for comparing policy alternatives."""
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="scorecard",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("scores", SlotType.VECTOR, Unit("score", "value"), shape=("n_criteria",)),
                SlotSpec("weights", SlotType.VECTOR, Unit("weight", "value"), shape=("n_criteria",)),
            }
        ),
        output_slots=_result_slot(),
        parameters=(
            ParameterSpec(name="normalize", default=True),
        ),
        fidelity=FidelityLevel.MEDIUM,
        complexity=ComplexityClass.O_N,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Multi-dimensional policy scorecard with weighted criteria.",
        tags=frozenset({"policy", "evaluation", "scorecard", "multi-criteria", "structural"}),
        assumptions={"linear": "Weighted linear combination of normalized scores"},
        determinism_tier=DeterminismTier.LIBRARY_DETERMINISTIC,
        required_deps=("numpy",),
        when_to_use="Rapid policy ranking across multiple criteria when full MCDA is not required; stakeholder-driven scoring exercises",
        output_interpretation="Composite score between 0 and 1 (if inputs normalized). Higher = better overall performance across weighted criteria.",
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        scores = np.asarray(state["scores"], dtype=float)
        weights = np.asarray(state["weights"], dtype=float)
        if scores.shape != weights.shape or scores.ndim != 1:
            raise ValueError("scores and weights must be 1D with same length")

        normalize = bool(params.get("normalize", True))
        if normalize:
            weight_sum = float(np.sum(weights))
            if weight_sum <= 0:
                raise ValueError("weights must sum to a positive value")
            norm_weights = weights / weight_sum
        else:
            norm_weights = weights

        composite = float(np.sum(norm_weights * scores))
        contributions = (norm_weights * scores).tolist()

        return {
            "result": {
                "composite_score": composite,
                "contributions": contributions,
                "normalized_weights": norm_weights.tolist(),
                "n_criteria": len(scores),
            }
        }


# ---------------------------------------------------------------------------
# Ex-Ante Simulation
# ---------------------------------------------------------------------------


@foundry_method(
    namespace="policy.evaluation",
    version="1.0.0",
    tags={"policy", "evaluation", "ex-ante", "counterfactual", "structural"},
)
class ExAnteSimulationEstimator:
    """Project candidate policy outcomes by replaying interventions before deployment."""
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="ex_ante_simulation",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("baseline", SlotType.VECTOR, Unit("value", "amount"), shape=("n_agents",)),
                SlotSpec("scenario", SlotType.VECTOR, Unit("value", "amount"), shape=("n_agents",)),
            }
        ),
        output_slots=_result_slot(),
        parameters=(
            ParameterSpec(name="poverty_line", default=None),
        ),
        fidelity=FidelityLevel.MEDIUM,
        complexity=ComplexityClass.O_N,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Ex-ante policy simulation comparing baseline vs scenario distributions.",
        tags=frozenset({"policy", "evaluation", "ex-ante", "counterfactual", "simulation", "structural"}),
        assumptions={"paired": "Baseline and scenario values are paired by agent"},
        determinism_tier=DeterminismTier.LIBRARY_DETERMINISTIC,
        required_deps=("numpy",),
        when_to_use="Pre-implementation distributional impact assessment; comparing policy scenarios before rollout using microsimulation data",
        output_interpretation="Mean/median changes and quintile breakdowns show who gains and loses. Positive mean_change = average improvement under scenario.",
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        baseline = np.asarray(state["baseline"], dtype=float)
        scenario = np.asarray(state["scenario"], dtype=float)
        if baseline.shape != scenario.shape or baseline.ndim != 1:
            raise ValueError("baseline and scenario must be 1D with same length")

        diff = scenario - baseline
        n = len(baseline)

        result: dict[str, Any] = {
            "mean_baseline": float(np.mean(baseline)),
            "mean_scenario": float(np.mean(scenario)),
            "mean_change": float(np.mean(diff)),
            "median_change": float(np.median(diff)),
            "pct_gainers": float(np.mean(diff > 0)),
            "pct_losers": float(np.mean(diff < 0)),
            "total_change": float(np.sum(diff)),
            "n_agents": n,
        }

        # Distributional impact by quintile
        baseline_quintiles = np.percentile(baseline, [20, 40, 60, 80])
        quintile_labels = np.digitize(baseline, baseline_quintiles)
        quintile_means = []
        for q in range(5):
            mask = quintile_labels == q
            if np.any(mask):
                quintile_means.append(float(np.mean(diff[mask])))
            else:
                quintile_means.append(0.0)
        result["quintile_mean_change"] = quintile_means

        poverty_line = params.get("poverty_line")
        if poverty_line is not None:
            pl = float(poverty_line)
            result["baseline_poverty_rate"] = float(np.mean(baseline < pl))
            result["scenario_poverty_rate"] = float(np.mean(scenario < pl))

        return {"result": result}


__all__ = [
    "BudgetImpactEstimator",
    "ExAnteSimulationEstimator",
    "PolicyScorecardEstimator",
]
