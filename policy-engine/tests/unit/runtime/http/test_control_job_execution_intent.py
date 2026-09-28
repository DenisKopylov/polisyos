from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from polisyos.core.components import ComponentId
from polisyos.core.contracts.control import NaturalLanguageRunRequest
from polisyos.pdc._impl.gy_waist import ArtifactRef
from polisyos.runtime.http.errors import RuntimeHTTPError
from polisyos.runtime.http.execution_policy import RuntimePrincipal
from polisyos.runtime.http.resilience import GuardedDependencyProxy
from polisyos.runtime.quality.evaluation_modes import resolve_evaluation_mode
from polisyos.runtime.quality.evaluation_safety import EvaluationAttemptIntake
from tests.unit.runtime.http.control_service_test_support import (
    bound_nl_authorization_proof,
)
from tests.unit.runtime.http.test_control_service_di import (
    _build_control_service,
    _fixture_claims,
)


def _artifact_ref(kind: str, digit: str) -> ArtifactRef:
    digest = "sha256:" + digit * 64
    return ArtifactRef(
        artifact_id=digest,
        artifact_type=kind,
        content_hash=digest,
        schema_ref=f"{kind}.v1",
        uri=f"cas://sha256/{digest.removeprefix('sha256:')}",
        version="1.0",
    )


def _field_pilot_intake() -> EvaluationAttemptIntake:
    requested_at = datetime.now(UTC)
    return EvaluationAttemptIntake(
        attempt_id="attempt-r5-durable-intent",
        evaluator_owner_id=ComponentId("polisyos.runtime.quality.foundry_value_port@1.0.0"),
        design_problem_ref="sha256:" + "1" * 64,
        candidate_ref=_artifact_ref("test.candidate", "2"),
        world_model_record_ref=_artifact_ref("test.world_model_record", "3"),
        requested_mode_token="field_pilot",  # noqa: S106
        mode_resolution=resolve_evaluation_mode("field_pilot"),
        domain_hint=None,
        domain_pack_ref=None,
        target_population_scope_ref=_artifact_ref("test.population", "4"),
        evaluation_input_refs=(),
        evaluation_input_provenance=(),
        evidence_refs=(),
        requested_at=requested_at,
        intended_start_at=requested_at,
        requested_rule_version=None,
        external_executor_identity_ref=None,
    )


def _job_created_event(service, job_id: str) -> tuple[int, dict[str, object]]:
    with service._control_store._sqlite_connection() as connection:  # noqa: SLF001
        rows = connection.execute(
            "SELECT event_id, payload_json FROM control_job_events "
            "WHERE job_id = ? AND event_type = 'job_created' ORDER BY event_id",
            (job_id,),
        ).fetchall()
    assert len(rows) == 1
    return int(rows[0][0]), json.loads(str(rows[0][1]))


def _outbox_payload(service, job_id: str) -> dict[str, object]:
    record = service._control_store.get_job_created_outbox_event(job_id)  # noqa: SLF001
    assert record is not None
    return dict(record.payload)


def _valid_intake_for_mode(mode: str) -> EvaluationAttemptIntake:
    original = _field_pilot_intake()
    return original.model_copy(
        update={
            "requested_mode_token": mode,
            "mode_resolution": resolve_evaluation_mode(mode),
        }
    )


