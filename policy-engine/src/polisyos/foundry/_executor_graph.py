"""Program-graph orchestrator — execute_program_graph and direct helpers."""
from __future__ import annotations

import time
from typing import Any

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
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.contracts.foundry import (
    ConstraintReportRef,
    ExecPlan,
    Metrics,
    PatchOp,
    ProgramGraph,
    StateDelta,
)
from polisyos.foundry.agents import AdaptiveAgentMechanism
from polisyos.foundry.patch_vm import merge_patch_records
from polisyos.foundry.registry import create_mechanism_from_spec
from polisyos.ir.kernel import (
    ConstraintRegistry,
    MechanismTypeRegistry,
    MergeRuleRegistry,
    SelectorFieldRegistry,
    SlotRegistry,
    SlotScope,
)
from polisyos.ir.governance.schedule import ScheduleSpec, schedule_range
from polisyos.ir.governance.selector_expr import SelectorExpr
from polisyos.ir.trinity import TrinityBundle

from ._executor_models import ExecuteArtifacts, artifact_id, load_model, load_payload
from ._executor_ops import check_constraints, coerce_number, evaluate_selector, apply_ops_to_state

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

    order = exec_plan.order or [node.node_id for node in program_graph.nodes]
    node_map = {node.node_id: node for node in program_graph.nodes}

    n_agents = getattr(base_state.agents, "size", None)
    if n_agents is None:
        n_agents = int(base_state.agents.income.shape[0])
    n_firms = getattr(base_state.firms, "size", None)
    if n_firms is None:
        n_firms = int(base_state.firms.capital.shape[0])

    key = jax.random.PRNGKey(seed)
    tax_rate_value = _resolve_income_tax_rate(program_graph, store, step)
    patch_records: dict[str, list[dict[str, Any]]] = {}
    ops: list[PatchOp] = []
    applied_nodes = 0
    skipped_nodes = 0
    op_nodes = 0
    checked_constraints = 0
    masks: dict[str, tuple[jnp.ndarray, SlotScope]] = {}
    state_for_checks = base_state

    constraint_values: dict[str, Any] = {}
    if constraint_registry is not None:
        try:
            ir_payload = from_canonical_bytes(store.get_bytes(program_graph.ir_ref.artifact_id))
            if program_graph.ir_ref.kind == "ir.trinity_bundle":
                bundle = TrinityBundle.model_validate(ir_payload)
                constraint_values = {
                    constraint.constraint_id: constraint.value
                    for constraint in (
                        bundle.problem_frame.hard_constraints
                        + bundle.problem_frame.soft_constraints
                    )
                }
            else:
                raise ValueError(
                    f"Unsupported IR kind for constraints: {program_graph.ir_ref.kind}"
                )
        except Exception as exc:  # pragma: no cover - defensive
            raise ValueError(f"Failed to load policy for constraints: {exc}") from exc
    constraint_events: list[dict[str, Any]] = []

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
                payload = load_payload(store, node.params_ref)
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
                    selector_payload = payload.get("target") or {}
                    target = _SELECTOR_ADAPTER.validate_python(selector_payload)
                    mask_info = evaluate_selector(
                        target, base_state, selector_field_registry=selector_field_registry
                    )
                mask, mask_scope = mask_info

                params = payload.get("params", {})
                mechanism_type = node.mechanism_type
                mechanism = create_mechanism_from_spec(
                    mechanism_type, params, n_agents=n_agents, n_firms=n_firms
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
                if isinstance(ids, list):
                    checked_constraints += len(ids)
                if constraint_registry is not None:
                    check_constraints(
                        ids,
                        constraint_registry=constraint_registry,
                        constraint_values=constraint_values,
                        slot_registry=slot_registry,
                        state=state_for_checks,
                        events=constraint_events,
                    )
            else:
                skipped_nodes += 1
            continue
        if node.node_kind == "mechanism":
            if node.params_ref is None:
                skipped_nodes += 1
                continue
            payload = load_payload(store, node.params_ref)
            schedule = ScheduleSpec.model_validate(payload.get("schedule", {}))
            start, end = schedule_range(schedule)
            if step < start or step > end:
                skipped_nodes += 1
                continue
            params = payload.get("params", {})
            mechanism_type = node.mechanism_type
            mechanism = create_mechanism_from_spec(
                mechanism_type, params, n_agents=n_agents, n_firms=n_firms
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
    if constraint_registry is not None:
        report = {
            "schema_version": "1.0",
            "step": step,
            "checked": checked_constraints,
            "events": constraint_events,
        }
        cref = store.put_json(
            report,
            PutOptions(
                kind="foundry.constraint_report",
                media_type="application/json",
                inputs=inputs,
            ),
        )
        constraint_report_ref = ConstraintReportRef.model_validate(cref.model_dump())

    return ExecuteArtifacts(
        state_delta_ref=state_delta_ref,
        metrics_ref=metrics_ref,
        constraint_report_ref=constraint_report_ref,
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
) -> jnp.ndarray | None:
    for node in program_graph.nodes:
        if node.mechanism_type != "income_tax" or node.params_ref is None:
            continue
        payload = load_payload(store, node.params_ref)
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
