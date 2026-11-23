from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from hashlib import sha256
from types import SimpleNamespace

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.canon import CanonSpec, from_canonical_bytes, to_canonical_bytes
from polisyos.scientist.methods.search.funnel.types import CheapSignalVector, FunnelStageResult
from polisyos.scientist.methods.search.uncertainty import UncertaintyEnvelope
from polisyos.scientist.methods.search.voi_scheduler import (
    SchedulingDecision,
    SimpleVOIScheduler,
    build_adversarial_challenge_voi_decision,
    build_stop_search_voi_decision,
    load_voi_run_report,
    persist_voi_run_report,
    scheduling_decision_to_voi_record,
)
from polisyos.scientist.orchestration.engine.budget import BudgetLimit, BudgetState


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


def test_voi_report_reopens_missing_value_proxy_as_a_limited_heuristic(tmp_path) -> None:
    scheduler = SimpleVOIScheduler(stage_costs={3: Decimal("0.5")})
    tickets = [
        SimpleNamespace(
            candidate_hash="informative",
            next_level=3,
            last_result=SimpleNamespace(cheap_signal=signal),
        )
        for signal in (
            SimpleNamespace(expected_information_gain=0.8),
            SimpleNamespace(expected_information_gain=0.8, expected_value_proxy=0.0),
        )
    ]
    report = scheduler.report_for_candidates(
        run_id="missing-and-known-proxy",
        candidates=tickets,
        budget_remaining=_budget(),
    )
    store = FileSystemCAS(tmp_path / "cas")
    ref = persist_voi_run_report(store, report)

    fresh_reader = FileSystemCAS.open_existing_read_only(store.root)
    reopened = load_voi_run_report(fresh_reader, ref)
    missing, zero = reopened.decisions

    assert reopened == report
    assert missing.recommended_action == zero.recommended_action == "advance"
    assert missing.expected_value == zero.expected_value
    assert missing.metadata["value_proxy_basis"] == "not_established"
    assert missing.metadata["expected_value_basis"] == "heuristic_available_signals"
    assert "heuristic" in missing.explanation
    assert zero.metadata["value_proxy_basis"] == "supplied_numeric_proxy"


def test_historical_nested_schedule_keeps_exact_canonical_digest() -> None:
    # A complete old schedule nested as in the persisted reentry checkpoints.
    old_wire = {
        "schedule": {
            "candidate_id": "informative",
            "priority": 0.12,
            "next_level": 3,
            "recommended_action": "advance",
            "reason": "advance_by_information_value",
            "economics": {
                "candidate_id": "informative",
                "recommended_action": "advance",
                "expected_improvement_per_usd": 0.0,
                "expected_falsification_value": 0.8,
                "expected_governance_value": 0.4,
                "timeout_risk": 0.0,
                "replay_cost_usd": 0.5,
                "calibration_debt": 0.0,
                "current_pareto_position": "unknown",
                "predicted_metric_vector": {"objective_value": 0.0},
                "promotion_likelihood": 0.4,
                "estimated_wall_seconds": 0.0,
                "estimated_cost_usd": 0.5,
                "estimated_cost_basis": "stage_cost_configuration",
                "predicted_disagreement": 0.8,
                "exploration_bonus": 0.12,
                "reserved_calibration_budget_usd": 0.0,
                "scheduler_mode": "simple",
            },
        }
    }
    canon = CanonSpec(forbid_floats=False)
    original_bytes = to_canonical_bytes(old_wire, canon)
    original_digest = sha256(original_bytes).hexdigest()

    loaded = from_canonical_bytes(original_bytes)
    historical = SchedulingDecision.model_validate(loaded["schedule"])
    assert historical.economics.value_proxy_basis is None
    assert historical.economics.expected_improvement_per_usd == 0.0

    replayed_bytes = to_canonical_bytes({"schedule": historical.model_dump(mode="json")}, canon)
    assert replayed_bytes == original_bytes
    assert sha256(replayed_bytes).hexdigest() == original_digest
    assert (
        "value_proxy_basis"
        not in scheduling_decision_to_voi_record(historical, run_id="historical").metadata
    )


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
