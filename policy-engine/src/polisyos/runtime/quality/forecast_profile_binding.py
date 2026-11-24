"""Bind selected Data Forge series and forecast outcomes to their owners.

This adapter belongs in runtime quality because it consumes Data Forge's
projection and the runtime-owned EMP-01 profile. Calibration and Scientist
receive the typed Core candidate receipt. Runtime can separately reconcile that
series for a supported N4 observed-level target.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, ConfigDict

from polisyos.core.artifacts import (
    ArtifactRef,
    ArtifactStore,
    artifact_ref_for_manifest,
    artifact_ref_identity_key,
    input_ref_from_artifact_ref,
    load_core_json_artifact,
    read_core_manifest_profile,
    validate_core_model_json_artifact,
)
from polisyos.core.contracts.fabric import DataSnapshot
from polisyos.core.contracts.forecast_profile_member import (
    FORECAST_PROFILE_MEMBER_CONTRACT_VERSION,
    FORECAST_PROFILE_MEMBER_KIND,
    FORECAST_PROFILE_MEMBER_SCHEMA,
    FORECAST_PROFILE_MEMBER_SCHEMA_VERSION,
    VALUE_DATA_PROFILE_KIND,
    VALUE_OWNER_PROJECTION_KIND,
    ForecastProfileMemberV1,
    forecast_profile_observed_series_sha256,
)
from polisyos.core.contracts.model_input_requirements import (
    ModelInputPort,
    load_model_input_port_declaration,
    verify_model_input_port_semantics,
)
from polisyos.core.contracts.variable_binding import (
    MeasurementAxis,
    MeasurementBindingProfile,
    MeasurementBindingProfileRef,
    ModelInputScope,
    VariableRepresentationRef,
    VariableSemanticDefinition,
    VariableSemanticDefinitionRef,
    compare_measurement_representation_axes,
    load_variable_representation,
)
from polisyos.data_forge.read_api.catalog import (
    AcquisitionAuthorityEntry,
    ActivatedAcquisitionObservationProjection,
    iso2_to_iso3,
    normalize_country_code,
)
from polisyos.runtime.quality.generation_cycle import (
    ValueDataProfile,
    ValueOwnerRow,
    _measurement_unit_from_condition_json,
    _value_owner_row,
)

VALUE_DATA_PROFILE_SCHEMA = "runtime.value_data_profile.v2"
VALUE_DATA_PROFILE_SCHEMA_VERSION = "2.0"
VALUE_OWNER_PROJECTION_SCHEMA = "runtime.value_owner_source_projection.v1"
VALUE_OWNER_PROJECTION_SCHEMA_VERSION = "1.0"

if TYPE_CHECKING:
    from polisyos.core.artifacts import InputRef
    from polisyos.ir import ArtifactRefModel
    from polisyos.runtime.quality.generation_source import N4CandidateScenarioSourceRecordV3


@dataclass(frozen=True)
class ResolvedValueProfileProjection:
    """Canonical selected profile and its exact activated source projection."""

    profile: ValueDataProfile
    source_projection_ref: ArtifactRefModel
    projection: ActivatedAcquisitionObservationProjection
    source_passport: object


def _registered_wdi_unit(
    *, observation: object, unit_id: str, profile: ValueDataProfile, passport: object | None
) -> str | None:
    """Resolve only the canonical owner's declared identity WDI unit binding."""

    if passport is None:
        return None
    observed_unit = getattr(observation, "country_code", None)
    try:
        iso3 = iso2_to_iso3(unit_id)
        normalized = normalize_country_code(observed_unit)
    except Exception:
        return None
    registration = getattr(passport, "registration", None)
    binding = getattr(passport, "field_binding", None)
    live_source = getattr(passport, "live_source_execution", None)
    authorization = getattr(live_source, "authorization", None)
    if (
        normalized != unit_id
        or observed_unit != iso3
        or getattr(passport, "source_lane", None) != "live_fetch"
        or getattr(passport, "variable_id", None) != profile.outcome
        or getattr(registration, "connector_id", None) != "worldbank.wdi"
        or getattr(registration, "catalog_dataset_id", None)
        != getattr(observation, "dataset_id", None)
        or observed_unit not in getattr(registration, "country_codes", ())
        or getattr(binding, "canonical_variable", None) != profile.outcome
        or getattr(binding, "canonical_unit", None) != profile.measurement_unit
        or getattr(binding, "raw_unit", None) != profile.measurement_unit
        or getattr(binding, "unit_transform", None) != "identity"
        or getattr(authorization, "connector_id", None) != "worldbank.wdi"
        or getattr(authorization, "profile_id", None)
        != getattr(registration, "source_profile_id", None)
        or getattr(authorization, "request_variables", None)
        != (getattr(registration, "request_dataset_id", None),)
    ):
        return None
    return profile.measurement_unit


