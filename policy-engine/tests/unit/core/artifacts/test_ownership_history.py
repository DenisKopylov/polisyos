"""Behavioral witnesses for versioned artifact-ownership history."""

from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from polisyos.core.artifacts import _atomic_write as atomic_write_module
from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.ownership import ArtifactOwnershipError, ArtifactOwnershipIndex
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon.canon_json import CanonSpec, to_canonical_bytes

_V1_INDEX_SCHEMA = "policyos.artifact_ownership_index.v1"
_V1_SIGNATURE_SCHEMA = "policyos.artifact_ownership_index_signature.v1"
_V2_INDEX_SCHEMA = "policyos.artifact_ownership_index.v2"
_V2_SIGNATURE_SCHEMA = "policyos.artifact_ownership_index_signature.v2"
_V3_INDEX_SCHEMA = "policyos.artifact_ownership_index.v3"
_V3_SIGNATURE_SCHEMA = "policyos.artifact_ownership_index_signature.v3"
_POINTER_SCHEMA = "policyos.artifact_ownership_index_pointer.v1"
_GENERATION_SCHEMA = "policyos.artifact_ownership_index_generation.v1"
_EVIDENCE_SCHEMA_V3 = "policyos.artifact_ownership_evidence.v3"
_POINTER_GENERATION_FORMAT = "pointer_generation_v1"
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
    signature_bytes = (json.dumps(signature_payload, indent=2, sort_keys=True) + "\n").encode()
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
    signature_bytes = (json.dumps(signature_payload, indent=2, sort_keys=True) + "\n").encode()
    index.signature_path.write_bytes(signature_bytes)
    return index, index_bytes, signature_bytes


def _write_signed_index_documents(
    root: Path,
    raw_payload: dict[str, Any],
    signed_projection: dict[str, Any],
) -> tuple[ArtifactOwnershipIndex, bytes, bytes]:
    index = ArtifactOwnershipIndex(root)
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
    signature_bytes = (json.dumps(signature_payload, indent=2, sort_keys=True) + "\n").encode()
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
        payload["artifacts"] = {"sha256:" + "E" * 64: payload["artifacts"][str(claimed_id)]}
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


def test_evidence_read_preserves_valid_v1_index_and_signature_bytes(
    tmp_path: Path,
) -> None:
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
    assert set(evidence) == {
        "mode",
        "schema_version",
        "ownership_index_path",
        "ownership_index_digest",
        "ownership_index_signature_path",
        "ownership_index_signature_digest",
        "artifact_count",
        "blob_reader_claim_count",
        "manifest_view_claim_count",
        "tenant_id",
        "cell_id",
        "tenant_artifact_count",
    }


def test_evidence_read_preserves_valid_v2_index_and_signature_bytes(
    tmp_path: Path,
) -> None:
    artifact_id = ArtifactID.from_sha256_hex("b" * 64)
    index, index_bytes, signature_bytes = _write_signed_v2_index(
        tmp_path,
        {
            "artifacts": {
                str(artifact_id): [
                    {
                        "tenant_id": "tenant-a",
                        "claimed_at": "2024-01-01T00:00:00+00:00",
                    }
                ]
            },
            "blob_readers": {},
        },
    )

    evidence = index.evidence()

    assert index.path.read_bytes() == index_bytes
    assert index.signature_path.read_bytes() == signature_bytes
    assert evidence["schema_version"] == _V2_INDEX_SCHEMA
    assert set(evidence) == {
        "mode",
        "schema_version",
        "ownership_index_path",
        "ownership_index_digest",
        "ownership_index_signature_path",
        "ownership_index_signature_digest",
        "artifact_count",
        "blob_reader_claim_count",
        "manifest_view_claim_count",
    }
    assert "ownership_evidence_schema_version" not in evidence
    assert "ownership_index_format" not in evidence
    assert "ownership_index_pointer_sha256" not in evidence


def test_ambiguous_duplicate_schema_fails_before_stale_legacy_fallback(
    tmp_path: Path,
) -> None:
    artifact_id = ArtifactID.from_sha256_hex("c" * 64)
    index, original_index_bytes, stale_signature_bytes = _write_signed_v2_index(
        tmp_path,
        {
            "artifacts": {
                str(artifact_id): [
                    {
                        "tenant_id": "tenant-a",
                        "claimed_at": "2024-01-01T00:00:00+00:00",
                    }
                ]
            },
            "blob_readers": {},
        },
    )
    v2_schema_line = f'  "schema_version": "{_V2_INDEX_SCHEMA}"\n'.encode()
    ambiguous_index_bytes = original_index_bytes.replace(
        v2_schema_line,
        (
            f'  "schema_version": "{_POINTER_SCHEMA}",\n  "schema_version": "{_V2_INDEX_SCHEMA}"\n'
        ).encode(),
        1,
    )
    assert ambiguous_index_bytes != original_index_bytes
    index.path.write_bytes(ambiguous_index_bytes)

    with pytest.raises(ValueError, match="ownership_index_document_invalid"):
        index.has_any_tenant_claim(artifact_id)

    assert index.path.read_bytes() == ambiguous_index_bytes
    assert index.signature_path.read_bytes() == stale_signature_bytes


