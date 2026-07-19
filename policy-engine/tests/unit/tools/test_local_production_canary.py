from __future__ import annotations

import json
import os
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from polisyos.runtime.quality.assurance_case import build_policy_intent_envelope
from tools.ops_runners.runtime.local_production_canary import (
    DEFAULT_MODEL,
    _build_canary_request,
    _build_runtime_canary_app,
    _configure_local_runtime_env,
    _extract_provider_preflight,
    _has_required_materialization_refs,
    _is_terminal_job_state,
    _load_env_file,
    _load_local_run_evidence,
    _runtime_canary_bearer_token,
)
from tools.ops_runners.runtime.quality_scenarios import (
    DEFAULT_QUALITY_SCENARIO_ID,
    load_quality_scenario_contract,
)


def _runtime_canary_security(
    tmp_path: Path,
    request: pytest.FixtureRequest,
) -> tuple[Any, Any]:
    import jwt
    from cryptography.hazmat.primitives.asymmetric import rsa

    from polisyos.runtime.http.deployment_security import (
        DeploymentSecurityConfig,
        build_deployment_security,
    )
    from tests.unit.runtime.http.deployment_security_test_support import (
        LocalJWKSStub,
    )
    from tests.unit.runtime.http.test_runtime_deployment_security import (
        _config_mapping,
    )

    private_key = rsa.generate_private_key(public_exponent=65_537, key_size=2_048)
    jwks_server = LocalJWKSStub(private_key)
    jwks_uri = jwks_server.start()
    request.addfinalizer(jwks_server.close)
    raw = _config_mapping(tmp_path)
    identity_config = raw["identity_verifier"]
    assert isinstance(identity_config, dict)
    identity_config["jwks_uri"] = jwks_uri
    principals = raw["service_principals"]
    assert isinstance(principals, list)
    valid = principals[0]
    assert isinstance(valid, dict)
    principals.append(
        {
            **valid,
            "subject": "runtime-canary-over-granted",
            "permissions": ["runs.launch", "runs.view", "evidence.acquire"],
        }
    )
    runtime = build_deployment_security(DeploymentSecurityConfig.from_mapping(raw))

    def _token(subject: str) -> str:
        now = int(time.time())
        return jwt.encode(
            {
                "iss": "https://idp.example",
                "aud": "polisyos-runtime",
                "sub": subject,
                "tenant_id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
                "cell_id": "018f47a0-0000-7000-8000-000000000001",
                "realm_access": {"roles": ["polisyos_admin"]},
                "amr": ["pwd", "mfa"],
                "iat": now,
                "exp": now + 60,
                "jti": f"{subject}-{now}",
            },
            private_key,
            algorithm="RS256",
            headers={"kid": "identity-2026-07"},
        )

    return runtime, _token


def test_build_canary_request_is_real_one_model_production_data_lane(tmp_path: Path) -> None:
    production_data_root = tmp_path / "production_data"
    request = _build_canary_request(
        model=DEFAULT_MODEL,
        production_data_root=production_data_root,
        max_iterations=1,
        run_budget_usd=0.05,
    )

    assert request["execution_profile"] == "research"
    assert request["llm_models"] == [DEFAULT_MODEL]
    assert request["max_parallel_models"] == 1
    assert request["policy_flags"] == {"allow_mock_fallback": False}
    assert request["context"]["production_data_root"] == str(production_data_root)
    assert request["context"]["query_outcome"] == "msme_survival_rate"
    assert request["context"]["query_treatment"] == "wartime_credit_support"
    assert request["stop_criteria"]["require_data_snapshot_or_bindings"] is True


def test_build_canary_request_applies_quality_scenario_contract(tmp_path: Path) -> None:
    production_data_root = tmp_path / "production_data"
    scenario = load_quality_scenario_contract(DEFAULT_QUALITY_SCENARIO_ID)

    request = _build_canary_request(
        model=DEFAULT_MODEL,
        production_data_root=production_data_root,
        max_iterations=1,
        run_budget_usd=0.05,
        quality_scenario=scenario,
    )

    expected_contract = request["context"]["expected_evidence_contract"]
    assert request["request"] == scenario["request"]
    assert request["domain_hint"] == scenario["domain_hint"]
    assert request["context"]["quality_scenario_id"] == DEFAULT_QUALITY_SCENARIO_ID
    assert request["context"]["production_data_root"] == str(production_data_root)
    assert request["context"]["scenario_evidence_contract_id"] == (
        "scenario-evidence-contract:ukraine_msme_wartime_credit_support:v1"
    )
    assert request["context"]["scenario_evidence_contract"]["requirements"]
    assert expected_contract["normative_fact_classes"]
    assert expected_contract["admissible_data_source_families"]
    assert expected_contract["foundry_method_expectations"]
    assert expected_contract["conflict_checks"]


