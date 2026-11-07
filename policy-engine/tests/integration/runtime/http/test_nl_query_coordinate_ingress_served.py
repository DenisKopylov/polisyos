"""Ordinary NL ingress preserves only the coordinates returned by its compiler."""

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


def _compiler_user_payload(request_body: Mapping[str, object]) -> dict[str, object]:
    messages = request_body.get("messages")
    assert isinstance(messages, list)
    user_contents = [
        message.get("content")
        for message in messages
        if isinstance(message, Mapping) and message.get("role") == "user"
    ]
    assert len(user_contents) == 1
    assert isinstance(user_contents[0], str)
    payload = json.loads(user_contents[0])
    assert isinstance(payload, dict)
    return payload


def _outcome_schema_properties(request_body: Mapping[str, object]) -> Mapping[str, object]:
    tools = request_body.get("tools")
    assert isinstance(tools, list) and len(tools) == 1
    tool = tools[0]
    assert isinstance(tool, Mapping)
    function = tool.get("function")
    assert isinstance(function, Mapping)
    parameters = function.get("parameters")
    assert isinstance(parameters, Mapping)
    properties = parameters.get("properties")
    assert isinstance(properties, Mapping)
    outcome = properties.get("outcome_of_interest")
    assert isinstance(outcome, Mapping)
    variants = outcome.get("anyOf", [outcome])
    assert isinstance(variants, list)
    for variant in variants:
        if not isinstance(variant, Mapping) or variant.get("type") != "object":
            continue
        nested_properties = variant.get("properties")
        if isinstance(nested_properties, Mapping):
            return nested_properties
    raise AssertionError("compiler_provider_outcome_schema_missing")


