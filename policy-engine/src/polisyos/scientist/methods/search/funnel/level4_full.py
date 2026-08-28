"""Level 4 full-fidelity funnel adapter."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from polisyos.common.logger import get_logger
from polisyos.ir import FailureSeverity, TypedFailureCard
from polisyos.scientist.methods.search.actionable_side_information import (
    ActionableSideInformation,
    persist_actionable_side_information,
    resolve_actionable_store,
)
from polisyos.scientist.methods.search.funnel.types import (
    FunnelStage,
    FunnelStageResult,
    UncertaintyEnvelope,
    UncertaintyEstimate,
    UncertaintyType,
)
from polisyos.scientist.methods.search.stages import ExpensiveStage
from polisyos.scientist.orchestration.workflows.engine_base import WorkflowEngine

logger = get_logger(__name__)


class Level4FullFidelity(FunnelStage):
    """Thin Level 4 adapter over the existing full expensive evaluation."""

    def __init__(
        self,
        workflow_engine: WorkflowEngine | None = None,
        *,
        expensive_stage: ExpensiveStage | None = None,
        estimated_cost_usd: float = 1.0,
        cost_per_second_usd: float = 0.01,
    ) -> None:
        if expensive_stage is None and workflow_engine is None:
            raise ValueError("Level4FullFidelity requires workflow_engine or expensive_stage")
        self._stage = expensive_stage or ExpensiveStage(workflow_engine=workflow_engine)  # type: ignore[arg-type]
        self._estimated_cost_usd = float(estimated_cost_usd)
        self._cost_per_second_usd = float(cost_per_second_usd)

    @property
    def stage_name(self) -> str:
        return "funnel_L4_full"

    @property
    def fidelity_level(self) -> int:
        return 4

    @property
    def estimated_cost_usd(self) -> float:
        return self._estimated_cost_usd

    def evaluate(
        self,
        candidate: dict[str, Any],
        context: dict[str, Any],
    ) -> FunnelStageResult:
        start = datetime.now(UTC)
        result = self._stage.evaluate(candidate, context)
        duration = max(
            result.duration_seconds,
            (datetime.now(UTC) - start).total_seconds(),
        )
        cards: list[TypedFailureCard] = []
        if not result.is_promising:
            cards.append(
                TypedFailureCard(
                    judge_name="L4_full",
                    failure_type="full_fidelity_rejection",
                    severity=FailureSeverity.WARNING,
                    description="Full-fidelity evaluation did not approve the candidate.",
                    metadata={"feedback": result.feedback},
                )
            )

        envelope = self._build_uncertainty_envelope(result.simulation_results)
        feedback = dict(result.feedback)
        feedback.setdefault("fidelity_level", self.fidelity_level)
        side_information = ActionableSideInformation(
            candidate_id=str(
                candidate.get("candidate_id")
                or candidate.get("id")
                or candidate.get("name")
                or "unknown_candidate"
            ),
            profiler_output={
                "stage_name": self.stage_name,
                "duration_seconds": float(duration),
            },
            timeout_diagnostics={
                key: feedback.get(key)
                for key in ("timed_out", "timeout", "timeout_occurred")
                if key in feedback
            },
            identifiability_blockers=[],
            sensitivity_failures=[],
            subgroup_harm_notes=[],
            legality_failures=[],
            transport_failures=[],
            discovery_ambiguity_notes=[],
            policy_budget_explanation={},
            compute_budget_explanation={
                "level4_usd": max(
                    self._estimated_cost_usd,
                    duration * self._cost_per_second_usd,
                ),
                "duration_seconds": float(duration),
            },
            metadata={"approved": result.is_promising},
        )
        store = resolve_actionable_store(context=context)
        side_information_ref = None
        audit_refs = []
        if store is not None:
            side_information_ref = persist_actionable_side_information(
                store,
                side_information,
            )
            audit_refs.append(side_information_ref)
            feedback["actionable_side_information_ref"] = side_information_ref.model_dump(
                mode="json"
            )

        return FunnelStageResult(
            policy_candidate=result.policy_candidate,
            objective_value=result.objective_value,
            is_promising=result.is_promising,
            stage_name=self.stage_name,
            duration_seconds=duration,
            simulation_results=result.simulation_results,
            feedback=feedback,
            predicted_score=result.predicted_score,
            actual_score=result.actual_score,
            uncertainty_envelope=envelope,
            failure_cards=cards,
            compute_actual_usd=max(self._estimated_cost_usd, duration * self._cost_per_second_usd),
            fidelity_level=self.fidelity_level,
            audit_refs=audit_refs,
            actionable_side_information_ref=side_information_ref,
        )

    def _build_uncertainty_envelope(
        self,
        simulation_results: dict[str, Any],
    ) -> UncertaintyEnvelope:
        bootstrap = simulation_results.get("bootstrap", {})
        effect = abs(float(simulation_results.get("ate", 0.0) or 0.0))
        ci_width = bootstrap.get("ci_width")
        statistical_level = 0.5
        if ci_width is not None:
            try:
                ci_width_float = abs(float(ci_width))
            except (TypeError, ValueError):
                ci_width_float = 0.0
            if effect > 0.0:
                statistical_level = min(1.0, ci_width_float / (2.0 * effect))
            else:
                statistical_level = 1.0 if ci_width_float > 0.0 else 0.5

        return UncertaintyEnvelope.from_partial(
            {
                UncertaintyType.STATISTICAL: UncertaintyEstimate(
                    level=statistical_level,
                    source="full bootstrap/full estimator stack",
                    quantification_method="full_fidelity_bootstrap",
                    is_reducible=True,
                    recommended_action="Run refutation and holdout checks before promotion.",
                ),
                UncertaintyType.MODEL: UncertaintyEstimate(
                    level=0.25,
                    source="full-fidelity estimator stack",
                    quantification_method="full_fidelity_proxy",
                    is_reducible=True,
                    recommended_action="Run stress and hidden-holdout evaluation.",
                ),
                UncertaintyType.MEASUREMENT: UncertaintyEstimate(
                    level=0.5,
                    source="not directly assessed by level 4 adapter",
                    quantification_method="adapter_default",
                    is_reducible=True,
                ),
                UncertaintyType.TRANSPORT: UncertaintyEstimate(
                    level=0.5,
                    source="transport robustness not directly assessed by level 4 adapter",
                    quantification_method="adapter_default",
                    is_reducible=True,
                ),
            }
        )
