"""Build and persist a CAS-backed snapshot of the currently registered method catalog."""

from __future__ import annotations

import hashlib
import json
import platform
from collections.abc import Mapping, Sequence
from contextlib import nullcontext
from copy import deepcopy
from datetime import UTC, datetime
from typing import Any

from polisyos.core.artifacts.manifest import InputRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec, truncated_hash
from polisyos.core.contracts.execution_plan import (
    MethodCatalogEntry,
    MethodCatalogSnapshot,
    MethodCatalogSnapshotRef,
)
from polisyos.core.observability import (
    DeterminismTier,
    parse_determinism_tier,
)
from polisyos.foundry.extensions.registry import (
    ComponentDiscoveryManifest,
    FoundryExtensionRegistryReport,
)
from polisyos.foundry.methods.backends.dispatch import (
    BackendNotAvailableError as MethodBackendNotAvailableError,
)
from polisyos.foundry.methods.backends.dispatch import (
    MethodDispatcher,
)
from polisyos.foundry.methods.backends.runtime_fingerprint import (
    BackendRuntimeFingerprint,
    capture_backend_runtime_fingerprint,
    runtime_stack_for,
    safe_version,
)
from polisyos.foundry.methods.base import ComputeBackend
from polisyos.foundry.methods.catalog import ensure_all_methods_registered
from polisyos.foundry.methods.catalog.causal.capabilities import build_causal_capability_contract
from polisyos.foundry.methods.catalog.dependency_authority import (
    DependencyProfileResolutionFailure,
    MethodCatalogDependencyAuthorityRequest,
    build_production_method_catalog_dependency_authority,
)
from polisyos.foundry.methods.components.value_evidence import (
    resolve_method_value_projection_capabilities,
)
from polisyos.foundry.methods.selection.registry import MethodRegistry
from polisyos.ir.analytics import (
    TruthfulnessStatus,
    parse_truthfulness_scope,
    parse_truthfulness_tier,
    reconcile_truthfulness_tiers,
)
from polisyos.ir.analytics.causal_capabilities import (
    CausalCapabilityContract,
    CausalIdentificationFamily,
)


class MethodCatalogDiscoveryProvenanceError(RuntimeError):
    """Refuse a governed snapshot whose exact registry intake is not established."""


def build_method_catalog_snapshot(
    *,
    run_id: str | None = None,
    registry: MethodRegistry | None = None,
    capability_contract: CausalCapabilityContract | None = None,
    registry_report: FoundryExtensionRegistryReport | None = None,
    require_bound_discovery: bool = False,
) -> MethodCatalogSnapshot:
    """Build a `MethodCatalogSnapshot` with backend availability and semantic metadata."""
    reg = registry if registry is not None else MethodRegistry.get_instance()
    registry_scope = reg.snapshot_scope() if require_bound_discovery else nullcontext()
    with registry_scope:
        _admit_catalog_registry(
            reg,
            registry_report=registry_report,
            require_bound_discovery=require_bound_discovery,
        )
        snapshot = _build_method_catalog_snapshot_from_admitted_registry(
            run_id=run_id,
            registry=reg,
            capability_contract=capability_contract,
        )
        if registry_report is not None:
            _admit_catalog_registry(
                reg,
                registry_report=registry_report,
                require_bound_discovery=require_bound_discovery,
            )
        return snapshot


