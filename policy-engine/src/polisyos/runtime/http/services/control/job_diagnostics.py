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
from pydantic import BaseModel, ConfigDict, model_validator

from polisyos.common import logger as common_logger
from polisyos.core.security import AccessScope
from polisyos.runtime.http.execution_policy import (
    ResolvedExecutionPolicy,
    build_capability_manifest_payload,
)
from polisyos.runtime.http.resilience import run_guarded_dependency_operation
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
from polisyos.runtime.quality.event_log import (
    DiagnosticEventPayloadPolicy,
    _PreparedDiagnosticEvent,
)

from .._control_contracts import (
    _coerce_control_job_kind,
    _ControlJobAdmissionDiagnosticBinding,
)
from ..control_plane_store import (
    ControlDiagnosticEventRecord,
    ControlJobExecutionScope,
    ControlJobLeaseLostError,
    ControlJobRecord,
    _ControlJobExecutionLifecycleProof,
)
from .job_attempt_publication import (
    _EXECUTION_INTENT_BINDING_KEY,
    _build_control_execution_intent_binding,
)

logger = common_logger.get_logger("polisyos.runtime.http.services.control.run_lifecycle")

_SERIOUS_EXECUTION_PROFILES = frozenset({"research", "governed", "production"})
_CONTROL_JOB_EXECUTION_BINDING_KEY = "control_job_execution_binding"
_OBSERVATIONAL_METHOD_INTENT_PAYLOAD_KEY = "observational_method_execution"


