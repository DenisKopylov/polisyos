"""CAS-backed persistence for entity-resolution candidates and overrides."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Literal

from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec
from polisyos.fabric.io.atomic import append_text_locked, file_lock
from polisyos.ir.artifacts.io import get_json_artifact

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
    ):
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
        )

    def load_candidates(self, artifact_id) -> EntityMatchBatch:
        payload = get_json_artifact(self._store, artifact_id)
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
    ):
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
        )
        append_text_locked(
            _override_index_path(self._store),
            json.dumps(
                {
                    "artifact_id": str(ref.artifact_id),
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

    def load_override(self, artifact_id) -> EntityOverrideEnvelope:
        payload = get_json_artifact(self._store, artifact_id)
        return EntityOverrideEnvelope.model_validate(payload)

    def list_override_audit(self) -> list[tuple[str, EntityOverrideAuditRecord]]:
        index_path = _override_index_path(self._store)
        if not index_path.exists():
            return []
        rows: list[tuple[str, EntityOverrideAuditRecord]] = []
        with file_lock(_override_lock_path(self._store)), index_path.open(
            "r",
            encoding="utf-8",
        ) as handle:
            for line in handle:
                raw = line.strip()
                if not raw:
                    continue
                artifact_id = str(json.loads(raw)["artifact_id"])
                rows.append((artifact_id, self.load_override(artifact_id).audit))
        rows.sort(key=lambda item: (item[1].created_at, item[0]))
        return rows


def _override_index_path(store: FileSystemCAS) -> Path:
    return Path(store.root) / "entity_resolution" / _OVERRIDE_INDEX_NAME


def _override_lock_path(store: FileSystemCAS) -> Path:
    return Path(store.root) / "entity_resolution" / _OVERRIDE_LOCK_NAME


__all__ = ["EntityMatchStore"]
