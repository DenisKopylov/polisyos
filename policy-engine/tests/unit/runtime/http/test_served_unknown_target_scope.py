from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from polisyos.core.contracts.control import NaturalLanguageRunRequest
from tests._helpers.control_worker import dispatch_one_control_job


def test_unknown_target_scope_selector_is_typed_input_not_authority() -> None:
    request = NaturalLanguageRunRequest(
        request="Draft candidate options for a policy question.",
        target_world_scope_profile_id="future-profile-v2",
    )
    assert request.target_world_scope_profile_id == "future-profile-v2"
    with pytest.raises(ValidationError):
        NaturalLanguageRunRequest(
            request="Draft candidate options for a policy question.",
            target_world_scope_profile_id="",
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("profile_id", "profile_status", "payload_schema_version", "simulate_only"),
    [
        pytest.param(
            "future-profile-v2",
            "profile_admission_missing",
            "1.1",
            False,
            id="unknown-profile",
        ),
        pytest.param(None, "profile_not_requested", "1.0", False, id="omitted-profile"),
        pytest.param(
            "future-profile-v2",
            "profile_admission_missing",
            "1.1",
            True,
            id="simulate-only-unknown-profile",
        ),
    ],
)
async def test_served_unknown_scope_job_keeps_candidate_n4_without_default_ua_world(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    profile_id: str | None,
    profile_status: str,
    payload_schema_version: str,
    simulate_only: bool,
) -> None:
    """The persisted selector must not fall through to the fixed UA WMR."""
    import polisyos.runtime.http.services.control.generation_cycle as generation_cycle_service
    import polisyos.runtime.quality.design_generation as design_generation
    import polisyos.runtime.quality.generation_source as generation_source
    import polisyos.runtime.quality.intervention_substrate as intervention_substrate
    from polisyos.runtime.http.execution_policy import RuntimePrincipal
    from polisyos.runtime.http.services.adapters.core_run import (
        load_completed_control_job_core_run_source,
    )
    from polisyos.runtime.http.services.control import nl_pipeline
    from polisyos.runtime.quality.generation_source import N4CandidateProposalLocator
    from polisyos.scientist.orchestration.engine.budget import BudgetState
    from polisyos.scientist.orchestration.engine.budget_ledger import (
        BudgetLedgerProducerRunBinding,
        FileBudgetLedger,
    )
    from polisyos.scientist.orchestration.engine.budget_middleware import BudgetMiddleware
    from tests.unit.runtime.http import test_control_service_di as fixtures
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
    raw_request = (
        "Design a wartime MSME credit guarantee for Ukraine within the stated UAH 10b budget cap."
    )
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
    llm_factory = __import__("polisyos.scientist.orchestration.llm.factory", fromlist=["factory"])
    from polisyos.scientist.orchestration.llm.factory import GatewayLLMConfig

    fixture_gateway_config = GatewayLLMConfig(
        base_url="https://controlled-gateway.invalid/v1",
        api_key="sk-controlled-fixture-key",
        default_provider="recorded_gateway_replay",
        enable_prompt_sanitizer=False,
    )
    monkeypatch.setenv("POLISYOS_LLM_SIMULATION_MODE", "0")
    monkeypatch.setattr(
        GatewayLLMConfig,
        "from_env",
        classmethod(lambda _cls: fixture_gateway_config),
    )
    monkeypatch.setattr(llm_factory, "GatewayLLMClient", lambda **_kwargs: generation_gateway)

    def forbidden_default_wmr(*_args, **_kwargs):
        pytest.fail("unknown selector consumed the implicit UA WMR")

    monkeypatch.setattr(
        intervention_substrate,
        "production_composed_world_model_record",
        forbidden_default_wmr,
    )
    monkeypatch.setattr(
        design_generation,
        "build_credal_reference",
        forbidden_default_wmr,
    )

    service = fixtures._build_control_service(tmp_path)
    settlement_store = BudgetMiddleware(
        BudgetState(),
        ledger=FileBudgetLedger(tmp_path / "producer-ledger.json"),
    )
    service.bind_llm_producer_settlement_store(settlement_store)
    try:
        intent_context = _intent_context(as_of="2026-05-12")
        if simulate_only:
            from tests.unit.runtime.http.test_control_job_execution_intent import (
                _valid_intake_for_mode,
            )

            intent_context["evaluation_safety_attempt"] = _valid_intake_for_mode(
                "simulate_only"
            ).model_dump(mode="json")
        request_fields: dict[str, object] = {
            "request": raw_request,
            "llm_model": model_id,
            "context": intent_context,
        }
        if profile_id is not None:
            request_fields["target_world_scope_profile_id"] = profile_id
        request = NaturalLanguageRunRequest.model_validate(request_fields)
        launch = await service.launch_nl_run(
            request,
            principal=RuntimePrincipal.from_user_claims(fixtures._fixture_claims()),
            authorization_proof=fixtures.bound_nl_authorization_proof(
                fixtures._fixture_claims(), request
            ),
        )
        job = service._control_store.get_job(launch.job_id)
        assert job is not None and job.payload_ref is not None
        payload = service._load_payload_ref(
            job.payload_ref, kind="runtime.control_job_payload.natural_language_run"
        )
        assert payload.get("target_world_scope_profile_id") == profile_id
        assert (
            service._artifact_store.get_manifest(job.payload_ref).artifact_schema.version
            == payload_schema_version
        )

        monkeypatch.setattr(
            service,
            "resolve_generation_value_choices",
            lambda **_kwargs: pytest.fail("candidate proposal reached S8"),
        )
        publication_calls: list[dict[str, object]] = []
        original_publish_generation_run = service._publish_generation_run  # noqa: SLF001

        def publish_candidate_core_output(**kwargs: object) -> object:
            assert kwargs.get("proposal_ref") is not None
            assert kwargs.get("compiled_run_ref") is None
            assert kwargs.get("normative_disposition_ref") is None
            publication_calls.append(dict(kwargs))
            return original_publish_generation_run(**kwargs)  # type: ignore[arg-type]

        monkeypatch.setattr(service, "_publish_generation_run", publish_candidate_core_output)
        monkeypatch.setattr(
            generation_cycle_service,
            "build_default_recursive_generation_cycle_controller",
            lambda **_kwargs: pytest.fail("candidate proposal entered N6"),
        )

        dispatch_one_control_job(
            store=service._control_store,  # noqa: SLF001
            handler=service._process_control_job,  # noqa: SLF001
            expected_job_id=launch.job_id,
        )

        completed = service._control_store.get_job(launch.job_id)
        assert completed is not None and completed.state == "completed"
        assert completed.progress["target_world_scope_status"] == "not_established"
        assert completed.progress["target_world_scope_profile_status"] == profile_status
        assert completed.progress["target_world_scope_profile_id"] == profile_id
        assert completed.progress["target_world_model_record_ref"] is None
        assert completed.progress["n5_status"] == "not_run"
        assert completed.progress["s8_status"] == "not_run"
        if simulate_only:
            assert completed.progress["execution_intent_band"] == "simulate_only_attempt"
            assert completed.progress["simulation_status"] == "simulation_unavailable"
            assert completed.progress["simulation_limitation_code"] == (
                "cycle_substrate_context_not_established"
            )
            assert "compiled_recursive_generation_cycle_ref" not in completed.progress
        else:
            assert completed.progress["execution_intent_band"] == "candidate_only"
            assert "simulation_status" not in completed.progress
        assert completed.progress["candidate_proposal_ref"]
        assert len(publication_calls) == 1
        proposal_locator = N4CandidateProposalLocator.model_validate(
            completed.progress["candidate_proposal_ref"]
        )
        proposal = generation_source.GenerationSourceRepository(
            service._artifact_store
        ).load_candidate_proposal_for_served_job(
            proposal_locator,
            job_id=launch.job_id,
            run_id=str(job.run_id),
            tenant_id="tenant-fixture",
            cell_id="cell-fixture",
            raw_request=raw_request,
        )
        assert proposal.problem.nl_provenance.raw_request == raw_request
        assert proposal.proposal.trinity_bundle.policy_spec.interventions
        assert proposal.proposal.limitation_code == "cycle_substrate_context_unavailable"
        terminal = load_completed_control_job_core_run_source(
            store=service._artifact_store,
            core_runs_root=service._core_runs_root,  # noqa: SLF001
            job=completed,
            expected_control_run_id=str(job.run_id),
            tenant_id="tenant-fixture",
            cell_id="cell-fixture",
        )
        assert terminal.manifest.outputs == [proposal_locator.artifact_ref]
        assert all(
            ref.kind
            not in {
                "runtime.compiled_recursive_generation_cycle",
                "runtime.normative_generation_composition",
                "runtime.n8_joint_simulation",
                "runtime.s8_normative_disposition",
            }
            for ref in terminal.manifest.outputs
        )
        binding = BudgetLedgerProducerRunBinding(
            run_id=str(job.run_id),
            tenant_id="tenant-fixture",
            cell_id="cell-fixture",
            profile_id=job.effective_execution_profile,
            control_job_id=job.job_id,
        )
        producer_records = settlement_store.list_producer_events_for_run_safe(binding)
        assert producer_records
        assert {event.event_id for event in proposal.producer_cost_events} == {
            record.event_id for record in producer_records
        }
        if simulate_only:
            assert proposal.schema_version.endswith(".v3")
            assert proposal.simulation_disposition.status == "simulation_unavailable"
            assert proposal.simulation_disposition.reason_code == (
                "cycle_substrate_context_not_established"
            )
        else:
            assert proposal.schema_version.endswith(".v3")
    finally:
        service.close()


