"""Real six-judge diagnostics capture their actual threshold and profile uses."""

from __future__ import annotations

import pytest

from polisyos.core.artifacts import FileSystemCAS
from polisyos.scientist.governance.report import GovernanceReport
from polisyos.scientist.methods.search.judge_threshold_basis import load_judge_threshold_basis
from polisyos.scientist.methods.search.judge_thresholds import JudgeThresholdRegistry
from polisyos.scientist.validation.policy_verified.models import (
    VerifiedLegalClaim,
    VerifiedPolicyReport,
)
from polisyos.scientist.validation.policy_verified.phase5_candidate import evaluate_phase5_candidate
from tests.unit.scientist.search.test_phase_b_policy_runtime import _candidate


@pytest.mark.parametrize("scenario", ["stable", "missing", "missing_entry", "drift"])
def test_real_judge_diagnostic_preserves_actual_threshold_uses_and_human_gate(
    tmp_path, monkeypatch, scenario: str
) -> None:
    from polisyos.scientist.methods.search.judge_stack import JudgeStack

    monkeypatch.setenv("POLISYOS_SEARCH_REGISTRY_ROOT", str(tmp_path / "registry"))
    registry = JudgeThresholdRegistry()
    if scenario != "missing":
        registry.record(registry.snapshot().entries[0])
    if scenario == "missing_entry":
        snapshot = registry.snapshot()
        registry._write_snapshot(
            snapshot.model_copy(
                update={
                    "entries": [
                        entry
                        for entry in snapshot.entries
                        if entry.metric_name != "statistical_uncertainty_level"
                    ]
                }
            )
        )
    if scenario == "drift":
        original = JudgeStack._statistical

        def mutate(stack, bundle):
            entry = registry.snapshot().entries[0]
            registry.record(
                entry.model_copy(update={"threshold_value": entry.threshold_value + 1}),
                allow_loosen=True,
                change_reason="synthetic drift control",
            )
            return original(stack, bundle)

        monkeypatch.setattr(JudgeStack, "_statistical", mutate)

    store = FileSystemCAS(tmp_path / "cas")
    result = evaluate_phase5_candidate(
        store,
        candidate=_candidate(),
        governance_report=GovernanceReport(verdict="human_gate"),
        run_id="synthetic-candidate-judges",
    )
    if scenario == "missing":
        assert result.reason == "phase5_threshold_registry_not_established"
        assert result.verdict is None and result.threshold_basis_ref is None
    elif scenario == "drift":
        assert result.reason == "phase5_threshold_registry_changed"
        assert result.verdict is None and result.threshold_basis_status == "stale"
        assert result.threshold_basis_ref is not None
    else:
        assert result.threshold_basis_status == "current_at_evaluation"
        assert result.threshold_basis_ref is not None
        assert load_judge_threshold_basis(store, result.threshold_basis_ref).snapshot.entries
        assert result.verdict is not None and len(result.verdict.per_judge) == 6
        assert result.verdict.composite_decision == "defer_to_human"
        assert any(
            card.failure_type == "human_gate_required" for card in result.verdict.blocking_failures
        )
        assert result.threshold_uses
        assert result.validation_profiles
        assert any(
            "human_review_required" in profile.pass_ids for profile in result.validation_profiles
        )
        if scenario == "missing_entry":
            assert result.reason is not None
            assert result.reason.startswith(
                "phase5_threshold_requirement_not_established:statistical:"
            )
            assert any(item.source == "missing" for item in result.threshold_uses)
        else:
            assert result.reason is None


def test_body_claims_reach_the_actual_citation_judge_without_invented_source(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setenv("POLISYOS_SEARCH_REGISTRY_ROOT", str(tmp_path / "registry"))
    registry = JudgeThresholdRegistry()
    registry.record(registry.snapshot().entries[0])
    claim = VerifiedLegalClaim(
        claim_id="synthetic-claim",
        bundle_id="synthetic-bundle",
        doc_id="synthetic-document",
        anchor="synthetic-anchor",
        claim_type="candidate",
        claim_text="Synthetic diagnostic text",
        quote="Synthetic diagnostic text",
    )
    body = VerifiedPolicyReport(
        request_id="synthetic",
        executive_summary="Synthetic candidate body",
        verified_legal_basis=[claim],
    )
    result = evaluate_phase5_candidate(
        FileSystemCAS(tmp_path / "cas"),
        candidate=_candidate(),
        governance_report=GovernanceReport(verdict="human_gate"),
        run_id="synthetic-body-claims",
        body=body,
    )
    assert result.verdict is not None
    reproducibility = result.verdict.per_judge["reproducibility"]
    assert any(card.failure_type == "CITATION_MISSING_REF" for card in reproducibility.warnings)
    assert result.verdict.composite_decision == "defer_to_human"
