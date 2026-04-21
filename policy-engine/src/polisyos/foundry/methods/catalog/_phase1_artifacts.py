"""Shared Phase 1 artifact helpers for catalog methods."""
from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from polisyos.ir.artifacts.contracts import ArtifactStore


def resolve_artifact_store(
    state: Any,
    params: Mapping[str, Any] | None = None,
) -> "ArtifactStore | None":
    """Resolve an artifact store from params or mapping-like state."""

    for container in (params, state):
        if not isinstance(container, Mapping):
            continue
        candidate = container.get("artifact_store")
        if hasattr(candidate, "put_json") and hasattr(candidate, "get_bytes"):
            return candidate
    return None


def resolve_dataset_context(
    state: Any,
    params: Mapping[str, Any] | None = None,
) -> dict[str, str | None]:
    """Best-effort dataset/source metadata lookup shared by Phase 1 gates."""

    metadata_sources: list[Mapping[str, Any]] = []
    for container in (params, state):
        if not isinstance(container, Mapping):
            continue
        metadata_sources.append(container)
        nested_metadata = container.get("metadata")
        if isinstance(nested_metadata, Mapping):
            metadata_sources.append(nested_metadata)
        for nested_key in ("dataset_metadata", "source_metadata", "data_quality_report"):
            nested = container.get(nested_key)
            if isinstance(nested, Mapping):
                metadata_sources.append(nested)
                nested_meta = nested.get("metadata")
                if isinstance(nested_meta, Mapping):
                    metadata_sources.append(nested_meta)

    dataset_id = _first_string(
        metadata_sources,
        "dataset_id",
        "resolved_dataset_id",
        "request_dataset_id",
        "binding_dataset_id",
        "catalog_dataset_id",
        "source_dataset_id",
    )
    data_origin = _first_string(metadata_sources, "data_origin", "origin", "source_origin")
    source_type = _first_string(metadata_sources, "source_type", "source", "profile_id")
    source_portal = _first_string(metadata_sources, "source_portal", "portal", "publisher")
    return {
        "dataset_id": dataset_id,
        "data_origin": data_origin,
        "source_type": source_type,
        "source_portal": source_portal,
    }


def is_government_dataset(
    dataset_context: Mapping[str, str | None],
    *,
    flagship_dataset_ids: set[str] | None = None,
) -> bool:
    """Classify whether a dataset should be subject to the strict Phase 1 gate."""

    dataset_id = str(dataset_context.get("dataset_id") or "").strip()
    if dataset_id and flagship_dataset_ids and dataset_id in flagship_dataset_ids:
        return True

    haystacks = (
        str(dataset_context.get("data_origin") or "").strip().lower(),
        str(dataset_context.get("source_type") or "").strip().lower(),
        str(dataset_context.get("source_portal") or "").strip().lower(),
        dataset_id.lower(),
    )
    government_tokens = (
        "government",
        "gov",
        "data.gov",
        "data_gov_",
        "eurostat",
        "worldbank",
        "who",
        "oecd",
        "unesco",
        "unpd",
        "ukons",
    )
    return any(token in haystack for haystack in haystacks for token in government_tokens if haystack)


def _first_string(
    sources: list[Mapping[str, Any]],
    *keys: str,
) -> str | None:
    for source in sources:
        for key in keys:
            candidate = source.get(key)
            if candidate is None:
                continue
            text = str(candidate).strip()
            if text:
                return text
    return None


__all__ = ["is_government_dataset", "resolve_artifact_store", "resolve_dataset_context"]
