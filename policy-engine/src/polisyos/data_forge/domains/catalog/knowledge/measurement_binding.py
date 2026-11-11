"""Candidate-only checks from admitted Catalog measurements to model ports.

Catalog search and alignment can identify candidates, but this module compares
selected typed representations against the exact model-owned input interface.
It never grants execution, scientific equivalence, or source authority.
"""

from __future__ import annotations

import hashlib
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
    CanonicalAcquisitionObservation,
    CatalogAcquisitionOverlay,
    _resolve_fixed_unit_transform,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

    from polisyos.data_forge.domains.catalog.knowledge.overlay import (
        _CanonicalAuthority,
        _Passport,
    )


class _AssessmentRefusalError(ValueError):
    """Expected fail-closed result from a missing or mismatched selected input."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


_AssessmentRefusal = _AssessmentRefusalError


def assess_measurement_to_model_candidate(
    store: CoreJSONArtifactStore,
    overlay: CatalogAcquisitionOverlay,
    *,
    receipt_ref: ArtifactRef,
    passport: _Passport,
    authority: _CanonicalAuthority,
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
    except _AssessmentRefusal as exc:
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
            refusal_codes=(exc.code,),
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
    passport: _Passport,
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
    passport: _Passport,
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
    if boundary_statement.source_record_content_hash != passport.source_watermark:
        raise _AssessmentRefusal("source_boundary_record_watermark_mismatch")
    raw_body = _read_exact_selected_bytes(store, source_record_ref)
    try:
        source_selection = scoped_source_selection_from_passport_mapping(
            passport.model_dump(mode="json"),
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
            raw_body,
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


__all__ = ["assess_measurement_to_model_candidate"]
