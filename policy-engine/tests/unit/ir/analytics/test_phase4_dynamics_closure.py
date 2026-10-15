from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

import polisyos.foundry.methods.catalog.simulation.dynamics as simulation_dynamics
from polisyos.core.artifacts import ensure_ir_artifact_store as _ensure_ir_artifact_store
from polisyos.core.artifacts.manifest import InputRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec
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
from polisyos.foundry.analysis.attractors import (
    attach_abm_bifurcation_report_ref,
    persist_attractor_analysis_result,
)
from polisyos.foundry.calibration import (
    IdentifiabilityDiagnosticConfig,
    IdentifiabilityDiagnosticStatus,
    attach_abm_identifiability_certificate_ref,
    identifiability_diagnostic,
)
from polisyos.foundry.methods.catalog.simulation.dynamics import (
    build_content_bound_abm_result,
)
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
    StrangleReceiptError,
    TemporalGraphCausalCertificate,
    build_dynamic_microsim_validation_report,
    build_space_time_causal_certificate,
    build_strangle_receipt,
    build_temporal_graph_causal_certificate,
    enforce_dynamic_microsim_validation_report,
    load_abm_result,
    load_dynamic_microsim_validation_report,
    load_space_time_causal_certificate,
    load_temporal_graph_causal_certificate,
    persist_abm_result,
    persist_dynamic_microsim_validation_report,
    persist_space_time_causal_certificate,
    persist_temporal_graph_causal_certificate,
    verify_strangle_receipt,
)
from polisyos.ir.registry.refs import (
    DynamicMicrosimValidationReportRef,
    MicrosimCalibrationReportRef,
)
from polisyos.ir.schemas import get_ir_type


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


def test_phase4_storeless_abm_conversion_does_not_promote_unresolved_refs() -> None:
    diagnostic_ref = IdentifiabilityDiagnosticRef(artifact_id=_artifact_id("c"))
    simulation = SimulationResult(
        exec_plan_ref=ExecPlanRef(artifact_id=_artifact_id("a")),
        metrics_ref=MetricsRef(artifact_id=_artifact_id("b")),
        identifiability_diagnostic_ref=diagnostic_ref,
    )
    attractor_ref = AttractorAnalysisResultRef(artifact_id=_artifact_id("d"))

    result = simulation_dynamics.build_abm_result_from_simulation(
        simulation,
        identifiability_diagnostic_ref=diagnostic_ref,
        attractor_analysis_ref=attractor_ref,
        bifurcation_count=2,
        attractor_count=3,
    )

    assert isinstance(result, ABMResult)
    assert result.identifiability_certificate is not None
    assert result.identifiability_certificate.status == "not_available"
    assert result.identifiability_certificate.diagnostic_ref is None
    assert result.bifurcation_report is not None
    assert result.bifurcation_report.status == "not_available"
    assert result.bifurcation_report.attractor_analysis_ref is None
    assert result.bifurcation_report.bifurcation_count is None
    assert result.identifiability_diagnostic_ref is None
    assert set(ABMResult.model_fields) == {
        *SimulationResult.model_fields,
        "identifiability_certificate",
        "bifurcation_report",
    }
    expected_wire = simulation.model_dump(mode="json")
    expected_wire["identifiability_diagnostic_ref"] = None
    assert (
        result.model_dump(
            mode="json",
            exclude={"identifiability_certificate", "bifurcation_report"},
        )
        == expected_wire
    )


