"""Durable runtime diagnostic event log backed by CAS and the control store."""

from __future__ import annotations

import json
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol

from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
from polisyos.core.canon import CanonSpec
from polisyos.core.canon.canon_json import to_canonical_bytes
from polisyos.runtime.quality.diagnostic_events import (
    DIAGNOSTIC_EVENT_SCHEMA_NAME,
    DIAGNOSTIC_EVENT_SCHEMA_VERSION,
    SERIOUS_EXECUTION_PROFILES,
    DiagnosticEvent,
    validate_diagnostic_event,
)

INLINE_PAYLOAD_MAX_BYTES = 2048
CORRECTIVE_EVENT_ACTIONS = frozenset({"supersede", "withdraw", "reconcile", "quarantine"})
_SENSITIVE_KEY_MARKERS = (
    "access_token",
    "api_key",
    "bearer",
    "credential",
    "hidden_answer",
    "password",
    "refresh_token",
    "secret",
    "token",
)


@dataclass(frozen=True)
class DiagnosticEventPayloadPolicy:
    """Decide whether an event payload may be inline or must be CAS-backed."""

    authority_bearing: bool = False
    redacted: bool = False
    sensitive: bool = False
    inline_max_bytes: int = INLINE_PAYLOAD_MAX_BYTES


class _DiagnosticPayloadRecord(Protocol):
    @property
    def payload_ref(self) -> str | None: ...

    @property
    def payload_inline(self) -> dict[str, Any] | None: ...

    @property
    def payload_sha256(self) -> str | None: ...


_DIAGNOSTIC_PREPARATION_SEAL = object()


@dataclass(frozen=True, slots=True)
class _PreparedDiagnosticEvent:
    """Freeze diagnostic bytes prepared outside a control-store transaction.

    This ephemeral candidate is not an event receipt or an authorization proof.
    The publication owner must reconcile its source before appending any row.
    """

    event_json: str
    payload_json: str | None
    payload_ref: str | None
    payload_sha256: str | None
    inline_payload: bool
    preparation_seal: object

    def publication_values(self) -> tuple[DiagnosticEvent, dict[str, Any] | None]:
        """Decode detached values and recheck the exact prepared payload bytes."""
        if self.preparation_seal is not _DIAGNOSTIC_PREPARATION_SEAL:
            raise ValueError("diagnostic_preparation_not_owned")
        event = validate_diagnostic_event(DiagnosticEvent.model_validate_json(self.event_json))
        payload = None if self.payload_json is None else json.loads(self.payload_json)
        if payload is not None and not isinstance(payload, dict):
            raise ValueError("diagnostic_preparation_payload_invalid")
        expected = (
            None if payload is None else _sha256_from_canonical_bytes(_payload_bytes(payload))
        )
        if expected != self.payload_sha256 or event.payload_ref != self.payload_ref:
            raise ValueError("diagnostic_preparation_content_mismatch")
        if self.inline_payload and self.payload_ref is not None:
            raise ValueError("diagnostic_preparation_storage_mismatch")
        if payload is not None and not self.inline_payload and self.payload_ref != expected:
            raise ValueError("diagnostic_preparation_cas_identity_mismatch")
        return event, payload


