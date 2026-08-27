from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from polisyos.ir.governance.policy_spec import (
    InterventionSpec,
    ParameterSpec,
    PolicySearchLevel,
    PolicySpec,
    TemporalInterventionSequence,
)
from polisyos.ir.governance.problem_frame import ObjectiveSpec, ProblemDomain, ProblemFrame
from polisyos.ir.governance.schedule import ScheduleSpec
from polisyos.ir.governance.selector_expr import SelectorPredicate
from polisyos.ir.kernel.values import MoneyValue
from polisyos.ir.model_layer.model_spec import AssumptionSpec, AssumptionType, ModelSpec
from polisyos.ir.model_layer.types import OptimizationDirection, SelectorOperator
from polisyos.ir.observation.contracts import StrategicResponseChannel
from polisyos.ir.trinity import TrinityBundle
from polisyos.lex import (
    InterventionKnobSpec,
    LexInterventionCompiler,
    LexPolicyBundleInput,
    LexProvisionDirective,
)
from polisyos.scientist.nodes.builtins.planning.run_hierarchical_policy_search import (
    HierarchicalPolicySearchAdapter,
    RunHierarchicalPolicySearchNode,
)
from polisyos.scientist.orchestration.engine.state_branching import (
    branch_state as real_branch_state,
)
from polisyos.scientist.policy_design.search import (
    PolicySearchLevel as ScientistPolicySearchLevel,
)


def test_hierarchical_policy_search_adapter_is_scientist_owned() -> None:
    assert HierarchicalPolicySearchAdapter.__module__ == (
        "polisyos.scientist.nodes.builtins.planning.run_hierarchical_policy_search"
    )


def _selector() -> SelectorPredicate:
    return SelectorPredicate(
        field="region_code",
        operator=SelectorOperator.EQUALS,
        value="UA-30",
    )


def _bundle() -> TrinityBundle:
    return TrinityBundle(
        problem_frame=ProblemFrame(
            problem_id="ua_policy_problem",
            domain=ProblemDomain.FISCAL,
            objectives=[
                ObjectiveSpec(
                    objective_id="employment_goal",
                    metric_id="employment_rate",
                    direction=OptimizationDirection.MAXIMIZE,
                )
            ],
        ),
        policy_spec=PolicySpec(
            policy_id="ua_policy",
            interventions=[
                InterventionSpec(
                    intervention_id="wage_support",
                    kind="wage_subsidy",
                    target=_selector(),
                    schedule=ScheduleSpec(start_step=0, duration_steps=3),
                    params={"amount": MoneyValue(amount=Decimal("1000"), currency="UAH")},
                )
            ],
            parameters=[
                ParameterSpec(
                    param_id="wage_support_amount",
                    intervention_id="wage_support",
                    param_path="amount",
                    default_value=MoneyValue(amount=Decimal("1000"), currency="UAH"),
                    min_value=MoneyValue(amount=Decimal("500"), currency="UAH"),
                    max_value=MoneyValue(amount=Decimal("2000"), currency="UAH"),
                )
            ],
        ),
        model_spec=ModelSpec(
            model_id="ua_model",
            data_snapshot_ref="sha256:" + "2" * 64,
            assumptions=[
                AssumptionSpec(
                    assumption_id="stable_labor_demand",
                    assumption_type=AssumptionType.PARAMETRIC,
                    description="Labor-demand response remains stable within the rollout horizon.",
                )
            ],
        ),
    )


def test_hierarchical_search_handoff_preserves_shared_enum_and_none_compatibility() -> None:
    bundle_input = LexPolicyBundleInput.model_validate(
        {
            "trinity_bundle": _bundle().model_dump(mode="python"),
            "compiled_interventions": None,
        }
    )
    plan = HierarchicalPolicySearchAdapter().build_request(bundle_input)

    assert bundle_input.compiled_interventions == []
    assert ScientistPolicySearchLevel is PolicySearchLevel
    assert plan.level_order == [
        PolicySearchLevel.STRUCTURE,
        PolicySearchLevel.PARAMETER,
        PolicySearchLevel.NARRATIVE,
    ]
    assert [level.value for level in plan.level_order] == [
        "structure",
        "parameter",
        "narrative",
    ]


def test_hierarchical_policy_search_adapter_validates_against_policy_design_api() -> None:
    adapter = HierarchicalPolicySearchAdapter()
    compiled = LexInterventionCompiler().compile(
        LexProvisionDirective(
            provision_ref="ua.public_wage.art7",
            intervention_id="wage_support",
            intervention_kind="wage_subsidy",
            target=_selector(),
            schedule=ScheduleSpec(start_step=0, duration_steps=3),
            params={"amount": MoneyValue(amount=Decimal("1000"), currency="UAH")},
            knobs=[
                InterventionKnobSpec(
                    param_id="wage_support_amount",
                    param_path="params.amount",
                    default_value=MoneyValue(amount=Decimal("1000"), currency="UAH"),
                )
            ],
            strategic_response_expected=True,
            transmission_channels=[StrategicResponseChannel.LABOR_CHANNEL],
        )
    )
    sequence = TemporalInterventionSequence(
        sequence_id="ua_wage_support_sequence",
        dynamic_intervention_id="dynamic_wage_support",
        steps=[
            {
                "step_id": "step_1",
                "effective_date": "2022-01",
                "intervention_id": "wage_support",
            }
        ],
    )
    bundle_input = LexPolicyBundleInput(
        trinity_bundle=_bundle(),
        compiled_interventions=[compiled],
        temporal_sequences=[sequence],
        metadata={"source_bundle": "ukraine_wave1"},
    )
    candidate = adapter.build_candidate(bundle_input, policy_family="ua_wave1_policy")
    plan = adapter.build_request(
        bundle_input,
        search_config={
            "max_structure_candidates": 3,
            "max_parameter_iterations": 4,
            "narrative_top_k": 2,
        },
        policy_family="ua_wave1_policy",
        metadata={"country": "ua"},
    )
    coordinator = adapter.validate_policy_design_api(
        bundle_input,
        search_config={
            "max_structure_candidates": 3,
            "max_parameter_iterations": 4,
            "narrative_top_k": 2,
        },
        policy_family="ua_wave1_policy",
    )

    assert plan.level_order == ["structure", "parameter", "narrative"]
    assert coordinator._config.max_parameter_iterations == 4
    assert candidate.metadata["jurisdiction"] == "UA"
    assert candidate.metadata["country"] == "ua"
    assert candidate.metadata["domain"] == "fiscal"
    assert candidate.metadata["dynamic_intervention_ids"] == ["dynamic_wage_support"]
    assert candidate.metadata["strategic_intervention_kinds"] == ["wage_subsidy"]


