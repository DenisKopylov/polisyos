#!/usr/bin/env python3
"""Run lightweight local production-debug validation probes."""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import subprocess
import sys
import time
from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlsplit, urlunsplit

from polisyos.core.contracts import (
    RequirementToCapabilityQuery,
    construct_for_legacy_family,
)
from polisyos.core.security.authz import AuthzDecision, AuthzResult
from polisyos.runtime.http.execution_policy import (
    RuntimeBootstrapError,
    RuntimeExecutionPolicyResolver,
)
from polisyos.runtime.http.services.control.production_data import (
    load_production_data_manifest,
    production_data_contract_binding_report,
    production_data_evidence_context,
    production_data_quality_report,
)
from polisyos.runtime.http.services.control_plane_store import ControlPlaneStore
from polisyos.runtime.quality.capability_resolver import RequirementToCapabilityResolver
from polisyos.runtime.quality.diagnostic_events import (
    DIAGNOSTIC_EVENT_SCHEMA_NAME,
    DIAGNOSTIC_EVENT_SCHEMA_VERSION,
    DiagnosticEvent,
)
from polisyos.scientist.orchestration.llm.gateway_client import GatewayLLMClient
from polisyos.scientist.orchestration.llm.provider_quality import (
    DefaultProductionModelChoice,
    build_controlled_grounding_observation,
    build_controlled_provider_model_comparison,
    controlled_grounding_task,
)
from polisyos.scientist.orchestration.llm.provider_verification import run_provider_preflight
from tools.ops_runners.runtime.quality_scenarios import (
    DEFAULT_QUALITY_SCENARIO_ID,
    load_quality_scenario_contract,
)

SCHEMA_VERSION = "policyos.local_prod_debug_probe.v1"
DEFAULT_OUTPUT = Path("_build/.tmp/production-quality/local_prod_debug_probe.json")
DEFAULT_CAPABILITY_INDEX = Path(
    "_build/.tmp/production-quality/capability-index/capability_index_v1.duckdb"
)
DEFAULT_MODEL = "Qwen/Qwen3-235B-A22B-Instruct-2507-FP8"
KIMI_MODEL = "moonshotai/Kimi-K2.6"
LIVE_RESEARCH_LANE_ID = (
    "profile-research__provider-live_gonka_proxy__data-canonical_production"
    "__scenario-public_golden__ui-api_only"
)
QUICK_CHECKS = (
    "bootstrap",
    "postgres-lifecycle",
    "stale-recovery",
    "production-dry-run",
    "postgres-resource",
    "production-data-static",
    "docs-repro",
)
VALID_CHECKS = frozenset(
    {
        "quick",
        "bootstrap",
        "postgres-lifecycle",
        "stale-recovery",
        "production-dry-run",
        "provider-preflight",
        "provider-quality-controlled",
        "live-research-lane",
        "evidence-inspection",
        "postgres-resource",
        "production-data-static",
        "docs-repro",
    }
)
POSTGRES_REQUIRED_CHECKS = frozenset(
    {
        "postgres-lifecycle",
        "stale-recovery",
        "production-dry-run",
        "postgres-resource",
    }
)
SECRET_ENV_KEYS = (
    "POLISYOS_CONTROL_POSTGRES_DSN",
    "POLISYOS_LLM_GATEWAY_API_KEY",
    "POLISYOS_DELEGATION_SECRET",
)
VISIBLE_ENV_KEYS = (
    "POLISYOS_EXECUTION_PROFILE",
    "POLISYOS_CONTROL_WORKER_BACKEND",
    "POLISYOS_CONTROL_STATE_STORE_BACKEND",
    "POLISYOS_LLM_GATEWAY_BASE_URL",
    "POLISYOS_LLM_GATEWAY_PROVIDER",
    "POLISYOS_PRODUCTION_DATA_ROOT",
)
STATUS_ORDER = {"fail": 3, "invalid": 3, "warn": 2, "skipped": 1, "pass": 0}


@dataclass
class ProbeContext:
    """Runtime configuration for one local production-debug probe run."""

    repo_root: Path
    output: Path = DEFAULT_OUTPUT
    probe_id: str = field(default_factory=lambda: _new_probe_id())
    store_backend: str = "postgres"
    postgres_dsn: str | None = None
    sqlite_path: Path = Path(".polisyos/local-prod-debug/probe.sqlite3")
    allow_live_provider: bool = False
    require_passing: bool = False
    model: str = DEFAULT_MODEL
    provider_timeout_s: int = 20
    live_timeout_s: int = 900
    pg_stress_jobs: int = 20
    pg_stress_events_per_job: int = 5
    keep_probe_state: bool = False
    production_data_root: Path | None = None
    live_matrix_json: Path | None = None
    runtime_env: dict[str, str] = field(default_factory=dict)
    artifacts: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def for_tests(
        cls,
        *,
        repo_root: Path,
        output: Path | None = None,
        probe_id: str = "local_probe_test",
        sqlite_path: Path | None = None,
        postgres_dsn: str | None = None,
        allow_live_provider: bool = False,
        production_data_root: Path | None = None,
        live_matrix_json: Path | None = None,
    ) -> ProbeContext:
        backend = "sqlite" if sqlite_path is not None else "postgres"
        return cls(
            repo_root=repo_root,
            output=output or DEFAULT_OUTPUT,
            probe_id=probe_id,
            store_backend=backend,
            postgres_dsn=postgres_dsn,
            sqlite_path=sqlite_path or Path(".polisyos/local-prod-debug/test.sqlite3"),
            allow_live_provider=allow_live_provider,
            production_data_root=production_data_root,
            live_matrix_json=live_matrix_json,
            runtime_env=dict(os.environ),
        )


