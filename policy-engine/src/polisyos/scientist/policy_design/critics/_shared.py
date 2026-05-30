"""Shared helpers for W6.E critic implementations."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from polisyos.scientist.policy_design.critic_contracts import (
    CriticEnvelope,
    CriticVerdict,
    build_critic_candidate,
    critic_verdict,
)
from polisyos.scientist.policy_design.formulator import (
    FormulatorCandidate,
    LLMFormulatorInput,
    mapping_from_any,
    sequence_from_any,
)

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence


def candidate_ids(candidates: Sequence[FormulatorCandidate]) -> tuple[str, ...]:
    """Return candidate ids in deterministic order."""

    return tuple(candidate.candidate_id for candidate in candidates)


def context_facets(context: LLMFormulatorInput) -> dict[str, Any]:
    """Return the input facet mapping."""

    return mapping_from_any(context.facets)


def context_claims(context: LLMFormulatorInput) -> tuple[dict[str, Any], ...]:
    """Return claim decomposition records as mappings."""

    return tuple(mapping_from_any(item) for item in sequence_from_any(context.claim_decomposition))


def context_obligations(context: LLMFormulatorInput) -> tuple[dict[str, Any], ...]:
    """Return obligation records as mappings."""

    return tuple(mapping_from_any(item) for item in sequence_from_any(context.obligations))


def has_any(mapping: Mapping[str, Any], keys: Sequence[str]) -> bool:
    """Return whether any key has a non-empty value."""

    return any(bool(mapping.get(key)) for key in keys)


def text_contains_any(text: str, terms: Sequence[str]) -> bool:
    """Case-insensitive containment check."""

    lower = text.lower()
    return any(term.lower() in lower for term in terms)


def candidates_contain_any(
    candidates: Sequence[FormulatorCandidate],
    terms: Sequence[str],
) -> bool:
    """Return whether any candidate text contains one of the terms."""

    return any(text_contains_any(candidate.text, terms) for candidate in candidates)


def claim_family_present(claims: Sequence[Mapping[str, Any]], families: Sequence[str]) -> bool:
    """Return whether any claim belongs to one of the families."""

    wanted = {family.lower() for family in families}
    for claim in claims:
        family = str(
            claim.get("claim_family") or claim.get("family") or claim.get("claim_type") or ""
        ).lower()
        if family in wanted:
            return True
    return False


def obligation_family_present(
    obligations: Sequence[Mapping[str, Any]],
    families: Sequence[str],
) -> bool:
    """Return whether any obligation belongs to one of the families."""

    wanted = {family.lower() for family in families}
    for obligation in obligations:
        family = str(obligation.get("family") or obligation.get("rule_family") or "").lower()
        if family in wanted:
            return True
    return False


def agree(
    envelope: CriticEnvelope,
    candidates: Sequence[FormulatorCandidate],
    message: str,
    *,
    failure_modes: Sequence[str] = (),
) -> CriticVerdict:
    """Build an agree verdict."""

    return critic_verdict(
        envelope,
        verdict="agree",
        target_candidate_ids=candidate_ids(candidates),
        message=message,
        failure_modes=failure_modes,
    )


def missing_evidence(
    envelope: CriticEnvelope,
    candidates: Sequence[FormulatorCandidate],
    message: str,
    *,
    failure_modes: Sequence[str],
    evidence_refs: Sequence[str] = (),
) -> CriticVerdict:
    """Build a missing-evidence verdict."""

    return critic_verdict(
        envelope,
        verdict="flag_missing_evidence",
        target_candidate_ids=candidate_ids(candidates),
        message=message,
        failure_modes=failure_modes,
        evidence_refs=evidence_refs,
    )


def contest(
    envelope: CriticEnvelope,
    candidates: Sequence[FormulatorCandidate],
    message: str,
    *,
    failure_modes: Sequence[str],
) -> CriticVerdict:
    """Build a contest verdict."""

    return critic_verdict(
        envelope,
        verdict="contest",
        target_candidate_ids=candidate_ids(candidates),
        message=message,
        failure_modes=failure_modes,
    )


def scope_drift(
    envelope: CriticEnvelope,
    candidates: Sequence[FormulatorCandidate],
    message: str,
    *,
    failure_modes: Sequence[str],
) -> CriticVerdict:
    """Build a scope-drift verdict."""

    return critic_verdict(
        envelope,
        verdict="flag_scope_drift",
        target_candidate_ids=candidate_ids(candidates),
        message=message,
        failure_modes=failure_modes,
    )


def speculation(
    envelope: CriticEnvelope,
    candidates: Sequence[FormulatorCandidate],
    message: str,
    *,
    failure_modes: Sequence[str],
) -> CriticVerdict:
    """Build a speculation verdict."""

    return critic_verdict(
        envelope,
        verdict="flag_speculation",
        target_candidate_ids=candidate_ids(candidates),
        message=message,
        failure_modes=failure_modes,
    )


def candidate_obligation(
    envelope: CriticEnvelope,
    context: LLMFormulatorInput,
    candidates: Sequence[FormulatorCandidate],
    text: str,
    *,
    failure_modes: Sequence[str],
    facet_refs: Sequence[str] = (),
    claim_refs: Sequence[str] = (),
    obligation_refs: Sequence[str] = (),
) -> CriticVerdict:
    """Build an add-candidate-obligation verdict with a candidate-only payload."""

    proposed = build_critic_candidate(
        envelope,
        context,
        kind="obligation",
        text=text,
        facet_refs=facet_refs,
        claim_refs=claim_refs,
        obligation_refs=obligation_refs,
        metadata={"failure_modes": list(failure_modes)},
    )
    return critic_verdict(
        envelope,
        verdict="add_candidate_obligation",
        target_candidate_ids=candidate_ids(candidates),
        message=text,
        failure_modes=failure_modes,
        proposed_candidate=proposed,
    )
