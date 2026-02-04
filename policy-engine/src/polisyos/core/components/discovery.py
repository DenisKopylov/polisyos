from __future__ import annotations

import hashlib
import importlib.util
import os
import sys
from dataclasses import dataclass, field
from enum import Enum
from importlib import metadata
from pathlib import Path
from typing import Any, Iterable, Sequence

from .metadata import ComponentKind
from .protocols import Component

ENTRY_POINT_GROUP_IR_FRAGMENTS = "polisyos.ir_fragments"
ENTRY_POINT_GROUP_FOUNDRY_METHODS = "polisyos.foundry_methods"
ENTRY_POINT_GROUP_SCHOLAR_EXTRACTORS = "polisyos.scholar_extractors"
ENTRY_POINT_GROUP_LEX_EXTRACTORS = "polisyos.lex_extractors"
ENTRY_POINT_GROUP_LEX_EVALUATORS = "polisyos.lex_evaluators"
ENTRY_POINT_GROUP_SCIENTIST_NODES = "polisyos.scientist_nodes"
ENTRY_POINT_GROUP_NORM_PACK_PROVIDERS = "polisyos.norm_pack_providers"

LEGACY_ENTRY_POINT_GROUP = "polisyos.components"
ENTRY_POINT_GROUP = LEGACY_ENTRY_POINT_GROUP  # backwards compatibility

ENTRY_POINT_KIND_BY_GROUP: dict[str, ComponentKind] = {
    ENTRY_POINT_GROUP_IR_FRAGMENTS: ComponentKind.IR_FRAGMENT,
    ENTRY_POINT_GROUP_FOUNDRY_METHODS: ComponentKind.FOUNDRY_METHOD,
    ENTRY_POINT_GROUP_SCHOLAR_EXTRACTORS: ComponentKind.SCHOLAR_EXTRACTOR,
    ENTRY_POINT_GROUP_LEX_EXTRACTORS: ComponentKind.LEX_EXTRACTOR,
    ENTRY_POINT_GROUP_LEX_EVALUATORS: ComponentKind.LEX_EVALUATOR,
    ENTRY_POINT_GROUP_SCIENTIST_NODES: ComponentKind.SCIENTIST_NODE,
    ENTRY_POINT_GROUP_NORM_PACK_PROVIDERS: ComponentKind.NORM_PACK_PROVIDER,
}

DEFAULT_ENTRY_POINT_GROUPS: tuple[str, ...] = tuple(sorted(ENTRY_POINT_KIND_BY_GROUP.keys()))
DEFAULT_DEV_SCAN_ROOT = Path(__file__).resolve().parents[2] / "packs"
DISCOVERY_MODULE_PREFIX = "_polisyos_components_scan_"


class DuplicatePolicy(str, Enum):
    WARN = "warn"
    ERROR = "error"
    IGNORE = "ignore"


@dataclass(slots=True, frozen=True)
class DiscoverySourceInfo:
    source_type: str
    location: str
    group: str | None = None
    entry_point: str | None = None


@dataclass(slots=True)
class DiscoveredComponent:
    metadata: Any
    component: Component
    source: DiscoverySourceInfo


@dataclass(slots=True)
class DiscoveryDuplicate:
    component_id: str
    kept_source: DiscoverySourceInfo
    dropped_source: DiscoverySourceInfo
    reason: str


@dataclass(slots=True)
class DiscoveryError:
    source: str
    item: str | None
    error_type: str
    message: str
    details: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class DiscoveryPrecedencePolicy:
    dev_scan_wins_over_entry_points: bool = True


@dataclass(slots=True)
class DiscoveryReport:
    components: list[DiscoveredComponent] = field(default_factory=list)
    duplicates: list[DiscoveryDuplicate] = field(default_factory=list)
    errors: list[DiscoveryError] = field(default_factory=list)
    sources_processed: int = 0

    @property
    def success(self) -> bool:
        return len(self.errors) == 0


