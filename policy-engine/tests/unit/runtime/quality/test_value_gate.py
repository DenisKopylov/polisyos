from __future__ import annotations

import copy
import hashlib
import sys
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any, ClassVar

import pytest

from polisyos.core.contracts.value_outer_set import DataTrust, ValueOuterSet
from polisyos.core.observability.determinism import DeterminismTier
from polisyos.foundry.methods.backends.protocol import (
    MethodResult,
    MethodTiming,
    ReproducibilityInfo,
)
from polisyos.foundry.methods.base import (
    ComplexityClass,
    ComputeBackend,
    FidelityLevel,
    MethodSignature,
    SlotSpec,
    SlotType,
    Unit,
)
from polisyos.foundry.methods.catalog.bayesian.protocols import PosteriorResult
from polisyos.foundry.methods.catalog.bayesian.regression import (
    BayesianLinearRegressionEstimator,
)
from polisyos.foundry.methods.catalog.econometrics.protocols import (
    EconometricDiagnosticResult,
    EconometricResult,
)
from polisyos.foundry.methods.catalog.econometrics.timeseries import TimeSeriesEstimator
from polisyos.foundry.methods.components.consensus import EstimandSpec
from polisyos.foundry.methods.components.value_evidence import (
    MethodValueEvidence,
    MethodValueRefusal,
    project_method_value_evidence,
)
from polisyos.foundry.methods.selection import (
    MethodSelectionReceipt,
    reachable_value_method_fqns,
    select_value_method_for_problem,
)
from polisyos.ir.analytics.causal import (
    CausalEffectReport,
    CausalMethod,
    DiagnosticTest,
)
from polisyos.ir.analytics.distributional import (
    DistributionalBoundsBundle,
    DistributionalFunctional,
    FunctionalBounds,
    GridAxis,
)
from polisyos.ir.analytics.forecasting_uncertainty import (
    FanChartSpec,
    ForecastCalibrationMethod,
    ForecastCoverageDiagnostic,
    ForecastingUncertaintyBundle,
    ForecastIntervalSemantics,
    HorizonInterval,
    HorizonPolicySpec,
)
from polisyos.ir.analytics.partial_identification import (
    BoundMethod,
    BoundsBundle,
    PartialIdentificationResult,
)
from polisyos.ir.analytics.transportability import (
    TransportabilityResult,
    TransportabilityStatus,
    TransportMode,
)
from polisyos.ir.analytics.uncertainty import (
    IntervalSemantics,
    NativeValueEstimandBinding,
)
from polisyos.runtime.quality.acquisition_planner import (
    value_input_world_knowledge_requirement_gap,
)
from polisyos.runtime.quality.cycle_substrate import (
    CandidateLeverEvidence,
    CycleSubstrateContext,
    TransportContextEvidence,
    TransportCovariateObservation,
    build_cycle_substrate_context,
    cycle_substrate_context_binding_hash,
)
from polisyos.runtime.quality.design_problem import DesignProblem, OutcomeOfInterest
from polisyos.runtime.quality.generation_cycle import (
    FoundryValuePort,
    JointSimulationPort,
    RealValueOwnerGateway,
    SimulationPortObservation,
    ValueCalibrationReceipt,
    ValueDataProfile,
    ValueGateReceipt,
    ValueOwnerAccessError,
    ValuePortObservation,
    ValueTransportReceipt,
    _build_candidate_selection_diagram,
    _build_s10_forecast_inputs,
    _derived_value_data_modalities,
    _run_value_transport,
    _s10_calibration_evidence_from_report,
    _selector_problem_for_value_profile,
    _value_calibration_receipt,
    _value_outer_set_from_foundry_result,
    _value_owner_row,
)
from polisyos.runtime.quality.intervention_substrate import (
    InterventionLeverRefusal,
    resolve_intervention_lever,
)
from polisyos.runtime.quality.world_model_record import (
    BranchMode,
    DataForgeBindingRef,
    FabricWorldRef,
    FoundryBindingRef,
    PolicySlotBinding,
    ResolvedSubstrateEntryRef,
    SimulationModelRef,
    SkgCausalPriorRef,
    SubstrateRegistryRef,
    WorldModelRecord,
    world_model_record_content_hash,
)
from tools.quality.validation import check_layer3_gy_second_domain_pack as second_domain_pack
from tools.quality.validation import check_layer3_gy_value_gate_contract as value_contract

from .test_cycle_substrate import _registry as _lane0_registry
from .test_cycle_substrate import _world_record as _lane0_world_record
from .test_generation_cycle import _Atom, _Candidate, _problem


def _hash(char: str) -> str:
    return "sha256:" + char * 64


def _posterior_method_result(report: object) -> MethodResult:
    return MethodResult(
        output={"result": report},
        slot_outputs={"result": report},
        timing=MethodTiming(wall_time_ms=1.0),
        reproducibility=ReproducibilityInfo(
            backend=ComputeBackend.BAYESIAN,
            determinism_tier=DeterminismTier.STATISTICAL,
            seed=42,
        ),
    )


def _posterior_estimand(parameter: str = "coefficients_0") -> EstimandSpec:
    return EstimandSpec(
        query_id="candidate-credit-guarantee-value",
        estimand_id=parameter,
        outcome="avg_income",
        treatment_or_exposure="candidate_credit_guarantee:treatment",
        population="owner_resolved_country_year_rows",
        time_horizon="2017/2020",
        unit="avg_income",
        target_role="causal",
    )


def _value_contract_signature(*, output_contract: type[object], family: str) -> MethodSignature:
    return MethodSignature(
        name="value_projection_probe",
        namespace=family,
        version="1.0.0",
        input_slots=frozenset(),
        output_slots=frozenset(
            {
                SlotSpec.for_output_contract(
                    "result",
                    SlotType.SCALAR,
                    Unit("value", "json"),
                    output_contract=output_contract,
                )
            }
        ),
        parameters=(),
        fidelity=FidelityLevel.MEDIUM,
        complexity=ComplexityClass.O_1,
        family=family,
    )


def _projection_binding(
    report: object,
    *,
    estimand: EstimandSpec,
    signature: MethodSignature,
) -> NativeValueEstimandBinding:
    return NativeValueEstimandBinding.from_estimand(
        estimand=estimand,
        native_contract_id=str(type(report).contract_id),  # type: ignore[attr-defined]
        producer_method_fqn=signature.fqn,
        projection_input_content_hash=_hash("a"),
    )


def test_posterior_contract_projects_native_interval() -> None:
    estimand = _posterior_estimand()
    posterior = PosteriorResult(
        method_name="bayesian_linear_regression",
        posterior_means={"coefficients_0": 1.5},
        posterior_stds={"coefficients_0": 0.8},
        credible_intervals={"coefficients_0": (-2.0, 5.0)},
        sampler_family="mcmc",
        diagnostics={
            "credible_mass": 0.9,
            "num_samples": 128,
            "rhat_max": 1.01,
            "ess_bulk_min": 128.0,
            "ess_tail_min": 64.0,
            "quantile_mcse_relative_max": 0.05,
            "divergences": 0.0,
        },
    )
    binding = _projection_binding(
        posterior,
        estimand=estimand,
        signature=BayesianLinearRegressionEstimator.signature,
    )

    evidence = project_method_value_evidence(
        method_signature=BayesianLinearRegressionEstimator.signature,
        method_result=_posterior_method_result(posterior),
        estimand=estimand,
        selected_output_slot="result",
        projection_binding=binding,
    )

    assert isinstance(evidence, MethodValueEvidence)
    assert evidence.status == "contract_projection_ready"
    assert evidence.authority_scope == "contract_only_nonproduction"
    assert evidence.production_value_eligible is False
    assert evidence.envelope.confidence_interval == (-2.0, 5.0)
    assert evidence.native_contract_id == PosteriorResult.contract_id
    assert evidence.envelope.metadata["parameter"] == "coefficients_0"


def test_shaped_mapping_without_resolved_contract_id_refuses() -> None:
    shaped_report = {
        "method_name": "bayesian_linear_regression",
        "posterior_means": {"coefficients_0": 1.5},
        "credible_intervals": {"coefficients_0": (-2.0, 5.0)},
    }

    refusal = project_method_value_evidence(
        method_signature=BayesianLinearRegressionEstimator.signature,
        method_result=_posterior_method_result(shaped_report),
        estimand=_posterior_estimand(),
        selected_output_slot="result",
    )

    assert isinstance(refusal, MethodValueRefusal)
    assert refusal.reason_code == "method_output_contract_unresolved"


def test_pretty_interval_for_wrong_estimand_refuses() -> None:
    posterior = PosteriorResult(
        method_name="bayesian_linear_regression",
        posterior_means={"coefficients_0": 1.5},
        posterior_stds={"coefficients_0": 0.8},
        credible_intervals={"coefficients_0": (-2.0, 5.0)},
        diagnostics={"credible_mass": 0.9, "num_samples": 128},
    )

    refusal = project_method_value_evidence(
        method_signature=BayesianLinearRegressionEstimator.signature,
        method_result=_posterior_method_result(posterior),
        estimand=_posterior_estimand("education_teaching_method"),
        selected_output_slot="result",
    )

    assert isinstance(refusal, MethodValueRefusal)
    assert refusal.reason_code == "method_estimand_binding_mismatch"


def test_econometric_contract_projects_its_own_interval_without_family_branch() -> None:
    estimand = _posterior_estimand()
    report = EconometricResult(
        method_name="time_series_ols",
        params={"coefficients_0": 2.0},
        std_errors={"coefficients_0": 0.4},
        confidence_intervals={"coefficients_0": (1.1, 2.9)},
        n_obs=64,
    )
    binding = _projection_binding(
        report,
        estimand=estimand,
        signature=TimeSeriesEstimator.signature,
    )

    evidence = project_method_value_evidence(
        method_signature=TimeSeriesEstimator.signature,
        method_result=_posterior_method_result(report),
        estimand=estimand,
        selected_output_slot="result",
        projection_binding=binding,
    )

    assert isinstance(evidence, MethodValueEvidence)
    assert evidence.envelope.confidence_interval == (1.1, 2.9)
    assert evidence.native_contract_id == EconometricResult.contract_id


def test_diagnostic_only_contract_refuses_value_projection() -> None:
    diagnostic = EconometricDiagnosticResult(
        test_name="placebo",
        statistic=0.1,
        p_value=0.8,
        passed=True,
    )
    signature = TimeSeriesEstimator.signature.__class__(
        name="diagnostic_probe",
        namespace="econometrics.diagnostic",
        version="1.0.0",
        input_slots=frozenset(),
        output_slots=frozenset(
            {
                SlotSpec(
                    "result",
                    SlotType.SCALAR,
                    Unit("diagnostic", "json"),
                    contract_id=EconometricDiagnosticResult.contract_id,
                )
            }
        ),
        parameters=(),
        fidelity=TimeSeriesEstimator.signature.fidelity,
        complexity=TimeSeriesEstimator.signature.complexity,
    )

    refusal = project_method_value_evidence(
        method_signature=signature,
        method_result=_posterior_method_result(diagnostic),
        estimand=_posterior_estimand(),
        selected_output_slot="result",
    )

    assert isinstance(refusal, MethodValueRefusal)
    assert refusal.reason_code == "method_value_projection_capability_undeclared"


