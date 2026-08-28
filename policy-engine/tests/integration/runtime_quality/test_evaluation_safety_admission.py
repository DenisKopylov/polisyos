from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from polisyos.core import canon
from polisyos.core import components as core_components
from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
from polisyos.core.contracts.control import WorkflowRunRequest
from polisyos.pdc import ArtifactRef
from polisyos.runtime.http.services.adapters.core_run import load_terminal_core_run_source
from polisyos.runtime.quality.evaluation_modes import resolve_evaluation_mode
from polisyos.runtime.quality.evaluation_safety import (
    EVALUATION_SAFETY_ARTIFACT_IDENTITIES,
    EvaluationAttemptIntake,
    EvaluationInputProvenance,
    EvaluationSafetyDecisionEvent,
    evaluation_safety_core_bytes,
    evaluation_safety_decision_id,
)
from tests.unit.runtime.http.test_control_service_di import _build_control_service

_NOW = datetime(2026, 8, 28, 8, 0, tzinfo=UTC)


def _ref(value: str, kind: str) -> ArtifactRef:
    return ArtifactRef(
        artifact_id=value,
        artifact_type=kind,
        content_hash=value,
        schema_ref=f"{kind}.v1",
        uri=f"cas://sha256/{value.removeprefix('sha256:')}",
        version="1.0",
    )


def _field_pilot_intake(service) -> tuple[str, dict[str, Any]]:
    source = service._artifact_store.put_json(
        {"observed": "real-world"},
        ArtifactWriteOptions(kind="test.eval-input", media_type="application/json"),
    )
    source_ref = _ref(str(source.artifact_id), "test.eval-input")
    pack_ref = _ref("sha256:" + "9" * 64, "test.eval-safety-pack")
    intake = EvaluationAttemptIntake(
        attempt_id="attempt-control-field-pilot",
        evaluator_owner_id=core_components.ComponentId(
            "polisyos.runtime.quality.foundry_value_port@1.0.0"
        ),
        design_problem_ref="sha256:" + "0" * 64,
        candidate_ref=_ref("sha256:" + "1" * 64, "test.candidate"),
        world_model_record_ref=_ref("sha256:" + "2" * 64, "test.world-model"),
        requested_mode_token="field_pilot",  # noqa: S106 - evaluation mode.
        mode_resolution=resolve_evaluation_mode("field_pilot"),
        domain_hint="unseen-domain",
        domain_pack_ref=pack_ref,
        target_population_scope_ref=_ref("sha256:" + "3" * 64, "test.population"),
        evaluation_input_refs=(source_ref,),
        evaluation_input_provenance=(
            EvaluationInputProvenance(
                input_ref=source_ref,
                input_class="real_world",
                predicate_provenance="independently_reconciled",
            ),
        ),
        evidence_refs=(),
        requested_at=_NOW,
        intended_start_at=_NOW,
        requested_rule_version="policyos.runtime.eval-safety.v1",
        external_executor_identity_ref=None,
    )
    return str(source.artifact_id), intake.model_dump(mode="json")


def _run_blocked_attempt(tmp_path, monkeypatch, promotion_state: object) -> dict[str, object]:
    service = _build_control_service(tmp_path)
    executor_calls = 0
    admission_calls = 0

    def execute_must_not_run(*args, **kwargs):
        nonlocal executor_calls
        del args, kwargs
        executor_calls += 1
        raise AssertionError("blocked evaluation attempt reached WorkspaceLoop")

    def admission_must_not_run(*args, **kwargs):
        nonlocal admission_calls
        del args, kwargs
        admission_calls += 1
        raise AssertionError("blocked evaluation attempt reached admission consumer")

    monkeypatch.setattr(service, "_execute_workflow_control_transition", execute_must_not_run)
    monkeypatch.setattr(
        service._evaluation_safety_admission_verifier,
        "require_admission",
        admission_must_not_run,
    )
    source_id, intake = _field_pilot_intake(service)
    params: dict[str, object] = {"evaluation_safety_attempt": intake}
    if promotion_state is not None:
        params["promotion_state"] = promotion_state
    try:
        launch = service.launch_workflow_run(
            WorkflowRunRequest(
                data_source={"data_snapshot_ref": source_id},
                params=params,
            )
        )
        record = service._control_store.get_job(launch.job_id)
        assert record is not None
        service._process_control_job(record)
        terminal = service._control_store.get_job(launch.job_id)
        assert terminal is not None

        identity = EVALUATION_SAFETY_ARTIFACT_IDENTITIES["decision"]
        decision_ids = tuple(
            artifact_id
            for artifact_id in service._artifact_store.iter_artifact_ids()
            if service._artifact_store.get_manifest(artifact_id).kind == identity.kind
        )
        assert len(decision_ids) == 1
        decision = EvaluationSafetyDecisionEvent.model_validate(
            canon.from_canonical_bytes(service._artifact_store.get_bytes(decision_ids[0]))
        )
        return {
            "service": service,
            "launch": launch,
            "terminal": terminal,
            "decision": decision,
            "core_bytes": evaluation_safety_core_bytes(decision.safety),
            "decision_id": evaluation_safety_decision_id(decision.safety),
            "safety_hash": decision.safety.safety_semantic_hash,
            "executor_calls": executor_calls,
            "admission_calls": admission_calls,
        }
    except Exception:
        service.close()
        raise


