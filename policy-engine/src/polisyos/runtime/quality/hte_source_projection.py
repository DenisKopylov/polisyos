"""Resolve candidate HTE source roles to exact selected DataForge profile rows.

This adapter reuses the existing ValueOwner source-assignment and DataForge
profile artifacts. It proves a content join for the selected HTE input only;
the role choice remains consumer asserted, while owner issuance, semantic
alignment, and source time remain unestablished. Selected CAS and projection
digests establish internal consistency only; active-owner provenance requires
the existing catalog receipt/passport readback and is not inferred here.
"""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Sequence
from typing import TYPE_CHECKING, NoReturn

import numpy as np

from polisyos.core.artifacts import (
    CoreJSONArtifactBoundedMemberReader,
    matches_runtime_protocol,
    read_core_json_artifact_bounded,
    validate_core_model_bounded_read,
)
from polisyos.core.artifacts.manifest import (
    ArtifactManifest,
    ArtifactRef,
    InputRef,
    SchemaInfo,
    artifact_ref_identity_key,
)
from polisyos.data_forge.domains.catalog.knowledge.overlay import (
    ActivatedAcquisitionObservationProjection,
)
from polisyos.foundry.data_plane.bindings import materialize_method_contract
from polisyos.foundry.methods.catalog.causal.protocols import HTEObservationalData
from polisyos.ir.observation.bundles import (
    HTE_OBSERVATIONAL_DATA_CONTRACT_FQN,
    HTE_OBSERVATIONAL_DATA_CONTRACT_ID,
    OBSERVATION_METHOD_INPUT_KIND,
    OBSERVATION_METHOD_INPUT_SCHEMA_NAME,
    OBSERVATION_METHOD_INPUT_SCHEMA_VERSION,
    ObservationMethodInputEnvelope,
)
from polisyos.scientist.methods.search.uncertainty import (
    SearchHTESourceProjectionError as HTESourceProjectionError,
)
from polisyos.scientist.methods.search.uncertainty import (
    SearchHTESourceProjectionJoin as HTESourceProjectionJoin,
)

if TYPE_CHECKING:
    from pydantic import BaseModel

    from polisyos.core.artifacts.canonical_profile import (
        CoreJsonArtifactBoundedRead,
        CoreJsonReadLimits,
    )
    from polisyos.runtime.quality.generation_cycle import (
        ValueArtifactBindingRefV1,
        ValueDataProfile,
        ValueOwnerRow,
    )
    from polisyos.scientist.methods.search.uncertainty import (
        SearchHTESourceProjectionBasis,
        SearchUncertaintyHTERequestProjection,
        SearchUncertaintyStore,
    )

SOURCE_VARIABLE_ASSIGNMENT_ROLE = "source_variable_assignment"
SOURCE_VARIABLE_ASSIGNMENT_KIND = "runtime.value_owner_source_variable_assignment"
SOURCE_VARIABLE_ASSIGNMENT_SCHEMA = SchemaInfo(
    name="runtime.value_owner_source_variable_assignment.v1",
    version="1.0",
)
VALUE_DATA_PROFILE_KIND = "runtime.value_data_profile"
VALUE_DATA_PROFILE_SCHEMA = SchemaInfo(name="runtime.value_data_profile.v2", version="2.0")
VALUE_SOURCE_PROJECTION_KIND = "runtime.value_owner_source_projection"
VALUE_SOURCE_PROJECTION_SCHEMA = SchemaInfo(
    name="runtime.value_owner_source_projection.v1",
    version="1.0",
)


def _refuse(reason_code: str) -> NoReturn:
    raise HTESourceProjectionError(reason_code)


