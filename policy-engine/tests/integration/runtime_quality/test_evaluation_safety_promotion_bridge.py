"""Production near-miss source plumbing preserves admission and honest absence."""

from __future__ import annotations

import asyncio
from dataclasses import replace
from uuid import uuid4

import pytest

from polisyos.core import canon
from polisyos.core.contracts.control import WorkflowRunRequest
from polisyos.runtime.http.execution_policy import RuntimePrincipal
from polisyos.runtime.http.services.control.evaluation_safety import (
    EvaluationSafetyPromotionSourceSlot,
)
from tests.integration.runtime_quality.test_evaluation_safety_admission import (
    _field_pilot_intake,
    _run_blocked_attempt,
)
from tests.unit.runtime.http.test_control_service_di import (
    _build_control_service,
    _fixture_claims,
)
from tests.unit.runtime.http.test_control_service_di import (
    test_process_nl_job_enters_persisted_tenant_scope as _worker_example,
)


def _resolution(service, terminal):
    ref = terminal.progress["eval_safety_promotion_source_resolution_ref"]
    assert terminal.progress["artifacts_index"]["eval_safety_promotion_source_resolution_ref"] == ref
    return canon.from_canonical_bytes(service._artifact_store.get_bytes(ref))


def test_production_empty_slot_persists_named_absence_and_ignores_request_verdict(
    tmp_path, monkeypatch
):
    result = _run_blocked_attempt(tmp_path, monkeypatch, {"consumer_promotable": True})
    service = result["service"]
    try:
        resolution = _resolution(service, result["terminal"])
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
    service = _build_control_service(tmp_path)
    try:
        source_id, intake = _field_pilot_intake(service)
        service._evaluation_safety_promotion_sources = replace(
            service._evaluation_safety_promotion_sources,
            slot=EvaluationSafetyPromotionSourceSlot(source_run_ids=("missing-prior-run",)),
        )
        launch = service.launch_workflow_run(
            WorkflowRunRequest(
                data_source={"data_snapshot_ref": source_id},
                params={"evaluation_safety_attempt": intake},
            )
        )
        job = service._control_store.get_job(launch.job_id)
        service._process_control_job(job)
        terminal = service._control_store.get_job(launch.job_id)
        resolution = _resolution(service, terminal)
        assert resolution["inputs_read"] == ["control_completed_job:missing-prior-run"]
        assert "promotion_source_job_not_completed" in resolution["refusal_reasons"]
        assert resolution["classification"] == "not_established"
        assert terminal.progress["eval_safety_counters"]["near_miss_count"] == 0
        # Existing retry path reconciles the same safety decision once.
        service._process_control_job(job)
        retried = service._control_store.get_job(launch.job_id)
        assert retried.progress["eval_safety_counters"] == terminal.progress["eval_safety_counters"]
    finally:
        service.close()


@pytest.fixture(scope="module")
def produced_station(tmp_path_factory):
    """Retain an existing actual control producer run for exact downstream source reads."""
    captured = {}
    service_type = _build_control_service.__globals__["ControlPlaneService"]
    real_close = service_type.close
    real_process = service_type._process_control_job

    def keep_service(self):
        captured["service"] = self

    def process(self, job):
        real_process(self, job)
        if job.kind == "natural_language_run":
            captured["source_run_id"] = job.run_id
            captured["job_id"] = job.job_id

    with pytest.MonkeyPatch.context() as patches:
        patches.setattr(service_type, "close", keep_service)
        patches.setattr(service_type, "_process_control_job", process)
        asyncio.run(_worker_example(patches, tmp_path_factory.mktemp("near-miss-source"), "missing"))
    try:
        yield captured
    finally:
        real_close(captured["service"])


def _attempt_from_produced_source(produced_station, *, candidate_hash=None, world_hash=None):
    service = produced_station["service"]
    source_run_id = produced_station["source_run_id"]
    source_job = service._control_store.get_job(produced_station["job_id"])
    compiled_ref = source_job.progress["compiled_recursive_generation_cycle_ref"]
    compiled = canon.from_canonical_bytes(service._artifact_store.get_bytes(compiled_ref))
    leaf = next(row for row in compiled["recursive_run"]["nodes"] if row["cycle_run"] is not None)
    candidate = leaf["cycle_run"]["candidate_summaries"][0]
    source_id, intake = _field_pilot_intake(service)
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
    launch = service.launch_workflow_run(
        WorkflowRunRequest(
            data_source={"data_snapshot_ref": source_id},
            params={"evaluation_safety_attempt": intake},
        ),
        principal=RuntimePrincipal.from_user_claims(_fixture_claims()),
    )
    return service, source_job, compiled_ref, launch


