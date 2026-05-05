from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.foundry.methods.catalog.causal.protocols import DynamicTreatmentData
from polisyos.ir.governance.policy_spec import (
    InterventionSpec,
    ParameterSpec,
    PolicySpec,
    TemporalInterventionSequence,
)
from polisyos.ir.governance.problem_frame import ObjectiveSpec, ProblemDomain, ProblemFrame
from polisyos.ir.governance.schedule import ScheduleSpec
from polisyos.ir.governance.selector_expr import SelectorPredicate
from polisyos.ir.kernel.values import MoneyValue
from polisyos.ir.model_spec import AssumptionSpec, AssumptionType, ModelSpec
from polisyos.ir.observation.bundles import StrategicResponseSpec
from polisyos.ir.observation.contract_compilers import (
    DynamicTreatmentCompileSpec,
    ObservationContractCompilerSuite,
)
from polisyos.ir.observation.contracts import (
    EntityScope,
    IdentificationMode,
    ObservationFamily,
    ObservationPanel,
    ObservationRecord,
    SourceConfidenceTier,
    StrategicResponseChannel,
)
from polisyos.ir.trinity import TrinityBundle
from polisyos.ir.types import OptimizationDirection, SelectorOperator, TimeFrequency
from polisyos.lex import (
    HierarchicalPolicySearchAdapter,
    InterventionKnobSpec,
    LexInterventionCompiler,
    LexPolicyBundleInput,
    LexProvisionDirective,
    StrategicResponseRegistryEntry,
    StrategicResponseSpecRegistry,
    TemporalInterventionSequenceCompiler,
    TemporalInterventionSequencer,
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


def test_lex_intervention_compiler_maps_provision_ref_to_knob_and_parameter() -> None:
    compiler = LexInterventionCompiler()

    compiled = compiler.compile(
        LexProvisionDirective(
            provision_ref="ua.procurement.thresholds.art12",
            intervention_id="proc_threshold_change",
            intervention_kind="procurement_threshold_change",
            target=_selector(),
            schedule=ScheduleSpec(start_step=1, duration_steps=2),
            params={"threshold": Decimal("500000")},
            knobs=[
                InterventionKnobSpec(
                    param_id="proc_threshold_knob",
                    param_path="params.threshold",
                    default_value=Decimal("500000"),
                    min_value=Decimal("100000"),
                    max_value=Decimal("1000000"),
                )
            ],
            identification_mode=IdentificationMode.INTERFERENCE_AWARE,
            strategic_response_expected=True,
            transmission_channels=[
                StrategicResponseChannel.PROCUREMENT_CHANNEL,
                StrategicResponseChannel.COMPLIANCE_CHANNEL,
            ],
        )
    )

    assert compiled.intervention.lex_provision_ref == "ua.procurement.thresholds.art12"
    assert compiled.intervention.identification_mode is IdentificationMode.INTERFERENCE_AWARE
    assert compiled.intervention.transmission_channels == [
        StrategicResponseChannel.PROCUREMENT_CHANNEL,
        StrategicResponseChannel.COMPLIANCE_CHANNEL,
    ]
    assert compiled.parameters[0].param_id == "proc_threshold_knob"
    assert compiled.parameters[0].param_path == "params.threshold"
    assert compiled.metadata["provision_ref"] == "ua.procurement.thresholds.art12"
    assert compiled.metadata["knob_ids"] == ["proc_threshold_knob"]


def test_lex_intervention_compiler_rejects_unknown_param_path() -> None:
    compiler = LexInterventionCompiler()

    with pytest.raises(
        ValueError,
        match="references unknown intervention param",
    ):
        compiler.compile(
            LexProvisionDirective(
                provision_ref="ua.procurement.thresholds.art12",
                intervention_id="proc_threshold_change",
                intervention_kind="procurement_threshold_change",
                target=_selector(),
                schedule=ScheduleSpec(start_step=1, duration_steps=2),
                params={"threshold": Decimal("500000")},
                knobs=[
                    InterventionKnobSpec(
                        param_id="proc_threshold_knob",
                        param_path="params.missing_threshold",
                        default_value=Decimal("500000"),
                    )
                ],
            )
        )


def test_lex_intervention_compiler_rejects_inverted_bounds() -> None:
    compiler = LexInterventionCompiler()

    with pytest.raises(ValueError, match="inverted bounds"):
        compiler.compile(
            LexProvisionDirective(
                provision_ref="ua.procurement.thresholds.art12",
                intervention_id="proc_threshold_change",
                intervention_kind="procurement_threshold_change",
                target=_selector(),
                schedule=ScheduleSpec(start_step=1, duration_steps=2),
                params={"threshold": Decimal("500000")},
                knobs=[
                    InterventionKnobSpec(
                        param_id="proc_threshold_knob",
                        param_path="params.threshold",
                        default_value=Decimal("500000"),
                        min_value=Decimal("1000000"),
                        max_value=Decimal("100000"),
                    )
                ],
            )
        )


def test_lex_provision_directive_requires_channels_when_strategic_response_expected() -> None:
    with pytest.raises(ValueError, match="transmission_channels are required"):
        LexProvisionDirective(
            provision_ref="ua.procurement.thresholds.art12",
            intervention_id="proc_threshold_change",
            intervention_kind="procurement_threshold_change",
            target=_selector(),
            schedule=ScheduleSpec(start_step=1, duration_steps=2),
            strategic_response_expected=True,
        )


def test_temporal_intervention_sequencer_builds_valid_dynamic_treatment_data() -> None:
    sequencer = TemporalInterventionSequencer()
    sequence = sequencer.compile_sequence(
        sequence_id="ua_wage_support_sequence",
        dynamic_intervention_id="dynamic_wage_support",
        strategic_response_expected=True,
        transmission_channels=[StrategicResponseChannel.LABOR_CHANNEL],
        steps=[
            {"effective_date": "2022-01", "intervention_id": "wage_support_launch"},
            {"effective_date": "2022-06", "intervention_id": "wage_support_expand"},
            {"effective_date": "2023-01", "intervention_id": "wage_support_taper"},
        ],
    )

    dynamic = sequencer.to_dynamic_treatment(sequence, n_units=12)

    assert dynamic.treatment_sequence.shape == (12, 4)
    assert dynamic.covariate_sequence.shape == (12, 4, 2)
    assert dynamic.time_ids.tolist() == ["baseline", "2022-01", "2022-06", "2023-01"]
    assert dynamic.treatment_sequence[:, 0].sum() == 0
    assert dynamic.treatment_sequence[:, 1:].min() == 1
    assert dynamic.metadata["dynamic_intervention_id"] == "dynamic_wage_support"
    assert dynamic.metadata["data_origin"] == "c6a_synthetic_scaffold"
    assert dynamic.metadata["identification_mode"] == "sequential"
    assert dynamic.metadata["transmission_channels"] == ["labor_channel"]


def test_temporal_intervention_sequencer_rejects_unknown_override_param() -> None:
    compiler = LexInterventionCompiler()
    compiled = compiler.compile(
        LexProvisionDirective(
            provision_ref="ua.procurement.thresholds.art12",
            intervention_id="proc_threshold_change",
            intervention_kind="procurement_threshold_change",
            target=_selector(),
            schedule=ScheduleSpec(start_step=1, duration_steps=2),
            params={"threshold": Decimal("500000")},
            knobs=[
                InterventionKnobSpec(
                    param_id="proc_threshold_knob",
                    param_path="params.threshold",
                    default_value=Decimal("500000"),
                )
            ],
        )
    )
    sequencer = TemporalInterventionSequencer()

    with pytest.raises(ValueError, match="unknown parameter_overrides"):
        sequencer.compile_sequence(
            sequence_id="ua_proc_sequence",
            dynamic_intervention_id="dynamic_proc_threshold",
            compiled_interventions=[compiled],
            steps=[
                {
                    "effective_date": "2022-01",
                    "intervention_id": "proc_threshold_change",
                    "parameter_overrides": {"unknown_param": Decimal("1")},
                }
            ],
        )


def test_temporal_intervention_sequencer_rejects_short_time_ids() -> None:
    sequencer = TemporalInterventionSequencer()
    sequence = TemporalInterventionSequence(
        sequence_id="ua_wage_support_sequence",
        dynamic_intervention_id="dynamic_wage_support",
        steps=[
            {
                "step_id": "step_1",
                "effective_date": "2022-01",
                "intervention_id": "wage_support_launch",
            },
            {
                "step_id": "step_2",
                "effective_date": "2022-06",
                "intervention_id": "wage_support_expand",
            },
            {
                "step_id": "step_3",
                "effective_date": "2023-01",
                "intervention_id": "wage_support_taper",
            },
        ],
    )

    with pytest.raises(ValueError, match="at least 4 periods"):
        sequencer.to_dynamic_treatment(
            sequence,
            n_units=12,
            time_ids=["baseline", "2022-01", "2022-06"],
        )


def test_strategic_response_spec_registry_returns_channels_and_hook_config() -> None:
    registry = StrategicResponseSpecRegistry(
        [
            StrategicResponseRegistryEntry(
                spec=StrategicResponseSpec(
                    intervention_kind="procurement_threshold_change",
                    channels=[StrategicResponseChannel.PROCUREMENT_CHANNEL],
                ),
                expected_response_type="equilibrium_shift",
                hook_config={"solver": "stackelberg_exact"},
            )
        ]
    )

    entry = registry.require("procurement_threshold_change")

    assert registry.channels_for("procurement_threshold_change") == (
        StrategicResponseChannel.PROCUREMENT_CHANNEL,
    )
    assert entry.expected_response_type == "equilibrium_shift"
    assert entry.hook_config == {"solver": "stackelberg_exact"}
    assert registry.hook_fqn_for("procurement_threshold_change") == entry.spec.hook_fqn
    assert (
        registry.expected_response_type_for("procurement_threshold_change") == "equilibrium_shift"
    )
    assert registry.strategic_required_for("procurement_threshold_change") is True
    bundle = registry.bundle()
    assert bundle.expectations[0].intervention_kind == "procurement_threshold_change"
    round_trip = StrategicResponseSpecRegistry.from_bundle(bundle)
    assert round_trip.channels_for("procurement_threshold_change") == (
        StrategicResponseChannel.PROCUREMENT_CHANNEL,
    )


def test_strategic_response_spec_registry_rejects_duplicate_intervention_kind() -> None:
    entry = StrategicResponseRegistryEntry(
        spec=StrategicResponseSpec(
            intervention_kind="procurement_threshold_change",
            channels=[StrategicResponseChannel.PROCUREMENT_CHANNEL],
        )
    )

    with pytest.raises(ValueError, match="duplicate strategic response spec"):
        StrategicResponseSpecRegistry([entry, entry])


def test_hierarchical_policy_search_adapter_validates_against_policy_design_api() -> None:
    adapter = HierarchicalPolicySearchAdapter()
    compiler = LexInterventionCompiler()
    compiled = compiler.compile(
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

    assert (
        plan.coordinator_fqn
        == "polisyos.scientist.policy_design.search.HierarchicalSearchCoordinator"
    )
    assert plan.search_config["max_structure_candidates"] == 3
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


def _period(month: int) -> tuple[date, date]:
    return date(2024, month, 1), date(2024, month, 28)


def _dynamic_treatment_panel(n_units: int = 24, n_periods: int = 4) -> ObservationPanel:
    records: list[ObservationRecord] = []
    for unit_idx in range(n_units):
        unit_id = f"hh_{unit_idx:02d}"
        base_cov = 1.0 + unit_idx / 10.0
        for period_idx in range(n_periods):
            period_start, period_end = _period(period_idx + 1)
            treated = 1.0 if unit_idx % 2 == 0 and period_idx >= 1 else 0.0
            outcome = 2.0 + 0.5 * treated + 0.2 * period_idx + 0.05 * unit_idx
            metrics = {
                "outcome_score": outcome,
                "treatment": treated,
                "cov_a": base_cov,
                "cov_b": base_cov + period_idx / 10.0,
            }
            for metric_id, value in metrics.items():
                records.append(
                    ObservationRecord(
                        observation_id=f"obs_{unit_id}_{metric_id}_{period_idx}",
                        family=ObservationFamily.HOUSEHOLD_DISTRIBUTION,
                        time_grain=TimeFrequency.MONTH,
                        period_start=period_start,
                        period_end=period_end,
                        entity_scope=EntityScope.HOUSEHOLD,
                        entity_id=unit_id,
                        metric_id=metric_id,
                        observed_value=value,
                        unit="value",
                        coverage_estimate=0.95,
                        measurement_bias_flag=False,
                        censoring_mask=False,
                        trust_weight=1.0,
                        lag_days_estimate=1,
                        source_id="synthetic_dynamic_panel",
                        source_version="1.0",
                        regime_id="ua_2024",
                        shock_mask=False,
                        schema_regime_id="schema_v1",
                        identification_mode=IdentificationMode.SEQUENTIAL,
                        source_confidence_tier=SourceConfidenceTier.VALIDATED,
                    )
                )
    return ObservationPanel(
        panel_id="synthetic_dynamic_panel",
        family=ObservationFamily.HOUSEHOLD_DISTRIBUTION,
        time_grain=TimeFrequency.MONTH,
        records=records,
    )


def _direct_dynamic_treatment_data() -> DynamicTreatmentData:
    outcome = [1.0 + (idx % 4) for idx in range(24)]
    treatment_sequence = [
        [0, 1, 1],
        [0, 0, 1],
        [0, 1, 1],
        [0, 0, 1],
    ] * 6
    covariate_sequence = [
        [[0.1, 0.2], [0.2, 0.3], [0.3, 0.4]],
        [[0.5, 0.2], [0.6, 0.3], [0.7, 0.4]],
        [[0.2, 0.1], [0.3, 0.2], [0.4, 0.3]],
        [[0.8, 0.4], [0.9, 0.5], [1.0, 0.6]],
    ] * 6
    return DynamicTreatmentData(
        outcome=outcome,
        treatment_sequence=treatment_sequence,
        covariate_sequence=covariate_sequence,
        time_ids=["baseline", "step_1", "step_2"],
        variable_names=["cov_a", "cov_b"],
    )


def test_temporal_intervention_sequence_compiler_runs_three_step_sequence_and_returns_dtr_result(
    tmp_path,
) -> None:
    compiler = TemporalInterventionSequenceCompiler(store=FileSystemCAS(tmp_path))

    result = compiler.compile(
        {
            "task_id": "temporal_sequence_task",
            "sequence_id": "ua_wage_support_sequence",
            "dynamic_intervention_id": "dynamic_wage_support",
            "steps": [
                {"effective_date": "2022-01", "intervention_id": "wage_support_launch"},
                {"effective_date": "2022-06", "intervention_id": "wage_support_expand"},
                {"effective_date": "2023-01", "intervention_id": "wage_support_taper"},
            ],
            "n_units": 24,
            "params": {"n_bootstrap": 20},
        }
    )

    assert result.dynamic_treatment_data.treatment_sequence.shape == (24, 4)
    assert result.dtr_result is not None
    assert result.dtr_result.n_stages == 4
    assert result.entry.status == "ok"
    assert result.entry.dynamic_treatment_regime_ref is not None


def test_temporal_intervention_sequence_compiler_accepts_direct_dynamic_data_and_method_override(
    tmp_path,
) -> None:
    compiler = TemporalInterventionSequenceCompiler(store=FileSystemCAS(tmp_path))

    result = compiler.compile(
        {
            "task_id": "temporal_direct_task",
            "dynamic_treatment_data": _direct_dynamic_treatment_data().model_dump(mode="json"),
            "dtr_method": "a_learning",
            "params": {"n_bootstrap": 20},
        }
    )

    assert result.dtr_result is not None
    assert result.dtr_result.method == "a_learning"
    assert result.entry.metadata["source_precedence"] == "dynamic_treatment_data"
    assert result.entry.dynamic_treatment_regime_ref is not None


def test_c3_dynamic_treatment_artifact_flows_into_temporal_compiler(tmp_path) -> None:
    suite = ObservationContractCompilerSuite()
    compiled = suite.compile_all(
        observation_panel=_dynamic_treatment_panel(),
        dynamic_treatment_spec=DynamicTreatmentCompileSpec(
            spec_id="dynamic_treatment_spec",
            outcome_metric_id="outcome_score",
            treatment_metric_id="treatment",
            covariate_metric_ids=["cov_a", "cov_b"],
        ),
    )
    artifact = compiled.artifacts["dynamic_treatment_data"]
    compiler = TemporalInterventionSequenceCompiler(store=FileSystemCAS(tmp_path))

    result = compiler.compile(
        {
            "task_id": "compiled_dynamic_task",
            "bundle_manifest": artifact.bundle.model_dump(mode="json"),
            "params": {"n_bootstrap": 20},
        }
    )

    assert result.entry.status == "ok"
    assert result.dtr_result is not None
    assert result.entry.dynamic_treatment_regime_ref is not None