def _read_model[ModelT: BaseModel](
    store: CoreJSONArtifactBoundedMemberReader,
    ref: ArtifactRef,
    *,
    limits: CoreJsonReadLimits,
    model_type: type[ModelT],
    kind: str,
    schema: SchemaInfo,
    failure_code: str,
) -> tuple[CoreJsonArtifactBoundedRead, ModelT]:
    try:
        selected = read_core_json_artifact_bounded(store, ref, limits=limits)
    except Exception as exc:
        raise HTESourceProjectionError(failure_code) from exc
    if (
        artifact_ref_identity_key(selected.effective_ref) != artifact_ref_identity_key(ref)
        or selected.manifest.kind != kind
        or selected.manifest.media_type != "application/json"
        or selected.manifest.artifact_schema != schema
    ):
        _refuse(failure_code)
    try:
        model = validate_core_model_bounded_read(model_type, selected)
    except Exception as exc:
        raise HTESourceProjectionError(failure_code) from exc
    return selected, model


def _value_ref(ref: ValueArtifactBindingRefV1, *, kind: str) -> ArtifactRef:
    try:
        artifact_ref = ArtifactRef(
            artifact_id=ref.artifact_id,
            kind=kind,
            media_type=ref.media_type,
            manifest_profile_sha256=ref.manifest_profile_sha256,
        )
    except Exception as exc:
        raise HTESourceProjectionError("source_owner_ref_invalid") from exc
    if artifact_ref.manifest_profile_sha256 is None:
        _refuse("source_owner_ref_unprofiled")
    return artifact_ref


def _edge_key(edge: InputRef) -> tuple[str, str, str | None]:
    return (str(edge.artifact_id), edge.role, edge.manifest_profile_sha256)


def _require_exact_inputs(
    manifest: ArtifactManifest, expected: Sequence[tuple[ArtifactRef, str]]
) -> None:
    observed = manifest.inputs
    if not isinstance(observed, Sequence) or isinstance(observed, str | bytes | bytearray):
        _refuse("source_owner_lineage_unavailable")
    actual_edges = Counter(_edge_key(edge) for edge in observed)
    expected_edges = Counter(
        (
            str(ref.artifact_id),
            role,
            ref.manifest_profile_sha256,
        )
        for ref, role in expected
    )
    if actual_edges != expected_edges:
        _refuse("source_owner_lineage_mismatch")


def _profile_rows_from_projection(
    projection: ActivatedAcquisitionObservationProjection,
) -> tuple[ValueOwnerRow, ...]:
    """Use the owner intake without assigning a country or unit conversion.

    The supplied CAS snapshot is candidate content, not a current owner read.
    Only its declared coordinates enter this join. An owner-normalized scope or
    registered conversion must already be represented by an exact matching
    profile; this reader never fills it in from a country string or role label.
    """
    from polisyos.runtime.quality import generation_cycle as gc

    raw_rows: list[tuple[str, int, float, str, str, object]] = []
    for projected in projection.observations:
        observation = projected.observation
        period_id = (
            observation.year
            if observation.year is not None
            else observation.survey_year
            if observation.survey_year is not None
            else observation.wave
        )
        if type(period_id) is not int:
            _refuse("source_projection_time_coordinate_not_supported")
        raw_rows.append(
            (
                observation.country_code,
                period_id,
                observation.value,
                observation.dataset_id,
                observation.observation_id,
                observation.condition_json,
            )
        )
    try:
        selected_rows = gc._value_owner_rows_from_source_rows(
            outcome=projection.variable_id,
            raw_rows=raw_rows,
            owner_access_ref="selected_hte_source_projection:internal_consistency_only",
            registered_measurement_units_by_id={},
        )
    except gc.ValueOwnerAccessError as exc:
        raise HTESourceProjectionError(exc.code) from exc
    except (TypeError, ValueError, OverflowError) as exc:
        # Malformed optional source metadata cannot discard an independently
        # verified native point/interval. Programming/backend errors still
        # propagate rather than being relabeled as a source-data refusal.
        raise HTESourceProjectionError("source_projection_rows_invalid") from exc
    if selected_rows is None:
        _refuse("source_projection_rows_missing")
    owner_rows, _measurement_unit = selected_rows
    return owner_rows


