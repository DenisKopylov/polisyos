from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from pydantic import ValidationError

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.scientist.evidence.claims.export import (
    ClaimExportAudience,
    _format_resolved_claim_ledger,
)
from polisyos.scientist.evidence.claims.head_index import ClaimBridgePendingProjection
from polisyos.scientist.evidence.claims.ledger import _load_claim_ledger, _persist_claim_ledger
from polisyos.scientist.evidence.claims.models import (
    AlternativeRejectionReason,
    AlternativeStatus,
    BaselineType,
    ClaimFamily,
    ClaimPublishability,
    ClaimRecord,
    ClaimSourceClass,
    ClaimSupportStatus,
    ClaimType,
    ClaimUse,
)
from polisyos.scientist.methods.search.readiness import DecisionReadiness
from polisyos.scientist.policy_design.claim_decomposition import (
    ClaimDecompositionCompiler,
    ClaimDecompositionFacet,
    ClaimDecompositionInput,
    ClaimDecompositionNamedAlternative,
    ClaimDecompositionObligation,
    compile_participation_requirements_from_claim_ledger,
)

if TYPE_CHECKING:
    from pathlib import Path


def _msme_compilation_input() -> ClaimDecompositionInput:
    return ClaimDecompositionInput(
        run_id="run_w6d_msme",
        intent=(
            "Design an MSME credit guarantee that improves credit access without hiding "
            "fiscal risk."
        ),
        facets=[
            ClaimDecompositionFacet(
                facet_id="facet_instrument",
                facet_type="instrument_type",
                value="credit guarantee",
                concept_spine_refs=["concept.msme_credit_guarantee"],
                authority_profile_refs=["authority.fiscal_delegated"],
            ),
            ClaimDecompositionFacet(
                facet_id="facet_outcome",
                facet_type="outcome_channel",
                value="credit access",
                concept_spine_refs=["concept.credit_access"],
                authority_profile_refs=["authority.fiscal_delegated"],
            ),
            ClaimDecompositionFacet(
                facet_id="facet_equity",
                facet_type="risk_facet",
                value="underserved firm exclusion",
                concept_spine_refs=["concept.underserved_msme"],
                authority_profile_refs=["authority.fiscal_delegated"],
            ),
            ClaimDecompositionFacet(
                facet_id="facet_shock",
                facet_type="scenario_baseline",
                value="regional banking liquidity shock",
                concept_spine_refs=["concept.liquidity_shock"],
                authority_profile_refs=["authority.fiscal_delegated"],
            ),
        ],
        obligations=[
            ClaimDecompositionObligation(
                obligation_id="obl_legal",
                family="legal_authority",
                description="Verify delegated fiscal authority and guarantee limits.",
                facet_refs=["facet_instrument"],
                concept_spine_refs=["concept.msme_credit_guarantee"],
                authority_profile_refs=["authority.fiscal_delegated"],
                source_class=ClaimSourceClass.GOVERNED_RULE,
            ),
            ClaimDecompositionObligation(
                obligation_id="obl_participation",
                family="participation",
                description="Affected MSMEs and lenders must be represented before legitimacy use.",
                facet_refs=["facet_equity"],
                concept_spine_refs=["concept.underserved_msme"],
                authority_profile_refs=["authority.public_consultation"],
                source_class=ClaimSourceClass.GOVERNED_RULE,
            ),
            ClaimDecompositionObligation(
                obligation_id="obl_delivery",
                family="implementation",
                description="Confirm bank delivery channel feasibility and monitoring burden.",
                facet_refs=["facet_instrument", "facet_shock"],
                concept_spine_refs=["concept.bank_delivery"],
                authority_profile_refs=["authority.fiscal_delegated"],
                source_class=ClaimSourceClass.DETERMINISTIC_CRITIC,
            ),
        ],
        named_alternatives=[
            ClaimDecompositionNamedAlternative(
                alternative_id="alt_direct_grants",
                label="Direct MSME grants",
                description="Provide direct grants instead of loan guarantees.",
            ),
            ClaimDecompositionNamedAlternative(
                alternative_id="alt_bank_liquidity_line",
                label="Bank liquidity line",
                description="Provide liquidity to banks without MSME targeting.",
                status=AlternativeStatus.REJECTED,
                rejected_reasons=[AlternativeRejectionReason.VALUE_CHOICE],
            ),
        ],
    )


