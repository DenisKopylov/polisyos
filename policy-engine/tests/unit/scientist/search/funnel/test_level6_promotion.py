"""Actual policy-node positive control for the promotion callback boundary.

The shared harness substitutes external evidence and publication boundaries.
It retains the node, workflow adapter, funnel, Level 6 and inner owner recheck;
its effect recorder establishes ordering, never production publication.
"""

from polisyos.scientist.methods.search.funnel.level6_promotion import Level6PromotionStage
from polisyos.scientist.nodes.builtins.decide import run_policy_blueprint_runtime as runtime
from tests.unit.remediation.test_fun_03 import _install_actual_runtime_node_dependencies


def test_generic_effectful_callback_requires_explicit_boolean_owner_permission():
    for owner_return in (
        None,
        False,
        {"allowed": False},
        {"allowed": True},
        "allowed",
        1,
        object(),
    ):
        effects = []

        def runner(candidate, context, effects=effects):
            effects.append(candidate["id"])
            return {"decision": "complete"}

        check = (
            None if owner_return is None else lambda candidate, context, value=owner_return: value
        )
        result = Level6PromotionStage(
            promotion_runner=runner, promotion_owner_recheck=check
        ).evaluate({"id": "fixture-subject"}, {})
        assert effects == [], repr(owner_return)
        assert result.terminal_action == "defer_to_human"
        assert any(
            card.failure_type == "promotion_owner_recheck_failed" for card in result.failure_cards
        )


def test_generic_boolean_allow_is_callback_ordering_without_typed_admission_claim():
    events = []

    def owner(candidate, context):
        events.append("owner")
        return True

    def runner(candidate, context):
        events.append("runner")
        return {"decision": "complete"}

    result = Level6PromotionStage(promotion_runner=runner, promotion_owner_recheck=owner).evaluate(
        {"id": "fixture-subject"}, {}
    )
    assert events == ["owner", "runner"]
    assert result.terminal_action == "complete"


def test_actual_policy_node_normal_path_calls_owner_and_effect_once(tmp_path, monkeypatch):
    harness = _install_actual_runtime_node_dependencies(monkeypatch, tmp_path, mode="normal")
    outcome = runtime.RunPolicyBlueprintRuntimeNode().execute(harness["ctx"], harness["state"])

    assert outcome.status == "ok"
    assert harness["backend_calls"] == ["full"]
    assert harness["runner_calls"] == ["runner"]
    assert harness["owner_checks"] == [True, True]
    assert len(harness["promotion_writes"]) == 1
    assert outcome.state.params["policy_promotion_result"]["decision"] == "complete"
    assert outcome.state.params["_funnel_outcome"]["final_action"] == "complete"


def test_actual_policy_node_rechecks_missing_wrong_and_malformed_candidate_binding(
    tmp_path, monkeypatch
):
    from polisyos.core.artifacts.manifest import ArtifactRef

    for mutation in ("missing", "wrong", "malformed"):
        with monkeypatch.context() as scoped_patch:
            harness = _install_actual_runtime_node_dependencies(
                scoped_patch, tmp_path / mutation, mode="normal"
            )
            original_extract = runtime._extract_level4_policy_evaluation

            def change_binding(
                ctx, *, candidate_ref, context, mutation=mutation, original_extract=original_extract
            ):
                result = original_extract(ctx, candidate_ref=candidate_ref, context=context)
                if mutation == "missing":
                    context.pop("policy_candidate_ref", None)
                elif mutation == "wrong":
                    context["policy_candidate_ref"] = ArtifactRef(
                        artifact_id="sha256:" + "c" * 64,
                        kind="test",
                        media_type="application/json",
                    )
                else:
                    context["policy_candidate_ref"] = "malformed-ref"
                return result

            scoped_patch.setattr(runtime, "_extract_level4_policy_evaluation", change_binding)
            outcome = runtime.RunPolicyBlueprintRuntimeNode().execute(
                harness["ctx"], harness["state"]
            )
            assert harness["runner_calls"] == ["runner"]
            assert harness["promotion_writes"] == [], mutation
            assert outcome.state.params["policy_promotion_result"]["reason"] == (
                "promotion_owner_recheck_failed"
            )
            assert outcome.state.params["_funnel_outcome"]["final_action"] == "defer_to_human"
