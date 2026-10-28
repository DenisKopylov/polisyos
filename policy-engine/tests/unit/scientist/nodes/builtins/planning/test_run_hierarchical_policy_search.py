from __future__ import annotations

import logging
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from polisyos.core.artifacts import CanonInfo, FileSystemCAS, PutOptions, SchemaInfo
from polisyos.core.artifacts.manifest import ArtifactTenantContextInfo
from polisyos.core.canon import CanonSpec, to_canonical_bytes
from polisyos.core.run.context import RunContext
from polisyos.core.security.tenant_context import tenant_scope
from polisyos.ir.governance.policy_spec import (
    InterventionSpec,
    ParameterSpec,
    PolicySearchLevel,
    PolicySpec,
    TemporalInterventionSequence,
)
from polisyos.ir.governance.problem_frame import (
    ObjectiveSpec,
    ProblemDomain,
    ProblemFrame,
)
from polisyos.ir.governance.schedule import ScheduleSpec
from polisyos.ir.governance.selector_expr import SelectorPredicate
from polisyos.ir.kernel.values import MoneyValue
from polisyos.ir.model_layer.model_spec import AssumptionSpec, AssumptionType, ModelSpec
from polisyos.ir.model_layer.types import OptimizationDirection, SelectorOperator
from polisyos.ir.observation.contracts import StrategicResponseChannel
from polisyos.ir.trinity import TrinityBundle
from polisyos.ir.trinity.loaders import TrinityLoadError, load_trinity_bundle_artifact
from polisyos.lex import (
    InterventionKnobSpec,
    LexInterventionCompiler,
    LexPolicyBundleInput,
    LexProvisionDirective,
)
from polisyos.scientist.agent.vector_memory import VectorMemoryStore
from polisyos.scientist.methods.autotune.models import BayesianSourceProfile
from polisyos.scientist.methods.search.contracts import (
    ParetoBasisScope,
    ParetoViewAssessment,
    ParetoViewProjection,
)
from polisyos.scientist.methods.search.objective import (
    ObjectiveScoreStatus,
    _assess_default_search_objective,
)
from polisyos.scientist.methods.search.strategies.transfer import (
    RunFingerprint,
    TransferLearningManager,
)
from polisyos.scientist.methods.search.strategies.types import Evaluation
from polisyos.scientist.methods.search.transfer_context import (
    TransferScopeRefusedError,
    resolve_transfer_context,
)
from polisyos.scientist.nodes.builtins.planning.run_hierarchical_policy_search import (
    ARTIFACT_POLICY_FRONTIER_REPORT_REF,
    HierarchicalPolicySearchAdapter,
    RunHierarchicalPolicySearchNode,
    _evaluate_candidate_payload,
    _iter_candidate_records,
    _persist_frontier_report,
    _persist_trinity_bundle,
    _resolve_search_candidate,
    _select_champion_candidate,
)
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.protocol import NodeOutcome
from polisyos.scientist.orchestration.engine.retry import _node_facing_context
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.engine.state_branching import (
    branch_state as real_branch_state,
)
from polisyos.scientist.policy_design.objectives import (
    ObjectiveStack,
    PolicyEvaluationBundle,
)
from polisyos.scientist.policy_design.output import (
    PolicyFrontierReport,
    load_policy_frontier_report,
)
from polisyos.scientist.policy_design.schema import PolicyCandidateSchema
from polisyos.scientist.policy_design.search import (
    HierarchicalSearchConfig,
    HierarchicalSearchCoordinator,
    StructureCandidate,
)
from polisyos.scientist.policy_design.search import (
    PolicySearchLevel as ScientistPolicySearchLevel,
)


def test_hierarchical_policy_search_adapter_is_scientist_owned() -> None:
    assert HierarchicalPolicySearchAdapter.__module__ == (
        "polisyos.scientist.nodes.builtins.planning.run_hierarchical_policy_search"
    )


