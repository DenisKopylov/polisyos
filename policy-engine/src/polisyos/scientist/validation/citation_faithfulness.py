"""Offline citation-faithfulness checks for public factual and legal claims."""

from __future__ import annotations

import asyncio
import concurrent.futures
import inspect
import json
import os
import re
from collections import Counter
from collections.abc import Awaitable, Mapping, Sequence
from datetime import date, datetime
from typing import Any, Literal

from polisyos.common.llm_json import extract_llm_json_object

SCHEMA_VERSION = "policyos.scientist.citation_faithfulness.v1"

CitationFaithfulnessLabel = Literal[
    "supports",
    "partially_supports",
    "scope_limited",
    "contradicts",
    "irrelevant",
    "fabricated",
    "unverifiable",
]

BLOCKING_CITATION_LABELS = frozenset(
    {
        "partially_supports",
        "scope_limited",
        "contradicts",
        "irrelevant",
        "fabricated",
        "unverifiable",
    }
)

SPAN_ENTAILMENT_SUPPORT_LABELS = frozenset({"supports"})
SPAN_SUPPORT_AGENT_TOOL_NAME = "layer3_gy_record_span_support_judgment"
SPAN_SUPPORT_CONFIDENCE_THRESHOLD = 0.72
SPAN_SUPPORT_BLOCKER_CODE = "layer3_gy_span_support_unverified"
SPAN_SUPPORT_GATEWAY_MODEL_ID = "MiniMaxAI/MiniMax-M2.7"
SPAN_SUPPORT_TEMPERATURE = 0.0
SPAN_SUPPORT_SEED = 0

_PUBLIC_FACTUAL_LEGAL_FAMILIES = frozenset(
    {
        "empirical",
        "fact",
        "factual",
        "legal",
        "normative",
        "statute",
        "statutory",
    }
)
_UNVERIFIABLE_STATUSES = frozenset(
    {
        "blocked",
        "error",
        "failed",
        "missing",
        "not_found",
        "paywalled",
        "unavailable",
        "unfetched",
        "unknown",
    }
)
_FALSE_VALUES = frozenset({"0", "false", "internal", "no", "private"})
_SCOPE_DIMENSIONS = ("legal_scope", "jurisdiction", "date", "population")
_STOP_WORDS = frozenset(
    {
        "a",
        "all",
        "an",
        "and",
        "are",
        "as",
        "by",
        "for",
        "from",
        "in",
        "is",
        "it",
        "of",
        "on",
        "or",
        "the",
        "to",
        "was",
        "were",
    }
)


