"""ControlJobDiagnosticsMixin implementation for durable control-job lifecycle facets."""

from __future__ import annotations

import time
import uuid
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Any, Literal, cast

from opentelemetry.context import attach, detach
from pydantic import BaseModel, ConfigDict

from polisyos.common.logger import get_logger
from polisyos.core.security import AccessScope
from polisyos.runtime.http.execution_policy import (
    ResolvedExecutionPolicy,
    build_capability_manifest_payload,
)
from polisyos.runtime.http.services.control.admission import (
    _record_control_plane_job_admission_metric,
    _record_control_plane_job_execution_metric,
)
from polisyos.runtime.quality.diagnostic_events import (
    DIAGNOSTIC_EVENT_SCHEMA_NAME,
    DIAGNOSTIC_EVENT_SCHEMA_VERSION,
    SERIOUS_EXECUTION_PROFILES,
    DiagnosticEvent,
)
from polisyos.runtime.quality.evaluation_modes import ExecutionIntentBand
from polisyos.runtime.quality.event_log import DiagnosticEventPayloadPolicy

from .._control_contracts import _coerce_control_job_kind
from ..control_plane_store import ControlJobExecutionScope, ControlJobRecord
from .job_attempt_publication import (
    _EXECUTION_INTENT_BINDING_KEY,
    _build_control_execution_intent_binding,
)

logger = get_logger("polisyos.runtime.http.services.control.run_lifecycle")

_SERIOUS_EXECUTION_PROFILES = frozenset({"research", "governed", "production"})


