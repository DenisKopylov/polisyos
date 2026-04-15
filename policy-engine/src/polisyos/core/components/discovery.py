"""Discover plugin components from Python entry points and local dev scan roots.

Entry-point groups are the stable package-install boundary, while
`POLISYOS_PACKS_PATHS`/`dev_scan_paths` provide a local development override
for unpacked component repositories. Duplicate handling is deterministic and
reported through `DiscoveryReport`.
"""
from __future__ import annotations

import os
import sys
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from polisyos.common.logger import get_logger
from polisyos.core.discovery import (
    BaseDiscovery,
    DuplicatePolicy,
    discovery_module_name,
    format_traceback,
    list_entry_points,
    load_module_from_file,
)

from .metadata import ComponentKind, ComponentMetadata
from .protocols import Component

if TYPE_CHECKING:
    from types import ModuleType

_DISCOVERY_BOUNDARY_ERRORS = (
    AttributeError,
    ImportError,
    LookupError,
    ModuleNotFoundError,
    RuntimeError,
    SyntaxError,
    TypeError,
    ValueError,
)

ENTRY_POINT_GROUP_IR_FRAGMENTS = "polisyos.ir_fragments"
ENTRY_POINT_GROUP_FOUNDRY_METHODS = "polisyos.foundry_methods"
ENTRY_POINT_GROUP_FABRIC_CONNECTORS = "polisyos.fabric_connectors"
ENTRY_POINT_GROUP_SCHOLAR_EXTRACTORS = "polisyos.scholar_extractors"
ENTRY_POINT_GROUP_LEX_EXTRACTORS = "polisyos.lex_extractors"
ENTRY_POINT_GROUP_LEX_EVALUATORS = "polisyos.lex_evaluators"
ENTRY_POINT_GROUP_SCIENTIST_NODES = "polisyos.scientist_nodes"
ENTRY_POINT_GROUP_NORM_PACK_PROVIDERS = "polisyos.norm_pack_providers"

LEGACY_ENTRY_POINT_GROUP = "polisyos.components"
ENTRY_POINT_GROUP = LEGACY_ENTRY_POINT_GROUP  # backwards compatibility
logger = get_logger(__name__)

ENTRY_POINT_KIND_BY_GROUP: dict[str, ComponentKind] = {
    ENTRY_POINT_GROUP_IR_FRAGMENTS: ComponentKind.IR_FRAGMENT,
    ENTRY_POINT_GROUP_FOUNDRY_METHODS: ComponentKind.FOUNDRY_METHOD,
    ENTRY_POINT_GROUP_FABRIC_CONNECTORS: ComponentKind.FABRIC_CONNECTOR,
    ENTRY_POINT_GROUP_SCHOLAR_EXTRACTORS: ComponentKind.SCHOLAR_EXTRACTOR,
    ENTRY_POINT_GROUP_LEX_EXTRACTORS: ComponentKind.LEX_EXTRACTOR,
    ENTRY_POINT_GROUP_LEX_EVALUATORS: ComponentKind.LEX_EVALUATOR,
    ENTRY_POINT_GROUP_SCIENTIST_NODES: ComponentKind.SCIENTIST_NODE,
    ENTRY_POINT_GROUP_NORM_PACK_PROVIDERS: ComponentKind.NORM_PACK_PROVIDER,
}

DEFAULT_ENTRY_POINT_GROUPS: tuple[str, ...] = tuple(sorted(ENTRY_POINT_KIND_BY_GROUP.keys()))
DEFAULT_DEV_SCAN_ROOT: Path | None = None
DISCOVERY_MODULE_PREFIX = "_polisyos_components_scan_"


@dataclass(slots=True, frozen=True)
class DiscoverySourceInfo:
    """Describe where a component declaration was loaded from."""
    source_type: str
    location: str
    group: str | None = None
    entry_point: str | None = None


@dataclass(slots=True)
class DiscoveredComponent:
    """Pair a materialized component with metadata and source provenance."""
    metadata: ComponentMetadata
    component: Component
    source: DiscoverySourceInfo