def build_citation_faithfulness_report(
    *,
    claims: Sequence[Mapping[str, Any]],
    evidence: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Return a deterministic citation-faithfulness report.

    The checker uses only provided refs, snippets, and structured scope
    metadata. It intentionally does not call live LLM judges, network fetchers,
    or nondeterministic semantic services.
    """

    evidence_by_ref = _index_evidence(evidence)
    claim_reports: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []

    for index, claim in enumerate(claims):
        claim_id = _claim_id(claim, index)
        claim_family = _claim_family(claim)
        citation_refs = _citation_refs(claim)
        citation_reports: list[dict[str, Any]] = []

        if _is_public_factual_or_legal_claim(claim) and not citation_refs:
            issues.append(
                _issue(
                    code="public_claim_missing_citation",
                    claim_id=claim_id,
                    claim_text=_claim_text(claim),
                    message=f"Public factual/legal claim {claim_id} has no cited refs.",
                    next_action=(
                        "Attach source-backed citation_refs or mark the claim as "
                        "non-public/internal with rationale."
                    ),
                )
            )

        for citation_ref in citation_refs:
            citation = _classify_citation(
                claim=claim,
                claim_id=claim_id,
                citation_ref=citation_ref,
                evidence=evidence_by_ref.get(citation_ref),
            )
            citation_reports.append(citation)
            if (
                _is_public_factual_or_legal_claim(claim)
                and citation["label"] in BLOCKING_CITATION_LABELS
            ):
                issues.append(
                    _issue(
                        code="public_claim_has_unfaithful_citation",
                        claim_id=claim_id,
                        claim_text=_claim_text(claim),
                        citation_ref=citation_ref,
                        label=citation["label"],
                        mismatch_dimensions=citation["mismatch_dimensions"],
                        message=(
                            f"Public factual/legal claim {claim_id} cites "
                            f"{citation_ref} as {citation['label']}."
                        ),
                        next_action=(
                            "Replace or repair the citation, narrow the claim to the "
                            "source scope, or route the claim for human review."
                        ),
                    )
                )

        claim_has_blocking_issue = any(
            issue.get("claim_id") == claim_id and issue.get("severity") == "fail"
            for issue in issues
        )
        claim_status = "fail" if (
            claim_has_blocking_issue
            or any(
                citation["label"] in BLOCKING_CITATION_LABELS
                for citation in citation_reports
                if _is_public_factual_or_legal_claim(claim)
            )
        ) else "pass"
        claim_reports.append(
            {
                "claim_id": claim_id,
                "claim_family": claim_family,
                "public": _is_public_factual_or_legal_claim(claim),
                "claim_text": _claim_text(claim),
                "citation_refs": citation_refs,
                "citations": citation_reports,
                "status": claim_status,
            }
        )

    label_counts = Counter(
        citation["label"]
        for claim_report in claim_reports
        for citation in claim_report["citations"]
    )
    blocking_issues = [
        issue for issue in issues if str(issue.get("severity")) == "fail"
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "fail" if blocking_issues else "pass",
        "live_llm_judging_enabled": False,
        "claims": claim_reports,
        "issues": issues,
        "blocking_issue_count": len(blocking_issues),
        "label_counts": dict(sorted(label_counts.items())),
        "residual_risk": {
            "level": "medium",
            "deterministic_only": True,
            "summary": (
                "Offline checks catch fabricated refs, explicit contradictions, "
                "irrelevant snippets, and structured scope mismatches, but they "
                "do not prove full semantic entailment."
            ),
        },
        "false_pass_limits": [
            "semantic_paraphrase_not_proven",
            "metadata_omission_can_hide_scope_mismatch",
            "quoted_text_may_be_selective_without_full_source_context",
            "structured_support_claim_ids_are_trusted_inputs",
        ],
    }


def build_policy_context_citation_faithfulness_report(
    *,
    claims: Sequence[Mapping[str, Any]],
    normative_evidence: Mapping[str, Any] | None = None,
    fabric_retrieval_trace: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build an offline citation-faithfulness report from runtime evidence payloads."""

    claim_ids_by_ref = _claim_ids_by_citation_ref(claims)
    evidence: list[dict[str, Any]] = []
    for norm in _mapping_items((normative_evidence or {}).get("applied_norms")):
        ref_id = _first_text(
            norm.get("norm_id"),
            norm.get("id"),
            norm.get("artifact_id"),
            norm.get("norm_ref"),
        )
        if not ref_id:
            continue
        evidence.append(
            {
                "ref_id": ref_id,
                "source_id": ref_id,
                "artifact_id": _text(norm.get("artifact_id")),
                "text": _first_text(
                    norm.get("text"),
                    norm.get("legal_text"),
                    norm.get("summary"),
                    norm.get("description"),
                    norm.get("relevance_rationale"),
                    norm.get("title"),
                    ref_id,
                ),
                "jurisdiction": norm.get("jurisdiction"),
                "legal_scope": norm.get("legal_scope") or norm.get("fact_class"),
                "effective_from": norm.get("effective_from") or norm.get("valid_from"),
                "effective_to": norm.get("effective_to") or norm.get("valid_to"),
                "supports_claim_ids": claim_ids_by_ref.get(ref_id, []),
                "fetch_status": norm.get("fetch_status") or "ok",
            }
        )
    for source in _mapping_items((fabric_retrieval_trace or {}).get("selected_sources")):
        ref_id = _first_text(
            source.get("source_id"),
            source.get("data_snapshot_ref"),
            source.get("artifact_id"),
            source.get("id"),
            source.get("url"),
        )
        if not ref_id:
            continue
        evidence.append(
            {
                "ref_id": ref_id,
                "source_id": ref_id,
                "artifact_id": _text(source.get("artifact_id") or source.get("data_snapshot_ref")),
                "url": _text(source.get("url")),
                "text": _first_text(
                    source.get("text"),
                    source.get("snippet"),
                    source.get("summary"),
                    source.get("title"),
                    source.get("source_family"),
                    ref_id,
                ),
                "jurisdiction": source.get("jurisdiction"),
                "population": source.get("population") or source.get("coverage"),
                "supports_claim_ids": claim_ids_by_ref.get(ref_id, []),
                "fetch_status": source.get("fetch_status") or source.get("status") or "ok",
            }
        )
    return build_citation_faithfulness_report(claims=claims, evidence=evidence)


def evaluate_span_claim_entailment(
    *,
    claim: Mapping[str, Any],
    evidence: Mapping[str, Any],
    client: Any | None = None,
    confidence_threshold: float = SPAN_SUPPORT_CONFIDENCE_THRESHOLD,
    timeout_s: float = 30.0,
) -> dict[str, Any]:
    """Return an agent-judged entailment decision for one claim/span pair.

    Claim-support predicates and lexical checks are reject-only prefilters.
    Positive support is granted only when the bounded-agent judge returns a
    high-confidence entailment decision for this exact span and claim. When no
    production agent is configured, the function fails closed; deterministic
    clients are accepted only through explicit test injection.
    """

    claim_id = _claim_id(claim, 0)
    claim_text = _claim_text(claim)
    evidence_text = _evidence_text(evidence)
    evidence_ref = _evidence_ref(evidence) or _text(evidence.get("ref_id")) or "span"
    support_assessment = _evaluate_claim_support_assessment(
        {
            **dict(claim),
            "claim_id": claim_id,
            "claim_family": claim.get("claim_family") or "causal",
            "data_refs": claim.get("data_refs") or [evidence_ref],
            "source_attribution": claim.get("source_attribution") or evidence_ref,
            "method_refs": claim.get("method_refs") or [evidence_ref],
            "identification_strategy": claim.get("identification_strategy")
            or claim.get("design_family")
            or "source_bound_claim_span",
        }
    )
    base = {
        "schema_version": SCHEMA_VERSION,
        "claim_id": claim_id,
        "evidence_ref": evidence_ref,
        "support_strength": _support_strength_value(support_assessment),
        "claim_support_issues": [dict(issue) for issue in support_assessment.issues],
    }
    support_strength = _support_strength_value(support_assessment)
    reject = _span_support_reject_prefilter(
        claim=claim,
        evidence=evidence,
        claim_text=claim_text,
        evidence_text=evidence_text,
        support_strength=support_strength,
    )
    if reject is not None:
        return {**base, **reject}

    close_agent_client = client is None
    agent_client = client if client is not None else _create_default_span_support_client()
    if agent_client is None:
        return _span_support_abstention_result(
            base,
            reason_code="entailment_verifier_unavailable",
            claim_id=claim_id,
        )

    try:
        judgment = _run_span_support_coro_sync(
            _run_span_support_agent(
                client=agent_client,
                claim=claim,
                evidence=evidence,
                claim_text=claim_text,
                evidence_text=evidence_text,
            ),
            timeout_seconds=timeout_s,
        )
    except Exception as exc:
        return _span_support_abstention_result(
            base,
            reason_code="entailment_verifier_error",
            claim_id=claim_id,
            error=str(exc),
        )
    finally:
        if close_agent_client and agent_client is not None:
            _close_span_support_client(agent_client)

    return _span_support_result_from_agent_judgment(
        base,
        judgment=judgment,
        confidence_threshold=confidence_threshold,
        claim_id=claim_id,
    )


def build_span_support_replay_manifest(
    *,
    claim: Mapping[str, Any],
    evidence: Mapping[str, Any],
    judgment: Mapping[str, Any],
) -> dict[str, Any]:
    """Build a replay manifest for deterministic test-injected span judgments."""

    module = _bounded_agent_module()
    return dict(
        module.build_replay_manifest(
            request_payload={
                "claim_id": _claim_id(claim, 0),
                "claim_text": _claim_text(claim),
                "span_ref": _evidence_ref(evidence) or _text(evidence.get("ref_id")),
                "span_text_sha256": _fingerprint(_evidence_text(evidence)),
                "direction": _text(claim.get("direction") or claim.get("claim_direction")),
            },
            provider_model_metadata={
                "provider": "test-injected-deterministic-client",
                "model": "layer3-gy-span-support-judge",
                "model_variant_id": "layer3-gy-span-support-judge-v1",
            },
            prompt_template_fingerprints={
                "layer3_gy_span_support_judge": _fingerprint(_span_support_system_prompt()),
            },
            data_refs={"evidence_ref": _evidence_ref(evidence) or _text(evidence.get("ref_id"))},
            source_refs={"claim_id": _claim_id(claim, 0)},
            run_params={"threshold": SPAN_SUPPORT_CONFIDENCE_THRESHOLD},
            authority_envelopes=[
                {
                    "ref": "layer3-gy://span-support/judge",
                    "authoritative_for": ["openalex_span_grounding_support"],
                    "may_not_use_for": ["unvalidated_web_bundle_authority"],
                }
            ],
            prompt_tool_parser_ledger={
                "tool_name": SPAN_SUPPORT_AGENT_TOOL_NAME,
                "judgment": dict(judgment),
            },
            registry_refs={"owner": "polisyos.scientist.validation.citation_faithfulness"},
            execution_summary={"decision": judgment.get("decision")},
            quality_summary={"confidence": judgment.get("confidence")},
        )
    )


def explain_span_support_replay_drift(
    *,
    baseline_manifest: Mapping[str, Any],
    replay_manifest: Mapping[str, Any],
) -> dict[str, Any]:
    """Explain deterministic test replay drift for span-support judgments."""

    return dict(
        _bounded_agent_module().explain_replay_drift(
            baseline_manifest=baseline_manifest,
            replay_manifest=replay_manifest,
        )
    )


def _span_support_reject_prefilter(
    *,
    claim: Mapping[str, Any],
    evidence: Mapping[str, Any],
    claim_text: str,
    evidence_text: str,
    support_strength: str,
) -> dict[str, Any] | None:
    """Reject impossible span-support cases without granting authority."""

    if support_strength in {"unsupported", "weak"}:
        return {
            "label": "unverifiable",
            "status": "fail",
            "score": 0.0,
            "reason_codes": ["claim_support_predicates_missing"],
        }
    if not evidence_text:
        return {
            "label": "unverifiable",
            "status": "fail",
            "score": 0.0,
            "reason_codes": ["span_text_missing"],
        }
    if _normal_token(evidence.get("section")) in {"title", "heading", "display_name"}:
        return {
            "label": "irrelevant",
            "status": "fail",
            "score": 0.0,
            "reason_codes": ["title_or_heading_not_claim_support"],
        }
    if _looks_contradictory(claim_text, evidence_text):
        return {
            "label": "contradicts",
            "status": "fail",
            "score": 0.0,
            "reason_codes": ["span_direction_contradicts_claim"],
        }
    return None


def _run_span_support_coro_sync(
    coro: Awaitable[dict[str, Any]],
    *,
    timeout_seconds: float,
) -> dict[str, Any]:
    """Run the span-support agent coroutine from sync validation code."""

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop and loop.is_running():
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_run_span_support_coro_fresh_loop, coro, timeout_seconds)
            try:
                return future.result(timeout=timeout_seconds + 1.0)
            except concurrent.futures.TimeoutError as exc:
                future.cancel()
                raise TimeoutError(
                    f"Span-support agent did not complete within {timeout_seconds + 1.0:.3f}s"
                ) from exc
    return _run_span_support_coro_fresh_loop(coro, timeout_seconds)


