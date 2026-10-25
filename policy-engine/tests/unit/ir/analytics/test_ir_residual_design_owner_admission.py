from __future__ import annotations

import importlib
import os
from datetime import UTC, datetime
from pathlib import Path

import pytest

import polisyos.ir.analytics as analytics_package
from polisyos.core.artifacts import ensure_ir_artifact_store
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.ir.analytics._owner_admission import (
    OwnedJSONRepresentation,
    register_owner_representations,
)
from polisyos.ir.artifacts import get_json_artifact, put_json_artifact
from polisyos.ir.artifacts.io import _get_owned_json_artifact_with_bytes
from polisyos.ir.migrations import base as migrations_base
from polisyos.ir.model_layer.canon import CanonSpec, CanonViolation
from polisyos.ir.registry.refs import ArtifactRefModel, NormativeArbitrationResultRef

_OVERLAY = Path(
    os.environ.get(
        "POLISYOS_IR_ANALYTICS_OVERLAY",
        str(Path(analytics_package.__file__).resolve().parent),
    )
).resolve()
analytics_package.__path__.insert(0, str(_OVERLAY))

normative = importlib.import_module("polisyos.ir.analytics.normative_arbitration")
recourse = importlib.import_module("polisyos.ir.analytics.recourse_manifold")
regime = importlib.import_module("polisyos.ir.analytics.regime_shift_forecast")
rough = importlib.import_module("polisyos.ir.analytics.rough_path_semantics")
shift = importlib.import_module("polisyos.ir.analytics.shift_diagnostics")

assert Path(normative.__file__).resolve().parent == _OVERLAY
assert Path(recourse.__file__).resolve().parent == _OVERLAY
assert Path(regime.__file__).resolve().parent == _OVERLAY
assert Path(rough.__file__).resolve().parent == _OVERLAY
assert Path(shift.__file__).resolve().parent == _OVERLAY


def _normative_result():
    from polisyos.ir.analytics.normative_arbitration import (
        ArbitrationOption,
        NormativeArbitrationResult,
        OptionOutcomeMatrix,
        PolicyOutcome,
        TradeoffCertificate,
    )
    from polisyos.ir.governance.problem_frame import NormativeArbitrationPolicy

    policy = NormativeArbitrationPolicy.WEIGHTED_WELFARE
    return NormativeArbitrationResult(
        option_matrix=(
            OptionOutcomeMatrix(option=ArbitrationOption.BASELINE),
            OptionOutcomeMatrix(option=ArbitrationOption.PROPOSAL),
        ),
        policy_outcomes=(
            PolicyOutcome(
                policy=policy,
                selected_option=ArbitrationOption.PROPOSAL,
                rationale="candidate preference",
            ),
        ),
        selected_policy=policy,
        selected_option=ArbitrationOption.PROPOSAL,
        tradeoff_certificate=TradeoffCertificate(
            selected_policy=policy,
            selected_option=ArbitrationOption.PROPOSAL,
        ),
    )


def _manifold():
    from polisyos.ir.analytics.recourse_manifold import (
        ActionChannel,
        ActionDomain,
        CouplingCost,
        EquivalenceMode,
        InterventionCostManifold,
        PrimitiveCost,
        RecourseSemantics,
    )

    return InterventionCostManifold(
        scm_ref="scm:demo",
        factual_unit_ref="unit:1",
        semantics=RecourseSemantics.COUNTERFACTUAL_UNIT,
        mutable_nodes=("education", "income"),
        immutable_nodes=("age",),
        action_channels=(
            ActionChannel(
                node="education",
                channel="certificate_course",
                prerequisite_refs=("prereq:education_course_eligible",),
            ),
            ActionChannel(node="income", channel="salary_raise"),
        ),
        prerequisite_refs=("prereq:education_course_eligible",),
        domains=(
            ActionDomain(node="education", kind="discrete", values=("master",)),
            ActionDomain(node="income", kind="interval", lower=0.0, upper=1_000_000.0),
        ),
        primitive_costs=(
            PrimitiveCost(node="education", cost_kind="constant", base_cost=5.0),
            PrimitiveCost(node="income", cost_kind="linear", base_cost=1.0, slope=0.001),
        ),
        coupling_costs=(CouplingCost(kind="budget", nodes=("income", "education"), limit=1_000.0),),
        equivalence_mode=EquivalenceMode.SAME_COUNTERFACTUAL_DISTRIBUTION,
    )


