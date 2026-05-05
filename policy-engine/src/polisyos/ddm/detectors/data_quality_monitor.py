"""Deterministic data-quality contract checks for DDM-15.7."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.ddm.integration.events import DataQualitySignal


class FeatureContract(BaseModel):
    """Per-feature serving contract."""

    model_config = ConfigDict(extra="forbid")

    feature: str = Field(min_length=1)
    dtype: Literal["number", "string", "boolean"]
    required: bool = True
    min_value: float | None = None
    max_value: float | None = None
    allowed_values: list[str] | None = None
    max_null_rate: float = Field(default=0.0, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def _validate_range(self) -> FeatureContract:
        if (
            self.min_value is not None
            and self.max_value is not None
            and self.max_value < self.min_value
        ):
            raise ValueError("max_value must be >= min_value")
        if self.dtype != "number" and (self.min_value is not None or self.max_value is not None):
            raise ValueError("min_value and max_value are only valid for numeric features")
        return self


def evaluate_data_quality(
    *,
    records: list[dict[str, object | None]],
    contracts: list[FeatureContract],
    model_id: str,
    model_version: str,
    timestamp: datetime | None = None,
    freshness_timestamp: datetime | None = None,
    max_freshness_lag_seconds: float | None = None,
) -> DataQualitySignal:
    """Evaluate schema, null, type, range, value, and freshness contracts."""

    if not records:
        raise ValueError("at least one record is required for data-quality checks")
    if not contracts:
        raise ValueError("at least one feature contract is required")

    event_time = timestamp or datetime.now(UTC)
    violations: list[str] = []
    affected_features: set[str] = set()
    hard_failure = False

    for contract in contracts:
        feature_violations, feature_hard_failure = _evaluate_feature(records, contract)
        if feature_violations:
            violations.extend(feature_violations)
            affected_features.add(contract.feature)
        hard_failure = hard_failure or feature_hard_failure

    freshness_violation = _freshness_violation(
        event_time=event_time,
        freshness_timestamp=freshness_timestamp,
        max_freshness_lag_seconds=max_freshness_lag_seconds,
    )
    if freshness_violation is not None:
        violations.append(freshness_violation)
        hard_failure = True

    risk_score = min(1.0, len(violations) / max(len(contracts), 1))
    return DataQualitySignal(
        signal_id=f"data-quality-{model_id}-{model_version}-{event_time.isoformat()}",
        timestamp=event_time,
        model_id=model_id,
        model_version=model_version,
        risk_score=risk_score,
        hard_failure=hard_failure,
        violations=violations,
        affected_features=sorted(affected_features),
    )


def _evaluate_feature(
    records: list[dict[str, object | None]],
    contract: FeatureContract,
) -> tuple[list[str], bool]:
    violations: list[str] = []
    hard_failure = False
    missing_or_null = 0
    type_errors = 0
    range_errors = 0
    allowed_value_errors = 0

    for record in records:
        value = record.get(contract.feature)
        if value is None:
            missing_or_null += 1
            continue
        if not _matches_dtype(value, contract.dtype):
            type_errors += 1
            continue
        if contract.dtype == "number" and _outside_range(_numeric_value(value), contract):
            range_errors += 1
        if contract.allowed_values is not None and str(value) not in contract.allowed_values:
            allowed_value_errors += 1

    null_rate = missing_or_null / len(records)
    if contract.required and null_rate > contract.max_null_rate:
        violations.append(
            f"{contract.feature}: null_rate {null_rate:.3f} exceeds {contract.max_null_rate:.3f}"
        )
        hard_failure = True
    if type_errors:
        violations.append(f"{contract.feature}: {type_errors} type errors")
        hard_failure = True
    if range_errors:
        violations.append(f"{contract.feature}: {range_errors} range errors")
        hard_failure = True
    if allowed_value_errors:
        violations.append(f"{contract.feature}: {allowed_value_errors} allowed-value errors")
        hard_failure = True
    return violations, hard_failure


def _matches_dtype(value: object, dtype: Literal["number", "string", "boolean"]) -> bool:
    if dtype == "number":
        return isinstance(value, int | float) and not isinstance(value, bool)
    if dtype == "string":
        return isinstance(value, str)
    return isinstance(value, bool)


def _numeric_value(value: object) -> float:
    if isinstance(value, int | float) and not isinstance(value, bool):
        return float(value)
    raise ValueError("value is not numeric")


def _outside_range(value: float, contract: FeatureContract) -> bool:
    below = contract.min_value is not None and value < contract.min_value
    above = contract.max_value is not None and value > contract.max_value
    return below or above


def _freshness_violation(
    *,
    event_time: datetime,
    freshness_timestamp: datetime | None,
    max_freshness_lag_seconds: float | None,
) -> str | None:
    if freshness_timestamp is None or max_freshness_lag_seconds is None:
        return None
    lag = (event_time - freshness_timestamp).total_seconds()
    if lag <= max_freshness_lag_seconds:
        return None
    return f"freshness lag {lag:.1f}s exceeds {max_freshness_lag_seconds:.1f}s"