def build_parser() -> argparse.ArgumentParser:
    """Build CLI parser for local production-debug probes."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--checks", default="quick")
    parser.add_argument("--postgres-dsn", default="")
    parser.add_argument("--allow-live-provider", action="store_true")
    parser.add_argument("--require-passing", action="store_true")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--provider-timeout-s", type=int, default=20)
    parser.add_argument("--live-timeout-s", type=int, default=900)
    parser.add_argument("--pg-stress-jobs", type=int, default=20)
    parser.add_argument("--pg-stress-events-per-job", type=int, default=5)
    parser.add_argument("--keep-probe-state", action="store_true")
    return parser


def parse_checks(raw: str) -> tuple[str, ...]:
    """Parse comma-separated check aliases into stable check ids."""
    selected: list[str] = []
    for item in (part.strip() for part in str(raw or "quick").split(",")):
        if not item:
            continue
        if item not in VALID_CHECKS:
            raise ValueError(f"unknown local-prod-debug check: {item}")
        if item == "quick":
            selected.extend(QUICK_CHECKS)
        else:
            selected.append(item)
    deduped = tuple(dict.fromkeys(selected or QUICK_CHECKS))
    return deduped


def sanitized_env(env: Mapping[str, str]) -> dict[str, Any]:
    """Return a secret-free environment summary for probe JSON."""
    payload: dict[str, Any] = {}
    for key in VISIBLE_ENV_KEYS:
        if key in env:
            payload[key] = env[key]
    for key in SECRET_ENV_KEYS:
        value = env.get(key)
        if key == "POLISYOS_CONTROL_POSTGRES_DSN":
            payload[key] = {
                "present": bool(value),
                "redacted": _redact_dsn(value) if value else None,
            }
        else:
            payload[key] = {
                "present": bool(value),
                "fingerprint": _secret_fingerprint(value),
            }
    return payload


def run_bootstrap_check(*, postgres_dsn: str | None) -> dict[str, Any]:
    """Check production profile fail-closed bootstrap behavior."""
    cases = [
        {
            "case_id": "production_sqlite",
            "worker": "external",
            "store": "sqlite",
            "dsn": postgres_dsn,
            "security": True,
            "expected_error": (
                "Execution profile requires PostgreSQL-backed control-plane state store."
            ),
        },
        {
            "case_id": "production_postgres_missing_dsn",
            "worker": "external",
            "store": "postgres",
            "dsn": None,
            "security": True,
            "expected_error": "Execution profile requires POLISYOS_CONTROL_POSTGRES_DSN.",
        },
        {
            "case_id": "production_embedded_worker",
            "worker": "embedded",
            "store": "postgres",
            "dsn": postgres_dsn or "postgresql://example.invalid/polisyos",
            "security": True,
            "expected_error": (
                "Execution profile requires POLISYOS_CONTROL_WORKER_BACKEND=external."
            ),
        },
        {
            "case_id": "production_missing_security_chain",
            "worker": "external",
            "store": "postgres",
            "dsn": postgres_dsn or "postgresql://example.invalid/polisyos",
            "security": False,
            "expected_error": (
                "Execution profile requires runtime security middlewares and providers."
            ),
        },
        {
            "case_id": "production_security_chain_available",
            "worker": "external",
            "store": "postgres",
            "dsn": postgres_dsn or "postgresql://example.invalid/polisyos",
            "security": True,
            "expected_error": None,
        },
    ]
    observed: list[dict[str, Any]] = []
    for case in cases:
        resolver = RuntimeExecutionPolicyResolver(
            default_profile="production",
            worker_backend=str(case["worker"]),
            state_store_backend=str(case["store"]),
            sqlite_path=".polisyos/local-prod-debug/control.sqlite3",
            postgres_dsn=case["dsn"],
        )
        expected_error = case["expected_error"]
        try:
            policy = resolver.validate_bootstrap(
                authz_shadow_mode=False,
                security_chain_available=bool(case["security"]),
            )
        except RuntimeBootstrapError as exc:
            observed_error = str(exc)
            observed.append(
                {
                    "case_id": case["case_id"],
                    "status": "pass" if observed_error == expected_error else "fail",
                    "observed_error": observed_error,
                    "expected_error": expected_error,
                }
            )
        else:
            observed.append(
                {
                    "case_id": case["case_id"],
                    "status": "pass" if expected_error is None else "fail",
                    "observed_error": None,
                    "expected_error": expected_error,
                    "policy": {
                        "effective_profile": policy.effective_profile,
                        "worker_backend": policy.worker_backend,
                        "state_store_backend": policy.state_store_backend,
                        "postgres_dsn_present": bool(policy.postgres_dsn),
                    },
                }
            )
    return _check_result(
        "bootstrap",
        _worst_status(item["status"] for item in observed),
        details={"cases": observed},
    )


def run_postgres_lifecycle_check(context: ProbeContext) -> dict[str, Any]:
    """Exercise durable control-plane lifecycle operations."""
    store = _make_store(context)
    try:
        worker_id = f"{context.probe_id}_worker_lifecycle"
        completed_job_id = f"{context.probe_id}_job_completed"
        failed_job_id = f"{context.probe_id}_job_failed"
        outbox_key = f"{context.probe_id}:outbox-idempotency"
        store.heartbeat_worker(
            worker_id=worker_id,
            state="idle",
            lease_seconds=30,
            backend=context.store_backend,
            metadata={"probe": context.probe_id},
        )
        completed = store.create_job(
            job_id=completed_job_id,
            kind="workflow_run",
            run_id=f"{context.probe_id}_run_completed",
            pipeline_id=f"{context.probe_id}_pipeline_completed",
            requested_execution_profile="research",
            effective_execution_profile="research",
            policy_flags={},
            capability_manifest_ref=None,
            payload_ref=None,
            submitted_by="local-prod-debug",
        )
        leased = store.lease_next_job(worker_id=worker_id, lease_seconds=30)
        if leased is None or leased.job_id != completed.job_id:
            return _check_result(
                "postgres-lifecycle",
                "fail",
                code="control_job_lease_failed",
                message="Created probe job was not leased by the control-plane store.",
            )
        store.update_progress_state(
            job_id=completed_job_id,
            state="running",
            progress={"phase": "local_prod_debug_lifecycle", "probe_id": context.probe_id},
        )
        store.complete_job(
            job_id=completed_job_id,
            progress={"phase": "completed", "probe_id": context.probe_id},
        )
        first_outbox = store.enqueue_outbox_event(
            topic="control.local_prod_debug_probe",
            event_key=outbox_key,
            job_id=completed_job_id,
            run_id=f"{context.probe_id}_run_completed",
            payload={"probe_id": context.probe_id},
        )
        second_outbox = store.enqueue_outbox_event(
            topic="control.local_prod_debug_probe",
            event_key=outbox_key,
            job_id=completed_job_id,
            run_id=f"{context.probe_id}_run_completed",
            payload={"probe_id": context.probe_id},
        )
        store.release_worker(worker_id=worker_id)

        store.create_job(
            job_id=failed_job_id,
            kind="workflow_run",
            run_id=f"{context.probe_id}_run_failed",
            pipeline_id=f"{context.probe_id}_pipeline_failed",
            requested_execution_profile="research",
            effective_execution_profile="research",
            policy_flags={},
            capability_manifest_ref=None,
            payload_ref=None,
            submitted_by="local-prod-debug",
        )
        store.fail_job(job_id=failed_job_id, error_message="local-prod-debug failure")
        dead_letters = [row for row in store.list_dead_letter_jobs() if row.job_id == failed_job_id]
        if not dead_letters:
            return _check_result(
                "postgres-lifecycle",
                "fail",
                code="dead_letter_missing",
                message="Failed probe job did not create a dead-letter row.",
            )
        store.acknowledge_dead_letter_job(
            job_id=failed_job_id,
            acknowledged_by="local-prod-debug",
        )
        acknowledged = [
            row
            for row in store.list_dead_letter_jobs(acknowledged=True)
            if row.job_id == failed_job_id
        ]
        completed_after = store.get_job(completed_job_id)
        failed_after = store.get_job(failed_job_id)
        details = {
            "backend": context.store_backend,
            "completed_job": {
                "job_id": completed_job_id,
                "state": completed_after.state if completed_after else None,
                "outbox_idempotent": first_outbox.event_id == second_outbox.event_id,
            },
            "failed_job": {
                "job_id": failed_job_id,
                "state": failed_after.state if failed_after else None,
                "dead_letter_created": bool(dead_letters),
                "dead_letter_acknowledged": bool(acknowledged),
            },
        }
        status = (
            "pass"
            if completed_after
            and completed_after.state == "completed"
            and failed_after
            and failed_after.state == "failed"
            and first_outbox.event_id == second_outbox.event_id
            and acknowledged
            else "fail"
        )
        return _check_result("postgres-lifecycle", status, details=details)
    finally:
        if not context.keep_probe_state:
            _cleanup_probe_rows(store, context.probe_id)
        store.close()


def run_stale_recovery_check(context: ProbeContext) -> dict[str, Any]:
    """Check that expired running leases can be recovered by a second worker."""
    store = _make_store(context)
    try:
        job_id = f"{context.probe_id}_job_stale_recovery"
        worker_a = f"{context.probe_id}_worker_a"
        worker_b = f"{context.probe_id}_worker_b"
        store.create_job(
            job_id=job_id,
            kind="workflow_run",
            run_id=f"{context.probe_id}_run_stale_recovery",
            pipeline_id=None,
            requested_execution_profile="research",
            effective_execution_profile="research",
            policy_flags={},
            capability_manifest_ref=None,
            payload_ref=None,
            submitted_by="local-prod-debug",
        )
        store.heartbeat_worker(
            worker_id=worker_a,
            state="running",
            lease_seconds=1,
            backend=context.store_backend,
            active_job_id=job_id,
        )
        first = store.lease_next_job(worker_id=worker_a, lease_seconds=1)
        time.sleep(1.2)
        second = store.lease_next_job(worker_id=worker_b, lease_seconds=10)
        if second is not None:
            store.heartbeat_worker(
                worker_id=worker_b,
                state="running",
                lease_seconds=10,
                backend=context.store_backend,
                active_job_id=job_id,
            )
            store.complete_job(job_id=job_id, progress={"phase": "stale_recovered"})
        active_workers = store.list_worker_leases(active_only=True)
        attempt_incremented = bool(
            first is not None and second is not None and second.attempt > first.attempt
        )
        details = {
            "first_lease": {
                "worker_id": worker_a,
                "job_id": first.job_id if first else None,
                "attempt": first.attempt if first else None,
            },
            "second_lease": {
                "worker_id": worker_b,
                "job_id": second.job_id if second else None,
                "attempt": second.attempt if second else None,
            },
            "attempt_incremented": attempt_incremented,
            "active_workers": [worker.worker_id for worker in active_workers],
            "diagnostic_summary": {
                "stale_worker_released_by_expiry": worker_a
                not in {worker.worker_id for worker in active_workers},
                "recovered_by": worker_b if second else None,
            },
        }
        status = "pass" if second and second.job_id == job_id and attempt_incremented else "fail"
        return _check_result("stale-recovery", status, details=details)
    finally:
        if not context.keep_probe_state:
            _cleanup_probe_rows(store, context.probe_id)
        store.close()


def run_production_dry_run_check(context: ProbeContext) -> dict[str, Any]:
    """Dry-run strict production bootstrap and health route composition."""
    if not context.postgres_dsn and context.store_backend == "postgres":
        return _missing_dsn_result("production-dry-run")
    env = _production_env(context)
    with _temporary_environ(env):
        try:
            RuntimeExecutionPolicyResolver.from_env().validate_bootstrap(
                authz_shadow_mode=False,
                security_chain_available=False,
            )
        except RuntimeBootstrapError as exc:
            blocker = str(exc)
        else:
            blocker = None
        try:
            from fastapi.testclient import TestClient

            from polisyos.runtime.http.app import create_runtime_api_app

            app = create_runtime_api_app(
                cas_root=context.repo_root / ".polisyos" / "local-prod-debug" / "dry-run-cas",
                core_runs_root=context.repo_root
                / ".polisyos"
                / "local-prod-debug"
                / "dry-run-runs",
                identity_provider=object(),
                cell_registry=object(),
                opa_client=_AllowingOPAClient(),
                authz_enforce=True,
                authz_shadow_mode=False,
                allow_fixture_identity=False,
            )
            with TestClient(app) as client:
                response = client.get("/health")
                health_status = response.status_code
        except Exception as exc:
            return _check_result(
                "production-dry-run",
                "fail",
                code="production_dry_run_failed",
                message=str(exc),
                details={"missing_security_chain_blocker": blocker},
            )
    expected_blocker = "Execution profile requires runtime security middlewares and providers."
    status = "pass" if blocker == expected_blocker and 200 <= health_status < 300 else "fail"
    return _check_result(
        "production-dry-run",
        status,
        details={
            "missing_security_chain_blocker": blocker,
            "health_status": health_status,
            "strict_profile": {
                "execution_profile": "production",
                "worker_backend": "external",
                "state_store_backend": context.store_backend,
                "postgres_dsn_present": bool(context.postgres_dsn),
                "authz_shadow_mode": False,
            },
        },
    )


def run_provider_preflight_check(context: ProbeContext) -> dict[str, Any]:
    """Run the explicit live-provider preflight check."""
    api_key = context.runtime_env.get("POLISYOS_LLM_GATEWAY_API_KEY")
    if not context.allow_live_provider or not api_key:
        return _check_result(
            "provider-preflight",
            "skipped",
            code="live_provider_not_enabled",
            message="Provider preflight requires --allow-live-provider and an API key.",
        )
    try:
        report = asyncio.run(
            run_provider_preflight(
                models=[context.model],
                base_url=context.runtime_env.get("POLISYOS_LLM_GATEWAY_BASE_URL"),
                provider=context.runtime_env.get("POLISYOS_LLM_GATEWAY_PROVIDER"),
                api_key=api_key,
                api_key_env="POLISYOS_LLM_GATEWAY_API_KEY",
                timeout_s=float(context.provider_timeout_s),
                ttl_s=0,
            )
        )
    except Exception as exc:
        return _check_result(
            "provider-preflight",
            "fail",
            code="provider_preflight_exception",
            message=str(exc),
        )
    details = report.model_dump(mode="json", exclude_none=True)
    status = "pass" if report.status == "ok" else "fail"
    return _check_result(
        "provider-preflight",
        status,
        code=(None if status == "pass" else "provider_preflight_failed"),
        details=details,
    )


def run_provider_quality_controlled_check(context: ProbeContext) -> dict[str, Any]:
    """Run bounded evidence-bound provider/model quality comparison."""
    api_key = context.runtime_env.get("POLISYOS_LLM_GATEWAY_API_KEY")
    task = controlled_grounding_task()
    if not context.allow_live_provider or not api_key:
        return _check_result(
            "provider-quality-controlled",
            "skipped",
            code="live_provider_not_enabled",
            message=(
                "Controlled provider-quality comparison requires "
                "--allow-live-provider and an API key."
            ),
            details={
                "controlled_task": task.model_dump(mode="json"),
                "candidate_models": [context.model, KIMI_MODEL],
            },
        )
    try:
        observations = asyncio.run(_run_controlled_grounding_live_samples(context))
        candidates = _controlled_candidate_models(context.model)
        default_choice = candidates[0]
        comparison = build_controlled_provider_model_comparison(
            observations,
            candidate_models=candidates,
            default_model_choice=default_choice,
            generated_at=datetime.now(UTC),
            hidden_answer_tokens={api_key},
        )
    except Exception as exc:
        return _check_result(
            "provider-quality-controlled",
            "fail",
            code="provider_quality_controlled_exception",
            message=str(exc),
            details={"controlled_task": task.model_dump(mode="json")},
        )

    comparison_payload = comparison.model_dump(mode="json", exclude_none=True)
    comparison_path = context.output.parent / "local_prod_debug_provider_quality_controlled.json"
    _write_json(comparison_path, comparison_payload)
    context.artifacts["provider_quality_controlled_comparison"] = str(comparison_path)
    context.artifacts["provider_quality_controlled_selected_model"] = context.model
    action = str(comparison.default_model_gate.get("action") or "")
    status = (
        "pass"
        if comparison.summary.get("status") == "pass" and action == "approve"
        else "fail"
    )
    return _check_result(
        "provider-quality-controlled",
        status,
        code=None if status == "pass" else "provider_quality_controlled_gate_failed",
        details={
            "comparison_path": str(comparison_path),
            "selected_model": context.model,
            "comparison": comparison_payload,
            "next_live_lane": {
                "lane_id": LIVE_RESEARCH_LANE_ID,
                "selected_model": context.model,
                "requires_allow_live_provider": True,
            },
        },
    )


async def _run_controlled_grounding_live_samples(
    context: ProbeContext,
) -> list[Any]:
    task = controlled_grounding_task()
    api_key = context.runtime_env.get("POLISYOS_LLM_GATEWAY_API_KEY") or ""
    base_url = context.runtime_env.get("POLISYOS_LLM_GATEWAY_BASE_URL") or (
        "https://proxy.gonka.gg/v1"
    )
    provider = context.runtime_env.get("POLISYOS_LLM_GATEWAY_PROVIDER") or "gonka_proxy"
    observations: list[Any] = []
    for candidate in _controlled_candidate_models(context.model):
        client = GatewayLLMClient(
            base_url=base_url,
            api_key=api_key,
            model=candidate.model_id,
            provider_hint=provider,
            max_retries=0,
            timeout_s=float(context.provider_timeout_s),
        )
        try:
            for sample_index in range(3):
                request_fingerprint = _controlled_request_fingerprint(
                    model_id=candidate.model_id,
                    sample_index=sample_index,
                    task_refs=task.required_evidence_refs,
                )
                started = time.perf_counter()
                try:
                    response = await client.generate(
                        system="Return compact JSON only. Do not include prose.",
                        user=_controlled_grounding_prompt(sample_index=sample_index),
                        response_format={"type": "json_object"},
                        max_tokens=180,
                        temperature=0.0,
                    )
                    latency_ms = (time.perf_counter() - started) * 1000
                    parsed = _parse_json_object(getattr(response, "content", ""))
                    observed_refs = {
                        key: str(parsed.get(key) or "")
                        for key in task.required_evidence_refs
                    }
                    raw_response = getattr(response, "raw", None)
                    degraded_events = (
                        raw_response.get("_gateway_degraded_events")
                        if isinstance(raw_response, Mapping)
                        else None
                    )
                    observations.append(
                        build_controlled_grounding_observation(
                            provider=provider,
                            model_id=candidate.model_id,
                            model_fingerprint=candidate.model_fingerprint,
                            sample_index=sample_index,
                            task=task,
                            grounding_refs=observed_refs,
                            schema_valid=bool(parsed),
                            refusal_detected=_looks_like_refusal(
                                getattr(response, "content", "")
                            ),
                            degradation_behavior=(
                                "fallback_plain_json"
                                if isinstance(degraded_events, list) and degraded_events
                                else None
                            ),
                            request_fingerprint=request_fingerprint,
                            latency_ms=latency_ms,
                            cost_usd=getattr(getattr(response, "usage", None), "cost_usd", None),
                            raw_evidence={
                                "request_id": getattr(response, "request_id", None),
                                "request_fingerprint": request_fingerprint,
                                "response_format_mode": (
                                    "fallback_plain_json"
                                    if isinstance(degraded_events, list) and degraded_events
                                    else "json_object"
                                ),
                            },
                        )
                    )
                except Exception as exc:
                    observations.append(
                        build_controlled_grounding_observation(
                            provider=provider,
                            model_id=candidate.model_id,
                            model_fingerprint=candidate.model_fingerprint,
                            sample_index=sample_index,
                            task=task,
                            grounding_refs={},
                            schema_valid=False,
                            refusal_detected=False,
                            degradation_behavior="provider_exception",
                            request_fingerprint=request_fingerprint,
                            latency_ms=(time.perf_counter() - started) * 1000,
                            cost_usd=None,
                            raw_evidence={
                                "request_fingerprint": request_fingerprint,
                                "provider_error_code": exc.__class__.__name__,
                            },
                        )
                    )
        finally:
            await client.aclose()
    return observations


def run_live_research_lane_check(context: ProbeContext) -> dict[str, Any]:
    """Run the one approved live research lane through the matrix wrapper."""
    if (
        not context.allow_live_provider
        or not context.runtime_env.get("POLISYOS_LLM_GATEWAY_API_KEY")
    ):
        return _check_result(
            "live-research-lane",
            "skipped",
            code="live_provider_not_enabled",
            message="Live lane requires --allow-live-provider and an API key.",
        )
    matrix_json = (
        context.output.parent / "local_prod_debug_live_research_lane.json"
    ).resolve()
    command = [
        sys.executable,
        "tools/ops_runners/runtime/run_canary_matrix.py",
        "--lane-id",
        LIVE_RESEARCH_LANE_ID,
        "--allow-live-provider",
        "--output-root",
        ".polisyos/canary_evidence/local-prod-debug/live-research",
        "--run-root",
        ".polisyos/canary_matrix_runs/local-prod-debug/live-research",
        "--json-output",
        str(matrix_json),
        "--timeout-s",
        str(max(1, int(context.live_timeout_s))),
    ]
    env = dict(context.runtime_env)
    if context.postgres_dsn:
        env["POLISYOS_CONTROL_POSTGRES_DSN"] = context.postgres_dsn
    completed = _run_subprocess(
        command,
        cwd=context.repo_root,
        env=env,
        timeout_s=context.live_timeout_s + 30,
    )
    context.live_matrix_json = matrix_json
    context.artifacts["live_matrix_json"] = str(matrix_json)
    matrix = _load_json(matrix_json) or {}
    lanes = matrix.get("lanes") if isinstance(matrix, dict) else None
    lane = lanes[0] if isinstance(lanes, list) and lanes else {}
    failure_envelope = lane.get("failure_envelope") if isinstance(lane, dict) else None
    bundle_path = lane.get("bundle_path") if isinstance(lane, dict) else None
    bundle_dir = _resolve_optional_path(context.repo_root, bundle_path)
    timeout_classification = classify_control_plane_timeout_signal(
        failure_envelope if isinstance(failure_envelope, Mapping) else None,
        bundle_path=str(bundle_dir) if bundle_dir is not None else bundle_path,
        replay_manifest_present=(
            (bundle_dir / "quality_evidence" / "replay_manifest.json").is_file()
            if bundle_dir is not None
            else False
        ),
        closeout_artifact_present=(
            (bundle_dir / "quality_evidence" / "can_i_closeout_compatibility.json").is_file()
            if bundle_dir is not None
            else False
        ),
    )
    if completed["returncode"] == 0:
        status = "pass"
    elif (
        timeout_classification.get("applies") is True
        and timeout_classification.get("status") == "warn"
    ):
        status = "warn"
    else:
        status = "fail"
    return _check_result(
        "live-research-lane",
        status,
        code=(
            None
            if status == "pass"
            else (
                "control_plane_timeout_resilience_signal"
                if status == "warn"
                else "live_research_lane_failed"
            )
        ),
        details={
            "command": command,
            "returncode": completed["returncode"],
            "stdout_tail": completed["stdout_tail"],
            "stderr_tail": completed["stderr_tail"],
            "matrix_json": str(matrix_json),
            "bundle_path": bundle_path,
            "failure_envelope": failure_envelope,
            "control_plane_timeout_classification": timeout_classification,
        },
    )


def classify_control_plane_timeout_signal(
    failure_envelope: Mapping[str, Any] | None,
    *,
    bundle_path: str | None,
    replay_manifest_present: bool,
    closeout_artifact_present: bool,
) -> dict[str, Any]:
    """Classify control-plane timeouts as resilience unless durability breaks."""
    if not isinstance(failure_envelope, Mapping):
        return {"applies": False, "status": "pass", "root_cause_class": None}
    code = str(failure_envelope.get("code") or "").casefold()
    layer = str(failure_envelope.get("layer") or "").casefold()
    phase = str(failure_envelope.get("phase") or "").casefold()
    message = str(failure_envelope.get("message") or "").casefold()
    haystack = " ".join((code, layer, phase, message))
    if "timeout" not in haystack or "control" not in haystack:
        return {"applies": False, "status": "pass", "root_cause_class": None}

    blocking_axes: list[str] = []
    if not bundle_path:
        blocking_axes.append("bundle_production")
    if not replay_manifest_present:
        blocking_axes.append("replay_manifest")
    if not closeout_artifact_present:
        blocking_axes.append("closeout_artifact")
    if blocking_axes:
        return {
            "applies": True,
            "status": "fail",
            "root_cause_class": "artifact_durability_break",
            "failure_reason": (
                "Control-plane timeout broke bundle, replay, or closeout artifact "
                "durability."
            ),
            "blocking_artifact_axes": blocking_axes,
            "resilience_signal": True,
        }
    return {
        "applies": True,
        "status": "warn",
        "root_cause_class": "secondary_resilience_signal",
        "failure_reason": (
            "Control-plane timeout was observed, but bundle/replay/closeout "
            "durability remained intact."
        ),
        "blocking_artifact_axes": [],
        "resilience_signal": True,
    }


def run_evidence_inspection_check(context: ProbeContext) -> dict[str, Any]:
    """Inspect failed live evidence and preserve the matrix failure envelope."""
    matrix_json = context.live_matrix_json or (
        context.output.parent / "local_prod_debug_live_research_lane.json"
    )
    if not matrix_json.exists():
        return _check_result(
            "evidence-inspection",
            "skipped",
            code="live_matrix_json_missing",
            message="No local live matrix JSON exists to inspect.",
        )
    matrix = _load_json(matrix_json) or {}
    lanes = matrix.get("lanes") if isinstance(matrix, dict) else []
    lane_summaries = [
        {
            "lane_id": lane.get("lane_id"),
            "status": lane.get("status"),
            "scorecard_status": lane.get("scorecard_status"),
            "bundle_path": lane.get("bundle_path"),
            "failure_envelope": lane.get("failure_envelope"),
        }
        for lane in lanes
        if isinstance(lane, dict)
    ]
    failed_live_lane = any(lane.get("status") == "failed" for lane in lane_summaries)
    bundle_paths = [lane["bundle_path"] for lane in lane_summaries if lane.get("bundle_path")]
    details: dict[str, Any] = {
        "matrix_json": str(matrix_json),
        "matrix": {"summary": matrix.get("summary"), "lanes": lane_summaries},
        "inspection": None,
        "readiness": None,
        "readiness_mismatch": {"detected": False},
    }
    status = "warn" if failed_live_lane else "pass"
    if bundle_paths:
        inspection_json = context.output.parent / "local_prod_debug_evidence_inspection.json"
        readiness_json = context.output.parent / "local_prod_debug_readiness.json"
        inspection_cmd = [
            sys.executable,
            "tools/quality/validation/inspect_evidence_bundles.py",
            "--repo-root",
            str(context.repo_root),
            "--matrix-run-json",
            str(matrix_json),
            "--json-output",
            str(inspection_json),
        ]
        readiness_cmd = [
            sys.executable,
            "tools/ci/check_policyos_production_quality_best_in_class.py",
            "--repo-root",
            str(context.repo_root),
            "--matrix-run-json",
            str(matrix_json),
            "--output",
            str(readiness_json),
            "--output-format",
            "json",
        ]
        details["inspection_command"] = _run_subprocess(
            inspection_cmd,
            cwd=context.repo_root,
            env=context.runtime_env,
            timeout_s=300,
        )
        details["readiness_command"] = _run_subprocess(
            readiness_cmd,
            cwd=context.repo_root,
            env=context.runtime_env,
            timeout_s=300,
        )
        details["inspection"] = _load_json(inspection_json)
        details["readiness"] = _load_json(readiness_json)
        readiness_status = (
            details["readiness"].get("status")
            if isinstance(details["readiness"], dict)
            else None
        )
        mismatch = bool(failed_live_lane and readiness_status == "pass")
        details["readiness_mismatch"] = {
            "detected": mismatch,
            "reason": (
                "readiness_passed_failed_live_lane"
                if mismatch
                else "no_failed_live_readiness_pass_mismatch"
            ),
        }
        if mismatch and context.require_passing:
            status = "fail"
    return _check_result("evidence-inspection", status, details=details)


def run_postgres_resource_check(context: ProbeContext) -> dict[str, Any]:
    """Run bounded resource-profile writes against the control-plane store."""
    store = _make_store(context)
    metrics: dict[str, list[float]] = {
        "create_ms": [],
        "lease_ms": [],
        "progress_ms": [],
        "heartbeat_ms": [],
        "diagnostic_event_ms": [],
        "complete_or_fail_ms": [],
    }
    try:
        jobs = max(1, int(context.pg_stress_jobs))
        events_per_job = max(0, int(context.pg_stress_events_per_job))
        for index in range(jobs):
            job_id = f"{context.probe_id}_resource_job_{index}"
            run_id = f"{context.probe_id}_resource_run_{index}"
            worker_id = f"{context.probe_id}_resource_worker_{index % 2}"
            _timed(
                metrics["heartbeat_ms"],
                lambda worker_id=worker_id: store.heartbeat_worker(
                    worker_id=worker_id,
                    state="idle",
                    lease_seconds=30,
                    backend=context.store_backend,
                    metadata={"probe": context.probe_id},
                ),
            )
            _timed(
                metrics["create_ms"],
                lambda job_id=job_id, run_id=run_id: store.create_job(
                    job_id=job_id,
                    kind="workflow_run",
                    run_id=run_id,
                    pipeline_id=None,
                    requested_execution_profile="research",
                    effective_execution_profile="research",
                    policy_flags={},
                    capability_manifest_ref=None,
                    payload_ref=None,
                    submitted_by="local-prod-debug",
                ),
            )
            _timed(
                metrics["lease_ms"],
                lambda worker_id=worker_id: store.lease_next_job(worker_id=worker_id),
            )
            for event_index in range(events_per_job):
                _timed(
                    metrics["progress_ms"],
                    lambda job_id=job_id, event_index=event_index: store.update_progress_state(
                        job_id=job_id,
                        state="running",
                        progress={"phase": "resource_profile", "event_index": event_index},
                    ),
                )
                _timed(
                    metrics["diagnostic_event_ms"],
                    _diagnostic_event_appender(
                        store=store,
                        context=context,
                        job_id=job_id,
                        run_id=run_id,
                        index=event_index,
                    ),
                )
            if index % 5 == 4:
                _timed(
                    metrics["complete_or_fail_ms"],
                    lambda job_id=job_id: store.fail_job(
                        job_id=job_id,
                        error_message="resource profile fail",
                    ),
                )
            else:
                _timed(
                    metrics["complete_or_fail_ms"],
                    lambda job_id=job_id: store.complete_job(job_id=job_id),
                )
        summary = {name: _latency_summary(values) for name, values in metrics.items()}
        warnings = []
        if summary["lease_ms"]["p95"] > 250:
            warnings.append("lease_p95_over_250ms")
        if summary["progress_ms"]["p95"] > 250:
            warnings.append("progress_p95_over_250ms")
        if summary["heartbeat_ms"]["p95"] > 1000:
            warnings.append("heartbeat_p95_over_1000ms")
        status = "warn" if warnings else "pass"
        return _check_result(
            "postgres-resource",
            status,
            details={
                "jobs": jobs,
                "events_per_job": events_per_job,
                "latency_ms": summary,
                "warnings": warnings,
            },
        )
    finally:
        if not context.keep_probe_state:
            _cleanup_probe_rows(store, context.probe_id)
        store.close()


def run_production_data_static_check(context: ProbeContext) -> dict[str, Any]:
    """Run cheap static checks over production_data without Scientist workflow."""
    root = context.production_data_root or context.repo_root / "production_data"
    manifest_path = root / "manifest.json"
    if not manifest_path.exists():
        return _check_result(
            "production-data-static",
            "fail",
            code="production_data_manifest_missing",
            message=f"Production data manifest is missing: {manifest_path}",
            details={
                "root": str(root),
                "issues": [
                    {
                        "code": "production_data_manifest_missing",
                        "path": str(manifest_path),
                    }
                ],
            },
        )
    manifest = load_production_data_manifest(root)
    context_payload = production_data_evidence_context(
        {"production_data_root": str(root)},
        allow_default=False,
    )
    issues: list[dict[str, Any]] = []
    bundles = manifest.get("bundles") if isinstance(manifest, Mapping) else None
    if not isinstance(bundles, Mapping) or not bundles:
        issues.append({"code": "production_data_bundles_missing"})
    else:
        for role, bundle in sorted(bundles.items()):
            if not isinstance(bundle, Mapping):
                issues.append({"code": "production_data_bundle_malformed", "role": role})
                continue
            if not bundle.get("path"):
                issues.append({"code": "production_data_bundle_path_missing", "role": role})
            dictionary = bundle.get("data_dictionary_path")
            if isinstance(dictionary, str) and not (root / dictionary).exists():
                issues.append(
                    {
                        "code": "production_data_dictionary_missing",
                        "role": role,
                        "path": dictionary,
                    }
                )
    quality = None
    if context_payload is not None:
        try:
            quality = production_data_quality_report(
                evidence_context=context_payload,
                materialization_refs={
                    "data_snapshot_ref": _fake_sha("1"),
                    "input_bindings_ref": _fake_sha("2"),
                    "registry_bundle_ref": _fake_sha("3"),
                    "quality_report_ref": _fake_sha("4"),
                    "fabric_retrieval_trace_ref": _fake_sha("5"),
                    "production_data_quality_report_ref": _fake_sha("6"),
                },
                data_needs=[
                    {
                        "metric": "msme_survival_rate",
                        "geography": "UA",
                        "unit": "rate",
                        "population": "wartime_msme",
                    }
                ],
                claims=[
                    {
                        "claim_id": "local_prod_debug_claim",
                        "major": True,
                        "data_refs": ["msme_survival_rate"],
                    }
                ],
            )
        except Exception as exc:
            issues.append(
                {"code": "production_data_quality_report_failed", "message": str(exc)}
            )
    if isinstance(quality, Mapping) and quality.get("status") == "fail":
        for issue in quality.get("issues") or []:
            if isinstance(issue, Mapping):
                issues.append(dict(issue))
    scenario_binding_report = None
    try:
        quality_scenario = load_quality_scenario_contract(DEFAULT_QUALITY_SCENARIO_ID)
        scenario_evidence_contract = quality_scenario.get("scenario_evidence_contract")
        if isinstance(scenario_evidence_contract, Mapping):
            scenario_binding_report = production_data_contract_binding_report(
                {"production_data_root": str(root)},
                scenario_evidence_contract=scenario_evidence_contract,
                allow_default=False,
            )
    except Exception as exc:
        issues.append(
            {"code": "production_data_contract_index_failed", "message": str(exc)}
        )
    scenario_binding_findings = (
        scenario_binding_report.get("scenario_binding_findings")
        if isinstance(scenario_binding_report, Mapping)
        else []
    )
    construct_capability_report = _construct_capability_report(
        context,
        scenario_binding_report if isinstance(scenario_binding_report, Mapping) else {},
    )
    construct_capability_blockers = _construct_capability_blockers(
        {
            **(scenario_binding_report if isinstance(scenario_binding_report, Mapping) else {}),
            "construct_capability_report": construct_capability_report,
        }
    )
    untyped_construct_capability_blockers = [
        blocker
        for blocker in construct_capability_blockers
        if not str(blocker.get("status") or "").startswith(("blocked_", "selected_"))
    ]
    construct_issue = bool(untyped_construct_capability_blockers)
    construct_evidence_issue = (
        construct_capability_report.get("status") == "blocked"
        and not construct_capability_blockers
    )
    status = (
        "fail"
        if (construct_evidence_issue or construct_issue)
        else ("pass" if not issues else "warn")
    )
    if construct_evidence_issue:
        code = str(
            next(
                iter(construct_capability_report.get("issue_codes") or ()),
                "production_data_construct_capability_evidence_missing",
            )
        )
    elif construct_issue:
        code = "production_data_construct_capability_blockers"
    else:
        code = None
    return _check_result(
        "production-data-static",
        status,
        code=code,
        details={
            "root": str(root),
            "manifest_path": str(manifest_path),
            "bundle_roles": sorted(str(role) for role in (bundles or {}))
            if isinstance(bundles, Mapping)
            else [],
            "quality_status": quality.get("status") if isinstance(quality, Mapping) else None,
            "scenario_binding_status": (
                scenario_binding_report.get("summary")
                if isinstance(scenario_binding_report, Mapping)
                else None
            ),
            "construct_capability_report": construct_capability_report,
            "scenario_binding_findings": scenario_binding_findings or [],
            "compatibility_projection_findings": scenario_binding_findings or [],
            "construct_capability_blockers": construct_capability_blockers,
            "untyped_construct_capability_blockers": untyped_construct_capability_blockers,
            "missing_scenario_source_families": (
                []
                if construct_capability_report.get("resolver_executed")
                or construct_capability_blockers
                else list(
                    scenario_binding_report.get("missing_scenario_source_families") or []
                )
                if isinstance(scenario_binding_report, Mapping)
                else []
            ),
            "issues": issues,
        },
    )


def _construct_capability_blockers(report: Mapping[str, Any]) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    blocker_statuses = {
        "selected_proxy_with_limitation",
        "selected_with_conflict_marker",
        "selected_context_only",
        "selected_simulation_only",
    }
    for spec in report.get("compiled_data_requirement_specs") or []:
        if not isinstance(spec, Mapping):
            continue
        metadata = spec.get("metadata")
        if not isinstance(metadata, Mapping):
            continue
        binding = metadata.get("capability_binding")
        if not isinstance(binding, Mapping):
            continue
        status = str(binding.get("status") or "")
        if not (status.startswith("blocked_") or status in blocker_statuses):
            continue
        blockers.append(
            {
                "construct_ref": binding.get("construct_ref"),
                "capability_ref": binding.get("selected_capability_ref"),
                "requirement_id": binding.get("requirement_id"),
                "status": status,
                "code": status,
                "blocked_reasons": list(binding.get("blocked_reasons") or ()),
                "limitations": list(binding.get("limitations") or ()),
                "acquisition_strategies": list(binding.get("acquisition_strategies") or ()),
                "rejected_alternatives": list(binding.get("rejected_alternatives") or ()),
            }
        )
    construct_report = report.get("construct_capability_report")
    if isinstance(construct_report, Mapping):
        for binding in construct_report.get("capability_bindings") or []:
            if not isinstance(binding, Mapping):
                continue
            status = str(binding.get("status") or "")
            if not (status.startswith("blocked_") or status in blocker_statuses):
                continue
            blockers.append(
                {
                    "construct_ref": binding.get("construct_ref"),
                    "capability_ref": binding.get("selected_capability_ref"),
                    "requirement_id": binding.get("requirement_id"),
                    "status": status,
                    "code": status,
                    "blocked_reasons": list(binding.get("blocked_reasons") or ()),
                    "limitations": list(binding.get("limitations") or ()),
                    "acquisition_strategies": list(
                        binding.get("acquisition_strategies") or ()
                    ),
                    "rejected_alternatives": list(
                        binding.get("rejected_alternatives") or ()
                    ),
                }
            )
    return blockers


def _construct_capability_report(
    context: ProbeContext,
    scenario_binding_report: Mapping[str, Any],
) -> dict[str, Any]:
    embedded_bindings = _embedded_capability_bindings(scenario_binding_report)
    if embedded_bindings:
        return {
            "schema_version": "policyos.local_prod_debug.construct_capability_report.v1",
            "status": "pass",
            "source": "compiled_data_requirement_spec_metadata",
            "resolver_executed": False,
            "capability_index_loaded": None,
            "capability_bindings": embedded_bindings,
            "binding_count": len(embedded_bindings),
            "issue_codes": [],
            "issues": [],
        }
    specs = [
        spec
        for spec in scenario_binding_report.get("compiled_data_requirement_specs") or []
        if isinstance(spec, Mapping)
    ]
    capability_index = context.repo_root / DEFAULT_CAPABILITY_INDEX
    base = {
        "schema_version": "policyos.local_prod_debug.construct_capability_report.v1",
        "source": "requirement_to_capability_resolver",
        "capability_index_path": f"repo://{DEFAULT_CAPABILITY_INDEX.as_posix()}",
        "resolver_executed": False,
        "capability_index_loaded": False,
        "capability_bindings": [],
        "binding_count": 0,
        "issues": [],
    }
    if not specs:
        return {
            **base,
            "status": "blocked",
            "issue_codes": ["production_data_construct_capability_evidence_missing"],
        }
    if not capability_index.exists():
        return {
            **base,
            "status": "blocked",
            "issue_codes": ["production_data_construct_capability_evidence_missing"],
            "issues": [
                {
                    "code": "production_data_construct_capability_evidence_missing",
                    "message": "W12.A production-data-static could not load capability index evidence.",
                    "capability_index_path": f"repo://{DEFAULT_CAPABILITY_INDEX.as_posix()}",
                }
            ],
        }
    try:
        resolver = RequirementToCapabilityResolver.from_duckdb(capability_index)
    except Exception as exc:  # pragma: no cover - environment-dependent.
        return {
            **base,
            "status": "blocked",
            "issue_codes": ["production_data_construct_capability_resolver_failed"],
            "issues": [
                {
                    "code": "production_data_construct_capability_resolver_failed",
                    "message": str(exc),
                }
            ],
        }
    bindings: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    for spec in specs:
        query = _capability_query_for_static_spec(spec)
        if query is None:
            issues.append(
                {
                    "code": "production_data_construct_capability_query_missing",
                    "requirement_id": spec.get("requirement_id"),
                }
            )
            continue
        try:
            result = resolver.resolve(query)
        except Exception as exc:  # pragma: no cover - defensive diagnostic path.
            issues.append(
                {
                    "code": "production_data_construct_capability_resolver_failed",
                    "requirement_id": query.requirement_id,
                    "message": str(exc),
                }
            )
            continue
        row = result.model_dump(mode="json", exclude_none=True)
        row.setdefault("capability_index_ref", resolver.capability_index_ref)
        row.setdefault("construct_registry_ref", "construct-registry:v1")
        bindings.append(row)
    issue_codes = sorted({str(issue["code"]) for issue in issues if issue.get("code")})
    return {
        **base,
        "status": "pass" if bindings and not issues else "blocked",
        "resolver_executed": bool(bindings or issues),
        "capability_index_loaded": True,
        "capability_index_ref": resolver.capability_index_ref,
        "capability_bindings": bindings,
        "binding_count": len(bindings),
        "issue_codes": issue_codes
        or ([] if bindings else ["production_data_construct_capability_evidence_missing"]),
        "issues": issues,
    }


def _embedded_capability_bindings(report: Mapping[str, Any]) -> list[dict[str, Any]]:
    bindings: list[dict[str, Any]] = []
    for spec in report.get("compiled_data_requirement_specs") or []:
        if not isinstance(spec, Mapping):
            continue
        metadata = spec.get("metadata")
        if not isinstance(metadata, Mapping):
            continue
        binding = metadata.get("capability_binding")
        if isinstance(binding, Mapping):
            bindings.append(dict(binding))
    return bindings


def _capability_query_for_static_spec(
    spec: Mapping[str, Any],
) -> RequirementToCapabilityQuery | None:
    requirement_id = _optional_text(spec.get("requirement_id"))
    construct = _construct_for_static_spec(spec)
    if not requirement_id or not construct:
        return None
    scope = spec.get("scope") if isinstance(spec.get("scope"), Mapping) else {}
    family = _first_text(spec.get("required_data_families"))
    geography = (
        _optional_text(scope.get("jurisdiction"))
        or _optional_text(scope.get("geography"))
        or "scenario_geography"
    )
    return RequirementToCapabilityQuery(
        requirement_id=requirement_id,
        construct=construct,
        entity_scope=_entity_scope_for_construct(construct),
        population_filter={
            "type": _optional_text(scope.get("population")) or "scenario_population"
        },
        geography=geography,
        time_window={"start": _optional_text(scope.get("time")), "end": None},
        authority_level="production",
        claim_use=_optional_text(spec.get("claim_use")) or "claim_evidence_closeout",
        required_evidence_modes=(
            "observed",
            "derived",
            "proxy_observational",
            "scholarly_causal_support",
            "legal_threshold",
        ),
        forbidden_evidence_modes=("simulation_only", "candidate_unverified"),
        source_family_alias=family,
    )


def _construct_for_static_spec(spec: Mapping[str, Any]) -> str | None:
    metadata = spec.get("metadata") if isinstance(spec.get("metadata"), Mapping) else {}
    binding = (
        metadata.get("capability_binding")
        if isinstance(metadata.get("capability_binding"), Mapping)
        else {}
    )
    for value in (
        binding.get("construct_ref"),
        metadata.get("construct_ref"),
        spec.get("construct_ref"),
        spec.get("target_construct_ref"),
    ):
        text = _optional_text(value)
        if text:
            return text.removeprefix("construct:")
    family = _first_text(spec.get("required_data_families"))
    return construct_for_legacy_family(family) if family else None


def _entity_scope_for_construct(construct: str) -> str:
    bare = construct.removeprefix("construct:")
    return {
        "firm_survival": "firm",
        "credit_program_enrollment": "firm_or_program",
        "regional_displacement_pressure": "region",
    }.get(bare, "entity")


def _first_text(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return _optional_text(value)
    if isinstance(value, Iterable):
        for item in value:
            if text := _optional_text(item):
                return text
    return None


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def run_docs_repro_check(context: ProbeContext) -> dict[str, Any]:
    """Check local-prod-debug docs and gitignore reproducibility."""
    runbook = context.repo_root / "docs/runbooks/local-production-debugging.md"
    runbook_text = runbook.read_text(encoding="utf-8") if runbook.exists() else ""
    ignored = subprocess.run(
        ["git", "check-ignore", "-q", ".env.prod-local"],  # noqa: S607
        cwd=context.repo_root,
        check=False,
    ).returncode == 0
    required = [
        "polisyos-control-pg",
        ".env.prod-local",
        "tools/quality/testing/local_prod_debug_probe.py",
        "--checks quick",
    ]
    missing = [item for item in required if item not in runbook_text]
    status = "pass" if ignored and not missing else "fail"
    return _check_result(
        "docs-repro",
        status,
        code=None if status == "pass" else "local_prod_debug_docs_repro_failed",
        details={
            "runbook": str(runbook),
            "env_prod_local_gitignored": ignored,
            "missing_runbook_terms": missing,
            "runbook_text": "\n".join(line for line in runbook_text.splitlines() if line.strip()),
        },
    )


def run_checks(context: ProbeContext, checks: Sequence[str]) -> list[dict[str, Any]]:
    """Run selected checks in order."""
    runners: dict[str, Callable[[ProbeContext], dict[str, Any]]] = {
        "postgres-lifecycle": run_postgres_lifecycle_check,
        "stale-recovery": run_stale_recovery_check,
        "production-dry-run": run_production_dry_run_check,
        "provider-preflight": run_provider_preflight_check,
        "provider-quality-controlled": run_provider_quality_controlled_check,
        "live-research-lane": run_live_research_lane_check,
        "evidence-inspection": run_evidence_inspection_check,
        "postgres-resource": run_postgres_resource_check,
        "production-data-static": run_production_data_static_check,
        "docs-repro": run_docs_repro_check,
    }
    results: list[dict[str, Any]] = []
    for check in checks:
        if check == "bootstrap":
            results.append(run_bootstrap_check(postgres_dsn=context.postgres_dsn))
            continue
        runner = runners[check]
        try:
            results.append(runner(context))
        except Exception as exc:
            results.append(
                _check_result(
                    check,
                    "fail",
                    code=f"{check.replace('-', '_')}_exception",
                    message=str(exc),
                )
            )
    return results


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entrypoint."""
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        checks = parse_checks(args.checks)
    except ValueError as exc:
        parser.error(str(exc))
    repo_root = Path(args.repo_root).expanduser().resolve()
    runtime_env = _runtime_env(repo_root)
    postgres_dsn = str(args.postgres_dsn or runtime_env.get("POLISYOS_CONTROL_POSTGRES_DSN") or "")
    if args.postgres_dsn:
        runtime_env["POLISYOS_CONTROL_POSTGRES_DSN"] = postgres_dsn
    output = _resolve_output(repo_root, Path(args.output))
    context = ProbeContext(
        repo_root=repo_root,
        output=output,
        postgres_dsn=postgres_dsn or None,
        allow_live_provider=bool(args.allow_live_provider),
        require_passing=bool(args.require_passing),
        model=str(args.model),
        provider_timeout_s=max(1, int(args.provider_timeout_s)),
        live_timeout_s=max(1, int(args.live_timeout_s)),
        pg_stress_jobs=max(1, int(args.pg_stress_jobs)),
        pg_stress_events_per_job=max(0, int(args.pg_stress_events_per_job)),
        keep_probe_state=bool(args.keep_probe_state),
        production_data_root=Path(
            runtime_env.get("POLISYOS_PRODUCTION_DATA_ROOT") or repo_root / "production_data"
        ),
        runtime_env=runtime_env,
    )
    missing_dsn_checks = [
        check
        for check in checks
        if (
            check in POSTGRES_REQUIRED_CHECKS
            and context.store_backend == "postgres"
            and not postgres_dsn
        )
    ]
    if missing_dsn_checks:
        missing_dsn_check_set = set(missing_dsn_checks)
        results = []
        for check in checks:
            if check in missing_dsn_check_set:
                results.append(_missing_dsn_result(check))
            else:
                results.extend(run_checks(context, (check,)))
        payload = _payload(
            context=context,
            checks=results,
            requested_checks=checks,
            invalid=True,
        )
        _write_json(output, payload)
        print(f"Local prod-debug probe: invalid ({', '.join(missing_dsn_checks)})")  # noqa: T201
        print(f"Report: {output}")  # noqa: T201
        return 3
    results = run_checks(context, checks)
    payload = _payload(context=context, checks=results, requested_checks=checks)
    _write_json(output, payload)
    print(  # noqa: T201
        "Local prod-debug probe: "
        f"{payload['summary']['status']} "
        f"({payload['summary']['passed']} passed, "
        f"{payload['summary']['warned']} warned, "
        f"{payload['summary']['failed']} failed, "
        f"{payload['summary']['skipped']} skipped)"
    )
    print(f"Report: {output}")  # noqa: T201
    if payload["summary"]["failed"]:
        return 2
    if args.require_passing and (payload["summary"]["warned"] or payload["summary"]["skipped"]):
        return 2
    return 0