def test_eval_safety_source_reader_accepts_v10_and_validated_v11_payloads(
    tmp_path: Path,
) -> None:
    """Selector-bearing payloads remain readable without restamping v1.0 jobs."""
    from tests.unit.runtime.http import test_control_service_di as fixtures

    service = fixtures._build_control_service(tmp_path)
    kind = "runtime.control_job_payload.natural_language_run"
    schema_name = "polisyos.runtime.ControlJobPayload"
    try:
        legacy_payload = {"run_id": "run-legacy", "request": "legacy request"}
        legacy_ref = service._persist_job_payload(
            job_kind="natural_language_run",
            payload=legacy_payload,
        )
        assert service._artifact_store.get_manifest(legacy_ref).artifact_schema.version == "1.0"

        selected_payload = {
            "run_id": "run-selected",
            "request": "selected request",
            "target_world_scope_profile_id": "future-profile-v2",
        }
        selected_ref = service._persist_job_payload(
            job_kind="natural_language_run",
            payload=selected_payload,
        )
        assert service._artifact_store.get_manifest(selected_ref).artifact_schema.version == "1.1"

        def read(ref: str) -> object:
            return service._evaluation_safety_persistence_service._read_promotion_source_json(
                ref,
                kind=kind,
                schema_name=schema_name,
                inputs_read=[],
                read_attempts=[],
            )

        assert read(legacy_ref) == legacy_payload
        assert read(selected_ref) == selected_payload

        malformed_payload = {
            "run_id": "run-malformed",
            "request": "malformed selector",
            "target_world_scope_profile_id": "Not a valid selector",
        }
        malformed_ref = service._persist_job_payload(
            job_kind="natural_language_run",
            payload=malformed_payload,
        )
        with pytest.raises(ValueError, match="promotion_source_artifact_binding_mismatch"):
            read(malformed_ref)

        downgraded_payload = {
            "run_id": "run-downgraded",
            "request": "selector under a legacy schema",
            "target_world_scope_profile_id": "future-profile-v2",
        }
        downgraded_ref = service._put_json_artifact(
            downgraded_payload,
            kind=kind,
            schema_name=schema_name,
            schema_version="1.0",
        )
        with pytest.raises(ValueError, match="promotion_source_artifact_binding_mismatch"):
            read(downgraded_ref)
    finally:
        service.close()


