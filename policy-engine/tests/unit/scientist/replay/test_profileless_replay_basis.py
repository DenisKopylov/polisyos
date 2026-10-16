from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest

from polisyos.core.artifacts.graph import NodeStatus
from polisyos.core.artifacts.manifest import (
    ArtifactRef,
    SchemaInfo,
    input_ref_from_artifact_ref,
)
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec
from polisyos.scientist.policy_design.output import (
    ReplayableAuditBundle,
    _replayable_audit_bundle_artifact_refs,
    _replayable_audit_bundle_input_refs,
    load_replayable_audit_bundle,
    persist_replayable_audit_bundle,
)
from polisyos.scientist.replay.deterministic import measure_replayable_audit_bundle
from polisyos.scientist.replay.verification import verify_and_persist_replay_bundle


def _selected_ref(store: FileSystemCAS, *, name: str, kind: str) -> ArtifactRef:
    return store.put_json(
        {"name": name},
        PutOptions(
            kind=kind,
            media_type="application/json",
            schema=SchemaInfo(name=f"tests.{name}", version="1.0"),
        ),
        return_selected_profile=True,
    )


def _complete_bundle(store: FileSystemCAS, *, run_id: str) -> ReplayableAuditBundle:
    refs = {
        "candidate": _selected_ref(
            store, name=f"{run_id}.candidate", kind="scientist.policy_candidate_schema"
        ),
        "evaluation": _selected_ref(
            store, name=f"{run_id}.evaluation", kind="scientist.policy_evaluation_vector"
        ),
        "readiness": _selected_ref(
            store, name=f"{run_id}.readiness", kind="scientist.readiness_report"
        ),
        "runtime_input": _selected_ref(
            store, name=f"{run_id}.runtime_input", kind="scientist.runtime_input"
        ),
        "runtime_artifact": _selected_ref(
            store, name=f"{run_id}.runtime_artifact", kind="scientist.runtime_artifact"
        ),
        "runtime_report": _selected_ref(
            store, name=f"{run_id}.runtime_report", kind="scientist.runtime_report"
        ),
        "upstream": _selected_ref(store, name=f"{run_id}.upstream", kind="scientist.audit"),
        "side_information": _selected_ref(
            store, name=f"{run_id}.side_information", kind="scientist.side_information"
        ),
        "extra": _selected_ref(store, name=f"{run_id}.extra", kind="scientist.extra_artifact"),
    }
    return ReplayableAuditBundle(
        run_id=run_id,
        candidate_ref=refs["candidate"],
        evaluation_ref=refs["evaluation"],
        readiness_ref=refs["readiness"],
        workflow_id="policy_design",
        execution_profile="selected-local",
        runtime_input_refs={"decision_packet": refs["runtime_input"]},
        runtime_artifacts_index={"output": refs["runtime_artifact"]},
        runtime_reports_index={"summary": refs["runtime_report"]},
        upstream_audit_refs=[refs["upstream"]],
        actionable_side_information_refs=[refs["side_information"]],
        artifact_refs={"extra": refs["extra"]},
    )


def _profileless_for_role(bundle: ReplayableAuditBundle, role: str) -> ReplayableAuditBundle:
    target = next(item for item in _replayable_audit_bundle_input_refs(bundle) if item.role == role)
    assert target.manifest_profile_sha256 is not None
    payload = bundle.model_dump(mode="python")
    changed = 0

    def strip(value: Any) -> Any:
        nonlocal changed
        if isinstance(value, dict):
            is_target = (
                "kind" in value
                and "media_type" in value
                and str(value.get("artifact_id")) == str(target.artifact_id)
                and value.get("manifest_profile_sha256") == target.manifest_profile_sha256
            )
            if is_target:
                value["manifest_profile_sha256"] = None
                changed += 1
            for key, nested in tuple(value.items()):
                if isinstance(nested, (dict, list)):
                    value[key] = strip(nested)
            return value
        if isinstance(value, list):
            return [strip(item) for item in value]
        return value

    payload = strip(payload)
    assert changed == 1, f"expected exactly one payload ref for {role}, changed={changed}"
    return ReplayableAuditBundle.model_validate(payload)