def test_search_candidate_route_refuses_same_trinity_bytes_with_wrong_schema(
    execution_context,
) -> None:
    store = execution_context.store
    bundle = _bundle()
    spec = CanonSpec(forbid_floats=False, exclude_none=False)
    trinity_ref = store.put_bytes(
        to_canonical_bytes(bundle, spec),
        PutOptions(
            kind=TrinityBundle.ARTIFACT_KIND,
            media_type=TrinityBundle.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(name="polisyos.test.TrinityBundle", version="9.9"),
            canon=CanonInfo.from_spec(spec),
        ),
        return_selected_profile=True,
    )
    state = ExperimentState(
        run_id="R_search_wrong_trinity_owner",
        inputs={"trinity_bundle_ref": trinity_ref},
    )

    with pytest.raises(TrinityLoadError, match="manifest does not match"):
        _resolve_search_candidate(execution_context, state)


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
    assert all(
        search_result.best_candidate is None
        for search_result in result.state.parameter_search_results.values()
    )
    assert all(
        iteration.score_status is ObjectiveScoreStatus.NOT_ESTABLISHED
        and iteration.objective_value is None
        for search_result in result.state.parameter_search_results.values()
        for iteration in search_result.history
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
    candidate = PolicyCandidateSchema.from_trinity_bundle(_bundle(), candidate_id="champion")
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


def test_no_registry_hierarchy_persists_candidates_without_global_frontier_claim(
    execution_context,
    minimal_state,
    artifact_ref_factory,
) -> None:
    candidate = PolicyCandidateSchema.from_trinity_bundle(
        _bundle(), candidate_id="candidate_without_registry"
    )
    candidate_hash = candidate.candidate_hash()
    rejected_candidate = candidate.model_copy(
        update={"candidate_id": "candidate_rejected_without_registry"}
    )
    rejected_candidate_hash = rejected_candidate.candidate_hash()
    search_result = SimpleNamespace(
        state=SimpleNamespace(
            structure_candidates=[
                SimpleNamespace(
                    structure_id="structure_without_registry",
                    candidate=candidate,
                    accepted=True,
                    candidate_hash=candidate_hash,
                    metadata={},
                ),
                SimpleNamespace(
                    structure_id="rejected_structure_without_registry",
                    candidate=rejected_candidate,
                    accepted=False,
                    candidate_hash=rejected_candidate_hash,
                    metadata={},
                ),
            ],
            parameter_search_results={},
        ),
        model_dump=lambda mode="json": {"status": "candidate_only"},
    )

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
            "polisyos.scientist.nodes.builtins.planning.run_hierarchical_policy_search._persist_trinity_bundle",
            return_value=artifact_ref_factory(kind="ir.trinity_bundle"),
        ),
    ):
        outcome = RunHierarchicalPolicySearchNode().execute(execution_context, minimal_state)

    assert outcome.status == "ok"
    assert outcome.state.params["policy_search_result"]["champion_status"] == "not_established"
    report_ref = outcome.state.artifacts_index[ARTIFACT_POLICY_FRONTIER_REPORT_REF]
    fresh_store = FileSystemCAS(execution_context.store.root)
    assert fresh_store is not execution_context.store
    report = load_policy_frontier_report(fresh_store, report_ref)
    assert report.global_frontier == []
    assert [item.candidate_hash for item in report.candidate_frontier] == [candidate_hash]
    assert rejected_candidate_hash not in {
        item.candidate_hash for item in report.candidate_frontier
    }
    assert rejected_candidate_hash not in report.eligibility_unknown_candidate_hashes
    projection = report.view_projections["global_feasible"]
    assert projection.assessment.status == "denominator_limited"
    assert projection.assessment.basis_scope.scope == "not_established"
    assert projection.eligible_candidate_hashes == ()
    assert projection.assessment.input_count == 0
    assert projection.candidate_frontier_hashes == ()
    assert projection.unassessed_candidate_hashes == ()
    assert report.eligibility_unknown_candidate_hashes == (candidate_hash,)

    payload = report.model_dump(mode="json")
    payload["eligibility_unknown_candidate_hashes"] = []
    with pytest.raises(ValueError, match="Pareto denominator reconciliation status"):
        PolicyFrontierReport.model_validate(payload)


