from __future__ import annotations

# ruff: noqa: S101
from datetime import UTC, datetime
from typing import Any

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.pdc import compile_runtime_policy_design_case
from polisyos.runtime.quality.rule_evolution import build_rule_evolution_registry
from polisyos.runtime.quality.rule_replay_engine import replay_under_original_rules
from polisyos.scientist.evidence.claims.lifecycle import (
    AppendOnlyClaimLedger,
    ClaimLifecycleAction,
)
from polisyos.scientist.evidence.claims.models import (
    ClaimPublishability,
    ClaimRecord,
    ClaimSupportStatus,
    ClaimType,
)
from polisyos.scientist.governance.continuous.detectors import (
    PolicyContextSignal,
    detect_policy_context_drift,
)
from polisyos.scientist.governance.continuous.lifecycle_bridge import (
    bridge_governance_events_to_claim_lifecycle,
)
from polisyos.scientist.governance.continuous.monitors import DecisionValidityStatus
from polisyos.scientist.methods.search.readiness import DecisionReadiness


def _ref(seed: str, *, kind: str = "scientist.test") -> ArtifactRef:
    return ArtifactRef(
        artifact_id="sha256:" + seed * 64,
        kind=kind,
        media_type="application/json",
    )


def _sha(char: str) -> str:
    return "sha256:" + char * 64


def _claim(claim_id: str) -> ClaimRecord:
    return ClaimRecord(
        claim_id=claim_id,
        run_id="run-i9-lifecycle-smoke",
        claim_type=ClaimType.FACTUAL,
        text=f"{claim_id} remains in the closed case graph.",
        support_status=ClaimSupportStatus.SUPPORTED,
        publishability=ClaimPublishability.INTERNAL_ONLY,
        readiness_level=DecisionReadiness.RESEARCH_ARTIFACT,
    )


def _closed_claims() -> list[dict[str, Any]]:
    return [
        {
            "claim_id": "claim_legal_context",
            "claim_type": "factual",
            "text": "Legal context supports current publication guidance.",
            "support_status": "supported",
            "publishability": "internal_only",
            "readiness_level": "research_artifact",
            "scenario_requirement_refs": ["req.legal_context"],
            "facts": {"legal_context_validity": 0.72},
        },
        {
            "claim_id": "claim_unaffected",
            "claim_type": "factual",
            "text": "Unrelated operational claim keeps historical semantics.",
            "support_status": "supported",
            "publishability": "internal_only",
            "readiness_level": "research_artifact",
            "scenario_requirement_refs": ["req.unaffected"],
            "facts": {"legal_context_validity": 0.91},
        },
    ]


def _registry(*, version: str, threshold: float) -> dict[str, Any]:
    return build_rule_evolution_registry(
        registry_id=f"rule-registry-{version}",
        version=version,
        effective_at="2026-05-24T00:00:00+00:00",
        rule_refs=[
            {
                "requirement_id": "req.legal_context",
                "logic": {
                    "field": "legal_context_validity",
                    "operator": ">=",
                    "threshold": threshold,
                },
                "taxonomy_refs": ["taxonomy.policy_context.v1"],
                "authority_purpose": "admissibility",
                "rule_version": version,
                "provenance_ref": _sha("a"),
            },
            {
                "requirement_id": "req.unaffected",
                "logic": {
                    "field": "legal_context_validity",
                    "operator": ">=",
                    "threshold": threshold,
                },
                "taxonomy_refs": ["taxonomy.policy_context.v1"],
                "authority_purpose": "admissibility",
                "rule_version": version,
                "provenance_ref": _sha("b"),
            },
        ],
        taxonomy_refs=[
            {
                "taxonomy_id": "taxonomy.policy_context",
                "version": version,
                "ref": _sha("c"),
            }
        ],
        evidence_ref=_sha("d"),
        runtime_event_ref=f"event://rule-evolution/{version}",
    )


def _closed_case(registry: dict[str, Any]) -> dict[str, Any]:
    return {
        "case_id": "pdc-i9-lifecycle-smoke",
        "case_status": "closed",
        "closed_at": "2026-05-24T10:00:00+00:00",
        "rule_evolution_registry": registry,
        "claims": _closed_claims(),
        "closed_semantic_outputs": [
            {
                "claim_id": "claim_legal_context",
                "requirement_id": "req.legal_context",
                "current_requirement_id": "req.legal_context",
                "rule_id": "req.legal_context",
                "logic_hash": registry["rule_refs"][0]["logic_hash"],
                "taxonomy_refs": ["taxonomy.policy_context.v1"],
                "authority_purpose": "admissibility",
                "evaluation_status": "admissible",
                "passed": True,
                "observed_value": 0.72,
                "operator": ">=",
                "threshold": 0.5,
                "reason": "observed_value_satisfies_threshold",
            },
            {
                "claim_id": "claim_unaffected",
                "requirement_id": "req.unaffected",
                "current_requirement_id": "req.unaffected",
                "rule_id": "req.unaffected",
                "logic_hash": registry["rule_refs"][1]["logic_hash"],
                "taxonomy_refs": ["taxonomy.policy_context.v1"],
                "authority_purpose": "admissibility",
                "evaluation_status": "admissible",
                "passed": True,
                "observed_value": 0.91,
                "operator": ">=",
                "threshold": 0.5,
                "reason": "observed_value_satisfies_threshold",
            },
        ],
    }