def _profile_source_rows_for_unit_period(
    *,
    profile: ValueDataProfile,
    row: ValueOwnerRow,
    projection: ActivatedAcquisitionObservationProjection,
    passport: object | None,
) -> tuple[tuple[float, str, str, str], ...]:
    source_rows: list[tuple[float, str, str, str]] = []
    for projected in projection.observations:
        observation = projected.observation
        period_id = (
            observation.year
            if observation.year is not None
            else observation.survey_year
            if observation.survey_year is not None
            else observation.wave
        )
        if observation.canonical_var != profile.outcome or period_id != row.period_id:
            continue
        if observation.country_code == row.unit_id:
            try:
                measurement_unit = _measurement_unit_from_condition_json(observation.condition_json)
            except Exception as exc:
                raise ValueError("forecast_profile_member_source_measurement_unit_invalid") from exc
        else:
            measurement_unit = _registered_wdi_unit(
                observation=observation,
                unit_id=row.unit_id,
                profile=profile,
                passport=passport,
            )
            if measurement_unit is None:
                continue
        if measurement_unit is None:
            raise ValueError("forecast_profile_member_source_measurement_unit_missing")
        if measurement_unit != profile.measurement_unit:
            raise ValueError("forecast_profile_member_source_measurement_unit_mismatch")
        source_rows.append(
            (
                float(observation.value),
                observation.dataset_id,
                observation.observation_id,
                measurement_unit,
            )
        )
    if not source_rows:
        raise ValueError("forecast_profile_member_source_row_binding_mismatch")
    return tuple(source_rows)


def validate_profile_projection_binding(
    *,
    profile: ValueDataProfile,
    projection_payload: object,
    passport_payload: object | None = None,
    require_canonical_owner_profile_shape: bool = False,
) -> ActivatedAcquisitionObservationProjection:
    """Recompute every profile row from its full selected source-row set.

    ``require_canonical_owner_profile_shape`` applies the current canonical
    EMP-01 producer's refusal rules at the Runtime admission boundary. The
    default keeps this primitive usable for bounded candidate-only tuple
    calculations that do not enter the served profile path.
    """

    try:
        projection = ActivatedAcquisitionObservationProjection.model_validate(projection_payload)
    except Exception as exc:
        raise ValueError("forecast_profile_member_source_projection_invalid") from exc
    if (
        projection.variable_id != profile.outcome
        or projection.activation_state != "active"
        or projection.predicate_provenance != "recomputed"
        or projection.source_time_status != "not_established"
    ):
        raise ValueError("forecast_profile_member_source_projection_binding_mismatch")
    passport: object | None = None
    if passport_payload is not None:
        from polisyos.fabric.data_plane import content_sha256
        from polisyos.runtime.quality.acquisition_executor import AdmissionPassport

        try:
            passport = AdmissionPassport.model_validate(passport_payload)
        except Exception as exc:
            raise ValueError("forecast_profile_member_source_passport_invalid") from exc
        if (
            passport.passport_id != projection.passport_id
            or passport.epoch_id != projection.epoch_id
            or passport.variable_id != projection.variable_id
            or content_sha256(passport_payload) != projection.passport_content_sha256
        ):
            raise ValueError("forecast_profile_member_source_passport_binding_mismatch")
    matched_observation_ids: set[str] = set()
    source_dataset_ids: set[str] = set()
    for row in profile.rows:
        source_rows = _profile_source_rows_for_unit_period(
            profile=profile,
            row=row,
            projection=projection,
            passport=passport,
        )
        if require_canonical_owner_profile_shape:
            if len(source_rows) != 1:
                raise ValueError("forecast_profile_member_source_row_binding_ambiguous")
            dataset_id = source_rows[0][1].strip()
            if not dataset_id:
                raise ValueError("forecast_profile_member_source_dataset_missing")
            source_dataset_ids.add(dataset_id)
        recomputed = _value_owner_row(
            outcome=profile.outcome,
            unit_id=row.unit_id,
            period_id=row.period_id,
            source_rows=source_rows,
        )
        if recomputed != row:
            raise ValueError("forecast_profile_member_source_row_binding_mismatch")
        observation_ids = {source_row[2] for source_row in source_rows}
        if len(observation_ids) != len(source_rows) or matched_observation_ids.intersection(
            observation_ids
        ):
            raise ValueError("forecast_profile_member_source_row_binding_ambiguous")
        matched_observation_ids.update(observation_ids)
    if require_canonical_owner_profile_shape and len(source_dataset_ids) != 1:
        raise ValueError("forecast_profile_member_source_dataset_ambiguous")
    return projection


