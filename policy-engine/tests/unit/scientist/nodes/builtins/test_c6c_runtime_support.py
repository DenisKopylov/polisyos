from __future__ import annotations

import logging
from decimal import Decimal

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.contracts.foundry import (
    LoweredIR,
    LoweredMechanism,
    ProgramGraph,
    ProgramNode,
    ProgramOp,
)
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.ir.analytics.abstraction import (
    AbstractionCertificate,
    AbstractionPreservationType,
    FiniteStateAbstractionMap,
    VariableStateAbstraction,
    persist_abstraction_certificate,
    persist_finite_state_abstraction_map,
)
from polisyos.ir.governance.policy_spec import InterventionSpec, ParameterSpec, PolicySpec
from polisyos.ir.governance.problem_frame import ObjectiveSpec, ProblemDomain, ProblemFrame
from polisyos.ir.model_spec import ModelSpec
from polisyos.ir.trinity import TrinityBundle
from polisyos.ir.types import OptimizationDirection, SelectorOperator
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.nodes.builtins.c6c_runtime_support import (
    build_policy_parameter_override_bundle,
    build_runtime_abstraction_metadata,
)
from polisyos.scientist.nodes.builtins.state_keys import ARTIFACT_ABSTRACTION_CERTIFICATE_REF
from polisyos.scientist.policy_design.schema import (
    ParameterScheduleEntry,
    PolicyCandidateSchema,
    RolloutStep,
    TargetPopulationSpec,
)


def _candidate() -> PolicyCandidateSchema:
    bundle = TrinityBundle(
        problem_frame=ProblemFrame(
            problem_id="problem_policy",
            domain=ProblemDomain.FISCAL,
            objectives=[
                ObjectiveSpec(
                    objective_id="welfare",
                    metric_id="welfare_metric",
                    direction=OptimizationDirection.MAXIMIZE,
                )
            ],
        ),
        policy_spec=PolicySpec(
            policy_id="policy_policy",
            interventions=[
                InterventionSpec(
                    intervention_id="tax_cut",
                    kind="tax_policy",
                    target={
                        "kind": "predicate",
                        "field": "id",
                        "operator": SelectorOperator.EQUALS,
                        "value": "all",
                    },
                    schedule={"start_step": 0, "duration_steps": 2},
                    params={"rate": Decimal("0.1")},
                )
            ],
            parameters=[
                ParameterSpec(
                    param_id="tax_rate",
                    intervention_id="tax_cut",
                    param_path="rate",
                    default_value=Decimal("0.1"),
                    min_value=Decimal("0.05"),
                    max_value=Decimal("0.2"),
                )
            ],
        ),
        model_spec=ModelSpec(
            model_id="model_policy",
            data_snapshot_ref="sha256:" + "1" * 64,
        ),
    )
    return PolicyCandidateSchema(
        candidate_id="candidate_policy",
        trinity_bundle=bundle,
        target_population=TargetPopulationSpec(
            population_id="population_policy",
            description="General population",
        ),
        rollout_plan=[
            RolloutStep(
                step_id="step_tax",
                intervention_id="tax_cut",
                order=0,
                schedule={"start_step": 0, "duration_steps": 2},
            )
        ],
        parameter_schedule=[
            ParameterScheduleEntry(
                entry_id="schedule_tax_rate",
                param_id="tax_rate",
                scheduled_value=Decimal("0.1"),
            )
        ],
        metadata={"policy_family": "core_family"},
    )


