"""Crash-safe orchestration owner for one costed acquisition route."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from datetime import datetime
from typing import TYPE_CHECKING, Literal, Protocol

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from polisyos.core import canon
from polisyos.core.artifacts import ArtifactID, ArtifactRef, load_core_json_artifact
from polisyos.data_requirement import DataRequirementCompilationReport
from polisyos.runtime.quality.acquisition_evaluation import AcquisitionSelectedEvaluation
from polisyos.runtime.quality.acquisition_planner import (
    _N7_SOURCE_JOIN_RULE,
    AcquisitionActionRecord,
    AcquisitionCostBasisRecord,
    AcquisitionPlannerReport,
    AcquisitionRequirementGap,
    load_planner_acquisition_cost_schedule,
    produce_acquisition_cost_basis_record,
    validate_persisted_acquisition_planner_report,
)
from polisyos.runtime.quality.design_problem import DesignProblem
from polisyos.runtime.quality.generation_cycle import (
    AcquisitionOverlayReentryReceipt,
    GenerationCycleRecord,
    GenerationCycleRun,
    _cycle_acquisition_requirement,
    _cycle_basis_ref,
    _n7_cycle_source_gap,
    _n7_joined_planner_records_match,
    _problem_ref,
    generation_cycle_run_content_hash,
    validate_acquisition_overlay_continuation,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from polisyos.runtime.http.services.adapters.core_run import TerminalCoreRunSource
    from polisyos.runtime.http.services.control_plane_store import (
        ControlJobRecord,
        ControlPlaneStore,
    )
    from polisyos.runtime.quality.event_log import RuntimeDiagnosticEventLog


class _ArtifactSchema(Protocol):
    name: str
    version: str


class _ArtifactProducer(Protocol):
    component: str


class _ArtifactManifest(Protocol):
    kind: str
    artifact_schema: _ArtifactSchema | None
    producer: _ArtifactProducer | None


class _ArtifactStore(Protocol):
    def has(self, artifact_id: ArtifactID | ArtifactRef) -> bool: ...

    def get_bytes(self, artifact_id: ArtifactID | ArtifactRef) -> bytes: ...

    def get_manifest(self, artifact_id: ArtifactID | ArtifactRef) -> _ArtifactManifest: ...


class AcquisitionRouteClosureError(ValueError):
    """Typed fail-closed current-route resolution error."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _select_source_planner_record(
    report: AcquisitionPlannerReport,
    source: AcquisitionRequirementGap | None,
) -> AcquisitionActionRecord:
    """Select one joined source action without dropping other compiler gaps."""
    records = report.acquisition_records
    if len(records) == 1:
        return records[0]
    if source is None:
        raise AcquisitionRouteClosureError("costed_route_not_unique")
    selected = tuple(
        record
        for record in records
        if record.requirement_gap_ref == source.requirement_gap_id
        and record.requirement_schema_version == source.requirement_schema_version
        and record.gap_type == source.gap_type
        and record.compiled_requirement_ref != source.compiled_requirement_ref
    )
    if len(selected) != 1:
        raise AcquisitionRouteClosureError("costed_route_not_unique")
    return selected[0]


class AcquisitionRouteRecoveryRequired(RuntimeError):  # noqa: N818 - exact lifecycle signal
    """Raised after the durable world-commit head requires re-entry recovery."""


def _resolve_source_cycle_problem_basis(
    *,
    generation_run: GenerationCycleRun,
    source_cycle: GenerationCycleRecord,
    design_problem: DesignProblem,
    design_problem_ref: str,
    acquisition_basis_transitions: tuple[AcquisitionOverlayReentryReceipt, ...] = (),
) -> DesignProblem:
    """Compose verified source refreshes separately from actual design revisions.

    The route owner's action fold supplies the acquisition proofs only after
    selected CAS, event, action and append-only continuation replay. A receipt
    object or same-basis declaration supplied by a caller is not admission;
    mutation consumers must obtain this closure from that live owner again.
    """

    if (
        _problem_ref(design_problem) != design_problem_ref
        or generation_run.design_problem_ref != design_problem_ref
    ):
        raise AcquisitionRouteClosureError("source_cycle_subject_binding_mismatch")
    indexes = tuple(cycle.cycle_index for cycle in generation_run.cycles)
    if len(indexes) != len(set(indexes)):
        raise AcquisitionRouteClosureError("source_cycle_basis_chain_invalid")
    matching_source = tuple(
        cycle for cycle in generation_run.cycles if cycle.cycle_index == source_cycle.cycle_index
    )
    if matching_source != (source_cycle,):
        raise AcquisitionRouteClosureError("source_cycle_not_in_generation_run")
    prefix = tuple(
        sorted(
            (
                cycle
                for cycle in generation_run.cycles
                if cycle.cycle_index <= source_cycle.cycle_index
            ),
            key=lambda cycle: cycle.cycle_index,
        )
    )
    if tuple(cycle.cycle_index for cycle in prefix) != tuple(range(source_cycle.cycle_index + 1)):
        raise AcquisitionRouteClosureError("source_cycle_basis_predecessor_missing")

    transitions: dict[int, AcquisitionOverlayReentryReceipt] = {}
    for transition in acquisition_basis_transitions:
        index = transition.new_cycle.cycle_index
        continued = transition.continued_generation_run
        if (
            index in transitions
            or not transition.schema_version.endswith(".v3")
            or transition.source_cycle_index + 1 != index
            or transition.design_problem_ref != design_problem_ref
            or continued is None
            or continued.run_id != generation_run.run_id
            or continued.cycles != generation_run.cycles[: index + 1]
            or transition.new_cycle != continued.cycles[-1]
        ):
            raise AcquisitionRouteClosureError("source_acquisition_basis_transition_invalid")
        transitions[index] = transition
    expected_basis = design_problem
    for cycle in prefix:
        if cycle.design_problem_ref != design_problem_ref or _cycle_basis_ref(
            cycle
        ) != _problem_ref(expected_basis):
            raise AcquisitionRouteClosureError("source_cycle_basis_chain_invalid")
        if cycle.cycle_index == source_cycle.cycle_index:
            return expected_basis
        transition = transitions.get(cycle.cycle_index + 1)
        if transition is None:
            expected_basis = cycle.revision_request.revised_problem
        elif transition.source_candidate_ref != cycle.selected_candidate_ref or _cycle_basis_ref(
            transition.new_cycle
        ) != _problem_ref(expected_basis):
            raise AcquisitionRouteClosureError("source_acquisition_basis_transition_invalid")
    raise AcquisitionRouteClosureError("source_cycle_basis_unresolved")


