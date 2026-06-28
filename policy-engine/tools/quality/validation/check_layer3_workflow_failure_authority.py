#!/usr/bin/env python3
"""Validate failed-workflow authority-surface proof artifacts."""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
import sys
import tempfile
import tomllib
import uuid
from collections.abc import Iterator
from contextlib import ExitStack
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import patch

from pydantic import BaseModel, ConfigDict, Field

FAMILY_ID = "policy-design-case-layer3-workflow-failure-authority"
PROOF_PATH = "architecture/policy_design_case/layer3_gy_workflow_failure_authority_proofs.json"
OUTPUTS = [PROOF_PATH]
FIXTURE_TENANT_ID = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
FIXTURE_CELL_ID = "cell-a"
FIXED_TIME = datetime(2026, 6, 16, 14, 15, 16, tzinfo=UTC)
SURFACE_NAMES = (
    "run",
    "artifact",
    "lineage",
    "export",
    "dashboard",
    "public_packet",
)


def declared_outputs() -> list[str]:
    """Return the generated artifacts this validator writes in --write mode."""

    return list(OUTPUTS)


class WorkflowFailureAuthorityProof(BaseModel):
    """Proof emitted by a durable worker run and surface readback probes."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    scenario: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    endpoint: str = Field(min_length=1)
    job_kind: str = Field(min_length=1)
    enqueued_at: str = Field(min_length=1)
    worker_lease_id: str = Field(min_length=1)
    worker_id: str = Field(min_length=1)
    execute_workflow_invocation_id: str = Field(
        alias="_execute_workflow_invocation_id",
        min_length=1,
    )
    workspace_loop_invocation_id: str = Field(min_length=1)
    control_store_state_transitions: list[str] = Field(min_length=1)
    input_artifacts: list[str] = Field(min_length=1)
    output_search_exit_contract_ref: str = Field(min_length=1)
    output_cas_refs: list[str] = Field(min_length=1)
    artifacts_index_refs: list[str] = Field(min_length=1)
    surface_reads_checked: list[str] = Field(min_length=1)
    surface_readbacks: list[dict[str, Any]] = Field(min_length=1)
    legacy_path_disposition: str = Field(min_length=1)
    authority_path: str = Field(min_length=1)
    authority_result: str = Field(min_length=1)
    terminal_job_state: str = Field(min_length=1)
    authority_boundary_ref: str = Field(min_length=1)
    progress_artifact_ref: str = Field(min_length=1)


def validate(repo_root: Path, *, write: bool = False) -> dict[str, Any]:
    """Return a drift report for failed-workflow authority proofs."""

    _ensure_src_path(repo_root)
    issues: list[dict[str, str]] = []
    _validate_generated_artifacts_registration(repo_root, issues)
    expected = build_live_proof_payloads(repo_root)
    _validate_proof_payload(expected[PROOF_PATH], issues)
    if write:
        for relative_path, payload in expected.items():
            path = repo_root / relative_path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps(payload, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
    else:
        for relative_path, expected_payload in expected.items():
            committed = _read_json(repo_root / relative_path, issues)
            if committed != expected_payload:
                issues.append(
                    {
                        "code": "layer3_workflow_failure_authority_drift",
                        "path": relative_path,
                    }
                )
    return {
        "status": "pass" if not issues else "fail",
        "family_id": FAMILY_ID,
        "checked_artifacts": OUTPUTS,
        "write": write,
        "issues": issues,
    }


def build_live_proof_payloads(repo_root: Path) -> dict[str, dict[str, Any]]:
    """Recompute proofs from durable worker jobs and public surface probes."""

    _ensure_src_path(repo_root)
    proofs = [
        _run_durable_authority_surface_proof("workflow_failure"),
        _run_durable_authority_surface_proof("legacy_shadow_candidate"),
    ]
    return {
        PROOF_PATH: {
            "schema_version": "policyos.policy_design_case.layer3_gy.workflow_failure_authority.v1",
            "owner": "team-runtime-quality",
            "proof_source": "durable_worker_surface_readback_recompute",
            "strangle_receipt": _workflow_completion_strangle_receipt(),
            "proofs": proofs,
        }
    }


def _run_durable_authority_surface_proof(scenario: str) -> dict[str, Any]:
    from polisyos.core.artifacts.manifest import SchemaInfo
    from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
    from polisyos.core.canon import CanonSpec
    from polisyos.core.contracts.control import NaturalLanguageRunRequest, WorkflowRunRequest
    from polisyos.data_forge.read_api.catalog import build_slice0_fixture_catalog_graph
    from polisyos.runtime.http.execution_policy import RuntimeExecutionPolicyResolver
    from polisyos.runtime.http.services.control.run_lifecycle import ControlPlaneService
    from polisyos.runtime.http.services.control_registry_providers import (
        resolve_control_registry_providers,
    )
    from polisyos.runtime.http.services.control_worker import ControlWorker

    uuid_iter = _deterministic_uuid_sequence(f"workflow-failure-authority:{scenario}")
    with tempfile.TemporaryDirectory(
        prefix=f"polisyos-workflow-failure-authority-{scenario}-"
    ) as tmp:
        root = Path(tmp)
        cas_root = root / ".polisyos"
        store = FileSystemCAS(cas_root)
        root_ref = store.put_json(
            {"fixture_id": scenario, "root": True},
            PutOptions(
                kind="workflow.failure.authority.root",
                media_type="application/json",
                schema=SchemaInfo(name="workflow.failure.authority.root", version="1.0"),
            ),
            canon_spec=CanonSpec(forbid_floats=False),
        )
        providers = resolve_control_registry_providers(
            gy_catalog_graph=build_slice0_fixture_catalog_graph(root / "catalog")
        )
        worker_id = f"control-worker-{next(uuid_iter).hex[:16]}"
        with ExitStack() as stack:
            stack.enter_context(
                patch(
                    "polisyos.core.run.context.secrets.token_hex",
                    side_effect=lambda size=8: next(uuid_iter).hex[: size * 2],
                )
            )
            for target in (
                "polisyos.runtime.http.services.control.run_lifecycle.uuid.uuid4",
                "polisyos.runtime.http.services.control.workspace_loop_transition.uuid.uuid4",
                "polisyos.runtime.http.services.control_worker.uuid.uuid4",
            ):
                stack.enter_context(patch(target, side_effect=lambda: next(uuid_iter)))
            stack.enter_context(
                patch(
                    "polisyos.runtime.http.services.control_plane_store._utc_now",
                    return_value=FIXED_TIME,
                )
            )
            stack.enter_context(
                patch(
                    "polisyos.runtime.http.services.control.run_lifecycle.logger.exception",
                    lambda *_args, **_kwargs: None,
                )
            )
            service = ControlPlaneService(
                cas_root=cas_root,
                core_runs_root=cas_root / "runs",
                artifact_store=store,
                registry_providers=providers,
                policy_resolver=RuntimeExecutionPolicyResolver(
                    default_profile="dev",
                    worker_backend="external",
                    state_store_backend="sqlite",
                    sqlite_path=str(root / "control_plane.sqlite3"),
                    postgres_dsn=None,
                ),
            )
            service._worker = ControlWorker(
                store=service._control_store,
                handler=service._process_control_job,
                worker_id=worker_id,
            )
            try:
                if scenario == "legacy_shadow_candidate":
                    launch = asyncio.run(
                        service.launch_nl_run(
                            NaturalLanguageRunRequest(
                                request=(
                                    "Estimate whether UA MSME credit access can be measured."
                                ),
                                max_iterations=1,
                            )
                        )
                    )
                    endpoint = "/api/v1/control/runs/nl"
                else:
                    launch = service.launch_workflow_run(
                        WorkflowRunRequest(
                            data_source={"data_snapshot_ref": str(root_ref.artifact_id)},
                            params={"slice0_fixture_id": "workflow_failure_missing_fixture"},
                        )
                    )
                    endpoint = "/api/v1/control/runs"
                response = _await_terminal_response(service, launch.job_id)
                progress = dict(response.progress)
                progress_ref = store.put_json(
                    progress,
                    PutOptions(
                        kind=f"workflow.failure.authority.progress.{scenario}",
                        media_type="application/json",
                        schema=SchemaInfo(
                            name="workflow.failure.authority.progress",
                            version="1.0",
                        ),
                    ),
                    canon_spec=CanonSpec(forbid_floats=False),
                )
                _claim_route_fixture_owner(store, progress_ref.artifact_id)
                surface_readbacks = _surface_readbacks(
                    cas_root=cas_root,
                    progress=progress,
                    progress_artifact_id=str(progress_ref.artifact_id),
                    scenario=scenario,
                    terminal_job=response.model_dump(mode="json"),
                )
                clean_completion_probe = _clean_completion_probe(root / "clean-completion.sqlite3")
                production_fields = _production_loop_fields(
                    progress=progress,
                    progress_artifact_ref=str(progress_ref.artifact_id),
                    scenario=scenario,
                    response=response,
                    service=service,
                    endpoint=endpoint,
                    worker_id=worker_id,
                )
                proof = WorkflowFailureAuthorityProof(
                    scenario=scenario,
                    run_id=str(launch.run_id),
                    job_id=str(launch.job_id),
                    endpoint=endpoint,
                    job_kind=production_fields["job_kind"],
                    enqueued_at=production_fields["enqueued_at"],
                    worker_lease_id=production_fields["worker_lease_id"],
                    worker_id=production_fields["worker_id"],
                    _execute_workflow_invocation_id=production_fields[
                        "_execute_workflow_invocation_id"
                    ],
                    workspace_loop_invocation_id=production_fields[
                        "workspace_loop_invocation_id"
                    ],
                    control_store_state_transitions=production_fields[
                        "control_store_state_transitions"
                    ],
                    input_artifacts=production_fields["input_artifacts"],
                    output_search_exit_contract_ref=production_fields[
                        "output_search_exit_contract_ref"
                    ],
                    output_cas_refs=production_fields["output_cas_refs"],
                    artifacts_index_refs=production_fields["artifacts_index_refs"],
                    surface_reads_checked=[
                        *production_fields["surface_reads_checked"],
                        *[readback["surface"] for readback in surface_readbacks],
                    ],
                    surface_readbacks=[
                        *production_fields["surface_readbacks"],
                        *surface_readbacks,
                        {
                            "surface": "clean_completion_probe",
                            **clean_completion_probe,
                        },
                    ],
                    legacy_path_disposition=str(progress.get("legacy_path_disposition")),
                    authority_path=str(progress.get("authority_path")),
                    authority_result=str(progress.get("authority_result")),
                    terminal_job_state=response.state,
                    authority_boundary_ref=str(
                        (progress.get("authority_boundary") or {}).get("boundary_id")
                    ),
                    progress_artifact_ref=str(progress_ref.artifact_id),
                )
                return proof.model_dump(mode="json", by_alias=True)
            finally:
                service.close()


def _production_loop_fields(
    *,
    progress: dict[str, Any],
    progress_artifact_ref: str,
    scenario: str,
    response: Any,
    service: Any,
    endpoint: str,
    worker_id: str,
) -> dict[str, Any]:
    record = service._control_store.get_job(response.job_id)
    enqueued_at = (
        record.created_at.isoformat()
        if record is not None and record.created_at is not None
        else FIXED_TIME.isoformat()
    )
    proof = progress.get("production_loop_run_proof")
    if isinstance(proof, dict):
        return {
            "job_kind": str(proof.get("job_kind") or response.kind),
            "enqueued_at": str(proof.get("enqueued_at") or enqueued_at),
            "worker_lease_id": str(proof.get("worker_lease_id") or worker_id),
            "worker_id": str(proof.get("worker_id") or worker_id),
            "_execute_workflow_invocation_id": str(
                proof.get("execute_workflow_invocation_id")
                or proof.get("_execute_workflow_invocation_id")
            ),
            "workspace_loop_invocation_id": str(proof.get("workspace_loop_invocation_id")),
            "control_store_state_transitions": _state_transitions(
                service._control_store,
                terminal_state=response.state,
            ),
            "input_artifacts": [str(item) for item in proof.get("input_artifacts") or []],
            "output_search_exit_contract_ref": str(
                proof.get("output_search_exit_contract_ref")
            ),
            "output_cas_refs": [str(item) for item in proof.get("output_cas_refs") or []],
            "artifacts_index_refs": [
                str(item) for item in proof.get("artifacts_index_refs") or []
            ],
            "surface_reads_checked": [
                str(item) for item in proof.get("surface_reads_checked") or []
            ],
            "surface_readbacks": [
                dict(item) for item in proof.get("surface_readbacks") or [] if isinstance(item, dict)
            ],
        }

    artifacts_index = progress.get("artifacts_index")
    artifacts_index_refs = sorted(str(key) for key in artifacts_index) if isinstance(
        artifacts_index, dict
    ) else ["progress_artifact_ref"]
    return {
        "job_kind": str(response.kind),
        "enqueued_at": enqueued_at,
        "worker_lease_id": worker_id,
        "worker_id": worker_id,
        "_execute_workflow_invocation_id": f"{scenario}:{response.job_id}:not_applicable",
        "workspace_loop_invocation_id": f"{scenario}:{response.job_id}:not_applicable",
        "control_store_state_transitions": _state_transitions(
            service._control_store,
            terminal_state=response.state,
        ),
        "input_artifacts": [progress_artifact_ref],
        "output_search_exit_contract_ref": progress_artifact_ref,
        "output_cas_refs": [progress_artifact_ref],
        "artifacts_index_refs": artifacts_index_refs,
        "surface_reads_checked": ["control_worker_precompletion"],
        "surface_readbacks": [],
    }


def _await_terminal_response(service: Any, job_id: str) -> Any:
    response = service.get_job_status(job_id)
    attempts = 0
    while response.state in {"pending", "running"} and attempts < 20:
        if service._worker is None:
            raise RuntimeError("Durable proof worker was not initialized")
        service._worker.dispatch_once()
        response = service.get_job_status(job_id)
        attempts += 1
    if response.state not in {"completed", "failed"}:
        raise RuntimeError(f"Durable proof job did not reach terminal state: {response.state}")
    return response


def _surface_readbacks(
    *,
    cas_root: Path,
    progress: dict[str, Any],
    progress_artifact_id: str,
    scenario: str,
    terminal_job: dict[str, Any],
) -> list[dict[str, Any]]:
    from polisyos.runtime.http.app import create_runtime_api_app
    from polisyos.runtime.quality.authority import authority_surface_decision
    from polisyos.runtime.quality.public_export import (
        PublicExportRedactionError,
        build_public_export_bundle,
    )

    try:
        from fastapi.testclient import TestClient
    except ModuleNotFoundError as exc:  # pragma: no cover
        raise RuntimeError(
            "Workflow failure authority validator requires fastapi testclient"
        ) from exc

    app = create_runtime_api_app(
        cas_root=cas_root,
        core_runs_root=cas_root / "runs",
        allow_unscoped_artifacts=True,
        allow_fixture_identity=True,
        enable_response_compression=False,
        enable_security_middlewares=False,
    )
    readbacks: list[dict[str, Any]] = [
        {
            "surface": "run",
            "read_method": "ControlPlaneService.get_job_status",
            "observed_job_state": terminal_job["state"],
            "observed_authority_result": progress.get("authority_result"),
            "decision": authority_surface_decision(progress, surface="run").model_dump(
                mode="json"
            ),
        }
    ]
    with TestClient(app, raise_server_exceptions=False) as client:
        route_specs = (
            (
                "artifact",
                "GET",
                f"/api/v1/artifacts/{progress_artifact_id}/content",
                {"headers": {"Accept": "application/json"}},
            ),
            (
                "lineage",
                "GET",
                f"/api/v1/artifacts/{progress_artifact_id}/lineage",
                {},
            ),
            (
                "export",
                "GET",
                f"/api/v1/artifacts/{progress_artifact_id}/export",
                {},
            ),
            (
                "dashboard",
                "POST",
                f"/api/v1/artifacts/{progress_artifact_id}/render",
                {
                    "json": {
                        "genre": "postanova_kmu",
                        "jurisdiction": "ua",
                        "trust_view": True,
                    }
                },
            ),
        )
        for surface, method, path, kwargs in route_specs:
            response = (
                client.post(path, **kwargs)
                if method == "POST"
                else client.get(path, **kwargs)
            )
            readbacks.append(
                {
                    "surface": surface,
                    "read_method": f"{method} {path}",
                    "status_code": response.status_code,
                    "blocked_or_downgraded": response.status_code == 409,
                    "decision": authority_surface_decision(
                        progress,
                        surface=surface,
                    ).model_dump(mode="json"),
                }
            )

    public_packet_readback: dict[str, Any]
    try:
        bundle = build_public_export_bundle(
            run_id=f"run-public-packet-{scenario}",
            artifacts={"progress": progress},
            generated_at=FIXED_TIME,
        )
    except PublicExportRedactionError as exc:
        public_packet_readback = {
            "surface": "public_packet",
            "read_method": "build_public_export_bundle",
            "blocked_or_downgraded": True,
            "error_code": exc.code,
            "decision": authority_surface_decision(
                progress,
                surface="public_packet",
            ).model_dump(mode="json"),
        }
    else:
        public_packet_readback = {
            "surface": "public_packet",
            "read_method": "build_public_export_bundle",
            "blocked_or_downgraded": bool(
                bundle["semantic_audit"]["authority_surface_decisions"]
            ),
            "decisions": bundle["semantic_audit"]["authority_surface_decisions"],
            "decision": authority_surface_decision(
                progress,
                surface="public_packet",
            ).model_dump(mode="json"),
        }
    readbacks.append(public_packet_readback)
    return readbacks


def _clean_completion_probe(sqlite_path: Path) -> dict[str, Any]:
    from polisyos.runtime.http.services.control_plane_store import ControlPlaneStore

    store = ControlPlaneStore(backend="sqlite", sqlite_path=sqlite_path)
    try:
        store.create_job(
            job_id="job-clean-completion-probe",
            kind="workflow_run",
            run_id="run-clean-completion-probe",
            pipeline_id=None,
            requested_execution_profile=None,
            effective_execution_profile="dev",
            policy_flags={},
            capability_manifest_ref=None,
            payload_ref=None,
            submitted_by="validator",
        )
        store.complete_job(
            job_id="job-clean-completion-probe",
            progress={
                "state": "failed",
                "runtime_state": "blocked",
                "authority_path": "workflow_failure",
                "authority_result": "repair_required",
                "legacy_path_disposition": "blocked_workflow_failure_ring2_withheld",
                "failure": {
                    "code": "workflow_failed_non_authority",
                    "message": "clean completion probe failed",
                },
            },
        )
        record = store.get_job("job-clean-completion-probe")
        if record is None:
            raise RuntimeError("clean completion probe record missing")
        return {
            "attempted_state_after": "completed",
            "observed_job_state": record.state,
            "blocked_clean_completion": record.state == "failed",
            "error_message": record.error_message,
        }
    finally:
        store.close()


def _state_transitions(store: Any, *, terminal_state: str) -> list[str]:
    transitions = ["pending"]
    topics = [event.topic for event in store.list_outbox_events(state=None, limit=128)]
    if "control.job.running" in topics:
        transitions.append("running")
    transitions.append(terminal_state)
    return transitions


def _workflow_completion_strangle_receipt() -> dict[str, Any]:
    return {
        "predecessor_ref": (
            "runtime.http.services.control.run_lifecycle.workflow_run."
            "complete_job_unconditional_completed"
        ),
        "replacement_ref": (
            "runtime.http.services.control_plane_store.complete_job."
            "fail_closed_workflow_failure_progress"
        ),
        "disposition": "fenced_default_flipped",
        "default_before": (
            "workflow failure progress could be completed by a direct complete_job caller"
        ),
        "default_after": (
            "workflow failure progress is converted to failed before completion events"
        ),
        "guard_ref": (
            "tests/unit/runtime/http/test_control_plane_store.py::"
            "test_control_plane_store_rejects_clean_completion_for_failed_workflow_progress"
        ),
        "remaining_callers": [
            "runtime.http.services.control.run_lifecycle._process_control_job",
            "tests and diagnostics that intentionally call complete_job",
        ],
        "remaining_callers_disposition": (
            "all callers pass through store-level fail-closed guard"
        ),
        "removed_loc": "src/polisyos/runtime/http/services/control_plane_store.py::complete_job",
        "verified_by": [
            "tools/quality/validation/check_layer3_workflow_failure_authority.py "
            "--check --repo-root .",
        ],
    }


def _claim_route_fixture_owner(store: Any, *artifact_ids: Any) -> None:
    for artifact_id in artifact_ids:
        store.record_artifact_owner(
            artifact_id,
            tenant_id=FIXTURE_TENANT_ID,
            cell_id=FIXTURE_CELL_ID,
            writer="layer3-workflow-failure-authority-validator",
        )


def _validate_generated_artifacts_registration(
    repo_root: Path,
    issues: list[dict[str, str]],
) -> None:
    try:
        generated = tomllib.loads(
            (repo_root / "architecture/generated_artifacts.toml").read_text(
                encoding="utf-8"
            )
        )
    except FileNotFoundError:
        issues.append({"code": "generated_artifacts_registry_missing"})
        return
    families = {family.get("id"): family for family in generated.get("family", [])}
    family = families.get(FAMILY_ID)
    if not family:
        issues.append({"code": "workflow_failure_authority_family_missing"})
        return
    if family.get("stale_output_behavior") != "fail":
        issues.append({"code": "workflow_failure_authority_stale_output_not_fail"})
    if PROOF_PATH not in set(family.get("outputs") or []):
        issues.append({"code": "workflow_failure_authority_output_not_registered"})
    if "--check" not in list(family.get("check_command") or []):
        issues.append({"code": "workflow_failure_authority_check_mode_missing"})
    regenerate_commands = " ".join(family.get("regenerate_commands") or [])
    if "--write" not in regenerate_commands:
        issues.append({"code": "workflow_failure_authority_write_mode_missing"})


def _validate_proof_payload(payload: dict[str, Any], issues: list[dict[str, str]]) -> None:
    if payload.get("schema_version") != (
        "policyos.policy_design_case.layer3_gy.workflow_failure_authority.v1"
    ):
        issues.append({"code": "workflow_failure_authority_schema_version_invalid"})
    receipt = payload.get("strangle_receipt")
    if not isinstance(receipt, dict):
        issues.append({"code": "workflow_failure_authority_strangle_receipt_missing"})
    else:
        for field in (
            "predecessor_ref",
            "replacement_ref",
            "disposition",
            "default_before",
            "default_after",
            "guard_ref",
            "remaining_callers",
            "remaining_callers_disposition",
            "removed_loc",
            "verified_by",
        ):
            if not receipt.get(field):
                issues.append(
                    {
                        "code": "workflow_failure_authority_strangle_receipt_field_missing",
                        "field": field,
                    }
                )
    proofs = payload.get("proofs")
    if not isinstance(proofs, list) or len(proofs) != 2:
        issues.append({"code": "workflow_failure_authority_proof_count_invalid"})
        return
    by_scenario: dict[str, dict[str, Any]] = {}
    for index, raw_proof in enumerate(proofs):
        try:
            proof = WorkflowFailureAuthorityProof.model_validate(raw_proof)
        except ValueError as exc:
            issues.append(
                {
                    "code": "workflow_failure_authority_proof_shape_invalid",
                    "index": str(index),
                    "error": str(exc),
                }
            )
            continue
        by_scenario[proof.scenario] = proof.model_dump(mode="json")
        if set(proof.surface_reads_checked) < set(SURFACE_NAMES):
            issues.append(
                {
                    "code": "workflow_failure_authority_surface_coverage_missing",
                    "scenario": proof.scenario,
                }
            )
        for readback in proof.surface_readbacks:
            _validate_readback(proof.scenario, readback, issues)
    failure = by_scenario.get("workflow_failure")
    if failure and failure.get("terminal_job_state") != "failed":
        issues.append({"code": "workflow_failure_clean_completed"})
    candidate = by_scenario.get("legacy_shadow_candidate")
    if candidate and candidate.get("authority_result") != "candidate_only":
        issues.append({"code": "legacy_shadow_not_candidate_only"})


def _validate_readback(
    scenario: str,
    readback: dict[str, Any],
    issues: list[dict[str, str]],
) -> None:
    surface = str(readback.get("surface") or "")
    if surface == "clean_completion_probe":
        if readback.get("blocked_clean_completion") is not True:
            issues.append({"code": "clean_completion_probe_not_blocked"})
        return
    decision = readback.get("decision")
    if not isinstance(decision, dict):
        issues.append(
            {
                "code": "workflow_failure_authority_decision_missing",
                "scenario": scenario,
                "surface": surface,
            }
        )
        return
    if decision.get("consumed_authority_boundary") is not True:
        issues.append(
            {
                "code": "workflow_failure_authority_boundary_not_consumed",
                "scenario": scenario,
                "surface": surface,
            }
        )
    if not (decision.get("blocking") or decision.get("visible_downgrade")):
        issues.append(
            {
                "code": "workflow_failure_authority_surface_not_blocked_or_downgraded",
                "scenario": scenario,
                "surface": surface,
            }
        )
    if surface in {"artifact", "lineage", "export", "dashboard"} and (
        readback.get("status_code") != 409
    ):
        issues.append(
            {
                "code": "workflow_failure_authority_route_not_blocked",
                "scenario": scenario,
                "surface": surface,
                "status_code": str(readback.get("status_code")),
            }
        )


def _deterministic_uuid_sequence(seed: str) -> Iterator[uuid.UUID]:
    index = 0
    while True:
        yield uuid.uuid5(uuid.NAMESPACE_URL, f"{seed}:{index}")
        index += 1


def _ensure_src_path(repo_root: Path) -> None:
    src_path = repo_root / "src"
    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))


def _read_json(path: Path, issues: list[dict[str, str]]) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        issues.append({"code": "workflow_failure_authority_artifact_missing", "path": str(path)})
        return {}
    except json.JSONDecodeError as exc:
        issues.append(
            {
                "code": "workflow_failure_authority_artifact_invalid_json",
                "path": str(path),
                "error": str(exc),
            }
        )
        return {}
    if not isinstance(payload, dict):
        issues.append(
            {
                "code": "workflow_failure_authority_artifact_not_object",
                "path": str(path),
            }
        )
        return {}
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--output-format", choices=("json", "text"), default="text")
    parser.add_argument("--check", action="store_true", help="Validate committed artifacts.")
    parser.add_argument(
        "--write",
        action="store_true",
        help="Regenerate committed proof artifacts.",
    )
    args = parser.parse_args(argv)
    if args.check and args.write:
        parser.error("--check and --write are mutually exclusive")

    with contextlib.redirect_stdout(sys.stderr):
        report = validate(Path(args.repo_root).resolve(), write=args.write)
    if args.output_format == "json":
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"Layer 3 workflow failure authority: {report['status']}")
        for issue in report["issues"]:
            print(f"- {issue['code']}: {issue}")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
