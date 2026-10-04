"""Production near-miss source plumbing preserves admission and honest absence."""

from __future__ import annotations

import asyncio
from dataclasses import replace
from uuid import uuid4

import pytest

from polisyos.core import canon
from polisyos.core.contracts.control import WorkflowRunRequest
from polisyos.core.security.tenant_context import tenant_scope
from polisyos.runtime.http.execution_policy import RuntimePrincipal
from polisyos.runtime.http.services.control.evaluation_safety import (
    EvaluationSafetyPromotionSourceSlot,
)
from tests._helpers.control_worker import dispatch_one_control_job
from tests.integration.runtime_quality.test_evaluation_safety_admission import (
    _PRINCIPAL as _ADMISSION_FIXTURE_PRINCIPAL,
)
from tests.integration.runtime_quality.test_evaluation_safety_admission import (
    _field_pilot_intake,
    _launch_fixture_workflow,
    _run_blocked_attempt,
)
from tests.unit.runtime.http import test_control_service_di
from tests.unit.runtime.http.control_service_test_support import (
    bound_nl_authorization_proof,
)
from tests.unit.runtime.http.test_control_service_di import (
    _build_control_service,
    _fixture_claims,
    _run_controlled_simulate_only_job_fixture,
)


def _within_owner(owner: RuntimePrincipal, function, *args, **kwargs):
    """Run fixture operations under the supplied principal tenant/cell scope."""
    assert owner.tenant_id is not None
    assert owner.cell_id is not None
    with tenant_scope(None, tenant_id=owner.tenant_id, cell_id=owner.cell_id):
        return function(*args, **kwargs)


def _resolution(service, terminal, *, owner: RuntimePrincipal):
    def read_resolution():
        ref = terminal.progress["eval_safety_promotion_source_resolution_ref"]
        assert (
            terminal.progress["artifacts_index"][
                "eval_safety_promotion_source_resolution_ref"
            ]
            == ref
        )
        return canon.from_canonical_bytes(service._artifact_store.get_bytes(ref))

    return _within_owner(owner, read_resolution)


def _artifact_id(ref) -> str:
    """Return an artifact identity without discarding the supplied typed view."""
    artifact_id = getattr(ref, "artifact_id", ref)
    return str(artifact_id)


def _completed_core_source(produced_station, source_job):
    """Resolve the actual completed Core child owned by the control-job lease."""
    from polisyos.core.artifacts.manifest import ArtifactRef
    from polisyos.runtime.http.services.adapters.core_run import (
        derive_control_job_core_run_id,
        load_completed_control_job_core_run_source,
    )

    service = produced_station["service"]
    owner = produced_station["principal"]
    control_run_id = str(source_job.run_id)
    attempt = source_job.progress["core_run_attempt"]
    assert type(attempt) is int and attempt >= 1
    expected_core_run_id = derive_control_job_core_run_id(
        job_id=source_job.job_id,
        control_run_id=control_run_id,
        attempt=attempt,
    )
    assert source_job.progress["core_run_id"] == expected_core_run_id
    core_manifest_ref = ArtifactRef.model_validate(
        source_job.progress["core_manifest_artifact_ref"]
    )
    assert source_job.progress["manifest_ref"] == str(core_manifest_ref.artifact_id)

    source = _within_owner(
        owner,
        load_completed_control_job_core_run_source,
        store=service._artifact_store,
        core_runs_root=service._core_runs_root,
        job=source_job,
        expected_control_run_id=control_run_id,
        tenant_id=owner.tenant_id,
        cell_id=owner.cell_id,
    )
    assert source.run_id == expected_core_run_id
    assert source.tenant_id == owner.tenant_id
    assert source.cell_id == owner.cell_id
    assert source.manifest_ref == core_manifest_ref
    assert source.manifest.status == "ok"
    return source


def test_production_empty_slot_persists_named_absence_and_ignores_request_verdict(
    tmp_path, monkeypatch
):
    result = _run_blocked_attempt(tmp_path, monkeypatch, {"consumer_promotable": True})
    service = result["service"]
    try:
        resolution = _resolution(
            service, result["terminal"], owner=_ADMISSION_FIXTURE_PRINCIPAL
        )
        assert resolution["requested_source_run_ids"] == []
        assert resolution["inputs_read"] == []
        assert resolution["refusal_reasons"] == ["promotion_source_slot_empty"]
        assert resolution["classification"] == "not_established"
        assert "outside_deployment_selected_source_runs" in resolution["unresolved_by_construction"]
        assert result["decision"].near_miss is False
        assert result["executor_calls"] == 0
    finally:
        service.close()


def test_unreadable_selected_run_is_ambiguous_and_cannot_change_safety(tmp_path, monkeypatch):
    owner = _ADMISSION_FIXTURE_PRINCIPAL
    service = _within_owner(owner, _build_control_service, tmp_path)
    try:
        source_id, intake = _field_pilot_intake(service)
        service._evaluation_safety_promotion_sources = replace(
            service._evaluation_safety_promotion_sources,
            slot=EvaluationSafetyPromotionSourceSlot(source_run_ids=("missing-prior-run",)),
        )
        launch = _launch_fixture_workflow(
            service,
            WorkflowRunRequest(
                data_source={"data_snapshot_ref": source_id},
                params={"evaluation_safety_attempt": intake},
            ),
        )
        job = _within_owner(owner, service._control_store.get_job, launch.job_id)
        assert job is not None
        _within_owner(
            owner,
            dispatch_one_control_job,
            store=service._control_store,  # noqa: SLF001
            handler=service._process_control_job,  # noqa: SLF001
            expected_job_id=job.job_id,
        )
        terminal = _within_owner(owner, service._control_store.get_job, launch.job_id)
        assert terminal is not None
        resolution = _resolution(service, terminal, owner=owner)
        assert resolution["inputs_read"] == ["control_completed_job:missing-prior-run"]
        assert "promotion_source_job_not_completed" in resolution["refusal_reasons"]
        assert resolution["classification"] == "not_established"
        assert terminal.progress["eval_safety_counters"]["near_miss_count"] == 0
        # The worker does not reclaim a terminal row; no retry producer exists.
        assert (
            _within_owner(
                owner,
                dispatch_one_control_job,
                store=service._control_store,  # noqa: SLF001
                handler=service._process_control_job,  # noqa: SLF001
            )
            is None
        )
        retried = _within_owner(owner, service._control_store.get_job, launch.job_id)
        assert retried.progress["eval_safety_counters"] == terminal.progress["eval_safety_counters"]
    finally:
        service.close()


