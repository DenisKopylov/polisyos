from __future__ import annotations

import hashlib
import json
from typing import TYPE_CHECKING

import pytest

from polisyos.core import artifacts
from polisyos.core.contracts import chronology as chronology_contract
from polisyos.core.contracts import epoch as epoch_contract
from polisyos.runtime.quality import chronology_proof
from polisyos.runtime.quality import semantic_epoch as epoch
from polisyos.runtime.quality.acquisition_executor import (
    SemanticEpochAdmissionResolutionError,
    resolve_activated_semantic_epoch_admission,
)
from polisyos.runtime.quality.chronology_qualification import QualificationConsumer
from polisyos.runtime.quality.epoch_deployment import (
    EpochDeployment,
    EpochTrustedIssuerConfig,
)
from polisyos.runtime.quality.semantic_epoch_qualification import (
    build_semantic_epoch_native_deployment,
)
from tests._helpers.semantic_epoch_native import (
    _real_epoch_scenario,
    finalize_native_epoch_case,
    sign_native_epoch_scenario,
)

if TYPE_CHECKING:
    from pathlib import Path


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


def _put_selected_manifest_view(
    store: artifacts.ArtifactStore,
    ref: artifacts.ArtifactRef,
    *,
    inputs: list[artifacts.InputRef],
) -> artifacts.ArtifactRef:
    manifest = store.get_manifest(ref)
    selected = store.put_bytes(
        store.get_bytes(ref),
        artifacts.ArtifactWriteOptions(
            kind=ref.kind,
            media_type=ref.media_type,
            schema=manifest.artifact_schema,
            inputs=inputs,
            canon=manifest.canon,
        ),
        return_selected_profile=True,
    )
    assert selected.artifact_id == ref.artifact_id
    assert selected.manifest_profile_sha256 != ref.manifest_profile_sha256
    return selected


def _mutate_manifest_inputs(
    inputs: list[artifacts.InputRef], variant: str
) -> list[artifacts.InputRef]:
    assert inputs
    if variant == "missing":
        return list(inputs[:-1])
    if variant == "extra":
        return [*inputs, inputs[0].model_copy(update={"role": "unowned_extra_edge"})]
    changed = inputs[-1].model_copy(update={"manifest_profile_sha256": "sha256:" + "0" * 64})
    return [*inputs[:-1], changed]