def test_hierarchical_report_limits_complete_rank_when_candidate_eligibility_is_unknown(
    execution_context,
    minimal_state,
) -> None:
    known = PolicyCandidateSchema.from_trinity_bundle(_bundle(), candidate_id="evaluated_candidate")
    unknown = PolicyCandidateSchema.from_trinity_bundle(
        _bundle(), candidate_id="unevaluated_candidate"
    )
    known_hash = known.candidate_hash()
    unknown_hash = unknown.candidate_hash()
    complete = ParetoViewProjection(
        view="global_feasible",
        assessment=ParetoViewAssessment(
            status="complete",
            coverage_status="complete",
            basis_scope=ParetoBasisScope(
                scope="declared",
                coordinate_ids=["policy_value"],
                basis_ref="test:hierarchical-objective-basis",
            ),
            input_count=1,
            assessed_count=1,
        ),
        eligible_candidate_hashes=(known_hash,),
        candidate_frontier_hashes=(known_hash,),
        ranked_frontier_hashes=(known_hash,),
    )
    known_record = SimpleNamespace(
        structure_id="known",
        candidate=known,
        evaluation=SimpleNamespace(feasible=True, primary={}, constraint_statuses={}),
        metadata={},
    )
    unknown_record = SimpleNamespace(
        structure_id="unknown",
        candidate=unknown,
        evaluation=None,
        metadata={},
    )
    search_result = SimpleNamespace(pareto_projection=complete)

    with patch(
        "polisyos.scientist.nodes.builtins.planning.run_hierarchical_policy_search"
        "._iter_candidate_records",
        return_value=[known_record, unknown_record],
    ):
        limited_ref = _persist_frontier_report(
            execution_context,
            state=minimal_state,
            loop_id="unknown-eligibility",
            search_result=search_result,
        )
    limited = load_policy_frontier_report(execution_context.store, limited_ref)
    assert limited.global_frontier == []
    assert {item.candidate_hash for item in limited.candidate_frontier} == {
        known_hash,
        unknown_hash,
    }
    assert limited.eligibility_unknown_candidate_hashes == (unknown_hash,)
    limited_projection = limited.view_projections["global_feasible"]
    assert limited_projection.assessment.status == "denominator_limited"
    assert limited.source_feasible_candidate_hashes == (known_hash,)
    assert limited_projection.eligible_candidate_hashes == (known_hash,)
    assert limited_projection.unassessed_candidate_hashes == (known_hash,)
    assert limited_projection.ranked_frontier_hashes == ()

    with patch(
        "polisyos.scientist.nodes.builtins.planning.run_hierarchical_policy_search"
        "._iter_candidate_records",
        return_value=[known_record],
    ):
        complete_ref = _persist_frontier_report(
            execution_context,
            state=minimal_state,
            loop_id="known-eligibility",
            search_result=search_result,
        )
    complete_report = load_policy_frontier_report(execution_context.store, complete_ref)
    assert [item.candidate_hash for item in complete_report.global_frontier] == [known_hash]
    assert complete_report.eligibility_unknown_candidate_hashes == ()
    assert complete_report.view_projections["global_feasible"].assessment.status == "complete"

    omitted_feasible_record = SimpleNamespace(
        structure_id="omitted-feasible",
        candidate=unknown,
        evaluation=SimpleNamespace(feasible=True, primary={}, constraint_statuses={}),
        metadata={},
    )
    with patch(
        "polisyos.scientist.nodes.builtins.planning.run_hierarchical_policy_search"
        "._iter_candidate_records",
        return_value=[known_record, omitted_feasible_record],
    ):
        omitted_ref = _persist_frontier_report(
            execution_context,
            state=minimal_state,
            loop_id="projection-omits-feasible-source",
            search_result=search_result,
        )
    omitted = load_policy_frontier_report(execution_context.store, omitted_ref)
    assert omitted.source_feasible_candidate_hashes == tuple(sorted((known_hash, unknown_hash)))
    assert omitted.eligibility_unknown_candidate_hashes == ()
    assert omitted.view_projections["global_feasible"].assessment.status == "denominator_limited"
    assert omitted.global_frontier == []
    assert {item.candidate_hash for item in omitted.candidate_frontier} == {
        known_hash,
        unknown_hash,
    }


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


