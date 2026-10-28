"""Real source unit join through a real method and fresh candidate consumer."""

from __future__ import annotations

import json
from dataclasses import replace
from fractions import Fraction
from pathlib import Path
from typing import Any, Literal

import pytest

from polisyos.core.artifacts import artifact_ref_for_manifest, ensure_ir_artifact_store
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.contracts.value_outer_set import ValueOuterSet
from polisyos.foundry.methods.catalog.causal.treatment_effects import AIPWEstimator
from polisyos.ir.analytics.causal import load_causal_effect_report, persist_causal_effect_report
from polisyos.ir.analytics.partial_identification import BoundMethod, BoundsBundle
from polisyos.ir.analytics.uncertainty import NativeValueEstimandBinding
from polisyos.ir.registry.refs import CausalEffectReportRef
from polisyos.runtime.quality import (
    ValueOwnerSourceProjectionRequestV1,
    ValueOwnerSourceVariableProjectionV1,
)
from polisyos.runtime.quality import generation_cycle as gc
from polisyos.runtime.quality.substrate_registry import catalog_serving_source_scope
from tests._helpers.catalog_source_admission import admit_fixture_catalog_source
from tests._helpers.semantic_epoch_native import make_native_multivariable_active_projections
from tests.unit.runtime.quality.test_b31_owner_run_basis_v2 import _rebind_basis
from tests.unit.runtime.quality.test_value_gate import (
    _avg_income_problem,
    _avg_income_typed_atom_candidate,
    _simulation,
    _simulation_execution_context,
    _world_record,
)


