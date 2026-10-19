"""CAS-backed persistence for entity-resolution candidates and overrides."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from polisyos.core.artifacts import ensure_ir_artifact_store as _ensure_ir_artifact_store
from polisyos.core.artifacts.manifest import ArtifactRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec
from polisyos.fabric.io.atomic import append_text_locked, file_lock
from polisyos.ir.artifacts.io import get_json_artifact

if TYPE_CHECKING:
    from polisyos.ir import ArtifactSelector

from .models import (
    EntityMatchBatch,
    EntityMatchCandidate,
    EntityOverrideAuditRecord,
    EntityOverrideEnvelope,
)

_MATCH_BATCH_KIND = "fabric.entity_resolution.candidate_batch"
_MATCH_OVERRIDE_KIND = "fabric.entity_resolution.override"
_MATCH_BATCH_SCHEMA = SchemaInfo(name="polisyos.fabric.EntityMatchBatch", version="1.0")
_MATCH_OVERRIDE_SCHEMA = SchemaInfo(name="polisyos.fabric.EntityMatchOverride", version="1.0")
_OVERRIDE_INDEX_NAME = "entity_resolution_overrides.jsonl"
_OVERRIDE_LOCK_NAME = "entity_resolution_overrides.lock"


def _require_entity_resolution_manifest(
    store: FileSystemCAS,
    selector: ArtifactSelector,
    *,
    kind: str,
    schema: SchemaInfo,
) -> None:
    """Require a selected CAS view to match the entity-resolution producer ABI."""
    ir_store = _ensure_ir_artifact_store(store)
    manifest = ir_store.get_manifest(selector)
    actual_schema = getattr(manifest, "artifact_schema", None)
    if (
        getattr(manifest, "kind", None) != kind
        or getattr(manifest, "media_type", None) != "application/json"
        or actual_schema is None
        or getattr(actual_schema, "name", None) != schema.name
        or str(getattr(actual_schema, "version", "")) != schema.version
    ):
        raise ValueError("Entity resolution artifact manifest is incompatible")


def _selected_ref_fields(ref: ArtifactRef) -> dict[str, str]:
    """Project the exact selected artifact view into the append-only audit index."""
    kind = ref.kind
    media_type = ref.media_type
    profile = ref.manifest_profile_sha256
    if not kind or not media_type or not profile:
        raise ValueError("Entity resolution write did not return a complete selected artifact view")
    return {
        "artifact_id": str(ref.artifact_id),
        "kind": kind,
        "media_type": media_type,
        "manifest_profile_sha256": profile,
    }


class EntityMatchStore:
    """Persist candidate matches and operator overrides through CAS."""

    def __init__(self, store: FileSystemCAS) -> None:
        self._store = store

    def persist_candidates(
        self,
        candidates: list[EntityMatchCandidate],
        *,
        method: str,
        metadata: dict[str, str] | None = None,
    ) -> ArtifactRef:
        batch = EntityMatchBatch(
            candidates=candidates,
            method=method,
            metadata=metadata or {},
        )
        return self._store.put_json(
            batch.model_dump(mode="json"),
            opts=PutOptions(
                kind=_MATCH_BATCH_KIND,
                media_type="application/json",
                schema=_MATCH_BATCH_SCHEMA,
            ),
            canon_spec=CanonSpec(forbid_floats=False),
            return_selected_profile=True,
        )

    def load_candidates(self, artifact_id: ArtifactSelector) -> EntityMatchBatch:
        _require_entity_resolution_manifest(
            self._store,
            artifact_id,
            kind=_MATCH_BATCH_KIND,
            schema=_MATCH_BATCH_SCHEMA,
        )
        payload = get_json_artifact(_ensure_ir_artifact_store(self._store), artifact_id)
        return EntityMatchBatch.model_validate(payload)

    def persist_override(
        self,
        candidate: EntityMatchCandidate,
        *,
        status: Literal["accepted", "rejected"],
        actor: str = "",
        reason: str = "",
        provenance_ref: str | None = None,
        merge_governance_ref: str | None = None,
        canonical_write: bool = False,
    ) -> ArtifactRef:
        """Persist an override without mutating canonical facts.

        Accepted overrides require merge-governance evidence before they can be
        used by any later canonical-write workflow. Rejections remain reversible
        but still require actor and reason for auditability.
        """

        if not actor.strip():
            raise ValueError("entity override requires actor")
        if not reason.strip():
            raise ValueError("entity override requires reason")
        if status == "accepted" or canonical_write:
            if not provenance_ref:
                raise ValueError("accepted entity override requires provenance_ref")
            if not merge_governance_ref:
                raise ValueError("accepted entity override requires merge_governance_ref")
        updated = candidate.model_copy(
            update={
                "override_status": status,
                "override_provenance_ref": provenance_ref,
                "merge_governance_ref": merge_governance_ref,
            }
        )
        audit = EntityOverrideAuditRecord(
            override_id=f"entity_override_{uuid.uuid4().hex}",
            match_id=candidate.match_id,
            status=status,
            actor=actor,
            reason=reason,
            provenance_ref=provenance_ref,
            merge_governance_ref=merge_governance_ref,
            canonical_write=canonical_write,
            previous_status=candidate.override_status,
        )
        envelope = EntityOverrideEnvelope(candidate=updated, audit=audit)
        ref = self._store.put_json(
            envelope.model_dump(mode="json"),
            opts=PutOptions(
                kind=_MATCH_OVERRIDE_KIND,
                media_type="application/json",
                schema=_MATCH_OVERRIDE_SCHEMA,
            ),
            canon_spec=CanonSpec(forbid_floats=False),
            return_selected_profile=True,
        )
        append_text_locked(
            _override_index_path(self._store),
            json.dumps(
                {
                    **_selected_ref_fields(ref),
                    "override_id": audit.override_id,
                    "match_id": audit.match_id,
                    "status": audit.status,
                    "actor": audit.actor,
                    "created_at": audit.created_at.isoformat(),
                },
                sort_keys=True,
            )
            + "\n",
            lock_path=_override_lock_path(self._store),
        )
        return ref

    def load_override(self, artifact_id: ArtifactSelector) -> EntityOverrideEnvelope:
        _require_entity_resolution_manifest(
            self._store,
            artifact_id,
            kind=_MATCH_OVERRIDE_KIND,
            schema=_MATCH_OVERRIDE_SCHEMA,
        )
        payload = get_json_artifact(_ensure_ir_artifact_store(self._store), artifact_id)
        return EntityOverrideEnvelope.model_validate(payload)

    def list_override_audit(self) -> list[tuple[str, EntityOverrideAuditRecord]]:
        index_path = _override_index_path(self._store)
        if not index_path.exists():
            return []
        rows: list[tuple[str, EntityOverrideAuditRecord]] = []
        with (
            file_lock(_override_lock_path(self._store)),
            index_path.open(
                "r",
                encoding="utf-8",
            ) as handle,
        ):
            for line in handle:
                raw = line.strip()
                if not raw:
                    continue
                record = json.loads(raw)
                artifact_id = str(record["artifact_id"])
                view_fields = {"kind", "media_type", "manifest_profile_sha256"}
                present_view_fields = view_fields & set(record)
                if present_view_fields and present_view_fields != view_fields:
                    raise ValueError("Entity override history contains an incomplete artifact view")
                selector = (
                    {
                        "artifact_id": artifact_id,
                        "kind": record["kind"],
                        "media_type": record["media_type"],
                        "manifest_profile_sha256": record["manifest_profile_sha256"],
                    }
                    if present_view_fields
                    else artifact_id
                )
                rows.append((artifact_id, self.load_override(selector).audit))
        rows.sort(key=lambda item: (item[1].created_at, item[0]))
        return rows


def _override_index_path(store: FileSystemCAS) -> Path:
    return Path(store.root) / "entity_resolution" / _OVERRIDE_INDEX_NAME


def _override_lock_path(store: FileSystemCAS) -> Path:
    return Path(store.root) / "entity_resolution" / _OVERRIDE_LOCK_NAME


__all__ = ["EntityMatchStore"]