def test_hierarchical_stage_b_absent_or_mismatched_eval_safety_refuses_without_evaluation(
    execution_context,
    minimal_state,
) -> None:
    """Stage B translates the production owner's typed refusal without evaluation work."""
    candidate = PolicyCandidateSchema.from_trinity_bundle(
        _bundle(), candidate_id="candidate_eval_safety_absent"
    )
    ok = NodeOutcome(status="ok", state=minimal_state)
    evaluation_work = MagicMock()

    with (
        patch(
            "polisyos.scientist.nodes.builtins.planning.run_hierarchical_policy_search."
            "CompileFoundryNode.execute",
            return_value=ok,
        ),
        patch(
            "polisyos.scientist.nodes.builtins.planning.run_hierarchical_policy_search."
            "CompileCrossGraphEvidenceNode.execute",
            return_value=ok,
        ),
        patch(
            "polisyos.scientist.nodes.builtins.planning.run_hierarchical_policy_search."
            "ResolveParametersNode.execute",
            return_value=ok,
        ),
        patch(
            "polisyos.scientist.nodes.builtins.planning.run_hierarchical_policy_search."
            "RunCausalReadinessNode.execute",
            return_value=ok,
        ),
        patch(
            "polisyos.scientist.nodes.builtins.planning.run_hierarchical_policy_search."
            "evaluate_counterfactual_gate",
            return_value=ok,
        ),
        patch(
            "polisyos.scientist.nodes.builtins.planning.run_hierarchical_policy_search."
            "RunSimulationNode.execute",
            return_value=ok,
        ),
        patch(
            "polisyos.scientist.nodes.builtins.planning.run_hierarchical_policy_search."
            "load_simulation_metrics",
            return_value={"policy_value": 1.0},
        ),
        patch(
            "polisyos.scientist.nodes.builtins.decide.policy_runtime_support."
            "_build_evidence_driven_simulation_metrics",
            evaluation_work,
        ),
    ):
        result = _evaluate_candidate_payload(
            execution_context,
            minimal_state,
            candidate_payload=candidate.model_dump(mode="json"),
            context={},
        )

    assert result["status"] == "rejected"
    assert result["blocked_reason"] == "eval_safety_blocked"
    assert result["details"]["blocker_codes"] == [
        "polisyos.eval_safety.execution_context_missing@1.0.0"
    ]
    assert evaluation_work.call_count == 0