def _make_store(context: ProbeContext) -> ControlPlaneStore:
    if context.store_backend == "postgres" and not context.postgres_dsn:
        raise RuntimeError("POLISYOS_CONTROL_POSTGRES_DSN is required for this check")
    sqlite_path = (
        context.sqlite_path
        if context.sqlite_path.is_absolute()
        else context.repo_root / context.sqlite_path
    )
    return ControlPlaneStore(
        backend=context.store_backend,
        sqlite_path=sqlite_path,
        postgres_dsn=context.postgres_dsn,
    )


def _cleanup_probe_rows(store: ControlPlaneStore, probe_id: str) -> None:
    like = f"{probe_id}%"
    event_like = f"{probe_id}:%"
    statements = [
        (
            "DELETE FROM control_dead_letter_jobs "
            "WHERE job_id LIKE ? OR run_id LIKE ? OR pipeline_id LIKE ?",
            (like, like, like),
        ),
        (
            "DELETE FROM control_diagnostic_events "
            "WHERE job_id LIKE ? OR run_id LIKE ? OR event_id LIKE ?",
            (like, like, like),
        ),
        ("DELETE FROM control_job_events WHERE job_id LIKE ?", (like,)),
        ("DELETE FROM control_job_progress WHERE job_id LIKE ?", (like,)),
        (
            "DELETE FROM control_outbox_events "
            "WHERE job_id LIKE ? OR run_id LIKE ? OR event_key LIKE ?",
            (like, like, event_like),
        ),
        (
            "DELETE FROM control_jobs WHERE job_id LIKE ? OR run_id LIKE ? OR pipeline_id LIKE ?",
            (like, like, like),
        ),
        ("DELETE FROM control_worker_leases WHERE worker_id LIKE ?", (like,)),
    ]
    for sql, params in statements:
        store._execute(sql, params)


