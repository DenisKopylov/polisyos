from __future__ import annotations

from pathlib import Path
from typing import Any

from polisyos.runtime.quality.proving_ground.status_decision_reducers import (
    G1SourceGroundingClosureInputs,
    G2ForecastAdmissionInputs,
    G3ProofAuthorityInputs,
    G4PromotionStateInputs,
    G5ConversionOutcomeInputs,
    G7RegionClosureInputs,
    G8DomainVsSearchCeilingInputs,
    GLLegalAuthorityInputs,
    Layer3ReducerInputRef,
    reduce_g1_source_grounding_closure,
    reduce_g2_forecast_admission,
    reduce_g3_proof_authority,
    reduce_g4_promotion_state,
    reduce_g5_conversion_outcome,
    reduce_g7_region_closure,
    reduce_g8_domain_vs_search_ceiling,
    reduce_gl_legal_authority,
)
from tools.quality.validation import check_policy_design_case_layer3_gx_hardening as gx


def _hash(suffix: str) -> str:
    return "sha256:" + suffix * 64


def _input_ref(
    ref: str = "repo://architecture/policy_design_case/input.json",
    *,
    producer_type: str = "measurement",
    producer_root_status: str = "validated",
    supply_side: bool = True,
) -> Layer3ReducerInputRef:
    return Layer3ReducerInputRef(
        ref=ref,
        content_hash=_hash("a"),
        producer_ref=f"{producer_type}://layer3-gx/input",
        producer_type=producer_type,
        producer_root_refs=(f"{producer_type}://layer3-gx/root",),
        producer_root_status=producer_root_status,
        supply_side=supply_side,
    )


def test_g1_source_grounding_truth_table_is_reducer_authored() -> None:
    cases: tuple[tuple[str, G1SourceGroundingClosureInputs, str], ...] = (
        (
            "noncanonical store cannot close grounding",
            G1SourceGroundingClosureInputs(
                canonical_store=False,
                binding_count=1,
                binding_statuses=("grounded",),
                input_refs=(_input_ref(),),
            ),
            "bounded_surrogate",
        ),
        (
            "validated binding grounds only through reducer",
            G1SourceGroundingClosureInputs(
                canonical_store=True,
                binding_count=1,
                binding_statuses=("grounded",),
                input_refs=(_input_ref(),),
            ),
            "grounded_or_uncertain",
        ),
        (
            "observed binding remains observed",
            G1SourceGroundingClosureInputs(
                canonical_store=True,
                binding_count=1,
                binding_statuses=("observed_but_uncertain",),
                input_refs=(_input_ref(),),
            ),
            "observed_but_uncertain",
        ),
        (
            "measured no-hit can only become approved abstention candidate",
            G1SourceGroundingClosureInputs(
                canonical_store=True,
                measured_no_hit=True,
                search_recall_status="pass",
                index_freshness_status="pass",
                overlay_injection_status="pass",
                abstention_vocabulary_approved=True,
                input_refs=(_input_ref(),),
            ),
            "grounded_abstention_candidate",
        ),
        (
            "unmeasured no-hit is a search ceiling repair",
            G1SourceGroundingClosureInputs(
                canonical_store=True,
                measured_no_hit=False,
                search_recall_status="not_measured",
                index_freshness_status="pass",
                overlay_injection_status="pass",
                input_refs=(_input_ref(),),
            ),
            "search_ceiling_repair_required",
        ),
        (
            "blocked admission prevents closure",
            G1SourceGroundingClosureInputs(
                canonical_store=True,
                candidate_exists=True,
                admission_status="blocked",
                input_refs=(_input_ref(),),
            ),
            "typed_blocker",
        ),
    )

    for _label, inputs, expected in cases:
        decision = reduce_g1_source_grounding_closure(inputs)

        assert decision.status == expected
        assert decision.produced_by["reducer_id"] == "reduce_g1_source_grounding_closure"
        assert decision.produced_by["output_hash"].startswith("sha256:")


def test_required_task4_reducers_have_fail_closed_truth_table_branches() -> None:
    valid = _input_ref()
    cases: tuple[tuple[str, Any, str], ...] = (
        (
            "g2 admits only forecast-support edges",
            reduce_g2_forecast_admission(
                G2ForecastAdmissionInputs(
                    method_binding_status="pass",
                    calibration_status="pass",
                    skg_edge_type="ForecastSupport",
                    input_refs=(valid,),
                )
            ),
            "forecast_admitted",
        ),
        (
            "g2 rejects non-forecast-support edges",
            reduce_g2_forecast_admission(
                G2ForecastAdmissionInputs(
                    method_binding_status="pass",
                    calibration_status="pass",
                    skg_edge_type="RelatedTo",
                    input_refs=(valid,),
                )
            ),
            "typed_blocker",
        ),
        (
            "g3 proof candidate is not proof authority",
            reduce_g3_proof_authority(
                G3ProofAuthorityInputs(
                    proof_candidate_status="candidate",
                    certificate_status="pass",
                    input_refs=(valid,),
                )
            ),
            "typed_blocker",
        ),
        (
            "gl closes only with legal authority",
            reduce_gl_legal_authority(
                GLLegalAuthorityInputs(
                    legal_basis_status="pass",
                    applicability_status="pass",
                    mandate_status="pass",
                    input_refs=(valid,),
                )
            ),
            "legal_authority",
        ),
        (
            "g4 blocks on upstream blocker",
            reduce_g4_promotion_state(
                G4PromotionStateInputs(
                    dependency_statuses=("pass",),
                    blocker_refs=("layer3_g4_required_ref_unresolved",),
                    input_refs=(valid,),
                )
            ),
            "promotion_blocked",
        ),
        (
            "g5 is the only grounded abstention converter",
            reduce_g5_conversion_outcome(
                G5ConversionOutcomeInputs(
                    requested_conversion_outcome="grounded_abstention",
                    g1_grounding_closure="grounded_abstention_candidate",
                    demand_pull_status="pass",
                    cross_slice_status="pass",
                    grounded_evidence_ref_count=1,
                    input_refs=(valid,),
                )
            ),
            "grounded_abstention",
        ),
        (
            "g7 cannot close while gx migration is blocked",
            reduce_g7_region_closure(
                G7RegionClosureInputs(
                    gx_migration_state="blocked_by_gx_migration",
                    g5_conversion_outcome="grounded_limited",
                    regional_breadth_status="pass",
                    input_refs=(valid,),
                )
            ),
            "blocked_by_gx_migration",
        ),
        (
            "g8 separates search ceiling from domain ceiling",
            reduce_g8_domain_vs_search_ceiling(
                G8DomainVsSearchCeilingInputs(
                    g5_conversion_outcome="unchanged_blocker",
                    g7_region_closure="blocked_by_gx_migration",
                    search_recall_status="fail",
                    index_freshness_status="pass",
                    input_refs=(valid,),
                )
            ),
            "search_ceiling_repair_required",
        ),
    )

    for _label, decision, expected in cases:
        assert decision.status == expected
        assert decision.input_refs
        assert decision.rule_version == "policyos.layer3.gx.reducer_only_status.v1"


