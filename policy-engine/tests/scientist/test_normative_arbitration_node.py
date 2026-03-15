from __future__ import annotations

import logging

import pytest

from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.ir.analytics.distributional import (
    CohortDimension,
    CohortImpact,
    DimensionBreakdown,
    DistributionalReport,
    ImpactDirection,
    MetricUnit,
    WinnersLosersEntry,
    WinnersLosersTable,
    persist_distributional_report,
)
from polisyos.ir.analytics.normative_arbitration import (
    ArbitrationOption,
    load_normative_arbitration_result,
)
from polisyos.ir.governance.policy_spec import PolicySpec
from polisyos.ir.governance.problem_frame import (
    NormativeArbitrationPolicy,
    NormativeFrame,
    ObjectiveSpec,
    ProblemDomain,
    ProblemFrame,
    StakeholderOutcomeBinding,
    StakeholderRightSpec,
    StakeholderSpec,
    StakeholderUtilityTerm,
)
from polisyos.ir.model_spec import FidelityLevel, ModelSpec
from polisyos.ir.trinity import TrinityBundle
from polisyos.ir.types import EntityType, OptimizationDirection
from polisyos.scientist.engine.context import ExecutionContext
from polisyos.scientist.engine.state import ExperimentState
from polisyos.scientist.nodes.builtins.governance.run_normative_arbitration import (
    RunNormativeArbitrationNode,
)
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_DISTRIBUTIONAL_REPORT_REF,
    ARTIFACT_NORMATIVE_ARBITRATION_RESULT_REF,
    INPUT_TRINITY_BUNDLE_REF,
)


def test_normative_arbitration_rights_policy_blocks_proposal(tmp_path) -> None:
    result = _run_node(
        tmp_path=tmp_path,
        policy=NormativeArbitrationPolicy.LEXICOGRAPHIC_RIGHTS,
        impacts={"workers": -2.0, "owners": 1.5},
        with_right=True,
    )

    assert result.selected_option == ArbitrationOption.BASELINE
    assert any(item.status.value == "violated" for item in result.rights_audit)


def test_normative_arbitration_weighted_welfare_prefers_proposal(tmp_path) -> None:
    result = _run_node(
        tmp_path=tmp_path,
        policy=NormativeArbitrationPolicy.WEIGHTED_WELFARE,
        impacts={"workers": 1.0, "owners": 2.0},
    )

    assert result.selected_option == ArbitrationOption.PROPOSAL


def test_normative_arbitration_max_min_prefers_baseline_when_worst_harm_increases(tmp_path) -> None:
    result = _run_node(
        tmp_path=tmp_path,
        policy=NormativeArbitrationPolicy.MAX_MIN_HARM,
        impacts={"workers": -1.0, "owners": 4.0},
    )

    assert result.selected_option == ArbitrationOption.BASELINE


def test_normative_arbitration_pareto_marks_proposal_inadmissible_with_loser(tmp_path) -> None:
    result = _run_node(
        tmp_path=tmp_path,
        policy=NormativeArbitrationPolicy.PARETO_FILTER,
        impacts={"workers": -0.2, "owners": 1.0},
    )

    assert result.selected_option == ArbitrationOption.BASELINE
    pareto_outcome = next(
        item for item in result.policy_outcomes if item.policy == NormativeArbitrationPolicy.PARETO_FILTER
    )
    assert pareto_outcome.selected_option == ArbitrationOption.BASELINE


@pytest.mark.parametrize("execution_profile", ["governed", "production"])
def test_normative_arbitration_requires_explicit_frame_for_serious_profiles(
    tmp_path,
    execution_profile: str,
) -> None:
    outcome, _ = _execute_node(
        tmp_path=tmp_path,
        policy=NormativeArbitrationPolicy.WEIGHTED_WELFARE,
        impacts={"workers": 1.0, "owners": 2.0},
        include_normative_frame=False,
        execution_profile=execution_profile,
    )

    assert outcome.status == "fail"
    assert outcome.error is not None
    assert outcome.error.code == "node.invalid_state"
    assert outcome.error.details["execution_profile"] == execution_profile


def _run_node(
    *,
    tmp_path,
    policy: NormativeArbitrationPolicy,
    impacts: dict[str, float],
    with_right: bool = False,
    include_normative_frame: bool = True,
    execution_profile: str | None = None,
):
    outcome, store = _execute_node(
        tmp_path=tmp_path,
        policy=policy,
        impacts=impacts,
        with_right=with_right,
        include_normative_frame=include_normative_frame,
        execution_profile=execution_profile,
    )
    result_ref = outcome.state.artifacts_index[ARTIFACT_NORMATIVE_ARBITRATION_RESULT_REF]
    return load_normative_arbitration_result(store, result_ref)


