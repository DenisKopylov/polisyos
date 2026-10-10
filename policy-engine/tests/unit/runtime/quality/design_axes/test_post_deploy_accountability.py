from __future__ import annotations

from polisyos.pdc import TypedDiagnosticRecord
from polisyos.runtime.quality.design_axes.post_deploy_accountability import (
    DivergenceRecord,
    build_s13_accountability_authority_boundary,
    classify_post_deploy_divergence,
    summarize_post_deploy_accountability,
)


def _divergence(
    *,
    divergence_id: str,
    attribution_status: str,
    attribution_class: str,
    action_item_status: str,
) -> DivergenceRecord:
    return classify_post_deploy_divergence(
        divergence_id=divergence_id,
        divergence_ref=f"pdc://accountability/{divergence_id}",
        case_id="case-mixed-post-deploy",
        deployment_dossier_ref="pdc://accountability/deployment-dossier",
        diagnostic=TypedDiagnosticRecord(
            diagnostic_id=f"diagnostic/{divergence_id}",
            code="post_deploy_outcome_divergence",
            severity="governance_required",
            message="The observed outcome differs from the monitored expectation.",
            authority_purpose="post_deploy_accountability_only_not_claim_authority",
            owner="post-deploy-review-owner",
            rule_version_ref="policyos.layer2.s13.post_deploy_accountability.v1",
        ),
        attribution_class=attribution_class,
        attribution_status=attribution_status,
        severity="governance_required",
        evidence_refs=[f"evidence://accountability/{divergence_id}"],
        attribution_owner=(
            "independent-review-owner" if attribution_status == "attributed" else None
        ),
        learning_eligible=attribution_status == "attributed",
        authority_boundary=build_s13_accountability_authority_boundary(),
        action_item_owner="post-deploy-review-owner",
        action_item_due_date="2026-12-01",
        action_item_status=action_item_status,
        action_item_closure_ref=(
            f"closure://accountability/{divergence_id}" if action_item_status == "closed" else None
        ),
    )


def test_mixed_attribution_summary_keeps_unattributable_work_out_of_learning() -> None:
    """The summary counts an owned unresolved divergence without calling it training."""

    attributed = _divergence(
        divergence_id="divergence/attributed-world-change",
        attribution_status="attributed",
        attribution_class="world_change",
        action_item_status="closed",
    )
    unattributable = _divergence(
        divergence_id="divergence/unattributable-implementation",
        attribution_status="unattributable",
        attribution_class="implementation_failure",
        action_item_status="open",
    )

    summary = summarize_post_deploy_accountability(
        divergences=(attributed, unattributable),
        case_count=1,
        summary_id="mixed-post-deploy-summary",
    )

    assert summary.unattributable_accountability_without_training_count == 1
    assert summary.action_item_closure_rate == 0.5
    assert summary.false_clear_counts["learning_without_attribution"] == 0
    assert "production_rollout_authority" in summary.authority_boundary.may_not_use_for
