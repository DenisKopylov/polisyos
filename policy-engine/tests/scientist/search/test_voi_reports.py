from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.scientist.engine.budget import BudgetLimit, BudgetState
from polisyos.scientist.search.funnel.types import CheapSignalVector, FunnelStageResult
from polisyos.scientist.search.uncertainty import UncertaintyEnvelope
from polisyos.scientist.search.voi_scheduler import (
    SimpleVOIScheduler,
    build_adversarial_challenge_voi_decision,
    build_stop_search_voi_decision,
    load_voi_run_report,
    persist_voi_run_report,
    scheduling_decision_to_voi_record,
)


@dataclass
class _Ticket:
    candidate_hash: str
    next_level: int
    last_result: FunnelStageResult


def _budget() -> BudgetState:
    return BudgetState(limits={"run": BudgetLimit(key="run", max_usd=Decimal("10.0"))})


def _ticket() -> _Ticket:
    result = FunnelStageResult(
        policy_candidate={},
        objective_value=0.0,
        is_promising=True,
        stage_name="L2",
        feedback={},
        uncertainty_envelope=UncertaintyEnvelope.unknown(),
        cheap_signal=CheapSignalVector(
            expected_value_proxy=1.2,
            expected_information_gain=0.4,
        ),
        fidelity_level=2,
    )
    return _Ticket(candidate_hash="candidate_a", next_level=3, last_result=result)


def test_existing_scheduler_emits_report_compatible_records() -> None:
    scheduler = SimpleVOIScheduler(stage_costs={3: Decimal("0.25")})
    decision = scheduler.prioritize([_ticket()], _budget())[0]

    record = scheduling_decision_to_voi_record(decision, run_id="run_voi")
    report = scheduler.report_for_decisions(run_id="run_voi", decisions=[decision])

    assert record.run_id == "run_voi"
    assert report.decisions[0].decision_id == record.decision_id
    assert report.total_expected_cost == report.decisions[0].expected_cost


def test_voi_run_report_persists_to_cas(tmp_path) -> None:
    scheduler = SimpleVOIScheduler(stage_costs={3: Decimal("0.25")})
    decision = scheduler.prioritize([_ticket()], _budget())[0]
    report = scheduler.report_for_decisions(
        run_id="run_voi",
        decisions=[decision],
        calibration_status="shadow",
    )
    store = FileSystemCAS(tmp_path / "cas")

    ref = persist_voi_run_report(store, report)
    loaded = load_voi_run_report(store, ref)
    manifest = store.get_manifest(ref.artifact_id)

    assert loaded == report
    assert ref.kind == "scientist.voi_run_report"
    assert manifest.artifact_schema is not None
    assert manifest.artifact_schema.name == "polisyos.scientist.search.VOIRunReport"


def test_stop_search_and_adversarial_challenge_helpers_cover_decision_families() -> None:
    stop = build_stop_search_voi_decision(
        run_id="run_voi",
        marginal_expected_improvement=0.02,
        expected_cost_to_continue=0.1,
        safety_regression_risk=0.01,
    )
    challenge = build_adversarial_challenge_voi_decision(
        run_id="run_voi",
        candidate_id="candidate_near_frontier",
        promotion_likelihood=0.8,
        impact_score=0.75,
        expected_challenge_cost=0.1,
    )

    assert stop.recommended_action == "stop_search"
    assert stop.expected_value < 0.0
    assert challenge.recommended_action == "run_adversarial_challenge"
    assert challenge.expected_risk_reduction > challenge.expected_cost