def _diagnostic_event(
    *,
    context: ProbeContext,
    job_id: str,
    run_id: str,
    index: int,
) -> DiagnosticEvent:
    return DiagnosticEvent(
        event_id=f"{context.probe_id}_evt_{job_id}_{index}",
        event_source="polisyos.local_prod_debug_probe",
        event_type="polisyos.runtime.diagnostic.producer_execution.v1",
        event_time=datetime.now(UTC).replace(microsecond=0),
        event_subject=f"run/{run_id}/job/{job_id}/local-prod-debug/{index}",
        schema_name=DIAGNOSTIC_EVENT_SCHEMA_NAME,
        schema_version=DIAGNOSTIC_EVENT_SCHEMA_VERSION,
        trace_id=f"trace_{context.probe_id}",
        span_id=f"span_{index}",
        parent_span_id=None,
        run_id=run_id,
        job_id=job_id,
        tenant_id="tenant-local-prod-debug",
        cell_id="cell-local-prod-debug",
        producer_component="tools.quality.testing.local_prod_debug_probe",
        producer_version="2026.05.19",
        execution_profile="research",
        phase="postgres_resource",
        state_before="running",
        state_after="running",
        payload_ref=None,
        artifact_refs=(),
        input_refs=(),
        blocking_status=None,
        redaction_policy_ref="redaction-policy/runtime-diagnostics-v1",
        duplicate_of=None,
        dedupe_key=None,
        sampling_decision="always_record",
        sampling_rate=1.0,
    )


