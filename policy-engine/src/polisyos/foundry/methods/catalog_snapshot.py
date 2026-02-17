from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from polisyos.core.artifacts.manifest import InputRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec
from polisyos.core.canon import truncated_hash
from polisyos.core.contracts.execution_plan import (
    MethodCatalogEntry,
    MethodCatalogSnapshot,
    MethodCatalogSnapshotRef,
)
from polisyos.foundry.methods.registry import MethodRegistry


def build_method_catalog_snapshot(
    *,
    run_id: str | None = None,
    registry: MethodRegistry | None = None,
) -> MethodCatalogSnapshot:
    reg = registry or MethodRegistry.get_instance()
    signatures = reg.list_all()
    entries: list[MethodCatalogEntry] = []
    for sig in signatures:
        entry = reg.get_entry(sig.fqn)
        tags: list[str] = []
        deprecations: list[str] = []
        incompatibilities: list[str] = []
        if entry is not None:
            tags = sorted(str(tag) for tag in entry.metadata.tags)
            deprecations = sorted(tag for tag in tags if tag.startswith("deprecated"))
            incompatibilities = sorted(str(item) for item in entry.signature.conflicts_with)
        entries.append(
            MethodCatalogEntry(
                fqn=sig.fqn,
                namespace=sig.namespace,
                name=sig.name,
                version=sig.version,
                backend=sig.backend.value,
                input_slots=[
                    {
                        "name": slot.name,
                        "slot_type": slot.slot_type.name.lower(),
                        "unit": slot.unit.symbol,
                        "dimension": slot.unit.dimension,
                        "shape": list(slot.shape),
                    }
                    for slot in sorted(sig.input_slots, key=lambda item: item.name)
                ],
                output_slots=[
                    {
                        "name": slot.name,
                        "slot_type": slot.slot_type.name.lower(),
                        "unit": slot.unit.symbol,
                        "dimension": slot.unit.dimension,
                        "shape": list(slot.shape),
                    }
                    for slot in sorted(sig.output_slots, key=lambda item: item.name)
                ],
                parameters=[
                    {
                        "name": param.name,
                        "default": _jsonable(param.default),
                        "is_static": bool(param.is_static),
                        "bounds": list(param.bounds),
                    }
                    for param in sig.parameters
                ],
                requires=sorted(str(item) for item in sig.requires),
                conflicts_with=sorted(str(item) for item in sig.conflicts_with),
                incompatibilities=incompatibilities,
                deprecations=deprecations,
                tags=tags,
            )
        )
    snapshot_payload = {
        "method_count": len(entries),
        "entries": [entry.model_dump(mode="json") for entry in entries],
    }
    snapshot_id = f"method_catalog_{truncated_hash(str(snapshot_payload), length=16)}"
    return MethodCatalogSnapshot(
        snapshot_id=snapshot_id,
        run_id=run_id,
        generated_at=datetime.now(timezone.utc),
        entries=entries,
        notes=[f"method_count:{len(entries)}"],
    )


def persist_method_catalog_snapshot(
    store: FileSystemCAS,
    snapshot: MethodCatalogSnapshot,
    *,
    inputs: list[InputRef] | None = None,
) -> MethodCatalogSnapshotRef:
    payload_ref = store.put_json(
        snapshot,
        PutOptions(
            kind="foundry.method_catalog_snapshot",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.MethodCatalogSnapshot", version="1.0"),
            inputs=list(inputs or []),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return MethodCatalogSnapshotRef(artifact_id=payload_ref.artifact_id)


def _jsonable(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    return str(value)


__all__ = [
    "build_method_catalog_snapshot",
    "persist_method_catalog_snapshot",
]
