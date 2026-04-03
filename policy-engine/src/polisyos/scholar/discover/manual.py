"""Normalizes manually supplied Scholar seed sources into canonical discover inputs."""
from __future__ import annotations

from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from polisyos.core.canon import content_hash
from polisyos.core.contracts.scholar import SourceSpec
from polisyos.scholar.errors import ScholarDiscoverError, ScholarValidationError


def _canonicalize_url(raw_url: str) -> str:
    candidate = raw_url.strip()
    parsed = urlparse(candidate)
    if not parsed.scheme or not parsed.netloc:
        raise ScholarValidationError(
            f"invalid URL: {raw_url!r}",
            stage="discover",
            details={"field": "canonical_url"},
        )

    scheme = parsed.scheme.lower()
    host = (parsed.hostname or "").lower()
    if not host:
        raise ScholarValidationError(
            f"invalid URL host: {raw_url!r}",
            stage="discover",
            details={"field": "canonical_url"},
        )

    netloc = host
    if parsed.port is not None:
        default_port = (scheme == "http" and parsed.port == 80) or (
            scheme == "https" and parsed.port == 443
        )
        if not default_port:
            netloc = f"{host}:{parsed.port}"

    query_pairs = parse_qsl(parsed.query, keep_blank_values=True)
    query = urlencode(sorted((str(k), str(v)) for k, v in query_pairs), doseq=True)

    return urlunparse(
        (
            scheme,
            netloc,
            parsed.path or "/",
            parsed.params,
            query,
            "",  # drop fragment
        )
    )


def source_identity_key(source: SourceSpec) -> str:
    """Return the canonical identity used to sort and deduplicate Scholar seed sources."""
    return source.canonical_url or source.official_id or source.source_locator or ""


def _normalize_single_source(source: SourceSpec) -> SourceSpec:
    props = {key: value for key, value in sorted(source.props.items())}
    mime_hint = source.mime_hint.strip() if source.mime_hint else None
    license_value = source.license.strip()

    if source.kind == "local_file":
        if source.path is None:
            raise ScholarValidationError(
                "local_file source requires path",
                stage="discover",
                source_identity=source_identity_key(source),
            )
        canonical_path = str(Path(source.path).expanduser().resolve())
        return SourceSpec(
            kind="local_file",
            canonical_url=None,
            official_id=None,
            source_locator=canonical_path,
            license=license_value,
            mime_hint=mime_hint,
            props=props,
            path=canonical_path,
        )

    if source.kind == "bytes":
        if source.data is None:
            raise ScholarValidationError(
                "bytes source requires data",
                stage="discover",
                source_identity=source_identity_key(source),
            )
        locator = f"bytes.sha256_{content_hash(source.data)}"
        return SourceSpec(
            kind="bytes",
            canonical_url=None,
            official_id=None,
            source_locator=locator,
            license=license_value,
            mime_hint=mime_hint,
            props=props,
            data=source.data,
        )

    if source.kind == "url":
        raw_url = source.canonical_url or source.url
        if not raw_url:
            raise ScholarValidationError(
                "url source requires canonical_url or url",
                stage="discover",
                source_identity=source_identity_key(source),
            )
        canonical_url = _canonicalize_url(raw_url)
        return SourceSpec(
            kind="url",
            canonical_url=canonical_url,
            official_id=None,
            source_locator=None,
            license=license_value,
            mime_hint=mime_hint,
            props=props,
            url=canonical_url,
        )

    raise ScholarValidationError(
        f"unsupported source kind: {source.kind}",
        stage="discover",
        source_identity=source_identity_key(source),
    )


def normalize_seed_sources(
    seed_sources: list[SourceSpec], *, max_docs: int | None = None
) -> list[SourceSpec]:
    """Canonicalize, sort, deduplicate, and optionally truncate manual Scholar seed sources."""
    if max_docs is not None and max_docs <= 0:
        raise ScholarValidationError(
            "max_docs must be > 0",
            stage="discover",
            details={"max_docs": max_docs},
        )

    normalized: list[SourceSpec] = []
    for source in seed_sources:
        try:
            normalized.append(_normalize_single_source(source))
        except ScholarValidationError:
            raise
        except Exception as exc:  # pragma: no cover - defensive wrapper
            raise ScholarDiscoverError(
                f"failed to normalize source: {exc}",
                source_identity=source_identity_key(source),
            ) from exc

    normalized.sort(key=lambda source: (source_identity_key(source), source.kind))

    deduped: list[SourceSpec] = []
    seen: set[str] = set()
    for source in normalized:
        key = source_identity_key(source)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(source)

    if max_docs is not None:
        return deduped[:max_docs]
    return deduped


__all__ = ["normalize_seed_sources", "source_identity_key"]