def _ref(ch: str = "a", *, kind: str = "ir.test_artifact") -> ArtifactRefModel:
    return ArtifactRefModel(
        artifact_id=f"sha256:{ch * 64}",
        kind=kind,
        media_type="application/json",
    )


def _regime_bundle():
    from polisyos.ir.analytics.forecasting_uncertainty import (
        FanChartSpec,
        ForecastCalibrationMethod,
        ForecastCoverageDiagnostic,
        ForecastIntervalSemantics,
        HorizonDiagnosticState,
        HorizonInterval,
        HorizonPolicyRule,
        HorizonPolicySpec,
        HorizonQuantileSet,
    )
    from polisyos.ir.analytics.regime_shift_forecast import (
        ForecastShiftTypeAssessment,
        RegimeBenchmarkStatus,
        RegimeForecastCalibrationStatus,
        RegimeIdentifiabilityStatus,
        RegimeModelFamily,
        RegimeShiftForecastBundle,
    )

    now = datetime.now(UTC)
    method = ForecastCalibrationMethod.BAYESIAN_PLUS_CONFORMAL
    return RegimeShiftForecastBundle(
        method_fqn="forecasting.regime.markov@1.0.0",
        target_id="tax_receipts",
        generated_at=now,
        prediction_interval=(
            HorizonInterval(
                horizon=1,
                point=10.0,
                lower=8.0,
                upper=12.0,
                coverage_target=0.9,
                constructor=method,
                sample_count=40,
            ),
        ),
        fan_chart=FanChartSpec(
            quantile_levels=(0.05, 0.5, 0.95),
            horizons=(
                HorizonQuantileSet(
                    horizon=1,
                    quantiles={"0.05": 8.0, "0.5": 10.0, "0.95": 12.0},
                ),
            ),
        ),
        coverage_diagnostic=ForecastCoverageDiagnostic(
            nominal_coverage=0.9,
            empirical_coverage_by_horizon={1: 0.91},
            coverage_gap_by_horizon={1: 0.01},
            mean_interval_width_by_horizon={1: 4.0},
            conditional_coverage_pvalue_by_horizon={1: 0.32},
            independence_pvalue_by_horizon={1: 0.29},
            wis_by_horizon={1: 1.7},
            sample_count_by_horizon={1: 40},
            regime_flags=("regime_conditional_coverage_checked",),
            calibration_window=40,
            last_recalibrated_at=now,
        ),
        horizon_policy=HorizonPolicySpec(
            default_method=method,
            rules=(
                HorizonPolicyRule(
                    horizon_start=1,
                    horizon_end=1,
                    diagnostic_state=HorizonDiagnosticState.GREEN,
                    allowed_methods=(method,),
                    gate_eligible=True,
                    regime="candidate_regime",
                ),
            ),
            gate_eligible=True,
            summary="Regime-conditional coverage gate",
        ),
        interval_semantics=ForecastIntervalSemantics.CONFORMALIZED_PREDICTION_INTERVAL,
        calibration_method=method,
        nominal_coverage=0.9,
        sample_size_assumption="minimum dwell time exceeds lag order",
        regime_assumption="one stable regime",
        regime_model_family=RegimeModelFamily.MARKOV_SWITCHING,
        identifiability_status=RegimeIdentifiabilityStatus.WEAKLY_IDENTIFIED,
        regime_status=RegimeForecastCalibrationStatus.UNKNOWN,
        regime_count_posterior_ref=_ref("1"),
        assignment_posterior_ref=_ref("2"),
        permutation_invariant_regime_map_ref=_ref("3"),
        regime_parameter_summary_ref=_ref("4"),
        predictive_mixture_ref=_ref("5"),
        regime_conditional_forecasts_ref=_ref("6"),
        calibration_slice_ref=_ref("7"),
        break_recovery_curve_ref=_ref("8"),
        shift_type_assessment=ForecastShiftTypeAssessment.STRUCTURAL,
        identifiability_diagnostics_ref=_ref("9"),
        benchmark_status=RegimeBenchmarkStatus.YELLOW,
    )


