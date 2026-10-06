"""Core data models for advanced search strategies."""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from polisyos.scientist.methods.search.objective import ObjectiveValue

NormalizedVector = tuple[float, ...]


class ParameterType(str, Enum):
    """Parameter type for search-space encoding."""

    CONTINUOUS = "continuous"
    INTEGER = "integer"
    CATEGORICAL = "categorical"
    LOG_CONTINUOUS = "log_continuous"


class AcquisitionType(str, Enum):
    """Supported acquisition functions."""

    EI = "expected_improvement"
    UCB = "upper_confidence_bound"
    PI = "probability_of_improvement"
    QEI = "q_expected_improvement"
    EHVI = "expected_hypervolume_improvement"
    QEHVI = "q_expected_hypervolume_improvement"


class EvaluationStatus(str, Enum):
    """Evaluation completion status."""

    SUCCESS = "success"
    STAGE_A_REJECT = "stage_a_reject"
    STAGE_B_ERROR = "stage_b_error"


@dataclass(frozen=True, slots=True)
class ParameterBounds:
    """Bounds specification for one search-space parameter."""

    name: str
    lower: float = 0.0
    upper: float = 1.0
    dtype: ParameterType = ParameterType.CONTINUOUS
    log_scale: bool = False
    categories: tuple[Any, ...] | None = None

    @classmethod
    def explicit(
        cls,
        *,
        name: str,
        lower: float | int | None,
        upper: float | int | None,
        dtype: ParameterType = ParameterType.CONTINUOUS,
        log_scale: bool = False,
        categories: tuple[Any, ...] | None = None,
    ) -> ParameterBounds:
        """Build bounds for GY/serious paths where missing values may not default."""

        if lower is None or upper is None:
            raise ValueError(f"Explicit bounds required for '{name}'")
        lower_float = float(lower)
        upper_float = float(upper)
        if not math.isfinite(lower_float) or not math.isfinite(upper_float):
            raise ValueError(f"Finite explicit bounds required for '{name}'")
        return cls(
            name=name,
            lower=lower_float,
            upper=upper_float,
            dtype=dtype,
            log_scale=log_scale,
            categories=categories,
        )

    def __post_init__(self) -> None:
        if self.dtype == ParameterType.CATEGORICAL:
            if not self.categories or len(self.categories) < 2:
                raise ValueError(
                    f"Categorical parameter '{self.name}' requires at least two categories"
                )
            return
        if any(
            isinstance(value, bool) or not math.isfinite(value)
            for value in (self.lower, self.upper)
        ):
            raise ValueError(f"Finite numeric bounds required for '{self.name}'")
        if self.lower >= self.upper:
            raise ValueError(f"Invalid bounds for '{self.name}': lower >= upper")
        if not math.isfinite(self.upper - self.lower):
            raise ValueError(f"Unsupported representable span for '{self.name}'")
        if (self.log_scale or self.dtype == ParameterType.LOG_CONTINUOUS) and self.lower <= 0:
            raise ValueError(f"Log-scale parameter '{self.name}' requires lower > 0")
        if self.dtype == ParameterType.INTEGER and math.ceil(self.lower) > math.floor(self.upper):
            raise ValueError(f"Integer parameter '{self.name}' has no attainable values")


@dataclass(slots=True)
class Evaluation:
    """Normalized evaluation record for strategy training."""

    candidate_id: str
    params: dict[str, Any]
    params_normalized: NormalizedVector
    objectives: list[ObjectiveValue]
    scalar_score: float
    stage_a_passed: bool
    stage_b_result: dict[str, Any] | None = None
    status: EvaluationStatus = EvaluationStatus.SUCCESS
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    wall_time_seconds: float = 0.0
    provenance_ref: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_valid(self) -> bool:
        """True when evaluation is usable for surrogate training."""
        return (
            self.status == EvaluationStatus.SUCCESS
            and self.stage_a_passed is True
            and isinstance(self.scalar_score, (int, float))
            and not isinstance(self.scalar_score, bool)
            and math.isfinite(self.scalar_score)
        )


@dataclass(slots=True)
class PolicyCandidate:
    """Candidate suggested by strategy."""

    candidate_id: str = field(default_factory=lambda: str(uuid4())[:8])
    params: dict[str, Any] = field(default_factory=dict)
    params_normalized: NormalizedVector | None = None
    semantic: dict[str, Any] = field(default_factory=lambda: {"interventions": []})
    acquisition_value: float | None = None
    predicted_mean: float | None = None
    predicted_std: float | None = None
    source_strategy: str = "unknown"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to SearchController-compatible payload."""
        return {
            **self.params,
            "semantic": self.semantic,
            "_strategy_metadata": {
                "candidate_id": self.candidate_id,
                "acquisition_value": self.acquisition_value,
                "predicted_mean": self.predicted_mean,
                "predicted_std": self.predicted_std,
                "source": self.source_strategy,
                **self.metadata,
            },
        }


@dataclass(slots=True)
class StrategyState:
    """Serializable strategy state for checkpointing/warm start."""

    strategy_name: str
    iteration: int
    rng_state: dict[str, Any]
    model_state: bytes | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_artifact(self) -> bytes:
        payload = asdict(self)
        if payload["model_state"] is not None:
            payload["model_state"] = payload["model_state"].hex()
        payload["schema_version"] = "strategy_state.v2"
        try:
            return json.dumps(payload, sort_keys=True, allow_nan=False).encode("utf-8")
        except (TypeError, ValueError) as exc:
            raise ValueError("Strategy artifact contains unsupported or non-finite data") from exc

    @classmethod
    def from_artifact(cls, data: bytes) -> StrategyState:
        try:
            payload = json.loads(data.decode("utf-8"), parse_constant=_refuse_json_constant)
            if not isinstance(payload, dict):
                raise ValueError("Strategy artifact must be an object")
            if "schema_version" in payload and payload["schema_version"] != "strategy_state.v2":
                raise ValueError("Unsupported strategy artifact schema")
            payload.pop("schema_version", None)
            if set(payload) != {
                "strategy_name",
                "iteration",
                "rng_state",
                "model_state",
                "metadata",
            }:
                raise ValueError("Strategy artifact fields are incomplete or unknown")
            if not isinstance(payload["strategy_name"], str) or not payload["strategy_name"]:
                raise ValueError("Strategy identity is invalid")
            if type(payload["iteration"]) is not int or payload["iteration"] < 0:
                raise ValueError("Strategy iteration must be a non-negative integer")
            if not isinstance(payload["rng_state"], dict) or not isinstance(
                payload["metadata"], dict
            ):
                raise ValueError("Strategy RNG and metadata must be objects")
            model_state = payload["model_state"]
            if model_state is not None and not isinstance(model_state, str):
                raise ValueError("Strategy model must be hex bytes or null")
            payload["model_state"] = bytes.fromhex(model_state) if model_state is not None else None
            return cls(**payload)
        except (UnicodeError, KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"Invalid strategy artifact: {exc}") from exc


def _refuse_json_constant(value: str) -> None:
    raise ValueError(f"Non-finite JSON value: {value}")
