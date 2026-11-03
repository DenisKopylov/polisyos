"""The live EvidenceBundle verifier replays Fabric's exact writer profile."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import pytest

from polisyos.core import artifacts
from polisyos.core.contracts.fabric import EvidenceBundle, IngestionExecutionContext
from polisyos.fabric.evidence.evidence import (
    EvidencePayloadError,
    build_evidence_bundle,
    persist_evidence_bundle,
    persist_provenance_graph,
    verify_live_ingestion_evidence_profile,
)
from polisyos.fabric.provenance.core import ProvenanceCoreGraph
from polisyos.fabric.security import DataClassification


def _actual_bundle(
    tmp_path: Path, *, replay: bool = False
) -> tuple[artifacts.FileSystemCAS, artifacts.ArtifactRef, EvidenceBundle]:
    store = artifacts.FileSystemCAS(tmp_path / "cas")
    source = store.put_bytes(
        b"controlled normalized source",
        artifacts.ArtifactWriteOptions(
            kind="connector_cache.payload", media_type="application/octet-stream"
        ),
        return_selected_profile=True,
    )
    context = None
    graph_inputs = [artifacts.input_ref_from_artifact_ref(source, role="fabric.ingestion.payload")]
    if replay:
        session = store.put_json(
            {"session_id": "controlled-session"},
            artifacts.ArtifactWriteOptions(
                kind="fabric.record_session", media_type="application/json"
            ),
            return_selected_profile=True,
        )
        context = IngestionExecutionContext(
            mode="replay",
            capture_session_id="controlled-session",
            selected_record_session_ref=session,
        )
        graph_inputs.append(
            artifacts.input_ref_from_artifact_ref(session, role="fabric.ingestion.record_session")
        )
    provenance = persist_provenance_graph(
        store,
        ProvenanceCoreGraph(graph_id="fixture-live-evidence"),
        inputs=graph_inputs,
        return_selected_profile=True,
    )
    bundle = build_evidence_bundle(
        sources=[source], provenance_ref=provenance, execution_context=context
    )
    ref = persist_evidence_bundle(store, bundle, return_selected_profile=True)
    return store, ref, bundle


def _foreign_profile(
    store: artifacts.ArtifactStore,
    ref: artifacts.ArtifactRef,
    *,
    mutation: Literal["producer", "input", "environment", "warning", "schema", "canon"],
) -> artifacts.ArtifactRef:
    manifest = store.get_manifest(ref)
    values: dict[str, Any] = {
        "kind": manifest.kind,
        "media_type": manifest.media_type,
        "schema": manifest.artifact_schema,
        "canon": manifest.canon,
        "inputs": manifest.inputs,
        "producer": manifest.producer,
        "env": manifest.env,
        "governance": manifest.governance,
        "tenant_context": manifest.tenant_context,
        "same_input_closure": manifest.same_input_closure,
        "authority": manifest.authority,
        "warnings": manifest.warnings,
    }
    if mutation == "producer":
        values["producer"] = artifacts.ProducerInfo(component="foreign.writer", version="1")
    elif mutation == "input":
        values["inputs"] = [
            *manifest.inputs,
            manifest.inputs[0].model_copy(update={"role": "extra"}),
        ]
    elif mutation == "environment":
        values["env"] = artifacts.EnvInfo(python="foreign", platform="foreign", deps_lock_hash="x")
    elif mutation == "warning":
        values["warnings"] = [artifacts.WarningRecord(code="foreign", msg="foreign")]
    elif mutation == "schema":
        values["schema"] = artifacts.SchemaInfo(name="fabric.evidence_bundle", version="99.0")
    else:
        values["canon"] = manifest.canon.model_copy(update={"forbid_floats": False})
    sibling = store.put_bytes(
        store.get_bytes(ref), artifacts.ArtifactWriteOptions(**values), return_selected_profile=True
    )
    assert sibling.artifact_id == ref.artifact_id
    assert sibling.manifest_profile_sha256 != ref.manifest_profile_sha256
    return sibling


@pytest.mark.parametrize("replay", [False, True])
def test_owner_writer_profile_reopens_live_and_replay_inputs(tmp_path: Path, replay: bool) -> None:
    store, ref, bundle = _actual_bundle(tmp_path, replay=replay)
    manifest = store.get_manifest(ref)
    assert manifest.artifact_schema == artifacts.SchemaInfo(
        name="fabric.evidence_bundle", version="2.0"
    )
    assert [edge.role for edge in manifest.inputs] == (
        [
            "fabric.ingestion.payload",
            "fabric.ingestion.record_session",
            "fabric.ingestion.provenance",
        ]
        if replay
        else ["fabric.ingestion.payload", "fabric.ingestion.provenance"]
    )
    verify_live_ingestion_evidence_profile(store, ref, bundle)


@pytest.mark.parametrize(
    "mutation", ["producer", "input", "environment", "warning", "schema", "canon"]
)
def test_same_bytes_foreign_profile_is_refused(
    tmp_path: Path,
    mutation: Literal["producer", "input", "environment", "warning", "schema", "canon"],
) -> None:
    store, ref, bundle = _actual_bundle(tmp_path, replay=True)
    foreign = _foreign_profile(store, ref, mutation=mutation)
    with pytest.raises(EvidencePayloadError, match="live_evidence_writer_profile_mismatch"):
        verify_live_ingestion_evidence_profile(store, foreign, bundle)
    verify_live_ingestion_evidence_profile(store, ref, bundle)


def test_nondefault_governance_is_not_treated_as_the_live_writer(tmp_path: Path) -> None:
    store, ref, bundle = _actual_bundle(tmp_path)
    other = persist_evidence_bundle(
        store,
        bundle,
        return_selected_profile=True,
        classification=DataClassification.INTERNAL,
        encrypted_at_rest=True,
    )
    assert other.artifact_id == ref.artifact_id
    assert other.manifest_profile_sha256 != ref.manifest_profile_sha256
    with pytest.raises(EvidencePayloadError, match="live_evidence_writer_profile_mismatch"):
        verify_live_ingestion_evidence_profile(store, other, bundle)
    verify_live_ingestion_evidence_profile(store, ref, bundle)


def test_writer_profile_uses_the_same_verified_selected_manifest(tmp_path: Path) -> None:
    store, ref, bundle = _actual_bundle(tmp_path)
    foreign = _foreign_profile(store, ref, mutation="producer")
    foreign_manifest = store.get_manifest(foreign)
    actual_manifest = store.get_manifest(ref)

    class SwitchingReader:
        def __init__(self) -> None:
            self.selected_reads = 0

        def has(self, selected: artifacts.ArtifactID | artifacts.ArtifactRef) -> bool:
            return store.has(selected)

        def get_manifest(
            self, selected: artifacts.ArtifactID | artifacts.ArtifactRef
        ) -> artifacts.ArtifactManifest:
            if selected == foreign:
                self.selected_reads += 1
                return foreign_manifest if self.selected_reads == 1 else actual_manifest
            return store.get_manifest(selected)

        def get_bytes(self, selected: artifacts.ArtifactID | artifacts.ArtifactRef) -> bytes:
            return store.get_bytes(selected)

    reader = SwitchingReader()
    with pytest.raises(EvidencePayloadError, match="live_evidence_writer_profile_mismatch"):
        verify_live_ingestion_evidence_profile(reader, foreign, bundle)
    assert reader.selected_reads == 1


@pytest.mark.parametrize("mutation", ["producer", "input"])
def test_bundle_rejects_same_bytes_foreign_provenance_writer_profile(
    tmp_path: Path, mutation: Literal["producer", "input"]
) -> None:
    store, ref, bundle = _actual_bundle(tmp_path, replay=True)
    provenance = bundle.provenance_ref
    assert provenance is not None
    selected = artifacts.ArtifactRef(
        artifact_id=artifacts.ArtifactID.model_validate(provenance.artifact_id),
        kind="fabric.provenance_graph",
        media_type="application/json",
        manifest_profile_sha256=provenance.manifest_profile_sha256,
    )
    foreign = _foreign_profile(store, selected, mutation=mutation)
    forged_bundle = bundle.model_copy(
        update={
            "provenance_ref": provenance.model_copy(
                update={"manifest_profile_sha256": foreign.manifest_profile_sha256}
            )
        }
    )
    forged_ref = persist_evidence_bundle(store, forged_bundle, return_selected_profile=True)
    with pytest.raises(
        EvidencePayloadError, match="live_evidence_provenance_writer_profile_mismatch"
    ):
        verify_live_ingestion_evidence_profile(store, forged_ref, forged_bundle)
    verify_live_ingestion_evidence_profile(store, ref, bundle)


@pytest.mark.parametrize("field", ["graph_id", "stable_id"])
def test_bundle_rejects_falsified_provenance_identity(tmp_path: Path, field: str) -> None:
    store, ref, bundle = _actual_bundle(tmp_path)
    provenance = bundle.provenance_ref
    assert provenance is not None
    forged_bundle = bundle.model_copy(
        update={"provenance_ref": provenance.model_copy(update={field: "foreign"})}
    )
    forged_ref = persist_evidence_bundle(store, forged_bundle, return_selected_profile=True)
    with pytest.raises(EvidencePayloadError, match="live_evidence_provenance_payload_mismatch"):
        verify_live_ingestion_evidence_profile(store, forged_ref, forged_bundle)
    verify_live_ingestion_evidence_profile(store, ref, bundle)


def test_unknown_unselected_missing_and_changed_inputs_fail_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store, ref, bundle = _actual_bundle(tmp_path, replay=True)
    verify_live_ingestion_evidence_profile(store, ref, bundle)
    with pytest.raises(EvidencePayloadError, match="live_evidence_profile_unselected_or_invalid"):
        verify_live_ingestion_evidence_profile(
            store, ref.model_copy(update={"manifest_profile_sha256": None}), bundle
        )
    with pytest.raises(EvidencePayloadError, match="live_evidence_input_unavailable"):
        verify_live_ingestion_evidence_profile(
            store, ref.model_copy(update={"manifest_profile_sha256": "sha256:" + "0" * 64}), bundle
        )
    unselected_source = bundle.sources[0].model_copy(update={"manifest_profile_sha256": None})
    with pytest.raises(EvidencePayloadError, match="live_evidence_input_profile_unselected"):
        verify_live_ingestion_evidence_profile(
            store, ref, bundle.model_copy(update={"sources": [unselected_source]})
        )
    with pytest.raises(EvidencePayloadError, match="live_evidence_selected_inputs_missing"):
        verify_live_ingestion_evidence_profile(
            store, ref, bundle.model_copy(update={"provenance_ref": None})
        )
    with pytest.raises(EvidencePayloadError, match="live_evidence_bundle_payload_mismatch"):
        verify_live_ingestion_evidence_profile(
            store, ref, bundle.model_copy(update={"notes": ["changed"]})
        )

    assert bundle.execution_context is not None
    assert bundle.execution_context.selected_record_session_ref is not None
    assert bundle.provenance_ref is not None
    provenance = artifacts.ArtifactRef(
        artifact_id=artifacts.ArtifactID.model_validate(bundle.provenance_ref.artifact_id),
        kind="fabric.provenance_graph",
        media_type="application/json",
        manifest_profile_sha256=bundle.provenance_ref.manifest_profile_sha256,
    )
    original_get_bytes = store.get_bytes
    for missing_ref in (
        bundle.sources[0],
        bundle.execution_context.selected_record_session_ref,
        provenance,
    ):

        def get_bytes(
            selected: object,
            *,
            missing_id: str = str(missing_ref.artifact_id),
        ) -> bytes:
            if str(getattr(selected, "artifact_id", selected)) == missing_id:
                raise FileNotFoundError("controlled selected-input removal")
            return original_get_bytes(selected)

        with monkeypatch.context() as scoped:
            scoped.setattr(store, "get_bytes", get_bytes)
            with pytest.raises(EvidencePayloadError, match="live_evidence_input_unavailable"):
                verify_live_ingestion_evidence_profile(store, ref, bundle)