@pytest.fixture(scope="module")
def produced_station(tmp_path_factory):
    """Retain the controlled producer and its actual DI fixture principal."""
    from polisyos.runtime.quality.cycle_substrate import (
        CycleSubstrateContextArtifactOwner,
    )

    principal = RuntimePrincipal.from_user_claims(_fixture_claims())
    context_refs = []
    original_context_persist = (
        CycleSubstrateContextArtifactOwner.persist_for_current_job
    )

    def capture_context_ref(
        context_owner, context, *, problem, verified_nl_job_scope=None
    ):
        ref = original_context_persist(
            context_owner,
            context,
            problem=problem,
            verified_nl_job_scope=verified_nl_job_scope,
        )
        context_refs.append(ref)
        return ref

    base_cas_type = test_control_service_di.FileSystemCAS

    def runtime_composed_cas(*args, **kwargs):
        base_store = base_cas_type(*args, **kwargs)
        return base_store.with_ambient_ownership_enforcement()

    with pytest.MonkeyPatch.context() as patches:
        # Runtime composition uses this owner-aware view of the original CAS.
        # The DI helper's plain FileSystemCAS leaves default writes ownerless,
        # then its fixture tenant claim makes the later registry replay fail.
        patches.setattr(
            test_control_service_di, "FileSystemCAS", runtime_composed_cas
        )
        patches.setattr(
            CycleSubstrateContextArtifactOwner,
            "persist_for_current_job",
            capture_context_ref,
        )
        fixture = _within_owner(
            principal,
            asyncio.run,
            _run_controlled_simulate_only_job_fixture(
                patches,
                tmp_path_factory.mktemp("controlled-profile-source"),
            ),
        )
    assert len(context_refs) == 1
    context_ref = context_refs[0]
    assert str(context_ref.artifact_id) == (
        fixture.job.progress["cycle_substrate_context_job_ref"]
    )
    try:
        yield {
            "service": fixture.service,
            "source_run_id": fixture.job.run_id,
            "job_id": fixture.job.job_id,
            "principal": principal,
            "cycle_substrate_context_ref": context_ref,
        }
    finally:
        _within_owner(principal, fixture.service.close)


def _attempt_from_produced_source(produced_station, *, candidate_hash=None, world_hash=None):
    service = produced_station["service"]
    owner = produced_station["principal"]
    source_run_id = produced_station["source_run_id"]
    source_job = _within_owner(
        owner, service._control_store.get_job, produced_station["job_id"]
    )
    assert source_job is not None
    core_source = _completed_core_source(produced_station, source_job)
    from polisyos.core.artifacts.manifest import ArtifactRef

    compiled_refs = tuple(
        ref
        for ref in core_source.manifest.outputs
        if ref.kind == "runtime.compiled_recursive_generation_cycle"
    )
    assert len(compiled_refs) == 1
    compiled_ref = compiled_refs[0]
    assert type(compiled_ref) is ArtifactRef
    assert (
        str(compiled_ref.artifact_id)
        == source_job.progress["compiled_recursive_generation_cycle_ref"]
    )
    compiled_bytes = _within_owner(
        owner, service._artifact_store.get_bytes, compiled_ref
    )
    compiled = canon.from_canonical_bytes(compiled_bytes)
    leaf = next(row for row in compiled["recursive_run"]["nodes"] if row["cycle_run"] is not None)
    candidate = leaf["cycle_run"]["candidate_summaries"][0]
    source_id, intake = _field_pilot_intake(service, owner=owner)
    intake["attempt_id"] = f"prior-generation-near-miss-{uuid4().hex}"
    intake["design_problem_ref"] = leaf["design_problem_ref"]
    intake["candidate_ref"]["artifact_id"] = candidate["candidate_id"]
    intake["candidate_ref"]["content_hash"] = candidate_hash or candidate["content_hash"]
    if world_hash is not None:
        intake["world_model_record_ref"]["content_hash"] = world_hash
    service._evaluation_safety_promotion_sources = replace(
        service._evaluation_safety_promotion_sources,
        slot=EvaluationSafetyPromotionSourceSlot(source_run_ids=(source_run_id,)),
    )
    launch = _within_owner(
        owner,
        service.launch_workflow_run,
        WorkflowRunRequest(
            data_source={"data_snapshot_ref": source_id},
            params={"evaluation_safety_attempt": intake},
        ),
        principal=owner,
    )
    return service, source_job, compiled_ref, launch


def test_existing_blocked_generation_producer_is_read_before_n9_refusal(
    produced_station,
):
    owner = produced_station["principal"]
    service, source_job, compiled_ref, launch = _attempt_from_produced_source(produced_station)
    _within_owner(
        owner,
        dispatch_one_control_job,
        store=service._control_store,  # noqa: SLF001
        handler=service._process_control_job,  # noqa: SLF001
        expected_job_id=launch.job_id,
    )
    terminal = _within_owner(owner, service._control_store.get_job, launch.job_id)
    assert terminal is not None
    core_source = _completed_core_source(produced_station, source_job)
    result = _resolution(service, terminal, owner=owner)
    assert result["inputs_read_scope"] == "source_selection_only"
    assert f"cas_bytes:{_artifact_id(compiled_ref)}" in result["inputs_read"]
    assert f"cas_manifest:{source_job.progress['manifest_ref']}" in result["inputs_read"]
    assert any(value.startswith("terminal_trace:") for value in result["inputs_read"])
    assert tuple(core_source.manifest.outputs) == (compiled_ref,)
    assert source_job.progress["candidate_computation_status"] == "completed"
    assert source_job.progress["normative_disposition_status"] == "not_run"
    assert source_job.progress["s8_status"] == "not_run"
    assert source_job.progress["publication_status"] == "not_run"
    compiled_bytes = _within_owner(
        owner, service._artifact_store.get_bytes, compiled_ref
    )
    compiled = canon.from_canonical_bytes(compiled_bytes)
    leaf = next(
        row for row in compiled["recursive_run"]["nodes"]
        if row["cycle_run"] is not None
    )
    assert leaf["cycle_run"]["terminal_status"] == "blocked"
    from polisyos.core.artifacts.manifest import ArtifactRef
    from polisyos.runtime.http.services.control.evaluation_safety import (
        EvaluationSafetyPromotionSourceResolution,
    )

    persisted_compiled_ref = ArtifactRef.model_validate(
        source_job.progress["compiled_recursive_generation_cycle_artifact_ref"]
    )
    assert persisted_compiled_ref == compiled_ref
    resolution = EvaluationSafetyPromotionSourceResolution.model_validate(result)
    assert resolution.requested_source_run_ids == (str(source_job.run_id),)
    assert resolution.selected_compiled_ref is None
    assert f"cas_manifest:{_artifact_id(compiled_ref)}" in resolution.inputs_read
    assert f"cas_bytes:{_artifact_id(compiled_ref)}" in resolution.inputs_read
    assert resolution.refusal_reasons == (
        f"promotion_source_unresolved:{source_job.run_id}:ValueError",
        "promotion_source_blocked_generation_cycle_cannot_supply_n9_receipt",
    )
    assert resolution.classification == "not_established"
    assert terminal.state == "failed"
    assert terminal.error_message == "evaluation_safety_attempt_blocked"
    assert terminal.progress["authority_result"] == "blocked"
    assert terminal.progress["eval_safety_counters"]["near_miss_count"] == 0
    assert terminal.progress["eval_safety_counters"]["near_miss_classification_status"] == (
        "not_established"
    )
    assert "classification_offer" not in terminal.progress["artifacts_index"]


