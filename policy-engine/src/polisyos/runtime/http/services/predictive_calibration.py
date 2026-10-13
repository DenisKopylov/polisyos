"""Run-bound candidate predictive-calibration production and readback."""

from __future__ import annotations

import hashlib
import json
import logging
import uuid
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Literal, Protocol, cast

from pydantic import BaseModel, ConfigDict, Field

from polisyos.calibration.forecast_bridge import (
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
from polisyos.core.canon import CanonSpec
from polisyos.core.canon.canon_json import to_canonical_bytes
from polisyos.core.contracts.fabric import DataSnapshotRef
from polisyos.core.contracts.runtime import ApiMeta, RunDetails
from polisyos.ir.analytics.backtest import (
    BacktestReport,
    load_backtest_report,
    persist_backtest_report,
)
from polisyos.ir.artifacts import InputRef, normalize_artifact_ref, put_json_artifact
from polisyos.ir.registry.refs import ArtifactRefModel
from polisyos.runtime.http.services.run_operation_idempotency import (
    RuntimeOperationIntentClaim,
    RuntimeOperationIntentKey,
    RuntimeOperationIntentStore,
)
from polisyos.runtime.quality.diagnostic_events import DiagnosticEvent
from polisyos.runtime.quality.event_log import DiagnosticEventPayloadPolicy
from polisyos.scientist.methods.backtesting.forecast_owner import (
    CALIBRATION_RULE_ID,
    CalibrationRuleBinding,
    ForecastMethodParams,
    ForecastOwner,
    ForecastOwnerRequest,
    ForecastTemporalRoles,
    TrainHoldoutSplit,
)

if TYPE_CHECKING:
    from polisyos.core.artifacts.manifest import ArtifactManifest
    from polisyos.core.artifacts.protocol import ArtifactStore
    from polisyos.runtime.http.services.control_plane_store import ControlDiagnosticEventRecord
    from polisyos.runtime.http.services.run_index import IndexedRunRecord

_ASSOCIATION_KIND = "runtime.predictive_calibration_association"
_ASSOCIATION_SCHEMA = "polisyos.runtime.predictive_calibration_association.v2"
_ASSOCIATION_VERSION = "2.0"
_ASSOCIATION_EVENT = "polisyos.runtime.diagnostic.ref_publication.v1"
_ASSOCIATION_EVENT_SCHEMA = "polisyos.runtime.quality.diagnostic_event"
_ASSOCIATION_EVENT_SCHEMA_VERSION = "1.0"
_METHOD_FQN = "forecasting.univariate.exponential_smoothing@1.0.0"
_METHOD_REF, _METHOD_VERSION = _METHOD_FQN.rsplit("@", maxsplit=1)
_logger = logging.getLogger(__name__)


def _as_ir_artifact_ref(ref: ArtifactRef) -> ArtifactRefModel:
    """Adapt a selected Core reference without dropping its manifest profile."""
    return ArtifactRefModel.model_validate(normalize_artifact_ref(ref))


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


class PredictiveCalibrationRequest(BaseModel):
    """Explicit, profile-selected inputs for one run-bound predictive diagnostic."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    intent_id: str = Field(min_length=1, max_length=120, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")
    candidate_source_ref: ArtifactRef
    observed_source_ref: DataSnapshotRef
    model_spec_ref: ArtifactRef
    policy_spec_ref: ArtifactRef
    calibration_rule_ref: ArtifactRef
    calibration_threshold: float = Field(gt=0.0, le=1.0)
    split: TrainHoldoutSplit
    target_metric: str = Field(min_length=1, max_length=200)
    method_params: ForecastMethodParams
    temporal_roles: ForecastTemporalRoles
    seed: int = Field(ge=0)


class PredictiveCalibrationS10Summary(BaseModel):
    """Small persisted summary of the recomputed S10 candidate projection."""

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


class PredictiveCalibrationAssociation(BaseModel):
    """Versioned, append-only run attachment for a limited predictive result."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["polisyos.runtime.predictive_calibration_association.v2"] = (
        "polisyos.runtime.predictive_calibration_association.v2"
    )
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
    may_not_use_for: tuple[
        Literal["promotion", "publication", "policy_selection", "causal_effect_claim"], ...
    ] = ("promotion", "publication", "policy_selection", "causal_effect_claim")
    created_at: datetime


