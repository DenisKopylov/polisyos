"""
Foundry Methods Core Types & Protocol.

Phase 3.2 Public API.
"""
from __future__ import annotations

from polisyos.foundry.methods.base import (
    FoundryMethod,
    MethodSignature,
    MethodMetadata,
    SlotSpec,
    SlotType,
    ParameterSpec,
    Unit,
    FidelityLevel,
    ComplexityClass,
    foundry_method,
    check_protocol_compliance,
    parse_fqn,
    is_valid_semver,
)

from polisyos.foundry.methods.exceptions import (
    FoundryMethodError,
    MethodDefinitionError,
    MethodNotFoundError,
    MethodAlreadyRegisteredError,
    ResolutionError,
    SlotConnectionError,
    UnitMismatchError,
    ShapeMismatchError,
    CyclicDependencyError,
    CompilationError,
    ParameterValidationError,
    ArtifactError,
    LawViolationError,
)

from polisyos.foundry.methods.resolution import (
    ResolutionPolicy,
    VersionConstraint,
    resolve_version,
    find_compatible_versions,
    compare_versions,
    is_compatible_upgrade,
)

from polisyos.foundry.methods.registry import (
    MethodEntry,
    MethodRegistry,
    RegistrySnapshot,
    get_registry,
)

from polisyos.foundry.methods.types.checker import (
    AdapterPlan,
    IncompatibilityReason,
    ShapeAdapter,
    ShapeAdapterKind,
    SlotCompatibility,
    TypeAdapter,
    TypeAdapterKind,
    UnitAdapter,
    UnitAdapterKind,
    check_multiple_compatibility,
    check_slot_compatibility,
    find_compatible_slots,
)

from polisyos.foundry.methods.linker import (
    SlotLinker,
    SlotBinding,
    LinkResult,
    LinkerConfig,
    link_methods,
    check_linkable,
)

from polisyos.foundry.methods.composer import (
    MethodNode,
    CompositionDAG,
    MethodComposer,
    CompiledMethodChain,
)

__all__ = [
    "FoundryMethod",
    "MethodSignature",
    "MethodMetadata",
    "SlotSpec",
    "SlotType",
    "ParameterSpec",
    "Unit",
    "FidelityLevel",
    "ComplexityClass",
    "foundry_method",
    "check_protocol_compliance",
    "parse_fqn",
    "is_valid_semver",
    "FoundryMethodError",
    "MethodDefinitionError",
    "MethodNotFoundError",
    "MethodAlreadyRegisteredError",
    "ResolutionError",
    "SlotConnectionError",
    "UnitMismatchError",
    "ShapeMismatchError",
    "CyclicDependencyError",
    "CompilationError",
    "ParameterValidationError",
    "ArtifactError",
    "LawViolationError",
    "ResolutionPolicy",
    "VersionConstraint",
    "resolve_version",
    "find_compatible_versions",
    "compare_versions",
    "is_compatible_upgrade",
    "MethodEntry",
    "MethodRegistry",
    "RegistrySnapshot",
    "get_registry",
    "AdapterPlan",
    "IncompatibilityReason",
    "ShapeAdapter",
    "ShapeAdapterKind",
    "SlotCompatibility",
    "TypeAdapter",
    "TypeAdapterKind",
    "UnitAdapter",
    "UnitAdapterKind",
    "check_multiple_compatibility",
    "check_slot_compatibility",
    "find_compatible_slots",
    "SlotLinker",
    "SlotBinding",
    "LinkResult",
    "LinkerConfig",
    "link_methods",
    "check_linkable",
    "MethodNode",
    "CompositionDAG",
    "MethodComposer",
    "CompiledMethodChain",
]

__version__ = "3.4.0"
