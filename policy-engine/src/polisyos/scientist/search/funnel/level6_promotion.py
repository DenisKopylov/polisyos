"""Level 6 promotion funnel stage."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from polisyos.common.logger import get_logger
from polisyos.scientist.search.actionable_side_information import (
    ActionableSideInformation,
    persist_actionable_side_information,
    resolve_actionable_store,
)
from polisyos.scientist.search.failure_cards import FailureSeverity, TypedFailureCard
from polisyos.scientist.search.funnel.types import FunnelStage, FunnelStageResult
from polisyos.scientist.search.uncertainty import UncertaintyEnvelope

logger = get_logger(__name__)

_PromotionRunner = Callable[[dict[str, Any], dict[str, Any]], Any]


class Level6PromotionStage(FunnelStage):
    """Terminal funnel stage that interprets promotion results generically."""

    def __init__(
        self,
        *,
        promotion_runner: _PromotionRunner | None = None,
        estimated_cost_usd: float = 0.05,
        cost_per_second_usd: float = 0.002,
        allow_noop_complete: bool = False,
        store=None,
    ) -> None:
        self._promotion_runner = promotion_runner
        self._estimated_cost_usd = float(estimated_cost_usd)
        self._cost_per_second_usd = float(cost_per_second_usd)
        self._allow_noop_complete = bool(allow_noop_complete)
        self._store = store

    @property
    def stage_name(self) -> str:
        return "funnel_L6_promotion"

    @property
    def fidelity_level(self) -> int:
        return 6

    @property
    def estimated_cost_usd(self) -> float:
        return self._estimated_cost_usd

    def evaluate(
        self,
        candidate: dict[str, Any],
        context: dict[str, Any],
    ) -> FunnelStageResult:
        start = datetime.now(UTC)
        prior_result = _prior_result(context)
        objective_value = float(prior_result.objective_value) if prior_result is not None else 0.0
        promotion_payload = context.get("promotion_result")
        if promotion_payload is None and self._promotion_runner is not None:
            promotion_payload = self._promotion_runner(candidate, context)

        failure_cards: list[TypedFailureCard] = []
        terminal_action = "complete"
        audit_refs = list(getattr(prior_result, "audit_refs", []))
        feedback = dict(getattr(prior_result, "feedback", {}) or {})
        degradation_mode = str(context.get("funnel_degradation_mode", "normal"))

        if degradation_mode in {"no_promotion", "reduced_judge", "auto_cap"}:
            terminal_action = "defer_to_human"
            failure_cards.append(
                TypedFailureCard(
                    judge_name="L6_promotion",
                    failure_type="degraded_mode_promotion_cap",
                    severity=FailureSeverity.WARNING,
                    description=(
                        f"Promotion is capped by degraded funnel mode '{degradation_mode}'."
                    ),
                )
            )
            promotion_payload = None

        if terminal_action != "complete":
            feedback["promotion_mode"] = "degraded_cap"
        elif _looks_like_policy_promotion_result(promotion_payload):
            judge_verdict = promotion_payload.judge_verdict
            promotion_decision = promotion_payload.promotion_decision
            readiness_contract = promotion_payload.readiness_contract
            readiness_ref = getattr(promotion_payload, "readiness_ref", None)
            failure_cards.extend(judge_verdict.blocking_failures)
            failure_cards.extend(judge_verdict.warnings)
            if promotion_decision.promoted:
                terminal_action = "complete"
            elif judge_verdict.composite_decision == "defer_to_human":
                terminal_action = "defer_to_human"
            else:
                terminal_action = "reject"
                if not judge_verdict.blocking_failures:
                    failure_cards.append(
                        TypedFailureCard(
                            judge_name="L6_promotion",
                            failure_type="promotion_denied",
                            severity=FailureSeverity.WARNING,
                            description=promotion_decision.reason,
                        )
                    )
            if readiness_ref is not None:
                audit_refs.append(readiness_ref)
            feedback.update(
                {
                    "promotion_reason": promotion_decision.reason,
                    "judge_verdict": judge_verdict.model_dump(mode="json"),
                    "decision_readiness_contract": readiness_contract.model_dump(mode="json"),
                    "readiness_level": readiness_contract.readiness_level.value,
                }
            )
        elif isinstance(promotion_payload, dict):
            raw_action = str(
                promotion_payload.get("decision")
                or promotion_payload.get("final_action")
                or promotion_payload.get("recommended_action")
                or ("complete" if promotion_payload.get("promoted") else "reject")
            )
            terminal_action = (
                raw_action
                if raw_action in {"complete", "reject", "defer_to_human", "defer"}
                else "reject"
            )
            if terminal_action != "complete":
                failure_cards.append(
                    TypedFailureCard(
                        judge_name="L6_promotion",
                        failure_type="promotion_denied",
                        severity=FailureSeverity.WARNING,
                        description=str(
                            promotion_payload.get("reason")
                            or promotion_payload.get("message")
                            or "Promotion payload denied candidate advancement."
                        ),
                    )
                )
            feedback.update(dict(promotion_payload))
        elif promotion_payload is None:
            if self._allow_noop_complete:
                terminal_action = "complete"
                feedback["promotion_mode"] = "noop_complete"
            else:
                terminal_action = "defer_to_human"
                failure_cards.append(
                    TypedFailureCard(
                        judge_name="L6_promotion",
                        failure_type="promotion_runtime_unavailable",
                        severity=FailureSeverity.WARNING,
                        description="Promotion runtime was not attached to the Level 6 funnel stage.",
                        remediation_hint="Attach a promotion_result or promotion_runner to Level 6.",
                    )
                )
        else:
            terminal_action = "reject"
            failure_cards.append(
                TypedFailureCard(
                    judge_name="L6_promotion",
                    failure_type="promotion_payload_unsupported",
                    severity=FailureSeverity.WARNING,
                    description=(
                        "Level 6 received an unsupported promotion payload and rejected promotion."
                    ),
                )
            )

        duration = (datetime.now(UTC) - start).total_seconds()
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
                "terminal_action": terminal_action,
            },
            timeout_diagnostics={},
            identifiability_blockers=[],
            sensitivity_failures=[
                card.description
                for card in failure_cards
                if card.severity == FailureSeverity.BLOCKER
            ],
            subgroup_harm_notes=[],
            legality_failures=[],
            transport_failures=[],
            discovery_ambiguity_notes=[],
            policy_budget_explanation={},
            compute_budget_explanation={
                "level6_wall_seconds": float(duration),
                "level6_usd": max(self._estimated_cost_usd, duration * self._cost_per_second_usd),
            },
            metadata={"terminal_action": terminal_action},
        )
        store = resolve_actionable_store(context=context, store=self._store)
        side_information_ref = None
        if store is not None:
            side_information_ref = persist_actionable_side_information(
                store,
                side_information,
            )
            audit_refs.append(side_information_ref)

        feedback.update(
            {
                "fidelity_level": self.fidelity_level,
                "funnel_action": terminal_action,
                "actionable_side_information_ref": None
                if side_information_ref is None
                else side_information_ref.model_dump(mode="json"),
            }
        )
        return FunnelStageResult(
            policy_candidate=candidate,
            objective_value=objective_value,
            is_promising=terminal_action != "reject",
            stage_name=self.stage_name,
            duration_seconds=duration,
            timestamp=datetime.now(UTC),
            simulation_results=getattr(prior_result, "simulation_results", {}),
            feedback=feedback,
            predicted_score=getattr(prior_result, "predicted_score", None),
            actual_score=getattr(prior_result, "actual_score", objective_value),
            uncertainty_envelope=(
                prior_result.uncertainty_envelope
                if prior_result is not None
                else UncertaintyEnvelope.unknown()
            ),
            failure_cards=failure_cards,
            compute_actual_usd=max(
                self._estimated_cost_usd,
                duration * self._cost_per_second_usd,
            ),
            fidelity_level=self.fidelity_level,
            audit_refs=audit_refs,
            actionable_side_information_ref=side_information_ref,
            terminal_action=terminal_action,
        )


def _prior_result(context: dict[str, Any]) -> FunnelStageResult | None:
    for key in ("_funnel_L6_result", "_funnel_L5_result", "_funnel_L4_result"):
        result = context.get(key)
        if isinstance(result, FunnelStageResult):
            return result
    return None


def _looks_like_policy_promotion_result(value: Any) -> bool:
    return all(
        hasattr(value, attribute)
        for attribute in (
            "judge_verdict",
            "promotion_decision",
            "readiness_contract",
        )
    )


__all__ = ["Level6PromotionStage"]