def test_hierarchical_policy_search_adapter_supports_candidate_without_tunable_parameters() -> None:
    adapter = HierarchicalPolicySearchAdapter()
    bundle = _bundle().model_copy(
        update={"policy_spec": _bundle().policy_spec.model_copy(update={"parameters": []})}
    )
    coordinator = adapter.validate_policy_design_api(bundle)
    result = adapter.run_search(
        bundle,
        loop_id="loop_no_params",
        stage_b_evaluator=lambda candidate_payload, context: {
            "feasible": True,
            "objective_value": 0.0,
            "simulation_results": {"gdp_change": 0.1},
        },
    )

    assert coordinator is not None
    assert result.state.parameter_search_results
    assert all(
        search_result.telemetry["parameterless_candidate"] is True
        for search_result in result.state.parameter_search_results.values()
    )


def test_run_hierarchical_policy_search_adapter_assertion_is_not_swallowed(
    execution_context,
    minimal_state,
) -> None:
    candidate = MagicMock()

    with (
        patch(
            "polisyos.scientist.nodes.builtins.planning.run_hierarchical_policy_search._resolve_search_candidate",
            return_value=candidate,
        ),
        patch(
            "polisyos.scientist.nodes.builtins.planning.run_hierarchical_policy_search.HierarchicalPolicySearchAdapter.run_search",
            side_effect=AssertionError("search invariant"),
        ),
    ):
        with pytest.raises(AssertionError, match="search invariant"):
            RunHierarchicalPolicySearchNode().execute(execution_context, minimal_state)


def test_run_hierarchical_policy_search_uses_branch_state_for_final_outputs(
    execution_context,
    minimal_state,
    artifact_ref_factory,
) -> None:
    candidate = MagicMock()
    candidate.candidate_id = "champion"
    candidate.candidate_hash.return_value = "hash:champion"
    candidate.trinity_bundle = {"bundle": "payload"}
    search_result = SimpleNamespace(model_dump=lambda mode="json": {"status": "ok"})
    calls: list[tuple[str, ...]] = []

    def _recording_branch_state(base_state, *, write_paths=()):
        calls.append(tuple(write_paths))
        return real_branch_state(base_state, write_paths=write_paths)

    with (
        patch(
            "polisyos.scientist.nodes.builtins.planning.run_hierarchical_policy_search._resolve_search_candidate",
            return_value=candidate,
        ),
        patch(
            "polisyos.scientist.nodes.builtins.planning.run_hierarchical_policy_search.HierarchicalPolicySearchAdapter.run_search",
            return_value=search_result,
        ),
        patch(
            "polisyos.scientist.nodes.builtins.planning.run_hierarchical_policy_search._select_champion_candidate",
            return_value=candidate,
        ),
        patch(
            "polisyos.scientist.nodes.builtins.planning.run_hierarchical_policy_search._persist_trinity_bundle",
            return_value=artifact_ref_factory(kind="ir.trinity_bundle"),
        ),
        patch(
            "polisyos.scientist.nodes.builtins.planning.run_hierarchical_policy_search._persist_frontier_report",
            return_value=artifact_ref_factory(kind="ir.policy_frontier_report"),
        ),
        patch(
            "polisyos.scientist.nodes.builtins.planning.run_hierarchical_policy_search.branch_state",
            side_effect=_recording_branch_state,
        ),
    ):
        outcome = RunHierarchicalPolicySearchNode().execute(execution_context, minimal_state)

    assert outcome.status == "ok"
    assert any("params.policy_candidate_schema" in write_paths for write_paths in calls)


def test_run_hierarchical_policy_search_rejects_runtime_legacy_inferred_bounds_config(
    execution_context,
    minimal_state,
) -> None:
    candidate = MagicMock()
    state = minimal_state.model_copy(deep=True)
    state.params["hierarchical_policy_search_config"] = {
        "require_explicit_parameter_bounds": False,
        "allow_legacy_shadow_inferred_bounds": True,
    }

    with (
        patch(
            "polisyos.scientist.nodes.builtins.planning.run_hierarchical_policy_search._resolve_search_candidate",
            return_value=candidate,
        ),
        patch(
            "polisyos.scientist.nodes.builtins.planning.run_hierarchical_policy_search.HierarchicalPolicySearchAdapter.run_search",
            side_effect=AssertionError("legacy _derive_bounds path reached"),
        ),
    ):
        outcome = RunHierarchicalPolicySearchNode().execute(execution_context, state)

    assert outcome.status == "fail"
    assert outcome.error is not None
    assert "legacy inferred bounds" in outcome.error.message
