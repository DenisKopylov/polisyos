from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from polisyos.core.components import (
    ComponentEntry,
    ComponentKind,
    ComponentMetadata,
    ComponentRegistry,
    DuplicateComponentIdPolicy,
    ENTRY_POINT_GROUP_LEX_EXTRACTORS,
    ENTRY_POINT_GROUP_SCHOLAR_EXTRACTORS,
    HostAbi,
    discover_components,
    validate_metadata,
)
from polisyos.core.components.ids import SemVer
from polisyos.core.registry.generic import GenericRegistry
from polisyos.fabric.claims.errors import ClaimUnsupportedExtractorError
from polisyos.fabric.claims.types import ChunkContext, ClaimCandidate, ClaimExtractOptions
from polisyos.ir.world.doc import DocMeta


class ClaimExtractorFn(Protocol):
    def __call__(
        self,
        *,
        ctx: ChunkContext,
        meta: DocMeta,
        normalized_text: str,
        options: ClaimExtractOptions,
    ) -> list[ClaimCandidate]: ...


@dataclass(slots=True)
class ExtractorRecord:
    extractor_id: str
    fn: ClaimExtractorFn
    source: str
    kind: str
    metadata: ComponentMetadata | None = None


@dataclass(slots=True)
class ExtractorBootstrapReport:
    registered: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    discovery_errors: list[str] = field(default_factory=list)


class ClaimExtractorRegistry:
    def __init__(self) -> None:
        self._legacy: dict[str, ClaimExtractorFn] = {}
        self._components = GenericRegistry[str, ExtractorRecord](
            key_fn=lambda row: row.extractor_id,
            indexers={
                "base_id": lambda row: row.extractor_id.rsplit("@", 1)[0],
            },
        )

    def register_legacy(self, extractor_id: str, fn: ClaimExtractorFn) -> None:
        self._legacy[extractor_id] = fn

    def register_component(
        self,
        *,
        component_id: str,
        fn: ClaimExtractorFn,
        kind: ComponentKind,
        source: str,
        metadata: ComponentMetadata,
    ) -> None:
        record = ExtractorRecord(
            extractor_id=component_id,
            fn=fn,
            source=source,
            kind=kind.value,
            metadata=metadata,
        )
        self._components.register(record, override=True)

    def resolve(self, extractor_id: str) -> tuple[str, ClaimExtractorFn]:
        if extractor_id in self._legacy:
            return extractor_id, self._legacy[extractor_id]

        direct = self._components.get(extractor_id)
        if direct is not None:
            return direct.extractor_id, direct.fn

        rows = self._components.find("base_id", extractor_id.strip())
        if rows:
            selected = sorted(
                rows,
                key=lambda row: SemVer.parse(row.extractor_id.rsplit("@", 1)[1]),
                reverse=True,
            )[0]
            return selected.extractor_id, selected.fn

        raise ClaimUnsupportedExtractorError(f"unsupported extractor_id: {extractor_id}")

    def select(
        self,
        *,
        domain: str | None,
        jurisdiction: str | None,
        language: str | None,
        mime: str | None,
        preferred_id: str | None,
    ) -> tuple[str, ClaimExtractorFn]:
        if preferred_id is not None and preferred_id.strip():
            normalized_preferred = preferred_id.strip()
            try:
                return self.resolve(normalized_preferred)
            except ClaimUnsupportedExtractorError:
                _ensure_builtin_legacy_extractors(self)
                try:
                    return self.resolve(normalized_preferred)
                except ClaimUnsupportedExtractorError:
                    # Fall through to auto-selection to preserve backward compatibility.
                    pass

        candidates = self._components.values()
        if candidates:
            ranked = sorted(
                candidates,
                key=lambda row: _score_component_extractor(
                    row=row,
                    domain=domain,
                    jurisdiction=jurisdiction,
                    language=language,
                    mime=mime,
                ),
                reverse=True,
            )
            selected = ranked[0]
            return selected.extractor_id, selected.fn

        _ensure_builtin_legacy_extractors(self)
        if self._legacy:
            preferred_legacy = "explicit_lines_v1"
            if preferred_legacy in self._legacy:
                return preferred_legacy, self._legacy[preferred_legacy]
            chosen = sorted(self._legacy.keys())[0]
            return chosen, self._legacy[chosen]

        raise ClaimUnsupportedExtractorError("no extractor registered")

    def list_extractors(self) -> list[str]:
        names = set(self._legacy.keys())
        names.update(self._components.keys())
        names.update(str(value) for value in self._components.index_values("base_id"))
        return sorted(names)


_GLOBAL_REGISTRY = ClaimExtractorRegistry()