@pytest.mark.asyncio
async def test_plain_nl_job_persists_candidate_intent_and_reaches_candidate_compiler(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = _build_control_service(tmp_path)
    try:
        request = NaturalLanguageRunRequest(
            request="Explore a policy option as a candidate.",
            llm_model="simulated-qwen",
            run_budget_usd=2.0,
            per_model_budget_usd=1.0,
            execution_plan={
                "stop_criteria": {"min_delta_improvement": 0.01},
            },
        )
        launch = await service.launch_nl_run(
            request,
            principal=RuntimePrincipal.from_user_claims(_fixture_claims()),
            authorization_proof=bound_nl_authorization_proof(_fixture_claims(), request),
        )
        record = service._control_store.get_job(launch.job_id)  # noqa: SLF001
        assert record is not None
        status = service.get_job_status(launch.job_id)
        assert record.state == status.state == "pending"
        assert record.progress["state"] == status.progress["state"] == "pending"
        assert service._control_store.list_job_state_transitions(launch.job_id) == [  # noqa: SLF001
            "pending"
        ]
        created_event = service._control_store.get_job_created_event_payload(  # noqa: SLF001
            launch.job_id
        )
        assert created_event["state"] == "pending"
        outbox_payload = _outbox_payload(service, launch.job_id)
        assert outbox_payload["state"] == "pending"
        pending_admission_transitions = [
            item.event
            for item in service._control_store.list_diagnostic_events(  # noqa: SLF001
                job_id=launch.job_id
            )
            if item.event.event_type == "polisyos.runtime.diagnostic.phase_transition.v1"
        ]
        assert len(pending_admission_transitions) == 1
        assert pending_admission_transitions[0].state_after == "pending"
        payload = service._load_payload_ref(str(record.payload_ref))  # noqa: SLF001
        _, created_event = _job_created_event(service, launch.job_id)

        binding = payload.get("execution_intent_binding")
        assert isinstance(binding, dict)
        assert binding.get("intent_band") == "candidate_only"
        assert created_event.get("execution_intent_binding") == binding
        assert created_event.get("payload_ref") == record.payload_ref
        outbox_payload = _outbox_payload(service, launch.job_id)
        assert outbox_payload.get("execution_intent_binding") == binding
        assert outbox_payload.get("payload_ref") == record.payload_ref

        compiler_intents: list[str | None] = []

        async def compiler_probe(**kwargs: object) -> object:
            compiler_intents.append(
                str(kwargs.get("execution_intent"))
                if kwargs.get("execution_intent") is not None
                else None
            )
            raise RuntimeError("candidate_control_reached_compiler")

        monkeypatch.setattr(service, "compile_and_run_recursive_generation_cycle", compiler_probe)
        service._process_control_job(record)  # noqa: SLF001

        completed = service._control_store.get_job(launch.job_id)  # noqa: SLF001
        assert completed is not None
        assert compiler_intents == ["candidate_only"]
        assert completed.error_message == "candidate_control_reached_compiler"
    finally:
        service.close()


@pytest.mark.asyncio
async def test_nl_launch_requires_served_proof_for_candidate_and_protected_requests(
    tmp_path,
) -> None:
    service = _build_control_service(tmp_path)
    principal = RuntimePrincipal.from_user_claims(_fixture_claims())
    try:
        with pytest.raises(ValueError, match="nl_route_authorization_proof_not_established"):
            await service.launch_nl_run(
                NaturalLanguageRunRequest(
                    request="A direct service launch must carry the route proof.",
                    llm_model="simulated-qwen",
                ),
                principal=principal,
            )

        with pytest.raises(ValueError, match="nl_route_authorization_proof_not_established"):
            await service.launch_nl_run(
                NaturalLanguageRunRequest(
                    request="A protected service launch must carry the route proof.",
                    llm_model="simulated-qwen",
                    context={
                        "evaluation_safety_attempt": _field_pilot_intake().model_dump(
                            mode="json"
                        )
                    },
                ),
                principal=principal,
            )

    finally:
        service.close()


@pytest.mark.asyncio
async def test_served_authorization_proof_binds_exact_body_and_query_bytes(tmp_path) -> None:
    service = _build_control_service(tmp_path)
    claims = _fixture_claims()
    principal = RuntimePrincipal.from_user_claims(claims)
    request = NaturalLanguageRunRequest(
        request="Bind the authorization proof to this exact request.",
        llm_model="simulated-qwen",
    )
    proof = bound_nl_authorization_proof(claims, request)
    try:
        with pytest.raises(ValueError, match="nl_route_authorization_resource_digest_mismatch"):
            await service.launch_nl_run(
                request.model_copy(update={"request": "A substituted request."}),
                principal=principal,
                authorization_proof=proof,
            )

        with pytest.raises(ValueError, match="nl_route_authorization_resource_digest_mismatch"):
            await service.launch_nl_run(
                request,
                principal=principal,
                authorization_proof=proof,
                authorization_request_body=b"",
            )

        with pytest.raises(ValueError, match="nl_route_authorization_resource_digest_mismatch"):
            await service.launch_nl_run(
                request,
                principal=principal,
                authorization_proof=proof,
                authorization_query_bytes=b"tenant_id=foreign",
            )

        foreign_principal = RuntimePrincipal(
            subject="user-foreign",
            tenant_id=claims.tenant_id,
            cell_id=claims.cell_id,
            roles=principal.roles,
            authenticated=True,
        )
        with pytest.raises(ValueError, match="nl_route_authorization_actor_binding_mismatch"):
            await service.launch_nl_run(
                request,
                principal=foreign_principal,
                authorization_proof=proof,
            )

        foreign_tenant_principal = RuntimePrincipal(
            subject=principal.subject,
            tenant_id="tenant-foreign",
            cell_id=principal.cell_id,
            roles=principal.roles,
            authenticated=True,
        )
        with pytest.raises(ValueError, match="nl_route_authorization_actor_binding_mismatch"):
            await service.launch_nl_run(
                request,
                principal=foreign_tenant_principal,
                authorization_proof=proof,
            )
    finally:
        service.close()


def test_nl_request_snapshot_digest_profile_accepts_float_and_type_key() -> None:
    from polisyos.runtime.http.services.control.run_lifecycle import (
        _NL_REQUEST_SNAPSHOT_DIGEST_PROFILE,
        _NL_REQUEST_SNAPSHOT_SCHEMA,
        _nl_request_snapshot_content_hash,
    )

    snapshot = {
        "schema_version": _NL_REQUEST_SNAPSHOT_SCHEMA,
        "digest_profile": _NL_REQUEST_SNAPSHOT_DIGEST_PROFILE,
        "request": {
            "context": {"_type": "caller-owned-context-key"},
            "run_budget_usd": 2.0,
        },
        "normalized_llm_models": ["simulated-qwen"],
    }

    digest = _nl_request_snapshot_content_hash(snapshot)

    assert digest == (
        "sha256:56ab3d64aaacfd3fc0175f89f499c10f31f9082d2191181e3635f7082a615ded"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "nonfinite_value",
    [float("nan"), float("inf"), float("-inf")],
    ids=["nan", "positive-infinity", "negative-infinity"],
)
async def test_served_launch_rejects_nonfinite_context_before_enqueue(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
    nonfinite_value: float,
) -> None:
    service = _build_control_service(tmp_path)
    claims = _fixture_claims()
    principal = RuntimePrincipal.from_user_claims(claims)
    compiler_calls: list[str] = []
    enqueue_calls: list[str] = []
    original_enqueue = service._enqueue_job  # noqa: SLF001

    async def compiler_probe(**_kwargs: object) -> object:
        compiler_calls.append("candidate_compiler")
        raise RuntimeError("nonfinite_candidate_reached_compiler")

    def enqueue_probe(**kwargs: object) -> object:
        enqueue_calls.append("enqueue")
        return original_enqueue(**kwargs)  # noqa: SLF001

    monkeypatch.setattr(service, "compile_and_run_recursive_generation_cycle", compiler_probe)
    monkeypatch.setattr(service, "_enqueue_job", enqueue_probe)  # noqa: SLF001
    try:
        with service._control_store._sqlite_connection() as connection:  # noqa: SLF001
            before_count = int(connection.execute("SELECT COUNT(*) FROM control_jobs").fetchone()[0])

        request = NaturalLanguageRunRequest(
            request="A non-finite context must not be silently normalized into a candidate.",
            llm_model="simulated-qwen",
            context={"measurement": nonfinite_value},
        )
        proof = bound_nl_authorization_proof(claims, request)
        with pytest.raises(RuntimeHTTPError) as raised:
            await service.launch_nl_run(
                request,
                principal=principal,
                authorization_proof=proof,
            )

        assert raised.value.code == "authorization_binding_selector_invalid"
        with service._control_store._sqlite_connection() as connection:  # noqa: SLF001
            after_count = int(connection.execute("SELECT COUNT(*) FROM control_jobs").fetchone()[0])
        assert after_count == before_count
        assert enqueue_calls == []
        assert compiler_calls == []
    finally:
        service.close()


@pytest.mark.asyncio
async def test_float_snapshot_tamper_fails_before_worker_with_markers_intact(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = _build_control_service(tmp_path)
    claims = _fixture_claims()
    request = NaturalLanguageRunRequest(
        request="Keep the exact numeric request bound to its served authorization proof.",
        llm_model="simulated-qwen",
        run_budget_usd=2.0,
        per_model_budget_usd=1.0,
        execution_plan={
            "stop_criteria": {"min_delta_improvement": 0.01},
        },
    )
    try:
        launch = await service.launch_nl_run(
            request,
            principal=RuntimePrincipal.from_user_claims(claims),
            authorization_proof=bound_nl_authorization_proof(claims, request),
        )
        record = service._control_store.get_job(launch.job_id)  # noqa: SLF001
        assert record is not None
        reached: list[str] = []

        async def compiler_probe(**_kwargs: object) -> object:
            reached.append("candidate_compiler")
            raise RuntimeError("tampered_request_reached_candidate_compiler")

        original_load = service._load_payload_ref  # noqa: SLF001

        def load_tampered_request(payload_ref: str) -> dict[str, object]:
            value = original_load(payload_ref)
            if payload_ref == record.payload_ref:
                snapshot = value.get("nl_request_snapshot")
                assert isinstance(snapshot, dict)
                request_data = snapshot.get("request")
                assert isinstance(request_data, dict)
                request_data["run_budget_usd"] = 3.0
                # Keep the authorization receipt and all intent/event markers intact.
                assert value.get("nl_authorization_receipt")
                assert value.get("execution_intent_binding")
            return value

        monkeypatch.setattr(service, "_load_payload_ref", load_tampered_request)
        monkeypatch.setattr(service, "compile_and_run_recursive_generation_cycle", compiler_probe)
        service._process_control_job(record)  # noqa: SLF001

        terminal = service._control_store.get_job(launch.job_id)  # noqa: SLF001
        assert terminal is not None
        assert terminal.state == "failed"
        assert terminal.error_message == "nl_job_execution_intent_not_established"
        assert reached == []
    finally:
        service.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "tamper",
    [
        "event_missing",
        "event_mismatched",
        "outbox_missing",
        "outbox_mismatched",
        "capability_actor_mismatched",
        "payload_authorization_receipt_missing",
        "payload_authorization_receipt_foreign",
    ],
)
async def test_protected_intent_event_tamper_blocks_before_evaluation_safety_or_n4(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
    tamper: str,
) -> None:
    service = _build_control_service(tmp_path)
    try:
        request = NaturalLanguageRunRequest(
            request="Evaluate this candidate for a field pilot.",
            llm_model="simulated-qwen",
            context={
                "evaluation_safety_attempt": _field_pilot_intake().model_dump(
                    mode="json"
                )
            },
        )
        launch = await service.launch_nl_run(
            request,
            principal=RuntimePrincipal.from_user_claims(_fixture_claims()),
            authorization_proof=bound_nl_authorization_proof(_fixture_claims(), request),
        )
        record = service._control_store.get_job(launch.job_id)  # noqa: SLF001
        assert record is not None
        payload = service._load_payload_ref(str(record.payload_ref))  # noqa: SLF001
        binding = payload.get("execution_intent_binding")
        assert isinstance(binding, dict)
        assert binding.get("intent_band") == "eval_safety_required"

        event_id, created_event = _job_created_event(service, launch.job_id)
        if tamper == "event_missing":
            created_event.pop("execution_intent_binding", None)
        elif tamper == "event_mismatched":
            event_binding = created_event.get("execution_intent_binding")
            assert isinstance(event_binding, dict)
            event_binding["intent_band"] = "candidate_only"
        with service._control_store._sqlite_connection() as connection:  # noqa: SLF001
            if tamper.startswith("event_"):
                connection.execute(
                    "UPDATE control_job_events SET payload_json = ? "
                    "WHERE event_id = ? AND job_id = ? AND event_type = 'job_created'",
                    (json.dumps(created_event, sort_keys=True), event_id, launch.job_id),
                )
            elif tamper.startswith("outbox_"):
                row = connection.execute(
                    "SELECT event_id, payload_json FROM control_outbox_events "
                    "WHERE topic = 'control.job.created' AND event_key = ? AND job_id = ?",
                    (f"{launch.job_id}:job_created", launch.job_id),
                ).fetchone()
                assert row is not None
                outbox = json.loads(str(row[1]))
                if tamper == "outbox_missing":
                    outbox.pop("execution_intent_binding", None)
                else:
                    outbox["execution_intent_binding"]["intent_band"] = "candidate_only"
                connection.execute(
                    "UPDATE control_outbox_events SET payload_json = ? WHERE event_id = ?",
                    (json.dumps(outbox, sort_keys=True), row[0]),
                )
            elif tamper == "capability_actor_mismatched":
                original_load = service._load_payload_ref  # noqa: SLF001

                def load_foreign_manifest(payload_ref: str) -> dict[str, object]:
                    value = original_load(payload_ref)
                    if payload_ref == record.capability_manifest_ref:
                        actor = value.get("actor")
                        assert isinstance(actor, dict)
                        actor["tenant_id"] = "tenant-foreign"
                    return value

                monkeypatch.setattr(service, "_load_payload_ref", load_foreign_manifest)
            else:
                original_load = service._load_payload_ref  # noqa: SLF001

                def load_tampered_payload(payload_ref: str) -> dict[str, object]:
                    value = original_load(payload_ref)
                    if payload_ref == record.payload_ref:
                        if tamper == "payload_authorization_receipt_missing":
                            value.pop("nl_authorization_receipt", None)
                        else:
                            receipt = value.get("nl_authorization_receipt")
                            assert isinstance(receipt, dict)
                            snapshot = receipt.get("permission_snapshot")
                            assert isinstance(snapshot, dict)
                            snapshot["subject"] = "user-foreign"
                    return value

                monkeypatch.setattr(service, "_load_payload_ref", load_tampered_payload)
            connection.commit()

        reached: list[str] = []

        def forbidden_eval_safety(**_kwargs: object) -> object:
            reached.append("evaluation_safety")
            raise RuntimeError("protected_intent_reached_evaluation_safety_without_binding")

        async def forbidden_compiler(**_kwargs: object) -> object:
            reached.append("n4")
            raise RuntimeError("protected_intent_reached_n4_without_binding")

        monkeypatch.setattr(service, "_admit_evaluation_safety_attempt", forbidden_eval_safety)
        monkeypatch.setattr(service, "compile_and_run_recursive_generation_cycle", forbidden_compiler)
        service._process_control_job(record)  # noqa: SLF001

        blocked = service._control_store.get_job(launch.job_id)  # noqa: SLF001
        assert blocked is not None
        assert blocked.state == "failed"
        assert blocked.error_message == "nl_job_execution_intent_not_established"
        assert reached == []
    finally:
        service.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("context", "expected_band"),
    [
        ({"evaluation_safety_attempt": {"requested_mode_token": "field_pilot "}}, "not_established"),
        ({"evaluation_safety_attempt": {"requested_mode_token": "field_pilot"}}, "eval_safety_required"),
    ],
)
async def test_unestablished_attempt_band_refuses_before_evaluation_safety_or_n4(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
    context: dict[str, object],
    expected_band: str,
    ) -> None:
    service = _build_control_service(tmp_path)
    try:
        request = NaturalLanguageRunRequest(
            request="Keep an incomplete protected intent from becoming a candidate run.",
            llm_model="simulated-qwen",
            context=context,
        )
        launch = await service.launch_nl_run(
            request,
            principal=RuntimePrincipal.from_user_claims(_fixture_claims()),
            authorization_proof=bound_nl_authorization_proof(_fixture_claims(), request),
        )
        record = service._control_store.get_job(launch.job_id)  # noqa: SLF001
        assert record is not None
        payload = service._load_payload_ref(str(record.payload_ref))  # noqa: SLF001
        binding = payload.get("execution_intent_binding")
        assert isinstance(binding, dict)
        assert binding.get("intent_band") == expected_band
        assert binding.get("admission_status") == "not_established"

        status = service.get_job_status(launch.job_id)
        assert record.state == status.state == "failed"
        assert record.finished_at is not None
        assert record.lease_owner is None
        assert record.progress["state"] == status.progress["state"] == "failed"
        assert status.progress["failure_code"] == "nl_job_execution_intent_not_established"
        assert service._control_store.get_job_created_event_payload(  # noqa: SLF001
            launch.job_id
        )["state"] == "failed"
        assert _outbox_payload(service, launch.job_id)["state"] == "failed"
        assert service._control_store.list_job_state_transitions(launch.job_id) == [  # noqa: SLF001
            "failed"
        ]
        admission_transitions = [
            item.event
            for item in service._control_store.list_diagnostic_events(  # noqa: SLF001
                job_id=launch.job_id
            )
            if item.event.event_type == "polisyos.runtime.diagnostic.phase_transition.v1"
        ]
        assert len(admission_transitions) == 1
        assert admission_transitions[0].state_after == "failed"
        assert service._control_store.lease_next_job(  # noqa: SLF001
            worker_id="r5-unestablished-intent-probe"
        ) is None

        reached: list[str] = []

        def forbidden_eval_safety(**_kwargs: object) -> object:
            reached.append("evaluation_safety")
            raise RuntimeError("unestablished_intent_reached_evaluation_safety")

        async def forbidden_compiler(**_kwargs: object) -> object:
            reached.append("n4")
            raise RuntimeError("unestablished_intent_reached_n4")

        monkeypatch.setattr(service, "_admit_evaluation_safety_attempt", forbidden_eval_safety)
        monkeypatch.setattr(service, "compile_and_run_recursive_generation_cycle", forbidden_compiler)
        service._process_control_job(record)  # noqa: SLF001

        failed = service._control_store.get_job(launch.job_id)  # noqa: SLF001
        assert failed is not None
        assert failed.state == "failed"
        assert failed.error_message == "nl_job_execution_intent_not_established"
        assert reached == []
    finally:
        service.close()


