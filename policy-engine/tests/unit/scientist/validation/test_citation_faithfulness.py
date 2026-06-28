from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from polisyos.scientist.validation.citation_faithfulness import (
    BLOCKING_CITATION_LABELS,
    SCHEMA_VERSION,
    build_citation_faithfulness_report,
    build_policy_context_citation_faithfulness_report,
    build_span_support_replay_manifest,
    evaluate_span_claim_entailment,
    explain_span_support_replay_drift,
)

GOLDEN_PATH = (
    Path(__file__).parents[3]
    / "_golden"
    / "quality"
    / "citation_faithfulness"
    / "cases.json"
)


def _golden() -> dict[str, object]:
    return json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))


def _cases() -> list[dict[str, object]]:
    return list(_golden()["cases"])  # type: ignore[index]


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
            model="test-raw-gateway-model",
            provider="test-gateway-provider",
            request_id="test-gateway-request",
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
            usage=SimpleNamespace(total_tokens=7),
            raw={"deterministic_replay_key": "test-only"},
        )


class _GatewayWitnessClient(_DeterministicSpanSupportClient):
    provider = "openai"


class _SimulatedSpanSupportClient(_DeterministicSpanSupportClient):
    provider = "simulated"


class _RecordedSpanSupportClient(_DeterministicSpanSupportClient):
    provider = "recorded-replay"


def _causal_claim(text: str, *, direction: str = "positive") -> dict[str, object]:
    return {
        "claim_id": "claim.audit",
        "claim_family": "causal",
        "claim_text": text,
        "direction": direction,
        "data_refs": ["openalex:test"],
        "source_attribution": "openalex:test",
        "method_refs": ["did"],
        "identification_strategy": "did",
        "citation_refs": ["span.audit"],
    }


def _span(text: str) -> dict[str, object]:
    return {
        "ref_id": "span.audit",
        "source_id": "openalex:test",
        "section": "abstract",
        "text": text,
        "source_content_sha256": "sha256:test",
    }


@pytest.mark.parametrize("case", _cases(), ids=lambda case: case["case_id"])
def test_golden_cases_label_cited_evidence_offline(case: dict[str, object]) -> None:
    report = build_citation_faithfulness_report(
        claims=[case["claim"]],
        evidence=case["evidence"],
    )

    labels_by_ref = {
        citation["citation_ref"]: citation["label"]
        for claim in report["claims"]
        for citation in claim["citations"]
    }

    assert report["schema_version"] == SCHEMA_VERSION
    assert report["status"] == case["expected_status"]
    assert labels_by_ref == case["expected_labels"]
    assert report["live_llm_judging_enabled"] is False


def test_required_mismatch_dimensions_are_represented_in_fixtures() -> None:
    golden = _golden()
    represented = {
        str(case.get("mismatch_dimension"))
        for case in _cases()
        if case.get("mismatch_dimension")
    }

    assert represented == set(golden["required_mismatch_dimensions"])


def test_public_factual_and_legal_claims_cannot_pass_with_bad_refs() -> None:
    bad_public_cases = [
        case
        for case in _cases()
        if case["case_id"]
        in {
            "contradicts_public_legal_claim",
            "irrelevant_public_factual_claim",
        }
    ]

    for case in bad_public_cases:
        report = build_citation_faithfulness_report(
            claims=[case["claim"]],
            evidence=case["evidence"],
        )
        labels = {
            citation["label"]
            for claim in report["claims"]
            for citation in claim["citations"]
        }
        blocking_codes = {issue["code"] for issue in report["issues"]}

        assert report["status"] == "fail"
        assert labels & BLOCKING_CITATION_LABELS
        assert "public_claim_has_unfaithful_citation" in blocking_codes


