from __future__ import annotations

# ruff: noqa: S101
from pathlib import Path
from typing import Any

from polisyos.runtime.quality.evidence_independence import (
    build_evidence_independence_map,
)
from polisyos.runtime.quality.evidence_portfolio import (
    EVIDENCE_PORTFOLIO_DESIGN_SCHEMA_VERSION,
)
from polisyos.runtime.quality.prompt_tool_ledger import (
    CompressionClaimItem,
    CompressionMaterialItem,
    CompressionMaterialSet,
    build_compression_loss_receipt,
)
from tests._helpers.hds_quality import sha

REPO_ROOT = Path(__file__).resolve().parents[4]


def _portfolio_design() -> dict[str, object]:
    return {
        "schema_version": EVIDENCE_PORTFOLIO_DESIGN_SCHEMA_VERSION,
        "portfolio_id": "portfolio-compression-consensus",
        "claim_ids": ["claim-consensus"],
        "predeclared": True,
        "declared_at": "2026-08-19T08:00:00+00:00",
        "declared_before_producer_execution": True,
        "authority_level": "production",
        "strands": [
            {
                "strand_id": "data-method-literature",
                "claim_id": "claim-consensus",
                "authority_level": "production",
                "candidate_data_source_families": ["administrative_registry"],
                "candidate_method_families": ["causal_effect_estimation"],
                "defensible_specification_space": {
                    "primary_estimand": "ATT",
                    "allowed_models": ["event_study"],
                },
                "inclusion_rules": ["Include admitted administrative sources."],
                "exclusion_rules": ["Exclude ungrounded candidate sources."],
                "disconfirming_lines": [
                    {
                        "line_id": "negative-control",
                        "required": True,
                        "evidence_family": "negative_control",
                    }
                ],
                "synthesis_rules": {"strategy": "triangulate_independent_lines"},
                "stopping_rules": {
                    "minimum_effective_independent_evidence_count": 2,
                },
                "cost_proportionality": {"budget_tier": "standard"},
            }
        ],
        "candidate_data_source_families": ["administrative_registry"],
        "candidate_method_families": ["causal_effect_estimation"],
        "inclusion_rules": ["Include admitted administrative sources."],
        "exclusion_rules": ["Exclude ungrounded candidate sources."],
        "disconfirming_lines": ["negative-control"],
        "synthesis_rules": {"strategy": "triangulate_independent_lines"},
        "stopping_rules": {"minimum_effective_independent_evidence_count": 2},
        "cost_proportionality": {"budget_tier": "standard"},
        "cas_ref": sha("compression-portfolio"),
        "runtime_event_ref": sha("compression-portfolio-event"),
    }


def _dependent_evidence_line(index: int) -> dict[str, Any]:
    return {
        "schema_version": "policyos.runtime.policy_design_case.evidence_line.v1",
        "line_id": f"compression-line-{index}",
        "portfolio_id": "portfolio-compression-consensus",
        "portfolio_strand_id": "data-method-literature",
        "claim_id": "claim-consensus",
        "evidence_strand": "data",
        "source_lineage": {
            "source_id": "shared-administrative-registry",
            "source_ref": sha("shared-source"),
            "lineage_refs": [sha("shared-lineage")],
            "corpus_id": "shared-corpus",
            "corpus_ancestry": ["shared-corpus-parent"],
        },
        "corpus_ancestry": ["shared-corpus-parent"],
        "author_pool": ["shared-analysis-cell"],
        "institution_pool": ["shared-policy-lab"],
        "preprocessing_pipeline_id": "shared-preprocessing",
        "method_id": "foundry.did.shared",
        "method_assumptions": ["shared parallel-trends assumption"],
        "identification_strategy_id": "shared-did-identification",
        "shared_failure_modes": ["shared-linkage-bias"],
        "specification_id": f"shared-spec-{index}",
        "producer_identity": {
            "component": "polisyos.foundry.methods.causal",
            "version": "2026.08.19+compression-red",
            "owner": "team-science-quality",
        },
        "execution_context": {
            "run_id": "run-compression-red",
            "job_id": f"job-compression-red-{index}",
            "tenant_id": "tenant-prod",
            "trace_id": f"trace-compression-red-{index}",
        },
        "evidence_ref": sha(f"compression-evidence-{index}"),
        "runtime_event_ref": sha(f"compression-event-{index}"),
    }


