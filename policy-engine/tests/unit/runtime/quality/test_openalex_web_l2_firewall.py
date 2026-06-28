"""Tests for the web-bundle to L2 authority firewall."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from polisyos.runtime.quality.candidate_firewall import (
    CandidateFirewallError,
    assert_l2_claim_authority_span_grounded,
)


class _DeterministicSpanSupportClient:
    def __init__(self, *, decision: str, confidence: float) -> None:
        self.decision = decision
        self.confidence = confidence
        self.calls: list[dict[str, object]] = []

    async def generate(
        self,
        *,
        messages: list[dict[str, object]],
        tools: list[dict[str, object]],
        temperature: float | None = None,
        seed: int | None = None,
    ) -> SimpleNamespace:
        self.calls.append(
            {
                "messages": messages,
                "tools": tools,
                "temperature": temperature,
                "seed": seed,
            }
        )
        return SimpleNamespace(
            content="",
            tool_calls=[
                SimpleNamespace(
                    id="call-span-support",
                    name="layer3_gy_record_span_support_judgment",
                    arguments={
                        "decision": self.decision,
                        "confidence": self.confidence,
                        "rationale": "deterministic test judgment",
                    },
                )
            ],
            usage=SimpleNamespace(total_tokens=5),
            raw={"deterministic_replay_key": "test-only"},
        )


def test_web_bundle_cannot_satisfy_l2_claim_authority_without_validated_span() -> None:
    with pytest.raises(CandidateFirewallError, match="web_bundle_l2_authority_blocked"):
        assert_l2_claim_authority_span_grounded(
            {
                "claim_authority": {
                    "source_kind": "scholar.web_evidence_bundle",
                    "source_ref": "webkb.123",
                    "authority_tier": "design_tier_l2",
                }
            },
            surface="l2_skg_ingest",
        )


@pytest.mark.parametrize(
    "payload",
    [
        {
            "claim_authority": {
                "source_kind": "scholar.web_evidence_bundle",
                "source_ref": "webkb.123",
                "authority_tier": "design_tier_l2",
                "span_grounding_status": "validated_supporting",
                "validated_span_grounding_ref": "openalex-span-grounding://W1/c1",
            }
        },
        {
            "claim_authority": {
                "source_kind": "openalex_span_grounded_claim",
                "source_ref": "openalex-span-grounding://W1/c1",
                "authority_tier": "design_tier_l2",
                "span_grounding_status": "validated_supporting",
                "validated_span_grounding_ref": "openalex-span-grounding://W1/c1",
            }
        },
        {
            "claim_authority": {
                "source_kind": "openalex_span_grounded_claim",
                "source_ref": "openalex-span-grounding://W1/c1",
                "authority_tier": "design_tier_l2",
            }
        },
    ],
)
def test_l2_claim_authority_blocks_self_attested_grounding(payload: dict[str, object]) -> None:
    with pytest.raises(CandidateFirewallError, match="l2_claim_authority_grounding_unresolved"):
        assert_l2_claim_authority_span_grounded(payload, surface="l2_skg_ingest")


def test_validated_span_grounded_claim_can_satisfy_l2_claim_authority_after_resolution() -> None:
    payload = {
        "claim_authority": {
            "source_kind": "openalex_span_grounded_claim",
            "source_ref": "openalex-span-grounding://W1/c1",
            "authority_tier": "design_tier_l2",
            "span_grounding_status": "validated_supporting",
            "validated_span_grounding_ref": "openalex-span-grounding://W1/c1",
            "claim_id": "c1",
            "claim_text": "policy intervention -> employment: The intervention reduced employment.",
        }
    }

    def _resolve(ref: str) -> dict[str, object] | None:
        assert ref == "openalex-span-grounding://W1/c1"
        return {
            "grounding_ref": ref,
            "claim_id": "c1",
            "claim_text": payload["claim_authority"]["claim_text"],
            "span_text": "We find that the intervention reduced employment.",
            "cause": "policy intervention",
            "effect": "employment",
            "direction": "negative",
            "design_family": "did",
            "support_status": "validated_supporting",
            "authority_tier": "design_tier_l2",
            "source_content_sha256": "sha256:test",
        }

    client = _DeterministicSpanSupportClient(decision="entails", confidence=0.93)
    assert (
        assert_l2_claim_authority_span_grounded(
            payload,
            surface="l2_skg_ingest",
            grounding_resolver=_resolve,
            span_support_client=client,
        )
        == payload
    )
    assert client.calls


def test_l2_claim_authority_revalidates_resolved_grounding_content() -> None:
    payload = {
        "claim_authority": {
            "source_kind": "openalex_span_grounded_claim",
            "source_ref": "openalex-span-grounding://W1/c1",
            "authority_tier": "design_tier_l2",
            "span_grounding_status": "validated_supporting",
            "validated_span_grounding_ref": "openalex-span-grounding://W1/c1",
        }
    }

    def _self_attested_only(ref: str) -> dict[str, object] | None:
        return {
            "grounding_ref": ref,
            "support_status": "validated_supporting",
            "authority_tier": "design_tier_l2",
            "source_content_sha256": "sha256:test",
        }

    with pytest.raises(CandidateFirewallError, match="l2_claim_authority_grounding_unvalidated"):
        assert_l2_claim_authority_span_grounded(
            payload,
            surface="l2_skg_ingest",
            grounding_resolver=_self_attested_only,
        )


def test_l2_claim_authority_blocks_borrowed_grounding_for_another_claim() -> None:
    payload = {
        "claim_authority": {
            "source_kind": "openalex_span_grounded_claim",
            "source_ref": "openalex-span-grounding://W1/other",
            "authority_tier": "design_tier_l2",
            "span_grounding_status": "validated_supporting",
            "validated_span_grounding_ref": "openalex-span-grounding://W1/other",
            "claim_id": "candidate-claim",
            "claim_text": "Cash transfers increased school attendance.",
        }
    }

    def _borrowed(ref: str) -> dict[str, object]:
        return {
            "grounding_ref": ref,
            "claim_id": "other-claim",
            "claim_text": "Policy intervention reduced employment.",
            "span_text": "We find that the intervention reduced employment.",
            "cause": "policy intervention",
            "effect": "employment",
            "direction": "negative",
            "design_family": "did",
            "support_status": "validated_supporting",
            "authority_tier": "design_tier_l2",
            "source_content_sha256": "sha256:test",
        }

    with pytest.raises(CandidateFirewallError, match="l2_claim_authority_grounding_unvalidated"):
        assert_l2_claim_authority_span_grounded(
            payload,
            surface="l2_skg_ingest",
            grounding_resolver=_borrowed,
            span_support_client=_DeterministicSpanSupportClient(
                decision="entails",
                confidence=0.95,
            ),
        )


def test_l2_claim_authority_blocks_resolver_backed_non_entailing_span() -> None:
    payload = {
        "claim_authority": {
            "source_kind": "openalex_span_grounded_claim",
            "source_ref": "openalex-span-grounding://W1/c1",
            "authority_tier": "design_tier_l2",
            "span_grounding_status": "validated_supporting",
            "validated_span_grounding_ref": "openalex-span-grounding://W1/c1",
            "claim_id": "c1",
            "claim_text": (
                "We estimate the effect of cash transfers on school attendance. "
                "Therefore, cash transfers increased school attendance."
            ),
        }
    }

    def _non_entailing(ref: str) -> dict[str, object]:
        span = "We estimate the effect of cash transfers on school attendance."
        return {
            "grounding_ref": ref,
            "claim_id": "c1",
            "claim_text": payload["claim_authority"]["claim_text"],
            "span_text": span,
            "cause": "cash transfers",
            "effect": "school attendance",
            "direction": "positive",
            "design_family": "did",
            "support_status": "validated_supporting",
            "authority_tier": "design_tier_l2",
            "source_content_sha256": "sha256:test",
        }

    with pytest.raises(CandidateFirewallError, match="l2_claim_authority_grounding_unvalidated"):
        assert_l2_claim_authority_span_grounded(
            payload,
            surface="l2_skg_ingest",
            grounding_resolver=_non_entailing,
            span_support_client=_DeterministicSpanSupportClient(
                decision="neutral",
                confidence=0.96,
            ),
        )


def test_l2_claim_authority_blocks_same_id_conflicting_resolved_claim_text() -> None:
    payload = {
        "claim_authority": {
            "source_kind": "openalex_span_grounded_claim",
            "source_ref": "openalex-span-grounding://W1/c1",
            "authority_tier": "design_tier_l2",
            "span_grounding_status": "validated_supporting",
            "validated_span_grounding_ref": "openalex-span-grounding://W1/c1",
            "claim_id": "c1",
            "claim_text": "Cash transfers increased school attendance.",
        }
    }

    def _conflicting_same_id(ref: str) -> dict[str, object]:
        return {
            "grounding_ref": ref,
            "claim_id": "c1",
            "claim_text": "Cash transfers reduced school attendance.",
            "span_text": "We find that cash transfers increased school attendance.",
            "cause": "cash transfers",
            "effect": "school attendance",
            "direction": "positive",
            "design_family": "did",
            "support_status": "validated_supporting",
            "authority_tier": "design_tier_l2",
            "source_content_sha256": "sha256:test",
        }

    with pytest.raises(CandidateFirewallError, match="l2_claim_authority_grounding_unvalidated"):
        assert_l2_claim_authority_span_grounded(
            payload,
            surface="l2_skg_ingest",
            grounding_resolver=_conflicting_same_id,
            span_support_client=_DeterministicSpanSupportClient(
                decision="entails",
                confidence=0.96,
            ),
        )
