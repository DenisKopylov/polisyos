"""Canonical, content-bound state transitions emitted by workflow finalizers."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from polisyos.core.artifacts.manifest import ArtifactRef

FINAL_WORKFLOW_REPORT_STATE_PATH = "reports_index.workflow_report"
FINAL_RESEARCH_DAG_STATE_PATH = "artifacts_index.research_dag_ref"
FINALIZATION_OUTPUT_KINDS = {
    FINAL_WORKFLOW_REPORT_STATE_PATH: "scientist.workflow_report",
    FINAL_RESEARCH_DAG_STATE_PATH: "scientist.research_dag",
}
FINALIZATION_KIND = "scientist.workflow_state_finalization"
FINALIZATION_SCHEMA_NAME = "polisyos.scientist.orchestration.engine.WorkflowStateFinalization"
FINALIZATION_SCHEMA_VERSION = "1.0"


class FinalizationOutputBinding(BaseModel):
    """One state reference written by the terminal workflow finalizer."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    state_path: str = Field(min_length=1)
    artifact_ref: ArtifactRef


class WorkflowStateFinalization(BaseModel):
    """Persisted before/after evidence for the engine's terminal state transition."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"] = "1.0"
    run_id: str = Field(min_length=1)
    workflow_id: str = Field(min_length=1)
    workflow_spec_ref: ArtifactRef
    prior_state_ref: ArtifactRef
    final_state_ref: ArtifactRef
    output_bindings: tuple[FinalizationOutputBinding, ...] = ()

    @classmethod
    def create(
        cls,
        *,
        run_id: str,
        workflow_id: str,
        workflow_spec_ref: ArtifactRef,
        prior_state_ref: ArtifactRef,
        final_state_ref: ArtifactRef,
        output_refs: dict[str, ArtifactRef],
    ) -> WorkflowStateFinalization:
        """Create a strict receipt for the registered terminal output paths."""
        if set(output_refs) - set(FINALIZATION_OUTPUT_KINDS):
            raise ValueError("workflow_finalization_output_path_unsupported")
        for path, ref in output_refs.items():
            if ref.kind != FINALIZATION_OUTPUT_KINDS[path]:
                raise ValueError("workflow_finalization_output_kind_mismatch")
        return cls(
            run_id=run_id,
            workflow_id=workflow_id,
            workflow_spec_ref=workflow_spec_ref,
            prior_state_ref=prior_state_ref,
            final_state_ref=final_state_ref,
            output_bindings=tuple(
                FinalizationOutputBinding(state_path=path, artifact_ref=ref)
                for path, ref in sorted(output_refs.items())
            ),
        )


__all__ = [
    "FINALIZATION_KIND",
    "FINALIZATION_OUTPUT_KINDS",
    "FINALIZATION_SCHEMA_NAME",
    "FINALIZATION_SCHEMA_VERSION",
    "FINAL_RESEARCH_DAG_STATE_PATH",
    "FINAL_WORKFLOW_REPORT_STATE_PATH",
    "FinalizationOutputBinding",
    "WorkflowStateFinalization",
]