def _rough_path_certificate():
    from polisyos.ir.analytics.rough_path_semantics import (
        RoughPathGraphCriterion,
        RoughPathIdentificationStatus,
        RoughPathIdentificationStrategy,
        RoughPathInterventionCertificate,
        RoughPathInterventionType,
        RoughPathModelFamily,
        RoughPathTopology,
        TemporalPathSemanticsScope,
    )

    return RoughPathInterventionCertificate(
        semantics_scope=TemporalPathSemanticsScope.REPRESENTED_PATH,
        model_family=RoughPathModelFamily.HYBRID_RDE,
        topology=RoughPathTopology.P_VARIATION,
        graph_criterion=RoughPathGraphCriterion.DELTA_SEP,
        observation_operator_ref=_ref("a", kind="test.observation_operator"),
        lift_operator_ref=_ref("b", kind="test.lift_operator"),
        interpolation_is_adapted=True,
        future_leakage_ruled_out=True,
        intervention_type=RoughPathInterventionType.POLICY_OVERRIDE,
        intervention_operator_ref=_ref("c", kind="test.intervention_operator"),
        actuatable_component="income",
        filtration_ref=_ref("d", kind="test.filtration"),
        well_posedness_ref=_ref("e", kind="test.well_posedness"),
        identification_strategy=RoughPathIdentificationStrategy.CONTINUOUS_TIME_G_FORMULA,
        positivity_ref=_ref("f", kind="test.positivity"),
        sampling_ignorability_ref=_ref("1", kind="test.sampling_ignorability"),
        target_functional_ref=_ref("2", kind="test.target_functional"),
        proof_trace_ref=_ref("3", kind="test.proof_trace"),
        status=RoughPathIdentificationStatus.IDENTIFIED_REPRESENTATION_ONLY,
        scope_notes=("representation-level only",),
    )


def _shift_report():
    from polisyos.ir.analytics.shift_diagnostics import (
        CalibrationInfo,
        DetectorResult,
        OperatingCharacteristicKey,
        ShiftComponent,
        ShiftDiagnosticReport,
        build_readiness_impact,
    )

    key = OperatingCharacteristicKey(
        modality="tabular_administrative",
        task_type="classification",
        n_reference_bucket="n_ref_1k_10k",
        n_current_bucket="n_cur_1k_10k",
        feature_count_bucket="p_10_100",
        categorical_cardinality_bucket="cat_medium",
        sparsity_missingness_bucket="missing_low",
        label_lag_bucket="no_labels",
        detector_family="univariate",
        reference_comparison_type="training_vs_current",
        windowing_strategy="calendar_month",
        calibration_version="test",
    )
    calibration = CalibrationInfo(
        operating_characteristic_library_version="ocl-test-v1",
        calibration_id="cal-test",
        reference_comparison_type="training_vs_current",
        target_report_fpr=0.05,
        null_regime="stable_adjacent_months",
        min_detectable_effect_summary={"global_x": "medium"},
        power_summary={"global_x_medium": 0.84},
    )
    component = ShiftComponent(
        status="not_detected",
        severity_score=0.0,
        severity_bucket="none",
        power=0.82,
    )
    concept = ShiftComponent(
        status="unassessable_until_labels",
        severity_score=None,
        severity_bucket="unassessable",
        power=0.82,
    )
    return ShiftDiagnosticReport(
        report_id="shift-report-owner-admission",
        generated_at=datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
        model_id="benefits-risk-model",
        model_version="candidate",
        task_type="classification",
        modality="tabular_administrative",
        training_reference_id="train-window",
        validation_reference_id="validation-window",
        current_window_id="current-window",
        current_window_start="2026-10-01",
        current_window_end="2026-10-24",
        n_reference=1200,
        n_current=900,
        effective_n_reference=1190.0,
        effective_n_current=880.0,
        label_availability="none",
        power_status="sufficient",
        calibration=calibration,
        schema_shift=component,
        marginal_shift=component,
        support_shift=component,
        label_prior_shift=component,
        concept_shift=concept,
        prediction_output_shift=component,
        harmful_shift_risk=component,
        global_verdict="no_shift_detected",
        detector_results=(
            DetectorResult(
                detector_name="feature_wise_ks",
                detector_family="univariate",
                data_view="raw_features",
                statistic=0.04,
                p_value=0.31,
                q_value=0.42,
                operating_characteristic_key=key.to_cache_key(),
            ),
        ),
        readiness_impact=build_readiness_impact(
            base_readiness="ready",
            downgrade_level=0,
            downgrade_reasons=(),
            required_actions=(),
        ),
        human_summary="No material covariate shift detected; concept shift awaits labels.",
        machine_summary={"top_level": "no_shift_detected"},
        limitations=("concept_shift_unassessable_without_labels",),
        recommended_next_checks=("attach_delayed_outcomes_when_available",),
    )