def _run_span_support_coro_fresh_loop(
    coro: Awaitable[dict[str, Any]],
    timeout_seconds: float,
) -> dict[str, Any]:
    async def _bounded() -> dict[str, Any]:
        return await asyncio.wait_for(coro, timeout=timeout_seconds)

    return asyncio.run(_bounded())


def _close_span_support_client(client: Any) -> None:
    close = getattr(client, "aclose", None) or getattr(client, "close", None)
    if not callable(close):
        return
    try:
        result = close()
        if inspect.isawaitable(result):
            _run_span_support_coro_sync(result, timeout_seconds=5.0)
    except Exception:
        return


async def _run_span_support_agent(
    *,
    client: Any,
    claim: Mapping[str, Any],
    evidence: Mapping[str, Any],
    claim_text: str,
    evidence_text: str,
) -> dict[str, Any]:
    response = await client.generate(
        messages=[
            {"role": "system", "content": _span_support_system_prompt()},
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "claim_id": _claim_id(claim, 0),
                        "claim_text": claim_text,
                        "claim_direction": _text(
                            claim.get("direction") or claim.get("claim_direction")
                        ),
                        "span_ref": _evidence_ref(evidence) or _text(evidence.get("ref_id")),
                        "span_text": evidence_text,
                        "instructions": (
                            "Decide whether the span alone entails the claim and its direction. "
                            "Return neutral for method-only, merely topical, hedged, or partial "
                            "support of a stronger claim. Return entails for faithful paraphrase."
                        ),
                    },
                    sort_keys=True,
                ),
            },
        ],
        tools=[_span_support_judge_tool()],
        temperature=SPAN_SUPPORT_TEMPERATURE,
        seed=SPAN_SUPPORT_SEED,
    )
    return _extract_span_support_judgment(response)


