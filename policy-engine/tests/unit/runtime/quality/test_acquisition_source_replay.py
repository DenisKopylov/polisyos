"""Reconcile current source/request and complete N7 emission across recorded intake."""

from __future__ import annotations

import hashlib
from copy import deepcopy
from datetime import UTC, datetime

import duckdb
import pytest

from polisyos.core import artifacts
from polisyos.data_forge.read_api import academic
from polisyos.runtime.quality import acquisition_planner as n7
from polisyos.runtime.quality.design_problem import DesignProblem
from polisyos.runtime.quality.production_grounding_calibration import ProductionCG2CalibrationSource
from tests.unit.runtime.quality.test_acquisition_planner import (
    _acquisition_design_problem,
    _owner_payload,
    _substrate_registry,
)


@pytest.fixture
def captured(tmp_path):
    path = tmp_path / "retained.duckdb"
    with duckdb.connect(str(path)) as con:
        con.execute(
            "CREATE TABLE ac_skg_simulation_parameters AS SELECT 'n1' numeric_id, "
            "'W1' openalex_id, 'avg_income' canonical_name, '[]' linked_claim_ids_json, "
            "'[]' linked_edges_json"
        )
    source = academic.SourceSnapshot(
        path=path,
        reference="fixture://source",
        sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
    )
    problem_payload = _acquisition_design_problem().model_dump(mode="json")
    problem_payload["outcome_of_interest"] = {
        "target_variable": "avg_income",
        "metric_id": "avg_income",
        "estimand": "average_treatment_effect",
        "direction": "maximize",
    }
    problem = DesignProblem.model_validate(problem_payload)
    world = n7.AcquisitionWorldSnapshot(
        world_ref="world:current",
        known_slots=("avg_income",),
        substrate_registry=_substrate_registry().model_dump(mode="json"),
    )
    gap = n7.value_input_world_knowledge_requirement_gap(claim_ref="claim:avg_income")
    receipt = n7.run_acquisition_closed_loop(
        run_id="source-live",
        acquisition_request={"cycle_index": 1},
        data_requirement_specs=(gap,),
        world_snapshot=world,
        design_problem=problem,
        owner_gateway=n7.RealAcquisitionOwnerGateway(
            repo_root=tmp_path, skg_source_snapshot=source
        ),
    )
    assert n7.validate_acquisition_receipt(receipt) == ()
    owner = ProductionCG2CalibrationSource(
        source=source,
        store=artifacts.FileSystemCAS(tmp_path / ".n7-live-cas"),
        scratch=tmp_path / ".n7-live-cas" / "source-query-scratch",
    )
    return gap, problem, world, receipt.owner_artifacts[0], owner


def _replay(gap, problem, world, artifact, source_owner):
    return n7.run_acquisition_closed_loop(
        run_id="source-recorded",
        acquisition_request={"cycle_index": 1},
        data_requirement_specs=(gap,),
        world_snapshot=world,
        design_problem=problem,
        owner_gateway=n7.RecordedAcquisitionOwnerGateway(
            artifacts_by_requirement={gap.compiled_requirement_ref: artifact},
            skg_calibration_source=source_owner,
        ),
    )


def _recapture(gap, payload, owner_component="data_forge.skg"):
    record = n7.plan_requirement_gap_acquisition(
        run_id="source-plan", requirement_gaps=(gap,)
    ).acquisition_records[0]
    payload["raw_owner_response_hash"] = n7._stable_content_hash(payload["owner_response"])
    return n7._artifact_from_owner_response(
        owner_component=owner_component,
        owner_endpoint="ProductionCG2CalibrationSource.produce/replay",
        record=record,
        spec=gap.model_dump(mode="json"),
        payload=payload,
        captured_at=datetime(2026, 7, 5, tzinfo=UTC),
        network_call=False,
        cost_usd=0,
    )


def _assert_unverified_refusal(receipt):
    assert all(row.status == "rejected" for row in receipt.world_write_outcomes)
    response = receipt.owner_artifacts[0].payload["owner_response"]
    assert response["owner_response_kind"] == "skg_unverified_source_refusal"
    assert "resolution" not in response
    assert "source_population" not in response["refusal"]
    assert response["refusal"]["verification_status"] == "not_established"
    assert receipt.grown_world_added_slots == ()
    assert receipt.real_grounding_result_count == 0


def test_configured_recorded_source_replay_preserves_verified_audit_without_grounding(captured):
    receipt = _replay(*captured)
    assert n7.validate_acquisition_receipt(receipt) == ()
    assert [row.status for row in receipt.world_write_outcomes] == ["no_result"]
    assert (
        receipt.owner_artifacts[0].payload["owner_response"]["resolution"]["source_population"][
            "row_count"
        ]
        == 1
    )
    assert receipt.real_grounding_result_count == 0


def test_zero_context_recorded_source_is_typed_unverified_without_copied_grades(captured):
    gap, problem, world, artifact, _ = captured
    _assert_unverified_refusal(_replay(gap, problem, world, artifact, None))


