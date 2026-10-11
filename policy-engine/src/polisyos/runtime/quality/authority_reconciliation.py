"""Reconcile runtime CAS authority artifacts with durable diagnostic events."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, NoReturn, cast

from polisyos.core import canon
from polisyos.core.artifacts import VerificationReport, resolve_manifest_by_profile
from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import (
    ArtifactAuthorityInfo,
    ArtifactManifest,
    ArtifactRef,
    artifact_reference_parts,
)
from polisyos.runtime.quality.diagnostic_events import (
    DIAGNOSTIC_EVENT_ARTIFACT_KIND,
    DIAGNOSTIC_EVENT_SCHEMA_NAME,
    DIAGNOSTIC_EVENT_SCHEMA_VERSION,
    RECONCILIATION_FAILURE_CODES,
    DiagnosticEvent,
)

if TYPE_CHECKING:
    from collections.abc import Mapping


@dataclass(frozen=True, slots=True)
class AuthorityReconciliationReport:
    """Result of one CAS/event authority cross-check."""

    status: str
    cas_ref: str
    durable_event_id: str | None = None
    findings: tuple[dict[str, Any], ...] = ()


@dataclass(frozen=True, slots=True)
class _AuthorityReadFailure:
    """Safe classification of an exception raised by an external read."""

    error_kind: str


@dataclass(frozen=True, slots=True)
class _AuthorityReadResult:
    """Result of an external read without retaining its exception object."""

    value: Any = None
    failure: _AuthorityReadFailure | None = None


class _AuthorityManifestReadError(ValueError):
    """ValueError-compatible fixed refusal from the exported manifest resolver."""

    def __init__(self, error_kind: str) -> None:
        super().__init__("authority_diagnostic_event_manifest_resolution_failed")
        self.error_kind = error_kind


class AuthorityReconciliationError(ValueError):
    """Raised when serious runtime authority reconciliation fails."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.details = dict(details or {})


DIAGNOSTIC_EVENT_MEDIA_TYPE = "application/json"


def _safe_exception_kind(error: Exception) -> str:
    """Map an arbitrary external exception to a fixed public category."""
    if isinstance(error, FileNotFoundError):
        return "not_found"
    if isinstance(error, PermissionError):
        return "permission_denied"
    if isinstance(error, KeyError):
        return "unresolved_lookup"
    if isinstance(error, TypeError):
        return "type_error"
    if isinstance(error, ValueError):
        return "value_error"
    return "read_error"


def _capture_untrusted_read(read: Any) -> _AuthorityReadResult:
    """Capture any ordinary read failure without retaining backend error text."""
    try:
        return _AuthorityReadResult(value=read())
    except Exception as error:
        return _AuthorityReadResult(failure=_AuthorityReadFailure(_safe_exception_kind(error)))


def _capture_manifest_read(
    artifact_store: Any,
    artifact_id: ArtifactID,
    profile_sha256: str | None,
) -> _AuthorityReadResult:
    """Resolve and validate one default or profile-selected CAS manifest."""
    if profile_sha256 is None:
        return _capture_untrusted_read(
            lambda: ArtifactManifest.model_validate(artifact_store.get_manifest(artifact_id))
        )
    return _capture_untrusted_read(
        lambda: resolve_manifest_by_profile(artifact_store, artifact_id, profile_sha256)
    )


def _capture_bytes_read(artifact_store: Any, selector: Any) -> _AuthorityReadResult:
    """Read one CAS byte object and reject a malformed backend return value."""

    def read_bytes() -> bytes:
        value = artifact_store.get_bytes(selector)
        if not isinstance(value, bytes):
            raise TypeError("CAS byte read did not return bytes")
        return value

    return _capture_untrusted_read(read_bytes)


def _capture_verification(artifact_store: Any, selector: Any) -> _AuthorityReadResult:
    """Run and validate one CAS integrity report."""
    return _capture_untrusted_read(
        lambda: VerificationReport.model_validate(artifact_store.verify(selector))
    )


def _capture_event_rows(event_log: Any, **selector: Any) -> _AuthorityReadResult:
    """Read and materialize event rows within the protected boundary."""
    return _capture_untrusted_read(lambda: list(event_log.list_events(**selector)))


