"""Compose canonical acquisition routing with Fabric's new non-data intake plane.

Routing and report persistence remain owned by ``acquisition_planner``. This
module only binds an existing typed owner gap to the newly commissioned non-data
request. It neither maps acquisition types to strategies nor supplies a default
gap, and a routing report cannot lift the candidate authority ceiling.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from polisyos.fabric.evidence.non_data_acquisition import (
    NonDataAcquisitionRuntime,
    NonDataReceipt,
    NonDataRequest,
)
from polisyos.runtime.quality.acquisition_planner import (
    AcquisitionGap,
    persist_acquisition_planner_report,
    plan_evidence_acquisition,
)

if TYPE_CHECKING:
    from datetime import datetime

    from polisyos.core.artifacts.manifest import ArtifactRef


@dataclass(frozen=True)
class NonDataAcquisitionRun:
    """The canonical routing artifact and its exact candidate runtime consumer."""

    planner_report_ref: ArtifactRef
    receipt: NonDataReceipt


def run_non_data_acquisition(
    *,
    runtime: NonDataAcquisitionRuntime,
    request: NonDataRequest,
    gap: AcquisitionGap,
    run_id: str,
    at: datetime,
) -> NonDataAcquisitionRun:
    """Route through the existing planner before candidate object admission."""
    request = NonDataRequest.model_validate(request.model_dump(mode="json"))
    gap = AcquisitionGap.model_validate(gap.model_dump(mode="json"))
    if gap.gap_id != request.gap_id or gap.claim_ref != request.claim_ref:
        raise ValueError("non_data_gap_binding_mismatch")
    report = plan_evidence_acquisition(run_id=run_id, gaps=[gap], generated_at=at)
    report_ref = persist_acquisition_planner_report(runtime.store, report)
    bound = NonDataRequest.model_validate(
        {
            **request.model_dump(mode="json"),
            "planner_report_ref": str(report_ref.artifact_id),
        }
    )
    receipt = runtime.acquire(bound, at=at)
    return NonDataAcquisitionRun(planner_report_ref=report_ref, receipt=receipt)
