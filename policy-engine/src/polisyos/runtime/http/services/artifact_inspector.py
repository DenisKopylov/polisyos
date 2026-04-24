"""Project CAS artifacts into redacted HTTP inspection views.

`ArtifactInspectorService` is a read-only runtime boundary: it loads artifact
manifests and payload bytes from CAS, applies preview limits and secret
redaction, and delegates lineage expansion to `LineageService`.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from polisyos.common.logger import get_logger
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.contracts.runtime import (
    ArtifactContentPreview,
    ArtifactLineageView,
    ArtifactManifestView,
    ArtifactSchemaView,
    DecisionPacketAuthoredBlock,
    DecisionPacketEffectSize,
    DecisionPacketMetricComparisonRow,
    DecisionPacketMetricSignificance,
    DecisionPacketOutlineEntry,
    DecisionPacketPreview,
    PreviewMode,
)

if TYPE_CHECKING:
    from polisyos.core.artifacts.ids import ArtifactID
    from polisyos.core.artifacts.protocol import ArtifactStore

    from .lineage import LineageService

RedactionHook = Callable[[Any, PreviewMode], Any]
_SENSITIVE_KIND_MARKERS = ("secret", "token", "credential", "password", "key_material")
_REDACTED_PREVIEW = "[REDACTED]"
logger = get_logger(__name__)


def _as_float(value: object) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        try:
            return float(stripped)
        except ValueError:
            return None
    return None


def _normalize_text_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    items: list[str] = []
    for item in value:
        if isinstance(item, str):
            stripped = item.strip()
            if stripped:
                items.append(stripped)
    return items


def _normalize_effect_method(value: object) -> str | None:
    if isinstance(value, str):
        lowered = value.strip().lower()
        if not lowered:
            return None
        if "bootstrap" in lowered:
            return "bootstrap"
        if lowered in {"paired_t", "delong_auc", "mcnemar_exact", "mcnemar_chi2"}:
            return "analytic"
        return lowered
    return None


def _normalize_effect_size(
    *,
    effect_value: object,
    ci_low: object = None,
    ci_high: object = None,
    method: object = None,
) -> DecisionPacketEffectSize | None:
    point = _as_float(effect_value)
    low = _as_float(ci_low)
    high = _as_float(ci_high)
    ci_95 = (low, high) if low is not None and high is not None else None
    normalized_method = _normalize_effect_method(method)
    if point is None and ci_95 is None and normalized_method is None:
        return None
    return DecisionPacketEffectSize(
        point=point,
        ci_95=ci_95,
        method=normalized_method,
    )


def _comparison_lookup(
    rows: object,
) -> dict[str, dict[str, object]]:
    lookup: dict[str, dict[str, object]] = {}
    if not isinstance(rows, list):
        return lookup
    for row in rows:
        if not isinstance(row, dict):
            continue
        metric_id = row.get("metric_id")
        if isinstance(metric_id, str) and metric_id not in lookup:
            lookup[metric_id] = row
    return lookup


def _normalize_outline(value: object) -> list[DecisionPacketOutlineEntry]:
    if not isinstance(value, list):
        return []
    items: list[DecisionPacketOutlineEntry] = []
    for entry in value:
        if not isinstance(entry, dict):
            continue
        section_id = entry.get("section_id")
        title = entry.get("title")
        section_type = entry.get("section_type")
        if not isinstance(section_id, str) or not isinstance(title, str):
            continue
        items.append(
            DecisionPacketOutlineEntry(
                section_id=section_id,
                title=title,
                section_type=section_type if isinstance(section_type, str) else None,
            )
        )
    return items


def _normalize_metric_significance(
    value: object,
    *,
    comparison_rows: object,
) -> dict[str, DecisionPacketMetricSignificance]:
    if not isinstance(value, dict):
        return {}
    comparisons = _comparison_lookup(comparison_rows)
    normalized: dict[str, DecisionPacketMetricSignificance] = {}
    for metric_id, entry in value.items():
        if not isinstance(metric_id, str) or not isinstance(entry, dict):
            continue
        comparison = comparisons.get(metric_id, {})
        effect_size = _normalize_effect_size(
            effect_value=entry.get("effect_size"),
            ci_low=comparison.get("ci_low"),
            ci_high=comparison.get("ci_high"),
            method=comparison.get("resampling_method") or entry.get("test_id"),
        )
        normalized[metric_id] = DecisionPacketMetricSignificance(
            baseline_model_id=entry.get("baseline_model_id")
            if isinstance(entry.get("baseline_model_id"), str)
            else None,
            candidate_model_id=entry.get("candidate_model_id")
            if isinstance(entry.get("candidate_model_id"), str)
            else None,
            metric_direction=entry.get("metric_direction")
            if isinstance(entry.get("metric_direction"), str)
            else None,
            baseline_value=_as_float(entry.get("baseline_value")),
            candidate_value=_as_float(entry.get("candidate_value")),
            delta_value=_as_float(entry.get("delta_value")),
            test_id=entry.get("test_id") if isinstance(entry.get("test_id"), str) else None,
            test_label=entry.get("test_label")
            if isinstance(entry.get("test_label"), str)
            else None,
            p_value=_as_float(entry.get("p_value")),
            p_adj=_as_float(entry.get("p_adj")),
            alpha=_as_float(entry.get("alpha")),
            significant=entry.get("significant")
            if isinstance(entry.get("significant"), bool)
            else None,
            effect_size=effect_size,
            assumption_warnings=_normalize_text_list(entry.get("assumption_warnings")),
            calibration_warnings=_normalize_text_list(entry.get("calibration_warnings")),
        )
    return normalized


def _normalize_metric_comparison_rows(
    value: object,
) -> list[DecisionPacketMetricComparisonRow]:
    if not isinstance(value, list):
        return []
    rows: list[DecisionPacketMetricComparisonRow] = []
    for entry in value:
        if not isinstance(entry, dict):
            continue
        metric_id = entry.get("metric_id")
        if not isinstance(metric_id, str):
            continue
        rows.append(
            DecisionPacketMetricComparisonRow(
                metric_id=metric_id,
                metric_direction=entry.get("metric_direction")
                if isinstance(entry.get("metric_direction"), str)
                else None,
                baseline_model_id=entry.get("baseline_model_id")
                if isinstance(entry.get("baseline_model_id"), str)
                else None,
                candidate_model_id=entry.get("candidate_model_id")
                if isinstance(entry.get("candidate_model_id"), str)
                else None,
                baseline_value=_as_float(entry.get("baseline_value")),
                candidate_value=_as_float(entry.get("candidate_value")),
                delta_value=_as_float(entry.get("delta_value")),
                family_id=entry.get("family_id")
                if isinstance(entry.get("family_id"), str)
                else None,
                family_scope=entry.get("family_scope")
                if isinstance(entry.get("family_scope"), str)
                else None,
                sample_size_effective=(
                    int(entry["sample_size_effective"])
                    if isinstance(entry.get("sample_size_effective"), int)
                    else None
                ),
                resampling_method=entry.get("resampling_method")
                if isinstance(entry.get("resampling_method"), str)
                else None,
                test_id=entry.get("test_id") if isinstance(entry.get("test_id"), str) else None,
                test_label=entry.get("test_label")
                if isinstance(entry.get("test_label"), str)
                else None,
                statistic=_as_float(entry.get("statistic")),
                effect_size=_normalize_effect_size(
                    effect_value=entry.get("effect_size"),
                    ci_low=entry.get("ci_low"),
                    ci_high=entry.get("ci_high"),
                    method=entry.get("resampling_method") or entry.get("test_id"),
                ),
                p_value=_as_float(entry.get("p_value")),
                p_adj=_as_float(entry.get("p_adj")),
                alpha=_as_float(entry.get("alpha")),
                significant=entry.get("significant")
                if isinstance(entry.get("significant"), bool)
                else None,
                assumption_warnings=_normalize_text_list(entry.get("assumption_warnings")),
                calibration_warnings=_normalize_text_list(entry.get("calibration_warnings")),
            )
        )
    return rows


def _normalize_authored_blocks(value: object) -> list[DecisionPacketAuthoredBlock]:
    if not isinstance(value, list):
        return []
    blocks: list[DecisionPacketAuthoredBlock] = []
    for entry in value:
        if not isinstance(entry, dict):
            continue
        content = entry.get("content")
        if not isinstance(content, str) or not content.strip():
            continue
        sources_value = entry.get("sources")
        sources: list[dict[str, str]] = []
        if isinstance(sources_value, list):
            for source in sources_value:
                if not isinstance(source, dict):
                    continue
                ref = source.get("ref")
                if not isinstance(ref, str) or not ref.strip():
                    continue
                kind = source.get("kind")
                sources.append(
                    {
                        "ref": ref,
                        "kind": kind if isinstance(kind, str) and kind.strip() else "source",
                    }
                )
        blocks.append(
            DecisionPacketAuthoredBlock(
                id=entry.get("id") if isinstance(entry.get("id"), str) else None,
                content=content,
                author=entry.get("author")
                if isinstance(entry.get("author"), str)
                and entry.get("author") in {"citation", "human", "drafter", "formalizer", "critic"}
                else None,
                author_agent_version=entry.get("author_agent_version")
                if isinstance(entry.get("author_agent_version"), str)
                else None,
                sources=sources,
                timestamp=entry.get("timestamp")
                if isinstance(entry.get("timestamp"), str)
                else None,
                confidence=_as_float(entry.get("confidence")),
                reviewed_by_human=entry.get("reviewed_by_human")
                if isinstance(entry.get("reviewed_by_human"), bool)
                else None,
            )
        )
    return blocks


def _build_decision_packet_preview(payload: object) -> DecisionPacketPreview | None:
    if not isinstance(payload, dict):
        return None
    normalized = dict(payload)
    normalized["document_outline"] = _normalize_outline(payload.get("document_outline"))
    normalized["metric_validation_comparison_rows"] = _normalize_metric_comparison_rows(
        payload.get("metric_validation_comparison_rows")
    )
    normalized["metric_significance_by_metric"] = _normalize_metric_significance(
        payload.get("metric_significance_by_metric"),
        comparison_rows=payload.get("metric_validation_comparison_rows"),
    )
    normalized["blocks"] = _normalize_authored_blocks(payload.get("blocks"))
    normalized["narrative_blocks"] = _normalize_authored_blocks(payload.get("narrative_blocks"))
    normalized["evidence_summary_blocks"] = _normalize_authored_blocks(
        payload.get("evidence_summary_blocks")
    )
    return DecisionPacketPreview.model_validate(normalized)


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
        elif _is_text_media_type(manifest.media_type) or not truncated:
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
        decision_packet_preview = (
            _build_decision_packet_preview(preview)
            if manifest.kind == "scientist.decision_packet" and mode == "json"
            else None
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
            decision_packet_preview=decision_packet_preview,
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
        logger.warning("Redaction hook failed for kind=%s mode=%s: %s", artifact_kind, mode, exc)
        return _REDACTED_PREVIEW
