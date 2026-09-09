#!/usr/bin/env python3
"""Validate failed-workflow authority-surface proof artifacts."""

from __future__ import annotations

import argparse
import contextlib
import copy
import hashlib
import json
import re
import sqlite3
import sys
import tempfile
import tomllib
import uuid
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

FAMILY_ID = "policy-design-case-layer3-workflow-failure-authority"
HISTORY_FAMILY_ID = "policy-design-case-layer3-workflow-failure-authority-history"
HISTORICAL_PROOF_PATH = (
    "architecture/policy_design_case/layer3_gy_workflow_failure_authority_proofs.json"
)
HISTORICAL_PROOF_SHA256 = "9eb9463e2ec2701f1f45d001d307796db7e650567b388545863c1f9f578efcb5"
PROOF_PATH = "architecture/policy_design_case/layer3_gy_workflow_failure_authority_proofs_v2.json"
SCHEMA_VERSION = "policyos.policy_design_case.layer3_gy.workflow_failure_authority.v2"
OUTPUTS = [PROOF_PATH]
FIXTURE_TENANT_ID = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
FIXTURE_CELL_ID = "cell-a"
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


class WorkflowWorkerClaim(BaseModel):
    """Readback of the actual persisted running event and its worker lease."""

    model_config = ConfigDict(extra="forbid")
    event_id: str = Field(min_length=1)
    created_at: datetime
    payload: dict[str, Any]


class WorkflowFailureAuthorityProof(BaseModel):
    """Actual durable job, persisted execution and unchanged surface decisions."""

    model_config = ConfigDict(extra="forbid")
    scenario: Literal["workflow_failure", "legacy_shadow_candidate"]
    run_id: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    endpoint: Literal["/api/v1/control/runs"]
    job_kind: Literal["workflow_run"]
    enqueued_at: datetime
    started_at: datetime
    finished_at: datetime
    worker_id: str = Field(min_length=1)
    worker_claim: WorkflowWorkerClaim
    control_store_state_transitions: list[str] = Field(min_length=1)
    control_event_denominator: int = Field(gt=0)
    request_artifact_ref: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    request_payload: dict[str, Any]
    input_artifacts: list[str] = Field(min_length=1)
    surface_reads_checked: list[str] = Field(min_length=1)
    surface_readbacks: list[dict[str, Any]] = Field(min_length=1)
    legacy_path_disposition: str = Field(min_length=1)
    authority_path: str = Field(min_length=1)
    authority_result: str = Field(min_length=1)
    terminal_job_state: Literal["completed", "failed"]
    authority_boundary_ref: str = Field(min_length=1)
    progress_artifact_ref: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    progress_payload: dict[str, Any]
    workflow_execution: dict[str, Any] | None


def validate(repo_root: Path, *, write: bool = False) -> dict[str, Any]:
    """Return a drift report for failed-workflow authority proofs."""

    _ensure_src_path(repo_root)
    issues: list[dict[str, str]] = []
    _validate_generated_artifacts_registration(repo_root, issues)
    if (
        not (repo_root / HISTORICAL_PROOF_PATH).is_file()
        or hashlib.sha256((repo_root / HISTORICAL_PROOF_PATH).read_bytes()).hexdigest()
        != HISTORICAL_PROOF_SHA256
    ):
        issues.append(
            {"code": "workflow_failure_authority_history_drift", "path": HISTORICAL_PROOF_PATH}
        )
    expected = build_live_proof_payloads(repo_root)
    _validate_proof_payload(expected[PROOF_PATH], issues)
    if write:
        if not issues:
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
            try:
                equal = comparison_payload(committed) == comparison_payload(expected_payload)
            except (KeyError, TypeError, ValueError):
                equal = False
            if not equal:
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
        # The check run has fresh coordinates and cannot be replayed as history.
        # Write mode already stores its full record in the tracked artifact.
        **({"recomputed_proofs": expected[PROOF_PATH]} if not write else {}),
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
            "schema_version": SCHEMA_VERSION,
            "owner": "team-runtime-quality",
            "proof_source": "durable_worker_surface_readback_recompute",
            "strangle_receipt": _workflow_completion_strangle_receipt(),
            "canonical_proof_strangle_receipt": _canonical_proof_strangle_receipt(),
            "historical_proof": {
                "path": HISTORICAL_PROOF_PATH,
                "sha256": HISTORICAL_PROOF_SHA256,
                "disposition": "recorded_v1_not_current_execution_evidence",
            },
            "proofs": proofs,
        }
    }


