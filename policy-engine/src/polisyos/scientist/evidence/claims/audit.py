"""CAS persistence and audit helpers for Claim Ledger v2."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from pydantic import ValidationError

from polisyos.core import artifacts as core_artifacts
from polisyos.core.artifacts.manifest import ArtifactRef, InputRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec, from_canonical_bytes, to_canonical_bytes
from polisyos.scientist.evidence.claims.ledger import CLAIM_LEDGER_KIND
from polisyos.scientist.evidence.claims.lifecycle import (
    AppendOnlyClaimLedger,
    build_initial_append_only_ledger,
)
from polisyos.scientist.evidence.claims.models import ClaimLedger

ArtifactStore = core_artifacts.ArtifactStore

CLAIM_LEDGER_V2_KIND = "scientist.claim_ledger_v2"
CLAIM_LEDGER_V2_SCHEMA_NAME = "polisyos.scientist.claims.AppendOnlyClaimLedger"
CLAIM_LEDGER_V2_SCHEMA_VERSION = "2.0"


def _claim_ledger_v2_inputs(
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


def _persist_append_only_claim_ledger(
    store: FileSystemCAS,
    ledger: AppendOnlyClaimLedger,
    *,
    inputs: list[InputRef] | None = None,
) -> ArtifactRef:
    """Persist an append-only Claim Ledger v2 artifact."""

    manifest_inputs = (
        list(inputs)
        if inputs is not None
        else _claim_ledger_v2_inputs(base_ledger_ref=ledger.base_ledger_ref)
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


def _load_append_only_claim_ledger(
    store: ArtifactStore,
    ref: ArtifactRef,
) -> AppendOnlyClaimLedger:
    """Load one exact-profile append-only Claim Ledger v2 artifact."""

    raw = store.get_bytes(ref.artifact_id)
    manifest = store.get_manifest(ref.artifact_id)
    report = store.verify(ref.artifact_id)
    expected_schema = SchemaInfo(
        name=CLAIM_LEDGER_V2_SCHEMA_NAME,
        version=CLAIM_LEDGER_V2_SCHEMA_VERSION,
    )
    if (
        not report.ok
        or ref.kind != CLAIM_LEDGER_V2_KIND
        or ref.kind != manifest.kind
        or ref.media_type != "application/json"
        or ref.media_type != manifest.media_type
        or manifest.artifact_schema != expected_schema
        or str(ref.artifact_id) != str(manifest.artifact_id)
    ):
        raise ValueError("claim_ledger_v2_profile_mismatch")
    ledger = AppendOnlyClaimLedger.model_validate(from_canonical_bytes(raw))
    if to_canonical_bytes(ledger, CanonSpec(forbid_floats=False)) != raw:
        raise ValueError("claim_ledger_v2_canonical_mismatch")
    return ledger


def _load_claim_ledger_as_append_only(
    store: ArtifactStore,
    ref: ArtifactRef,
    *,
    actor_id: str = "legacy_loader",
    reason: str = "Loaded legacy ClaimLedger without lifecycle events.",
) -> AppendOnlyClaimLedger:
    """Load v2 ledgers or wrap legacy v1 ledgers as `legacy_no_events` compatible v2."""

    try:
        return _load_append_only_claim_ledger(store, ref)
    except (ValidationError, ValueError):
        from polisyos.scientist.evidence.claims.ledger import _load_claim_ledger

        legacy = _load_claim_ledger(store, ref)
        return build_initial_append_only_ledger(
            legacy,
            actor_id=actor_id,
            reason=reason,
            base_ledger_ref=ref if ref.kind == CLAIM_LEDGER_KIND else None,
            retention_policy={"legacy_status": "legacy_no_events"},
        )


def _append_only_audit_summary(ledger: AppendOnlyClaimLedger) -> dict[str, Any]:
    """Return compact audit metadata for packet and reviewer surfaces."""

    actor_ids = sorted({event.actor_id for event in ledger.events})
    return {
        "schema_version": ledger.schema_version,
        "run_id": ledger.run_id,
        "event_count": len(ledger.events),
        "first_event_at": (ledger.events[0].occurred_at.isoformat() if ledger.events else None),
        "latest_event_at": (ledger.events[-1].occurred_at.isoformat() if ledger.events else None),
        "actor_ids": actor_ids,
        "append_only_ordered": ledger.events
        == sorted(ledger.events, key=lambda event: event.occurred_at),
        "retention_policy": dict(ledger.retention_policy),
    }


def _retention_window_for_export(ledger: AppendOnlyClaimLedger) -> dict[str, Any]:
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
]
