"""Runtime control-plane artifact helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.runtime.http.services import _control_contracts as _contracts


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


def _resolve_curated_dir() -> Path:
    candidates = (
        Path("data/curated"),
        Path("policy-engine/data/curated"),
    )
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


__all__ = [
    "_artifact_ref_from_summary_payload",
    "_make_artifact_ref",
    "_resolve_curated_dir",
    "_typed_artifact_ref",
]
