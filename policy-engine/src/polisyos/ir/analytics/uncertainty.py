from __future__ import annotations

import math
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.ir.artifacts import ArtifactStore, InputRef, get_json_artifact, put_json_artifact
from polisyos.ir.canon import CanonSpec
from polisyos.ir.refs import UncertaintyEnvelopeRef


class UncertaintySource(str, Enum):
    CALIBRATION = "calibration"
    TRUST = "trust"
    CONFLICT_RESOLUTION = "conflict_resolution"
    CAUSAL = "causal"
    BOOTSTRAP = "bootstrap"
    ENSEMBLE = "ensemble"
    MANUAL = "manual"


class DistributionFamily(str, Enum):
    NORMAL = "normal"
    BOOTSTRAP = "bootstrap"
    BAYESIAN = "bayesian"
    UNIFORM = "uniform"
    TRIANGULAR = "triangular"
    UNKNOWN = "unknown"


class PropagationMethod(str, Enum):
    DELTA_METHOD = "delta_method"
    MONTE_CARLO = "monte_carlo"
    ANALYTICAL = "analytical"
    NONE = "none"


class IntervalSemantics(str, Enum):
    CONFIDENCE_INTERVAL = "confidence_interval"
    CREDIBLE_INTERVAL = "credible_interval"
    DETERMINISTIC_BOUNDS = "deterministic_bounds"
    HEURISTIC_RANGE = "heuristic_range"


class UncertaintyEnvelope(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        json_schema_extra={
            "title": "UncertaintyEnvelope",
            "description": "Unified uncertainty contract for Policy OS IR layer.",
        },
    )

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")

    point_estimate: float
    confidence_interval: tuple[float, float]
    confidence_level: float | None = Field(default=0.95, gt=0.0, lt=1.0)

    distribution_family: DistributionFamily = DistributionFamily.UNKNOWN
    source: UncertaintySource
    propagation_method: PropagationMethod = PropagationMethod.NONE
    interval_semantics: IntervalSemantics = IntervalSemantics.CONFIDENCE_INTERVAL

    sample_size: int | None = Field(default=None, ge=1)

    # Marks whether interval is heuristic and therefore non-statistical.
    is_heuristic_ci: bool = False
    # Heuristic intervals are not eligible for strict governance gates.
    gate_eligible: bool = True

    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_fields(self) -> "UncertaintyEnvelope":
        lo, hi = self.confidence_interval

        for value, label in (
            (self.point_estimate, "point_estimate"),
            (lo, "confidence_interval[0]"),
            (hi, "confidence_interval[1]"),
        ):
            if not math.isfinite(value):
                raise ValueError(f"{label} must be finite")

        if self.confidence_level is not None and not math.isfinite(self.confidence_level):
            raise ValueError("confidence_level must be finite")

        if lo > hi:
            raise ValueError(f"confidence_interval lower ({lo}) > upper ({hi})")

        if not (lo <= self.point_estimate <= hi):
            raise ValueError(
                f"point_estimate ({self.point_estimate}) must lie within "
                f"confidence_interval [{lo}, {hi}]"
            )

        statistical = {
            IntervalSemantics.CONFIDENCE_INTERVAL,
            IntervalSemantics.CREDIBLE_INTERVAL,
        }
        if self.interval_semantics in statistical and self.confidence_level is None:
            raise ValueError("confidence_level is required for statistical intervals")

        non_statistical = {
            IntervalSemantics.DETERMINISTIC_BOUNDS,
            IntervalSemantics.HEURISTIC_RANGE,
        }
        if self.interval_semantics in non_statistical and self.confidence_level is not None:
            raise ValueError("confidence_level must be None for non-statistical interval semantics")

        if (
            self.interval_semantics == IntervalSemantics.HEURISTIC_RANGE
            and not self.is_heuristic_ci
        ):
            raise ValueError("interval_semantics=heuristic_range requires is_heuristic_ci=True")

        if self.is_heuristic_ci and self.gate_eligible:
            raise ValueError("heuristic intervals must set gate_eligible=False")

        return self

    @property
    def ci_lower(self) -> float:
        return self.confidence_interval[0]

    @property
    def ci_upper(self) -> float:
        return self.confidence_interval[1]

    @property
    def ci_width(self) -> float:
        return self.ci_upper - self.ci_lower

    @property
    def relative_uncertainty(self) -> float | None:
        if abs(self.point_estimate) < 1e-15:
            return None
        return self.ci_width / abs(self.point_estimate)


def persist_uncertainty_envelope(
    store: ArtifactStore,
    envelope: UncertaintyEnvelope,
    *,
    inputs: list[InputRef] | None = None,
    schema_name: str = "ir.uncertainty_envelope",
    schema_version: str = "1.0",
) -> UncertaintyEnvelopeRef:
    ref = put_json_artifact(
        store,
        envelope.model_dump(mode="python"),
        kind="ir.uncertainty_envelope",
        schema_name=schema_name,
        schema_version=schema_version,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return UncertaintyEnvelopeRef.model_validate(ref)


def load_uncertainty_envelope(
    store: ArtifactStore,
    ref: UncertaintyEnvelopeRef,
) -> UncertaintyEnvelope:
    payload = get_json_artifact(store, ref.artifact_id)
    return UncertaintyEnvelope.model_validate(payload)


__all__ = [
    "DistributionFamily",
    "IntervalSemantics",
    "PropagationMethod",
    "UncertaintyEnvelope",
    "UncertaintySource",
    "persist_uncertainty_envelope",
    "load_uncertainty_envelope",
]
