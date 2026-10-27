from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import BaseModel

from polisyos.core.artifacts import ensure_ir_artifact_store
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.contracts.value_outer_set import DataTrust
from polisyos.foundry.methods.components.consensus import EstimandSpec
from polisyos.ir.analytics.causal import load_causal_effect_report, persist_causal_effect_report
from polisyos.ir.analytics.uncertainty import NativeValueEstimandBinding
from polisyos.ir.artifacts import get_json_artifact, put_json_artifact
from polisyos.ir.model_layer.canon import CanonSpec
from polisyos.ir.registry.refs import CausalEffectReportRef
from polisyos.runtime.quality import generation_cycle as gc


def _profile() -> gc.ValueDataProfile:
    periods = tuple(range(8))
    rows: list[dict[str, Any]] = []
    controls = [
        [
            10.0 + 1.7 * index + (0.62 + 0.07 * index) * period + 0.035 * period**2
            for period in periods
        ]
        for index in range(5)
    ]
    treated = [10.6 + 0.67 * period + 0.035 * period**2 for period in periods]
    treatment_effects = (1.0, 2.0, 2.5, 3.0)
    for offset, effect in enumerate(treatment_effects, start=4):
        treated[offset] += effect
    outcomes = [treated, *controls]
    units = ("treated", "c1", "c2", "c3", "c4", "c5")
    for unit_id, values in zip(units, outcomes, strict=True):
        for period_id, outcome_value in enumerate(values):
            row_fields = {
                "unit_id": unit_id,
                "period_id": period_id,
                "outcome_value": float(outcome_value),
                "measurement_unit": "synthetic_index",
                "source_row_content_hashes": (
                    gc.gy_content_hash(
                        {
                            "fixture": "b31-v2",
                            "unit_id": unit_id,
                            "period_id": period_id,
                            "outcome_value": float(outcome_value),
                        }
                    ),
                ),
            }
            rows.append(
                gc.ValueOwnerRow(
                    **row_fields,
                    row_content_hash=gc.gy_content_hash(row_fields),
                ).model_dump(mode="json")
            )
    payload: dict[str, Any] = {
        "schema_version": "policyos.runtime.value_data_profile.v2",
        "outcome": "avg_income",
        "measurement_unit": "synthetic_index",
        "rows": rows,
        "owner_row_count": len(rows),
        "unit_count": len(units),
        "period_count": len(periods),
        "available_data_modalities": ["panel", "tabular"],
        "treatment_assignment_status": "owner_assignment_unresolved",
        "owner_access_ref": "fixture://b31-v2/synthetic-panel",
        "owner_rows_content_hash": gc.gy_content_hash(rows),
    }
    return gc.ValueDataProfile.model_validate(
        {**payload, "content_hash": gc.gy_content_hash(payload)}
    )


def test_historical_profile_without_unit_is_not_upgraded_to_candidate_run_input() -> None:
    profile_payload = _profile().model_dump(mode="json")
    profile_payload["schema_version"] = "policyos.runtime.value_data_profile.v1"

    with pytest.raises(ValueError, match="schema_version"):
        gc.ValueDataProfile.model_validate(profile_payload)