def join_profile_member_to_observed_series(
    *,
    profile: ValueDataProfile,
    profile_ref: ArtifactRefModel,
    source_projection_ref: ArtifactRefModel,
    projection: ActivatedAcquisitionObservationProjection,
    observed_source_ref: ArtifactRefModel,
    observed_data_ref: ArtifactRefModel,
    target_metric: str,
    unit_id: str,
    observed_values: object,
    source_passport: object | None = None,
) -> tuple[ForecastProfileMemberV1, tuple[float, ...]]:
    """Join one canonically recomputed profile member to observed values."""

    if profile_ref.kind != VALUE_DATA_PROFILE_KIND:
        raise ValueError("forecast_profile_member_profile_kind_mismatch")
    if (
        profile_ref.media_type != "application/json"
        or profile_ref.manifest_profile_sha256 is None
        or source_projection_ref.kind != VALUE_OWNER_PROJECTION_KIND
        or source_projection_ref.media_type != "application/json"
        or source_projection_ref.manifest_profile_sha256 is None
    ):
        raise ValueError("forecast_profile_member_profile_ref_unbound")
    projection = validate_profile_projection_binding(
        profile=profile,
        projection_payload=projection.model_dump(mode="json"),
        passport_payload=(
            None if source_passport is None else source_passport.model_dump(mode="json")
        ),
    )
    if not target_metric or target_metric != target_metric.strip():
        raise ValueError("forecast_profile_member_target_metric_invalid")
    if not unit_id or unit_id != unit_id.strip():
        raise ValueError("forecast_profile_member_unit_id_invalid")
    if profile.outcome != target_metric:
        raise ValueError("forecast_profile_member_outcome_target_mismatch")
    digest = forecast_profile_observed_series_sha256(observed_values)
    values = tuple(float(value) for value in observed_values)
    selected_rows = sorted(
        (row for row in profile.rows if row.unit_id == unit_id),
        key=lambda row: row.period_id,
    )
    if not selected_rows:
        raise ValueError("forecast_profile_member_unit_not_found")
    periods = tuple(row.period_id for row in selected_rows)
    if len(set(periods)) != len(periods):
        raise ValueError("forecast_profile_member_duplicate_unit_period")
    row_values = tuple(row.outcome_value for row in selected_rows)
    if row_values != values:
        raise ValueError("forecast_profile_member_observed_series_mismatch")
    row_payloads = tuple(row.model_dump(mode="json") for row in selected_rows)
    receipt = ForecastProfileMemberV1(
        schema_version=FORECAST_PROFILE_MEMBER_CONTRACT_VERSION,
        status="joined_candidate",
        profile_ref=profile_ref,
        profile_content_hash=profile.content_hash,
        source_projection_ref=source_projection_ref,
        source_projection_content_sha256=projection.projection_content_sha256,
        observed_source_ref=observed_source_ref,
        observed_data_ref=observed_data_ref,
        target_metric=target_metric,
        unit_id=unit_id,
        outcome=profile.outcome,
        measurement_unit=profile.measurement_unit,
        period_ids=periods,
        row_content_hashes=tuple(row.row_content_hash for row in selected_rows),
        selected_rows_content_hash=_canonical_digest(row_payloads),
        observed_series_sha256=digest,
        row_count=len(selected_rows),
        treatment_assignment_status=profile.treatment_assignment_status,
    )
    return receipt, row_values


