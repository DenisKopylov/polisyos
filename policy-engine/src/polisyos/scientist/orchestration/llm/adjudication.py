"""Deterministic adjudication records for multi-model Scientist variants."""

from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

SCHEMA_VERSION = "policyos.scientist.llm_model_adjudication.v1"
DISAGREEMENT_CODE = "multi_model_policy_disagreement"
ADJUDICATION_CODE = "llm_model_variant_adjudication"


def _text(value: object) -> str:
    return str(value or "").strip()


def _as_refs(value: object) -> list[str]:
    if isinstance(value, str):
        return [_text(value)] if _text(value) else []
    if not isinstance(value, list | tuple | set):
        return []
    refs: list[str] = []
    for item in value:
        ref = _text(item)
        if ref and ref not in refs:
            refs.append(ref)
    return refs


def _claim_id(claim: Mapping[str, Any], index: int) -> str:
    return _text(claim.get("claim_id") or claim.get("id") or f"claim_{index + 1}")


def _claim_text(claim: Mapping[str, Any]) -> str:
    return _text(claim.get("text") or claim.get("claim") or claim.get("statement"))


def _claim_family(claim: Mapping[str, Any]) -> str:
    raw = (
        claim.get("claim_family")
        or claim.get("family")
        or claim.get("claim_type")
        or claim.get("type")
        or "recommendation"
    )
    token = re.sub(r"[^a-z0-9_]+", "_", _text(raw).casefold()).strip("_")
    return token or "recommendation"


def _is_major_claim(claim: Mapping[str, Any]) -> bool:
    value = claim.get("major")
    if value is None:
        return True
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().casefold() not in {"false", "0", "no", "minor"}
    return bool(value)


def _claim_evidence_refs(claim: Mapping[str, Any]) -> list[str]:
    grounding = claim.get("grounding")
    grounding_map = grounding if isinstance(grounding, Mapping) else {}
    refs: list[str] = []
    for source in (claim, grounding_map):
        for key in (
            "data_refs",
            "data_source_refs",
            "source_refs",
            "fabric_refs",
            "data_snapshot_refs",
            "method_refs",
            "foundry_method_refs",
            "analysis_refs",
            "norm_refs",
            "normative_refs",
            "norm_ids",
            "legal_refs",
        ):
            refs.extend(_as_refs(source.get(key)))
    deduped: list[str] = []
    for ref in refs:
        if ref not in deduped:
            deduped.append(ref)
    return deduped


def _no_grounding_rationale(claim: Mapping[str, Any]) -> str:
    grounding = claim.get("grounding")
    grounding_map = grounding if isinstance(grounding, Mapping) else {}
    return _text(
        claim.get("no_grounding_rationale")
        or claim.get("grounding_rationale")
        or claim.get("not_grounded_rationale")
        or grounding_map.get("no_grounding_rationale")
    )


def _recommendation_signature(claim: Mapping[str, Any]) -> str | None:
    if _claim_family(claim) != "recommendation" or not _is_major_claim(claim):
        return None
    action = _text(
        claim.get("policy_action")
        or claim.get("action")
        or claim.get("intervention")
        or claim.get("intervention_type")
    )
    signature = action or _claim_text(claim)
    return re.sub(r"\s+", " ", signature.casefold()).strip() or None


def _variant_id(variant: Mapping[str, Any], index: int) -> str:
    return _text(
        variant.get("model_variant_id")
        or variant.get("variant_id")
        or variant.get("model")
        or f"variant_{index + 1}"
    )


def _variant_ref(variant: Mapping[str, Any], index: int) -> dict[str, str]:
    ref: dict[str, str] = {"model_variant_id": _variant_id(variant, index)}
    for key in (
        "model",
        "provider",
        "trinity_bundle_ref",
        "final_policy_claims_ref",
        "policy_grounding_matrix_ref",
    ):
        value = _text(variant.get(key))
        if value:
            ref[key] = value
    return ref


def _claims_from_variant(variant: Mapping[str, Any]) -> list[dict[str, Any]]:
    raw_claims = (
        variant.get("claims")
        or variant.get("policy_claims")
        or variant.get("recommendations")
    )
    if raw_claims is None:
        report = variant.get("final_policy_claims")
        if isinstance(report, Mapping):
            raw_claims = report.get("claims")
    if not isinstance(raw_claims, list):
        return []
    return [dict(claim) for claim in raw_claims if isinstance(claim, Mapping)]


def _major_recommendation_summaries(claims: list[dict[str, Any]]) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    for index, claim in enumerate(claims):
        signature = _recommendation_signature(claim)
        if not signature:
            continue
        summaries.append(
            {
                "claim_id": _claim_id(claim, index),
                "text": _claim_text(claim),
                "policy_action": _text(
                    claim.get("policy_action")
                    or claim.get("action")
                    or claim.get("intervention")
                    or claim.get("intervention_type")
                )
                or None,
                "signature": signature,
                "evidence_refs": _claim_evidence_refs(claim),
            }
        )
    return summaries


def _variant_evidence_refs(claims: list[dict[str, Any]]) -> list[str]:
    refs: list[str] = []
    for claim in claims:
        refs.extend(_claim_evidence_refs(claim))
    deduped: list[str] = []
    for ref in refs:
        if ref not in deduped:
            deduped.append(ref)
    return deduped