def test_compiler_emits_claim_families_baseline_alternative_seeds_and_method_preconditions(
    tmp_path: Path,
) -> None:
    ledger = ClaimDecompositionCompiler().compile(_msme_compilation_input())

    families = {assignment.claim_family for assignment in ledger.family_assignments}
    baseline_types = {record.baseline_type for record in ledger.baseline_records}
    alternative_ids = {record.alternative_id for record in ledger.alternative_records}
    superiority_claims = [
        claim for claim in ledger.claims if claim.claim_use is ClaimUse.SUPERIORITY
    ]

    assert {
        ClaimFamily.CAUSAL,
        ClaimFamily.DISTRIBUTIONAL,
        ClaimFamily.LEGITIMACY,
        ClaimFamily.ACCEPTABILITY,
        ClaimFamily.IMPLEMENTATION_FEASIBILITY,
    }.issubset(families)
    assert {
        BaselineType.NO_ACTION,
        BaselineType.STATUS_QUO,
        BaselineType.BUSINESS_AS_USUAL,
        BaselineType.NAMED_ALTERNATIVE,
        BaselineType.FRAGILITY_SCENARIO,
    }.issubset(baseline_types)
    assert alternative_ids == {"alt_direct_grants", "alt_bank_liquidity_line"}
    assert superiority_claims
    assert all(claim.baseline_refs for claim in superiority_claims)
    assert all(claim.alternative_refs for claim in superiority_claims)
    assert any(
        precondition.method_need == "causal_identification"
        for claim in ledger.claims
        for precondition in claim.method_need_preconditions
    )
    assert all(claim.claim_use is not None for claim in ledger.claims)
    assert all(claim.facet_refs for claim in ledger.claims)
    assert all(claim.concept_spine_refs for claim in ledger.claims)
    assert all(claim.authority_profile_refs for claim in ledger.claims)

    store = FileSystemCAS(tmp_path)
    ref = _persist_claim_ledger(store, ledger)
    loaded = _load_claim_ledger(store, ref)
    exported = _format_resolved_claim_ledger(
        loaded,
        audience=ClaimExportAudience.MACHINE,
        pending_projection=ClaimBridgePendingProjection(
            completed_batch_denominator_established=True,
        ),
    )

    assert loaded.baseline_records == ledger.baseline_records
    assert loaded.alternative_records == ledger.alternative_records
    assert exported.metadata["baseline_record_count"] == len(ledger.baseline_records)
    assert exported.metadata["alternative_record_count"] == len(ledger.alternative_records)
    assert any(claim.claim_use == ClaimUse.SUPERIORITY.value for claim in exported.claims)


def test_superiority_claim_requires_baseline_and_named_alternative_refs() -> None:
    with pytest.raises(ValidationError, match="superiority claims require"):
        ClaimRecord(
            claim_id="claim_superiority_without_comparator",
            run_id="run_w6d",
            claim_type=ClaimType.WELFARE,
            text="The selected option is superior.",
            support_status=ClaimSupportStatus.UNSUPPORTED,
            publishability=ClaimPublishability.DRAFT,
            readiness_level=DecisionReadiness.RESEARCH_ARTIFACT,
            claim_family=ClaimFamily.WELFARE,
            claim_use=ClaimUse.SUPERIORITY,
            facet_refs=["facet_outcome"],
            obligation_refs=["obl_compare"],
            concept_spine_refs=["concept.welfare"],
            authority_profile_refs=["authority.fiscal_delegated"],
        )


def test_llm_candidate_obligation_is_downgraded_to_context_only_not_authority() -> None:
    payload = ClaimDecompositionInput(
        run_id="run_w6d_laundering",
        intent="Approve an emergency housing subsidy because an LLM says residents support it.",
        facets=[
            ClaimDecompositionFacet(
                facet_id="facet_housing",
                facet_type="delivery_channel",
                value="housing subsidy",
                concept_spine_refs=["concept.housing_subsidy"],
                authority_profile_refs=["authority.housing"],
            )
        ],
        obligations=[
            ClaimDecompositionObligation(
                obligation_id="obl_llm_support",
                family="participation_legitimacy",
                description="Residents strongly support the subsidy.",
                facet_refs=["facet_housing"],
                concept_spine_refs=["concept.resident_support"],
                authority_profile_refs=["authority.housing"],
                source_class=ClaimSourceClass.LLM_CANDIDATE,
            )
        ],
    )

    ledger = ClaimDecompositionCompiler().compile(payload)

    laundering_claims = [
        claim for claim in ledger.claims if "Residents strongly support" in claim.text
    ]
    assert laundering_claims
    assert all(claim.claim_family is ClaimFamily.CONTEXT_ONLY for claim in laundering_claims)
    assert all(claim.claim_use is ClaimUse.CONTEXT_ONLY for claim in laundering_claims)
    assert all(
        claim.decomposition_source_class is ClaimSourceClass.LLM_CANDIDATE
        for claim in laundering_claims
    )
    assert all(
        "candidate_source_not_authority" in claim.blocked_reasons for claim in laundering_claims
    )
    assert not any(
        claim.claim_use is ClaimUse.PARTICIPATION_LEGITIMACY
        and claim.decomposition_source_class is ClaimSourceClass.LLM_CANDIDATE
        for claim in ledger.claims
    )


def test_claim_decomposition_bridges_participation_claims_to_requirements() -> None:
    ledger = ClaimDecompositionCompiler().compile(_msme_compilation_input())

    bundle = compile_participation_requirements_from_claim_ledger(
        ledger,
        authority_level="production",
        population_scope="affected_population",
    )

    assert bundle.requirements
    assert {requirement.claim_id for requirement in bundle.requirements} <= {
        claim.claim_id for claim in ledger.claims
    }
    assert any(
        requirement.claim_use_requested == "qualitative"
        and requirement.claim_purpose == "acceptability"
        for requirement in bundle.requirements
    )
