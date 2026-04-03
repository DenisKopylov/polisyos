"""Value-of-Information schedulers that decide whether a candidate advances, defers, or retries."""

from __future__ import annotations

import math
from decimal import Decimal
from typing import Any, Literal, Mapping, Sequence

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

from polisyos.foundry.methods.selection_history import (
    MethodExecutionRecord,
    RuntimePredictor,
    SelectionHistoryStore,
)
from polisyos.scientist.engine.budget import BudgetState


class ParetoSnapshot(BaseModel):
    """Expose frontier/near-frontier/dominated membership used by VOI ranking."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    frontier_candidate_hashes: frozenset[str] = Field(default_factory=frozenset)
    near_frontier_candidate_hashes: frozenset[str] = Field(default_factory=frozenset)
    dominated_candidate_hashes: frozenset[str] = Field(default_factory=frozenset)

    def position_for(self, candidate_hash: str) -> str:
        if candidate_hash in self.dominated_candidate_hashes:
            return "dominated"
        if candidate_hash in self.frontier_candidate_hashes:
            return "frontier"
        if candidate_hash in self.near_frontier_candidate_hashes:
            return "near_frontier"
        return "unknown"


class ComputeEconomicsDecision(BaseModel):
    """Explain the predicted ROI, governance value, and cost/risk terms for one candidate."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    candidate_id: str = Field(min_length=1)
    recommended_action: Literal["advance", "defer", "reject", "retry_cheaper"]
    expected_improvement_per_usd: float
    expected_falsification_value: float
    expected_governance_value: float
    timeout_risk: float = Field(ge=0.0, le=1.0)
    replay_cost_usd: float = Field(ge=0.0)
    calibration_debt: float = Field(ge=0.0)
    current_pareto_position: str = Field(min_length=1)
    predicted_metric_vector: dict[str, float] = Field(default_factory=dict)
    promotion_likelihood: float = Field(default=0.0, ge=0.0, le=1.0)
    estimated_wall_seconds: float = Field(default=0.0, ge=0.0)
    estimated_cost_usd: float = Field(default=0.0, ge=0.0)
    predicted_disagreement: float = Field(default=0.0, ge=0.0)
    exploration_bonus: float = 0.0
    reserved_calibration_budget_usd: float = Field(default=0.0, ge=0.0)
    scheduler_mode: str = Field(default="simple", min_length=1)


class SchedulingDecision(BaseModel):
    """Return the recommended routing action and priority for one funnel ticket."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    candidate_id: str = Field(min_length=1)
    priority: float
    next_level: int | None = None
    recommended_action: Literal["advance", "defer", "reject", "retry_cheaper"]
    reason: str = Field(min_length=1)
    economics: ComputeEconomicsDecision


class VOITrainingConfig(BaseModel):
    """Configure sample minima, ridge regularization, exploration, and calibration reserves."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    min_stage_observations: int = Field(default=5, ge=2, le=1000)
    min_promotion_observations: int = Field(default=4, ge=2, le=1000)
    ridge_alpha: float = Field(default=0.25, ge=0.0, le=100.0)
    cross_domain_weight: float = Field(default=0.0, ge=0.0, le=1.0)
    exploration_fraction_low_utilization: float = Field(default=0.15, ge=0.0, le=1.0)
    exploration_fraction_high_utilization: float = Field(default=0.05, ge=0.0, le=1.0)
    budget_utilization_switch: float = Field(default=0.7, ge=0.0, le=1.0)
    reserved_calibration_budget_fraction: float = Field(
        default=0.15,
        ge=0.0,
        le=0.95,
    )