def _unsupported_major_claim_ids(claims: list[dict[str, Any]]) -> list[str]:
    unsupported: list[str] = []
    for index, claim in enumerate(claims):
        if not _is_major_claim(claim):
            continue
        if _claim_evidence_refs(claim) or _no_grounding_rationale(claim):
            continue
        unsupported.append(_claim_id(claim, index))
    return unsupported


def _material_disagreements(
    variant_claims: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    signatures_by_variant: dict[str, list[str]] = {}
    variant_refs: list[dict[str, str]] = []
    for index, variant in enumerate(variant_claims):
        signatures = [
            str(item.get("signature"))
            for item in variant.get("major_recommendations") or []
            if item.get("signature")
        ]
        signatures = sorted(set(signatures))
        if not signatures:
            continue
        variant_id = _variant_id(variant, index)
        signatures_by_variant[variant_id] = signatures
        ref_payload = variant.get("variant_ref")
        variant_refs.append(
            dict(ref_payload)
            if isinstance(ref_payload, Mapping)
            else _variant_ref(variant, index)
        )
    if len({tuple(value) for value in signatures_by_variant.values()}) <= 1:
        return []
    return [
        {
            "code": DISAGREEMENT_CODE,
            "severity": "fail",
            "message": (
                "LLM model variants produced materially different major "
                "recommendation actions."
            ),
            "variant_refs": variant_refs,
            "variant_signatures": signatures_by_variant,
            "next_action": (
                "Review the adjudication decision, selected variant rationale, "
                "and claim evidence refs before approving serious quality."
            ),
        }
    ]


def build_model_variant_adjudication(
    *,
    variants: list[Mapping[str, Any]],
    selected_variant: Mapping[str, Any],
) -> dict[str, Any]:
    """Build a stable adjudication packet for persisted LLM model variants."""
    selected_variant_id = _text(selected_variant.get("model_variant_id"))
    variant_claims: list[dict[str, Any]] = []
    selected_claims: list[dict[str, Any]] = []
    selected_ref: dict[str, str] = {}

    for index, variant in enumerate(variants):
        claims = _claims_from_variant(variant)
        ref = _variant_ref(variant, index)
        variant_id = ref["model_variant_id"]
        if variant_id == selected_variant_id:
            selected_claims = claims
            selected_ref = ref
        variant_claims.append(
            {
                "model_variant_id": variant_id,
                "model": ref.get("model"),
                "provider": ref.get("provider"),
                "status": variant.get("status"),
                "verdict": variant.get("verdict"),
                "selected_for_workflow": variant_id == selected_variant_id,
                "variant_ref": ref,
                "claim_count": len(claims),
                "major_recommendations": _major_recommendation_summaries(claims),
                "evidence_refs": _variant_evidence_refs(claims),
                "unsupported_major_claim_ids": _unsupported_major_claim_ids(claims),
            }
        )

    if not selected_claims:
        selected_claims = _claims_from_variant(selected_variant)
    if not selected_ref:
        selected_ref = _variant_ref(selected_variant, 0)

    disagreements = _material_disagreements(variant_claims)
    selected_evidence_refs = _variant_evidence_refs(selected_claims)
    selected_unsupported = _unsupported_major_claim_ids(selected_claims)
    disagreement_codes = [item["code"] for item in disagreements]
    support_status = (
        "unsupported_claims_present" if selected_unsupported else "selected_claims_supported"
    )
    rationale_parts = [
        f"Selected {selected_variant_id or selected_ref.get('model_variant_id')} for workflow.",
        "It produced a usable Trinity bundle and completed the model-variant pipeline.",
    ]
    if disagreements:
        rationale_parts.append(
            "Material recommendation differences were adjudicated against the selected "
            "variant's explicit claim evidence refs."
        )
    if selected_evidence_refs:
        rationale_parts.append("Selected major recommendations include evidence refs.")
    if selected_unsupported:
        rationale_parts.append(
            "Unsupported selected major claims remain blocking in the grounding matrix."
        )
    decision = {
        "code": ADJUDICATION_CODE,
        "decision": "select_variant",
        "status": "adjudicated" if disagreements else "selected_without_disagreement",
        "support_status": support_status,
        "selected_variant_id": selected_variant_id or selected_ref.get("model_variant_id"),
        "selected_variant_ref": selected_ref,
        "rationale": " ".join(rationale_parts),
        "evidence_refs": selected_evidence_refs,
        "disagreement_codes": disagreement_codes,
        "unsupported_selected_claim_ids": selected_unsupported,
        "next_action": (
            "Fix unsupported selected claims before approval."
            if selected_unsupported
            else "Retain this adjudication packet with the final policy quality evidence."
        ),
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "status": "fail" if selected_unsupported else "pass",
        "decision": decision,
        "selected_variant_id": decision["selected_variant_id"],
        "selected_variant_rationale": decision["rationale"],
        "selected_variant_evidence_refs": selected_evidence_refs,
        "variant_claims": variant_claims,
        "disagreements": disagreements,
        "summary": {
            "variant_count": len(variant_claims),
            "disagreement_count": len(disagreements),
            "selected_evidence_ref_count": len(selected_evidence_refs),
            "unsupported_selected_claim_count": len(selected_unsupported),
        },
    }


__all__ = [
    "ADJUDICATION_CODE",
    "DISAGREEMENT_CODE",
    "SCHEMA_VERSION",
    "build_model_variant_adjudication",
]
