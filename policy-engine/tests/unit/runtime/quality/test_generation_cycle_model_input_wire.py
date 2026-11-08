from __future__ import annotations

import copy
import hashlib
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import ValidationError

from polisyos.core.artifacts import ArtifactID, ArtifactRef
from polisyos.core.canon import CanonSpec, from_canonical_bytes, to_canonical_bytes
from polisyos.runtime.quality import generation_cycle as generation
from polisyos.runtime.quality.model_input_routing import MODEL_INPUT_ROUTING_REPORT_KIND

_V3_FIXTURE_SHA256 = "dba1d1ff6598ac7c7705e2d46fc085e42e6d1f4651e14ab5c16af57f848ea02c"
_V7 = "policyos.runtime.generation_cycle_controller.v7"
_V8 = "policyos.runtime.generation_cycle_controller.v8"
_V9 = "policyos.runtime.generation_cycle_controller.v9"
_V10 = "policyos.runtime.generation_cycle_controller.v10"


def _v3_fixture() -> tuple[bytes, dict[str, Any]]:
    fixture = Path(__file__).parent / "fixtures" / "generation_cycle_controller_v3.json.fixture"
    raw = fixture.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == _V3_FIXTURE_SHA256
    payload = from_canonical_bytes(raw)
    assert isinstance(payload, dict)
    return raw, payload


def _ref(kind: str, digit: str) -> dict[str, Any]:
    artifact_digest = hashlib.sha256(f"artifact:{digit}".encode()).hexdigest()
    profile_digest = hashlib.sha256(f"profile:{digit}".encode()).hexdigest()
    return ArtifactRef(
        artifact_id=ArtifactID.from_sha256_hex(artifact_digest),
        kind=kind,
        media_type="application/json",
        manifest_profile_sha256="sha256:" + profile_digest,
    ).model_dump(mode="json")


def _routed_payload() -> dict[str, Any]:
    _raw, fixture = _v3_fixture()
    payload = copy.deepcopy(fixture)
    payload["schema_version"] = _V10
    cycle = payload["cycles"][0]
    simulation = cycle["simulation"]
    simulation.update(
        {
            "model_input_obligation_set_ref": _ref(
                "runtime.quality.model_input_obligation_set", "obligation"
            ),
            "generic_n4_source_ref": _ref("runtime.generation_source_handoff", "generic-n4"),
            "generic_context_job_ref": _ref(
                "runtime.quality.cycle_substrate_context_job", "generic-context"
            ),
            "generic_profile_ref": _ref(
                "runtime.quality.generic_cycle_simulation_profile", "generic-profile"
            ),
            "generic_n5_input_ref": _ref(
                "runtime.quality.generic_cycle_simulation_n5_input", "generic-n5-input"
            ),
            "generic_profile_selection_ref": "sha256:"
            + hashlib.sha256(b"generic-profile-selection").hexdigest(),
            "generic_n5_execution_ref": _ref(
                "runtime.quality.generic_cycle_simulation_n5_execution", "generic-n5-execution"
            ),
        }
    )
    cycle["model_input_routing_report_ref"] = _ref(
        MODEL_INPUT_ROUTING_REPORT_KIND, "routing-report"
    )
    return payload


