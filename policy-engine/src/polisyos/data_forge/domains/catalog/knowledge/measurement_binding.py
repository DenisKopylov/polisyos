"""Candidate-only checks from admitted Catalog measurements to model ports.

Catalog search and alignment can identify candidates, but this module compares
selected typed representations against the exact model-owned input interface.
It never grants execution, scientific equivalence, or source authority.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING

from polisyos.core.artifacts import (
    ArtifactManifest,
    ArtifactRef,
    CoreJSONArtifactStore,
    PutOptions,
    SchemaInfo,
    artifact_manifest_profile_sha256,
    artifact_ref_identity_key,
    validate_core_model_json_artifact,
)
from polisyos.core.contracts import (
    FixedUnitTransformWitness,
    MeasurementAxis,
    MeasurementBindingProfile,
    MeasurementBindingProfileRef,
    MeasurementCorrespondenceResult,
    ScopedCorrespondenceBasis,
    ScopedCorrespondenceBasisRef,
    ScopedMeasurementOccurrence,
    ScopedMeasurementOccurrenceRef,
    ScopedSourceSelection,
    SelectedVariableBindingRef,
    VariableRepresentationRef,
    VariableSemanticDefinition,
    VariableSemanticDefinitionRef,
    epoch,
    evaluate_scoped_correspondence_basis,
    load_program_graph_input_interface,
    load_variable_representation,
    replay_scoped_measurement_occurrence,
    scoped_correspondence_basis_manifest_inputs,
    scoped_measurement_occurrence_manifest_inputs,
    scoped_source_selection_from_passport_mapping,
)
from polisyos.data_forge.domains.catalog.knowledge.overlay import (
    ActivatedAcquisitionObservationProjection,
    ActivatedAcquisitionPassport,
    CanonicalAcquisitionObservation,
    CatalogAcquisitionOverlay,
    MetricFieldBinding,
    OverlayAdmissionError,
    _resolve_fixed_unit_transform,
)

if TYPE_CHECKING:
    from polisyos.data_forge.domains.catalog.knowledge.acquisition_authority import (
        CanonicalAcquisitionAuthority,
    )


class _AssessmentRefusalError(ValueError):
    """Expected fail-closed result from a missing or mismatched selected input."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


_AssessmentRefusal = _AssessmentRefusalError


def materialize_activated_measurement_occurrence(
    store: CoreJSONArtifactStore,
    overlay: CatalogAcquisitionOverlay,
    *,
    receipt_ref: ArtifactRef,
    passport: ActivatedAcquisitionPassport,
    authority: CanonicalAcquisitionAuthority,
    observation_id: str,
) -> ScopedMeasurementOccurrenceRef:
    """Persist one exact row from the activation owner's current admitted view.

    The producer reopens the selected activation through the Catalog overlay,
    then replays and persists only the row occurrence and its source lineage.
    It does not select a model port or assert semantic correspondence,
    independence, source currentness, or publication authority.

    Args:
        store: Core JSON artifact store shared by the Catalog owner.
        overlay: Canonical reader for active Catalog acquisition epochs.
        receipt_ref: Exact selected activation receipt to reopen.
        passport: Structural view supplied by the Catalog's active passport owner.
        authority: Canonical source-admission authority used by that owner.
        observation_id: Exact row ID from the active projection.

    Returns:
        ScopedMeasurementOccurrenceRef: Persisted occurrence and exact source refs.

    Raises:
        ValueError: If the selected row, activation, or source replay is invalid.
        OverlayAdmissionError: If the activation owner cannot revalidate admission.
    """
    if not observation_id.strip():
        raise _AssessmentRefusal("selected_observation_missing")
    projection = overlay.read_activated_semantic_epoch_observations(
        receipt_ref=receipt_ref,
        artifact_store=store,
        passport=passport,
        authority=authority,
    )
    projection = ActivatedAcquisitionObservationProjection.model_validate(
        projection.model_dump(mode="json")
    )
    row_matches = tuple(
        row for row in projection.observations if row.observation.observation_id == observation_id
    )
    if len(row_matches) != 1:
        raise _AssessmentRefusal("selected_observation_not_unique")
    observation_row = row_matches[0]
    observation = observation_row.observation
    _reopen_activation_evidence(store, projection, receipt_ref=receipt_ref, passport=passport)

    binding = passport.registration.field_binding
    expected_transform = (
        None if binding.unit_transform == "identity" else _resolve_fixed_unit_transform(binding)
    )
    if observation.unit_transform_evidence != expected_transform:
        raise _AssessmentRefusal("observation_unit_transform_evidence_mismatch")
    _source_selection, replayed_occurrence = _materialize_occurrence(
        store,
        projection=projection,
        observation=observation,
        observation_content_sha256=observation_row.row_content_sha256,
        receipt_ref=receipt_ref,
        passport=passport,
        expected_transform=expected_transform,
    )
    return _persist_occurrence(store, replayed_occurrence)