def test_build_canary_request_materializes_policy_intent_fields_for_scenario(
    tmp_path: Path,
) -> None:
    production_data_root = tmp_path / "production_data"
    scenario = load_quality_scenario_contract(DEFAULT_QUALITY_SCENARIO_ID)

    request = _build_canary_request(
        model=DEFAULT_MODEL,
        production_data_root=production_data_root,
        max_iterations=1,
        run_budget_usd=0.05,
        execution_profile="research",
        quality_scenario=scenario,
    )

    context = request["context"]
    intent = build_policy_intent_envelope(
        intent_id="intent-canary",
        run_id="run-canary",
        job_id="job-canary",
        tenant_id="tenant-canary",
        policy_problem=context["policy_problem"],
        desired_outcome=context["desired_outcome"],
        proposed_intervention=context["proposed_intervention"],
        jurisdiction=context["jurisdiction"],
        target_population=context["target_population"],
        policy_time=context["policy_time"],
        data_time=context["data_time"],
        requester_preferred_conclusion=context["requester_preferred_conclusion"],
        requested_authority_level=context["requested_authority_level"],
        authoring_provenance={"source": "local_production_canary"},
    )

    assert intent["requested_authority_level"] == "research"
    assert intent["requested_execution_profile"] == "research"
    assert intent["validation_profile"] == "mvp"
    assert intent["fallback_policy"] == "serious_fallback_fail_closed"


def test_terminal_job_state_detection() -> None:
    assert _is_terminal_job_state({"state": "completed"}) is True
    assert _is_terminal_job_state({"state": "failed"}) is True
    assert _is_terminal_job_state({"state": "running"}) is False
    assert _is_terminal_job_state({"state": "pending"}) is False


def test_extract_provider_preflight_from_progress_shapes() -> None:
    top_level = {"progress": {"provider_preflight": {"status": "ok"}}}
    nested = {"progress": {"details": {"provider_preflight": {"status": "skipped"}}}}

    assert _extract_provider_preflight(top_level) == {"status": "ok"}
    assert _extract_provider_preflight(nested) == {"status": "skipped"}
    assert _extract_provider_preflight({"progress": {}}) is None


def test_materialization_refs_accept_job_or_run_payloads() -> None:
    refs = {
        "data_snapshot_ref": "sha256:" + "1" * 64,
        "input_bindings_ref": "sha256:" + "2" * 64,
        "registry_bundle_ref": "sha256:" + "3" * 64,
        "quality_report_ref": "sha256:" + "4" * 64,
    }
    assert _has_required_materialization_refs({"progress": {"auto_data_source_refs": refs}}, None)
    assert _has_required_materialization_refs(
        None,
        {"run": {"params": {"auto_data_source_refs": refs}}},
    )
    assert not _has_required_materialization_refs(
        {"progress": {"auto_data_source_refs": {"data_snapshot_ref": refs["data_snapshot_ref"]}}},
        None,
    )


def test_local_run_evidence_fallback_reads_trace_timeline_and_lineage(tmp_path: Path) -> None:
    run_id = "R_test"
    run_dir = tmp_path / "cas" / "runs" / run_id
    run_dir.mkdir(parents=True)
    (run_dir / "checkpoint_head.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "checkpoint_ref": "sha256:" + "a" * 64,
                "sequence_number": 2,
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "checkpoint_history.json").write_text(
        json.dumps(
            {
                "entries": [
                    {"run_id": run_id, "checkpoint_ref": "sha256:" + "b" * 64},
                    {"run_id": run_id, "checkpoint_ref": "sha256:" + "c" * 64},
                ]
            }
        ),
        encoding="utf-8",
    )
    events = [
        {
            "ts": "2026-05-12T00:00:00Z",
            "run_id": run_id,
            "phase": "core",
            "event": "RUN_OUTPUT_ADDED",
            "refs": {
                "inputs": [],
                "outputs": [
                    {
                        "artifact_id": "sha256:" + "1" * 64,
                        "kind": "scientist.workflow_report",
                        "media_type": "application/json",
                    }
                ],
            },
            "metrics": {},
        },
        {
            "ts": "2026-05-12T00:00:01Z",
            "run_id": run_id,
            "phase": "core",
            "event": "RUN_FINALIZED",
            "refs": {"inputs": [], "outputs": []},
            "metrics": {"status_ok": 1},
        },
    ]
    (run_dir / "trace.jsonl").write_text(
        "\n".join(json.dumps(event) for event in events) + "\n",
        encoding="utf-8",
    )

    run_payload, timeline_payload, lineage_payload = _load_local_run_evidence(tmp_path, run_id)

    assert run_payload is not None
    assert run_payload["status"] == "completed"
    assert run_payload["trace_event_count"] == 2
    assert run_payload["checkpoint_count"] == 2
    assert timeline_payload is not None
    assert timeline_payload["events"][0]["event"] == "RUN_OUTPUT_ADDED"
    assert lineage_payload is not None
    assert lineage_payload["artifact_refs"][0]["artifact_id"] == "sha256:" + "1" * 64
    assert len(lineage_payload["checkpoint_refs"]) == 2