def _safe_failure_details(
    failure: Exception | VerificationReport | _AuthorityReadFailure,
    *,
    artifact_id: ArtifactID | str | None = None,
) -> dict[str, Any]:
    """Project untrusted failures into bounded, typed diagnostic details."""
    if isinstance(failure, _AuthorityReadFailure):
        return {"error_kind": failure.error_kind}
    if isinstance(failure, _AuthorityManifestReadError):
        return {"error_kind": failure.error_kind}
    if isinstance(failure, VerificationReport):
        selected_id = _normalize_cas_ref(str(artifact_id)) if artifact_id is not None else None
        verification: dict[str, Any] = {"status": "failed", "error_kind": "verification_failed"}
        if selected_id is not None:
            verification["artifact_id"] = str(selected_id)
        expected = _safe_sha256_hex(failure.expected_sha256_hex)
        if expected is not None:
            verification["expected_sha256_hex"] = expected
        actual = _safe_sha256_hex(failure.actual_sha256_hex)
        if actual is not None:
            verification["actual_sha256_hex"] = actual
        if (
            isinstance(failure.byte_size, int)
            and not isinstance(failure.byte_size, bool)
            and failure.byte_size >= 0
        ):
            verification["byte_size"] = failure.byte_size
        return {"verification": verification}

    return {"error_kind": _safe_exception_kind(failure)}


def _safe_sha256_hex(value: str | None) -> str | None:
    """Return only a valid content digest, never an arbitrary backend string."""
    if not isinstance(value, str):
        return None
    try:
        return ArtifactID.from_sha256_hex(value).hex
    except (TypeError, ValueError):
        return None


def _fail_authority_store_read(
    error: _AuthorityReadFailure,
    *,
    artifact_id: ArtifactID | str,
    operation: str,
    missing_code: str | None = None,
    profile_sha256: str | None = None,
) -> NoReturn:
    """Classify one failed CAS read without treating lookup keys as absence."""
    details: dict[str, Any] = {"artifact_id": str(artifact_id)}
    if profile_sha256 is not None:
        details["profile_sha256"] = profile_sha256
    details.update(_safe_failure_details(error))

    if error.error_kind == "not_found" and missing_code is not None:
        _fail(
            missing_code,
            f"CAS artifact is missing: {artifact_id}.",
            **details,
        )
    if error.error_kind == "permission_denied":
        _fail(
            "authority_payload_mismatch",
            f"CAS artifact view is not accessible during {operation}.",
            **details,
        )
    _fail(
        "authority_payload_mismatch",
        f"CAS artifact view could not be resolved during {operation}.",
        **details,
    )


def _fail_authority_event_log_read(
    failure: _AuthorityReadFailure, *, event_id: str, operation: str
) -> NoReturn:
    """Refuse an unavailable event-log read without exposing backend details."""
    _fail(
        "authority_payload_mismatch",
        f"Durable diagnostic event lookup is unavailable during {operation}.",
        error_kind=failure.error_kind,
        event_id=event_id,
    )


def _diagnostic_event_manifest_mismatch(manifest: Any) -> str | None:
    """Return the fixed diagnostic-event manifest boundary that failed."""
    schema = manifest.artifact_schema
    if (
        manifest.kind != DIAGNOSTIC_EVENT_ARTIFACT_KIND
        or schema is None
        or schema.name != DIAGNOSTIC_EVENT_SCHEMA_NAME
        or schema.version != DIAGNOSTIC_EVENT_SCHEMA_VERSION
    ):
        return "kind_or_schema"
    if manifest.media_type != DIAGNOSTIC_EVENT_MEDIA_TYPE:
        return "media_type"
    return None


