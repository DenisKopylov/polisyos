from __future__ import annotations

# ruff: noqa: S101
from copy import deepcopy
from typing import Any

import pytest

from polisyos.runtime.quality.institutional_provenance import (
    InstitutionalProvenanceError,
    emit_contestability_appeals_runtime_provenance,
    emit_implementation_feasibility_runtime_provenance,
)


def test_implementation_feasibility_runtime_producer_emits_serious_claim_provenance() -> None:
    payload = emit_implementation_feasibility_runtime_provenance(
        recommendation_rows=[_implementation_row()],
        run_context=_serious_context(),
    )

    assert payload["status"] == "complete"
    assert payload["evidence_authority"] == "runtime_emitted"
    assert payload["producer"] == "polisyos.runtime.quality.institutional_provenance"
    assert len(payload["records"]) == 1

    record = payload["records"][0]
    assert record["emitted_during_serious_run"] is True
    assert record["producer"]
    assert record["event_refs"]
    assert record["artifact_refs"]
    assert record["trace_refs"]
    assert record["claim_binding"]["claim_id"] == "deterministic_recommendation_1"
    assert record["actor"]["actor_id"] == "ua-wartime-msme-program-administrator"
    assert record["risk"]["risk_refs"]
    assert set(record["monitoring_outcome_refs"]) >= {
        "quality_evidence/continuous_governance_reissue_report.json",
        "quality_evidence/continuous_governance_stale_report.json",
        "quality_evidence/continuous_governance_withdraw_report.json",
    }


def test_implementation_feasibility_runtime_producer_fails_closed_without_required_refs() -> None:
    missing_monitoring = deepcopy(_implementation_row())
    missing_monitoring["monitoring_evidence"] = {}

    with pytest.raises(InstitutionalProvenanceError, match="monitoring_outcome_refs_missing"):
        emit_implementation_feasibility_runtime_provenance(
            recommendation_rows=[missing_monitoring],
            run_context=_serious_context(),
        )

    dev_context = {**_serious_context(), "execution_profile": "dev"}
    with pytest.raises(InstitutionalProvenanceError, match="serious_run_required"):
        emit_implementation_feasibility_runtime_provenance(
            recommendation_rows=[_implementation_row()],
            run_context=dev_context,
        )


def test_contestability_runtime_producer_emits_one_outcome_per_appeal() -> None:
    payload = emit_contestability_appeals_runtime_provenance(
        appeal_rows=_appeal_rows(),
        run_context=_serious_context(),
    )

    assert payload["status"] == "complete"
    assert payload["evidence_authority"] == "runtime_emitted"
    records = payload["records"]
    assert {record["appeal_id"] for record in records} == {
        "appeal-msme-standing-001",
        "appeal-auditor-trace-002",
        "appeal-withdrawal-003",
    }
    assert {record["appeal_disposition"] for record in records} == {
        "accepted_for_reissue",
        "accepted_mark_stale_until_authority_refs_reviewed",
        "withdraw_public_projection_pending_competence_review",
    }
    assert {record["lifecycle_transition"] for record in records} == {
        "reissue_required",
        "stale_required",
        "withdrawal_required",
    }
    assert all(record["publication_state_effect"] for record in records)
    assert all(record["event_refs"] for record in records)
    assert all(record["artifact_refs"] for record in records)
    assert all(record["trace_refs"] for record in records)


def test_contestability_runtime_producer_rejects_empty_or_manual_appeal_rows() -> None:
    with pytest.raises(InstitutionalProvenanceError, match="appeal_rows_missing"):
        emit_contestability_appeals_runtime_provenance(
            appeal_rows=[],
            run_context=_serious_context(),
        )

    manual_only = deepcopy(_appeal_rows()[0])
    manual_only["outcome_refs"] = []
    with pytest.raises(InstitutionalProvenanceError, match="artifact_refs_missing"):
        emit_contestability_appeals_runtime_provenance(
            appeal_rows=[manual_only],
            run_context=_serious_context(),
        )