def test_task6_g4_g5_g8_change_only_from_governed_reducer_inputs() -> None:
    governed_input = _input_ref(
        "repo://architecture/policy_design_case/task6_governed_upstream_artifact.json"
    )

    g4_blocked = reduce_g4_promotion_state(
        G4PromotionStateInputs(
            dependency_statuses=("pass",),
            blocker_refs=("layer3_g4_required_ref_unresolved",),
            input_refs=(governed_input,),
        )
    )
    g4_promoted = reduce_g4_promotion_state(
        G4PromotionStateInputs(
            dependency_statuses=("pass",),
            input_refs=(governed_input,),
        )
    )
    g5_blocked = reduce_g5_conversion_outcome(
        G5ConversionOutcomeInputs(
            requested_conversion_outcome="grounded_limited",
            g4_promotion_state=g4_blocked.status,
            cross_slice_status="pass",
            grounded_evidence_ref_count=1,
            input_refs=(governed_input,),
        )
    )
    g5_limited = reduce_g5_conversion_outcome(
        G5ConversionOutcomeInputs(
            requested_conversion_outcome="grounded_limited",
            g4_promotion_state=g4_promoted.status,
            cross_slice_status="pass",
            grounded_evidence_ref_count=1,
            input_refs=(governed_input,),
        )
    )
    g8_search_blocked = reduce_g8_domain_vs_search_ceiling(
        G8DomainVsSearchCeilingInputs(
            g5_conversion_outcome="unchanged_blocker",
            g7_region_closure="blocked_by_gx_migration",
            search_recall_status="fail",
            index_freshness_status="pass",
            input_refs=(governed_input,),
        )
    )
    g8_domain_supported = reduce_g8_domain_vs_search_ceiling(
        G8DomainVsSearchCeilingInputs(
            g5_conversion_outcome="grounded_abstention",
            g7_region_closure="region_closed",
            search_recall_status="pass",
            index_freshness_status="pass",
            input_refs=(governed_input,),
        )
    )

    assert g4_blocked.status == "promotion_blocked"
    assert g4_promoted.status == "governed_promoted"
    assert g5_blocked.status == "unchanged_blocker"
    assert "layer3_g5_governed_promotion_missing" in g5_blocked.blocker_refs
    assert g5_limited.status == "grounded_limited"
    assert g8_search_blocked.status == "search_ceiling_repair_required"
    assert g8_domain_supported.status == "domain_ceiling_supported"
    for decision in (
        g4_blocked,
        g4_promoted,
        g5_blocked,
        g5_limited,
        g8_search_blocked,
        g8_domain_supported,
    ):
        assert decision.input_refs == (governed_input.ref,)
        assert decision.produced_by["reducer_id"].startswith("reduce_")


def test_positive_reducer_output_hash_matches_gx_recompute_guard(tmp_path: Path) -> None:
    decision = reduce_g4_promotion_state(
        G4PromotionStateInputs(dependency_statuses=("pass",), input_refs=(_input_ref(),))
    )
    artifact = tmp_path / "architecture/policy_design_case/layer3_probe.json"
    artifact.parent.mkdir(parents=True)
    artifact.write_text(
        gx._json_dumps({"promotion_state": decision.status, "produced_by": decision.produced_by}),
        encoding="utf-8",
    )

    report = gx.build_persisted_status_recompute_drift(
        tmp_path,
        artifact_paths=(Path("architecture/policy_design_case/layer3_probe.json"),),
    )

    assert report["status"] == "pass"
    assert report["issues"] == []


def test_inline_or_invalid_supply_inputs_block_positive_statuses() -> None:
    inline = _input_ref().model_copy(update={"producer_ref": None})
    derivation_only = _input_ref(
        producer_type="derivation",
        producer_root_status="derivation_only",
    )

    inline_decision = reduce_g4_promotion_state(
        G4PromotionStateInputs(dependency_statuses=("pass",), input_refs=(inline,))
    )
    derivation_decision = reduce_g4_promotion_state(
        G4PromotionStateInputs(dependency_statuses=("pass",), input_refs=(derivation_only,))
    )

    assert inline_decision.status == "promotion_blocked"
    assert "layer3_gx_inline_input_forbidden" in inline_decision.issue_codes
    assert derivation_decision.status == "promotion_blocked"
    assert "layer3_gx_producer_root_invalid" in derivation_decision.issue_codes
