"""Stable execute facade for compiled Foundry plans."""

from __future__ import annotations

import importlib
import sys
import types
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from polisyos.foundry.execute.executor import load_model, load_payload

__all__ = [
    "BoundedNumericNPZError",
    "BoundedStateSnapshotInputs",
    "ExecutionSourceAdmission",
    "ExecutionSourceAdmissionRefusal",
    "BoundedExecutionSourceReader",
    "ProgramGraphExecutionObserver",
    "ExecutionSourceBoundedReadRefusal",
    "ResolvedExecutionPosture",
    "SnapshotStateInputReadRefusal",
    "StateSnapshotInputReadUsage",
    "StateSnapshotInputReadRefusal",
    "SnapshotStateLayoutError",
    "admit_execution_source",
    "admit_execution_source_bounded",
    "apply_state_delta",
    "admit_semantic_horizon_step_chain",
    "execute",
    "execute_program_graph",
    "execute_semantic_horizon_step",
    "read_method_artifact_output_bounded",
    "execution_input_basis_sources",
    "get_state_path",
    "load_model",
    "load_payload",
    "load_state_snapshot",
    "new_method_execution_capture",
    "persist_method_execution_capture",
    "prepare_program_graph_mechanism_calls",
    "put_state_snapshot",
    "program_graph_declares_model_input_ports",
    "recompute_program_graph_inputs",
    "resolve_core_json_profile_store",
    "resolve_program_graph_input_declaration",
    "verify_program_graph_input_preflight",
    "StateSnapshotValueLeaf",
    "state_snapshot_value_projection",
    "read_numeric_npz_bounded",
    "read_state_snapshot_inputs_bounded",
    "resolve_execution_posture",
]

