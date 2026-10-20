"""Candidate-only binding between one forecast and an EMP-01 source member."""

from __future__ import annotations

import hashlib
import json
import math
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt, model_validator

from polisyos.ir import ArtifactRefModel

FORECAST_PROFILE_MEMBER_KIND = "runtime.forecast_profile_member"
FORECAST_PROFILE_MEMBER_SCHEMA = "runtime.forecast_profile_member.v1"
FORECAST_PROFILE_MEMBER_SCHEMA_VERSION = "1.0"
FORECAST_PROFILE_MEMBER_CONTRACT_VERSION = "policyos.runtime.forecast_profile_member.v1"
VALUE_DATA_PROFILE_KIND = "runtime.value_data_profile"
VALUE_OWNER_PROJECTION_KIND = "runtime.value_owner_source_projection"


def forecast_profile_observed_series_sha256(values: object) -> str:
    """Hash a finite numeric series using the forecast owner's JSON encoding."""

    if not isinstance(values, (tuple, list)) or not values:
        raise ValueError("forecast_profile_member_observed_series_missing")
    normalized: list[float] = []
    for value in values:
        if isinstance(value, bool):
            raise ValueError("forecast_profile_member_observed_series_non_numeric")
        try:
            numeric = float(value)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError("forecast_profile_member_observed_series_non_numeric") from exc
        if not math.isfinite(numeric):
            raise ValueError("forecast_profile_member_observed_series_nonfinite")
        normalized.append(numeric)
    encoded = json.dumps(
        normalized,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class ForecastProfileMemberV1(BaseModel):
    """Exact candidate join receipt for one profile unit and observed series.

    The receipt binds the selected immutable profile and its exact activated
    source projection to the observed forecast-series artifacts. It does not
    establish population completeness, source currentness, treatment
    assignment, issuer authority, or causal calibration.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["policyos.runtime.forecast_profile_member.v1"]
    status: Literal["joined_candidate"]
    profile_ref: ArtifactRefModel
    profile_content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    source_projection_ref: ArtifactRefModel
    source_projection_content_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    observed_source_ref: ArtifactRefModel
    observed_data_ref: ArtifactRefModel
    target_metric: str = Field(min_length=1)
    unit_id: str = Field(min_length=1)
    outcome: str = Field(min_length=1)
    measurement_unit: str = Field(min_length=1)
    period_ids: tuple[StrictInt, ...] = Field(min_length=1)
    row_content_hashes: tuple[str, ...] = Field(min_length=1)
    selected_rows_content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    observed_series_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    row_count: StrictInt = Field(ge=1)
    treatment_assignment_status: Literal["owner_assignment_unresolved"]
    population_scope_status: Literal["not_established"] = "not_established"
    completeness_status: Literal["not_established"] = "not_established"
    source_relation_status: Literal["not_established"] = "not_established"
    source_time_status: Literal["not_established"] = "not_established"
    authority_scope: Literal["predictive_only"] = "predictive_only"

    @model_validator(mode="after")
    def _verify_receipt(self) -> ForecastProfileMemberV1:
        if self.target_metric != self.outcome:
            raise ValueError("forecast_profile_member_outcome_target_mismatch")
        if any(
            not value or value != value.strip() for value in (self.unit_id, self.measurement_unit)
        ):
            raise ValueError("forecast_profile_member_selection_identity_missing")
        if self.row_count != len(self.period_ids) or self.row_count != len(self.row_content_hashes):
            raise ValueError("forecast_profile_member_selected_row_count_mismatch")
        if tuple(sorted(set(self.period_ids))) != self.period_ids:
            raise ValueError("forecast_profile_member_periods_not_strictly_ordered")
        if any(
            re.fullmatch(r"sha256:[0-9a-f]{64}", value) is None for value in self.row_content_hashes
        ):
            raise ValueError("forecast_profile_member_selected_row_hash_invalid")
        if (
            self.profile_ref.kind != VALUE_DATA_PROFILE_KIND
            or self.profile_ref.media_type != "application/json"
            or self.profile_ref.manifest_profile_sha256 is None
            or self.source_projection_ref.kind != VALUE_OWNER_PROJECTION_KIND
            or self.source_projection_ref.media_type != "application/json"
            or self.source_projection_ref.manifest_profile_sha256 is None
            or self.observed_source_ref.manifest_profile_sha256 is None
            or self.observed_data_ref.manifest_profile_sha256 is None
        ):
            raise ValueError("forecast_profile_member_selected_ref_unbound")
        return self


__all__ = [
    "FORECAST_PROFILE_MEMBER_CONTRACT_VERSION",
    "FORECAST_PROFILE_MEMBER_KIND",
    "FORECAST_PROFILE_MEMBER_SCHEMA",
    "FORECAST_PROFILE_MEMBER_SCHEMA_VERSION",
    "VALUE_DATA_PROFILE_KIND",
    "VALUE_OWNER_PROJECTION_KIND",
    "ForecastProfileMemberV1",
    "forecast_profile_observed_series_sha256",
]