def _resolve_authority_diagnostic_event_ref(
    artifact_store: Any,
    authority: ArtifactAuthorityInfo,
) -> tuple[ArtifactRef | None, _AuthorityReadFailure | None]:
    """Resolve one selected event view while retaining only safe read failures."""
    typed_authority = ArtifactAuthorityInfo.model_validate(authority)
    artifact_id = _normalize_cas_ref(typed_authority.diagnostic_event_ref)
    if artifact_id is None:
        raise ValueError("authority_diagnostic_event_ref_not_cas")
    profile = typed_authority.diagnostic_event_manifest_profile_sha256
    read_result = _capture_manifest_read(artifact_store, artifact_id, profile)
    if read_result.failure is not None:
        return None, read_result.failure
    manifest = read_result.value
    if manifest.artifact_id != artifact_id:
        raise ValueError("authority_diagnostic_event_artifact_id_mismatch")
    mismatch = _diagnostic_event_manifest_mismatch(manifest)
    if mismatch is not None:
        raise ValueError(f"authority_diagnostic_event_{mismatch}_mismatch")
    return (
        ArtifactRef(
            artifact_id=artifact_id,
            kind=manifest.kind,
            media_type=manifest.media_type,
            manifest_profile_sha256=profile,
        ),
        None,
    )


def resolve_authority_diagnostic_event_ref(
    artifact_store: Any,
    authority: ArtifactAuthorityInfo,
) -> ArtifactRef:
    """Resolve the exact event manifest view carried by one authority link.

    Profileless historical links keep selecting their persisted default view;
    this reader does not derive a producer profile for old records.
    """
    resolved, failure = _resolve_authority_diagnostic_event_ref(artifact_store, authority)
    if failure is not None:
        raise _AuthorityManifestReadError(failure.error_kind) from None
    if resolved is None:
        raise AssertionError("successful authority manifest resolution returned no ref")
    return resolved


def _resolve_supplied_authority_ref(
    artifact_store: Any,
    requested_ref: ArtifactRef,
) -> tuple[ArtifactID, ArtifactRef, Any]:
    """Resolve and validate the exact manifest view named by a typed ref."""
    try:
        artifact_id, profile_sha256, selected_ref = artifact_reference_parts(requested_ref)
    except (TypeError, ValueError) as exc:
        _fail(
            "authority_payload_mismatch",
            "Supplied CAS artifact reference is malformed.",
            **_safe_failure_details(exc),
        )
    if selected_ref is None:
        _fail(
            "authority_payload_mismatch",
            "Supplied CAS artifact reference did not retain its typed selector.",
        )

    read_result = _capture_manifest_read(artifact_store, artifact_id, profile_sha256)
    if read_result.failure is not None:
        if read_result.failure.error_kind == "not_found" and profile_sha256 is not None:
            probe = _capture_bytes_read(artifact_store, artifact_id)
            if probe.failure is not None:
                _fail_authority_store_read(
                    probe.failure,
                    artifact_id=artifact_id,
                    operation="selected profile existence probe",
                    missing_code="authority_cas_missing",
                    profile_sha256=profile_sha256,
                )
            _fail(
                "authority_payload_mismatch",
                f"Supplied CAS manifest profile is absent for existing artifact {artifact_id}.",
                artifact_id=str(artifact_id),
                profile_sha256=profile_sha256,
            )
        _fail_authority_store_read(
            read_result.failure,
            artifact_id=artifact_id,
            operation="selected manifest resolution",
            missing_code=(
                "authority_cas_missing"
                if profile_sha256 is None and read_result.failure.error_kind == "not_found"
                else None
            ),
            profile_sha256=profile_sha256,
        )
    manifest = read_result.value
    if manifest.artifact_id != artifact_id:
        _fail(
            "authority_payload_mismatch",
            f"CAS manifest view resolved a different artifact than {artifact_id}.",
            selected_artifact_id=str(manifest.artifact_id),
        )
    if manifest.kind != selected_ref.kind or manifest.media_type != selected_ref.media_type:
        _fail(
            "authority_payload_mismatch",
            "Supplied CAS artifact reference does not match its selected manifest view.",
            selected_kind=selected_ref.kind,
            manifest_kind=manifest.kind,
            selected_media_type=selected_ref.media_type,
            manifest_media_type=manifest.media_type,
            profile_sha256=profile_sha256,
        )
    return artifact_id, selected_ref, manifest


