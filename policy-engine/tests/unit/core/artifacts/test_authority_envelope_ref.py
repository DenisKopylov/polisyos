from __future__ import annotations

import pytest

from polisyos.core.artifacts.manifest import (
    ArtifactAuthorityInfo,
    ArtifactRef,
    ProducerInfo,
    SchemaInfo,
)
from polisyos.core.artifacts.protocol import resolve_authority_envelope_ref
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
from polisyos.runtime.quality.authority import _surface_authority_payload

_ENVELOPE_KIND = "runtime_quality.evidence_authority_envelope"
_ENVELOPE_SCHEMA = "runtime_quality.evidence_authority_envelope"


def _envelope_options(
    *,
    kind: str = _ENVELOPE_KIND,
    media_type: str = "application/json",
    schema_name: str = _ENVELOPE_SCHEMA,
    schema_version: str = "1.0.0",
    producer_version: str,
) -> ArtifactWriteOptions:
    return ArtifactWriteOptions(
        kind=kind,
        media_type=media_type,
        schema=SchemaInfo(name=schema_name, version=schema_version),
        producer=ProducerInfo(
            component="polisyos.tests.authority-envelope",
            version=producer_version,
        ),
    )


def _authority_link(ref: ArtifactRef) -> ArtifactAuthorityInfo:
    return ArtifactAuthorityInfo(
        authority_envelope_ref=str(ref.artifact_id),
        authority_envelope_manifest_profile_sha256=ref.manifest_profile_sha256,
        diagnostic_event_ref="sha256:" + "2" * 64,
        manifest_ref=f"cas-manifest://{ref.artifact_id}",
        payload_sha256=ref.artifact_id.hex,
    )


def test_authority_envelope_ref_resolves_exact_profile_and_legacy_default(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "authority-envelope-views")
    payload = b'{"authority":"same bytes, selected metadata"}'
    default_ref = store.put_bytes(
        payload,
        _envelope_options(producer_version="default-view"),
    )
    selected_ref = store.put_bytes(
        payload,
        _envelope_options(producer_version="selected-view"),
    )
    assert selected_ref.artifact_id == default_ref.artifact_id
    assert selected_ref.manifest_profile_sha256 is not None

    resolved = resolve_authority_envelope_ref(store, _authority_link(selected_ref))

    assert resolved == selected_ref
    assert (
        store.get_manifest(resolved).producer
        == _envelope_options(producer_version="selected-view").producer
    )
    assert store.get_bytes(resolved) == payload
    assert store.verify(resolved).ok

    legacy_default = resolve_authority_envelope_ref(store, _authority_link(default_ref))

    assert legacy_default == default_ref
    assert legacy_default.manifest_profile_sha256 is None
    assert (
        store.get_manifest(legacy_default).producer
        == _envelope_options(producer_version="default-view").producer
    )

    invalid_contracts = (
        {"kind": "runtime_quality.not_authority_envelope"},
        {"media_type": "application/octet-stream"},
        {"schema_name": "runtime_quality.not_authority_envelope"},
        {"schema_version": "2.0.0"},
    )
    for index, contract in enumerate(invalid_contracts):
        wrong_ref = store.put_bytes(
            payload,
            _envelope_options(producer_version=f"wrong-{index}", **contract),
        )
        assert wrong_ref.manifest_profile_sha256 is not None
        with pytest.raises(ValueError, match="authority_envelope_manifest_contract_mismatch"):
            resolve_authority_envelope_ref(store, _authority_link(wrong_ref))

    mismatched_profile = _authority_link(selected_ref).model_copy(
        update={"authority_envelope_manifest_profile_sha256": "sha256:" + "f" * 64}
    )
    with pytest.raises(ValueError, match="authority_envelope_manifest_resolution_failed"):
        resolve_authority_envelope_ref(store, mismatched_profile)


def test_authority_surface_reads_the_producer_selected_envelope_view(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "authority-envelope-surface")
    envelope_bytes = b'{"authority_boundary":{"posture":"limited"}}'
    store.put_bytes(envelope_bytes, _envelope_options(producer_version="default-view"))
    selected_ref = store.put_bytes(
        envelope_bytes,
        _envelope_options(producer_version="selected-view"),
    )
    assert selected_ref.manifest_profile_sha256 is not None
    payload_ref = store.put_bytes(
        b'{"ordinary_payload":"no authority carrier"}',
        ArtifactWriteOptions(
            kind="runtime.test_payload",
            media_type="application/json",
            schema=SchemaInfo(name="runtime.test_payload", version="1.0.0"),
            authority=_authority_link(selected_ref),
        ),
    )

    class RecordingStore:
        def __init__(self) -> None:
            self.profiled_reads: list[object] = []

        def __getattr__(self, name: str) -> object:
            return getattr(store, name)

        def get_bytes(self, artifact_id: object) -> bytes:
            if getattr(artifact_id, "artifact_id", None) == selected_ref.artifact_id:
                self.profiled_reads.append(artifact_id)
            return store.get_bytes(artifact_id)

        def get_manifest(self, artifact_id: object) -> object:
            if getattr(artifact_id, "artifact_id", None) == selected_ref.artifact_id:
                self.profiled_reads.append(artifact_id)
            return store.get_manifest(artifact_id)

        def verify(self, artifact_id: object) -> object:
            if getattr(artifact_id, "artifact_id", None) == selected_ref.artifact_id:
                self.profiled_reads.append(artifact_id)
            return store.verify(artifact_id)

    recording_store = RecordingStore()
    projected = _surface_authority_payload(
        None,
        artifact_store=recording_store,
        artifact_id=payload_ref,
    )

    assert projected == {"authority_boundary": {"posture": "limited"}}
    assert selected_ref in recording_store.profiled_reads