def test_public_factual_claim_without_citation_fails_claim_status() -> None:
    report = build_citation_faithfulness_report(
        claims=[
            {
                "claim_id": "fact.no_cite",
                "claim_family": "factual",
                "public": True,
                "text": "The programme increased firm survival rates.",
            }
        ],
        evidence=[],
    )

    assert report["status"] == "fail"
    assert report["claims"][0]["status"] == "fail"
    assert {issue["code"] for issue in report["issues"]} == {
        "public_claim_missing_citation"
    }


def test_policy_context_helper_builds_offline_evidence_from_runtime_payloads() -> None:
    report = build_policy_context_citation_faithfulness_report(
        claims=[
            {
                "claim_id": "legal.supported",
                "claim_family": "legal",
                "public": True,
                "text": "The rule authorizes targeted credit support.",
                "norm_refs": ["norm.ua.credit_eligibility"],
            }
        ],
        normative_evidence={
            "applied_norms": [
                {
                    "norm_id": "norm.ua.credit_eligibility",
                    "legal_text": "The rule authorizes targeted credit support for eligible firms.",
                }
            ]
        },
        fabric_retrieval_trace={"selected_sources": []},
    )

    assert report["status"] == "pass"
    assert report["claims"][0]["citations"][0]["label"] == "supports"
    assert report["live_llm_judging_enabled"] is False


def test_checker_reports_residual_risk_and_false_pass_limits() -> None:
    case = next(
        item for item in _cases() if item["case_id"] == "supports_public_legal_claim"
    )

    report = build_citation_faithfulness_report(
        claims=[case["claim"]],
        evidence=case["evidence"],
    )

    assert report["residual_risk"]["level"] == "medium"
    assert report["residual_risk"]["deterministic_only"] is True
    assert report["false_pass_limits"]
    assert "semantic_paraphrase_not_proven" in report["false_pass_limits"]
    assert "metadata_omission_can_hide_scope_mismatch" in report["false_pass_limits"]


def test_span_claim_support_uses_injected_agent_judge_not_lexical_containment() -> None:
    non_entailing_client = _DeterministicSpanSupportClient(
        decision="neutral",
        confidence=0.96,
    )
    copied_method_span = "We estimate the effect of cash transfers on school attendance."

    rejected = evaluate_span_claim_entailment(
        claim=_causal_claim(
            copied_method_span + " Therefore, cash transfers increased school attendance."
        ),
        evidence=_span(copied_method_span),
        client=non_entailing_client,
    )

    assert non_entailing_client.calls
    assert rejected["status"] == "fail"
    assert rejected["label"] == "irrelevant"
    assert "span_support_agent_neutral" in rejected["reason_codes"]

    paraphrase_client = _DeterministicSpanSupportClient(
        decision="entails",
        confidence=0.91,
    )
    accepted = evaluate_span_claim_entailment(
        claim=_causal_claim("School attendance improved after the stipend program."),
        evidence=_span("We find that the program raised student participation."),
        client=paraphrase_client,
    )

    assert accepted["status"] == "pass"
    assert accepted["label"] == "supports"
    assert accepted["score"] == pytest.approx(0.91)
    assert "span_support_agent_entails_claim" in accepted["reason_codes"]


def test_span_claim_support_fails_closed_without_real_agent(monkeypatch: pytest.MonkeyPatch) -> None:
    import polisyos.scientist.validation.citation_faithfulness as cf

    monkeypatch.setattr(cf, "_create_default_span_support_client", lambda: None)

    result = evaluate_span_claim_entailment(
        claim=_causal_claim("Cash transfers increased school attendance."),
        evidence=_span("We find that cash transfers increased school attendance."),
    )

    assert result["status"] == "fail"
    assert result["label"] == "unverifiable"
    assert "entailment_verifier_unavailable" in result["reason_codes"]
    assert "layer3_gy_span_support_unverified" in result["blocker_codes"]