def test_existing_generation_producer_is_read_before_candidate_absence_is_reported(
    produced_station,
):
    service, source_job, compiled_ref, launch = _attempt_from_produced_source(produced_station)
    service._process_control_job(service._control_store.get_job(launch.job_id))
    terminal = service._control_store.get_job(launch.job_id)
    result = _resolution(service, terminal)
    assert result["inputs_read_scope"] == "source_selection_only"
    assert f"cas_bytes:{compiled_ref}" in result["inputs_read"]
    assert f"cas_manifest:{source_job.progress['manifest_ref']}" in result["inputs_read"]
    assert any(value.startswith("terminal_trace:") for value in result["inputs_read"])
    assert "promotion_source_candidate_receipt_not_unique" in result["refusal_reasons"]
    assert result["classification"] == "not_established"
    assert terminal.progress["eval_safety_counters"]["near_miss_count"] == 0


def test_compiled_source_content_binding_survives_retained_semantic_markers(
    produced_station, monkeypatch
):
    service, _, compiled_ref, launch = _attempt_from_produced_source(produced_station)
    original = service._artifact_store.get_bytes

    def rebound_bytes(ref):
        body = original(ref)
        # Identical parsed values and self-hash; changed CAS bytes must still refuse.
        return body + b" " if str(ref) == compiled_ref else body

    monkeypatch.setattr(service._artifact_store, "get_bytes", rebound_bytes)
    service._process_control_job(service._control_store.get_job(launch.job_id))
    terminal = service._control_store.get_job(launch.job_id)
    result = _resolution(service, terminal)
    assert "promotion_source_artifact_binding_mismatch" in result["refusal_reasons"], (
        "source CAS binding property was removed"
    )
    assert f"cas_bytes:{compiled_ref}" in result["source_selection_read_attempts"]
    assert result["classification"] == "not_established"


def test_matching_candidate_label_cannot_select_foreign_candidate_bytes(produced_station):
    service, _, _, launch = _attempt_from_produced_source(
        produced_station, candidate_hash="sha256:" + "a" * 64
    )
    service._process_control_job(service._control_store.get_job(launch.job_id))
    result = _resolution(service, service._control_store.get_job(launch.job_id))
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
    service, _, compiled_ref, launch = _attempt_from_produced_source(produced_station)
    original = service._artifact_store.get_manifest

    def wrong_manifest(ref):
        manifest = original(ref)
        if str(ref) != compiled_ref:
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
    service._process_control_job(service._control_store.get_job(launch.job_id))
    result = _resolution(service, service._control_store.get_job(launch.job_id))
    original_failure = {
        "artifact_id": "Manifest artifact_id mismatch",
        "integrity": "Manifest integrity mismatch",
        "byte_size": "Manifest byte_size mismatch",
        "media_type": "promotion_source_artifact_binding_mismatch",
        "artifact_schema": "promotion_source_artifact_binding_mismatch",
    }[changed_field]
    assert any(original_failure in reason for reason in result["refusal_reasons"])
    assert f"cas_bytes:{compiled_ref}" in result["source_selection_read_attempts"]
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


