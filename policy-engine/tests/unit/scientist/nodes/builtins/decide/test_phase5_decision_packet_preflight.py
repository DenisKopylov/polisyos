from __future__ import annotations

import logging

from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.contracts.foundry import Metrics
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.governance.report import GovernanceReport
from polisyos.scientist.nodes.builtins.decide.build_decision_packet import BuildDecisionPacketNode
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_DECISION_PACKET_REF,
    ARTIFACT_JUDGE_VERDICT_REF,
    ARTIFACT_METRICS_REF,
    ARTIFACT_VALIDATION_REPORT_REF,
    INPUT_DATA_SNAPSHOT_REF,
    INPUT_REGISTRY_BUNDLE_REF,
    INPUT_TRINITY_BUNDLE_REF,
    REPORT_GOVERNANCE_REPORT_REF,
)


def _passing_judge_verdict() -> dict[str, object]:
    return {
        "per_judge": {
            name: {"judge_name": name, "passed": True, "is_fatal": True}
            for name in (
                "structural",
                "statistical",
                "robustness",
                "governance",
                "reproducibility",
                "compute",
            )
        },
        "composite_decision": "promote",
        "blocking_failures": [],
        "warnings": [],
    }


def _context_and_state(
    tmp_path,
    *,
    params: dict[str, object] | None = None,
) -> tuple[FileSystemCAS, ExecutionContext, ExperimentState]:
    store = FileSystemCAS(tmp_path)
    registry_bundle = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(store=store, registry_bundle=registry_bundle, run_id="R_phase5_packet")
    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger("test.phase5.packet"))

    trinity_ref = store.put_json(
        {"trinity": {}},
        PutOptions(
            kind="ir.trinity_bundle",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.ir.TrinityBundle", version="1.0"),
        ),
    )
    state_snapshot_ref = store.put_json(
        {"state": {}},
        PutOptions(kind="foundry.state_snapshot", media_type="application/json"),
    )
    data_snapshot_ref = store.put_json(
        {
            "data_ref": {
                "artifact_id": str(state_snapshot_ref.artifact_id),
                "kind": "foundry.state_snapshot",
                "media_type": "application/json",
            }
        },
        PutOptions(kind="fabric.data_snapshot", media_type="application/json"),
    )
    metrics_ref = store.put_json(
        Metrics(values={"applied_nodes": 1, "status": "ok"}),
        PutOptions(kind="foundry.metrics", media_type="application/json"),
    )
    governance_ref = store.put_json(
        GovernanceReport(verdict="approve", issues=[]),
        PutOptions(kind="scientist.governance_report", media_type="application/json"),
    )

    state = ExperimentState(
        run_id="R_phase5_packet",
        inputs={
            INPUT_TRINITY_BUNDLE_REF: trinity_ref,
            INPUT_REGISTRY_BUNDLE_REF: registry_bundle,
            INPUT_DATA_SNAPSHOT_REF: data_snapshot_ref,
        },
        artifacts_index={ARTIFACT_METRICS_REF: metrics_ref},
        reports_index={REPORT_GOVERNANCE_REPORT_REF: governance_ref},
        params=dict(params or {}),
    )
    return store, ctx, state


def test_decision_packet_persists_phase5_validation_ref_on_pass(tmp_path) -> None:
    store, ctx, state = _context_and_state(
        tmp_path,
        params={"judge_verdict": _passing_judge_verdict()},
    )

    outcome = BuildDecisionPacketNode().execute(ctx, state)

    assert outcome.status == "ok"
    assert ARTIFACT_VALIDATION_REPORT_REF in outcome.state.artifacts_index
    assert ARTIFACT_JUDGE_VERDICT_REF in outcome.state.artifacts_index
    packet_ref = outcome.state.artifacts_index[ARTIFACT_DECISION_PACKET_REF]
    packet = from_canonical_bytes(store.get_bytes(packet_ref.artifact_id))
    assert packet["validation_report_ref"]["artifact_id"] == str(
        outcome.state.artifacts_index[ARTIFACT_VALIDATION_REPORT_REF].artifact_id
    )
    assert packet["validation"]["verdict"] in {"pass", "warn"}
    assert packet["validation"]["readiness"] in {"ready", "monitor"}
    assert packet["judge_verdict_ref"]["artifact_id"] == str(
        outcome.state.artifacts_index[ARTIFACT_JUDGE_VERDICT_REF].artifact_id
    )


def test_decision_packet_is_not_persisted_when_phase5_blocks(tmp_path) -> None:
    store, ctx, state = _context_and_state(
        tmp_path,
        params={"phase5_enforce_publication": True},
    )

    outcome = BuildDecisionPacketNode().execute(ctx, state)

    assert outcome.status == "fail"
    assert outcome.error is not None
    assert outcome.error.code == "phase5_validation_failed"
    assert ARTIFACT_DECISION_PACKET_REF not in outcome.state.artifacts_index
    validation_ref = outcome.state.artifacts_index[ARTIFACT_VALIDATION_REPORT_REF]
    assert ARTIFACT_JUDGE_VERDICT_REF in outcome.state.artifacts_index
    report = from_canonical_bytes(store.get_bytes(validation_ref.artifact_id))
    assert report["verdict"] == "blocked"
    assert any(component["name"] == "six_judges" for component in report["phase5_components"])