def test_replay_verifier_refuses_profileless_reference_in_every_projected_role(
    tmp_path: Path,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    complete = _complete_bundle(store, run_id="selected-replay-basis")
    roles = [item.role for item in _replayable_audit_bundle_input_refs(complete)]
    assert len(roles) == 9
    assert len(set(roles)) == len(roles)

    selected_bundle_ref = persist_replayable_audit_bundle(store, complete)
    selected_report_ref = verify_and_persist_replay_bundle(
        store, run_id=complete.run_id, replay_bundle_ref=selected_bundle_ref
    )
    assert selected_report_ref.manifest_profile_sha256 is not None

    for role in roles:
        run_id = f"profileless-{role}"
        malformed = complete.model_copy(update={"run_id": run_id})
        malformed = _profileless_for_role(malformed, role)
        replay_bundle_ref = persist_replayable_audit_bundle(store, malformed)
        with pytest.raises(
            ValueError,
            match=re.escape(f"replay_bundle_{role}_selected_profile_required"),
        ):
            verify_and_persist_replay_bundle(
                store, run_id=run_id, replay_bundle_ref=replay_bundle_ref
            )


def test_replay_measurement_marks_profileless_current_basis_incomplete(tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    complete = _complete_bundle(store, run_id="profileless-current-basis")
    malformed = _profileless_for_role(complete, "runtime_input:decision_packet")
    replay_bundle_ref = persist_replayable_audit_bundle(store, malformed)
    archived_view = load_replayable_audit_bundle(store, replay_bundle_ref)
    assert archived_view.runtime_input_refs["decision_packet"].manifest_profile_sha256 is None

    measurement = measure_replayable_audit_bundle(store, replay_bundle_ref)

    assert measurement.completeness.level.value == "incomplete"
    assert measurement.completeness.ok is False
    assert measurement.passed is False
    assert "bundle_dependency_selected_profile_missing" in measurement.reason_codes
    assert measurement.details["unselected_profile_roles"] == ["runtime_input:decision_packet"]


@pytest.mark.parametrize("damage", ["missing_blob", "corrupt_blob"])
def test_replay_measurement_verifies_selected_basis_blob_integrity(
    tmp_path: Path, damage: str
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    bundle = _complete_bundle(store, run_id=f"integrity-{damage}")
    selected_ref = next(
        ref
        for role, ref in _replayable_audit_bundle_artifact_refs(bundle)
        if role == "runtime_input:decision_packet"
    )
    replay_bundle_ref = persist_replayable_audit_bundle(store, bundle)
    assert store.verify(selected_ref).ok is True
    assert store.get_manifest(selected_ref).integrity.sha256 == selected_ref.artifact_id.hex

    blob_path, _manifest_path = store._paths(selected_ref.artifact_id)
    if damage == "missing_blob":
        blob_path.unlink()
    else:
        blob_path.write_bytes(b"tampered runtime input")

    assert store.verify(selected_ref).ok is False
    assert store.get_manifest(selected_ref).integrity.sha256 == selected_ref.artifact_id.hex

    measurement = measure_replayable_audit_bundle(store, replay_bundle_ref)

    assert measurement.completeness.level.value == "incomplete"
    assert measurement.completeness.ok is False
    assert measurement.passed is False
    assert measurement.completeness.total_artifacts == 10
    assert measurement.completeness.present_artifacts == 9
    assert "bundle_dependency_integrity_failed" in measurement.reason_codes
    failure = next(
        item
        for item in measurement.completeness.corrupted
        if item.role == "runtime_input:decision_packet"
    )
    assert failure.status is NodeStatus.CORRUPTED
    assert measurement.details["integrity_errors"]["runtime_input:decision_packet"]


def test_replay_verification_binds_nested_edge_to_the_selected_body_view(
    tmp_path: Path,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    bundle = _complete_bundle(store, run_id="nested-selected-view")
    source_ref = bundle.runtime_input_refs["decision_packet"]
    alternate_ref = store.put_bytes(
        store.get_bytes(source_ref),
        PutOptions(
            kind=source_ref.kind,
            media_type=source_ref.media_type,
            schema=SchemaInfo(name="tests.AlternateRuntimeInput", version="9.9"),
        ),
        return_selected_profile=True,
    )
    assert alternate_ref.artifact_id == source_ref.artifact_id
    assert alternate_ref.manifest_profile_sha256 != source_ref.manifest_profile_sha256
    assert store.verify(alternate_ref).ok is True

    selected_view_bundle = bundle.model_copy(
        update={
            "runtime_input_refs": {
                **bundle.runtime_input_refs,
                "decision_packet": alternate_ref,
            }
        }
    )
    selected_bundle_ref = persist_replayable_audit_bundle(store, selected_view_bundle)
    selected_report_ref = verify_and_persist_replay_bundle(
        store,
        run_id=selected_view_bundle.run_id,
        replay_bundle_ref=selected_bundle_ref,
    )
    assert selected_report_ref.manifest_profile_sha256 is not None
    selected_measurement = measure_replayable_audit_bundle(store, selected_bundle_ref)
    assert selected_measurement.completeness.level.value == "complete"

    mismatched_inputs = [
        input_ref_from_artifact_ref(
            alternate_ref if role == "runtime_input:decision_packet" else ref,
            role=role,
        )
        for role, ref in _replayable_audit_bundle_artifact_refs(bundle)
    ]
    mismatched_bundle_ref = store.put_json(
        bundle.model_dump(mode="json", exclude_none=True),
        PutOptions(
            kind="scientist.replayable_audit_bundle",
            media_type="application/json",
            schema=SchemaInfo(
                name="polisyos.scientist.policy_design.ReplayableAuditBundle",
                version="1.0",
            ),
            inputs=mismatched_inputs,
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    mismatched_manifest = store.get_manifest(mismatched_bundle_ref)
    mismatched_edge = next(
        edge for edge in mismatched_manifest.inputs if edge.role == "runtime_input:decision_packet"
    )
    assert mismatched_edge.manifest_profile_sha256 == alternate_ref.manifest_profile_sha256
    assert (
        mismatched_edge.manifest_profile_sha256
        != bundle.runtime_input_refs["decision_packet"].manifest_profile_sha256
    )

    with pytest.raises(
        ValueError,
        match=re.escape("replay_bundle_runtime_input:decision_packet_input_mismatch"),
    ):
        verify_and_persist_replay_bundle(
            store,
            run_id=bundle.run_id,
            replay_bundle_ref=mismatched_bundle_ref,
        )

    measurement = measure_replayable_audit_bundle(store, mismatched_bundle_ref)

    assert measurement.completeness.level.value == "incomplete"
    assert measurement.completeness.ok is False
    assert measurement.passed is False
    assert "bundle_dependency_input_mismatch" in measurement.reason_codes
    assert measurement.details["input_mismatch_roles"] == ["runtime_input:decision_packet"]
    failure = next(
        item
        for item in measurement.completeness.corrupted
        if item.role == "runtime_input:decision_packet"
    )
    assert failure.status is NodeStatus.CORRUPTED


def test_replay_measurement_refuses_profileless_outer_bundle_but_archive_load_remains_available(
    tmp_path: Path,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    bundle = _complete_bundle(store, run_id="profileless-outer-bundle")
    selected_bundle_ref = persist_replayable_audit_bundle(store, bundle)
    selected_measurement = measure_replayable_audit_bundle(store, selected_bundle_ref)
    assert selected_measurement.completeness.level.value == "complete"
    assert selected_measurement.completeness.total_artifacts == 10
    assert selected_measurement.completeness.present_artifacts == 10
    profileless_ref = selected_bundle_ref.model_copy(update={"manifest_profile_sha256": None})

    archived_view = load_replayable_audit_bundle(store, profileless_ref)
    assert archived_view.run_id == bundle.run_id

    measurement = measure_replayable_audit_bundle(store, profileless_ref)
    assert measurement.completeness.level.value == "incomplete"
    assert measurement.completeness.ok is False
    assert measurement.passed is False
    assert "replay_bundle_selected_profile_required" in measurement.reason_codes
    assert measurement.details["root_admission_error"] == "replay_bundle_selected_profile_required"
    assert measurement.completeness.total_artifacts == 1
    assert measurement.completeness.missing[0].role == "replay_bundle"

    with pytest.raises(ValueError, match=re.escape("replay_bundle_selected_profile_required")):
        verify_and_persist_replay_bundle(
            store, run_id=bundle.run_id, replay_bundle_ref=profileless_ref
        )


@pytest.mark.parametrize(
    ("mutation", "expected_error"),
    [
        ("kind", "replay_bundle_kind_or_media_type_mismatch"),
        ("media_type", "replay_bundle_kind_or_media_type_mismatch"),
        ("profile", "replay_bundle_selected_manifest_mismatch"),
        ("schema", "replay_bundle_owner_schema_mismatch"),
    ],
)
def test_replay_consumers_reject_false_outer_bundle_owner_or_profile(
    tmp_path: Path, mutation: str, expected_error: str
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    bundle = _complete_bundle(store, run_id=f"outer-owner-{mutation}")
    selected_bundle_ref = persist_replayable_audit_bundle(store, bundle)
    if mutation in {"kind", "media_type", "profile"}:
        update: dict[str, object]
        if mutation == "kind":
            update = {"kind": "scientist.foreign_bundle"}
        elif mutation == "media_type":
            update = {"media_type": "application/octet-stream"}
        else:
            update = {"manifest_profile_sha256": "sha256:" + "0" * 64}
        malformed_ref = selected_bundle_ref.model_copy(update=update)
    else:
        manifest = store.get_manifest(selected_bundle_ref)
        malformed_ref = store.put_bytes(
            store.get_bytes(selected_bundle_ref),
            PutOptions(
                kind=selected_bundle_ref.kind,
                media_type=selected_bundle_ref.media_type,
                schema=SchemaInfo(name="tests.ForeignReplayBundle", version="9.9"),
                inputs=manifest.inputs,
            ),
            return_selected_profile=True,
        )
        assert malformed_ref.artifact_id == selected_bundle_ref.artifact_id
        assert store.verify(malformed_ref).ok is True

    measurement = measure_replayable_audit_bundle(store, malformed_ref)
    assert measurement.completeness.level.value == "incomplete"
    assert measurement.completeness.ok is False
    assert measurement.passed is False
    assert expected_error in measurement.reason_codes
    assert any(
        item.role == "replay_bundle"
        for item in measurement.completeness.missing + measurement.completeness.corrupted
    )

    with pytest.raises(ValueError, match=re.escape(expected_error)):
        verify_and_persist_replay_bundle(
            store, run_id=bundle.run_id, replay_bundle_ref=malformed_ref
        )


@pytest.mark.parametrize("damage", ["missing_blob", "corrupt_blob"])
def test_replay_consumers_reject_outer_bundle_with_invalid_selected_bytes(
    tmp_path: Path, damage: str
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    bundle = _complete_bundle(store, run_id=f"outer-integrity-{damage}")
    selected_bundle_ref = persist_replayable_audit_bundle(store, bundle)
    assert store.verify(selected_bundle_ref).ok is True
    blob_path, _manifest_path = store._paths(selected_bundle_ref.artifact_id)
    if damage == "missing_blob":
        blob_path.unlink()
    else:
        blob_path.write_bytes(b"tampered replay bundle")

    assert store.verify(selected_bundle_ref).ok is False
    measurement = measure_replayable_audit_bundle(store, selected_bundle_ref)
    assert measurement.completeness.level.value == "incomplete"
    assert measurement.completeness.ok is False
    assert measurement.passed is False
    assert "replay_bundle_integrity_failed" in measurement.reason_codes
    assert measurement.details["root_integrity_error"]
    assert measurement.completeness.corrupted[0].role == "replay_bundle"

    with pytest.raises(ValueError, match=re.escape("replay_bundle_integrity_failed")):
        verify_and_persist_replay_bundle(
            store, run_id=bundle.run_id, replay_bundle_ref=selected_bundle_ref
        )