def test_phase4_abm_result_is_an_independent_strict_ir_round_trip(tmp_path) -> None:
    payload = {
        "exec_plan_ref": {"artifact_id": _artifact_id("a")},
        "metrics_ref": {"artifact_id": _artifact_id("b")},
        "metric_observation_bundle_ref": {"artifact_id": _artifact_id("c")},
        "state_snapshot_ref": {"artifact_id": _artifact_id("d")},
        "environment_ref": {"artifact_id": _artifact_id("e")},
        "trace_slice_ref": {"artifact_id": _artifact_id("f")},
        "uncertainty_envelopes": {
            "outcome": {"artifact_id": _artifact_id("1")},
        },
        "distributional_report_ref": {"artifact_id": _artifact_id("2")},
        "welfare_bundle_ref": {"artifact_id": _artifact_id("3")},
        "welfare_bound_refs": {
            "aggregate": {"artifact_id": _artifact_id("4")},
        },
        "metric_validation_report_ref": {"artifact_id": _artifact_id("5")},
        "fairness_audit_report_ref": {"artifact_id": _artifact_id("6")},
        "feedback_result_ref": {"artifact_id": _artifact_id("7")},
        "identifiability_diagnostic_ref": {"artifact_id": _artifact_id("8")},
        "notes": ["independent_ir_result"],
        "identifiability_certificate": {
            "status": "diagnostic_attached",
            "diagnostic_ref": {"artifact_id": _artifact_id("8")},
        },
        "bifurcation_report": {
            "status": "available",
            "attractor_analysis_ref": {"artifact_id": _artifact_id("9")},
        },
    }
    expected_kinds = {
        "exec_plan_ref": "foundry.exec_plan",
        "metrics_ref": "foundry.metrics",
        "metric_observation_bundle_ref": "foundry.metric_observation_bundle",
        "state_snapshot_ref": "foundry.state_snapshot",
        "environment_ref": "foundry.environment_manifest",
        "trace_slice_ref": "foundry.trace_slice",
        "distributional_report_ref": "ir.distributional_report",
        "welfare_bundle_ref": "ir.welfare_bundle",
        "metric_validation_report_ref": "scientist.metric_validation_report",
        "fairness_audit_report_ref": "scientist.fairness_audit_report",
        "feedback_result_ref": "foundry.feedback_result",
        "identifiability_diagnostic_ref": "foundry.identifiability_diagnostic",
    }

    result = ABMResult.model_validate(payload)
    wire_payload = result.model_dump(mode="json")
    store = FileSystemCAS(tmp_path)
    ref = persist_abm_result(_ensure_ir_artifact_store(store), result)
    loaded = load_abm_result(_ensure_ir_artifact_store(store), ref)

    assert SimulationResult not in ABMResult.__mro__
    assert loaded == result
    assert loaded.model_dump(mode="json") == wire_payload
    for field_name, kind in expected_kinds.items():
        assert getattr(loaded, field_name).kind == kind
    assert loaded.uncertainty_envelopes is not None
    assert loaded.uncertainty_envelopes["outcome"].kind == "ir.uncertainty_envelope"
    assert loaded.welfare_bound_refs is not None
    assert loaded.welfare_bound_refs["aggregate"].kind == "foundry.welfare_bound_report"
    assert loaded.identifiability_certificate is not None
    assert loaded.identifiability_certificate.diagnostic_ref is not None
    assert (
        loaded.identifiability_certificate.diagnostic_ref.kind
        == "foundry.identifiability_diagnostic"
    )
    assert loaded.bifurcation_report is not None
    assert loaded.bifurcation_report.attractor_analysis_ref is not None
    assert (
        loaded.bifurcation_report.attractor_analysis_ref.kind == "foundry.attractor_analysis_result"
    )
    assert loaded.trace_slice_ref is not None
    assert loaded.trace_slice_ref.media_type == "application/jsonl"
    with pytest.raises(ValidationError, match="frozen_instance"):
        loaded.notes = []
    with pytest.raises(ValueError):
        ABMResult.model_validate({**payload, "unexpected_authority": True})