def test_controlled_profile_candidate_preserves_simulation_without_n9_authority(
    produced_station,
):
    """The actual controlled profile reaches N5 while N9, S8, and publication stay open."""
    from polisyos.runtime.http.services.control import generation_cycle

    owner = produced_station["principal"]
    service = produced_station["service"]
    source_job = _within_owner(
        owner, service._control_store.get_job, produced_station["job_id"]
    )
    assert source_job is not None
    source = _completed_core_source(produced_station, source_job)
    compiled_refs = tuple(
        ref
        for ref in source.manifest.outputs
        if ref.kind == "runtime.compiled_recursive_generation_cycle"
    )
    assert len(compiled_refs) == 1
    compiled = generation_cycle.CompiledRecursiveGenerationCycleRun.model_validate(
        canon.from_canonical_bytes(
            _within_owner(owner, service._artifact_store.get_bytes, compiled_refs[0])
        )
    )
    leaf = compiled.recursive_run.leaf_nodes[0]
    cycle = leaf.cycle_run
    assert cycle is not None
    assert cycle.cycles
    assert cycle.cycles[-1].simulation.status == "joint_simulated"
    assert cycle.value_port.status == "value_pending_n8"
    assert cycle.value_port.authority_blockers == ("candidate_scenario_n5_only",)
    assert cycle.promotion_port.status == "not_promoted"
    assert cycle.promotion_port.receipts == ()
    assert cycle.promotion_port.certified_candidate_ids == ()
    assert all(not candidate.certified_by_n9 for candidate in cycle.candidate_summaries)
    assert source_job.progress["cycle_substrate_context_job_ref"]
    assert source_job.progress["execution_intent_band"] == "simulate_only_attempt"
    assert source_job.progress["candidate_computation_status"] == "completed"
    assert source_job.progress["normative_disposition_status"] == "not_run"
    assert source_job.progress["s8_status"] == "not_run"
    assert source_job.progress["publication_status"] == "not_run"


def test_removing_core_terminal_with_progress_markers_retained_refuses_source(
    produced_station,
):
    """The promotion reader requires the lease-owned terminal trace itself."""
    owner = produced_station["principal"]
    service, source_job, compiled_ref, launch = _attempt_from_produced_source(
        produced_station
    )
    core_source = _completed_core_source(produced_station, source_job)
    trace_path = core_source.trace_path
    original_trace = trace_path.read_bytes()
    trace_lines = original_trace.splitlines(keepends=True)
    assert len(trace_lines) >= 2
    assert b"RUN_FINALIZED" in trace_lines[-1]
    retained_progress = dict(source_job.progress)
    trace_path.write_bytes(b"".join(trace_lines[:-1]))
    try:
        _within_owner(
            owner,
            dispatch_one_control_job,
            store=service._control_store,  # noqa: SLF001
            handler=service._process_control_job,  # noqa: SLF001
            expected_job_id=launch.job_id,
        )
        terminal = _within_owner(owner, service._control_store.get_job, launch.job_id)
        assert terminal is not None
        result = _resolution(service, terminal, owner=owner)
        assert result["classification"] == "not_established"
        assert result["requested_source_run_ids"] == [source_job.run_id]
        assert any(
            value.startswith("terminal_trace:")
            for value in result["source_selection_read_attempts"]
        )
        assert f"cas_bytes:{_artifact_id(compiled_ref)}" not in result["inputs_read"]
        assert "promotion_source_candidate_receipt_not_unique" not in result["refusal_reasons"]
        assert terminal.progress["eval_safety_counters"]["near_miss_count"] == 0
        current_source_job = _within_owner(
            owner, service._control_store.get_job, source_job.job_id
        )
        assert current_source_job is not None
        assert current_source_job.progress == retained_progress
        assert current_source_job.progress["core_run_id"] == source_job.progress["core_run_id"]
        assert current_source_job.progress["core_run_attempt"] == source_job.progress[
            "core_run_attempt"
        ]
        assert current_source_job.progress["core_manifest_artifact_ref"] == source_job.progress[
            "core_manifest_artifact_ref"
        ]
        assert current_source_job.progress["manifest_ref"] == source_job.progress["manifest_ref"]
        assert current_source_job.progress[
            "compiled_recursive_generation_cycle_ref"
        ] == source_job.progress["compiled_recursive_generation_cycle_ref"]
    finally:
        trace_path.write_bytes(original_trace)


def test_compiled_source_content_binding_survives_retained_semantic_markers(
    produced_station, monkeypatch
):
    owner = produced_station["principal"]
    service, _, compiled_ref, launch = _attempt_from_produced_source(produced_station)
    original = service._artifact_store.get_bytes

    def rebound_bytes(ref):
        body = original(ref)
        # Identical parsed values and self-hash; changed CAS bytes must still refuse.
        return body + b" " if _artifact_id(ref) == _artifact_id(compiled_ref) else body

    monkeypatch.setattr(service._artifact_store, "get_bytes", rebound_bytes)
    _within_owner(
        owner,
        dispatch_one_control_job,
        store=service._control_store,  # noqa: SLF001
        handler=service._process_control_job,  # noqa: SLF001
        expected_job_id=launch.job_id,
    )
    terminal = _within_owner(owner, service._control_store.get_job, launch.job_id)
    assert terminal is not None
    result = _resolution(service, terminal, owner=owner)
    assert "promotion_source_artifact_binding_mismatch" in result["refusal_reasons"], (
        "source CAS binding property was removed"
    )
    assert f"cas_bytes:{_artifact_id(compiled_ref)}" in result["source_selection_read_attempts"]
    assert result["classification"] == "not_established"


def test_matching_candidate_label_cannot_select_foreign_candidate_bytes(produced_station):
    owner = produced_station["principal"]
    service, _, _, launch = _attempt_from_produced_source(
        produced_station, candidate_hash="sha256:" + "a" * 64
    )
    _within_owner(
        owner,
        dispatch_one_control_job,
        store=service._control_store,  # noqa: SLF001
        handler=service._process_control_job,  # noqa: SLF001
        expected_job_id=launch.job_id,
    )
    terminal = _within_owner(owner, service._control_store.get_job, launch.job_id)
    assert terminal is not None
    result = _resolution(service, terminal, owner=owner)
    assert "promotion_source_candidate_content_mismatch" in result["refusal_reasons"]
    assert result["classification"] == "not_established"


