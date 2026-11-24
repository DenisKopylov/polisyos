"""Candidate-only EMP-01 interval witness through the real method and CAS owners."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import asdict
from pathlib import Path
from typing import Any

import pytest

from polisyos.core.artifacts import ensure_ir_artifact_store
from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.contracts.value_outer_set import DataTrust
from polisyos.foundry.extensions.registry import controlled_builtin_foundry_method_registry_scope
from polisyos.foundry.methods.catalog.causal.synthetic_control import SyntheticControlMethod
from polisyos.foundry.methods.components.consensus import EstimandSpec
from polisyos.ir.analytics.causal import load_causal_effect_report
from polisyos.ir.model_layer.canon import CanonViolation
from polisyos.ir.registry.refs import CausalEffectReportRef
from polisyos.runtime.quality import generation_cycle as gc
from polisyos.runtime.quality.candidate_value_method import _reconcile_selected_outer_set
from tests.unit.runtime.quality.test_b31_owner_run_basis_v2 import _persist_json, _rebind_basis
from tests.unit.runtime.quality.test_value_gate import (
    _avg_income_candidate,
    _avg_income_problem,
    _simulation,
    _simulation_execution_context,
    _world_record,
)


def _controlled_panel() -> gc.ValueDataProfile:
    """Build a dense panel with a known candidate-only counterfactual premise.

    At 95% the six placebo effects are approximately -856/91, four times
    168/91, and 184/91. Their interpolated tails are -8 and 2; the treated
    effect is 2. This specifies input data, not the resulting method report.
    """
    placebo_effects = (-856 / 91, *(168 / 91 for _ in range(4)), 184 / 91)
    post_values = (12.0, *(10.0 + 5 * effect / 6 for effect in placebo_effects))
    units = ("treated", *(f"control-{index}" for index in range(6)))
    rows: list[dict[str, Any]] = []
    for unit_id, post_value in zip(units, post_values, strict=True):
        for period_id in range(8):
            value = 10.0 if period_id < 4 else post_value
            fields = {
                "unit_id": unit_id,
                "period_id": period_id,
                "outcome_value": float(value),
                "measurement_unit": "synthetic_index",
                "source_row_content_hashes": (
                    gc.gy_content_hash(
                        {"fixture": "emp03-panel", "unit": unit_id, "period": period_id, "v": value}
                    ),
                ),
            }
            rows.append(
                gc.ValueOwnerRow(**fields, row_content_hash=gc.gy_content_hash(fields)).model_dump(
                    mode="json"
                )
            )
    payload: dict[str, Any] = {
        "schema_version": "policyos.runtime.value_data_profile.v2",
        "outcome": "avg_income",
        "measurement_unit": "synthetic_index",
        "rows": rows,
        "owner_row_count": len(rows),
        "unit_count": len(units),
        "period_count": 8,
        "available_data_modalities": ["panel", "tabular"],
        "treatment_assignment_status": "owner_assignment_unresolved",
        "owner_access_ref": "fixture://emp03/synthetic-panel",
        "owner_rows_content_hash": gc.gy_content_hash(rows),
    }
    return gc.ValueDataProfile.model_validate(
        {**payload, "content_hash": gc.gy_content_hash(payload)}
    )


def test_real_synthetic_control_keeps_id_and_confidence_intervals_distinct_after_reopen(
    tmp_path: Path,
    record_property: Callable[[str, object], None],
) -> None:
    """The N8 port persists two intervals with their actual candidate-only source."""
    store = FileSystemCAS(tmp_path / "cas")
    ir_store = ensure_ir_artifact_store(store)
    profile = _controlled_panel()
    profile_ref = _persist_json(
        ir_store,
        profile.model_dump(mode="json"),
        kind="runtime.value_data_profile",
        schema="runtime.value_data_profile.v2",
    )
    assignment_payload: dict[str, Any] = {
        "schema_version": "policyos.runtime.value_owner_treatment_assignment_fixture.v1",
        "authority_scope": "candidate_fixture_only",
        "production_value_eligible": False,
        "profile_content_hash": profile.content_hash,
        "outcome": profile.outcome,
        "measurement_unit": profile.measurement_unit,
        "treated_unit_ids": ["treated"],
        "treatment_period_id": 4,
        "fixture_identification_lower": 2.0,
        "fixture_identification_upper": 2.0,
        "source_ref": "fixture://emp03/synthetic-truth-and-assignment",
    }
    assignment_payload["content_hash"] = gc.gy_content_hash(assignment_payload)
    assignment_ref = _persist_json(
        ir_store,
        assignment_payload,
        kind="runtime.value_owner_treatment_assignment_fixture",
        schema="runtime.value_owner_treatment_assignment_fixture.v1",
    )
    estimand = EstimandSpec(
        query_id="fixture-query-emp03",
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
        "estimand_spec_json": json.dumps(asdict(estimand), sort_keys=True, separators=(",", ":")),
        "seed": 7,
    }
    intent_payload["content_hash"] = gc.gy_content_hash(intent_payload)
    intent = gc.ValueOwnerMethodRunIntentV1.model_validate(intent_payload)

    class CandidateFixtureOwnerGateway:
        def load_value_data_profile(self, **_: Any) -> gc.ValueDataProfile:
            return profile

        def load_value_method_run_intent(self, **_: Any) -> gc.ValueOwnerMethodRunIntentV1:
            return intent

    trust = DataTrust(
        tier="candidate_fixture",
        trust_cap=0.5,
        trust_multiplier=0.5,
        min_coverage=0.0,
        max_coverage=1.0,
        promotion_floor=0.5,
        authority_ref="fixture://candidate-only",
    )
    problem = _avg_income_problem()
    candidate = _avg_income_candidate()
    world_record = _world_record()
    simulation = _simulation(world_record, candidate_id=candidate.candidate_id)
    with controlled_builtin_foundry_method_registry_scope() as (registry, registry_report):
        port = gc.FoundryValuePort(
            evaluation_context=_simulation_execution_context(
                candidate=candidate, simulation=simulation, problem=problem
            ),
            owner_gateway=CandidateFixtureOwnerGateway(),
            requested_method_fqn=SyntheticControlMethod.signature.fqn,
            data_trust=trust,
            artifact_store=store,
            method_registry=registry,
            method_registry_report=registry_report,
        )
        observation = port(
            candidate=candidate, simulation=simulation, problem=problem, cycle_index=0
        )
        assert observation.status == "value_blocked", observation.reason
        assert observation.authority_blockers == ("candidate_fixture_value_run_not_authority",)
        assert observation.value_receipt is None
        assert observation.selected_method_fqn == SyntheticControlMethod.signature.fqn
        basis_ref = observation._candidate_method_run_basis_ref
        outer_ref = observation._candidate_method_value_ref
        assert basis_ref is not None and outer_ref is not None
        assert observation.value_ref == outer_ref.artifact_id

        # Reopen selected objects through a separate CAS reader, then reconcile
        # the stored outer set against the real method/selection consumer.
        fresh_store = ensure_ir_artifact_store(FileSystemCAS(tmp_path / "cas"))
        basis = gc.ValueOwnerMethodRunBasisV2.model_validate(
            gc._value_load_ref_payload(fresh_store, basis_ref)
        )
        stored_assignment = gc.ValueOwnerTreatmentAssignmentFixtureV1.model_validate(
            gc._value_load_ref_payload(fresh_store, basis.assignment_ref)
        )
        report = load_causal_effect_report(
            fresh_store,
            CausalEffectReportRef.model_validate(basis.report_ref.model_dump(mode="json")),
        )
        assert basis.assignment_ref == assignment_ref
        assert stored_assignment.source_ref == "fixture://emp03/synthetic-truth-and-assignment"
        assert not stored_assignment.production_value_eligible
        assert (
            stored_assignment.fixture_identification_lower,
            stored_assignment.fixture_identification_upper,
        ) == (
            2.0,
            2.0,
        )
        assert report.status.value == "success"
        assert report.confidence_level == 0.95
        confidence_default = next(
            parameter.default
            for parameter in SyntheticControlMethod.signature.parameters
            if parameter.name == "confidence_level"
        )
        assert confidence_default == report.confidence_level
        assert report.inference_method == "placebo_permutation"
        assert report.point_estimate == 2.0
        assert report.confidence_interval == (0.0, 10.0)
        assert len(report.placebo_results) == 6
        assert basis.estimand_coordinate == gc._value_estimand_coordinate(estimand)
        consumer_arguments = {
            "store": fresh_store,
            "run_basis_ref": basis_ref,
            "world_record": world_record,
            "data_trust": trust,
            "candidate": candidate,
            "problem": problem,
            "registry": registry,
            "registry_report": registry_report,
            "selection_inputs": port._selection_inputs(),
        }
        recomputed = gc._value_outer_set_from_owner_method_run_basis(**consumer_arguments)
        persisted = _reconcile_selected_outer_set(
            fresh_store, value_ref=outer_ref, run_basis_ref=basis_ref, recomputed=recomputed
        )
        assert persisted.lower == persisted.upper == (2.0,)
        assert persisted.statistical_lower == (report.confidence_interval[0],)
        assert persisted.statistical_upper == (report.confidence_interval[1],)
        assert persisted.coordinates == (basis.estimand_coordinate,)
        assert persisted.representation_status == "search_only"
        assert not persisted.promotion_decision().promotable

        # A report alone is not an owner-run basis, and a foreign estimand
        # coordinate cannot be grafted onto a valid, content-bound basis.
        with pytest.raises(ValueError, match="value_owner_method_artifact_kind_mismatch"):
            gc._value_outer_set_from_owner_method_run_basis(
                **{**consumer_arguments, "run_basis_ref": basis.report_ref}
            )
        foreign_basis_ref = _rebind_basis(
            fresh_store, basis, estimand_coordinate=gc.gy_content_hash({"foreign": "estimand"})
        )
        with pytest.raises(ValueError, match="value_owner_method_estimand_binding_mismatch"):
            gc._value_outer_set_from_owner_method_run_basis(
                **{**consumer_arguments, "run_basis_ref": foreign_basis_ref}
            )

        # The selected physical native report is indispensable to fresh replay.
        report_path = store._member_path(
            ArtifactID.model_validate(basis.report_ref.artifact_id), "blob", None
        )
        report_bytes = report_path.read_bytes()
        report_path.unlink()
        try:
            with pytest.raises(CanonViolation, match="ir_owned_artifact_read_refused") as refusal:
                gc._value_outer_set_from_owner_method_run_basis(**consumer_arguments)
            assert isinstance(refusal.value.__cause__, FileNotFoundError)
        finally:
            report_path.write_bytes(report_bytes)
        assert gc._value_outer_set_from_owner_method_run_basis(**consumer_arguments) == persisted
        record_property(
            "actual_selected_intervals",
            json.dumps(
                {
                    "identification": [persisted.lower[0], persisted.upper[0]],
                    "statistical": list(report.confidence_interval),
                    "confidence_level": report.confidence_level,
                    "outer_artifact_id": outer_ref.artifact_id,
                    "outer_manifest_profile": outer_ref.manifest_profile_sha256,
                    "report_artifact_id": basis.report_ref.artifact_id,
                    "basis_artifact_id": basis_ref.artifact_id,
                },
                sort_keys=True,
                separators=(",", ":"),
            ),
        )
