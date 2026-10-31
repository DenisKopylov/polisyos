"""Controlled provider inputs traverse the real N4 owners, validation and HTTP."""

from __future__ import annotations

import asyncio
import copy
import gzip
import hashlib
import json
from pathlib import Path

import pytest

from polisyos.pdc import gy_content_hash
from polisyos.runtime.quality._n4_usage_capture import capture_call_usage
from polisyos.runtime.quality.design_generation import (
    N4CandidateScenarioProposalRun,
    generate_design_candidate_scenario_proposal_under_a,
)
from polisyos.scientist.orchestration.llm.gateway_client import GatewayLLMClient
from tests._helpers.acquisition_chain import (
    SERVED_WDI_FISCAL_REQUEST,
    controlled_served_wdi_generation_recording,
    controlled_served_wdi_problem,
    load_served_wdi_generation_recording,
    synthetic_served_wdi_provider_profile,
)
from tests._helpers.controlled_candidate_profile import (
    ControlledCandidateGateway,
    SyntheticCandidateProviderProfile,
    _current_compiler_problem,
)


def _inputs(tmp_path):
    recording = load_served_wdi_generation_recording()
    problem = controlled_served_wdi_problem(
        _current_compiler_problem(recording), raw_request=SERVED_WDI_FISCAL_REQUEST
    )
    profile = synthetic_served_wdi_provider_profile(
        recording, problem=problem, evidence_root=tmp_path / "exchanges"
    )
    return recording, problem, profile


async def _run(gateway, problem, model):
    client = GatewayLLMClient(base_url=gateway.base_url, api_key="", model=model, max_retries=0)
    try:
        return await generate_design_candidate_scenario_proposal_under_a(
            problem,
            model_id=model,
            llm_client=client,
            repo_root=Path(__file__).resolve().parents[4],
        )
    finally:
        await client.aclose()


def test_explicit_profile_uses_real_n4_call_owners_and_preserves_deciding_exchange_bytes(tmp_path):
    recording, problem, profile = _inputs(tmp_path)
    original = copy.deepcopy(recording)
    with ControlledCandidateGateway() as gateway:
        gateway.set_fixture(recording, problem=problem, provider_profile=profile)
        gateway.admit_compiled_problem(problem)
        with capture_call_usage() as captured:
            result = asyncio.run(_run(gateway, problem, profile.model_id))
    assert isinstance(result, N4CandidateScenarioProposalRun)
    proposal = result.proposal
    assert {"draft", "formalizer", "critic"} <= {call.role_hint for call in proposal.llm_calls}
    assert all(call.status == "success" for call in proposal.llm_calls)
    assert len(captured.evidence) == len(proposal.llm_calls)
    assert all(row.observation.provider_usage_status == "known" for row in captured.evidence)
    assert proposal.formalizer_path == "model_generated"
    assert recording == original
    receipts = sorted(profile.evidence_root.glob("*/receipt.json"))
    assert len(receipts) == len(proposal.llm_calls)
    for path in receipts:
        receipt = json.loads(path.read_text())
        request = gzip.decompress(path.with_name("request.json.gz").read_bytes())
        response = gzip.decompress(path.with_name("response.json.gz").read_bytes())
        assert hashlib.sha256(request).hexdigest() == receipt["request_bytes_sha256"]
        assert hashlib.sha256(response).hexdigest() == receipt["serialized_response_bytes_sha256"]
        assert receipt["producer_context"]["subject_ref"] == gy_content_hash(
            problem.model_dump(mode="json")
        )
        assert (
            receipt["profile"]["cost_scope"]
            == "current_configured_model_estimate_not_historical_billing"
        )


def test_same_stage_marker_with_wrong_semantic_body_cannot_become_formalizer_provenance(tmp_path):
    recording, problem, profile = _inputs(tmp_path)
    critic = json.loads(dict(profile.response_rows)["critic"])
    rows = []
    for stage, encoded in profile.response_rows:
        if stage == "formalizer":
            row = json.loads(encoded)
            row["raw_response"] = critic["raw_response"]
            row["raw_response_hash"] = gy_content_hash(row["raw_response"])
            encoded = json.dumps(row, sort_keys=True, separators=(",", ":"))
        rows.append((stage, encoded))
    wrong = SyntheticCandidateProviderProfile(
        model_id=profile.model_id,
        profile_selection_ref=profile.profile_selection_ref,
        source_recording_id=profile.source_recording_id,
        source_recording_content_hash=profile.source_recording_content_hash,
        controlled_recording_content_hash=profile.controlled_recording_content_hash,
        response_rows=tuple(rows),
        evidence_root=tmp_path / "wrong-exchanges",
    )
    with ControlledCandidateGateway() as gateway:
        gateway.set_fixture(recording, problem=problem, provider_profile=wrong)
        gateway.admit_compiled_problem(problem)
        result = asyncio.run(_run(gateway, problem, profile.model_id))
    assert not isinstance(result, N4CandidateScenarioProposalRun)