def _persist_json(
    store: Any,
    payload: Any,
    *,
    kind: str,
    schema: str,
    schema_version: str = "1.0",
    inputs: list[Any] | None = None,
    canon_spec: CanonSpec | None = None,
) -> gc.ValueArtifactBindingRefV1:
    ref = put_json_artifact(
        store,
        payload,
        kind=kind,
        schema_name=schema,
        schema_version=schema_version,
        inputs=inputs,
        canon_spec=canon_spec or CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    return gc._value_artifact_ref(ref, expected_kind=kind)


def _basis_input_edges(basis: gc.ValueOwnerMethodRunBasisV2) -> list[Any]:
    return [
        gc._value_input_ref(basis.intent_ref, role="immutable_run_intent"),
        gc._value_input_ref(basis.profile_ref, role="selected_owner_profile"),
        gc._value_input_ref(basis.assignment_ref, role="owner_assignment"),
        gc._value_input_ref(basis.panel_input_ref, role="exact_method_input_bytes"),
        gc._value_input_ref(basis.runner_request_ref, role="selected_method_runner_request"),
        gc._value_input_ref(basis.report_ref, role="native_method_report"),
        gc._value_input_ref(basis.execution_receipt_ref, role="method_execution_receipt"),
    ]


def _request_input_edges(request: gc.ValueOwnerMethodRunnerRequestV1) -> list[Any]:
    return [
        gc._value_input_ref(request.intent_ref, role="immutable_run_intent"),
        gc._value_input_ref(request.profile_ref, role="selected_owner_profile"),
        gc._value_input_ref(request.assignment_ref, role="owner_assignment"),
        gc._value_input_ref(request.panel_input_ref, role="exact_method_input_bytes"),
    ]


def _execution_receipt_input_edges(
    receipt: gc.ValueOwnerMethodExecutionReceiptV1,
) -> list[Any]:
    return [
        gc._value_input_ref(receipt.intent_ref, role="immutable_run_intent"),
        gc._value_input_ref(receipt.profile_ref, role="selected_owner_profile"),
        gc._value_input_ref(receipt.assignment_ref, role="owner_assignment"),
        gc._value_input_ref(receipt.panel_input_ref, role="exact_method_input_bytes"),
        gc._value_input_ref(receipt.runner_request_ref, role="selected_method_runner_request"),
        gc._value_input_ref(receipt.report_ref, role="native_method_report"),
    ]


def _rebind_basis(
    store: Any,
    basis: gc.ValueOwnerMethodRunBasisV2,
    **changes: Any,
) -> gc.ValueArtifactBindingRefV1:
    payload = basis.model_dump(mode="json")
    payload.update(changes)
    payload.pop("content_hash")
    payload["content_hash"] = gc.gy_content_hash(payload)
    rebound = gc.ValueOwnerMethodRunBasisV2.model_validate(payload)
    return _persist_json(
        store,
        rebound.model_dump(mode="json"),
        kind="runtime.value_owner_method_run_basis",
        schema="runtime.value_owner_method_run_basis.v2",
        schema_version="2.0",
        inputs=_basis_input_edges(rebound),
        canon_spec=CanonSpec(forbid_floats=True),
    )


def test_two_real_method_reports_share_owner_coordinate_and_fresh_cas_basis(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    producer = getattr(gc, "_produce_value_owner_method_run_basis", None)
    consumer = getattr(gc, "_value_outer_set_from_owner_method_run_basis", None)
    assert callable(producer), "N8 has no persisted owner-bound real method-run producer"
    assert callable(consumer), "N8 has no fresh CAS consumer for an owner method-run basis"

    core_store = FileSystemCAS(tmp_path / "cas")
    ir_store = ensure_ir_artifact_store(core_store)
    profile = _profile()
    profile_ref = _persist_json(
        ir_store,
        profile.model_dump(mode="json"),
        kind="runtime.value_data_profile",
        schema="runtime.value_data_profile.v2",
    )
    assignment_payload = {
        "schema_version": "policyos.runtime.value_owner_treatment_assignment_fixture.v1",
        "authority_scope": "candidate_fixture_only",
        "production_value_eligible": False,
        "profile_content_hash": profile.content_hash,
        "outcome": profile.outcome,
        "measurement_unit": profile.measurement_unit,
        "treated_unit_ids": ["treated"],
        "treatment_period_id": 4,
        "fixture_identification_lower": 2.125,
        "fixture_identification_upper": 2.125,
        "source_ref": "fixture://b31-v2/synthetic-dgp-and-assignment",
    }
    assignment_payload["content_hash"] = gc.gy_content_hash(assignment_payload)
    assignment_ref = _persist_json(
        ir_store,
        assignment_payload,
        kind="runtime.value_owner_treatment_assignment_fixture",
        schema="runtime.value_owner_treatment_assignment_fixture.v1",
    )
    estimand = EstimandSpec(
        query_id="fixture-query-b31-v2",
        estimand_id="ATT",
        outcome=profile.outcome,
        treatment_or_exposure="fixture.treated_unit_after_period_4",
        population="the explicitly treated fixture unit",
        time_horizon="periods_4_to_7",
        unit=profile.measurement_unit,
        target_role="estimate",
    )
    intent_payload: dict[str, Any] = {
        "schema_version": "policyos.runtime.value_owner_method_run_intent.v1",
        "authority_scope": "candidate_fixture_only",
        "production_value_eligible": False,
        "profile_content_hash": profile.content_hash,
        "profile_ref": profile_ref.model_dump(mode="json"),
        "assignment_ref": assignment_ref.model_dump(mode="json"),
        "estimand_spec_json": json.dumps(
            {
                "query_id": estimand.query_id,
                "estimand_id": estimand.estimand_id,
                "outcome": estimand.outcome,
                "treatment_or_exposure": estimand.treatment_or_exposure,
                "covariates_or_conditioning": [],
                "adjustment_set": None,
                "population": estimand.population,
                "sample_filter": None,
                "time_horizon": estimand.time_horizon,
                "prediction_origin": None,
                "unit": estimand.unit,
                "scale": estimand.scale,
                "transform": None,
                "target_role": estimand.target_role,
                "loss_or_utility_id": None,
            },
            sort_keys=True,
            separators=(",", ":"),
        ),
        "seed": 7,
    }
    intent_payload["content_hash"] = gc.gy_content_hash(intent_payload)
    intent = gc.ValueOwnerMethodRunIntentV1.model_validate(intent_payload)
    world = SimpleNamespace(
        content_hash="sha256:" + "a" * 64,
        valid_time_scope="controlled-fixture",
    )
    trust = DataTrust(
        tier="candidate_fixture",
        trust_cap=0.5,
        trust_multiplier=0.5,
        min_coverage=0.0,
        max_coverage=1.0,
        promotion_floor=0.5,
        authority_ref="fixture://candidate-only",
    )

    from polisyos.foundry.methods.catalog.causal.did import StandardDifferenceInDifferences
    from polisyos.foundry.methods.catalog.causal.synthetic_control import SyntheticControlMethod

    method_cases = (
        (
            StandardDifferenceInDifferences.signature.fqn,
            {"confidence_level": 0.95},
        ),
        (
            SyntheticControlMethod.signature.fqn,
            {"confidence_level": 0.95, "n_placebo_runs": 2, "max_iter": 120},
        ),
    )
    coordinate_sets = []
    reports = []
    outer_sets = []
    basis_refs: list[gc.ValueArtifactBindingRefV1] = []
    captured_basis_refs: list[gc.ValueArtifactBindingRefV1] = []
    original_producer = producer

    def capture_producer(**kwargs: Any) -> gc.ValueArtifactBindingRefV1:
        basis_ref = original_producer(**kwargs)
        captured_basis_refs.append(basis_ref)
        return basis_ref

    monkeypatch.setattr(gc, "_produce_value_owner_method_run_basis", capture_producer)
    from tests.unit.runtime.quality.test_value_gate import (
        _avg_income_candidate,
        _avg_income_problem,
        _simulation,
        _simulation_execution_context,
        _world_record,
    )

    class CandidateFixtureOwnerGateway:
        def load_value_data_profile(self, **_: Any) -> gc.ValueDataProfile:
            return profile

        def load_value_method_run_intent(self, **_: Any) -> gc.ValueOwnerMethodRunIntentV1:
            return intent

    for method_fqn, params in method_cases:
        if method_fqn == method_cases[0][0]:
            problem = _avg_income_problem()
            candidate = _avg_income_candidate()
            world_record = _world_record()
            simulation = _simulation(world_record, candidate_id=candidate.candidate_id)
            observation = gc.FoundryValuePort(
                evaluation_context=_simulation_execution_context(
                    candidate=candidate,
                    simulation=simulation,
                    problem=problem,
                ),
                owner_gateway=CandidateFixtureOwnerGateway(),
                requested_method_fqn=method_fqn,
                data_trust=trust,
                artifact_store=core_store,
            )(
                candidate=candidate,
                simulation=simulation,
                problem=problem,
                cycle_index=0,
            )
            assert observation.status == "value_blocked"
            assert observation.authority_blockers == ("candidate_fixture_value_run_not_authority",)
            assert observation.value_receipt is None
            assert observation.value_ref is not None
            assert observation.selected_method_fqn == method_fqn
            assert len(captured_basis_refs) == 1
            basis_ref = captured_basis_refs[-1]
        else:
            basis_ref = producer(
                store=ir_store,
                profile=profile,
                intent=intent,
                selected_method_fqn=method_fqn,
                method_parameters=params,
            )
        basis_refs.append(basis_ref)
        basis = gc.ValueOwnerMethodRunBasisV2.model_validate(
            get_json_artifact(ir_store, basis_ref.model_dump(mode="python"))
        )
        selected_basis_refs = (
            basis_ref,
            basis.intent_ref,
            basis.profile_ref,
            basis.assignment_ref,
            basis.panel_input_ref,
            basis.runner_request_ref,
            basis.report_ref,
            basis.execution_receipt_ref,
        )
        assert all(ref.manifest_profile_sha256 is not None for ref in selected_basis_refs)
        runner_request = gc.ValueOwnerMethodRunnerRequestV1.model_validate(
            get_json_artifact(
                ir_store,
                basis.runner_request_ref.model_dump(mode="python"),
            )
        )
        report = load_causal_effect_report(
            ir_store,
            CausalEffectReportRef.model_validate(basis.report_ref.model_dump(mode="python")),
        )
        projected_interval = report.to_value_uncertainty(
            estimand=estimand,
            projection_binding=NativeValueEstimandBinding.model_validate(
                runner_request.native_estimand_binding
            ),
        )
        value_set = consumer(
            store=ir_store,
            run_basis_ref=basis_ref,
            world_record=world,
            data_trust=trust,
        )
        assert report.status.value == "success"
        assert report.estimand == estimand.estimand_id
        assert projected_interval is not None
        assert projected_interval.gate_eligible is False
        assert projected_interval.is_heuristic_ci is False
        assert basis.authority_scope == "candidate_fixture_only"
        assert basis.production_value_eligible is False
        assert basis.runner_input_sha256.startswith("sha256:")
        assert value_set.lower == value_set.upper == (2.125,)
        assert value_set.statistical_lower == (projected_interval.confidence_interval[0],)
        assert value_set.statistical_upper == (projected_interval.confidence_interval[1],)
        assert value_set.assumption_status == "declared"
        assert value_set.representation_status == "search_only"
        coordinate_sets.append(value_set.coordinates)
        reports.append(report)
        outer_sets.append(value_set)

    assert coordinate_sets[0] == coordinate_sets[1]
    assert len(set(coordinate_sets[0])) == 1
    assert reports[0].method != reports[1].method
    assert any(
        abs(
            (report.confidence_interval[1] - report.point_estimate)
            - (report.point_estimate - report.confidence_interval[0])
        )
        > 1e-6
        for report in reports
    )

    first_basis = gc.ValueOwnerMethodRunBasisV2.model_validate(
        get_json_artifact(ir_store, basis_refs[0].model_dump(mode="python"))
    )
    first_request = gc.ValueOwnerMethodRunnerRequestV1.model_validate(
        get_json_artifact(ir_store, first_basis.runner_request_ref.model_dump(mode="python"))
    )
    changed_parameters = json.loads(first_request.method_parameters_json)
    changed_parameters["confidence_level"] = 0.90
    changed_request_payload = first_request.model_dump(mode="json", exclude={"content_hash"})
    changed_request_payload["method_parameters_json"] = json.dumps(
        changed_parameters,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )
    changed_request = gc.ValueOwnerMethodRunnerRequestV1.model_validate(
        {
            **changed_request_payload,
            "content_hash": gc.gy_content_hash(changed_request_payload),
        }
    )
    changed_request_ref = _persist_json(
        ir_store,
        changed_request.model_dump(mode="json"),
        kind="runtime.value_owner_method_runner_request",
        schema="runtime.value_owner_method_runner_request.v1",
        inputs=_request_input_edges(changed_request),
    )
    changed_report_ref_raw = persist_causal_effect_report(
        ir_store,
        reports[0],
        inputs=[
            gc._value_input_ref(first_basis.panel_input_ref, role="exact_method_input_bytes"),
            gc._value_input_ref(
                gc._value_artifact_ref(changed_request_ref),
                role="selected_method_runner_request",
            ),
        ],
        return_selected_profile=True,
    )
    changed_report_ref = gc._value_artifact_ref(changed_report_ref_raw)
    assert changed_report_ref.artifact_id == first_basis.report_ref.artifact_id
    changed_parameters_basis_ref = _rebind_basis(
        ir_store,
        first_basis,
        runner_request_ref=gc._value_artifact_ref(changed_request_ref).model_dump(mode="json"),
        report_ref=changed_report_ref.model_dump(mode="json"),
        report_sha256="sha256:"
        + hashlib.sha256(
            ir_store.get_bytes(changed_report_ref.model_dump(mode="python"))
        ).hexdigest(),
    )
    with pytest.raises(
        ValueError,
        match="value_owner_method_execution_receipt_binding_mismatch",
    ):
        consumer(
            store=ir_store,
            run_basis_ref=changed_parameters_basis_ref,
            world_record=world,
            data_trust=trust,
        )

    # A content-valid replacement receipt still cannot make the frozen report
    # agree with the changed confidence request; the consumer checks the output.
    original_execution_receipt = gc.ValueOwnerMethodExecutionReceiptV1.model_validate(
        get_json_artifact(
            ir_store,
            first_basis.execution_receipt_ref.model_dump(mode="python"),
        )
    )
    rebound_receipt_payload = original_execution_receipt.model_dump(
        mode="json",
        exclude={"content_hash"},
    )
    rebound_receipt_payload["runner_request_ref"] = gc._value_artifact_ref(
        changed_request_ref
    ).model_dump(mode="json")
    rebound_receipt_payload["report_ref"] = changed_report_ref.model_dump(mode="json")
    rebound_receipt_payload["requested_method_parameters_json"] = (
        changed_request.method_parameters_json
    )
    rebound_receipt = gc.ValueOwnerMethodExecutionReceiptV1.model_validate(
        {
            **rebound_receipt_payload,
            "content_hash": gc.gy_content_hash(rebound_receipt_payload),
        }
    )
    rebound_receipt_ref = _persist_json(
        ir_store,
        rebound_receipt.model_dump(mode="json"),
        kind="runtime.value_owner_method_execution_receipt",
        schema="runtime.value_owner_method_execution_receipt.v1",
        inputs=_execution_receipt_input_edges(rebound_receipt),
    )
    parameter_output_mismatch_basis_ref = _rebind_basis(
        ir_store,
        first_basis,
        runner_request_ref=gc._value_artifact_ref(changed_request_ref).model_dump(mode="json"),
        report_ref=changed_report_ref.model_dump(mode="json"),
        execution_receipt_ref=gc._value_artifact_ref(rebound_receipt_ref).model_dump(mode="json"),
        report_sha256="sha256:"
        + hashlib.sha256(
            ir_store.get_bytes(changed_report_ref.model_dump(mode="python"))
        ).hexdigest(),
    )
    with pytest.raises(
        ValueError,
        match="value_owner_method_execution_report_parameters_mismatch",
    ):
        consumer(
            store=ir_store,
            run_basis_ref=parameter_output_mismatch_basis_ref,
            world_record=world,
            data_trust=trust,
        )

    changed_intent_payload = intent.model_dump(mode="json", exclude={"content_hash"})
    changed_intent_payload["seed"] = intent.seed + 1
    changed_intent = gc.ValueOwnerMethodRunIntentV1.model_validate(
        {
            **changed_intent_payload,
            "content_hash": gc.gy_content_hash(changed_intent_payload),
        }
    )
    changed_intent_ref = _persist_json(
        ir_store,
        changed_intent.model_dump(mode="json"),
        kind="runtime.value_owner_method_run_intent",
        schema="runtime.value_owner_method_run_intent.v1",
        inputs=[
            gc._value_input_ref(profile_ref, role="selected_owner_profile"),
            gc._value_input_ref(assignment_ref, role="owner_assignment"),
        ],
        canon_spec=CanonSpec(forbid_floats=True),
    )
    old_panel = get_json_artifact(
        ir_store,
        first_basis.panel_input_ref.model_dump(mode="python"),
    )
    changed_panel_ref = _persist_json(
        ir_store,
        old_panel,
        kind="runtime.value_owner_method_panel_input",
        schema="runtime.value_owner_method_panel_input.v1",
        inputs=[
            gc._value_input_ref(profile_ref, role="selected_owner_profile"),
            gc._value_input_ref(assignment_ref, role="owner_assignment"),
            gc._value_input_ref(
                gc._value_artifact_ref(changed_intent_ref),
                role="immutable_run_intent",
            ),
        ],
    )
    changed_seed_request_payload = first_request.model_dump(
        mode="json",
        exclude={"content_hash"},
    )
    changed_seed_request_payload["intent_ref"] = gc._value_artifact_ref(
        changed_intent_ref
    ).model_dump(mode="json")
    changed_seed_request_payload["panel_input_ref"] = gc._value_artifact_ref(
        changed_panel_ref
    ).model_dump(mode="json")
    changed_seed_request_payload["seed"] = changed_intent.seed
    changed_seed_request = gc.ValueOwnerMethodRunnerRequestV1.model_validate(
        {
            **changed_seed_request_payload,
            "content_hash": gc.gy_content_hash(changed_seed_request_payload),
        }
    )
    changed_seed_request_ref = _persist_json(
        ir_store,
        changed_seed_request.model_dump(mode="json"),
        kind="runtime.value_owner_method_runner_request",
        schema="runtime.value_owner_method_runner_request.v1",
        inputs=_request_input_edges(changed_seed_request),
    )
    changed_seed_report_ref = gc._value_artifact_ref(
        persist_causal_effect_report(
            ir_store,
            reports[0],
            inputs=[
                gc._value_input_ref(
                    gc._value_artifact_ref(changed_panel_ref),
                    role="exact_method_input_bytes",
                ),
                gc._value_input_ref(
                    gc._value_artifact_ref(changed_seed_request_ref),
                    role="selected_method_runner_request",
                ),
            ],
            return_selected_profile=True,
        )
    )
    assert changed_seed_report_ref.artifact_id == first_basis.report_ref.artifact_id
    changed_seed_basis_ref = _rebind_basis(
        ir_store,
        first_basis,
        intent_ref=gc._value_artifact_ref(changed_intent_ref).model_dump(mode="json"),
        panel_input_ref=gc._value_artifact_ref(changed_panel_ref).model_dump(mode="json"),
        runner_request_ref=gc._value_artifact_ref(changed_seed_request_ref).model_dump(mode="json"),
        report_ref=changed_seed_report_ref.model_dump(mode="json"),
        report_sha256="sha256:"
        + hashlib.sha256(
            ir_store.get_bytes(changed_seed_report_ref.model_dump(mode="python"))
        ).hexdigest(),
    )
    with pytest.raises(
        ValueError,
        match="value_owner_method_execution_receipt_binding_mismatch",
    ):
        consumer(
            store=ir_store,
            run_basis_ref=changed_seed_basis_ref,
            world_record=world,
            data_trust=trust,
        )

    first_basis = gc.ValueOwnerMethodRunBasisV2.model_validate(
        get_json_artifact(ir_store, basis_refs[0].model_dump(mode="python"))
    )
    swapped_basis = first_basis.model_dump(mode="json")
    swapped_report_ref_raw = persist_causal_effect_report(
        ir_store,
        reports[1],
        inputs=[
            gc._value_input_ref(first_basis.panel_input_ref, role="exact_method_input_bytes"),
            gc._value_input_ref(
                first_basis.runner_request_ref,
                role="selected_method_runner_request",
            ),
        ],
        return_selected_profile=True,
    )
    swapped_report_ref = gc._value_artifact_ref(swapped_report_ref_raw)
    swapped_basis["report_ref"] = swapped_report_ref.model_dump(mode="json")
    swapped_basis["report_sha256"] = (
        "sha256:"
        + hashlib.sha256(
            ir_store.get_bytes(swapped_report_ref.model_dump(mode="python"))
        ).hexdigest()
    )
    swapped_basis["native_interval_content_hash"] = gc.gy_content_hash(
        reports[1].confidence_interval
    )
    swapped_basis.pop("content_hash")
    swapped_basis["content_hash"] = gc.gy_content_hash(swapped_basis)
    swapped_basis_model = gc.ValueOwnerMethodRunBasisV2.model_validate(swapped_basis)
    swapped_ref = _persist_json(
        ir_store,
        swapped_basis_model.model_dump(mode="json"),
        kind="runtime.value_owner_method_run_basis",
        schema="runtime.value_owner_method_run_basis.v2",
        schema_version="2.0",
        inputs=_basis_input_edges(swapped_basis_model),
        canon_spec=CanonSpec(forbid_floats=True),
    )
    with pytest.raises(ValueError, match="value_owner_method_report_method_mismatch"):
        consumer(
            store=ir_store,
            run_basis_ref=swapped_ref,
            world_record=world,
            data_trust=trust,
        )

    missing_basis_ref_payload = basis_refs[0].model_dump(mode="json")
    missing_basis_ref_payload["artifact_id"] = "sha256:" + "f" * 64
    missing_basis_ref = gc.ValueArtifactBindingRefV1.model_validate(missing_basis_ref_payload)
    with pytest.raises((ValueError, OSError, KeyError)):
        consumer(
            store=ir_store,
            run_basis_ref=missing_basis_ref,
            world_record=world,
            data_trust=trust,
        )

    class _TamperedPanelProfileStore:
        def __init__(self, delegate: Any) -> None:
            self._delegate = delegate

        def __getattr__(self, name: str) -> Any:
            return getattr(self._delegate, name)

        def get_raw_manifest_bytes(
            self,
            selector: object,
            *,
            manifest_profile_sha256: str | None = None,
        ) -> bytes:
            raw_manifest = self._delegate.get_raw_manifest_bytes(
                selector, manifest_profile_sha256=manifest_profile_sha256
            )
            manifest = self._delegate.get_manifest(selector)
            if manifest.kind != "runtime.value_owner_method_panel_input":
                return raw_manifest
            raw = json.loads(raw_manifest)
            raw["canon"]["forbid_floats"] = not raw["canon"]["forbid_floats"]
            return json.dumps(
                raw, sort_keys=True, separators=(",", ":"), ensure_ascii=False
            ).encode()

    from polisyos.foundry.methods.backends import numpy_runner

    def forbidden_runner_call(*_: Any, **__: Any) -> None:
        raise AssertionError("method runner received a nonconformant selected panel")

    with monkeypatch.context() as profile_context:
        profile_context.setattr(numpy_runner.NumpyRunner, "execute", forbidden_runner_call)
        with pytest.raises(ValueError, match="ir_artifact_selected_manifest_changed"):
            producer(
                store=_TamperedPanelProfileStore(core_store),
                profile=profile,
                intent=intent,
                selected_method_fqn=method_cases[0][0],
                method_parameters=method_cases[0][1],
            )


def _selected_ref(
    *, artifact_hex: str, profile_hex: str, kind: str
) -> gc.ValueArtifactBindingRefV1:
    return gc.ValueArtifactBindingRefV1.model_validate(
        {
            "artifact_id": f"sha256:{artifact_hex * 64}",
            "kind": kind,
            "media_type": "application/json",
            "manifest_profile_sha256": f"sha256:{profile_hex * 64}",
        }
    )


def test_manifest_lineage_requires_exact_complete_input_multiset() -> None:
    basis = _selected_ref(
        artifact_hex="a", profile_hex="1", kind="runtime.value_owner_method_run_basis"
    )
    intent = _selected_ref(
        artifact_hex="b", profile_hex="2", kind="runtime.value_owner_method_run_intent"
    )
    panel = _selected_ref(
        artifact_hex="c", profile_hex="3", kind="runtime.value_owner_method_panel_input"
    )
    expected = ((intent, "intent"), (panel, "panel"))
    intended_edges = [
        SimpleNamespace(
            artifact_id=item.artifact_id,
            role=role,
            manifest_profile_sha256=item.manifest_profile_sha256,
        )
        for item, role in expected
    ]

    class ManifestStore:
        def __init__(self, inputs: list[object]) -> None:
            self.inputs = inputs

        def get_manifest_by_profile(self, artifact_id: str, profile_sha256: str) -> object:
            assert artifact_id == basis.artifact_id
            assert profile_sha256 == basis.manifest_profile_sha256
            return SimpleNamespace(inputs=self.inputs)

    assert gc._value_manifest_has_exact_inputs(ManifestStore(intended_edges), basis, expected)
    assert not gc._value_manifest_has_exact_inputs(
        ManifestStore([*intended_edges, intended_edges[0]]), basis, expected
    )
    assert not gc._value_manifest_has_exact_inputs(
        ManifestStore(
            [
                *intended_edges,
                SimpleNamespace(
                    artifact_id="sha256:" + "d" * 64,
                    role="unbound_extra",
                    manifest_profile_sha256="sha256:" + "4" * 64,
                ),
            ]
        ),
        basis,
        expected,
    )
    assert not gc._value_manifest_has_exact_inputs(
        ManifestStore(intended_edges[:1]), basis, expected
    )


@pytest.mark.parametrize(
    ("field", "malformed"),
    [
        ("covariates_or_conditioning", "xy"),
        ("covariates_or_conditioning", {"x": "y"}),
        ("adjustment_set", "xy"),
        ("adjustment_set", {"x": "y"}),
    ],
)
def test_estimand_json_rejects_non_array_coordinate_members(
    field: str,
    malformed: object,
) -> None:
    base_spec = EstimandSpec(
        query_id="strict-json",
        estimand_id="ATT",
        outcome="outcome",
        treatment_or_exposure="exposure",
        population="population",
        time_horizon="time",
        unit="unit",
        target_role="estimate",
    )
    payload = {
        "query_id": base_spec.query_id,
        "estimand_id": base_spec.estimand_id,
        "outcome": base_spec.outcome,
        "treatment_or_exposure": base_spec.treatment_or_exposure,
        "covariates_or_conditioning": [],
        "adjustment_set": None,
        "population": base_spec.population,
        "sample_filter": None,
        "time_horizon": base_spec.time_horizon,
        "prediction_origin": None,
        "unit": base_spec.unit,
        "scale": base_spec.scale,
        "transform": None,
        "target_role": base_spec.target_role,
        "loss_or_utility_id": None,
    }
    payload[field] = malformed
    with pytest.raises(ValueError, match="value_owner_method_estimand_invalid"):
        gc._value_estimand_spec_from_json(json.dumps(payload))


def test_owner_run_intent_does_not_upgrade_profileless_default_view() -> None:
    profile_ref = {
        "artifact_id": "sha256:" + "a" * 64,
        "kind": "runtime.value_data_profile",
        "media_type": "application/json",
    }
    assignment_ref = {
        "artifact_id": "sha256:" + "b" * 64,
        "kind": "runtime.value_owner_treatment_assignment_fixture",
        "media_type": "application/json",
        "manifest_profile_sha256": "sha256:" + "2" * 64,
    }
    payload: dict[str, Any] = {
        "schema_version": "policyos.runtime.value_owner_method_run_intent.v1",
        "authority_scope": "candidate_fixture_only",
        "production_value_eligible": False,
        "profile_content_hash": "sha256:" + "3" * 64,
        "profile_ref": profile_ref,
        "assignment_ref": assignment_ref,
        "estimand_spec_json": json.dumps(
            {
                "query_id": "profileless",
                "estimand_id": "ATT",
                "outcome": "outcome",
                "treatment_or_exposure": "exposure",
                "covariates_or_conditioning": [],
                "adjustment_set": None,
                "population": "population",
                "sample_filter": None,
                "time_horizon": "time",
                "prediction_origin": None,
                "unit": "unit",
                "scale": None,
                "transform": None,
                "target_role": "estimate",
                "loss_or_utility_id": None,
            }
        ),
        "seed": 7,
    }
    intent_unhashed = gc.ValueOwnerMethodRunIntentV1.model_construct(
        schema_version=payload["schema_version"],
        authority_scope=payload["authority_scope"],
        production_value_eligible=payload["production_value_eligible"],
        profile_content_hash=payload["profile_content_hash"],
        profile_ref=gc.ValueArtifactBindingRefV1.model_validate(profile_ref),
        assignment_ref=gc.ValueArtifactBindingRefV1.model_validate(assignment_ref),
        estimand_spec_json=payload["estimand_spec_json"],
        seed=payload["seed"],
        content_hash="sha256:" + "0" * 64,
    )
    payload["content_hash"] = gc.gy_content_hash(
        intent_unhashed.model_dump(mode="json", exclude={"content_hash"})
    )
    with pytest.raises(ValueError, match="value_owner_method_selected_profile_unresolved"):
        gc.ValueOwnerMethodRunIntentV1.model_validate(payload)


# B31 V5 raw numeric input boundary


def _input_ref(kind: str, artifact_digit: str) -> dict[str, str]:
    return {
        "artifact_id": "sha256:" + artifact_digit * 64,
        "kind": kind,
        "media_type": "application/json",
        "manifest_profile_sha256": "sha256:" + "f" * 64,
    }


def _rehash_payload(payload: dict[str, Any]) -> dict[str, Any]:
    result = {key: value for key, value in payload.items() if key != "content_hash"}
    result["content_hash"] = gc.gy_content_hash(result)
    return result


def _raw_with_normalized_hash(
    payload: dict[str, Any], field: str, raw_value: object, normalized_value: object
) -> str:
    normalized = dict(payload)
    normalized[field] = normalized_value
    normalized = _rehash_payload(normalized)
    raw = dict(normalized)
    raw[field] = raw_value
    return json.dumps(raw, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _assignment_payload() -> dict[str, Any]:
    return _rehash_payload(
        {
            "schema_version": "policyos.runtime.value_owner_treatment_assignment_fixture.v1",
            "authority_scope": "candidate_fixture_only",
            "production_value_eligible": False,
            "profile_content_hash": "sha256:" + "1" * 64,
            "outcome": "avg_income",
            "measurement_unit": "synthetic_index",
            "treated_unit_ids": ["treated"],
            "treatment_period_id": 4,
            "fixture_identification_lower": 2.125,
            "fixture_identification_upper": 2.125,
            "source_ref": "fixture://b31/numeric-input",
        }
    )


def _estimand_json() -> str:
    return json.dumps(
        {
            "query_id": "numeric-input-query",
            "estimand_id": "ATT",
            "outcome": "avg_income",
            "treatment_or_exposure": "fixture-treatment",
            "covariates_or_conditioning": [],
            "adjustment_set": None,
            "population": "fixture population",
            "sample_filter": None,
            "time_horizon": "four periods",
            "prediction_origin": None,
            "unit": "synthetic_index",
            "scale": "identity",
            "transform": None,
            "target_role": "estimate",
            "loss_or_utility_id": None,
        },
        sort_keys=True,
        separators=(",", ":"),
    )


def _intent_payload() -> dict[str, Any]:
    return _rehash_payload(
        {
            "schema_version": "policyos.runtime.value_owner_method_run_intent.v1",
            "authority_scope": "candidate_fixture_only",
            "production_value_eligible": False,
            "profile_content_hash": "sha256:" + "1" * 64,
            "profile_ref": _input_ref("runtime.value_data_profile", "1"),
            "assignment_ref": _input_ref("runtime.value_owner_treatment_assignment_fixture", "2"),
            "estimand_spec_json": _estimand_json(),
            "seed": 7,
        }
    )


def _request_payload() -> dict[str, Any]:
    return _rehash_payload(
        {
            "schema_version": "policyos.runtime.value_owner_method_runner_request.v1",
            "authority_scope": "candidate_fixture_only",
            "production_value_eligible": False,
            "intent_ref": _input_ref("runtime.value_owner_method_run_intent", "3"),
            "profile_ref": _input_ref("runtime.value_data_profile", "1"),
            "assignment_ref": _input_ref("runtime.value_owner_treatment_assignment_fixture", "2"),
            "panel_input_ref": _input_ref("runtime.value_owner_method_panel_input", "4"),
            "selected_method_fqn": "causal.inference.difference_in_differences@1.0.0",
            "method_parameters_json": "{}",
            "seed": 7,
            "runner_input_sha256": "sha256:" + "5" * 64,
            "native_estimand_binding": {},
        }
    )


def _execution_receipt_payload() -> dict[str, Any]:
    return _rehash_payload(
        {
            "schema_version": "policyos.runtime.value_owner_method_execution_receipt.v1",
            "authority_scope": "candidate_fixture_only",
            "production_value_eligible": False,
            "intent_ref": _input_ref("runtime.value_owner_method_run_intent", "3"),
            "profile_ref": _input_ref("runtime.value_data_profile", "1"),
            "assignment_ref": _input_ref("runtime.value_owner_treatment_assignment_fixture", "2"),
            "panel_input_ref": _input_ref("runtime.value_owner_method_panel_input", "4"),
            "runner_request_ref": _input_ref("runtime.value_owner_method_runner_request", "6"),
            "report_ref": _input_ref("ir.causal_effect_report", "7"),
            "selected_method_fqn": "causal.inference.difference_in_differences@1.0.0",
            "requested_method_parameters_json": "{}",
            "runner_seed": 7,
            "runner_backend": "numpy",
            "runner_fingerprint": "0123456789abcdef",
            "runner_input_sha256": "sha256:" + "5" * 64,
            "report_sha256": "sha256:" + "8" * 64,
            "report_method_parameters_sha256": "sha256:" + "9" * 64,
        }
    )


_INTEGER_CASES = [
    pytest.param(
        gc.ValueOwnerTreatmentAssignmentFixtureV1,
        _assignment_payload,
        "treatment_period_id",
        4,
        id="assignment-treatment-period",
    ),
    pytest.param(gc.ValueOwnerMethodRunIntentV1, _intent_payload, "seed", 7, id="intent-seed"),
    pytest.param(
        gc.ValueOwnerMethodRunnerRequestV1, _request_payload, "seed", 7, id="request-seed"
    ),
    pytest.param(
        gc.ValueOwnerMethodExecutionReceiptV1,
        _execution_receipt_payload,
        "runner_seed",
        7,
        id="receipt-runner-seed",
    ),
]


@pytest.mark.parametrize(("model", "payload_factory", "field", "valid_value"), _INTEGER_CASES)
@pytest.mark.parametrize(
    ("raw_value", "normalized_value"),
    [
        pytest.param(True, 1, id="bool"),
        pytest.param("1", 1, id="numeric-string"),
        pytest.param(1.0, 1, id="integral-float"),
        pytest.param(None, None, id="null"),
    ],
)
def test_b31_integer_fields_reject_coercible_json_types_with_valid_normalized_hash(
    model: type[BaseModel],
    payload_factory: Any,
    field: str,
    valid_value: int,
    raw_value: object,
    normalized_value: int | None,
) -> None:
    payload = payload_factory()
    raw_json = _raw_with_normalized_hash(payload, field, raw_value, normalized_value)

    with pytest.raises(ValueError):
        model.model_validate_json(raw_json)


@pytest.mark.parametrize(("model", "payload_factory", "field", "valid_value"), _INTEGER_CASES)
def test_b31_integer_fields_accept_actual_integer_json_values(
    model: type[BaseModel], payload_factory: Any, field: str, valid_value: int
) -> None:
    payload = payload_factory()

    parsed = model.model_validate_json(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
    )

    assert getattr(parsed, field) == valid_value
    assert type(getattr(parsed, field)) is int


@pytest.mark.parametrize("field", ["fixture_identification_lower", "fixture_identification_upper"])
@pytest.mark.parametrize(
    ("raw_value", "normalized_value"),
    [
        pytest.param(True, 1.0, id="bool"),
        pytest.param("1.0", 1.0, id="numeric-string"),
        pytest.param(None, None, id="null"),
    ],
)
def test_b31_assignment_bounds_reject_coercible_json_types_with_valid_normalized_hash(
    field: str, raw_value: object, normalized_value: float | None
) -> None:
    payload = _assignment_payload()
    if field == "fixture_identification_upper":
        payload["fixture_identification_lower"] = 0.0
        payload = _rehash_payload(payload)
    raw_json = _raw_with_normalized_hash(payload, field, raw_value, normalized_value)

    with pytest.raises(ValueError):
        gc.ValueOwnerTreatmentAssignmentFixtureV1.model_validate_json(raw_json)


def test_b31_assignment_bounds_accept_finite_float_controls() -> None:
    payload = _assignment_payload()

    parsed = gc.ValueOwnerTreatmentAssignmentFixtureV1.model_validate_json(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
    )

    assert parsed.fixture_identification_lower == 2.125
    assert type(parsed.fixture_identification_lower) is float
    assert parsed.fixture_identification_upper == 2.125
    assert type(parsed.fixture_identification_upper) is float