@pytest.mark.asyncio
async def test_data_trust_band_keeps_candidate_compute_and_persists_bridge_limitation(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from polisyos.runtime.http.services.control.generation_cycle import (
        N4CandidateProposalExecution,
    )
    from polisyos.runtime.quality.design_generation import (
        DesignGenerationOrganRun,
        GenerationDiversityReport,
        GenerationUnderAResult,
        ModelProfilePreflight,
    )
    from polisyos.runtime.quality.generation_cycle import gy_content_hash
    from tests.unit.runtime.quality.test_generation_cycle import _problem

    problem = _problem("r5_data_trust_dispatch")
    terminal_generation = GenerationUnderAResult(
        status="generation_unavailable",
        design_problem_ref=gy_content_hash(problem.model_dump(mode="json")),
        model_id="simulated-qwen",
        preflight=ModelProfilePreflight(
            status="gateway_unavailable",
            model_id="simulated-qwen",
            supported_model_ids=("simulated-qwen",),
            reason="test_terminal",
        ),
        diversity_report=GenerationDiversityReport(
            min_required=1,
            candidate_count=0,
            unique_diversity_key_count=0,
        ),
    )
    compiler_result = N4CandidateProposalExecution(
        design_problem=problem,
        proposal=DesignGenerationOrganRun(result=terminal_generation),
    )
    request = NaturalLanguageRunRequest(
        request="Explore a retrospective policy option as a candidate.",
        llm_model="simulated-qwen",
        context={
            "evaluation_safety_attempt": _valid_intake_for_mode(
                "retrospective"
            ).model_dump(mode="json"),
            "data_trust_admission": {
                "status": "verified",
                "tenant_id": "tenant-foreign",
            },
        },
    )
    service = _build_control_service(tmp_path)
    try:
        launch = await service.launch_nl_run(
            request,
            principal=RuntimePrincipal.from_user_claims(_fixture_claims()),
            authorization_proof=bound_nl_authorization_proof(_fixture_claims(), request),
        )
        record = service._control_store.get_job(launch.job_id)  # noqa: SLF001
        assert record is not None
        compiler_intents: list[object] = []

        async def candidate_compiler(**kwargs: object) -> object:
            compiler_intents.append(kwargs.get("execution_intent"))
            assert kwargs.get("root_evaluation_context") is None
            return compiler_result

        def forbidden_eval_safety(**_kwargs: object) -> object:
            pytest.fail("DataTrust intent was substituted into the EvalSafety owner")

        def forbidden_authority_consumer(**_kwargs: object) -> object:
            pytest.fail("DataTrust bridge absence reached an authority consumer")

        monkeypatch.setattr(service, "compile_and_run_recursive_generation_cycle", candidate_compiler)
        monkeypatch.setattr(service, "_admit_evaluation_safety_attempt", forbidden_eval_safety)
        monkeypatch.setattr(service, "resolve_generation_value_choices", forbidden_authority_consumer)
        monkeypatch.setattr(service, "_publish_generation_run", forbidden_authority_consumer)

        service._process_control_job(record)  # noqa: SLF001

        completed = service._control_store.get_job(launch.job_id)  # noqa: SLF001
        assert completed is not None
        assert completed.state == "completed"
        assert compiler_intents == ["candidate_only"]
        assert completed.progress["status"] == "not_established"
        assert completed.progress["execution_band"] == "candidate"
        assert completed.progress["execution_intent_band"] == "data_trust_required"
        assert completed.progress["execution_intent_limitation_code"] == (
            "data_trust_owner_not_established"
        )
        assert completed.progress["n4_status"] == "generation_unavailable"
        assert completed.progress["n5_status"] == "not_run"
        assert completed.progress["n8_status"] == "not_run"
        assert completed.progress["n9_status"] == "not_run"
        assert completed.progress["s8_status"] == "not_run"
    finally:
        service.close()


@pytest.mark.asyncio
async def test_simulate_only_served_worker_persists_computation_without_s8_or_publication(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Persist real N4 output with an unavailable simulation, not a fake run."""
    import polisyos.runtime.http.services.control.generation_cycle as generation_cycle_service
    from polisyos.runtime.http.services.control import nl_pipeline
    from polisyos.runtime.quality.generation_source import (
        GenerationSourceRepository,
        N4CandidateProposalSimulationRecord,
    )
    from tests.unit.runtime.http.test_nl_pipeline_materialization import (
        _design_problem_tool_args,
        _DeterministicSpanSupportClient,
        _FakeDesignProblemGateway,
        _intent_context,
    )
    from tests.unit.runtime.quality.test_design_generation import (
        RecordedClientWithCatalog,
        _recording_with_successful_first_response,
    )

    recording = _recording_with_successful_first_response()
    model_id = str(recording["model_id"])
    compiler_gateway = _FakeDesignProblemGateway(
        models=[model_id],
        arguments=_design_problem_tool_args(),
    )
    generation_gateway = RecordedClientWithCatalog(recording, model_ids=[model_id])
    original_compiler = nl_pipeline.build_design_problem_from_nl_request

    async def run_real_compiler(**kwargs):
        kwargs["gateway_client"] = compiler_gateway
        kwargs["span_support_client"] = _DeterministicSpanSupportClient()
        return await original_compiler(**kwargs)

    monkeypatch.setattr(
        generation_cycle_service,
        "build_design_problem_from_nl_request",
        run_real_compiler,
    )
    monkeypatch.setattr(
        nl_pipeline,
        "build_design_problem_from_nl_request",
        run_real_compiler,
    )
    monkeypatch.setattr(
        __import__("polisyos.scientist.orchestration.llm.factory", fromlist=["factory"]),
        "create_traced_gateway_client",
        lambda **_kwargs: generation_gateway,
    )

    service = _build_control_service(tmp_path)
    context = _intent_context(as_of="2026-05-15")
    context["evaluation_safety_attempt"] = _valid_intake_for_mode(
        "simulate_only"
    ).model_dump(mode="json")
    request = NaturalLanguageRunRequest(
        request="Design a wartime MSME credit guarantee for Ukraine within the stated "
        "UAH 10b budget cap. Simulate this candidate while carrying unknown "
        "world scope.",
        llm_model=model_id,
        context=context,
    )
    try:
        launch = await service.launch_nl_run(
            request,
            principal=RuntimePrincipal.from_user_claims(_fixture_claims()),
            authorization_proof=bound_nl_authorization_proof(
                _fixture_claims(), request
            ),
        )
        job = service._control_store.get_job(launch.job_id)  # noqa: SLF001
        assert job is not None and job.run_id is not None

        compiler_calls: list[tuple[object, object, object]] = []
        original_compile = service.compile_and_run_recursive_generation_cycle

        async def record_compiler_route(**kwargs):
            compiler_calls.append(
                (
                    kwargs["execution_intent"],
                    kwargs["n4_proposal_only"],
                    kwargs["root_evaluation_context"],
                )
            )
            return await original_compile(**kwargs)

        monkeypatch.setattr(
            service,
            "compile_and_run_recursive_generation_cycle",
            record_compiler_route,
        )

        # Removal probe: removing the served selector leaves persisted markers
        # intact but sends simulate_only into generic N6, which this guard rejects.
        def forbidden_recursive_controller(**_kwargs: object) -> object:
            pytest.fail("no-context simulate_only entered N6 instead of stopping after N4")

        monkeypatch.setattr(
            generation_cycle_service,
            "build_default_recursive_generation_cycle_controller",
            forbidden_recursive_controller,
        )
        monkeypatch.setattr(
            service,
            "resolve_generation_value_choices",
            lambda **_kwargs: pytest.fail("simulate_only reached normative S8"),
        )
        monkeypatch.setattr(
            service,
            "_publish_generation_run",
            lambda **_kwargs: pytest.fail("simulate_only published a recursive run"),
        )

        service._process_control_job(job)  # noqa: SLF001

        completed = service._control_store.get_job(launch.job_id)  # noqa: SLF001
        assert completed is not None and completed.state == "completed"
        progress = completed.progress
        assert compiler_calls == [("simulate_only", True, None)]
        assert progress["execution_intent_band"] == "simulate_only_attempt"
        assert progress["candidate_computation_status"] == "completed"
        assert progress["simulation_status"] == "simulation_unavailable"
        assert progress["simulation_limitation_code"] == (
            "cycle_substrate_context_not_established"
        )
        assert {
            progress["n5_status"],
            progress["n8_status"],
            progress["n9_status"],
            progress["s8_status"],
        } == {"not_run"}
        assert "publication_status" not in progress
        assert "compiled_recursive_generation_cycle_ref" not in progress
        assert "normative_disposition_ref" not in progress
        assert "manifest_ref" not in progress
        assert progress["candidate_proposal_ref"]

        repository = GenerationSourceRepository(service._artifact_store)
        proposal = repository.load_candidate_proposal_for_served_job(
            progress["candidate_proposal_ref"],
            job_id=launch.job_id,
            run_id=str(job.run_id),
            tenant_id="tenant-fixture",
            cell_id="cell-fixture",
            raw_request=request.request,
        )
        assert isinstance(proposal, N4CandidateProposalSimulationRecord)
        assert proposal.proposal.trinity_bundle.policy_spec.interventions
        assert proposal.simulation_disposition.execution_intent_band == (
            "simulate_only_attempt"
        )
    finally:
        service.close()


@pytest.mark.asyncio
async def test_simulate_only_n4_selector_refuses_an_owner_bound_cycle_context(
    tmp_path,
) -> None:
    """An admitted cycle context cannot be silently reduced to an N4 proposal."""
    from polisyos.runtime.http.services.control.generation_cycle import (
        compile_and_run_recursive_generation_cycle,
    )
    from polisyos.runtime.quality.cycle_substrate import (
        revalidate_cycle_substrate_context,
    )
    from polisyos.runtime.quality.design_problem import DesignProblemAuthorityError
    from polisyos.runtime.quality.recursive_generation_cycle import RecursiveCycleBudget
    from tests.unit.runtime.quality.test_generation_cycle import (
        _budget,
        _cyc01_owner_bound_n5_case,
    )

    problem, substrate_context, _candidate = _cyc01_owner_bound_n5_case()
    revalidate_cycle_substrate_context(substrate_context)
    service = _build_control_service(tmp_path)
    try:
        with pytest.raises(DesignProblemAuthorityError) as exc_info:
            await compile_and_run_recursive_generation_cycle(
                raw_request=problem.nl_provenance.raw_request,
                context={},
                model_name="fixture-model",
                execution_intent="simulate_only",
                n4_proposal_only=True,
                compiler_gateway=object(),  # type: ignore[arg-type]
                budget_state=_budget(),
                recursive_budget=RecursiveCycleBudget(
                    max_depth=0,
                    max_nodes=1,
                    min_cycles_per_leaf=1,
                    max_cycles_per_leaf=1,
                ),
                root_evaluation_context=None,
                eval_safety_verifier=service._evaluation_safety_admission_verifier,  # noqa: SLF001
                cycle_substrate_context=substrate_context,
                promotion_runtime=service._promotion_runtime,  # noqa: SLF001
            )
        assert exc_info.value.code == "n4_proposal_only_context_conflict"
    finally:
        service.close()


@pytest.mark.asyncio
async def test_simulate_only_n4_terminal_failure_is_not_simulation_unavailable(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A terminal N4 failure stays distinct from a persisted proposal outcome."""
    from polisyos.runtime.http.services.control.generation_cycle import (
        N4CandidateProposalExecution,
    )
    from polisyos.runtime.quality import design_generation as n4
    from tests.unit.runtime.quality.test_design_generation import (
        _bundle,
        _test_design_problem,
    )

    service = _build_control_service(tmp_path)
    problem = _test_design_problem()
    result = n4.GenerationUnderAResult(
        status="generation_unavailable",
        design_problem_ref=n4.gy_content_hash(problem.model_dump(mode="json")),
        model_id="synthetic-c2",
        preflight=n4.ModelProfilePreflight(
            status="gateway_unavailable",
            model_id="synthetic-c2",
        ),
        diversity_report=n4.GenerationDiversityReport(
            min_required=1,
            candidate_count=0,
            unique_diversity_key_count=0,
        ),
    )
    terminal_n4 = result.as_organ_run(trinity_bundle=_bundle([]))
    compiled = N4CandidateProposalExecution(
        design_problem=problem,
        proposal=terminal_n4,
    )
    request = NaturalLanguageRunRequest(
        request="Simulate candidate options with unavailable N4 generation.",
        llm_model="simulated-qwen",
        context={
            "evaluation_safety_attempt": _valid_intake_for_mode(
                "simulate_only"
            ).model_dump(mode="json")
        },
    )
    try:
        launch = await service.launch_nl_run(
            request,
            principal=RuntimePrincipal.from_user_claims(_fixture_claims()),
            authorization_proof=bound_nl_authorization_proof(
                _fixture_claims(), request
            ),
        )
        job = service._control_store.get_job(launch.job_id)  # noqa: SLF001
        assert job is not None

        async def terminal_n4_compiler(**_kwargs: object) -> object:
            return compiled

        monkeypatch.setattr(
            service,
            "compile_and_run_recursive_generation_cycle",
            terminal_n4_compiler,
        )
        service._process_control_job(job)  # noqa: SLF001

        completed = service._control_store.get_job(launch.job_id)  # noqa: SLF001
        assert completed is not None and completed.state == "completed"
        assert completed.progress["n4_status"] == "generation_unavailable"
        assert completed.progress["simulation_status"] == "not_run"
        assert completed.progress["simulation_limitation_code"] == (
            "n4_generation_unavailable"
        )
        assert completed.progress["candidate_proposal_ref"] is None
        assert completed.progress["n5_status"] == completed.progress["s8_status"] == "not_run"
    finally:
        service.close()


@pytest.mark.asyncio
async def test_authenticated_launch_binds_all_five_intent_bands_and_actor_scope(tmp_path) -> None:
    service = _build_control_service(tmp_path)
    assert isinstance(service._control_store, GuardedDependencyProxy)  # noqa: SLF001
    cases = (
        ("candidate", {}, "candidate_only", "established", None),
        (
            "simulation",
            {"evaluation_safety_attempt": _valid_intake_for_mode("simulate_only").model_dump(mode="json")},
            "simulate_only_attempt",
            "established",
            "simulate_only",
        ),
        (
            "data_trust",
            {"evaluation_safety_attempt": _valid_intake_for_mode("retrospective").model_dump(mode="json")},
            "data_trust_required",
            "established",
            "retrospective",
        ),
        (
            "eval_safety",
            {"evaluation_safety_attempt": _valid_intake_for_mode("field_pilot").model_dump(mode="json")},
            "eval_safety_required",
            "established",
            "field_pilot",
        ),
        (
            "invalid_mode",
            {"evaluation_safety_attempt": {"requested_mode_token": "field_pilot "}},
            "not_established",
            "not_established",
            None,
        ),
        (
            "malformed_protected_attempt",
            {"evaluation_safety_attempt": {"requested_mode_token": "field_pilot"}},
            "eval_safety_required",
            "not_established",
            "field_pilot",
        ),
    )
    try:
        for name, context, expected_band, expected_status, expected_mode in cases:
            request = NaturalLanguageRunRequest(
                request=f"Run the {name} intent as a candidate or protected action.",
                llm_model="simulated-qwen",
                context=context,
            )
            launch = await service.launch_nl_run(
                request,
                principal=RuntimePrincipal.from_user_claims(_fixture_claims()),
                authorization_proof=bound_nl_authorization_proof(
                    _fixture_claims(), request
                ),
            )
            job = service._control_store.get_job(launch.job_id)  # noqa: SLF001
            assert job is not None
            assert job.submitted_by == "user-fixture"
            payload = service._load_payload_ref(str(job.payload_ref))  # noqa: SLF001
            binding = payload.get("execution_intent_binding")
            assert isinstance(binding, dict)
            assert binding.get("intent_band") == expected_band
            assert binding.get("admission_status") == expected_status
            assert binding.get("canonical_mode") == expected_mode
            assert binding.get("schema_version") == (
                "polisyos.runtime.control_execution_intent.v2"
            )
            assert binding.get("route_action") == "control.launch_nl_run"
            assert binding.get("actor_subject") == "user-fixture"
            assert binding.get("actor_authenticated") is True
            assert binding.get("tenant_id") == "tenant-fixture"
            assert binding.get("cell_id") == "cell-fixture"
            assert binding.get("job_id") == job.job_id
            assert binding.get("run_id") == job.run_id
            assert isinstance(binding.get("intent_digest"), str)

            _, created_event = _job_created_event(service, launch.job_id)
            outbox = _outbox_payload(service, launch.job_id)
            capability_manifest = service._load_payload_ref(  # noqa: SLF001
                str(job.capability_manifest_ref)
            )
            assert created_event.get("execution_intent_binding") == binding
            assert outbox.get("execution_intent_binding") == binding
            assert created_event.get("intent_digest") == binding.get("intent_digest")
            assert outbox.get("intent_digest") == binding.get("intent_digest")
            assert created_event.get("payload_ref") == job.payload_ref
            assert outbox.get("payload_ref") == job.payload_ref
            assert created_event.get("capability_manifest_ref") == job.capability_manifest_ref
            assert outbox.get("capability_manifest_ref") == job.capability_manifest_ref
            actor = capability_manifest.get("actor")
            assert isinstance(actor, dict)
            assert actor.get("subject") == binding.get("actor_subject")
            assert actor.get("authenticated") is binding.get("actor_authenticated")
            assert actor.get("tenant_id") == binding.get("tenant_id")
            assert actor.get("cell_id") == binding.get("cell_id")
    finally:
        service.close()


def test_control_job_creation_rolls_back_and_replays_through_guarded_store(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = _build_control_service(tmp_path)
    store = service._control_store  # noqa: SLF001
    assert isinstance(store, GuardedDependencyProxy)
    raw_store = store._target  # noqa: SLF001
    job_id = "job-r5-transaction-replay"
    event_payload = {
        "job_id": job_id,
        "run_id": "run-r5-transaction-replay",
        "job_kind": "natural_language_run",
        "payload_ref": "sha256:" + "a" * 64,
        "execution_intent_binding": {"intent_band": "candidate_only"},
        "intent_digest": "sha256:" + "b" * 64,
        "capability_manifest_ref": "sha256:" + "c" * 64,
    }
    create_args = {
        "job_id": job_id,
        "kind": "natural_language_run",
        "run_id": "run-r5-transaction-replay",
        "pipeline_id": None,
        "requested_execution_profile": None,
        "effective_execution_profile": "dev",
        "policy_flags": {},
        "capability_manifest_ref": "sha256:" + "c" * 64,
        "payload_ref": "sha256:" + "a" * 64,
        "submitted_by": "user-fixture",
        "creation_event_payload": event_payload,
    }
    original_emit = raw_store._emit_job_outbox_event  # noqa: SLF001

    def append_then_interrupt(**kwargs: object) -> None:
        original_emit(**kwargs)
        raise RuntimeError("injected_after_outbox_insert")

    service_closed = False
    try:
        with monkeypatch.context() as patcher:
            patcher.setattr(raw_store, "_emit_job_outbox_event", append_then_interrupt)
            with pytest.raises(RuntimeError, match="injected_after_outbox_insert"):
                store.create_job(**create_args)

        assert store.get_job(job_id) is None
        with raw_store._sqlite_connection() as connection:  # noqa: SLF001
            assert connection.execute(
                "SELECT count(*) FROM control_job_progress WHERE job_id = ?", (job_id,)
            ).fetchone()[0] == 0
            assert connection.execute(
                "SELECT count(*) FROM control_job_events WHERE job_id = ?", (job_id,)
            ).fetchone()[0] == 0
            assert connection.execute(
                "SELECT count(*) FROM control_outbox_events WHERE job_id = ?", (job_id,)
            ).fetchone()[0] == 0

        store.create_job(**create_args)
        service.close()
        service_closed = True
        reopened = _build_control_service(tmp_path)
        try:
            record = reopened._control_store.get_job(job_id)  # noqa: SLF001
            assert record is not None
            _, event = _job_created_event(reopened, job_id)
            outbox = _outbox_payload(reopened, job_id)
            assert outbox == event | {
                "effective_execution_profile": "dev",
                "pipeline_id": None,
            }
            assert event["execution_intent_binding"] == event_payload["execution_intent_binding"]
            assert outbox["intent_digest"] == event_payload["intent_digest"]
        finally:
            reopened.close()
    finally:
        if not service_closed:
            service.close()
