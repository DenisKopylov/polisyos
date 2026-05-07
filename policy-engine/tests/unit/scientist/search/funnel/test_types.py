"""Tests for funnel core types (A.1)."""

from __future__ import annotations

from polisyos.scientist.methods.search.funnel.types import (
    CheapSignalVector,
    FunnelStageResult,
    TypedFailureCard,
    UncertaintyEnvelope,
    UncertaintyEstimate,
    UncertaintyType,
)

# ---------------------------------------------------------------------------
# UncertaintyEnvelope
# ---------------------------------------------------------------------------


class TestUncertaintyEnvelope:
    def test_deterministic_factory(self):
        env = UncertaintyEnvelope.deterministic()
        assert len(env.uncertainties) == len(UncertaintyType)
        for ut, est in env.uncertainties.items():
            assert est.level == 1.0
            assert "not assessed at this fidelity" in est.source

    def test_unknown_factory(self):
        env = UncertaintyEnvelope.unknown()
        assert len(env.uncertainties) == len(UncertaintyType)
        for ut, est in env.uncertainties.items():
            assert est.level == 1.0

    def test_with_update_returns_new_envelope(self):
        env = UncertaintyEnvelope.unknown()
        updated = env.with_update(
            UncertaintyType.STATISTICAL,
            UncertaintyEstimate(
                level=0.3,
                source="bootstrap",
                quantification_method="bootstrap_ci",
                is_reducible=True,
            ),
        )
        # Original unchanged.
        assert env.uncertainties[UncertaintyType.STATISTICAL].level == 1.0
        # Updated has new value.
        assert updated.uncertainties[UncertaintyType.STATISTICAL].level == 0.3
        # Other types preserved.
        assert updated.uncertainties[UncertaintyType.STRUCTURAL].level == 1.0


# ---------------------------------------------------------------------------
# TypedFailureCard
# ---------------------------------------------------------------------------


class TestTypedFailureCard:
    def test_is_blocker_property(self):
        blocker = TypedFailureCard(
            judge_name="test",
            failure_type="x",
            severity="blocker",
            description="fatal",
        )
        warning = TypedFailureCard(
            judge_name="test",
            failure_type="x",
            severity="warning",
            description="non-fatal",
        )
        info = TypedFailureCard(
            judge_name="test",
            failure_type="x",
            severity="info",
            description="informational",
        )
        assert blocker.is_blocker is True
        assert warning.is_blocker is False
        assert info.is_blocker is False


# ---------------------------------------------------------------------------
# CheapSignalVector
# ---------------------------------------------------------------------------


class TestCheapSignalVector:
    def test_default_routing_is_advance(self):
        signal = CheapSignalVector()
        assert signal.routing_decision() == "advance"

    def test_reject_on_low_structural_validity(self):
        signal = CheapSignalVector(structural_validity=0.3)
        assert signal.routing_decision() == "reject"

    def test_reject_on_low_causal_identifiability(self):
        signal = CheapSignalVector(causal_identifiability=0.1)
        assert signal.routing_decision() == "reject"

    def test_reject_on_high_positivity_risk(self):
        signal = CheapSignalVector(positivity_risk=0.9)
        assert signal.routing_decision() == "reject"

    def test_reject_on_high_policy_conflict(self):
        signal = CheapSignalVector(policy_conflict=0.9)
        assert signal.routing_decision() == "reject"

    def test_fast_track(self):
        signal = CheapSignalVector(
            structural_validity=1.0,
            causal_identifiability=1.0,
            expected_value_proxy=0.95,
            feasibility=0.9,
            expected_harm_proxy=0.05,
            positivity_risk=0.1,
            uncertainty_prior=0.2,
        )
        assert signal.routing_decision() == "fast_track"

    def test_advance_normal_case(self):
        signal = CheapSignalVector(
            structural_validity=0.8,
            causal_identifiability=0.6,
            positivity_risk=0.3,
            policy_conflict=0.2,
            feasibility=0.7,
        )
        assert signal.routing_decision() == "advance"


# ---------------------------------------------------------------------------
# FunnelStageResult
# ---------------------------------------------------------------------------


class TestFunnelStageResult:
    def test_has_blockers(self):
        result = FunnelStageResult(
            policy_candidate={},
            objective_value=0.0,
            is_promising=False,
            stage_name="test",
            failure_cards=[
                TypedFailureCard(
                    judge_name="t",
                    failure_type="x",
                    severity="blocker",
                    description="bad",
                ),
            ],
        )
        assert result.has_blockers is True

    def test_no_blockers(self):
        result = FunnelStageResult(
            policy_candidate={},
            objective_value=0.0,
            is_promising=True,
            stage_name="test",
            failure_cards=[
                TypedFailureCard(
                    judge_name="t",
                    failure_type="x",
                    severity="warning",
                    description="mild",
                ),
            ],
        )
        assert result.has_blockers is False

    def test_empty_cards(self):
        result = FunnelStageResult(
            policy_candidate={},
            objective_value=0.0,
            is_promising=True,
            stage_name="test",
        )
        assert result.has_blockers is False
