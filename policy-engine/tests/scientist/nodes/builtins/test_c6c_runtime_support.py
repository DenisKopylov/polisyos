from __future__ import annotations

from decimal import Decimal

from polisyos.core.contracts.foundry import LoweredIR, LoweredMechanism, ProgramGraph, ProgramNode, ProgramOp
from polisyos.ir.governance.policy_spec import InterventionSpec, ParameterSpec, PolicySpec
from polisyos.ir.governance.problem_frame import ObjectiveSpec, ProblemDomain, ProblemFrame
from polisyos.ir.model_spec import ModelSpec
from polisyos.ir.trinity import TrinityBundle
from polisyos.ir.types import OptimizationDirection, SelectorOperator
from polisyos.scientist.nodes.builtins.c6c_runtime_support import (
    build_policy_parameter_override_bundle,
)
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
                _candidate().parameter_schedule[0].model_copy(
                    update={"scheduled_value": Decimal("0.15")}
                )
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
