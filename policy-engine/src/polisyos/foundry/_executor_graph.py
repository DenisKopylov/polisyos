"""Program-graph orchestrator — execute_program_graph and direct helpers."""
from __future__ import annotations

import logging
import time
from typing import Any

logger = logging.getLogger(__name__)

import jax
import jax.numpy as jnp
from pydantic import TypeAdapter

from polisyos.core.artifacts.environment import (
    EnvironmentManifest,
    EnvironmentManifestRef,
    capture_environment,
)
from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactRef, InputRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.contracts.foundry import (
    ConstraintReport,
    ConstraintReportRef,
    ExecPlan,
    LoweredIR,
    Metrics,
    PatchOp,
    ProgramGraph,
    StateDelta,
)
from polisyos.foundry.agents import AdaptiveAgentMechanism
from polisyos.foundry.patch_vm import merge_patch_records
from polisyos.foundry.registry import create_mechanism_from_spec
from polisyos.ir.governance.schedule import ScheduleSpec, schedule_range
from polisyos.ir.governance.selector_expr import SelectorExpr
from polisyos.ir.kernel import (
    ConstraintRegistry,
    MechanismTypeRegistry,
    MergeRuleRegistry,
    SelectorFieldRegistry,
    SlotRegistry,
    SlotScope,
)

from ._executor_models import ExecuteArtifacts, artifact_id, load_model, load_payload
from ._executor_ops import apply_ops_to_state, coerce_number, evaluate_selector
from .constraints_engine import check_constraints as evaluate_lowered_constraints

__all__ = [
    "execute_program_graph",
]