def _item(item_id: str, content: str) -> CompressionMaterialItem:
    return CompressionMaterialItem(item_id=item_id, content=content)


def _baseline_material(
    *,
    claims: tuple[CompressionClaimItem, ...] = (),
    limitations: tuple[CompressionMaterialItem, ...] | None = None,
    governance_burden_refs: tuple[str, ...] = ("burden:legal-review",),
    framing_refs: tuple[str, ...] = ("frame:bounded-routing-audit",),
) -> CompressionMaterialSet:
    return CompressionMaterialSet(
        claims=claims,
        limitations=(
            limitations
            if limitations is not None
            else (_item("limitation:candidate-only", "Candidate-only result."),)
        ),
        denied_uses=(
            _item("denied-use:claim-authority", "claim_authority"),
            _item("denied-use:policy-recommendation", "policy_recommendation"),
        ),
        counterevidence=(
            _item("counterevidence:rejected-branch", "Rejected legal-advice branch."),
        ),
        governance_burden_refs=governance_burden_refs,
        framing_refs=framing_refs,
    )


def test_compression_dropping_retained_limitation_fails_closed() -> None:
    source = _baseline_material(
        limitations=(
            _item("limitation:candidate-only", "Candidate-only result."),
            _item("limitation:scope", "Applies only to the pinned G5 envelope."),
        )
    )
    candidate_summary = _baseline_material()

    receipt = build_compression_loss_receipt(
        receipt_id="compression-loss:retained-limitation-red",
        source_ref="layer3-g6://run/retained-limitation-red",
        summary_ref="layer3-g6://summary/retained-limitation-red",
        source_material=source,
        candidate_summary=candidate_summary,
        repo_root=REPO_ROOT,
    )

    assert receipt.status == "blocked"
    assert "compression_retained_limitation_dropped" in receipt.issue_codes
    assert receipt.emitted_summary is None
    assert receipt.terminal_result is not None
    assert receipt.terminal_result.result_kind == "governed_refusal"


def test_low_effective_independence_cannot_be_presented_as_broad_consensus() -> None:
    independence_map = build_evidence_independence_map(
        [_dependent_evidence_line(1), _dependent_evidence_line(2)],
        portfolio_designs=[_portfolio_design()],
        map_id="independence-map:compression-consensus-red",
        producer_execution_started_at="2026-08-19T09:00:00+00:00",
    )
    source_claim = CompressionClaimItem(
        item_id="claim:consensus",
        content="The selected evidence supports the bounded routing result.",
        claim_kind="substantive",
        presentation_scope="bounded",
        evidence_independence_ref=independence_map["map_id"],
    )
    summary_claim = source_claim.model_copy(
        update={"presentation_scope": "broad_consensus"}
    )

    receipt = build_compression_loss_receipt(
        receipt_id="compression-loss:consensus-red",
        source_ref="layer3-g6://run/consensus-red",
        summary_ref="layer3-g6://summary/consensus-red",
        source_material=_baseline_material(claims=(source_claim,)),
        candidate_summary=_baseline_material(claims=(summary_claim,)),
        evidence_independence_maps={independence_map["map_id"]: independence_map},
        repo_root=REPO_ROOT,
    )

    assert receipt.status == "blocked"
    assert "compression_broad_consensus_not_supported" in receipt.issue_codes
    assert receipt.emitted_summary is None


def test_framing_narrowing_governance_burden_without_delta_fails_closed() -> None:
    source = _baseline_material(
        governance_burden_refs=(
            "burden:public-consultation",
            "burden:legal-review",
        ),
        framing_refs=("frame:public-policy-choice",),
    )
    candidate_summary = _baseline_material(
        governance_burden_refs=("burden:legal-review",),
        framing_refs=("frame:technical-routing-choice",),
    )

    receipt = build_compression_loss_receipt(
        receipt_id="compression-loss:framing-red",
        source_ref="layer3-g6://run/framing-red",
        summary_ref="layer3-g6://summary/framing-red",
        source_material=source,
        candidate_summary=candidate_summary,
        repo_root=REPO_ROOT,
    )

    assert receipt.status == "blocked"
    assert (
        "compression_governance_burden_narrowed_without_delta"
        in receipt.issue_codes
    )
    assert receipt.emitted_summary is None