def _run_durable_authority_surface_proof(scenario: str) -> dict[str, Any]:
    from polisyos.core.artifacts.manifest import SchemaInfo
    from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
    from polisyos.core.canon import CanonSpec
    from polisyos.core.contracts.control import WorkflowRunRequest
    from polisyos.data_forge.read_api.catalog import build_slice0_fixture_catalog_graph
    from polisyos.runtime.http.execution_policy import RuntimeExecutionPolicyResolver
    from polisyos.runtime.http.services.control.run_lifecycle import ControlPlaneService
    from polisyos.runtime.http.services.control_registry_providers import (
        resolve_control_registry_providers,
    )
    from polisyos.runtime.http.services.control_worker import ControlWorker

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
        worker_id = f"control-worker-{uuid.uuid4().hex[:16]}"
        sqlite_path = root / "control_plane.sqlite3"
        service = ControlPlaneService(
            cas_root=cas_root,
            core_runs_root=cas_root / "runs",
            artifact_store=store,
            registry_providers=providers,
            policy_resolver=RuntimeExecutionPolicyResolver(
                default_profile="dev",
                worker_backend="external",
                state_store_backend="sqlite",
                sqlite_path=str(sqlite_path),
                postgres_dsn=None,
            ),
        )
        service._worker = ControlWorker(
            store=service._control_store, handler=service._process_control_job, worker_id=worker_id
        )
        try:
            params = (
                {"control_plane_transition": "legacy_shadow", "workflow_id": "scientist_discovery"}
                if scenario == "legacy_shadow_candidate"
                else {"slice0_fixture_id": "workflow_failure_missing_fixture"}
            )
            launch = service.launch_workflow_run(
                WorkflowRunRequest(
                    data_source={"data_snapshot_ref": str(root_ref.artifact_id)},
                    params=params,
                )
            )
            response = _await_terminal_response(service, launch.job_id)
            progress = dict(response.progress)
            progress_ref = store.put_json(
                progress,
                PutOptions(
                    kind=f"workflow.failure.authority.progress.{scenario}",
                    media_type="application/json",
                    schema=SchemaInfo(name="workflow.failure.authority.progress", version="1.0"),
                ),
                canon_spec=CanonSpec(forbid_floats=False),
            )
            if (
                _read_cas_json(
                    store,
                    str(progress_ref.artifact_id),
                    kind=f"workflow.failure.authority.progress.{scenario}",
                    schema_name="workflow.failure.authority.progress",
                )
                != progress
            ):
                raise ValueError("workflow_progress_content_mismatch")
            record = service._control_store.get_job(launch.job_id)
            if record is None or record.payload_ref is None:
                raise ValueError("workflow_durable_job_missing")
            request = _read_cas_json(
                store,
                record.payload_ref,
                kind="runtime.control_job_payload.workflow_run",
                schema_name="polisyos.runtime.ControlJobPayload",
            )
            if request["run_id"] != launch.run_id or request["state_payload"]["params"] != params:
                raise ValueError("workflow_request_binding_mismatch")
            events = service._control_store.list_outbox_events(state=None, limit=500)
            with sqlite3.connect(f"file:{sqlite_path}?mode=ro", uri=True) as connection:
                independent = {
                    str(row[0])
                    for row in connection.execute("SELECT event_id FROM control_outbox_events")
                }
            if {event.event_id for event in events} != independent:
                raise ValueError("workflow_event_population_incomplete")
            selected_events = [event for event in events if event.job_id == launch.job_id]
            running = [event for event in selected_events if event.topic == "control.job.running"]
            if len(running) != 1 or running[0].payload["lease_owner"] != worker_id:
                raise ValueError("workflow_worker_claim_not_established")
            transitions = list(
                dict.fromkeys(
                    event.payload["state"]
                    for event in sorted(selected_events, key=lambda item: item.created_at)
                    if event.topic.startswith("control.job.") and "state" in event.payload
                )
            )
            if transitions != ["pending", "running", response.state]:
                raise ValueError("workflow_state_transitions_not_established")
            workflow_execution = (
                _read_workflow_execution(store, run_id=launch.run_id)
                if scenario == "legacy_shadow_candidate"
                else None
            )
            _claim_route_fixture_owner(store, progress_ref.artifact_id)
            readbacks = _surface_readbacks(
                cas_root=cas_root,
                progress=progress,
                progress_artifact_id=str(progress_ref.artifact_id),
                scenario=scenario,
                terminal_job=response.model_dump(mode="json"),
            )
            proof = WorkflowFailureAuthorityProof(
                scenario=scenario,
                run_id=launch.run_id,
                job_id=launch.job_id,
                endpoint="/api/v1/control/runs",
                job_kind=record.kind,
                enqueued_at=record.created_at,
                started_at=record.started_at,
                finished_at=record.finished_at,
                worker_id=worker_id,
                worker_claim=WorkflowWorkerClaim(
                    event_id=running[0].event_id,
                    created_at=running[0].created_at,
                    payload=running[0].payload,
                ),
                control_store_state_transitions=transitions,
                control_event_denominator=len(events),
                request_artifact_ref=record.payload_ref,
                request_payload=json.loads(store.get_bytes(record.payload_ref)),
                input_artifacts=[str(root_ref.artifact_id)],
                surface_reads_checked=[
                    "control_worker_precompletion",
                    *[row["surface"] for row in readbacks],
                ],
                surface_readbacks=[
                    *readbacks,
                    {
                        "surface": "clean_completion_probe",
                        **_clean_completion_probe(root / "clean-completion.sqlite3"),
                    },
                ],
                legacy_path_disposition=progress["legacy_path_disposition"],
                authority_path=progress["authority_path"],
                authority_result=progress["authority_result"],
                terminal_job_state=response.state,
                authority_boundary_ref=progress["authority_boundary"]["boundary_id"],
                progress_artifact_ref=str(progress_ref.artifact_id),
                progress_payload=json.loads(store.get_bytes(progress_ref.artifact_id)),
                workflow_execution=workflow_execution,
            )
            result = proof.model_dump(mode="json")
            _validate_recorded_proof(result, store=store)
            return result
        finally:
            service.close()


