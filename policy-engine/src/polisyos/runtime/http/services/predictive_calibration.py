"""Run-bound candidate predictive-calibration production and readback."""

from __future__ import annotations

import hashlib
import json
import logging
import uuid
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Literal, Protocol, cast

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from polisyos.calibration import (
    REFERENCE_PROFILES,
    EmpiricalCalibrationContext,
    EmpiricalCalibrationEvidenceRef,
    EvidenceArtifactRef,
    load_empirical_calibration_evidence,
    persist_empirical_calibration_evidence,
    produce_empirical_calibration_evidence,
)
from polisyos.core.artifacts import (
    ArtifactID,
    ArtifactRef,
    artifact_manifest_profile_sha256,
    artifact_ref_identity_key,
    ensure_ir_artifact_store,
)
from polisyos.core.canon import CanonSpec as CoreCanonSpec
from polisyos.core.canon import to_canonical_bytes
from polisyos.core.contracts import (
    ApiMeta,
    DataSnapshot,
    DataSnapshotRef,
    ForecastProfileMemberV1,
    RunDetails,
)
from polisyos.ir import (
    ArtifactRefModel,
    BacktestReport,
    InputRef,
    get_json_artifact,
    load_backtest_report,
    normalize_artifact_ref,
    persist_backtest_report,
    put_json_artifact,
)
from polisyos.ir import (
    CanonSpec as IRCanonSpec,
)
from polisyos.pdc import AuthorityBoundary
from polisyos.runtime.http.services.run_operation_idempotency import (
    RuntimeOperationIntentClaim,
    RuntimeOperationIntentKey,
    RuntimeOperationIntentStore,
)
from polisyos.runtime.quality.diagnostic_events import DiagnosticEvent
from polisyos.runtime.quality.event_log import DiagnosticEventPayloadPolicy
from polisyos.runtime.quality.forecast_profile_binding import (
    FORECAST_PROFILE_MEMBER_KIND,
    FORECAST_PROFILE_MEMBER_SCHEMA,
    FORECAST_PROFILE_MEMBER_SCHEMA_VERSION,
    VALUE_DATA_PROFILE_KIND,
    VALUE_DATA_PROFILE_SCHEMA,
    VALUE_DATA_PROFILE_SCHEMA_VERSION,
    VALUE_OWNER_PROJECTION_KIND,
    VALUE_OWNER_PROJECTION_SCHEMA,
    VALUE_OWNER_PROJECTION_SCHEMA_VERSION,
    ResolvedValueProfileProjection,
    join_profile_member_to_observed_series,
    validate_profile_projection_binding,
)
from polisyos.scientist.methods.backtesting import (
    CALIBRATION_RULE_ID,
    CalibrationRuleBinding,
    ForecastMethodParams,
    ForecastOwner,
    ForecastOwnerRequest,
    ForecastTemporalRoles,
    TrainHoldoutSplit,
)

if TYPE_CHECKING:
    from polisyos.core.artifacts import ArtifactManifest, ArtifactStore
    from polisyos.runtime.http.services.control_plane_store import (
        ControlDiagnosticEventRecord,
    )
    from polisyos.runtime.http.services.run_index import IndexedRunRecord

_ASSOCIATION_KIND = "runtime.predictive_calibration_association"
_LEGACY_ASSOCIATION_SCHEMA = "polisyos.runtime.predictive_calibration_association.v2"
_LEGACY_ASSOCIATION_VERSION = "2.0"
_PRIOR_ASSOCIATION_SCHEMA = "polisyos.runtime.predictive_calibration_association.v3"
_PRIOR_ASSOCIATION_VERSION = "3.0"
_ASSOCIATION_SCHEMA = "polisyos.runtime.predictive_calibration_association.v4"
_ASSOCIATION_VERSION = "4.0"
_N4_OUTCOME_BINDING_LIMITATION_CODE = "n4_outcome_target_binding_not_established"
_N4_OUTCOME_BINDING_LIMITATION_REF = (
    f"s10://calibration/fail-closed/{_N4_OUTCOME_BINDING_LIMITATION_CODE}"
)
_ASSOCIATION_EVENT = "polisyos.runtime.diagnostic.ref_publication.v1"
_ASSOCIATION_EVENT_SCHEMA = "polisyos.runtime.quality.diagnostic_event"
_ASSOCIATION_EVENT_SCHEMA_VERSION = "1.0"
_METHOD_FQN = "forecasting.univariate.exponential_smoothing@1.0.0"
_METHOD_REF, _METHOD_VERSION = _METHOD_FQN.rsplit("@", maxsplit=1)
_logger = logging.getLogger(__name__)


def _as_ir_artifact_ref(ref: ArtifactRef) -> ArtifactRefModel:
    """Adapt a selected Core reference without dropping its manifest profile."""
    return ArtifactRefModel.model_validate(normalize_artifact_ref(ref))


def _as_ir_empirical_calibration_evidence_ref(
    ref: object,
) -> EmpiricalCalibrationEvidenceRef:
    """Adapt the complete selected view into the evidence reader's typed role."""
    return EmpiricalCalibrationEvidenceRef.model_validate(normalize_artifact_ref(ref))


class _ControlJob(Protocol):
    """Control-job identity used to bind diagnostic writes to a completed run."""

    job_id: str
    run_id: str | None
    state: str
    kind: str
    progress: Mapping[str, Any]


class _ControlStore(Protocol):
    """Control-store read seam used to bind an event to the selected Core run."""

    def get_job(self, job_id: str) -> _ControlJob | None:
        """Return the current control job row, if present."""


class _DiagnosticEventLog(Protocol):
    """Append-only diagnostic event log consumed by the service."""

    artifact_store: ArtifactStore
    _store: _ControlStore

    def append(
        self,
        event: DiagnosticEvent,
        *,
        payload: Mapping[str, Any] | None = None,
        payload_policy: DiagnosticEventPayloadPolicy | None = None,
    ) -> object:
        """Append one validated diagnostic event."""

    def list_events(
        self,
        *,
        run_id: str | None = None,
        job_id: str | None = None,
        limit: int = 500,
    ) -> list[ControlDiagnosticEventRecord]:
        """Read the durable event stream for one run/job pair."""


class PredictiveCalibrationError(ValueError):
    """A candidate predictive-calibration operation could not bind its inputs."""

    def __init__(self, code: str, message: str | None = None) -> None:
        super().__init__(message or code)
        self.code = code


class _AcquiredObservedSourceNotEstablishedError(PredictiveCalibrationError):
    """Keep the source-row limitation distinct at both predictive intakes."""

    def __init__(self) -> None:
        super().__init__("predictive_calibration_acquired_source_row_not_established")


class PredictiveCalibrationRequest(BaseModel):
    """Explicit, profile-selected inputs for one run-bound predictive diagnostic."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    intent_id: str = Field(min_length=1, max_length=120, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")
    candidate_source_ref: ArtifactRef
    observed_source_ref: DataSnapshotRef
    value_data_profile_ref: ArtifactRef | None = None
    value_data_unit_id: str | None = None
    model_spec_ref: ArtifactRef
    policy_spec_ref: ArtifactRef
    calibration_rule_ref: ArtifactRef
    calibration_threshold: float = Field(gt=0.0, le=1.0)
    split: TrainHoldoutSplit
    target_metric: str = Field(min_length=1, max_length=200)
    method_params: ForecastMethodParams
    temporal_roles: ForecastTemporalRoles
    seed: int = Field(ge=0)

    @model_validator(mode="after")
    def _validate_value_profile_selection(self) -> PredictiveCalibrationRequest:
        if (self.value_data_profile_ref is None) != (self.value_data_unit_id is None):
            raise ValueError("value profile ref and selected unit must be supplied as a pair")
        if self.value_data_profile_ref is not None:
            if (
                self.value_data_profile_ref.kind != VALUE_DATA_PROFILE_KIND
                or self.value_data_profile_ref.media_type != "application/json"
                or self.value_data_profile_ref.manifest_profile_sha256 is None
            ):
                raise ValueError("value profile ref must select an exact JSON manifest view")
            if (
                not self.value_data_unit_id
                or self.value_data_unit_id != self.value_data_unit_id.strip()
            ):
                raise ValueError("selected value profile unit must be a clean identifier")
        return self


class PredictiveCalibrationS10Summary(BaseModel):
    """Typed persisted projection of the recomputed S10 candidate support."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    calibration_status: Literal[
        "pass",
        "limit",
        "blocked",
        "not_applicable_non_observable",
        "insufficient_history",
    ]
    forecast_tier: str = Field(min_length=1, max_length=120)
    counterfactual_credibility: Literal["not_established"]
    numerator: int = Field(ge=0)
    denominator: int = Field(ge=0)
    observed_pass_rate: float = Field(ge=0.0, le=1.0)
    calibration_record_ref: str | None = None
    outcome_binding_status: Literal["not_established"] | None = None
    limitation_refs: tuple[str, ...] = ()
    authority_boundary: AuthorityBoundary | None = None
    may_not_use_for: tuple[str, ...] | None = Field(default=None, min_length=1, max_length=20)


