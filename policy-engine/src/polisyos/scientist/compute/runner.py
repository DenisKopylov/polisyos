from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import numpy as np

try:  # pragma: no cover - optional dependency for local/dev environments
    import jax
    import jax.numpy as jnp
except ModuleNotFoundError:  # pragma: no cover
    jax = None  # type: ignore[assignment]
    jnp = np  # type: ignore[assignment]

from polisyos.common.serialization import to_python_data
from polisyos.core.artifacts.manifest import ArtifactRef, InputRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec
from polisyos.core.components import ENTRY_POINT_GROUP_FOUNDRY_METHODS
from polisyos.core.components.bootstrap import build_components_index
from polisyos.foundry.methods.backends.dispatch import MethodDispatcher
from polisyos.foundry.methods.components_bridge import bootstrap_method_registry_from_components
from polisyos.foundry.methods.exceptions import MethodNotFoundError
from polisyos.foundry.methods.registry import MethodRegistry
from polisyos.ir.governance.validation import ValidationIssue
from polisyos.scientist.compute.job_spec import JobKey, JobResult, JobSpec


@dataclass
class ExecutionResult:
    exec_artifacts: Any
    applied: Any
    final_state: Any


@dataclass(frozen=True)
class MethodExecutionArtifacts:
    result_ref: ArtifactRef
    evidence_ref: ArtifactRef


class RunnerBackend:
    """Backend interface for executing compiled program jobs."""

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
        from polisyos.foundry.executor import (
            apply_state_delta_and_snapshot,
            execute_program_graph,
        )

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
            capture_env=False,
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
            exec_artifacts=exec_artifacts,
            applied=applied,
            final_state=final_state,
        )


class MethodBackend:
    """Backend for method-based jobs via foundry.methods dispatcher."""

    def run(
        self,
        *,
        cas_root: Path,
        method_fqn: str,
        method_version: str | None,
        input_state: Any,
        method_params: Mapping[str, Any],
        seed: int,
        input_refs: Mapping[str, ArtifactRef] | None = None,
    ) -> ExecutionResult:
        store = FileSystemCAS(cas_root)
        registry = MethodRegistry.get_instance()
        resolved_name = method_fqn
        if method_version and "@" not in method_fqn:
            resolved_name = f"{method_fqn}@{method_version}"
        try:
            method_class = registry.get(resolved_name, version=method_version)
        except MethodNotFoundError:
            components_index, _ = build_components_index(
                groups=[ENTRY_POINT_GROUP_FOUNDRY_METHODS],
                include_dev_scan=False,
            )
            bootstrap_method_registry_from_components(
                components_index,
                registry,
                resolution_policy=registry.get_default_policy(),
            )
            method_class = registry.get(resolved_name, version=method_version)
        signature = method_class.signature

        dispatcher = MethodDispatcher.get_instance()
        method_result = dispatcher.dispatch(
            method_class=method_class,
            signature=signature,
            state=input_state,
            params=method_params,
            seed=seed,
        )

        result_payload = to_python_data(method_result.output, sort_keys=True)
        result_inputs: list[InputRef] = []
        for slot_name, ref in sorted((input_refs or {}).items(), key=lambda kv: kv[0]):
            result_inputs.append(InputRef(artifact_id=ref.artifact_id, role=f"input:{slot_name}"))

        result_ref = store.put_json(
            result_payload,
            PutOptions(
                kind=f"scientist.method_result.{signature.namespace}",
                media_type="application/json",
                schema=SchemaInfo(
                    name="polisyos.scientist.MethodResult",
                    version="0.1.0",
                ),
                inputs=result_inputs,
            ),
            canon_spec=CanonSpec(forbid_floats=False),
        )

        evidence_payload = {
            "method_fqn": signature.fqn,
            "backend": signature.backend.value,
            "timing": {
                "wall_time_ms": method_result.timing.wall_time_ms,
                "cpu_time_ms": method_result.timing.cpu_time_ms,
                "compile_time_ms": method_result.timing.compile_time_ms,
            },
            "reproducibility": {
                "tier": method_result.reproducibility.determinism_tier.value,
                "seed": method_result.reproducibility.seed,
                "library_versions": dict(
                    sorted(method_result.reproducibility.library_versions.items())
                ),
                "solver_status": method_result.reproducibility.solver_status.value
                if method_result.reproducibility.solver_status
                else None,
                "solver_gap": method_result.reproducibility.solver_gap,
                "solver_iterations": method_result.reproducibility.solver_iterations,
                "fingerprint": method_result.reproducibility.fingerprint,
                "note": method_result.reproducibility.note,
            },
            "warnings": list(method_result.warnings),
            "artifacts": to_python_data(method_result.artifacts, sort_keys=True),
            "result_ref": str(result_ref.artifact_id),
        }
        evidence_ref = store.put_json(
            evidence_payload,
            PutOptions(
                kind="scientist.method_evidence",
                media_type="application/json",
                schema=SchemaInfo(
                    name="polisyos.scientist.MethodExecutionEvidence",
                    version="0.1.0",
                ),
                inputs=[InputRef(artifact_id=result_ref.artifact_id, role="method_result")],
            ),
            canon_spec=CanonSpec(forbid_floats=False),
        )

        return ExecutionResult(
            exec_artifacts=MethodExecutionArtifacts(
                result_ref=result_ref,
                evidence_ref=evidence_ref,
            ),
            applied=None,
            final_state=method_result.output,
        )


