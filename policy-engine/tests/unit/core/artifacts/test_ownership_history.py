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


def _rewrite_signed_v1_index(index: ArtifactOwnershipIndex, payload: dict[str, Any]) -> None:
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
    index.signature_path.write_bytes(
        (json.dumps(signature_payload, indent=2, sort_keys=True) + "\n").encode()
    )


def _write_signed_v2_index(
    root: Path,
    payload: dict[str, Any],
) -> tuple[ArtifactOwnershipIndex, bytes, bytes]:
    index = ArtifactOwnershipIndex(root)
    index.path.parent.mkdir(parents=True)
    payload = {
        "schema_version": _V2_INDEX_SCHEMA,
        "mode": _MODE,
        "artifacts": {},
        "blob_readers": {},
        **payload,
    }
    index_bytes = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode()
    index.path.write_bytes(index_bytes)
    statement: dict[str, Any] = {
        "schema_version": _V2_SIGNATURE_SCHEMA,
        "mode": _MODE,
        "index_sha256": _canonical_sha256(payload),
        "index_schema_version": _V2_INDEX_SCHEMA,
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
    return index, index_bytes, signature_bytes


def _write_signed_index_documents(
    root: Path,
    raw_payload: dict[str, Any],
    signed_projection: dict[str, Any],
) -> tuple[ArtifactOwnershipIndex, bytes, bytes]:
    index = ArtifactOwnershipIndex(root)
    index.path.parent.mkdir(parents=True)
    index_bytes = (json.dumps(raw_payload, indent=2, sort_keys=True) + "\n").encode()
    index.path.write_bytes(index_bytes)
    schema_version = str(signed_projection["schema_version"])
    signature_schema = (
        _V1_SIGNATURE_SCHEMA if schema_version == _V1_INDEX_SCHEMA else _V2_SIGNATURE_SCHEMA
    )
    statement: dict[str, Any] = {
        "schema_version": signature_schema,
        "mode": _MODE,
        "index_sha256": _canonical_sha256(signed_projection),
        "index_schema_version": schema_version,
        "algorithm": "sha256-local-integrity",
        "key_id": "local-cas-ownership-index",
    }
    signature_payload = {**statement, "signature": _canonical_sha256(statement)}
    signature_bytes = (
        json.dumps(signature_payload, indent=2, sort_keys=True) + "\n"
    ).encode()
    index.signature_path.write_bytes(signature_bytes)
    return index, index_bytes, signature_bytes


@pytest.mark.parametrize("missing_field", ["artifacts", "mode"])
def test_v2_missing_raw_required_fields_are_rejected_even_when_defaults_are_signed(
    tmp_path: Path,
    missing_field: str,
) -> None:
    raw_payload: dict[str, Any] = {
        "schema_version": _V2_INDEX_SCHEMA,
        "mode": _MODE,
        "artifacts": {},
        "blob_readers": {},
    }
    raw_payload.pop(missing_field)
    signed_projection = {
        "schema_version": _V2_INDEX_SCHEMA,
        "mode": _MODE,
        "artifacts": {},
        "blob_readers": {},
    }
    index, index_bytes, signature_bytes = _write_signed_index_documents(
        tmp_path,
        raw_payload,
        signed_projection,
    )

    with pytest.raises(ValueError, match="ownership_index_signature_invalid"):
        index.has_any_tenant_claim(ArtifactID.from_sha256_hex("a" * 64))

    assert index.path.read_bytes() == index_bytes
    assert index.signature_path.read_bytes() == signature_bytes


def test_v1_historical_raw_defaults_remain_accepted_without_rewriting(
    tmp_path: Path,
) -> None:
    raw_payload: dict[str, Any] = {}
    historical_projection = {
        "schema_version": _V1_INDEX_SCHEMA,
        "mode": _MODE,
        "artifacts": {},
    }
    index, index_bytes, signature_bytes = _write_signed_index_documents(
        tmp_path,
        raw_payload,
        historical_projection,
    )

    assert not index.has_any_tenant_claim(ArtifactID.from_sha256_hex("b" * 64))
    assert index.path.read_bytes() == index_bytes
    assert index.signature_path.read_bytes() == signature_bytes


def test_any_claim_query_preserves_signed_v1_index_bytes(tmp_path: Path) -> None:
    claimed_id = ArtifactID.from_sha256_hex("5" * 64)
    unclaimed_id = ArtifactID.from_sha256_hex("6" * 64)
    index, _payload, index_bytes, signature_bytes = _write_signed_v1_index(
        tmp_path,
        claimed_id,
    )

    assert index.has_any_tenant_claim(claimed_id)
    assert not index.has_any_tenant_claim(unclaimed_id)

    assert index.path.read_bytes() == index_bytes
    assert index.signature_path.read_bytes() == signature_bytes


@pytest.mark.parametrize("mutation", ["noncanonical-id", "unknown-row-field"])
def test_any_claim_query_rejects_malformed_signed_v1_rows(
    tmp_path: Path,
    mutation: str,
) -> None:
    claimed_id = ArtifactID.from_sha256_hex("e" * 64)
    other_id = ArtifactID.from_sha256_hex("f" * 64)
    index, payload, _index_bytes, _signature_bytes = _write_signed_v1_index(
        tmp_path,
        claimed_id,
    )
    if mutation == "noncanonical-id":
        payload["artifacts"] = {
            "sha256:" + "E" * 64: payload["artifacts"][str(claimed_id)]
        }
    else:
        payload["artifacts"][str(claimed_id)][0]["unrecognized"] = "claimed"
    _rewrite_signed_v1_index(index, payload)

    with pytest.raises(ValueError, match="ownership_index_signature_invalid"):
        index.has_any_tenant_claim(other_id)


def test_any_claim_query_covers_v2_owner_view_and_blob_reader_rows_without_rewriting(
    tmp_path: Path,
) -> None:
    owner_id = ArtifactID.from_sha256_hex("7" * 64)
    view_id = ArtifactID.from_sha256_hex("8" * 64)
    blob_reader_id = ArtifactID.from_sha256_hex("9" * 64)
    unclaimed_id = ArtifactID.from_sha256_hex("a" * 64)
    index, index_bytes, signature_bytes = _write_signed_v2_index(
        tmp_path,
        {
            "artifacts": {
                str(owner_id): [
                    {
                        "tenant_id": "tenant-a",
                        "cell_id": "cell-a",
                        "claimed_at": "2024-01-01T00:00:00+00:00",
                    }
                ],
                str(view_id): [
                    {
                        "tenant_id": "tenant-b",
                        "manifest_profile_sha256": "sha256:" + "b" * 64,
                        "claimed_at": "2024-01-01T00:00:00+00:00",
                    }
                ],
            },
            "blob_readers": {
                str(blob_reader_id): [
                    {
                        "tenant_id": "tenant-c",
                        "cell_id": "cell-c",
                        "claimed_at": "2024-01-01T00:00:00+00:00",
                    }
                ]
            },
        },
    )

    assert index.has_any_tenant_claim(owner_id)
    assert index.has_any_tenant_claim(view_id)
    assert index.has_any_tenant_claim(blob_reader_id)
    assert not index.has_any_tenant_claim(unclaimed_id)

    assert index.path.read_bytes() == index_bytes
    assert index.signature_path.read_bytes() == signature_bytes


@pytest.mark.parametrize(
    "mutation",
    [
        "artifacts-not-a-map",
        "noncanonical-artifact-key",
        "artifact-rows-not-a-list",
        "artifact-row-not-an-object",
        "artifact-row-missing-tenant",
        "view-row-invalid-profile",
        "blob-readers-not-a-map",
        "blob-reader-row-missing-time",
    ],
)
def test_any_claim_query_rejects_malformed_but_signed_v2_index_rows(
    tmp_path: Path,
    mutation: str,
) -> None:
    known_id = ArtifactID.from_sha256_hex("c" * 64)
    other_id = ArtifactID.from_sha256_hex("d" * 64)
    artifacts: dict[str, Any] = {
        str(known_id): [
            {
                "tenant_id": "tenant-a",
                "claimed_at": "2024-01-01T00:00:00+00:00",
            }
        ]
    }
    blob_readers: dict[str, Any] = {}
    if mutation == "artifacts-not-a-map":
        artifacts = []  # type: ignore[assignment]
    elif mutation == "noncanonical-artifact-key":
        artifacts = {
            "sha256:" + "C" * 64: [
                {
                    "tenant_id": "tenant-a",
                    "claimed_at": "2024-01-01T00:00:00+00:00",
                }
            ]
        }
    elif mutation == "artifact-rows-not-a-list":
        artifacts[str(known_id)] = {"tenant_id": "tenant-a"}
    elif mutation == "artifact-row-not-an-object":
        artifacts[str(known_id)] = ["tenant-a"]
    elif mutation == "artifact-row-missing-tenant":
        artifacts[str(known_id)] = [{"claimed_at": "2024-01-01T00:00:00+00:00"}]
    elif mutation == "view-row-invalid-profile":
        artifacts[str(known_id)] = [
            {
                "tenant_id": "tenant-a",
                "claimed_at": "2024-01-01T00:00:00+00:00",
                "manifest_profile_sha256": "invalid",
            }
        ]
    elif mutation == "blob-readers-not-a-map":
        blob_readers = []  # type: ignore[assignment]
    elif mutation == "blob-reader-row-missing-time":
        blob_readers = {str(known_id): [{"tenant_id": "tenant-a"}]}

    index, _index_bytes, _signature_bytes = _write_signed_v2_index(
        tmp_path,
        {"artifacts": artifacts, "blob_readers": blob_readers},
    )

    with pytest.raises(ValueError, match="ownership_index_signature_invalid"):
        index.has_any_tenant_claim(other_id)


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