@pytest.mark.parametrize("legacy_version", ["v1", "v2"])
def test_explicit_blob_reader_admission_migrates_legacy_pair_to_exact_generation_history(
    tmp_path: Path,
    legacy_version: str,
) -> None:
    existing_id = ArtifactID.from_sha256_hex("2" * 64)
    reader_id = ArtifactID.from_sha256_hex("3" * 64)
    if legacy_version == "v1":
        index, original_payload, legacy_index_bytes, legacy_signature_bytes = (
            _write_signed_v1_index(tmp_path, existing_id)
        )
    else:
        legacy_payload = {
            "artifacts": {
                str(existing_id): [
                    {
                        "tenant_id": "tenant-a",
                        "cell_id": "cell-a",
                        "claimed_at": "2024-01-01T00:00:00+00:00",
                        "writer": "historical-v2-writer",
                    }
                ]
            },
            "blob_readers": {},
        }
        index, legacy_index_bytes, legacy_signature_bytes = _write_signed_v2_index(
            tmp_path,
            legacy_payload,
        )
        original_payload = json.loads(legacy_index_bytes)

    index.record_blob_reader(
        reader_id,
        tenant_id="tenant-b",
        cell_id="cell-b",
        writer="explicit-reader-admission",
    )

    pointer_bytes = index.path.read_bytes()
    pointer = json.loads(pointer_bytes)
    assert set(pointer) == {"schema_version", "mode", "generation_sha256"}
    assert pointer["schema_version"] == _POINTER_SCHEMA
    assert pointer["mode"] == _MODE
    generation_hex = pointer["generation_sha256"].removeprefix("sha256:")
    generation_path = index.path.parent / "generations" / f"{generation_hex}.json"
    generation_bytes = generation_path.read_bytes()
    assert "sha256:" + hashlib.sha256(generation_bytes).hexdigest() == pointer["generation_sha256"]
    generation = json.loads(generation_bytes)

    assert set(generation) == {
        "schema_version",
        "mode",
        "parent_generation_sha256",
        "payload",
        "payload_sha256",
        "signature",
        "legacy_source",
    }
    assert generation["schema_version"] == _GENERATION_SCHEMA
    assert generation["mode"] == _MODE
    assert generation["parent_generation_sha256"] is None
    migrated = generation["payload"]
    assert migrated["schema_version"] == _V3_INDEX_SCHEMA
    assert migrated["artifacts"] == original_payload["artifacts"]
    assert migrated["public_read_closures"] == {}
    assert migrated["blob_readers"][str(reader_id)][0]["tenant_id"] == "tenant-b"
    assert migrated["blob_readers"][str(reader_id)][0]["cell_id"] == "cell-b"
    assert migrated["blob_readers"][str(reader_id)][0]["writer"] == ("explicit-reader-admission")
    assert generation["payload_sha256"] == _canonical_sha256(migrated)

    signature = generation["signature"]
    statement = {key: value for key, value in signature.items() if key != "signature"}
    assert signature["schema_version"] == _V3_SIGNATURE_SCHEMA
    assert signature["index_sha256"] == generation["payload_sha256"]
    assert signature["signature"] == _canonical_sha256(statement)

    legacy_source = generation["legacy_source"]
    assert set(legacy_source) == {
        "index_bytes_base64",
        "index_bytes_sha256",
        "signature_bytes_base64",
        "signature_bytes_sha256",
    }
    assert base64.b64decode(legacy_source["index_bytes_base64"], validate=True) == (
        legacy_index_bytes
    )
    assert base64.b64decode(legacy_source["signature_bytes_base64"], validate=True) == (
        legacy_signature_bytes
    )

    assert legacy_source["index_bytes_sha256"] == (
        "sha256:" + hashlib.sha256(legacy_index_bytes).hexdigest()
    )
    assert legacy_source["signature_bytes_sha256"] == (
        "sha256:" + hashlib.sha256(legacy_signature_bytes).hexdigest()
    )
    assert index.signature_path.read_bytes() == legacy_signature_bytes
    assert index.has_any_tenant_claim(reader_id)

    evidence = index.evidence(tenant_id="tenant-b", cell_id="cell-b")
    assert evidence["ownership_evidence_schema_version"] == _EVIDENCE_SCHEMA_V3
    assert evidence["ownership_index_format"] == _POINTER_GENERATION_FORMAT
    assert evidence["ownership_index_pointer_schema_version"] == _POINTER_SCHEMA
    assert evidence["ownership_index_generation_schema_version"] == _GENERATION_SCHEMA
    assert evidence["ownership_index_pointer_sha256"] == (
        "sha256:" + hashlib.sha256(pointer_bytes).hexdigest()
    )
    assert evidence["ownership_index_path"] == str(index.path)
    assert evidence["ownership_index_generation_path"] == str(generation_path)
    assert evidence["ownership_index_generation_sha256"] == pointer["generation_sha256"]
    assert evidence["ownership_index_digest"] == generation["payload_sha256"]
    assert evidence["ownership_index_signature_digest"] == _canonical_sha256(signature)
    assert "ownership_index_signature_path" not in evidence
    assert evidence["ownership_index_signature_locator"] == {
        "container_ref": pointer["generation_sha256"],
        "member": "signature",
    }
    assert evidence["ownership_index_pre_v3_history_status"] == (
        "current_pair_captured; earlier_overwritten_generations_unresolved"
    )
    assert set(evidence) == {
        "mode",
        "schema_version",
        "ownership_index_path",
        "ownership_index_digest",
        "ownership_index_signature_digest",
        "artifact_count",
        "blob_reader_claim_count",
        "manifest_view_claim_count",
        "ownership_evidence_schema_version",
        "ownership_index_format",
        "ownership_index_pointer_schema_version",
        "ownership_index_pointer_sha256",
        "ownership_index_generation_schema_version",
        "ownership_index_generation_path",
        "ownership_index_generation_sha256",
        "ownership_index_signature_locator",
        "ownership_index_pre_v3_history_status",
        "tenant_id",
        "cell_id",
        "tenant_artifact_count",
    }

    index.record_owner(ArtifactID.from_sha256_hex("d" * 64), tenant_id="tenant-c")
    later_evidence = index.evidence()
    assert later_evidence["ownership_index_pre_v3_history_status"] == (
        "current_pair_captured; earlier_overwritten_generations_unresolved"
    )


