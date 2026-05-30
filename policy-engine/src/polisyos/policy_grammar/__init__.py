"""Universal policy grammar compiler public API."""

from __future__ import annotations

from polisyos.core import contracts

from ._impl.artifacts import (
    UNIVERSAL_POLICY_DESIGN_CASE_ARTIFACT_KIND,
    UNIVERSAL_POLICY_DESIGN_CASE_SCHEMA_VERSION,
    load_universal_policy_design_case,
    persist_universal_policy_design_case,
)
from ._impl.compiler import PolicyGrammarCompiler
from ._impl.consumer import (
    PolicyGrammarConsumerError,
    assert_authority_slot_eligible,
    facet_snapshots_for_obligation_graph,
    require_compiled_universal_policy_design_case,
)
from ._impl.schema import (
    CompiledUniversalPolicyDesignCaseArtifact,
    PolicyGrammarConceptSpineRefs,
    PolicyGrammarIntent,
    authority_profile_from_mapping,
)

UniversalAuthorityProfile = contracts.UniversalAuthorityProfile

__all__ = [
    "UNIVERSAL_POLICY_DESIGN_CASE_ARTIFACT_KIND",
    "UNIVERSAL_POLICY_DESIGN_CASE_SCHEMA_VERSION",
    "CompiledUniversalPolicyDesignCaseArtifact",
    "PolicyGrammarCompiler",
    "PolicyGrammarConceptSpineRefs",
    "PolicyGrammarConsumerError",
    "PolicyGrammarIntent",
    "UniversalAuthorityProfile",
    "assert_authority_slot_eligible",
    "authority_profile_from_mapping",
    "facet_snapshots_for_obligation_graph",
    "load_universal_policy_design_case",
    "persist_universal_policy_design_case",
    "require_compiled_universal_policy_design_case",
]
