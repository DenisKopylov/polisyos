"""Currentness admission for persisted engine-owned governance reports.

Owner-profile loading proves the report bytes match a supported ABI. This module
adds the distinct source-currentness check used by runtime consumers: a successful
registered RunGovernance invocation must have emitted this exact selected report,
and the consumer state must still match the producer's declared read projection.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from polisyos.core.artifacts import ArtifactRef
from polisyos.core.artifacts.manifest import artifact_ref_identity_key
from polisyos.scientist.governance.report import (
    GovernanceReport,
    GovernanceReportInvocationBinding,
    load_governance_report_artifact,
)
from polisyos.scientist.nodes.builtins.state_keys import REPORT_GOVERNANCE_REPORT_REF
from polisyos.scientist.orchestration.engine.context import (
    ExecutionContext,
    _EngineInvocationBinding,
    _load_engine_owned_invocation_input_state,
)
from polisyos.scientist.orchestration.engine.producer_currentness import (
    resolve_engine_produced_artifact,
    state_read_projection,
)
from polisyos.scientist.orchestration.engine.state import ExperimentState

GovernanceReportCurrentness = Literal["current", "stale", "not_established", "invalid"]

# The runtime profile dynamically loads builtin and entry-point ValidatorPass
# implementations. Every selected pass receives these complete state maps, so a
# finite per-key list cannot establish the full input basis. Bump this identifier
# and its path tuple together whenever the supplied context or direct node reads
# change.
GOVERNANCE_REPORT_SOURCE_BASIS_ID = "governance-pass-context-v2"
GOVERNANCE_REPORT_SOURCE_READ_PATHS = (
    "run_id",
    "execution_profile",
    "inputs",
    "artifacts_index",
    "reports_index",
    "params",
    "policy_output_bundle_ref",
    "policy_brief_ref",
    "champion_policy_dossier_ref",
    "verified_policy_report_ref",
)


@dataclass(frozen=True)
class GovernanceReportAdmission:
    """Currentness outcome for one selected report reference."""

    status: GovernanceReportCurrentness
    report: GovernanceReport | None
    reason_code: str

    @property
    def is_current(self) -> bool:
        """Return whether this report is eligible as current runtime evidence."""
        return self.status == "current" and self.report is not None


def capture_governance_report_invocation_binding(
    ctx: ExecutionContext,
    state: ExperimentState,
) -> GovernanceReportInvocationBinding | None:
    """Capture the exact started engine attempt that is producing the report.

    Direct node calls remain supported as readable v1 candidate artifacts. If an
    engine binding is present but cannot be owner-verified, emission fails rather
    than silently downgrading an engine execution to an unbound report.
    """
    engine_binding = ctx._engine_invocation
    if engine_binding is None:
        return None
    if type(engine_binding) is not _EngineInvocationBinding:
        raise ValueError("governance_report_invocation_binding_invalid")

    expected_component = _run_governance_component_id()
    if (
        engine_binding.run_id != ctx.run.run_manifest.run_id
        or state.run_id != engine_binding.run_id
    ):
        raise ValueError("governance_report_invocation_run_mismatch")
    attempts = ctx.run.read_runtime_invocation_attempts()
    matches = [
        item
        for item in attempts
        if item.basis.attempt_id == engine_binding.attempt_id
        and item.basis_ref == engine_binding.basis_ref
    ]
    if len(matches) != 1:
        raise ValueError("governance_report_invocation_basis_not_owner_linked")
    attempt = matches[0]
    basis = attempt.basis
    if (
        basis.component_id != expected_component
        or attempt.outcome is not None
        or basis.run_id != state.run_id
    ):
        raise ValueError("governance_report_invocation_producer_mismatch")
    _load_engine_owned_invocation_input_state(ctx, state)
    return GovernanceReportInvocationBinding(
        run_id=basis.run_id,
        attempt_id=basis.attempt_id,
        attempt_basis_ref=attempt.basis_ref,
        workflow_spec_ref=basis.workflow_spec_ref,
        input_state_ref=basis.input_state_ref,
        node_alias=basis.node_alias,
        component_id=basis.component_id,
        source_basis_id=GOVERNANCE_REPORT_SOURCE_BASIS_ID,
    )


def resolve_current_governance_report(
    ctx: ExecutionContext,
    state: ExperimentState,
    selector: ArtifactRef | None = None,
) -> GovernanceReportAdmission:
    """Admit a report only when its exact successful producer and source remain current."""
    ref = selector or state.reports_index.get(REPORT_GOVERNANCE_REPORT_REF)
    if ref is None:
        return GovernanceReportAdmission("not_established", None, "governance_report_absent")
    selected_ref = state.reports_index.get(REPORT_GOVERNANCE_REPORT_REF)
    if selected_ref is None or artifact_ref_identity_key(selected_ref) != artifact_ref_identity_key(
        ref
    ):
        return GovernanceReportAdmission("stale", None, "governance_report_not_currently_selected")

    try:
        report = load_governance_report_artifact(ctx.store, ref)
    except Exception:
        return GovernanceReportAdmission("invalid", None, "governance_report_owner_profile_invalid")
    binding = report.invocation_binding
    if binding is None:
        return GovernanceReportAdmission(
            "not_established", report, "governance_report_source_unbound"
        )
    if ref.manifest_profile_sha256 is None:
        return GovernanceReportAdmission(
            "not_established", report, "governance_report_profile_not_established"
        )
    if binding.run_id != state.run_id or binding.run_id != ctx.run.run_manifest.run_id:
        return GovernanceReportAdmission("stale", report, "governance_report_run_mismatch")

    try:
        attempts = ctx.run.read_runtime_invocation_attempts()
        matches = [
            item
            for item in attempts
            if item.basis.attempt_id == binding.attempt_id
            and item.basis_ref == binding.attempt_basis_ref
        ]
        if len(matches) != 1:
            return GovernanceReportAdmission(
                "not_established", report, "governance_report_invocation_not_owner_linked"
            )
        attempt = matches[0]
        basis = attempt.basis
        outcome = attempt.outcome
        if (
            basis.run_id != binding.run_id
            or basis.workflow_spec_ref != binding.workflow_spec_ref
            or basis.input_state_ref != binding.input_state_ref
            or basis.node_alias != binding.node_alias
            or basis.component_id != binding.component_id
            or basis.component_id != _run_governance_component_id()
        ):
            return GovernanceReportAdmission(
                "invalid", report, "governance_report_invocation_mismatch"
            )
        if outcome is None or outcome.status != "ok" or outcome.outcome_state_ref is None:
            return GovernanceReportAdmission(
                "not_established", report, "governance_report_producer_not_successful"
            )
        if not any(
            artifact_ref_identity_key(output_ref) == artifact_ref_identity_key(ref)
            for output_ref in outcome.output_refs
        ):
            return GovernanceReportAdmission(
                "invalid", report, "governance_report_not_exact_producer_output"
            )
        if binding.source_basis_id != GOVERNANCE_REPORT_SOURCE_BASIS_ID:
            return GovernanceReportAdmission(
                "not_established", report, "governance_report_source_basis_unsupported"
            )
        from polisyos.scientist.nodes.builtins.governance.run_governance import RunGovernanceNode

        producer_admission = resolve_engine_produced_artifact(
            ctx,
            state,
            ref,
            expected_component_id=binding.component_id,
            expected_node_spec=RunGovernanceNode().spec,
            source_read_paths=GOVERNANCE_REPORT_SOURCE_READ_PATHS,
            expected_attempt_id=binding.attempt_id,
            expected_basis_ref=binding.attempt_basis_ref,
        )
        if not producer_admission.is_current:
            return GovernanceReportAdmission(
                producer_admission.status,
                report,
                producer_admission.reason_code,
            )
    except Exception:
        return GovernanceReportAdmission(
            "not_established", report, "governance_report_currentness_recomputation_failed"
        )
    return GovernanceReportAdmission("current", report, "governance_report_source_current")


def load_current_governance_report(
    ctx: ExecutionContext,
    state: ExperimentState,
    selector: ArtifactRef | None = None,
) -> GovernanceReport | None:
    """Return a report only when its currentness is established for this state."""
    admission = resolve_current_governance_report(ctx, state, selector)
    return admission.report if admission.is_current else None


def _run_governance_component_id() -> str:
    from polisyos.scientist.nodes.builtins.governance.run_governance import RunGovernanceNode

    return str(RunGovernanceNode().spec.metadata.component_id)


def _state_read_projection(
    producer_input: ExperimentState,
    producer_output: ExperimentState,
    current: ExperimentState,
    spec: object,
    *,
    read_paths: tuple[str, ...] = GOVERNANCE_REPORT_SOURCE_READ_PATHS,
) -> bool:
    """Compatibility wrapper for the shared full-map source projection."""
    return state_read_projection(
        producer_input,
        producer_output,
        current,
        spec,
        source_read_paths=read_paths,
    )


__all__ = [
    "GovernanceReportAdmission",
    "GovernanceReportCurrentness",
    "capture_governance_report_invocation_binding",
    "load_current_governance_report",
    "resolve_current_governance_report",
]
