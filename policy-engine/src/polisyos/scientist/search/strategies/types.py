"""Core data models for advanced search strategies."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from polisyos.scientist.search.objective import ObjectiveValue

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

    def __post_init__(self) -> None:
        if self.dtype == ParameterType.CATEGORICAL:
            if not self.categories or len(self.categories) < 2:
                raise ValueError(
                    f"Categorical parameter '{self.name}' requires at least two categories"
                )
            return
        if self.lower >= self.upper:
            raise ValueError(f"Invalid bounds for '{self.name}': lower >= upper")
        if self.log_scale and self.lower <= 0:
            raise ValueError(f"Log-scale parameter '{self.name}' requires lower > 0")


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
        return self.status == EvaluationStatus.SUCCESS and self.stage_a_passed


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
        return json.dumps(payload, sort_keys=True, default=str).encode("utf-8")

    @classmethod
    def from_artifact(cls, data: bytes) -> "StrategyState":
        payload = json.loads(data.decode("utf-8"))
        model_state = payload.get("model_state")
        payload["model_state"] = bytes.fromhex(model_state) if model_state else None
        return cls(**payload)