class PredictiveCalibrationAssociation(BaseModel):
    """Versioned, append-only run attachment for a limited predictive result."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[
        "polisyos.runtime.predictive_calibration_association.v2",
        "polisyos.runtime.predictive_calibration_association.v3",
        "polisyos.runtime.predictive_calibration_association.v4",
    ] = _ASSOCIATION_SCHEMA
    event_id: str = Field(min_length=1)
    intent_id: str = Field(min_length=1, max_length=120)
    request_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    run_id: str = Field(min_length=1)
    control_run_id: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    tenant_id: str = Field(min_length=1)
    cell_id: str = Field(min_length=1)
    run_manifest_ref: ArtifactRef
    candidate_source_ref: ArtifactRef
    observed_source_ref: ArtifactRef
    model_spec_ref: ArtifactRef
    policy_spec_ref: ArtifactRef
    calibration_rule_ref: ArtifactRef
    backtest_report_ref: ArtifactRef
    empirical_evidence_ref: ArtifactRef
    uncertainty_bundle_ref: ArtifactRef
    value_data_profile_ref: ArtifactRef | None = None
    forecast_profile_member_ref: ArtifactRef | None = None
    profile_join_status: Literal["joined_candidate", "profileless_legacy"] = "profileless_legacy"
    assessment: Literal["limited"] = "limited"
    authority_scope: Literal["predictive_only"] = "predictive_only"
    issuer_status: Literal["not_established"] = "not_established"
    source_time_status: Literal["not_established"] = "not_established"
    population_scope_status: Literal["not_established"] = "not_established"
    counterfactual_credibility_status: Literal["not_established"] = "not_established"
    observed_numerator: int = Field(ge=0)
    observed_denominator: int = Field(ge=1)
    observed_hit_rate: float = Field(ge=0.0, le=1.0)
    nominal_confidence_level: float | None = Field(default=None, gt=0.0, lt=1.0)
    owner_suitability: Literal["supported", "limited", "blocked"]
    s10: PredictiveCalibrationS10Summary
    evidence_reason_codes: tuple[str, ...] = ()
    may_not_use_for: tuple[str, ...] = Field(
        default=("promotion", "publication", "policy_selection", "causal_effect_claim"),
        min_length=1,
        max_length=40,
    )
    created_at: datetime

    @model_validator(mode="after")
    def _validate_n4_s10_scope(self) -> PredictiveCalibrationAssociation:
        if (self.value_data_profile_ref is None) != (self.forecast_profile_member_ref is None):
            raise ValueError("predictive_calibration_profile_member_refs_incomplete")
        if self.value_data_profile_ref is None:
            if self.profile_join_status != "profileless_legacy":
                raise ValueError("predictive_calibration_profileless_status_mismatch")
        elif (
            self.profile_join_status != "joined_candidate"
            or self.value_data_profile_ref.kind != VALUE_DATA_PROFILE_KIND
            or self.forecast_profile_member_ref.kind != FORECAST_PROFILE_MEMBER_KIND
            or self.value_data_profile_ref.media_type != "application/json"
            or self.forecast_profile_member_ref.media_type != "application/json"
            or self.value_data_profile_ref.manifest_profile_sha256 is None
            or self.forecast_profile_member_ref.manifest_profile_sha256 is None
        ):
            raise ValueError("predictive_calibration_profile_member_binding_invalid")
        if (
            self.schema_version in {_ASSOCIATION_SCHEMA, _PRIOR_ASSOCIATION_SCHEMA}
            or self.candidate_source_ref.kind == "runtime.quality.n4_candidate_scenario_source"
        ) and (
            self.s10.outcome_binding_status != "not_established"
            or _N4_OUTCOME_BINDING_LIMITATION_REF not in self.s10.limitation_refs
            or self.s10.forecast_tier != "blocked"
            or self.s10.authority_boundary is None
            or self.s10.may_not_use_for is None
            or tuple(self.s10.authority_boundary.may_not_use_for) != self.s10.may_not_use_for
            or self.may_not_use_for != self.s10.may_not_use_for
        ):
            raise ValueError("predictive_calibration_n4_outcome_binding_not_established")
        return self


class PredictiveCalibrationResponse(BaseModel):
    """API wrapper for a durable, freshly resolved predictive association."""

    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    association_ref: ArtifactRef
    association: PredictiveCalibrationAssociation


def _s10_summary_from_owner(record: object, support: object) -> PredictiveCalibrationS10Summary:
    """Copy the real S10 support boundary into the persisted API projection."""
    from polisyos.runtime.quality.design_axes.outcome_prediction import ForecastSupport

    if type(support) is not ForecastSupport:
        raise PredictiveCalibrationError("predictive_calibration_s10_support_untyped")
    authority_boundary = support.authority_boundary
    may_not_use_for = tuple(support.may_not_use_for)
    if tuple(authority_boundary.may_not_use_for) != may_not_use_for:
        raise PredictiveCalibrationError("predictive_calibration_s10_authority_projection_mismatch")
    return PredictiveCalibrationS10Summary(
        calibration_status=_calibration_status(getattr(record, "calibration_status", None)),
        forecast_tier=_required_text(getattr(support, "forecast_tier", None), "forecast_tier"),
        counterfactual_credibility="not_established",
        numerator=int(getattr(record, "numerator", 0)),
        denominator=int(getattr(record, "denominator", 0)),
        observed_pass_rate=float(getattr(record, "pass_rate", 0.0) or 0.0),
        calibration_record_ref=getattr(record, "calibration_ref", None),
        outcome_binding_status="not_established",
        limitation_refs=tuple(str(item) for item in support.limitation_refs),
        authority_boundary=authority_boundary.model_copy(deep=True),
        may_not_use_for=may_not_use_for,
    )


def produce_run_predictive_calibration(
    *,
    store: ArtifactStore,
    run: IndexedRunRecord,
    request: PredictiveCalibrationRequest,
    event_log: _DiagnosticEventLog,
    event_scope: Mapping[str, str],
    actor_subject: str,
) -> tuple[ArtifactRef, PredictiveCalibrationAssociation]:
    """Run the real owner, bridge, S10 consumer, and append-only association path."""

    run_details = getattr(run, "details", None)
    run_id = _required_text(getattr(run_details, "run_id", None), "run_id")
    job_id = _required_text(getattr(run_details, "control_job_id", None), "control_job_id")
    tenant_id = _required_text(getattr(run_details, "tenant_id", None), "tenant_id")
    cell_id = _required_text(getattr(run_details, "cell_id", None), "cell_id")
    run_manifest_ref = _selected_run_manifest(run_details)
    root_refs = _root_refs(run_details)
    root_input_refs = _root_input_refs(run_details)
    _require_candidate_source_ref(request.candidate_source_ref, run_details, root_refs)
    _require_run_root_ref(request.observed_source_ref, root_input_refs, "observed_source")
    run_bound_refs = (*root_refs, *root_input_refs)
    for role, reference in (
        ("model_spec", request.model_spec_ref),
        ("policy_spec", request.policy_spec_ref),
        ("calibration_rule", request.calibration_rule_ref),
    ):
        _require_run_root_ref(reference, run_bound_refs, role)
    _require_selected_ref(
        store,
        request.candidate_source_ref,
        expected_kind="runtime.quality.n4_candidate_scenario_source",
    )
    _require_selected_ref(store, request.observed_source_ref, expected_kind="fabric.data_snapshot")
    _require_selected_ref(store, request.model_spec_ref, expected_kind="ir.model_spec")
    _require_selected_ref(store, request.policy_spec_ref, expected_kind="ir.policy_spec")
    _require_selected_ref(
        store,
        request.calibration_rule_ref,
        expected_kind="ir.forecast_calibration_rule",
    )
    selected_profile_binding: ResolvedValueProfileProjection | None = None
    selected_profile_member: ForecastProfileMemberV1 | None = None
    if request.value_data_profile_ref is not None:
        _require_run_root_ref(request.value_data_profile_ref, run_bound_refs, "value_data_profile")
        selected_profile_binding = _validate_selected_value_data_profile(
            store, request.value_data_profile_ref
        )
        selected_profile_member = _build_selected_profile_member(
            store=store,
            request=request,
            binding=selected_profile_binding,
        )
    _require_event_scope(
        event_scope,
        run_id=run_id,
        job_id=job_id,
        tenant_id=tenant_id,
        cell_id=cell_id,
    )
    if (
        not isinstance(actor_subject, str)
        or not actor_subject
        or actor_subject != actor_subject.strip()
    ):
        raise PredictiveCalibrationError("predictive_calibration_actor_scope_missing")
    control_run_id = _require_event_log_owner(
        event_log,
        store=store,
        run_id=run_id,
        job_id=job_id,
        run_manifest_ref=run_manifest_ref,
    )
    request_sha256 = _request_sha256(request)
    body_sha256 = _operation_body_sha256(
        request=request,
        run_id=run_id,
        job_id=job_id,
        tenant_id=tenant_id,
        cell_id=cell_id,
        run_manifest_ref=run_manifest_ref,
    )
    key = RuntimeOperationIntentKey(
        purpose="run.predictive_calibration.v1",
        tenant_id=tenant_id,
        cell_id=cell_id,
        actor_subject_sha256=hashlib.sha256(actor_subject.encode("utf-8")).hexdigest(),
        run_id=run_id,
        intent_id=request.intent_id,
        body_sha256=body_sha256,
    )
    event_id = _intent_event_id(key)
    replay = _load_existing_intent(
        store=store,
        run=run,
        event_log=event_log,
        event_scope=event_scope,
        event_id=event_id,
        intent_id=request.intent_id,
        request_sha256=request_sha256,
        run_manifest_ref=run_manifest_ref,
    )
    if replay is not None:
        return replay

    operation_store = _operation_intent_store(event_log)
    claim = operation_store.begin_runtime_operation_intent(key)
    if claim.disposition == "body_conflict":
        raise PredictiveCalibrationError("predictive_calibration_intent_conflict")
    if claim.disposition == "completed":
        replay = _load_existing_intent(
            store=store,
            run=run,
            event_log=event_log,
            event_scope=event_scope,
            event_id=event_id,
            intent_id=request.intent_id,
            request_sha256=request_sha256,
            run_manifest_ref=run_manifest_ref,
        )
        if replay is None or not _claim_result_matches(claim, replay):
            raise PredictiveCalibrationError(
                "predictive_calibration_completed_intent_result_unresolved"
            )
        return replay
    if claim.disposition == "pending":
        raise PredictiveCalibrationError("predictive_calibration_intent_in_progress")
    if claim.disposition == "refused":
        raise PredictiveCalibrationError(
            claim.record.reason_code or "predictive_calibration_intent_refused"
        )
    if claim.disposition == "recovery_required":
        raise PredictiveCalibrationError("predictive_calibration_intent_recovery_required")
    if claim.disposition != "owner" or claim.owner_token is None:
        raise PredictiveCalibrationError("predictive_calibration_intent_owner_unavailable")
    owner_token = claim.owner_token
    owner_started = False
    try:
        from polisyos.runtime.quality.generation_source import (
            GenerationSourceRepository,
            N4CandidateScenarioSourceRecordV3,
        )

        try:
            candidate_source = GenerationSourceRepository(
                store
            ).load_candidate_scenario_source_for_n5(
                request.candidate_source_ref,
                expected_run_id=control_run_id,
                expected_job_id=job_id,
                expected_tenant_id=tenant_id,
                expected_cell_id=cell_id,
            )
        except (FileNotFoundError, OSError, TypeError, ValueError) as exc:
            raise PredictiveCalibrationError(
                "predictive_calibration_candidate_source_unresolved",
                "The selected candidate source could not be re-resolved for this run.",
            ) from exc
        if type(candidate_source) is not N4CandidateScenarioSourceRecordV3:
            raise PredictiveCalibrationError(
                "predictive_calibration_candidate_source_profile_mismatch"
            )
        candidate = candidate_source.candidate
        problem = candidate_source.problem
        context_inputs = getattr(candidate_source.profile, "context_inputs", None)
        world_record = getattr(context_inputs, "world_model_record", None)
        if candidate is None or world_record is None:
            raise PredictiveCalibrationError("predictive_calibration_candidate_context_incomplete")
        n4_outcome_binding = _n4_outcome_target_binding_record(
            candidate_source,
            request.target_metric.strip(),
        )

        report_id = (
            f"{run_id}:predictive-calibration:"
            f"{event_id.removeprefix('evt_predictive_calibration_')}"
        )
        run_inputs = [
            _core_input(run_manifest_ref, "run_manifest"),
            _core_input(request.candidate_source_ref, "candidate_source"),
            _core_input(request.observed_source_ref, "observed_source"),
        ]
        if request.value_data_profile_ref is not None:
            run_inputs.append(_core_input(request.value_data_profile_ref, "value_data_profile"))
        owner_request = ForecastOwnerRequest(
            observed_source_ref=DataSnapshotRef.model_validate(
                request.observed_source_ref.model_dump()
            ),
            value_data_profile_ref=(
                None
                if request.value_data_profile_ref is None
                else _as_ir_artifact_ref(request.value_data_profile_ref)
            ),
            value_data_unit_id=request.value_data_unit_id,
            forecast_profile_member=selected_profile_member,
            split=request.split,
            target_metric=request.target_metric.strip(),
            method_fqn=_METHOD_FQN,
            method_params=request.method_params,
            report_id=report_id,
            calibration_rule=CalibrationRuleBinding(
                rule_id=CALIBRATION_RULE_ID,
                artifact_ref=_as_ir_artifact_ref(request.calibration_rule_ref),
            ),
            temporal_roles=request.temporal_roles,
            model_spec_ref=_as_ir_artifact_ref(request.model_spec_ref),
            policy_spec_ref=_as_ir_artifact_ref(request.policy_spec_ref),
            manifest_inputs=run_inputs,
            seed=request.seed,
        )
        try:
            owner_started = True
            owner_result = ForecastOwner(store).run(owner_request)
        except (FileNotFoundError, OSError, TypeError, ValueError) as exc:
            raise PredictiveCalibrationError(
                "predictive_calibration_owner_rejected_inputs",
                "The predictive owner refused the selected source, split, or rule binding.",
            ) from exc

        ir_store = ensure_ir_artifact_store(store)
        preliminary_report = load_backtest_report(ir_store, owner_result.backtest_report_ref)
        reference_payloads = _persist_evidence_role_refs(
            store=store,
            report_id=report_id,
            threshold=request.calibration_threshold,
            model_spec_ref=request.model_spec_ref,
            policy_spec_ref=request.policy_spec_ref,
            candidate_source_ref=request.candidate_source_ref,
            observed_source_ref=owner_result.observed_source_ref,
            training_slice_ref=owner_result.training_slice_ref,
            uncertainty_bundle_ref=owner_result.uncertainty_bundle_ref,
            method_artifact_ref=owner_result.method_artifact_ref,
            calibration_rule_ref=owner_result.calibration_rule_ref,
        )
        context = _build_empirical_context(
            reference_payloads,
            model_spec_ref=owner_result.model_spec_ref,
            policy_spec_ref=owner_result.policy_spec_ref,
            threshold=request.calibration_threshold,
            temporal_roles=request.temporal_roles,
        )
        report_metadata = dict(preliminary_report.metadata)
        report_metadata["run_binding"] = {
            "run_id": run_id,
            "control_run_id": control_run_id,
            "job_id": job_id,
            "intent_id": request.intent_id,
            "request_sha256": request_sha256,
            "run_manifest_ref": run_manifest_ref.model_dump(mode="json"),
            "candidate_source_ref": request.candidate_source_ref.model_dump(mode="json"),
        }
        report_metadata["source_population_scope_status"] = "not_established"
        report_metadata["source_time_status"] = "not_established"
        report_metadata["issuer_status"] = "not_established"
        report_metadata["n4_outcome_target_binding"] = n4_outcome_binding
        report_metadata["profile_join_status"] = (
            "joined_candidate"
            if owner_result.value_data_profile_ref is not None
            else "profileless_legacy"
        )
        if owner_result.value_data_profile_ref is not None:
            report_metadata["value_data_profile_ref"] = (
                owner_result.value_data_profile_ref.model_dump(mode="json")
            )
            report_metadata["forecast_profile_member_ref"] = (
                owner_result.forecast_profile_member_ref.model_dump(mode="json")
            )
        report_with_run_binding = preliminary_report.model_copy(
            update={"metadata": report_metadata}
        )
        preliminary_manifest = store.get_manifest(owner_result.backtest_report_ref)
        report_inputs = [
            InputRef.model_validate(item.model_dump(mode="python"))
            for item in preliminary_manifest.inputs
        ]
        existing_edges = {
            (str(item.artifact_id), item.role, item.manifest_profile_sha256)
            for item in report_inputs
        }
        for role, reference in reference_payloads.items():
            item = _core_input(reference, role)
            edge = (str(item.artifact_id), item.role, item.manifest_profile_sha256)
            if edge not in existing_edges:
                report_inputs.append(item)
                existing_edges.add(edge)
        run_manifest_edge = _core_input(run_manifest_ref, "run_manifest")
        candidate_source_edge = _core_input(request.candidate_source_ref, "candidate_source")
        for item in (run_manifest_edge, candidate_source_edge):
            edge = (str(item.artifact_id), item.role, item.manifest_profile_sha256)
            if edge not in existing_edges:
                report_inputs.append(item)
                existing_edges.add(edge)
        final_report_ref = persist_backtest_report(
            ir_store,
            report_with_run_binding,
            inputs=report_inputs,
        )
        evidence = produce_empirical_calibration_evidence(store, final_report_ref, context=context)
        evidence_ref = persist_empirical_calibration_evidence(store, evidence)

        from polisyos.runtime.quality.generation_cycle import RealValueOwnerGateway

        def evidence_resolver(ref: object) -> object:
            return load_empirical_calibration_evidence(
                store,
                _as_ir_empirical_calibration_evidence_ref(ref),
            )

        method_result = {
            "output": {
                "report": load_backtest_report(ir_store, final_report_ref),
                "empirical_calibration_evidence_ref": evidence_ref,
                "expected_rule_version_ref": context.rule_version_ref,
                "temporal_roles": request.temporal_roles.model_dump(mode="python"),
            }
        }
        try:
            s10_result = RealValueOwnerGateway(
                empirical_evidence_resolver=evidence_resolver,
                artifact_store=store,
            ).produce_forecast_inputs(
                candidate=candidate,
                problem=problem,
                world_record=world_record,
                method_result=method_result,
                selected_method_fqn=_METHOD_FQN,
            )
        except (TypeError, ValueError) as exc:
            raise PredictiveCalibrationError(
                "predictive_calibration_s10_projection_unresolved",
                "The selected candidate could not consume the re-opened predictive evidence.",
            ) from exc
        s10_record = s10_result.get("forecast_calibration_record")
        s10_support = s10_result.get("forecast_support")
        if s10_record is None or s10_support is None:
            raise PredictiveCalibrationError("predictive_calibration_s10_record_missing")
        counterfactual_status = _required_text(
            getattr(s10_record, "counterfactual_credibility", None),
            "counterfactual_credibility",
        )
        if counterfactual_status != "not_established":
            raise PredictiveCalibrationError(
                "predictive_calibration_s10_credibility_not_conservative"
            )

        created_at = datetime.now(UTC).replace(microsecond=0)
        s10_summary = _s10_summary_from_owner(s10_record, s10_support)
        nominal = evidence.nominal_confidence_level
        association = PredictiveCalibrationAssociation(
            event_id=event_id,
            intent_id=request.intent_id,
            request_sha256=request_sha256,
            run_id=run_id,
            control_run_id=control_run_id,
            job_id=job_id,
            tenant_id=tenant_id,
            cell_id=cell_id,
            run_manifest_ref=run_manifest_ref,
            candidate_source_ref=request.candidate_source_ref,
            observed_source_ref=ArtifactRef.model_validate(owner_result.observed_source_ref),
            model_spec_ref=request.model_spec_ref,
            policy_spec_ref=request.policy_spec_ref,
            calibration_rule_ref=request.calibration_rule_ref,
            backtest_report_ref=ArtifactRef.model_validate(final_report_ref),
            empirical_evidence_ref=ArtifactRef.model_validate(evidence_ref),
            uncertainty_bundle_ref=ArtifactRef.model_validate(owner_result.uncertainty_bundle_ref),
            value_data_profile_ref=(
                None
                if owner_result.value_data_profile_ref is None
                else ArtifactRef.model_validate(owner_result.value_data_profile_ref)
            ),
            forecast_profile_member_ref=(
                None
                if owner_result.forecast_profile_member_ref is None
                else ArtifactRef.model_validate(owner_result.forecast_profile_member_ref)
            ),
            profile_join_status=(
                "joined_candidate"
                if owner_result.value_data_profile_ref is not None
                else "profileless_legacy"
            ),
            observed_numerator=evidence.recomputed_numerator,
            observed_denominator=evidence.recomputed_denominator,
            observed_hit_rate=evidence.recomputed_pass_rate or 0.0,
            nominal_confidence_level=nominal,
            owner_suitability=owner_result.empirical_suitability,
            s10=s10_summary,
            may_not_use_for=s10_summary.may_not_use_for or (),
            evidence_reason_codes=evidence.failure_codes,
            created_at=created_at,
        )
        association_ref = _persist_association(
            store=store,
            association=association,
            report_inputs=tuple(report_inputs),
        )
        result_ref_json = json.dumps(
            association_ref.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
        )
        operation_store.complete_runtime_operation_intent(
            key=key,
            owner_token=owner_token,
            result_ref_json=result_ref_json,
            event_id=event_id,
            publish=lambda: _append_association_event(
                event_log=event_log,
                association=association,
                association_ref=association_ref,
                request_sha256=request_sha256,
                refs=(
                    run_manifest_ref,
                    request.candidate_source_ref,
                    request.observed_source_ref,
                    request.model_spec_ref,
                    request.policy_spec_ref,
                    request.calibration_rule_ref,
                    final_report_ref,
                    evidence_ref,
                    owner_result.uncertainty_bundle_ref,
                    *(
                        ()
                        if owner_result.value_data_profile_ref is None
                        else (
                            owner_result.value_data_profile_ref,
                            owner_result.forecast_profile_member_ref,
                        )
                    ),
                ),
            ),
        )
        return association_ref, association
    except BaseException as exc:
        reason_code = (
            exc.code
            if isinstance(exc, PredictiveCalibrationError)
            else (
                "predictive_calibration_owner_failed"
                if owner_started
                else "predictive_calibration_preflight_refused"
            )
        )
        try:
            if owner_started:
                operation_store.require_runtime_operation_recovery(
                    key=key,
                    owner_token=owner_token,
                    reason_code=reason_code,
                )
            else:
                operation_store.refuse_runtime_operation_intent(
                    key=key,
                    owner_token=owner_token,
                    reason_code=reason_code,
                )
        except Exception:
            # Preserve the original failure. A failed transition leaves the
            # row pending, which remains fail-closed.
            _logger.exception(
                "Could not transition failed predictive-calibration intent; it remains pending"
            )
        raise


def _is_predictive_calibration_association_event(
    event: object,
    *,
    run_id: str,
    job_id: str,
) -> bool:
    """Select only this producer's association publication before newest-first choice."""
    artifact_refs = getattr(event, "artifact_refs", ())
    if not isinstance(artifact_refs, (tuple, list)) or len(artifact_refs) != 1:
        return False
    artifact_id = str(artifact_refs[0])
    return (
        getattr(event, "event_type", None) == _ASSOCIATION_EVENT
        and getattr(event, "event_source", None) == "polisyos.runtime"
        and getattr(event, "producer_component", None)
        == "polisyos.runtime.http.predictive_calibration"
        and getattr(event, "phase", None) == "predictive_calibration_publication"
        and getattr(event, "run_id", None) == run_id
        and getattr(event, "job_id", None) == job_id
        and getattr(event, "event_subject", None)
        == f"run/{run_id}/job/{job_id}/predictive-calibration/{artifact_id}"
    )


