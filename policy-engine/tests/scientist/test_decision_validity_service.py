from __future__ import annotations

from datetime import UTC, datetime

from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec
from polisyos.core.contracts.decision_validity import (
    DecisionBasisSection,
    DecisionDependencyEvent,
    DecisionDependencyKind,
    DecisionDependencyRef,
    DecisionTriggerRecord,
    DecisionTriggerSpec,
    DecisionTriggerType,
    DecisionValidityEnvelope,
    DecisionValidityEvaluation,
    DecisionValidityStatus,
)
from polisyos.core.contracts.feedback import DecisionMonitoringContract
from polisyos.scientist.decision_validity import DecisionValidityService


class _StoreWithRootProxy:
    def __init__(self, store: FileSystemCAS) -> None:
        self._store = store
        self.root = store.root

    def __getattr__(self, name: str):
        return getattr(self._store, name)


def _put_json(store: FileSystemCAS, payload, *, kind: str):
    return store.put_json(
        payload,
        PutOptions(
            kind=kind,
            media_type="application/json",
            schema=SchemaInfo(name=kind, version="1.0"),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )


def test_decision_validity_service_records_events_dedupes_and_tracks_monitoring(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    service = DecisionValidityService(store)
    envelope = DecisionValidityEnvelope(
        decision_lineage_key="lineage_fixture_001",
        policy_fingerprint="policy_fixture_v1",
        normative_basis=DecisionBasisSection(
            dependencies=[
                DecisionDependencyRef(
                    kind=DecisionDependencyKind.NORM_PACK,
                    key="norm::fixture_primary",
                    label="Fixture norm pack",
                )
            ]
        ),
        data_basis=DecisionBasisSection(
            dependencies=[
                DecisionDependencyRef(
                    kind=DecisionDependencyKind.DATASET,
                    key="dataset::fixture_primary",
                    label="Fixture dataset",
                )
            ]
        ),
        watched_triggers=[
            DecisionTriggerSpec(
                trigger_type=DecisionTriggerType.LAW_CHANGE,
                dependency_keys=["norm::fixture_primary"],
            )
        ],
    )
    baseline = DecisionValidityEvaluation(
        decision_lineage_key=envelope.decision_lineage_key,
        status=DecisionValidityStatus.ACTIVE,
        dependency_keys=envelope.dependency_keys(),
    )
    monitoring_contract = DecisionMonitoringContract.model_validate(
        {
            "run_id": "R_validity_fixture",
            "decision_lineage_key": envelope.decision_lineage_key,
            "anchor_at": "2026-03-12T12:00:00Z",
            "metrics": [
                {
                    "metric_id": "policy_cost",
                    "source_metric_id": "policy_cost",
                    "baseline_value": 100.0,
                    "confirm_range": {"lower": 90.0, "upper": 110.0},
                    "refute_range": {"lower": 80.0, "upper": 120.0},
                    "window": {"start_offset_days": 0, "end_offset_days": 30, "grace_days": 7},
                }
            ],
        }
    )
    monitoring_contract_ref = _put_json(
        store,
        monitoring_contract.model_dump(mode="json"),
        kind="scientist.decision_monitoring_contract",
    )
    packet_ref = _put_json(
        store,
        {
            "schema_version": "3.4",
            "decision_validity_envelope": envelope.model_dump(mode="json"),
            "decision_validity_baseline": baseline.model_dump(mode="json"),
        },
        kind="scientist.decision_packet",
    )

    service.register_decision_packet(
        packet_ref=str(packet_ref.artifact_id),
        envelope=envelope,
        baseline=baseline,
        monitoring_contract_ref=str(monitoring_contract_ref.artifact_id),
    )

    initial_summary = service.get_summary(str(packet_ref.artifact_id))
    assert initial_summary["status"] == "active"
    assert len(initial_summary["lifecycle"]["scheduled_jobs"]) == 1
    assert initial_summary["lifecycle"]["scheduled_jobs"][0]["job_kind"] == "scheduled_monitoring"
    assert initial_summary["lifecycle"]["scheduled_jobs"][0]["state"] == "pending"

    event = DecisionDependencyEvent(
        event_id="decision_evt_fixture_001",
        dedupe_key="decision_evt_fixture_law_change",
        occurred_at=datetime(2026, 3, 12, 13, 0, tzinfo=UTC),
        trigger_type=DecisionTriggerType.LAW_CHANGE,
        status=DecisionValidityStatus.REQUIRES_HUMAN_REVIEW,
        reason="fixture_law_changed",
        dependency_keys=["norm::fixture_primary"],
        source_ref="law://fixture/2026-03-12",
    )

    first = service.record_dependency_event(event=event)
    second = service.record_dependency_event(event=event)

    assert len(first) == 1
    assert len(second) == 1
    assert first[0].status == DecisionValidityStatus.REQUIRES_HUMAN_REVIEW

    summary = service.get_summary(str(packet_ref.artifact_id), force=True)
    assert summary["status"] == "requires_human_review"
    assert len(summary["lifecycle"]["events"]) == 1
    assert len(summary["lifecycle"]["transitions"]) == 1
    assert summary["lifecycle"]["pending_reviews"][0]["trigger_type"] == "law_change"
    assert summary["recommended_action"] == "human_review"

    monitoring_report_ref = _put_json(
        store,
        {"schema_version": "1.0", "overall_verdict": "refuted"},
        kind="scientist.decision_monitoring_report",
    )
    reissue_plan_ref = _put_json(
        store,
        {"schema_version": "1.0", "candidate_action": "refresh_decision"},
        kind="scientist.decision_reissue_plan",
    )
    service.update_feedback_refs(
        str(packet_ref.artifact_id),
        monitoring_contract_ref=str(monitoring_contract_ref.artifact_id),
        monitoring_report_ref=str(monitoring_report_ref.artifact_id),
        reissue_plan_ref=str(reissue_plan_ref.artifact_id),
    )

    refreshed_summary = service.get_summary(str(packet_ref.artifact_id))
    assert refreshed_summary["lifecycle"]["scheduled_jobs"][0]["state"] == "completed"
    assert refreshed_summary["lifecycle"]["scheduled_jobs"][0]["payload"]["monitoring_report_ref"] == str(
        monitoring_report_ref.artifact_id
    )
    assert refreshed_summary["lifecycle"]["reissue_candidates"] == [
        {"artifact_id": str(reissue_plan_ref.artifact_id)}
    ]


def test_decision_validity_service_applies_sticky_triggers_to_legacy_packets(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    service = DecisionValidityService(store)
    packet_ref = _put_json(
        store,
        {
            "schema_version": "3.4",
            "run_id": "R_legacy_fixture",
            "artifacts": {},
        },
        kind="scientist.decision_packet",
    )

    evaluation = service.mark_packet_trigger(
        packet_ref=str(packet_ref.artifact_id),
        trigger=DecisionTriggerRecord(
            trigger_type=DecisionTriggerType.CONTEXT_PROFILE_DRIFT,
            status=DecisionValidityStatus.REQUIRES_HUMAN_REVIEW,
            reason="target_applicability_changed",
        ),
    )

    assert evaluation.status == DecisionValidityStatus.REQUIRES_HUMAN_REVIEW
    summary = service.get_summary(str(packet_ref.artifact_id), force=True)
    assert summary["status"] == "requires_human_review"
    assert summary["review_required"] is True
    assert summary["lifecycle"]["pending_reviews"][0]["trigger_type"] == "context_profile_drift"


def test_decision_validity_service_accepts_protocol_store_proxy(tmp_path) -> None:
    base_store = FileSystemCAS(tmp_path)
    store = _StoreWithRootProxy(base_store)
    service = DecisionValidityService(store)
    packet_ref = _put_json(
        base_store,
        {"schema_version": "3.4", "run_id": "R_proxy_fixture", "artifacts": {}},
        kind="scientist.decision_packet",
    )

    evaluation = service.mark_packet_trigger(
        packet_ref=str(packet_ref.artifact_id),
        trigger=DecisionTriggerRecord(
            trigger_type=DecisionTriggerType.CONTEXT_PROFILE_DRIFT,
            status=DecisionValidityStatus.REQUIRES_HUMAN_REVIEW,
            reason="proxy_store_support",
        ),
    )

    assert evaluation.status == DecisionValidityStatus.REQUIRES_HUMAN_REVIEW