def _diagnostic_event_appender(
    *,
    store: ControlPlaneStore,
    context: ProbeContext,
    job_id: str,
    run_id: str,
    index: int,
) -> Callable[[], object]:
    def append_event() -> object:
        return store.append_diagnostic_event(
            event=_diagnostic_event(
                context=context,
                job_id=job_id,
                run_id=run_id,
                index=index,
            )
        )

    return append_event


class _AllowingOPAClient:
    async def check(self, _authz_input: object) -> AuthzResult:
        return AuthzResult(
            decision=AuthzDecision.ALLOW,
            policy="local-prod-debug-allow-all-health-dry-run",
            reasons=(),
            audit_entry={},
        )


def _production_env(context: ProbeContext) -> dict[str, str]:
    env = dict(context.runtime_env)
    env["POLISYOS_EXECUTION_PROFILE"] = "production"
    env["POLISYOS_CONTROL_WORKER_BACKEND"] = "external"
    env["POLISYOS_CONTROL_STATE_STORE_BACKEND"] = context.store_backend
    if context.postgres_dsn:
        env["POLISYOS_CONTROL_POSTGRES_DSN"] = context.postgres_dsn
    env.pop("POLISYOS_RESEARCH_ALLOW_LOCAL_CONTROL_PLANE", None)
    return env