def replay_selected_scoped_measurement_facts(
    store: CoreJSONArtifactStore,
    occurrence_ref: ScopedMeasurementOccurrenceRef,
) -> tuple[ScopedMeasurementOccurrence, ScopedMeasurementOccurrence, ScopedSourceSelection]:
    """Reopen and replay selected CAS facts without claiming activation currentness.

    This read path verifies the stored occurrence, its exact manifest inputs,
    selected receipt/passport/boundary/source-record lineage, and the registered
    fixed-unit transform before replaying the source row. It reads only the
    selected CAS artifacts; it does not consult the mutable Catalog overlay or
    assert that the activation remains current.

    Args:
        store: Core JSON artifact store containing the selected artifacts.
        occurrence_ref: Exact selected occurrence to reconstruct from its sources.

    Returns:
        tuple: Stored occurrence, independently replayed occurrence, and
            passport-derived source selection.

    Raises:
        ValueError: If any selected occurrence or source fact cannot be reopened.
    """
    try:
        selected_occurrence_ref = _selected_exact_ref(store, occurrence_ref)
        occurrence = validate_core_model_json_artifact(
            ScopedMeasurementOccurrence, store, selected_occurrence_ref
        )
        if tuple(store.get_manifest(selected_occurrence_ref).inputs) != (
            scoped_measurement_occurrence_manifest_inputs(occurrence)
        ):
            raise _AssessmentRefusal("occurrence_lineage_mismatch")

        receipt_mapping = epoch.load_verified_epoch_statement(
            store=store,
            ref=occurrence.source_receipt_ref,
            expected_kind="epoch.activated_overlay_admission_receipt",
        )
        receipt = epoch.ActivatedOverlayAdmissionStatement.model_validate(receipt_mapping)
        if receipt.admitted_boundary_evidence_ref.manifest_profile_sha256 is None:
            raise _AssessmentRefusal("source_profile_required")
        boundary_mapping = epoch.load_verified_epoch_statement(
            store=store,
            ref=receipt.admitted_boundary_evidence_ref,
            expected_kind="epoch.admitted_acquisition_boundary_evidence",
        )
        boundary = epoch.AdmittedAcquisitionBoundaryEvidence.model_validate(boundary_mapping)
        passport_mapping = epoch.load_verified_epoch_statement(
            store=store,
            ref=occurrence.source_passport_ref,
            expected_kind="epoch.acquisition_passport_snapshot",
        )
        candidate_mapping = epoch.load_verified_epoch_statement(
            store=store,
            ref=occurrence.source_boundary_candidate_ref,
            expected_kind="epoch.acquisition_semantic_boundary_candidate",
        )
        candidate = epoch.AcquisitionSemanticBoundaryCandidateStatement.model_validate(
            candidate_mapping
        )
        source_selection = scoped_source_selection_from_passport_mapping(
            passport_mapping,
            source_receipt_ref=occurrence.source_receipt_ref,
            source_passport_ref=occurrence.source_passport_ref,
            source_boundary_candidate_ref=occurrence.source_boundary_candidate_ref,
            source_record_ref=occurrence.source_record_ref,
        )
        if (
            receipt.epoch_id != source_selection.epoch_id
            or receipt.passport_id != source_selection.passport_id
            or receipt.observation_class != source_selection.observation_class
            or boundary.epoch_id != receipt.epoch_id
            or boundary.semantic_epoch_stamp != receipt.semantic_epoch_stamp
            or artifact_ref_identity_key(boundary.passport_ref)
            != artifact_ref_identity_key(source_selection.source_passport_ref)
            or boundary.passport_content_hash != _sha256_mapping(passport_mapping)
            or artifact_ref_identity_key(boundary.semantic_candidate_ref)
            != artifact_ref_identity_key(source_selection.source_boundary_candidate_ref)
            or boundary.semantic_candidate_content_hash
            != epoch.acquisition_semantic_candidate_content_hash(candidate)
            or artifact_ref_identity_key(candidate.source_record_ref)
            != artifact_ref_identity_key(source_selection.source_record_ref)
            or candidate.source_record_content_hash
            != str(source_selection.source_record_ref.artifact_id)
        ):
            raise _AssessmentRefusal("source_owner_mismatch")

        registration = passport_mapping.get("registration")
        if not isinstance(registration, Mapping):
            raise _AssessmentRefusal("source_registration_missing")
        binding_mapping = registration.get("field_binding")
        if not isinstance(binding_mapping, Mapping):
            raise _AssessmentRefusal("source_field_binding_missing")
        binding = MetricFieldBinding.model_validate(binding_mapping)
        expected_transform = (
            None if binding.unit_transform == "identity" else _resolve_fixed_unit_transform(binding)
        )
        witness = (
            None
            if expected_transform is None
            else FixedUnitTransformWitness.model_validate(
                expected_transform.model_dump(mode="json")
            )
        )
        if occurrence.unit_transform_evidence != witness:
            raise _AssessmentRefusal("occurrence_transform_mismatch")
        replayed = replay_scoped_measurement_occurrence(
            read_scoped_measurement_source_body(
                store,
                passport_mapping=passport_mapping,
                source_selection=source_selection,
            ),
            observation_id=occurrence.observation_id,
            source_selection=source_selection,
            unit_transform_evidence=witness,
        )
        return occurrence, replayed, source_selection
    except (_AssessmentRefusal, OverlayAdmissionError):
        raise
    except (FileNotFoundError, OSError, TypeError, ValueError) as exc:
        raise _AssessmentRefusal("selected_occurrence_source_replay_failed") from exc


