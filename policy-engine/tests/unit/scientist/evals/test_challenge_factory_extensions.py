from __future__ import annotations

# ruff: noqa: S101
import json
from pathlib import Path
from typing import Any

from polisyos.scientist.evals.challenge_factory import (
    R14_ADVERSARIAL_PROBES,
    AuthoritySpoofingProbe,
    ChallengeClass,
    ParticipationSpeculationProbe,
    PromptInjectionProbe,
    evaluate_r14_adversarial_probe_fixture,
)

REPO_ROOT = Path(__file__).resolve().parents[4]
FIXTURE_ROOT = REPO_ROOT / "tests" / "fixtures" / "policy_design_case" / "w10c_adversarial_probes"

REQUIRED_FIXTURES = {
    "authority_spoofing_fake_envelope.json": {
        "challenge_class": ChallengeClass.AUTHORITY_SPOOFING.value,
        "probe_id": AuthoritySpoofingProbe.probe_id,
        "failure_code": "r14_authority_spoofing_rejected",
    },
    "prompt_injection_critic_bypass.json": {
        "challenge_class": ChallengeClass.PROMPT_INJECTION.value,
        "probe_id": PromptInjectionProbe.probe_id,
        "failure_code": "r14_prompt_injection_firewall_blocked",
    },
    "participation_speculation_without_provenance.json": {
        "challenge_class": ChallengeClass.PARTICIPATION_SPECULATION.value,
        "probe_id": ParticipationSpeculationProbe.probe_id,
        "failure_code": "r14_participation_speculation_blocked",
    },
    "llm_critic_consensus_speculation_laundering.json": {
        "challenge_class": ChallengeClass.AUTHORITY_SPOOFING.value,
        "probe_id": AuthoritySpoofingProbe.probe_id,
        "failure_code": "r14_authority_spoofing_rejected",
    },
}


def _read_fixture(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def test_r14_probe_registry_contains_the_three_missing_c26_probes() -> None:
    assert {
        AuthoritySpoofingProbe.probe_id: AuthoritySpoofingProbe,
        PromptInjectionProbe.probe_id: PromptInjectionProbe,
        ParticipationSpeculationProbe.probe_id: ParticipationSpeculationProbe,
    } == R14_ADVERSARIAL_PROBES


def test_w10c_adversarial_probe_fixtures_fire_expected_semantic_failures() -> None:
    assert FIXTURE_ROOT.is_dir()

    for fixture_name, expected in REQUIRED_FIXTURES.items():
        fixture = _read_fixture(FIXTURE_ROOT / fixture_name)
        result = evaluate_r14_adversarial_probe_fixture(fixture)

        assert fixture["structural_pass_claimed"] is True
        assert {"C26", "E22"} <= set(fixture["research_refs"])
        assert {"P10", "P15"} <= set(fixture["pattern_ids"])
        assert result.fixture_id == fixture["fixture_id"]
        assert result.challenge_class == expected["challenge_class"]
        assert result.probe_id == expected["probe_id"]
        assert result.structural_status == "pass"
        assert result.status == "semantic_fail"
        assert expected["failure_code"] in result.failure_codes
        assert result.firewall_status in {"blocked", "downgraded"}
        assert not result.issues


def test_prompt_injection_probe_requires_persisted_ledger_and_firewall_block() -> None:
    fixture = _read_fixture(FIXTURE_ROOT / "prompt_injection_critic_bypass.json")

    result = PromptInjectionProbe().evaluate(fixture)

    assert result.metadata["detected_prompt_injection"] is True
    assert result.metadata["prompt_tool_ledger_persisted"] is True
    assert "candidate_firewall_candidate_unverified" in result.metadata["firewall_issue_codes"]
    assert "r14_prompt_injection_firewall_blocked" in result.failure_codes


def test_participation_speculation_probe_uses_requirement_compiler_and_firewall() -> None:
    fixture = _read_fixture(FIXTURE_ROOT / "participation_speculation_without_provenance.json")

    result = ParticipationSpeculationProbe().evaluate(fixture)

    assert result.metadata["participation_requirement_statuses"] == ["blocked"]
    assert result.metadata["participation_blocker_codes"] == [
        "llm_speculation_not_participation"
    ]
    assert "candidate_firewall_rejected_speculation" in result.metadata["firewall_issue_codes"]
    assert "r14_participation_speculation_blocked" in result.failure_codes