class AcquisitionRoutePhaseReceipt(BaseModel):
    """Immutable phase fact for one exact acquisition action generation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[
        "AcquisitionRoutePhaseReceipt@1.0", "AcquisitionRoutePhaseReceipt@1.1"
    ] = "AcquisitionRoutePhaseReceipt@1.0"
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
    coarse_phase: Literal["requested", "executing", "world_committed"]
    receipt_phase: Literal[
        "requested",
        "executing",
        "outcome_selected",
        "world_committed_reentry_pending",
    ]
    recovery_state: Literal["none", "reentry_recovery_required"]
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
            "outcome_selected": ("executing", "none"),
            "world_committed_reentry_pending": (
                "world_committed",
                "reentry_recovery_required",
            ),
        }[self.receipt_phase]
        if (self.coarse_phase, self.recovery_state) != expected:
            raise ValueError("acquisition_route_phase_state_mismatch")
        if self.receipt_phase == "requested" and self.predecessor_receipt_ref is not None:
            raise ValueError("requested_phase_cannot_have_predecessor")
        if self.receipt_phase != "requested" and self.predecessor_receipt_ref is None:
            raise ValueError("acquisition_route_phase_predecessor_missing")
        if self.receipt_phase == "outcome_selected":
            if (
                self.schema_version != "AcquisitionRoutePhaseReceipt@1.1"
                or len(self.owner_receipt_refs) != 1
            ):
                raise ValueError("acquisition_action_selection_binding_invalid")
        elif self.schema_version != "AcquisitionRoutePhaseReceipt@1.0":
            raise ValueError("acquisition_route_phase_schema_version_mismatch")
        if self.receipt_phase == "world_committed_reentry_pending" and not self.owner_receipt_refs:
            raise ValueError("world_commit_owner_receipt_missing")
        return self


class AcquisitionRouteLoopReceipt(BaseModel):
    """Immutable terminal fact for one exact acquisition action generation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["AcquisitionRouteLoopReceipt@1.0"] = "AcquisitionRouteLoopReceipt@1.0"
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
    coarse_phase: Literal["terminal"] = "terminal"
    receipt_phase: Literal["terminal"] = "terminal"
    recovery_state: Literal["complete"] = "complete"
    terminal_outcome: Literal["quarantined_no_growth", "reentry_completed"]
    predecessor_receipt_ref: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    owner_receipt_refs: tuple[str, ...] = Field(min_length=1)
    reentry_receipt_ref: str | None = Field(
        default=None,
        pattern=r"^sha256:[0-9a-f]{64}$",
    )
    generated_at: AwareDatetime

    @model_validator(mode="after")
    def _validate_terminal_truth(self) -> AcquisitionRouteLoopReceipt:
        if self.terminal_outcome == "reentry_completed":
            if self.reentry_receipt_ref is None:
                raise ValueError("terminal_reentry_receipt_missing")
        elif self.reentry_receipt_ref is not None:
            raise ValueError("quarantined_terminal_cannot_claim_reentry")
        return self