def load_run_predictive_calibration(
    *,
    store: ArtifactStore,
    run: IndexedRunRecord,
    event_log: _DiagnosticEventLog,
    event_scope: Mapping[str, str],
) -> tuple[ArtifactRef, PredictiveCalibrationAssociation]:
    """Resolve an append-only association and recompute its complete S10 seam."""

    run_details = getattr(run, "details", None)
    run_id = _required_text(getattr(run_details, "run_id", None), "run_id")
    job_id = _required_text(getattr(run_details, "control_job_id", None), "control_job_id")
    tenant_id = _required_text(getattr(run_details, "tenant_id", None), "tenant_id")
    cell_id = _required_text(getattr(run_details, "cell_id", None), "cell_id")
    _require_event_scope(
        event_scope,
        run_id=run_id,
        job_id=job_id,
        tenant_id=tenant_id,
        cell_id=cell_id,
    )
    run_manifest_ref = _selected_run_manifest(run_details)
    _require_event_log_owner(
        event_log,
        store=store,
        run_id=run_id,
        job_id=job_id,
        run_manifest_ref=run_manifest_ref,
    )
    list_events = getattr(event_log, "list_events", None)
    if not callable(list_events):
        raise PredictiveCalibrationError("predictive_calibration_event_log_unavailable")
    records = list_events(run_id=run_id, job_id=job_id, limit=1000)
    if len(records) >= 1000:
        raise PredictiveCalibrationError("predictive_calibration_event_history_bounded")
    record = next(
        (
            item
            for item in reversed(records)
            if _is_predictive_calibration_association_event(
                getattr(item, "event", None), run_id=run_id, job_id=job_id
            )
        ),
        None,
    )
    if record is None:
        raise FileNotFoundError("run predictive calibration association was not found")
    event = record.event
    if (
        event.event_source != "polisyos.runtime"
        or event.producer_component != "polisyos.runtime.http.predictive_calibration"
        or event.phase != "predictive_calibration_publication"
        or event.run_id != run_id
        or event.job_id != job_id
        or event.tenant_id != tenant_id
        or event.cell_id != cell_id
    ):
        raise PredictiveCalibrationError("predictive_calibration_event_scope_mismatch")
    payload = _read_event_payload(store, record)
    if payload.get("schema_version") not in {
        _ASSOCIATION_VERSION,
        _LEGACY_ASSOCIATION_VERSION,
    }:
        raise PredictiveCalibrationError("predictive_calibration_event_payload_schema_mismatch")
    raw_association_ref = payload.get("association_ref")
    try:
        association_ref = ArtifactRef.model_validate(raw_association_ref)
    except (TypeError, ValueError) as exc:
        raise PredictiveCalibrationError("predictive_calibration_association_ref_invalid") from exc
    if str(association_ref.artifact_id) not in event.artifact_refs:
        raise PredictiveCalibrationError("predictive_calibration_event_ref_mismatch")
    association = _load_association(store, association_ref)
    if _association_event_version(association.schema_version) != payload.get("schema_version"):
        raise PredictiveCalibrationError(
            "predictive_calibration_event_association_binding_mismatch"
        )
    expected_event_inputs = {
        str(getattr(association, field).artifact_id)
        for field in (
            "run_manifest_ref",
            "candidate_source_ref",
            "observed_source_ref",
            "model_spec_ref",
            "policy_spec_ref",
            "calibration_rule_ref",
            "backtest_report_ref",
            "empirical_evidence_ref",
            "uncertainty_bundle_ref",
        )
    }
    if association.value_data_profile_ref is not None:
        expected_event_inputs.add(str(association.value_data_profile_ref.artifact_id))
        expected_event_inputs.add(str(association.forecast_profile_member_ref.artifact_id))
    if (
        payload.get("intent_id") != association.intent_id
        or payload.get("request_sha256") != association.request_sha256
        or association.event_id != event.event_id
        or association.created_at != event.event_time
        or association.run_id != event.run_id
        or association.job_id != event.job_id
        or association.tenant_id != event.tenant_id
        or association.cell_id != event.cell_id
        or not expected_event_inputs.issubset(set(event.input_refs))
    ):
        raise PredictiveCalibrationError(
            "predictive_calibration_event_association_binding_mismatch"
        )
    _validate_current_run_binding(store, run_details, association, event_log=event_log)
    return association_ref, association