def test_all_owner_pairs_persist_through_cas_and_read_typed_consumers(tmp_path: Path) -> None:
    from polisyos.ir.analytics.normative_arbitration import (
        load_normative_arbitration_result,
        persist_normative_arbitration_result,
    )
    from polisyos.ir.analytics.recourse_manifold import (
        InterventionProgram,
        OptimalRecourseInterventionBundle,
        OptimalRecourseInterventionQuery,
        PrimitiveAction,
        RecourseRecoverabilityStatus,
        RecourseSemantics,
        RecourseSolverStatus,
        RecourseSuccessMode,
        build_feasibility_certificate,
        build_recourse_proof_bundle,
        load_feasibility_certificate,
        load_intervention_cost_manifold,
        load_optimal_recourse_query,
        load_recourse_bundle,
        load_recourse_proof_bundle,
        persist_feasibility_certificate,
        persist_intervention_cost_manifold,
        persist_optimal_recourse_query,
        persist_recourse_bundle,
        persist_recourse_proof_bundle,
    )
    from polisyos.ir.analytics.regime_shift_forecast import (
        load_regime_shift_forecast_bundle,
        persist_regime_shift_forecast_bundle,
    )
    from polisyos.ir.analytics.rough_path_semantics import (
        load_rough_path_intervention_certificate,
        persist_rough_path_intervention_certificate,
    )
    from polisyos.ir.analytics.shift_diagnostics import (
        load_shift_diagnostic_report,
        persist_shift_diagnostic_report,
    )

    store = ensure_ir_artifact_store(FileSystemCAS(tmp_path / "cas"))
    normative_value = _normative_result()
    normative_ref = persist_normative_arbitration_result(store, normative_value)
    assert load_normative_arbitration_result(store, normative_ref) == normative_value

    manifold = _manifold()
    manifold_ref = persist_intervention_cost_manifold(store, manifold)
    assert load_intervention_cost_manifold(store, manifold_ref) == manifold

    query = OptimalRecourseInterventionQuery(
        factual_unit_ref="unit:1",
        target_outcome="loan_approval",
        target_value=1,
        threshold_tau=0.75,
        semantics=RecourseSemantics.COUNTERFACTUAL_UNIT,
        success_mode=RecourseSuccessMode.POINT_PROBABILITY,
        intervention_cost_manifold_ref=manifold_ref,
        mutable_nodes=("education", "income"),
        immutable_nodes=("age",),
        support_budget=2,
    )
    query_ref = persist_optimal_recourse_query(store, query)
    assert load_optimal_recourse_query(store, query_ref) == query

    proof = build_recourse_proof_bundle(
        query_ref=query_ref,
        scm_ref="scm:demo",
        semantics=query.semantics,
        success_mode=query.success_mode,
        recoverability_status=RecourseRecoverabilityStatus.IDENTIFIED,
        mutable_nodes=query.mutable_nodes,
        immutable_nodes=query.immutable_nodes,
    )
    proof_ref = persist_recourse_proof_bundle(store, proof)
    assert load_recourse_proof_bundle(store, proof_ref) == proof

    action = InterventionProgram(
        actions=(PrimitiveAction(node="education", target_value="master"),),
        metadata={"satisfied_prerequisite_refs": ["prereq:education_course_eligible"]},
    )
    feasibility = build_feasibility_certificate(
        action=action,
        factual_unit_ref="unit:1",
        scm_ref="scm:demo",
        semantics=query.semantics,
        manifold=manifold,
        achieved_success_value=0.9,
        threshold_tau=query.threshold_tau,
        success_measure=query.success_mode,
        structural_consistency_ok=True,
        optimality_status="exact",
        optimality_gap=0.0,
        recoverability_ref=proof_ref,
    )
    feasibility_ref = persist_feasibility_certificate(store, feasibility)
    assert load_feasibility_certificate(store, feasibility_ref) == feasibility

    bundle = OptimalRecourseInterventionBundle(
        query_ref=query_ref,
        proof_ref=proof_ref,
        action=action,
        achieved_cost=5.0,
        achieved_success_value=0.9,
        feasibility_certificate_ref=feasibility_ref,
        solver_status=RecourseSolverStatus.EXACT,
        readiness_cap=proof.readiness_cap,
        candidate_supports_explored=3,
    )
    bundle_ref = persist_recourse_bundle(store, bundle)
    assert load_recourse_bundle(store, bundle_ref) == bundle

    regime_value = _regime_bundle()
    regime_ref = persist_regime_shift_forecast_bundle(store, regime_value)
    assert load_regime_shift_forecast_bundle(store, regime_ref) == regime_value

    rough_value = _rough_path_certificate()
    rough_ref = persist_rough_path_intervention_certificate(store, rough_value)
    assert load_rough_path_intervention_certificate(store, rough_ref) == rough_value

    shift_value = _shift_report()
    shift_ref = persist_shift_diagnostic_report(store, shift_value)
    assert load_shift_diagnostic_report(store, shift_ref) == shift_value

    for ref in (
        normative_ref,
        manifold_ref,
        query_ref,
        proof_ref,
        feasibility_ref,
        bundle_ref,
        regime_ref,
        rough_ref,
        shift_ref,
    ):
        assert ref.manifest_profile_sha256 is not None
        assert store.get_manifest(ref).artifact_schema.version == "1.0"


