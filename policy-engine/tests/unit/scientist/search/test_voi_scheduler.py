from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from polisyos.scientist.orchestration.engine.budget import BudgetLimit, BudgetState
from polisyos.scientist.methods.search.funnel.types import CheapSignalVector, FunnelStageResult
from polisyos.scientist.methods.search.uncertainty import UncertaintyEnvelope
from polisyos.scientist.methods.search.voi_scheduler import (
    ParetoSnapshot,
    PredictiveVOIScheduler,
    SimpleVOIScheduler,
    VOITrainingConfig,
)


@dataclass
class _Ticket:
    candidate_hash: str
    current_level: int
    next_level: int | None
    last_result: FunnelStageResult
    stage_results: dict[int, FunnelStageResult]
    context: dict[str, object] | None = None


def _ticket(
    *,
    candidate_hash: str,
    next_level: int | None,
    expected_value_proxy: float,
    expected_information_gain: float,
    timeout_risk: float = 0.0,
    context: dict[str, object] | None = None,
) -> _Ticket:
    result = FunnelStageResult(
        policy_candidate={},
        objective_value=0.0,
        is_promising=True,
        stage_name="L2",
        feedback={"timeout_risk": timeout_risk},
        uncertainty_envelope=UncertaintyEnvelope.unknown(),
        cheap_signal=CheapSignalVector(
            expected_value_proxy=expected_value_proxy,
            expected_information_gain=expected_information_gain,
        ),
        fidelity_level=2,
    )
    return _Ticket(
        candidate_hash=candidate_hash,
        current_level=2,
        next_level=next_level,
        last_result=result,
        stage_results={2: result},
        context=context or {},
    )


def _budget(max_usd: str = "10.0") -> BudgetState:
    return BudgetState(
        limits={"run": BudgetLimit(key="run", max_usd=Decimal(max_usd))},
    )


def test_voi_prioritizes_higher_roi_ticket_first() -> None:
    scheduler = SimpleVOIScheduler(stage_costs={3: Decimal("0.5")})
    decisions = scheduler.prioritize(
        [
            _ticket(
                candidate_hash="a",
                next_level=3,
                expected_value_proxy=0.9,
                expected_information_gain=0.2,
            ),
            _ticket(
                candidate_hash="b",
                next_level=3,
                expected_value_proxy=0.3,
                expected_information_gain=0.9,
            ),
        ],
        _budget(),
        ParetoSnapshot(),
    )
    assert decisions[0].candidate_id == "a"
    assert decisions[0].recommended_action == "advance"


def test_voi_defers_when_budget_is_insufficient() -> None:
    scheduler = SimpleVOIScheduler(stage_costs={4: Decimal("5.0")})
    budget = _budget(max_usd="1.0")
    decision = scheduler.prioritize(
        [
            _ticket(
                candidate_hash="a",
                next_level=4,
                expected_value_proxy=0.9,
                expected_information_gain=0.2,
            )
        ],
        budget,
        ParetoSnapshot(),
    )[0]
    assert decision.recommended_action == "defer"


def test_voi_rejects_dominated_candidate() -> None:
    scheduler = SimpleVOIScheduler(stage_costs={3: Decimal("0.5")})
    decision = scheduler.prioritize(
        [
            _ticket(
                candidate_hash="dom",
                next_level=3,
                expected_value_proxy=0.9,
                expected_information_gain=0.2,
            )
        ],
        _budget(),
        ParetoSnapshot(dominated_candidate_hashes=frozenset({"dom"})),
    )[0]
    assert decision.recommended_action == "reject"


def test_voi_requests_retry_cheaper_on_high_timeout_risk_before_level4() -> None:
    scheduler = SimpleVOIScheduler(stage_costs={4: Decimal("0.5")})
    decision = scheduler.prioritize(
        [
            _ticket(
                candidate_hash="slow",
                next_level=4,
                expected_value_proxy=0.9,
                expected_information_gain=0.2,
                timeout_risk=0.95,
            )
        ],
        _budget(),
        ParetoSnapshot(),
    )[0]
    assert decision.recommended_action == "retry_cheaper"


