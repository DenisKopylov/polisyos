"""Persist exact blob, manifest, and detached-signature evidence graphs.

The ordinary :class:`ArtifactStore` contract intentionally exposes parsed
manifests only.  Anchor verification needs the bytes that were actually
signed, so this adapter accepts only the filesystem CAS exact-byte surface and
never reconstructs manifest or sidecar bytes from parsed objects.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from polisyos.core import canon as core_canon
from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactRef, CanonInfo, SchemaInfo
from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
from polisyos.core.contracts import chronology as contract

if TYPE_CHECKING:
    from pathlib import Path

    from polisyos.core.artifacts.signing import ArtifactSigner, DetachedSignature


_MEDIA_TYPE = "application/octet-stream"
_SIGNATURE_KIND = "core.chronology.detached_signature_bytes"
_RECORD_KIND = "core.chronology.signed_artifact_evidence_record"
_RECORD_DOMAIN = b"polisyos.signed-artifact-evidence-record.v1\0"


@runtime_checkable
class _ExactFileSystemCAS(Protocol):
    """Minimum exact-byte CAS surface required by this adapter."""

    def put_bytes(self, data: bytes, opts: ArtifactWriteOptions) -> ArtifactRef: ...

    def get_bytes(self, artifact_id: ArtifactID | str) -> bytes: ...

    def get_manifest_bytes(self, artifact_id: ArtifactID | str) -> bytes: ...

    def put_signature(
        self, artifact_id: ArtifactID | str, signature: DetachedSignature
    ) -> Path: ...

    def get_paths(self, artifact_id: ArtifactID) -> tuple[Path, Path]: ...

    def verify(self, artifact_id: ArtifactID | str) -> object: ...


def supports_signed_evidence_repository(store: object) -> bool:
    """Return whether ``store`` exposes every required exact-byte operation.

    This is deliberately structural only at the adapter boundary.  Every read
    then verifies the content identities, including the raw sidecar path.  A
    generic store with a parsed-manifest API cannot issue anchor evidence.
    """

    required = (
        "put_bytes",
        "get_bytes",
        "get_manifest_bytes",
        "put_signature",
        "get_paths",
        "verify",
    )
    return all(callable(getattr(store, name, None)) for name in required)


def _raw_hash(payload: bytes) -> contract.Digest:
    return f"sha256:{core_canon.content_hash(payload)}"


def _record_bytes(record: contract.SignedArtifactEvidenceRecord) -> bytes:
    canonical = contract._canonical_raw_bytes(contract._raw_model_mapping(record))
    return contract._frame_record(canonical)


def _record_content_hash(payload: bytes) -> contract.Digest:
    return contract._sha256_digest(_RECORD_DOMAIN, payload)


def _record_options(*, inputs: list[contract.InputRef]) -> ArtifactWriteOptions:
    return ArtifactWriteOptions(
        kind=_RECORD_KIND,
        media_type=_MEDIA_TYPE,
        schema=SchemaInfo(
            name="polisyos.chronology.SignedArtifactEvidenceRecord",
            version="1",
        ),
        canon=CanonInfo.from_spec(contract.CHRONOLOGY_CANON_SPEC),
        inputs=inputs,
    )


def _signature_options(*, artifact_ref: ArtifactRef) -> ArtifactWriteOptions:
    return ArtifactWriteOptions(
        kind=_SIGNATURE_KIND,
        media_type="application/json",
        schema=SchemaInfo(name="polisyos.cas.DetachedSignature", version="1"),
        inputs=[
            contract.InputRef(
                artifact_id=artifact_ref.artifact_id,
                role="signed_artifact",
            )
        ],
    )


def _one_framed_mapping(payload: bytes) -> dict[str, object]:
    records = contract._split_framed_records(payload)
    if len(records) != 1:
        raise ValueError("signed evidence record must contain exactly one frame")
    decoded = json.loads(records[0])
    if not isinstance(decoded, dict):
        raise ValueError("signed evidence record must decode to a mapping")
    if contract._canonical_raw_bytes(decoded) != records[0]:
        raise ValueError("signed evidence record bytes are not canonical")
    return decoded


@dataclass(frozen=True, slots=True)
class FileSystemSignedArtifactEvidenceRepository:
    """Issue and reload exact signed-evidence records through one filesystem CAS."""

    store: _ExactFileSystemCAS

    def __post_init__(self) -> None:
        if not supports_signed_evidence_repository(self.store):
            raise TypeError("exact manifest/signature byte ports are required")

    def _sidecar_bytes(self, artifact_id: ArtifactID) -> bytes:
        blob_path, _ = self.store.get_paths(artifact_id)
        signature_path = blob_path.with_suffix(".sig")
        if not signature_path.is_file():
            raise FileNotFoundError(f"detached signature absent for {artifact_id}")
        return signature_path.read_bytes()

    def persist_signed(
        self,
        *,
        blob_bytes: bytes,
        write_options: ArtifactWriteOptions,
        signer: ArtifactSigner,
        signing_profile_ref: ArtifactRef,
        signer_provenance_ref: ArtifactRef,
    ) -> contract.PersistedSignedArtifactEvidence:
        """Persist a blob and an exact, non-self-referential evidence record."""

        artifact_ref = self.store.put_bytes(blob_bytes, write_options)
        manifest_bytes = self.store.get_manifest_bytes(artifact_ref.artifact_id)
        signature = signer.sign(
            artifact_ref.artifact_id,
            blob_bytes,
            manifest_bytes,
            signer_identity=None,
        )
        self.store.put_signature(artifact_ref.artifact_id, signature)
        signature_bytes = self._sidecar_bytes(artifact_ref.artifact_id)
        signature_ref = self.store.put_bytes(
            signature_bytes,
            _signature_options(artifact_ref=artifact_ref),
        )
        record = contract.SignedArtifactEvidenceRecord(
            artifact_ref=artifact_ref,
            raw_blob_bytes_hash=_raw_hash(blob_bytes),
            exact_manifest_raw_bytes_hash=_raw_hash(manifest_bytes),
            signature_artifact_ref=signature_ref,
            signature_raw_bytes_hash=_raw_hash(signature_bytes),
            signing_profile_ref=signing_profile_ref,
            signer_provenance_ref=signer_provenance_ref,
        )
        payload = _record_bytes(record)
        record_ref = self.store.put_bytes(
            payload,
            _record_options(
                inputs=[
                    contract.InputRef(
                        artifact_id=artifact_ref.artifact_id,
                        role="signed_artifact",
                    ),
                    contract.InputRef(
                        artifact_id=signature_ref.artifact_id,
                        role="exact_signature_bytes",
                    ),
                ]
            ),
        )
        return contract.PersistedSignedArtifactEvidence(
            evidence_record_ref=record_ref,
            evidence_record_content_hash=_record_content_hash(payload),
            record_bytes=payload,
        )

    def read_exact(self, *, evidence_record_ref: ArtifactRef) -> contract.SignedArtifactEvidence:
        """Reload and independently reconcile every raw identity in a record."""

        report = self.store.verify(evidence_record_ref.artifact_id)
        if not bool(getattr(report, "ok", False)):
            raise ValueError("signed evidence record fails CAS verification")
        record_bytes = self.store.get_bytes(evidence_record_ref.artifact_id)
        if str(evidence_record_ref.artifact_id) != _raw_hash(record_bytes):
            raise ValueError("signed evidence record CAS identity mismatch")
        record = contract.SignedArtifactEvidenceRecord.model_validate(
            _one_framed_mapping(record_bytes)
        )
        blob_bytes = self.store.get_bytes(record.artifact_ref.artifact_id)
        manifest_bytes = self.store.get_manifest_bytes(record.artifact_ref.artifact_id)
        signature_bytes = self.store.get_bytes(record.signature_artifact_ref.artifact_id)
        if self._sidecar_bytes(record.artifact_ref.artifact_id) != signature_bytes:
            raise ValueError("detached signature sidecar differs from retained exact bytes")
        checks = (
            (record.raw_blob_bytes_hash, _raw_hash(blob_bytes), "blob"),
            (
                record.exact_manifest_raw_bytes_hash,
                _raw_hash(manifest_bytes),
                "manifest",
            ),
            (record.signature_raw_bytes_hash, _raw_hash(signature_bytes), "signature"),
            (
                str(record.signature_artifact_ref.artifact_id),
                _raw_hash(signature_bytes),
                "signature artifact",
            ),
        )
        for expected, observed, role in checks:
            if expected != observed:
                raise ValueError(f"{role} exact-byte identity mismatch")
        return contract.SignedArtifactEvidence(
            persisted=contract.PersistedSignedArtifactEvidence(
                evidence_record_ref=evidence_record_ref,
                evidence_record_content_hash=_record_content_hash(record_bytes),
                record_bytes=record_bytes,
            ),
            blob_bytes=blob_bytes,
            exact_manifest_bytes=manifest_bytes,
            detached_signature_bytes=signature_bytes,
        )

    def read_raw(self, *, artifact_ref: ArtifactRef) -> bytes:
        """Return exact CAS bytes only after the real store verifies identity."""

        report = self.store.verify(artifact_ref.artifact_id)
        if not bool(getattr(report, "ok", False)):
            raise ValueError("signed-evidence raw artifact fails CAS verification")
        payload = self.store.get_bytes(artifact_ref.artifact_id)
        if str(artifact_ref.artifact_id) != _raw_hash(payload):
            raise ValueError("signed-evidence raw artifact identity mismatch")
        return payload


__all__ = [
    "FileSystemSignedArtifactEvidenceRepository",
    "supports_signed_evidence_repository",
]
