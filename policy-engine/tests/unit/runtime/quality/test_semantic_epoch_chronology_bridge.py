from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from polisyos.core import artifacts
from polisyos.core.contracts import chronology as chronology_contract
from polisyos.core.contracts import epoch as epoch_contract
from polisyos.runtime.quality import semantic_epoch as epoch
from tests._helpers.semantic_epoch_native import (
    _real_epoch_scenario,
    finalize_native_epoch_case,
    sign_native_epoch_scenario,
)


def test_owner_chain_composes_chronology_artifact_codecs(tmp_path: Path) -> None:
    scenario = _real_epoch_scenario(tmp_path / "scenario")
    case = sign_native_epoch_scenario(scenario, tmp_path / "policy")
    finalized = finalize_native_epoch_case(case)
    codecs = {
        kind: epoch_contract.acquisition_artifact_codec(kind, media_type=media_type)
        for kind, media_type in (
            ("core.chronology.full_prefix.bundle", "application/octet-stream"),
            ("core.chronology.full_prefix.verification_result", "application/octet-stream"),
            ("core.chronology.native_projection", "application/octet-stream"),
            (
                "epoch.history_append_receipt",
                "application/vnd.polisyos.epoch+json",
            ),
        )
    }

    assert all(codec is not None for codec in codecs.values())
    assert (
        epoch._resolve_selected_reference_graph(
            case.store,
            finalized.production.receipt_ref,
            native_projection_qualifier=case.service._requalify_persisted_native_projection,
        )
        is not None
    )


def test_current_owner_requalification_rejects_a_changed_owner_receipt_ref(
    tmp_path: Path,
) -> None:
    scenario = _real_epoch_scenario(tmp_path / "scenario")
    case = sign_native_epoch_scenario(scenario, tmp_path / "policy")
    finalized = finalize_native_epoch_case(case)
    projection_ref, projection_mapping = epoch._load_owner_projection_mapping(
        case.store, finalized.production.chronology_projection_ref
    )
    projection = chronology_contract.NativeChronologyProjectionStatement.model_validate(
        projection_mapping
    )

    tampered_mapping = projection.model_dump(mode="json")
    owner_context = tampered_mapping["reconciliation"]["owner_context"]
    owner_relation = owner_context["owner_qualified_candidate"]["owner_relation_verification"]
    absent_receipt_id = f"sha256:{hashlib.sha256(b'absent owner verification receipt').hexdigest()}"
    owner_relation["verification_receipt_ref"]["artifact_id"] = absent_receipt_id
    owner_relation["verification_receipt_content_hash"] = absent_receipt_id
    tampered_projection = chronology_contract.NativeChronologyProjectionStatement.model_validate(
        tampered_mapping
    )
    tampered_owner_qualified = (
        tampered_projection.reconciliation.owner_context.owner_qualified_candidate
    )
    original_owner_qualified = projection.reconciliation.owner_context.owner_qualified_candidate
    assert tampered_owner_qualified.candidate == original_owner_qualified.candidate
    assert tampered_projection.proof_result == projection.proof_result
    assert (
        tampered_owner_qualified.owner_relation_verification.verification_receipt_content_hash
        == absent_receipt_id
    )

    projection_raw = chronology_contract._frame_record(
        chronology_contract._canonical_raw_bytes(
            chronology_contract._raw_model_mapping(tampered_projection)
        )
    )
    projection_manifest = case.store.get_manifest(projection_ref)
    altered_owner_receipt_ref = artifacts.ArtifactRef.model_validate(
        owner_relation["verification_receipt_ref"]
    )
    altered_projection_ref = case.store.put_bytes(
        projection_raw,
        artifacts.ArtifactWriteOptions(
            kind="core.chronology.native_projection",
            media_type="application/octet-stream",
            schema=projection_manifest.artifact_schema,
            inputs=[
                artifacts.input_ref_from_artifact_ref(
                    altered_owner_receipt_ref,
                    role="native_owner_verification",
                ),
                artifacts.input_ref_from_artifact_ref(
                    tampered_projection.reconciliation.applicable_predicate_denominator.artifact_ref,
                    role="applicable_predicate_denominator",
                ),
            ],
            canon=projection_manifest.canon,
        ),
        return_selected_profile=True,
    )
    assert case.store.verify(altered_projection_ref).ok
    assert (
        chronology_contract.NativeChronologyProjectionStatement.model_validate(
            epoch._load_owner_projection_mapping(case.store, altered_projection_ref)[1]
        )
        == tampered_projection
    )

    altered_production_statement = epoch.SemanticEpochProductionReceipt.model_validate(
        finalized.production.statement_projection()
        | {"chronology_projection_ref": altered_projection_ref.model_dump(mode="json")}
    )
    altered_production = epoch.persist_semantic_epoch_production_receipt(
        store=case.store,
        receipt=altered_production_statement,
    )

    with pytest.raises(ValueError, match="fresh owner qualification differs"):
        case.service._requalify_persisted_native_projection(
            altered_projection_ref, tampered_projection
        )
    assert (
        epoch._resolve_selected_reference_graph(
            case.store,
            altered_production.receipt_ref,
            native_projection_qualifier=case.service._requalify_persisted_native_projection,
        )
        is None
    )