def test_default_capture_keeps_original_errors_and_overlay_is_identity_stable(tmp_path):
    recording, problem, profile = _inputs(tmp_path)
    original_bytes = json.dumps(recording, sort_keys=True).encode()
    controlled = controlled_served_wdi_generation_recording(
        recording, outcome_variable=problem.outcome_of_interest.target_variable
    )
    assert json.dumps(recording, sort_keys=True).encode() == original_bytes
    original_errors = [row for row in recording["responses"] if row.get("status") == "error"]
    assert original_errors
    assert [
        row for row in controlled["responses"] if row.get("status") == "error"
    ] == original_errors
    assert (
        profile.descriptor()["source_recording_content_hash"] == recording["recording_content_hash"]
    )
    assert {stage for stage, _row in profile.response_rows} == {
        "draft",
        "drafter_multipass",
        "drafter_consolidation",
        "formalizer",
        "critic",
    }


def test_profile_rejects_genuinely_sealed_unknown_stage_before_exchange_persistence(tmp_path):
    from types import SimpleNamespace

    from polisyos.common._producer_request import (
        _binding_scope,
        _call_context,
        _ProducerBinding,
        _request_args,
    )

    _recording, problem, profile = _inputs(tmp_path)
    subject = gy_content_hash(problem.model_dump(mode="json"))
    holder = SimpleNamespace(
        _producer_request_binding=_ProducerBinding(subject, profile.model_id, "scientist.n4")
    )
    gateway = GatewayLLMClient(base_url="http://127.0.0.1:1/v1", api_key="", model=profile.model_id)

    def payload(stage):
        values = _request_args(holder, stage=stage, user="complete fixture protocol probe")
        context = _call_context(values, holder._producer_request_binding)
        with _binding_scope(holder._producer_request_binding, context, values):
            return gateway.completion_request_payload(**values)

    positive = payload("draft")
    completion = profile.completion(
        positive, raw_request=json.dumps(positive).encode(), compiled_problem_ref=subject
    )
    assert completion["choices"][0]["message"]["content"]
    before = {
        str(path.relative_to(profile.evidence_root)): path.read_bytes()
        for path in profile.evidence_root.rglob("*")
        if path.is_file()
    }
    wrong = payload("unsupported_stage")
    with pytest.raises(ValueError, match="n4_producer_context_incompatible"):
        profile.completion(
            wrong, raw_request=json.dumps(wrong).encode(), compiled_problem_ref=subject
        )
    after = {
        str(path.relative_to(profile.evidence_root)): path.read_bytes()
        for path in profile.evidence_root.rglob("*")
        if path.is_file()
    }
    assert after == before


def test_missing_profile_context_is_a_separate_refusal(tmp_path):
    _recording, _problem, profile = _inputs(tmp_path)
    with pytest.raises(ValueError, match="producer_request_context_fields_invalid"):
        profile.completion(
            {"model": profile.model_id}, raw_request=b"{}", compiled_problem_ref=None
        )


@pytest.mark.parametrize("owner_name", ["drafter_clients", "formalizer", "critic"])
def test_actual_n4_owner_cannot_lose_context_while_retaining_its_prompt_markers(
    tmp_path, monkeypatch, owner_name
):
    import importlib

    owner = importlib.import_module("polisyos.scientist.agent." + owner_name)
    invoked = []

    def remove_owned_context(_client, *, stage, attempt=0, instance=None, **request):
        invoked.append((stage, attempt, instance))
        return request

    monkeypatch.setattr(owner, "_request_args", remove_owned_context)
    recording, problem, profile = _inputs(tmp_path)
    with ControlledCandidateGateway() as gateway:
        gateway.set_fixture(recording, problem=problem, provider_profile=profile)
        gateway.admit_compiled_problem(problem)
        try:
            result = asyncio.run(_run(gateway, problem, profile.model_id))
        except ValueError as error:
            if "producer_request_context_" not in str(error):
                raise
            result = None
    assert invoked, "selected real owner was not exercised"
    assert not isinstance(result, N4CandidateScenarioProposalRun)