def test_registered_policy_vector_transfer_refuses_unbound_source_units(
    execution_context,
) -> None:
    candidate = PolicyCandidateSchema.from_trinity_bundle(
        _bundle(), candidate_id="candidate_transfer_target"
    ).model_copy(update={"parameter_schedule": []})
    coordinator = HierarchicalSearchCoordinator(
        config=HierarchicalSearchConfig(
            max_structure_candidates=1,
            max_parameter_iterations=1,
            enable_hybrid_seeds=False,
        )
    )
    spec = coordinator.build_parameter_search_spec(candidate)
    parameter_name = next(iter(spec.parameter_paths))
    bound = spec.search_space.bounds[0]
    source_params = {parameter_name: (bound.lower + bound.upper) / 2.0}
    profile = BayesianSourceProfile(
        profile_kind="injected_optimizer",
        optimizer_fqn="tests.controlled_v5_source",
        optimizer_config_fingerprint="controlled-config",
        proposal_source="injected_optimizer",
        search_space_fingerprint=spec.search_space.sobol_space_fingerprint(),
        warm_start_eligible=False,
    )
    objective_spec = coordinator.build_optimizer_objective_spec(candidate)
    objective_template = ObjectiveStack().evaluate(PolicyEvaluationBundle(candidate=candidate))
    runtime_binding = {
        "evaluation_attempt_id": "candidate-transfer-source-attempt",
        "requested_draw_count": 0,
        "requested_draw_source": "candidate-transfer-fixture",
        "effective_estimation_config_sha256": "b" * 64,
    }
    simulation_results = {
        "objective_channels": {
            channel.name: channel.value for channel in objective_template.all_channels().values()
        },
        "metric_units": {},
        "feasible": objective_template.feasible,
        "blocking_reasons": list(objective_template.blocking_reasons),
        "bootstrap": runtime_binding,
    }
    objective_vector = objective_template.with_runtime_score_assessment(
        runtime_binding
    ).with_score_source_results(simulation_results)
    objective_values = objective_vector.as_legacy_objectives(simulation_results)
    source_evaluation = Evaluation(
        candidate_id="source_candidate",
        params=source_params,
        params_normalized=spec.search_space.normalize(source_params),
        objectives=objective_values,
        scalar_score=None,
        stage_a_passed=True,
        stage_b_result={
            "status": "ok",
            "simulation_results": simulation_results,
            "policy_evaluation": objective_vector.model_dump(mode="json"),
        },
        score_status=ObjectiveScoreStatus.NOT_ESTABLISHED,
        score_assessment=None,
        metadata={"warm_start_compatibility": profile.model_dump(mode="json")},
    )
    tenant_id = "controlled-tenant"
    execution_context.run.tenant_id = tenant_id
    source_fingerprint = RunFingerprint(
        run_id="v5_source_run",
        space_hash=profile.search_space_fingerprint,
        objective_names=objective_spec.objective_names,
        bounds={parameter_name: {"lower": bound.lower, "upper": bound.upper}},
        split="selection",
        units={},
        origin="controlled-v5-candidate-source",
        tenant_id=tenant_id,
        objective_directions={
            name: direction.value
            for name, direction in zip(
                objective_spec.objective_names, objective_spec.directions, strict=True
            )
        },
        objective_rule_specs=objective_spec.objective_rule_specs,
        embedding=[1.0, 0.0],
        num_evaluations=1,
    )
    # ObjectiveStack and the runtime metrics envelope have no source-owned unit
    # binding for these axes. A value/name/RunFingerprint self-claim cannot stand
    # in for that missing measurement basis, so reject before persisting history.
    assert source_fingerprint.objective_names
    vector_index = VectorMemoryStore(dim=2)
    transfer_manager = TransferLearningManager(execution_context.store, vector_index)
    with patch.object(
        execution_context.store, "put_json", wraps=execution_context.store.put_json
    ) as persist_history:
        with pytest.raises(ValueError, match="explicitly supplied complete run fingerprint"):
            transfer_manager.register_run(source_fingerprint, [source_evaluation])
    persist_history.assert_not_called()


def _candidate_transfer_intent_payload(*, index_kind: str) -> dict[str, object]:
    return {
        "index_ref": {
            "artifact_id": "sha256:" + "0" * 64,
            "kind": index_kind,
            "media_type": "application/json",
        },
        "query_fingerprint": {
            "run_id": "source-run",
            "space_hash": "candidate-space",
            "objective_names": ["score"],
            "embedding": [1.0],
            "tenant_id": "controlled-tenant",
        },
    }


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param(None, id="explicit-null"),
        pytest.param(False, id="explicit-false"),
        pytest.param([], id="list"),
        pytest.param("invalid", id="string"),
        pytest.param({}, id="empty-mapping"),
        pytest.param({"unknown": "field"}, id="unknown-field"),
        pytest.param(
            _candidate_transfer_intent_payload(index_kind="wrong.bundle"),
            id="wrong-index-ref-kind",
        ),
        pytest.param(
            {
                **_candidate_transfer_intent_payload(index_kind="vector_memory.bundle"),
                "unknown": "field",
            },
            id="valid-shaped-request-with-unknown-field",
        ),
    ],
)
def test_explicit_malformed_candidate_transfer_fails_before_missing_candidate_skip(
    execution_context,
    minimal_state,
    payload,
) -> None:
    state = minimal_state.model_copy(deep=True)
    state.params["policy_search_candidate_transfer"] = payload

    with patch(
        "polisyos.scientist.nodes.builtins.planning.run_hierarchical_policy_search."
        "_resolve_search_candidate",
        return_value=None,
    ) as resolve_candidate:
        outcome = RunHierarchicalPolicySearchNode().execute(execution_context, state)

    assert outcome.status == "fail"
    assert outcome.error is not None
    assert "Invalid policy_search_candidate_transfer intent" in outcome.error.message
    resolve_candidate.assert_not_called()


