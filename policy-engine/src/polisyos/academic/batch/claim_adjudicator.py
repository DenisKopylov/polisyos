"""Claim-level adjudication and consensus aggregation for academic extraction."""

from __future__ import annotations

import asyncio
import json
import logging
from collections import defaultdict
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from polisyos.academic.batch.claim_ids import stable_claim_id
from polisyos.academic.batch.prompts import (
    CLAIM_ADJUDICATION_SCHEMA_HINT,
)
from polisyos.batch_common.manifest import write_stage_manifest
from polisyos.ir.analytics.literature import (
    ArticleExtractionResult,
    CausalClaim,
    CausalCredibility,
    ClaimAdjudicationResult,
    ClaimType,
    DesignFamily,
    RiskOfBias,
    SourceBasis,
    SupportStatus,
)
from polisyos.scientist.autotune.claim_adjudication import (
    ClaimAdjudicationSearchConfig,
    aggregate_claim_rows,
    load_claim_adjudication_config,
    select_prompt_variant,
)

if TYPE_CHECKING:
    from polisyos.academic.batch.config import AcademicBatchConfig

logger = logging.getLogger(__name__)


def _load_article_results(config: AcademicBatchConfig) -> list[ArticleExtractionResult]:
    rows: list[ArticleExtractionResult] = []
    retracted_work_ids = _retracted_work_ids(config)
    source_path = (
        config.resolve_extract_final_results_path
        if config.resolve_extract_final_results_path.exists()
        else config.article_extraction_results_path
    )
    if not source_path.exists():
        return rows
    with open(source_path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            result = ArticleExtractionResult.model_validate_json(line)
            if result.openalex_id in retracted_work_ids:
                continue
            rows.append(result)
    return rows


def _retracted_work_ids(config: AcademicBatchConfig) -> set[str]:
    work_ids: set[str] = set()
    if not config.merged_records_path.exists():
        return work_ids
    with open(config.merged_records_path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(row, dict):
                continue
            if bool(row.get("is_retracted")) or bool(
                (row.get("metadata") or {}).get("is_retracted")
            ):
                work_id = str(row.get("id") or row.get("openalex_id") or "").strip()
                if work_id:
                    work_ids.add(work_id)
    return work_ids


def _intra_paper_contradictions(rows: list[ArticleExtractionResult]) -> set[str]:
    contradictory_claim_ids: set[str] = set()
    for result in rows:
        grouped: dict[tuple[str, str], dict[str, list[str]]] = defaultdict(
            lambda: defaultdict(list)
        )
        for claim in result.causal_claims:
            key = (claim.cause_variable, claim.effect_variable)
            grouped[key][claim.direction.value].append(_claim_id_for(result, claim))
        for direction_map in grouped.values():
            if direction_map.get("positive") and direction_map.get("negative"):
                for claim_ids in direction_map.values():
                    contradictory_claim_ids.update(claim_ids)
    return contradictory_claim_ids


def _coerce_float(value: Any, default: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        parsed = default
    return max(0.0, min(1.0, parsed))


def _credibility_score(value: CausalCredibility) -> float:
    return {
        CausalCredibility.STRONG: 0.92,
        CausalCredibility.MODERATE: 0.72,
        CausalCredibility.WEAK: 0.45,
        CausalCredibility.NOT_CAUSAL: 0.05,
        CausalCredibility.UNCLEAR: 0.28,
    }[value]


def _support_score(value: SupportStatus) -> float:
    return {
        SupportStatus.SUPPORTED: 1.0,
        SupportStatus.MIXED: 0.65,
        SupportStatus.COUNTEREVIDENCE: 0.2,
        SupportStatus.INSUFFICIENT: 0.3,
    }[value]


def _source_basis_from(value: Any) -> SourceBasis:
    normalized = str(value or "").strip().lower()
    return (
        SourceBasis.ABSTRACT_ONLY
        if normalized == SourceBasis.ABSTRACT_ONLY.value
        else SourceBasis.FULLTEXT
    )


def _claim_type_from(value: Any) -> ClaimType:
    normalized = str(value or "").strip().lower().replace(" ", "_")
    try:
        return ClaimType(normalized)
    except ValueError:
        return ClaimType.ASSOCIATION


def _design_family_from(value: Any, *, fallback: DesignFamily) -> DesignFamily:
    normalized = str(value or "").strip().lower().replace(" ", "_")
    if not normalized:
        return fallback
    aliases = {
        "difference_in_differences": DesignFamily.DID,
        "fixed_effects": DesignFamily.PANEL_FE,
        "fe": DesignFamily.PANEL_FE,
        "randomized": DesignFamily.RCT,
        "randomised": DesignFamily.RCT,
    }
    try:
        return DesignFamily(normalized)
    except ValueError:
        return aliases.get(normalized, fallback)


def _credibility_from(value: Any) -> CausalCredibility:
    normalized = str(value or "").strip().lower().replace(" ", "_")
    try:
        return CausalCredibility(normalized)
    except ValueError:
        return CausalCredibility.UNCLEAR


def _risk_of_bias_from(value: Any) -> RiskOfBias:
    normalized = str(value or "").strip().lower().replace(" ", "_")
    try:
        return RiskOfBias(normalized)
    except ValueError:
        return RiskOfBias.UNCLEAR


def _support_status_from(value: Any) -> SupportStatus:
    normalized = str(value or "").strip().lower().replace(" ", "_")
    try:
        return SupportStatus(normalized)
    except ValueError:
        return SupportStatus.INSUFFICIENT


def _claim_id_for(result: ArticleExtractionResult, claim: CausalClaim) -> str:
    return claim.claim_id or stable_claim_id(
        work_id=result.openalex_id,
        cause=claim.cause_variable,
        effect=claim.effect_variable,
        claim_text=claim.claim_text,
        direction=claim.direction.value,
        supporting_span_ids=tuple(claim.supporting_span_ids),
    )


_DESIGN_TIER: dict[DesignFamily, int] = {
    # Tier 1: Strong causal identification
    DesignFamily.RCT: 1,
    DesignFamily.IV: 1,
    DesignFamily.DID: 1,
    DesignFamily.RDD: 1,
    DesignFamily.SYNTHETIC_CONTROL: 1,
    # Tier 2: Quasi-causal
    DesignFamily.PANEL_FE: 2,
    DesignFamily.EVENT_STUDY: 2,
    DesignFamily.QUASI_EXPERIMENTAL_OTHER: 2,
    DesignFamily.QUASI_EXPERIMENTAL_DID: 2,
    DesignFamily.QUASI_EXPERIMENTAL_RDD: 2,
    # Tier 3: Empirical without identification
    DesignFamily.OLS: 3,
    DesignFamily.OLS_CROSS_SECTIONAL: 3,
    DesignFamily.STRUCTURAL_MODEL: 3,
    DesignFamily.TIME_SERIES_COINTEGRATION: 3,
    # Tier 4: Synthesis / aggregation
    DesignFamily.META_ANALYSIS: 4,
    DesignFamily.REVIEW: 4,
    DesignFamily.REVIEW_NARRATIVE: 4,
    DesignFamily.REVIEW_META_ANALYSIS: 4,
    # Tier 5: No identification
    DesignFamily.THEORETICAL: 5,
    DesignFamily.UNCLEAR: 5,
}
_TIER_VALIDITY_BASE = {1: 0.65, 2: 0.50, 3: 0.40, 4: 0.55, 5: 0.25}
_TIER_CREDIBILITY = {
    1: CausalCredibility.MODERATE,
    2: CausalCredibility.MODERATE,
    3: CausalCredibility.WEAK,
    4: CausalCredibility.MODERATE,
    5: CausalCredibility.WEAK,
}


def _fallback_adjudication(
    result: ArticleExtractionResult, claim: CausalClaim
) -> ClaimAdjudicationResult:
    claim_id = _claim_id_for(result, claim)
    source_basis = (
        claim.source_basis if isinstance(claim.source_basis, SourceBasis) else result.source_basis
    )

    tier = _DESIGN_TIER.get(claim.design_family_hint, 5)
    span_count = len(claim.supporting_spans)
    is_explicit = claim.claim_explicitness.value == "explicit"

    validity = min(
        1.0,
        _TIER_VALIDITY_BASE[tier]
        + min(0.15, 0.05 * max(0, span_count - 1))
        + (0.05 if is_explicit else 0.0),
    )
    publishable = bool(span_count > 0 and (tier <= 2 or (tier == 4 and is_explicit)))

    return ClaimAdjudicationResult(
        claim_id=claim_id,
        openalex_id=result.openalex_id,
        cause_variable=claim.cause_variable,
        effect_variable=claim.effect_variable,
        source_basis=source_basis,
        paper_asserts_causality_score=0.55 if is_explicit else 0.35,
        claim_type=ClaimType.CAUSAL_ASSERTION if is_explicit else ClaimType.ASSOCIATION,
        design_family=claim.design_family_hint,
        causal_credibility=_TIER_CREDIBILITY[tier],
        risk_of_bias=RiskOfBias.MODERATE if tier <= 2 else RiskOfBias.UNCLEAR,
        support_status=SupportStatus.SUPPORTED if span_count > 0 else SupportStatus.INSUFFICIENT,
        claim_validity_score=validity,
        adjudication_confidence=min(0.75, 0.35 + 0.05 * min(span_count, 4)),
        publishable_edge=publishable,
        adjudication_notes="fallback_adjudication_without_llm",
    )


def _normalize_adjudication_payload(
    *,
    result: ArticleExtractionResult,
    claim: CausalClaim,
    parsed: dict[str, Any],
    pass_index: int,
    total_passes: int,
) -> dict[str, Any]:
    source_basis = _source_basis_from(
        parsed.get("source_basis") or claim.source_basis.value or result.source_basis.value
    )
    claim_type = _claim_type_from(parsed.get("claim_type") or ClaimType.ASSOCIATION.value)
    design_family = _design_family_from(
        parsed.get("design_family") or claim.design_family_hint.value or DesignFamily.UNCLEAR.value,
        fallback=claim.design_family_hint,
    )
    causal_credibility = _credibility_from(
        parsed.get("causal_credibility") or CausalCredibility.UNCLEAR.value
    )
    risk_of_bias = _risk_of_bias_from(parsed.get("risk_of_bias") or RiskOfBias.UNCLEAR.value)
    support_status = _support_status_from(
        parsed.get("support_status") or SupportStatus.INSUFFICIENT.value
    )
    paper_asserts = _coerce_float(parsed.get("paper_asserts_causality_score"), 0.4)
    adjudication_confidence = _coerce_float(parsed.get("adjudication_confidence"), 0.5)

    model_validity = parsed.get("claim_validity_score")
    if model_validity is None:
        model_validity = (
            _credibility_score(causal_credibility) * 0.5
            + paper_asserts * 0.3
            + _support_score(support_status) * 0.1
            + (1.0 if source_basis == SourceBasis.FULLTEXT else 0.75) * 0.1
        )
    claim_validity = _coerce_float(model_validity, 0.3)

    publishable = bool(parsed.get("publishable_edge", False))
    if source_basis == SourceBasis.ABSTRACT_ONLY and causal_credibility == CausalCredibility.STRONG:
        _strong_abstract_designs = {
            DesignFamily.RCT,
            DesignFamily.IV,
            DesignFamily.DID,
            DesignFamily.RDD,
            DesignFamily.SYNTHETIC_CONTROL,
        }
        if design_family not in _strong_abstract_designs:
            publishable = False
            claim_validity = min(claim_validity, 0.65)

    return {
        "claim_id": _claim_id_for(result, claim),
        "openalex_id": result.openalex_id,
        "cause_variable": claim.cause_variable,
        "effect_variable": claim.effect_variable,
        "source_basis": source_basis.value,
        "paper_asserts_causality_score": paper_asserts,
        "claim_type": claim_type.value,
        "design_family": design_family.value,
        "causal_credibility": causal_credibility.value,
        "risk_of_bias": risk_of_bias.value,
        "support_status": support_status.value,
        "claim_validity_score": claim_validity,
        "adjudication_confidence": adjudication_confidence,
        "publishable_edge": publishable,
        "adjudication_notes": str(parsed.get("adjudication_notes") or ""),
        "consensus_passes": total_passes,
        "consensus_stability": 1.0
        if total_passes <= 1
        else max(0.0, min(1.0, 1.0 / max(1, pass_index + 1))),
    }


async def _adjudicate_with_llm(
    *,
    client: Any,
    model: str,
    result: ArticleExtractionResult,
    claim: CausalClaim,
    pass_index: int,
    search_config: ClaimAdjudicationSearchConfig,
) -> ClaimAdjudicationResult:
    variant = select_prompt_variant(search_config, pass_index)
    source_basis = claim.source_basis.value if claim.source_basis else result.source_basis.value
    supporting = [span.model_dump(mode="json") for span in claim.supporting_spans]
    method_spans = [span.model_dump(mode="json") for span in claim.method_spans]
    prompt = f"""
Adjudicate a single extracted literature claim for causal validity.
Return strict JSON only:
{CLAIM_ADJUDICATION_SCHEMA_HINT}

Rules:
- Distinguish between the paper asserting causality and the graph treating it as a credible causal edge.
- Be conservative.
- panel FE, OLS, generic regression, and ML prediction are not strong causal evidence by themselves.
- abstract_only claims with weak designs (OLS, panel_FE) should almost never be publishable.
- abstract_only claims with strong designs (RCT, IV, DiD, RDD) CAN be publishable if the abstract clearly describes the identification strategy.
- If design evidence is missing, prefer weak or unclear.
- Use the effect_size and confidence_interval below (if available) to assess whether the claim is quantitatively grounded. A precise numeric effect with CI is more credible than a vague directional claim.

Calibration note:
{variant}

Paper:
title: {result.title}
methodology: {result.methodology}
methodology_enum: {result.methodology_enum.value}
source_basis: {source_basis}
text_quality: {result.text_quality.value}

Claim:
claim_text: {claim.claim_text}
cause_variable: {claim.cause_variable}
effect_variable: {claim.effect_variable}
direction: {claim.direction.value}
claim_explicitness: {claim.claim_explicitness.value}
design_family_hint: {claim.design_family_hint.value}
effect_size: {claim.effect_size if claim.effect_size is not None else "[not provided]"}
scope_conditions: {json.dumps(claim.scope_conditions or [], ensure_ascii=False)}

Supporting spans:
{json.dumps(supporting, ensure_ascii=False)}

Method spans:
{json.dumps(method_spans, ensure_ascii=False)}
""".strip()
    parsed, _usage = await client.chat(model=model, temperature=0.0, prompt=prompt)
    payload = _normalize_adjudication_payload(
        result=result,
        claim=claim,
        parsed=parsed,
        pass_index=pass_index,
        total_passes=1,
    )
    return ClaimAdjudicationResult.model_validate(payload)


async def _adjudicate_with_pool(
    *,
    pool: Any,
    model: str,
    result: ArticleExtractionResult,
    claim: CausalClaim,
    pass_index: int,
    search_config: ClaimAdjudicationSearchConfig,
) -> ClaimAdjudicationResult:
    variant = select_prompt_variant(search_config, pass_index)
    source_basis = claim.source_basis.value if claim.source_basis else result.source_basis.value
    supporting = [span.model_dump(mode="json") for span in claim.supporting_spans]
    method_spans = [span.model_dump(mode="json") for span in claim.method_spans]
    prompt = f"""
Adjudicate a single extracted literature claim for causal validity.
Return strict JSON only:
{CLAIM_ADJUDICATION_SCHEMA_HINT}

Rules:
- Distinguish between the paper asserting causality and the graph treating it as a credible causal edge.
- Be conservative.
- panel FE, OLS, generic regression, and ML prediction are not strong causal evidence by themselves.
- abstract_only claims with weak designs (OLS, panel_FE) should almost never be publishable.
- abstract_only claims with strong designs (RCT, IV, DiD, RDD) CAN be publishable if the abstract clearly describes the identification strategy.
- If design evidence is missing, prefer weak or unclear.
- Use the effect_size and confidence_interval below (if available) to assess whether the claim is quantitatively grounded. A precise numeric effect with CI is more credible than a vague directional claim.

Calibration note:
{variant}

Paper:
title: {result.title}
methodology: {result.methodology}
methodology_enum: {result.methodology_enum.value}
source_basis: {source_basis}
text_quality: {result.text_quality.value}

Claim:
claim_text: {claim.claim_text}
cause_variable: {claim.cause_variable}
effect_variable: {claim.effect_variable}
direction: {claim.direction.value}
claim_explicitness: {claim.claim_explicitness.value}
design_family_hint: {claim.design_family_hint.value}
effect_size: {claim.effect_size if claim.effect_size is not None else "[not provided]"}
scope_conditions: {json.dumps(claim.scope_conditions or [], ensure_ascii=False)}

Supporting spans:
{json.dumps(supporting, ensure_ascii=False)}

Method spans:
{json.dumps(method_spans, ensure_ascii=False)}
""".strip()
    response = await pool.chat_json(model=model, prompt=prompt, temperature=0.0)
    if response.http_status != 200 or not response.parsed:
        logger.warning(
            "LLM FAIL (status=%s, error=%s) %s — fallback",
            response.http_status,
            response.error_class,
            result.openalex_id,
        )
        return _fallback_adjudication(result, claim)
    payload = _normalize_adjudication_payload(
        result=result,
        claim=claim,
        parsed=response.parsed,
        pass_index=pass_index,
        total_passes=1,
    )
    adj = ClaimAdjudicationResult.model_validate(payload)
    logger.info(
        "LLM OK %s validity=%.2f publish=%s latency=%.0fms",
        result.openalex_id,
        adj.claim_validity_score,
        adj.publishable_edge,
        response.latency_ms,
    )
    return adj


async def run_claim_adjudicate(config: AcademicBatchConfig) -> dict[str, int | float]:
    """Run claim adjudicate with checkpoint support."""
    import time as _time
    from pathlib import Path

    from polisyos.academic.batch.resolve_extract import GonkaMultiKeyPool

    started_at = datetime.now(UTC).isoformat()
    search_config = load_claim_adjudication_config(context={"academic_config": config})
    rows = _load_article_results(config)
    if not rows:
        write_stage_manifest(
            manifest_path=config.manifests_dir / "claim_adjudicate.json",
            stage="claim_adjudicate",
            status="ok",
            metrics={"claims": 0, "passes": 0},
            artifacts=[],
            started_at=started_at,
        )
        return {"claims": 0, "passes": 0}

    pass_rows: list[dict[str, Any]] = []
    llm_calls = 0
    deterministic_fallbacks = 0

    total_claims = sum(len(r.causal_claims) for r in rows)

    # --- Checkpoint: load previously completed claim_ids ---
    checkpoint_path = Path(str(config.claim_adjudication_passes_path) + ".checkpoint.jsonl")
    done_claim_ids: set[str] = set()
    if checkpoint_path.exists():
        with open(checkpoint_path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    cid = str(obj.get("claim_id") or "")
                    if cid:
                        done_claim_ids.add(cid)
                        pass_rows.append(obj)
                        if obj.get("adjudication_notes") == "fallback_adjudication_without_llm":
                            deterministic_fallbacks += 1
                        else:
                            llm_calls += 1
                except json.JSONDecodeError:
                    continue
        logger.info(
            "claim_adjudicate: resumed from checkpoint — %d claims already done (%d llm, %d fallback)",
            len(done_claim_ids),
            llm_calls,
            deterministic_fallbacks,
        )

    logger.info(
        "claim_adjudicate: %d articles, %d claims, keys=%d",
        len(rows),
        total_claims,
        len(config.gonka_api_keys),
    )

    if not config.gonka_api_keys:
        for result in rows:
            for claim in result.causal_claims:
                cid = _claim_id_for(result, claim)
                if cid in done_claim_ids:
                    continue
                fallback = _fallback_adjudication(result, claim)
                row = {**fallback.model_dump(mode="json"), "pass_index": 0}
                pass_rows.append(row)
                deterministic_fallbacks += 1
        logger.info(
            "claim_adjudicate: all %d claims adjudicated via deterministic fallback",
            deterministic_fallbacks,
        )
    else:
        async with GonkaMultiKeyPool(config) as pool:
            logger.info(
                "claim_adjudicate: pool started with %d clients, aggregate RPS=%.1f",
                pool.client_count,
                pool.theoretical_aggregate_rps,
            )
            sem = asyncio.Semaphore(config.article_max_concurrent_llm)
            completed_count = len(done_claim_ids)
            batch_size = 200
            checkpoint_every = 100  # flush to disk every N completions
            checkpoint_pending = 0
            t0 = _time.monotonic()

            # Open checkpoint file for appending new results
            checkpoint_fh = open(checkpoint_path, "a", encoding="utf-8")

            async def _run_one(
                pass_index: int, result: ArticleExtractionResult, claim: CausalClaim
            ) -> tuple[int, ClaimAdjudicationResult]:
                if not claim.supporting_spans:
                    return pass_index, _fallback_adjudication(result, claim)
                async with sem:
                    try:
                        adjudication = await _adjudicate_with_pool(
                            pool=pool,
                            model=config.article_extraction_model,
                            result=result,
                            claim=claim,
                            pass_index=pass_index,
                            search_config=search_config,
                        )
                    except Exception:
                        logger.warning(
                            "LLM exception for %s — fallback", result.openalex_id, exc_info=True
                        )
                        adjudication = _fallback_adjudication(result, claim)
                return pass_index, adjudication

            # Build work items — 1 pass, skip already-done claims
            work_items: list[tuple[int, ArticleExtractionResult, CausalClaim]] = []
            for result in rows:
                for claim in result.causal_claims:
                    cid = _claim_id_for(result, claim)
                    if cid in done_claim_ids:
                        continue
                    work_items.append((0, result, claim))

            total_items = len(work_items) + len(done_claim_ids)
            logger.info(
                "claim_adjudicate: %d remaining work items (of %d total), batches of %d",
                len(work_items),
                total_items,
                batch_size,
            )

            try:
                for batch_start in range(0, len(work_items), batch_size):
                    batch = work_items[batch_start : batch_start + batch_size]
                    tasks = [asyncio.create_task(_run_one(pi, res, cl)) for pi, res, cl in batch]
                    for task in asyncio.as_completed(tasks):
                        pass_index, adjudication = await task
                        row = adjudication.model_dump(mode="json")
                        row["pass_index"] = pass_index
                        pass_rows.append(row)

                        # Write to checkpoint immediately
                        checkpoint_fh.write(json.dumps(row, ensure_ascii=False) + "\n")
                        checkpoint_pending += 1
                        if checkpoint_pending >= checkpoint_every:
                            checkpoint_fh.flush()
                            checkpoint_pending = 0

                        if adjudication.adjudication_notes == "fallback_adjudication_without_llm":
                            deterministic_fallbacks += 1
                        else:
                            llm_calls += 1
                        completed_count += 1

                        if completed_count % 100 == 0:
                            elapsed = _time.monotonic() - t0
                            rate = (completed_count - len(done_claim_ids)) / max(elapsed, 1.0)
                            remaining = (total_items - completed_count) / max(rate, 0.01)
                            logger.info(
                                "progress: %d/%d (llm=%d fallback=%d) %.1f/s ETA %.0fm",
                                completed_count,
                                total_items,
                                llm_calls,
                                deterministic_fallbacks,
                                rate,
                                remaining / 60.0,
                            )
            finally:
                checkpoint_fh.flush()
                checkpoint_fh.close()

    # Write final sorted results
    with open(config.claim_adjudication_passes_path, "w", encoding="utf-8") as fh:
        for row in sorted(
            pass_rows,
            key=lambda item: (str(item.get("claim_id") or ""), int(item.get("pass_index") or 0)),
        ):
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")

    # Clean up checkpoint after successful completion
    if checkpoint_path.exists():
        checkpoint_path.unlink()
        logger.info("claim_adjudicate: checkpoint file removed after successful completion")

    metrics: dict[str, int | float] = {
        "claims": len({str(row.get("claim_id") or "") for row in pass_rows}),
        "passes": len(pass_rows),
        "llm_calls": llm_calls,
        "deterministic_fallbacks": deterministic_fallbacks,
    }
    write_stage_manifest(
        manifest_path=config.manifests_dir / "claim_adjudicate.json",
        stage="claim_adjudicate",
        status="ok",
        metrics=metrics,
        artifacts=[config.claim_adjudication_passes_path],
        started_at=started_at,
    )
    logger.info(
        "claim_adjudicate DONE: %d claims, %d llm, %d fallback",
        metrics["claims"],
        llm_calls,
        deterministic_fallbacks,
    )
    return metrics


def run_consensus_aggregate(config: AcademicBatchConfig) -> dict[str, int | float]:
    """Run consensus aggregate."""
    started_at = datetime.now(UTC).isoformat()
    search_config = load_claim_adjudication_config(context={"academic_config": config})
    grouped: dict[str, list[ClaimAdjudicationResult]] = defaultdict(list)
    contradiction_ids = _intra_paper_contradictions(_load_article_results(config))
    if not config.claim_adjudication_passes_path.exists():
        write_stage_manifest(
            manifest_path=config.manifests_dir / "consensus_aggregate.json",
            stage="consensus_aggregate",
            status="ok",
            metrics={"claims": 0, "published": 0},
            artifacts=[],
            started_at=started_at,
        )
        return {"claims": 0, "published": 0}

    with open(config.claim_adjudication_passes_path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            row.pop("pass_index", None)
            adjudication = ClaimAdjudicationResult.model_validate(row)
            grouped[adjudication.claim_id].append(adjudication)

    aggregated: list[ClaimAdjudicationResult] = []
    for rows in grouped.values():
        item = aggregate_claim_rows(rows, search_config)
        if item.claim_id in contradiction_ids:
            notes = " | ".join(
                part
                for part in [item.adjudication_notes, "intra_paper_direction_contradiction"]
                if part
            )
            item = item.model_copy(
                update={
                    "publishable_edge": False,
                    "intra_paper_contradiction": True,
                    "adjudication_notes": notes[:800],
                }
            )
        aggregated.append(item)
    with open(config.claim_adjudications_path, "w", encoding="utf-8") as fh:
        for item in sorted(aggregated, key=lambda row: (row.openalex_id, row.claim_id)):
            fh.write(item.model_dump_json() + "\n")

    stability_values = [row.consensus_stability for row in aggregated]
    report = {
        "claims": len(aggregated),
        "published": sum(1 for row in aggregated if row.publishable_edge),
        "avg_consensus_stability": round(sum(stability_values) / max(1, len(stability_values)), 6),
    }
    with open(config.claim_consensus_report_path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)

    write_stage_manifest(
        manifest_path=config.manifests_dir / "consensus_aggregate.json",
        stage="consensus_aggregate",
        status="ok",
        metrics=report,
        artifacts=[config.claim_adjudications_path, config.claim_consensus_report_path],
        started_at=started_at,
    )
    return report


__all__ = ["run_claim_adjudicate", "run_consensus_aggregate"]