def _write_generic_normative(store, payload, *, schema_version="1.0", canon_spec=None):
    return NormativeArbitrationResultRef.model_validate(
        put_json_artifact(
            store,
            payload,
            kind="ir.normative_arbitration_result",
            schema_name="ir.normative_arbitration_result",
            schema_version=schema_version,
            canon_spec=canon_spec or CanonSpec(forbid_floats=False),
            return_selected_profile=True,
        )
    )


def _assert_normative_unknown_refuses(store, ref) -> None:
    try:
        normative.load_normative_arbitration_result(store, ref)
    except CanonViolation:
        return
    raise AssertionError("owner admission bypassed for an unknown manifest tuple")


def test_unknown_matching_manifest_tuple_stays_opaque_and_removal_control_is_semantic(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = ensure_ir_artifact_store(FileSystemCAS(tmp_path / "unknown"))
    payload = _normative_result().model_dump(mode="json")
    # Keep the manifest and embedded version coherent while the tuple is unknown.
    payload["schema_version"] = "9.9"
    ref = _write_generic_normative(store, payload, schema_version="9.9")
    assert store.get_manifest(ref).artifact_schema.version == "9.9"
    persisted = get_json_artifact(store, ref)
    assert persisted == payload
    assert persisted["schema_version"] == "9.9"
    _assert_normative_unknown_refuses(store, ref)

    def legacy_unowned_reader(store_arg, ref_arg, *, owner):
        del owner
        from polisyos.ir.analytics.normative_arbitration import NormativeArbitrationResult

        return NormativeArbitrationResult.model_validate(get_json_artifact(store_arg, ref_arg))

    with monkeypatch.context() as patch:
        patch.setattr(normative, "_get_owned_json_artifact", legacy_unowned_reader)
        with pytest.raises(AssertionError, match="owner admission bypassed"):
            _assert_normative_unknown_refuses(store, ref)


def test_payload_manifest_mismatch_and_wrong_selected_profile_refuse(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    store = ensure_ir_artifact_store(FileSystemCAS(tmp_path / "invalid"))
    payload = _normative_result().model_dump(mode="json")
    mismatched = dict(payload)
    mismatched["schema_version"] = "9.9"
    mismatched_ref = _write_generic_normative(store, mismatched)
    assert get_json_artifact(store, mismatched_ref)["schema_version"] == "9.9"
    with pytest.raises(CanonViolation):
        normative.load_normative_arbitration_result(store, mismatched_ref)

    wrong_profile_ref = _write_generic_normative(
        store,
        payload,
        canon_spec=CanonSpec(forbid_floats=False, max_depth=64),
    )
    assert wrong_profile_ref.manifest_profile_sha256 is not None
    payload_reads = 0
    original_get_bytes = FileSystemCAS.get_bytes

    def track_payload_read(*args, **kwargs):
        nonlocal payload_reads
        payload_reads += 1
        return original_get_bytes(*args, **kwargs)

    monkeypatch.setattr(FileSystemCAS, "get_bytes", track_payload_read)
    with pytest.raises(CanonViolation, match="ir_owned_artifact_profile_refused"):
        normative.load_normative_arbitration_result(store, wrong_profile_ref)
    assert payload_reads == 0


def test_later_registered_same_owner_representation_needs_no_core_dispatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry = {
        artifact: dict(versions) for artifact, versions in migrations_base._SCHEMA_REGISTRY.items()
    }
    monkeypatch.setattr(migrations_base, "_SCHEMA_REGISTRY", registry)
    owner = normative._NORMATIVE_ARBITRATION_RESULT_OWNER
    register_owner_representations(
        owner,
        (
            OwnedJSONRepresentation(
                schema_name="ir.normative_arbitration_result",
                schema_version="1.2",
                payload_version="1.0",
                wire_policy_ref=owner.accepted_wire_policies[0][0],
                wire_policy_revision=owner.accepted_wire_policies[0][1],
                profile_ref=None,
                compatibility=migrations_base.CompatibilityMode.NONE,
                notes=("Test-only registered nondefault tuple reusing the owner wire law.",),
                readable=True,
                writable=True,
                current=False,
                default_write=False,
                readable_from=(),
            ),
        ),
    )
    store = ensure_ir_artifact_store(FileSystemCAS(tmp_path / "registered"))
    value = _normative_result()
    ref = normative.persist_normative_arbitration_result(store, value, schema_version="1.2")
    read = _get_owned_json_artifact_with_bytes(store, ref, owner=owner)
    assert store.get_manifest(ref).artifact_schema.version == "1.2"
    assert read.admission.source_registration.schema_version == "1.2"
    assert read.admission.source_registration.payload_version == "1.0"
    assert read.admission.current_registration.schema_version == "1.0"
    assert read.admission.compatibility_kind is migrations_base.IRCompatibilityKind.DIRECT
    assert normative.load_normative_arbitration_result(store, ref) == value


def test_unregistered_writer_override_refuses_before_cas_mutation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = ensure_ir_artifact_store(FileSystemCAS(tmp_path / "unregistered-write"))
    writes = 0
    original_put_json = FileSystemCAS.put_json

    def count_cas_writes(*args, **kwargs):
        nonlocal writes
        writes += 1
        return original_put_json(*args, **kwargs)

    monkeypatch.setattr(FileSystemCAS, "put_json", count_cas_writes)
    with pytest.raises(CanonViolation, match="ir_owned_artifact_write_override_unregistered"):
        normative.persist_normative_arbitration_result(
            store,
            _normative_result(),
            schema_version="9.9",
        )
    assert writes == 0
