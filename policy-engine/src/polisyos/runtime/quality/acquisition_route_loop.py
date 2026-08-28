"""Crash-safe orchestration owner for one costed acquisition route."""

from __future__ import annotations

import hashlib
from datetime import datetime
from typing import TYPE_CHECKING, Literal, Protocol

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from polisyos.core import canon
from polisyos.runtime.quality.acquisition_planner import (
    AcquisitionActionRecord,
    AcquisitionCostBasisRecord,
    AcquisitionPlannerReport,
    load_planner_acquisition_cost_schedule,
    produce_acquisition_cost_basis_record,
)
from polisyos.runtime.quality.design_problem import DesignProblem  # noqa: TC001
from polisyos.runtime.quality.generation_cycle import (  # noqa: TC001
    GenerationCycleRecord,
    GenerationCycleRun,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from polisyos.core.artifacts.protocol import ArtifactStore
    from polisyos.runtime.http.services.control_plane_store import ControlPlaneStore
    from polisyos.runtime.quality.event_log import RuntimeDiagnosticEventLog


class AcquisitionRouteClosureError(ValueError):
    """Typed fail-closed current-route resolution error."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class AcquisitionRouteRecoveryRequired(RuntimeError):  # noqa: N818 - exact lifecycle signal
    """Raised after the durable world-commit head requires re-entry recovery."""


class AcquisitionRoutePhaseReceipt(BaseModel):
    """Immutable phase fact for one exact acquisition action generation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["AcquisitionRoutePhaseReceipt@1.0"] = "AcquisitionRoutePhaseReceipt@1.0"
    receipt_id: str = Field(min_length=1)
    tenant_id: str = Field(min_length=1)
    cell_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    source_job_id: str = Field(min_length=1)
    route_id: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    action_generation: int = Field(ge=1)
    job_id: str = Field(min_length=1)
    compiled_ref: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    planner_report_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    cost_basis_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    decision_ref: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    coarse_phase: Literal["requested", "executing", "world_committed", "terminal"]
    receipt_phase: Literal[
        "requested",
        "executing",
        "world_committed_reentry_pending",
        "terminal",
    ]
    recovery_state: Literal["none", "reentry_recovery_required", "complete"]
    predecessor_receipt_ref: str | None = Field(
        default=None,
        pattern=r"^sha256:[0-9a-f]{64}$",
    )
    owner_receipt_refs: tuple[str, ...] = ()
    generated_at: AwareDatetime

    @model_validator(mode="after")
    def _validate_phase_truth(self) -> AcquisitionRoutePhaseReceipt:
        expected = {
            "requested": ("requested", "none"),
            "executing": ("executing", "none"),
            "world_committed_reentry_pending": (
                "world_committed",
                "reentry_recovery_required",
            ),
            "terminal": ("terminal", "complete"),
        }[self.receipt_phase]
        if (self.coarse_phase, self.recovery_state) != expected:
            raise ValueError("acquisition_route_phase_state_mismatch")
        if self.receipt_phase == "requested" and self.predecessor_receipt_ref is not None:
            raise ValueError("requested_phase_cannot_have_predecessor")
        if self.receipt_phase != "requested" and self.predecessor_receipt_ref is None:
            raise ValueError("acquisition_route_phase_predecessor_missing")
        if self.receipt_phase == "world_committed_reentry_pending" and not self.owner_receipt_refs:
            raise ValueError("world_commit_owner_receipt_missing")
        return self


class AcquisitionRoutePhaseHead(Protocol):
    """Read-back fields required from one durable acquisition phase head."""

    receipt_ref: str
    receipt_phase: str
    recovery_state: str


class AcquisitionRoutePhaseSink(Protocol):
    """Persistence surface required by the crash-safe re-entry helpers."""

    def persist_phase(
        self,
        receipt: AcquisitionRoutePhaseReceipt,
    ) -> AcquisitionRoutePhaseHead: ...

    def get_head(
        self,
        receipt: AcquisitionRoutePhaseReceipt,
    ) -> AcquisitionRoutePhaseHead | None: ...


class VerifiedAcquisitionRouteClosure(BaseModel):
    """Content-bound source job, problem, planner, and cost closure."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    tenant_id: str = Field(min_length=1)
    cell_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    source_job_id: str = Field(min_length=1)
    source_payload_ref: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    capability_manifest_ref: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    compiled_ref: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    compiled_content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    terminal_event_id: str = Field(min_length=1)
    design_problem_ref: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    design_problem: DesignProblem
    generation_run: GenerationCycleRun
    source_cycle: GenerationCycleRecord
    planner_report: AcquisitionPlannerReport
    planner_record: AcquisitionActionRecord
    cost_basis_record: AcquisitionCostBasisRecord
    cost_basis_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    route_id: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class AcquisitionRouteLoop:
    """Resolve verified closures and own acquisition phase orchestration."""

    def __init__(
        self,
        *,
        control_store: ControlPlaneStore,
        artifact_store: ArtifactStore,
        event_log: RuntimeDiagnosticEventLog,
        tenant_id: str,
        cell_id: str,
    ) -> None:
        if not tenant_id.strip() or not cell_id.strip():
            raise ValueError("acquisition route loop requires tenant and cell")
        for capability in ("has", "get_bytes", "get_manifest"):
            if not callable(getattr(artifact_store, capability, None)):
                raise TypeError("acquisition route loop requires guarded CAS read capabilities")
        self._control_store = control_store
        self._artifact_store = artifact_store
        self._event_log = event_log
        self._tenant_id = tenant_id
        self._cell_id = cell_id

    def resolve_current_route(self, *, run_id: str) -> VerifiedAcquisitionRouteClosure:
        """Resolve the sole completed natural-language costed source closure."""

        try:
            job = self._control_store.get_unique_completed_job_by_run_and_kind(
                run_id=run_id,
                kind="natural_language_run",
            )
        except ValueError as exc:
            raise AcquisitionRouteClosureError("source_job_ambiguous") from exc
        if job is None:
            raise AcquisitionRouteClosureError("source_job_not_completed")
        if job.run_id != run_id or job.state != "completed":
            raise AcquisitionRouteClosureError("source_job_not_completed")
        payload_ref = job.payload_ref
        manifest_ref = job.capability_manifest_ref
        if payload_ref is None or manifest_ref is None:
            raise AcquisitionRouteClosureError("source_job_owner_refs_missing")
        payload = self._read_json_artifact(
            payload_ref,
            expected_kind="runtime.control_job_payload.natural_language_run",
            expected_schema_name="polisyos.runtime.ControlJobPayload",
        )
        if not isinstance(payload, dict) or (
            payload.get("tenant_id") != self._tenant_id
            or payload.get("cell_id") != self._cell_id
            or payload.get("run_id") != run_id
        ):
            raise AcquisitionRouteClosureError("source_job_actor_scope_mismatch")
        if not self._artifact_store.has(manifest_ref):
            raise AcquisitionRouteClosureError("source_manifest_missing")
        progress = job.progress
        compiled_ref = progress.get("compiled_recursive_generation_cycle_ref")
        if (
            progress.get("state") != "completed"
            or progress.get("phase") != "natural_language_run"
            or progress.get("run_id") != run_id
            or not isinstance(compiled_ref, str)
        ):
            raise AcquisitionRouteClosureError("source_progress_incomplete")
        terminal_event_id = self._resolve_terminal_event(
            run_id=run_id,
            job_id=job.job_id,
            compiled_ref=compiled_ref,
            manifest_ref=manifest_ref,
        )
        compiled_payload = self._read_json_artifact(
            compiled_ref,
            expected_kind="runtime.compiled_recursive_generation_cycle",
            expected_schema_name="polisyos.runtime.CompiledRecursiveGenerationCycleRun",
        )
        from polisyos.runtime.http.services.control.generation_cycle import (
            COMPILED_RECURSIVE_GENERATION_CYCLE_SCHEMA_VERSION,
            CompiledRecursiveGenerationCycleRun,
        )

        try:
            compiled = CompiledRecursiveGenerationCycleRun.model_validate(compiled_payload)
        except (TypeError, ValueError) as exc:
            raise AcquisitionRouteClosureError("compiled_run_invalid") from exc
        if compiled.schema_version != COMPILED_RECURSIVE_GENERATION_CYCLE_SCHEMA_VERSION:
            raise AcquisitionRouteClosureError("compiled_run_schema_mismatch")
        costed = [
            (leaf.cycle_run, cycle)
            for leaf in compiled.recursive_run.leaf_nodes
            if leaf.cycle_run is not None
            for cycle in leaf.cycle_run.cycles
            if cycle.acquisition_routing_report is not None
            and cycle.acquisition_cost_basis_record is not None
        ]
        if len(costed) != 1:
            raise AcquisitionRouteClosureError("costed_route_not_unique")
        generation_run, source_cycle = costed[0]
        report = source_cycle.acquisition_routing_report
        cost = source_cycle.acquisition_cost_basis_record
        if report is None or cost is None or len(report.acquisition_records) != 1:
            raise AcquisitionRouteClosureError("costed_route_not_unique")
        planner_record = report.acquisition_records[0]
        schedule = load_planner_acquisition_cost_schedule()
        recomputed = produce_acquisition_cost_basis_record(
            missing_distribution=cost.missing_distribution,
            strategy=planner_record.recommended_strategy,
            schedule=schedule,
        )
        if (
            recomputed is None
            or recomputed != cost
            or source_cycle.acquisition_cost_basis_hash != cost.record_content_hash
            or cost.schedule_content_hash != schedule.schedule_content_hash
        ):
            raise AcquisitionRouteClosureError("cost_basis_revalidation_required")
        route_id = _content_hash(
            {
                "tenant_id": self._tenant_id,
                "cell_id": self._cell_id,
                "run_id": run_id,
                "source_job_id": job.job_id,
                "compiled_ref": compiled_ref,
                "design_problem_ref": compiled.design_problem_ref,
                "planner_run_id": report.run_id,
                "planner_record_id": planner_record.acquisition_id,
                "cost_basis_hash": cost.record_content_hash,
            }
        )
        return VerifiedAcquisitionRouteClosure(
            tenant_id=self._tenant_id,
            cell_id=self._cell_id,
            run_id=run_id,
            source_job_id=job.job_id,
            source_payload_ref=payload_ref,
            capability_manifest_ref=manifest_ref,
            compiled_ref=compiled_ref,
            compiled_content_hash=compiled.content_hash,
            terminal_event_id=terminal_event_id,
            design_problem_ref=compiled.design_problem_ref,
            design_problem=compiled.design_problem,
            generation_run=generation_run,
            source_cycle=source_cycle,
            planner_report=report,
            planner_record=planner_record,
            cost_basis_record=cost,
            cost_basis_hash=cost.record_content_hash,
            route_id=route_id,
        )

    def _resolve_terminal_event(
        self,
        *,
        run_id: str,
        job_id: str,
        compiled_ref: str,
        manifest_ref: str,
    ) -> str:
        matches = [
            row.event
            for row in self._event_log.list_events(run_id=run_id, job_id=job_id)
            if row.event.event_type == "polisyos.runtime.diagnostic.phase_transition.v1"
            and row.event.phase == "job_execution"
            and row.event.state_before == "running"
            and row.event.state_after == "completed"
            and row.event.tenant_id == self._tenant_id
            and row.event.cell_id == self._cell_id
            and compiled_ref in row.event.artifact_refs
            and manifest_ref in row.event.artifact_refs
        ]
        if not matches:
            raise AcquisitionRouteClosureError("source_terminal_event_missing")
        if len(matches) != 1:
            raise AcquisitionRouteClosureError("source_terminal_event_ambiguous")
        return matches[0].event_id

    def _read_json_artifact(
        self,
        ref: str,
        *,
        expected_kind: str,
        expected_schema_name: str,
    ) -> object:
        try:
            if not self._artifact_store.has(ref):
                raise ValueError("artifact missing")
            blob = self._artifact_store.get_bytes(ref)
            if ref != f"sha256:{hashlib.sha256(blob).hexdigest()}":
                raise ValueError("artifact content mismatch")
            manifest = self._artifact_store.get_manifest(ref)
            schema = manifest.artifact_schema
            if (
                manifest.kind != expected_kind
                or schema is None
                or schema.name != expected_schema_name
                or schema.version != "1.0"
            ):
                raise ValueError("artifact manifest mismatch")
            return canon.from_canonical_bytes(blob)
        except Exception as exc:
            raise AcquisitionRouteClosureError("source_artifact_unverified") from exc


def _content_hash(payload: object) -> str:
    return f"sha256:{canon.content_hash(canon.to_canonical_bytes(payload, canon.CanonSpec()))}"


def persist_world_commit_and_reenter(
    *,
    sink: AcquisitionRoutePhaseSink,
    pending_receipt: AcquisitionRoutePhaseReceipt,
    reentry: Callable[[], str],
) -> AcquisitionRoutePhaseHead:
    """Persist/read back the recovery head before attempting direct re-entry."""

    if pending_receipt.receipt_phase != "world_committed_reentry_pending":
        raise ValueError("world_commit_pending_receipt_required")
    pending_head = sink.persist_phase(pending_receipt)
    if (
        pending_head.receipt_phase != "world_committed_reentry_pending"
        or sink.get_head(pending_receipt) != pending_head
    ):
        raise RuntimeError("world_commit_pending_head_readback_failed")
    try:
        reentry_ref = reentry()
    except Exception as exc:
        raise AcquisitionRouteRecoveryRequired("reentry_recovery_required") from exc
    return _persist_terminal_after_reentry(
        sink=sink,
        pending_receipt=pending_receipt,
        pending_receipt_ref=pending_head.receipt_ref,
        reentry_ref=reentry_ref,
    )


def resume_world_committed_reentry(
    *,
    sink: AcquisitionRoutePhaseSink,
    pending_receipt: AcquisitionRoutePhaseReceipt,
    reentry: Callable[[], str],
) -> AcquisitionRoutePhaseHead:
    """Resume only re-entry from an exact durable world-committed head."""

    pending_head = sink.get_head(pending_receipt)
    if (
        pending_head is None
        or pending_head.receipt_phase != "world_committed_reentry_pending"
        or pending_head.recovery_state != "reentry_recovery_required"
    ):
        raise AcquisitionRouteRecoveryRequired("reentry_recovery_head_missing")
    try:
        reentry_ref = reentry()
    except Exception as exc:
        raise AcquisitionRouteRecoveryRequired("reentry_recovery_required") from exc
    return _persist_terminal_after_reentry(
        sink=sink,
        pending_receipt=pending_receipt,
        pending_receipt_ref=pending_head.receipt_ref,
        reentry_ref=reentry_ref,
    )


def _persist_terminal_after_reentry(
    *,
    sink: AcquisitionRoutePhaseSink,
    pending_receipt: AcquisitionRoutePhaseReceipt,
    pending_receipt_ref: str,
    reentry_ref: str,
) -> AcquisitionRoutePhaseHead:
    if not isinstance(reentry_ref, str) or not reentry_ref.startswith("sha256:"):
        raise AcquisitionRouteRecoveryRequired("reentry_receipt_invalid")
    terminal = pending_receipt.model_copy(
        update={
            "receipt_id": f"{pending_receipt.receipt_id}.terminal",
            "coarse_phase": "terminal",
            "receipt_phase": "terminal",
            "recovery_state": "complete",
            "predecessor_receipt_ref": pending_receipt_ref,
            "owner_receipt_refs": (*pending_receipt.owner_receipt_refs, reentry_ref),
            "generated_at": datetime.now(pending_receipt.generated_at.tzinfo),
        }
    )
    return sink.persist_phase(AcquisitionRoutePhaseReceipt.model_validate(terminal))


__all__ = [
    "AcquisitionRouteClosureError",
    "AcquisitionRouteLoop",
    "AcquisitionRoutePhaseReceipt",
    "AcquisitionRouteRecoveryRequired",
    "VerifiedAcquisitionRouteClosure",
    "persist_world_commit_and_reenter",
    "resume_world_committed_reentry",
]
