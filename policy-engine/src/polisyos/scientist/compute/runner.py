from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.foundry.executor import apply_state_delta_and_snapshot, execute_program_graph
from polisyos.scientist.compute.job_spec import JobKey, JobResult, JobSpec


@dataclass
class ExecutionResult:
    exec_artifacts: Any
    applied: Any
    final_state: Any


class RunnerBackend:
    """Backend interface for executing compiled programs."""

    def run(
        self,
        *,
        cas_root: Path,
        program_ref: ArtifactRef,
        exec_plan_ref: ArtifactRef,
        base_state: Any,
        registry_content: Any,
        seed: int,
    ) -> ExecutionResult:
        raise NotImplementedError


class LocalBackend(RunnerBackend):
    """Local execution using FileSystemCAS and Foundry executor."""

    def run(
        self,
        *,
        cas_root: Path,
        program_ref: ArtifactRef,
        exec_plan_ref: ArtifactRef,
        base_state: Any,
        registry_content: Any,
        seed: int,
    ) -> ExecutionResult:
        store = FileSystemCAS(cas_root)
        exec_artifacts = execute_program_graph(
            store,
            program_ref=program_ref,
            exec_plan_ref=exec_plan_ref,
            base_state=base_state,
            mechanism_registry=registry_content.mechanism_registry,
            slot_registry=registry_content.slot_registry,
            merge_registry=registry_content.merge_registry,
            selector_field_registry=registry_content.selector_field_registry,
            constraint_registry=registry_content.constraint_registry,
            step=int(base_state.step),
            seed=seed,
        )
        final_state, applied = apply_state_delta_and_snapshot(
            store,
            base_state=base_state,
            state_delta_ref=exec_artifacts.state_delta_ref,
            slot_registry=registry_content.slot_registry,
            merge_registry=registry_content.merge_registry,
            step=int(base_state.step),
        )
        return ExecutionResult(exec_artifacts=exec_artifacts, applied=applied, final_state=final_state)


class RayBackend(RunnerBackend):
    """Skeleton for future distributed execution."""

    def run(
        self,
        *,
        cas_root: Path,
        program_ref: ArtifactRef,
        exec_plan_ref: ArtifactRef,
        base_state: Any,
        registry_content: Any,
        seed: int,
    ) -> ExecutionResult:
        raise NotImplementedError("RayBackend is not implemented yet.")


def resolve_backend(kind: str | None) -> RunnerBackend:
    backend_kind = (kind or os.getenv("POLISYOS_RUNNER_BACKEND") or "local").lower()
    if backend_kind == "ray":
        return RayBackend()
    return LocalBackend()


def run_job(
    spec: JobSpec,
    *,
    backend: RunnerBackend | None = None,
    registry_content: Any = None,
    base_state: Any = None,
    cas_root: Path | None = None,
) -> JobResult:
    """
    Execute a compiled job spec via the provided backend.

    Parameters
    ----------
    spec: JobSpec
        References to program graph, exec plan, and state snapshot.
    backend: RunnerBackend
        Execution backend (default LocalBackend).
    registry_content: Any
        Loaded registry bundle content (mechanism/slot/merge/constraint registries).
    base_state: Any
        Loaded state snapshot (GlobalState).
    """
    job_key = JobKey.from_spec(spec)
    if backend is None:
        backend = resolve_backend(None)
    if registry_content is None or base_state is None or spec.exec_plan_ref is None or cas_root is None:
        return JobResult(job_key=job_key, warnings=["missing inputs for execution"])

    result = backend.run(
        cas_root=cas_root,
        program_ref=spec.program_ref,
        exec_plan_ref=spec.exec_plan_ref,
        base_state=base_state,
        registry_content=registry_content,
        seed=spec.seed,
    )

    return JobResult(
        job_key=job_key,
        state_delta_ref=result.exec_artifacts.state_delta_ref,
        metrics_ref=result.exec_artifacts.metrics_ref,
        state_snapshot_ref=result.applied.state_snapshot_ref if hasattr(result.applied, "state_snapshot_ref") else None,
        final_state=result.final_state,
        warnings=[],
    )
