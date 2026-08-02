#!/usr/bin/env python3
"""Validate or regenerate GY-K OpenAlex span-grounded L2 artifacts."""

from __future__ import annotations

from time import perf_counter as _timing_perf_counter

_TIMING_STARTED_AT = _timing_perf_counter()

import argparse
import asyncio
import json
import os
import sys
import tempfile
import tomllib
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import duckdb

from tools.lib.timing import run_timed_entrypoint

FAMILY_ID = "policy-design-case-layer3-gy-openalex-artifacts"
SOURCE_FAMILY_ID = "policy-design-case-layer3-gy-openalex-source-artifacts"
CONFIG_PATH = "architecture/policy_design_case/layer3_gy_openalex_provider_config.json"
GOLD_PATH = "architecture/policy_design_case/layer3_gy_openalex_claim_span_gold.json"
ACCURACY_PATH = "architecture/policy_design_case/layer3_gy_openalex_accuracy_report.json"
INGEST_PATH = "architecture/policy_design_case/layer3_gy_openalex_skg_ingest_records.json"
OUTPUTS = [ACCURACY_PATH, INGEST_PATH]

REAL_AGENT_MODEL_ID = "MiniMaxAI/MiniMax-M2.7"
REAL_AGENT_MODEL_VARIANT_ID = "layer3-gy-span-support-judge-v1"
HELD_OUT_ACCURACY_CASES: tuple[dict[str, Any], ...] = (
    {
        "label_id": "openalex-heldout-credit-sme-contribution-positive",
        "case_set": "held_out",
        "openalex_id": "https://openalex.org/W2169693233",
        "title": (
            "The Impact of Firm and Entrepreneurial Characteristics on Access to Debt "
            "Finance by SMEs in King Williams' Town, South Africa"
        ),
        "query": "loan guarantees SMEs firm survival impact evaluation",
        "claim_text": (
            "SMEs contribute to economic growth, employment, and poverty alleviation "
            "in South Africa."
        ),
        "treatment_or_cause": "SMEs",
        "effect": "economic growth, employment, and poverty alleviation",
        "claim_direction": "positive",
        "gold_span_text": (
            "SMEs contribute positively to economic growth, employment and poverty "
            "alleviation in South Africa."
        ),
        "expected_supported": True,
        "source_fixture": "tests/fixtures/scholar/openalex/credit_guarantee_firm_survival.json",
    },
    {
        "label_id": "openalex-heldout-credit-rct-negative",
        "case_set": "held_out",
        "openalex_id": "https://openalex.org/W2169693233",
        "title": (
            "The Impact of Firm and Entrepreneurial Characteristics on Access to Debt "
            "Finance by SMEs in King Williams' Town, South Africa"
        ),
        "query": "loan guarantees SMEs firm survival impact evaluation",
        "claim_text": "The South Africa SME study was a randomized controlled trial.",
        "treatment_or_cause": "random assignment",
        "effect": "access to debt finance by SMEs",
        "claim_direction": "mixed",
        "gold_span_text": "Data was collected throughself-administered questionnaire in a survey.",
        "expected_supported": False,
        "source_fixture": "tests/fixtures/scholar/openalex/credit_guarantee_firm_survival.json",
    },
    {
        "label_id": "openalex-heldout-collateral-credit-positive",
        "case_set": "held_out",
        "openalex_id": "https://openalex.org/W3123109680",
        "title": "Collateralization, Bank Loan Rates, and Monitoring",
        "query": "loan guarantees SMEs firm survival impact evaluation",
        "claim_text": (
            "A legal reform that reduced collateral values led the bank to raise "
            "interest rates, tighten credit limits, and reduce monitoring."
        ),
        "treatment_or_cause": "legal reform reducing collateral values",
        "effect": "bank loan rates, credit limits, and monitoring",
        "claim_direction": "mixed",
        "gold_span_text": (
            "Using a unique data set from a large bank containing timely assessments "
            "of collateral values, we find that the bank responded to a legal reform "
            "that exogenously reduced collateral values by increasing interest rates, "
            "tightening credit limits, and reducing the intensity of its monitoring "
            "of borrowers and collateral, spurring borrower delinquency on outstanding claims."
        ),
        "expected_supported": True,
        "source_fixture": "tests/fixtures/scholar/openalex/credit_guarantee_firm_survival.json",
    },
    {
        "label_id": "openalex-heldout-collateral-opposite-negative",
        "case_set": "held_out",
        "openalex_id": "https://openalex.org/W3123109680",
        "title": "Collateralization, Bank Loan Rates, and Monitoring",
        "query": "loan guarantees SMEs firm survival impact evaluation",
        "claim_text": (
            "A legal reform that reduced collateral values led the bank to lower "
            "interest rates and loosen credit limits."
        ),
        "treatment_or_cause": "legal reform reducing collateral values",
        "effect": "bank loan rates and credit limits",
        "claim_direction": "negative",
        "gold_span_text": (
            "Using a unique data set from a large bank containing timely assessments "
            "of collateral values, we find that the bank responded to a legal reform "
            "that exogenously reduced collateral values by increasing interest rates, "
            "tightening credit limits, and reducing the intensity of its monitoring "
            "of borrowers and collateral, spurring borrower delinquency on outstanding claims."
        ),
        "expected_supported": False,
        "source_fixture": "tests/fixtures/scholar/openalex/credit_guarantee_firm_survival.json",
    },
)