def _cell_values(profile: ValueDataProfile) -> dict[tuple[str, int], float]:
    result: dict[tuple[str, int], float] = {}
    for row in profile.rows:
        key = (row.unit_id, row.period_id)
        if (
            key in result
            or row.measurement_unit != profile.measurement_unit
            or not math.isfinite(row.outcome_value)
        ):
            _refuse("source_profile_rows_invalid")
        result[key] = float(row.outcome_value)
    if not result:
        _refuse("source_profile_rows_missing")
    return result


def verify_hte_source_projection_join(
    *,
    store: SearchUncertaintyStore,
    selected_method_input_ref: ArtifactRef,
    basis: SearchHTESourceProjectionBasis,
    request_projection: SearchUncertaintyHTERequestProjection,
    limits: CoreJsonReadLimits,
) -> HTESourceProjectionJoin:
    """Recompute the assignment/profile/array join for one selected HTE input.

    Only existing selected refs and owner rows participate. A missing or
    mismatched edge cannot make a score available, even when a basis carries a
    unit-scope ref.
    """
    if not matches_runtime_protocol(store, CoreJSONArtifactBoundedMemberReader):
        _refuse("source_projection_store_unavailable")
    if (
        basis.unit_binding_status != "bound"
        or basis.unit_scope_ref is None
        or artifact_ref_identity_key(basis.selected_method_input_ref)
        != artifact_ref_identity_key(selected_method_input_ref)
    ):
        _refuse("source_unit_scope_not_frozen_in_basis")

    from polisyos.runtime.quality import generation_cycle as gc

    if (
        selected_method_input_ref.kind != OBSERVATION_METHOD_INPUT_KIND
        or selected_method_input_ref.media_type != "application/json"
        or selected_method_input_ref.manifest_profile_sha256 is None
    ):
        _refuse("selected_hte_input_ref_invalid")
    source_read, envelope = _read_model(
        store,
        selected_method_input_ref,
        limits=limits,
        model_type=ObservationMethodInputEnvelope,
        kind=OBSERVATION_METHOD_INPUT_KIND,
        schema=SchemaInfo(
            name=OBSERVATION_METHOD_INPUT_SCHEMA_NAME,
            version=OBSERVATION_METHOD_INPUT_SCHEMA_VERSION,
        ),
        failure_code="selected_hte_input_unavailable",
    )
    if (
        envelope.contract_target.contract_id != HTE_OBSERVATIONAL_DATA_CONTRACT_ID
        or envelope.contract_target.contract_fqn != HTE_OBSERVATIONAL_DATA_CONTRACT_FQN
    ):
        _refuse("selected_hte_input_target_mismatch")
    assignment_edges = [
        edge for edge in source_read.manifest.inputs if edge.role == SOURCE_VARIABLE_ASSIGNMENT_ROLE
    ]
    if len(assignment_edges) != 1 or assignment_edges[0].manifest_profile_sha256 is None:
        _refuse("source_assignment_edge_missing_or_ambiguous")
    assignment_edge = assignment_edges[0]
    assignment_ref = ArtifactRef(
        artifact_id=assignment_edge.artifact_id,
        kind=SOURCE_VARIABLE_ASSIGNMENT_KIND,
        media_type="application/json",
        manifest_profile_sha256=assignment_edge.manifest_profile_sha256,
    )
    selected_assignment_edges = [
        item
        for item in basis.selected_state_input_refs
        if getattr(item, "role_path", None) == SOURCE_VARIABLE_ASSIGNMENT_ROLE
    ]
    if (
        len(selected_assignment_edges) != 1
        or getattr(selected_assignment_edges[0], "ref", None) is None
        or artifact_ref_identity_key(selected_assignment_edges[0].ref)
        != artifact_ref_identity_key(assignment_ref)
    ):
        _refuse("source_assignment_ref_not_frozen_in_basis")

    assignment_read, assignment = _read_model(
        store,
        assignment_ref,
        limits=limits,
        model_type=gc.ValueOwnerSourceVariableAssignmentV1,
        kind=SOURCE_VARIABLE_ASSIGNMENT_KIND,
        schema=SOURCE_VARIABLE_ASSIGNMENT_SCHEMA,
        failure_code="source_assignment_artifact_unavailable",
    )
    assignment_inputs = [
        edge
        for role_profile in assignment.role_profiles
        for edge in (
            (
                _value_ref(role_profile.profile_ref, kind=VALUE_DATA_PROFILE_KIND),
                f"selected_source_profile:{role_profile.role}:{role_profile.variable_id}",
            ),
            (
                _value_ref(role_profile.projection_ref, kind=VALUE_SOURCE_PROJECTION_KIND),
                f"selected_source_projection:{role_profile.role}:{role_profile.variable_id}",
            ),
        )
    ]
    _require_exact_inputs(assignment_read.manifest, assignment_inputs)

    profiles: dict[str, ValueDataProfile] = {}
    for role_profile in assignment.role_profiles:
        profile_ref = _value_ref(role_profile.profile_ref, kind=VALUE_DATA_PROFILE_KIND)
        projection_ref = _value_ref(
            role_profile.projection_ref,
            kind=VALUE_SOURCE_PROJECTION_KIND,
        )
        projection_read, projection = _read_model(
            store,
            projection_ref,
            limits=limits,
            model_type=ActivatedAcquisitionObservationProjection,
            kind=VALUE_SOURCE_PROJECTION_KIND,
            schema=VALUE_SOURCE_PROJECTION_SCHEMA,
            failure_code="source_projection_artifact_unavailable",
        )
        del projection_read
        if (
            projection.variable_id != role_profile.variable_id
            or projection.activation_state != "active"
            or projection.predicate_provenance != "recomputed"
            or projection.source_time_status != "not_established"
        ):
            _refuse("source_projection_profile_mismatch")
        profile_read, profile = _read_model(
            store,
            profile_ref,
            limits=limits,
            model_type=gc.ValueDataProfile,
            kind=VALUE_DATA_PROFILE_KIND,
            schema=VALUE_DATA_PROFILE_SCHEMA,
            failure_code="source_profile_artifact_unavailable",
        )
        _require_exact_inputs(
            profile_read.manifest,
            ((projection_ref, "activated_source_projection"),),
        )
        if (
            profile.content_hash != role_profile.profile_content_hash
            or profile.outcome != role_profile.variable_id
            or profile.measurement_unit != role_profile.measurement_unit
            or tuple(profile.rows) != _profile_rows_from_projection(projection)
        ):
            _refuse("source_profile_projection_content_mismatch")
        profiles[role_profile.variable_id] = profile

    outcome_roles = [item for item in assignment.role_profiles if item.role == "outcome"]
    treatment_roles = [item for item in assignment.role_profiles if item.role == "treatment"]
    covariate_roles = [item for item in assignment.role_profiles if item.role == "covariate"]
    if len(outcome_roles) != 1 or len(treatment_roles) != 1 or not covariate_roles:
        _refuse("source_assignment_role_set_invalid")
    outcome_role = outcome_roles[0]
    treatment_role = treatment_roles[0]
    if (
        outcome_role.variable_id != request_projection.outcome_variable_id
        or treatment_role.variable_id != request_projection.treatment_variable_id
    ):
        _refuse("source_request_role_mismatch")
    outcome_profile_ref = _value_ref(
        outcome_role.profile_ref,
        kind=VALUE_DATA_PROFILE_KIND,
    )
    if basis.unit_scope_ref is None or artifact_ref_identity_key(
        basis.unit_scope_ref
    ) != artifact_ref_identity_key(outcome_profile_ref):
        _refuse("source_unit_scope_profile_mismatch")

    cell_values = {variable_id: _cell_values(profile) for variable_id, profile in profiles.items()}
    cell_sets = [set(values) for values in cell_values.values()]
    if not cell_sets or any(cells != cell_sets[0] for cells in cell_sets[1:]):
        _refuse("source_profiles_do_not_share_complete_rows")
    cells = tuple(sorted(cell_sets[0]))

    try:
        data = materialize_method_contract(
            contract_target=envelope.contract_target,
            contract_payload=envelope.contract_payload,
        )
    except Exception as exc:
        raise HTESourceProjectionError("selected_hte_input_materialization_refused") from exc
    if type(data) is not HTEObservationalData:
        _refuse("selected_hte_input_materializer_mismatch")

    expected_sample_ids = tuple(f"{unit_id}:{period_id}" for unit_id, period_id in cells)
    if (
        data.sample_ids is None
        or tuple(np.asarray(data.sample_ids).tolist()) != expected_sample_ids
    ):
        _refuse("source_profile_sample_ids_mismatch")
    expected_outcome = np.asarray(
        [cell_values[outcome_role.variable_id][cell] for cell in cells],
        dtype=float,
    )
    expected_treatment = np.asarray(
        [cell_values[treatment_role.variable_id][cell] for cell in cells],
        dtype=float,
    )
    if not np.array_equal(np.asarray(data.outcome), expected_outcome):
        _refuse("source_outcome_array_mismatch")
    if not np.array_equal(np.asarray(data.treatment), expected_treatment):
        _refuse("source_treatment_array_mismatch")
    observed_treatments = {float(value) for value in np.asarray(data.treatment).tolist()}
    requested_treatments = {
        float(request_projection.control_value),
        float(request_projection.treated_value),
    }
    if observed_treatments != requested_treatments:
        _refuse("source_treatment_contrast_values_mismatch")

    feature_names = data.feature_names
    if (
        feature_names is None
        or any(type(name) is not str or not name.strip() for name in feature_names)
        or len(feature_names) != len(set(feature_names))
    ):
        _refuse("source_feature_role_names_missing_or_ambiguous")
    confounders = data.confounders
    confounder_names = data.confounder_names
    if confounders is None:
        if confounder_names not in (None, []):
            _refuse("source_confounder_role_names_without_array")
        confounder_names = []
    elif (
        confounder_names is None
        or any(type(name) is not str or not name.strip() for name in confounder_names)
        or len(confounder_names) != len(set(confounder_names))
    ):
        _refuse("source_confounder_role_names_missing_or_ambiguous")
    all_covariate_names = tuple(feature_names) + tuple(confounder_names)
    if len(all_covariate_names) != len(set(all_covariate_names)) or set(all_covariate_names) != {
        item.variable_id for item in covariate_roles
    }:
        _refuse("source_covariate_role_map_mismatch")
    if np.asarray(data.covariates).shape[1] != len(feature_names):
        _refuse("source_feature_array_shape_mismatch")
    for index, variable_id in enumerate(feature_names):
        expected = np.asarray(
            [cell_values[variable_id][cell] for cell in cells],
            dtype=float,
        )
        if not np.array_equal(np.asarray(data.covariates)[:, index], expected):
            _refuse("source_feature_array_mismatch")
    if confounders is not None:
        if np.asarray(confounders).shape[1] != len(confounder_names):
            _refuse("source_confounder_array_shape_mismatch")
        for index, variable_id in enumerate(confounder_names):
            expected = np.asarray(
                [cell_values[variable_id][cell] for cell in cells],
                dtype=float,
            )
            if not np.array_equal(np.asarray(confounders)[:, index], expected):
                _refuse("source_confounder_array_mismatch")

    return HTESourceProjectionJoin(
        selected_method_input_ref=selected_method_input_ref,
        assignment_ref=assignment_ref,
        outcome_profile_ref=outcome_profile_ref,
    )
