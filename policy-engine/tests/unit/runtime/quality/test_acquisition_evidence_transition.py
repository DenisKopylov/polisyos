"""Pure transition routing controls; placeholder refs never establish authority."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, get_args

import pytest
from pydantic import ValidationError

from polisyos.core.artifacts import ArtifactRef
from polisyos.core.artifacts.ids import ArtifactID
from polisyos.runtime.quality.acquisition_evidence_transition import (
    AcquisitionConstraintTransitionIntent,
    AcquisitionEvidenceTransitionBasis,
    AcquisitionEvidenceTransitionKind,
    AcquisitionIndependentReplicaTransitionIntent,
    AcquisitionMethodTransitionIntent,
    AcquisitionModelTransitionIntent,
    DeclaredAcquisitionReplicaObservation,
    acquisition_evidence_transition_profiles,
    dispatch_acquisition_evidence_transition,
)
from polisyos.runtime.quality.design_problem import DesignConstraint


def _ref(kind: str, digit: str) -> ArtifactRef:
    return ArtifactRef(
        artifact_id=ArtifactID.model_validate("sha256:" + digit * 64),
        kind=kind,
        media_type="application/json",
        manifest_profile_sha256="sha256:" + "f" * 64,
    )


def _basis(*, selected: bool = True) -> AcquisitionEvidenceTransitionBasis:
    # These are declared selectors for a pure dispatcher test, not CAS proof.
    return AcquisitionEvidenceTransitionBasis(
        evaluation_decision_ref=_ref("runtime_quality.acquisition_evaluation_decision", "1"),
        previous_basis_ref=_ref("runtime_quality.acquisition_evaluation_basis", "2"),
        prospective_basis_ref=_ref("runtime_quality.acquisition_evaluation_basis", "3"),
        selected_basis_ref=(
            _ref("runtime_quality.acquisition_evaluation_basis", "4") if selected else None
        ),
        selected_basis_status="declared_for_replay" if selected else "not_established",
    )


def _observation(**updates: Any) -> DeclaredAcquisitionReplicaObservation:
    return DeclaredAcquisitionReplicaObservation(
        **{
            "observation_id": "observation-one",
            "measurement_id": "measurement-one",
            "sample_id": "sample-one",
            "independence_group_id": "declared-group-one",
            "observed_at": datetime(2026, 11, 3, 12, tzinfo=UTC),
            "sample_size": 12,
            "seed": 101,
            "scalar_value": -17.1,
            "independence_basis_refs": (_ref("declared_sampling_context", "5"),),
            **updates,
        }
    )


def test_finite_table_has_one_real_model_chain_and_three_zero_budget_refusals() -> None:
    """The complete declared kind denominator cannot quietly omit a refusal."""
    profiles = acquisition_evidence_transition_profiles()
    assert len(profiles) == 4
    assert {row.kind for row in profiles} == set(
        get_args(AcquisitionEvidenceTransitionKind.__value__)
    )
    assert len({row.kind for row in profiles}) == len(profiles)
    model, *unsupported = profiles
    assert model.kind == "model" and model.status == "verification_required"
    assert model.consumer_ref == (
        "polisyos.runtime.quality.acquisition_model_transition.resolve_candidate_model_revision"
    )
    assert model.producer_refs and model.repeated_step_refs
    assert model.maximum_budget.acquisition_actions == 1
    assert model.maximum_budget.n5_evaluations == 1
    assert model.maximum_budget.new_empirical_samples == 0
    for row in unsupported:
        assert row.status == "not_supported"
        assert row.producer_refs == row.repeated_step_refs == ()
        assert row.consumer_ref is None and "owner_not_established" in row.required_owner
        assert row.maximum_budget.acquisition_actions == row.maximum_budget.n5_evaluations == 0
        assert row.maximum_budget.new_empirical_samples == 0
    assert all(row.execution_authority is False for row in profiles)


def test_model_intent_routes_to_verification_without_promoting_declared_refs() -> None:
    """Well-shaped selected refs remain declared inputs until the real owner replays."""
    intent = AcquisitionModelTransitionIntent(
        purpose="Inspect the effect of a declared candidate coefficient change.",
        dependency_basis=_basis(),
    )
    dispatched = dispatch_acquisition_evidence_transition(intent)
    assert dispatched.intent == intent
    assert dispatched.status == "verification_required"
    assert dispatched.predicate_provenance == dispatched.independence_status == "not_established"
    assert dispatched.publication_authority is False
    assert dispatched.authority_purpose == "candidate_transition_intent_only"
    assert dispatched.replica_request_relation is None
    # Even all-equal selected basis refs cannot establish a model difference.
    same = intent.dependency_basis.previous_basis_ref
    equal_intent = intent.model_copy(
        update={
            "dependency_basis": AcquisitionEvidenceTransitionBasis(
                evaluation_decision_ref=intent.dependency_basis.evaluation_decision_ref,
                previous_basis_ref=same,
                prospective_basis_ref=same,
                selected_basis_ref=same,
                selected_basis_status="declared_for_replay",
            )
        }
    )
    assert dispatch_acquisition_evidence_transition(equal_intent).predicate_provenance == (
        "not_established"
    )


def test_prospective_intent_never_invents_the_post_execution_selected_basis() -> None:
    """An executable request cannot pretend its future N5 output already exists."""
    basis = _basis(selected=False)
    intent = AcquisitionModelTransitionIntent(
        purpose="Request a bounded real model rerun after prospective comparison.",
        dependency_basis=basis,
    )
    dispatched = dispatch_acquisition_evidence_transition(intent)
    assert dispatched.status == "verification_required"
    assert dispatched.intent.dependency_basis.selected_basis_ref is None
    assert dispatched.intent.dependency_basis.selected_basis_status == "not_established"
    assert dispatched.profile.execution_authority is False
    assert dispatched.predicate_provenance == "not_established"
    for updates in (
        {"selected_basis_status": "declared_for_replay"},
        {"selected_basis_ref": basis.prospective_basis_ref},
    ):
        with pytest.raises(
            ValidationError, match="acquisition_transition_selected_basis_stage_mismatch"
        ):
            AcquisitionEvidenceTransitionBasis.model_validate(
                {**basis.model_dump(mode="python"), **updates}
            )


def test_method_and_constraint_changes_preserve_full_intent_and_refuse_execution() -> None:
    """No unavailable transition is silently treated as model reuse or a no-op."""
    constraint = DesignConstraint(
        constraint_id="cost_limit",
        description="Keep declared cost below the requested limit.",
        admissibility_basis="request",
        source_text="The request declares a cost limit.",
    )
    intents = (
        AcquisitionMethodTransitionIntent(
            purpose="Compare a requested alternative method.",
            dependency_basis=_basis(),
            previous_method_fqn="foundry.methods.catalog.causal.ncm_engine.pure_step",
            requested_method_fqn="declared_alternative_method_not_admitted",
        ),
        AcquisitionConstraintTransitionIntent(
            purpose="Reconsider the requested constraint.",
            dependency_basis=_basis(),
            previous_constraints=(constraint,),
            requested_constraints=(constraint.model_copy(update={"hard": False}),),
        ),
    )
    for intent in intents:
        dispatched = dispatch_acquisition_evidence_transition(intent)
        assert dispatched.status == "not_supported"
        assert dispatched.intent.model_dump(mode="python") == intent.model_dump(mode="python")
        assert (
            dispatched.profile.reason_code == f"acquisition_{intent.kind}_transition_not_supported"
        )
        assert dispatched.profile.maximum_budget.n5_evaluations == 0
        assert dispatched.predicate_provenance == "not_established"


def test_equal_scalar_replica_preserves_sample_time_seed_and_declared_independence() -> None:
    """Distinct declared metadata is retained without inventing independent evidence."""
    previous = _observation()
    requested = _observation(
        observation_id="observation-two",
        measurement_id="measurement-two",
        sample_id="sample-two",
        independence_group_id="declared-group-two",
        observed_at=previous.observed_at + timedelta(days=1),
        sample_size=21,
        seed=202,
    )
    intent = AcquisitionIndependentReplicaTransitionIntent(
        purpose="Request a distinct scientific sample with the same observed scalar.",
        dependency_basis=_basis(),
        attempt_kind="new_scientific_sample",
        previous_observation=previous,
        requested_observation=requested,
    )
    dispatched = dispatch_acquisition_evidence_transition(intent)
    assert dispatched.status == "not_supported"
    assert dispatched.replica_request_relation == "distinct_declared_sample"
    assert dispatched.intent == intent
    assert dispatched.intent.previous_observation.scalar_value == (
        dispatched.intent.requested_observation.scalar_value
    )
    assert dispatched.intent.previous_observation.sample_size == 12
    assert dispatched.intent.requested_observation.sample_size == 21
    assert dispatched.intent.requested_observation.independence_status == "declared_not_verified"
    assert dispatched.independence_status == "not_established"
    assert dispatched.profile.maximum_budget.new_empirical_samples == 0
    # JSON transport preserves the complete declared observation/time payload.
    round_trip = type(intent).model_validate_json(intent.model_dump_json())
    assert dispatch_acquisition_evidence_transition(round_trip) == dispatched


def test_new_uuid_and_technical_retry_do_not_establish_a_new_independent_sample() -> None:
    """An observation alias cannot convert the same measurement/sample into independence."""
    original = _observation()
    for attempt, expected in (
        ("new_scientific_sample", "same_declared_sample"),
        ("technical_retry", "technical_retry"),
    ):
        intent = AcquisitionIndependentReplicaTransitionIntent(
            purpose="Keep a technical retry separate from a scientific sample.",
            dependency_basis=_basis(),
            attempt_kind=attempt,
            previous_observation=original,
            requested_observation=_observation(observation_id="new-uuid-only"),
        )
        dispatched = dispatch_acquisition_evidence_transition(intent)
        assert dispatched.replica_request_relation == expected
        assert dispatched.status == "not_supported"
        assert dispatched.independence_status == "not_established"
        assert dispatched.profile.maximum_budget.n5_evaluations == 0


@pytest.mark.parametrize(
    "field",
    [
        "evaluation_decision_ref",
        "previous_basis_ref",
        "prospective_basis_ref",
        "selected_basis_ref",
    ],
)
def test_dependency_basis_requires_full_correctly_typed_selected_views(field: str) -> None:
    payload = _basis().model_dump(mode="python")
    original = payload[field]
    for updates in (
        {"manifest_profile_sha256": None},
        {"kind": "foreign_kind"},
        {"media_type": "text/plain"},
    ):
        with pytest.raises(
            ValidationError, match="acquisition_transition_basis_selected_view_required"
        ):
            AcquisitionEvidenceTransitionBasis.model_validate(
                {**payload, field: {**original, **updates}}
            )


def test_dispatch_revalidates_bypassed_models_and_rejects_claimed_authority() -> None:
    """Neither model_copy nor a present certificate-shaped extra can grant success."""
    valid = AcquisitionModelTransitionIntent(
        purpose="Candidate sensitivity.", dependency_basis=_basis()
    )
    for mutation in (
        {"publication_authority": True},
        {"purpose": "  "},
        {"changed_field": "outcome_noise_stddev"},
        {"verified_certificate": "declared-verifier-label"},
    ):
        with pytest.raises(ValidationError):
            dispatch_acquisition_evidence_transition(valid.model_copy(update=mutation))
    with pytest.raises(TypeError, match="acquisition_evidence_transition_intent_untyped"):
        dispatch_acquisition_evidence_transition(valid.model_dump(mode="python"))
    for updates in (
        {"sample_size": True},
        {"sample_size": 0},
        {"seed": "101"},
        {"observed_at": datetime(2026, 11, 3, 12)},
        {"scalar_value": float("nan")},
        {"independence_status": "verified"},
    ):
        with pytest.raises(ValidationError):
            _observation(**updates)
