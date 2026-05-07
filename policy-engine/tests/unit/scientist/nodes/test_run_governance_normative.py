from __future__ import annotations

import logging
from unittest.mock import patch

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.ir.analytics.normative_arbitration import (
    ArbitrationOption,
    NormativeArbitrationResult,
    NormativeAuditStatus,
    NormativeModelCompleteness,
    OptionOutcomeMatrix,
    PolicyOutcome,
    RightsAuditEntry,
    TradeoffCertificate,
    persist_normative_arbitration_result,
)
from polisyos.ir.governance.problem_frame import NormativeArbitrationPolicy
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.engine.state_branching import branch_state as real_branch_state
from polisyos.scientist.governance.report import GovernanceReport
from polisyos.scientist.nodes.builtins.governance.run_governance import RunGovernanceNode
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_NORMATIVE_ARBITRATION_RESULT_REF,
    REPORT_GOVERNANCE_REPORT_REF,
)


def test_run_governance_rejects_on_explicit_normative_right_violation(tmp_path) -> None:
    report = _run_governance_with_normative_result(
        tmp_path=tmp_path,
        selected_option=ArbitrationOption.BASELINE,
        rights_status=NormativeAuditStatus.VIOLATED,
        model_source="declared",
        completeness=NormativeModelCompleteness.COMPLETE,
    )

    assert report.verdict == "reject"
    assert any(issue["code"] == "NORMATIVE_RIGHT_VIOLATION" for issue in report.issues)


def test_run_governance_marks_needs_revision_when_policy_prefers_baseline(tmp_path) -> None:
    report = _run_governance_with_normative_result(
        tmp_path=tmp_path,
        selected_option=ArbitrationOption.BASELINE,
        rights_status=NormativeAuditStatus.SATISFIED,
        model_source="declared",
        completeness=NormativeModelCompleteness.COMPLETE,
    )

    assert report.verdict == "needs_revision"
    assert any(issue["code"] == "NORMATIVE_POLICY_REJECTS_PROPOSAL" for issue in report.issues)


def test_run_governance_keeps_warning_only_for_partial_model_when_proposal_selected(
    tmp_path,
) -> None:
    report = _run_governance_with_normative_result(
        tmp_path=tmp_path,
        selected_option=ArbitrationOption.PROPOSAL,
        rights_status=NormativeAuditStatus.SATISFIED,
        model_source="legacy_synthesized",
        completeness=NormativeModelCompleteness.PARTIAL,
    )

    assert report.verdict == "approve"
    assert any(issue["code"] == "NORMATIVE_MODEL_PARTIAL" for issue in report.issues)


def test_run_governance_preserves_human_gate_precedence(tmp_path) -> None:
    report = _run_governance_with_normative_result(
        tmp_path=tmp_path,
        selected_option=ArbitrationOption.BASELINE,
        rights_status=NormativeAuditStatus.VIOLATED,
        model_source="declared",
        completeness=NormativeModelCompleteness.COMPLETE,
        require_human_gate=True,
    )

    assert report.verdict == "human_gate"