def test_span_claim_support_default_path_constructs_gateway_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import polisyos.runtime.quality.proving_ground.bounded_request_agent as g6

    client = _GatewayWitnessClient(decision="entails", confidence=0.92)
    created: list[dict[str, object]] = []

    def _create(**kwargs: object) -> _GatewayWitnessClient:
        created.append(kwargs)
        return client

    monkeypatch.setattr(g6, "create_traced_gateway_client", _create)

    result = evaluate_span_claim_entailment(
        claim=_causal_claim("School attendance improved after the stipend program."),
        evidence=_span("The program raised student participation."),
    )

    assert created == [
        {
            "model_name": "MiniMaxAI/MiniMax-M2.7",
            "provider_hint": "polisyos-gy-span-support",
            "run_id": "layer3-gy-span-support-runtime",
            "model_variant_id": "layer3-gy-span-support-judge-v1",
        }
    ]
    assert client.calls
    assert client.calls[0]["temperature"] == 0.0
    assert client.calls[0]["seed"] == 0
    assert result["status"] == "pass"
    assert result["label"] == "supports"
    assert result["agent_judgment"]["model_id"] == "test-raw-gateway-model"
    assert result["agent_judgment"]["provider"] == "test-gateway-provider"
    assert result["agent_judgment"]["request_id"] == "test-gateway-request"


def test_span_claim_support_default_path_honors_gateway_model_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import polisyos.runtime.quality.proving_ground.bounded_request_agent as g6

    client = _GatewayWitnessClient(decision="entails", confidence=0.92)
    created: list[dict[str, object]] = []

    def _create(**kwargs: object) -> _GatewayWitnessClient:
        created.append(kwargs)
        return client

    monkeypatch.setenv("POLISYOS_LLM_GATEWAY_SPAN_SUPPORT_MODEL", "custom/live-model")
    monkeypatch.setattr(g6, "create_traced_gateway_client", _create)

    result = evaluate_span_claim_entailment(
        claim=_causal_claim("School attendance improved after the stipend program."),
        evidence=_span("The program raised student participation."),
    )

    assert created[0]["model_name"] == "custom/live-model"
    assert created[0]["model_variant_id"] == "layer3-gy-span-support-judge-v1"
    assert result["status"] == "pass"


@pytest.mark.parametrize(
    "client",
    [
        _SimulatedSpanSupportClient(decision="entails", confidence=0.99),
        _RecordedSpanSupportClient(decision="entails", confidence=0.99),
    ],
)
def test_span_claim_support_rejects_non_production_default_clients(
    monkeypatch: pytest.MonkeyPatch,
    client: _DeterministicSpanSupportClient,
) -> None:
    import polisyos.runtime.quality.proving_ground.bounded_request_agent as g6

    monkeypatch.setattr(g6, "create_traced_gateway_client", lambda **_: client)

    result = evaluate_span_claim_entailment(
        claim=_causal_claim("School attendance improved after the stipend program."),
        evidence=_span("The stipend program increased school attendance."),
    )

    assert not client.calls
    assert result["status"] == "fail"
    assert result["label"] == "unverifiable"
    assert "entailment_verifier_unavailable" in result["reason_codes"]
    assert "layer3_gy_span_support_unverified" in result["blocker_codes"]


def test_span_support_replay_manifest_explains_judgment_drift() -> None:
    claim = _causal_claim("School attendance improved after the stipend program.")
    evidence = _span("The program raised student participation.")
    baseline = build_span_support_replay_manifest(
        claim=claim,
        evidence=evidence,
        judgment={"decision": "entails", "confidence": 0.91},
    )
    replay = build_span_support_replay_manifest(
        claim=claim,
        evidence=evidence,
        judgment={"decision": "neutral", "confidence": 0.91},
    )

    drift = explain_span_support_replay_drift(
        baseline_manifest=baseline,
        replay_manifest=replay,
    )

    assert drift["status"] == "unexplained_drift"
    assert drift["production_readiness"] == "fail"
    assert {
        difference["path"] for difference in drift["differences"]
    } >= {"$.prompt_tool_parser_ledger.judgment.decision"}
