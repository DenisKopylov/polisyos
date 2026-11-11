"""Deterministic compiler for W6.A universal policy grammar."""

from __future__ import annotations

import hashlib
import json
from typing import TYPE_CHECKING, Literal

from polisyos.core import artifacts, contracts

from .artifacts import persist_universal_policy_design_case
from .authority import bind_authority_profile, status_for_authority_profile
from .facets import FACET_NAMES, derive_facets
from .normalizer import normalise_component_intent, normalise_intent

if TYPE_CHECKING:
    from .schema import (
        CompiledUniversalPolicyDesignCaseArtifact,
        PolicyGrammarConceptSpineRefs,
        PolicyGrammarIntent,
    )

FileSystemCAS = artifacts.FileSystemCAS
UniversalAuthorityProfile = contracts.UniversalAuthorityProfile
UniversalPolicyComponentFacets = contracts.UniversalPolicyComponentFacets
UniversalPolicyDesignCase = contracts.UniversalPolicyDesignCase
UniversalPolicyDesignCaseAuditSurface = contracts.UniversalPolicyDesignCaseAuditSurface
UniversalPolicyFacets = contracts.UniversalPolicyFacets
UniversalPolicyGrammarBlocker = contracts.UniversalPolicyGrammarBlocker


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
        if intent.policy_spec is not None and len(intent.policy_spec.interventions) > 1:
            return self._compile_components(
                intent=intent,
                authority_profile=authority_profile,
                concept_spine_refs=concept_spine_refs,
            )
        normalized = normalise_intent(intent)
        envelope = bind_authority_profile(authority_profile)
        derivation = derive_facets(
            normalized=normalized,
            authority_type=authority_profile.authority_type,
            concept_spine_refs=concept_spine_refs,
        )
        status = status_for_authority_profile(
            authority_profile,
            blocked=any(blocker.severity == "blocked" for blocker in derivation.blockers),
        )
        case_id = _case_id(
            intent_id=intent.intent_id,
            authority_profile=authority_profile,
            concept_spine_refs=concept_spine_refs,
        )
        schema_version: Literal[
            "policyos.universal_policy_design_case.v1",
            "policyos.universal_policy_design_case.v2",
        ] = "policyos.universal_policy_design_case.v1"
        source_fields: dict[str, str] = {}
        if any("details" in blocker.model_fields_set for blocker in derivation.blockers):
            schema_version = "policyos.universal_policy_design_case.v2"
            case_id, source_intent_sha256 = _extended_case_identity(
                intent=intent,
                authority_profile=authority_profile,
                concept_spine_refs=concept_spine_refs,
                facets=derivation.facets,
                blockers=derivation.blockers,
            )
            source_fields["source_intent_sha256"] = source_intent_sha256
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
            schema_version=schema_version,
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
            **source_fields,
        )

    def _compile_components(
        self,
        *,
        intent: PolicyGrammarIntent,
        authority_profile: UniversalAuthorityProfile,
        concept_spine_refs: PolicyGrammarConceptSpineRefs,
    ) -> UniversalPolicyDesignCase:
        """Compile explicit action components without a global scalar projection."""
        policy = intent.policy_spec
        if policy is None:
            raise ValueError("component compilation requires PolicySpec")
        blockers: list[UniversalPolicyGrammarBlocker] = []
        unsupported = []
        if intent.candidate is not None:
            unsupported.append("shared candidate target")
        if policy.composition is not None:
            unsupported.append("policy composition plan")
        if policy.mechanism_design is not None:
            unsupported.append("mechanism design")
        if policy.temporal_constraints:
            unsupported.append("cross-component temporal constraints")
        if unsupported:
            blockers.append(
                UniversalPolicyGrammarBlocker(
                    code="policy_grammar_component_context_unsupported",
                    message=(
                        "Independent action compilation cannot bind "
                        + ", ".join(unsupported)
                        + " to the declared components."
                    ),
                    pattern_refs=("P10", "P31", "P33"),
                    missing_capability_label="bridge_missing",
                )
            )
        if intent.text or intent.problem_frame is not None or policy.description or policy.labels:
            blockers.append(
                UniversalPolicyGrammarBlocker(
                    code="policy_grammar_shared_context_not_component_scoped",
                    severity="warning",
                    message=(
                        "Shared prose and problem context are retained in the source identity; "
                        "only explicit intervention declarations ground the component facets. "
                        "This result does not establish complete interpretation of shared prose."
                    ),
                    pattern_refs=("P10", "P33"),
                    missing_capability_label="semantic_test_missing",
                )
            )
        components: list[UniversalPolicyComponentFacets] = []
        for intervention in sorted(policy.interventions, key=lambda row: row.intervention_id):
            normalized = normalise_component_intent(intent, intervention=intervention)
            derivation = derive_facets(
                normalized=normalized,
                authority_type=authority_profile.authority_type,
                concept_spine_refs=concept_spine_refs,
            )
            blockers.extend(
                blocker.model_copy(
                    update={
                        "message": f"Component {intervention.intervention_id}: {blocker.message}"
                    }
                )
                for blocker in derivation.blockers
            )
            if not intervention.enabled:
                blockers.append(
                    UniversalPolicyGrammarBlocker(
                        code="policy_grammar_disabled_component_unsupported",
                        message=(
                            f"Component {intervention.intervention_id} is disabled; "
                            "the independent-action envelope cannot treat it as active."
                        ),
                        pattern_refs=("P04", "P33"),
                        missing_capability_label="bridge_missing",
                    )
                )
            if derivation.facets is not None:
                components.append(
                    UniversalPolicyComponentFacets(
                        component_id=intervention.intervention_id,
                        source_intervention_sha256=_content_digest(
                            intervention.model_dump(mode="json")
                        ),
                        facets=derivation.facets,
                        source_contract_refs=normalized.source_contract_refs,
                    )
                )
        blocked = any(blocker.severity == "blocked" for blocker in blockers)
        if blocked:
            components.clear()
        status = status_for_authority_profile(authority_profile, blocked=blocked)
        case_id, source_intent_sha256 = _extended_case_identity(
            intent=intent,
            authority_profile=authority_profile,
            concept_spine_refs=concept_spine_refs,
            components=tuple(components),
            blockers=tuple(blockers),
        )
        envelope = bind_authority_profile(authority_profile)
        return UniversalPolicyDesignCase(
            schema_version="policyos.universal_policy_design_case.v2",
            case_id=case_id,
            intent_id=intent.intent_id,
            status=status,
            authority_profile=authority_profile,
            authority_envelope=envelope,
            concept_spine_ref=concept_spine_refs.concept_spine_ref,
            jurisdiction_spine_ref=concept_spine_refs.jurisdiction_spine_ref,
            facets=None,
            components=tuple(components),
            source_intent_sha256=source_intent_sha256,
            blockers=tuple(blockers),
            audit_surface=UniversalPolicyDesignCaseAuditSurface(
                case_id=case_id,
                status=status,
                authoritative_for=envelope.authoritative_for,
                may_not_use_for=envelope.may_not_use_for,
                facet_names=FACET_NAMES if components else (),
                blocker_codes=tuple(blocker.code for blocker in blockers),
                consumer_components=(
                    "obligation_graph",
                    "claim_decomposition",
                    "requirement_compilers",
                ),
                capability_reality_label="implemented",
            ),
            capability_reality_label="implemented",
            reuse_classification="extend_existing",
            reuse_evidence=tuple(
                dict.fromkeys(
                    ref for component in components for ref in component.source_contract_refs
                )
            ),
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


def _content_digest(payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def _extended_case_identity(
    *,
    intent: PolicyGrammarIntent,
    authority_profile: UniversalAuthorityProfile,
    concept_spine_refs: PolicyGrammarConceptSpineRefs,
    facets: UniversalPolicyFacets | None = None,
    components: tuple[UniversalPolicyComponentFacets, ...] = (),
    blockers: tuple[UniversalPolicyGrammarBlocker, ...] = (),
) -> tuple[str, str]:
    source_intent_sha256 = _content_digest(intent.model_dump(mode="json"))
    payload: dict[str, object] = {
        "source_intent_sha256": source_intent_sha256,
        "components": [component.model_dump(mode="json") for component in components],
        "blockers": [blocker.model_dump(mode="json") for blocker in blockers],
        "authority_profile": authority_profile.model_dump(mode="json"),
        "concept_spine_refs": concept_spine_refs.model_dump(mode="json"),
    }
    if facets is not None:
        payload["facets"] = facets.model_dump(mode="json")
    case_digest = _content_digest(payload)
    return (
        f"universal-policy-design-case:{intent.intent_id}:{case_digest[7:]}",
        source_intent_sha256,
    )


__all__ = ["PolicyGrammarCompiler"]