def test_phase4_abm_strangle_receipt_recomputes_payload_and_diagnostics() -> None:
    payload = {
        "trajectory": [{"step": 0, "outcome": 1.0}],
        "metrics": {"completed_count": 2},
    }
    diagnostics = {"engine": "simulation.test", "warnings": []}
    receipt = build_strangle_receipt(
        method_id="simulation.test.abm",
        horizon=3,
        payload=payload,
        diagnostics=diagnostics,
    )

    verify_strangle_receipt(
        receipt,
        method_id="simulation.test.abm",
        horizon=3,
        payload=payload,
        diagnostics=diagnostics,
    )
    with pytest.raises(StrangleReceiptError, match="receipt_content_mismatch"):
        verify_strangle_receipt(
            receipt,
            method_id="simulation.test.abm",
            horizon=3,
            payload={**payload, "trajectory": [{"step": 0, "outcome": 2.0}]},
            diagnostics=diagnostics,
        )

    no_diagnostics = build_strangle_receipt(
        method_id="simulation.test.abm",
        horizon=3,
        payload=payload,
        diagnostics={},
    )
    with pytest.raises(StrangleReceiptError, match="receipt_diagnostics_missing"):
        verify_strangle_receipt(
            no_diagnostics,
            method_id="simulation.test.abm",
            horizon=3,
            payload=payload,
            diagnostics={},
        )

    result = build_content_bound_abm_result(
        method_id="simulation.test.abm",
        horizon=3,
        payload=payload,
        diagnostics=diagnostics,
    )
    assert result.identifiability_certificate is not None
    assert result.identifiability_certificate.status == "not_available"
    assert "phase4_abm_result_stub" not in result.model_dump_json()


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
    simulation = SimulationResult(
        exec_plan_ref=ExecPlanRef(artifact_id=exec_plan_ref.artifact_id),
        metrics_ref=MetricsRef(artifact_id=metrics_ref.artifact_id),
    )
    sim_ref_payload = store.put_json(
        simulation,
        PutOptions(
            kind="foundry.simulation_result",
            media_type="application/json",
            schema=SchemaInfo(
                name=SimulationResult.ARTIFACT_SCHEMA_NAME,
                version=simulation.schema_version,
            ),
        ),
        return_selected_profile=True,
    )
    sim_ref = SimulationResultRef.model_validate(sim_ref_payload.model_dump(mode="python"))
    diagnostic = identifiability_diagnostic(
        store,
        simulation_result_ref=sim_ref,
        observed_moment_bundle={"mean_y": 1.0, "q50_y": 2.0},
        parameter_center={"alpha": 1.0},
        summary_evaluator=lambda theta, _seed: {
            "mean_y": float(theta["alpha"]),
            "q50_y": float(2.0 * theta["alpha"]),
        },
        config=IdentifiabilityDiagnosticConfig(
            simulation_reps=2,
            bootstrap_reps=0,
            profile_grid_size=0,
            seed=3,
        ),
    )
    assert diagnostic.status is IdentifiabilityDiagnosticStatus.IDENTIFIED
    diagnostic_ref = diagnostic.diagnostic_ref
    assert diagnostic_ref is not None
    assert diagnostic_ref.manifest_profile_sha256 is not None
    ident_abm_ref = attach_abm_identifiability_certificate_ref(
        store,
        simulation_result_ref=sim_ref,
        diagnostic_ref=diagnostic_ref,
    )
    fresh_store = FileSystemCAS(tmp_path)
    ident_abm = load_abm_result(_ensure_ir_artifact_store(fresh_store), ident_abm_ref)
    assert not isinstance(
        ident_abm.identifiability_diagnostic_ref,
        IdentifiabilityDiagnosticRef,
    )
    assert str(ident_abm.identifiability_diagnostic_ref.artifact_id) == str(
        diagnostic_ref.artifact_id
    )
    assert (
        ident_abm.identifiability_diagnostic_ref.manifest_profile_sha256
        == diagnostic_ref.manifest_profile_sha256
    )
    assert ident_abm.identifiability_certificate is not None
    assert ident_abm.identifiability_certificate.status == "diagnostic_attached"
    assert ident_abm.identifiability_certificate.identified is None
    assert (
        "diagnostic_verifier_provenance_not_admitted"
        in (ident_abm.identifiability_certificate.metadata["limitation_codes"])
    )
    assert str(ident_abm.identifiability_certificate.diagnostic_ref.artifact_id) == str(
        diagnostic_ref.artifact_id
    )

    # A same-kind CAS payload can bind this simulation while contradicting the
    # rank and conditioning fields; content binding does not prove verification.
    forged_payload = diagnostic.model_dump(mode="json")
    forged_payload.update(
        {
            "effective_dimension": 0,
            "jacobian_rank": 0,
            "fisher_eigenvalues": [0.0],
            "min_eigenvalue": 0.0,
            "condition_number": 1e30,
            "blocking_reasons": ["forged_rank_deficient"],
            "status": IdentifiabilityDiagnosticStatus.IDENTIFIED.value,
        }
    )
    forged_ref = store.put_json(
        forged_payload,
        PutOptions(
            kind="foundry.identifiability_diagnostic",
            media_type="application/json",
            schema=SchemaInfo(
                name="polisyos.core.IdentifiabilityDiagnosticResult",
                version="1.0",
            ),
            inputs=[
                InputRef(
                    artifact_id=sim_ref.artifact_id,
                    role="simulation_result",
                    manifest_profile_sha256=sim_ref.manifest_profile_sha256,
                )
            ],
        ),
        canon_spec=CanonSpec(forbid_floats=False, forbid_nan_inf=False),
        return_selected_profile=True,
    )
    forged_abm_ref = attach_abm_identifiability_certificate_ref(
        store,
        simulation_result_ref=sim_ref,
        diagnostic_ref=IdentifiabilityDiagnosticRef.model_validate(
            forged_ref.model_dump(mode="python")
        ),
    )
    fresh_forged_abm = load_abm_result(_ensure_ir_artifact_store(fresh_store), forged_abm_ref)
    assert fresh_forged_abm.identifiability_certificate is not None
    assert fresh_forged_abm.identifiability_certificate.status == "diagnostic_attached"
    assert fresh_forged_abm.identifiability_certificate.identified is None
    assert (
        "diagnostic_verifier_provenance_not_admitted"
        in (fresh_forged_abm.identifiability_certificate.metadata["limitation_codes"])
    )
    assert str(fresh_forged_abm.identifiability_certificate.diagnostic_ref.artifact_id) == str(
        forged_ref.artifact_id
    )

    second_simulation = simulation.model_copy(update={"notes": ["different selected run"]})
    second_sim_payload = store.put_json(
        second_simulation,
        PutOptions(
            kind="foundry.simulation_result",
            media_type="application/json",
            schema=SchemaInfo(
                name=SimulationResult.ARTIFACT_SCHEMA_NAME,
                version=second_simulation.schema_version,
            ),
        ),
        return_selected_profile=True,
    )
    with pytest.raises(ValueError, match="not bound to this selected simulation"):
        attach_abm_identifiability_certificate_ref(
            store,
            simulation_result_ref=SimulationResultRef(artifact_id=second_sim_payload.artifact_id),
            diagnostic_ref=diagnostic_ref,
        )
    with pytest.raises(FileNotFoundError):
        attach_abm_identifiability_certificate_ref(
            store,
            simulation_result_ref=sim_ref,
            diagnostic_ref=IdentifiabilityDiagnosticRef(artifact_id=_artifact_id("f")),
        )

    diagnostic_payload = diagnostic.model_dump(mode="json")
    wrong_schema_ref = store.put_json(
        diagnostic_payload,
        PutOptions(
            kind="foundry.identifiability_diagnostic",
            media_type="application/json",
            schema=SchemaInfo(
                name="polisyos.core.IdentifiabilityDiagnosticResult",
                version="9.0",
            ),
        ),
        canon_spec=CanonSpec(forbid_floats=False, forbid_nan_inf=False),
        return_selected_profile=True,
    )
    with pytest.raises(
        ValueError,
        match="canon_profile_typed_artifact_schema_version_unsupported",
    ):
        attach_abm_identifiability_certificate_ref(
            store,
            simulation_result_ref=sim_ref,
            diagnostic_ref=IdentifiabilityDiagnosticRef(
                artifact_id=wrong_schema_ref.artifact_id,
                manifest_profile_sha256=wrong_schema_ref.manifest_profile_sha256,
            ),
        )

    # A matching manifest and payload version is still unsupported when the
    # typed artifact owner has no contract for that version.
    matched_unsupported_payload = diagnostic_payload | {"schema_version": "9.0"}
    matched_unsupported_ref = store.put_json(
        matched_unsupported_payload,
        PutOptions(
            kind="foundry.identifiability_diagnostic",
            media_type="application/json",
            schema=SchemaInfo(
                name="polisyos.core.IdentifiabilityDiagnosticResult",
                version="9.0",
            ),
            inputs=[
                InputRef(
                    artifact_id=sim_ref.artifact_id,
                    role="simulation_result",
                    manifest_profile_sha256=sim_ref.manifest_profile_sha256,
                )
            ],
        ),
        canon_spec=CanonSpec(forbid_floats=False, forbid_nan_inf=False),
        return_selected_profile=True,
    )
    with pytest.raises(
        ValueError,
        match="canon_profile_typed_artifact_schema_version_unsupported",
    ):
        attach_abm_identifiability_certificate_ref(
            store,
            simulation_result_ref=sim_ref,
            diagnostic_ref=IdentifiabilityDiagnosticRef(
                artifact_id=matched_unsupported_ref.artifact_id,
                manifest_profile_sha256=matched_unsupported_ref.manifest_profile_sha256,
            ),
        )

    wrong_kind_ref = store.put_json(
        diagnostic_payload,
        PutOptions(
            kind="foundry.unrelated_diagnostic",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.IdentifiabilityDiagnosticResult", version="1.0"),
        ),
        canon_spec=CanonSpec(forbid_floats=False, forbid_nan_inf=False),
        return_selected_profile=True,
    )
    with pytest.raises(ValueError):
        attach_abm_identifiability_certificate_ref(
            store,
            simulation_result_ref=sim_ref,
            diagnostic_ref=IdentifiabilityDiagnosticRef(
                artifact_id=wrong_kind_ref.artifact_id,
                manifest_profile_sha256=wrong_kind_ref.manifest_profile_sha256,
            ),
        )

    attractor_ref = persist_attractor_analysis_result(
        store,
        AttractorAnalysisResult(
            analysis_id="phase4-test-attractors",
            simulation_result_ref=sim_ref,
            state_projection=AttractorStateProjection(
                variables=["welfare"],
                reduced_dimension=1,
            ),
        ),
    )
    assert attractor_ref.manifest_profile_sha256 is not None
    bifurcation_abm_ref = attach_abm_bifurcation_report_ref(
        store,
        simulation_result_ref=sim_ref,
        attractor_analysis_ref=attractor_ref,
    )
    bifurcation_abm = load_abm_result(_ensure_ir_artifact_store(fresh_store), bifurcation_abm_ref)
    assert bifurcation_abm.bifurcation_report is not None
    assert bifurcation_abm.bifurcation_report.status == "available"
    assert bifurcation_abm.bifurcation_report.attractor_analysis_ref is not None
    assert bifurcation_abm.bifurcation_report.bifurcation_count == 0
    assert bifurcation_abm.bifurcation_report.attractor_count == 0
    with pytest.raises(ValueError, match="not bound to this selected simulation"):
        attach_abm_bifurcation_report_ref(
            store,
            simulation_result_ref=SimulationResultRef(artifact_id=second_sim_payload.artifact_id),
            attractor_analysis_ref=attractor_ref,
        )


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

    ref = persist_dynamic_microsim_validation_report(_ensure_ir_artifact_store(store), report)
    loaded = load_dynamic_microsim_validation_report(_ensure_ir_artifact_store(store), ref)
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
    from pydantic import BaseModel

    class LocalIndependencePayload(BaseModel):
        verification_status: str
        assumptions: list[str]

    store = FileSystemCAS(tmp_path)
    temporal = build_temporal_graph_causal_certificate(
        temporal_identification_certificate={"theorem_family": "local_independence"},
        local_independence_certificate=LocalIndependencePayload(
            verification_status="identified",
            assumptions=["observed_filtration"],
        ),
    )
    assert isinstance(temporal, TemporalGraphCausalCertificate)
    temporal_ref = persist_temporal_graph_causal_certificate(
        _ensure_ir_artifact_store(store), temporal
    )
    assert (
        load_temporal_graph_causal_certificate(_ensure_ir_artifact_store(store), temporal_ref)
        == temporal
    )

    space_time = build_space_time_causal_certificate(
        {
            "status": "model_extrapolation",
            "assumptions": {"consistency": "pass"},
            "caveats": ["policy_field_leaves_observed_treatment_range"],
        }
    )
    assert isinstance(space_time, SpaceTimeCausalCertificate)
    space_ref = persist_space_time_causal_certificate(_ensure_ir_artifact_store(store), space_time)
    assert (
        load_space_time_causal_certificate(_ensure_ir_artifact_store(store), space_ref)
        == space_time
    )


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
