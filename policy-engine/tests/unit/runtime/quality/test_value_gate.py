from __future__ import annotations

import copy
import hashlib
import json
import os
import subprocess
import sys
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any, ClassVar, Literal, cast

import pytest
from packaging.markers import default_environment

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
from polisyos.foundry.methods.catalog import dependency_profile as dependency_profile_module
from polisyos.foundry.methods.catalog.bayesian.protocols import PosteriorResult
from polisyos.foundry.methods.catalog.bayesian.regression import (
    BayesianLinearRegressionEstimator,
)
from polisyos.foundry.methods.catalog.dependency_evidence import (
    DigestDomain,
    canonical_json_bytes,
    domain_digest,
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
from polisyos.pdc import ArtifactRef, gy_content_hash
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
from polisyos.runtime.quality.evaluation_safety import (
    EvalSafetyAdmissionChallenge,
    EvalSafetyConsumerAdmissionReceipt,
    EvaluationExecutionContext,
    EvaluationInputProvenance,
    evaluation_execution_context_hash,
)
from polisyos.runtime.quality.generation_cycle import (
    FOUNDRY_VALUE_PORT_EVALUATOR_ID,
    FoundryValuePort,
    JointSimulationPort,
    RealValueOwnerGateway,
    SimulationPortObservation,
    ValueCalibrationReceipt,
    ValueDataProfile,
    ValueGateReceipt,
    ValueOwnerAccessError,
    ValueOwnerRow,
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
    simulation_evaluation_input_ref,
    simulation_value_execution_context,
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
from tests._helpers.catalog_source_admission import admit_fixture_catalog_source
from tools.quality.validation import check_layer3_gy_second_domain_pack as second_domain_pack
from tools.quality.validation import check_layer3_gy_value_gate_contract as value_contract

from .test_cycle_substrate import _registry as _lane0_registry
from .test_cycle_substrate import _world_record as _lane0_world_record
from .test_generation_cycle import _Atom, _Candidate, _problem


def _simulation_execution_context(
    *,
    candidate: object,
    simulation: SimulationPortObservation,
    problem: DesignProblem,
) -> EvaluationExecutionContext:
    return simulation_value_execution_context(
        candidate=candidate,
        simulation=simulation,
        problem=problem,
    )


def _execution_ref(
    artifact_id: str,
    content_hash: str,
    *,
    artifact_type: str = "evaluation_execution_binding",
    schema_ref: str = "policyos.runtime.eval_safety.execution_binding.v1",
) -> ArtifactRef:
    return ArtifactRef(
        artifact_id=artifact_id,
        artifact_type=artifact_type,
        content_hash=content_hash,
        schema_ref=schema_ref,
        uri=f"runtime://eval-safety/{artifact_id}",
        version="1.0.0",
    )


def _non_simulation_execution_context(
    *,
    mode: str,
    candidate: object,
    world: WorldModelRecord,
    problem: DesignProblem,
    input_class: str = "real_world",
    candidate_id: str | None = None,
) -> EvaluationExecutionContext:
    input_ref = simulation_evaluation_input_ref(
        _simulation(
            world,
            candidate_id=candidate_id or str(candidate.candidate_id),  # type: ignore[attr-defined]
        )
    )
    assert input_ref is not None
    return EvaluationExecutionContext(
        intake_ref=_execution_ref("evaluation-intake", _hash("b")),
        evaluator_owner_id=FOUNDRY_VALUE_PORT_EVALUATOR_ID,
        design_problem_ref=gy_content_hash(problem.model_dump(mode="json")),
        evaluation_mode=mode,  # type: ignore[arg-type]
        candidate_ref=_execution_ref(
            candidate_id or str(candidate.candidate_id),  # type: ignore[attr-defined]
            str(candidate.atom.content_hash),  # type: ignore[attr-defined]
            artifact_type="candidate",
            schema_ref="policyos.runtime.candidate.v1",
        ),
        world_model_record_ref=_execution_ref(
            world.world_model_record_id,
            world.content_hash,
            artifact_type="world_model_record",
            schema_ref="policyos.runtime.world_model_record.v1",
        ),
        target_population_scope_ref=_execution_ref(
            "target-population",
            _hash("c"),
            artifact_type="target_population_scope",
            schema_ref="policyos.runtime.target_population_scope.v1",
        ),
        rule_version="polisyos.eval_safety.test@1.0.0",
        intended_start_at=datetime(2026, 8, 27, tzinfo=UTC),
        evaluation_input_refs=(input_ref,),
        evaluation_input_provenance=(
            EvaluationInputProvenance(
                input_ref=input_ref,
                input_class=input_class,  # type: ignore[arg-type]
                predicate_provenance=(
                    "not_established" if input_class == "not_established" else "recomputed"
                ),
            ),
        ),
        eval_safety_certificate_ref=_execution_ref("eval-safety-certificate", _hash("d")),
        eval_safety_revision_head_ref=_execution_ref("eval-safety-revision", _hash("e")),
    )


@pytest.fixture(autouse=True)
def _isolate_polisyos_cache(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Keep catalog caches out of the appointed hermetic tooling home."""

    monkeypatch.setenv("POLISYOS_CACHE_HOME", (tmp_path / "polisyos-cache").as_posix())


def _hash(char: str) -> str:
    return "sha256:" + char * 64


def _source_freeze() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


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
    simulation = _simulation(
        lane["world_model_record"], candidate_id=lane["candidate"].candidate_id
    )

    observation = FoundryValuePort(
        evaluation_context=_simulation_execution_context(
            candidate=lane["candidate"],
            simulation=simulation,
            problem=lane["problem"],
        ),
        repo_root=Path.cwd(),
        cycle_substrate_context=lane["cycle_substrate_context"],
    )(
        candidate=lane["candidate"],
        simulation=simulation,
        problem=lane["problem"],
        cycle_index=0,
    )
    assert observation.authority_blockers == ("acquire_data:value_panel_data_missing",)
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
    simulation = _simulation(lane["world_model_record"], candidate_id=candidate.candidate_id)

    observation = FoundryValuePort(
        evaluation_context=_simulation_execution_context(
            candidate=candidate,
            simulation=simulation,
            problem=problem,
        ),
        repo_root=Path.cwd(),
        cycle_substrate_context=lane["cycle_substrate_context"],
    )(
        candidate=candidate,
        simulation=simulation,
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
    simulation = _simulation(lane["world_model_record"], candidate_id=candidate.candidate_id)

    observation = FoundryValuePort(
        evaluation_context=_simulation_execution_context(
            candidate=candidate,
            simulation=simulation,
            problem=lane["problem"],
        ),
        repo_root=Path.cwd(),
        cycle_substrate_context=lane["cycle_substrate_context"],
    )(
        candidate=candidate,
        simulation=simulation,
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
    assert cycle.value_port.authority_blockers == ("acquire_data:value_panel_data_missing",)
    assert cycle.terminal_kind == "acquisition_required"
    assert cycle.acquisition_receipt is None
    assert cycle.acquisition_routing_report is not None
    assert cycle.acquisition_routing_report.status == "pass"
    assert len(cycle.acquisition_routing_report.acquisition_records) == 1
    record = cycle.acquisition_routing_report.acquisition_records[0]
    assert record.recommended_strategy.value == "production_snapshot_build"
    assert record.terminal_disposition.value == "acquire"
    assert record.claim_ref == f"value-claim:{cycle.selected_candidate_ref}"


def test_n8_v2_frozen_payload_records_only_dependency_authority_nonreceipt() -> None:
    source_freeze = _source_freeze()
    payload = value_contract.build_payload(
        value_contract._repo_root(),
        expected_source_freeze=source_freeze,
    )

    assert payload["schema_version"].endswith(".v2")
    assert payload["status"] == "not_established"
    assert payload["retained_capability_label"] == "producer_missing"
    assert "denominators" not in payload
    assert "production_refusal" not in payload
    authority = payload["catalog_dependency_authority"]
    assert authority["result_kind"] in {
        "source_rejected",
        "source_not_established",
        "runtime_cutoff_not_established",
    }
    refusal = authority.get("preflight_refusal", authority)
    assert refusal["persistence"] == {
        "status": "not_established",
        "missing_capability": "owner_resolved_resolution_receipt_store",
        "missing_capability_state": "absent/unallocated",
    }
    if authority["result_kind"] == "runtime_cutoff_not_established":
        assert (
            refusal["failure"]["failure_code"]
            == "owner_enforced_runtime_subtree_cutoff_not_established"
        )
    assert (
        value_contract.validate_payload_result(
            payload,
            expected_source_freeze=source_freeze,
        ).governing_issues
        == ()
    )


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


def _frozen_value_contract_payload() -> dict[str, Any]:
    return json.loads(
        (value_contract._repo_root() / value_contract.OUTPUT_PATH).read_text(encoding="utf-8")
    )


def test_frozen_v1_contract_blocks_live_default_v2_and_keeps_ambient_drift_visible() -> None:
    """The unchanged v1 contract refuses the default v2 producer without hiding ambient drift."""

    payload = _frozen_value_contract_payload()

    result = value_contract.validate_payload_result(payload)

    assert isinstance(result, value_contract.ValueGateValidationResult)
    governing_codes = {issue["code"] for issue in result.governing_issues}
    assert "catalog_builtin_discovery_manifest_mismatch" in governing_codes
    assert "catalog_provenance_schema_version_mismatch" in governing_codes
    assert {issue["code"] for issue in value_contract.validate_payload(payload)} == governing_codes
    assert {finding["code"] for finding in result.ambient_findings} == {
        "catalog_ambient_discovery_manifest_mismatch",
        "catalog_entry_point_distribution_manifest_mismatch",
        "catalog_ambient_unbound_input_manifest_mismatch",
        "catalog_predicate_provenance_mismatch",
    }
    predicate_finding = next(
        finding
        for finding in result.ambient_findings
        if finding["code"] == "catalog_predicate_provenance_mismatch"
    )
    assert predicate_finding["predicate"] == "ambient.discovered_component_membership"
    assert "catalog_provenance_manifest_mismatch" not in {
        finding["code"] for finding in result.ambient_findings
    }


def test_n8_validation_result_keeps_governed_catalog_drift_named_and_decisive() -> None:
    """A governed registry-binding change remains an N8 failure with its named code."""

    from polisyos.foundry.methods.catalog.snapshot import method_catalog_provenance_id

    payload = _frozen_value_contract_payload()
    provenance = payload["denominators"]["catalog_provenance"]
    provenance["governed_discovery"]["registry_binding_sha256"] = "sha256:" + "f" * 64
    provenance["provenance_id"] = method_catalog_provenance_id(provenance)
    payload["contract_content_hash"] = value_contract._content_hash(payload)

    result = value_contract.validate_payload_result(payload)
    governing_codes = {issue["code"] for issue in result.governing_issues}
    ambient_codes = {finding["code"] for finding in result.ambient_findings}

    assert "catalog_builtin_discovery_manifest_mismatch" in governing_codes
    assert "catalog_builtin_discovery_manifest_mismatch" not in ambient_codes
    assert {issue["code"] for issue in value_contract.validate_payload(payload)} >= {
        "catalog_builtin_discovery_manifest_mismatch"
    }


def test_n8_validation_result_fails_closed_when_ambient_admission_is_missing() -> None:
    """Removing the declaration cannot turn unknown posture into an ambient finding."""

    from polisyos.foundry.methods.catalog.snapshot import method_catalog_provenance_id

    payload = _frozen_value_contract_payload()
    provenance = payload["denominators"]["catalog_provenance"]
    provenance["ambient_discovery"].pop("admission")
    provenance["provenance_id"] = method_catalog_provenance_id(provenance)
    payload["contract_content_hash"] = value_contract._content_hash(payload)

    result = value_contract.validate_payload_result(payload)

    assert "catalog_ambient_input_not_quarantined" in {
        issue["code"] for issue in result.governing_issues
    }
    assert "catalog_ambient_input_not_quarantined" not in {
        finding["code"] for finding in result.ambient_findings
    }


def test_n8_full_check_and_rederive_compare_the_governed_projection(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Sibling paths retain ambient evidence without restoring it as the gate."""

    root = value_contract._repo_root()
    source_freeze = _source_freeze()

    result = value_contract.run_rederive_audit_result(
        root,
        expected_source_freeze=source_freeze,
    )
    assert value_contract.check(
        root,
        expected_source_freeze=source_freeze,
    ) == (
        {
            "code": "artifact_drift",
            "path": value_contract.OUTPUT_PATH,
        },
    )
    assert result.governing_issues == (
        {
            "code": "live_rederive_section_drift",
            "section": "catalog_dependency_authority",
        },
    )
    assert {(finding["code"], finding.get("predicate")) for finding in result.ambient_findings} == {
        ("catalog_ambient_discovery_manifest_mismatch", None),
        ("catalog_entry_point_distribution_manifest_mismatch", None),
        ("catalog_ambient_unbound_input_manifest_mismatch", None),
        (
            "catalog_predicate_provenance_mismatch",
            "ambient.discovered_component_membership",
        ),
    }
    summary = json.loads(capsys.readouterr().out.splitlines()[-1])
    assert summary["ambient_findings"] == list(result.ambient_findings)

    monkeypatch.setattr(
        value_contract,
        "run_rederive_audit_result",
        lambda _root, *, expected_source_freeze: result,
    )
    assert (
        value_contract.run_rederive_audit(
            root,
            expected_source_freeze=source_freeze,
        )
        == result.governing_issues
    )


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
        _build_candidate_method_catalog_provenance_manifest,
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

    def _ambient_manifest(direct_url_payload: dict[str, object]):
        entry_point = _EntryPoint(
            _Distribution(
                json.dumps(
                    direct_url_payload,
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
    first = _build_candidate_method_catalog_provenance_manifest(
        snapshot,
        registry_report=governed_report,
        ambient_manifest=_ambient_manifest(
            {
                "url": first_checkout.resolve().as_uri(),
                "dir_info": {"editable": True},
            }
        ),
    )
    second = _build_candidate_method_catalog_provenance_manifest(
        snapshot,
        registry_report=governed_report,
        ambient_manifest=_ambient_manifest(
            {
                "url": second_checkout.resolve().as_uri(),
                "dir_info": {"editable": True},
            }
        ),
    )

    first_entry = first["ambient_discovery"]["entry_points"][0]
    second_entry = second["ambient_discovery"]["entry_points"][0]
    assert first_entry["editable_install"] is True
    assert second_entry["editable_install"] is True
    assert first_entry["direct_url_sha256"] is None
    assert second_entry["direct_url_sha256"] is None
    assert first_entry["source_byte_closure"] == "not_established"
    assert second_entry["source_byte_closure"] == "not_established"
    assert first["ambient_discovery"]["unbound_inputs"] == [
        "entry_point_source_byte_closure_not_established:"
        "polisyos.foundry_methods:roads.method.direct_url_bridge:"
        "roads.method.direct_url_bridge:factory"
    ]
    assert first["ambient_discovery"]["admission"] == {
        "status": "quarantined_unbound",
        "included_in_governed_denominator": False,
        "fail_closed_action": "quarantine",
    }
    assert next(
        row
        for row in first["predicate_provenance"]
        if row["predicate"] == "ambient.entry_point_source_byte_closure"
    ) == {
        "predicate": "ambient.entry_point_source_byte_closure",
        "classification": "not_established",
        "decisive": False,
        "fail_closed_action": "quarantine",
    }
    assert next(
        row
        for row in first["predicate_admission_policy"]
        if row["classification"] == "not_established"
    ) == {
        "classification": "not_established",
        "admitted": False,
        "fail_closed_action": "reject_or_quarantine",
    }
    assert first["provenance_id"] == second["provenance_id"]
    assert value_contract._catalog_provenance_issues(first, second) == ()

    first_bound = _build_candidate_method_catalog_provenance_manifest(
        snapshot,
        registry_report=governed_report,
        ambient_manifest=_ambient_manifest(
            {
                "url": "https://packages.example/roads-direct-url-bridge.whl",
                "archive_info": {"hash": "sha256=" + "a" * 64},
                "dir_info": {"editable": False},
            }
        ),
    )
    second_bound = _build_candidate_method_catalog_provenance_manifest(
        snapshot,
        registry_report=governed_report,
        ambient_manifest=_ambient_manifest(
            {
                "url": "https://packages.example/roads-direct-url-bridge.whl",
                "archive_info": {"hash": "sha256=" + "b" * 64},
                "dir_info": {"editable": False},
            }
        ),
    )
    first_bound_entry = first_bound["ambient_discovery"]["entry_points"][0]
    second_bound_entry = second_bound["ambient_discovery"]["entry_points"][0]
    assert first_bound_entry["editable_install"] is False
    assert second_bound_entry["editable_install"] is False
    assert first_bound_entry["direct_url_sha256"] != second_bound_entry["direct_url_sha256"]
    bound_result = value_contract._catalog_provenance_validation_result(
        second_bound,
        first_bound,
    )
    bound_governing_codes = {issue["code"] for issue in bound_result.governing_issues}
    assert bound_governing_codes == set()
    assert "catalog_entry_point_distribution_manifest_mismatch" in {
        finding["code"] for finding in bound_result.ambient_findings
    }
    assert "catalog_provenance_content_hash_mismatch" not in bound_governing_codes


def test_default_foundry_loader_roundtrips_through_valuegate_and_reissuer(
    tmp_path: Path,
) -> None:
    from polisyos.foundry.extensions.discovery import BUILTIN_LOADER, ENTRY_POINT_GROUP
    from polisyos.foundry.methods.catalog.snapshot import method_catalog_provenance_id

    evidence_cache = value_contract._candidate_catalog_denominator_evidence_cached
    denominator_cache = value_contract._candidate_catalog_denominators_cached
    evidence_cache.cache_clear()
    denominator_cache.cache_clear()
    try:
        live_denominators, live_ambient_manifest = evidence_cache()
        expected = copy.deepcopy(live_denominators["catalog_provenance"])
        target = BUILTIN_LOADER[0]
        assert expected["schema_version"] == ("policyos.method_catalog_provenance_manifest.v2")
        assert expected["governed_discovery"]["declared_builtin_loaders"] == [
            {"name": target, "target": target, "group": ENTRY_POINT_GROUP}
        ]
        assert expected["ambient_discovery"]["declared_builtin_loaders"] == []

        denominator_fields = frozenset(live_denominators) - {"catalog_provenance"}
        result = value_contract._catalog_provenance_validation_result(
            expected,
            expected,
            denominator_fields=denominator_fields,
        )
        assert result.governing_issues == ()

        wrong_group = copy.deepcopy(expected)
        wrong_group["governed_discovery"]["declared_builtin_loaders"][0]["group"] = (
            "polisyos.scientist_nodes"
        )
        wrong_group["provenance_id"] = method_catalog_provenance_id(wrong_group)
        wrong_result = value_contract._catalog_provenance_validation_result(
            wrong_group,
            expected,
            denominator_fields=denominator_fields,
        )
        assert "catalog_builtin_discovery_manifest_mismatch" in {
            issue["code"] for issue in wrong_result.governing_issues
        }

        missing_declaration = copy.deepcopy(expected)
        missing_declaration["governed_discovery"].pop("declared_builtin_loaders")
        missing_declaration["provenance_id"] = method_catalog_provenance_id(missing_declaration)
        missing_result = value_contract._catalog_provenance_validation_result(
            missing_declaration,
            expected,
            denominator_fields=denominator_fields,
        )
        assert "catalog_builtin_discovery_manifest_mismatch" in {
            issue["code"] for issue in missing_result.governing_issues
        }

        historical_mutation_ids = [
            mutation_id
            for mutation_id in value_contract.SOURCE_FLIP_MUTATION_IDS
            if mutation_id != value_contract.EDITABLE_DIRECT_URL_SOURCE_FLIP_ID
        ]
        recorded = {
            "denominators": copy.deepcopy(live_denominators),
            "contract_content_hash": "stale",
            "source_flip_mutation_harness": {
                "mutation_ids": historical_mutation_ids,
            },
            "unrelated_receipt": {"status": "frozen"},
        }
        reissued = value_contract._catalog_provenance_reissue_payload(
            recorded,
            live_denominators,
            live_ambient_manifest,
        )
        candidate_path = tmp_path / "catalog-provenance-v2-candidate.json"
        value_contract._write_json(candidate_path, reissued)
        persisted = value_contract._load_json(candidate_path)
        assert (
            persisted["denominators"]["catalog_provenance"]
            == (live_denominators["catalog_provenance"])
        )
        assert persisted["source_flip_mutation_harness"]["mutation_ids"] == list(
            value_contract.SOURCE_FLIP_MUTATION_IDS
        )
        assert persisted["unrelated_receipt"] == {"status": "frozen"}
        assert persisted["contract_content_hash"] == value_contract._content_hash(persisted)
        persisted_result = value_contract._catalog_provenance_validation_result(
            persisted["denominators"]["catalog_provenance"],
            expected,
            denominator_fields=denominator_fields,
        )
        assert persisted_result.governing_issues == ()
    finally:
        evidence_cache.cache_clear()
        denominator_cache.cache_clear()


def test_n8_catalog_provenance_reports_changed_content_bound_distribution_identity() -> None:
    from polisyos.foundry.methods.catalog.snapshot import method_catalog_provenance_id

    expected = _catalog_provenance_comparison_fixture()
    expected_entry = expected["ambient_discovery"]["entry_points"][0]
    expected_entry["editable_install"] = False
    expected_entry["direct_url_sha256"] = _hash("bound-wheel-a")
    expected["provenance_id"] = method_catalog_provenance_id(expected)
    recorded = copy.deepcopy(expected)
    recorded["ambient_discovery"]["entry_points"][0]["direct_url_sha256"] = _hash("bound-wheel-b")
    recorded["provenance_id"] = method_catalog_provenance_id(recorded)

    result = value_contract._catalog_provenance_validation_result(recorded, expected)
    governing_codes = {issue["code"] for issue in result.governing_issues}
    ambient_codes = {finding["code"] for finding in result.ambient_findings}

    assert "catalog_entry_point_distribution_manifest_mismatch" in ambient_codes
    assert "catalog_entry_point_distribution_manifest_mismatch" not in governing_codes
    assert "catalog_provenance_content_hash_mismatch" not in governing_codes


def test_n8_catalog_provenance_reissue_changes_only_the_member_and_witness() -> None:
    from polisyos.core.components.discovery import _component_discovery_manifest_id
    from polisyos.foundry.methods.catalog.snapshot import method_catalog_provenance_id

    frozen_entry = {
        "editable_install": True,
        "direct_url_sha256": _hash("a"),
        "source_byte_closure": "not_established",
    }
    historical_manifest_content = {
        "schema_version": "policyos.component_discovery_manifest.v1",
        "entry_points": [frozen_entry],
        "hidden_policy": "stable",
    }
    recorded_provenance = {
        "ambient_discovery": {
            "manifest_id": _component_discovery_manifest_id(historical_manifest_content),
            "entry_points": [frozen_entry],
        },
        "provenance_id": "method_catalog_provenance_recorded",
    }
    live_manifest_content = copy.deepcopy(historical_manifest_content)
    live_manifest_content["entry_points"][0]["direct_url_sha256"] = None
    live_provenance = copy.deepcopy(recorded_provenance)
    live_provenance["ambient_discovery"]["manifest_id"] = _component_discovery_manifest_id(
        live_manifest_content
    )
    live_provenance["ambient_discovery"]["entry_points"][0]["direct_url_sha256"] = None
    live_provenance["provenance_id"] = method_catalog_provenance_id(live_provenance)
    historical_mutation_ids = [
        mutation_id
        for mutation_id in value_contract.SOURCE_FLIP_MUTATION_IDS
        if mutation_id != value_contract.EDITABLE_DIRECT_URL_SOURCE_FLIP_ID
    ]
    recorded = {
        "denominators": {
            "registered_method_count": 389,
            "catalog_entry_count": 389,
            "catalog_provenance": recorded_provenance,
        },
        "contract_content_hash": "stale",
        "source_flip_mutation_harness": {
            "mutation_ids": historical_mutation_ids,
        },
        "unrelated_receipt": {"status": "frozen"},
    }
    live_denominators = {
        "registered_method_count": 389,
        "catalog_entry_count": 389,
        "catalog_provenance": live_provenance,
    }

    reissued = value_contract._catalog_provenance_reissue_payload(
        recorded,
        live_denominators,
        live_manifest_content,
    )

    assert reissued["denominators"]["catalog_provenance"] == live_provenance
    assert reissued["unrelated_receipt"] == recorded["unrelated_receipt"]
    assert reissued["source_flip_mutation_harness"]["mutation_ids"] == list(
        value_contract.SOURCE_FLIP_MUTATION_IDS
    )
    assert reissued["contract_content_hash"] == value_contract._content_hash(reissued)
    assert recorded["denominators"]["catalog_provenance"] == recorded_provenance


def test_n8_catalog_provenance_reissue_refuses_sibling_denominator_drift() -> None:
    recorded = {
        "denominators": {
            "registered_method_count": 389,
            "catalog_provenance": {"provenance_id": "recorded"},
        },
        "contract_content_hash": "stale",
        "source_flip_mutation_harness": {
            "mutation_ids": [
                mutation_id
                for mutation_id in value_contract.SOURCE_FLIP_MUTATION_IDS
                if mutation_id != value_contract.EDITABLE_DIRECT_URL_SOURCE_FLIP_ID
            ],
        },
    }
    live_denominators = {
        "registered_method_count": 390,
        "catalog_provenance": {"provenance_id": "live"},
    }

    with pytest.raises(
        ValueError,
        match="catalog_provenance_reissue_denominator_drift",
    ):
        value_contract._catalog_provenance_reissue_payload(
            recorded,
            live_denominators,
            {},
        )


def test_n8_catalog_provenance_reissue_refuses_unrelated_ambient_drift() -> None:
    from polisyos.core.components.discovery import _component_discovery_manifest_id

    recorded = _catalog_provenance_comparison_fixture()
    live_manifest_content = {
        "schema_version": "policyos.component_discovery_manifest.v1",
        "entry_points": copy.deepcopy(recorded["ambient_discovery"]["entry_points"]),
        "hidden_policy": "stable",
    }
    recorded["ambient_discovery"]["manifest_id"] = _component_discovery_manifest_id(
        live_manifest_content
    )
    live = copy.deepcopy(recorded)
    live["ambient_discovery"]["component_count"] = 390
    historical_mutation_ids = [
        mutation_id
        for mutation_id in value_contract.SOURCE_FLIP_MUTATION_IDS
        if mutation_id != value_contract.EDITABLE_DIRECT_URL_SOURCE_FLIP_ID
    ]

    with pytest.raises(
        ValueError,
        match="catalog_provenance_reissue_unrelated_ambient_drift",
    ):
        value_contract._catalog_provenance_reissue_payload(
            {
                "denominators": {
                    "registered_method_count": 389,
                    "catalog_provenance": recorded,
                },
                "source_flip_mutation_harness": {
                    "mutation_ids": historical_mutation_ids,
                },
            },
            {
                "registered_method_count": 389,
                "catalog_provenance": live,
            },
            live_manifest_content,
        )


def test_n8_catalog_provenance_reissue_refuses_unproven_manifest_id() -> None:
    from polisyos.core.components.discovery import _component_discovery_manifest_id

    frozen_entry = {
        "editable_install": True,
        "direct_url_sha256": _hash("a"),
    }
    historical_manifest_content = {
        "schema_version": "policyos.component_discovery_manifest.v1",
        "entry_points": [frozen_entry],
        "hidden_policy": "stable",
    }
    recorded = {
        "ambient_discovery": {
            "manifest_id": _component_discovery_manifest_id(historical_manifest_content),
            "entry_points": [frozen_entry],
        },
        "provenance_id": "recorded",
    }
    live_manifest_content = copy.deepcopy(historical_manifest_content)
    live_manifest_content["entry_points"][0]["direct_url_sha256"] = None
    live = copy.deepcopy(recorded)
    live["ambient_discovery"]["entry_points"][0]["direct_url_sha256"] = None
    live["ambient_discovery"]["manifest_id"] = "component_discovery_manifest_unproven"
    historical_mutation_ids = [
        mutation_id
        for mutation_id in value_contract.SOURCE_FLIP_MUTATION_IDS
        if mutation_id != value_contract.EDITABLE_DIRECT_URL_SOURCE_FLIP_ID
    ]

    with pytest.raises(
        ValueError,
        match="catalog_provenance_reissue_manifest_evidence_mismatch",
    ):
        value_contract._catalog_provenance_reissue_payload(
            {
                "denominators": {
                    "registered_method_count": 389,
                    "catalog_provenance": recorded,
                },
                "source_flip_mutation_harness": {
                    "mutation_ids": historical_mutation_ids,
                },
            },
            {
                "registered_method_count": 389,
                "catalog_provenance": live,
            },
            live_manifest_content,
        )


def test_n8_catalog_provenance_reissue_refuses_mutation_denominator_drift() -> None:
    recorded = _catalog_provenance_comparison_fixture()

    with pytest.raises(
        ValueError,
        match="catalog_provenance_reissue_source_flip_denominator_drift",
    ):
        value_contract._catalog_provenance_reissue_payload(
            {
                "denominators": {
                    "registered_method_count": 389,
                    "catalog_provenance": recorded,
                },
                "source_flip_mutation_harness": {
                    "mutation_ids": list(reversed(value_contract.SOURCE_FLIP_MUTATION_IDS)),
                },
            },
            {
                "registered_method_count": 389,
                "catalog_provenance": recorded,
            },
            {},
        )


def test_n8_catalog_provenance_check_uses_the_frozen_payload(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    artifact = tmp_path / "catalog-contract.json"
    artifact.write_text('{"frozen": true}\n', encoding="utf-8")
    observed: list[object] = []
    monkeypatch.setattr(value_contract, "OUTPUT_PATH", artifact.name)
    monkeypatch.setattr(
        value_contract,
        "validate_payload_result",
        lambda payload, *, expected_source_freeze: (
            observed.append(payload) or value_contract.ValueGateValidationResult((), ())
        ),
    )

    assert (
        value_contract.check_catalog_provenance(
            tmp_path,
            expected_source_freeze=_source_freeze(),
        )
        == ()
    )
    assert observed == [{"frozen": True}]


def test_n8_catalog_provenance_reports_environment_without_masking_count_drift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected_denominators = value_contract._candidate_catalog_denominators()
    recorded_denominators = copy.deepcopy(expected_denominators)
    entry_points = recorded_denominators["catalog_provenance"]["ambient_discovery"]["entry_points"]
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
    from polisyos.foundry.methods.catalog.snapshot import method_catalog_provenance_id

    recorded_provenance = recorded_denominators["catalog_provenance"]
    recorded_provenance["provenance_id"] = method_catalog_provenance_id(recorded_provenance)
    monkeypatch.setattr(
        value_contract,
        "_candidate_catalog_denominators_cached",
        lambda: expected_denominators,
    )
    payload = {
        "schema_version": value_contract.SCHEMA_VERSION,
        "rule_version": value_contract.VALUE_GATE_RULE_VERSION,
        "denominators": recorded_denominators,
    }

    result = value_contract.validate_payload_result(payload)
    governing_codes = {issue["code"] for issue in result.governing_issues}
    ambient_codes = {finding["code"] for finding in result.ambient_findings}

    assert "catalog_entry_point_distribution_manifest_mismatch" in ambient_codes
    assert "catalog_entry_point_distribution_manifest_mismatch" not in governing_codes
    assert "catalog_method_denominator_drift" in governing_codes


@pytest.mark.parametrize(
    ("section", "field", "corrupt_value", "expected_code", "destination"),
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
            "ambient",
        ),
        (
            "runtime_backend_identity",
            "schema_version",
            "policyos.method_catalog_runtime_identity.forged",
            "catalog_runtime_backend_identity_mismatch",
            "governing",
        ),
    ],
)
def test_n8_catalog_provenance_recomputes_recorded_manifest_identity(
    section: str,
    field: str,
    corrupt_value: object,
    expected_code: str,
    destination: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected_denominators = value_contract._candidate_catalog_denominators()
    recorded_denominators = copy.deepcopy(expected_denominators)
    recorded_denominators["catalog_provenance"][section][field] = corrupt_value
    monkeypatch.setattr(
        value_contract,
        "_candidate_catalog_denominators_cached",
        lambda: expected_denominators,
    )
    payload = {
        "schema_version": value_contract.SCHEMA_VERSION,
        "rule_version": value_contract.VALUE_GATE_RULE_VERSION,
        "denominators": recorded_denominators,
    }

    result = value_contract.validate_payload_result(payload)
    governing_codes = {issue["code"] for issue in result.governing_issues}
    ambient_codes = {finding["code"] for finding in result.ambient_findings}

    if destination == "ambient":
        assert expected_code in ambient_codes
        assert expected_code not in governing_codes
    else:
        assert expected_code in governing_codes
    assert "catalog_provenance_content_hash_mismatch" in governing_codes


def test_n8_catalog_predicate_bindings_cover_every_denominator_field() -> None:
    denominators = value_contract._candidate_catalog_denominators()
    provenance = denominators["catalog_provenance"]
    bindings = provenance["predicate_bindings"]
    predicate_names = {row["predicate"] for row in provenance["predicate_provenance"]}

    assert set(bindings) == set(denominators) - {"catalog_provenance"}
    assert all(references for references in bindings.values())
    assert all(
        reference in predicate_names for references in bindings.values() for reference in references
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
    assert first["typed_refusal"]["code"] == ("acquire_data:transport_context_unresolved")
    assert first["transport_covariates"] == []
    assert first["selection_diagram_content_hash"] is None
    assert first["transport_receipt"] is None

    for role in ("education", "unseen_pack_shape"):
        proof = proofs[role]
        assert proof["outcome_kind"] == "typed_refusal"
        assert proof["transport_receipt"] is None
        assert proof["transport_result_content_hash"] is None
        assert proof["typed_refusal"]["code"] == ("acquire_data:causal_graph_artifact_unresolved")
        assert proof["transport_covariates"]
        assert proof["selection_diagram_content_hash"] is None

    water = proofs["unseen_pack_shape"]
    assert water["domain"] == "water_quality"
    assert water["query_treatment"] == "riparian_buffer_width"
    assert water["query_outcome"] == "nitrate_load"


def test_n8_transport_component_validator_rejects_static_or_malformed_receipts() -> None:
    proofs = value_contract._transport_component_proofs()
    malformed = copy.deepcopy(proofs)
    malformed["education"]["typed_refusal"]["code"] = ""
    malformed["education"]["proof_content_hash"] = value_contract.gy_content_hash(
        {key: value for key, value in malformed["education"].items() if key != "proof_content_hash"}
    )
    static = malformed["unseen_pack_shape"]
    static["outcome_kind"] = "behavioral_probe_in_focused_test"
    static["proof_content_hash"] = value_contract.gy_content_hash(
        {key: value for key, value in static.items() if key != "proof_content_hash"}
    )

    codes = {
        issue["code"] for issue in value_contract._validate_transport_component_proofs(malformed)
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
            "import sys; print('MUTATION_RED:source_flip_unit_semantic_red'); "
            "print('retained stderr', file=sys.stderr); raise SystemExit(1)",
        ),
        expected_red_patterns=("MUTATION_RED:source_flip_unit_semantic_red",),
    )

    retention_root = (
        tmp_path / "docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/run"
    )
    retention_root.mkdir(parents=True)
    result = value_contract._run_source_flip_case(tmp_path, case, retention_root=retention_root)

    assert result["result"] == "RED"
    assert source.read_text(encoding="utf-8") == "guard = True\n"
    assert result["source_restored_sha256"]["owner.py"] == original_hash
    captured = result["captured_output"]
    stdout_path = tmp_path / captured["stdout"]["path"]
    stderr_path = tmp_path / captured["stderr"]["path"]
    assert stdout_path.read_bytes() == b"MUTATION_RED:source_flip_unit_semantic_red\n"
    assert stderr_path.read_bytes() == b"retained stderr\n"
    assert captured["stdout"]["sha256"] == hashlib.sha256(stdout_path.read_bytes()).hexdigest()
    assert captured["stderr"]["sha256"] == hashlib.sha256(stderr_path.read_bytes()).hexdigest()


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


def test_n8_v2_validator_rejects_dependency_authority_promotion() -> None:
    source_freeze = _source_freeze()
    payload = value_contract.build_payload(
        value_contract._repo_root(),
        expected_source_freeze=source_freeze,
    )
    payload["status"] = "value_ready"
    payload["retained_capability_label"] = "implemented"
    payload["contract_content_hash"] = value_contract._content_hash(payload)

    codes = {
        issue["code"]
        for issue in value_contract.validate_payload_result(
            payload,
            expected_source_freeze=source_freeze,
        ).governing_issues
    }

    assert "catalog_dependency_status_promoted" in codes
    assert "catalog_dependency_capability_label_promoted" in codes


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


def _avg_income_typed_atom_candidate(
    problem: Any,
    *,
    unit_id: str | None = "binary",
    treatment_variable: str = "agents.income",
) -> _Candidate:
    """Build a controlled candidate from the registered intervention-atom producer."""
    from polisyos.ir.analytics.interventions import (
        QueryTarget,
        identification_plan_for_intervention,
    )
    from polisyos.runtime.quality import generation_cycle as gc
    from polisyos.runtime.quality.intervention_atom_binding import (
        build_intervention_atom_binding,
    )
    from tests.unit.runtime.quality.test_intervention_atom_binding import (
        _context,
        _intervention,
        _linked,
        _node,
    )

    intervention = _intervention()
    causal_intervention = _node(variable=treatment_variable)
    atom = build_intervention_atom_binding(
        problem_frame_ref=gc._problem_ref(problem),
        policy_spec_ref=_hash("a"),
        intervention=intervention,
        linked_intervention=_linked(intervention),
        causal_intervention=causal_intervention,
        query_target=QueryTarget(
            outcome_variables=("avg_income",),
            conditioning=("income_covariate",),
            functional="ATE",
        ),
        identification_plan=identification_plan_for_intervention(causal_intervention),
        causal_context=_context(intervention),
        world_model_record_ref="world_model_record_candidate_fixture_only",
        producer_ref="tests.unit.runtime.quality.test_value_gate:b31_source_atom",
        provenance_refs=("controlled_fixture:candidate_atom_only",),
        estimand_metric_id=problem.outcome_of_interest.metric_id,
        estimand_unit_id=unit_id,
    )
    return replace(_avg_income_candidate(), atom=atom)


def test_b31_source_atom_binding_requires_recomputed_exact_join() -> None:
    from polisyos.runtime.quality import generation_cycle as gc

    problem = _avg_income_problem()
    candidate = _avg_income_typed_atom_candidate(problem)
    estimand = EstimandSpec(
        query_id="b31-controlled-source-estimand",
        estimand_id="ATE",
        outcome="avg_income",
        treatment_or_exposure="agents.income",
        covariates_or_conditioning=("income_covariate",),
        adjustment_set=("income_covariate",),
        unit="binary",
    )
    bind = gc._value_owner_source_atom_estimand_binding
    assert (
        bind(
            candidate=candidate,
            problem=problem,
            estimand=estimand,
            measurement_unit="binary",
        )
        == candidate.atom.content_hash
    )

    def refuses(
        *,
        selected_candidate: Any = candidate,
        selected_problem: Any = problem,
        selected_estimand: EstimandSpec = estimand,
        selected_unit: str = "binary",
        code: str,
    ) -> None:
        with pytest.raises(ValueError, match=code):
            bind(
                candidate=selected_candidate,
                problem=selected_problem,
                estimand=selected_estimand,
                measurement_unit=selected_unit,
            )

    refuses(
        selected_problem=problem.model_copy(update={"design_problem_id": "foreign_problem"}),
        code="value_owner_source_atom_subject_mismatch",
    )
    refuses(
        selected_estimand=replace(estimand, outcome="foreign_outcome"),
        code="value_owner_source_atom_outcome_mismatch",
    )
    refuses(
        selected_estimand=replace(estimand, estimand_id="ATT"),
        code="value_owner_source_atom_functional_mismatch",
    )
    refuses(
        selected_estimand=replace(estimand, treatment_or_exposure="government.balance"),
        code="value_owner_source_atom_treatment_mismatch",
    )
    refuses(
        selected_estimand=replace(estimand, covariates_or_conditioning=("foreign_covariate",)),
        code="value_owner_source_atom_conditioning_mismatch",
    )
    refuses(
        selected_estimand=replace(estimand, unit="percent"),
        code="value_owner_source_atom_unit_mismatch",
    )
    refuses(selected_unit="percent", code="value_owner_source_atom_unit_mismatch")
    refuses(
        selected_candidate=_avg_income_typed_atom_candidate(problem, unit_id=None),
        code="value_owner_source_atom_unit_unbound",
    )
    refuses(
        selected_candidate=replace(
            candidate,
            atom=candidate.atom.model_copy(update={"content_hash": _hash("f")}),
        ),
        code="value_owner_source_atom_hash_mismatch",
    )
    refuses(selected_candidate=_avg_income_candidate(), code="value_owner_source_atom_untyped")


def _rehash_typed_atom_candidate(candidate: Any, **atom_updates: Any) -> Any:
    """Rehash controlled atom edits so tests reach semantic checks after identity passes."""
    from polisyos.runtime.quality.intervention_atom_binding import (
        InterventionAtomBinding,
        intervention_atom_content_hash,
    )

    provisional = candidate.atom.model_copy(update=atom_updates)
    content_hash = intervention_atom_content_hash(provisional)
    atom = InterventionAtomBinding.model_validate(
        {
            **provisional.model_dump(mode="python"),
            "atom_id": f"atom_{content_hash.removeprefix('sha256:')[:16]}",
            "content_hash": content_hash,
        }
    )
    return replace(candidate, atom=atom)


def test_b31_source_atom_binding_rehydrates_expression_and_limits_ate_action() -> None:
    from polisyos.ir.analytics.interventions import NodeIntervention, VariableAssignment
    from polisyos.runtime.quality import generation_cycle as gc
    from polisyos.runtime.quality.intervention_atom_binding import (
        CausalAssignmentProjection,
    )

    problem = _avg_income_problem()
    candidate = _avg_income_typed_atom_candidate(problem)
    estimand = EstimandSpec(
        query_id="b31-rehydrated-action-source-estimand",
        estimand_id="ATE",
        outcome="avg_income",
        treatment_or_exposure="agents.income",
        covariates_or_conditioning=("income_covariate",),
        adjustment_set=("income_covariate",),
        unit="binary",
    )
    bind = gc._value_owner_source_atom_estimand_binding
    assert (
        bind(
            candidate=candidate,
            problem=problem,
            estimand=estimand,
            measurement_unit="binary",
        )
        == candidate.atom.content_hash
    )

    # The changed expression is valid and the atom content hash is recomputed,
    # while the cached assignment/write-set projection keeps the old action.
    changed_action = NodeIntervention(
        assignments=(
            VariableAssignment(variable="government.balance", value_expr="balance + subsidy"),
        )
    )
    changed_payload_only = candidate.atom.causal_do_expr.model_copy(
        update={"expression_payload": changed_action.model_dump(mode="json")}
    )
    forged = _rehash_typed_atom_candidate(candidate, causal_do_expr=changed_payload_only)
    with pytest.raises(ValueError, match="value_owner_source_atom_expression_projection_mismatch"):
        bind(candidate=forged, problem=problem, estimand=estimand, measurement_unit="binary")

    # A rehashed malformed payload cannot be treated as an absent expression.
    malformed_projection = candidate.atom.causal_do_expr.model_copy(
        update={"expression_payload": {"intervention_type": "unknown_action"}}
    )
    malformed = _rehash_typed_atom_candidate(candidate, causal_do_expr=malformed_projection)
    with pytest.raises(ValueError, match="value_owner_source_atom_expression_invalid"):
        bind(candidate=malformed, problem=problem, estimand=estimand, measurement_unit="binary")

    # Generic atoms can represent multi-target actions; this ATE source route
    # refuses them until it can reconcile the single-treatment coordinate.
    multiple_action = NodeIntervention(
        assignments=(
            VariableAssignment(variable="agents.income", value_expr="income + subsidy(rate)"),
            VariableAssignment(variable="government.balance", value_expr="balance - subsidy(rate)"),
        )
    )
    multiple_projection = candidate.atom.causal_do_expr.model_copy(
        update={
            "assignments": (
                CausalAssignmentProjection(
                    variable="agents.income", value_expr="income + subsidy(rate)"
                ),
                CausalAssignmentProjection(
                    variable="government.balance", value_expr="balance - subsidy(rate)"
                ),
            ),
            "expression_payload": multiple_action.model_dump(mode="json"),
            "write_variables": ("agents.income", "government.balance"),
        }
    )
    multiple = _rehash_typed_atom_candidate(candidate, causal_do_expr=multiple_projection)
    with pytest.raises(ValueError, match="value_owner_source_atom_multiple_treatments_unsupported"):
        bind(candidate=multiple, problem=problem, estimand=estimand, measurement_unit="binary")

    # A valid direct action must also be included in the linker-resolved slot set.
    wrong_slots = _rehash_typed_atom_candidate(
        candidate,
        target_world_slots=("government.balance",),
    )
    with pytest.raises(ValueError, match="value_owner_source_atom_treatment_mismatch"):
        bind(candidate=wrong_slots, problem=problem, estimand=estimand, measurement_unit="binary")


def _controlled_avg_income_owner_profile() -> ValueDataProfile:
    """Build the controlled, content-valid N8 owner profile used by unit witnesses."""
    rows = []
    for unit_index in range(3):
        for period_id in range(4):
            row_fields = {
                "unit_id": f"unit_{unit_index}",
                "period_id": period_id,
                "outcome_value": float(period_id + unit_index),
                "measurement_unit": "synthetic index",
                "source_row_content_hashes": (_hash("a"),),
            }
            rows.append(
                ValueOwnerRow(
                    **row_fields,
                    row_content_hash=gy_content_hash(row_fields),
                )
            )
    rows_payload = [row.model_dump(mode="json") for row in rows]
    profile_payload = {
        "schema_version": "policyos.runtime.value_data_profile.v2",
        "outcome": "avg_income",
        "measurement_unit": "synthetic index",
        "rows": rows_payload,
        "owner_row_count": len(rows_payload),
        "unit_count": 3,
        "period_count": 4,
        "available_data_modalities": ["panel", "tabular"],
        "treatment_assignment_status": "owner_assignment_unresolved",
        "owner_access_ref": "test://synthetic-n8-owner-profile",
        "owner_rows_content_hash": gy_content_hash(rows_payload),
    }
    return ValueDataProfile.model_validate(
        {**profile_payload, "content_hash": gy_content_hash(profile_payload)}
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


def test_education_selection_diagram_requires_selected_graph_artifact() -> None:
    """Measured pack covariates cannot supply the missing graph topology."""

    bundle = second_domain_pack._load_frozen_bundle(Path.cwd())
    problem = DesignProblem.model_validate(bundle["smoke_problem"]["design_problem"])
    context = second_domain_pack._build_frozen_cycle_substrate_context(
        Path.cwd(),
        bundle=bundle,
        design_problem=problem,
    )
    assert context.transport_context is not None
    assert context.transport_context.covariates
    assert context.transport_context.causal_graph_ref is None

    with pytest.raises(ValueOwnerAccessError) as exc_info:
        _build_candidate_selection_diagram(
            candidate=SimpleNamespace(candidate_id="education_candidate"),
            problem=problem,
            world_record=context.world_model_record,
            query_treatment="education_teaching_method",
            query_outcome="years_of_schooling",
            cycle_substrate_context=context,
        )
    assert exc_info.value.code == "acquire_data:causal_graph_artifact_unresolved"


def test_third_pack_transport_context_without_graph_is_typed_refusal() -> None:
    """Pack-shaped covariates do not imply a causal graph or its edge direction."""

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
    assert context.transport_context is not None
    assert context.transport_context.causal_graph_ref is None

    with pytest.raises(ValueOwnerAccessError) as exc_info:
        _build_candidate_selection_diagram(
            candidate=SimpleNamespace(candidate_id="riparian_buffer_candidate"),
            problem=problem,
            world_record=context.world_model_record,
            query_treatment="riparian_buffer_width",
            query_outcome="nitrate_load",
            cycle_substrate_context=context,
        )
    assert exc_info.value.code == "acquire_data:causal_graph_artifact_unresolved"


def test_unseen_transport_context_without_selected_graph_is_refused() -> None:
    """The solver is not reached from names and measured covariates alone."""

    problem, candidate, context = value_contract._unseen_transport_lane()
    assert context.transport_context is not None
    assert context.transport_context.causal_graph_ref is None
    with pytest.raises(ValueOwnerAccessError) as exc_info:
        RealValueOwnerGateway(
            repo_root=Path.cwd(),
            cycle_substrate_context=context,
        ).build_transport_inputs(
            candidate=candidate,
            problem=problem,
            world_record=context.world_model_record,
        )
    assert exc_info.value.code == "acquire_data:causal_graph_artifact_unresolved"


def test_missing_measured_transport_context_blocks_without_defaults() -> None:
    """Absent measured context is an acquisition gap, never governance defaults."""

    problem = _problem("missing_transport_context").model_copy(update={"domain": "unseen_domain"})
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

    problem = _problem("bound_transport_problem").model_copy(update={"domain": "water_quality"})
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
    with pytest.raises(ValueError, match="eval_safety_simulation_input_unresolved"):
        _simulation_execution_context(
            candidate=candidate,
            simulation=simulation,
            problem=problem,
        )

    assert simulation.status == "simulation_blocked"
    assert simulation.world_model_record is None
    assert "world_model_record_unresolved" in simulation.authority_blockers


def test_empty_hints_cycle_reaches_honest_value_acquisition_with_real_boundary_wmr() -> None:
    lane = value_contract._canonical_first_vertical_lane()
    problem = lane["problem"]
    assert problem.runtime_hints == {}
    candidate = lane["candidate"]
    context = lane["cycle_substrate_context"]
    simulation = _simulation(context.world_model_record, candidate_id=candidate.candidate_id)

    observation = FoundryValuePort(
        evaluation_context=_simulation_execution_context(
            candidate=candidate,
            simulation=simulation,
            problem=problem,
        ),
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
    assert observation.authority_blockers == ("acquire_data:value_panel_data_missing",)
    assert observation.selected_method_fqn is None
    assert observation.method_selection_receipt is None
    assert observation.value_data_profile_content_hash is None
    assert observation.acquisition_requirement is not None
    assert observation.value_receipt is None


def test_runtime_value_hints_cannot_change_owner_data_terminal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Runtime hints cannot promote a valid profile's unresolved assignment."""
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
    world = _world_record()
    profile = _controlled_avg_income_owner_profile()

    def load_controlled_profile(
        _gateway: RealValueOwnerGateway,
        *,
        candidate: object,
        problem: DesignProblem,
        world_record: object,
    ) -> ValueDataProfile:
        assert candidate is candidate_arg
        assert problem is problem_arg or problem is forged_problem_arg
        assert world_record is world_arg
        return profile

    candidate_arg = candidate
    problem_arg = problem
    forged_problem_arg = forged_problem
    world_arg = world
    monkeypatch.setattr(
        RealValueOwnerGateway,
        "load_value_data_profile",
        load_controlled_profile,
    )
    simulation = _simulation(world, candidate_id=candidate.candidate_id)
    canonical_port = FoundryValuePort(
        evaluation_context=_simulation_execution_context(
            candidate=candidate,
            simulation=simulation,
            problem=problem,
        ),
        repo_root=Path.cwd(),
    )
    forged_port = FoundryValuePort(
        evaluation_context=_simulation_execution_context(
            candidate=candidate,
            simulation=simulation,
            problem=forged_problem,
        ),
        repo_root=Path.cwd(),
    )

    canonical = canonical_port(
        candidate=candidate,
        simulation=simulation,
        problem=problem,
        cycle_index=0,
    )
    forged = forged_port(
        candidate=candidate,
        simulation=simulation,
        problem=forged_problem,
        cycle_index=0,
    )

    assert forged.status == canonical.status == "value_blocked"
    assert (
        forged.authority_blockers
        == canonical.authority_blockers
        == ("treatment_assignment_not_owner_derived",)
    )
    assert forged.value_receipt is canonical.value_receipt is None
    assert forged.acquisition_requirement == canonical.acquisition_requirement
    assert forged.acquisition_requirement is not None
    assert forged.value_data_profile_content_hash == profile.content_hash
    assert canonical.value_data_profile_content_hash == profile.content_hash


@pytest.mark.parametrize(
    ("source_rows", "expected_reason"),
    [
        (((1.0, "dataset", "observation", ""),), "missing"),
        (
            (
                (1.0, "dataset_a", "observation_a", "USD"),
                (2.0, "dataset_b", "observation_b", "EUR"),
            ),
            "conflicting",
        ),
    ],
)
def test_value_owner_row_refuses_missing_or_conflicting_measurement_units(
    source_rows: tuple[tuple[float, str, str, str], ...],
    expected_reason: str,
) -> None:
    """Do not combine source rows whose measurement units are unknown or mixed."""
    from polisyos.runtime.quality import generation_cycle as gc

    with pytest.raises(gc._ValueOwnerMeasurementUnitRefusalError) as refusal:
        _value_owner_row(
            outcome="avg_income",
            unit_id="AM",
            period_id=2020,
            source_rows=source_rows,
        )
    assert refusal.value.reason == expected_reason


@pytest.mark.parametrize(
    ("condition_json_values", "expected_code", "expected_next_input"),
    [
        (
            (None,) * 8,
            "acquire_data:value_owner_measurement_unit_missing",
            "nonblank unit",
        ),
        (
            ("",) * 8,
            "acquire_data:value_owner_measurement_unit_missing",
            "nonblank unit",
        ),
        (
            ("{}",) * 8,
            "acquire_data:value_owner_measurement_unit_missing",
            "nonblank unit",
        ),
        (
            ('{"unit":"  "}',) * 8,
            "acquire_data:value_owner_measurement_unit_missing",
            "nonblank unit",
        ),
        (
            ('{"unit":"USD"',) * 8,
            "acquire_data:value_owner_measurement_unit_malformed_json",
            "valid JSON object",
        ),
        (
            ("[]",) * 8,
            "acquire_data:value_owner_measurement_unit_wrong_shape",
            "JSON object",
        ),
        (
            ('{"unit":7}',) * 8,
            "acquire_data:value_owner_measurement_unit_wrong_unit_type",
            "string",
        ),
        (
            tuple(json.dumps({"unit": unit}, separators=(",", ":")) for unit in ("USD", "EUR") * 4),
            "acquire_data:value_owner_measurement_unit_conflicting",
            "one declared unit",
        ),
    ],
)
def test_value_port_surfaces_typed_owner_measurement_unit_refusal(
    condition_json_values: tuple[str | None, ...],
    expected_code: str,
    expected_next_input: str,
    tmp_path: Path,
) -> None:
    """Real owner rows with invalid units reach the port's typed refusal."""
    from dataclasses import replace

    import duckdb

    from polisyos.data_forge.read_api.catalog import (
        build_slice0_fixture_catalog_graph,
        default_acquisition_overlay_path,
    )
    from polisyos.runtime.quality.substrate_registry import (
        catalog_serving_source_scope,
        default_substrate_catalog_paths,
    )

    repo_root = tmp_path / "owner-source"
    catalog = build_slice0_fixture_catalog_graph(repo_root / "catalog")
    catalog.close()
    substrate_paths = replace(
        default_substrate_catalog_paths(repo_root),
        l1_dcat_path=repo_root / "catalog/catalog.duckdb",
    )
    with duckdb.connect(str(substrate_paths.l1_dcat_path)) as connection:
        connection.executemany(
            """
            INSERT INTO ds_observations (
                observation_id, dataset_id, raw_variable, canonical_var,
                country_code, year, survey_year, wave, value, condition_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    f"fixture-avg-income-{index}",
                    "acquisition.local.avg_income",
                    "avg_income",
                    "avg_income",
                    "UA",
                    1800 + index,
                    None,
                    None,
                    float(index % 2),
                    condition_json,
                )
                for index, condition_json in enumerate(condition_json_values)
            ],
        )
    catalog_source = admit_fixture_catalog_source(
        repo_root=repo_root, database_path=substrate_paths.l1_dcat_path
    )
    gateway = RealValueOwnerGateway(
        repo_root=repo_root,
        catalog_overlay_path=default_acquisition_overlay_path(repo_root),
        catalog_serving_source=catalog_source,
    )
    candidate, problem, world = _avg_income_candidate(), _avg_income_problem(), _world_record()
    simulation = _simulation(world, candidate_id=candidate.candidate_id)
    port = FoundryValuePort(
        evaluation_context=_simulation_execution_context(
            candidate=candidate,
            simulation=simulation,
            problem=problem,
        ),
        owner_gateway=gateway,
    )

    with catalog_serving_source_scope(catalog_source):
        observation = port(
            candidate=candidate,
            simulation=simulation,
            problem=problem,
            cycle_index=0,
        )

    assert observation.status == "value_blocked"
    assert observation.authority_blockers == (expected_code,)
    assert observation.value_ref is None
    assert observation.value_data_profile_content_hash is None
    assert observation.acquisition_requirement is None
    assert "#measurement-unit-binding" in str(observation.reason)
    assert str(catalog_source.database_path) in str(observation.reason)
    assert expected_next_input in str(observation.reason)


def test_candidate_treatment_assignment_is_not_owner_world_knowledge(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Candidate assignment claims cannot promote a controlled owner profile."""
    problem = _avg_income_problem()
    base = _avg_income_candidate()
    candidate = SimpleNamespace(
        candidate_id=base.candidate_id,
        atom=base.atom,
        diversity_key=base.diversity_key,
        treated_unit_ids=("AM",),
        treatment_period=2020,
        treatment_assignment_authority="owner_derived",
        treatment_assignment_owner_ref="substrate_owner://invented",
        treatment_assignment_content_hash=_hash("9"),
    )
    world = _world_record()
    profile = _controlled_avg_income_owner_profile()
    loaded_candidates: list[object] = []

    def load_controlled_profile(
        _gateway: RealValueOwnerGateway,
        *,
        candidate: object,
        problem: DesignProblem,
        world_record: object,
    ) -> ValueDataProfile:
        assert problem is problem_arg
        assert world_record is world_arg
        loaded_candidates.append(candidate)
        return profile

    problem_arg = problem
    world_arg = world
    gateway = RealValueOwnerGateway(repo_root=Path.cwd())
    monkeypatch.setattr(
        RealValueOwnerGateway,
        "load_value_data_profile",
        load_controlled_profile,
    )

    canonical_profile = gateway.load_value_data_profile(
        candidate=base,
        problem=problem,
        world_record=world,
    )
    forged_profile = gateway.load_value_data_profile(
        candidate=candidate,
        problem=problem,
        world_record=world,
    )

    assert canonical_profile is forged_profile is profile
    assert profile.outcome == "avg_income"
    assert profile.owner_row_count == 12
    assert profile.unit_count == 3
    assert profile.period_count == 4
    assert profile.treatment_assignment_status == "owner_assignment_unresolved"
    assert profile.content_hash.startswith("sha256:")
    assert loaded_candidates == [base, candidate]

    def observe(selected_candidate: object) -> ValuePortObservation:
        simulation = _simulation(world, candidate_id=base.candidate_id)
        return FoundryValuePort(
            evaluation_context=_simulation_execution_context(
                candidate=selected_candidate,
                simulation=simulation,
                problem=problem,
            ),
            owner_gateway=gateway,
        )(
            candidate=selected_candidate,
            simulation=simulation,
            problem=problem,
            cycle_index=0,
        )

    canonical = observe(base)
    forged = observe(candidate)

    assert canonical.status == forged.status == "value_blocked"
    assert (
        canonical.authority_blockers
        == forged.authority_blockers
        == ("treatment_assignment_not_owner_derived",)
    )
    assert canonical.value_data_profile_content_hash == profile.content_hash
    assert forged.value_data_profile_content_hash == profile.content_hash
    assert canonical.value_receipt is forged.value_receipt is None
    assert canonical.acquisition_requirement is not None
    assert forged.acquisition_requirement is not None
    assert loaded_candidates == [base, candidate, base, candidate]


def test_shaped_owner_assignment_attestation_is_not_authority(tmp_path: Path) -> None:
    from dataclasses import replace

    import duckdb

    from polisyos.data_forge.read_api.catalog import (
        build_slice0_fixture_catalog_graph,
        default_acquisition_overlay_path,
    )
    from polisyos.runtime.quality.substrate_registry import (
        catalog_serving_source_scope,
        default_substrate_catalog_paths,
    )

    problem = _avg_income_problem()
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

    repo_root = tmp_path / "shaped-owner-source"
    catalog = build_slice0_fixture_catalog_graph(repo_root / "catalog")
    catalog.close()
    substrate_paths = replace(
        default_substrate_catalog_paths(repo_root),
        l1_dcat_path=repo_root / "catalog/catalog.duckdb",
    )
    with duckdb.connect(str(substrate_paths.l1_dcat_path)) as connection:
        connection.executemany(
            """
            INSERT INTO ds_observations (
                observation_id, dataset_id, raw_variable, canonical_var,
                country_code, year, survey_year, wave, value, condition_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    f"shaped-owner-avg-income-{index}",
                    "acquisition.local.avg_income",
                    "avg_income",
                    "avg_income",
                    "UA",
                    1800 + index,
                    None,
                    None,
                    float(index % 2),
                    '{"unit":"synthetic index"}',
                )
                for index in range(8)
            ],
        )
    overlay_path = default_acquisition_overlay_path(repo_root)
    catalog_source = admit_fixture_catalog_source(
        repo_root=repo_root, database_path=substrate_paths.l1_dcat_path
    )
    gateway = RealValueOwnerGateway(
        repo_root=repo_root,
        catalog_overlay_path=overlay_path,
        catalog_serving_source=catalog_source,
    )
    with catalog_serving_source_scope(catalog_source):
        shaped = gateway.load_value_data_profile(
            candidate=candidate,
            problem=problem,
            world_record=_world_record(),
        )
        canonical = gateway.load_value_data_profile(
            candidate=_avg_income_candidate(),
            problem=problem,
            world_record=_world_record(),
        )

    assert shaped == canonical
    assert shaped.treatment_assignment_status == "owner_assignment_unresolved"

    simulation = _simulation(_world_record(), candidate_id=base.candidate_id)
    port = FoundryValuePort(
        evaluation_context=_simulation_execution_context(
            candidate=candidate,
            simulation=simulation,
            problem=problem,
        ),
        owner_gateway=gateway,
    )
    with catalog_serving_source_scope(catalog_source):
        observation = port(
            candidate=candidate,
            simulation=simulation,
            problem=problem,
            cycle_index=0,
        )

    assert observation.authority_blockers == ("treatment_assignment_not_owner_derived",)
    assert observation.acquisition_requirement is not None
    assert observation.value_receipt is None


def test_simulation_context_refuses_candidate_simulation_mismatch() -> None:
    problem = _avg_income_problem()
    candidate = _avg_income_candidate()
    simulation = _simulation(_world_record(), candidate_id="another_candidate")
    with pytest.raises(ValueError, match="eval_safety_simulation_candidate_mismatch"):
        _simulation_execution_context(
            candidate=candidate,
            simulation=simulation,
            problem=problem,
        )


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
            source_rows=(
                (
                    float(index),
                    f"dataset_{index}",
                    f"observation_{index}",
                    "synthetic index",
                ),
            ),
        )
        for index in range(4)
    )
    rows_payload = tuple(row.model_dump(mode="json") for row in rows)
    payload = {
        "schema_version": "policyos.runtime.value_data_profile.v2",
        "outcome": "synthetic_outcome",
        "measurement_unit": "synthetic index",
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
                    "synthetic index",
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


def test_value_port_selects_then_routes_missing_owner_assignment_to_acquisition(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A unit-valid profile lets method selection reach the missing-assignment gate."""
    world = _world_record()
    problem = _avg_income_problem()
    candidate = _avg_income_candidate()
    profile = _controlled_avg_income_owner_profile()

    def load_controlled_profile(
        _gateway: RealValueOwnerGateway,
        *,
        candidate: object,
        problem: DesignProblem,
        world_record: object,
    ) -> ValueDataProfile:
        assert candidate is candidate_arg
        assert problem is problem_arg
        assert world_record is world_arg
        return profile

    candidate_arg = candidate
    problem_arg = problem
    world_arg = world
    monkeypatch.setattr(
        RealValueOwnerGateway,
        "load_value_data_profile",
        load_controlled_profile,
    )

    simulation = _simulation(world, candidate_id="candidate_avg_income_real")
    observation = FoundryValuePort(
        evaluation_context=_simulation_execution_context(
            candidate=candidate,
            simulation=simulation,
            problem=problem,
        ),
        repo_root=Path.cwd(),
    )(
        candidate=candidate,
        simulation=simulation,
        problem=problem,
        cycle_index=0,
    )

    assert observation.status == "value_blocked"
    assert observation.selected_method_fqn is not None
    assert observation.value_receipt is None
    assert observation.authority_blockers == ("treatment_assignment_not_owner_derived",)
    assert observation.value_data_profile_content_hash == profile.content_hash
    assert isinstance(observation.method_selection_receipt, MethodSelectionReceipt)
    assert observation.method_selection_receipt.selection_authority == ("foundry_registry_advisor")
    assert len(observation.method_selection_receipt.denominator) > 1
    assert observation.acquisition_requirement is not None
    assert observation.acquisition_requirement.metadata["requirement"]["operator"] == "any_of"
    assert observation.acquisition_requirement.metadata["satisfaction_status"] == "unsatisfied"


def test_value_port_preserves_typed_method_run_owner_refusal() -> None:
    """A typed owner refusal keeps its blocker and provenance at the port boundary."""
    profile = _controlled_avg_income_owner_profile()
    world = _world_record()
    problem = _avg_income_problem()
    candidate = _avg_income_candidate()
    failure = ValueOwnerAccessError(
        "acquire_data:value_owner_measurement_unit_malformed_json",
        "owner condition_json is malformed; supply a valid declared unit",
        owner_access_ref="owner://source#measurement-unit-binding",
    )

    def observe_failure(selected_failure: Exception) -> ValuePortObservation:
        class Gateway:
            def load_value_data_profile(self, **_kwargs: Any) -> ValueDataProfile:
                return profile

            def load_value_method_run_intent(self, **_kwargs: Any) -> None:
                raise selected_failure

        simulation = _simulation(world, candidate_id=candidate.candidate_id)
        return FoundryValuePort(
            evaluation_context=_simulation_execution_context(
                candidate=candidate,
                simulation=simulation,
                problem=problem,
            ),
            owner_gateway=Gateway(),
        )(
            candidate=candidate,
            simulation=simulation,
            problem=problem,
            cycle_index=0,
        )

    observation = observe_failure(failure)

    assert observation.status == "value_blocked"
    assert observation.authority_blockers == (failure.code,)
    assert observation.value_ref is None
    assert observation.acquisition_requirement is None
    assert observation.selected_method_fqn is not None
    assert observation.method_selection_receipt is not None
    assert observation.value_data_profile_content_hash == profile.content_hash
    assert "owner condition_json is malformed" in str(observation.reason)
    assert "owner://source#measurement-unit-binding" in str(observation.reason)

    plain_error = ValueError(failure.code)
    plain_observation = observe_failure(plain_error)
    assert plain_observation.status == "value_blocked"
    assert plain_observation.authority_blockers == ("value_owner_method_run_intent_unresolved",)
    assert plain_observation.reason == (
        f"Owner method-run intent could not be resolved: {failure.code}"
    )
    assert plain_observation.value_ref is None
    assert plain_observation.method_selection_receipt is not None
    assert plain_observation.acquisition_requirement is None


def test_source_time_limitation_can_accompany_the_bound_treatment_gap() -> None:
    """N8 retains unknown source currentness without replacing its primary gap."""
    candidate_id = "candidate_source_time_limitation"
    base = ValuePortObservation(
        status="value_blocked",
        candidate_id=candidate_id,
        authority_blockers=("treatment_assignment_not_owner_derived",),
        reason="Treatment assignment remains unresolved.",
        decision_grade="blocked",
        acquisition_requirement=value_input_world_knowledge_requirement_gap(
            claim_ref=f"value-claim:{candidate_id}"
        ),
    )
    payload = base.model_dump(mode="python")
    payload["authority_blockers"] = (
        "treatment_assignment_not_owner_derived",
        "source_update_time_not_established",
    )

    limited = ValuePortObservation.model_validate(payload)

    assert limited.status == "value_blocked"
    assert limited.authority_blockers == (
        "treatment_assignment_not_owner_derived",
        "source_update_time_not_established",
    )
    assert limited.acquisition_requirement == base.acquisition_requirement
    assert limited.value_receipt is None

    payload["authority_blockers"] = (
        "treatment_assignment_not_owner_derived",
        "unbound_runtime_hint",
    )
    with pytest.raises(ValueError, match="value_acquisition_requirement_not_canonical"):
        ValuePortObservation.model_validate(payload)


def test_n8_value_port_accepts_recomputed_foundry_receipt_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An ordinary N8 call accepts the advisor receipt against recomputed context."""
    from polisyos.core.artifacts.ids import ArtifactID as CoreArtifactID
    from polisyos.core.artifacts.manifest import ArtifactRef as CoreArtifactRef
    from polisyos.data_forge.domains.catalog.knowledge.overlay import (
        ActivatedAcquisitionObservationProjection,
        CanonicalAcquisitionObservation,
        ObservationProvenanceClass,
    )

    candidate = _avg_income_candidate()
    problem = _avg_income_problem()
    world = _world_record()
    profile = _controlled_avg_income_owner_profile()

    receipt_ref = CoreArtifactRef(
        artifact_id=CoreArtifactID(_hash("1")),
        kind="epoch.activated_overlay_admission_receipt",
        media_type="application/json",
    )
    passport_ref = CoreArtifactRef(
        artifact_id=CoreArtifactID(_hash("2")),
        kind="epoch.acquisition_passport_snapshot",
        media_type="application/json",
    )
    projection = ActivatedAcquisitionObservationProjection.issue(
        receipt_ref=receipt_ref,
        receipt_content_sha256=_hash("3"),
        passport_ref=passport_ref,
        passport_content_sha256=_hash("4"),
        variable_id="avg_income",
        epoch_id=1,
        passport_id="fixture-passport",
        admission_content_sha256=_hash("5"),
        observations=(
            CanonicalAcquisitionObservation(
                observation_id="fixture-active-avg-income",
                dataset_id="fixture-acquired-avg-income",
                raw_variable="avg_income",
                canonical_var="avg_income",
                country_code="AM",
                year=2024,
                value=1.0,
                condition_json='{"unit":"usd"}',
                acquisition_method="fixture",
                source_watermark="fixture",
                dataset_version="1",
                observation_class=ObservationProvenanceClass.OBSERVED,
            ),
        ),
    )

    def load_fixture_profile(
        _gateway: RealValueOwnerGateway,
        *,
        candidate: object,
        problem: DesignProblem,
        world_record: object,
    ) -> ValueDataProfile:
        assert candidate is candidate_arg
        assert problem is problem_arg
        assert world_record is world_arg
        return profile

    candidate_arg = candidate
    problem_arg = problem
    world_arg = world
    monkeypatch.setattr(
        RealValueOwnerGateway,
        "load_value_data_profile",
        load_fixture_profile,
    )

    accepted_contexts: list[str] = []
    verify_context = MethodSelectionReceipt.verify_selection_context

    def capture_context(
        receipt: MethodSelectionReceipt, expected_selection_context_hash: str
    ) -> MethodSelectionReceipt:
        accepted_contexts.append(expected_selection_context_hash)
        return verify_context(receipt, expected_selection_context_hash)

    monkeypatch.setattr(MethodSelectionReceipt, "verify_selection_context", capture_context)
    simulation = _simulation(world, candidate_id=candidate.candidate_id)
    observation = FoundryValuePort(
        evaluation_context=_simulation_execution_context(
            candidate=candidate, simulation=simulation, problem=problem
        ),
        owner_gateway=RealValueOwnerGateway(
            repo_root=Path.cwd(),
            activated_observation_projection=projection,
        ),
    )(candidate=candidate, simulation=simulation, problem=problem, cycle_index=0)

    assert observation.status == "value_blocked"
    assert observation.authority_blockers == (
        "treatment_assignment_not_owner_derived",
        "source_update_time_not_established",
    )
    assert observation.method_selection_receipt is not None
    assert observation.method_selection_receipt.selection_authority == ("foundry_registry_advisor")
    assert observation.selected_method_fqn == (
        observation.method_selection_receipt.selected_method_fqn
    )
    assert accepted_contexts == [observation.method_selection_receipt.selection_context_hash]


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

    candidate = _avg_income_candidate()
    simulation = _simulation(_world_record(), candidate_id="candidate_avg_income_real")
    observation = FoundryValuePort(
        evaluation_context=_simulation_execution_context(
            candidate=candidate,
            simulation=simulation,
            problem=problem,
        ),
        repo_root=Path.cwd(),
    )(
        candidate=candidate,
        simulation=simulation,
        problem=problem,
        cycle_index=0,
    )

    assert observation.status == "value_blocked"
    assert observation.authority_blockers == ("value_method_selection_context_hash_mismatch",)
    assert observation.acquisition_requirement is None


def test_shaped_relation_certificate_cannot_open_missing_value_input_lane() -> None:
    problem = _avg_income_problem()
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
        problem=problem,
        world_record=_world_record(),
    )
    canonical_profile = gateway.load_value_data_profile(
        candidate=base,
        problem=problem,
        world_record=_world_record(),
    )

    assert forged_profile == canonical_profile

    simulation = _simulation(_world_record(), candidate_id=base.candidate_id)
    observation = FoundryValuePort(
        evaluation_context=_simulation_execution_context(
            candidate=candidate,
            simulation=simulation,
            problem=problem,
        ),
        repo_root=Path.cwd(),
    )(
        candidate=candidate,
        simulation=simulation,
        problem=problem,
        cycle_index=0,
    )

    assert observation.status == "value_blocked"
    assert observation.authority_blockers == ("treatment_assignment_not_owner_derived",)
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

    problem = _avg_income_problem()
    candidate = _avg_income_candidate()
    simulation = _simulation(_world_record(), candidate_id="candidate_avg_income_real")
    observation = FoundryValuePort(
        evaluation_context=_simulation_execution_context(
            candidate=candidate,
            simulation=simulation,
            problem=problem,
        ),
        repo_root=Path.cwd(),
    )(
        candidate=candidate,
        simulation=simulation,
        problem=problem,
        cycle_index=0,
    )

    assert observation.status == "value_blocked"
    assert observation.authority_blockers == ("value_method_selection_authority_unresolved",)
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

    simulation = _simulation(
        context.world_model_record,
        candidate_id=candidate.candidate_id,
    )
    observation = FoundryValuePort(
        evaluation_context=_simulation_execution_context(
            candidate=candidate,
            simulation=simulation,
            problem=problem,
        ),
        repo_root=Path.cwd(),
        cycle_substrate_context=context,
    )(
        candidate=candidate,
        simulation=simulation,
        problem=problem,
        cycle_index=0,
    )

    assert observation.status == "value_blocked"
    assert observation.authority_blockers == ("method_estimand_binding_mismatch",)
    assert observation.value_receipt is None
    assert observation.selected_method_fqn is not None
    assert observation.method_selection_receipt is not None
    assert observation.method_selection_receipt.selection_authority == ("foundry_registry_advisor")
    assert observation.method_selection_receipt.ranked_alternatives
    selected_alternative = next(
        row for row in observation.method_selection_receipt.ranked_alternatives if row.selected
    )
    assert "panel" not in selected_alternative.data_modalities
    assert observation.acquisition_requirement is None


@pytest.mark.parametrize("mutation", ["blocker", "claim_ref"])
def test_value_world_knowledge_gap_must_match_blocker_and_candidate(
    mutation: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    problem = _avg_income_problem()
    candidate = _avg_income_candidate()
    world = _world_record()
    profile = _controlled_avg_income_owner_profile()

    def load_controlled_profile(
        _gateway: RealValueOwnerGateway,
        *,
        candidate: object,
        problem: DesignProblem,
        world_record: object,
    ) -> ValueDataProfile:
        assert candidate is candidate_arg
        assert problem is problem_arg
        assert world_record is world_arg
        return profile

    candidate_arg = candidate
    problem_arg = problem
    world_arg = world
    monkeypatch.setattr(
        RealValueOwnerGateway,
        "load_value_data_profile",
        load_controlled_profile,
    )
    simulation = _simulation(world, candidate_id="candidate_avg_income_real")
    canonical = FoundryValuePort(
        evaluation_context=_simulation_execution_context(
            candidate=candidate,
            simulation=simulation,
            problem=problem,
        ),
        repo_root=Path.cwd(),
    )(
        candidate=candidate,
        simulation=simulation,
        problem=problem,
        cycle_index=0,
    )
    assert canonical.status == "value_blocked"
    assert canonical.authority_blockers == ("treatment_assignment_not_owner_derived",)
    assert canonical.acquisition_requirement is not None
    payload = canonical.model_dump(mode="python")
    if mutation == "blocker":
        payload["authority_blockers"] = ("unrelated_value_blocker",)
    else:
        payload["acquisition_requirement"] = value_input_world_knowledge_requirement_gap(
            claim_ref="value-claim:another-candidate"
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
    problem = _avg_income_problem()
    simulation = _simulation(world, candidate_id=candidate.candidate_id)

    observation = FoundryValuePort(
        evaluation_context=_simulation_execution_context(
            candidate=candidate,
            simulation=simulation,
            problem=problem,
        ),
        repo_root=Path.cwd(),
    )(
        candidate=candidate,
        simulation=simulation,
        problem=problem,
        cycle_index=0,
    )

    assert observation.status == "value_blocked"
    assert observation.value_receipt is None
    assert observation.authority_blockers == ("treatment_assignment_not_owner_derived",)
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
    assert (
        evidence["false_clear_counts"]["uncalibrated_observable_promotion_false_clear_count"] == 1
    )

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
    assert receipt.false_clear_counts["uncalibrated_observable_promotion_false_clear_count"] == 1


def test_report_only_did_interval_requires_owner_method_run_basis() -> None:
    """A transport label cannot promote a report-only CI to identified value bounds."""
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

    with pytest.raises(
        ValueError, match="foundry_method_refused_value:owner_method_run_basis_missing"
    ):
        _value_outer_set_from_foundry_result(
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


def test_production_value_block_is_real_data_gap_not_missing_inputs() -> None:
    world = _world_record()
    problem = _problem("value_gate_problem")
    candidate = _candidate()
    simulation = _simulation(world)

    observation = FoundryValuePort(
        evaluation_context=_simulation_execution_context(
            candidate=candidate,
            simulation=simulation,
            problem=problem,
        ),
        owner_gateway=RealValueOwnerGateway(repo_root=Path.cwd()),
        requested_method_fqn="causal.inference.synthetic_control@1.0.0",
    )(
        candidate=candidate,
        simulation=simulation,
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
    assert (
        observation.acquisition_requirement.metadata["availability"]["variable_id"]
        == "firm_survival"
    )
    assert observation.acquisition_requirement.metadata["availability"]["observation_count"] == 0
    assert "substrate owner" in str(observation.reason)
    assert "dataset_catalog.duckdb#variable/firm_survival" in str(observation.reason)
    assert "value_method_state_missing" not in observation.authority_blockers
    assert "world_model_record_missing" not in observation.authority_blockers


def test_missing_cycle_wmr_is_wiring_error_not_acquire_gap() -> None:
    world = _world_record()
    problem = _problem("value_gate_problem")
    simulation = _simulation(world).model_copy(update={"world_model_record": None})
    candidate = _candidate()

    with pytest.raises(ValueError, match="eval_safety_simulation_input_unresolved"):
        _simulation_execution_context(
            candidate=candidate,
            simulation=simulation,
            problem=problem,
        )


def test_value_port_reuses_cached_world_model_record() -> None:
    world = _world_record()
    problem = _problem("value_gate_problem")
    candidate = _candidate()
    simulation = _simulation(world)
    port = FoundryValuePort(
        evaluation_context=_simulation_execution_context(
            candidate=candidate,
            simulation=simulation,
            problem=problem,
        )
    )

    first_record, first_status, first_error = port._world_record_from_simulation(simulation)
    second_record, second_status, second_error = port._world_record_from_simulation(simulation)

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


def test_value_receipt_exposes_each_decisive_consistency_predicate() -> None:
    world = _world_record("1")
    receipt = _receipt(world)

    predicates = receipt.decisive_consistency_predicates()

    assert [
        predicate.model_dump(mode="json", exclude={"content_hash"}) for predicate in predicates
    ] == [
        {
            "rule_version": "polisyos.runtime.value_receipt_consistency.v1",
            "predicate_id": "transport_wmr_hash_equals_receipt_wmr_hash",
            "source_basis": "receipt_internal_consistency",
            "candidate_id": "candidate_value_gate",
            "observed_ref": world.content_hash,
            "expected_ref": world.content_hash,
            "satisfied": True,
            "predicate_provenance": "recomputed",
        },
        {
            "rule_version": "polisyos.runtime.value_receipt_consistency.v1",
            "predicate_id": "outer_set_wmr_ref_equals_receipt_wmr_hash",
            "source_basis": "receipt_internal_consistency",
            "candidate_id": "candidate_value_gate",
            "observed_ref": world.content_hash,
            "expected_ref": world.content_hash,
            "satisfied": True,
            "predicate_provenance": "recomputed",
        },
    ]
    assert len({predicate.content_hash for predicate in predicates}) == 2


def test_value_receipt_transport_hash_predicate_fails_independently() -> None:
    receipt = _receipt(_world_record("1"))
    payload = receipt.model_dump(mode="python")
    payload["value_outer_set"] = receipt.value_outer_set
    payload["transport_receipt"] = receipt.transport_receipt.model_copy(
        update={"world_model_record_content_hash": _hash("4")}
    )
    payload["calibration_receipt"] = receipt.calibration_receipt

    with pytest.raises(ValueError, match="transport_wmr_hash_mismatch"):
        ValueGateReceipt.model_validate(payload)


def test_value_receipt_outer_set_ref_predicate_fails_independently() -> None:
    receipt = _receipt(_world_record("1"))
    payload = receipt.model_dump(mode="python")
    payload["value_outer_set"] = receipt.value_outer_set.model_copy(
        update={"world_model_record_ref": _hash("4")}
    )
    payload["transport_receipt"] = receipt.transport_receipt
    payload["calibration_receipt"] = receipt.calibration_receipt

    with pytest.raises(ValueError, match="outer_set_wmr_ref_mismatch"):
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
    problem = _problem("value_gate_problem")
    candidate = _candidate()
    observation = FoundryValuePort(
        evaluation_context=_non_simulation_execution_context(
            mode=mode,
            candidate=candidate,
            world=world,
            problem=problem,
        ),
        owner_gateway=RealValueOwnerGateway(repo_root=Path.cwd()),
        requested_method_fqn="causal.inference.synthetic_control@1.0.0",
    )(
        candidate=candidate,
        simulation=_simulation(world),
        problem=problem,
        cycle_index=0,
    )

    assert observation.status == "value_blocked"
    assert observation.authority_blockers == ("eval_safety_verifier_unresolved",)


def test_non_simulation_blocks_before_value_gateway() -> None:
    """Non-simulation and simulation-laundering failures stop before N8 owner work."""

    candidate = _candidate()
    world = _world_record()
    simulation = _simulation(world)
    problem = _problem("value_gate_problem")

    class GatewaySpy:
        def __init__(self) -> None:
            self.calls = 0

        def load_value_data_profile(self, **_kwargs: object) -> object:
            self.calls += 1
            return object()

    class BlockingVerifier:
        def __init__(self) -> None:
            self.calls = 0
            self.challenges: list[EvalSafetyAdmissionChallenge] = []

        def require_admission(
            self,
            context: EvaluationExecutionContext,
            challenge: EvalSafetyAdmissionChallenge,
        ) -> EvalSafetyConsumerAdmissionReceipt:
            self.calls += 1
            self.challenges.append(challenge)
            return EvalSafetyConsumerAdmissionReceipt(
                status="blocked",
                intake_ref=context.intake_ref,
                certificate_ref=context.eval_safety_certificate_ref,
                current_revision_head_ref=None,
                execution_context_hash=evaluation_execution_context_hash(context),
                challenge=challenge,
                blocker_codes=("polisyos.eval_safety.certificate_stale@1.0.0",),
                verified_at=datetime(2026, 8, 27, tzinfo=UTC),
            )

    class ForgedPositiveVerifier:
        def require_admission(
            self,
            context: EvaluationExecutionContext,
            challenge: EvalSafetyAdmissionChallenge,
        ) -> EvalSafetyConsumerAdmissionReceipt:
            return EvalSafetyConsumerAdmissionReceipt(
                status="verified",
                intake_ref=context.intake_ref,
                certificate_ref=context.eval_safety_certificate_ref,
                current_revision_head_ref=context.eval_safety_revision_head_ref,
                execution_context_hash=evaluation_execution_context_hash(context),
                challenge=challenge,
                blocker_codes=(),
                verified_at=datetime(2026, 8, 27, tzinfo=UTC),
            )

    missing_gateway = GatewaySpy()
    missing = FoundryValuePort(
        evaluation_context=_non_simulation_execution_context(
            mode="field_pilot",
            candidate=candidate,
            world=world,
            problem=problem,
        ),
        owner_gateway=missing_gateway,  # type: ignore[arg-type]
    )(
        candidate=candidate,
        simulation=simulation,
        problem=problem,
        cycle_index=0,
    )
    blocked_gateway = GatewaySpy()
    blocking_verifier = BlockingVerifier()
    blocked_port = FoundryValuePort(
        evaluation_context=_non_simulation_execution_context(
            mode="field_pilot",
            candidate=candidate,
            world=world,
            problem=problem,
        ),
        eval_safety_verifier=blocking_verifier,
        owner_gateway=blocked_gateway,  # type: ignore[arg-type]
    )
    blocked = blocked_port(
        candidate=candidate,
        simulation=simulation,
        problem=problem,
        cycle_index=0,
    )
    blocked_again = blocked_port(
        candidate=candidate,
        simulation=simulation,
        problem=problem,
        cycle_index=1,
    )
    wrong_gateway = GatewaySpy()
    wrong_context = _non_simulation_execution_context(
        mode="field_pilot",
        candidate=candidate,
        world=world,
        problem=problem,
        candidate_id="different-candidate",
    )
    wrong = FoundryValuePort(
        evaluation_context=wrong_context,
        eval_safety_verifier=blocking_verifier,
        owner_gateway=wrong_gateway,  # type: ignore[arg-type]
    )(
        candidate=candidate,
        simulation=simulation,
        problem=problem,
        cycle_index=0,
    )
    forged_gateway = GatewaySpy()
    forged = FoundryValuePort(
        evaluation_context=_non_simulation_execution_context(
            mode="field_pilot",
            candidate=candidate,
            world=world,
            problem=problem,
        ),
        eval_safety_verifier=ForgedPositiveVerifier(),
        owner_gateway=forged_gateway,  # type: ignore[arg-type]
    )(
        candidate=candidate,
        simulation=simulation,
        problem=problem,
        cycle_index=0,
    )
    for input_class in ("real_world", "not_established"):
        laundering_gateway = GatewaySpy()
        laundering = FoundryValuePort(
            evaluation_context=_non_simulation_execution_context(
                mode="simulate_only",
                candidate=candidate,
                world=world,
                problem=problem,
                input_class=input_class,
            ),
            owner_gateway=laundering_gateway,  # type: ignore[arg-type]
        )(
            candidate=candidate,
            simulation=simulation,
            problem=problem,
            cycle_index=0,
        )
        assert laundering.status == "value_blocked"
        assert laundering.authority_blockers == ("eval_safety_simulation_provenance_mismatch",)
        assert laundering_gateway.calls == 0

    wrong_input_gateway = GatewaySpy()
    wrong_simulation_ref = _execution_ref("wrong-simulation", _hash("a"))
    wrong_input_context = _non_simulation_execution_context(
        mode="simulate_only",
        candidate=candidate,
        world=world,
        problem=problem,
        input_class="simulation",
    ).model_copy(
        update={
            "evaluation_input_refs": (wrong_simulation_ref,),
            "evaluation_input_provenance": (
                EvaluationInputProvenance(
                    input_ref=wrong_simulation_ref,
                    input_class="simulation",
                    predicate_provenance="recomputed",
                ),
            ),
        }
    )
    wrong_input = FoundryValuePort(
        evaluation_context=wrong_input_context,
        owner_gateway=wrong_input_gateway,  # type: ignore[arg-type]
    )(
        candidate=candidate,
        simulation=simulation,
        problem=problem,
        cycle_index=0,
    )
    assert wrong_input.status == "value_blocked"
    assert wrong_input.authority_blockers == ("eval_safety_simulation_provenance_mismatch",)
    assert wrong_input_gateway.calls == 0

    simulation_gateway = GatewaySpy()
    bound_simulation_context = _simulation_execution_context(
        candidate=candidate,
        simulation=simulation,
        problem=problem,
    )
    explicit_simulation = FoundryValuePort(
        evaluation_context=bound_simulation_context.model_copy(
            update={"evaluation_input_refs": (), "evaluation_input_provenance": ()}
        ),
        owner_gateway=simulation_gateway,  # type: ignore[arg-type]
    )(
        candidate=candidate,
        simulation=simulation,
        problem=problem,
        cycle_index=0,
    )
    assert missing.authority_blockers == ("eval_safety_verifier_unresolved",)
    assert blocked.authority_blockers == ("polisyos.eval_safety.certificate_stale@1.0.0",)
    assert blocked_again.authority_blockers == blocked.authority_blockers
    assert wrong.authority_blockers == ("eval_safety_execution_context_binding_mismatch",)
    assert forged.status == "value_blocked"
    assert forged.authority_blockers == ("eval_safety_consumer_admission_blocked",)
    assert missing_gateway.calls == blocked_gateway.calls == wrong_gateway.calls == 0
    assert forged_gateway.calls == 0
    assert blocking_verifier.calls == 2
    assert blocking_verifier.challenges[0] != blocking_verifier.challenges[1]
    assert explicit_simulation.status == "value_blocked"
    assert explicit_simulation.authority_blockers == ("eval_safety_simulation_provenance_mismatch",)
    assert simulation_gateway.calls == 0
    valid_simulation_gateway = GatewaySpy()
    valid_simulation = FoundryValuePort(
        evaluation_context=bound_simulation_context,
        owner_gateway=valid_simulation_gateway,  # type: ignore[arg-type]
    )(
        candidate=candidate,
        simulation=simulation,
        problem=_problem("value_gate_problem"),
        cycle_index=0,
    )
    assert valid_simulation.status == "value_blocked"
    assert valid_simulation.authority_blockers == ("value_owner_data_profile_invalid",)
    assert valid_simulation_gateway.calls == 1


@pytest.mark.parametrize("mutation", ["content", "identity", "schema_family"])
def test_foundry_binds_actual_world_model_record_before_verifier_or_owner(
    mutation: str,
) -> None:
    """Foundry binds recomputed WMR bytes, canonical ID, and schema family."""

    candidate = _candidate()
    world = _world_record()
    problem = _problem("value_gate_problem")
    context = _non_simulation_execution_context(
        mode="field_pilot",
        candidate=candidate,
        world=world,
        problem=problem,
    )
    active_simulation = _simulation(world)
    active_context = context
    if mutation == "content":
        active_simulation = active_simulation.model_copy(
            update={
                "world_model_record": world.model_copy(update={"policy_domain": "changed-domain"})
            }
        )
    elif mutation == "identity":
        active_simulation = active_simulation.model_copy(
            update={
                "world_model_record": world.model_copy(
                    update={"world_model_record_id": "world_model_record_deadbeefdeadbeef"}
                )
            }
        )
    else:
        active_context = context.model_copy(
            update={
                "world_model_record_ref": context.world_model_record_ref.model_copy(
                    update={"schema_ref": "polisyos.ir.model_spec@1.0"}
                )
            }
        )

    class GatewaySpy:
        def __init__(self) -> None:
            self.calls = 0

        def load_value_data_profile(self, **_kwargs: object) -> object:
            self.calls += 1
            return object()

    class VerifierSpy:
        def __init__(self) -> None:
            self.calls = 0

        def require_admission(
            self,
            checked_context: EvaluationExecutionContext,
            challenge: EvalSafetyAdmissionChallenge,
        ) -> EvalSafetyConsumerAdmissionReceipt:
            self.calls += 1
            return EvalSafetyConsumerAdmissionReceipt(
                status="blocked",
                intake_ref=checked_context.intake_ref,
                certificate_ref=checked_context.eval_safety_certificate_ref,
                current_revision_head_ref=None,
                execution_context_hash=evaluation_execution_context_hash(checked_context),
                challenge=challenge,
                blocker_codes=("polisyos.eval_safety.certificate_stale@1.0.0",),
                verified_at=datetime(2026, 8, 28, tzinfo=UTC),
            )

    gateway = GatewaySpy()
    verifier = VerifierSpy()
    observation = FoundryValuePort(
        evaluation_context=active_context,
        eval_safety_verifier=verifier,
        owner_gateway=gateway,  # type: ignore[arg-type]
    )(
        candidate=candidate,
        simulation=active_simulation,
        problem=problem,
        cycle_index=0,
    )

    assert observation.status == "value_blocked"
    assert observation.authority_blockers == ("eval_safety_world_model_record_binding_mismatch",)
    assert verifier.calls == 0
    assert gateway.calls == 0


def test_foundry_blocks_same_input_cross_problem_context_before_verifier_or_owner() -> None:
    candidate = _candidate()
    world = _world_record()
    simulation = _simulation(world)
    routed_problem = _problem("routed_value_gate_problem")
    foreign_problem = _problem("foreign_value_gate_problem")

    class GatewaySpy:
        def __init__(self) -> None:
            self.calls = 0

        def load_value_data_profile(self, **_kwargs: object) -> object:
            self.calls += 1
            return object()

    class VerifierSpy:
        def __init__(self) -> None:
            self.calls = 0

        def require_admission(
            self,
            context: EvaluationExecutionContext,
            challenge: EvalSafetyAdmissionChallenge,
        ) -> EvalSafetyConsumerAdmissionReceipt:
            self.calls += 1
            return EvalSafetyConsumerAdmissionReceipt(
                status="blocked",
                intake_ref=context.intake_ref,
                certificate_ref=context.eval_safety_certificate_ref,
                current_revision_head_ref=None,
                execution_context_hash=evaluation_execution_context_hash(context),
                challenge=challenge,
                blocker_codes=("polisyos.eval_safety.certificate_stale@1.0.0",),
                verified_at=datetime(2026, 8, 27, tzinfo=UTC),
            )

    gateway = GatewaySpy()
    verifier = VerifierSpy()
    foreign_context = _non_simulation_execution_context(
        mode="field_pilot",
        candidate=candidate,
        world=world,
        problem=foreign_problem,
    )

    observation = FoundryValuePort(
        evaluation_context=foreign_context,
        eval_safety_verifier=verifier,
        owner_gateway=gateway,  # type: ignore[arg-type]
    )(
        candidate=candidate,
        simulation=simulation,
        problem=routed_problem,
        cycle_index=0,
    )

    assert observation.status == "value_blocked"
    assert observation.authority_blockers == ("eval_safety_design_problem_binding_mismatch",)
    assert verifier.calls == 0
    assert gateway.calls == 0


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


def _n8_dependency_source_freeze() -> str:
    resolver = getattr(value_contract, "dependency_discriminant_source_freeze", None)
    assert callable(resolver), "missing behavior: N8 must derive the complete Foundry source freeze"
    return resolver(value_contract._repo_root())


def _build_n8_dependency_companion() -> object:
    builder = getattr(value_contract, "build_dependency_discriminant_companion", None)
    assert callable(builder), (
        "missing behavior: N8 must produce the shared Foundry dependency discriminant"
    )
    return builder(
        repo_root=value_contract._repo_root(),
        source_freeze=_n8_dependency_source_freeze(),
    )


def _legacy_n8_governing_issues() -> tuple[dict[str, Any], ...]:
    """Capture the unmodified N8 governing path independently of diagnostics."""

    root = value_contract._repo_root()
    return value_contract._legacy_value_gate_result(
        value_contract._appoint_git_product_root(root),
        source_freeze=_n8_dependency_source_freeze(),
    ).governing_issues


def _independent_n8_dependency_companion_hash(payload: dict[str, Any]) -> str:
    material = {key: value for key, value in payload.items() if key != "artifact_content_hash"}
    encoded = json.dumps(
        material,
        ensure_ascii=True,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _rebind_corrupt_dependency_discriminant(payload: dict[str, Any]) -> None:
    profile = payload["profile_discriminant"]
    rows = profile["resolved_distributions"]
    profile["distribution_set"] = domain_digest(
        DigestDomain.DISTRIBUTION_SET,
        canonical_json_bytes(rows),
    ).model_dump(mode="json")
    statement = {key: value for key, value in profile.items() if key != "discriminant_ref"}
    profile["discriminant_ref"] = domain_digest(
        DigestDomain.DEPENDENCY_DISCRIMINANT,
        canonical_json_bytes(statement),
    ).model_dump(mode="json")


def _seal_corrupt_n8_dependency_companion(payload: dict[str, Any]) -> None:
    payload["artifact_content_hash"] = _independent_n8_dependency_companion_hash(payload)


def _identity_equal_case_alias(path: Path) -> Path | None:
    """Return a differently cased spelling for one existing path when supported."""

    absolute = path.absolute()
    parts = list(absolute.parts)
    for index, part in enumerate(parts):
        swapped = part.swapcase()
        if swapped == part:
            continue
        candidate = Path(*parts[:index], swapped, *parts[index + 1 :])
        try:
            if candidate != absolute and os.path.samefile(candidate, absolute):
                return candidate
        except OSError:
            continue
    return None


def _git_test_environment() -> dict[str, str]:
    """Return a deterministic environment without ambient Git repository redirects."""

    return {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}


def _run_git_test_command(
    toplevel: Path,
    *args: str,
    text: bool = False,
) -> subprocess.CompletedProcess[Any]:
    """Run one real scratch Git command without ambient repository redirects."""

    return subprocess.run(
        ["git", *args],
        cwd=toplevel,
        env=_git_test_environment(),
        check=True,
        capture_output=True,
        text=text,
    )


def _initialize_git_test_repository(
    toplevel: Path,
    *,
    relative_path: Path,
    content: str,
) -> str:
    """Create one real scratch repository and return its derived head."""

    target = toplevel / relative_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    _run_git_test_command(toplevel, "init", "--quiet")
    _run_git_test_command(toplevel, "add", "--", relative_path.as_posix())
    _run_git_test_command(
        toplevel,
        "-c",
        "user.name=PolicyOS Test",
        "-c",
        "user.email=policyos-test@example.invalid",
        "commit",
        "--quiet",
        "-m",
        "test fixture",
    )
    return _run_git_test_command(toplevel, "rev-parse", "HEAD", text=True).stdout.strip()


def _research_torch_diagnostic(companion: object) -> object:
    companion_profile = companion.profile_discriminant  # type: ignore[attr-defined]
    declaration = dependency_profile_module.MethodCatalogDependencyProfileDeclaration(
        schema_version="polisyos.foundry.dependency-profile.v1",
        profile_id="research-diagnostic",
        root_distribution=companion_profile.root_distribution,
        extras=("research",),
        python_constraint=companion_profile.python_constraint,
        resolver_name=companion_profile.resolver_name,
        resolver_version=companion_profile.resolver_version,
        pyproject_ref=companion_profile.pyproject_ref,
        lockfile_ref=companion_profile.lockfile_ref,
    )
    marker_environment = default_environment()
    marker_environment["extra"] = ""
    profile = dependency_profile_module.resolve_dependency_discriminant(
        declaration,
        pyproject_bytes=(value_contract._repo_root() / "pyproject.toml").read_bytes(),
        lockfile_bytes=(value_contract._repo_root() / "uv.lock").read_bytes(),
        marker_environment=marker_environment,
    )
    assert isinstance(profile, dependency_profile_module.DependencyProfileDiscriminant)
    assert any(row.name == "torch" for row in profile.resolved_distributions)
    observations = dependency_profile_module.AmbientDependencyEnvironmentObservation(
        observation_kind="ambient",
        distributions=tuple(
            dependency_profile_module.InstalledDistributionObservation(
                name=row.name,
                version=("incompatible-version" if row.name == "torch" else row.version),
            )
            for row in profile.resolved_distributions
        ),
    )
    result = dependency_profile_module.diagnose_dependency_environment(
        discriminant=profile,
        observed_distributions=observations,
    )
    assert result.status == "fail"
    assert result.first_case.coordinate == "distribution:torch:version"
    return result


def test_n8_dependency_discriminant_companion_binds_owner_source_and_exact_n8_bytes() -> None:
    """The producer binds frozen owner data and raw N8 bytes, not labels or ambient state."""

    companion = _build_n8_dependency_companion()
    payload = companion.model_dump(mode="json")
    root = value_contract._repo_root()
    n8_bytes = (root / value_contract.OUTPUT_PATH).read_bytes()

    assert value_contract.declared_outputs() == [
        value_contract.DEPENDENCY_DISCRIMINANT_OUTPUT_PATH,
    ]
    assert set(payload) == {
        "schema_version",
        "rule_version",
        "produced_by",
        "authority_owner",
        "authority_purpose",
        "source_freeze",
        "n8_contract_ref",
        "profile_discriminant",
        "predicate_class",
        "decision_role",
        "authority_boundary",
        "artifact_content_hash",
    }
    assert payload["source_freeze"] == _n8_dependency_source_freeze()
    assert payload["n8_contract_ref"] == {
        "path": value_contract.OUTPUT_PATH,
        "schema_version": value_contract.SCHEMA_VERSION,
        "rule_version": value_contract.VALUE_GATE_RULE_VERSION,
        "content_hash": "sha256:" + hashlib.sha256(n8_bytes).hexdigest(),
    }
    assert payload["predicate_class"] == "recomputed"
    assert payload["decision_role"] == "ambient_non_decisive"
    assert payload["authority_boundary"]["may_not_use_for"] == [
        "n8_admission",
        "n10a_stage_gap_closure",
        "chronology_acceptance",
        "policy_publication",
        "policy_promotion",
    ]
    assert payload["profile_discriminant"]["resolved_distributions"]
    assert payload["artifact_content_hash"] == _independent_n8_dependency_companion_hash(payload)
    assert not {
        "diagnostic",
        "interpreter_path",
        "hostname",
        "machine_identity",
        "installed_environment_path",
        "production_data_ref",
    } & set(payload)


def test_n8_dependency_discriminant_write_and_check_modes_are_explicit_and_read_only(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Scratch writes are explicit, governed writes need --write, and checks do not mutate."""

    _build_n8_dependency_companion()
    source_freeze = _n8_dependency_source_freeze()
    candidate = tmp_path / "n8-dependency-discriminant.json"

    assert (
        value_contract.main(
            [
                "--write-dependency-discriminant",
                str(candidate),
                "--expected-source-freeze",
                source_freeze,
                "--output-format",
                "json",
            ]
        )
        == 0
    )
    write_report = json.loads(capsys.readouterr().out.splitlines()[-1])
    assert write_report["status"] == "pass"
    candidate_bytes = candidate.read_bytes()

    assert (
        value_contract.main(
            [
                "--write-dependency-discriminant",
                str(candidate),
                "--expected-source-freeze",
                source_freeze,
                "--output-format",
                "json",
            ]
        )
        == 1
    )
    overwrite_refused = json.loads(capsys.readouterr().out.splitlines()[-1])
    assert overwrite_refused["status"] == "fail"
    assert candidate.read_bytes() == candidate_bytes

    symlink_target = tmp_path / "n8-dependency-discriminant-target.json"
    symlink_target.write_bytes(b"candidate-target-sentinel")
    symlink_candidate = tmp_path / "n8-dependency-discriminant-symlink.json"
    symlink_candidate.symlink_to(symlink_target)
    assert (
        value_contract.main(
            [
                "--write-dependency-discriminant",
                str(symlink_candidate),
                "--expected-source-freeze",
                source_freeze,
                "--output-format",
                "json",
            ]
        )
        == 1
    )
    symlink_refused = json.loads(capsys.readouterr().out.splitlines()[-1])
    assert symlink_refused["status"] == "fail"
    assert symlink_candidate.is_symlink()
    assert symlink_target.read_bytes() == b"candidate-target-sentinel"

    symlink_parent_target = tmp_path / "n8-symlink-parent-target"
    symlink_parent_target.mkdir()
    symlink_parent = tmp_path / "n8-symlink-parent"
    symlink_parent.symlink_to(symlink_parent_target, target_is_directory=True)
    symlink_nested_candidate = symlink_parent / "nested-candidate.json"
    assert (
        value_contract.main(
            [
                "--write-dependency-discriminant",
                str(symlink_nested_candidate),
                "--expected-source-freeze",
                source_freeze,
                "--output-format",
                "json",
            ]
        )
        == 1
    )
    symlink_parent_refused = json.loads(capsys.readouterr().out.splitlines()[-1])
    assert symlink_parent_refused["status"] == "fail"
    assert not (symlink_parent_target / "nested-candidate.json").exists()

    assert (
        value_contract.main(
            [
                "--check-dependency-discriminant",
                str(candidate),
                "--expected-source-freeze",
                source_freeze,
                "--output-format",
                "json",
            ]
        )
        == 0
    )
    check_report = json.loads(capsys.readouterr().out.splitlines()[-1])
    assert check_report["status"] == "pass"
    assert candidate.read_bytes() == candidate_bytes

    assert (
        value_contract.main(
            [
                "--check-dependency-discriminant",
                str(candidate),
                "--expected-source-freeze",
                "0" * 40,
                "--output-format",
                "json",
            ]
        )
        == 1
    )
    wrong_freeze = json.loads(capsys.readouterr().out.splitlines()[-1])
    assert wrong_freeze["status"] == "fail"
    assert wrong_freeze["governing_issues"] == list(_legacy_n8_governing_issues())
    assert candidate.read_bytes() == candidate_bytes

    in_repo_candidate = (
        value_contract._repo_root() / f".n8-dependency-discriminant-{tmp_path.name}.json"
    )
    assert not in_repo_candidate.exists()
    assert (
        value_contract.main(
            [
                "--write-dependency-discriminant",
                str(in_repo_candidate),
                "--expected-source-freeze",
                source_freeze,
                "--output-format",
                "json",
            ]
        )
        == 1
    )
    in_repo_refused = json.loads(capsys.readouterr().out.splitlines()[-1])
    assert in_repo_refused["status"] == "fail"
    assert not in_repo_candidate.exists()

    git_toplevel = Path(
        subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=value_contract._repo_root(),
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    )
    whole_repo_candidate = (
        git_toplevel / ".github" / f"n8-dependency-discriminant-{tmp_path.name}.json"
    )
    assert not whole_repo_candidate.exists()
    try:
        whole_repo_exit = value_contract.main(
            [
                "--write-dependency-discriminant",
                str(whole_repo_candidate),
                "--expected-source-freeze",
                source_freeze,
                "--output-format",
                "json",
            ]
        )
        whole_repo_refused = json.loads(capsys.readouterr().out.splitlines()[-1])
        whole_repo_created = whole_repo_candidate.exists()
    finally:
        whole_repo_candidate.unlink(missing_ok=True)
    assert whole_repo_exit == 1
    assert whole_repo_refused["status"] == "fail"
    assert not whole_repo_created

    aliased_target = (
        git_toplevel / ".github" / f"n8-dependency-discriminant-aliased-{tmp_path.name}.json"
    )
    aliased_candidate = (
        git_toplevel.parent.parent
        / ".git"
        / ".."
        / git_toplevel.parent.name
        / git_toplevel.name
        / ".github"
        / aliased_target.name
    )
    assert aliased_candidate != aliased_target
    assert aliased_candidate.resolve() == aliased_target
    assert not aliased_target.exists()
    try:
        aliased_exit = value_contract.main(
            [
                "--write-dependency-discriminant",
                str(aliased_candidate),
                "--expected-source-freeze",
                source_freeze,
                "--output-format",
                "json",
            ]
        )
        aliased_refused = json.loads(capsys.readouterr().out.splitlines()[-1])
        aliased_created = aliased_target.exists()
    finally:
        aliased_target.unlink(missing_ok=True)
    assert aliased_exit == 1
    assert aliased_refused["status"] == "fail"
    assert not aliased_created

    governed = value_contract._repo_root() / value_contract.DEPENDENCY_DISCRIMINANT_OUTPUT_PATH
    governed_before = governed.read_bytes()
    assert (
        value_contract.main(
            [
                "--write-dependency-discriminant",
                str(governed),
                "--expected-source-freeze",
                source_freeze,
                "--output-format",
                "json",
            ]
        )
        == 1
    )
    refused = json.loads(capsys.readouterr().out.splitlines()[-1])
    assert refused["status"] == "fail"
    assert governed.read_bytes() == governed_before

    assert (
        value_contract.main(
            [
                "--write-dependency-discriminant",
                str(governed),
                "--write",
                "--expected-source-freeze",
                source_freeze,
                "--output-format",
                "json",
            ]
        )
        == 0
    )
    governed_written = json.loads(capsys.readouterr().out.splitlines()[-1])
    assert governed_written["status"] == "pass"
    assert governed.read_bytes() == governed_before

    assert (
        value_contract.main(
            [
                "--write",
                "--expected-source-freeze",
                source_freeze,
                "--output-format",
                "json",
            ]
        )
        == 1
    )
    legacy_refused = json.loads(capsys.readouterr().out.splitlines()[-1])
    assert legacy_refused["status"] == "not_established"
    assert governed.read_bytes() == governed_before


def test_n8_dependency_discriminant_case_alias_inside_repository_is_refused(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """An absent destination is classified by filesystem identity, not path spelling."""

    root = value_contract._repo_root()
    git_toplevel = Path(
        _run_git_test_command(root, "rev-parse", "--show-toplevel", text=True).stdout.strip()
    )
    aliased_toplevel = _identity_equal_case_alias(git_toplevel)
    if aliased_toplevel is None:
        pytest.skip("filesystem has no identity-equal differently cased path alias")
    canonical_existing_ancestor = root / "architecture"
    canonical_target = (
        root
        / "architecture"
        / f"n8-dependency-discriminant-case-alias-{tmp_path.name}"
        / "absent-parent"
        / "candidate.json"
    )
    aliased_target = (
        aliased_toplevel / root.relative_to(git_toplevel) / canonical_target.relative_to(root)
    )
    assert aliased_target != canonical_target
    assert os.path.samefile(
        aliased_toplevel / root.relative_to(git_toplevel) / "architecture",
        canonical_existing_ancestor,
    )
    assert not canonical_target.parent.exists()
    assert not canonical_target.exists()

    try:
        exit_code = value_contract.main(
            [
                "--write-dependency-discriminant",
                str(aliased_target),
                "--expected-source-freeze",
                _n8_dependency_source_freeze(),
                "--output-format",
                "json",
            ]
        )
        report = json.loads(capsys.readouterr().out.splitlines()[-1])
        created = canonical_target.exists()
    finally:
        canonical_target.unlink(missing_ok=True)
        for directory in (canonical_target.parent, canonical_target.parent.parent):
            if directory.exists():
                directory.rmdir()

    assert exit_code == 1
    assert report["status"] == "fail"
    assert not created


def test_n8_dependency_discriminant_rejects_every_appointed_repository_owned_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Candidate writes cannot enter any storage root owned by the appointment."""

    canonical_root = value_contract._repo_root()
    governed = canonical_root / value_contract.DEPENDENCY_DISCRIMINANT_OUTPUT_PATH
    recorded = value_contract.FoundryDependencyDiscriminantCompanion.model_validate_json(
        governed.read_bytes()
    )
    main_toplevel = tmp_path / "main-repository"
    linked_toplevel = tmp_path / "linked-worktree"
    _initialize_git_test_repository(
        main_toplevel,
        relative_path=Path("product/owner-source.txt"),
        content="appointed source\n",
    )
    _run_git_test_command(
        main_toplevel,
        "worktree",
        "add",
        "--quiet",
        "--detach",
        str(linked_toplevel),
        "HEAD",
    )
    product = linked_toplevel / "product"
    monkeypatch.setattr(value_contract, "_repo_root", lambda: product)

    def reuse_recorded_companion(
        *,
        appointment: object,
        source_freeze: str,
    ) -> value_contract.FoundryDependencyDiscriminantCompanion:
        del appointment, source_freeze
        return recorded

    monkeypatch.setattr(
        value_contract,
        "_build_dependency_discriminant_companion",
        reuse_recorded_companion,
    )
    appointment = value_contract._appoint_git_product_root(product)
    owned_roots = {
        "git-dir": appointment.git_dir,
        "common-dir": appointment.git_common_dir,
        "object-directory": appointment.object_directory,
        "index-parent": appointment.index_file.parent,
    }
    accepted: list[str] = []
    created: list[str] = []

    for label, owned_root in owned_roots.items():
        candidate = owned_root / f"n8-dependency-discriminant-{label}-{tmp_path.name}.json"
        assert not candidate.exists()
        try:
            try:
                value_contract.write_dependency_discriminant_companion(
                    product,
                    companion_path=candidate,
                    source_freeze="0" * 40,
                    allow_repository_write=False,
                )
            except ValueError:
                if candidate.exists():
                    created.append(label)
            else:
                accepted.append(label)
        finally:
            candidate.unlink(missing_ok=True)

    assert not accepted, f"repository-owned roots accepted candidate writes: {accepted}"
    assert not created, f"repository-owned roots received candidate files: {created}"


def test_n8_dependency_discriminant_owner_reads_ignore_git_redirects_after_appointment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """All owner-object reads remain pinned after ambient Git redirects mutate."""

    root = value_contract._repo_root()
    source_freeze = _n8_dependency_source_freeze()
    governed = root / value_contract.DEPENDENCY_DISCRIMINANT_OUTPUT_PATH
    recorded = value_contract.FoundryDependencyDiscriminantCompanion.model_validate_json(
        governed.read_bytes()
    )
    alternate = tmp_path / "redirect-repository"
    alternate.mkdir()
    _run_git_test_command(alternate, "init", "--quiet")
    appointment = value_contract._appoint_git_product_root(root)
    monkeypatch.setenv("GIT_DIR", str(alternate / ".git"))
    monkeypatch.setenv("GIT_WORK_TREE", str(alternate))
    monkeypatch.setenv("GIT_COMMON_DIR", str(alternate / ".git"))
    monkeypatch.setenv(
        "GIT_OBJECT_DIRECTORY",
        str(alternate / ".git" / "objects"),
    )
    monkeypatch.setenv(
        "GIT_ALTERNATE_OBJECT_DIRECTORIES",
        str(alternate / ".git" / "objects"),
    )
    monkeypatch.setenv("GIT_INDEX_FILE", str(alternate / ".git" / "index"))

    rebuilt = value_contract._build_dependency_discriminant_companion(
        appointment=appointment,
        source_freeze=source_freeze,
    )

    assert rebuilt.content_ref == recorded.content_ref
    assert rebuilt.profile_discriminant == recorded.profile_discriminant


@pytest.mark.parametrize("mutation", ["nested_git", "replaced_git_dir"])
def test_n8_dependency_discriminant_git_appointment_is_stable_or_fails_closed(
    mutation: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Later repository discovery cannot redirect or silently replace an appointment."""

    toplevel = tmp_path / "appointed-repository"
    product = toplevel / "product"
    head = _initialize_git_test_repository(
        toplevel,
        relative_path=Path("product/owner-source.txt"),
        content="appointed source\n",
    )
    monkeypatch.setattr(value_contract, "_repo_root", lambda: product)
    monkeypatch.setattr(
        value_contract,
        "_foundry_dependency_source_paths",
        lambda: (Path("owner-source.txt"),),
    )
    appointment = value_contract._appoint_git_product_root(product)
    if mutation == "nested_git":
        _run_git_test_command(product, "init", "--quiet")
        assert value_contract._dependency_discriminant_source_freeze(appointment) == head
    else:
        (toplevel / ".git").rename(toplevel / ".git-appointed")
        _run_git_test_command(toplevel, "init", "--quiet")
        with pytest.raises(ValueError, match="appointed Git identity changed"):
            value_contract._run_git(appointment, "rev-parse", "HEAD")


def test_n8_dependency_discriminant_git_reads_disable_replacement_objects(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Frozen owner bytes cannot be substituted through repository replacement refs."""

    toplevel = tmp_path / "appointed-repository"
    product = toplevel / "product"
    relative_path = Path("product/owner-source.txt")
    original_head = _initialize_git_test_repository(
        toplevel,
        relative_path=relative_path,
        content="original owner source\n",
    )
    monkeypatch.setattr(value_contract, "_repo_root", lambda: product)
    monkeypatch.setattr(
        value_contract,
        "_foundry_dependency_source_paths",
        lambda: (Path("owner-source.txt"),),
    )
    appointment = value_contract._appoint_git_product_root(product)
    (toplevel / relative_path).write_text("replacement owner source\n", encoding="utf-8")
    _run_git_test_command(toplevel, "add", "--", relative_path.as_posix())
    _run_git_test_command(
        toplevel,
        "-c",
        "user.name=PolicyOS Test",
        "-c",
        "user.email=policyos-test@example.invalid",
        "commit",
        "--quiet",
        "-m",
        "replacement fixture",
    )
    replacement_head = _run_git_test_command(
        toplevel,
        "rev-parse",
        "HEAD",
        text=True,
    ).stdout.strip()
    _run_git_test_command(toplevel, "replace", original_head, replacement_head)

    unprotected = _run_git_test_command(
        toplevel,
        "show",
        f"{original_head}:{relative_path.as_posix()}",
    ).stdout
    protected = value_contract._frozen_foundry_bytes(
        appointment,
        original_head,
        "owner-source.txt",
    )

    assert unprotected == b"replacement owner source\n"
    assert protected == b"original owner source\n"


@pytest.mark.parametrize(
    ("mechanism", "relative_git_path"),
    [
        ("alternates", "objects/info/alternates"),
        ("grafts", "info/grafts"),
        ("shallow", "shallow"),
    ],
)
def test_n8_dependency_discriminant_rejects_unsupported_git_semantics(
    mechanism: str,
    relative_git_path: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Alternates, grafts, and shallow history fail before replay or writing."""

    toplevel = tmp_path / f"appointed-{mechanism}"
    product = toplevel / "product"
    head = _initialize_git_test_repository(
        toplevel,
        relative_path=Path("product/owner-source.txt"),
        content="appointed source\n",
    )
    monkeypatch.setattr(value_contract, "_repo_root", lambda: product)
    monkeypatch.setattr(
        value_contract,
        "_foundry_dependency_source_paths",
        lambda: (Path("owner-source.txt"),),
    )
    appointment = value_contract._appoint_git_product_root(product)
    semantic_path = Path(
        _run_git_test_command(
            toplevel,
            "rev-parse",
            "--path-format=absolute",
            "--git-path",
            relative_git_path,
            text=True,
        ).stdout.strip()
    )
    semantic_path.parent.mkdir(parents=True, exist_ok=True)
    if mechanism == "alternates":
        external = tmp_path / "external-object-store"
        external.mkdir()
        _run_git_test_command(external, "init", "--bare", "--quiet")
        external_objects = external / "objects"
        semantic_path.write_text(str(external_objects) + "\n", encoding="utf-8")
    elif mechanism == "grafts":
        semantic_path.write_text(f"{head} {head}\n", encoding="utf-8")
    else:
        semantic_path.write_text(head + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="unsupported Git repository semantics"):
        value_contract._run_git(appointment, "rev-parse", "HEAD")
    with pytest.raises(ValueError, match="unsupported Git repository semantics"):
        value_contract._appoint_git_product_root(product)
    with pytest.raises(ValueError, match="unsupported Git repository semantics"):
        value_contract.dependency_discriminant_source_freeze(product)

    if mechanism == "alternates":
        candidate = external_objects / "n8-candidate.json"
        assert not candidate.exists()
        with pytest.raises(ValueError, match="unsupported Git repository semantics"):
            value_contract.write_dependency_discriminant_companion(
                product,
                companion_path=candidate,
                source_freeze=head,
                allow_repository_write=False,
            )
        assert not candidate.exists()


@pytest.mark.parametrize("hidden_by", ["eol_normalization", "assume_unchanged"])
def test_n8_dependency_discriminant_source_freeze_compares_raw_filesystem_bytes(
    hidden_by: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Raw owner-byte drift fails even when Git's index/attribute proxy reports clean."""

    toplevel = tmp_path / "appointed-repository"
    product = toplevel / "product"
    relative_path = Path("product/owner-source.txt")
    source_freeze = _initialize_git_test_repository(
        toplevel,
        relative_path=relative_path,
        content="original owner source\n",
    )
    (toplevel / ".gitattributes").write_text("*.txt text eol=lf\n", encoding="utf-8")
    _run_git_test_command(toplevel, "add", "--", ".gitattributes")
    _run_git_test_command(
        toplevel,
        "-c",
        "user.name=PolicyOS Test",
        "-c",
        "user.email=policyos-test@example.invalid",
        "commit",
        "--quiet",
        "-m",
        "attribute fixture",
    )
    monkeypatch.setattr(value_contract, "_repo_root", lambda: product)
    monkeypatch.setattr(
        value_contract,
        "_foundry_dependency_source_paths",
        lambda: (Path("owner-source.txt"),),
    )
    appointment = value_contract._appoint_git_product_root(product)
    target = toplevel / relative_path
    if hidden_by == "eol_normalization":
        target.write_bytes(b"original owner source\r\n")
    else:
        _run_git_test_command(
            toplevel,
            "update-index",
            "--assume-unchanged",
            "--",
            relative_path.as_posix(),
        )
        target.write_bytes(b"different owner source\n")
    proxy = subprocess.run(
        ["git", "diff", "--quiet", source_freeze, "--", relative_path.as_posix()],
        cwd=toplevel,
        env=_git_test_environment(),
        check=False,
        capture_output=True,
    )

    assert proxy.returncode == 0
    with pytest.raises(ValueError, match=r"source freeze.*bytes"):
        value_contract._require_current_foundry_source_freeze(
            appointment,
            source_freeze,
        )


@pytest.mark.parametrize("node_kind", ["symlink", "fifo"])
def test_n8_dependency_discriminant_state_token_rejects_nonregular_owner_source(
    node_kind: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The cache token and live freeze both consume the descriptor source gate."""

    from polisyos.foundry.methods.catalog import dependency_authority

    toplevel = tmp_path / "appointed-repository"
    product = toplevel / "product"
    relative_path = Path("product/owner-source.txt")
    source_freeze = _initialize_git_test_repository(
        toplevel,
        relative_path=relative_path,
        content="owner source\n",
    )
    monkeypatch.setattr(value_contract, "_repo_root", lambda: product)
    monkeypatch.setattr(
        value_contract,
        "_foundry_dependency_source_paths",
        lambda: (Path("owner-source.txt"),),
    )
    monkeypatch.setattr(
        dependency_authority,
        "_AUTHORITY_SOURCE_PATHS",
        (relative_path.as_posix(),),
    )
    appointment = value_contract._appoint_git_product_root(product)
    source = toplevel / relative_path
    source.unlink()
    if node_kind == "symlink":
        backing = tmp_path / "matching-backing-source.txt"
        backing.write_bytes(b"owner source\n")
        source.symlink_to(backing)
    else:
        os.mkfifo(source)

    with pytest.raises(ValueError, match="regular no-follow source"):
        value_contract._foundry_authority_state_token(appointment)
    with pytest.raises(ValueError, match="regular no-follow source"):
        value_contract._require_current_foundry_source_freeze(
            appointment,
            source_freeze,
        )


def test_n8_dependency_discriminant_appointed_scope_preserves_caller_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The appointed process scope preserves non-Git inputs and restores its caller."""

    appointment = value_contract._appoint_git_product_root(value_contract._repo_root())
    caller_path = f"{os.environ['PATH']}{os.pathsep}/n8-caller-path-sentinel"
    caller_sentinel = "n8-caller-environment-sentinel"
    monkeypatch.setenv("PATH", caller_path)
    monkeypatch.setenv("POLISYOS_N8_CALLER_SENTINEL", caller_sentinel)
    monkeypatch.setenv("GIT_DIR", "hostile-git-directory")
    monkeypatch.setenv("GIT_WORK_TREE", "hostile-git-worktree")
    monkeypatch.setenv("GIT_ALTERNATE_OBJECT_DIRECTORIES", "hostile-object-store")
    caller_environment = dict(os.environ)
    authority_state_token = value_contract._foundry_authority_state_token(appointment)

    with value_contract._appointed_git_process_environment(
        appointment,
        authority_state_token=authority_state_token,
    ):
        assert os.environ["PATH"] == caller_path
        assert os.environ["POLISYOS_N8_CALLER_SENTINEL"] == caller_sentinel
        assert os.environ["GIT_DIR"] == str(appointment.git_dir)
        assert os.environ["GIT_WORK_TREE"] == str(appointment.git_toplevel)
        assert "GIT_ALTERNATE_OBJECT_DIRECTORIES" not in os.environ

    assert dict(os.environ) == caller_environment


def test_n8_dependency_discriminant_real_legacy_call_uses_appointed_git_environment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The unchanged real governing call ignores hostile Git inputs and replacements."""

    root = value_contract._repo_root()
    appointment = value_contract._appoint_git_product_root(root)
    source_freeze = value_contract._dependency_discriminant_source_freeze(appointment)
    canonical_toplevel = appointment.git_toplevel
    alternate = tmp_path / "hostile-repository"
    _run_git_test_command(
        canonical_toplevel,
        "clone",
        "--quiet",
        "--no-hardlinks",
        "--no-checkout",
        str(canonical_toplevel),
        str(alternate),
    )
    original_head = value_contract._git_text(appointment, "rev-parse", "HEAD")
    _run_git_test_command(alternate, "checkout", "--quiet", "--detach", original_head)
    replacement_source = (
        alternate
        / "policy-engine"
        / "src"
        / "polisyos"
        / "foundry"
        / "methods"
        / "catalog"
        / "dependency_authority.py"
    )
    replacement_source.write_bytes(replacement_source.read_bytes() + b"\n# hostile replacement\n")
    _run_git_test_command(
        alternate,
        "add",
        "--",
        replacement_source.relative_to(alternate).as_posix(),
    )
    _run_git_test_command(
        alternate,
        "-c",
        "user.name=PolicyOS Test",
        "-c",
        "user.email=policyos-test@example.invalid",
        "commit",
        "--quiet",
        "-m",
        "replacement fixture",
    )
    replacement_head = _run_git_test_command(
        alternate,
        "rev-parse",
        "HEAD",
        text=True,
    ).stdout.strip()
    _run_git_test_command(alternate, "update-ref", "HEAD", original_head)
    _run_git_test_command(alternate, "replace", original_head, replacement_head)
    assert (
        b"hostile replacement"
        in _run_git_test_command(
            alternate,
            "show",
            f"{original_head}:{replacement_source.relative_to(alternate).as_posix()}",
        ).stdout
    )

    real_check_result = value_contract.check_result
    observed_git_environments: list[dict[str, str]] = []

    def recording_real_check_result(
        repo_root: Path,
        *,
        expected_source_freeze: str | None = None,
    ) -> object:
        observed_git_environments.append(
            {key: value for key, value in os.environ.items() if key.startswith("GIT_")}
        )
        return real_check_result(
            repo_root,
            expected_source_freeze=expected_source_freeze,
        )

    monkeypatch.setattr(value_contract, "check_result", recording_real_check_result)
    value_contract._catalog_denominator_evidence_cached.cache_clear()
    value_contract._cached_legacy_value_gate_transport.cache_clear()
    clean = value_contract._legacy_value_gate_result(
        appointment,
        source_freeze=source_freeze,
    )

    hostile = {
        "GIT_DIR": str(alternate / ".git"),
        "GIT_WORK_TREE": str(alternate),
        "GIT_COMMON_DIR": str(alternate / ".git"),
        "GIT_OBJECT_DIRECTORY": str(alternate / ".git" / "objects"),
        "GIT_ALTERNATE_OBJECT_DIRECTORIES": str(alternate / ".git" / "objects"),
        "GIT_INDEX_FILE": str(alternate / ".git" / "index"),
        "GIT_NO_REPLACE_OBJECTS": "0",
    }
    for key, value in hostile.items():
        monkeypatch.setenv(key, value)
    hostile_snapshot = dict(os.environ)
    value_contract._catalog_denominator_evidence_cached.cache_clear()
    value_contract._cached_legacy_value_gate_transport.cache_clear()
    redirected = value_contract._legacy_value_gate_result(
        appointment,
        source_freeze=source_freeze,
    )

    expected_git_environment = {
        key: value
        for key, value in value_contract._appointed_git_environment(appointment).items()
        if key.startswith("GIT_")
    }
    assert canonical_json_bytes(redirected.governing_issues) == canonical_json_bytes(
        clean.governing_issues
    )
    assert observed_git_environments == [expected_git_environment, expected_git_environment]
    assert expected_git_environment["GIT_NO_REPLACE_OBJECTS"] == "1"
    assert dict(os.environ) == hostile_snapshot


@pytest.mark.parametrize("exception_type", [RuntimeError, KeyboardInterrupt])
def test_n8_dependency_discriminant_governing_exception_escapes_and_restores_environment(
    exception_type: type[BaseException],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The appointed process scope restores Git inputs without absorbing failures."""

    appointment = value_contract._appoint_git_product_root(value_contract._repo_root())
    alternate = tmp_path / "redirect"
    monkeypatch.setenv("GIT_DIR", str(alternate / ".git"))
    monkeypatch.setenv("GIT_WORK_TREE", str(alternate))
    before = dict(os.environ)
    expected = value_contract._appointed_git_environment(appointment)

    def explode(
        _repo_root: Path,
        *,
        expected_source_freeze: str | None = None,
    ) -> object:
        del expected_source_freeze
        assert {key: value for key, value in os.environ.items() if key.startswith("GIT_")} == {
            key: value for key, value in expected.items() if key.startswith("GIT_")
        }
        raise exception_type("governing replay failed")

    monkeypatch.setattr(value_contract, "check_result", explode)
    value_contract._cached_legacy_value_gate_transport.cache_clear()
    with pytest.raises(exception_type, match="governing replay failed"):
        value_contract._legacy_value_gate_result(
            appointment,
            source_freeze=value_contract._dependency_discriminant_source_freeze(appointment),
        )
    assert dict(os.environ) == before


def test_n8_dependency_discriminant_authority_state_misses_both_caches(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Same-HEAD authority byte drift invalidates inner and outer memoization."""

    from polisyos.foundry.methods.catalog import dependency_authority
    from polisyos.foundry.methods.catalog import snapshot as catalog_snapshot

    toplevel = tmp_path / "appointed-repository"
    product = toplevel / "product"
    authority_source = product / "owner-source.txt"
    source_freeze = _initialize_git_test_repository(
        toplevel,
        relative_path=Path("product/owner-source.txt"),
        content="authority source one\n",
    )
    output = product / value_contract.OUTPUT_PATH
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("{}\n", encoding="utf-8")
    monkeypatch.setattr(value_contract, "_repo_root", lambda: product)
    monkeypatch.setattr(
        value_contract,
        "_foundry_dependency_source_paths",
        lambda: (Path("owner-source.txt"),),
    )
    monkeypatch.setattr(
        dependency_authority,
        "_AUTHORITY_SOURCE_PATHS",
        ("product/owner-source.txt",),
    )
    generations: list[int] = []

    @dataclass(frozen=True)
    class FakeAuthorityResult:
        generation: int

        def model_dump(self, *, mode: str) -> dict[str, object]:
            assert mode == "json"
            return {"generation": self.generation}

    def fake_authority_builder(*args: object, **kwargs: object) -> FakeAuthorityResult:
        del args, kwargs
        generation = len(generations) // 2
        generations.append(generation)
        return FakeAuthorityResult(generation)

    monkeypatch.setattr(
        catalog_snapshot,
        "build_method_catalog_runtime_identity",
        fake_authority_builder,
    )
    monkeypatch.setattr(
        catalog_snapshot,
        "build_method_catalog_provenance_manifest",
        fake_authority_builder,
    )
    value_contract._catalog_denominator_evidence_cached.cache_clear()
    first_inner = value_contract._catalog_denominators(source_freeze, product)
    authority_source.write_text("authority source two\n", encoding="utf-8")
    second_inner = value_contract._catalog_denominators(source_freeze, product)
    assert first_inner != second_inner
    assert generations == [0, 0, 1, 1]

    appointment = value_contract._appoint_git_product_root(product)
    governing_calls: list[int] = []

    def fake_governing_result(
        _repo_root: Path,
        *,
        expected_source_freeze: str | None = None,
    ) -> value_contract.ValueGateValidationResult:
        del expected_source_freeze
        governing_calls.append(len(governing_calls) + 1)
        return value_contract.ValueGateValidationResult(
            governing_issues=({"code": f"generation_{governing_calls[-1]}"},),
            ambient_findings=(),
        )

    monkeypatch.setattr(value_contract, "check_result", fake_governing_result)
    value_contract._cached_legacy_value_gate_transport.cache_clear()
    first_outer = value_contract._legacy_value_gate_result(
        appointment,
        source_freeze=source_freeze,
    )
    authority_source.write_text("authority source three\n", encoding="utf-8")
    second_outer = value_contract._legacy_value_gate_result(
        appointment,
        source_freeze=source_freeze,
    )
    assert first_outer.governing_issues != second_outer.governing_issues
    assert governing_calls == [1, 2]


def test_n8_dependency_discriminant_cached_governing_result_cannot_be_poisoned(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Mutating one result cannot alter later direct, oracle, or CLI governing evidence."""

    companion = cast(
        "value_contract.FoundryDependencyDiscriminantCompanion",
        _build_n8_dependency_companion(),
    )
    source_freeze = _n8_dependency_source_freeze()
    appointment = value_contract._appoint_git_product_root(value_contract._repo_root())
    value_contract._catalog_denominator_evidence_cached.cache_clear()
    value_contract._cached_legacy_value_gate_transport.cache_clear()
    authority_state_token = value_contract._foundry_authority_state_token(appointment)
    inner_transport = value_contract._catalog_denominator_evidence_cached(
        source_freeze,
        appointment.product_root,
        authority_state_token,
    )
    assert isinstance(inner_transport, bytes)
    inner_wire = json.loads(inner_transport)
    inner_transport_baseline = canonical_json_bytes(inner_wire)
    inner_wire["denominators"]["catalog_dependency_authority"]["cache_poison"] = {
        "nested": ["transport"]
    }
    assert (
        canonical_json_bytes(
            json.loads(
                value_contract._catalog_denominator_evidence_cached(
                    source_freeze,
                    appointment.product_root,
                    authority_state_token,
                )
            )
        )
        == inner_transport_baseline
    )
    inner_first = value_contract._catalog_denominator_evidence(
        source_freeze,
        appointment.product_root,
    )
    inner_baseline = canonical_json_bytes(inner_first)
    inner_first[0]["catalog_dependency_authority"]["cache_poison"] = {"nested": ["inner"]}
    inner_second = value_contract._catalog_denominator_evidence(
        source_freeze,
        appointment.product_root,
    )
    assert canonical_json_bytes(inner_second) == inner_baseline
    diagnostic = _research_torch_diagnostic(companion)
    first = value_contract.validate_foundry_dependency_discriminant(
        repo_root=value_contract._repo_root(),
        companion=companion,
        diagnostic_verification=diagnostic,
    )
    baseline = canonical_json_bytes(first.governing_issues)
    ambient_baseline = canonical_json_bytes(first.ambient_findings)
    assert first.governing_issues
    assert first.ambient_findings
    first.governing_issues[0]["cache_poison"] = {"nested": ["direct"]}
    for finding in first.ambient_findings:
        finding["cache_poison"] = {"nested": ["ambient"]}

    second = value_contract.validate_foundry_dependency_discriminant(
        repo_root=value_contract._repo_root(),
        companion=companion,
        diagnostic_verification=diagnostic,
    )
    oracle_first = _legacy_n8_governing_issues()
    oracle_first[0]["cache_poison"] = {"nested": ["oracle"]}
    oracle_second = _legacy_n8_governing_issues()
    governed = value_contract._repo_root() / value_contract.DEPENDENCY_DISCRIMINANT_OUTPUT_PATH
    governed_before = governed.read_bytes()
    exit_code = value_contract.main(
        [
            "--check-dependency-discriminant",
            str(governed),
            "--expected-source-freeze",
            source_freeze,
            "--output-format",
            "json",
        ]
    )
    report = json.loads(capsys.readouterr().out.splitlines()[-1])

    assert exit_code == 0
    assert canonical_json_bytes(second.governing_issues) == baseline
    assert canonical_json_bytes(second.ambient_findings) == ambient_baseline
    assert canonical_json_bytes(oracle_second) == baseline
    assert canonical_json_bytes(report["governing_issues"]) == baseline
    assert not any("cache_poison" in finding for finding in second.ambient_findings)
    assert governed.read_bytes() == governed_before


def test_n8_dependency_discriminant_research_warning_is_ambient_non_decisive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A cross-profile research claim is unaccepted and cannot change governing bytes."""

    companion = _build_n8_dependency_companion()
    admitted = dependency_profile_module.DependencyEnvironmentDiagnosticPass(
        status="pass",
        ordered_cases=(),
        first_case=None,
        predicate_class="recomputed",
    )
    research = _research_torch_diagnostic(companion)
    monkeypatch.setattr(
        value_contract,
        "_current_dependency_environment_diagnostic",
        lambda _profile: admitted,
    )

    admitted_result = value_contract.validate_foundry_dependency_discriminant(
        repo_root=value_contract._repo_root(),
        companion=companion,
        diagnostic_verification=admitted,
    )
    research_result = value_contract.validate_foundry_dependency_discriminant(
        repo_root=value_contract._repo_root(),
        companion=companion,
        diagnostic_verification=research,
    )

    expected_governing = _legacy_n8_governing_issues()
    assert admitted_result.governing_issues == research_result.governing_issues
    assert admitted_result.governing_issues == expected_governing
    assert canonical_json_bytes(admitted_result.governing_issues) == canonical_json_bytes(
        research_result.governing_result
    )
    assert not any(
        finding.get("code") == "dependency_environment_diagnostic_failed"
        for finding in admitted_result.ambient_findings
    )
    research_codes = {finding.get("code") for finding in research_result.ambient_findings}
    assert "dependency_environment_diagnostic_failed" not in research_codes
    assert "dependency_environment_diagnostic_not_reconciled" in research_codes
    warning = next(
        finding
        for finding in research_result.ambient_findings
        if finding.get("code") == "dependency_environment_diagnostic_not_reconciled"
    )
    assert warning["decision_role"] == "ambient_non_decisive"
    assert "diagnostic" not in warning
    assert warning["unaccepted_diagnostic_claim"]["first_case"]["coordinate"] == (
        "distribution:torch:version"
    )
    assert (
        warning["unaccepted_diagnostic_claim"]["ordered_cases"][0]
        == (warning["unaccepted_diagnostic_claim"]["first_case"])
    )
    assert warning["current_diagnostic"]["status"] == "pass"


def test_n8_dependency_discriminant_supplied_pass_requires_current_recomputation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A supplied pass that disagrees with current observation becomes a diagnostic non-receipt."""

    companion = _build_n8_dependency_companion()
    supplied = dependency_profile_module.DependencyEnvironmentDiagnosticPass(
        status="pass",
        ordered_cases=(),
        first_case=None,
        predicate_class="recomputed",
    )
    current = _research_torch_diagnostic(companion)
    monkeypatch.setattr(
        value_contract,
        "_current_dependency_environment_diagnostic",
        lambda _profile: current,
    )

    result = value_contract.validate_foundry_dependency_discriminant(
        repo_root=value_contract._repo_root(),
        companion=companion,
        diagnostic_verification=supplied,
    )

    assert result.governing_issues == _legacy_n8_governing_issues()
    warning = next(
        finding
        for finding in result.ambient_findings
        if finding.get("code") == "dependency_environment_diagnostic_not_reconciled"
    )
    assert warning["unaccepted_diagnostic_claim"]["status"] == "pass"
    assert warning["current_diagnostic"]["status"] == "fail"


def test_n8_dependency_discriminant_supplied_not_established_must_reconcile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A not-established claim for another observation is an ambient non-receipt."""

    companion = _build_n8_dependency_companion()
    current = dependency_profile_module.DependencyEnvironmentDiagnosticPass(
        status="pass",
        ordered_cases=(),
        first_case=None,
        predicate_class="recomputed",
    )
    supplied = dependency_profile_module.DependencyEnvironmentDiagnosticNotEstablished(
        status="not_established",
        code="installed_distribution_source_evidence_not_established",
        missing_coordinates=("distribution:torch:source_kind",),
        predicate_class="not_established",
    )
    monkeypatch.setattr(
        value_contract,
        "_current_dependency_environment_diagnostic",
        lambda _profile: current,
    )

    result = value_contract.validate_foundry_dependency_discriminant(
        repo_root=value_contract._repo_root(),
        companion=companion,
        diagnostic_verification=supplied,
    )

    assert result.content_ref == companion.content_ref
    assert result.governing_issues == _legacy_n8_governing_issues()
    warning = next(
        finding
        for finding in result.ambient_findings
        if finding.get("code") == "dependency_environment_diagnostic_not_reconciled"
    )
    assert "diagnostic" not in warning
    assert warning["unaccepted_diagnostic_claim"]["status"] == "not_established"
    assert warning["current_diagnostic"]["status"] == "pass"


def test_n8_dependency_discriminant_matching_supplied_fail_is_ambient_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An exactly reconciled fail remains a self-describing ambient warning."""

    companion = _build_n8_dependency_companion()
    matching_fail = _research_torch_diagnostic(companion)
    monkeypatch.setattr(
        value_contract,
        "_current_dependency_environment_diagnostic",
        lambda _profile: matching_fail,
    )

    result = value_contract.validate_foundry_dependency_discriminant(
        repo_root=value_contract._repo_root(),
        companion=companion,
        diagnostic_verification=matching_fail,
    )

    assert result.content_ref == companion.content_ref
    assert result.governing_issues == _legacy_n8_governing_issues()
    warning = next(
        finding
        for finding in result.ambient_findings
        if finding.get("code") == "dependency_environment_diagnostic_failed"
    )
    assert warning["diagnostic"] == matching_fail.model_dump(mode="json")
    assert not any(
        finding.get("code") == "dependency_environment_diagnostic_not_reconciled"
        for finding in result.ambient_findings
    )


@pytest.mark.parametrize("exception_type", [OSError, RuntimeError])
def test_n8_dependency_discriminant_observer_failure_is_ambient_nonreceipt(
    exception_type: type[Exception],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Ordinary observer failures cannot invalidate a received companion or CLI check."""

    companion = _build_n8_dependency_companion()
    source_freeze = _n8_dependency_source_freeze()

    def unavailable_observer(_profile: object) -> object:
        raise exception_type("ambient dependency observer unavailable")

    monkeypatch.setattr(
        value_contract,
        "_current_dependency_environment_diagnostic",
        unavailable_observer,
    )

    direct = value_contract.validate_foundry_dependency_discriminant(
        repo_root=value_contract._repo_root(),
        companion=companion,
        diagnostic_verification=None,
    )

    assert direct.content_ref == companion.content_ref
    assert direct.governing_issues == _legacy_n8_governing_issues()
    assert any(
        finding.get("code") == "dependency_environment_diagnostic_not_received"
        for finding in direct.ambient_findings
    )

    governed = value_contract._repo_root() / value_contract.DEPENDENCY_DISCRIMINANT_OUTPUT_PATH
    governed_before = governed.read_bytes()
    assert (
        value_contract.main(
            [
                "--check-dependency-discriminant",
                str(governed),
                "--expected-source-freeze",
                source_freeze,
                "--output-format",
                "json",
            ]
        )
        == 0
    )
    report = json.loads(capsys.readouterr().out.splitlines()[-1])
    assert report["status"] == "pass"
    assert report["content_ref"] == companion.content_ref
    assert report["governing_issues"] == list(_legacy_n8_governing_issues())
    assert any(
        finding.get("code") == "dependency_environment_diagnostic_not_received"
        for finding in report["ambient_findings"]
    )
    assert governed.read_bytes() == governed_before


@pytest.mark.parametrize("exception_type", [OSError, RuntimeError])
def test_n8_dependency_discriminant_supplied_protocol_failure_is_ambient_nonreceipt(
    exception_type: type[Exception],
) -> None:
    """Every ordinary supplied-object protocol failure remains ambient-only."""

    companion = cast(
        "value_contract.FoundryDependencyDiscriminantCompanion",
        _build_n8_dependency_companion(),
    )

    class ExplodingDiagnostic(dependency_profile_module.DependencyEnvironmentDiagnosticPass):
        def model_dump(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
            del args, kwargs
            raise exception_type("supplied diagnostic transport unavailable")

    supplied = ExplodingDiagnostic(
        status="pass",
        ordered_cases=(),
        first_case=None,
        predicate_class="recomputed",
    )

    result = value_contract.validate_foundry_dependency_discriminant(
        repo_root=value_contract._repo_root(),
        companion=companion,
        diagnostic_verification=supplied,
    )

    assert result.content_ref == companion.content_ref
    assert result.governing_issues == _legacy_n8_governing_issues()
    finding = next(
        finding
        for finding in result.ambient_findings
        if finding.get("code") == "dependency_environment_diagnostic_not_received"
    )
    assert finding == {
        "code": "dependency_environment_diagnostic_not_received",
        "decision_role": "ambient_non_decisive",
    }


def test_n8_dependency_discriminant_supplied_protocol_base_exception_escapes() -> None:
    """Process-control BaseException remains outside the ambient intake boundary."""

    companion = cast(
        "value_contract.FoundryDependencyDiscriminantCompanion",
        _build_n8_dependency_companion(),
    )

    class InterruptingDiagnostic(dependency_profile_module.DependencyEnvironmentDiagnosticPass):
        def model_dump(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
            del args, kwargs
            raise KeyboardInterrupt("process-control interrupt")

    supplied = InterruptingDiagnostic(
        status="pass",
        ordered_cases=(),
        first_case=None,
        predicate_class="recomputed",
    )

    with pytest.raises(KeyboardInterrupt, match="process-control interrupt"):
        value_contract.validate_foundry_dependency_discriminant(
            repo_root=value_contract._repo_root(),
            companion=companion,
            diagnostic_verification=supplied,
        )


def test_n8_dependency_discriminant_rejects_unappointed_isomorphic_git_checkout(
    tmp_path: Path,
) -> None:
    """An alternate Git checkout cannot appoint itself by copying paths and commits."""

    canonical_root = value_contract._repo_root()
    canonical_toplevel = Path(
        subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=canonical_root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    )
    alternate_toplevel = tmp_path / "alternate-checkout"
    subprocess.run(
        [
            "git",
            "clone",
            "--shared",
            "--no-checkout",
            str(canonical_toplevel),
            str(alternate_toplevel),
        ],
        check=True,
        capture_output=True,
    )
    alternate_root = alternate_toplevel / canonical_root.name
    alternate_root.mkdir()
    tracked_paths = subprocess.run(
        ["git", "ls-tree", "-r", "--name-only", "HEAD"],
        cwd=alternate_toplevel,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    assert all(
        f"{canonical_root.name}/{path.as_posix()}" in tracked_paths
        for path in value_contract._foundry_dependency_source_paths()
    )
    assert (
        subprocess.run(
            ["git", "cat-file", "-e", f"{_n8_dependency_source_freeze()}^{{commit}}"],
            cwd=alternate_toplevel,
            check=False,
            capture_output=True,
        ).returncode
        == 0
    )

    with pytest.raises(ValueError, match="not the appointed product root"):
        value_contract.dependency_discriminant_source_freeze(alternate_root)


@pytest.mark.parametrize(
    "case_id",
    [
        "root",
        "selected_distribution",
        "source_freeze",
        "n8_content_ref",
        "decision_role",
        "digest_domain",
        "strict_shape",
        "may_not_use_for:n8_admission",
        "may_not_use_for:n10a_stage_gap_closure",
        "may_not_use_for:chronology_acceptance",
        "may_not_use_for:policy_publication",
        "may_not_use_for:policy_promotion",
    ],
)
def test_n8_dependency_discriminant_corruption_is_diagnostic_nonreceipt(
    case_id: str,
    tmp_path: Path,
) -> None:
    """Self-consistent corruptions fail owner replay without changing legacy governing status."""

    companion = _build_n8_dependency_companion()
    payload = copy.deepcopy(companion.model_dump(mode="json"))
    if case_id == "root":
        payload["profile_discriminant"]["root_distribution"] = "forged-root"
        _rebind_corrupt_dependency_discriminant(payload)
    elif case_id == "selected_distribution":
        payload["profile_discriminant"]["resolved_distributions"][0]["selected_artifact"][
            "value"
        ] = "sha256:" + "0" * 64
        _rebind_corrupt_dependency_discriminant(payload)
    elif case_id == "source_freeze":
        payload["source_freeze"] = "0" * 40
    elif case_id == "n8_content_ref":
        payload["n8_contract_ref"]["content_hash"] = "sha256:" + "0" * 64
    elif case_id == "decision_role":
        payload["decision_role"] = "governing"
    elif case_id == "digest_domain":
        payload["profile_discriminant"]["discriminant_ref"]["domain"] = "dependency-closure"
    elif case_id == "strict_shape":
        payload["undeclared_field"] = True
    else:
        denied_use = case_id.partition(":")[2]
        payload["authority_boundary"]["may_not_use_for"].remove(denied_use)
    _seal_corrupt_n8_dependency_companion(payload)
    scratch = tmp_path / f"{case_id.replace(':', '-')}.json"
    scratch.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    scratch_before = scratch.read_bytes()

    result = value_contract.check_dependency_discriminant_companion(
        value_contract._repo_root(),
        companion_path=scratch,
    )

    assert result.governing_issues == _legacy_n8_governing_issues()
    assert any(
        finding.get("code") == "dependency_discriminant_diagnostic_not_received"
        for finding in result.ambient_findings
    )
    assert scratch.read_bytes() == scratch_before


@pytest.mark.parametrize(
    "forgery_kind",
    ["mapping", "model_copy", "model_construct"],
)
def test_n8_dependency_discriminant_forged_pass_with_mismatching_rows_is_nonreceipt(
    forgery_kind: str,
) -> None:
    """A pass-shaped diagnostic cannot retain mismatch cases behind strict typing."""

    companion = _build_n8_dependency_companion()
    failed = _research_torch_diagnostic(companion)
    if forgery_kind == "mapping":
        forged: object = {
            "status": "pass",
            "ordered_cases": [failed.first_case.model_dump(mode="json")],
            "first_case": None,
            "predicate_class": "recomputed",
        }
    else:
        valid_pass = dependency_profile_module.DependencyEnvironmentDiagnosticPass(
            status="pass",
            ordered_cases=(),
            first_case=None,
            predicate_class="recomputed",
        )
        if forgery_kind == "model_copy":
            forged = valid_pass.model_copy(update={"ordered_cases": (failed.first_case,)})
        else:
            forged = valid_pass.__class__.model_construct(
                status="pass",
                ordered_cases=(failed.first_case,),
                first_case=None,
                predicate_class="recomputed",
            )

    result = value_contract.validate_foundry_dependency_discriminant(
        repo_root=value_contract._repo_root(),
        companion=companion,
        diagnostic_verification=forged,
    )

    assert result.governing_issues == _legacy_n8_governing_issues()
    assert any(
        finding.get("code") == "dependency_environment_diagnostic_not_received"
        for finding in result.ambient_findings
    )


@pytest.mark.parametrize("bypass_kind", ["model_copy", "model_construct"])
def test_n8_dependency_discriminant_model_bypass_is_revalidated(
    bypass_kind: str,
) -> None:
    """Trusted-looking model instances must re-enter strict transport validation."""

    companion = _build_n8_dependency_companion()
    if bypass_kind == "model_copy":
        bypassed = companion.model_copy(update={"decision_role": "governing"})
    else:
        values = {name: getattr(companion, name) for name in companion.__class__.model_fields}
        values["decision_role"] = "governing"
        bypassed = companion.__class__.model_construct(**values)

    result = value_contract.validate_foundry_dependency_discriminant(
        repo_root=value_contract._repo_root(),
        companion=bypassed,
        diagnostic_verification=None,
    )

    assert result.governing_issues == _legacy_n8_governing_issues()
    assert result.content_ref is None
    assert any(
        finding.get("code") == "dependency_discriminant_diagnostic_not_received"
        for finding in result.ambient_findings
    )


def test_n8_source_flip_rejects_stale_freeze_before_cases_or_output(
    monkeypatch: Any, tmp_path: Path
) -> None:
    repo_root = value_contract._repo_root()

    def unexpected_cases() -> tuple[object, ...]:
        pytest.fail("source-flip cases were enumerated before the freeze was admitted")

    monkeypatch.setattr(value_contract, "_source_flip_cases", unexpected_cases)
    with pytest.raises(ValueError, match="dependency discriminant source freeze mismatch"):
        value_contract.run_source_flip_mutations(
            repo_root,
            expected_source_freeze="0" * 40,
            output_root=tmp_path,
        )
    assert list(tmp_path.iterdir()) == []


def test_source_flip_retention_is_exact_immutable_and_under_local_raw(tmp_path: Path) -> None:
    repo_root = tmp_path
    raw_root = repo_root / "docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw"
    run_root = raw_root / "source-flip-test-run"
    run_root.mkdir(parents=True)
    stdout = b"complete stdout\nwith trailing evidence\n"
    stderr = b"complete stderr\n"

    retained = value_contract._retain_source_flip_outputs(
        repo_root,
        run_root,
        probe_id="mutation-one",
        command=(sys.executable, "-c", "print('probe')"),
        exit_code=1,
        stdout=stdout,
        stderr=stderr,
    )

    assert (repo_root / retained["stdout"]["path"]).read_bytes() == stdout
    assert retained["stdout"]["sha256"] == hashlib.sha256(stdout).hexdigest()
    assert retained["stdout"]["bytes"] == len(stdout)
    assert (repo_root / retained["stderr"]["path"]).read_bytes() == stderr
    assert retained["stderr"]["sha256"] == hashlib.sha256(stderr).hexdigest()
    assert json.loads((repo_root / retained["probe_receipt"]["path"]).read_text()) == {
        "command": [sys.executable, "-c", "print('probe')"],
        "exit_code": 1,
        "probe_id": "mutation-one",
        "capture_complete": True,
        "timeout_seconds": None,
        "streams": {key: retained[key] for key in ("stdout", "stderr")},
    }
    with pytest.raises(FileExistsError):
        value_contract._retain_source_flip_outputs(
            repo_root,
            run_root,
            probe_id="mutation-one",
            command=(sys.executable, "-c", "print('changed')"),
            exit_code=1,
            stdout=b"changed\n",
            stderr=stderr,
        )
    assert (repo_root / retained["stdout"]["path"]).read_bytes() == stdout


def test_source_flip_output_root_rejects_paths_outside_local_raw(
    monkeypatch: Any, tmp_path: Path
) -> None:
    monkeypatch.delenv(value_contract._SOURCE_FLIP_OUTPUT_ROOT_ENV, raising=False)
    with pytest.raises(ValueError, match="must remain under canonical LOCAL/raw"):
        value_contract._source_flip_output_base(tmp_path.resolve(), tmp_path.resolve() / "outside")


def test_n8_source_projection_runs_real_method_and_fresh_candidate_bounds(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Canonical active admissions reach the real method, CAS, and fresh reader."""
    from copy import deepcopy
    from dataclasses import replace

    from polisyos.core.artifacts import artifact_ref_for_manifest, ensure_ir_artifact_store
    from polisyos.data_forge.domains.catalog.knowledge.overlay import (
        ActivatedAcquisitionObservationProjection,
    )
    from polisyos.foundry.methods.catalog.causal.treatment_effects import (
        AIPWEstimator,
        TMLEEstimator,
    )
    from polisyos.foundry.methods.causal import BoundsEngineMethod
    from polisyos.ir.analytics.causal import load_causal_effect_report
    from polisyos.ir.analytics.partial_identification import (
        BoundMethod,
        BoundsBundle,
        BoundSoundnessLevel,
    )
    from polisyos.ir.registry.refs import CausalEffectReportRef
    from polisyos.runtime.quality import (
        ValueOwnerSourceProjectionRequestV1,
        ValueOwnerSourceVariableProjectionV1,
    )
    from polisyos.runtime.quality import generation_cycle as gc
    from polisyos.runtime.quality.substrate_registry import (
        catalog_serving_source_scope,
        default_substrate_catalog_paths,
    )
    from tests._helpers.semantic_epoch_native import make_native_multivariable_active_projections

    method_fqn = AIPWEstimator.signature.fqn
    problem, world = _avg_income_problem(), _world_record()
    candidate = replace(
        _avg_income_typed_atom_candidate(problem),
        diversity_key=("grant", "country", "avg_income", "selected_owner_rows"),
    )
    source_rows: list[dict[str, object]] = []
    for index in range(200):
        treatment = float(index % 2)
        covariate = float((index // 2) % 2)
        outcome = float((index * 11) % 17 < (6 + int(treatment) + int(covariate)))
        source_rows.append(
            {
                "country_code": "UA",
                "year": 1800 + index,
                "avg_income": outcome,
                "agents.income": treatment,
                "income_covariate": covariate,
                "condition_json": '{"unit":"binary"}',
            }
        )
    source_fixture = make_native_multivariable_active_projections(
        tmp_path / "native-owner-source",
        source_rows=source_rows,
        variable_specs=(
            {
                "target_variable": "avg_income",
                "raw_field": "avg_income",
                "raw_unit": "binary",
                "canonical_unit": "binary",
            },
            {
                "target_variable": "agents.income",
                "raw_field": "agents.income",
                "raw_unit": "binary",
                "canonical_unit": "binary",
            },
            {
                "target_variable": "income_covariate",
                "raw_field": "income_covariate",
                "raw_unit": "binary",
                "canonical_unit": "binary",
            },
        ),
    )
    projections = source_fixture.projections
    estimand_spec = json.dumps(
        {
            "query_id": "n8-source-projection-controlled",
            "estimand_id": "ATE",
            "outcome": "avg_income",
            "treatment_or_exposure": "agents.income",
            "covariates_or_conditioning": ["income_covariate"],
            "adjustment_set": ["income_covariate"],
            "population": "unspecified",
            "sample_filter": None,
            "time_horizon": None,
            "prediction_origin": None,
            "unit": "binary",
            "scale": "identity",
            "transform": None,
            "target_role": "estimate",
            "loss_or_utility_id": None,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    role_bindings: tuple[tuple[Literal["outcome", "treatment", "covariate"], str], ...] = (
        ("outcome", "avg_income"),
        ("treatment", "agents.income"),
        ("covariate", "income_covariate"),
    )
    request = ValueOwnerSourceProjectionRequestV1(
        selected_method_fqn=method_fqn,
        estimand_spec_json=estimand_spec,
        variable_projections=tuple(
            ValueOwnerSourceVariableProjectionV1(
                role=role,
                variable_id=variable_id,
                projection_payload=projections[variable_id].model_dump(mode="json"),
            )
            for role, variable_id in role_bindings
        ),
        outcome_lower=0.0,
        outcome_upper=1.0,
        outcome_bounds_unit="binary",
        method_parameters_json="{}",
        seed=7,
    )
    core_store = source_fixture.artifact_store
    ir_store = ensure_ir_artifact_store(core_store)
    substrate_paths = replace(
        default_substrate_catalog_paths(source_fixture.repo_root),
        l1_dcat_path=source_fixture.baseline_path,
    )
    catalog_source = admit_fixture_catalog_source(
        repo_root=source_fixture.repo_root, database_path=source_fixture.baseline_path
    )
    gateway = RealValueOwnerGateway(
        repo_root=source_fixture.repo_root,
        catalog_overlay_path=source_fixture.overlay_path,
        catalog_serving_source=catalog_source,
        artifact_store=core_store,
        activated_observation_projection=projections["avg_income"],
        source_projection_request=request,
    )
    basis_refs: list[Any] = []
    original_producer = gc._produce_value_owner_method_run_basis

    def capture_producer(**kwargs: Any) -> Any:
        ref = original_producer(**kwargs)
        basis_refs.append(ref)
        return ref

    outer_sets: list[ValueOuterSet] = []
    consumer_arguments: list[dict[str, Any]] = []
    original_consumer = gc._value_outer_set_from_owner_method_run_basis

    def capture_consumer(**kwargs: Any) -> ValueOuterSet:
        consumer_arguments.append(dict(kwargs))
        result = original_consumer(**kwargs)
        outer_sets.append(result)
        return result

    monkeypatch.setattr(gc, "_produce_value_owner_method_run_basis", capture_producer)
    monkeypatch.setattr(gc, "_value_outer_set_from_owner_method_run_basis", capture_consumer)
    simulation = _simulation(world, candidate_id=candidate.candidate_id)

    def run(
        selected_gateway: RealValueOwnerGateway,
        *,
        candidate_override: Any | None = None,
        selected_method_fqn: str | None = None,
    ) -> ValuePortObservation:
        selected_candidate = candidate if candidate_override is None else candidate_override
        with catalog_serving_source_scope(catalog_source):
            return FoundryValuePort(
                evaluation_context=_simulation_execution_context(
                    candidate=selected_candidate, simulation=simulation, problem=problem
                ),
                owner_gateway=selected_gateway,
                requested_method_fqn=selected_method_fqn or method_fqn,
                artifact_store=core_store,
            )(
                candidate=selected_candidate,
                simulation=simulation,
                problem=problem,
                cycle_index=0,
            )

    observation = run(gateway)
    assert observation.status == "value_blocked"
    from polisyos.ir.analytics.interventions import NodeIntervention, VariableAssignment

    changed_action = NodeIntervention(
        assignments=(
            VariableAssignment(variable="government.balance", value_expr="balance + subsidy"),
        )
    )
    producer_forgery = _rehash_typed_atom_candidate(
        candidate,
        causal_do_expr=candidate.atom.causal_do_expr.model_copy(
            update={"expression_payload": changed_action.model_dump(mode="json")}
        ),
    )
    producer_counts = (len(basis_refs), len(outer_sets))
    producer_refusal = run(gateway, candidate_override=producer_forgery)
    assert producer_refusal.status == "value_blocked"
    assert "value_owner_source_atom_expression_projection_mismatch" in str(producer_refusal.reason)
    assert (len(basis_refs), len(outer_sets)) == producer_counts
    assert observation.authority_blockers == ("candidate_fixture_value_run_not_authority",), (
        observation.reason
    )
    assert observation.value_ref is not None and observation.selected_method_fqn == method_fqn
    assert len(basis_refs) == len(outer_sets) == 1
    basis = gc.ValueOwnerMethodRunBasisV2.model_validate(
        gc._value_load_ref_payload(ir_store, basis_refs[0])
    )
    assignment = gc.ValueOwnerSourceVariableAssignmentV1.model_validate(
        gc._value_load_ref_payload(ir_store, basis.assignment_ref)
    )
    report = load_causal_effect_report(
        ir_store, CausalEffectReportRef.model_validate(basis.report_ref.model_dump(mode="python"))
    )
    bounds_ref = gc._value_artifact_ref(
        report.metadata["identification_bounds_ref"], expected_kind="ir.bounds_bundle"
    )
    bounds = BoundsBundle.model_validate(gc._value_load_ref_payload(ir_store, bounds_ref))
    manski = next(item for item in bounds.method_summaries if item.method is BoundMethod.MANSKI)
    outer_set = outer_sets[0]
    stored_intent = gc.ValueOwnerMethodRunIntentV1.model_validate(
        gc._value_load_ref_payload(ir_store, basis.intent_ref)
    )
    stored_runner_request = gc.ValueOwnerMethodRunnerRequestV1.model_validate(
        gc._value_load_ref_payload(ir_store, basis.runner_request_ref)
    )
    projected_interval = report.to_value_uncertainty(
        estimand=gc._value_estimand_spec_from_json(stored_intent.estimand_spec_json),
        projection_binding=NativeValueEstimandBinding.model_validate(
            stored_runner_request.native_estimand_binding
        ),
    )
    assert projected_interval is not None and projected_interval.gate_eligible is False
    assert basis.selected_method_fqn == method_fqn
    assert (
        assignment.assignment_provenance == "consumer_asserted"
        and assignment.source_time_status == "not_established"
    )
    assert assignment.candidate_content_hash == candidate.atom.content_hash
    assert assignment.outcome_bounds_unit == assignment.measurement_unit == "binary"
    assert len(assignment.role_profiles) == 3
    for role_profile in assignment.role_profiles:
        assert (
            role_profile.profile_ref.manifest_profile_sha256 is not None
            and role_profile.projection_ref.manifest_profile_sha256 is not None
        )
        assert gc._value_load_ref_payload(ir_store, role_profile.projection_ref) == projections[
            role_profile.variable_id
        ].model_dump(mode="json")
    assert (
        report.status.value == "success"
        and report.estimand == "ATE"
        and report.confidence_interval is not None
    )
    assert report.metadata["gate_eligible"] is False
    assert bounds.estimand_type == "ate" and manski.lower_bound < manski.upper_bound
    assert bounds.sharpness_status == "outer_approx"
    assert bounds.dual_certificate_ref is None
    assert all(
        summary.soundness_level is BoundSoundnessLevel.ASSUMPTION_ONLY
        and summary.assumptions_used == ["no_assumptions_on_selection"]
        and summary.certificate_ref is None
        for summary in bounds.method_summaries
    )
    assert report.metadata["identification_bounds_contract"] == "ir.bounds_bundle.v1"
    assert report.metadata["identification_bounds_status"] == "candidate_only"
    assert report.metadata["identification_bounds_ref"] == bounds_ref.model_dump(mode="json")
    assert gc._value_manifest_has_exact_inputs(
        ir_store,
        bounds_ref,
        (
            (basis.profile_ref, "selected_owner_profile"),
            (basis.assignment_ref, "owner_source_assignment"),
            (basis.panel_input_ref, "exact_method_input_bytes"),
            (basis.runner_request_ref, "selected_method_runner_request"),
        ),
    )
    assert gc._value_manifest_has_exact_inputs(
        ir_store,
        basis.report_ref,
        (
            (basis.panel_input_ref, "exact_method_input_bytes"),
            (basis.runner_request_ref, "selected_method_runner_request"),
            (bounds_ref, "candidate_identification_bounds"),
        ),
    )
    assert gc._value_manifest_has_exact_inputs(
        ir_store,
        basis_refs[0],
        (
            (basis.intent_ref, "immutable_run_intent"),
            (basis.profile_ref, "selected_owner_profile"),
            (basis.assignment_ref, "owner_assignment"),
            (basis.panel_input_ref, "exact_method_input_bytes"),
            (basis.runner_request_ref, "selected_method_runner_request"),
            (basis.report_ref, "native_method_report"),
            (basis.execution_receipt_ref, "method_execution_receipt"),
        ),
    )
    # The public observation exposes only the content ID. Resolve the actual CAS
    # manifest and materialize its typed view; this is a reader-selected view,
    # not a producer-attested profile copied from the observation.
    outer_manifest = ir_store.get_manifest(observation.value_ref)
    outer_ref = gc._value_artifact_ref(
        artifact_ref_for_manifest(outer_manifest),
        expected_kind="runtime.value_outer_set_candidate_fixture",
    )
    assert str(outer_ref.artifact_id) == observation.value_ref
    assert outer_ref.media_type == "application/json"
    assert outer_ref.manifest_profile_sha256 is not None
    assert outer_manifest.artifact_schema is not None
    assert outer_manifest.artifact_schema.name == "runtime.value_outer_set_candidate_fixture"
    assert outer_manifest.artifact_schema.version == "1.0"
    outer_manifest = ir_store.get_manifest_by_profile(
        outer_ref.artifact_id, outer_ref.manifest_profile_sha256
    )
    assert artifact_ref_for_manifest(outer_manifest) == artifact_ref_for_manifest(
        ir_store.get_manifest(observation.value_ref)
    )
    # Reconcile the full selected-profile edge set through the shared helper;
    # Core's ArtifactID RootModel and the runtime ref's string are wire-equal.
    assert gc._value_manifest_has_exact_inputs(
        ir_store, outer_ref, ((basis_refs[0], "owner_method_run_basis"),)
    )

    # Prove the persisted outer artifact can be freshly loaded by its typed
    # consumer, including its serialized derived-width checksum.
    outer_payload = gc._value_load_ref_payload(ir_store, outer_ref)
    assert isinstance(outer_payload, dict)
    persisted_outer = ValueOuterSet.from_persisted_payload(outer_payload)
    assert persisted_outer == outer_set
    tampered_outer_payload = deepcopy(outer_payload)
    persisted_width = tampered_outer_payload.get("width")
    assert isinstance(persisted_width, list) and persisted_width
    persisted_width[0] = float(persisted_width[0]) + 0.01
    with pytest.raises(ValueError, match="value_outer_set_width_tampered"):
        ValueOuterSet.from_persisted_payload(tampered_outer_payload)
    assert outer_set.identification_status == "partial"
    assert outer_set.lower == (manski.lower_bound,) and outer_set.upper == (manski.upper_bound,)
    assert outer_set.statistical_lower == (
        projected_interval.numeric_policy.canonicalize(report.confidence_interval[0]),
    ) and outer_set.statistical_upper == (
        projected_interval.numeric_policy.canonicalize(report.confidence_interval[1]),
    )
    assert (
        outer_set.assumption_status == "declared"
        and outer_set.representation_status == "search_only"
    )
    assert "consumer_asserted_treatment_role" in outer_set.assumptions
    assert "no_assumptions_on_selection" in outer_set.assumptions
    assert "bounds_estimand_relation_not_established" in outer_set.assumptions

    # Preserve the current engine tier; unknown, certified, or heuristic tiers
    # cannot stand in for the assumption-only candidate route.
    for unsafe_level in (None, "CERTIFIED", "HEURISTIC"):
        unsafe_bundle = deepcopy(bounds.model_dump(mode="json"))
        manski_payload = next(
            row
            for row in unsafe_bundle["method_summaries"]
            if row["method"] == BoundMethod.MANSKI.value
        )
        manski_payload["soundness_level"] = unsafe_level

        def return_unsafe_bundle(
            *args: Any, _bundle: dict[str, object] = unsafe_bundle, **kwargs: Any
        ) -> dict[str, object]:
            return {"bounds_report": _bundle}

        with monkeypatch.context() as tier_control:
            tier_control.setattr(
                BoundsEngineMethod, "pure_step", staticmethod(return_unsafe_bundle)
            )
            with pytest.raises(
                ValueError, match="value_owner_source_bounds_soundness_not_established"
            ):
                gc._value_source_bounds_bundle({"outcome": (), "treatment": ()}, assignment)

    consumer_kwargs = consumer_arguments[0]
    original_payload_loader = gc._value_load_ref_payload

    def replay_candidate_consumer() -> ValueOuterSet:
        with catalog_serving_source_scope(catalog_source):
            return original_consumer(**consumer_kwargs)

    foreign_problem = problem.model_copy(update={"design_problem_id": "foreign_b31_problem"})
    wrong_join_candidates = (
        (
            _avg_income_typed_atom_candidate(foreign_problem),
            "value_owner_source_atom_subject_mismatch",
        ),
        (
            _avg_income_typed_atom_candidate(problem, treatment_variable="government.balance"),
            "value_owner_source_atom_treatment_mismatch",
        ),
        (
            producer_forgery,
            "value_owner_source_atom_expression_projection_mismatch",
        ),
        (
            _avg_income_typed_atom_candidate(problem, unit_id="synthetic_score"),
            "value_owner_source_atom_unit_mismatch",
        ),
        (
            replace(
                candidate,
                atom=candidate.atom.model_copy(update={"content_hash": _hash("f")}),
            ),
            "value_owner_source_atom_hash_mismatch",
        ),
    )
    for wrong_candidate, refusal_code in wrong_join_candidates:
        with (
            catalog_serving_source_scope(catalog_source),
            pytest.raises(ValueError, match=refusal_code),
        ):
            original_consumer(**{**consumer_kwargs, "candidate": wrong_candidate})

    # Missing the report-to-bounds reference is refused even with other markers present.
    with monkeypatch.context() as missing_basis_control:

        def omit_bounds_ref(
            selected_store: object, selected_ref: gc.ValueArtifactBindingRefV1
        ) -> object:
            payload = original_payload_loader(selected_store, selected_ref)
            if getattr(selected_ref, "artifact_id", None) == basis.report_ref.artifact_id:
                assert isinstance(payload, dict)
                payload = deepcopy(payload)
                metadata = payload.get("metadata")
                assert isinstance(metadata, dict)
                metadata.pop("identification_bounds_ref")
            return payload

        missing_basis_control.setattr(gc, "_value_load_ref_payload", omit_bounds_ref)
        with pytest.raises(KeyError, match="identification_bounds_ref"):
            replay_candidate_consumer()

    # Recomputed content must still match when markers and ref shape are present.
    def corrupt_tier(payload: dict[str, Any]) -> dict[str, Any]:
        summaries = payload["method_summaries"]
        manski_row = next(row for row in summaries if row["method"] == "manski_bounds")
        manski_row["soundness_level"] = "HEURISTIC"
        return payload

    def corrupt_assumptions(payload: dict[str, Any]) -> dict[str, Any]:
        summaries = payload["method_summaries"]
        manski_row = next(row for row in summaries if row["method"] == "manski_bounds")
        manski_row["assumptions_used"] = ["forged_present_assumption"]
        return payload

    def corrupt_bounds_content(payload: dict[str, Any]) -> dict[str, Any]:
        for key in ("lower_bound", "upper_bound", "consensus_lower", "consensus_upper"):
            value = payload[key]
            if value is not None:
                payload[key] = float(value) + 0.01
        summaries = payload["method_summaries"]
        assert isinstance(summaries, list)
        for row in summaries:
            row["lower_bound"] = float(row["lower_bound"]) + 0.01
            row["upper_bound"] = float(row["upper_bound"]) + 0.01
        return payload

    for corrupt in (corrupt_tier, corrupt_assumptions, corrupt_bounds_content):
        with monkeypatch.context() as corrupt_bundle_control:

            def load_corrupt_bounds(
                selected_store: object,
                selected_ref: gc.ValueArtifactBindingRefV1,
                *,
                _corrupt=corrupt,
            ) -> object:
                payload = original_payload_loader(selected_store, selected_ref)
                if (
                    getattr(selected_ref, "artifact_id", None) == bounds_ref.artifact_id
                    and getattr(selected_ref, "manifest_profile_sha256", None)
                    == bounds_ref.manifest_profile_sha256
                ):
                    return _corrupt(deepcopy(payload))
                return payload

            corrupt_bundle_control.setattr(gc, "_value_load_ref_payload", load_corrupt_bounds)
            with pytest.raises(
                ValueError, match="value_owner_source_bounds_recomputation_mismatch"
            ):
                replay_candidate_consumer()

    # A store view missing one selected-profile edge is refused with the ref and
    # candidate markers intact; the actual consumer resolver remains in use.
    original_manifest_lookup = core_store.get_manifest_by_profile
    with monkeypatch.context() as missing_edge_control:

        def omit_bounds_input_edge(artifact_id: Any, profile_sha256: str) -> Any:
            manifest = original_manifest_lookup(artifact_id, profile_sha256)
            if (
                str(artifact_id) == bounds_ref.artifact_id
                and profile_sha256 == bounds_ref.manifest_profile_sha256
            ):
                return manifest.model_copy(
                    update={
                        "inputs": tuple(
                            edge
                            for edge in manifest.inputs
                            if edge.role != "selected_method_runner_request"
                        )
                    }
                )
            return manifest

        missing_edge_control.setattr(core_store, "get_manifest_by_profile", omit_bounds_input_edge)
        with pytest.raises(ValueError, match="value_owner_source_bounds_lineage_mismatch"):
            replay_candidate_consumer()

    panel_candidate = replace(
        candidate,
        diversity_key=("grant", "country", "avg_income", "real_panel"),
    )
    panel_basis_count, panel_outer_count = len(basis_refs), len(outer_sets)
    panel_observation = run(gateway, candidate_override=panel_candidate)
    assert panel_observation.status == "value_blocked"
    assert panel_observation.authority_blockers == (
        "value_method_required_data_modality_unavailable",
    )
    assert panel_observation.value_ref is None
    assert len(basis_refs) == panel_basis_count
    assert len(outer_sets) == panel_outer_count

    genuine = projections["agents.income"]
    forged = ActivatedAcquisitionObservationProjection.issue(
        receipt_ref=genuine.receipt_ref,
        receipt_content_sha256=genuine.receipt_content_sha256,
        passport_ref=genuine.passport_ref,
        passport_content_sha256=genuine.passport_content_sha256,
        variable_id=genuine.variable_id,
        epoch_id=genuine.epoch_id,
        passport_id=genuine.passport_id,
        admission_content_sha256=_hash("e"),
        observations=tuple(row.observation for row in genuine.observations),
    )
    forged_request = request.model_copy(
        update={
            "variable_projections": tuple(
                item.model_copy(update={"projection_payload": forged.model_dump(mode="json")})
                if item.variable_id == "agents.income"
                else item
                for item in request.variable_projections
            )
        }
    )
    basis_count = len(basis_refs)
    forged_observation = run(replace(gateway, source_projection_request=forged_request))
    assert forged_observation.status == "value_blocked" and forged_observation.value_ref is None
    assert "value_owner_source_projection_canonical_owner_mismatch" in str(
        forged_observation.reason
    )
    assert len(basis_refs) == basis_count

    null_observation = run(replace(gateway, source_projection_request=None))
    assert null_observation.status == "value_blocked"
    assert "value_owner_method_run_intent_unresolved" in null_observation.authority_blockers
    assert "value_owner_source_request_explicit_null" in str(null_observation.reason)
    assert null_observation.value_ref is None

    expected_refusal_code = "acquire_data:value_owner_measurement_unit_malformed_json"
    failure_state: dict[str, Any] = {}
    original_loader = gc._load_value_data_profile_from_l1_dcat

    def fail_selected_treatment_load(**kwargs: Any) -> Any:
        if kwargs.get("outcome") == "agents.income":
            treatment_calls = int(failure_state.get("treatment_calls", 0)) + 1
            failure_state["treatment_calls"] = treatment_calls
            if treatment_calls == failure_state.get("fail_on_call"):
                failure = failure_state["error"]
                assert isinstance(failure, Exception)
                raise failure
        return original_loader(**kwargs)

    monkeypatch.setattr(gc, "_load_value_data_profile_from_l1_dcat", fail_selected_treatment_load)

    def run_with_treatment_failure(fail_on_call: int, failure: Exception) -> ValuePortObservation:
        failure_state.update(
            fail_on_call=fail_on_call,
            error=failure,
            treatment_calls=0,
        )
        return run(gateway)

    def typed_unit_refusal() -> gc.ValueOwnerAccessError:
        return gc.ValueOwnerAccessError(
            expected_refusal_code,
            (
                "owner condition_json is malformed. Next input: supply valid JSON object "
                "text with a declared unit; N8 will not infer or assign one."
            ),
            owner_access_ref=f"{source_fixture.baseline_path}#measurement-unit-binding",
        )

    baseline_basis_count = len(basis_refs)
    baseline_outer_count = len(outer_sets)

    intent_refusal = run_with_treatment_failure(1, typed_unit_refusal())
    assert intent_refusal.status == "value_blocked"
    assert intent_refusal.authority_blockers == (expected_refusal_code,)
    assert intent_refusal.value_ref is None
    assert intent_refusal.acquisition_requirement is None
    assert intent_refusal.method_selection_receipt is not None
    assert str(source_fixture.baseline_path) in str(intent_refusal.reason)
    assert "#measurement-unit-binding" in str(intent_refusal.reason)
    assert "Next input:" in str(intent_refusal.reason)
    assert len(basis_refs) == baseline_basis_count
    assert len(outer_sets) == baseline_outer_count

    intent_code_text = run_with_treatment_failure(1, ValueError(expected_refusal_code))
    assert intent_code_text.status == "value_blocked"
    assert intent_code_text.authority_blockers == ("value_owner_method_run_intent_unresolved",)
    assert intent_code_text.value_ref is None
    assert len(basis_refs) == baseline_basis_count
    assert len(outer_sets) == baseline_outer_count

    fresh_reload_refusal = run_with_treatment_failure(2, typed_unit_refusal())
    assert fresh_reload_refusal.status == "value_blocked"
    assert fresh_reload_refusal.authority_blockers == (expected_refusal_code,)
    assert fresh_reload_refusal.value_ref is None
    assert fresh_reload_refusal.acquisition_requirement is None
    assert fresh_reload_refusal.method_selection_receipt is not None
    assert str(source_fixture.baseline_path) in str(fresh_reload_refusal.reason)
    assert "#measurement-unit-binding" in str(fresh_reload_refusal.reason)
    assert "Next input:" in str(fresh_reload_refusal.reason)
    assert len(basis_refs) == baseline_basis_count + 1
    assert len(outer_sets) == baseline_outer_count

    fresh_reload_code_text = run_with_treatment_failure(2, ValueError(expected_refusal_code))
    assert fresh_reload_code_text.status == "value_blocked"
    assert fresh_reload_code_text.authority_blockers == ("value_owner_method_run_basis_invalid",)
    assert fresh_reload_code_text.value_ref is None
    assert len(basis_refs) == baseline_basis_count + 2
    assert len(outer_sets) == baseline_outer_count

    # A second native method changes provenance only. The same atom and typed
    # estimand remain one coordinate in both persisted bases and fresh outputs.
    second_method_fqn = TMLEEstimator.signature.fqn
    second_request = request.model_copy(update={"selected_method_fqn": second_method_fqn})
    second_observation = run(
        replace(gateway, source_projection_request=second_request),
        selected_method_fqn=second_method_fqn,
    )
    assert second_observation.status == "value_blocked"
    assert second_observation.authority_blockers == ("candidate_fixture_value_run_not_authority",)
    assert second_observation.selected_method_fqn == second_method_fqn
    second_basis = gc.ValueOwnerMethodRunBasisV2.model_validate(
        gc._value_load_ref_payload(ir_store, basis_refs[-1])
    )
    second_assignment = gc.ValueOwnerSourceVariableAssignmentV1.model_validate(
        gc._value_load_ref_payload(ir_store, second_basis.assignment_ref)
    )
    assert basis.selected_method_fqn == AIPWEstimator.signature.fqn
    assert second_basis.selected_method_fqn == second_method_fqn
    assert second_assignment.candidate_content_hash == assignment.candidate_content_hash
    assert second_assignment.candidate_content_hash == candidate.atom.content_hash
    assert second_basis.estimand_coordinate == basis.estimand_coordinate
    assert outer_sets[-1].coordinates == outer_sets[0].coordinates


def test_n8_source_profile_selects_exact_active_projection_before_row_cap(
    tmp_path: Path,
) -> None:
    """Read the exact selected member set and reject a malformed supplied projection."""
    from dataclasses import replace

    from polisyos.runtime.quality import generation_cycle as gc
    from polisyos.runtime.quality.substrate_registry import (
        catalog_serving_source_scope,
        default_substrate_catalog_paths,
    )
    from tests._helpers.semantic_epoch_native import make_native_multivariable_active_projections

    source_rows = [
        {
            "country_code": "UA",
            "year": 1800 + index,
            "avg_income": float((index * 11) % 17 < 7),
            "observed_treatment": float(index % 2),
            "income_covariate": float((index // 2) % 2),
            "condition_json": '{"unit":"binary"}',
        }
        for index in range(200)
    ]
    unprojected = (
        {
            "observation_id": "fixture-unprojected-avg-income-same-dataset-2400",
            "dataset_id": "acquisition.local.avg_income",
            "raw_variable": "avg_income",
            "canonical_var": "avg_income",
            "country_code": "UA",
            "year": 2400,
            "survey_year": None,
            "wave": None,
            "value": 1.0,
            "condition_json": '{"unit":"binary"}',
        },
        {
            "observation_id": "fixture-unprojected-avg-income-other-dataset-2401",
            "dataset_id": "aaa-unrelated-population",
            "raw_variable": "avg_income",
            "canonical_var": "avg_income",
            "country_code": "UA",
            "year": 2401,
            "survey_year": None,
            "wave": None,
            "value": 1.0,
            "condition_json": '{"unit":"binary"}',
        },
        {
            "observation_id": "fixture-unprojected-avg-income-foreign-scope-2402",
            "dataset_id": "acquisition.local.avg_income",
            "raw_variable": "avg_income",
            "canonical_var": "avg_income",
            "country_code": "US",
            "year": 2402,
            "survey_year": None,
            "wave": None,
            "value": 1.0,
            "condition_json": '{"unit":"binary"}',
        },
    )
    fixture = make_native_multivariable_active_projections(
        tmp_path / "native-owner-source-with-extra-baseline-row",
        source_rows=source_rows,
        variable_specs=(
            {
                "target_variable": "avg_income",
                "raw_field": "avg_income",
                "raw_unit": "binary",
                "canonical_unit": "binary",
            },
            {
                "target_variable": "observed_treatment",
                "raw_field": "observed_treatment",
                "raw_unit": "binary",
                "canonical_unit": "binary",
            },
            {
                "target_variable": "income_covariate",
                "raw_field": "income_covariate",
                "raw_unit": "binary",
                "canonical_unit": "binary",
            },
        ),
        unadmitted_baseline_observations=unprojected,
    )
    projection = fixture.projections["avg_income"]
    assert projection.activation_state == "active"
    assert projection.predicate_provenance == "recomputed"
    projected_ids = {row.observation.observation_id for row in projection.observations}
    assert all(row["observation_id"] not in projected_ids for row in unprojected)

    substrate_paths = replace(
        default_substrate_catalog_paths(fixture.repo_root),
        l1_dcat_path=fixture.baseline_path,
    )
    catalog_source = admit_fixture_catalog_source(
        repo_root=fixture.repo_root, database_path=fixture.baseline_path
    )
    with catalog_serving_source_scope(catalog_source):
        profile = gc._load_value_data_profile_from_l1_dcat(
            repo_root=fixture.repo_root,
            outcome="avg_income",
            owner_access_ref="fixture://n8-active-source-profile",
            overlay_path=fixture.overlay_path,
            scope_region="UA",
            artifact_store=fixture.artifact_store,
            activated_observation_projection=projection,
        )
    assert profile is not None
    assert profile.owner_row_count == len(projection.observations) == 200
    assert {row.period_id for row in profile.rows} == {1800 + index for index in range(200)}

    malformed_projection = projection.model_copy(
        update={"projection_content_sha256": "sha256:" + "0" * 64}
    )
    with (
        catalog_serving_source_scope(catalog_source),
        pytest.raises(gc.ValueOwnerAccessError) as refusal,
    ):
        gc._load_value_data_profile_from_l1_dcat(
            repo_root=fixture.repo_root,
            outcome="avg_income",
            owner_access_ref="fixture://n8-malformed-active-source-profile",
            overlay_path=fixture.overlay_path,
            scope_region="UA",
            artifact_store=fixture.artifact_store,
            activated_observation_projection=malformed_projection,
        )
    assert refusal.value.code == "acquire_data:active_observation_projection_invalid"


def test_n8_active_projection_rows_are_selected_before_large_owner_row_cap(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A large unrelated source population cannot starve a small active projection."""
    from dataclasses import replace
    from types import SimpleNamespace

    from polisyos.runtime.quality import data_state_substrate, substrate_registry
    from polisyos.runtime.quality.generation_cycle import RealValueOwnerGateway
    from polisyos.runtime.quality.substrate_registry import (
        catalog_serving_source_scope,
        default_substrate_catalog_paths,
    )
    from tests._helpers.semantic_epoch_native import make_native_multivariable_active_projections

    source_rows = [
        {
            "country_code": "UA",
            "year": year,
            "avg_income": value,
            "condition_json": {"unit": "ratio", "population": "selected"},
        }
        for year, value in ((2021, 0.42), (2022, 0.51), (2023, 0.47), (2024, 0.56))
    ]
    unrelated_rows = [
        {
            "observation_id": f"fixture-unadmitted-avg-income-{index:05d}",
            "dataset_id": "aaa-unrelated-population",
            "raw_variable": "avg_income",
            "canonical_var": "avg_income",
            "country_code": "UA",
            "year": 1900,
            "survey_year": None,
            "wave": None,
            "value": float(index),
            "condition_json": '{"unit":"ratio","population":"unrelated"}',
        }
        for index in range(20_001)
    ]
    fixture = make_native_multivariable_active_projections(
        tmp_path / "native-owner-source-with-crowded-unadmitted-baseline",
        source_rows=source_rows,
        variable_specs=(
            {
                "target_variable": "avg_income",
                "raw_field": "avg_income",
                "raw_unit": "ratio",
                "canonical_unit": "ratio",
            },
        ),
        unadmitted_baseline_observations=unrelated_rows,
    )
    projection = fixture.projections["avg_income"]
    selected_ids = {row.observation.observation_id for row in projection.observations}
    assert len(selected_ids) == 4
    local_paths = SimpleNamespace(l1_dcat_path=fixture.baseline_path)
    monkeypatch.setattr(
        data_state_substrate,
        "default_substrate_catalog_paths",
        lambda _root: local_paths,
    )
    monkeypatch.setattr(
        substrate_registry,
        "default_substrate_catalog_paths",
        lambda _root: local_paths,
    )

    substrate_paths = replace(
        default_substrate_catalog_paths(fixture.repo_root),
        l1_dcat_path=fixture.baseline_path,
    )
    catalog_source = admit_fixture_catalog_source(
        repo_root=fixture.repo_root, database_path=fixture.baseline_path
    )
    gateway = RealValueOwnerGateway(
        repo_root=fixture.repo_root,
        catalog_overlay_path=fixture.overlay_path,
        artifact_store=fixture.artifact_store,
        activated_observation_projection=projection,
    )
    candidate = SimpleNamespace(atom=SimpleNamespace(target_world_slots=("avg_income",)))
    problem = SimpleNamespace(
        outcome_of_interest=SimpleNamespace(target_variable="avg_income"),
        jurisdiction_time=SimpleNamespace(region="UA"),
    )
    with catalog_serving_source_scope(catalog_source):
        profile = gateway.load_value_data_profile(
            candidate=candidate,
            problem=problem,
            world_record=object(),
        )
    assert profile is not None
    assert profile.owner_row_count == len(selected_ids) == 4
    assert {row.period_id for row in profile.rows} == {2021, 2022, 2023, 2024}


def test_n8_source_projection_preserves_synthetic_asymmetric_ci_through_fresh_cas(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Keep ID and native CI channels paired across m/km source projections and fresh reads."""
    from polisyos.core.artifacts.store import FileSystemCAS
    from polisyos.ir.artifacts import put_json_artifact
    from polisyos.ir.model_layer.canon import CanonSpec as IRCanonSpec
    from polisyos.runtime.quality import generation_cycle as gc

    shared_artifact_store = FileSystemCAS(tmp_path / "paired-source-cas")
    runs: dict[str, dict[str, Any]] = {}
    for measurement_unit, raw_unit, raw_value_scale, channel_scale in (
        ("m", "km", 0.001, 1.0),
        ("km", "m", 1.0, 0.001),
    ):
        with monkeypatch.context() as unit_patch:
            runs[measurement_unit] = _run_n8_source_projection_case(
                tmp_path / measurement_unit,
                unit_patch,
                measurement_unit=measurement_unit,
                raw_unit=raw_unit,
                raw_value_scale=raw_value_scale,
                channel_scale=channel_scale,
                shared_artifact_store=shared_artifact_store,
            )

    meters = runs["m"]
    kilometers = runs["km"]
    meter_outer = meters["outer"]
    kilometer_outer = kilometers["outer"]
    meter_endpoints = (
        meter_outer.lower[0],
        meter_outer.upper[0],
        meter_outer.statistical_lower[0],
        meter_outer.statistical_upper[0],
    )
    kilometer_endpoints = (
        kilometer_outer.lower[0],
        kilometer_outer.upper[0],
        kilometer_outer.statistical_lower[0],
        kilometer_outer.statistical_upper[0],
    )
    assert meter_endpoints == (4.0, 4.0, 1.0, 10.0)
    assert kilometer_endpoints == (0.004, 0.004, 0.001, 0.010)
    assert tuple(value * 1000 for value in kilometer_endpoints) == pytest.approx(
        meter_endpoints, rel=0, abs=1e-12
    )

    for unit_run, expected_unit in ((meters, "m"), (kilometers, "km")):
        assert unit_run["assignment"].measurement_unit == expected_unit
        assert unit_run["report"].metadata["measurement_unit"] == expected_unit
        assert unit_run["bounds"].metadata["measurement_unit"] == expected_unit
        assert unit_run["outer"].calibration_scope["measurement_unit"] == expected_unit
        assert unit_run["outer"].calibration_scope["authority_scope"] == "candidate_fixture_only"

    meter_spec = asdict(meters["coordinate_spec"])
    kilometer_spec = asdict(kilometers["coordinate_spec"])
    assert meter_spec["unit"] == "m"
    assert kilometer_spec["unit"] == "km"
    assert {**meter_spec, "unit": None} == {**kilometer_spec, "unit": None}
    assert meters["outer"].coordinates != kilometers["outer"].coordinates

    # Bind the real km report (including its ID-bounds ref) to a recomputed m basis.
    cross_bound_payload = meters["basis"].model_dump(mode="json")
    cross_bound_payload["report_ref"] = kilometers["basis"].report_ref.model_dump(mode="json")
    cross_bound_payload["report_sha256"] = kilometers["basis"].report_sha256
    cross_bound_payload["native_interval_content_hash"] = kilometers[
        "basis"
    ].native_interval_content_hash
    cross_bound_payload.pop("content_hash")
    cross_bound_payload["content_hash"] = gc.gy_content_hash(cross_bound_payload)
    cross_bound_basis = gc.ValueOwnerMethodRunBasisV2.model_validate(cross_bound_payload)
    cross_bound_ref_raw = put_json_artifact(
        meters["ir_store"],
        cross_bound_basis.model_dump(mode="json"),
        kind="runtime.value_owner_method_run_basis",
        schema_name="runtime.value_owner_method_run_basis.v2",
        schema_version="2.0",
        inputs=[
            gc._value_input_ref(cross_bound_basis.intent_ref, role="immutable_run_intent"),
            gc._value_input_ref(cross_bound_basis.profile_ref, role="selected_owner_profile"),
            gc._value_input_ref(cross_bound_basis.assignment_ref, role="owner_assignment"),
            gc._value_input_ref(cross_bound_basis.panel_input_ref, role="exact_method_input_bytes"),
            gc._value_input_ref(
                cross_bound_basis.runner_request_ref, role="selected_method_runner_request"
            ),
            gc._value_input_ref(cross_bound_basis.report_ref, role="native_method_report"),
            gc._value_input_ref(
                cross_bound_basis.execution_receipt_ref, role="method_execution_receipt"
            ),
        ],
        canon_spec=IRCanonSpec(forbid_floats=True),
        return_selected_profile=True,
    )
    cross_bound_ref = gc._value_artifact_ref(
        cross_bound_ref_raw, expected_kind="runtime.value_owner_method_run_basis"
    )
    with (
        meters["catalog_serving_source_scope"](meters["catalog_source"]),
        pytest.raises(ValueError, match="value_owner_method_report_method_mismatch"),
    ):
        meters["consumer"](**{**meters["consumer_kwargs"], "run_basis_ref": cross_bound_ref})


def _run_n8_source_projection_case(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    measurement_unit: str,
    raw_unit: str,
    raw_value_scale: float,
    channel_scale: float,
    shared_artifact_store: Any,
) -> dict[str, Any]:
    """Keep synthetic continuous-outcome CI and ID channels separate in candidate CAS.

    Role-specific source conditions bind the outcome to its m/km unit while keeping treatment
    and covariate binary. Report and bounds backends remain deterministic fixtures.
    This test exercises NumpyRunner, N8, CAS, and the fresh consumer; it establishes no
    causal estimate, source assignment, or owner authority.
    """
    from polisyos.core.artifacts import artifact_ref_for_manifest, ensure_ir_artifact_store
    from polisyos.foundry.methods.catalog.causal.treatment_effects import AIPWEstimator
    from polisyos.foundry.methods.causal import BoundsEngineMethod
    from polisyos.ir.analytics.causal import CausalMethod, load_causal_effect_report
    from polisyos.ir.analytics.partial_identification import (
        BoundMethod,
        BoundsBundle,
        BoundSoundnessLevel,
        PartialIdentificationResult,
        bounds_bundle_from_partial_identification_result,
    )
    from polisyos.ir.registry.refs import CausalEffectReportRef
    from polisyos.runtime.quality import (
        ValueOwnerSourceProjectionRequestV1,
        ValueOwnerSourceVariableProjectionV1,
    )
    from polisyos.runtime.quality import generation_cycle as gc
    from polisyos.runtime.quality.substrate_registry import (
        catalog_serving_source_scope,
        default_substrate_catalog_paths,
    )
    from tests._helpers.semantic_epoch_native import make_native_multivariable_active_projections

    problem, world = _avg_income_problem(), _world_record()
    candidate = replace(
        _avg_income_typed_atom_candidate(problem, unit_id=measurement_unit),
        diversity_key=("grant", "country", "avg_income", "synthetic_ci_channel"),
    )
    source_rows: list[dict[str, object]] = []
    for index in range(200):
        treatment = float(index % 2)
        covariate = float((index // 2) % 2)
        outcome = raw_value_scale * float(
            (index % 13) + 0.25 * int(treatment) + 0.5 * int(covariate)
        )
        source_rows.append(
            {
                "country_code": "UA",
                "year": 1800 + index,
                "avg_income": outcome,
                "agents.income": treatment,
                "income_covariate": covariate,
                "condition_json": '{"population":"synthetic_candidate","time_basis":"year"}',
            }
        )
    outcome_values = [float(row["avg_income"]) for row in source_rows]
    assert len(set(outcome_values)) > 2
    assert min(outcome_values) >= 0.0 and max(outcome_values) <= 13.0
    assert {float(row["agents.income"]) for row in source_rows} == {0.0, 1.0}
    assert sum(float(row["agents.income"]) == 1.0 for row in source_rows) == 100
    assert sum(float(row["agents.income"]) == 0.0 for row in source_rows) == 100
    assert {float(row["income_covariate"]) for row in source_rows} == {0.0, 1.0}
    source_fixture = make_native_multivariable_active_projections(
        tmp_path / "synthetic-owner-source",
        source_rows=source_rows,
        condition_units_by_raw_field={
            "avg_income": raw_unit,
            "agents.income": "binary",
            "income_covariate": "binary",
        },
        variable_specs=(
            {
                "target_variable": "avg_income",
                "raw_field": "avg_income",
                "raw_unit": raw_unit,
                "canonical_unit": measurement_unit,
                "unit_transform": "fixed_multiplicative",
                "unit_transform_ref": "fabric://units/fixed-multiplicative/v1",
                "valid_min": 0.0,
                "valid_max": 13.0,
            },
            {
                "target_variable": "agents.income",
                "raw_field": "agents.income",
                "raw_unit": "binary",
                "canonical_unit": "binary",
                "valid_min": 0.0,
                "valid_max": 1.0,
            },
            {
                "target_variable": "income_covariate",
                "raw_field": "income_covariate",
                "raw_unit": "binary",
                "canonical_unit": "binary",
                "valid_min": 0.0,
                "valid_max": 1.0,
            },
        ),
        artifact_store=shared_artifact_store,
    )
    projections = source_fixture.projections
    estimand_spec = json.dumps(
        {
            "query_id": "n8-synthetic-asymmetric-ci-channel",
            "estimand_id": "ATE",
            "outcome": "avg_income",
            "treatment_or_exposure": "agents.income",
            "covariates_or_conditioning": ["income_covariate"],
            "adjustment_set": ["income_covariate"],
            "population": "unspecified",
            "sample_filter": None,
            "time_horizon": None,
            "prediction_origin": None,
            "unit": measurement_unit,
            "scale": "identity",
            "transform": None,
            "target_role": "estimate",
            "loss_or_utility_id": None,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    role_bindings: tuple[tuple[Literal["outcome", "treatment", "covariate"], str], ...] = (
        ("outcome", "avg_income"),
        ("treatment", "agents.income"),
        ("covariate", "income_covariate"),
    )
    method_fqn = AIPWEstimator.signature.fqn
    request = ValueOwnerSourceProjectionRequestV1(
        selected_method_fqn=method_fqn,
        estimand_spec_json=estimand_spec,
        variable_projections=tuple(
            ValueOwnerSourceVariableProjectionV1(
                role=role,
                variable_id=variable_id,
                projection_payload=projections[variable_id].model_dump(mode="json"),
            )
            for role, variable_id in role_bindings
        ),
        outcome_lower=0.0,
        outcome_upper=13.0 * channel_scale,
        outcome_bounds_unit=measurement_unit,
        method_parameters_json="{}",
        seed=7,
    )
    core_store = source_fixture.artifact_store
    ir_store = ensure_ir_artifact_store(core_store)
    substrate_paths = replace(
        default_substrate_catalog_paths(source_fixture.repo_root),
        l1_dcat_path=source_fixture.baseline_path,
    )
    catalog_source = admit_fixture_catalog_source(
        repo_root=source_fixture.repo_root, database_path=source_fixture.baseline_path
    )
    gateway = RealValueOwnerGateway(
        repo_root=source_fixture.repo_root,
        catalog_overlay_path=source_fixture.overlay_path,
        catalog_serving_source=catalog_source,
        artifact_store=core_store,
        activated_observation_projection=projections["avg_income"],
        source_projection_request=request,
    )
    synthetic_report = CausalEffectReport(
        method=CausalMethod.AIPW,
        estimand="ATE",
        point_estimate=4.0 * channel_scale,
        standard_error=1.0 * channel_scale,
        confidence_interval=(1.0 * channel_scale, 10.0 * channel_scale),
        confidence_level=0.95,
        inference_method="asymptotic",
        sample_size=200,
        n_treated=100,
        n_control=100,
        pre_periods=0,
        post_periods=1,
        metadata={
            "synthetic_test_fixture": "asymmetric-channel-preservation-only",
            "authority_scope": "candidate_fixture_only",
            "gate_eligible": False,
            "measurement_unit": measurement_unit,
            "outcome_support": [0.0, 13.0 * channel_scale],
        },
    )
    synthetic_bounds = bounds_bundle_from_partial_identification_result(
        PartialIdentificationResult(
            method=BoundMethod.MANSKI,
            lower_bound=4.0 * channel_scale,
            upper_bound=4.0 * channel_scale,
            confidence=1.0,
            assumptions_used=["synthetic_zero_width_channel_fixture_only"],
            bounds_type="manski",
            soundness_level=BoundSoundnessLevel.ASSUMPTION_ONLY,
        ),
        estimand_type="ate",
        metadata={
            "synthetic_test_fixture": "zero-width-identification-channel-only",
            "measurement_unit": measurement_unit,
            "outcome_support": [0.0, 13.0 * channel_scale],
        },
    )
    assert synthetic_bounds.point_identified is True
    assert synthetic_bounds.lower_bound == synthetic_bounds.upper_bound == (4.0 * channel_scale)
    assert synthetic_report.confidence_interval == (
        1.0 * channel_scale,
        10.0 * channel_scale,
    )

    def synthetic_aipw(_state: object, _params: object) -> dict[str, object]:
        return {
            "result": {"synthetic_test_fixture": "no-statistical-estimator-run"},
            "report": synthetic_report,
        }

    def synthetic_bounds_engine(_state: object, _params: object) -> dict[str, object]:
        return {"bounds_report": synthetic_bounds.model_dump(mode="json")}

    monkeypatch.setattr(AIPWEstimator, "pure_step", staticmethod(synthetic_aipw))
    monkeypatch.setattr(BoundsEngineMethod, "pure_step", staticmethod(synthetic_bounds_engine))
    consumer_arguments: list[dict[str, Any]] = []
    outer_results: list[ValueOuterSet] = []
    original_consumer = gc._value_outer_set_from_owner_method_run_basis

    def capture_consumer(**kwargs: Any) -> ValueOuterSet:
        consumer_arguments.append(dict(kwargs))
        result = original_consumer(**kwargs)
        outer_results.append(result)
        return result

    monkeypatch.setattr(gc, "_value_outer_set_from_owner_method_run_basis", capture_consumer)
    simulation = _simulation(world, candidate_id=candidate.candidate_id)

    def run(selected_gateway: RealValueOwnerGateway) -> ValuePortObservation:
        with catalog_serving_source_scope(catalog_source):
            return FoundryValuePort(
                evaluation_context=_simulation_execution_context(
                    candidate=candidate, simulation=simulation, problem=problem
                ),
                owner_gateway=selected_gateway,
                requested_method_fqn=method_fqn,
                artifact_store=core_store,
            )(candidate=candidate, simulation=simulation, problem=problem, cycle_index=0)

    observation = run(gateway)
    assert observation.status == "value_blocked"
    assert observation.authority_blockers == ("candidate_fixture_value_run_not_authority",)
    assert observation.value_ref is not None
    assert observation.selected_method_fqn == method_fqn
    assert len(consumer_arguments) == len(outer_results) == 1
    consumer_kwargs = consumer_arguments[0]
    basis_ref = gc._value_artifact_ref(
        consumer_kwargs["run_basis_ref"], expected_kind="runtime.value_owner_method_run_basis"
    )
    basis = gc.ValueOwnerMethodRunBasisV2.model_validate(
        gc._value_load_ref_payload(ir_store, basis_ref)
    )
    assignment = gc.ValueOwnerSourceVariableAssignmentV1.model_validate(
        gc._value_load_ref_payload(ir_store, basis.assignment_ref)
    )
    intent = gc.ValueOwnerMethodRunIntentV1.model_validate(
        gc._value_load_ref_payload(ir_store, basis.intent_ref)
    )
    report = load_causal_effect_report(
        ir_store, CausalEffectReportRef.model_validate(basis.report_ref.model_dump(mode="python"))
    )
    bounds_ref = gc._value_artifact_ref(
        report.metadata["identification_bounds_ref"], expected_kind="ir.bounds_bundle"
    )
    stored_bounds = BoundsBundle.model_validate(gc._value_load_ref_payload(ir_store, bounds_ref))

    assert assignment.authority_scope == "candidate_fixture_only"
    assert assignment.production_value_eligible is False
    assert assignment.assignment_provenance == "consumer_asserted"
    assert assignment.source_time_status == "not_established"
    assert assignment.measurement_unit == measurement_unit
    assert assignment.outcome_lower == 0.0 and assignment.outcome_upper == 13.0 * channel_scale
    assert assignment.outcome_bounds_unit == measurement_unit
    assert {(item.role, item.measurement_unit) for item in assignment.role_profiles} == {
        ("outcome", measurement_unit),
        ("treatment", "binary"),
        ("covariate", "binary"),
    }
    assert report.estimand == "ATE" and report.point_estimate == 4.0 * channel_scale
    assert report.confidence_interval == (
        1.0 * channel_scale,
        10.0 * channel_scale,
    )
    assert (
        -(13.0 * channel_scale)
        <= report.confidence_interval[0]
        <= report.confidence_interval[1]
        <= 13.0 * channel_scale
    )
    assert report.metadata["synthetic_test_fixture"] == "asymmetric-channel-preservation-only"
    assert report.metadata["gate_eligible"] is False
    assert report.metadata["measurement_unit"] == measurement_unit
    assert report.metadata["outcome_support"] == [0.0, 13.0 * channel_scale]
    assert stored_bounds.metadata["synthetic_test_fixture"] == (
        "zero-width-identification-channel-only"
    )
    assert stored_bounds.metadata["measurement_unit"] == measurement_unit
    assert stored_bounds.metadata["outcome_support"] == [0.0, 13.0 * channel_scale]
    assert stored_bounds.point_identified is True
    assert stored_bounds.lower_bound == stored_bounds.upper_bound == 4.0 * channel_scale
    assert (
        -(13.0 * channel_scale)
        <= stored_bounds.lower_bound
        <= stored_bounds.upper_bound
        <= 13.0 * channel_scale
    )
    assert stored_bounds.method_summaries[0].soundness_level is BoundSoundnessLevel.ASSUMPTION_ONLY
    assert basis.native_interval_content_hash == gy_content_hash(
        (1.0 * channel_scale, 10.0 * channel_scale)
    )
    assert gc._value_manifest_has_exact_inputs(
        ir_store,
        bounds_ref,
        (
            (basis.profile_ref, "selected_owner_profile"),
            (basis.assignment_ref, "owner_source_assignment"),
            (basis.panel_input_ref, "exact_method_input_bytes"),
            (basis.runner_request_ref, "selected_method_runner_request"),
        ),
    )
    assert gc._value_manifest_has_exact_inputs(
        ir_store,
        basis.report_ref,
        (
            (basis.panel_input_ref, "exact_method_input_bytes"),
            (basis.runner_request_ref, "selected_method_runner_request"),
            (bounds_ref, "candidate_identification_bounds"),
        ),
    )
    assert gc._value_manifest_has_exact_inputs(
        ir_store,
        basis_ref,
        (
            (basis.intent_ref, "immutable_run_intent"),
            (basis.profile_ref, "selected_owner_profile"),
            (basis.assignment_ref, "owner_assignment"),
            (basis.panel_input_ref, "exact_method_input_bytes"),
            (basis.runner_request_ref, "selected_method_runner_request"),
            (basis.report_ref, "native_method_report"),
            (basis.execution_receipt_ref, "method_execution_receipt"),
        ),
    )

    coordinate = gc._value_estimand_coordinate(
        gc._typed_value_estimand_spec(intent.estimand_spec_json)
    )
    assert basis.estimand_coordinate == coordinate
    outer_manifest = ir_store.get_manifest(observation.value_ref)
    outer_ref = gc._value_artifact_ref(
        artifact_ref_for_manifest(outer_manifest),
        expected_kind="runtime.value_outer_set_candidate_fixture",
    )
    assert gc._value_manifest_has_exact_inputs(
        ir_store, outer_ref, ((basis_ref, "owner_method_run_basis"),)
    )
    persisted_outer = ValueOuterSet.from_persisted_payload(
        gc._value_load_ref_payload(ir_store, outer_ref)
    )
    with catalog_serving_source_scope(catalog_source):
        fresh_outer = original_consumer(**consumer_kwargs)

    assert persisted_outer == outer_results[0] == fresh_outer
    assert persisted_outer.coordinates == (coordinate,)
    assert persisted_outer.calibration_scope["measurement_unit"] == measurement_unit
    assert persisted_outer.calibration_scope["authority_scope"] == "candidate_fixture_only"
    assert persisted_outer.identification_status == "partial"
    assert persisted_outer.lower == persisted_outer.upper == (4.0 * channel_scale,)
    assert persisted_outer.statistical_lower == (1.0 * channel_scale,)
    assert persisted_outer.statistical_upper == (10.0 * channel_scale,)
    assert 4.0 * channel_scale - 1.0 * channel_scale != 10.0 * channel_scale - 4.0 * channel_scale

    # Property-removal control: a plausible symmetric replacement keeps the typed report,
    # success, point, and all lineage markers but must not replace persisted native [1, 10].
    symmetric_report = synthetic_report.model_copy(
        update={"confidence_interval": (1.0 * channel_scale, 7.0 * channel_scale)}
    )

    def symmetric_proxy(_state: object, _params: object) -> dict[str, object]:
        return {
            "result": {"synthetic_test_fixture": "symmetric-proxy-not-native"},
            "report": symmetric_report,
        }

    with monkeypatch.context() as fake_report_control:
        fake_report_control.setattr(AIPWEstimator, "pure_step", staticmethod(symmetric_proxy))
        with (
            catalog_serving_source_scope(catalog_source),
            pytest.raises(ValueError, match="value_owner_source_report_recomputation_mismatch"),
        ):
            original_consumer(**consumer_kwargs)

    mismatched_gateway = replace(
        gateway, source_projection_request=request.model_copy(update={"seed": 8})
    )
    mismatch_kwargs = {**consumer_kwargs, "source_gateway": mismatched_gateway}
    with (
        catalog_serving_source_scope(catalog_source),
        pytest.raises(ValueError, match="value_owner_source_fresh_context_mismatch"),
    ):
        original_consumer(**mismatch_kwargs)

    unresolved_gateway = replace(gateway, source_projection_request=None)
    unresolved_kwargs = {**consumer_kwargs, "source_gateway": unresolved_gateway}
    with (
        catalog_serving_source_scope(catalog_source),
        pytest.raises(ValueError, match="value_owner_source_fresh_request_missing"),
    ):
        original_consumer(**unresolved_kwargs)

    original_manifest_lookup = core_store.get_manifest_by_profile

    def remove_owner_assignment_edge(artifact_id: object, profile_sha256: str) -> Any:
        manifest = original_manifest_lookup(artifact_id, profile_sha256)
        if (
            str(artifact_id) == basis_ref.artifact_id
            and profile_sha256 == basis_ref.manifest_profile_sha256
        ):
            return manifest.model_copy(
                update={
                    "inputs": tuple(
                        edge for edge in manifest.inputs if edge.role != "owner_assignment"
                    )
                }
            )
        return manifest

    with monkeypatch.context() as removed_edge_control:
        removed_edge_control.setattr(
            core_store, "get_manifest_by_profile", remove_owner_assignment_edge
        )
        with (
            catalog_serving_source_scope(catalog_source),
            pytest.raises(ValueError, match="value_owner_method_run_basis_binding_mismatch"),
        ):
            original_consumer(**consumer_kwargs)

    # Missing identification/bounds ref remains a hard failure at the fresh consumer.
    original_payload_loader = gc._value_load_ref_payload

    def omit_bounds_ref(
        selected_store: object, selected_ref: gc.ValueArtifactBindingRefV1
    ) -> object:
        payload = original_payload_loader(selected_store, selected_ref)
        if getattr(selected_ref, "artifact_id", None) == basis.report_ref.artifact_id:
            assert isinstance(payload, dict)
            payload = copy.deepcopy(payload)
            metadata = payload.get("metadata")
            assert isinstance(metadata, dict)
            metadata.pop("identification_bounds_ref")
        return payload

    with monkeypatch.context() as missing_bounds_control:
        missing_bounds_control.setattr(gc, "_value_load_ref_payload", omit_bounds_ref)
        with (
            catalog_serving_source_scope(catalog_source),
            pytest.raises(KeyError, match="identification_bounds_ref"),
        ):
            original_consumer(**consumer_kwargs)

    return {
        "consumer": original_consumer,
        "consumer_kwargs": consumer_kwargs,
        "basis": basis,
        "basis_ref": basis_ref,
        "catalog_source": catalog_source,
        "catalog_serving_source_scope": catalog_serving_source_scope,
        "outer": persisted_outer,
        "coordinate_spec": gc._typed_value_estimand_spec(intent.estimand_spec_json),
        "intent": intent,
        "report": report,
        "bounds": stored_bounds,
        "assignment": assignment,
        "ir_store": ir_store,
    }


def test_n8_fresh_consumer_reads_recomputed_fixed_unit_owner_projection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Static unit conversion reaches the fresh N8 reader without changing assignment authority."""
    from dataclasses import replace

    from polisyos.runtime.quality import generation_cycle as gc
    from polisyos.runtime.quality.substrate_registry import (
        catalog_serving_source_scope,
        default_substrate_catalog_paths,
    )
    from tests._helpers.semantic_epoch_native import make_native_multivariable_active_projections

    source_rows = [
        {
            "country_code": "UA",
            "year": 2021 + index,
            "distance": 0.001 * (index + 1),
            "condition_json": '{"population":"synthetic-candidate"}',
        }
        for index in range(4)
    ]
    fixture = make_native_multivariable_active_projections(
        tmp_path / "fixed-unit-owner-source",
        source_rows=source_rows,
        condition_units_by_raw_field={"distance": "km"},
        variable_specs=(
            {
                "target_variable": "distance",
                "raw_field": "distance",
                "raw_unit": "km",
                "canonical_unit": "m",
                "unit_transform": "fixed_multiplicative",
                "unit_transform_ref": "fabric://units/fixed-multiplicative/v1",
                "valid_min": 0.0,
                "valid_max": 5.0,
            },
        ),
    )
    projection = fixture.projections["distance"]
    observations = tuple(row.observation for row in projection.observations)
    assert [row.value for row in observations] == [1.0, 2.0, 3.0, 4.0]
    assert all(json.loads(row.condition_json)["unit"] == "m" for row in observations)
    assert all(row.unit_transform_evidence is not None for row in observations)
    assert all(row.unit_transform_evidence.raw_unit == "km" for row in observations)
    assert all(row.unit_transform_evidence.canonical_unit == "m" for row in observations)
    assert all(row.unit_transform_evidence.multiplier == "1000" for row in observations)
    assert projection.source_time_status == "not_established"
    assert projection.predicate_provenance == "recomputed"

    substrate_paths = replace(
        default_substrate_catalog_paths(fixture.repo_root),
        l1_dcat_path=fixture.baseline_path,
    )
    catalog_source = admit_fixture_catalog_source(
        repo_root=fixture.repo_root, database_path=fixture.baseline_path
    )
    with catalog_serving_source_scope(catalog_source):
        profile = gc._load_value_data_profile_from_l1_dcat(
            repo_root=fixture.repo_root,
            outcome="distance",
            owner_access_ref="fixture://n8-fixed-unit-fresh-profile",
            overlay_path=fixture.overlay_path,
            scope_region="UA",
            artifact_store=fixture.artifact_store,
            activated_observation_projection=projection,
        )

    assert profile is not None
    assert profile.measurement_unit == "m"
    assert [row.outcome_value for row in profile.rows] == [1.0, 2.0, 3.0, 4.0]
    assert all(row.measurement_unit == "m" for row in profile.rows)
    assert profile.treatment_assignment_status == "owner_assignment_unresolved"

    import duckdb

    from polisyos.runtime.quality.acquisition_executor import AdmissionPassport

    with duckdb.connect(str(fixture.overlay_path), read_only=True) as con:
        columns = {
            str(row[1])
            for row in con.execute(
                "PRAGMA table_info('acquisition_observation_provenance')"
            ).fetchall()
        }
    assert "unit_transform_evidence_json" in columns

    with duckdb.connect(str(fixture.overlay_path), read_only=True) as con:
        passport_row = con.execute(
            "SELECT passport_json FROM acquisition_passports WHERE epoch_id = ? "
            "AND passport_id = ?",
            [projection.epoch_id, projection.passport_id],
        ).fetchone()
    assert passport_row is not None
    persisted_passport = AdmissionPassport.model_validate(json.loads(str(passport_row[0])))
    fresh_projection = fixture.overlay.read_activated_semantic_epoch_observations(
        receipt_ref=projection.receipt_ref,
        artifact_store=fixture.artifact_store,
        passport=persisted_passport,
        authority=fixture.authority,
    )
    assert fresh_projection.projection_content_sha256 == projection.projection_content_sha256

    with duckdb.connect(str(fixture.overlay_path), read_only=True) as con:
        stored = con.execute(
            "SELECT observation_id, unit_transform_evidence_json "
            "FROM acquisition_observation_provenance WHERE epoch_id = ? "
            "AND passport_id = ? ORDER BY observation_id",
            [projection.epoch_id, projection.passport_id],
        ).fetchall()
    assert len(stored) == len(observations)
    expected = {
        row.observation_id: row.unit_transform_evidence.model_dump(mode="json")
        for row in observations
    }
    for observation_id, evidence_json in stored:
        assert json.loads(str(evidence_json)) == expected[str(observation_id)]

    with duckdb.connect(str(fixture.overlay_path)) as con:
        first_id, first_json = stored[0]
        tampered = json.loads(str(first_json))
        tampered["multiplier"] = "1"
        con.execute(
            "UPDATE acquisition_observation_provenance "
            "SET unit_transform_evidence_json = ? WHERE observation_id = ?",
            [json.dumps(tampered), first_id],
        )

    from polisyos.data_forge.domains.catalog.knowledge import overlay as overlay_module

    with pytest.raises(
        overlay_module.OverlayAdmissionError,
        match="active_epoch_observation_content_mismatch",
    ):
        fixture.overlay.read_activated_semantic_epoch_observations(
            receipt_ref=projection.receipt_ref,
            artifact_store=fixture.artifact_store,
            passport=persisted_passport,
            authority=fixture.authority,
        )

    ref_drift = json.loads(str(first_json))
    ref_drift["definition_content_sha256"] = "sha256:" + "0" * 64
    with duckdb.connect(str(fixture.overlay_path)) as con:
        con.execute(
            "UPDATE acquisition_observation_provenance "
            "SET unit_transform_evidence_json = ? WHERE observation_id = ?",
            [json.dumps(ref_drift), first_id],
        )
    with pytest.raises(
        overlay_module.OverlayAdmissionError,
        match="active_epoch_observation_content_mismatch",
    ):
        fixture.overlay.read_activated_semantic_epoch_observations(
            receipt_ref=projection.receipt_ref,
            artifact_store=fixture.artifact_store,
            passport=persisted_passport,
            authority=fixture.authority,
        )