def test_public_read_closure_is_per_record_replayable_and_revocable(tmp_path: Path) -> None:
    """Closure mutation advances only that record and persists in the canonical index."""
    artifact_id = ArtifactID.from_sha256_hex("4" * 64)
    record_id = "gpr_" + "r" * 32
    index = ArtifactOwnershipIndex(tmp_path)
    operation_refs = [
        {
            "operation": "get_bytes",
            "artifact_id": str(artifact_id),
            "kind": "test.public_member",
            "media_type": "application/json",
            "manifest_profile_sha256": None,
        }
    ]

    first = index._record_public_read_closure(
        record_id,
        store_identity="sha256:" + "a" * 64,
        operation_refs=operation_refs,
    )
    assert first["status"] == "active"
    assert first["epoch"] == 1
    assert first["operation_refs"] == operation_refs
    assert index._get_public_read_closure(record_id) == first
    assert (
        index._record_public_read_closure(
            record_id,
            store_identity="sha256:" + "a" * 64,
            operation_refs=operation_refs,
        )
        == first
    )
    with pytest.raises(ValueError, match="public_read_closure_already_exists"):
        index._record_public_read_closure(
            record_id,
            store_identity="sha256:" + "a" * 64,
            operation_refs=[
                {
                    **operation_refs[0],
                    "kind": "test.foreign_profile",
                }
            ],
        )

    assert index._revoke_public_read_closure(record_id) is True
    withdrawn = index._get_public_read_closure(record_id)
    assert withdrawn is not None
    assert withdrawn["status"] == "revoked"
    assert withdrawn["epoch"] == 2
    assert withdrawn["operation_refs"] == operation_refs
    assert index._public_read_closure_matches(
        record_id,
        store_identity="sha256:" + "a" * 64,
        epoch=1,
        operation="get_bytes",
        ref_identity=(str(artifact_id), "test.public_member", "application/json", None),
    ) is False