@pytest.mark.parametrize("mutation", ["source", "cas"])
def test_same_replayer_and_request_cannot_reuse_old_seal_after_input_drift(captured, mutation):
    gap, problem, world, artifact, owner = captured
    first = _replay(gap, problem, world, artifact, owner)
    artifact = first.owner_artifacts[0]
    if mutation == "source":
        with duckdb.connect(str(owner._source.path)) as con:
            con.execute("UPDATE ac_skg_simulation_parameters SET canonical_name='substituted'")
    else:
        ref = artifacts.ArtifactRef.model_validate(
            artifact.payload["owner_response"]["resolution_ref"]
        )
        blob, _ = owner._store.get_paths(ref.artifact_id)
        blob.write_bytes(b"{}")
    _assert_unverified_refusal(_replay(gap, problem, world, artifact, owner))


@pytest.mark.parametrize("mutation", ["current_world", "current_outcome", "population", "cas_ref"])
def test_recorded_source_requires_complete_current_request_and_population(captured, mutation):
    gap, problem, world, artifact, owner = captured
    if mutation == "current_world":
        world = world.model_copy(update={"world_ref": "world:other-current"})
    elif mutation == "current_outcome":
        payload = problem.model_dump(mode="json")
        payload["outcome_of_interest"]["target_variable"] = "employment_rate"
        payload["outcome_of_interest"]["metric_id"] = "employment_rate"
        problem = DesignProblem.model_validate(payload)
    else:
        payload = deepcopy(artifact.payload)
        if mutation == "population":
            payload["owner_response"]["resolution"]["source_population"]["rows"][0][
                "canonical_name"
            ] = "invented"
        else:
            payload["owner_response"]["resolution_ref"]["artifact_id"] = "sha256:" + "7" * 64
        artifact = _recapture(gap, payload)
    _assert_unverified_refusal(_replay(gap, problem, world, artifact, owner))


@pytest.mark.parametrize("owner_component", ["data_forge.skg", "fabric.ingestion"])
def test_expected_skg_route_cannot_escape_by_relabeling_artifact_owner(captured, owner_component):
    gap, problem, world, artifact, owner = captured
    payload = deepcopy(artifact.payload)
    projection = _owner_payload(
        acquired_family="production_msme_panel",
        source_id="self-issued",
        candidate_id="candidate:forged",
    )
    payload["acquired_substrate_registrations"] = projection["acquired_substrate_registrations"]
    payload["candidate_bindings"] = projection["candidate_bindings"]
    _assert_unverified_refusal(
        _replay(gap, problem, world, _recapture(gap, payload, owner_component), owner)
    )


@pytest.mark.parametrize("mutation", ["world", "grounding", "request", "owner", "candidate"])
def test_complete_receipt_emission_and_actual_cycle_consumer_refuse_forged_bytes(
    captured, mutation
):
    from polisyos.runtime.quality.generation_cycle import _n7_rederived_grounding_for_candidate

    receipt = _replay(*captured)
    payload = receipt.model_dump(mode="json")
    if mutation in {"world", "grounding"}:
        payload["world_write_outcomes"][0].update(
            status="written",
            source_id="self-issued",
            family_id="avg_income",
            world_ref_after="world:self-issued",
            reason=None,
        )
        payload["grown_world_after_ref"] = "world:self-issued"
        payload["grown_world_added_slots"] = ["avg_income"]
        if mutation == "grounding":
            payload["grounding_rederivations"] = [
                {
                    "design_id": "candidate:forged",
                    "source_slots": ["avg_income"],
                    "status": "current_valid",
                    "grounding_score": 1.0,
                    "report_ref": "report:self-issued",
                    "evidence_refs": [],
                    "issue_codes": [],
                }
            ]
            payload["real_grounding_result_count"] = 1
            payload["useful_design_rate_after"] = 1.0
            payload["status"] = "completed"
            payload["no_result_costed_gap"] = False
    elif mutation == "request":
        payload["compiled_requirement_specs"] = []
        payload["compiled_spec_count"] = 0
    elif mutation == "owner":
        payload["owner_artifacts"][0]["owner_component"] = "fabric.ingestion"
    else:
        payload["owner_artifacts"][0]["payload"]["candidate_bindings"] = [
            {"candidate_id": "forged"}
        ]
    payload["content_hash"] = ""
    forged = n7.AcquisitionReceipt.model_validate(payload)
    assert not n7.acquisition_receipt_has_verified_emission(forged)
    assert any(
        issue["code"] == "acquisition_receipt_current_context_replay_unavailable"
        for issue in n7.validate_acquisition_receipt(forged)
    )
    assert _n7_rederived_grounding_for_candidate(forged, candidate_id="candidate:forged") is None


def test_identical_deserialized_receipt_requires_replay_and_nested_mutation_revokes_seal(captured):
    receipt = _replay(*captured)
    decoded = n7.AcquisitionReceipt.model_validate_json(receipt.model_dump_json())
    assert not n7.acquisition_receipt_has_verified_emission(decoded)
    assert n7.acquisition_receipt_has_verified_emission(receipt)
    receipt.owner_artifacts[0].payload["candidate_bindings"].append({"candidate_id": "forged"})
    assert not n7.acquisition_receipt_has_verified_emission(receipt)
