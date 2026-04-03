"""Validate normative arbitration results and dissent/hard-constraint outcomes."""
from __future__ import annotations

from typing import List

from polisyos.core.contracts.lex import ComplianceIssue, IssueSeverity
from polisyos.core.governance.passes.base import PassContext, ValidatorPass
from polisyos.ir.analytics.normative_arbitration import (
    ArbitrationOption,
    NormativeArbitrationResult,
    NormativeAuditStatus,
    NormativeModelCompleteness,
    load_normative_arbitration_result,
)
from polisyos.ir.refs import NormativeArbitrationResultRef


class NormativeArbitrationPass(ValidatorPass):
    """Check that rights, hard constraints, and policy-vs-baseline arbitration cleared.

    The pass reads `normative_arbitration_result` directly or from
    `artifacts_index.normative_arbitration_result_ref` via `_store`. Missing
    results produce `NORMATIVE_RESULT_MISSING` warnings, explicit normative
    models can elevate rights/hard-constraint violations to blockers, and
    partial models, dissent, or proposal rejection remain warnings.
    """
    @property
    def pass_id(self) -> str:
        return "normative_arbitration"

    @property
    def estimated_cost_ms(self) -> int:
        return 20

    def validate(self, ctx: PassContext) -> List[ComplianceIssue]:
        if self.pass_id not in ctx.profile.pass_ids:
            return []

        result = self._resolve_result(ctx)
        if result is None:
            return [
                ComplianceIssue(
                    pass_id=self.pass_id,
                    path=["artifacts_index", "normative_arbitration_result_ref"],
                    message="Normative arbitration result is missing.",
                    severity=IssueSeverity.WARNING,
                    code="NORMATIVE_RESULT_MISSING",
                    suggestion="Run normative arbitration before governance verdicting.",
                )
            ]

        issues: list[ComplianceIssue] = []
        model_source = str(result.metadata.get("model_source", "declared"))
        explicit_model = model_source == "declared"

        rights_violations = [
            item
            for item in result.rights_audit
            if item.status == NormativeAuditStatus.VIOLATED and "soft_right" not in item.notes
        ]
        if rights_violations:
            severity = IssueSeverity.BLOCKER if explicit_model else IssueSeverity.WARNING
            issues.append(
                ComplianceIssue(
                    pass_id=self.pass_id,
                    path=["rights_audit"],
                    message=f"Normative rights violations detected: {len(rights_violations)}.",
                    severity=severity,
                    code="NORMATIVE_RIGHT_VIOLATION",
                    suggestion="Revise the proposal or narrow the affected stakeholder scope.",
                )
            )

        hard_constraint_violations = [
            item
            for item in result.hard_constraint_audit
            if item.status == NormativeAuditStatus.VIOLATED
        ]
        if hard_constraint_violations:
            severity = IssueSeverity.BLOCKER if explicit_model else IssueSeverity.WARNING
            issues.append(
                ComplianceIssue(
                    pass_id=self.pass_id,
                    path=["hard_constraint_audit"],
                    message=(
                        "Normative hard-constraint violations detected: "
                        f"{len(hard_constraint_violations)}."
                    ),
                    severity=severity,
                    code="NORMATIVE_HARD_CONSTRAINT_VIOLATION",
                    suggestion="Revise parameters until the referenced hard constraints pass.",
                )
            )

        if result.model_completeness == NormativeModelCompleteness.PARTIAL:
            issues.append(
                ComplianceIssue(
                    pass_id=self.pass_id,
                    path=["model_completeness"],
                    message="Normative model is partial; arbitration result is advisory.",
                    severity=IssueSeverity.WARNING,
                    code="NORMATIVE_MODEL_PARTIAL",
                    suggestion="Add explicit normative_frame bindings, utilities, and rights.",
                )
            )

        if result.residual_dissent:
            issues.append(
                ComplianceIssue(
                    pass_id=self.pass_id,
                    path=["residual_dissent"],
                    message=(
                        "Normative dissent remains across enabled arbitration policies: "
                        f"{len(result.residual_dissent)}."
                    ),
                    severity=IssueSeverity.WARNING,
                    code="NORMATIVE_DISSENT",
                    suggestion="Review the tradeoff certificate and document why the active policy wins.",
                )
            )

        if result.selected_option != ArbitrationOption.PROPOSAL:
            issues.append(
                ComplianceIssue(
                    pass_id=self.pass_id,
                    path=["selected_option"],
                    message=(
                        "Active normative policy does not currently support the proposal "
                        f"({result.selected_option.value})."
                    ),
                    severity=IssueSeverity.WARNING,
                    code="NORMATIVE_POLICY_REJECTS_PROPOSAL",
                    suggestion="Revise the policy or explicitly override via governance/human gate.",
                )
            )

        return issues

    @staticmethod
    def _resolve_result(ctx: PassContext) -> NormativeArbitrationResult | None:
        direct = ctx.state.get("normative_arbitration_result")
        if isinstance(direct, NormativeArbitrationResult):
            return direct
        if isinstance(direct, dict):
            try:
                return NormativeArbitrationResult.model_validate(direct)
            except Exception:
                return None

        artifacts_index = ctx.state.get("artifacts_index")
        store = ctx.state.get("_store")
        if not isinstance(artifacts_index, dict) or store is None:
            return None
        ref = artifacts_index.get("normative_arbitration_result_ref")
        if ref is None:
            return None
        try:
            return load_normative_arbitration_result(
                store,
                NormativeArbitrationResultRef(artifact_id=ref.artifact_id),
            )
        except Exception:
            return None


__all__ = ["NormativeArbitrationPass"]
