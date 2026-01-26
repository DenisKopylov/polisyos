from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import jax.numpy as jnp

from polisyos.core.canon import CanonSpec
from polisyos.core.artifacts.manifest import ArtifactRef, InputRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.foundry.executor import (
    apply_state_delta_and_snapshot,
    execute_program_graph,
    load_state_snapshot,
)
from polisyos.ir.validation import ValidationIssue
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
        return ExecutionResult(
            exec_artifacts=exec_artifacts, applied=applied, final_state=final_state
        )


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


def _issue_payload(loc: list[Any], message: str, error_type: str, input_value: Any = None) -> dict:
    issue = ValidationIssue(
        loc=loc,
        message=message,
        error_type=error_type,
        input_value=input_value,
    )
    return issue.model_dump()


def _summarize_state(state: Any) -> dict[str, Any]:
    if state is None:
        return {}
    summary: dict[str, Any] = {}
    try:
        summary["avg_income"] = float(jnp.mean(state.agents.income))
        summary["n_agents"] = int(state.agents.income.shape[0])
    except Exception:
        pass
    try:
        summary["gov_balance"] = float(state.government_balance)
    except Exception:
        pass
    try:
        summary["step"] = int(state.step)
    except Exception:
        pass
    return summary


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
    issues: list[dict[str, Any]] = []
    if cas_root is None:
        issues.append(_issue_payload(["job_spec"], "cas_root is required", "runtime"))
    if registry_content is None:
        issues.append(_issue_payload(["job_spec"], "registry_content is required", "runtime"))
    if spec.exec_plan_ref is None:
        issues.append(
            _issue_payload(["job_spec", "exec_plan_ref"], "exec_plan_ref missing", "runtime")
        )

    store = FileSystemCAS(cas_root) if cas_root is not None else None
    if base_state is None and store is not None and spec.state_snapshot_ref is not None:
        try:
            base_state = load_state_snapshot(store, snapshot_ref=spec.state_snapshot_ref)
        except Exception as exc:
            issues.append(
                _issue_payload(
                    ["state_snapshot_ref"], f"Failed to load snapshot: {exc}", "runtime"
                )
            )

    if base_state is None:
        issues.append(
            _issue_payload(["job_spec", "state_snapshot_ref"], "base_state missing", "runtime")
        )

    if issues:
        return JobResult(job_key=job_key, issues=issues, warnings=["missing inputs for execution"])

    try:
        result = backend.run(
            cas_root=cas_root,
            program_ref=spec.program_ref,
            exec_plan_ref=spec.exec_plan_ref,
            base_state=base_state,
            registry_content=registry_content,
            seed=spec.seed,
        )
    except Exception as exc:
        error_type = "runtime"
        loc = ["runtime"]
        if str(exc).startswith("Constraint"):
            error_type = "constraint"
            loc = ["semantic", "constraints"]
        issues.append(_issue_payload(loc, str(exc), error_type))
        return JobResult(job_key=job_key, issues=issues)

    summary_ref = None
    if store is not None:
        summary = _summarize_state(result.final_state)
        if summary:
            inputs = [
                InputRef(artifact_id=spec.program_ref.artifact_id, role="program_graph"),
                InputRef(artifact_id=spec.exec_plan_ref.artifact_id, role="exec_plan"),
            ]
            if result.exec_artifacts.state_delta_ref is not None:
                inputs.append(
                    InputRef(
                        artifact_id=result.exec_artifacts.state_delta_ref.artifact_id,
                        role="state_delta",
                    )
                )
            if result.exec_artifacts.metrics_ref is not None:
                inputs.append(
                    InputRef(
                        artifact_id=result.exec_artifacts.metrics_ref.artifact_id,
                        role="metrics",
                    )
                )
            if getattr(result.exec_artifacts, "environment_ref", None) is not None:
                inputs.append(
                    InputRef(
                        artifact_id=result.exec_artifacts.environment_ref.artifact_id,
                        role="environment_manifest",
                    )
                )
            if getattr(result.applied, "state_snapshot_ref", None) is not None:
                inputs.append(
                    InputRef(
                        artifact_id=result.applied.state_snapshot_ref.artifact_id,
                        role="state_snapshot",
                    )
                )
            if spec.state_snapshot_ref is not None:
                inputs.append(
                    InputRef(
                        artifact_id=spec.state_snapshot_ref.artifact_id,
                        role="base_snapshot",
                    )
                )
            # Simulation summaries are numeric; allow canonical float encoding for determinism.
            summary_ref = store.put_json(
                summary,
                PutOptions(
                    kind="scientist.simulation_results",
                    media_type="application/json",
                    schema=SchemaInfo(
                        name="polisyos.scientist.SimulationResults", version="0.1.0"
                    ),
                    inputs=inputs,
                ),
                canon_spec=CanonSpec(forbid_floats=False),
            )

    return JobResult(
        job_key=job_key,
        state_delta_ref=result.exec_artifacts.state_delta_ref,
        metrics_ref=result.exec_artifacts.metrics_ref,
        environment_ref=getattr(result.exec_artifacts, "environment_ref", None),
        environment_fingerprint=getattr(result.exec_artifacts, "environment_fingerprint", None),
        state_snapshot_ref=result.applied.state_snapshot_ref
        if hasattr(result.applied, "state_snapshot_ref")
        else None,
        simulation_results_ref=summary_ref,
        final_state=result.final_state,
        warnings=[],
    )
