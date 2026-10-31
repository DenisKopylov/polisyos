"""Actual Stage B child preparation and refused evaluation paths."""

import pytest

from polisyos.core.artifacts.store import PutOptions
from polisyos.core.run.child_custody import ChildComputationOutcomeUnknown
from polisyos.ir.governance.policy_spec import PolicySpec
from polisyos.ir.governance.problem_frame import ProblemDomain, ProblemFrame
from polisyos.ir.model_layer.model_spec import ModelSpec
from polisyos.ir.trinity import TrinityBundle
from polisyos.ir.trinity.loaders import load_trinity_bundle_artifact
from polisyos.scientist.nodes.builtins.planning.child_stage_b import (
    StageBFinalizeNode,
    StageBPrepareNode,
    stage_b_child_template,
)
from polisyos.scientist.nodes.builtins.planning.stage_b_projection import load_stage_b_projection
from polisyos.scientist.nodes.builtins.state_keys import ARTIFACT_EXEC_PLAN_REF
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.policy_design.schema import PolicyCandidateSchema, TargetPopulationSpec


def test_real_candidate_is_prepared_in_child_without_mutating_parent(execution_context) -> None:
    """The existing Trinity producer and consumer bind the new child candidate."""
    ctx = execution_context
    data = ctx.store.put_json(
        {"population": 1},
        PutOptions(kind="test.data", media_type="application/json"),
        return_selected_profile=True,
    )
    candidate = PolicyCandidateSchema(
        candidate_id="candidate_one",
        trinity_bundle=TrinityBundle(
            problem_frame=ProblemFrame(problem_id="problem_one", domain=ProblemDomain.SOCIAL),
            policy_spec=PolicySpec(policy_id="policy_one", interventions=[]),
            model_spec=ModelSpec(model_id="model_one", data_snapshot_ref=str(data.artifact_id)),
        ),
        target_population=TargetPopulationSpec(population_id="all", description="All"),
    )
    stale = ctx.store.put_json(
        {"stale": True},
        PutOptions(kind="test.stale", media_type="application/json"),
        return_selected_profile=True,
    )
    parent = ExperimentState(
        run_id="R_test",
        inputs={"data_snapshot_ref": data},
        params={"child_stage_b_candidate": candidate.model_dump(mode="json")},
        artifacts_index={ARTIFACT_EXEC_PLAN_REF: stale, "unrelated_ref": stale},
    )
    before = parent.model_dump(mode="json")
    outcome = StageBPrepareNode().execute(ctx, parent)
    assert outcome.status == "ok"
    assert isinstance(outcome.state.params["policy_candidate_schema"], dict)
    assert outcome.state.params["policy_candidate_schema"] == candidate.model_dump(mode="python")
    assert parent.model_dump(mode="json") == before
    assert ARTIFACT_EXEC_PLAN_REF not in outcome.state.artifacts_index
    assert outcome.state.artifacts_index["unrelated_ref"] == stale
    trinity_ref = outcome.state.inputs["trinity_bundle_ref"]
    assert trinity_ref.manifest_profile_sha256 is not None
    assert load_trinity_bundle_artifact(ctx.store, trinity_ref) == candidate.trinity_bundle
    selected_candidate = outcome.state.artifacts_index["child_stage_b_selected_candidate_ref"]
    candidate_edges = ctx.store.get_manifest(selected_candidate).inputs
    assert [(edge.role, str(edge.artifact_id)) for edge in candidate_edges] == [
        ("model_primary_data_snapshot", str(data.artifact_id)),
        ("world_model_data_snapshot", str(data.artifact_id)),
    ]
    trinity_edges = ctx.store.get_manifest(trinity_ref).inputs
    assert any(
        edge.role == "policy_candidate"
        and edge.artifact_id == selected_candidate.artifact_id
        and edge.manifest_profile_sha256 == selected_candidate.manifest_profile_sha256
        for edge in trinity_edges
    )


def test_real_evaluation_safety_refusal_is_persisted_as_a_candidate_observation(
    execution_context,
) -> None:
    """A missing safety context stays a refusal through producer and fresh consumer."""
    candidate = PolicyCandidateSchema(
        candidate_id="candidate_one",
        trinity_bundle=TrinityBundle(
            problem_frame=ProblemFrame(problem_id="problem_one", domain=ProblemDomain.SOCIAL),
            policy_spec=PolicySpec(policy_id="policy_one", interventions=[]),
            model_spec=ModelSpec(model_id="model_one", data_snapshot_ref="sha256:" + "0" * 64),
        ),
        target_population=TargetPopulationSpec(population_id="all", description="All"),
    )
    state = ExperimentState(
        run_id="R_test", params={"policy_candidate_schema": candidate.model_dump(mode="json")}
    )
    outcome = StageBFinalizeNode().execute(execution_context, state)
    assert outcome.status == "ok"
    projection = load_stage_b_projection(
        execution_context.store, outcome.state.artifacts_index["child_stage_b_projection_ref"]
    )
    result = projection.original_result()
    assert result["status"] == "rejected"
    assert result["blocked_reason"] == "eval_safety_blocked"
    assert (
        "polisyos.eval_safety.execution_context_missing@1.0.0" in result["details"]["blocker_codes"]
    )
    assert projection.candidate_ref is None and projection.evaluation_ref is None


def test_stage_b_template_uses_registered_counterfactual_node_and_serial_dependencies() -> None:
    config, members = stage_b_child_template()
    ids = [str(inv.node_id) for inv in config.workflow.nodes]
    assert ids == [str(node.spec.metadata.component_id) for node in members]
    assert "scientist.node_counterfactual_identification_gate@1.0.0" in ids
    assert [inv.depends_on for inv in config.workflow.nodes] == [
        [],
        ["prepare"],
        ["compile"],
        ["cross_graph"],
        ["resolve_parameters"],
        ["readiness"],
        ["counterfactual"],
        ["simulate"],
    ]


def test_unknown_candidate_write_is_not_downgraded_to_a_missing_source(
    execution_context, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An indeterminate stage write must reach the parent's settlement owner."""
    from polisyos.scientist.nodes.builtins.planning import stage_b_projection

    candidate = PolicyCandidateSchema(
        candidate_id="candidate_one",
        trinity_bundle=TrinityBundle(
            problem_frame=ProblemFrame(problem_id="problem_one", domain=ProblemDomain.SOCIAL),
            policy_spec=PolicySpec(policy_id="policy_one", interventions=[]),
            model_spec=ModelSpec(model_id="model_one", data_snapshot_ref="sha256:" + "0" * 64),
        ),
        target_population=TargetPopulationSpec(population_id="all", description="All"),
    )
    state = ExperimentState(
        run_id="R_test", params={"child_stage_b_candidate": candidate.model_dump(mode="json")}
    )
    unknown = ChildComputationOutcomeUnknown("write acknowledgment unavailable")

    def uncertain_write(*args, **kwargs):
        raise unknown

    monkeypatch.setattr(stage_b_projection, "persist_stage_b_candidate", uncertain_write)
    with pytest.raises(ChildComputationOutcomeUnknown) as caught:
        StageBPrepareNode().execute(execution_context, state)
    assert caught.value is unknown
