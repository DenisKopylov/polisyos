"""Project CAS artifacts into redacted HTTP inspection views.

`ArtifactInspectorService` is a read-only runtime boundary: it loads artifact
manifests and payload bytes from CAS, applies preview limits and secret
redaction, and delegates lineage expansion to `LineageService`.
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from polisyos.common.logger import get_logger
from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.protocol import ArtifactStore
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
_REDACTED_PREVIEW = "[REDACTED]"
logger = get_logger(__name__)


class ArtifactInspectorService:
    """Serve manifest/content/schema/lineage projections for one CAS artifact.

    The service never mutates CAS state. Missing artifacts and invalid artifact
    references surface as the underlying `ArtifactStore` exceptions so HTTP
    route handlers can translate them into RFC 7807 responses.
    """
    def __init__(
        self,
        *,
        store: ArtifactStore,
        lineage_service: LineageService,
        default_max_preview_bytes: int = 64 * 1024,
        redaction_hooks: dict[str, RedactionHook] | None = None,
    ) -> None:
        self._store = store
        self._lineage_service = lineage_service
        self._default_max_preview_bytes = max(default_max_preview_bytes, 1024)
        self._redaction_hooks = dict(redaction_hooks or {})

    def get_manifest_view(self, artifact_id: ArtifactID) -> ArtifactManifestView:
        """Return the manifest metadata used by `/artifacts/{id}/manifest`.

        Args:
            artifact_id: Canonical CAS artifact identifier.

        Returns:
            A normalized manifest projection with schema, producer, input, and
            integrity metadata.

        Raises:
            FileNotFoundError: If the artifact or its manifest sidecar is
                missing from CAS.
        """
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
        """Return a bounded, redacted content preview for an artifact payload.

        JSON payloads are decoded only when the preview is not truncated. Text
        payloads are decoded as UTF-8 when possible, and binary payloads fall
        back to a hex preview. Artifact kinds containing secret-like markers or
        custom redaction hooks are redacted before the response is returned.

        Args:
            artifact_id: Canonical CAS artifact identifier.
            max_bytes: Optional per-request preview byte limit. Values are
                clamped to `[1024, 2_000_000]`.

        Returns:
            A content preview DTO with mode, truncation metadata, and sanitized
            payload content.

        Raises:
            FileNotFoundError: If the artifact bytes or manifest sidecar do not
                exist in CAS.
        """
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
        """Return schema metadata plus top-level JSON keys when available.

        Args:
            artifact_id: Canonical CAS artifact identifier.

        Returns:
            A schema projection derived from the manifest and a best-effort
            inspection of JSON payload keys.

        Raises:
            FileNotFoundError: If the artifact manifest or bytes are missing.
        """
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
        """Build an upstream lineage graph rooted at one artifact.

        Args:
            artifact_id: Root artifact to inspect.
            max_depth: Optional traversal depth override.
            max_nodes: Optional graph size override.

        Returns:
            A lineage graph with completeness and corruption flags.
        """
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
        return _REDACTED_PREVIEW

    hook = hooks.get(artifact_kind) or hooks.get("*")
    if hook is None:
        return preview
    try:
        return hook(preview, mode)
    except (AttributeError, RuntimeError, TypeError, ValueError) as exc:
        logger.warning(
            "Redaction hook failed for kind=%s mode=%s: %s", artifact_kind, mode, exc
        )
        return _REDACTED_PREVIEW
