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

from polisyos.foundry.methods.compiler import (
    MethodCompiler,
    CompiledMethod,
    CompilationCache,
    CompiledChainExecutor,
    get_global_cache,
    reset_global_cache,
)

from polisyos.foundry.methods.specialization import (
    Specialization,
    ShapeSpec,
    BackendSpec,
    build_specialization,
    compute_static_params_hash,
    specialization_from_signature_and_state,
)

from polisyos.foundry.methods.artifacts import (
    MethodArtifact,
    ChainArtifact,
    ExecutionEvidence,
    SlotBindingRecord,
    MethodTiming,
    DeviceInfo,
    ChainNodeRecord,
    SourceFingerprint,
    compute_source_hash,
    compute_source_fingerprint,
    store_method_artifact,
    store_chain_artifact,
    store_execution_evidence,
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
    "MethodCompiler",
    "CompiledMethod",
    "CompilationCache",
    "CompiledChainExecutor",
    "get_global_cache",
    "reset_global_cache",
    "Specialization",
    "ShapeSpec",
    "BackendSpec",
    "build_specialization",
    "compute_static_params_hash",
    "specialization_from_signature_and_state",
    "MethodArtifact",
    "ChainArtifact",
    "ExecutionEvidence",
    "SlotBindingRecord",
    "MethodTiming",
    "DeviceInfo",
    "ChainNodeRecord",
    "SourceFingerprint",
    "compute_source_hash",
    "compute_source_fingerprint",
    "store_method_artifact",
    "store_chain_artifact",
    "store_execution_evidence",
]

__version__ = "3.5.0"
