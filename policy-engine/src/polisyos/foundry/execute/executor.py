"""Public helper facade for Foundry execution internals.

`polisyos.foundry.execute` is the canonical public execution entrypoint.
This module keeps a narrower helper surface for tests, state fixtures, and
runtime glue without exposing the `_internal` package layout as API.
"""

from __future__ import annotations

# Program-graph orchestrator
from ._internal.graph import (
    execute_program_graph,
)

# Models & low-level helpers
from ._internal.models import (
    ApplyArtifacts,
    ExecuteArtifacts,
    ExecutionStrictness,
    FailureCard,
    FailureKind,
    FailureSeverity,
    artifact_id,
    get_state_path,
    load_model,
    load_payload,
    load_tensor,
    put_tensor,
    set_state_path,
)

# Selector evaluation, constraint checking, patch-op application
from ._internal.ops import (
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
from ._internal.patching import (
    apply_patch_map,
    apply_patch_records,
    apply_state_delta,
    apply_state_delta_and_snapshot,
)

# State snapshot persistence
from ._internal.snapshots import (
    export_seed_state_npz,
    import_seed_state_npz,
    load_state_snapshot,
    put_state_snapshot,
)

__all__ = [
    # dataclasses
    "ExecuteArtifacts",
    "ApplyArtifacts",
    "ExecutionStrictness",
    "FailureCard",
    "FailureKind",
    "FailureSeverity",
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
