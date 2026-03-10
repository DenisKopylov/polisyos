from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

try:  # pragma: no cover - optional dependency guard
    from fastapi.testclient import TestClient
except ModuleNotFoundError:  # pragma: no cover
    TestClient = None  # type: ignore[assignment]

from polisyos.core.artifacts.manifest import InputRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.contracts.control import PromotionCandidate
from polisyos.core.run.context import RunContext
from polisyos.runtime.http.app import create_runtime_api_app
from polisyos.runtime.http.services.control import ControlPlaneService


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


def build_runtime_api_env(tmp_path: Path, *, include_test_client: bool = True):
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
            "issues": [{"code": "GOV001", "message": "Policy blocker", "severity": "blocker"}],
            "notes": ["manual review required"],
            "links": {},
        },
        kind="scientist.governance_report",
    )
    evidence_bundle_ref = _put_json(
        store,
        {
            "schema_version": "1.0",
            "sources": [{"title": "World Bank GDP", "source_id": "wb.gdp"}],
            "notes": ["fixture evidence bundle"],
        },
        kind="fabric.evidence_bundle",
    )
    quality_ref = _put_json(
        store,
        {
            "quality_score": "0.82",
            "status": "warn",
            "metrics": {"coverage": "0.74", "completeness": "0.81"},
            "gates": {"status": "review_required"},
            "violations": [{"severity": "warning", "code": "coverage_gap"}],
        },
        kind="fabric.quality_report",
    )
    legal_ref = _put_json(
        store,
        {
            "status": "blocked",
            "verdict": "reject",
            "jurisdiction": "US",
            "issues": [{"code": "LEGAL001", "message": "Statutory conflict"}],
            "issue_summary": {"blocker_count": 1},
            "links": {"quality_report_ref": quality_ref.model_dump(mode="json")},
            "recommendations": ["Escalate to legal review"],
        },
        kind="lex.legal_report",
    )
    execution_plan_ref = _put_json(
        store,
        {
            "schema_version": "1.0",
            "plan_id": "plan_fixture_001",
            "run_id": core_run_id,
            "iteration": 1,
            "data_needs": [
                {
                    "metric": "macro.gdp.real",
                    "geography": "USA",
                    "time_start": "2019",
                    "time_end": "2024",
                    "granularity": "annual",
                    "quality_min": "0.75",
                    "purpose": "policy_drafting",
                }
            ],
            "method_dag": [],
            "method_edges": [],
            "params": {"operator_intent": "Assess macro outlook"},
            "budgets": {"max_iterations": 2},
            "stop_criteria": {"max_no_delta_iterations": 1},
            "governance_constraints": [],
            "expected_outputs": [],
            "notes": ["fixture execution plan"],
        },
        kind="scientist.execution_plan",
    )
    preflight_ref = _put_json(
        store,
        {
            "schema_version": "1.0",
            "ready_to_run": False,
            "diagnostics": [
                {
                    "code": "MISSING_BINDING",
                    "severity": "error",
                    "message": "Bindings require review",
                    "path": ["inputs", "input_bindings_ref"],
                    "replanning_hints": ["Refresh bindings before execution"],
                }
            ],
            "notes": ["fixture preflight"],
        },
        kind="scientist.preflight_report",
    )
    evaluator_ref = _put_json(
        store,
        {
            "schema_version": "1.0",
                "verdict": "REPLAN_DATA",
                "scores": {
                "kpi_score": "0.71",
                "uncertainty_score": "0.52",
                "constraints_score": "0.64",
                "data_quality_score": "0.58",
                "budget_score": "0.93",
                "total_score": "0.67",
            },
            "reasons": ["Coverage below threshold"],
            "replanning_hints": ["Resolve fresher macro data"],
        },
        kind="scientist.evaluator_report",
    )
    reproducibility_ref = _put_json(
        store,
        {
            "schema_version": "1.0",
            "seed": 42,
            "plan_hash": "plan_hash_fixture",
            "registry_hash": "registry_hash_fixture",
            "method_catalog_hash": "catalog_hash_fixture",
            "data_snapshot_hash": "snapshot_hash_fixture",
            "input_bindings_hash": "bindings_hash_fixture",
            "notes": ["fixture reproducibility manifest"],
        },
        kind="scientist.reproducibility_manifest",
    )
    data_snapshot_ref = _put_json(
        store,
        {
            "data_ref": str(evidence_bundle_ref.artifact_id),
            "quality_report_ref": quality_ref.model_dump(mode="json"),
            "stats": {"metric_count": 1, "metadata_docs_fetched": 18},
            "notes": ["fixture data snapshot"],
        },
        kind="fabric.data_snapshot",
    )
    input_bindings_ref = _put_json(
        store,
        {
            "data_snapshot_ref": str(data_snapshot_ref.artifact_id),
            "registry_bundle_ref": str(registry_ref.artifact_id),
            "rules": [{"name": "macro.default"}],
            "notes": ["fixture input bindings"],
        },
        kind="foundry.input_bindings",
    )
    decision_card_ref = _put_json(
        store,
        {
            "schema_version": "1.0",
            "headline": "Replan data sourcing",
            "summary": "Macro evidence is incomplete.",
            "recommended_action": "Refresh evidence before recommendation.",
        },
        kind="scientist.decision_card",
    )
    governance_json = {
        "schema_version": "1.0",
        "verdict": "reject",
        "issues": [{"code": "GOV001", "message": "Policy blocker", "severity": "blocker"}],
        "notes": ["manual review required"],
        "links": {
            "legal_report_ref": legal_ref.model_dump(mode="json"),
            "quality_report_ref": quality_ref.model_dump(mode="json"),
        },
    }
    governance_ref = _put_json(store, governance_json, kind="scientist.governance_report")
    decision_packet_ref = _put_json(
        store,
        {
            "schema_version": "3.1",
            "run_id": core_run_id,
            "inputs": {
                "data_snapshot_ref": str(data_snapshot_ref.artifact_id),
                "input_bindings_ref": str(input_bindings_ref.artifact_id),
                "evidence_bundle_ref": str(evidence_bundle_ref.artifact_id),
            },
            "artifacts": {
                "decision_card_ref": str(decision_card_ref.artifact_id),
                "execution_plan_ref": str(execution_plan_ref.artifact_id),
            },
            "governance": {
                "verdict": "reject",
                "issues": [{"code": "GOV001", "message": "Policy blocker", "severity": "blocker"}],
                "notes": ["fallback-governance"],
            },
            "causal": {
                "transportability_summary": {
                    "status": "blocked",
                    "assumptions": ["parallel trends not established"],
                    "portability_blockers": ["missing external validation set"],
                    "trace": {"source": "fixture"},
                }
            },
            "diagnostics_summary": {
                "legal_executed": True,
                "contract_warnings": ["norm_pack_ref_missing"],
            },
            "audit_trail": [
                {
                    "timestamp": "2026-02-11T12:00:00Z",
                    "node": "pi_decompose",
                    "action": "problem_frame_created",
                    "details": {"summary": "Problem framed", "attempt": 1},
                },
                {
                    "timestamp": "2026-02-11T12:00:01Z",
                    "node": "drafter",
                    "action": "draft_created",
                    "details": {"summary": "Draft policy prepared", "attempt": 1},
                },
                {
                    "timestamp": "2026-02-11T12:00:02Z",
                    "node": "formalize",
                    "action": "ir_generated",
                    "details": {"summary": "Trinity bundle assembled", "attempt": 1},
                },
                {
                    "timestamp": "2026-02-11T12:00:03Z",
                    "node": "critic_review",
                    "action": "critique_complete",
                    "details": {"verdict": "NEEDS_REVISION", "attempt": 1},
                },
                {
                    "timestamp": "2026-02-11T12:00:04Z",
                    "node": "reflexion",
                    "action": "abort_with_report",
                    "details": {"attempt": 1, "can_retry": False},
                },
            ],
        },
        kind="scientist.decision_packet",
    )
    reflexion_terminal_ref = _put_json(
        store,
        {
            "decision": "abort_with_report",
            "card": {
                "attempt_number": 1,
                "created_at": "2026-02-11T12:00:04Z",
                "violation_summary": "NEEDS_REVISION",
            },
            "failure_history": [
                {
                    "artifact_type": "failure_card",
                    "attempt_number": 1,
                    "error_code": "CRITIC_REJECTION",
                }
            ],
        },
        kind="scientist.reflexion_terminal",
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
            "params": {
                "validation_trace": {"total_issues": 1, "total_blockers": 1},
                "retrieval_mode": "hybrid",
                "retrieval_lane_used": "explorelane",
                "retrieval_telemetry": {
                    "mode": "hybrid",
                    "lane_used": "explorelane",
                    "metadata_docs_fetched": 18,
                    "local_index_size_bytes": 4096,
                    "local_index_docs_total": 12,
                    "candidates_filtered": 2,
                    "candidates_promoted": 1,
                    "phases": [
                        {
                            "phase": "resolve_fast_lane",
                            "lane": "fastlane",
                            "duration_ms": 9,
                            "candidates_total": 1,
                            "candidates_selected": 0,
                            "docs_fetched": 0,
                        },
                        {
                            "phase": "discover_explore_lane",
                            "lane": "explorelane",
                            "duration_ms": 22,
                            "candidates_total": 3,
                            "candidates_selected": 1,
                            "docs_fetched": 18,
                        },
                    ],
                    "warnings": ["quality_review_required"],
                },
                "execution_plan_ref": str(execution_plan_ref.artifact_id),
                "preflight_report_ref": str(preflight_ref.artifact_id),
                "evaluator_report_ref": str(evaluator_ref.artifact_id),
                "reproducibility_manifest_ref": str(reproducibility_ref.artifact_id),
                "retrieval_context": {
                    "data_needs": [
                        {
                            "metric": "macro.gdp.real",
                            "geography": "USA",
                            "time_start": "2019",
                            "time_end": "2024",
                            "granularity": "annual",
                            "quality_min": "0.75",
                            "purpose": "policy_drafting",
                        }
                    ],
                    "fetch_plans": [
                        {
                            "plan_id": "plan_fixture_fetch_001",
                            "metric_id": "macro.gdp.real",
                            "connector_id": "worldbank.wdi",
                            "dataset_id": "NY.GDP.MKTP.KD",
                            "profile_id": "worldbank_wdi",
                            "filters": {"country": ["USA"]},
                            "date_start": "2019",
                            "date_end": "2024",
                            "granularity": "annual",
                            "quality_min": "0.75",
                            "source_lane": "explorelane",
                            "fallbacks": [],
                        }
                    ],
                    "promotion_candidates": [
                        {
                            "promotion_id": "promotion_fixture_001",
                            "metric_id": "macro.gdp.real",
                            "connector_id": "worldbank.wdi",
                            "dataset_id": "NY.GDP.MKTP.KD",
                            "profile_id": "worldbank_wdi",
                            "source_lane": "explorelane",
                            "confidence": "0.87",
                            "status": "pending",
                            "signals": ["new_source", "coverage_gap_closed"],
                            "metadata": {"profile": "worldbank_wdi"},
                        }
                    ],
                    "auto_data_source_refs": {
                        "data_snapshot_ref": str(data_snapshot_ref.artifact_id),
                        "input_bindings_ref": str(input_bindings_ref.artifact_id),
                        "evidence_bundle_ref": str(evidence_bundle_ref.artifact_id),
                    },
                },
            },
            "budgets": {},
            "execution_plan_ref": execution_plan_ref.model_dump(mode="json"),
            "preflight_report_ref": preflight_ref.model_dump(mode="json"),
            "evaluator_report_ref": evaluator_ref.model_dump(mode="json"),
            "reproducibility_manifest_ref": reproducibility_ref.model_dump(mode="json"),
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
    workflow_spec_ref = _put_json(
        store,
        {
            "schema_version": "1.0",
            "workflow_id": "scientist_default",
            "error_policy": "fail_fast",
            "nodes": [
                {
                    "alias": "compile_foundry",
                    "node_id": "scientist.node_compile_foundry@1.0.0",
                    "depends_on": [],
                    "params": {},
                },
                {
                    "alias": "run_governance",
                    "node_id": "scientist.node_run_governance@1.1.0",
                    "depends_on": ["compile_foundry"],
                    "params": {},
                },
            ],
            "required_binds": [],
            "notes": [],
        },
        kind="scientist.workflow_spec",
    )

    run = RunContext.start(
        store=store,
        registry_bundle=registry_ref,
        run_id=core_run_id,
        tenant_id=tenant_a,
        cell_id="cell-a",
    )
    run.add_input(workflow_spec_ref)
    run.add_input(data_snapshot_ref)
    run.add_input(input_bindings_ref)
    run.add_input(evidence_bundle_ref)
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
    run.add_output(decision_card_ref)
    run.add_output(execution_plan_ref)
    run.add_output(preflight_ref)
    run.add_output(evaluator_ref)
    run.add_output(reproducibility_ref)
    run.add_output(quality_ref)
    run.add_output(legal_ref)
    run.add_output(reflexion_terminal_ref)
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
    control_service = ControlPlaneService(
        cas_root=cas_root,
        core_runs_root=cas_root / "runs",
    )
    control_service._retrieval._promotion_queue["promotion_fixture_001"] = PromotionCandidate(
        promotion_id="promotion_fixture_001",
        metric_id="macro.gdp.real",
        connector_id="worldbank.wdi",
        dataset_id="NY.GDP.MKTP.KD",
        profile_id="worldbank_wdi",
        source_lane="explorelane",
        confidence=0.87,
        status="pending",
        created_at=datetime.fromisoformat("2026-02-11T12:00:00+00:00"),
        signals=["new_source", "coverage_gap_closed"],
        metadata={
            "profile": "worldbank_wdi",
            "run_id": core_run_id,
        },
    )
    app.state._control_service = control_service
    client = TestClient(app) if include_test_client and TestClient is not None else None

    return {
        "app": app,
        "client": client,
        "cas_root": cas_root,
        "core_run_id": core_run_id,
        "core_run_id_secondary": core_run_id_secondary,
        "root_artifact_id": str(root_ref.artifact_id),
        "child_artifact_id": str(child_ref.artifact_id),
        "binary_artifact_id": str(binary_ref.artifact_id),
        "secret_artifact_id": str(secret_ref.artifact_id),
        "governance_artifact_id": str(governance_ref.artifact_id),
        "decision_card_artifact_id": str(decision_card_ref.artifact_id),
        "decision_packet_artifact_id": str(decision_packet_ref.artifact_id),
        "reflexion_terminal_artifact_id": str(reflexion_terminal_ref.artifact_id),
        "workflow_spec_artifact_id": str(workflow_spec_ref.artifact_id),
        "experiment_state_artifact_id": str(experiment_state_ref.artifact_id),
        "workflow_report_artifact_id": str(workflow_report_ref.artifact_id),
        "execution_plan_artifact_id": str(execution_plan_ref.artifact_id),
        "preflight_artifact_id": str(preflight_ref.artifact_id),
        "evaluator_artifact_id": str(evaluator_ref.artifact_id),
        "reproducibility_artifact_id": str(reproducibility_ref.artifact_id),
        "data_snapshot_artifact_id": str(data_snapshot_ref.artifact_id),
        "input_bindings_artifact_id": str(input_bindings_ref.artifact_id),
        "evidence_bundle_artifact_id": str(evidence_bundle_ref.artifact_id),
        "quality_artifact_id": str(quality_ref.artifact_id),
        "legal_artifact_id": str(legal_ref.artifact_id),
        "promotion_candidate_id": "promotion_fixture_001",
        "tenant_a": tenant_a,
        "tenant_b": tenant_b,
    }


@pytest.fixture
def runtime_api_env(tmp_path: Path):
    if TestClient is None:  # pragma: no cover
        pytest.skip("fastapi is not installed")

    return build_runtime_api_env(tmp_path, include_test_client=True)
