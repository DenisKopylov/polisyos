"""Verify selected comparable measurement pooling on the stock backtest path."""

from __future__ import annotations

import math
from decimal import Decimal, localcontext
from fractions import Fraction
from typing import TYPE_CHECKING, Any

import pytest

from polisyos.core.artifacts import (
    ArtifactRef,
    FileSystemCAS,
    PutOptions,
    SchemaInfo,
    ensure_ir_artifact_store,
    input_ref_from_artifact_ref,
)
from polisyos.core.contracts.variable_binding import (
    SelectedVariableBindingRef,
    VariableRepresentation,
    VariableRepresentationRef,
    VariableSemanticDefinition,
    VariableSemanticDefinitionRef,
    variable_representation_manifest_inputs,
)
from polisyos.core.registry.builder import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.ir.analytics.backtest import (
    BacktestPoolingVerificationRequiredError,
    NativeBacktestVerificationRequiredError,
    load_backtest_report,
    load_backtest_report_candidate,
    persist_backtest_report,
    summarize_backtest_errors,
)
from polisyos.ir.analytics.backtest_pooling import (
    BacktestPoolingMember,
    BacktestPoolingPolicy,
    SelectedHistoricalRowsRef,
    SelectedRepresentationRef,
    _converted_residual,
    load_backtest_pooling_policy,
    persist_backtest_pooling_policy,
    pooling_policy_edge,
    project_backtest_pooling,
    read_selected_inputs,
)
from polisyos.ir.artifacts import put_json_artifact
from polisyos.ir.kernel.units import MoneyUnit
from polisyos.ir.model_layer.canon import CanonSpec
from polisyos.ir.observation.contract_compilers import (
    HistoricalValidationCompileSpec,
    HistoricalValidationPlanCompiler,
)
from polisyos.ir.registry.refs import BacktestReportRef
from polisyos.scientist.governance.backtest_matrix import BacktestKind, BacktestMatrixRunner
from polisyos.scientist.methods.backtesting.evaluator import PredictionEvaluator
from polisyos.scientist.methods.backtesting.native_replay import (
    load_backtest_report_for_consumption,
)
from polisyos.scientist.methods.backtesting.orchestrator import BacktestOrchestrator
from polisyos.scientist.methods.backtesting.plan import (
    HistoricalReplaySourceSelection,
    HistoricalValidationPlan,
    PredictionSource,
)
from polisyos.scientist.methods.backtesting.pooling import (
    BacktestPoolingRunSelectionRequiredError,
    SelectedBacktestPoolingRun,
)
from tests.unit.ir.observation.test_contract_compilers import _observation_panel

if TYPE_CHECKING:
    from pathlib import Path


def test_normalization_preserves_representable_residual_and_refuses_underflow() -> None:
    predicted = 1e308
    observed = math.nextafter(predicted, 0.0)
    with localcontext() as context:
        context.prec = 340
        expected = float((Decimal(predicted) - Decimal(observed)) * Decimal(100))
    assert _converted_residual(predicted, observed, Fraction(100)) == expected
    with pytest.raises(OverflowError, match="normalized backtest residual underflow"):
        _converted_residual(math.nextafter(0.0, 1.0), 0.0, Fraction(1, 100))


def _start_run(store: FileSystemCAS) -> RunContext:
    registry = build_default_registry_bundle(store, return_selected_profile=True)
    return RunContext.start(store, registry.bundle_ref)


def _finalize_run(context: RunContext) -> SelectedBacktestPoolingRun:
    path = context.trace_path
    assert path is not None
    return SelectedBacktestPoolingRun(
        run_dir=path.parent, run_id=context.run_manifest.run_id, terminal_ref=context.finalize()
    )


