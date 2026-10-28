"""Bind native acquisition activation to durable, same-case generation re-entry.

Deployment selects evidence and a finite re-entry budget. Native catalog and epoch
owners decide admission; neither a successful fetch nor deployment configuration
can decide it. An empty selection remains a usable quarantine-only deployment.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from collections.abc import Sequence  # noqa: TC003
from datetime import UTC, datetime
from decimal import Decimal  # Pydantic resolves this annotation
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar, Literal, Protocol, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.common import async_tools
from polisyos.core import artifacts, canon, contracts
from polisyos.data_forge import read_api as data_forge_read_api
from polisyos.runtime.quality import acquisition_executor
from polisyos.runtime.quality.acquisition_route_loop import (
    AcquisitionRouteLoop,
    AcquisitionRouteLoopReceipt,
    AcquisitionRoutePhaseReceipt,
)
from polisyos.runtime.quality.agent_action_authority import (
    agent_action_content_hash,
    write_runtime_authority_artifact,
)
from polisyos.runtime.quality.authority import GovernanceMetadata
from polisyos.runtime.quality.authority_reconciliation import reconcile_authority_ref
from polisyos.runtime.quality.generation_cycle import (
    AcquisitionOverlayReentryReceipt,
    GenerationCycleController,
)
from polisyos.runtime.quality.semantic_epoch import (
    EpochScopeIdentity,
    PersistedSemanticEpochProductionReceipt,
    PreparedSemanticEpoch,
    build_epoch_resolution_query_from_evidence,
)
from polisyos.scientist import BudgetState

if TYPE_CHECKING:
    from polisyos.runtime.http.services.control.run_lifecycle import ControlPlaneService
    from polisyos.runtime.quality.acquisition_route_loop import (
        VerifiedAcquisitionRouteClosure,
    )
    from polisyos.runtime.quality.epoch_deployment import EpochDeployment
    from polisyos.runtime.quality.event_log import RuntimeDiagnosticEventLog
    from polisyos.runtime.quality.open_world_risk import PromotionRuntime

_SHA = r"^sha256:[0-9a-f]{64}$"
_GROWTH_KIND = "runtime_quality.acquisition_world_growth_receipt"
_ATTEMPT_KIND = "runtime_quality.acquisition_world_growth_attempt"
_DEFERRAL_KIND = "runtime_quality.acquisition_world_growth_deferral"
_NO_GROWTH_KIND = "runtime_quality.acquisition_world_growth_no_growth_receipt"
_REENTRY_KIND = "runtime_quality.acquisition_overlay_reentry_receipt"


class _CurrentActionOutcomeSnapshot(Protocol):
    head: object
    latest_receipt: AcquisitionRoutePhaseReceipt | AcquisitionRouteLoopReceipt
    executing_phase_ref: str | None
    executing_phase: AcquisitionRoutePhaseReceipt | None
    selection_phase_ref: str | None
    selection_phase: AcquisitionRoutePhaseReceipt | None


class _CurrentActionOutcomeReader(Protocol):
    def current_action_outcome(
        self,
        *,
        tenant_id: str,
        cell_id: str,
        run_id: str,
        source_job_id: str,
        route_id: str,
    ) -> _CurrentActionOutcomeSnapshot | None: ...


def _require_promotion_runtime_store_binding(
    promotion_runtime: PromotionRuntime | None,
    artifact_store: artifacts.ArtifactStore,
) -> None:
    if (
        promotion_runtime is not None
        and getattr(promotion_runtime, "store", None) is not artifact_store
    ):
        raise ValueError("acquisition_world_growth_promotion_runtime_store_mismatch")


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class AcquisitionCandidateWorldRefresh(_Strict):
    """Explicit controlled-candidate mapping for one admitted route variable."""

    tenant_id: str = Field(min_length=1)
    cell_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    route_id: str = Field(pattern=_SHA)
    profile_selection_ref: str = Field(pattern=_SHA)
    canonical_variable_id: str = Field(min_length=1)
    target_slot_id: str = Field(min_length=1)
    mapping_semantics: Literal["candidate_value_forwarded_without_conversion"] = (
        "candidate_value_forwarded_without_conversion"
    )

    @property
    def key(self) -> tuple[str, str, str, str]:
        """Exact served route key selected by this candidate-only mapping."""

        return self.tenant_id, self.cell_id, self.run_id, self.route_id


class AcquisitionWorldGrowthRoute(_Strict):
    """Explicit deployment selection for one route; it conveys no admission."""

    tenant_id: str = Field(min_length=1)
    cell_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    route_id: str = Field(pattern=_SHA)
    design_problem_ref: str = Field(pattern=_SHA)
    epoch_id: int = Field(gt=0)
    epoch_scope_identity: EpochScopeIdentity
    authority_purpose: str = Field(min_length=1)
    valid_effect_coordinate_evidence_ref: artifacts.ArtifactRef
    visibility_knowledge_cutoff_evidence_ref: artifacts.ArtifactRef
    purpose_admission_cutoff_evidence_ref: artifacts.ArtifactRef
    facet_source_refs: dict[str, artifacts.ArtifactRef]
    reentry_budget_usd: Decimal = Field(gt=0, allow_inf_nan=False)

    @property
    def key(self) -> tuple[str, str, str, str]:
        """Exact tenant and route selection key."""
        return self.tenant_id, self.cell_id, self.run_id, self.route_id


class AcquisitionWorldGrowthConfig(_Strict):
    """Typed empty-by-default evidence and controlled-refresh selections."""

    routes: tuple[AcquisitionWorldGrowthRoute, ...] = ()
    candidate_world_refreshes: tuple[AcquisitionCandidateWorldRefresh, ...] = ()

    @model_validator(mode="after")
    def _unique_routes(self) -> Self:
        route_keys = {route.key for route in self.routes}
        if len(route_keys) != len(self.routes):
            raise ValueError("acquisition_world_growth_route_ambiguous")
        refresh_keys = {refresh.key for refresh in self.candidate_world_refreshes}
        if len(refresh_keys) != len(self.candidate_world_refreshes):
            raise ValueError("acquisition_candidate_world_refresh_ambiguous")
        if not refresh_keys.issubset(route_keys):
            raise ValueError("acquisition_candidate_world_refresh_route_unconfigured")
        return self


class AcquisitionWorldGrowthActionOutcomeSelector(_Strict):
    """Mutable pointer to one action-head-bound owner outcome; the CAS receipt is immutable."""

    schema_version: Literal[
        "AcquisitionWorldGrowthActionOutcomeSelector@1.0",
        "AcquisitionWorldGrowthActionOutcomeSelector@1.1",
    ] = "AcquisitionWorldGrowthActionOutcomeSelector@1.1"
    route_id: str = Field(pattern=_SHA)
    action_phase_ref: str = Field(pattern=_SHA)
    state: Literal["executing", "prepared", "selected"]
    receipt_kind: Literal[_GROWTH_KIND, _NO_GROWTH_KIND] | None = None
    receipt_ref: str | None = Field(default=None, pattern=_SHA)

    @model_validator(mode="after")
    def _selector_state_matches_receipt(self) -> Self:
        has_receipt = self.receipt_kind is not None and self.receipt_ref is not None
        if (self.state == "executing") == has_receipt:
            raise ValueError("acquisition_action_outcome_selector_state_mismatch")
        if self.state == "prepared" and self.schema_version != (
            "AcquisitionWorldGrowthActionOutcomeSelector@1.1"
        ):
            raise ValueError("acquisition_action_outcome_selector_schema_version_mismatch")
        return self


class _PriorMembership(_Strict):
    epoch_id: int
    passport_id: str
    epoch_activation_state: str
    admitted_observation_count: int = Field(ge=0)


class AcquisitionWorldGrowthAttempt(_Strict):
    """Immutable evidence and pre-state saved before native activation can happen."""

    selection: AcquisitionWorldGrowthRoute
    binding_id: str
    target_variable: str
    evidence: acquisition_executor.LiveSourceExecutionEvidence
    owner_receipt_refs: tuple[str, ...]
    before: tuple[_PriorMembership, ...]
    action_phase_ref: str | None = Field(default=None, pattern=_SHA)


class AcquisitionWorldGrowthReceipt(_Strict):
    """Native activation plus the measured change in active membership."""

    ARTIFACT_SCHEMA_NAME: ClassVar[str] = "AcquisitionWorldGrowthReceipt"

    schema_version: Literal[
        "AcquisitionWorldGrowthReceipt@1.0", "AcquisitionWorldGrowthReceipt@1.1"
    ] = "AcquisitionWorldGrowthReceipt@1.1"
    selection: AcquisitionWorldGrowthRoute
    binding_id: str = Field(min_length=1)
    activation: acquisition_executor.ActivatedSemanticEpochAdmissionReceipt
    passport_id: str = Field(min_length=1)
    admitted_observation_delta: int = Field(gt=0)
    previously_active_observations: int = Field(ge=0)
    live_evidence_refs: tuple[str, ...] = Field(min_length=1)
    action_phase_ref: str | None = Field(default=None, pattern=_SHA)

    @model_validator(mode="after")
    def _action_scope_schema_version(self) -> Self:
        if self.schema_version.endswith("@1.0") and self.action_phase_ref is not None:
            raise ValueError("acquisition_growth_action_scope_schema_version_mismatch")
        return self


class AcquisitionWorldGrowthDeferral(_Strict):
    """Known native negative over the exact durable live attempt, not retry authority."""

    schema_version: Literal["AcquisitionWorldGrowthDeferral@1.0"] = (
        "AcquisitionWorldGrowthDeferral@1.0"
    )
    attempt_ref: str = Field(pattern=_SHA)
    negative_receipt: PersistedSemanticEpochProductionReceipt


class _EpochMembership(Protocol):
    epoch_id: int
    passport_id: str
    epoch_activation_state: str
    admitted_observation_count: int


def admitted_membership_delta(
    *,
    before: Sequence[_EpochMembership],
    after: Sequence[_EpochMembership],
    epoch_id: int,
    passport_id: str,
) -> int:
    """Measure the exact native epoch, refusing ambiguity or replacement."""
    prior = tuple(row for row in before if row.epoch_id == epoch_id)
    current = tuple(row for row in after if row.epoch_id == epoch_id)
    if (
        len(current) != 1
        or current[0].passport_id != passport_id
        or current[0].epoch_activation_state != "active"
        or current[0].admitted_observation_count <= 0
    ):
        raise ValueError("acquisition_active_membership_unresolved")
    if len(prior) > 1 or (prior and prior[0].passport_id != passport_id):
        raise ValueError("acquisition_prior_membership_changed")
    old = (
        prior[0].admitted_observation_count
        if prior and prior[0].epoch_activation_state == "active"
        else 0
    )
    delta = current[0].admitted_observation_count - old
    if delta < 0:
        raise ValueError("acquisition_prior_membership_changed")
    return delta


class AcquisitionWorldGrowthNoGrowthReceipt(_Strict):
    """Persist a verified repeat action whose current owner membership did not grow."""

    schema_version: Literal[
        "AcquisitionWorldGrowthNoGrowthReceipt@1.0",
        "AcquisitionWorldGrowthNoGrowthReceipt@1.1",
    ] = "AcquisitionWorldGrowthNoGrowthReceipt@1.1"
    selection: AcquisitionWorldGrowthRoute
    growth_receipt_ref: str = Field(pattern=_SHA)
    attempt_ref: str = Field(pattern=_SHA)
    binding_id: str = Field(min_length=1)
    passport_id: str = Field(min_length=1)
    observed_admitted_observation_count: int = Field(gt=0)
    admitted_observation_delta: Literal[0] = 0
    live_evidence_refs: tuple[str, ...] = Field(min_length=1)
    before: tuple[_PriorMembership, ...]
    after: tuple[_PriorMembership, ...]
    action_phase_ref: str | None = Field(default=None, pattern=_SHA)

    @model_validator(mode="after")
    def _recompute_zero_delta(self) -> Self:
        if self.schema_version.endswith("@1.0") and self.action_phase_ref is not None:
            raise ValueError("acquisition_no_growth_action_scope_schema_version_mismatch")
        if self.before != self.after:
            raise ValueError("acquisition_no_growth_membership_snapshot_changed")
        rows = tuple(row for row in self.after if row.epoch_id == self.selection.epoch_id)
        if (
            len(rows) != 1
            or rows[0].passport_id != self.passport_id
            or rows[0].epoch_activation_state != "active"
            or rows[0].admitted_observation_count != self.observed_admitted_observation_count
        ):
            raise ValueError("acquisition_no_growth_membership_unresolved")
        if (
            admitted_membership_delta(
                before=self.before,
                after=self.after,
                epoch_id=self.selection.epoch_id,
                passport_id=self.passport_id,
            )
            != self.admitted_observation_delta
        ):
            raise ValueError("acquisition_no_growth_delta_mismatch")
        return self


class AcquisitionWorldGrowthRecoveredOutcome(_Strict):
    """A reverified outcome selected for the current immutable executing action head."""

    disposition: Literal["quarantined_no_growth", "world_committed"]
    action_phase_ref: str = Field(pattern=_SHA)
    outcome_receipt_ref: str = Field(pattern=_SHA)
    growth_receipt_ref: str = Field(pattern=_SHA)
    growth: AcquisitionWorldGrowthReceipt
    no_growth_receipt: AcquisitionWorldGrowthNoGrowthReceipt | None = None
    owner_receipt_refs: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _bind_selected_outcome(self) -> Self:
        refs = set(self.owner_receipt_refs)
        if (
            not set(self.growth.live_evidence_refs).issubset(refs)
            or self.growth_receipt_ref not in refs
            or self.outcome_receipt_ref not in refs
            or self.action_phase_ref not in refs
            or (
                self.growth.action_phase_ref is not None
                and self.growth.action_phase_ref not in refs
            )
        ):
            raise ValueError("acquisition_growth_recovery_owner_binding_mismatch")
        if self.no_growth_receipt is None and self.growth.action_phase_ref != self.action_phase_ref:
            raise ValueError("acquisition_growth_recovery_action_scope_mismatch")
        if self.no_growth_receipt is not None:
            if (
                self.no_growth_receipt.action_phase_ref != self.action_phase_ref
                or self.disposition != "quarantined_no_growth"
                or self.outcome_receipt_ref == self.growth_receipt_ref
                or self.no_growth_receipt.selection != self.growth.selection
                or self.no_growth_receipt.growth_receipt_ref != self.growth_receipt_ref
                or self.no_growth_receipt.live_evidence_refs != self.growth.live_evidence_refs
                or self.no_growth_receipt.attempt_ref not in refs
            ):
                raise ValueError("acquisition_growth_recovery_zero_binding_mismatch")
        elif (
            self.disposition != "world_committed"
            or self.outcome_receipt_ref != self.growth_receipt_ref
            or self.growth.admitted_observation_delta <= 0
        ):
            raise ValueError("acquisition_growth_recovery_positive_binding_mismatch")
        if any(not ref.startswith("sha256:") for ref in self.owner_receipt_refs):
            raise ValueError("acquisition_growth_recovery_owner_ref_invalid")
        return self


def _reentry_operation_namespace(overlay_path: Path) -> Path:
    """Keep pointer serialization distinct from the physical native DB fence.

    The native fence replaces the final suffix. Two appended namespace segments
    therefore retain the full original filename and the operation discriminator
    after that transformation, for suffix-less and multi-suffix DB names too.
    This is a lock namespace selector, not a second overlay or a data path.
    """

    physical = Path(overlay_path).resolve(strict=False)
    return physical.with_name(physical.name + ".reentry-operation.lock-target")


class AcquisitionWorldGrowthBridge:
    """Production owner composition for growth and durable re-entry recovery."""

    def __init__(
        self,
        *,
        config: AcquisitionWorldGrowthConfig,
        repo_root: Path,
        runtime_root: Path,
        authority: data_forge_read_api.catalog.CanonicalAcquisitionAuthority,
        artifact_store: artifacts.ArtifactStore,
        event_log: RuntimeDiagnosticEventLog,
        epoch_deployment: EpochDeployment | None,
        promotion_runtime: PromotionRuntime | None = None,
        cycle_substrate_context_admission_owner: object | None = None,
        control_store: object | None = None,
        action_head_sink: _CurrentActionOutcomeReader | None = None,
        source_control_service: ControlPlaneService | None = None,
    ) -> None:
        if type(config) is not AcquisitionWorldGrowthConfig:
            raise TypeError("acquisition world growth selection must be typed")
        _require_promotion_runtime_store_binding(promotion_runtime, artifact_store)
        self.config = config
        self.repo_root = repo_root
        self.runtime_root = runtime_root
        self.authority = authority
        self.artifact_store = artifact_store
        self.event_log = event_log
        self.epoch_deployment = epoch_deployment
        self.promotion_runtime = promotion_runtime
        self.cycle_substrate_context_admission_owner = cycle_substrate_context_admission_owner
        self.control_store = control_store
        self.action_head_sink = action_head_sink
        if source_control_service is not None:
            from polisyos.runtime.http.services.control.run_lifecycle import ControlPlaneService

            if (
                type(source_control_service) is not ControlPlaneService
                or source_control_service._control_store is not control_store
                or source_control_service._artifact_store is not artifact_store
                or source_control_service._diagnostic_event_log is not event_log
                or source_control_service.acquisition_route_sink is not action_head_sink
            ):
                raise TypeError("acquisition_source_control_owner_unbound")
        self._source_control_service = source_control_service

    def selection(
        self, closure: VerifiedAcquisitionRouteClosure
    ) -> AcquisitionWorldGrowthRoute | None:
        """Resolve only an exact configured tenant, case and route."""
        key = closure.tenant_id, closure.cell_id, closure.run_id, closure.route_id
        selected = next((row for row in self.config.routes if row.key == key), None)
        if selected is not None and selected.design_problem_ref != closure.design_problem_ref:
            raise ValueError("acquisition_world_growth_case_mismatch")
        return selected

    def _paths(
        self, selected: AcquisitionWorldGrowthRoute, *, create: bool = True
    ) -> tuple[Path, Path]:
        # One overlay per tenant/cell. Epoch identity remains the native owner's domain.
        scope = hashlib.sha256(canon.to_canonical_bytes(list(selected.key[:2]))).hexdigest()
        root = self.runtime_root / "runtime/acquisition/world-growth" / scope
        if create:
            root.mkdir(parents=True, exist_ok=True)
        return root / "overlay.duckdb", root / "epochs"

    def _validate_action_phase(
        self,
        closure: VerifiedAcquisitionRouteClosure,
        selected: AcquisitionWorldGrowthRoute,
        action_phase_ref: str,
    ) -> AcquisitionRoutePhaseReceipt:
        """Resolve the exact executing phase through the current durable action head."""
        from polisyos.core.artifacts import (
            artifact_ref_for_manifest,
            read_core_json_artifact,
        )

        if not re.fullmatch(_SHA, action_phase_ref):
            raise ValueError("acquisition_action_phase_ref_invalid")
        manifest = contracts.epoch._preflight_core_manifest_profile(
            store=self.artifact_store,
            selector=action_phase_ref,
            expected_kind="runtime_quality.acquisition_route_phase_receipt",
            expected_media_type="application/json",
            expected_schema=artifacts.SchemaInfo(
                name="polisyos.runtime.AcquisitionRoutePhaseReceipt", version="1.0"
            ),
            expected_canon=artifacts.CanonInfo.from_spec(canon.CanonSpec(forbid_floats=False)),
            require_selected_profile=False,
            expected_inputs=contracts.epoch._ExactManifestInputClosure(()),
        )
        selected_ref = artifact_ref_for_manifest(manifest)
        producer, schema = manifest.producer, manifest.artifact_schema
        if (
            producer is None
            or producer.component != "polisyos.runtime.acquisition_route_loop"
            or schema is None
        ):
            raise ValueError("acquisition_action_phase_receipt_unverified")
        payload = self.artifact_store.get_bytes(action_phase_ref)
        if self.artifact_store.get_manifest(action_phase_ref) != manifest:
            raise ValueError("acquisition_action_phase_receipt_unverified")
        if "sha256:" + hashlib.sha256(payload).hexdigest() != action_phase_ref:
            raise ValueError("acquisition_action_phase_receipt_unverified")
        phase = AcquisitionRoutePhaseReceipt.model_validate(
            read_core_json_artifact(
                self.artifact_store, selected_ref, raw_payload_bytes=payload
            ).value
        )
        report = reconcile_authority_ref(
            artifact_store=self.artifact_store,
            event_log=self.event_log,
            cas_ref=action_phase_ref,
            expected_tenant_id=closure.tenant_id,
            expected_cell_id=closure.cell_id,
            expected_run_id=closure.run_id,
            expected_job_id=phase.job_id,
        )
        if report.durable_event_id is None:
            raise ValueError("acquisition_action_phase_source_binding_mismatch")
        if (
            phase.receipt_phase != "executing"
            or phase.tenant_id != closure.tenant_id
            or phase.cell_id != closure.cell_id
            or phase.run_id != closure.run_id
            or phase.source_job_id != closure.source_job_id
            or phase.route_id != selected.route_id
            or phase.compiled_ref != closure.compiled_ref
            or phase.planner_report_hash != agent_action_content_hash(closure.planner_report)
            or phase.cost_basis_hash != closure.cost_basis_hash
        ):
            raise ValueError("acquisition_action_phase_source_binding_mismatch")
        reader = self.action_head_sink
        if reader is not None:
            snapshot = reader.current_action_outcome(
                tenant_id=closure.tenant_id,
                cell_id=closure.cell_id,
                run_id=closure.run_id,
                source_job_id=closure.source_job_id,
                route_id=selected.route_id,
            )
            if (
                snapshot is None
                or snapshot.executing_phase_ref != action_phase_ref
                or snapshot.executing_phase != phase
            ):
                raise ValueError("acquisition_action_phase_head_binding_mismatch")
        else:
            getter = getattr(self.control_store, "get_acquisition_action_head", None)
            if not callable(getter):
                raise ValueError("acquisition_action_head_unavailable")
            head = getter(
                tenant_id=phase.tenant_id,
                cell_id=phase.cell_id,
                run_id=phase.run_id,
                source_job_id=phase.source_job_id,
                route_id=phase.route_id,
                action_generation=phase.action_generation,
            )
            if (
                head is None
                or head.receipt_ref != action_phase_ref
                or head.receipt_sha256 != action_phase_ref
                or head.durable_event_id != report.durable_event_id
                or head.receipt_phase != "executing"
            ):
                raise ValueError("acquisition_action_phase_head_binding_mismatch")
        return phase

    def _action_selector_path(
        self,
        selected: AcquisitionWorldGrowthRoute,
        action_phase_ref: str,
        *,
        create: bool = True,
    ) -> Path:
        overlay_path, _ = self._paths(selected, create=create)
        route_identity = hashlib.sha256(canon.to_canonical_bytes(list(selected.key))).hexdigest()
        action_identity = hashlib.sha256(action_phase_ref.encode()).hexdigest()
        return overlay_path.parent / f"{route_identity}.{action_identity}.action.json"

    def _write_action_selector(
        self,
        pointer: Path,
        selector: AcquisitionWorldGrowthActionOutcomeSelector,
    ) -> None:
        temporary = pointer.with_suffix(".tmp")
        encoded = json.dumps(selector.model_dump(mode="json"), sort_keys=True) + "\n"
        with temporary.open("w") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, pointer)
        self._sync_directory(pointer.parent)

    def _load_action_selector(
        self,
        selected: AcquisitionWorldGrowthRoute,
        action_phase_ref: str,
    ) -> tuple[Path, AcquisitionWorldGrowthActionOutcomeSelector | None]:
        """Read the selector payload without substituting a caller phase claim."""
        pointer = self._action_selector_path(selected, action_phase_ref, create=False)
        try:
            payload = json.loads(pointer.read_text())
        except FileNotFoundError:
            return pointer, None
        except json.JSONDecodeError as exc:
            raise ValueError("acquisition_action_outcome_selector_unverified") from exc
        selector = AcquisitionWorldGrowthActionOutcomeSelector.model_validate(payload)
        if selector.route_id != selected.route_id or selector.action_phase_ref != action_phase_ref:
            raise ValueError("acquisition_action_outcome_selector_binding_mismatch")
        return pointer, selector

    def _read_action_selector(
        self,
        closure: VerifiedAcquisitionRouteClosure,
        selected: AcquisitionWorldGrowthRoute,
        action_phase_ref: str,
    ) -> tuple[Path, AcquisitionWorldGrowthActionOutcomeSelector]:
        self._validate_action_phase(closure, selected, action_phase_ref)
        pointer, selector = self._load_action_selector(selected, action_phase_ref)
        if selector is None:
            raise ValueError("acquisition_owner_outcome_not_established")
        return pointer, selector

    def begin_action(
        self,
        closure: VerifiedAcquisitionRouteClosure,
        action_phase_ref: str,
    ) -> None:
        """Persist the current action scope before the owner can create an outcome."""
        selected = self.selection(closure)
        if selected is None:
            raise ValueError("acquisition_world_growth_selection_missing")
        self._validate_action_phase(closure, selected, action_phase_ref)
        overlay_path, _ = self._paths(selected)
        with data_forge_read_api.catalog.acquisition_overlay_admission_fence(overlay_path):
            pointer = self._action_selector_path(selected, action_phase_ref)
            if pointer.exists():
                _path, prior = self._read_action_selector(closure, selected, action_phase_ref)
                if prior.state == "executing":
                    return
                raise ValueError("acquisition_action_outcome_already_selected")
            self._write_action_selector(
                pointer,
                AcquisitionWorldGrowthActionOutcomeSelector(
                    route_id=selected.route_id,
                    action_phase_ref=action_phase_ref,
                    state="executing",
                ),
            )

    def _prepare_action_outcome(
        self,
        closure: VerifiedAcquisitionRouteClosure,
        selected: AcquisitionWorldGrowthRoute,
        action_phase_ref: str | None,
        receipt_kind: str,
        receipt_ref: str,
    ) -> None:
        """Journal the action-specific CAS result before replacing the route pointer."""
        if action_phase_ref is None:
            return
        if receipt_kind not in (_GROWTH_KIND, _NO_GROWTH_KIND):
            raise ValueError("acquisition_action_outcome_kind_invalid")
        if not re.fullmatch(_SHA, receipt_ref):
            raise ValueError("acquisition_action_outcome_receipt_ref_invalid")
        receipt_value = self._read(receipt_ref, receipt_kind)
        if receipt_value.get("action_phase_ref") != action_phase_ref:
            raise ValueError("acquisition_action_outcome_receipt_scope_mismatch")
        pointer, current = self._read_action_selector(closure, selected, action_phase_ref)
        if current.state == "selected":
            if (current.receipt_kind, current.receipt_ref) != (
                receipt_kind,
                receipt_ref,
            ):
                raise ValueError("acquisition_action_outcome_replay_conflict")
            return
        if current.state == "prepared":
            if (current.receipt_kind, current.receipt_ref) != (
                receipt_kind,
                receipt_ref,
            ):
                raise ValueError("acquisition_action_outcome_replay_conflict")
            return
        self._write_action_selector(
            pointer,
            current.model_copy(
                update={
                    "schema_version": "AcquisitionWorldGrowthActionOutcomeSelector@1.1",
                    "state": "prepared",
                    "receipt_kind": receipt_kind,
                    "receipt_ref": receipt_ref,
                }
            ),
        )

    def _select_action_outcome(
        self,
        closure: VerifiedAcquisitionRouteClosure,
        selected: AcquisitionWorldGrowthRoute,
        action_phase_ref: str | None,
        receipt_kind: str,
        receipt_ref: str,
    ) -> None:
        if action_phase_ref is None:
            return
        if receipt_kind not in (_GROWTH_KIND, _NO_GROWTH_KIND):
            raise ValueError("acquisition_action_outcome_kind_invalid")
        if not re.fullmatch(_SHA, receipt_ref):
            raise ValueError("acquisition_action_outcome_receipt_ref_invalid")
        receipt_value = self._read(receipt_ref, receipt_kind)
        receipt_action_ref = receipt_value.get("action_phase_ref")
        if receipt_action_ref != action_phase_ref:
            raise ValueError("acquisition_action_outcome_receipt_scope_mismatch")
        pointer, current = self._read_action_selector(closure, selected, action_phase_ref)
        if current.state == "selected":
            if (current.receipt_kind, current.receipt_ref) != (
                receipt_kind,
                receipt_ref,
            ):
                raise ValueError("acquisition_action_outcome_replay_conflict")
            return
        self._write_action_selector(
            pointer,
            current.model_copy(
                update={
                    "state": "selected",
                    "receipt_kind": receipt_kind,
                    "receipt_ref": receipt_ref,
                }
            ),
        )

    def admit(
        self,
        *,
        closure: VerifiedAcquisitionRouteClosure,
        binding_id: str,
        target_variable: str,
        evidence: acquisition_executor.LiveSourceExecutionEvidence,
        owner_receipt_refs: tuple[str, ...],
        action_phase_ref: str | None = None,
    ) -> AcquisitionWorldGrowthReceipt | PersistedSemanticEpochProductionReceipt | None:
        """Attempt native admission, measuring fresh membership under the owner lock."""
        selected = self.selection(closure)
        if selected is None:
            return None
        if action_phase_ref is not None:
            self._validate_action_phase(closure, selected, action_phase_ref)
            _selector_path, selector = self._read_action_selector(
                closure, selected, action_phase_ref
            )
            if selector.state != "executing":
                raise ValueError("acquisition_action_outcome_already_selected")
        overlay_path, _ = self._paths(selected)

        # The shared native owner is the contended resource, across routes/processes.
        with data_forge_read_api.catalog.acquisition_overlay_admission_fence(overlay_path):
            before = data_forge_read_api.catalog.project_catalog_acquisition_state(
                self.authority.baseline_path, overlay_path=overlay_path
            )
            attempt = AcquisitionWorldGrowthAttempt(
                selection=selected,
                binding_id=binding_id,
                target_variable=target_variable,
                evidence=evidence,
                owner_receipt_refs=owner_receipt_refs,
                action_phase_ref=action_phase_ref,
                before=tuple(
                    _PriorMembership.model_validate(
                        {key: getattr(row, key) for key in _PriorMembership.model_fields}
                    )
                    for row in before.epochs
                ),
            )
            attempt_pointer = self._growth_pointer(selected).with_suffix(".attempt.json")
            if attempt_pointer.exists():
                prior_ref = json.loads(attempt_pointer.read_text())["receipt_ref"]
                prior = AcquisitionWorldGrowthAttempt.model_validate(
                    self._read(prior_ref, _ATTEMPT_KIND)
                )
                if prior != attempt:
                    raise ValueError("acquisition_world_growth_attempt_replay_conflict")
                attempt_ref = prior_ref
            else:
                attempt_ref = self._persist(
                    closure,
                    attempt.model_dump(mode="json"),
                    _ATTEMPT_KIND,
                    "AcquisitionWorldGrowthAttempt",
                    "admission_pending",
                )
                self._write_pointer(attempt_pointer, attempt_ref)
            return self._admit_stored_attempt(
                closure, attempt_ref, attempt, action_phase_ref=action_phase_ref
            )

    def _admit_stored_attempt(
        self,
        closure: VerifiedAcquisitionRouteClosure,
        attempt_ref: str,
        attempt: AcquisitionWorldGrowthAttempt,
        *,
        action_phase_ref: str | None = None,
    ) -> AcquisitionWorldGrowthReceipt | PersistedSemanticEpochProductionReceipt | None:
        """Run the existing native owner; callers hold the shared admission lock."""
        selected = attempt.selection
        overlay_path, history_root = self._paths(selected)
        activation = acquisition_executor.admit_acquisition_with_production_semantic_epoch(
            repo_root=self.repo_root,
            epoch_id=selected.epoch_id,
            raw_evidence_ref=attempt.evidence.raw_evidence_ref,
            artifact_store=self.artifact_store,
            authority=self.authority,
            overlay_path=overlay_path,
            epoch_history_root=history_root,
            epoch_scope_identity=selected.epoch_scope_identity,
            authority_purpose=selected.authority_purpose,
            valid_effect_coordinate_evidence_ref=selected.valid_effect_coordinate_evidence_ref,
            visibility_knowledge_cutoff_evidence_ref=selected.visibility_knowledge_cutoff_evidence_ref,
            purpose_admission_cutoff_evidence_ref=selected.purpose_admission_cutoff_evidence_ref,
            facet_source_refs=selected.facet_source_refs,
            live_source_execution=attempt.evidence,
            epoch_deployment=self.epoch_deployment,
        )
        if isinstance(activation, PersistedSemanticEpochProductionReceipt):
            negative = self._verified_negative(attempt, activation)
            deferral = AcquisitionWorldGrowthDeferral(
                attempt_ref=attempt_ref, negative_receipt=negative
            )
            ref = self._persist(
                closure,
                deferral.model_dump(mode="json"),
                _DEFERRAL_KIND,
                "AcquisitionWorldGrowthDeferral",
                "admission_deferred",
            )
            self._write_pointer(self._growth_pointer(selected).with_suffix(".deferred.json"), ref)
            return negative
        if not isinstance(activation, acquisition_executor.ActivatedSemanticEpochAdmissionReceipt):
            return None
        growth = self._finish_admission(
            closure, attempt, activation, action_phase_ref=action_phase_ref
        )
        if growth is not None:
            self.persist_growth(closure, growth)
        return growth

    def has_deferred_admission(self, closure: VerifiedAcquisitionRouteClosure) -> bool:
        """Read eligibility from a known negative; never create files or predict admission."""
        try:
            self._load_deferral(closure)
        except KeyError, OSError, RuntimeError, TypeError, ValueError:
            return False
        return True

    def record_measured_no_growth(
        self,
        closure: VerifiedAcquisitionRouteClosure,
        action_phase_ref: str | None = None,
    ) -> tuple[str, ...]:
        """Record a real zero-delta repeat check for an existing native admission."""
        selected = self.selection(closure)
        if selected is None:
            raise ValueError("acquisition_world_growth_selection_missing")
        if action_phase_ref is not None:
            self._validate_action_phase(closure, selected, action_phase_ref)
            _selector_path, selector = self._read_action_selector(
                closure, selected, action_phase_ref
            )
            if selector.state != "executing":
                raise ValueError("acquisition_action_outcome_already_selected")
        overlay_path, _ = self._paths(selected, create=False)
        with data_forge_read_api.catalog.acquisition_overlay_admission_fence(overlay_path):
            pointer = self._growth_pointer(selected, create=False)
            if not pointer.exists():
                raise ValueError("acquisition_world_growth_receipt_missing")
            pointer_kind, selected_ref = self._read_outcome_pointer(pointer)
            if pointer_kind == _NO_GROWTH_KIND:
                prior_no_growth, growth, admitted = self._verified_no_growth(closure, selected_ref)
                growth_ref = prior_no_growth.growth_receipt_ref
            else:
                growth_ref = selected_ref
                growth, admitted = self._verified_growth(closure, growth_ref)

            attempt_pointer = pointer.with_suffix(".attempt.json")
            if not attempt_pointer.exists():
                raise ValueError("acquisition_world_growth_attempt_missing")
            attempt_ref = json.loads(attempt_pointer.read_text())["receipt_ref"]
            attempt = AcquisitionWorldGrowthAttempt.model_validate(
                self._read(attempt_ref, _ATTEMPT_KIND)
            )
            reconcile_authority_ref(
                artifact_store=self.artifact_store,
                event_log=self.event_log,
                cas_ref=attempt_ref,
                expected_tenant_id=closure.tenant_id,
                expected_cell_id=closure.cell_id,
                expected_run_id=closure.run_id,
                expected_job_id=closure.source_job_id,
            )
            if (
                attempt.selection != selected
                or attempt.binding_id != growth.binding_id
                or attempt.owner_receipt_refs != growth.live_evidence_refs
                or admitted.passport_id != growth.passport_id
            ):
                raise ValueError("acquisition_world_growth_attempt_binding_mismatch")
            for evidence_ref in attempt.owner_receipt_refs:
                if not self.artifact_store.verify(evidence_ref).ok:
                    raise ValueError("acquisition_world_growth_evidence_unreadable")

            before_state = data_forge_read_api.catalog.project_catalog_acquisition_state(
                self.authority.baseline_path, overlay_path=overlay_path
            )
            before = tuple(
                _PriorMembership.model_validate(
                    {key: getattr(row, key) for key in _PriorMembership.model_fields}
                )
                for row in before_state.epochs
            )
            measured_attempt = AcquisitionWorldGrowthAttempt.model_validate(
                {**attempt.model_dump(mode="python"), "before": before}
            )
            rechecked_growth = self._finish_admission(
                closure,
                measured_attempt,
                growth.activation,
                action_phase_ref=action_phase_ref,
            )
            if rechecked_growth is not None:
                raise ValueError("acquisition_duplicate_action_membership_grew")

            after_state = data_forge_read_api.catalog.project_catalog_acquisition_state(
                self.authority.baseline_path, overlay_path=overlay_path
            )
            after = tuple(
                _PriorMembership.model_validate(
                    {key: getattr(row, key) for key in _PriorMembership.model_fields}
                )
                for row in after_state.epochs
            )
            receipt = AcquisitionWorldGrowthNoGrowthReceipt(
                selection=selected,
                growth_receipt_ref=growth_ref,
                attempt_ref=attempt_ref,
                binding_id=growth.binding_id,
                passport_id=growth.passport_id,
                observed_admitted_observation_count=admitted.admitted_observation_count,
                live_evidence_refs=attempt.owner_receipt_refs,
                before=before,
                after=after,
                action_phase_ref=action_phase_ref,
            )
            receipt_ref = self._persist(
                closure,
                receipt.model_dump(mode="json"),
                _NO_GROWTH_KIND,
                "polisyos.runtime.AcquisitionWorldGrowthNoGrowthReceipt",
                "admission_no_growth",
            )
            verified_receipt = AcquisitionWorldGrowthNoGrowthReceipt.model_validate(
                self._read(receipt_ref, _NO_GROWTH_KIND)
            )
            if verified_receipt != receipt:
                raise ValueError("acquisition_no_growth_receipt_readback_mismatch")
            self._prepare_action_outcome(
                closure, selected, action_phase_ref, _NO_GROWTH_KIND, receipt_ref
            )
            self._write_pointer(pointer, receipt_ref, receipt_kind=_NO_GROWTH_KIND)
            self._select_action_outcome(
                closure,
                selected,
                action_phase_ref,
                _NO_GROWTH_KIND,
                receipt_ref,
            )
            owner_refs = (
                *growth.live_evidence_refs,
                growth_ref,
                receipt_ref,
                attempt_ref,
                *(() if growth.action_phase_ref is None else (growth.action_phase_ref,)),
            )
            if action_phase_ref is not None:
                owner_refs = (*owner_refs, action_phase_ref)
            return tuple(dict.fromkeys(owner_refs))

    def has_admission_attempt(self, closure: VerifiedAcquisitionRouteClosure) -> bool:
        """Recognize any prior attempt marker, including corrupt or unreadable state."""
        selected = self.selection(closure)
        if selected is None:
            return False
        pointer = self._growth_pointer(selected, create=False)
        return any(
            os.path.lexists(path)
            for path in (
                pointer,
                pointer.with_suffix(".attempt.json"),
                pointer.with_suffix(".deferred.json"),
                pointer.with_suffix(".admission.started"),
            )
        )

    def resume_deferred_admission(
        self,
        closure: VerifiedAcquisitionRouteClosure,
        action_phase_ref: str | None = None,
    ) -> tuple[
        tuple[str, ...],
        AcquisitionWorldGrowthReceipt | PersistedSemanticEpochProductionReceipt,
    ]:
        """Admit original durable evidence under new authority, without another live fetch."""
        selected = self.selection(closure)
        if selected is None:
            raise ValueError("acquisition_deferred_admission_missing")
        if action_phase_ref is not None:
            self._validate_action_phase(closure, selected, action_phase_ref)
            _selector_path, selector = self._read_action_selector(
                closure, selected, action_phase_ref
            )
            if selector.state != "executing":
                raise ValueError("acquisition_action_outcome_already_selected")
        overlay_path, _ = self._paths(selected)
        with data_forge_read_api.catalog.acquisition_overlay_admission_fence(overlay_path):
            deferral_ref, deferral, attempt = self._load_deferral(closure)
            fence = self._growth_pointer(selected).with_suffix(".admission.started")
            with fence.open("x") as stream:
                stream.write(
                    json.dumps(
                        {
                            "action_phase_ref": action_phase_ref,
                            "deferral_ref": deferral_ref,
                        },
                        sort_keys=True,
                    )
                    if action_phase_ref is not None
                    else deferral_ref
                )
                stream.flush()
                os.fsync(stream.fileno())
            self._sync_directory(fence.parent)
            result = self._admit_stored_attempt(
                closure,
                deferral.attempt_ref,
                attempt,
                action_phase_ref=action_phase_ref,
            )
            if isinstance(result, PersistedSemanticEpochProductionReceipt):
                # The updated negative is durable before another action can be eligible.
                fence.unlink()
                self._sync_directory(fence.parent)
            elif result is None:
                raise ValueError("acquisition_deferred_admission_outcome_not_established")
            return attempt.owner_receipt_refs, result

    def _load_deferral(
        self, closure: VerifiedAcquisitionRouteClosure
    ) -> tuple[str, AcquisitionWorldGrowthDeferral, AcquisitionWorldGrowthAttempt]:
        selected = self.selection(closure)
        if selected is None:
            raise ValueError("acquisition_deferred_admission_missing")
        pointer = self._growth_pointer(selected, create=False)
        if pointer.exists():
            raise ValueError("acquisition_deferred_admission_already_delivered")
        if pointer.with_suffix(".admission.started").exists():
            raise ValueError("acquisition_deferred_admission_outcome_not_established")
        ref = json.loads(pointer.with_suffix(".deferred.json").read_text())["receipt_ref"]
        deferral = AcquisitionWorldGrowthDeferral.model_validate(self._read(ref, _DEFERRAL_KIND))
        if (
            json.loads(pointer.with_suffix(".attempt.json").read_text())["receipt_ref"]
            != deferral.attempt_ref
        ):
            raise ValueError("acquisition_deferred_admission_attempt_mismatch")
        attempt = AcquisitionWorldGrowthAttempt.model_validate(
            self._read(deferral.attempt_ref, _ATTEMPT_KIND)
        )
        if attempt.selection != selected:
            raise ValueError("acquisition_world_growth_case_mismatch")
        for owner_ref in (ref, deferral.attempt_ref):
            reconcile_authority_ref(
                artifact_store=self.artifact_store,
                event_log=self.event_log,
                cas_ref=owner_ref,
                expected_tenant_id=closure.tenant_id,
                expected_cell_id=closure.cell_id,
                expected_run_id=closure.run_id,
                expected_job_id=closure.source_job_id,
            )
        self._verified_negative(attempt, deferral.negative_receipt)
        return ref, deferral, attempt

    def _verified_negative(
        self,
        attempt: AcquisitionWorldGrowthAttempt,
        negative: PersistedSemanticEpochProductionReceipt,
    ) -> PersistedSemanticEpochProductionReceipt:
        statement = contracts.epoch.load_verified_epoch_statement(
            store=self.artifact_store,
            ref=negative.receipt_ref,
            expected_kind="epoch.production_receipt",
            expected_media_type="application/vnd.polisyos.epoch-production-receipt+json",
        )
        verified = PersistedSemanticEpochProductionReceipt.model_validate(
            {
                **statement,
                "receipt_ref": negative.receipt_ref,
                "receipt_content_hash": negative.receipt_content_hash,
            }
        )
        if (
            verified != negative
            or verified.production_mode != "acquisition_finalization"
            or verified.status not in {"not_established", "contested"}
            or verified.prepared_epoch_ref is None
            or verified.admitted_boundary_evidence_ref is None
        ):
            raise ValueError("acquisition_deferred_admission_negative_unverified")
        prepared_statement = contracts.epoch.load_verified_epoch_statement(
            store=self.artifact_store,
            ref=verified.prepared_epoch_ref,
            expected_kind="epoch.prepared",
        )
        prepared = PreparedSemanticEpoch.model_validate(
            {
                **prepared_statement,
                "prepared_epoch_ref": verified.prepared_epoch_ref,
                "prepared_content_hash": contracts.epoch.epoch_semantic_content_hash(
                    domain="polisyos.epoch.prepared.v1", value=prepared_statement
                ),
            }
        )
        admitted = contracts.epoch.AdmittedAcquisitionBoundaryEvidence.model_validate(
            contracts.epoch.load_verified_epoch_statement(
                store=self.artifact_store,
                ref=verified.admitted_boundary_evidence_ref,
                expected_kind="epoch.admitted_acquisition_boundary_evidence",
            )
        )
        passport = acquisition_executor.AdmissionPassport.model_validate(
            contracts.epoch.load_verified_epoch_statement(
                store=self.artifact_store,
                ref=admitted.passport_ref,
                expected_kind="epoch.acquisition_passport_snapshot",
            )
        )
        selected = attempt.selection
        query = build_epoch_resolution_query_from_evidence(
            artifact_store=self.artifact_store,
            scope_identity=selected.epoch_scope_identity,
            authority_purpose=selected.authority_purpose,
            valid_effect_coordinate_evidence_ref=selected.valid_effect_coordinate_evidence_ref,
            visibility_knowledge_cutoff_evidence_ref=selected.visibility_knowledge_cutoff_evidence_ref,
            purpose_admission_cutoff_evidence_ref=selected.purpose_admission_cutoff_evidence_ref,
        )
        if (
            prepared.query != query
            or verified.requested_query_context_ref != query.requested_query_context_ref
            or admitted.epoch_id != selected.epoch_id
            or admitted.prepared_epoch_ref != prepared.prepared_epoch_ref
            or admitted.prepared_epoch_content_hash != prepared.prepared_content_hash
            or admitted.semantic_epoch_stamp != prepared.stamp
            or admitted.semantic_candidate_ref != passport.semantic_boundary_candidate_ref
            or passport.live_source_execution != attempt.evidence
            or passport.variable_id != attempt.target_variable
            or passport.epoch_id != selected.epoch_id
            or passport.prepared_semantic_epoch_ref != prepared.prepared_epoch_ref
            or passport.semantic_epoch_stamp != prepared.stamp
            or passport.semantic_boundary_candidate_ref not in prepared.boundary_candidate_refs
        ):
            raise ValueError("acquisition_deferred_admission_native_binding_mismatch")
        required_refs = {
            str(attempt.evidence.raw_artifact_id),
            str(attempt.evidence.evidence_bundle_ref.artifact_id),
            str(attempt.evidence.data_snapshot_ref.artifact_id),
            str(attempt.evidence.normalized_data_artifact_id),
        }
        if not required_refs.issubset(attempt.owner_receipt_refs):
            raise ValueError("acquisition_deferred_admission_evidence_incomplete")
        for ref in attempt.owner_receipt_refs:
            if not self.artifact_store.verify(ref).ok:
                raise ValueError("acquisition_deferred_admission_evidence_unreadable")
        return verified

    def _finish_admission(
        self,
        closure: VerifiedAcquisitionRouteClosure,
        attempt: AcquisitionWorldGrowthAttempt,
        activation: acquisition_executor.ActivatedSemanticEpochAdmissionReceipt,
        *,
        action_phase_ref: str | None = None,
    ) -> AcquisitionWorldGrowthReceipt | None:
        selected = attempt.selection
        overlay_path, _ = self._paths(selected)
        overlay = data_forge_read_api.catalog.CatalogAcquisitionOverlay(
            self.authority.baseline_path, overlay_path
        )
        admitted = acquisition_executor.resolve_activated_semantic_epoch_admission(
            receipt=activation,
            artifact_store=self.artifact_store,
            overlay=overlay,
            authority=self.authority,
            epoch_deployment=self.epoch_deployment,
        )
        after = data_forge_read_api.catalog.project_catalog_acquisition_state(
            self.authority.baseline_path, overlay_path=overlay_path
        )
        passports = tuple(row for row in after.passports if row.passport_id == admitted.passport_id)
        if (
            len(passports) != 1
            or passports[0].variable_id != attempt.target_variable
            or passports[0].source_lane != "live_fetch"
        ):
            raise ValueError("acquisition_world_growth_passport_route_mismatch")
        delta = admitted_membership_delta(
            before=attempt.before,
            after=after.epochs,
            epoch_id=selected.epoch_id,
            passport_id=admitted.passport_id,
        )
        if delta <= 0:
            return None
        return AcquisitionWorldGrowthReceipt(
            selection=selected,
            binding_id=attempt.binding_id,
            activation=activation,
            passport_id=admitted.passport_id,
            admitted_observation_delta=delta,
            previously_active_observations=admitted.admitted_observation_count - delta,
            live_evidence_refs=attempt.owner_receipt_refs,
            action_phase_ref=action_phase_ref,
        )

    def _recover_current_positive_from_activation(
        self,
        closure: VerifiedAcquisitionRouteClosure,
        selected: AcquisitionWorldGrowthRoute,
        attempt_ref: str,
        action_phase_ref: str,
    ) -> AcquisitionWorldGrowthRecoveredOutcome:
        attempt = AcquisitionWorldGrowthAttempt.model_validate(
            self._read(attempt_ref, _ATTEMPT_KIND)
        )
        if attempt.selection != selected:
            raise ValueError("acquisition_world_growth_case_mismatch")
        overlay_path, _ = self._paths(selected, create=False)
        projection = data_forge_read_api.catalog.project_catalog_acquisition_state(
            self.authority.baseline_path, overlay_path=overlay_path
        )
        native = []
        for event in projection.events:
            if event.receipt_kind != "epoch.activated_overlay_admission_receipt":
                continue
            ref = self._native_ref(event.receipt_ref)
            value = contracts.epoch.ActivatedOverlayAdmissionStatement.model_validate(
                contracts.epoch.load_verified_epoch_statement(
                    store=self.artifact_store, ref=ref, expected_kind=event.receipt_kind
                )
            )
            if value.epoch_id == selected.epoch_id:
                native.append((ref, value))
        if len(native) != 1:
            raise ValueError("acquisition_owner_outcome_not_established")
        ref, active = native[0]
        admitted = contracts.epoch.AdmittedAcquisitionBoundaryEvidence.model_validate(
            contracts.epoch.load_verified_epoch_statement(
                store=self.artifact_store,
                ref=active.admitted_boundary_evidence_ref,
                expected_kind="epoch.admitted_acquisition_boundary_evidence",
            )
        )
        passport = acquisition_executor.AdmissionPassport.model_validate(
            contracts.epoch.load_verified_epoch_statement(
                store=self.artifact_store,
                ref=admitted.passport_ref,
                expected_kind="epoch.acquisition_passport_snapshot",
            )
        )
        if passport.live_source_execution != attempt.evidence:
            raise ValueError("acquisition_world_growth_attempt_evidence_mismatch")
        activation = acquisition_executor.ActivatedSemanticEpochAdmissionReceipt(
            passport_ref=admitted.passport_ref,
            prepared_epoch_ref=active.prepared_semantic_epoch_ref,
            pending_overlay_receipt_ref=active.pending_overlay_receipt_ref,
            semantic_epoch_production_receipt_ref=active.semantic_epoch_production_receipt_ref,
            overlay_admission_receipt_ref=ref,
            native_membership_receipt_ref=admitted.native_membership_receipt_ref,
            semantic_denominator_receipt_ref=admitted.semantic_denominator_receipt_ref,
            semantic_projection_verification_receipt_ref=admitted.semantic_projection_verification_receipt_ref,
            semantic_epoch_stamp=active.semantic_epoch_stamp,
            activation_state="active",
        )
        growth = self._finish_admission(
            closure, attempt, activation, action_phase_ref=action_phase_ref
        )
        if growth is None:
            raise ValueError("acquisition_owner_outcome_not_established")
        growth_ref = self.persist_growth(closure, growth)
        owner_refs = tuple(
            dict.fromkeys((*growth.live_evidence_refs, attempt_ref, growth_ref, action_phase_ref))
        )
        return AcquisitionWorldGrowthRecoveredOutcome(
            disposition="world_committed",
            action_phase_ref=action_phase_ref,
            outcome_receipt_ref=growth_ref,
            growth_receipt_ref=growth_ref,
            growth=growth,
            owner_receipt_refs=owner_refs,
        )

    def _recover_selected_action_outcome(
        self,
        closure: VerifiedAcquisitionRouteClosure,
        selected: AcquisitionWorldGrowthRoute,
        action_phase_ref: str,
        receipt_kind: str,
        receipt_ref: str,
    ) -> AcquisitionWorldGrowthRecoveredOutcome:
        """Recover an owner CAS; route pointers are repairable locators, never authority."""
        route_pointer = self._growth_pointer(selected, create=False)
        if receipt_kind not in {_GROWTH_KIND, _NO_GROWTH_KIND}:
            raise ValueError("acquisition_action_route_selector_binding_mismatch")
        if receipt_kind == _NO_GROWTH_KIND:
            no_growth, growth, _admitted = self._verified_no_growth(
                closure, receipt_ref, require_route_pointer=False
            )
            if no_growth.action_phase_ref != action_phase_ref:
                raise ValueError("acquisition_action_outcome_scope_mismatch")
            self._write_pointer(route_pointer, receipt_ref, receipt_kind=receipt_kind)
            owner_ref_list = [
                *growth.live_evidence_refs,
                no_growth.growth_receipt_ref,
                receipt_ref,
                no_growth.attempt_ref,
            ]
            if growth.action_phase_ref is not None:
                owner_ref_list.append(growth.action_phase_ref)
            owner_ref_list.append(action_phase_ref)
            owner_refs = tuple(dict.fromkeys(owner_ref_list))
            return AcquisitionWorldGrowthRecoveredOutcome(
                disposition="quarantined_no_growth",
                action_phase_ref=action_phase_ref,
                outcome_receipt_ref=receipt_ref,
                growth_receipt_ref=no_growth.growth_receipt_ref,
                growth=growth,
                no_growth_receipt=no_growth,
                owner_receipt_refs=owner_refs,
            )
        growth, _admitted = self._verified_growth(closure, receipt_ref)
        if growth.action_phase_ref != action_phase_ref:
            raise ValueError("acquisition_action_outcome_scope_mismatch")
        self._write_pointer(route_pointer, receipt_ref, receipt_kind=receipt_kind)
        owner_refs = tuple(
            dict.fromkeys((*growth.live_evidence_refs, receipt_ref, action_phase_ref))
        )
        return AcquisitionWorldGrowthRecoveredOutcome(
            disposition="world_committed",
            action_phase_ref=action_phase_ref,
            outcome_receipt_ref=receipt_ref,
            growth_receipt_ref=receipt_ref,
            growth=growth,
            owner_receipt_refs=owner_refs,
        )

    def recover_admission(
        self,
        closure: VerifiedAcquisitionRouteClosure,
        action_phase_ref: str,
    ) -> AcquisitionWorldGrowthRecoveredOutcome:
        """Recover only an outcome bound to the current durable executing action head."""
        selected = self.selection(closure)
        if selected is None:
            raise ValueError("acquisition_live_evidence_not_admitted")
        self._validate_action_phase(closure, selected, action_phase_ref)
        snapshot = self._current_action_outcome_snapshot(closure, selected)
        if (
            snapshot is not None
            and snapshot.executing_phase_ref == action_phase_ref
            and snapshot.selection_phase is not None
        ):
            selection = snapshot.selection_phase
            if (
                selection.receipt_phase != "outcome_selected"
                or selection.predecessor_receipt_ref != action_phase_ref
                or len(selection.owner_receipt_refs) != 1
            ):
                raise ValueError("acquisition_action_selection_binding_mismatch")
            selected_ref = selection.owner_receipt_refs[0]
            selected_kind = self.artifact_store.get_manifest(selected_ref).kind
            if selected_kind not in {_GROWTH_KIND, _NO_GROWTH_KIND}:
                raise ValueError("acquisition_action_selection_outcome_kind_invalid")
            return self._recover_selected_action_outcome(
                closure, selected, action_phase_ref, selected_kind, selected_ref
            )
        overlay_path, _ = self._paths(selected)
        remeasure_prior = False
        with data_forge_read_api.catalog.acquisition_overlay_admission_fence(overlay_path):
            selector_path, selector = self._read_action_selector(
                closure, selected, action_phase_ref
            )
            route_pointer = self._growth_pointer(selected, create=False)
            if selector.state == "selected":
                return self._recover_selected_action_outcome(
                    closure,
                    selected,
                    action_phase_ref,
                    str(selector.receipt_kind),
                    str(selector.receipt_ref),
                )
            if selector.state == "prepared":
                prepared_kind = str(selector.receipt_kind)
                prepared_ref = str(selector.receipt_ref)
                if prepared_kind == _NO_GROWTH_KIND:
                    prepared, _growth, _admitted = self._verified_no_growth(
                        closure, prepared_ref, require_route_pointer=False
                    )
                    if prepared.action_phase_ref != action_phase_ref:
                        raise ValueError("acquisition_action_outcome_scope_mismatch")
                else:
                    prepared, _admitted = self._verified_growth(closure, prepared_ref)
                    if prepared.action_phase_ref != action_phase_ref:
                        raise ValueError("acquisition_action_outcome_scope_mismatch")
                self._write_pointer(route_pointer, prepared_ref, receipt_kind=prepared_kind)
                self._select_action_outcome(
                    closure, selected, action_phase_ref, prepared_kind, prepared_ref
                )
                return self._recover_selected_action_outcome(
                    closure, selected, action_phase_ref, prepared_kind, prepared_ref
                )
            if route_pointer.exists():
                route_kind, route_ref = self._read_outcome_pointer(route_pointer)
                if route_kind == _NO_GROWTH_KIND:
                    no_growth = AcquisitionWorldGrowthNoGrowthReceipt.model_validate(
                        self._read(route_ref, _NO_GROWTH_KIND)
                    )
                    if no_growth.action_phase_ref == action_phase_ref:
                        self._write_action_selector(
                            selector_path,
                            selector.model_copy(
                                update={
                                    "state": "selected",
                                    "receipt_kind": _NO_GROWTH_KIND,
                                    "receipt_ref": route_ref,
                                }
                            ),
                        )
                        return self._recover_selected_action_outcome(
                            closure,
                            selected,
                            action_phase_ref,
                            _NO_GROWTH_KIND,
                            route_ref,
                        )
                else:
                    growth = AcquisitionWorldGrowthReceipt.model_validate(
                        self._read(route_ref, _GROWTH_KIND)
                    )
                    if growth.action_phase_ref == action_phase_ref:
                        self._write_action_selector(
                            selector_path,
                            selector.model_copy(
                                update={
                                    "state": "selected",
                                    "receipt_kind": _GROWTH_KIND,
                                    "receipt_ref": route_ref,
                                }
                            ),
                        )
                        return self._recover_selected_action_outcome(
                            closure, selected, action_phase_ref, _GROWTH_KIND, route_ref
                        )
                    remeasure_prior = True
            attempt_pointer = self._growth_pointer(selected, create=False).with_suffix(
                ".attempt.json"
            )
            if attempt_pointer.exists():
                attempt_ref = json.loads(attempt_pointer.read_text()).get("receipt_ref")
                if not isinstance(attempt_ref, str):
                    raise ValueError("acquisition_world_growth_attempt_pointer_unverified")
                attempt = AcquisitionWorldGrowthAttempt.model_validate(
                    self._read(attempt_ref, _ATTEMPT_KIND)
                )
                if attempt.action_phase_ref == action_phase_ref:
                    return self._recover_current_positive_from_activation(
                        closure, selected, attempt_ref, action_phase_ref
                    )
                if route_pointer.exists():
                    # A previous route receipt is evidence for remeasurement only. It is
                    # never the result of this action generation.
                    remeasure_prior = True
            fence = self._growth_pointer(selected, create=False).with_suffix(".admission.started")
            if fence.exists():
                try:
                    fence_value = json.loads(fence.read_text())
                except json.JSONDecodeError as exc:
                    raise ValueError("acquisition_deferred_action_fence_unverified") from exc
                if (
                    not isinstance(fence_value, dict)
                    or fence_value.get("action_phase_ref") != action_phase_ref
                    or not isinstance(fence_value.get("deferral_ref"), str)
                ):
                    raise ValueError("acquisition_deferred_action_fence_scope_mismatch")
                if not attempt_pointer.exists():
                    raise ValueError("acquisition_world_growth_attempt_missing")
                attempt_ref = json.loads(attempt_pointer.read_text()).get("receipt_ref")
                if not isinstance(attempt_ref, str):
                    raise ValueError("acquisition_world_growth_attempt_pointer_unverified")
                deferral_ref = fence_value["deferral_ref"]
                deferral = AcquisitionWorldGrowthDeferral.model_validate(
                    self._read(deferral_ref, _DEFERRAL_KIND)
                )
                if deferral.attempt_ref != attempt_ref:
                    raise ValueError("acquisition_deferred_admission_attempt_mismatch")
                return self._recover_current_positive_from_activation(
                    closure, selected, attempt_ref, action_phase_ref
                )
        if remeasure_prior:
            self.record_measured_no_growth(closure, action_phase_ref)
            return self.recover_admission(closure, action_phase_ref)
        raise ValueError("acquisition_owner_outcome_not_established")

    def _native_ref(self, ref: str) -> artifacts.ArtifactRef:
        manifest = self.artifact_store.get_manifest(ref)
        return artifacts.ArtifactRef(
            artifact_id=artifacts.ArtifactID.model_validate(ref),
            kind=manifest.kind,
            media_type=manifest.media_type,
        )

    def persist_growth(
        self,
        closure: VerifiedAcquisitionRouteClosure,
        growth: AcquisitionWorldGrowthReceipt,
    ) -> str:
        """Persist the supplier's measured activation before phase advancement."""
        ref = self._persist(
            closure,
            growth.model_dump(mode="json"),
            _GROWTH_KIND,
            AcquisitionWorldGrowthReceipt.ARTIFACT_SCHEMA_NAME,
            "world_committed",
        )
        pointer = self._growth_pointer(growth.selection)
        self._prepare_action_outcome(
            closure, growth.selection, growth.action_phase_ref, _GROWTH_KIND, ref
        )
        self._write_pointer(pointer, ref, receipt_kind=_GROWTH_KIND)
        self._select_action_outcome(
            closure,
            growth.selection,
            growth.action_phase_ref,
            _GROWTH_KIND,
            ref,
        )
        return ref

    def _growth_pointer(
        self, selected: AcquisitionWorldGrowthRoute, *, create: bool = True
    ) -> Path:
        overlay_path, _ = self._paths(selected, create=create)
        identity = hashlib.sha256(canon.to_canonical_bytes(list(selected.key))).hexdigest()
        return overlay_path.parent / (identity + ".growth.json")

    @staticmethod
    def _read_outcome_pointer(pointer: Path) -> tuple[str, str]:
        value = json.loads(pointer.read_text())
        if not isinstance(value, dict) or set(value) not in (
            {"receipt_ref"},
            {"receipt_ref", "receipt_kind"},
        ):
            raise ValueError("acquisition_world_growth_pointer_unverified")
        ref = value.get("receipt_ref")
        kind = value.get("receipt_kind", _GROWTH_KIND)
        if not isinstance(ref, str) or kind not in (_GROWTH_KIND, _NO_GROWTH_KIND):
            raise ValueError("acquisition_world_growth_pointer_unverified")
        return kind, ref

    @staticmethod
    def _write_pointer(pointer: Path, ref: str, *, receipt_kind: str | None = None) -> None:
        value = {"receipt_ref": ref}
        if receipt_kind is not None:
            if receipt_kind not in (_GROWTH_KIND, _NO_GROWTH_KIND):
                raise ValueError("acquisition_world_growth_pointer_kind_invalid")
            value["receipt_kind"] = receipt_kind
        temporary = pointer.with_suffix(".tmp")
        with temporary.open("w") as stream:
            stream.write(json.dumps(value, sort_keys=True) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, pointer)
        AcquisitionWorldGrowthBridge._sync_directory(pointer.parent)

    @staticmethod
    def _sync_directory(path: Path) -> None:
        descriptor = os.open(path, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

    def _current_action_outcome_snapshot(
        self,
        closure: VerifiedAcquisitionRouteClosure,
        selected: AcquisitionWorldGrowthRoute,
    ) -> _CurrentActionOutcomeSnapshot | None:
        reader = self.action_head_sink
        if reader is None:
            return None
        return reader.current_action_outcome(
            tenant_id=closure.tenant_id,
            cell_id=closure.cell_id,
            run_id=closure.run_id,
            source_job_id=closure.source_job_id,
            route_id=selected.route_id,
        )

    @staticmethod
    def _action_phase_matches_closure(
        closure: VerifiedAcquisitionRouteClosure,
        selected: AcquisitionWorldGrowthRoute,
        phase: AcquisitionRoutePhaseReceipt,
    ) -> bool:
        return (
            phase.receipt_phase == "executing"
            and phase.tenant_id == closure.tenant_id
            and phase.cell_id == closure.cell_id
            and phase.run_id == closure.run_id
            and phase.source_job_id == closure.source_job_id
            and phase.route_id == selected.route_id
            and phase.compiled_ref == closure.compiled_ref
            and phase.planner_report_hash == agent_action_content_hash(closure.planner_report)
            and phase.cost_basis_hash == closure.cost_basis_hash
        )

    @staticmethod
    def _required_outcome_kind(
        latest: AcquisitionRoutePhaseReceipt | AcquisitionRouteLoopReceipt,
    ) -> str | None:
        if isinstance(latest, AcquisitionRoutePhaseReceipt):
            if latest.receipt_phase == "world_committed_reentry_pending":
                return _GROWTH_KIND
            return None
        if latest.terminal_outcome == "quarantined_no_growth":
            return _NO_GROWTH_KIND
        return _GROWTH_KIND

    def _has_verified_admission_basis(self, closure: VerifiedAcquisitionRouteClosure) -> bool:
        """Verify a prior native admission only as the baseline for another measurement.

        This predicate cannot project the prior result as the current action outcome. Public
        readers use ``project_growth_outcome`` and require the latest action selector.
        """
        selected = self.selection(closure)
        if selected is None:
            return False
        overlay_path, _ = self._paths(selected, create=False)
        lock_path = data_forge_read_api.catalog.acquisition_overlay_admission_lock_path(
            overlay_path
        )
        pointer = self._growth_pointer(selected, create=False)
        if not lock_path.exists() or not pointer.exists():
            return False
        with data_forge_read_api.catalog.acquisition_overlay_admission_fence(overlay_path):
            if not pointer.exists():
                return False
            pointer_kind, pointer_ref = self._read_outcome_pointer(pointer)
            if pointer_kind == _GROWTH_KIND:
                self._verified_growth(closure, pointer_ref)
                return True
            self._verified_no_growth(closure, pointer_ref)
            return True

    def project_growth_outcome(
        self,
        closure: VerifiedAcquisitionRouteClosure,
    ) -> tuple[
        Literal["not_established", "no_growth", "admitted_delta"],
        AcquisitionWorldGrowthReceipt | None,
    ]:
        """Project only an owner CAS selected by a complete current ActionHead chain."""
        selected = self.selection(closure)
        if selected is None:
            return "not_established", None
        overlay_path, _ = self._paths(selected, create=False)
        lock_path = data_forge_read_api.catalog.acquisition_overlay_admission_lock_path(
            overlay_path
        )
        if not lock_path.exists():
            return "not_established", None
        with data_forge_read_api.catalog.acquisition_overlay_admission_fence(overlay_path):
            snapshot = self._current_action_outcome_snapshot(closure, selected)
            if snapshot is None:
                return "not_established", None
            phase, phase_ref = snapshot.executing_phase, snapshot.executing_phase_ref
            selection, selection_ref = (
                snapshot.selection_phase,
                snapshot.selection_phase_ref,
            )
            if phase is None or phase_ref is None or selection is None or selection_ref is None:
                return "not_established", None
            if not self._action_phase_matches_closure(closure, selected, phase):
                raise ValueError("acquisition_action_phase_source_binding_mismatch")
            identity_fields = (
                "tenant_id",
                "cell_id",
                "run_id",
                "source_job_id",
                "route_id",
                "action_generation",
                "job_id",
                "compiled_ref",
                "planner_report_hash",
                "cost_basis_hash",
                "decision_ref",
            )
            if (
                selection.receipt_phase != "outcome_selected"
                or selection.schema_version != "AcquisitionRoutePhaseReceipt@1.1"
                or selection.predecessor_receipt_ref != phase_ref
                or len(selection.owner_receipt_refs) != 1
                or any(
                    getattr(selection, field) != getattr(phase, field) for field in identity_fields
                )
            ):
                raise ValueError("acquisition_action_selection_binding_mismatch")
            outcome_ref = selection.owner_receipt_refs[0]
            outcome_kind = self.artifact_store.get_manifest(outcome_ref).kind
            required_kind = self._required_outcome_kind(snapshot.latest_receipt)
            if required_kind is not None and outcome_kind != required_kind:
                raise ValueError("acquisition_action_terminal_outcome_binding_mismatch")
            if outcome_kind == _GROWTH_KIND:
                growth, _admitted = self._verified_growth(closure, outcome_ref)
                if growth.action_phase_ref != phase_ref:
                    raise ValueError("acquisition_action_outcome_scope_mismatch")
                status: Literal["not_established", "no_growth", "admitted_delta"] = "admitted_delta"
            elif outcome_kind == _NO_GROWTH_KIND:
                no_growth, growth, _admitted = self._verified_no_growth(
                    closure, outcome_ref, require_route_pointer=False
                )
                if no_growth.action_phase_ref != phase_ref:
                    raise ValueError("acquisition_action_outcome_scope_mismatch")
                status = "no_growth"
            else:
                raise ValueError("acquisition_action_selection_outcome_kind_invalid")
            if self._current_action_outcome_snapshot(closure, selected) != snapshot:
                return "not_established", None
            return status, growth

    def project_growth(
        self, closure: VerifiedAcquisitionRouteClosure
    ) -> AcquisitionWorldGrowthReceipt | None:
        """Project only owner evidence selected by a complete current ActionHead chain."""
        status, growth = self.project_growth_outcome(closure)
        return growth if status != "not_established" else None

    def _verified_growth(
        self, closure: VerifiedAcquisitionRouteClosure, ref: str
    ) -> tuple[
        AcquisitionWorldGrowthReceipt,
        data_forge_read_api.catalog.OverlayAdmissionReceipt,
    ]:
        growth = AcquisitionWorldGrowthReceipt.model_validate(self._read(ref, _GROWTH_KIND))
        if self.selection(closure) != growth.selection:
            raise ValueError("acquisition_world_growth_case_mismatch")
        overlay_path, _ = self._paths(growth.selection)
        overlay = data_forge_read_api.catalog.CatalogAcquisitionOverlay(
            self.authority.baseline_path, overlay_path
        )
        admitted = acquisition_executor.resolve_activated_semantic_epoch_admission(
            receipt=growth.activation,
            artifact_store=self.artifact_store,
            overlay=overlay,
            authority=self.authority,
            epoch_deployment=self.epoch_deployment,
        )
        if (
            admitted.passport_id != growth.passport_id
            or admitted.admitted_observation_count
            != growth.previously_active_observations + growth.admitted_observation_delta
        ):
            raise ValueError("acquisition_world_growth_membership_drift")
        reconcile_authority_ref(
            artifact_store=self.artifact_store,
            event_log=self.event_log,
            cas_ref=ref,
            expected_tenant_id=closure.tenant_id,
            expected_cell_id=closure.cell_id,
            expected_run_id=closure.run_id,
            expected_job_id=closure.source_job_id,
        )
        return growth, admitted

    def _verified_no_growth(
        self,
        closure: VerifiedAcquisitionRouteClosure,
        ref: str,
        *,
        require_route_pointer: bool = True,
    ) -> tuple[
        AcquisitionWorldGrowthNoGrowthReceipt,
        AcquisitionWorldGrowthReceipt,
        data_forge_read_api.catalog.OverlayAdmissionReceipt,
    ]:
        """Reverify a selected zero-delta receipt against current owner state."""
        selected = self.selection(closure)
        if selected is None:
            raise ValueError("acquisition_world_growth_selection_missing")
        pointer = self._growth_pointer(selected, create=False)
        if require_route_pointer:
            pointer_kind, pointer_ref = self._read_outcome_pointer(pointer)
            if pointer_kind != _NO_GROWTH_KIND or pointer_ref != ref:
                raise ValueError("acquisition_no_growth_pointer_binding_mismatch")
        receipt = AcquisitionWorldGrowthNoGrowthReceipt.model_validate(
            self._read(ref, _NO_GROWTH_KIND)
        )
        if receipt.selection != selected:
            raise ValueError("acquisition_world_growth_case_mismatch")
        reconcile_authority_ref(
            artifact_store=self.artifact_store,
            event_log=self.event_log,
            cas_ref=ref,
            expected_tenant_id=closure.tenant_id,
            expected_cell_id=closure.cell_id,
            expected_run_id=closure.run_id,
            expected_job_id=closure.source_job_id,
        )
        growth, admitted = self._verified_growth(closure, receipt.growth_receipt_ref)
        attempt_pointer = pointer.with_suffix(".attempt.json")
        if not attempt_pointer.exists():
            raise ValueError("acquisition_world_growth_attempt_missing")
        attempt_ref = json.loads(attempt_pointer.read_text()).get("receipt_ref")
        if not isinstance(attempt_ref, str) or attempt_ref != receipt.attempt_ref:
            raise ValueError("acquisition_no_growth_attempt_binding_mismatch")
        attempt = AcquisitionWorldGrowthAttempt.model_validate(
            self._read(attempt_ref, _ATTEMPT_KIND)
        )
        reconcile_authority_ref(
            artifact_store=self.artifact_store,
            event_log=self.event_log,
            cas_ref=attempt_ref,
            expected_tenant_id=closure.tenant_id,
            expected_cell_id=closure.cell_id,
            expected_run_id=closure.run_id,
            expected_job_id=closure.source_job_id,
        )
        if (
            attempt.selection != selected
            or attempt.binding_id != receipt.binding_id
            or attempt.binding_id != growth.binding_id
            or attempt.owner_receipt_refs != receipt.live_evidence_refs
            or attempt.owner_receipt_refs != growth.live_evidence_refs
            or admitted.passport_id != receipt.passport_id
            or admitted.passport_id != growth.passport_id
            or admitted.admitted_observation_count != receipt.observed_admitted_observation_count
            or receipt.before != receipt.after
        ):
            raise ValueError("acquisition_no_growth_attempt_binding_mismatch")
        for evidence_ref in receipt.live_evidence_refs:
            if not self.artifact_store.verify(evidence_ref).ok:
                raise ValueError("acquisition_world_growth_evidence_unreadable")

        overlay_path, _ = self._paths(selected, create=False)
        current_state = data_forge_read_api.catalog.project_catalog_acquisition_state(
            self.authority.baseline_path, overlay_path=overlay_path
        )
        current = tuple(
            _PriorMembership.model_validate(
                {key: getattr(row, key) for key in _PriorMembership.model_fields}
            )
            for row in current_state.epochs
        )
        current_selected = tuple(row for row in current if row.epoch_id == selected.epoch_id)
        recorded_selected = tuple(row for row in receipt.after if row.epoch_id == selected.epoch_id)
        if (
            current_selected != recorded_selected
            or admitted_membership_delta(
                before=receipt.before,
                after=current,
                epoch_id=selected.epoch_id,
                passport_id=receipt.passport_id,
            )
            != 0
        ):
            raise ValueError("acquisition_no_growth_membership_drift")
        return receipt, growth, admitted

    def _read(self, ref: str, kind: str) -> dict[str, Any]:
        from polisyos.core.artifacts import artifact_ref_for_manifest, load_core_json_artifact

        schema_names = {
            _ATTEMPT_KIND: "AcquisitionWorldGrowthAttempt",
            _GROWTH_KIND: AcquisitionWorldGrowthReceipt.ARTIFACT_SCHEMA_NAME,
            _DEFERRAL_KIND: "AcquisitionWorldGrowthDeferral",
            _NO_GROWTH_KIND: "polisyos.runtime.AcquisitionWorldGrowthNoGrowthReceipt",
            _REENTRY_KIND: "polisyos.runtime.AcquisitionOverlayReentryReceipt",
        }
        schema_versions = {
            _ATTEMPT_KIND: ("1.0", "1.1"),
            _GROWTH_KIND: ("1.0", "1.1"),
            _DEFERRAL_KIND: ("1.0",),
            _NO_GROWTH_KIND: ("1.0", "1.1"),
            _REENTRY_KIND: ("2.0",),
        }
        if kind not in schema_names:
            raise ValueError("acquisition_world_growth_receipt_schema_contract_unregistered")
        expected_schema = tuple(
            artifacts.SchemaInfo(name=schema_names[kind], version=version)
            for version in schema_versions[kind]
        )
        manifest = contracts.epoch._preflight_core_manifest_profile(
            store=self.artifact_store,
            selector=ref,
            expected_kind=kind,
            expected_media_type="application/json",
            expected_canon=artifacts.CanonInfo.from_spec(canon.CanonSpec(forbid_floats=False)),
            expected_schema=expected_schema,
            require_selected_profile=False,
            expected_inputs=contracts.epoch._ExactManifestInputClosure(()),
        )
        selected_ref = artifact_ref_for_manifest(manifest)
        schema = manifest.artifact_schema
        if (
            manifest.authority is None
            or manifest.producer is None
            or manifest.producer.component != "polisyos.runtime.acquisition_world_growth"
            or (kind in schema_names and schema is None)
            or (
                kind in schema_names
                and schema is not None
                and (
                    schema.name != schema_names[kind] or schema.version not in schema_versions[kind]
                )
            )
        ):
            raise ValueError("acquisition_world_growth_receipt_unverified")
        payload = self.artifact_store.get_bytes(ref)
        if self.artifact_store.get_manifest(ref) != manifest:
            raise ValueError("acquisition_world_growth_receipt_unverified")
        if "sha256:" + hashlib.sha256(payload).hexdigest() != ref:
            raise ValueError("acquisition_world_growth_receipt_unverified")
        report = reconcile_authority_ref(
            artifact_store=self.artifact_store, event_log=self.event_log, cas_ref=ref
        )
        if report.durable_event_id is None:
            raise ValueError("acquisition_world_growth_receipt_unverified")
        value = load_core_json_artifact(
            self.artifact_store, selected_ref, raw_payload_bytes=payload
        )
        if (
            kind in (_GROWTH_KIND, _NO_GROWTH_KIND)
            and schema is not None
            and value.get("schema_version") != f"{schema_names[kind]}@{schema.version}"
        ):
            raise ValueError("acquisition_world_growth_receipt_schema_mismatch")
        return value

    def resume(self, closure: VerifiedAcquisitionRouteClosure, refs: tuple[str, ...]) -> str:
        """Read verified native activation and enter the original case at the next cycle."""
        from polisyos.core.artifacts import load_core_json_artifact

        _require_promotion_runtime_store_binding(self.promotion_runtime, self.artifact_store)
        current_action_job_id: str | None = None
        source_route_reader: AcquisitionRouteLoop | None = None
        if self._source_control_service is not None:
            source_route_reader = AcquisitionRouteLoop(
                control_store=self.control_store,
                artifact_store=self.artifact_store,
                event_log=self.event_log,
                core_source_resolver=(
                    self._source_control_service.resolve_completed_control_job_core_run_source
                ),
                tenant_id=closure.tenant_id,
                cell_id=closure.cell_id,
                action_outcome_reader=self.action_head_sink,
            )
            current_job = self.control_store.current_execution_job_record()
            current_action_job_id = current_job.job_id
            refreshed = source_route_reader.resolve_current_route(
                run_id=closure.run_id, action_job_id=current_action_job_id
            )
            if (
                refreshed.tenant_id != closure.tenant_id
                or refreshed.cell_id != closure.cell_id
                or refreshed.run_id != closure.run_id
                or refreshed.source_job_id != closure.source_job_id
                or refreshed.compiled_ref != closure.compiled_ref
                or refreshed.route_id != closure.route_id
                or refreshed.cost_basis_hash != closure.cost_basis_hash
                or refreshed.source_cycle != closure.source_cycle
                or refreshed.generation_run != closure.generation_run
            ):
                raise ValueError("acquisition_source_reaction_selector_changed")
            # Only the actual live owner output is used below. A caller-carried
            # same-basis flag or constructed closure cannot provide transitions.
            closure = refreshed
        growth_refs = tuple(
            ref for ref in refs if self.artifact_store.get_manifest(ref).kind == _GROWTH_KIND
        )
        if len(growth_refs) != 1:
            raise ValueError("acquisition_live_evidence_not_admitted")
        selected = self.selection(closure)
        if selected is None:
            raise ValueError("acquisition_live_evidence_not_admitted")
        overlay_path, _ = self._paths(selected)
        pointer = overlay_path.parent / (growth_refs[0].removeprefix("sha256:") + ".reentry.json")
        # This operation lock protects recovery pointers only. It deliberately
        # does not exclude native acquisition writers during an async N5 job.
        operation_path = _reentry_operation_namespace(overlay_path)
        with data_forge_read_api.catalog.acquisition_overlay_admission_fence(operation_path):
            growth, admitted = self._verified_growth(closure, growth_refs[0])
            if pointer.exists():
                ref = json.loads(pointer.read_text())["receipt_ref"]
                receipt = AcquisitionOverlayReentryReceipt.model_validate(
                    self._read(ref, _REENTRY_KIND)
                )
                self._validate_reentry(closure, growth, receipt)
                return str(ref)
            event_id = "evt_acquisition_reentry_" + growth_refs[0].removeprefix("sha256:")
            events = self.event_log.list_events(event_id=event_id, limit=2)
            if events:
                if len(events) != 1:
                    raise ValueError("acquisition_reentry_outcome_ambiguous")
                refs = tuple(
                    ref
                    for ref in events[0].event.artifact_refs
                    if self.artifact_store.get_manifest(ref).kind == _REENTRY_KIND
                )
                if len(refs) != 1:
                    raise ValueError("acquisition_reentry_outcome_ambiguous")
                receipt = AcquisitionOverlayReentryReceipt.model_validate(
                    self._read(refs[0], _REENTRY_KIND)
                )
                self._validate_reentry(closure, growth, receipt)
                self._write_pointer(pointer, refs[0])
                return refs[0]
            fence = pointer.with_suffix(".started")
            if fence.exists():
                raise ValueError("acquisition_reentry_outcome_not_established")
            payload = load_core_json_artifact(self.artifact_store, closure.source_payload_ref)
            models = payload.get("llm_models")
            model = str(models[0]) if isinstance(models, list) and models else None
            if model is None:
                raise ValueError("acquisition_reentry_model_unconfigured")
            passport = acquisition_executor.AdmissionPassport.model_validate(
                contracts.epoch.load_verified_epoch_statement(
                    store=self.artifact_store,
                    ref=growth.activation.passport_ref,
                    expected_kind="epoch.acquisition_passport_snapshot",
                )
            )
            overlay = data_forge_read_api.catalog.CatalogAcquisitionOverlay(
                self.authority.baseline_path,
                overlay_path,
            )
            observation_projection = overlay.read_activated_semantic_epoch_observations(
                receipt_ref=admitted.receipt_ref,
                artifact_store=self.artifact_store,
                passport=passport,
                authority=self.authority,
            )
            if (
                growth.activation.overlay_admission_receipt_ref != admitted.receipt_ref
                or growth.activation.passport_ref != observation_projection.passport_ref
                or growth.activation.activation_state != observation_projection.activation_state
                or growth.activation.passport_ref.kind != "epoch.acquisition_passport_snapshot"
                or passport.passport_id != growth.passport_id
                or passport.epoch_id != admitted.epoch_id
                or observation_projection.epoch_id != admitted.epoch_id
                or observation_projection.passport_id != admitted.passport_id
            ):
                raise ValueError("acquisition_world_growth_selected_observation_binding_mismatch")
            refresh = next(
                (
                    candidate_refresh
                    for candidate_refresh in self.config.candidate_world_refreshes
                    if candidate_refresh.key == growth.selection.key
                ),
                None,
            )
            controller_kwargs: dict[str, object] = {}
            if refresh is not None:
                context, handoff, currentness_resolver = self._candidate_world_context_handoff(
                    closure=closure,
                    growth=growth,
                    overlay=overlay,
                    observation_projection=observation_projection,
                    refresh=refresh,
                )
                controller_kwargs = {
                    "cycle_substrate_context": context,
                    "candidate_simulation_handoff": handoff,
                    "candidate_simulation_currentness_resolver": currentness_resolver,
                }
            controller = GenerationCycleController(
                repo_root=self.repo_root,
                model_id=model,
                promotion_runtime=self.promotion_runtime,
                **controller_kwargs,
            )
            with fence.open("x") as stream:
                stream.write(growth_refs[0])
                stream.flush()
                os.fsync(stream.fileno())
            receipt = async_tools.run_coro_sync(
                controller.reenter_after_active_acquisition_overlay(
                    original_run=closure.generation_run,
                    source_cycle=closure.source_cycle,
                    problem=closure.design_problem_basis,
                    overlay_receipt=admitted,
                    observation_projection=observation_projection,
                    baseline_path=self.authority.baseline_path,
                    overlay_path=overlay_path,
                    source_control_service=self._source_control_service,
                    budget_state=BudgetState.model_validate(
                        {
                            "limits": {
                                "run": {
                                    "key": "run",
                                    "max_usd": growth.selection.reentry_budget_usd,
                                }
                            }
                        }
                    ),
                )
            )
            # No copied-context borrowing is permitted. Re-read complete owner
            # selections on the deciding thread after async/numerical work, then
            # bind this re-entry artifact while every native writer is excluded.
            with data_forge_read_api.catalog.acquisition_overlay_admission_fence(overlay_path):
                current_growth, current_admitted = self._verified_growth(closure, growth_refs[0])
                current_projection = overlay.read_activated_semantic_epoch_observations(
                    receipt_ref=current_admitted.receipt_ref,
                    artifact_store=self.artifact_store,
                    passport=passport,
                    authority=self.authority,
                )
                if (
                    current_growth != growth
                    or current_admitted != admitted
                    or current_projection != observation_projection
                ):
                    raise ValueError("acquisition_reentry_native_selector_changed")
                if source_route_reader is not None:
                    final_source = source_route_reader.resolve_current_route(
                        run_id=closure.run_id, action_job_id=current_action_job_id
                    )
                    if final_source != closure:
                        raise ValueError("acquisition_reentry_source_selector_changed")
                self._validate_reentry(closure, growth, receipt)
                ref = self._persist(
                    closure,
                    receipt.model_dump(mode="json"),
                    _REENTRY_KIND,
                    "polisyos.runtime.AcquisitionOverlayReentryReceipt",
                    "reentry_terminal",
                    event_id=event_id,
                )
                self._write_pointer(pointer, ref)
                return ref

    def _candidate_world_context_handoff(
        self,
        *,
        closure: VerifiedAcquisitionRouteClosure,
        growth: AcquisitionWorldGrowthReceipt,
        overlay: data_forge_read_api.catalog.CatalogAcquisitionOverlay,
        observation_projection: (
            data_forge_read_api.catalog.ActivatedAcquisitionObservationProjection
        ),
        refresh: AcquisitionCandidateWorldRefresh,
    ) -> tuple[object, object, object]:
        """Materialize one owner-read-back row and persist a fresh leased context."""

        from polisyos.runtime.quality.candidate_simulation import (
            CandidateSimulationContextHandoff,
        )
        from polisyos.runtime.quality.cycle_substrate import (
            ConfiguredCandidateSimulationContextAdmissionOwner,
            CycleSubstrateContextArtifactOwner,
        )
        from polisyos.runtime.quality.data_state_substrate import (
            ControlledAcquisitionSlotBinding,
            build_acquired_observation_candidate_world,
            materialize_acquired_observation_snapshot,
            prepare_acquired_observation_snapshot,
        )
        from polisyos.runtime.quality.substrate_registry import (
            persist_substrate_registry,
        )
        from polisyos.runtime.quality.world_model_record import (
            world_model_artifact_views,
        )

        admission_owner = self.cycle_substrate_context_admission_owner
        control_store = self.control_store
        if (
            type(admission_owner) is not ConfiguredCandidateSimulationContextAdmissionOwner
            or control_store is None
            or not callable(getattr(control_store, "current_execution_job_record", None))
        ):
            raise ValueError("acquisition_candidate_context_owner_unavailable")
        configured_profile = admission_owner.configured_profile_for_selection_ref(
            refresh.profile_selection_ref
        )
        if (
            configured_profile.profile_selection_ref != refresh.profile_selection_ref
            or configured_profile.rule.target_world_slot != refresh.target_slot_id
            or configured_profile.context_inputs.world_model_record.authority_status
            not in {"bound", "limited"}
        ):
            raise ValueError("acquisition_candidate_context_profile_binding_mismatch")
        base_world_views = world_model_artifact_views(
            configured_profile.context_inputs.world_model_record
        )
        selected_rows = tuple(
            row
            for row in observation_projection.observations
            if row.observation.canonical_var == refresh.canonical_variable_id
        )
        if len(selected_rows) != 1:
            raise ValueError("acquisition_candidate_observation_not_unique")
        selected_row = selected_rows[0]
        base_world = configured_profile.context_inputs.world_model_record
        base_data_snapshot_ref = base_world_views.data_snapshot_ref
        if not self.artifact_store.verify(base_data_snapshot_ref).ok:
            raise ValueError("acquisition_candidate_base_snapshot_unverified")
        substrate_registry_ref = base_world_views.substrate_registry_ref
        if substrate_registry_ref is None:
            substrate_registry_ref = persist_substrate_registry(
                self.artifact_store,
                configured_profile.context_inputs.substrate_registry,
            )
        else:
            manifest = self.artifact_store.get_manifest(substrate_registry_ref)
            if manifest.kind != "runtime.quality.production_data_substrate_registry":
                raise ValueError("acquisition_candidate_substrate_registry_kind_mismatch")
        from polisyos.runtime.quality.acquisition_executor import AdmissionPassport

        passport_payload = contracts.epoch.load_verified_epoch_statement(
            store=self.artifact_store,
            ref=growth.activation.passport_ref,
            expected_kind="epoch.acquisition_passport_snapshot",
        )
        passport = AdmissionPassport.model_validate(passport_payload)
        if passport.variable_id != refresh.canonical_variable_id:
            raise ValueError("acquisition_candidate_context_profile_variable_mismatch")
        current_job = control_store.current_execution_job_record()
        if current_job.run_id != closure.run_id:
            raise ValueError("acquisition_candidate_context_current_job_mismatch")
        selected_profile_binding = ControlledAcquisitionSlotBinding(
            profile_selection_ref=refresh.profile_selection_ref,
            canonical_variable_id=refresh.canonical_variable_id,
            target_slot_id=refresh.target_slot_id,
        )
        workspace_dir = (
            self.runtime_root
            / "runtime/acquisition/world-growth/candidate-snapshots"
            / hashlib.sha256(
                canon.to_canonical_bytes(
                    [
                        closure.tenant_id,
                        closure.cell_id,
                        closure.run_id,
                        closure.route_id,
                        current_job.job_id,
                        str(growth.activation.overlay_admission_receipt_ref.artifact_id),
                    ]
                )
            ).hexdigest()
        )
        transaction_time = datetime.now(UTC)
        preparation = prepare_acquired_observation_snapshot(
            self.artifact_store,
            base_data_snapshot_ref=base_data_snapshot_ref,
            overlay=overlay,
            receipt_ref=growth.activation.overlay_admission_receipt_ref,
            passport=passport,
            authority=self.authority,
            observation_id=selected_row.observation.observation_id,
            slot_binding=selected_profile_binding,
            transaction_time=transaction_time,
        )
        from polisyos.foundry.data_plane import (
            load_input_bindings,
            prepare_json_input_binding_values,
        )

        prior_bindings = load_input_bindings(
            self.artifact_store, base_world_views.input_bindings_ref
        )
        prospective_rules = [
            rule
            for rule in prior_bindings.rules
            if rule.target_slot_id != preparation.foundry_binding_rule.target_slot_id
        ]
        prospective_rules.append(preparation.foundry_binding_rule)
        prospective_values = prepare_json_input_binding_values(
            self.artifact_store,
            payload_json=preparation.payload_json,
            registry_bundle_ref=base_world_views.registry_bundle_ref,
            rules=prospective_rules,
        )
        prospective_model = admission_owner.prepare_model_values_for_acquired_state(
            problem=closure.design_problem_basis,
            profile_selection_ref=refresh.profile_selection_ref,
            source_world_model=base_world,
            state=prospective_values.materialized_state,
        )
        materialization = materialize_acquired_observation_snapshot(
            self.artifact_store,
            base_data_snapshot_ref=base_data_snapshot_ref,
            overlay=overlay,
            receipt_ref=growth.activation.overlay_admission_receipt_ref,
            passport=passport,
            authority=self.authority,
            observation_id=selected_row.observation.observation_id,
            slot_binding=selected_profile_binding,
            workspace_dir=workspace_dir / "data-forge",
            transaction_time=transaction_time,
            prepared=preparation,
        )
        candidate_world = build_acquired_observation_candidate_world(
            self.artifact_store,
            base_world_model=base_world,
            substrate_registry=configured_profile.context_inputs.substrate_registry,
            substrate_registry_artifact_ref=substrate_registry_ref,
            materialization=materialization,
            workspace_dir=workspace_dir / "fabric-world",
            transaction_time=transaction_time,
        )
        self._reconcile_acquired_candidate_values(
            prospective_values=prospective_values,
            world_model_record=candidate_world.world_model.record,
        )
        offer = admission_owner.admit_context_for_acquired_world(
            problem=closure.design_problem_basis,
            profile_selection_ref=refresh.profile_selection_ref,
            world_model_record=candidate_world.world_model.record,
            job_id=current_job.job_id,
            run_id=current_job.run_id,
            tenant_id=closure.tenant_id,
            cell_id=closure.cell_id,
        )
        self._reconcile_acquired_candidate_model_values(
            prospective_model=prospective_model, offer=offer
        )
        context_owner = CycleSubstrateContextArtifactOwner(
            store=self.artifact_store,
            control_store=control_store,
        )
        context_ref = context_owner.persist_for_current_job(
            offer.context,
            problem=closure.design_problem_basis,
        )
        resolved = context_owner.resolve_for_current_job(
            context_ref,
            problem=closure.design_problem_basis,
        )
        if (
            resolved.context.content_hash != offer.context.content_hash
            or resolved.tenant_id != closure.tenant_id
            or resolved.cell_id != closure.cell_id
            or resolved.job_id != current_job.job_id
            or resolved.run_id != current_job.run_id
        ):
            raise ValueError("acquisition_candidate_context_replay_changed_content")
        handoff = CandidateSimulationContextHandoff(
            context=resolved.context,
            context_job_ref=context_ref,
            profile=offer.profile,
            profile_config_ref=offer.profile_config_ref,
            job_id=current_job.job_id,
            run_id=current_job.run_id,
            tenant_id=closure.tenant_id,
            cell_id=closure.cell_id,
            model_declaration=offer.model_declaration,
            model_declaration_ref=offer.model_declaration_ref,
            ncm_ref=offer.ncm_ref,
        )

        def currentness_resolver() -> bool:
            """Recheck Data Forge readback and the context under the live job lease."""

            try:
                current_job_record = control_store.current_execution_job_record()
                if (
                    current_job_record.job_id != handoff.job_id
                    or current_job_record.run_id != handoff.run_id
                    or current_job_record.run_id != closure.run_id
                ):
                    return False
                replayed_job = context_owner.resolve_for_current_job(
                    context_ref,
                    problem=closure.design_problem_basis,
                )
                latest_projection = overlay.read_activated_semantic_epoch_observations(
                    receipt_ref=growth.activation.overlay_admission_receipt_ref,
                    artifact_store=self.artifact_store,
                    passport=passport,
                    authority=self.authority,
                )
                current_offer = admission_owner.admit_context_for_acquired_world(
                    problem=closure.design_problem_basis,
                    profile_selection_ref=refresh.profile_selection_ref,
                    world_model_record=candidate_world.world_model.record,
                    job_id=current_job_record.job_id,
                    run_id=current_job_record.run_id,
                    tenant_id=closure.tenant_id,
                    cell_id=closure.cell_id,
                )
                return (
                    latest_projection.projection_content_sha256
                    == materialization.observation_projection.projection_content_sha256
                    and replayed_job.context.content_hash == handoff.context.content_hash
                    and current_offer == offer
                    and current_offer.context == handoff.context
                    and current_offer.profile == handoff.profile
                    and current_offer.model_declaration == handoff.model_declaration
                    and current_offer.model_declaration_ref == handoff.model_declaration_ref
                    and current_offer.ncm_ref == handoff.ncm_ref
                )
            except Exception:
                return False

        return offer.context, handoff, currentness_resolver

    def _reconcile_acquired_candidate_model_values(
        self, *, prospective_model: object, offer: object
    ) -> None:
        """Consume actual selected context model bytes and exact native N5 values."""

        from polisyos.ir import prepare_ncm_spec_selected_values
        from polisyos.runtime.quality.candidate_simulation import (
            CandidateSimulationContextOffer,
            prepare_candidate_n5_request_values,
        )
        from polisyos.runtime.quality.cycle_substrate import AcquiredCandidateModelValues
        from polisyos.runtime.quality.generation_source import GenerationSourceRepository

        if (
            type(prospective_model) is not AcquiredCandidateModelValues
            or type(offer) is not CandidateSimulationContextOffer
        ):
            raise TypeError("acquisition_prospective_model_values_untyped")
        if prepare_candidate_n5_request_values(
            offer.profile.n5
        ) != prepare_candidate_n5_request_values(prospective_model.n5_config):
            raise ValueError("acquisition_prospective_n5_configuration_mismatch")
        if offer.model_declaration_ref is None or offer.ncm_ref is None:
            raise ValueError("acquisition_prospective_selected_model_not_established")
        admission = self.control_store.current_execution_job_admission()
        if (
            admission.job.kind != "acquisition"
            or not admission.job.run_id
            or admission.scope.status != "established"
            or not admission.scope.tenant_id
            or not admission.scope.cell_id
        ):
            raise ValueError("acquisition_prospective_selected_model_scope_not_established")
        repository = GenerationSourceRepository(self.artifact_store)
        try:
            actual_declaration, actual_ncm = repository.load_candidate_declared_ncm(
                declaration_ref=offer.model_declaration_ref,
                ncm_ref=offer.ncm_ref,
                expected_profile=offer.profile,
                expected_run_id=admission.job.run_id,
                expected_job_id=admission.job.job_id,
                expected_tenant_id=admission.scope.tenant_id,
                expected_cell_id=admission.scope.cell_id,
            )
        except (OSError, RuntimeError, TypeError, ValueError) as exc:
            raise ValueError("acquisition_prospective_selected_model_not_established") from exc
        if (
            actual_declaration != offer.model_declaration
            or prepare_ncm_spec_selected_values(actual_ncm).value_bytes
            != prepare_ncm_spec_selected_values(prospective_model.ncm_spec).value_bytes
        ):
            raise ValueError("acquisition_prospective_declared_model_mismatch")

    def _reconcile_acquired_candidate_values(
        self, *, prospective_values: object, world_model_record: object
    ) -> None:
        """Consume prepared values only after fresh complete state/rule replay."""

        from polisyos.foundry.data_plane import InputBindingValuesPreparation, load_input_bindings
        from polisyos.foundry.execute import load_state_snapshot, state_snapshot_value_projection
        from polisyos.runtime.quality.world_model_record import (
            WorldModelRecord,
            world_model_artifact_views,
        )

        if (
            type(prospective_values) is not InputBindingValuesPreparation
            or type(world_model_record) is not WorldModelRecord
        ):
            raise TypeError("acquisition_prospective_values_untyped")
        actual_world_views = world_model_artifact_views(world_model_record)
        actual_state = load_state_snapshot(
            self.artifact_store, snapshot_ref=actual_world_views.bound_state_snapshot_ref
        )
        if state_snapshot_value_projection(actual_state) != state_snapshot_value_projection(
            prospective_values.materialized_state
        ):
            raise ValueError("acquisition_prospective_state_owner_reconciliation_failed")
        actual_bindings = load_input_bindings(
            self.artifact_store, actual_world_views.input_bindings_ref
        )
        if actual_bindings.rules != list(prospective_values.effective_rules):
            raise ValueError("acquisition_prospective_rule_owner_reconciliation_failed")

    @staticmethod
    def _validate_reentry(
        closure: VerifiedAcquisitionRouteClosure,
        growth: AcquisitionWorldGrowthReceipt,
        receipt: AcquisitionOverlayReentryReceipt,
    ) -> None:
        if (
            receipt.source_run_id != closure.generation_run.run_id
            or receipt.design_problem_ref != closure.design_problem_ref
            or receipt.source_cycle_index != closure.source_cycle.cycle_index
            or receipt.new_cycle.cycle_index != closure.source_cycle.cycle_index + 1
            or receipt.new_cycle.design_problem_ref != closure.design_problem_ref
            or receipt.new_cycle.design_problem_basis_ref != closure.design_problem_basis_ref
            or receipt.overlay_receipt_ref
            != str(growth.activation.overlay_admission_receipt_ref.artifact_id)
            or receipt.admitted_observation_count
            != growth.previously_active_observations + growth.admitted_observation_delta
        ):
            raise ValueError("acquisition_reentry_result_binding_mismatch")
        if receipt.schema_version.endswith(".v3"):
            from polisyos.runtime.quality.generation_cycle import (
                validate_acquisition_overlay_continuation,
            )

            validate_acquisition_overlay_continuation(closure.generation_run, receipt)

    def _persist(
        self,
        closure: VerifiedAcquisitionRouteClosure,
        payload: dict[str, Any],
        kind: str,
        schema: str,
        phase: str,
        *,
        event_id: str | None = None,
    ) -> str:
        encoded = canon.to_canonical_bytes(payload, canon.CanonSpec(forbid_floats=False))
        identity = hashlib.sha256(encoded).hexdigest()
        expected_ref = "sha256:" + identity
        if self.artifact_store.has(expected_ref):
            if self._read(expected_ref, kind) != payload:
                raise ValueError("acquisition_world_growth_readback_mismatch")
            reconcile_authority_ref(
                artifact_store=self.artifact_store,
                event_log=self.event_log,
                cas_ref=expected_ref,
                expected_tenant_id=closure.tenant_id,
                expected_cell_id=closure.cell_id,
                expected_run_id=closure.run_id,
                expected_job_id=closure.source_job_id,
            )
            return expected_ref
        now = datetime.now(UTC).isoformat()
        result = write_runtime_authority_artifact(
            self.artifact_store,
            self.event_log,
            payload,
            artifacts.ArtifactWriteOptions(
                kind=kind,
                media_type="application/json",
                schema=artifacts.SchemaInfo(
                    name=schema,
                    version=(
                        "2.0"
                        if kind == _REENTRY_KIND
                        else ("1.1" if "action_phase_ref" in payload else "1.0")
                    ),
                ),
                producer=artifacts.ProducerInfo(
                    component="polisyos.runtime.acquisition_world_growth", version="1.0"
                ),
                governance=artifacts.ArtifactGovernanceInfo(classification="internal"),
            ),
            evidence_id=identity,
            evidence_class="authority_bearing",
            authority_role="producer_authority",
            provenance_kind="runtime_emitted",
            owner="team-runtime-quality",
            reader_contract=kind + ".reader",
            reader_contract_version="1.0",
            tenant_id=closure.tenant_id,
            cell_id=closure.cell_id,
            run_id=closure.run_id,
            job_id=closure.source_job_id,
            trace_id="trace-" + closure.source_job_id,
            span_id="span-" + phase,
            parent_span_id=None,
            requested_execution_profile="production",
            effective_execution_profile="production",
            phase=phase,
            generated_at=now,
            as_of_time=now,
            same_input_closure={
                "closure_id": identity,
                "status": "closed",
                "run_id": closure.run_id,
                "job_id": closure.source_job_id,
                "tenant_id": closure.tenant_id,
                "cell_id": closure.cell_id,
                "evidence_input_refs": (closure.compiled_ref,),
                "closure_sha256": closure.route_id,
            },
            input_refs=(closure.compiled_ref,),
            effective_mode_ref=closure.route_id,
            degradation_ledger_ref=None,
            semantic_binding_ref=closure.cost_basis_hash,
            validation_status="pass",
            blocking_status="non_blocking",
            governance=GovernanceMetadata(
                classification="internal",
                authority_boundary=kind,
                pii="none",
                retention_policy="runtime-quality-90d",
                review_status="runtime_verified",
                override_policy="no_override",
                approval_policy="pa2_ds9_decision_required",
            ),
            event_id=event_id or "evt_acquisition_growth_" + identity,
            event_source="polisyos.runtime.acquisition_world_growth",
            event_type="polisyos.runtime.diagnostic.producer_execution.v1",
            event_subject="run/" + closure.run_id + "/acquisition/" + phase,
            state_before=None,
            state_after=phase,
            canon_spec=canon.CanonSpec(forbid_floats=False),
        )
        ref = str(result.cas_ref.artifact_id)
        if self._read(ref, kind) != payload:
            raise ValueError("acquisition_world_growth_readback_mismatch")
        return ref
