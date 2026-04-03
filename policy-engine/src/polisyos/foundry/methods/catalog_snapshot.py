"""Public methods catalog snapshot module API."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from polisyos.core.artifacts.manifest import InputRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec, truncated_hash
from polisyos.core.contracts.execution_plan import (
    MethodCatalogEntry,
    MethodCatalogSnapshot,
    MethodCatalogSnapshotRef,
)
from polisyos.foundry.methods.base import ComputeBackend
from polisyos.foundry.methods.catalog import ensure_all_methods_registered
from polisyos.foundry.methods.backends.dispatch import (
    BackendNotAvailableError as MethodBackendNotAvailableError,
    MethodDispatcher,
)
from polisyos.foundry.methods.backends.runtime_fingerprint import runtime_stack_for, safe_version
from polisyos.foundry.methods.catalog.causal.capabilities import build_causal_capability_contract
from polisyos.foundry.methods.registry import MethodRegistry
from polisyos.ir.analytics.causal_capabilities import (
    CausalCapabilityContract,
    CausalIdentificationFamily,
)


def build_method_catalog_snapshot(
    *,
    run_id: str | None = None,
    registry: MethodRegistry | None = None,
    capability_contract: CausalCapabilityContract | None = None,
) -> MethodCatalogSnapshot:
    """Build method catalog snapshot."""
    reg = registry or MethodRegistry.get_instance()
    ensure_all_methods_registered(reg)
    contract = capability_contract or build_causal_capability_contract()
    available_backends = _available_execution_backends()
    signatures = reg.list_all()
    entries: list[MethodCatalogEntry] = []
    for sig in signatures:
        entry = reg.get_entry(sig.fqn)
        method_cls = reg.get(sig.fqn)
        runtime_stack = runtime_stack_for(method_cls)
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
            backend_available = sig.execution_backend.value in available_backends
            disabled_reasons = list(_disabled_reasons_for(sig.execution_backend.value, backend_available))
            disabled_reasons.extend(dependency_posture["missing_required"])
        else:
            dependency_posture = _dependency_posture((), (), runtime_stack)
            backend_available = sig.execution_backend.value in available_backends
            disabled_reasons = list(_disabled_reasons_for(sig.execution_backend.value, backend_available))
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
        runnable = backend_available and not dependency_posture["missing_required"] and causal_available is not False
        determinism_tier = None
        if entry is not None and entry.metadata.determinism_tier is not None:
            determinism_tier = entry.metadata.determinism_tier.value
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
            "required_deps": list(entry.metadata.required_deps) if entry is not None else [],
            "optional_deps": list(entry.metadata.optional_deps) if entry is not None else [],
            "fallback_policy": entry.metadata.fallback_policy if entry is not None else "none",
            "side_effect_profile": (
                entry.metadata.side_effect_profile.value if entry is not None else "none"
            ),
            "backend_available": backend_available,
            "runnable": runnable,
        }
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
                # Rich semantic metadata — sourced from MethodMetadata
                description=str(entry.metadata.description) if entry is not None else "",
                citations=list(entry.metadata.citations) if entry is not None else [],
                assumptions=sorted(str(k) for k in entry.metadata.assumptions.keys()) if entry is not None else [],
                when_to_use=str(getattr(entry.metadata, "when_to_use", "")) if entry is not None else "",
                when_not_to_use=str(getattr(entry.metadata, "when_not_to_use", "")) if entry is not None else "",
                prerequisites=list(getattr(entry.metadata, "prerequisites", ())) if entry is not None else [],
                diagnostic_checks=list(getattr(entry.metadata, "diagnostic_checks", ())) if entry is not None else [],
                typical_min_obs=getattr(entry.metadata, "typical_min_obs", None) if entry is not None else None,
                output_interpretation=str(getattr(entry.metadata, "output_interpretation", "")) if entry is not None else "",
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
        generated_at=datetime.now(timezone.utc),
        causal_capability_hash=contract.dependency_fingerprint if contract is not None else None,
        causal_runtime_posture=(
            contract.model_dump(mode="json") if contract is not None else {}
        ),
        entries=entries,
        notes=[f"method_count:{len(entries)}"],
    )


def persist_method_catalog_snapshot(
    store: FileSystemCAS,
    snapshot: MethodCatalogSnapshot,
    *,
    inputs: list[InputRef] | None = None,
) -> MethodCatalogSnapshotRef:
    """Persist method catalog snapshot helper."""
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
        "missing_required": [f"missing_dependency:{dep}" for dep, ok in required_map.items() if not ok],
        "missing_optional": [dep for dep, ok in optional_map.items() if not ok],
        "missing_runtime_stack": [dep for dep, ok in runtime_map.items() if not ok],
    }


def _disabled_reasons_for(execution_backend: str, backend_available: bool) -> tuple[str, ...]:
    if backend_available:
        return ()
    return (f"execution_backend_unavailable:{execution_backend}",)


__all__ = [
    "build_method_catalog_snapshot",
    "persist_method_catalog_snapshot",
]
