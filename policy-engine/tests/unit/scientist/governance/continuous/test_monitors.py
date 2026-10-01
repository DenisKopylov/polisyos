from __future__ import annotations

import pytest

from polisyos.core.artifacts import ArtifactIntegrityError, ArtifactWriteOptions, ProducerInfo
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.canon import CanonSpec, content_hash, from_canonical_bytes, to_canonical_bytes
from polisyos.runtime.http.services.control_plane_store import ControlPlaneStore
from polisyos.runtime.quality.event_log import RuntimeDiagnosticEventLog
from polisyos.scientist.governance.continuous import monitors
from polisyos.scientist.governance.continuous.monitors import (
    DecisionValidityStatus,
    GovernanceMonitorEvent,
    aggregate_validity_status,
    build_drift_monitor_event,
    persist_governance_monitor_event,
    recommend_validity_action,
    resolve_governance_monitor_event,
)


def _ref(seed: str, *, kind: str = "scientist.decision_packet") -> ArtifactRef:
    return ArtifactRef(
        artifact_id="sha256:" + seed * 64,
        kind=kind,
        media_type="application/json",
    )


def _event_log(tmp_path, store: FileSystemCAS) -> RuntimeDiagnosticEventLog:
    return RuntimeDiagnosticEventLog(
        store=ControlPlaneStore(
            backend="sqlite",
            sqlite_path=tmp_path / "control.sqlite3",
        ),
        artifact_store=store,
    )


def test_drift_warning_triggers_human_review() -> None:
    event = build_drift_monitor_event(
        decision_packet_ref=_ref("1"),
        event_type="fairness_drift",
        severity="warning",
        reason="Subgroup false-block rate exceeded warning threshold.",
        affected_claim_ids=["claim_fairness"],
        metric_name="false_block_rate",
        observed_value=0.17,
        threshold=0.1,
    )

    recommendation = recommend_validity_action(event)

    assert recommendation.status is DecisionValidityStatus.REVIEW_REQUIRED
    assert recommendation.recommended_action == "human_review"
    assert recommendation.human_review_required is True


def test_drift_block_triggers_reissue_assessment() -> None:
    event = build_drift_monitor_event(
        decision_packet_ref=_ref("1"),
        event_type="calibration_drift",
        severity="block",
        reason="Calibration drift exceeded release envelope.",
        affected_claim_ids=["claim_calibration"],
    )

    recommendation = recommend_validity_action(event)

    assert recommendation.reissue_recommended is True
    assert recommendation.human_review_required is True
    assert aggregate_validity_status([recommendation]) is DecisionValidityStatus.REVIEW_REQUIRED


def test_info_monitor_event_keeps_artifact_monitoring() -> None:
    event = build_drift_monitor_event(
        decision_packet_ref=_ref("1"),
        event_type="policy_context_drift",
        severity="info",
        reason="Related statute is being watched but did not change.",
    )

    recommendation = recommend_validity_action(event)

    assert recommendation.status is DecisionValidityStatus.MONITORING
    assert recommendation.recommended_action == "continue_monitoring"


def test_stale_lifecycle_decision_emits_runtime_authority_evidence(tmp_path) -> None:
    emit = getattr(monitors, "emit_governance_lifecycle_evidence", None)
    assert emit is not None, "Phase 2.7 must expose runtime lifecycle evidence emission"

    store = FileSystemCAS(tmp_path)
    event_log = _event_log(tmp_path, store)
    decision_ref = _ref("1")
    monitor_event_ref = _ref("2", kind="scientist.governance_monitor_event")
    event = GovernanceMonitorEvent(
        event_id="stale-source-event",
        decision_packet_ref=decision_ref,
        event_type="source_invalidation",
        severity="warning",
        affected_claim_ids=["claim_1"],
        reason="Source freshness TTL expired.",
    )
    recommendation = recommend_validity_action(event)

    result = emit(
        store,
        lifecycle_decision="stale",
        decision_packet_ref=decision_ref,
        status=recommendation.status,
        reason=recommendation.reason,
        monitor_event_refs=[monitor_event_ref],
        run_id="R_lifecycle",
        job_id="job-lifecycle",
        tenant_id="tenant-1",
        cell_id="cell-a",
        trace_id="trace-lifecycle",
        span_id="span-stale",
        effective_mode_ref="sha256:" + "3" * 64,
        fallback_degradation_ref="sha256:" + "4" * 64,
        event_log=event_log,
    )

    assert result.runtime_quality_ref_key == "continuous_governance_stale_report_ref"
    assert result.runtime_quality_refs == {
        "continuous_governance_stale_report_ref": str(result.report_ref.artifact_id)
    }
    assert result.report_ref.kind == "governance_lifecycle_report"
    assert result.diagnostic_event_ref.kind == "runtime_quality.diagnostic_event"
    assert result.authority_envelope_ref.kind == "runtime_quality.evidence_authority_envelope"
    assert result.report["schema_compatibility"]["decision"] == "compatible"
    assert result.report["effective_mode_ref"] == "sha256:" + "3" * 64
    assert result.report["fallback_degradation_ref"] == "sha256:" + "4" * 64
    persisted_report = from_canonical_bytes(store.get_bytes(result.report_ref.artifact_id))
    assert persisted_report == result.report
    assert result.payload_sha256 == content_hash(
        to_canonical_bytes(result.report, CanonSpec(forbid_floats=False))
    )
    assert result.diagnostic_event["event_type"] == (
        "polisyos.runtime.diagnostic.governance_lifecycle_decision.v1"
    )
    assert result.authority_envelope["cas_ref"] == str(result.report_ref.artifact_id)


