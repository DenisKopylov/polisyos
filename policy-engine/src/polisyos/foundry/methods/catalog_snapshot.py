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
from polisyos.foundry.methods.catalog import ensure_all_methods_registered
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
    reg = registry or MethodRegistry.get_instance()
    ensure_all_methods_registered(reg)
    contract = capability_contract or build_causal_capability_contract()
    signatures = reg.list_all()
    entries: list[MethodCatalogEntry] = []
    for sig in signatures:
        entry = reg.get_entry(sig.fqn)
        tags: list[str] = []
        deprecations: list[str] = []
        incompatibilities: list[str] = []
        if entry is not None:
            tags = sorted(str(tag) for tag in entry.metadata.tags)
            deprecations = sorted(tag for tag in tags if tag.startswith("deprecated"))
            incompatibilities = sorted(str(item) for item in entry.signature.conflicts_with)
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
        entries.append(
            MethodCatalogEntry(
                fqn=sig.fqn,
                namespace=sig.namespace,
                name=sig.name,
                version=sig.version,
                backend=sig.backend.value,
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
    payload_ref = store.put_json(
        snapshot,
        PutOptions(
            kind="foundry.method_catalog_snapshot",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.MethodCatalogSnapshot", version="1.0"),
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


__all__ = [
    "build_method_catalog_snapshot",
    "persist_method_catalog_snapshot",
]
