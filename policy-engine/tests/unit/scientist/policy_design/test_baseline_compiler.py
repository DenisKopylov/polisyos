from __future__ import annotations

# ruff: noqa: S101
from typing import TYPE_CHECKING

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.runtime.quality.claim_registry import build_runtime_claim_registry
from polisyos.scientist.evidence.claims.export import ClaimExportAudience, export_claim_ledger
from polisyos.scientist.evidence.claims.ledger import load_claim_ledger, persist_claim_ledger
from polisyos.scientist.evidence.claims.models import (
    AlternativeRejectionReason,
    AlternativeStatus,
    BaselineType,
    ClaimLedger,
    ClaimUse,
)
from polisyos.scientist.evidence.claims.validators import (
    validate_claim_ledger_for_publication,
)
from polisyos.scientist.policy_design.baseline_compiler import (
    BaselineComparisonCompiler,
    BaselineComparisonInput,
)
from polisyos.scientist.policy_design.claim_decomposition import (
    ClaimDecompositionCompiler,
    ClaimDecompositionFacet,
    ClaimDecompositionInput,
    ClaimDecompositionNamedAlternative,
    ClaimDecompositionObligation,
)

if TYPE_CHECKING:
    from pathlib import Path


def _claim_ledger() -> ClaimLedger:
    return ClaimDecompositionCompiler().compile(
        ClaimDecompositionInput(
            run_id="run_w8c_msme",
            intent=(
                "Choose an MSME credit guarantee only if it beats no-action, "
                "status quo, and named grant alternatives on access and fiscal risk."
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
            ],
            obligations=[
                ClaimDecompositionObligation(
                    obligation_id="obl_compare",
                    family="welfare comparison",
                    description="Compare selected option against baselines and alternatives.",
                    facet_refs=["facet_instrument", "facet_outcome"],
                    concept_spine_refs=["concept.credit_access"],
                    authority_profile_refs=["authority.fiscal_delegated"],
                )
            ],
            named_alternatives=[
                ClaimDecompositionNamedAlternative(
                    alternative_id="alt_direct_grants",
                    label="Direct MSME grants",
                    description="Provide direct grants instead of guarantees.",
                ),
                ClaimDecompositionNamedAlternative(
                    alternative_id="alt_liquidity_line",
                    label="Bank liquidity line",
                    description="Provide wholesale liquidity without MSME targeting.",
                    status=AlternativeStatus.REJECTED,
                    rejected_reasons=[AlternativeRejectionReason.VALUE_CHOICE],
                ),
            ],
        )
    )