def _transition(run: dict[str, Any]) -> dict[str, Any]:
    transition = generation.CandidateSourceBasisTransition.issue(
        tenant_id="tenant-1",
        cell_id="cell-1",
        run_id=run["run_id"],
        action_job_id="job-1",
        route_id="sha256:" + "1" * 64,
        from_cycle_index=0,
        to_cycle_index=1,
        source_generation_run_content_hash="sha256:" + "2" * 64,
        source_candidate_ref="candidate_same_subject",
        source_candidate_content_hash="sha256:" + "3" * 64,
        target_candidate_content_hash="sha256:" + "4" * 64,
        design_problem_basis_ref="sha256:" + "5" * 64,
        prior_n4_source_ref=generation.CASArtifactRef.model_validate(
            _ref("runtime.quality.n4_candidate_scenario_source", "transition-prior-n4")
        ),
        prior_n5_input_ref=generation.CASArtifactRef.model_validate(
            _ref("runtime.quality.candidate_simulation_n5_input", "transition-prior-n5")
        ),
        prior_context_job_ref=generation.CASArtifactRef.model_validate(
            _ref("runtime.quality.cycle_substrate_context_job", "transition-prior-context")
        ),
        prior_scenario_world_model_hash="sha256:" + "6" * 64,
        candidate_action_ref=generation.CASArtifactRef.model_validate(
            _ref("runtime_quality.acquisition_candidate_action_receipt", "transition-action")
        ),
        candidate_source_ref=generation.CASArtifactRef.model_validate(
            _ref("runtime.quality.candidate_acquisition_source", "transition-source")
        ),
        candidate_world_intent_ref=generation.CASArtifactRef.model_validate(
            _ref("runtime_quality.acquisition_candidate_world_intent", "transition-intent")
        ),
        candidate_world_checkpoint_ref=generation.CASArtifactRef.model_validate(
            _ref("runtime_quality.acquisition_candidate_world_checkpoint", "transition-checkpoint")
        ),
        data_snapshot_ref=generation.CASArtifactRef.model_validate(
            _ref("fabric.data_snapshot", "transition-snapshot")
        ),
        world_model_ref=generation.CASArtifactRef.model_validate(
            _ref("runtime.quality.world_model_record", "transition-world")
        ),
        world_model_content_hash="sha256:" + "7" * 64,
        context_job_ref=generation.CASArtifactRef.model_validate(
            _ref("runtime.quality.cycle_substrate_context_job", "transition-context")
        ),
        scenario_world_model_content_hash="sha256:" + "8" * 64,
        model_declaration_ref=generation.CASArtifactRef.model_validate(
            _ref(
                "runtime.quality.candidate_simulation_model_declaration",
                "transition-model-declaration",
            )
        ),
        ncm_ref=generation.CASArtifactRef.model_validate(
            _ref("ir.ncm_spec", "transition-ncm")
        ),
        limitations=("candidate_only",),
    )
    return transition.model_dump(mode="json")


def _add_n5_attempt(payload: dict[str, Any]) -> None:
    cycle = payload["cycles"][0]
    simulation = generation.SimulationPortObservation.model_validate(cycle["simulation"])
    value = generation.ValuePortObservation.model_validate(cycle["value_port"])
    candidate_id = cycle["selected_candidate_ref"]
    summary = next(
        item
        for item in payload["candidate_summaries"]
        if item["candidate_id"] == candidate_id and item["cycle_index"] == cycle["cycle_index"]
    )
    candidate_hash = summary["content_hash"]
    problem_ref = cycle["design_problem_ref"]
    attempt_ref = generation._candidate_evaluation_attempt_ref(
        candidate_id=candidate_id,
        candidate_content_hash=candidate_hash,
        cycle_index=cycle["cycle_index"],
        problem_ref=problem_ref,
        failure_stage="n5",
        simulation=simulation,
        value=value,
    )
    summary["evaluation_attempt"] = generation.CandidateEvaluationAttempt(
        candidate_id=candidate_id,
        candidate_content_hash=candidate_hash,
        cycle_index=cycle["cycle_index"],
        problem_ref=problem_ref,
        attempt_ref=attempt_ref,
        failure_stage="n5",
        simulation=simulation,
        value=value,
    ).model_dump(mode="json")


def test_model_input_route_uses_v10_and_composes_existing_attempt_and_transition_wires() -> None:
    payload = _routed_payload()
    payload["basis_transitions"] = [_transition(payload)]
    _add_n5_attempt(payload)

    run = generation.GenerationCycleRun.model_validate(payload)
    wire = run.model_dump(mode="json")

    assert run.schema_version == _V10
    assert len(run.basis_transitions) == 1
    assert any(summary.evaluation_attempt is not None for summary in run.candidate_summaries)
    assert wire["cycles"][0]["simulation"]["model_input_obligation_set_ref"]["kind"] == (
        "runtime.quality.model_input_obligation_set"
    )
    assert wire["cycles"][0]["model_input_routing_report_ref"]["kind"] == (
        MODEL_INPUT_ROUTING_REPORT_KIND
    )
    assert generation.GenerationCycleRun.model_validate(wire) == run


