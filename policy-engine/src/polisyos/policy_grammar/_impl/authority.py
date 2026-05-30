"""Authority-profile binding for universal policy grammar compilation."""

from __future__ import annotations

from polisyos.core import contracts

UniversalAuthorityProfile = contracts.UniversalAuthorityProfile
UniversalPolicyAuthorityPurpose = contracts.UniversalPolicyAuthorityPurpose
UniversalPolicyGrammarAuthorityEnvelope = contracts.UniversalPolicyGrammarAuthorityEnvelope
UniversalPolicyGrammarStatus = contracts.UniversalPolicyGrammarStatus

_LLM_PROTECTED_PURPOSES: tuple[UniversalPolicyAuthorityPurpose, ...] = (
    "legal_authority",
    "data_authority",
    "method_authority",
    "closeout_authority",
    "publication_authority",
)


def bind_authority_profile(
    profile: UniversalAuthorityProfile,
) -> UniversalPolicyGrammarAuthorityEnvelope:
    """Bind a request authority profile into a compiler authority envelope."""
    may_not_use_for = _dedupe((*profile.may_not_use_for, *_llm_may_not_use_for(profile)))
    return UniversalPolicyGrammarAuthorityEnvelope(
        profile_id=profile.profile_id,
        authority_type=profile.authority_type,
        source_classification=profile.source_classification,
        authoritative_for=profile.authoritative_for,
        may_not_use_for=may_not_use_for,
        rule_version_ref=profile.rule_version_ref,
    )


def status_for_authority_profile(
    profile: UniversalAuthorityProfile,
    *,
    blocked: bool,
) -> UniversalPolicyGrammarStatus:
    """Return the local grammar status implied by blockers and source classification."""
    if blocked:
        return "blocked"
    if profile.source_classification.startswith("llm_"):
        return "candidate_unverified"
    return "compiled"


def _llm_may_not_use_for(
    profile: UniversalAuthorityProfile,
) -> tuple[UniversalPolicyAuthorityPurpose, ...]:
    if profile.source_classification.startswith("llm_"):
        return _LLM_PROTECTED_PURPOSES
    return ()


def _dedupe(
    values: tuple[UniversalPolicyAuthorityPurpose, ...],
) -> tuple[UniversalPolicyAuthorityPurpose, ...]:
    deduped: list[UniversalPolicyAuthorityPurpose] = []
    for value in values:
        if value in deduped:
            continue
        deduped.append(value)
    return tuple(deduped)


__all__ = ["bind_authority_profile", "status_for_authority_profile"]
