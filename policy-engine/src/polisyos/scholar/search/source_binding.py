"""Resolve persisted Scholar page snapshots and bind citations to their exact text."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.canon import content_hash
from polisyos.scholar.search.fetcher import _extract_title_and_text
from polisyos.scholar.search.security import sanitize_untrusted_text

if TYPE_CHECKING:
    from polisyos.core.artifacts.protocol import ArtifactStore
    from polisyos.scholar.search.models import SourceMetadata, SourceSnippet, WebEvidenceBundle

_RAW_PAGE_KIND = "scholar.web_fetch_payload"
_RAW_PAGE_SCHEMA_NAME = "polisyos.scholar.web_fetch_payload"
_RAW_PAGE_SCHEMA_VERSION = "1.0"
_RAW_PAGE_PRODUCER = "polisyos.scholar.search.cache"
_RAW_PAGE_PRODUCER_VERSION = "1.0.0"


@dataclass(frozen=True, slots=True)
class SourceBindingResult:
    """Result of resolving page snapshots and checking every citation span."""

    passed: bool
    source_text_by_id: dict[str, str] = field(default_factory=dict)
    violations: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


def validate_web_evidence_source_binding(
    bundle: WebEvidenceBundle,
    *,
    cas: ArtifactStore | None,
    require_all_sources: bool = False,
) -> SourceBindingResult:
    """Verify bundle snippets against exact text re-extracted from their CAS payloads.

    A content digest alone is not evidence that an artifact is present or that
    it has the Scholar raw-page contract. This resolver binds the selected CAS
    view, its manifest, the raw bytes, the current Scholar extractor, and the
    citation offsets as one check. Legacy bundles with only an artifact ID use
    the CAS default manifest view and are reported as profileless.
    """
    violations: list[str] = []
    warnings: list[str] = []
    source_text_by_id: dict[str, str] = {}
    required_source_ids = {snippet.source_id for snippet in bundle.snippets}
    source_by_id: dict[str, SourceMetadata] = {}

    for source in bundle.sources:
        if source.source_id in source_by_id:
            violations.append(f"duplicate_source_id:{source.source_id}")
            continue
        source_by_id[source.source_id] = source

    missing_source_ids = required_source_ids - set(source_by_id)
    violations.extend(f"missing_source_metadata:{item}" for item in sorted(missing_source_ids))
    for snippet in bundle.snippets:
        source = source_by_id.get(snippet.source_id)
        if source is not None and str(snippet.url) != str(source.url):
            violations.append(f"snippet_url_mismatch:{snippet.snippet_id}")

    sources_to_resolve = [
        source
        for source in bundle.sources
        if source.source_id in required_source_ids
        or (require_all_sources and source.fetch_status in {"ok", "cached"})
    ]
    if sources_to_resolve and cas is None:
        violations.append("source_cas_unavailable")
        return _result(source_text_by_id, violations, warnings)

    if cas is not None:
        for source in sources_to_resolve:
            if source.fetch_status not in {"ok", "cached"} or source.paywalled or source.error:
                if source.source_id in required_source_ids:
                    violations.append(f"source_not_fetchable:{source.source_id}")
                continue
            resolved_text, source_violations, source_warnings = _resolve_source_text(
                source,
                cas=cas,
            )
            violations.extend(source_violations)
            warnings.extend(source_warnings)
            if resolved_text is not None:
                source_text_by_id[source.source_id] = resolved_text

    span_violations, span_warnings = validate_source_snippet_spans(
        bundle.snippets,
        source_text_by_id=source_text_by_id,
    )
    violations.extend(span_violations)
    warnings.extend(span_warnings)
    return _result(source_text_by_id, violations, warnings)


def validate_source_snippet_spans(
    snippets: list[SourceSnippet],
    *,
    source_text_by_id: dict[str, str],
) -> tuple[list[str], list[str]]:
    """Check that each half-open citation span selects the exact reported text."""
    violations: list[str] = []
    warnings: list[str] = []
    seen: set[str] = set()
    for snippet in snippets:
        if snippet.snippet_id in seen:
            violations.append(f"duplicate_snippet_id:{snippet.snippet_id}")
        seen.add(snippet.snippet_id)
        if snippet.start_char < 0 or snippet.end_char < snippet.start_char:
            violations.append(f"invalid_span:{snippet.snippet_id}")
            continue
        if not snippet.text:
            violations.append(f"empty_snippet_text:{snippet.snippet_id}")
        source_text = source_text_by_id.get(snippet.source_id)
        if source_text is None:
            violations.append(f"missing_source_text:{snippet.source_id}")
            continue
        if snippet.end_char > len(source_text):
            violations.append(f"span_exceeds_source_text:{snippet.snippet_id}")
            continue
        if source_text[snippet.start_char : snippet.end_char] != snippet.text:
            violations.append(f"span_text_mismatch:{snippet.snippet_id}")
    return violations, warnings


def _resolve_source_text(
    source: SourceMetadata,
    *,
    cas: ArtifactStore,
) -> tuple[str | None, list[str], list[str]]:
    violations: list[str] = []
    warnings: list[str] = []
    raw_ref = source.raw_artifact_ref
    source_identity = source.source_id

    if raw_ref is None:
        candidate_id = source.artifact_id
        if candidate_id is None:
            violations.append(f"source_artifact_ref_missing:{source_identity}")
            return None, violations, warnings
        try:
            artifact_id = ArtifactID.model_validate(candidate_id)
        except (TypeError, ValueError):
            violations.append(f"source_artifact_ref_invalid:{source_identity}")
            return None, violations, warnings
        selected_ref: ArtifactID | ArtifactRef = artifact_id
        warnings.append(f"source_artifact_profileless_default:{source_identity}")
    else:
        try:
            selected_ref = ArtifactRef.model_validate(raw_ref)
            artifact_id = selected_ref.artifact_id
        except (TypeError, ValueError):
            violations.append(f"source_artifact_ref_invalid:{source_identity}")
            return None, violations, warnings
        if source.artifact_id is not None and str(artifact_id) != source.artifact_id:
            violations.append(f"source_artifact_id_conflict:{source_identity}")
            return None, violations, warnings

    expected_digest = _normalize_digest(source.content_sha256)
    if source.content_sha256 and expected_digest is None:
        violations.append(f"source_content_digest_invalid:{source_identity}")
        return None, violations, warnings
    if expected_digest is None:
        violations.append(f"source_content_digest_missing:{source_identity}")
        return None, violations, warnings
    if artifact_id.hex != expected_digest:
        violations.append(f"source_artifact_digest_mismatch:{source_identity}")
        return None, violations, warnings

    try:
        manifest = cas.get_manifest(selected_ref)
        raw_bytes = cas.get_bytes(selected_ref)
    except Exception:
        violations.append(f"source_artifact_unavailable:{source_identity}")
        return None, violations, warnings

    actual_digest = content_hash(raw_bytes)
    if actual_digest != expected_digest or actual_digest != artifact_id.hex:
        violations.append(f"source_payload_digest_mismatch:{source_identity}")
        return None, violations, warnings
    if manifest.artifact_id != artifact_id or manifest.integrity.sha256 != actual_digest:
        violations.append(f"source_manifest_identity_mismatch:{source_identity}")
        return None, violations, warnings
    if manifest.byte_size != len(raw_bytes) or (
        source.byte_size is not None and source.byte_size != len(raw_bytes)
    ):
        violations.append(f"source_byte_size_mismatch:{source_identity}")
        return None, violations, warnings

    schema = manifest.artifact_schema
    producer = manifest.producer
    if (
        manifest.kind != _RAW_PAGE_KIND
        or manifest.media_type != source.content_type
        or (
            raw_ref is not None
            and (raw_ref.kind != manifest.kind or raw_ref.media_type != manifest.media_type)
        )
        or schema is None
        or schema.name != _RAW_PAGE_SCHEMA_NAME
        or schema.version != _RAW_PAGE_SCHEMA_VERSION
        or producer is None
        or producer.component != _RAW_PAGE_PRODUCER
        or producer.version != _RAW_PAGE_PRODUCER_VERSION
    ):
        violations.append(f"source_manifest_contract_mismatch:{source_identity}")
        return None, violations, warnings

    selected_profile = raw_ref.manifest_profile_sha256 if raw_ref is not None else None
    if selected_profile is not None:
        from polisyos.core.artifacts._manifest_lifecycle import ManifestLifecycle

        if ManifestLifecycle.profile_sha256(manifest) != selected_profile:
            violations.append(f"source_manifest_profile_mismatch:{source_identity}")
            return None, violations, warnings

    final_url = source.final_url or str(source.url)
    try:
        _title, extracted_text = _extract_title_and_text(
            raw_bytes,
            mime=source.content_type,
            final_url=final_url,
        )
        normalized_text = sanitize_untrusted_text(extracted_text)
    except Exception:
        violations.append(f"source_text_extraction_failed:{source_identity}")
        return None, violations, warnings
    return normalized_text, violations, warnings


def _normalize_digest(value: str | None) -> str | None:
    if value is None or not value.strip():
        return None
    candidate = value.strip().lower()
    if candidate.startswith("sha256:"):
        candidate = candidate[7:]
    if len(candidate) != 64 or any(char not in "0123456789abcdef" for char in candidate):
        return None
    return candidate


def _result(
    source_text_by_id: dict[str, str],
    violations: list[str],
    warnings: list[str],
) -> SourceBindingResult:
    normalized_violations = tuple(sorted(dict.fromkeys(violations)))
    normalized_warnings = tuple(sorted(dict.fromkeys(warnings)))
    return SourceBindingResult(
        passed=not normalized_violations,
        source_text_by_id=source_text_by_id,
        violations=normalized_violations,
        warnings=normalized_warnings,
    )


__all__ = [
    "SourceBindingResult",
    "validate_source_snippet_spans",
    "validate_web_evidence_source_binding",
]