@dataclass(slots=True)
class DiscoveryDuplicate:
    """Explain which duplicate component declaration was kept or dropped."""
    component_id: str
    kept_source: DiscoverySourceInfo
    dropped_source: DiscoverySourceInfo
    reason: str


@dataclass(slots=True)
class DiscoveryError:
    """Capture a non-fatal discovery failure tied to one source/item."""
    source: str
    item: str | None
    error_type: str
    message: str
    details: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class DiscoveryPrecedencePolicy:
    """Select whether local dev scan declarations override installed entry points."""
    dev_scan_wins_over_entry_points: bool = True


@dataclass(slots=True)
class DiscoveryReport:
    """Collect discovered components plus duplicate/error diagnostics."""
    components: list[DiscoveredComponent] = field(default_factory=list)
    duplicates: list[DiscoveryDuplicate] = field(default_factory=list)
    errors: list[DiscoveryError] = field(default_factory=list)
    sources_processed: int = 0

    @property
    def success(self) -> bool:
        return len(self.errors) == 0


@dataclass(slots=True)
class _EntryPointSource:
    group: str
    errors: list[DiscoveryError] = field(default_factory=list)

    def discover(self) -> Iterator[DiscoveredComponent]:
        self.errors.clear()
        return iter(_discover_group(group=self.group, errors=self.errors))


@dataclass(slots=True)
class _DevPathSource:
    path: Path
    errors: list[DiscoveryError] = field(default_factory=list)

    def discover(self) -> Iterator[DiscoveredComponent]:
        self.errors.clear()
        return iter(_discover_dev_path(self.path, errors=self.errors))


def _source_kind(source: object) -> str:
    if isinstance(source, _EntryPointSource):
        return "entry_point"
    if isinstance(source, _DevPathSource):
        return "dev_scan"
    return type(source).__name__


def _source_location(source: object) -> str | None:
    if isinstance(source, _EntryPointSource):
        return source.group
    if isinstance(source, _DevPathSource):
        return str(source.path)
    return None


def discover_components(
    *,
    groups: Sequence[str] | None = None,
    include_legacy_group: bool = False,
    include_dev_scan: bool = True,
    dev_scan_paths: Sequence[Path | str] | None = None,
    precedence: DiscoveryPrecedencePolicy | None = None,
    duplicate_policy: DuplicatePolicy = DuplicatePolicy.WARN,
) -> DiscoveryReport:
    """Discover components and return a deterministic report.

    Args:
        groups: Entry-point groups to scan. Defaults to all stable component
            groups defined by `DEFAULT_ENTRY_POINT_GROUPS`.
        include_legacy_group: Include the backward-compatible
            `polisyos.components` group.
        include_dev_scan: Scan local development roots after entry points.
        dev_scan_paths: Optional explicit roots/files to scan instead of
            `POLISYOS_PACKS_PATHS`.
        precedence: Duplicate precedence policy. By default dev scans override
            entry-point declarations for the same `component_id`.
        duplicate_policy: Collector-level handling for duplicate discoveries.

    Returns:
        `DiscoveryReport` with sorted components, duplicate decisions, and
        source-specific errors.
    """
    report = DiscoveryReport()
    precedence_policy = precedence or DiscoveryPrecedencePolicy()
    selected_groups = list(DEFAULT_ENTRY_POINT_GROUPS if groups is None else groups)
    if include_legacy_group and LEGACY_ENTRY_POINT_GROUP not in selected_groups:
        selected_groups.append(LEGACY_ENTRY_POINT_GROUP)

    sources: list[_EntryPointSource | _DevPathSource] = [
        _EntryPointSource(group=group) for group in selected_groups
    ]
    if include_dev_scan:
        paths = list(dev_scan_paths) if dev_scan_paths is not None else _default_dev_scan_paths()
        sources.extend(_DevPathSource(path=Path(base)) for base in paths)

    index: dict[str, DiscoveredComponent] = {}
    collector = BaseDiscovery[DiscoveredComponent, DiscoveryError](
        sources=sources,
        on_source_error=lambda source, exc: DiscoveryError(
            source=_source_kind(source),
            item=_source_location(source),
            error_type=type(exc).__name__,
            message=str(exc),
            details={"traceback": format_traceback()},
        ),
    )
    batches, sources_processed = collector.collect()
    report.sources_processed = sources_processed

    for batch in batches:
        report.errors.extend(batch.errors)
        for discovered in batch.items:
            _register_discovered(
                discovered,
                index=index,
                report=report,
                precedence=precedence_policy,
                duplicate_policy=duplicate_policy,
            )

    report.components = sorted(
        index.values(),
        key=lambda item: (
            str(item.metadata.component_id),
            item.source.source_type,
            item.source.location,
        ),
    )
    return report