def reconcile_authority_ref(
    *,
    artifact_store: Any,
    event_log: Any,
    cas_ref: str | ArtifactID | ArtifactRef,
    expected_tenant_id: str | None = None,
    expected_cell_id: str | None = None,
    expected_run_id: str | None = None,
    expected_job_id: str | None = None,
) -> AuthorityReconciliationReport:
    """Verify that one runtime authority CAS ref has a matching durable event.

    An ``ArtifactRef`` retains its selected manifest profile. String and ID selectors
    keep selecting the default view, preserving the historical caller contract.
    """

    if isinstance(cas_ref, ArtifactRef):
        normalized_ref, selected_selector, manifest = _resolve_supplied_authority_ref(
            artifact_store,
            cas_ref,
        )
    else:
        normalized_ref = _normalize_cas_ref(str(cas_ref))
        if normalized_ref is None:
            _fail(
                "authority_ref_not_cas",
                f"Authority ref is not a CAS ref: {cas_ref!r}.",
                ref=cas_ref,
            )
        normalized_ref = cast("ArtifactID", normalized_ref)
        selected_selector = normalized_ref
        read_result = _capture_manifest_read(artifact_store, normalized_ref, None)
        if read_result.failure is not None:
            _fail_authority_store_read(
                read_result.failure,
                artifact_id=normalized_ref,
                operation="default manifest resolution",
                missing_code=(
                    "authority_cas_missing"
                    if read_result.failure.error_kind == "not_found"
                    else None
                ),
            )
        manifest = read_result.value

    verification_result = _capture_verification(artifact_store, selected_selector)
    if verification_result.failure is not None:
        _fail_authority_store_read(
            verification_result.failure,
            artifact_id=normalized_ref,
            operation="integrity verification",
            profile_sha256=(
                selected_selector.manifest_profile_sha256
                if isinstance(selected_selector, ArtifactRef)
                else None
            ),
        )
    verification = verification_result.value
    if not verification.ok:
        _fail(
            "authority_payload_mismatch",
            f"CAS artifact {normalized_ref} failed integrity verification.",
            **_safe_failure_details(verification, artifact_id=normalized_ref),
        )

    authority = manifest.authority
    if authority is None:
        _fail(
            "authority_payload_mismatch",
            f"CAS artifact {normalized_ref} has no authority manifest linkage.",
        )
    if authority.payload_sha256 != manifest.integrity.sha256:
        _fail(
            "authority_payload_mismatch",
            f"CAS artifact {normalized_ref} manifest payload hash does not match authority hash.",
            expected=manifest.integrity.sha256,
            actual=authority.payload_sha256,
        )

    tenant = manifest.tenant_context
    closure = manifest.same_input_closure
    _assert_expected_identity(
        normalized_ref=normalized_ref,
        manifest_tenant_id=tenant.tenant_id if tenant is not None else None,
        manifest_cell_id=tenant.cell_id if tenant is not None else None,
        manifest_run_id=closure.run_id if closure is not None else None,
        manifest_job_id=closure.job_id if closure is not None else None,
        expected_tenant_id=expected_tenant_id,
        expected_cell_id=expected_cell_id,
        expected_run_id=expected_run_id,
        expected_job_id=expected_job_id,
    )

    try:
        linked_event_ref, resolver_failure = _resolve_authority_diagnostic_event_ref(
            artifact_store, authority
        )
    except (TypeError, ValueError) as exc:
        _fail(
            "authority_payload_mismatch",
            "CAS artifact has an invalid linked diagnostic event selector.",
            **_safe_failure_details(exc),
        )
    if resolver_failure is not None:
        _fail_authority_store_read(
            resolver_failure,
            artifact_id=authority.diagnostic_event_ref,
            operation="linked diagnostic event resolution",
            profile_sha256=authority.diagnostic_event_manifest_profile_sha256,
        )
    if linked_event_ref is None:
        raise AssertionError("successful authority event resolution returned no ref")
    linked_event_id = linked_event_ref.artifact_id
    manifest_result = _capture_manifest_read(
        artifact_store, linked_event_id, linked_event_ref.manifest_profile_sha256
    )
    if manifest_result.failure is not None:
        _fail_authority_store_read(
            manifest_result.failure,
            artifact_id=linked_event_id,
            operation="linked diagnostic event manifest resolution",
            profile_sha256=linked_event_ref.manifest_profile_sha256,
        )
    linked_manifest = manifest_result.value
    linked_verification_result = _capture_verification(artifact_store, linked_event_ref)
    if linked_verification_result.failure is not None:
        _fail_authority_store_read(
            linked_verification_result.failure,
            artifact_id=linked_event_id,
            operation="linked diagnostic event integrity verification",
            profile_sha256=linked_event_ref.manifest_profile_sha256,
        )
    linked_verification = linked_verification_result.value
    if not linked_verification.ok:
        _fail(
            "authority_payload_mismatch",
            f"Linked diagnostic event {linked_event_id} failed integrity verification.",
            **_safe_failure_details(linked_verification, artifact_id=linked_event_id),
        )
    if _diagnostic_event_manifest_mismatch(linked_manifest) is not None:
        _fail(
            "authority_payload_mismatch",
            (
                f"Linked diagnostic event {linked_event_id} has the wrong kind, media type, "
                "or schema."
            ),
        )
    if (
        linked_manifest.inputs != manifest.inputs
        or linked_manifest.producer != manifest.producer
        or linked_manifest.tenant_context != manifest.tenant_context
        or linked_manifest.same_input_closure != manifest.same_input_closure
        or linked_manifest.canon != manifest.canon
        or linked_manifest.governance != manifest.governance
    ):
        _fail(
            "authority_payload_mismatch",
            (
                f"Linked diagnostic event {linked_event_id} manifest context differs from "
                "its authority payload."
            ),
            diagnostic_event_ref=str(linked_event_id),
        )
    bytes_result = _capture_bytes_read(artifact_store, linked_event_ref)
    if bytes_result.failure is not None:
        _fail_authority_store_read(
            bytes_result.failure,
            artifact_id=linked_event_id,
            operation="linked diagnostic event byte read",
            profile_sha256=linked_event_ref.manifest_profile_sha256,
        )
    event_result = _capture_untrusted_read(
        lambda: DiagnosticEvent.model_validate(canon.from_canonical_bytes(bytes_result.value))
    )
    if event_result.failure is not None:
        _fail(
            "authority_payload_mismatch",
            f"Linked diagnostic event {linked_event_id} is malformed.",
            error_kind=event_result.failure.error_kind,
        )
    linked_event = event_result.value
    event_rows = _capture_event_rows(event_log, event_id=linked_event.event_id, limit=2)
    if event_rows.failure is not None:
        _fail_authority_event_log_read(
            event_rows.failure, event_id=linked_event.event_id, operation="linked event lookup"
        )
    records = event_rows.value
    if len(records) != 1:
        _fail(
            "authority_event_collision" if records else "authority_orphan_cas",
            f"Diagnostic event {linked_event.event_id} did not resolve exactly once.",
            event_id=linked_event.event_id,
            record_count=len(records),
        )
    record = records[0]
    event = record.event
    if event != linked_event:
        _fail(
            "authority_payload_mismatch",
            f"Durable event {event.event_id} differs from its linked CAS event.",
            event_id=event.event_id,
        )
    event_ref = _normalize_cas_ref(event.payload_ref or "")
    row_ref = _normalize_cas_ref(record.payload_ref or "")
    if (
        event_ref != normalized_ref
        or row_ref != normalized_ref
        or event.artifact_refs != (str(normalized_ref),)
    ):
        _fail(
            "authority_payload_mismatch",
            f"Durable event {event.event_id} does not bind exactly to {normalized_ref}.",
            event_id=event.event_id,
            event_payload_ref=event.payload_ref,
            row_payload_ref=record.payload_ref,
            event_artifact_refs=event.artifact_refs,
            cas_ref=str(normalized_ref),
        )
    if str(event.tenant_id) != str(tenant.tenant_id if tenant is not None else event.tenant_id):
        _fail(
            "authority_tenant_conflict",
            f"Durable event {event.event_id} tenant conflicts with CAS manifest.",
            event_id=event.event_id,
            event_tenant_id=event.tenant_id,
            manifest_tenant_id=tenant.tenant_id if tenant is not None else None,
        )

    return AuthorityReconciliationReport(
        status="pass",
        cas_ref=str(normalized_ref),
        durable_event_id=event.event_id,
    )


