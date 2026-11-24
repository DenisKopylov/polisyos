"""Candidate-only checks from admitted Catalog measurements to model ports.

Catalog search and alignment can identify candidates, but this module compares
selected typed representations against the exact model-owned input interface.
It never grants execution, scientific equivalence, or source authority.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING

from polisyos.core.artifacts import (
    ArtifactManifest,
    ArtifactRef,
    CoreJSONArtifactStore,
    CoreJsonReadLimits,
    InputRef,
    PutOptions,
    SchemaInfo,
    artifact_manifest_profile_sha256,
    artifact_ref_identity_key,
    input_ref_from_artifact_ref,
    read_core_json_artifact_bounded,
    validate_core_model_json_artifact,
)
from polisyos.core.contracts import (
    ENTITY_VECTOR_CANDIDATE_LIMITATIONS,
    DataSnapshotOwnerBound,
    EntityAxisMemberId,
    EntityVectorCorrespondenceBasis,
    EntityVectorCorrespondenceBasisRef,
    FabricBridgeDataSnapshotLineage,
    FixedUnitTransformWitness,
    FoundryInputBindings,
    MeasurementAxis,
    MeasurementBindingProfile,
    MeasurementBindingProfileRef,
    MeasurementCorrespondenceResult,
    ModelInputObligationSet,
    ModelInputPort,
    ModelInputScope,
    ModelInputStepSelectionResolution,
    ModelInputStepSubject,
    RegisteredSQLAdmissionBinding,
    RegisteredSQLCapture,
    RegisteredSQLMeasurementOccurrence,
    RegisteredSQLMeasurementSourceSelection,
    ResolvedEntityVectorInput,
    ResolvedEntityVectorInputAtStep,
    ResolvedInputBindingManifest,
    ResolvedInputBindingManifestRef,
    ScopedCorrespondenceBasis,
    ScopedCorrespondenceBasisRef,
    ScopedCorrespondenceEvaluation,
    ScopedMeasurementOccurrence,
    ScopedMeasurementOccurrenceRef,
    ScopedSourceSelection,
    SelectedEntityAxis,
    SelectedEntityVectorSourceMeaning,
    SelectedEntityVectorSourceMeaningRef,
    SelectedVariableBindingRef,
    VariableRepresentationRef,
    VariableSemanticDefinition,
    VariableSemanticDefinitionRef,
    data_snapshot_manifest_inputs_match,
    entity_axis_member_sort_key,
    entity_vector_correspondence_basis_manifest_inputs,
    epoch,
    evaluate_entity_vector_correspondence_basis,
    evaluate_scoped_correspondence_basis,
    load_entity_vector_correspondence_basis,
    load_program_graph_input_interface,
    load_resolved_input_binding_manifest,
    load_scoped_measurement_occurrence,
    load_selected_entity_vector_source_meaning,
    load_variable_representation,
    persist_resolved_input_binding_manifest,
    registered_sql_capture_input_refs,
    replay_registered_sql_measurement_occurrence,
    replay_scoped_measurement_occurrence,
    resolve_model_input_step_subjects,
    scoped_correspondence_basis_manifest_inputs,
    scoped_measurement_occurrence_manifest_inputs,
    scoped_source_selection_from_passport_mapping,
    selected_entity_vector_source_meaning_manifest_inputs,
)
from polisyos.core.registry import load_registry_bundle, load_registry_bundle_content
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
    from polisyos.core.artifacts import ArtifactReader, VerifiableCoreJSONArtifactProfileReader
    from polisyos.core.registry import RegistryBundleContent
    from polisyos.data_forge.domains.catalog.knowledge.acquisition_authority import (
        CanonicalAcquisitionAuthority,
    )
    from polisyos.ir.kernel import UnitSpecType


class _AssessmentRefusalError(ValueError):
    """Expected fail-closed result from a missing or mismatched selected input."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


_AssessmentRefusal = _AssessmentRefusalError

_REGISTERED_SQL_MEASUREMENT_READ_LIMITS = CoreJsonReadLimits(
    max_bytes=4 * 1024 * 1024,
    max_depth=32,
    max_elements=100_000,
    max_manifest_bytes=512 * 1024,
)


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
    store: VerifiableCoreJSONArtifactProfileReader,
    occurrence_ref: ScopedMeasurementOccurrenceRef,
) -> tuple[
    ScopedMeasurementOccurrence | RegisteredSQLMeasurementOccurrence,
    ScopedMeasurementOccurrence | RegisteredSQLMeasurementOccurrence,
    ScopedSourceSelection | RegisteredSQLMeasurementSourceSelection,
]:
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
        occurrence = load_scoped_measurement_occurrence(store, selected_occurrence_ref)
        if tuple(store.get_manifest(selected_occurrence_ref).inputs) != (
            scoped_measurement_occurrence_manifest_inputs(occurrence)
        ):
            raise _AssessmentRefusal("occurrence_lineage_mismatch")

        if isinstance(occurrence, RegisteredSQLMeasurementOccurrence):
            source = occurrence.source_selection
            _binding, _snapshot, _capture, payload = _read_registered_sql_measurement_source(
                store,
                registered_sql_admission_ref=source.registered_sql_admission_ref,
                read_limits=_REGISTERED_SQL_MEASUREMENT_READ_LIMITS,
            )
            materialization = _binding.materialization
            if any(
                artifact_ref_identity_key(left) != artifact_ref_identity_key(right)
                for left, right in (
                    (source.snapshot_ref, materialization.snapshot_ref),
                    (source.capture_ref, materialization.producer_capture_ref),
                    (source.payload_ref, materialization.payload_ref),
                )
            ):
                raise _AssessmentRefusal("registered_sql_measurement_source_mismatch")
            replayed = _replay_registered_sql_cell(payload, source=source, capture=_capture)
            return occurrence, replayed, source

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