def _span_support_system_prompt() -> str:
    return (
        "You are the PolicyOS span-to-claim support judge. You must decide whether "
        "the cited source span itself entails the candidate claim. Use the tool "
        f"{SPAN_SUPPORT_AGENT_TOOL_NAME} exactly once. Decisions: entails, "
        "contradicts, neutral, abstain. Entails requires the span to support the "
        "claim direction and strength, including paraphrases. Neutral covers topical "
        "or method-only text, hedging that does not support a stronger claim, and "
        "partial support. Contradicts covers opposite direction. Abstain if unsure."
    )


def _span_support_judge_tool() -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": SPAN_SUPPORT_AGENT_TOOL_NAME,
            "description": "Record a span-to-claim entailment judgment.",
            "parameters": {
                "type": "object",
                "properties": {
                    "decision": {
                        "type": "string",
                        "enum": ["entails", "contradicts", "neutral", "abstain"],
                    },
                    "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                    "rationale": {"type": "string"},
                },
                "required": ["decision", "confidence", "rationale"],
                "additionalProperties": False,
            },
        },
    }


def _extract_span_support_judgment(response: Any) -> dict[str, Any]:
    response_metadata = {
        "model_id": _text(getattr(response, "model", "")),
        "provider": _text(getattr(response, "provider", "")),
        "request_id": _text(getattr(response, "request_id", "")),
    }
    for call in _response_tool_calls(response):
        name = _tool_call_name(call)
        if name != SPAN_SUPPORT_AGENT_TOOL_NAME:
            continue
        arguments = _tool_call_arguments(call)
        return {
            "decision": _normal_token(arguments.get("decision")),
            "confidence": _as_float(arguments.get("confidence")),
            "rationale": _text(arguments.get("rationale")),
            "raw": arguments,
            "tool_call_used": True,
            **response_metadata,
        }
    content = _text(getattr(response, "content", ""))
    if content:
        try:
            payload = extract_llm_json_object(content)
        except json.JSONDecodeError:
            payload = {}
        if isinstance(payload, Mapping):
            return {
                "decision": _normal_token(payload.get("decision")),
                "confidence": _as_float(payload.get("confidence")),
                "rationale": _text(payload.get("rationale")),
                "raw": dict(payload),
                "tool_call_used": False,
                **response_metadata,
            }
    return {
        "decision": "abstain",
        "confidence": 0.0,
        "rationale": "agent response did not include a parseable judgment",
        "raw": {},
        "tool_call_used": False,
        **response_metadata,
    }


def _span_support_result_from_agent_judgment(
    base: dict[str, Any],
    *,
    judgment: Mapping[str, Any],
    confidence_threshold: float,
    claim_id: str,
) -> dict[str, Any]:
    decision = _normal_token(judgment.get("decision"))
    confidence = max(0.0, min(1.0, float(judgment.get("confidence") or 0.0)))
    projection = _span_support_grounded_projection(
        claim_id=claim_id,
        supported=decision == "entails" and confidence >= confidence_threshold,
        issue_codes=(),
    )
    if decision == "entails" and confidence >= confidence_threshold:
        return {
            **base,
            "label": "supports",
            "status": "pass",
            "score": confidence,
            "reason_codes": ["span_support_agent_entails_claim"],
            "agent_judgment": dict(judgment),
            "grounded_result_or_abstention": projection,
        }
    if decision == "contradicts":
        label = "contradicts"
        reason_code = "span_support_agent_contradicts_claim"
    elif decision == "entails":
        label = "unverifiable"
        reason_code = "span_support_agent_low_confidence"
    elif decision == "neutral":
        label = "irrelevant"
        reason_code = "span_support_agent_neutral"
    else:
        label = "unverifiable"
        reason_code = "span_support_agent_abstained"
    return {
        **base,
        "label": label,
        "status": "fail",
        "score": confidence,
        "reason_codes": [reason_code],
        "blocker_codes": [SPAN_SUPPORT_BLOCKER_CODE],
        "agent_judgment": dict(judgment),
        "grounded_result_or_abstention": _span_support_grounded_projection(
            claim_id=claim_id,
            supported=False,
            issue_codes=(SPAN_SUPPORT_BLOCKER_CODE, reason_code),
        ),
    }