def test_valid_candidate_transfer_without_policy_input_fails_instead_of_skipping(
    execution_context,
    minimal_state,
) -> None:
    state = minimal_state.model_copy(deep=True)
    state.params["policy_search_candidate_transfer"] = _candidate_transfer_intent_payload(
        index_kind="vector_memory.bundle"
    )

    with patch(
        "polisyos.scientist.nodes.builtins.planning.run_hierarchical_policy_search."
        "_resolve_search_candidate",
        return_value=None,
    ) as resolve_candidate:
        outcome = RunHierarchicalPolicySearchNode().execute(execution_context, state)

    assert outcome.status == "fail"
    assert outcome.error is not None
    assert "requires a policy candidate or Lex bundle input" in outcome.error.message
    resolve_candidate.assert_called_once()


def test_absent_candidate_transfer_intent_preserves_missing_candidate_skip(
    execution_context,
    minimal_state,
) -> None:
    state = minimal_state.model_copy(deep=True)
    state.params.pop("policy_search_candidate_transfer", None)

    with patch(
        "polisyos.scientist.nodes.builtins.planning.run_hierarchical_policy_search."
        "_resolve_search_candidate",
        return_value=None,
    ) as resolve_candidate:
        outcome = RunHierarchicalPolicySearchNode().execute(execution_context, state)

    assert outcome.status == "skip"
    resolve_candidate.assert_called_once()


def test_hierarchical_producer_scope_fields_reconcile_from_emitted_context() -> None:
    candidate = PolicyCandidateSchema.from_trinity_bundle(
        _bundle(), candidate_id="hierarchical-domain-candidate"
    )
    runtime_context = HierarchicalPolicySearchAdapter().build_runtime_context(
        candidate,
        loop_id="hierarchical-domain-run",
        metadata={"domain": "fiscal"},
    )
    emitted_scope = runtime_context["policy_search_context"]
    assert emitted_scope["task_family"] == emitted_scope["policy_family"]
    assert emitted_scope["domain"] == "fiscal"

    resolved = resolve_transfer_context(context=runtime_context)
    assert resolved.task_family == emitted_scope["task_family"]
    assert resolved.domain == emitted_scope["domain"]

    for field_name, conflicting_value in (
        ("task_family", "discovery"),
        ("domain", "labor"),
    ):
        conflicting = {**runtime_context, field_name: conflicting_value}
        with pytest.raises(TransferScopeRefusedError):
            resolve_transfer_context(context=conflicting)