def _read_cas_json(store: Any, ref: str, *, kind: str, schema_name: str) -> dict[str, Any]:
    from polisyos.core.artifacts.manifest import CanonInfo, SchemaInfo
    from polisyos.core.canon import CanonSpec, from_canonical_bytes

    raw = store.get_bytes(ref)
    manifest = store.get_manifest(ref)
    if (
        not store.verify(ref).ok
        or str(manifest.artifact_id) != ref
        or hashlib.sha256(raw).hexdigest() != ref.removeprefix("sha256:")
        or manifest.byte_size != len(raw)
        or manifest.kind != kind
        or manifest.media_type != "application/json"
        or manifest.canon
        != CanonInfo.from_spec(CanonSpec(forbid_floats=kind == "scientist.workflow_report"))
        or manifest.artifact_schema != SchemaInfo(name=schema_name, version="1.0")
    ):
        raise ValueError("workflow_source_custody_invalid")
    value = from_canonical_bytes(raw)
    if not isinstance(value, dict):
        raise ValueError("workflow_source_payload_invalid")
    return value


def _read_workflow_execution(store: Any, *, run_id: str) -> dict[str, Any]:
    from polisyos.scientist.orchestration.engine.executor import WorkflowReport
    from polisyos.scientist.orchestration.engine.workflow_spec import WorkflowSpec
    from polisyos.scientist.orchestration.workflows.discovery import discovery_workflow_spec

    identities = store.iter_artifact_ids()
    independent = {
        "sha256:" + path.name.removesuffix(".manifest.json")
        for path in store.base.rglob("*.manifest.json")
    }
    if set(map(str, identities)) != independent:
        raise ValueError("workflow_report_cas_population_incomplete")
    selected = {"scientist.workflow_report": [], "scientist.workflow_spec": []}
    for identity in identities:
        kind = store.get_manifest(identity).kind
        if kind in selected:
            selected[kind].append(str(identity))
    if any(len(refs) != 1 for refs in selected.values()):
        raise ValueError("workflow_report_execution_not_established")
    result: dict[str, Any] = {"cas_manifest_denominator": len(identities)}
    for suffix, schema in (("report", "WorkflowReport"), ("spec", "WorkflowSpec")):
        ref = selected[f"scientist.workflow_{suffix}"][0]
        result[f"workflow_{suffix}_ref"] = ref
        raw_payload = _read_cas_json(
            store,
            ref,
            kind=f"scientist.workflow_{suffix}",
            schema_name=f"polisyos.scientist.orchestration.engine.{schema}",
        )
        model = WorkflowReport if suffix == "report" else WorkflowSpec
        typed = model.model_validate(raw_payload)
        if typed.model_dump(mode="python") != raw_payload:
            raise ValueError("workflow_source_raw_shape_mismatch")
        result[f"workflow_{suffix}"] = typed.model_dump(mode="json")
    if result["workflow_spec"] != discovery_workflow_spec().model_dump(mode="json"):
        raise ValueError("workflow_spec_owner_mismatch")
    _validated_execution(result, run_id=run_id)
    return result


