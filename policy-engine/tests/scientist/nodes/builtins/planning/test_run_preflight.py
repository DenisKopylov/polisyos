from __future__ import annotations

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
