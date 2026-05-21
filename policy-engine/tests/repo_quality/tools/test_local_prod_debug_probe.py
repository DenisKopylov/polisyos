from __future__ import annotations

import json
import os
from pathlib import Path
from types import SimpleNamespace

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

    sanitized = local_prod_debug_probe.sanitized_env(os.environ)

    rendered = json.dumps(sanitized, sort_keys=True)
    assert "super-secret" not in rendered
    assert "sk-live-secret-value" not in rendered
    assert sanitized["POLISYOS_CONTROL_POSTGRES_DSN"]["redacted"].startswith(
        "postgresql://polisyos:***@127.0.0.1:54329/"
    )
    assert sanitized["POLISYOS_LLM_GATEWAY_API_KEY"]["present"] is True
    assert sanitized["POLISYOS_LLM_GATEWAY_API_KEY"]["fingerprint"].startswith("sha256:")


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


def test_production_data_static_exports_scenario_binding_findings(tmp_path: Path) -> None:
    root = _production_data_root_with_credit_registry_contract(tmp_path)
    context = local_prod_debug_probe.ProbeContext.for_tests(
        repo_root=Path.cwd(),
        production_data_root=root,
    )

    result = local_prod_debug_probe.run_production_data_static_check(context)

    assert result["status"] == "fail"
    assert result["code"] == "production_data_scenario_contracts_missing"
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
    assert any(
        issue["code"] == "production_data_scenario_binding_incomplete"
        and issue["expected_family"] == "production_msme_panel"
        for issue in result["details"]["issues"]
    )


def test_production_data_scenario_contract_checker_blocks_missing_families(
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
    assert report["summary"]["satisfied"] == 1
    assert report["missing_scenario_source_families"] == [
        "production_msme_panel",
        "regional_displacement_indicators",
    ]
    assert {
        finding["code"] for finding in report["findings"]
    } == {"production_data_scenario_family_missing"}
    assert all(
        "source_family" in finding["missing_facets"]
        for finding in report["findings"]
    )


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


def _production_data_root_with_credit_registry_contract(tmp_path: Path) -> Path:
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
                "required_files": ["data_contracts.json", "source_bindings.json"],
            }
        },
    }
    contract = {
        "contract_id": "contract.credit_registry",
        "source_family": "credit_program_registry",
        "dataset_identity": "dataset:credit_program_registry:202605",
        "source_rights": "public_sector_reuse",
        "dictionary_ref": "sha256:" + "d" * 64,
        "schema_ref": "sha256:" + "s" * 64,
        "field_refs": ["program_id", "firm_id", "region", "credit_amount"],
        "unit_refs": ["uah", "firm"],
        "geography_refs": ["UA", "oblast"],
        "time_coverage_refs": ["2024-01-01/2026-05-01"],
        "quality_refs": ["quality:credit-program-registry:v1"],
        "missingness_refs": ["missingness:credit-program-registry:v1"],
        "lineage_refs": ["lineage:ministry-credit-registry:v1"],
        "transformation_refs": ["transform:normalize-credit-program-registry:v1"],
        "derived_feature_bindings": ["feature:wartime_credit_intensity:v1"],
        "freshness_ref": "freshness:2026-05-01",
        "recency_ref": "as_of:2026-05-01",
        "quality_assertion_refs": ["quality-assertion:credit-program-registry:v1"],
        "construct_validity_refs": ["construct:credit-program-eligibility:v1"],
        "outlier_refs": ["outliers:credit-program-registry:v1"],
        "claim_bindability_refs": ["claim-bindability:credit-program-registry:v1"],
    }
    binding = {
        "binding_id": "binding.credit_registry",
        "contract_id": "contract.credit_registry",
        "scenario_source_family": "credit_program_registry",
        "connector_id": "ministry.credit_registry",
        "dataset_id": "wartime_credit_programs",
    }
    (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (curated / "data_contracts.json").write_text(
        json.dumps({"schema_version": "1.0", "contracts": [contract]}),
        encoding="utf-8",
    )
    (curated / "source_bindings.json").write_text(
        json.dumps({"schema_version": "1.0", "bindings": [binding]}),
        encoding="utf-8",
    )
    return root
