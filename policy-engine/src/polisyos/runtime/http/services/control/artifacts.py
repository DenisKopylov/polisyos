"""Runtime control-plane artifact helpers."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from polisyos.core.artifacts.manifest import (
    ArtifactAuthorityInfo,
    ArtifactGovernanceInfo,
    ArtifactRef,
    ArtifactSameInputClosureInfo,
    ArtifactTenantContextInfo,
    InputRef,
    ProducerInfo,
    SchemaInfo,
)
from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
from polisyos.core.canon import (
    CanonSpec,
    content_hash,
    from_canonical_bytes,
    to_canonical_bytes,
)
from polisyos.runtime.http.services import _control_contracts as _contracts
from polisyos.runtime.http.services.control.production_data import production_data_bundle_path
from polisyos.runtime.quality.attestation import (
    build_verified_attestation_record,
    serialize_attestation_record,
)
from polisyos.runtime.quality.authority import (
    AUTHORITY_ENVELOPE_CONTRACT_NAME,
    AUTHORITY_ENVELOPE_CONTRACT_VERSION,
    EvidenceAuthorityEnvelope,
    GovernanceMetadata,
    SameInputClosure,
)
from polisyos.runtime.quality.authority_reconciliation import reconcile_authority_ref
from polisyos.runtime.quality.diagnostic_events import (
    DIAGNOSTIC_EVENT_SCHEMA_NAME,
    DIAGNOSTIC_EVENT_SCHEMA_VERSION,
    DiagnosticEvent,
    validate_diagnostic_event,
)
from polisyos.runtime.quality.event_log import DiagnosticEventPayloadPolicy

NORMATIVE_APPLICABILITY_REPORT_KIND = "lex.normative_applicability_report"
AUTHORITY_ENVELOPE_ARTIFACT_KIND = "runtime_quality.evidence_authority_envelope"
DIAGNOSTIC_EVENT_ARTIFACT_KIND = "runtime_quality.diagnostic_event"
TRUST_BOUNDARY_ATTESTATION_ARTIFACT_KIND = "runtime_quality.trust_boundary_attestation"


@dataclass(frozen=True, slots=True)
class AuthorityArtifactWriteResult:
    """Return refs produced by one authority-aware runtime CAS write."""

    cas_ref: ArtifactRef
    payload_sha256: str
    manifest_ref: str
    authority_envelope_ref: ArtifactRef
    diagnostic_event_ref: ArtifactRef


def _make_artifact_ref(
    ref_str: str,
    *,
    kind: str,
    media_type: str = "application/json",
) -> ArtifactRef:
    return _contracts._make_artifact_ref(ref_str, kind=kind, media_type=media_type)


def _typed_artifact_ref(
    ref_str: str,
    *,
    kind: str,
    ref_type: Any,
    media_type: str = "application/json",
) -> Any:
    return ref_type.model_validate(
        _make_artifact_ref(ref_str, kind=kind, media_type=media_type).model_dump(mode="json")
    )


def _artifact_ref_from_summary_payload(
    payload: Any,
    *,
    kind: str,
    media_type: str = "application/json",
) -> ArtifactRef | None:
    if not isinstance(payload, dict):
        return None
    artifact_id = payload.get("artifact_id")
    if not isinstance(artifact_id, str) or not artifact_id:
        return None
    return _make_artifact_ref(artifact_id, kind=kind, media_type=media_type)


def _normative_applicability_report_write_options(
    *,
    inputs: list[InputRef] | None = None,
) -> ArtifactWriteOptions:
    return ArtifactWriteOptions(
        kind=NORMATIVE_APPLICABILITY_REPORT_KIND,
        media_type="application/json",
        schema=SchemaInfo(
            name="polisyos.lex.NormativeApplicabilityReport",
            version="1.0",
        ),
        inputs=list(inputs or []),
    )


def write_authority_artifact(
    store: Any,
    payload: object,
    opts: ArtifactWriteOptions,
    *,
    evidence_id: str,
    evidence_class: str,
    authority_role: str,
    provenance_kind: str,
    owner: str,
    reader_contract: str,
    reader_contract_version: str,
    tenant_id: str,
    cell_id: str | None,
    run_id: str,
    job_id: str,
    trace_id: str,
    span_id: str,
    parent_span_id: str | None,
    requested_execution_profile: str,
    effective_execution_profile: str,
    phase: str,
    generated_at: str,
    as_of_time: str,
    same_input_closure: SameInputClosure | Mapping[str, Any],
    input_refs: list[str] | tuple[str, ...] | None,
    effective_mode_ref: str,
    validation_status: str,
    blocking_status: str,
    governance: GovernanceMetadata | Mapping[str, Any],
    degradation_ledger_ref: str | None = None,
    schema_compatibility_ref: str | None = None,
    semantic_binding_ref: str | None = None,
    attestation_ref: str | None = None,
    redaction_policy_ref: str | None = None,
    event_id: str | None = None,
    event_source: str = "polisyos.runtime.cas",
    event_type: str = "polisyos.runtime.diagnostic.cas_write.v1",
    event_subject: str | None = None,
    state_before: str | None = None,
    state_after: str | None = "persisted",
    canon_spec: CanonSpec | None = None,
) -> AuthorityArtifactWriteResult:
    """Write a runtime authority artifact plus linked envelope/event records to CAS."""

    canon_spec = canon_spec or CanonSpec()
    payload_bytes = to_canonical_bytes(payload, canon_spec)
    payload_sha256 = content_hash(payload_bytes)
    cas_ref_value = f"sha256:{payload_sha256}"
    manifest_ref = f"cas-manifest://{cas_ref_value}"
    producer = _require_producer(opts)
    schema = _require_schema(opts)
    closure = SameInputClosure.model_validate(same_input_closure)
    authority_governance = GovernanceMetadata.model_validate(governance)
    manifest_inputs = _coerce_manifest_inputs(opts.inputs)
    envelope_input_refs = tuple(input_refs or _input_ref_values(manifest_inputs))
    existing = _existing_authority_result(
        store,
        cas_ref_value=cas_ref_value,
        payload_sha256=payload_sha256,
        artifact_kind=opts.kind,
    )
    if existing is not None:
        return existing
    effective_attestation_ref = attestation_ref or _persist_cas_writer_attestation(
        store,
        cas_ref_value=cas_ref_value,
        manifest_ref=manifest_ref,
        payload_sha256=payload_sha256,
        schema=schema,
        producer=producer,
        tenant_id=tenant_id,
        cell_id=cell_id,
        execution_profile=effective_execution_profile,
        phase=phase,
        generated_at=generated_at,
    )

    diagnostic_event = _build_diagnostic_event(
        event_id=event_id,
        evidence_id=evidence_id,
        cas_ref=cas_ref_value,
        event_source=event_source,
        event_type=event_type,
        event_subject=event_subject,
        event_time=generated_at,
        run_id=run_id,
        job_id=job_id,
        tenant_id=tenant_id,
        cell_id=cell_id,
        trace_id=trace_id,
        span_id=span_id,
        parent_span_id=parent_span_id,
        producer=producer,
        execution_profile=effective_execution_profile,
        phase=phase,
        state_before=state_before,
        state_after=state_after,
        input_refs=envelope_input_refs,
        blocking_status=blocking_status,
        redaction_policy_ref=redaction_policy_ref,
    )
    diagnostic_event_ref = store.put_json(
        diagnostic_event.model_dump(mode="json"),
        _diagnostic_event_write_options(
            opts,
            inputs=manifest_inputs,
            tenant_id=tenant_id,
            cell_id=cell_id,
            same_input_closure=closure,
        ),
        canon_spec,
    )

    authority_envelope = EvidenceAuthorityEnvelope.model_validate(
        {
            "evidence_id": evidence_id,
            "artifact_ref": cas_ref_value,
            "artifact_kind": opts.kind,
            "evidence_class": evidence_class,
            "authority_role": authority_role,
            "provenance_kind": provenance_kind,
            "producer_component": str(producer.component),
            "producer_version": producer.version,
            "owner": owner,
            "runtime_event_ref": str(diagnostic_event_ref.artifact_id),
            "cas_ref": cas_ref_value,
            "payload_sha256": payload_sha256,
            "schema_name": schema.name,
            "schema_version": schema.version,
            "reader_contract": reader_contract,
            "reader_contract_version": reader_contract_version,
            "tenant_id": tenant_id,
            "cell_id": cell_id,
            "run_id": run_id,
            "job_id": job_id,
            "trace_id": trace_id,
            "span_id": span_id,
            "parent_span_id": parent_span_id,
            "requested_execution_profile": requested_execution_profile,
            "effective_execution_profile": effective_execution_profile,
            "phase": phase,
            "state_before": state_before,
            "state_after": state_after,
            "generated_at": generated_at,
            "as_of_time": as_of_time,
            "same_input_closure": closure.model_dump(mode="json"),
            "input_refs": envelope_input_refs,
            "output_refs": (cas_ref_value,),
            "effective_mode_ref": effective_mode_ref,
            "degradation_ledger_ref": degradation_ledger_ref,
            "schema_compatibility_ref": schema_compatibility_ref,
            "semantic_binding_ref": semantic_binding_ref,
            "attestation_ref": effective_attestation_ref,
            "redaction_policy_ref": redaction_policy_ref,
            "validation_status": validation_status,
            "blocking_status": blocking_status,
            "governance": authority_governance.model_dump(mode="json"),
        }
    )
    authority_envelope_ref = store.put_json(
        authority_envelope.model_dump(mode="json"),
        _authority_envelope_write_options(
            opts,
            inputs=manifest_inputs,
            tenant_id=tenant_id,
            cell_id=cell_id,
            same_input_closure=closure,
        ),
        canon_spec,
    )

    cas_ref = store.put_json(
        payload,
        _authority_payload_write_options(
            opts,
            inputs=manifest_inputs,
            tenant_id=tenant_id,
            cell_id=cell_id,
            same_input_closure=closure,
            authority_envelope_ref=str(authority_envelope_ref.artifact_id),
            diagnostic_event_ref=str(diagnostic_event_ref.artifact_id),
            manifest_ref=manifest_ref,
            payload_sha256=payload_sha256,
        ),
        canon_spec,
    )
    if str(cas_ref.artifact_id) != cas_ref_value:
        raise ValueError(
            "authority payload CAS ref changed during write: "
            f"expected {cas_ref_value}, got {cas_ref.artifact_id}"
        )
    _assert_authority_manifest_linkage(
        store,
        cas_ref=cas_ref,
        authority_envelope_ref=authority_envelope_ref,
        diagnostic_event_ref=diagnostic_event_ref,
        manifest_ref=manifest_ref,
        payload_sha256=payload_sha256,
    )
    return AuthorityArtifactWriteResult(
        cas_ref=cas_ref,
        payload_sha256=payload_sha256,
        manifest_ref=manifest_ref,
        authority_envelope_ref=authority_envelope_ref,
        diagnostic_event_ref=diagnostic_event_ref,
    )


def _persist_cas_writer_attestation(
    store: Any,
    *,
    cas_ref_value: str,
    manifest_ref: str,
    payload_sha256: str,
    schema: SchemaInfo,
    producer: ProducerInfo,
    tenant_id: str,
    cell_id: str | None,
    execution_profile: str,
    phase: str,
    generated_at: str,
) -> str:
    record = build_verified_attestation_record(
        boundary_id="cas_writer",
        material_refs={
            "payload_bytes": f"sha256:{payload_sha256}",
            "schema_identity": f"{schema.name}@{schema.version}",
            "tenant_identity": tenant_id,
        },
        product_refs={
            "cas_ref": cas_ref_value,
            "artifact_manifest": manifest_ref,
        },
        producer_component=str(producer.component),
        producer_version=producer.version,
        tenant_id=tenant_id,
        cell_id=cell_id,
        execution_profile=execution_profile,
        metadata={
            "phase": phase,
            "source": "runtime.cas",
            "authority_role": "producer_authority",
        },
        generated_at=_event_time(generated_at),
    )
    ref = store.put_json(
        serialize_attestation_record(record),
        ArtifactWriteOptions(
            kind=TRUST_BOUNDARY_ATTESTATION_ARTIFACT_KIND,
            media_type="application/json",
            schema=SchemaInfo(
                name="polisyos.runtime.quality.AttestationRecord",
                version="1.0",
            ),
            producer=producer,
            tenant_context=_tenant_context(tenant_id, cell_id),
        ),
        CanonSpec(forbid_floats=False),
    )
    return str(ref.artifact_id)


def write_runtime_authority_artifact(
    store: Any,
    event_log: Any,
    payload: object,
    opts: ArtifactWriteOptions,
    **authority_fields: Any,
) -> AuthorityArtifactWriteResult:
    """Write a runtime authority artifact and append its event to the durable log."""

    canon_spec = authority_fields.get("canon_spec")
    if not isinstance(canon_spec, CanonSpec):
        canon_spec = CanonSpec()
    payload_sha256 = content_hash(to_canonical_bytes(payload, canon_spec))
    cas_ref_value = f"sha256:{payload_sha256}"
    existing = _existing_authority_result(
        store,
        cas_ref_value=cas_ref_value,
        payload_sha256=payload_sha256,
        artifact_kind=opts.kind,
    )
    if existing is not None:
        reconcile_authority_ref(
            artifact_store=store,
            event_log=event_log,
            cas_ref=str(existing.cas_ref.artifact_id),
            expected_tenant_id=authority_fields.get("tenant_id"),
            expected_cell_id=authority_fields.get("cell_id"),
            expected_run_id=authority_fields.get("run_id"),
            expected_job_id=authority_fields.get("job_id"),
        )
        return existing

    result = write_authority_artifact(
        store,
        payload,
        opts,
        **authority_fields,
    )
    event_payload = from_canonical_bytes(store.get_bytes(result.diagnostic_event_ref.artifact_id))
    event = DiagnosticEvent.model_validate(event_payload)
    event_log.append(
        event,
        payload_policy=DiagnosticEventPayloadPolicy(authority_bearing=True),
    )
    return result


def _existing_authority_result(
    store: Any,
    *,
    cas_ref_value: str,
    payload_sha256: str,
    artifact_kind: str,
) -> AuthorityArtifactWriteResult | None:
    try:
        if not store.has(cas_ref_value):
            return None
        manifest = store.get_manifest(cas_ref_value)
    except Exception:
        return None
    authority = manifest.authority
    if authority is None:
        return None
    if authority.payload_sha256 != payload_sha256:
        raise ValueError(
            "existing authority manifest payload hash mismatch for "
            f"{cas_ref_value}: expected {payload_sha256}, got {authority.payload_sha256}"
        )
    return AuthorityArtifactWriteResult(
        cas_ref=_make_artifact_ref(cas_ref_value, kind=artifact_kind),
        payload_sha256=payload_sha256,
        manifest_ref=authority.manifest_ref,
        authority_envelope_ref=_make_artifact_ref(
            authority.authority_envelope_ref,
            kind=AUTHORITY_ENVELOPE_ARTIFACT_KIND,
        ),
        diagnostic_event_ref=_make_artifact_ref(
            authority.diagnostic_event_ref,
            kind=DIAGNOSTIC_EVENT_ARTIFACT_KIND,
        ),
    )


def _require_producer(opts: ArtifactWriteOptions) -> ProducerInfo:
    producer = opts.producer
    if producer is None:
        raise ValueError("authority writes require ArtifactWriteOptions.producer")
    return ProducerInfo.model_validate(producer)


def _require_schema(opts: ArtifactWriteOptions) -> SchemaInfo:
    schema = opts.schema
    if schema is None:
        raise ValueError("authority writes require ArtifactWriteOptions.schema")
    return SchemaInfo.model_validate(schema)


def _coerce_manifest_inputs(values: list[Any] | None) -> list[InputRef]:
    return [InputRef.model_validate(value) for value in values or []]


def _input_ref_values(inputs: list[InputRef]) -> tuple[str, ...]:
    return tuple(str(input_ref.artifact_id) for input_ref in inputs)


def _tenant_context(tenant_id: str, cell_id: str | None) -> ArtifactTenantContextInfo:
    return ArtifactTenantContextInfo(tenant_id=tenant_id, cell_id=cell_id)


def _same_input_closure_summary(
    closure: SameInputClosure,
) -> ArtifactSameInputClosureInfo:
    return ArtifactSameInputClosureInfo(
        closure_id=closure.closure_id,
        status=closure.status,
        closure_sha256=closure.closure_sha256,
        run_id=closure.run_id,
        job_id=closure.job_id,
        tenant_id=closure.tenant_id,
        cell_id=closure.cell_id,
        evidence_input_refs=closure.evidence_input_refs,
    )


def _copy_governance(
    opts: ArtifactWriteOptions,
) -> ArtifactGovernanceInfo | None:
    governance = getattr(opts, "governance", None)
    if governance is None:
        return None
    return ArtifactGovernanceInfo.model_validate(governance)


def _copy_write_options(
    opts: ArtifactWriteOptions,
    *,
    kind: str,
    schema: SchemaInfo,
    inputs: list[InputRef],
    tenant_id: str,
    cell_id: str | None,
    same_input_closure: SameInputClosure,
    authority: ArtifactAuthorityInfo | None = None,
) -> ArtifactWriteOptions:
    return ArtifactWriteOptions(
        kind=kind,
        media_type="application/json",
        schema=schema,
        producer=_require_producer(opts),
        env=opts.env,
        inputs=inputs,
        canon=opts.canon,
        governance=_copy_governance(opts),
        tenant_context=_tenant_context(tenant_id, cell_id),
        same_input_closure=_same_input_closure_summary(same_input_closure),
        authority=authority,
    )


def _diagnostic_event_write_options(
    opts: ArtifactWriteOptions,
    *,
    inputs: list[InputRef],
    tenant_id: str,
    cell_id: str | None,
    same_input_closure: SameInputClosure,
) -> ArtifactWriteOptions:
    return _copy_write_options(
        opts,
        kind=DIAGNOSTIC_EVENT_ARTIFACT_KIND,
        schema=SchemaInfo(
            name=DIAGNOSTIC_EVENT_SCHEMA_NAME,
            version=DIAGNOSTIC_EVENT_SCHEMA_VERSION,
        ),
        inputs=inputs,
        tenant_id=tenant_id,
        cell_id=cell_id,
        same_input_closure=same_input_closure,
    )


def _authority_envelope_write_options(
    opts: ArtifactWriteOptions,
    *,
    inputs: list[InputRef],
    tenant_id: str,
    cell_id: str | None,
    same_input_closure: SameInputClosure,
) -> ArtifactWriteOptions:
    return _copy_write_options(
        opts,
        kind=AUTHORITY_ENVELOPE_ARTIFACT_KIND,
        schema=SchemaInfo(
            name=AUTHORITY_ENVELOPE_CONTRACT_NAME,
            version=AUTHORITY_ENVELOPE_CONTRACT_VERSION,
        ),
        inputs=inputs,
        tenant_id=tenant_id,
        cell_id=cell_id,
        same_input_closure=same_input_closure,
    )


def _authority_payload_write_options(
    opts: ArtifactWriteOptions,
    *,
    inputs: list[InputRef],
    tenant_id: str,
    cell_id: str | None,
    same_input_closure: SameInputClosure,
    authority_envelope_ref: str,
    diagnostic_event_ref: str,
    manifest_ref: str,
    payload_sha256: str,
) -> ArtifactWriteOptions:
    return _copy_write_options(
        opts,
        kind=opts.kind,
        schema=_require_schema(opts),
        inputs=inputs,
        tenant_id=tenant_id,
        cell_id=cell_id,
        same_input_closure=same_input_closure,
        authority=ArtifactAuthorityInfo(
            authority_envelope_ref=authority_envelope_ref,
            diagnostic_event_ref=diagnostic_event_ref,
            manifest_ref=manifest_ref,
            payload_sha256=payload_sha256,
        ),
    )


def _build_diagnostic_event(
    *,
    event_id: str | None,
    evidence_id: str,
    cas_ref: str,
    event_source: str,
    event_type: str,
    event_subject: str | None,
    event_time: str,
    run_id: str,
    job_id: str,
    tenant_id: str,
    cell_id: str | None,
    trace_id: str,
    span_id: str,
    parent_span_id: str | None,
    producer: ProducerInfo,
    execution_profile: str,
    phase: str,
    state_before: str | None,
    state_after: str | None,
    input_refs: tuple[str, ...],
    blocking_status: str | None,
    redaction_policy_ref: str | None,
) -> DiagnosticEvent:
    normalized_event_id = event_id or _stable_event_id(
        evidence_id=evidence_id,
        cas_ref=cas_ref,
        trace_id=trace_id,
        span_id=span_id,
    )
    event = DiagnosticEvent.model_validate(
        {
            "event_id": normalized_event_id,
            "event_source": event_source,
            "event_type": event_type,
            "event_time": _event_time(event_time),
            "event_subject": event_subject
            or f"run/{run_id}/job/{job_id}/phase/{phase}/artifact/{cas_ref}",
            "schema_name": DIAGNOSTIC_EVENT_SCHEMA_NAME,
            "schema_version": DIAGNOSTIC_EVENT_SCHEMA_VERSION,
            "trace_id": trace_id,
            "span_id": span_id,
            "parent_span_id": parent_span_id,
            "run_id": run_id,
            "job_id": job_id,
            "tenant_id": tenant_id,
            "cell_id": cell_id or "",
            "producer_component": str(producer.component),
            "producer_version": producer.version,
            "execution_profile": execution_profile,
            "phase": phase,
            "state_before": state_before,
            "state_after": state_after,
            "payload_ref": cas_ref,
            "artifact_refs": (cas_ref,),
            "input_refs": input_refs,
            "blocking_status": blocking_status,
            "redaction_policy_ref": redaction_policy_ref,
            "duplicate_of": None,
            "dedupe_key": f"{job_id}:{phase}:{evidence_id}:cas_write",
            "sampling_decision": "always_record",
            "sampling_rate": None,
        }
    )
    return validate_diagnostic_event(event, expected_artifact_refs=(cas_ref,), now=None)


def _event_time(value: str) -> datetime:
    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _stable_event_id(
    *,
    evidence_id: str,
    cas_ref: str,
    trace_id: str,
    span_id: str,
) -> str:
    seed = f"policyos:hds:cas-write:{evidence_id}:{cas_ref}:{trace_id}:{span_id}"
    return f"evt-{uuid5(NAMESPACE_URL, seed)}"


def _assert_authority_manifest_linkage(
    store: Any,
    *,
    cas_ref: ArtifactRef,
    authority_envelope_ref: ArtifactRef,
    diagnostic_event_ref: ArtifactRef,
    manifest_ref: str,
    payload_sha256: str,
) -> None:
    manifest = store.get_manifest(cas_ref.artifact_id)
    authority = manifest.authority
    if authority is None:
        raise ValueError(f"authority manifest linkage missing for {cas_ref.artifact_id}")
    expected = ArtifactAuthorityInfo(
        authority_envelope_ref=str(authority_envelope_ref.artifact_id),
        diagnostic_event_ref=str(diagnostic_event_ref.artifact_id),
        manifest_ref=manifest_ref,
        payload_sha256=payload_sha256,
    )
    if authority != expected:
        raise ValueError(
            "authority manifest linkage mismatch for "
            f"{cas_ref.artifact_id}: expected {expected}, got {authority}"
        )


def _nested_get(payload: Any, key: str) -> Any:
    if isinstance(payload, Mapping):
        if key in payload:
            return payload[key]
        for value in payload.values():
            found = _nested_get(value, key)
            if found is not None:
                return found
    elif isinstance(payload, list):
        for value in payload:
            found = _nested_get(value, key)
            if found is not None:
                return found
    return None


def _runtime_quality_evidence_from_payloads(*payloads: Any) -> dict[str, Any]:
    """Extract runtime-owned quality reports embedded in job/run/agent payloads."""
    evidence: dict[str, Any] = {}
    for payload in payloads:
        runtime_evidence = _nested_get(payload, "runtime_quality_evidence")
        if isinstance(runtime_evidence, Mapping):
            for key, value in runtime_evidence.items():
                if isinstance(key, str) and isinstance(value, Mapping) and key not in evidence:
                    evidence[key] = dict(value)
        normative_evidence = _nested_get(payload, "normative_evidence")
        if isinstance(normative_evidence, Mapping) and "normative_evidence" not in evidence:
            evidence["normative_evidence"] = dict(normative_evidence)
    return evidence


def _resolve_curated_dir() -> Path:
    configured = os.getenv("POLISYOS_CURATED_DIR") or os.getenv("POLISYOS_FABRIC_CURATED_DIR")
    if configured:
        return Path(configured).expanduser()

    manifest_candidate = production_data_bundle_path("curated", allow_default=True)
    legacy_candidates = (
        Path("data/curated"),
        Path("policy-engine/data/curated"),
        Path("production_data/canonical/local_data_20260501/policy_engine_data/curated"),
        Path(
            "policy-engine/production_data/canonical/local_data_20260501/policy_engine_data/curated"
        ),
    )
    candidates = legacy_candidates
    if manifest_candidate is not None:
        candidates = (manifest_candidate, *legacy_candidates)
    for candidate in candidates:
        if _has_curated_catalog(candidate):
            return candidate
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def _has_curated_catalog(candidate: Path) -> bool:
    return candidate.exists() and (
        (candidate / "data_contracts.json").exists()
        or (candidate / "source_bindings.json").exists()
    )


__all__ = [
    "AUTHORITY_ENVELOPE_ARTIFACT_KIND",
    "DIAGNOSTIC_EVENT_ARTIFACT_KIND",
    "NORMATIVE_APPLICABILITY_REPORT_KIND",
    "TRUST_BOUNDARY_ATTESTATION_ARTIFACT_KIND",
    "AuthorityArtifactWriteResult",
    "_artifact_ref_from_summary_payload",
    "_make_artifact_ref",
    "_normative_applicability_report_write_options",
    "_resolve_curated_dir",
    "_runtime_quality_evidence_from_payloads",
    "_typed_artifact_ref",
    "write_authority_artifact",
    "write_runtime_authority_artifact",
]
