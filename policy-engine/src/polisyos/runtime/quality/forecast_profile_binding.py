"""Bind canonical EMP-01 rows to the selected active Data Forge projection.

This adapter belongs in runtime quality because it consumes Data Forge's
projection and the runtime-owned EMP-01 profile. Calibration and Scientist
receive only the typed Core candidate receipt.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import TYPE_CHECKING

from polisyos.core.contracts import (
    FORECAST_PROFILE_MEMBER_CONTRACT_VERSION,
    FORECAST_PROFILE_MEMBER_KIND,
    FORECAST_PROFILE_MEMBER_SCHEMA,
    FORECAST_PROFILE_MEMBER_SCHEMA_VERSION,
    VALUE_DATA_PROFILE_KIND,
    VALUE_OWNER_PROJECTION_KIND,
    ForecastProfileMemberV1,
    forecast_profile_observed_series_sha256,
)
from polisyos.data_forge.read_api.catalog import (
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
    from polisyos.ir import ArtifactRefModel


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


def _canonical_digest(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


__all__ = [
    "FORECAST_PROFILE_MEMBER_CONTRACT_VERSION",
    "FORECAST_PROFILE_MEMBER_KIND",
    "FORECAST_PROFILE_MEMBER_SCHEMA",
    "FORECAST_PROFILE_MEMBER_SCHEMA_VERSION",
    "VALUE_DATA_PROFILE_KIND",
    "VALUE_DATA_PROFILE_SCHEMA",
    "VALUE_DATA_PROFILE_SCHEMA_VERSION",
    "VALUE_OWNER_PROJECTION_KIND",
    "VALUE_OWNER_PROJECTION_SCHEMA",
    "VALUE_OWNER_PROJECTION_SCHEMA_VERSION",
    "ResolvedValueProfileProjection",
    "join_profile_member_to_observed_series",
    "validate_profile_projection_binding",
]