def test_predictive_voi_uses_observations_and_snapshot_round_trip() -> None:
    scheduler = PredictiveVOIScheduler(
        stage_costs={4: Decimal("1.0")},
        training_config=VOITrainingConfig(min_stage_observations=3, min_promotion_observations=2),
    )
    for index, value in enumerate((0.2, 0.5, 0.9), start=1):
        signal = CheapSignalVector(
            expected_value_proxy=value,
            expected_information_gain=0.2 + (0.1 * index),
            structural_validity=0.7,
            causal_identifiability=0.8,
            feasibility=0.75,
            uncertainty_prior=0.3,
        )
        scheduler.observe_stage_result(
            candidate_id=f"c{index}",
            task_family="policy",
            domain="fiscal",
            tenant_hash="tenant",
            stage_level=4,
            frontier_position="near_frontier",
            cheap_signal=signal,
            actual_objective_value=value + 0.1,
            actual_promising=True,
            duration_seconds=1.0 + value,
            compute_cost_usd=1.0,
            disagreement=0.05,
        )
    scheduler.observe_promotion_outcome(
        candidate_id="c1",
        promoted=False,
        task_family="policy",
        domain="fiscal",
        tenant_hash="tenant",
        frontier_position="near_frontier",
        cheap_signal=CheapSignalVector(expected_value_proxy=0.2, expected_information_gain=0.3),
    )
    scheduler.observe_promotion_outcome(
        candidate_id="c3",
        promoted=True,
        task_family="policy",
        domain="fiscal",
        tenant_hash="tenant",
        frontier_position="frontier",
        cheap_signal=CheapSignalVector(expected_value_proxy=0.9, expected_information_gain=0.2),
    )

    decision = scheduler.prioritize(
        [
            _ticket(
                candidate_hash="future",
                next_level=4,
                expected_value_proxy=0.85,
                expected_information_gain=0.3,
                context={
                    "transfer_context": type(
                        "Transfer",
                        (),
                        {"task_family": "policy", "domain": "fiscal", "tenant_hash": "tenant"},
                    )()
                },
            )
        ],
        _budget(),
        ParetoSnapshot(near_frontier_candidate_hashes=frozenset({"future"})),
    )[0]

    assert decision.economics.scheduler_mode == "predictive"
    assert decision.economics.predicted_metric_vector
    assert 0.0 <= decision.economics.promotion_likelihood <= 1.0

    restored = PredictiveVOIScheduler.from_snapshot(scheduler.snapshot())
    restored_decision = restored.prioritize(
        [
            _ticket(
                candidate_hash="future",
                next_level=4,
                expected_value_proxy=0.85,
                expected_information_gain=0.3,
                context={
                    "transfer_context": type(
                        "Transfer",
                        (),
                        {"task_family": "policy", "domain": "fiscal", "tenant_hash": "tenant"},
                    )()
                },
            )
        ],
        _budget(),
        ParetoSnapshot(near_frontier_candidate_hashes=frozenset({"future"})),
    )[0]
    assert restored_decision.economics.scheduler_mode == "predictive"


def test_predictive_voi_falls_back_under_drift() -> None:
    scheduler = PredictiveVOIScheduler(
        stage_costs={4: Decimal("1.0")},
        training_config=VOITrainingConfig(min_stage_observations=2, min_promotion_observations=2),
    )
    scheduler.update_calibration_state({"routing_mode": "conservative_routing"})

    decision = scheduler.prioritize(
        [
            _ticket(
                candidate_hash="a",
                next_level=4,
                expected_value_proxy=0.9,
                expected_information_gain=0.2,
            )
        ],
        _budget(),
        ParetoSnapshot(),
    )[0]

    assert decision.economics.scheduler_mode == "simple"