@pytest.mark.parametrize("artifact_role", ["bundle", "verification", "projection"])
@pytest.mark.parametrize("input_variant", ["missing", "extra", "wrong_profile"])
def test_epoch_graph_rejects_wrong_core_chronology_input_closure(
    tmp_path: Path,
    artifact_role: str,
    input_variant: str,
) -> None:
    scenario = _real_epoch_scenario(tmp_path / "scenario")
    case = sign_native_epoch_scenario(scenario, tmp_path / "policy")
    finalized = finalize_native_epoch_case(case)
    original = finalized.production
    statement = epoch_contract.SemanticEpochProductionReceiptStatement.model_validate(
        original.statement_projection()
    )
    updates: dict[str, object] = {}

    if artifact_role == "bundle":
        bundle_ref = statement.chronology_bundle_ref
        assert bundle_ref is not None
        bundle_manifest = case.store.get_manifest(bundle_ref)
        assert bundle_manifest.inputs
        selected_bundle = _put_selected_manifest_view(
            case.store,
            bundle_ref,
            inputs=_mutate_manifest_inputs(bundle_manifest.inputs, input_variant),
        )
        assert statement.chronology_verification_ref is not None
        verification_mapping = epoch._load_owner_projection_mapping(
            case.store, statement.chronology_verification_ref
        )[1]
        verification = chronology_contract.FullPrefixVerificationStatement.model_validate(
            verification_mapping
        ).model_copy(update={"bundle_ref": selected_bundle})
        verification_raw = chronology_contract._frame_record(
            chronology_contract._canonical_raw_bytes(
                chronology_contract._raw_model_mapping(verification)
            )
        )
        old_verification_ref = statement.chronology_verification_ref
        verification_manifest = case.store.get_manifest(old_verification_ref)
        selected_verification = case.store.put_bytes(
            verification_raw,
            artifacts.ArtifactWriteOptions(
                kind=old_verification_ref.kind,
                media_type=old_verification_ref.media_type,
                schema=verification_manifest.artifact_schema,
                inputs=list(
                    chronology_contract._full_prefix_verification_manifest_input_refs(verification)
                ),
                canon=verification_manifest.canon,
            ),
            return_selected_profile=True,
        )
        updates = {
            "chronology_bundle_ref": selected_bundle.model_dump(mode="json"),
            "chronology_verification_ref": selected_verification.model_dump(mode="json"),
        }
        assert statement.chronology_projection_ref is not None
        projection_mapping = epoch._load_owner_projection_mapping(
            case.store, statement.chronology_projection_ref
        )[1]
        projection = chronology_contract.NativeChronologyProjectionStatement.model_validate(
            projection_mapping
        )
        verification_replay = chronology_proof.ChronologyProofArtifactReader(
            store=case.store
        ).load_and_verify(
            query=projection.reconciliation.owner_context.query,
            bundle_ref=selected_bundle,
            expected_domain=projection.reconciliation.owner_context.query.domain,
            expected_prefix=verification.expected_prefix,
            expected_bundle_content_hash=verification.expected_bundle_content_hash,
            reconciliation=projection.reconciliation,
        )
        assert isinstance(
            verification_replay,
            chronology_contract.ChronologyPersistenceManifestMismatch,
        )
    elif artifact_role == "verification":
        ref = statement.chronology_verification_ref
        assert ref is not None
        manifest = case.store.get_manifest(ref)
        assert manifest.inputs
        selected = _put_selected_manifest_view(
            case.store,
            ref,
            inputs=_mutate_manifest_inputs(manifest.inputs, input_variant),
        )
        updates = {"chronology_verification_ref": selected.model_dump(mode="json")}
        with pytest.raises(ValueError, match="chronology statement manifest input closure differs"):
            epoch._load_selected_acquisition_mapping(
                case.store,
                selected,
                expected_kind="core.chronology.full_prefix.verification_result",
            )
    else:
        ref = statement.chronology_projection_ref
        assert ref is not None
        manifest = case.store.get_manifest(ref)
        assert manifest.inputs
        selected = _put_selected_manifest_view(
            case.store,
            ref,
            inputs=_mutate_manifest_inputs(manifest.inputs, input_variant),
        )
        updates = {"chronology_projection_ref": selected.model_dump(mode="json")}
        with pytest.raises(ValueError, match="chronology statement manifest input closure differs"):
            epoch._load_selected_acquisition_mapping(
                case.store,
                selected,
                expected_kind="core.chronology.native_projection",
            )

    changed = epoch_contract.SemanticEpochProductionReceiptStatement.model_validate(
        original.statement_projection() | updates
    )
    persisted = epoch.persist_semantic_epoch_production_receipt(
        store=case.store,
        receipt=epoch.SemanticEpochProductionReceipt.model_validate(
            changed.model_dump(mode="json")
        ),
    )
    assert (
        epoch._resolve_selected_reference_graph(
            case.store,
            persisted.receipt_ref,
            native_projection_qualifier=case.service._requalify_persisted_native_projection,
        )
        is None
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


def test_additive_native_trust_requalifies_historical_projection_and_graph(
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

    exact = case.service._requalify_persisted_native_projection(projection_ref, projection)
    assert scenario.service._native_projection_requalification_matches(
        projection_ref, projection, exact
    )
    unrelated = type(case.custodian).create(case.store, tmp_path / "unrelated-issuer")
    current_config = case.config.model_copy(
        update={
            "trusted_issuers": (
                *case.config.trusted_issuers,
                EpochTrustedIssuerConfig(
                    identity="fixture-native-epoch-independent-reviewer",
                    public_key_path=unrelated.public_key_path,
                    roles=("predicate_policy_admission",),
                ),
            )
        }
    )
    deployment = build_semantic_epoch_native_deployment(current_config)
    policy_owner = deployment._state().chronology_policy_owner
    assert policy_owner is not None
    current_service = epoch.SemanticEpochService(
        boundary_registry=case.service._boundary_registry,
        boundary_adapters=case.service._boundary_adapters,
        facet_registry=case.service._facet_registry,
        facet_provider=case.service._facet_provider,
        history=scenario.history,
        artifact_store=case.store,
        qualification_consumer=QualificationConsumer.from_deployment(
            deployment, runtime_artifact_store=case.store
        ),
        chronology_adapter=epoch.SemanticEpochQualificationAdapter(
            history=scenario.history,
            artifacts=case.store,
            policy_owner=policy_owner,
        ),
    )

    fresh = current_service._requalify_persisted_native_projection(projection_ref, projection)
    assert fresh.proof_result == projection.proof_result
    assert fresh.reconciliation.owner_context.query == projection.reconciliation.owner_context.query
    assert fresh.projection_receipt.statement != projection
    assert (
        epoch._resolve_selected_reference_graph(
            case.store,
            finalized.production.receipt_ref,
            native_projection_qualifier=current_service._requalify_persisted_native_projection,
            native_projection_requalification_matches=(
                current_service._native_projection_requalification_matches
            ),
        )
        is not None
    )

    def read_activation(owner: EpochDeployment) -> object:
        return resolve_activated_semantic_epoch_admission(
            receipt=finalized.receipt,
            artifact_store=case.store,
            overlay=scenario.overlay,
            authority=scenario.authority,
            epoch_deployment=owner,
        )

    original_activation = read_activation(case.deployment)
    assert read_activation(deployment) == original_activation
    original_bundle = finalized.production.chronology_bundle_ref
    assert original_bundle is not None
    fresh_bundle = fresh.persisted_proof.artifact_ref
    assert fresh_bundle != original_bundle
    bundle_path = case.store._manifest_path_for_ref(
        original_bundle.artifact_id, original_bundle.manifest_profile_sha256
    )
    removed = bundle_path.with_suffix(".removed-for-readback")
    bundle_path.rename(removed)
    try:
        assert case.store.verify(fresh_bundle).ok
        with pytest.raises(SemanticEpochAdmissionResolutionError, match="basis_mismatch"):
            read_activation(deployment)
    finally:
        removed.rename(bundle_path)
    assert read_activation(deployment) == original_activation

    historical_denominator = projection.reconciliation.applicable_predicate_denominator
    profileless_denominator_ref = artifacts.ArtifactRef.model_validate(
        historical_denominator.artifact_ref.model_dump(mode="json")
        | {"manifest_profile_sha256": None}
    )
    profileless_denominator = epoch._replace_epoch_model(
        historical_denominator, artifact_ref=profileless_denominator_ref
    )
    profileless_reconciliation = epoch._replace_epoch_model(
        projection.reconciliation,
        applicable_predicate_denominator=profileless_denominator,
    )
    profileless_projection = epoch._replace_epoch_model(
        projection, reconciliation=profileless_reconciliation
    )
    projection_manifest = case.store.get_manifest(projection_ref)
    profileless_projection_bytes = chronology_contract._frame_record(
        chronology_contract._canonical_raw_bytes(
            chronology_contract._raw_model_mapping(profileless_projection)
        )
    )
    profileless_projection_ref = case.store.put_bytes(
        profileless_projection_bytes,
        artifacts.ArtifactWriteOptions(
            kind=projection_ref.kind,
            media_type=projection_ref.media_type,
            schema=projection_manifest.artifact_schema,
            inputs=list(
                chronology_contract._native_chronology_projection_manifest_input_refs(
                    profileless_projection
                )
            ),
            canon=projection_manifest.canon,
        ),
        return_selected_profile=True,
    )
    assert profileless_projection_ref is not None
    assert (
        current_service._requalify_persisted_native_projection(
            profileless_projection_ref, profileless_projection
        ).proof_result
        == projection.proof_result
    )

    revoked_config = current_config.model_copy(
        update={"revoked_key_ids": (unrelated.signer.key_id,)}
    )
    revoked_deployment = build_semantic_epoch_native_deployment(revoked_config)
    revoked_owner = revoked_deployment._state().chronology_policy_owner
    assert revoked_owner is not None
    revoked_service = epoch.SemanticEpochService(
        boundary_registry=case.service._boundary_registry,
        boundary_adapters=case.service._boundary_adapters,
        facet_registry=case.service._facet_registry,
        facet_provider=case.service._facet_provider,
        history=scenario.history,
        artifact_store=case.store,
        qualification_consumer=QualificationConsumer.from_deployment(
            revoked_deployment, runtime_artifact_store=case.store
        ),
        chronology_adapter=epoch.SemanticEpochQualificationAdapter(
            history=scenario.history,
            artifacts=case.store,
            policy_owner=revoked_owner,
        ),
    )
    assert isinstance(
        revoked_service.qualify_chronology_query(query=case.query),
        chronology_contract.NativeChronologyQualified,
    )
    with pytest.raises(ValueError):
        revoked_service._requalify_persisted_native_projection(projection_ref, projection)


def test_native_query_context_default_writer_profile_has_no_manifest_inputs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scenario = _real_epoch_scenario(tmp_path / "scenario")
    case = sign_native_epoch_scenario(scenario, tmp_path / "policy")
    native_query = chronology_contract.NativeChronologyQuery(
        domain=chronology_contract.ChronologyProofDomain(
            format=chronology_contract.FULL_PREFIX_FORMAT,
            profile=chronology_contract.FULL_PREFIX_PROFILE,
            proof_domain="semantic_epoch",
            family="epoch",
            scope_ref=scenario.query.scope_identity.scope_identity_ref,
            authority_purpose=scenario.query.authority_purpose,
        ),
        requested_cutoff_ref=scenario.prepared.stamp.epoch_ref,
        requested_query_context_ref=scenario.query.requested_query_context_ref,
    )
    candidate = case.adapter.reconcile_candidate(native_query)
    context_ref = candidate.query_context_artifact_ref
    manifest = case.store.get_manifest(context_ref)

    assert context_ref.manifest_profile_sha256 is None
    assert manifest.kind == "epoch.chronology_query_context"
    assert manifest.media_type == "application/vnd.polisyos.chronology-query+json"
    assert manifest.canon is None
    assert manifest.artifact_schema is None
    assert manifest.inputs == []
    selected_context_ref, decoded = epoch._load_owner_projection_mapping(case.store, context_ref)
    assert selected_context_ref.manifest_profile_sha256 is not None
    assert decoded == {}

    native_owner = case.deployment._state().chronology_policy_owner
    assert native_owner is not None
    owner_candidate = native_owner._native(native_query)[6]
    owner_context_ref = owner_candidate.query_context_artifact_ref
    assert owner_context_ref.manifest_profile_sha256 is None
    owner_selected_ref, owner_decoded = epoch._load_owner_projection_mapping(
        case.store, owner_context_ref
    )
    assert owner_selected_ref.manifest_profile_sha256 is not None
    assert owner_decoded == {}
    assert case.store.get_bytes(owner_context_ref) == case.store.get_bytes(context_ref)

    context_bytes = case.store.get_bytes(context_ref)
    dependency_ref = case.store.put_bytes(
        b"unrelated dependency",
        artifacts.ArtifactWriteOptions(
            kind="fixture.unrelated", media_type="application/octet-stream"
        ),
        return_selected_profile=True,
    )
    malformed_options = (
        artifacts.ArtifactWriteOptions(
            kind="epoch.chronology_query_context",
            media_type="application/vnd.polisyos.chronology-query+json",
            inputs=[
                artifacts.input_ref_from_artifact_ref(dependency_ref, role="unexpected_dependency")
            ],
        ),
        artifacts.ArtifactWriteOptions(
            kind="epoch.chronology_query_context",
            media_type="application/vnd.polisyos.chronology-query+json",
            canon=epoch_contract.epoch_canon_info(),
        ),
        artifacts.ArtifactWriteOptions(
            kind="epoch.chronology_query_context",
            media_type="application/vnd.polisyos.chronology-query+json",
            schema=artifacts.SchemaInfo(name="polisyos.epoch.QueryContext", version="1"),
        ),
    )
    malformed_refs = tuple(
        case.store.put_bytes(context_bytes, options, return_selected_profile=True)
        for options in malformed_options
    )
    payload_reads: list[str] = []
    original_verify = type(case.store).verify
    original_get_bytes = type(case.store).get_bytes

    def record_verify(instance: object, selector: object) -> object:
        payload_reads.append("verify")
        return original_verify(instance, selector)

    def record_get_bytes(instance: object, selector: object) -> bytes:
        payload_reads.append("get_bytes")
        return original_get_bytes(instance, selector)

    monkeypatch.setattr(type(case.store), "verify", record_verify)
    monkeypatch.setattr(type(case.store), "get_bytes", record_get_bytes)
    for malformed_ref in malformed_refs:
        with pytest.raises(
            ValueError, match="selected acquisition artifact manifest profile differs"
        ):
            epoch._load_owner_projection_mapping(case.store, malformed_ref)
    wrong_media_ref = case.store.put_bytes(
        context_bytes,
        artifacts.ArtifactWriteOptions(
            kind="epoch.chronology_query_context", media_type="application/json"
        ),
        return_selected_profile=True,
    )
    with pytest.raises(ValueError, match="no registered content resolver"):
        epoch._load_owner_projection_mapping(case.store, wrong_media_ref)
    assert payload_reads == []

    query_mapping = chronology_contract._raw_model_mapping(native_query)
    noncanonical_query_bytes = json.dumps(query_mapping, ensure_ascii=False).encode("utf-8")
    assert noncanonical_query_bytes != chronology_contract._canonical_raw_bytes(query_mapping)
    assert (
        chronology_contract.NativeChronologyQuery.model_validate_json(noncanonical_query_bytes)
        == native_query
    )
    invalid_payloads = (
        chronology_contract._frame_record(noncanonical_query_bytes),
        b"garbage",
        chronology_contract._canonical_raw_bytes(query_mapping),
        chronology_contract._frame_record(b"{}"),
        context_bytes[:-1],
        context_bytes + context_bytes,
        chronology_contract._frame_record(
            chronology_contract._canonical_raw_bytes(query_mapping | {"unexpected": "value"})
        ),
    )
    invalid_content_refs = tuple(
        case.store.put_bytes(
            payload,
            artifacts.ArtifactWriteOptions(
                kind="epoch.chronology_query_context",
                media_type="application/vnd.polisyos.chronology-query+json",
            ),
            return_selected_profile=True,
        )
        for payload in invalid_payloads
    )
    payload_reads.clear()
    for invalid_content_ref in invalid_content_refs:
        with pytest.raises(ValueError):
            epoch._load_owner_projection_mapping(case.store, invalid_content_ref)
    assert "verify" in payload_reads and "get_bytes" in payload_reads
