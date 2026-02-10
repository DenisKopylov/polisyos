from __future__ import annotations

from pathlib import Path

import pytest

try:  # pragma: no cover - optional dependency guard
    from fastapi.testclient import TestClient
except ModuleNotFoundError:  # pragma: no cover
    TestClient = None  # type: ignore[assignment]

from polisyos.core.artifacts.manifest import InputRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.run.context import RunContext
from polisyos.runtime.http.app import create_runtime_api_app


def _put_json(store: FileSystemCAS, payload, *, kind: str, inputs: list[InputRef] | None = None):
    return store.put_json(
        payload,
        PutOptions(
            kind=kind,
            media_type="application/json",
            schema=SchemaInfo(name=kind, version="1.0"),
            inputs=inputs,
        ),
    )


@pytest.fixture
def runtime_api_env(tmp_path: Path):
    if TestClient is None:  # pragma: no cover
        pytest.skip("fastapi is not installed")

    tenant_a = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    tenant_b = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"

    cas_root = tmp_path / ".polisyos"
    store = FileSystemCAS(cas_root)

    child_ref = _put_json(store, {"child": 1}, kind="test.child")
    root_ref = _put_json(
        store,
        {"root": True},
        kind="test.root",
        inputs=[InputRef(artifact_id=child_ref.artifact_id, role="child")],
    )
    binary_ref = store.put_bytes(
        b"x" * 5000,
        PutOptions(kind="test.binary", media_type="application/octet-stream"),
    )
    secret_ref = _put_json(
        store,
        {"token": "do-not-expose"},
        kind="security.secret_bundle",
    )

    core_run_id = "R_core_api_001"
    registry_ref = _put_json(store, {"registry": {}}, kind="core.registry_bundle")
    governance_ref = _put_json(
        store,
        {
            "schema_version": "1.0",
            "verdict": "reject",
            "issues": [{"code": "GOV001", "message": "Policy blocker"}],
            "notes": ["manual review required"],
        },
        kind="scientist.governance_report",
    )
    decision_packet_ref = _put_json(
        store,
        {
            "schema_version": "3.1",
            "run_id": core_run_id,
            "governance": {
                "verdict": "reject",
                "issues": [{"code": "GOV001", "message": "Policy blocker"}],
                "notes": ["fallback-governance"],
            },
        },
        kind="scientist.decision_packet",
    )
    experiment_state_ref = _put_json(
        store,
        {
            "schema_version": "1.1",
            "run_id": core_run_id,
            "inputs": {},
            "artifacts_index": {
                "decision_packet_ref": decision_packet_ref.model_dump(mode="json"),
            },
            "reports_index": {
                "governance_report_ref": governance_ref.model_dump(mode="json"),
            },
            "params": {"validation_trace": {"total_issues": 1, "total_blockers": 1}},
            "budgets": {},
        },
        kind="scientist.experiment_state",
    )
    workflow_report_ref = _put_json(
        store,
        {
            "schema_version": "1.0",
            "workflow_id": "scientist_default",
            "run_id": core_run_id,
            "error_policy": "fail_fast",
            "status": "fail",
            "nodes": [
                {
                    "alias": "compile_foundry",
                    "node_id": "scientist.node_compile_foundry@1.0.0",
                    "status": "ok",
                    "duration_ms": 11,
                    "artifacts": [experiment_state_ref.model_dump(mode="json")],
                },
                {
                    "alias": "run_governance",
                    "node_id": "scientist.node_run_governance@1.1.0",
                    "status": "fail",
                    "duration_ms": 7,
                    "artifacts": [governance_ref.model_dump(mode="json")],
                    "error": {
                        "code": "governance.blocked",
                        "message": "Blocked by policy",
                        "details": {
                            "severity": "blocker",
                            "api_token": "Bearer should-not-leak",
                        },
                    },
                },
            ],
        },
        kind="scientist.workflow_report",
    )

    run = RunContext.start(
        store=store,
        registry_bundle=registry_ref,
        run_id=core_run_id,
        tenant_id=tenant_a,
        cell_id="cell-a",
    )
    run.emit(
        "scientist.node.compile_foundry",
        "NODE_OK",
        outputs=[experiment_state_ref],
        metrics={"duration_ms": 11, "status_ok": 1, "cache_hit": 1},
    )
    run.emit(
        "scientist.node.run_governance",
        "NODE_FAIL",
        outputs=[governance_ref],
        metrics={"duration_ms": 7, "status_ok": 0, "cache_bypass": 1},
    )
    run.add_output(experiment_state_ref)
    run.add_output(workflow_report_ref)
    run.add_output(decision_packet_ref)
    run.finalize(
        status="fail",
        errors=[{"code": "run.failed", "message": "workflow execution failed"}],
    )

    core_run_id_secondary = "R_core_api_002"
    second_run = RunContext.start(
        store=store,
        registry_bundle=registry_ref,
        run_id=core_run_id_secondary,
        tenant_id=tenant_a,
        cell_id="cell-a",
    )
    second_run.emit(
        "scientist.node.compile_foundry",
        "NODE_OK",
        metrics={"duration_ms": 3, "status_ok": 1},
    )
    second_run.finalize(status="completed")

    app = create_runtime_api_app(
        cas_root=cas_root,
        core_runs_root=cas_root / "runs",
        enable_security_middlewares=False,
    )
    client = TestClient(app)

    return {
        "client": client,
        "cas_root": cas_root,
        "core_run_id": core_run_id,
        "core_run_id_secondary": core_run_id_secondary,
        "root_artifact_id": str(root_ref.artifact_id),
        "child_artifact_id": str(child_ref.artifact_id),
        "binary_artifact_id": str(binary_ref.artifact_id),
        "secret_artifact_id": str(secret_ref.artifact_id),
        "governance_artifact_id": str(governance_ref.artifact_id),
        "decision_packet_artifact_id": str(decision_packet_ref.artifact_id),
        "experiment_state_artifact_id": str(experiment_state_ref.artifact_id),
        "workflow_report_artifact_id": str(workflow_report_ref.artifact_id),
        "tenant_a": tenant_a,
        "tenant_b": tenant_b,
    }