def test_opaque_classifier_forwards_real_evidence_repository_to_both_n9_readers(
    tmp_path, monkeypatch
):
    from polisyos.runtime.quality import evaluation_safety as es
    from polisyos.runtime.quality import promotion_sequence as n9
    from tests.unit.runtime.http.services.test_evaluation_safety import (
        _blocked_core,
        _service,
        _verified_classification,
    )

    persistence, store = _service(tmp_path)
    core, _source_ref = _blocked_core(store)
    repository = n9.N9PromotionEvidenceBridgeRepository(store=store)
    actual = es.verify_near_miss_classification
    calls = []

    def invoke(**kwargs):
        # This fixture isolates forwarding; it deliberately supplies no real promotion claim.
        for name in ("validate_canonical_promotion_receipt", "promotion_receipt_allows_decision_front"):
            delegate = getattr(n9, name)

            def reader(*args, _delegate=delegate, _name=name, **reader_kwargs):
                assert reader_kwargs["promotion_evidence_resolver"] is repository
                calls.append(_name)
                return _delegate(*args, **reader_kwargs)

            monkeypatch.setattr(n9, name, reader)
        return actual(**kwargs, promotion_evidence_resolver=repository)

    monkeypatch.setattr(es, "verify_near_miss_classification", invoke)
    _verified_classification(core, monkeypatch, promotion_safe=False)
    assert calls == ["validate_canonical_promotion_receipt", "promotion_receipt_allows_decision_front"]
    assert persistence._artifact_store is store


@pytest.mark.parametrize("changed_field", [
    "artifact_id", "integrity", "byte_size", "media_type", "artifact_schema",
])
def test_compiled_source_manifest_custody_requires_exact_writer_contract(
    produced_station, monkeypatch, changed_field,
):
    owner = produced_station["principal"]
    service, _, compiled_ref, launch = _attempt_from_produced_source(produced_station)
    original = service._artifact_store.get_manifest

    def wrong_manifest(ref):
        manifest = original(ref)
        if _artifact_id(ref) != _artifact_id(compiled_ref):
            return manifest
        changes = {
            "artifact_id": type(manifest.artifact_id).model_validate("sha256:" + "f" * 64),
            "integrity": manifest.integrity.model_copy(update={"sha256": "f" * 64}),
            "byte_size": manifest.byte_size + 1,
            "media_type": "text/plain",
            "artifact_schema": manifest.artifact_schema.model_copy(update={"version": "99"}),
        }
        # Blob, payload markers, and kind remain exactly those the owner wrote.
        return manifest.model_copy(update={changed_field: changes[changed_field]})

    monkeypatch.setattr(service._artifact_store, "get_manifest", wrong_manifest)
    _within_owner(
        owner,
        dispatch_one_control_job,
        store=service._control_store,  # noqa: SLF001
        handler=service._process_control_job,  # noqa: SLF001
        expected_job_id=launch.job_id,
    )
    terminal = _within_owner(owner, service._control_store.get_job, launch.job_id)
    assert terminal is not None
    result = _resolution(service, terminal, owner=owner)
    original_failure = {
        "artifact_id": "Manifest artifact_id mismatch",
        "integrity": "Manifest integrity mismatch",
        "byte_size": "Manifest byte_size mismatch",
        "media_type": "promotion_source_artifact_binding_mismatch",
        "artifact_schema": "promotion_source_artifact_binding_mismatch",
    }[changed_field]
    assert any(original_failure in reason for reason in result["refusal_reasons"])
    assert f"cas_bytes:{_artifact_id(compiled_ref)}" in result["source_selection_read_attempts"]
    assert result["classification"] == "not_established"


def test_authoritative_classifier_rejects_foreign_mode_with_identical_candidate_and_world(
    tmp_path, monkeypatch,
):
    from types import SimpleNamespace

    from polisyos.runtime.quality import evaluation_safety as es
    from tests.unit.runtime.http.services.test_evaluation_safety import (
        _blocked_core,
        _service,
        _verified_classification,
    )

    _, store = _service(tmp_path)
    core, _ = _blocked_core(store)
    actual = es.verify_near_miss_classification
    calls = []

    def invoke(**kwargs):
        matching = actual(**kwargs)
        assert matching is not None
        assert kwargs["value_receipt"].evaluation_mode == core.evaluation_mode == "field_pilot"
        values = vars(kwargs["value_receipt"]).copy()
        values["evaluation_mode"] = "simulate_only"
        changed = dict(kwargs, value_receipt=SimpleNamespace(**values))
        # The mode alone changes: offer, candidate, world, and canonical markers are retained.
        assert actual(**changed) is None, "foreign evaluation mode accepted"
        calls.append("foreign_mode_refused")
        return matching

    monkeypatch.setattr(es, "verify_near_miss_classification", invoke)
    _verified_classification(core, monkeypatch, promotion_safe=False)
    assert calls == ["foreign_mode_refused"]