class AcquisitionRouteLoopReceiptV2(BaseModel):
    """Versioned terminal separating source admission from selected evaluation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["AcquisitionRouteLoopReceipt@2.0"] = "AcquisitionRouteLoopReceipt@2.0"
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
    coarse_phase: Literal["terminal"] = "terminal"
    receipt_phase: Literal["terminal"] = "terminal"
    recovery_state: Literal["complete"] = "complete"
    terminal_outcome: Literal[
        "quarantined_no_growth", "reentry_completed", "source_admitted_evaluation_retained"
    ]
    predecessor_receipt_ref: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    owner_receipt_refs: tuple[str, ...] = Field(min_length=1)
    reentry_receipt_ref: str | None = Field(
        default=None,
        pattern=r"^sha256:[0-9a-f]{64}$",
    )
    evaluation_decision_ref: ArtifactRef
    selected_basis_ref: ArtifactRef
    selected_evaluation_witness_ref: ArtifactRef
    selected_evaluation: AcquisitionSelectedEvaluation | None = None
    current_continuation_ref: ArtifactRef | None = None
    generated_at: AwareDatetime

    @model_validator(mode="after")
    def _validate_terminal_truth(self) -> AcquisitionRouteLoopReceiptV2:
        if self.terminal_outcome == "reentry_completed":
            if self.reentry_receipt_ref is None or self.current_continuation_ref is not None:
                raise ValueError("terminal_reentry_receipt_missing_or_retained_continuation")
        elif self.reentry_receipt_ref is not None:
            raise ValueError("terminal_cannot_claim_new_reentry")
        if self.terminal_outcome == "source_admitted_evaluation_retained" and (
            self.selected_evaluation is None
            or self.selected_evaluation.basis_ref is None
            or self.current_continuation_ref is None
            or self.selected_evaluation.basis_ref != self.selected_basis_ref
            or self.selected_evaluation.n5_execution_ref != self.selected_evaluation_witness_ref
        ):
            raise ValueError("terminal_retained_evaluation_incomplete")
        for ref, kind in (
            (self.evaluation_decision_ref, "runtime_quality.acquisition_evaluation_decision"),
            (self.selected_basis_ref, "runtime_quality.acquisition_evaluation_basis"),
        ):
            if (
                ref.kind != kind
                or ref.media_type != "application/json"
                or (ref.manifest_profile_sha256 is None)
            ):
                raise ValueError("terminal_evaluation_selected_profile_missing")
        if self.selected_evaluation_witness_ref.manifest_profile_sha256 is None:
            raise ValueError("terminal_evaluation_witness_profile_missing")
        return self


def parse_acquisition_route_loop_receipt(
    value: object,
) -> AcquisitionRouteLoopReceipt | AcquisitionRouteLoopReceiptV2:
    """Select the exact versioned reader; legacy serialized meaning is unchanged."""
    if isinstance(value, (AcquisitionRouteLoopReceipt, AcquisitionRouteLoopReceiptV2)):
        value = value.model_dump(mode="python")
    if not isinstance(value, dict):
        raise ValueError("acquisition_terminal_payload_not_mapping")
    if value.get("schema_version") == "AcquisitionRouteLoopReceipt@2.0":
        return AcquisitionRouteLoopReceiptV2.model_validate(value)
    return AcquisitionRouteLoopReceipt.model_validate(value)


AcquisitionTerminalReceipt = AcquisitionRouteLoopReceipt | AcquisitionRouteLoopReceiptV2


class AcquisitionRoutePhaseHead(Protocol):
    """Read-back fields required from one durable acquisition phase head."""

    receipt_ref: str
    receipt_phase: str
    recovery_state: str


class AcquisitionRoutePhaseSink(Protocol):
    """Persistence surface required by the crash-safe route helpers."""

    def persist_phase(
        self,
        receipt: AcquisitionRoutePhaseReceipt,
    ) -> AcquisitionRoutePhaseHead: ...

    def persist_terminal(
        self,
        receipt: AcquisitionTerminalReceipt,
    ) -> AcquisitionRoutePhaseHead: ...

    def get_head(
        self,
        receipt: AcquisitionRoutePhaseReceipt,
    ) -> AcquisitionRoutePhaseHead | None: ...


class CompletedControlJobCoreSourceResolver(Protocol):
    """HTTP-composed port for exact completed-job to Core-attempt source intake."""

    def __call__(
        self,
        job: ControlJobRecord,
        *,
        expected_control_run_id: str,
        tenant_id: str,
        cell_id: str,
    ) -> TerminalCoreRunSource: ...


class VerifiedAcquisitionRouteClosure(BaseModel):
    """Content-bound route origin and latest verified continuation closure."""

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
    route_source_cycle_index: int = Field(ge=0)
    planner_report: AcquisitionPlannerReport
    planner_record: AcquisitionActionRecord
    cost_basis_record: AcquisitionCostBasisRecord
    cost_basis_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    route_id: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    # Transport only. The actual action fold replayed these selected receipts;
    # the production mutation bridge re-resolves that owner before using them.
    acquisition_basis_transitions: tuple[AcquisitionOverlayReentryReceipt, ...] = Field(
        default=(), exclude=True, repr=False
    )

    @property
    def route_source_cycle(self) -> GenerationCycleRecord:
        """Resolve the immutable compiled cycle that anchors route and cost identity."""

        matches = tuple(
            cycle
            for cycle in self.generation_run.cycles
            if cycle.cycle_index == self.route_source_cycle_index
        )
        if len(matches) != 1:
            raise AcquisitionRouteClosureError("route_origin_cycle_not_in_continuation")
        return matches[0]

    @property
    def design_problem_basis(self) -> DesignProblem:
        """Recompute the concrete source-cycle basis from the recorded revision chain."""

        return _resolve_source_cycle_problem_basis(
            generation_run=self.generation_run,
            source_cycle=self.source_cycle,
            design_problem=self.design_problem,
            design_problem_ref=self.design_problem_ref,
            acquisition_basis_transitions=self.acquisition_basis_transitions,
        )

    @property
    def design_problem_basis_ref(self) -> str:
        """Return the recomputed hash of the concrete source-cycle basis."""

        return _problem_ref(self.design_problem_basis)


class _ActionHead(Protocol):
    """Structural view of the persisted action-generation owner."""

    action_generation: int
    job_id: str


class _VerifiedActionOutcome(Protocol):
    """Exact verified head and its latest persisted phase or terminal receipt."""

    head: _ActionHead
    latest_receipt: AcquisitionRoutePhaseReceipt | AcquisitionTerminalReceipt
    executing_phase_ref: str | None


class _ActionOutcomeReader(Protocol):
    """Read every owner-verified generation for one exact route identity."""

    def action_outcomes(
        self,
        *,
        tenant_id: str,
        cell_id: str,
        run_id: str,
        source_job_id: str,
        route_id: str,
    ) -> tuple[_VerifiedActionOutcome, ...]: ...

    def resolve_action_generation(
        self,
        *,
        tenant_id: str,
        cell_id: str,
        run_id: str,
        source_job_id: str,
        route_id: str,
        job_id: str,
    ) -> int: ...


class AcquisitionRouteLoop:
    """Resolve verified closures and own acquisition phase orchestration."""

    def __init__(
        self,
        *,
        control_store: ControlPlaneStore,
        artifact_store: _ArtifactStore,
        event_log: RuntimeDiagnosticEventLog,
        core_source_resolver: CompletedControlJobCoreSourceResolver,
        tenant_id: str,
        cell_id: str,
        action_outcome_reader: _ActionOutcomeReader | None = None,
    ) -> None:
        if not tenant_id.strip() or not cell_id.strip():
            raise ValueError("acquisition route loop requires tenant and cell")
        for capability in ("has", "get_bytes", "get_manifest"):
            if not callable(getattr(artifact_store, capability, None)):
                raise TypeError("acquisition route loop requires guarded CAS read capabilities")
        self._control_store = control_store
        self._artifact_store = artifact_store
        self._event_log = event_log
        self._core_source_resolver = core_source_resolver
        self._tenant_id = tenant_id
        self._cell_id = cell_id
        self._action_outcome_reader = action_outcome_reader

    def resolve_current_route(
        self,
        *,
        run_id: str,
        before_action_generation: int | None = None,
        action_job_id: str | None = None,
    ) -> VerifiedAcquisitionRouteClosure:
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
        if not self._artifact_store.has(ArtifactID.model_validate(manifest_ref)):
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
        try:
            selected_compiled_ref = ArtifactRef.model_validate(
                progress.get("compiled_recursive_generation_cycle_artifact_ref")
            )
            terminal = self._core_source_resolver(
                job,
                expected_control_run_id=run_id,
                tenant_id=self._tenant_id,
                cell_id=self._cell_id,
            )
        except (TypeError, ValueError, OSError) as exc:
            raise AcquisitionRouteClosureError("source_core_attempt_not_established") from exc
        from polisyos.core.artifacts import artifact_ref_identity_key

        compiled_outputs = tuple(
            ref
            for ref in terminal.manifest.outputs
            if ref.kind == "runtime.compiled_recursive_generation_cycle"
        )
        if (
            terminal.manifest.status != "ok"
            or terminal.tenant_id != self._tenant_id
            or terminal.cell_id != self._cell_id
            or str(terminal.manifest_ref.artifact_id) != progress.get("manifest_ref")
            or len(compiled_outputs) != 1
            or str(compiled_outputs[0].artifact_id) != compiled_ref
            or artifact_ref_identity_key(compiled_outputs[0])
            != artifact_ref_identity_key(selected_compiled_ref)
        ):
            raise AcquisitionRouteClosureError("source_core_output_binding_mismatch")
        terminal_event_id = self._resolve_terminal_event(
            run_id=run_id,
            job_id=job.job_id,
            compiled_ref=compiled_ref,
            manifest_ref=manifest_ref,
        )
        compiled_payload = self._read_json_artifact(
            selected_compiled_ref,
            expected_kind="runtime.compiled_recursive_generation_cycle",
            expected_schema_name="polisyos.runtime.CompiledRecursiveGenerationCycleRun",
        )
        from polisyos.runtime.http.services.control.generation_cycle import (
            CompiledRecursiveGenerationCycleRun,
        )

        try:
            compiled = CompiledRecursiveGenerationCycleRun.model_validate(compiled_payload)
        except (TypeError, ValueError) as exc:
            raise AcquisitionRouteClosureError("compiled_run_invalid") from exc
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
        source_problem = _resolve_source_cycle_problem_basis(
            generation_run=generation_run,
            source_cycle=source_cycle,
            design_problem=compiled.design_problem,
            design_problem_ref=compiled.design_problem_ref,
        )
        report = source_cycle.acquisition_routing_report
        cost = source_cycle.acquisition_cost_basis_record
        if report is None or cost is None:
            raise AcquisitionRouteClosureError("costed_route_not_unique")
        source_requirement = _cycle_acquisition_requirement(
            source_cycle.grounding, source_cycle.value_port
        )
        planner_record = _select_source_planner_record(report, source_requirement)
        planner_ref = source_cycle.acquisition_routing_report_ref
        if planner_ref is None:
            raise AcquisitionRouteClosureError("acquisition_planner_report_ref_required")
        basis_issues = validate_persisted_acquisition_planner_report(
            self._artifact_store,
            planner_ref,
            report,
            expected_scenario_id=compiled.design_problem.design_problem_id,
            expected_compiled_requirement_ref=planner_record.compiled_requirement_ref,
        )
        if basis_issues:
            first_issue = basis_issues[0]
            code = first_issue.get("code") if isinstance(first_issue, dict) else None
            raise AcquisitionRouteClosureError(
                code if isinstance(code, str) else "acquisition_planner_basis_not_revalidated"
            )
        source_semantic_schema = planner_record.requirement_schema_version in {
            "policyos.runtime.l1_variable_availability_gap.v1",
            "policyos.runtime.grounding_coverage_gap.v1",
        }
        if source_semantic_schema and source_requirement is None:
            raise AcquisitionRouteClosureError("source_requirement_missing")
        request = source_cycle.revision_request.strategy_payload.get("acquisition_request")
        source_rule = request.get("n7_source_join_rule") if isinstance(request, Mapping) else None
        if source_rule is not None and source_rule != _N7_SOURCE_JOIN_RULE:
            raise AcquisitionRouteClosureError("source_requirement_rule_unsupported")
        row_has_joined_shape = (
            source_semantic_schema
            and source_requirement is not None
            and planner_record.compiled_requirement_ref
            != source_requirement.compiled_requirement_ref
        )
        if row_has_joined_shape and source_rule is None:
            raise AcquisitionRouteClosureError("source_requirement_rule_missing")
        if source_rule == _N7_SOURCE_JOIN_RULE:
            if not isinstance(request, Mapping):
                raise AcquisitionRouteClosureError("source_requirement_request_missing")
            source_gap, refusal = _n7_cycle_source_gap(
                source_problem,
                cycle=source_cycle,
                acquisition_request=request,
            )
            binding = report.requirement_basis_binding
            if refusal is not None or source_gap is None or binding is None:
                raise AcquisitionRouteClosureError("source_requirement_binding_mismatch")
            try:
                compiler_report = DataRequirementCompilationReport.model_validate(
                    load_core_json_artifact(self._artifact_store, binding.compiler_report_ref)
                )
            except Exception as exc:
                raise AcquisitionRouteClosureError(
                    "source_requirement_compiler_unreadable"
                ) from exc
            if not _n7_joined_planner_records_match(
                problem=source_problem,
                acquisition_request=request,
                source_gap=source_gap,
                specs=compiler_report.specs,
                capability_resolutions=compiler_report.capability_requirement_resolutions,
                report=report,
            ):
                raise AcquisitionRouteClosureError("source_requirement_projection_mismatch")
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
        route_source_cycle = source_cycle
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
        generation_run, source_cycle, basis_transitions = self._latest_verified_source(
            run_id=run_id,
            source_job_id=job.job_id,
            route_id=route_id,
            compiled_ref=compiled_ref,
            planner_report_hash=_content_hash(report.model_dump(mode="json")),
            cost_basis_hash=cost.record_content_hash,
            design_problem=compiled.design_problem,
            design_problem_ref=compiled.design_problem_ref,
            generation_run=generation_run,
            source_cycle=source_cycle,
            before_action_generation=before_action_generation,
            action_job_id=action_job_id,
        )
        _resolve_source_cycle_problem_basis(
            generation_run=generation_run,
            source_cycle=source_cycle,
            design_problem=compiled.design_problem,
            design_problem_ref=compiled.design_problem_ref,
            acquisition_basis_transitions=basis_transitions,
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
            route_source_cycle_index=route_source_cycle.cycle_index,
            acquisition_basis_transitions=basis_transitions,
            planner_report=report,
            planner_record=planner_record,
            cost_basis_record=cost,
            cost_basis_hash=cost.record_content_hash,
            route_id=route_id,
        )

    def _latest_verified_source(
        self,
        *,
        run_id: str,
        source_job_id: str,
        route_id: str,
        compiled_ref: str,
        planner_report_hash: str,
        cost_basis_hash: str,
        design_problem: DesignProblem,
        design_problem_ref: str,
        generation_run: GenerationCycleRun,
        source_cycle: GenerationCycleRecord,
        before_action_generation: int | None,
        action_job_id: str | None,
    ) -> tuple[
        GenerationCycleRun, GenerationCycleRecord, tuple[AcquisitionOverlayReentryReceipt, ...]
    ]:
        """Fold only verified terminal re-entry receipts over the compiled source."""

        if before_action_generation is not None and before_action_generation < 1:
            raise AcquisitionRouteClosureError("continuation_action_generation_invalid")
        if before_action_generation is not None and action_job_id is not None:
            raise AcquisitionRouteClosureError("continuation_action_cutoff_ambiguous")
        reader = self._action_outcome_reader
        if reader is None:
            list_heads = getattr(self._control_store, "list_acquisition_action_heads", None)
            if not callable(list_heads):
                raise AcquisitionRouteClosureError("continuation_selector_not_composed")
            heads = list_heads(
                tenant_id=self._tenant_id,
                cell_id=self._cell_id,
                run_id=run_id,
                source_job_id=source_job_id,
                route_id=route_id,
            )
            if heads:
                raise AcquisitionRouteClosureError("continuation_selector_not_composed")
            outcomes: tuple[_VerifiedActionOutcome, ...] = ()
        else:
            try:
                outcomes = reader.action_outcomes(
                    tenant_id=self._tenant_id,
                    cell_id=self._cell_id,
                    run_id=run_id,
                    source_job_id=source_job_id,
                    route_id=route_id,
                )
            except (AttributeError, TypeError, ValueError, OSError) as exc:
                raise AcquisitionRouteClosureError(
                    "acquisition_action_history_not_verified"
                ) from exc
            if not isinstance(outcomes, tuple):
                raise AcquisitionRouteClosureError("acquisition_action_history_not_verified")
            if action_job_id is not None:
                same_job = tuple(item for item in outcomes if item.head.job_id == action_job_id)
                if len(same_job) > 1:
                    raise AcquisitionRouteClosureError(
                        "acquisition_action_job_generation_ambiguous"
                    )
                if same_job:
                    before_action_generation = same_job[0].head.action_generation
                elif outcomes:
                    latest = outcomes[-1].latest_receipt
                    if not isinstance(
                        latest, (AcquisitionRouteLoopReceipt, AcquisitionRouteLoopReceiptV2)
                    ) or latest.terminal_outcome not in {
                        "quarantined_no_growth",
                        "reentry_completed",
                        "source_admitted_evaluation_retained",
                    }:
                        raise AcquisitionRouteClosureError(
                            "acquisition_action_generation_not_resolvable"
                        )
                    before_action_generation = outcomes[-1].head.action_generation + 1
                else:
                    before_action_generation = 1

        selected_run = generation_run
        selected_cycle = source_cycle
        basis_transitions: list[AcquisitionOverlayReentryReceipt] = []
        for snapshot in outcomes:
            receipt = snapshot.latest_receipt
            if (
                receipt.action_generation != snapshot.head.action_generation
                or receipt.action_generation < 1
            ):
                raise AcquisitionRouteClosureError("acquisition_action_history_not_verified")
            if (
                before_action_generation is not None
                and snapshot.head.action_generation >= before_action_generation
            ):
                continue
            if not isinstance(
                receipt, (AcquisitionRouteLoopReceipt, AcquisitionRouteLoopReceiptV2)
            ):
                raise AcquisitionRouteClosureError("acquisition_action_outcome_not_terminal")
            if (
                receipt.tenant_id != self._tenant_id
                or receipt.cell_id != self._cell_id
                or receipt.run_id != run_id
                or receipt.source_job_id != source_job_id
                or receipt.route_id != route_id
                or receipt.compiled_ref != compiled_ref
                or receipt.planner_report_hash != planner_report_hash
                or receipt.cost_basis_hash != cost_basis_hash
            ):
                raise AcquisitionRouteClosureError("acquisition_action_source_identity_mismatch")
            if receipt.terminal_outcome == "quarantined_no_growth":
                continue
            if receipt.terminal_outcome == "source_admitted_evaluation_retained":
                from polisyos.runtime.quality.acquisition_evaluation_history import (
                    verify_retained_route_accumulator,
                )

                verify_retained_route_accumulator(
                    artifact_store=self._artifact_store,
                    event_log=self._event_log,
                    control_store=self._control_store,
                    snapshot=snapshot,
                    terminal=receipt,
                    generation_run=selected_run,
                    source_cycle=selected_cycle,
                    design_problem_ref=design_problem_ref,
                )
                # The actual selected evaluation tuple was reconciled above;
                # admission changed, the evaluation accumulator did not.
                continue
            selected_run, selected_cycle = self._verified_reentry_source(
                snapshot=snapshot,
                terminal=receipt,
                source_run=selected_run,
                source_cycle=selected_cycle,
                design_problem=design_problem,
                design_problem_ref=design_problem_ref,
                route_id=route_id,
                source_job_id=source_job_id,
                acquisition_basis_transitions=tuple(basis_transitions),
            )
            # The preceding call verified this exact immutable source/event/
            # predecessor relation. Reload its typed body for the basis fold;
            # never derive a transition from a same-ID marker alone.
            transition = AcquisitionOverlayReentryReceipt.model_validate(
                self._read_json_artifact(
                    receipt.reentry_receipt_ref,
                    expected_kind="runtime_quality.acquisition_overlay_reentry_receipt",
                    expected_schema_name="polisyos.runtime.AcquisitionOverlayReentryReceipt",
                    expected_schema_versions=("2.0",),
                )
            )
            basis_transitions.append(transition)
        return selected_run, selected_cycle, tuple(basis_transitions)

    def _verified_reentry_source(
        self,
        *,
        snapshot: object,
        terminal: AcquisitionTerminalReceipt,
        source_run: GenerationCycleRun,
        source_cycle: GenerationCycleRecord,
        design_problem: DesignProblem,
        design_problem_ref: str,
        route_id: str,
        source_job_id: str,
        acquisition_basis_transitions: tuple[AcquisitionOverlayReentryReceipt, ...] = (),
    ) -> tuple[GenerationCycleRun, GenerationCycleRecord]:
        """Verify owner persistence, event scope, growth binding, and append-only N4 history."""

        if terminal.reentry_receipt_ref is None or not source_run.cycles:
            raise AcquisitionRouteClosureError("continuation_reentry_ref_missing")
        action_phase_ref = getattr(snapshot, "executing_phase_ref", None)
        if not isinstance(action_phase_ref, str):
            raise AcquisitionRouteClosureError("continuation_action_phase_missing")
        owner_refs = tuple(terminal.owner_receipt_refs)
        try:
            growth_refs = tuple(
                ref
                for ref in owner_refs
                if self._artifact_store.get_manifest(ArtifactID.model_validate(ref)).kind
                == "runtime_quality.acquisition_world_growth_receipt"
            )
        except Exception as exc:
            raise AcquisitionRouteClosureError("continuation_growth_owner_unverified") from exc
        if len(growth_refs) != 1:
            raise AcquisitionRouteClosureError("continuation_growth_owner_ambiguous")
        from polisyos.runtime.quality.acquisition_world_growth import (
            AcquisitionWorldGrowthReceipt,
        )
        from polisyos.runtime.quality.authority_reconciliation import (
            reconcile_authority_ref,
        )

        growth_ref = growth_refs[0]
        try:
            growth_payload = self._read_json_artifact(
                growth_ref,
                expected_kind="runtime_quality.acquisition_world_growth_receipt",
                expected_schema_name=AcquisitionWorldGrowthReceipt.ARTIFACT_SCHEMA_NAME,
                expected_schema_versions=("1.1",),
            )
            if (
                not isinstance(growth_payload, dict)
                or growth_payload.get("schema_version") != "AcquisitionWorldGrowthReceipt@1.1"
                or "action_phase_ref" not in growth_payload
            ):
                raise ValueError("growth schema or action phase absent")
            growth = AcquisitionWorldGrowthReceipt.model_validate(growth_payload)
            growth_report = reconcile_authority_ref(
                artifact_store=self._artifact_store,
                event_log=self._event_log,
                cas_ref=growth_ref,
                expected_tenant_id=self._tenant_id,
                expected_cell_id=self._cell_id,
                expected_run_id=terminal.run_id,
                expected_job_id=source_job_id,
            )
            growth_manifest = self._artifact_store.get_manifest(
                ArtifactID.model_validate(growth_ref)
            )
            if (
                growth_manifest.producer is None
                or growth_manifest.producer.component != "polisyos.runtime.acquisition_world_growth"
                or growth_report.durable_event_id is None
                or growth.action_phase_ref != action_phase_ref
                or growth.selection.key
                != (self._tenant_id, self._cell_id, terminal.run_id, route_id)
                or growth.selection.design_problem_ref != design_problem_ref
            ):
                raise ValueError("growth reentry binding mismatch")
        except Exception as exc:
            raise AcquisitionRouteClosureError("continuation_growth_owner_unverified") from exc

        reentry_ref = terminal.reentry_receipt_ref
        try:
            reentry_payload = self._read_json_artifact(
                reentry_ref,
                expected_kind="runtime_quality.acquisition_overlay_reentry_receipt",
                expected_schema_name="polisyos.runtime.AcquisitionOverlayReentryReceipt",
                expected_schema_versions=("1.0", "2.0"),
            )
            if not isinstance(reentry_payload, dict) or "schema_version" not in reentry_payload:
                raise AcquisitionRouteClosureError("continuation_schema_version_missing")
            if reentry_payload["schema_version"] in {
                "policyos.runtime.acquisition_overlay_reentry.v1",
                "policyos.runtime.acquisition_overlay_reentry.v2",
            }:
                raise AcquisitionRouteClosureError("legacy_occurrence_unbound")
            if (
                reentry_payload["schema_version"]
                != "policyos.runtime.acquisition_overlay_reentry.v3"
            ):
                raise AcquisitionRouteClosureError("continuation_schema_version_invalid")
            reentry = AcquisitionOverlayReentryReceipt.model_validate(reentry_payload)
            reentry_manifest = self._artifact_store.get_manifest(
                ArtifactID.model_validate(reentry_ref)
            )
            if (
                reentry_manifest.producer is None
                or reentry_manifest.producer.component
                != "polisyos.runtime.acquisition_world_growth"
            ):
                raise ValueError("reentry producer mismatch")
            if not reentry.schema_version.endswith(".v3"):
                raise AcquisitionRouteClosureError("legacy_occurrence_unbound")
            if (
                reentry_manifest.artifact_schema is None
                or reentry_manifest.artifact_schema.version != "2.0"
            ):
                raise ValueError("v3 reentry schema version mismatch")
            reentry_event_id = "evt_acquisition_reentry_" + growth_ref.removeprefix("sha256:")
            reentry_report = reconcile_authority_ref(
                artifact_store=self._artifact_store,
                event_log=self._event_log,
                cas_ref=reentry_ref,
                expected_tenant_id=self._tenant_id,
                expected_cell_id=self._cell_id,
                expected_run_id=terminal.run_id,
                expected_job_id=source_job_id,
            )
            rows = self._event_log.list_events(event_id=reentry_event_id, limit=2)
            if (
                reentry_report.durable_event_id != reentry_event_id
                or len(rows) != 1
                or rows[0].event.event_source != "polisyos.runtime.acquisition_world_growth"
                or rows[0].event.producer_component != "polisyos.runtime.acquisition_world_growth"
                or rows[0].event.phase != "reentry_terminal"
                or rows[0].event.state_after != "reentry_terminal"
                or rows[0].event.tenant_id != self._tenant_id
                or rows[0].event.cell_id != self._cell_id
                or rows[0].event.run_id != terminal.run_id
                or rows[0].event.job_id != source_job_id
                or reentry_ref not in rows[0].event.artifact_refs
            ):
                raise ValueError("reentry event binding mismatch")
            if (
                reentry.source_run_id != source_run.run_id
                or reentry.design_problem_ref != design_problem_ref
                or reentry.source_cycle_index != source_cycle.cycle_index
                or reentry.source_candidate_ref != source_cycle.selected_candidate_ref
                or reentry.new_cycle.cycle_index != source_cycle.cycle_index + 1
                or reentry.new_cycle.design_problem_ref != design_problem_ref
                or reentry.new_cycle.design_problem_basis_ref
                != _problem_ref(
                    _resolve_source_cycle_problem_basis(
                        generation_run=source_run,
                        source_cycle=source_cycle,
                        design_problem=design_problem,
                        design_problem_ref=design_problem_ref,
                        acquisition_basis_transitions=acquisition_basis_transitions,
                    )
                )
                or reentry.overlay_receipt_ref
                != str(growth.activation.overlay_admission_receipt_ref.artifact_id)
                or reentry.semantic_epoch_production_receipt_ref
                != str(growth.activation.semantic_epoch_production_receipt_ref.artifact_id)
                or reentry.admitted_observation_count
                != growth.previously_active_observations + growth.admitted_observation_delta
            ):
                raise ValueError("reentry source or growth binding mismatch")
            validate_acquisition_overlay_continuation(source_run, reentry)
        except AcquisitionRouteClosureError:
            raise
        except Exception as exc:
            raise AcquisitionRouteClosureError("continuation_reentry_unverified") from exc
        continued = reentry.continued_generation_run
        if (
            continued is None
            or generation_cycle_run_content_hash(continued)
            != reentry.continued_generation_run_content_hash
        ):
            raise AcquisitionRouteClosureError("continuation_run_missing")
        return continued, reentry.new_cycle

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
        ref: str | ArtifactRef,
        *,
        expected_kind: str,
        expected_schema_name: str,
        expected_schema_versions: tuple[str, ...] = ("1.0",),
    ) -> object:
        from polisyos.core.artifacts import load_core_json_artifact

        try:
            selected_ref = ref if isinstance(ref, ArtifactRef) else ArtifactID.model_validate(ref)
            artifact_id = (
                selected_ref.artifact_id if isinstance(selected_ref, ArtifactRef) else selected_ref
            )
            selected_id = str(artifact_id)
            if not self._artifact_store.has(selected_ref):
                raise ValueError("artifact missing")
            blob = self._artifact_store.get_bytes(selected_ref)
            if selected_id != f"sha256:{hashlib.sha256(blob).hexdigest()}":
                raise ValueError("artifact content mismatch")
            manifest = self._artifact_store.get_manifest(selected_ref)
            schema = manifest.artifact_schema
            if (
                manifest.kind != expected_kind
                or schema is None
                or schema.name != expected_schema_name
                or schema.version not in expected_schema_versions
            ):
                raise ValueError("artifact manifest mismatch")
            return load_core_json_artifact(
                self._artifact_store, selected_ref, raw_payload_bytes=blob
            )
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
    terminal = AcquisitionRouteLoopReceipt(
        receipt_id=f"{pending_receipt.receipt_id}.terminal",
        tenant_id=pending_receipt.tenant_id,
        cell_id=pending_receipt.cell_id,
        run_id=pending_receipt.run_id,
        source_job_id=pending_receipt.source_job_id,
        route_id=pending_receipt.route_id,
        action_generation=pending_receipt.action_generation,
        job_id=pending_receipt.job_id,
        compiled_ref=pending_receipt.compiled_ref,
        planner_report_hash=pending_receipt.planner_report_hash,
        cost_basis_hash=pending_receipt.cost_basis_hash,
        decision_ref=pending_receipt.decision_ref,
        terminal_outcome="reentry_completed",
        predecessor_receipt_ref=pending_receipt_ref,
        owner_receipt_refs=pending_receipt.owner_receipt_refs,
        reentry_receipt_ref=reentry_ref,
        generated_at=datetime.now(pending_receipt.generated_at.tzinfo),
    )
    return sink.persist_terminal(terminal)


__all__ = [
    "AcquisitionRouteClosureError",
    "AcquisitionRouteLoop",
    "AcquisitionRouteLoopReceipt",
    "AcquisitionRouteLoopReceiptV2",
    "AcquisitionRoutePhaseReceipt",
    "AcquisitionRouteRecoveryRequired",
    "AcquisitionTerminalReceipt",
    "VerifiedAcquisitionRouteClosure",
    "parse_acquisition_route_loop_receipt",
    "persist_world_commit_and_reenter",
    "resume_world_committed_reentry",
]
