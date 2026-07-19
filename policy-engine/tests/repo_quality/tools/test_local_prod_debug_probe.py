from __future__ import annotations

import json
import os
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

from polisyos.scientist.orchestration.llm.provider_quality import (
    build_controlled_grounding_observation,
)
from tools.quality.testing import local_prod_debug_probe
from tools.quality.validation import check_production_data_scenario_contracts


def test_parser_defaults_to_quick_and_redacts_secret_env(monkeypatch: pytest.MonkeyPatch) -> None:
    parser = local_prod_debug_probe.build_parser()
    args = parser.parse_args([])

    assert args.checks == "quick"
    assert args.output == str(local_prod_debug_probe.DEFAULT_OUTPUT)
    assert args.model == local_prod_debug_probe.DEFAULT_MODEL
    assert args.provider_timeout_s == 20
    assert args.live_timeout_s == 900
    assert args.pg_stress_jobs == 20
    assert args.pg_stress_events_per_job == 5
    assert args.keep_probe_state is False

    monkeypatch.setenv(
        "POLISYOS_CONTROL_POSTGRES_DSN",
        "postgresql://polisyos:super-secret@127.0.0.1:54329/polisyos_control",
    )
    monkeypatch.setenv("POLISYOS_LLM_GATEWAY_API_KEY", "sk-live-secret-value")
    monkeypatch.setenv(
        "POLISYOS_RUNTIME_CANARY_BEARER_TOKEN",
        "runtime-canary-secret-token",
    )
    monkeypatch.setenv(
        "POLISYOS_RUNTIME_DEBUG_PROBE_BEARER_TOKEN",
        "runtime-debug-probe-secret-token",
    )

    sanitized = local_prod_debug_probe.sanitized_env(os.environ)

    rendered = json.dumps(sanitized, sort_keys=True)
    assert "super-secret" not in rendered
    assert "sk-live-secret-value" not in rendered
    assert sanitized["POLISYOS_CONTROL_POSTGRES_DSN"]["redacted"].startswith(
        "postgresql://polisyos:***@127.0.0.1:54329/"
    )
    assert sanitized["POLISYOS_LLM_GATEWAY_API_KEY"]["present"] is True
    assert sanitized["POLISYOS_LLM_GATEWAY_API_KEY"]["fingerprint"].startswith("sha256:")
    assert sanitized["POLISYOS_RUNTIME_CANARY_BEARER_TOKEN"]["present"] is True
    assert sanitized["POLISYOS_RUNTIME_DEBUG_PROBE_BEARER_TOKEN"]["present"] is True
    assert "runtime-canary-secret-token" not in rendered
    assert "runtime-debug-probe-secret-token" not in rendered


def test_debug_probe_requires_a_separately_injected_bearer() -> None:
    with pytest.raises(RuntimeError, match="short-lived service-principal token"):
        local_prod_debug_probe._debug_probe_bearer_token({})

    token = "eyJ-short-lived-debug-probe-token"  # noqa: S105 - inert test sentinel
    assert local_prod_debug_probe._debug_probe_bearer_token(
        {"POLISYOS_RUNTIME_DEBUG_PROBE_BEARER_TOKEN": token}
    ) == token


def test_production_dry_run_exercises_protected_route_with_debug_principal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from fastapi import FastAPI, Response

    observed_authorization: list[str] = []
    app = FastAPI()

    @app.middleware("http")
    async def _capture_authorization(request, call_next):  # type: ignore[no-untyped-def]
        if request.url.path == "/api/v1/runs/local-prod-debug-probe":
            observed_authorization.append(request.headers.get("authorization", ""))
        return await call_next(request)

    @app.get("/health")
    def _health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/v1/runs/{run_id}")
    def _protected_probe(run_id: str) -> Response:
        assert run_id == "local-prod-debug-probe"
        return Response(status_code=404)

    context = local_prod_debug_probe.ProbeContext.for_tests(
        repo_root=tmp_path,
        postgres_dsn="postgresql://probe.invalid/polisyos",
    )
    synthetic_token = "-".join(("eyJ", "debug", "probe", "sentinel"))
    context.runtime_env["POLISYOS_RUNTIME_DEBUG_PROBE_BEARER_TOKEN"] = synthetic_token
    deployment_security = object()
    app.state.runtime_deployment_security = deployment_security
    verified: list[tuple[object, object]] = []

    def _verify_probe_bearer(security: object, env: object) -> str:
        verified.append((security, env))
        return synthetic_token

    monkeypatch.setattr(
        local_prod_debug_probe,
        "_verified_debug_probe_bearer",
        _verify_probe_bearer,
    )
    monkeypatch.setattr(
        local_prod_debug_probe,
        "_build_production_dry_run_app",
        lambda _context: app,
    )

    result = local_prod_debug_probe.run_production_dry_run_check(context)

    assert result["details"]["protected_probe_status"] == 404
    assert result["status"] == "pass", result
    assert observed_authorization == [f"Bearer {synthetic_token}"]
    assert verified == [(deployment_security, context.runtime_env)]