@pytest.mark.parametrize("schema_version", [_V7, _V8, _V9])
def test_populated_model_input_route_is_rejected_by_v7_v8_and_v9(
    schema_version: str,
) -> None:
    payload = _routed_payload()
    payload["schema_version"] = schema_version

    with pytest.raises(ValidationError, match="generation_cycle_model_input_routing_requires_v10"):
        generation.GenerationCycleRun.model_validate(payload)


def test_v10_requires_a_complete_populated_pair_and_old_v3_bytes_stay_exact() -> None:
    payload = _routed_payload()
    _raw, empty_v3 = _v3_fixture()
    empty_v3["schema_version"] = _V10
    with pytest.raises(ValidationError, match="generation_cycle_v10_requires_model_input_routing"):
        generation.GenerationCycleRun.model_validate(empty_v3)

    missing_report = copy.deepcopy(payload)
    del missing_report["cycles"][0]["model_input_routing_report_ref"]
    with pytest.raises(ValidationError, match="generation_cycle_v10_model_input_routing_pair_mismatch"):
        generation.GenerationCycleRun.model_validate(missing_report)

    missing_obligation = copy.deepcopy(payload)
    del missing_obligation["cycles"][0]["simulation"]["model_input_obligation_set_ref"]
    with pytest.raises(ValidationError, match="generation_cycle_v10_model_input_routing_pair_mismatch"):
        generation.GenerationCycleRun.model_validate(missing_obligation)

    unversioned = copy.deepcopy(payload)
    unversioned["schema_version"] = _V9
    with pytest.raises(ValidationError, match="generation_cycle_model_input_routing_requires_v10"):
        generation.GenerationCycleRun.model_validate(unversioned)

    raw, v3_payload = _v3_fixture()
    legacy = generation.GenerationCycleRun.model_validate(v3_payload)
    projected = generation._historical_generation_cycle_run_projection(legacy)
    assert to_canonical_bytes(projected, CanonSpec(forbid_floats=False)) == raw

    typed_routed_cycle = generation.GenerationCycleRecord.model_validate(payload["cycles"][0])
    downgraded = legacy.model_copy(
        update={"schema_version": _V7, "cycles": (typed_routed_cycle, *legacy.cycles[1:])}
    )
    with pytest.raises(ValueError, match="generation_cycle_model_input_routing_requires_v10"):
        downgraded.model_dump(mode="json")


def test_run_schema_selection_only_advances_for_populated_model_input_route() -> None:
    _raw, payload = _v3_fixture()
    run = generation.GenerationCycleRun.model_validate(payload)

    assert (
        generation._generation_cycle_run_schema_version(
            cycles=run.cycles,
            candidate_summaries=run.candidate_summaries,
            basis_transitions=(),
        )
        == _V7
    )
    assert (
        generation._generation_cycle_run_schema_version(
            cycles=_routed_payload()["cycles"],
            candidate_summaries=run.candidate_summaries,
            basis_transitions=(),
        )
        == _V10
    )
    attempt_summary = SimpleNamespace(evaluation_attempt=object())
    assert (
        generation._generation_cycle_run_schema_version(
            cycles=run.cycles,
            candidate_summaries=(attempt_summary,),
            basis_transitions=(),
        )
        == _V8
    )
    assert (
        generation._generation_cycle_run_schema_version(
            cycles=run.cycles,
            candidate_summaries=(attempt_summary,),
            basis_transitions=(object(),),
        )
        == _V9
    )
    assert (
        generation._generation_cycle_run_schema_version(
            cycles=_routed_payload()["cycles"],
            candidate_summaries=(attempt_summary,),
            basis_transitions=(object(),),
        )
        == _V10
    )
