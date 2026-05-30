"""Normative applicability quality reports for policy canaries."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from datetime import date

from polisyos.lex.common import parse_iso_date
from polisyos.lex.normpack.legal_authority import build_legal_authority_report
from polisyos.lex.normpack.query_normalization import (
    legal_requirements_from_query_normalization_report,
    legal_requirements_from_scenario_contract,
    normalize_lex_query_terms,
)

SCHEMA_VERSION = "policyos.lex.normative_applicability_report.v1"
_CANDIDATE_NORM_KEYS = frozenset(
    {
        "applied_norms",
        "candidate_norms",
        "lex_candidate_norms",
        "normative_candidate_norms",
        "normative_facts",
    }
)
_NORM_PACK_KEYS = frozenset(
    {
        "legal_candidate_pack",
        "legal_source_pack",
        "norm_pack",
        "normative_pack",
    }
)
_RECOMMENDATION_KEYS = frozenset(
    {
        "claims",
        "claim_supports",
        "policy_claims",
        "policy_recommendations",
        "recommendation_claims",
        "recommendations",
    }
)


def _text(value: object) -> str:
    return str(value or "").strip()


def _text_list(value: object) -> list[str]:
    if isinstance(value, str):
        token = _text(value)
        return [token] if token else []
    if isinstance(value, list | tuple | set):
        return [token for item in value if (token := _text(item))]
    return []


def _mapping_list(value: object) -> list[dict[str, Any]]:
    if isinstance(value, Mapping):
        return [dict(value)]
    if isinstance(value, list | tuple):
        return [dict(item) for item in value if isinstance(item, Mapping)]
    return []


def _mapping(value: object) -> dict[str, Any] | None:
    if isinstance(value, Mapping):
        return {str(key): item for key, item in value.items()}
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        dumped = to_dict()
        if isinstance(dumped, Mapping):
            return {str(key): item for key, item in dumped.items()}
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        try:
            dumped = model_dump(mode="json")
        except TypeError:
            dumped = model_dump()
        if isinstance(dumped, Mapping):
            return {str(key): item for key, item in dumped.items()}
    return None


def _list(value: object) -> list[Any]:
    if isinstance(value, list | tuple):
        return list(value)
    return []


def _first_token(value: object) -> str:
    if isinstance(value, list | tuple | set):
        for item in value:
            token = _text(item)
            if token:
                return token
        return ""
    return _text(value)


def _first_country_code(context: Mapping[str, Any]) -> str:
    countries = context.get("countries")
    if isinstance(countries, list | tuple):
        for country in countries:
            token = _text(country).upper()
            if token:
                return token
    for key in ("country_code", "country", "jurisdiction", "jurisdiction_norm"):
        token = _text(context.get(key)).upper()
        if token:
            return token
    return ""


def _domain_from_payload(payload: Mapping[str, Any]) -> str:
    return _text(
        payload.get("policy_domain")
        or payload.get("top_domain")
        or payload.get("domain")
        or payload.get("domain_hint")
    )


def _stable_ref(payload: Mapping[str, Any]) -> str:
    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        default=str,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(canonical).hexdigest()


def _default_query_terms(
    *,
    target_context: Mapping[str, Any],
    recommendation_claims: list[dict[str, Any]],
) -> list[str]:
    terms = [
        _domain_from_payload(target_context),
        _text(target_context.get("jurisdiction") or target_context.get("jurisdiction_norm")),
    ]
    for claim in recommendation_claims[:3]:
        terms.append(
            _text(
                claim.get("text")
                or claim.get("recommended_action")
                or claim.get("description")
                or claim.get("claim_id")
            )
        )
    return list(dict.fromkeys(term for term in terms if term))


def _default_concept_refs(target_context: Mapping[str, Any]) -> list[str]:
    return list(
        dict.fromkeys(
            [
                *_text_list(target_context.get("concept_refs")),
                *_text_list(target_context.get("canonical_concept_refs")),
                *_text_list(target_context.get("legal_concept_refs")),
            ]
        )
    )


def _query_normalization_payload(
    *,
    query_normalization_report: Mapping[str, Any] | None,
    query_terms: list[str],
    target_context: Mapping[str, Any],
    scenario_evidence_contract: Mapping[str, Any] | None,
    kg_paths: list[str],
    candidate_norm_count: int,
    blocker_code: str | None,
) -> dict[str, Any]:
    provided = _mapping(query_normalization_report)
    if provided is not None:
        payload = dict(provided)
        if candidate_norm_count == 0 and not _text(payload.get("blocker_code")):
            payload["blocker_code"] = blocker_code or "no_relevant_norm_found"
        if not _text_list(payload.get("kg_paths")) and kg_paths:
            payload["kg_paths"] = kg_paths
        if not _text_list(payload.get("original_terms")):
            payload["original_terms"] = query_terms
        if not _text_list(payload.get("normalized_terms")):
            payload["normalized_terms"] = query_terms
        return payload
    return normalize_lex_query_terms(
        original_terms=query_terms,
        target_context=target_context,
        scenario_evidence_contract=scenario_evidence_contract,
        kg_paths=kg_paths,
        candidate_norm_count=candidate_norm_count,
        blocker_code=blocker_code,
    ).to_dict()


def _query_normalization_trace_issue(
    query_normalization_report: Mapping[str, Any],
) -> dict[str, Any] | None:
    normalized_terms = _text_list(query_normalization_report.get("normalized_terms"))
    original_terms = _text_list(query_normalization_report.get("original_terms"))
    kg_paths = _text_list(query_normalization_report.get("kg_paths"))
    language_coverage = _mapping(query_normalization_report.get("language_coverage")) or {}
    blocker_code = _text(query_normalization_report.get("blocker_code"))
    if (
        normalized_terms
        and original_terms
        and kg_paths
        and language_coverage.get("status") == "pass"
        and blocker_code
    ):
        return None
    missing: list[str] = []
    if not original_terms:
        missing.append("original_terms")
    if not normalized_terms:
        missing.append("normalized_terms")
    if not kg_paths:
        missing.append("kg_paths")
    if language_coverage.get("status") != "pass":
        missing.append("language_coverage")
    if not blocker_code:
        missing.append("blocker_code")
    return _issue(
        code="lex_zero_candidate_query_trace_incomplete",
        message=(
            "Lex returned zero candidate norms without a complete bilingual query "
            f"normalization trace: {', '.join(missing)}."
        ),
        next_action=(
            "Emit normalized bilingual query terms, KG path, language coverage, and "
            "a typed no-norm blocker before treating zero candidates as meaningful."
        ),
    )


def _legal_requirements_from_inputs(
    *,
    scenario_evidence_contract: Mapping[str, Any] | None,
    query_normalization_report: Mapping[str, Any],
) -> list[dict[str, Any]]:
    requirements = [
        *legal_requirements_from_scenario_contract(scenario_evidence_contract),
        *legal_requirements_from_query_normalization_report(query_normalization_report),
    ]
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, requirement in enumerate(requirements):
        requirement_id = _text(requirement.get("requirement_id"))
        fingerprint = requirement_id or _stable_ref(
            {"index": index, "legal_requirement": requirement}
        )
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        result.append(requirement)
    return result


def _jurisdiction_filters(
    *,
    explicit: list[str] | None,
    target_jurisdiction: str,
) -> list[str]:
    values = explicit if explicit is not None else [target_jurisdiction]
    return list(dict.fromkeys(value for value in values if value))


def _time_filters(*, explicit: list[str] | None, as_of: str) -> list[str]:
    values = explicit if explicit is not None else [as_of]
    return list(dict.fromkeys(value for value in values if value))


def _legal_corpus_snapshot(
    *,
    legal_corpus_snapshot: Mapping[str, Any] | None,
    target_context: Mapping[str, Any],
    candidate_norms: list[dict[str, Any]],
    retrieval_status: str,
) -> dict[str, Any]:
    provided = _mapping(legal_corpus_snapshot)
    if provided is not None:
        return provided
    if retrieval_status == "missing_store":
        return {
            "store_status": "missing",
            "candidate_norm_count": len(candidate_norms),
        }
    return {
        "snapshot_ref": _stable_ref(
            {
                "kind": "lex.inline_candidate_norm_snapshot",
                "target_context": dict(target_context),
                "candidate_norm_ids": [_norm_id(norm) for norm in candidate_norms],
            }
        ),
        "store_kind": "runtime_candidate_norms",
        "candidate_norm_count": len(candidate_norms),
    }


def _legal_kg_paths_from_snapshot(snapshot: Mapping[str, Any] | None) -> list[str]:
    payload = _mapping(snapshot) or {}
    paths: list[str] = []
    for key in (
        "kg_path",
        "legal_kg_db_path",
        "legal_kg_path",
        "db_path",
        "path",
        "snapshot_path",
    ):
        paths.extend(_text_list(payload.get(key)))
    return list(dict.fromkeys(paths))


def _legal_kg_paths_from_runtime_context(context: Mapping[str, Any]) -> list[str]:
    paths: list[str] = []
    for mapping in _walk_mappings(context):
        for key in (
            "legal_kg_db_path",
            "legal_kg_path",
            "lex_kg_db_path",
            "lex_knowledge_graph_path",
        ):
            paths.extend(_text_list(mapping.get(key)))
    return list(dict.fromkeys(paths))


def _retrieval_status(
    *,
    explicit: str | None,
    candidate_norms: list[dict[str, Any]],
) -> str:
    token = _text(explicit).casefold()
    aliases = {
        "complete": "completed",
        "success": "completed",
        "ok": "completed",
        "no_norms_retrieved": "no_relevant_norm_found",
        "no_relevant_evidence": "no_relevant_norm_found",
        "retrieval_failure": "retrieval_failed",
        "failed": "retrieval_failed",
        "store_missing": "missing_store",
        "missing_legal_store": "missing_store",
    }
    if token:
        return aliases.get(token, token)
    return "completed" if candidate_norms else "no_relevant_norm_found"


def _retrieval_blocker_for_status(status: str) -> dict[str, Any] | None:
    if status == "no_relevant_norm_found":
        return {
            "code": "no_relevant_norm_found",
            "blocker_type": "no_relevant_norm_found",
            "message": "Lex retrieval completed but found no relevant norms.",
            "next_action": (
                "Keep legal authority blocked or broaden the legal query with explicit "
                "jurisdiction, time, and concept terms."
            ),
        }
    if status == "retrieval_failed":
        return {
            "code": "lex_retrieval_failed",
            "blocker_type": "retrieval_failure",
            "message": "Lex retrieval failed before relevant norms could be selected.",
            "next_action": "Retry Lex retrieval and preserve the retrieval error trace.",
        }
    if status == "missing_store":
        return {
            "code": "lex_legal_store_missing",
            "blocker_type": "missing_store",
            "message": "Lex legal store is missing or not configured.",
            "next_action": "Configure a legal knowledge store or emit a missing-store blocker.",
        }
    return None


def _issue_from_blocker(blocker: Mapping[str, Any]) -> dict[str, Any]:
    return _issue(
        code=_text(blocker.get("code")) or "lex_retrieval_blocked",
        message=_text(blocker.get("message")) or "Lex retrieval emitted a typed blocker.",
        next_action=_text(blocker.get("next_action")) or "Resolve the Lex retrieval blocker.",
    )


def _competence_rows(applied_norms: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for norm in applied_norms:
        authority, level = _norm_authority(norm)
        norm_id = _norm_id(norm)
        if not norm_id:
            continue
        rows.append(
            {
                "norm_id": norm_id,
                "jurisdiction": _norm_jurisdiction(norm),
                "source_authority": authority,
                "authority_level": level,
                "competent_authority": _text(norm.get("competent_authority")) or authority,
            }
        )
    return rows


def _walk_mappings(value: object, *, depth: int = 0) -> list[dict[str, Any]]:
    if depth > 8:
        return []
    mapped = _mapping(value)
    if mapped is not None:
        result = [mapped]
        for item in mapped.values():
            result.extend(_walk_mappings(item, depth=depth + 1))
        return result
    if isinstance(value, list | tuple):
        result: list[dict[str, Any]] = []
        for item in value:
            result.extend(_walk_mappings(item, depth=depth + 1))
        return result
    return []


def _norm_id(norm: dict[str, Any]) -> str:
    return _text(norm.get("norm_id") or norm.get("id") or norm.get("artifact_id"))


def _norm_jurisdiction(norm: dict[str, Any]) -> str:
    return _text(norm.get("jurisdiction") or norm.get("jurisdiction_norm"))


def _norm_domain(norm: dict[str, Any]) -> str:
    return _text(norm.get("policy_domain") or norm.get("top_domain") or norm.get("domain"))


def _norm_authority(norm: dict[str, Any]) -> tuple[str, str]:
    authority = _text(
        norm.get("source_authority")
        or norm.get("authority")
        or norm.get("publisher")
        or norm.get("doc_source_authority")
    )
    level = _text(norm.get("authority_level") or norm.get("source_authority_level"))
    return authority, level


def _first_selector_value(selector: object) -> str:
    selector_payload = _mapping(selector)
    if selector_payload is None:
        return _first_token(selector)
    return _first_token(
        selector_payload.get("any_of")
        or selector_payload.get("all_of")
        or selector_payload.get("value")
    )


def _norm_from_pack_rule(
    rule: dict[str, Any],
    *,
    pack_defaults: Mapping[str, Any],
) -> dict[str, Any]:
    norm = dict(rule)
    metadata = _mapping(norm.get("metadata")) or {}
    backend_metadata = _mapping(norm.get("backend_metadata")) or {}
    applicability = _mapping(norm.get("applicability")) or {}
    applicability_time = _mapping(applicability.get("time")) or {}
    applicability_jurisdiction = _mapping(applicability.get("jurisdiction")) or {}

    if not _norm_jurisdiction(norm):
        norm["jurisdiction"] = (
            _first_selector_value(applicability_jurisdiction)
            or _text(pack_defaults.get("jurisdiction"))
        )
    if not _norm_domain(norm):
        norm["policy_domain"] = (
            _domain_from_payload(backend_metadata)
            or _domain_from_payload(metadata)
            or _domain_from_payload(pack_defaults)
        )
    if not _text(norm.get("effective_from")):
        norm["effective_from"] = _text(
            applicability_time.get("valid_from") or pack_defaults.get("effective_date")
        )
    if not _text(norm.get("effective_to")):
        norm["effective_to"] = _text(applicability_time.get("valid_to"))
    authority, level = _norm_authority(norm)
    if not authority:
        norm["source_authority"] = _text(
            backend_metadata.get("source_authority")
            or metadata.get("source_authority")
            or pack_defaults.get("source_authority")
            or pack_defaults.get("authority")
        )
    if not level:
        norm["authority_level"] = _text(
            backend_metadata.get("authority_level")
            or metadata.get("authority_level")
            or pack_defaults.get("authority_level")
        )
    if "relevance_rationale" not in norm and norm.get("description"):
        norm["relevance_rationale"] = norm["description"]
    return norm


def _candidate_norms_from_runtime_payload(context: Mapping[str, Any]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for mapping in _walk_mappings(context):
        for key, value in mapping.items():
            if key in _CANDIDATE_NORM_KEYS:
                candidates.extend(
                    candidate
                    for item in _list(value)
                    if (candidate := _mapping(item)) is not None
                )
            if key in _NORM_PACK_KEYS:
                pack = _mapping(value)
                if pack is not None:
                    candidates.extend(_candidate_norms_from_pack(pack))
    for mapping in _walk_mappings(context):
        if "norms" in mapping and ("pack_id" in mapping or "jurisdiction" in mapping):
            candidates.extend(_candidate_norms_from_pack(mapping))
    return _dedupe_norms(candidates)


def _candidate_norms_from_lex_kg(
    *,
    kg_paths: list[str],
    query_terms: list[str],
    target_context: Mapping[str, Any],
    top_k_per_term: int = 5,
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    if not kg_paths or not query_terms:
        return candidates
    try:
        from polisyos.data_forge.read_api.legal import search_legal_knowledge_graph
    except (ImportError, RuntimeError):
        return candidates
    try:
        import duckdb

        search_errors = (OSError, RuntimeError, TypeError, ValueError, duckdb.Error)
    except ImportError:
        search_errors = (OSError, RuntimeError, TypeError, ValueError)
    target_jurisdiction = _text(
        target_context.get("jurisdiction") or target_context.get("jurisdiction_norm")
    )
    target_domain = _text(
        target_context.get("policy_domain")
        or target_context.get("top_domain")
        or target_context.get("domain")
    )
    for kg_path_raw in kg_paths[:3]:
        output_dir = _lex_kg_output_dir(kg_path_raw)
        db_path = output_dir / "lex_knowledge_graph.duckdb"
        if not db_path.exists():
            continue
        for term in query_terms[:16]:
            if len(term) < 3:
                continue
            try:
                rows = search_legal_knowledge_graph(
                    output_dir=output_dir,
                    query=term,
                    top_k=top_k_per_term,
                )
            except search_errors:
                continue
            for row in rows:
                norm_id = _text(getattr(row, "fact_id", ""))
                if not norm_id:
                    continue
                doc_name = _text(getattr(row, "doc_name", ""))
                candidates.append(
                    {
                        "norm_id": norm_id,
                        "artifact_id": norm_id,
                        "fact_class": _text(getattr(row, "norm_type_canon", ""))
                        or _text(getattr(row, "norm_type", ""))
                        or "lex_kg_fact",
                        "jurisdiction": target_jurisdiction,
                        "policy_domain": target_domain,
                        "source_authority": doc_name or "Lex legal knowledge graph",
                        "authority_level": "lex_knowledge_graph",
                        "relevance_rationale": (
                            f"Retrieved from Lex KG with normalized query term {term!r}."
                        ),
                        "legal_query_term": term,
                        "doc_name": doc_name,
                        "doc_reestr_code": _text(getattr(row, "doc_reestr_code", "")),
                        "provision_citation": _text(
                            getattr(row, "provision_citation", "")
                        ),
                        "source_quote_uk": _text(getattr(row, "source_quote_uk", "")),
                        "fact_text": _text(getattr(row, "fact_text", "")),
                        "confidence": getattr(row, "confidence", 0.0),
                    }
                )
    return _dedupe_norms(candidates)


def _lex_kg_output_dir(path_raw: str) -> Path:
    path = Path(path_raw)
    if path.name == "lex_knowledge_graph.duckdb":
        return path.parent
    return path


def _candidate_norms_from_pack(pack: Mapping[str, Any]) -> list[dict[str, Any]]:
    pack_metadata = _mapping(pack.get("metadata")) or {}
    pack_defaults = {
        **pack_metadata,
        "jurisdiction": pack.get("jurisdiction") or pack_metadata.get("jurisdiction"),
        "effective_date": pack.get("effective_date") or pack_metadata.get("effective_date"),
        "policy_domain": pack.get("policy_domain") or pack_metadata.get("policy_domain"),
        "source_authority": pack.get("source_authority") or pack_metadata.get("source_authority"),
        "authority": pack.get("authority") or pack_metadata.get("authority"),
        "authority_level": pack.get("authority_level") or pack_metadata.get("authority_level"),
    }
    candidates: list[dict[str, Any]] = []
    for raw_rule in _list(pack.get("norms") or pack.get("rules")):
        rule = _mapping(raw_rule)
        if rule is not None:
            candidates.append(_norm_from_pack_rule(rule, pack_defaults=pack_defaults))
    return candidates


def _dedupe_norms(norms: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    result: list[dict[str, Any]] = []
    for norm in norms:
        norm_id = _norm_id(norm)
        fingerprint = norm_id or repr(sorted(norm.items()))
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        result.append(norm)
    return result


def _target_context_from_runtime_payload(
    context: Mapping[str, Any],
    *,
    domain_hint: str | None,
    as_of: str | None,
) -> dict[str, Any]:
    nested_target = _mapping(context.get("target_context")) or {}
    cross_graph = _mapping(context.get("cross_graph_evidence_config")) or {}
    jurisdiction = (
        _text(context.get("jurisdiction") or context.get("jurisdiction_norm")).upper()
        or _first_country_code(nested_target)
        or _first_country_code(cross_graph)
    )
    policy_domain = (
        _domain_from_payload(context)
        or _domain_from_payload(nested_target)
        or _domain_from_payload(cross_graph)
    )
    as_of_value = (
        _text(as_of)
        or _text(context.get("as_of") or context.get("as_of_iso"))
        or _text(nested_target.get("as_of") or nested_target.get("as_of_iso"))
    )
    if not as_of_value:
        raw_year = nested_target.get("publication_year") or cross_graph.get("target_year")
        try:
            year = int(raw_year)
        except (TypeError, ValueError):
            year = 0
        if year > 0:
            as_of_value = f"{year}-12-31"

    return {
        "jurisdiction": jurisdiction,
        "policy_domain": policy_domain,
        "as_of": as_of_value,
        "domain_hint": _text(domain_hint),
    }


def _recommendation_claims_from_runtime_payload(
    context: Mapping[str, Any],
    *,
    selected_variant: Mapping[str, Any] | None,
) -> list[dict[str, Any]]:
    claims: list[dict[str, Any]] = []
    payloads: list[Any] = [context]
    if selected_variant is not None:
        payloads.append(selected_variant)
        bundle = selected_variant.get("_bundle")
        if bundle is not None:
            payloads.append(bundle)
    for payload in payloads:
        for mapping in _walk_mappings(payload):
            for key, value in mapping.items():
                if key not in _RECOMMENDATION_KEYS:
                    continue
                for item in _list(value):
                    claim = _coerce_recommendation_claim(item)
                    if claim is not None:
                        claims.append(claim)
    if claims:
        return _dedupe_claims(claims)
    if selected_variant is None:
        return []
    return _recommendation_claims_from_trinity_payload(selected_variant.get("_bundle"))


def _coerce_recommendation_claim(item: object) -> dict[str, Any] | None:
    if isinstance(item, str):
        text = item.strip()
        return {"text": text, "major": True, "norm_refs": []} if text else None
    claim = _mapping(item)
    if claim is None:
        return None
    if not (
        claim.get("claim_id")
        or claim.get("id")
        or claim.get("text")
        or claim.get("recommended_action")
        or claim.get("description")
        or claim.get("norm_refs")
        or claim.get("normative_refs")
    ):
        return None
    if "text" not in claim:
        claim["text"] = _text(claim.get("recommended_action") or claim.get("description"))
    claim.setdefault("major", True)
    return claim


def _recommendation_claims_from_trinity_payload(bundle: object) -> list[dict[str, Any]]:
    payload = _mapping(bundle)
    if payload is None:
        return []
    policy_spec = _mapping(payload.get("policy_spec")) or {}
    claims: list[dict[str, Any]] = []
    for index, raw_intervention in enumerate(_list(policy_spec.get("interventions"))):
        intervention = _mapping(raw_intervention)
        if intervention is None:
            continue
        intervention_id = _text(intervention.get("intervention_id") or f"intervention_{index + 1}")
        claims.append(
            {
                "claim_id": f"intervention:{intervention_id}",
                "claim_type": "recommendation",
                "major": True,
                "text": _text(intervention.get("description") or intervention_id),
                "norm_refs": _claim_norm_refs(intervention),
            }
        )
    return claims


def _dedupe_claims(claims: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    result: list[dict[str, Any]] = []
    for index, claim in enumerate(claims):
        claim_id = _text(claim.get("claim_id") or claim.get("id"))
        fingerprint = claim_id or _text(claim.get("text")) or f"claim_{index}"
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        if not claim_id:
            claim = {**claim, "claim_id": f"claim_{len(result) + 1}"}
        result.append(claim)
    return result


def _issue(
    *,
    code: str,
    message: str,
    norm_id: str | None = None,
    claim_id: str | None = None,
    severity: str = "fail",
    next_action: str,
) -> dict[str, Any]:
    return {
        "code": code,
        "severity": severity,
        "layer": "lex",
        "phase": "normative_applicability",
        "norm_id": norm_id,
        "claim_id": claim_id,
        "message": message,
        "next_action": next_action,
    }


def _reject(
    norm: dict[str, Any],
    *,
    reason_code: str,
    message: str,
    next_action: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    norm_id = _norm_id(norm)
    rejected = {
        **norm,
        "norm_id": norm_id,
        "applicability_status": "rejected",
        "reason_code": reason_code,
        "message": message,
    }
    return rejected, _issue(
        code=reason_code,
        norm_id=norm_id,
        message=message,
        next_action=next_action,
    )


def _classify_norm(
    norm: dict[str, Any],
    *,
    target_jurisdiction: str,
    target_domain: str,
    as_of: date | None,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None, dict[str, Any] | None]:
    norm_id = _norm_id(norm)
    if not norm_id:
        rejected, issue = _reject(
            norm,
            reason_code="missing_norm_id",
            message="Normative fact is missing a stable norm_id or artifact_id.",
            next_action="Persist a stable norm_id/artifact_id before using the norm.",
        )
        return None, rejected, issue

    jurisdiction = _norm_jurisdiction(norm)
    if not jurisdiction:
        rejected, issue = _reject(
            norm,
            reason_code="missing_jurisdiction",
            message=f"Norm {norm_id} is missing jurisdiction metadata.",
            next_action="Attach jurisdiction metadata during Lex retrieval.",
        )
        return None, rejected, issue
    if target_jurisdiction and jurisdiction.casefold() != target_jurisdiction.casefold():
        rejected, issue = _reject(
            norm,
            reason_code="wrong_jurisdiction",
            message=(
                f"Norm {norm_id} jurisdiction {jurisdiction} does not match "
                f"target jurisdiction {target_jurisdiction}."
            ),
            next_action="Retrieve norms for the target jurisdiction or add transport rationale.",
        )
        return None, rejected, issue

    norm_domain = _norm_domain(norm)
    if target_domain and norm_domain and norm_domain.casefold() != target_domain.casefold():
        rejected, issue = _reject(
            norm,
            reason_code="wrong_policy_domain",
            message=(
                f"Norm {norm_id} domain {norm_domain} does not match "
                f"target domain {target_domain}."
            ),
            next_action="Use domain-relevant norms or document why cross-domain authority applies.",
        )
        return None, rejected, issue

    if as_of is not None:
        effective_from = parse_iso_date(_text(norm.get("effective_from")) or None)
        effective_to = parse_iso_date(_text(norm.get("effective_to")) or None)
        if effective_from is None:
            rejected, issue = _reject(
                norm,
                reason_code="missing_effective_from",
                message=f"Norm {norm_id} is missing effective_from metadata.",
                next_action="Resolve the active legal version and effective date range.",
            )
            return None, rejected, issue
        if effective_from > as_of:
            rejected, issue = _reject(
                norm,
                reason_code="not_yet_effective",
                message=f"Norm {norm_id} is not effective on {as_of.isoformat()}.",
                next_action="Use the active version for the canary as_of date.",
            )
            return None, rejected, issue
        if effective_to is not None and effective_to < as_of:
            rejected, issue = _reject(
                norm,
                reason_code="expired_norm",
                message=f"Norm {norm_id} expired before {as_of.isoformat()}.",
                next_action="Select the active successor norm or flag the legal gap explicitly.",
            )
            return None, rejected, issue

    superseded_by = _text(norm.get("superseded_by") or norm.get("successor_norm_id"))
    if superseded_by:
        rejected, issue = _reject(
            norm,
            reason_code="superseded_norm",
            message=f"Norm {norm_id} is superseded by {superseded_by}.",
            next_action="Ground recommendations in the active successor norm.",
        )
        return None, rejected, issue

    authority, level = _norm_authority(norm)
    if not authority or not level:
        rejected, issue = _reject(
            norm,
            reason_code="missing_authority_metadata",
            message=f"Norm {norm_id} is missing source authority or authority level.",
            next_action="Persist source authority and authority_level during Lex retrieval.",
        )
        return None, rejected, issue

    applied = {
        **norm,
        "norm_id": norm_id,
        "jurisdiction": jurisdiction,
        "policy_domain": norm_domain,
        "source_authority": authority,
        "authority_level": level,
        "applicability_status": "applied",
    }
    return applied, None, None


def _claim_norm_refs(claim: dict[str, Any]) -> list[str]:
    refs = claim.get("norm_refs") or claim.get("normative_refs") or claim.get("norm_ids") or []
    if not isinstance(refs, list):
        return []
    return [_text(ref) for ref in refs if _text(ref)]


def _claim_value(claim: Mapping[str, Any], *keys: str) -> str:
    for key in keys:
        value = _first_token(claim.get(key))
        if value:
            return value
    return ""


def _norm_values(norm: Mapping[str, Any], *keys: str) -> list[str]:
    values: list[str] = []
    for key in keys:
        value = norm.get(key)
        values.extend(_text_list(value))
        if isinstance(value, Mapping):
            values.extend(_text_list(value.get("ref") or value.get("id") or value.get("value")))
    return list(dict.fromkeys(values))


def _norm_haystack(norm: Mapping[str, Any]) -> str:
    values: list[str] = []
    for key in (
        "norm_id",
        "fact_class",
        "policy_instrument",
        "instrument_type",
        "beneficiary_class",
        "fiscal_authority",
        "implementation_agency",
        "competent_authority",
        "source_authority",
        "relevance_rationale",
        "fact_text",
        "text",
        "description",
        "source_quote_uk",
    ):
        values.extend(_text_list(norm.get(key)))
    values.extend(_text_list(norm.get("legal_terms")))
    return " ".join(values).casefold()


def _claim_haystack(claim: Mapping[str, Any]) -> str:
    values: list[str] = []
    for key in (
        "claim_id",
        "text",
        "recommended_action",
        "description",
        "policy_instrument",
        "instrument_type",
        "beneficiary_class",
        "fiscal_authority",
        "implementation_agency",
    ):
        values.extend(_text_list(claim.get(key)))
    return " ".join(values).casefold()


def _facet_match(
    *,
    claim_value: str,
    claim_text: str,
    norm_values: list[str],
    norm_text: str,
) -> bool:
    candidates = [value.casefold() for value in norm_values if value]
    claim_token = claim_value.casefold()
    if claim_token and any(
        claim_token == value or claim_token in value or value in claim_token
        for value in candidates
    ):
        return True
    if claim_token and claim_token in norm_text:
        return True
    return bool(
        candidates
        and any(value and value in claim_text for value in candidates if len(value) >= 4)
    )


def _claim_norm_score(norm: Mapping[str, Any], claim: Mapping[str, Any]) -> dict[str, Any]:
    claim_text = _claim_haystack(claim)
    norm_text = _norm_haystack(norm)
    matched_facets: list[str] = []
    missing_facets: list[str] = []
    score = 0
    if _norm_jurisdiction(dict(norm)):
        matched_facets.append("jurisdiction")
        score += 1
    else:
        missing_facets.append("jurisdiction")
    if _text(norm.get("effective_from")):
        matched_facets.append("temporal_validity")
        score += 1
    else:
        missing_facets.append("temporal_validity")
    authority, _level = _norm_authority(dict(norm))
    if authority or _norm_values(norm, "competence_refs", "competent_authority"):
        matched_facets.append("competence")
        score += 1
    else:
        missing_facets.append("competence")

    facet_specs = (
        (
            "policy_instrument",
            _claim_value(claim, "policy_instrument", "instrument_type"),
            _norm_values(norm, "policy_instrument", "instrument_type", "fact_class"),
            2,
        ),
        (
            "beneficiary_class",
            _claim_value(claim, "beneficiary_class"),
            _norm_values(norm, "beneficiary_class", "beneficiary_classes", "legal_terms"),
            1,
        ),
        (
            "fiscal_authority",
            _claim_value(claim, "fiscal_authority"),
            _norm_values(norm, "fiscal_authority", "fiscal_authority_refs"),
            1,
        ),
        (
            "implementation_agency",
            _claim_value(claim, "implementation_agency"),
            _norm_values(norm, "implementation_agency", "implementation_agency_refs"),
            1,
        ),
    )
    for facet, claim_value, norm_values, weight in facet_specs:
        if _facet_match(
            claim_value=claim_value,
            claim_text=claim_text,
            norm_values=norm_values,
            norm_text=norm_text,
        ):
            matched_facets.append(facet)
            score += weight
        else:
            missing_facets.append(facet)
    if claim_text and norm_text:
        claim_tokens = {token for token in claim_text.replace("_", " ").split() if len(token) > 4}
        if any(token in norm_text for token in claim_tokens):
            matched_facets.append("claim_text_overlap")
            score += 1
    return {
        "norm_id": _norm_id(dict(norm)),
        "score": score,
        "matched_facets": list(dict.fromkeys(matched_facets)),
        "missing_facets": list(dict.fromkeys(missing_facets)),
    }


def _score_reason(norm_score: Mapping[str, Any]) -> str:
    missing = _text_list(norm_score.get("missing_facets"))
    if "policy_instrument" in missing:
        return "policy_instrument_mismatch"
    if "beneficiary_class" in missing:
        return "beneficiary_class_mismatch"
    return "lower_claim_specific_score"


def _recommendation_coverage(
    *,
    recommendation_claims: list[dict[str, Any]],
    candidate_norm_ids: list[str],
    applied_norms: list[dict[str, Any]],
    rejected_norms: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    coverage: list[dict[str, Any]] = []
    anchors: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    applied_norm_ids = {_norm_id(norm) for norm in applied_norms}
    rejected_norm_ids = {_norm_id(norm) for norm in rejected_norms}
    for index, claim in enumerate(recommendation_claims):
        claim_id = _text(claim.get("claim_id") or claim.get("id") or f"claim_{index + 1}")
        major = bool(claim.get("major", True))
        refs = _claim_norm_refs(claim)
        applicable_refs = [ref for ref in refs if ref in applied_norm_ids]
        rejected_refs = [ref for ref in refs if ref in rejected_norm_ids]
        rationale = _text(
            claim.get("no_normative_anchor_rationale")
            or claim.get("normative_gap_rationale")
        )

        if applicable_refs:
            item = {
                "claim_id": claim_id,
                "major": major,
                "status": "pass",
                "reason_code": "applicable_norm_refs_present",
                "norm_refs": applicable_refs,
                "candidate_norm_refs": candidate_norm_ids,
                "selected_norm_refs": applicable_refs,
                "rejected_norm_refs": rejected_refs,
            }
            anchor = {
                **item,
                "anchor_mode": "explicit_norm_refs",
                "scored_norms": [],
                "no_anchor_rationale": None,
            }
        elif rationale:
            item = {
                "claim_id": claim_id,
                "major": major,
                "status": "pass",
                "reason_code": "explicit_no_anchor_rationale",
                "norm_refs": [],
                "candidate_norm_refs": candidate_norm_ids,
                "selected_norm_refs": [],
                "rejected_norm_refs": rejected_refs,
                "rationale": rationale,
            }
            anchor = {
                **item,
                "anchor_mode": "explicit_no_anchor_rationale",
                "scored_norms": [],
                "no_anchor_rationale": rationale,
            }
        elif rejected_refs:
            item = {
                "claim_id": claim_id,
                "major": major,
                "status": "fail",
                "reason_code": "recommendation_references_rejected_norm",
                "norm_refs": rejected_refs,
                "candidate_norm_refs": candidate_norm_ids,
                "selected_norm_refs": [],
                "rejected_norm_refs": rejected_refs,
            }
            issues.append(
                _issue(
                    code="recommendation_references_rejected_norm",
                    claim_id=claim_id,
                    message=(
                        f"Recommendation {claim_id} references rejected normative refs: "
                        f"{', '.join(rejected_refs)}."
                    ),
                    next_action="Replace rejected normative refs with applicable norms.",
                )
            )
            anchor = {
                **item,
                "anchor_mode": "explicit_rejected_norm_refs",
                "scored_norms": [],
                "no_anchor_rationale": None,
            }
        elif applied_norms:
            scored = sorted(
                (_claim_norm_score(norm, claim) for norm in applied_norms),
                key=lambda row: (-int(row["score"]), str(row["norm_id"])),
            )
            selected_scores = [
                row
                for row in scored
                if int(row["score"]) >= 5
                and (
                    "policy_instrument" in row["matched_facets"]
                    or "claim_text_overlap" in row["matched_facets"]
                )
            ][:3]
            selected_refs = [
                _text(row["norm_id"])
                for row in selected_scores
                if _text(row["norm_id"])
            ]
            rejected_refs = [
                _text(row["norm_id"])
                for row in scored
                if _text(row["norm_id"]) and _text(row["norm_id"]) not in selected_refs
            ]
            if selected_refs:
                item = {
                    "claim_id": claim_id,
                    "major": major,
                    "status": "pass",
                    "reason_code": "claim_specific_norm_anchor_selected",
                    "norm_refs": selected_refs,
                    "candidate_norm_refs": candidate_norm_ids,
                    "selected_norm_refs": selected_refs,
                    "rejected_norm_refs": rejected_refs,
                }
                anchor = {
                    **item,
                    "anchor_mode": "claim_specific_scoring",
                    "scored_norms": [
                        {
                            **row,
                            "selection_status": (
                                "selected"
                                if _text(row["norm_id"]) in selected_refs
                                else "rejected"
                            ),
                            "reason_code": (
                                "claim_specific_best_match"
                                if _text(row["norm_id"]) in selected_refs
                                else _score_reason(row)
                            ),
                        }
                        for row in scored
                    ],
                    "no_anchor_rationale": None,
                }
            elif major:
                item = {
                    "claim_id": claim_id,
                    "major": major,
                    "status": "fail",
                    "reason_code": "missing_normative_anchor",
                    "norm_refs": [],
                    "candidate_norm_refs": candidate_norm_ids,
                    "selected_norm_refs": [],
                    "rejected_norm_refs": [
                        _text(row["norm_id"]) for row in scored if _text(row["norm_id"])
                    ],
                }
                anchor = {
                    **item,
                    "reason_code": "missing_claim_specific_normative_anchor",
                    "anchor_mode": "claim_specific_scoring",
                    "scored_norms": [
                        {
                            **row,
                            "selection_status": "rejected",
                            "reason_code": _score_reason(row),
                        }
                        for row in scored
                    ],
                    "no_anchor_rationale": None,
                }
                issues.append(
                    _issue(
                        code="missing_claim_specific_normative_anchor",
                        claim_id=claim_id,
                        message=(
                            f"Major recommendation {claim_id} has global legal "
                            "candidates but no claim-specific legal anchor."
                        ),
                        next_action=(
                            "Select candidate norms whose competence, temporal validity, "
                            "instrument, beneficiary, fiscal authority, and "
                            "implementation agency match the recommendation."
                        ),
                    )
                )
            else:
                item = {
                    "claim_id": claim_id,
                    "major": major,
                    "status": "warn",
                    "reason_code": "non_major_claim_without_normative_anchor",
                    "norm_refs": [],
                    "candidate_norm_refs": candidate_norm_ids,
                    "selected_norm_refs": [],
                    "rejected_norm_refs": [
                        _text(row["norm_id"]) for row in scored if _text(row["norm_id"])
                    ],
                }
                anchor = {
                    **item,
                    "anchor_mode": "claim_specific_scoring",
                    "scored_norms": [
                        {**row, "selection_status": "rejected", "reason_code": _score_reason(row)}
                        for row in scored
                    ],
                    "no_anchor_rationale": None,
                }
        elif major:
            item = {
                "claim_id": claim_id,
                "major": major,
                "status": "fail",
                "reason_code": "missing_normative_anchor",
                "norm_refs": [],
                "candidate_norm_refs": candidate_norm_ids,
                "selected_norm_refs": [],
                "rejected_norm_refs": rejected_refs,
            }
            issues.append(
                _issue(
                    code="missing_recommendation_normative_anchor",
                    claim_id=claim_id,
                    message=f"Major recommendation {claim_id} has no normative anchor.",
                    next_action="Attach an applicable norm ref or explicit no-anchor rationale.",
                )
            )
            anchor = {
                **item,
                "anchor_mode": "no_candidate_norms",
                "scored_norms": [],
                "no_anchor_rationale": None,
            }
        else:
            item = {
                "claim_id": claim_id,
                "major": major,
                "status": "warn",
                "reason_code": "non_major_claim_without_normative_anchor",
                "norm_refs": [],
                "candidate_norm_refs": candidate_norm_ids,
                "selected_norm_refs": [],
                "rejected_norm_refs": rejected_refs,
            }
            anchor = {
                **item,
                "anchor_mode": "no_candidate_norms",
                "scored_norms": [],
                "no_anchor_rationale": None,
            }
        coverage.append(item)
        anchors.append(anchor)
    return coverage, anchors, issues


def _merge_legal_authority_anchors(
    legacy_anchors: list[dict[str, Any]],
    legal_authority_anchors: object,
) -> list[dict[str, Any]]:
    legal_by_claim = {
        _text(anchor.get("claim_id")): dict(anchor)
        for anchor in _mapping_list(legal_authority_anchors)
        if _text(anchor.get("claim_id"))
    }
    merged: list[dict[str, Any]] = []
    seen: set[str] = set()
    for legacy in legacy_anchors:
        claim_id = _text(legacy.get("claim_id"))
        legal = legal_by_claim.get(claim_id)
        if legal is None:
            merged.append(legacy)
            continue
        seen.add(claim_id)
        if bool(legal.get("legal_authority_required")):
            merged.append({**legacy, **legal})
        else:
            merged.append(
                {
                    **legacy,
                    "legal_authority_required": False,
                    "legal_admissibility_grade": legal.get("admissibility_grade"),
                    "legal_authority_record_refs": legal.get("legal_authority_record_refs", []),
                    "legal_authority_blocker_refs": legal.get("legal_authority_blocker_refs", []),
                }
            )
    for claim_id, legal in legal_by_claim.items():
        if claim_id not in seen:
            merged.append(legal)
    return merged


def _status_from_issues(issues: list[dict[str, Any]]) -> str:
    if any(issue.get("severity") == "fail" for issue in issues):
        return "fail"
    if any(issue.get("severity") == "warn" for issue in issues):
        return "warn"
    return "pass"


def build_normative_applicability_report(
    *,
    target_context: dict[str, Any],
    candidate_norms: list[dict[str, Any]],
    recommendation_claims: list[dict[str, Any]] | None = None,
    spine_context: Mapping[str, Any] | None = None,
    scenario_evidence_contract: Mapping[str, Any] | None = None,
    query_terms: list[str] | None = None,
    query_normalization_report: Mapping[str, Any] | None = None,
    concept_refs: list[str] | None = None,
    jurisdiction_filters: list[str] | None = None,
    time_filters: list[str] | None = None,
    legal_corpus_snapshot: Mapping[str, Any] | None = None,
    retrieval_status: str | None = None,
    authority_blockers: list[dict[str, Any]] | None = None,
    conflicts: list[dict[str, Any]] | None = None,
    competence: list[dict[str, Any]] | None = None,
    jurisdiction_fallback_config: Mapping[str, Any] | None = None,
    legal_requirement_specs: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build a strict applicability report from candidate Lex norms."""
    recommendation_claims = recommendation_claims or []
    candidate_norms = [dict(norm) for norm in candidate_norms if isinstance(norm, dict)]
    target_jurisdiction = _text(
        target_context.get("jurisdiction") or target_context.get("jurisdiction_norm")
    )
    target_domain = _text(
        target_context.get("policy_domain")
        or target_context.get("top_domain")
        or target_context.get("domain")
    )
    as_of_raw = _text(target_context.get("as_of") or target_context.get("as_of_iso"))
    as_of = parse_iso_date(as_of_raw) if as_of_raw else None
    resolved_retrieval_status = _retrieval_status(
        explicit=retrieval_status,
        candidate_norms=candidate_norms,
    )
    retrieval_blocker = _retrieval_blocker_for_status(resolved_retrieval_status)
    resolved_query_terms = (
        query_terms
        if query_terms is not None
        else _default_query_terms(
            target_context=target_context,
            recommendation_claims=recommendation_claims,
        )
    )
    corpus_snapshot = _legal_corpus_snapshot(
        legal_corpus_snapshot=legal_corpus_snapshot,
        target_context=target_context,
        candidate_norms=candidate_norms,
        retrieval_status=resolved_retrieval_status,
    )
    resolved_kg_paths = _legal_kg_paths_from_snapshot(corpus_snapshot)
    normalized_query_report = _query_normalization_payload(
        query_normalization_report=query_normalization_report,
        query_terms=resolved_query_terms,
        target_context=target_context,
        scenario_evidence_contract=scenario_evidence_contract,
        kg_paths=resolved_kg_paths,
        candidate_norm_count=len(candidate_norms),
        blocker_code=(
            _text(retrieval_blocker.get("code")) if retrieval_blocker is not None else None
        ),
    )

    applied_norms: list[dict[str, Any]] = []
    rejected_norms: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    for candidate in candidate_norms:
        if not isinstance(candidate, dict):
            continue
        applied, rejected, issue = _classify_norm(
            candidate,
            target_jurisdiction=target_jurisdiction,
            target_domain=target_domain,
            as_of=as_of,
        )
        if applied is not None:
            applied_norms.append(applied)
        if rejected is not None:
            rejected_norms.append(rejected)
        if issue is not None:
            issues.append(issue)

    legal_authority = build_legal_authority_report(
        target_context=target_context,
        candidate_norms=candidate_norms,
        recommendation_claims=recommendation_claims,
        legal_requirement_specs=legal_requirement_specs,
        jurisdiction_fallback_config=jurisdiction_fallback_config,
    )
    legal_selected_norm_refs = set(_text_list(legal_authority.get("selected_norm_refs")))
    if legal_selected_norm_refs:
        candidate_by_id = {
            _norm_id(candidate): candidate for candidate in candidate_norms if _norm_id(candidate)
        }
        existing_applied = {_norm_id(norm) for norm in applied_norms if _norm_id(norm)}
        for norm_ref in sorted(legal_selected_norm_refs - existing_applied):
            selected_candidate = candidate_by_id.get(norm_ref)
            if selected_candidate is None:
                continue
            applied_norms.append(
                {
                    **selected_candidate,
                    "norm_id": norm_ref,
                    "applicability_status": "applied",
                    "legal_selection_reason": "claim_level_legal_authority",
                }
            )
        rejected_norms = [
            norm for norm in rejected_norms if _norm_id(norm) not in legal_selected_norm_refs
        ]
        issues = [
            issue
            for issue in issues
            if not (
                _text(issue.get("norm_id")) in legal_selected_norm_refs
                and _text(issue.get("code")) in {"wrong_jurisdiction"}
            )
        ]

    authority_blocker_rows = _mapping_list(authority_blockers)
    if retrieval_blocker is not None and not any(
        _text(blocker.get("code")) == retrieval_blocker["code"]
        for blocker in authority_blocker_rows
    ):
        authority_blocker_rows.append(retrieval_blocker)
    issues.extend(_issue_from_blocker(blocker) for blocker in authority_blocker_rows)

    candidate_norm_ids = [_norm_id(norm) for norm in candidate_norms if _norm_id(norm)]
    coverage, claim_legal_anchors, coverage_issues = _recommendation_coverage(
        recommendation_claims=recommendation_claims,
        candidate_norm_ids=candidate_norm_ids,
        applied_norms=applied_norms,
        rejected_norms=rejected_norms,
    )
    claim_legal_anchors = _merge_legal_authority_anchors(
        claim_legal_anchors,
        legal_authority.get("claim_legal_anchors"),
    )
    legal_selected_claim_ids = {
        _text(anchor.get("claim_id"))
        for anchor in _mapping_list(legal_authority.get("claim_legal_anchors"))
        if _text_list(anchor.get("selected_norm_refs"))
    }
    coverage_issues = [
        issue
        for issue in coverage_issues
        if not (
            _text(issue.get("claim_id")) in legal_selected_claim_ids
            and _text(issue.get("code"))
            in {
                "missing_claim_specific_normative_anchor",
                "missing_recommendation_normative_anchor",
                "recommendation_references_rejected_norm",
            }
        )
    ]
    issues.extend(coverage_issues)
    issues.extend(_mapping_list(legal_authority.get("issues")))
    if not candidate_norms:
        query_trace_issue = _query_normalization_trace_issue(normalized_query_report)
        if query_trace_issue is not None:
            issues.append(query_trace_issue)
    if not applied_norms:
        issues.append(
            _issue(
                code="no_applicable_norms",
                message="No candidate norms were applicable to the target policy context.",
                next_action=(
                    "Retrieve Lex norms for the target jurisdiction, effective date, "
                    "domain, and authority level."
                ),
            )
        )

    status = _status_from_issues(issues)
    legal_requirements = _legal_requirements_from_inputs(
        scenario_evidence_contract=scenario_evidence_contract,
        query_normalization_report=normalized_query_report,
    )
    selected_norm_refs = [_norm_id(norm) for norm in applied_norms]
    rejected_norm_refs = [_norm_id(norm) for norm in rejected_norms]
    report = {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "retrieval_status": resolved_retrieval_status,
        "legal_corpus_snapshot": corpus_snapshot,
        "query_terms": resolved_query_terms,
        "normalized_query_terms": _text_list(
            normalized_query_report.get("normalized_terms")
        ),
        "query_normalization_report": normalized_query_report,
        "concept_refs": concept_refs
        if concept_refs is not None
        else _default_concept_refs(target_context),
        "jurisdiction_filters": _jurisdiction_filters(
            explicit=jurisdiction_filters,
            target_jurisdiction=target_jurisdiction,
        ),
        "time_filters": _time_filters(explicit=time_filters, as_of=as_of_raw),
        "target_context": {
            "jurisdiction": target_jurisdiction,
            "policy_domain": target_domain,
            "as_of": as_of.isoformat() if as_of is not None else as_of_raw,
        },
        "legal_requirements": legal_requirements,
        "legal_requirement_specs": _mapping_list(
            legal_authority.get("legal_requirement_specs")
        ),
        "candidate_norms": candidate_norms,
        "candidate_norm_refs": candidate_norm_ids,
        "global_candidate_norms": candidate_norms,
        "global_candidate_norm_refs": candidate_norm_ids,
        "selected_norms": applied_norms,
        "selected_norm_refs": selected_norm_refs,
        "applied_norms": applied_norms,
        "global_selected_norms": applied_norms,
        "global_selected_norm_refs": selected_norm_refs,
        "rejected_norms": rejected_norms,
        "rejected_norm_refs": rejected_norm_refs,
        "global_rejected_norms": rejected_norms,
        "global_rejected_norm_refs": rejected_norm_refs,
        "conflicts": _mapping_list(conflicts),
        "competence": _mapping_list(competence) or _competence_rows(applied_norms),
        "legal_authority_report_schema_version": legal_authority.get("schema_version"),
        "capability_reality_status": legal_authority.get("capability_reality_status"),
        "runtime_authority_envelope": dict(
            legal_authority.get("runtime_authority_envelope") or {}
        ),
        "legal_authority_required": bool(legal_authority.get("legal_authority_required")),
        "legal_authority_records": _mapping_list(
            legal_authority.get("legal_authority_records")
        ),
        "claim_window_splits": _mapping_list(legal_authority.get("claim_window_splits")),
        "legal_authority_summary": dict(legal_authority.get("summary") or {}),
        "authority_blockers": authority_blocker_rows,
        "blockers": authority_blocker_rows,
        "recommendation_coverage": coverage,
        "claim_legal_anchors": claim_legal_anchors,
        "issues": issues,
        "issue_codes": [str(issue.get("code")) for issue in issues if issue.get("code")],
        "blocking_issue_count": sum(1 for issue in issues if issue.get("severity") == "fail"),
        "summary": {
            "candidate_norm_count": len(candidate_norms),
            "global_candidate_norm_count": len(candidate_norms),
            "applied_norm_count": len(applied_norms),
            "rejected_norm_count": len(rejected_norms),
            "legal_requirement_count": len(legal_requirements),
            "legal_requirement_spec_count": int(
                dict(legal_authority.get("summary") or {}).get(
                    "legal_requirement_spec_count",
                    0,
                )
            ),
            "claim_legal_anchor_count": len(claim_legal_anchors),
            "claim_legal_anchor_pass_count": sum(
                1 for anchor in claim_legal_anchors if anchor.get("status") == "pass"
            ),
            "claim_legal_anchor_fail_count": sum(
                1 for anchor in claim_legal_anchors if anchor.get("status") == "fail"
            ),
            "major_recommendation_count": sum(
                1 for claim in recommendation_claims or [] if bool(claim.get("major", True))
            ),
        },
    }
    if spine_context is not None:
        from polisyos.core import contracts as core_contracts

        report.update(
            core_contracts.build_producer_spine_binding_fields(
                component="lex",
                spine_context=spine_context,
                candidate_refs=[_norm_id(norm) for norm in candidate_norms],
                blocker_refs=[issue.get("code") for issue in issues],
            )
        )
    return report