class _DiagnosticExecutionScopeRecord(BaseModel):
    """Typed source and establishment state for one durable diagnostic."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["polisyos.runtime.control_execution_scope.v1"] = (
        "polisyos.runtime.control_execution_scope.v1"
    )
    status: Literal["established", "not_established"]
    source: Literal["job_admission", "authenticated_request"]
    limitation_code: Literal["control_job_execution_scope_not_established"] | None = None


class _ControlJobExecutionBinding(BaseModel):
    """Bind a diagnostic to its persisted control-job lifecycle source."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["polisyos.runtime.control_job_execution_binding.v1"] = (
        "polisyos.runtime.control_job_execution_binding.v1"
    )
    binding_status: Literal["established"] = "established"
    proof_phase: Literal["job_admission", "running", "completed", "failed"]
    control_job_id: str
    control_run_id: str | None
    source_event_job_state: Literal["pending", "running", "completed", "failed"]
    control_worker_id: str | None
    control_worker_attempt: int | None
    source_event_id: int
    source_event_type: Literal["job_created", "job_running", "job_completed", "job_failed"]
    source_event_created_at: datetime
    source_event_payload_sha256: str
    bound_job_record_refs: tuple[str, ...]

    @model_validator(mode="after")
    def _validate_phase_binding(self) -> _ControlJobExecutionBinding:
        digest = self.source_event_payload_sha256
        if (
            not digest.startswith("sha256:")
            or len(digest) != 71
            or any(character not in "0123456789abcdef" for character in digest[7:])
        ):
            raise ValueError("control_job_execution_binding_payload_digest_invalid")
        if self.proof_phase == "job_admission":
            if (
                self.source_event_type != "job_created"
                or self.control_worker_id is not None
                or self.control_worker_attempt is not None
                or self.source_event_job_state not in {"pending", "failed"}
            ):
                raise ValueError("control_job_execution_binding_admission_invalid")
            return self
        if (
            self.source_event_type != f"job_{self.proof_phase}"
            or self.source_event_job_state != self.proof_phase
            or not isinstance(self.control_worker_id, str)
            or not self.control_worker_id.strip()
            or type(self.control_worker_attempt) is not int
            or self.control_worker_attempt < 1
        ):
            raise ValueError("control_job_execution_binding_worker_attempt_invalid")
        return self


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

        sentinels = {
            "unknown",
            "tenant-unknown",
            "cell-unknown",
            "anonymous",
            "none",
            "null",
        }

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

    def _build_runtime_diagnostic_event(
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
    ) -> tuple[
        DiagnosticEvent,
        _DiagnosticExecutionScopeRecord,
        dict[str, Any],
        Mapping[str, Any],
        bool,
        bool,
    ]:
        """Build one detached diagnostic candidate without storage or source publication."""

        trace = self._job_trace_context(
            job_id=job_id,
            payload=payload,
            parent_span_id=parent_span_id,
        )
        scope_record, tenant_id, cell_id = self._diagnostic_scope_record(execution_scope)
        caller_event_payload = dict(event_payload or {})
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
                **caller_event_payload,
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
        return (
            event,
            scope_record,
            caller_event_payload,
            persisted_event_payload,
            authority_withheld,
            scope_established,
        )

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

        (
            event,
            scope_record,
            caller_event_payload,
            persisted_event_payload,
            authority_withheld,
            scope_established,
        ) = self._build_runtime_diagnostic_event(
            job_id=job_id,
            run_id=run_id,
            execution_profile=execution_profile,
            phase=phase,
            event_type=event_type,
            state_before=state_before,
            state_after=state_after,
            payload=payload,
            event_payload=event_payload,
            artifact_refs=artifact_refs,
            input_refs=input_refs,
            blocking_status=blocking_status,
            authority_bearing_payload=authority_bearing_payload,
            producer_component=producer_component,
            parent_span_id=parent_span_id,
            execution_scope=execution_scope,
        )
        try:
            # The top-level `attempt` name is reserved for this control-worker path.
            # Domain/evaluation attempts remain in their nested step payloads.
            if _CONTROL_JOB_EXECUTION_BINDING_KEY in caller_event_payload:
                raise ControlJobLeaseLostError(
                    "runtime diagnostic caller supplied a reserved worker binding"
                )
            if "attempt" in caller_event_payload and not isinstance(
                execution_scope, ControlJobExecutionScope
            ):
                raise ControlJobLeaseLostError(
                    "runtime diagnostic attempt lacks a control-job worker proof"
                )
            payload_policy = DiagnosticEventPayloadPolicy(
                authority_bearing=authority_bearing_payload and scope_established
            )
            if isinstance(execution_scope, ControlJobExecutionScope):
                selected_job = self._control_store.get_job(job_id)
                if selected_job is None:
                    raise ControlJobLeaseLostError("runtime diagnostic source job is not present")
                if phase == "job_admission":
                    proof_purpose: Literal["execution", "completed_proof", "failed_proof"] = (
                        "execution"
                    )
                elif selected_job.state == "completed":
                    proof_purpose = "completed_proof"
                elif selected_job.state == "failed":
                    proof_purpose = "failed_proof"
                else:
                    proof_purpose = "execution"

                def source_in_transaction() -> _ControlJobExecutionLifecycleProof:
                    if phase == "job_admission":
                        self._control_store._lock_job_state(job_id)
                        current = self._control_store.get_job(job_id)
                        if current is None:
                            raise ControlJobLeaseLostError("runtime diagnostic source job missing")
                        source = self._control_store._get_job_created_source_event_record(job_id)
                        proof = _ControlJobExecutionLifecycleProof(
                            record=current,
                            proof_phase="job_admission",
                            worker_id=None,
                            attempt=None,
                            source_event=source,
                        )
                    elif proof_purpose == "completed_proof":
                        proof = self._control_store._current_execution_completed_job_proof()
                    elif proof_purpose == "failed_proof":
                        proof = self._control_store._current_execution_failed_job_proof()
                    else:
                        proof = self._control_store._current_execution_running_job_proof()
                    scope, admission_manifest = (
                        self._control_store._reconcile_control_job_creation_envelope(proof.record)
                    )
                    if phase == "job_admission" and (
                        proof.record.capability_manifest_ref != admission_manifest
                    ):
                        raise ControlJobLeaseLostError(
                            "runtime admission diagnostic manifest changed"
                        )
                    if (
                        proof.record.job_id != job_id
                        or proof.record.run_id != run_id
                        or scope != execution_scope
                    ):
                        raise ControlJobLeaseLostError("runtime diagnostic source scope changed")
                    return proof

                def read_source() -> _ControlJobExecutionLifecycleProof:
                    with self._control_store._job_transaction(purpose=proof_purpose):
                        return source_in_transaction()

                snapshot = run_guarded_dependency_operation(self._control_store, read_source)
                append_payload = self._control_job_bound_diagnostic_payload(
                    persisted_payload=persisted_event_payload,
                    caller_payload=caller_event_payload,
                    proof=snapshot,
                )
                # Preparation enforces that no caller-owned SQL transaction is
                # active. CAS/registry work occurs before the fresh write proof.
                prepared = self._diagnostic_event_log.prepare(
                    event, payload=append_payload, payload_policy=payload_policy
                )
                prepared_event, prepared_payload = prepared.publication_values()
                if prepared_payload is None:
                    raise ControlJobLeaseLostError("runtime diagnostic prepared payload missing")
                expected_binding = prepared_payload[_CONTROL_JOB_EXECUTION_BINDING_KEY]

                def append_reconciled_event() -> ControlDiagnosticEventRecord:
                    with self._control_store._job_transaction(purpose=proof_purpose):
                        current_proof = source_in_transaction()
                        current_payload = self._control_job_bound_diagnostic_payload(
                            persisted_payload={},
                            caller_payload=caller_event_payload,
                            proof=current_proof,
                        )
                        if current_payload[_CONTROL_JOB_EXECUTION_BINDING_KEY] != expected_binding:
                            raise ControlJobLeaseLostError(
                                "runtime diagnostic source changed after I/O"
                            )
                        return self._control_store.append_diagnostic_event(
                            event=prepared_event,
                            payload_ref=prepared.payload_ref,
                            payload_inline=(prepared_payload if prepared.inline_payload else None),
                            payload_sha256=prepared.payload_sha256,
                        )

                record = run_guarded_dependency_operation(
                    self._control_store, append_reconciled_event
                )
            else:
                record = self._diagnostic_event_log.append(
                    event,
                    payload=persisted_event_payload,
                    payload_policy=payload_policy,
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
    def _control_job_bound_diagnostic_payload(
        *,
        persisted_payload: Mapping[str, Any],
        caller_payload: Mapping[str, Any],
        proof: _ControlJobExecutionLifecycleProof,
    ) -> dict[str, Any]:
        """Attach a strict binding recomputed from one persisted lifecycle proof."""
        if "attempt" in caller_payload and (
            proof.attempt is None
            or type(caller_payload["attempt"]) is not int
            or caller_payload["attempt"] != proof.attempt
        ):
            raise ControlJobLeaseLostError(
                "runtime diagnostic attempt does not match control worker proof"
            )
        source_state = proof.source_event.payload.get("state")
        if source_state not in {"pending", "running", "completed", "failed"}:
            raise ControlJobLeaseLostError(
                "runtime diagnostic source event has no recognized state"
            )
        source = proof.source_event
        binding = _ControlJobExecutionBinding(
            proof_phase=proof.proof_phase,
            control_job_id=proof.record.job_id,
            control_run_id=proof.record.run_id,
            source_event_job_state=source_state,
            control_worker_id=proof.worker_id,
            control_worker_attempt=proof.attempt,
            source_event_id=source.event_id,
            source_event_type=source.event_type,
            source_event_created_at=source.created_at,
            source_event_payload_sha256=source.payload_sha256,
            bound_job_record_refs=tuple(
                ref
                for ref in (
                    proof.record.payload_ref,
                    proof.record.capability_manifest_ref,
                )
                if ref is not None
            ),
        )
        return {
            **dict(persisted_payload),
            _CONTROL_JOB_EXECUTION_BINDING_KEY: binding.model_dump(mode="json"),
        }

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
        sentinel_values = {
            "unknown",
            "tenant-unknown",
            "cell-unknown",
            "anonymous",
            "none",
            "null",
        }

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
        pre_admission_attempt_id: str | None = None,
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
            selected_nl_payload_ref = None
            if job_kind == "natural_language_run" and "temporal_scope" in payload:
                selected_nl_payload_ref = self._put_json_artifact_ref(
                    payload,
                    kind="runtime.control_job_payload.natural_language_run",
                    schema_name="polisyos.runtime.ControlJobPayload",
                    schema_version="1.1",
                )
                payload_ref = str(selected_nl_payload_ref.artifact_id)
            else:
                payload_ref = self._persist_job_payload(job_kind=job_kind, payload=payload)
            capability_manifest_ref = self._persist_capability_manifest(
                policy=policy,
                job_id=job_id,
                run_id=run_id,
                pipeline_id=pipeline_id,
                payload_ref=payload_ref,
            )
            creation_event_payload = {
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
                        "intent_digest": payload[_EXECUTION_INTENT_BINDING_KEY]["intent_digest"],
                    }
                    if job_kind == "natural_language_run"
                    else {}
                ),
                **(
                    {
                        "nl_request_payload_artifact_ref": selected_nl_payload_ref.model_dump(
                            mode="json"
                        )
                    }
                    if selected_nl_payload_ref is not None
                    else {}
                ),
                **(
                    {
                        _OBSERVATIONAL_METHOD_INTENT_PAYLOAD_KEY: dict(
                            payload[_OBSERVATIONAL_METHOD_INTENT_PAYLOAD_KEY]
                        )
                    }
                    if job_kind == "workflow_run"
                    and isinstance(payload.get(_OBSERVATIONAL_METHOD_INTENT_PAYLOAD_KEY), Mapping)
                    else {}
                ),
            }
            creation_basis = self._control_store.prepare_job_creation(
                job_id=job_id,
                initial_state="failed" if initially_refused else "pending",
                creation_event_payload=creation_event_payload,
            )
            candidates = (
                self._build_runtime_diagnostic_event(
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
                self._build_runtime_diagnostic_event(
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
                self._build_runtime_diagnostic_event(
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
            prepared_diagnostics: list[_PreparedDiagnosticEvent] = []
            preparation_failed = False
            for event, _scope_record, caller_payload, event_payload, _, established in candidates:
                if (
                    "attempt" in caller_payload
                    or _CONTROL_JOB_EXECUTION_BINDING_KEY in caller_payload
                ):
                    raise ControlJobLeaseLostError("runtime diagnostic reserved admission binding")
                # These are unpublished candidate bytes. Only create_job may
                # reconcile them with an actual row/event/outbox and emit them.
                binding = _ControlJobAdmissionDiagnosticBinding(
                    control_job_id=job_id,
                    control_run_id=run_id,
                    source_event_job_state="failed" if initially_refused else "pending",
                    source_event_payload_sha256=creation_basis.source_payload_sha256,
                    prepared_at=creation_basis.prepared_at,
                    bound_job_record_refs=tuple(
                        ref for ref in (payload_ref, capability_manifest_ref) if ref is not None
                    ),
                )
                bound_payload = {
                    **dict(event_payload),
                    _CONTROL_JOB_EXECUTION_BINDING_KEY: binding.model_dump(mode="json"),
                }
                try:
                    prepared_diagnostics.append(
                        self._diagnostic_event_log.prepare(
                            event,
                            payload=bound_payload,
                            payload_policy=DiagnosticEventPayloadPolicy(
                                authority_bearing=(
                                    policy.effective_profile in _SERIOUS_EXECUTION_PROFILES
                                    and established
                                )
                            ),
                        )
                    )
                except Exception as exc:
                    if policy.effective_profile in _SERIOUS_EXECUTION_PROFILES:
                        raise RuntimeError(
                            f"runtime_diagnostic_event_persistence_failed:{job_id}:job_admission"
                        ) from exc
                    # Preserve the existing dev best-effort rule. No omitted
                    # event ID is advertised; the limitation is initial progress.
                    preparation_failed = True
                    logger.debug("Admission diagnostic preparation failed for %s: %s", job_id, exc)
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
                creation_event_payload=creation_event_payload,
                initial_state="failed" if initially_refused else "pending",
                initial_error_message=(
                    "nl_job_execution_intent_not_established" if initially_refused else None
                ),
                initial_progress={
                    "state": "failed" if initially_refused else "pending",
                    "phase": "job_admission",
                    **(
                        {
                            "status": "not_established",
                            "failure_code": "nl_job_execution_intent_not_established",
                            "execution_intent_binding": payload[_EXECUTION_INTENT_BINDING_KEY],
                        }
                        if initially_refused
                        else {}
                    ),
                },
                creation_basis=creation_basis,
                prepared_admission_diagnostics=tuple(prepared_diagnostics),
                diagnostic_preparation_failed=preparation_failed,
                pre_admission_attempt_id=pre_admission_attempt_id,
                pre_admission_outcome=(
                    ("refused" if initially_refused else "admitted")
                    if pre_admission_attempt_id is not None
                    else None
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
