"""Deterministic compiler for W6.A universal policy grammar."""

from __future__ import annotations

import hashlib
import json

from polisyos.core import artifacts, contracts

from .artifacts import persist_universal_policy_design_case
from .authority import bind_authority_profile, status_for_authority_profile
from .facets import FACET_NAMES, derive_facets
from .normalizer import normalise_intent
from .schema import (
    CompiledUniversalPolicyDesignCaseArtifact,
    PolicyGrammarConceptSpineRefs,
    PolicyGrammarIntent,
)

FileSystemCAS = artifacts.FileSystemCAS
UniversalAuthorityProfile = contracts.UniversalAuthorityProfile
UniversalPolicyDesignCase = contracts.UniversalPolicyDesignCase
UniversalPolicyDesignCaseAuditSurface = contracts.UniversalPolicyDesignCaseAuditSurface


class PolicyGrammarCompiler:
    """Compile policy intent into a typed, compilation-only policy design case."""

    def compile(
        self,
        *,
        intent: PolicyGrammarIntent,
        authority_profile: UniversalAuthorityProfile,
        concept_spine_refs: PolicyGrammarConceptSpineRefs,
    ) -> UniversalPolicyDesignCase:
        """Compile intent, authority profile, and concept-spine refs into W6.A facets."""
        normalized = normalise_intent(intent)
        envelope = bind_authority_profile(authority_profile)
        derivation = derive_facets(
            normalized=normalized,
            authority_type=authority_profile.authority_type,
            concept_spine_refs=concept_spine_refs,
        )
        status = status_for_authority_profile(
            authority_profile,
            blocked=bool(derivation.blockers),
        )
        case_id = _case_id(
            intent_id=intent.intent_id,
            authority_profile=authority_profile,
            concept_spine_refs=concept_spine_refs,
        )
        audit_surface = UniversalPolicyDesignCaseAuditSurface(
            case_id=case_id,
            status=status,
            authoritative_for=envelope.authoritative_for,
            may_not_use_for=envelope.may_not_use_for,
            facet_names=FACET_NAMES if derivation.facets is not None else (),
            blocker_codes=tuple(blocker.code for blocker in derivation.blockers),
            consumer_components=(
                "obligation_graph",
                "claim_decomposition",
                "requirement_compilers",
            ),
            capability_reality_label="implemented",
        )
        return UniversalPolicyDesignCase(
            case_id=case_id,
            intent_id=intent.intent_id,
            status=status,
            authority_profile=authority_profile,
            authority_envelope=envelope,
            concept_spine_ref=concept_spine_refs.concept_spine_ref,
            jurisdiction_spine_ref=concept_spine_refs.jurisdiction_spine_ref,
            facets=derivation.facets,
            blockers=derivation.blockers,
            audit_surface=audit_surface,
            capability_reality_label="implemented",
            reuse_classification="build_new",
            reuse_evidence=normalized.source_contract_refs,
        )

    def compile_and_persist(
        self,
        *,
        store: FileSystemCAS,
        intent: PolicyGrammarIntent,
        authority_profile: UniversalAuthorityProfile,
        concept_spine_refs: PolicyGrammarConceptSpineRefs,
    ) -> CompiledUniversalPolicyDesignCaseArtifact:
        """Compile and persist a universal policy design case artifact."""
        case = self.compile(
            intent=intent,
            authority_profile=authority_profile,
            concept_spine_refs=concept_spine_refs,
        )
        return persist_universal_policy_design_case(store=store, case=case)


def _case_id(
    *,
    intent_id: str,
    authority_profile: UniversalAuthorityProfile,
    concept_spine_refs: PolicyGrammarConceptSpineRefs,
) -> str:
    payload = {
        "intent_id": intent_id,
        "authority_profile": authority_profile.model_dump(mode="json"),
        "concept_spine_refs": concept_spine_refs.model_dump(mode="json"),
    }
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()[:16]
    return f"universal-policy-design-case:{intent_id}:{digest}"


__all__ = ["PolicyGrammarCompiler"]