def _read_registered_sql_measurement_source(
    store: VerifiableCoreJSONArtifactProfileReader,
    *,
    registered_sql_admission_ref: ArtifactRef,
    read_limits: CoreJsonReadLimits,
) -> tuple[RegisteredSQLAdmissionBinding, DataSnapshotOwnerBound, RegisteredSQLCapture, object]:
    """Read exact stored SQL facts, without performing a query or current admission."""
    if type(read_limits) is not CoreJsonReadLimits:
        raise _AssessmentRefusal("registered_sql_measurement_read_limits_required")
    limits = CoreJsonReadLimits(
        max_bytes=min(read_limits.max_bytes, _REGISTERED_SQL_MEASUREMENT_READ_LIMITS.max_bytes),
        max_depth=min(read_limits.max_depth, _REGISTERED_SQL_MEASUREMENT_READ_LIMITS.max_depth),
        max_elements=min(
            read_limits.max_elements, _REGISTERED_SQL_MEASUREMENT_READ_LIMITS.max_elements
        ),
        max_manifest_bytes=min(
            read_limits.max_manifest_bytes,
            _REGISTERED_SQL_MEASUREMENT_READ_LIMITS.max_manifest_bytes,
        ),
    )
    if registered_sql_admission_ref.manifest_profile_sha256 is None:
        raise _AssessmentRefusal("source_profile_required")
    selected = _selected_exact_ref(store, registered_sql_admission_ref)
    binding = validate_core_model_json_artifact(RegisteredSQLAdmissionBinding, store, selected)
    materialization = binding.materialization
    snapshot = validate_core_model_json_artifact(
        DataSnapshotOwnerBound, store, materialization.snapshot_ref
    )
    capture = validate_core_model_json_artifact(
        RegisteredSQLCapture, store, materialization.producer_capture_ref
    )
    if not isinstance(snapshot.source_lineage, FabricBridgeDataSnapshotLineage):
        raise _AssessmentRefusal("registered_sql_measurement_snapshot_owner_mismatch")
    if any(
        artifact_ref_identity_key(left) != artifact_ref_identity_key(right)
        for left, right in (
            (capture.snapshot_ref, materialization.snapshot_ref),
            (capture.payload_ref, materialization.payload_ref),
            (capture.schema_ref, materialization.schema_ref),
            (capture.quality_ref, materialization.quality_ref),
            (capture.request_ref, materialization.request_ref),
            (capture.view_ref, materialization.registration.effective_view_contract_ref),
            (capture.use_ref, materialization.registration.use_contract_ref),
            (snapshot.data_ref, materialization.payload_ref),
            (snapshot.source_lineage.data_view_request_ref, materialization.request_ref),
        )
    ) or (
        snapshot.data_schema_ref is None
        or snapshot.quality_report_ref is None
        or artifact_ref_identity_key(snapshot.data_schema_ref)
        != artifact_ref_identity_key(materialization.schema_ref)
        or artifact_ref_identity_key(snapshot.quality_report_ref)
        != artifact_ref_identity_key(materialization.quality_ref)
    ):
        raise _AssessmentRefusal("registered_sql_measurement_source_mismatch")
    snapshot_manifest = store.get_manifest(materialization.snapshot_ref)
    if not data_snapshot_manifest_inputs_match(
        snapshot,
        snapshot_manifest.inputs,
        schema_version=snapshot_manifest.artifact_schema.version
        if snapshot_manifest.artifact_schema
        else None,
    ):
        raise _AssessmentRefusal("registered_sql_measurement_snapshot_lineage_mismatch")
    capture_inputs = registered_sql_capture_input_refs(
        snapshot, materialization.snapshot_ref, materialization.registration
    )
    admission_inputs = [
        *capture_inputs,
        input_ref_from_artifact_ref(materialization.producer_capture_ref, role="source.capture"),
    ]

    def edge_key(edge: InputRef) -> tuple[str, str, str | None]:
        return (str(edge.artifact_id), edge.role, edge.manifest_profile_sha256)

    if Counter(
        map(edge_key, store.get_manifest(materialization.producer_capture_ref).inputs)
    ) != Counter(map(edge_key, capture_inputs)) or Counter(
        map(edge_key, store.get_manifest(selected).inputs)
    ) != Counter(map(edge_key, admission_inputs)):
        raise _AssessmentRefusal("registered_sql_measurement_transport_lineage_mismatch")
    for ref in (
        selected,
        materialization.producer_capture_ref,
        materialization.snapshot_ref,
        materialization.schema_ref,
        materialization.quality_ref,
        materialization.registration.effective_view_contract_ref,
        materialization.registration.use_contract_ref,
    ):
        if ref.manifest_profile_sha256 is None or not store.verify(ref).ok:
            raise _AssessmentRefusal("registered_sql_measurement_source_unverified")
    payload_ref = _selected_exact_ref(store, materialization.payload_ref)
    read = read_core_json_artifact_bounded(store, payload_ref, limits=limits)
    if artifact_ref_identity_key(read.effective_ref) != artifact_ref_identity_key(payload_ref):
        raise _AssessmentRefusal("registered_sql_measurement_payload_profile_mismatch")
    return binding, snapshot, capture, read.value


def _replay_registered_sql_cell(
    payload: object,
    *,
    source: RegisteredSQLMeasurementSourceSelection,
    capture: RegisteredSQLCapture,
) -> RegisteredSQLMeasurementOccurrence:
    """Apply the same captured-column and exact-cell law to production and replay."""
    if source.source_path.split(".")[1] not in capture.columns:
        raise _AssessmentRefusal("registered_sql_measurement_column_not_captured")
    return replay_registered_sql_measurement_occurrence(payload, source_selection=source)


def materialize_registered_sql_measurement_occurrence(
    store: CoreJSONArtifactStore,
    *,
    registered_sql_admission_ref: ArtifactRef,
    source_path: str,
    source_definition_ref: VariableSemanticDefinitionRef,
    source_representation_ref: VariableRepresentationRef,
    source_scope: ModelInputScope,
    declared_release: str,
    read_limits: CoreJsonReadLimits,
) -> ScopedMeasurementOccurrenceRef:
    """Persist a candidate declaration over one actual captured SQL cell.

    Snapshot, capture and payload identities are derived from the exact stored
    SQL admission. The declaration does not establish empirical meaning,
    release truth, source currentness, or current-use authority.
    Production and replay both cap each selected payload at 4 MiB, depth 32,
    100,000 lexical nodes, and a 512 KiB manifest. Stricter caller bounds apply;
    a payload outside this profile refuses before any occurrence is persisted.

    Args:
        store: Existing Core CAS containing the actual SQL capture and model facts.
        registered_sql_admission_ref: Selected immutable SQL transport binding.
        source_path: Explicit zero-based row and column, such as ``0.amount``.
        source_definition_ref: Selected consumer-declared source definition.
        source_representation_ref: Selected consumer-declared representation.
        source_scope: Explicit consumer-declared population, geography and time scope.
        declared_release: Consumer-declared release identifier, without issuer authority.
        read_limits: Explicit selected JSON payload and manifest resource bounds.

    Returns:
        The persisted candidate occurrence bound to its actual capture and cell.
    """
    binding, _snapshot, capture, payload = _read_registered_sql_measurement_source(
        store,
        registered_sql_admission_ref=registered_sql_admission_ref,
        read_limits=read_limits,
    )
    definition = validate_core_model_json_artifact(
        VariableSemanticDefinition, store, source_definition_ref
    )
    representation = load_variable_representation(store, source_representation_ref)
    _reopen_definition_evidence(store, definition)
    if (
        artifact_ref_identity_key(representation.semantic_definition_ref)
        != artifact_ref_identity_key(source_definition_ref)
        or representation.unit_id is None
    ):
        raise _AssessmentRefusal("registered_sql_measurement_representation_mismatch")
    source = RegisteredSQLMeasurementSourceSelection(
        registered_sql_admission_ref=SelectedVariableBindingRef.model_validate(
            _selected_exact_ref(store, registered_sql_admission_ref).model_dump(mode="python")
        ),
        capture_ref=SelectedVariableBindingRef.model_validate(
            binding.materialization.producer_capture_ref.model_dump(mode="python")
        ),
        snapshot_ref=SelectedVariableBindingRef.model_validate(
            binding.materialization.snapshot_ref.model_dump(mode="python")
        ),
        payload_ref=SelectedVariableBindingRef.model_validate(
            binding.materialization.payload_ref.model_dump(mode="python")
        ),
        source_path=source_path,
        declared_source_definition_ref=source_definition_ref,
        declared_source_representation_ref=source_representation_ref,
        declared_release=declared_release,
        source_scope=source_scope,
        canonical_variable=f"{definition.namespace}.{definition.stable_id}",
        canonical_unit=representation.unit_id,
    )
    occurrence = _replay_registered_sql_cell(payload, source=source, capture=capture)
    return _persist_occurrence(store, occurrence)