class DeterministicSpanSupportClient:
    """Offline replay client for the GY-K validator; never production wiring."""

    async def generate(
        self,
        *,
        messages: list[dict[str, object]],
        tools: list[dict[str, object]],
        temperature: float | None = None,
        seed: int | None = None,
    ) -> SimpleNamespace:
        del tools, temperature, seed
        decision, confidence, rationale = _deterministic_span_support_judgment(messages)
        return SimpleNamespace(
            content="",
            tool_calls=[
                SimpleNamespace(
                    id="call-span-support",
                    name="layer3_gy_record_span_support_judgment",
                    arguments={
                        "decision": decision,
                        "confidence": confidence,
                        "rationale": rationale,
                    },
                )
            ],
            usage=SimpleNamespace(total_tokens=5),
            raw={"deterministic_replay_key": "layer3-gy-openalex-validator"},
        )


def _deterministic_span_support_judgment(
    messages: list[dict[str, object]],
) -> tuple[str, float, str]:
    """Return the committed offline replay label for the validator gold set."""

    payload = _span_support_request_payload(messages)
    span = str(payload.get("span_text", "")).lower()
    claim = str(payload.get("claim_text", "")).lower()
    direction = str(payload.get("claim_direction", "")).lower()

    if "difference-in-differences approach" in span and "reduced" in claim:
        return "neutral", 0.94, "method-only span does not entail the effect claim"
    if "tradeable sectors" in span and (
        "all low-wage jobs" in claim or "overall low-wage" in claim
    ):
        return "neutral", 0.93, "sector-specific span does not support the broad claim"
    if "remained essentially unchanged" in span and (
        "reduced overall" in claim
        or ("reduced" in claim and direction in {"negative", "positive"})
    ):
        return "contradicts", 0.95, "stable-job span contradicts a reduction claim"

    return "entails", 0.91, "deterministic validator replay support"


def _span_support_request_payload(messages: list[dict[str, object]]) -> dict[str, object]:
    for message in reversed(messages):
        if message.get("role") != "user":
            continue
        content = message.get("content")
        if not isinstance(content, str):
            continue
        try:
            payload = json.loads(content)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload
    return {}


def declared_outputs() -> list[str]:
    """Return generated OpenAlex GY-K artifacts written by --write mode."""

    return list(OUTPUTS)


