from __future__ import annotations

import logging

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.contracts.foundry import Metrics
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.ir.analytics.normative_arbitration import (
    ArbitrationOption,
    NormativeAuditStatus,
    NormativeModelCompleteness,
)
from polisyos.ir.governance.problem_frame import (
    ConstraintSpec,
    NormativeArbitrationPolicy,
    NormativeFrame,
    NormativeOutcomeChannel,
    ProblemDomain,
    ProblemFrame,
    StakeholderOutcomeBinding,
    StakeholderRightSpec,
    StakeholderSpec,
    StakeholderUtilityTerm,
    UtilityDirection,
)
from polisyos.ir.model_layer.types import EntityType
from polisyos.scientist.nodes.builtins.governance.normative_arbitration_calculations import (
    _audit_hard_constraints,
    _audit_rights,
    _compute_stakeholder_utilities,
    _evaluate_policies,
    _resolve_binding_values,
    _resolve_model_completeness,
)
from polisyos.scientist.orchestration.engine.context import ExecutionContext


def test_calculations_preserve_utility_rights_and_unevaluated_status_mix(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    registry_bundle = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(
        store=store,
        registry_bundle=registry_bundle,
        run_id="R_normative_calculations",
    )
    ctx = ExecutionContext(
        store=store,
        run=run,
        logger=logging.getLogger("test.normative.calculations"),
    )

    frame = NormativeFrame(
        enabled_policies=[
            NormativeArbitrationPolicy.LEXICOGRAPHIC_RIGHTS,
            NormativeArbitrationPolicy.WEIGHTED_WELFARE,
            NormativeArbitrationPolicy.MAX_MIN_HARM,
            NormativeArbitrationPolicy.PARETO_FILTER,
        ],
        stakeholder_bindings=[
            StakeholderOutcomeBinding(
                binding_id="worker_outcome",
                stakeholder_id="workers",
                channel=NormativeOutcomeChannel.SIMULATION_METRIC,
                outcome_key="worker_impact",
            ),
            StakeholderOutcomeBinding(
                binding_id="owner_outcome",
                stakeholder_id="owners",
                channel=NormativeOutcomeChannel.SIMULATION_METRIC,
                outcome_key="owner_impact",
            ),
            StakeholderOutcomeBinding(
                binding_id="missing_outcome",
                stakeholder_id="workers",
                channel=NormativeOutcomeChannel.SIMULATION_METRIC,
                outcome_key="missing_metric",
            ),
            StakeholderOutcomeBinding(
                binding_id="nonfinite_outcome",
                stakeholder_id="owners",
                channel=NormativeOutcomeChannel.SIMULATION_METRIC,
                outcome_key="nonfinite_metric",
            ),
        ],
        utility_terms=[
            StakeholderUtilityTerm(
                term_id="worker_utility",
                stakeholder_id="workers",
                binding_refs=["worker_outcome"],
                direction=UtilityDirection.MAXIMIZE,
                coefficient=1,
                welfare_weight=1,
            ),
            StakeholderUtilityTerm(
                term_id="owner_utility",
                stakeholder_id="owners",
                binding_refs=["owner_outcome"],
                direction=UtilityDirection.MINIMIZE,
                coefficient=2,
                welfare_weight=3,
            ),
        ],
        rights_catalog=[
            StakeholderRightSpec(
                right_id="worker_non_loss",
                stakeholder_id="workers",
                binding_ref="worker_outcome",
                operator=">=",
                threshold=0,
            ),
            StakeholderRightSpec(
                right_id="owner_soft_target",
                stakeholder_id="owners",
                binding_ref="owner_outcome",
                operator=">=",
                threshold=-2,
                hard=False,
            ),
            StakeholderRightSpec(
                right_id="owner_floor_satisfied",
                stakeholder_id="owners",
                binding_ref="owner_outcome",
                operator=">=",
                threshold=-4,
            ),
            StakeholderRightSpec(
                right_id="worker_type_mismatch",
                stakeholder_id="workers",
                binding_ref="worker_outcome",
                operator=">=",
                threshold="unavailable",
            ),
            StakeholderRightSpec(
                right_id="missing_right_binding",
                stakeholder_id="workers",
                binding_ref="missing_outcome",
                operator=">=",
                threshold=0,
            ),
        ],
        hard_constraint_refs=["budget_limit", "missing_metric_limit"],
    )
    problem_frame = ProblemFrame(
        problem_id="normative_calculation_problem",
        domain=ProblemDomain.SOCIAL,
        stakeholders=[
            StakeholderSpec(
                stakeholder_id="workers",
                entity_type=EntityType.AGENT,
            ),
            StakeholderSpec(
                stakeholder_id="owners",
                entity_type=EntityType.AGENT,
            ),
        ],
        hard_constraints=[
            ConstraintSpec(
                constraint_id="budget_limit",
                value=10,
                slot_id="budget",
                operator="<=",
            ),
            ConstraintSpec(
                constraint_id="missing_metric_limit",
                value=10,
                slot_id="missing_budget_metric",
                operator="<=",
            ),
        ],
        normative_frame=frame,
    )

    binding_values, binding_warnings = _resolve_binding_values(
        ctx=ctx,
        frame=frame,
        problem_frame=problem_frame,
        metrics=Metrics(
            values={
                "worker_impact": -2.0,
                "owner_impact": -3.0,
                "nonfinite_metric": "nan",
                "budget": 8,
            }
        ),
        simulation_result=None,
        simulation_result_ref=None,
        distributional_report=None,
    )

    assert set(binding_values) == {"worker_outcome", "owner_outcome"}
    assert binding_warnings == [
        "missing_binding_value:missing_outcome",
        "missing_binding_value:nonfinite_outcome",
    ]

    utilities, utility_warnings = _compute_stakeholder_utilities(
        problem_frame=problem_frame,
        frame=frame,
        binding_values=binding_values,
    )
    utility_by_id = {item.stakeholder_id: item for item in utilities}
    assert utility_warnings == []
    assert utility_by_id["workers"].delta_utility == -2.0
    assert utility_by_id["workers"].welfare_weight == 1.0
    assert utility_by_id["owners"].delta_utility == 6.0
    assert utility_by_id["owners"].welfare_weight == 3.0

    rights_audit, rights_warnings = _audit_rights(
        problem_frame=problem_frame,
        frame=frame,
        binding_values=binding_values,
        utility_summaries=utilities,
    )
    rights_by_id = {item.right_id: item for item in rights_audit}
    assert rights_by_id["worker_non_loss"].status == NormativeAuditStatus.VIOLATED
    assert rights_by_id["owner_soft_target"].status == NormativeAuditStatus.VIOLATED
    assert "soft_right" in rights_by_id["owner_soft_target"].notes
    assert rights_by_id["owner_floor_satisfied"].status == NormativeAuditStatus.SATISFIED
    assert rights_by_id["worker_type_mismatch"].status == NormativeAuditStatus.UNEVALUATED
    assert rights_by_id["worker_type_mismatch"].notes == ["comparison_type_mismatch"]
    assert rights_by_id["missing_right_binding"].status == NormativeAuditStatus.UNEVALUATED
    assert rights_warnings == [
        "unevaluable_right:worker_type_mismatch",
        "missing_right_binding:missing_right_binding",
    ]

    hard_audit, hard_warnings = _audit_hard_constraints(
        problem_frame=problem_frame,
        frame=frame,
        metrics=Metrics(values={"budget": 8}),
    )
    hard_by_id = {item.constraint_id: item for item in hard_audit}
    assert hard_by_id["budget_limit"].status == NormativeAuditStatus.SATISFIED
    assert hard_by_id["missing_metric_limit"].status == NormativeAuditStatus.UNEVALUATED
    assert hard_by_id["missing_metric_limit"].notes == ["proposal_value_missing"]
    assert hard_warnings == ["unevaluable_hard_constraint:missing_metric_limit"]

    completeness = _resolve_model_completeness(
        source="declared",
        warnings=[*binding_warnings, *rights_warnings, *hard_warnings],
        rights_audit=rights_audit,
        hard_constraint_audit=hard_audit,
    )
    assert completeness == NormativeModelCompleteness.PARTIAL

    outcomes = _evaluate_policies(
        frame=frame,
        utility_summaries=utilities,
        rights_audit=rights_audit,
        hard_constraint_audit=hard_audit,
    )
    outcome_by_policy = {item.policy: item for item in outcomes}
    assert outcome_by_policy[NormativeArbitrationPolicy.LEXICOGRAPHIC_RIGHTS].selected_option == (
        ArbitrationOption.BASELINE
    )
    assert outcome_by_policy[NormativeArbitrationPolicy.WEIGHTED_WELFARE].selected_option == (
        ArbitrationOption.PROPOSAL
    )
    assert outcome_by_policy[NormativeArbitrationPolicy.MAX_MIN_HARM].selected_option == (
        ArbitrationOption.BASELINE
    )
    assert outcome_by_policy[NormativeArbitrationPolicy.PARETO_FILTER].selected_option == (
        ArbitrationOption.BASELINE
    )

    soft_only_outcomes = _evaluate_policies(
        frame=frame,
        utility_summaries=utilities,
        rights_audit=[item for item in rights_audit if item.right_id != "worker_non_loss"],
        hard_constraint_audit=[hard_by_id["budget_limit"]],
    )
    soft_only_lexicographic = next(
        item
        for item in soft_only_outcomes
        if item.policy == NormativeArbitrationPolicy.LEXICOGRAPHIC_RIGHTS
    )
    assert soft_only_lexicographic.selected_option == ArbitrationOption.PROPOSAL