def _n4_outcome_target_binding_record(
    candidate_source: object,
    target_metric: str,
) -> dict[str, str]:
    """Record both typed identities without asserting a mapping between them."""
    problem = getattr(candidate_source, "problem", None)
    outcome = getattr(problem, "outcome_of_interest", None)
    target_variable = _required_text(getattr(outcome, "target_variable", None), "target_variable")
    metric_id = _required_text(getattr(outcome, "metric_id", None), "metric_id")
    observed_target_metric = _required_text(target_metric, "target_metric")
    return {
        "status": "not_established",
        "reason_code": _N4_OUTCOME_BINDING_LIMITATION_CODE,
        "n4_target_variable": target_variable,
        "n4_metric_id": metric_id,
        "observed_target_metric": observed_target_metric,
    }


def _association_event_version(schema_version: str) -> str:
    versions = {
        _ASSOCIATION_SCHEMA: _ASSOCIATION_VERSION,
        _PRIOR_ASSOCIATION_SCHEMA: _PRIOR_ASSOCIATION_VERSION,
        _LEGACY_ASSOCIATION_SCHEMA: _LEGACY_ASSOCIATION_VERSION,
    }
    try:
        return versions[schema_version]
    except KeyError as exc:
        raise PredictiveCalibrationError(
            "predictive_calibration_association_manifest_mismatch"
        ) from exc


def _request_sha256(request: PredictiveCalibrationRequest) -> str:
    """Hash the exact declared request, including every selected ref profile."""

    return hashlib.sha256(
        to_canonical_bytes(request.model_dump(mode="json"), CoreCanonSpec(forbid_floats=False))
    ).hexdigest()


def _operation_body_sha256(
    *,
    request: PredictiveCalibrationRequest,
    run_id: str,
    job_id: str,
    tenant_id: str,
    cell_id: str,
    run_manifest_ref: ArtifactRef,
) -> str:
    """Bind request refs and the selected run profile into the owner-row digest."""

    bound_request = {
        "schema_version": "polisyos.runtime.operation_intent_binding.v1",
        "request": request.model_dump(mode="json"),
        "run_id": run_id,
        "job_id": job_id,
        "tenant_id": tenant_id,
        "cell_id": cell_id,
        "run_manifest_ref": run_manifest_ref.model_dump(mode="json"),
    }
    return hashlib.sha256(
        to_canonical_bytes(bound_request, CoreCanonSpec(forbid_floats=False))
    ).hexdigest()


def _intent_event_id(key: RuntimeOperationIntentKey) -> str:
    """Derive an event identity from the complete authorized intent scope."""

    material = json.dumps(key.identity, ensure_ascii=False, separators=(",", ":"))
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()
    return f"evt_predictive_calibration_{digest[:32]}"


def _legacy_intent_event_id(run_id: str, intent_id: str) -> str:
    """Locate pre-owner events whose identity did not include the principal scope."""

    digest = hashlib.sha256(f"{run_id}\0{intent_id}".encode()).hexdigest()
    return f"evt_predictive_calibration_{digest[:32]}"


def _operation_intent_store(
    event_log: _DiagnosticEventLog,
) -> RuntimeOperationIntentStore:
    """Return the durable owner only when the event log shares its transaction store."""

    owner = getattr(event_log, "_store", None)
    required = (
        "begin_runtime_operation_intent",
        "get_runtime_operation_intent",
        "complete_runtime_operation_intent",
        "refuse_runtime_operation_intent",
        "require_runtime_operation_recovery",
    )
    if owner is None or any(not callable(getattr(owner, name, None)) for name in required):
        raise PredictiveCalibrationError("predictive_calibration_intent_store_unavailable")
    return cast("RuntimeOperationIntentStore", owner)


def _claim_result_matches(
    claim: RuntimeOperationIntentClaim,
    replay: tuple[ArtifactRef, PredictiveCalibrationAssociation],
) -> bool:
    """Require database custody and the reopened event to name the same full ref."""

    ref, association = replay
    stored_json = claim.record.result_ref_json
    if stored_json is None or claim.record.event_id != association.event_id:
        return False
    try:
        stored_ref = ArtifactRef.model_validate(json.loads(stored_json))
    except (TypeError, ValueError, json.JSONDecodeError):
        return False
    return artifact_ref_identity_key(stored_ref) == artifact_ref_identity_key(
        ref
    ) and stored_ref.model_dump(mode="json") == ref.model_dump(mode="json")


def _load_existing_intent(
    *,
    store: ArtifactStore,
    run: IndexedRunRecord,
    event_log: _DiagnosticEventLog,
    event_scope: Mapping[str, str],
    event_id: str,
    intent_id: str,
    request_sha256: str,
    run_manifest_ref: ArtifactRef,
) -> tuple[ArtifactRef, PredictiveCalibrationAssociation] | None:
    """Reopen an exact previously published intent after retry or lost response."""

    run_details = getattr(run, "details", None)
    run_id = _required_text(getattr(run_details, "run_id", None), "run_id")
    job_id = _required_text(getattr(run_details, "control_job_id", None), "control_job_id")
    records = event_log.list_events(run_id=run_id, job_id=job_id, limit=1000)
    if len(records) >= 1000:
        raise PredictiveCalibrationError("predictive_calibration_event_history_bounded")
    record = next(
        (
            item
            for item in records
            if getattr(getattr(item, "event", None), "event_id", None) == event_id
        ),
        None,
    )
    legacy_scope_unverifiable = False
    if record is None:
        legacy_event_id = _legacy_intent_event_id(run_id, intent_id)
        record = next(
            (
                item
                for item in records
                if getattr(getattr(item, "event", None), "event_id", None) == legacy_event_id
            ),
            None,
        )
        legacy_scope_unverifiable = record is not None
    if record is None:
        return None
    event = record.event
    _require_event_scope(
        event_scope,
        run_id=run_id,
        job_id=job_id,
        tenant_id=_required_text(getattr(run_details, "tenant_id", None), "tenant_id"),
        cell_id=_required_text(getattr(run_details, "cell_id", None), "cell_id"),
    )
    if (
        event.event_source != "polisyos.runtime"
        or event.event_type != _ASSOCIATION_EVENT
        or event.producer_component != "polisyos.runtime.http.predictive_calibration"
        or event.phase != "predictive_calibration_publication"
        or event.run_id != run_id
        or event.job_id != job_id
    ):
        raise PredictiveCalibrationError("predictive_calibration_intent_event_binding_mismatch")
    payload = _read_event_payload(store, record)
    if payload.get("schema_version") not in {
        _ASSOCIATION_VERSION,
        _LEGACY_ASSOCIATION_VERSION,
    }:
        raise PredictiveCalibrationError("predictive_calibration_event_payload_schema_mismatch")
    if payload.get("intent_id") != intent_id or payload.get("request_sha256") != request_sha256:
        raise PredictiveCalibrationError("predictive_calibration_intent_conflict")
    if legacy_scope_unverifiable:
        raise PredictiveCalibrationError("predictive_calibration_legacy_intent_scope_unverifiable")
    try:
        association_ref = ArtifactRef.model_validate(payload.get("association_ref"))
    except (TypeError, ValueError) as exc:
        raise PredictiveCalibrationError("predictive_calibration_association_ref_invalid") from exc
    if str(association_ref.artifact_id) not in event.artifact_refs:
        raise PredictiveCalibrationError("predictive_calibration_event_ref_mismatch")
    association = _load_association(store, association_ref)
    if _association_event_version(association.schema_version) != payload.get("schema_version"):
        raise PredictiveCalibrationError(
            "predictive_calibration_event_association_binding_mismatch"
        )
    control_run_id = _require_event_log_owner(
        event_log,
        store=store,
        run_id=run_id,
        job_id=job_id,
        run_manifest_ref=run_manifest_ref,
    )
    if (
        association.event_id != event_id
        or association.intent_id != intent_id
        or association.request_sha256 != request_sha256
        or association.control_run_id != control_run_id
    ):
        raise PredictiveCalibrationError("predictive_calibration_intent_association_mismatch")
    _validate_current_run_binding(store, run_details, association, event_log=event_log)
    return association_ref, association


