"""Public services artifact inspector module API."""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from polisyos.common.logger import get_logger
from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.contracts.runtime import (
    ArtifactContentPreview,
    ArtifactLineageView,
    ArtifactManifestView,
    ArtifactSchemaView,
    PreviewMode,
)

from .lineage import LineageService

RedactionHook = Callable[[Any, PreviewMode], Any]
_SENSITIVE_KIND_MARKERS = ("secret", "token", "credential", "password", "key_material")
logger = get_logger(__name__)


class ArtifactInspectorService:
    """Artifact inspector service implementation."""
    def __init__(
        self,
        *,
        store: FileSystemCAS,
        lineage_service: LineageService,
        default_max_preview_bytes: int = 64 * 1024,
        redaction_hooks: dict[str, RedactionHook] | None = None,
    ) -> None:
        self._store = store
        self._lineage_service = lineage_service
        self._default_max_preview_bytes = max(default_max_preview_bytes, 1024)
        self._redaction_hooks = dict(redaction_hooks or {})

    def get_manifest_view(self, artifact_id: ArtifactID) -> ArtifactManifestView:
        manifest = self._store.get_manifest(artifact_id)
        schema = manifest.artifact_schema
        producer = manifest.producer
        return ArtifactManifestView(
            artifact_id=str(manifest.artifact_id),
            kind=manifest.kind,
            media_type=manifest.media_type,
            byte_size=int(manifest.byte_size),
            created_at=manifest.created_at,
            schema_name=schema.name if schema is not None else None,
            schema_version=schema.version if schema is not None else None,
            producer_component=str(producer.component) if producer is not None else None,
            producer_version=producer.version if producer is not None else None,
            inputs=list(manifest.inputs),
            integrity_sha256=manifest.integrity.sha256,
        )

    def get_content_preview(
        self,
        artifact_id: ArtifactID,
        *,
        max_bytes: int | None = None,
    ) -> ArtifactContentPreview:
        manifest = self._store.get_manifest(artifact_id)
        data = self._store.get_bytes(artifact_id)
        byte_size = len(data)
        preview_limit = _normalize_preview_limit(
            max_bytes,
            default_value=self._default_max_preview_bytes,
        )
        truncated = byte_size > preview_limit
        preview_bytes = data[:preview_limit]

        mode: PreviewMode = "binary"
        preview: Any = None

        if _is_json_media_type(manifest.media_type) and not truncated:
            try:
                payload = from_canonical_bytes(data)
                mode = "json"
                preview = payload
            except (TypeError, ValueError) as exc:
                logger.debug(
                    "Failed to decode JSON artifact content preview for %s: %s",
                    artifact_id,
                    exc,
                )
                text = _decode_text(preview_bytes)
                if text is not None:
                    mode = "text"
                    preview = text
        elif _is_text_media_type(manifest.media_type):
            text = _decode_text(preview_bytes)
            if text is not None:
                mode = "text"
                preview = text
        elif not truncated:
            text = _decode_text(preview_bytes)
            if text is not None:
                mode = "text"
                preview = text

        if preview is None:
            mode = "binary"
            preview = preview_bytes.hex()

        preview = _apply_redaction_hook(
            hooks=self._redaction_hooks,
            artifact_kind=manifest.kind,
            mode=mode,
            preview=preview,
        )

        return ArtifactContentPreview(
            artifact_id=str(artifact_id),
            kind=manifest.kind,
            media_type=manifest.media_type,
            mode=mode,
            size_bytes=byte_size,
            max_bytes=preview_limit,
            truncated=truncated,
            preview=preview,
        )

    def get_schema_view(self, artifact_id: ArtifactID) -> ArtifactSchemaView:
        manifest = self._store.get_manifest(artifact_id)
        schema = manifest.artifact_schema

        top_keys: list[str] = []
        if _is_json_media_type(manifest.media_type):
            try:
                payload = from_canonical_bytes(self._store.get_bytes(artifact_id))
                if isinstance(payload, dict):
                    top_keys = sorted(str(key) for key in payload)
            except (TypeError, ValueError) as exc:
                logger.debug(
                    "Failed to load schema preview payload for %s: %s",
                    artifact_id,
                    exc,
                )
                top_keys = []

        return ArtifactSchemaView(
            artifact_id=str(artifact_id),
            kind=manifest.kind,
            media_type=manifest.media_type,
            schema_name=schema.name if schema is not None else None,
            schema_version=schema.version if schema is not None else None,
            top_level_keys=top_keys,
        )

    def get_lineage_view(
        self,
        artifact_id: ArtifactID,
        *,
        max_depth: int | None = None,
        max_nodes: int | None = None,
    ) -> ArtifactLineageView:
        return self._lineage_service.build_for_artifact_ids(
            [artifact_id],
            max_depth=max_depth,
            max_nodes=max_nodes,
        )


def _normalize_preview_limit(max_bytes: int | None, *, default_value: int) -> int:
    if max_bytes is None:
        return default_value
    return min(max(int(max_bytes), 1024), 2_000_000)


def _decode_text(payload: bytes) -> str | None:
    try:
        return payload.decode("utf-8")
    except UnicodeDecodeError:
        return None


def _is_json_media_type(media_type: str) -> bool:
    normalized = media_type.lower()
    return normalized == "application/json" or normalized.endswith("+json")


def _is_text_media_type(media_type: str) -> bool:
    normalized = media_type.lower()
    return normalized.startswith("text/")


def _apply_redaction_hook(
    *,
    hooks: dict[str, RedactionHook],
    artifact_kind: str,
    mode: PreviewMode,
    preview: Any,
) -> Any:
    lowered_kind = artifact_kind.lower()
    if any(marker in lowered_kind for marker in _SENSITIVE_KIND_MARKERS):
        return "[REDACTED]"

    hook = hooks.get(artifact_kind) or hooks.get("*")
    if hook is None:
        return preview
    try:
        return hook(preview, mode)
    except (AttributeError, RuntimeError, TypeError, ValueError) as exc:
        logger.debug(
            "Redaction hook failed for kind=%s mode=%s: %s", artifact_kind, mode, exc
        )
        return preview