class VOIModelStatus(BaseModel):
    """Report whether a predictive VOI sub-model is trained, degraded, or insufficiently sampled."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    model_name: str = Field(min_length=1)
    status: str = Field(min_length=1)
    sample_count: int = Field(default=0, ge=0)
    notes: list[str] = Field(default_factory=list)


class VOIObservation(BaseModel):
    """Store one expensive-stage training sample for predictive VOI models."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    candidate_id: str = Field(min_length=1)
    task_family: str = Field(default="policy", min_length=1)
    domain: str = Field(default="general", min_length=1)
    tenant_hash: str = Field(default="", min_length=0)
    stage_level: int = Field(default=0, ge=0)
    frontier_position: str = Field(default="unknown", min_length=1)
    features: dict[str, float] = Field(default_factory=dict)
    actual_objective_value: float = 0.0
    actual_promising: bool = True
    duration_seconds: float = Field(default=0.0, ge=0.0)
    compute_cost_usd: float = Field(default=0.0, ge=0.0)
    timeout_occurred: bool = False
    disagreement: float = Field(default=0.0, ge=0.0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class PromotionObservation(BaseModel):
    """Attach the eventual promotion label to a previously observed candidate."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    candidate_id: str = Field(min_length=1)
    task_family: str = Field(default="policy", min_length=1)
    domain: str = Field(default="general", min_length=1)
    tenant_hash: str = Field(default="", min_length=0)
    frontier_position: str = Field(default="unknown", min_length=1)
    features: dict[str, float] = Field(default_factory=dict)
    promoted: bool
    metadata: dict[str, Any] = Field(default_factory=dict)


class VOIModelSnapshot(BaseModel):
    """Persist predictive VOI training data, stage costs, and calibration metadata."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field(default="1.0", pattern=r"^\d+\.\d+$")
    training_config: VOITrainingConfig = Field(default_factory=VOITrainingConfig)
    stage_costs: dict[int, float] = Field(default_factory=dict)
    observations: list[VOIObservation] = Field(default_factory=list)
    promotion_observations: list[PromotionObservation] = Field(default_factory=list)
    calibration_state: dict[str, Any] = Field(default_factory=dict)


class SimpleVOIScheduler:
    """Rank funnel tickets with a deterministic expected-improvement-per-cost heuristic.

    This scheduler does not train predictive models; it reads the latest
    cheap-stage signals, current Pareto position, and `BudgetState`, then emits
    `SchedulingDecision` records that distinguish candidate advancement, budget
    deferral, ROI rejection, and cheaper retry under timeout risk.
    """

    def __init__(
        self,
        *,
        stage_costs: Mapping[int, Decimal] | None = None,
        budget_key: str = "run",
        min_roi_threshold: float = 1.0,
        timeout_risk_threshold: float = 0.7,
        reserved_calibration_budget_fraction: float = 0.15,
    ) -> None:
        self._stage_costs = dict(stage_costs or {})
        self._budget_key = budget_key
        self._min_roi_threshold = float(min_roi_threshold)
        self._timeout_risk_threshold = float(timeout_risk_threshold)
        self._reserved_calibration_budget_fraction = max(
            0.0,
            min(0.95, float(reserved_calibration_budget_fraction)),
        )

    def prioritize(
        self,
        candidates: Sequence[Any],
        budget_remaining: BudgetState,
        frontier: ParetoSnapshot | None = None,
    ) -> list[SchedulingDecision]:
        snapshot = frontier or ParetoSnapshot()
        decisions = [
            self._prioritize_single(
                ticket,
                budget_remaining=budget_remaining,
                frontier=snapshot,
                exploration_weight=self._exploration_weight(budget_remaining),
            )
            for ticket in candidates
        ]
        return sorted(decisions, key=lambda item: item.priority, reverse=True)

    def _prioritize_single(
        self,
        ticket: Any,
        *,
        budget_remaining: BudgetState,
        frontier: ParetoSnapshot,
        exploration_weight: float,
    ) -> SchedulingDecision:
        inputs = self._heuristic_inputs(ticket, frontier)
        estimated_cost = self._estimated_cost_decimal(inputs["next_level"])
        estimated_cost_float = max(float(estimated_cost), 1e-9)
        expected_improvement_per_usd = inputs["expected_value_proxy"] / estimated_cost_float
        exploration_bonus = exploration_weight * inputs["expected_information_gain"]
        reserved_calibration_budget_usd = self._reserved_calibration_budget_usd(
            budget_remaining
        )
        priority = ((1.0 - exploration_weight) * expected_improvement_per_usd) + exploration_bonus
        economics = ComputeEconomicsDecision(
            candidate_id=inputs["candidate_id"],
            recommended_action="advance",
            expected_improvement_per_usd=expected_improvement_per_usd,
            expected_falsification_value=inputs["expected_information_gain"],
            expected_governance_value=inputs["governance_value"],
            timeout_risk=inputs["timeout_risk"],
            replay_cost_usd=float(estimated_cost),
            calibration_debt=0.0,
            current_pareto_position=inputs["pareto_position"],
            predicted_metric_vector={"objective_value": inputs["expected_value_proxy"]},
            promotion_likelihood=inputs["governance_value"],
            estimated_wall_seconds=0.0,
            estimated_cost_usd=float(estimated_cost),
            predicted_disagreement=inputs["expected_information_gain"],
            exploration_bonus=exploration_bonus,
            reserved_calibration_budget_usd=reserved_calibration_budget_usd,
            scheduler_mode="simple",
        )
        action, reason = self._recommended_action(
            next_level=inputs["next_level"],
            pareto_position=inputs["pareto_position"],
            budget_remaining=budget_remaining,
            estimated_cost=estimated_cost,
            timeout_risk=inputs["timeout_risk"],
            expected_improvement_per_usd=expected_improvement_per_usd,
            is_sentinel=inputs["is_sentinel"],
            reserved_calibration_budget_usd=reserved_calibration_budget_usd,
            scheduler_mode="simple",
        )
        economics = economics.model_copy(update={"recommended_action": action})
        return SchedulingDecision(
            candidate_id=inputs["candidate_id"],
            priority=priority,
            next_level=inputs["next_level"],
            recommended_action=action,
            reason=reason,
            economics=economics,
        )

    def _heuristic_inputs(
        self,
        ticket: Any,
        frontier: ParetoSnapshot,
    ) -> dict[str, Any]:
        candidate_id = str(getattr(ticket, "candidate_hash", getattr(ticket, "ticket_id", "unknown")))
        next_level = getattr(ticket, "next_level", None)
        last_result = self._last_result(ticket)
        cheap_signal = getattr(last_result, "cheap_signal", None)
        expected_value_proxy = float(getattr(cheap_signal, "expected_value_proxy", 0.0))
        expected_information_gain = float(
            getattr(cheap_signal, "expected_information_gain", 0.0)
        )
        pareto_position = frontier.position_for(candidate_id)
        governance_value = {
            "frontier": 1.0,
            "near_frontier": 0.7,
            "unknown": 0.4,
            "dominated": 0.0,
        }.get(pareto_position, 0.4)
        return {
            "candidate_id": candidate_id,
            "next_level": next_level,
            "expected_value_proxy": expected_value_proxy,
            "expected_information_gain": expected_information_gain,
            "timeout_risk": self._timeout_risk(last_result),
            "pareto_position": pareto_position,
            "governance_value": governance_value,
            "is_sentinel": bool(getattr(ticket, "context", {}) and getattr(ticket, "context", {}).get("is_sentinel")),
        }

    def _recommended_action(
        self,
        *,
        next_level: int | None,
        pareto_position: str,
        budget_remaining: BudgetState,
        estimated_cost: Decimal,
        timeout_risk: float,
        expected_improvement_per_usd: float,
        is_sentinel: bool,
        reserved_calibration_budget_usd: float,
        scheduler_mode: str,
    ) -> tuple[Literal["advance", "defer", "reject", "retry_cheaper"], str]:
        del scheduler_mode
        recommended_action: Literal["advance", "defer", "reject", "retry_cheaper"] = "advance"
        reason = "advance_by_voi"
        if pareto_position == "dominated" and not is_sentinel:
            recommended_action = "reject"
            reason = "dominated_candidate"
        elif next_level is not None and budget_remaining.would_exceed(
            self._budget_key,
            estimated_cost,
        ):
            recommended_action = "defer"
            reason = "budget_exhausted_for_next_level"
        elif (
            not is_sentinel
            and next_level is not None
            and next_level >= 4
            and self._violates_calibration_reserve(
                budget_remaining=budget_remaining,
                estimated_cost=estimated_cost,
                reserved_calibration_budget_usd=reserved_calibration_budget_usd,
            )
        ):
            recommended_action = "defer"
            reason = "reserved_calibration_budget"
        elif (
            next_level is not None
            and next_level >= 4
            and timeout_risk >= self._timeout_risk_threshold
        ):
            recommended_action = "retry_cheaper"
            reason = "high_timeout_risk"
        elif expected_improvement_per_usd < self._min_roi_threshold:
            recommended_action = "reject"
            reason = "roi_below_threshold"
        return recommended_action, reason

    def _exploration_weight(self, budget_remaining: BudgetState) -> float:
        utilization = budget_remaining.utilization(self._budget_key)
        if utilization is None:
            return 0.15
        if utilization < 0.3:
            return 0.4
        if utilization < 0.7:
            return 0.15
        return 0.05

    def _estimated_cost_decimal(self, next_level: int | None) -> Decimal:
        return self._stage_costs.get(next_level or -1, Decimal("0"))

    def _reserved_calibration_budget_usd(self, budget_remaining: BudgetState) -> float:
        limit = budget_remaining.limits.get(self._budget_key)
        if limit is None:
            return 0.0
        return float(limit.max_usd) * self._reserved_calibration_budget_fraction

    def _violates_calibration_reserve(
        self,
        *,
        budget_remaining: BudgetState,
        estimated_cost: Decimal,
        reserved_calibration_budget_usd: float,
    ) -> bool:
        remaining = budget_remaining.remaining(self._budget_key)
        if remaining is None:
            return False
        post_spend_remaining = float(remaining - estimated_cost)
        return post_spend_remaining < reserved_calibration_budget_usd

    @staticmethod
    def _last_result(ticket: Any) -> Any | None:
        last_result = getattr(ticket, "last_result", None)
        if last_result is not None:
            return last_result
        stage_results = getattr(ticket, "stage_results", None)
        if not stage_results:
            return None
        return stage_results[max(stage_results)]

    @staticmethod
    def _timeout_risk(last_result: Any | None) -> float:
        if last_result is None:
            return 0.0
        feedback = getattr(last_result, "feedback", {}) or {}
        timeout_risk = feedback.get("timeout_risk", 0.0)
        try:
            timeout_risk_float = float(timeout_risk)
        except (TypeError, ValueError):
            return 0.0
        return max(0.0, min(1.0, timeout_risk_float))


class PredictiveVOIScheduler(SimpleVOIScheduler):
    """History-backed VOI scheduler with predictive models and hard fallbacks."""

    def __init__(
        self,
        *,
        stage_costs: Mapping[int, Decimal] | None = None,
        budget_key: str = "run",
        min_roi_threshold: float = 1.0,
        timeout_risk_threshold: float = 0.7,
        training_config: VOITrainingConfig | None = None,
    ) -> None:
        super().__init__(
            stage_costs=stage_costs,
            budget_key=budget_key,
            min_roi_threshold=min_roi_threshold,
            timeout_risk_threshold=timeout_risk_threshold,
            reserved_calibration_budget_fraction=(
                training_config.reserved_calibration_budget_fraction
                if training_config is not None
                else 0.15
            ),
        )
        self._training_config = training_config or VOITrainingConfig()
        self._observations: list[VOIObservation] = []
        self._promotion_observations: list[PromotionObservation] = []
        self._calibration_state: dict[str, Any] = {}
        self._runtime_history = SelectionHistoryStore()
        self._runtime_predictor = RuntimePredictor()

    @property
    def training_config(self) -> VOITrainingConfig:
        return self._training_config

    def observe_stage_result(
        self,
        *,
        candidate_id: str,
        task_family: str = "policy",
        domain: str = "",
        tenant_hash: str = "",
        stage_level: int,
        frontier_position: str = "unknown",
        cheap_signal: Any | None = None,
        actual_objective_value: float,
        actual_promising: bool,
        duration_seconds: float,
        compute_cost_usd: float,
        timeout_occurred: bool = False,
        disagreement: float | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        features = _feature_vector(
            cheap_signal=cheap_signal,
            frontier_position=frontier_position,
            stage_level=stage_level,
        )
        observation = VOIObservation(
            candidate_id=candidate_id,
            task_family=str(task_family or "policy"),
            domain=_normalized_scope_domain(domain, fallback_id=candidate_id),
            tenant_hash=str(tenant_hash or ""),
            stage_level=stage_level,
            frontier_position=frontier_position,
            features=features,
            actual_objective_value=float(actual_objective_value),
            actual_promising=bool(actual_promising),
            duration_seconds=max(float(duration_seconds), 0.0),
            compute_cost_usd=max(float(compute_cost_usd), 0.0),
            timeout_occurred=bool(timeout_occurred),
            disagreement=max(
                0.0,
                float(
                    disagreement
                    if disagreement is not None
                    else abs(features["expected_value_proxy"] - float(actual_objective_value))
                ),
            ),
            metadata=dict(metadata or {}),
        )
        self._observations.append(observation)
        self._record_runtime_history(observation)

    def observe_promotion_outcome(
        self,
        *,
        candidate_id: str,
        promoted: bool,
        task_family: str = "policy",
        domain: str = "",
        tenant_hash: str = "",
        frontier_position: str = "unknown",
        cheap_signal: Any | None = None,
        stage_level: int = 4,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self._promotion_observations.append(
            PromotionObservation(
                candidate_id=candidate_id,
                task_family=str(task_family or "policy"),
                domain=_normalized_scope_domain(domain, fallback_id=candidate_id),
                tenant_hash=str(tenant_hash or ""),
                frontier_position=frontier_position,
                features=_feature_vector(
                    cheap_signal=cheap_signal,
                    frontier_position=frontier_position,
                    stage_level=stage_level,
                ),
                promoted=bool(promoted),
                metadata=dict(metadata or {}),
            )
        )

    def update_calibration_state(
        self,
        metrics: Mapping[str, Any],
    ) -> None:
        self._calibration_state = dict(metrics)

    def snapshot(self) -> VOIModelSnapshot:
        return VOIModelSnapshot(
            training_config=self._training_config,
            stage_costs={level: float(cost) for level, cost in self._stage_costs.items()},
            observations=list(self._observations),
            promotion_observations=list(self._promotion_observations),
            calibration_state=dict(self._calibration_state),
        )

    @classmethod
    def from_snapshot(
        cls,
        snapshot: VOIModelSnapshot,
        *,
        budget_key: str = "run",
        min_roi_threshold: float = 1.0,
        timeout_risk_threshold: float = 0.7,
    ) -> "PredictiveVOIScheduler":
        scheduler = cls(
            stage_costs={
                level: Decimal(str(cost))
                for level, cost in snapshot.stage_costs.items()
            },
            budget_key=budget_key,
            min_roi_threshold=min_roi_threshold,
            timeout_risk_threshold=timeout_risk_threshold,
            training_config=snapshot.training_config,
        )
        scheduler._observations = list(snapshot.observations)
        scheduler._promotion_observations = list(snapshot.promotion_observations)
        scheduler._calibration_state = dict(snapshot.calibration_state)
        for observation in scheduler._observations:
            scheduler._record_runtime_history(observation)
        return scheduler

    def model_status(self) -> list[VOIModelStatus]:
        stage_count = len(self._observations)
        promotion_count = len(self._promotion_observations)
        calibration_mode = str(self._calibration_state.get("routing_mode", "normal"))
        base_status = "ready"
        notes: list[str] = []
        if calibration_mode != "normal":
            base_status = "conservative"
            notes.append(f"routing_mode={calibration_mode}")
        return [
            VOIModelStatus(
                model_name="cheap_causal_surrogate",
                status="ready" if stage_count >= self._training_config.min_stage_observations else "fallback",
                sample_count=stage_count,
                notes=notes,
            ),
            VOIModelStatus(
                model_name="runtime_timeout",
                status="ready" if stage_count >= self._training_config.min_stage_observations else "fallback",
                sample_count=stage_count,
                notes=["runtime_predictor_fitted" if self._runtime_predictor.is_fitted else "runtime_default"],
            ),
            VOIModelStatus(
                model_name="uncertainty_proxy",
                status="ready" if stage_count >= self._training_config.min_stage_observations else "fallback",
                sample_count=stage_count,
                notes=notes,
            ),
            VOIModelStatus(
                model_name="promotion_likelihood",
                status=(
                    base_status
                    if promotion_count >= self._training_config.min_promotion_observations
                    else "fallback"
                ),
                sample_count=promotion_count,
                notes=notes,
            ),
        ]

    def prioritize(
        self,
        candidates: Sequence[Any],
        budget_remaining: BudgetState,
        frontier: ParetoSnapshot | None = None,
    ) -> list[SchedulingDecision]:
        if self._predictive_disabled():
            return super().prioritize(candidates, budget_remaining, frontier)

        snapshot = frontier or ParetoSnapshot()
        decisions: list[SchedulingDecision] = []
        exploration_fraction = self._exploration_fraction(budget_remaining)
        for ticket in candidates:
            heuristic = self._heuristic_inputs(ticket, snapshot)
            context = _resolve_context(ticket)
            stage_slice = self._slice_stage_observations(context)
            promotion_slice = self._slice_promotion_observations(context)
            features = _feature_vector(
                cheap_signal=getattr(self._last_result(ticket), "cheap_signal", None),
                frontier_position=heuristic["pareto_position"],
                stage_level=heuristic["next_level"] or 0,
            )

            predicted_objective = _predict_continuous(
                stage_slice,
                features,
                target_getter=lambda obs: obs.actual_objective_value,
                alpha=self._training_config.ridge_alpha,
                minimum=self._training_config.min_stage_observations,
                fallback=heuristic["expected_value_proxy"],
            )
            predicted_disagreement = _predict_continuous(
                stage_slice,
                features,
                target_getter=lambda obs: obs.disagreement,
                alpha=self._training_config.ridge_alpha,
                minimum=self._training_config.min_stage_observations,
                fallback=heuristic["expected_information_gain"],
            )
            estimated_wall_seconds = self._predict_duration_seconds(
                features,
                heuristic["next_level"] or 0,
                stage_slice,
                fallback=0.0,
            )
            estimated_cost_usd = self._predict_cost_usd(
                stage_slice,
                features,
                heuristic["next_level"] or 0,
            )
            timeout_risk = _predict_probability(
                stage_slice,
                features,
                target_getter=lambda obs: 1.0 if obs.timeout_occurred else 0.0,
                alpha=self._training_config.ridge_alpha,
                minimum=self._training_config.min_stage_observations,
                fallback=heuristic["timeout_risk"],
            )
            promotion_likelihood = _predict_probability(
                promotion_slice,
                features,
                target_getter=lambda obs: 1.0 if obs.promoted else 0.0,
                alpha=self._training_config.ridge_alpha,
                minimum=self._training_config.min_promotion_observations,
                fallback=heuristic["governance_value"],
            )
            expected_improvement_per_usd = predicted_objective / max(estimated_cost_usd, 1e-9)
            calibration_debt = self._calibration_debt()
            governance_bonus = heuristic["governance_value"] * max(promotion_likelihood, 0.1)
            exploration_bonus = exploration_fraction * max(predicted_disagreement, 0.0)
            timeout_penalty = timeout_risk * 0.5
            replay_cost_penalty = min(estimated_cost_usd, 10.0) * 0.05
            calibration_penalty = calibration_debt * 0.3
            reserved_calibration_budget_usd = self._reserved_calibration_budget_usd(
                budget_remaining
            )
            priority = (
                expected_improvement_per_usd
                + exploration_bonus
                + governance_bonus
                - timeout_penalty
                - replay_cost_penalty
                - calibration_penalty
            )
            economics = ComputeEconomicsDecision(
                candidate_id=heuristic["candidate_id"],
                recommended_action="advance",
                expected_improvement_per_usd=expected_improvement_per_usd,
                expected_falsification_value=predicted_disagreement,
                expected_governance_value=governance_bonus,
                timeout_risk=max(0.0, min(1.0, timeout_risk)),
                replay_cost_usd=estimated_cost_usd,
                calibration_debt=calibration_debt,
                current_pareto_position=heuristic["pareto_position"],
                predicted_metric_vector={
                    "objective_value": predicted_objective,
                    "promising_probability": float(prediction_bool_to_probability(predicted_objective)),
                },
                promotion_likelihood=max(0.0, min(1.0, promotion_likelihood)),
                estimated_wall_seconds=max(0.0, estimated_wall_seconds),
                estimated_cost_usd=max(0.0, estimated_cost_usd),
                predicted_disagreement=max(0.0, predicted_disagreement),
                exploration_bonus=exploration_bonus,
                reserved_calibration_budget_usd=reserved_calibration_budget_usd,
                scheduler_mode="predictive",
            )
            action, reason = self._recommended_action(
                next_level=heuristic["next_level"],
                pareto_position=heuristic["pareto_position"],
                budget_remaining=budget_remaining,
                estimated_cost=Decimal(str(estimated_cost_usd)),
                timeout_risk=max(timeout_risk, 0.0),
                expected_improvement_per_usd=expected_improvement_per_usd,
                is_sentinel=heuristic["is_sentinel"],
                reserved_calibration_budget_usd=reserved_calibration_budget_usd,
                scheduler_mode="predictive",
            )
            if (
                heuristic["next_level"] is not None
                and heuristic["next_level"] >= 4
                and self._model_confidence_low(stage_slice)
            ):
                action = "retry_cheaper"
                reason = "predictive_confidence_low"
            economics = economics.model_copy(update={"recommended_action": action})
            decisions.append(
                SchedulingDecision(
                    candidate_id=heuristic["candidate_id"],
                    priority=priority,
                    next_level=heuristic["next_level"],
                    recommended_action=action,
                    reason=reason,
                    economics=economics,
                )
            )
        return sorted(decisions, key=lambda item: item.priority, reverse=True)

    def _predictive_disabled(self) -> bool:
        routing_mode = str(self._calibration_state.get("routing_mode", "normal"))
        if routing_mode in {"conservative_routing", "no_promotion"}:
            return True
        return False

    def _slice_stage_observations(self, context: dict[str, str]) -> list[tuple[VOIObservation, float]]:
        return _weighted_slice(
            self._observations,
            task_family=context["task_family"],
            domain=context["domain"],
            tenant_hash=context["tenant_hash"],
            cross_domain_weight=self._training_config.cross_domain_weight,
        )

    def _slice_promotion_observations(
        self,
        context: dict[str, str],
    ) -> list[tuple[PromotionObservation, float]]:
        return _weighted_slice(
            self._promotion_observations,
            task_family=context["task_family"],
            domain=context["domain"],
            tenant_hash=context["tenant_hash"],
            cross_domain_weight=self._training_config.cross_domain_weight,
        )

    def _record_runtime_history(self, observation: VOIObservation) -> None:
        complexity = 1.0 + observation.features.get("stage_level", 0.0) + observation.features.get(
            "uncertainty_prior", 0.0
        )
        self._runtime_history.record(
            MethodExecutionRecord(
                method_fqn=f"scientist.funnel.L{observation.stage_level}",
                timestamp=float(observation.metadata.get("timestamp", len(self._observations) + 1)),
                latency_ms=max(observation.duration_seconds, 0.0) * 1000.0,
                success=not observation.timeout_occurred,
                output_quality=max(0.0, min(1.0, observation.actual_objective_value)),
                data_characteristics={
                    "n_obs": max(1, int(100 * complexity)),
                    "n_features": max(1, len(observation.features)),
                },
                failure_type="timeout" if observation.timeout_occurred else None,
            )
        )
        self._runtime_predictor.fit(self._runtime_history)

    def _predict_duration_seconds(
        self,
        features: dict[str, float],
        stage_level: int,
        observations: list[tuple[VOIObservation, float]],
        *,
        fallback: float,
    ) -> float:
        if self._runtime_predictor.is_fitted:
            complexity = 1.0 + features.get("stage_level", 0.0) + features.get("uncertainty_prior", 0.0)
            return self._runtime_predictor.predict_ms(
                f"scientist.funnel.L{stage_level}",
                n_obs=max(1, int(100 * complexity)),
                n_features=max(1, len(features)),
            ) / 1000.0
        return _predict_continuous(
            observations,
            features,
            target_getter=lambda obs: obs.duration_seconds,
            alpha=self._training_config.ridge_alpha,
            minimum=self._training_config.min_stage_observations,
            fallback=fallback,
        )

    def _predict_cost_usd(
        self,
        observations: list[tuple[VOIObservation, float]],
        features: dict[str, float],
        stage_level: int,
    ) -> float:
        baseline = float(self._estimated_cost_decimal(stage_level))
        return max(
            baseline,
            _predict_continuous(
                observations,
                features,
                target_getter=lambda obs: obs.compute_cost_usd,
                alpha=self._training_config.ridge_alpha,
                minimum=self._training_config.min_stage_observations,
                fallback=baseline,
            ),
        )

    def _exploration_fraction(self, budget_remaining: BudgetState) -> float:
        utilization = budget_remaining.utilization(self._budget_key)
        if utilization is None or utilization < self._training_config.budget_utilization_switch:
            return self._training_config.exploration_fraction_low_utilization
        return self._training_config.exploration_fraction_high_utilization

    def _calibration_debt(self) -> float:
        sample_count = int(self._calibration_state.get("rolling_sample_count", 0) or 0)
        shortfall = max(0, self._training_config.min_stage_observations - sample_count)
        debt = shortfall / max(self._training_config.min_stage_observations, 1)
        if bool(self._calibration_state.get("promotion_ban_active")):
            debt += 0.5
        sentinel_rate = self._calibration_state.get("sentinel_pass_rate")
        if sentinel_rate is not None and float(sentinel_rate) < 0.95:
            debt += 0.25
        return max(0.0, min(1.0, debt))

    def _model_confidence_low(self, observations: list[tuple[VOIObservation, float]]) -> bool:
        return len(observations) < self._training_config.min_stage_observations


def _resolve_context(ticket: Any) -> dict[str, str]:
    context = getattr(ticket, "context", {}) or {}
    transfer = context.get("transfer_context")
    task_family = getattr(transfer, "task_family", None) or str(context.get("task_family", "policy"))
    domain = getattr(transfer, "domain", None) or _normalized_scope_domain(
        context.get("domain"),
        fallback_id=str(getattr(ticket, "candidate_hash", getattr(ticket, "ticket_id", "unknown"))),
    )
    tenant_hash = getattr(transfer, "tenant_hash", None) or str(context.get("tenant_hash", ""))
    return {
        "task_family": task_family or "policy",
        "domain": domain,
        "tenant_hash": tenant_hash,
    }


def _feature_vector(
    *,
    cheap_signal: Any | None,
    frontier_position: str,
    stage_level: int,
) -> dict[str, float]:
    return {
        "expected_value_proxy": float(getattr(cheap_signal, "expected_value_proxy", 0.0)),
        "expected_information_gain": float(
            getattr(cheap_signal, "expected_information_gain", 0.0)
        ),
        "structural_validity": float(getattr(cheap_signal, "structural_validity", 0.5)),
        "causal_identifiability": float(
            getattr(cheap_signal, "causal_identifiability", 0.5)
        ),
        "feasibility": float(getattr(cheap_signal, "feasibility", 0.5)),
        "uncertainty_prior": float(getattr(cheap_signal, "uncertainty_prior", 0.5)),
        "expected_harm_proxy": float(getattr(cheap_signal, "expected_harm_proxy", 0.5)),
        "frontier_score": {
            "frontier": 1.0,
            "near_frontier": 0.7,
            "unknown": 0.4,
            "dominated": 0.0,
        }.get(frontier_position, 0.4),
        "stage_level": float(stage_level),
    }


def _weighted_slice(
    items: Sequence[Any],
    *,
    task_family: str,
    domain: str,
    tenant_hash: str,
    cross_domain_weight: float,
) -> list[tuple[Any, float]]:
    sliced: list[tuple[Any, float]] = []
    for item in items:
        if tenant_hash and str(getattr(item, "tenant_hash", "")) != tenant_hash:
            continue
        if str(getattr(item, "task_family", "")) != task_family:
            continue
        item_domain = str(getattr(item, "domain", ""))
        if item_domain == domain:
            weight = 1.0
        elif cross_domain_weight > 0.0:
            weight = cross_domain_weight
        else:
            continue
        sliced.append((item, weight))
    return sliced


def _normalized_scope_domain(domain: Any, *, fallback_id: str) -> str:
    value = str(domain or "").strip()
    if value:
        return value
    normalized = str(fallback_id or "unknown").strip() or "unknown"
    return f"isolated::{normalized}"


def _predict_continuous(
    rows: list[tuple[Any, float]],
    features: dict[str, float],
    *,
    target_getter,
    alpha: float,
    minimum: int,
    fallback: float,
) -> float:
    if len(rows) < minimum:
        return float(fallback)
    keys = sorted(features)
    X = np.array(
        [
            [1.0, *[float(item.features.get(key, 0.0)) for key in keys]]
            for item, _weight in rows
        ],
        dtype=float,
    )
    y = np.array([float(target_getter(item)) for item, _weight in rows], dtype=float)
    w = np.sqrt(np.array([weight for _item, weight in rows], dtype=float))
    Xw = X * w[:, None]
    yw = y * w
    ridge = alpha * np.eye(X.shape[1], dtype=float)
    ridge[0, 0] = 0.0
    try:
        coeffs = np.linalg.solve(Xw.T @ Xw + ridge, Xw.T @ yw)
    except np.linalg.LinAlgError:
        return float(fallback)
    x = np.array([1.0, *[float(features.get(key, 0.0)) for key in keys]], dtype=float)
    prediction = float(x @ coeffs)
    if not math.isfinite(prediction):
        return float(fallback)
    return prediction


def _predict_probability(
    rows: list[tuple[Any, float]],
    features: dict[str, float],
    *,
    target_getter,
    alpha: float,
    minimum: int,
    fallback: float,
) -> float:
    latent = _predict_continuous(
        rows,
        features,
        target_getter=target_getter,
        alpha=alpha,
        minimum=minimum,
        fallback=fallback,
    )
    if len(rows) < minimum:
        return max(0.0, min(1.0, float(fallback)))
    clipped = max(-20.0, min(20.0, latent))
    return max(0.0, min(1.0, 1.0 / (1.0 + math.exp(-clipped))))


def prediction_bool_to_probability(value: float) -> float:
    """Prediction bool to probability helper."""
    return max(0.0, min(1.0, value))


__all__ = [
    "ComputeEconomicsDecision",
    "ParetoSnapshot",
    "PredictiveVOIScheduler",
    "PromotionObservation",
    "SchedulingDecision",
    "SimpleVOIScheduler",
    "VOIModelSnapshot",
    "VOIModelStatus",
    "VOIObservation",
    "VOITrainingConfig",
]
