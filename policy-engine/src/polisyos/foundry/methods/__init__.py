"""
Foundry Methods Core Types & Protocol.

Phase 3.2 Public API.
"""
from __future__ import annotations

from polisyos.foundry.methods.backends import (
    BackendNotAvailableError,
    ChainExecutionResult,
    MethodDispatcher,
    MethodResult,
    MethodRunner,
    MethodTiming,
    ReproducibilityInfo,
    SolverStatus,
    execute_heterogeneous_chain,
)
from polisyos.foundry.methods.base import (
    ComplexityClass,
    ComputeBackend,
    DimExpr,
    DimVar,
    FidelityLevel,
    FoundryMethod,
    FoundryMethodBase,
    MethodContracts,
    MethodKind,
    MethodMetadata,
    MethodSignature,
    ParameterSpec,
    Shape,
    SideEffectProfile,
    SlotSpec,
    SlotType,
    Unit,
    check_protocol_compliance,
    foundry_method,
    is_valid_semver,
    parse_fqn,
)
from polisyos.foundry.methods.composer import (
    CompiledMethodChain,
    CompositionDAG,
    MethodComposer,
    MethodNode,
)
from polisyos.foundry.methods.discovery import (
    DISCOVERY_MODULE_PREFIX,
    ENTRY_POINT_GROUP,
    DiscoveryError,
    DiscoveryReport,
    DiscoverySource,
    DuplicatePolicy,
    EntryPointSource,
    FileSystemSource,
    MethodDiscovery,
    is_foundry_method,
)
from polisyos.foundry.methods.exceptions import (
    ArtifactError,
    CompilationError,
    ContractViolationError,
    CyclicDependencyError,
    FoundryMethodError,
    LawViolationError,
    MethodAlreadyRegisteredError,
    MethodContractError,
    MethodDefinitionError,
    MethodNotFoundError,
    ParameterValidationError,
    ResolutionError,
    ShapeMismatchError,
    SlotConnectionError,
    UnitMismatchError,
)
from polisyos.foundry.methods.lifecycle import (
    LifecycleLog,
    LifecycleManager,
    MethodLifecycle,
)
from polisyos.foundry.methods.plan_optimizer import (
    ComplexityClass as PlanComplexityClass,
    ExecutionPlanOptimizer,
    MethodCostModel,
    NodeSchedule,
    OptimizedPlan,
)
from polisyos.foundry.methods.linker import (
    LinkerConfig,
    LinkResult,
    SlotBinding,
    SlotLinker,
    check_linkable,
    link_methods,
)
from polisyos.foundry.methods.slot_schema import (
    SLOT_SCHEMA_REGISTRY,
    SlotSchema,
    get_slot_schema,
    is_semantically_compatible,
    register_slot_schema,
)
from polisyos.foundry.methods.registry import (
    MethodEntry,
    MethodRegistry,
    RegistrySnapshot,
    get_registry,
    registry_scope,
)
from polisyos.foundry.methods.resolution import (
    ResolutionPolicy,
    VersionConstraint,
    compare_versions,
    find_compatible_versions,
    is_compatible_upgrade,
    parse_pip_specifier,
    resolve_by_specifier,
    resolve_method_version,
    resolve_version,
)
from polisyos.foundry.methods.selection import (
    MethodSelectionCriteria,
    authoring_catalog_payload,
    method_selection_payload,
    rank_method_catalog_entries,
    suggest_adapter_methods,
    suggest_plan_node_alternatives,
    suggest_alternative_methods,
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

try:
    from polisyos.foundry.methods.compiler import (
        CompilationCache,
        CompiledChainExecutor,
        CompiledMethod,
        MethodCompiler,
        get_global_cache,
        reset_global_cache,
    )
    _COMPILER_AVAILABLE = True
except ModuleNotFoundError:  # pragma: no cover - optional dependency path
    _COMPILER_AVAILABLE = False

try:
    from polisyos.foundry.methods.specialization import (
        BackendSpec,
        ShapeSpec,
        Specialization,
        build_specialization,
        compute_static_params_hash,
        specialization_from_signature_and_state,
    )
    _SPECIALIZATION_AVAILABLE = True
except ModuleNotFoundError:  # pragma: no cover - optional dependency path
    _SPECIALIZATION_AVAILABLE = False

try:
    from polisyos.foundry.methods.artifacts import (
        ChainArtifact,
        ChainNodeRecord,
        DeviceInfo,
        ExecutionEvidence,
        MethodArtifact,
        MethodTiming,
        SlotBindingRecord,
        SourceFingerprint,
        compute_source_fingerprint,
        compute_source_hash,
        store_chain_artifact,
        store_execution_evidence,
        store_method_artifact,
    )
    _ARTIFACTS_AVAILABLE = True
except ModuleNotFoundError:  # pragma: no cover - optional dependency path
    _ARTIFACTS_AVAILABLE = False
from polisyos.foundry.methods.catalog_snapshot import (
    build_method_catalog_snapshot,
    persist_method_catalog_snapshot,
)
from polisyos.foundry.methods.catalog import ensure_all_methods_registered
from polisyos.foundry.methods.compat import (
    BreakingChange,
    BreakingChangeError,
    SignatureDiff,
    assert_no_breaking_changes,
)
from polisyos.foundry.methods.deprecation import (
    DeprecationAudit,
    DeprecationInfo,
    MethodRetiredException,
    deprecate_method,
    tag_deprecated_in_registry,
)
from polisyos.foundry.methods.components_bridge import (
    ComponentsBridgeError,
    ComponentsBridgeReport,
    bootstrap_method_registry_from_components,
)

__all__ = [
    "FoundryMethod",
    "ComputeBackend",
    "MethodKind",
    "MethodSignature",
    "MethodMetadata",
    "SideEffectProfile",
    "SlotSpec",
    "SlotType",
    "ParameterSpec",
    "Unit",
    "DimVar",
    "DimExpr",
    "Shape",
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
    "MethodContractError",
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
    "resolve_by_specifier",
    "resolve_method_version",
    "parse_pip_specifier",
    "find_compatible_versions",
    "compare_versions",
    "is_compatible_upgrade",
    "MethodSelectionCriteria",
    "rank_method_catalog_entries",
    "suggest_alternative_methods",
    "suggest_adapter_methods",
    "suggest_plan_node_alternatives",
    "method_selection_payload",
    "authoring_catalog_payload",
    "MethodEntry",
    "MethodRegistry",
    "RegistrySnapshot",
    "get_registry",
    "DISCOVERY_MODULE_PREFIX",
    "ENTRY_POINT_GROUP",
    "DiscoveryError",
    "DiscoveryReport",
    "DiscoverySource",
    "DuplicatePolicy",
    "EntryPointSource",
    "FileSystemSource",
    "MethodDiscovery",
    "is_foundry_method",
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
    "BackendNotAvailableError",
    "ChainExecutionResult",
    "MethodDispatcher",
    "MethodResult",
    "MethodRunner",
    "MethodTiming",
    "ReproducibilityInfo",
    "SolverStatus",
    "execute_heterogeneous_chain",
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
    "ComponentsBridgeError",
    "ComponentsBridgeReport",
    "bootstrap_method_registry_from_components",
    "build_method_catalog_snapshot",
    "persist_method_catalog_snapshot",
    "ensure_all_methods_registered",
    "ExecutionPlanOptimizer",
    "MethodCostModel",
    "NodeSchedule",
    "OptimizedPlan",
    "PlanComplexityClass",
    # compat
    "BreakingChange",
    "BreakingChangeError",
    "SignatureDiff",
    "assert_no_breaking_changes",
    # deprecation
    "DeprecationAudit",
    "DeprecationInfo",
    "MethodRetiredException",
    "deprecate_method",
    "tag_deprecated_in_registry",
]

if not _COMPILER_AVAILABLE:
    for _name in [
        "MethodCompiler",
        "CompiledMethod",
        "CompilationCache",
        "CompiledChainExecutor",
        "get_global_cache",
        "reset_global_cache",
    ]:
        if _name in __all__:
            __all__.remove(_name)

if not _SPECIALIZATION_AVAILABLE:
    for _name in [
        "Specialization",
        "ShapeSpec",
        "BackendSpec",
        "build_specialization",
        "compute_static_params_hash",
        "specialization_from_signature_and_state",
    ]:
        if _name in __all__:
            __all__.remove(_name)

if not _ARTIFACTS_AVAILABLE:
    for _name in [
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
    ]:
        if _name in __all__:
            __all__.remove(_name)

__version__ = "3.5.0"