def test_real_negative_n9_source_reaches_offer_cas_and_authoritative_classifier(
    produced_station, monkeypatch,
):
    from polisyos.core.contracts.control import NaturalLanguageRunRequest
    from polisyos.pdc import gy_artifact_self_identity_projection, gy_content_hash
    from polisyos.runtime.http.services.control import evaluation_safety as adapter
    from polisyos.runtime.http.services.control import generation_cycle as generation
    from polisyos.runtime.quality import evaluation_safety as es
    from polisyos.runtime.quality import promotion_sequence as n9
    from tests.unit.runtime.quality.test_generation_cycle import (
        REPO_ROOT,
        _positive_epoch_admitted_batch,
    )
    from tests.unit.runtime.quality.test_promotion_sequence import _value_receipt

    service = produced_station["service"]
    prior_job = service._control_store.get_job(produced_station["job_id"])
    compiled = generation.CompiledRecursiveGenerationCycleRun.model_validate(
        canon.from_canonical_bytes(service._artifact_store.get_bytes(
            prior_job.progress["compiled_recursive_generation_cycle_ref"]
        ))
    )
    leaf = compiled.recursive_run.leaf_nodes[0]
    summary = leaf.cycle_run.candidate_summaries[0]
    value = _value_receipt().model_copy(update={
        "candidate_id": summary.candidate_id, "evaluation_mode": "field_pilot",
    })
    # Appoint only the test epoch verifier; N9 and its promotion refusal run unchanged.
    admitted = _positive_epoch_admitted_batch(
        runtime=service._promotion_runtime, problem=compiled.design_problem, summaries=(summary,),
    )
    monkeypatch.setattr(n9, "_legacy_policy_promotion_callers", lambda _root: ())
    observation = n9.CanonicalN9PromotionPort(
        promotion_runtime=service._promotion_runtime, repo_root=REPO_ROOT,
        context_provider=lambda _summary, _problem: {"value_receipt": value},
    )(admitted_batch=admitted, problem=compiled.design_problem)
    receipt = n9.CanonicalPromotionReceipt.model_validate(observation.receipts[0])
    assert observation.status == "not_promoted"
    assert receipt.owner_projection.open_world_gate is not None
    assert receipt.owner_projection.epoch_validity_projection is not None
    assert receipt.owner_projection.value_receipt.evaluation_mode == "field_pilot"

    # Reuse the real generated tree and install the actual N9 owner's negative output.
    cycle = leaf.cycle_run.model_copy(update={"promotion_port": observation})
    node = leaf.model_copy(update={"cycle_run": cycle})
    recursive = compiled.recursive_run.model_copy(update={"nodes": (node,)})
    recursive_values = gy_artifact_self_identity_projection(recursive)
    recursive_values.pop("leaf_nodes", None)
    recursive = type(recursive).model_validate({
        **recursive.model_dump(mode="json"), "content_hash": gy_content_hash(recursive_values),
    })
    revised = compiled.model_copy(update={"recursive_run": recursive})
    compiled_values = gy_artifact_self_identity_projection(revised)
    compiled_values["recursive_run"].pop("leaf_nodes", None)
    revised = type(compiled).model_validate({
        **revised.model_dump(mode="json"), "content_hash": gy_content_hash(compiled_values),
    })

    async def compiled_owner_output(**_kwargs):
        return revised

    monkeypatch.setattr(generation, "compile_and_run_recursive_generation_cycle", compiled_owner_output)
    source = asyncio.run(service.launch_nl_run(
        NaturalLanguageRunRequest(
            request=compiled.design_problem.nl_provenance.raw_request, llm_model="simulated-qwen",
        ), principal=RuntimePrincipal.from_user_claims(_fixture_claims()),
    ))
    source_job = service._control_store.get_job(source.job_id)
    service._process_control_job(source_job)
    completed = service._control_store.get_job(source.job_id)
    assert completed.state == "completed"
    selected = {"service": service, "source_run_id": source_job.run_id, "job_id": source.job_id}
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
    service._process_control_job(service._control_store.get_job(launch.job_id))
    terminal = service._control_store.get_job(launch.job_id)
    resolution = _resolution(service, terminal)
    assert calls, "real canonical classifier was never reached from persisted source"
    result = outcomes[0]
    assert result.classification_offer_ref is not None
    offer = es.EvalSafetyNearMissClassificationOffer.model_validate_json(
        service._artifact_store.get_bytes(result.classification_offer_ref.artifact_id)
    )
    assert offer.safety_semantic_hash == result.decision.safety.safety_semantic_hash
    assert resolution["selected_compiled_ref"] == compiled_ref
    if calls[0] is None:
        assert resolution["classification"] == "not_established"
        assert "canonical_promotion_replay_not_established" in resolution["refusal_reasons"]
    else:
        assert calls[0].promotion_safe_facet is False
        assert resolution["classification"] == "verified"
    assert result.decision.near_miss is False
    assert result.decision.safety.status == "blocked"
    assert terminal.progress["eval_safety_counters"]["near_miss_count"] == 0

    # The genuine prior source still exists, but is outside this deployment's selector.
    assert service._artifact_store.get_bytes(compiled_ref)
    _, _, _, outside_launch = _attempt_from_produced_source(
        selected, world_hash=value.world_model_record_content_hash,
    )
    service._evaluation_safety_promotion_sources = replace(
        service._evaluation_safety_promotion_sources,
        slot=EvaluationSafetyPromotionSourceSlot(),
    )
    prior_calls = tuple(calls)
    service._process_control_job(service._control_store.get_job(outside_launch.job_id))
    outside_terminal = service._control_store.get_job(outside_launch.job_id)
    outside = _resolution(service, outside_terminal)
    assert tuple(calls) == prior_calls
    assert outside["requested_source_run_ids"] == []
    assert outside["inputs_read"] == outside["source_selection_read_attempts"] == []
    assert outside["refusal_reasons"] == ["promotion_source_slot_empty"]
    assert "outside_deployment_selected_source_runs" in outside["unresolved_by_construction"]
    assert outside["classification"] == "not_established"
    assert outside_terminal.progress["eval_safety_counters"]["near_miss_count"] == 0