@pytest.mark.parametrize("sanitizer_profile", ["default", "custom_digits"])
def test_actual_default_factory_sanitizer_and_settlement_survive_source_issuance(
    tmp_path, monkeypatch, sanitizer_profile
):
    from decimal import Decimal

    from polisyos.scientist.orchestration.engine.budget import BudgetLimit, BudgetState
    from polisyos.scientist.orchestration.engine.budget_ledger import FileBudgetLedger
    from polisyos.scientist.orchestration.engine.budget_middleware import BudgetMiddleware
    from polisyos.scientist.orchestration.llm.factory import (
        GatewayLLMConfig,
        create_traced_gateway_client,
    )

    monkeypatch.setenv("POLISYOS_LLM_SIMULATION_MODE", "0")
    if sanitizer_profile == "custom_digits":
        import re

        from polisyos.core.llm import PromptSanitizer, SanitizationRule
        from polisyos.scientist.orchestration.llm import factory

        actual_sanitizer = PromptSanitizer(
            rules=(SanitizationRule("digits", re.compile(r"([0-9]+)")),)
        )
        monkeypatch.setattr(factory, "PromptSanitizer", lambda: actual_sanitizer)
    recording, problem, profile = _inputs(tmp_path)
    ledger = FileBudgetLedger(tmp_path / "default-factory-ledger.json")
    middleware = BudgetMiddleware(
        BudgetState(limits={"run": BudgetLimit(key="run", max_usd=Decimal("10"))}), ledger=ledger
    )
    with ControlledCandidateGateway() as gateway:
        gateway.set_fixture(recording, problem=problem, provider_profile=profile)
        gateway.admit_compiled_problem(problem)

        async def run():
            client = create_traced_gateway_client(
                model_name=profile.model_id,
                config=GatewayLLMConfig(
                    base_url=gateway.base_url,
                    api_key="local-fixture-key",
                    timeout_s=10,
                    max_retries=0,
                ),
                producer_settlement_store=middleware,
            )
            assert client is not None
            try:
                with capture_call_usage() as capture:
                    result = await generate_design_candidate_scenario_proposal_under_a(
                        problem,
                        model_id=profile.model_id,
                        llm_client=client,
                        repo_root=Path(__file__).resolve().parents[4],
                        data_context={
                            "contact": "analyst@example.org",
                            "note": "password=fixturepassword123",
                            "custom_digits_probe": "123",
                        },
                    )
                return result, capture
            finally:
                await client.aclose()

        result, captured = asyncio.run(run())
    assert isinstance(result, N4CandidateScenarioProposalRun)
    assert any(
        row.producer_context["source_input_sha256"] != row.producer_context["prepared_input_sha256"]
        for row in captured.evidence
        if row.producer_context is not None
    )
    requests = [
        gzip.decompress(path.read_bytes())
        for path in profile.evidence_root.glob("*/request.json.gz")
    ]
    assert requests
    if sanitizer_profile == "default":
        assert all(b"analyst@example.org" not in raw for raw in requests)
        assert any(b"POLISYOS_SECRET_EMAIL" in raw for raw in requests)
        assert all(b"fixturepassword123" not in raw for raw in requests)
        assert any(b"POLISYOS_SECRET_PASSWORD_ASSIGNMENT" in raw for raw in requests)
    else:
        assert any(b"POLISYOS_SECRET_DIGITS" in raw for raw in requests)
        # The actual provider admitted every complete context despite digits in
        # schema, hashes and attempts: those owned bytes were never rescanned.
        assert all(
            json.loads(raw)["metadata"]["polisyos_producer_request"]["subject_ref"]
            == gy_content_hash(problem.model_dump(mode="json"))
            for raw in requests
        )
    snapshot = ledger.snapshot()
    source_events = [row.observation.settlement for row in captured.evidence]
    assert source_events and all(
        event is not None and event.ack_status == "committed" for event in source_events
    )
    assert all(
        event.event_id in snapshot.producer_settlements
        for event in source_events
        if event is not None
    )
    from polisyos.core.observability.pricing import estimate_llm_cost_usd

    assert any(
        record.cost_origin == "estimated" for record in snapshot.producer_settlements.values()
    )
    for row in captured.evidence:
        event = row.observation.settlement
        if event is not None and event.cost_origin == "estimated":
            usage = row.observation.provider_usage
            expected = Decimal(
                str(
                    estimate_llm_cost_usd(
                        model=event.model,
                        prompt_tokens=usage["prompt_tokens"],
                        completion_tokens=usage["completion_tokens"],
                    )
                )
            )
            assert Decimal(event.amount) == expected