def assess_selected_measurement_to_model_candidate(
    store: CoreJSONArtifactStore,
    *,
    occurrence_ref: ScopedMeasurementOccurrenceRef,
    source_definition_ref: VariableSemanticDefinitionRef,
    source_representation_ref: VariableRepresentationRef,
    model_interface_ref: SelectedVariableBindingRef,
    port_id: str,
) -> MeasurementCorrespondenceResult:
    """Assess a replayed source occurrence through the shared candidate predicate.

    Args:
        store: Existing selected Core CAS reader and candidate artifact writer.
        occurrence_ref: Exact versioned epoch or SQL source occurrence.
        source_definition_ref: Explicit source semantic declaration.
        source_representation_ref: Explicit source measurement representation.
        model_interface_ref: Exact model-owned input interface.
        port_id: Unique selected port in that interface.

    Returns:
        Candidate/refusal and its selected correspondence basis. No current
        source permission or empirical semantic authority follows.
    """
    try:
        occurrence, replayed, source = replay_selected_scoped_measurement_facts(
            store, occurrence_ref
        )
        return _assess_measurement_occurrence(
            store,
            occurrence_ref=occurrence_ref,
            occurrence=occurrence,
            replayed_occurrence=replayed,
            source_selection=source,
            source_definition_ref=source_definition_ref,
            source_representation_ref=source_representation_ref,
            model_interface_ref=model_interface_ref,
            port_id=port_id,
        )
    except (_AssessmentRefusal, OverlayAdmissionError, OSError, TypeError, ValueError) as exc:
        return _result(
            source_observation_id="unknown",
            source_definition_ref=source_definition_ref,
            source_representation_ref=source_representation_ref,
            model_interface_ref=model_interface_ref,
            model_port_id=port_id,
            status="refused",
            refusal_codes=(getattr(exc, "code", "selected_owner_input_invalid"),),
        )


