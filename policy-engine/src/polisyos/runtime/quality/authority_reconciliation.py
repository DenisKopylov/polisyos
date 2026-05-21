"""Reconcile runtime CAS authority artifacts with durable diagnostic events."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.runtime.quality.diagnostic_events import RECONCILIATION_FAILURE_CODES


@dataclass(frozen=True, slots=True)
class AuthorityReconciliationReport:
    """Result of one CAS/event authority cross-check."""

    status: str
    cas_ref: str
    durable_event_id: str | None = None
    findings: tuple[dict[str, Any], ...] = ()


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


def reconcile_authority_ref(
    *,
    artifact_store: Any,
    event_log: Any,
    cas_ref: str,
    expected_tenant_id: str | None = None,
    expected_cell_id: str | None = None,
    expected_run_id: str | None = None,
    expected_job_id: str | None = None,
) -> AuthorityReconciliationReport:
    """Verify that one runtime authority CAS ref has a matching durable event."""

    normalized_ref = _normalize_cas_ref(cas_ref)
    if normalized_ref is None:
        _fail(
            "authority_ref_not_cas",
            f"Authority ref is not a CAS ref: {cas_ref!r}.",
            ref=cas_ref,
        )

    assert normalized_ref is not None
    if not artifact_store.has(normalized_ref):
        _fail("authority_cas_missing", f"CAS artifact is missing: {normalized_ref}.")

    manifest = artifact_store.get_manifest(normalized_ref)
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

    records = _matching_event_records(
        event_log,
        normalized_ref=normalized_ref,
        run_id=closure.run_id if closure is not None else None,
        job_id=closure.job_id if closure is not None else None,
    )
    if not records:
        _fail(
            "authority_orphan_cas",
            f"CAS artifact {normalized_ref} has no durable diagnostic event.",
            cas_ref=normalized_ref,
            diagnostic_event_ref=authority.diagnostic_event_ref,
        )
    _assert_no_event_collision(records, normalized_ref=normalized_ref)
    event = records[0].event
    event_ref = _normalize_cas_ref(event.payload_ref or "")
    if event_ref != normalized_ref:
        _fail(
            "authority_payload_mismatch",
            f"Durable event {event.event_id} points at {event.payload_ref}, not {normalized_ref}.",
            event_id=event.event_id,
            event_payload_ref=event.payload_ref,
            cas_ref=normalized_ref,
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
        cas_ref=normalized_ref,
        durable_event_id=event.event_id,
    )


def reconcile_authority_event(
    *,
    artifact_store: Any,
    event_log: Any,
    event_id: str,
) -> AuthorityReconciliationReport:
    """Verify that one durable diagnostic event references a live CAS artifact."""

    records = event_log.list_events(event_id=event_id, limit=100)
    if not records:
        _fail(
            "authority_orphan_cas",
            f"Durable diagnostic event {event_id!r} was not found.",
            event_id=event_id,
        )
    _assert_no_event_collision(records, normalized_ref=None)
    event = records[0].event
    normalized_ref = _normalize_cas_ref(event.payload_ref or "")
    if normalized_ref is None:
        _fail(
            "authority_ref_not_cas",
            f"Durable event {event.event_id} payload_ref is not a CAS ref.",
            event_id=event.event_id,
            payload_ref=event.payload_ref,
        )
    if not artifact_store.has(normalized_ref):
        _fail(
            "authority_cas_missing",
            f"Durable event {event.event_id} references missing CAS artifact {normalized_ref}.",
            event_id=event.event_id,
            cas_ref=normalized_ref,
        )
    return reconcile_authority_ref(
        artifact_store=artifact_store,
        event_log=event_log,
        cas_ref=normalized_ref,
        expected_tenant_id=event.tenant_id,
        expected_cell_id=event.cell_id,
        expected_run_id=event.run_id,
        expected_job_id=event.job_id,
    )


def _matching_event_records(
    event_log: Any,
    *,
    normalized_ref: str,
    run_id: str | None,
    job_id: str | None,
) -> list[Any]:
    records = event_log.list_events(run_id=run_id, job_id=job_id, limit=1000)
    return [
        record
        for record in records
        if _normalize_cas_ref(record.event.payload_ref or "") == normalized_ref
        or normalized_ref
        in {
            ref
            for raw_ref in record.event.artifact_refs
            if (ref := _normalize_cas_ref(raw_ref)) is not None
        }
    ]


def _assert_no_event_collision(records: list[Any], *, normalized_ref: str | None) -> None:
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


def _normalize_cas_ref(value: str) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    if text.startswith("sha256:"):
        try:
            return str(ArtifactID.model_validate(text))
        except Exception:
            return None
    if text.startswith("cas://sha256/"):
        digest = text.removeprefix("cas://sha256/")
        try:
            return str(ArtifactID.model_validate(f"sha256:{digest}"))
        except Exception:
            return None
    return None


def _fail(code: str, message: str, **details: Any) -> None:
    if code not in RECONCILIATION_FAILURE_CODES:
        code = "authority_replay_drift_unexplained"
    raise AuthorityReconciliationError(code, message, details=details)


__all__ = [
    "AuthorityReconciliationError",
    "AuthorityReconciliationReport",
    "reconcile_authority_event",
    "reconcile_authority_ref",
]

