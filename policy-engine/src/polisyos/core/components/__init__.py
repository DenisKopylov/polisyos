"""Expose the stable component discovery, metadata, compliance, and registry API.

This facade is the contract boundary between plugin packages and the host
platform. Component packages should publish `ComponentMetadata` plus a
`Component` factory, while runtime/bootstrap code consumes this package for
entry-point discovery, dev scanning, ABI validation, and version resolution.
"""

from .bootstrap import (
    BootstrapDomainReport,
    BootstrapReport,
    bootstrap_plugin_registries,
    build_components_index,
)
from .capabilities import (
    Capabilities,
    Capability,
    capabilities_from_flags,
    flags_from_capabilities,
)
from .compliance import (
    ComplianceIssue,
    HostAbi,
    has_errors,
    validate_component_id,
    validate_metadata,
)
from .discovery import (
    DEFAULT_ENTRY_POINT_GROUPS,
    ENTRY_POINT_GROUP,
    ENTRY_POINT_GROUP_FABRIC_CONNECTORS,
    ENTRY_POINT_GROUP_FOUNDRY_METHODS,
    ENTRY_POINT_GROUP_IR_FRAGMENTS,
    ENTRY_POINT_GROUP_LEX_EVALUATORS,
    ENTRY_POINT_GROUP_LEX_EXTRACTORS,
    ENTRY_POINT_GROUP_NORM_PACK_PROVIDERS,
    ENTRY_POINT_GROUP_SCHOLAR_EXTRACTORS,
    ENTRY_POINT_GROUP_SCIENTIST_NODES,
    LEGACY_ENTRY_POINT_GROUP,
    DiscoveryError,
    DiscoveryPrecedencePolicy,
    DiscoveryReport,
    discover_components,
    discover_dev_components,
    discover_entry_points,
)
from .ids import ComponentId, SemVer, SemverRange, compare_semver
from .metadata import ComponentDep, ComponentKind, ComponentMetadata
from .protocols import Component, ComponentFactory, ComponentProvider, SupportsValidation
from .registry import (
    ComponentEntry,
    ComponentRegistry,
    ConflictPolicy,
    DuplicateComponentIdPolicy,
    ResolvePolicy,
    SourcePrecedencePolicy,
)

__all__ = [
    "DEFAULT_ENTRY_POINT_GROUPS",
    "ENTRY_POINT_GROUP",
    "ENTRY_POINT_GROUP_FABRIC_CONNECTORS",
    "ENTRY_POINT_GROUP_FOUNDRY_METHODS",
    "ENTRY_POINT_GROUP_IR_FRAGMENTS",
    "ENTRY_POINT_GROUP_LEX_EVALUATORS",
    "ENTRY_POINT_GROUP_LEX_EXTRACTORS",
    "ENTRY_POINT_GROUP_NORM_PACK_PROVIDERS",
    "ENTRY_POINT_GROUP_SCHOLAR_EXTRACTORS",
    "ENTRY_POINT_GROUP_SCIENTIST_NODES",
    "LEGACY_ENTRY_POINT_GROUP",
    "BootstrapDomainReport",
    "BootstrapReport",
    "Capabilities",
    "Capability",
    "ComplianceIssue",
    "Component",
    "ComponentDep",
    "ComponentEntry",
    "ComponentFactory",
    "ComponentId",
    "ComponentKind",
    "ComponentMetadata",
    "ComponentProvider",
    "ComponentRegistry",
    "ConflictPolicy",
    "DiscoveryError",
    "DiscoveryPrecedencePolicy",
    "DiscoveryReport",
    "DuplicateComponentIdPolicy",
    "HostAbi",
    "ResolvePolicy",
    "SemVer",
    "SemverRange",
    "SourcePrecedencePolicy",
    "SupportsValidation",
    "bootstrap_plugin_registries",
    "build_components_index",
    "capabilities_from_flags",
    "compare_semver",
    "discover_components",
    "discover_dev_components",
    "discover_entry_points",
    "flags_from_capabilities",
    "has_errors",
    "validate_component_id",
    "validate_metadata",
]
