"""Engine nodes for the existing Stage B candidate evaluation pipeline.

The graph and node instances here are a template, not an admission or a grant.
Only an independently appointed execution owner may run the template as a child.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.scientist.orchestration.engine.protocol import NodeOutcome, NodeSpec
from polisyos.scientist.orchestration.engine.state_branching import branch_state
from polisyos.scientist.policy_design.schema import PolicyCandidateSchema

if TYPE_CHECKING:
    from polisyos.scientist.orchestration.engine.context import ExecutionContext
    from polisyos.scientist.orchestration.engine.state import ExperimentState
    from polisyos.scientist.orchestration.engine.sub_workflow import SubWorkflowConfig


_CANDIDATE_KEY = "child_stage_b_candidate"
_PROJECTION_KEY = "child_stage_b_projection_ref"
_SELECTED_CANDIDATE_KEY = "child_stage_b_selected_candidate_ref"
_SELECTED_EVALUATION_KEY = "child_stage_b_selected_evaluation_ref"


def _spec(component_id: str, title: str, writes: list[str]) -> NodeSpec:
    return NodeSpec(
        metadata=ComponentMetadata(
            component_id=ComponentId.parse(component_id),
            kind=ComponentKind.SCIENTIST_NODE,
            abi_targets={"world_abi": "1.x"},
            display_name=title,
            description=title,
            tags=["builtin", "planning", "child_candidate"],
            capabilities=Capability.SCIENTIST_NODE,
        ),
        state_reads=["params", "inputs", "artifacts_index", "reports_index"],
        state_writes=writes,
        produces=[],
    )


class StageBPrepareNode:
    """Construct one isolated candidate input using the existing Trinity producer."""

    @property
    def spec(self) -> NodeSpec:
        from polisyos.scientist.nodes.builtins.planning.run_hierarchical_policy_search import (
            _INNER_CANDIDATE_ARTIFACT_KEYS,
        )
        from polisyos.scientist.nodes.builtins.state_keys import INPUT_TRINITY_BUNDLE_REF

        return _spec(
            "scientist.node_prepare_child_stage_b@1.0.0",
            "Prepare child Stage B candidate",
            [
                "params.policy_candidate_schema",
                f"inputs.{INPUT_TRINITY_BUNDLE_REF}",
                *(f"artifacts_index.{key}" for key in _INNER_CANDIDATE_ARTIFACT_KEYS),
                f"artifacts_index.{_PROJECTION_KEY}",
                f"artifacts_index.{_SELECTED_CANDIDATE_KEY}",
                f"artifacts_index.{_SELECTED_EVALUATION_KEY}",
            ],
        )

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        """Write the candidate and clear preceding candidate artifacts in the child only."""
        from polisyos.core.artifacts import ensure_ir_artifact_store, input_ref_from_artifact_ref
        from polisyos.core.contracts import TrinityBundleRef
        from polisyos.ir.trinity import persist_trinity_bundle_artifact
        from polisyos.scientist.nodes.builtins.planning.run_hierarchical_policy_search import (
            _INNER_CANDIDATE_ARTIFACT_KEYS,
            _candidate_payload_without_hash,
        )
        from polisyos.scientist.nodes.builtins.planning.stage_b_projection import (
            persist_stage_b_candidate,
        )
        from polisyos.scientist.nodes.builtins.state_keys import INPUT_TRINITY_BUNDLE_REF

        payload = state.params.get(_CANDIDATE_KEY)
        if type(payload) is not dict:
            raise ValueError("child_stage_b_candidate_invalid")
        candidate = PolicyCandidateSchema.model_validate(_candidate_payload_without_hash(payload))
        result = branch_state(state, write_paths=self.spec.state_writes).state
        result.params["policy_candidate_schema"] = candidate
        if "policy_candidate" in state.inputs:
            raise ValueError("child_stage_b_candidate_input_role_reserved")
        candidate_ref = persist_stage_b_candidate(ctx.store, candidate, state.inputs)
        inputs = [input_ref_from_artifact_ref(candidate_ref, role="policy_candidate")]
        inputs.extend(
            input_ref_from_artifact_ref(ref, role=key) for key, ref in state.inputs.items()
        )
        selected = persist_trinity_bundle_artifact(
            ensure_ir_artifact_store(ctx.store),
            candidate.trinity_bundle,
            inputs=inputs,
            tenant_context=ctx.run.artifact_tenant_context(),
        )
        result.inputs[INPUT_TRINITY_BUNDLE_REF] = TrinityBundleRef.model_validate(
            selected.model_dump(mode="json")
        )
        for key in (
            *_INNER_CANDIDATE_ARTIFACT_KEYS,
            _PROJECTION_KEY,
            _SELECTED_CANDIDATE_KEY,
            _SELECTED_EVALUATION_KEY,
        ):
            result.artifacts_index.pop(key, None)
        result.artifacts_index[_SELECTED_CANDIDATE_KEY] = candidate_ref
        return NodeOutcome(status="ok", state=result, artifacts=[candidate_ref])


def _evaluate_stage_b(ctx: ExecutionContext, state: ExperimentState) -> dict[str, Any]:
    """Run the existing evaluation owner after the child's simulation step."""
    from polisyos.core.run.child_custody import ChildComputationOutcomeUnknown
    from polisyos.scientist.nodes.builtins.c6c_runtime_support import resolve_baseline_policy_value
    from polisyos.scientist.nodes.builtins.decide.policy_runtime_support import (
        PolicyRuntimeEvaluationSafetyError,
        ProductionPolicyEvaluationBackend,
        build_policy_runtime_evaluation,
        load_ambiguity_certificate,
        load_causal_report,
        load_cross_graph_profile,
        load_distributional_report_for_state,
        load_governance_report,
        load_search_uncertainty,
        load_simulation_metrics,
        persist_policy_evaluation_vector,
    )
    from polisyos.scientist.nodes.builtins.planning.run_hierarchical_policy_search import (
        _rejected_stage_b_result,
        _world_model_record_from_state,
    )
    from polisyos.scientist.policy_design.schema import load_policy_candidate_schema

    candidate = PolicyCandidateSchema.model_validate(state.params.get("policy_candidate_schema"))
    gate_summary = dict(state.params.get("counterfactual_gate_summary") or {})
    try:
        artifact = build_policy_runtime_evaluation(
            candidate,
            backend=ProductionPolicyEvaluationBackend(
                eval_safety_execution_context=ctx.eval_safety_execution_context,
                eval_safety_verifier=ctx.eval_safety_verifier,
                world_model_record=_world_model_record_from_state(state),
            ),
            fidelity="selection",
            simulation_metrics=load_simulation_metrics(ctx, state) or None,
            uncertainty=load_search_uncertainty(ctx, state),
            distributional_report=load_distributional_report_for_state(ctx, state),
            causal_effect_report=load_causal_report(ctx, state),
            cross_graph_profile=load_cross_graph_profile(ctx, state),
            governance_report=load_governance_report(ctx, state),
            ambiguity_certificate=load_ambiguity_certificate(ctx, state),
        )
    except PolicyRuntimeEvaluationSafetyError as exc:
        return _rejected_stage_b_result(
            candidate,
            blocked_reason="eval_safety_blocked",
            details={"blocker_codes": list(exc.blocker_codes)},
        )
    evaluation = artifact.evaluation_vector.model_copy(
        update={
            "metadata": {
                **dict(artifact.evaluation_vector.metadata),
                "counterfactual_gate_summary": gate_summary,
                "candidate_hash": candidate.candidate_hash(),
            }
        }
    )
    simulation_results = dict(artifact.simulation_results)
    objective_value, score_status = evaluation.legacy_scalar_proxy_for_search(simulation_results)
    candidate_ref = evaluation_ref = None
    try:
        candidate_ref = state.artifacts_index.get(_SELECTED_CANDIDATE_KEY)
        if (
            candidate_ref is None
            or load_policy_candidate_schema(ctx.store, candidate_ref) != candidate
        ):
            raise ValueError("child_stage_b_selected_candidate_mismatch")
        evaluation_ref = persist_policy_evaluation_vector(
            ctx, candidate_ref=candidate_ref, evaluation_vector=evaluation
        )
    except ChildComputationOutcomeUnknown:
        raise
    except (AttributeError, ImportError, OSError, RuntimeError, TypeError, ValueError):
        # Retain the original candidate-only behavior; no ref means no source admission.
        candidate_ref = evaluation_ref = None
    return {
        "candidate_ref": candidate_ref.model_dump(mode="json") if candidate_ref else None,
        "policy_evaluation_ref": evaluation_ref.model_dump(mode="json") if evaluation_ref else None,
        "status": "ok",
        "feasible": bool(evaluation.feasible),
        "objective_value": objective_value,
        "objective_score_status": score_status.value,
        "simulation_results": simulation_results,
        "policy_evaluation": evaluation.model_dump(mode="json"),
        "counterfactual_gate_summary": gate_summary,
        "baseline_policy_value": resolve_baseline_policy_value(artifact.simulation_results),
    }


