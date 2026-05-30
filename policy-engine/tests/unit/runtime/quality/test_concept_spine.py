"""Compatibility entrypoint for the archived Policy Design Case validation ladder."""

# W2.A extends this compatibility entrypoint with semantic regression asserts.
# The repository test-suite normally suppresses S101/F403 through per-file
# ignores; keep the local directive because this file is often linted directly.
# ruff: noqa: F403,S101

import pytest

from polisyos.runtime.quality.claim_registry import build_runtime_claim_registry
from polisyos.runtime.quality.concept_spine import (
    CONCEPT_SPINE_HANDSHAKE_LEDGER_SCHEMA_VERSION,
    CONCEPT_SPINE_HYBRID_CARRIER_SCHEMA_VERSION,
    ProducerHandshakeValidationError,
    build_concept_spine_bridge_authority_record,
    build_hybrid_concept_spine_carrier,
    build_producer_handshake_ledger,
    build_producer_handshake_record,
    validate_hybrid_concept_spine_carrier,
)
from polisyos.runtime.quality.semantic_binding import (
    build_producer_spine_read_context,
    close_semantic_binding_ledger,
)
from tests.unit.runtime.quality.test_policy_design_case_concept_spine import *


def _sha2(char: str) -> str:
    return "sha256:" + char * 64


def _namespace(namespace_id: str, namespace_type: str = "metric") -> dict[str, object]:
    return {
        "namespace_id": namespace_id,
        "namespace_type": namespace_type,
        "scheme_owner": "team-policy-semantics",
        "scheme_version": "2026-05-22",
        "definition_ref": f"repo://policy-engine/architecture/concept-namespaces#{namespace_id}",
        "governed": True,
    }


def _reconciled_concept(**overrides: object) -> dict[str, object]:
    concept: dict[str, object] = {
        "concept_id": "concept.msme_survival_rate",
        "concept_type": "metric",
        "label": "MSME survival rate",
        "namespace_refs": ["policyos.metric.v1"],
        "source_refs": ["fabric:metric:msme_survival", "ir:metric:msme_survival_rate"],
        "producer_refs": ["fabric", "scientist", "ir"],
        "status": "resolved",
        "time_roles": {
            "policy_time": "2026-05-15",
            "data_time": "2024-2026",
            "freshness_time": "2026-05-17",
            "replay_time": "2026-05-22T00:00:00Z",
        },
        "geography_refs": ["UA"],
        "population_refs": ["wartime-msmes"],
        "unit_refs": ["unit:percent"],
    }
    concept.update(overrides)
    return concept


def test_hybrid_concept_spine_carrier_preserves_governed_namespaces_and_blocks_conflicts() -> None:
    carrier = build_hybrid_concept_spine_carrier(
        run_id="run-w2a",
        job_id="job-w2a",
        tenant_id="tenant-1",
        authority_profile="production",
        concept_spine_ref=_sha2("2"),
        governed_namespace_refs=[
            _namespace("policyos.metric.v1"),
            _namespace("policyos.time_role.v1", "time_role"),
            _namespace("policyos.relation_taxonomy.v1", "relation_taxonomy"),
        ],
        reconciled_concepts=[
            _reconciled_concept(),
            _reconciled_concept(
                concept_id="concept.credit_volume",
                label="Credit volume",
                status="conflicting",
                source_refs=["fabric:metric:credit_volume"],
                conflict_refs=["concept.msme_survival_rate"],
            ),
        ],
        relations=[
            {
                "relation_id": "relation:credit-volume-survival",
                "source_concept_ref": "concept.credit_volume",
                "target_concept_ref": "concept.msme_survival_rate",
                "relation_type": "conflicting",
                "closeout_effect": "blocker",
                "namespace_ref": "policyos.relation_taxonomy.v1",
                "provenance_ref": _sha2("9"),
                "time_roles": {"policy_time": "2026-05-15", "data_time": "2024-2026"},
            }
        ],
    )

    validated = validate_hybrid_concept_spine_carrier(carrier)

    assert validated["schema_version"] == CONCEPT_SPINE_HYBRID_CARRIER_SCHEMA_VERSION
    assert validated["status"] == "blocked"
    assert validated["authority_boundary"] == "concept_spine_closeout_input"
    assert validated["summary"]["governed_namespace_count"] == 3
    assert validated["summary"]["reconciled_concept_count"] == 2
    assert validated["summary"]["blocker_count"] == 1
    assert validated["governed_namespace_refs"][1]["namespace_type"] == "time_role"
    assert {
        blocker["code"] for blocker in validated["blockers"]
    } == {"concept_spine_conflicting_concept_blocker"}
    assert validated["blockers"][0]["capability_label"] == "bridge_missing"