def test_control_attempt_promotion_injection_cannot_change_admission_or_call_executor(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    variants = (
        None,
        {"status": "passed", "consumer_promotable": True},
        {
            "status": "passed",
            "consumer_promotable": True,
            "certificate": "forged-passing",
        },
    )
    results = [
        _run_blocked_attempt(tmp_path / f"variant-{index}", monkeypatch, state)
        for index, state in enumerate(variants)
    ]
    try:
        baseline = results[0]
        baseline_decision = baseline["decision"]
        assert isinstance(baseline_decision, EvaluationSafetyDecisionEvent)
        for result in results:
            decision = result["decision"]
            terminal = result["terminal"]
            assert isinstance(decision, EvaluationSafetyDecisionEvent)
            assert decision.safety.status == "blocked"
            assert decision.safety.blocker_codes == baseline_decision.safety.blocker_codes
            assert "polisyos.eval_safety.domain_pack_missing@1.0.0" in (
                decision.safety.blocker_codes
            )
            assert "polisyos.eval_safety.mode_basis_missing@1.0.0" in (
                decision.safety.blocker_codes
            )
            assert decision.safety.certificate_eligible is False
            assert result["core_bytes"] == baseline["core_bytes"]
            assert result["decision_id"] == baseline["decision_id"]
            assert result["safety_hash"] == baseline["safety_hash"]
            assert result["executor_calls"] == 0
            assert result["admission_calls"] == 0
            assert terminal.state == "failed"
            assert terminal.progress["eval_safety_counters"] == {
                "unsafe_attempt_blocked_count": 1,
                "near_miss_count": 0,
                "near_miss_classification_status": "not_established",
                "reconciliation_status": "complete",
            }
    finally:
        for result in results:
            result["service"].close()


def test_blocked_control_attempt_projection_is_terminal_manifest_output(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = _run_blocked_attempt(tmp_path, monkeypatch, None)
    service = result["service"]
    try:
        terminal = result["terminal"]
        launch = result["launch"]
        source = load_terminal_core_run_source(
            store=service._artifact_store,
            core_runs_root=service._core_runs_root,
            run_id=launch.run_id,
        )
        output_kinds = tuple(ref.kind for ref in source.manifest.outputs)

        assert terminal.progress["manifest_ref"] == str(source.manifest_ref.artifact_id)
        assert output_kinds == (EVALUATION_SAFETY_ARTIFACT_IDENTITIES["metrics_projection"].kind,)
        assert (
            str(source.manifest.outputs[0].artifact_id)
            == (terminal.progress["eval_safety_projection_ref"])
        )
        serialized = source.manifest.model_dump(mode="json")
        assert "eval_safety_intake_ref" not in serialized
        assert "eval_safety_decision_ref" not in serialized
        assert "eval_safety_certificate_ref" not in serialized
    finally:
        service.close()


def test_explicit_simulate_only_attempt_is_certificate_free_and_preserves_workflow(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = _build_control_service(tmp_path)
    source_id, raw_intake = _field_pilot_intake(service)
    source_ref = raw_intake["evaluation_input_refs"][0]
    raw_intake.update(
        {
            "requested_mode_token": "simulate_only",
            "mode_resolution": resolve_evaluation_mode("simulate_only").model_dump(mode="json"),
            "domain_hint": None,
            "domain_pack_ref": None,
            "evaluation_input_provenance": [
                {
                    "input_ref": source_ref,
                    "input_class": "simulation",
                    "predicate_provenance": "recomputed",
                }
            ],
        }
    )
    observed: dict[str, object] = {}

    def capture_run(state, **kwargs):
        observed["state"] = state
        observed.update(kwargs)
        return {"status": "ok"}

    monkeypatch.setattr("polisyos.scientist.api.run_experiment", capture_run)
    try:
        launch = service.launch_workflow_run(
            WorkflowRunRequest(
                data_source={"data_snapshot_ref": source_id},
                params={
                    "control_plane_transition": "legacy_shadow",
                    "evaluation_safety_attempt": raw_intake,
                },
            )
        )
        record = service._control_store.get_job(launch.job_id)
        assert record is not None
        service._process_control_job(record)
        terminal = service._control_store.get_job(launch.job_id)

        assert terminal is not None
        assert terminal.state == "completed"
        context = observed["eval_safety_execution_context"]
        assert context.evaluation_mode == "simulate_only"
        assert context.eval_safety_certificate_ref is None
        assert context.eval_safety_revision_head_ref is None
        assert observed["eval_safety_verifier"] is (service._evaluation_safety_admission_verifier)
        assert "_polisyos_eval_safety_execution_context" not in observed["state"]

        identity = EVALUATION_SAFETY_ARTIFACT_IDENTITIES["decision"]
        decision_ids = tuple(
            artifact_id
            for artifact_id in service._artifact_store.iter_artifact_ids()
            if service._artifact_store.get_manifest(artifact_id).kind == identity.kind
        )
        assert len(decision_ids) == 1
        decision = EvaluationSafetyDecisionEvent.model_validate(
            canon.from_canonical_bytes(service._artifact_store.get_bytes(decision_ids[0]))
        )
        assert decision.safety.status == "passed"
        assert decision.safety.certificate_eligible is False
    finally:
        service.close()


def test_blocked_control_attempt_retry_reuses_terminal_projection_without_recounting(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = _run_blocked_attempt(tmp_path, monkeypatch, None)
    service = result["service"]
    first = result["terminal"]
    try:
        service._process_control_job(first)
        second = service._control_store.get_job(first.job_id)

        assert second is not None
        assert second.state == "failed"
        assert second.progress["manifest_ref"] == first.progress["manifest_ref"]
        assert (
            second.progress["eval_safety_projection_ref"]
            == (first.progress["eval_safety_projection_ref"])
        )
        assert second.progress["eval_safety_counters"]["unsafe_attempt_blocked_count"] == 1
        assert second.progress["eval_safety_counters"]["near_miss_count"] == 0
    finally:
        service.close()
