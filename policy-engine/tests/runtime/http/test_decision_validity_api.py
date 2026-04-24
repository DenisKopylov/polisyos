from __future__ import annotations

from datetime import UTC, datetime

from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec
from polisyos.core.contracts.decision_validity import (
    DecisionBasisSection,
    DecisionDependencyKind,
    DecisionDependencyRef,
    DecisionValidityEnvelope,
    DecisionValidityEvaluation,
    DecisionValidityStatus,
)
from polisyos.scientist.decision_validity import DecisionValidityService


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


def test_publish_decision_validity_event_updates_registered_packets(runtime_api_env) -> None:
    client = runtime_api_env["client"]
    store = FileSystemCAS(runtime_api_env["cas_root"])
    service = DecisionValidityService(store)
    envelope = DecisionValidityEnvelope(
        decision_lineage_key="lineage_api_fixture",
        policy_fingerprint="policy_api_fixture_v1",
        normative_basis=DecisionBasisSection(
            dependencies=[
                DecisionDependencyRef(
                    kind=DecisionDependencyKind.NORM_PACK,
                    key="norm::api_fixture",
                )
            ]
        ),
    )
    baseline = DecisionValidityEvaluation(
        decision_lineage_key=envelope.decision_lineage_key,
        status=DecisionValidityStatus.ACTIVE,
        dependency_keys=envelope.dependency_keys(),
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
    )

    response = client.post(
        "/api/v1/control/decision-validity/events",
        json={
            "trigger_type": "law_change",
            "status": "requires_human_review",
            "reason": "fixture_api_law_changed",
            "dependency_keys": ["norm::api_fixture"],
            "source_ref": "law://fixture/api",
            "occurred_at": datetime(2026, 3, 12, 14, 0, tzinfo=UTC).isoformat(),
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["affected_packets"] == [str(packet_ref.artifact_id)]
    assert body["affected_statuses"] == {"requires_human_review": 1}

    summary = service.get_summary(str(packet_ref.artifact_id), force=True)
    assert summary["status"] == "requires_human_review"
    assert summary["lifecycle"]["events"][0]["reason"] == "fixture_api_law_changed"