def _execute_node(
    *,
    tmp_path,
    policy: NormativeArbitrationPolicy,
    impacts: dict[str, float],
    with_right: bool = False,
    include_normative_frame: bool = True,
    execution_profile: str | None = None,
):
    store = FileSystemCAS(tmp_path)
    registry_bundle = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(store=store, registry_bundle=registry_bundle, run_id="R_normative")
    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger("test.normative"))

    stakeholders = [
        StakeholderSpec(stakeholder_id="workers", entity_type=EntityType.AGENT, priority=3),
        StakeholderSpec(stakeholder_id="owners", entity_type=EntityType.AGENT, priority=2),
    ]
    bindings = [
        StakeholderOutcomeBinding(
            binding_id="workers_delta",
            stakeholder_id="workers",
            channel="distributional_net_impact",
            outcome_key="workers",
        ),
        StakeholderOutcomeBinding(
            binding_id="owners_delta",
            stakeholder_id="owners",
            channel="distributional_net_impact",
            outcome_key="owners",
        ),
    ]
    rights = []
    if with_right:
        rights.append(
            StakeholderRightSpec(
                right_id="workers_non_loss",
                stakeholder_id="workers",
                binding_ref="workers_delta",
                operator=">=",
                threshold=0,
            )
        )

    normative_frame = (
        NormativeFrame(
            default_policy=policy,
            enabled_policies=[
                NormativeArbitrationPolicy.LEXICOGRAPHIC_RIGHTS,
                NormativeArbitrationPolicy.WEIGHTED_WELFARE,
                NormativeArbitrationPolicy.MAX_MIN_HARM,
                NormativeArbitrationPolicy.PARETO_FILTER,
            ],
            stakeholder_bindings=bindings,
            utility_terms=[
                StakeholderUtilityTerm(
                    term_id="workers_utility",
                    stakeholder_id="workers",
                    binding_refs=["workers_delta"],
                    welfare_weight=2,
                ),
                StakeholderUtilityTerm(
                    term_id="owners_utility",
                    stakeholder_id="owners",
                    binding_refs=["owners_delta"],
                    welfare_weight=1,
                ),
            ],
            rights_catalog=rights,
        )
        if include_normative_frame
        else None
    )

    problem_frame = ProblemFrame(
        problem_id="normative_problem",
        domain=ProblemDomain.SOCIAL,
        objectives=[
            ObjectiveSpec(
                objective_id="obj1",
                metric_id="net_welfare",
                direction=OptimizationDirection.MAXIMIZE,
            )
        ],
        stakeholders=stakeholders,
        normative_frame=normative_frame,
    )
    trinity_ref = store.put_json(
        TrinityBundle(
            problem_frame=problem_frame,
            policy_spec=PolicySpec(policy_id="policy", interventions=[]),
            model_spec=ModelSpec(
                model_id="model",
                data_snapshot_ref="sha256:" + "0" * 64,
                fidelity_level=FidelityLevel.HYBRID,
            ),
        ),
        PutOptions(
            kind="ir.trinity_bundle",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.ir.TrinityBundle", version="1.0"),
        ),
    )

    distributional_ref = persist_distributional_report(store, _build_distributional_report(impacts))
    state = ExperimentState(
        run_id="R_normative",
        inputs={INPUT_TRINITY_BUNDLE_REF: trinity_ref},
        artifacts_index={ARTIFACT_DISTRIBUTIONAL_REPORT_REF: distributional_ref},
        execution_profile=execution_profile,
    )

    return RunNormativeArbitrationNode().execute(ctx, state), store


def _build_distributional_report(impacts: dict[str, float]) -> DistributionalReport:
    winners: list[WinnersLosersEntry] = []
    losers: list[WinnersLosersEntry] = []
    cohorts: list[CohortImpact] = []
    for cohort_id, delta in impacts.items():
        direction = ImpactDirection.POSITIVE if delta > 0 else ImpactDirection.NEGATIVE
        entry = WinnersLosersEntry(
            cohort_id=cohort_id,
            cohort_label=cohort_id,
            dimension=CohortDimension.CUSTOM,
            net_impact=delta,
            impact_direction=direction,
            population_share=0.5,
            key_metric="net_income_pct",
            key_metric_delta=delta,
        )
        if delta > 0:
            winners.append(entry)
        else:
            losers.append(entry)
        cohorts.append(
            CohortImpact(
                cohort_id=cohort_id,
                cohort_label=cohort_id,
                population_share=0.5,
                metric_deltas={"net_income_pct": delta},
                impact_direction=direction,
                is_vulnerable=cohort_id == "workers",
            )
        )
    return DistributionalReport(
        breakdowns=[
            DimensionBreakdown(
                dimension=CohortDimension.CUSTOM,
                dimension_label="Stakeholders",
                primary_metric="net_income_pct",
                primary_metric_unit=MetricUnit.PERCENT,
                cohorts=cohorts,
            )
        ],
        winners_losers=WinnersLosersTable(winners=winners, losers=losers, neutral=[]),
    )