def _run_blocked_generation_source_refuses_before_eval_safety_n9_classifier(
    produced_station, monkeypatch,
):
    """Prove blocked source custody cannot reach EvalSafety classification.

    The N4/N5 candidate and simulation-only profile context come from the
    controlled served fixture. The epoch appointment, value receipt, and
    signing principal are test fixtures; this proves component wiring, not
    institutionally appointed production epoch authority or empirical grounding.
    """
    from threading import Event

    from polisyos.core import artifacts
    from polisyos.core.contracts.control import NaturalLanguageRunRequest
    from polisyos.pdc import gy_artifact_self_identity_projection, gy_content_hash
    from polisyos.runtime.http.resilience import build_guarded_signature_verifier
    from polisyos.runtime.http.services.control import evaluation_safety as adapter
    from polisyos.runtime.http.services.control import generation_cycle as generation
    from polisyos.runtime.http.services.control_worker import ControlWorker
    from polisyos.runtime.quality import evaluation_safety as es
    from polisyos.runtime.quality import promotion_safety as safety
    from polisyos.runtime.quality import promotion_sequence as n9
    from polisyos.runtime.quality.open_world_risk import PromotionRuntime
    from tests.unit.runtime.http.test_control_job_execution_intent import (
        _valid_intake_for_mode,
    )
    from tests.unit.runtime.quality.test_generation_cycle import (
        REPO_ROOT,
        _positive_epoch_admitted_batch,
    )
    from tests.unit.runtime.quality.test_promotion_sequence import _value_receipt

    service = produced_station["service"]
    owner = produced_station["principal"]
    prior_job = _within_owner(
        owner, service._control_store.get_job, produced_station["job_id"]
    )
    assert prior_job is not None
    compiled_bytes = _within_owner(
        owner,
        service._artifact_store.get_bytes,
        prior_job.progress["compiled_recursive_generation_cycle_ref"],
    )
    compiled = generation.CompiledRecursiveGenerationCycleRun.model_validate(
        canon.from_canonical_bytes(compiled_bytes)
    )
    leaf = compiled.recursive_run.leaf_nodes[0]
    summary = leaf.cycle_run.candidate_summaries[0]
    assert leaf.cycle_run.deployment_identity_status == "established"
    deployment_identity = leaf.cycle_run.deployment_identity
    assert deployment_identity is not None
    value = _value_receipt().model_copy(
        update={"candidate_id": summary.candidate_id, "evaluation_mode": "field_pilot"}
    )
    key = artifacts.KeyPair.generate()
    signer_identity = "source-owner://worker-r10-test"
    trust = safety.PromotionSafetySourceTrust(
        principals=(
            safety.PromotionSafetySourcePrincipal(
                identity=signer_identity, public_key_pem=key.public_pem().decode()
            ),
        )
    )
    signature_calls = []
    original_verify_signature = service._artifact_store.verify_signature

    def record_signature_verification(artifact_id, verifier, *, strict_identity=None):
        signature_calls.append(artifact_id)
        return original_verify_signature(
            artifact_id, verifier, strict_identity=strict_identity
        )

    monkeypatch.setattr(service._artifact_store, "verify_signature", record_signature_verification)
    signature_verifier = build_guarded_signature_verifier(
        backend="filesystem", guarded_store=service._artifact_store
    )
    assert signature_verifier is not None
    previous_runtime = service._promotion_runtime
    promotion_runtime = PromotionRuntime(
        store=service._artifact_store,
        completed_epoch_batches=service._decision_validity_service,
        promotion_safety_source_trust=trust,
        promotion_evidence_source=previous_runtime.promotion_evidence_source,
        signature_verifier=signature_verifier,
    )
    service._promotion_runtime = promotion_runtime
    n9_repository = n9.N9PromotionEvidenceBridgeRepository(
        store=service._artifact_store,
        measurement_catalog=promotion_runtime.promotion_evidence_source.measurement_catalog,
        measurement_providers=promotion_runtime.promotion_evidence_source.measurement_providers,
        promotion_safety_source_trust=trust,
        signature_verifier=signature_verifier,
    )
    service._evaluation_safety_promotion_sources = replace(
        service._evaluation_safety_promotion_sources,
        promotion_runtime=promotion_runtime,
        promotion_evidence_resolver=n9_repository,
    )

    def source_context(candidate_summary, design_problem):
        promotion_input = n9.CanonicalPromotionInput(
            design_problem_binding=n9.N9DesignProblemBinding.from_problem(design_problem),
            candidate_summary=candidate_summary,
            value_receipt=value,
        )
        source_evidence = safety.PromotionSafetyCandidateEvidence(
            scope=n9._promotion_safety_scope(promotion_input)
        )
        source_ref = service._artifact_store.put_json(
            source_evidence.model_dump(mode="json"),
            artifacts.PutOptions(
                kind=safety.PROMOTION_SAFETY_CANDIDATE_KIND,
                media_type="application/json",
                schema=artifacts.SchemaInfo(
                    name=safety.PROMOTION_SAFETY_CANDIDATE_KIND,
                    version=safety.PROMOTION_SAFETY_CANDIDATE_SCHEMA,
                ),
            ),
        )
        service._artifact_store.sign_artifact(
            source_ref.artifact_id,
            artifacts.Ed25519Signer(key.private_key),
            signer_identity=signer_identity,
        )
        return {
            "value_receipt": value,
            "promotion_safety_source_refs": (str(source_ref.artifact_id),),
        }

    # This test-only verifier exercises N9 consumer wiring. It is not an
    # institutionally appointed production epoch verifier, so the receipt below
    # cannot establish production epoch authority.
    monkeypatch.setattr(n9, "_legacy_policy_promotion_callers", lambda _root: ())
    owned_handoffs = []
    n9_observations = []

    async def compiled_owner_output(**kwargs):
        """Replay an existing owned candidate through N9 within this Core run."""
        context_resolver = kwargs.get("cycle_substrate_context_resolver")
        currentness_resolver = kwargs.get("candidate_simulation_currentness_resolver")
        assert callable(context_resolver), "controlled profile owner was bypassed"
        assert callable(currentness_resolver), "controlled profile currentness was bypassed"
        from polisyos.runtime.quality.candidate_simulation import (
            CandidateSimulationContextHandoff,
        )
        from polisyos.runtime.quality.cycle_substrate import (
            cycle_job_design_problem_ref,
            cycle_job_profile_selection_ref,
        )

        handoff = context_resolver(compiled.design_problem)
        assert type(handoff) is CandidateSimulationContextHandoff
        assert handoff.profile.profile_selection_ref == cycle_job_profile_selection_ref(
            compiled.design_problem
        )
        assert handoff.context.design_problem_ref == cycle_job_design_problem_ref(
            compiled.design_problem
        )
        assert handoff.context.world_model_record.authority_status == "limited"
        assert handoff.context.world_model_record.simulation_model_ref.calibrated is False
        assert currentness_resolver() is True
        owned_handoffs.append(handoff)

        # The persisted N4/N5 candidate above is the input to this N9 replay.
        # The source run below carries a real SIMULATE_ONLY intent and actual
        # profile owner; it does not claim that the old N4 computation reran.
        admitted = _within_owner(
            owner,
            _positive_epoch_admitted_batch,
            runtime=promotion_runtime,
            problem=compiled.design_problem,
            summaries=(summary,),
        )
        observation = _within_owner(
            owner,
            n9.CanonicalN9PromotionPort(
                promotion_runtime=promotion_runtime,
                repo_root=REPO_ROOT,
                context_provider=source_context,
            ),
            admitted_batch=admitted,
            problem=compiled.design_problem,
            deployment_identity=deployment_identity,
        )
        receipt = n9.CanonicalPromotionReceipt.model_validate(observation.receipts[0])
        assert observation.status == "not_promoted"
        assert receipt.owner_projection.open_world_gate is not None
        assert receipt.owner_projection.epoch_validity_projection is not None
        assert receipt.owner_projection.value_receipt.evaluation_mode == "field_pilot"
        n9_observations.append(observation)

        # Reuse the real generated tree and install the actual N9 owner's
        # negative output for this candidate-only replay.
        cycle = leaf.cycle_run.model_copy(update={"promotion_port": observation})
        node = leaf.model_copy(update={"cycle_run": cycle})
        recursive = compiled.recursive_run.model_copy(update={"nodes": (node,)})
        recursive_values = gy_artifact_self_identity_projection(recursive)
        recursive_values.pop("leaf_nodes", None)
        recursive = type(recursive).model_validate({
            **recursive.model_dump(mode="json"),
            "content_hash": gy_content_hash(recursive_values),
        })
        revised = compiled.model_copy(update={"recursive_run": recursive})
        compiled_values = gy_artifact_self_identity_projection(revised)
        compiled_values["recursive_run"].pop("leaf_nodes", None)
        return type(compiled).model_validate({
            **revised.model_dump(mode="json"),
            "content_hash": gy_content_hash(compiled_values),
        })

    monkeypatch.setattr(
        generation,
        "compile_and_run_recursive_generation_cycle",
        compiled_owner_output,
    )

    def process_job_with_worker(job_id):
        finished = Event()
        worker = ControlWorker(
            store=service._control_store,
            handler=lambda job: _process_job_for_worker(job, job_id, finished),
            poll_interval_s=0.05,
            worker_id=f"r10-worker-{uuid4().hex[:8]}",
        )
        worker.start()
        try:
            worker.wake()
            assert finished.wait(timeout=121), f"ControlWorker did not finish job {job_id}"
        finally:
            worker.stop(timeout=5)

    def _process_job_for_worker(job, expected_job_id, finished):
        try:
            service._process_control_job(job)
        finally:
            if job.job_id == expected_job_id:
                finished.set()
    from polisyos.runtime.quality.cycle_substrate import (
        CycleSubstrateContextArtifactOwner,
    )

    context_owner = CycleSubstrateContextArtifactOwner(
        store=service._artifact_store
    )
    context_artifact = _within_owner(
        owner,
        context_owner.resolve_historical_job_artifact,
        produced_station["cycle_substrate_context_ref"],
        problem=compiled.design_problem,
        expected_job_id=prior_job.job_id,
        expected_run_id=str(prior_job.run_id),
        expected_tenant_id=owner.tenant_id,
        expected_cell_id=owner.cell_id,
    )
    context_world = context_artifact.context.world_model_record
    source_simulation = leaf.cycle_run.cycles[-1].simulation
    assert source_simulation.status == "joint_simulated"
    assert source_simulation.k_world_ref_before == context_world.content_hash
    assert source_simulation.k_world_ref_after == context_world.content_hash
    if source_simulation.world_model_record is not None:
        assert source_simulation.world_model_record.content_hash == (
            context_world.content_hash
        )
    simulate_only_attempt = _valid_intake_for_mode("simulate_only").model_dump(
        mode="json"
    )
    simulate_only_attempt["design_problem_ref"] = leaf.design_problem_ref
    simulate_only_attempt["candidate_ref"]["artifact_id"] = summary.candidate_id
    simulate_only_attempt["candidate_ref"]["content_hash"] = summary.content_hash
    simulate_only_attempt["world_model_record_ref"]["artifact_id"] = (
        context_world.world_model_record_id
    )
    simulate_only_attempt["world_model_record_ref"]["content_hash"] = (
        context_world.content_hash
    )
    request = NaturalLanguageRunRequest(
        request=compiled.design_problem.nl_provenance.raw_request,
        llm_model="simulated-qwen",
        context={"evaluation_safety_attempt": simulate_only_attempt},
        max_iterations=1,
    )
    source = _within_owner(
        owner,
        lambda: asyncio.run(
            service.launch_nl_run(
                request,
                principal=owner,
                authorization_proof=bound_nl_authorization_proof(
                    _fixture_claims(), request
                ),
            )
        ),
    )
    source_job = _within_owner(owner, service._control_store.get_job, source.job_id)
    assert source_job is not None
    process_job_with_worker(source.job_id)
    completed = _within_owner(owner, service._control_store.get_job, source.job_id)
    assert completed is not None
    assert completed.state == "completed"
    assert completed.progress["execution_intent_band"] == "simulate_only_attempt"
    assert completed.progress["candidate_computation_status"] == "completed"
    assert completed.progress["normative_disposition_status"] == "not_run"
    assert completed.progress["s8_status"] == "not_run"
    assert completed.progress["publication_status"] == "not_run"
    assert len(owned_handoffs) == 1
    assert owned_handoffs[0].job_id == completed.job_id
    assert owned_handoffs[0].run_id == str(completed.run_id)
    assert owned_handoffs[0].tenant_id == owner.tenant_id
    assert owned_handoffs[0].cell_id == owner.cell_id
    assert len(n9_observations) == 1
    assert n9_observations[0].status == "not_promoted"
    assert n9_observations[0].certified_candidate_ids == ()
    selected = {
        "service": service,
        "source_run_id": source_job.run_id,
        "job_id": source.job_id,
        "principal": owner,
    }
    _, _, compiled_ref, launch = _attempt_from_produced_source(
        selected, world_hash=value.world_model_record_content_hash,
    )
    real_verify = adapter.verify_near_miss_classification
    real_compose = service._evaluation_safety_persistence_service.compose_and_persist_attempt
    calls, outcomes = [], []

    def verify(**kwargs):
        frozen = es.evaluation_safety_core_bytes(kwargs["core"])
        result = real_verify(**kwargs)
        assert es.evaluation_safety_core_bytes(kwargs["core"]) == frozen
        calls.append(result)
        return result

    def compose(**kwargs):
        result = real_compose(**kwargs)
        outcomes.append(result)
        return result

    monkeypatch.setattr(adapter, "verify_near_miss_classification", verify)
    monkeypatch.setattr(service._evaluation_safety_persistence_service, "compose_and_persist_attempt", compose)
    signature_calls.clear()
    process_job_with_worker(launch.job_id)
    terminal = _within_owner(owner, service._control_store.get_job, launch.job_id)
    assert terminal is not None
    assert terminal.state == "failed"
    assert terminal.error_message == "evaluation_safety_attempt_blocked"
    assert terminal.progress["authority_path"] == "evaluation_safety"
    assert terminal.progress["authority_result"] == "blocked"
    assert terminal.progress["eval_safety_disposition"] == "blocked"
    counters = terminal.progress["eval_safety_counters"]
    assert counters["near_miss_classification_status"] == "not_established"
    assert counters["near_miss_count"] == 0

    # Read the persisted selected source again through the actual Core and CAS owners.
    source_job = _within_owner(
        owner, service._control_store.get_job, selected["job_id"]
    )
    assert source_job is not None
    assert source_job.state == "completed"
    source_core = _completed_core_source(produced_station, source_job)
    from polisyos.core.artifacts.manifest import ArtifactRef
    from polisyos.runtime.http.services.control.evaluation_safety import (
        EvaluationSafetyPromotionSourceResolution,
    )

    persisted_compiled_ref = ArtifactRef.model_validate(
        source_job.progress["compiled_recursive_generation_cycle_artifact_ref"]
    )
    assert persisted_compiled_ref == compiled_ref
    assert tuple(source_core.manifest.outputs) == (compiled_ref,)
    assert source_job.progress["compiled_recursive_generation_cycle_ref"] == (
        _artifact_id(compiled_ref)
    )
    assert source_job.progress["candidate_computation_status"] == "completed"
    assert source_job.progress["normative_disposition_status"] == "not_run"
    assert source_job.progress["s8_status"] == "not_run"
    assert source_job.progress["publication_status"] == "not_run"

    compiled_bytes = _within_owner(
        owner, service._artifact_store.get_bytes, compiled_ref
    )
    persisted_compiled = generation.CompiledRecursiveGenerationCycleRun.model_validate(
        canon.from_canonical_bytes(compiled_bytes)
    )
    source_leaves = [
        node.cycle_run
        for node in persisted_compiled.recursive_run.leaf_nodes
        if node.cycle_run is not None
        and any(
            item.candidate_id == summary.candidate_id
            for item in node.cycle_run.candidate_summaries
        )
    ]
    assert len(source_leaves) == 1
    persisted_cycle = source_leaves[0]
    assert persisted_cycle.terminal_status == "blocked"
    assert persisted_cycle.promotion_port.status == "not_promoted"
    assert persisted_cycle.promotion_port.certified_candidate_ids == ()

    resolution = EvaluationSafetyPromotionSourceResolution.model_validate(
        _resolution(service, terminal, owner=owner)
    )
    assert resolution.requested_source_run_ids == (str(source_job.run_id),)
    assert resolution.inputs_read_scope == "source_selection_only"
    assert resolution.selected_compiled_ref is None
    compiled_id = _artifact_id(compiled_ref)
    assert f"cas_manifest:{compiled_id}" in resolution.inputs_read
    assert f"cas_bytes:{compiled_id}" in resolution.inputs_read
    assert f"cas_manifest:{source_job.progress['manifest_ref']}" in resolution.inputs_read
    assert f"cas_bytes:{source_job.progress['manifest_ref']}" in resolution.inputs_read
    assert f"terminal_trace:{source_core.trace_path}" in resolution.inputs_read
    assert resolution.refusal_reasons == (
        f"promotion_source_unresolved:{source_job.run_id}:ValueError",
        "promotion_source_blocked_generation_cycle_cannot_supply_n9_receipt",
    )
    assert resolution.classification == "not_established"

    # The blocked source is terminal for N9, while EvalSafety still persists its
    # typed refusal so the authority band has an auditable reason for blocking.
    assert calls == []
    assert len(outcomes) == 1
    persisted_attempt = outcomes[0]
    assert persisted_attempt.decision.safety.status == "blocked"
    assert persisted_attempt.classification_offer_ref is None
    assert persisted_attempt.certificate_ref is None
    assert persisted_attempt.owner_evidence.classification is None
    assert persisted_attempt.decision.classification_offer_ref is None
    assert persisted_attempt.decision.promotion_validation_basis_ref is None
    assert persisted_attempt.decision.promotion_safe_facet is None
    assert persisted_attempt.decision.near_miss is False

    persisted_decision = es.EvaluationSafetyDecisionEvent.model_validate(
        canon.from_canonical_bytes(
            _within_owner(
                owner,
                service._artifact_store.get_bytes,
                persisted_attempt.decision_ref.artifact_id,
            )
        )
    )
    assert persisted_decision == persisted_attempt.decision

    assert persisted_attempt.promotion_source_resolution_ref == (
        terminal.progress["eval_safety_promotion_source_resolution_ref"]
    )
    persisted_resolution = EvaluationSafetyPromotionSourceResolution.model_validate(
        canon.from_canonical_bytes(
            _within_owner(
                owner,
                service._artifact_store.get_bytes,
                persisted_attempt.promotion_source_resolution_ref,
            )
        )
    )
    assert persisted_resolution == resolution
    assert persisted_resolution.classification == "not_established"
    assert persisted_resolution.selected_compiled_ref is None

    persisted_projection = es.EvalSafetyMetricsProjection.model_validate(
        canon.from_canonical_bytes(
            _within_owner(
                owner,
                service._artifact_store.get_bytes,
                terminal.progress["eval_safety_projection_ref"],
            )
        )
    )
    assert persisted_attempt.decision_ref in persisted_projection.selected_decision_artifact_refs
    assert persisted_attempt.decision.decision_id in (
        persisted_projection.unclassified_blocked_decision_ids
    )
    assert persisted_projection.near_miss_count == 0
    assert persisted_projection.near_miss_classification_status == "not_established"

    assert signature_calls == []
    assert "classification_offer" not in terminal.progress["artifacts_index"]
    failed_manifest_bytes = _within_owner(
        owner,
        service._artifact_store.get_bytes,
        terminal.progress["manifest_ref"],
    )
    failed_manifest = canon.from_canonical_bytes(failed_manifest_bytes)
    offer_kind = es.EVALUATION_SAFETY_ARTIFACT_IDENTITIES[
        "classification_offer"
    ].kind
    assert all(output["kind"] != offer_kind for output in failed_manifest["outputs"])

    # The genuine prior source still exists, but is outside this deployment's selector.
    assert _within_owner(owner, service._artifact_store.get_bytes, compiled_ref)
    _, _, _, outside_launch = _attempt_from_produced_source(
        selected, world_hash=value.world_model_record_content_hash,
    )
    service._evaluation_safety_promotion_sources = replace(
        service._evaluation_safety_promotion_sources,
        slot=EvaluationSafetyPromotionSourceSlot(),
    )
    prior_calls = tuple(calls)
    process_job_with_worker(outside_launch.job_id)
    outside_terminal = _within_owner(
        owner, service._control_store.get_job, outside_launch.job_id
    )
    assert outside_terminal is not None
    outside = _resolution(service, outside_terminal, owner=owner)
    assert tuple(calls) == prior_calls
    assert outside["requested_source_run_ids"] == []
    assert outside["inputs_read"] == outside["source_selection_read_attempts"] == []
    assert outside["refusal_reasons"] == ["promotion_source_slot_empty"]
    assert "outside_deployment_selected_source_runs" in outside["unresolved_by_construction"]
    assert outside["classification"] == "not_established"
    assert outside_terminal.progress["eval_safety_counters"]["near_miss_count"] == 0


