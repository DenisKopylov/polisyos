"""The live snapshot verifier replays the real Fabric writer's full profile."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from polisyos.common.async_tools import run_coro_sync
from polisyos.core import artifacts
from polisyos.core.artifacts.manifest import (
    ArtifactGovernanceInfo,
    ArtifactRef,
    EnvInfo,
    ProducerInfo,
    SchemaInfo,
    WarningRecord,
)
from polisyos.core.canon import CanonSpec
from polisyos.core.contracts.fabric import DataSnapshot, DataSnapshotRef, RetrievalSummary
from polisyos.fabric.data_plane.orchestrator import (
    _build_snapshot_from_evidence_async,
    _ingestion_snapshot_write_options,
    _retrieval_summary_write_options,
    verify_live_ingestion_snapshot_profile,
)
from polisyos.fabric.evidence import build_evidence_bundle, persist_evidence_bundle


@pytest.fixture
def live_snapshot(tmp_path: Path) -> tuple[artifacts.FileSystemCAS, DataSnapshotRef, DataSnapshot]:
    """Use real Fabric bundle/snapshot writers over a tiny test-owned payload."""
    store = artifacts.FileSystemCAS(tmp_path / "cas")
    data_ref = store.put_json(
        {"rows": [{"value": 4}]},
        artifacts.ArtifactWriteOptions(kind="fixture.dataset", media_type="application/json"),
        return_selected_profile=True,
    )
    evidence = build_evidence_bundle(sources=[data_ref], notes=["test-owned fixture"])
    evidence_ref = persist_evidence_bundle(store, evidence, return_selected_profile=True)
    snapshot_ref = run_coro_sync(
        _build_snapshot_from_evidence_async(
            store=artifacts.ensure_async_artifact_store(store),
            evidence_ref=evidence_ref,
            datasets_fetched=1,
            source="fixture",
        )
    )
    assert snapshot_ref is not None
    snapshot = artifacts.validate_core_model_json_artifact(DataSnapshot, store, snapshot_ref)
    return store, snapshot_ref, snapshot


def test_real_writer_selected_snapshot_profile_is_accepted(
    live_snapshot: tuple[artifacts.FileSystemCAS, DataSnapshotRef, DataSnapshot],
) -> None:
    store, ref, snapshot = live_snapshot
    assert ref.manifest_profile_sha256 is not None
    verify_live_ingestion_snapshot_profile(store, ref, snapshot)
    manifest = store.get_manifest(ref)
    assert [edge.role for edge in manifest.inputs] == [
        "evidence_ref",
        "data_ref",
        "quality_report_ref",
    ]


@pytest.mark.parametrize("field", ["parent", "data_ref", "evidence_ref", "quality_report_ref"])
def test_missing_selected_view_is_refused(
    live_snapshot: tuple[artifacts.FileSystemCAS, DataSnapshotRef, DataSnapshot],
    field: str,
) -> None:
    store, ref, snapshot = live_snapshot
    if field == "parent":
        ref = ref.model_copy(update={"manifest_profile_sha256": None})
    else:
        child = getattr(snapshot, field)
        assert isinstance(child, ArtifactRef)
        snapshot = snapshot.model_copy(
            update={field: child.model_copy(update={"manifest_profile_sha256": None})}
        )
    with pytest.raises(ValueError, match="live_snapshot_profile_required"):
        verify_live_ingestion_snapshot_profile(store, ref, snapshot)


@pytest.mark.parametrize(
    "mutation",
    [
        "producer",
        "environment",
        "governance",
        "warnings",
        "schema",
        "canon",
        "missing_data",
        "missing_evidence",
        "missing_quality",
        "duplicate_data",
    ],
)
def test_same_bytes_foreign_manifest_profile_is_refused(
    live_snapshot: tuple[artifacts.FileSystemCAS, DataSnapshotRef, DataSnapshot],
    mutation: str,
) -> None:
    store, ref, snapshot = live_snapshot
    payload = store.get_bytes(ref)
    manifest = store.get_manifest(ref)
    options = artifacts.ArtifactWriteOptions(
        kind=manifest.kind,
        media_type=manifest.media_type,
        schema=manifest.artifact_schema,
        producer=manifest.producer,
        env=manifest.env,
        inputs=manifest.inputs,
        canon=manifest.canon,
        governance=manifest.governance,
        tenant_context=manifest.tenant_context,
        same_input_closure=manifest.same_input_closure,
        authority=manifest.authority,
        warnings=manifest.warnings,
    )
    if mutation == "producer":
        options = replace(options, producer=ProducerInfo(component="fixture.foreign", version="1"))
    elif mutation == "environment":
        options = replace(
            options, env=EnvInfo(python="other", platform="other", deps_lock_hash="x")
        )
    elif mutation == "governance":
        options = replace(options, governance=ArtifactGovernanceInfo(classification="restricted"))
    elif mutation == "warnings":
        options = replace(options, warnings=[WarningRecord(code="foreign", msg="extra")])
    elif mutation == "schema":
        options = replace(
            options, schema=SchemaInfo(name="polisyos.core.DataSnapshot", version="9")
        )
    elif mutation == "canon":
        assert options.canon is not None
        options = replace(options, canon=options.canon.model_copy(update={"forbid_floats": True}))
    elif mutation == "duplicate_data":
        options = replace(options, inputs=[*manifest.inputs, manifest.inputs[1]])
    else:
        missing = {
            "missing_data": "data_ref",
            "missing_evidence": "evidence_ref",
            "missing_quality": "quality_report_ref",
        }[mutation]
        options = replace(
            options, inputs=[edge for edge in manifest.inputs if edge.role != missing]
        )
    sibling = store.put_bytes(payload, options, return_selected_profile=True)
    assert sibling.artifact_id == ref.artifact_id
    assert sibling.manifest_profile_sha256 != ref.manifest_profile_sha256
    assert store.verify(sibling).ok
    with pytest.raises(ValueError, match="live_snapshot_profile_drift"):
        verify_live_ingestion_snapshot_profile(store, sibling, snapshot)
    verify_live_ingestion_snapshot_profile(store, ref, snapshot)


def test_mismatched_snapshot_payload_is_refused(
    live_snapshot: tuple[artifacts.FileSystemCAS, DataSnapshotRef, DataSnapshot],
) -> None:
    store, ref, snapshot = live_snapshot
    changed = snapshot.model_copy(update={"stats": {"datasets_fetched": 5}})
    with pytest.raises(ValueError, match="live_snapshot_profile_drift"):
        verify_live_ingestion_snapshot_profile(store, ref, changed)


def test_non_writer_snapshot_field_is_refused(
    live_snapshot: tuple[artifacts.FileSystemCAS, DataSnapshotRef, DataSnapshot],
) -> None:
    store, ref, snapshot = live_snapshot
    changed = snapshot.model_copy(update={"warnings_ref": snapshot.data_ref})
    with pytest.raises(ValueError, match="live_snapshot_profile_drift"):
        verify_live_ingestion_snapshot_profile(store, ref, changed)


def test_missing_direct_child_is_refused(
    live_snapshot: tuple[artifacts.FileSystemCAS, DataSnapshotRef, DataSnapshot],
) -> None:
    store, ref, snapshot = live_snapshot
    child = snapshot.quality_report_ref
    assert child is not None and child.manifest_profile_sha256 is not None
    child_manifest = store._manifest_path_for_ref(child.artifact_id, child.manifest_profile_sha256)
    child_manifest.unlink()
    with pytest.raises(ValueError, match="live_snapshot_profile_drift"):
        verify_live_ingestion_snapshot_profile(store, ref, snapshot)


def test_corrupt_selected_snapshot_bytes_are_refused(
    live_snapshot: tuple[artifacts.FileSystemCAS, DataSnapshotRef, DataSnapshot],
) -> None:
    store, ref, snapshot = live_snapshot
    blob, _ = store._paths(ref.artifact_id)
    blob.write_bytes(b"{}")
    with pytest.raises(ValueError, match="live_snapshot_profile_drift"):
        verify_live_ingestion_snapshot_profile(store, ref, snapshot)


def _snapshot_with_quality(
    store: artifacts.FileSystemCAS,
    snapshot: DataSnapshot,
    quality_ref: ArtifactRef,
) -> tuple[DataSnapshotRef, DataSnapshot]:
    """Rebind the child through the real snapshot writer's options."""
    rebound = snapshot.model_copy(update={"quality_report_ref": quality_ref})
    ref = store.put_json(
        rebound,
        _ingestion_snapshot_write_options(rebound),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    return DataSnapshotRef.model_validate(ref.model_dump(mode="python")), rebound


@pytest.mark.parametrize("mutation", ["producer", "input", "schema", "canon", "governance"])
def test_same_bytes_foreign_retrieval_summary_profile_is_refused(
    live_snapshot: tuple[artifacts.FileSystemCAS, DataSnapshotRef, DataSnapshot],
    mutation: str,
) -> None:
    store, ref, snapshot = live_snapshot
    verify_live_ingestion_snapshot_profile(store, ref, snapshot)
    quality_ref = snapshot.quality_report_ref
    assert quality_ref is not None
    payload = store.get_bytes(quality_ref)
    manifest = store.get_manifest(quality_ref)
    options = artifacts.ArtifactWriteOptions(
        kind=manifest.kind,
        media_type=manifest.media_type,
        schema=manifest.artifact_schema,
        producer=manifest.producer,
        env=manifest.env,
        inputs=manifest.inputs,
        canon=manifest.canon,
        governance=manifest.governance,
        tenant_context=manifest.tenant_context,
        same_input_closure=manifest.same_input_closure,
        authority=manifest.authority,
        warnings=manifest.warnings,
    )
    if mutation == "producer":
        options = replace(options, producer=ProducerInfo(component="fixture.foreign", version="1"))
    elif mutation == "input":
        options = replace(
            options,
            inputs=[artifacts.input_ref_from_artifact_ref(snapshot.data_ref, role="foreign")],
        )
    elif mutation == "schema":
        options = replace(
            options,
            schema=SchemaInfo(name=RetrievalSummary.ARTIFACT_SCHEMA_NAME, version="9"),
        )
    elif mutation == "canon":
        assert options.canon is not None
        options = replace(options, canon=options.canon.model_copy(update={"forbid_floats": True}))
    else:
        options = replace(options, governance=ArtifactGovernanceInfo(classification="restricted"))
    sibling = store.put_bytes(payload, options, return_selected_profile=True)
    assert sibling.artifact_id == quality_ref.artifact_id
    assert sibling.manifest_profile_sha256 != quality_ref.manifest_profile_sha256
    assert store.verify(sibling).ok
    rebound_ref, rebound = _snapshot_with_quality(store, snapshot, sibling)
    with pytest.raises(ValueError, match="live_snapshot_profile_drift"):
        verify_live_ingestion_snapshot_profile(store, rebound_ref, rebound)
    verify_live_ingestion_snapshot_profile(store, ref, snapshot)


@pytest.mark.parametrize(
    "mutation", ["source_ref", "source", "dataset_count", "notes", "assessment_status"]
)
def test_retrieval_summary_must_match_writer_inputs_and_remain_unassessed(
    live_snapshot: tuple[artifacts.FileSystemCAS, DataSnapshotRef, DataSnapshot],
    mutation: str,
) -> None:
    store, ref, snapshot = live_snapshot
    quality_ref = snapshot.quality_report_ref
    assert quality_ref is not None
    payload = artifacts.load_core_json_artifact(store, quality_ref)
    assert isinstance(payload, dict) and payload["assessment_status"] == "not_assessed"
    if mutation == "source_ref":
        other = store.put_json(
            {"rows": [{"value": 99}]},
            artifacts.ArtifactWriteOptions(kind="fixture.dataset", media_type="application/json"),
            return_selected_profile=True,
        )
        payload["source_refs"] = [other.model_dump(mode="json")]
    elif mutation == "source":
        payload["source"] = "orchestrated_ingestion:foreign"
    elif mutation == "dataset_count":
        payload["observed_counts"] = {"datasets_fetched": 2}
    elif mutation == "notes":
        payload["notes"] = ["foreign notes"]
    else:
        payload["assessment_status"] = "assessed"
    changed_quality = store.put_json(
        payload,
        _retrieval_summary_write_options(),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    rebound_ref, rebound = _snapshot_with_quality(store, snapshot, changed_quality)
    with pytest.raises(ValueError, match="live_snapshot_profile_drift"):
        verify_live_ingestion_snapshot_profile(store, rebound_ref, rebound)
    verify_live_ingestion_snapshot_profile(store, ref, snapshot)
