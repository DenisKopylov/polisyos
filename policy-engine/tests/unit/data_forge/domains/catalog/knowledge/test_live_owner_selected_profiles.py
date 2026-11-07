"""Real Fabric live carriers must retain their exact owner-selected profiles."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Literal

import pytest

from polisyos.common.async_tools import run_coro_sync
from polisyos.core import artifacts, contracts
from polisyos.data_forge.domains.catalog.knowledge.acquisition_authority import (
    AcquisitionAuthorityError,
)
from polisyos.fabric.data_plane.orchestrator import _build_snapshot_from_evidence_async
from polisyos.fabric.evidence import persist_evidence_bundle
from polisyos.runtime.quality.acquisition_executor import content_sha256
from tests._helpers.lane01_wdi_profiles import GDP_PROFILE
from tests.unit.runtime.quality.test_lane01_candidate_provenance import _fixture

ViewRole = Literal["snapshot", "bundle", "normalized"]
Mutation = Literal["unselected", "sibling"]


class _ReadOnlyArtifactReader:
    """Expose only read methods; do not inherit a writer or integrity check."""

    def __init__(self, store: artifacts.ArtifactStore) -> None:
        self._store = store

    def has(self, ref: artifacts.ArtifactID | artifacts.ArtifactRef) -> bool:
        return self._store.has(ref)

    def get_bytes(self, ref: artifacts.ArtifactID | artifacts.ArtifactRef) -> bytes:
        return self._store.get_bytes(ref)

    def get_manifest(
        self, ref: artifacts.ArtifactID | artifacts.ArtifactRef
    ) -> artifacts.ArtifactManifest:
        return self._store.get_manifest(ref)


class _VerifiableReadOnlyArtifactReader(_ReadOnlyArtifactReader):
    def verify(
        self, ref: artifacts.ArtifactID | artifacts.ArtifactRef
    ) -> artifacts.VerificationReport:
        return self._store.verify(ref)


def _foreign_sibling(
    store: artifacts.ArtifactStore,
    ref: artifacts.ArtifactRef,
) -> artifacts.ArtifactRef:
    """Create identical bytes under an otherwise matching, foreign-producer view."""
    manifest = store.get_manifest(ref)
    payload = store.get_bytes(ref)
    sibling = store.put_bytes(
        payload,
        artifacts.ArtifactWriteOptions(
            kind=manifest.kind,
            media_type=manifest.media_type,
            schema=manifest.artifact_schema,
            producer=artifacts.ProducerInfo(component="fixture.foreign-producer", version="1"),
            env=manifest.env,
            inputs=manifest.inputs,
            canon=manifest.canon,
            governance=manifest.governance,
            tenant_context=manifest.tenant_context,
            same_input_closure=manifest.same_input_closure,
            authority=manifest.authority,
            warnings=manifest.warnings,
        ),
        return_selected_profile=True,
    )
    assert sibling.artifact_id == ref.artifact_id
    assert sibling.manifest_profile_sha256 is not None
    assert sibling.manifest_profile_sha256 != ref.manifest_profile_sha256
    assert store.get_bytes(sibling) == payload
    assert store.verify(sibling).ok
    return sibling


def _mutated_ref(
    store: artifacts.ArtifactStore,
    ref: artifacts.ArtifactRef,
    mutation: Mutation,
) -> artifacts.ArtifactRef:
    assert ref.manifest_profile_sha256 is not None
    if mutation == "unselected":
        return ref.model_copy(update={"manifest_profile_sha256": None})
    return _foreign_sibling(store, ref)


def _rebuild_snapshot(
    case: SimpleNamespace,
    evidence_ref: contracts.EvidenceBundleRef,
) -> contracts.DataSnapshotRef:
    """Use the actual Fabric snapshot producer after rebinding its bundle."""
    snapshot_ref = run_coro_sync(
        _build_snapshot_from_evidence_async(
            store=artifacts.ensure_async_artifact_store(case.store),
            evidence_ref=evidence_ref,
            datasets_fetched=1,
            source=f"acquisition:{case.entry.target_variable}",
        )
    )
    assert snapshot_ref is not None
    return snapshot_ref


def _forged_proof(case: SimpleNamespace, role: ViewRole, mutation: Mutation):
    evidence = case.evidence
    snapshot = artifacts.validate_core_model_json_artifact(
        contracts.DataSnapshot, case.store, evidence.data_snapshot_ref
    )
    bundle = contracts.EvidenceBundle.model_validate(
        artifacts.load_core_json_artifact(case.store, evidence.evidence_bundle_ref)
    )
    assert snapshot.evidence_ref == evidence.evidence_bundle_ref
    assert bundle.sources == [snapshot.data_ref]

    if role == "snapshot":
        forged_snapshot = _mutated_ref(case.store, evidence.data_snapshot_ref, mutation)
        updates = {
            "data_snapshot_ref": contracts.DataSnapshotRef.model_validate(
                forged_snapshot.model_dump(mode="python")
            )
        }
    else:
        if role == "bundle":
            forged_bundle = _mutated_ref(case.store, evidence.evidence_bundle_ref, mutation)
            bundle_ref = contracts.EvidenceBundleRef.model_validate(
                forged_bundle.model_dump(mode="python")
            )
        else:
            forged_data = _mutated_ref(case.store, snapshot.data_ref, mutation)
            mutated_bundle = bundle.model_copy(update={"sources": [forged_data]})
            bundle_ref = persist_evidence_bundle(
                case.store, mutated_bundle, return_selected_profile=True
            )
        snapshot_ref = _rebuild_snapshot(case, bundle_ref)
        updates = {"data_snapshot_ref": snapshot_ref, "evidence_bundle_ref": bundle_ref}

    forged = evidence.model_copy(update=updates)
    forged = forged.model_copy(update={"content_sha256": content_sha256(forged.identity_payload())})
    return type(evidence).model_validate(forged.model_dump(mode="json"))


@pytest.mark.parametrize("role", ["snapshot", "bundle", "normalized"])
@pytest.mark.parametrize("mutation", ["unselected", "sibling"])
def test_real_live_owner_rejects_unselected_or_foreign_carrier_profile(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    role: ViewRole,
    mutation: Mutation,
) -> None:
    """An internally rehashed proof cannot promote an alternate carrier view."""
    case = _fixture(tmp_path, monkeypatch, GDP_PROFILE)
    try:
        before = case.authority.resolve_live_source_execution(
            case.entry.entry_id, case.evidence, case.store
        )
        assert before.row_count == 1
        forged = _forged_proof(case, role, mutation)
        with pytest.raises(
            AcquisitionAuthorityError,
            match=rf"live_{role}_profile_(?:required|drift)",
        ):
            case.authority.resolve_live_source_execution(case.entry.entry_id, forged, case.store)
        after = case.authority.resolve_live_source_execution(
            case.entry.entry_id, case.evidence, case.store
        )
        assert after.row_count == before.row_count
        assert after.data.equals(before.data)
    finally:
        case.overlay.close()


def test_live_owner_requires_verification_without_requiring_a_writable_store(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A read-only verifier works; a reader without integrity checks is refused."""
    case = _fixture(tmp_path, monkeypatch, GDP_PROFILE)
    try:
        reader = _VerifiableReadOnlyArtifactReader(case.store)
        assert not hasattr(reader, "put_bytes") and not hasattr(reader, "root")
        result = case.authority.resolve_live_source_execution(
            case.entry.entry_id, case.evidence, reader
        )
        assert result.row_count == 1
        with pytest.raises(
            AcquisitionAuthorityError, match="live_artifact_verification_unavailable"
        ):
            case.authority.resolve_live_source_execution(
                case.entry.entry_id, case.evidence, _ReadOnlyArtifactReader(case.store)
            )
    finally:
        case.overlay.close()
