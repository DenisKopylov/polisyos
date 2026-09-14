"""Bind native acquisition activation to durable, same-case generation re-entry.

Deployment selects evidence and a finite re-entry budget. Native catalog and epoch
owners decide admission; neither a successful fetch nor deployment configuration
can decide it. An empty selection remains a usable quarantine-only deployment.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
from collections.abc import Iterator, Sequence  # noqa: TC003
from contextlib import contextmanager
from datetime import UTC, datetime
from decimal import Decimal  # noqa: TC003 - Pydantic resolves this annotation
from pathlib import Path  # noqa: TC003
from typing import TYPE_CHECKING, Any, Literal, Protocol, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.common import async_tools
from polisyos.core import artifacts, canon, contracts
from polisyos.data_forge import read_api as data_forge_read_api
from polisyos.runtime.quality import acquisition_executor
from polisyos.runtime.quality.agent_action_authority import write_runtime_authority_artifact
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
    from polisyos.runtime.quality.acquisition_route_loop import VerifiedAcquisitionRouteClosure
    from polisyos.runtime.quality.epoch_deployment import EpochDeployment
    from polisyos.runtime.quality.event_log import RuntimeDiagnosticEventLog
    from polisyos.runtime.quality.open_world_risk import PromotionRuntime

_SHA = r"^sha256:[0-9a-f]{64}$"
_GROWTH_KIND = "runtime_quality.acquisition_world_growth_receipt"
_ATTEMPT_KIND = "runtime_quality.acquisition_world_growth_attempt"
_DEFERRAL_KIND = "runtime_quality.acquisition_world_growth_deferral"
_REENTRY_KIND = "runtime_quality.acquisition_overlay_reentry_receipt"


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


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
    """Typed empty-by-default evidence-selection slots."""

    routes: tuple[AcquisitionWorldGrowthRoute, ...] = ()

    @model_validator(mode="after")
    def _unique_routes(self) -> Self:
        if len({route.key for route in self.routes}) != len(self.routes):
            raise ValueError("acquisition_world_growth_route_ambiguous")
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


class AcquisitionWorldGrowthReceipt(_Strict):
    """Native activation plus the measured change in active membership."""

    schema_version: Literal["AcquisitionWorldGrowthReceipt@1.0"] = (
        "AcquisitionWorldGrowthReceipt@1.0"
    )
    selection: AcquisitionWorldGrowthRoute
    binding_id: str = Field(min_length=1)
    activation: acquisition_executor.ActivatedSemanticEpochAdmissionReceipt
    passport_id: str = Field(min_length=1)
    admitted_observation_delta: int = Field(gt=0)
    previously_active_observations: int = Field(ge=0)
    live_evidence_refs: tuple[str, ...] = Field(min_length=1)


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


@contextmanager
def _owner_lock(path: Path) -> Iterator[None]:
    with path.open("a+b") as stream:
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


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
    ) -> None:
        if type(config) is not AcquisitionWorldGrowthConfig:
            raise TypeError("acquisition world growth selection must be typed")
        self.config = config
        self.repo_root = repo_root
        self.runtime_root = runtime_root
        self.authority = authority
        self.artifact_store = artifact_store
        self.event_log = event_log
        self.epoch_deployment = epoch_deployment
        self.promotion_runtime = promotion_runtime

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

    def admit(
        self,
        *,
        closure: VerifiedAcquisitionRouteClosure,
        binding_id: str,
        target_variable: str,
        evidence: acquisition_executor.LiveSourceExecutionEvidence,
        owner_receipt_refs: tuple[str, ...],
    ) -> AcquisitionWorldGrowthReceipt | PersistedSemanticEpochProductionReceipt | None:
        """Attempt native admission, measuring fresh membership under the owner lock."""
        selected = self.selection(closure)
        if selected is None:
            return None
        overlay_path, _ = self._paths(selected)

        # The shared native owner is the contended resource, across routes/processes.
        with _owner_lock(overlay_path.with_suffix(".admission.lock")):
            before = data_forge_read_api.catalog.project_catalog_acquisition_state(
                self.authority.baseline_path, overlay_path=overlay_path
            )
            attempt = AcquisitionWorldGrowthAttempt(
                selection=selected,
                binding_id=binding_id,
                target_variable=target_variable,
                evidence=evidence,
                owner_receipt_refs=owner_receipt_refs,
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
            return self._admit_stored_attempt(closure, attempt_ref, attempt)

    def _admit_stored_attempt(
        self,
        closure: VerifiedAcquisitionRouteClosure,
        attempt_ref: str,
        attempt: AcquisitionWorldGrowthAttempt,
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
        growth = self._finish_admission(closure, attempt, activation)
        if growth is not None:
            self.persist_growth(closure, growth)
        return growth

    def has_deferred_admission(self, closure: VerifiedAcquisitionRouteClosure) -> bool:
        """Read eligibility from a known negative; never create files or predict admission."""
        try:
            self._load_deferral(closure)
        except (KeyError, OSError, RuntimeError, TypeError, ValueError):
            return False
        return True

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
        self, closure: VerifiedAcquisitionRouteClosure
    ) -> tuple[
        tuple[str, ...], AcquisitionWorldGrowthReceipt | PersistedSemanticEpochProductionReceipt
    ]:
        """Admit original durable evidence under new authority, without another live fetch."""
        selected = self.selection(closure)
        if selected is None:
            raise ValueError("acquisition_deferred_admission_missing")
        overlay_path, _ = self._paths(selected)
        with _owner_lock(overlay_path.with_suffix(".admission.lock")):
            deferral_ref, deferral, attempt = self._load_deferral(closure)
            fence = self._growth_pointer(selected).with_suffix(".admission.started")
            with fence.open("x") as stream:
                stream.write(deferral_ref)
                stream.flush()
                os.fsync(stream.fileno())
            self._sync_directory(fence.parent)
            result = self._admit_stored_attempt(closure, deferral.attempt_ref, attempt)
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
        )

    def recover_admission(
        self, closure: VerifiedAcquisitionRouteClosure
    ) -> AcquisitionWorldGrowthReceipt:
        """Recover an already-active owner outcome without fetching or activating again."""
        selected = self.selection(closure)
        if selected is None:
            raise ValueError("acquisition_live_evidence_not_admitted")
        overlay_path, _ = self._paths(selected)
        with _owner_lock(overlay_path.with_suffix(".admission.lock")):
            pointer = self._growth_pointer(selected)
            if pointer.exists():
                growth, _ = self._verified_growth(
                    closure, json.loads(pointer.read_text())["receipt_ref"]
                )
                return growth
            attempt_pointer = pointer.with_suffix(".attempt.json")
            attempt = AcquisitionWorldGrowthAttempt.model_validate(
                self._read(json.loads(attempt_pointer.read_text())["receipt_ref"], _ATTEMPT_KIND)
            )
            if attempt.selection != selected:
                raise ValueError("acquisition_world_growth_case_mismatch")
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
            growth = self._finish_admission(closure, attempt, activation)
            if growth is None:
                raise ValueError("acquisition_owner_outcome_not_established")
            self.persist_growth(closure, growth)
            return growth

    def _native_ref(self, ref: str) -> artifacts.ArtifactRef:
        manifest = self.artifact_store.get_manifest(ref)
        return artifacts.ArtifactRef(
            artifact_id=artifacts.ArtifactID.model_validate(ref),
            kind=manifest.kind,
            media_type=manifest.media_type,
        )

    def persist_growth(
        self, closure: VerifiedAcquisitionRouteClosure, growth: AcquisitionWorldGrowthReceipt
    ) -> str:
        """Persist the supplier's measured activation before phase advancement."""
        ref = self._persist(
            closure,
            growth.model_dump(mode="json"),
            _GROWTH_KIND,
            "AcquisitionWorldGrowthReceipt",
            "world_committed",
        )
        pointer = self._growth_pointer(growth.selection)
        self._write_pointer(pointer, ref)
        return ref

    def _growth_pointer(
        self, selected: AcquisitionWorldGrowthRoute, *, create: bool = True
    ) -> Path:
        overlay_path, _ = self._paths(selected, create=create)
        identity = hashlib.sha256(canon.to_canonical_bytes(list(selected.key))).hexdigest()
        return overlay_path.parent / (identity + ".growth.json")

    @staticmethod
    def _write_pointer(pointer: Path, ref: str) -> None:
        temporary = pointer.with_suffix(".tmp")
        with temporary.open("w") as stream:
            stream.write(json.dumps({"receipt_ref": ref}) + "\n")
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

    def project_growth(
        self, closure: VerifiedAcquisitionRouteClosure
    ) -> AcquisitionWorldGrowthReceipt | None:
        """Read and reverify the native admission selected by this route's receipt."""
        selected = self.selection(closure)
        if selected is None:
            return None
        pointer = self._growth_pointer(selected)
        if not pointer.exists():
            return None
        ref = json.loads(pointer.read_text())["receipt_ref"]
        growth, _ = self._verified_growth(closure, ref)
        return growth

    def _verified_growth(
        self, closure: VerifiedAcquisitionRouteClosure, ref: str
    ) -> tuple[AcquisitionWorldGrowthReceipt, data_forge_read_api.catalog.OverlayAdmissionReceipt]:
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

    def _read(self, ref: str, kind: str) -> dict[str, Any]:
        payload = self.artifact_store.get_bytes(ref)
        manifest = self.artifact_store.get_manifest(ref)
        if (
            "sha256:" + hashlib.sha256(payload).hexdigest() != ref
            or manifest.kind != kind
            or manifest.authority is None
            or manifest.producer is None
            or manifest.producer.component != "polisyos.runtime.acquisition_world_growth"
        ):
            raise ValueError("acquisition_world_growth_receipt_unverified")
        report = reconcile_authority_ref(
            artifact_store=self.artifact_store, event_log=self.event_log, cas_ref=ref
        )
        if report.durable_event_id is None:
            raise ValueError("acquisition_world_growth_receipt_unverified")
        return canon.from_canonical_bytes(payload)

    def resume(self, closure: VerifiedAcquisitionRouteClosure, refs: tuple[str, ...]) -> str:
        """Read verified native activation and enter the original case at the next cycle."""
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
        with _owner_lock(overlay_path.with_suffix(".admission.lock")):
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
            payload = json.loads(self.artifact_store.get_bytes(closure.source_payload_ref))
            models = payload.get("llm_models")
            model = str(models[0]) if isinstance(models, list) and models else None
            controller = GenerationCycleController(
                repo_root=self.repo_root, model_id=model, promotion_runtime=self.promotion_runtime
            )
            if model is None:
                raise ValueError("acquisition_reentry_model_unconfigured")
            with fence.open("x") as stream:
                stream.write(growth_refs[0])
                stream.flush()
                os.fsync(stream.fileno())
            receipt = async_tools.run_coro_sync(
                controller.reenter_after_active_acquisition_overlay(
                    original_run=closure.generation_run,
                    source_cycle=closure.source_cycle,
                    problem=closure.design_problem,
                    overlay_receipt=admitted,
                    baseline_path=self.authority.baseline_path,
                    overlay_path=overlay_path,
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
            self._validate_reentry(closure, growth, receipt)
            ref = self._persist(
                closure,
                receipt.model_dump(mode="json"),
                _REENTRY_KIND,
                "AcquisitionOverlayReentryReceipt",
                "reentry_terminal",
                event_id=event_id,
            )
            self._write_pointer(pointer, ref)
            return ref

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
            or receipt.overlay_receipt_ref
            != str(growth.activation.overlay_admission_receipt_ref.artifact_id)
            or receipt.admitted_observation_count
            != growth.previously_active_observations + growth.admitted_observation_delta
        ):
            raise ValueError("acquisition_reentry_result_binding_mismatch")

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
                schema=artifacts.SchemaInfo(name=schema, version="1.0"),
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