def test_i9_lifecycle_drift_smoke_runs_detector_to_partial_reissue_and_rule_replay() -> None:
    decision_ref = _ref("1", kind="scientist.decision_packet")
    original_claim_ledger_ref = _ref("2", kind="scientist.claim_ledger_v2")
    registry = _registry(version="2026.05", threshold=0.5)
    closed_case = _closed_case(registry)
    graph = compile_runtime_policy_design_case(
        run_id="run-i9-lifecycle-smoke",
        claims=closed_case["claims"],
        claim_registry={"claims": closed_case["claims"]},
        closeout_verdict={
            "status": "closed",
            "verdict": "can_closeout",
            "can_closeout": True,
        },
        generated_at=datetime(2026, 5, 24, 10, 0, tzinfo=UTC),
    )

    detector_result = detect_policy_context_drift(
        decision_packet_ref=decision_ref,
        signals=[
            PolicyContextSignal(
                signal_id="context-drift-legal-001",
                change_kind="legal_authority_reissue_required",
                description="Legal context drift requires claim-local reissue.",
                severity_score=0.96,
                history_count=240,
                blocking_candidate=True,
                affected_claim_ids=("claim_legal_context",),
                scope={"domain": "benefits", "jurisdiction": "UA"},
                occurred_at=datetime(2026, 5, 24, 12, 0, tzinfo=UTC),
                metadata={"lifecycle_transition": "reissued"},
            )
        ],
    )
    event = detector_result.events[0]

    bridge = bridge_governance_events_to_claim_lifecycle(
        ledger=AppendOnlyClaimLedger(
            run_id="run-i9-lifecycle-smoke",
            current_claims=[_claim("claim_legal_context"), _claim("claim_unaffected")],
        ),
        decision_packet_ref=decision_ref,
        original_claim_ledger_ref=original_claim_ledger_ref,
        monitor_events=[event],
        monitor_event_refs=[_ref("3", kind="scientist.governance_monitor_event")],
        actor_id="continuous_governance.lifecycle_bridge",
        case_id=closed_case["case_id"],
        new_decision_packet_ref=_ref("4", kind="scientist.decision_packet"),
        new_claim_ledger_ref=_ref("5", kind="scientist.claim_ledger_v2"),
        unchanged_records=[_ref("6", kind="scientist.claim_record")],
        superseded_refs=[_ref("7", kind="scientist.claim_record")],
        public_diff_refs=[_ref("8", kind="runtime.public_revision_diff")],
        occurred_at=datetime(2026, 5, 24, 12, 5, tzinfo=UTC),
    )
    replay = replay_under_original_rules(
        closed_case,
        {
            "change_id": "context-rule-change-2026-05",
            "change_class": "stricter_admissibility",
            "from_rule_registry": registry,
            "to_rule_registry": _registry(version="2026.06", threshold=0.8),
            "affected_requirement_ids": ["req.legal_context"],
        },
        replay_time="2026-05-24T12:10:00+00:00",
    )

    assert graph.claim_graph.claims[0].claim_id == "claim_legal_context"
    assert len(graph.claim_graph.claims) == 2
    assert detector_result.detector_family == "policy_context_drift"
    assert event.event_type == "policy_context_drift"
    assert event.affected_claim_ids == ["claim_legal_context"]
    assert bridge.status == "pass"
    assert bridge.blockers == []
    assert bridge.updated_ledger.events[0].action is ClaimLifecycleAction.REISSUED
    assert bridge.reissue_packet is not None
    assert bridge.reissue_packet.status is DecisionValidityStatus.REISSUED
    assert bridge.reissue_packet.scope_to_revise == ["claim_legal_context"]
    assert bridge.public_revision_state.affected_claim_ids == ["claim_legal_context"]
    assert bridge.public_revision_state.unaffected_claim_ids == ["claim_unaffected"]
    assert bridge.public_revision_state.closed_case_historical_meaning == "preserved"
    assert replay["semantic_replay_status"] == "match"
    assert replay["reproduces_closed_outputs"] is True
