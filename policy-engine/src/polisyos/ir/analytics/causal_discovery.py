from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from polisyos.ir.analytics.causal_graph import CausalGraphModel
from polisyos.ir.artifacts import ArtifactStore, InputRef, get_json_artifact, put_json_artifact
from polisyos.ir.canon import CanonSpec
from polisyos.ir.refs import CausalDiscoveryReportRef


class CausalDiscoveryReport(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1.0"
    method: str
    graph: CausalGraphModel
    resolved_graph: CausalGraphModel | None = None
    bootstrap_stability: dict[str, float] = Field(default_factory=dict)
    n_bootstrap: int = Field(default=0, ge=0)
    significance_level: float = Field(default=0.05, ge=0.0, le=1.0)
    computation_time_seconds: float = Field(default=0.0, ge=0.0)
    warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class DataType(str, Enum):
    CROSS_SECTIONAL = "cross_sectional"
    TIME_SERIES = "time_series"


class DimensionRegime(str, Enum):
    LOW_DIM = "low_dim"   # n_vars <= 20
    MED_DIM = "med_dim"   # 21 <= n_vars <= 50
    HIGH_DIM = "high_dim"  # n_vars > 50


class DataCharacteristics(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    data_type: DataType
    n_samples: int
    n_variables: int
    dimension_regime: DimensionRegime
    estimated_density: float
    has_mixed_types: bool
    suspected_latent_confounders: bool
    is_stationary: bool | None = None
    max_lag: int | None = None


class EdgeAgreement(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    edge_key: str
    presence_score: float
    orientation_confidence: float
    mark_src: str
    mark_dst: str
    contributing_algorithms: list[str]


class DiscoveryPipelineReport(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    unified_pag: CausalGraphModel
    individual_results: list[CausalDiscoveryReport]
    algorithm_weights: dict[str, float]
    edge_agreements: list[EdgeAgreement]
    skeleton_agreement: dict[str, float] = Field(default_factory=dict)
    temporal_dag: CausalGraphModel | None = None
    pag_validity_violations: list[str] = Field(default_factory=list)
    data_characteristics: DataCharacteristics
    n_algorithms_run: int
    warnings: list[str] = Field(default_factory=list)
    computation_time_seconds: float = Field(default=0.0, ge=0.0)
    metadata: dict[str, Any] = Field(default_factory=dict)


def persist_causal_discovery_report(
    store: ArtifactStore,
    report: CausalDiscoveryReport,
    *,
    inputs: list[InputRef] | None = None,
    schema_name: str = "ir.causal_discovery_report",
    schema_version: str = "1.0",
) -> CausalDiscoveryReportRef:
    ref = put_json_artifact(
        store,
        report.model_dump(mode="json"),
        kind="ir.causal_discovery_report",
        schema_name=schema_name,
        schema_version=schema_version,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return CausalDiscoveryReportRef.model_validate(ref)


def load_causal_discovery_report(
    store: ArtifactStore,
    ref: CausalDiscoveryReportRef,
) -> CausalDiscoveryReport:
    payload = get_json_artifact(store, ref.artifact_id)
    return CausalDiscoveryReport.model_validate(payload)


__all__ = [
    "CausalDiscoveryReport",
    "DataType",
    "DimensionRegime",
    "DataCharacteristics",
    "EdgeAgreement",
    "DiscoveryPipelineReport",
    "persist_causal_discovery_report",
    "load_causal_discovery_report",
]