def assess_measurement_to_model_candidate(
    store: CoreJSONArtifactStore,
    overlay: CatalogAcquisitionOverlay,
    *,
    receipt_ref: ArtifactRef,
    passport: ActivatedAcquisitionPassport,
    authority: CanonicalAcquisitionAuthority,
    observation_id: str,
    source_definition_ref: VariableSemanticDefinitionRef,
    source_representation_ref: VariableRepresentationRef,
    model_interface_ref: SelectedVariableBindingRef,
    port_id: str,
) -> MeasurementCorrespondenceResult:
    """Reopen admitted source and selected model artifacts, then assess one candidate.

    The function re-reads the Catalog activation through its current owner,
    verifies the selected receipt/passport bytes and source identities, and
    reopens the selected model input interface through its owner. A positive
    result means only that the bounded typed predicates agree; independent
    empirical correspondence and source currentness remain unestablished.

    Args:
        store: Existing Core JSON artifact store shared with Catalog and Runtime.
        overlay: Existing read owner for the admitted Catalog acquisition overlay.
        receipt_ref: Exact selected activation receipt for the source acquisition.
        passport: The Catalog passport supplied by its existing owner.
        authority: The source-admission authority supplied by its existing owner.
        observation_id: Exact active observation row to assess.
        source_definition_ref: Selected semantic definition for that Catalog row.
        source_representation_ref: Selected representation for that Catalog row.
        model_interface_ref: Exact selected ProgramGraph input-interface reference.
        port_id: Unique model-owned port inside that selected interface.
    Returns:
        MeasurementCorrespondenceResult: Candidate or refusal with explicit limitations.
    """
    source_observation_id = observation_id or "unknown"
    model_port_id = port_id or "unknown"
    target_definition_ref: VariableSemanticDefinitionRef | None = None
    target_representation_ref: VariableRepresentationRef | None = None
    profile_ref: MeasurementBindingProfileRef | None = None
    try:
        if not observation_id.strip() or not port_id.strip():
            raise _AssessmentRefusal("selected_observation_or_port_missing")

        projection = overlay.read_activated_semantic_epoch_observations(
            receipt_ref=receipt_ref,
            artifact_store=store,
            passport=passport,
            authority=authority,
        )
        projection = ActivatedAcquisitionObservationProjection.model_validate(
            projection.model_dump(mode="json")
        )
        row_matches = tuple(
            row
            for row in projection.observations
            if row.observation.observation_id == observation_id
        )
        if len(row_matches) != 1:
            raise _AssessmentRefusal("selected_observation_not_unique")
        observation_row = row_matches[0]
        observation = observation_row.observation

        _reopen_activation_evidence(store, projection, receipt_ref=receipt_ref, passport=passport)
        source_definition = validate_core_model_json_artifact(
            VariableSemanticDefinition, store, source_definition_ref
        )
        source_representation = load_variable_representation(store, source_representation_ref)
        interface = load_program_graph_input_interface(store, model_interface_ref)
        selected_ports = tuple(port for port in interface.ports if port.port_id == port_id)
        if len(selected_ports) != 1:
            raise _AssessmentRefusal("selected_model_port_not_unique")
        port = selected_ports[0]
        target_definition_ref = port.semantic_definition_ref
        target_representation_ref = port.representation_ref
        profile_ref = port.binding_profile_ref
        target_definition = validate_core_model_json_artifact(
            VariableSemanticDefinition, store, target_definition_ref
        )
        target_representation = load_variable_representation(store, target_representation_ref)
        profile = validate_core_model_json_artifact(MeasurementBindingProfile, store, profile_ref)
        _reopen_definition_evidence(store, source_definition)

        binding = passport.registration.field_binding
        expected_transform = (
            None if binding.unit_transform == "identity" else _resolve_fixed_unit_transform(binding)
        )
        if observation.unit_transform_evidence != expected_transform:
            raise _AssessmentRefusal("observation_unit_transform_evidence_mismatch")
        source_selection, replayed_occurrence = _materialize_occurrence(
            store,
            projection=projection,
            observation=observation,
            observation_content_sha256=observation_row.row_content_sha256,
            receipt_ref=receipt_ref,
            passport=passport,
            expected_transform=expected_transform,
        )
        occurrence_ref = _persist_occurrence(store, replayed_occurrence)
        occurrence = validate_core_model_json_artifact(
            ScopedMeasurementOccurrence, store, occurrence_ref
        )
        basis = ScopedCorrespondenceBasis(
            profile_id="measurement_to_model.same_definition.v1",
            occurrence_ref=occurrence_ref,
            source_definition_ref=source_definition_ref,
            source_representation_ref=source_representation_ref,
            source_definition_evidence_refs=source_definition.definition_evidence_refs,
            model_interface_ref=SelectedVariableBindingRef.model_validate(
                _selected_exact_ref(store, model_interface_ref).model_dump(mode="json")
            ),
            model_port_id=port_id,
            target_definition_ref=target_definition_ref,
            target_representation_ref=target_representation_ref,
            binding_profile_ref=profile_ref,
            scope=port.scope,
        )
        evaluation = evaluate_scoped_correspondence_basis(
            basis=basis,
            occurrence_ref=occurrence_ref,
            occurrence=occurrence,
            replayed_occurrence=replayed_occurrence,
            source_selection=source_selection,
            source_definition_ref=source_definition_ref,
            source_definition=source_definition,
            source_representation_ref=source_representation_ref,
            source_representation=source_representation,
            target_definition_ref=target_definition_ref,
            target_definition=target_definition,
            target_representation_ref=target_representation_ref,
            target_representation=target_representation,
            binding_profile_ref=profile_ref,
            profile=profile,
            model_interface_ref=basis.model_interface_ref,
            model_port=port,
        )
        if evaluation.status == "refused":
            return _result(
                source_observation_id=observation_id,
                source_definition_ref=source_definition_ref,
                source_representation_ref=source_representation_ref,
                model_interface_ref=model_interface_ref,
                model_port_id=port_id,
                status="refused",
                target_definition_ref=target_definition_ref,
                target_representation_ref=target_representation_ref,
                binding_profile_ref=profile_ref,
                occurrence_ref=occurrence_ref,
                recomputed_axes=evaluation.recomputed_axes,
                optional_unknown_axes=evaluation.optional_unknown_axes,
                refusal_codes=evaluation.refusal_codes,
            )
        basis_ref = _persist_correspondence_basis(store, basis)
        return _result(
            source_observation_id=observation_id,
            source_definition_ref=source_definition_ref,
            source_representation_ref=source_representation_ref,
            model_interface_ref=model_interface_ref,
            model_port_id=port_id,
            status="candidate",
            target_definition_ref=target_definition_ref,
            target_representation_ref=target_representation_ref,
            binding_profile_ref=profile_ref,
            occurrence_ref=occurrence_ref,
            correspondence_basis_ref=basis_ref,
            recomputed_axes=evaluation.recomputed_axes,
            optional_unknown_axes=evaluation.optional_unknown_axes,
            limitation_codes=evaluation.limitation_codes,
            refusal_codes=(),
            semantic_correspondence="recomputed",
        )
    except (_AssessmentRefusal, OverlayAdmissionError) as exc:
        refusal_code = (
            f"source_activation_{exc.code}" if isinstance(exc, OverlayAdmissionError) else exc.code
        )
        return _result(
            source_observation_id=source_observation_id,
            source_definition_ref=source_definition_ref,
            source_representation_ref=source_representation_ref,
            model_interface_ref=model_interface_ref,
            model_port_id=model_port_id,
            status="refused",
            target_definition_ref=target_definition_ref,
            target_representation_ref=target_representation_ref,
            binding_profile_ref=profile_ref,
            refusal_codes=(refusal_code,),
        )
    except (OSError, TypeError, ValueError):
        return _result(
            source_observation_id=source_observation_id,
            source_definition_ref=source_definition_ref,
            source_representation_ref=source_representation_ref,
            model_interface_ref=model_interface_ref,
            model_port_id=model_port_id,
            status="refused",
            target_definition_ref=target_definition_ref,
            target_representation_ref=target_representation_ref,
            binding_profile_ref=profile_ref,
            refusal_codes=("selected_owner_input_invalid",),
        )