def reconcile_authority_event(
    *,
    artifact_store: Any,
    event_log: Any,
    event_id: str,
) -> AuthorityReconciliationReport:
    """Verify that one durable diagnostic event references a live CAS artifact."""

    event_rows = _capture_event_rows(event_log, event_id=event_id, limit=2)
    if event_rows.failure is not None:
        _fail_authority_event_log_read(
            event_rows.failure, event_id=event_id, operation="event lookup"
        )
    records = event_rows.value
    if len(records) != 1:
        _fail(
            "authority_event_collision" if records else "authority_orphan_cas",
            f"Durable diagnostic event {event_id!r} did not resolve exactly once.",
            event_id=event_id,
            record_count=len(records),
        )
    event = records[0].event
    normalized_ref = _normalize_cas_ref(event.payload_ref or "")
    if normalized_ref is None:
        _fail(
            "authority_ref_not_cas",
            f"Durable event {event.event_id} payload_ref is not a CAS ref.",
            event_id=event.event_id,
            payload_ref=event.payload_ref,
        )
    normalized_ref = cast("ArtifactID", normalized_ref)
    return reconcile_authority_ref(
        artifact_store=artifact_store,
        event_log=event_log,
        cas_ref=str(normalized_ref),
        expected_tenant_id=event.tenant_id,
        expected_cell_id=event.cell_id,
        expected_run_id=event.run_id,
        expected_job_id=event.job_id,
    )