def _validated_execution(value: dict[str, Any], *, run_id: str) -> None:
    from polisyos.core.canon import CanonSpec, to_canonical_bytes
    from polisyos.scientist.orchestration.engine.executor import WorkflowReport
    from polisyos.scientist.orchestration.engine.workflow_spec import WorkflowSpec

    if set(value) != {
        "cas_manifest_denominator",
        "workflow_spec_ref",
        "workflow_spec",
        "workflow_report_ref",
        "workflow_report",
    }:
        raise ValueError("workflow_execution_shape_invalid")
    report = WorkflowReport.model_validate(value["workflow_report"])
    spec = WorkflowSpec.model_validate(value["workflow_spec"])
    for suffix, model in (("report", report), ("spec", spec)):
        if model.model_dump(mode="json") != value[f"workflow_{suffix}"]:
            raise ValueError("workflow_recorded_raw_shape_mismatch")
        raw = to_canonical_bytes(
            model.model_dump(mode="python"), spec=CanonSpec(forbid_floats=suffix == "report")
        )
        if value[f"workflow_{suffix}_ref"] != "sha256:" + hashlib.sha256(raw).hexdigest():
            raise ValueError("workflow_report_recorded_content_mismatch")
    if (
        report.run_id != run_id
        or report.workflow_id != spec.workflow_id
        or report.error_policy != spec.error_policy
        or report.status != "ok"
        or not spec.nodes
        or any(row.status == "fail" or row.duration_ms < 0 for row in report.nodes)
        or Counter((row.alias, row.node_id) for row in report.nodes)
        != Counter((row.alias, str(row.node_id)) for row in spec.nodes)
    ):
        raise ValueError("workflow_report_execution_mismatch")
    if len(report.nodes) != len(spec.nodes):
        raise ValueError("workflow_report_node_population_incomplete")
    for row in report.nodes:
        if row.skip_blocker is not None:
            _utc_coordinate(row.skip_blocker.generated_at)


def _utc_coordinate(value: Any) -> datetime:
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset().total_seconds() != 0
    ):
        raise ValueError("workflow_operational_time_not_established")
    return value


def _validate_recorded_proof(value: dict[str, Any], *, store: Any = None) -> None:
    from polisyos.pdc import AuthorityBoundary

    proof = WorkflowFailureAuthorityProof.model_validate(value)
    request = _verified_recorded_payload(proof.request_payload, proof.request_artifact_ref)
    progress = _verified_recorded_payload(proof.progress_payload, proof.progress_artifact_ref)
    times = [
        _utc_coordinate(item) for item in (proof.enqueued_at, proof.started_at, proof.finished_at)
    ]
    if times != sorted(times):
        raise ValueError("workflow_job_time_order_invalid")
    claim = proof.worker_claim
    claimed_at = _utc_coordinate(claim.created_at)
    expires_at = _utc_coordinate(claim.payload["lease_expires_at"])
    if not times[0] <= claimed_at <= times[-1] or expires_at <= claimed_at:
        raise ValueError("workflow_worker_claim_time_invalid")
    if (
        claim.payload["job_id"] != proof.job_id
        or claim.payload["run_id"] != proof.run_id
        or claim.payload["job_kind"] != proof.job_kind
        or claim.payload["state"] != "running"
        or claim.payload["lease_owner"] != proof.worker_id
        or request["run_id"] != proof.run_id
        or request["state_payload"]["run_id"] != proof.run_id
        or progress["run_id"] != proof.run_id
        or progress["authority_result"] != proof.authority_result
        or progress["authority_path"] != proof.authority_path
        or progress["legacy_path_disposition"] != proof.legacy_path_disposition
        or [request["state_payload"]["inputs"]["data_snapshot_ref"]["artifact_id"]]
        != proof.input_artifacts
    ):
        raise ValueError("workflow_job_binding_mismatch")
    boundary = AuthorityBoundary.model_validate(progress["authority_boundary"])
    if boundary.boundary_id != proof.authority_boundary_ref or not boundary.boundary_id.endswith(
        "." + proof.job_id
    ):
        raise ValueError("workflow_boundary_job_binding_mismatch")
    _validate_progress_reference_closure(proof, progress, store=store)
    if proof.scenario == "legacy_shadow_candidate":
        if proof.workflow_execution is None:
            raise ValueError("workflow_report_execution_not_established")
        _validated_execution(proof.workflow_execution, run_id=proof.run_id)
        for row in proof.workflow_execution["workflow_report"]["nodes"]:
            if (
                row["skip_blocker"] is not None
                and not times[1].replace(microsecond=0)
                <= _utc_coordinate(row["skip_blocker"]["generated_at"])
                <= times[-1]
            ):
                raise ValueError("workflow_blocker_time_outside_run")
    elif proof.workflow_execution is not None:
        raise ValueError("workflow_failure_has_unclaimed_execution")