def test_eval_safety_source_reader_rejects_missing_artifact_schema_as_typed_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A missing CAS schema must produce the reader's typed binding refusal."""
    from tests.unit.runtime.http import test_control_service_di as fixtures

    service = fixtures._build_control_service(tmp_path)
    kind = "runtime.control_job_payload.natural_language_run"
    schema_name = "polisyos.runtime.ControlJobPayload"
    payload = {
        "run_id": "run-missing-schema",
        "request": "schema is required",
        "target_world_scope_profile_id": "unadmitted-profile-v1",
    }
    try:
        ref = service._persist_job_payload(job_kind="natural_language_run", payload=payload)
        reader = service._evaluation_safety_persistence_service
        store = reader._artifact_store
        assert (
            reader._read_promotion_source_json(
                ref,
                kind=kind,
                schema_name=schema_name,
                inputs_read=[],
                read_attempts=[],
            )
            == payload
        )
        original_manifest = store.get_manifest(ref)
        malformed_manifest = original_manifest.model_copy(update={"artifact_schema": None})

        class _MissingSchemaStore:
            def get_manifest(self, artifact_ref: object) -> object:
                from polisyos.core.artifacts import ArtifactID

                if isinstance(artifact_ref, ArtifactID) and str(artifact_ref) == ref:
                    return malformed_manifest
                return store.get_manifest(artifact_ref)

            def get_bytes(self, artifact_ref: str) -> bytes:
                return store.get_bytes(artifact_ref)

        monkeypatch.setattr(reader, "_artifact_store", _MissingSchemaStore())
        with pytest.raises(ValueError, match="promotion_source_artifact_binding_mismatch"):
            reader._read_promotion_source_json(
                ref,
                kind=kind,
                schema_name=schema_name,
                inputs_read=[],
                read_attempts=[],
            )
    finally:
        service.close()