_SELECTOR_ADAPTER = TypeAdapter(SelectorExpr)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def execute_program_graph(
    store: FileSystemCAS,
    *,
    program_ref: ArtifactRef | ArtifactID | str,
    exec_plan_ref: ArtifactRef | ArtifactID | str,
    base_state: Any,
    mechanism_registry: MechanismTypeRegistry,
    slot_registry: SlotRegistry,
    merge_registry: MergeRuleRegistry,
    selector_field_registry: SelectorFieldRegistry | None = None,
    constraint_registry: ConstraintRegistry | None = None,
    step: int = 0,
    seed: int = 0,
    base_ref: ArtifactRef | None = None,
    project_root: str | None = None,
    capture_env: bool = False,
    parameter_overrides: dict[str, dict[str, Any]] | None = None,
    parameter_override_bundle_ref: ArtifactRef | None = None,
) -> ExecuteArtifacts:
    env_manifest_ref: EnvironmentManifestRef | None = None
    env_fingerprint: str | None = None
    if capture_env:
        env_manifest = capture_environment(
            project_root=project_root,
            include_git=True,
            include_dependencies=True,
            custom_metadata={
                "seed": seed,
                "seed_source": "jax_prng",
                "exec_plan_id": str(artifact_id(exec_plan_ref)),
            },
        )
        env_manifest_ref = _persist_environment_manifest(store, env_manifest, exec_plan_ref)
        env_fingerprint = env_manifest.fingerprint
        _log_environment_captured(env_manifest)

    start_time = time.perf_counter()
    program_graph = load_model(store, program_ref, ProgramGraph)
    exec_plan = load_model(store, exec_plan_ref, ExecPlan)
    if program_graph.lowered_ir_ref is None:
        raise ValueError("program_graph_missing_lowered_ir_ref")
    lowered_ir = load_model(store, program_graph.lowered_ir_ref, LoweredIR)

    order = exec_plan.order or [node.node_id for node in program_graph.nodes]
    node_map = {node.node_id: node for node in program_graph.nodes}

    n_agents = getattr(base_state.agents, "size", None)
    if n_agents is None:
        n_agents = int(base_state.agents.income.shape[0])
    n_firms = getattr(base_state.firms, "size", None)
    if n_firms is None:
        n_firms = int(base_state.firms.capital.shape[0])

    key = jax.random.PRNGKey(seed)
    tax_rate_value = _resolve_income_tax_rate(
        program_graph,
        store,
        step,
        parameter_overrides=parameter_overrides,
    )
    patch_records: dict[str, list[dict[str, Any]]] = {}
    ops: list[PatchOp] = []
    applied_nodes = 0
    skipped_nodes = 0
    op_nodes = 0
    checked_constraints = 0
    masks: dict[str, tuple[jnp.ndarray, SlotScope]] = {}
    state_for_checks = base_state
    constraint_report = ConstraintReport(
        ok=True,
        hard_fail=False,
        constraint_mode=lowered_ir.constraint_mode,
        total_constraints=0,
        violations=[],
        penalty_total=None,
        notes=[],
    )

    for node_id in order:
        node = node_map.get(node_id)
        if node is None:
            skipped_nodes += 1
            continue
        if node.node_kind == "op":
            op_nodes += 1
            if node.op is None:
                skipped_nodes += 1
                continue
            if node.op.op_kind == "make_mask":
                selector_payload = node.op.params.get("selector") or {}
                target = _SELECTOR_ADAPTER.validate_python(selector_payload)
                mask, scope = evaluate_selector(
                    target, base_state, selector_field_registry=selector_field_registry
                )
                masks[node.node_id] = (mask, scope)
                continue
            if node.op.op_kind == "apply_mechanism":
                if node.params_ref is None:
                    skipped_nodes += 1
                    continue
                payload = _load_node_payload(
                    store,
                    node=node,
                    parameter_overrides=parameter_overrides,
                )
                schedule = ScheduleSpec.model_validate(payload.get("schedule", {}))
                start, end = schedule_range(schedule)
                if step < start or step > end:
                    skipped_nodes += 1
                    continue

                mask_info = None
                mask_id = node.op.params.get("mask_id")
                if isinstance(mask_id, str):
                    mask_info = masks.get(mask_id)
                if mask_info is None:
                    selector_payload = payload.get("selector") or payload.get("target") or {}
                    target = _SELECTOR_ADAPTER.validate_python(selector_payload)
                    mask_info = evaluate_selector(
                        target, base_state, selector_field_registry=selector_field_registry
                    )
                mask, mask_scope = mask_info

                params = payload.get("params", {})
                mechanism_type = node.mechanism_type or payload.get("mechanism_id")
                mechanism_spec = mechanism_registry.mechanisms.get(mechanism_type)
                mechanism = create_mechanism_from_spec(
                    mechanism_type,
                    params,
                    n_agents=n_agents,
                    n_firms=n_firms,
                    mechanism_spec=mechanism_spec,
                    selected_fidelity=payload.get("selected_fidelity"),
                )
                if (
                    tax_rate_value is not None
                    and isinstance(mechanism, AdaptiveAgentMechanism)
                    and (
                        "global.tax_rate" in mechanism.observation_space
                        or "policy.tax_rate" in mechanism.observation_space
                    )
                ):
                    object.__setattr__(mechanism, "tax_rate_value", tax_rate_value)
                key, step_key = jax.random.split(key)
                patch_map, key = mechanism.emit_patches(
                    base_state,
                    step_key,
                    target_mask=mask
                    if mask_scope in {SlotScope.PER_AGENT, SlotScope.PER_FIRM}
                    else None,
                )
                if patch_map is None:
                    raise ValueError(f"Mechanism '{mechanism_type}' did not emit patches")
                applied_nodes += 1
                for slot_id, patches in patch_map.items():
                    patch_list = patches if isinstance(patches, list) else [patches]
                    for patch in patch_list:
                        record = {
                            "node_id": node_id,
                            "priority": payload.get("priority"),
                        }
                        record.update(patch)
                        patch_records.setdefault(slot_id, []).append(record)
                continue
            if node.op.op_kind == "merge_state":
                ops = merge_patch_records(
                    store,
                    patch_records,
                    slot_registry=slot_registry,
                    merge_registry=merge_registry,
                )
                patch_records = {}
                if constraint_registry is not None:
                    state_for_checks = apply_ops_to_state(
                        store,
                        base_state=base_state,
                        ops=ops,
                        slot_registry=slot_registry,
                        merge_registry=merge_registry,
                    )
            elif node.op.op_kind == "check_constraints":
                ids = node.op.params.get("constraint_ids") or []
                if constraint_registry is not None:
                    constraint_ids = [item for item in ids if isinstance(item, str)]
                    lowered_constraints = [
                        item
                        for item in lowered_ir.constraints
                        if item.constraint_id in constraint_ids
                    ]
                    checked_constraints += len(lowered_constraints)
                    constraint_report = evaluate_lowered_constraints(
                        constraints=lowered_constraints,
                        slot_registry=slot_registry,
                        state=state_for_checks,
                    )
            else:
                skipped_nodes += 1
            continue
        if node.node_kind == "mechanism":
            if node.params_ref is None:
                skipped_nodes += 1
                continue
            payload = _load_node_payload(
                store,
                node=node,
                parameter_overrides=parameter_overrides,
            )
            schedule = ScheduleSpec.model_validate(payload.get("schedule", {}))
            start, end = schedule_range(schedule)
            if step < start or step > end:
                skipped_nodes += 1
                continue
            params = payload.get("params", {})
            mechanism_type = node.mechanism_type
            mechanism_spec = mechanism_registry.mechanisms.get(mechanism_type)
            mechanism = create_mechanism_from_spec(
                mechanism_type,
                params,
                n_agents=n_agents,
                n_firms=n_firms,
                mechanism_spec=mechanism_spec,
                selected_fidelity=payload.get("selected_fidelity"),
            )
            if (
                tax_rate_value is not None
                and isinstance(mechanism, AdaptiveAgentMechanism)
                and (
                    "global.tax_rate" in mechanism.observation_space
                    or "policy.tax_rate" in mechanism.observation_space
                )
            ):
                object.__setattr__(mechanism, "tax_rate_value", tax_rate_value)
            key, step_key = jax.random.split(key)
            patch_map, key = mechanism.emit_patches(base_state, step_key)
            if patch_map is None:
                raise ValueError(f"Mechanism '{mechanism_type}' did not emit patches")
            applied_nodes += 1
            for slot_id, patches in patch_map.items():
                patch_list = patches if isinstance(patches, list) else [patches]
                for patch in patch_list:
                    record = {
                        "node_id": node_id,
                        "priority": payload.get("priority"),
                    }
                    record.update(patch)
                    patch_records.setdefault(slot_id, []).append(record)
            continue
        if node.node_kind == "method":
            method_fqn = node.method_fqn
            if not method_fqn:
                skipped_nodes += 1
                continue
            try:
                from polisyos.foundry.methods.backends.dispatch import MethodDispatcher
                from polisyos.foundry.methods.registry import MethodRegistry

                registry = MethodRegistry.get_instance()
                method_class = registry.get(method_fqn, version=node.method_version)
                signature = method_class.signature
                dispatcher = MethodDispatcher.get_instance()
                method_result = dispatcher.dispatch(
                    method_class=method_class,
                    signature=signature,
                    state=base_state,
                    params=node.method_params,
                    seed=seed,
                )
                output_payload = method_result.output
                if isinstance(output_payload, dict):
                    patch_payload = output_payload.get("patch_records")
                    if isinstance(patch_payload, dict):
                        for slot_id, patches in patch_payload.items():
                            if isinstance(patches, list):
                                for patch in patches:
                                    if isinstance(patch, dict):
                                        patch_records.setdefault(str(slot_id), []).append(patch)
                applied_nodes += 1
            except Exception as exc:
                logger.debug(
                    "Failed to execute method node '%s' (method=%s): %s",
                    node_id, method_fqn, exc,
                )
                skipped_nodes += 1
            continue
        skipped_nodes += 1

    if patch_records:
        ops = merge_patch_records(
            store,
            patch_records,
            slot_registry=slot_registry,
            merge_registry=merge_registry,
        )

    latency_ms = int((time.perf_counter() - start_time) * 1000)

    inputs = [
        InputRef(artifact_id=artifact_id(program_ref), role="program_graph"),
        InputRef(artifact_id=artifact_id(exec_plan_ref), role="exec_plan"),
    ]
    if program_graph.lowered_ir_ref is not None:
        inputs.append(
            InputRef(artifact_id=program_graph.lowered_ir_ref.artifact_id, role="lowered_ir")
        )
    if parameter_override_bundle_ref is not None:
        inputs.append(
            InputRef(
                artifact_id=parameter_override_bundle_ref.artifact_id,
                role="parameter_override_bundle",
            )
        )
    for op in ops:
        if op.value_ref is not None:
            inputs.append(InputRef(artifact_id=op.value_ref.artifact_id, role="patch_value"))

    state_delta = StateDelta(base_ref=base_ref, ops=ops)
    state_delta_ref = store.put_json(
        state_delta,
        PutOptions(
            kind="foundry.state_delta",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.StateDelta", version="0.1.0"),
            inputs=inputs,
        ),
    )

    metrics = Metrics(
        values={
            "applied_nodes": int(applied_nodes),
            "skipped_nodes": int(skipped_nodes),
            "op_nodes": int(op_nodes),
            "checked_constraints": int(checked_constraints),
            "patch_ops": int(len(ops)),
            "step": int(step),
            "step_latency_ms": latency_ms,
            "constraint_hard_fail": int(constraint_report.hard_fail),
        }
    )
    metrics_ref = store.put_json(
        metrics,
        PutOptions(
            kind="foundry.metrics",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.Metrics", version="0.1.0"),
            inputs=inputs,
        ),
    )

    constraint_report_ref = None
    if constraint_registry is not None or lowered_ir.constraints:
        cref = store.put_json(
            constraint_report,
            PutOptions(
                kind="foundry.constraint_report",
                media_type="application/json",
                schema=SchemaInfo(name="polisyos.core.ConstraintReport", version="1.0"),
                inputs=inputs,
            ),
        )
        constraint_report_ref = ConstraintReportRef.model_validate(cref.model_dump())

    return ExecuteArtifacts(
        state_delta_ref=state_delta_ref,
        metrics_ref=metrics_ref,
        constraint_report_ref=constraint_report_ref,
        constraint_hard_fail=constraint_report.hard_fail,
        environment_ref=env_manifest_ref,
        environment_fingerprint=env_fingerprint,
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _persist_environment_manifest(
    store: FileSystemCAS,
    manifest: EnvironmentManifest,
    exec_plan_ref: ArtifactRef | ArtifactID | str,
) -> EnvironmentManifestRef:
    artifact_ref = store.put_json(
        manifest,
        PutOptions(
            kind="foundry.environment_manifest",
            media_type="application/json",
            schema=SchemaInfo(
                name="polisyos.core.artifacts.environment.EnvironmentManifest",
                version="1.0",
            ),
            inputs=[InputRef(artifact_id=artifact_id(exec_plan_ref), role="exec_plan")],
        ),
    )
    return EnvironmentManifestRef(artifact_id=artifact_ref.artifact_id)


def _log_environment_captured(manifest: EnvironmentManifest) -> None:
    from polisyos.common.logger import get_logger

    log = get_logger(__name__)
    log.info(
        "Environment captured",
        fingerprint=manifest.fingerprint,
        cpu_arch=manifest.cpu.architecture,
        jax_version=manifest.jax.jax_version,
        cuda_version=manifest.gpu.cuda_version,
        python_version=manifest.python.version,
        git_commit=manifest.git.commit_short if manifest.git else None,
    )


def _resolve_income_tax_rate(
    program_graph: ProgramGraph,
    store: FileSystemCAS,
    step: int,
    parameter_overrides: dict[str, dict[str, Any]] | None = None,
) -> jnp.ndarray | None:
    for node in program_graph.nodes:
        if node.mechanism_type != "income_tax" or node.params_ref is None:
            continue
        payload = _load_node_payload(
            store,
            node=node,
            parameter_overrides=parameter_overrides,
        )
        schedule = ScheduleSpec.model_validate(payload.get("schedule", {}))
        start, end = schedule_range(schedule)
        if step < start or step > end:
            continue
        params = payload.get("params", {})
        numeric = coerce_number(params.get("rate"))
        if numeric is None:
            continue
        return jnp.array(float(numeric), dtype=jnp.float32)
    return None


def _load_node_payload(
    store: FileSystemCAS,
    *,
    node: Any,
    parameter_overrides: dict[str, dict[str, Any]] | None,
) -> dict[str, Any]:
    payload = load_payload(store, node.params_ref)
    if not isinstance(payload, dict):
        return {}
    if not parameter_overrides:
        return payload
    node_overrides = parameter_overrides.get(str(node.node_id))
    if not isinstance(node_overrides, dict) or not node_overrides:
        return payload
    merged_payload = dict(payload)
    params = payload.get("params")
    merged_payload["params"] = {**(params if isinstance(params, dict) else {}), **node_overrides}
    return merged_payload
