"""Natural-language control-job publication facet."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from polisyos.core.artifacts import ArtifactTenantContextInfo

if TYPE_CHECKING:
    from collections.abc import Mapping
    from typing import Any

    from polisyos.runtime.http.services.control.generation_cycle import (
        CompiledRecursiveGenerationCycleRun,
    )

    from .job_nl_context import _ControlNLJobContext


def _n4_proposal_progress_with_budget(
    progress: Mapping[str, Any],
    recursive_budget_resolution: Mapping[str, Any],
) -> dict[str, Any]:
    """Attach the resolved but unapplied cycle budget to N4-only progress."""

    return {
        **progress,
        "recursive_budget_resolution": dict(recursive_budget_resolution),
        "recursive_budget_application_status": "not_applied_n4_proposal_only",
    }


class ControlNLJobPublicationMixin:
    """Publish the full recursive result after NL execution reaches this phase."""

    def _publish_control_nl_job(
        self,
        context: _ControlNLJobContext,
        compiled: CompiledRecursiveGenerationCycleRun,
    ) -> None:
        """Persist compiled, normative, Core, and terminal job artifacts."""
        job = context.job
        payload = context.payload
        execution_scope = context.execution_scope
        capability_manifest_ref = context.capability_manifest_ref
        recursive_budget_resolution = context.recursive_budget_resolution
        core_run_id = context.core_run_id
        core_run_context = context.core_run_context
        compiled_artifact_ref = self._put_json_artifact_ref(
            compiled.model_dump(mode="json"),
            kind="runtime.compiled_recursive_generation_cycle",
            schema_name="polisyos.runtime.CompiledRecursiveGenerationCycleRun",
            tenant_context=(
                ArtifactTenantContextInfo(
                    tenant_id=execution_scope.tenant_id,
                    cell_id=execution_scope.cell_id,
                )
                if execution_scope.status == "established" and execution_scope.tenant_id is not None
                else None
            ),
        )
        compiled_ref = str(compiled_artifact_ref.artifact_id)
        from polisyos.runtime.http.services.control.generation_cycle import (
            parse_normative_run_evidence,
        )

        normative_raw = (payload.get("context") or {}).get("normative_evidence")
        normative = self.resolve_generation_value_choices(
            compiled_run_ref=compiled_ref,
            evidence=parse_normative_run_evidence(normative_raw),
            evaluated_at=datetime.now(UTC),
            compiled_artifact_ref=compiled_artifact_ref,
        )
        refusal_reasons = tuple(
            receipt.reason
            for leaf in compiled.recursive_run.leaf_nodes
            if leaf.cycle_run is not None
            for receipt in (leaf.cycle_run.promotion_port,)
            if receipt.reason is not None
        )
        normative_artifact_ref = normative.persisted_artifact_ref
        if normative_artifact_ref is None:
            raise RuntimeError("normative_disposition_full_artifact_ref_missing")
        if core_run_context is None or core_run_id is None:
            raise RuntimeError("control_job_core_run_not_started_before_compute")
        core_manifest_ref = self._publish_generation_run(
            job=job,
            payload=payload,
            execution_scope=execution_scope,
            core_run_id=core_run_id,
            run_context=core_run_context,
            compiled_run_ref=compiled_artifact_ref,
            normative_disposition_ref=normative_artifact_ref,
        )
        core_progress = self._core_run_progress_fields(
            job=job,
            core_run_id=core_run_id,
            manifest_ref=core_manifest_ref,
        )
        from polisyos.runtime.http.services.control_plane_store import (
            ControlJobExecutionAdmissionError,
            ControlJobLeaseLostError,
        )
        from polisyos.runtime.quality.phase_barriers import (
            _execution_owner_binding_from_admission,
            _validated_execution_owner_binding,
        )
        from polisyos.runtime.quality.run_state import RunIntentBinding

        try:
            current_admission = self._control_store.current_execution_job_admission()
        except (ControlJobExecutionAdmissionError, ControlJobLeaseLostError) as exc:
            raise ControlJobLeaseLostError("control_job_terminal_admission_not_current") from exc
        expected_scope = {
            "tenant_id": execution_scope.tenant_id,
            "cell_id": execution_scope.cell_id,
        }
        current_owner_binding = _execution_owner_binding_from_admission(
            current_admission,
            expected_job_id=job.job_id,
            expected_run_id=str(job.run_id or ""),
            expected_effective_profile=job.effective_execution_profile,
            expected_scope=expected_scope,
        )
        original_admission = context.admission
        original_job = original_admission.job
        if (
            current_owner_binding is None
            or current_admission.attempt != original_admission.attempt
            or current_admission.job.lease_owner != original_job.lease_owner
            or current_admission.scope != execution_scope
        ):
            raise ControlJobLeaseLostError("control_job_terminal_owner_binding_not_current")
        current_progress = current_admission.job.progress
        persisted_owner_binding = _validated_execution_owner_binding(
            current_progress.get("execution_owner_binding"),
            expected=current_owner_binding,
        )
        if persisted_owner_binding != current_owner_binding:
            raise ControlJobLeaseLostError("control_job_terminal_progress_owner_binding_missing")
        progress = {
            "state": "completed",
            "phase": "natural_language_run",
            **core_progress,
            "manifest_ref": str(core_manifest_ref.artifact_id),
            "run_id": str(job.run_id or ""),
            "compiled_recursive_generation_cycle_ref": compiled_ref,
            "compiled_recursive_generation_cycle_artifact_ref": (
                compiled_artifact_ref.model_dump(mode="json")
            ),
            "recursive_budget_resolution": recursive_budget_resolution.model_dump(mode="json"),
            "normative_disposition_ref": normative.disposition_ref,
            "normative_disposition_artifact_ref": (normative_artifact_ref.model_dump(mode="json")),
            "normative_disposition": normative.model_dump(mode="json"),
            "promotion_refusal_reasons": list(refusal_reasons),
            "execution_owner_binding": persisted_owner_binding,
        }
        raw_intent_binding = current_progress.get("run_intent_binding")
        if isinstance(raw_intent_binding, dict):
            try:
                intent_binding = RunIntentBinding.model_validate(raw_intent_binding)
            except Exception:
                intent_binding = None
            if (
                intent_binding is not None
                and intent_binding.run_id == current_owner_binding["run_id"]
                and intent_binding.tenant_id == current_owner_binding["tenant_id"]
                and intent_binding.requested_profile
                == current_owner_binding["requested_execution_profile"]
            ):
                progress["run_intent_binding"] = intent_binding.model_dump(mode="json")
        for progress_key in (
            "runtime_quality_refs",
            "runtime_quality_artifact_refs",
            "runtime_quality_projection",
            "runtime_quality_diagnostic_events",
            "diagnostic_event_log_ref",
            "diagnostic_events",
            "trust_boundary_attestations",
        ):
            if progress_key in current_progress:
                progress[progress_key] = current_progress[progress_key]
        self._control_store.complete_job(
            job_id=job.job_id,
            run_id=str(job.run_id or ""),
            capability_manifest_ref=str(capability_manifest_ref),
            progress=progress,
        )
        self._emit_runtime_diagnostic_event(
            execution_scope=execution_scope,
            job_id=job.job_id,
            run_id=str(job.run_id or ""),
            execution_profile=job.effective_execution_profile,
            phase="job_execution",
            event_type="polisyos.runtime.diagnostic.phase_transition.v1",
            state_before="running",
            state_after="completed",
            payload=payload,
            event_payload={
                "job_kind": job.kind,
                "capability_manifest_ref": str(capability_manifest_ref),
                "compiled_recursive_generation_cycle_ref": compiled_ref,
                "recursive_budget_resolution": recursive_budget_resolution.model_dump(mode="json"),
                "normative_disposition_ref": normative.disposition_ref,
                "epoch_strangle_disposition": (
                    "candidate_only_typed_negative" if refusal_reasons else "candidate_only"
                ),
            },
            artifact_refs=[
                str(capability_manifest_ref),
                str(core_manifest_ref.artifact_id),
                compiled_ref,
                str(normative.disposition_ref),
            ],
        )
        return
