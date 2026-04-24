"""Public analytics abm bridge module API."""

from __future__ import annotations

import math
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from polisyos.ir.artifacts import ArtifactStore, InputRef, get_json_artifact, put_json_artifact
from polisyos.ir.canon import CanonSpec
from polisyos.ir.refs import ABMAlignmentReportRef


class AlignmentStatus(str, Enum):
    """Alignment status between SCM macro effect and ABM macro aggregate."""

    CONSISTENT = "consistent"
    INCONSISTENT = "inconsistent"
    NON_LINEAR_DIVERGENCE = "non_linear_divergence"
    INSUFFICIENT_RUNS = "insufficient_runs"


class AggregationFunction(str, Enum):
    """Aggregation function public type."""

    MEAN = "mean"
    MEDIAN = "median"
    GINI = "gini"
    SUM = "sum"
    COUNT = "count"


class ToleranceMethod(str, Enum):
    """Tolerance method public type."""

    ADAPTIVE = "adaptive"
    FIXED = "fixed"


class MacroMicroMapping(BaseModel):
    """Mapping from SCM macro variable to ABM aggregate metric."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    macro_variable: str
    abm_aggregation: str
    aggregation_function: AggregationFunction
    agent_property: str
    tolerance: float | None = Field(default=None, ge=0.0)
    tolerance_method: ToleranceMethod = ToleranceMethod.ADAPTIVE

    @field_validator("macro_variable", "abm_aggregation", "agent_property")
    @classmethod
    def _validate_non_empty(cls, value: str) -> str:
        candidate = str(value).strip()
        if not candidate:
            raise ValueError("field must be non-empty")
        return candidate

    @field_validator("tolerance", mode="before")
    @classmethod
    def _validate_optional_tolerance(cls, value: Any) -> Any:
        if value is None:
            return None
        casted = float(value)
        if not math.isfinite(casted):
            raise ValueError("tolerance must be finite")
        if casted < 0.0:
            raise ValueError("tolerance must be >= 0")
        return casted


class AlignmentResult(BaseModel):
    """Per-variable alignment output."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    scm_effect: float | None = None
    abm_effect: float | None = None
    status: AlignmentStatus
    tolerance_used: float | None = Field(default=None, ge=0.0)
    delta: float | None = Field(default=None, ge=0.0)
    n_runs: int = Field(default=0, ge=0)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("scm_effect", "abm_effect", "tolerance_used", "delta", mode="before")
    @classmethod
    def _validate_optional_finite_float(cls, value: Any) -> Any:
        if value is None:
            return None
        casted = float(value)
        if not math.isfinite(casted):
            raise ValueError("numeric fields must be finite")
        return casted


class PhaseTransition(BaseModel):
    """Detected ABM phase transition event."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    variable: str
    threshold_value: float
    pre_regime: str
    post_regime: str
    jump_value: float | None = None

    @field_validator("variable", "pre_regime", "post_regime")
    @classmethod
    def _validate_text_fields(cls, value: str) -> str:
        candidate = str(value).strip()
        if not candidate:
            raise ValueError("field must be non-empty")
        return candidate

    @field_validator("threshold_value", "jump_value", mode="before")
    @classmethod
    def _validate_float_fields(cls, value: Any) -> Any:
        if value is None:
            return None
        casted = float(value)
        if not math.isfinite(casted):
            raise ValueError("numeric fields must be finite")
        return casted


class ABMAlignmentReport(BaseModel):
    """SCM to ABM consistency report."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    mappings: list[MacroMicroMapping] = Field(default_factory=list)
    alignment_results: dict[str, AlignmentResult] = Field(default_factory=dict)
    overall_consistent: bool = False
    phase_transitions: list[PhaseTransition] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


def persist_abm_alignment_report(
    store: ArtifactStore,
    report: ABMAlignmentReport,
    *,
    inputs: list[InputRef] | None = None,
    schema_name: str = "ir.abm_alignment_report",
    schema_version: str = "1.0",
) -> ABMAlignmentReportRef:
    """Persist abm alignment report helper."""
    ref = put_json_artifact(
        store,
        report.model_dump(mode="json"),
        kind="ir.abm_alignment_report",
        schema_name=schema_name,
        schema_version=schema_version,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return ABMAlignmentReportRef.model_validate(ref)


def load_abm_alignment_report(
    store: ArtifactStore,
    ref: ABMAlignmentReportRef,
) -> ABMAlignmentReport:
    """Load abm alignment report."""
    payload = get_json_artifact(store, ref.artifact_id)
    return ABMAlignmentReport.model_validate(payload)


__all__ = [
    "ABMAlignmentReport",
    "AggregationFunction",
    "AlignmentResult",
    "AlignmentStatus",
    "MacroMicroMapping",
    "PhaseTransition",
    "ToleranceMethod",
    "load_abm_alignment_report",
    "persist_abm_alignment_report",
]