def _span_support_abstention_result(
    base: dict[str, Any],
    *,
    reason_code: str,
    claim_id: str,
    error: str | None = None,
) -> dict[str, Any]:
    payload = {
        **base,
        "label": "unverifiable",
        "status": "fail",
        "score": 0.0,
        "reason_codes": [reason_code],
        "blocker_codes": [SPAN_SUPPORT_BLOCKER_CODE],
        "grounded_result_or_abstention": _span_support_grounded_projection(
            claim_id=claim_id,
            supported=False,
            issue_codes=(SPAN_SUPPORT_BLOCKER_CODE, reason_code),
        ),
    }
    if error:
        payload["error"] = error
    return payload


def _span_support_grounded_projection(
    *,
    claim_id: str,
    supported: bool,
    issue_codes: Sequence[str],
) -> dict[str, Any]:
    module = _bounded_agent_module()
    projection = module.Layer3G6GroundedResultOrAbstention(
        result_id=f"layer3-gy://span-support/result/{_normal_token(claim_id) or 'claim'}",
        request_id=f"layer3-gy-span-support:{_normal_token(claim_id) or 'claim'}",
        outcome="g5_grounded_result" if supported else "g5_grounded_abstention",
        grounding_disposition="grounded_limited" if supported else "grounded_abstention",
        envelope_match_status=(
            "same_class_as_g5_pinned_case" if supported else "ambiguous_requires_abstention"
        ),
        g5_record_refs=(),
        abstention_reason_refs=tuple(issue_codes),
        issue_codes=tuple(issue_codes),
    )
    return dict(projection.model_dump(mode="json"))


def _create_default_span_support_client() -> Any | None:
    """Create the real production span-support client; never use replay fallback."""

    module = _bounded_agent_module()
    client = module.create_traced_gateway_client(
        model_name=_span_support_gateway_model_name(),
        provider_hint="polisyos-gy-span-support",
        run_id="layer3-gy-span-support-runtime",
        model_variant_id="layer3-gy-span-support-judge-v1",
    )
    if client is None or _is_simulated_or_recorded_client(client):
        return None
    return client


def _span_support_gateway_model_name() -> str:
    return (
        os.getenv("POLISYOS_LLM_GATEWAY_SPAN_SUPPORT_MODEL", "").strip()
        or os.getenv("POLISYOS_LLM_GATEWAY_MODEL", "").strip()
        or SPAN_SUPPORT_GATEWAY_MODEL_ID
    )


def _bounded_agent_module() -> Any:
    import importlib

    return importlib.import_module(
        "polisyos.runtime.quality.proving_ground.bounded_request_agent"
    )


def _evaluate_claim_support_assessment(claim: Mapping[str, Any]) -> Any:
    """Call the claim-support owner without making validation imports cyclic."""

    from polisyos.scientist.validation.claim_support import evaluate_claim_support

    return evaluate_claim_support(claim)


def _support_strength_value(assessment: Any) -> str:
    strength = getattr(assessment, "support_strength", "")
    return str(getattr(strength, "value", strength) or "").strip().lower()


def _classify_citation(
    *,
    claim: Mapping[str, Any],
    claim_id: str,
    citation_ref: str,
    evidence: Mapping[str, Any] | None,
) -> dict[str, Any]:
    if evidence is None:
        return _citation_result(
            citation_ref=citation_ref,
            label="fabricated",
            reason_codes=["citation_ref_not_found"],
        )

    evidence_text = _evidence_text(evidence)
    if _is_unverifiable(evidence, evidence_text=evidence_text):
        return _citation_result(
            citation_ref=citation_ref,
            evidence_ref=_evidence_ref(evidence),
            label="unverifiable",
            reason_codes=["source_not_verifiable"],
        )

    if _contains_id(evidence, "contradicts_claim_ids", claim_id):
        return _citation_result(
            citation_ref=citation_ref,
            evidence_ref=_evidence_ref(evidence),
            label="contradicts",
            reason_codes=["source_contradicts_claim"],
        )

    mismatch_dimensions = _mismatch_dimensions(claim, evidence)
    explicit_support = _contains_id(evidence, "supports_claim_ids", claim_id)
    if explicit_support:
        if any(dimension in mismatch_dimensions for dimension in _SCOPE_DIMENSIONS):
            return _citation_result(
                citation_ref=citation_ref,
                evidence_ref=_evidence_ref(evidence),
                label="scope_limited",
                reason_codes=["structured_scope_mismatch"],
                mismatch_dimensions=mismatch_dimensions,
            )
        if "exception" in mismatch_dimensions:
            return _citation_result(
                citation_ref=citation_ref,
                evidence_ref=_evidence_ref(evidence),
                label="partially_supports",
                reason_codes=["source_exception_not_preserved"],
                mismatch_dimensions=mismatch_dimensions,
            )
        return _citation_result(
            citation_ref=citation_ref,
            evidence_ref=_evidence_ref(evidence),
            label="supports",
            reason_codes=["structured_support_match"],
        )

    if _looks_contradictory(_claim_text(claim), evidence_text):
        return _citation_result(
            citation_ref=citation_ref,
            evidence_ref=_evidence_ref(evidence),
            label="contradicts",
            reason_codes=["lexical_contradiction_proxy"],
        )

    lexical_overlap = _lexical_claim_overlap(_claim_text(claim), evidence_text)
    if lexical_overlap < 0.22:
        return _citation_result(
            citation_ref=citation_ref,
            evidence_ref=_evidence_ref(evidence),
            label="irrelevant",
            reason_codes=["low_lexical_overlap"],
            lexical_overlap=round(lexical_overlap, 6),
        )
    if any(dimension in mismatch_dimensions for dimension in _SCOPE_DIMENSIONS):
        return _citation_result(
            citation_ref=citation_ref,
            evidence_ref=_evidence_ref(evidence),
            label="scope_limited",
            reason_codes=["lexical_match_scope_mismatch"],
            mismatch_dimensions=mismatch_dimensions,
            lexical_overlap=round(lexical_overlap, 6),
        )
    if "exception" in mismatch_dimensions:
        return _citation_result(
            citation_ref=citation_ref,
            evidence_ref=_evidence_ref(evidence),
            label="partially_supports",
            reason_codes=["lexical_match_exception_mismatch"],
            mismatch_dimensions=mismatch_dimensions,
            lexical_overlap=round(lexical_overlap, 6),
        )
    return _citation_result(
        citation_ref=citation_ref,
        evidence_ref=_evidence_ref(evidence),
        label="supports" if lexical_overlap >= 0.62 else "partially_supports",
        reason_codes=["lexical_support_proxy"],
        lexical_overlap=round(lexical_overlap, 6),
    )


