from __future__ import annotations

import logging
from typing import Any, Mapping

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.registry import build_default_registry_bundle, load_registry_bundle_content
from polisyos.core.run.context import RunContext
from polisyos.foundry.compiler import put_policy_surface
from polisyos.ir.surface import PolicySurfaceIR
from polisyos.scientist import deprecated_import
from polisyos.scientist.engine.context import ExecutionContext
from polisyos.scientist.foundry import DefaultFoundryPort
from polisyos.scientist.nodes.builtins.compile.compile_foundry import CompileFoundryNode
from polisyos.scientist.nodes.builtins.simulate.run_simulation import RunSimulationNode
from polisyos.scientist.nodes.builtins.state_keys import (
    INPUT_POLICY_IR_REF,
    INPUT_REGISTRY_BUNDLE_REF,
    INPUT_TRINITY_BUNDLE_REF,
)
from polisyos.scientist.orchestrator import flow_nodes_impl as legacy_impl
from polisyos.scientist.orchestrator.state_adapter import apply_engine_to_legacy, legacy_to_engine_state

_WARNED = False


def _warn_once() -> None:
    global _WARNED
    if _WARNED:
        return
    deprecated_import(
        "polisyos.scientist.orchestrator.flow_nodes is deprecated; use polisyos.scientist.workflows.default (engine)."
    )
    _WARNED = True


def _cas_root(state: Mapping[str, Any]):
    return legacy_impl._cas_root(state)  # reuse legacy resolution


def _ensure_registry_bundle_ref(state: Mapping[str, Any], store: FileSystemCAS) -> ArtifactRef:
    ref_value = state.get("registry_bundle_ref")
    if ref_value:
        try:
            return ArtifactRef.model_validate(ref_value)
        except Exception:
            pass
    bundle = build_default_registry_bundle(store)
    return bundle.bundle_ref


def _ensure_policy_ir_ref(state: Mapping[str, Any], store: FileSystemCAS, registry_ref: ArtifactRef) -> ArtifactRef | None:
    ref_value = state.get("policy_ir_ref")
    if ref_value:
        try:
            return ArtifactRef.model_validate(ref_value)
        except Exception:
            pass
    ir = state.get("ir")
    if isinstance(ir, PolicySurfaceIR):
        registries = load_registry_bundle_content(store, registry_ref)
        return put_policy_surface(
            store,
            ir,
            mechanism_registry=registries.mechanism_registry,
            units_registry=registries.units_registry,
        )
    return None


def _build_execution_context(store: FileSystemCAS, run_id: str, registry_ref: ArtifactRef) -> ExecutionContext:
    run_ctx = RunContext.start(store, registry_ref, run_id=run_id)
    return ExecutionContext(
        store=store,
        run=run_ctx,
        logger=logging.getLogger("polisyos.scientist.legacy"),
        foundry=DefaultFoundryPort(),
    )


def _feedback_for_error(code: str, message: str) -> dict[str, Any]:
    return {
        "verdict": "NEEDS_REVISION",
        "issues": [
            {
                "severity": "error",
                "error_type": "runtime",
                "code": code,
                "message": message,
            }
        ],
    }


def _compile_model_node_engine(state: Mapping[str, Any]) -> dict[str, Any]:
    store = FileSystemCAS(_cas_root(state))
    registry_ref = _ensure_registry_bundle_ref(state, store)
    run_id = str(state.get("run_id") or "R_legacy")
    ctx = _build_execution_context(store, run_id, registry_ref)

    engine_state = legacy_to_engine_state(state)

    trinity_ref_val = state.get("trinity_bundle_ref")
    if trinity_ref_val:
        try:
            engine_state.inputs[INPUT_TRINITY_BUNDLE_REF] = ArtifactRef.model_validate(
                trinity_ref_val
            )
        except Exception:
            pass

    policy_ref = _ensure_policy_ir_ref(state, store, registry_ref)
    if policy_ref is not None:
        engine_state.inputs[INPUT_POLICY_IR_REF] = policy_ref

    engine_state.inputs[INPUT_REGISTRY_BUNDLE_REF] = registry_ref

    node = CompileFoundryNode()
    outcome = node.execute(ctx, engine_state)
    updated = apply_engine_to_legacy(outcome.state, state)

    if outcome.status == "fail" and outcome.error is not None:
        updated["feedback"] = _feedback_for_error(outcome.error.code, outcome.error.message)

    return updated


def _run_sim_node_engine(state: Mapping[str, Any]) -> dict[str, Any]:
    store = FileSystemCAS(_cas_root(state))
    registry_ref = _ensure_registry_bundle_ref(state, store)
    run_id = str(state.get("run_id") or "R_legacy")
    ctx = _build_execution_context(store, run_id, registry_ref)

    engine_state = legacy_to_engine_state(state)
    engine_state.inputs[INPUT_REGISTRY_BUNDLE_REF] = registry_ref

    node = RunSimulationNode()
    outcome = node.execute(ctx, engine_state)
    updated = apply_engine_to_legacy(outcome.state, state)

    if outcome.status == "fail" and outcome.error is not None:
        updated["feedback"] = _feedback_for_error(outcome.error.code, outcome.error.message)
        return updated

    # Best-effort metrics -> simulation_results legacy field
    metrics_ref = outcome.state.artifacts_index.get("metrics_ref")
    if metrics_ref is not None:
        try:
            payload = from_canonical_bytes(store.get_bytes(metrics_ref.artifact_id))
            updated["simulation_results"] = payload.get("values") if isinstance(payload, dict) else payload
        except Exception:
            pass

    return updated


# Legacy wrappers (LLM/governance/reflexion) defer to previous implementation.

def pi_decompose_node(state):
    _warn_once()
    return legacy_impl.pi_decompose_node(state)


def drafter_node(state):
    _warn_once()
    return legacy_impl.drafter_node(state)


def formalize_node(state):
    _warn_once()
    return legacy_impl.formalize_node(state)


def critic_review_node(state):
    _warn_once()
    return legacy_impl.critic_review_node(state)


def reflexion_node(state):
    _warn_once()
    return legacy_impl.reflexion_node(state)


def validate_ir_node(state):
    _warn_once()
    return legacy_impl.validate_ir_node(state)


def repair_ir_node(state):
    _warn_once()
    return legacy_impl.repair_ir_node(state)


def compile_data_views_node(state):
    _warn_once()
    return legacy_impl.compile_data_views_node(state)


def compile_model_node(state):
    _warn_once()
    return _compile_model_node_engine(state)


def train_agents_node(state):
    _warn_once()
    return legacy_impl.train_agents_node(state)


def run_sim_node(state):
    _warn_once()
    return _run_sim_node_engine(state)


def analyze_node(state):
    _warn_once()
    return legacy_impl.analyze_node(state)


def governor_node(state):
    _warn_once()
    return legacy_impl.governor_node(state)


def pack_decision_node(state):
    _warn_once()
    return legacy_impl.pack_decision_node(state)


def draft_ir_node(state):
    _warn_once()
    return legacy_impl.draft_ir_node(state)


def reflexion_repair_node(state):
    _warn_once()
    return legacy_impl.reflexion_repair_node(state)


def run_calibration_node(state):
    _warn_once()
    return legacy_impl.run_calibration_node(state)