class StageBFinalizeNode:
    """Persist the real candidate observation for owner-verified handoff."""

    @property
    def spec(self) -> NodeSpec:
        return _spec(
            "scientist.node_finalize_child_stage_b@1.0.0",
            "Finalize child Stage B observation",
            [
                f"artifacts_index.{_PROJECTION_KEY}",
                f"artifacts_index.{_SELECTED_CANDIDATE_KEY}",
                f"artifacts_index.{_SELECTED_EVALUATION_KEY}",
            ],
        ).model_copy(update={"produces": [_PROJECTION_KEY]})

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        """Persist the actual evaluator result; it is not a closure or release grant."""
        from polisyos.scientist.nodes.builtins.planning.stage_b_projection import (
            persist_stage_b_projection,
            stage_b_projection,
        )

        observation = _evaluate_stage_b(ctx, state)
        projection = stage_b_projection(observation)
        ref = persist_stage_b_projection(ctx.store, observation)
        result = branch_state(state, write_paths=self.spec.state_writes).state
        result.artifacts_index[_PROJECTION_KEY] = ref
        artifacts = [ref]
        for key, selected in (
            (_SELECTED_CANDIDATE_KEY, projection.candidate_ref),
            (_SELECTED_EVALUATION_KEY, projection.evaluation_ref),
        ):
            if selected is None:
                result.artifacts_index.pop(key, None)
            else:
                result.artifacts_index[key] = selected
                artifacts.append(selected)
        return NodeOutcome(status="ok", state=result, artifacts=artifacts)


