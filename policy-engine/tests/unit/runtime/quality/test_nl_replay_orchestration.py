from __future__ import annotations

# ruff: noqa: S101
from polisyos.runtime.quality.nl_replay_orchestration import (
    NL_REPLAY_ORCHESTRATION_SCHEMA_VERSION,
    build_nl_replay_orchestration_continuity,
)
from polisyos.runtime.quality.replay import build_replay_manifest, explain_replay_drift


def _sha(char: str) -> str:
    return "sha256:" + char * 64


def _spine_context() -> dict[str, object]:
    return {
        "schema_version": "policyos.producer_spine_context.v1",
        "context_id": "producer-spine-context-w4a",
        "concept_spine_ref": _sha("2"),
        "jurisdiction_spine_ref": _sha("6"),
        "canonical_concept_refs": ["concept.msme_survival_rate"],
        "jurisdiction_refs": ["UA"],
        "consumer_components": [
            "lex",
            "fabric",
            "scholar",
            "foundry",
            "scientist",
            "final_compiler",
        ],
    }


def _claim_registry() -> dict[str, object]:
    return {
        "schema_version": "policyos.runtime.claim_registry.v1",
        "runtime_claim_registry_ref": "quality_evidence/runtime_claim_registry.json",
        "status": "pass",
        "claims": [
            {
                "claim_id": "rec_1",
                "claim_ref": "claim:rec_1",
                "runtime_event_ref": "event://claim/rec_1",
                "concept_spine_ref": _sha("2"),
                "producer_handshake_ledger_ref": "producer-handshake-ledger:w4a",
                "producer_handshake_refs": ["producer-handshake:fabric"],
                "selected_producer_refs": {
                    "fabric": ["binding.fabric.msme-panel"],
                    "lex": ["binding.lex.credit-norm"],
                },
            }
        ],
    }


def _quality_evidence() -> dict[str, object]:
    return {
        "semantic_binding_ledger": {
            "schema_version": "policyos.semantic_binding_ledger.v1",
            "semantic_binding_ref": _sha("b"),
            "status": "pass",
            "spine_context": _spine_context(),
            "producer_handshake_ledger": {
                "producer_handshake_ledger_ref": "producer-handshake-ledger:w4a",
                "status": "pass",
                "records": [
                    {
                        "handshake_id": "producer-handshake:fabric",
                        "producer_component": "fabric",
                        "status": "pass",
                        "state": "emitted_binding",
                        "selected_binding_refs": ["binding.fabric.msme-panel"],
                        "emitted_binding_refs": ["binding.fabric.msme-panel"],
                    }
                ],
            },
            "fabric": [
                {
                    "candidate_spine_binding_refs": ["binding.fabric.msme-panel"],
                    "spine_blocker_refs": [],
                }
            ],
            "lex": [
                {
                    "candidate_spine_binding_refs": ["binding.lex.credit-norm"],
                    "spine_blocker_refs": [],
                }
            ],
        },
        "runtime_claim_registry": _claim_registry(),
        "evidence_spine_handoff_ledger": {
            "schema_version": "policyos.evidence_spine_handoff_ledger.v1",
            "status": "pass",
            "handoffs": [
                {
                    "handoff_id": "handoff:request",
                    "handoff_kind": "nl_request_creation",
                    "carrier_ref": "evidence-spine:carrier-w4a",
                    "parent_spine_ref": "evidence-spine:carrier-w4a",
                    "concept_spine_ref": _sha("2"),
                    "producer_handshake_refs": ["producer-handshake:fabric"],
                    "input_refs": ["request.sanitized.json"],
                    "output_refs": ["job.json"],
                    "producer_ref": "runtime.api.nl_request",
                    "consumer_ref": "runtime.control_plane.create_job",
                }
            ],
        },
        "scenario_contract_propagation_graph": {
            "schema_version": "policyos.scenario_contract_propagation_graph.v1",
            "status": "pass",
            "nodes": [
                {
                    "node_id": "runtime.request_context",
                    "carrier": {
                        "spine_id": "evidence-spine:carrier-w4a",
                        "trace_id": "evidence-spine:carrier-w4a",
                    },
                }
            ],
        },
    }