def test_actual_factory_new_raw_issued_marker_keeps_normal_privacy_scan(tmp_path, monkeypatch):
    from polisyos.core.llm import PromptSanitizer, scan_secret_and_pii
    from polisyos.runtime.quality.design_generation import RecordingLLMClient
    from polisyos.scientist.orchestration.llm import factory
    from polisyos.scientist.orchestration.llm._n4_request import _request_args

    sanitizer = PromptSanitizer()
    marker = sanitizer.sanitize_payload({"secret": "alpha"})["secret"]
    scanned = scan_secret_and_pii(
        {"secret": marker},
        scope="connector request/response payloads",
        artifact_ref_or_route="fixture://new-raw-issued-marker",
        sanitizer=sanitizer,
        redact=True,
    )
    assert scanned.has_findings and scanned.redacted_payload["secret"] != marker
    assert any(report.redaction_applied for report in scanned.reports)
    monkeypatch.setattr(factory, "PromptSanitizer", lambda: sanitizer)
    monkeypatch.setenv("POLISYOS_LLM_SIMULATION_MODE", "0")
    recording, problem, profile = _inputs(tmp_path)
    with ControlledCandidateGateway() as gateway:
        gateway.set_fixture(recording, problem=problem, provider_profile=profile)
        gateway.admit_compiled_problem(problem)

        async def run():
            client = factory.create_traced_gateway_client(
                model_name=profile.model_id,
                config=factory.GatewayLLMConfig(
                    base_url=gateway.base_url,
                    api_key="local-fixture-key",
                    timeout_s=10,
                    max_retries=0,
                ),
            )
            assert client is not None
            recorder = RecordingLLMClient(
                client,
                model_id=profile.model_id,
                producer_problem_ref=gy_content_hash(problem.model_dump(mode="json")),
            )
            request = _request_args(
                recorder,
                stage="draft",
                user="new sensitive raw literal",
                metadata={"secret": marker},
            )
            try:
                await recorder.generate(**request)
                return request
            finally:
                await client.aclose()

        request = asyncio.run(run())
    assert request["metadata"]["secret"] != marker
    requests = [
        json.loads(gzip.decompress(path.read_bytes()))
        for path in profile.evidence_root.glob("*/request.json.gz")
    ]
    assert len(requests) == 1
    assert requests[0]["metadata"]["secret"] == request["metadata"]["secret"]


