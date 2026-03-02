from __future__ import annotations

import json
import logging

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.ir.analytics.causal import (
    CausalEffectReport,
    CausalMethod,
    EstimationStatus,
    persist_causal_effect_report,
)
from polisyos.ir.analytics.causal_graph import (
    CausalEdge,
    CausalGraphModel,
    EdgeSource,
    GraphType,
    persist_causal_graph_model,
)
from polisyos.scientist.engine.context import ExecutionContext
from polisyos.scientist.engine.state import ExperimentState
from polisyos.scientist.governance.preflight import build_default_pipeline
from polisyos.scientist.nodes.builtins.causal.resolve_transport import RunTransportabilityNode
from polisyos.scientist.nodes.builtins.governance.run_governance import RunGovernanceNode
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_CAUSAL_REPORT_REF,
    ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF,
    INPUT_REGISTRY_BUNDLE_REF,
    REPORT_GOVERNANCE_REPORT_REF,
)


def _load_verdict(store: FileSystemCAS, state: ExperimentState) -> str:
    report_ref = state.reports_index[REPORT_GOVERNANCE_REPORT_REF]
    payload = from_canonical_bytes(store.get_bytes(report_ref.artifact_id))
    return str(payload["verdict"])


def _load_report_payload(store: FileSystemCAS, state: ExperimentState) -> dict:
    report_ref = state.reports_index[REPORT_GOVERNANCE_REPORT_REF]
    payload = from_canonical_bytes(store.get_bytes(report_ref.artifact_id))
    return dict(payload)


def test_run_governance_emits_gate_request_and_decision_audit(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    bundle = build_default_registry_bundle(store)
    run = RunContext.start(store=store, registry_bundle=bundle.bundle_ref, run_id="R_gate_audit")
    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger("test"))

    node = RunGovernanceNode()
    state = ExperimentState(
        run_id="R_gate_audit",
        inputs={INPUT_REGISTRY_BUNDLE_REF: bundle.bundle_ref},
        params={"require_human_gate": True},
    )

    pending = node.execute(ctx, state)
    assert _load_verdict(store, pending.state) == "human_gate"
    gate_request = pending.state.params["gate_request"]
    gate_request_ref = pending.state.params["gate_request_ref"]
    assert isinstance(gate_request, dict)
    assert isinstance(gate_request_ref, str)
    assert store.get_manifest(ArtifactID.model_validate(gate_request_ref)).kind == "ir.gate_request"

    approved_state = pending.state.model_copy(deep=True)
    approved_state.params["gate_decision"] = {
        "request_id": gate_request["request_id"],
        "run_id": approved_state.run_id,
        "verdict": "approve",
        "approver_id": "ops.reviewer",
    }
    approved = node.execute(ctx, approved_state)

    assert _load_verdict(store, approved.state) == "approve"
    trace_path = tmp_path / "runs" / "R_gate_audit" / "trace.jsonl"
    trace_events = [
        json.loads(line)["event"] for line in trace_path.read_text("utf-8").splitlines()
    ]
    assert "GATE_REQUESTED" in trace_events
    assert "GATE_DECIDED" in trace_events


def test_run_governance_escalate_advances_iteration(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    bundle = build_default_registry_bundle(store)
    run = RunContext.start(store=store, registry_bundle=bundle.bundle_ref, run_id="R_gate_escalate")
    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger("test"))

    node = RunGovernanceNode()
    state = ExperimentState(
        run_id="R_gate_escalate",
        inputs={INPUT_REGISTRY_BUNDLE_REF: bundle.bundle_ref},
        params={"require_human_gate": True},
    )

    pending = node.execute(ctx, state)
    first_request = pending.state.params["gate_request"]

    escalated_state = pending.state.model_copy(deep=True)
    escalated_state.params["gate_decision"] = {
        "request_id": first_request["request_id"],
        "run_id": escalated_state.run_id,
        "verdict": "escalate",
        "approver_id": "ops.reviewer",
    }
    escalated = node.execute(ctx, escalated_state)

    second_request = escalated.state.params["gate_request"]
    assert _load_verdict(store, escalated.state) == "human_gate"
    assert second_request["context"]["iteration"] == 2
    assert second_request["priority"] == "critical"
    assert second_request["request_id"] != first_request["request_id"]


