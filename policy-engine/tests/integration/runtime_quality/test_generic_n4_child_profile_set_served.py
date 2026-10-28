from __future__ import annotations

import copy
import hashlib
import json
import os
import shutil
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from tests._helpers.generic_n4_served_replay import (
    _ORIGINAL_SECOND_CAPTURE_CONTENT_HASH,
    _ORIGINAL_SECOND_CAPTURE_RECORDING_ID,
    _assert_original_second_capture_child_semantic_join,
    _assert_original_second_capture_generation_result,
    _original_second_capture_child_group,
    _seed_controlled_selected_skg_source,
    prepare_generic_n4_served_replay,
    run_n4_budget_stop_worker_and_get,
    run_n4_control_worker_and_get,
)

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_candidate_kref_builder_root_guard_rejects_wrong_actual_root_before_builder(
    tmp_path: Path,
) -> None:
    """Reject a wrong actual root while the expected profile markers stay unchanged."""
    from tests._helpers.candidate_cycle_source_profile import (
        bind_candidate_cycle_kref_builder_root,
    )

    selected_root = tmp_path / "selected-fixture-root"
    selected_root.mkdir()
    profile_markers = {
        "source_root": str(selected_root.resolve(strict=True)),
        "profile_id": "candidate-cycle-source-profile-test-only",
        "selected_bundle_sha256": "sha256:" + "a" * 64,
    }
    original_profile_markers = dict(profile_markers)
    actual_builder_calls: list[Path] = []
    observed_repo_roots: list[str] = []

    def sentinel_builder(
        repo_root: Path,
        *args: Any,
        **kwargs: Any,
    ) -> dict[str, str]:
        actual_builder_calls.append(Path(repo_root).resolve(strict=True))
        return dict(profile_markers)

    selected_root_builder = bind_candidate_cycle_kref_builder_root(
        sentinel_builder,
        expected_repo_root=selected_root,
        observed_repo_roots=observed_repo_roots,
    )
    rejected: AssertionError | None = None
    try:
        selected_root_builder(REPO_ROOT)
    except AssertionError as error:
        rejected = error

    assert actual_builder_calls == []
    assert observed_repo_roots == []
    assert rejected is not None
    assert str(rejected) == "candidate_kref_builder_repo_root_mismatch"
    assert profile_markers == original_profile_markers


def _n6_history_rows_from_compiled(compiled: Any) -> list[dict[str, Any]]:
    """Read the complete executed-cycle denominator from persisted compiled bytes."""
    from polisyos.runtime.quality.recursive_generation_cycle import RecursiveCycleNode

    rows: list[dict[str, Any]] = []
    for node in compiled.recursive_run.nodes:
        if not isinstance(node, RecursiveCycleNode) or node.cycle_run is None:
            continue
        for cycle in node.cycle_run.cycles:
            rows.append(
                {
                    "node_ref": node.node_ref,
                    "cycle_index": cycle.cycle_index,
                    "design_problem_ref": cycle.design_problem_ref,
                    "design_problem_basis_ref": cycle.design_problem_basis_ref,
                    "selected_candidate_ref": cycle.selected_candidate_ref,
                    "selected_candidate_content_hash": cycle.selected_candidate_content_hash,
                    "generation_cycle_run_terminal_status": node.cycle_run.terminal_status,
                    "terminal_kind": cycle.terminal_kind,
                    "refinement_decision": cycle.refinement_decision.decision,
                    "search_iteration_status": cycle.search_iteration.status,
                    "grounding_status": cycle.grounding.status,
                    "grounding_current_valid": cycle.grounding.current_valid,
                    "value_status": cycle.value_port.status,
                    "value_decision_grade": cycle.value_port.decision_grade,
                    "value_authority_blockers": list(cycle.value_port.authority_blockers),
                    "value_ref": cycle.value_port.value_ref,
                    "voi_next_action": cycle.voi_decision.next_action,
                }
            )
    return rows


@pytest.fixture
def controlled_candidate_gateway(monkeypatch: pytest.MonkeyPatch):
    """Route the served compiler and N4 calls through the local recording gateway."""
    from tests._helpers.controlled_candidate_profile import ControlledCandidateGateway

    monkeypatch.setenv("POLISYOS_LLM_GATEWAY_BASE_URL", "http://127.0.0.1:1/v1")
    monkeypatch.setenv("POLISYOS_LLM_GATEWAY_API_KEY", "sk-synthetic-local-gateway-key")
    monkeypatch.setenv("POLISYOS_LLM_GATEWAY_MAX_RETRIES", "0")
    monkeypatch.setenv("POLISYOS_LLM_CACHE_TTL_S", "0")
    monkeypatch.setenv("POLISYOS_LLM_CACHE_MAXSIZE", "0")
    monkeypatch.setenv("POLISYOS_LLM_PROMPT_SANITIZER", "false")
    with ControlledCandidateGateway() as gateway:
        monkeypatch.setenv("POLISYOS_LLM_GATEWAY_BASE_URL", gateway.base_url)
        yield gateway


