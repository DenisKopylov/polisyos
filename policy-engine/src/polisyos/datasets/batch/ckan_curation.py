"""Helpers for curating CKAN package metadata into execution-ready subsets."""

from __future__ import annotations

from copy import deepcopy
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

if TYPE_CHECKING:
    from polisyos.datasets.batch.source_registry import SourceSpec

_EXTENSION_FORMATS = {
    ".csv": "CSV",
    ".json": "JSON",
    ".xlsx": "XLSX",
    ".xls": "XLS",
    ".ods": "ODS",
    ".zip": "ZIP",
    ".pdf": "PDF",
    ".doc": "DOC",
    ".docx": "DOCX",
    ".xml": "XML",
}


def guess_ckan_resource_format(resource: dict[str, Any]) -> str:
    """Infer a normalized resource format from metadata and URL."""
    explicit = str(resource.get("format") or "").strip().upper()
    if explicit:
        if explicit in {"XLSM", "XLSB"}:
            return "XLSX"
        if explicit in {"ODS", "XLS", "XLSX", "CSV", "JSON", "ZIP", "PDF", "DOC", "DOCX", "XML"}:
            return explicit
    parsed = urlparse(str(resource.get("url") or ""))
    path = parsed.path.lower()
    for suffix, fmt in _EXTENSION_FORMATS.items():
        if path.endswith(suffix):
            return fmt
    return explicit


def curate_ckan_package(raw: dict[str, Any], spec: SourceSpec) -> dict[str, Any] | None:
    """Apply source-spec curation rules and prune resources.

    Returns a copied and pruned package dict or ``None`` if the package does not
    satisfy the curated execution rules.
    """
    if not raw:
        return None
    if not _has_curation_rules(spec):
        return deepcopy(raw)

    text = _package_search_text(raw)
    allow_match = _matches_any(text, spec.keyword_allowlist) if spec.keyword_allowlist else True
    deny_match = _matches_any(text, spec.keyword_denylist)
    if not allow_match or deny_match:
        return None

    resources = raw.get("resources") if isinstance(raw.get("resources"), list) else []
    curated_resources: list[dict[str, Any]] = []
    for resource in resources:
        if not isinstance(resource, dict):
            continue
        fmt = guess_ckan_resource_format(resource)
        if spec.format_denylist and fmt in spec.format_denylist:
            continue
        if spec.format_allowlist and fmt not in spec.format_allowlist:
            continue
        curated = dict(resource)
        curated["format"] = fmt
        curated_resources.append(curated)

    if spec.require_curated_resources and not curated_resources:
        return None

    curated_package = deepcopy(raw)
    if curated_resources:
        curated_package["resources"] = curated_resources
    elif "resources" in curated_package:
        curated_package["resources"] = []
    curated_package["policyos_curated_source"] = spec.name
    return curated_package


def _has_curation_rules(spec: SourceSpec) -> bool:
    return bool(
        spec.seed_from
        or spec.format_allowlist
        or spec.format_denylist
        or spec.keyword_allowlist
        or spec.keyword_denylist
        or spec.require_curated_resources
    )


def _package_search_text(raw: dict[str, Any]) -> str:
    parts: list[str] = []
    for key in ("title", "notes", "description", "name"):
        value = raw.get(key)
        if value:
            parts.append(str(value))

    organization = raw.get("organization")
    if isinstance(organization, dict):
        for key in ("title", "name", "description"):
            value = organization.get(key)
            if value:
                parts.append(str(value))

    for tag in raw.get("tags") or []:
        if isinstance(tag, dict):
            value = tag.get("display_name") or tag.get("name")
            if value:
                parts.append(str(value))

    keywords = raw.get("keywords")
    if isinstance(keywords, str):
        parts.append(keywords)
    elif isinstance(keywords, list):
        parts.extend(str(item) for item in keywords if item)

    extras = raw.get("extras") or []
    for extra in extras:
        if isinstance(extra, dict):
            value = extra.get("value")
            if value:
                parts.append(str(value))

    return " ".join(parts).lower()


def _matches_any(text: str, needles: tuple[str, ...]) -> bool:
    haystack = text.lower()
    for needle in needles:
        candidate = str(needle or "").strip().lower()
        if candidate and candidate in haystack:
            return True
    return False


__all__ = ["curate_ckan_package", "guess_ckan_resource_format"]
