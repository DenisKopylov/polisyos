"""Public compute runner module API."""

from __future__ import annotations

import json
import os
import threading
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, cast

import numpy as np

from polisyos.common.async_tools import run_shared_executor_sync
from polisyos.common.logger import get_logger
from polisyos.common.serialization import to_python_data
from polisyos.core.artifacts.backends.config import (
    ArtifactStoreConfig,
    build_artifact_store,
    with_ambient_ownership_enforcement_if_supported,
)
from polisyos.core.artifacts.manifest import (
    ArtifactRef,
    InputRef,
    SchemaInfo,
    input_ref_from_artifact_ref,
)
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
from polisyos.core.canon import CanonSpec
from polisyos.core.components import ENTRY_POINT_GROUP_FOUNDRY_METHODS
from polisyos.core.components.bootstrap import build_components_index
from polisyos.foundry.methods.backends.dispatch import MethodDispatcher
from polisyos.foundry.methods.components_bridge import bootstrap_method_registry_from_components
from polisyos.foundry.methods.exceptions import MethodNotFoundError
from polisyos.foundry.methods.registry import MethodRegistry
from polisyos.ir.analytics import PosteriorPointRole, PosteriorSummaryRef
from polisyos.ir.governance.validation import ValidationIssue
from polisyos.scientist.compute.job_spec import JobKey, JobResult, JobSpec
from polisyos.scientist.orchestration.engine.error_semantics import emit_degraded_path

try:  # pragma: no cover - optional dependency for local/dev environments
    import jax as _jax
    import jax.numpy as _jnp
except ModuleNotFoundError:  # pragma: no cover
    jax: Any | None = None
    jnp: Any = np
else:  # pragma: no cover - exercised only when jax extra is installed
    jax = _jax
    jnp = _jnp

logger = get_logger(__name__)
_METHOD_REGISTRY_BOOTSTRAP_LOCK = threading.RLock()
_RUNNER_DEGRADED_ERRORS = (
    ArithmeticError,
    AttributeError,
    ImportError,
    ModuleNotFoundError,
    OSError,
    RuntimeError,
    TypeError,
    ValueError,
)

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from polisyos.core.artifacts.protocol import ArtifactStore


def _build_store(cas_root: Path) -> ArtifactStore:
    store = build_artifact_store(ArtifactStoreConfig(backend="filesystem", root=str(cas_root)))
    return cast(
        "ArtifactStore",
        with_ambient_ownership_enforcement_if_supported(store),
    )


def _require_filesystem_store(store: ArtifactStore, *, operation: str) -> FileSystemCAS:
    if isinstance(store, FileSystemCAS):
        return store
    raise TypeError(f"{operation} requires a filesystem-backed artifact store")


def _default_method_registry() -> MethodRegistry:
    return MethodRegistry.get_instance()


def _default_method_dispatcher() -> MethodDispatcher:
    return MethodDispatcher.get_instance()


@dataclass
class ExecutionResult:
    """Execution result data model."""

    exec_artifacts: Any
    applied: Any
    final_state: Any


@dataclass(frozen=True)
class MethodExecutionArtifacts:
    """Method execution artifacts public type."""

    result_ref: ArtifactRef
    evidence_ref: ArtifactRef
    posterior_summary_refs: dict[PosteriorPointRole, PosteriorSummaryRef] = field(
        default_factory=dict
    )


@dataclass(frozen=True)
class MethodRuntimeProviders:
    """Injected runtime providers for method execution orchestration."""

    registry_provider: Callable[[], MethodRegistry]
    dispatcher_provider: Callable[[], MethodDispatcher]


