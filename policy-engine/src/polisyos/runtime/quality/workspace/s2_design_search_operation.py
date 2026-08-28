"""Governed REFINE adapter for run-bound Layer-2 S2 design search."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, ConfigDict

from polisyos.core import artifacts, registry, run
from polisyos.core.security import get_current_cell_id, get_current_tenant_id
from polisyos.pdc import (
    Layer2S2DesignSearchInput,
    persist_s2_design_search_run,
    run_s2_shadow_design_loop,
)
from polisyos.runtime.http.services.adapters.core_run import derive_core_run_dir

if TYPE_CHECKING:
    from pathlib import Path

S2_DESIGN_SEARCH_OPERATION_ID = "phase2.refine.layer2_s2_design_search"


class S2DesignSearchOperationResult(BaseModel):
    """Exact artifacts and terminal manifest emitted by one governed S2 invocation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    operation_id: Literal["phase2.refine.layer2_s2_design_search"] = (
        S2_DESIGN_SEARCH_OPERATION_ID
    )
    design_record_ref: artifacts.ArtifactRef
    search_ledger_ref: artifacts.ArtifactRef
    binding_ref: artifacts.ArtifactRef
    manifest_ref: artifacts.ArtifactRef


def execute_s2_design_search_operation(
    *,
    operation_id: str,
    search_input: Layer2S2DesignSearchInput,
    store: artifacts.FileSystemCAS,
    core_runs_root: Path,
    run_id: str,
) -> S2DesignSearchOperationResult:
    """Execute the exact governed S2 operation under verified ambient ownership."""

    if operation_id != S2_DESIGN_SEARCH_OPERATION_ID:
        raise ValueError("S2 design search adapter rejects non-owner operation IDs")
    if not isinstance(search_input, Layer2S2DesignSearchInput):
        raise TypeError("S2 design search adapter requires Layer2S2DesignSearchInput")
    tenant_id = get_current_tenant_id()
    cell_id = get_current_cell_id()
    run_dir = derive_core_run_dir(core_runs_root, run_id)
    registry_bundle_ref = registry.build_default_registry_bundle(store).bundle_ref
    run_context = run.RunContext.start(
        store,
        registry_bundle_ref,
        producer=artifacts.ProducerInfo(
            component="polisyos.runtime.quality.workspace.s2_design_search_operation",
            version="policyos.runtime.s2_design_search_operation.v1",
        ),
        run_dir=run_dir,
        run_id=run_id,
        tenant_id=tenant_id,
        cell_id=cell_id,
    )
    search_run = run_s2_shadow_design_loop(search_input)
    persisted = persist_s2_design_search_run(
        search_run,
        store=store,
        run_id=run_id,
        tenant_id=tenant_id,
        cell_id=cell_id,
    )
    candidate_metrics = {"candidate_only": 1, "authority_bearing": 0}
    run_context.emit(
        "pdc.gy",
        "S2_APPLICABILITY_RECORDED",
        metrics=candidate_metrics,
    )
    run_context.emit(
        "pdc.gy",
        "S2_OPERATION_INVOCATION_RECORDED",
        metrics=candidate_metrics,
    )
    run_context.emit(
        "pdc.gy",
        "S2_SEARCH_LEDGER_RECORDED",
        metrics=candidate_metrics,
    )
    run_context.emit(
        "pdc.gy",
        "S2_ARTIFACT_ENVELOPE_RECORDED",
        metrics=candidate_metrics,
    )
    for artifact_ref in (
        persisted.design_record_ref,
        persisted.search_ledger_ref,
        persisted.binding_ref,
    ):
        run_context.add_output(artifact_ref)
    manifest_ref = run_context.finalize()
    return S2DesignSearchOperationResult(
        design_record_ref=persisted.design_record_ref,
        search_ledger_ref=persisted.search_ledger_ref,
        binding_ref=persisted.binding_ref,
        manifest_ref=manifest_ref,
    )


__all__ = [
    "S2_DESIGN_SEARCH_OPERATION_ID",
    "S2DesignSearchOperationResult",
    "execute_s2_design_search_operation",
]
