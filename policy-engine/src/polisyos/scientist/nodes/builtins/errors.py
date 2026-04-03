"""Public builtins errors module API."""
from __future__ import annotations

# Canonical node error codes (E1.7)
ERROR_MISSING_INPUT = "node.missing_input"
ERROR_FOUNDATION_MISSING = "node.missing_port"
ERROR_INVALID_STATE = "node.invalid_state"
ERROR_TRINITY_LINK_FAILED = "trinity.link_failed"
ERROR_FOUNDRY_COMPILE_FAILED = "foundry.compile_failed"
ERROR_FOUNDRY_EXECUTE_FAILED = "foundry.execute_failed"
ERROR_DATA_PLANE_BIND_FAILED = "foundry.input_bindings_failed"
ERROR_DATA_PLANE_GATE_BLOCKED = "governance.data_plane_blocked"
ERROR_COUNTERFACTUAL_GATE_BLOCKED = "causal.counterfactual_gate_blocked"

# Phase 11 — Node hardening codes
ERROR_VALIDATION = "node.validation_error"
ERROR_STATE_GUARD_VIOLATION = "node.state_guard_violation"
ERROR_OPTIONAL_DEP_MISSING = "node.optional_dep_missing"