def _reopen_activation_evidence(
    store: CoreJSONArtifactStore,
    projection: ActivatedAcquisitionObservationProjection,
    *,
    receipt_ref: ArtifactRef,
    passport: ActivatedAcquisitionPassport,
) -> None:
    """Reopen selected receipt/passport bytes and reconcile their exact owner identities."""

    selected_receipt_ref = _selected_exact_ref(store, receipt_ref)
    projected_receipt_ref = _selected_exact_ref(store, projection.receipt_ref)
    if artifact_ref_identity_key(selected_receipt_ref) != artifact_ref_identity_key(
        projected_receipt_ref
    ):
        raise _AssessmentRefusal("activation_receipt_input_mismatch")

    receipt_mapping = epoch.load_verified_epoch_statement(
        store=store,
        ref=selected_receipt_ref,
        expected_kind="epoch.activated_overlay_admission_receipt",
    )
    receipt = epoch.ActivatedOverlayAdmissionStatement.model_validate(receipt_mapping)
    if (
        _sha256_mapping(receipt_mapping) != projection.receipt_content_sha256
        or receipt.epoch_id != projection.epoch_id
        or receipt.passport_id != projection.passport_id
        or receipt.admission_content_sha256 != projection.admission_content_sha256
        or receipt.admitted_observation_count != len(projection.observations)
        or receipt.activation_state != "active"
    ):
        raise _AssessmentRefusal("activation_receipt_identity_mismatch")

    boundary_ref = _selected_exact_ref(store, receipt.admitted_boundary_evidence_ref)
    boundary_mapping = epoch.load_verified_epoch_statement(
        store=store,
        ref=boundary_ref,
        expected_kind="epoch.admitted_acquisition_boundary_evidence",
    )
    boundary = epoch.AdmittedAcquisitionBoundaryEvidence.model_validate(boundary_mapping)
    if artifact_ref_identity_key(_selected_exact_ref(store, boundary.passport_ref)) != (
        artifact_ref_identity_key(_selected_exact_ref(store, projection.passport_ref))
    ):
        raise _AssessmentRefusal("activation_passport_reference_mismatch")
    passport_mapping = epoch.load_verified_epoch_statement(
        store=store,
        ref=_selected_exact_ref(store, projection.passport_ref),
        expected_kind="epoch.acquisition_passport_snapshot",
    )
    if (
        _sha256_mapping(passport_mapping) != projection.passport_content_sha256
        or boundary.passport_content_hash != projection.passport_content_sha256
        or passport_mapping.get("passport_id") != projection.passport_id
        or passport_mapping.get("epoch_id") != projection.epoch_id
        or passport_mapping.get("variable_id") != projection.variable_id
        or passport.model_dump(mode="json") != passport_mapping
    ):
        raise _AssessmentRefusal("activation_passport_identity_mismatch")


