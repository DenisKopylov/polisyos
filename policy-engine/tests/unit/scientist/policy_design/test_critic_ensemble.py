"""W6.E multi-critic ensemble tests."""

from __future__ import annotations

from collections.abc import Sequence

from polisyos.scientist.policy_design.critic_ensemble import (
    CriticEnvelope,
    CriticVerdict,
    MultiCriticEnsemble,
    PolicyDesignCritic,
)
from polisyos.scientist.policy_design.formulator import FormulatorCandidate, LLMFormulator

from .test_formulator import _msme_input


def test_default_critic_ensemble_uses_eight_substantive_bases() -> None:
    payload = _msme_input()
    formulated = LLMFormulator().formulate(payload)

    report = MultiCriticEnsemble.default().evaluate(
        payload,
        candidates=formulated.candidates,
    )

    assert report.diversity.critic_count == 8
    assert report.diversity.basis_count == 8
    assert {verdict.envelope.critic_role for verdict in report.verdicts} == {
        "legal",
        "fiscal",
        "equity",
        "data",
        "implementation",
        "affected_person",
        "adversarial",
        "monitoring",
    }
    assert len({verdict.envelope.substantive_basis for verdict in report.verdicts}) == 8
    assert "critic_monoculture_identical_output" not in {
        warning.code for warning in report.diversity.warnings
    }
    for verdict in report.verdicts:
        assert verdict.verdict in {
            "agree",
            "contest",
            "add_candidate_obligation",
            "flag_missing_evidence",
            "flag_speculation",
            "flag_scope_drift",
        }
        if verdict.proposed_candidate is not None:
            assert verdict.proposed_candidate.source_class == "llm_critic"
            assert verdict.proposed_candidate.admission_state == "candidate_unverified"


def test_ensemble_warns_when_all_critics_emit_identical_agree_output() -> None:
    payload = _msme_input()
    formulated = LLMFormulator().formulate(payload)
    critics = tuple(
        _StaticAgreeCritic(role=role, basis=basis)
        for role, basis in (
            ("legal", "legal_corpus_probe"),
            ("fiscal", "deterministic_rule_set"),
            ("equity", "statistical_pattern"),
            ("data", "historical_failure_corpus"),
            ("implementation", "simulation_probe"),
            ("affected_person", "participation_provenance_check"),
            ("adversarial", "adversarial_scenario_generator"),
            ("monitoring", "monitoring_lifecycle_drift_simulator"),
        )
    )

    report = MultiCriticEnsemble(critics=critics).evaluate(
        payload,
        candidates=formulated.candidates,
    )

    assert "critic_monoculture_identical_output" in {
        warning.code for warning in report.diversity.warnings
    }


def test_affected_person_critic_flags_preference_speculation_without_provenance() -> None:
    payload = _msme_input().model_copy(
        update={
            "facets": {
                "instrument_type": "credit_guarantee",
                "targeting_type": "means_tested_msme",
            }
        }
    )
    formulated = LLMFormulator().formulate(payload)

    report = MultiCriticEnsemble.default().evaluate(payload, candidates=formulated.candidates)

    assert any(
        verdict.envelope.critic_role == "affected_person"
        and verdict.verdict == "flag_speculation"
        and "participation_provenance_missing" in verdict.failure_modes
        for verdict in report.verdicts
    )


class _StaticAgreeCritic(PolicyDesignCritic):
    def __init__(self, *, role: str, basis: str) -> None:
        self._envelope = CriticEnvelope(
            critic_role=role,
            substantive_basis=basis,
            critic_version="test",
        )

    @property
    def envelope(self) -> CriticEnvelope:
        return self._envelope

    def evaluate(
        self,
        context: object,
        candidates: Sequence[FormulatorCandidate],
    ) -> tuple[CriticVerdict, ...]:
        return (
            CriticVerdict(
                verdict="agree",
                envelope=self.envelope,
                target_candidate_ids=tuple(candidate.candidate_id for candidate in candidates),
                message="No additional critique.",
                failure_modes=(),
            ),
        )