def test_hierarchical_candidate_ranking_omits_no_score_records_and_empty_fallback() -> None:
    available = PolicyCandidateSchema.from_trinity_bundle(
        _bundle(), candidate_id="available_candidate"
    )
    unavailable = PolicyCandidateSchema.from_trinity_bundle(
        _bundle(), candidate_id="unavailable_candidate"
    )
    source = {"gdp_change": 0.0, "budget_deficit": 0.0}
    assessment = _assess_default_search_objective(source).score_assessment
    available_iteration = SimpleNamespace(
        score_status=ObjectiveScoreStatus.AVAILABLE,
        score_assessment=assessment,
        objective_value=0.0,
        candidate=available.model_dump(mode="json"),
        stage_b_result={"simulation_results": source},
        policy_evaluation=None,
        is_promising=True,
    )
    unavailable_iteration = SimpleNamespace(
        score_status=ObjectiveScoreStatus.UNAVAILABLE,
        score_assessment=None,
        objective_value=None,
        candidate=unavailable.model_dump(mode="json"),
        stage_b_result={"simulation_results": {"budget_deficit": 100.0}},
        policy_evaluation=None,
        is_promising=True,
    )
    accepted_unscored_structure = StructureCandidate(
        structure_id="unscored-structure",
        candidate=unavailable,
        candidate_hash=unavailable.candidate_hash(),
        policy_family="labor",
        source="fixture",
        accepted=True,
    )
    search_result = SimpleNamespace(
        state=SimpleNamespace(
            parameter_search_results={
                "available": SimpleNamespace(history=[available_iteration]),
                "unavailable": SimpleNamespace(history=[unavailable_iteration]),
            },
            structure_candidates=[accepted_unscored_structure],
        )
    )

    records = _iter_candidate_records(search_result)

    assert [record.candidate.candidate_id for record in records] == [
        "available_candidate",
        "unavailable_candidate",
    ]
    assert records[0].objective_value == 0.0
    assert records[1].objective_value is None
    assert _select_champion_candidate(search_result).candidate_id == "available_candidate"

    all_unavailable = SimpleNamespace(
        state=SimpleNamespace(
            parameter_search_results={
                "unavailable": SimpleNamespace(history=[unavailable_iteration]),
            },
            structure_candidates=[accepted_unscored_structure],
        )
    )
    unavailable_records = _iter_candidate_records(all_unavailable)
    assert [record.candidate.candidate_id for record in unavailable_records] == [
        "unavailable_candidate"
    ]
    assert unavailable_records[0].objective_value is None
    assert _select_champion_candidate(all_unavailable) is None


def test_hierarchical_trinity_persistence_uses_validated_run_owner_context(tmp_path) -> None:
    tenant_id = "tenant-hierarchical-trinity"
    cell_id = "cell-hierarchical-trinity"
    base_store = FileSystemCAS(tmp_path / "tenant-cas")
    tenant_store = base_store.for_tenant(tenant_id, cell_id)
    bundle = _bundle()
    with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
        registry_ref = tenant_store.put_json(
            {"registry": {}},
            PutOptions(kind="core.registry.bundle", media_type="application/json"),
            return_selected_profile=True,
        )
        run = RunContext.start(
            store=tenant_store,
            registry_bundle=registry_ref,
            run_id="R_hierarchical_trinity_owner",
            tenant_id=tenant_id,
            cell_id=cell_id,
            access_scope=None,
        )
        completed = False
        try:
            run.update_manifest(
                execution_profile="test",
                control_job_id="job_hierarchical_trinity_owner",
            )
            context = ExecutionContext(
                store=tenant_store,
                run=run,
                logger=logging.getLogger("test.hierarchical_trinity_owner"),
            )
            node_context = _node_facing_context(context)
            state = ExperimentState(run_id=run.run_manifest.run_id)

            selected_ref = _persist_trinity_bundle(node_context, bundle, state=state)
            manifest = tenant_store.get_manifest(selected_ref)
            assert manifest.tenant_context == ArtifactTenantContextInfo(
                tenant_id=tenant_id,
                cell_id=cell_id,
            )
            loaded_bundle = load_trinity_bundle_artifact(tenant_store, selected_ref)
            # ParamValue is opaque; compare the persisted JSON representation.
            assert loaded_bundle.model_dump(mode="json") == bundle.model_dump(mode="json")

            run.add_output(selected_ref)
            completed = True
        finally:
            run.finalize(status="ok" if completed else "failed")


def test_hierarchical_trinity_persistence_refuses_job_without_owner_scope_before_write(
    tmp_path,
) -> None:
    from unittest.mock import patch

    base_store = FileSystemCAS(tmp_path / "unscoped-cas")
    registry_ref = base_store.put_json(
        {"registry": {}},
        PutOptions(kind="core.registry.bundle", media_type="application/json"),
        return_selected_profile=True,
    )
    run = RunContext.start(
        store=base_store,
        registry_bundle=registry_ref,
        run_id="R_hierarchical_trinity_unscoped_job",
        access_scope=None,
    )
    try:
        run.update_manifest(control_job_id="job_hierarchical_trinity_unscoped")
        context = ExecutionContext(
            store=base_store,
            run=run,
            logger=logging.getLogger("test.hierarchical_trinity_owner_refusal"),
        )
        state = ExperimentState(run_id=run.run_manifest.run_id)
        with patch("polisyos.ir.trinity.loaders.persist_trinity_bundle_artifact") as writer:
            with pytest.raises(
                ValueError,
                match="run_owner_control_job_tenant_context_not_established",
            ):
                _persist_trinity_bundle(context, _bundle(), state=state)
            writer.assert_not_called()
    finally:
        run.finalize(status="failed")