def _verified_recorded_payload(value: dict[str, Any], ref: str) -> dict[str, Any]:
    from polisyos.core.canon import CanonSpec, from_canonical_bytes, to_canonical_bytes

    decoded = from_canonical_bytes(json.dumps(value).encode("utf-8"))
    raw = to_canonical_bytes(decoded, spec=CanonSpec(forbid_floats=False))
    if ref != "sha256:" + hashlib.sha256(raw).hexdigest():
        raise ValueError("workflow_recorded_content_mismatch")
    return decoded


def _progress_output_bodies(progress: dict[str, Any]) -> list[tuple[dict[str, Any], str, str]]:
    """Read the complete outputs of the existing failed-loop owner projection.

    The owner is WorkspaceLoopTransitionMixin._attach_failed_workspace_loop_proof.
    These are projections of bodies retained once in progress, not substitute CAS
    records. Live admission resolves and compares the actual emitted bytes.
    """

    return [
        (
            {key: progress.get(key) for key in (
                "state", "phase", "authority_path", "authority_result",
                "legacy_path_disposition", "failure",
            )},
            "pdc.gy.workflow_failure_non_authority",
            "polisyos.pdc.gy.WorkflowFailureNonAuthority",
        ),
        (progress["authority_boundary"], "pdc.gy.workflow_failure_authority_boundary",
         "polisyos.pdc.gy.WorkflowFailureAuthorityBoundary"),
        (progress["authority_surface_packet"], "pdc.gy.workflow_failure_authority_surface_packet",
         "polisyos.pdc.gy.WorkflowFailureAuthoritySurfacePacket"),
    ]


def _all_cas_references(value: Any) -> set[str]:
    if isinstance(value, dict):
        return set().union(*(_all_cas_references(child) for child in value.values()))
    if isinstance(value, list):
        return set().union(*(_all_cas_references(child) for child in value))
    return {value} if isinstance(value, str) and value.startswith("sha256:") else set()


def _validate_progress_reference_closure(
    proof: WorkflowFailureAuthorityProof, progress: dict[str, Any], *, store: Any = None,
) -> None:
    from polisyos.runtime.quality.authority import ProductionLoopRunProof

    if proof.scenario != "workflow_failure":
        if _all_cas_references(progress):
            raise ValueError("workflow_progress_reference_closure_unclaimed")
        return
    raw_loop = progress["production_loop_run_proof"]
    loop = ProductionLoopRunProof.model_validate(raw_loop)
    if loop.model_dump(mode="json", by_alias=True) != raw_loop:
        raise ValueError("workflow_progress_raw_shape_mismatch")
    outputs = _progress_output_bodies(progress)
    if len(loop.output_cas_refs) != len(outputs):
        raise ValueError("workflow_progress_output_population_mismatch")
    records = [
        (ref, body, kind, schema)
        for ref, (body, kind, schema) in zip(loop.output_cas_refs, outputs, strict=True)
    ]
    records.append((
        progress["production_loop_run_proof_ref"], raw_loop,
        "pdc.gy.production_loop_run_proof", "polisyos.runtime.ProductionLoopRunProof",
    ))
    for ref, body, kind, schema in records:
        decoded = _verified_recorded_payload(body, ref)
        if store is not None and _read_cas_json(store, ref, kind=kind, schema_name=schema) != decoded:
            raise ValueError("workflow_progress_record_content_mismatch")
    if (
        loop.run_id != proof.run_id or loop.job_id != proof.job_id
        or loop.endpoint != proof.endpoint or loop.job_kind != proof.job_kind
        or loop.worker_id != proof.worker_id or loop.worker_lease_id != proof.worker_id
        or _utc_coordinate(loop.enqueued_at) != proof.enqueued_at
        or loop.http_request_id != "control-job:" + proof.job_id
        or loop.input_artifacts != proof.input_artifacts
        or loop.control_store_state_transitions != proof.control_store_state_transitions[:-1]
        or loop.legacy_path_disposition != proof.legacy_path_disposition
    ):
        raise ValueError("workflow_progress_durable_binding_mismatch")
    for value, pattern in (
        (loop.execute_workflow_invocation_id, r"execute-workflow-[0-9a-f]{16}"),
        (loop.workspace_loop_invocation_id, r"workspace-loop-[0-9a-f]{16}"),
    ):
        if re.fullmatch(pattern, value) is None:
            raise ValueError("workflow_progress_invocation_coordinate_invalid")
    failure_ref = loop.output_cas_refs[0]
    proof_ref = progress["production_loop_run_proof_ref"]
    index = progress["artifacts_index"]
    evidence = progress["quality_scorecard"]["evidence_refs"]
    if (
        loop.output_search_exit_contract_ref != failure_ref
        or any(item["workflow_failure_ref"] != failure_ref for item in (index, evidence))
        or any(item["production_loop_run_proof_ref"] != proof_ref for item in (index, evidence))
        or _all_cas_references(progress)
        != {proof_ref, *loop.output_cas_refs, *loop.input_artifacts}
    ):
        raise ValueError("workflow_progress_reference_closure_mismatch")