def _assess_measurement_occurrence(
    store: CoreJSONArtifactStore,
    *,
    occurrence_ref: ScopedMeasurementOccurrenceRef,
    occurrence: ScopedMeasurementOccurrence | RegisteredSQLMeasurementOccurrence,
    replayed_occurrence: ScopedMeasurementOccurrence | RegisteredSQLMeasurementOccurrence,
    source_selection: ScopedSourceSelection | RegisteredSQLMeasurementSourceSelection,
    source_definition_ref: VariableSemanticDefinitionRef,
    source_representation_ref: VariableRepresentationRef,
    model_interface_ref: SelectedVariableBindingRef,
    port_id: str,
) -> MeasurementCorrespondenceResult:
    """Use one selected model/basis/evaluator path for both source owners."""
    source_definition = validate_core_model_json_artifact(
        VariableSemanticDefinition, store, source_definition_ref
    )
    source_representation = load_variable_representation(store, source_representation_ref)
    _reopen_definition_evidence(store, source_definition)
    interface = load_program_graph_input_interface(store, model_interface_ref)
    ports = tuple(port for port in interface.ports if port.port_id == port_id)
    if len(ports) != 1:
        raise _AssessmentRefusal("selected_model_port_not_unique")
    (port,) = ports
    target_definition_ref = port.semantic_definition_ref
    target_representation_ref = port.representation_ref
    profile_ref = port.binding_profile_ref
    target_definition = validate_core_model_json_artifact(
        VariableSemanticDefinition, store, target_definition_ref
    )
    target_representation = load_variable_representation(store, target_representation_ref)
    profile = validate_core_model_json_artifact(MeasurementBindingProfile, store, profile_ref)
    basis = ScopedCorrespondenceBasis(
        occurrence_ref=occurrence_ref,
        source_definition_ref=source_definition_ref,
        source_representation_ref=source_representation_ref,
        source_definition_evidence_refs=source_definition.definition_evidence_refs,
        model_interface_ref=SelectedVariableBindingRef.model_validate(
            _selected_exact_ref(store, model_interface_ref).model_dump(mode="python")
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
    basis_ref = (
        _persist_correspondence_basis(store, basis) if evaluation.status == "candidate" else None
    )
    return _result(
        source_observation_id=occurrence.observation_id,
        source_definition_ref=source_definition_ref,
        source_representation_ref=source_representation_ref,
        model_interface_ref=model_interface_ref,
        model_port_id=port_id,
        status=evaluation.status,
        target_definition_ref=target_definition_ref,
        target_representation_ref=target_representation_ref,
        binding_profile_ref=profile_ref,
        occurrence_ref=occurrence_ref,
        correspondence_basis_ref=basis_ref,
        recomputed_axes=evaluation.recomputed_axes,
        optional_unknown_axes=evaluation.optional_unknown_axes,
        limitation_codes=evaluation.limitation_codes,
        refusal_codes=evaluation.refusal_codes,
        semantic_correspondence=evaluation.semantic_correspondence,
    )


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
        return _assess_measurement_occurrence(
            store,
            occurrence_ref=occurrence_ref,
            occurrence=replayed_occurrence,
            replayed_occurrence=replayed_occurrence,
            source_selection=source_selection,
            source_definition_ref=source_definition_ref,
            source_representation_ref=source_representation_ref,
            model_interface_ref=model_interface_ref,
            port_id=port_id,
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


def _read_exact_selected_bytes(store: ArtifactReader, ref: ArtifactRef) -> bytes:
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


def _selected_exact_ref(store: ArtifactReader, ref: ArtifactRef) -> ArtifactRef:
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
    store: VerifiableCoreJSONArtifactProfileReader,
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
    occurrence: ScopedMeasurementOccurrence | RegisteredSQLMeasurementOccurrence,
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
    loaded = load_scoped_measurement_occurrence(store, selected_ref)
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


def assess_entity_vector_to_model_candidate(
    store: CoreJSONArtifactStore,
    *,
    source_meaning_ref: SelectedEntityVectorSourceMeaningRef,
    obligation_set_ref: ArtifactRef,
    step_subject: ModelInputStepSubject,
    read_limits: CoreJsonReadLimits,
) -> tuple[ScopedCorrespondenceEvaluation, EntityVectorCorrespondenceBasisRef | None]:
    """Replay one selected entity-vector declaration against a model port.

    The result is candidate-only. A successful comparison recomputes equality
    between selected semantic definitions and representation axes; it does not
    establish empirical meaning, source currentness, representativeness, or
    permission for a current method call. Source JSON is reopened with bounded
    Core readers and its generic parallel-array layout, membership, cardinality,
    and finite numeric values are checked before a basis is persisted. The
    original obligation set resolves the exact interface and step scope; a
    caller-supplied scope cannot turn a declaration into a positive predicate.

    Args:
        store: Core JSON artifact store shared by the Catalog owner.
        source_meaning_ref: Exact persisted declaration for one selected source
            view, member pointer, value pointer, and consumer-declared scope.
        obligation_set_ref: Exact original full-horizon model-input preflight.
        step_subject: One original obligation and port-step coordinate whose
            scope is resolved against the selected model clock.
        read_limits: Explicit byte, depth, and element limits for the selected
            source JSON read.

    Returns:
        tuple[ScopedCorrespondenceEvaluation, EntityVectorCorrespondenceBasisRef | None]:
        Recomputed candidate/refusal and its persisted basis reference when
        candidate predicates pass. Refusals never carry a basis reference.
    """
    if type(step_subject) is not ModelInputStepSubject:
        return _entity_vector_refusal("entity_vector_step_subject_untyped"), None
    try:
        resolution = resolve_model_input_step_subjects(
            store,
            obligation_set_ref=obligation_set_ref,
            subjects=(step_subject,),
        )
    except (FileNotFoundError, OSError, TypeError, ValueError) as exc:
        return _entity_vector_refusal(_entity_vector_refusal_code(exc)), None
    return _assess_entity_vector_to_model_candidate_from_resolution(
        store,
        source_meaning_ref=source_meaning_ref,
        step_subject=step_subject,
        resolution=resolution,
        read_limits=read_limits,
    )


def _assess_entity_vector_to_model_candidate_from_resolution(
    store: CoreJSONArtifactStore,
    *,
    source_meaning_ref: SelectedEntityVectorSourceMeaningRef,
    step_subject: ModelInputStepSubject,
    resolution: ModelInputStepSelectionResolution,
    read_limits: CoreJsonReadLimits,
) -> tuple[ScopedCorrespondenceEvaluation, EntityVectorCorrespondenceBasisRef | None]:
    """Evaluate and persist one candidate using an existing Core step replay."""
    try:
        if (
            type(read_limits) is not CoreJsonReadLimits
            or type(resolution) is not ModelInputStepSelectionResolution
            or type(step_subject) is not ModelInputStepSubject
        ):
            raise _AssessmentRefusal("entity_vector_bounded_step_inputs_required")
        resolved_scopes = tuple(
            scope
            for scope in resolution.coverage.supplied_step_scopes
            if (scope.port_id, scope.step)
            == (step_subject.step_scope.port_id, step_subject.step_scope.step)
        )
        if len(resolved_scopes) != 1 or resolved_scopes[0] != step_subject.step_scope:
            raise _AssessmentRefusal("entity_vector_step_scope_not_recomputed")
        expected_scope = resolved_scopes[0].scope
        selected_source_meaning_ref = SelectedEntityVectorSourceMeaningRef.model_validate(
            _selected_exact_ref(store, source_meaning_ref).model_dump(mode="json")
        )
        source_meaning = load_selected_entity_vector_source_meaning(
            store, selected_source_meaning_ref
        )
        selected_set = resolution.obligation_set
        selected_interface_ref = SelectedVariableBindingRef.model_validate(
            _selected_exact_ref(store, selected_set.invocation.interface_ref).model_dump(
                mode="json"
            )
        )
        model_port_id = step_subject.step_scope.port_id
        interface = load_program_graph_input_interface(store, selected_interface_ref)
        if artifact_ref_identity_key(interface.registry_bundle_ref) != artifact_ref_identity_key(
            source_meaning.source_registry_bundle_ref
        ):
            raise _AssessmentRefusal("entity_vector_registry_bundle_mismatch")
        selected_ports = tuple(port for port in interface.ports if port.port_id == model_port_id)
        if len(selected_ports) != 1:
            raise _AssessmentRefusal("entity_vector_model_port_not_unique")
        model_port = selected_ports[0]
        if type(model_port) is not ModelInputPort or model_port.entity_axis_ref is None:
            raise _AssessmentRefusal("entity_vector_model_port_axis_required")
        selected_obligation_refs = tuple(
            (ref, member)
            for ref, member in zip(
                selected_set.obligation_refs, resolution.obligations, strict=True
            )
            if artifact_ref_identity_key(ref)
            == artifact_ref_identity_key(step_subject.model_input_obligation_ref)
        )
        if len(selected_obligation_refs) != 1 or selected_obligation_refs[0][1].port != model_port:
            raise _AssessmentRefusal("entity_vector_step_origin_port_mismatch")

        selected_axis_ref = _selected_exact_ref(store, model_port.entity_axis_ref)
        _replay_entity_vector_source_layout(
            store,
            source_meaning=source_meaning,
            model_port=model_port,
            axis_ref=selected_axis_ref,
            read_limits=read_limits,
        )

        source_definition_ref = VariableSemanticDefinitionRef.model_validate(
            _selected_exact_ref(store, source_meaning.source_definition_ref).model_dump(mode="json")
        )
        source_representation_ref = VariableRepresentationRef.model_validate(
            _selected_exact_ref(store, source_meaning.source_representation_ref).model_dump(
                mode="json"
            )
        )
        source_definition = validate_core_model_json_artifact(
            VariableSemanticDefinition, store, source_definition_ref
        )
        source_representation = load_variable_representation(store, source_representation_ref)
        _reopen_definition_evidence(store, source_definition)

        target_definition_ref = VariableSemanticDefinitionRef.model_validate(
            _selected_exact_ref(store, model_port.semantic_definition_ref).model_dump(mode="json")
        )
        target_representation_ref = VariableRepresentationRef.model_validate(
            _selected_exact_ref(store, model_port.representation_ref).model_dump(mode="json")
        )
        binding_profile_ref = MeasurementBindingProfileRef.model_validate(
            _selected_exact_ref(store, model_port.binding_profile_ref).model_dump(mode="json")
        )
        target_definition = validate_core_model_json_artifact(
            VariableSemanticDefinition, store, target_definition_ref
        )
        target_representation = load_variable_representation(store, target_representation_ref)
        profile = validate_core_model_json_artifact(
            MeasurementBindingProfile, store, binding_profile_ref
        )
        _reopen_definition_evidence(store, target_definition)

        registry_content = _load_reconciled_registry_bundle_content(
            store, source_meaning.source_registry_bundle_ref
        )
        units = registry_content.units_registry
        source_unit: UnitSpecType | None = (
            None if units is None else units.units.get(source_representation.unit_id)
        )
        target_unit: UnitSpecType | None = (
            None if units is None else units.units.get(target_representation.unit_id)
        )
        basis = EntityVectorCorrespondenceBasis(
            source_meaning_ref=selected_source_meaning_ref,
            model_interface_ref=selected_interface_ref,
            model_port_id=model_port_id,
            target_definition_ref=target_definition_ref,
            target_representation_ref=target_representation_ref,
            binding_profile_ref=binding_profile_ref,
            scope=expected_scope,
        )
        evaluation = evaluate_entity_vector_correspondence_basis(
            basis=basis,
            source_meaning_ref=selected_source_meaning_ref,
            source_meaning=source_meaning,
            source_definition_ref=source_definition_ref,
            source_definition=source_definition,
            source_representation_ref=source_representation_ref,
            source_representation=source_representation,
            source_registry_bundle_ref=source_meaning.source_registry_bundle_ref,
            source_unit=source_unit,
            target_unit=target_unit,
            target_definition_ref=target_definition_ref,
            target_definition=target_definition,
            target_representation_ref=target_representation_ref,
            target_representation=target_representation,
            binding_profile_ref=binding_profile_ref,
            profile=profile,
            model_interface_ref=selected_interface_ref,
            model_port=model_port,
            expected_scope=expected_scope,
        )
        if evaluation.status == "refused":
            return evaluation, None

        basis_ref = _persist_entity_vector_correspondence_basis(store, basis)
        reopened_basis = load_entity_vector_correspondence_basis(store, basis_ref)
        if reopened_basis != basis:
            raise _AssessmentRefusal("entity_vector_correspondence_basis_readback_mismatch")
        reopened_meaning = load_selected_entity_vector_source_meaning(
            store, selected_source_meaning_ref
        )
        reopened_interface = load_program_graph_input_interface(store, selected_interface_ref)
        reopened_ports = tuple(
            port for port in reopened_interface.ports if port.port_id == model_port_id
        )
        if len(reopened_ports) != 1:
            raise _AssessmentRefusal("entity_vector_model_port_not_unique")
        reopened_source_definition = validate_core_model_json_artifact(
            VariableSemanticDefinition, store, source_definition_ref
        )
        reopened_target_definition = validate_core_model_json_artifact(
            VariableSemanticDefinition, store, target_definition_ref
        )
        _reopen_definition_evidence(store, reopened_source_definition)
        _reopen_definition_evidence(store, reopened_target_definition)
        reopened_registry_content = _load_reconciled_registry_bundle_content(
            store, reopened_meaning.source_registry_bundle_ref
        )
        reopened_units = reopened_registry_content.units_registry
        reopened_source_representation = load_variable_representation(
            store, source_representation_ref
        )
        reopened_target_representation = load_variable_representation(
            store, target_representation_ref
        )
        reopened_source_unit: UnitSpecType | None = (
            None
            if reopened_units is None
            else reopened_units.units.get(reopened_source_representation.unit_id)
        )
        reopened_target_unit: UnitSpecType | None = (
            None
            if reopened_units is None
            else reopened_units.units.get(reopened_target_representation.unit_id)
        )
        replayed = evaluate_entity_vector_correspondence_basis(
            basis=reopened_basis,
            source_meaning_ref=selected_source_meaning_ref,
            source_meaning=reopened_meaning,
            source_definition_ref=source_definition_ref,
            source_definition=reopened_source_definition,
            source_representation_ref=source_representation_ref,
            source_representation=reopened_source_representation,
            source_registry_bundle_ref=reopened_meaning.source_registry_bundle_ref,
            source_unit=reopened_source_unit,
            target_unit=reopened_target_unit,
            target_definition_ref=target_definition_ref,
            target_definition=reopened_target_definition,
            target_representation_ref=target_representation_ref,
            target_representation=reopened_target_representation,
            binding_profile_ref=binding_profile_ref,
            profile=validate_core_model_json_artifact(
                MeasurementBindingProfile, store, binding_profile_ref
            ),
            model_interface_ref=selected_interface_ref,
            model_port=reopened_ports[0],
            expected_scope=expected_scope,
        )
        if replayed != evaluation or replayed.status != "candidate":
            raise _AssessmentRefusal("entity_vector_correspondence_replay_mismatch")
        return replayed, basis_ref
    except (_AssessmentRefusal, OverlayAdmissionError) as exc:
        return _entity_vector_refusal(exc.code), None
    except (FileNotFoundError, OSError, TypeError, ValueError) as exc:
        return _entity_vector_refusal(_entity_vector_refusal_code(exc)), None


def prepare_registered_entity_vector_input_steps(
    store: CoreJSONArtifactStore,
    *,
    data_snapshot_ref: ArtifactRef,
    obligation_set_ref: ArtifactRef,
    source_inputs: tuple[tuple[ModelInputStepSubject, SelectedEntityVectorSourceMeaning], ...],
    read_limits: CoreJsonReadLimits,
) -> ResolvedInputBindingManifestRef:
    """Persist a complete candidate vector selection for registered method ports.

    The source inputs pair one selected meaning declaration with each original
    model-owned `(port, step)` subject. Core reopens the full obligation set and
    computes the coverage denominator. Each target port and entity axis is
    derived from that selected interface; callers cannot substitute a free
    axis. The original DataSnapshot predecessor is checked against the input
    bindings selected by the same invocation and is recorded unchanged in
    manifest 4.0. This only stages candidate inputs for Foundry's independent
    source replay and typed vector alignment.

    Args:
        store: Core JSON artifact store shared by Catalog and Foundry.
        data_snapshot_ref: Exact original predecessor from the invocation's
            selected `FoundryInputBindings` artifact.
        obligation_set_ref: Exact selected original full-horizon preflight set.
        source_inputs: Nonempty, canonical `(step subject, source meaning)` rows.
        read_limits: Explicit bounds for each selected generic JSON source view.

    Returns:
        ResolvedInputBindingManifestRef: Selected direct vector manifest v4.

    Raises:
        ValueError: If a step, source declaration, full predecessor, coverage,
            or candidate correspondence fails replay.
    """
    if (
        type(read_limits) is not CoreJsonReadLimits
        or type(source_inputs) is not tuple
        or not source_inputs
        or len(source_inputs) > 32
        or any(type(row) is not tuple or len(row) != 2 for row in source_inputs)
    ):
        raise _AssessmentRefusal("entity_vector_step_input_inventory_invalid")
    subjects: tuple[ModelInputStepSubject, ...] = tuple(row[0] for row in source_inputs)
    meanings: tuple[SelectedEntityVectorSourceMeaning, ...] = tuple(row[1] for row in source_inputs)
    if any(
        type(subject) is not ModelInputStepSubject
        or type(meaning) is not SelectedEntityVectorSourceMeaning
        for subject, meaning in zip(subjects, meanings, strict=True)
    ):
        raise _AssessmentRefusal("entity_vector_step_input_inventory_invalid")
    step_keys = tuple((row.step_scope.port_id, row.step_scope.step) for row in subjects)
    if step_keys != tuple(sorted(set(step_keys))):
        raise _AssessmentRefusal("entity_vector_step_input_inventory_noncanonical")

    selected_obligation_set_ref = _selected_exact_ref(store, obligation_set_ref)
    selected_obligation_set = validate_core_model_json_artifact(
        ModelInputObligationSet, store, selected_obligation_set_ref
    )
    predecessor_input_bindings_ref = _selected_exact_ref(
        store, selected_obligation_set.invocation.input_bindings_ref
    )
    original_input_bindings = validate_core_model_json_artifact(
        FoundryInputBindings, store, predecessor_input_bindings_ref
    )
    if (
        original_input_bindings.selected_method_inputs is not None
        or original_input_bindings.selected_method_input_steps is not None
    ):
        raise _AssessmentRefusal("foundry_selected_method_input_step_original_prestate_required")

    resolution = resolve_model_input_step_subjects(
        store,
        obligation_set_ref=selected_obligation_set_ref,
        subjects=subjects,
    )
    if artifact_ref_identity_key(
        resolution.obligation_set.invocation.input_bindings_ref
    ) != artifact_ref_identity_key(predecessor_input_bindings_ref):
        raise _AssessmentRefusal("entity_vector_original_predecessor_context_mismatch")
    coverage = resolution.coverage
    try:
        coverage.require_complete()
    except ValueError as exc:
        raise _AssessmentRefusal("entity_vector_step_coverage_incomplete") from exc

    invocation = resolution.obligation_set.invocation
    selected_interface_ref = SelectedVariableBindingRef.model_validate(
        _selected_exact_ref(store, invocation.interface_ref).model_dump(mode="json")
    )
    interface = load_program_graph_input_interface(store, selected_interface_ref)
    selected_registry_ref = _selected_exact_ref(store, invocation.registry_bundle_ref)
    original_input_bindings_ref = predecessor_input_bindings_ref
    original_input_bindings_manifest = store.get_manifest(original_input_bindings_ref)
    _require_exact_input_role(
        original_input_bindings_manifest,
        "input.data_snapshot_ref",
        original_input_bindings.data_snapshot_ref,
        refusal_code="entity_vector_original_snapshot_lineage_mismatch",
    )
    _require_exact_input_role(
        original_input_bindings_manifest,
        "input.registry_bundle_ref",
        original_input_bindings.registry_bundle_ref,
        refusal_code="entity_vector_original_registry_lineage_mismatch",
    )
    _require_exact_input_role(
        original_input_bindings_manifest,
        "artifact.bound_state_snapshot_ref",
        original_input_bindings.bound_state_snapshot_ref,
        refusal_code="entity_vector_original_prestate_lineage_mismatch",
    )
    original_data_snapshot_ref = _selected_exact_ref(
        store, original_input_bindings.data_snapshot_ref
    )
    supplied_data_snapshot_ref = _selected_exact_ref(store, data_snapshot_ref)
    if artifact_ref_identity_key(supplied_data_snapshot_ref) != artifact_ref_identity_key(
        original_data_snapshot_ref
    ):
        raise _AssessmentRefusal("entity_vector_original_predecessor_mismatch")
    if artifact_ref_identity_key(original_input_bindings.registry_bundle_ref) != (
        artifact_ref_identity_key(selected_registry_ref)
    ):
        raise _AssessmentRefusal("entity_vector_invocation_registry_mismatch")
    if artifact_ref_identity_key(original_input_bindings.bound_state_snapshot_ref) != (
        artifact_ref_identity_key(resolution.obligation_set.prestate_ref)
    ):
        raise _AssessmentRefusal("entity_vector_original_prestate_mismatch")

    obligations_by_ref = {
        artifact_ref_identity_key(ref): obligation
        for ref, obligation in zip(
            resolution.obligation_set.obligation_refs, resolution.obligations, strict=True
        )
    }
    entity_vector_steps: list[ResolvedEntityVectorInputAtStep] = []
    binding_ids: set[str] = set()
    for subject, source_meaning in zip(subjects, meanings, strict=True):
        obligation_ref = _selected_exact_ref(store, subject.model_input_obligation_ref)
        obligation = obligations_by_ref.get(artifact_ref_identity_key(obligation_ref))
        if obligation is None:
            raise _AssessmentRefusal("entity_vector_step_origin_not_selected")
        model_port = obligation.port
        if (
            model_port.carrier != "method_input"
            or model_port.port_id != subject.step_scope.port_id
            or model_port.entity_axis_ref is None
            or model_port.physical_encoding is None
            or len(model_port.physical_encoding.shape) != 1
        ):
            raise _AssessmentRefusal("entity_vector_method_vector_port_required")
        interface_ports = tuple(
            port for port in interface.ports if port.port_id == model_port.port_id
        )
        if len(interface_ports) != 1 or interface_ports[0] != model_port:
            raise _AssessmentRefusal("entity_vector_interface_port_mismatch")
        if source_meaning.source_scope != subject.step_scope.scope or artifact_ref_identity_key(
            source_meaning.source_registry_bundle_ref
        ) != artifact_ref_identity_key(selected_registry_ref):
            raise _AssessmentRefusal("entity_vector_candidate_scope_or_registry_mismatch")

        source_meaning_ref = _persist_entity_vector_source_meaning(store, source_meaning)
        evaluation, correspondence_ref = _assess_entity_vector_to_model_candidate_from_resolution(
            store,
            source_meaning_ref=source_meaning_ref,
            step_subject=subject,
            resolution=resolution,
            read_limits=read_limits,
        )
        if evaluation.status != "candidate" or correspondence_ref is None:
            code = (
                evaluation.refusal_codes[0]
                if evaluation.refusal_codes
                else "entity_vector_candidate_refused"
            )
            raise _AssessmentRefusal(code)

        axis_ref = _selected_exact_ref(store, model_port.entity_axis_ref)
        selection = ResolvedEntityVectorInput(
            binding_id=_entity_vector_binding_id(
                model_port.port_id, subject.step_scope.step, source_meaning_ref
            ),
            model_input_obligation_ref=SelectedVariableBindingRef.model_validate(
                obligation_ref.model_dump(mode="json")
            ),
            model_interface_ref=selected_interface_ref,
            model_port_id=model_port.port_id,
            entity_axis_ref=SelectedVariableBindingRef.model_validate(
                axis_ref.model_dump(mode="json")
            ),
            source_descriptor=source_meaning.source_descriptor,
            source_meaning_ref=source_meaning_ref,
            correspondence_ref=correspondence_ref,
        )
        if selection.binding_id in binding_ids:
            raise _AssessmentRefusal("entity_vector_binding_id_duplicate")
        binding_ids.add(selection.binding_id)
        entity_vector_steps.append(
            ResolvedEntityVectorInputAtStep(
                step_scope=subject.step_scope,
                selection=selection,
            )
        )

    retained_binding_ids = tuple(
        sorted(
            rule.binding_id
            for rule in original_input_bindings.rules
            if rule.target_slot_id in resolution.obligation_set.supplied_initial_slots
        )
    )
    manifest = ResolvedInputBindingManifest(
        schema_version="4.0",
        data_snapshot_ref=SelectedVariableBindingRef.model_validate(
            original_data_snapshot_ref.model_dump(mode="json")
        ),
        model_input_obligation_set_ref=SelectedVariableBindingRef.model_validate(
            selected_obligation_set_ref.model_dump(mode="json")
        ),
        entity_vector_steps=tuple(entity_vector_steps),
        retained_binding_ids=retained_binding_ids,
    )
    manifest_ref = persist_resolved_input_binding_manifest(store, manifest)
    reopened_manifest = load_resolved_input_binding_manifest(store, manifest_ref)
    if reopened_manifest != manifest:
        raise _AssessmentRefusal("entity_vector_manifest_readback_mismatch")
    return manifest_ref


def _persist_entity_vector_source_meaning(
    store: CoreJSONArtifactStore,
    source_meaning: SelectedEntityVectorSourceMeaning,
) -> SelectedEntityVectorSourceMeaningRef:
    """Persist and reopen one exact consumer-declared vector source view."""
    if type(source_meaning) is not SelectedEntityVectorSourceMeaning:
        raise _AssessmentRefusal("entity_vector_source_meaning_untyped")
    try:
        checked = SelectedEntityVectorSourceMeaning.model_validate(
            source_meaning.model_dump(mode="python")
        )
        raw_ref = store.put_json(
            checked,
            PutOptions(
                kind=checked.ARTIFACT_KIND,
                media_type=checked.ARTIFACT_MEDIA_TYPE,
                schema=SchemaInfo(
                    name=checked.ARTIFACT_SCHEMA_NAME,
                    version=checked.ARTIFACT_SCHEMA_VERSION,
                ),
                inputs=list(selected_entity_vector_source_meaning_manifest_inputs(checked)),
            ),
            return_selected_profile=True,
        )
        selected_ref = SelectedEntityVectorSourceMeaningRef.model_validate(
            raw_ref.model_dump(mode="json")
        )
        reopened = load_selected_entity_vector_source_meaning(store, selected_ref)
        if reopened != checked:
            raise _AssessmentRefusal("entity_vector_source_meaning_readback_mismatch")
        return selected_ref
    except _AssessmentRefusal:
        raise
    except (FileNotFoundError, OSError, TypeError, ValueError) as exc:
        raise _AssessmentRefusal(_entity_vector_refusal_code(exc)) from exc


def _persist_entity_vector_correspondence_basis(
    store: CoreJSONArtifactStore,
    basis: EntityVectorCorrespondenceBasis,
) -> EntityVectorCorrespondenceBasisRef:
    """Persist and reopen one exact candidate vector-to-port relation."""
    try:
        if type(basis) is not EntityVectorCorrespondenceBasis:
            raise _AssessmentRefusal("entity_vector_correspondence_basis_untyped")
        checked = EntityVectorCorrespondenceBasis.model_validate(basis.model_dump(mode="python"))
        inputs = list(entity_vector_correspondence_basis_manifest_inputs(checked))
        raw_ref = store.put_json(
            checked,
            PutOptions(
                kind=checked.ARTIFACT_KIND,
                media_type=checked.ARTIFACT_MEDIA_TYPE,
                schema=SchemaInfo(
                    name=checked.ARTIFACT_SCHEMA_NAME,
                    version=checked.ARTIFACT_SCHEMA_VERSION,
                ),
                inputs=inputs,
            ),
            return_selected_profile=True,
        )
        selected_ref = EntityVectorCorrespondenceBasisRef.model_validate(
            raw_ref.model_dump(mode="json")
        )
        reopened = load_entity_vector_correspondence_basis(store, selected_ref)
        if reopened != checked or store.get_manifest(selected_ref).inputs != inputs:
            raise _AssessmentRefusal("entity_vector_correspondence_basis_readback_mismatch")
        return selected_ref
    except _AssessmentRefusal:
        raise
    except (FileNotFoundError, OSError, TypeError, ValueError) as exc:
        raise _AssessmentRefusal(_entity_vector_refusal_code(exc)) from exc


def _load_reconciled_registry_bundle_content(
    store: CoreJSONArtifactStore,
    registry_bundle_ref: ArtifactRef,
) -> RegistryBundleContent:
    """Load selected registries only after the bundle and member edges reconcile."""
    selected_bundle_ref = _selected_exact_ref(store, registry_bundle_ref)
    try:
        bundle = load_registry_bundle(store, selected_bundle_ref)
        if artifact_ref_identity_key(bundle.bundle_ref) != artifact_ref_identity_key(
            selected_bundle_ref
        ):
            raise _AssessmentRefusal("entity_vector_registry_bundle_ref_mismatch")
        required = (
            (bundle.slot_registry, "slot_registry"),
            (bundle.merge_registry, "merge_registry"),
            (bundle.constraint_registry, "constraint_registry"),
            (bundle.mechanism_registry, "mechanism_registry"),
        )
        optional = (
            (bundle.selector_field_registry, "selector_field_registry"),
            (bundle.metric_registry, "metric_registry"),
            (bundle.units_registry, "units_registry"),
            (bundle.trust_registry, "trust_registry"),
            (bundle.predicate_registry, "predicate_registry"),
            (bundle.privacy_registry, "privacy_registry"),
        )
        registry_inputs = []
        for ref, role in required:
            if ref.manifest_profile_sha256 is None:
                raise _AssessmentRefusal("entity_vector_registry_member_profile_required")
            selected_ref = _selected_exact_ref(store, ref)
            if artifact_ref_identity_key(selected_ref) != artifact_ref_identity_key(ref):
                raise _AssessmentRefusal("entity_vector_registry_member_profile_mismatch")
            registry_inputs.append(input_ref_from_artifact_ref(selected_ref, role=role))
        for ref, role in optional:
            if ref is None:
                continue
            if ref.manifest_profile_sha256 is None:
                raise _AssessmentRefusal("entity_vector_registry_member_profile_required")
            selected_ref = _selected_exact_ref(store, ref)
            if artifact_ref_identity_key(selected_ref) != artifact_ref_identity_key(ref):
                raise _AssessmentRefusal("entity_vector_registry_member_profile_mismatch")
            registry_inputs.append(input_ref_from_artifact_ref(selected_ref, role=role))
        if tuple(store.get_manifest(selected_bundle_ref).inputs) != tuple(registry_inputs):
            raise _AssessmentRefusal("entity_vector_registry_bundle_lineage_mismatch")
        return load_registry_bundle_content(store, selected_bundle_ref)
    except _AssessmentRefusal:
        raise
    except (FileNotFoundError, OSError, TypeError, ValueError) as exc:
        raise _AssessmentRefusal(_entity_vector_refusal_code(exc)) from exc


def _require_exact_input_role(
    manifest: ArtifactManifest,
    role: str,
    ref: ArtifactRef,
    *,
    refusal_code: str,
) -> None:
    """Require one original selected input edge with exact identity/profile."""
    expected = input_ref_from_artifact_ref(ref, role=role)
    actual = tuple(edge for edge in manifest.inputs if edge.role == role)
    if actual != (expected,):
        raise _AssessmentRefusal(refusal_code)


def _replay_entity_vector_source_layout(
    store: CoreJSONArtifactStore,
    *,
    source_meaning: SelectedEntityVectorSourceMeaning,
    model_port: ModelInputPort,
    axis_ref: ArtifactRef,
    read_limits: CoreJsonReadLimits,
) -> SelectedEntityAxis:
    """Reopen generic JSON arrays and recompute their exact selected membership."""
    descriptor = source_meaning.source_descriptor
    try:
        source_view_ref = _selected_exact_ref(store, descriptor.source_view_ref)
        axis = validate_core_model_json_artifact(SelectedEntityAxis, store, axis_ref)
        if (
            axis.identity_basis != "selected_source_view"
            or axis.source_view_ref is None
            or artifact_ref_identity_key(axis.source_view_ref)
            != artifact_ref_identity_key(source_view_ref)
            or axis.member_values_pointer != descriptor.member_ids_pointer
            or model_port.entity_axis_ref is None
            or artifact_ref_identity_key(model_port.entity_axis_ref)
            != artifact_ref_identity_key(axis_ref)
            or model_port.physical_encoding is None
            or model_port.physical_encoding.shape != (axis.cardinality,)
            or axis.cardinality > read_limits.max_elements
        ):
            raise _AssessmentRefusal("entity_vector_source_axis_or_port_mismatch")
        if tuple(store.get_manifest(axis_ref).inputs) != (
            input_ref_from_artifact_ref(axis.source_view_ref, role="selected_source_view"),
        ):
            raise _AssessmentRefusal("entity_vector_axis_lineage_mismatch")

        source_read = read_core_json_artifact_bounded(store, source_view_ref, limits=read_limits)
        if artifact_ref_identity_key(source_read.effective_ref) != artifact_ref_identity_key(
            source_view_ref
        ):
            raise _AssessmentRefusal("entity_vector_source_view_profile_mismatch")
        payload = source_read.value
        if not isinstance(payload, Mapping):
            raise _AssessmentRefusal("entity_vector_source_json_container_invalid")
        member_values = _entity_vector_json_pointer(payload, descriptor.member_ids_pointer)
        numeric_values = _entity_vector_json_pointer(payload, descriptor.values_pointer)
        if (
            type(member_values) is not list
            or type(numeric_values) is not list
            or not member_values
            or len(member_values) != len(numeric_values)
            or len(member_values) != axis.cardinality
            or len(member_values) > read_limits.max_elements
        ):
            raise _AssessmentRefusal("entity_vector_source_parallel_array_layout_invalid")

        members: list[EntityAxisMemberId] = []
        for raw_member in member_values:
            if type(raw_member) is str and raw_member:
                members.append(EntityAxisMemberId(kind="string", value=raw_member))
            elif type(raw_member) is int:
                members.append(EntityAxisMemberId(kind="integer", value=raw_member))
            else:
                raise _AssessmentRefusal("entity_vector_source_member_id_invalid")
        member_tuple = tuple(members)
        member_keys = tuple(entity_axis_member_sort_key(member) for member in member_tuple)
        if (
            len(set(member_keys)) != len(member_keys)
            or tuple(sorted(member_tuple, key=entity_axis_member_sort_key)) != axis.members
        ):
            raise _AssessmentRefusal("entity_vector_source_axis_membership_mismatch")
        for value in numeric_values:
            if type(value) not in {int, float}:
                raise _AssessmentRefusal("entity_vector_source_numeric_value_invalid")
            try:
                finite = math.isfinite(value)
            except (OverflowError, TypeError, ValueError):
                finite = False
            if not finite:
                raise _AssessmentRefusal("entity_vector_source_numeric_value_invalid")
        return axis
    except _AssessmentRefusal:
        raise
    except (FileNotFoundError, OSError, TypeError, ValueError) as exc:
        raise _AssessmentRefusal(_entity_vector_refusal_code(exc)) from exc


def _entity_vector_json_pointer(payload: object, pointer: str) -> object:
    """Resolve the bounded RFC 6901 subset shared with the physical reader."""
    if not pointer.startswith("/") or pointer.endswith("/") or "//" in pointer:
        raise _AssessmentRefusal("entity_vector_source_pointer_invalid")
    current = payload
    for raw_token in pointer[1:].split("/"):
        if any(
            raw_token[index] == "~"
            and (index + 1 == len(raw_token) or raw_token[index + 1] not in "01")
            for index in range(len(raw_token))
        ):
            raise _AssessmentRefusal("entity_vector_source_pointer_invalid")
        token = raw_token.replace("~1", "/").replace("~0", "~")
        if isinstance(current, Mapping):
            if token not in current:
                raise _AssessmentRefusal("entity_vector_source_pointer_missing")
            current = current[token]
        elif type(current) is list and token.isdecimal():
            index = int(token)
            if index >= len(current):
                raise _AssessmentRefusal("entity_vector_source_pointer_missing")
            current = current[index]
        else:
            raise _AssessmentRefusal("entity_vector_source_pointer_missing")
    return current


def _entity_vector_refusal(code: str) -> ScopedCorrespondenceEvaluation:
    """Return one explicit candidate-only refusal with the mandatory limits."""
    return ScopedCorrespondenceEvaluation(
        status="refused",
        semantic_correspondence="not_established",
        limitation_codes=ENTITY_VECTOR_CANDIDATE_LIMITATIONS,
        refusal_codes=(code,),
    )


def _entity_vector_refusal_code(exc: BaseException) -> str:
    """Keep stable typed refusal codes and collapse unstructured errors safely."""
    value = getattr(exc, "code", None)
    if not isinstance(value, str):
        value = str(exc).strip()
    if (
        value
        and len(value) <= 128
        and all(
            character.islower() or character.isdigit() or character == "_" for character in value
        )
    ):
        return value
    return "entity_vector_selected_source_replay_failed"


def _entity_vector_binding_id(
    port_id: str,
    step: int,
    source_meaning_ref: SelectedEntityVectorSourceMeaningRef,
) -> str:
    """Derive a stable collision-resistant ID from the complete selected input identity."""
    canonical = json.dumps(
        [port_id, step, list(artifact_ref_identity_key(source_meaning_ref))],
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return "entity-vector-" + hashlib.sha256(canonical).hexdigest()[:32]


__all__ = [
    "assess_entity_vector_to_model_candidate",
    "assess_measurement_to_model_candidate",
    "materialize_activated_measurement_occurrence",
    "prepare_registered_entity_vector_input_steps",
    "read_scoped_measurement_source_body",
    "replay_selected_scoped_measurement_facts",
]