def _build_method_catalog_snapshot_from_admitted_registry(
    *,
    run_id: str | None,
    registry: MethodRegistry,
    capability_contract: CausalCapabilityContract | None,
) -> MethodCatalogSnapshot:
    """Build from a registry held inside its mutation-excluding snapshot scope."""
    reg = registry
    contract = capability_contract or build_causal_capability_contract()
    available_backends = _available_execution_backends()
    signatures = reg.list_all()
    entries: list[MethodCatalogEntry] = []
    for sig in signatures:
        entry = reg.get_entry(sig.fqn)
        method_cls = reg.get(sig.fqn)
        value_projection_contracts = resolve_method_value_projection_capabilities(
            method_cls=method_cls,
            method_signature=sig,
        )
        runtime_stack = runtime_stack_for(method_cls)
        runtime_posture = _capture_entry_runtime_posture(sig.execution_backend, method_cls)
        tags: list[str] = []
        deprecations: list[str] = []
        incompatibilities: list[str] = []
        if entry is not None:
            tags = sorted(str(tag) for tag in entry.metadata.tags)
            deprecations = sorted(tag for tag in tags if tag.startswith("deprecated"))
            incompatibilities = sorted(str(item) for item in entry.signature.conflicts_with)
            dependency_posture = _dependency_posture(
                entry.metadata.required_deps,
                entry.metadata.optional_deps,
                runtime_stack,
            )
            backend_available = (
                sig.execution_backend.value in available_backends and runtime_posture.available
            )
            disabled_reasons = list(
                _disabled_reasons_for(sig.execution_backend.value, backend_available)
            )
            disabled_reasons.extend(dependency_posture["missing_required"])
        else:
            dependency_posture = _dependency_posture((), (), runtime_stack)
            backend_available = (
                sig.execution_backend.value in available_backends and runtime_posture.available
            )
            disabled_reasons = list(
                _disabled_reasons_for(sig.execution_backend.value, backend_available)
            )
        if not runtime_posture.available:
            disabled_reasons.append(f"runtime_posture_unavailable:{sig.execution_backend.value}")
        requirements = _causal_requirements_for_method(sig.fqn)
        if contract is None or not requirements:
            causal_available = True if requirements else None
            causal_disabled_reasons: list[str] = []
        else:
            disabled = [
                contract.disabled_families.get(requirement.value, "family_unavailable")
                for requirement in requirements
                if not contract.supports_family(requirement)
            ]
            causal_available = len(disabled) == 0
            causal_disabled_reasons = [reason for reason in disabled if reason]
        if causal_available is False:
            disabled_reasons.extend(causal_disabled_reasons)
        disabled_reasons = sorted(dict.fromkeys(reason for reason in disabled_reasons if reason))
        runnable = (
            backend_available
            and not dependency_posture["missing_required"]
            and causal_available is not False
        )
        shape_semantics = _shape_semantics(sig)
        effect_semantics = _effect_semantics(sig, entry)
        dependency_semantics = _dependency_semantics(sig, entry)
        implementation_depth_tier, implementation_depth_notes = _truthfulness_profile(sig, entry)
        declared_truthfulness_tier = _declared_truthfulness_tier(entry)
        declared_truthfulness_scope = _declared_truthfulness_scope(entry)
        runtime_truthfulness_tier = None
        effective_truthfulness_tier, truthfulness_status = reconcile_truthfulness_tiers(
            declared_truthfulness_tier,
            runtime_truthfulness_tier,
        )
        truthfulness_notes = _truthfulness_notes_for_status(truthfulness_status)
        declared_determinism_tier = None
        if entry is not None and entry.metadata.determinism_tier is not None:
            declared_determinism_tier = entry.metadata.determinism_tier.value
        determinism_tier = _effective_determinism_tier(
            declared_determinism_tier,
            runtime_posture.determinism_tier,
        )
        capability_matrix = {
            "kind": sig.kind.value,
            "execution_backend": sig.execution_backend.value,
            "runtime_stack": list(runtime_stack),
            "fidelity_tier": sig.fidelity_tier.name.lower(),
            "data_modalities": sorted(sig.data_modalities),
            "supports_jit": bool(sig.supports_jit),
            "supports_vmap": bool(sig.supports_vmap),
            "supports_grad": bool(sig.supports_grad),
            "determinism_tier": determinism_tier,
            "declared_determinism_tier": declared_determinism_tier,
            "runtime_determinism_tier": (
                None
                if runtime_posture.determinism_tier is None
                else runtime_posture.determinism_tier.value
            ),
            "replay_semantics": runtime_posture.replay_semantics,
            "tolerance_budget": runtime_posture.tolerance_budget,
            "observed_tolerance_budget": runtime_posture.observed_tolerance_budget,
            "runtime_posture": runtime_posture.as_dict(),
            "required_deps": list(entry.metadata.required_deps) if entry is not None else [],
            "optional_deps": list(entry.metadata.optional_deps) if entry is not None else [],
            "fallback_policy": entry.metadata.fallback_policy if entry is not None else "none",
            "side_effect_profile": (
                entry.metadata.side_effect_profile.value if entry is not None else "none"
            ),
            "truthfulness_tier": effective_truthfulness_tier.value,
            "implementation_depth_tier": implementation_depth_tier,
            "implementation_depth_notes": implementation_depth_notes,
            "declared_truthfulness_tier": declared_truthfulness_tier,
            "runtime_truthfulness_tier": runtime_truthfulness_tier,
            "effective_truthfulness_tier": effective_truthfulness_tier.value,
            "truthfulness_status": truthfulness_status.value,
            "truthfulness_scope": declared_truthfulness_scope,
            "truthfulness_evidence_ref": None,
            "effect_semantics": effect_semantics,
            "shape_semantics": shape_semantics,
            "dependency_semantics": dependency_semantics,
            "simulator_regime_schema": (
                dict(entry.metadata.simulator_regime_schema) if entry is not None else {}
            ),
            "summary_schema_ref": entry.metadata.summary_schema_ref if entry is not None else None,
            "identifiable_target": (
                dict(entry.metadata.identifiable_target) if entry is not None else {}
            ),
            "coverage_contract": (
                dict(entry.metadata.coverage_contract) if entry is not None else {}
            ),
            "diagnostic_contract": (
                dict(entry.metadata.diagnostic_contract) if entry is not None else {}
            ),
            "backend_available": backend_available,
            "runnable": runnable,
        }
        if value_projection_contracts:
            capability_matrix["value_projection_contracts"] = [
                item.model_dump(mode="json") for item in value_projection_contracts
            ]
        entries.append(
            MethodCatalogEntry(
                fqn=sig.fqn,
                namespace=sig.namespace,
                name=sig.name,
                version=sig.version,
                backend=sig.backend.value,
                execution_backend=sig.execution_backend.value,
                kind=sig.kind.value,
                family=sig.family,
                variant=sig.variant,
                fidelity_tier=sig.fidelity_tier.name.lower(),
                data_modalities=sorted(sig.data_modalities),
                runtime_stack=list(runtime_stack),
                determinism_tier=determinism_tier,
                required_deps=list(entry.metadata.required_deps) if entry is not None else [],
                optional_deps=list(entry.metadata.optional_deps) if entry is not None else [],
                fallback_policy=entry.metadata.fallback_policy if entry is not None else "none",
                side_effect_profile=(
                    entry.metadata.side_effect_profile.value if entry is not None else "none"
                ),
                runnable=runnable,
                disabled_reasons=disabled_reasons,
                dependency_posture=dependency_posture,
                capability_matrix=capability_matrix,
                input_slots=[
                    {
                        "name": slot.name,
                        "slot_type": slot.slot_type.name.lower(),
                        "unit": slot.unit.symbol,
                        "dimension": slot.unit.dimension,
                        "contract_id": slot.contract_id,
                        "shape": list(slot.shape),
                        **(
                            {
                                "contract_capabilities": sorted(
                                    item.value for item in slot.contract_capabilities
                                ),
                                "contract_owner": slot.contract_owner,
                            }
                            if slot.contract_capabilities
                            else {}
                        ),
                    }
                    for slot in sorted(sig.input_slots, key=lambda item: item.name)
                ],
                output_slots=[
                    {
                        "name": slot.name,
                        "slot_type": slot.slot_type.name.lower(),
                        "unit": slot.unit.symbol,
                        "dimension": slot.unit.dimension,
                        "contract_id": slot.contract_id,
                        "shape": list(slot.shape),
                        **(
                            {
                                "contract_capabilities": sorted(
                                    item.value for item in slot.contract_capabilities
                                ),
                                "contract_owner": slot.contract_owner,
                            }
                            if slot.contract_capabilities
                            else {}
                        ),
                    }
                    for slot in sorted(sig.output_slots, key=lambda item: item.name)
                ],
                parameters=[
                    {
                        "name": param.name,
                        "default": _jsonable(param.default),
                        "is_static": bool(param.is_static),
                        "bounds": list(param.bounds),
                    }
                    for param in sig.parameters
                ],
                requires=sorted(str(item) for item in sig.requires),
                conflicts_with=sorted(str(item) for item in sig.conflicts_with),
                incompatibilities=incompatibilities,
                deprecations=deprecations,
                tags=tags,
                causal_capability_requirements=[item.value for item in requirements],
                causal_available=causal_available,
                causal_disabled_reasons=sorted(set(causal_disabled_reasons)),
                truthfulness_tier=effective_truthfulness_tier.value,
                implementation_depth_tier=implementation_depth_tier,
                implementation_depth_notes=implementation_depth_notes,
                declared_truthfulness_tier=declared_truthfulness_tier,
                runtime_truthfulness_tier=runtime_truthfulness_tier,
                effective_truthfulness_tier=effective_truthfulness_tier.value,
                truthfulness_status=truthfulness_status.value,
                truthfulness_scope=declared_truthfulness_scope,
                truthfulness_evidence_ref=None,
                truthfulness_notes=truthfulness_notes,
                effect_semantics=effect_semantics,
                shape_semantics=shape_semantics,
                dependency_semantics=dependency_semantics,
                # Rich semantic metadata — sourced from MethodMetadata
                description=str(entry.metadata.description) if entry is not None else "",
                citations=list(entry.metadata.citations) if entry is not None else [],
                assumptions=sorted(str(k) for k in entry.metadata.assumptions.keys())
                if entry is not None
                else [],
                when_to_use=str(getattr(entry.metadata, "when_to_use", ""))
                if entry is not None
                else "",
                when_not_to_use=str(getattr(entry.metadata, "when_not_to_use", ""))
                if entry is not None
                else "",
                prerequisites=list(getattr(entry.metadata, "prerequisites", ()))
                if entry is not None
                else [],
                diagnostic_checks=list(getattr(entry.metadata, "diagnostic_checks", ()))
                if entry is not None
                else [],
                typical_min_obs=getattr(entry.metadata, "typical_min_obs", None)
                if entry is not None
                else None,
                output_interpretation=str(getattr(entry.metadata, "output_interpretation", ""))
                if entry is not None
                else "",
                simulator_regime_schema=dict(getattr(entry.metadata, "simulator_regime_schema", {}))
                if entry is not None
                else {},
                summary_schema_ref=getattr(entry.metadata, "summary_schema_ref", None)
                if entry is not None
                else None,
                identifiable_target=dict(getattr(entry.metadata, "identifiable_target", {}))
                if entry is not None
                else {},
                coverage_contract=dict(getattr(entry.metadata, "coverage_contract", {}))
                if entry is not None
                else {},
                diagnostic_contract=dict(getattr(entry.metadata, "diagnostic_contract", {}))
                if entry is not None
                else {},
            )
        )
    snapshot_payload = {
        "method_count": len(entries),
        "entries": [entry.model_dump(mode="json") for entry in entries],
    }
    snapshot_id = f"method_catalog_{truncated_hash(str(snapshot_payload), length=16)}"
    return MethodCatalogSnapshot(
        snapshot_id=snapshot_id,
        run_id=run_id,
        generated_at=datetime.now(UTC),
        causal_capability_hash=contract.dependency_fingerprint if contract is not None else None,
        causal_runtime_posture=(contract.model_dump(mode="json") if contract is not None else {}),
        entries=entries,
        notes=[f"method_count:{len(entries)}"],
    )


