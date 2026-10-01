from __future__ import annotations

import pytest

from polisyos.core.artifacts import ArtifactWriteOptions, ProducerInfo
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.scientist.governance.continuous.monitors import build_drift_monitor_event
from polisyos.scientist.governance.continuous.reports import (
    build_validity_report,
    export_public_validity_report,
    load_validity_report,
    persist_validity_report,
)


def _ref(seed: str, *, kind: str = "scientist.test") -> ArtifactRef:
    return ArtifactRef(
        artifact_id="sha256:" + seed * 64,
        kind=kind,
        media_type="application/json",
    )


def test_validity_report_public_export_redacts_internal_refs() -> None:
    event = build_drift_monitor_event(
        decision_packet_ref=_ref("1", kind="scientist.decision_packet"),
        event_type="fairness_drift",
        severity="warning",
        reason="Fairness drift requires reviewer triage.",
        affected_claim_ids=["claim_1"],
    )
    report = build_validity_report(
        decision_packet_ref=_ref("1", kind="scientist.decision_packet"),
        monitor_events=[event],
        hidden_internal_ref_ids=["hidden_holdout_suite_42"],
        metadata={"internal_monitor_ref": "hidden_eval_answer_ref"},
    )

    public = export_public_validity_report(report)

    assert public["status"] == "review_required"
    assert public["event_count"] == 1
    assert "hidden_holdout_suite_42" not in str(public)
    assert "internal_monitor_ref" not in str(public)


def test_public_export_rejects_hidden_decision_packet_ref() -> None:
    event = build_drift_monitor_event(
        decision_packet_ref=_ref("1", kind="scientist.decision_packet"),
        event_type="calibration_drift",
        severity="info",
        reason="Calibration is being monitored.",
    )
    report = build_validity_report(
        decision_packet_ref=ArtifactRef(
            artifact_id="sha256:" + "a" * 64,
            kind="scientist.hidden_eval.decision_packet",
            media_type="application/json",
        ),
        monitor_events=[event],
    )

    with pytest.raises(ValueError, match="hidden/internal"):
        export_public_validity_report(report)


def test_validity_report_persists_to_cas(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    event = build_drift_monitor_event(
        decision_packet_ref=_ref("1", kind="scientist.decision_packet"),
        event_type="policy_context_drift",
        severity="warning",
        reason="Policy context changed.",
        affected_claim_ids=["claim_1"],
    )
    report = build_validity_report(
        decision_packet_ref=_ref("1", kind="scientist.decision_packet"),
        monitor_events=[event],
        reissue_packet_ref=_ref("2", kind="scientist.reissue_packet"),
    )

    ref = persist_validity_report(store, report)
    loaded = load_validity_report(store, ref)

    assert loaded == report
    assert ref.kind == "scientist.continuous_governance_report"
    selected_ref, missing_ref, _ = _selected_and_missing_profile(store, ref)
    assert load_validity_report(store, selected_ref) == report
    with pytest.raises((KeyError, OSError, ValueError)):
        load_validity_report(store, missing_ref)


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
