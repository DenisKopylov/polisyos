from __future__ import annotations

from decimal import Decimal

from polisyos.ir.governance.policy_spec import InterventionSpec, ParameterSpec, PolicySpec
from polisyos.ir.governance.problem_frame import ObjectiveSpec, ProblemDomain, ProblemFrame
from polisyos.ir.model_spec import ModelSpec
from polisyos.ir.trinity import TrinityBundle
from polisyos.ir.types import OptimizationDirection, SelectorOperator
from polisyos.scientist.policy_design.objectives import (
    ConstraintStatus,
    ObjectiveChannelValue,
    ObjectiveDirection,
    ObjectiveKind,
    PolicyEvaluationVector,
)
from polisyos.scientist.policy_design.schema import PolicyCandidateSchema, TargetPopulationSpec
from polisyos.scientist.search.pareto_registry import ParetoRegistry
from polisyos.scientist.search.transfer_context import TransferContext


def _candidate() -> PolicyCandidateSchema:
    return PolicyCandidateSchema(
        candidate_id="candidate_policy",
        trinity_bundle=TrinityBundle(
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
                    )
                ],
            ),
            model_spec=ModelSpec(
                model_id="model_policy",
                data_snapshot_ref="sha256:" + "1" * 64,
            ),
        ),
        target_population=TargetPopulationSpec(
            population_id="population_policy",
            description="General population",
            geography="national",
        ),
        metadata={"policy_family": "core_family"},
    )


def _evaluation_vector(candidate: PolicyCandidateSchema) -> PolicyEvaluationVector:
    return PolicyEvaluationVector(
        candidate_id=candidate.candidate_id,
        primary={
            "policy_value": ObjectiveChannelValue(
                name="policy_value",
                kind=ObjectiveKind.PRIMARY,
                value=1.2,
                direction=ObjectiveDirection.MAXIMIZE,
            )
        },
        hard_constraints={
            "policy_budget_constraint": ObjectiveChannelValue(
                name="policy_budget_constraint",
                kind=ObjectiveKind.HARD_CONSTRAINT,
                value=0.95,
                direction=ObjectiveDirection.MINIMIZE,
                threshold=1.0,
                status=ConstraintStatus.NEAR_BINDING,
            )
        },
        secondary={},
        penalties={},
        feasible=True,
        blocking_reasons=[],
        metadata={"policy_family": "core_family", "candidate_hash": candidate.candidate_hash()},
    )


def test_publish_transfer_surface_produces_seed_only_bundle(tmp_path) -> None:
    registry = ParetoRegistry(tmp_path / "registry")
    candidate = _candidate()
    evaluation = _evaluation_vector(candidate)
    source = TransferContext(
        task_family="policy",
        domain="fiscal",
        run_id="loop-source",
        tenant_hash="tenant-a",
    )
    target = TransferContext(
        task_family="policy",
        domain="labor",
        run_id="loop-target",
        tenant_hash="tenant-a",
    )

    registry.update(
        "loop-source",
        candidate_hash=candidate.candidate_hash(),
        evaluation=evaluation,
        candidate_id=candidate.candidate_id,
        policy_family="core_family",
        seed_payload=candidate.model_dump(mode="json"),
        transfer_context=source,
    )

    bundle = registry.get_seed_bundle(target, max_seeds=3)
    warm_start = registry.build_warm_start_evaluations(target, max_seeds=3)

    assert bundle.entries
    assert all(entry.seed_only for entry in bundle.entries)
    assert bundle.cross_domain_seed_count == 1
    assert warm_start
    assert warm_start[0]["metadata"]["seed_only"] is True
    assert registry.get_snapshot("loop-target").entries == {}


def test_same_domain_seed_sorting_precedes_cross_domain(tmp_path) -> None:
    registry = ParetoRegistry(tmp_path / "registry")
    candidate = _candidate()
    evaluation = _evaluation_vector(candidate)
    registry.update(
        "loop-fiscal",
        candidate_hash=f"{candidate.candidate_hash()}::fiscal",
        evaluation=evaluation.model_copy(update={"candidate_id": "candidate_fiscal"}),
        candidate_id="candidate_fiscal",
        policy_family="core_family",
        seed_payload=candidate.model_dump(mode="json"),
        transfer_context=TransferContext(
            task_family="policy",
            domain="fiscal",
            run_id="loop-fiscal",
            tenant_hash="tenant-a",
        ),
    )
    registry.update(
        "loop-labor",
        candidate_hash=f"{candidate.candidate_hash()}::labor",
        evaluation=evaluation.model_copy(update={"candidate_id": "candidate_labor"}),
        candidate_id="candidate_labor",
        policy_family="core_family",
        seed_payload=candidate.model_dump(mode="json"),
        transfer_context=TransferContext(
            task_family="policy",
            domain="labor",
            run_id="loop-labor",
            tenant_hash="tenant-a",
        ),
    )

    bundle = registry.get_seed_bundle(
        TransferContext(
            task_family="policy",
            domain="labor",
            run_id="loop-target",
            tenant_hash="tenant-a",
        ),
        max_seeds=5,
    )

    assert len(bundle.entries) >= 2
    assert bundle.entries[0].domain == "labor"
