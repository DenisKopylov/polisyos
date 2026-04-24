"""Public facade -- re-exports from decomposed sub-modules."""

from __future__ import annotations

# Program-graph orchestrator
from ._executor_graph import (
    execute_program_graph,
)

# Models & low-level helpers
from ._executor_models import (
    ApplyArtifacts,
    ExecuteArtifacts,
    artifact_id,
    get_state_path,
    load_model,
    load_payload,
    load_tensor,
    put_tensor,
    set_state_path,
)

# Selector evaluation, constraint checking, patch-op application
from ._executor_ops import (
    apply_op,
    apply_operator,
    apply_ops_for_slot,
    apply_ops_to_state,
    check_constraints,
    coerce_number,
    coerce_selector_scalar,
    evaluate_selector,
    selector_field_values,
    validate_ops_compatibility,
)

# State-delta application & patching
from ._executor_patching import (
    apply_patch_map,
    apply_patch_records,
    apply_state_delta,
    apply_state_delta_and_snapshot,
)

# State snapshot persistence
from ._executor_snapshots import (
    export_seed_state_npz,
    import_seed_state_npz,
    load_state_snapshot,
    put_state_snapshot,
)

__all__ = [
    # dataclasses
    "ExecuteArtifacts",
    "ApplyArtifacts",
    # graph orchestrator
    "execute_program_graph",
    # patching / delta
    "apply_state_delta",
    "apply_patch_records",
    "apply_patch_map",
    "apply_state_delta_and_snapshot",
    # snapshots
    "export_seed_state_npz",
    "import_seed_state_npz",
    "load_state_snapshot",
    "put_state_snapshot",
    # ops
    "apply_op",
    "apply_operator",
    "apply_ops_for_slot",
    "apply_ops_to_state",
    "check_constraints",
    "coerce_number",
    "coerce_selector_scalar",
    "evaluate_selector",
    "selector_field_values",
    "validate_ops_compatibility",
    # low-level helpers
    "artifact_id",
    "get_state_path",
    "load_model",
    "load_payload",
    "load_tensor",
    "put_tensor",
    "set_state_path",
]