def test_predictive_voi_requests_retry_cheaper_when_model_support_is_too_low() -> None:
    scheduler = PredictiveVOIScheduler(
        stage_costs={4: Decimal("1.0")},
        training_config=VOITrainingConfig(min_stage_observations=5, min_promotion_observations=2),
    )
    scheduler.observe_stage_result(
        candidate_id="c1",
        task_family="policy",
        domain="fiscal",
        tenant_hash="tenant",
        stage_level=4,
        frontier_position="unknown",
        cheap_signal=CheapSignalVector(expected_value_proxy=0.5, expected_information_gain=0.2),
        actual_objective_value=0.6,
        actual_promising=True,
        duration_seconds=1.0,
        compute_cost_usd=1.0,
    )

    decision = scheduler.prioritize(
        [
            _ticket(
                candidate_hash="b",
                next_level=4,
                expected_value_proxy=0.9,
                expected_information_gain=0.4,
                context={
                    "transfer_context": type(
                        "Transfer",
                        (),
                        {"task_family": "policy", "domain": "fiscal", "tenant_hash": "tenant"},
                    )()
                },
            )
        ],
        _budget(),
        ParetoSnapshot(),
    )[0]

    assert decision.recommended_action == "retry_cheaper"


def test_voi_reserves_calibration_budget_for_non_sentinels() -> None:
    scheduler = SimpleVOIScheduler(
        stage_costs={4: Decimal("1.0")},
        reserved_calibration_budget_fraction=0.15,
    )
    budget = _budget(max_usd="10.0")
    budget.record_spend("run", Decimal("7.6"))

    decision = scheduler.prioritize(
        [
            _ticket(
                candidate_hash="late",
                next_level=4,
                expected_value_proxy=2.0,
                expected_information_gain=0.4,
            )
        ],
        budget,
        ParetoSnapshot(),
    )[0]

    assert decision.recommended_action == "defer"
    assert decision.reason == "reserved_calibration_budget"


def test_voi_allows_sentinels_to_bypass_reserved_calibration_budget() -> None:
    scheduler = SimpleVOIScheduler(
        stage_costs={4: Decimal("1.0")},
        reserved_calibration_budget_fraction=0.15,
    )
    budget = _budget(max_usd="10.0")
    budget.record_spend("run", Decimal("7.6"))

    decision = scheduler.prioritize(
        [
            _ticket(
                candidate_hash="sentinel",
                next_level=4,
                expected_value_proxy=2.0,
                expected_information_gain=0.4,
                context={"is_sentinel": True},
            )
        ],
        budget,
        ParetoSnapshot(),
    )[0]

    assert decision.recommended_action == "advance"


def test_predictive_voi_does_not_mix_cross_domain_observations_by_default() -> None:
    scheduler = PredictiveVOIScheduler(
        stage_costs={4: Decimal("1.0")},
        training_config=VOITrainingConfig(
            min_stage_observations=2,
            min_promotion_observations=2,
        ),
    )
    scheduler.observe_stage_result(
        candidate_id="fiscal-1",
        task_family="policy",
        domain="fiscal",
        tenant_hash="tenant",
        stage_level=4,
        cheap_signal=CheapSignalVector(expected_value_proxy=0.7, expected_information_gain=0.3),
        actual_objective_value=0.8,
        actual_promising=True,
        duration_seconds=1.0,
        compute_cost_usd=1.0,
    )
    scheduler.observe_stage_result(
        candidate_id="labor-1",
        task_family="policy",
        domain="labor",
        tenant_hash="tenant",
        stage_level=4,
        cheap_signal=CheapSignalVector(expected_value_proxy=0.2, expected_information_gain=0.1),
        actual_objective_value=0.3,
        actual_promising=False,
        duration_seconds=1.0,
        compute_cost_usd=1.0,
    )

    sliced = scheduler._slice_stage_observations(
        {"task_family": "policy", "domain": "fiscal", "tenant_hash": "tenant"}
    )

    assert [item.candidate_id for item, _weight in sliced] == ["fiscal-1"]
