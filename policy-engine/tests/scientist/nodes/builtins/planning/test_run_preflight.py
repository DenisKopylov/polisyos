from __future__ import annotations

from unittest.mock import patch

import pytest

from polisyos.scientist.engine.state_branching import branch_state as real_branch_state
from polisyos.scientist.nodes.builtins.planning.build_execution_plan import BuildExecutionPlanNode
from polisyos.scientist.nodes.builtins.planning.build_method_catalog_snapshot import (
    BuildMethodCatalogSnapshotNode,
)
from polisyos.scientist.nodes.builtins.planning.run_preflight import RunPreflightNode
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_PREFLIGHT_REPORT_REF,
)


def _prepare_state(execution_context, minimal_state):
    """Run prerequisite nodes to populate plan + catalog refs."""
    plan_outcome = BuildExecutionPlanNode().execute(execution_context, minimal_state)
    assert plan_outcome.status == "ok"
    catalog_outcome = BuildMethodCatalogSnapshotNode().execute(
        execution_context, plan_outcome.state
    )
    assert catalog_outcome.status == "ok"
    return catalog_outcome.state


def test_preflight_success(execution_context, minimal_state):
    state = _prepare_state(execution_context, minimal_state)
    outcome = RunPreflightNode().execute(execution_context, state)
    # Preflight may pass or fail depending on method bindings, but it should not error
    assert outcome.status in ("ok", "fail")
    assert ARTIFACT_PREFLIGHT_REPORT_REF in outcome.state.artifacts_index
    assert outcome.state.params.get("preflight_ready") is not None


def test_preflight_missing_binds(execution_context, minimal_state):
    """Missing execution plan and catalog refs causes fail."""
    outcome = RunPreflightNode().execute(execution_context, minimal_state)
    assert outcome.status == "fail"
    assert outcome.error is not None
    assert outcome.error.code == "node.missing_input"


def test_preflight_partial_only_plan(execution_context, minimal_state):
    """With only the execution plan but no catalog, preflight fails."""
    plan_outcome = BuildExecutionPlanNode().execute(execution_context, minimal_state)
    assert plan_outcome.status == "ok"
    outcome = RunPreflightNode().execute(execution_context, plan_outcome.state)
    assert outcome.status == "fail"
    assert outcome.error.code == "node.missing_input"


def test_preflight_invalid_input_load_returns_typed_fail(
    execution_context, minimal_state, monkeypatch: pytest.MonkeyPatch
):
    state = _prepare_state(execution_context, minimal_state)

    def _boom(*args, **kwargs):
        del args, kwargs
        raise OSError("cas-unavailable")

    monkeypatch.setattr(execution_context.store, "get_bytes", _boom)
    outcome = RunPreflightNode().execute(execution_context, state)

    assert outcome.status == "fail"
    assert outcome.error is not None
    assert outcome.error.code == "node.invalid_state"
    assert "cas-unavailable" in outcome.error.message


def test_preflight_uses_branch_state_for_declared_outputs(
    execution_context,
    minimal_state,
):
    state = _prepare_state(execution_context, minimal_state)
    state.params["nested"] = {"baseline": True}
    observed: dict[str, tuple[str, ...]] = {}

    def _spy_branch(base_state, *, write_paths=()):
        observed["write_paths"] = tuple(write_paths)
        return real_branch_state(base_state, write_paths=write_paths)

    with patch(
        "polisyos.scientist.nodes.builtins.planning.run_preflight.branch_state",
        _spy_branch,
    ):
        outcome = RunPreflightNode().execute(execution_context, state)

    assert outcome.status in ("ok", "fail")
    assert observed["write_paths"] == (
        "params.preflight_ready",
        "params.preflight_diagnostics",
        "params.preflight_report_ref",
        "artifacts_index.preflight_report_ref",
        "preflight_report_ref",
    )
    assert state.params["nested"] == {"baseline": True}
    assert ARTIFACT_PREFLIGHT_REPORT_REF not in state.artifacts_index
    assert ARTIFACT_PREFLIGHT_REPORT_REF in outcome.state.artifacts_index
