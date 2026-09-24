"""Behavioral conservation and anti-fork proofs for the admitted movement channel."""

from __future__ import annotations

from copy import deepcopy
from typing import get_args

import pytest

from polisyos.runtime.quality import vocabulary_crosswalk as subject
from polisyos.runtime.quality.adaptation_transition import KPIControlStateSnapshot


def test_canonical_movement_admits_every_member_and_refuses_unknowns() -> None:
    for member in subject.MovementClass:
        assert subject.require_canonical_movement("SMDV-1@1", member.value) is member
    with pytest.raises(ValueError, match="movement_namespace_refused"):
        subject.require_canonical_movement("same-meaning-another-name", "prediction_error")
    with pytest.raises(ValueError, match="movement_member_refused"):
        subject.require_canonical_movement("SMDV-1@1", "cause_looks_plausible")


def test_second_arbitrarily_named_movement_vocabulary_is_refused() -> None:
    rows = deepcopy(subject.movement_registry())
    rows.append({**rows[0], "vocabulary_id": "unrelated-spelling@91"})
    with pytest.raises(ValueError, match="movement_vocabulary_fork"):
        subject.validate_movement_registry(rows)
    rows = deepcopy(subject.movement_registry())
    rows[0]["terms"].append("unknown_cause")
    with pytest.raises(ValueError, match="movement_vocabulary_terms_drift"):
        subject.validate_movement_registry(rows)


def test_removing_registry_independence_cannot_hide_a_new_namespace(monkeypatch) -> None:
    rows = deepcopy(subject.movement_registry())
    rows.append({**rows[0], "vocabulary_id": "fork@1"})
    monkeypatch.setattr(subject, "movement_registry", lambda: rows)
    with pytest.raises(ValueError, match="movement_vocabulary_fork"):
        subject.require_canonical_movement("SMDV-1@1", "prediction_error")


def test_blocking_loss_refuses_for_each_dimension_and_display_loss_preserves_identity() -> None:
    entry = subject.CrosswalkEntry(
        vocabulary_id="int-r6.semantic@candidate-1",
        source_term="withdrawn",
        source_owner="int-r6",
        source_version="candidate-1",
        semantic_purpose="candidate_identity_transport",
        target_owner=subject.TARGET_OWNER,
    )
    for loss in subject.BLOCKING_DIMENSIONS:
        with pytest.raises(ValueError, match=f"blocking_loss:{loss}"):
            subject.project_term(entry, current_status="failed_safe", losses=(loss,))
    with pytest.raises(ValueError, match="unclassified_loss"):
        subject.project_term(entry, current_status="failed_safe", losses=("unseen_semantic_loss",))
    result = subject.project_term(entry, current_status="failed_safe", losses=("display_label",))
    assert result.source_term == "withdrawn"
    assert result.vocabulary_id == entry.vocabulary_id
    assert result.target_status == "failed_safe"
    assert result.authority_granted is False


def test_no_status_addition_and_no_source_identity_or_owner_substitution() -> None:
    entry = subject.CrosswalkEntry(
        vocabulary_id="int-r5.reason@0.1.0-candidate",
        source_term="polisyos.int_r5.reason.certificate_stale@0.1.0-candidate",
        source_owner="int-r5",
        source_version="0.1.0-candidate",
        semantic_purpose="candidate_identity_transport",
        target_owner=subject.TARGET_OWNER,
    )
    assert set(subject.target_statuses()) == set(
        get_args(KPIControlStateSnapshot.model_fields["status"].annotation)
    )
    for status in subject.target_statuses():
        assert subject.project_term(entry, current_status=status).target_status == status
    with pytest.raises(ValueError, match="target_status_unregistered"):
        subject.project_term(entry, current_status="positive_with_warning")
    with pytest.raises(ValueError, match="target_owner_refused"):
        subject.project_term(
            entry.model_copy(update={"target_owner": "claimant.status"}), current_status="pending"
        )
    with pytest.raises(ValueError, match="reason_namespace_or_version_lost"):
        subject.project_term(
            entry.model_copy(update={"source_term": "certificate_stale"}),
            current_status="failed_safe",
        )


def test_factor_axes_are_not_lifecycle_statuses() -> None:
    expected = [
        (subject.EpistemicFactor, "E", 5),
        (subject.ExposureFactor, "X", 5),
        (subject.InterventionFactor, "V", 5),
        (subject.ClaimFactor, "C", 4),
    ]
    for owner, prefix, size in expected:
        assert {item.value for item in owner} == {f"{prefix}{i}" for i in range(size)}
        assert not ({item.value for item in owner} & set(subject.target_statuses()))
