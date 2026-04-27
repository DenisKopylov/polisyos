"""Projection helpers that turn existing Scientist outputs into ClaimLedgers."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from typing import Any

from pydantic import BaseModel, ValidationError

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.scientist.claims.models import (
    ClaimLedger,
    ClaimPublishability,
    ClaimRecord,
    ClaimSupportStatus,
    ClaimType,
)
from polisyos.scientist.claims.readiness import normalize_claim_readiness
from polisyos.scientist.search.readiness import DecisionReadiness

DECISION_BEARING_PACKET_FIELDS: tuple[str, ...] = (
    "policy_answer",
    "verified_findings",
    "hypotheses",
    "intervention_legal_basis_map",
    "governance",
    "legal_verification",
    "source_coverage",
    "policy_output_bundle",
    "causal",
    "distributional",
    "welfare",
    "metric_significance_summary",
    "simulation_results",
)


def deterministic_claim_id(
    *,
    run_id: str,
    claim_type: ClaimType,
    text: str,
    source_label: str,
) -> str:
    """Build a stable claim id from run, type, text, and projection source."""

    digest = hashlib.sha256(
        json.dumps(
            {
                "run_id": run_id,
                "claim_type": claim_type.value,
                "text": text,
                "source_label": source_label,
            },
            ensure_ascii=False,
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()[:16]
    return f"claim_{digest}"


def has_decision_bearing_content(payload: Mapping[str, Any]) -> bool:
    """Return whether a payload has fields that require claim projection."""

    return any(_has_meaningful_value(payload.get(field)) for field in DECISION_BEARING_PACKET_FIELDS)


def project_decision_packet_claims(
    packet_payload: Mapping[str, Any],
    *,
    run_id: str,
    source_artifact_refs: Iterable[ArtifactRef] = (),
    decision_readiness_ref: ArtifactRef | None = None,
    created_by_node_id: str = "scientist.node_build_decision_packet",
) -> ClaimLedger:
    """Project a decision packet payload into a ClaimLedger sidecar."""

    source_refs = _dedupe_refs(source_artifact_refs)
    readiness_level = _readiness_from_packet(packet_payload)
    claims: list[ClaimRecord] = []

    policy_summary = _string_or_none(packet_payload.get("policy_summary"))
    if policy_summary and policy_summary not in {"N/A", "Policy data unavailable"}:
        claims.append(
            _claim(
                run_id=run_id,
                claim_type=ClaimType.IMPLEMENTATION,
                text=f"Decision packet scope: {policy_summary}.",
                source_label="decision_packet.policy_summary",
                readiness_level=readiness_level,
                evidence_refs=source_refs,
                source_attribution=["decision_packet.policy_summary"],
            )
        )

    policy_answer = packet_payload.get("policy_answer")
    if isinstance(policy_answer, Mapping):
        summary = _string_or_none(policy_answer.get("executive_summary"))
        if summary:
            claims.append(
                _claim(
                    run_id=run_id,
                    claim_type=ClaimType.NORMATIVE,
                    text=summary,
                    source_label="decision_packet.policy_answer.executive_summary",
                    readiness_level=readiness_level,
                    evidence_refs=source_refs,
                    source_attribution=["verified_policy_report.executive_summary"],
                )
            )

    for index, finding in enumerate(_string_list(packet_payload.get("verified_findings"))):
        claims.append(
            _claim(
                run_id=run_id,
                claim_type=ClaimType.FACTUAL,
                text=finding,
                source_label=f"decision_packet.verified_findings[{index}]",
                readiness_level=readiness_level,
                evidence_refs=source_refs,
                source_attribution=["verified_policy_report.verified_findings"],
            )
        )

    for index, hypothesis in enumerate(_string_list(packet_payload.get("hypotheses"))):
        claims.append(
            _claim(
                run_id=run_id,
                claim_type=ClaimType.FORECAST,
                text=hypothesis,
                source_label=f"decision_packet.hypotheses[{index}]",
                readiness_level=readiness_level,
                evidence_refs=source_refs,
                source_attribution=["verified_policy_report.hypotheses"],
            )
        )

    legal_basis = packet_payload.get("intervention_legal_basis_map")
    if isinstance(legal_basis, Mapping):
        for subject, basis in sorted(legal_basis.items()):
            claims.append(
                _claim(
                    run_id=run_id,
                    claim_type=ClaimType.LEGAL,
                    text=f"Intervention {subject} has legal basis: {basis}.",
                    source_label=f"decision_packet.intervention_legal_basis_map.{subject}",
                    readiness_level=readiness_level,
                    evidence_refs=source_refs,
                    source_attribution=["verified_policy_report.intervention_legal_basis_map"],
                    normalized_subject=str(subject),
                )
            )

    governance = packet_payload.get("governance")
    if isinstance(governance, Mapping) and governance.get("verdict") is not None:
        claims.append(
            _claim(
                run_id=run_id,
                claim_type=ClaimType.IMPLEMENTATION,
                text=f"Governance verdict is {governance.get('verdict')}.",
                source_label="decision_packet.governance.verdict",
                readiness_level=readiness_level,
                evidence_refs=source_refs,
                source_attribution=["governance_report.verdict"],
            )
        )

    causal = packet_payload.get("causal")
    if isinstance(causal, Mapping) and causal.get("status") is not None:
        estimand = _string_or_none(causal.get("estimand")) or "causal estimand"
        estimate = causal.get("point_estimate")
        claims.append(
            _claim(
                run_id=run_id,
                claim_type=ClaimType.CAUSAL,
                text=f"{estimand} was estimated with status {causal.get('status')} and point estimate {estimate}.",
                source_label="decision_packet.causal",
                readiness_level=readiness_level,
                evidence_refs=source_refs,
                counterevidence_refs=[] if causal.get("refutation_robust") is not False else source_refs,
                source_attribution=["causal_effect_report"],
                uncertainty_profile_ref=_first_ref_by_kind(source_refs, "uncertainty"),
            )
        )

    for section_name, claim_type in (
        ("distributional", ClaimType.DISTRIBUTIONAL),
        ("welfare", ClaimType.WELFARE),
    ):
        section = packet_payload.get(section_name)
        if isinstance(section, Mapping) and _has_meaningful_value(section):
            claims.append(
                _claim(
                    run_id=run_id,
                    claim_type=claim_type,
                    text=f"{section_name} section is available for this decision packet.",
                    source_label=f"decision_packet.{section_name}",
                    readiness_level=readiness_level,
                    evidence_refs=source_refs,
                    source_attribution=[f"decision_packet.{section_name}"],
                )
            )

    metric_summary = packet_payload.get("metric_significance_summary")
    if isinstance(metric_summary, Mapping) and _has_meaningful_value(metric_summary):
        claims.append(
            _claim(
                run_id=run_id,
                claim_type=ClaimType.FACTUAL,
                text="Metric validation significance summary is available.",
                source_label="decision_packet.metric_significance_summary",
                readiness_level=readiness_level,
                evidence_refs=source_refs,
                source_attribution=["metric_validation_report"],
            )
        )

    return ClaimLedger(
        run_id=run_id,
        claims=_dedupe_claims(claims),
        decision_readiness_ref=decision_readiness_ref,
        source_artifact_refs=source_refs,
        created_by_node_id=created_by_node_id,
        metadata={
            "projection": "decision_packet",
            "decision_bearing_content": has_decision_bearing_content(packet_payload),
        },
    )


def project_policy_artifact_bundle_claims(
    bundle_payload: Mapping[str, Any] | BaseModel,
    *,
    run_id: str,
    source_artifact_refs: Iterable[ArtifactRef] = (),
    readiness_level: DecisionReadiness = DecisionReadiness.RESEARCH_ARTIFACT,
    created_by_node_id: str = "scientist.policy_design.PolicyArtifactBuilder",
) -> ClaimLedger:
    """Project a policy artifact bundle into a compact claim ledger."""

    payload = _mapping_from_model(bundle_payload)
    source_refs = _dedupe_refs([*source_artifact_refs, *_collect_artifact_refs(payload)])
    claims: list[ClaimRecord] = []
    candidate_id = _string_or_none(payload.get("candidate_id")) or "unknown"

    claims.append(
        _claim(
            run_id=run_id,
            claim_type=ClaimType.IMPLEMENTATION,
            text=f"Policy artifact bundle selected candidate {candidate_id}.",
            source_label="policy_artifact_bundle.candidate_id",
            readiness_level=readiness_level,
            evidence_refs=source_refs,
            source_attribution=["policy_artifact_bundle.candidate_id"],
            normalized_subject=candidate_id,
        )
    )

    phase3 = payload.get("phase3_gate")
    if isinstance(phase3, Mapping):
        claims.append(
            _claim(
                run_id=run_id,
                claim_type=ClaimType.SOURCE_QUALITY,
                text=f"Phase 3 gate pass status is {bool(phase3.get('gate_passed'))}.",
                source_label="policy_artifact_bundle.phase3_gate",
                readiness_level=readiness_level,
                evidence_refs=source_refs,
                counterevidence_refs=source_refs if not bool(phase3.get("gate_passed")) else [],
                source_attribution=["policy_artifact_bundle.phase3_gate"],
                normalized_subject=candidate_id,
            )
        )

    readiness_ref = payload.get("decision_readiness_contract_ref")
    if readiness_ref is not None:
        claims.append(
            _claim(
                run_id=run_id,
                claim_type=ClaimType.SOURCE_QUALITY,
                text="Policy artifact bundle is linked to a DecisionReadinessContract.",
                source_label="policy_artifact_bundle.decision_readiness_contract_ref",
                readiness_level=readiness_level,
                evidence_refs=source_refs,
                source_attribution=["decision_readiness_contract"],
                normalized_subject=candidate_id,
            )
        )

    return ClaimLedger(
        run_id=run_id,
        claims=_dedupe_claims(claims),
        decision_readiness_ref=_first_ref_by_kind(source_refs, "decision_readiness_contract"),
        source_artifact_refs=source_refs,
        created_by_node_id=created_by_node_id,
        metadata={"projection": "policy_artifact_bundle", "candidate_id": candidate_id},
    )


def project_governance_report_claims(
    report_payload: Mapping[str, Any] | BaseModel,
    *,
    run_id: str,
    source_artifact_refs: Iterable[ArtifactRef] = (),
    readiness_level: DecisionReadiness = DecisionReadiness.RESEARCH_ARTIFACT,
    created_by_node_id: str = "scientist.node_run_governance",
) -> ClaimLedger:
    """Project a governance report into claim records."""

    payload = _mapping_from_model(report_payload)
    source_refs = _dedupe_refs([*source_artifact_refs, *_collect_artifact_refs(payload)])
    claims: list[ClaimRecord] = []
    verdict = _string_or_none(payload.get("verdict"))
    if verdict is not None:
        claims.append(
            _claim(
                run_id=run_id,
                claim_type=ClaimType.IMPLEMENTATION,
                text=f"Governance verdict is {verdict}.",
                source_label="governance_report.verdict",
                readiness_level=readiness_level,
                evidence_refs=source_refs,
                counterevidence_refs=source_refs if verdict in {"reject", "human_gate"} else [],
                source_attribution=["governance_report.verdict"],
            )
        )
    for index, issue in enumerate(payload.get("issues", []) if isinstance(payload.get("issues"), list) else []):
        if isinstance(issue, Mapping):
            text = _string_or_none(issue.get("message")) or _string_or_none(issue.get("code"))
            if text:
                claims.append(
                    _claim(
                        run_id=run_id,
                        claim_type=ClaimType.LEGAL
                        if "legal" in text.lower()
                        else ClaimType.IMPLEMENTATION,
                        text=text,
                        source_label=f"governance_report.issues[{index}]",
                        readiness_level=readiness_level,
                        evidence_refs=source_refs,
                        counterevidence_refs=source_refs,
                        source_attribution=["governance_report.issues"],
                    )
                )

    return ClaimLedger(
        run_id=run_id,
        claims=_dedupe_claims(claims),
        source_artifact_refs=source_refs,
        created_by_node_id=created_by_node_id,
        metadata={"projection": "governance_report"},
    )


def project_causal_effect_claims(
    report_payload: Mapping[str, Any] | BaseModel,
    *,
    run_id: str,
    source_artifact_refs: Iterable[ArtifactRef] = (),
    readiness_level: DecisionReadiness = DecisionReadiness.RESEARCH_ARTIFACT,
    created_by_node_id: str = "scientist.node_run_causal_evaluation",
) -> ClaimLedger:
    """Project a causal effect report into claim records."""

    payload = _mapping_from_model(report_payload)
    source_refs = _dedupe_refs([*source_artifact_refs, *_collect_artifact_refs(payload)])
    status = _string_or_none(payload.get("status")) or "unknown"
    estimand = _string_or_none(payload.get("estimand")) or "causal estimand"
    point = payload.get("point_estimate")
    counter_refs = source_refs if status != "success" or _has_failed_refutations(payload) else []
    claim = _claim(
        run_id=run_id,
        claim_type=ClaimType.CAUSAL,
        text=f"{estimand} has causal estimate {point} with status {status}.",
        source_label="causal_effect_report",
        readiness_level=readiness_level,
        evidence_refs=source_refs,
        counterevidence_refs=counter_refs,
        source_attribution=["causal_effect_report"],
    )
    return ClaimLedger(
        run_id=run_id,
        claims=[claim],
        source_artifact_refs=source_refs,
        created_by_node_id=created_by_node_id,
        metadata={"projection": "causal_effect_report", "status": status},
    )


def project_causal_validity_bundle_claims(
    bundle_payload: Mapping[str, Any],
    *,
    run_id: str,
    source_artifact_refs: Iterable[ArtifactRef] = (),
    readiness_level: DecisionReadiness = DecisionReadiness.RESEARCH_ARTIFACT,
    created_by_node_id: str = "polisyos.scientist.causal.validity",
) -> ClaimLedger:
    """Project a causal validity bundle into claim records."""

    source_refs = _dedupe_refs(source_artifact_refs)
    checks = bundle_payload.get("checks")
    failed_checks = []
    if isinstance(checks, Mapping):
        failed_checks = [
            str(name)
            for name, payload in checks.items()
            if isinstance(payload, Mapping)
            and str(payload.get("status", "")).lower() in {"failed", "blocked"}
        ]
    claim = _claim(
        run_id=run_id,
        claim_type=ClaimType.CAUSAL,
        text=(
            "Causal validity diagnostics completed"
            if not failed_checks
            else f"Causal validity diagnostics have failed checks: {', '.join(failed_checks)}."
        ),
        source_label="causal_validity_bundle.checks",
        readiness_level=readiness_level,
        evidence_refs=source_refs,
        counterevidence_refs=source_refs if failed_checks else [],
        source_attribution=["causal_validity_bundle.checks"],
    )
    return ClaimLedger(
        run_id=run_id,
        claims=[claim],
        source_artifact_refs=source_refs,
        created_by_node_id=created_by_node_id,
        metadata={"projection": "causal_validity_bundle", "failed_checks": failed_checks},
    )


def project_frontier_runtime_claims(
    report_payload: Mapping[str, Any] | BaseModel,
    *,
    run_id: str,
    source_artifact_refs: Iterable[ArtifactRef] = (),
    readiness_level: DecisionReadiness = DecisionReadiness.RESEARCH_ARTIFACT,
    created_by_node_id: str = "polisyos.scientist.frontier_runtime",
) -> ClaimLedger:
    """Project frontier runtime capability status into claim records."""

    payload = _mapping_from_model(report_payload)
    source_refs = _dedupe_refs(source_artifact_refs)
    claims: list[ClaimRecord] = []
    capabilities = payload.get("capabilities")
    if isinstance(capabilities, list):
        for index, capability in enumerate(capabilities):
            if not isinstance(capability, Mapping):
                continue
            capability_id = _string_or_none(capability.get("capability_id")) or f"capability_{index}"
            status = _string_or_none(capability.get("status")) or "unknown"
            claims.append(
                _claim(
                    run_id=run_id,
                    claim_type=ClaimType.SOURCE_QUALITY,
                    text=f"Frontier capability {capability_id} status is {status}.",
                    source_label=f"frontier_runtime.capabilities[{index}]",
                    readiness_level=readiness_level,
                    evidence_refs=source_refs,
                    source_attribution=["frontier_runtime.capabilities"],
                    normalized_subject=capability_id,
                )
            )
    return ClaimLedger(
        run_id=run_id,
        claims=_dedupe_claims(claims),
        source_artifact_refs=source_refs,
        created_by_node_id=created_by_node_id,
        metadata={"projection": "frontier_runtime"},
    )


def _claim(
    *,
    run_id: str,
    claim_type: ClaimType,
    text: str,
    source_label: str,
    readiness_level: DecisionReadiness,
    evidence_refs: Iterable[ArtifactRef],
    counterevidence_refs: Iterable[ArtifactRef] = (),
    source_attribution: Iterable[str] = (),
    normalized_subject: str | None = None,
    uncertainty_profile_ref: ArtifactRef | None = None,
) -> ClaimRecord:
    evidence = _dedupe_refs(evidence_refs)
    counterevidence = _dedupe_refs(counterevidence_refs)
    support_status = _support_status(evidence, counterevidence)
    record = ClaimRecord(
        claim_id=deterministic_claim_id(
            run_id=run_id,
            claim_type=claim_type,
            text=_compact_text(text),
            source_label=source_label,
        ),
        run_id=run_id,
        claim_type=claim_type,
        text=_compact_text(text),
        normalized_subject=normalized_subject,
        support_status=support_status,
        publishability=ClaimPublishability.DRAFT,
        readiness_level=readiness_level,
        evidence_refs=evidence,
        counterevidence_refs=counterevidence,
        uncertainty_profile_ref=uncertainty_profile_ref,
        source_attribution=list(source_attribution),
        metadata={"source_label": source_label},
    )
    return normalize_claim_readiness(record)


def _support_status(
    evidence_refs: list[ArtifactRef],
    counterevidence_refs: list[ArtifactRef],
) -> ClaimSupportStatus:
    if counterevidence_refs:
        return ClaimSupportStatus.CONTESTED
    if evidence_refs:
        return ClaimSupportStatus.SUPPORTED
    return ClaimSupportStatus.UNSUPPORTED


def _readiness_from_packet(payload: Mapping[str, Any]) -> DecisionReadiness:
    causal = payload.get("causal")
    if isinstance(causal, Mapping):
        raw = causal.get("decision_readiness_level")
        if isinstance(raw, str):
            try:
                return DecisionReadiness(raw)
            except ValueError:
                pass
    validation = payload.get("validation")
    if isinstance(validation, Mapping) and validation.get("readiness") == "ready":
        return DecisionReadiness.ANALYST_ADVISORY
    return DecisionReadiness.RESEARCH_ARTIFACT


def _mapping_from_model(value: Mapping[str, Any] | BaseModel) -> dict[str, Any]:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    return {str(key): item for key, item in value.items()}


def _collect_artifact_refs(value: Any) -> list[ArtifactRef]:
    refs: list[ArtifactRef] = []
    if isinstance(value, Mapping):
        if {"artifact_id", "kind", "media_type"}.issubset(value):
            try:
                refs.append(ArtifactRef.model_validate(value))
            except (TypeError, ValueError, ValidationError):
                pass
        for nested in value.values():
            refs.extend(_collect_artifact_refs(nested))
    elif isinstance(value, list):
        for nested in value:
            refs.extend(_collect_artifact_refs(nested))
    return refs


def _dedupe_refs(refs: Iterable[ArtifactRef]) -> list[ArtifactRef]:
    output: list[ArtifactRef] = []
    seen: set[str] = set()
    for ref in refs:
        artifact_id = str(ref.artifact_id)
        if artifact_id in seen:
            continue
        seen.add(artifact_id)
        output.append(ref)
    return output


def _dedupe_claims(claims: Iterable[ClaimRecord]) -> list[ClaimRecord]:
    output: list[ClaimRecord] = []
    seen: set[str] = set()
    for claim in claims:
        if claim.claim_id in seen:
            continue
        seen.add(claim.claim_id)
        output.append(claim)
    return output


def _first_ref_by_kind(refs: Iterable[ArtifactRef], token: str) -> ArtifactRef | None:
    token = token.lower()
    for ref in refs:
        if token in ref.kind.lower():
            return ref
    return None


def _has_failed_refutations(payload: Mapping[str, Any]) -> bool:
    refutations = payload.get("refutation_results")
    if not isinstance(refutations, list):
        return False
    return any(isinstance(item, Mapping) and item.get("passed") is False for item in refutations)


def _has_meaningful_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, Mapping):
        return any(_has_meaningful_value(item) for item in value.values())
    if isinstance(value, (list, tuple, set)):
        return any(_has_meaningful_value(item) for item in value)
    return True


def _string_or_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [text for item in value if (text := _string_or_none(item))]


def _compact_text(text: str, *, limit: int = 600) -> str:
    clean = " ".join(str(text).split())
    if len(clean) <= limit:
        return clean
    return clean[: limit - 3].rstrip() + "..."


__all__ = [
    "DECISION_BEARING_PACKET_FIELDS",
    "deterministic_claim_id",
    "has_decision_bearing_content",
    "project_causal_effect_claims",
    "project_causal_validity_bundle_claims",
    "project_decision_packet_claims",
    "project_frontier_runtime_claims",
    "project_governance_report_claims",
    "project_policy_artifact_bundle_claims",
]
