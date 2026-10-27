"""Discover plugin components from Python entry points and local dev scan roots.

Entry-point groups are the stable package-install boundary, while
`POLISYOS_PACKS_PATHS`/`dev_scan_paths` provide a local development override
for unpacked component repositories. Duplicate handling is deterministic and
reported through `DiscoveryReport`.
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import re
import sys
from collections.abc import Callable, Iterable, Iterator, Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from packaging.utils import InvalidName, canonicalize_name
from packaging.version import InvalidVersion, Version

from polisyos.common.logger import get_logger
from polisyos.core.discovery import (
    BaseDiscovery,
    DuplicatePolicy,
    discovery_module_name,
    format_traceback,
    list_entry_points,
    load_module_from_file,
)

from ._provider_origin import (
    ProviderOriginBinding,
    bind_component_factory_origin,
    bind_loaded_entry_point_target,
    preflight_entry_point_target,
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
ENTRY_POINT_GROUP_SCIENTIST_GOVERNANCE_PASSES = "polisyos.scientist_governance_passes"
ENTRY_POINT_GROUP_SCIENTIST_NODES = "polisyos.scientist_nodes"
ENTRY_POINT_GROUP_DATA_FORGE_DOMAINS = "polisyos.data_forge_domains"
ENTRY_POINT_GROUP_LEX_NORMPACKS = "polisyos.lex_normpacks"
ENTRY_POINT_GROUP_NORM_PACK_PROVIDERS = "polisyos.norm_pack_providers"
ENTRY_POINT_GROUP_RUNTIME_MIDDLEWARES = "polisyos.runtime_middlewares"

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
    ENTRY_POINT_GROUP_DATA_FORGE_DOMAINS: ComponentKind.DATA_FORGE_DOMAIN,
    ENTRY_POINT_GROUP_LEX_NORMPACKS: ComponentKind.NORM_PACK_PROVIDER,
    ENTRY_POINT_GROUP_NORM_PACK_PROVIDERS: ComponentKind.NORM_PACK_PROVIDER,
    ENTRY_POINT_GROUP_RUNTIME_MIDDLEWARES: ComponentKind.RUNTIME_MIDDLEWARE,
}

DEFAULT_ENTRY_POINT_GROUPS: tuple[str, ...] = tuple(sorted(ENTRY_POINT_KIND_BY_GROUP.keys()))
EXTENSION_ENTRY_POINT_GROUPS: tuple[str, ...] = (
    ENTRY_POINT_GROUP_FABRIC_CONNECTORS,
    ENTRY_POINT_GROUP_SCIENTIST_GOVERNANCE_PASSES,
    ENTRY_POINT_GROUP_FOUNDRY_METHODS,
    ENTRY_POINT_GROUP_SCIENTIST_NODES,
    ENTRY_POINT_GROUP_DATA_FORGE_DOMAINS,
    ENTRY_POINT_GROUP_LEX_NORMPACKS,
    ENTRY_POINT_GROUP_RUNTIME_MIDDLEWARES,
)
DEFAULT_DEV_SCAN_ROOT: Path | None = None
DISCOVERY_MODULE_PREFIX = "_polisyos_components_scan_"


@dataclass(slots=True, frozen=True)
class DeclaredBuiltinLoader:
    """Reference a declared builtin provider by target and entry-point group.

    The group selects the expected `ComponentKind` and is retained as source
    identity for each accepted component.
    """

    target: str
    group: str


BuiltinComponentLoader = Callable[[], object]
BuiltinLoaderSpec = (
    BuiltinComponentLoader
    | tuple[str, BuiltinComponentLoader | DeclaredBuiltinLoader]
    | DeclaredBuiltinLoader
)
PredicateProvenanceClassification = Literal[
    "recomputed",
    "independently_reconciled",
    "consumer_asserted",
    "institutionally_supplied",
    "not_established",
]


@dataclass(slots=True, frozen=True)
class DiscoveryPredicateProvenance:
    """Freeze how one load-bearing discovery predicate was established."""

    predicate: str
    classification: PredicateProvenanceClassification

    def as_dict(self) -> dict[str, str]:
        """Return a canonical JSON-compatible representation."""
        return {
            "predicate": self.predicate,
            "classification": self.classification,
        }


@dataclass(slots=True, frozen=True)
class DiscoveryEntryPointIdentity:
    """Bind one enumerated entry point to its installed distribution identity."""

    group: str
    name: str
    value: str
    distribution_name: str | None
    distribution_version: str | None
    entry_points_sha256: str | None
    direct_url_sha256: str | None
    editable_install: bool | None
    source_byte_closure: PredicateProvenanceClassification

    @property
    def distribution_identity_is_bound(self) -> bool:
        """Return whether complete owner and entry-point identity fields are valid."""
        required = (
            self.group,
            self.name,
            self.value,
            self.distribution_name,
            self.distribution_version,
            self.entry_points_sha256,
        )
        if any(not isinstance(value, str) or not value.strip() for value in required):
            return False
        if self.distribution_version != self.distribution_version.strip():
            return False
        if re.fullmatch(r"sha256:[0-9a-f]{64}", self.entry_points_sha256) is None:
            return False
        try:
            normalized_name = canonicalize_name(self.distribution_name, validate=True)
            Version(self.distribution_version)
        except (InvalidName, InvalidVersion):
            return False
        return normalized_name == self.distribution_name

    def as_dict(self) -> dict[str, str | bool | None]:
        """Return a canonical JSON-compatible representation."""
        return {
            "group": self.group,
            "name": self.name,
            "value": self.value,
            "distribution_name": self.distribution_name,
            "distribution_version": self.distribution_version,
            "entry_points_sha256": self.entry_points_sha256,
            "direct_url_sha256": self.direct_url_sha256,
            "editable_install": self.editable_install,
            "source_byte_closure": self.source_byte_closure,
        }


@dataclass(slots=True, frozen=True)
class DiscoveryDevScanRootIdentity:
    """Bind one declared development-scan root before loading its declarations."""

    root: str
    exists: bool
    path_kind: str
    candidate_count: int

    def as_dict(self) -> dict[str, str | bool | int]:
        """Return a canonical JSON-compatible representation."""
        return {
            "root": self.root,
            "exists": self.exists,
            "path_kind": self.path_kind,
            "candidate_count": self.candidate_count,
        }


@dataclass(slots=True, frozen=True)
class DiscoveryDevScanFileIdentity:
    """Content-bind one development declaration file consumed by discovery."""

    root: str
    path: str
    byte_count: int
    sha256: str

    def as_dict(self) -> dict[str, str | int]:
        """Return a canonical JSON-compatible representation."""
        return {
            "root": self.root,
            "path": self.path,
            "byte_count": self.byte_count,
            "sha256": self.sha256,
        }


@dataclass(slots=True, frozen=True)
class DiscoveryComponentIdentity:
    """Bind one winning component declaration and its discovery source."""

    component_id: str
    metadata_sha256: str
    source_type: str
    location: str
    group: str | None
    entry_point: str | None

    def as_dict(self) -> dict[str, str | None]:
        """Return a canonical JSON-compatible representation."""
        return {
            "component_id": self.component_id,
            "metadata_sha256": self.metadata_sha256,
            "source_type": self.source_type,
            "location": self.location,
            "group": self.group,
            "entry_point": self.entry_point,
        }


@dataclass(slots=True, frozen=True)
class DiscoveryDeclaredBuiltinLoaderIdentity:
    """Bind one declared builtin loader before its target is imported or called."""

    name: str
    target: str
    group: str

    def as_dict(self) -> dict[str, str]:
        """Return a canonical JSON-compatible declaration identity."""
        return {"name": self.name, "target": self.target, "group": self.group}


@dataclass(slots=True, frozen=True)
class ComponentDiscoveryManifest:
    """Bind discovered inputs and name any source closure not established."""

    schema_version: str
    manifest_id: str
    entry_point_groups: tuple[str, ...]
    builtin_loaders: tuple[str, ...]
    dev_scan_enabled: bool
    duplicate_policy: str
    dev_scan_wins_over_entry_points: bool
    entry_points: tuple[DiscoveryEntryPointIdentity, ...]
    dev_scan_roots: tuple[DiscoveryDevScanRootIdentity, ...]
    dev_scan_files: tuple[DiscoveryDevScanFileIdentity, ...]
    components: tuple[DiscoveryComponentIdentity, ...]
    unbound_inputs: tuple[str, ...]
    predicate_provenance: tuple[DiscoveryPredicateProvenance, ...]
    declared_builtin_loaders: tuple[DiscoveryDeclaredBuiltinLoaderIdentity, ...] = ()
    provider_origin_bindings: tuple[ProviderOriginBinding, ...] = ()

    @property
    def is_bound(self) -> bool:
        """Return whether every load-bearing source predicate was established."""
        admissible = {"recomputed", "independently_reconciled"}
        return not self.unbound_inputs and all(
            row.classification in admissible for row in self.predicate_provenance
        )

    def as_dict(self) -> dict[str, object]:
        """Return the canonical content plus its derived ``manifest_id``."""
        return {"manifest_id": self.manifest_id, **self.content_payload()}

    def content_payload(self) -> dict[str, object]:
        """Return the canonical payload whose SHA-256 derives ``manifest_id``."""
        payload: dict[str, object] = {
            "schema_version": self.schema_version,
            "entry_point_groups": list(self.entry_point_groups),
            "builtin_loaders": list(self.builtin_loaders),
            "dev_scan_enabled": self.dev_scan_enabled,
            "duplicate_policy": self.duplicate_policy,
            "dev_scan_wins_over_entry_points": self.dev_scan_wins_over_entry_points,
            "entry_points": [row.as_dict() for row in self.entry_points],
            "dev_scan_roots": [row.as_dict() for row in self.dev_scan_roots],
            "dev_scan_files": [row.as_dict() for row in self.dev_scan_files],
            "components": [row.as_dict() for row in self.components],
            "unbound_inputs": list(self.unbound_inputs),
            "predicate_provenance": [row.as_dict() for row in self.predicate_provenance],
        }
        if self.schema_version in {
            "policyos.component_discovery_manifest.v2",
            "policyos.component_discovery_manifest.v3",
        }:
            payload["declared_builtin_loaders"] = [
                row.as_dict() for row in self.declared_builtin_loaders
            ]
        if self.schema_version == "policyos.component_discovery_manifest.v3":
            payload["provider_origin_bindings"] = [
                row.as_dict() for row in self.provider_origin_bindings
            ]
        return payload


@dataclass(slots=True, frozen=True)
class DiscoverySourceInfo:
    """Describe where a component declaration was loaded from."""

    source_type: str
    location: str
    group: str | None = None
    entry_point: str | None = None
    provider_origin_binding: ProviderOriginBinding | None = None


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
    manifest: ComponentDiscoveryManifest | None = None

    @property
    def success(self) -> bool:
        return len(self.errors) == 0


@dataclass(slots=True)
class _EntryPointOutcome:
    """Account for one enumerated entry point through provider and factory binding."""

    identity: DiscoveryEntryPointIdentity
    bindings: list[ProviderOriginBinding] = field(default_factory=list)
    component_result_count: int = 0
    component_results_complete: bool = False
    provider_status: Literal["verified", "refused", "not_established"] = "not_established"
    factory_status: Literal["verified", "delegated", "not_established"] = "not_established"


@dataclass(slots=True)
class _EntryPointSource:
    group: str
    errors: list[DiscoveryError] = field(default_factory=list)
    entry_points: list[DiscoveryEntryPointIdentity] = field(default_factory=list)
    provider_origin_bindings: list[ProviderOriginBinding] = field(default_factory=list)
    entry_point_outcomes: list[_EntryPointOutcome] = field(default_factory=list)
    enumerated_entry_point_count: int | None = None
    enumeration_established: bool = False

    def discover(self) -> Iterator[DiscoveredComponent]:
        self.errors.clear()
        self.entry_points.clear()
        self.provider_origin_bindings.clear()
        self.entry_point_outcomes.clear()
        self.enumerated_entry_point_count = None
        self.enumeration_established = False
        return iter(
            _discover_group(
                group=self.group,
                errors=self.errors,
                identities=self.entry_points,
                owner_source=self,
            )
        )


@dataclass(slots=True)
class _DevPathSource:
    path: Path
    errors: list[DiscoveryError] = field(default_factory=list)
    root_identity: DiscoveryDevScanRootIdentity | None = None
    file_identities: list[DiscoveryDevScanFileIdentity] = field(default_factory=list)

    def discover(self) -> Iterator[DiscoveredComponent]:
        self.errors.clear()
        self.root_identity = None
        self.file_identities.clear()
        return iter(
            _discover_dev_path(
                self.path,
                errors=self.errors,
                source=self,
            )
        )


@dataclass(slots=True)
class _BuiltinLoaderSource:
    name: str
    loader: BuiltinComponentLoader | DeclaredBuiltinLoader
    errors: list[DiscoveryError] = field(default_factory=list)
    declaration_identity: DiscoveryDeclaredBuiltinLoaderIdentity | None = field(
        init=False,
        default=None,
    )

    def __post_init__(self) -> None:
        if isinstance(self.loader, DeclaredBuiltinLoader):
            self.declaration_identity = DiscoveryDeclaredBuiltinLoaderIdentity(
                name=self.name,
                target=self.loader.target,
                group=self.loader.group,
            )

    def discover(self) -> Iterator[DiscoveredComponent]:
        self.errors.clear()
        return iter(
            _discover_builtin_loader(
                name=self.name,
                loader=self.loader,
                errors=self.errors,
            )
        )


def _entry_point_source_is_accounted(source: _EntryPointSource) -> bool:
    """Require one completed outcome for every fully enumerated entry point."""
    count = source.enumerated_entry_point_count
    if not source.enumeration_established or count is None:
        return False
    if count != len(source.entry_points) or count != len(source.entry_point_outcomes):
        return False
    return all(
        identity == outcome.identity
        for identity, outcome in zip(source.entry_points, source.entry_point_outcomes, strict=True)
    )


def _entry_point_bindings_are_accounted(source: _EntryPointSource) -> bool:
    """Reconcile every provider-binding row to exactly one entry-point outcome."""
    tracked = [
        id(binding) for outcome in source.entry_point_outcomes for binding in outcome.bindings
    ]
    recorded = [id(binding) for binding in source.provider_origin_bindings]
    return len(tracked) == len(recorded) and sorted(tracked) == sorted(recorded)


def _fabric_provider_origin_is_accounted(source: _EntryPointSource) -> bool:
    if not _entry_point_source_is_accounted(source) or not _entry_point_bindings_are_accounted(
        source
    ):
        return False
    return all(
        outcome.bindings
        and outcome.provider_status == "verified"
        and all(binding.status == "verified" for binding in outcome.bindings)
        for outcome in source.entry_point_outcomes
    )


def _fabric_factory_dispatch_is_accounted(source: _EntryPointSource) -> bool:
    if not _entry_point_source_is_accounted(source) or not _entry_point_bindings_are_accounted(
        source
    ):
        return False
    if source.enumerated_entry_point_count == 0:
        return True
    for outcome in source.entry_point_outcomes:
        component_bindings = [
            binding for binding in outcome.bindings if binding.component_id is not None
        ]
        if (
            outcome.component_result_count <= 0
            or len(component_bindings) != outcome.component_result_count
            or not outcome.component_results_complete
            or outcome.factory_status not in {"verified", "delegated"}
            or any(
                binding.status != "verified"
                or binding.component_factory_status not in {"verified", "delegated"}
                for binding in component_bindings
            )
        ):
            return False
    return True


def _record_provider_binding(
    source: _EntryPointSource,
    outcome: _EntryPointOutcome,
    binding: ProviderOriginBinding,
) -> None:
    source.provider_origin_bindings.append(binding)
    outcome.bindings.append(binding)


def _source_kind(source: object) -> str:
    if isinstance(source, _EntryPointSource):
        return "entry_point"
    if isinstance(source, _DevPathSource):
        return "dev_scan"
    if isinstance(source, _BuiltinLoaderSource):
        return "builtin_loader"
    return type(source).__name__


def _source_location(source: object) -> str | None:
    if isinstance(source, _EntryPointSource):
        return source.group
    if isinstance(source, _DevPathSource):
        return str(source.path)
    if isinstance(source, _BuiltinLoaderSource):
        return source.name
    return None


def discover_components(
    *,
    groups: Sequence[str] | None = None,
    include_legacy_group: bool = False,
    include_dev_scan: bool = True,
    dev_scan_paths: Sequence[Path | str] | None = None,
    builtin_loaders: Sequence[BuiltinLoaderSpec] | None = None,
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
        builtin_loaders: Optional in-process loaders for built-in components.
            Builtins registered this way use the same materialization,
            duplicate handling, and provenance path as external components.
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

    sources: list[_EntryPointSource | _DevPathSource | _BuiltinLoaderSource] = [
        _EntryPointSource(group=group) for group in selected_groups
    ]
    sources.extend(
        _BuiltinLoaderSource(*_coerce_builtin_loader_spec(spec)) for spec in builtin_loaders or ()
    )
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
    report.manifest = _build_discovery_manifest(
        sources=sources,
        report=report,
        selected_groups=selected_groups,
        include_dev_scan=include_dev_scan,
        precedence=precedence_policy,
        duplicate_policy=duplicate_policy,
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


def _discover_group(
    *,
    group: str,
    errors: list[DiscoveryError],
    identities: list[DiscoveryEntryPointIdentity],
    owner_source: _EntryPointSource,
) -> list[DiscoveredComponent]:
    discovered: list[DiscoveredComponent] = []
    expected_kind = ENTRY_POINT_KIND_BY_GROUP.get(group)

    try:
        group_eps = list(list_entry_points(group=group))
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
    owner_source.enumerated_entry_point_count = len(group_eps)
    owner_source.enumeration_established = True

    identified_entry_points = [(_entry_point_identity(ep, group=group), ep) for ep in group_eps]
    identified_entry_points.sort(
        key=lambda item: (
            item[0].group,
            item[0].name,
            item[0].value,
            item[0].distribution_name or "",
            item[0].distribution_version or "",
            item[0].entry_points_sha256 or "",
            item[0].direct_url_sha256 or "",
        )
    )
    for identity, ep in identified_entry_points:
        identities.append(identity)
        outcome = _EntryPointOutcome(identity=identity)
        owner_source.entry_point_outcomes.append(outcome)
        try:
            module_name = getattr(ep, "module", None)
            module_attr = getattr(ep, "attr", None)
        except _DISCOVERY_BOUNDARY_ERRORS:
            module_name = module_attr = None
        location = (
            f"{module_name}:{module_attr}"
            if isinstance(module_name, str) and isinstance(module_attr, str)
            else identity.value or "<unknown>"
        )
        item_name = identity.name or None
        discovery_source = DiscoverySourceInfo(
            source_type="entry_point",
            location=location,
            group=group,
            entry_point=item_name,
        )
        binding: ProviderOriginBinding | None = None
        origin_context = None
        if group == ENTRY_POINT_GROUP_FABRIC_CONNECTORS:
            binding, origin_context = preflight_entry_point_target(
                ep,
                expected_distribution_name=identity.distribution_name,
                expected_distribution_version=identity.distribution_version,
                expected_identity_is_bound=identity.distribution_identity_is_bound,
                expected_group=identity.group,
                expected_name=identity.name,
                expected_value=identity.value,
                expected_entry_points_sha256=identity.entry_points_sha256,
                editable_install=identity.editable_install,
            )
            if origin_context is None:
                outcome.provider_status = binding.status
                _record_provider_binding(owner_source, outcome, binding)
                errors.append(
                    DiscoveryError(
                        source="entry_point",
                        item=item_name,
                        error_type=(
                            "ProviderOriginRefused"
                            if binding.status == "refused"
                            else "ProviderOriginNotEstablished"
                        ),
                        message=binding.reason_code or "provider origin was not established",
                        details={
                            "group": group,
                            "origin_status": binding.status,
                            "reason_code": binding.reason_code or "",
                        },
                    )
                )
                continue
        try:
            loaded = ep.load()
        except _DISCOVERY_BOUNDARY_ERRORS as exc:
            if binding is not None:
                failed_binding = replace(
                    binding,
                    status="not_established",
                    reason_code=f"entry_point_load_failed:{type(exc).__name__}",
                )
                outcome.provider_status = "not_established"
                _record_provider_binding(owner_source, outcome, failed_binding)
            errors.append(
                DiscoveryError(
                    source="entry_point",
                    item=item_name,
                    error_type=type(exc).__name__,
                    message=str(exc),
                    details={"group": group},
                )
            )
            continue

        if binding is not None and origin_context is not None:
            binding = bind_loaded_entry_point_target(
                origin_context,
                binding,
                loaded,
                is_component=isinstance(loaded, Component),
            )
            if binding.status != "verified":
                outcome.provider_status = binding.status
                _record_provider_binding(owner_source, outcome, binding)
                errors.append(
                    DiscoveryError(
                        source="entry_point",
                        item=item_name,
                        error_type=(
                            "ProviderOriginRefused"
                            if binding.status == "refused"
                            else "ProviderOriginNotEstablished"
                        ),
                        message=binding.reason_code or "loaded provider origin was not established",
                        details={
                            "group": group,
                            "origin_status": binding.status,
                            "reason_code": binding.reason_code or "",
                        },
                    )
                )
                continue
            outcome.provider_status = "verified"

        components, rejected_result_count, invocation_completed = _materialize_components(loaded)
        outcome.component_result_count = len(components)
        outcome.component_results_complete = invocation_completed and (
            group != ENTRY_POINT_GROUP_FABRIC_CONNECTORS or rejected_result_count == 0
        )
        if rejected_result_count and group == ENTRY_POINT_GROUP_FABRIC_CONNECTORS:
            errors.append(
                DiscoveryError(
                    source="entry_point",
                    item=item_name,
                    error_type="InvalidEntryPointResult",
                    message="Entry point output contains values that are not Components",
                    details={"group": group, "rejected_result_count": rejected_result_count},
                )
            )
        if not components:
            if binding is not None:
                _record_provider_binding(owner_source, outcome, binding)
            errors.append(
                DiscoveryError(
                    source="entry_point",
                    item=item_name,
                    error_type="InvalidEntryPoint",
                    message="Entry point must expose Component, iterable of Components, or factory",
                    details={"group": group},
                )
            )
            continue

        for component in components:
            metadata_obj = component.metadata
            component_id = str(metadata_obj.component_id)
            source_info = discovery_source
            if binding is not None and origin_context is not None:
                component_binding = bind_component_factory_origin(
                    origin_context,
                    binding,
                    component,
                    component_id=component_id,
                )
                _record_provider_binding(owner_source, outcome, component_binding)
                source_info = replace(
                    discovery_source,
                    provider_origin_binding=component_binding,
                )
                if component_binding.component_factory_status == "not_established":
                    errors.append(
                        DiscoveryError(
                            source="entry_point",
                            item=item_name,
                            error_type="ProviderOriginNotEstablished",
                            message=(
                                component_binding.reason_code
                                or "component factory origin was not established"
                            ),
                            details={
                                "group": group,
                                "component_id": component_id,
                                "origin_status": component_binding.status,
                                "factory_status": component_binding.component_factory_status,
                            },
                        )
                    )
                    continue
            if expected_kind is not None and metadata_obj.kind != expected_kind:
                errors.append(
                    DiscoveryError(
                        source="entry_point",
                        item=item_name,
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
                    source=source_info,
                )
            )

        component_bindings = [row for row in outcome.bindings if row.component_id is not None]
        if len(component_bindings) == outcome.component_result_count and all(
            row.status == "verified" and row.component_factory_status in {"verified", "delegated"}
            for row in component_bindings
        ):
            outcome.factory_status = (
                "delegated"
                if any(row.component_factory_status == "delegated" for row in component_bindings)
                else "verified"
            )

    return discovered


def _default_dev_scan_paths() -> list[Path]:
    paths: list[Path] = []
    if DEFAULT_DEV_SCAN_ROOT is not None:
        paths.append(DEFAULT_DEV_SCAN_ROOT)

    env_raw = os.getenv("POLISYOS_PACKS_PATHS", "").strip()
    if env_raw:
        for item in env_raw.split(os.pathsep):
            candidate = Path(item.strip())
            if item.strip():
                paths.append(candidate)

    unique: dict[Path, None] = {}
    for path in paths:
        unique[path.resolve()] = None
    return list(unique.keys())


def _discover_dev_path(
    path: Path,
    *,
    errors: list[DiscoveryError],
    source: _DevPathSource,
) -> list[DiscoveredComponent]:
    discovered: list[DiscoveredComponent] = []

    resolved_root = path.resolve()
    candidates = _dev_component_candidates(path)
    source.root_identity = DiscoveryDevScanRootIdentity(
        root=str(resolved_root),
        exists=path.exists(),
        path_kind=("file" if path.is_file() else "directory" if path.is_dir() else "missing"),
        candidate_count=len(candidates),
    )

    for components_file in candidates:
        try:
            contributed_bytes = components_file.read_bytes()
        except OSError as exc:
            errors.append(
                DiscoveryError(
                    source="dev_scan",
                    item=str(components_file),
                    error_type=type(exc).__name__,
                    message=str(exc),
                )
            )
            continue
        contributed_sha256 = _sha256_bytes(contributed_bytes)
        source.file_identities.append(
            DiscoveryDevScanFileIdentity(
                root=str(resolved_root),
                path=str(components_file.resolve()),
                byte_count=len(contributed_bytes),
                sha256=contributed_sha256,
            )
        )
        discovery_source = DiscoverySourceInfo(
            source_type="dev_scan",
            location=str(components_file),
        )
        module_name = _module_name_for_path(components_file)
        module = _load_module_from_file(components_file, module_name=module_name, errors=errors)
        if module is None:
            continue
        try:
            loaded_sha256 = _sha256_bytes(components_file.read_bytes())
        except OSError as exc:
            errors.append(
                DiscoveryError(
                    source="dev_scan",
                    item=str(components_file),
                    error_type=type(exc).__name__,
                    message=str(exc),
                )
            )
            continue
        if loaded_sha256 != contributed_sha256:
            errors.append(
                DiscoveryError(
                    source="dev_scan",
                    item=str(components_file),
                    error_type="DevScanBytesChanged",
                    message="components.py changed while discovery was loading it",
                )
            )
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
                    source=discovery_source,
                )
            )

    return discovered


def _dev_component_candidates(path: Path) -> list[Path]:
    candidates: list[Path] = []
    if path.is_file() and path.name == "components.py":
        candidates.append(path)
    elif path.is_dir() and (path / "components.py").is_file():
        candidates.append(path / "components.py")
    elif path.is_dir():
        for child in sorted(path.iterdir(), key=lambda item: item.name):
            if child.is_dir() and (child / "components.py").is_file():
                candidates.append(child / "components.py")
    return candidates


def _entry_point_identity(ep: object, *, group: str) -> DiscoveryEntryPointIdentity:
    distribution = getattr(ep, "dist", None)
    distribution_name: str | None = None
    distribution_version: str | None = None
    entry_points_sha256: str | None = None
    direct_url_sha256: str | None = None
    editable_install: bool | None = None
    if distribution is not None:
        try:
            metadata_obj = getattr(distribution, "metadata", None)
            metadata_get = getattr(metadata_obj, "get", None)
            raw_name = metadata_get("Name") if callable(metadata_get) else None
        except (AttributeError, LookupError, RuntimeError, TypeError, ValueError):
            raw_name = None
        if isinstance(raw_name, str) and raw_name:
            distribution_name = re.sub(
                r"[-_.]+",
                "-",
                raw_name.strip().lower(),
            )

        try:
            raw_version = getattr(distribution, "version", None)
        except (AttributeError, LookupError, RuntimeError, TypeError, ValueError):
            raw_version = None
        if isinstance(raw_version, str) and raw_version:
            distribution_version = raw_version

        try:
            read_text = getattr(distribution, "read_text", None)
        except (AttributeError, LookupError, RuntimeError, TypeError, ValueError):
            read_text = None
        if callable(read_text):
            try:
                entry_points_text = read_text("entry_points.txt")
            except (LookupError, OSError, RuntimeError, TypeError, UnicodeError, ValueError):
                entry_points_text = None
            if isinstance(entry_points_text, str):
                entry_points_sha256 = _sha256_bytes(entry_points_text.encode("utf-8"))
            try:
                direct_url_text = read_text("direct_url.json")
            except (LookupError, OSError, RuntimeError, TypeError, UnicodeError, ValueError):
                direct_url_text = None
            if isinstance(direct_url_text, str):
                try:
                    direct_url_payload = json.loads(direct_url_text)
                except (json.JSONDecodeError, TypeError, ValueError):
                    direct_url_payload = None
                if isinstance(direct_url_payload, dict):
                    dir_info = direct_url_payload.get("dir_info")
                    if isinstance(dir_info, dict) and isinstance(dir_info.get("editable"), bool):
                        editable_install = bool(dir_info["editable"])
                # An editable direct URL is an installer-chosen address, not content identity.
                # Record the editable posture while leaving its source-byte closure unestablished.
                if editable_install is not True:
                    direct_url_sha256 = _sha256_bytes(direct_url_text.encode("utf-8"))
    try:
        raw_group = getattr(ep, "group", None)
        raw_name = getattr(ep, "name", None)
        raw_value = getattr(ep, "value", None)
    except (AttributeError, LookupError, RuntimeError, TypeError, ValueError):
        raw_group = raw_name = raw_value = None
    identity_group = raw_group if isinstance(raw_group, str) else ""
    if identity_group != group:
        identity_group = ""
    identity_name = raw_name if isinstance(raw_name, str) else ""
    identity_value = raw_value if isinstance(raw_value, str) else ""
    return DiscoveryEntryPointIdentity(
        group=identity_group,
        name=identity_name,
        value=identity_value,
        distribution_name=distribution_name,
        distribution_version=distribution_version,
        entry_points_sha256=entry_points_sha256,
        direct_url_sha256=direct_url_sha256,
        editable_install=editable_install,
        # Python entry-point factories may depend on arbitrary editable source,
        # transitive imports, and process state. Distribution metadata names that
        # input but cannot content-bind it. Governed consumers must quarantine it.
        source_byte_closure="not_established",
    )


def _build_discovery_manifest(
    *,
    sources: Sequence[_EntryPointSource | _DevPathSource | _BuiltinLoaderSource],
    report: DiscoveryReport,
    selected_groups: Sequence[str],
    include_dev_scan: bool,
    precedence: DiscoveryPrecedencePolicy,
    duplicate_policy: DuplicatePolicy,
) -> ComponentDiscoveryManifest:
    entry_points = tuple(
        sorted(
            (
                identity
                for source in sources
                if isinstance(source, _EntryPointSource)
                for identity in source.entry_points
            ),
            key=lambda row: (
                row.group or "",
                row.name or "",
                row.value or "",
                row.distribution_name or "",
                row.distribution_version or "",
                row.entry_points_sha256 or "",
                row.direct_url_sha256 or "",
            ),
        )
    )
    dev_scan_roots = tuple(
        source.root_identity
        for source in sources
        if isinstance(source, _DevPathSource) and source.root_identity is not None
    )
    dev_scan_files = tuple(
        sorted(
            (
                identity
                for source in sources
                if isinstance(source, _DevPathSource)
                for identity in source.file_identities
            ),
            key=lambda row: (row.root, row.path),
        )
    )
    components = tuple(
        DiscoveryComponentIdentity(
            component_id=str(row.metadata.component_id),
            metadata_sha256=_sha256_json(row.metadata.model_dump(mode="json")),
            source_type=row.source.source_type,
            location=row.source.location,
            group=row.source.group,
            entry_point=row.source.entry_point,
        )
        for row in report.components
    )
    builtin_loader_sources = tuple(
        source for source in sources if isinstance(source, _BuiltinLoaderSource)
    )
    builtin_loaders = tuple(source.name for source in builtin_loader_sources)
    declared_builtin_loader_rows: list[DiscoveryDeclaredBuiltinLoaderIdentity] = []
    for source in sources:
        if isinstance(source, _BuiltinLoaderSource) and source.declaration_identity is not None:
            declared_builtin_loader_rows.append(source.declaration_identity)
    declared_builtin_loaders = tuple(declared_builtin_loader_rows)
    fabric_sources = [
        source
        for source in sources
        if isinstance(source, _EntryPointSource)
        and source.group == ENTRY_POINT_GROUP_FABRIC_CONNECTORS
    ]
    provider_origin_bindings = tuple(
        sorted(
            (binding for source in fabric_sources for binding in source.provider_origin_bindings),
            key=lambda row: (
                row.group,
                row.name,
                row.value,
                row.component_id or "",
                row.status,
                row.reason_code or "",
            ),
        )
    )
    manifest_schema_version = (
        "policyos.component_discovery_manifest.v3"
        if fabric_sources
        else (
            "policyos.component_discovery_manifest.v2"
            if declared_builtin_loaders
            else "policyos.component_discovery_manifest.v1"
        )
    )
    unbound_inputs: list[str] = []
    entry_point_sources = tuple(
        source for source in sources if isinstance(source, _EntryPointSource)
    )
    entry_point_source_selection_is_accounted = tuple(
        source.group for source in entry_point_sources
    ) == tuple(selected_groups)
    if not entry_point_source_selection_is_accounted:
        unbound_inputs.append("entry_point_group_source_selection_not_reconciled")
    for source in builtin_loader_sources:
        if source.declaration_identity is None:
            unbound_inputs.append(f"builtin_loader_declaration_not_established:{source.name}")
    for source in entry_point_sources:
        if not source.enumeration_established:
            unbound_inputs.append(f"entry_point_group_enumeration_not_established:{source.group}")
        if not _entry_point_source_is_accounted(source):
            unbound_inputs.append(
                f"entry_point_group_outcome_accounting_not_established:{source.group}"
            )
        if (
            source.group == ENTRY_POINT_GROUP_FABRIC_CONNECTORS
            and not _entry_point_bindings_are_accounted(source)
        ):
            unbound_inputs.append(
                f"fabric_provider_origin_binding_accounting_not_established:{source.group}"
            )
    for row in entry_points:
        if not row.distribution_identity_is_bound:
            unbound_inputs.append(
                "entry_point_distribution_identity_not_established:"
                f"{row.group}:{row.name}:{row.value}"
            )
        if row.source_byte_closure not in {"recomputed", "independently_reconciled"}:
            unbound_inputs.append(
                "entry_point_source_byte_closure_not_established:"
                f"{row.group}:{row.name}:{row.value}"
            )
    for row in provider_origin_bindings:
        if row.status != "verified":
            unbound_inputs.append(
                "fabric_provider_entrypoint_origin_not_established:"
                f"{row.group}:{row.name}:{row.value}:{row.reason_code or row.status}"
            )
        if row.component_factory_status == "not_established":
            unbound_inputs.append(
                "fabric_component_factory_origin_not_established:"
                f"{row.group}:{row.name}:{row.value}:{row.component_id or '<no-component>'}"
            )
        elif row.component_factory_status == "delegated":
            unbound_inputs.append(
                "fabric_component_implementation_delegated:"
                f"{row.group}:{row.name}:{row.value}:{row.component_id or '<no-component>'}"
            )
    for row in dev_scan_roots:
        if not row.exists:
            unbound_inputs.append(f"dev_scan_root_not_found:{row.root}")
    for error in report.errors:
        error_context = (
            tuple(
                f"{key}={error.details[key]}"
                for key in ("group", "expected_kind", "actual_kind")
                if key in error.details
            )
            if error.source == "builtin_loader"
            else ()
        )
        error_identity = (
            f"discovery_error:{error.source}:{error.item or '<unknown>'}:{error.error_type}"
        )
        if error_context:
            error_identity += ":" + ":".join(error_context)
        unbound_inputs.append(error_identity)
    unbound_inputs = sorted(dict.fromkeys(unbound_inputs))
    source_policy_classification: PredicateProvenanceClassification = (
        "recomputed" if entry_point_source_selection_is_accounted else "not_established"
    )
    entry_point_enumeration_classification: PredicateProvenanceClassification = (
        "recomputed"
        if entry_point_source_selection_is_accounted
        and all(_entry_point_source_is_accounted(source) for source in entry_point_sources)
        else "not_established"
    )
    entry_points_classification: PredicateProvenanceClassification = (
        "recomputed"
        if entry_point_source_selection_is_accounted
        and all(_entry_point_source_is_accounted(source) for source in entry_point_sources)
        and all(row.distribution_identity_is_bound for row in entry_points)
        else "not_established"
    )
    entry_point_source_classification: PredicateProvenanceClassification = (
        "recomputed"
        if entry_point_source_selection_is_accounted
        and all(_entry_point_source_is_accounted(source) for source in entry_point_sources)
        and all(
            row.source_byte_closure in {"recomputed", "independently_reconciled"}
            for row in entry_points
        )
        else "not_established"
    )
    fabric_provider_origin_classification: PredicateProvenanceClassification = (
        "recomputed"
        if fabric_sources
        and all(_fabric_provider_origin_is_accounted(source) for source in fabric_sources)
        else "not_established"
    )
    fabric_component_factory_classification: PredicateProvenanceClassification = (
        "recomputed"
        if fabric_sources
        and all(_fabric_factory_dispatch_is_accounted(source) for source in fabric_sources)
        else "not_established"
    )
    dev_bytes_classification: PredicateProvenanceClassification = (
        "recomputed"
        if all(row.exists for row in dev_scan_roots)
        and not any(item.startswith("discovery_error:dev_scan:") for item in unbound_inputs)
        else "not_established"
    )
    component_classification: PredicateProvenanceClassification = (
        "recomputed" if not report.errors else "not_established"
    )
    dev_sources = [source for source in sources if isinstance(source, _DevPathSource)]
    dev_root_classification: PredicateProvenanceClassification = (
        "recomputed"
        if all(source.root_identity is not None for source in dev_sources)
        else "not_established"
    )
    dev_import_classification: PredicateProvenanceClassification = (
        "not_established" if dev_scan_files else "recomputed"
    )
    if dev_import_classification == "not_established":
        unbound_inputs.append("development_scan_import_closure_not_established")
        unbound_inputs.sort()
    predicate_provenance = (
        DiscoveryPredicateProvenance("source_policy", source_policy_classification),
        DiscoveryPredicateProvenance(
            "entry_point_group_enumeration",
            entry_point_enumeration_classification,
        ),
        DiscoveryPredicateProvenance(
            "entry_point_distribution_identity",
            entry_points_classification,
        ),
        DiscoveryPredicateProvenance(
            "entry_point_source_byte_closure",
            entry_point_source_classification,
        ),
        *(
            (
                DiscoveryPredicateProvenance(
                    "fabric_provider_entrypoint_record_binding",
                    fabric_provider_origin_classification,
                ),
                DiscoveryPredicateProvenance(
                    "fabric_component_factory_dispatch",
                    fabric_component_factory_classification,
                ),
            )
            if fabric_sources
            else ()
        ),
        DiscoveryPredicateProvenance(
            "development_scan_root_membership",
            dev_root_classification,
        ),
        DiscoveryPredicateProvenance(
            "development_scan_contributed_bytes",
            dev_bytes_classification,
        ),
        DiscoveryPredicateProvenance(
            "development_scan_import_closure",
            dev_import_classification,
        ),
        DiscoveryPredicateProvenance("duplicate_precedence", "recomputed"),
        DiscoveryPredicateProvenance(
            "discovered_component_membership",
            component_classification,
        ),
    )
    payload: dict[str, object] = {
        "schema_version": manifest_schema_version,
        "entry_point_groups": list(selected_groups),
        "builtin_loaders": list(builtin_loaders),
        "dev_scan_enabled": include_dev_scan,
        "duplicate_policy": duplicate_policy.value,
        "dev_scan_wins_over_entry_points": precedence.dev_scan_wins_over_entry_points,
        "entry_points": [row.as_dict() for row in entry_points],
        "dev_scan_roots": [row.as_dict() for row in dev_scan_roots],
        "dev_scan_files": [row.as_dict() for row in dev_scan_files],
        "components": [row.as_dict() for row in components],
        "unbound_inputs": unbound_inputs,
        "predicate_provenance": [row.as_dict() for row in predicate_provenance],
    }
    if manifest_schema_version in {
        "policyos.component_discovery_manifest.v2",
        "policyos.component_discovery_manifest.v3",
    }:
        payload["declared_builtin_loaders"] = [row.as_dict() for row in declared_builtin_loaders]
    if manifest_schema_version == "policyos.component_discovery_manifest.v3":
        payload["provider_origin_bindings"] = [row.as_dict() for row in provider_origin_bindings]
    manifest_id = _component_discovery_manifest_id(payload)
    return ComponentDiscoveryManifest(
        schema_version=manifest_schema_version,
        manifest_id=manifest_id,
        entry_point_groups=tuple(selected_groups),
        builtin_loaders=builtin_loaders,
        dev_scan_enabled=include_dev_scan,
        duplicate_policy=duplicate_policy.value,
        dev_scan_wins_over_entry_points=precedence.dev_scan_wins_over_entry_points,
        entry_points=entry_points,
        dev_scan_roots=dev_scan_roots,
        dev_scan_files=dev_scan_files,
        components=components,
        unbound_inputs=tuple(unbound_inputs),
        predicate_provenance=predicate_provenance,
        declared_builtin_loaders=declared_builtin_loaders,
        provider_origin_bindings=provider_origin_bindings,
    )


def _sha256_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _sha256_json(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return _sha256_bytes(encoded)


def _component_discovery_manifest_id(content_payload: object) -> str:
    """Derive the canonical identity of full discovery-manifest content."""

    return "component_discovery_manifest_" + _sha256_json(content_payload).removeprefix("sha256:")


def _coerce_builtin_loader_spec(
    spec: BuiltinLoaderSpec,
) -> tuple[str, BuiltinComponentLoader | DeclaredBuiltinLoader]:
    if isinstance(spec, DeclaredBuiltinLoader):
        return spec.target, spec
    if isinstance(spec, tuple):
        return spec
    return f"{spec.__module__}:{getattr(spec, '__qualname__', spec.__name__)}", spec


def _load_declared_builtin_loader(
    loader: DeclaredBuiltinLoader,
) -> tuple[object, ComponentKind]:
    """Resolve a typed target and the component kind declared by its group."""
    expected_kind = ENTRY_POINT_KIND_BY_GROUP.get(loader.group)
    if expected_kind is None:
        raise ValueError(f"unsupported declared builtin loader group: {loader.group}")
    module_name, separator, attribute = loader.target.partition(":")
    if not separator or not module_name or not attribute:
        raise ValueError("declared builtin loader must use module:attribute syntax")
    loaded = importlib.metadata.EntryPoint(
        name=module_name,
        value=loader.target,
        group=loader.group,
    ).load()
    return loaded, expected_kind


def _discover_builtin_loader(
    *,
    name: str,
    loader: BuiltinComponentLoader | DeclaredBuiltinLoader,
    errors: list[DiscoveryError],
) -> list[DiscoveredComponent]:
    discovered: list[DiscoveredComponent] = []
    source = DiscoverySourceInfo(
        source_type="builtin_loader",
        location=name,
        group=loader.group if isinstance(loader, DeclaredBuiltinLoader) else None,
    )
    expected_kind: ComponentKind | None = None

    try:
        if isinstance(loader, DeclaredBuiltinLoader):
            if loader.target != name:
                raise ValueError("declared builtin loader target must match its discovery name")
            declared_loader, expected_kind = _load_declared_builtin_loader(loader)
            declared = declared_loader() if callable(declared_loader) else declared_loader
        else:
            declared = loader()
    except _DISCOVERY_BOUNDARY_ERRORS as exc:
        details = {"traceback": format_traceback()}
        if isinstance(loader, DeclaredBuiltinLoader):
            details.update({"target": loader.target, "group": loader.group})
        errors.append(
            DiscoveryError(
                source="builtin_loader",
                item=name,
                error_type=type(exc).__name__,
                message=str(exc),
                details=details,
            )
        )
        return discovered

    for idx, item in enumerate(_iter_loader_items(declared)):
        component = _materialize_component(item)
        if component is None:
            errors.append(
                DiscoveryError(
                    source="builtin_loader",
                    item=f"{name}:{idx}",
                    error_type="InvalidDeclaration",
                    message="builtin loader item must be Component or factory",
                )
            )
            continue
        if (
            isinstance(loader, DeclaredBuiltinLoader)
            and expected_kind is not None
            and component.metadata.kind is not expected_kind
        ):
            errors.append(
                DiscoveryError(
                    source="builtin_loader",
                    item=f"{name}:{idx}",
                    error_type="ComponentKindMismatch",
                    message=(
                        f"declared loader group {loader.group} expects "
                        f"{expected_kind.value}, got {component.metadata.kind.value}"
                    ),
                    details={
                        "target": loader.target,
                        "group": loader.group,
                        "expected_kind": expected_kind.value,
                        "actual_kind": component.metadata.kind.value,
                    },
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


def _iter_loader_items(declared: object) -> list[object]:
    if isinstance(declared, Component) or callable(declared):
        return [declared]
    if isinstance(declared, Iterable):
        return list(declared)
    return [declared]


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


def _materialize_components(value: object) -> tuple[list[Component], int, bool]:
    if isinstance(value, Component):
        return [value], 0, True
    if callable(value):
        try:
            value = value()
        except (AttributeError, ImportError, RuntimeError, TypeError, ValueError) as exc:
            logger.warning("Component factory materialization failed: %s", exc)
            return [], 0, False

    components: list[Component] = []
    rejected_result_count = 0
    for item in _iter_loader_items(value):
        component = _materialize_component(item)
        if component is not None:
            components.append(component)
        else:
            rejected_result_count += 1
    return components, rejected_result_count, True


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