@pytest.mark.asyncio
async def test_recorded_n4_formalizer_uses_source_capture_retry_window(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A local response replay must consume its recorded retry window, not ambient defaults."""
    from polisyos.runtime.quality.design_generation import (
        RecordingLLMClient,
        _n4_multipass_config,
    )
    from polisyos.scientist.agent.formalizer import (
        LLMFormalizerAgent,
        trinity_bundle_formalizer_generator_path,
    )
    from polisyos.scientist.agent.protocols import DraftResult
    from tests._helpers.controlled_candidate_profile import (
        _controlled_procurement_recording,
        _current_compiler_problem,
    )
    from tests._helpers.generic_n4_served_replay import (
        _bind_source_recorded_n4_retry_inputs,
        _three_child_recording,
    )
    from tools.quality.validation import (
        check_layer3_gy_design_generation_contract as n4_contract,
    )

    source = next(
        item
        for item in n4_contract._load_recordings(REPO_ROOT)
        if item.get("recording_id") == _ORIGINAL_SECOND_CAPTURE_RECORDING_ID
    )
    source_problem = _current_compiler_problem(source)
    controlled = _controlled_procurement_recording(
        source,
        outcome_variable=source_problem.outcome_of_interest.target_variable,
    )
    replay = _three_child_recording(
        controlled,
        outcome_variable=source_problem.outcome_of_interest.target_variable,
    )
    monkeypatch.delenv("POLISYOS_DRAFTER_PASS_RETRY_COUNT", raising=False)
    default_drafter_retries = _n4_multipass_config().pass_retry_count
    assert default_drafter_retries == 2
    monkeypatch.setenv("POLISYOS_FORMALIZER_LLM_RETRIES", "2")
    retry_inputs = _bind_source_recorded_n4_retry_inputs(source, monkeypatch)
    assert retry_inputs == {
        "POLISYOS_DRAFTER_PASS_RETRY_COUNT": 3,
        "POLISYOS_FORMALIZER_LLM_RETRIES": 5,
    }
    assert (
        _n4_multipass_config().pass_retry_count == retry_inputs["POLISYOS_DRAFTER_PASS_RETRY_COUNT"]
    )

    malformed_capture = copy.deepcopy(source)
    del malformed_capture["capture_summary"]["effective_runtime_config"]["formalizer_retry_count"]
    env_sentinels = {
        "POLISYOS_DRAFTER_PASS_RETRY_COUNT": "sentinel-drafter-retries",
        "POLISYOS_FORMALIZER_LLM_RETRIES": "sentinel-formalizer-retries",
        "POLISYOS_LLM_GATEWAY_MAX_RETRIES": "sentinel-gateway-retries",
    }
    for name, value in env_sentinels.items():
        monkeypatch.setenv(name, value)
    with pytest.raises(
        ValueError,
        match="controlled_n4_recorded_runtime_config_invalid:formalizer_retry_count",
    ):
        _bind_source_recorded_n4_retry_inputs(malformed_capture, monkeypatch)
    assert {name: os.environ.get(name) for name in env_sentinels} == env_sentinels

    absent_capture = copy.deepcopy(source)
    absent_capture.pop("capture_summary")
    with pytest.raises(
        ValueError,
        match="controlled_n4_recorded_runtime_config_missing",
    ):
        _bind_source_recorded_n4_retry_inputs(absent_capture, monkeypatch)
    assert {name: os.environ.get(name) for name in env_sentinels} == env_sentinels

    model_id = str(replay["model_id"])
    draft = DraftResult(**json.loads(replay["responses"][0]["raw_response"]))
    formalizer_rows = replay["responses"][4:9]

    async def formalize(retry_count: int) -> tuple[str, tuple[Any, ...]]:
        client = RecordingLLMClient(
            n4_contract.RecordedGenerationReplayClient(
                {"model_id": model_id, "responses": copy.deepcopy(formalizer_rows)}
            ),
            model_id=model_id,
        )
        agent = LLMFormalizerAgent(
            client,
            model_name=model_id,
            enable_response_healing=True,
        )
        agent.MAX_RETRIES = retry_count
        bundle = await agent.formalize(draft)
        return (
            trinity_bundle_formalizer_generator_path(bundle, recorded_calls=client.calls),
            tuple(client.calls),
        )

    unbound_path, unbound_calls = await formalize(2)
    assert unbound_path == "path_unrecorded"
    assert len(unbound_calls) == 3
    assert unbound_calls[-1].error_type == "RecordedGatewayError"
    assert unbound_calls[-1].error_status == 502
    bound_path, bound_calls = await formalize(retry_inputs["POLISYOS_FORMALIZER_LLM_RETRIES"])
    assert bound_path == "model_generated"
    assert [call.role_hint for call in bound_calls] == ["formalizer"] * 5
    assert [call.status for call in bound_calls] == [
        "success",
        "success",
        "error",
        "success",
        "success",
    ]
    assert bound_calls[2].model_id == model_id
    assert bound_calls[2].error_status == 502
    assert bound_calls[2].error_message == (
        "Failed LLM gateway call to https://proxy.gonka.gg/v1/chat/completions"
    )


@pytest.fixture
def served_worker_phase_probe(tmp_path: Path) -> Any:
    """Persist payload-free stage timings and bounded all-thread stacks for one worker probe."""
    import faulthandler
    import json
    import threading
    import time
    from datetime import UTC, datetime

    probe_dir = tmp_path / "served-worker-phase-probe"
    probe_dir.mkdir(parents=True, exist_ok=True)
    phase_path = probe_dir / "phases.jsonl"
    stack_path = probe_dir / "thread-stacks.txt"
    phase_stream = phase_path.open("a", encoding="utf-8", buffering=1)
    stack_stream = stack_path.open("a", encoding="utf-8", buffering=1)
    started_ns = time.monotonic_ns()

    def mark(
        stage: str,
        job_id: str | None = None,
        run_id: str | None = None,
    ) -> None:
        now_ns = time.monotonic_ns()
        event = {
            "stage": stage,
            "timestamp_utc": datetime.now(UTC).isoformat(timespec="milliseconds"),
            "monotonic_ns": now_ns,
            "elapsed_ms": (now_ns - started_ns) / 1_000_000,
            "thread_name": threading.current_thread().name,
            "job_id": job_id,
            "run_id": run_id,
        }
        phase_stream.write(json.dumps(event, sort_keys=True) + "\n")
        phase_stream.flush()

    faulthandler.dump_traceback_later(30.0, repeat=True, file=stack_stream)
    mark("probe.started")
    try:
        yield mark
    finally:
        mark("probe.cleanup.start")
        faulthandler.cancel_dump_traceback_later()
        phase_stream.flush()
        stack_stream.flush()
        phase_stream.close()
        stack_stream.close()


@pytest.mark.integration
def test_two_child_recording_lineage_tracks_selected_recorded_source() -> None:
    """Bind each controlled transformation to the selected recorded source."""
    from tests._helpers.controlled_candidate_profile import (
        _controlled_procurement_recording,
        _current_compiler_problem,
    )
    from tests._helpers.generic_n4_served_replay import (
        _RECORDING_ID,
        _two_child_recording,
    )
    from tools.quality.validation import (
        check_layer3_gy_design_generation_contract as n4_contract,
    )

    source_recordings = [
        item
        for item in n4_contract._load_recordings(REPO_ROOT)
        if item.get("design_problem_id") == _RECORDING_ID
    ]
    assert source_recordings
    for source_recording in source_recordings:
        source_problem = _current_compiler_problem(source_recording)
        outcome_variable = source_problem.outcome_of_interest.target_variable
        controlled_overlay = _controlled_procurement_recording(
            source_recording, outcome_variable=outcome_variable
        )
        derived = _two_child_recording(source_recording, outcome_variable=outcome_variable)

        assert controlled_overlay["recording_source"] == (
            "synthetic_controlled_overlay_of_recorded_capture"
        )
        assert controlled_overlay["derived_from_recording_id"] == source_recording["recording_id"]
        assert (
            controlled_overlay["derived_from_content_hash"]
            == source_recording["recording_content_hash"]
        )
        n4_contract._validate_recording_fixture(controlled_overlay)

        assert derived["recording_source"] == "synthetic_two_child_overlay_of_recorded_capture"
        assert derived["recording_id"] != source_recording["recording_id"]
        assert derived["derived_from_recording_id"] == source_recording["recording_id"]
        assert derived["derived_from_content_hash"] == source_recording["recording_content_hash"]
        assert derived["derived_from_recording_id"] != controlled_overlay["recording_id"]
        assert derived["derived_from_content_hash"] != controlled_overlay["recording_content_hash"]
        n4_contract._validate_recording_fixture(derived)


@pytest.mark.integration
def test_original_capture_uses_a_complete_controlled_parent_scope() -> None:
    """Resolve the full controlled parent without claiming the recording had one."""
    from polisyos.ir.kernel import DEFAULT_SLOT_REGISTRY
    from polisyos.pdc import gy_content_hash
    from polisyos.runtime.quality.design_problem import (
        DESIGN_PROBLEM_CURRENT_SCHEMA_VERSION,
    )
    from tests._helpers.controlled_candidate_profile import (
        _current_compiler_problem,
        _resolve_controlled_parent_slot,
    )
    from tests._helpers.generic_n4_served_replay import (
        _ORIGINAL_SECOND_CAPTURE_CONTENT_HASH,
        _ORIGINAL_SECOND_CAPTURE_RECORDING_ID,
    )
    from tools.quality.validation import (
        check_layer3_gy_design_generation_contract as n4_contract,
    )

    recordings = n4_contract._load_recordings(REPO_ROOT)
    matches = [
        row
        for row in recordings
        if row.get("recording_id") == _ORIGINAL_SECOND_CAPTURE_RECORDING_ID
    ]
    assert len(matches) == 1
    recording = matches[0]
    assert recording.get("recording_content_hash") == _ORIGINAL_SECOND_CAPTURE_CONTENT_HASH
    reconstructed = n4_contract._design_problem(recording)
    controlled = _current_compiler_problem(recording)
    scope = controlled.runtime_hints.get("n4_controlled_parent_scope")
    assert isinstance(scope, dict)
    assert scope.get("purpose") == "controlled_test_fixture_only"
    assert scope.get("scope_status") == "declared_controlled_fixture"
    assert scope.get("historical_scope_status") == "not_established"
    assert scope.get("source_recording_id") == _ORIGINAL_SECOND_CAPTURE_RECORDING_ID
    assert scope.get("source_recording_content_hash") == _ORIGINAL_SECOND_CAPTURE_CONTENT_HASH
    scope_ref = scope.get("parent_scope_ref")
    assert isinstance(scope_ref, str) and scope_ref.startswith("sha256:")
    assert controlled.design_problem_id == (
        "controlled_n4_parent_" + scope_ref.removeprefix("sha256:")[:24]
    )
    assert controlled.design_problem_id != recording["design_problem_id"]

    # Independently recompute every field consumed by the scope identity.
    source_levers = tuple(reconstructed.candidate_lever_space.candidate_levers)
    resolved_levers = tuple(
        lever.model_copy(update={"target_slot": _resolve_controlled_parent_slot(lever.target_slot)})
        for lever in source_levers
    )
    expected_constraints = [
        constraint.model_copy(
            update={
                "description": "All proposals remain candidate-only.",
                "source_text": "all proposals remain candidate-only",
            }
        )
        if constraint.constraint_id == "no_authority_without_a"
        else constraint
        for constraint in reconstructed.constraints
    ]
    basis_problem = reconstructed.model_copy(
        update={
            "schema_version": DESIGN_PROBLEM_CURRENT_SCHEMA_VERSION,
            "constraints": expected_constraints,
        }
    )
    expected_resolution_rows = [
        {
            "lever_id": source.lever_id,
            "operator_kind": source.operator_kind,
            "instrument": source.instrument,
            "source_target_slot": source.target_slot,
            "resolved_target_slot": resolved.target_slot,
        }
        for source, resolved in zip(source_levers, resolved_levers, strict=True)
    ]
    expected_scope_basis = {
        "schema_version": "controlled_n4_parent_scope_v1",
        "source_recording_id": _ORIGINAL_SECOND_CAPTURE_RECORDING_ID,
        "source_recording_content_hash": _ORIGINAL_SECOND_CAPTURE_CONTENT_HASH,
        "reconstructed_problem": basis_problem.model_dump(mode="json"),
        "allowed_operator_kinds": list(basis_problem.candidate_lever_space.allowed_operator_kinds),
        "resolved_candidate_levers": [lever.model_dump(mode="json") for lever in resolved_levers],
        "lever_slot_resolutions": expected_resolution_rows,
    }
    expected_scope_ref = gy_content_hash(expected_scope_basis)
    assert scope_ref == expected_scope_ref

    # Mutate one full-basis field while retaining the selected source identity
    # and fixture markers. The identity from the unchanged basis must not match.
    corrupted_scope_basis = copy.deepcopy(expected_scope_basis)
    original_basis_slot = corrupted_scope_basis["resolved_candidate_levers"][0]["target_slot"]
    replacement_basis_slot = next(
        row["resolved_target_slot"]
        for row in expected_resolution_rows
        if row["resolved_target_slot"] != original_basis_slot
    )
    corrupted_scope_basis["resolved_candidate_levers"][0]["target_slot"] = replacement_basis_slot
    corrupted_scope_ref = gy_content_hash(corrupted_scope_basis)
    assert corrupted_scope_ref != scope_ref
    assert controlled.design_problem_id == (
        "controlled_n4_parent_" + scope_ref.removeprefix("sha256:")[:24]
    )
    assert controlled.design_problem_id != (
        "controlled_n4_parent_" + corrupted_scope_ref.removeprefix("sha256:")[:24]
    )

    # Exercise the actual helper with a different, valid synthetic source row.
    mutated_recording = copy.deepcopy(recording)
    mutated_recording["recording_id"] = "controlled_n4_scope_digest_mutation"
    mutated_recording["recording_content_hash"] = gy_content_hash(
        {key: value for key, value in mutated_recording.items() if key != "recording_content_hash"}
    )
    n4_contract._validate_recording_fixture(mutated_recording)
    mutated_controlled = _current_compiler_problem(mutated_recording)
    mutated_scope = mutated_controlled.runtime_hints.get("n4_controlled_parent_scope")
    assert isinstance(mutated_scope, dict)
    assert mutated_scope.get("purpose") == "controlled_test_fixture_only"
    assert mutated_scope.get("scope_status") == "declared_controlled_fixture"
    assert mutated_scope.get("historical_scope_status") == "not_established"
    assert mutated_scope.get("source_recording_id") == mutated_recording["recording_id"]
    assert (
        mutated_scope.get("source_recording_content_hash")
        == mutated_recording["recording_content_hash"]
    )
    assert mutated_scope.get("parent_scope_ref") != scope_ref
    assert mutated_controlled.design_problem_id != controlled.design_problem_id

    # Slot canonicalization changes only the complete declared slot set and the
    # derived controlled-parent identity; every premise and lever remains present.
    for field in (
        "problem_statement",
        "domain",
        "nl_provenance",
        "authority_profile",
        "jurisdiction_time",
        "objectives",
        "stakeholders",
        "outcome_of_interest",
        "evidence_acquisition_needs",
    ):
        assert getattr(controlled, field) == getattr(reconstructed, field)
    assert len(controlled.constraints) == len(reconstructed.constraints) == 1
    assert controlled.constraints[0].constraint_id == reconstructed.constraints[0].constraint_id
    assert controlled.constraints[0].admissibility_basis == (
        reconstructed.constraints[0].admissibility_basis
    )
    assert controlled.constraints[0].description == "All proposals remain candidate-only."
    assert controlled.constraints[0].source_text == "all proposals remain candidate-only"
    before = tuple(reconstructed.candidate_lever_space.candidate_levers)
    after = tuple(controlled.candidate_lever_space.candidate_levers)
    assert len(before) == len(after) == 5
    assert controlled.candidate_lever_space.allowed_operator_kinds == (
        reconstructed.candidate_lever_space.allowed_operator_kinds
    )
    assert tuple(
        (lever.lever_id, lever.operator_kind, lever.instrument) for lever in after
    ) == tuple((lever.lever_id, lever.operator_kind, lever.instrument) for lever in before)
    expected_lever_pairs = {
        ("budget_allocation_multiplier", "government.balance"),
        ("income_tax", "agents.income"),
        ("labor_market", "agents.is_employed"),
        ("procurement_shock_intensity", "cells.distress_score"),
        ("tax_relief_rate", "global.tax_rate"),
    }
    observed_lever_pairs = {(lever.operator_kind, lever.target_slot) for lever in after}
    assert observed_lever_pairs == expected_lever_pairs
    assert all(lever.target_slot in DEFAULT_SLOT_REGISTRY.slots for lever in after)
    expected_resolution_rows = [
        {
            "lever_id": source.lever_id,
            "operator_kind": source.operator_kind,
            "instrument": source.instrument,
            "source_target_slot": source.target_slot,
            "resolved_target_slot": resolved.target_slot,
        }
        for source, resolved in zip(before, after, strict=True)
    ]
    assert scope.get("lever_slot_resolutions") == expected_resolution_rows

    responses = recording.get("responses")
    assert isinstance(responses, list)
    drafts = [
        row.get("parsed")
        for row in responses
        if isinstance(row, dict)
        and row.get("role") == "draft"
        and isinstance(row.get("parsed"), dict)
    ]
    assert len(drafts) == 1
    interventions = drafts[0].get("interventions")
    assert isinstance(interventions, list) and len(interventions) == 3
    recorded_atom_pairs = tuple(
        sorted(
            (
                str(item.get("mechanism_type")),
                str(item.get("parameters", {}).get("target_world_slot")),
            )
            for item in interventions
            if isinstance(item, dict) and isinstance(item.get("parameters"), dict)
        )
    )
    assert recorded_atom_pairs == tuple(
        sorted(
            (
                ("tax_relief_rate", "global.tax_rate"),
                ("procurement_shock_intensity", "cells.distress_score"),
                ("credit_guarantee", "agents.access_to_credit"),
            )
        )
    )
    assert tuple(sorted(set(recorded_atom_pairs) & observed_lever_pairs)) == tuple(
        sorted(
            {
                ("tax_relief_rate", "global.tax_rate"),
                ("procurement_shock_intensity", "cells.distress_score"),
            }
        )
    )
    assert tuple(pair for pair in recorded_atom_pairs if pair not in observed_lever_pairs) == (
        ("credit_guarantee", "agents.access_to_credit"),
    )
    with pytest.raises(
        ValueError,
        match="controlled_n4_parent_slot_alias_not_established",
    ):
        _resolve_controlled_parent_slot("agents.unregistered_controlled_alias")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_original_second_capture_serves_two_meaningful_children_through_fresh_get(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    controlled_candidate_gateway: Any,
    served_worker_phase_probe: Any,
) -> None:
    """Replay the unchanged three-proposal capture through ordinary POST and fresh GET."""
    pytest.importorskip("fastapi.testclient")
    from fastapi.testclient import TestClient

    from polisyos.core.security.tenant_context import tenant_scope
    from polisyos.pdc import gy_content_hash
    from polisyos.runtime.http.app import create_runtime_api_app
    from polisyos.runtime.http.routes.runs import (
        _require_generic_recursive_root_child_denominator,
    )
    from polisyos.runtime.http.services.control import (
        generation_cycle as generation_cycle_service,
    )
    from polisyos.runtime.quality.cycle_substrate import (
        cycle_job_design_problem_ref,
        cycle_job_profile_selection_ref,
        generic_n4_child_profile_selection_ref,
    )
    from polisyos.runtime.quality.design_generation import (
        DesignGenerationError,
        derive_n4_candidate_child_problems,
    )
    from polisyos.runtime.quality.generation_source import GenerationSourceRepository
    from polisyos.runtime.quality.intervention_atom_binding import (
        intervention_atom_content_hash,
    )
    from polisyos.runtime.quality.recursive_generation_cycle import (
        RecursiveCycleNode,
        RecursiveGenerationCycleRun,
    )
    from tests._helpers.candidate_cycle_source_profile import (
        build_candidate_cycle_substrate_route_inputs,
    )
    from tests._helpers.control_worker import dispatch_one_control_job
    from tests.unit.runtime.http.test_nl_pipeline_materialization import (
        _DeterministicSpanSupportClient,
    )
    from tools.quality.validation import (
        check_layer3_gy_design_generation_contract as n4_contract,
    )

    tenant_id = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    cell_id = "cell-v2-original-n4-capture"
    served_worker_phase_probe("fixture_prepare.start")
    source_inputs = build_candidate_cycle_substrate_route_inputs(
        tmp_path / "n4-candidate-source-root"
    )
    prepared = await prepare_generic_n4_served_replay(
        tmp_path=tmp_path,
        controlled_candidate_gateway=controlled_candidate_gateway,
        monkeypatch=monkeypatch,
        tenant_id=tenant_id,
        cell_id=cell_id,
        recording_mode="original_second_capture",
        child_count=2,
        phase_callback=served_worker_phase_probe,
        source_root=source_inputs.root,
    )
    prepared = replace(prepared, request_json={**prepared.request_json, "max_iterations": 1})
    source_witness = prepared.source_root_witness
    assert prepared.source_root == source_inputs.root
    assert prepared.app_kwargs["repo_root"] == source_inputs.root
    assert source_witness["source_root"] == str(source_inputs.root)
    assert source_witness["n4_repo_root"] == str(source_inputs.root)
    assert len(source_witness["selected_l1_dcat_sha256"]) == 64
    assert len(source_witness["selected_l2_source_sha256"]) == 64
    assert source_witness["selected_l2_version_id"] == prepared.selected_skg_version_id
    assert Path(source_witness["selected_l1_dcat_path"]).is_relative_to(source_inputs.root)
    assert Path(source_witness["selected_l2_skg_path"]).is_relative_to(source_inputs.root)
    assert Path(source_witness["selected_l3_lex_path"]).is_relative_to(source_inputs.root)
    assert all(
        Path(source_witness["selected_l6_bundle_paths"][name]).is_relative_to(source_inputs.root)
        for name in (
            "intervention_knob_dictionary",
            "lex_intervention_map",
            "observation_to_contract_manifest",
        )
    )
    assert set(source_witness["selected_l3_row_counts"]) == {
        "lex_amendments",
        "lex_normative_ready_facts",
        "lex_reference_edges",
        "lex_rule_thresholds",
    }
    assert max(source_witness["selected_l3_row_counts"].values(), default=0) < 1000
    assert source_witness["selected_l6_bundle_content_hash"].startswith("sha256:")
    actual_kref = source_witness["actual_kref"]
    assert source_witness["actual_kref_build_repo_roots"]
    assert all(
        root == str(source_inputs.root) for root in source_witness["actual_kref_build_repo_roots"]
    )
    actual_catalog = actual_kref["l1_catalog"]
    assert actual_catalog["selection_owner"] == "catalog_serving_source_paths"
    assert actual_catalog["selection_basis"] == "explicit_path_candidate_only"
    assert actual_catalog["catalog_run_profile"] == "preflight_core"
    assert actual_catalog["source_database_path"] == source_witness["selected_l1_dcat_path"]
    assert actual_catalog["source_database_sha256"] == source_witness["selected_l1_dcat_sha256"]
    assert (
        actual_catalog["alignment_row_count"]
        == source_witness["selected_catalog_readback"]["alignment_row_count"]
    )
    assert (
        actual_catalog["alignment_rows_sha256"]
        == source_witness["selected_catalog_readback"]["alignment_rows_sha256"]
    )
    actual_l6 = actual_kref["l6_intervention"]
    assert actual_l6["actual_reader_witnesses"]
    assert (
        actual_l6["profile_bundle_content_hash"]
        == source_witness["selected_l6_bundle_content_hash"]
    )
    assert all(
        reader["bundle"] == source_witness["selected_l6_source_witness"]
        for reader in actual_l6["actual_reader_witnesses"]
    )
    assert all(
        reader["bundle"]["code_root"] == str(REPO_ROOT.resolve())
        and reader["bundle"]["source_owner_root"] == str(source_inputs.root)
        for reader in actual_l6["actual_reader_witnesses"]
    )
    assert actual_l6["candidate_input_counts"] == {
        "knob_dictionary": 0,
        "lex_intervention_map": 0,
        "observation_routes": 0,
    }
    assert (
        actual_l6["loaded_code_owner_authority"]["source_ref"]
        == (source_witness["selected_l6_source_witness"]["source_refs"]["owner_authority_bindings"])
    )
    assert actual_l6["consumption_status"] == (
        "empty_candidate_data_no_kref_l6_projection_not_established"
    )
    served_worker_phase_probe("fixture_prepare.complete")

    canonical_recording = next(
        item
        for item in n4_contract._load_recordings(REPO_ROOT)
        if item.get("recording_id") == _ORIGINAL_SECOND_CAPTURE_RECORDING_ID
    )
    assert prepared.recording == canonical_recording
    assert prepared.source_recording_id == _ORIGINAL_SECOND_CAPTURE_RECORDING_ID
    assert prepared.source_recording_content_hash == _ORIGINAL_SECOND_CAPTURE_CONTENT_HASH
    assert prepared.recorded_problem.design_problem_id.startswith("controlled_n4_parent_")
    controlled_scope = prepared.recorded_problem.runtime_hints["n4_controlled_parent_scope"]
    assert controlled_scope["historical_scope_status"] == "not_established"
    assert controlled_scope["source_recording_id"] == prepared.source_recording_id
    assert controlled_scope["source_recording_content_hash"] == (
        prepared.source_recording_content_hash
    )
    prepared_problem_snapshot = prepared.recorded_problem.model_dump(mode="json")
    prepared_problem_ref = cycle_job_design_problem_ref(prepared.recorded_problem)

    preflight_result = prepared.organ_run.result
    preflight_candidate_semantics = _assert_original_second_capture_generation_result(
        preflight_result,
        design_problem_ref=prepared_problem_ref,
        recording_id=prepared.source_recording_id,
        recording_content_hash=prepared.source_recording_content_hash,
    )
    expected_child_atom_refs_by_group = _assert_original_second_capture_child_semantic_join(
        prepared.children,
        preflight_candidate_semantics,
    )
    assert preflight_result.status == "generated"
    assert preflight_result.diversity_report.min_required == 3
    assert preflight_result.diversity_report.candidate_count == 3
    assert preflight_result.diversity_report.unique_diversity_key_count == 3
    assert preflight_result.diversity_report.diverse_enough
    assert preflight_result.grounding_disposition_summary.total_candidates == 3
    assert preflight_result.grounding_disposition_summary.shadow_bound == 2
    assert preflight_result.grounding_disposition_summary.abstain_or_blocked == 1
    assert {
        row.proposal_id: row.disposition for row in preflight_result.grounding_dispositions
    } == {
        "gy_n4.industrial_retention_tax_credit": "shadow_bound",
        "gy_n4.procurement_distress_backstop": "shadow_bound",
        "gy_n4.msme_working_capital_guarantee": "unknown_blocked",
    }
    assert len(preflight_result.candidates) == 2

    # Reuse the actual admitted candidates, but test them against a distinct
    # controlled parent that omits exactly their first matching declared lever.
    assert (
        len(
            derive_n4_candidate_child_problems(
                prepared.recorded_problem, preflight_result, model_id=prepared.model_id
            )
        )
        == 2
    )
    selected_candidate = preflight_result.candidates[0]
    selected_operator = selected_candidate.atom.operator_kind.trinity_kind
    if hasattr(selected_operator, "value"):
        selected_operator = selected_operator.value
    selected_targets = set(selected_candidate.atom.target_world_slots)
    matching_parent_levers = tuple(
        lever
        for lever in prepared.recorded_problem.candidate_lever_space.candidate_levers
        if lever.operator_kind == selected_operator and lever.target_slot in selected_targets
    )
    assert matching_parent_levers
    assert {lever.target_slot for lever in matching_parent_levers} == selected_targets
    retained_parent_levers = tuple(
        lever
        for lever in prepared.recorded_problem.candidate_lever_space.candidate_levers
        if lever not in matching_parent_levers
    )
    assert retained_parent_levers
    assert len(retained_parent_levers) + len(matching_parent_levers) == len(
        prepared.recorded_problem.candidate_lever_space.candidate_levers
    )
    original_scope = prepared.recorded_problem.runtime_hints.get("n4_controlled_parent_scope")
    assert isinstance(original_scope, dict)
    assert original_scope.get("historical_scope_status") == "not_established"

    guard_parent_payload = prepared.recorded_problem.model_dump(mode="json")
    guard_parent_payload["candidate_lever_space"] = (
        prepared.recorded_problem.candidate_lever_space.model_copy(
            update={"candidate_levers": retained_parent_levers}
        ).model_dump(mode="json")
    )
    guard_runtime_hints = dict(prepared.recorded_problem.runtime_hints)
    guard_runtime_hints.pop("n4_controlled_parent_scope", None)
    guard_parent_payload["runtime_hints"] = guard_runtime_hints
    guard_parent_payload["design_problem_id"] = "controlled_n4_guard_probe_pending"
    guard_scope_basis_ref = gy_content_hash(
        {
            "schema_version": "controlled_n4_declared_lever_guard_probe_v1",
            "source_recording_id": prepared.source_recording_id,
            "source_recording_content_hash": prepared.source_recording_content_hash,
            "source_parent_scope_ref": original_scope["parent_scope_ref"],
            "omitted_declared_levers": [
                lever.model_dump(mode="json") for lever in matching_parent_levers
            ],
            "parent_without_probe_identity": guard_parent_payload,
        }
    )
    guard_parent_id = (
        "controlled_n4_guard_probe_" + guard_scope_basis_ref.removeprefix("sha256:")[:24]
    )
    guard_scope = dict(original_scope)
    guard_scope.update(
        {
            "parent_problem_id": guard_parent_id,
            "parent_scope_ref": guard_scope_basis_ref,
            "historical_scope_status": "not_established",
            "guard_probe_kind": "single_declared_lever_omission",
        }
    )
    guard_runtime_hints["n4_controlled_parent_scope"] = guard_scope
    guard_parent_payload["design_problem_id"] = guard_parent_id
    guard_parent_payload["runtime_hints"] = guard_runtime_hints
    guard_parent = type(prepared.recorded_problem).model_validate(guard_parent_payload)
    assert guard_parent.candidate_lever_space.allowed_operator_kinds == (
        prepared.recorded_problem.candidate_lever_space.allowed_operator_kinds
    )
    assert len(guard_parent.candidate_lever_space.candidate_levers) == (
        len(prepared.recorded_problem.candidate_lever_space.candidate_levers)
        - len(matching_parent_levers)
    )
    assert (
        guard_parent.runtime_hints["n4_controlled_parent_scope"]["historical_scope_status"]
        == "not_established"
    )
    guard_parent_ref = gy_content_hash(guard_parent.model_dump(mode="json"))

    rebound_candidates = []
    rebound_atoms_by_candidate_id = {}
    for generated_candidate in preflight_result.candidates:
        rebound_atom_basis = generated_candidate.atom.model_copy(
            update={"problem_frame_ref": guard_parent_ref}
        )
        rebound_atom_hash = intervention_atom_content_hash(rebound_atom_basis)
        rebound_atom_payload = generated_candidate.atom.model_dump(mode="python")
        rebound_atom_payload.update(
            {
                "problem_frame_ref": guard_parent_ref,
                "atom_id": "atom_" + rebound_atom_hash.removeprefix("sha256:")[:16],
                "content_hash": rebound_atom_hash,
            }
        )
        rebound_atom = type(generated_candidate.atom).model_validate(rebound_atom_payload)
        rebound_provenance = generated_candidate.provenance.model_copy(
            update={"content_hash": rebound_atom_hash}
        )
        rebound_candidate = generated_candidate.model_copy(
            update={"atom": rebound_atom, "provenance": rebound_provenance}
        )
        rebound_candidates.append(rebound_candidate)
        rebound_atoms_by_candidate_id[rebound_candidate.candidate_id] = rebound_atom

    guard_result_payload = preflight_result.model_dump(mode="python")
    guard_result_payload["design_problem_ref"] = guard_parent_ref
    guard_result_payload["candidates"] = tuple(rebound_candidates)
    for disposition in guard_result_payload["grounding_dispositions"]:
        rebound_atom = rebound_atoms_by_candidate_id.get(disposition.get("candidate_id"))
        if rebound_atom is not None:
            disposition["identified_atom_id"] = rebound_atom.atom_id
            disposition["shadow_atom_content_hash"] = rebound_atom.content_hash
    guard_result = type(preflight_result).model_validate(guard_result_payload)
    assert guard_result.status == "generated"
    assert len(guard_result.candidates) == len(preflight_result.candidates) == 2
    assert {row.candidate_id for row in guard_result.candidates} == {
        row.candidate_id for row in preflight_result.candidates
    }
    assert all(row.atom.problem_frame_ref == guard_parent_ref for row in guard_result.candidates)
    served_worker_phase_probe("n4.declared_lever_guard_negative.start")
    with pytest.raises(DesignGenerationError) as guard_refusal:
        derive_n4_candidate_child_problems(guard_parent, guard_result, model_id=prepared.model_id)
    assert guard_refusal.value.code == "n4_recursive_child_declared_lever_semantics_missing"
    served_worker_phase_probe("n4.declared_lever_guard_negative.complete")

    assert len(prepared.children) == 2
    assert len(prepared.generic_child_profiles) == 2
    expected_profile_node_pairs: dict[str, str] = {}
    expected_node_ref_by_atom_ref: dict[str, str] = {}
    for child in prepared.children:
        group = _original_second_capture_child_group(child)
        source_atom_refs = tuple(sorted(str(ref) for ref in child.source_atom_refs))
        assert expected_child_atom_refs_by_group[group] == source_atom_refs
        node_ref = "design-problem://" + cycle_job_design_problem_ref(child.problem).removeprefix(
            "sha256:"
        )
        profile_selection_ref = generic_n4_child_profile_selection_ref(
            child.problem,
            parent_problem_ref=prepared_problem_ref,
            source_result_ref=child.source_result_ref,
            source_atom_refs=child.source_atom_refs,
            semantic_ref=child.semantic_ref,
        )
        assert profile_selection_ref not in expected_profile_node_pairs
        expected_profile_node_pairs[profile_selection_ref] = node_ref
        for atom_ref in source_atom_refs:
            assert atom_ref not in expected_node_ref_by_atom_ref
            expected_node_ref_by_atom_ref[atom_ref] = node_ref
    assert set(expected_node_ref_by_atom_ref) == {
        semantics[0] for semantics in preflight_candidate_semantics.values()
    }
    expected_child_node_refs = set(expected_profile_node_pairs.values())
    assert len(expected_child_node_refs) == len(expected_profile_node_pairs)
    assert {profile.profile_selection_ref for profile in prepared.generic_child_profiles} == set(
        expected_profile_node_pairs
    )

    original_compiler = generation_cycle_service.build_design_problem_from_nl_request
    compiled_problems: list[Any] = []

    async def run_real_compiler(**kwargs: Any):
        kwargs["span_support_client"] = _DeterministicSpanSupportClient()
        compiled = await original_compiler(**kwargs)
        compiled_problems.append(compiled)
        return compiled

    monkeypatch.setattr(
        generation_cycle_service,
        "build_design_problem_from_nl_request",
        run_real_compiler,
    )
    original_persist_ref = GenerationSourceRepository.persist_ref
    served_parent_results: list[Any] = []

    def observe_persisted_parent_result(repository: Any, **kwargs: Any):
        if cycle_job_design_problem_ref(kwargs["problem"]) == prepared_problem_ref:
            served_parent_results.append(kwargs["organ"].result)
        return original_persist_ref(repository, **kwargs)

    monkeypatch.setattr(
        GenerationSourceRepository,
        "persist_ref",
        observe_persisted_parent_result,
    )
    served_worker_phase_probe("app_create.start")
    app = create_runtime_api_app(**prepared.app_kwargs)
    served_worker_phase_probe("app_create.complete")
    served_worker_phase_probe("testclient_lifespan.start")
    with TestClient(app) as client:
        served_worker_phase_probe("testclient_lifespan.ready")
        assert app.state._control_service._repo_root == source_inputs.root
        served_worker_phase_probe("control_post.start")
        response = client.post(
            "/api/v1/control/runs/nl",
            headers={"Idempotency-Key": uuid.uuid4().hex},
            json=prepared.request_json,
        )
        assert response.status_code == 200, response.text
        accepted = response.json()
        served_worker_phase_probe("control_post.accepted", job_id=str(accepted.get("job_id")))
        assert accepted.get("status") == "accepted"
        service = app.state._control_service
        served_worker_phase_probe("worker_dispatch.start", job_id=str(accepted["job_id"]))
        dispatched = dispatch_one_control_job(
            store=service._control_store,
            handler=service._process_control_job,
            expected_job_id=accepted["job_id"],
        )
        served_worker_phase_probe("worker_dispatch.complete", job_id=str(accepted["job_id"]))
        assert dispatched == accepted["job_id"]
        job = service._control_store.get_job(accepted["job_id"])
        assert job is not None and job.state == "completed"
        with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
            compiled_payload = service._load_payload_ref(
                job.progress["compiled_recursive_generation_cycle_ref"],
                kind="runtime.compiled_recursive_generation_cycle",
            )
        compiled = generation_cycle_service.CompiledRecursiveGenerationCycleRun.model_validate(
            compiled_payload
        )
        run_id = str(job.progress["core_run_id"])
        served_worker_phase_probe(
            "fresh_run_get.start", job_id=str(accepted["job_id"]), run_id=run_id
        )
        get_response = client.get(f"/api/v1/runs/{run_id}")
        served_worker_phase_probe(
            "fresh_run_get.complete", job_id=str(accepted["job_id"]), run_id=run_id
        )
        assert get_response.status_code == 200, get_response.text
        run = get_response.json()["run"]
        projection = run["generic_cycle_simulation"]

        assert len(compiled_problems) == 1
        assert cycle_job_profile_selection_ref(compiled_problems[0]) == (
            prepared.root_profile.profile_selection_ref
        )
        assert len(served_parent_results) == 1
        served_result = served_parent_results[0]
        served_candidate_semantics = _assert_original_second_capture_generation_result(
            served_result,
            design_problem_ref=prepared_problem_ref,
            recording_id=prepared.source_recording_id,
            recording_content_hash=prepared.source_recording_content_hash,
        )
        assert served_candidate_semantics == preflight_candidate_semantics
        assert served_result.status == "generated"
        assert served_result.diversity_report.min_required == 3
        assert served_result.diversity_report.candidate_count == 3
        assert served_result.diversity_report.unique_diversity_key_count == 3
        assert served_result.diversity_report.diverse_enough
        assert served_result.grounding_disposition_summary.total_candidates == 3
        assert served_result.grounding_disposition_summary.shadow_bound == 2
        assert served_result.grounding_disposition_summary.abstain_or_blocked == 1
        assert {
            row.proposal_id: row.disposition for row in served_result.grounding_dispositions
        } == {
            "gy_n4.industrial_retention_tax_credit": "shadow_bound",
            "gy_n4.procurement_distress_backstop": "shadow_bound",
            "gy_n4.msme_working_capital_guarantee": "unknown_blocked",
        }
        assert prepared.recorded_problem.model_dump(mode="json") == prepared_problem_snapshot
        assert prepared.recording == canonical_recording

        assert projection["artifact_status"] == "resolved"
        assert projection["publication_authority"] is False
        assert projection["currentness_status"] == "not_established"
        assert projection["child_profile_status"] == "resolved"
        bindings = projection["child_profile_bindings"]
        assert len(bindings) == 2
        assert {row["profile_selection_ref"] for row in bindings} == set(
            expected_profile_node_pairs
        )
        observed_profile_node_pairs = {
            (row["profile_selection_ref"], row["node_ref"]) for row in bindings
        }
        assert len(observed_profile_node_pairs) == len(bindings)
        assert observed_profile_node_pairs == set(expected_profile_node_pairs.items())
        assert {row["node_ref"] for row in bindings} == expected_child_node_refs
        assert all(row["currentness_status"] == "not_established" for row in bindings)
        observations = [
            row for row in projection["n5_observations"] if row["status"] == "joint_simulated"
        ]
        assert len(observations) == len(expected_child_node_refs)
        assert len({row["node_ref"] for row in observations}) == len(observations)
        assert {row["node_ref"] for row in observations} == expected_child_node_refs
        assert set(expected_node_ref_by_atom_ref.values()) == expected_child_node_refs
        assert all(
            row["simulation_result_ref"]["kind"] == "polisyos.runtime.joint_simulation_result"
            for row in observations
        )
        # A completed recursive run has no partial checkpoint. Prove the two-child
        # result from the persisted, complete compiled tree and its N5 leaf cycles.
        assert projection["recursive_cycle_checkpoint"] is None
        recursive_run = compiled.recursive_run
        assert isinstance(recursive_run, RecursiveGenerationCycleRun)
        assert projection["n6_cycle_history_status"] == "resolved"
        assert projection["n6_cycle_history_limitation_code"] is None
        assert projection["n6_cycle_history"] == _n6_history_rows_from_compiled(compiled)
        assert recursive_run.root_design_problem_ref == prepared_problem_ref
        assert set(recursive_run.recursive_graph.node_refs) == {
            recursive_run.root_node_ref,
            *expected_child_node_refs,
        }
        assert len(recursive_run.nodes) == 1 + len(expected_child_node_refs)
        root_node = next(
            node for node in recursive_run.nodes if node.node_ref == recursive_run.root_node_ref
        )
        assert isinstance(root_node, RecursiveCycleNode)
        assert set(root_node.child_refs) == expected_child_node_refs
        # A graph-shaped complete root cannot replace the source-derived roster.
        with pytest.raises(
            ValueError,
            match="generic_recursive_graph_source_denominator_mismatch",
        ):
            _require_generic_recursive_root_child_denominator(
                nodes=recursive_run.nodes,
                root_node_ref=recursive_run.root_node_ref,
                expected_child_nodes=(expected_child_node_refs - {min(expected_child_node_refs)}),
            )
        leaf_nodes = tuple(recursive_run.leaf_nodes)
        assert {node.node_ref for node in leaf_nodes} == expected_child_node_refs
        assert all(node.cycle_run is not None for node in leaf_nodes)
        assert all(
            node.cycle_run.terminal_status == "completed"
            and len(node.cycle_run.cycles) == 1
            and node.cycle_run.cycles[0].simulation.status == "joint_simulated"
            for node in leaf_nodes
        )
        resolution = compiled.recursive_budget_resolution
        assert resolution is not None
        assert resolution.requested_max_iterations == 1
        assert resolution.effective_max_iterations == 1
        assert resolution.requested_candidate_children == 2
        assert resolution.effective_candidate_children == 2
        assert resolution.child_budget_profile == "n4-source-complete-child-set.v1"
        assert resolution.recursive_budget.max_depth == 1
        assert resolution.recursive_budget.max_nodes == 1 + len(expected_child_node_refs)
        assert resolution.recursive_budget.max_cycles_per_leaf == 1
    served_worker_phase_probe("testclient_lifespan.shutdown.complete")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_served_real_n4_children_keep_first_n5_after_later_sibling_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    controlled_candidate_gateway: Any,
    served_worker_phase_probe: Any,
) -> None:
    """A real N4 source, full child family, first N5 and fresh GET survive sibling failure."""
    pytest.importorskip("fastapi.testclient")
    from fastapi.testclient import TestClient

    from polisyos.core.artifacts import load_core_json_artifact
    from polisyos.core.artifacts.manifest import ArtifactRef
    from polisyos.core.security.tenant_context import tenant_scope
    from polisyos.pdc import gy_content_hash
    from polisyos.runtime.http.app import create_runtime_api_app
    from polisyos.runtime.http.container import RuntimeContainerOverrides
    from polisyos.runtime.http.dependencies import build_runtime_api_context
    from polisyos.runtime.http.services.control import (
        generation_cycle as generation_cycle_service,
    )
    from polisyos.runtime.quality.credal_reference import (
        build_credal_reference,
        credal_reference_l2_source_profile,
    )
    from polisyos.runtime.quality.cycle_substrate import (
        CycleSubstrateContextArtifactOwner,
        CycleSubstrateContextOwnerError,
        cycle_job_design_problem_ref,
        cycle_job_profile_selection_ref,
    )
    from polisyos.runtime.quality.generation_source import GenerationSourceRepository
    from polisyos.runtime.quality.generic_simulation_admission import (
        GenericCycleSimulationAdmissionOwner,
        GenericCycleSimulationN5InputV1,
        parse_generic_cycle_simulation_n5_execution,
    )
    from polisyos.scientist.orchestration.llm import factory as llm_factory
    from tests._helpers.controlled_candidate_profile import (
        _validate_controlled_skg_source,
    )
    from tests.unit.runtime.http.test_nl_pipeline_materialization import (
        _DeterministicSpanSupportClient,
    )

    tenant_id = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    cell_id = "cell-v6-generic-n4"
    served_worker_phase_probe("fixture_prepare.start")
    prepared = await prepare_generic_n4_served_replay(
        tmp_path=tmp_path,
        controlled_candidate_gateway=controlled_candidate_gateway,
        monkeypatch=monkeypatch,
        tenant_id=tenant_id,
        cell_id=cell_id,
        child_count=3,
        phase_callback=served_worker_phase_probe,
    )
    prepared = replace(prepared, request_json={**prepared.request_json, "max_iterations": 1})
    served_worker_phase_probe("fixture_prepare.complete")
    assert prepared.request_json["max_iterations"] == 1
    selected_skg_source = prepared.selected_skg_source
    selected_skg_source_version = str(selected_skg_source.version_id)
    assert selected_skg_source.version_id == prepared.selected_skg_version_id
    assert selected_skg_source.snapshot_ref == prepared.selected_skg_snapshot_ref
    assert prepared.selected_skg_source_checkpoints == (selected_skg_source.sha256,) * 4
    assert selected_skg_source.sha256 == prepared.selected_source_profile.source_snapshot_sha256

    from polisyos.runtime.quality.world_model_record import _parse_skg_snapshot_ref

    wrong_version_ref = replace(
        selected_skg_source,
        version_id=selected_skg_source.version_id + 1,
        snapshot_ref=(
            "duckdb://"
            + selected_skg_source.db_path.as_posix()
            + "#v"
            + str(selected_skg_source.version_id + 1)
        ),
    )
    with pytest.raises(ValueError, match="controlled_selected_skg_source_version_mismatch"):
        _validate_controlled_skg_source(wrong_version_ref)
    assert _validate_controlled_skg_source(selected_skg_source).sha256 == selected_skg_source.sha256

    malformed_seed_root = tmp_path / "malformed-existing-source"
    malformed_db_path = malformed_seed_root / "controlled-candidate-source" / "academic-skg.duckdb"
    malformed_db_path.parent.mkdir(parents=True)
    malformed_db_path.write_bytes(b"existing malformed DuckDB bytes")
    malformed_bytes = malformed_db_path.read_bytes()
    with pytest.raises(ValueError, match="synthetic_academic_skg_seed_target_exists"):
        _seed_controlled_selected_skg_source(
            malformed_seed_root,
            recorded_problem=prepared.recorded_problem,
        )
    assert malformed_db_path.read_bytes() == malformed_bytes

    import duckdb

    changed_copy = tmp_path / "changed-selected-skg.duckdb"
    shutil.copyfile(selected_skg_source.db_path, changed_copy)
    with duckdb.connect(str(changed_copy)) as connection:
        connection.execute(
            "UPDATE ac_skg_edges SET confidence = 0.91 WHERE edge_id = 'tax-balance'"
        )
    changed_copy_ref = (
        "duckdb://" + changed_copy.resolve().as_posix() + "#v" + str(selected_skg_source.version_id)
    )
    changed_source = replace(
        selected_skg_source,
        db_path=changed_copy.resolve(),
        snapshot_ref=changed_copy_ref,
    )
    changed_copy_sha = hashlib.sha256(changed_copy.read_bytes()).hexdigest()
    with pytest.raises(ValueError, match="controlled_selected_skg_source_bytes_mismatch"):
        _validate_controlled_skg_source(changed_source)
    assert hashlib.sha256(changed_copy.read_bytes()).hexdigest() == changed_copy_sha

    assert prepared.recording["recording_source"] == (
        "synthetic_three_child_overlay_of_recorded_capture"
    )
    assert prepared.recording["derived_from_recording_id"] == prepared.source_recording_id
    assert prepared.recording["derived_from_content_hash"] == prepared.source_recording_content_hash
    base_inputs = prepared.base_profile.context_inputs
    organ_run = prepared.organ_run
    selected_reference = prepared.selected_reference
    selected_skg_source_profile = prepared.selected_source_profile
    selected_skg_prior_ref = prepared.selected_source_ref
    generic_child_profiles = prepared.generic_child_profiles
    root_profile = prepared.root_profile
    generic_profiles = prepared.generic_profiles
    child_keys = prepared.child_keys
    generation_result = organ_run.result
    assert generation_result.status == "generated"
    assert generation_result.diversity_report.diverse_enough
    assert len(prepared.children) == 3
    assert len(generic_child_profiles) == 3
    assert len(set(child_keys)) == 3
    assert len({child.semantic_ref for child in prepared.children}) == 3
    assert {child.source_result_ref for child in prepared.children} == {
        gy_content_hash(generation_result.model_dump(mode="json"))
    }
    result_candidate_ids = {candidate.candidate_id for candidate in generation_result.candidates}
    captured_candidate_ids = {source.candidate_id for source in organ_run.candidate_sources}
    assert result_candidate_ids
    assert captured_candidate_ids == result_candidate_ids
    result_atom_refs = {candidate.atom.content_hash for candidate in generation_result.candidates}
    child_source_atom_refs = {
        atom_ref for child in prepared.children for atom_ref in child.source_atom_refs
    }
    assert child_source_atom_refs == result_atom_refs
    assert {profile.profile_selection_ref for profile in generic_child_profiles} == set(child_keys)

    assert selected_skg_source_profile.selection_owner == (
        "world_model_record.skg_causal_prior_ref"
    )
    assert selected_skg_source_profile.skg_causal_prior_ref == selected_skg_prior_ref
    assert selected_skg_prior_ref.skg_snapshot_ref == prepared.selected_skg_snapshot_ref
    assert selected_skg_prior_ref.skg_snapshot_ref == selected_skg_source.snapshot_ref
    assert selected_skg_prior_ref.skg_version_id == str(prepared.selected_skg_version_id)
    assert selected_skg_prior_ref.skg_version_id == selected_skg_source_version
    assert selected_skg_source_profile.source_snapshot_ref == prepared.selected_skg_snapshot_ref
    assert selected_skg_source_profile.source_snapshot_ref == selected_skg_source.snapshot_ref
    assert selected_skg_source_profile.world_model_record_content_hash == (
        base_inputs.world_model_record.content_hash
    )
    assert selected_skg_source_profile.authority_band == "candidate"
    assert selected_skg_source_profile.source_snapshot_authenticity == "not_established"
    assert selected_skg_source_profile.currentness_status == "not_established"
    assert selected_skg_source_profile.source_read_prepared_at_utc.endswith("Z")
    source_path = _parse_skg_snapshot_ref(selected_skg_source_profile.source_snapshot_ref).db_path
    assert source_path.resolve() == prepared.selected_skg_db_path.resolve()
    assert hashlib.sha256(source_path.read_bytes()).hexdigest() == (
        selected_skg_source_profile.source_snapshot_sha256
    )
    from polisyos.pdc._impl.world_model_record import world_model_record_content_hash

    invalid_prior_refs = (
        (
            selected_skg_prior_ref.model_copy(
                update={"skg_version_id": str(int(selected_skg_prior_ref.skg_version_id) + 1)}
            ),
            "credal_reference_skg_wmr_version_mismatch",
        ),
        (
            selected_skg_prior_ref.model_copy(
                update={"skg_snapshot_ref": "lane0://invalid-supplied-source"}
            ),
            "skg_prior_ref_unresolved",
        ),
    )
    for invalid_prior_ref, refusal_code in invalid_prior_refs:
        invalid_world = base_inputs.world_model_record.model_copy(
            update={
                "skg_causal_prior_ref": invalid_prior_ref,
                "content_hash": "sha256:" + "0" * 64,
            }
        )
        invalid_world_hash = world_model_record_content_hash(invalid_world)
        invalid_world = invalid_world.model_copy(
            update={
                "content_hash": invalid_world_hash,
                "world_model_record_id": (
                    "world_model_record_" + invalid_world_hash.removeprefix("sha256:")[:16]
                ),
            }
        )
        with pytest.raises(ValueError, match=refusal_code):
            build_credal_reference(REPO_ROOT, world_model_record=invalid_world)

    for selected_edge_id in ("tax-balance", "distress-output"):
        selected_edge = selected_reference.essential_edges[("L2_CAUSAL_EDGE", selected_edge_id)]
        assert selected_edge.provenance["source"] == "ac_skg_edges"
        assert selected_edge.provenance["version"] == selected_skg_source_version
        assert (
            selected_edge.provenance["selected_source_profile"]["content_hash"]
            == selected_skg_source_profile.content_hash
        )
    assert {
        source.grounding_decision_certificate.reference_hash
        for source in organ_run.candidate_sources
    } == {selected_reference.reference_hash}

    original_compiler = generation_cycle_service.build_design_problem_from_nl_request
    compiled_problems: list[Any] = []

    async def run_real_compiler(**kwargs: Any):
        kwargs["span_support_client"] = _DeterministicSpanSupportClient()
        compiled = await original_compiler(**kwargs)
        compiled_problems.append(compiled)
        return compiled

    monkeypatch.setattr(
        generation_cycle_service,
        "build_design_problem_from_nl_request",
        run_real_compiler,
    )
    gateway_factory = llm_factory.create_traced_gateway_client
    gateway_clients: list[Any] = []

    def observe_gateway(**kwargs: Any):
        client = gateway_factory(**kwargs)
        gateway_clients.append(client)
        return client

    monkeypatch.setattr(llm_factory, "create_traced_gateway_client", observe_gateway)
    failure_code = "v6_controlled_second_n4_child_failure"
    profile_handoff_receipts: list[tuple[str, ArtifactRef, ArtifactRef]] = []
    original_persist_handoff = GenericCycleSimulationAdmissionOwner.persist_handoff

    def persist_handoff_and_replay_profile_ref(owner: Any, **kwargs: Any) -> Any:
        offer = kwargs["offer"]
        assert type(offer.profile_ref) is ArtifactRef
        assert (
            owner.resolve_profile(
                offer.profile_ref,
                expected_profile=offer.profile,
                job_id=kwargs["job_id"],
                run_id=kwargs["run_id"],
                tenant_id=kwargs["tenant_id"],
                cell_id=kwargs["cell_id"],
            )
            == offer.profile
        )
        if offer.profile.profile_selection_kind == "n4_candidate_child":
            assert (
                offer.profile.context_inputs.world_model_record.skg_causal_prior_ref
                == selected_skg_prior_ref
            )
        handoff = original_persist_handoff(owner, **kwargs)
        fresh_reader = GenericCycleSimulationAdmissionOwner(
            profiles=generic_profiles,
            store=owner.store,
        )
        assert fresh_reader is not owner
        assert type(handoff.profile_ref) is ArtifactRef
        assert handoff.profile_ref is offer.profile_ref
        assert (
            fresh_reader.resolve_profile(
                handoff.profile_ref,
                expected_profile=handoff.profile,
                job_id=handoff.job_id,
                run_id=handoff.run_id,
                tenant_id=handoff.tenant_id,
                cell_id=handoff.cell_id,
            )
            == offer.profile
        )
        profile_handoff_receipts.append(
            (offer.profile.profile_id, offer.profile_ref, handoff.profile_ref)
        )
        if offer.profile.profile_selection_kind == "problem":
            wrong_profile = generic_child_profiles[0]
            with pytest.raises(CycleSubstrateContextOwnerError) as refusal:
                fresh_reader.resolve_profile(
                    handoff.profile_ref,
                    expected_profile=wrong_profile,
                    job_id=handoff.job_id,
                    run_id=handoff.run_id,
                    tenant_id=handoff.tenant_id,
                    cell_id=handoff.cell_id,
                )
            assert refusal.value.code in {
                "generic_cycle_simulation_profile_manifest_binding_mismatch",
                "generic_cycle_simulation_profile_content_binding_mismatch",
            }
            family_ref = handoff.n4_child_profile_family_ref
            assert family_ref is not None
            family = fresh_reader.resolve_child_profile_family(
                family_ref,
                parent_handoff=handoff,
                parent_problem=kwargs["problem"],
                verified_nl_job_scope=kwargs["verified_nl_job_scope"],
                context_owner=kwargs["context_owner"],
            )
            assert {member.profile_id for member in family.children} == {
                profile.profile_id for profile in generic_child_profiles
            }
            assert all(
                profile.context_inputs.world_model_record.skg_causal_prior_ref
                == selected_skg_prior_ref
                for profile in generic_child_profiles
            )
        return handoff

    monkeypatch.setattr(
        GenericCycleSimulationAdmissionOwner,
        "persist_handoff",
        persist_handoff_and_replay_profile_ref,
    )
    original_persist_source_ref = GenerationSourceRepository.persist_ref
    served_source_profiles: list[tuple[ArtifactRef | None, Any]] = []

    def persist_source_and_replay_selected_profile(repository: Any, **kwargs: Any):
        source_ref = original_persist_source_ref(repository, **kwargs)
        handoff = repository.load(
            source_ref,
            run_id=kwargs["run_id"],
            expected_run_id=kwargs.get("expected_run_id"),
            expected_job_id=kwargs.get("job_id"),
            expected_tenant_id=kwargs.get("tenant_id"),
            expected_cell_id=kwargs.get("cell_id"),
            context_job_ref=kwargs.get("context_job_ref"),
            profile_ref=kwargs.get("profile_ref"),
            n4_child_profile_family_ref=kwargs.get("n4_child_profile_family_ref"),
        )
        source_profile = credal_reference_l2_source_profile(handoff.reference())
        assert source_profile is not None
        profile_ref = kwargs.get("profile_ref")
        assert profile_ref is None or type(profile_ref) is ArtifactRef
        served_source_profiles.append((profile_ref, source_profile))
        return source_ref

    monkeypatch.setattr(
        GenerationSourceRepository,
        "persist_ref",
        persist_source_and_replay_selected_profile,
    )
    served_worker_phase_probe("app_create.start")
    app = create_runtime_api_app(**prepared.app_kwargs)
    served_worker_phase_probe("app_create.complete")
    served_worker_phase_probe("testclient_lifespan.start")
    with TestClient(app) as client:
        served_worker_phase_probe("testclient_lifespan.ready")
        receipt = await run_n4_control_worker_and_get(
            client=client,
            app=app,
            prepared=prepared,
            monkeypatch=monkeypatch,
            expected_failure_code=failure_code,
            exercise_projection_controls=True,
            phase_callback=served_worker_phase_probe,
        )
        accepted = receipt.accepted_payload
        assert accepted["status"] == "accepted"
        assert receipt.job_state == "completed"
        service = app.state._control_service
        job = service._control_store.get_job(receipt.job_id)
        assert job is not None and job.run_id == receipt.run_id
        with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
            compiled_payload = service._load_payload_ref(
                job.progress["compiled_recursive_generation_cycle_ref"],
                kind="runtime.compiled_recursive_generation_cycle",
            )
        compiled = generation_cycle_service.CompiledRecursiveGenerationCycleRun.model_validate(
            compiled_payload
        )
        from polisyos.scientist.orchestration.engine.budget_ledger import (
            BudgetLedgerProducerRunBinding,
        )

        served_owner = BudgetLedgerProducerRunBinding(
            run_id=receipt.run_id,
            tenant_id=prepared.tenant_id,
            cell_id=prepared.cell_id,
            profile_id=job.effective_execution_profile,
            control_job_id=job.job_id,
        )
        settlement_store = service.llm_producer_settlement_store
        assert settlement_store is not None
        served_events = settlement_store.list_producer_events_for_run_safe(served_owner)
        assert served_events
        assert len({event.event_id for event in served_events}) == len(served_events)
        assert all(event.run_binding == served_owner for event in served_events)
        assert all(
            event.status == "committed"
            and event.amount is not None
            and event.amount >= 0
            and event.cost_origin in {"reported", "estimated", "reuse"}
            for event in served_events
        )
        assert {profile_id for profile_id, _, _ in profile_handoff_receipts} == {
            profile.profile_id for profile in generic_profiles
        }
        assert all(
            offer_ref is handoff_ref for _, offer_ref, handoff_ref in profile_handoff_receipts
        )
        assert len(profile_handoff_receipts) == len(generic_profiles)
        assert len(compiled_problems) == 1
        assert cycle_job_profile_selection_ref(compiled_problems[0]) == (
            root_profile.profile_selection_ref
        )
        assert len(receipt.child_attempt_profile_ids) == 2
        assert len(receipt.successful_child_runs) == 1
        assert len(set(receipt.child_attempt_profile_ids)) == 2
        assert set(receipt.child_attempt_profile_ids).issubset(
            {profile.profile_id for profile in generic_child_profiles}
        )
        assert gateway_clients
        assert served_source_profiles
        expected_profiles_by_ref = {
            str(handoff_ref.artifact_id): next(
                profile for profile in generic_profiles if profile.profile_id == profile_id
            )
            for profile_id, _, handoff_ref in profile_handoff_receipts
        }
        observed_profile_refs = {
            str(profile_ref.artifact_id)
            for profile_ref, _ in served_source_profiles
            if profile_ref is not None
        }
        assert observed_profile_refs == set(expected_profiles_by_ref)
        for profile_ref, source_profile in served_source_profiles:
            if profile_ref is None:
                expected_world = base_inputs.world_model_record
            else:
                expected_profile = expected_profiles_by_ref[str(profile_ref.artifact_id)]
                expected_world = expected_profile.context_inputs.world_model_record
            assert source_profile.world_model_record_content_hash == expected_world.content_hash
            assert source_profile.skg_causal_prior_ref == expected_world.skg_causal_prior_ref
            assert source_profile.skg_causal_prior_ref == selected_skg_prior_ref
            assert source_profile.source_snapshot_ref == selected_skg_source.snapshot_ref
            assert source_profile.source_snapshot_sha256 == selected_skg_source.sha256
            assert source_profile.authority_band == "candidate"
            assert source_profile.source_snapshot_authenticity == "not_established"
        assert _validate_controlled_skg_source(selected_skg_source).sha256 == (
            selected_skg_source_profile.source_snapshot_sha256
        )

        details = receipt.get_payload
        projection = receipt.projection
        assert projection["artifact_status"] == "resolved"
        assert projection["authority_purpose"] == "cycle_input_candidate_only"
        assert projection["publication_authority"] is False
        assert projection["currentness_status"] == "not_established"
        assert projection["child_profile_status"] == "resolved"
        assert projection["child_profile_limitation_code"] is None
        assert len(projection["child_profile_bindings"]) == 3
        assert {
            row["profile_selection_ref"] for row in projection["child_profile_bindings"]
        } == set(child_keys)
        child_profile_rows = {
            row["profile_id"]: row for row in projection["child_profile_bindings"]
        }
        assert set(child_profile_rows) == {profile.profile_id for profile in generic_child_profiles}
        expected_child_node_refs = {
            "design-problem://"
            + cycle_job_design_problem_ref(child.problem).removeprefix("sha256:")
            for child in prepared.children
        }
        assert {row["node_ref"] for row in child_profile_rows.values()} == (
            expected_child_node_refs
        )
        assert all(
            row["currentness_status"] == "not_established"
            for row in projection["child_profile_bindings"]
        )
        successful_observations = [
            row for row in projection["n5_observations"] if row["status"] == "joint_simulated"
        ]
        assert len(successful_observations) == 1
        successful = successful_observations[0]
        # A fresh GET must bind the observed N5 to the actual per-cycle source
        # and owner context. Cycle-zero's selected child handoff is only the
        # initial basis; later cycles may legitimately have a reissued context.
        selected_input_ref = ArtifactRef.model_validate(successful["n5_input_ref"])
        selected_execution_ref = ArtifactRef.model_validate(successful["n5_execution_ref"])
        with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
            selected_input = GenericCycleSimulationN5InputV1.model_validate(
                load_core_json_artifact(prepared.runtime_api_context.store, selected_input_ref)
            )
            selected_execution = parse_generic_cycle_simulation_n5_execution(
                load_core_json_artifact(
                    prepared.runtime_api_context.store,
                    selected_execution_ref,
                )
            )
            selected_source = GenerationSourceRepository(prepared.runtime_api_context.store).load(
                selected_input.n4_source_ref,
                run_id=selected_input.source_run_id,
                expected_run_id=selected_input.run_id,
                expected_job_id=selected_input.job_id,
                expected_tenant_id=selected_input.tenant_id,
                expected_cell_id=selected_input.cell_id,
                context_job_ref=selected_input.context_job_ref,
                profile_ref=selected_input.profile_ref,
                n4_child_profile_family_ref=selected_input.n4_child_profile_family_ref,
            )
            selected_context = CycleSubstrateContextArtifactOwner(
                store=prepared.runtime_api_context.store
            ).resolve_historical_job_artifact(
                selected_input.context_job_ref,
                problem=selected_source.problem,
                expected_job_id=selected_input.job_id,
                expected_run_id=selected_input.run_id,
                expected_tenant_id=selected_input.tenant_id,
                expected_cell_id=selected_input.cell_id,
            )
        matching_cycles = tuple(
            (node, cycle)
            for node in compiled.recursive_run.nodes
            if node.cycle_run is not None
            for cycle in node.cycle_run.cycles
            if cycle.simulation.generic_n5_input_ref == selected_input_ref
        )
        assert len(matching_cycles) == 1
        selected_node, selected_cycle = matching_cycles[0]
        assert selected_cycle.cycle_index == 0
        assert selected_cycle.design_problem_basis_ref == selected_input.design_problem_ref
        selected_initial_child = tuple(
            row
            for row in projection["child_profile_bindings"]
            if row["node_ref"] == selected_node.node_ref
        )
        assert len(selected_initial_child) == 1
        assert selected_input.context_job_ref == ArtifactRef.model_validate(
            selected_initial_child[0]["context_job_ref"]
        )
        initial_problem = next(
            child.problem
            for child in prepared.children
            if "design-problem://"
            + cycle_job_design_problem_ref(child.problem).removeprefix("sha256:")
            == selected_node.node_ref
        )
        assert selected_node.cycle_run is not None
        expected_cycle_problem = (
            initial_problem
            if selected_cycle.cycle_index == 0
            else selected_node.cycle_run.cycles[
                selected_cycle.cycle_index - 1
            ].revision_request.revised_problem
        )
        assert selected_source.problem == expected_cycle_problem
        assert selected_source.cycle_index == selected_input.cycle_index
        assert selected_source.cycle_substrate_context is not None
        assert selected_source.cycle_substrate_context.content_hash == (
            selected_context.context.content_hash
        )
        assert selected_context.problem == selected_source.problem
        assert selected_cycle.simulation.cycle_substrate_context_job_ref == (
            selected_input.context_job_ref
        )
        assert selected_cycle.simulation.generic_context_job_ref == selected_input.context_job_ref
        assert selected_execution.context_job_ref == selected_input.context_job_ref
        assert selected_execution.n4_source_ref == selected_input.n4_source_ref
        assert selected_execution.profile_ref == selected_input.profile_ref
        assert selected_execution.input_ref == selected_input_ref
        assert selected_cycle.simulation.generic_n4_source_ref == selected_input.n4_source_ref
        assert selected_cycle.simulation.generic_n5_execution_ref == selected_execution_ref
        assert successful["simulation_result_ref"]["kind"] == (
            "polisyos.runtime.joint_simulation_result"
        )
        result_body = successful["simulation_result_body"]
        assert successful["simulation_result_body_status"] == "resolved"
        assert successful["simulation_result_body_limitation_code"] is None
        assert result_body["artifact_ref"] == successful["simulation_result_ref"]
        assert result_body["artifact_schema_name"] == (
            "policyos.runtime.n5.joint_simulation_result"
        )
        assert result_body["artifact_schema_version"] == "4.0.0"
        assert (
            result_body["selected_manifest_profile_sha256"]
            == (successful["simulation_result_ref"]["manifest_profile_sha256"])
        )
        assert result_body["result_schema_version"] == (
            "policyos.runtime.joint_simulation_horizon.v4"
        )
        assert result_body["atom_ids"] == successful["atom_ids"]
        assert result_body["selected_outcomes"] == successful["selected_outcomes"]
        assert (
            result_body["world_model_record_content_hash"]
            == (successful["world_model_record_content_hash"])
        )
        assert result_body["trajectories"]
        assert all(
            set(result_body["selected_outcomes"]).issubset(point["outcomes"])
            and set(result_body["selected_outcomes"]).issubset(point["effects"])
            for trajectory in result_body["trajectories"]
            for point in trajectory["points"]
        )
        assert result_body["authority_purpose"] == "cycle_input_candidate_only"
        assert result_body["candidate_status"] == "candidate_unverified"
        assert result_body["publication_authority"] is False
        assert result_body["currentness_status"] == "not_established"
        from pydantic import ValidationError

        from polisyos.core.contracts.runtime import (
            RunGenericCycleSimulationN5Observation,
            RunGenericCycleSimulationN5ResultBody,
        )

        negative_controls = (
            ("artifact_ref", "kind", "runtime.other_result"),
            ("artifact_ref", "media_type", "text/plain"),
            ("artifact_ref", "manifest_profile_sha256", "sha256:" + "8" * 64),
            ("artifact_schema_name", None, "policyos.runtime.other_result"),
            ("artifact_schema_version", None, "3.0.0"),
        )
        for field, nested_field, wrong_value in negative_controls:
            corrupted_body = copy.deepcopy(result_body)
            if nested_field is None:
                corrupted_body[field] = wrong_value
            else:
                corrupted_body[field][nested_field] = wrong_value
            with pytest.raises(ValidationError):
                RunGenericCycleSimulationN5ResultBody.model_validate(corrupted_body)
        unavailable = copy.deepcopy(successful)
        unavailable["simulation_result_body"] = None
        unavailable["simulation_result_body_status"] = "not_established"
        unavailable["simulation_result_body_limitation_code"] = (
            "generic_n5_result_body_content_refused"
        )
        RunGenericCycleSimulationN5Observation.model_validate(unavailable)

        invalid_observations = []
        missing_body_outcome = copy.deepcopy(successful)
        missing_body_outcome["simulation_result_body"] = None
        missing_body_outcome["simulation_result_body_status"] = None
        missing_body_outcome["simulation_result_body_limitation_code"] = None
        invalid_observations.append(missing_body_outcome)
        unrelated_limitation = copy.deepcopy(missing_body_outcome)
        unrelated_limitation["n8_lineage_status"] = "not_established"
        unrelated_limitation["n8_value_ref"] = None
        unrelated_limitation["n8_limitation_code"] = "law_status_unknown"
        invalid_observations.append(unrelated_limitation)
        wrong_result_digest = copy.deepcopy(successful)
        wrong_result_digest["simulation_result_body"]["artifact_ref"]["artifact_id"] = (
            "sha256:" + "f" * 64
        )
        invalid_observations.append(wrong_result_digest)
        body_on_blocked_row = copy.deepcopy(successful)
        body_on_blocked_row["status"] = "simulation_blocked"
        invalid_observations.append(body_on_blocked_row)
        for invalid_observation in invalid_observations:
            with pytest.raises(ValidationError):
                RunGenericCycleSimulationN5Observation.model_validate(invalid_observation)
        assert successful["n5_request_binding_status"] == "resolved"
        assert successful["n5_request_content_hash"].startswith("sha256:")
        assert successful["n8_status"] == "value_conditional"
        assert successful["n8_lineage_status"] == "resolved"
        assert successful["n8_value_ref"] == successful["simulation_result_ref"]["artifact_id"]
        assert successful["child_profile_set_ref"] == projection["child_profile_set_ref"]
        checkpoint = projection["recursive_cycle_checkpoint"]
        assert checkpoint["status"] == "partial"
        assert checkpoint["publication_authority"] is False
        assert checkpoint["budget_stop_node_ref"] is None
        assert checkpoint["failed_branches"]
        assert checkpoint["failed_branches"][0]["error_code"] == failure_code
        assert checkpoint["failed_branches"][0]["stage"] == "leaf_generation"
        assert details["status"] == "fail"
        assert details["finished_at"] is not None
        assert successful["node_ref"] in checkpoint["completed_design_refs"]
        completed_child_refs = set(checkpoint["completed_design_refs"]) & expected_child_node_refs
        failed_child_refs = {
            row["failed_branch_ref"] for row in checkpoint["failed_branches"]
        } & expected_child_node_refs
        pending_child_refs = set(checkpoint["pending_frontier"]) & expected_child_node_refs
        assert len(completed_child_refs) == 1
        assert len(failed_child_refs) == 1
        assert len(pending_child_refs) == 1
        assert completed_child_refs | failed_child_refs | pending_child_refs == (
            expected_child_node_refs
        )
        assert not (completed_child_refs & failed_child_refs)
        assert not (completed_child_refs & pending_child_refs)
        assert not (failed_child_refs & pending_child_refs)
        profile_id_by_child_ref = {
            row["node_ref"]: profile_id for profile_id, row in child_profile_rows.items()
        }
        attempted_child_refs = {
            child_profile_rows[profile_id]["node_ref"]
            for profile_id in receipt.child_attempt_profile_ids
        }
        assert attempted_child_refs == completed_child_refs | failed_child_refs
        assert (
            profile_id_by_child_ref[next(iter(failed_child_refs))]
            == (receipt.child_attempt_profile_ids[-1])
        )
        third_profile_id = generic_child_profiles[2].profile_id
        third_child_ref = child_profile_rows[third_profile_id]["node_ref"]
        assert third_child_ref in pending_child_refs
        assert third_profile_id not in receipt.child_attempt_profile_ids

        assert receipt.n5_result_ref.model_dump(mode="json") == successful["simulation_result_ref"]
        assert receipt.failure_code == failure_code
        assert receipt.failure_message == checkpoint["failed_branches"][0]["error_message"]
        assert receipt.missing_result_ref_error_code == "joint_simulation_result_unavailable"
        assert receipt.corrupt_projection is not None
        assert receipt.incomplete_profile_projection is not None
        assert receipt.corrupt_projection["n5_limitation_code"] == (
            "generic_n5_persisted_lineage_not_established"
        )
        assert receipt.corrupt_projection["recursive_cycle_checkpoint"] == checkpoint
        assert receipt.corrupt_projection["n5_observations"] == []
        assert receipt.incomplete_profile_projection["child_profile_status"] == ("not_established")
        assert receipt.incomplete_profile_projection["child_profile_limitation_code"] == (
            "generic_n4_child_profile_set_reference_not_established"
        )
        assert receipt.incomplete_profile_projection["n5_observations"] == []
        assert receipt.incomplete_profile_projection["recursive_cycle_checkpoint"] == checkpoint

        budget_receipt = await run_n4_budget_stop_worker_and_get(
            client=client,
            app=app,
            prepared=prepared,
            phase_callback=served_worker_phase_probe,
        )
        assert budget_receipt.accepted_payload["status"] == "accepted"
        assert budget_receipt.job_state == "completed"
        job_status = budget_receipt.job_status_payload
        assert job_status["job_id"] == budget_receipt.job_id
        assert job_status["state"] == "completed"
        job_progress = job_status["progress"]
        assert job_progress["recursive_budget_resolution"] == {
            "requested_max_iterations": 1,
            "effective_max_iterations": 1,
            "recursive_budget": {
                "max_depth": 1,
                "max_nodes": 4,
                "min_cycles_per_leaf": 1,
                "max_cycles_per_leaf": 1,
            },
            "clamp_reason": "none",
            "requested_candidate_children": 3,
            "effective_candidate_children": 3,
            "child_budget_profile": "n4-source-complete-child-set.v1",
        }
        assert budget_receipt.projection["child_profile_status"] == "resolved"
        assert budget_receipt.projection["publication_authority"] is False
        assert budget_receipt.projection["currentness_status"] == "not_established"
        assert len(budget_receipt.child_node_refs) == 3
        budget_checkpoint = budget_receipt.checkpoint
        budget_stop_ref = budget_checkpoint["budget_stop_node_ref"]
        assert budget_checkpoint["schema_version"] == (
            "policyos.runtime.recursive_cycle_checkpoint.v1"
        )
        assert budget_checkpoint["status"] == "partial"
        assert budget_checkpoint["publication_authority"] is False
        assert budget_checkpoint["root_n9_status"] == "not_run"
        assert budget_checkpoint["failed_branches"] == []
        assert budget_stop_ref in budget_receipt.child_node_refs
        pending_frontier = set(budget_checkpoint["pending_frontier"])
        assert pending_frontier == set(budget_receipt.child_node_refs) - {budget_stop_ref}
        assert budget_stop_ref in budget_checkpoint["completed_design_refs"]
        assert budget_checkpoint["leaf_terminal_kinds"][budget_stop_ref] == "budget_exhausted"
        served_worker_phase_probe("testclient_lifespan.shutdown.start")
    served_worker_phase_probe("testclient_lifespan.shutdown.complete")

    reopened_context = build_runtime_api_context(
        cas_root=prepared.cas_root,
        core_runs_root=prepared.runtime_api_context.core_runs_root,
    )
    reopened_kwargs = dict(prepared.app_kwargs)
    reopened_kwargs["container_overrides"] = RuntimeContainerOverrides(
        runtime_api_context=reopened_context
    )
    reopened_app = create_runtime_api_app(**reopened_kwargs)
    with TestClient(reopened_app) as reopened_client:
        reopened_response = reopened_client.get(f"/api/v1/runs/{receipt.run_id}")
        assert reopened_response.status_code == 200, reopened_response.text
        reopened_run = reopened_response.json()["run"]
        assert reopened_run["status"] == "fail"
        assert reopened_run["finished_at"] is not None
        reopened_projection = reopened_run["generic_cycle_simulation"]
        reopened_observation = next(
            row
            for row in reopened_projection["n5_observations"]
            if row["status"] == "joint_simulated"
        )
        assert (
            reopened_observation["simulation_result_body"] == (successful["simulation_result_body"])
        )
        assert reopened_projection["recursive_cycle_checkpoint"]["status"] == "partial"
        assert (
            reopened_projection["recursive_cycle_checkpoint"]["failed_branches"][0]["error_code"]
            == failure_code
        )
        assert (
            reopened_projection["recursive_cycle_checkpoint"]["failed_branches"][0]["stage"]
            == "leaf_generation"
        )
        summary_response = reopened_client.get("/api/v1/runs", params={"q": receipt.run_id})
        assert summary_response.status_code == 200, summary_response.text
        matching_summaries = [
            row for row in summary_response.json()["runs"] if row["run_id"] == receipt.run_id
        ]
        assert len(matching_summaries) == 1
        assert matching_summaries[0]["status"] == "fail"
        assert matching_summaries[0]["run_terminality"] == "terminal"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_n6_voi_reconciles_real_gateway_settlements_and_refuses_unknown_costs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    controlled_candidate_gateway: Any,
) -> None:
    """Bind N6 spend to real gateway settlements and keep unknown outcomes distinct."""
    from decimal import Decimal

    from polisyos.runtime.http.services.control.run_lifecycle import (
        _build_control_nl_producer_budget_reconciler,
    )
    from polisyos.runtime.quality.generation_cycle import (
        GenerationCycleController,
        GenerationCycleError,
    )
    from polisyos.scientist.methods.search.voi_scheduler import SimpleVOIScheduler
    from polisyos.scientist.orchestration.engine.budget import BudgetLimit, BudgetState
    from polisyos.scientist.orchestration.engine.budget_ledger import (
        BudgetLedgerProducerRunBinding,
        FileBudgetLedger,
    )
    from polisyos.scientist.orchestration.engine.budget_middleware import (
        BudgetMiddleware,
    )
    from polisyos.scientist.orchestration.llm.factory import (
        create_traced_gateway_client,
    )
    from tests._helpers.controlled_candidate_profile import _current_compiler_problem
    from tools.quality.validation import (
        check_layer3_gy_design_generation_contract as n4_contract,
    )

    recordings_path = REPO_ROOT / (
        "architecture/policy_design_case/layer3_gy_design_generation_replay_recordings.json"
    )
    assert hashlib.sha256(recordings_path.read_bytes()).hexdigest() == (
        "db5f892c19412e74ff78683901dd81e49ebb446f75eb394d254cc75d7c74ae71"
    )
    recordings = n4_contract._load_recordings(REPO_ROOT)
    all_success_id = "gy_n4_replay_20260704_091144_550613_f74107b0bbd2"
    all_success = [row for row in recordings if row.get("recording_id") == all_success_id]
    assert len(all_success) == 1
    source_recording = all_success[0]
    assert source_recording["recording_content_hash"] == (
        "sha256:103e8680d9603db3eca33873669424f9aaf3e3c2342c96bea9975baf750a0eba"
    )
    source_responses = source_recording.get("responses")
    assert isinstance(source_responses, list) and len(source_responses) == 9
    assert all(
        isinstance(row, dict)
        and row.get("status") == "success"
        and isinstance(row.get("usage"), dict)
        and type(row["usage"].get("prompt_tokens")) is int
        and type(row["usage"].get("completion_tokens")) is int
        and row["usage"]["prompt_tokens"] > 0
        and row["usage"]["completion_tokens"] > 0
        for row in source_responses
    )
    from polisyos.core.observability.pricing import estimate_llm_cost_usd

    source_price_estimates = tuple(
        Decimal(
            str(
                estimate_llm_cost_usd(
                    model=str(source_recording["model_id"]),
                    prompt_tokens=row["usage"]["prompt_tokens"],
                    completion_tokens=row["usage"]["completion_tokens"],
                )
            )
        )
        for row in source_responses
    )
    assert len(source_price_estimates) == len(source_responses)
    assert all(amount.is_finite() and amount > Decimal(0) for amount in source_price_estimates)
    controlled_candidate_gateway.set_fixture(
        source_recording,
        problem=_current_compiler_problem(source_recording),
    )
    monkeypatch.setenv("POLISYOS_LLM_CACHE_TTL_S", "60")
    monkeypatch.setenv("POLISYOS_LLM_CACHE_MAXSIZE", "16")

    ledger = FileBudgetLedger(tmp_path / "actual-gateway-ledger.json")
    store = BudgetMiddleware(BudgetState(), ledger=ledger)
    owner = BudgetLedgerProducerRunBinding(
        run_id="n6-real-gateway-owner",
        tenant_id="tenant-candidate",
        cell_id="cell-candidate",
        profile_id="research",
        control_job_id="job-owner",
    )
    sibling = owner.model_copy(
        update={"run_id": "n6-real-gateway-sibling", "control_job_id": "job-sibling"}
    )

    def client_for(binding: BudgetLedgerProducerRunBinding) -> Any:
        client = create_traced_gateway_client(
            model_name=str(source_recording["model_id"]),
            run_id=binding.run_id,
            producer_settlement_store=store,
            producer_budget_key=f"nl-run:{binding.run_id}",
        )
        if client is None:
            raise AssertionError("controlled_gateway_traced_client_unavailable")
        return client

    owner_client = client_for(owner)
    sibling_client = client_for(sibling)
    clients = (owner_client, sibling_client)
    try:
        system = "Return one short candidate diagnostic; do not claim authority."
        user = "Reconcile this controlled recorded gateway response."
        with store.producer_run_binding_scope(owner):
            first = await owner_client.generate(system=system, user=user)
            reused = await owner_client.generate(system=system, user=user)
        with store.producer_run_binding_scope(sibling):
            foreign = await sibling_client.generate(
                system=system,
                user="A distinct sibling run consumes its own recorded response.",
            )

        owner_records = store.list_producer_events_for_run_safe(owner)
        sibling_records = store.list_producer_events_for_run_safe(sibling)
        assert len(owner_records) == 2
        assert len(sibling_records) == 1
        owner_by_id = {record.event_id: record for record in owner_records}
        assert len(owner_by_id) == len(owner_records)
        first_event = first.settlement.event
        reuse_event = reused.settlement.event
        sibling_event = foreign.settlement.event
        provider_record = owner_by_id[first_event.event_id]
        reuse_record = owner_by_id[reuse_event.event_id]
        assert provider_record.status == "committed"
        assert provider_record.cost_origin == "estimated"
        assert provider_record.amount is not None and provider_record.amount > Decimal(0)
        assert provider_record.payload_digest == first_event.payload_digest
        assert provider_record.run_binding == owner
        assert reuse_record.status == "committed"
        assert reuse_record.cost_origin == "reuse"
        assert reuse_record.amount == Decimal(0)
        assert reuse_record.origin_event_id == provider_record.event_id
        assert reuse_record.payload_digest == reuse_event.payload_digest
        assert reuse_record.run_binding == owner
        assert sibling_records[0].event_id == sibling_event.event_id
        sibling_record = sibling_records[0]
        assert sibling_record.run_binding == sibling
        assert sibling_record.status == "committed"
        assert sibling_record.cost_origin == "estimated"
        assert type(sibling_record.amount) is Decimal
        assert sibling_record.amount in set(source_price_estimates)

        expected_amount = source_price_estimates[0]
        assert provider_record.amount == expected_amount
        assert provider_record.amount > Decimal(0)

        def budget_state() -> BudgetState:
            return BudgetState(
                limits={
                    "run": BudgetLimit(
                        key="run",
                        max_usd=provider_record.amount * Decimal("1.5"),
                    )
                }
            )

        def controller(
            current: BudgetState,
            *,
            reconciler: bool,
        ) -> GenerationCycleController:
            callback = (
                _build_control_nl_producer_budget_reconciler(
                    settlement_store=store,
                    producer_run_binding=owner,
                    budget_state=current,
                )
                if reconciler
                else None
            )
            return GenerationCycleController(
                model_id="n6-real-gateway-controller",
                authority_scope="contract_testing",
                voi_scheduler=SimpleVOIScheduler(
                    stage_costs={3: provider_record.amount},
                    min_roi_threshold=0.0,
                ),
                _producer_budget_reconciler=callback,
            )

        reconciled_state = budget_state()
        reconciled = controller(reconciled_state, reconciler=True)
        decision = reconciled._schedule_candidate_for_execution(
            candidate_id="candidate-real-source",
            proxy_score=1.0,
            voi_estimate=1.0,
            budget_state=reconciled_state,
        )
        assert reconciled_state.spent["run"] == provider_record.amount
        assert decision.reason == "budget_exhausted_for_next_level"
        assert decision.recommended_action == "defer"

        # Removing only the reconciler keeps the persisted gateway rows and owner
        # markers but reopens the N6 decision, proving the settlement is consumed.
        unbound_state = budget_state()
        unbound = controller(unbound_state, reconciler=False)
        unbound_decision = unbound._schedule_candidate_for_execution(
            candidate_id="candidate-real-source",
            proxy_score=1.0,
            voi_estimate=1.0,
            budget_state=unbound_state,
        )
        assert unbound_state.spent == {}
        assert unbound_decision.recommended_action == "advance"
        assert unbound_decision.reason != "budget_exhausted_for_next_level"

        original_id = "gy_n4_replay_20260704_095710_425807_7bf5552df372"
        original = [row for row in recordings if row.get("recording_id") == original_id]
        assert len(original) == 1
        original_recording = original[0]
        assert original_recording["recording_content_hash"] == (
            "sha256:107f896fb1fd1c37170b74c88726c07169277d05d3ec5459ceb360919e692cb1"
        )
        original_responses = original_recording.get("responses")
        assert isinstance(original_responses, list) and len(original_responses) == 10
        assert [
            index for index, row in enumerate(original_responses) if row.get("status") == "error"
        ] == [
            2,
            6,
        ]
        controlled_candidate_gateway.set_fixture(
            original_recording,
            problem=_current_compiler_problem(original_recording),
        )
        unknown_outcomes: list[tuple[int, str | None, Decimal | None]] = []
        with store.producer_run_binding_scope(owner):
            for index, row in enumerate(original_responses):
                before = {
                    record.event_id for record in store.list_producer_events_for_run_safe(owner)
                }
                try:
                    response = await owner_client.generate(
                        system=system,
                        user=f"Original selected capture request {index}, fixture-only.",
                    )
                except RuntimeError:
                    if row.get("status") != "error":
                        raise
                else:
                    if row.get("status") != "success":
                        raise AssertionError("original_capture_error_response_was_not_raised")
                    if response.settlement.event.event_id in before:
                        raise AssertionError("original_capture_event_identity_reused")
                after = tuple(store.list_producer_events_for_run_safe(owner))
                added = [record for record in after if record.event_id not in before]
                assert len(added) == 1
                record = added[0]
                if row.get("status") == "error":
                    assert record.status == "unknown"
                    assert record.cost_origin == "unknown"
                    assert record.amount is None
                    unknown_outcomes.append((index, record.event_id, record.amount))
                else:
                    assert record.status == "committed"
                    assert record.cost_origin == "estimated"
                    assert record.amount is not None and record.amount > Decimal(0)
        assert [index for index, _, _ in unknown_outcomes] == [2, 6]
        assert all(event_id and amount is None for _, event_id, amount in unknown_outcomes)

        unknown_state = budget_state()
        unknown_controller = controller(unknown_state, reconciler=True)
        with pytest.raises(
            GenerationCycleError,
            match="control_nl_budget_producer_event_not_settled",
        ):
            unknown_controller._schedule_candidate_for_execution(
                candidate_id="candidate-original-capture",
                proxy_score=1.0,
                voi_estimate=1.0,
                budget_state=unknown_state,
            )
        assert unknown_state.spent == {}
    finally:
        for client in clients:
            close = getattr(client.unwrap(), "aclose", None)
            if callable(close):
                await close()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_actual_n5_writer_removal_keeps_refs_and_fresh_get_limits(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    controlled_candidate_gateway: Any,
    served_worker_phase_probe: Any,
) -> None:
    """Delete N5 bytes at its writer boundary while retaining the persisted run refs."""
    pytest.importorskip("fastapi.testclient")
    from fastapi.testclient import TestClient

    from polisyos.runtime.http.app import create_runtime_api_app
    from polisyos.runtime.http.services.control import (
        generation_cycle as generation_cycle_service,
    )
    from tests._helpers.generic_n4_served_replay import (
        prepare_generic_n4_served_replay,
        run_n4_control_worker_and_get,
    )
    from tests.unit.runtime.http.test_nl_pipeline_materialization import (
        _DeterministicSpanSupportClient,
    )

    served_worker_phase_probe("fixture_prepare.start")
    prepared = await prepare_generic_n4_served_replay(
        tmp_path=tmp_path,
        controlled_candidate_gateway=controlled_candidate_gateway,
        monkeypatch=monkeypatch,
        tenant_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        cell_id="cell-v2-n5-writer-removal",
        recording_mode="original_second_capture",
        child_count=2,
        phase_callback=served_worker_phase_probe,
    )
    prepared = replace(prepared, request_json={**prepared.request_json, "max_iterations": 1})
    served_worker_phase_probe("fixture_prepare.complete")
    original_compiler = generation_cycle_service.build_design_problem_from_nl_request

    async def run_real_compiler(**kwargs: Any):
        kwargs["span_support_client"] = _DeterministicSpanSupportClient()
        return await original_compiler(**kwargs)

    monkeypatch.setattr(
        generation_cycle_service,
        "build_design_problem_from_nl_request",
        run_real_compiler,
    )
    served_worker_phase_probe("app_create.start")
    app = create_runtime_api_app(**prepared.app_kwargs)
    served_worker_phase_probe("app_create.complete")
    served_worker_phase_probe("testclient_lifespan.start")
    with TestClient(app) as client:
        served_worker_phase_probe("testclient_lifespan.ready")
        receipt = await run_n4_control_worker_and_get(
            client=client,
            app=app,
            prepared=prepared,
            monkeypatch=monkeypatch,
            expected_failure_code="v6_controlled_second_n4_child_failure",
            exercise_projection_controls=False,
            remove_n5_writer=True,
            phase_callback=served_worker_phase_probe,
        )
    served_worker_phase_probe("testclient_lifespan.shutdown.complete")

    assert receipt.accepted_payload["status"] == "accepted"
    assert receipt.job_state == "completed"
    assert receipt.successful_observation == {}
    assert receipt.n5_result_ref is not None
    assert receipt.missing_result_ref_error_code == "joint_simulation_result_unavailable"
    assert receipt.projection["child_profile_status"] == "resolved"
    assert receipt.projection["n5_observations"] == []
    assert receipt.projection["n5_limitation_code"] == (
        "generic_n5_persisted_lineage_not_established"
    )
    assert receipt.checkpoint["status"] == "partial"
    assert receipt.actual_sibling_failure["error_code"] == ("v6_controlled_second_n4_child_failure")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_served_n6_uses_later_real_n4_spend_and_keeps_first_n5(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    controlled_candidate_gateway: Any,
    served_worker_phase_probe: Any,
) -> None:
    """Reconcile real N4 settlements before a budget terminal and fresh GET."""
    pytest.importorskip("fastapi.testclient")
    from decimal import Decimal

    from fastapi.testclient import TestClient

    from polisyos.core.artifacts.canonical_profile import read_core_json_artifact
    from polisyos.core.artifacts.ids import ArtifactID
    from polisyos.core.artifacts.manifest import ArtifactRef
    from polisyos.core.observability.pricing import estimate_llm_cost_usd
    from polisyos.core.security.tenant_context import tenant_scope
    from polisyos.runtime.http.app import create_runtime_api_app
    from polisyos.runtime.http.container import RuntimeContainerOverrides
    from polisyos.runtime.http.dependencies import build_runtime_api_context
    from polisyos.runtime.http.services.control.generation_cycle import (
        CompiledRecursiveGenerationCycleRun,
    )
    from polisyos.runtime.quality.generation_cycle import GenerationCycleController
    from polisyos.runtime.quality.recursive_generation_cycle import (
        RecursiveCyclePendingNode,
    )
    from polisyos.scientist.orchestration.engine.budget_ledger import (
        BudgetLedgerProducerRunBinding,
    )
    from tools.quality.validation import (
        check_layer3_gy_design_generation_contract as n4_contract,
    )

    recordings_path = REPO_ROOT / (
        "architecture/policy_design_case/layer3_gy_design_generation_replay_recordings.json"
    )
    assert hashlib.sha256(recordings_path.read_bytes()).hexdigest() == (
        "db5f892c19412e74ff78683901dd81e49ebb446f75eb394d254cc75d7c74ae71"
    )
    recordings = n4_contract._load_recordings(REPO_ROOT)
    recording_id = "gy_n4_replay_20260704_091144_550613_f74107b0bbd2"
    problem_id = "gy_n4_cgf_decisive_capture_1_20260704_085428_165363"
    source_rows = [row for row in recordings if row.get("recording_id") == recording_id]
    assert len(source_rows) == 1
    source = source_rows[0]
    assert source.get("design_problem_id") == problem_id
    assert source.get("recording_content_hash") == (
        "sha256:103e8680d9603db3eca33873669424f9aaf3e3c2342c96bea9975baf750a0eba"
    )
    responses = source.get("responses")
    assert isinstance(responses, list) and len(responses) == 9
    assert all(
        isinstance(row, dict)
        and row.get("status") == "success"
        and isinstance(row.get("usage"), dict)
        and type(row["usage"].get("prompt_tokens")) is int
        and type(row["usage"].get("completion_tokens")) is int
        and row["usage"]["prompt_tokens"] > 0
        and row["usage"]["completion_tokens"] > 0
        for row in responses
    )
    model = str(source["model_id"])
    source_prices = tuple(
        Decimal(
            str(
                estimate_llm_cost_usd(
                    model=model,
                    prompt_tokens=row["usage"]["prompt_tokens"],
                    completion_tokens=row["usage"]["completion_tokens"],
                )
            )
        )
        for row in responses
    )
    assert len(source_prices) == len(responses)
    assert all(price.is_finite() and price > Decimal(0) for price in source_prices)

    tenant_id = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    cell_id = "cell-v7-n6-real-spend-after-n5"
    served_worker_phase_probe("fixture_prepare.start")
    prepared = await prepare_generic_n4_served_replay(
        tmp_path=tmp_path,
        controlled_candidate_gateway=controlled_candidate_gateway,
        monkeypatch=monkeypatch,
        tenant_id=tenant_id,
        cell_id=cell_id,
        recording_id=problem_id,
        child_count=3,
        phase_callback=served_worker_phase_probe,
    )
    prepared = replace(prepared, request_json={**prepared.request_json, "max_iterations": 1})
    served_worker_phase_probe("fixture_prepare.complete")
    assert prepared.source_recording_id == recording_id
    assert prepared.source_recording_content_hash == source["recording_content_hash"]
    assert prepared.recording["recording_source"] == (
        "synthetic_three_child_overlay_of_recorded_capture"
    )
    assert prepared.recording["derived_from_recording_id"] == recording_id
    assert prepared.recording["derived_from_content_hash"] == source["recording_content_hash"]
    assert [row["usage"] for row in prepared.recording["responses"]] == [
        row["usage"] for row in responses
    ]
    assert prepared.model_id == model and prepared.request_json["llm_model"] == model
    n4_call_count = len(prepared.organ_run.result.llm_calls)
    assert n4_call_count == len(responses)
    one_n4_cost = sum(source_prices[:n4_call_count], Decimal(0))
    preflight_cost = Decimal(
        str(
            estimate_llm_cost_usd(
                model=prepared.request_json["llm_model"],
                prompt_tokens=1,
                completion_tokens=1,
            )
        )
    )
    scheduler = GenerationCycleController(
        model_id=prepared.model_id,
        authority_scope="contract_testing",
    )._voi_scheduler
    stage_three_cost = scheduler._estimated_cost_decimal(3)
    assert preflight_cost.is_finite() and preflight_cost >= Decimal(0)
    assert stage_three_cost.is_finite() and stage_three_cost > Decimal(0)
    selected_budget = (
        preflight_cost + one_n4_cost + stage_three_cost + min(source_prices) / Decimal(4)
    )
    run_budget_usd = float(selected_budget)
    budget_limit = Decimal(str(run_budget_usd))
    assert preflight_cost + one_n4_cost + stage_three_cost < budget_limit
    assert budget_limit < preflight_cost + Decimal(2) * one_n4_cost

    app = create_runtime_api_app(**prepared.app_kwargs)
    with TestClient(app) as client:
        receipt = await run_n4_budget_stop_worker_and_get(
            client=client,
            app=app,
            prepared=prepared,
            run_budget_usd=run_budget_usd,
            phase_callback=served_worker_phase_probe,
        )
        assert receipt.accepted_payload["status"] == "accepted"
        assert receipt.job_state == "completed"
        assert receipt.run_id == receipt.get_payload["run"]["run_id"]
        assert receipt.projection["child_profile_status"] == "resolved"
        assert receipt.projection["publication_authority"] is False
        assert receipt.projection["currentness_status"] == "not_established"
        assert len(receipt.child_node_refs) == 3
        checkpoint = receipt.checkpoint
        assert checkpoint["status"] == "partial"
        assert checkpoint["publication_authority"] is False
        assert checkpoint["root_n9_status"] == "not_run"
        assert checkpoint["failed_branches"] == []
        child_refs = set(receipt.child_node_refs)
        stop_ref = checkpoint["budget_stop_node_ref"]
        assert stop_ref in child_refs
        assert checkpoint["leaf_terminal_kinds"][stop_ref] == "budget_exhausted"
        successful_n5 = [
            row
            for row in receipt.projection["n5_observations"]
            if row["status"] == "joint_simulated"
        ]
        assert len(successful_n5) == 1
        assert successful_n5[0]["simulation_result_body_status"] == "resolved"
        assert (
            successful_n5[0]["simulation_result_body"]["artifact_ref"]
            == (successful_n5[0]["simulation_result_ref"])
        )
        assert successful_n5[0]["simulation_result_body"]["publication_authority"] is False
        first_n5_ref = successful_n5[0]["node_ref"]
        assert first_n5_ref in child_refs and first_n5_ref != stop_ref
        completed_children = set(checkpoint["completed_design_refs"]) & child_refs
        pending_children = set(checkpoint["pending_frontier"]) & child_refs
        assert completed_children == {first_n5_ref, stop_ref}
        assert pending_children == child_refs - completed_children
        assert len(pending_children) == 1

        service = app.state._control_service
        job = service._control_store.get_job(receipt.job_id)
        assert job is not None and job.state == "completed" and job.payload_ref is not None
        with tenant_scope(None, tenant_id=prepared.tenant_id, cell_id=prepared.cell_id):
            job_payload = service._load_payload_ref(
                job.payload_ref, kind=f"runtime.control_job_payload.{job.kind}"
            )
            assert job_payload["run_budget_usd"] == run_budget_usd
            assert job_payload["max_iterations"] == 1
            compiled_payload = service._load_payload_ref(
                job.progress["compiled_recursive_generation_cycle_ref"],
                kind="runtime.compiled_recursive_generation_cycle",
            )
        compiled = CompiledRecursiveGenerationCycleRun.model_validate(compiled_payload)
        root_node = next(
            node
            for node in compiled.recursive_run.nodes
            if node.node_ref == compiled.recursive_run.root_node_ref
        )
        assert isinstance(root_node, RecursiveCyclePendingNode)
        assert set(root_node.child_refs) == child_refs
        assert len(compiled.nl_preflight_cost_events) == 1
        preflight_event = compiled.nl_preflight_cost_events[0]
        assert preflight_event.model == prepared.request_json["llm_model"]
        assert preflight_event.amount == preflight_cost
        assert preflight_event.cost_origin == "estimated"
        assert preflight_event.settlement_status == "committed"
        assert preflight_event.durability == "ledger"
        n4_events = tuple(compiled.n4_generation_cost_events)
        assert len(n4_events) == 2 * n4_call_count
        n4_amounts = tuple(sorted(event.amount for event in n4_events if event.amount is not None))
        assert len(n4_amounts) == len(n4_events)
        assert n4_amounts == tuple(sorted(source_prices * 2))
        assert all(
            event.cost_origin == "estimated"
            and event.settlement_status == "committed"
            and event.durability == "ledger"
            for event in n4_events
        )
        owner = BudgetLedgerProducerRunBinding(
            run_id=receipt.run_id,
            tenant_id=prepared.tenant_id,
            cell_id=prepared.cell_id,
            profile_id=job.effective_execution_profile,
            control_job_id=job.job_id,
        )
        records = service.llm_producer_settlement_store.list_producer_events_for_run_safe(owner)
        compiled_events = (preflight_event, *n4_events)
        compiled_ids = [event.event_id for event in compiled_events]
        records_by_id = {record.event_id: record for record in records}
        assert len(compiled_ids) == len(set(compiled_ids))
        assert len(records_by_id) == len(records)
        assert set(compiled_ids) == set(records_by_id)
        assert len(records) == 1 + (2 * n4_call_count)
        for event in compiled_events:
            record = records_by_id[event.event_id]
            assert record.run_binding == owner
            assert record.status == "committed"
            assert record.cost_origin == event.cost_origin
            assert record.amount == event.amount
        assert all(record.amount is not None for record in records)
        actual_spend = sum(
            (record.amount for record in records if record.amount is not None),
            Decimal(0),
        )
        assert actual_spend == preflight_cost + Decimal(2) * one_n4_cost
        assert actual_spend > budget_limit
        resolution = receipt.job_status_payload["progress"]["recursive_budget_resolution"]
        assert resolution["requested_max_iterations"] == 1
        assert resolution["effective_max_iterations"] == 1
        assert resolution["requested_candidate_children"] == 3
        assert resolution["effective_candidate_children"] == 3
        assert resolution["recursive_budget"]["max_nodes"] == 4
        original_run = receipt.get_payload["run"]
        original_projection = receipt.projection
        selected_result_ref = ArtifactRef.model_validate(successful_n5[0]["simulation_result_ref"])
    served_worker_phase_probe("testclient_lifespan.shutdown.complete")

    # Reopen a distinct API context over the actual saved run and selected CAS,
    # then compare it to the typed persisted source rather than a supplied graph.
    assert prepared.cas_root.resolve(strict=True).is_relative_to(tmp_path.resolve(strict=True))
    reopened_context = build_runtime_api_context(
        cas_root=prepared.cas_root,
        core_runs_root=prepared.runtime_api_context.core_runs_root,
    )
    assert reopened_context is not prepared.runtime_api_context
    indexed = reopened_context.run_index.get_run(receipt.run_id)
    assert indexed is not None
    compiled_refs = tuple(
        ref
        for ref in indexed.details.root_artifacts
        if ref.kind == "runtime.compiled_recursive_generation_cycle"
    )
    assert len(compiled_refs) == 1
    assert (
        str(compiled_refs[0].artifact_id) == job.progress["compiled_recursive_generation_cycle_ref"]
    )
    # Bind the full selected view published by the actual job, not only its bytes.
    assert compiled_refs[0] == ArtifactRef.model_validate(
        job.progress["compiled_recursive_generation_cycle_artifact_ref"]
    )
    assert compiled_refs[0].manifest_profile_sha256 is not None
    with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
        assert reopened_context.store.verify(compiled_refs[0]).ok
        reopened_payload = read_core_json_artifact(reopened_context.store, compiled_refs[0]).value
        assert reopened_context.store.verify(selected_result_ref).ok
        result_path, _manifest_path = reopened_context.store._paths(
            ArtifactID.model_validate(selected_result_ref.artifact_id)
        )
    reopened_compiled = CompiledRecursiveGenerationCycleRun.model_validate(reopened_payload)
    assert reopened_compiled.model_dump(mode="json") == compiled.model_dump(mode="json")
    expected_history = _n6_history_rows_from_compiled(reopened_compiled)
    assert {first_n5_ref, stop_ref} <= {row["node_ref"] for row in expected_history}
    assert pending_children.isdisjoint({row["node_ref"] for row in expected_history})
    assert not result_path.is_symlink()
    assert result_path.resolve(strict=True).is_relative_to(prepared.cas_root.resolve(strict=True))
    original_result_bytes = result_path.read_bytes()
    assert "sha256:" + hashlib.sha256(original_result_bytes).hexdigest() == str(
        selected_result_ref.artifact_id
    )

    reopened_kwargs = dict(prepared.app_kwargs)
    reopened_kwargs["container_overrides"] = RuntimeContainerOverrides(
        runtime_api_context=reopened_context
    )
    reopened_app = create_runtime_api_app(**reopened_kwargs)
    served_worker_phase_probe("budget.reopened_client.start", run_id=receipt.run_id)
    with TestClient(reopened_app) as reopened_client:

        def get_projection() -> tuple[dict[str, Any], dict[str, Any]]:
            response = reopened_client.get(f"/api/v1/runs/{receipt.run_id}")
            assert response.status_code == 200, response.text
            reopened_run = response.json()["run"]
            return reopened_run, reopened_run["generic_cycle_simulation"]

        reopened_run, reopened_projection = get_projection()
        assert reopened_run["status"] == original_run["status"]
        assert reopened_run["finished_at"] == original_run["finished_at"]
        assert (
            reopened_projection["child_profile_bindings"]
            == (original_projection["child_profile_bindings"])
        )
        assert reopened_projection["recursive_cycle_checkpoint"] == checkpoint
        assert reopened_projection["n5_observations"] == original_projection["n5_observations"]
        assert reopened_projection["n6_cycle_history_status"] == "resolved"
        assert reopened_projection["n6_cycle_history"] == expected_history
        assert reopened_projection["publication_authority"] is False
        assert reopened_projection["currentness_status"] == "not_established"

        # Keep the already-persisted checkpoint/reference markers in place.
        # Both corrupt and missing N5 bytes must suppress that result; restoring
        # the exact bytes must recover the same selected observation each time.
        for removal_kind in ("corrupt", "missing"):
            try:
                if removal_kind == "corrupt":
                    result_path.write_bytes(b"controlled-corrupt-budget-result")
                else:
                    result_path.unlink()
                _, limited_projection = get_projection()
                assert limited_projection["recursive_cycle_checkpoint"] == checkpoint
                assert limited_projection["child_profile_status"] == "resolved"
                assert limited_projection["n5_limitation_code"] == (
                    "generic_n5_persisted_lineage_not_established"
                )
                assert all(
                    row["simulation_result_ref"] != successful_n5[0]["simulation_result_ref"]
                    for row in limited_projection["n5_observations"]
                )
            finally:
                result_path.write_bytes(original_result_bytes)
            assert result_path.read_bytes() == original_result_bytes
            _, restored_projection = get_projection()
            assert restored_projection["recursive_cycle_checkpoint"] == checkpoint
            assert restored_projection["n5_observations"] == original_projection["n5_observations"]
            assert restored_projection["n6_cycle_history"] == expected_history
    served_worker_phase_probe("budget.reopened_client.shutdown.complete", run_id=receipt.run_id)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_portable_n4_budget_stop_reopens_prior_selected_result(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    controlled_candidate_gateway: Any,
    served_worker_phase_probe: Any,
) -> None:
    """Run the existing later-spend path against an owner-built portable source profile."""
    from tests._helpers.candidate_cycle_source_profile import (
        build_candidate_cycle_substrate_route_inputs,
    )

    source_inputs = build_candidate_cycle_substrate_route_inputs(
        tmp_path / "portable-n4-budget-source-root"
    )
    original_prepare = prepare_generic_n4_served_replay

    async def prepare_portable(**kwargs: Any) -> Any:
        assert "source_root" not in kwargs
        prepared = await original_prepare(**kwargs, source_root=source_inputs.root)
        assert prepared.source_root == source_inputs.root
        assert prepared.app_kwargs["repo_root"] == source_inputs.root
        witness = prepared.source_root_witness
        assert witness["source_root"] == str(source_inputs.root)
        assert witness["n4_repo_root"] == str(source_inputs.root)
        assert all(
            Path(witness[name]).is_relative_to(source_inputs.root)
            for name in ("selected_l1_dcat_path", "selected_l2_skg_path", "selected_l3_lex_path")
        )
        return prepared

    # Select input only; keep the exact existing producer, checks and consumer.
    with monkeypatch.context() as selected_source:
        selected_source.setitem(globals(), "prepare_generic_n4_served_replay", prepare_portable)
        await test_served_n6_uses_later_real_n4_spend_and_keeps_first_n5(
            tmp_path, monkeypatch, controlled_candidate_gateway, served_worker_phase_probe
        )


@pytest.mark.integration
def test_controlled_candidate_snapshot_requires_selected_profile_and_input_lineage(
    tmp_path: Path,
) -> None:
    """Read back the exact fixture view and reject marker-preserving removals."""
    from polisyos.common.canonical_profile import CanonicalProfileRefusalError
    from polisyos.core.artifacts import (
        CanonInfo,
        FileSystemCAS,
        PutOptions,
        SchemaInfo,
    )
    from polisyos.core.canon import CanonSpec
    from polisyos.core.contracts import DataSnapshot
    from tests._helpers.controlled_candidate_profile import (
        _persist_controlled_data_snapshot,
        _read_controlled_data_snapshot_source,
    )

    store = FileSystemCAS(tmp_path / "controlled-candidate-cas")
    canon_spec = CanonSpec(forbid_floats=False)
    payload_ref = store.put_json(
        {"cells": {"distress_score": [0.0]}},
        PutOptions(kind="fabric.world_payload", media_type="application/json"),
        canon_spec=canon_spec,
        return_selected_profile=True,
    )
    snapshot_ref = _persist_controlled_data_snapshot(
        artifact_store=store,
        payload_ref=payload_ref,
        snapshot_id="controlled-profile-admission",
    )
    snapshot = _read_controlled_data_snapshot_source(
        artifact_store=store,
        snapshot_ref=snapshot_ref,
        payload_ref=payload_ref,
    )
    manifest = store.get_manifest(snapshot_ref)
    expected_schema = SchemaInfo(
        name=DataSnapshot.ARTIFACT_SCHEMA_NAME,
        version=DataSnapshot.ARTIFACT_SCHEMA_VERSION,
    )
    expected_canon = CanonInfo.from_spec(canon_spec)

    assert isinstance(snapshot, DataSnapshot)
    assert snapshot.data_ref == payload_ref
    assert snapshot_ref.manifest_profile_sha256 is not None
    assert manifest.artifact_schema == expected_schema
    assert manifest.canon == expected_canon
    assert len(manifest.inputs) == 1
    assert manifest.inputs[0].role == "data_ref"
    assert manifest.inputs[0].artifact_id == payload_ref.artifact_id
    assert manifest.inputs[0].manifest_profile_sha256 == payload_ref.manifest_profile_sha256

    profileless_ref = snapshot_ref.model_copy(update={"manifest_profile_sha256": None})
    with pytest.raises(ValueError, match="controlled_data_snapshot_selected_profile_missing"):
        _read_controlled_data_snapshot_source(
            artifact_store=store,
            snapshot_ref=profileless_ref,
            payload_ref=payload_ref,
        )

    snapshot_bytes = store.get_bytes(snapshot_ref)
    missing_canon_ref = store.put_bytes(
        snapshot_bytes,
        PutOptions(
            kind=manifest.kind,
            media_type=manifest.media_type,
            schema=manifest.artifact_schema,
            inputs=manifest.inputs,
        ),
        return_selected_profile=True,
    )
    with pytest.raises(CanonicalProfileRefusalError, match="canon_profile_absent"):
        _read_controlled_data_snapshot_source(
            artifact_store=store,
            snapshot_ref=missing_canon_ref,
            payload_ref=payload_ref,
        )

    missing_input_ref = store.put_bytes(
        snapshot_bytes,
        PutOptions(
            kind=manifest.kind,
            media_type=manifest.media_type,
            schema=manifest.artifact_schema,
            canon=manifest.canon,
        ),
        return_selected_profile=True,
    )
    with pytest.raises(ValueError, match="controlled_data_snapshot_input_binding_mismatch"):
        _read_controlled_data_snapshot_source(
            artifact_store=store,
            snapshot_ref=missing_input_ref,
            payload_ref=payload_ref,
        )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_served_selected_ncm_refusal_preserves_successful_n4_sibling(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    controlled_candidate_gateway: Any,
    served_worker_phase_probe: Any,
) -> None:
    """A selected NCM overflow stays visible beside persisted finite siblings."""
    pytest.importorskip("fastapi.testclient")
    from fastapi.testclient import TestClient

    from polisyos.core.artifacts import load_core_json_artifact
    from polisyos.core.artifacts.manifest import ArtifactRef
    from polisyos.core.security.tenant_context import tenant_scope
    from polisyos.runtime.http.app import create_runtime_api_app
    from polisyos.runtime.http.services.control import (
        generation_cycle as generation_cycle_service,
    )
    from polisyos.runtime.quality.generic_simulation_admission import (
        GenericCycleSimulationN5InputV1,
        parse_generic_cycle_simulation_n5_execution,
    )
    from tests._helpers.control_worker import dispatch_one_control_job
    from tests._helpers.generic_n4_served_replay import prepare_generic_n4_served_replay
    from tests.unit.runtime.http.test_nl_pipeline_materialization import (
        _DeterministicSpanSupportClient,
    )

    tenant_id = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    cell_id = "cell-v6-selected-ncm-refusal"
    selected_overflow_model = {
        "target_baseline": 0.0,
        "outcome_baseline": 1.7e308,
        "outcome_per_target_unit": 1.0e308,
        "outcome_noise_stddev": 0.0,
    }
    served_worker_phase_probe("fixture_prepare.start")
    prepared = await prepare_generic_n4_served_replay(
        tmp_path=tmp_path,
        controlled_candidate_gateway=controlled_candidate_gateway,
        monkeypatch=monkeypatch,
        tenant_id=tenant_id,
        cell_id=cell_id,
        child_count=3,
        candidate_scm_overrides_by_child_index={1: selected_overflow_model},
        phase_callback=served_worker_phase_probe,
    )
    prepared = replace(prepared, request_json={**prepared.request_json, "max_iterations": 1})
    served_worker_phase_probe("fixture_prepare.complete")

    assert prepared.recording["recording_source"] == (
        "synthetic_three_child_overlay_of_recorded_capture"
    )
    assert prepared.source_recording_content_hash == _ORIGINAL_SECOND_CAPTURE_CONTENT_HASH
    assert len(prepared.children) == len(prepared.generic_child_profiles) == 3
    assert tuple(profile.profile_selection_ref for profile in prepared.generic_child_profiles) == (
        *prepared.child_keys,
    )
    overflow_profile = prepared.generic_child_profiles[1]
    assert overflow_profile.profile_id == "v6-n4-child-1"
    assert overflow_profile.profile_selection_ref == prepared.child_keys[1]
    assert overflow_profile.context_inputs.world_model_record.skg_causal_prior_ref == (
        prepared.selected_source_ref
    )
    assert overflow_profile.limitations == (
        "controlled_inputs_only",
        "currentness_not_established",
        "n5_simulation_not_world_evidence",
        "n9_not_admitted",
        "s8_blocked",
        "source_truth_not_established",
    )

    original_compiler = generation_cycle_service.build_design_problem_from_nl_request

    async def run_real_compiler(**kwargs: Any):
        kwargs["span_support_client"] = _DeterministicSpanSupportClient()
        return await original_compiler(**kwargs)

    monkeypatch.setattr(
        generation_cycle_service,
        "build_design_problem_from_nl_request",
        run_real_compiler,
    )
    served_worker_phase_probe("app_create.start")
    app = create_runtime_api_app(**prepared.app_kwargs)
    served_worker_phase_probe("app_create.complete")

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/control/runs/nl",
            headers={"Idempotency-Key": uuid.uuid4().hex},
            json=prepared.request_json,
        )
        assert response.status_code == 200, response.text
        accepted = response.json()
        assert accepted.get("status") == "accepted"
        service = app.state._control_service
        dispatched = dispatch_one_control_job(
            store=service._control_store,
            handler=service._process_control_job,
            expected_job_id=accepted["job_id"],
        )
        assert dispatched == accepted["job_id"]
        job = service._control_store.get_job(accepted["job_id"])
        assert job is not None and job.state == "completed"
        run_id = str(job.progress["core_run_id"])

        # This is a separate HTTP consumer read after the worker persisted the run.
        get_response = client.get(f"/api/v1/runs/{run_id}")
        assert get_response.status_code == 200, get_response.text
        run_payload = get_response.json()["run"]

    projection = run_payload["generic_cycle_simulation"]
    assert projection["artifact_status"] == "resolved"
    assert projection["child_profile_status"] == "resolved"
    assert projection["publication_authority"] is False
    assert projection["currentness_status"] == "not_established"
    bindings_by_selection = {
        row["profile_selection_ref"]: row for row in projection["child_profile_bindings"]
    }
    assert set(bindings_by_selection) == set(prepared.child_keys)
    assert all(
        row["historical_binding_status"] == "resolved" for row in bindings_by_selection.values()
    )

    observations_by_selection = {
        row["profile_selection_ref"]: row for row in projection["n5_observations"]
    }
    assert set(observations_by_selection) == set(prepared.child_keys)
    blocked = observations_by_selection[overflow_profile.profile_selection_ref]
    assert blocked["status"] == "simulation_blocked"
    assert blocked["simulation_result_ref"] is None
    assert blocked["n5_execution_ref"] is not None
    assert blocked["n8_status"] == "value_blocked"
    assert "ncm_outcome_non_finite" in blocked["authority_blockers"]
    assert "ncm_outcome_non_finite" in blocked["n8_authority_blockers"]

    peers = [
        row
        for key, row in observations_by_selection.items()
        if key != overflow_profile.profile_selection_ref
    ]
    assert len(peers) == 2
    assert all(row["status"] == "joint_simulated" for row in peers)
    assert all(row["simulation_result_ref"] is not None for row in peers)
    assert all(row["simulation_result_body_status"] == "resolved" for row in peers)

    with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
        blocked_input = GenericCycleSimulationN5InputV1.model_validate(
            load_core_json_artifact(
                prepared.runtime_api_context.store,
                ArtifactRef.model_validate(blocked["n5_input_ref"]),
            )
        )
        blocked_execution = parse_generic_cycle_simulation_n5_execution(
            load_core_json_artifact(
                prepared.runtime_api_context.store,
                ArtifactRef.model_validate(blocked["n5_execution_ref"]),
            )
        )
        peer_inputs = tuple(
            GenericCycleSimulationN5InputV1.model_validate(
                load_core_json_artifact(
                    prepared.runtime_api_context.store,
                    ArtifactRef.model_validate(row["n5_input_ref"]),
                )
            )
            for row in peers
        )
    assert blocked_input.profile == overflow_profile
    assert blocked_input.child_selection is not None
    assert blocked_input.child_selection.profile_selection_ref == prepared.child_keys[1]
    assert blocked_execution.status == "simulation_blocked"
    assert blocked_execution.limitation_code == "ncm_outcome_non_finite"
    assert blocked_execution.result_ref is None
    peer_inputs_by_selection = {item.profile.profile_selection_ref: item for item in peer_inputs}
    assert set(peer_inputs_by_selection) == {
        prepared.child_keys[0],
        prepared.child_keys[2],
    }
    assert all(
        peer_inputs_by_selection[prepared.child_keys[index]].profile
        == prepared.generic_child_profiles[index]
        for index in (0, 2)
    )

    checkpoint = projection["recursive_cycle_checkpoint"]
    assert checkpoint["publication_authority"] is False
    assert checkpoint["failed_branches"] == []


@pytest.mark.integration
@pytest.mark.asyncio
async def test_served_generic_cycle_reissues_owner_context_for_second_n5(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    controlled_candidate_gateway: Any,
    served_worker_phase_probe: Any,
) -> None:
    """A controlled N6 advance must persist and freshly read its reissued N5 context."""
    pytest.importorskip("fastapi.testclient")
    from decimal import Decimal

    from fastapi.testclient import TestClient

    from polisyos.core.artifacts import load_core_json_artifact
    from polisyos.core.artifacts.manifest import ArtifactRef
    from polisyos.core.security.tenant_context import tenant_scope
    from polisyos.runtime.http.app import create_runtime_api_app
    from polisyos.runtime.http.services.control import (
        generation_cycle as generation_cycle_service,
    )
    from polisyos.runtime.quality.cycle_substrate import (
        CycleSubstrateContextArtifactOwner,
        cycle_job_design_problem_ref,
    )
    from polisyos.runtime.quality.generation_cycle import (
        GenerationCycleController,
        SimpleVOIScheduler,
    )
    from polisyos.runtime.quality.generation_source import GenerationSourceRepository
    from polisyos.runtime.quality.generic_simulation_admission import (
        GenericCycleSimulationN5InputV1,
        parse_generic_cycle_simulation_n5_execution,
    )
    from tests._helpers.candidate_cycle_source_profile import (
        build_candidate_cycle_substrate_route_inputs,
    )

    source_inputs = build_candidate_cycle_substrate_route_inputs(tmp_path / "two-cycle-source-root")
    tenant_id = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    cell_id = "cell-v8-generic-cycle-rebind"
    prepared = await prepare_generic_n4_served_replay(
        tmp_path=tmp_path,
        controlled_candidate_gateway=controlled_candidate_gateway,
        monkeypatch=monkeypatch,
        tenant_id=tenant_id,
        cell_id=cell_id,
        child_count=3,
        phase_callback=served_worker_phase_probe,
        source_root=source_inputs.root,
    )
    assert prepared.source_root == source_inputs.root
    prepared = replace(
        prepared,
        request_json={
            **prepared.request_json,
            "max_iterations": 2,
            "run_budget_usd": 10.0,
        },
    )

    # This test drives the already-existing N6 advance branch to exercise the
    # context rebind. N4, N5, persistence, and the fresh GET remain the real path.
    original_controller_init = GenerationCycleController.__init__

    def controller_init_with_advancing_voi(self: Any, *args: Any, **kwargs: Any) -> None:
        kwargs["voi_scheduler"] = SimpleVOIScheduler(
            stage_costs={3: Decimal("0.000001"), 4: Decimal("0.000001")},
            min_roi_threshold=0.0,
            reserved_calibration_budget_fraction=0.0,
        )
        original_controller_init(self, *args, **kwargs)

    monkeypatch.setattr(
        GenerationCycleController,
        "__init__",
        controller_init_with_advancing_voi,
    )
    app = create_runtime_api_app(**prepared.app_kwargs)
    with TestClient(app) as client:
        receipt = await run_n4_control_worker_and_get(
            client=client,
            app=app,
            prepared=prepared,
            monkeypatch=monkeypatch,
            expected_failure_code="v6_controlled_second_n4_child_failure",
            exercise_projection_controls=False,
            phase_callback=served_worker_phase_probe,
        )
        assert receipt.job_state == "completed"
        projection = receipt.projection
        assert projection["authority_purpose"] == "cycle_input_candidate_only"
        assert projection["publication_authority"] is False
        assert projection["currentness_status"] == "not_established"
        assert projection["child_profile_status"] == "resolved"

        joint_rows = tuple(
            row for row in projection["n5_observations"] if row["status"] == "joint_simulated"
        )
        assert len(joint_rows) == 2
        by_node: dict[str, list[dict[str, Any]]] = {}
        for row in joint_rows:
            by_node.setdefault(row["node_ref"], []).append(row)
        matching = tuple(
            sorted(rows, key=lambda row: row["cycle_index"])
            for rows in by_node.values()
            if {row["cycle_index"] for row in rows} == {0, 1}
        )
        assert len(matching) == 1
        first, second = matching[0]
        assert first["n5_owner_join_status"] == "resolved"
        assert second["n5_owner_join_status"] == "resolved"
        assert first["context_job_ref"] != second["context_job_ref"]
        assert first["n4_source_ref"] != second["n4_source_ref"]
        assert first["profile_ref"] == second["profile_ref"]
        assert first["world_model_record_content_hash"] == second["world_model_record_content_hash"]

        service = app.state._control_service
        job = service._control_store.get_job(receipt.job_id)
        assert job is not None and job.run_id == receipt.run_id
        with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
            compiled_payload = service._load_payload_ref(
                job.progress["compiled_recursive_generation_cycle_ref"],
                kind="runtime.compiled_recursive_generation_cycle",
            )
        compiled = generation_cycle_service.CompiledRecursiveGenerationCycleRun.model_validate(
            compiled_payload
        )
        node = next(
            row for row in compiled.recursive_run.nodes if row.node_ref == first["node_ref"]
        )
        assert node.cycle_run is not None
        cycles = {row.cycle_index: row for row in node.cycle_run.cycles}
        assert set(cycles) == {0, 1}
        initial_binding = tuple(
            row
            for row in projection["child_profile_bindings"]
            if row["node_ref"] == first["node_ref"]
        )
        assert len(initial_binding) == 1
        assert first["context_job_ref"] == initial_binding[0]["context_job_ref"]

        repository = GenerationSourceRepository(prepared.runtime_api_context.store)
        context_owner = CycleSubstrateContextArtifactOwner(store=prepared.runtime_api_context.store)
        children_by_node = {
            "design-problem://"
            + cycle_job_design_problem_ref(child.problem).removeprefix("sha256:"): child
            for child in prepared.children
        }
        initial_child = children_by_node[first["node_ref"]]
        for observation in (first, second):
            input_ref = ArtifactRef.model_validate(observation["n5_input_ref"])
            execution_ref = ArtifactRef.model_validate(observation["n5_execution_ref"])
            with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
                input_record = GenericCycleSimulationN5InputV1.model_validate(
                    load_core_json_artifact(prepared.runtime_api_context.store, input_ref)
                )
                execution = parse_generic_cycle_simulation_n5_execution(
                    load_core_json_artifact(prepared.runtime_api_context.store, execution_ref)
                )
                source = repository.load(
                    input_record.n4_source_ref,
                    run_id=input_record.source_run_id,
                    expected_run_id=input_record.run_id,
                    expected_job_id=input_record.job_id,
                    expected_tenant_id=input_record.tenant_id,
                    expected_cell_id=input_record.cell_id,
                    context_job_ref=input_record.context_job_ref,
                    profile_ref=input_record.profile_ref,
                    n4_child_profile_family_ref=input_record.n4_child_profile_family_ref,
                )
                context_job = context_owner.resolve_historical_job_artifact(
                    input_record.context_job_ref,
                    problem=source.problem,
                    expected_job_id=input_record.job_id,
                    expected_run_id=input_record.run_id,
                    expected_tenant_id=input_record.tenant_id,
                    expected_cell_id=input_record.cell_id,
                )
            cycle = cycles[observation["cycle_index"]]
            assert input_record.cycle_index == cycle.cycle_index
            assert input_record.child_selection is not None
            assert input_record.child_selection.problem == source.problem
            assert input_record.design_problem_ref == cycle.design_problem_basis_ref
            assert input_record.context_job_ref == ArtifactRef.model_validate(
                observation["context_job_ref"]
            )
            assert execution.input_ref == input_ref
            assert execution.context_job_ref == input_record.context_job_ref
            assert execution.n4_source_ref == input_record.n4_source_ref
            assert execution.profile_ref == input_record.profile_ref
            assert execution.status == "joint_simulated"
            assert source.problem == (
                initial_child.problem
                if cycle.cycle_index == 0
                else cycles[0].revision_request.revised_problem
            )
            assert source.cycle_index == cycle.cycle_index
            assert source.cycle_substrate_context == context_job.context
            assert context_job.context.design_problem_ref == cycle.design_problem_basis_ref

        assert cycles[0].design_problem_basis_ref == cycle_job_design_problem_ref(
            initial_child.problem
        )
        assert cycles[1].design_problem_basis_ref == cycle_job_design_problem_ref(
            cycles[0].revision_request.revised_problem
        )
        assert cycles[0].simulation.cycle_substrate_context_job_ref == ArtifactRef.model_validate(
            first["context_job_ref"]
        )
        assert cycles[1].simulation.cycle_substrate_context_job_ref == ArtifactRef.model_validate(
            second["context_job_ref"]
        )


@contextmanager
def _serve_runtime_api_over_tcp(app: Any, *, port: int) -> Iterator[Any]:
    """Serve one prepared runtime app on loopback and fully join its Uvicorn thread."""
    import threading
    import time

    import httpx
    import uvicorn

    server = uvicorn.Server(
        uvicorn.Config(
            app,
            host="127.0.0.1",
            port=port,
            access_log=False,
            lifespan="on",
            log_level="warning",
        )
    )
    server_thread = threading.Thread(
        target=server.run,
        name=f"runtime-api-uvicorn-{port}",
        daemon=True,
    )
    server_thread.start()
    try:
        startup_deadline = time.monotonic() + 30.0
        while (
            server_thread.is_alive() and not server.started and time.monotonic() < startup_deadline
        ):
            time.sleep(0.01)
        if not server.started:
            raise RuntimeError("runtime_api_uvicorn_start_failed")

        with httpx.Client(
            base_url=f"http://127.0.0.1:{port}",
            timeout=httpx.Timeout(120.0, connect=10.0),
        ) as client:
            yield client
    finally:
        server.should_exit = True
        server_thread.join(timeout=10.0)
        if server_thread.is_alive():
            server.force_exit = True
            server_thread.join(timeout=10.0)
        if server_thread.is_alive():
            raise AssertionError("runtime_api_uvicorn_thread_did_not_stop")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_original_second_capture_tcp_reopens_partial_n5_after_sibling_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    controlled_candidate_gateway: Any,
    unused_tcp_port: int,
) -> None:
    """A controlled N4 sibling failure retains typed N5 through a fresh TCP reader."""
    pytest.importorskip("httpx")
    pytest.importorskip("uvicorn")

    from polisyos.core.artifacts.canonical_profile import read_core_json_artifact
    from polisyos.core.security.tenant_context import tenant_scope
    from polisyos.runtime.http.app import create_runtime_api_app
    from polisyos.runtime.http.container import RuntimeContainerOverrides
    from polisyos.runtime.http.dependencies import build_runtime_api_context
    from polisyos.runtime.http.routes import runs as run_routes
    from polisyos.runtime.http.services.control import (
        generation_cycle as generation_cycle_service,
    )
    from polisyos.runtime.quality.cycle_substrate import cycle_job_design_problem_ref
    from tests._helpers.candidate_cycle_source_profile import (
        build_candidate_cycle_substrate_route_inputs,
    )
    from tests._helpers.generic_n4_served_replay import (
        prepare_generic_n4_served_replay,
        run_n4_control_worker_and_get,
    )
    from tests.unit.runtime.http.test_nl_pipeline_materialization import (
        _DeterministicSpanSupportClient,
    )

    source_inputs = build_candidate_cycle_substrate_route_inputs(
        tmp_path / "n4-tcp-candidate-source-root"
    )
    prepared = await prepare_generic_n4_served_replay(
        tmp_path=tmp_path,
        controlled_candidate_gateway=controlled_candidate_gateway,
        monkeypatch=monkeypatch,
        tenant_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        cell_id="cell-v2-original-n4-tcp",
        recording_mode="original_second_capture",
        child_count=2,
        source_root=source_inputs.root,
    )
    prepared = replace(prepared, request_json={**prepared.request_json, "max_iterations": 1})
    source_witness = prepared.source_root_witness
    assert prepared.source_root == source_inputs.root
    assert prepared.app_kwargs["repo_root"] == source_inputs.root
    assert source_witness["source_root"] == str(source_inputs.root)
    assert source_witness["n4_repo_root"] == str(source_inputs.root)
    assert len(source_witness["selected_l1_dcat_sha256"]) == 64
    assert len(source_witness["selected_l2_source_sha256"]) == 64
    assert source_witness["selected_l2_version_id"] == prepared.selected_skg_version_id
    assert Path(source_witness["selected_l1_dcat_path"]).is_relative_to(source_inputs.root)
    assert Path(source_witness["selected_l2_skg_path"]).is_relative_to(source_inputs.root)
    assert Path(source_witness["selected_l3_lex_path"]).is_relative_to(source_inputs.root)
    assert all(
        Path(source_witness["selected_l6_bundle_paths"][name]).is_relative_to(source_inputs.root)
        for name in (
            "intervention_knob_dictionary",
            "lex_intervention_map",
            "observation_to_contract_manifest",
        )
    )
    assert max(source_witness["selected_l3_row_counts"].values(), default=0) < 1000
    assert source_witness["selected_l6_bundle_content_hash"].startswith("sha256:")

    def persisted_n6_rows(run_id: str) -> list[dict[str, Any]]:
        indexed = prepared.runtime_api_context.run_index.get_run(run_id)
        assert indexed is not None
        refs = tuple(
            ref
            for ref in indexed.details.root_artifacts
            if ref.kind == "runtime.compiled_recursive_generation_cycle"
        )
        assert len(refs) == 1
        store = prepared.runtime_api_context.store
        with tenant_scope(None, tenant_id=prepared.tenant_id, cell_id=prepared.cell_id):
            assert store.verify(refs[0]).ok
            payload = read_core_json_artifact(store, refs[0]).value
        compiled = generation_cycle_service.CompiledRecursiveGenerationCycleRun.model_validate(
            payload
        )
        return _n6_history_rows_from_compiled(compiled)

    assert prepared.source_recording_id == _ORIGINAL_SECOND_CAPTURE_RECORDING_ID
    assert prepared.source_recording_content_hash == _ORIGINAL_SECOND_CAPTURE_CONTENT_HASH
    assert len(prepared.children) == 2
    assert len(prepared.generic_child_profiles) == 2
    selected_profile_ids = {profile.profile_id for profile in prepared.generic_profiles}
    assert prepared.app_kwargs["generic_cycle_simulation_profiles"] == prepared.generic_profiles
    assert prepared.app_kwargs["generic_cycle_simulation_root_profile_id"] == (
        prepared.root_profile.profile_id
    )
    assert {profile.profile_id for profile in prepared.generic_child_profiles} <= (
        selected_profile_ids
    )

    original_compiler = generation_cycle_service.build_design_problem_from_nl_request

    async def run_deterministic_compiler(**kwargs: Any) -> Any:
        kwargs["span_support_client"] = _DeterministicSpanSupportClient()
        return await original_compiler(**kwargs)

    monkeypatch.setattr(
        generation_cycle_service,
        "build_design_problem_from_nl_request",
        run_deterministic_compiler,
    )
    failure_code = "v6_controlled_second_n4_child_failure"
    app = create_runtime_api_app(**prepared.app_kwargs)
    with _serve_runtime_api_over_tcp(app, port=unused_tcp_port) as client:
        assert app.state._control_service._repo_root == source_inputs.root
        receipt = await run_n4_control_worker_and_get(
            client=client,
            app=app,
            prepared=prepared,
            monkeypatch=monkeypatch,
            expected_failure_code=failure_code,
            exercise_projection_controls=True,
        )
        assert receipt.corrupt_projection is not None
        assert receipt.corrupt_projection["n5_limitation_code"] == (
            "generic_n5_persisted_lineage_not_established"
        )
        assert receipt.incomplete_profile_projection is not None
        assert receipt.incomplete_profile_projection["child_profile_status"] == "not_established"
        budget_receipt = await run_n4_budget_stop_worker_and_get(
            client=client,
            app=app,
            prepared=prepared,
        )

    first_run = receipt.get_payload
    first_projection = receipt.projection
    first_source_n6_rows = persisted_n6_rows(receipt.run_id)
    assert first_projection["n6_cycle_history_status"] == "resolved"
    assert first_projection["n6_cycle_history_limitation_code"] is None
    assert first_projection["n6_cycle_history"] == first_source_n6_rows
    assert receipt.accepted_payload["status"] == "accepted"
    assert receipt.job_state == "completed"
    assert first_run["status"] == "fail"
    assert first_run["finished_at"] is not None
    assert first_projection["artifact_status"] == "resolved"
    assert first_projection["authority_purpose"] == "cycle_input_candidate_only"
    assert first_projection["publication_authority"] is False
    assert first_projection["currentness_status"] == "not_established"
    assert first_projection["child_profile_status"] == "resolved"

    expected_child_refs = {
        "design-problem://" + cycle_job_design_problem_ref(child.problem).removeprefix("sha256:")
        for child in prepared.children
    }
    child_bindings = first_projection["child_profile_bindings"]
    child_rows_by_profile = {row["profile_id"]: row for row in child_bindings}
    assert len(child_bindings) == 2
    assert set(child_rows_by_profile) == {
        profile.profile_id for profile in prepared.generic_child_profiles
    }
    assert {row["profile_selection_ref"] for row in child_bindings} == set(prepared.child_keys)
    assert {row["node_ref"] for row in child_bindings} == expected_child_refs
    assert all(row["currentness_status"] == "not_established" for row in child_bindings)

    successful_rows = [
        row for row in first_projection["n5_observations"] if row["status"] == "joint_simulated"
    ]
    assert len(successful_rows) == 1
    successful = successful_rows[0]
    assert successful["simulation_result_body_status"] == "resolved"
    assert (
        successful["simulation_result_ref"] == successful["simulation_result_body"]["artifact_ref"]
    )
    assert successful["simulation_result_body"]["authority_purpose"] == "cycle_input_candidate_only"
    assert successful["simulation_result_body"]["candidate_status"] == "candidate_unverified"
    assert successful["simulation_result_body"]["publication_authority"] is False
    assert successful["simulation_result_body"]["currentness_status"] == "not_established"
    assert receipt.n5_result_ref.model_dump(mode="json") == successful["simulation_result_ref"]
    assert receipt.missing_result_ref_error_code == "joint_simulation_result_unavailable"

    checkpoint = first_projection["recursive_cycle_checkpoint"]
    assert checkpoint["status"] == "partial"
    assert checkpoint["publication_authority"] is False
    assert checkpoint["budget_stop_node_ref"] is None
    assert len(checkpoint["failed_branches"]) == 1
    failed_branch = checkpoint["failed_branches"][0]
    assert failed_branch["error_code"] == failure_code
    assert failed_branch["stage"] == "leaf_generation"
    completed_children = set(checkpoint["completed_design_refs"]) & expected_child_refs
    failed_children = {failed_branch["failed_branch_ref"]} & expected_child_refs
    pending_children = set(checkpoint["pending_frontier"]) & expected_child_refs
    assert len(completed_children) == 1
    assert len(failed_children) == 1
    assert not pending_children
    assert completed_children | failed_children == expected_child_refs
    assert not (completed_children & failed_children)
    attempted_children = {
        child_rows_by_profile[profile_id]["node_ref"]
        for profile_id in receipt.child_attempt_profile_ids
    }
    assert attempted_children == completed_children | failed_children
    assert child_rows_by_profile[receipt.child_attempt_profile_ids[-1]]["node_ref"] == (
        next(iter(failed_children))
    )

    budget_first_run = budget_receipt.get_payload["run"]
    budget_projection = budget_receipt.projection
    budget_source_n6_rows = persisted_n6_rows(budget_receipt.run_id)
    assert budget_projection["n6_cycle_history_status"] == "resolved"
    assert budget_projection["n6_cycle_history_limitation_code"] is None
    assert budget_projection["n6_cycle_history"] == budget_source_n6_rows
    assert budget_receipt.accepted_payload["status"] == "accepted"
    assert budget_receipt.job_state == "completed"
    assert budget_first_run["finished_at"] is not None
    assert budget_projection["child_profile_status"] == "resolved"
    assert budget_projection["publication_authority"] is False
    assert budget_projection["currentness_status"] == "not_established"
    assert len(budget_receipt.child_node_refs) == 2
    budget_resolution = budget_receipt.job_status_payload["progress"]["recursive_budget_resolution"]
    assert budget_resolution == {
        "requested_max_iterations": 1,
        "effective_max_iterations": 1,
        "recursive_budget": {
            "max_depth": 1,
            "max_nodes": 3,
            "min_cycles_per_leaf": 1,
            "max_cycles_per_leaf": 1,
        },
        "clamp_reason": "none",
        "requested_candidate_children": 2,
        "effective_candidate_children": 2,
        "child_budget_profile": "n4-source-complete-child-set.v1",
    }
    budget_checkpoint = budget_receipt.checkpoint
    budget_stop_ref = budget_checkpoint["budget_stop_node_ref"]
    assert budget_checkpoint["status"] == "partial"
    assert budget_checkpoint["publication_authority"] is False
    assert budget_checkpoint["root_n9_status"] == "not_run"
    assert budget_checkpoint["failed_branches"] == []
    assert budget_stop_ref in budget_receipt.child_node_refs
    budget_child_refs = set(budget_receipt.child_node_refs)
    completed_budget_child_refs = (
        set(budget_checkpoint["completed_design_refs"]) & budget_child_refs
    )
    pending_budget_child_refs = set(budget_checkpoint["pending_frontier"]) & budget_child_refs
    assert completed_budget_child_refs == {budget_stop_ref}
    assert completed_budget_child_refs.isdisjoint(pending_budget_child_refs)
    assert set(budget_checkpoint["pending_frontier"]) == (budget_child_refs - {budget_stop_ref})
    assert budget_checkpoint["leaf_terminal_kinds"][budget_stop_ref] == "budget_exhausted"
    budget_history_node_refs = {row["node_ref"] for row in budget_projection["n6_cycle_history"]}
    assert budget_stop_ref in budget_history_node_refs
    assert pending_budget_child_refs.isdisjoint(budget_history_node_refs)

    reopened_context = build_runtime_api_context(
        cas_root=prepared.cas_root,
        core_runs_root=prepared.runtime_api_context.core_runs_root,
    )
    reopened_kwargs = dict(prepared.app_kwargs)
    reopened_kwargs["container_overrides"] = RuntimeContainerOverrides(
        runtime_api_context=reopened_context
    )
    reopened_app = create_runtime_api_app(**reopened_kwargs)
    with _serve_runtime_api_over_tcp(reopened_app, port=unused_tcp_port) as reopened_client:
        reopened_response = reopened_client.get(f"/api/v1/runs/{receipt.run_id}")
        assert reopened_response.status_code == 200, reopened_response.text
        reopened_run = reopened_response.json()["run"]
        reopened_budget_response = reopened_client.get(f"/api/v1/runs/{budget_receipt.run_id}")
        assert reopened_budget_response.status_code == 200, reopened_budget_response.text
        reopened_budget_run = reopened_budget_response.json()["run"]
        summary_response = reopened_client.get(
            "/api/v1/runs",
            params={"q": receipt.run_id},
        )
        assert summary_response.status_code == 200, summary_response.text
        matching_summaries = [
            row for row in summary_response.json()["runs"] if row["run_id"] == receipt.run_id
        ]
        budget_summary_response = reopened_client.get(
            "/api/v1/runs",
            params={"q": budget_receipt.run_id},
        )
        assert budget_summary_response.status_code == 200, budget_summary_response.text
        matching_budget_summaries = [
            row
            for row in budget_summary_response.json()["runs"]
            if row["run_id"] == budget_receipt.run_id
        ]
        with monkeypatch.context() as removal:
            removal.setattr(
                run_routes,
                "_generic_n6_cycle_history_fields",
                lambda _recursive_run: {
                    "n6_cycle_history_status": "resolved",
                    "n6_cycle_history_limitation_code": None,
                    "n6_cycle_history": (),
                },
            )
            removed_history_response = reopened_client.get(f"/api/v1/runs/{receipt.run_id}")
            assert removed_history_response.status_code >= 400
        restored_history_response = reopened_client.get(f"/api/v1/runs/{receipt.run_id}")
        assert restored_history_response.status_code == 200, restored_history_response.text
        restored_history = restored_history_response.json()["run"]["generic_cycle_simulation"]
        assert restored_history["n6_cycle_history_status"] == "resolved"
        assert restored_history["n6_cycle_history"] == first_source_n6_rows

    assert reopened_run["status"] == first_run["status"]
    assert reopened_run["finished_at"] == first_run["finished_at"]
    reopened_projection = reopened_run["generic_cycle_simulation"]
    assert reopened_projection["child_profile_bindings"] == child_bindings
    assert reopened_projection["n5_observations"] == first_projection["n5_observations"]
    assert reopened_projection["recursive_cycle_checkpoint"] == checkpoint
    assert reopened_projection["n6_cycle_history_status"] == "resolved"
    assert reopened_projection["n6_cycle_history"] == first_source_n6_rows
    assert len(matching_summaries) == 1
    assert matching_summaries[0]["status"] == "fail"
    assert matching_summaries[0]["run_terminality"] == "terminal"
    assert reopened_budget_run["status"] == budget_first_run["status"]
    assert reopened_budget_run["finished_at"] == budget_first_run["finished_at"]
    reopened_budget_projection = reopened_budget_run["generic_cycle_simulation"]
    assert (
        reopened_budget_projection["child_profile_bindings"]
        == budget_projection["child_profile_bindings"]
    )
    assert reopened_budget_projection["recursive_cycle_checkpoint"] == budget_checkpoint
    assert reopened_budget_projection["n6_cycle_history_status"] == "resolved"
    assert reopened_budget_projection["n6_cycle_history"] == budget_source_n6_rows
    assert len(matching_budget_summaries) == 1
    assert matching_budget_summaries[0]["status"] == budget_first_run["status"]
    assert matching_budget_summaries[0]["run_terminality"] == "terminal"
