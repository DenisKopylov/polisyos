"""
Lazy facade for the stable Foundry Methods ABI.

The mypy plugin lives under this package, so package import must stay lightweight:
loading ``polisyos.foundry.methods.mypy_plugin`` must not import the full method
catalog, Fabric connectors, optional solver stacks, or benchmark helpers.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

_EXPORTS: dict[str, tuple[str, str]] = {
    "ADVISOR_EXECUTION_CONTEXT_PARAM": (
        "polisyos.foundry.methods.selection_history",
        "ADVISOR_EXECUTION_CONTEXT_PARAM",
    ),
    "ActiveSetSummary": ("polisyos.foundry.methods.selection", "ActiveSetSummary"),
    "AdapterPlan": ("polisyos.foundry.methods.types.checker", "AdapterPlan"),
    "AdvisorExecutionContext": (
        "polisyos.foundry.methods.selection_history",
        "AdvisorExecutionContext",
    ),
    "ArtifactError": ("polisyos.foundry.methods.exceptions", "ArtifactError"),
    "BackendNotAvailableError": (
        "polisyos.foundry.methods.backends",
        "BackendNotAvailableError",
    ),
    "BackendSpec": ("polisyos.foundry.methods.specialization", "BackendSpec"),
    "BreakingChange": ("polisyos.foundry.methods.compat", "BreakingChange"),
    "BreakingChangeError": ("polisyos.foundry.methods.compat", "BreakingChangeError"),
    "CalibrationBattery": ("polisyos.foundry.methods.equivalence", "CalibrationBattery"),
    "CalibrationCase": ("polisyos.foundry.methods.equivalence", "CalibrationCase"),
    "CalibrationResult": ("polisyos.foundry.methods.equivalence", "CalibrationResult"),
    "ChainArtifact": ("polisyos.foundry.methods.artifacts", "ChainArtifact"),
    "ChainExecutionResult": (
        "polisyos.foundry.methods.backends",
        "ChainExecutionResult",
    ),
    "ChainNodeRecord": ("polisyos.foundry.methods.artifacts", "ChainNodeRecord"),
    "CompilationCache": ("polisyos.foundry.methods.compiler", "CompilationCache"),
    "CompilationError": ("polisyos.foundry.methods.exceptions", "CompilationError"),
    "CompiledChainExecutor": (
        "polisyos.foundry.methods.compiler",
        "CompiledChainExecutor",
    ),
    "CompiledMethod": ("polisyos.foundry.methods.compiler", "CompiledMethod"),
    "CompiledMethodChain": ("polisyos.foundry.methods.composer", "CompiledMethodChain"),
    "ComparatorKind": ("polisyos.foundry.methods.equivalence", "ComparatorKind"),
    "ComplexityClass": ("polisyos.foundry.methods.base", "ComplexityClass"),
    "ComponentsBridgeError": (
        "polisyos.foundry.methods.components_bridge",
        "ComponentsBridgeError",
    ),
    "ComponentsBridgeReport": (
        "polisyos.foundry.methods.components_bridge",
        "ComponentsBridgeReport",
    ),
    "CompositionDAG": ("polisyos.foundry.methods.composer", "CompositionDAG"),
    "ComputeBackend": ("polisyos.foundry.methods.base", "ComputeBackend"),
    "ContractViolationError": (
        "polisyos.foundry.methods.exceptions",
        "ContractViolationError",
    ),
    "CrossBackendEquivalenceCertificate": (
        "polisyos.foundry.methods.equivalence",
        "CrossBackendEquivalenceCertificate",
    ),
    "CyclicDependencyError": (
        "polisyos.foundry.methods.exceptions",
        "CyclicDependencyError",
    ),
    "DISCOVERY_MODULE_PREFIX": (
        "polisyos.foundry.methods.discovery",
        "DISCOVERY_MODULE_PREFIX",
    ),
    "DataCharacteristics": ("polisyos.foundry.methods.selection", "DataCharacteristics"),
    "DeprecationAudit": ("polisyos.foundry.methods.deprecation", "DeprecationAudit"),
    "DeprecationInfo": ("polisyos.foundry.methods.deprecation", "DeprecationInfo"),
    "DeviceInfo": ("polisyos.foundry.methods.artifacts", "DeviceInfo"),
    "DimExpr": ("polisyos.foundry.methods.base", "DimExpr"),
    "DimVar": ("polisyos.foundry.methods.base", "DimVar"),
    "DiscoveryError": ("polisyos.foundry.methods.discovery", "DiscoveryError"),
    "DiscoveryReport": ("polisyos.foundry.methods.discovery", "DiscoveryReport"),
    "DiscoverySource": ("polisyos.foundry.methods.discovery", "DiscoverySource"),
    "DuplicatePolicy": ("polisyos.foundry.methods.discovery", "DuplicatePolicy"),
    "ENTRY_POINT_GROUP": ("polisyos.foundry.methods.discovery", "ENTRY_POINT_GROUP"),
    "EQUIVALENCE_ATTESTATION_KIND": (
        "polisyos.foundry.methods.equivalence",
        "EQUIVALENCE_ATTESTATION_KIND",
    ),
    "EQUIVALENCE_ATTESTATION_PREDICATE_TYPE": (
        "polisyos.foundry.methods.equivalence",
        "EQUIVALENCE_ATTESTATION_PREDICATE_TYPE",
    ),
    "EQUIVALENCE_ATTESTATION_SCHEMA": (
        "polisyos.foundry.methods.equivalence",
        "EQUIVALENCE_ATTESTATION_SCHEMA",
    ),
    "EQUIVALENCE_ATTESTATION_SCHEMA_VERSION": (
        "polisyos.foundry.methods.equivalence",
        "EQUIVALENCE_ATTESTATION_SCHEMA_VERSION",
    ),
    "EntryPointSource": ("polisyos.foundry.methods.discovery", "EntryPointSource"),
    "EquivalenceCertificateResolver": (
        "polisyos.foundry.methods.equivalence",
        "EquivalenceCertificateResolver",
    ),
    "EquivalencePolicy": ("polisyos.foundry.methods.equivalence", "EquivalencePolicy"),
    "EquivalenceRuntimeEnvelope": (
        "polisyos.foundry.methods.equivalence",
        "EquivalenceRuntimeEnvelope",
    ),
    "EquivalenceVerificationReport": (
        "polisyos.foundry.methods.equivalence",
        "EquivalenceVerificationReport",
    ),
    "EquivalenceVerdict": ("polisyos.foundry.methods.equivalence", "EquivalenceVerdict"),
    "ExecutionEvidence": ("polisyos.foundry.methods.artifacts", "ExecutionEvidence"),
    "ExecutionKernel": ("polisyos.foundry.methods.plan_optimizer", "ExecutionKernel"),
    "ExecutionPlanOptimizer": (
        "polisyos.foundry.methods.plan_optimizer",
        "ExecutionPlanOptimizer",
    ),
    "FidelityLevel": ("polisyos.foundry.methods.base", "FidelityLevel"),
    "FieldCalibrationStats": (
        "polisyos.foundry.methods.equivalence",
        "FieldCalibrationStats",
    ),
    "FieldComparison": ("polisyos.foundry.methods.equivalence", "FieldComparison"),
    "FieldRequirement": ("polisyos.foundry.methods.equivalence", "FieldRequirement"),
    "FieldToleranceSpec": ("polisyos.foundry.methods.equivalence", "FieldToleranceSpec"),
    "FileSystemSource": ("polisyos.foundry.methods.discovery", "FileSystemSource"),
    "FoundryMethod": ("polisyos.foundry.methods.base", "FoundryMethod"),
    "FoundryMethodBase": ("polisyos.foundry.methods.base", "FoundryMethodBase"),
    "FoundryMethodError": ("polisyos.foundry.methods.exceptions", "FoundryMethodError"),
    "InMemoryEquivalenceCertificateRegistry": (
        "polisyos.foundry.methods.equivalence",
        "InMemoryEquivalenceCertificateRegistry",
    ),
    "IncompatibilityReason": (
        "polisyos.foundry.methods.types.checker",
        "IncompatibilityReason",
    ),
    "LawViolationError": ("polisyos.foundry.methods.exceptions", "LawViolationError"),
    "LifecycleLog": ("polisyos.foundry.methods.lifecycle", "LifecycleLog"),
    "LifecycleManager": ("polisyos.foundry.methods.lifecycle", "LifecycleManager"),
    "LinkResult": ("polisyos.foundry.methods.linker", "LinkResult"),
    "LinkerConfig": ("polisyos.foundry.methods.linker", "LinkerConfig"),
    "MethodAdvisorQuery": ("polisyos.foundry.methods.selection", "MethodAdvisorQuery"),
    "MethodAdvisorResult": ("polisyos.foundry.methods.selection", "MethodAdvisorResult"),
    "MethodAlreadyRegisteredError": (
        "polisyos.foundry.methods.exceptions",
        "MethodAlreadyRegisteredError",
    ),
    "MethodArtifact": ("polisyos.foundry.methods.artifacts", "MethodArtifact"),
    "MethodCompiler": ("polisyos.foundry.methods.compiler", "MethodCompiler"),
    "MethodComposer": ("polisyos.foundry.methods.composer", "MethodComposer"),
    "MethodContractError": (
        "polisyos.foundry.methods.exceptions",
        "MethodContractError",
    ),
    "MethodContracts": ("polisyos.foundry.methods.base", "MethodContracts"),
    "MethodCostModel": ("polisyos.foundry.methods.plan_optimizer", "MethodCostModel"),
    "MethodDefinitionError": (
        "polisyos.foundry.methods.exceptions",
        "MethodDefinitionError",
    ),
    "MethodDiscovery": ("polisyos.foundry.methods.discovery", "MethodDiscovery"),
    "MethodDispatcher": ("polisyos.foundry.methods.backends", "MethodDispatcher"),
    "MethodEntry": ("polisyos.foundry.methods.registry", "MethodEntry"),
    "MethodKind": ("polisyos.foundry.methods.base", "MethodKind"),
    "MethodLifecycle": ("polisyos.foundry.methods.lifecycle", "MethodLifecycle"),
    "MethodLossProfile": ("polisyos.foundry.methods.selection", "MethodLossProfile"),
    "MethodMetadata": ("polisyos.foundry.methods.base", "MethodMetadata"),
    "MethodNode": ("polisyos.foundry.methods.composer", "MethodNode"),
    "MethodNotFoundError": (
        "polisyos.foundry.methods.exceptions",
        "MethodNotFoundError",
    ),
    "MethodRegistry": ("polisyos.foundry.methods.registry", "MethodRegistry"),
    "MethodResult": ("polisyos.foundry.methods.backends", "MethodResult"),
    "MethodRetiredException": (
        "polisyos.foundry.methods.deprecation",
        "MethodRetiredException",
    ),
    "MethodRunner": ("polisyos.foundry.methods.backends", "MethodRunner"),
    "MethodScoreTraceEntry": (
        "polisyos.foundry.methods.selection",
        "MethodScoreTraceEntry",
    ),
    "MethodSelectionCriteria": (
        "polisyos.foundry.methods.selection",
        "MethodSelectionCriteria",
    ),
    "MethodSignature": ("polisyos.foundry.methods.base", "MethodSignature"),
    "MethodTiming": ("polisyos.foundry.methods.backends", "MethodTiming"),
    "NodeSchedule": ("polisyos.foundry.methods.plan_optimizer", "NodeSchedule"),
    "OptimizedPlan": ("polisyos.foundry.methods.plan_optimizer", "OptimizedPlan"),
    "ParameterSpec": ("polisyos.foundry.methods.base", "ParameterSpec"),
    "ParameterValidationError": (
        "polisyos.foundry.methods.exceptions",
        "ParameterValidationError",
    ),
    "PersistedEquivalenceArtifacts": (
        "polisyos.foundry.methods.equivalence",
        "PersistedEquivalenceArtifacts",
    ),
    "PlanComplexityClass": ("polisyos.foundry.methods.plan_optimizer", "ComplexityClass"),
    "RegistrySnapshot": ("polisyos.foundry.methods.registry", "RegistrySnapshot"),
    "RegistrySnapshotEntry": (
        "polisyos.foundry.methods.registry",
        "RegistrySnapshotEntry",
    ),
    "ReproducibilityInfo": ("polisyos.foundry.methods.backends", "ReproducibilityInfo"),
    "ResolvedEquivalenceCertificate": (
        "polisyos.foundry.methods.equivalence",
        "ResolvedEquivalenceCertificate",
    ),
    "ResolutionError": ("polisyos.foundry.methods.exceptions", "ResolutionError"),
    "ResolutionPolicy": ("polisyos.foundry.methods.resolution", "ResolutionPolicy"),
    "Shape": ("polisyos.foundry.methods.base", "Shape"),
    "ShapeAdapter": ("polisyos.foundry.methods.types.checker", "ShapeAdapter"),
    "ShapeAdapterKind": ("polisyos.foundry.methods.types.checker", "ShapeAdapterKind"),
    "ShapeMismatchError": (
        "polisyos.foundry.methods.exceptions",
        "ShapeMismatchError",
    ),
    "ShapeSpec": ("polisyos.foundry.methods.specialization", "ShapeSpec"),
    "SideEffectProfile": ("polisyos.foundry.methods.base", "SideEffectProfile"),
    "SignatureDiff": ("polisyos.foundry.methods.compat", "SignatureDiff"),
    "SlotBinding": ("polisyos.foundry.methods.linker", "SlotBinding"),
    "SlotBindingRecord": ("polisyos.foundry.methods.artifacts", "SlotBindingRecord"),
    "SlotCompatibility": (
        "polisyos.foundry.methods.types.checker",
        "SlotCompatibility",
    ),
    "SlotConnectionError": (
        "polisyos.foundry.methods.exceptions",
        "SlotConnectionError",
    ),
    "SlotLinker": ("polisyos.foundry.methods.linker", "SlotLinker"),
    "SlotSchema": ("polisyos.foundry.methods.slot_schema", "SlotSchema"),
    "SlotSpec": ("polisyos.foundry.methods.base", "SlotSpec"),
    "SlotType": ("polisyos.foundry.methods.base", "SlotType"),
    "SolverStatus": ("polisyos.foundry.methods.backends", "SolverStatus"),
    "SourceFingerprint": ("polisyos.foundry.methods.artifacts", "SourceFingerprint"),
    "Specialization": ("polisyos.foundry.methods.specialization", "Specialization"),
    "TypeAdapter": ("polisyos.foundry.methods.types.checker", "TypeAdapter"),
    "TypeAdapterKind": ("polisyos.foundry.methods.types.checker", "TypeAdapterKind"),
    "Unit": ("polisyos.foundry.methods.base", "Unit"),
    "UnitAdapter": ("polisyos.foundry.methods.types.checker", "UnitAdapter"),
    "UnitAdapterKind": ("polisyos.foundry.methods.types.checker", "UnitAdapterKind"),
    "UnitMismatchError": ("polisyos.foundry.methods.exceptions", "UnitMismatchError"),
    "VersionConstraint": ("polisyos.foundry.methods.resolution", "VersionConstraint"),
    "advise_methods": ("polisyos.foundry.methods.selection", "advise_methods"),
    "assert_no_breaking_changes": (
        "polisyos.foundry.methods.compat",
        "assert_no_breaking_changes",
    ),
    "assess_certificate_applicability": (
        "polisyos.foundry.methods.equivalence",
        "assess_certificate_applicability",
    ),
    "attach_advisor_execution_context": (
        "polisyos.foundry.methods.selection",
        "attach_advisor_execution_context",
    ),
    "attach_equivalence_ref": (
        "polisyos.foundry.methods.equivalence",
        "attach_equivalence_ref",
    ),
    "authoring_catalog_payload": (
        "polisyos.foundry.methods.selection",
        "authoring_catalog_payload",
    ),
    "bootstrap_method_registry_from_components": (
        "polisyos.foundry.methods.components_bridge",
        "bootstrap_method_registry_from_components",
    ),
    "build_advisor_execution_context": (
        "polisyos.foundry.methods.selection",
        "build_advisor_execution_context",
    ),
    "build_method_capability_matrix": (
        "polisyos.foundry.methods.catalog_snapshot",
        "build_method_capability_matrix",
    ),
    "build_method_catalog_snapshot": (
        "polisyos.foundry.methods.catalog_snapshot",
        "build_method_catalog_snapshot",
    ),
    "build_specialization": ("polisyos.foundry.methods.specialization", "build_specialization"),
    "calibrate_backend_pair": (
        "polisyos.foundry.methods.equivalence",
        "calibrate_backend_pair",
    ),
    "calibrate_backend_pair_detailed": (
        "polisyos.foundry.methods.equivalence",
        "calibrate_backend_pair_detailed",
    ),
    "canonicalize_method_result": (
        "polisyos.foundry.methods.equivalence",
        "canonicalize_method_result",
    ),
    "check_linkable": ("polisyos.foundry.methods.linker", "check_linkable"),
    "check_multiple_compatibility": (
        "polisyos.foundry.methods.types.checker",
        "check_multiple_compatibility",
    ),
    "check_protocol_compliance": (
        "polisyos.foundry.methods.base",
        "check_protocol_compliance",
    ),
    "check_slot_compatibility": (
        "polisyos.foundry.methods.types.checker",
        "check_slot_compatibility",
    ),
    "compare_field_values": (
        "polisyos.foundry.methods.equivalence",
        "compare_field_values",
    ),
    "compare_versions": ("polisyos.foundry.methods.resolution", "compare_versions"),
    "compute_source_fingerprint": (
        "polisyos.foundry.methods.artifacts",
        "compute_source_fingerprint",
    ),
    "compute_source_hash": ("polisyos.foundry.methods.artifacts", "compute_source_hash"),
    "compute_static_params_hash": (
        "polisyos.foundry.methods.specialization",
        "compute_static_params_hash",
    ),
    "deprecate_method": ("polisyos.foundry.methods.deprecation", "deprecate_method"),
    "derive_field_tolerance_spec": (
        "polisyos.foundry.methods.equivalence",
        "derive_field_tolerance_spec",
    ),
    "derive_pairwise_budget": (
        "polisyos.foundry.methods.equivalence",
        "derive_pairwise_budget",
    ),
    "ensure_all_methods_registered": (
        "polisyos.foundry.methods.catalog",
        "ensure_all_methods_registered",
    ),
    "execute_heterogeneous_chain": (
        "polisyos.foundry.methods.backends",
        "execute_heterogeneous_chain",
    ),
    "find_compatible_slots": (
        "polisyos.foundry.methods.types.checker",
        "find_compatible_slots",
    ),
    "find_compatible_versions": (
        "polisyos.foundry.methods.resolution",
        "find_compatible_versions",
    ),
    "foundry_method": ("polisyos.foundry.methods.base", "foundry_method"),
    "get_global_cache": ("polisyos.foundry.methods.compiler", "get_global_cache"),
    "get_registry": ("polisyos.foundry.methods.registry", "get_registry"),
    "get_slot_schema": ("polisyos.foundry.methods.slot_schema", "get_slot_schema"),
    "is_foundry_method": ("polisyos.foundry.methods.discovery", "is_foundry_method"),
    "is_semantically_compatible": (
        "polisyos.foundry.methods.slot_schema",
        "is_semantically_compatible",
    ),
    "is_valid_semver": ("polisyos.foundry.methods.base", "is_valid_semver"),
    "is_compatible_upgrade": ("polisyos.foundry.methods.resolution", "is_compatible_upgrade"),
    "link_methods": ("polisyos.foundry.methods.linker", "link_methods"),
    "load_equivalence_certificate": (
        "polisyos.foundry.methods.equivalence",
        "load_equivalence_certificate",
    ),
    "method_selection_payload": (
        "polisyos.foundry.methods.selection",
        "method_selection_payload",
    ),
    "parse_fqn": ("polisyos.foundry.methods.base", "parse_fqn"),
    "parse_pip_specifier": ("polisyos.foundry.methods.resolution", "parse_pip_specifier"),
    "persist_attested_equivalence_certificate": (
        "polisyos.foundry.methods.equivalence",
        "persist_attested_equivalence_certificate",
    ),
    "persist_equivalence_certificate": (
        "polisyos.foundry.methods.equivalence",
        "persist_equivalence_certificate",
    ),
    "persist_method_catalog_snapshot": (
        "polisyos.foundry.methods.catalog_snapshot",
        "persist_method_catalog_snapshot",
    ),
    "rank_method_catalog_entries": (
        "polisyos.foundry.methods.selection",
        "rank_method_catalog_entries",
    ),
    "register_slot_schema": (
        "polisyos.foundry.methods.slot_schema",
        "register_slot_schema",
    ),
    "registry_scope": ("polisyos.foundry.methods.registry", "registry_scope"),
    "reset_global_cache": ("polisyos.foundry.methods.compiler", "reset_global_cache"),
    "resolve_by_specifier": ("polisyos.foundry.methods.resolution", "resolve_by_specifier"),
    "resolve_method_version": (
        "polisyos.foundry.methods.resolution",
        "resolve_method_version",
    ),
    "resolve_version": ("polisyos.foundry.methods.resolution", "resolve_version"),
    "runtime_envelope_from_results": (
        "polisyos.foundry.methods.equivalence",
        "runtime_envelope_from_results",
    ),
    "specialization_from_signature_and_state": (
        "polisyos.foundry.methods.specialization",
        "specialization_from_signature_and_state",
    ),
    "store_chain_artifact": ("polisyos.foundry.methods.artifacts", "store_chain_artifact"),
    "store_execution_evidence": (
        "polisyos.foundry.methods.artifacts",
        "store_execution_evidence",
    ),
    "store_method_artifact": ("polisyos.foundry.methods.artifacts", "store_method_artifact"),
    "suggest_adapter_methods": (
        "polisyos.foundry.methods.selection",
        "suggest_adapter_methods",
    ),
    "suggest_alternative_methods": (
        "polisyos.foundry.methods.selection",
        "suggest_alternative_methods",
    ),
    "suggest_plan_node_alternatives": (
        "polisyos.foundry.methods.selection",
        "suggest_plan_node_alternatives",
    ),
    "tag_deprecated_in_registry": (
        "polisyos.foundry.methods.deprecation",
        "tag_deprecated_in_registry",
    ),
    "verify_backend_equivalence": (
        "polisyos.foundry.methods.equivalence",
        "verify_backend_equivalence",
    ),
    "verify_persisted_equivalence_certificate": (
        "polisyos.foundry.methods.equivalence",
        "verify_persisted_equivalence_certificate",
    ),
}

__all__ = sorted(_EXPORTS)
__version__ = "3.5.0"


def __getattr__(name: str) -> Any:
    """Resolve a public facade export on demand."""
    try:
        module_name, attr_name = _EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc
    value = getattr(import_module(module_name), attr_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    """Return facade exports for interactive discovery."""
    return sorted({*globals(), *__all__})
