"""CAS-backed persistence for entity-resolution candidates and overrides."""

from __future__ import annotations

from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec
from polisyos.ir.artifacts.io import get_json_artifact

from .models import EntityMatchBatch, EntityMatchCandidate

_MATCH_BATCH_KIND = "fabric.entity_resolution.candidate_batch"
_MATCH_OVERRIDE_KIND = "fabric.entity_resolution.override"
_MATCH_BATCH_SCHEMA = SchemaInfo(name="polisyos.fabric.EntityMatchBatch", version="1.0")
_MATCH_OVERRIDE_SCHEMA = SchemaInfo(name="polisyos.fabric.EntityMatchOverride", version="1.0")


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
        status: str,
        provenance_ref: str | None = None,
    ):
        updated = candidate.model_copy(
            update={
                "override_status": status,
                "override_provenance_ref": provenance_ref,
            }
        )
        return self._store.put_json(
            updated.model_dump(mode="json"),
            opts=PutOptions(
                kind=_MATCH_OVERRIDE_KIND,
                media_type="application/json",
                schema=_MATCH_OVERRIDE_SCHEMA,
            ),
            canon_spec=CanonSpec(forbid_floats=False),
        )


__all__ = ["EntityMatchStore"]