def test_production_dry_run_composes_genuine_deployment_security(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import polisyos.runtime.http.app as app_module

    deployment_config = object()
    deployment_security = object()
    captured: dict[str, object] = {}
    context = local_prod_debug_probe.ProbeContext.for_tests(
        repo_root=tmp_path,
        sqlite_path=tmp_path / "control.sqlite3",
    )
    monkeypatch.setattr(
        local_prod_debug_probe.DeploymentSecurityConfig,
        "from_env",
        lambda: deployment_config,
    )
    monkeypatch.setattr(
        local_prod_debug_probe,
        "build_deployment_security",
        lambda config: deployment_security if config is deployment_config else None,
    )

    def _capture_app(**kwargs: object) -> object:
        captured.update(kwargs)
        return object()

    monkeypatch.setattr(app_module, "create_runtime_api_app", _capture_app)

    local_prod_debug_probe._build_production_dry_run_app(context)

    assert captured["deployment_security"] is deployment_security
    assert captured["enable_security_middlewares"] is True
    assert captured["authz_enforce"] is True
    assert captured["authz_shadow_mode"] is False
    assert captured["allow_fixture_identity"] is False
    assert "identity_provider" not in captured
    assert "opa_client" not in captured


def test_debug_probe_strict_bundle_authenticates_and_enforces_exact_grant(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import jwt
    from cryptography.hazmat.primitives.asymmetric import rsa
    from fastapi.testclient import TestClient

    from tests.unit.runtime.http.test_runtime_deployment_security import (
        _config_mapping,
    )
    from tests.unit.runtime.http.test_runtime_rego_authorization_parity import (
        _opa_eval,
    )

    raw_config = _config_mapping(tmp_path)
    principals = raw_config["service_principals"]
    assert isinstance(principals, list)
    valid_principal = principals[0]
    assert isinstance(valid_principal, dict)
    valid_principal.update(
        {
            "subject": "runtime-debug-probe",
            "permissions": ["runs.view"],
        }
    )
    principals.append(
        {
            **valid_principal,
            "subject": "runtime-debug-no-view",
            "permissions": ["runs.launch"],
        }
    )
    principals.append(
        {
            **valid_principal,
            "subject": "runtime-debug-over-granted",
            "permissions": ["runs.view", "runs.launch"],
        }
    )
    config_path = tmp_path / "runtime-security.json"
    config_path.write_text(json.dumps(raw_config), encoding="utf-8")
    monkeypatch.setenv(
        "POLISYOS_RUNTIME_SERVICE_PRINCIPAL_GRANTS_PATH",
        str(config_path),
    )
    monkeypatch.setenv("POLISYOS_EXECUTION_PROFILE", "dev")
    monkeypatch.setenv("POLISYOS_CONTROL_WORKER_BACKEND", "embedded")
    monkeypatch.setenv("POLISYOS_CONTROL_STATE_STORE_BACKEND", "sqlite")
    monkeypatch.setenv(
        "POLISYOS_CONTROL_SQLITE_PATH",
        str(tmp_path / "control.sqlite3"),
    )
    context = local_prod_debug_probe.ProbeContext.for_tests(
        repo_root=tmp_path,
        sqlite_path=tmp_path / "control.sqlite3",
    )
    app = local_prod_debug_probe._build_production_dry_run_app(context)
    deployment_security = cast("Any", app).state.runtime_deployment_security

    private_key = rsa.generate_private_key(public_exponent=65_537, key_size=2_048)

    class _StaticJWKClient:
        def get_signing_key_from_jwt(self, _token: str) -> SimpleNamespace:
            return SimpleNamespace(key=private_key.public_key())

    deployment_security.identity_provider._jwks_cache["client"] = _StaticJWKClient()
    deployment_security.identity_provider._jwks_cache_expires = float("inf")
    opa_inputs: list[dict[str, Any]] = []

    async def _query_opa(authz_input: Any) -> dict[str, Any]:
        from asyncio import to_thread

        payload = authz_input.to_opa_input()
        opa_inputs.append(payload)
        decision = await to_thread(
            lambda: _opa_eval(
                '{"allow": data.polisyos.authz.decision.allow, '
                '"deny_reasons": data.polisyos.authz.decision.deny_reasons}',
                input_value=payload,
            )
        )
        assert isinstance(decision, dict)
        return decision

    monkeypatch.setattr(deployment_security.opa_client, "_query_opa", _query_opa)
    now = int(time.time())

    def _token(
        subject: str,
        *,
        role: str = "polisyos_viewer",
        signing_key: Any = private_key,
    ) -> str:
        return jwt.encode(
            {
                "iss": "https://idp.example",
                "aud": "polisyos-runtime",
                "sub": subject,
                "tenant_id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
                "cell_id": "018f47a0-0000-7000-8000-000000000001",
                "realm_access": {"roles": [role]},
                "amr": ["pwd", "mfa"],
                "iat": now,
                "exp": now + 60,
                "jti": f"{subject}-{now}",
            },
            signing_key,
            algorithm="RS256",
            headers={"kid": "identity-2026-07"},
        )

    valid_bearer = local_prod_debug_probe._verified_debug_probe_bearer(
        deployment_security,
        {"POLISYOS_RUNTIME_DEBUG_PROBE_BEARER_TOKEN": _token("runtime-debug-probe")},
    )
    rejected_bearers = (
        _token("unmanaged-admin", role="polisyos_admin"),
        _token("runtime-debug-over-granted"),
    )
    for rejected_bearer in rejected_bearers:
        with pytest.raises(
            RuntimeError,
            match="exact deployment service-principal grant",
        ) as exc:
            local_prod_debug_probe._verified_debug_probe_bearer(
                deployment_security,
                {"POLISYOS_RUNTIME_DEBUG_PROBE_BEARER_TOKEN": rejected_bearer},
            )
        assert rejected_bearer not in str(exc.value)

    path = "/api/v1/runs/local-prod-debug-probe"
    tenant_header = {"X-Tenant-ID": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"}
    wrong_key = rsa.generate_private_key(public_exponent=65_537, key_size=2_048)
    with TestClient(app) as client:
        invalid = client.get(
            path,
            headers={
                **tenant_header,
                "Authorization": f"Bearer {_token('runtime-debug-probe', signing_key=wrong_key)}",
            },
        )
        missing_grant = client.get(
            path,
            headers={
                **tenant_header,
                "Authorization": f"Bearer {_token('runtime-debug-no-view')}",
            },
        )
        authorized = client.get(
            path,
            headers={
                **tenant_header,
                "Authorization": f"Bearer {valid_bearer}",
            },
        )

    assert invalid.status_code == 401
    assert missing_grant.status_code == 403
    assert authorized.status_code == 404
    assert len(opa_inputs) == 2
    assert opa_inputs[0]["identity"]["sub"] == "runtime-debug-no-view"
    assert opa_inputs[0]["identity"]["permissions"] == ["runs.launch"]
    assert opa_inputs[1]["identity"]["sub"] == "runtime-debug-probe"
    assert opa_inputs[1]["identity"]["permissions"] == ["runs.view"]
    assert opa_inputs[1]["identity"]["authorization_source"] == (
        "deployment_service_principal"
    )


def test_parse_checks_expands_quick_without_live_or_workflow_heavy_checks() -> None:
    checks = local_prod_debug_probe.parse_checks("quick")

    assert checks == (
        "bootstrap",
        "postgres-lifecycle",
        "stale-recovery",
        "production-dry-run",
        "postgres-resource",
        "production-data-static",
        "docs-repro",
    )
    assert "provider-preflight" not in checks
    assert "live-research-lane" not in checks
    assert "evidence-inspection" not in checks


def test_parse_checks_accepts_provider_quality_controlled_without_quick() -> None:
    checks = local_prod_debug_probe.parse_checks("provider-quality-controlled")

    assert checks == ("provider-quality-controlled",)


def test_bootstrap_matrix_records_expected_fail_closed_contract() -> None:
    result = local_prod_debug_probe.run_bootstrap_check(postgres_dsn="postgresql://example/db")

    assert result["status"] == "pass"
    cases = {case["case_id"]: case for case in result["details"]["cases"]}
    assert cases["production_sqlite"]["status"] == "pass"
    assert cases["production_sqlite"]["observed_error"] == (
        "Execution profile requires PostgreSQL-backed control-plane state store."
    )
    assert cases["production_postgres_missing_dsn"]["observed_error"] == (
        "Execution profile requires POLISYOS_CONTROL_POSTGRES_DSN."
    )
    assert cases["production_embedded_worker"]["observed_error"] == (
        "Execution profile requires POLISYOS_CONTROL_WORKER_BACKEND=external."
    )
    assert cases["production_missing_security_chain"]["observed_error"] == (
        "Execution profile requires runtime security middlewares and providers."
    )
    assert cases["production_security_chain_available"]["status"] == "pass"
    assert cases["production_security_chain_available"]["policy"] == {
        "effective_profile": "production",
        "worker_backend": "external",
        "state_store_backend": "postgres",
        "postgres_dsn_present": True,
    }


def test_store_lifecycle_and_stale_recovery_are_ci_safe_with_sqlite(tmp_path: Path) -> None:
    context = local_prod_debug_probe.ProbeContext.for_tests(
        repo_root=Path.cwd(),
        probe_id="local_probe_test_lifecycle",
        sqlite_path=tmp_path / "control.sqlite3",
    )

    lifecycle = local_prod_debug_probe.run_postgres_lifecycle_check(context)
    stale = local_prod_debug_probe.run_stale_recovery_check(context)

    assert lifecycle["status"] == "pass"
    assert stale["status"] == "pass"
    assert lifecycle["details"]["completed_job"]["state"] == "completed"
    assert lifecycle["details"]["failed_job"]["dead_letter_acknowledged"] is True
    assert stale["details"]["first_lease"]["worker_id"].endswith("_worker_a")
    assert stale["details"]["second_lease"]["worker_id"].endswith("_worker_b")
    assert stale["details"]["attempt_incremented"] is True


def test_live_checks_refuse_without_explicit_operator_approval(tmp_path: Path) -> None:
    context = local_prod_debug_probe.ProbeContext.for_tests(
        repo_root=Path.cwd(),
        output=tmp_path / "probe.json",
        allow_live_provider=False,
    )

    provider = local_prod_debug_probe.run_provider_preflight_check(context)
    lane = local_prod_debug_probe.run_live_research_lane_check(context)

    assert provider["status"] == "skipped"
    assert provider["code"] == "live_provider_not_enabled"
    assert lane["status"] == "skipped"
    assert lane["code"] == "live_provider_not_enabled"


def test_control_plane_timeout_is_resilience_signal_until_artifacts_break() -> None:
    warning = local_prod_debug_probe.classify_control_plane_timeout_signal(
        {
            "code": "control_plane_lease_timeout",
            "layer": "control_plane",
            "phase": "job_lease",
        },
        bundle_path="/tmp/bundle",
        replay_manifest_present=True,
        closeout_artifact_present=True,
    )
    failure = local_prod_debug_probe.classify_control_plane_timeout_signal(
        {
            "code": "control_plane_lease_timeout",
            "layer": "control_plane",
            "phase": "job_lease",
        },
        bundle_path=None,
        replay_manifest_present=False,
        closeout_artifact_present=False,
    )

    assert warning["applies"] is True
    assert warning["status"] == "warn"
    assert warning["root_cause_class"] == "secondary_resilience_signal"
    assert warning["failure_reason"] == (
        "Control-plane timeout was observed, but bundle/replay/closeout "
        "durability remained intact."
    )
    assert failure["status"] == "fail"
    assert failure["root_cause_class"] == "artifact_durability_break"
    assert failure["blocking_artifact_axes"] == [
        "bundle_production",
        "replay_manifest",
        "closeout_artifact",
    ]


def test_provider_preflight_no_key_path_does_not_construct_client(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _unexpected_preflight(**_kwargs: object) -> object:
        raise AssertionError("provider preflight should not be called without an API key")

    monkeypatch.setattr(local_prod_debug_probe, "run_provider_preflight", _unexpected_preflight)
    context = local_prod_debug_probe.ProbeContext.for_tests(
        repo_root=Path.cwd(),
        output=tmp_path / "probe.json",
        allow_live_provider=True,
    )
    context.runtime_env.pop("POLISYOS_LLM_GATEWAY_API_KEY", None)

    result = local_prod_debug_probe.run_provider_preflight_check(context)

    assert result["status"] == "skipped"
    assert result["code"] == "live_provider_not_enabled"


def test_provider_quality_controlled_check_builds_qwen_kimi_gate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _fake_samples(_context: local_prod_debug_probe.ProbeContext) -> list[object]:
        observations = []
        for model_id, fingerprint, prefix in (
            (
                "Qwen/Qwen3-235B-A22B-Instruct-2507-FP8",
                "Qwen/Qwen3-235B-A22B-Instruct-2507-FP8",
                "qwen",
            ),
            ("moonshotai/Kimi-K2.6", "moonshotai/Kimi-K2.6", "kimi"),
        ):
            for index in range(3):
                observations.append(
                    build_controlled_grounding_observation(
                        provider="gonka_proxy",
                        model_id=model_id,
                        model_fingerprint=fingerprint,
                        sample_index=index,
                        request_fingerprint=f"sha256:{prefix}-controlled-{index}",
                        latency_ms=100 + index,
                        cost_usd=0.001,
                    )
                )
        return observations

    monkeypatch.setattr(
        local_prod_debug_probe,
        "_run_controlled_grounding_live_samples",
        _fake_samples,
    )
    context = local_prod_debug_probe.ProbeContext.for_tests(
        repo_root=Path.cwd(),
        output=tmp_path / "probe.json",
        allow_live_provider=True,
    )
    context.runtime_env["POLISYOS_LLM_GATEWAY_API_KEY"] = "sk-live-secret-value"

    result = local_prod_debug_probe.run_provider_quality_controlled_check(context)
    rendered = json.dumps(result, sort_keys=True)

    assert result["status"] == "pass"
    assert result["details"]["comparison"]["summary"]["status"] == "pass"
    assert result["details"]["comparison"]["default_model_gate"]["action"] == "approve"
    assert result["details"]["selected_model"] == local_prod_debug_probe.DEFAULT_MODEL
    assert result["details"]["comparison"]["rows"][0]["sample_count"] == 3
    assert "sk-live-secret-value" not in rendered


def test_optional_postgres_lifecycle_probe_is_gated_by_env(tmp_path: Path) -> None:
    dsn = os.environ.get("POLISYOS_LOCAL_PROD_DEBUG_TEST_POSTGRES_DSN")
    if not dsn:
        pytest.skip("set POLISYOS_LOCAL_PROD_DEBUG_TEST_POSTGRES_DSN to run this integration check")
    context = local_prod_debug_probe.ProbeContext.for_tests(
        repo_root=Path.cwd(),
        output=tmp_path / "probe.json",
        probe_id="local_probe_test_postgres_lifecycle",
        postgres_dsn=dsn,
    )
    context.store_backend = "postgres"

    result = local_prod_debug_probe.run_postgres_lifecycle_check(context)

    assert result["status"] == "pass"
    assert result["details"]["backend"] == "postgres"


def test_production_data_static_passes_with_actionable_construct_blockers(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    production_root = tmp_path / "production_data"
    production_root.mkdir()
    (production_root / "manifest.json").write_text(
        json.dumps({"bundles": {"catalog": {"path": "catalog.duckdb"}}}),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        local_prod_debug_probe,
        "load_production_data_manifest",
        lambda _root: {"bundles": {"catalog": {"path": "catalog.duckdb"}}},
    )
    monkeypatch.setattr(
        local_prod_debug_probe,
        "production_data_evidence_context",
        lambda *_args, **_kwargs: {"production_data_root": str(production_root)},
    )
    monkeypatch.setattr(
        local_prod_debug_probe,
        "production_data_quality_report",
        lambda *_args, **_kwargs: {"status": "pass", "issues": []},
    )
    monkeypatch.setattr(
        local_prod_debug_probe,
        "load_quality_scenario_contract",
        lambda _scenario_id: {"scenario_evidence_contract": {}},
    )
    monkeypatch.setattr(
        local_prod_debug_probe,
        "production_data_contract_binding_report",
        lambda *_args, **_kwargs: {
            "summary": {"status": "blocked"},
            "missing_scenario_source_families": ["credit_program_registry"],
            "scenario_binding_findings": [
                {
                    "requirement_id": "req:credit-program",
                    "expected_family": "credit_program_registry",
                    "status": "blocked",
                }
            ],
            "compiled_data_requirement_specs": [
                {
                    "metadata": {
                        "capability_binding": {
                            "construct_ref": "construct:credit_program_enrollment",
                            "selected_capability_ref": None,
                            "requirement_id": "req:credit-program",
                            "status": "blocked_acquisition_required",
                            "blocked_reasons": ["acquisition_required"],
                            "acquisition_strategies": [
                                {
                                    "strategy_id": "acquisition:acquire_from_nbu_registry",
                                    "owner_team": "team-data-acquisition",
                                }
                            ],
                            "rejected_alternatives": [
                                {
                                    "capability_ref": "capability:simulation-only",
                                    "rejection_reason": "evidence_mode_forbidden",
                                    "rejection_severity": "hard",
                                }
                            ],
                        }
                    }
                }
            ],
        },
    )
    context = local_prod_debug_probe.ProbeContext.for_tests(
        repo_root=tmp_path,
        production_data_root=production_root,
    )

    result = local_prod_debug_probe.run_production_data_static_check(context)

    assert result["status"] == "pass"
    assert result["code"] is None
    details = result["details"]
    assert details["missing_scenario_source_families"] == []
    assert details["construct_capability_blockers"][0]["construct_ref"] == (
        "construct:credit_program_enrollment"
    )
    assert details["construct_capability_blockers"][0]["status"] == (
        "blocked_acquisition_required"
    )
    assert details["construct_capability_blockers"][0]["acquisition_strategies"]
    assert not any(
        issue["code"] == "production_data_scenario_binding_incomplete"
        for issue in details["issues"]
    )


def test_production_data_static_uses_resolver_when_projection_lacks_binding(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    production_root = tmp_path / "production_data"
    production_root.mkdir()
    capability_index = (
        tmp_path
        / "_build/.tmp/production-quality/capability-index/capability_index_v1.duckdb"
    )
    capability_index.parent.mkdir(parents=True)
    capability_index.write_text("fixture", encoding="utf-8")
    (production_root / "manifest.json").write_text(
        json.dumps({"bundles": {"catalog": {"path": "catalog.duckdb"}}}),
        encoding="utf-8",
    )
    _write_governed_scenario_family_construct_rows(tmp_path)

    monkeypatch.setattr(
        local_prod_debug_probe,
        "load_production_data_manifest",
        lambda _root: {"bundles": {"catalog": {"path": "catalog.duckdb"}}},
    )
    monkeypatch.setattr(
        local_prod_debug_probe,
        "production_data_evidence_context",
        lambda *_args, **_kwargs: {"production_data_root": str(production_root)},
    )
    monkeypatch.setattr(
        local_prod_debug_probe,
        "production_data_quality_report",
        lambda *_args, **_kwargs: {"status": "pass", "issues": []},
    )
    monkeypatch.setattr(
        local_prod_debug_probe,
        "load_quality_scenario_contract",
        lambda _scenario_id: {"scenario_evidence_contract": {}},
    )
    monkeypatch.setattr(
        local_prod_debug_probe,
        "production_data_contract_binding_report",
        lambda *_args, **_kwargs: {
            "summary": {"status": "blocked"},
            "missing_scenario_source_families": ["credit_program_registry"],
            "scenario_binding_findings": [
                {
                    "requirement_id": "req:credit-program",
                    "expected_family": "credit_program_registry",
                    "status": "blocked",
                }
            ],
            "compiled_data_requirement_specs": [
                {
                    "requirement_id": "req:credit-program",
                    "claim_id": "claim:credit-program",
                    "claim_use": "claim_evidence_closeout",
                    "required_data_families": ["credit_program_registry"],
                    "scope": {
                        "population": "msme",
                        "geography": "UA",
                        "time": "2022",
                        "jurisdiction": "UA",
                    },
                    "metadata": {},
                }
            ],
        },
    )

    class _Resolver:
        capability_index_ref = "capability-index:test"

        @classmethod
        def from_duckdb(cls, path: Path) -> _Resolver:
            assert path == capability_index
            return cls()

        def resolve(self, query: object) -> object:
            query_payload = cast("Any", query)
            assert query_payload.construct == "credit_program_enrollment"
            return _BindingResult(
                {
                    "requirement_id": "req:credit-program",
                    "status": "blocked_acquisition_required",
                    "construct_ref": "construct:credit_program_enrollment",
                    "selected_capability_ref": None,
                    "capability_index_ref": self.capability_index_ref,
                    "blocked_reasons": ["acquisition_required"],
                    "acquisition_strategies": [
                        {"strategy_id": "acquisition:acquire_from_nbu_registry"}
                    ],
                    "rejected_alternatives": [],
                }
            )

    monkeypatch.setattr(local_prod_debug_probe, "RequirementToCapabilityResolver", _Resolver)
    context = local_prod_debug_probe.ProbeContext.for_tests(
        repo_root=tmp_path,
        production_data_root=production_root,
    )

    result = local_prod_debug_probe.run_production_data_static_check(context)

    assert result["status"] == "pass"
    assert result["code"] is None
    assert result["details"]["missing_scenario_source_families"] == []
    assert result["details"]["construct_capability_report"]["resolver_executed"] is True
    assert result["details"]["compatibility_projection_findings"]
    assert result["details"]["construct_capability_blockers"][0]["status"] == (
        "blocked_acquisition_required"
    )


def test_production_data_static_fails_closed_without_governed_legacy_mapping(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    production_root = tmp_path / "production_data"
    production_root.mkdir()
    capability_index = (
        tmp_path
        / "_build/.tmp/production-quality/capability-index/capability_index_v1.duckdb"
    )
    capability_index.parent.mkdir(parents=True)
    capability_index.write_text("fixture", encoding="utf-8")
    (production_root / "manifest.json").write_text(
        json.dumps({"bundles": {"catalog": {"path": "catalog.duckdb"}}}),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        local_prod_debug_probe,
        "load_production_data_manifest",
        lambda _root: {"bundles": {"catalog": {"path": "catalog.duckdb"}}},
    )
    monkeypatch.setattr(
        local_prod_debug_probe,
        "production_data_evidence_context",
        lambda *_args, **_kwargs: {"production_data_root": str(production_root)},
    )
    monkeypatch.setattr(
        local_prod_debug_probe,
        "production_data_quality_report",
        lambda *_args, **_kwargs: {"status": "pass", "issues": []},
    )
    monkeypatch.setattr(
        local_prod_debug_probe,
        "load_quality_scenario_contract",
        lambda _scenario_id: {"scenario_evidence_contract": {}},
    )
    monkeypatch.setattr(
        local_prod_debug_probe,
        "production_data_contract_binding_report",
        lambda *_args, **_kwargs: {
            "summary": {"status": "blocked"},
            "missing_scenario_source_families": ["credit_program_registry"],
            "scenario_binding_findings": [
                {
                    "requirement_id": "req:credit-program",
                    "expected_family": "credit_program_registry",
                    "status": "blocked",
                }
            ],
            "compiled_data_requirement_specs": [
                {
                    "requirement_id": "req:credit-program",
                    "claim_id": "claim:credit-program",
                    "claim_use": "claim_evidence_closeout",
                    "required_data_families": ["credit_program_registry"],
                    "scope": {
                        "population": "msme",
                        "geography": "UA",
                        "time": "2022",
                        "jurisdiction": "UA",
                    },
                    "metadata": {},
                }
            ],
        },
    )

    class _Resolver:
        capability_index_ref = "capability-index:test"

        @classmethod
        def from_duckdb(cls, path: Path) -> _Resolver:
            assert path == capability_index
            return cls()

        def resolve(self, query: object) -> object:
            raise AssertionError("legacy family mapping must not use hardcoded fallback")

    monkeypatch.setattr(local_prod_debug_probe, "RequirementToCapabilityResolver", _Resolver)
    context = local_prod_debug_probe.ProbeContext.for_tests(
        repo_root=tmp_path,
        production_data_root=production_root,
    )

    result = local_prod_debug_probe.run_production_data_static_check(context)

    assert result["status"] == "fail"
    details = result["details"]
    assert details["construct_capability_report"]["resolver_executed"] is True
    assert details["construct_capability_report"]["binding_count"] == 0
    assert details["construct_capability_report"]["issue_codes"] == [
        "production_data_construct_capability_query_missing"
    ]


def _write_governed_scenario_family_construct_rows(repo_root: Path) -> None:
    path = (
        repo_root
        / "architecture/policy_design_case/layer2_s3_governed_capability_rows.json"
    )
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": (
                    "policyos.policy_design_case.layer2_s3_governed_capability_rows.v1"
                ),
                "scenario_family_construct_rows": [
                    {
                        "scenario_family": "credit_program_registry",
                        "construct": "credit_program_enrollment",
                        "producer_ref": (
                            "repo://architecture/policy_design_case/"
                            "layer2_s3_governed_capability_rows.json"
                            "#scenario-family/credit_program_registry"
                        ),
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


def test_evidence_inspection_preserves_failed_lane_failure_envelope(tmp_path: Path) -> None:
    matrix_path = tmp_path / "failed_live_matrix.json"
    matrix_payload = {
        "schema_version": "policyos.canary_matrix_run.v1",
        "summary": {"failed": 1, "passed": 0},
        "lanes": [
            {
                "lane_id": local_prod_debug_probe.LIVE_RESEARCH_LANE_ID,
                "status": "failed",
                "scorecard_status": "fail",
                "bundle_path": None,
                "failure_envelope": {
                    "code": "no_model_variant_completed",
                    "layer": "llm_gateway",
                    "phase": "model_variants",
                },
            }
        ],
    }
    matrix_path.write_text(json.dumps(matrix_payload), encoding="utf-8")
    context = local_prod_debug_probe.ProbeContext.for_tests(
        repo_root=Path.cwd(),
        output=tmp_path / "probe.json",
        live_matrix_json=matrix_path,
    )

    result = local_prod_debug_probe.run_evidence_inspection_check(context)

    assert result["status"] == "warn"
    assert result["details"]["matrix"]["lanes"][0]["failure_envelope"]["code"] == (
        "no_model_variant_completed"
    )
    assert result["details"]["readiness_mismatch"]["detected"] is False


def test_production_data_static_reports_missing_manifest_cleanly(tmp_path: Path) -> None:
    missing_root = tmp_path / "production_data"
    missing_root.mkdir()
    context = local_prod_debug_probe.ProbeContext.for_tests(
        repo_root=Path.cwd(),
        production_data_root=missing_root,
    )

    result = local_prod_debug_probe.run_production_data_static_check(context)

    assert result["status"] == "fail"
    assert result["code"] == "production_data_manifest_missing"
    assert result["details"]["issues"][0]["code"] == "production_data_manifest_missing"


def test_production_data_static_exports_compatibility_projection_findings(
    tmp_path: Path,
) -> None:
    root = _production_data_root_with_credit_registry_contract(tmp_path)
    context = local_prod_debug_probe.ProbeContext.for_tests(
        repo_root=tmp_path,
        production_data_root=root,
    )

    result = local_prod_debug_probe.run_production_data_static_check(context)

    assert result["status"] == "fail"
    assert result["code"] == "production_data_construct_capability_evidence_missing"
    assert result["details"]["construct_capability_blockers"] == []
    assert result["details"]["construct_capability_report"]["resolver_executed"] is False
    assert result["details"]["compatibility_projection_findings"]
    assert result["details"]["missing_scenario_source_families"] == [
        "production_msme_panel",
        "regional_displacement_indicators",
    ]
    findings = {
        finding["expected_family"]: finding
        for finding in result["details"]["scenario_binding_findings"]
    }
    assert findings["credit_program_registry"]["status"] == "satisfied"
    assert findings["credit_program_registry"]["missing_facets"] == []
    assert findings["production_msme_panel"]["status"] == "blocked"
    assert findings["production_msme_panel"]["candidate_ref"] is None
    assert {
        "requirement_id",
        "candidate_ref",
        "status",
        "missing_facets",
    } <= set(findings["credit_program_registry"])
    assert not any(
        issue["code"] == "production_data_scenario_binding_incomplete"
        for issue in result["details"]["issues"]
    )


def test_production_data_scenario_contract_checker_reports_projection_findings_without_resolver(
    tmp_path: Path,
) -> None:
    root = _production_data_root_with_credit_registry_contract(tmp_path)

    report = check_production_data_scenario_contracts.build_report(
        repo_root=Path.cwd(),
        production_data_root=root,
        scenario="scenario-public_golden",
    )

    assert report["status"] == "fail"
    assert report["scenario_id"] == "ukraine_msme_wartime_credit_support"
    assert report["requirement_source"] == "compiled_data_requirement_spec"
    assert {
        family
        for spec in report["compiled_data_requirement_specs"]
        for family in spec["required_data_families"]
    } >= {
        "production_msme_panel",
        "credit_program_registry",
        "regional_displacement_indicators",
    }
    assert report["summary"]["construct_capability_blockers"] == 0
    assert report["missing_scenario_source_families"] == [
        "production_msme_panel",
        "regional_displacement_indicators",
    ]
    assert {
        finding["code"] for finding in report["findings"]
    } == {"production_data_scenario_family_missing"}
    assert {
        finding["expected_family"] for finding in report["findings"]
    } >= {
        "production_msme_panel",
        "regional_displacement_indicators",
    }


def test_docs_repro_checks_runbook_and_gitignore_contract() -> None:
    context = local_prod_debug_probe.ProbeContext.for_tests(repo_root=Path.cwd())

    result = local_prod_debug_probe.run_docs_repro_check(context)

    assert result["status"] == "pass"
    assert result["details"]["env_prod_local_gitignored"] is True
    assert "tools/quality/testing/local_prod_debug_probe.py" in result["details"]["runbook_text"]


def test_docs_repro_check_catches_stale_runbook_references(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runbook = tmp_path / "docs/runbooks/local-production-debugging.md"
    runbook.parent.mkdir(parents=True)
    runbook.write_text(
        "# Local Production Debugging Runbook\n\n"
        "Container: polisyos-control-pg\n"
        "Env: .env.prod-local\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        local_prod_debug_probe.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(returncode=0),
    )
    context = local_prod_debug_probe.ProbeContext.for_tests(repo_root=tmp_path)

    result = local_prod_debug_probe.run_docs_repro_check(context)

    assert result["status"] == "fail"
    assert "tools/quality/testing/local_prod_debug_probe.py" in result["details"][
        "missing_runbook_terms"
    ]


def test_cli_writes_schema_and_returns_failed_status_for_missing_postgres_dsn(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("POLISYOS_CONTROL_POSTGRES_DSN", raising=False)
    monkeypatch.setattr(local_prod_debug_probe, "_runtime_env", lambda _repo_root: {})
    output = tmp_path / "probe.json"

    exit_code = local_prod_debug_probe.main(
        [
            "--repo-root",
            str(Path.cwd()),
            "--checks",
            "postgres-lifecycle",
            "--output",
            str(output),
        ]
    )

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert exit_code == 3
    assert payload["schema_version"] == "policyos.local_prod_debug_probe.v1"
    assert payload["summary"]["status"] == "invalid"
    assert payload["checks"][0]["code"] == "postgres_dsn_missing"


def test_cli_missing_postgres_dsn_still_runs_static_production_data_checks(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _production_data_root_with_credit_registry_contract(
        tmp_path,
        source_families=(
            "production_msme_panel",
            "credit_program_registry",
            "regional_displacement_indicators",
        ),
    )
    monkeypatch.delenv("POLISYOS_CONTROL_POSTGRES_DSN", raising=False)
    monkeypatch.setenv("POLISYOS_PRODUCTION_DATA_ROOT", str(root))
    monkeypatch.setattr(
        local_prod_debug_probe,
        "_runtime_env",
        lambda _repo_root: {"POLISYOS_PRODUCTION_DATA_ROOT": str(root)},
    )
    output = tmp_path / "probe.json"

    exit_code = local_prod_debug_probe.main(
        [
            "--repo-root",
            str(Path.cwd()),
            "--checks",
            "postgres-lifecycle,production-data-static,docs-repro",
            "--output",
            str(output),
        ]
    )

    payload = json.loads(output.read_text(encoding="utf-8"))
    checks = {check["name"]: check for check in payload["checks"]}
    assert exit_code == 3
    assert payload["summary"]["status"] == "invalid"
    assert checks["postgres-lifecycle"]["code"] == "postgres_dsn_missing"
    assert checks["production-data-static"]["code"] != (
        "production_data_scenario_contracts_missing"
    )
    assert checks["production-data-static"]["details"][
        "missing_scenario_source_families"
    ] == []


def _production_data_root_with_credit_registry_contract(
    tmp_path: Path,
    *,
    source_families: tuple[str, ...] = ("credit_program_registry",),
) -> Path:
    root = tmp_path / "production_data"
    curated = root / "canonical/local_data_20260501/policy_engine_data/curated"
    curated.mkdir(parents=True)
    manifest = {
        "schema_version": "1.0",
        "generated_at": "2026-05-01T00:00:00Z",
        "bundles": {
            "curated": {
                "role": "fabric_curated_catalog",
                "version_id": "local_data_20260501",
                "readiness": "ready",
                "path": "canonical/local_data_20260501/policy_engine_data/curated",
                "required_files": [
                    "data_contracts.json",
                    "source_bindings.json",
                    "source_contracts_v2.json",
                ],
            }
        },
    }
    scenario_source_families = list(source_families)

    def _contract(source_family: str) -> dict[str, object]:
        return {
            "contract_id": f"contract.{source_family}",
            "source_family": source_family,
            "dataset_identity": f"dataset:{source_family}:202605",
            "source_contract_ref": f"source-contract:{source_family}:v1",
            "source_rights": "public_sector_reuse",
            "dictionary_ref": "sha256:" + "d" * 64,
            "schema_ref": "sha256:" + "s" * 64,
            "field_refs": ["program_id", "firm_id", "region", "credit_amount"],
            "unit_refs": ["uah", "firm"],
            "geography_refs": ["UA", "oblast"],
            "time_coverage_refs": ["2024-01-01/2026-05-01"],
            "quality_refs": [f"quality:{source_family}:v1"],
            "missingness_refs": [f"missingness:{source_family}:v1"],
            "lineage_refs": [f"lineage:{source_family}:v1"],
            "transformation_refs": [f"transform:{source_family}:v1"],
            "derived_feature_bindings": ["feature:wartime_credit_intensity:v1"],
            "freshness_ref": "freshness:2026-05-01",
            "recency_ref": "as_of:2026-05-01",
            "quality_assertion_refs": [f"quality-assertion:{source_family}:v1"],
            "construct_validity_refs": [f"construct:{source_family}:v1"],
            "outlier_refs": [f"outliers:{source_family}:v1"],
            "claim_bindability_refs": [f"claim-bindability:{source_family}:v1"],
        }

    contracts = [_contract(source_family) for source_family in scenario_source_families]
    bindings = [
        {
            "binding_id": f"binding.{source_family}",
            "contract_id": f"contract.{source_family}",
            "scenario_source_family": source_family,
            "connector_id": f"fixture.{source_family}",
            "dataset_id": f"{source_family}_snapshot",
        }
        for source_family in scenario_source_families
    ]
    source_contracts = {
        f"source-contract:{source_family}:v1": {
            "id": f"source-contract:{source_family}:v1",
            "version": "1.1.0",
            "status": "active",
            "content_hash": "sha256:" + "c" * 64,
            "contract": {
                "id": f"source-contract:{source_family}:v1",
                "version": "1.1.0",
                "status": "active",
            },
        }
        for source_family in scenario_source_families
    }
    (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (curated / "data_contracts.json").write_text(
        json.dumps({"schema_version": "1.0", "contracts": contracts}),
        encoding="utf-8",
    )
    (curated / "source_bindings.json").write_text(
        json.dumps({"schema_version": "1.0", "bindings": bindings}),
        encoding="utf-8",
    )
    (curated / "source_contracts_v2.json").write_text(
        json.dumps(
            {
                "schema_version": "fabric.source_contract.v2",
                "contracts": source_contracts,
            }
        ),
        encoding="utf-8",
    )
    return root


class _BindingResult:
    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = payload

    def model_dump(self, **_kwargs: object) -> dict[str, object]:
        return dict(self._payload)