def stage_b_child_template() -> tuple[SubWorkflowConfig, tuple[object, ...]]:
    """Return the fixed builtin graph; the caller must independently appoint it."""
    from polisyos.scientist.nodes.builtins.causal.counterfactual_identification_gate import (
        CounterfactualIdentificationGateNode,
    )
    from polisyos.scientist.nodes.builtins.causal.resolve_parameters import ResolveParametersNode
    from polisyos.scientist.nodes.builtins.causal.run_causal_readiness import RunCausalReadinessNode
    from polisyos.scientist.nodes.builtins.compile.compile_foundry import CompileFoundryNode
    from polisyos.scientist.nodes.builtins.planning.compile_cross_graph_evidence import (
        CompileCrossGraphEvidenceNode,
    )
    from polisyos.scientist.nodes.builtins.simulate.run_simulation import RunSimulationNode
    from polisyos.scientist.orchestration.engine.state import ExperimentState
    from polisyos.scientist.orchestration.engine.sub_workflow import StateMapping, SubWorkflowConfig
    from polisyos.scientist.orchestration.engine.workflow_spec import NodeInvocation, WorkflowSpec

    names_and_nodes = (
        ("prepare", StageBPrepareNode()),
        ("compile", CompileFoundryNode()),
        ("cross_graph", CompileCrossGraphEvidenceNode()),
        ("resolve_parameters", ResolveParametersNode()),
        ("readiness", RunCausalReadinessNode()),
        ("counterfactual", CounterfactualIdentificationGateNode()),
        ("simulate", RunSimulationNode()),
        ("finalize", StageBFinalizeNode()),
    )
    nodes = [
        NodeInvocation(
            alias=name,
            node_id=node.spec.metadata.component_id,
            depends_on=[names_and_nodes[index - 1][0]] if index else [],
        )
        for index, (name, node) in enumerate(names_and_nodes)
    ]
    mappings = [
        StateMapping(source_path=name, target_path=name)
        for name in ExperimentState.model_fields
        if name not in {"run_id", "schema_version", "budgets", "last_checkpoint_ref"}
    ]
    return (
        SubWorkflowConfig(
            workflow=WorkflowSpec(
                workflow_id="child_stage_b", nodes=nodes, error_policy="fail_fast"
            ),
            input_mappings=mappings,
            output_mappings=[],
            max_depth=1,
        ),
        tuple(node for _, node in names_and_nodes),
    )