def test_forecasting_contract_projects_requested_native_horizon() -> None:
    now = datetime(2026, 7, 13, tzinfo=UTC)
    report = ForecastingUncertaintyBundle(
        method_fqn="forecasting.probe@1.0.0",
        target_id="avg_income",
        generated_at=now,
        prediction_interval=(
            HorizonInterval(
                horizon=1,
                point=10.0,
                lower=8.0,
                upper=13.0,
                coverage_target=0.9,
                constructor=ForecastCalibrationMethod.CONFORMAL,
                sample_count=64,
            ),
        ),
        fan_chart=FanChartSpec(quantile_levels=(), horizons=()),
        coverage_diagnostic=ForecastCoverageDiagnostic(
            nominal_coverage=0.9,
            empirical_coverage_by_horizon={1: 0.91},
            sample_count_by_horizon={1: 64},
            last_recalibrated_at=now,
        ),
        horizon_policy=HorizonPolicySpec(
            default_method=ForecastCalibrationMethod.CONFORMAL,
            gate_eligible=True,
        ),
        interval_semantics=ForecastIntervalSemantics.CONFORMALIZED_PREDICTION_INTERVAL,
        calibration_method=ForecastCalibrationMethod.CONFORMAL,
        nominal_coverage=0.9,
        sample_size_assumption="owner calibration rows",
    )
    estimand = replace(
        _posterior_estimand("avg_income"),
        time_horizon="1",
        target_role="prediction",
    )
    signature = _value_contract_signature(
        output_contract=ForecastingUncertaintyBundle,
        family="forecasting",
    )
    binding = _projection_binding(report, estimand=estimand, signature=signature)

    evidence = project_method_value_evidence(
        method_signature=signature,
        method_result=_posterior_method_result(report),
        estimand=estimand,
        selected_output_slot="result",
        projection_binding=binding,
    )

    assert isinstance(evidence, MethodValueEvidence)
    assert evidence.envelope.confidence_interval == (8.0, 13.0)
    assert evidence.envelope.interval_semantics is IntervalSemantics.CONFIDENCE_INTERVAL


def test_distributional_contract_projects_outer_hull_for_bound_estimand() -> None:
    estimand = _posterior_estimand("quantile_shift")
    signature = _value_contract_signature(
        output_contract=DistributionalBoundsBundle,
        family="distributional",
    )
    report = DistributionalBoundsBundle(
        estimand_type="quantile_shift",
        functional=DistributionalFunctional.QUANTILE_SHIFT,
        axis=GridAxis(axis_name="quantile", values=(0.25, 0.75), unit="probability"),
        consensus_bounds=FunctionalBounds(lower=(-2.0, -1.0), upper=(1.0, 4.0)),
        sharpness_status="outer_approx",
    )
    binding = _projection_binding(report, estimand=estimand, signature=signature)

    evidence = project_method_value_evidence(
        method_signature=signature,
        method_result=_posterior_method_result(report),
        estimand=estimand,
        selected_output_slot="result",
        projection_binding=binding,
    )

    assert isinstance(evidence, MethodValueEvidence)
    assert evidence.envelope.confidence_interval == (-2.0, 4.0)
    assert evidence.envelope.interval_semantics is IntervalSemantics.DETERMINISTIC_BOUNDS


def test_partial_identification_contract_projects_exact_native_bounds() -> None:
    estimand = _posterior_estimand("ate")
    signature = _value_contract_signature(
        output_contract=BoundsBundle,
        family="partial_identification",
    )
    report = BoundsBundle(
        estimand_type="ate",
        lower_bound=-0.5,
        upper_bound=1.25,
        consensus_lower=-0.5,
        consensus_upper=1.25,
        sharpness_status="sharp",
    )
    binding = _projection_binding(report, estimand=estimand, signature=signature)

    evidence = project_method_value_evidence(
        method_signature=signature,
        method_result=_posterior_method_result(report),
        estimand=estimand,
        selected_output_slot="result",
        projection_binding=binding,
    )

    assert isinstance(evidence, MethodValueEvidence)
    assert evidence.envelope.confidence_interval == (-0.5, 1.25)
    assert evidence.envelope.confidence_level is None


def test_transport_contract_projects_only_its_bound_native_region() -> None:
    estimand = _posterior_estimand("transported_ate")
    signature = _value_contract_signature(
        output_contract=TransportabilityResult,
        family="transport",
    )
    bounds = PartialIdentificationResult(
        method=BoundMethod.TRANSPORT_BOUNDS,
        lower_bound=-1.0,
        upper_bound=2.0,
        confidence=0.8,
        informativeness_threshold=4.0,
    )
    report = TransportabilityResult(
        query="transported_ate",
        status=TransportabilityStatus.BOUNDED_NON_IDENTIFIED,
        transport_mode=TransportMode.BOUNDS_ONLY,
        partial_identification_result=bounds,
    )
    binding = _projection_binding(report, estimand=estimand, signature=signature)

    evidence = project_method_value_evidence(
        method_signature=signature,
        method_result=_posterior_method_result(report),
        estimand=estimand,
        selected_output_slot="result",
        projection_binding=binding,
    )

    assert isinstance(evidence, MethodValueEvidence)
    assert evidence.envelope.confidence_interval == (-1.0, 2.0)

    mismatch = project_method_value_evidence(
        method_signature=signature,
        method_result=_posterior_method_result(report),
        estimand=_posterior_estimand("different_estimand"),
        selected_output_slot="result",
        projection_binding=binding,
    )
    assert isinstance(mismatch, MethodValueRefusal)
    assert mismatch.reason_code == "method_estimand_binding_mismatch"


def test_n8_audit_world_uses_canonical_design_problem_contract() -> None:
    """Keep the N8 rederive lane on the same typed boundary as production."""

    problem = value_contract._audit_problem()

    assert isinstance(problem, DesignProblem)
    assert problem.stakeholders
    assert problem.jurisdiction_time.region
    assert value_contract._audit_world_record().policy_domain == problem.domain


def test_n8_first_vertical_resolves_world_identity_before_value() -> None:
    """The real N4 atom reaches N5 despite scenario/WMR label drift."""

    lane = value_contract._canonical_first_vertical_lane()

    assert lane["problem"].domain == "ua_msme_cgf_decisive_capture"
    assert lane["world_model_record"].policy_domain == "fiscal_credit"
    assert lane["world_binding"].world_model_record_content_hash == (
        lane["world_model_record"].content_hash
    )
    assert lane["simulation"].status == "simulation_pending_n5"
    assert lane["simulation"].world_model_record is lane["world_model_record"]

    observation = FoundryValuePort(
        repo_root=Path.cwd(),
        cycle_substrate_context=lane["cycle_substrate_context"],
    )(
        candidate=lane["candidate"],
        simulation=lane["simulation"],
        problem=lane["problem"],
        cycle_index=0,
    )
    assert observation.authority_blockers == (
        "acquire_data:value_panel_data_missing",
    )
    assert observation.acquisition_requirement is not None


def test_n8_refuses_context_candidate_with_unresolved_world_slot() -> None:
    """N8 re-resolves the strict atom instead of trusting an N5-shaped carrier."""

    from polisyos.runtime.quality.intervention_atom_binding import (
        InterventionAtomBinding,
        intervention_atom_content_hash,
    )

    lane = value_contract._canonical_first_vertical_lane()
    estimand = lane["candidate"].atom.intended_downstream_estimand.model_copy(
        update={
            "metric_id": "avg_income",
            "outcome_variables": ("avg_income",),
        }
    )
    problem = lane["problem"].model_copy(
        update={
            "outcome_of_interest": lane["problem"].outcome_of_interest.model_copy(
                update={"target_variable": "avg_income", "metric_id": "avg_income"}
            )
        }
    )
    draft = lane["candidate"].atom.model_copy(
        update={
            "target_world_slots": ("missing.world_slot",),
            "intended_downstream_estimand": estimand,
        }
    )
    atom = draft.model_copy(update={"content_hash": intervention_atom_content_hash(draft)})
    atom = InterventionAtomBinding.model_validate(atom.model_dump(mode="python"))
    candidate = lane["candidate"].model_copy(update={"atom": atom})

    observation = FoundryValuePort(
        repo_root=Path.cwd(),
        cycle_substrate_context=lane["cycle_substrate_context"],
    )(
        candidate=candidate,
        simulation=lane["simulation"].model_copy(
            update={"candidate_id": candidate.candidate_id}
        ),
        problem=problem,
        cycle_index=0,
    )

    assert observation.status == "value_blocked"
    assert observation.authority_blockers == ("world_identity_unresolved",)


def test_n8_resolves_bound_world_before_routing_owner_data_gap() -> None:
    """A real owner gap cannot route a malformed bound atom into N7."""

    from polisyos.runtime.quality.intervention_atom_binding import (
        InterventionAtomBinding,
        intervention_atom_content_hash,
    )

    lane = value_contract._canonical_first_vertical_lane()
    draft = lane["candidate"].atom.model_copy(
        update={"target_world_slots": ("missing.world_slot",)}
    )
    atom = draft.model_copy(update={"content_hash": intervention_atom_content_hash(draft)})
    atom = InterventionAtomBinding.model_validate(atom.model_dump(mode="python"))
    candidate = lane["candidate"].model_copy(update={"atom": atom})

    observation = FoundryValuePort(
        repo_root=Path.cwd(),
        cycle_substrate_context=lane["cycle_substrate_context"],
    )(
        candidate=candidate,
        simulation=lane["simulation"].model_copy(
            update={"candidate_id": candidate.candidate_id}
        ),
        problem=lane["problem"],
        cycle_index=0,
    )

    assert observation.status == "value_blocked"
    assert observation.authority_blockers == ("world_identity_unresolved",)
    assert observation.acquisition_requirement is None


def test_n8_first_vertical_real_cycle_routes_owner_data_gap_through_n7() -> None:
    """The real N4 candidate reaches a typed N7 plan without simulated re-entry."""

    run = value_contract._run_real_first_vertical_cycle()
    assert len(run.cycles) == 1
    cycle = run.cycles[0]
    owner_candidate = value_contract._canonical_first_vertical_lane()["candidate"]

    assert cycle.selected_candidate_ref == owner_candidate.candidate_id
    assert cycle.value_port.authority_blockers == (
        "acquire_data:value_panel_data_missing",
    )
    assert cycle.terminal_kind == "acquisition_required"
    assert cycle.acquisition_receipt is None
    assert cycle.acquisition_routing_report is not None
    assert cycle.acquisition_routing_report.status == "pass"
    assert len(cycle.acquisition_routing_report.acquisition_records) == 1
    record = cycle.acquisition_routing_report.acquisition_records[0]
    assert record.recommended_strategy.value == "production_snapshot_build"
    assert record.terminal_disposition.value == "acquire"
    assert record.claim_ref == f"value-claim:{cycle.selected_candidate_ref}"