def _ensure_builtin_legacy_extractors(registry: ClaimExtractorRegistry) -> None:
    if (
        "explicit_lines_v1" in registry._legacy
        and "lex.norm_extractor.regex_v1" in registry._legacy
        and "regex_numeric_v1" in registry._legacy
    ):
        return
    try:
        from polisyos.fabric.claims.backends import (
            explicit_lines_v1,
            lex_norm_regex_v1,
            regex_numeric_v1,
        )
    except Exception:
        return

    if "explicit_lines_v1" not in registry._legacy:
        registry.register_legacy("explicit_lines_v1", explicit_lines_v1.extract)
    if "lex.norm_extractor.regex_v1" not in registry._legacy:
        registry.register_legacy("lex.norm_extractor.regex_v1", lex_norm_regex_v1.extract)
    if "regex_numeric_v1" not in registry._legacy:
        registry.register_legacy("regex_numeric_v1", regex_numeric_v1.extract)


def get_extractor_registry() -> ClaimExtractorRegistry:
    return _GLOBAL_REGISTRY


def bootstrap_component_extractors(components_index: ComponentRegistry) -> ExtractorBootstrapReport:
    report = ExtractorBootstrapReport()
    host = HostAbi(versions={"world_abi": "1.0", "ir_abi": "1.0"}, strict=True)

    entries = components_index.query(kind=ComponentKind.SCHOLAR_EXTRACTOR)
    entries.extend(components_index.query(kind=ComponentKind.LEX_EXTRACTOR))

    for entry in entries:
        component_id = str(entry.metadata.component_id)
        issues = validate_metadata(
            entry.metadata,
            host_abi=host,
            available_components=components_index,
        )
        errors = [issue for issue in issues if issue.severity == "error"]
        if errors:
            report.errors.append(
                f"{component_id}: {'; '.join(issue.message for issue in errors)}"
            )
            continue

        try:
            extractor = entry.component.create()
        except Exception as exc:
            report.errors.append(f"{component_id}: component.create() failed: {exc}")
            continue

        if not callable(extractor):
            report.errors.append(f"{component_id}: extractor must be callable")
            continue

        get_extractor_registry().register_component(
            component_id=component_id,
            fn=extractor,
            kind=entry.metadata.kind,
            source=str(getattr(entry.source, "source_type", "entry_point")),
            metadata=entry.metadata,
        )
        report.registered.append(component_id)

    report.registered.sort()
    report.errors.sort()
    return report


def discover_and_bootstrap_extractors(
    *,
    include_dev_scan: bool = True,
    components_index: ComponentRegistry | None = None,
) -> ExtractorBootstrapReport:
    if components_index is not None:
        return bootstrap_component_extractors(components_index)

    discovered = discover_components(
        groups=[
            ENTRY_POINT_GROUP_SCHOLAR_EXTRACTORS,
            ENTRY_POINT_GROUP_LEX_EXTRACTORS,
        ],
        include_dev_scan=include_dev_scan,
    )

    registry = ComponentRegistry()
    for row in discovered.components:
        registry.register(
            ComponentEntry(metadata=row.metadata, component=row.component, source=row.source),
            on_duplicate=DuplicateComponentIdPolicy.WARN,
        )

    report = bootstrap_component_extractors(registry)
    report.discovery_errors = [
        f"{error.source}:{error.item or '<unknown>'}: {error.message}"
        for error in discovered.errors
    ]
    report.discovery_errors.sort()
    return report


def _score_component_extractor(
    *,
    row: ExtractorRecord,
    domain: str | None,
    jurisdiction: str | None,
    language: str | None,
    mime: str | None,
) -> tuple[int, int, int, int, str]:
    metadata = row.metadata
    if metadata is None:
        return (0, 0, 0, 0, row.extractor_id)

    score = 0
    if domain is not None:
        if domain in metadata.domains:
            score += 100
        elif not metadata.domains:
            score += 5
    elif not metadata.domains:
        score += 1

    if jurisdiction is not None:
        if jurisdiction in metadata.jurisdictions:
            score += 50
        elif not metadata.jurisdictions:
            score += 5
    elif not metadata.jurisdictions:
        score += 1

    lang_tags = [tag for tag in metadata.tags if tag.startswith("lang:")]
    if language is not None and lang_tags:
        if f"lang:{language}" in lang_tags:
            score += 20
    elif language is not None and not lang_tags:
        score += 2

    mime_tags = [tag for tag in metadata.tags if tag.startswith("mime:")]
    if mime is not None and mime_tags:
        if f"mime:{mime}" in mime_tags:
            score += 20
        for tag in mime_tags:
            if tag.endswith("/*"):
                prefix = tag[5:-1]
                if mime.startswith(prefix):
                    score += 10
    elif mime is not None and not mime_tags:
        score += 2

    semver = SemVer.parse(row.extractor_id.rsplit("@", 1)[1])
    prerelease_rank = 0 if semver.prerelease else 1
    return (score, semver.major, semver.minor, semver.patch * 10 + prerelease_rank, row.extractor_id)


__all__ = [
    "ClaimExtractorFn",
    "ClaimExtractorRegistry",
    "ExtractorBootstrapReport",
    "bootstrap_component_extractors",
    "discover_and_bootstrap_extractors",
    "get_extractor_registry",
]