def _reference_manski_meters() -> tuple[Fraction, Fraction]:
    """Calculate the two-arm worst-case ATE bounds from fixture rows, independently."""
    treatment_groups: dict[int, list[Fraction]] = {0: [], 1: []}
    for index in range(200):
        treatment = index % 2
        covariate = (index // 2) % 2
        outcome = Fraction(index % 13) + Fraction(treatment, 4) + Fraction(covariate, 2)
        treatment_groups[treatment].append(outcome)
    treated, controls = treatment_groups[1], treatment_groups[0]
    total = len(treated) + len(controls)
    p1 = Fraction(len(treated), total)
    p0 = Fraction(len(controls), total)
    mean1 = sum(treated, Fraction()) / len(treated)
    mean0 = sum(controls, Fraction()) / len(controls)
    lower = p1 * mean1 + p0 * 0 - (p0 * mean0 + p1 * 13)
    upper = p1 * mean1 + p0 * 13 - (p0 * mean0 + p1 * 0)
    return lower, upper


def _run_source_case(
    root: Path,
    patch: pytest.MonkeyPatch,
    shared_store: FileSystemCAS,
    *,
    measurement_unit: str,
    raw_unit: str,
    raw_scale: float,
    canonical_scale: float,
) -> dict[str, Any]:
    """Execute the real source/owner path on an isolated synthetic observation panel."""
    problem = _avg_income_problem()
    world = _world_record()
    candidate = replace(
        _avg_income_typed_atom_candidate(problem, unit_id=measurement_unit),
        diversity_key=("grant", "country", "avg_income", "real_source_unit_join"),
    )
    source_rows: list[dict[str, object]] = []
    for index in range(200):
        treatment = index % 2
        covariate = (index // 2) % 2
        outcome_m = float(index % 13) + 0.25 * treatment + 0.5 * covariate
        source_rows.append(
            {
                "country_code": "UA",
                "year": 1800 + index,
                "avg_income": outcome_m * raw_scale,
                "agents.income": float(treatment),
                "income_covariate": float(covariate),
                "condition_json": '{"population":"synthetic_candidate","time_basis":"year"}',
            }
        )
    source = make_native_multivariable_active_projections(
        root / "owner-source",
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
        artifact_store=shared_store,
    )
    projections = source.projections
    outcome_rows = [row.observation for row in projections["avg_income"].observations]
    assert len(outcome_rows) == 200
    assert {row.year for row in outcome_rows} == set(range(1800, 2000))
    for row in outcome_rows:
        assert row.year is not None
        index = row.year - 1800
        expected_m = Fraction(index % 13) + Fraction(index % 2, 4) + Fraction((index // 2) % 2, 2)
        assert row.value == pytest.approx(float(expected_m), rel=1e-12, abs=1e-12)
        conversion = row.unit_transform_evidence
        assert conversion is not None
        assert (conversion.raw_unit, conversion.canonical_unit, conversion.multiplier) == (
            "km",
            "m",
            "1000",
        )
    estimand_json = json.dumps(
        {
            "query_id": "b31-real-source-unit-join",
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
    bindings: tuple[tuple[Literal["outcome", "treatment", "covariate"], str], ...] = (
        ("outcome", "avg_income"),
        ("treatment", "agents.income"),
        ("covariate", "income_covariate"),
    )
    request = ValueOwnerSourceProjectionRequestV1(
        selected_method_fqn=AIPWEstimator.signature.fqn,
        estimand_spec_json=estimand_json,
        variable_projections=tuple(
            ValueOwnerSourceVariableProjectionV1(
                role=role,
                variable_id=variable_id,
                projection_payload=projections[variable_id].model_dump(mode="json"),
            )
            for role, variable_id in bindings
        ),
        outcome_lower=0.0,
        outcome_upper=13.0 * canonical_scale,
        outcome_bounds_unit=measurement_unit,
        method_parameters_json="{}",
        seed=7,
    )
    catalog_source = admit_fixture_catalog_source(
        repo_root=source.repo_root, database_path=source.baseline_path
    )
    gateway = gc.RealValueOwnerGateway(
        repo_root=source.repo_root,
        catalog_overlay_path=source.overlay_path,
        catalog_serving_source=catalog_source,
        artifact_store=shared_store,
        activated_observation_projection=projections["avg_income"],
        source_projection_request=request,
    )
    actual_consumer = gc._value_outer_set_from_owner_method_run_basis
    captured: list[tuple[dict[str, Any], ValueOuterSet]] = []

    def capture_consumer(**kwargs: Any) -> ValueOuterSet:
        result = actual_consumer(**kwargs)
        captured.append((dict(kwargs), result))
        return result

    # Observe the real consumer; do not replace either numerical producer or its report.
    patch.setattr(gc, "_value_outer_set_from_owner_method_run_basis", capture_consumer)
    simulation = _simulation(world, candidate_id=candidate.candidate_id)
    with catalog_serving_source_scope(catalog_source):
        observation = gc.FoundryValuePort(
            evaluation_context=_simulation_execution_context(
                candidate=candidate, simulation=simulation, problem=problem
            ),
            owner_gateway=gateway,
            requested_method_fqn=AIPWEstimator.signature.fqn,
            artifact_store=shared_store,
        )(candidate=candidate, simulation=simulation, problem=problem, cycle_index=0)
    assert observation.status == "value_blocked"
    assert observation.authority_blockers == ("candidate_fixture_value_run_not_authority",)
    assert observation.value_ref is not None
    assert len(captured) == 1
    consumer_kwargs, produced_outer = captured[0]
    ir_store = ensure_ir_artifact_store(shared_store)
    basis_ref = gc._value_artifact_ref(
        consumer_kwargs["run_basis_ref"], expected_kind="runtime.value_owner_method_run_basis"
    )
    basis = gc.ValueOwnerMethodRunBasisV2.model_validate(
        gc._value_load_ref_payload(ir_store, basis_ref)
    )
    intent = gc.ValueOwnerMethodRunIntentV1.model_validate(
        gc._value_load_ref_payload(ir_store, basis.intent_ref)
    )
    assignment = gc.ValueOwnerSourceVariableAssignmentV1.model_validate(
        gc._value_load_ref_payload(ir_store, basis.assignment_ref)
    )
    runner_request = gc.ValueOwnerMethodRunnerRequestV1.model_validate(
        gc._value_load_ref_payload(ir_store, basis.runner_request_ref)
    )
    report = load_causal_effect_report(
        ir_store, CausalEffectReportRef.model_validate(basis.report_ref.model_dump(mode="python"))
    )
    bounds_ref = gc._value_artifact_ref(
        report.metadata["identification_bounds_ref"], expected_kind="ir.bounds_bundle"
    )
    bounds = BoundsBundle.model_validate(gc._value_load_ref_payload(ir_store, bounds_ref))
    manski = next(row for row in bounds.method_summaries if row.method is BoundMethod.MANSKI)
    estimand = gc._typed_value_estimand_spec(intent.estimand_spec_json)
    native = report.to_value_uncertainty(
        estimand=estimand,
        projection_binding=NativeValueEstimandBinding.model_validate(
            runner_request.native_estimand_binding
        ),
    )
    assert native is not None and native.gate_eligible is False
    assert report.point_estimate is not None and report.confidence_interval is not None
    assert native.point_estimate == pytest.approx(report.point_estimate)
    assert report.confidence_interval[0] != pytest.approx(report.confidence_interval[1])
    assert report.confidence_interval[0] != pytest.approx(report.point_estimate)
    assert assignment.assignment_provenance == "consumer_asserted"
    assert assignment.source_time_status == "not_established"
    assert assignment.measurement_unit == measurement_unit
    assert assignment.outcome_bounds_unit == measurement_unit
    assert basis.estimand_coordinate == gc._value_estimand_coordinate(estimand)
    assert gc._value_manifest_has_exact_inputs(
        ir_store,
        basis.report_ref,
        (
            (basis.panel_input_ref, "exact_method_input_bytes"),
            (basis.runner_request_ref, "selected_method_runner_request"),
            (bounds_ref, "candidate_identification_bounds"),
        ),
    )
    outer_manifest = ir_store.get_manifest(observation.value_ref)
    outer_ref = gc._value_artifact_ref(
        artifact_ref_for_manifest(outer_manifest),
        expected_kind="runtime.value_outer_set_candidate_fixture",
    )
    assert gc._value_manifest_has_exact_inputs(
        ir_store, outer_ref, ((basis_ref, "owner_method_run_basis"),)
    )
    persisted = ValueOuterSet.from_persisted_payload(
        gc._value_load_ref_payload(ir_store, outer_ref)
    )
    with catalog_serving_source_scope(catalog_source):
        fresh = actual_consumer(**consumer_kwargs)
    assert persisted == produced_outer == fresh
    assert fresh.calibration_scope["measurement_unit"] == measurement_unit
    assert fresh.calibration_scope["authority_scope"] == "candidate_fixture_only"
    assert fresh.representation_status == "search_only"
    assert "bounds_estimand_relation_not_established" in fresh.assumptions
    assert fresh.lower == pytest.approx((manski.lower_bound,))
    assert fresh.upper == pytest.approx((manski.upper_bound,))
    assert fresh.statistical_lower == pytest.approx((native.confidence_interval[0],))
    assert fresh.statistical_upper == pytest.approx((native.confidence_interval[1],))

    wrong_unit = _avg_income_typed_atom_candidate(problem, unit_id="synthetic_score")
    foreign_problem = problem.model_copy(update={"design_problem_id": "foreign_b31_subject"})
    wrong_subject = _avg_income_typed_atom_candidate(foreign_problem, unit_id=measurement_unit)
    for wrong, reason in (
        (wrong_unit, "value_owner_source_atom_unit_mismatch"),
        (wrong_subject, "value_owner_source_atom_subject_mismatch"),
    ):
        with pytest.raises(ValueError, match=reason):
            gc._value_owner_source_atom_estimand_binding(
                candidate=wrong,
                problem=problem,
                estimand=estimand,
                measurement_unit=measurement_unit,
            )
        with catalog_serving_source_scope(catalog_source), pytest.raises(ValueError, match=reason):
            actual_consumer(**{**consumer_kwargs, "candidate": wrong})
    return {
        "basis": basis,
        "basis_ref": basis_ref,
        "bounds_ref": bounds_ref,
        "catalog_source": catalog_source,
        "consumer": actual_consumer,
        "consumer_kwargs": consumer_kwargs,
        "estimand": estimand,
        "ir_store": ir_store,
        "manski": manski,
        "outer": fresh,
        "report": report,
    }


def test_real_source_keeps_subject_and_native_interval(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Trace one actual selected native result, its interval, bounds, and input units."""
    shared = FileSystemCAS(tmp_path / "cas")
    with monkeypatch.context() as patch:
        run = _run_source_case(
            tmp_path / "m",
            patch,
            shared,
            measurement_unit="m",
            raw_unit="km",
            raw_scale=0.001,
            canonical_scale=1.0,
        )

    expected_lower, expected_upper = _reference_manski_meters()
    assert (expected_lower, expected_upper) == (Fraction(-1279, 200), Fraction(1321, 200))
    assert (run["manski"].lower_bound, run["manski"].upper_bound) == pytest.approx(
        (float(expected_lower), float(expected_upper)), rel=1e-9, abs=1e-9
    )
    assert run["manski"].lower_bound < run["manski"].upper_bound

    # Re-persist the exact real report under a different manifest profile. The
    # payload and digest stay unchanged, but the panel input role is false.
    basis, ir_store = run["basis"], run["ir_store"]
    wrong_ref = gc._value_artifact_ref(
        persist_causal_effect_report(
            ir_store,
            run["report"],
            inputs=[
                gc._value_input_ref(basis.panel_input_ref, role="wrong_method_input_role"),
                gc._value_input_ref(
                    basis.runner_request_ref, role="selected_method_runner_request"
                ),
                gc._value_input_ref(run["bounds_ref"], role="candidate_identification_bounds"),
            ],
            return_selected_profile=True,
        ),
        expected_kind="ir.causal_effect_report",
    )
    assert wrong_ref.artifact_id == basis.report_ref.artifact_id
    assert wrong_ref.manifest_profile_sha256 != basis.report_ref.manifest_profile_sha256
    assert ir_store.get_bytes(wrong_ref.model_dump(mode="python")) == ir_store.get_bytes(
        basis.report_ref.model_dump(mode="python")
    )
    wrong_basis_ref = _rebind_basis(
        ir_store,
        basis,
        report_ref=wrong_ref.model_dump(mode="json"),
    )
    with (
        catalog_serving_source_scope(run["catalog_source"]),
        pytest.raises(ValueError, match="value_owner_method_report_method_mismatch"),
    ):
        run["consumer"](**{**run["consumer_kwargs"], "run_basis_ref": wrong_basis_ref})