def _citation_result(
    *,
    citation_ref: str,
    label: CitationFaithfulnessLabel,
    reason_codes: list[str],
    evidence_ref: str | None = None,
    mismatch_dimensions: list[str] | None = None,
    lexical_overlap: float | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "citation_ref": citation_ref,
        "evidence_ref": evidence_ref or citation_ref,
        "label": label,
        "reason_codes": reason_codes,
        "mismatch_dimensions": sorted(mismatch_dimensions or []),
    }
    if lexical_overlap is not None:
        result["lexical_overlap"] = lexical_overlap
    return result


def _issue(
    *,
    code: str,
    claim_id: str,
    claim_text: str,
    message: str,
    next_action: str,
    citation_ref: str | None = None,
    label: str | None = None,
    mismatch_dimensions: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "code": code,
        "severity": "fail",
        "layer": "scientist_policy_artifacts",
        "phase": "citation_faithfulness",
        "claim_id": claim_id,
        "claim_text": claim_text,
        "citation_ref": citation_ref,
        "label": label,
        "mismatch_dimensions": sorted(mismatch_dimensions or []),
        "message": message,
        "next_action": next_action,
    }


def _index_evidence(
    evidence: Sequence[Mapping[str, Any]],
) -> dict[str, Mapping[str, Any]]:
    indexed: dict[str, Mapping[str, Any]] = {}
    for item in evidence:
        for key in (
            "ref_id",
            "citation_ref",
            "snippet_id",
            "source_id",
            "id",
            "artifact_id",
            "url",
        ):
            value = _text(item.get(key))
            if value:
                indexed.setdefault(value, item)
    return indexed