def _reopen_definition_evidence(
    store: CoreJSONArtifactStore,
    source: VariableSemanticDefinition,
) -> None:
    """Resolve exact source documentation refs bound by the shared definition."""

    if not source.definition_evidence_refs:
        raise _AssessmentRefusal("source_definition_documentation_missing")
    for ref in source.definition_evidence_refs:
        _read_exact_selected_bytes(store, ref)


def _read_exact_selected_bytes(store: CoreJSONArtifactStore, ref: ArtifactRef) -> bytes:
    selected_ref = _selected_exact_ref(store, ref)
    try:
        manifest = store.get_manifest(selected_ref)
        raw = store.get_bytes(selected_ref)
    except (FileNotFoundError, OSError, ValueError) as exc:
        raise _AssessmentRefusal("evidence_bytes_unavailable") from exc
    manifest_ref = _manifest_selected_ref(manifest)
    if (
        artifact_ref_identity_key(manifest_ref) != artifact_ref_identity_key(selected_ref)
        or hashlib.sha256(raw).hexdigest() != selected_ref.artifact_id.hex
    ):
        raise _AssessmentRefusal("evidence_bytes_identity_mismatch")
    return raw


def _selected_exact_ref(store: CoreJSONArtifactStore, ref: ArtifactRef) -> ArtifactRef:
    """Bind a ref to the exact manifest profile returned by its current CAS owner."""

    try:
        manifest = store.get_manifest(ref)
    except (FileNotFoundError, OSError, ValueError) as exc:
        raise _AssessmentRefusal("selected_manifest_unavailable") from exc
    manifest_ref = _manifest_selected_ref(manifest)
    actual_profile_sha256 = manifest_ref.manifest_profile_sha256
    if (
        str(manifest_ref.artifact_id) != str(ref.artifact_id)
        or manifest_ref.kind != ref.kind
        or manifest_ref.media_type != ref.media_type
        or (
            ref.manifest_profile_sha256 is not None
            and ref.manifest_profile_sha256 != actual_profile_sha256
        )
    ):
        raise _AssessmentRefusal("selected_manifest_identity_mismatch")
    return manifest_ref


