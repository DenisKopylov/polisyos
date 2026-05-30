"""Downstream consumer guards for compiled universal policy design cases."""

from __future__ import annotations

from polisyos.core import contracts

UniversalPolicyAuthorityPurpose = contracts.UniversalPolicyAuthorityPurpose
UniversalPolicyDesignCase = contracts.UniversalPolicyDesignCase


class PolicyGrammarConsumerError(ValueError):
    """Raised when a compiled grammar artifact cannot be consumed safely."""


def require_compiled_universal_policy_design_case(
    case: UniversalPolicyDesignCase,
) -> UniversalPolicyDesignCase:
    """Return a case only when W6.A facets are present and consumer-safe."""
    if case.status == "blocked":
        raise PolicyGrammarConsumerError("universal policy design case is blocked")
    if case.facets is None:
        raise PolicyGrammarConsumerError("universal policy design case has no compiled facets")
    return case


def facet_snapshots_for_obligation_graph(
    case: UniversalPolicyDesignCase,
) -> tuple[dict[str, object], ...]:
    """Project W6.A facets into the W6.C parallel interface schema.

    The obligation graph consumes field-level facet snapshots instead of the
    policy-grammar implementation. Keeping the bridge here gives downstream
    compilers stable semantic grounding without duplicating facet derivation.
    """

    compiled = require_compiled_universal_policy_design_case(case)
    facets = compiled.facets
    if facets is None:
        raise PolicyGrammarConsumerError("universal policy design case has no compiled facets")
    scope = ":".join(
        (
            _facet_value(facets.population_predicate),
            _facet_value(facets.geography_predicate),
        )
    )
    authority_profile = compiled.authority_profile.profile_id
    temporal_window = _facet_value(facets.time_predicate)
    rows: list[dict[str, object]] = []
    for facet in facets.iter_facets():
        rows.append(
            {
                "facet_id": f"{compiled.case_id}:{facet.facet_name}",
                "facet_type": facet.facet_name,
                "value": _facet_value(facet),
                "concept_ref": facet.concept_spine_refs[0],
                "scope": scope,
                "authority_profile": authority_profile,
                "temporal_window": temporal_window,
                "metadata": {
                    "case_id": compiled.case_id,
                    "intent_id": compiled.intent_id,
                    "concept_spine_refs": list(facet.concept_spine_refs),
                    "source_vocabulary_refs": list(facet.source_vocabulary_refs),
                    "derivation_rule_ref": facet.derivation_rule_ref,
                },
            }
        )
    return tuple(rows)


def assert_authority_slot_eligible(
    case: UniversalPolicyDesignCase,
    purpose: UniversalPolicyAuthorityPurpose,
) -> UniversalPolicyDesignCase:
    """Fail closed when a compiled case is read as unsupported authority."""
    if case.status == "candidate_unverified":
        raise PolicyGrammarConsumerError(
            f"candidate_unverified case cannot satisfy {purpose} authority"
        )
    if purpose in case.authority_envelope.may_not_use_for:
        raise PolicyGrammarConsumerError(f"case may_not_use_for {purpose}")
    if purpose not in case.authority_envelope.authoritative_for:
        raise PolicyGrammarConsumerError(f"case is not authoritative_for {purpose}")
    return case


def _facet_value(facet: object) -> str:
    value = getattr(facet, "value", facet)
    enum_value = getattr(value, "value", value)
    text = str(enum_value).strip()
    if not text:
        raise PolicyGrammarConsumerError("facet snapshot value is empty")
    return text


__all__ = [
    "PolicyGrammarConsumerError",
    "assert_authority_slot_eligible",
    "facet_snapshots_for_obligation_graph",
    "require_compiled_universal_policy_design_case",
]