@pytest.mark.parametrize("provider_mode", ["synthetic", "legacy_unknown"])
def test_controlled_candidate_factory_settles_only_declared_new_provider_quantities(
    tmp_path, monkeypatch, provider_mode
):
    """Exercise the exact HTTP/factory/ledger seam before numerical Runtime work."""
    from decimal import Decimal

    from polisyos.core.observability.pricing import estimate_llm_cost_usd
    from polisyos.runtime.quality.design_generation import RecordingLLMClient
    from polisyos.scientist.orchestration.engine.budget import BudgetLimit, BudgetState
    from polisyos.scientist.orchestration.engine.budget_ledger import (
        BudgetLedgerProducerRunBinding,
        FileBudgetLedger,
    )
    from polisyos.scientist.orchestration.engine.budget_middleware import BudgetMiddleware
    from polisyos.scientist.orchestration.engine.producer_budget import (
        ProducerBudgetObserver,
        ProducerBudgetSourceError,
    )
    from polisyos.scientist.orchestration.llm._n4_request import _request_args
    from polisyos.scientist.orchestration.llm.factory import (
        GatewayLLMConfig,
        create_traced_gateway_client,
    )
    from tests._helpers.controlled_candidate_profile import (
        _controlled_registered_tax_recording,
        synthetic_controlled_candidate_provider_profile,
    )

    recording = load_served_wdi_generation_recording()
    problem = _current_compiler_problem(recording)
    controlled = _controlled_registered_tax_recording(
        recording, outcome_variable=problem.outcome_of_interest.target_variable
    )
    profile = synthetic_controlled_candidate_provider_profile(
        recording, controlled, problem=problem, evidence_root=tmp_path / "exchanges"
    )
    binding = BudgetLedgerProducerRunBinding(
        run_id="controlled-candidate-preflight",
        tenant_id="candidate-test-tenant",
        cell_id="candidate-test-cell",
        profile_id="candidate-test-profile",
        control_job_id="candidate-test-job",
    )
    ledger_path = tmp_path / "producer-ledger.json"
    middleware = BudgetMiddleware(BudgetState(), ledger=FileBudgetLedger(ledger_path))
    state = BudgetState(limits={"run": BudgetLimit(key="run", max_usd=Decimal("10"))})
    monkeypatch.setenv("POLISYOS_LLM_SIMULATION_MODE", "0")
    with ControlledCandidateGateway() as gateway:
        gateway.set_fixture(
            controlled,
            problem=problem,
            provider_profile=profile if provider_mode == "synthetic" else None,
        )
        gateway.admit_compiled_problem(problem)

        async def run():
            client = create_traced_gateway_client(
                model_name=profile.model_id,
                run_id=binding.run_id,
                config=GatewayLLMConfig(
                    base_url=gateway.base_url,
                    api_key="synthetic-local-key",
                    timeout_s=10,
                    max_retries=0,
                    cache_ttl_s=0,
                    cache_maxsize=0,
                ),
                producer_settlement_store=middleware,
                producer_budget_key=f"nl-run:{binding.run_id}",
            )
            assert client is not None
            recorder = RecordingLLMClient(
                client,
                model_id=profile.model_id,
                producer_problem_ref=gy_content_hash(problem.model_dump(mode="json")),
            )
            try:
                request = _request_args(
                    recorder, stage="draft", user="Controlled candidate transport preflight"
                )
                with middleware.producer_run_binding_scope(binding, control_job_attempt=1):
                    return await recorder.generate(**request)
            finally:
                await client.aclose()

        response = asyncio.run(run())
    snapshot = FileBudgetLedger(ledger_path).snapshot()
    assert len(snapshot.producer_settlements) == 1
    record = next(iter(snapshot.producer_settlements.values()))
    assert record.run_binding == binding
    assert record.key == f"nl-run:{binding.run_id}"
    assert record.control_job_attempt == 1
    assert record.payload_digest is not None
    observer = ProducerBudgetObserver(
        settlement_store=middleware, producer_run_binding=binding, budget_state=state
    )
    if provider_mode == "legacy_unknown":
        assert (
            record.status == "unknown" and record.amount is None and record.cost_origin == "unknown"
        )
        with pytest.raises(ProducerBudgetSourceError, match="producer_event_not_settled"):
            observer.observe()
        return
    assert record.status == "committed" and record.cost_origin == "estimated"
    usage = json.loads(dict(profile.response_rows)["draft"])["usage"]
    expected = Decimal(
        str(
            estimate_llm_cost_usd(
                model=profile.model_id,
                prompt_tokens=usage["prompt_tokens"],
                completion_tokens=usage["completion_tokens"],
            )
        )
    )
    assert record.amount == expected
    observed = observer.observe()
    assert observed.producer_spent_usd == expected
    assert observed.producer_events[0][0] == record.event_id
    assert observed.run_binding == binding
    assert response.content == json.loads(dict(profile.response_rows)["draft"])["raw_response"]
    assert "n5_usd_price_not_established" in observed.limitations


def test_controlled_candidate_provider_rejects_another_overlay_parent(tmp_path):
    from tests._helpers.controlled_candidate_profile import (
        _controlled_registered_tax_recording,
        synthetic_controlled_candidate_provider_profile,
    )

    recording = load_served_wdi_generation_recording()
    problem = _current_compiler_problem(recording)
    controlled = _controlled_registered_tax_recording(
        recording, outcome_variable=problem.outcome_of_interest.target_variable
    )
    controlled["derived_from_content_hash"] = "sha256:" + "0" * 64
    controlled["recording_content_hash"] = gy_content_hash(
        {key: value for key, value in controlled.items() if key != "recording_content_hash"}
    )
    with pytest.raises(ValueError, match="synthetic_provider_controlled_parent_mismatch"):
        synthetic_controlled_candidate_provider_profile(
            recording, controlled, problem=problem, evidence_root=tmp_path / "exchanges"
        )
    assert not (tmp_path / "exchanges").exists()
