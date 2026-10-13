from __future__ import annotations

import hashlib
import shutil
import uuid
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]

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
    from tests._helpers.generic_n4_served_replay import _RECORDING_ID, _two_child_recording
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
@pytest.mark.asyncio
async def test_original_second_capture_serves_two_meaningful_children_through_fresh_get(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    controlled_candidate_gateway: Any,
) -> None:
    """Replay the unchanged three-proposal capture through ordinary POST and fresh GET."""
    pytest.importorskip("fastapi.testclient")
    from fastapi.testclient import TestClient

    from polisyos.runtime.http.app import create_runtime_api_app
    from polisyos.runtime.http.services.control import generation_cycle as generation_cycle_service
    from polisyos.runtime.quality.cycle_substrate import (
        cycle_job_design_problem_ref,
        cycle_job_profile_selection_ref,
        generic_n4_child_profile_selection_ref,
    )
    from polisyos.runtime.quality.generation_source import GenerationSourceRepository
    from tests._helpers.control_worker import dispatch_one_control_job
    from tests.unit.runtime.http.test_nl_pipeline_materialization import (
        _DeterministicSpanSupportClient,
    )
    from tools.quality.validation import (
        check_layer3_gy_design_generation_contract as n4_contract,
    )

    tenant_id = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    cell_id = "cell-v2-original-n4-capture"
    prepared = await prepare_generic_n4_served_replay(
        tmp_path=tmp_path,
        controlled_candidate_gateway=controlled_candidate_gateway,
        monkeypatch=monkeypatch,
        tenant_id=tenant_id,
        cell_id=cell_id,
        recording_mode="original_second_capture",
        child_count=2,
    )
    prepared = replace(prepared, request_json={**prepared.request_json, "max_iterations": 1})

    canonical_recording = next(
        item
        for item in n4_contract._load_recordings(REPO_ROOT)
        if item.get("recording_id") == _ORIGINAL_SECOND_CAPTURE_RECORDING_ID
    )
    assert prepared.recording == canonical_recording
    assert prepared.source_recording_id == _ORIGINAL_SECOND_CAPTURE_RECORDING_ID
    assert prepared.source_recording_content_hash == _ORIGINAL_SECOND_CAPTURE_CONTENT_HASH
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
    app = create_runtime_api_app(**prepared.app_kwargs)
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
        get_response = client.get(f"/api/v1/runs/{run_id}")
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
        checkpoint = projection["recursive_cycle_checkpoint"]
        assert checkpoint["budget_stop_node_ref"] is None
        assert checkpoint["failed_branches"] == []
        assert expected_child_node_refs.issubset(set(checkpoint["completed_design_refs"]))


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

    from polisyos.core.artifacts.manifest import ArtifactRef
    from polisyos.pdc import gy_content_hash
    from polisyos.runtime.http.app import create_runtime_api_app
    from polisyos.runtime.http.services.control import generation_cycle as generation_cycle_service
    from polisyos.runtime.quality.credal_reference import (
        build_credal_reference,
        credal_reference_l2_source_profile,
    )
    from polisyos.runtime.quality.cycle_substrate import (
        CycleSubstrateContextOwnerError,
        cycle_job_design_problem_ref,
        cycle_job_profile_selection_ref,
    )
    from polisyos.runtime.quality.generic_simulation_admission import (
        GenericCycleSimulationAdmissionOwner,
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
    with pytest.raises(ValueError, match="controlled_selected_skg_seed_target_exists"):
        _seed_controlled_selected_skg_source(malformed_seed_root)
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

    runtime_api_context = prepared.runtime_api_context
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
    assert selected_skg_prior_ref.skg_version_id == str(prepared.selected_skg_version_id)
    assert selected_skg_source_profile.source_snapshot_ref == prepared.selected_skg_snapshot_ref
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
        assert selected_edge.provenance["version"] == "7"
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
    from polisyos.runtime.quality.generation_source import (
        GenerationSourceRepository,
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
        assert successful["simulation_result_ref"]["kind"] == (
            "polisyos.runtime.joint_simulation_result"
        )
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
    from polisyos.scientist.orchestration.engine.budget_middleware import BudgetMiddleware
    from polisyos.scientist.orchestration.llm.factory import create_traced_gateway_client
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
) -> None:
    """Delete N5 bytes at its writer boundary while retaining the persisted run refs."""
    pytest.importorskip("fastapi.testclient")
    from fastapi.testclient import TestClient

    from polisyos.runtime.http.app import create_runtime_api_app
    from polisyos.runtime.http.services.control import generation_cycle as generation_cycle_service
    from tests._helpers.generic_n4_served_replay import (
        prepare_generic_n4_served_replay,
        run_n4_control_worker_and_get,
    )
    from tests.unit.runtime.http.test_nl_pipeline_materialization import (
        _DeterministicSpanSupportClient,
    )

    prepared = await prepare_generic_n4_served_replay(
        tmp_path=tmp_path,
        controlled_candidate_gateway=controlled_candidate_gateway,
        monkeypatch=monkeypatch,
        tenant_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        cell_id="cell-v2-n5-writer-removal",
        recording_mode="original_second_capture",
        child_count=2,
    )
    prepared = replace(prepared, request_json={**prepared.request_json, "max_iterations": 1})
    original_compiler = generation_cycle_service.build_design_problem_from_nl_request

    async def run_real_compiler(**kwargs: Any):
        kwargs["span_support_client"] = _DeterministicSpanSupportClient()
        return await original_compiler(**kwargs)

    monkeypatch.setattr(
        generation_cycle_service,
        "build_design_problem_from_nl_request",
        run_real_compiler,
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
            remove_n5_writer=True,
        )

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

    from polisyos.core.observability.pricing import estimate_llm_cost_usd
    from polisyos.core.security.tenant_context import tenant_scope
    from polisyos.runtime.http.app import create_runtime_api_app
    from polisyos.runtime.http.services.control.generation_cycle import (
        CompiledRecursiveGenerationCycleRun,
    )
    from polisyos.runtime.quality.generation_cycle import GenerationCycleController
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
            (record.amount for record in records if record.amount is not None), Decimal(0)
        )
        assert actual_spend == preflight_cost + Decimal(2) * one_n4_cost
        assert actual_spend > budget_limit
    served_worker_phase_probe("testclient_lifespan.shutdown.complete")