class PredictiveCalibrationResponse(BaseModel):
    """API wrapper for a durable, freshly resolved predictive association."""

    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    association_ref: ArtifactRef
    association: PredictiveCalibrationAssociation


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

        report_id = (
            f"{run_id}:predictive-calibration:"
            f"{event_id.removeprefix('evt_predictive_calibration_')}"
        )
        run_inputs = (
            _core_input(run_manifest_ref, "run_manifest"),
            _core_input(request.candidate_source_ref, "candidate_source"),
            _core_input(request.observed_source_ref, "observed_source"),
        )
        owner_request = ForecastOwnerRequest(
            observed_source_ref=DataSnapshotRef.model_validate(
                request.observed_source_ref.model_dump()
            ),
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
            report_id=report_id,
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
                EmpiricalCalibrationEvidenceRef.model_validate(ref),
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
        s10_summary = PredictiveCalibrationS10Summary(
            calibration_status=_calibration_status(getattr(s10_record, "calibration_status", None)),
            forecast_tier=_required_text(
                getattr(s10_support, "forecast_tier", None), "forecast_tier"
            ),
            counterfactual_credibility="not_established",
            numerator=int(getattr(s10_record, "numerator", 0)),
            denominator=int(getattr(s10_record, "denominator", 0)),
            observed_pass_rate=float(getattr(s10_record, "pass_rate", 0.0) or 0.0),
            calibration_record_ref=getattr(s10_record, "calibration_ref", None),
        )
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
            observed_numerator=evidence.recomputed_numerator,
            observed_denominator=evidence.recomputed_denominator,
            observed_hit_rate=evidence.recomputed_pass_rate or 0.0,
            nominal_confidence_level=nominal,
            owner_suitability=owner_result.empirical_suitability,
            s10=s10_summary,
            evidence_reason_codes=evidence.reason_codes,
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
            if getattr(getattr(item, "event", None), "event_type", None) == _ASSOCIATION_EVENT
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
    if payload.get("schema_version") != _ASSOCIATION_VERSION:
        raise PredictiveCalibrationError("predictive_calibration_event_payload_schema_mismatch")
    raw_association_ref = payload.get("association_ref")
    try:
        association_ref = ArtifactRef.model_validate(raw_association_ref)
    except (TypeError, ValueError) as exc:
        raise PredictiveCalibrationError("predictive_calibration_association_ref_invalid") from exc
    if str(association_ref.artifact_id) not in event.artifact_refs:
        raise PredictiveCalibrationError("predictive_calibration_event_ref_mismatch")
    association = _load_association(store, association_ref)
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


def _request_sha256(request: PredictiveCalibrationRequest) -> str:
    """Hash the exact declared request, including every selected ref profile."""

    return hashlib.sha256(
        to_canonical_bytes(request.model_dump(mode="json"), CanonSpec(forbid_floats=False))
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
        to_canonical_bytes(bound_request, CanonSpec(forbid_floats=False))
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


def _operation_intent_store(event_log: _DiagnosticEventLog) -> RuntimeOperationIntentStore:
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
    if payload.get("schema_version") != _ASSOCIATION_VERSION:
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
            canon_spec=CanonSpec(forbid_floats=False),
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
    report_id: str,
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
        evidence_origin=f"run-bound candidate report {report_id}",
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
        canon_spec=CanonSpec(forbid_floats=False),
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
    if (
        manifest.kind != _ASSOCIATION_KIND
        or manifest.media_type != "application/json"
        or manifest.artifact_schema is None
        or manifest.artifact_schema.name != _ASSOCIATION_SCHEMA
        or manifest.artifact_schema.version != _ASSOCIATION_VERSION
        or artifact_manifest_profile_sha256(manifest) != ref.manifest_profile_sha256
    ):
        raise PredictiveCalibrationError("predictive_calibration_association_manifest_mismatch")
    if not store.verify(ref).ok:
        raise PredictiveCalibrationError("predictive_calibration_association_integrity_failed")
    from polisyos.ir.artifacts.io import _get_json_artifact_with_bytes
    from polisyos.ir.model_layer.canon import CanonViolation

    try:
        payload, _raw_payload = _get_json_artifact_with_bytes(
            ensure_ir_artifact_store(store),
            ref,
        )
    except CanonViolation as exc:
        raise PredictiveCalibrationError(
            "predictive_calibration_association_profile_unverified"
        ) from exc
    association = PredictiveCalibrationAssociation.model_validate(payload)
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
        )
    }
    actual = {
        (str(item.artifact_id), item.role, item.manifest_profile_sha256) for item in manifest.inputs
    }
    if not expected.issubset(actual):
        raise PredictiveCalibrationError("predictive_calibration_association_edges_mismatch")


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
    evidence = load_empirical_calibration_evidence(
        store,
        EmpiricalCalibrationEvidenceRef.model_validate(association.empirical_evidence_ref),
    )
    if (
        report.report_id != evidence.report_id
        or artifact_ref_identity_key(ArtifactRef.model_validate(evidence.report_ref))
        != artifact_ref_identity_key(association.backtest_report_ref)
        or evidence.recomputed_numerator != association.observed_numerator
        or evidence.recomputed_denominator != association.observed_denominator
        or evidence.recomputed_pass_rate != association.observed_hit_rate
        or evidence.reason_codes != association.evidence_reason_codes
    ):
        raise PredictiveCalibrationError("predictive_calibration_evidence_reopen_mismatch")
    _recompute_s10(store, association, report=report, evidence=evidence)


def _recompute_s10(
    store: ArtifactStore,
    association: PredictiveCalibrationAssociation,
    *,
    report: BacktestReport | None = None,
    evidence: object | None = None,
) -> None:
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
    evidence = evidence or load_empirical_calibration_evidence(
        store,
        EmpiricalCalibrationEvidenceRef.model_validate(association.empirical_evidence_ref),
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
            EmpiricalCalibrationEvidenceRef.model_validate(ref),
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
    if (
        str(getattr(record, "calibration_status", "")) != association.s10.calibration_status
        or str(getattr(support, "forecast_tier", "")) != association.s10.forecast_tier
        or str(getattr(record, "counterfactual_credibility", ""))
        != association.s10.counterfactual_credibility
        or int(getattr(record, "numerator", -1)) != association.s10.numerator
        or int(getattr(record, "denominator", -1)) != association.s10.denominator
        or float(getattr(record, "pass_rate", -1.0)) != association.s10.observed_pass_rate
    ):
        raise PredictiveCalibrationError("predictive_calibration_s10_reopen_mismatch")


def _read_event_payload(
    store: ArtifactStore,
    record: ControlDiagnosticEventRecord,
) -> dict[str, Any]:
    """Read event payload and verify its append-only payload hash."""
    from polisyos.core.artifacts import load_core_json_artifact

    payload = getattr(record, "payload_inline", None)
    payload_ref = getattr(record, "payload_ref", None)
    if isinstance(payload, Mapping):
        payload_bytes = to_canonical_bytes(dict(payload), CanonSpec(forbid_floats=False))
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
    digest = hashlib.sha256(to_canonical_bytes(payload, CanonSpec(forbid_floats=False))).hexdigest()
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