@contextmanager
def _temporary_environ(env: Mapping[str, str]) -> Iterator[None]:
    previous = dict(os.environ)
    os.environ.clear()
    os.environ.update(env)
    try:
        yield
    finally:
        os.environ.clear()
        os.environ.update(previous)


def _runtime_env(repo_root: Path) -> dict[str, str]:
    env = dict(os.environ)
    _load_env_file(repo_root / ".env", env=env, override=False)
    env.setdefault("POLISYOS_LLM_GATEWAY_BASE_URL", "https://proxy.gonka.gg/v1")
    env.setdefault("POLISYOS_LLM_GATEWAY_PROVIDER", "gonka_proxy")
    return env


def _load_env_file(path: Path, *, env: dict[str, str], override: bool) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[7:].strip()
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        if not key:
            continue
        if override or key not in env:
            env[key] = value


def _run_subprocess(
    command: Sequence[str],
    *,
    cwd: Path,
    env: Mapping[str, str],
    timeout_s: int,
) -> dict[str, Any]:
    try:
        completed = subprocess.run(  # noqa: S603
            list(command),
            cwd=str(cwd),
            env=dict(env),
            check=False,
            capture_output=True,
            text=True,
            timeout=max(1, timeout_s),
        )
        return {
            "returncode": completed.returncode,
            "stdout_tail": _tail(completed.stdout),
            "stderr_tail": _tail(completed.stderr),
        }
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = exc.stderr if isinstance(exc.stderr, str) else ""
        return {
            "returncode": 124,
            "stdout_tail": _tail(stdout),
            "stderr_tail": _tail(
                (stderr + "\n" if stderr else "") + f"Timed out after {timeout_s}s"
            ),
        }