def test_build_policy_parameter_override_bundle_maps_candidate_parameter_to_program_node(
    artifact_ref_factory,
) -> None:
    candidate = _candidate().model_copy(
        update={
            "parameter_schedule": [
                _candidate()
                .parameter_schedule[0]
                .model_copy(update={"scheduled_value": Decimal("0.15")})
            ]
        }
    )
    ir_ref = artifact_ref_factory(kind="ir.trinity_bundle")
    lowered_ir = LoweredIR(
        ir_ref=ir_ref,
        mechanisms=[
            LoweredMechanism(
                binding_id="binding_tax",
                mechanism_id="mechanism_tax",
                intervention_ids=["tax_cut"],
            )
        ],
    )
    program_graph = ProgramGraph(
        ir_ref=ir_ref,
        nodes=[
            ProgramNode(
                node_id="node_tax",
                node_kind="op",
                op=ProgramOp(
                    op_kind="apply_mechanism",
                    params={"binding_id": "binding_tax"},
                ),
            )
        ],
        edges=[],
        entrypoints=["node_tax"],
    )

    bundle = build_policy_parameter_override_bundle(
        candidate=candidate,
        lowered_ir=lowered_ir,
        program_graph=program_graph,
    )

    assert bundle is not None
    assert bundle.overrides["node_tax"]["rate"] == Decimal("0.15")
    assert bundle.sources["node_tax"] == ["parameter_schedule:schedule_tax_rate"]


def test_build_runtime_abstraction_metadata_includes_continuous_error_bound_spec(
    tmp_path,
) -> None:
    store = FileSystemCAS(tmp_path)
    registry_bundle = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(
        store=store,
        registry_bundle=registry_bundle,
        run_id="R_runtime_abstraction_metadata",
    )
    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger("test.runtime"))

    abstraction_map_ref = persist_finite_state_abstraction_map(
        store,
        FiniteStateAbstractionMap(
            variable_maps=(
                VariableStateAbstraction(
                    micro_variable="X_m",
                    macro_variable="X",
                    state_map={"__continuous__": "__continuous__"},
                ),
            )
        ),
    )
    certificate_ref = persist_abstraction_certificate(
        store,
        AbstractionCertificate(
            micro_graph_ref={
                "artifact_id": "sha256:" + "a" * 64,
                "kind": "ir.causal_graph_model",
                "media_type": "application/json",
            },
            macro_graph_ref={
                "artifact_id": "sha256:" + "b" * 64,
                "kind": "ir.causal_graph_model",
                "media_type": "application/json",
            },
            abstraction_map_ref=abstraction_map_ref,
            preservation_type=AbstractionPreservationType.POLICY_VALUE_ONLY,
            preserved_queries=("policy_value:planner_welfare",),
            error_bound=0.2,
            metadata={
                "abstraction_family": "continuous_linear_gaussian",
                "allowed_intervention_family": "hard_or_soft_declared_scope",
                "intervention_family_verified": True,
                "proof_obligations_satisfied": [
                    "linear_gaussian_closed_form",
                    "decision_margin_gate_materialized",
                ],
                "estimand_error_bounds": {
                    "policy_value:planner_welfare": 0.2,
                },
                "diagnostics": {"global_state_bound": 0.1},
                "non_preserved_queries": ["unit_level_counterfactual"],
                "error_bound_spec": {
                    "scope": {
                        "query_family": "policy_value",
                        "interventions": "hard_or_soft_declared_scope",
                        "action_domain": "compact_box",
                    },
                    "state_metric": "weighted_l1",
                    "distribution_metric": "wasserstein_2_gaussian",
                    "value_lipschitz_constant": 1.0,
                    "global_state_bound": 0.1,
                    "recommendation_margin_required": 0.4,
                    "gain_matrix_spectral_radius": 0.0,
                    "tightness_status": "exact_on_linear_gaussian",
                },
            },
        ),
    )

    metadata = build_runtime_abstraction_metadata(
        ctx,
        artifacts_index={ARTIFACT_ABSTRACTION_CERTIFICATE_REF: certificate_ref},
    )

    assert metadata["abstraction_preservation_type"] == "policy_value_only"
    assert metadata["abstraction_error_bound"] == 0.2
    assert metadata["abstraction_recommendation_margin_required"] == 0.4
    assert metadata["abstraction_error_bound_spec"] == {
        "scope": {
            "query_family": "policy_value",
            "interventions": "hard_or_soft_declared_scope",
            "action_domain": "compact_box",
        },
        "state_metric": "weighted_l1",
        "distribution_metric": "wasserstein_2_gaussian",
        "value_lipschitz_constant": 1.0,
        "global_state_bound": 0.1,
        "recommendation_margin_required": 0.4,
        "gain_matrix_spectral_radius": 0.0,
        "tightness_status": "exact_on_linear_gaussian",
    }
