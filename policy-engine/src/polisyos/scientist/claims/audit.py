"""CAS persistence and audit helpers for Claim Ledger v2."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from pydantic import ValidationError

from polisyos.core.artifacts.manifest import ArtifactRef, InputRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec, from_canonical_bytes
from polisyos.scientist.claims.ledger import CLAIM_LEDGER_KIND
from polisyos.scientist.claims.lifecycle import (
    AppendOnlyClaimLedger,
    ClaimLifecycleEvent,
    append_lifecycle_event,
    build_initial_append_only_ledger,
)
from polisyos.scientist.claims.models import ClaimLedger

CLAIM_LEDGER_V2_KIND = "scientist.claim_ledger_v2"
CLAIM_LEDGER_V2_SCHEMA_NAME = "polisyos.scientist.claims.AppendOnlyClaimLedger"
CLAIM_LEDGER_V2_SCHEMA_VERSION = "2.0"


def claim_ledger_v2_inputs(
    *,
    base_ledger_ref: ArtifactRef | None = None,
    source_artifact_refs: Iterable[ArtifactRef] = (),
) -> list[InputRef]:
    """Build manifest inputs for the append-only claim ledger sidecar."""

    inputs: list[InputRef] = []
    seen: set[tuple[str, str]] = set()

    def add(ref: ArtifactRef, role: str) -> None:
        key = (str(ref.artifact_id), role)
        if key in seen:
            return
        seen.add(key)
        inputs.append(InputRef(artifact_id=ref.artifact_id, role=role))

    if base_ledger_ref is not None:
        add(base_ledger_ref, "base_claim_ledger")
    for index, ref in enumerate(source_artifact_refs):
        add(ref, f"claim_lifecycle_source[{index}]")
    return inputs


def persist_append_only_claim_ledger(
    store: FileSystemCAS,
    ledger: AppendOnlyClaimLedger,
    *,
    inputs: list[InputRef] | None = None,
) -> ArtifactRef:
    """Persist an append-only Claim Ledger v2 artifact."""

    manifest_inputs = (
        list(inputs)
        if inputs is not None
        else claim_ledger_v2_inputs(base_ledger_ref=ledger.base_ledger_ref)
    )
    return store.put_json(
        ledger,
        PutOptions(
            kind=CLAIM_LEDGER_V2_KIND,
            media_type="application/json",
            schema=SchemaInfo(
                name=CLAIM_LEDGER_V2_SCHEMA_NAME,
                version=CLAIM_LEDGER_V2_SCHEMA_VERSION,
            ),
            inputs=manifest_inputs or None,
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )


def load_append_only_claim_ledger(
    store: FileSystemCAS,
    ref: ArtifactRef,
) -> AppendOnlyClaimLedger:
    """Load a persisted append-only Claim Ledger v2 artifact."""

    payload = from_canonical_bytes(store.get_bytes(ref.artifact_id))
    return AppendOnlyClaimLedger.model_validate(payload)


def load_claim_ledger_as_append_only(
    store: FileSystemCAS,
    ref: ArtifactRef,
    *,
    actor_id: str = "legacy_loader",
    reason: str = "Loaded legacy ClaimLedger without lifecycle events.",
) -> AppendOnlyClaimLedger:
    """Load v2 ledgers or wrap legacy v1 ledgers as `legacy_no_events` compatible v2."""

    payload = from_canonical_bytes(store.get_bytes(ref.artifact_id))
    try:
        return AppendOnlyClaimLedger.model_validate(payload)
    except ValidationError:
        legacy = ClaimLedger.model_validate(payload)
        return build_initial_append_only_ledger(
            legacy,
            actor_id=actor_id,
            reason=reason,
            base_ledger_ref=ref if ref.kind == CLAIM_LEDGER_KIND else None,
            retention_policy={"legacy_status": "legacy_no_events"},
        )


def append_and_persist_claim_event(
    store: FileSystemCAS,
    ledger: AppendOnlyClaimLedger,
    event: ClaimLifecycleEvent,
    *,
    previous_ledger_ref: ArtifactRef | None = None,
) -> tuple[AppendOnlyClaimLedger, ArtifactRef]:
    """Append one event and persist the resulting immutable ledger artifact."""

    updated = append_lifecycle_event(ledger, event)
    ref = persist_append_only_claim_ledger(
        store,
        updated,
        inputs=claim_ledger_v2_inputs(
            base_ledger_ref=previous_ledger_ref or ledger.base_ledger_ref
        ),
    )
    return updated, ref


def append_only_audit_summary(ledger: AppendOnlyClaimLedger) -> dict[str, Any]:
    """Return compact audit metadata for packet and reviewer surfaces."""

    actor_ids = sorted({event.actor_id for event in ledger.events})
    return {
        "schema_version": ledger.schema_version,
        "run_id": ledger.run_id,
        "event_count": len(ledger.events),
        "first_event_at": (
            ledger.events[0].occurred_at.isoformat() if ledger.events else None
        ),
        "latest_event_at": (
            ledger.events[-1].occurred_at.isoformat() if ledger.events else None
        ),
        "actor_ids": actor_ids,
        "append_only_ordered": ledger.events
        == sorted(ledger.events, key=lambda event: event.occurred_at),
        "retention_policy": dict(ledger.retention_policy),
    }


def retention_window_for_export(ledger: AppendOnlyClaimLedger) -> dict[str, Any]:
    """Return the bounded-retention export window without mutating the ledger."""

    max_events = ledger.retention_policy.get("max_events")
    if not isinstance(max_events, int) or max_events < 1:
        return {
            "retention_applied": False,
            "included_event_ids": [event.event_id for event in ledger.events],
            "omitted_event_ids": [],
        }
    included = ledger.events[-max_events:]
    omitted = ledger.events[: max(0, len(ledger.events) - max_events)]
    return {
        "retention_applied": len(omitted) > 0,
        "included_event_ids": [event.event_id for event in included],
        "omitted_event_ids": [event.event_id for event in omitted],
    }


__all__ = [
    "CLAIM_LEDGER_V2_KIND",
    "CLAIM_LEDGER_V2_SCHEMA_NAME",
    "CLAIM_LEDGER_V2_SCHEMA_VERSION",
    "append_and_persist_claim_event",
    "append_only_audit_summary",
    "claim_ledger_v2_inputs",
    "load_append_only_claim_ledger",
    "load_claim_ledger_as_append_only",
    "persist_append_only_claim_ledger",
    "retention_window_for_export",
]
