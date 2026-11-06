"""Ordinary NL ingress can feed persisted candidates to the N7 basis consumer."""

from __future__ import annotations

import copy
import json
import uuid
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

from tests._helpers.control_worker import dispatch_one_control_job, stop_embedded_control_worker
from tests._helpers.controlled_candidate_profile import (
    ControlledCandidateGateway,
    _controlled_procurement_recording,
    _current_compiler_problem,
    synthetic_controlled_candidate_provider_profile,
)
from tests._helpers.generic_n4_served_replay import _RECORDING_ID, REPO_ROOT
from tests._helpers.runtime_http import build_runtime_api_env, close_runtime_api_env
from tools.quality.validation import check_layer3_gy_design_generation_contract as n4_contract


def _compiler_raw_request(request_body: Mapping[str, object]) -> str:
    messages = request_body.get("messages")
    assert isinstance(messages, list)
    user_messages = [
        row.get("content")
        for row in messages
        if isinstance(row, Mapping) and row.get("role") == "user"
    ]
    assert len(user_messages) == 1 and isinstance(user_messages[0], str)
    payload = json.loads(user_messages[0])
    assert isinstance(payload, dict)
    raw_request = payload.get("raw_request")
    assert isinstance(raw_request, str)
    return raw_request


def test_persisted_ordinary_nl_candidate_compiles_to_n7_basis_and_report_readback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Prove the component-level N7 basis/report chain after ordinary NL candidate persistence.

    This ends at the canonical basis and report-reader boundary. It does not claim that
    the served job invokes N7 terminal/planner orchestration or performs acquisition.
    """
    monkeypatch.setenv("POLISYOS_EXECUTION_PROFILE", "dev")
    monkeypatch.setenv("POLISYOS_CONTROL_WORKER_BACKEND", "external")
    monkeypatch.setenv("POLISYOS_CONTROL_STATE_STORE_BACKEND", "sqlite")
    monkeypatch.setenv("POLISYOS_CONTROL_SQLITE_PATH", (tmp_path / "control.sqlite3").as_posix())
    monkeypatch.setenv("POLISYOS_CACHE_HOME", (tmp_path / "runtime-cache").as_posix())
    monkeypatch.setenv("POLISYOS_LLM_GATEWAY_MAX_RETRIES", "0")
    monkeypatch.setenv("POLISYOS_LLM_CACHE_TTL_S", "0")
    monkeypatch.setenv("POLISYOS_LLM_CACHE_MAXSIZE", "0")
    monkeypatch.setenv("POLISYOS_LLM_PROMPT_SANITIZER", "false")

    recording = next(
        row
        for row in n4_contract._load_recordings(REPO_ROOT)
        if row.get("design_problem_id") == _RECORDING_ID
    )
    base_problem = _current_compiler_problem(recording)
    target_variable = base_problem.outcome_of_interest.target_variable
    assert target_variable == "employment_retention"
    required_construct = "economic.gdp"
    scope_profile = {
        "profile_id": "scope:canada-2024:requirement-ingress-v1",
        "jurisdiction": "Canada",
        "population": "national_economy",
        "entity_scope": "country",
        "time_window": {"start": "2024-01-01", "end": "2024-12-31"},
        "time_role": "observation_time",
        "granularity": "annual",
        "required_constructs": [required_construct],
    }
    request_cases = (
        (
            "education_policy",
            "opaque_education_case_41",
            "Assess education policy effects on employment retention in Canada during 2024; "
            "all proposals remain candidate-only.",
            False,
        ),
        (
            "unmapped:regional-support-policy",
            "opaque_scenario_case_73",
            "Assess the regional support policy effect on employment retention in Canada "
            "during 2024; all proposals remain candidate-only.",
            True,
        ),
    )

    env: dict[str, object] | None = None
    compiled_problems: list[Any] = []
    captured_compiler_bodies: list[bytes] = []
    with ControlledCandidateGateway() as gateway:
        for key, value in gateway.environment().items():
            monkeypatch.setenv(key, value)
        monkeypatch.setenv("POLISYOS_LLM_GATEWAY_API_KEY", "sk-synthetic-local-gateway-key")
        env = build_runtime_api_env(tmp_path, include_test_client=True)
        try:
            client = env["client"]
            app = env["app"]
            assert client is not None and app is not None
            service = app.state._control_service
            stop_embedded_control_worker(service)
            tenant_id = str(env["tenant_a"])
            cell_id = str(env["cell_a"])
            cas_root = Path(env["cas_root"])

            from polisyos.core.artifacts import FileSystemCAS
            from polisyos.runtime.http.services.control import generation_cycle
            from polisyos.runtime.quality.generation_cycle import GenerationCycleController
            from polisyos.runtime.quality.generation_source import (
                GenerationSourceRepository,
                N4CandidateProposalLocator,
                N4CandidateProposalRecordV3,
            )
            from tests._helpers.runtime_http import _DeterministicSpanSupportClient

            build_design_problem = generation_cycle.build_design_problem_from_nl_request

            async def compile_with_controlled_span_support(**kwargs: Any) -> Any:
                kwargs["span_support_client"] = _DeterministicSpanSupportClient()
                problem = await build_design_problem(**kwargs)
                gateway.admit_compiled_problem(problem)
                return problem

            monkeypatch.setattr(
                generation_cycle,
                "build_design_problem_from_nl_request",
                compile_with_controlled_span_support,
            )

            for index, (domain, scenario_id, raw_request, poison_specs) in enumerate(request_cases):
                payload = base_problem.model_dump(mode="json")
                payload["design_problem_id"] = scenario_id
                payload["domain"] = domain
                provenance = payload["nl_provenance"]
                assert isinstance(provenance, dict)
                provenance["raw_request"] = raw_request
                payload["problem_statement"] = raw_request
                runtime_hints: dict[str, object] = {"n7_scope_profile": scope_profile}
                if poison_specs:
                    # Caller/compiler-carried specs are an unbound hint. N7 must keep
                    # the compiler denominator derived from the typed scenario.
                    runtime_hints["n7_data_requirement_specs"] = [
                        {"construct": "forged.unbound.denominator", "authority": "source"}
                    ]
                payload["runtime_hints"] = runtime_hints
                expected_problem = type(base_problem).model_validate(payload)
                controlled_recording = _controlled_procurement_recording(
                    recording,
                    outcome_variable=target_variable,
                )
                provider_profile = synthetic_controlled_candidate_provider_profile(
                    recording,
                    controlled_recording,
                    problem=expected_problem,
                    evidence_root=tmp_path / f"synthetic-provider-{index}",
                )
                expected_reply = expected_problem.model_dump(mode="json")

                def controlled_compiler_reply(
                    request_body: Mapping[str, object],
                    *,
                    expected_raw_request: str = raw_request,
                    reply: dict[str, object] = expected_reply,
                ) -> Mapping[str, object]:
                    # The controlled local gateway is the external structured-reply
                    # boundary. This proves transport, product parsing, and persistence,
                    # not that a model inferred these fields correctly from the text.
                    assert _compiler_raw_request(request_body) == expected_raw_request
                    return copy.deepcopy(reply)

                gateway.set_fixture(
                    controlled_recording,
                    problem=expected_problem,
                    provider_profile=provider_profile,
                    compiler_reply_factory=controlled_compiler_reply,
                )
                accepted = client.post(
                    "/api/v1/control/runs/nl",
                    headers={"Idempotency-Key": uuid.uuid4().hex},
                    json={
                        "request": raw_request,
                        "llm_model": str(recording["model_id"]),
                        "max_iterations": 1,
                    },
                )
                assert accepted.status_code == 200, accepted.text
                job_id = str(accepted.json()["job_id"])
                assert (
                    dispatch_one_control_job(
                        store=service._control_store,
                        handler=service._process_control_job,
                        expected_job_id=job_id,
                    )
                    == job_id
                )
                job = service._control_store.get_job(job_id)
                assert job is not None and job.state == "completed", getattr(
                    job, "error_message", None
                )
                progress = dict(job.progress)
                assert progress["execution_intent_band"] == "candidate_only"
                assert progress["execution_band"] == "candidate"
                assert progress["n5_status"] == "not_run"
                assert progress["n8_status"] == "not_run"
                assert progress["n9_status"] == "not_run"
                locator_payload = progress.get("candidate_proposal_ref")
                assert isinstance(locator_payload, dict), {
                    key: progress.get(key)
                    for key in ("n4_status", "limitation_code", "proposal_persistence_status")
                }
                served = client.get(f"/api/v1/control/jobs/{job_id}")
                assert served.status_code == 200, served.text
                assert served.json()["progress"]["candidate_proposal_ref"] == locator_payload
                locator = N4CandidateProposalLocator.model_validate(locator_payload)
                proposal = GenerationSourceRepository(
                    FileSystemCAS(cas_root)
                ).load_candidate_proposal_for_served_job(
                    locator,
                    job_id=job_id,
                    run_id=str(job.run_id),
                    tenant_id=tenant_id,
                    cell_id=cell_id,
                    raw_request=raw_request,
                )
                assert isinstance(proposal, N4CandidateProposalRecordV3)
                assert proposal.problem.nl_provenance.raw_request == raw_request
                assert proposal.problem.design_problem_id == scenario_id
                assert proposal.problem.domain == domain
                assert proposal.problem.runtime_hints["n7_scope_profile"] == scope_profile
                compiled_problems.append(proposal.problem)
                captured_compiler_bodies.extend(gateway.compiler_request_bodies())

            # Ordinary Runtime composition passes no resolver here. The controller's
            # governed-fixture fallback is the same fallback used by its N7 owner.
            assert service._registry_providers.capability_resolver is None
            n7 = GenerationCycleController(
                repo_root=REPO_ROOT,
                capability_resolver=service._registry_providers.capability_resolver,
            )
            from polisyos.core.artifacts import load_core_json_artifact
            from polisyos.data_requirement import DataRequirementCompilationReport
            from polisyos.runtime.quality.acquisition_planner import (
                persist_and_verify_data_requirement_compilation_report,
                validate_persisted_data_requirement_compilation_report,
            )

            assert len(compiled_problems) == 2
            assert len(captured_compiler_bodies) == 2
            for problem, (domain, scenario_id, raw_request, poison_specs) in zip(
                compiled_problems, request_cases, strict=True
            ):
                assert (
                    _compiler_raw_request(json.loads(captured_compiler_bodies.pop(0)))
                    == raw_request
                )
                # Consume the fresh-CAS problem above through the canonical N7 basis
                # component. This does not assert the ordinary job's terminal N7 bridge.
                basis = n7._n7_data_requirement_basis_with_report(problem, acquisition_request={})
                resolution = basis.compilation_report.metadata["scenario_domain_resolution"]
                assert resolution["raw_inputs"] == {"domain": domain}
                assert resolution["rule_version_ref"] in basis.compilation_report.rule_version_refs
                if domain == "education_policy":
                    assert resolution["canonical_domain"] == "education"
                    assert resolution["status"] == "resolved"
                else:
                    assert resolution["canonical_domain"] == "custom"
                    assert resolution["status"] == "unresolved"
                assert basis.compilation_report.scenario_id == scenario_id
                assert "ua_2022" not in scenario_id
                selected = next(
                    row
                    for row in basis.capability_resolutions or ()
                    if row.query.construct == required_construct
                )
                assert selected.scope_profile_id == scope_profile["profile_id"]
                assert selected.query.construct == required_construct
                assert selected.query.geography == "Canada"
                assert selected.query.population_filter == {"type": "national_economy"}
                assert selected.query.entity_scope == "country"
                assert selected.query.time_window.start == "2024-01-01"
                assert selected.query.time_window.end == "2024-12-31"
                assert selected.candidate_discovery is not None
                assert selected.candidate_discovery.query == selected.query
                assert selected.candidate_discovery.satisfies_claim_evidence is False

                if poison_specs:
                    clean_problem = problem.model_copy(
                        update={
                            "runtime_hints": {
                                key: value
                                for key, value in problem.runtime_hints.items()
                                if key != "n7_data_requirement_specs"
                            }
                        }
                    )
                    clean = n7._n7_data_requirement_basis_with_report(
                        clean_problem,
                        acquisition_request={},
                    )
                    assert basis.unbound_input_fields == (
                        "runtime_hints.n7_data_requirement_specs",
                    )
                    assert tuple(row.model_dump(mode="json") for row in basis.specs) == tuple(
                        row.model_dump(mode="json") for row in clean.specs
                    )
                    assert tuple(row.query for row in basis.capability_resolutions or ()) == tuple(
                        row.query for row in clean.capability_resolutions or ()
                    )
                    assert required_construct in {
                        row.query.construct for row in basis.capability_resolutions or ()
                    }
                    assert "forged.unbound.denominator" not in {
                        row.query.construct for row in basis.capability_resolutions or ()
                    }

                report_store_root = tmp_path / f"n7-report-cas-{scenario_id}"
                writer = FileSystemCAS(report_store_root)
                binding = persist_and_verify_data_requirement_compilation_report(
                    writer,
                    basis.compilation_report,
                    expected_scenario_id=scenario_id,
                )
                fresh_reader = FileSystemCAS(report_store_root)
                raw_report = load_core_json_artifact(fresh_reader, binding.compiler_report_ref)
                reopened = DataRequirementCompilationReport.model_validate(raw_report)
                assert reopened.model_dump(mode="json") == basis.compilation_report.model_dump(
                    mode="json"
                )
                assert (
                    validate_persisted_data_requirement_compilation_report(
                        fresh_reader,
                        binding,
                        expected_report=basis.compilation_report,
                        require_selected_writer_profile=True,
                    )
                    == ()
                )
        finally:
            close_runtime_api_env(env)