def test_n8_v2_frozen_payload_records_only_honest_fork_b_terminals() -> None:
    payload = value_contract.build_payload(value_contract._repo_root())

    assert payload["schema_version"].endswith(".v2")
    assert "frozen_positive_receipt" not in payload
    assert "frozen_value_receipts" not in payload
    assert "decisive_mutations" not in payload
    assert {row["mutation_id"] for row in payload["decisive_mutation_expectations"]} == set(
        value_contract.EXPECTED_MUTATION_IDS
    )
    assert all(
        row["expected_result"] == "RED" and "observed_result" not in row and "result" not in row
        for row in payload["decisive_mutation_expectations"]
    )
    expected_denominators = value_contract._catalog_denominators()
    assert payload["denominators"] == expected_denominators
    assert (
        payload["denominators"]["registered_method_count"]
        == payload["denominators"]["catalog_entry_count"]
    )
    assert payload["denominators"]["value_capable_method_count"] == len(
        payload["denominators"]["value_capable_methods"]
    )
    provenance = payload["denominators"]["catalog_provenance"]
    assert provenance["governed_discovery"]["source_policy"] == {
        "include_builtins": True,
        "include_entry_points": False,
        "include_dev_scan": False,
    }
    ambient_admission = provenance["ambient_discovery"]["admission"]
    assert ambient_admission["status"] in {
        "quarantined_unbound",
        "declared_not_admitted",
    }
    assert ambient_admission["included_in_governed_denominator"] is False
    assert ambient_admission["fail_closed_action"] == "quarantine"
    assert len(payload["native_projector_contract_proofs"]) == 6
    assert {proof["family"] for proof in payload["native_projector_contract_proofs"]} == {
        "posterior",
        "econometric",
        "forecasting",
        "distributional",
        "partial_identification",
        "transport",
    }
    assert all(
        proof["authority_scope"] == "contract_only_nonproduction"
        and proof["production_value_eligible"] is False
        and proof["status"].startswith("contract_projection_")
        and "value_outer_set" not in proof
        and "value_gate_receipt" not in proof
        for proof in payload["native_projector_contract_proofs"]
    )
    production = payload["production_refusal"]
    assert production["status"] == "value_blocked"
    assert production["authority_blockers"] == ["acquire_data:value_panel_data_missing"]
    assert production["selection_stage"] == "not_reached_owner_data_unavailable"
    assert production["selected_method_fqn"] is None
    assert production["method_selection_receipt"] is None
    assert production["owner_availability"]["variable_id"] == ("employment_retention")
    assert production["value_receipt"] is None
    route = payload["acquisition_routing"]
    assert route["terminal_kind"] == "acquisition_required"
    assert route["simulated_reentry"] is False
    assert route["acquisition_receipt"] is None
    assert route["requirement_gap"]["metadata"]["source"] == ("l1_dcat_variable_availability")
    assert route["planner_report"]["status"] == "pass"
    assert (
        route["planner_report"]["acquisition_records"][0]["recommended_strategy"]
        == "production_snapshot_build"
    )
    education = payload["education_refusal"]
    assert education["status"] == "value_blocked"
    assert education["authority_blockers"] == ["method_estimand_binding_mismatch"]
    assert education["method_selection_receipt"] is not None
    assert education["value_receipt"] is None


def _catalog_provenance_comparison_fixture() -> dict[str, Any]:
    return {
        "schema_version": "policyos.method_catalog_provenance_manifest.v1",
        "provenance_id": "method_catalog_provenance_fixture",
        "governed_discovery": {
            "source_policy": {
                "include_builtins": True,
                "include_entry_points": False,
                "include_dev_scan": False,
            },
            "manifest_id": "component_discovery_manifest_builtin",
            "component_count": 389,
            "component_set_sha256": _hash("1"),
            "registry_fqn_set_sha256": _hash("2"),
            "registry_binding_sha256": _hash("8"),
            "unbound_inputs": [],
        },
        "ambient_discovery": {
            "source_policy": {
                "include_builtins": False,
                "include_entry_points": True,
                "include_dev_scan": True,
            },
            "manifest_id": "component_discovery_manifest_ambient",
            "entry_points": [
                {
                    "group": "polisyos.foundry_methods",
                    "name": "example.weighted_average",
                    "value": "example:factory",
                    "distribution_name": "example",
                    "distribution_version": "1.0.0",
                    "entry_points_sha256": _hash("3"),
                    "direct_url_sha256": None,
                    "editable_install": True,
                    "source_byte_closure": "not_established",
                }
            ],
            "dev_scan_roots": [],
            "dev_scan_files": [],
            "component_count": 1,
            "component_set_sha256": _hash("5"),
            "added_component_ids": ["example.weighted_average@1.0.0"],
            "overlap_component_count": 0,
            "overlap_component_set_sha256": _hash("6"),
            "unbound_inputs": ["entry_point_source_byte_closure_not_established"],
            "admission": {
                "status": "quarantined_unbound",
                "included_in_governed_denominator": False,
                "fail_closed_action": "quarantine",
            },
        },
        "runtime_backend_identity": {
            "identity_id": "method_catalog_runtime_identity_fixture",
            "runtime_packages": [
                {"name": "policy-engine", "version": "0.1.0"},
                {"name": "python", "version": "3.14.0"},
            ],
            "backend_fingerprints": [{"backend": "numpy", "fingerprint": "fingerprint-a"}],
            "entry_runtime_binding_count": 389,
            "entry_runtime_bindings_sha256": _hash("7"),
        },
        "predicate_provenance": [
            {
                "predicate": "governed.source_policy",
                "classification": "recomputed",
                "decisive": True,
                "fail_closed_action": "reject",
            },
            {
                "predicate": "ambient.entry_point_source_byte_closure",
                "classification": "not_established",
                "decisive": False,
                "fail_closed_action": "quarantine",
            },
        ],
        "predicate_bindings": {},
        "predicate_admission_policy": [
            {
                "classification": "recomputed",
                "admitted": True,
                "fail_closed_action": None,
            },
            {
                "classification": "independently_reconciled",
                "admitted": True,
                "fail_closed_action": None,
            },
            *[
                {
                    "classification": classification,
                    "admitted": False,
                    "fail_closed_action": "reject_or_quarantine",
                }
                for classification in (
                    "consumer_asserted",
                    "institutionally_supplied",
                    "not_established",
                )
            ],
        ],
    }


def test_n8_catalog_provenance_records_editable_identity_as_quarantined() -> None:
    from polisyos.foundry.methods.catalog.snapshot import method_catalog_provenance_id

    provenance = _catalog_provenance_comparison_fixture()
    provenance["provenance_id"] = method_catalog_provenance_id(provenance)

    entry = provenance["ambient_discovery"]["entry_points"][0]
    assert entry["editable_install"] is True
    assert entry["direct_url_sha256"] is None
    assert entry["source_byte_closure"] == "not_established"
    assert provenance["ambient_discovery"]["admission"] == {
        "status": "quarantined_unbound",
        "included_in_governed_denominator": False,
        "fail_closed_action": "quarantine",
    }
    predicate = next(
        row
        for row in provenance["predicate_provenance"]
        if row["predicate"] == "ambient.entry_point_source_byte_closure"
    )
    assert predicate == {
        "predicate": "ambient.entry_point_source_byte_closure",
        "classification": "not_established",
        "decisive": False,
        "fail_closed_action": "quarantine",
    }
    admission = next(
        row
        for row in provenance["predicate_admission_policy"]
        if row["classification"] == "not_established"
    )
    assert admission == {
        "classification": "not_established",
        "admitted": False,
        "fail_closed_action": "reject_or_quarantine",
    }
    assert value_contract._catalog_provenance_issues(provenance, provenance) == ()