def test_compiler_emits_full_comparison_records_and_claim_registry_refs(
    tmp_path: Path,
) -> None:
    ledger = _claim_ledger()
    superiority_claim = next(
        claim for claim in ledger.claims if claim.claim_use is ClaimUse.SUPERIORITY
    )

    comparison_input = BaselineComparisonInput(
        claim_ledger=ledger,
        selected_option_ref="selected:msme-credit-guarantee",
        selected_option_label="MSME credit guarantee",
        option_metric_values={
            "selected:msme-credit-guarantee": {
                "credit_access_gain": 0.34,
                "fiscal_risk": 0.18,
            },
            "alt_direct_grants": {
                "credit_access_gain": 0.22,
                "fiscal_risk": 0.31,
            },
            "alt_liquidity_line": {
                "credit_access_gain": 0.12,
                "fiscal_risk": 0.27,
            },
        },
        objective_directions={
            "credit_access_gain": "maximize",
            "fiscal_risk": "minimize",
        },
        fabric_source_bindings={
            "source_contract_bindings": [
                {
                    "claim_id": superiority_claim.claim_id,
                    "option_ref": "selected:msme-credit-guarantee",
                    "candidate_ref": "fabric:msme-panel:selected",
                    "binding_status": "selected",
                },
                {
                    "claim_id": superiority_claim.claim_id,
                    "option_ref": "alt_direct_grants",
                    "candidate_ref": "fabric:grant-registry:alternative",
                    "binding_status": "selected",
                },
            ]
        },
        foundry_method_report={
            "selected_methods": [
                {
                    "method_id": "foundry.bounds.credit_access",
                    "claim_id": superiority_claim.claim_id,
                    "method_output_refs": {
                        "selected": "foundry-output:credit-access-bounds"
                    },
                    "limitation_refs": {"scope": "foundry-limitation:regional-transfer"},
                    "uncertainty_envelope_refs": {"bounds": "uncertainty:credit-access"},
                    "baseline_refs": list(superiority_claim.baseline_refs),
                    "alternative_refs": list(superiority_claim.alternative_refs),
                }
            ]
        },
        ir_analytics_bridge={
            "claim_bindings": [
                {
                    "claim_id": superiority_claim.claim_id,
                    "ir_analytics_refs": ["ir:contrast:credit-access"],
                    "method_output_refs": ["ir-method:contrast-estimator"],
                    "ir_certificate_refs": ["ir-certificate:transportability"],
                    "uncertainty_refs": ["ir-uncertainty:transport"],
                    "limitation_refs": ["ir-limitation:partial-identification"],
                    "baseline_refs": list(superiority_claim.baseline_refs),
                }
            ]
        },
        scholar_evidence_report={
            "support_links": [
                {
                    "claim_id": superiority_claim.claim_id,
                    "option_ref": "selected:msme-credit-guarantee",
                    "support_ref": "scholar-support:guarantees",
                    "source_id": "study:credit-guarantees-2025",
                    "support_status": "supported",
                    "effective_support_count": 1,
                },
                {
                    "claim_id": superiority_claim.claim_id,
                    "option_ref": "alt_direct_grants",
                    "support_ref": "scholar-support:grants",
                    "source_id": "study:grants-2024",
                    "support_status": "supported",
                    "effective_support_count": 1,
                },
            ],
            "conflict_links": [],
        },
    )

    compiled = BaselineComparisonCompiler().compile(comparison_input)

    comparison = compiled.comparison_records[0]
    updated_claim = next(
        claim for claim in compiled.claims if claim.claim_id == superiority_claim.claim_id
    )
    exported = export_claim_ledger(compiled, audience=ClaimExportAudience.MACHINE)

    assert comparison.claim_id == superiority_claim.claim_id
    assert set(comparison.baseline_types_covered) >= {
        BaselineType.NO_ACTION,
        BaselineType.STATUS_QUO,
        BaselineType.BUSINESS_AS_USUAL,
        BaselineType.NAMED_ALTERNATIVE,
    }
    assert comparison.selected_option_evidence_refs
    assert set(comparison.comparison_method_refs) >= {
        "foundry-output:credit-access-bounds",
        "ir-method:contrast-estimator",
        "ir-certificate:transportability",
    }
    assert set(comparison.comparison_limitation_refs) >= {
        "foundry-limitation:regional-transfer",
        "ir-limitation:partial-identification",
    }
    assert comparison.comparison_status == "limited"
    assert {record.dominated_option_ref for record in comparison.dominated_frontier_records} >= {
        "alt_direct_grants",
        "alt_liquidity_line",
    }
    assert any(
        reason.reason is AlternativeRejectionReason.DOMINATED_FRONTIER
        for reason in comparison.rejected_option_reasons
    )
    assert updated_claim.comparison_refs == [comparison.comparison_id]
    assert exported.metadata["comparison_record_count"] == 1
    assert exported.comparison_records[0]["comparison_id"] == comparison.comparison_id

    store = FileSystemCAS(tmp_path)
    ref = persist_claim_ledger(store, compiled)
    loaded = load_claim_ledger(store, ref)
    assert loaded.comparison_records == compiled.comparison_records


def test_superiority_publication_and_registry_fail_without_w8c_comparison_record() -> None:
    ledger = _claim_ledger()
    superiority_claim = next(
        claim for claim in ledger.claims if claim.claim_use is ClaimUse.SUPERIORITY
    )

    validation = validate_claim_ledger_for_publication(ledger)
    registry = build_runtime_claim_registry(
        claims=[superiority_claim.model_dump(mode="json", exclude_none=True)],
        run_id=ledger.run_id,
    )

    assert not validation.passed
    assert f"superiority_comparison_missing:{superiority_claim.claim_id}" in validation.violations
    assert any(
        issue["code"] == "runtime_claim_registry_superiority_comparison_refs_missing"
        for issue in registry["issues"]
    )