def _assert_no_event_collision(records: list[Any], *, normalized_ref: ArtifactID | None) -> None:
    seen: dict[str, str | None] = {}
    for record in records:
        event = record.event
        event_ref = _normalize_cas_ref(event.payload_ref or "")
        if normalized_ref is not None and event_ref != normalized_ref:
            continue
        previous = seen.setdefault(event.event_id, event_ref)
        if previous != event_ref:
            _fail(
                "authority_event_collision",
                f"Diagnostic event {event.event_id} was reused for different payload refs.",
                event_id=event.event_id,
                first_payload_ref=previous,
                second_payload_ref=event_ref,
            )


def _assert_expected_identity(
    *,
    normalized_ref: str,
    manifest_tenant_id: str | None,
    manifest_cell_id: str | None,
    manifest_run_id: str | None,
    manifest_job_id: str | None,
    expected_tenant_id: str | None,
    expected_cell_id: str | None,
    expected_run_id: str | None,
    expected_job_id: str | None,
) -> None:
    conflicts: dict[str, tuple[str | None, str | None]] = {}
    for field, actual, expected in (
        ("tenant_id", manifest_tenant_id, expected_tenant_id),
        ("cell_id", manifest_cell_id, expected_cell_id),
        ("run_id", manifest_run_id, expected_run_id),
        ("job_id", manifest_job_id, expected_job_id),
    ):
        if expected is not None and actual != expected:
            conflicts[field] = (actual, expected)
    if conflicts:
        _fail(
            "authority_tenant_conflict",
            f"Authority identity conflict for {normalized_ref}.",
            cas_ref=normalized_ref,
            conflicts=conflicts,
        )


def _normalize_cas_ref(value: str) -> ArtifactID | None:
    text = str(value or "").strip()
    if not text:
        return None
    if text.startswith("sha256:"):
        try:
            return ArtifactID.model_validate(text)
        except (TypeError, ValueError):
            return None
    if text.startswith("cas://sha256/"):
        digest = text.removeprefix("cas://sha256/")
        try:
            return ArtifactID.model_validate(f"sha256:{digest}")
        except (TypeError, ValueError):
            return None
    return None


def _fail(code: str, message: str, **details: Any) -> None:
    if code not in RECONCILIATION_FAILURE_CODES:
        code = "authority_replay_drift_unexplained"
    raise AuthorityReconciliationError(code, message, details=details) from None


__all__ = [
    "AuthorityReconciliationError",
    "AuthorityReconciliationReport",
    "reconcile_authority_event",
    "reconcile_authority_ref",
    "resolve_authority_diagnostic_event_ref",
]
