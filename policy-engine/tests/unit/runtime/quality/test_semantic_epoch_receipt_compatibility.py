"""Persisted epoch receipt evolution preserves the original statement bytes."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from polisyos.core import artifacts
from polisyos.core.artifacts import ArtifactRef, FileSystemCAS, PutOptions
from polisyos.core.contracts import chronology as chronology_contract
from polisyos.core.contracts import epoch as epoch_contract
from polisyos.runtime.quality import semantic_epoch


def test_historical_production_receipt_wire_shape_survives_profiled_readback(
    tmp_path: Path,
) -> None:
    """The old omitted projection field remains readable with real owner inputs."""
    from tests.unit.runtime.quality.test_epoch_validity_cascade import (
        _transition_history_fixture,
    )

    fixture = _transition_history_fixture(tmp_path)
    store = fixture.store
    statement = fixture.current_receipt.statement_projection()
    statement.pop("chronology_projection_ref")
    parsed = semantic_epoch.SemanticEpochProductionReceipt.model_validate(statement)
    inputs = epoch_contract._semantic_epoch_production_receipt_input_refs(parsed)
    raw = chronology_contract._frame_record(epoch_contract.canonical_epoch_bytes(statement))
    ref = store.put_bytes(
        raw,
        PutOptions(
            kind="epoch.production_receipt",
            media_type="application/vnd.polisyos.epoch-production-receipt+json",
            canon=epoch_contract.epoch_canon_info(),
            inputs=list(inputs),
        ),
        return_selected_profile=True,
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

    # Presence with null changes exact bytes just as presence with a ref.
    # Neither may borrow the old persisted identity or content hash.
    for projection in (None, fixture.current_ref.model_dump(mode="json")):
        with pytest.raises(ValidationError):
            semantic_epoch.PersistedSemanticEpochProductionReceipt.model_validate(
                {**serialized, "chronology_projection_ref": projection}
            )


def test_profileless_historical_production_receipt_remains_typed_refusal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Legacy receipt bytes without a Core declaration never acquire reader authority."""
    from polisyos.common.canonical_profile import CanonicalProfileRefusalError

    store = FileSystemCAS(tmp_path / "profileless-cas")
    digest = f"sha256:{hashlib.sha256(b'legacy-query').hexdigest()}"
    statement = semantic_epoch.SemanticEpochProductionReceipt(
        production_mode="ordinary",
        status="not_established",
        prepared_epoch_ref=None,
        admitted_boundary_evidence_ref=None,
        epoch_ref=None,
        semantic_manifest_ref=None,
        owner_denominator_receipt_refs=(),
        history_append_receipt_ref=None,
        chronology_bundle_ref=None,
        chronology_verification_ref=None,
        requested_query_context_ref=digest,
        failure_codes=("policy_admission_missing",),
    ).statement_projection()
    raw = chronology_contract._frame_record(epoch_contract.canonical_epoch_bytes(statement))
    ref = store.put_bytes(
        raw,
        PutOptions(
            kind="epoch.production_receipt",
            media_type="application/vnd.polisyos.epoch-production-receipt+json",
        ),
    )
    reads: list[str] = []
    read_raw_manifest = store.get_raw_manifest_bytes

    def observe_raw_manifest(*args: Any, **kwargs: Any) -> bytes:
        reads.append("raw_manifest")
        return read_raw_manifest(*args, **kwargs)

    def refuse_payload_access(*args: Any, **kwargs: Any) -> object:
        reads.append("payload_or_verify")
        raise AssertionError("profileless refusal must precede payload and integrity reads")

    monkeypatch.setattr(store, "get_raw_manifest_bytes", observe_raw_manifest)
    monkeypatch.setattr(store, "verify", refuse_payload_access)
    monkeypatch.setattr(store, "get_bytes", refuse_payload_access)
    with pytest.raises(CanonicalProfileRefusalError, match="canon_profile_absent"):
        epoch_contract.load_verified_epoch_statement(
            store=store,
            ref=ref,
            expected_kind="epoch.production_receipt",
            expected_media_type="application/vnd.polisyos.epoch-production-receipt+json",
        )


