from __future__ import annotations

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
    "persist_causal_discovery_report",
    "load_causal_discovery_report",
]