def test_legacy_candidate_transfer_continues_cold_with_persisted_limitation(
    execution_context, minimal_state, artifact_ref_factory, monkeypatch
) -> None:
    pytest.importorskip("hnswlib")
    import polisyos.scientist.agent.vector_memory as vector_module

    source = VectorMemoryStore(dim=2, max_elements=4)
    source.add("source", [1.0, 0.0], {"source": "fixture"})
    legacy = source.save_to_artifact(execution_context.store)
    candidate = PolicyCandidateSchema.from_trinity_bundle(_bundle(), candidate_id="cold-target")
    spec = HierarchicalSearchCoordinator().build_optimizer_objective_spec(candidate)
    execution_context.run.tenant_id = "controlled-tenant"
    state = minimal_state.model_copy(deep=True)
    loop_id = str(state.params.get("policy_loop_id") or f"{state.run_id}:policy_search")
    state.params["policy_search_candidate_transfer"] = {
        "index_ref": legacy.model_dump(mode="json"),
        "query_fingerprint": {
            "run_id": loop_id,
            "space_hash": "controlled-space",
            "objective_names": spec.objective_names,
            "objective_directions": dict(
                zip(spec.objective_names, [d.value for d in spec.directions], strict=True)
            ),
            "objective_rule_specs": spec.objective_rule_specs,
            "embedding": [1.0, 0.0],
            "tenant_id": "controlled-tenant",
        },
    }
    candidate_hash = candidate.candidate_hash()
    search_result = SimpleNamespace(
        state=SimpleNamespace(
            structure_candidates=[
                SimpleNamespace(
                    structure_id="cold",
                    candidate=candidate,
                    accepted=True,
                    candidate_hash=candidate_hash,
                    metadata={},
                )
            ],
            parameter_search_results={},
        ),
        model_dump=lambda mode="json": {"status": "candidate_only"},
    )

    def forbidden_index(*_args, **_kwargs):
        raise AssertionError("legacy transfer must not construct or load a native index")

    class NoNativeModule:
        Index = staticmethod(forbidden_index)

    monkeypatch.setattr(vector_module, "hnswlib", NoNativeModule())
    with (
        patch(
            "polisyos.scientist.nodes.builtins.planning.run_hierarchical_policy_search._resolve_search_candidate",
            return_value=candidate,
        ),
        patch(
            "polisyos.scientist.nodes.builtins.planning.run_hierarchical_policy_search.HierarchicalPolicySearchAdapter.run_search",
            return_value=search_result,
        ) as run_search,
        patch(
            "polisyos.scientist.nodes.builtins.planning.run_hierarchical_policy_search._persist_trinity_bundle",
            return_value=artifact_ref_factory(kind="ir.trinity_bundle"),
        ),
    ):
        outcome = RunHierarchicalPolicySearchNode().execute(execution_context, state)
    assert outcome.status == "ok"
    assert run_search.call_args.kwargs["candidate_only_seed_evaluations"] is None
    limitation = {
        "status": "limited",
        "reason": "unversioned_bundle_not_admitted",
        "continuation": "cold_search",
    }
    assert outcome.state.params["policy_search_result"]["transfer_limitation"] == limitation
    assert [event.code for event in outcome.events] == ["policy_search.transfer_limited"]
    report_ref = outcome.state.artifacts_index[ARTIFACT_POLICY_FRONTIER_REPORT_REF]
    report = load_policy_frontier_report(FileSystemCAS(execution_context.store.root), report_ref)
    assert report.metadata["transfer_limitation"] == limitation