def read_scoped_measurement_source_body(
    store: CoreJSONArtifactStore,
    *,
    passport_mapping: Mapping[str, object],
    source_selection: ScopedSourceSelection,
) -> bytes:
    """Reopen the source carriers and replay the exact measurement-row bytes.

    Local sources use their selected raw JSON directly. A live source binds a
    selected raw HTTP carrier and a separate selected Fabric cached result.
    The latter is decoded only for the admitted JSON/Parquet formats, and the
    existing connector normalizer is replayed against the captured raw rows.
    This establishes source-content identity, not currentness or publication
    authority.
    """
    source_ref = source_selection.source_record_ref
    selected_body = _read_exact_selected_bytes(store, source_ref)
    live_mapping = passport_mapping.get("live_source_execution")
    if live_mapping is None:
        if (
            source_selection.measured_source_body_sha256 is not None
            or "sha256:" + hashlib.sha256(selected_body).hexdigest()
            != source_selection.source_watermark
        ):
            raise ValueError("scoped_source_local_carrier_mismatch")
        source_entry = passport_mapping.get("source_authority_entry")
        if source_entry is not None:
            if not isinstance(source_entry, Mapping):
                raise ValueError("scoped_source_declaration_carrier_invalid")
            from polisyos.data_forge.domains.catalog.knowledge.acquisition_authority import (
                AcquisitionAuthorityEntry,
                verify_declared_source_geography,
            )

            registration = passport_mapping.get("registration")
            if not isinstance(registration, Mapping) or not isinstance(
                registration.get("connector_id"), str
            ):
                raise ValueError("scoped_source_registration_missing")
            verify_declared_source_geography(
                AcquisitionAuthorityEntry.model_validate(dict(source_entry)),
                connector_id=registration["connector_id"],
                raw_body=selected_body,
            )
        return selected_body
    if not isinstance(live_mapping, Mapping):
        raise ValueError("scoped_source_live_carrier_untyped")

    import pandas as pd

    from polisyos.core.canon import from_canonical_bytes
    from polisyos.core.contracts import DataSnapshot, EvidenceBundle
    from polisyos.data_forge.domains.catalog.knowledge.acquisition_authority import (
        AcquisitionAuthorityEntry,
        LiveSourceExecutionEvidence,
        _live_normalized_coordinates_match,
        normalized_acquisition_source_body,
        read_selected_live_raw_source,
        verify_declared_source_geography,
    )
    from polisyos.fabric.connectors import (
        ResultSerializer,
        get_registry,
        normalize_worldbank_records,
        verify_selected_cache_payload_writer_profile,
    )
    from polisyos.fabric.data_plane import verify_live_ingestion_snapshot_profile
    from polisyos.fabric.ingestion import verify_live_ingestion_evidence_profile

    proof = LiveSourceExecutionEvidence.model_validate(dict(live_mapping))
    raw_ref = proof.raw_artifact_ref
    registration = passport_mapping.get("registration")
    if (
        raw_ref is None
        or not isinstance(registration, Mapping)
        or registration.get("connector_id") != proof.authorization.connector_id
        or proof.authorization.connector_id != "worldbank.wdi"
        or proof.authorization.request_variables != (registration.get("request_dataset_id"),)
        or str(proof.raw_artifact_id) != source_selection.source_watermark
        or proof.raw_body_sha256 != source_selection.source_watermark
        or str(proof.normalized_data_artifact_id) != str(source_ref.artifact_id)
        or source_ref.kind != "connector_cache.payload"
        or source_ref.media_type
        not in {
            "application/vnd.polisyos.cached-result+application/json",
            "application/vnd.polisyos.cached-result+application/parquet",
        }
    ):
        raise ValueError("scoped_source_live_carrier_mismatch")
    raw_body = read_selected_live_raw_source(store, raw_ref)
    if "sha256:" + hashlib.sha256(raw_body).hexdigest() != source_selection.source_watermark:
        raise ValueError("scoped_source_live_raw_content_mismatch")

    snapshot_bytes = _read_exact_selected_bytes(store, proof.data_snapshot_ref)
    snapshot = validate_core_model_json_artifact(
        DataSnapshot,
        store,
        proof.data_snapshot_ref,
        raw_payload_bytes=snapshot_bytes,
    )
    bundle = EvidenceBundle.model_validate(
        from_canonical_bytes(_read_exact_selected_bytes(store, proof.evidence_bundle_ref))
    )
    if (
        artifact_ref_identity_key(snapshot.data_ref) != artifact_ref_identity_key(source_ref)
        or snapshot.evidence_ref is None
        or artifact_ref_identity_key(snapshot.evidence_ref)
        != artifact_ref_identity_key(proof.evidence_bundle_ref)
        or len(bundle.sources) != 1
        or artifact_ref_identity_key(bundle.sources[0]) != artifact_ref_identity_key(source_ref)
    ):
        raise ValueError("scoped_source_live_snapshot_mismatch")
    verify_live_ingestion_snapshot_profile(store, proof.data_snapshot_ref, snapshot)
    verify_live_ingestion_evidence_profile(store, proof.evidence_bundle_ref, bundle)
    try:
        metadata = get_registry().get_metadata(proof.authorization.connector_id)
        cache_profile_matches = verify_selected_cache_payload_writer_profile(
            store,
            source_ref,
            connector_id=proof.authorization.connector_id,
            dataset_id=str(registration["request_dataset_id"]),
            classification=metadata.data_classification,
            column_classification=metadata.column_classification,
        )
    except Exception as exc:
        raise ValueError("scoped_source_live_normalized_writer_profile_unavailable") from exc
    if not cache_profile_matches:
        raise ValueError("scoped_source_live_normalized_writer_profile_mismatch")

    # Reject unsupported envelopes before the shared decoder can reach its
    # separate pickle fallback, regardless of the outer manifest's media type.
    if len(selected_body) < 4:
        raise ValueError("scoped_source_live_envelope_invalid")
    envelope_length = int.from_bytes(selected_body[:4], "big")
    if envelope_length <= 0 or envelope_length > len(selected_body) - 4:
        raise ValueError("scoped_source_live_envelope_invalid")
    envelope = from_canonical_bytes(selected_body[4 : 4 + envelope_length])
    if (
        not isinstance(envelope, Mapping)
        or envelope.get("data_media_type") not in {"application/json", "application/parquet"}
        or source_ref.media_type
        != "application/vnd.polisyos.cached-result+" + str(envelope.get("data_media_type"))
    ):
        raise ValueError("scoped_source_live_envelope_unsupported")
    result = ResultSerializer.deserialize(selected_body)
    replay_bytes, replay_media = ResultSerializer.serialize(result)
    if (
        replay_bytes != selected_body
        or replay_media != source_ref.media_type
        or result.version.content_hash != source_selection.source_watermark
    ):
        raise ValueError("scoped_source_live_result_identity_mismatch")

    raw_payload = json.loads(raw_body)
    if (
        not isinstance(raw_payload, list)
        or len(raw_payload) < 2
        or not isinstance(raw_payload[1], list)
        or any(not isinstance(row, Mapping) for row in raw_payload[1])
    ):
        raise ValueError("scoped_source_live_raw_rows_invalid")
    source_entry = passport_mapping.get("source_authority_entry")
    if source_entry is not None:
        if not isinstance(source_entry, Mapping):
            raise ValueError("scoped_source_declaration_carrier_invalid")
        verify_declared_source_geography(
            AcquisitionAuthorityEntry.model_validate(dict(source_entry)),
            connector_id=proof.authorization.connector_id,
            raw_body=raw_body,
        )
    expected = normalize_worldbank_records(raw_payload[1], str(registration["request_dataset_id"]))
    registered_countries = registration.get("country_codes")
    if (
        not isinstance(registered_countries, Sequence)
        or isinstance(registered_countries, (str, bytes, bytearray))
        or any(not isinstance(value, str) for value in registered_countries)
        or not _live_normalized_coordinates_match(
            expected.to_dict(orient="records"),
            indicator_id=str(registration["request_dataset_id"]),
            country_codes=registered_countries,
        )
    ):
        raise ValueError("scoped_source_live_coordinate_mismatch")
    actual = result.data
    if isinstance(actual, pd.DataFrame):
        actual_frame = actual
    elif isinstance(actual, Sequence) and not isinstance(actual, (str, bytes, bytearray)):
        actual_frame = pd.DataFrame(actual)
    else:
        raise ValueError("scoped_source_live_result_unsupported")
    if (
        list(actual_frame.columns) != list(expected.columns)
        or not actual_frame.reset_index(drop=True).equals(expected.reset_index(drop=True))
        or result.row_count != len(expected)
    ):
        raise ValueError("scoped_source_live_normalized_projection_mismatch")
    rows_body = normalized_acquisition_source_body(result)
    if (
        source_selection.measured_source_body_sha256 is None
        or "sha256:" + hashlib.sha256(rows_body).hexdigest()
        != source_selection.measured_source_body_sha256
    ):
        raise ValueError("scoped_source_live_measured_content_mismatch")
    return rows_body