def _serious_context() -> dict[str, Any]:
    return {
        "run_id": "R_8bbd65c6d0a03dc6",
        "job_id": "66696d6a137a4e6ba95afc9dd810c045",
        "case_id": "pdc-R_8bbd65c6d0a03dc6",
        "tenant_id": "tenant-public-golden",
        "cell_id": "cell-msme-ua",
        "trace_id": "trace-wave35h-runtime",
        "execution_profile": "production",
        "event_refs": [
            "runtime-event://policy-design-case/R_8bbd65c6d0a03dc6/publication-readiness",
            "runtime-event://policy-design-case/R_8bbd65c6d0a03dc6/governance-lifecycle",
        ],
        "artifact_refs": [
            "quality_evidence/evidence_provenance_manifest.json",
            "quality_evidence/public_export_bundle.json",
        ],
        "trace_refs": [
            ".polisyos/canary_evidence/profile-research__provider-simulated__data-canonical_production__scenario-public_golden__ui-api_only/20260518T185434Z_66696d6a137a4e6ba95afc9dd810c045/timeline.json",
        ],
    }


def _implementation_row() -> dict[str, Any]:
    return {
        "recommendation_id": "deterministic_recommendation_1",
        "implementation_actor": {
            "actor_id": "ua-wartime-msme-program-administrator",
            "actor_type": "public_program_administrator",
        },
        "feasibility_evidence": {
            "capacity_evidence_ref": "quality_evidence/production_data_quality.json",
            "status": "runtime_bound",
        },
        "risk_evidence": {
            "risk_refs": [
                "quality_evidence/decision_artifact_quality.json#/issues",
                "quality_evidence/semantic_binding_ledger.json",
            ],
        },
        "monitoring_evidence": {
            "monitor_refs": [
                "quality_evidence/continuous_governance_stale_report.json",
                "quality_evidence/continuous_governance_reissue_report.json",
                "quality_evidence/continuous_governance_withdraw_report.json",
            ],
        },
        "source_refs": ["production_msme_panel.golden_source"],
        "method_refs": ["foundry.causal_effect_estimation"],
        "norm_refs": ["norm.wartime_business_support_authority"],
        "claim_binding": {
            "claim_id": "deterministic_recommendation_1",
            "claim_type": "recommendation",
            "claim_text_ref": "policy_grounding_matrix.json#/claims/0",
            "claim_authority_ledger_ref": (
                "_build/policy-design-case/rebaseline/wave-35C/"
                "claim_authority_binding_ledger.json"
            ),
            "generic_final_text_sufficient": False,
        },
    }


def _appeal_rows() -> list[dict[str, Any]]:
    return [
        _appeal_row(
            appeal_id="appeal-msme-standing-001",
            disposition="accepted_for_reissue",
            transition="reissue_required",
            outcome_ref="quality_evidence/continuous_governance_reissue_report.json",
        ),
        _appeal_row(
            appeal_id="appeal-auditor-trace-002",
            disposition="accepted_mark_stale_until_authority_refs_reviewed",
            transition="stale_required",
            outcome_ref="quality_evidence/continuous_governance_stale_report.json",
        ),
        _appeal_row(
            appeal_id="appeal-withdrawal-003",
            disposition="withdraw_public_projection_pending_competence_review",
            transition="withdrawal_required",
            outcome_ref="quality_evidence/continuous_governance_withdraw_report.json",
        ),
    ]


def _appeal_row(
    *,
    appeal_id: str,
    disposition: str,
    transition: str,
    outcome_ref: str,
) -> dict[str, Any]:
    return {
        "appeal_id": appeal_id,
        "claim_id": "deterministic_recommendation_1",
        "standing": "affected_party",
        "grounds": "runtime-owned appeal outcome test",
        "submitted_evidence": ["quality_evidence/public_export_bundle.json"],
        "owner": "team-public-legitimacy",
        "sla": "5 business days",
        "disposition": disposition,
        "outcome_refs": [f"appeal-ledger://{appeal_id}/disposition", outcome_ref],
        "lifecycle_transition": transition,
        "publication_state_effect": "public_projection_blocked_until_runtime_outcome_applied",
        "monitoring_changes": ["monitor appeal effect"],
    }
