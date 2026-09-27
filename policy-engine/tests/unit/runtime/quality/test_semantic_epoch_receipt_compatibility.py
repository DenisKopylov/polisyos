"""Persisted epoch receipt evolution preserves the original statement bytes."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from pydantic import ValidationError

from polisyos.core.artifacts import ArtifactRef, FileSystemCAS, PutOptions
from polisyos.core.artifacts.manifest import InputRef
from polisyos.core.contracts import chronology as chronology_contract
from polisyos.core.contracts import epoch as epoch_contract
from polisyos.runtime.quality import semantic_epoch


@pytest.mark.parametrize("positive", [False, True])
def test_legacy_production_receipt_cas_readback_preserves_exact_statement(
    tmp_path: Path, positive: bool
) -> None:
    """Old statement grammar remains readable without acquiring native custody."""
    store = FileSystemCAS(tmp_path / "cas")
    evidence = store.put_bytes(
        b"legacy-proof",
        PutOptions(kind="epoch.legacy-test-evidence", media_type="application/octet-stream"),
    )
    digest = f"sha256:{hashlib.sha256(b'legacy-query').hexdigest()}"
    # These are the complete pre-projection receipt fields. The old positive
    # shape is evidence for codec compatibility, never a native qualification.
    statement = {
        "production_mode": "ordinary",
        "status": "appended" if positive else "not_established",
        "prepared_epoch_ref": None,
        "admitted_boundary_evidence_ref": None,
        "epoch_ref": digest if positive else None,
        "semantic_manifest_ref": evidence.model_dump(mode="json") if positive else None,
        "owner_denominator_receipt_refs": [],
        "history_append_receipt_ref": evidence.model_dump(mode="json") if positive else None,
        "chronology_bundle_ref": evidence.model_dump(mode="json") if positive else None,
        "chronology_verification_ref": evidence.model_dump(mode="json") if positive else None,
        "requested_query_context_ref": digest,
        "failure_codes": [] if positive else ["policy_admission_missing"],
    }
    raw = chronology_contract._frame_record(epoch_contract.canonical_epoch_bytes(statement))
    ref = store.put_bytes(
        raw,
        PutOptions(
            kind="epoch.production_receipt",
            media_type="application/vnd.polisyos.epoch-production-receipt+json",
        ),
    )
    content_hash = epoch_contract.epoch_semantic_content_hash(
        domain="polisyos.epoch.production-receipt.v1", value=statement
    )
    decoded = epoch_contract.load_verified_epoch_statement(
        store=store,
        ref=ref,
        expected_kind=ref.kind,
        expected_media_type=ref.media_type,
    )
    assert decoded == statement
    base_receipt = semantic_epoch.SemanticEpochProductionReceipt.model_validate(decoded)
    assert base_receipt.statement_projection() == statement
    assert "chronology_projection_ref" not in base_receipt.statement_projection()
    explicitly_null = semantic_epoch.SemanticEpochProductionReceipt.model_validate(
        {**decoded, "chronology_projection_ref": None}
    )
    explicit_null_projection = explicitly_null.statement_projection()
    assert "chronology_projection_ref" in explicit_null_projection
    assert explicit_null_projection["chronology_projection_ref"] is None
    if positive:
        assert "manifest_profile_sha256" not in decoded["semantic_manifest_ref"]
    receipt = semantic_epoch.PersistedSemanticEpochProductionReceipt.model_validate(
        {**decoded, "receipt_ref": ref, "receipt_content_hash": content_hash}
    )
    assert receipt.chronology_projection_ref is None
    serialized = receipt.model_dump(mode="json")
    assert "chronology_projection_ref" not in serialized
    assert (
        semantic_epoch.PersistedSemanticEpochProductionReceipt.model_validate_json(
            receipt.model_dump_json()
        )
        == receipt
    )
    exact = {
        key: value
        for key, value in serialized.items()
        if key not in {"receipt_ref", "receipt_content_hash"}
    }
    assert chronology_contract._frame_record(epoch_contract.canonical_epoch_bytes(exact)) == raw
    assert store.get_bytes(ref.artifact_id) == raw
    assert str(ref.artifact_id) == f"sha256:{hashlib.sha256(raw).hexdigest()}"
    assert receipt.receipt_content_hash == content_hash

    # Presence with null changes exact bytes just as presence with a ref does.
    # Neither may borrow the old persisted identity or content hash.
    for projection in (None, evidence.model_dump(mode="json")):
        with pytest.raises(ValidationError):
            semantic_epoch.PersistedSemanticEpochProductionReceipt.model_validate(
                {**serialized, "chronology_projection_ref": projection}
            )


def test_production_receipt_persists_a_selected_manifest_view(tmp_path: Path) -> None:
    """The exact receipt payload distinguishes the selected view of identical bytes."""
    store = FileSystemCAS(tmp_path / "cas").for_tenant("tenant-a")
    anchor_ref = store.put_bytes(
        b"owner-anchor",
        PutOptions(kind="epoch.owner_anchor", media_type="application/vnd.polisyos.epoch+json"),
    )
    manifest_bytes = b"same semantic manifest bytes"
    default_manifest_ref = store.put_bytes(
        manifest_bytes,
        PutOptions(
            kind="epoch.semantic_manifest",
            media_type="application/vnd.polisyos.epoch+json",
        ),
    )
    selected_manifest_ref = store.put_bytes(
        manifest_bytes,
        PutOptions(
            kind="epoch.semantic_manifest",
            media_type="application/vnd.polisyos.epoch+json",
            inputs=[InputRef(artifact_id=anchor_ref.artifact_id, role="semantic_basis")],
        ),
    )
    assert default_manifest_ref.artifact_id == selected_manifest_ref.artifact_id
    assert default_manifest_ref.kind == selected_manifest_ref.kind
    assert default_manifest_ref.media_type == selected_manifest_ref.media_type
    assert default_manifest_ref.manifest_profile_sha256 is None
    assert selected_manifest_ref.manifest_profile_sha256 is not None

    history_ref = store.put_bytes(
        b"history receipt",
        PutOptions(
            kind="epoch.history_append_receipt", media_type="application/vnd.polisyos.epoch+json"
        ),
    )
    chronology_ref = store.put_bytes(
        b"chronology proof",
        PutOptions(
            kind="chronology.full_prefix.bundle", media_type="application/vnd.polisyos.epoch+json"
        ),
    )
    verification_ref = store.put_bytes(
        b"chronology verification",
        PutOptions(
            kind="chronology.verifier.result", media_type="application/vnd.polisyos.epoch+json"
        ),
    )
    digest = "sha256:" + hashlib.sha256(b"same-epoch").hexdigest()

    def persist(
        manifest_ref: ArtifactRef,
    ) -> semantic_epoch.PersistedSemanticEpochProductionReceipt:
        return semantic_epoch.persist_semantic_epoch_production_receipt(
            store=store,
            receipt=semantic_epoch.SemanticEpochProductionReceipt(
                production_mode="ordinary",
                status="appended",
                prepared_epoch_ref=None,
                admitted_boundary_evidence_ref=None,
                epoch_ref=digest,
                semantic_manifest_ref=manifest_ref,
                owner_denominator_receipt_refs=(),
                history_append_receipt_ref=history_ref,
                chronology_bundle_ref=chronology_ref,
                chronology_verification_ref=verification_ref,
                requested_query_context_ref=digest,
                failure_codes=(),
            ),
        )

    default_receipt = persist(default_manifest_ref)
    selected_receipt = persist(selected_manifest_ref)
    assert default_receipt.receipt_ref.artifact_id != selected_receipt.receipt_ref.artifact_id
    assert default_receipt.receipt_content_hash != selected_receipt.receipt_content_hash

    selected_statement = epoch_contract.load_verified_epoch_statement(
        store=store,
        ref=selected_receipt.receipt_ref,
        expected_kind="epoch.production_receipt",
        expected_media_type="application/vnd.polisyos.epoch-production-receipt+json",
    )
    assert "chronology_projection_ref" in selected_statement
    assert selected_statement["chronology_projection_ref"] is None
    assert (
        selected_statement["semantic_manifest_ref"]["manifest_profile_sha256"]
        == selected_manifest_ref.manifest_profile_sha256
    )
    default_statement = epoch_contract.load_verified_epoch_statement(
        store=store,
        ref=default_receipt.receipt_ref,
        expected_kind="epoch.production_receipt",
        expected_media_type="application/vnd.polisyos.epoch-production-receipt+json",
    )
    assert "manifest_profile_sha256" not in default_statement["semantic_manifest_ref"]