def test_serious_lifecycle_decision_requires_durable_event_log(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    decision_ref = _ref("1")
    monitor_event_ref = _ref("2", kind="scientist.governance_monitor_event")

    with pytest.raises(ValueError, match="event_log"):
        monitors.emit_governance_lifecycle_evidence(
            store,
            lifecycle_decision="stale",
            decision_packet_ref=decision_ref,
            status=DecisionValidityStatus.STALE,
            reason="Source freshness TTL expired.",
            monitor_event_refs=[monitor_event_ref],
            run_id="R_lifecycle",
            job_id="job-lifecycle",
            tenant_id="tenant-1",
            cell_id="cell-a",
            trace_id="trace-lifecycle",
            span_id="span-stale",
            effective_mode_ref="sha256:" + "3" * 64,
            fallback_degradation_ref="sha256:" + "4" * 64,
            requested_execution_profile="production",
            effective_execution_profile="production",
        )


@pytest.mark.parametrize(
    ("source_class", "event_type", "perturbation"),
    [
        (
            "incident",
            "incident",
            {"source_class": "incident", "incident_report_ref": _ref("a")},
        ),
        (
            "appeal",
            "policy_context_drift",
            {
                "source_class": "appeal",
                "appeal_evidence_ref": _ref("b"),
                "affected_instance_ref": _ref("1"),
                "scope": "instance",
            },
        ),
        (
            "correction",
            "source_invalidation",
            {
                "source_class": "correction",
                "evidence_validity_event_ref": _ref("c"),
                "replacement_refs": (_ref("d"),),
            },
        ),
        (
            "retraction",
            "source_invalidation",
            {"source_class": "retraction", "evidence_validity_event_ref": _ref("e")},
        ),
        (
            "legal_change",
            "policy_context_drift",
            {"source_class": "legal_change", "legal_change_evidence_ref": _ref("f")},
        ),
        (
            "discovered_bias",
            "fairness_drift",
            {"source_class": "discovered_bias", "bias_evidence_ref": _ref("9")},
        ),
    ],
)
def test_six_perturbation_classes_round_trip_as_exact_distinct_bytes(
    tmp_path,
    source_class: str,
    event_type: str,
    perturbation: dict[str, object],
) -> None:
    store = FileSystemCAS(tmp_path / source_class)
    event = GovernanceMonitorEvent.model_validate(
        {
            "event_id": f"event-{source_class}",
            "decision_packet_ref": _ref("1"),
            "event_type": event_type,
            "severity": "warning",
            "affected_claim_ids": ["claim-ds18"],
            "reason": "The class identity survives the same review-required posture.",
            "perturbation": perturbation,
            "advisory_posture": "review_required",
        }
    )

    persisted = persist_governance_monitor_event(store, event)
    loaded = resolve_governance_monitor_event(store, persisted.event_ref)

    assert loaded == persisted
    assert loaded.event.perturbation is not None
    assert loaded.event.perturbation.source_class == source_class
    assert loaded.event.advisory_posture == "review_required"

    selected_ref, missing_ref, raw = _selected_and_missing_profile(
        store, persisted.event_ref
    )
    selected = resolve_governance_monitor_event(store, selected_ref)
    assert selected.event_ref == selected_ref
    assert selected.event == event
    assert store.get_bytes(selected_ref) == raw
    with pytest.raises((KeyError, OSError, ValueError)):
        resolve_governance_monitor_event(store, missing_ref)

    with pytest.raises(ArtifactIntegrityError):
        resolve_governance_monitor_event(
            store,
            persisted.event_ref.model_copy(update={"kind": "test.wrong_profile"}),
        )


def _selected_and_missing_profile(
    store: FileSystemCAS, ref: ArtifactRef
) -> tuple[ArtifactRef, ArtifactRef, bytes]:
    manifest = store.get_manifest(ref)
    raw = store.get_bytes(ref)
    selected = store.put_bytes(
        raw,
        ArtifactWriteOptions(
            kind=ref.kind,
            media_type=ref.media_type,
            schema=manifest.artifact_schema,
            producer=ProducerInfo(component="tests.r9.profile_probe", version="2"),
            env=manifest.env,
            inputs=manifest.inputs,
            canon=manifest.canon,
            governance=manifest.governance,
            tenant_context=manifest.tenant_context,
            same_input_closure=manifest.same_input_closure,
            authority=manifest.authority,
        ),
    )
    assert selected.artifact_id == ref.artifact_id
    assert selected.kind == ref.kind
    assert selected.media_type == ref.media_type
    assert selected.manifest_profile_sha256 != ref.manifest_profile_sha256
    assert store.get_bytes(selected) == raw
    present_profiles = {ref.manifest_profile_sha256, selected.manifest_profile_sha256}
    absent_profile = next(
        f"sha256:{digit * 64}"
        for digit in "0123456789abcdef"
        if f"sha256:{digit * 64}" not in present_profiles
        and not store.has_manifest_view(ref.artifact_id, f"sha256:{digit * 64}")
    )
    assert not store.has_manifest_view(ref.artifact_id, absent_profile)
    missing = selected.model_copy(update={"manifest_profile_sha256": absent_profile})
    assert missing.artifact_id == ref.artifact_id
    assert missing.kind == ref.kind
    assert missing.media_type == ref.media_type
    return selected, missing, raw