def discover_entry_points(*, group: str = ENTRY_POINT_GROUP) -> list[Component]:
    """Discover components from one entry-point group for legacy callers."""
    report = discover_components(
        groups=[group],
        include_legacy_group=False,
        include_dev_scan=False,
    )
    return [item.component for item in report.components]


def discover_dev_components(root: Path) -> list[ComponentMetadata]:
    """Scan one local root and return discovered metadata objects for legacy callers."""
    report = discover_components(
        groups=[],
        include_dev_scan=True,
        dev_scan_paths=[root],
    )
    return [item.metadata for item in report.components]


def _register_discovered(
    discovered: DiscoveredComponent,
    *,
    index: dict[str, DiscoveredComponent],
    report: DiscoveryReport,
    precedence: DiscoveryPrecedencePolicy,
    duplicate_policy: DuplicatePolicy,
) -> None:
    component_id = str(discovered.metadata.component_id)
    existing = index.get(component_id)
    if existing is None:
        index[component_id] = discovered
        return

    replacement = _choose_preferred(
        left=existing,
        right=discovered,
        precedence=precedence,
    )

    kept = replacement
    dropped = discovered if replacement is existing else existing
    if replacement is discovered:
        index[component_id] = discovered

    duplicate = DiscoveryDuplicate(
        component_id=component_id,
        kept_source=kept.source,
        dropped_source=dropped.source,
        reason="source_precedence" if replacement is not existing else "duplicate_component_id",
    )

    if duplicate_policy == DuplicatePolicy.IGNORE:
        report.duplicates.append(duplicate)
        return
    if duplicate_policy == DuplicatePolicy.WARN:
        report.duplicates.append(duplicate)
        return

    report.errors.append(
        DiscoveryError(
            source="registry",
            item=component_id,
            error_type="DuplicateComponentId",
            message=f"Duplicate component_id discovered: {component_id}",
            details={
                "kept": kept.source.location,
                "dropped": dropped.source.location,
            },
        )
    )


def _choose_preferred(
    *,
    left: DiscoveredComponent,
    right: DiscoveredComponent,
    precedence: DiscoveryPrecedencePolicy,
) -> DiscoveredComponent:
    if not precedence.dev_scan_wins_over_entry_points:
        return left

    left_dev = left.source.source_type == "dev_scan"
    right_dev = right.source.source_type == "dev_scan"
    if left_dev == right_dev:
        return left
    if right_dev:
        return right
    return left


def _discover_group(*, group: str, errors: list[DiscoveryError]) -> list[DiscoveredComponent]:
    discovered: list[DiscoveredComponent] = []
    expected_kind = ENTRY_POINT_KIND_BY_GROUP.get(group)

    try:
        group_eps = list_entry_points(group=group)
    except _DISCOVERY_BOUNDARY_ERRORS as exc:
        errors.append(
            DiscoveryError(
                source="entry_point",
                item=group,
                error_type=type(exc).__name__,
                message=str(exc),
            )
        )
        return discovered

    for ep in sorted(group_eps, key=lambda item: (item.name, item.value)):
        source = DiscoverySourceInfo(
            source_type="entry_point",
            location=f"{ep.module}:{ep.attr}" if hasattr(ep, "module") else ep.value,
            group=group,
            entry_point=ep.name,
        )
        try:
            loaded = ep.load()
        except _DISCOVERY_BOUNDARY_ERRORS as exc:
            errors.append(
                DiscoveryError(
                    source="entry_point",
                    item=ep.name,
                    error_type=type(exc).__name__,
                    message=str(exc),
                    details={"group": group},
                )
            )
            continue

        component = _materialize_component(loaded)
        if component is None:
            errors.append(
                DiscoveryError(
                    source="entry_point",
                    item=ep.name,
                    error_type="InvalidEntryPoint",
                    message="Entry point must expose Component or zero-arg factory",
                    details={"group": group},
                )
            )
            continue

        metadata_obj = component.metadata
        if expected_kind is not None and metadata_obj.kind != expected_kind:
            errors.append(
                DiscoveryError(
                    source="entry_point",
                    item=ep.name,
                    error_type="KindMismatch",
                    message=(
                        f"entry point group {group!r} expects kind={expected_kind.value!r}, "
                        f"got {metadata_obj.kind.value!r}"
                    ),
                )
            )
            continue

        discovered.append(
            DiscoveredComponent(
                metadata=metadata_obj,
                component=component,
                source=source,
            )
        )

    return discovered