def test_producer_handshake_records_bounded_liveness_and_context_only_labels() -> None:
    context = build_producer_spine_read_context(
        concept_spine_ref=_sha2("2"),
        jurisdiction_spine_ref=_sha2("6"),
        canonical_concept_refs=["concept.msme_survival_rate"],
        jurisdiction_refs=["UA"],
        unit_refs=["unit:percent"],
        period_refs=["2024-2026"],
        geography_refs=["UA"],
    )
    record = build_producer_handshake_record(
        producer_component="lex",
        run_id="run-w2a",
        job_id="job-w2a",
        tenant_id="tenant-1",
        state="emitted_binding",
        spine_context=context,
        consumed_requirement_refs=["req.legal_authority"],
        bindings=[
            {
                "binding_id": "binding.lex.norm.credit",
                "binding_kind": "norm",
                "disposition": "selected",
                "concept_ref": "concept.msme_survival_rate",
                "requirement_ref": "req.legal_authority",
                "artifact_ref": "norm.ua.credit_eligibility",
                "time_role": "legal_effective_time",
            },
            {
                "binding_id": "label.lex.credit-support",
                "binding_kind": "label",
                "disposition": "context_only",
                "concept_ref": "concept.msme_survival_rate",
                "label": "credit support",
            },
        ],
        liveness_config={
            "default_deadline_s": 30.0,
            "default_retry_ceiling": 2,
            "producer_deadline_overrides_s": {"lex": 5.0},
            "producer_retry_ceiling_overrides": {"lex": 1},
        },
    )

    assert record["state"] == "emitted_binding"
    assert record["status"] == "pass"
    assert record["liveness"]["deadline_s"] == 5.0
    assert record["liveness"]["retry_ceiling"] == 1
    assert record["consumed_concept_refs"] == ["concept.msme_survival_rate"]
    assert record["selected_binding_refs"] == ["binding.lex.norm.credit"]
    assert record["context_only_label_refs"] == ["label.lex.credit-support"]
    assert record["bridge_authority"]["authority_role"] == "closeout_input"
    assert "producer_domain_truth" in record["bridge_authority"]["may_not_use_for"]

    ledger = build_producer_handshake_ledger(
        [record],
        required_producers=("lex",),
        run_id="run-w2a",
    )

    assert ledger["schema_version"] == CONCEPT_SPINE_HANDSHAKE_LEDGER_SCHEMA_VERSION
    assert ledger["status"] == "pass"
    assert ledger["summary"]["record_count"] == 1


def test_waiting_on_peer_requires_named_peer_artifact_fields_and_deadline() -> None:
    with pytest.raises(
        ProducerHandshakeValidationError,
        match="producer_handshake_waiting_on_peer_condition_missing",
    ):
        build_producer_handshake_record(
            producer_component="foundry",
            run_id="run-w2a",
            job_id="job-w2a",
            tenant_id="tenant-1",
            state="waiting_on_peer",
            concept_spine_ref=_sha2("2"),
            jurisdiction_spine_ref=_sha2("6"),
            consumed_concept_refs=["concept.msme_survival_rate"],
            consumed_requirement_refs=["req.method"],
            wait_conditions=[{"peer_producer": "fabric"}],
        )


def test_bridge_authority_is_closeout_scoped_not_producer_evidence() -> None:
    closeout_input = build_concept_spine_bridge_authority_record(
        bridge_ref="bridge.lex.norm.credit",
        bridge_class="producer_attestation",
        authoritative_boundary="producer_consumed_spine_and_emitted_binding",
        producer_component="lex",
        consumer_component="semantic_binding",
        input_refs=[_sha2("2"), "req.legal_authority"],
        output_refs=["binding.lex.norm.credit"],
        cas_ref=_sha2("c"),
        same_input_closed=True,
        reader_compatible=True,
        redaction_integrity_status="pass",
    )
    diagnostic = build_concept_spine_bridge_authority_record(
        bridge_ref="bridge.dashboard.render",
        bridge_class="diagnostic_projection",
        authoritative_boundary="dashboard_rendered_handshake_state",
        producer_component="runtime.dashboard",
        consumer_component="operator",
        input_refs=["quality_evidence/producer_handshake_ledger.json"],
        output_refs=["dashboard.json"],
        cas_ref=_sha2("d"),
        same_input_closed=True,
        reader_compatible=True,
        redaction_integrity_status="pass",
    )

    assert closeout_input["closeout_input"] is True
    assert closeout_input["authoritative_for"] == ["boundary_continuity"]
    assert "producer_domain_truth" in closeout_input["may_not_use_for"]
    assert diagnostic["closeout_input"] is False
    assert diagnostic["authority_role"] == "diagnostic_only"
    assert "runtime_closeout_authority" in diagnostic["may_not_use_for"]