def build_method_catalog_runtime_identity(
    snapshot: MethodCatalogSnapshot,
    *,
    dependency_authority_request: MethodCatalogDependencyAuthorityRequest,
) -> DependencyProfileResolutionFailure:
    """Return the Foundry owner's current typed dependency-authority result.

    The snapshot is intentionally not inspected before the owner resolves the
    request.  V1 has no positive public arm, so ambient runtime projection is
    unreachable from this boundary.
    """

    del snapshot
    return build_production_method_catalog_dependency_authority().resolve(
        dependency_authority_request
    )


def _build_candidate_method_catalog_runtime_identity(
    snapshot: MethodCatalogSnapshot,
) -> dict[str, Any]:
    """Build non-authoritative candidate runtime posture for internal tests."""
    bindings: list[dict[str, Any]] = []
    package_versions: dict[str, set[str]] = {}
    backend_fingerprints: set[tuple[str, str]] = set()
    for entry in snapshot.entries:
        posture = entry.capability_matrix.get("runtime_posture")
        if not isinstance(posture, Mapping):
            raise MethodCatalogDiscoveryProvenanceError(
                f"catalog_runtime_posture_missing:{entry.fqn}"
            )
        fingerprint = str(posture.get("fingerprint") or "")
        if not fingerprint:
            raise MethodCatalogDiscoveryProvenanceError(
                f"catalog_backend_fingerprint_missing:{entry.fqn}"
            )
        libraries = posture.get("library_versions")
        if not isinstance(libraries, Mapping):
            raise MethodCatalogDiscoveryProvenanceError(
                f"catalog_runtime_package_identity_missing:{entry.fqn}"
            )
        normalized_libraries = {
            str(name): str(version)
            for name, version in sorted(libraries.items(), key=lambda item: str(item[0]))
        }
        for name, version in normalized_libraries.items():
            package_versions.setdefault(name, set()).add(version)
        backend = str(posture.get("backend") or entry.execution_backend)
        backend_fingerprints.add((backend, fingerprint))
        bindings.append(
            {
                "fqn": entry.fqn,
                "backend": backend,
                "fingerprint": fingerprint,
                "library_versions": normalized_libraries,
            }
        )

    policy_engine_version = safe_version("policy-engine")
    if policy_engine_version is None:
        raise MethodCatalogDiscoveryProvenanceError(
            "catalog_runtime_package_identity_missing:policy-engine"
        )
    runtime_packages = [
        {
            "name": "policy-engine",
            "version": policy_engine_version,
        },
        {
            "name": "python",
            "version": platform.python_version(),
            "implementation": platform.python_implementation(),
        },
        *(
            {
                "name": name,
                "versions": sorted(versions),
            }
            for name, versions in sorted(package_versions.items())
        ),
    ]
    canonical_bindings = sorted(bindings, key=lambda row: row["fqn"])
    payload: dict[str, Any] = {
        "schema_version": "policyos.method_catalog_runtime_identity.v1",
        "runtime_packages": runtime_packages,
        "backend_fingerprints": [
            {"backend": backend, "fingerprint": fingerprint}
            for backend, fingerprint in sorted(backend_fingerprints)
        ],
        "entry_runtime_binding_count": len(canonical_bindings),
        "entry_runtime_bindings_sha256": _sha256_payload(canonical_bindings),
    }
    payload["identity_id"] = "method_catalog_runtime_identity_" + _sha256_payload(
        payload
    ).removeprefix("sha256:")
    return payload


