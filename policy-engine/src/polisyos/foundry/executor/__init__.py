"""Compatibility shim for a Phase 5/6 decomposition module move."""

from __future__ import annotations

import importlib
from typing import Any

__all__ = (
    "ApplyArtifacts",
    "ExecuteArtifacts",
    "apply_op",
    "apply_operator",
    "apply_ops_for_slot",
    "apply_ops_to_state",
    "apply_patch_map",
    "apply_patch_records",
    "apply_state_delta",
    "apply_state_delta_and_snapshot",
    "artifact_id",
    "check_constraints",
    "coerce_number",
    "coerce_selector_scalar",
    "evaluate_selector",
    "execute_program_graph",
    "export_seed_state_npz",
    "get_state_path",
    "import_seed_state_npz",
    "load_model",
    "load_payload",
    "load_state_snapshot",
    "load_tensor",
    "put_state_snapshot",
    "put_tensor",
    "selector_field_values",
    "set_state_path",
    "validate_ops_compatibility",
)

_LAZY_IMPORTS: dict[str, tuple[str, str]] = {
    "ApplyArtifacts": ("polisyos.foundry.execute.executor", "ApplyArtifacts"),
    "ExecuteArtifacts": ("polisyos.foundry.execute.executor", "ExecuteArtifacts"),
    "apply_op": ("polisyos.foundry.execute.executor", "apply_op"),
    "apply_operator": ("polisyos.foundry.execute.executor", "apply_operator"),
    "apply_ops_for_slot": ("polisyos.foundry.execute.executor", "apply_ops_for_slot"),
    "apply_ops_to_state": ("polisyos.foundry.execute.executor", "apply_ops_to_state"),
    "apply_patch_map": ("polisyos.foundry.execute.executor", "apply_patch_map"),
    "apply_patch_records": ("polisyos.foundry.execute.executor", "apply_patch_records"),
    "apply_state_delta": ("polisyos.foundry.execute.executor", "apply_state_delta"),
    "apply_state_delta_and_snapshot": (
        "polisyos.foundry.execute.executor",
        "apply_state_delta_and_snapshot",
    ),
    "artifact_id": ("polisyos.foundry.execute.executor", "artifact_id"),
    "check_constraints": ("polisyos.foundry.execute.executor", "check_constraints"),
    "coerce_number": ("polisyos.foundry.execute.executor", "coerce_number"),
    "coerce_selector_scalar": ("polisyos.foundry.execute.executor", "coerce_selector_scalar"),
    "evaluate_selector": ("polisyos.foundry.execute.executor", "evaluate_selector"),
    "execute_program_graph": ("polisyos.foundry.execute.executor", "execute_program_graph"),
    "export_seed_state_npz": ("polisyos.foundry.execute.executor", "export_seed_state_npz"),
    "get_state_path": ("polisyos.foundry.execute.executor", "get_state_path"),
    "import_seed_state_npz": ("polisyos.foundry.execute.executor", "import_seed_state_npz"),
    "load_model": ("polisyos.foundry.execute.executor", "load_model"),
    "load_payload": ("polisyos.foundry.execute.executor", "load_payload"),
    "load_state_snapshot": ("polisyos.foundry.execute.executor", "load_state_snapshot"),
    "load_tensor": ("polisyos.foundry.execute.executor", "load_tensor"),
    "put_state_snapshot": ("polisyos.foundry.execute.executor", "put_state_snapshot"),
    "put_tensor": ("polisyos.foundry.execute.executor", "put_tensor"),
    "selector_field_values": ("polisyos.foundry.execute.executor", "selector_field_values"),
    "set_state_path": ("polisyos.foundry.execute.executor", "set_state_path"),
    "validate_ops_compatibility": (
        "polisyos.foundry.execute.executor",
        "validate_ops_compatibility",
    ),
}


def __getattr__(name: str) -> Any:
    if name not in _LAZY_IMPORTS:
        raise AttributeError(f"module 'polisyos.foundry.executor' has no attribute {name!r}")
    module_name, attr_name = _LAZY_IMPORTS[name]
    value = getattr(importlib.import_module(module_name), attr_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(list(globals().keys()) + list(_LAZY_IMPORTS.keys()))
