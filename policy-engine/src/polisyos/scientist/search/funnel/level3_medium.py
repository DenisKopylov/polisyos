"""Level 3 — Medium-Fidelity Evaluation.

Cost: 5 s – 2 min.  The critical neglected middle layer.

Wraps ``WorkflowEngine.run()`` with reduced-data and reduced-bootstrap
configurations.  Produces comparable intermediate metrics for
ASHA / Successive-Halving pruning.

**Cardinal rule**: Level 3 metrics are routing signals, never promotion
evidence.  No candidate may be promoted based solely on Level 3 results.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Dict, List

from polisyos.common.logger import get_logger
from polisyos.scientist.search.funnel.types import (
    FunnelStage,
    FunnelStageResult,
    TypedFailureCard,
    UncertaintyEnvelope,
    UncertaintyEstimate,
    UncertaintyType,
)
from polisyos.scientist.workflows.engine_base import WorkflowEngine

logger = get_logger(__name__)

# Metrics that change meaning at reduced fidelity and MUST NOT be used
# for pruning decisions (blueprint §8.2, Level 3 causal distortion warning).
_FORBIDDEN_PRUNING_METRICS = [
    "ci_width",
    "hte_heterogeneity",
    "subgroup_harm_magnitude",
    "bootstrap_stability",
]


class Level3MediumFidelity(FunnelStage):
    """Funnel Level 3: reduced-fidelity workflow evaluation."""

    def __init__(
        self,
        workflow_engine: WorkflowEngine,
        subsample_fraction: float = 0.2,
        bootstrap_draws: int = 50,
        estimator_tier: str = "linear",
        scenario_set: str = "coarse",
        top_k_subgroups: int = 3,
        cost_per_second_usd: float = 0.001,
    ):
        """
        Args:
            workflow_engine: The ``WorkflowEngine`` to run.
            subsample_fraction: Fraction of data to use (stratified).
            bootstrap_draws: Number of bootstrap draws (vs 500+ at L4).
            estimator_tier: Estimator family — ``"linear"`` or ``"matching"``.
            scenario_set: Scenario grid density — ``"coarse"`` or ``"medium"``.
            top_k_subgroups: Number of subgroups to evaluate (not full HTE).
            cost_per_second_usd: Rough cost estimate per second of wall time.
        """
        self._engine = workflow_engine
        self._subsample_fraction = subsample_fraction
        self._bootstrap_draws = bootstrap_draws
        self._estimator_tier = estimator_tier
        self._scenario_set = scenario_set
        self._top_k_subgroups = top_k_subgroups
        self._cost_per_second = cost_per_second_usd

    # ------------------------------------------------------------------
    # FunnelStage interface
    # ------------------------------------------------------------------

    @property
    def stage_name(self) -> str:
        return "funnel_L3_medium"

    @property
    def fidelity_level(self) -> int:
        return 3

    @property
    def estimated_cost_usd(self) -> float:
        return 0.05

    # ------------------------------------------------------------------
    # Evaluate
    # ------------------------------------------------------------------

    def evaluate(
        self,
        candidate: Dict[str, Any],
        context: Dict[str, Any],
    ) -> FunnelStageResult:
        start = datetime.now(UTC)
        cards: List[TypedFailureCard] = []

        # Build initial_state with reduced-fidelity configuration.
        initial_state = self._build_reduced_state(candidate, context)

        try:
            result = self._engine.run(initial_state)
        except Exception as exc:
            logger.error("L3 workflow failed: %s", exc)
            duration = (datetime.now(UTC) - start).total_seconds()
            cards.append(
                TypedFailureCard(
                    judge_name="L3_medium",
                    failure_type="workflow_error",
                    severity="warning",
                    description=f"Medium-fidelity workflow failed: {exc}",
                    remediation_hint="Check workflow engine logs for details.",
                )
            )
            return FunnelStageResult(
                policy_candidate=candidate,
                objective_value=float("inf"),
                is_promising=False,
                stage_name=self.stage_name,
                duration_seconds=duration,
                uncertainty_envelope=UncertaintyEnvelope.unknown(
                    source="L3 workflow error",
                ),
                failure_cards=cards,
                compute_actual_usd=duration * self._cost_per_second,
                fidelity_level=self.fidelity_level,
                feedback={"verdict": "REJECT", "issues": [{"message": str(exc)}]},
            )

        duration = (datetime.now(UTC) - start).total_seconds()

        sim_results = result.get("simulation_results", {})
        feedback = result.get("feedback", {})
        verdict = feedback.get("verdict", "UNKNOWN")

        # Compute objective (same formula as ExpensiveStage).
        objective = self._compute_objective(sim_results)
        is_promising = verdict == "APPROVE"

        # Build uncertainty envelope from reduced bootstrap.
        envelope = self._build_uncertainty_envelope(sim_results)

        # Enforce cardinal rule: tag output as routing-only.
        feedback = dict(feedback)
        feedback["level3_disclaimer"] = "routing_signal_only"
        feedback["forbidden_for_pruning"] = _FORBIDDEN_PRUNING_METRICS
        feedback["fidelity_config"] = {
            "subsample_fraction": self._subsample_fraction,
            "bootstrap_draws": self._bootstrap_draws,
            "estimator_tier": self._estimator_tier,
            "scenario_set": self._scenario_set,
            "top_k_subgroups": self._top_k_subgroups,
        }

        return FunnelStageResult(
            policy_candidate=candidate,
            objective_value=objective,
            is_promising=is_promising,
            stage_name=self.stage_name,
            duration_seconds=duration,
            simulation_results=sim_results,
            feedback=feedback,
            uncertainty_envelope=envelope,
            failure_cards=cards,
            compute_actual_usd=duration * self._cost_per_second,
            fidelity_level=self.fidelity_level,
            actual_score=objective,
        )

    # ------------------------------------------------------------------
    # State construction
    # ------------------------------------------------------------------

    def _build_reduced_state(
        self,
        candidate: Dict[str, Any],
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Build initial_state with reduced-fidelity config overrides."""
        state: Dict[str, Any] = {
            "ir": candidate,
            "user_request": context.get("user_request", ""),
            "optimize": True,
        }

        # Propagate non-reserved context keys.
        for k, v in context.items():
            if k not in ("ir", "user_request") and not k.startswith("_funnel_"):
                state[k] = v

        # Inject reduced-fidelity configuration.
        state.setdefault("data_config", {})
        state["data_config"]["subsample_fraction"] = self._subsample_fraction
        state["data_config"]["stratified"] = True

        state.setdefault("estimation_config", {})
        state["estimation_config"]["estimator"] = self._estimator_tier
        state["estimation_config"]["n_bootstrap"] = self._bootstrap_draws

        state.setdefault("scenario_config", {})
        state["scenario_config"]["grid"] = self._scenario_set

        state.setdefault("subgroup_config", {})
        state["subgroup_config"]["top_k"] = self._top_k_subgroups

        state.setdefault("model_config", {})
        state["model_config"]["scm_complexity"] = "reduced"

        # Flag that this is a medium-fidelity evaluation.
        state["_fidelity_level"] = self.fidelity_level

        return state

    # ------------------------------------------------------------------
    # Objective computation
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_objective(results: Dict[str, Any]) -> float:
        """Same formula as ``ExpensiveStage._compute_default_objective``."""
        gdp = results.get("gdp_change", 0.0)
        deficit = abs(min(results.get("gov_balance", 0.0), 0))
        return -(gdp - 0.5 * deficit)

    # ------------------------------------------------------------------
    # Uncertainty envelope
    # ------------------------------------------------------------------

    def _build_uncertainty_envelope(
        self,
        sim_results: Dict[str, Any],
    ) -> UncertaintyEnvelope:
        """Build envelope from reduced bootstrap results."""
        envelope = UncertaintyEnvelope.unknown(source="L3 medium fidelity")

        # Statistical uncertainty from bootstrap (if available).
        bootstrap_stats = sim_results.get("bootstrap", {})
        ci_width = bootstrap_stats.get("ci_width")
        if ci_width is not None:
            # Wider CI → higher uncertainty.  Normalize relative to effect size.
            effect = abs(sim_results.get("ate", 0.0))
            if effect > 0:
                relative_width = min(1.0, ci_width / (2 * effect))
            else:
                relative_width = 1.0

            envelope = envelope.with_update(
                UncertaintyType.STATISTICAL,
                UncertaintyEstimate(
                    level=relative_width,
                    source=f"reduced bootstrap ({self._bootstrap_draws} draws)",
                    quantification_method="bootstrap_reduced",
                    is_reducible=True,
                    recommended_action="Advance to L4 for full bootstrap.",
                ),
            )

        # Model uncertainty from estimator tier.
        envelope = envelope.with_update(
            UncertaintyType.MODEL,
            UncertaintyEstimate(
                level=0.7 if self._estimator_tier == "linear" else 0.5,
                source=f"estimator tier: {self._estimator_tier}",
                quantification_method="estimator_complexity_proxy",
                is_reducible=True,
                recommended_action="Advance to L4 for flagship estimators.",
            ),
        )

        return envelope

    # ------------------------------------------------------------------
    # Adapter for SearchController
    # ------------------------------------------------------------------

    def as_stage_b_callable(self):
        """Return a callable compatible with SearchController's stage_b_evaluator."""

        def _evaluate(candidate: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
            result = self.evaluate(candidate, context)
            return {
                "simulation_results": result.simulation_results,
                "feedback": result.feedback,
                "objective_value": result.objective_value,
                "is_promising": result.is_promising,
                "_funnel_result": result,
            }

        return _evaluate