def build_method_catalog_provenance_manifest(
    snapshot: MethodCatalogSnapshot,
    *,
    registry_report: FoundryExtensionRegistryReport,
    ambient_manifest: ComponentDiscoveryManifest,
    dependency_authority_request: MethodCatalogDependencyAuthorityRequest,
    additional_predicate_provenance: Sequence[Mapping[str, object]] = (),
    predicate_bindings: Mapping[str, Sequence[str]] | None = None,
) -> DependencyProfileResolutionFailure:
    """Return the same owner result before reading candidate provenance inputs."""

    del snapshot, registry_report, ambient_manifest
    del additional_predicate_provenance, predicate_bindings
    return build_production_method_catalog_dependency_authority().resolve(
        dependency_authority_request
    )


def _build_candidate_method_catalog_provenance_manifest(
    snapshot: MethodCatalogSnapshot,
    *,
    registry_report: FoundryExtensionRegistryReport,
    ambient_manifest: ComponentDiscoveryManifest,
    additional_predicate_provenance: Sequence[Mapping[str, object]] = (),
    predicate_bindings: Mapping[str, Sequence[str]] | None = None,
) -> dict[str, Any]:
    """Bind candidate discovery/runtime posture without authority promotion."""
    governed_manifest = registry_report.discovery_manifest
    if governed_manifest is None or not governed_manifest.is_bound:
        raise MethodCatalogDiscoveryProvenanceError("catalog_governed_discovery_manifest_unbound")
    if (
        governed_manifest.entry_point_groups
        or governed_manifest.dev_scan_enabled
        or len(governed_manifest.builtin_loaders) != 1
    ):
        raise MethodCatalogDiscoveryProvenanceError(
            "catalog_governed_source_policy_not_builtins_only"
        )
    from polisyos.foundry.extensions.discovery import BUILTIN_LOADER, ENTRY_POINT_GROUP

    expected_builtin_loader = str(BUILTIN_LOADER[0])
    if governed_manifest.builtin_loaders != (expected_builtin_loader,):
        raise MethodCatalogDiscoveryProvenanceError(
            "catalog_governed_builtin_loader_identity_mismatch"
        )
    if (
        ambient_manifest.entry_point_groups != (ENTRY_POINT_GROUP,)
        or ambient_manifest.builtin_loaders
        or not ambient_manifest.dev_scan_enabled
    ):
        raise MethodCatalogDiscoveryProvenanceError(
            "catalog_ambient_source_policy_mismatch"
        )
    if registry_report.registry_binding_sha256 is None:
        raise MethodCatalogDiscoveryProvenanceError(
            "catalog_governed_registry_binding_missing"
        )
    catalog_fqns = tuple(entry.fqn for entry in snapshot.entries)
    if catalog_fqns != registry_report.registry_fqns:
        raise MethodCatalogDiscoveryProvenanceError(
            "catalog_snapshot_admission_membership_mismatch"
        )

    governed_component_ids = tuple(sorted(row.component_id for row in governed_manifest.components))
    if catalog_fqns != governed_component_ids:
        raise MethodCatalogDiscoveryProvenanceError(
            "catalog_snapshot_governed_manifest_membership_mismatch"
        )
    ambient_component_ids = tuple(sorted(row.component_id for row in ambient_manifest.components))
    governed_set = set(governed_component_ids)
    ambient_set = set(ambient_component_ids)
    additions = tuple(sorted(ambient_set - governed_set))
    overlaps = tuple(sorted(ambient_set & governed_set))
    ambient_unbound = not ambient_manifest.is_bound
    ambient_status = "quarantined_unbound" if ambient_unbound else "declared_not_admitted"
    predicate_provenance = [
        {
            "predicate": "governed_discovery_policy",
            "classification": "recomputed",
            "decisive": True,
            "fail_closed_action": "reject",
        },
        *(
            {
                "predicate": f"governed.{row.predicate}",
                "classification": row.classification,
                "decisive": True,
                "fail_closed_action": "reject",
            }
            for row in governed_manifest.predicate_provenance
        ),
        {
            "predicate": "registry_matches_governed_manifest",
            "classification": "recomputed",
            "decisive": True,
            "fail_closed_action": "reject",
        },
        {
            "predicate": "governed_registry_content_binding",
            "classification": "recomputed",
            "decisive": True,
            "fail_closed_action": "reject",
        },
        {
            "predicate": "ambient_discovery_exclusion_policy",
            "classification": "recomputed",
            "decisive": True,
            "fail_closed_action": "reject",
        },
        *(
            {
                "predicate": f"ambient.{row.predicate}",
                "classification": row.classification,
                "decisive": False,
                "fail_closed_action": "quarantine",
            }
            for row in ambient_manifest.predicate_provenance
        ),
        {
            "predicate": "runtime_backend_package_identity",
            "classification": "recomputed",
            "decisive": True,
            "fail_closed_action": "reject",
        },
        {
            "predicate": "recorded_live_provenance_equality",
            "classification": "recomputed",
            "decisive": True,
            "fail_closed_action": "reject",
        },
        *(dict(row) for row in additional_predicate_provenance),
    ]
    predicate_names = [str(row.get("predicate") or "") for row in predicate_provenance]
    if any(not name for name in predicate_names) or len(set(predicate_names)) != len(
        predicate_names
    ):
        raise MethodCatalogDiscoveryProvenanceError(
            "catalog_predicate_provenance_names_invalid"
        )
    canonical_bindings = {
        str(field): list(references)
        for field, references in sorted((predicate_bindings or {}).items())
    }
    known_predicates = set(predicate_names)
    if any(
        not references or any(reference not in known_predicates for reference in references)
        for references in canonical_bindings.values()
    ):
        raise MethodCatalogDiscoveryProvenanceError(
            "catalog_predicate_binding_reference_invalid"
        )
    payload: dict[str, Any] = {
        "schema_version": "policyos.method_catalog_provenance_manifest.v1",
        "governed_discovery": {
            "source_policy": {
                "include_builtins": True,
                "include_entry_points": False,
                "include_dev_scan": False,
            },
            "manifest_id": governed_manifest.manifest_id,
            "component_count": len(governed_component_ids),
            "component_set_sha256": _sha256_payload(governed_component_ids),
            "registry_fqn_set_sha256": _sha256_payload(catalog_fqns),
            "registry_binding_sha256": registry_report.registry_binding_sha256,
            "unbound_inputs": list(governed_manifest.unbound_inputs),
        },
        "ambient_discovery": {
            "source_policy": {
                "include_builtins": False,
                "include_entry_points": True,
                "include_dev_scan": True,
            },
            "manifest_id": ambient_manifest.manifest_id,
            "entry_points": [row.as_dict() for row in ambient_manifest.entry_points],
            "dev_scan_roots": [row.as_dict() for row in ambient_manifest.dev_scan_roots],
            "dev_scan_files": [row.as_dict() for row in ambient_manifest.dev_scan_files],
            "component_count": len(ambient_component_ids),
            "component_set_sha256": _sha256_payload(ambient_component_ids),
            "added_component_ids": list(additions),
            "overlap_component_count": len(overlaps),
            "overlap_component_set_sha256": _sha256_payload(overlaps),
            "unbound_inputs": list(ambient_manifest.unbound_inputs),
            "admission": {
                "status": ambient_status,
                "included_in_governed_denominator": False,
                "fail_closed_action": "quarantine",
            },
        },
        "runtime_backend_identity": _build_candidate_method_catalog_runtime_identity(snapshot),
        "predicate_provenance": predicate_provenance,
        "predicate_bindings": canonical_bindings,
        "predicate_admission_policy": [
            {
                "classification": "recomputed",
                "admitted": True,
                "fail_closed_action": None,
            },
            {
                "classification": "independently_reconciled",
                "admitted": True,
                "fail_closed_action": None,
            },
            {
                "classification": "consumer_asserted",
                "admitted": False,
                "fail_closed_action": "reject_or_quarantine",
            },
            {
                "classification": "institutionally_supplied",
                "admitted": False,
                "fail_closed_action": "reject_or_quarantine",
            },
            {
                "classification": "not_established",
                "admitted": False,
                "fail_closed_action": "reject_or_quarantine",
            },
        ],
    }
    payload["provenance_id"] = method_catalog_provenance_id(payload)
    return payload