def _persist_evidence_role_refs(
    *,
    store: ArtifactStore,
    report_id: str,
    threshold: float,
    model_spec_ref: ArtifactRef,
    policy_spec_ref: ArtifactRef,
    candidate_source_ref: ArtifactRef,
    observed_source_ref: object,
    training_slice_ref: object,
    uncertainty_bundle_ref: object,
    method_artifact_ref: object,
    calibration_rule_ref: object,
) -> dict[str, EvidenceArtifactRef]:
    """Persist every bridge role with exact input edges and honest unknowns."""

    observed_ref = ArtifactRef.model_validate(observed_source_ref)
    training_ref = ArtifactRef.model_validate(training_slice_ref)
    uncertainty_ref = ArtifactRef.model_validate(uncertainty_bundle_ref)
    method_ref = ArtifactRef.model_validate(method_artifact_ref)
    rule_ref = ArtifactRef.model_validate(calibration_rule_ref)
    binding = {
        "report_id": report_id,
        "model_spec_ref": str(model_spec_ref.artifact_id),
        "policy_spec_ref": str(policy_spec_ref.artifact_id),
        "estimand": "predictive_interval_coverage",
        "method_ref": _METHOD_REF,
        "method_version": _METHOD_VERSION,
        "rule_version_ref": CALIBRATION_RULE_ID,
        "calibration_threshold": threshold,
        "authority_scope": "predictive_only",
    }
    role_definition = tuple[
        str,
        str,
        str,
        tuple[tuple[ArtifactRef, str], ...],
        Mapping[str, object],
    ]
    definitions: tuple[role_definition, ...] = (
        (
            "scope_binding",
            "report_id",
            report_id,
            (
                (candidate_source_ref, "candidate_source"),
                (model_spec_ref, "model_spec"),
                (policy_spec_ref, "policy_spec"),
                (rule_ref, "calibration_rule"),
            ),
            {"binding": binding, "authority_scope": "predictive_only"},
        ),
        (
            "calibration_threshold",
            "identity",
            _identity("calibration_threshold", report_id, {"threshold": threshold}),
            ((rule_ref, "calibration_rule"),),
            {"threshold": threshold},
        ),
        (
            "observed_outcome",
            "identity",
            _identity("observed_outcome", report_id, observed_ref),
            ((observed_ref, "observed_source"),),
            {"observed_source_ref": observed_ref.model_dump(mode="json")},
        ),
        (
            "prediction",
            "identity",
            _identity("prediction", report_id, uncertainty_ref),
            ((uncertainty_ref, "uncertainty_bundle"),),
            {"uncertainty_bundle_ref": uncertainty_ref.model_dump(mode="json")},
        ),
        (
            "evaluation_design",
            "identity",
            _identity("evaluation_design", report_id, training_ref),
            ((training_ref, "training_slice"),),
            {"training_slice_ref": training_ref.model_dump(mode="json")},
        ),
        (
            "credible_evaluation",
            "identity",
            _identity("credible_evaluation", report_id, candidate_source_ref),
            ((candidate_source_ref, "candidate_source"),),
            {"credibility_status": "not_established"},
        ),
        (
            "source_lineage",
            "identity",
            _identity("source_lineage", report_id, (candidate_source_ref, observed_ref)),
            (
                (candidate_source_ref, "candidate_source"),
                (observed_ref, "observed_source"),
            ),
            {
                "candidate_source_ref": candidate_source_ref.model_dump(mode="json"),
                "observed_source_ref": observed_ref.model_dump(mode="json"),
            },
        ),
        (
            "method_lineage",
            "identity",
            _identity("method_lineage", report_id, (method_ref, rule_ref)),
            ((method_ref, "method_artifact"), (rule_ref, "calibration_rule")),
            {
                "method_ref": _METHOD_REF,
                "method_version": _METHOD_VERSION,
                "method_artifact_ref": method_ref.model_dump(mode="json"),
                "calibration_rule_ref": rule_ref.model_dump(mode="json"),
            },
        ),
    )
    refs: dict[str, EvidenceArtifactRef] = {}
    ir_store = ensure_ir_artifact_store(store)
    for role, identity_path, identity_value, input_edges, fields in definitions:
        kind, schema_name, schema_version = REFERENCE_PROFILES[role]
        payload = {
            "role": role,
            "report_id": report_id,
            "identity": identity_value,
            **dict(fields),
        }
        selected = put_json_artifact(
            ir_store,
            payload,
            kind=kind,
            schema_name=schema_name,
            schema_version=schema_version,
            inputs=[
                InputRef(
                    artifact_id=ref.artifact_id,
                    role=input_role,
                    manifest_profile_sha256=ref.manifest_profile_sha256,
                )
                for ref, input_role in input_edges
            ],
            canon_spec=IRCanonSpec(forbid_floats=False),
            return_selected_profile=True,
        )
        typed_ref = EvidenceArtifactRef.model_validate(
            {
                **selected,
                "role": role,
                "schema_name": schema_name,
                "schema_version": schema_version,
                "identity_path": identity_path,
                "identity_value": identity_value,
            }
        )
        refs[role] = typed_ref
    return refs


def _build_empirical_context(
    refs: Mapping[str, EvidenceArtifactRef],
    *,
    model_spec_ref: ArtifactRefModel | None,
    policy_spec_ref: ArtifactRefModel | None,
    threshold: float,
    temporal_roles: ForecastTemporalRoles,
) -> EmpiricalCalibrationContext:
    """Bind report, exact references, and caller times without upgrading provenance."""

    if model_spec_ref is None or policy_spec_ref is None:
        raise PredictiveCalibrationError("predictive_calibration_model_policy_pair_missing")
    return EmpiricalCalibrationContext(
        model_spec_ref=str(model_spec_ref.artifact_id),
        policy_spec_ref=str(policy_spec_ref.artifact_id),
        estimand="predictive_interval_coverage",
        method_ref=_METHOD_REF,
        method_version=_METHOD_VERSION,
        rule_version_ref=CALIBRATION_RULE_ID,
        calibration_threshold=threshold,
        scope_binding_ref=refs["scope_binding"],
        calibration_threshold_ref=refs["calibration_threshold"],
        observed_outcome_ref=refs["observed_outcome"],
        prediction_ref=refs["prediction"],
        evaluation_design_ref=refs["evaluation_design"],
        credible_evaluation_evidence_ref=refs["credible_evaluation"],
        source_lineage_refs=(refs["source_lineage"],),
        method_lineage_refs=(refs["method_lineage"],),
        prediction_time=temporal_roles.prediction_time,
        observation_time=temporal_roles.observation_time,
        policy_effective_time=temporal_roles.policy_effective_time,
        data_valid_time=temporal_roles.data_valid_time,
        calibration_window_start=temporal_roles.calibration_window_start,
        calibration_window_end=temporal_roles.calibration_window_end,
        evidence_origin="run-bound candidate report",
    )


