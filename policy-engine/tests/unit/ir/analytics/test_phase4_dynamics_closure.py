from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.contracts.foundry import (
    AttractorAnalysisResult,
    AttractorAnalysisResultRef,
    AttractorStateProjection,
    ExecPlanRef,
    IdentifiabilityDiagnosticRef,
    MetricsRef,
    SimulationResult,
    SimulationResultRef,
)
from polisyos.foundry.analysis.attractors import attach_abm_bifurcation_report_ref
from polisyos.foundry.calibration import attach_abm_identifiability_certificate_ref
from polisyos.ir.analytics.forecasting_uncertainty import (
    FanChartSpec,
    ForecastCalibrationMethod,
    ForecastCoverageDiagnostic,
    ForecastingUncertaintyBundle,
    ForecastIntervalSemantics,
    HorizonDiagnosticState,
    HorizonInterval,
    HorizonPolicyRule,
    HorizonPolicySpec,
)
from polisyos.ir.analytics.microsim_calibration import (
    attach_dynamic_validation_report_ref,
    build_microsim_calibration_report,
)
from polisyos.ir.analytics.phase4_dynamics import (
    ABMResult,
    DynamicMicrosimValidationError,
    Phase4DynamicsGate,
    Phase4DynamicsGateError,
    SpaceTimeCausalCertificate,
    TemporalGraphCausalCertificate,
    build_abm_result_from_simulation,
    build_dynamic_microsim_validation_report,
    build_space_time_causal_certificate,
    build_temporal_graph_causal_certificate,
    enforce_dynamic_microsim_validation_report,
    load_abm_result,
    load_dynamic_microsim_validation_report,
    load_space_time_causal_certificate,
    load_temporal_graph_causal_certificate,
    persist_dynamic_microsim_validation_report,
    persist_space_time_causal_certificate,
    persist_temporal_graph_causal_certificate,
)
from polisyos.ir.refs import (
    DynamicMicrosimValidationReportRef,
    MicrosimCalibrationReportRef,
)
from polisyos.ir.schema_catalog import get_ir_type


def _artifact_id(char: str) -> str:
    return f"sha256:{char * 64}"


def test_phase4_gate_blocks_long_uncalibrated_or_red_horizons() -> None:
    gate = Phase4DynamicsGate()

    assert gate.enforce(
        horizon=13,
        regime_bundle={"regime_status": "calibrated"},
    ).allowed
    assert gate.validate(horizon=2).allowed

    with pytest.raises(Phase4DynamicsGateError) as missing:
        gate.enforce(horizon=13)
    assert missing.value.verdict.refusal_code == "phase4_regime_gate_failed"

    with pytest.raises(Phase4DynamicsGateError) as drifting:
        gate.enforce(horizon=13, regime_bundle={"regime_status": "drifting"})
    assert "regime_status_not_calibrated:drifting" in drifting.value.verdict.reasons

    red_bundle = ForecastingUncertaintyBundle(
        method_fqn="forecasting.test@1.0.0",
        target_id="series",
        generated_at=datetime.now(UTC),
        prediction_interval=(
            HorizonInterval(
                horizon=2,
                point=1.0,
                lower=0.0,
                upper=2.0,
                constructor=ForecastCalibrationMethod.CONFORMAL,
            ),
        ),
        horizon_policy=HorizonPolicySpec(
            default_method=ForecastCalibrationMethod.CONFORMAL,
            rules=(
                HorizonPolicyRule(
                    horizon_start=1,
                    horizon_end=2,
                    diagnostic_state=HorizonDiagnosticState.RED,
                    allowed_methods=(ForecastCalibrationMethod.CONFORMAL,),
                    gate_eligible=False,
                ),
            ),
            gate_eligible=False,
        ),
        fan_chart=FanChartSpec(),
        coverage_diagnostic=ForecastCoverageDiagnostic(
            nominal_coverage=0.9,
            last_recalibrated_at=datetime.now(UTC),
        ),
        interval_semantics=ForecastIntervalSemantics.PREDICTION_INTERVAL,
        calibration_method=ForecastCalibrationMethod.CONFORMAL,
        nominal_coverage=0.9,
        sample_size_assumption="unit_test_fixture",
    )
    verdict = gate.validate(horizon=2, regime_bundle=red_bundle)
    assert not verdict.allowed
    assert verdict.red_horizons == (1, 2)


def test_phase4_abm_result_exact_fields_wrap_existing_refs() -> None:
    simulation = SimulationResult(
        exec_plan_ref=ExecPlanRef(artifact_id=_artifact_id("a")),
        metrics_ref=MetricsRef(artifact_id=_artifact_id("b")),
    )
    diagnostic_ref = IdentifiabilityDiagnosticRef(artifact_id=_artifact_id("c"))
    attractor_ref = AttractorAnalysisResultRef(artifact_id=_artifact_id("d"))

    result = build_abm_result_from_simulation(
        simulation,
        identifiability_diagnostic_ref=diagnostic_ref,
        attractor_analysis_ref=attractor_ref,
        bifurcation_count=2,
        attractor_count=3,
    )

    assert isinstance(result, ABMResult)
    assert result.identifiability_certificate is not None
    assert result.identifiability_certificate.diagnostic_ref is not None
    assert result.bifurcation_report is not None
    assert result.bifurcation_report.bifurcation_count == 2


