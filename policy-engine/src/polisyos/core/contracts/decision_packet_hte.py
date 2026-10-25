"""Strict, non-authoritative decision-packet HTE legacy projection."""

from __future__ import annotations

import json
import math
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    field_validator,
    model_validator,
)

LegacyHTELimitation = Literal[
    "legacy_source_reference_unprofiled",
    "legacy_target_scope_not_established",
    "legacy_bound_meaning_not_established",
    "legacy_conditional_coverage_not_established",
    "legacy_population_coverage_not_established",
]

LEGACY_HTE_LIMITATIONS: tuple[LegacyHTELimitation, ...] = (
    "legacy_source_reference_unprofiled",
    "legacy_target_scope_not_established",
    "legacy_bound_meaning_not_established",
    "legacy_conditional_coverage_not_established",
    "legacy_population_coverage_not_established",
)


class _LegacyHTEFeatureWire(BaseModel):
    """Exact feature row emitted by the legacy HTE result serializer."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    feature_name: str = Field(min_length=1, max_length=256)
    importance_score: float
    importance_rank: int = Field(ge=1)
    method: str = Field(min_length=1, max_length=128)
    metadata: dict[str, JsonValue]

    @field_validator("importance_score")
    @classmethod
    def _finite_importance(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("legacy_hte_feature_importance_non_finite")
        return value


class _LegacyHTEAvailableSource(BaseModel):
    """Exact successful shape emitted by the legacy decision-packet builder."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    result_ref: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    method: str = Field(min_length=1, max_length=128)
    ate: float
    ate_ci_lower: float
    ate_ci_upper: float
    n_samples: int = Field(ge=0)
    n_features: int = Field(ge=0)
    n_subgroups: int = Field(ge=0)
    top_features: list[_LegacyHTEFeatureWire] = Field(max_length=5)
    warnings: list[str] = Field(max_length=64)

    @field_validator("ate", "ate_ci_lower", "ate_ci_upper")
    @classmethod
    def _finite_legacy_quantity(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("legacy_hte_quantity_non_finite")
        return value

    @model_validator(mode="after")
    def _ordered_bounds(self) -> _LegacyHTEAvailableSource:
        if self.ate_ci_lower > self.ate_ci_upper:
            raise ValueError("legacy_hte_bounds_order_invalid")
        if any(len(warning) > 512 for warning in self.warnings):
            raise ValueError("legacy_hte_warning_too_long")
        return self


class _LegacyHTEUnavailableSource(BaseModel):
    """Exact parse-failure shape emitted by the legacy decision-packet builder."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    result_ref: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    parse_warning: Literal["hte_result_parse_failed"]


class DecisionPacketLegacyHTEFeaturePreview(BaseModel):
    """One legacy feature ranking with metadata omitted from the public preview."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    feature_name: str = Field(min_length=1, max_length=256)
    importance_score: float
    importance_rank: int = Field(ge=1)
    method: str = Field(min_length=1, max_length=128)


class DecisionPacketLegacyHTEPreview(BaseModel):
    """Limited display projection of the older decision-packet HTE payload."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    kind: Literal["legacy_limited"] = "legacy_limited"
    schema_version: Literal["1.0"] = "1.0"
    projection_status: Literal["legacy_limited"] = "legacy_limited"
    availability: Literal["available", "unavailable"]
    source_result_ref: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    method: str | None = Field(default=None, min_length=1, max_length=128)
    ate: float | None = None
    ate_ci_lower: float | None = None
    ate_ci_upper: float | None = None
    n_samples: int | None = Field(default=None, ge=0)
    n_features: int | None = Field(default=None, ge=0)
    n_subgroups: int | None = Field(default=None, ge=0)
    top_features: list[DecisionPacketLegacyHTEFeaturePreview] = Field(max_length=5)
    warnings: list[str] = Field(max_length=64)
    parse_warning: Literal["hte_result_parse_failed"] | None
    source_reference_profile_status: Literal["not_established"] = "not_established"
    target_scope_status: Literal["not_established"] = "not_established"
    bounds_meaning_status: Literal["not_established"] = "not_established"
    conditional_coverage_status: Literal["not_established"] = "not_established"
    population_coverage_status: Literal["not_established"] = "not_established"
    authority_status: Literal["limited_display_only"] = "limited_display_only"
    limitations: tuple[LegacyHTELimitation, ...] = Field(
        default=LEGACY_HTE_LIMITATIONS,
        min_length=5,
        max_length=5,
    )

    @field_validator("ate", "ate_ci_lower", "ate_ci_upper")
    @classmethod
    def _finite_preview_quantity(cls, value: float | None) -> float | None:
        if value is not None and not math.isfinite(value):
            raise ValueError("legacy_hte_preview_quantity_non_finite")
        return value

    @field_validator("warnings")
    @classmethod
    def _bounded_warning_text(cls, value: list[str]) -> list[str]:
        if any(len(warning) > 512 for warning in value):
            raise ValueError("legacy_hte_preview_warning_too_long")
        return value

    @model_validator(mode="after")
    def _availability_matches_values(self) -> DecisionPacketLegacyHTEPreview:
        present = (
            self.method,
            self.ate,
            self.ate_ci_lower,
            self.ate_ci_upper,
            self.n_samples,
            self.n_features,
            self.n_subgroups,
        )
        if self.availability == "available":
            if any(value is None for value in present) or self.parse_warning is not None:
                raise ValueError("legacy_hte_preview_available_fields_missing")
            if (
                self.ate_ci_lower is not None
                and self.ate_ci_upper is not None
                and self.ate_ci_lower > self.ate_ci_upper
            ):
                raise ValueError("legacy_hte_preview_bounds_order_invalid")
        elif (
            any(value is not None for value in present)
            or self.parse_warning != "hte_result_parse_failed"
            or self.top_features
            or self.warnings
        ):
            raise ValueError("legacy_hte_preview_unavailable_fields_present")
        return self


def build_decision_packet_legacy_hte_preview(
    payload: object,
) -> DecisionPacketLegacyHTEPreview:
    """Parse one exact legacy packet shape into an explicitly limited DTO."""
    if not isinstance(payload, dict):
        raise ValueError("legacy_hte_source_must_be_object")
    try:
        encoded = json.dumps(payload, ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ValueError("legacy_hte_source_not_json") from exc

    keys = set(payload)
    if keys == set(_LegacyHTEAvailableSource.model_fields):
        source = _LegacyHTEAvailableSource.model_validate_json(encoded, strict=True)
        return DecisionPacketLegacyHTEPreview(
            availability="available",
            source_result_ref=source.result_ref,
            method=source.method,
            ate=source.ate,
            ate_ci_lower=source.ate_ci_lower,
            ate_ci_upper=source.ate_ci_upper,
            n_samples=source.n_samples,
            n_features=source.n_features,
            n_subgroups=source.n_subgroups,
            top_features=[
                DecisionPacketLegacyHTEFeaturePreview(
                    feature_name=feature.feature_name,
                    importance_score=feature.importance_score,
                    importance_rank=feature.importance_rank,
                    method=feature.method,
                )
                for feature in source.top_features
            ],
            warnings=source.warnings,
            parse_warning=None,
        )

    if keys == set(_LegacyHTEUnavailableSource.model_fields):
        source = _LegacyHTEUnavailableSource.model_validate_json(encoded, strict=True)
        return DecisionPacketLegacyHTEPreview(
            availability="unavailable",
            source_result_ref=source.result_ref,
            method=None,
            ate=None,
            ate_ci_lower=None,
            ate_ci_upper=None,
            n_samples=None,
            n_features=None,
            n_subgroups=None,
            top_features=[],
            warnings=[],
            parse_warning=source.parse_warning,
        )

    raise ValueError("legacy_hte_source_shape_invalid")


__all__ = [
    "DecisionPacketLegacyHTEFeaturePreview",
    "DecisionPacketLegacyHTEPreview",
    "build_decision_packet_legacy_hte_preview",
]