def _manifest_selected_ref(manifest: ArtifactManifest) -> ArtifactRef:
    """Reconstruct a manifest's exact selected ref using the canonical profile digest."""

    return ArtifactRef(
        artifact_id=manifest.artifact_id,
        kind=manifest.kind,
        media_type=manifest.media_type,
        manifest_profile_sha256=artifact_manifest_profile_sha256(manifest),
    )


def _materialize_occurrence(
    store: CoreJSONArtifactStore,
    *,
    projection: ActivatedAcquisitionObservationProjection,
    observation: CanonicalAcquisitionObservation,
    observation_content_sha256: str,
    receipt_ref: ArtifactRef,
    passport: ActivatedAcquisitionPassport,
    expected_transform: object,
) -> tuple[ScopedSourceSelection, ScopedMeasurementOccurrence]:
    """Build the occurrence only after replaying its exact admitted source bytes."""

    selected_receipt = _selected_exact_ref(store, receipt_ref)
    selected_passport = _selected_exact_ref(store, projection.passport_ref)
    boundary_ref = _selected_exact_ref(store, passport.semantic_boundary_candidate_ref)
    boundary_mapping = epoch.load_verified_epoch_statement(
        store=store,
        ref=boundary_ref,
        expected_kind="epoch.acquisition_semantic_boundary_candidate",
    )
    boundary_statement = epoch.AcquisitionSemanticBoundaryCandidateStatement.model_validate(
        boundary_mapping
    )
    source_record_ref = _selected_exact_ref(store, boundary_statement.source_record_ref)
    if boundary_statement.source_record_content_hash != str(source_record_ref.artifact_id):
        raise _AssessmentRefusal("source_boundary_record_watermark_mismatch")
    try:
        passport_mapping = passport.model_dump(mode="json")
        source_selection = scoped_source_selection_from_passport_mapping(
            passport_mapping,
            source_receipt_ref=SelectedVariableBindingRef.model_validate(
                selected_receipt.model_dump(mode="json")
            ),
            source_passport_ref=SelectedVariableBindingRef.model_validate(
                selected_passport.model_dump(mode="json")
            ),
            source_boundary_candidate_ref=SelectedVariableBindingRef.model_validate(
                boundary_ref.model_dump(mode="json")
            ),
            source_record_ref=SelectedVariableBindingRef.model_validate(
                source_record_ref.model_dump(mode="json")
            ),
        )
        witness = (
            None
            if expected_transform is None
            else FixedUnitTransformWitness.model_validate(
                expected_transform.model_dump(mode="json")
            )
        )
        replayed = replay_scoped_measurement_occurrence(
            read_scoped_measurement_source_body(
                store, passport_mapping=passport_mapping, source_selection=source_selection
            ),
            observation_id=observation.observation_id,
            source_selection=source_selection,
            unit_transform_evidence=witness,
        )
    except (TypeError, ValueError) as exc:
        raise _AssessmentRefusal("source_occurrence_replay_failed") from exc
    if (
        replayed.observation_content_sha256 != observation_content_sha256
        or replayed.observation_id != observation.observation_id
        or replayed.canonical_value != str(observation.value)
    ):
        raise _AssessmentRefusal("source_occurrence_replay_mismatch")
    return source_selection, replayed