def _payload(
    *,
    context: ProbeContext,
    checks: Sequence[dict[str, Any]],
    requested_checks: Sequence[str],
    invalid: bool = False,
) -> dict[str, Any]:
    summary = _summary(checks, invalid=invalid)
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "probe_id": context.probe_id,
        "requested_checks": list(requested_checks),
        "summary": summary,
        "checks": list(checks),
        "artifacts": dict(context.artifacts),
        "sanitized_env": sanitized_env(context.runtime_env),
    }


def _summary(checks: Sequence[Mapping[str, Any]], *, invalid: bool) -> dict[str, Any]:
    counts = {"pass": 0, "warn": 0, "fail": 0, "skipped": 0, "invalid": 0}
    for check in checks:
        status = str(check.get("status") or "fail")
        counts[status if status in counts else "fail"] += 1
    if invalid:
        status = "invalid"
    elif counts["fail"]:
        status = "fail"
    elif counts["warn"]:
        status = "warn"
    elif counts["skipped"]:
        status = "skipped"
    return {
        "status": status,
        "total": len(checks),
        "passed": counts["pass"],
        "warned": counts["warn"],
        "failed": counts["fail"],
        "skipped": counts["skipped"],
        "invalid": counts["invalid"],
    }


def _check_result(
    name: str,
    status: str,
    *,
    code: str | None = None,
    message: str | None = None,
    details: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "name": name,
        "status": status,
        "code": code,
        "message": message,
        "details": dict(details or {}),
    }
    return payload


