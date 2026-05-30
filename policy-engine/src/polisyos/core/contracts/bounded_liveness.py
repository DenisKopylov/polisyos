"""Bounded-liveness governed runtime configuration contracts."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

if TYPE_CHECKING:
    from collections.abc import Mapping

BOUNDED_LIVENESS_CONFIG_SCHEMA_VERSION = "policyos.core.contracts.bounded_liveness_config.v1"


class BoundedLivenessResolution(BaseModel):
    """Effective bounded-liveness policy for one producer wait."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    producer_key: str = Field(min_length=1)
    deadline_s: float = Field(gt=0.0)
    retry_ceiling: int = Field(ge=0)
    escalation: Literal["runtime_escalation"] = "runtime_escalation"
    config_id: str = Field(min_length=1)
    config_version: str = Field(min_length=1)
    owner: str = Field(min_length=1)
    feature_flag: str = Field(min_length=1)
    notes: list[str] = Field(default_factory=list)


class BoundedLivenessConfig(BaseModel):
    """Governed defaults and ceilings for finite producer waits.

    The config makes liveness checkable by turning an unbounded eventuality into
    a finite producer-specific deadline and retry ceiling. Tuned values are
    deployment/runtime configuration, while the structural escalation semantics
    are fixed by ADR-0169.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[BOUNDED_LIVENESS_CONFIG_SCHEMA_VERSION] = (
        BOUNDED_LIVENESS_CONFIG_SCHEMA_VERSION
    )
    config_id: str = Field(default="policyos.bounded_liveness.default.v1", min_length=1)
    owner: str = Field(default="team-runtime-quality", min_length=1)
    version: str = Field(default="2026-05-22", min_length=1)
    configuration_authority: Literal["governed_runtime_config"] = "governed_runtime_config"
    feature_flag: str = Field(default="universal_pdc_bounded_liveness", min_length=1)
    advisory_posture: Literal["enforced", "advisory"] = "enforced"
    default_deadline_s: float = Field(default=60.0, ge=0.01, le=86_400.0)
    default_retry_ceiling: int = Field(default=5, ge=0, le=20)
    producer_deadline_overrides_s: dict[str, float] = Field(default_factory=dict)
    producer_retry_ceiling_overrides: dict[str, int] = Field(default_factory=dict)
    escalation: Literal["runtime_escalation"] = "runtime_escalation"
    rollback_path: str = Field(default="restore previous governed runtime config", min_length=1)
    promotion_evidence_ref: str | None = None
    decision_ref: str = Field(default="ADR-0169", min_length=1)

    @field_validator("producer_deadline_overrides_s")
    @classmethod
    def _validate_deadline_overrides(cls, values: dict[str, float]) -> dict[str, float]:
        return {_normalize_key(key): _positive_float(value) for key, value in values.items()}

    @field_validator("producer_retry_ceiling_overrides")
    @classmethod
    def _validate_retry_overrides(cls, values: dict[str, int]) -> dict[str, int]:
        normalized: dict[str, int] = {}
        for key, value in values.items():
            ceiling = int(value)
            if ceiling < 0:
                raise ValueError("producer retry ceiling must be non-negative")
            normalized[_normalize_key(key)] = ceiling
        return normalized

    def resolve(
        self,
        producer_key: str,
        *,
        requested_deadline_s: float | None = None,
        requested_retries: int | None = None,
    ) -> BoundedLivenessResolution:
        """Return effective deadline/retry ceilings for one producer wait."""

        normalized_key = _normalize_key(producer_key)
        deadline_ceiling = self.producer_deadline_overrides_s.get(
            normalized_key,
            self.default_deadline_s,
        )
        retry_ceiling = self.producer_retry_ceiling_overrides.get(
            normalized_key,
            self.default_retry_ceiling,
        )
        notes: list[str] = []

        effective_deadline = deadline_ceiling
        if requested_deadline_s is not None:
            requested_deadline = _positive_float(requested_deadline_s)
            if requested_deadline > deadline_ceiling:
                notes.append("requested_deadline_clamped_to_governed_ceiling")
            effective_deadline = min(requested_deadline, deadline_ceiling)

        effective_retries = retry_ceiling
        if requested_retries is not None:
            requested_retry_count = int(requested_retries)
            if requested_retry_count < 0:
                raise ValueError("requested retries must be non-negative")
            if requested_retry_count > retry_ceiling:
                notes.append("requested_retries_clamped_to_governed_ceiling")
            effective_retries = min(requested_retry_count, retry_ceiling)

        return BoundedLivenessResolution(
            producer_key=normalized_key,
            deadline_s=effective_deadline,
            retry_ceiling=effective_retries,
            escalation=self.escalation,
            config_id=self.config_id,
            config_version=self.version,
            owner=self.owner,
            feature_flag=self.feature_flag,
            notes=notes,
        )


def bounded_liveness_config_from_mapping(
    value: BoundedLivenessConfig | Mapping[str, Any] | None,
) -> BoundedLivenessConfig:
    """Coerce optional runtime config into a bounded-liveness contract."""

    if value is None:
        return BoundedLivenessConfig()
    if isinstance(value, BoundedLivenessConfig):
        return value
    return BoundedLivenessConfig.model_validate(dict(value))


def _normalize_key(value: str) -> str:
    text = str(value).strip()
    if not text:
        raise ValueError("producer key must not be empty")
    return text


def _positive_float(value: float) -> float:
    number = float(value)
    if number <= 0.0:
        raise ValueError("deadline must be positive")
    return number


__all__ = [
    "BOUNDED_LIVENESS_CONFIG_SCHEMA_VERSION",
    "BoundedLivenessConfig",
    "BoundedLivenessResolution",
    "bounded_liveness_config_from_mapping",
]