def test_empty_index_evidence_is_ephemeral_and_read_only(tmp_path: Path) -> None:
    root = tmp_path / "empty-cas"
    index = ArtifactOwnershipIndex(root)

    def filesystem_state() -> dict[Path, tuple[str, int, int, bytes]]:
        state = {}
        for path in (root, *root.rglob("*")):
            stat = path.stat()
            relative = path.relative_to(root.parent)
            if path.is_dir():
                state[relative] = ("directory", stat.st_mtime_ns, stat.st_ino, b"")
            else:
                state[relative] = ("file", stat.st_mtime_ns, stat.st_ino, path.read_bytes())
        return state

    before_evidence = filesystem_state()

    evidence = index.evidence()

    assert evidence["ownership_evidence_schema_version"] == _EVIDENCE_SCHEMA_V3
    assert evidence["ownership_index_format"] == "ephemeral_empty_v2"
    assert evidence["ownership_index_persisted"] is False
    assert evidence["ownership_index_pointer_schema_version"] is None
    assert evidence["ownership_index_pointer_sha256"] is None
    assert evidence["ownership_index_generation_schema_version"] is None
    assert evidence["ownership_index_generation_path"] is None
    assert evidence["ownership_index_generation_sha256"] is None
    assert evidence["ownership_index_signature_locator"] is None
    assert evidence["ownership_index_pre_v3_history_status"] == "no_pre_v3_pair"
    assert not index.path.exists()
    assert not index.signature_path.exists()
    assert not (index.directory / "generations").exists()
    assert filesystem_state() == before_evidence


def test_noop_legacy_mutation_preserves_pair_without_migration(tmp_path: Path) -> None:
    artifact_id = ArtifactID.from_sha256_hex("4" * 64)
    index, _payload, index_bytes, signature_bytes = _write_signed_v1_index(
        tmp_path,
        artifact_id,
    )

    index.record_owner(artifact_id, tenant_id="tenant-a", cell_id="cell-a")

    assert index.path.read_bytes() == index_bytes
    assert index.signature_path.read_bytes() == signature_bytes
    assert not (index.directory / "generations").exists()


def test_pointer_precedence_rejects_missing_generation_without_legacy_fallback(
    tmp_path: Path,
) -> None:
    artifact_id = ArtifactID.from_sha256_hex("5" * 64)
    index, _payload, _index_bytes, signature_bytes = _write_signed_v1_index(
        tmp_path,
        artifact_id,
    )
    pointer = {
        "schema_version": _POINTER_SCHEMA,
        "mode": _MODE,
        "generation_sha256": "sha256:" + "a" * 64,
    }
    pointer_bytes = (json.dumps(pointer, indent=2, sort_keys=True) + "\n").encode()
    index.path.write_bytes(pointer_bytes)

    with pytest.raises(ValueError, match="ownership_index_generation_invalid"):
        index.has_any_tenant_claim(artifact_id)

    assert index.path.read_bytes() == pointer_bytes
    assert index.signature_path.read_bytes() == signature_bytes


@pytest.mark.parametrize(
    "mutation",
    ["unknown-field", "untrusted-path", "wrong-mode", "malformed-generation-digest"],
)
def test_current_pointer_rejects_malformed_shape_with_typed_failure(
    tmp_path: Path,
    mutation: str,
) -> None:
    index = ArtifactOwnershipIndex(tmp_path)
    index.record_owner(ArtifactID.from_sha256_hex("6" * 64), tenant_id="tenant-a")
    pointer = json.loads(index.path.read_bytes())
    if mutation == "unknown-field":
        pointer["extra"] = "ignored-by-legacy-fallback-is-not-allowed"
    elif mutation == "untrusted-path":
        pointer["generation_path"] = "../../foreign.json"
    elif mutation == "wrong-mode":
        pointer["mode"] = "different-owner"
    else:
        pointer["generation_sha256"] = "sha256:" + "A" * 64
    pointer_bytes = (json.dumps(pointer, indent=2, sort_keys=True) + "\n").encode()
    index.path.write_bytes(pointer_bytes)

    with pytest.raises(ValueError, match="ownership_index_pointer_invalid"):
        index.has_any_tenant_claim(ArtifactID.from_sha256_hex("6" * 64))

    assert index.path.read_bytes() == pointer_bytes