def test_nl_replay_continuity_binds_carrier_spine_claims_and_producers() -> None:
    record = build_nl_replay_orchestration_continuity(
        request_context={
            "context": {
                "producer_spine_context": _spine_context(),
                "scenario_evidence_contract": {
                    "scenario_evidence_contract_id": "scenario-contract:w4a",
                    "requirements": [{"requirement_id": "scenario.req.credit_support"}],
                },
            }
        },
        workflow_state={"producer_spine_context": _spine_context()},
        job_progress={
            "runtime_quality_refs": {
                "concept_spine_ref": _sha("2"),
                "jurisdiction_spine_ref": _sha("6"),
                "runtime_claim_registry_ref": "quality_evidence/runtime_claim_registry.json",
            },
            "evidence_spine_handoffs": _quality_evidence()[
                "evidence_spine_handoff_ledger"
            ]["handoffs"],
        },
        quality_evidence=_quality_evidence(),
        replay_manifest={
            "orchestration_continuity": {
                "carrier_ref": "evidence-spine:carrier-w4a",
                "concept_spine_ref": _sha("2"),
                "runtime_claim_registry_ref": "quality_evidence/runtime_claim_registry.json",
            }
        },
        bundle_payload={
            "files": {
                "quality_evidence": {
                    "runtime_orchestration_continuity": (
                        "quality_evidence/runtime_orchestration_continuity.json"
                    )
                }
            }
        },
        inspection_report={
            "bundle_inspections": [
                {
                    "components": [
                        {
                            "component_id": "runtime_orchestration_continuity",
                            "status": "pass",
                            "evidence_refs": [
                                "quality_evidence/runtime_orchestration_continuity.json"
                            ],
                        }
                    ]
                }
            ]
        },
        readiness_payload={
            "status": "pass",
            "orchestration_continuity_ref": (
                "quality_evidence/runtime_orchestration_continuity.json"
            ),
            "carrier_ref": "evidence-spine:carrier-w4a",
        },
        export_payload={
            "semantic_audit": {
                "runtime_orchestration_continuity": {
                    "carrier_ref": "evidence-spine:carrier-w4a"
                }
            }
        },
    )

    assert record["schema_version"] == NL_REPLAY_ORCHESTRATION_SCHEMA_VERSION
    assert record["status"] == "pass"
    assert record["carrier_ref"] == "evidence-spine:carrier-w4a"
    assert record["concept_spine_ref"] == _sha("2")
    assert record["jurisdiction_spine_ref"] == _sha("6")
    assert record["runtime_claim_registry_ref"] == "quality_evidence/runtime_claim_registry.json"
    assert record["producer_handshake_ledger_ref"] == "producer-handshake-ledger:w4a"
    assert record["producer_handshake_refs"] == ["producer-handshake:fabric"]
    assert {
        "binding.fabric.msme-panel",
        "binding.lex.credit-norm",
    } <= set(record["producer_binding_refs"])
    assert record["summary"]["surface_count"] >= 8
    assert record["findings"] == []


def test_replay_manifest_treats_orchestration_continuity_drift_as_high_impact() -> None:
    continuity = build_nl_replay_orchestration_continuity(
        request_context={"context": {"producer_spine_context": _spine_context()}},
        quality_evidence=_quality_evidence(),
    )

    baseline = build_replay_manifest(
        request_payload={"question": "Can replay see the same carrier?"},
        orchestration_continuity=continuity,
    )
    replay = dict(baseline)
    replay["orchestration_continuity"] = {
        **dict(baseline["orchestration_continuity"]),
        "carrier_ref": "evidence-spine:other-carrier",
    }

    explanation = explain_replay_drift(
        baseline_manifest=baseline,
        replay_manifest=replay,
    )

    assert explanation["status"] == "unexplained_drift"
    assert explanation["production_readiness"] == "fail"
    assert explanation["summary"]["drift_sources"] == ["orchestration"]
    assert explanation["differences"][0]["impact"] == "high"
