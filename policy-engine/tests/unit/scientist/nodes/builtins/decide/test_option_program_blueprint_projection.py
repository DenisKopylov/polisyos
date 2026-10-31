"""Blueprint evidence preserves human gates and the unproved option/program join."""

from __future__ import annotations

from polisyos.core.artifacts import ArtifactRef
from polisyos.scientist.methods.search.promotion_evidence import load_promotion_evidence_bundle
from polisyos.scientist.nodes.builtins.decide import run_policy_blueprint_runtime as runtime
from polisyos.scientist.nodes.builtins.decide.run_policy_blueprint_runtime import (
    RunPolicyBlueprintRuntimeNode,
)
from tests.unit.remediation.test_fun_03 import _install_actual_runtime_node_dependencies


def test_actual_blueprint_finalizer_persists_the_unproved_join_as_limitation(
    tmp_path, monkeypatch
) -> None:
    harness = _install_actual_runtime_node_dependencies(monkeypatch, tmp_path, mode="no_promotion")
    selection_builder = runtime.build_policy_runtime_evaluation

    def build_selection(*args, **kwargs):
        artifact = selection_builder(*args, **kwargs)
        artifact.completed_projection_binding = None
        return artifact

    backend_type = runtime.ProductionPolicyEvaluationBackend

    class BackendWithExplicitMissingBinding(backend_type):
        def evaluate(self, *args, **kwargs):
            artifact = super().evaluate(*args, **kwargs)
            artifact.completed_projection_binding = None
            return artifact

    monkeypatch.setattr(runtime, "build_policy_runtime_evaluation", build_selection)
    monkeypatch.setattr(
        runtime, "ProductionPolicyEvaluationBackend", BackendWithExplicitMissingBinding
    )
    finalize = runtime.finalize_runtime_session
    final_actions = []

    def capture_final_action(session):
        final_actions.append(session.outcome.final_action)
        return finalize(session)

    monkeypatch.setattr(runtime, "finalize_runtime_session", capture_final_action)
    harness["state"].params["option_program_correspondence"] = {"status": "verified"}
    outcome = RunPolicyBlueprintRuntimeNode().execute(harness["ctx"], harness["state"])
    assert outcome.status == "ok"
    assert len(final_actions) == 1
    assert outcome.state.params["_funnel_outcome"]["final_action"] == final_actions[0]
    expected = {
        "status": "not_established",
        "reason_code": "option_program_correspondence_not_established",
    }
    assert outcome.state.params["option_program_correspondence"] == expected
    evidence_ref = ArtifactRef.model_validate(outcome.state.params["promotion_evidence_bundle_ref"])
    reopened = load_promotion_evidence_bundle(harness["store"], evidence_ref)
    assert reopened.metadata["option_program_correspondence"] == expected