def _definition(store: FileSystemCAS, name: str) -> VariableSemanticDefinitionRef:
    evidence = store.put_bytes(
        name.encode(),
        PutOptions(kind="test.comparison_protocol", media_type="text/plain"),
        return_selected_profile=True,
    )
    definition = VariableSemanticDefinition(
        namespace="benchmark",
        stable_id=name,
        revision="1",
        meaning=f"Observed {name} under the fixed benchmark protocol",
        definition_evidence_refs=(
            SelectedVariableBindingRef.model_validate(evidence.model_dump()),
        ),
    )
    ref = store.put_json(
        definition,
        PutOptions(
            kind=definition.ARTIFACT_KIND,
            media_type=definition.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(
                name=definition.ARTIFACT_SCHEMA_NAME, version=definition.ARTIFACT_SCHEMA_VERSION
            ),
            inputs=[input_ref_from_artifact_ref(evidence, role="definition_evidence")],
        ),
        return_selected_profile=True,
    )
    return VariableSemanticDefinitionRef.model_validate(ref.model_dump())


def _representation(
    store: FileSystemCAS,
    name: str,
    definition: VariableSemanticDefinitionRef,
    unit: str,
    *,
    money_unit: MoneyUnit | None = None,
) -> VariableRepresentationRef:
    value = VariableRepresentation(
        schema_version="polisyos.catalog.variable_representation.v3",
        representation_id=name,
        revision="1",
        semantic_definition_ref=definition,
        quantity_kind="outcome",
        measure_form="absolute",
        unit_id=unit,
        scale_to_unit=Decimal(1),
        time_support="period_average",
        temporal_granularity="annual",
        aggregation="mean",
        grain=("year", "sample"),
        population_ref="benchmark:selected-sample",
        money_unit=money_unit,
    )
    ref = store.put_json(
        value,
        PutOptions(
            kind=value.ARTIFACT_KIND,
            media_type=value.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(name=value.ARTIFACT_SCHEMA_NAME, version="3.0"),
            inputs=list(variable_representation_manifest_inputs(value)),
        ),
        return_selected_profile=True,
    )
    return VariableRepresentationRef.model_validate(ref.model_dump())