class RuntimeDiagnosticEventLog:
    """Append ADR-0154 diagnostic events to durable store rows."""

    def __init__(
        self,
        *,
        store: Any,
        artifact_store: Any,
        inline_payload_max_bytes: int = INLINE_PAYLOAD_MAX_BYTES,
    ) -> None:
        self._store = store
        self._artifact_store = artifact_store
        self._inline_payload_max_bytes = max(0, int(inline_payload_max_bytes))

    @property
    def artifact_store(self) -> Any:
        """Expose the CAS store for tests and reconciliation tooling."""

        return self._artifact_store

    def prepare(
        self,
        event: DiagnosticEvent | Mapping[str, Any],
        *,
        payload: Mapping[str, Any] | None = None,
        payload_policy: DiagnosticEventPayloadPolicy | None = None,
    ) -> _PreparedDiagnosticEvent:
        """Prepare immutable payload/CAS values without publishing a diagnostic row.

        All caller mapping access, validation, serialization and CAS I/O occur
        here. A control-job creation transaction receives only frozen values;
        it must reconcile the actual source before publishing them.
        """
        active = getattr(self._store, "_has_active_job_transaction", None)
        if callable(active) and active():
            raise RuntimeError("diagnostic_preparation_inside_store_transaction")
        diagnostic_event = DiagnosticEvent.model_validate(event)
        policy = payload_policy or DiagnosticEventPayloadPolicy(
            inline_max_bytes=self._inline_payload_max_bytes
        )
        payload_ref = diagnostic_event.payload_ref
        payload_json: str | None = None
        payload_sha256: str | None = None
        inline_payload = False
        if payload is not None:
            # The Store already requires JSON-compatible inline values. Freeze
            # that exact JSON snapshot before any provider can retain the map.
            payload_json = json.dumps(dict(payload), sort_keys=True)
            snapshot = json.loads(payload_json)
            payload_bytes = _payload_bytes(snapshot)
            payload_sha256 = _sha256_from_canonical_bytes(payload_bytes)
            if payload_ref or _payload_requires_cas(
                snapshot, payload_bytes=payload_bytes, event=diagnostic_event, policy=policy
            ):
                ref = self._artifact_store.put_json(
                    snapshot,
                    ArtifactWriteOptions(
                        kind="runtime.diagnostic_event_payload",
                        media_type="application/json",
                        schema=SchemaInfo(
                            name="polisyos.runtime.DiagnosticEventPayload", version="1.0"
                        ),
                    ),
                    canon_spec=CanonSpec(forbid_floats=False),
                )
                payload_ref = str(ref.artifact_id)
                if payload_ref != payload_sha256:
                    raise ValueError("diagnostic_preparation_cas_identity_mismatch")
                diagnostic_event = diagnostic_event.model_copy(update={"payload_ref": payload_ref})
            else:
                inline_payload = True
        validated = validate_diagnostic_event(diagnostic_event)
        return _PreparedDiagnosticEvent(
            event_json=json.dumps(validated.model_dump(mode="json"), sort_keys=True),
            payload_json=payload_json,
            payload_ref=payload_ref,
            payload_sha256=payload_sha256,
            inline_payload=inline_payload,
            preparation_seal=_DIAGNOSTIC_PREPARATION_SEAL,
        )

    def load_payload(self, record: _DiagnosticPayloadRecord) -> dict[str, Any] | None:
        """Resolve and content-bind a stored payload without holding a Store transaction."""
        import hashlib

        from polisyos.core.artifacts.ids import ArtifactID
        from polisyos.core.canon import from_canonical_bytes

        if record.payload_ref is not None:
            raw = self._artifact_store.get_bytes(ArtifactID.model_validate(record.payload_ref))
            digest = "sha256:" + hashlib.sha256(raw).hexdigest()
            if digest != record.payload_sha256 or digest != record.payload_ref:
                raise ValueError("diagnostic_payload_content_mismatch")
            payload = from_canonical_bytes(raw)
        else:
            payload = record.payload_inline
            digest = (
                None if payload is None else _sha256_from_canonical_bytes(_payload_bytes(payload))
            )
            if digest != record.payload_sha256:
                raise ValueError("diagnostic_payload_content_mismatch")
        if payload is not None and not isinstance(payload, dict):
            raise ValueError("diagnostic_payload_not_object")
        return payload

    def append(
        self,
        event: DiagnosticEvent | Mapping[str, Any],
        *,
        payload: Mapping[str, Any] | None = None,
        payload_policy: DiagnosticEventPayloadPolicy | None = None,
    ) -> Any:
        """Persist one validated diagnostic event and its payload authority record."""

        diagnostic_event = DiagnosticEvent.model_validate(event)
        policy = payload_policy or DiagnosticEventPayloadPolicy(
            inline_max_bytes=self._inline_payload_max_bytes
        )
        payload_ref = diagnostic_event.payload_ref
        payload_inline: dict[str, Any] | None = None
        payload_sha256: str | None = None

        if payload is not None:
            payload_payload = dict(payload)
            payload_bytes = _payload_bytes(payload_payload)
            payload_sha256 = _sha256_from_canonical_bytes(payload_bytes)
            if payload_ref or _payload_requires_cas(
                payload_payload,
                payload_bytes=payload_bytes,
                event=diagnostic_event,
                policy=policy,
            ):
                ref = self._artifact_store.put_json(
                    payload_payload,
                    ArtifactWriteOptions(
                        kind="runtime.diagnostic_event_payload",
                        media_type="application/json",
                        schema=SchemaInfo(
                            name="polisyos.runtime.DiagnosticEventPayload",
                            version="1.0",
                        ),
                    ),
                    canon_spec=CanonSpec(forbid_floats=False),
                )
                payload_ref = str(ref.artifact_id)
                diagnostic_event = diagnostic_event.model_copy(update={"payload_ref": payload_ref})
            else:
                payload_inline = payload_payload

        validated = validate_diagnostic_event(diagnostic_event)
        return self._store.append_diagnostic_event(
            event=validated,
            payload_ref=payload_ref,
            payload_inline=payload_inline,
            payload_sha256=payload_sha256,
        )

    def append_correction(
        self,
        *,
        original_event_id: str,
        action: str,
        reason: str,
        trace_id: str,
        run_id: str,
        job_id: str,
        tenant_id: str,
        cell_id: str,
        execution_profile: str,
        phase: str,
    ) -> Any:
        """Append a corrective event without changing historical event meaning."""

        normalized_action = action.strip().casefold()
        if normalized_action not in CORRECTIVE_EVENT_ACTIONS:
            raise ValueError(f"unsupported corrective diagnostic action: {action!r}")

        event = DiagnosticEvent(
            event_id=f"evt_{normalized_action}_{uuid.uuid4().hex[:16]}",
            event_source="polisyos.runtime.reconciliation",
            event_type="polisyos.runtime.diagnostic.reconciliation_result.v1",
            event_time=datetime.now(UTC).replace(microsecond=0),
            event_subject=(
                f"run/{run_id}/job/{job_id}/phase/{phase}/correction/{normalized_action}"
            ),
            schema_name=DIAGNOSTIC_EVENT_SCHEMA_NAME,
            schema_version=DIAGNOSTIC_EVENT_SCHEMA_VERSION,
            trace_id=trace_id,
            span_id=f"span_{uuid.uuid4().hex[:16]}",
            parent_span_id=None,
            run_id=run_id,
            job_id=job_id,
            tenant_id=tenant_id,
            cell_id=cell_id,
            producer_component="polisyos.runtime.diagnostic_event_log",
            producer_version="2026.05.15+hds-phase2.2",
            execution_profile=execution_profile,
            phase=phase,
            state_before=None,
            state_after=normalized_action,
            payload_ref=None,
            artifact_refs=(),
            input_refs=(original_event_id,),
            blocking_status="blocking",
            redaction_policy_ref="redaction-policy/runtime-diagnostics-v1",
            duplicate_of=original_event_id,
            dedupe_key=f"{original_event_id}:{normalized_action}",
            sampling_decision="always_record",
            sampling_rate=1.0,
        )
        return self.append(
            event,
            payload={
                "action": normalized_action,
                "reason": reason,
                "original_event_id": original_event_id,
            },
            payload_policy=DiagnosticEventPayloadPolicy(authority_bearing=True),
        )

    def list_events(
        self,
        *,
        event_id: str | None = None,
        run_id: str | None = None,
        job_id: str | None = None,
        limit: int = 500,
    ) -> list[Any]:
        """List persisted diagnostic events from the backing store."""

        return self._store.list_diagnostic_events(
            event_id=event_id,
            run_id=run_id,
            job_id=job_id,
            limit=limit,
        )