def build_runtime_normative_applicability_report(
    *,
    context: Mapping[str, Any],
    domain_hint: str | None,
    selected_variant: Mapping[str, Any] | None = None,
    as_of: str | None = None,
    spine_context: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a normative applicability report from runtime NL context."""
    target_context = _target_context_from_runtime_payload(
        context,
        domain_hint=domain_hint,
        as_of=as_of,
    )
    query_terms = _text_list(
        context.get("query_terms")
        or context.get("legal_query_terms")
        or context.get("legal_queries")
    )
    scenario_evidence_contract = _mapping(context.get("scenario_evidence_contract"))
    runtime_kg_paths = _legal_kg_paths_from_runtime_context(context)
    runtime_query_report = normalize_lex_query_terms(
        original_terms=query_terms
        or _default_query_terms(
            target_context=target_context,
            recommendation_claims=_recommendation_claims_from_runtime_payload(
                context,
                selected_variant=selected_variant,
            ),
        ),
        target_context=target_context,
        scenario_evidence_contract=scenario_evidence_contract,
        kg_paths=runtime_kg_paths,
    ).to_dict()
    candidate_norms = _candidate_norms_from_runtime_payload(context)
    if not candidate_norms:
        candidate_norms = _candidate_norms_from_lex_kg(
            kg_paths=runtime_kg_paths,
            query_terms=_text_list(runtime_query_report.get("normalized_terms")),
            target_context=target_context,
        )
    recommendation_claims = _recommendation_claims_from_runtime_payload(
        context,
        selected_variant=selected_variant,
    )
    return build_normative_applicability_report(
        target_context=target_context,
        candidate_norms=candidate_norms,
        recommendation_claims=recommendation_claims,
        spine_context=spine_context,
        scenario_evidence_contract=scenario_evidence_contract,
        query_terms=query_terms or None,
        query_normalization_report=runtime_query_report,
        concept_refs=_text_list(
            context.get("concept_refs") or context.get("canonical_concept_refs")
        ),
        legal_corpus_snapshot=_mapping(
            context.get("legal_corpus_snapshot") or context.get("corpus_snapshot")
        ),
        retrieval_status=_text(context.get("retrieval_status")) or None,
        authority_blockers=_mapping_list(
            context.get("authority_blockers") or context.get("blockers")
        ),
        conflicts=_mapping_list(context.get("conflicts") or context.get("legal_conflicts")),
        jurisdiction_fallback_config=_mapping(
            context.get("jurisdiction_fallback_config")
            or context.get("legal_jurisdiction_fallback_config")
        ),
    )


def _has_legal_shape(report: Mapping[str, Any]) -> bool:
    return any(
        bool(report.get(key))
        for key in (
            "applied_norms",
            "selected_norms",
            "candidate_norms",
            "rejected_norms",
            "recommendation_coverage",
        )
    )


def _has_retrieval_trace(report: Mapping[str, Any]) -> bool:
    has_snapshot = bool(
        _mapping(report.get("legal_corpus_snapshot"))
        or _text_list(report.get("legal_snapshot_refs"))
        or _text_list(report.get("snapshot_refs"))
    )
    has_query = bool(
        _text_list(report.get("query_terms"))
        or _text_list(report.get("legal_query_terms"))
        or _text_list(report.get("legal_query_refs"))
        or _text_list(report.get("query_refs"))
    )
    return has_snapshot and has_query


def _add_issue(report: dict[str, Any], issue: dict[str, Any]) -> dict[str, Any]:
    issues = [*list(report.get("issues") or []), issue]
    status = _status_from_issues(issues)
    summary = dict(report.get("summary") or {})
    summary["retrieval_trace_present"] = False
    report = {
        **report,
        "status": status,
        "issues": issues,
        "issue_codes": [str(item.get("code")) for item in issues if item.get("code")],
        "blocking_issue_count": sum(1 for item in issues if item.get("severity") == "fail"),
        "summary": summary,
    }
    return report


def normalize_normative_applicability_report(report: dict[str, Any]) -> dict[str, Any]:
    """Recompute report status from its declared target context and applied norms."""
    if not isinstance(report, dict):
        return build_normative_applicability_report(
            target_context={},
            candidate_norms=[],
            recommendation_claims=[],
        )
    target_context = report.get("target_context")
    if not isinstance(target_context, dict):
        target_context = {}
    applied_norms = (
        report.get("applied_norms")
        or report.get("selected_norms")
        or report.get("applied_norm_refs")
        or []
    )
    rejected_norms = report.get("rejected_norms") or []
    declared_candidates = report.get("candidate_norms") or []
    applied_norms = applied_norms if isinstance(applied_norms, list) else []
    rejected_norms = rejected_norms if isinstance(rejected_norms, list) else []
    declared_candidates = declared_candidates if isinstance(declared_candidates, list) else []
    candidate_norms = [
        norm
        for norm in [*declared_candidates, *applied_norms, *rejected_norms]
        if isinstance(norm, dict)
    ]
    candidate_norms = _dedupe_norms(candidate_norms)
    coverage = report.get("recommendation_coverage")
    recommendation_claims = [claim for claim in coverage if isinstance(claim, dict)] if isinstance(
        coverage,
        list,
    ) else []
    missing_retrieval_trace = _has_legal_shape(report) and not _has_retrieval_trace(report)
    missing_zero_candidate_query_normalization = (
        not candidate_norms
        and _text(report.get("retrieval_status")) in {"no_relevant_norm_found", "missing_store"}
        and _mapping(report.get("query_normalization_report")) is None
    )
    normalized = build_normative_applicability_report(
        target_context=target_context,
        candidate_norms=candidate_norms,
        recommendation_claims=recommendation_claims,
        scenario_evidence_contract=_mapping(report.get("scenario_evidence_contract")),
        query_terms=_text_list(
            report.get("query_terms")
            or report.get("legal_query_terms")
            or report.get("legal_query_refs")
        ),
        query_normalization_report=_mapping(report.get("query_normalization_report")),
        concept_refs=_text_list(report.get("concept_refs")),
        jurisdiction_filters=_text_list(report.get("jurisdiction_filters")),
        time_filters=_text_list(report.get("time_filters") or report.get("effective_date_filters")),
        legal_corpus_snapshot=_mapping(report.get("legal_corpus_snapshot")),
        retrieval_status=_text(report.get("retrieval_status")) or None,
        authority_blockers=_mapping_list(
            report.get("authority_blockers") or report.get("blockers")
        ),
        conflicts=_mapping_list(report.get("conflicts")),
        competence=_mapping_list(report.get("competence")),
    )
    if missing_retrieval_trace:
        normalized = _add_issue(
            normalized,
            _issue(
                code="legal_retrieval_trace_missing",
                message=(
                    "Legal-shaped normative payload is missing Lex retrieval trace "
                    "metadata."
                ),
                next_action=(
                    "Emit legal corpus snapshot, query terms, filters, candidates, "
                    "selection, rejections, competence, conflicts, and blockers from Lex "
                    "retrieval."
                ),
            ),
        )
    if missing_zero_candidate_query_normalization:
        normalized = _add_issue(
            normalized,
            _issue(
                code="lex_query_normalization_report_missing",
                message=(
                    "Zero-candidate Lex applicability report is missing the bilingual "
                    "query normalization report."
                ),
                next_action=(
                    "Attach original terms, normalized Ukrainian/English terms, KG path, "
                    "language coverage, and the no-norm blocker code."
                ),
            ),
        )
    return {**report, **normalized}


__all__ = [
    "SCHEMA_VERSION",
    "build_normative_applicability_report",
    "build_runtime_normative_applicability_report",
    "normalize_normative_applicability_report",
]