def test_run_governance_uses_branch_state_for_params_and_report(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    registry_bundle = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(
        store=store, registry_bundle=registry_bundle, run_id="R_governance_branch"
    )
    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger("test.governance.branch"))

    normative_ref = persist_normative_arbitration_result(
        store,
        NormativeArbitrationResult(
            model_completeness=NormativeModelCompleteness.COMPLETE,
            option_matrix=[
                OptionOutcomeMatrix(option=ArbitrationOption.BASELINE, binding_values={"a": 0.0}),
                OptionOutcomeMatrix(option=ArbitrationOption.PROPOSAL, binding_values={"a": 1.0}),
            ],
            per_stakeholder_utility=[],
            rights_audit=[],
            hard_constraint_audit=[],
            policy_outcomes=[
                PolicyOutcome(
                    policy=NormativeArbitrationPolicy.LEXICOGRAPHIC_RIGHTS,
                    selected_option=ArbitrationOption.PROPOSAL,
                    rationale="fixture",
                )
            ],
            selected_policy=NormativeArbitrationPolicy.LEXICOGRAPHIC_RIGHTS,
            selected_option=ArbitrationOption.PROPOSAL,
            tradeoff_certificate=TradeoffCertificate(
                selected_policy=NormativeArbitrationPolicy.LEXICOGRAPHIC_RIGHTS,
                selected_option=ArbitrationOption.PROPOSAL,
            ),
        ),
    )
    state = ExperimentState(
        run_id="R_governance_branch",
        artifacts_index={ARTIFACT_NORMATIVE_ARBITRATION_RESULT_REF: normative_ref},
        params={
            "governance_profile": {
                "level": "mvp",
                "pass_ids": ["normative_arbitration"],
                "thresholds": {},
                "short_circuit_on_blocker": True,
            },
            "nested": {"baseline": True},
        },
    )
    observed: dict[str, tuple[str, ...]] = {}

    def _spy_branch(base_state, *, write_paths=()):
        observed["write_paths"] = tuple(write_paths)
        return real_branch_state(base_state, write_paths=write_paths)

    with patch(
        "polisyos.scientist.nodes.builtins.governance.run_governance.branch_state",
        _spy_branch,
    ):
        outcome = RunGovernanceNode().execute(ctx, state)

    assert outcome.status == "ok"
    assert observed["write_paths"] == (
        "params",
        "params.validation_trace",
        "params.human_review_request",
        "params.human_review_request_ref",
        "artifacts_index.claims_ref",
        "reports_index.governance_report_ref",
    )
    assert REPORT_GOVERNANCE_REPORT_REF not in state.reports_index
    assert state.params["nested"] == {"baseline": True}
    assert REPORT_GOVERNANCE_REPORT_REF in outcome.state.reports_index
    assert "validation_trace" in outcome.state.params


def _run_governance_with_normative_result(
    *,
    tmp_path,
    selected_option: ArbitrationOption,
    rights_status: NormativeAuditStatus,
    model_source: str,
    completeness: NormativeModelCompleteness,
    require_human_gate: bool = False,
) -> GovernanceReport:
    store = FileSystemCAS(tmp_path)
    registry_bundle = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(store=store, registry_bundle=registry_bundle, run_id="R_governance")
    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger("test.governance"))

    normative_ref = persist_normative_arbitration_result(
        store,
        NormativeArbitrationResult(
            model_completeness=completeness,
            option_matrix=[
                OptionOutcomeMatrix(option=ArbitrationOption.BASELINE, binding_values={"a": 0.0}),
                OptionOutcomeMatrix(option=ArbitrationOption.PROPOSAL, binding_values={"a": 1.0}),
            ],
            per_stakeholder_utility=[],
            rights_audit=[
                RightsAuditEntry(
                    right_id="r1",
                    stakeholder_id="workers",
                    status=rights_status,
                    compare_to="delta",
                    operator=">=",
                    threshold=0,
                    observed_value=-1 if rights_status == NormativeAuditStatus.VIOLATED else 1,
                    notes=[],
                )
            ],
            hard_constraint_audit=[],
            policy_outcomes=[
                PolicyOutcome(
                    policy=NormativeArbitrationPolicy.LEXICOGRAPHIC_RIGHTS,
                    selected_option=selected_option,
                    rationale="fixture",
                )
            ],
            selected_policy=NormativeArbitrationPolicy.LEXICOGRAPHIC_RIGHTS,
            selected_option=selected_option,
            tradeoff_certificate=TradeoffCertificate(
                selected_policy=NormativeArbitrationPolicy.LEXICOGRAPHIC_RIGHTS,
                selected_option=selected_option,
            ),
            metadata={"model_source": model_source},
        ),
    )

    state = ExperimentState(
        run_id="R_governance",
        artifacts_index={ARTIFACT_NORMATIVE_ARBITRATION_RESULT_REF: normative_ref},
        params={
            "governance_profile": {
                "level": "mvp",
                "pass_ids": ["normative_arbitration"],
                "thresholds": {},
                "short_circuit_on_blocker": True,
            },
            "require_human_gate": require_human_gate,
        },
    )
    outcome = RunGovernanceNode().execute(ctx, state)
    report_ref = outcome.state.reports_index[REPORT_GOVERNANCE_REPORT_REF]
    payload = from_canonical_bytes(store.get_bytes(report_ref.artifact_id))
    return GovernanceReport.model_validate(payload)