def test_ordinary_nl_ingress_persists_provider_returned_coordinate_variants(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Prove HTTP request, provider tool reply, real compiler, and proposal CAS binding."""
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
    base_request = base_problem.nl_provenance.raw_request
    target_variable = base_problem.outcome_of_interest.target_variable
    assert target_variable == "employment_retention"
    requests_and_coordinates = (
        (
            base_request
            + f" Estimate the ATE for {target_variable} in USD, conditioning on baseline_covariate.",
            ("baseline_covariate",),
            "usd",
        ),
        (
            base_request
            + f" Estimate the ATE for {target_variable} as a percentage, conditioning on "
            "baseline_firm_survival.",
            ("baseline_firm_survival",),
            "percent",
        ),
        (
            base_request
            + f" Estimate the ATE for {target_variable}; do not specify a unit or conditioning variable.",
            (),
            None,
        ),
    )
    raw_requests = tuple(row[0] for row in requests_and_coordinates)

    env: dict[str, object] | None = None
    with ControlledCandidateGateway() as gateway:
        for name, value in gateway.environment().items():
            monkeypatch.setenv(name, value)
        monkeypatch.setenv("POLISYOS_LLM_GATEWAY_API_KEY", "sk-synthetic-local-gateway-key")
        env = build_runtime_api_env(tmp_path, include_test_client=True)
        try:
            client = env["client"]
            app = env["app"]
            assert client is not None
            assert app is not None
            service = app.state._control_service
            stop_embedded_control_worker(service)
            tenant_id = str(env["tenant_a"])
            cell_id = str(env["cell_a"])
            cas_root = Path(env["cas_root"])
            from polisyos.core.artifacts import FileSystemCAS
            from polisyos.runtime.http.services.control import generation_cycle
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

            recovered: list[Any] = []
            compiler_request_bodies: list[bytes] = []
            for index, (raw_request, conditioning_variables, measurement_unit) in enumerate(
                requests_and_coordinates
            ):
                expected_payload = base_problem.model_dump(mode="json")
                provenance = expected_payload["nl_provenance"]
                assert isinstance(provenance, dict)
                provenance["raw_request"] = raw_request
                outcome = expected_payload["outcome_of_interest"]
                assert isinstance(outcome, dict)
                outcome["estimand"] = (
                    f"ATE of the requested candidate intervention on {target_variable}."
                )
                outcome.pop("conditioning_variables", None)
                outcome.pop("measurement_unit", None)
                outcome.pop("query_coordinate_status", None)
                if conditioning_variables:
                    outcome["conditioning_variables"] = list(conditioning_variables)
                if measurement_unit is not None:
                    outcome["measurement_unit"] = measurement_unit
                expected_problem = type(base_problem).model_validate(expected_payload)
                controlled_recording = _controlled_procurement_recording(
                    recording,
                    outcome_variable=expected_problem.outcome_of_interest.target_variable,
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
                    assert (
                        _compiler_user_payload(request_body).get("raw_request")
                        == expected_raw_request
                    )
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
                assert progress["s8_status"] == "not_run"
                assert progress.get("candidate_proposal_ref") is not None, {
                    key: progress.get(key)
                    for key in (
                        "n4_status",
                        "limitation_code",
                        "candidate_proposal_limitation_code",
                        "proposal_persistence_status",
                    )
                }

                served = client.get(f"/api/v1/control/jobs/{job_id}")
                assert served.status_code == 200, served.text
                assert (
                    served.json()["progress"]["candidate_proposal_ref"]
                    == progress["candidate_proposal_ref"]
                )
                locator = N4CandidateProposalLocator.model_validate(
                    progress["candidate_proposal_ref"]
                )
                # A new CAS adapter is the reader: it reopens owner-selected bytes, not
                # the worker's in-memory DesignProblem or proposal object.
                record_ref = GenerationSourceRepository(
                    FileSystemCAS(cas_root)
                ).load_candidate_proposal_for_served_job(
                    locator,
                    job_id=job_id,
                    run_id=str(job.run_id),
                    tenant_id=tenant_id,
                    cell_id=cell_id,
                    raw_request=raw_request,
                )
                assert isinstance(record_ref, N4CandidateProposalRecordV3)
                recovered.append(record_ref)
                compiler_request_bodies.extend(gateway.compiler_request_bodies())
        finally:
            close_runtime_api_env(env)

    assert len(compiler_request_bodies) == len(raw_requests)
    for body, raw_request in zip(compiler_request_bodies, raw_requests, strict=True):
        outbound = json.loads(body)
        assert isinstance(outbound, dict)
        provider_input = _compiler_user_payload(outbound)
        assert provider_input["raw_request"] == raw_request
        assert "conditioning_variables" in _outcome_schema_properties(outbound)
        assert "measurement_unit" in _outcome_schema_properties(outbound)

    first, changed, omitted = recovered
    first_outcome = first.problem.outcome_of_interest
    changed_outcome = changed.problem.outcome_of_interest
    omitted_outcome = omitted.problem.outcome_of_interest
    assert first.problem.nl_provenance.raw_request == raw_requests[0]
    assert first_outcome.estimand.startswith("ATE ")
    assert first_outcome.conditioning_variables == ("baseline_covariate",)
    assert first_outcome.measurement_unit == "usd"
    assert first_outcome.query_coordinate_status == "candidate_proposed_unverified"

    assert changed.problem.nl_provenance.raw_request == raw_requests[1]
    assert changed_outcome.conditioning_variables == ("baseline_firm_survival",)
    assert changed_outcome.measurement_unit == "percent"
    assert changed_outcome.query_coordinate_status == "candidate_proposed_unverified"
    assert changed.design_problem_ref != first.design_problem_ref
    assert changed.request_hash != first.request_hash

    assert omitted.problem.nl_provenance.raw_request == raw_requests[2]
    assert omitted_outcome.estimand.startswith("ATE ")
    assert omitted_outcome.conditioning_variables == ()
    assert omitted_outcome.measurement_unit is None
    assert omitted_outcome.query_coordinate_status is None
    assert omitted.design_problem_ref != first.design_problem_ref
    assert omitted.request_hash != first.request_hash

    for record in recovered:
        assert record.status == "candidate_limited"
        assert record.execution_band == "candidate"
        assert record.authority_purpose == "candidate_proposal"
        assert record.n5_status == record.n8_status == "not_run"
        assert record.n9_status == "not_run"
