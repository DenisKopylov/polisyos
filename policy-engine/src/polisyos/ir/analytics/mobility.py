"""Typed mobility report shell for Phase 1 downstream consumers."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal
from typing import ClassVar

from pydantic import ConfigDict, Field

from polisyos.ir.kernel.base import KernelModel

if TYPE_CHECKING:
    from polisyos.ir.artifacts.contracts import ArtifactStore
    from polisyos.ir.artifacts.refs import InputRef
    from polisyos.ir.refs import MobilityReportRef


class MobilityReport(KernelModel):
    """Minimal typed mobility shell registered for downstream consumers."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    contract_id: ClassVar[str] = "ir.mobility_report.v1"

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    artifact_name: Literal["mobility_report_v1.json"] = "mobility_report_v1.json"
    analysis_type: str
    status: Literal["ok", "warn", "block"]
    summary_metrics: dict[str, Any] = Field(default_factory=dict)
    sensitivity_envelope: dict[str, Any] = Field(default_factory=dict)
    upstream_refs: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


def persist_mobility_report(
    store: "ArtifactStore",
    report: MobilityReport,
    *,
    inputs: list["InputRef"] | None = None,
    schema_name: str = "ir.mobility_report",
    schema_version: str = "1.0",
) -> "MobilityReportRef":
    """Persist a mobility shell and return its typed ref."""

    from polisyos.ir.artifacts.io import put_json_artifact
    from polisyos.ir.canon import CanonSpec
    from polisyos.ir.refs import MobilityReportRef

    ref = put_json_artifact(
        store,
        report.model_dump(mode="json"),
        kind="ir.mobility_report",
        schema_name=schema_name,
        schema_version=schema_version,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return MobilityReportRef.model_validate(ref)


def load_mobility_report(
    store: "ArtifactStore",
    ref: "MobilityReportRef",
) -> MobilityReport:
    """Load a persisted mobility report shell."""

    from polisyos.ir.artifacts.io import get_json_artifact

    payload = get_json_artifact(store, ref.artifact_id)
    return MobilityReport.model_validate(payload)


__all__ = ["MobilityReport", "load_mobility_report", "persist_mobility_report"]