def _admit_catalog_registry(
    registry: MethodRegistry,
    *,
    registry_report: FoundryExtensionRegistryReport | None,
    require_bound_discovery: bool,
) -> None:
    if registry_report is None:
        if require_bound_discovery:
            raise MethodCatalogDiscoveryProvenanceError("catalog_discovery_provenance_missing")
        ensure_all_methods_registered(registry)
        return

    if require_bound_discovery:
        if registry_report.preexisting_method_fqns:
            raise MethodCatalogDiscoveryProvenanceError(
                "catalog_registry_preexisting_membership_not_admitted:"
                + "|".join(registry_report.preexisting_method_fqns)
            )
        manifest = registry_report.discovery_manifest
        if manifest is None:
            raise MethodCatalogDiscoveryProvenanceError("catalog_discovery_provenance_missing")
        if not manifest.is_bound:
            raise MethodCatalogDiscoveryProvenanceError(
                "catalog_discovery_provenance_unbound:" + "|".join(manifest.unbound_inputs)
            )
        if not registry_report.success:
            raise MethodCatalogDiscoveryProvenanceError("catalog_registry_admission_errors_present")

    current_snapshot = registry.snapshot()
    current_fqns = tuple(entry.fqn for entry in current_snapshot.entries())
    if current_fqns != registry_report.registry_fqns:
        raise MethodCatalogDiscoveryProvenanceError(
            "catalog_registry_admission_membership_mismatch"
        )
    from polisyos.foundry.extensions.registry import (
        _method_registry_snapshot_binding_sha256,
    )

    if (
        registry_report.registry_binding_sha256 is None
        or _method_registry_snapshot_binding_sha256(current_snapshot)
        != registry_report.registry_binding_sha256
    ):
        raise MethodCatalogDiscoveryProvenanceError("catalog_registry_admission_content_mismatch")
    if require_bound_discovery:
        manifest = registry_report.discovery_manifest
        assert manifest is not None
        manifest_fqns = tuple(sorted(row.component_id for row in manifest.components))
        if manifest_fqns != current_fqns:
            raise MethodCatalogDiscoveryProvenanceError(
                "catalog_registry_manifest_membership_mismatch"
            )