def _default_dev_scan_paths() -> list[Path]:
    paths: list[Path] = []
    if DEFAULT_DEV_SCAN_ROOT is not None and DEFAULT_DEV_SCAN_ROOT.exists():
        paths.append(DEFAULT_DEV_SCAN_ROOT)

    env_raw = os.getenv("POLISYOS_PACKS_PATHS", "").strip()
    if env_raw:
        for item in env_raw.split(os.pathsep):
            candidate = Path(item.strip())
            if candidate.exists():
                paths.append(candidate)

    unique: dict[Path, None] = {}
    for path in paths:
        unique[path.resolve()] = None
    return list(unique.keys())


def _discover_dev_path(path: Path, *, errors: list[DiscoveryError]) -> list[DiscoveredComponent]:
    discovered: list[DiscoveredComponent] = []

    candidates: list[Path] = []
    if path.is_file() and path.name == "components.py":
        candidates.append(path)
    elif (path / "components.py").is_file():
        candidates.append(path / "components.py")
    elif path.is_dir():
        for child in sorted(path.iterdir(), key=lambda item: item.name):
            if child.is_dir() and (child / "components.py").is_file():
                candidates.append(child / "components.py")

    for components_file in candidates:
        source = DiscoverySourceInfo(
            source_type="dev_scan",
            location=str(components_file),
        )
        module_name = _module_name_for_path(components_file)
        module = _load_module_from_file(components_file, module_name=module_name, errors=errors)
        if module is None:
            continue

        declared = getattr(module, "__polisyos_components__", None)
        if not isinstance(declared, Iterable):
            errors.append(
                DiscoveryError(
                    source="dev_scan",
                    item=str(components_file),
                    error_type="MissingDeclaration",
                    message="components.py must define iterable __polisyos_components__",
                )
            )
            continue

        for idx, item in enumerate(declared):
            component = _materialize_component(item)
            if component is None:
                errors.append(
                    DiscoveryError(
                        source="dev_scan",
                        item=f"{components_file}:{idx}",
                        error_type="InvalidDeclaration",
                        message="__polisyos_components__ item must be Component or factory",
                    )
                )
                continue
            discovered.append(
                DiscoveredComponent(
                    metadata=component.metadata,
                    component=component,
                    source=source,
                )
            )

    return discovered


def _module_name_for_path(path: Path) -> str:
    return discovery_module_name(
        path,
        prefix=DISCOVERY_MODULE_PREFIX,
        algorithm="sha1",
        digest_length=40,
    )


def _load_module_from_file(
    path: Path,
    *,
    module_name: str,
    errors: list[DiscoveryError],
) -> ModuleType | None:
    try:
        module = load_module_from_file(path, module_name=module_name)
    except _DISCOVERY_BOUNDARY_ERRORS as exc:
        errors.append(
            DiscoveryError(
                source="dev_scan",
                item=str(path),
                error_type=type(exc).__name__,
                message=str(exc),
                details={"traceback": format_traceback()},
            )
        )
        return None
    finally:
        sys.modules.pop(module_name, None)

    return module


def _materialize_component(value: object) -> Component | None:
    if isinstance(value, Component):
        return value
    if callable(value):
        try:
            created = value()
        except (AttributeError, ImportError, RuntimeError, TypeError, ValueError) as exc:
            logger.warning("Component factory materialization failed: %s", exc)
            return None
        if isinstance(created, Component):
            return created
    return None
