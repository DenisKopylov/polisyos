from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from polisyos.core.artifacts.manifest import ArtifactRef, InputRef, SchemaInfo
from polisyos.core.artifacts.registry import RegistryBundle, RegistryBundlePayload
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.ir.kernel import (
    DEFAULT_CONSTRAINT_REGISTRY,
    DEFAULT_MECHANISM_REGISTRY,
    DEFAULT_MERGE_RULE_REGISTRY,
    DEFAULT_METRIC_REGISTRY,
    DEFAULT_SELECTOR_FIELD_REGISTRY,
    DEFAULT_SLOT_REGISTRY,
    DEFAULT_UNITS_REGISTRY,
    MechanismTypeRegistry,
    MergeRuleRegistry,
    MetricRegistry,
    SelectorFieldRegistry,
    SlotRegistry,
    UnitsRegistry,
)


def _schema_info(name: str, obj: Any) -> SchemaInfo | None:
    version = getattr(obj, "schema_version", None)
    if version is None:
        return None
    return SchemaInfo(name=name, version=str(version))


def _put_registry(
    store: FileSystemCAS,
    *,
    obj: BaseModel | dict[str, Any],
    kind: str,
    schema_name: str,
    inputs: list[InputRef] | None = None,
) -> ArtifactRef:
    return store.put_json(
        obj,
        PutOptions(
            kind=kind,
            media_type="application/json",
            schema=_schema_info(schema_name, obj),
            inputs=inputs,
        ),
    )


def build_registry_bundle(
    store: FileSystemCAS,
    *,
    slot_registry: SlotRegistry,
    merge_registry: MergeRuleRegistry,
    mechanism_registry: MechanismTypeRegistry,
    constraint_registry: BaseModel | dict[str, Any],
    selector_field_registry: SelectorFieldRegistry | None = None,
    metric_registry: MetricRegistry | None = None,
    units_registry: UnitsRegistry | None = None,
    trust_registry: BaseModel | dict[str, Any] | None = None,
) -> RegistryBundle:
    slot_ref = _put_registry(
        store,
        obj=slot_registry,
        kind="ir.slot_registry",
        schema_name="polisyos.ir.kernel.SlotRegistry",
    )
    merge_ref = _put_registry(
        store,
        obj=merge_registry,
        kind="ir.merge_rule_registry",
        schema_name="polisyos.ir.kernel.MergeRuleRegistry",
    )
    mech_ref = _put_registry(
        store,
        obj=mechanism_registry,
        kind="ir.mechanism_registry",
        schema_name="polisyos.ir.kernel.MechanismTypeRegistry",
    )
    constraint_ref = _put_registry(
        store,
        obj=constraint_registry,
        kind="ir.constraint_registry",
        schema_name="polisyos.ir.kernel.ConstraintRegistry",
    )

    selector_field_ref = None
    if selector_field_registry is not None:
        selector_field_ref = _put_registry(
            store,
            obj=selector_field_registry,
            kind="ir.selector_field_registry",
            schema_name="polisyos.ir.kernel.SelectorFieldRegistry",
        )

    metric_ref = None
    if metric_registry is not None:
        metric_ref = _put_registry(
            store,
            obj=metric_registry,
            kind="ir.metric_registry",
            schema_name="polisyos.ir.kernel.MetricRegistry",
        )

    units_ref = None
    if units_registry is not None:
        units_ref = _put_registry(
            store,
            obj=units_registry,
            kind="ir.units_registry",
            schema_name="polisyos.ir.kernel.UnitsRegistry",
        )

    trust_ref = None
    if trust_registry is not None:
        trust_ref = _put_registry(
            store,
            obj=trust_registry,
            kind="ir.trust_registry",
            schema_name="polisyos.ir.kernel.TrustRegistry",
        )

    payload = RegistryBundlePayload(
        slot_registry=slot_ref,
        merge_registry=merge_ref,
        constraint_registry=constraint_ref,
        selector_field_registry=selector_field_ref,
        metric_registry=metric_ref,
        mechanism_registry=mech_ref,
        trust_registry=trust_ref,
        units_registry=units_ref,
    )

    inputs = [
        InputRef(artifact_id=slot_ref.artifact_id, role="slot_registry"),
        InputRef(artifact_id=merge_ref.artifact_id, role="merge_registry"),
        InputRef(artifact_id=constraint_ref.artifact_id, role="constraint_registry"),
        InputRef(artifact_id=mech_ref.artifact_id, role="mechanism_registry"),
    ]
    if selector_field_ref is not None:
        inputs.append(
            InputRef(artifact_id=selector_field_ref.artifact_id, role="selector_field_registry")
        )
    if metric_ref is not None:
        inputs.append(InputRef(artifact_id=metric_ref.artifact_id, role="metric_registry"))
    if units_ref is not None:
        inputs.append(InputRef(artifact_id=units_ref.artifact_id, role="units_registry"))
    if trust_ref is not None:
        inputs.append(InputRef(artifact_id=trust_ref.artifact_id, role="trust_registry"))

    bundle_ref = _put_registry(
        store,
        obj=payload,
        kind="core.registry_bundle",
        schema_name="polisyos.core.RegistryBundlePayload",
        inputs=inputs,
    )

    return RegistryBundle(bundle_ref=bundle_ref, **payload.model_dump())


def build_default_registry_bundle(store: FileSystemCAS) -> RegistryBundle:
    return build_registry_bundle(
        store,
        slot_registry=DEFAULT_SLOT_REGISTRY,
        merge_registry=DEFAULT_MERGE_RULE_REGISTRY,
        mechanism_registry=DEFAULT_MECHANISM_REGISTRY,
        constraint_registry=DEFAULT_CONSTRAINT_REGISTRY,
        selector_field_registry=DEFAULT_SELECTOR_FIELD_REGISTRY,
        metric_registry=DEFAULT_METRIC_REGISTRY,
        units_registry=DEFAULT_UNITS_REGISTRY,
    )