def test_load_env_file_supports_export_and_quotes_without_overwriting(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "export POLISYOS_LLM_GATEWAY_PROVIDER='gonka_proxy'",
                'POLISYOS_LLM_GATEWAY_BASE_URL="https://proxy.gonka.gg/v1"',
                "EXISTING=from-file",
                "bad-line",
            ]
        ),
        encoding="utf-8",
    )
    env = {"EXISTING": "already"}

    loaded = _load_env_file(env_file, env=env)

    assert loaded == {
        "POLISYOS_LLM_GATEWAY_PROVIDER": "gonka_proxy",
        "POLISYOS_LLM_GATEWAY_BASE_URL": "https://proxy.gonka.gg/v1",
    }
    assert env["EXISTING"] == "already"


def test_runtime_canary_requires_a_separately_injected_bearer() -> None:
    with pytest.raises(RuntimeError, match="short-lived service-principal token"):
        _runtime_canary_bearer_token({})

    token = "eyJ-short-lived-canary-token"  # noqa: S105 - inert test sentinel
    assert _runtime_canary_bearer_token(
        {"POLISYOS_RUNTIME_CANARY_BEARER_TOKEN": token}
    ) == token


def test_runtime_canary_authenticated_client_sends_exact_grant_bearer(
    tmp_path: Path,
    request: pytest.FixtureRequest,
) -> None:
    from fastapi import FastAPI

    import tools.ops_runners.runtime.local_production_canary as canary

    observed_authorization: list[str] = []
    app = FastAPI()
    runtime, token = _runtime_canary_security(tmp_path, request)
    app.state.runtime_deployment_security = runtime

    @app.middleware("http")
    async def _capture_authorization(request, call_next):  # type: ignore[no-untyped-def]
        observed_authorization.append(request.headers.get("authorization", ""))
        return await call_next(request)

    @app.get("/protected")
    def _protected() -> dict[str, bool]:
        return {"ok": True}

    synthetic_token = token("runtime-canary")
    with canary._authenticated_runtime_canary_client(
        app,
        bearer_token=synthetic_token,
    ) as client:
        response = client.get("/protected")

    assert response.status_code == 200
    assert observed_authorization == [f"Bearer {synthetic_token}"]


@pytest.mark.parametrize(
    "subject",
    ["unmanaged-admin", "runtime-canary-over-granted"],
)
def test_runtime_canary_rejects_unmanaged_or_over_granted_token_before_request(
    tmp_path: Path,
    subject: str,
    request: pytest.FixtureRequest,
) -> None:
    import tools.ops_runners.runtime.local_production_canary as canary

    runtime, token = _runtime_canary_security(tmp_path, request)
    app = SimpleNamespace(
        state=SimpleNamespace(runtime_deployment_security=runtime)
    )
    bearer = token(subject)

    with pytest.raises(RuntimeError, match="exact deployment service-principal grant") as exc:
        canary._authenticated_runtime_canary_client(
            app,
            bearer_token=bearer,
        )

    assert bearer not in str(exc.value)


def test_runtime_canary_configuration_removes_fixture_identity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("POLISYOS_ENABLE_DEV_FIXTURE_IDENTITY", "1")

    _configure_local_runtime_env(run_root=tmp_path, mode="simulated", timeout_s=1)

    assert "POLISYOS_ENABLE_DEV_FIXTURE_IDENTITY" not in os.environ


def test_runtime_canary_app_uses_only_deployment_security(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import tools.ops_runners.runtime.local_production_canary as canary

    deployment_config = object()
    deployment_security = object()
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        canary.DeploymentSecurityConfig,
        "from_env",
        lambda: deployment_config,
    )
    monkeypatch.setattr(
        canary,
        "build_deployment_security",
        lambda config: deployment_security if config is deployment_config else None,
    )

    def _capture_app(**kwargs: object) -> object:
        captured.update(kwargs)
        return object()

    monkeypatch.setattr(canary, "create_runtime_api_app", _capture_app)

    _build_runtime_canary_app(
        cas_root=tmp_path / "cas",
        core_runs_root=tmp_path / "runs",
    )

    assert captured["deployment_security"] is deployment_security
    assert captured["enable_security_middlewares"] is True
    assert captured["allow_fixture_identity"] is False
    assert "identity_provider" not in captured
    assert "opa_client" not in captured