class _DiagnosticExecutionScopeRecord(BaseModel):
    """Typed source and establishment state for one durable diagnostic."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["polisyos.runtime.control_execution_scope.v1"] = (
        "polisyos.runtime.control_execution_scope.v1"
    )
    status: Literal["established", "not_established"]
    source: Literal["job_admission", "authenticated_request"]
    limitation_code: Literal["control_job_execution_scope_not_established"] | None = None


@dataclass(frozen=True, slots=True)
class _DiagnosticEventEmission:
    """Report whether a diagnostic persisted and what its scope allows."""

    event_id: str | None
    status: Literal[
        "persisted",
        "candidate_diagnostic",
        "authority_withheld",
        "not_persisted",
    ]
    scope_status: Literal["established", "not_established"]
    limitation_code: str | None = None


class ControlJobDiagnosticsMixin:
    """Own one control-job lifecycle facet without changing service entrypoints."""

    @staticmethod
    def _diagnostic_scope_record(
        scope: ControlJobExecutionScope | AccessScope,
    ) -> tuple[_DiagnosticExecutionScopeRecord, str, str]:
        """Resolve diagnostic attribution only from admitted or request scope."""
        if isinstance(scope, ControlJobExecutionScope):
            source = "job_admission"
            tenant_id = scope.tenant_id
            cell_id = scope.cell_id
            subject = scope.actor_subject
            established = scope.status == "established"
        elif isinstance(scope, AccessScope):
            source = "authenticated_request"
            tenant_id = scope.tenant_id
            cell_id = scope.cell_id
            subject = scope.user_sub or scope.spiffe_id
            established = True
        else:
            raise TypeError("runtime_diagnostic_execution_scope_type_invalid")

        sentinels = {"unknown", "tenant-unknown", "cell-unknown", "anonymous", "none", "null"}

        def usable(value: object) -> bool:
            return (
                isinstance(value, str)
                and bool(value.strip())
                and value.strip().casefold() not in sentinels
            )

        established = established and usable(tenant_id) and usable(cell_id) and usable(subject)
        if established:
            record = _DiagnosticExecutionScopeRecord(status="established", source=source)
            return record, str(tenant_id).strip(), str(cell_id).strip()

        record = _DiagnosticExecutionScopeRecord(
            status="not_established",
            source=source,
            limitation_code="control_job_execution_scope_not_established",
        )
        return record, "tenant-unknown", "cell-unknown"

    def _emit_runtime_diagnostic_event(
        self,
        *,
        job_id: str,
        run_id: str | None,
        execution_profile: str,
        phase: str,
        event_type: str,
        state_before: str | None = None,
        state_after: str | None = None,
        payload: Mapping[str, Any] | None = None,
        event_payload: Mapping[str, Any] | None = None,
        artifact_refs: list[str] | tuple[str, ...] | None = None,
        input_refs: list[str] | tuple[str, ...] | None = None,
        blocking_status: str | None = None,
        authority_bearing_payload: bool = False,
        producer_component: str = "polisyos.runtime.control",
        parent_span_id: str | None = None,
        execution_scope: ControlJobExecutionScope | AccessScope,
    ) -> _DiagnosticEventEmission:
        """Persist a diagnostic with typed owner attribution or a scoped limitation."""

        trace = self._job_trace_context(
            job_id=job_id,
            payload=payload,
            parent_span_id=parent_span_id,
        )
        scope_record, tenant_id, cell_id = self._diagnostic_scope_record(execution_scope)
        scope_payload = scope_record.model_dump(mode="json")
        scope_established = scope_record.status == "established"
        authority_withheld = authority_bearing_payload and not scope_established
        persisted_event_type = (
            "polisyos.runtime.diagnostic.scope_limited.v1" if authority_withheld else event_type
        )
        if authority_withheld:
            persisted_event_payload: Mapping[str, Any] = {
                "execution_scope": scope_payload,
                "withheld_event_type": event_type,
                "authority_status": "withheld",
                "limitation_code": "control_job_execution_scope_not_established",
            }
            persisted_state_after = "not_established"
            persisted_artifact_refs: tuple[str, ...] = ()
            persisted_input_refs: tuple[str, ...] = ()
        else:
            persisted_event_payload = {
                **dict(event_payload or {}),
                "execution_scope": scope_payload,
            }
            persisted_state_after = state_after
            persisted_artifact_refs = tuple(artifact_refs or ())
            persisted_input_refs = tuple(input_refs or ())
        event = DiagnosticEvent(
            event_id=f"evt_{uuid.uuid4().hex[:24]}",
            event_source="polisyos.runtime.control",
            event_type=persisted_event_type,
            event_time=datetime.now(UTC).replace(microsecond=0),
            event_subject=f"run/{run_id or 'run-unknown'}/job/{job_id}/phase/{phase}",
            schema_name=DIAGNOSTIC_EVENT_SCHEMA_NAME,
            schema_version=DIAGNOSTIC_EVENT_SCHEMA_VERSION,
            trace_id=str(trace["trace_id"]),
            span_id=str(trace["span_id"]),
            parent_span_id=(str(trace["parent_span_id"]) if trace.get("parent_span_id") else None),
            run_id=str(run_id or "run-unknown"),
            job_id=job_id,
            tenant_id=tenant_id,
            cell_id=cell_id,
            producer_component=producer_component,
            producer_version="2026.05.15+hds-phase2.2",
            execution_profile=execution_profile,
            phase=phase,
            state_before=state_before,
            state_after=persisted_state_after,
            payload_ref=None,
            artifact_refs=persisted_artifact_refs,
            input_refs=persisted_input_refs,
            blocking_status=("blocking" if authority_withheld else blocking_status),
            redaction_policy_ref="redaction-policy/runtime-diagnostics-v1",
            duplicate_of=None,
            dedupe_key=None,
            sampling_decision="always_record",
            sampling_rate=1.0,
        )
        try:
            record = self._diagnostic_event_log.append(
                event,
                payload=persisted_event_payload,
                payload_policy=DiagnosticEventPayloadPolicy(
                    authority_bearing=authority_bearing_payload and scope_established
                ),
            )
        except Exception as exc:  # pragma: no cover - diagnostics cannot mask dev jobs
            if execution_profile.strip().casefold() in SERIOUS_EXECUTION_PROFILES:
                raise RuntimeError(
                    f"runtime_diagnostic_event_persistence_failed:{job_id}:{phase}"
                ) from exc
            logger.debug(
                "Failed to persist runtime diagnostic event for job %s phase %s: %s",
                job_id,
                phase,
                exc,
            )
            return _DiagnosticEventEmission(
                event_id=None,
                status="not_persisted",
                scope_status=scope_record.status,
                limitation_code=(
                    scope_record.limitation_code or "runtime_diagnostic_event_persistence_failed"
                ),
            )
        if authority_withheld:
            status: Literal[
                "persisted",
                "candidate_diagnostic",
                "authority_withheld",
                "not_persisted",
            ] = "authority_withheld"
        elif not scope_established:
            status = "candidate_diagnostic"
        else:
            status = "persisted"
        return _DiagnosticEventEmission(
            event_id=str(record.event.event_id),
            status=status,
            scope_status=scope_record.status,
            limitation_code=scope_record.limitation_code,
        )

    @staticmethod
    def _execution_scope_for_policy(
        policy: ResolvedExecutionPolicy,
    ) -> ControlJobExecutionScope:
        """Freeze complete authenticated identity from route policy at job admission."""
        actor = policy.actor
        if not isinstance(actor, Mapping):
            return ControlJobExecutionScope(
                status="not_established",
                tenant_id=None,
                cell_id=None,
                actor_subject=None,
                actor_authenticated=False,
                actor_roles=(),
            )
        subject = actor.get("subject")
        tenant_id = actor.get("tenant_id")
        cell_id = actor.get("cell_id")
        authenticated = actor.get("authenticated") is True
        roles_raw = actor.get("roles")
        sentinel_values = {"unknown", "tenant-unknown", "cell-unknown", "anonymous", "none", "null"}

        def established_text(value: object) -> bool:
            return (
                type(value) is str
                and bool(value)
                and value == value.strip()
                and value.casefold() not in sentinel_values
            )

        canonical_roles = (
            type(roles_raw) is list
            and all(type(role) is str and bool(role) and role == role.strip() for role in roles_raw)
            and roles_raw == sorted(set(roles_raw))
        )

        if (
            authenticated
            and established_text(subject)
            and established_text(tenant_id)
            and established_text(cell_id)
            and canonical_roles
        ):
            return ControlJobExecutionScope(
                status="established",
                tenant_id=tenant_id,
                cell_id=cell_id,
                actor_subject=subject,
                actor_authenticated=True,
                actor_roles=tuple(roles_raw),
            )
        return ControlJobExecutionScope(
            status="not_established",
            tenant_id=None,
            cell_id=None,
            actor_subject=None,
            actor_authenticated=False,
            actor_roles=(),
        )

    @staticmethod
    def _policy_with_execution_scope(
        policy: ResolvedExecutionPolicy,
        scope: ControlJobExecutionScope,
    ) -> ResolvedExecutionPolicy:
        """Bind submitted principal and persisted execution scope to one identity."""
        actor = dict(policy.actor)
        if scope.status == "established":
            actor.update(
                subject=scope.actor_subject,
                authenticated=True,
                tenant_id=scope.tenant_id,
                cell_id=scope.cell_id,
                roles=list(scope.actor_roles),
            )
        else:
            actor.update(
                subject="anonymous",
                authenticated=False,
                tenant_id=None,
                cell_id=None,
                roles=[],
            )
        return replace(policy, actor=actor)

    def _attach_job_actor_scope(
        self,
        payload: dict[str, Any],
        *,
        policy: ResolvedExecutionPolicy,
    ) -> dict[str, Any]:
        scoped_payload = dict(payload)
        scoped_payload.pop("tenant_id", None)
        scoped_payload.pop("cell_id", None)
        execution_scope = self._execution_scope_for_policy(policy)
        if execution_scope.status == "established":
            scoped_payload["tenant_id"] = execution_scope.tenant_id
            scoped_payload["cell_id"] = execution_scope.cell_id
        return scoped_payload

    @contextmanager
    def _control_job_span(
        self,
        *,
        job: ControlJobRecord,
        payload: dict[str, Any],
    ) -> Iterator[None]:
        telemetry = payload.get("_telemetry") if isinstance(payload, dict) else None
        request_id = None
        token = None
        if isinstance(telemetry, dict):
            request_id = telemetry.get("request_id")
            carrier = telemetry.get("trace_context")
            extract_context = getattr(self._tracer, "extract_context", None)
            if isinstance(carrier, dict) and carrier and callable(extract_context):
                token = attach(
                    cast(
                        "Any",
                        extract_context({str(key): str(value) for key, value in carrier.items()}),
                    )
                )
        queue_lag_seconds = max(
            (datetime.now(UTC) - job.created_at).total_seconds(),
            0.0,
        )
        started = time.perf_counter()
        status = "success"
        with self._tracer.start_as_current_span(
            "runtime.control.job.execute",
            attributes={
                "runtime.control.job_id": job.job_id,
                "runtime.control.job_kind": job.kind,
                "runtime.control.run_id": job.run_id or "",
                "runtime.control.pipeline_id": job.pipeline_id or "",
                "runtime.control.request_id": str(request_id or ""),
            },
        ):
            try:
                yield
            except Exception:
                status = "error"
                raise
            finally:
                _record_control_plane_job_execution_metric(
                    metrics=self._metrics,
                    job_kind=job.kind,
                    status=status,
                    duration_seconds=time.perf_counter() - started,
                    queue_lag_seconds=queue_lag_seconds,
                )
                if token is not None:
                    detach(token)

    def _persist_capability_manifest(
        self,
        *,
        policy: ResolvedExecutionPolicy,
        job_id: str,
        run_id: str | None,
        pipeline_id: str | None,
        payload_ref: str | None,
        observed_fallbacks: list[str] | None = None,
    ) -> str:
        payload = build_capability_manifest_payload(
            policy=policy,
            job_id=job_id,
            run_id=run_id,
            pipeline_id=pipeline_id,
            payload_ref=payload_ref,
            observed_fallbacks=observed_fallbacks,
        )
        return self._put_json_artifact(
            payload,
            kind="runtime.capability_manifest",
            schema_name="polisyos.runtime.CapabilityManifest",
        )

    def _enqueue_job(
        self,
        *,
        job_id: str,
        job_kind: str,
        run_id: str | None,
        pipeline_id: str | None,
        payload: dict[str, Any],
        policy: ResolvedExecutionPolicy,
        request_id: str | None = None,
    ) -> ControlJobRecord:
        started = time.perf_counter()
        execution_scope = self._execution_scope_for_policy(policy)
        policy = self._policy_with_execution_scope(policy, execution_scope)
        submitted_by = execution_scope.actor_subject or "anonymous"
        payload = self._attach_job_actor_scope(payload, policy=policy)
        payload = self._enrich_job_payload(payload, request_id=request_id)
        initially_refused = False
        if job_kind == "natural_language_run":
            payload[_EXECUTION_INTENT_BINDING_KEY] = _build_control_execution_intent_binding(
                payload,
                job_id=job_id,
                run_id=str(run_id or ""),
                actor=policy.actor,
            )
            initially_refused = (
                payload[_EXECUTION_INTENT_BINDING_KEY]["admission_status"] != "established"
            )
        try:
            payload_ref = self._persist_job_payload(job_kind=job_kind, payload=payload)
            capability_manifest_ref = self._persist_capability_manifest(
                policy=policy,
                job_id=job_id,
                run_id=run_id,
                pipeline_id=pipeline_id,
                payload_ref=payload_ref,
            )
            record = self._control_store.create_job(
                job_id=job_id,
                kind=_coerce_control_job_kind(job_kind),
                run_id=run_id,
                pipeline_id=pipeline_id,
                requested_execution_profile=policy.requested_profile,
                effective_execution_profile=policy.effective_profile,
                policy_flags=policy.policy_flags.model_dump(mode="json"),
                capability_manifest_ref=capability_manifest_ref,
                payload_ref=payload_ref,
                submitted_by=submitted_by,
                creation_event_payload={
                    **self._job_created_event_payload(
                        job_id=job_id,
                        job_kind=job_kind,
                        run_id=run_id,
                        pipeline_id=pipeline_id,
                        payload_ref=payload_ref,
                        submitted_by=submitted_by,
                        requested_execution_profile=policy.requested_profile,
                        effective_execution_profile=policy.effective_profile,
                        policy_flags=policy.policy_flags.model_dump(mode="json"),
                        capability_manifest_ref=capability_manifest_ref,
                        execution_scope=execution_scope,
                    ),
                    **(
                        {
                            _EXECUTION_INTENT_BINDING_KEY: payload[_EXECUTION_INTENT_BINDING_KEY],
                            "intent_digest": payload[_EXECUTION_INTENT_BINDING_KEY][
                                "intent_digest"
                            ],
                        }
                        if job_kind == "natural_language_run"
                        else {}
                    ),
                },
                initial_state="failed" if initially_refused else "pending",
                initial_error_message=(
                    "nl_job_execution_intent_not_established" if initially_refused else None
                ),
                initial_progress=(
                    {
                        "state": "failed",
                        "phase": "job_admission",
                        "status": "not_established",
                        "failure_code": "nl_job_execution_intent_not_established",
                        "execution_intent_binding": payload[_EXECUTION_INTENT_BINDING_KEY],
                    }
                    if initially_refused
                    else None
                ),
            )
            diagnostic_emissions = (
                self._emit_runtime_diagnostic_event(
                    job_id=job_id,
                    run_id=run_id,
                    execution_profile=policy.effective_profile,
                    phase="job_admission",
                    event_type="polisyos.runtime.diagnostic.cas_write.v1",
                    state_after="payload_persisted",
                    payload=payload,
                    execution_scope=execution_scope,
                    event_payload={
                        "artifact_ref": payload_ref,
                        "artifact_kind": f"runtime.control_job_payload.{job_kind}",
                        "projection_authority": "runtime_event_only",
                    },
                    artifact_refs=[payload_ref],
                    authority_bearing_payload=(
                        policy.effective_profile in _SERIOUS_EXECUTION_PROFILES
                    ),
                ),
                self._emit_runtime_diagnostic_event(
                    job_id=job_id,
                    run_id=run_id,
                    execution_profile=policy.effective_profile,
                    phase="job_admission",
                    event_type="polisyos.runtime.diagnostic.cas_write.v1",
                    state_after="capability_manifest_persisted",
                    payload=payload,
                    execution_scope=execution_scope,
                    event_payload={
                        "artifact_ref": capability_manifest_ref,
                        "artifact_kind": "runtime.capability_manifest",
                        "projection_authority": "runtime_event_only",
                    },
                    artifact_refs=[capability_manifest_ref],
                    input_refs=[payload_ref],
                    authority_bearing_payload=(
                        policy.effective_profile in _SERIOUS_EXECUTION_PROFILES
                    ),
                ),
                self._emit_runtime_diagnostic_event(
                    job_id=job_id,
                    run_id=run_id,
                    execution_profile=policy.effective_profile,
                    phase="job_admission",
                    event_type="polisyos.runtime.diagnostic.phase_transition.v1",
                    state_after="failed" if initially_refused else "pending",
                    payload=payload,
                    execution_scope=execution_scope,
                    event_payload={
                        "job_kind": job_kind,
                        "pipeline_id": pipeline_id,
                        "failure_code": (
                            "nl_job_execution_intent_not_established" if initially_refused else None
                        ),
                        "projection_authority": "progress_reference_only",
                    },
                ),
            )
            diagnostic_event_ids = [
                emission.event_id
                for emission in diagnostic_emissions
                if emission.event_id is not None
            ]
            if diagnostic_event_ids:
                diagnostic_progress = {
                    "diagnostic_event_ids": diagnostic_event_ids,
                    "diagnostic_event_authority": (
                        "scope_limited"
                        if any(
                            emission.status == "authority_withheld"
                            for emission in diagnostic_emissions
                        )
                        else "progress_reference_only"
                    ),
                    "diagnostic_event_scope_status": execution_scope.status,
                }
                if execution_scope.status == "not_established":
                    diagnostic_progress["diagnostic_event_limitation_code"] = (
                        "control_job_execution_scope_not_established"
                    )
                progress_state = "failed" if initially_refused else "pending"
                progress = (
                    {
                        **record.progress,
                        "state": "failed",
                        **diagnostic_progress,
                    }
                    if initially_refused
                    else {
                        "state": "pending",
                        "phase": "job_admission",
                        **diagnostic_progress,
                    }
                )
                self._control_store.update_progress_state(
                    job_id=job_id,
                    state=progress_state,
                    progress=progress,
                    error_message=(
                        "nl_job_execution_intent_not_established" if initially_refused else None
                    ),
                )
            if self._worker is not None:
                self._worker.wake()
        except Exception:
            _record_control_plane_job_admission_metric(
                metrics=self._metrics,
                job_kind=job_kind,
                effective_profile=policy.effective_profile,
                status="error",
                duration_seconds=time.perf_counter() - started,
            )
            raise
        _record_control_plane_job_admission_metric(
            metrics=self._metrics,
            job_kind=job_kind,
            effective_profile=policy.effective_profile,
            status="success",
            duration_seconds=time.perf_counter() - started,
        )
        return record

    def _emit_control_job_start_event(
        self,
        *,
        job: ControlJobRecord,
        payload: Mapping[str, Any],
        execution_scope: ControlJobExecutionScope,
        execution_intent_binding: Mapping[str, Any] | None,
    ) -> None:
        """Emit the accepted job-start diagnostic with its admitted intent view."""
        self._emit_runtime_diagnostic_event(
            execution_scope=execution_scope,
            job_id=job.job_id,
            run_id=job.run_id,
            execution_profile=job.effective_execution_profile,
            phase="job_execution",
            event_type="polisyos.runtime.diagnostic.producer_execution.v1",
            state_before=job.state,
            state_after="running",
            payload=payload,
            event_payload={
                "job_kind": job.kind,
                "attempt": job.attempt,
                "projection_authority": "runtime_event_only",
                **(
                    {
                        "execution_intent_band": execution_intent_binding["intent_band"],
                        "execution_intent_limitation_code": (
                            "data_trust_owner_not_established"
                            if execution_intent_binding["intent_band"]
                            == ExecutionIntentBand.DATA_TRUST_REQUIRED.value
                            else None
                        ),
                    }
                    if execution_intent_binding is not None
                    else {}
                ),
            },
        )

    def _complete_acquisition_control_job(
        self,
        *,
        job: ControlJobRecord,
        payload: dict[str, Any],
        execution_scope: ControlJobExecutionScope,
        capability_manifest_ref: str,
    ) -> None:
        """Run the configured acquisition handler and publish its terminal event."""
        handler = self._acquisition_job_handler
        if handler is None:
            raise RuntimeError("acquisition_job_handler_missing")
        progress = handler(job, payload, execution_scope)
        self._control_store.complete_job(
            job_id=job.job_id,
            run_id=str(job.run_id or ""),
            capability_manifest_ref=capability_manifest_ref,
            progress=progress,
        )
        artifact_refs = [capability_manifest_ref]
        terminal_receipt_ref = progress.get("terminal_receipt_ref")
        if isinstance(terminal_receipt_ref, str):
            artifact_refs.append(terminal_receipt_ref)
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
                "receipt_phase": progress.get("receipt_phase"),
            },
            artifact_refs=artifact_refs,
        )
        return