def test_run_governance_strict_literature_blocker_rejects_and_requests_review(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    bundle = build_default_registry_bundle(store)
    run = RunContext.start(
        store=store,
        registry_bundle=bundle.bundle_ref,
        run_id="R_gate_literature",
    )
    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger("test"))

    graph_ref = persist_causal_graph_model(
        store,
        CausalGraphModel(
            graph_type=GraphType.DAG,
            nodes=["tax_rate", "gdp_growth"],
            edges=[
                CausalEdge(
                    src="tax_rate",
                    dst="gdp_growth",
                    sources=[EdgeSource.LLM_PRIOR],
                    unsupported_by_evidence=True,
                )
            ],
            discovery_method="unit_test",
        ),
    )

    node = RunGovernanceNode()
    state = ExperimentState(
        run_id="R_gate_literature",
        inputs={INPUT_REGISTRY_BUNDLE_REF: bundle.bundle_ref},
        artifacts_index={"causal_graph_ref": graph_ref},
        params={"governance_profile": "strict", "query_treatment": "tax_rate"},
    )

    outcome = node.execute(ctx, state)

    assert _load_verdict(store, outcome.state) == "reject"
    report_payload = _load_report_payload(store, outcome.state)
    issue_codes = {item.get("code") for item in report_payload.get("issues", [])}
    assert "LITERATURE_GATE_UNSUPPORTED_EDGE" in issue_codes
    assert "HUMAN_REVIEW_REQUESTED" in issue_codes

    review_ref = outcome.state.params.get("human_review_request_ref")
    assert isinstance(review_ref, str)
    assert store.get_manifest(ArtifactID.model_validate(review_ref)).kind == "ir.gate_request"

    trace = outcome.state.params.get("validation_trace")
    assert isinstance(trace, dict)
    spans = trace.get("spans", [])
    assert isinstance(spans, list)
    assert any(span.get("pass_id") == "literature_gate" for span in spans)

    pipeline = build_default_pipeline()
    costs: list[int] = []
    for span in spans:
        pass_id = span.get("pass_id")
        if not isinstance(pass_id, str):
            continue
        validator = pipeline.get_pass(pass_id)
        if validator is not None:
            costs.append(validator.estimated_cost_ms)
    assert costs == sorted(costs)


def test_run_governance_strict_transportability_required_rejects_external_missing_check(
    tmp_path,
) -> None:
    store = FileSystemCAS(tmp_path)
    bundle = build_default_registry_bundle(store)
    run = RunContext.start(
        store=store,
        registry_bundle=bundle.bundle_ref,
        run_id="R_gate_transport_missing",
    )
    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger("test"))

    report_ref = persist_causal_effect_report(
        store,
        CausalEffectReport(
            method=CausalMethod.SYNTHETIC_CONTROL,
            status=EstimationStatus.SUCCESS,
            estimand="ATE",
            point_estimate=0.3,
            confidence_interval=(0.1, 0.5),
            inference_method="synthetic_control",
            sample_size=120,
            n_treated=10,
            n_control=110,
            pre_periods=12,
            post_periods=4,
            method_params={"source_type": "external_literature"},
        ),
    )

    node = RunGovernanceNode()
    state = ExperimentState(
        run_id="R_gate_transport_missing",
        inputs={INPUT_REGISTRY_BUNDLE_REF: bundle.bundle_ref},
        artifacts_index={ARTIFACT_CAUSAL_REPORT_REF: report_ref},
        params={"governance_profile": "strict"},
    )

    outcome = node.execute(ctx, state)

    assert _load_verdict(store, outcome.state) == "reject"
    report_payload = _load_report_payload(store, outcome.state)
    issue_codes = {item.get("code") for item in report_payload.get("issues", [])}
    assert "TRANSPORT_REQUIRED_MISSING" in issue_codes


def test_run_governance_strict_transportability_passes_after_transport_node(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    bundle = build_default_registry_bundle(store)
    run = RunContext.start(
        store=store,
        registry_bundle=bundle.bundle_ref,
        run_id="R_gate_transport_ok",
    )
    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger("test"))

    report_ref = persist_causal_effect_report(
        store,
        CausalEffectReport(
            method=CausalMethod.SYNTHETIC_CONTROL,
            status=EstimationStatus.SUCCESS,
            estimand="ATE",
            point_estimate=0.2,
            confidence_interval=(0.0, 0.4),
            inference_method="synthetic_control",
            sample_size=100,
            n_treated=20,
            n_control=80,
            pre_periods=8,
            post_periods=4,
            method_params={
                "source_type": "external_literature",
                "treatment": "tax_rate",
                "outcome": "gdp_growth",
            },
        ),
    )
    graph_ref = persist_causal_graph_model(
        store,
        CausalGraphModel(
            graph_type=GraphType.DAG,
            nodes=["tax_rate", "gdp_growth"],
            edges=[CausalEdge(src="tax_rate", dst="gdp_growth")],
        ),
    )

    base_state = ExperimentState(
        run_id="R_gate_transport_ok",
        inputs={INPUT_REGISTRY_BUNDLE_REF: bundle.bundle_ref},
        artifacts_index={
            ARTIFACT_CAUSAL_REPORT_REF: report_ref,
            ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF: graph_ref,
        },
        params={
            "source_context": {"context_id": "DE", "income_level": "high"},
            "target_context": {"context_id": "DE", "income_level": "high"},
            "query_treatment": "tax_rate",
            "query_outcome": "gdp_growth",
            "governance_profile": "strict",
        },
    )

    transport_outcome = RunTransportabilityNode().execute(ctx, base_state)
    assert transport_outcome.status == "ok"

    governance_outcome = RunGovernanceNode().execute(ctx, transport_outcome.state)
    report_payload = _load_report_payload(store, governance_outcome.state)
    issue_codes = {item.get("code") for item in report_payload.get("issues", [])}
    assert "TRANSPORT_REQUIRED_MISSING" not in issue_codes
    assert _load_verdict(store, governance_outcome.state) == "approve"
