from __future__ import annotations

import json

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.ir.governance.gate import GateContext, GateVerdict
from polisyos.scientist.kernel.gate_protocol import HumanGateProtocol


def test_gate_protocol_persists_request_and_decision(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    bundle = build_default_registry_bundle(store)
    run = RunContext.start(store=store, registry_bundle=bundle.bundle_ref, run_id="R_gate")

    protocol = HumanGateProtocol(run)
    context = GateContext(
        workflow_id="scientist_default",
        node_alias="run_governance",
        phase="POSTFLIGHT_GOV",
        iteration=1,
    )
    request, request_ref = protocol.request_gate(
        run_id="R_gate",
        reason="policy requires manual approval",
        context=context,
    )
    decision, decision_ref = protocol.record_decision(
        request,
        verdict=GateVerdict.APPROVE,
        approver_id="human.ops",
        request_ref=request_ref,
    )

    request_manifest = store.get_manifest(request_ref.artifact_id)
    decision_manifest = store.get_manifest(decision_ref.artifact_id)
    assert request_manifest.kind == "ir.gate_request"
    assert decision_manifest.kind == "ir.gate_decision"
    assert decision.request_id == request.request_id

    trace_path = tmp_path / "runs" / "R_gate" / "trace.jsonl"
    events = [json.loads(line) for line in trace_path.read_text("utf-8").splitlines() if line]
    event_names = [event["event"] for event in events]
    assert "GATE_REQUESTED" in event_names
    assert "GATE_DECIDED" in event_names


def test_gate_request_id_is_deterministic_for_same_context(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    bundle = build_default_registry_bundle(store)
    run = RunContext.start(store=store, registry_bundle=bundle.bundle_ref, run_id="R_gate_det")

    protocol = HumanGateProtocol(run)
    context = GateContext(
        workflow_id="scientist_default",
        node_alias="run_governance",
        phase="POSTFLIGHT_GOV",
        iteration=1,
    )

    request_a, _ = protocol.request_gate(
        run_id="R_gate_det",
        reason="manual review required",
        context=context,
    )
    request_b, _ = protocol.request_gate(
        run_id="R_gate_det",
        reason="manual review required",
        context=context,
    )
    assert request_a.request_id == request_b.request_id