def _replace_bound_values(value: Any, replacements: dict[str, str]) -> Any:
    """Substitute only exact already-bound identities, keeping all fields."""

    if isinstance(value, dict):
        return {key: _replace_bound_values(child, replacements) for key, child in value.items()}
    if isinstance(value, list):
        return [_replace_bound_values(child, replacements) for child in value]
    return replacements.get(value, value) if isinstance(value, str) else value


def _semantic_record_digest(body: dict[str, Any]) -> str:
    from polisyos.core.canon import CanonSpec, to_canonical_bytes

    # This is explicitly a comparison digest, never an address usable in CAS.
    return "semantic:sha256:" + hashlib.sha256(
        to_canonical_bytes(body, spec=CanonSpec(forbid_floats=False))
    ).hexdigest()


def _project_recorded_progress(
    progress: dict[str, Any], *, run_id: str, boundary: str, projected: str,
) -> dict[str, Any]:
    """Project the complete content-bound quantity, including repeated identities."""

    result = _replace_bound_values(progress, {run_id: "{run_id}", boundary: projected})
    if "production_loop_run_proof" not in result:
        return result
    loop = result["production_loop_run_proof"]
    for key, replacement in (
        ("job_id", "{job_id}"), ("http_request_id", "control-job:{job_id}"),
        ("enqueued_at", "{observed_utc}"), ("worker_id", "{worker_id}"),
        ("worker_lease_id", "{worker_id}"),
        ("_execute_workflow_invocation_id", "{execute_workflow_invocation_id}"),
        ("workspace_loop_invocation_id", "{workspace_loop_invocation_id}"),
    ):
        loop[key] = replacement
    replacements = {
        ref: _semantic_record_digest(body)
        for ref, (body, _, _) in zip(loop["output_cas_refs"], _progress_output_bodies(result), strict=True)
    }
    result = _replace_bound_values(result, replacements)
    return _replace_bound_values(result, {
        result["production_loop_run_proof_ref"]:
        _semantic_record_digest(result["production_loop_run_proof"]),
    })