def test_n8_catalog_provenance_accepts_same_editable_source_from_two_paths(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    import json

    from polisyos.core.components import (
        Capability,
        ComponentId,
        ComponentKind,
        ComponentMetadata,
    )
    from polisyos.core.components.discovery import (
        ENTRY_POINT_GROUP_FOUNDRY_METHODS,
        discover_components,
    )
    from polisyos.foundry.extensions.registry import bootstrap_foundry_method_registry
    from polisyos.foundry.methods.catalog.snapshot import (
        build_method_catalog_provenance_manifest,
        build_method_catalog_snapshot,
    )
    from polisyos.foundry.methods.selection.registry import registry_scope

    class _BridgeComponent:
        metadata = ComponentMetadata(
            component_id=ComponentId.parse("roads.method.direct_url_bridge@1.0.0"),
            kind=ComponentKind.FOUNDRY_METHOD,
            abi_targets={"foundry_methods_api": ">=3.5.0,<4.0.0"},
            domains=["roads"],
            jurisdictions=[],
            tags=[],
            capabilities=Capability.FOUNDRY_METHOD,
            deps=[],
        )

        def create(self) -> object:
            return object()

    class _Distribution:
        metadata: ClassVar[dict[str, str]] = {"Name": "roads-direct-url-bridge"}
        version: ClassVar[str] = "1.0.0"

        def __init__(self, direct_url_text: str) -> None:
            self._direct_url_text = direct_url_text

        def read_text(self, filename: str) -> str | None:
            if filename == "entry_points.txt":
                return (
                    "[polisyos.foundry_methods]\n"
                    "roads.method.direct_url_bridge = roads.method.direct_url_bridge:factory\n"
                )
            if filename == "direct_url.json":
                return self._direct_url_text
            return None

    class _EntryPoint:
        group = ENTRY_POINT_GROUP_FOUNDRY_METHODS
        name = "roads.method.direct_url_bridge"
        value = "roads.method.direct_url_bridge:factory"
        module = "roads.method.direct_url_bridge"
        attr = "factory"

        def __init__(self, distribution: _Distribution) -> None:
            self.dist = distribution

        @staticmethod
        def load() -> _BridgeComponent:
            return _BridgeComponent()

    def _ambient_manifest(checkout: Path):
        entry_point = _EntryPoint(
            _Distribution(
                json.dumps(
                    {
                        "url": checkout.resolve().as_uri(),
                        "dir_info": {"editable": True},
                    },
                    separators=(",", ":"),
                )
            )
        )
        monkeypatch.setattr(
            "polisyos.core.components.discovery.list_entry_points",
            lambda *, group: [entry_point],
        )
        report = discover_components(
            groups=[ENTRY_POINT_GROUP_FOUNDRY_METHODS],
            include_dev_scan=True,
            dev_scan_paths=[],
        )
        assert report.manifest is not None
        return report.manifest

    first_checkout = tmp_path / "checkout-a" / "policy-engine"
    second_checkout = tmp_path / "checkout-b" / "policy-engine"
    first_checkout.mkdir(parents=True)
    second_checkout.mkdir(parents=True)
    sentinel = b"same source bytes\n"
    (first_checkout / "source.py").write_bytes(sentinel)
    (second_checkout / "source.py").write_bytes(sentinel)
    assert first_checkout.resolve() != second_checkout.resolve()
    assert (first_checkout / "source.py").read_bytes() == (
        second_checkout / "source.py"
    ).read_bytes()

    with registry_scope() as registry:
        governed_report = bootstrap_foundry_method_registry(
            registry,
            include_builtins=True,
            include_entry_points=False,
            include_dev_scan=False,
            require_bound_discovery_manifest=True,
        )
        snapshot = build_method_catalog_snapshot(
            registry=registry,
            registry_report=governed_report,
            require_bound_discovery=True,
        )
    first = build_method_catalog_provenance_manifest(
        snapshot,
        registry_report=governed_report,
        ambient_manifest=_ambient_manifest(first_checkout),
    )
    second = build_method_catalog_provenance_manifest(
        snapshot,
        registry_report=governed_report,
        ambient_manifest=_ambient_manifest(second_checkout),
    )

    assert first["ambient_discovery"]["entry_points"][0]["direct_url_sha256"] is None
    assert second["ambient_discovery"]["entry_points"][0]["direct_url_sha256"] is None
    assert first["provenance_id"] == second["provenance_id"]
    assert value_contract._catalog_provenance_issues(first, second) == ()


def test_n8_catalog_provenance_rejects_changed_content_bound_distribution_identity() -> None:
    from polisyos.foundry.methods.catalog.snapshot import method_catalog_provenance_id

    expected = _catalog_provenance_comparison_fixture()
    expected_entry = expected["ambient_discovery"]["entry_points"][0]
    expected_entry["editable_install"] = False
    expected_entry["direct_url_sha256"] = _hash("bound-wheel-a")
    expected["provenance_id"] = method_catalog_provenance_id(expected)
    recorded = copy.deepcopy(expected)
    recorded["ambient_discovery"]["entry_points"][0]["direct_url_sha256"] = _hash(
        "bound-wheel-b"
    )
    recorded["provenance_id"] = method_catalog_provenance_id(recorded)

    codes = {
        issue["code"]
        for issue in value_contract._catalog_provenance_issues(recorded, expected)
    }

    assert "catalog_entry_point_distribution_manifest_mismatch" in codes
    assert "catalog_provenance_content_hash_mismatch" not in codes


def test_n8_catalog_provenance_names_environment_before_count_drift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected_denominators = value_contract._catalog_denominators()
    recorded_denominators = copy.deepcopy(expected_denominators)
    entry_points = recorded_denominators["catalog_provenance"]["ambient_discovery"][
        "entry_points"
    ]
    if entry_points:
        entry_points[0]["distribution_name"] = "different-environment"
    else:
        entry_points.append(
            {
                "group": "polisyos.foundry_methods",
                "name": "different-environment",
                "value": "different_environment:factory",
                "distribution_name": "different-environment",
                "distribution_version": "0",
                "entry_points_sha256": _hash("9"),
                "direct_url_sha256": None,
                "editable_install": None,
                "source_byte_closure": "not_established",
            }
        )
    recorded_denominators["registered_method_count"] += 1
    monkeypatch.setattr(
        value_contract,
        "_catalog_denominators_cached",
        lambda: expected_denominators,
    )
    payload = {
        "schema_version": value_contract.SCHEMA_VERSION,
        "rule_version": value_contract.VALUE_GATE_RULE_VERSION,
        "denominators": recorded_denominators,
    }

    codes = {issue["code"] for issue in value_contract.validate_payload(payload)}

    assert "catalog_entry_point_distribution_manifest_mismatch" in codes
    assert "catalog_method_denominator_drift" not in codes


@pytest.mark.parametrize(
    ("section", "field", "corrupt_value", "expected_code"),
    [
        (
            "ambient_discovery",
            "admission",
            {
                "status": "declared_not_admitted",
                "included_in_governed_denominator": False,
                "fail_closed_action": "quarantine",
            },
            "catalog_ambient_admission_mismatch",
        ),
        (
            "runtime_backend_identity",
            "schema_version",
            "policyos.method_catalog_runtime_identity.forged",
            "catalog_runtime_backend_identity_mismatch",
        ),
    ],
)
def test_n8_catalog_provenance_recomputes_recorded_manifest_identity(
    section: str,
    field: str,
    corrupt_value: object,
    expected_code: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected_denominators = value_contract._catalog_denominators()
    recorded_denominators = copy.deepcopy(expected_denominators)
    recorded_denominators["catalog_provenance"][section][field] = corrupt_value
    monkeypatch.setattr(
        value_contract,
        "_catalog_denominators_cached",
        lambda: expected_denominators,
    )
    payload = {
        "schema_version": value_contract.SCHEMA_VERSION,
        "rule_version": value_contract.VALUE_GATE_RULE_VERSION,
        "denominators": recorded_denominators,
    }

    codes = {issue["code"] for issue in value_contract.validate_payload(payload)}

    assert expected_code in codes
    assert "catalog_provenance_content_hash_mismatch" in codes


def test_n8_catalog_predicate_bindings_cover_every_denominator_field() -> None:
    denominators = value_contract._catalog_denominators()
    provenance = denominators["catalog_provenance"]
    bindings = provenance["predicate_bindings"]
    predicate_names = {
        row["predicate"] for row in provenance["predicate_provenance"]
    }

    assert set(bindings) == set(denominators) - {"catalog_provenance"}
    assert all(references for references in bindings.values())
    assert all(
        reference in predicate_names
        for references in bindings.values()
        for reference in references
    )
    corrupt = copy.deepcopy(provenance)
    corrupt["predicate_bindings"].pop("registered_method_count")

    codes = {
        issue["code"]
        for issue in value_contract._catalog_provenance_issues(
            corrupt,
            provenance,
            denominator_fields=frozenset(denominators) - {"catalog_provenance"},
        )
    }

    assert "catalog_predicate_binding_coverage_mismatch" in codes


@pytest.mark.parametrize(
    "classification",
    ["consumer_asserted", "institutionally_supplied", "not_established"],
)
def test_n8_catalog_provenance_fails_decisive_untrusted_predicates_closed(
    classification: str,
) -> None:
    expected = _catalog_provenance_comparison_fixture()
    recorded = copy.deepcopy(expected)
    recorded["predicate_provenance"][0]["classification"] = classification

    codes = {
        issue["code"] for issue in value_contract._catalog_provenance_issues(recorded, expected)
    }

    assert "catalog_predicate_provenance_not_admissible" in codes


def test_n8_transport_component_proofs_are_live_and_data_derived() -> None:
    """A1 freezes owner executions, including an honest missing-context terminal."""

    proofs = value_contract._transport_component_proofs()

    first = proofs["first_vertical"]
    assert first["outcome_kind"] == "typed_refusal"
    assert first["typed_refusal"]["code"] == (
        "acquire_data:transport_context_unresolved"
    )
    assert first["transport_covariates"] == []
    assert first["selection_diagram_content_hash"] is None
    assert first["transport_receipt"] is None

    for role in ("education", "unseen_pack_shape"):
        proof = proofs[role]
        assert proof["outcome_kind"] == "transport_receipt"
        assert proof["typed_refusal"] is None
        assert proof["selection_diagram_content_hash"].startswith("sha256:")
        assert proof["transport_covariates"]
        receipt = proof["transport_receipt"]
        assert receipt["transport_status"]
        assert receipt["transport_mode"]
        assert receipt["identification_engine"]
        assert proof["transport_result_content_hash"] == value_contract.gy_content_hash(
            receipt
        )

    water = proofs["unseen_pack_shape"]
    assert water["domain"] == "water_quality"
    assert water["query_treatment"] == "riparian_buffer_width"
    assert water["query_outcome"] == "nitrate_load"
    assert water["transport_covariates"] == [
        {
            "canonical_var": "watershed_slope",
            "source_value": 0.15,
            "target_value": 0.63,
            "source_row_content_hash": water["selection_nodes"][0]["source_ref"],
            "target_row_content_hash": water["selection_nodes"][0]["target_ref"],
        }
    ]


def test_n8_transport_component_validator_rejects_static_or_malformed_receipts() -> None:
    proofs = value_contract._transport_component_proofs()
    malformed = copy.deepcopy(proofs)
    malformed["education"]["transport_receipt"]["transport_status"] = ""
    malformed["education"]["proof_content_hash"] = value_contract.gy_content_hash(
        {
            key: value
            for key, value in malformed["education"].items()
            if key != "proof_content_hash"
        }
    )
    static = malformed["unseen_pack_shape"]
    static["outcome_kind"] = "behavioral_probe_in_focused_test"
    static["proof_content_hash"] = value_contract.gy_content_hash(
        {key: value for key, value in static.items() if key != "proof_content_hash"}
    )

    codes = {
        issue["code"]
        for issue in value_contract._validate_transport_component_proofs(malformed)
    }

    assert "transport_component_receipt_invalid" in codes
    assert "transport_component_outcome_kind_invalid" in codes


def test_n8_source_flip_runner_requires_semantic_red_and_restores_bytes(
    tmp_path: Path,
) -> None:
    source = tmp_path / "owner.py"
    source.write_text("guard = True\n", encoding="utf-8")
    original_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    case = value_contract._SourceFlipCase(
        mutation_id="source_flip_unit_semantic_red",
        guard="unit semantic guard",
        replacements=(
            value_contract._SourceFlipReplacement(
                "owner.py",
                "guard = True\n",
                "guard = False\n",
            ),
        ),
        probe_command=(
            sys.executable,
            "-c",
            "print('MUTATION_RED:source_flip_unit_semantic_red'); raise SystemExit(1)",
        ),
        expected_red_patterns=("MUTATION_RED:source_flip_unit_semantic_red",),
    )

    result = value_contract._run_source_flip_case(tmp_path, case)

    assert result["result"] == "RED"
    assert source.read_text(encoding="utf-8") == "guard = True\n"
    assert result["source_restored_sha256"]["owner.py"] == original_hash


def test_n8_editable_direct_url_binding_source_flip_turns_red() -> None:
    case = next(
        row
        for row in value_contract._source_flip_cases()
        if row.mutation_id == "source_flip_editable_direct_url_address_rejected"
    )

    result = value_contract._run_source_flip_case(value_contract._repo_root(), case)

    assert result["result"] == "RED"
    assert result["proof"]["exit_code"] == 1
    assert "test_n8_catalog_provenance_accepts_same_editable_source_from_two_paths" in (
        result["proof"]["stdout_tail"]
    )
    assert "src/polisyos/core/components/discovery.py" in result[
        "source_restored_sha256"
    ]


def test_n8_source_flip_runner_rejects_probe_errors_as_harness_failures(
    tmp_path: Path,
) -> None:
    source = tmp_path / "owner.py"
    source.write_text("guard = True\n", encoding="utf-8")
    case = value_contract._SourceFlipCase(
        mutation_id="source_flip_unit_probe_error",
        guard="unit probe guard",
        replacements=(
            value_contract._SourceFlipReplacement(
                "owner.py",
                "guard = True\n",
                "guard = False\n",
            ),
        ),
        probe_command=(sys.executable, "-c", "raise SystemExit(5)"),
        expected_red_patterns=("MUTATION_RED:source_flip_unit_probe_error",),
    )

    result = value_contract._run_source_flip_case(tmp_path, case)

    assert result["result"] == "PROBE_ERROR"
    assert source.read_text(encoding="utf-8") == "guard = True\n"


def test_n8_source_flip_runner_rejects_ambiguous_mutation_target(tmp_path: Path) -> None:
    source = tmp_path / "owner.py"
    source.write_text("guard = True\nguard = True\n", encoding="utf-8")
    case = value_contract._SourceFlipCase(
        mutation_id="source_flip_unit_ambiguous_target",
        guard="unit target guard",
        replacements=(
            value_contract._SourceFlipReplacement(
                "owner.py",
                "guard = True\n",
                "guard = False\n",
            ),
        ),
        probe_command=(sys.executable, "-c", "raise SystemExit(1)"),
        expected_red_patterns=("MUTATION_RED:source_flip_unit_ambiguous_target",),
    )

    result = value_contract._run_source_flip_case(tmp_path, case)

    assert result["result"] == "MUTATION_TARGET_ERROR"
    assert source.read_text(encoding="utf-8") == "guard = True\nguard = True\n"


def test_n8_v2_validator_rejects_fabricated_positive_and_contract_authority() -> None:
    payload = value_contract.build_payload(value_contract._repo_root())
    payload["production_refusal"]["status"] = "value_ready"
    payload["production_refusal"]["value_receipt"] = {"fabricated": True}
    payload["native_projector_contract_proofs"][0]["production_value_eligible"] = True
    first_transport = payload["transport_component_proofs"]["first_vertical"]
    first_transport["candidate_id"] = "candidate_transplanted"
    first_transport["proof_content_hash"] = value_contract.gy_content_hash(
        {
            key: value
            for key, value in first_transport.items()
            if key != "proof_content_hash"
        }
    )
    payload["contract_content_hash"] = value_contract._content_hash(payload)

    codes = {issue["code"] for issue in value_contract.validate_payload(payload)}

    assert "fabricated_production_value_ready" in codes
    assert "contract_projection_claimed_production_authority" in codes
    assert "first_vertical_transport_receipt_unbound" in codes


def _world_record(char: str = "1") -> WorldModelRecord:
    fields: dict[str, Any] = {
        "schema_version": "policyos.runtime.world_model_record.v1",
        "authority_status": "bound",
        "producer_ref": f"tests.unit.runtime.quality.test_value_gate.{char}",
        "region_or_jurisdiction": "UA-30",
        "population_scope": "wartime_msme",
        "policy_domain": "fiscal_credit",
        "valid_time_scope": "2026-05-24/2026-12-31",
        "tx_time_scope": "2026-05-24T12:00:00+00:00",
        "resolution": "firm_month",
        "branch_mode": BranchMode.OBSERVED,
        "fabric_world_ref": FabricWorldRef(
            snapshot_root="/tmp/policyos-value-gate-world",
            snapshot_id=f"snapshot-2026-05-24-{char}",
            branch="main",
            world_query_policy="as_of_valid_and_tx_time",
            provenance_manifest_ref=f"manifest://value-gate/{char}",
            content_query_digest=_hash(char),
            content_query_row_count=3,
        ),
        "data_forge_binding_ref": DataForgeBindingRef(
            snapshot_id=f"snapshot-2026-05-24-{char}",
            release_id=f"release-{char}",
            role="academic",
            read_api_identity="data_forge.read_api.value_gate",
            snapshot_ref=f"snapshot://data-forge/value-gate/{char}",
            merkle_root=f"merkle:value-gate:{char}",
            data_hash=_hash("a"),
            provenance_manifest_ref=f"manifest://data-forge/value-gate/{char}",
        ),
        "simulation_model_ref": SimulationModelRef(
            model_spec_ref=_hash("b"),
            model_spec_hash=_hash("c"),
            model_id="model_ua_msme_value_gate",
            data_snapshot_ref=_hash("d"),
            registry_bundle_ref=_hash("e"),
            ncm_refs=("ncm://fixture/value-gate",),
            fidelity_level="high",
            calibrated=True,
            calibration_ref=_hash("f"),
        ),
        "foundry_binding_ref": FoundryBindingRef(
            input_bindings_ref=_hash("0"),
            bound_state_snapshot_ref=_hash("2"),
            mapping_rules_ref=_hash("3"),
            state_slot_digest=_hash("4"),
        ),
        "skg_causal_prior_ref": SkgCausalPriorRef(
            skg_snapshot_ref=f"skg://value-gate/{char}",
            skg_version_id=f"skg-v{char}",
            source_data_snapshot_id=f"snapshot-2026-05-24-{char}",
        ),
        "substrate_registry_ref": SubstrateRegistryRef(
            substrate_version_id="substrate_version_1111111111111111",
            content_hash=_hash("5"),
            resolved_entries=(
                ResolvedSubstrateEntryRef(
                    source_id="l5_measurement_registry",
                    family_id="firm_fundamentals",
                    layer="L5",
                    coverage_score=0.8,
                    trust_tier="authoritative_partial_coverage",
                    trust_cap=0.85,
                    identification_mode="point_identified",
                    schema_regime_id="ukraine_schema_v2",
                    data_version="l5-calibration-d2",
                    snapshot_id=f"snapshot-2026-05-24-{char}",
                    source_snapshot_id=f"snapshot-2026-05-24-{char}",
                    entry_content_hash=_hash("6"),
                ),
            ),
        ),
        "policy_slot_map": (
            PolicySlotBinding(
                slot_id="firm_survival",
                state_path="firms.survival",
                entity_scope="firm",
                temporal_granularity="month",
            ),
            PolicySlotBinding(
                slot_id="government_balance",
                state_path="government.balance",
                entity_scope="government",
                temporal_granularity="month",
            ),
        ),
    }
    candidate = WorldModelRecord.model_construct(
        world_model_record_id="world_model_record_0000000000000000",
        content_hash=_hash("0"),
        **fields,
    )
    content_hash = world_model_record_content_hash(candidate)
    return WorldModelRecord(
        world_model_record_id=f"world_model_record_{content_hash.removeprefix('sha256:')[:16]}",
        content_hash=content_hash,
        **fields,
    )


def _candidate() -> _Candidate:
    return _Candidate(
        candidate_id="candidate_value_gate",
        atom=_Atom("candidate_value_gate", _hash("2")),
        diversity_key=("grant", "firms", "panel", "value_gate"),
    )


@dataclass(frozen=True)
class _ValueAtom:
    intervention_id: str
    content_hash: str
    status: str = "candidate_unverified"
    world_model_record_ref: str | None = "world_model_record_test"
    target_world_slots: tuple[str, ...] = ("avg_income",)


def _avg_income_problem() -> Any:
    return _problem("value_gate_avg_income_problem").model_copy(
        update={
            "outcome_of_interest": OutcomeOfInterest(
                target_variable="avg_income",
                metric_id="avg_income",
                estimand="average_treatment_effect",
            )
        }
    )


def _avg_income_candidate() -> _Candidate:
    return _Candidate(
        candidate_id="candidate_avg_income_real",
        atom=_ValueAtom("candidate_avg_income_real", _hash("8")),
        diversity_key=("grant", "country", "avg_income", "real_panel"),
    )


def _pack_shaped_transport_context(
    *,
    problem: DesignProblem,
    covariates: tuple[tuple[str, float, float], ...],
) -> CycleSubstrateContext:
    """Build a content-bound Lane-0 context from arbitrary pack-shaped data."""

    registry = _lane0_registry(problem.domain)
    world = _lane0_world_record(problem.domain, registry)
    selected_hash = registry.entries[0].entry_content_hash
    problem_ref = second_domain_pack.gy_content_hash(problem.model_dump(mode="json"))
    substrate_input_hash = second_domain_pack.gy_content_hash(
        {
            "domain": problem.domain,
            "registry": registry.content_hash,
            "covariates": covariates,
        }
    )
    binding_hash = cycle_substrate_context_binding_hash(
        design_problem_ref=problem_ref,
        domain=problem.domain,
        substrate_input_content_hash=substrate_input_hash,
        substrate_registry_content_hash=registry.content_hash,
        world_model_record_id=world.world_model_record_id,
        world_model_record_content_hash=world.content_hash,
        world_model_record_authority_status=world.authority_status,
        selected_registry_entry_hashes=(selected_hash,),
    )
    lever = CandidateLeverEvidence(
        lever_id=f"{problem.domain}_lever",
        instrument=f"{problem.domain}.lever",
        target_concept=problem.outcome_of_interest.target_variable,
        entry_content_hash=second_domain_pack.gy_content_hash(
            {"domain": problem.domain, "kind": "candidate_lever"}
        ),
        substrate_input_content_hash=substrate_input_hash,
        selected_registry_entry_hash=selected_hash,
        context_binding_hash=binding_hash,
        source_refs=(f"lane0://{problem.domain}/candidate-lever",),
    )
    transport = None
    if covariates:
        transport = TransportContextEvidence(
            status="candidate_context_only_not_transport_authority",
            source_context_id=f"{problem.domain}:source",
            target_context_id=f"{problem.domain}:target",
            source_profile_content_hash=_hash("a"),
            target_profile_content_hash=_hash("b"),
            substrate_input_content_hash=substrate_input_hash,
            context_binding_hash=binding_hash,
            covariates=tuple(
                TransportCovariateObservation(
                    canonical_var=name,
                    source_value=source_value,
                    target_value=target_value,
                    source_row_content_hash=second_domain_pack.gy_content_hash(
                        {
                            "domain": problem.domain,
                            "covariate": name,
                            "role": "source",
                        }
                    ),
                    target_row_content_hash=second_domain_pack.gy_content_hash(
                        {
                            "domain": problem.domain,
                            "covariate": name,
                            "role": "target",
                        }
                    ),
                )
                for name, source_value, target_value in covariates
            ),
        )
    return build_cycle_substrate_context(
        design_problem_ref=problem_ref,
        domain=problem.domain,
        substrate_registry=registry,
        selected_registry_entry_hashes=(selected_hash,),
        world_model_record=world,
        intervention_substrate=None,
        candidate_levers=(lever,),
        transport_context=transport,
        source_pack_content_hash=second_domain_pack.gy_content_hash(
            {"domain": problem.domain, "kind": "source_pack"}
        ),
        substrate_input_content_hash=substrate_input_hash,
    )


def test_education_selection_diagram_uses_only_pack_covariates() -> None:
    """The education pack, not an engine tuple, owns the transport vocabulary."""

    bundle = second_domain_pack._load_frozen_bundle(Path.cwd())
    problem = DesignProblem.model_validate(bundle["smoke_problem"]["design_problem"])
    context = second_domain_pack._build_frozen_cycle_substrate_context(
        Path.cwd(),
        bundle=bundle,
        design_problem=problem,
    )

    diagram = _build_candidate_selection_diagram(
        candidate=SimpleNamespace(candidate_id="education_candidate"),
        problem=problem,
        world_record=context.world_model_record,
        query_treatment="education_teaching_method",
        query_outcome="years_of_schooling",
        cycle_substrate_context=context,
    )

    assert {node.target_variable for node in diagram.s_nodes} == {
        "education_spending",
        "school_quality",
    }
    assert "state_capacity" not in diagram.base_graph.nodes
    assert "institutional_quality" not in diagram.base_graph.nodes
    assert {
        (node.source_ref, node.target_ref) for node in diagram.s_nodes
    } == {
        (
            row.source_row_content_hash,
            row.target_row_content_hash,
        )
        for row in context.transport_context.covariates
    }


def test_third_pack_transport_vocabulary_flows_without_engine_change() -> None:
    """A structurally unrelated pack-shaped vocabulary needs no code branch."""

    problem = _problem("water_transport_u2").model_copy(
        update={
            "domain": "water_quality",
            "outcome_of_interest": OutcomeOfInterest(
                target_variable="nitrate_load",
                metric_id="nitrate_load",
                estimand="average_treatment_effect",
            ),
        }
    )
    context = _pack_shaped_transport_context(
        problem=problem,
        covariates=(("watershed_slope", 0.15, 0.63),),
    )

    diagram = _build_candidate_selection_diagram(
        candidate=SimpleNamespace(candidate_id="riparian_buffer_candidate"),
        problem=problem,
        world_record=context.world_model_record,
        query_treatment="riparian_buffer_width",
        query_outcome="nitrate_load",
        cycle_substrate_context=context,
    )

    assert {node.target_variable for node in diagram.s_nodes} == {
        "watershed_slope"
    }
    assert diagram.s_nodes[0].source_value == 0.15
    assert diagram.s_nodes[0].target_value == 0.63


def test_unseen_transport_receipt_uses_real_solver_contract() -> None:
    problem, candidate, context = value_contract._unseen_transport_lane()
    inputs = RealValueOwnerGateway(
        repo_root=Path.cwd(),
        cycle_substrate_context=context,
    ).build_transport_inputs(
        candidate=candidate,
        problem=problem,
        world_record=context.world_model_record,
    )

    receipt, error = _run_value_transport(
        inputs=inputs,
        world_record=context.world_model_record,
    )

    assert error is None
    assert receipt is not None
    assert receipt.status == "transported_limited"
    assert receipt.transport_status
    assert receipt.transport_mode
    assert receipt.identification_engine
    assert receipt.world_model_record_content_hash == context.world_model_record.content_hash


def test_missing_measured_transport_context_blocks_without_defaults() -> None:
    """Absent measured context is an acquisition gap, never governance defaults."""

    problem = _problem("missing_transport_context").model_copy(
        update={"domain": "unseen_domain"}
    )
    context = _pack_shaped_transport_context(problem=problem, covariates=())
    gateway = RealValueOwnerGateway(
        repo_root=Path.cwd(),
        cycle_substrate_context=context,
    )

    with pytest.raises(ValueOwnerAccessError) as exc_info:
        gateway.build_transport_inputs(
            candidate=SimpleNamespace(candidate_id="unseen_candidate"),
            problem=problem,
            world_record=context.world_model_record,
        )

    assert exc_info.value.code == "acquire_data:transport_context_unresolved"


def test_transport_context_for_another_problem_is_not_authority() -> None:
    """A valid context shape cannot cross its DesignProblem content binding."""

    problem = _problem("bound_transport_problem").model_copy(
        update={"domain": "water_quality"}
    )
    context = _pack_shaped_transport_context(
        problem=problem,
        covariates=(("watershed_slope", 0.15, 0.63),),
    )
    mismatched_problem = problem.model_copy(
        update={"design_problem_id": "different_transport_problem"}
    )

    with pytest.raises(ValueOwnerAccessError) as exc_info:
        _build_candidate_selection_diagram(
            candidate=SimpleNamespace(candidate_id="riparian_buffer_candidate"),
            problem=mismatched_problem,
            world_record=context.world_model_record,
            query_treatment="riparian_buffer_width",
            query_outcome="nitrate_load",
            cycle_substrate_context=context,
        )

    assert exc_info.value.code == "transport_context_problem_mismatch"


def _simulation(
    world: WorldModelRecord,
    *,
    candidate_id: str = "candidate_value_gate",
) -> SimulationPortObservation:
    return SimulationPortObservation(
        candidate_id=candidate_id,
        status="joint_simulated",
        simulation_ref=_hash("3"),
        k_world_ref_before=world.content_hash,
        k_world_ref_after=world.content_hash,
        world_model_record=world,
    )


def _unit_value_set(
    *,
    lower: tuple[float, ...],
    upper: tuple[float, ...],
    identification_mode: str,
) -> ValueOuterSet:
    return ValueOuterSet.interval_box(
        coordinates=("firm_survival",),
        lower=lower,
        upper=upper,
        identification_mode=identification_mode,
        assumptions=("unit_test",),
        assumption_status="externally_supported",
        calibration_scope={"scope": "unit"},
        data_trust=DataTrust(
            tier="unit",
            trust_cap=1.0,
            trust_multiplier=1.0,
            authority_ref="test",
        ),
        world_model_record_ref=_hash("1"),
        epoch="2026",
        representation_status="certified",
    )


def _receipt(world: WorldModelRecord) -> ValueGateReceipt:
    value_set = ValueOuterSet.interval_box(
        coordinates=("difference_in_differences",),
        lower=(1.25,),
        upper=(1.25,),
        identification_mode="point",
        assumptions=("unit_test_receipt",),
        assumption_status="externally_supported",
        calibration_scope={"scope": "unit"},
        data_trust=DataTrust(
            tier="unit",
            trust_cap=1.0,
            trust_multiplier=1.0,
            authority_ref="test",
        ),
        world_model_record_ref=world.content_hash,
        epoch="2026",
        representation_status="certified",
    )
    transport = ValueTransportReceipt(
        status="direct",
        world_model_record_id=world.world_model_record_id,
        world_model_record_content_hash=world.content_hash,
        transport_result_ref=_hash("9"),
        transport_status="identified",
        transport_mode="direct",
        identification_engine="unit",
    )
    calibration = ValueCalibrationReceipt(
        status="pass",
        forecast_tier="observable_calibrated",
        calibration_record_ref="s10://unit",
    )
    value_ref = _hash("a")
    return ValueGateReceipt(
        candidate_id="candidate_value_gate",
        evaluation_mode="simulate_only",
        selected_method_fqn="causal.inference.did.standard@1.0.0",
        method_selection_trace=("causal.inference.did.standard@1.0.0",),
        identification_status=value_set.identification_status,
        value_outer_set=value_set,
        transport_receipt=transport,
        calibration_receipt=calibration,
        world_model_record_id=world.world_model_record_id,
        world_model_record_content_hash=world.content_hash,
        value_ref=value_ref,
        wall_time_ms=1.0,
        wmr_cache_status="built",
        k_world_ref_before=world.content_hash,
        k_world_ref_after=world.content_hash,
    )


def test_hand_set_value_outer_set_width_is_rejected() -> None:
    value_set = _unit_value_set(lower=(1.0,), upper=(1.0,), identification_mode="point")
    payload = value_set.model_dump(mode="json")

    with pytest.raises(ValueError, match="value_outer_set_width_supplied_not_derived"):
        ValueOuterSet.model_validate(payload)


def test_empty_hints_with_unresolved_candidate_wmr_ref_refuses_typed() -> None:
    problem = _avg_income_problem()
    candidate = _avg_income_candidate()

    simulation = JointSimulationPort(repo_root=Path.cwd())(
        candidate=candidate,
        problem=problem,
        cycle_index=0,
    )
    observation = FoundryValuePort(repo_root=Path.cwd())(
        candidate=candidate,
        simulation=simulation,
        problem=problem,
        cycle_index=0,
    )

    assert simulation.status == "simulation_blocked"
    assert simulation.world_model_record is None
    assert "world_model_record_unresolved" in simulation.authority_blockers
    assert observation.status == "value_blocked"
    assert observation.authority_blockers == ("value_world_model_record_unwired",)
    assert observation.world_model_record_content_hash is None


def test_empty_hints_cycle_reaches_honest_value_acquisition_with_real_boundary_wmr() -> None:
    lane = value_contract._canonical_first_vertical_lane()
    problem = lane["problem"]
    assert problem.runtime_hints == {}
    candidate = lane["candidate"]
    context = lane["cycle_substrate_context"]
    simulation = lane["simulation"]

    observation = FoundryValuePort(
        repo_root=Path.cwd(),
        cycle_substrate_context=context,
    )(
        candidate=candidate,
        simulation=simulation,
        problem=problem,
        cycle_index=0,
    )

    assert simulation.world_model_record is not None
    assert simulation.world_model_record is context.world_model_record
    assert simulation.world_model_record.content_hash == context.world_model_record.content_hash
    assert observation.status == "value_blocked"
    assert observation.world_model_record_content_hash == simulation.world_model_record.content_hash
    assert observation.authority_blockers == (
        "acquire_data:value_panel_data_missing",
    )
    assert observation.selected_method_fqn is None
    assert observation.method_selection_receipt is None
    assert observation.value_data_profile_content_hash is None
    assert observation.acquisition_requirement is not None
    assert observation.value_receipt is None


def test_runtime_value_hints_cannot_change_owner_data_terminal() -> None:
    problem = _avg_income_problem()
    forged_problem = problem.model_copy(
        update={
            "runtime_hints": {
                "value_gate_inputs": {
                    "status": "value_ready",
                    "owner_assignment": {"treated_unit_ids": ["AM"], "period": 2020},
                }
            }
        }
    )
    candidate = _avg_income_candidate()
    simulation = _simulation(_world_record(), candidate_id=candidate.candidate_id)
    port = FoundryValuePort(repo_root=Path.cwd())

    canonical = port(
        candidate=candidate,
        simulation=simulation,
        problem=problem,
        cycle_index=0,
    )
    forged = port(
        candidate=candidate,
        simulation=simulation,
        problem=forged_problem,
        cycle_index=0,
    )

    assert forged.status == canonical.status == "value_blocked"
    assert forged.authority_blockers == canonical.authority_blockers == (
        "treatment_assignment_not_owner_derived",
    )
    assert forged.value_receipt is canonical.value_receipt is None
    assert forged.acquisition_requirement is not None
    assert canonical.acquisition_requirement is not None
    assert forged.value_data_profile_content_hash == (
        canonical.value_data_profile_content_hash
    )


def test_candidate_treatment_assignment_is_not_owner_world_knowledge() -> None:
    problem = _avg_income_problem()
    candidate = _avg_income_candidate()
    world = _world_record()

    profile = RealValueOwnerGateway(repo_root=Path.cwd()).load_value_data_profile(
        candidate=candidate,
        problem=problem,
        world_record=world,
    )

    assert isinstance(profile, ValueDataProfile)
    assert profile.outcome == "avg_income"
    assert profile.owner_row_count == 64
    assert profile.unit_count == 16
    assert profile.period_count == 4
    assert profile.treatment_assignment_status == "owner_assignment_unresolved"
    assert profile.content_hash.startswith("sha256:")


def test_shaped_owner_assignment_attestation_is_not_authority() -> None:
    base = _avg_income_candidate()
    shaped_atom = SimpleNamespace(
        intervention_id=base.atom.intervention_id,
        content_hash=base.atom.content_hash,
        status=base.atom.status,
        world_model_record_ref=base.atom.world_model_record_ref,
        target_world_slots=base.atom.target_world_slots,
        treated_unit_ids=("AM",),
        treatment_period=2020,
    )
    candidate = SimpleNamespace(
        candidate_id=base.candidate_id,
        atom=shaped_atom,
        treated_unit_ids=("AM",),
        treatment_period=2020,
        treatment_assignment_authority="owner_derived",
        treatment_assignment_owner_ref="substrate_owner://invented",
        treatment_assignment_content_hash=_hash("9"),
    )

    gateway = RealValueOwnerGateway(repo_root=Path.cwd())
    shaped = gateway.load_value_data_profile(
        candidate=candidate,
        problem=_avg_income_problem(),
        world_record=_world_record(),
    )
    canonical = gateway.load_value_data_profile(
        candidate=_avg_income_candidate(),
        problem=_avg_income_problem(),
        world_record=_world_record(),
    )

    assert shaped == canonical
    assert shaped.treatment_assignment_status == "owner_assignment_unresolved"

    observation = FoundryValuePort(repo_root=Path.cwd())(
        candidate=candidate,
        simulation=_simulation(_world_record(), candidate_id=base.candidate_id),
        problem=_avg_income_problem(),
        cycle_index=0,
    )

    assert observation.authority_blockers == (
        "treatment_assignment_not_owner_derived",
    )
    assert observation.acquisition_requirement is not None
    assert observation.value_receipt is None


def test_value_port_refuses_candidate_simulation_mismatch() -> None:
    observation = FoundryValuePort(repo_root=Path.cwd())(
        candidate=_avg_income_candidate(),
        simulation=_simulation(_world_record(), candidate_id="another_candidate"),
        problem=_avg_income_problem(),
        cycle_index=0,
    )

    assert observation.status == "value_blocked"
    assert observation.authority_blockers == ("value_candidate_simulation_mismatch",)
    assert observation.method_selection_receipt is None
    assert observation.acquisition_requirement is None


def test_value_data_profile_rejects_content_drift() -> None:
    profile = RealValueOwnerGateway(repo_root=Path.cwd()).load_value_data_profile(
        candidate=_avg_income_candidate(),
        problem=_avg_income_problem(),
        world_record=_world_record(),
    )
    payload = profile.model_dump(mode="json")
    payload["owner_row_count"] -= 1

    with pytest.raises(ValueError, match="value_data_profile_row_count_mismatch"):
        ValueDataProfile.model_validate(payload)


def test_value_data_profile_rejects_panel_label_without_longitudinal_units() -> None:
    rows = tuple(
        _value_owner_row(
            outcome="synthetic_outcome",
            unit_id=f"unit_{index}",
            period_id=2020 + index,
            source_rows=((float(index), f"dataset_{index}", f"observation_{index}"),),
        )
        for index in range(4)
    )
    rows_payload = tuple(row.model_dump(mode="json") for row in rows)
    payload = {
        "schema_version": "policyos.runtime.value_data_profile.v1",
        "outcome": "synthetic_outcome",
        "rows": rows_payload,
        "owner_row_count": len(rows),
        "unit_count": 4,
        "period_count": 4,
        "available_data_modalities": ("panel", "tabular"),
        "treatment_assignment_status": "owner_assignment_unresolved",
        "owner_access_ref": "substrate_owner://diagonal_rows",
        "owner_rows_content_hash": second_domain_pack.gy_content_hash(rows_payload),
    }

    with pytest.raises(ValueError, match="value_data_profile_modalities_not_derived"):
        ValueDataProfile.model_validate(
            {**payload, "content_hash": second_domain_pack.gy_content_hash(payload)}
        )


@pytest.mark.parametrize(
    ("period_count", "expected_modalities"),
    [(3, ("tabular",)), (4, ("panel", "tabular"))],
)
def test_value_owner_shape_uses_canonical_four_period_panel_floor(
    period_count: int,
    expected_modalities: tuple[str, ...],
) -> None:
    rows = tuple(
        _value_owner_row(
            outcome="unseen_owner_outcome",
            unit_id=f"unit_{unit_index}",
            period_id=2020 + period_index,
            source_rows=(
                (
                    float(unit_index + period_index),
                    f"dataset_{unit_index}",
                    f"observation_{unit_index}_{period_index}",
                ),
            ),
        )
        for unit_index in range(5)
        for period_index in range(period_count)
    )

    assert _derived_value_data_modalities(rows) == expected_modalities


def test_value_advisor_projection_preserves_typed_design_problem_authority() -> None:
    """Owner data context must not turn a real DesignProblem into a shaped dict."""

    problem = _avg_income_problem()
    profile = RealValueOwnerGateway(repo_root=Path.cwd()).load_value_data_profile(
        problem=problem,
        candidate=_avg_income_candidate(),
        world_record=_world_record(),
    )

    projected = _selector_problem_for_value_profile(problem, profile)

    assert isinstance(projected, DesignProblem)
    assert projected.design_problem_id == problem.design_problem_id
    assert projected.nl_provenance == problem.nl_provenance
    assert projected.runtime_hints == {
        "value_required_data_modalities": profile.available_data_modalities,
        "value_data_characteristics": {
            "n_obs": profile.owner_row_count,
            "n_units": profile.unit_count,
            "n_periods": profile.period_count,
            "is_panel": "panel" in profile.available_data_modalities,
            "treatment_is_binary": None,
            "outcome_is_continuous": None,
        },
        "value_data_profile_content_hash": profile.content_hash,
    }


def test_value_port_selects_then_routes_missing_owner_assignment_to_acquisition() -> None:
    world = _world_record()
    observation = FoundryValuePort(repo_root=Path.cwd())(
        candidate=_avg_income_candidate(),
        simulation=_simulation(world, candidate_id="candidate_avg_income_real"),
        problem=_avg_income_problem(),
        cycle_index=0,
    )

    assert observation.status == "value_blocked"
    assert observation.selected_method_fqn is not None
    assert observation.value_receipt is None
    assert observation.authority_blockers == (
        "treatment_assignment_not_owner_derived",
    )
    assert isinstance(observation.method_selection_receipt, MethodSelectionReceipt)
    assert observation.method_selection_receipt.selection_authority == (
        "foundry_registry_advisor"
    )
    assert len(observation.method_selection_receipt.denominator) > 1
    assert observation.acquisition_requirement is not None
    assert observation.acquisition_requirement.metadata["requirement"]["operator"] == "any_of"
    assert observation.acquisition_requirement.metadata["satisfaction_status"] == "unsatisfied"


def test_value_port_rejects_selection_receipt_replayed_from_other_owner_profile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from polisyos.runtime.quality import generation_cycle

    problem = _avg_income_problem()
    wrong_problem = {
        "design_problem_id": problem.design_problem_id,
        "problem_statement": problem.problem_statement,
        "domain": problem.domain,
        "outcome_of_interest": problem.outcome_of_interest.model_dump(mode="json"),
        "runtime_hints": {
            "value_required_data_modalities": ("tabular",),
            "value_data_characteristics": {
                "n_obs": 64,
                "n_units": 16,
                "n_periods": 4,
                "is_panel": True,
                "treatment_is_binary": None,
                "outcome_is_continuous": None,
            },
            "value_data_profile_content_hash": _hash("f"),
        },
    }
    replayed = select_value_method_for_problem(
        candidate=_avg_income_candidate(),
        problem=wrong_problem,
    )
    monkeypatch.setattr(generation_cycle, "_select_value_method", lambda **_kwargs: replayed)

    observation = FoundryValuePort(repo_root=Path.cwd())(
        candidate=_avg_income_candidate(),
        simulation=_simulation(
            _world_record(), candidate_id="candidate_avg_income_real"
        ),
        problem=problem,
        cycle_index=0,
    )

    assert observation.status == "value_blocked"
    assert observation.authority_blockers == (
        "value_method_selection_context_hash_mismatch",
    )
    assert observation.acquisition_requirement is None


def test_shaped_relation_certificate_cannot_open_missing_value_input_lane() -> None:
    base = _avg_income_candidate()
    candidate = SimpleNamespace(
        candidate_id=base.candidate_id,
        atom=base.atom,
        skg_relation_certificate={
            "status": "certified",
            "relation": "exact",
            "content_hash": _hash("7"),
        },
    )

    gateway = RealValueOwnerGateway(repo_root=Path.cwd())
    forged_profile = gateway.load_value_data_profile(
        candidate=candidate,
        problem=_avg_income_problem(),
        world_record=_world_record(),
    )
    canonical_profile = gateway.load_value_data_profile(
        candidate=base,
        problem=_avg_income_problem(),
        world_record=_world_record(),
    )

    assert forged_profile == canonical_profile

    observation = FoundryValuePort(repo_root=Path.cwd())(
        candidate=candidate,
        simulation=_simulation(_world_record(), candidate_id=base.candidate_id),
        problem=_avg_income_problem(),
        cycle_index=0,
    )

    assert observation.status == "value_blocked"
    assert observation.authority_blockers == (
        "treatment_assignment_not_owner_derived",
    )
    assert observation.acquisition_requirement is not None
    assert observation.value_receipt is None


def test_value_port_rejects_unowned_method_selection_receipt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from polisyos.runtime.quality import generation_cycle

    monkeypatch.setattr(
        generation_cycle,
        "_select_value_method",
        lambda **_kwargs: {
            "status": "selected",
            "selected_method_fqn": "bayesian.regression.linear_regression@1.0.0",
            "selection_source": "caller_asserted_advisor",
            "denominator": ("bayesian.regression.linear_regression@1.0.0",),
            "score_trace": (),
            "blockers": (),
        },
    )

    observation = FoundryValuePort(repo_root=Path.cwd())(
        candidate=_avg_income_candidate(),
        simulation=_simulation(
            _world_record(), candidate_id="candidate_avg_income_real"
        ),
        problem=_avg_income_problem(),
        cycle_index=0,
    )

    assert observation.status == "value_blocked"
    assert observation.authority_blockers == (
        "value_method_selection_authority_unresolved",
    )
    assert observation.value_receipt is None


def test_real_education_owner_shape_selects_before_unbound_estimand_refusal() -> None:
    frozen = second_domain_pack._load_frozen_bundle(Path.cwd())
    problem = DesignProblem.model_validate(frozen["smoke_problem"]["design_problem"])
    context = second_domain_pack._build_frozen_cycle_substrate_context(
        Path.cwd(),
        bundle=frozen,
        design_problem=problem,
    )
    grounding = frozen["cycle_trace"]["stage_attempts"]["grounding"]
    candidate_lever = context.candidate_levers[0]
    assert context.intervention_substrate is not None
    lever_resolution = resolve_intervention_lever(
        context.intervention_substrate,
        operator_kind=candidate_lever.lever_id,
        parameter_value=0,
        world_model_record=context.world_model_record,
        cycle_substrate_context=context,
    )
    assert isinstance(lever_resolution, InterventionLeverRefusal)
    candidate = SimpleNamespace(
        candidate_id=str(grounding["proposal_id"]),
        content_hash=str(grounding["raw_candidate_hash"]),
        status="candidate_unbound",
        grounding_disposition=str(grounding["disposition"]),
        lever_resolution=lever_resolution,
    )
    profile = RealValueOwnerGateway(
        repo_root=Path.cwd(),
        cycle_substrate_context=context,
    ).load_value_data_profile(
        candidate=candidate,
        problem=problem,
        world_record=context.world_model_record,
    )

    assert (profile.owner_row_count, profile.unit_count, profile.period_count) == (
        32,
        16,
        2,
    )
    assert profile.available_data_modalities == ("tabular",)

    observation = FoundryValuePort(
        repo_root=Path.cwd(),
        cycle_substrate_context=context,
    )(
        candidate=candidate,
        simulation=_simulation(
            context.world_model_record,
            candidate_id=candidate.candidate_id,
        ),
        problem=problem,
        cycle_index=0,
    )

    assert observation.status == "value_blocked"
    assert observation.authority_blockers == ("method_estimand_binding_mismatch",)
    assert observation.value_receipt is None
    assert observation.selected_method_fqn is not None
    assert observation.method_selection_receipt is not None
    assert observation.method_selection_receipt.selection_authority == (
        "foundry_registry_advisor"
    )
    assert observation.method_selection_receipt.ranked_alternatives
    selected_alternative = next(
        row
        for row in observation.method_selection_receipt.ranked_alternatives
        if row.selected
    )
    assert "panel" not in selected_alternative.data_modalities
    assert observation.acquisition_requirement is None


@pytest.mark.parametrize("mutation", ["blocker", "claim_ref"])
def test_value_world_knowledge_gap_must_match_blocker_and_candidate(
    mutation: str,
) -> None:
    canonical = FoundryValuePort(repo_root=Path.cwd())(
        candidate=_avg_income_candidate(),
        simulation=_simulation(
            _world_record(), candidate_id="candidate_avg_income_real"
        ),
        problem=_avg_income_problem(),
        cycle_index=0,
    )
    payload = canonical.model_dump(mode="python")
    if mutation == "blocker":
        payload["authority_blockers"] = ("unrelated_value_blocker",)
    else:
        payload["acquisition_requirement"] = (
            value_input_world_knowledge_requirement_gap(
                claim_ref="value-claim:another-candidate"
            )
        )

    with pytest.raises(ValueError, match="value_acquisition_requirement_not_canonical"):
        ValuePortObservation.model_validate(payload)


def test_missing_candidate_treatment_binding_blocks_without_fallback() -> None:
    @dataclass(frozen=True)
    class MissingTreatmentAtom:
        intervention_id: str
        content_hash: str
        status: str = "candidate_unverified"
        world_model_record_ref: str = "world_model_record_test"
        target_world_slots: tuple[str, ...] = ("avg_income",)

    candidate = _Candidate(
        candidate_id="candidate_avg_income_missing_treatment",
        atom=MissingTreatmentAtom("candidate_avg_income_missing_treatment", _hash("8")),
        diversity_key=("grant", "country", "avg_income", "missing_treatment"),
    )
    world = _world_record()

    observation = FoundryValuePort(repo_root=Path.cwd())(
        candidate=candidate,
        simulation=_simulation(world, candidate_id=candidate.candidate_id),
        problem=_avg_income_problem(),
        cycle_index=0,
    )

    assert observation.status == "value_blocked"
    assert observation.value_receipt is None
    assert observation.authority_blockers == (
        "treatment_assignment_not_owner_derived",
    )
    assert "owner-derived treatment assignment" in observation.reason


def test_s10_refusal_is_report_driven_by_bad_did_report() -> None:
    world = _world_record()
    problem = _avg_income_problem()
    candidate = _avg_income_candidate()
    bad_report = CausalEffectReport(
        method=CausalMethod.DIFFERENCE_IN_DIFFERENCES,
        estimand="ATT",
        point_estimate=10.0,
        standard_error=1.0,
        confidence_interval=(8.0, 12.0),
        inference_method="did",
        diagnostics=[
            DiagnosticTest(
                test_name="parallel_trends",
                statistic=12.0,
                p_value=0.99,
                passed=False,
                details={"source": "report-driven-refusal-test"},
            )
        ],
        sample_size=64,
        n_treated=1,
        n_control=15,
        pre_periods=2,
        post_periods=1,
    )
    evidence = _s10_calibration_evidence_from_report(bad_report)
    assert evidence["calibration_status"] == "limit"
    assert evidence["floor_passed"] is False
    assert evidence["false_clear_counts"][
        "uncalibrated_observable_promotion_false_clear_count"
    ] == 1

    policy_context_ref = f"policy-context://{world.world_model_record_id}"
    inputs = _build_s10_forecast_inputs(
        candidate=candidate,
        problem=problem,
        world_record=world,
        method_result=SimpleNamespace(output={"report": bad_report}),
        selected_method_fqn="causal.inference.did.standard@1.0.0",
        forecast_tier=str(evidence["forecast_tier"]),
        calibration_status=str(evidence["calibration_status"]),
        policy_context_ref=policy_context_ref,
        expected_policy_context_ref=policy_context_ref,
        false_clear_counts=evidence["false_clear_counts"],
        calibration_evidence=evidence,
    )
    receipt = _value_calibration_receipt(inputs=inputs, world_record=world)

    assert receipt.status == "blocked"
    assert receipt.issue_codes == ("uncalibrated_forecast_minted_value",)
    assert receipt.false_clear_counts[
        "uncalibrated_observable_promotion_false_clear_count"
    ] == 1


def test_partial_value_outer_set_width_tracks_real_did_interval() -> None:
    world = _world_record()
    report = CausalEffectReport(
        method=CausalMethod.DIFFERENCE_IN_DIFFERENCES,
        estimand="ATT",
        point_estimate=10.0,
        standard_error=1.0,
        confidence_interval=(8.0, 12.0),
        inference_method="did",
        diagnostics=[],
        sample_size=64,
        n_treated=1,
        n_control=15,
        pre_periods=2,
        post_periods=1,
    )
    transport = ValueTransportReceipt(
        status="transported_limited",
        world_model_record_id=world.world_model_record_id,
        world_model_record_content_hash=world.content_hash,
        transport_result_ref=_hash("9"),
        transport_status="partially_identified",
        transport_mode="selection_diagram",
        identification_engine="transport_engine",
    )
    calibration = ValueCalibrationReceipt(
        status="pass",
        forecast_tier="observable_calibrated",
        calibration_record_ref="s10://did-width",
    )

    value_set = _value_outer_set_from_foundry_result(
        method_result=SimpleNamespace(output={"report": report}),
        transport_receipt=transport,
        calibration_receipt=calibration,
        world_record=world,
        data_trust=DataTrust(
            tier="unit",
            trust_cap=1.0,
            trust_multiplier=1.0,
            authority_ref="test",
        ),
    )

    assert value_set.identification_status == "partial"
    assert value_set.lower == (8.0,)
    assert value_set.upper == (12.0,)
    assert value_set.width == (4.0,)


def test_production_value_block_is_real_data_gap_not_missing_inputs() -> None:
    world = _world_record()
    problem = _problem("value_gate_problem")

    observation = FoundryValuePort(
        owner_gateway=RealValueOwnerGateway(repo_root=Path.cwd()),
        requested_method_fqn="causal.inference.synthetic_control@1.0.0",
    )(
        candidate=_candidate(),
        simulation=_simulation(world),
        problem=problem,
        cycle_index=0,
    )

    assert observation.status == "value_blocked"
    assert observation.value_receipt is None
    assert observation.authority_blockers == ("acquire_data:value_panel_data_missing",)
    assert observation.acquisition_requirement is not None
    assert observation.acquisition_requirement.claim_ref == (
        f"value-claim:{observation.candidate_id}"
    )
    assert observation.acquisition_requirement.metadata["source"] == (
        "l1_dcat_variable_availability"
    )
    assert observation.acquisition_requirement.metadata["availability"][
        "variable_id"
    ] == "firm_survival"
    assert observation.acquisition_requirement.metadata["availability"][
        "observation_count"
    ] == 0
    assert "substrate owner" in str(observation.reason)
    assert "dataset_catalog.duckdb#variable/firm_survival" in str(observation.reason)
    assert "value_method_state_missing" not in observation.authority_blockers
    assert "world_model_record_missing" not in observation.authority_blockers


def test_missing_cycle_wmr_is_wiring_error_not_acquire_gap() -> None:
    world = _world_record()
    simulation = _simulation(world).model_copy(update={"world_model_record": None})

    observation = FoundryValuePort(
        owner_gateway=RealValueOwnerGateway(repo_root=Path.cwd()),
        requested_method_fqn="causal.inference.synthetic_control@1.0.0",
    )(
        candidate=_candidate(),
        simulation=simulation,
        problem=_problem("value_gate_problem"),
        cycle_index=0,
    )

    assert observation.status == "value_blocked"
    assert observation.authority_blockers == ("value_world_model_record_unwired",)
    assert not observation.authority_blockers[0].startswith("acquire_data:")


def test_value_port_reuses_cached_world_model_record() -> None:
    world = _world_record()
    port = FoundryValuePort()

    first_record, first_status, first_error = port._world_record_from_simulation(
        _simulation(world)
    )
    second_record, second_status, second_error = port._world_record_from_simulation(
        _simulation(world)
    )

    assert first_record is world
    assert second_record is first_record
    assert first_status == "built"
    assert second_status == "reused"
    assert first_error is None
    assert second_error is None


def test_value_receipt_rejects_world_version_laundering() -> None:
    world = _world_record("1")
    receipt = _receipt(world)

    payload = receipt.model_dump(mode="python")
    payload["value_outer_set"] = receipt.value_outer_set
    payload["transport_receipt"] = receipt.transport_receipt
    payload["calibration_receipt"] = receipt.calibration_receipt
    payload["world_model_record_content_hash"] = _hash("4")
    with pytest.raises(ValueError, match="value_world_version_laundered"):
        ValueGateReceipt.model_validate(payload)


def test_value_ready_observation_requires_owner_selection_receipt() -> None:
    with pytest.raises(ValueError, match="value_ready_requires_owner_receipts"):
        ValuePortObservation(
            status="value_ready",
            selected_method_fqn="causal.inference.did.standard@1.0.0",
            decision_grade="high",
            value_receipt=_receipt(_world_record()),
        )


def test_dominance_timeout_returns_unknown() -> None:
    left = _unit_value_set(lower=(3.0,), upper=(4.0,), identification_mode="partial")
    right = _unit_value_set(lower=(1.0,), upper=(2.0,), identification_mode="partial")

    assert left.compare(right) == "dominates"
    assert left.compare(right, force_timeout=True) == "unknown"


def test_simulate_only_receipt_cannot_shrink_k_world() -> None:
    world = _world_record()
    receipt = _receipt(world)

    payload = receipt.model_dump(mode="python")
    payload["value_outer_set"] = receipt.value_outer_set
    payload["transport_receipt"] = receipt.transport_receipt
    payload["calibration_receipt"] = receipt.calibration_receipt
    payload["k_world_ref_after"] = _hash("5")
    with pytest.raises(ValueError, match="simulate_only_shrank_k_world"):
        ValueGateReceipt.model_validate(payload)


@pytest.mark.parametrize(
    ("case_name", "blocker"),
    [
        (
            "uncalibrated",
            "uncalibrated_forecast_minted_value",
        ),
        (
            "unsupported",
            "unsupported_method_unavailable",
        ),
        (
            "regime_laundered",
            "regime_laundered_forecast_minted_value",
        ),
        (
            "untransportable",
            "untransportable_forecast_minted_value",
        ),
    ],
)
def test_bad_forecasts_and_unavailable_methods_fail_closed(
    case_name: str,
    blocker: str,
) -> None:
    world = _world_record()
    candidate = _avg_income_candidate()
    problem = _avg_income_problem()
    method_fqn = "causal.inference.did.standard@1.0.0"
    if case_name == "unsupported":
        selection = select_value_method_for_problem(
            candidate=candidate,
            problem=problem,
            requested_method_fqn="causal.inference.no_such_method@9.9.9",
        )
        observed_blocker = str(selection["blockers"][0])
    elif case_name == "untransportable":
        receipt, error = _run_value_transport(
            inputs={
                "selection_diagram": {"invalid": "selection-diagram"},
                "query_treatment": "credit_guarantee",
                "query_outcome": "avg_income",
            },
            world_record=world,
        )
        assert receipt is None
        observed_blocker = str(error)
    else:
        report = CausalEffectReport(
            method=CausalMethod.DIFFERENCE_IN_DIFFERENCES,
            estimand="ATT",
            point_estimate=10.0,
            standard_error=1.0,
            confidence_interval=(8.0, 12.0),
            inference_method="did",
            diagnostics=[
                DiagnosticTest(
                    test_name="parallel_trends",
                    statistic=0.1,
                    p_value=0.8,
                    passed=True,
                )
            ],
            sample_size=64,
            n_treated=1,
            n_control=15,
            pre_periods=2,
            post_periods=1,
        )
        evidence = _s10_calibration_evidence_from_report(report)
        policy_context_ref = f"policy-context://{world.world_model_record_id}"
        inputs = _build_s10_forecast_inputs(
            candidate=candidate,
            problem=problem,
            world_record=world,
            method_result=SimpleNamespace(output={"report": report}),
            selected_method_fqn=method_fqn,
            forecast_tier=(
                "simulation_only_advisory"
                if case_name == "uncalibrated"
                else "observable_calibrated"
            ),
            calibration_status=(None if case_name == "uncalibrated" else "pass"),
            policy_context_ref=policy_context_ref,
            expected_policy_context_ref=(
                "policy-context://other-regime"
                if case_name == "regime_laundered"
                else policy_context_ref
            ),
            false_clear_counts=evidence["false_clear_counts"],
            calibration_evidence=evidence,
        )
        receipt = _value_calibration_receipt(inputs=inputs, world_record=world)
        assert receipt.status == "blocked"
        observed_blocker = receipt.issue_codes[0]

    assert observed_blocker.startswith(blocker)


@pytest.mark.parametrize(
    "mode",
    ["sandbox_pilot", "field_pilot", "deployment"],
)
def test_pilot_and_deployment_modes_block_pending_eval_safety(mode: str) -> None:
    world = _world_record()
    observation = FoundryValuePort(
        owner_gateway=RealValueOwnerGateway(repo_root=Path.cwd()),
        evaluation_mode=mode,  # type: ignore[arg-type]
        requested_method_fqn="causal.inference.synthetic_control@1.0.0",
    )(
        candidate=_candidate(),
        simulation=_simulation(world),
        problem=_problem("value_gate_problem"),
        cycle_index=0,
    )

    assert observation.status == "value_blocked"
    assert observation.authority_blockers == ("eval_safety_gate_unavailable",)


def test_candidate_problem_selection_uses_registry_denominator() -> None:
    denominator = reachable_value_method_fqns()
    selection = select_value_method_for_problem(
        candidate={
            "candidate_id": "candidate_panel_value",
            "atom": {"target_world_slots": ("panel", "firm_survival")},
        },
        problem={
            "design_problem_id": "value_selection_problem",
            "runtime_hints": {
                "value_method_hint": "panel",
                "value_required_data_modalities": ("panel",),
            },
        },
    )

    assert len(denominator) > 1
    assert selection["status"] == "selected"
    assert selection["selection_source"] == "foundry_registry_advisor"
    assert selection["selected_method_fqn"] in denominator
    receipt = MethodSelectionReceipt.model_validate(selection["selection_receipt"])
    assert tuple(selection["denominator"]) == tuple(receipt.denominator) == denominator
    assert selection["selected_method_fqn"] == receipt.selected_method_fqn
    assert tuple(selection["score_trace"]) == tuple(
        row.method_fqn for row in receipt.ranked_alternatives
    )
