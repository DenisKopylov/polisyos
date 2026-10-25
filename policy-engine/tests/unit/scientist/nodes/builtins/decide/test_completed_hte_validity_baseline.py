from __future__ import annotations

from polisyos.core.contracts.decision_validity import (
    DecisionBasisSection,
    DecisionTriggerType,
    DecisionValidityEnvelope,
    DecisionValidityStatus,
)
from polisyos.scientist.nodes.builtins.decide.decision_packet.validation import (
    _build_decision_validity_baseline,
)


def _envelope(summary: dict[str, object]) -> DecisionValidityEnvelope:
    return DecisionValidityEnvelope(
        decision_lineage_key="completed_hte_baseline_lineage",
        policy_fingerprint="completed_hte_baseline_policy",
        data_basis=DecisionBasisSection(summary=summary),
    )


def test_requested_hte_without_selected_owner_warns_from_typed_basis() -> None:
    envelope = _envelope(
        {
            "completed_hte_source_status": "verification_missing",
            "completed_hte_request_status": "requested",
            "completed_hte_requested_source_run_id": "R_requested_unowned",
            "completed_hte_limitation_code": "completed_hte_selection_owner_not_established",
            "completed_hte_authority_purpose": "candidate_method_evidence",
            "completed_hte_publication_authorization": "not_established",
        }
    )

    baseline = _build_decision_validity_baseline(
        packet_payload={"hte": None},
        envelope=envelope,
    )

    assert baseline.status == DecisionValidityStatus.WARNING
    assert "completed_hte_selection_owner_not_established" in baseline.reasons
    trigger = next(
        item
        for item in baseline.triggers
        if item.trigger_type == DecisionTriggerType.METRIC_INVALIDATION
    )
    assert trigger.details["request_status"] == "requested"
    assert trigger.details["selection_status"] == "verification_missing"
    assert trigger.details["requested_source_run_id"] == "R_requested_unowned"
    assert trigger.details["publication_authorization"] == "not_established"


def test_selected_candidate_stays_candidate_when_publication_is_not_established() -> None:
    envelope = _envelope(
        {
            "completed_hte_source_status": "selected",
            "completed_hte_request_status": "requested",
            "completed_hte_requested_source_run_id": "R_selected_candidate",
            "completed_hte_source_run_id": "R_selected_candidate",
            "completed_hte_authority_purpose": "candidate_method_evidence",
            "completed_hte_publication_authorization": "not_established",
        }
    )

    baseline = _build_decision_validity_baseline(
        packet_payload={"hte": None},
        envelope=envelope,
    )

    assert baseline.status == DecisionValidityStatus.ACTIVE
    assert not any(
        item.trigger_type == DecisionTriggerType.METRIC_INVALIDATION for item in baseline.triggers
    )


def test_raw_marker_without_typed_request_basis_does_not_change_baseline() -> None:
    envelope = _envelope({})
    packet_payload = {
        "hte": {
            "selection_status": "verification_missing",
            "limitation_code": "marker_only_is_not_request_evidence",
            "request_status": "requested",
            "requested_source_run_id": "R_marker_only",
        }
    }

    baseline = _build_decision_validity_baseline(
        packet_payload=packet_payload,
        envelope=envelope,
    )

    assert baseline.status == DecisionValidityStatus.ACTIVE
    assert "marker_only_is_not_request_evidence" not in baseline.reasons
    assert not any(
        item.trigger_type == DecisionTriggerType.METRIC_INVALIDATION for item in baseline.triggers
    )


def test_selected_source_must_match_the_typed_requested_run_id() -> None:
    envelope = _envelope(
        {
            "completed_hte_source_status": "selected",
            "completed_hte_request_status": "requested",
            "completed_hte_requested_source_run_id": "R_requested",
            "completed_hte_source_run_id": "R_other",
        }
    )

    baseline = _build_decision_validity_baseline(
        packet_payload={"hte": None},
        envelope=envelope,
    )

    assert baseline.status == DecisionValidityStatus.WARNING
    assert "completed_hte_dependency_basis_not_established" in baseline.reasons


def test_partial_typed_request_without_selection_status_warns() -> None:
    # Removing the selection-status field must not erase the remaining typed request.
    envelope = _envelope(
        {
            "completed_hte_request_status": "requested",
            "completed_hte_requested_source_run_id": "R_requested_without_selection",
        }
    )

    baseline = _build_decision_validity_baseline(
        packet_payload={"hte": None},
        envelope=envelope,
    )

    assert baseline.status == DecisionValidityStatus.WARNING
    assert "completed_hte_selection_status_not_established" in baseline.reasons
    trigger = next(
        item
        for item in baseline.triggers
        if item.trigger_type == DecisionTriggerType.METRIC_INVALIDATION
    )
    assert trigger.details["request_status"] == "requested"
    assert trigger.details["selection_status"] is None
    assert trigger.details["requested_source_run_id"] == "R_requested_without_selection"