def comparison_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Compare all outcome fields, projecting checked operational coordinates only.

    Raw run records remain in v2 and the deciding check output. There is no
    recursive key/prefix stripping: unknown and newly introduced fields survive.
    """
    from polisyos.runtime.quality.authority import AuthoritySurfaceDecision

    result = copy.deepcopy(payload)
    for proof in result["proofs"]:
        _validate_recorded_proof(proof)
        job_id = proof["job_id"]
        run_id = proof["run_id"]
        boundary = proof["authority_boundary_ref"]
        projected_boundary = boundary.removesuffix(job_id) + "{job_id}"
        progress_ref = proof["progress_artifact_ref"]
        proof["run_id"], proof["job_id"] = "{run_id}", "{job_id}"
        for key in ("enqueued_at", "started_at", "finished_at"):
            proof[key] = "{observed_utc}"
        proof["worker_id"] = "{worker_id}"
        claim = proof["worker_claim"]
        claim["event_id"], claim["created_at"] = "{running_event_id}", "{observed_utc}"
        for key, replacement in (
            ("job_id", "{job_id}"),
            ("run_id", "{run_id}"),
            ("lease_owner", "{worker_id}"),
            ("lease_expires_at", "{observed_utc}"),
        ):
            claim["payload"][key] = replacement
        request = proof["request_payload"]
        request["run_id"] = request["state_payload"]["run_id"] = "{run_id}"
        trace = request["_telemetry"]["runtime_trace"]
        for key, pattern in (
            ("trace_id", r"trace_[0-9a-f]{32}"),
            ("span_id", r"span_[0-9a-f]{16}"),
        ):
            if not isinstance(trace[key], str) or re.fullmatch(pattern, trace[key]) is None:
                raise ValueError("workflow_trace_coordinate_invalid")
            trace[key] = "{" + key + "}"
        proof["request_artifact_ref"] = "{content_checked_request_ref}"
        proof["progress_artifact_ref"] = "{content_checked_progress_ref}"
        proof["authority_boundary_ref"] = projected_boundary
        proof["progress_payload"] = _project_recorded_progress(
            proof["progress_payload"], run_id=run_id, boundary=boundary, projected=projected_boundary,
        )

        def project_decisions(
            item: Any, boundary: str = boundary, projected_boundary: str = projected_boundary
        ) -> None:
            if isinstance(item, dict):
                if "decision" in item:
                    decision = AuthoritySurfaceDecision.model_validate(item["decision"])
                    if decision.authority_boundary_ref != boundary:
                        raise ValueError("workflow_surface_boundary_mismatch")
                    item["decision"]["authority_boundary_ref"] = projected_boundary
                for key, child in item.items():
                    if key != "decision":
                        project_decisions(child)
            elif isinstance(item, list):
                for child in item:
                    project_decisions(child)

        for readback in proof["surface_readbacks"]:
            project_decisions(readback)
            if readback["surface"] in {"artifact", "lineage", "export", "dashboard"}:
                if readback["read_method"].count(progress_ref) != 1:
                    raise ValueError("workflow_surface_route_binding_mismatch")
                if (
                    readback["read_method"].split(" ", 1)[1]
                    != readback["response_artifact_ref_or_route"]
                ):
                    raise ValueError("workflow_surface_response_route_binding_mismatch")
                readback["response_artifact_ref_or_route"] = readback[
                    "response_artifact_ref_or_route"
                ].replace(progress_ref, "{progress_artifact_ref}")
                readback["read_method"] = readback["read_method"].replace(
                    progress_ref, "{progress_artifact_ref}"
                )
        execution = proof["workflow_execution"]
        if execution is not None:
            execution["workflow_report_ref"] = "{content_checked_workflow_report_ref}"
            report = execution["workflow_report"]
            report["run_id"] = "{run_id}"
            for row in report["nodes"]:
                row["duration_ms"] = "{elapsed_ms}"
                if row["skip_blocker"] is not None:
                    row["skip_blocker"]["generated_at"] = "{observed_utc}"
    return result


def _canonical_proof_strangle_receipt() -> dict[str, Any]:
    return {
        "predecessor_ref": "check_layer3_workflow_failure_authority.v1.nl_request_and_authored_clock",
        "replacement_ref": "check_layer3_workflow_failure_authority.v2.durable_workflow_report_readback",
        "disposition": "fenced_default_flipped",
        "default_before": "model-less NL request and deterministic clock/IDs without workflow report readback",
        "default_after": "real durable discovery workflow, emitted coordinates and complete persisted report reconciliation",
        "guard_ref": "tests/repo_quality/architecture/test_layer3_gy_artifact_lifecycle.py::test_layer3_workflow_failure_authority_refuses_removed_execution",
        "remaining_callers": [],
        "remaining_callers_disposition": "v1 bytes are immutable historical evidence; no current execution path",
        "removed_loc": "check_layer3_workflow_failure_authority::_deterministic_uuid_sequence,_production_loop_fields",
        "verified_by": [
            ".venv/bin/python -m tools.quality.validation.check_layer3_workflow_failure_authority --check --output-format json"
        ],
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
            "decision": authority_surface_decision(progress, surface="run").model_dump(mode="json"),
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
                client.post(path, **kwargs) if method == "POST" else client.get(path, **kwargs)
            )
            body = response.json()
            if (
                response.status_code != 409
                or body.get("code") != "authority_surface_admission_blocked"
                or body.get("artifact_ref_or_route") != path
            ):
                raise ValueError("workflow_http_authority_response_invalid")
            decision = _validated_surface_decision(body["authority_surface_decision"])
            if decision["surface"] != surface:
                raise ValueError("workflow_http_authority_surface_mismatch")
            readbacks.append(
                {
                    "surface": surface,
                    "read_method": f"{method} {path}",
                    "status_code": response.status_code,
                    "response_code": body["code"],
                    "response_artifact_ref_or_route": body["artifact_ref_or_route"],
                    "decision": decision,
                }
            )

    public_packet_readback: dict[str, Any]
    try:
        bundle = build_public_export_bundle(
            run_id=str(terminal_job["run_id"]),
            artifacts={"progress": progress},
            generated_at=datetime.now(UTC),
        )
    except PublicExportRedactionError as exc:
        if exc.code != "authority_surface_blocked":
            raise ValueError("workflow_public_authority_response_invalid") from exc
        decisions = _validated_public_decisions(exc.authority_surface_decisions)
        public_packet_readback = {
            "surface": "public_packet",
            "read_method": "build_public_export_bundle",
            "blocked_or_downgraded": True,
            "error_code": exc.code,
            "decisions": decisions,
        }
    else:
        decisions = _validated_public_decisions(
            bundle["semantic_audit"]["authority_surface_decisions"]
        )
        public_packet_readback = {
            "surface": "public_packet",
            "read_method": "build_public_export_bundle",
            "blocked_or_downgraded": True,
            "decisions": decisions,
        }
    readbacks.append(public_packet_readback)
    return readbacks


def _validated_surface_decision(value: Any) -> dict[str, Any]:
    from polisyos.runtime.quality.authority import AuthoritySurfaceDecision

    result = AuthoritySurfaceDecision.model_validate(value).model_dump(mode="json")
    if result != value:
        raise ValueError("workflow_surface_decision_raw_shape_invalid")
    return result


def _validated_public_decisions(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list) or not value:
        raise ValueError("workflow_public_authority_response_invalid")
    public_count = 0
    for item in value:
        if not isinstance(item, dict) or item.get("artifact_key") != "progress":
            raise ValueError("workflow_public_authority_response_invalid")
        decision = _validated_surface_decision(item["decision"])
        if not decision["consumed_authority_boundary"] or not (
            decision["blocking"] or decision["visible_downgrade"]
        ):
            raise ValueError("workflow_public_authority_response_invalid")
        public_count += decision["surface"] == "public_packet"
    if public_count != 1:
        raise ValueError("workflow_public_authority_response_invalid")
    return copy.deepcopy(value)


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
        "remaining_callers_disposition": ("all callers pass through store-level fail-closed guard"),
        "removed_loc": "src/polisyos/runtime/http/services/control_plane_store.py::complete_job",
        "verified_by": [
            "tools/quality/validation/check_layer3_workflow_failure_authority.py "
            "--check --repo-root .",
        ],
    }


def _claim_route_fixture_owner(store: Any, *artifact_ids: Any) -> None:
    from polisyos.core.artifacts.manifest import ArtifactRef
    from polisyos.core.registry import build_default_registry_bundle
    from polisyos.core.run.context import RunContext

    # The render route resolves ownership from finalized run manifests as well
    # as CAS ownership. This run captures the readback artifacts; it does not
    # replace or relabel the workflow execution that produced their contents.
    capture = RunContext.start(
        store,
        registry_bundle=build_default_registry_bundle(store).bundle_ref,
        tenant_id=FIXTURE_TENANT_ID,
        cell_id=FIXTURE_CELL_ID,
    )
    for artifact_id in artifact_ids:
        manifest = store.get_manifest(artifact_id)
        capture.add_output(
            ArtifactRef(
                artifact_id=manifest.artifact_id,
                kind=manifest.kind,
                media_type=manifest.media_type,
            )
        )
    capture.finalize()


def _validate_generated_artifacts_registration(
    repo_root: Path,
    issues: list[dict[str, str]],
) -> None:
    try:
        generated = tomllib.loads(
            (repo_root / "architecture/generated_artifacts.toml").read_text(encoding="utf-8")
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
    if (
        set(family.get("outputs") or []) != {PROOF_PATH}
        or family.get("lifecycle") != "generated_committed"
    ):
        issues.append({"code": "workflow_failure_authority_output_not_registered"})
    history = families.get(HISTORY_FAMILY_ID)
    if (
        not history
        or history.get("lifecycle") != "source_committed"
        or set(history.get("outputs") or []) != {HISTORICAL_PROOF_PATH}
        or history.get("source_integrity_sha256")
        != {HISTORICAL_PROOF_PATH: "sha256:" + HISTORICAL_PROOF_SHA256}
    ):
        issues.append({"code": "workflow_failure_authority_history_partition_invalid"})
    if "--check" not in list(family.get("check_command") or []):
        issues.append({"code": "workflow_failure_authority_check_mode_missing"})
    regenerate_commands = " ".join(family.get("regenerate_commands") or [])
    if "--write" not in regenerate_commands:
        issues.append({"code": "workflow_failure_authority_write_mode_missing"})


def _validate_proof_payload(payload: dict[str, Any], issues: list[dict[str, str]]) -> None:
    if payload.get("schema_version") != SCHEMA_VERSION:
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
            _validate_recorded_proof(raw_proof)
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
        if not set(SURFACE_NAMES).issubset(proof.surface_reads_checked):
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
    if surface == "public_packet":
        try:
            if "error_code" in readback and readback["error_code"] != "authority_surface_blocked":
                raise ValueError("workflow_public_authority_response_invalid")
            _validated_public_decisions(readback["decisions"])
        except (KeyError, TypeError, ValueError):
            issues.append(
                {"code": "workflow_public_authority_response_invalid", "scenario": scenario}
            )
        return
    if surface in {"artifact", "lineage", "export", "dashboard"} and (
        readback.get("response_code") != "authority_surface_admission_blocked"
        or not readback.get("response_artifact_ref_or_route")
    ):
        issues.append(
            {
                "code": "workflow_http_authority_response_invalid",
                "scenario": scenario,
                "surface": surface,
            }
        )
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
    try:
        _validated_surface_decision(decision)
    except (TypeError, ValueError):
        issues.append(
            {"code": "workflow_surface_decision_invalid", "scenario": scenario, "surface": surface}
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
