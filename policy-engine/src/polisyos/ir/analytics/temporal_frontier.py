"""Time-series discovery and frontier temporal-process contracts."""
from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.ir._validation import ensure_finite_numeric, ensure_unique_ids
from polisyos.ir.analytics.causal_graph import CausalGraphModel


class TemporalDiscoveryMethod(str, Enum):
    """Time-series/discovery methods surfaced by the IR."""

    PCMCI = "pcmci"
    PCMCI_PLUS = "pcmci_plus"
    GRANGER = "granger"
    HAWKES = "hawkes"
    REGIME_SWITCHING_SCM = "regime_switching_scm"
    LINEAR_SDE = "linear_sde"


class DynamicProcessFamily(str, Enum):
    """Underlying process family for temporal-discovery outputs."""

    VAR = "var"
    HAWKES = "hawkes"
    SDE = "sde"
    REGIME_SWITCHING = "regime_switching"
    SCM = "scm"


class EquivalenceClassType(str, Enum):
    """Graph-equivalence classes produced by discovery."""

    PAG = "pag"
    MAG = "mag"
    CPDAG = "cpdag"


class TemporalEdgeSign(str, Enum):
    """Qualitative sign for a temporal/discovery edge."""

    POSITIVE = "positive"
    NEGATIVE = "negative"
    UNKNOWN = "unknown"


class TemporalDiscoveryEdge(BaseModel):
    """One lagged temporal edge with confidence metadata."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    src: str = Field(min_length=1)
    dst: str = Field(min_length=1)
    lag: int = Field(ge=0)
    confidence: float = Field(ge=0.0, le=1.0)
    sign: TemporalEdgeSign = TemporalEdgeSign.UNKNOWN
    source_method: TemporalDiscoveryMethod

    @model_validator(mode="after")
    def validate_edge(self) -> "TemporalDiscoveryEdge":
        ensure_finite_numeric(self.confidence, field_name=f"edge {self.src}->{self.dst} confidence")
        return self


class RegimeSwitchSegment(BaseModel):
    """One discovered regime segment in a regime-switching process."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    regime_id: str = Field(min_length=1)
    start_index: int = Field(ge=0)
    end_index: int = Field(ge=0)
    dominant_drivers: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_segment(self) -> "RegimeSwitchSegment":
        if self.end_index < self.start_index:
            raise ValueError("regime segment end_index must be >= start_index")
        ensure_unique_ids(
            self.dominant_drivers,
            key_fn=lambda item: item,
            label="regime dominant_driver",
        )
        return self


class EquivalenceClassSummary(BaseModel):
    """Edge sets for a PAG/MAG/CPDAG equivalence class."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    class_type: EquivalenceClassType
    compelled_edges: tuple[str, ...] = ()
    reversible_edges: tuple[str, ...] = ()
    ambiguous_edges: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_summary(self) -> "EquivalenceClassSummary":
        ensure_unique_ids(
            self.compelled_edges,
            key_fn=lambda item: item,
            label="equivalence compelled_edge",
        )
        ensure_unique_ids(
            self.reversible_edges,
            key_fn=lambda item: item,
            label="equivalence reversible_edge",
        )
        ensure_unique_ids(
            self.ambiguous_edges,
            key_fn=lambda item: item,
            label="equivalence ambiguous_edge",
        )
        return self


class ActiveExperimentDesign(BaseModel):
    """Experiment-design hint emitted by active discovery tooling."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    design_id: str = Field(min_length=1)
    objective: str = Field(min_length=1)
    candidate_interventions: tuple[str, ...] = Field(..., min_length=1)
    budget: int = Field(ge=1)
    expected_information_gain: float | None = Field(default=None, ge=0.0)

    @model_validator(mode="after")
    def validate_design(self) -> "ActiveExperimentDesign":
        ensure_unique_ids(
            self.candidate_interventions,
            key_fn=lambda item: item,
            label="candidate intervention",
        )
        if self.expected_information_gain is not None:
            ensure_finite_numeric(
                self.expected_information_gain,
                field_name="expected_information_gain",
            )
        return self


class TemporalDiscoveryFrontierReport(BaseModel):
    """Frontier report for time-series discovery and dynamic-process outputs."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    method: TemporalDiscoveryMethod
    process_family: DynamicProcessFamily
    unified_graph: CausalGraphModel | None = None
    edges: list[TemporalDiscoveryEdge] = Field(default_factory=list)
    regime_segments: list[RegimeSwitchSegment] = Field(default_factory=list)
    equivalence_class: EquivalenceClassSummary | None = None
    active_experiment_design: ActiveExperimentDesign | None = None
    execution_semantics: Literal["time_series_research", "discovery_report"] = (
        "time_series_research"
    )
    warnings: tuple[str, ...] = ()
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_report(self) -> "TemporalDiscoveryFrontierReport":
        ensure_unique_ids(
            self.edges,
            key_fn=lambda item: (item.src, item.dst, item.lag, item.source_method.value),
            label="temporal discovery edge",
        )
        ensure_unique_ids(
            self.regime_segments,
            key_fn=lambda item: item.regime_id,
            label="regime segment_id",
        )
        if (
            self.process_family is DynamicProcessFamily.REGIME_SWITCHING
            and not self.regime_segments
        ):
            raise ValueError("regime_switching reports require regime_segments")
        return self


__all__ = [
    "ActiveExperimentDesign",
    "DynamicProcessFamily",
    "EquivalenceClassSummary",
    "EquivalenceClassType",
    "RegimeSwitchSegment",
    "TemporalDiscoveryEdge",
    "TemporalDiscoveryFrontierReport",
    "TemporalDiscoveryMethod",
    "TemporalEdgeSign",
]