def test_phase4_abm_attachment_helpers_persist_exact_fields(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    exec_plan_ref = store.put_json(
        {
            "program_ref": {
                "artifact_id": _artifact_id("a"),
                "kind": "foundry.program_graph",
                "media_type": "application/json",
            },
            "order": [],
        },
        PutOptions(kind="foundry.exec_plan", media_type="application/json"),
    )
    metrics_ref = store.put_json(
        {"values": {"welfare": 1}},
        PutOptions(kind="foundry.metrics", media_type="application/json"),
    )
    sim_ref_payload = store.put_json(
        SimulationResult(
            exec_plan_ref=ExecPlanRef(artifact_id=exec_plan_ref.artifact_id),
            metrics_ref=MetricsRef(artifact_id=metrics_ref.artifact_id),
        ),
        PutOptions(kind="foundry.simulation_result", media_type="application/json"),
    )
    sim_ref = SimulationResultRef(artifact_id=sim_ref_payload.artifact_id)

    diagnostic_ref = IdentifiabilityDiagnosticRef(artifact_id=_artifact_id("b"))
    ident_abm_ref = attach_abm_identifiability_certificate_ref(
        store,
        simulation_result_ref=sim_ref,
        diagnostic_ref=diagnostic_ref,
    )
    ident_abm = load_abm_result(store, ident_abm_ref)
    assert ident_abm.identifiability_diagnostic_ref == diagnostic_ref
    assert ident_abm.identifiability_certificate is not None
    assert str(ident_abm.identifiability_certificate.diagnostic_ref.artifact_id) == str(
        diagnostic_ref.artifact_id
    )

    attractor_ref_payload = store.put_json(
        AttractorAnalysisResult(
            analysis_id="phase4-test-attractors",
            simulation_result_ref=sim_ref,
            state_projection=AttractorStateProjection(
                variables=["welfare"],
                reduced_dimension=1,
            ),
        ),
        PutOptions(kind="foundry.attractor_analysis_result", media_type="application/json"),
    )
    bifurcation_abm_ref = attach_abm_bifurcation_report_ref(
        store,
        simulation_result_ref=sim_ref,
        attractor_analysis_ref=AttractorAnalysisResultRef(
            artifact_id=attractor_ref_payload.artifact_id
        ),
    )
    bifurcation_abm = load_abm_result(store, bifurcation_abm_ref)
    assert bifurcation_abm.bifurcation_report is not None
    assert bifurcation_abm.bifurcation_report.attractor_analysis_ref is not None


def test_dynamic_microsim_validation_report_roundtrip_and_calibration_integration(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    diagnostic = SimpleNamespace(
        status="fail",
        comparison_dataset="panel_fixture",
        horizons_reported=[1, 2],
        warnings=["bias_tolerance_failed"],
        diagnostics={"max_abs_relative_bias": 0.25},
        metadata={"track": "P4.12"},
    )
    report = build_dynamic_microsim_validation_report(diagnostic)

    assert report.validation_status == "red"
    with pytest.raises(DynamicMicrosimValidationError):
        enforce_dynamic_microsim_validation_report(report)

    ref = persist_dynamic_microsim_validation_report(store, report)
    loaded = load_dynamic_microsim_validation_report(store, ref)
    assert loaded == report

    calibration = build_microsim_calibration_report(
        compatibility_status="compatible",
        distance_to_feasibility=0.0,
        normalized_distance=0.0,
    )
    attached = attach_dynamic_validation_report_ref(
        calibration,
        dynamic_validation_report_ref=DynamicMicrosimValidationReportRef.model_validate(
            ref.model_dump(mode="python")
        ),
        dynamic_validation_status=loaded.validation_status,
    )
    assert attached.decision == "block"
    assert attached.dynamic_validation_report_ref == ref


def test_phase4_causal_certificates_roundtrip(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    temporal = build_temporal_graph_causal_certificate(
        temporal_identification_certificate={"theorem_family": "local_independence"},
        local_independence_certificate={
            "verification_status": "identified",
            "assumptions": ["observed_filtration"],
        },
    )
    assert isinstance(temporal, TemporalGraphCausalCertificate)
    temporal_ref = persist_temporal_graph_causal_certificate(store, temporal)
    assert load_temporal_graph_causal_certificate(store, temporal_ref) == temporal

    space_time = build_space_time_causal_certificate(
        {
            "status": "model_extrapolation",
            "assumptions": {"consistency": "pass"},
            "caveats": ["policy_field_leaves_observed_treatment_range"],
        }
    )
    assert isinstance(space_time, SpaceTimeCausalCertificate)
    space_ref = persist_space_time_causal_certificate(store, space_time)
    assert load_space_time_causal_certificate(store, space_ref) == space_time


def test_phase4_exact_public_symbols_and_fields_are_registered() -> None:
    expected_abi = {
        "ABMResult": "abm_result",
        "DynamicMicrosimValidationReport": "dynamic_microsim_validation_report",
        "TemporalGraphCausalCertificate": "temporal_graph_causal_certificate",
        "SpaceTimeCausalCertificate": "space_time_causal_certificate",
        "Phase4TemporalPolicyGateVerdict": "phase4_temporal_policy_gate_verdict",
    }
    for name, abi_key in expected_abi.items():
        entry = get_ir_type(name)
        assert entry.abi_key == abi_key
        assert entry.public_status.value == "root_facade"

    abm_fields = ABMResult.model_fields
    assert "identifiability_certificate" in abm_fields
    assert "bifurcation_report" in abm_fields
    assert DynamicMicrosimValidationReportRef.model_fields["kind"].default == (
        "ir.dynamic_microsim_validation_report"
    )
    assert MicrosimCalibrationReportRef.model_fields["kind"].default == (
        "ir.microsim_calibration_report"
    )