def resolve_method_runtime_providers(
    *,
    providers: MethodRuntimeProviders | None = None,
    registry_provider: Callable[[], MethodRegistry] | None = None,
    dispatcher_provider: Callable[[], MethodDispatcher] | None = None,
) -> MethodRuntimeProviders:
    """Resolve the effective method runtime providers for an execution path."""

    if providers is not None and registry_provider is None and dispatcher_provider is None:
        return providers
    return MethodRuntimeProviders(
        registry_provider=(
            registry_provider
            or (providers.registry_provider if providers is not None else None)
            or _default_method_registry
        ),
        dispatcher_provider=(
            dispatcher_provider
            or (providers.dispatcher_provider if providers is not None else None)
            or _default_method_dispatcher
        ),
    )


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

    def __init__(
        self,
        *,
        store_factory: Callable[[Path], ArtifactStore] | None = None,
    ) -> None:
        self._store_factory = store_factory or _build_store

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
        from polisyos.foundry.execute.executor import (
            apply_state_delta_and_snapshot,
            execute_program_graph,
        )

        store = _require_filesystem_store(
            self._store_factory(cas_root),
            operation="scientist.compute.LocalBackend.run",
        )
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

    def __init__(
        self,
        *,
        store_factory: Callable[[Path], ArtifactStore] | None = None,
        providers: MethodRuntimeProviders | None = None,
        registry_provider: Callable[[], MethodRegistry] | None = None,
        dispatcher_provider: Callable[[], MethodDispatcher] | None = None,
    ) -> None:
        self._store_factory = store_factory or _build_store
        self._providers = resolve_method_runtime_providers(
            providers=providers,
            registry_provider=registry_provider,
            dispatcher_provider=dispatcher_provider,
        )
        self._registry_provider = self._providers.registry_provider
        self._dispatcher_provider = self._providers.dispatcher_provider

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
        store = self._store_factory(cas_root)
        registry = self._registry_provider()
        resolved_name = method_fqn
        if method_version and "@" not in method_fqn:
            resolved_name = f"{method_fqn}@{method_version}"
        try:
            method_class = registry.get(resolved_name, version=method_version)
        except MethodNotFoundError:
            with _METHOD_REGISTRY_BOOTSTRAP_LOCK:
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

        dispatcher = self._dispatcher_provider()
        dispatch_binding: dict[str, Any] | None = None
        dispatch_binding_status: str | None = None

        def dispatch_with_observation() -> Any:
            nonlocal dispatch_binding, dispatch_binding_status
            if method_params.get("capture_execution_work") is True:
                from polisyos.core.canon import fingerprint
                from polisyos.scientist.methods.autotune.execution_work import (
                    MethodDispatchBinding,
                    fingerprint_method_input_value,
                )

                try:
                    if not isinstance(input_state, Mapping):
                        raise ValueError("dispatch input state is not a slot mapping")
                    binding = MethodDispatchBinding(
                        schema_version="1.1",
                        method_fqn=signature.fqn,
                        method_version=signature.version,
                        method_seed=seed,
                        method_params_fingerprint=fingerprint(dict(method_params)),
                        input_refs=dict(input_refs or {}),
                        input_schemas={
                            name: store.get_manifest(ref).artifact_schema
                            for name, ref in sorted((input_refs or {}).items())
                        },
                        input_state_fingerprints={
                            name: fingerprint_method_input_value(value)
                            for name, value in sorted(input_state.items())
                        },
                    )
                except (OSError, TypeError, ValueError):
                    dispatch_binding_status = "not_established"
                else:
                    dispatch_binding = binding.model_dump(mode="json")
                    dispatch_binding_status = "recomputed"
            return dispatcher.dispatch(
                method_class=method_class,
                signature=signature,
                state=input_state,
                params=method_params,
                seed=seed,
            )

        method_result = run_shared_executor_sync(dispatch_with_observation)

        result_payload = to_python_data(method_result.output, sort_keys=True)
        result_inputs: list[InputRef] = []
        for slot_name, ref in sorted((input_refs or {}).items(), key=lambda kv: kv[0]):
            result_inputs.append(input_ref_from_artifact_ref(ref, role=f"input:{slot_name}"))

        result_ref = store.put_json(
            result_payload,
            ArtifactWriteOptions(
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
            "authority_purpose": "method_execution",
            "authoritative_for": ["execution_reproducibility"],
            "may_not_use_for": ["governance_admissibility", "method_validity"],
            "method_fqn": signature.fqn,
            "backend": signature.backend.value,
            "execution_backend": getattr(signature, "execution_backend", signature.backend).value,
            "timing": _content_addressed_timing_policy(),
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
            "method_result_ref": result_ref.model_dump(mode="json"),
        }
        if dispatch_binding_status is not None:
            evidence_payload["method_dispatch_binding_status"] = dispatch_binding_status
            if dispatch_binding is not None:
                evidence_payload["method_dispatch_binding"] = dispatch_binding
        evidence_ref = store.put_json(
            evidence_payload,
            ArtifactWriteOptions(
                kind="scientist.method_evidence",
                media_type="application/json",
                schema=SchemaInfo(
                    name="polisyos.scientist.MethodExecutionEvidence",
                    version="0.1.0",
                ),
                inputs=[
                    InputRef(
                        artifact_id=result_ref.artifact_id,
                        role="method_result",
                        manifest_profile_sha256=result_ref.manifest_profile_sha256,
                    )
                ],
            ),
            canon_spec=CanonSpec(forbid_floats=False),
        )

        posterior_result = (
            result_payload.get("result") if isinstance(result_payload, dict) else None
        )
        declares_posterior_draws = (
            method_class.signature.backend.value == "bayesian"
            and isinstance(posterior_result, Mapping)
            and posterior_result.get("sampler_family") == "mcmc"
            and isinstance(posterior_result.get("draws_ref"), str)
        )
        has_posterior_draw_evidence = "posterior_draws" in method_result.artifacts
        if has_posterior_draw_evidence and method_class.signature.backend.value != "bayesian":
            raise ValueError("non-Bayesian method cannot emit native posterior draw evidence")
        if declares_posterior_draws and not has_posterior_draw_evidence:
            raise ValueError("method result declares native posterior draws without their evidence")

        posterior_summary_refs: dict[PosteriorPointRole, PosteriorSummaryRef] = {}
        if has_posterior_draw_evidence:
            from polisyos.foundry.calibration.uncertainty_adapter import (
                persist_posterior_summary_from_method_evidence,
            )

            for point_role in (
                PosteriorPointRole.POSTERIOR_MEAN,
                PosteriorPointRole.POSTERIOR_MEDIAN,
            ):
                posterior_summary_refs[point_role] = persist_posterior_summary_from_method_evidence(
                    store,
                    evidence_ref,
                    point_role=point_role,
                )

        return ExecutionResult(
            exec_artifacts=MethodExecutionArtifacts(
                result_ref=result_ref,
                evidence_ref=evidence_ref,
                posterior_summary_refs=posterior_summary_refs,
            ),
            applied=None,
            final_state=method_result.output,
        )


def _content_addressed_timing_policy() -> dict[str, str]:
    """Return stable timing semantics for content-addressed method evidence."""

    return {
        "policy": "runtime_timing_excluded_from_content_addressed_evidence",
        "reason": (
            "wall/cpu/compile timings are volatile runtime observations; "
            "method evidence CAS identity is restricted to semantic execution provenance"
        ),
    }


def resolve_backend(
    kind: str | None,
    *,
    store_factory: Callable[[Path], ArtifactStore] | None = None,
) -> RunnerBackend:
    """Resolve backend."""
    backend_kind = (kind or os.getenv("POLISYOS_RUNNER_BACKEND") or "local").lower()
    if backend_kind != "local":
        raise ValueError(f"Unsupported runner backend '{backend_kind}'. Only 'local' is available.")
    return LocalBackend(store_factory=store_factory)


def _issue_payload(
    loc: list[Any],
    message: str,
    error_type: str,
    input_value: Any = None,
) -> dict[str, Any]:
    issue = ValidationIssue(
        loc=loc,
        message=message,
        error_type=error_type,
        input_value=input_value,
    )
    return cast("dict[str, Any]", issue.model_dump())


def _runner_degraded(
    *,
    operation: str,
    reason: str,
    exc: BaseException,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return emit_degraded_path(
        component="compute.runner",
        operation=operation,
        reason=reason,
        exc=exc,
        details=details,
        log=logger,
    )


def _summarize_state(state: Any) -> dict[str, Any]:
    if state is None:
        return {}
    summary: dict[str, Any] = {}
    try:
        summary["avg_income"] = float(jnp.mean(state.agents.income))
        summary["n_agents"] = int(state.agents.income.shape[0])
    except _RUNNER_DEGRADED_ERRORS as exc:
        _runner_degraded(
            operation="summarize_state",
            reason="summary_field_unavailable",
            exc=exc,
            details={"field": "avg_income"},
        )
    try:
        summary["gov_balance"] = float(state.government_balance)
    except _RUNNER_DEGRADED_ERRORS as exc:
        _runner_degraded(
            operation="summarize_state",
            reason="summary_field_unavailable",
            exc=exc,
            details={"field": "gov_balance"},
        )
    try:
        summary["step"] = int(state.step)
    except _RUNNER_DEGRADED_ERRORS as exc:
        _runner_degraded(
            operation="summarize_state",
            reason="summary_field_unavailable",
            exc=exc,
            details={"field": "step"},
        )
    return summary


def _load_input_refs(
    cas_root: Path,
    input_refs: Mapping[str, ArtifactRef],
    *,
    store_factory: Callable[[Path], ArtifactStore] | None = None,
) -> Any:
    store = (store_factory or _build_store)(cas_root)
    loaded: dict[str, Any] = {}
    for slot_name, ref in input_refs.items():
        payload = store.get_bytes(ref)
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
    store_factory: Callable[[Path], ArtifactStore] | None = None,
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

    store = (store_factory or _build_store)(cas_root) if cas_root is not None else None
    if base_state is None and store is not None and spec.state_snapshot_ref is not None:
        try:
            from polisyos.foundry.execute.executor import load_state_snapshot

            filesystem_store = _require_filesystem_store(
                store,
                operation="scientist.compute.run_job.load_state_snapshot",
            )
            base_state = load_state_snapshot(filesystem_store, snapshot_ref=spec.state_snapshot_ref)
        except _RUNNER_DEGRADED_ERRORS as exc:
            envelope = _runner_degraded(
                operation="load_state_snapshot",
                reason="artifact_load_failed",
                exc=exc,
                details={"artifact_ref": str(spec.state_snapshot_ref.artifact_id)},
            )
            issues.append(
                _issue_payload(
                    ["state_snapshot_ref"],
                    f"Failed to load snapshot: {exc}",
                    "runtime",
                    input_value=envelope,
                )
            )

    if base_state is None:
        issues.append(
            _issue_payload(["job_spec", "state_snapshot_ref"], "base_state missing", "runtime")
        )

    if issues:
        return JobResult(job_key=job_key, issues=issues, warnings=["missing inputs for execution"])

    resolved_cas_root = cas_root
    program_ref = spec.program_ref
    exec_plan_ref = spec.exec_plan_ref
    if resolved_cas_root is None:
        raise RuntimeError("cas_root must be present after validation")
    if program_ref is None or exec_plan_ref is None:
        raise RuntimeError("program_ref and exec_plan_ref must be present after validation")

    try:
        cpu_device = None
        prefer_cpu = False
        if jax is not None:
            try:
                cpu_device = jax.devices("cpu")[0]
            except _RUNNER_DEGRADED_ERRORS as exc:
                _runner_degraded(
                    operation="resolve_cpu_device",
                    reason="device_probe_failed",
                    exc=exc,
                )
                cpu_device = None
            try:
                prefer_cpu = any(device.platform == "metal" for device in jax.devices())
            except _RUNNER_DEGRADED_ERRORS as exc:
                _runner_degraded(
                    operation="detect_preferred_device",
                    reason="device_probe_failed",
                    exc=exc,
                )
                prefer_cpu = False
        if cpu_device is not None and prefer_cpu:
            jax_module = jax
            if jax_module is None:
                raise RuntimeError("jax runtime disappeared during backend execution")
            with jax_module.default_device(cpu_device):
                result = backend.run(
                    cas_root=resolved_cas_root,
                    program_ref=program_ref,
                    exec_plan_ref=exec_plan_ref,
                    base_state=base_state,
                    registry_content=registry_content,
                    seed=spec.seed,
                )
        else:
            result = backend.run(
                cas_root=resolved_cas_root,
                program_ref=program_ref,
                exec_plan_ref=exec_plan_ref,
                base_state=base_state,
                registry_content=registry_content,
                seed=spec.seed,
            )
    except _RUNNER_DEGRADED_ERRORS as exc:
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
                ArtifactWriteOptions(
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
    store_factory: Callable[[Path], ArtifactStore] | None = None,
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
            loaded_state = _load_input_refs(
                cas_root,
                spec.input_refs,
                store_factory=store_factory,
            )
        except _RUNNER_DEGRADED_ERRORS as exc:
            envelope = _runner_degraded(
                operation="load_method_inputs",
                reason="artifact_load_failed",
                exc=exc,
                details={"input_slots": sorted(spec.input_refs)},
            )
            return JobResult(
                job_key=job_key,
                issues=[
                    _issue_payload(
                        ["job_spec", "input_refs"],
                        str(exc),
                        "runtime",
                        input_value=envelope,
                    )
                ],
            )
    if loaded_state is None:
        loaded_state = {}

    resolved_cas_root = cas_root
    method_fqn = spec.method_fqn
    if resolved_cas_root is None:
        raise RuntimeError("cas_root must be present after validation")
    if method_fqn is None:
        raise RuntimeError("method_fqn must be present after validation")

    try:
        result = backend.run(
            cas_root=resolved_cas_root,
            method_fqn=method_fqn,
            method_version=spec.method_version,
            input_state=loaded_state,
            method_params=spec.method_params,
            seed=spec.seed,
            input_refs=spec.input_refs,
        )
    except _RUNNER_DEGRADED_ERRORS as exc:
        return JobResult(
            job_key=job_key,
            issues=[_issue_payload(["method_runner"], str(exc), "runtime")],
        )

    artifacts = result.exec_artifacts
    warnings: list[str] = []
    warnings.extend(adapter_warnings or [])
    if (
        isinstance(result.final_state, dict)
        and "warnings" in result.final_state
        and isinstance(result.final_state["warnings"], list)
    ):
        warnings.extend(str(item) for item in result.final_state["warnings"])

    return JobResult(
        job_key=job_key,
        simulation_results_ref=artifacts.result_ref,
        method_result_ref=artifacts.result_ref,
        method_evidence_ref=artifacts.evidence_ref,
        posterior_summary_refs=artifacts.posterior_summary_refs,
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
    store_factory: Callable[[Path], ArtifactStore] | None = None,
    method_runtime_providers: MethodRuntimeProviders | None = None,
    method_registry_provider: Callable[[], MethodRegistry] | None = None,
    method_dispatcher_provider: Callable[[], MethodDispatcher] | None = None,
) -> JobResult:
    """
    Execute a job spec via either legacy program flow or method flow.
    """
    job_key = JobKey.from_spec(spec)

    if spec.is_method_job:
        adapter_warnings = _materialize_method_adapter(
            spec,
            cas_root=cas_root,
            store_factory=store_factory,
        )
        method_backend = (
            backend
            if isinstance(backend, MethodBackend)
            else MethodBackend(
                store_factory=store_factory,
                providers=method_runtime_providers,
                registry_provider=method_registry_provider,
                dispatcher_provider=method_dispatcher_provider,
            )
        )
        return _run_method_job(
            spec,
            job_key=job_key,
            cas_root=cas_root,
            method_state=method_state,
            backend=method_backend,
            adapter_warnings=adapter_warnings,
            store_factory=store_factory,
        )

    legacy_backend = (
        backend
        if backend is not None
        else resolve_backend(
            None,
            store_factory=store_factory,
        )
    )
    return _run_legacy_job(
        spec,
        job_key=job_key,
        backend=legacy_backend,
        registry_content=registry_content,
        base_state=base_state,
        cas_root=cas_root,
        store_factory=store_factory,
    )


def _materialize_method_adapter(
    spec: JobSpec,
    *,
    cas_root: Path | None,
    store_factory: Callable[[Path], ArtifactStore] | None = None,
) -> list[str]:
    """
    Temporary bridge until all method runs execute through unified ProgramGraph.

    We persist a single-node DAG descriptor so every method run has a stable adapter
    artifact that can be traced in lineage/debug output.
    """
    if cas_root is None:
        return ["legacy_adapter_missing_cas_root"]
    try:
        store = (store_factory or _build_store)(cas_root)
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
            ArtifactWriteOptions(
                kind="scientist.unified_dag_adapter",
                media_type="application/json",
                schema=SchemaInfo(name="polisyos.scientist.UnifiedDagAdapter", version="0.1.0"),
            ),
        )
        return [f"legacy_method_adapter_ref:{ref.artifact_id}"]
    except _RUNNER_DEGRADED_ERRORS as exc:
        envelope = _runner_degraded(
            operation="materialize_method_adapter",
            reason="artifact_write_failed",
            exc=exc,
            details={"method_fqn": spec.method_fqn},
        )
        return [f"legacy_method_adapter_failed:{envelope['message']}"]