def _mapping_items(value: object) -> list[Mapping[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, str | bytes | bytearray):
        return []
    return [item for item in value if isinstance(item, Mapping)]


def _claim_ids_by_citation_ref(
    claims: Sequence[Mapping[str, Any]],
) -> dict[str, list[str]]:
    output: dict[str, list[str]] = {}
    for index, claim in enumerate(claims):
        claim_id = _claim_id(claim, index)
        for ref in _citation_refs(claim):
            output.setdefault(ref, []).append(claim_id)
    return {ref: sorted(dict.fromkeys(ids)) for ref, ids in output.items()}


def _first_text(*values: object) -> str:
    for value in values:
        text = _text(value)
        if text:
            return text
    return ""


def _claim_id(claim: Mapping[str, Any], index: int) -> str:
    return _text(claim.get("claim_id") or claim.get("id") or f"claim_{index + 1}")


def _claim_family(claim: Mapping[str, Any]) -> str:
    return _normal_token(
        claim.get("claim_family") or claim.get("family") or claim.get("claim_type")
    )


def _claim_text(claim: Mapping[str, Any]) -> str:
    return _text(claim.get("text") or claim.get("claim_text") or claim.get("claim"))


def _citation_refs(claim: Mapping[str, Any]) -> list[str]:
    refs: list[str] = []
    for key in (
        "citation_refs",
        "citations",
        "source_refs",
        "source_ref",
        "evidence_refs",
        "legal_refs",
        "norm_refs",
    ):
        refs.extend(_as_text_list(claim.get(key)))
    return sorted(dict.fromkeys(refs))


def _is_public_factual_or_legal_claim(claim: Mapping[str, Any]) -> bool:
    raw_public = claim.get("public")
    if raw_public is None:
        public = True
    elif isinstance(raw_public, bool):
        public = raw_public
    else:
        public = _normal_token(raw_public) not in _FALSE_VALUES
    return public and _claim_family(claim) in _PUBLIC_FACTUAL_LEGAL_FAMILIES


def _contains_id(evidence: Mapping[str, Any], key: str, claim_id: str) -> bool:
    return claim_id in set(_as_text_list(evidence.get(key)))


def _is_unverifiable(
    evidence: Mapping[str, Any],
    *,
    evidence_text: str,
) -> bool:
    status = _normal_token(
        evidence.get("fetch_status") or evidence.get("status") or evidence.get("state")
    )
    if status in _UNVERIFIABLE_STATUSES:
        return True
    if evidence.get("unverifiable") is True:
        return True
    return not evidence_text and not (
        evidence.get("supports_claim_ids") or evidence.get("contradicts_claim_ids")
    )


def _evidence_text(evidence: Mapping[str, Any]) -> str:
    return _text(
        evidence.get("text")
        or evidence.get("snippet")
        or evidence.get("quote")
        or evidence.get("summary")
    )


def _evidence_ref(evidence: Mapping[str, Any]) -> str | None:
    for key in ("ref_id", "citation_ref", "snippet_id", "source_id", "id", "url"):
        value = _text(evidence.get(key))
        if value:
            return value
    return None


def _mismatch_dimensions(
    claim: Mapping[str, Any],
    evidence: Mapping[str, Any],
) -> list[str]:
    mismatches: list[str] = []
    for key in ("legal_scope", "jurisdiction", "population"):
        if _has_token_mismatch(claim.get(key), evidence.get(key)):
            mismatches.append(key)
    if _has_date_mismatch(claim, evidence):
        mismatches.append("date")
    claim_exceptions = set(_as_normal_tokens(claim.get("exceptions")))
    evidence_exceptions = set(_as_normal_tokens(evidence.get("exceptions")))
    if evidence_exceptions and not evidence_exceptions.issubset(claim_exceptions):
        mismatches.append("exception")
    return sorted(dict.fromkeys(mismatches))


def _has_token_mismatch(left: object, right: object) -> bool:
    left_tokens = set(_as_normal_tokens(left))
    right_tokens = set(_as_normal_tokens(right))
    return bool(left_tokens and right_tokens and left_tokens.isdisjoint(right_tokens))


def _has_date_mismatch(
    claim: Mapping[str, Any],
    evidence: Mapping[str, Any],
) -> bool:
    claim_date = _first_date(
        claim.get("as_of"),
        claim.get("date"),
        claim.get("effective_date"),
        claim.get("claim_date"),
    )
    if claim_date is None:
        return False
    effective_from = _first_date(
        evidence.get("effective_from"),
        evidence.get("valid_from"),
        evidence.get("published_at"),
    )
    effective_to = _first_date(
        evidence.get("effective_to"),
        evidence.get("valid_to"),
        evidence.get("expires_at"),
        evidence.get("withdrawn_at"),
    )
    if effective_from is not None and claim_date < effective_from:
        return True
    return bool(effective_to is not None and claim_date > effective_to)


def _looks_contradictory(claim_text: str, evidence_text: str) -> bool:
    claim_tokens = set(_tokens(claim_text))
    evidence_tokens = set(_tokens(evidence_text))
    if len(claim_tokens.intersection(evidence_tokens)) < 3:
        return False
    claim_permits = bool(
        claim_tokens.intersection(
            {"allow", "allows", "permit", "permits", "permitted"}
        )
    )
    evidence_prohibits = bool(
        evidence_tokens.intersection(
            {
                "ban",
                "bans",
                "bar",
                "bars",
                "forbid",
                "forbids",
                "prohibit",
                "prohibits",
            }
        )
    )
    claim_available = bool(
        claim_tokens.intersection(
            {"available", "eligible", "qualify", "qualifies"}
        )
    )
    evidence_excludes = bool(
        evidence_tokens.intersection({"exclude", "excluded", "excludes", "except", "ineligible"})
    )
    return (claim_permits and evidence_prohibits) or (
        claim_available and evidence_excludes
    )


def _direction_contradicts_span(claim: Mapping[str, Any], evidence_text: str) -> bool:
    claim_direction = _normal_token(claim.get("direction") or claim.get("claim_direction"))
    evidence_tokens = set(_tokens(evidence_text))
    positive = bool(
        evidence_tokens.intersection(
            {
                "boost",
                "boosts",
                "gain",
                "gains",
                "higher",
                "improve",
                "improved",
                "improvement",
                "improves",
                "increase",
                "increased",
                "increases",
                "raising",
                "raises",
            }
        )
    )
    negative = bool(
        evidence_tokens.intersection(
            {
                "decrease",
                "decreased",
                "decreases",
                "limit",
                "limiting",
                "limits",
                "lower",
                "reduced",
                "reduces",
                "reduction",
            }
        )
    )
    null = bool(
        evidence_tokens.intersection(
            {
                "unchanged",
                "insignificant",
                "nonsignificant",
                "null",
            }
        )
        or "no effect" in evidence_text.casefold()
        or "no discernible effect" in evidence_text.casefold()
        or "not significant" in evidence_text.casefold()
    )
    if claim_direction == "positive":
        return null or negative
    if claim_direction == "negative":
        return positive or null
    if claim_direction == "null":
        return (positive or negative) and not null
    return False


def _span_text_has_literal_containment(claim_text: str, evidence_text: str) -> bool:
    """Return literal containment only; this helper never grants authority."""

    claim_normalized = _normalized_text(claim_text)
    evidence_normalized = _normalized_text(evidence_text)
    if not claim_normalized or not evidence_normalized:
        return False
    if evidence_normalized in claim_normalized:
        return True
    if claim_normalized in evidence_normalized:
        return True
    return False


def _span_contains_lexical_evidence_cue(evidence_text: str) -> bool:
    """Return cue-word presence only; this helper never grants authority."""

    evidence = evidence_text.casefold()
    signal_phrases = (
        "we find",
        "we found",
        "results",
        "estimate",
        "estimated",
        "effect",
        "impact",
        "improve",
        "increase",
        "decrease",
        "reduce",
        "unchanged",
        "no discernible",
        "not significant",
        "limiting",
        "associated",
        "caused",
        "causal",
    )
    return any(phrase in evidence for phrase in signal_phrases)


def _normalized_text(value: str) -> str:
    return re.sub(r"\s+", " ", _text(value).casefold()).strip()


def _lexical_claim_overlap(claim_text: str, evidence_text: str) -> float:
    claim_tokens = set(_tokens(claim_text))
    if not claim_tokens:
        return 0.0
    evidence_tokens = set(_tokens(evidence_text))
    return len(claim_tokens.intersection(evidence_tokens)) / len(claim_tokens)


def _tokens(value: str) -> list[str]:
    return [
        token
        for token in re.findall(r"[a-z0-9_]+", value.casefold())
        if token and token not in _STOP_WORDS
    ]


def _response_tool_calls(response: Any) -> list[Any]:
    tool_calls = getattr(response, "tool_calls", None)
    if isinstance(tool_calls, list):
        return list(tool_calls)
    raw = getattr(response, "raw", None)
    if not isinstance(raw, Mapping):
        return []
    choices = raw.get("choices")
    if not isinstance(choices, list) or not choices:
        return []
    first_choice = choices[0]
    message = first_choice.get("message") if isinstance(first_choice, Mapping) else None
    raw_tool_calls = message.get("tool_calls") if isinstance(message, Mapping) else None
    return list(raw_tool_calls) if isinstance(raw_tool_calls, list) else []


def _tool_call_name(call: Any) -> str:
    if isinstance(call, Mapping):
        function = call.get("function")
        if isinstance(function, Mapping):
            return _text(function.get("name"))
        return _text(call.get("name"))
    return _text(getattr(call, "name", ""))


def _tool_call_arguments(call: Any) -> dict[str, Any]:
    if isinstance(call, Mapping):
        function = call.get("function")
        raw_arguments = (
            function.get("arguments")
            if isinstance(function, Mapping)
            else call.get("arguments")
        )
    else:
        raw_arguments = getattr(call, "arguments", {})
    if isinstance(raw_arguments, Mapping):
        return dict(raw_arguments)
    if isinstance(raw_arguments, str):
        try:
            parsed = json.loads(raw_arguments)
        except json.JSONDecodeError:
            return {}
        return dict(parsed) if isinstance(parsed, Mapping) else {}
    return {}


def _is_simulated_or_recorded_client(client: Any) -> bool:
    client_type_names: list[str] = [type(client).__name__.casefold()]
    provider_values: list[str] = []
    for attr in ("provider", "provider_name", "_provider_name"):
        value = getattr(client, attr, None)
        if isinstance(value, str):
            provider_values.append(value.casefold())
    unwrap = getattr(client, "unwrap", None)
    if callable(unwrap):
        try:
            raw = unwrap()
        except Exception:
            raw = None
        if raw is not None:
            client_type_names.append(type(raw).__name__.casefold())
            for attr in ("provider", "provider_name", "_provider_name"):
                value = getattr(raw, attr, None)
                if isinstance(value, str):
                    provider_values.append(value.casefold())
    text = " ".join([*client_type_names, *provider_values])
    return any(token in text for token in ("fake", "mock", "recorded", "replay", "simulated"))


def _as_float(value: object) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _fingerprint(value: object) -> str:
    import hashlib

    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _first_date(*values: object) -> date | None:
    for value in values:
        parsed = _parse_date(value)
        if parsed is not None:
            return parsed
    return None


def _parse_date(value: object) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = _text(value)
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def _as_text_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [_text(value)] if _text(value) else []
    if isinstance(value, Mapping):
        for key in ("ref_id", "citation_ref", "source_id", "snippet_id", "id"):
            ref = _text(value.get(key))
            if ref:
                return [ref]
        return []
    if isinstance(value, Sequence):
        refs: list[str] = []
        for item in value:
            refs.extend(_as_text_list(item))
        return refs
    return [_text(value)] if _text(value) else []


def _as_normal_tokens(value: object) -> list[str]:
    return [_normal_token(item) for item in _as_text_list(value) if _normal_token(item)]


def _normal_token(value: object) -> str:
    token = re.sub(r"[^a-z0-9_]+", "_", _text(value).casefold()).strip("_")
    return re.sub(r"_+", "_", token)


def _text(value: object) -> str:
    return str(value or "").strip()


__all__ = [
    "BLOCKING_CITATION_LABELS",
    "SCHEMA_VERSION",
    "SPAN_ENTAILMENT_SUPPORT_LABELS",
    "CitationFaithfulnessLabel",
    "build_citation_faithfulness_report",
    "build_policy_context_citation_faithfulness_report",
    "build_span_support_replay_manifest",
    "evaluate_span_claim_entailment",
    "explain_span_support_replay_drift",
]