def _payload_requires_cas(
    payload: Mapping[str, Any],
    *,
    payload_bytes: bytes,
    event: DiagnosticEvent,
    policy: DiagnosticEventPayloadPolicy,
) -> bool:
    if (
        policy.authority_bearing
        or policy.redacted
        or policy.sensitive
        or _contains_sensitive_key(payload)
        or len(payload_bytes) > policy.inline_max_bytes
    ):
        return True
    return event.execution_profile.casefold() in SERIOUS_EXECUTION_PROFILES


def _contains_sensitive_key(value: Any) -> bool:
    if isinstance(value, Mapping):
        for key, item in value.items():
            key_text = str(key).casefold()
            if any(marker in key_text for marker in _SENSITIVE_KEY_MARKERS):
                return True
            if _contains_sensitive_key(item):
                return True
    elif isinstance(value, list | tuple):
        return any(_contains_sensitive_key(item) for item in value)
    return False


def _payload_bytes(payload: Mapping[str, Any]) -> bytes:
    return to_canonical_bytes(payload, CanonSpec(forbid_floats=False))


def _sha256_from_canonical_bytes(payload_bytes: bytes) -> str:
    import hashlib

    return f"sha256:{hashlib.sha256(payload_bytes).hexdigest()}"


__all__ = [
    "CORRECTIVE_EVENT_ACTIONS",
    "INLINE_PAYLOAD_MAX_BYTES",
    "DiagnosticEventPayloadPolicy",
    "RuntimeDiagnosticEventLog",
]