def test_blocked_generation_source_refuses_before_eval_safety_n9_classifier(
    produced_station, monkeypatch,
):
    """Run the blocked-source refusal witness under its real tenant and cell owner."""
    owner = produced_station["principal"]
    return _within_owner(
        owner,
        _run_blocked_generation_source_refuses_before_eval_safety_n9_classifier,
        produced_station,
        monkeypatch,
    )


def test_n9_repository_signature_capability_preserves_guarded_tenant_cell_custody(
    tmp_path, monkeypatch
):
    """The N9 repository cannot replay requests or sources outside their CAS scope."""
    from polisyos.core import artifacts
    from polisyos.core.security.tenant_context import tenant_scope
    from polisyos.runtime.http.execution_policy import RuntimeExecutionPolicyResolver
    from polisyos.runtime.http.resilience import (
        build_guarded_signature_verifier,
        guard_runtime_cas,
    )
    from polisyos.runtime.http.services.control.run_lifecycle import ControlPlaneService
    from polisyos.runtime.quality import promotion_safety as safety
    from polisyos.runtime.quality import promotion_sequence as sequence
    from polisyos.runtime.quality.open_world_risk import PromotionRuntime
    from tests.unit.runtime.http import test_control_service_di as control_fixtures
    from tests.unit.runtime.quality.test_promotion_sequence import (
        _problem_binding,
        _summary,
        _value_receipt,
    )

    tenant_a, tenant_b = "tenant-r10-a", "tenant-r10-b"
    cell_a, cell_b = "cell-r10-a", "cell-r10-b"
    store_calls = {"get_bytes": 0, "get_manifest": 0, "verify_signature": 0}
    verifier_ids = []
    raw_store = artifacts.FileSystemCAS(tmp_path / "cas").with_ambient_ownership_enforcement()
    for method_name in store_calls:
        original = getattr(raw_store, method_name)

        def observe(*args, _name=method_name, _original=original, **kwargs):
            store_calls[_name] += 1
            if _name == "verify_signature":
                verifier_ids.append(args[0])
            return _original(*args, **kwargs)

        monkeypatch.setattr(raw_store, method_name, observe)
    guarded_store = guard_runtime_cas(raw_store)
    signature_verifier = build_guarded_signature_verifier(
        backend="filesystem", guarded_store=guarded_store
    )
    assert signature_verifier is not None

    key = artifacts.KeyPair.generate()
    signer_identity = "source-owner://served-test"
    trust = safety.PromotionSafetySourceTrust(
        principals=(
            safety.PromotionSafetySourcePrincipal(
                identity=signer_identity, public_key_pem=key.public_pem().decode()
            ),
        )
    )
    with tenant_scope(None, tenant_id=tenant_a, cell_id=cell_a):
        decision_validity = ControlPlaneService.build_decision_validity_owner(guarded_store)
        promotion_runtime = PromotionRuntime(
            store=guarded_store,
            completed_epoch_batches=decision_validity,
            promotion_safety_source_trust=trust,
            signature_verifier=signature_verifier,
        )
        resolver = RuntimeExecutionPolicyResolver(
            default_profile="dev",
            worker_backend="external",
            state_store_backend="sqlite",
            sqlite_path=str(tmp_path / "control.sqlite3"),
            postgres_dsn=None,
        )
        service = ControlPlaneService(
            cas_root=tmp_path / "cas",
            core_runs_root=tmp_path / "runs",
            artifact_store=guarded_store,
            retrieval_service=control_fixtures._NoOpRetrievalService(),
            policy_resolver=resolver,
            registry_providers=control_fixtures._build_registry_providers(),
            decision_validity_service=decision_validity,
            promotion_runtime=promotion_runtime,
        )
        try:
            original = sequence.CanonicalPromotionInput(
                design_problem_binding=_problem_binding(),
                candidate_summary=_summary(),
                value_receipt=_value_receipt().model_copy(
                    update={"evaluation_mode": "field_pilot"}
                ),
            )
            scope = sequence._promotion_safety_scope(original)
            candidate = safety.PromotionSafetyCandidateEvidence(
                scope=scope, evidence_refs=("urn:test:r10-uppercase-control",)
            )
            source = guarded_store.put_json(
                candidate.model_dump(mode="json"),
                artifacts.PutOptions(
                    kind=safety.PROMOTION_SAFETY_CANDIDATE_KIND,
                    media_type="application/json",
                    schema=artifacts.SchemaInfo(
                        name=safety.PROMOTION_SAFETY_CANDIDATE_KIND,
                        version=safety.PROMOTION_SAFETY_CANDIDATE_SCHEMA,
                    ),
                ),
            )
            guarded_store.sign_artifact(
                source.artifact_id,
                artifacts.Ed25519Signer(key.private_key),
                signer_identity=signer_identity,
            )
            canonical_ref = str(source.artifact_id)
            uppercase_ref = f"sha256:{canonical_ref.removeprefix('sha256:').upper()}"
            repository = service._evaluation_safety_promotion_sources.promotion_evidence_resolver

            bound = sequence._bind_production_promotion_evidence(
                original,
                context={"promotion_safety_source_refs": (uppercase_ref,)},
                repository=repository,
            )
            positive = repository.resolve_promotion_safety(promotion_input=bound)
            assert positive.custody_status == "verified"
            assert positive.source_attempts[0].source_ref == uppercase_ref
            assert positive.source_attempts[0].status == "candidate_custody_verified"
            assert positive.source_attempts[0].signature_verification_outcome == "verified"
            assert positive.promotion_authority_status == "not_established"
            assert all(type(artifact_id) is artifacts.ArtifactID for artifact_id in verifier_ids)
            assert all(str(artifact_id) == canonical_ref for artifact_id in verifier_ids)
            for name in store_calls:
                store_calls[name] = 0

            for tenant_id, cell_id in ((tenant_b, cell_a), (tenant_a, cell_b)):
                with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
                    verifier_calls_before_scope = store_calls["verify_signature"]
                    # The request itself belongs to tenant A / cell A. Its
                    # refusal is earlier than source verification, so do not
                    # claim the repository reached a foreign source attempt.
                    foreign = repository.resolve_promotion_safety(promotion_input=bound)
                    assert foreign.custody_status == "not_established"
                    assert foreign.source_attempts == ()
                    assert any(
                        row.status == "unreadable"
                        for row in foreign.inputs_read
                    )
                    assert foreign.promotion_authority_status == "not_established"

                    # Exercise the same owner-bound source read separately so
                    # this negative reaches the guarded CAS seam. Ownership
                    # refusal occurs before a signature verifier call.
                    attempt = repository._promotion_safety._source_attempt(
                        canonical_ref, scope
                    )
                    assert attempt.status != "candidate_custody_verified"
                    assert attempt.signer_identity is None
                    assert any(row.status == "unreadable" for row in attempt.inputs_read)
                    assert store_calls["verify_signature"] == verifier_calls_before_scope

                    # The optional capability itself still delegates through
                    # the guarded store and returns a typed refusal here.
                    verifier_calls_before = store_calls["verify_signature"]
                    verifier_result = signature_verifier.verify_signature(
                        source.artifact_id,
                        artifacts.Ed25519Verifier(strict_identity=True),
                    )
                    assert verifier_result.status == artifacts.SignatureVerificationStatus.ERROR
                    assert verifier_result.artifact_id == canonical_ref
                    assert store_calls["verify_signature"] == verifier_calls_before + 1

            for name in store_calls:
                store_calls[name] = 0
            malformed = repository._promotion_safety._source_attempt("malformed-ref", scope)
            assert malformed.signature_verification_outcome == "malformed_reference"
            assert malformed.inputs_read == ()
            assert store_calls == {"get_bytes": 0, "get_manifest": 0, "verify_signature": 0}
        finally:
            service.close()