def _history(
    store: FileSystemCAS,
    metric: str,
    baseline: float,
    representation: VariableRepresentationRef | None,
) -> ArtifactRef:
    return store.put_json(
        {metric: [baseline] * 3, "time_index": ["2010", "2011", "2012"]},
        PutOptions(
            kind="test.selected_benchmark_series",
            media_type="application/json",
            inputs=(
                [input_ref_from_artifact_ref(representation, role=f"measurement:{metric}")]
                if representation
                else []
            ),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )


def _case(
    name: str,
    metric: str,
    historical: ArtifactRef,
    raw: VariableRepresentationRef | None,
    canonical: VariableRepresentationRef | None,
    *,
    actual: float,
    predictions: tuple[float, ...],
    group: str | None = None,
    weight: str = "1",
    start: int = 1,
) -> tuple[HistoricalValidationPlan, BacktestPoolingMember]:
    return (
        HistoricalValidationPlan(
            plan_id=name,
            prediction_source=PredictionSource.PROVIDED,
            historical_replay_source=HistoricalReplaySourceSelection(source_data_ref=historical),
            target_metrics=[metric],
            ground_truth_outcomes={metric: [actual] * len(predictions)},
            predicted_outcomes={metric: list(predictions)},
            intervention_step=start,
        ),
        BacktestPoolingMember(
            scenario_id=name,
            metric_name=metric,
            scenario_group=group or name,
            macro_weight=Decimal(weight),
            historical_rows_ref=SelectedHistoricalRowsRef.model_validate(historical.model_dump()),
            observation_start=start,
            predictions=predictions,
            comparison_representation_ref=(
                SelectedRepresentationRef.model_validate(raw.model_dump()) if raw else None
            ),
            canonical_representation_ref=(
                SelectedRepresentationRef.model_validate(canonical.model_dump())
                if canonical
                else None
            ),
        ),
    )


def test_declared_units_and_weights_replay_and_hold_across_shards(tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    ir_store = ensure_ir_artifact_store(store)
    quantity = _definition(store, "distance")
    metres = _representation(store, "distance_metres", quantity, "m")
    centimetres = _representation(store, "distance_centimetres", quantity, "cm")
    m_series = _history(store, "length", 10.0, metres)
    cm_series = _history(store, "distance", 1000.0, centimetres)
    case_m = _case(
        "site_m",
        "length",
        m_series,
        metres,
        metres,
        actual=10.0,
        predictions=(11.0, 12.0),
        weight="0.25",
    )
    case_cm = _case(
        "site_cm",
        "distance",
        cm_series,
        centimetres,
        metres,
        actual=1000.0,
        predictions=(1300.0, 1400.0),
        group="site_cm",
        weight="0.75",
    )
    expected_micro = math.sqrt(30 / 4)
    expected_macro = 0.25 * math.sqrt(5 / 2) + 0.75 * math.sqrt(25 / 2)
    reports = []
    for cases in (
        [case_m, case_cm],
        [
            case_m,
            _case(
                "site_cm_1",
                "distance",
                cm_series,
                centimetres,
                metres,
                actual=1000.0,
                predictions=(1300.0,),
                group="site_cm",
                weight="0.75",
            ),
            _case(
                "site_cm_2",
                "distance",
                cm_series,
                centimetres,
                metres,
                actual=1000.0,
                predictions=(1400.0,),
                group="site_cm",
                weight="0.75",
                start=2,
            ),
        ],
    ):
        plans, members = zip(*cases, strict=True)
        policy = persist_backtest_pooling_policy(ir_store, BacktestPoolingPolicy(members=members))
        context = _start_run(store)
        report, ref = BacktestOrchestrator(cas=store).run_with_ref(
            list(plans), pooling_policy_ref=policy, pooling_run_context=context
        )
        run = _finalize_run(context)
        fresh = FileSystemCAS.open_existing_read_only(store.root)
        loaded = load_backtest_report_for_consumption(fresh, ref, pooling_run=run)
        assert pooling_policy_edge(policy) in read_selected_inputs(
            ensure_ir_artifact_store(fresh), ref
        )
        assert loaded.pooling == report.pooling
        assert loaded.pooling is not None
        assert loaded.pooling.measures[1].transform is not None
        assert loaded.pooling.measures[1].transform.multiplier == Decimal("0.01")
        stratum = loaded.pooling.strata[0]
        assert dict(stratum.semantic_definition_ref) == quantity.model_dump(mode="json")
        assert stratum.comparison_count == 4
        assert loaded.overall_rmse == pytest.approx(expected_micro)
        assert loaded.overall_mae == 2.5
        assert loaded.overall_macro_rmse == pytest.approx(expected_macro)
        assert not loaded.trust_eligible
        reports.append((loaded, ref, run))
    assert reports[0][0].overall_rmse == reports[1][0].overall_rmse
    assert reports[0][0].overall_macro_rmse == reports[1][0].overall_macro_rmse

    report, ref, run = reports[0]
    assert report.pooling is not None
    with pytest.raises(BacktestPoolingVerificationRequiredError):
        load_backtest_report(ir_store, ref)
    with pytest.raises(BacktestPoolingRunSelectionRequiredError):
        load_backtest_report_for_consumption(FileSystemCAS.open_existing_read_only(store.root), ref)
    with pytest.raises(ValueError, match="requires an exact selected report profile"):
        load_backtest_report_for_consumption(
            FileSystemCAS.open_existing_read_only(store.root),
            ref.model_copy(update={"manifest_profile_sha256": None}),
        )
    with pytest.raises(ValueError, match="pooling policy manifest binding"):
        persist_backtest_report(ir_store, report)

    other = reports[1][0].pooling
    assert other is not None
    foreign = BacktestReportRef.model_validate(
        put_json_artifact(
            ir_store,
            report.model_dump(mode="json"),
            kind="ir.backtest_report",
            schema_name="ir.backtest_report",
            schema_version="1.0",
            canon_spec=CanonSpec(forbid_floats=False),
            inputs=[pooling_policy_edge(other.policy_ref)],
            return_selected_profile=True,
        )
    )
    assert foreign.artifact_id == ref.artifact_id
    assert foreign.manifest_profile_sha256 != ref.manifest_profile_sha256
    with pytest.raises(ValueError, match="pooling policy manifest binding"):
        load_backtest_report_for_consumption(
            FileSystemCAS.open_existing_read_only(store.root), foreign
        )

    source = report.scenarios[0]
    native_marker = source.model_copy(
        update={"metadata": {**source.metadata, "native_workflow_status": "ok"}}
    )
    native_claim = report.model_copy(update={"scenarios": [native_marker, *report.scenarios[1:]]})
    native_claim_ref = persist_backtest_report(
        ir_store, native_claim, inputs=[pooling_policy_edge(report.pooling.policy_ref)]
    )
    with pytest.raises(NativeBacktestVerificationRequiredError):
        load_backtest_report(ir_store, native_claim_ref)
    with pytest.raises(
        ValueError, match="provided backtest pooling cannot claim a native forecast"
    ):
        load_backtest_report_for_consumption(
            FileSystemCAS.open_existing_read_only(store.root), native_claim_ref
        )

    # A different holdout and a correctly recomputed report still disagree with the source.
    bad_truth = PredictionEvaluator().evaluate(
        scenario_id=source.scenario_id,
        scenario_label=source.scenario_label,
        y_pred={"length": [11.0, 12.0]},
        y_true={"length": [9.0, 9.0]},
        jurisdiction=source.jurisdiction,
        intervention_date=source.intervention_date,
        data_source=source.data_source,
        metadata=source.metadata,
    )
    cases = [bad_truth, *report.scenarios[1:]]
    recalculated = project_backtest_pooling(
        report.pooling.policy_ref,
        load_backtest_pooling_policy(ir_store, report.pooling.policy_ref),
        report.pooling.measures,
        cases,
        summarize_backtest_errors,
    )
    combined = recalculated.combined_stratum
    assert combined is not None
    wrong_rows = report.model_copy(
        update={
            "scenarios": cases,
            "pooling": recalculated,
            "overall_rmse": combined.micro_rmse,
            "overall_mae": combined.micro_mae,
            "overall_macro_rmse": combined.weighted_macro_rmse,
        }
    )
    wrong_rows_ref = persist_backtest_report(
        ir_store, wrong_rows, inputs=[pooling_policy_edge(report.pooling.policy_ref)]
    )
    internally_coherent = load_backtest_report_candidate(ir_store, wrong_rows_ref)
    assert internally_coherent.overall_rmse == pytest.approx(math.sqrt(38 / 4))
    assert internally_coherent.scenarios[0].outcome_comparisons[0].y_true == 9.0
    with pytest.raises(ValueError, match="report rows differ from the selected holdout"):
        load_backtest_report_for_consumption(
            FileSystemCAS.open_existing_read_only(store.root), wrong_rows_ref, pooling_run=run
        )

    # A metadata-only factor forgery preserves the stored aggregate and arithmetic.
    measure = report.pooling.measures[1]
    assert measure.transform is not None
    forged_factor = measure.transform.model_copy(
        update={"definition_content_sha256": "sha256:" + "0" * 64}
    )
    forged_measure = measure.model_copy(update={"transform": forged_factor})
    forged_projection = report.pooling.model_copy(
        update={"measures": (report.pooling.measures[0], forged_measure)}
    )
    forged_report = report.model_copy(update={"pooling": forged_projection})
    forged_ref = persist_backtest_report(
        ir_store, forged_report, inputs=[pooling_policy_edge(report.pooling.policy_ref)]
    )
    assert load_backtest_report_candidate(ir_store, forged_ref).overall_rmse == report.overall_rmse
    with pytest.raises(ValueError, match="measurement or applied factor differs"):
        load_backtest_report_for_consumption(
            FileSystemCAS.open_existing_read_only(store.root), forged_ref, pooling_run=run
        )

    payload = report.model_dump(mode="json")
    payload["pooling"]["strata"][0]["micro_rmse"] = 9.0
    payload["overall_rmse"] = 9.0
    tampered = BacktestReportRef.model_validate(
        put_json_artifact(
            ir_store,
            payload,
            kind="ir.backtest_report",
            schema_name="ir.backtest_report",
            schema_version="1.0",
            canon_spec=CanonSpec(forbid_floats=False),
            inputs=[pooling_policy_edge(report.pooling.policy_ref)],
            return_selected_profile=True,
        )
    )
    with pytest.raises(ValueError, match="pooled statistics differ"):
        load_backtest_report_candidate(ir_store, tampered)

    policy = load_backtest_pooling_policy(ir_store, report.pooling.policy_ref)
    adjusted = policy.members[1].model_copy(update={"macro_weight": Decimal("0.25")})
    reweighted_policy = policy.model_copy(update={"members": (policy.members[0], adjusted)})
    reweighted_ref = persist_backtest_pooling_policy(ir_store, reweighted_policy)
    reweighted = project_backtest_pooling(
        reweighted_ref,
        reweighted_policy,
        report.pooling.measures,
        report.scenarios,
        summarize_backtest_errors,
    )
    combined = reweighted.combined_stratum
    assert combined is not None
    assert combined.weighted_macro_rmse != report.overall_macro_rmse
    rewritten = persist_backtest_report(
        ir_store,
        report.model_copy(
            update={"pooling": reweighted, "overall_macro_rmse": combined.weighted_macro_rmse}
        ),
        inputs=[pooling_policy_edge(reweighted_ref)],
    )
    assert load_backtest_report_candidate(ir_store, rewritten).pooling == reweighted
    with pytest.raises(ValueError, match="terminal policy differs"):
        load_backtest_report_for_consumption(
            FileSystemCAS.open_existing_read_only(store.root), rewritten, pooling_run=run
        )

    reversed_run = _start_run(store)
    reversed_run.add_output(ArtifactRef.model_validate(dict(ref)))
    reversed_run.add_input(ArtifactRef.model_validate(dict(report.pooling.policy_ref)))
    reversed_selection = _finalize_run(reversed_run)
    with pytest.raises(ValueError, match="run input and output order differs"):
        load_backtest_report_for_consumption(
            FileSystemCAS.open_existing_read_only(store.root), ref, pooling_run=reversed_selection
        )

    blob, _ = store._paths(centimetres.artifact_id)
    original = blob.read_bytes()
    blob.unlink()
    with pytest.raises((FileNotFoundError, ValueError)):
        load_backtest_report_for_consumption(
            FileSystemCAS.open_existing_read_only(store.root), ref, pooling_run=run
        )
    blob.write_bytes(original)
    restored = load_backtest_report_for_consumption(
        FileSystemCAS.open_existing_read_only(store.root), ref, pooling_run=run
    )
    assert restored.pooling == report.pooling


def test_incompatible_and_unknown_measures_have_separate_useful_summaries(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    ir_store = ensure_ir_artifact_store(store)
    money = _representation(
        store,
        "usd",
        _definition(store, "price"),
        "USD",
        money_unit=MoneyUnit(currency="USD", nominal_year=2010, price_base="nominal"),
    )
    temperature = _representation(store, "deg_c", _definition(store, "temperature"), "degC")
    cases = [
        _case(
            "dollar",
            "price",
            _history(store, "price", 10.0, money),
            money,
            money,
            actual=10.0,
            predictions=(12.0,),
        ),
        _case(
            "temperature",
            "heat",
            _history(store, "heat", 10.0, temperature),
            temperature,
            temperature,
            actual=10.0,
            predictions=(13.0,),
        ),
        _case(
            "unknown",
            "unknown",
            _history(store, "unknown", 10.0, None),
            None,
            None,
            actual=10.0,
            predictions=(14.0,),
        ),
    ]
    plans, members = zip(*cases, strict=True)
    policy = persist_backtest_pooling_policy(ir_store, BacktestPoolingPolicy(members=members))
    orchestrator = BacktestOrchestrator(cas=store)
    calls = []
    stock = orchestrator._run_single_scenario
    context = _start_run(store)

    def observe(plan: HistoricalValidationPlan, **kwargs: Any) -> Any:
        assert context.run_manifest.inputs[-1].model_dump(mode="json") == dict(policy)
        calls.append(plan.plan_id)
        return stock(plan, **kwargs)

    monkeypatch.setattr(orchestrator, "_run_single_scenario", observe)
    wrong = plans[0].model_copy(update={"predicted_outcomes": {"price": [999.0]}})
    refused_context = _start_run(store)
    try:
        with pytest.raises(ValueError, match="differs from the preselected provided case"):
            orchestrator.run_with_ref(
                [wrong, *plans[1:]], pooling_policy_ref=policy, pooling_run_context=refused_context
            )
    finally:
        refused_context.finalize(status="fail")
    assert not calls
    report, ref = orchestrator.run_with_ref(
        list(plans), pooling_policy_ref=policy, pooling_run_context=context
    )
    run = _finalize_run(context)
    assert calls == [plan.plan_id for plan in plans]
    loaded = load_backtest_report_for_consumption(
        FileSystemCAS.open_existing_read_only(store.root), ref, pooling_run=run
    )
    assert loaded.pooling == report.pooling
    assert loaded.pooling is not None
    assert loaded.pooling.unavailable == {"unknown": "measurement_comparability_unknown"}
    assert {s.canonical_unit: s.micro_rmse for s in loaded.pooling.strata} == {
        "USD": 2.0,
        "degC": 3.0,
    }
    assert loaded.scenarios[2].outcome_comparisons[0].absolute_error == 4.0
    assert loaded.overall_rmse is None
    assert loaded.overall_macro_rmse is None


@pytest.mark.parametrize(
    ("different_metrics", "jurisdictions"),
    [
        (True, ("",)),
        (False, ("north", "south")),
        (False, ("north", "")),
    ],
    ids=["metric", "jurisdiction", "known_and_unknown_jurisdiction"],
)
def test_compiled_matrix_preserves_unpooled_measurements(
    tmp_path: Path, different_metrics: bool, jurisdictions: tuple[str, ...]
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    panel = _observation_panel(n_units=1, n_periods=4)
    metrics = ["income", "outcome_score"] if different_metrics else ["income"]
    dates = sorted({record.period_start.isoformat() for record in panel.records})
    source = store.put_json(
        {
            "time_index": dates,
            **{
                metric: [
                    record.observed_value for record in panel.records if record.metric_id == metric
                ]
                for metric in metrics
            },
        },
        PutOptions(kind="test.historical_data", media_type="application/json"),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    compiler = HistoricalValidationPlanCompiler()
    compilations = [
        compiler.compile(
            panel,
            HistoricalValidationCompileSpec(
                spec_id=f"compiled_scope_{index}",
                metric_ids=metrics,
                historical_data_ref=str(source.artifact_id),
                intervention_date=dates[1],
                pre_intervention_periods=1,
                post_intervention_periods=3,
                jurisdiction=jurisdiction,
            ),
        )
        for index, jurisdiction in enumerate(jurisdictions)
    ]
    bundle = compilations[0].bundle.model_copy(
        update={
            "plans": [plan for item in compilations for plan in item.bundle.plans],
            "historical_payloads": {
                key: value
                for item in compilations
                for key, value in item.bundle.historical_payloads.items()
            },
        }
    )
    matrix = BacktestMatrixRunner(store).run({BacktestKind.HOUSEHOLD: bundle})
    household = next(item for item in matrix.kind_results if item.kind is BacktestKind.HOUSEHOLD)
    assert household.status == "gap"
    assert household.score is None
    assert matrix.composite_score is None
    assert "measurement_comparability_not_established" in matrix.gap_flags
    selected = matrix.backtest_report_ref
    assert selected is not None
    fresh = FileSystemCAS.open_existing_read_only(store.root)
    report = load_backtest_report_for_consumption(fresh, selected)
    assert report.aggregation_policy == "measurement_comparability_not_established"
    assert report.overall_rmse is None
    assert report.overall_macro_rmse is None
    assert not report.trust_eligible
    assert report.unpooled_strata is not None
    assert len(report.unpooled_strata) == 2
    assert sum(stratum.comparison_count for stratum in report.unpooled_strata) == 8
    assert all(stratum.rmse is not None and stratum.rmse > 0 for stratum in report.unpooled_strata)
    if different_metrics:
        assert {stratum.metric_name for stratum in report.unpooled_strata} == set(metrics)
        assert report.scenarios[0].rmse is None
        assert report.scenarios[0].absolute_error_sum is None
    else:
        assert {stratum.jurisdiction for stratum in report.unpooled_strata} == set(jurisdictions)
        assert all(scenario.rmse is not None for scenario in report.scenarios)
