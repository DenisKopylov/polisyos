"""Semantic epoch reads the actual Fabric evidence writer's selected profiles."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import pytest

from polisyos.core import artifacts
from polisyos.core.contracts.fabric import IngestionExecutionContext
from polisyos.fabric.evidence.evidence import build_evidence_bundle, persist_evidence_bundle
from polisyos.runtime.quality import semantic_epoch
from tests.unit.fabric.evidence.test_live_evidence_writer_profile import (
    _actual_bundle,
    _foreign_profile,
)


def test_legacy_evidence_bundle_profile_still_reads(tmp_path: Path) -> None:
    """An actual pre-lineage writer view remains readable without invented edges."""
    store = artifacts.FileSystemCAS(tmp_path / "cas")
    source = store.put_bytes(
        b"legacy source",
        artifacts.ArtifactWriteOptions(
            kind="test.legacy_source", media_type="application/octet-stream"
        ),
        return_selected_profile=True,
    )
    bundle = build_evidence_bundle(sources=[source], notes=["controlled legacy fixture"])
    ref = persist_evidence_bundle(store, bundle, return_selected_profile=True)
    manifest = store.get_manifest(ref)
    assert manifest.artifact_schema == artifacts.SchemaInfo(
        name="fabric.evidence_bundle", version="1.0"
    )
    assert manifest.inputs == []
    assert semantic_epoch._load_selected_acquisition_mapping(
        store, ref, expected_kind="fabric.evidence_bundle"
    ) == bundle.model_dump(mode="json")


def test_record_context_without_provenance_uses_v2_source_closure(tmp_path: Path) -> None:
    """The writer's record-only v2 profile does not invent a provenance edge."""
    store = artifacts.FileSystemCAS(tmp_path / "cas")
    source = store.put_bytes(
        b"record source",
        artifacts.ArtifactWriteOptions(
            kind="test.record_source", media_type="application/octet-stream"
        ),
        return_selected_profile=True,
    )
    bundle = build_evidence_bundle(
        sources=[source],
        execution_context=IngestionExecutionContext(mode="record", capture_session_id="fixture"),
    )
    ref = persist_evidence_bundle(store, bundle, return_selected_profile=True)
    manifest = store.get_manifest(ref)
    assert manifest.artifact_schema == artifacts.SchemaInfo(
        name="fabric.evidence_bundle", version="2.0"
    )
    assert manifest.inputs == [
        artifacts.input_ref_from_artifact_ref(source, role="fabric.ingestion.payload")
    ]
    assert semantic_epoch._load_selected_acquisition_mapping(
        store, ref, expected_kind="fabric.evidence_bundle"
    ) == bundle.model_dump(mode="json")


@pytest.mark.parametrize("replay", [False, True])
def test_evidence_bundle_writer_profile_reads_bound_inputs(tmp_path: Path, replay: bool) -> None:
    """The real writer's v2 selected input closure reaches the epoch reader."""
    store, ref, bundle = _actual_bundle(tmp_path, replay=replay)
    manifest = store.get_manifest(ref)
    assert manifest.artifact_schema == artifacts.SchemaInfo(
        name="fabric.evidence_bundle", version="2.0"
    )
    assert semantic_epoch._load_selected_acquisition_mapping(
        store, ref, expected_kind="fabric.evidence_bundle"
    ) == bundle.model_dump(mode="json")


@pytest.mark.parametrize("mutation", ["missing", "role", "sibling"])
def test_evidence_bundle_reader_rejects_false_input_closure(
    tmp_path: Path, mutation: Literal["missing", "role", "sibling"]
) -> None:
    """Rehashed sibling manifests cannot change the actual writer's direct edges."""
    store, ref, bundle = _actual_bundle(tmp_path, replay=True)
    manifest = store.get_manifest(ref)
    altered_inputs = list(manifest.inputs)
    if mutation == "missing":
        altered_inputs.pop()
    elif mutation == "role":
        altered_inputs[0] = altered_inputs[0].model_copy(update={"role": "foreign"})
    else:
        sibling = _foreign_profile(store, bundle.sources[0], mutation="producer")
        assert sibling.artifact_id == bundle.sources[0].artifact_id
        altered_inputs[0] = altered_inputs[0].model_copy(
            update={"manifest_profile_sha256": sibling.manifest_profile_sha256}
        )
    forged = store.put_bytes(
        store.get_bytes(ref),
        artifacts.ArtifactWriteOptions(
            kind=manifest.kind,
            media_type=manifest.media_type,
            schema=manifest.artifact_schema,
            canon=manifest.canon,
            inputs=altered_inputs,
            producer=manifest.producer,
            env=manifest.env,
            governance=manifest.governance,
            tenant_context=manifest.tenant_context,
            same_input_closure=manifest.same_input_closure,
            authority=manifest.authority,
            warnings=manifest.warnings,
        ),
        return_selected_profile=True,
    )
    assert forged.artifact_id == ref.artifact_id
    assert forged.manifest_profile_sha256 != ref.manifest_profile_sha256
    with pytest.raises(ValueError):
        semantic_epoch._load_selected_acquisition_mapping(
            store, forged, expected_kind="fabric.evidence_bundle"
        )
    assert semantic_epoch._load_selected_acquisition_mapping(
        store, ref, expected_kind="fabric.evidence_bundle"
    ) == bundle.model_dump(mode="json")


@pytest.mark.parametrize("direction", ["downgrade", "upgrade"])
def test_evidence_bundle_reader_rejects_schema_and_edges_rewrap(
    tmp_path: Path, direction: Literal["downgrade", "upgrade"]
) -> None:
    """Rehashing the same payload cannot erase or invent its input contract."""
    if direction == "downgrade":
        store, ref, bundle = _actual_bundle(tmp_path, replay=True)
        replacement_version = "1.0"
    else:
        store = artifacts.FileSystemCAS(tmp_path / "cas")
        bundle = build_evidence_bundle(notes=["controlled legacy fixture"])
        ref = persist_evidence_bundle(store, bundle, return_selected_profile=True)
        replacement_version = "2.0"
    manifest = store.get_manifest(ref)
    forged = store.put_bytes(
        store.get_bytes(ref),
        artifacts.ArtifactWriteOptions(
            kind=manifest.kind,
            media_type=manifest.media_type,
            schema=artifacts.SchemaInfo(name="fabric.evidence_bundle", version=replacement_version),
            canon=manifest.canon,
            inputs=[],
            producer=manifest.producer,
            env=manifest.env,
            governance=manifest.governance,
            tenant_context=manifest.tenant_context,
            same_input_closure=manifest.same_input_closure,
            authority=manifest.authority,
            warnings=manifest.warnings,
        ),
        return_selected_profile=True,
    )
    assert forged.artifact_id == ref.artifact_id
    assert forged.manifest_profile_sha256 != ref.manifest_profile_sha256
    with pytest.raises(ValueError, match="EvidenceBundle manifest input closure differs"):
        semantic_epoch._load_selected_acquisition_mapping(
            store, forged, expected_kind="fabric.evidence_bundle"
        )
    assert semantic_epoch._load_selected_acquisition_mapping(
        store, ref, expected_kind="fabric.evidence_bundle"
    ) == bundle.model_dump(mode="json")
