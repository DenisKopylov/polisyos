from __future__ import annotations

import logging

import pytest

from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import PutOptions
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.scientist.governance.report import GovernanceReport, load_governance_report_artifact
from polisyos.scientist.nodes.builtins.decide._decision_packet_contracts import (
    _DecisionPacketBuildRequest,
)
from polisyos.scientist.nodes.builtins.decide.decision_packet.builder import (
    BuildDecisionPacketNode,
    __build_packet_payload__,
    _GovernanceReportIntakeRefusal,
)
from polisyos.scientist.nodes.builtins.decide.decision_packet_support import ReplayReadiness
from polisyos.scientist.nodes.builtins.decide.policy_runtime_artifacts import (
    _load_governance_report_from_ref_impl,
    _load_governance_report_impl,
)
from polisyos.scientist.nodes.builtins.decide.run_policy_promotion import (
    _load_governance_report,
    _load_governance_report_from_ref,
)
from polisyos.scientist.nodes.builtins.planning.run_evaluator import RunEvaluatorNode
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_DECISION_PACKET_REF,
    REPORT_GOVERNANCE_REPORT_REF,
)
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.state import ExperimentState

_REPORT_PAYLOAD = {"schema_version": "1.0", "verdict": "approve", "issues": []}
_GOVERNANCE_SCHEMA = SchemaInfo(
    name="polisyos.scientist.GovernanceReport",
    version="1.0",
)


def _put_governance_report(store, *, schema: SchemaInfo | None = _GOVERNANCE_SCHEMA):
    return store.put_json(
        _REPORT_PAYLOAD,
        PutOptions(
            kind="scientist.governance_report",
            media_type="application/json",
            schema=schema,
        ),
        return_selected_profile=True,
    )


def _packet_request() -> _DecisionPacketBuildRequest:
    return _DecisionPacketBuildRequest(
        seed=1,
        inputs_section={},
        artifacts_section={},
        readiness=ReplayReadiness.INCOMPLETE,
        strategy_hint="test",
        policy_summary="test policy",
        intervention_count=0,
    )


def _context_and_state(store, ref=None):
    run_id = "governance-owner-admission"
    registry_bundle = build_default_registry_bundle(store).bundle_ref
    ctx = ExecutionContext(
        store=store,
        run=RunContext.start(store=store, registry_bundle=registry_bundle, run_id=run_id),
        logger=logging.getLogger("test.governance-owner-admission"),
    )
    state = ExperimentState(
        run_id=run_id,
        reports_index=({REPORT_GOVERNANCE_REPORT_REF: ref} if ref is not None else {}),
    )
    return ctx, state


def test_all_governance_consumers_accept_the_owner_profile(
    cas_store,
) -> None:
    """The producer's versioned schema reaches each current governance reader."""
    ref = _put_governance_report(cas_store)
    execution_context, state = _context_and_state(cas_store, ref)

    expected = GovernanceReport(**_REPORT_PAYLOAD)
    assert _load_governance_report_impl(execution_context, state) == expected
    assert _load_governance_report_from_ref_impl(execution_context, ref) == GovernanceReport(
        **_REPORT_PAYLOAD
    )
    assert _load_governance_report(execution_context, state) == expected
    assert _load_governance_report_from_ref(execution_context, ref) == GovernanceReport(
        **_REPORT_PAYLOAD
    )

    packet, packet_report = __build_packet_payload__(execution_context, state, _packet_request())
    assert packet_report == expected
    assert packet["governance"]["verdict"] == "approve"
    assert packet["governance"]["issues"] == []
    assert packet["governance"]["links"]["claims_ref"] is None

    evaluator = RunEvaluatorNode().execute(execution_context, state)
    assert not any(
        event.code == "EVALUATOR_GOVERNANCE_REPORT_INVALID" for event in evaluator.events
    )
    assert evaluator.state.params["evaluator_verdict"] == "APPROVE"


def test_governance_reader_preserves_existing_profileless_owner_manifest(cas_store) -> None:
    """Existing 1.0 reports remain readable when their selector predates profile refs."""
    legacy_ref = cas_store.put_json(
        _REPORT_PAYLOAD,
        PutOptions(
            kind="scientist.governance_report",
            media_type="application/json",
            schema=_GOVERNANCE_SCHEMA,
        ),
    )

    assert legacy_ref.manifest_profile_sha256 is None
    assert load_governance_report_artifact(cas_store, legacy_ref) == GovernanceReport(
        **_REPORT_PAYLOAD
    )


def test_all_governance_consumers_reject_same_bytes_under_foreign_schema(
    cas_store,
) -> None:
    """A matching kind and payload do not make an unrelated manifest schema admissible."""
    foreign_ref = _put_governance_report(
        cas_store,
        schema=SchemaInfo(name="polisyos.scientist.UnrelatedApproval", version="9.9"),
    )
    execution_context, state = _context_and_state(cas_store, foreign_ref)

    direct_readers = (
        lambda: _load_governance_report_impl(execution_context, state),
        lambda: _load_governance_report_from_ref_impl(execution_context, foreign_ref),
        lambda: _load_governance_report(execution_context, state),
        lambda: _load_governance_report_from_ref(execution_context, foreign_ref),
    )
    for reader in direct_readers:
        with pytest.raises(ValueError):
            reader()

    packet, packet_report = __build_packet_payload__(execution_context, state, _packet_request())
    assert isinstance(packet_report, _GovernanceReportIntakeRefusal)
    assert packet_report.reason_code == "canon_profile_owned_artifact_schema_mismatch"
    assert packet["governance"] is None
    assert any(
        item["reason"] == "governance_report_load_failed" for item in packet["degraded_paths"]
    )

    evaluator = RunEvaluatorNode().execute(execution_context, state)
    assert any(event.code == "EVALUATOR_GOVERNANCE_REPORT_INVALID" for event in evaluator.events)
    assert evaluator.state.params["evaluator_verdict"] != "APPROVE"


def test_decision_packet_node_fails_closed_for_supplied_foreign_governance_profile(
    cas_store,
) -> None:
    """An invalid supplied report cannot disappear into the packet's optional path."""
    foreign_ref = _put_governance_report(
        cas_store,
        schema=SchemaInfo(name="polisyos.scientist.UnrelatedApproval", version="9.9"),
    )
    execution_context, state = _context_and_state(cas_store, foreign_ref)

    outcome = BuildDecisionPacketNode().execute(execution_context, state)

    assert outcome.status == "fail"
    assert outcome.error is not None
    assert outcome.error.code == "governance_report_not_established"
    assert outcome.error.details["governance_report_status"] == "not_established"
    assert outcome.error.details["artifact_ref"] == str(foreign_ref.artifact_id)


def test_absent_governance_report_keeps_candidate_build_path(cas_store) -> None:
    """True absence remains optional and does not trigger the supplied-ref refusal."""
    execution_context, state = _context_and_state(cas_store)

    outcome = BuildDecisionPacketNode().execute(execution_context, state)

    assert outcome.status == "ok"
    assert ARTIFACT_DECISION_PACKET_REF in outcome.state.artifacts_index