def test_handshake_records_feed_semantic_binding_and_claim_registry_context() -> None:
    context = build_producer_spine_read_context(
        concept_spine_ref=_sha2("2"),
        jurisdiction_spine_ref=_sha2("6"),
        canonical_concept_refs=["concept.msme_survival_rate"],
        jurisdiction_refs=["UA"],
    )
    fabric_handshake = build_producer_handshake_record(
        producer_component="fabric",
        run_id="run-w2a",
        job_id="job-w2a",
        tenant_id="tenant-1",
        state="emitted_binding",
        spine_context=context,
        consumed_requirement_refs=["scenario.req.credit_support"],
        bindings=[
            {
                "binding_id": "binding.fabric.msme-panel",
                "binding_kind": "dataset",
                "disposition": "selected",
                "concept_ref": "concept.msme_survival_rate",
                "requirement_ref": "scenario.req.credit_support",
                "artifact_ref": "source.msme_panel",
                "time_role": "data_time",
            }
        ],
    )
    ledger = build_producer_handshake_ledger([fabric_handshake], required_producers=("fabric",))
    closed = close_semantic_binding_ledger(
        {
            "schema_version": "policyos.semantic_binding_ledger.v1",
            "semantic_binding_ref": _sha2("b"),
            "status": "pass",
            "policy_intent_ref": _sha2("a"),
            "spine_context": context,
            "producer_handshake_ledger": ledger,
            "intent": {
                "policy_intent_ref": _sha2("a"),
                "canonical_concept_refs": ["concept.msme_survival_rate"],
                "jurisdiction": "UA",
                "time_context": "2026-05-15",
                "population": "wartime MSMEs",
                "intervention": "credit support",
                "treatment": "credit eligibility",
                "outcome": "msme survival",
                "legal_domain": "wartime_msme_support",
                "data_source_family": "production_msme_panel",
                "dataset": "source.msme_panel",
                "columns": ["firm_id", "survival"],
                "method_family": "causal_effect_estimation",
                "final_claim": "rec_1",
                "monitoring_signal": "msme_survival_rate",
                "public_artifact_section": "recommendations",
            },
            "lex": [],
            "fabric": [],
            "scholar": [],
            "foundry": [],
            "scientist": [],
            "final_compiler": [],
        }
    )

    assert closed["producer_handshake_ledger"]["status"] == "pass"
    assert "semantic_binding_phase_record_missing" in {
        issue["code"] for issue in closed["issues"]
    }

    registry = build_runtime_claim_registry(
        claims=[
            {
                "claim_id": "rec_1",
                "scenario_requirement_refs": ["scenario.req.credit_support"],
                "data_refs": ["source.msme_panel"],
                "selected_norm_refs": ["norm.ua.credit_eligibility"],
                "method_output_refs": ["foundry.did.msme_survival"],
                "portfolio_refs": ["portfolio.rec_1"],
                "argument_refs": ["argument.rec_1"],
                "warrant_refs": ["warrant.rec_1"],
                "rebuttal_refs": ["rebuttal.rec_1"],
                "counter_evidence_refs": ["counter.rec_1"],
                "limitation_refs": ["limit.rec_1"],
                "accepted_deficit_refs": ["deficit.rec_1"],
            }
        ],
        spine_context={
            "concept_spine_ref": _sha2("2"),
            "producer_handshake_ledger_ref": ledger["producer_handshake_ledger_ref"],
        },
    )
    row = registry["claims"][0]

    assert row["concept_spine_ref"] == _sha2("2")
    assert row["producer_handshake_ledger_ref"] == ledger["producer_handshake_ledger_ref"]