def _persist_occurrence(
    store: CoreJSONArtifactStore,
    occurrence: ScopedMeasurementOccurrence,
) -> ScopedMeasurementOccurrenceRef:
    """Persist and immediately reopen the exact source occurrence and lineage."""

    inputs = list(scoped_measurement_occurrence_manifest_inputs(occurrence))
    raw_ref = store.put_json(
        occurrence,
        PutOptions(
            kind=occurrence.ARTIFACT_KIND,
            media_type=occurrence.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(
                name=occurrence.ARTIFACT_SCHEMA_NAME,
                version=occurrence.ARTIFACT_SCHEMA_VERSION,
            ),
            inputs=inputs,
        ),
        return_selected_profile=True,
    )
    selected_ref = ScopedMeasurementOccurrenceRef.model_validate(raw_ref.model_dump(mode="json"))
    loaded = validate_core_model_json_artifact(ScopedMeasurementOccurrence, store, selected_ref)
    if loaded != occurrence or store.get_manifest(selected_ref).inputs != inputs:
        raise _AssessmentRefusal("measurement_occurrence_readback_mismatch")
    return selected_ref


def _persist_correspondence_basis(
    store: CoreJSONArtifactStore,
    basis: ScopedCorrespondenceBasis,
) -> ScopedCorrespondenceBasisRef:
    """Persist the exact selected same-definition relation and direct lineage."""

    inputs = list(scoped_correspondence_basis_manifest_inputs(basis))
    raw_ref = store.put_json(
        basis,
        PutOptions(
            kind=basis.ARTIFACT_KIND,
            media_type=basis.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(
                name=basis.ARTIFACT_SCHEMA_NAME,
                version=basis.ARTIFACT_SCHEMA_VERSION,
            ),
            inputs=inputs,
        ),
        return_selected_profile=True,
    )
    selected_ref = ScopedCorrespondenceBasisRef.model_validate(raw_ref.model_dump(mode="json"))
    loaded = validate_core_model_json_artifact(ScopedCorrespondenceBasis, store, selected_ref)
    if loaded != basis or store.get_manifest(selected_ref).inputs != inputs:
        raise _AssessmentRefusal("correspondence_basis_readback_mismatch")
    return selected_ref


def _sha256_mapping(value: Mapping[str, object]) -> str:
    from polisyos.fabric.data_plane import content_sha256

    return content_sha256(value)


def _result(
    *,
    source_observation_id: str,
    source_definition_ref: VariableSemanticDefinitionRef,
    source_representation_ref: VariableRepresentationRef,
    model_interface_ref: ArtifactRef,
    model_port_id: str,
    status: str,
    target_definition_ref: VariableSemanticDefinitionRef | None = None,
    target_representation_ref: VariableRepresentationRef | None = None,
    binding_profile_ref: MeasurementBindingProfileRef | None = None,
    occurrence_ref: ScopedMeasurementOccurrenceRef | None = None,
    correspondence_basis_ref: ScopedCorrespondenceBasisRef | None = None,
    recomputed_axes: tuple[MeasurementAxis, ...] = (),
    optional_unknown_axes: tuple[MeasurementAxis, ...] = (),
    limitation_codes: tuple[str, ...] = (),
    refusal_codes: tuple[str, ...] = (),
    semantic_correspondence: str = "not_established",
) -> MeasurementCorrespondenceResult:
    return MeasurementCorrespondenceResult(
        status=status,
        source_observation_id=source_observation_id,
        source_definition_ref=source_definition_ref,
        source_representation_ref=source_representation_ref,
        model_interface_ref=model_interface_ref,
        model_port_id=model_port_id,
        target_definition_ref=target_definition_ref,
        target_representation_ref=target_representation_ref,
        binding_profile_ref=binding_profile_ref,
        occurrence_ref=occurrence_ref,
        correspondence_basis_ref=correspondence_basis_ref,
        recomputed_axes=recomputed_axes,
        optional_unknown_axes=optional_unknown_axes,
        limitation_codes=limitation_codes,
        refusal_codes=refusal_codes,
        semantic_correspondence=semantic_correspondence,
    )


__all__ = [
    "assess_measurement_to_model_candidate",
    "materialize_activated_measurement_occurrence",
    "read_scoped_measurement_source_body",
    "replay_selected_scoped_measurement_facts",
]
