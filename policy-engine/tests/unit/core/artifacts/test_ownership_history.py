"""Behavioral witnesses for versioned artifact-ownership history."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.ownership import ArtifactOwnershipIndex
from polisyos.core.canon.canon_json import CanonSpec, to_canonical_bytes

_V1_INDEX_SCHEMA = "policyos.artifact_ownership_index.v1"
_V1_SIGNATURE_SCHEMA = "policyos.artifact_ownership_index_signature.v1"
_V2_INDEX_SCHEMA = "policyos.artifact_ownership_index.v2"
_V2_SIGNATURE_SCHEMA = "policyos.artifact_ownership_index_signature.v2"
_MODE = "shared_immutable_cas"


def _canonical_sha256(payload: dict[str, Any]) -> str:
    canonical = to_canonical_bytes(payload, CanonSpec(forbid_floats=False))
    return "sha256:" + hashlib.sha256(canonical).hexdigest()


def _write_signed_v1_index(
    root: Path,
    artifact_id: ArtifactID,
) -> tuple[ArtifactOwnershipIndex, dict[str, Any], bytes, bytes]:
    payload: dict[str, Any] = {
        "schema_version": _V1_INDEX_SCHEMA,
        "mode": _MODE,
        "artifacts": {
            str(artifact_id): [
                {
                    "tenant_id": "tenant-a",
                    "cell_id": "cell-a",
                    "claimed_at": "2024-01-01T00:00:00+00:00",
                    "writer": "historical-writer",
                }
            ]
        },
    }
    index = ArtifactOwnershipIndex(root)
    index.path.parent.mkdir(parents=True)
    index_bytes = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode()
    index.path.write_bytes(index_bytes)

    statement: dict[str, Any] = {
        "schema_version": _V1_SIGNATURE_SCHEMA,
        "mode": _MODE,
        "index_sha256": _canonical_sha256(payload),
        "index_schema_version": _V1_INDEX_SCHEMA,
        "algorithm": "sha256-local-integrity",
        "key_id": "local-cas-ownership-index",
    }
    signature_payload = {
        **statement,
        "signature": _canonical_sha256(statement),
    }
    signature_bytes = (
        json.dumps(signature_payload, indent=2, sort_keys=True) + "\n"
    ).encode()
    index.signature_path.write_bytes(signature_bytes)
    return index, payload, index_bytes, signature_bytes


def test_evidence_read_preserves_valid_v1_index_and_signature_bytes(tmp_path: Path) -> None:
    artifact_id = ArtifactID.from_sha256_hex("1" * 64)
    index, payload, index_bytes, signature_bytes = _write_signed_v1_index(
        tmp_path,
        artifact_id,
    )

    evidence = index.evidence(tenant_id="tenant-a", cell_id="cell-a")

    assert index.path.read_bytes() == index_bytes
    assert index.signature_path.read_bytes() == signature_bytes
    signature = json.loads(signature_bytes)
    assert evidence["schema_version"] == _V1_INDEX_SCHEMA
    assert evidence["ownership_index_digest"] == _canonical_sha256(payload)
    assert evidence["ownership_index_digest"] == signature["index_sha256"]
    assert evidence["ownership_index_signature_digest"] == _canonical_sha256(signature)
    assert evidence["tenant_artifact_count"] == 1


def test_explicit_blob_reader_admission_migrates_v1_with_a_v2_signature(
    tmp_path: Path,
) -> None:
    artifact_id = ArtifactID.from_sha256_hex("2" * 64)
    reader_id = ArtifactID.from_sha256_hex("3" * 64)
    index, original_payload, _index_bytes, _signature_bytes = _write_signed_v1_index(
        tmp_path,
        artifact_id,
    )

    index.record_blob_reader(
        reader_id,
        tenant_id="tenant-b",
        cell_id="cell-b",
        writer="explicit-reader-admission",
    )

    migrated = json.loads(index.path.read_bytes())
    signature = json.loads(index.signature_path.read_bytes())
    signature_statement = {key: value for key, value in signature.items() if key != "signature"}
    assert migrated["schema_version"] == _V2_INDEX_SCHEMA
    assert migrated["artifacts"] == original_payload["artifacts"]
    assert migrated["blob_readers"][str(reader_id)][0]["tenant_id"] == "tenant-b"
    assert migrated["blob_readers"][str(reader_id)][0]["cell_id"] == "cell-b"
    assert migrated["blob_readers"][str(reader_id)][0]["writer"] == "explicit-reader-admission"
    assert signature["schema_version"] == _V2_SIGNATURE_SCHEMA
    assert signature["index_schema_version"] == _V2_INDEX_SCHEMA
    assert signature["index_sha256"] == _canonical_sha256(migrated)
    assert signature["signature"] == _canonical_sha256(signature_statement)
    assert index.is_blob_readable_by(reader_id, tenant_id="tenant-b", cell_id="cell-b")
    assert not index.is_owned_by(reader_id, tenant_id="tenant-b", cell_id="cell-b")

    migrated_bytes = index.path.read_bytes()
    signature_bytes = index.signature_path.read_bytes()
    evidence = index.evidence(tenant_id="tenant-b", cell_id="cell-b")
    assert evidence["schema_version"] == _V2_INDEX_SCHEMA
    assert evidence["ownership_index_digest"] == signature["index_sha256"]
    assert index.path.read_bytes() == migrated_bytes
    assert index.signature_path.read_bytes() == signature_bytes


def test_evidence_read_fails_closed_on_tampered_v1_without_rewriting_it(
    tmp_path: Path,
) -> None:
    artifact_id = ArtifactID.from_sha256_hex("4" * 64)
    index, _payload, _index_bytes, signature_bytes = _write_signed_v1_index(
        tmp_path,
        artifact_id,
    )
    tampered = json.loads(index.path.read_bytes())
    tampered["artifacts"][str(artifact_id)][0]["tenant_id"] = "tenant-intruder"
    tampered_bytes = (json.dumps(tampered, indent=2, sort_keys=True) + "\n").encode()
    index.path.write_bytes(tampered_bytes)

    with pytest.raises(ValueError, match="ownership_index_signature_invalid"):
        index.evidence()

    assert index.path.read_bytes() == tampered_bytes
    assert index.signature_path.read_bytes() == signature_bytes