FORECAST_OUTCOME_LEVEL_RELATION_KIND = "runtime.forecast_outcome_level_relation"
FORECAST_OUTCOME_LEVEL_RELATION_SCHEMA = "polisyos.runtime.ForecastOutcomeLevelRelation"
FORECAST_OUTCOME_LEVEL_RELATION_VERSION = "1.0"
OBSERVED_OUTCOME_LEVEL_ESTIMAND = "observed_outcome_level"


class ForecastOutcomeLevelRelationV1(BaseModel):
    """Recomputed same-definition relation for a finite observed-level series."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["polisyos.runtime.forecast_outcome_level_relation.v1"] = (
        "polisyos.runtime.forecast_outcome_level_relation.v1"
    )
    candidate_source_ref: ArtifactRef
    observed_member_ref: ArtifactRef
    value_data_profile_ref: ArtifactRef
    observed_source_ref: ArtifactRef
    source_passport_ref: ArtifactRef
    world_model_content_hash: str
    model_spec_ref: ArtifactRef
    model_port_declaration_ref: ArtifactRef
    model_port_id: str
    target_variable: str
    n4_metric_id: str
    observed_target_metric: str
    semantic_definition_ref: VariableSemanticDefinitionRef
    source_representation_ref: VariableRepresentationRef
    target_representation_ref: VariableRepresentationRef
    binding_profile_ref: MeasurementBindingProfileRef
    measurement_unit: str
    observed_scope: ModelInputScope
    source_dataset_version: str
    recomputed_axes: tuple[MeasurementAxis, ...]
    optional_unknown_axes: tuple[MeasurementAxis, ...]
    transformation: Literal["identity"] = "identity"
    authority_scope: Literal["predictive_only"] = "predictive_only"
    issuer_status: Literal["not_established"] = "not_established"
    population_scope_status: Literal["not_established"] = "not_established"
    source_time_status: Literal["not_established"] = "not_established"


def forecast_outcome_level_relation_inputs(
    relation: ForecastOutcomeLevelRelationV1,
) -> tuple[InputRef, ...]:
    """Return the exact dependencies of the recomputed candidate relation."""
    return tuple(
        input_ref_from_artifact_ref(ref, role=role)
        for role, ref in (
            ("candidate_source", relation.candidate_source_ref),
            ("forecast_profile_member", relation.observed_member_ref),
            ("value_data_profile", relation.value_data_profile_ref),
            ("observed_source", relation.observed_source_ref),
            ("source_passport", relation.source_passport_ref),
            ("model_spec", relation.model_spec_ref),
            ("model_port_declaration", relation.model_port_declaration_ref),
            ("semantic_definition", relation.semantic_definition_ref),
            ("source_representation", relation.source_representation_ref),
            ("target_representation", relation.target_representation_ref),
            ("measurement_binding_profile", relation.binding_profile_ref),
        )
    )


def build_forecast_outcome_level_relation(
    store: ArtifactStore,
    *,
    candidate_source_ref: ArtifactRef,
    candidate_source: N4CandidateScenarioSourceRecordV3,
    model_spec_ref: ArtifactRef,
    observed_member_ref: ArtifactRef,
    value_data_profile_ref: ArtifactRef,
    resolved_profile: ResolvedValueProfileProjection,
) -> ForecastOutcomeLevelRelationV1:
    """Project one bounded identity relation from the selected N4 and Catalog owners.

    The caller obtains the candidate and current Catalog profile through their
    stock scoped readers. This projection verifies the named model and observed
    evidence and can be rederived by the same caller on fresh read. The finite
    matching sample grants no upstream source or causal authority.
    """
    from polisyos.core.registry import load_registry_bundle_content
    from polisyos.ir import ModelSpec
    from polisyos.ir.analytics.interventions import QueryTargetKind
    from polisyos.ir.model_layer.types import TimeFrequency
    from polisyos.runtime.quality.cycle_substrate import CycleSubstrateContextArtifactOwner
    from polisyos.runtime.quality.generation_cycle import gy_content_hash
    from polisyos.runtime.quality.generation_source import N4CandidateScenarioSourceRecordV3
    from polisyos.runtime.quality.world_model_record import world_model_artifact_views

    candidate_schema = read_core_manifest_profile(store, candidate_source_ref)[0].artifact_schema
    if (
        type(candidate_source) is not N4CandidateScenarioSourceRecordV3
        or candidate_source_ref.kind != "runtime.quality.n4_candidate_scenario_source"
        or candidate_source_ref.manifest_profile_sha256 is None
        or candidate_schema is None
        or (candidate_schema.name, candidate_schema.version)
        != (candidate_source.schema_version, "3.0")
        or N4CandidateScenarioSourceRecordV3.model_validate(
            load_core_json_artifact(store, candidate_source_ref)
        )
        != candidate_source
    ):
        raise ValueError("forecast_outcome_level_candidate_selection_mismatch")
    problem = candidate_source.problem
    outcome = problem.outcome_of_interest
    atom = candidate_source.candidate.atom
    estimand = atom.intended_downstream_estimand
    if (
        outcome.estimand != OBSERVED_OUTCOME_LEVEL_ESTIMAND
        or estimand.functional != OBSERVED_OUTCOME_LEVEL_ESTIMAND
        or estimand.target_kind is not QueryTargetKind.EXPECTATION
        or estimand.outcome_variables != (outcome.target_variable,)
        or estimand.metric_id != outcome.metric_id
        or candidate_source.model_declaration.outcome_variable != outcome.target_variable
        or outcome.conditioning_variables
        or estimand.conditioning_set
    ):
        raise ValueError("forecast_outcome_level_estimand_unsupported")

    # The configured profile holds the precursor world. The atom belongs
    # to the exact world rebound and persisted by this job's context owner.
    context_job = CycleSubstrateContextArtifactOwner(store=store).resolve_historical_job_artifact(
        candidate_source.context_job_ref,
        problem=problem,
        expected_job_id=candidate_source.job_id,
        expected_run_id=candidate_source.run_id,
        expected_tenant_id=candidate_source.tenant_id,
        expected_cell_id=candidate_source.cell_id,
    )
    world = context_job.context.world_model_record
    views = world_model_artifact_views(world)
    # A stock WMR may name its model's default manifest. Qualify that exact
    # view before comparing it to the selected run input.
    world_model_spec_ref = views.model_spec_ref
    if world_model_spec_ref.manifest_profile_sha256 is None:
        manifest, _ = read_core_manifest_profile(store, world_model_spec_ref)
        world_model_spec_ref = artifact_ref_for_manifest(manifest)
    if (
        context_job.context.content_hash != candidate_source.context_hash
        or world.content_hash != candidate_source.world_model_record_hash
        or world.world_model_record_id != candidate_source.world_model_record_id
        or atom.world_model_record_ref != world.world_model_record_id
        or artifact_ref_identity_key(world_model_spec_ref)
        != artifact_ref_identity_key(model_spec_ref)
    ):
        raise ValueError("forecast_outcome_level_world_selection_mismatch")
    model = ModelSpec.model_validate(load_core_json_artifact(store, model_spec_ref))
    if (
        gy_content_hash(model.model_dump(mode="json")) != world.simulation_model_ref.model_spec_hash
        or model.model_input_port_declaration_ref is None
    ):
        raise ValueError("forecast_outcome_level_model_declaration_missing")
    # The WMR slot field records the slot kind (stock, flow, or parameter).
    # Cadence comes from the selected model clock and outcome representation.
    clock = model.time_semantics
    if clock is None or clock.frequency is not TimeFrequency.YEAR:
        raise ValueError("forecast_outcome_level_model_calendar_unsupported")
    first_period = date.fromisoformat(clock.start_date)
    if (first_period.month, first_period.day) != (1, 1):
        raise ValueError("forecast_outcome_level_model_calendar_unsupported")
    declaration_ref = ArtifactRef.model_validate(
        model.model_input_port_declaration_ref.model_dump(mode="python")
    )
    declaration = load_model_input_port_declaration(store, declaration_ref)
    ports = tuple(
        item
        for item in declaration.ports
        if item.slot_id == outcome.target_variable and item.purpose == "outcome_validation"
    )
    if len(ports) != 1:
        raise ValueError("forecast_outcome_level_model_port_not_unique")
    (port,) = ports
    slot = world.slot_binding(outcome.target_variable)
    registry = load_registry_bundle_content(store, views.registry_bundle_ref)
    registered_slot = registry.slot_registry.slots.get(outcome.target_variable)
    if (
        slot is None
        or registered_slot is None
        or slot.state_path != registered_slot.state_path
        or slot.state_path != port.state_path
        or slot.temporal_granularity != registered_slot.kind.value
        or slot.entity_scope != registered_slot.scope.value
        or registered_slot.unit is None
        or slot.unit != registered_slot.unit.unit_id
        or slot.unit != port.unit_id
        or estimand.unit_id != port.unit_id
        or outcome.measurement_unit not in (None, port.unit_id)
        or world.region_or_jurisdiction != problem.jurisdiction_time.region
        or problem.jurisdiction_time.region != port.scope.jurisdiction_ref
        or estimand.target_population != problem.jurisdiction_time.region
        or world.population_scope != port.scope.population_ref
    ):
        raise ValueError("forecast_outcome_level_model_slot_scope_mismatch")

    member = _reopen_outcome_level_profile_member(
        store, observed_member_ref, value_data_profile_ref, resolved_profile
    )
    selected_source, observed_scope, dataset_version = _match_outcome_level_observed_scope(
        member=member,
        resolved_profile=resolved_profile,
        port=port,
    )
    representation_ref, compared, optional_unknown = _verify_outcome_level_representation(
        store, selected_source=selected_source, member=member, port=port
    )
    return ForecastOutcomeLevelRelationV1(
        candidate_source_ref=candidate_source_ref,
        observed_member_ref=observed_member_ref,
        value_data_profile_ref=value_data_profile_ref,
        observed_source_ref=ArtifactRef.model_validate(member.observed_source_ref.model_dump()),
        source_passport_ref=resolved_profile.projection.passport_ref,
        world_model_content_hash=world.content_hash,
        model_spec_ref=model_spec_ref,
        model_port_declaration_ref=declaration_ref,
        model_port_id=port.port_id,
        target_variable=outcome.target_variable,
        n4_metric_id=outcome.metric_id,
        observed_target_metric=member.target_metric,
        semantic_definition_ref=port.semantic_definition_ref,
        source_representation_ref=representation_ref,
        target_representation_ref=port.representation_ref,
        binding_profile_ref=port.binding_profile_ref,
        measurement_unit=port.unit_id,
        observed_scope=observed_scope,
        source_dataset_version=dataset_version,
        recomputed_axes=compared,
        optional_unknown_axes=optional_unknown,
    )


def _verify_outcome_level_representation(
    store: ArtifactStore,
    *,
    selected_source: AcquisitionAuthorityEntry,
    member: ForecastProfileMemberV1,
    port: ModelInputPort,
) -> tuple[VariableRepresentationRef, tuple[MeasurementAxis, ...], tuple[MeasurementAxis, ...]]:
    """Recompute the finite identity relation against both selected declarations."""
    definition_ref = selected_source.source_semantic_definition_ref
    representation_ref = selected_source.source_representation_ref
    if definition_ref != port.semantic_definition_ref or representation_ref is None:
        raise ValueError("forecast_outcome_level_definition_mismatch")

    definition = validate_core_model_json_artifact(
        VariableSemanticDefinition, store, definition_ref
    )
    if f"{definition.namespace}.{definition.stable_id}" != member.outcome or any(
        not store.verify(ref).ok for ref in definition.definition_evidence_refs
    ):
        raise ValueError("forecast_outcome_level_definition_evidence_unresolved")
    source_representation = load_variable_representation(store, representation_ref)
    target_representation = verify_model_input_port_semantics(store, port)
    binding_profile = validate_core_model_json_artifact(
        MeasurementBindingProfile, store, port.binding_profile_ref
    )
    compared, optional_unknown, refusals = compare_measurement_representation_axes(
        source_representation, target_representation, binding_profile
    )
    declared_scope = selected_source.source_measure_scope
    # Catalog declares shares separately from absolute measures. A selected
    # denominator relation is outside this observed-level identity profile.
    if (
        declared_scope is None
        or declared_scope.quantity_kind != "unconstrained"
        or declared_scope.denominator is not None
        or source_representation.measure_form in {"ratio", "rate"}
        or target_representation.measure_form in {"ratio", "rate"}
        or source_representation.denominator_ref is not None
        or target_representation.denominator_ref is not None
    ):
        raise ValueError("forecast_outcome_level_source_quantity_scope_mismatch")
    if (
        source_representation.semantic_definition_ref != definition_ref
        or source_representation.unit_id != member.measurement_unit
        or source_representation.population_ref != port.scope.population_ref
        or declared_scope.temporal_granularity != "annual"
        or source_representation.temporal_granularity != "annual"
        or target_representation.temporal_granularity != "annual"
        or source_representation.scale_to_unit is None
        or source_representation.scale_to_unit != target_representation.scale_to_unit
        or source_representation.aggregation is None
        or source_representation.aggregation != target_representation.aggregation
        or source_representation.grain != target_representation.grain
        or source_representation.money_unit != target_representation.money_unit
        or refusals
    ):
        raise ValueError("forecast_outcome_level_representation_mismatch")
    return representation_ref, compared, optional_unknown


def _reopen_outcome_level_profile_member(
    store: ArtifactStore,
    member_ref: ArtifactRef,
    value_data_profile_ref: ArtifactRef,
    resolved_profile: ResolvedValueProfileProjection,
) -> ForecastProfileMemberV1:
    """Match the actual selected snapshot rows to the stock member projection."""
    from polisyos.ir import ArtifactRefModel
    from polisyos.runtime.quality.data_snapshot_lineage import validate_data_snapshot_owner_lineage

    manifest = read_core_manifest_profile(store, member_ref)[0]
    schema = manifest.artifact_schema
    if (
        member_ref.kind != FORECAST_PROFILE_MEMBER_KIND
        or member_ref.media_type != "application/json"
        or member_ref.manifest_profile_sha256 is None
        or schema is None
        or (schema.name, schema.version)
        != (FORECAST_PROFILE_MEMBER_SCHEMA, FORECAST_PROFILE_MEMBER_SCHEMA_VERSION)
    ):
        raise ValueError("forecast_outcome_level_member_unselected")
    member = ForecastProfileMemberV1.model_validate(load_core_json_artifact(store, member_ref))
    profile = resolved_profile.profile
    if artifact_ref_identity_key(member.profile_ref) != artifact_ref_identity_key(
        value_data_profile_ref
    ):
        raise ValueError("forecast_outcome_level_member_profile_selection_mismatch")
    source_ref = ArtifactRef.model_validate(member.observed_source_ref.model_dump())
    projection_ref = ArtifactRef.model_validate(resolved_profile.source_projection_ref.model_dump())
    snapshot = validate_core_model_json_artifact(DataSnapshot, store, source_ref)
    lineage = validate_data_snapshot_owner_lineage(store, source_ref, snapshot)
    if (
        lineage.required_admissibility_blockers
        or load_core_json_artifact(store, value_data_profile_ref) != profile.model_dump(mode="json")
        or load_core_json_artifact(store, projection_ref)
        != resolved_profile.projection.model_dump(mode="json")
    ):
        raise ValueError("forecast_outcome_level_member_lineage_mismatch")
    expected_edges = tuple(
        input_ref_from_artifact_ref(ref, role=role)
        for role, ref in (
            ("value_data_profile", value_data_profile_ref),
            ("activated_source_projection", projection_ref),
            ("observed_source", source_ref),
            ("observed_data", snapshot.data_ref),
        )
    )
    if len(manifest.inputs) != len(expected_edges) or any(
        ref not in manifest.inputs for ref in expected_edges
    ):
        raise ValueError("forecast_outcome_level_member_lineage_mismatch")
    observed_data_ref = ArtifactRefModel.model_validate(snapshot.data_ref.model_dump())
    values = load_core_json_artifact(store, snapshot.data_ref)
    if not isinstance(values, Mapping):
        raise ValueError("forecast_outcome_level_series_invalid")
    recomputed, _ = join_profile_member_to_observed_series(
        profile=profile,
        profile_ref=member.profile_ref,
        source_projection_ref=resolved_profile.source_projection_ref,
        projection=resolved_profile.projection,
        observed_source_ref=member.observed_source_ref,
        observed_data_ref=observed_data_ref,
        target_metric=member.target_metric,
        unit_id=member.unit_id,
        observed_values=values.get(member.target_metric),
        source_passport=resolved_profile.source_passport,
    )
    if recomputed != member:
        raise ValueError("forecast_outcome_level_member_replay_mismatch")
    return member


def _match_outcome_level_observed_scope(
    *,
    member: ForecastProfileMemberV1,
    resolved_profile: ResolvedValueProfileProjection,
    port: ModelInputPort,
) -> tuple[AcquisitionAuthorityEntry, ModelInputScope, str]:
    """Check canonical unit, scope and annual vintage of the exact member rows."""
    from polisyos.runtime.quality.acquisition_executor import AdmissionPassport

    passport = resolved_profile.source_passport
    if not isinstance(passport, AdmissionPassport):
        raise ValueError("forecast_outcome_level_source_passport_unresolved")
    entry = passport.source_authority_entry
    scope = port.scope
    source_scope = None if entry is None else entry.source_measure_scope
    if (
        entry is None
        or source_scope is None
        or source_scope.population != scope.population_ref
        or source_scope.geography_ref != scope.geography_ref
        or source_scope.jurisdiction_ref != scope.jurisdiction_ref
        or source_scope.time_period_basis != "calendar_year"
        or source_scope.temporal_granularity != "annual"
        or scope.period_basis != "calendar_year"
        or scope.time_role != "observation_time"
        or member.measurement_unit != port.unit_id
        or entry.aggregation_method != "identity"
        or entry.is_proxy
    ):
        raise ValueError("forecast_outcome_level_observed_scope_mismatch")

    observations = {
        row.observation.observation_id: row.observation
        for row in resolved_profile.projection.observations
    }
    for profile_row in resolved_profile.profile.rows:
        if profile_row.unit_id != member.unit_id:
            continue
        source_rows = _profile_source_rows_for_unit_period(
            profile=resolved_profile.profile,
            row=profile_row,
            projection=resolved_profile.projection,
            passport=passport,
        )
        if len(source_rows) != 1:
            raise ValueError("forecast_outcome_level_observed_row_ambiguous")
        observation = observations[source_rows[0][2]]
        condition = json.loads(observation.condition_json)
        if (
            any(
                key in condition and condition[key] != expected
                for key, expected in (
                    ("population_ref", scope.population_ref),
                    ("geography_ref", scope.geography_ref),
                    ("jurisdiction_ref", scope.jurisdiction_ref),
                    ("time_period_basis", scope.period_basis),
                )
            )
            or observation.observation_class != "observed"
            or observation.dataset_version != passport.dataset_version
            or observation.source_watermark != passport.source_watermark
            or observation.year != profile_row.period_id
            or observation.survey_year is not None
            or observation.wave is not None
            or observation.country_code != source_scope.source_geography_id
        ):
            raise ValueError("forecast_outcome_level_observed_vintage_mismatch")
    start = date(member.period_ids[0], 1, 1)
    end = date(member.period_ids[-1], 12, 31)
    if start < scope.period_start or end > scope.period_end:
        raise ValueError("forecast_outcome_level_observed_period_out_of_scope")
    return (
        entry,
        scope.model_copy(update={"period_start": start, "period_end": end}),
        passport.dataset_version,
    )


def _canonical_digest(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


__all__ = [
    "FORECAST_OUTCOME_LEVEL_RELATION_KIND",
    "FORECAST_OUTCOME_LEVEL_RELATION_SCHEMA",
    "FORECAST_OUTCOME_LEVEL_RELATION_VERSION",
    "FORECAST_PROFILE_MEMBER_CONTRACT_VERSION",
    "FORECAST_PROFILE_MEMBER_KIND",
    "FORECAST_PROFILE_MEMBER_SCHEMA",
    "FORECAST_PROFILE_MEMBER_SCHEMA_VERSION",
    "OBSERVED_OUTCOME_LEVEL_ESTIMAND",
    "VALUE_DATA_PROFILE_KIND",
    "VALUE_DATA_PROFILE_SCHEMA",
    "VALUE_DATA_PROFILE_SCHEMA_VERSION",
    "VALUE_OWNER_PROJECTION_KIND",
    "VALUE_OWNER_PROJECTION_SCHEMA",
    "VALUE_OWNER_PROJECTION_SCHEMA_VERSION",
    "ForecastOutcomeLevelRelationV1",
    "ResolvedValueProfileProjection",
    "build_forecast_outcome_level_relation",
    "forecast_outcome_level_relation_inputs",
    "join_profile_member_to_observed_series",
    "validate_profile_projection_binding",
]