def _persist_association(
    *,
    store: ArtifactStore,
    association: PredictiveCalibrationAssociation,
    report_inputs: Sequence[InputRef],
) -> ArtifactRef:
    """Persist one typed association with exact source and report lineage."""

    refs = (
        (association.run_manifest_ref, "run_manifest"),
        (association.candidate_source_ref, "candidate_source"),
        (association.observed_source_ref, "observed_source"),
        (association.model_spec_ref, "model_spec"),
        (association.policy_spec_ref, "policy_spec"),
        (association.calibration_rule_ref, "calibration_rule"),
        (association.backtest_report_ref, "backtest_report"),
        (association.empirical_evidence_ref, "empirical_calibration_evidence"),
        (association.uncertainty_bundle_ref, "uncertainty_bundle"),
        *(
            ()
            if association.value_data_profile_ref is None
            else (
                (association.value_data_profile_ref, "value_data_profile"),
                (association.forecast_profile_member_ref, "forecast_profile_member"),
            )
        ),
    )
    edges = [
        InputRef(
            artifact_id=ref.artifact_id,
            role=role,
            manifest_profile_sha256=ref.manifest_profile_sha256,
        )
        for ref, role in refs
    ]
    edges.extend(
        item
        for item in report_inputs
        if item.role in {"observed_data", "training_slice", "method_artifact"}
    )
    result = put_json_artifact(
        ensure_ir_artifact_store(store),
        association.model_dump(mode="json"),
        kind=_ASSOCIATION_KIND,
        schema_name=_ASSOCIATION_SCHEMA,
        schema_version=_ASSOCIATION_VERSION,
        inputs=edges,
        canon_spec=IRCanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    return ArtifactRef.model_validate(result)


def _append_association_event(
    *,
    event_log: _DiagnosticEventLog,
    association: PredictiveCalibrationAssociation,
    association_ref: ArtifactRef,
    request_sha256: str,
    refs: Sequence[ArtifactRef],
) -> object:
    """Publish only the selected association ref into the existing event stream."""

    event = DiagnosticEvent(
        event_id=association.event_id,
        event_source="polisyos.runtime",
        event_type=_ASSOCIATION_EVENT,
        event_time=association.created_at,
        event_subject=(
            f"run/{association.run_id}/job/{association.job_id}/"
            f"predictive-calibration/{association_ref.artifact_id}"
        ),
        schema_name=_ASSOCIATION_EVENT_SCHEMA,
        schema_version=_ASSOCIATION_EVENT_SCHEMA_VERSION,
        trace_id=association.event_id,
        span_id=f"span_{uuid.uuid4().hex[:16]}",
        parent_span_id=None,
        run_id=association.run_id,
        job_id=association.job_id,
        tenant_id=association.tenant_id,
        cell_id=association.cell_id,
        producer_component="polisyos.runtime.http.predictive_calibration",
        producer_version="1.0",
        execution_profile="candidate",
        phase="predictive_calibration_publication",
        state_before=None,
        state_after="candidate_diagnostic_persisted",
        payload_ref=None,
        artifact_refs=(str(association_ref.artifact_id),),
        input_refs=tuple(str(ref.artifact_id) for ref in refs),
        blocking_status=None,
        redaction_policy_ref="redaction-policy/runtime-diagnostics-v1",
        duplicate_of=None,
        dedupe_key=f"predictive-calibration:{association.event_id}",
        sampling_decision="always_record",
        sampling_rate=1.0,
    )
    return event_log.append(
        event,
        payload={
            "schema_version": _ASSOCIATION_VERSION,
            "intent_id": association.intent_id,
            "request_sha256": request_sha256,
            "association_ref": association_ref.model_dump(mode="json"),
        },
        payload_policy=DiagnosticEventPayloadPolicy(inline_max_bytes=2048),
    )


def _load_association(store: ArtifactStore, ref: ArtifactRef) -> PredictiveCalibrationAssociation:
    """Re-open association bytes and verify their exact selected manifest view."""

    if ref.manifest_profile_sha256 is None:
        raise PredictiveCalibrationError("predictive_calibration_association_profile_missing")
    manifest = store.get_manifest(ref)
    schema_contracts = {
        _ASSOCIATION_VERSION: _ASSOCIATION_SCHEMA,
        _PRIOR_ASSOCIATION_VERSION: _PRIOR_ASSOCIATION_SCHEMA,
        _LEGACY_ASSOCIATION_VERSION: _LEGACY_ASSOCIATION_SCHEMA,
    }
    schema_version = getattr(getattr(manifest, "artifact_schema", None), "version", None)
    schema_name = getattr(getattr(manifest, "artifact_schema", None), "name", None)
    if (
        manifest.kind != _ASSOCIATION_KIND
        or manifest.media_type != "application/json"
        or schema_contracts.get(schema_version) != schema_name
        or artifact_manifest_profile_sha256(manifest) != ref.manifest_profile_sha256
    ):
        raise PredictiveCalibrationError("predictive_calibration_association_manifest_mismatch")
    if not store.verify(ref).ok:
        raise PredictiveCalibrationError("predictive_calibration_association_integrity_failed")
    from polisyos.ir import CanonViolation
    from polisyos.ir import (
        get_json_artifact_with_bytes as _get_json_artifact_with_bytes,
    )

    try:
        payload, _raw_payload = _get_json_artifact_with_bytes(
            ensure_ir_artifact_store(store),
            ref,
        )
    except CanonViolation as exc:
        raise PredictiveCalibrationError(
            "predictive_calibration_association_profile_unverified"
        ) from exc
    try:
        association = PredictiveCalibrationAssociation.model_validate(payload)
    except ValidationError as exc:
        raise PredictiveCalibrationError("predictive_calibration_association_invalid") from exc
    if association.schema_version != schema_name:
        raise PredictiveCalibrationError("predictive_calibration_association_manifest_mismatch")
    _validate_association_input_edges(manifest, association)
    return association


def _validate_association_input_edges(
    manifest: ArtifactManifest,
    association: PredictiveCalibrationAssociation,
) -> None:
    expected = {
        (str(ref.artifact_id), role, ref.manifest_profile_sha256)
        for ref, role in (
            (association.run_manifest_ref, "run_manifest"),
            (association.candidate_source_ref, "candidate_source"),
            (association.observed_source_ref, "observed_source"),
            (association.model_spec_ref, "model_spec"),
            (association.policy_spec_ref, "policy_spec"),
            (association.calibration_rule_ref, "calibration_rule"),
            (association.backtest_report_ref, "backtest_report"),
            (association.empirical_evidence_ref, "empirical_calibration_evidence"),
            (association.uncertainty_bundle_ref, "uncertainty_bundle"),
            *(
                ()
                if association.value_data_profile_ref is None
                else (
                    (association.value_data_profile_ref, "value_data_profile"),
                    (
                        association.forecast_profile_member_ref,
                        "forecast_profile_member",
                    ),
                )
            ),
        )
    }
    actual = {
        (str(item.artifact_id), item.role, item.manifest_profile_sha256) for item in manifest.inputs
    }
    if not expected.issubset(actual):
        raise PredictiveCalibrationError("predictive_calibration_association_edges_mismatch")


def _validate_selected_value_data_profile(
    store: ArtifactStore, reference: ArtifactRef
) -> ResolvedValueProfileProjection:
    """Resolve canonical EMP-01 bytes and the exact activated source projection."""
    _require_selected_ref(store, reference, expected_kind=VALUE_DATA_PROFILE_KIND)
    from polisyos.runtime.quality.substrate_registry import (
        current_catalog_serving_source,
    )

    selected_source = current_catalog_serving_source()
    if selected_source is None:
        raise PredictiveCalibrationError(
            "predictive_calibration_catalog_serving_source_context_missing"
        )
    profile = _as_ir_artifact_ref(reference)
    manifest = store.get_manifest(reference)
    schema = getattr(manifest, "artifact_schema", None)
    if (
        schema is None
        or schema.name != VALUE_DATA_PROFILE_SCHEMA
        or schema.version != VALUE_DATA_PROFILE_SCHEMA_VERSION
    ):
        raise PredictiveCalibrationError("predictive_calibration_value_profile_schema_mismatch")
    try:
        payload = get_json_artifact(ensure_ir_artifact_store(store), profile)
        from polisyos.data_forge.read_api.catalog import (
            ActivatedAcquisitionObservationProjection,
        )
        from polisyos.runtime.quality import generation_cycle
        from polisyos.runtime.quality.generation_cycle import ValueDataProfile

        selected_profile = ValueDataProfile.model_validate(payload)
        profile_inputs = [
            item for item in manifest.inputs if item.role == "activated_source_projection"
        ]
        if len(profile_inputs) != 1 or profile_inputs[0].manifest_profile_sha256 is None:
            raise ValueError("selected profile lacks one exact source projection edge")
        source_input = profile_inputs[0]
        projection_ref = ArtifactRef.model_validate(
            {
                "artifact_id": source_input.artifact_id,
                "kind": VALUE_OWNER_PROJECTION_KIND,
                "media_type": "application/json",
                "manifest_profile_sha256": source_input.manifest_profile_sha256,
            }
        )
        _require_selected_ref(
            store,
            projection_ref,
            expected_kind=VALUE_OWNER_PROJECTION_KIND,
        )
        projection_manifest = store.get_manifest(projection_ref)
        projection_schema = getattr(projection_manifest, "artifact_schema", None)
        if (
            projection_schema is None
            or projection_schema.name != VALUE_OWNER_PROJECTION_SCHEMA
            or projection_schema.version != VALUE_OWNER_PROJECTION_SCHEMA_VERSION
        ):
            raise ValueError("selected source projection schema is unsupported")
        projection_payload = get_json_artifact(ensure_ir_artifact_store(store), projection_ref)
        selected_projection = ActivatedAcquisitionObservationProjection.model_validate(
            projection_payload
        )
        repo_root = selected_source.repo_root
        owner_projection, owner_passport, _ = (
            generation_cycle._read_canonical_active_source_projection(
                repo_root=repo_root,
                overlay_path=selected_source.overlay_path,
                artifact_store=store,
                supplied_projection=selected_projection,
            )
        )
        projection = validate_profile_projection_binding(
            profile=selected_profile,
            projection_payload=owner_projection.model_dump(mode="json"),
            passport_payload=owner_passport.model_dump(mode="json"),
            require_canonical_owner_profile_shape=True,
        )
        return ResolvedValueProfileProjection(
            profile=selected_profile,
            source_projection_ref=_as_ir_artifact_ref(projection_ref),
            projection=projection,
            source_passport=owner_passport,
        )
    except Exception as exc:
        raise PredictiveCalibrationError("predictive_calibration_value_profile_invalid") from exc


def _load_verified_observed_data_snapshot(
    store: ArtifactStore, observed_source_ref: ArtifactRef
) -> DataSnapshot:
    """Admit observed-source lineage without granting candidate-row authority."""
    from polisyos.runtime.quality.data_snapshot_lineage import (
        DataSnapshotSourceRowNotEstablishedError,
        validate_data_snapshot_owner_lineage,
    )

    snapshot_payload = get_json_artifact(
        ensure_ir_artifact_store(store), _as_ir_artifact_ref(observed_source_ref)
    )
    snapshot = DataSnapshot.model_validate(snapshot_payload)
    try:
        lineage_result = validate_data_snapshot_owner_lineage(store, observed_source_ref, snapshot)
        if lineage_result.required_admissibility_blockers:
            raise DataSnapshotSourceRowNotEstablishedError()
    except DataSnapshotSourceRowNotEstablishedError as exc:
        raise _AcquiredObservedSourceNotEstablishedError() from exc
    return snapshot


def _build_selected_profile_member(
    *,
    store: ArtifactStore,
    request: PredictiveCalibrationRequest,
    binding: ResolvedValueProfileProjection,
) -> ForecastProfileMemberV1:
    """Bind the selected profile to exact observed-source and data artifacts."""
    profile_ref = request.value_data_profile_ref
    unit_id = request.value_data_unit_id
    if profile_ref is None or unit_id is None:
        raise PredictiveCalibrationError("predictive_calibration_value_profile_selection_missing")
    try:
        snapshot = _load_verified_observed_data_snapshot(store, request.observed_source_ref)
        observed_data_ref = ArtifactRef.model_validate(snapshot.data_ref.model_dump(mode="json"))
        _require_selected_ref(store, observed_data_ref, expected_kind=None)
        observed_payload = get_json_artifact(
            ensure_ir_artifact_store(store), _as_ir_artifact_ref(observed_data_ref)
        )
        if not isinstance(observed_payload, Mapping):
            raise ValueError("observed source data is not a metric map")
        member, _values = join_profile_member_to_observed_series(
            profile=binding.profile,
            profile_ref=_as_ir_artifact_ref(profile_ref),
            source_projection_ref=binding.source_projection_ref,
            projection=binding.projection,
            observed_source_ref=_as_ir_artifact_ref(request.observed_source_ref),
            observed_data_ref=_as_ir_artifact_ref(observed_data_ref),
            target_metric=request.target_metric,
            unit_id=unit_id,
            observed_values=observed_payload.get(request.target_metric),
            source_passport=binding.source_passport,
        )
        return member
    except _AcquiredObservedSourceNotEstablishedError:
        raise
    except Exception as exc:
        raise PredictiveCalibrationError(
            "predictive_calibration_value_profile_observed_join_invalid"
        ) from exc


def _revalidate_profile_member_binding(
    store: ArtifactStore,
    association: PredictiveCalibrationAssociation,
    report: BacktestReport,
) -> None:
    """Recompute the profile/member join from exact current CAS bytes on fresh GET."""
    profile_ref = association.value_data_profile_ref
    member_ref = association.forecast_profile_member_ref
    if profile_ref is None or member_ref is None:
        if association.profile_join_status != "profileless_legacy":
            raise PredictiveCalibrationError("predictive_calibration_profileless_status_mismatch")
        if (
            association.schema_version == _ASSOCIATION_SCHEMA
            and report.metadata.get("profile_join_status") != "profileless_legacy"
        ):
            raise PredictiveCalibrationError("predictive_calibration_profileless_report_mismatch")
        return
    if association.profile_join_status != "joined_candidate":
        raise PredictiveCalibrationError("predictive_calibration_profile_member_status_mismatch")
    binding = _validate_selected_value_data_profile(store, profile_ref)
    _require_selected_ref(store, member_ref, expected_kind=FORECAST_PROFILE_MEMBER_KIND)
    member_manifest = store.get_manifest(member_ref)
    member_schema = getattr(member_manifest, "artifact_schema", None)
    if (
        member_schema is None
        or member_schema.name != FORECAST_PROFILE_MEMBER_SCHEMA
        or member_schema.version != FORECAST_PROFILE_MEMBER_SCHEMA_VERSION
    ):
        raise PredictiveCalibrationError("predictive_calibration_profile_member_schema_mismatch")
    try:
        member_payload = get_json_artifact(
            ensure_ir_artifact_store(store), _as_ir_artifact_ref(member_ref)
        )
        member = ForecastProfileMemberV1.model_validate(member_payload)
        snapshot = _load_verified_observed_data_snapshot(store, association.observed_source_ref)
        snapshot_data_ref = ArtifactRefModel.model_validate(
            snapshot.data_ref.model_dump(mode="json")
        )
        data_ref = _as_ir_artifact_ref(member.observed_data_ref)
        if snapshot_data_ref != member.observed_data_ref:
            raise ValueError(
                "selected observed data ref does not exactly belong to the source snapshot"
            )
        if member.observed_source_ref != _as_ir_artifact_ref(association.observed_source_ref):
            raise ValueError("member receipt names a different observed source view")
        if member.source_projection_ref != binding.source_projection_ref:
            raise ValueError("member receipt names a different source projection view")
        _require_selected_ref(
            store,
            ArtifactRef.model_validate(data_ref.model_dump(mode="json")),
            expected_kind=None,
        )
        observed_payload = get_json_artifact(ensure_ir_artifact_store(store), data_ref)
        target_metric = _required_text(report.metadata.get("target_metric"), "target_metric")
        if not isinstance(observed_payload, Mapping):
            raise ValueError("observed source data is not a metric map")
        recomputed, _values = join_profile_member_to_observed_series(
            profile=binding.profile,
            profile_ref=_as_ir_artifact_ref(profile_ref),
            source_projection_ref=binding.source_projection_ref,
            projection=binding.projection,
            observed_source_ref=_as_ir_artifact_ref(association.observed_source_ref),
            observed_data_ref=data_ref,
            target_metric=target_metric,
            unit_id=member.unit_id,
            observed_values=observed_payload.get(target_metric),
            source_passport=binding.source_passport,
        )
        if recomputed != member:
            raise ValueError("stored profile/member join receipt differs from recomputation")
        if report.metadata.get("profile_join_status") != "joined_candidate":
            raise ValueError("run-bound report lost the selected profile join status")
        if report.metadata.get("value_data_profile_ref") != profile_ref.model_dump(mode="json"):
            raise ValueError("run-bound report lost the selected profile ref")
        if report.metadata.get("forecast_profile_member_ref") != member_ref.model_dump(mode="json"):
            raise ValueError("run-bound report lost the profile member receipt ref")
        expected_edges = {
            (
                str(profile_ref.artifact_id),
                "value_data_profile",
                profile_ref.manifest_profile_sha256,
            ),
            (
                str(binding.source_projection_ref.artifact_id),
                "activated_source_projection",
                binding.source_projection_ref.manifest_profile_sha256,
            ),
            (
                str(association.observed_source_ref.artifact_id),
                "observed_source",
                association.observed_source_ref.manifest_profile_sha256,
            ),
            (
                str(data_ref.artifact_id),
                "observed_data",
                data_ref.manifest_profile_sha256,
            ),
        }
        actual_edges = {
            (str(item.artifact_id), item.role, item.manifest_profile_sha256)
            for item in member_manifest.inputs
        }
        if not expected_edges.issubset(actual_edges):
            raise ValueError("profile member manifest lost exact source input edges")
    except _AcquiredObservedSourceNotEstablishedError:
        raise
    except Exception as exc:
        raise PredictiveCalibrationError(
            "predictive_calibration_profile_member_reopen_mismatch"
        ) from exc


def _validate_current_run_binding(
    store: ArtifactStore,
    run_details: RunDetails,
    association: PredictiveCalibrationAssociation,
    *,
    event_log: _DiagnosticEventLog,
) -> None:
    """Require the reopened association to remain attached to this exact run view."""

    run_manifest_ref = _selected_run_manifest(run_details)
    control_run_id = _require_event_log_owner(
        event_log,
        store=store,
        run_id=_required_text(getattr(run_details, "run_id", None), "run_id"),
        job_id=_required_text(getattr(run_details, "control_job_id", None), "control_job_id"),
        run_manifest_ref=run_manifest_ref,
    )
    if association.control_run_id != control_run_id or artifact_ref_identity_key(
        association.run_manifest_ref
    ) != artifact_ref_identity_key(run_manifest_ref):
        raise PredictiveCalibrationError("predictive_calibration_run_manifest_mismatch")
    if (
        association.run_id != getattr(run_details, "run_id", None)
        or association.job_id != getattr(run_details, "control_job_id", None)
        or association.tenant_id != getattr(run_details, "tenant_id", None)
        or association.cell_id != getattr(run_details, "cell_id", None)
    ):
        raise PredictiveCalibrationError("predictive_calibration_run_scope_mismatch")
    roots = _root_refs(run_details)
    root_input_refs = _root_input_refs(run_details)
    _require_candidate_source_ref(association.candidate_source_ref, run_details, roots)
    _require_run_root_ref(association.observed_source_ref, root_input_refs, "observed_source")
    run_bound_refs = (*roots, *root_input_refs)
    for role, reference in (
        ("model_spec", association.model_spec_ref),
        ("policy_spec", association.policy_spec_ref),
        ("calibration_rule", association.calibration_rule_ref),
        *(
            ()
            if association.value_data_profile_ref is None
            else (("value_data_profile", association.value_data_profile_ref),)
        ),
    ):
        _require_run_root_ref(reference, run_bound_refs, role)
    _require_selected_ref(
        store,
        association.candidate_source_ref,
        expected_kind="runtime.quality.n4_candidate_scenario_source",
    )
    _require_selected_ref(
        store,
        association.observed_source_ref,
        expected_kind="fabric.data_snapshot",
    )
    _require_selected_ref(store, association.model_spec_ref, expected_kind="ir.model_spec")
    _require_selected_ref(store, association.policy_spec_ref, expected_kind="ir.policy_spec")
    _require_selected_ref(
        store,
        association.calibration_rule_ref,
        expected_kind="ir.forecast_calibration_rule",
    )
    report = load_backtest_report(
        ensure_ir_artifact_store(store),
        _as_ir_artifact_ref(association.backtest_report_ref),
    )
    _revalidate_profile_member_binding(store, association, report)
    evidence = load_empirical_calibration_evidence(
        store,
        _as_ir_empirical_calibration_evidence_ref(association.empirical_evidence_ref),
    )
    if (
        report.report_id != evidence.report_id
        or artifact_ref_identity_key(ArtifactRef.model_validate(evidence.report_ref))
        != artifact_ref_identity_key(association.backtest_report_ref)
        or evidence.recomputed_numerator != association.observed_numerator
        or evidence.recomputed_denominator != association.observed_denominator
        or evidence.recomputed_pass_rate != association.observed_hit_rate
        or evidence.failure_codes != association.evidence_reason_codes
    ):
        raise PredictiveCalibrationError("predictive_calibration_evidence_reopen_mismatch")
    recomputed_s10 = _recompute_s10(store, association, report=report, evidence=evidence)
    if not _s10_summary_matches(
        association.s10,
        recomputed_s10,
        association_schema_version=association.schema_version,
        candidate_source_kind=association.candidate_source_ref.kind,
    ):
        raise PredictiveCalibrationError("predictive_calibration_s10_reopen_mismatch")


def _s10_summary_matches(
    stored: PredictiveCalibrationS10Summary,
    recomputed: PredictiveCalibrationS10Summary,
    *,
    association_schema_version: str,
    candidate_source_kind: str,
) -> bool:
    """Compare the complete fresh projection for N4 and retain v2 grade semantics elsewhere."""
    if (
        association_schema_version == _LEGACY_ASSOCIATION_SCHEMA
        and candidate_source_kind != "runtime.quality.n4_candidate_scenario_source"
    ):
        legacy_grade_fields = (
            "calibration_status",
            "forecast_tier",
            "counterfactual_credibility",
            "numerator",
            "denominator",
            "observed_pass_rate",
            "calibration_record_ref",
        )
        return all(
            getattr(stored, field) == getattr(recomputed, field) for field in legacy_grade_fields
        )
    return stored == recomputed


def _recompute_s10(
    store: ArtifactStore,
    association: PredictiveCalibrationAssociation,
    *,
    report: BacktestReport | None = None,
    evidence: object | None = None,
) -> PredictiveCalibrationS10Summary:
    """Recompute S10 from freshly resolved report and evidence artifacts."""

    from polisyos.runtime.quality.generation_cycle import RealValueOwnerGateway
    from polisyos.runtime.quality.generation_source import (
        GenerationSourceRepository,
        N4CandidateScenarioSourceRecordV3,
    )

    try:
        candidate_source = GenerationSourceRepository(store).load_candidate_scenario_source_for_n5(
            association.candidate_source_ref,
            expected_run_id=association.control_run_id,
            expected_job_id=association.job_id,
            expected_tenant_id=association.tenant_id,
            expected_cell_id=association.cell_id,
        )
    except (FileNotFoundError, OSError, TypeError, ValueError) as exc:
        raise PredictiveCalibrationError(
            "predictive_calibration_candidate_source_reopen_failed"
        ) from exc
    if type(candidate_source) is not N4CandidateScenarioSourceRecordV3:
        raise PredictiveCalibrationError("predictive_calibration_candidate_source_profile_mismatch")
    candidate = candidate_source.candidate
    context_inputs = getattr(candidate_source.profile, "context_inputs", None)
    world_record = getattr(context_inputs, "world_model_record", None)
    if candidate is None or world_record is None:
        raise PredictiveCalibrationError("predictive_calibration_candidate_context_incomplete")
    report = report or load_backtest_report(
        ensure_ir_artifact_store(store),
        _as_ir_artifact_ref(association.backtest_report_ref),
    )
    if association.schema_version in {_ASSOCIATION_SCHEMA, _PRIOR_ASSOCIATION_SCHEMA}:
        target_metric = _required_text(report.metadata.get("target_metric"), "target_metric")
        expected_binding = _n4_outcome_target_binding_record(candidate_source, target_metric)
        if report.metadata.get("n4_outcome_target_binding") != expected_binding:
            raise PredictiveCalibrationError(
                "predictive_calibration_n4_outcome_binding_reopen_mismatch"
            )
    evidence = evidence or load_empirical_calibration_evidence(
        store,
        _as_ir_empirical_calibration_evidence_ref(association.empirical_evidence_ref),
    )
    method_result = {
        "output": {
            "report": report,
            "empirical_calibration_evidence_ref": association.empirical_evidence_ref,
            "expected_rule_version_ref": evidence.rule_version_ref,
            "temporal_roles": {
                name: getattr(evidence, name)
                for name in (
                    "data_valid_time",
                    "calibration_window_start",
                    "calibration_window_end",
                    "policy_effective_time",
                    "prediction_time",
                    "observation_time",
                )
            },
        }
    }

    def resolver(ref: object) -> object:
        return load_empirical_calibration_evidence(
            store,
            _as_ir_empirical_calibration_evidence_ref(ref),
        )

    result = RealValueOwnerGateway(
        empirical_evidence_resolver=resolver,
        artifact_store=store,
    ).produce_forecast_inputs(
        candidate=candidate,
        problem=candidate_source.problem,
        world_record=world_record,
        method_result=method_result,
        selected_method_fqn=_METHOD_FQN,
    )
    record = result.get("forecast_calibration_record")
    support = result.get("forecast_support")
    if record is None or support is None:
        raise PredictiveCalibrationError("predictive_calibration_s10_record_missing")
    return _s10_summary_from_owner(record, support)


def _read_event_payload(
    store: ArtifactStore,
    record: ControlDiagnosticEventRecord,
) -> dict[str, Any]:
    """Read event payload and verify its append-only payload hash."""
    from polisyos.core.artifacts import load_core_json_artifact

    payload = getattr(record, "payload_inline", None)
    payload_ref = getattr(record, "payload_ref", None)
    if isinstance(payload, Mapping):
        payload_bytes = to_canonical_bytes(dict(payload), CoreCanonSpec(forbid_floats=False))
    elif isinstance(payload_ref, str) and payload_ref:
        raw = store.get_bytes(ArtifactID.model_validate(payload_ref))
        payload_bytes = raw
        try:
            payload = load_core_json_artifact(
                store, ArtifactID.model_validate(payload_ref), raw_payload_bytes=raw
            )
        except (UnicodeDecodeError, ValueError) as exc:
            raise PredictiveCalibrationError(
                "predictive_calibration_event_payload_invalid"
            ) from exc
    else:
        raise PredictiveCalibrationError("predictive_calibration_event_payload_missing")
    expected = getattr(record, "payload_sha256", None)
    actual = "sha256:" + hashlib.sha256(payload_bytes).hexdigest()
    if expected != actual or not isinstance(payload, Mapping):
        raise PredictiveCalibrationError("predictive_calibration_event_payload_integrity_failed")
    return dict(payload)


def _selected_run_manifest(run_details: RunDetails) -> ArtifactRef:
    """Return the exact selected Core run manifest ref."""

    ref = getattr(run_details, "manifest_ref", None)
    try:
        selected = ArtifactRef.model_validate(ref)
    except (TypeError, ValueError) as exc:
        raise PredictiveCalibrationError("predictive_calibration_run_manifest_missing") from exc
    if selected.manifest_profile_sha256 is None:
        raise PredictiveCalibrationError("predictive_calibration_run_manifest_profile_missing")
    return selected


def _root_refs(run_details: RunDetails) -> tuple[ArtifactRef, ...]:
    """Normalize the run's selected root-artifact set without dropping profiles."""

    refs: list[ArtifactRef] = []
    raw_refs = getattr(run_details, "root_artifacts", ())
    if not isinstance(raw_refs, Sequence) or isinstance(raw_refs, str | bytes | bytearray):
        raise PredictiveCalibrationError("predictive_calibration_run_roots_unavailable")
    for raw in raw_refs:
        try:
            refs.append(ArtifactRef.model_validate(raw))
        except (TypeError, ValueError):
            continue
    return tuple(refs)


def _root_input_refs(run_details: RunDetails) -> tuple[ArtifactRef, ...]:
    """Normalize selected Core-manifest inputs without dropping full profiles."""

    refs: list[ArtifactRef] = []
    raw_refs = getattr(run_details, "root_input_artifacts", ())
    if not isinstance(raw_refs, Sequence) or isinstance(raw_refs, str | bytes | bytearray):
        raise PredictiveCalibrationError("predictive_calibration_run_inputs_unavailable")
    for raw in raw_refs:
        try:
            refs.append(ArtifactRef.model_validate(raw))
        except (TypeError, ValueError):
            continue
    return tuple(refs)


def _candidate_source_refs(run_details: RunDetails) -> tuple[ArtifactRef, ...]:
    """Read N4 sources only from the run's resolved, typed N5 observations."""

    projection = getattr(run_details, "candidate_simulation", None)
    if (
        projection is None
        or getattr(projection, "run_id", None) != getattr(run_details, "run_id", None)
        or getattr(projection, "artifact_status", None) != "resolved"
    ):
        return ()
    refs: list[ArtifactRef] = []
    observations = getattr(projection, "n5_observations", ())
    if not isinstance(observations, Sequence) or isinstance(observations, str | bytes | bytearray):
        return ()
    for observation in observations:
        if (
            getattr(observation, "status", None) != "joint_simulated"
            or getattr(observation, "lineage_status", None) != "resolved"
        ):
            continue
        raw = getattr(observation, "n4_source_ref", None)
        if raw is None:
            continue
        try:
            selected = ArtifactRef.model_validate(raw)
        except (TypeError, ValueError):
            continue
        if selected.kind == "runtime.quality.n4_candidate_scenario_source":
            refs.append(selected)
    return tuple(refs)


def _require_candidate_source_ref(
    reference: ArtifactRef,
    run_details: RunDetails,
    root_outputs: Sequence[ArtifactRef],
) -> None:
    allowed = (*root_outputs, *_candidate_source_refs(run_details))
    _require_run_root_ref(reference, allowed, "candidate_source")


def _require_run_root_ref(
    reference: ArtifactRef,
    roots: Sequence[ArtifactRef],
    role: str,
) -> None:
    if not any(
        artifact_ref_identity_key(reference) == artifact_ref_identity_key(item) for item in roots
    ):
        raise PredictiveCalibrationError(
            f"predictive_calibration_{role}_not_run_root",
            f"The selected {role.replace('_', ' ')} is not an exact root-artifact view "
            "of this run.",
        )


def _require_selected_ref(
    store: ArtifactStore,
    ref: ArtifactRef,
    *,
    expected_kind: str | None,
) -> None:
    """Require an exact full selected CAS profile and optional owner kind."""

    if ref.manifest_profile_sha256 is None or not store.verify(ref).ok:
        raise PredictiveCalibrationError("predictive_calibration_input_profile_unverified")
    manifest = store.get_manifest(ref)
    if (
        artifact_manifest_profile_sha256(manifest) != ref.manifest_profile_sha256
        or str(manifest.artifact_id) != str(ref.artifact_id)
        or manifest.kind != ref.kind
        or manifest.media_type != ref.media_type
        or (expected_kind is not None and manifest.kind != expected_kind)
    ):
        raise PredictiveCalibrationError("predictive_calibration_input_profile_mismatch")


def _core_input(ref: ArtifactRef, role: str) -> InputRef:
    """Build an exact-profile report input edge."""

    if ref.manifest_profile_sha256 is None:
        raise PredictiveCalibrationError("predictive_calibration_input_profile_missing")
    return InputRef(
        artifact_id=ref.artifact_id,
        role=role,
        manifest_profile_sha256=ref.manifest_profile_sha256,
    )


def _identity(role: str, report_id: str, content: object) -> str:
    """Derive a stable role identity from the actual bound input views."""

    payload = {"role": role, "report_id": report_id, "content": content}
    digest = hashlib.sha256(
        to_canonical_bytes(payload, CoreCanonSpec(forbid_floats=False))
    ).hexdigest()
    return f"sha256:{digest}"


def _require_event_scope(
    scope: Mapping[str, str],
    *,
    run_id: str,
    job_id: str,
    tenant_id: str,
    cell_id: str,
) -> None:
    """Require the event-log owner to share the exact run scope."""

    expected = {
        "run_id": run_id,
        "job_id": job_id,
        "tenant_id": tenant_id,
        "cell_id": cell_id,
    }
    if any(scope.get(key) != value for key, value in expected.items()):
        raise PredictiveCalibrationError("predictive_calibration_event_scope_mismatch")


def _require_event_log_owner(
    event_log: _DiagnosticEventLog,
    *,
    store: ArtifactStore,
    run_id: str,
    job_id: str,
    run_manifest_ref: ArtifactRef,
) -> str:
    """Verify the durable control-job → Core-attempt → manifest join.

    The control job's stable run identifier differs from its per-attempt Core
    run id. The persisted progress pointer, not a string equality assumption,
    binds the selected Core manifest to the completed owner job.
    """

    if getattr(event_log, "artifact_store", None) is not store:
        raise PredictiveCalibrationError("predictive_calibration_event_store_mismatch")
    control_store = getattr(event_log, "_store", None)
    get_job = getattr(control_store, "get_job", None)
    if not callable(get_job):
        raise PredictiveCalibrationError("predictive_calibration_control_store_unavailable")
    job = get_job(job_id)
    progress = getattr(job, "progress", None)
    try:
        selected_manifest_ref = ArtifactRef.model_validate(
            progress.get("core_manifest_artifact_ref") if isinstance(progress, Mapping) else None
        )
    except (TypeError, ValueError) as exc:
        raise PredictiveCalibrationError(
            "predictive_calibration_core_manifest_pointer_invalid"
        ) from exc
    control_run_id = str(getattr(job, "run_id", "") or "")
    if (
        job is None
        or getattr(job, "job_id", None) != job_id
        or str(getattr(job, "state", "")) != "completed"
        or str(getattr(job, "kind", "")) != "natural_language_run"
        or not control_run_id
        or not isinstance(progress, Mapping)
        or progress.get("core_run_id") != run_id
        or progress.get("manifest_ref") != str(run_manifest_ref.artifact_id)
        or artifact_ref_identity_key(selected_manifest_ref)
        != artifact_ref_identity_key(run_manifest_ref)
    ):
        raise PredictiveCalibrationError("predictive_calibration_completed_job_binding_mismatch")
    return control_run_id


def _calibration_status(
    value: object,
) -> Literal[
    "pass",
    "limit",
    "blocked",
    "not_applicable_non_observable",
    "insufficient_history",
]:
    """Normalize the S10 status to the finite public diagnostic lattice."""

    text = str(value or "blocked")
    if text not in {
        "pass",
        "limit",
        "blocked",
        "not_applicable_non_observable",
        "insufficient_history",
    }:
        return "blocked"
    return text  # type: ignore[return-value]


def _required_text(value: object, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise PredictiveCalibrationError(f"predictive_calibration_{field}_missing")
    return text


__all__ = [
    "PredictiveCalibrationAssociation",
    "PredictiveCalibrationError",
    "PredictiveCalibrationRequest",
    "PredictiveCalibrationResponse",
    "load_run_predictive_calibration",
    "produce_run_predictive_calibration",
]
