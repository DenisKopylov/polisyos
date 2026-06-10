from __future__ import annotations

# ruff: noqa: S101
import importlib
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


def test_layer3_g3_bridge_is_baseline_comparison_evidence_without_authority_escalation(
    tmp_path: Path,
) -> None:
    g3 = importlib.import_module("polisyos.runtime.quality.layer3_analytics_search")
    ledger = _claim_ledger()
    superiority_claim = next(
        claim for claim in ledger.claims if claim.claim_use is ClaimUse.SUPERIORITY
    )
    alternative_ref = sorted(superiority_claim.alternative_refs)[0]
    request, proof_bindings, bridge_binding = _g3_comparison_bridge(
        g3,
        tmp_path,
        superiority_claim.claim_id,
        baseline_ref=sorted(superiority_claim.baseline_refs)[0],
        alternative_ref=alternative_ref,
    )

    gate = g3.build_g3_baseline_comparison_consumer_gate(
        request=request,
        claim_ledger=ledger,
        ir_analytics_bridge=bridge_binding,
        selected_option_ref="selected:msme-credit-guarantee",
        selected_option_label="MSME credit guarantee",
        option_metric_values={
            "selected:msme-credit-guarantee": {"credit_access_gain": 0.34},
            alternative_ref: {"credit_access_gain": 0.22},
        },
        objective_directions={"credit_access_gain": "maximize"},
    )

    comparison = gate.compiled_ledger_payload["comparison_records"][0]
    evidence_refs = {
        evidence["evidence_ref"] for evidence in comparison["comparison_evidence"]
    }

    assert gate.status == "pass"
    assert gate.comparison_record_count == 1
    assert proof_bindings[0].s11_record["ir_analytics_refs"][0] in evidence_refs
    assert bridge_binding.bridge_ref in gate.ir_analytics_bridge_refs
    assert "ir_causal_analytics" in comparison["producer_refs"]
    assert "policy_recommendation" not in comparison["authority_boundary"]["authoritative_for"]
    assert "closeout_pass" in comparison["authority_boundary"]["may_not_use_for"]
    assert "policy_recommendation" in gate.may_not_use_for
    assert "closeout_authority" in gate.may_not_use_for


def _g3_comparison_bridge(
    g3: object,
    tmp_path: Path,
    claim_id: str,
    *,
    baseline_ref: str,
    alternative_ref: str,
) -> tuple[object, tuple[object, ...], object]:
    request = g3.Layer3G3AnalyticsRequest(
        request_id="g3-request:task5:baseline-comparison",
        claim_id=claim_id,
        case_id="ua-msme-affordable-loans-2022",
        cause="agriculture.fertilizer_use",
        effect="agriculture.food_nutritional_quality",
        comparison_ref="comparison://g3/task5/baseline-comparison",
        baseline_ref=baseline_ref,
        alternative_refs=(alternative_ref,),
        concept_refs=("concept://g3/task5/baseline-comparison",),
        semantic_spine_refs=("semantic-spine://g3/task5/baseline-comparison",),
        method_requirement_refs=("g3-method-req:baseline-comparison",),
        certificate_kinds=("proof_bundle",),
    )
    store = FileSystemCAS(tmp_path / "g3-cas")
    candidates = g3.produce_g3_deterministic_first_case_certificate(request, store=store)
    artifact_index = g3.build_g3_ir_artifact_store_index(
        store=store,
        selected_candidates=candidates,
    )
    certificate_report = g3.build_g3_certificate_resolution_report(
        candidates=candidates,
        artifact_index=artifact_index,
        store=store,
    )
    method_bindings = g3.build_g3_method_requirement_bindings(
        request=request,
        method_requirements=(
            {
                "requirement_id": request.method_requirement_refs[0],
                "run_id": request.case_id,
                "claim_id": request.claim_id,
                "identification_class": "point",
                "method_expectations": ["causal_identification"],
                "required_method_families": ["causal_identification"],
                "requires_uncertainty_envelope": False,
                "requires_limitation_refs": False,
                "baseline_refs": [request.baseline_ref],
                "alternative_refs": list(request.alternative_refs),
            },
        ),
        selected_method_refs=("ir.method.g3.task5.baseline_comparison",),
    )
    proof_bindings = g3.build_g3_proof_carrying_analytics_bindings(
        request=request,
        certificate_resolution_report=certificate_report,
        method_requirement_bindings=method_bindings,
    )
    bridge_binding = g3.build_g3_ir_analytics_bridge_bindings(
        proof_carrying_analytics_records=proof_bindings,
        method_requirement_bindings=method_bindings,
    )
    return request, proof_bindings, bridge_binding
