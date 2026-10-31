"""Currentness admission for engine-produced verified policy reports."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from polisyos.core.artifacts.manifest import ArtifactRef, artifact_ref_identity_key
from polisyos.core.contracts.scientist import VerifiedPolicyReportRef
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.validation.policy_verified.models import (
    VerifiedPolicyReport,
    load_verified_policy_report,
)

VerifiedPolicyReportCurrentness = Literal["current", "stale", "not_established", "invalid"]
VERIFIED_POLICY_REPORT_SOURCE_BASIS_ID = "verified-policy-report-state-v2"
# BuildVerifiedPolicyReportNode receives the complete producer-visible maps. The
# explicit refs are separately declared because the node also reads them directly.
VERIFIED_POLICY_REPORT_SOURCE_READ_PATHS = (
    "run_id",
    "execution_profile",
    "inputs",
    "artifacts_index",
    "reports_index",
    "params",
    "policy_request_ref",
    "policy_option_set_ref",
    "source_verification_report_ref",
    "verified_policy_report_ref",
)


@dataclass(frozen=True)
class VerifiedPolicyReportAdmission:
    """Currentness result for a selected policy-verification report."""

    status: VerifiedPolicyReportCurrentness
    report: VerifiedPolicyReport | None
    artifact_ref: ArtifactRef | None
    reason_code: str

    @property
    def is_current(self) -> bool:
        """Return whether the report has an exact current producer receipt."""
        return self.status == "current" and self.report is not None


def resolve_current_verified_policy_report(
    ctx: ExecutionContext,
    state: ExperimentState,
    selector: ArtifactRef | None = None,
) -> VerifiedPolicyReportAdmission:
    """Resolve current policy-report evidence through its engine producer and source maps."""
    from polisyos.scientist.nodes.builtins.state_keys import (
        ARTIFACT_VERIFIED_POLICY_REPORT_REF,
    )

    selected_refs = [
        ref
        for ref in (
            state.verified_policy_report_ref,
            state.artifacts_index.get(ARTIFACT_VERIFIED_POLICY_REPORT_REF),
        )
        if ref is not None
    ]
    artifact_ref = selector or (selected_refs[0] if selected_refs else None)
    if artifact_ref is None:
        return VerifiedPolicyReportAdmission(
            "not_established", None, None, "verified_policy_report_absent"
        )
    key = artifact_ref_identity_key(artifact_ref)
    if not selected_refs or any(artifact_ref_identity_key(ref) != key for ref in selected_refs):
        return VerifiedPolicyReportAdmission(
            "stale", None, artifact_ref, "verified_policy_report_not_currently_selected"
        )

    try:
        report = load_verified_policy_report(
            ctx.store,
            VerifiedPolicyReportRef.model_validate(artifact_ref.model_dump(mode="json")),
        )
    except Exception:
        return VerifiedPolicyReportAdmission(
            "invalid", None, artifact_ref, "verified_policy_report_owner_profile_invalid"
        )

    if report.composition is not None:
        return _resolve_current_composition(ctx, state, artifact_ref, report)

    try:
        from polisyos.scientist.nodes.builtins.decide.build_verified_policy_report import (
            BuildVerifiedPolicyReportNode,
        )
        from polisyos.scientist.orchestration.engine.producer_currentness import (
            resolve_engine_produced_artifact,
        )

        spec = BuildVerifiedPolicyReportNode().spec
        producer = resolve_engine_produced_artifact(
            ctx,
            state,
            artifact_ref,
            expected_component_id=str(spec.metadata.component_id),
            expected_node_spec=spec,
            source_read_paths=VERIFIED_POLICY_REPORT_SOURCE_READ_PATHS,
        )
    except Exception:
        return VerifiedPolicyReportAdmission(
            "not_established", report, artifact_ref, "verified_policy_report_currentness_failed"
        )
    return VerifiedPolicyReportAdmission(
        producer.status,
        report,
        artifact_ref,
        producer.reason_code,
    )


def _resolve_current_composition(
    ctx: ExecutionContext,
    state: ExperimentState,
    artifact_ref: ArtifactRef,
    report: VerifiedPolicyReport,
) -> VerifiedPolicyReportAdmission:
    """Reconcile the completed owner occurrence and its live fixed source basis."""
    from polisyos.scientist.nodes.builtins.decide.build_verified_policy_report import (
        BuildVerifiedPolicyReportCompositionNode,
    )
    from polisyos.scientist.orchestration.engine.input_ports import (
        read_completed_verified_policy_composition,
    )
    from polisyos.scientist.orchestration.engine.producer_currentness import (
        resolve_engine_produced_artifact,
    )

    binding = report.composition
    assert binding is not None
    if binding.run_id != state.run_id:
        return VerifiedPolicyReportAdmission(
            "stale", report, artifact_ref, "verified_policy_composition_run_mismatch"
        )
    try:
        spec = BuildVerifiedPolicyReportCompositionNode().spec
        producer = resolve_engine_produced_artifact(
            ctx,
            state,
            artifact_ref,
            expected_component_id=str(spec.metadata.component_id),
            expected_node_spec=spec,
            source_read_paths=tuple(spec.state_reads),
            expected_basis_ref=binding.selected_attempt_ref,
        )
        if not producer.is_current:
            return VerifiedPolicyReportAdmission(
                producer.status, report, artifact_ref, producer.reason_code
            )
        facts = read_completed_verified_policy_composition(
            ctx,
            current_state=state,
            report_ref=artifact_ref,
            expected_attempt_ref=binding.selected_attempt_ref,
            expected_input_ref=binding.selected_input_ref,
        )
    except (AttributeError, KeyError, OSError, RuntimeError, TypeError, ValueError):
        return VerifiedPolicyReportAdmission(
            "not_established", report, artifact_ref, "verified_policy_composition_not_established"
        )
    if facts.status != "current":
        return VerifiedPolicyReportAdmission(
            facts.status,
            report,
            artifact_ref,
            "verified_policy_composition_sources_" + facts.status,
        )
    return VerifiedPolicyReportAdmission(
        "current", report, artifact_ref, "verified_policy_composition_source_current"
    )


__all__ = [
    "VERIFIED_POLICY_REPORT_SOURCE_BASIS_ID",
    "VERIFIED_POLICY_REPORT_SOURCE_READ_PATHS",
    "VerifiedPolicyReportAdmission",
    "VerifiedPolicyReportCurrentness",
    "resolve_current_verified_policy_report",
]
