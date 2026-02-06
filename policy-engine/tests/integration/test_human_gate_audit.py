from __future__ import annotations

import json
import logging

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.scientist.engine.context import ExecutionContext
from polisyos.scientist.engine.state import ExperimentState
from polisyos.scientist.nodes.builtins.governance.run_governance import RunGovernanceNode
from polisyos.scientist.nodes.builtins.state_keys import (
    INPUT_REGISTRY_BUNDLE_REF,
    REPORT_GOVERNANCE_REPORT_REF,
)


def _load_verdict(store: FileSystemCAS, state: ExperimentState) -> str:
    report_ref = state.reports_index[REPORT_GOVERNANCE_REPORT_REF]
    payload = from_canonical_bytes(store.get_bytes(report_ref.artifact_id))
    return str(payload["verdict"])


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
    trace_events = [json.loads(line)["event"] for line in trace_path.read_text("utf-8").splitlines()]
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