def test_prepared_statement_recomputes_its_payload_derived_manifest_input_edge(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Prepared inputs are derived from the typed stamp and checked before return."""
    from tests.unit.runtime.quality.test_epoch_validity_cascade import (
        _transition_history_fixture,
    )

    fixture = _transition_history_fixture(tmp_path)
    store = fixture.store
    query = semantic_epoch.EpochResolutionQuery(
        scope_identity=fixture.scope,
        authority_purpose="decision_validity",
        valid_effect_coordinate_evidence_ref=ArtifactRef(
            artifact_id=artifacts.ArtifactID(
                f"sha256:{hashlib.sha256(b'valid-effect-evidence').hexdigest()}"
            ),
            kind="epoch.coordinate.valid-date.v1",
            media_type="application/vnd.polisyos.epoch+json",
        ),
        valid_effect_coordinate_ref=fixture.current.valid_effect_coordinate_ref,
        visibility_knowledge_cutoff_evidence_ref=ArtifactRef(
            artifact_id=artifacts.ArtifactID(
                f"sha256:{hashlib.sha256(b'visibility-evidence').hexdigest()}"
            ),
            kind="epoch.coordinate.knowledge-time.v1",
            media_type="application/vnd.polisyos.epoch+json",
        ),
        visibility_knowledge_cutoff_ref=fixture.current.visibility_knowledge_cutoff_ref,
        purpose_admission_cutoff_evidence_ref=ArtifactRef(
            artifact_id=artifacts.ArtifactID(
                f"sha256:{hashlib.sha256(b'admission-evidence').hexdigest()}"
            ),
            kind="epoch.coordinate.admission-time.v1",
            media_type="application/vnd.polisyos.epoch+json",
        ),
        purpose_admission_cutoff_ref=fixture.current.purpose_admission_cutoff_ref,
        requested_query_context_ref=fixture.current.requested_query_context_ref,
    )
    boundary_ref = ArtifactRef(
        artifact_id=artifacts.ArtifactID(f"sha256:{hashlib.sha256(b'boundary-ref').hexdigest()}"),
        kind="epoch.boundary_denominator_receipt",
        media_type="application/vnd.polisyos.epoch+json",
    )
    facet_ref = ArtifactRef(
        artifact_id=artifacts.ArtifactID(f"sha256:{hashlib.sha256(b'facet-ref').hexdigest()}"),
        kind="epoch.facet_denominator_receipt",
        media_type="application/vnd.polisyos.epoch+json",
    )
    stamp = epoch_contract.SemanticEpochStamp(
        epoch_ref=fixture.current.epoch_ref,
        semantic_manifest_ref=fixture.current_ref,
        semantic_manifest_hash=fixture.current.manifest_content_hash,
        boundary_denominator_receipt_ref=boundary_ref,
        boundary_denominator_receipt_hash=f"sha256:{hashlib.sha256(b'boundary-hash').hexdigest()}",
        facet_denominator_receipt_ref=facet_ref,
        facet_denominator_receipt_hash=f"sha256:{hashlib.sha256(b'facet-hash').hexdigest()}",
        requested_query_context_ref=query.requested_query_context_ref,
        authority_purpose=query.authority_purpose,
        valid_effect_coordinate_ref=query.valid_effect_coordinate_ref,
        visibility_knowledge_cutoff_ref=query.visibility_knowledge_cutoff_ref,
        purpose_admission_cutoff_ref=query.purpose_admission_cutoff_ref,
        predicate_provenance_class="independently_reconciled",
    )
    projection: dict[str, object] = {
        "query": query,
        "stamp": stamp,
        "boundary_candidate_refs": (),
        "boundary_candidates_by_registration": (),
        "owner_denominator_receipt_refs": (),
        "status": "prepared",
    }
    statement = semantic_epoch.PreparedSemanticEpoch.canonical_statement_projection(projection)
    raw = chronology_contract._frame_record(epoch_contract.canonical_epoch_bytes(statement))
    expected_inputs = [
        artifacts.input_ref_from_artifact_ref(
            fixture.current_ref,
            role="semantic_manifest",
        )
    ]
    selected_ref = store.put_bytes(
        raw,
        PutOptions(
            kind="epoch.prepared",
            media_type="application/vnd.polisyos.epoch+json",
            canon=epoch_contract.epoch_canon_info(),
            inputs=expected_inputs,
        ),
        return_selected_profile=True,
    )
    prepared = semantic_epoch.PreparedSemanticEpoch(
        prepared_epoch_ref=selected_ref,
        prepared_content_hash=semantic_epoch._model_hash(
            b"polisyos.epoch.prepared.v1\0",
            statement,
        ),
        **statement,
    )
    assert prepared.statement_projection()["stamp"] == stamp
    admitted = epoch_contract.load_verified_epoch_statement(
        store=store,
        ref=selected_ref,
        expected_kind="epoch.prepared",
    )
    assert admitted["status"] == "prepared"
    assert store.get_manifest(selected_ref).inputs == expected_inputs

    anchor = store.put_bytes(
        b"prepared-extra-edge",
        PutOptions(kind="epoch.test_anchor", media_type="application/octet-stream"),
    )
    wrong_ref = store.put_bytes(
        raw,
        PutOptions(
            kind="epoch.prepared",
            media_type="application/vnd.polisyos.epoch+json",
            canon=epoch_contract.epoch_canon_info(),
            inputs=[
                *expected_inputs,
                artifacts.input_ref_from_artifact_ref(anchor, role="unexpected_parent"),
            ],
        ),
        return_selected_profile=True,
    )
    assert wrong_ref.artifact_id == selected_ref.artifact_id
    assert wrong_ref.manifest_profile_sha256 != selected_ref.manifest_profile_sha256
    assert store.get_bytes(wrong_ref) == raw
    assert len(store.get_manifest(wrong_ref).inputs) == 2

    reads: list[str] = []
    original_get_bytes = type(store).get_bytes
    original_verify = type(store).verify
    prepared_artifact_id = wrong_ref.artifact_id

    def record_get_bytes(owner: object, ref: object) -> bytes:
        if getattr(ref, "artifact_id", ref) == prepared_artifact_id:
            reads.append("get_bytes")
        return original_get_bytes(owner, ref)

    def record_verify(owner: object, ref: object) -> object:
        if getattr(ref, "artifact_id", ref) == prepared_artifact_id:
            reads.append("verify")
        return original_verify(owner, ref)

    monkeypatch.setattr(type(store), "get_bytes", record_get_bytes)
    monkeypatch.setattr(type(store), "verify", record_verify)
    with pytest.raises(ValueError, match="epoch statement manifest input closure differs"):
        epoch_contract.load_verified_epoch_statement(
            store=store,
            ref=wrong_ref,
            expected_kind="epoch.prepared",
        )
    assert reads == ["verify", "get_bytes"]


def test_epoch_issuance_closure_reader_refuses_profileless_core_before_payload(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A typed Core closure edge cannot reach payload or integrity reads unprofiled."""
    from polisyos.common.canonical_profile import CanonicalProfileRefusalError
    from polisyos.runtime.quality.epoch_certificate_issuance import (
        DecisionPacketEpochIssuanceOwner,
    )

    store = FileSystemCAS(tmp_path / "profileless-closure-cas")
    ref = store.put_bytes(
        b"historical receipt bytes",
        PutOptions(
            kind="epoch.production_receipt",
            media_type="application/vnd.polisyos.epoch-production-receipt+json",
        ),
    )
    owner = DecisionPacketEpochIssuanceOwner(store=store, root=tmp_path / "issuance")
    reads: list[str] = []
    read_raw_manifest = store.get_raw_manifest_bytes

    def observe_raw_manifest(*args: object, **kwargs: object) -> bytes:
        reads.append("raw_manifest")
        return read_raw_manifest(*args, **kwargs)

    def refuse_payload_access(*args: object, **kwargs: object) -> object:
        reads.append("payload_or_verify")
        raise AssertionError("Core profile refusal must precede payload and integrity reads")

    monkeypatch.setattr(store, "get_raw_manifest_bytes", observe_raw_manifest)
    monkeypatch.setattr(store, "verify", refuse_payload_access)
    monkeypatch.setattr(store, "get_bytes", refuse_payload_access)
    with pytest.raises(CanonicalProfileRefusalError, match="canon_profile_absent"):
        owner._read_exact(ref)
    assert reads == ["raw_manifest"]


def test_production_receipt_preserves_producer_selected_or_default_manifest_view(
    tmp_path: Path,
) -> None:
    """Receipt persistence preserves the caller's exact child selector."""
    from tests.unit.runtime.quality.test_epoch_validity_cascade import (
        _transition_history_fixture,
    )

    fixture = _transition_history_fixture(tmp_path)
    store = fixture.store
    selected_manifest_ref = fixture.current_ref
    default_manifest_ref = ArtifactRef(
        artifact_id=selected_manifest_ref.artifact_id,
        kind=selected_manifest_ref.kind,
        media_type=selected_manifest_ref.media_type,
    )
    selected_manifest_profile = artifacts.artifact_manifest_profile_sha256(
        store.get_manifest(selected_manifest_ref)
    )
    assert selected_manifest_ref.manifest_profile_sha256 == selected_manifest_profile
    assert default_manifest_ref.manifest_profile_sha256 is None
    resolved_default_ref, resolved_mapping = semantic_epoch._load_owner_projection_mapping(
        store, default_manifest_ref
    )
    assert resolved_default_ref == default_manifest_ref
    assert resolved_default_ref.manifest_profile_sha256 is None
    assert resolved_mapping["epoch_ref"] == fixture.current.epoch_ref

    base = semantic_epoch.SemanticEpochProductionReceipt.model_validate(
        fixture.current_receipt.statement_projection()
    )

    def persist(manifest_ref: ArtifactRef):
        return semantic_epoch.persist_semantic_epoch_production_receipt(
            store=store,
            receipt=base.model_copy(update={"semantic_manifest_ref": manifest_ref}),
        )

    default_receipt = persist(default_manifest_ref)
    selected_receipt = persist(selected_manifest_ref)
    assert default_receipt.receipt_ref.manifest_profile_sha256 is not None
    assert selected_receipt.receipt_ref.manifest_profile_sha256 is not None
    assert (
        store.get_manifest(default_receipt.receipt_ref).canon == epoch_contract.epoch_canon_info()
    )
    assert (
        store.get_manifest(selected_receipt.receipt_ref).canon == epoch_contract.epoch_canon_info()
    )
    assert default_receipt.receipt_ref.artifact_id != selected_receipt.receipt_ref.artifact_id
    assert default_receipt.receipt_content_hash != selected_receipt.receipt_content_hash

    selected_statement = epoch_contract.load_verified_epoch_statement(
        store=store,
        ref=selected_receipt.receipt_ref,
        expected_kind="epoch.production_receipt",
        expected_media_type="application/vnd.polisyos.epoch-production-receipt+json",
    )
    assert (
        selected_statement["semantic_manifest_ref"]["manifest_profile_sha256"]
        == selected_manifest_profile
    )
    default_statement = epoch_contract.load_verified_epoch_statement(
        store=store,
        ref=default_receipt.receipt_ref,
        expected_kind="epoch.production_receipt",
        expected_media_type="application/vnd.polisyos.epoch-production-receipt+json",
    )
    assert "manifest_profile_sha256" not in default_statement["semantic_manifest_ref"]
    assert store.get_manifest(default_receipt.receipt_ref).inputs == list(
        epoch_contract._semantic_epoch_production_receipt_input_refs(
            semantic_epoch.SemanticEpochProductionReceipt.model_validate(default_statement)
        )
    )

    # An extra owner lineage edge is not admitted by the exact-byte/profile check.
    from polisyos.core.artifacts import ArtifactWriteOptions

    raw = store.get_bytes(selected_receipt.receipt_ref)
    old_inputs = list(store.get_manifest(selected_receipt.receipt_ref).inputs)
    anchor = store.put_bytes(
        b"receipt-extra-edge",
        ArtifactWriteOptions(kind="epoch.test_anchor", media_type="application/octet-stream"),
    )
    tampered_ref = store.put_bytes(
        raw,
        ArtifactWriteOptions(
            kind="epoch.production_receipt",
            media_type="application/vnd.polisyos.epoch-production-receipt+json",
            canon=epoch_contract.epoch_canon_info(),
            inputs=[
                *old_inputs,
                artifacts.input_ref_from_artifact_ref(anchor, role="epoch_production_input"),
            ],
        ),
        return_selected_profile=True,
    )
    with pytest.raises(ValueError, match="input closure differs"):
        epoch_contract.load_verified_epoch_statement(
            store=store,
            ref=tampered_ref,
            expected_kind="epoch.production_receipt",
            expected_media_type="application/vnd.polisyos.epoch-production-receipt+json",
        )