def discover_components(
    *,
    groups: Sequence[str] | None = None,
    include_legacy_group: bool = False,
    include_dev_scan: bool = True,
    dev_scan_paths: Sequence[Path | str] | None = None,
    precedence: DiscoveryPrecedencePolicy | None = None,
    duplicate_policy: DuplicatePolicy = DuplicatePolicy.WARN,
) -> DiscoveryReport:
    report = DiscoveryReport()
    precedence_policy = precedence or DiscoveryPrecedencePolicy()
    selected_groups = list(DEFAULT_ENTRY_POINT_GROUPS if groups is None else groups)
    if include_legacy_group and LEGACY_ENTRY_POINT_GROUP not in selected_groups:
        selected_groups.append(LEGACY_ENTRY_POINT_GROUP)

    index: dict[str, DiscoveredComponent] = {}

    for group in selected_groups:
        report.sources_processed += 1
        for discovered in _discover_group(group=group, report=report):
            _register_discovered(
                discovered,
                index=index,
                report=report,
                precedence=precedence_policy,
                duplicate_policy=duplicate_policy,
            )

    if include_dev_scan:
        paths = list(dev_scan_paths) if dev_scan_paths is not None else _default_dev_scan_paths()
        for base in paths:
            report.sources_processed += 1
            for discovered in _discover_dev_path(Path(base), report=report):
                _register_discovered(
                    discovered,
                    index=index,
                    report=report,
                    precedence=precedence_policy,
                    duplicate_policy=duplicate_policy,
                )

    report.components = sorted(
        index.values(),
        key=lambda item: (str(item.metadata.component_id), item.source.source_type, item.source.location),
    )
    return report


def discover_entry_points(*, group: str = ENTRY_POINT_GROUP) -> list[Component]:
    """Legacy helper: discover components from one entry point group."""
    report = discover_components(
        groups=[group],
        include_legacy_group=False,
        include_dev_scan=False,
    )
    return [item.component for item in report.components]


def discover_dev_components(root: Path) -> list[Any]:
    """Legacy helper: scan one root path and return component metadata entries."""
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


def _discover_group(*, group: str, report: DiscoveryReport) -> list[DiscoveredComponent]:
    discovered: list[DiscoveredComponent] = []
    expected_kind = ENTRY_POINT_KIND_BY_GROUP.get(group)

    try:
        eps = metadata.entry_points()
        group_eps = eps.select(group=group) if hasattr(eps, "select") else eps.get(group, [])
    except Exception as exc:
        report.errors.append(
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
        except Exception as exc:
            report.errors.append(
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
            report.errors.append(
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
            report.errors.append(
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
    if DEFAULT_DEV_SCAN_ROOT.exists():
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


def _discover_dev_path(path: Path, *, report: DiscoveryReport) -> list[DiscoveredComponent]:
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
        module = _load_module_from_file(components_file, module_name=module_name, report=report)
        if module is None:
            continue

        declared = getattr(module, "__polisyos_components__", None)
        if not isinstance(declared, Iterable):
            report.errors.append(
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
                report.errors.append(
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
    digest = hashlib.sha1(str(path.resolve()).encode("utf-8")).hexdigest()
    stem = path.parent.name.replace("-", "_")
    return f"{DISCOVERY_MODULE_PREFIX}{stem}_{digest}"


def _load_module_from_file(path: Path, *, module_name: str, report: DiscoveryReport) -> Any | None:
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        report.errors.append(
            DiscoveryError(
                source="dev_scan",
                item=str(path),
                error_type="ImportSpecError",
                message="failed to create module spec",
            )
        )
        return None

    module = importlib.util.module_from_spec(spec)
    try:
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
    except Exception as exc:
        report.errors.append(
            DiscoveryError(
                source="dev_scan",
                item=str(path),
                error_type=type(exc).__name__,
                message=str(exc),
            )
        )
        return None
    finally:
        sys.modules.pop(module_name, None)

    return module


def _materialize_component(value: Any) -> Component | None:
    if isinstance(value, Component):
        return value
    if callable(value):
        try:
            created = value()
        except Exception:
            return None
        if isinstance(created, Component):
            return created
    return None