def _missing_dsn_result(check: str) -> dict[str, Any]:
    return _check_result(
        check,
        "fail",
        code="postgres_dsn_missing",
        message="POLISYOS_CONTROL_POSTGRES_DSN is required for this check.",
    )


def _worst_status(statuses: Iterable[str]) -> str:
    observed = list(statuses)
    if not observed:
        return "pass"
    return max(observed, key=lambda item: STATUS_ORDER.get(str(item), 3))


def _timed(bucket: list[float], fn: Callable[[], object]) -> object:
    started = time.perf_counter()
    try:
        return fn()
    finally:
        bucket.append((time.perf_counter() - started) * 1000.0)


def _latency_summary(values: Sequence[float]) -> dict[str, float]:
    if not values:
        return {"count": 0, "p50": 0.0, "p95": 0.0, "max": 0.0}
    ordered = sorted(values)
    return {
        "count": len(ordered),
        "p50": round(_percentile(ordered, 50), 3),
        "p95": round(_percentile(ordered, 95), 3),
        "max": round(max(ordered), 3),
    }


def _percentile(ordered: Sequence[float], percentile: float) -> float:
    if not ordered:
        return 0.0
    index = max(0, min(len(ordered) - 1, math.ceil((percentile / 100.0) * len(ordered)) - 1))
    return float(ordered[index])


def _controlled_candidate_models(default_model: str) -> list[DefaultProductionModelChoice]:
    provider = "gonka_proxy"
    candidates = [
        DefaultProductionModelChoice(
            provider=provider,
            model_id=default_model,
            model_fingerprint=default_model,
            usage="policy_drafting",
        )
    ]
    if default_model != KIMI_MODEL:
        candidates.append(
            DefaultProductionModelChoice(
                provider=provider,
                model_id=KIMI_MODEL,
                model_fingerprint=KIMI_MODEL,
                usage="controlled_grounding_candidate",
            )
        )
    return candidates


def _controlled_grounding_prompt(*, sample_index: int) -> str:
    task = controlled_grounding_task()
    refs = task.required_evidence_refs
    return (
        "Controlled provider quality sample "
        f"{sample_index}. Return exactly a JSON object with these fields and values: "
        f"data_ref={refs['data_ref']}, norm_ref={refs['norm_ref']}, "
        f"method_ref={refs['method_ref']}, claim_ref={refs['claim_ref']}, "
        "decision=supported. Do not add legal or policy prose."
    )


def _controlled_request_fingerprint(
    *,
    model_id: str,
    sample_index: int,
    task_refs: Mapping[str, str],
) -> str:
    import hashlib

    payload = json.dumps(
        {
            "model_id": model_id,
            "sample_index": sample_index,
            "task_refs": dict(sorted(task_refs.items())),
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _parse_json_object(value: object) -> dict[str, Any]:
    if not isinstance(value, str) or not value.strip():
        return {}
    try:
        payload = json.loads(value)
    except json.JSONDecodeError:
        start = value.find("{")
        end = value.rfind("}")
        if start < 0 or end <= start:
            return {}
        try:
            payload = json.loads(value[start : end + 1])
        except json.JSONDecodeError:
            return {}
    return payload if isinstance(payload, dict) else {}


def _looks_like_refusal(value: object) -> bool:
    text = str(value or "").casefold()
    return any(
        marker in text
        for marker in (
            "i can't",
            "i cannot",
            "sorry",
            "refuse",
            "unable to",
        )
    )


def _redact_dsn(value: str | None) -> str | None:
    if not value:
        return None
    try:
        parsed = urlsplit(value)
    except ValueError:
        return "<redacted-dsn>"
    username = quote(parsed.username or "", safe="")
    host = parsed.hostname or ""
    port = f":{parsed.port}" if parsed.port is not None else ""
    auth = f"{username}:***@" if username else "***@"
    netloc = f"{auth}{host}{port}"
    return urlunsplit((parsed.scheme, netloc, parsed.path, "", ""))


def _secret_fingerprint(value: str | None) -> str | None:
    if not value:
        return None
    import hashlib

    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def _fake_sha(char: str) -> str:
    return "sha256:" + char * 64


def _new_probe_id() -> str:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"local_probe_{timestamp}_{os.getpid()}"


def _resolve_output(repo_root: Path, output: Path) -> Path:
    return output if output.is_absolute() else repo_root / output


def _resolve_optional_path(repo_root: Path, value: object) -> Path | None:
    if not isinstance(value, str) or not value.strip():
        return None
    path = Path(value)
    return path if path.is_absolute() else repo_root / path


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _load_json(path: Path) -> object | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _tail(value: str, *, limit: int = 4000) -> str:
    return value[-limit:] if len(value) > limit else value


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