_LAZY_IMPORTS: dict[str, tuple[str, str]] = {
    "ProgramGraphExecutionObserver": (
        "polisyos.foundry.execute.observation",
        "ProgramGraphExecutionObserver",
    ),
    "StateSnapshotValueLeaf": (
        "polisyos.foundry.execute._internal.snapshots",
        "StateSnapshotValueLeaf",
    ),
    "state_snapshot_value_projection": (
        "polisyos.foundry.execute._internal.snapshots",
        "state_snapshot_value_projection",
    ),
    "BoundedNumericNPZError": (
        "polisyos.foundry.execute._internal.snapshots",
        "BoundedNumericNPZError",
    ),
    "read_numeric_npz_bounded": (
        "polisyos.foundry.execute._internal.snapshots",
        "read_numeric_npz_bounded",
    ),
    "BoundedStateSnapshotInputs": (
        "polisyos.foundry.execute._internal.snapshots",
        "BoundedStateSnapshotInputs",
    ),
    "ExecutionSourceAdmission": (
        "polisyos.foundry.execute.api",
        "ExecutionSourceAdmission",
    ),
    "BoundedExecutionSourceReader": (
        "polisyos.foundry.execute.api",
        "BoundedExecutionSourceReader",
    ),
    "ExecutionSourceBoundedReadRefusal": (
        "polisyos.foundry.execute.api",
        "ExecutionSourceBoundedReadRefusal",
    ),
    "ExecutionSourceAdmissionRefusal": (
        "polisyos.foundry.execute.api",
        "ExecutionSourceAdmissionRefusal",
    ),
    "admit_semantic_horizon_step_chain": (
        "polisyos.foundry.execute.api",
        "admit_semantic_horizon_step_chain",
    ),
    "ResolvedExecutionPosture": (
        "polisyos.foundry.execute.api",
        "ResolvedExecutionPosture",
    ),
    "SnapshotStateInputReadRefusal": (
        "polisyos.foundry.execute._internal.snapshots",
        "StateSnapshotInputReadRefusal",
    ),
    "StateSnapshotInputReadUsage": (
        "polisyos.foundry.execute._internal.snapshots",
        "StateSnapshotInputReadUsage",
    ),
    "StateSnapshotInputReadRefusal": (
        "polisyos.foundry.execute._internal.snapshots",
        "StateSnapshotInputReadRefusal",
    ),
    "SnapshotStateLayoutError": (
        "polisyos.foundry.execute._internal.snapshots",
        "_SnapshotStateLayoutError",
    ),
    "admit_execution_source_bounded": (
        "polisyos.foundry.execute.api",
        "admit_execution_source_bounded",
    ),
    "admit_execution_source": (
        "polisyos.foundry.execute.api",
        "admit_execution_source",
    ),
    "apply_state_delta": (
        "polisyos.foundry.execute._internal.patching",
        "apply_state_delta",
    ),
    "execute": ("polisyos.foundry.execute.api", "execute"),
    "execute_semantic_horizon_step": (
        "polisyos.foundry.execute.api",
        "execute_semantic_horizon_step",
    ),
    "execute_program_graph": (
        "polisyos.foundry.execute.executor",
        "execute_program_graph",
    ),
    "read_method_artifact_output_bounded": (
        "polisyos.foundry.execute.api",
        "read_method_artifact_output_bounded",
    ),
    "execution_input_basis_sources": (
        "polisyos.foundry.execute.api",
        "execution_input_basis_sources",
    ),
    "get_state_path": ("polisyos.foundry.execute._internal.models", "get_state_path"),
    "load_model": ("polisyos.foundry.execute.executor", "load_model"),
    "load_payload": ("polisyos.foundry.execute.executor", "load_payload"),
    "load_state_snapshot": (
        "polisyos.foundry.execute._internal.snapshots",
        "load_state_snapshot",
    ),
    "new_method_execution_capture": (
        "polisyos.foundry.execute.executor",
        "new_method_execution_capture",
    ),
    "persist_method_execution_capture": (
        "polisyos.foundry.execute.executor",
        "persist_method_execution_capture",
    ),
    "prepare_program_graph_mechanism_calls": (
        "polisyos.foundry.execute.executor",
        "prepare_program_graph_mechanism_calls",
    ),
    "program_graph_declares_model_input_ports": (
        "polisyos.foundry.execute.model_input_requirements",
        "program_graph_declares_model_input_ports",
    ),
    "recompute_program_graph_inputs": (
        "polisyos.foundry.execute.model_input_requirements",
        "recompute_program_graph_inputs",
    ),
    "resolve_core_json_profile_store": (
        "polisyos.foundry._artifact_capabilities",
        "resolve_core_json_profile_store",
    ),
    "resolve_program_graph_input_declaration": (
        "polisyos.foundry.execute.model_input_requirements",
        "resolve_program_graph_input_declaration",
    ),
    "put_state_snapshot": (
        "polisyos.foundry.execute._internal.snapshots",
        "put_state_snapshot",
    ),
    "read_state_snapshot_inputs_bounded": (
        "polisyos.foundry.execute._internal.snapshots",
        "read_state_snapshot_inputs_bounded",
    ),
    "resolve_execution_posture": (
        "polisyos.foundry.execute.api",
        "resolve_execution_posture",
    ),
    "verify_program_graph_input_preflight": (
        "polisyos.foundry.execute.model_input_requirements",
        "verify_program_graph_input_preflight",
    ),
}


def __getattr__(name: str) -> Any:
    if name in _LAZY_IMPORTS:
        module_name, attr_name = _LAZY_IMPORTS[name]
        value = getattr(importlib.import_module(module_name), attr_name)
        globals()[name] = value
        return value

    module_name = f"{__name__}.{name}"
    try:
        value = importlib.import_module(module_name)
    except ModuleNotFoundError as exc:
        if exc.name == module_name:
            raise AttributeError(
                f"module 'polisyos.foundry.execute' has no attribute {name!r}"
            ) from None
        raise
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(list(globals().keys()) + list(_LAZY_IMPORTS.keys()))


class _CallableExecuteModule(types.ModuleType):
    """Allow `polisyos.foundry.execute(...)` while preserving package imports."""

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        return __getattr__("execute")(*args, **kwargs)


sys.modules[__name__].__class__ = _CallableExecuteModule