def test_generation_updates_are_immutable_and_link_to_prior_generation(
    tmp_path: Path,
) -> None:
    index = ArtifactOwnershipIndex(tmp_path)
    first_id = ArtifactID.from_sha256_hex("7" * 64)
    second_id = ArtifactID.from_sha256_hex("8" * 64)
    index.record_owner(first_id, tenant_id="tenant-a")

    first_pointer = json.loads(index.path.read_bytes())
    first_path = (
        index.directory
        / "generations"
        / (first_pointer["generation_sha256"].removeprefix("sha256:") + ".json")
    )
    first_bytes = first_path.read_bytes()
    first_generation = json.loads(first_bytes)
    assert first_generation["parent_generation_sha256"] is None
    assert first_generation["legacy_source"] is None

    index.record_blob_reader(second_id, tenant_id="tenant-b")

    second_pointer = json.loads(index.path.read_bytes())
    second_path = (
        index.directory
        / "generations"
        / (second_pointer["generation_sha256"].removeprefix("sha256:") + ".json")
    )
    second_generation = json.loads(second_path.read_bytes())
    assert second_pointer["generation_sha256"] != first_pointer["generation_sha256"]
    assert second_generation["parent_generation_sha256"] == first_pointer["generation_sha256"]
    assert first_path.read_bytes() == first_bytes
    assert index.has_any_tenant_claim(first_id)
    assert index.has_any_tenant_claim(second_id)


def test_generation_directory_and_pointer_commit_are_strictly_synced(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    index = ArtifactOwnershipIndex(tmp_path)
    fsync_directories: list[Path] = []
    original_fsync_directory = atomic_write_module.fsync_directory

    def observe_fsync_directory(path: Path) -> None:
        fsync_directories.append(path)
        original_fsync_directory(path)

    monkeypatch.setattr(atomic_write_module, "fsync_directory", observe_fsync_directory)
    index.record_owner(ArtifactID.from_sha256_hex("9" * 64), tenant_id="tenant-a")

    assert fsync_directories[-3:] == [
        index.directory,
        index.directory / "generations",
        index.directory,
    ]


def test_pointer_parent_fsync_failure_is_indeterminate_and_retryable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    index = ArtifactOwnershipIndex(tmp_path)
    artifact_id = ArtifactID.from_sha256_hex("a" * 64)
    original_fsync_directory = atomic_write_module.fsync_directory
    fail_after_replace = True

    def fail_pointer_parent_fsync(path: Path) -> None:
        nonlocal fail_after_replace
        if (
            fail_after_replace
            and path == index.directory
            and index.path.exists()
            and json.loads(index.path.read_bytes()).get("schema_version") == _POINTER_SCHEMA
        ):
            fail_after_replace = False
            raise OSError("injected pointer parent fsync failure")
        original_fsync_directory(path)

    monkeypatch.setattr(atomic_write_module, "fsync_directory", fail_pointer_parent_fsync)
    with pytest.raises(RuntimeError, match="ownership_index_publication_indeterminate"):
        index.record_owner(artifact_id, tenant_id="tenant-a")

    pointer = json.loads(index.path.read_bytes())
    assert pointer["schema_version"] == _POINTER_SCHEMA
    monkeypatch.setattr(atomic_write_module, "fsync_directory", original_fsync_directory)
    generation_count = len(list((index.directory / "generations").glob("*.json")))
    index.record_owner(artifact_id, tenant_id="tenant-a")
    assert len(list((index.directory / "generations").glob("*.json"))) == generation_count


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


def test_final_cas_parent_sync_failure_prevents_owner_generation_commit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "cas"
    store = FileSystemCAS(root).for_tenant("tenant-a", cell_id="cell-a")
    payload = b"durability must precede tenant owner-generation admission"
    artifact_id = ArtifactID.from_sha256_hex(hashlib.sha256(payload).hexdigest())
    final_parent = (
        root
        / "artifacts"
        / "sha256"
        / artifact_id.hex[:2]
        / artifact_id.hex[2:4]
    )
    original_fsync_directory = atomic_write_module.fsync_directory
    failed_final_sync = False

    def fail_final_parent_sync(path: Path) -> None:
        nonlocal failed_final_sync
        if path == final_parent and not failed_final_sync:
            failed_final_sync = True
            raise OSError("injected CAS member parent fsync failure")
        original_fsync_directory(path)

    monkeypatch.setattr(atomic_write_module, "fsync_directory", fail_final_parent_sync)
    with pytest.raises(OSError):
        store.put_bytes(
            payload,
            PutOptions(kind="test.r9.durable", media_type="application/octet-stream"),
        )

    assert failed_final_sync
    assert not store._ownership_index.has_any_tenant_claim(artifact_id)
    intent_path = store._ownership_index._transaction_intent_path(artifact_id)
    assert json.loads(intent_path.read_bytes())["status"] == "pending"
    with pytest.raises(ArtifactOwnershipError):
        store.with_ambient_ownership_enforcement().get_bytes(artifact_id)