def _sha256_payload(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def method_catalog_governed_provenance_projection(
    payload: Mapping[str, object],
) -> dict[str, object]:
    """Project full catalog custody evidence into its governed comparison content.

    Ambient observations remain present in ``payload`` and bound by the ordinary
    provenance identity. They are non-decisive here only when the parent admission
    and every predicate row carry the complete structural declaration emitted by
    this owner.

    Args:
        payload: Complete method-catalog provenance manifest.

    Returns:
        A detached JSON-compatible mapping containing every governed field and the
        structural shells of admitted non-decisive predicates.

    Raises:
        MethodCatalogDiscoveryProvenanceError: If an admission or predicate row is
            missing, malformed, duplicated, or contradictory.
    """

    ambient = payload.get("ambient_discovery")
    if not isinstance(ambient, Mapping):
        raise MethodCatalogDiscoveryProvenanceError(
            "catalog_ambient_discovery_manifest_missing"
        )
    admission = ambient.get("admission")
    if not isinstance(admission, Mapping) or set(admission) != {
        "status",
        "included_in_governed_denominator",
        "fail_closed_action",
    }:
        raise MethodCatalogDiscoveryProvenanceError("catalog_ambient_input_not_quarantined")
    if (
        admission.get("included_in_governed_denominator") is not False
        or admission.get("fail_closed_action") != "quarantine"
        or admission.get("status") not in {"quarantined_unbound", "declared_not_admitted"}
    ):
        raise MethodCatalogDiscoveryProvenanceError("catalog_ambient_input_not_quarantined")
    source_policy = ambient.get("source_policy")
    if not isinstance(source_policy, Mapping):
        raise MethodCatalogDiscoveryProvenanceError("catalog_ambient_source_policy_mismatch")

    predicate_rows = payload.get("predicate_provenance")
    if not isinstance(predicate_rows, list):
        raise MethodCatalogDiscoveryProvenanceError("catalog_predicate_provenance_invalid")
    allowed_classifications = {
        "recomputed",
        "independently_reconciled",
        "consumer_asserted",
        "institutionally_supplied",
        "not_established",
    }
    projected_rows: list[dict[str, object]] = []
    predicate_names: set[str] = set()
    for row in predicate_rows:
        if not isinstance(row, Mapping) or set(row) != {
            "predicate",
            "classification",
            "decisive",
            "fail_closed_action",
        }:
            raise MethodCatalogDiscoveryProvenanceError(
                "catalog_predicate_provenance_invalid"
            )
        predicate = row.get("predicate")
        classification = row.get("classification")
        decisive = row.get("decisive")
        action = row.get("fail_closed_action")
        if (
            not isinstance(predicate, str)
            or not predicate
            or predicate in predicate_names
            or classification not in allowed_classifications
            or not isinstance(decisive, bool)
            or action not in {"reject", "quarantine"}
        ):
            raise MethodCatalogDiscoveryProvenanceError(
                "catalog_predicate_provenance_invalid"
            )
        predicate_names.add(predicate)
        if decisive:
            if action != "reject" or classification in {
                "consumer_asserted",
                "institutionally_supplied",
                "not_established",
            }:
                raise MethodCatalogDiscoveryProvenanceError(
                    "catalog_predicate_provenance_invalid"
                )
            projected_rows.append(deepcopy(dict(row)))
        else:
            if action != "quarantine":
                raise MethodCatalogDiscoveryProvenanceError(
                    "catalog_predicate_provenance_invalid"
                )
            projected_rows.append(
                {
                    "predicate": predicate,
                    "decisive": False,
                    "fail_closed_action": "quarantine",
                }
            )

    projection = deepcopy(dict(payload))
    projection.pop("provenance_id", None)
    projection["ambient_discovery"] = {
        "source_policy": deepcopy(dict(source_policy)),
        "admission": {
            "included_in_governed_denominator": False,
            "fail_closed_action": "quarantine",
        },
    }
    projection["predicate_provenance"] = projected_rows
    return projection


def method_catalog_governed_provenance_id(payload: Mapping[str, object]) -> str:
    """Return the canonical governed comparison identity for catalog provenance."""

    projection = method_catalog_governed_provenance_projection(payload)
    return "method_catalog_governed_provenance_" + _sha256_payload(projection).removeprefix(
        "sha256:"
    )


def method_catalog_provenance_id(payload: Mapping[str, object]) -> str:
    """Return the canonical content identity for a catalog provenance manifest."""

    content = dict(payload)
    content.pop("provenance_id", None)
    return "method_catalog_provenance_" + _sha256_payload(content).removeprefix("sha256:")


def persist_method_catalog_snapshot(
    store: FileSystemCAS,
    snapshot: MethodCatalogSnapshot,
    *,
    inputs: list[InputRef] | None = None,
) -> MethodCatalogSnapshotRef:
    """Persist a method-catalog snapshot artifact and return its typed ref."""
    payload_ref = store.put_json(
        snapshot,
        PutOptions(
            kind="foundry.method_catalog_snapshot",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.MethodCatalogSnapshot", version="2.0"),
            inputs=list(inputs or []),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return MethodCatalogSnapshotRef(artifact_id=payload_ref.artifact_id)


def build_method_capability_matrix(
    snapshot: MethodCatalogSnapshot,
    *,
    runnable_only: bool = False,
) -> list[dict[str, Any]]:
    """Expose the catalog capability matrix as a machine-readable row set."""
    rows: list[dict[str, Any]] = []
    for entry in snapshot.entries:
        if runnable_only and not entry.runnable:
            continue
        rows.append(
            {
                "fqn": entry.fqn,
                "namespace": entry.namespace,
                "family": entry.family,
                "variant": entry.variant,
                **dict(entry.capability_matrix),
                "truthfulness_tier": entry.truthfulness_tier,
                "implementation_depth_tier": entry.implementation_depth_tier,
                "implementation_depth_notes": entry.implementation_depth_notes,
                "declared_truthfulness_tier": entry.declared_truthfulness_tier,
                "runtime_truthfulness_tier": entry.runtime_truthfulness_tier,
                "effective_truthfulness_tier": entry.effective_truthfulness_tier,
                "truthfulness_status": entry.truthfulness_status,
                "truthfulness_scope": entry.truthfulness_scope,
                "truthfulness_evidence_ref": entry.truthfulness_evidence_ref,
                "truthfulness_notes": entry.truthfulness_notes,
            }
        )
    return rows


def build_method_operator_evidence(
    snapshot: MethodCatalogSnapshot,
    *,
    runnable_only: bool = False,
    blocked_limit: int = 25,
) -> dict[str, Any]:
    """Build an operator-facing summary of applicability, replay, and degraded paths."""
    rows = build_method_capability_matrix(snapshot, runnable_only=runnable_only)
    runnable_rows = [row for row in rows if bool(row.get("runnable"))]
    blocked_rows = [row for row in rows if not bool(row.get("runnable"))]

    def _summarize(key: str) -> list[dict[str, Any]]:
        summary: dict[str, dict[str, Any]] = {}
        for row in rows:
            raw_value = row.get(key)
            value = "-" if raw_value in (None, "") else str(raw_value)
            bucket = summary.setdefault(
                value,
                {"value": value, "count": 0, "runnable_count": 0, "blocked_count": 0},
            )
            bucket["count"] += 1
            if bool(row.get("runnable")):
                bucket["runnable_count"] += 1
            else:
                bucket["blocked_count"] += 1
        return sorted(
            summary.values(),
            key=lambda item: (-int(item["count"]), str(item["value"])),
        )

    replay_contracts: dict[str, dict[str, Any]] = {}
    for row in rows:
        tier = str(row.get("determinism_tier") or "-")
        replay_contracts.setdefault(
            tier,
            {
                "determinism_tier": tier,
                "replay_semantics": row.get("replay_semantics"),
                "tolerance_budget": row.get("tolerance_budget"),
            },
        )

    blocked_details = [
        {
            "fqn": row["fqn"],
            "execution_backend": row.get("execution_backend"),
            "truthfulness_tier": row.get("truthfulness_tier"),
            "implementation_depth_tier": row.get("implementation_depth_tier"),
            "declared_truthfulness_tier": row.get("declared_truthfulness_tier"),
            "runtime_truthfulness_tier": row.get("runtime_truthfulness_tier"),
            "truthfulness_status": row.get("truthfulness_status"),
            "determinism_tier": row.get("determinism_tier"),
            "disabled_reasons": list(
                next(
                    (
                        entry.disabled_reasons
                        for entry in snapshot.entries
                        if entry.fqn == row["fqn"]
                    ),
                    (),
                )
            ),
        }
        for row in sorted(
            blocked_rows,
            key=lambda item: (
                -len(
                    next(
                        (
                            entry.disabled_reasons
                            for entry in snapshot.entries
                            if entry.fqn == item["fqn"]
                        ),
                        (),
                    )
                ),
                str(item["fqn"]),
            ),
        )[:blocked_limit]
    ]

    return {
        "snapshot_id": snapshot.snapshot_id,
        "generated_at": snapshot.generated_at.isoformat(),
        "method_count": len(rows),
        "runnable_count": len(runnable_rows),
        "blocked_count": len(blocked_rows),
        "backend_summary": _summarize("execution_backend"),
        "determinism_summary": _summarize("determinism_tier"),
        "truthfulness_summary": _summarize("truthfulness_tier"),
        "declared_truthfulness_summary": _summarize("declared_truthfulness_tier"),
        "runtime_truthfulness_summary": _summarize("runtime_truthfulness_tier"),
        "implementation_depth_summary": _summarize("implementation_depth_tier"),
        "replay_contracts": sorted(
            replay_contracts.values(),
            key=lambda item: str(item["determinism_tier"]),
        ),
        "blocked_methods": blocked_details,
    }


def _jsonable(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    return str(value)


def _causal_requirements_for_method(fqn: str) -> list[CausalIdentificationFamily]:
    normalized = str(fqn).strip().lower()
    if "causal.transport.symbolic_identify@" in normalized:
        return [
            CausalIdentificationFamily.FRONTDOOR,
            CausalIdentificationFamily.DO_CALCULUS_RULE2,
            CausalIdentificationFamily.DO_CALCULUS_RULE3,
            CausalIdentificationFamily.C_COMPONENT_FACTORIZATION,
        ]
    if (
        "causal.transport.check_transportability@" in normalized
        or "causal.parameter_transfer@" in normalized
    ):
        return [CausalIdentificationFamily.DIRECT]
    return []


def _package_available(package_name: str) -> bool:
    normalized = {"sklearn": "scikit-learn"}.get(package_name, package_name)
    return safe_version(normalized) is not None


def _available_execution_backends() -> set[str]:
    dispatcher = MethodDispatcher.get_instance()
    available: set[str] = set()
    for backend in ComputeBackend:
        try:
            dispatcher._resolve_runner(backend)
        except MethodBackendNotAvailableError:
            continue
        available.add(backend.value)
    return available


def _dependency_posture(
    required_deps: tuple[str, ...],
    optional_deps: tuple[str, ...],
    runtime_stack: tuple[str, ...],
) -> dict[str, Any]:
    required_map = {dep: _package_available(dep) for dep in required_deps}
    optional_map = {dep: _package_available(dep) for dep in optional_deps}
    runtime_map = {dep: _package_available(dep) for dep in runtime_stack}
    return {
        "required": required_map,
        "optional": optional_map,
        "runtime_stack": runtime_map,
        "all_required_available": all(required_map.values()) if required_map else True,
        "missing_required": [
            f"missing_dependency:{dep}" for dep, ok in required_map.items() if not ok
        ],
        "missing_optional": [dep for dep, ok in optional_map.items() if not ok],
        "missing_runtime_stack": [dep for dep, ok in runtime_map.items() if not ok],
    }


def _disabled_reasons_for(execution_backend: str, backend_available: bool) -> tuple[str, ...]:
    if backend_available:
        return ()
    return (f"execution_backend_unavailable:{execution_backend}",)


def _capture_entry_runtime_posture(
    execution_backend: ComputeBackend,
    method_class: type,
) -> BackendRuntimeFingerprint:
    return capture_backend_runtime_fingerprint(
        execution_backend,
        method_class=method_class,
    )


def _effective_determinism_tier(
    declared_tier: str | None,
    runtime_tier: DeterminismTier | None,
) -> str | None:
    declared = parse_determinism_tier(declared_tier)
    effective = _more_conservative_tier(declared, runtime_tier)
    if effective is not None:
        return effective.value
    return declared_tier


def _more_conservative_tier(
    left: DeterminismTier | None,
    right: DeterminismTier | None,
) -> DeterminismTier | None:
    if left is None:
        return right
    if right is None:
        return left
    order = {
        DeterminismTier.STRICT_CPU: 0,
        DeterminismTier.LIBRARY_DETERMINISTIC: 1,
        DeterminismTier.BEST_EFFORT_GPU: 2,
        DeterminismTier.STATISTICAL: 3,
        DeterminismTier.NONDETERMINISTIC: 4,
    }
    return left if order[left] >= order[right] else right


def _shape_semantics(sig: Any) -> dict[str, Any]:
    def _slot_payload(slot: Any) -> dict[str, Any]:
        return {
            "name": slot.name,
            "slot_type": slot.slot_type.name.lower(),
            "rank": len(slot.shape),
            "shape": [str(axis) for axis in slot.shape],
        }

    return {
        "input_arity": len(sig.input_slots),
        "output_arity": len(sig.output_slots),
        "input_slots": [
            _slot_payload(slot) for slot in sorted(sig.input_slots, key=lambda item: item.name)
        ],
        "output_slots": [
            _slot_payload(slot) for slot in sorted(sig.output_slots, key=lambda item: item.name)
        ],
        "has_symbolic_dimensions": any(
            not isinstance(axis, int)
            for slot in tuple(sig.input_slots) + tuple(sig.output_slots)
            for axis in slot.shape
        ),
    }


def _effect_semantics(sig: Any, entry: Any) -> dict[str, Any]:
    side_effect = entry.metadata.side_effect_profile.value if entry is not None else "none"
    return {
        "method_kind": sig.kind.value,
        "side_effect_profile": side_effect,
        "emits_patch": side_effect == "patch_emission",
        "emits_artifact": side_effect == "artifact_emission",
        "requires_training": side_effect == "training",
    }


def _dependency_semantics(sig: Any, entry: Any) -> dict[str, Any]:
    metadata = entry.metadata if entry is not None else None
    return {
        "hard_requires": sorted(str(item) for item in sig.requires),
        "conflicts_with": sorted(str(item) for item in sig.conflicts_with),
        "recommended_prerequisites": list(getattr(metadata, "prerequisites", ())),
        "diagnostic_checks": list(getattr(metadata, "diagnostic_checks", ())),
    }


def _declared_truthfulness_tier(entry: Any) -> str | None:
    metadata = entry.metadata if entry is not None else None
    candidate = getattr(metadata, "declared_truthfulness_tier", None)
    parsed = parse_truthfulness_tier(candidate)
    if parsed is None:
        return None
    return parsed.value


def _declared_truthfulness_scope(entry: Any) -> str | None:
    metadata = entry.metadata if entry is not None else None
    candidate = getattr(metadata, "truthfulness_scope", None)
    parsed = parse_truthfulness_scope(candidate)
    if parsed is None:
        return None
    return parsed.value


def _truthfulness_notes_for_status(status: TruthfulnessStatus) -> str:
    if status is TruthfulnessStatus.CATALOG_ONLY:
        return "Catalog declares a truthfulness tier, but no runtime certificate has been observed yet."
    if status is TruthfulnessStatus.RUNTIME_ONLY:
        return "Runtime produced a truthfulness certificate without a catalog declaration."
    if status is TruthfulnessStatus.RUNTIME_DOWNGRADED:
        return "Runtime evidence downgraded the catalog truthfulness claim."
    if status is TruthfulnessStatus.RUNTIME_CONSISTENT:
        return "Runtime evidence matched the catalog truthfulness claim."
    if status is TruthfulnessStatus.CATALOG_UNDERCLAIMS:
        return "Catalog remains the conservative bound even though runtime evidence was stronger."
    return "No runtime truthfulness certificate available; advisor should treat this method as unverified."


def _truthfulness_profile(sig: Any, entry: Any) -> tuple[str, str]:
    tags = (
        {str(tag).strip().lower() for tag in getattr(entry.metadata, "tags", ())}
        if entry is not None
        else set()
    )
    text = " ".join(
        [
            sig.namespace.lower(),
            sig.family.lower(),
            sig.variant.lower(),
            " ".join(sorted(tags)),
            str(getattr(entry.metadata, "description", "")).lower() if entry is not None else "",
        ]
    )
    if any(
        token in text for token in ("baseline", "heuristic", "proxy", "scorecard", "random_feature")
    ):
        return (
            "heuristic_baseline",
            "Fast baseline or proxy implementation; do not present as equivalent depth to trainable or production estimators.",
        )
    if any(
        token in text
        for token in (
            "discovery",
            "diagnostic",
            "identify",
            "mcda",
            "score",
            "ranking",
            "transport",
        )
    ):
        return (
            "structural_scoring",
            "Primarily structural/scoring logic; useful for screening, diagnostics, or planning rather than final policy estimation.",
        )
    if (entry is not None and entry.metadata.side_effect_profile.value == "training") or any(
        token in text for token in ("transformer", "neural", "deep", "trainable", "policy_learning")
    ):
        return (
            "frontier_trainable",
            "Frontier or trainable implementation with higher operational complexity and stronger runtime/dependency expectations.",
        )
    return (
        "production_method",
        "Production-oriented method surface with explicit ABI, dependency posture, and runtime capability reporting.",
    )


__all__ = [
    "MethodCatalogDiscoveryProvenanceError",
    "build_method_capability_matrix",
    "build_method_catalog_provenance_manifest",
    "build_method_catalog_runtime_identity",
    "build_method_catalog_snapshot",
    "method_catalog_provenance_id",
    "persist_method_catalog_snapshot",
]
