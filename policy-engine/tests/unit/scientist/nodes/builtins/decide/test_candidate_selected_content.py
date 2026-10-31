"""Candidate selection preserves actual typed content and selected source bytes."""

from __future__ import annotations

import logging

import pytest

from polisyos.core.artifacts import ArtifactRef, FileSystemCAS, ensure_ir_artifact_store
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.ir.trinity import TrinityBundle, persist_trinity_bundle_artifact
from polisyos.scientist.nodes.builtins.decide.select_policy_candidate import (
    SelectPolicyCandidateNode,
    _selected_candidate,
)
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.executor import WorkflowExecutor
from polisyos.scientist.orchestration.engine.registry import NodeRegistry
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.engine.workflow_spec import NodeInvocation, WorkflowSpec
from polisyos.scientist.policy_design.schema import (
    PolicyCandidateSchema,
    persist_policy_candidate_schema,
)
from tests.unit.scientist.search.test_phase_b_policy_runtime import _candidate


def _trinity_ref(store, bundle):
    return ArtifactRef.model_validate(
        persist_trinity_bundle_artifact(ensure_ir_artifact_store(store), bundle).model_dump(
            mode="json"
        )
    )


@pytest.mark.parametrize("field", ["parameter", "constraint"])
def test_candidate_and_trinity_numeric_boolean_do_not_alias(tmp_path, field: str) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    payload = _candidate().model_dump(mode="json")
    if field == "parameter":
        values = payload["trinity_bundle"]["policy_spec"]["interventions"][0]["params"]
        key = "rate"
    else:
        values = {"constraint_id": "synthetic_limit", "constraint_type": "hard"}
        payload["trinity_bundle"]["problem_frame"]["hard_constraints"] = [values]
        key = "value"
    values[key] = True
    candidate = PolicyCandidateSchema.model_validate(payload)
    selected = persist_policy_candidate_schema(store, candidate, return_selected_profile=True)
    values[key] = 1
    trinity = _trinity_ref(store, TrinityBundle.model_validate(payload["trinity_bundle"]))
    with pytest.raises(ValueError, match="policy_candidate_trinity_mismatch"):
        _selected_candidate(store, None, selected, trinity)


def test_inline_candidate_and_selected_source_boolean_numeric_do_not_alias(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    payload = _candidate().model_dump(mode="json")
    payload["metadata"]["synthetic_flag"] = 1
    selected = persist_policy_candidate_schema(
        store, PolicyCandidateSchema.model_validate(payload), return_selected_profile=True
    )
    payload["metadata"]["synthetic_flag"] = True
    with pytest.raises(ValueError, match="policy_candidate_selection_conflict"):
        _selected_candidate(store, payload, selected, None)


def test_actual_engine_reissues_exact_candidate_bytes_with_numeric_constraint(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    payload = _candidate().model_dump(mode="json")
    payload["trinity_bundle"]["problem_frame"]["hard_constraints"] = [
        {"constraint_id": "synthetic_limit", "constraint_type": "hard", "value": 10}
    ]
    candidate = PolicyCandidateSchema.model_validate(payload)
    selected = persist_policy_candidate_schema(store, candidate, return_selected_profile=True)
    bundle = TrinityBundle.model_validate(payload["trinity_bundle"])
    trinity = _trinity_ref(store, bundle)
    registry_ref = build_default_registry_bundle(store, return_selected_profile=True).bundle_ref
    state = ExperimentState(
        run_id="synthetic-exact-candidate",
        params={"policy_candidate_ref": selected.model_dump(mode="json")},
        inputs={"trinity_bundle_ref": trinity},
    )
    run = RunContext.start(store=store, registry_bundle=registry_ref, run_id=state.run_id)
    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger(__name__))
    node = SelectPolicyCandidateNode()
    registry = NodeRegistry()
    registry.register(node)
    workflow = WorkflowSpec(
        workflow_id="synthetic_exact_candidate",
        nodes=[NodeInvocation(alias="selected", node_id=node.spec.metadata.component_id)],
    )
    result = WorkflowExecutor(ctx, registry).execute(workflow, state)
    assert result.report.nodes[0].status == "ok"
    output = result.state.artifacts_index["verified_policy_candidate_ref"]
    assert output.manifest_profile_sha256 != selected.manifest_profile_sha256
    assert store.get_bytes(output) == store.get_bytes(selected)