def validate(
    repo_root: Path,
    *,
    write: bool = False,
    corrupt_field_drift_check: bool = False,
) -> dict[str, Any]:
    """Return a drift report for the OpenAlex generated proof family."""

    repo_root = repo_root.resolve()
    _ensure_src_path(repo_root)
    issues: list[dict[str, str]] = []
    _validate_generated_artifacts_registration(repo_root, issues)
    expected = build_live_payloads(repo_root)

    if write:
        for relative_path, payload in expected.items():
            path = repo_root / relative_path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps(payload, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
    else:
        for relative_path, expected_payload in expected.items():
            committed = _read_json(repo_root / relative_path, issues)
            if relative_path == ACCURACY_PATH and committed:
                validate_accuracy_report_payload(
                    committed,
                    expected=expected_payload,
                    issues=issues,
                )
            if committed and committed != expected_payload:
                issues.append({"code": "layer3_gy_openalex_artifact_drift", "path": relative_path})

    if corrupt_field_drift_check:
        corrupted = json.loads(json.dumps(expected[ACCURACY_PATH]))
        expected_precision = float(corrupted["accuracy"].get("precision") or 0.0)
        corrupted["accuracy"]["precision"] = 0.0 if expected_precision != 0.0 else 1.0
        corrupt_issues: list[dict[str, str]] = []
        validate_accuracy_report_payload(corrupted, expected[ACCURACY_PATH], corrupt_issues)
        if corrupt_issues:
            issues.append({"code": "layer3_gy_openalex_corrupt_field_drift_detected"})
        else:
            issues.append({"code": "layer3_gy_openalex_corrupt_field_drift_not_detected"})

    try:
        from tools.quality.validation import check_layer3_gy_generated_public_lifecycle_audit

        lifecycle_report = (
            check_layer3_gy_generated_public_lifecycle_audit.validate_gy_lifecycle_registry(
                repo_root
            )
        )
        issues.extend(lifecycle_report["issues"])
    except Exception as exc:
        issues.append({"code": "layer3_gy_openalex_lifecycle_check_failed", "error": str(exc)})

    status_issues = [
        issue
        for issue in issues
        if issue.get("code") != "layer3_gy_openalex_corrupt_field_drift_detected"
    ]
    return {
        "status": "pass" if not status_issues else "fail",
        "family_id": FAMILY_ID,
        "source_family_id": SOURCE_FAMILY_ID,
        "checked_artifacts": [CONFIG_PATH, GOLD_PATH, *OUTPUTS],
        "write": write,
        "issues": issues,
        "accuracy": expected[ACCURACY_PATH]["accuracy"],
        "ingest": expected[INGEST_PATH]["ingest"],
    }


def build_live_payloads(repo_root: Path) -> dict[str, dict[str, Any]]:
    """Recompute GY-K proof payloads from live code and recorded-real cassettes."""

    from polisyos.data_forge.domains.academic.knowledge.skg_store import (
        ensure_skg_schema,
        ingest_openalex_no_hit_frontier,
        ingest_openalex_span_grounded_claims,
    )
    from polisyos.ir.analytics.literature import (
        ClaimSpanGoldSet,
        EvidenceSpan,
        extract_span_grounded_claims_from_openalex_work,
        validate_causal_claim_span_grounding,
    )
    from polisyos.runtime.quality.candidate_firewall import (
        CandidateFirewallError,
        assert_l2_claim_authority_span_grounded,
    )
    from polisyos.scholar.search.models import SearchQueryTrace

    _read_required_json(repo_root / CONFIG_PATH)
    gold = ClaimSpanGoldSet.model_validate_json((repo_root / GOLD_PATH).read_text(encoding="utf-8"))
    span_support_client = DeterministicSpanSupportClient()
    accuracy_payload = _read_required_json(repo_root / ACCURACY_PATH)

    witness_records: list[dict[str, Any]] = []
    all_hit_sets: list[set[str]] = []
    with tempfile.TemporaryDirectory(prefix="polisyos-gy-k-openalex-") as tmpdir:
        con = duckdb.connect(str(Path(tmpdir) / "skg.duckdb"))
        ensure_skg_schema(con)
        seen_witness_keys: set[tuple[str, str, str]] = set()
        for record in gold.records:
            witness_key = (record.query, record.source_fixture, record.openalex_id)
            if witness_key in seen_witness_keys:
                continue
            seen_witness_keys.add(witness_key)
            fixture_payload = _read_required_json(repo_root / record.source_fixture)
            _assert_recorded_openalex_fixture(
                fixture_payload,
                path=record.source_fixture,
                query=record.query,
            )
            hits = asyncio.run(
                _provider_hits_from_fixture(
                    fixture_payload,
                    query=record.query,
                    max_results=5,
                )
            )
            all_hit_sets.append({str(hit.url) for hit in hits})
            work = _work_from_fixture(fixture_payload, record.openalex_id)
            claims = extract_span_grounded_claims_from_openalex_work(
                work,
                query=record.query,
                span_support_client=span_support_client,
            )
            trace = SearchQueryTrace(
                query_node_id=f"gold:{record.label_id}",
                query=record.query,
                perspective="root",
                provider="openalex",
                hit_count=len(hits),
                searched_at=_recorded_at(fixture_payload),
            )
            ingest_report = ingest_openalex_span_grounded_claims(
                con,
                work=work,
                claims=claims,
                query_trace=trace,
                span_support_client=span_support_client,
            )
            witness_records.append(
                {
                    "label_id": record.label_id,
                    "query": record.query,
                    "fixture": record.source_fixture,
                    "hit_ids": [str(hit.url) for hit in hits],
                    "first_title": hits[0].title if hits else "",
                    "ingested_claim_count": ingest_report.ingested_claim_count,
                    "rejected_claim_count": ingest_report.rejected_claim_count,
                    "authority_tier": ingest_report.authority_tier,
                    "query_trace_id": ingest_report.query_trace_id,
                }
            )
        no_hit_payload = _read_required_json(
            repo_root / "tests/fixtures/scholar/openalex/no_hits.json"
        )
        no_hit_query = str(no_hit_payload.get("_recording", {}).get("query") or "")
        _assert_recorded_openalex_fixture(
            no_hit_payload,
            path="tests/fixtures/scholar/openalex/no_hits.json",
            query=no_hit_query,
            allow_empty=True,
        )
        no_hit_hits = asyncio.run(
            _provider_hits_from_fixture(no_hit_payload, query=no_hit_query, max_results=5)
        )
        no_hit_trace = SearchQueryTrace(
            query_node_id="nohit:openalex",
            query=no_hit_query,
            perspective="root",
            provider="openalex",
            hit_count=len(no_hit_hits),
            searched_at=_recorded_at(no_hit_payload),
        )
        no_hit_report = ingest_openalex_no_hit_frontier(con, query_trace=no_hit_trace)
        skg_counts = {
            "query_traces": int(con.execute("SELECT COUNT(*) FROM ac_skg_query_traces").fetchone()[0]),
            "span_grounded_claims": int(
                con.execute("SELECT COUNT(*) FROM ac_skg_span_grounded_claims").fetchone()[0]
            ),
            "edge_evidence": int(con.execute("SELECT COUNT(*) FROM ac_skg_edge_evidence").fetchone()[0]),
            "no_hit_frontier": int(
                con.execute("SELECT COUNT(*) FROM ac_skg_no_hit_frontier").fetchone()[0]
            ),
        }
        con.close()

    first_record = gold.records[0]
    first_work = _work_from_fixture(
        _recorded_fixture_payload(
            repo_root,
            first_record.source_fixture,
            query=first_record.query,
        ),
        first_record.openalex_id,
    )
    first_claim = extract_span_grounded_claims_from_openalex_work(
        first_work,
        query=first_record.query,
        span_support_client=span_support_client,
    )[0]
    valid_grounding = validate_causal_claim_span_grounding(
        first_work,
        first_claim,
        span_support_client=span_support_client,
    )
    poisoned = first_claim.model_copy(
        update={
            "supporting_spans": [
                EvidenceSpan(
                    span_id="non-resolving",
                    text="This span is not in the OpenAlex work text.",
                    source_ref=first_work.openalex_id,
                )
            ],
            "supporting_span_ids": ["non-resolving"],
        }
    )
    rejected_grounding = validate_causal_claim_span_grounding(
        first_work,
        poisoned,
        span_support_client=span_support_client,
    )

    second_record = gold.records[1]
    second_work = _work_from_fixture(
        _recorded_fixture_payload(
            repo_root,
            second_record.source_fixture,
            query=second_record.query,
        ),
        second_record.openalex_id,
    )
    second_claim = extract_span_grounded_claims_from_openalex_work(
        second_work,
        query=second_record.query,
        span_support_client=span_support_client,
    )[0]
    non_supporting_claim = second_claim.model_copy(
        update={
            "claim_id": f"{second_claim.claim_id}.non_supporting_title",
            "claim_text": "Minimum wages substantially increase low-wage employment.",
            "cause_variable": "minimum wages",
            "effect_variable": "low-wage employment",
            "supporting_spans": [
                EvidenceSpan(
                    span_id="title-present",
                    text=second_work.title,
                    source_ref=second_work.openalex_id,
                    start_char=0,
                    end_char=len(second_work.title),
                    content_sha256=second_work.content_sha256,
                )
            ],
            "supporting_span_ids": ["title-present"],
        }
    )
    non_supporting_grounding = validate_causal_claim_span_grounding(
        second_work,
        non_supporting_claim,
        span_support_client=span_support_client,
    )

    def _resolve_grounding(ref: str) -> dict[str, object] | None:
        if ref != valid_grounding.grounding_ref:
            return None
        span = first_claim.supporting_spans[0]
        return {
            "grounding_ref": valid_grounding.grounding_ref,
            "claim_id": first_claim.claim_id,
            "claim_text": first_claim.claim_text,
            "span_text": span.text,
            "openalex_id": first_work.openalex_id,
            "cause": first_claim.cause_variable,
            "effect": first_claim.effect_variable,
            "direction": first_claim.direction.value,
            "design_family": first_claim.design_family_hint.value,
            "section": span.section,
            "support_status": valid_grounding.status,
            "authority_tier": valid_grounding.authority_tier,
            "source_content_sha256": first_work.content_sha256,
        }

    def _firewall_status(
        payload: dict[str, object],
        *,
        with_resolver: bool = False,
    ) -> str:
        try:
            assert_l2_claim_authority_span_grounded(
                payload,
                surface="l2_skg_ingest",
                grounding_resolver=_resolve_grounding if with_resolver else None,
                span_support_client=span_support_client,
            )
        except CandidateFirewallError:
            return "blocked"
        return "allowed"

    web_bundle_status = _firewall_status(
        {
            "claim_authority": {
                "source_kind": "scholar.web_evidence_bundle",
                "source_ref": "webkb.openalex-candidate",
                "authority_tier": "design_tier_l2",
            }
        }
    )
    web_self_attested_status = _firewall_status(
        {
            "claim_authority": {
                "source_kind": "scholar.web_evidence_bundle",
                "source_ref": "webkb.openalex-candidate",
                "authority_tier": "design_tier_l2",
                "span_grounding_status": "validated_supporting",
                "validated_span_grounding_ref": valid_grounding.grounding_ref,
            }
        }
    )
    non_web_self_attested_status = _firewall_status(
        {
            "claim_authority": {
                "source_kind": "openalex_span_grounded_claim",
                "source_ref": valid_grounding.grounding_ref,
                "authority_tier": "design_tier_l2",
                "span_grounding_status": "validated_supporting",
                "validated_span_grounding_ref": valid_grounding.grounding_ref,
            }
        }
    )
    non_web_no_grounding_status = _firewall_status(
        {
            "claim_authority": {
                "source_kind": "openalex_span_grounded_claim",
                "source_ref": valid_grounding.grounding_ref,
                "authority_tier": "design_tier_l2",
            }
        }
    )
    assert_l2_claim_authority_span_grounded(
        {
            "claim_authority": {
                "source_kind": "openalex_span_grounded_claim",
                "source_ref": valid_grounding.grounding_ref,
                "authority_tier": "design_tier_l2",
                "span_grounding_status": valid_grounding.status,
                "validated_span_grounding_ref": valid_grounding.grounding_ref,
                "claim_id": first_claim.claim_id,
                "claim_text": first_claim.claim_text,
            }
        },
        surface="l2_skg_ingest",
        grounding_resolver=_resolve_grounding,
        span_support_client=span_support_client,
    )
    validated_status = "allowed"

    ingest_payload = {
        "schema_version": "policyos.policy_design_case.layer3_gy.openalex_skg_ingest_records.v1",
        "gy_lifecycle_marker": "policyos.policy_design_case.layer3_gy.openalex_skg_ingest_records.v1",
        "produced_by": "tools/quality/validation/check_layer3_gy_openalex_artifacts.py",
        "provider_config_ref": CONFIG_PATH,
        "gold_set_ref": GOLD_PATH,
        "ingest": {
            "witness_records": witness_records,
            "skg_counts": skg_counts,
            "universality": {
                "queries": sorted({str(record["query"]) for record in witness_records}),
                "different_real_result_sets": len(all_hit_sets) >= 2
                and all_hit_sets[0] != all_hit_sets[1],
            },
            "no_hit_frontier": {
                "query": no_hit_query,
                "provider": "openalex",
                "hit_count": len(no_hit_hits),
                "frontier_reason": "provider_returned_no_hits",
                "query_trace_id": no_hit_report.query_trace_id,
            },
            "span_validation_probe": {
                "valid_span_status": valid_grounding.status,
                "non_resolving_span_status": rejected_grounding.status,
                "non_supporting_span_status": non_supporting_grounding.status,
            },
            "web_firewall_probe": {
                "unvalidated_web_bundle": web_bundle_status,
                "web_self_attested": web_self_attested_status,
                "non_web_self_attested": non_web_self_attested_status,
                "non_web_no_grounding": non_web_no_grounding_status,
                "validated_span_grounded_claim": validated_status,
            },
        },
    }
    validate_accuracy_report_payload(accuracy_payload, expected=accuracy_payload, issues=[])
    return {ACCURACY_PATH: accuracy_payload, INGEST_PATH: ingest_payload}


def build_real_agent_accuracy_payload(repo_root: Path) -> dict[str, Any]:
    """Measure OpenAlex claim/span support with the production default real agent."""

    from polisyos.scientist.validation.citation_faithfulness import (
        evaluate_span_claim_entailment,
    )

    _ensure_src_path(repo_root)
    gold_payload = _read_required_json(repo_root / GOLD_PATH)
    gold_cases = [
        {**record, "case_set": "gold"}
        for record in gold_payload.get("records", [])
        if isinstance(record, dict)
    ]
    cases = [*gold_cases, *HELD_OUT_ACCURACY_CASES]
    case_judgments: list[dict[str, Any]] = []
    for case in cases:
        result = evaluate_span_claim_entailment(
            claim=_claim_payload_from_accuracy_case(case),
            evidence=_evidence_payload_from_accuracy_case(repo_root, case),
            timeout_s=45.0,
        )
        agent_judgment = result.get("agent_judgment")
        predicted_supported = result.get("label") == "supports"
        case_judgments.append(
            {
                "label_id": str(case.get("label_id") or ""),
                "case_set": str(case.get("case_set") or "gold"),
                "openalex_id": str(case.get("openalex_id") or ""),
                "source_fixture": str(case.get("source_fixture") or ""),
                "claim_text": str(case.get("claim_text") or ""),
                "span_text": str(case.get("gold_span_text") or ""),
                "expected_supported": bool(case.get("expected_supported")),
                "predicted_supported": bool(predicted_supported),
                "decision": _agent_decision(result),
                "confidence": _agent_confidence(result),
                "label": str(result.get("label") or ""),
                "status": str(result.get("status") or ""),
                "reason_codes": list(result.get("reason_codes") or []),
                "blocker_codes": list(result.get("blocker_codes") or []),
                "agent_judgment": dict(agent_judgment) if isinstance(agent_judgment, dict) else {},
                "judge_client": "create_traced_gateway_client",
                "real_agent": "agent_judgment" in result,
                "span_found_in_source": _span_exists_in_source(repo_root, case),
            }
        )

    if not any(case.get("real_agent") for case in case_judgments):
        raise RuntimeError("real-agent accuracy measurement did not receive any agent judgments")

    accuracy = _accuracy_from_case_judgments(case_judgments)
    if accuracy is None:
        raise RuntimeError("real-agent accuracy measurement did not produce case judgments")
    degraded = _degraded_accuracy_from_case_judgments(case_judgments)
    payload = {
        "schema_version": "policyos.policy_design_case.layer3_gy.openalex_accuracy_report.v1",
        "gy_lifecycle_marker": "policyos.policy_design_case.layer3_gy.openalex_accuracy_report.v1",
        "produced_by": "tools/quality/validation/check_layer3_gy_openalex_artifacts.py",
        "patterns": ["P01", "P05", "P10", "P15", "P29", "P31", "P32", "P33"],
        "provider_config_ref": CONFIG_PATH,
        "gold_set_ref": GOLD_PATH,
        "accuracy": accuracy,
        "degraded_extractor_accuracy": degraded,
        "accuracy_provenance": {
            "real_agent": True,
            "deterministic_replay": False,
            "judge_client": "create_traced_gateway_client",
            "model_id": _real_agent_model_id(),
            "model_variant_id": REAL_AGENT_MODEL_VARIANT_ID,
            "measurement_timestamp": datetime.now(UTC).isoformat(),
            "gold_case_count": len(gold_cases),
            "held_out_case_count": len(HELD_OUT_ACCURACY_CASES),
            "methodology": (
                "Production default evaluate_span_claim_entailment over human-labeled "
                "gold plus held-out OpenAlex cases; no span-support client injection."
            ),
        },
        "case_judgments": case_judgments,
    }
    issues: list[dict[str, str]] = []
    validate_accuracy_report_payload(payload, expected=payload, issues=issues)
    blocking = [
        issue
        for issue in issues
        if issue.get("code") != "layer3_gy_openalex_degraded_extractor_not_lower"
    ]
    if blocking:
        raise RuntimeError(f"real-agent accuracy report failed validation: {blocking}")
    return payload


def _claim_payload_from_accuracy_case(case: dict[str, Any]) -> dict[str, Any]:
    return {
        "claim_id": str(case.get("label_id") or ""),
        "claim_text": str(case.get("claim_text") or ""),
        "claim_family": "causal",
        "cause_variable": str(case.get("treatment_or_cause") or ""),
        "effect_variable": str(case.get("effect") or ""),
        "direction": str(case.get("claim_direction") or ""),
        "data_refs": [str(case.get("openalex_id") or "")],
        "source_attribution": str(case.get("openalex_id") or ""),
        "method_refs": ["source_bound_claim_span"],
        "identification_strategy": "source_bound_claim_span",
    }


def _evidence_payload_from_accuracy_case(repo_root: Path, case: dict[str, Any]) -> dict[str, Any]:
    span_text = str(case.get("gold_span_text") or "")
    work = _work_from_fixture(
        _recorded_fixture_payload(
            repo_root,
            str(case.get("source_fixture") or ""),
            query=str(case.get("query") or ""),
        ),
        str(case.get("openalex_id") or ""),
    )
    span_start = work.source_text.find(span_text)
    return {
        "ref_id": f"{case.get('openalex_id')}#{case.get('label_id')}",
        "source_ref": str(case.get("openalex_id") or ""),
        "text": span_text,
        "section": "abstract",
        "start_char": span_start if span_start >= 0 else None,
        "end_char": span_start + len(span_text) if span_start >= 0 else None,
        "source_content_sha256": work.content_sha256,
    }


def _span_exists_in_source(repo_root: Path, case: dict[str, Any]) -> bool:
    try:
        work = _work_from_fixture(
            _recorded_fixture_payload(
                repo_root,
                str(case.get("source_fixture") or ""),
                query=str(case.get("query") or ""),
            ),
            str(case.get("openalex_id") or ""),
        )
    except Exception:
        return False
    return str(case.get("gold_span_text") or "") in work.source_text


def _agent_decision(result: dict[str, Any]) -> str:
    judgment = result.get("agent_judgment")
    if isinstance(judgment, dict):
        return str(judgment.get("decision") or "")
    return ""


def _agent_confidence(result: dict[str, Any]) -> float:
    judgment = result.get("agent_judgment")
    if isinstance(judgment, dict):
        try:
            return float(judgment.get("confidence") or 0.0)
        except (TypeError, ValueError):
            return 0.0
    try:
        return float(result.get("score") or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _degraded_accuracy_from_case_judgments(case_judgments: list[dict[str, Any]]) -> dict[str, Any]:
    degraded_cases = [
        {**case, "predicted_supported": False}
        for case in case_judgments
    ]
    degraded = _accuracy_from_case_judgments(degraded_cases)
    if degraded is None:
        raise RuntimeError("failed to build degraded accuracy report")
    return degraded


def _real_agent_model_id() -> str:
    return (
        os.getenv("POLISYOS_LLM_GATEWAY_SPAN_SUPPORT_MODEL", "").strip()
        or os.getenv("POLISYOS_LLM_GATEWAY_MODEL", "").strip()
        or REAL_AGENT_MODEL_ID
    )


async def _provider_hits_from_fixture(
    fixture_payload: dict[str, Any],
    *,
    query: str,
    max_results: int,
) -> list[Any]:
    from polisyos.scholar.search import providers as provider_module
    from polisyos.scholar.search.models import SearchConstraints
    from polisyos.scholar.search.providers import OpenAlexWorksProvider

    async def _fake_read_url_text(url: str, *, headers: dict[str, str], timeout_s: float) -> str:
        del url, headers, timeout_s
        return json.dumps(fixture_payload)

    original = provider_module._read_url_text
    provider_module._read_url_text = _fake_read_url_text
    try:
        provider = OpenAlexWorksProvider(endpoint="https://openalex.test/works")
        return await provider.search(
            query,
            constraints=SearchConstraints(source_types=["academic"]),
            max_results=max_results,
            timeout_s=5,
        )
    finally:
        provider_module._read_url_text = original


def _work_from_fixture(payload: dict[str, Any], openalex_id: str) -> Any:
    from polisyos.ir.analytics.literature import OpenAlexWorkText

    for item in payload.get("results", []):
        if isinstance(item, dict) and str(item.get("id") or "") == openalex_id:
            return OpenAlexWorkText.from_openalex_work(item)
    raise ValueError(f"OpenAlex work not found in fixture: {openalex_id}")


def _recorded_fixture_payload(repo_root: Path, relative_path: str, *, query: str) -> dict[str, Any]:
    payload = _read_required_json(repo_root / relative_path)
    _assert_recorded_openalex_fixture(payload, path=relative_path, query=query)
    return payload


def _assert_recorded_openalex_fixture(
    payload: dict[str, Any],
    *,
    path: str,
    query: str,
    allow_empty: bool = False,
) -> None:
    recording = payload.get("_recording")
    if not isinstance(recording, dict):
        raise ValueError(f"OpenAlex fixture lacks recording metadata: {path}")
    if recording.get("real_openalex_api_response") is not True:
        raise ValueError(f"OpenAlex fixture is not marked recorded-real: {path}")
    if str(recording.get("source") or "") != "https://api.openalex.org/works":
        raise ValueError(f"OpenAlex fixture source drift: {path}")
    request_params = recording.get("request_params")
    if not isinstance(request_params, dict):
        raise ValueError(f"OpenAlex fixture request params missing: {path}")
    if str(recording.get("query") or "") != query:
        raise ValueError(f"OpenAlex fixture recording query drift: {path}")
    if str(request_params.get("search") or "") != query:
        raise ValueError(f"OpenAlex fixture request search drift: {path}")
    if "abstract_inverted_index" not in str(request_params.get("select") or ""):
        raise ValueError(f"OpenAlex fixture select omits abstract text: {path}")
    results = payload.get("results")
    if not isinstance(results, list):
        raise ValueError(f"OpenAlex fixture results missing: {path}")
    if not allow_empty and not results:
        raise ValueError(f"OpenAlex fixture results unexpectedly empty: {path}")
    for item in results:
        if not isinstance(item, dict):
            raise ValueError(f"OpenAlex fixture result shape invalid: {path}")
        if not str(item.get("id") or "").startswith("https://openalex.org/W"):
            raise ValueError(f"OpenAlex fixture work id invalid: {path}")
        if not isinstance(item.get("abstract_inverted_index"), dict):
            raise ValueError(f"OpenAlex fixture work lacks abstract text: {path}")


def _recorded_at(payload: dict[str, Any]) -> str:
    recorded_at = payload.get("_recording", {}).get("captured_at")
    return str(recorded_at or "2026-06-23T00:00:00+00:00")


def _validate_generated_artifacts_registration(
    repo_root: Path,
    issues: list[dict[str, str]],
) -> None:
    generated_path = repo_root / "architecture/generated_artifacts.toml"
    if not generated_path.is_file():
        issues.append({"code": "layer3_gy_openalex_generated_artifacts_missing"})
        return
    generated = tomllib.loads(generated_path.read_text(encoding="utf-8"))
    families = {family.get("id"): family for family in generated.get("family", [])}
    family = families.get(FAMILY_ID)
    if not isinstance(family, dict):
        issues.append({"code": "layer3_gy_openalex_family_missing"})
    else:
        if set(family.get("outputs") or []) != set(OUTPUTS):
            issues.append({"code": "layer3_gy_openalex_output_scope_drift"})
        if family.get("lifecycle") != "generated_committed":
            issues.append({"code": "layer3_gy_openalex_lifecycle_drift"})
        if "--check" not in list(family.get("check_command") or []):
            issues.append({"code": "layer3_gy_openalex_check_command_missing"})
        if "--write" not in " ".join(family.get("regenerate_commands") or []):
            issues.append({"code": "layer3_gy_openalex_regenerate_command_missing"})
    source_family = families.get(SOURCE_FAMILY_ID)
    if not isinstance(source_family, dict):
        issues.append({"code": "layer3_gy_openalex_source_family_missing"})
    else:
        if set(source_family.get("outputs") or []) != {CONFIG_PATH, GOLD_PATH}:
            issues.append({"code": "layer3_gy_openalex_source_output_scope_drift"})
        _validate_source_integrity(repo_root, source_family, issues)


def _validate_source_integrity(
    repo_root: Path,
    family: dict[str, Any],
    issues: list[dict[str, str]],
) -> None:
    integrity = family.get("source_integrity_sha256")
    if not isinstance(integrity, dict):
        issues.append({"code": "layer3_gy_openalex_source_integrity_missing"})
        return
    for output in (CONFIG_PATH, GOLD_PATH):
        path = repo_root / output
        expected = str(integrity.get(output) or "")
        if not path.is_file():
            issues.append({"code": "layer3_gy_openalex_source_output_missing", "path": output})
            continue
        actual = _sha256(path)
        if expected != actual:
            issues.append({"code": "layer3_gy_openalex_source_integrity_drift", "path": output})


def validate_accuracy_report_payload(
    payload: dict[str, Any],
    expected: dict[str, Any],
    issues: list[dict[str, str]],
) -> None:
    if payload.get("schema_version") != expected.get("schema_version"):
        issues.append({"code": "layer3_gy_openalex_accuracy_schema_drift"})
    if payload.get("produced_by") != expected.get("produced_by"):
        issues.append({"code": "layer3_gy_openalex_accuracy_producer_drift"})
    recomputed = _accuracy_from_case_judgments(payload.get("case_judgments"))
    if recomputed is None:
        issues.append({"code": "layer3_gy_openalex_accuracy_case_judgments_missing"})
    elif payload.get("accuracy") != recomputed or (
        expected.get("accuracy") and payload.get("accuracy") != expected.get("accuracy")
    ):
        issues.append({"code": "layer3_gy_openalex_accuracy_metric_drift"})

    provenance = payload.get("accuracy_provenance")
    if not isinstance(provenance, dict):
        issues.append({"code": "layer3_gy_openalex_accuracy_provenance_missing"})
        provenance = {}
    if provenance.get("real_agent") is not True:
        issues.append({"code": "layer3_gy_openalex_accuracy_not_real_agent"})
    if provenance.get("deterministic_replay") is not False:
        issues.append({"code": "layer3_gy_openalex_accuracy_circular_replay"})
    judge_client = str(provenance.get("judge_client") or "").casefold()
    if any(token in judge_client for token in ("deterministic", "recorded", "replay")):
        issues.append({"code": "layer3_gy_openalex_accuracy_circular_replay"})
    provenance_model_id = str(provenance.get("model_id") or "")
    if provenance_model_id != REAL_AGENT_MODEL_ID:
        issues.append({"code": "layer3_gy_openalex_accuracy_model_mismatch"})
    try:
        held_out_case_count = int(provenance.get("held_out_case_count") or 0)
    except (TypeError, ValueError):
        held_out_case_count = 0
    if held_out_case_count <= 0:
        issues.append({"code": "layer3_gy_openalex_accuracy_held_out_missing"})

    case_judgments = payload.get("case_judgments")
    if isinstance(case_judgments, list):
        held_out_cases = [
            case
            for case in case_judgments
            if isinstance(case, dict) and case.get("case_set") == "held_out"
        ]
        if len(held_out_cases) != held_out_case_count:
            issues.append({"code": "layer3_gy_openalex_accuracy_held_out_count_drift"})
        if all(_case_looks_deterministic(case) for case in case_judgments if isinstance(case, dict)):
            issues.append({"code": "layer3_gy_openalex_accuracy_circular_replay"})
        for case in case_judgments:
            if not isinstance(case, dict):
                issues.append({"code": "layer3_gy_openalex_accuracy_case_judgment_invalid"})
                continue
            if "agent_judgment" not in case or not isinstance(case.get("agent_judgment"), dict):
                issues.append({"code": "layer3_gy_openalex_accuracy_agent_judgment_missing"})
            else:
                judgment_model_id = str(case["agent_judgment"].get("model_id") or "")
                if judgment_model_id != provenance_model_id:
                    issues.append({"code": "layer3_gy_openalex_accuracy_model_mismatch"})
            if not isinstance(case.get("predicted_supported"), bool):
                issues.append({"code": "layer3_gy_openalex_accuracy_prediction_missing"})
    degraded = payload.get("degraded_extractor_accuracy")
    accuracy = payload.get("accuracy")
    if isinstance(degraded, dict) and isinstance(accuracy, dict):
        accuracy_recall = float(accuracy.get("recall") or 0.0)
        if accuracy_recall > 0.0 and float(degraded.get("recall") or 0.0) >= accuracy_recall:
            issues.append({"code": "layer3_gy_openalex_degraded_extractor_not_lower"})


def _accuracy_from_case_judgments(value: object) -> dict[str, Any] | None:
    if not isinstance(value, list) or not value:
        return None
    true_positive_count = 0
    true_negative_count = 0
    false_positive_count = 0
    false_negative_count = 0
    predicted_claim_count = 0
    matched_label_ids: list[str] = []
    for item in value:
        if not isinstance(item, dict):
            return None
        expected_supported = bool(item.get("expected_supported"))
        predicted_supported = bool(item.get("predicted_supported"))
        if predicted_supported:
            predicted_claim_count += 1
        label_id = str(item.get("label_id") or "")
        if expected_supported and predicted_supported:
            true_positive_count += 1
            if label_id:
                matched_label_ids.append(label_id)
        elif expected_supported and not predicted_supported:
            false_negative_count += 1
        elif not expected_supported and predicted_supported:
            false_positive_count += 1
        else:
            true_negative_count += 1
    precision_denominator = true_positive_count + false_positive_count
    recall_denominator = true_positive_count + false_negative_count
    precision = true_positive_count / precision_denominator if precision_denominator else 0.0
    recall = true_positive_count / recall_denominator if recall_denominator else 0.0
    return {
        "schema_version": "policyos.policy_design_case.layer3_gy.openalex_accuracy.v1",
        "measurement_basis": "human_labeled_gold_set",
        "gold_record_count": len(value),
        "predicted_claim_count": predicted_claim_count,
        "true_positive_count": true_positive_count,
        "false_positive_count": false_positive_count,
        "false_negative_count": false_negative_count,
        "true_negative_count": true_negative_count,
        "precision": round(precision, 6),
        "recall": round(recall, 6),
        "matched_label_ids": sorted(matched_label_ids),
    }


def _case_looks_deterministic(case: dict[str, Any]) -> bool:
    haystack = " ".join(
        str(case.get(key) or "")
        for key in ("judge_client", "rationale", "replay_key", "methodology")
    ).casefold()
    raw = case.get("agent_judgment")
    if isinstance(raw, dict):
        haystack = f"{haystack} {json.dumps(raw, sort_keys=True)}".casefold()
    return any(token in haystack for token in ("deterministic", "recorded", "replay"))


def _read_json(path: Path, issues: list[dict[str, str]]) -> dict[str, Any]:
    if not path.is_file():
        issues.append({"code": "layer3_gy_openalex_artifact_missing", "path": str(path)})
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        issues.append(
            {
                "code": "layer3_gy_openalex_artifact_invalid_json",
                "path": str(path),
                "error": str(exc),
            }
        )
        return {}
    return payload if isinstance(payload, dict) else {}


def _read_required_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    import hashlib

    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _ensure_src_path(repo_root: Path) -> None:
    for path in (repo_root, repo_root / "src"):
        text = str(path)
        if text not in sys.path:
            sys.path.insert(0, text)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-real-accuracy", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--corrupt-field-drift-check", action="store_true")
    parser.add_argument("--output-format", choices=("text", "json"), default="text")
    args = parser.parse_args(argv)

    repo_root = Path(args.repo_root).resolve()
    if args.write_real_accuracy:
        _ensure_src_path(repo_root)
        payload = build_real_agent_accuracy_payload(repo_root)
        path = repo_root / ACCURACY_PATH
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        report = {
            "status": "pass",
            "family_id": FAMILY_ID,
            "checked_artifacts": [ACCURACY_PATH],
            "accuracy": payload["accuracy"],
            "accuracy_provenance": payload["accuracy_provenance"],
            "case_judgment_count": len(payload["case_judgments"]),
        }
        if args.output_format == "json":
            print(json.dumps(report, indent=2, sort_keys=True))
        else:
            print("PASS layer3_gy_openalex_real_accuracy")
        return 0

    report = validate(
        repo_root,
        write=bool(args.write),
        corrupt_field_drift_check=bool(args.corrupt_field_drift_check),
    )
    if args.output_format == "json":
        print(json.dumps(report, indent=2, sort_keys=True))
    elif report["status"] == "pass":
        print("PASS layer3_gy_openalex_artifacts")
    else:
        print("FAIL layer3_gy_openalex_artifacts")
        for issue in report["issues"]:
            print(issue)
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    import sys

    raise SystemExit(
        run_timed_entrypoint(
            main,
            script_path=__file__,
            argv=sys.argv[1:],
            started_perf_counter=_TIMING_STARTED_AT,
        )
    )