def resolve_backend(kind: str | None) -> RunnerBackend:
    backend_kind = (kind or os.getenv("POLISYOS_RUNNER_BACKEND") or "local").lower()
    if backend_kind != "local":
        raise ValueError(
            f"Unsupported runner backend '{backend_kind}'. Only 'local' is available."
        )
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


def _load_input_refs(cas_root: Path, input_refs: Mapping[str, ArtifactRef]) -> Any:
    store = FileSystemCAS(cas_root)
    loaded: dict[str, Any] = {}
    for slot_name, ref in input_refs.items():
        payload = store.get_bytes(ref.artifact_id)
        loaded[slot_name] = json.loads(payload.decode("utf-8"))
    return loaded


def _run_legacy_job(
    spec: JobSpec,
    *,
    job_key: JobKey,
    backend: RunnerBackend,
    registry_content: Any,
    base_state: Any,
    cas_root: Path | None,
) -> JobResult:
    issues: list[dict[str, Any]] = []
    if cas_root is None:
        issues.append(_issue_payload(["job_spec"], "cas_root is required", "runtime"))
    if registry_content is None:
        issues.append(_issue_payload(["job_spec"], "registry_content is required", "runtime"))
    if spec.exec_plan_ref is None:
        issues.append(
            _issue_payload(["job_spec", "exec_plan_ref"], "exec_plan_ref missing", "runtime")
        )
    if spec.program_ref is None:
        issues.append(_issue_payload(["job_spec", "program_ref"], "program_ref missing", "runtime"))

    store = FileSystemCAS(cas_root) if cas_root is not None else None
    if base_state is None and store is not None and spec.state_snapshot_ref is not None:
        try:
            from polisyos.foundry.executor import load_state_snapshot

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
        cpu_device = None
        prefer_cpu = False
        if jax is not None:
            try:
                cpu_device = jax.devices("cpu")[0]
            except Exception:
                cpu_device = None
            try:
                prefer_cpu = any(device.platform == "metal" for device in jax.devices())
            except Exception:
                prefer_cpu = False
        if cpu_device is not None and prefer_cpu:
            with jax.default_device(cpu_device):
                result = backend.run(
                    cas_root=cas_root,
                    program_ref=spec.program_ref,
                    exec_plan_ref=spec.exec_plan_ref,
                    base_state=base_state,
                    registry_content=registry_content,
                    seed=spec.seed,
                )
        else:
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
    if store is not None and spec.program_ref is not None and spec.exec_plan_ref is not None:
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
            summary_ref = store.put_json(
                summary,
                PutOptions(
                    kind="scientist.simulation_results",
                    media_type="application/json",
                    schema=SchemaInfo(
                        name="polisyos.scientist.SimulationResults",
                        version="0.1.0",
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


def _run_method_job(
    spec: JobSpec,
    *,
    job_key: JobKey,
    cas_root: Path | None,
    method_state: Any,
    backend: MethodBackend,
    adapter_warnings: list[str] | None = None,
) -> JobResult:
    issues: list[dict[str, Any]] = []
    if cas_root is None:
        issues.append(_issue_payload(["job_spec"], "cas_root is required", "runtime"))
    if not spec.method_fqn:
        issues.append(_issue_payload(["job_spec", "method_fqn"], "method_fqn missing", "runtime"))
    if issues:
        return JobResult(job_key=job_key, issues=issues)

    loaded_state = method_state
    if loaded_state is None and spec.input_refs and cas_root is not None:
        try:
            loaded_state = _load_input_refs(cas_root, spec.input_refs)
        except Exception as exc:
            return JobResult(
                job_key=job_key,
                issues=[_issue_payload(["job_spec", "input_refs"], str(exc), "runtime")],
            )
    if loaded_state is None:
        loaded_state = {}

    try:
        result = backend.run(
            cas_root=cas_root,
            method_fqn=spec.method_fqn,
            method_version=spec.method_version,
            input_state=loaded_state,
            method_params=spec.method_params,
            seed=spec.seed,
            input_refs=spec.input_refs,
        )
    except Exception as exc:
        return JobResult(
            job_key=job_key,
            issues=[_issue_payload(["method_runner"], str(exc), "runtime")],
        )

    artifacts = result.exec_artifacts
    warnings: list[str] = []
    warnings.extend(adapter_warnings or [])
    if isinstance(result.final_state, dict):
        if "warnings" in result.final_state and isinstance(result.final_state["warnings"], list):
            warnings.extend(str(item) for item in result.final_state["warnings"])

    return JobResult(
        job_key=job_key,
        simulation_results_ref=artifacts.result_ref,
        method_result_ref=artifacts.result_ref,
        method_evidence_ref=artifacts.evidence_ref,
        final_state=result.final_state,
        warnings=warnings,
    )


def run_job(
    spec: JobSpec,
    *,
    backend: RunnerBackend | None = None,
    registry_content: Any = None,
    base_state: Any = None,
    cas_root: Path | None = None,
    method_state: Any = None,
) -> JobResult:
    """
    Execute a job spec via either legacy program flow or method flow.
    """
    job_key = JobKey.from_spec(spec)

    if spec.is_method_job:
        adapter_warnings = _materialize_method_adapter(spec, cas_root=cas_root)
        method_backend = backend if isinstance(backend, MethodBackend) else MethodBackend()
        return _run_method_job(
            spec,
            job_key=job_key,
            cas_root=cas_root,
            method_state=method_state,
            backend=method_backend,
            adapter_warnings=adapter_warnings,
        )

    legacy_backend = backend if backend is not None else resolve_backend(None)
    return _run_legacy_job(
        spec,
        job_key=job_key,
        backend=legacy_backend,
        registry_content=registry_content,
        base_state=base_state,
        cas_root=cas_root,
    )


def _materialize_method_adapter(spec: JobSpec, *, cas_root: Path | None) -> list[str]:
    """
    Temporary bridge until all method runs execute through unified ProgramGraph.

    We persist a single-node DAG descriptor so every method run has a stable adapter
    artifact that can be traced in lineage/debug output.
    """
    if cas_root is None:
        return ["legacy_adapter_missing_cas_root"]
    try:
        store = FileSystemCAS(cas_root)
        payload = {
            "adapter_version": "0.1.0",
            "job_kind": "method",
            "method_fqn": spec.method_fqn,
            "method_version": spec.method_version,
            "method_params": spec.method_params,
            "notes": [
                "legacy_method_job_mapped_to_single_node_unified_dag",
            ],
            "program_graph": {
                "nodes": [
                    {
                        "node_id": "method_node_1",
                        "node_kind": "method",
                        "method_fqn": spec.method_fqn,
                    }
                ],
                "edges": [],
            },
        }
        ref = store.put_json(
            payload,
            PutOptions(
                kind="scientist.unified_dag_adapter",
                media_type="application/json",
                schema=SchemaInfo(name="polisyos.scientist.UnifiedDagAdapter", version="0.1.0"),
            ),
        )
        return [f"legacy_method_adapter_ref:{ref.artifact_id}"]
    except Exception as exc:
        return [f"legacy_method_adapter_failed:{exc}"]
