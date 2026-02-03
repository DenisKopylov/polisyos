from __future__ import annotations

import hashlib
from typing import Any, Iterable, Literal, Sequence

from pydantic import Field
from typing_extensions import Annotated

from polisyos.ir.canon import to_canonical_bytes
from polisyos.ir.kernel.base import ID_PATTERN, KernelModel
from polisyos.ir.kernel.constraints import ConstraintRegistry
from polisyos.ir.kernel.mechanisms import MechanismTypeRegistry
from polisyos.ir.kernel.merge_rules import MergeRuleRegistry
from polisyos.ir.kernel.metrics import MetricRegistry
from polisyos.ir.kernel.selector_fields import SelectorFieldRegistry
from polisyos.ir.kernel.slots import SlotRegistry
from polisyos.ir.kernel.trust import TrustRegistry
from polisyos.ir.kernel.units import UnitsRegistry
from polisyos.ir.predicate import PredicateRegistry, PrivacyPolicyRegistry

SCHEMA_VERSION_PATTERN = r"^\d+\.\d+$"

RESERVED_NAMESPACE_PREFIXES: tuple[str, ...] = ("core.", "world.")


class RegistryFragmentMeta(KernelModel):
    schema_version: str = Field("1.0", pattern=SCHEMA_VERSION_PATTERN)
    fragment_id: str = Field(..., pattern=ID_PATTERN)
    namespace: str = Field(..., pattern=ID_PATTERN)
    priority: int = Field(0)
    depends_on: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class TimeAxisSpec(KernelModel):
    axis_id: str = Field(..., pattern=ID_PATTERN)
    description: str | None = None
    notes: list[str] = Field(default_factory=list)


class TimeAxisRegistry(KernelModel):
    schema_version: str = Field("1.0", pattern=SCHEMA_VERSION_PATTERN)
    axes: dict[str, TimeAxisSpec] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)


class GeoAreaSpec(KernelModel):
    geo_id: str = Field(..., pattern=ID_PATTERN)
    name: str | None = None
    kind: str | None = None
    notes: list[str] = Field(default_factory=list)


class GeoRegistry(KernelModel):
    schema_version: str = Field("1.0", pattern=SCHEMA_VERSION_PATTERN)
    areas: dict[str, GeoAreaSpec] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)


class ActorTypeSpec(KernelModel):
    actor_type_id: str = Field(..., pattern=ID_PATTERN)
    name: str | None = None
    description: str | None = None
    notes: list[str] = Field(default_factory=list)


class ActorRegistry(KernelModel):
    schema_version: str = Field("1.0", pattern=SCHEMA_VERSION_PATTERN)
    actor_types: dict[str, ActorTypeSpec] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)


class ConceptSpec(KernelModel):
    concept_id: str = Field(..., pattern=ID_PATTERN)
    name: str | None = None
    description: str | None = None
    notes: list[str] = Field(default_factory=list)


class ConceptRegistry(KernelModel):
    schema_version: str = Field("1.0", pattern=SCHEMA_VERSION_PATTERN)
    concepts: dict[str, ConceptSpec] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)


class RegistryBundle(KernelModel):
    schema_version: str = Field("1.0", pattern=SCHEMA_VERSION_PATTERN)
    units: UnitsRegistry | None = None
    trust: TrustRegistry | None = None
    predicates: PredicateRegistry | None = None
    privacy: PrivacyPolicyRegistry | None = None
    metrics: MetricRegistry | None = None
    mechanisms: MechanismTypeRegistry | None = None
    slots: SlotRegistry | None = None
    selector_fields: SelectorFieldRegistry | None = None
    merge_rules: MergeRuleRegistry | None = None
    constraints: ConstraintRegistry | None = None
    time: TimeAxisRegistry | None = None
    geo: GeoRegistry | None = None
    actors: ActorRegistry | None = None
    concepts: ConceptRegistry | None = None
    notes: list[str] = Field(default_factory=list)


class UnitsFragment(KernelModel):
    kind: Literal["units"] = "units"
    meta: RegistryFragmentMeta
    payload: UnitsRegistry


class TrustFragment(KernelModel):
    kind: Literal["trust"] = "trust"
    meta: RegistryFragmentMeta
    payload: TrustRegistry


class PredicatesFragment(KernelModel):
    kind: Literal["predicates"] = "predicates"
    meta: RegistryFragmentMeta
    payload: PredicateRegistry


class PrivacyFragment(KernelModel):
    kind: Literal["privacy"] = "privacy"
    meta: RegistryFragmentMeta
    payload: PrivacyPolicyRegistry


class MetricsFragment(KernelModel):
    kind: Literal["metrics"] = "metrics"
    meta: RegistryFragmentMeta
    payload: MetricRegistry


class MechanismsFragment(KernelModel):
    kind: Literal["mechanisms"] = "mechanisms"
    meta: RegistryFragmentMeta
    payload: MechanismTypeRegistry


class SlotsFragment(KernelModel):
    kind: Literal["slots"] = "slots"
    meta: RegistryFragmentMeta
    payload: SlotRegistry


class SelectorFieldsFragment(KernelModel):
    kind: Literal["selector_fields"] = "selector_fields"
    meta: RegistryFragmentMeta
    payload: SelectorFieldRegistry


class MergeRulesFragment(KernelModel):
    kind: Literal["merge_rules"] = "merge_rules"
    meta: RegistryFragmentMeta
    payload: MergeRuleRegistry


class ConstraintsFragment(KernelModel):
    kind: Literal["constraints"] = "constraints"
    meta: RegistryFragmentMeta
    payload: ConstraintRegistry


class TimeFragment(KernelModel):
    kind: Literal["time"] = "time"
    meta: RegistryFragmentMeta
    payload: TimeAxisRegistry


class GeoFragment(KernelModel):
    kind: Literal["geo"] = "geo"
    meta: RegistryFragmentMeta
    payload: GeoRegistry


class ActorsFragment(KernelModel):
    kind: Literal["actors"] = "actors"
    meta: RegistryFragmentMeta
    payload: ActorRegistry


class ConceptsFragment(KernelModel):
    kind: Literal["concepts"] = "concepts"
    meta: RegistryFragmentMeta
    payload: ConceptRegistry


RegistryFragment = Annotated[
    UnitsFragment
    | TrustFragment
    | PredicatesFragment
    | PrivacyFragment
    | MetricsFragment
    | MechanismsFragment
    | SlotsFragment
    | SelectorFieldsFragment
    | MergeRulesFragment
    | ConstraintsFragment
    | TimeFragment
    | GeoFragment
    | ActorsFragment
    | ConceptsFragment,
    Field(discriminator="kind"),
]


class ComposePolicy(KernelModel):
    mode: Literal["error_on_conflict", "prefer_higher_priority"] = "error_on_conflict"


class RegistryComposeRequest(KernelModel):
    schema_version: str = Field("1.0", pattern=SCHEMA_VERSION_PATTERN)
    fragments: list[RegistryFragment]
    base_registries: RegistryBundle | None = None
    policy: ComposePolicy = Field(default_factory=ComposePolicy)


class RegistryConflict(KernelModel):
    registry_kind: str
    item_key: str
    conflict_kind: Literal[
        "duplicate_identical",
        "duplicate_different",
        "invalid_item",
        "reserved_prefix",
        "dependency_missing",
    ]
    left_fragment_id: str | None = None
    right_fragment_id: str | None = None
    left_value_hash: str | None = None
    right_value_hash: str | None = None
    resolution: Literal["none", "chose_left", "chose_right", "merged"] = "none"
    message: str | None = None


class RegistryComposeResult(KernelModel):
    schema_version: str = Field("1.0", pattern=SCHEMA_VERSION_PATTERN)
    composed: RegistryBundle | None = None
    conflicts: list[RegistryConflict] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    applied_fragments: list[str] = Field(default_factory=list)
    deterministic_hash: str | None = None


def _hash_item(value: Any) -> str:
    canonical = to_canonical_bytes(value)
    return f"sha256:{hashlib.sha256(canonical).hexdigest()}"


def _sorted_fragments(fragments: Sequence[RegistryFragment]) -> list[RegistryFragment]:
    return sorted(
        fragments,
        key=lambda frag: (-frag.meta.priority, frag.meta.fragment_id),
    )


def _registry_items(registry: Any, *, kind: str) -> list[tuple[str, str, Any]]:
    """Return list of (registry_kind, item_key, item_value)."""
    items: list[tuple[str, str, Any]] = []
    if registry is None:
        return items

    if kind == "units":
        items.extend(("units", key, value) for key, value in registry.units.items())
    elif kind == "trust":
        items.extend(("trust", key, value) for key, value in registry.policies.items())
    elif kind == "predicates":
        items.extend(("predicates.scalars", key, value) for key, value in registry.scalars.items())
        items.extend(("predicates.edges", key, value) for key, value in registry.edges.items())
    elif kind == "privacy":
        items.extend(("privacy", key, value) for key, value in registry.policies.items())
    elif kind == "metrics":
        items.extend(("metrics", key, value) for key, value in registry.metrics.items())
    elif kind == "mechanisms":
        items.extend(("mechanisms", key, value) for key, value in registry.mechanisms.items())
    elif kind == "slots":
        items.extend(("slots", key, value) for key, value in registry.slots.items())
    elif kind == "selector_fields":
        items.extend(("selector_fields", key, value) for key, value in registry.fields.items())
    elif kind == "merge_rules":
        items.extend(("merge_rules", key, value) for key, value in registry.rules.items())
    elif kind == "constraints":
        items.extend(("constraints", key, value) for key, value in registry.constraints.items())
    elif kind == "time":
        items.extend(("time", key, value) for key, value in registry.axes.items())
    elif kind == "geo":
        items.extend(("geo", key, value) for key, value in registry.areas.items())
    elif kind == "actors":
        items.extend(("actors", key, value) for key, value in registry.actor_types.items())
    elif kind == "concepts":
        items.extend(("concepts", key, value) for key, value in registry.concepts.items())

    return items


def _apply_items_to_registry(registry: Any, *, kind: str, items: dict[str, Any]) -> Any:
    if registry is None:
        registry = _empty_registry_for_kind(kind)
    if kind == "units":
        return UnitsRegistry(units=items, notes=list(registry.notes))
    if kind == "trust":
        return TrustRegistry(policies=items, notes=list(registry.notes))
    if kind == "predicates":
        scalars = items.get("scalars", {})
        edges = items.get("edges", {})
        return PredicateRegistry(scalars=scalars, edges=edges, notes=list(registry.notes))
    if kind == "privacy":
        return PrivacyPolicyRegistry(policies=items, notes=list(registry.notes))
    if kind == "metrics":
        return MetricRegistry(metrics=items, notes=list(registry.notes))
    if kind == "mechanisms":
        return MechanismTypeRegistry(mechanisms=items, notes=list(registry.notes))
    if kind == "slots":
        return SlotRegistry(slots=items, notes=list(registry.notes))
    if kind == "selector_fields":
        return SelectorFieldRegistry(fields=items, notes=list(registry.notes))
    if kind == "merge_rules":
        return MergeRuleRegistry(rules=items, notes=list(registry.notes))
    if kind == "constraints":
        return ConstraintRegistry(constraints=items, notes=list(registry.notes))
    if kind == "time":
        return TimeAxisRegistry(axes=items, notes=list(registry.notes))
    if kind == "geo":
        return GeoRegistry(areas=items, notes=list(registry.notes))
    if kind == "actors":
        return ActorRegistry(actor_types=items, notes=list(registry.notes))
    if kind == "concepts":
        return ConceptRegistry(concepts=items, notes=list(registry.notes))
    return registry


def _empty_registry_for_kind(kind: str) -> Any:
    if kind == "units":
        return UnitsRegistry()
    if kind == "trust":
        return TrustRegistry()
    if kind == "predicates":
        return PredicateRegistry()
    if kind == "privacy":
        return PrivacyPolicyRegistry()
    if kind == "metrics":
        return MetricRegistry()
    if kind == "mechanisms":
        return MechanismTypeRegistry()
    if kind == "slots":
        return SlotRegistry()
    if kind == "selector_fields":
        return SelectorFieldRegistry()
    if kind == "merge_rules":
        return MergeRuleRegistry()
    if kind == "constraints":
        return ConstraintRegistry()
    if kind == "time":
        return TimeAxisRegistry()
    if kind == "geo":
        return GeoRegistry()
    if kind == "actors":
        return ActorRegistry()
    if kind == "concepts":
        return ConceptRegistry()
    return None


def _apply_fragment_items(
    *,
    base_items: dict[str, Any],
    base_sources: dict[str, str],
    base_priorities: dict[str, int],
    fragment_meta: RegistryFragmentMeta,
    items: Iterable[tuple[str, str, Any]],
    mode: str,
    conflicts: list[RegistryConflict],
    reserved_prefixes: tuple[str, ...],
) -> dict[str, Any]:
    fragment_id = fragment_meta.fragment_id
    fragment_priority = fragment_meta.priority
    is_reserved_namespace = any(
        fragment_meta.namespace.startswith(prefix) for prefix in reserved_prefixes
    )

    for registry_kind, key, value in items:
        if any(key.startswith(prefix) for prefix in reserved_prefixes) and not is_reserved_namespace:
            conflicts.append(
                RegistryConflict(
                    registry_kind=registry_kind,
                    item_key=key,
                    conflict_kind="reserved_prefix",
                    right_fragment_id=fragment_id,
                    resolution="none",
                    message=f"Item '{key}' uses reserved prefix",
                )
            )
            continue

        existing = base_items.get(key)
        if existing is None:
            base_items[key] = value
            base_sources[key] = fragment_id
            base_priorities[key] = fragment_priority
            continue

        left_hash = _hash_item(existing)
        right_hash = _hash_item(value)
        left_source = base_sources.get(key)
        left_priority = base_priorities.get(key, -1)

        if left_hash == right_hash:
            conflicts.append(
                RegistryConflict(
                    registry_kind=registry_kind,
                    item_key=key,
                    conflict_kind="duplicate_identical",
                    left_fragment_id=left_source,
                    right_fragment_id=fragment_id,
                    left_value_hash=left_hash,
                    right_value_hash=right_hash,
                    resolution="none",
                    message="Duplicate identical item",
                )
            )
            continue

        resolution = "none"
        if mode == "prefer_higher_priority":
            choose_right = False
            if fragment_priority > left_priority:
                choose_right = True
            elif fragment_priority == left_priority and left_source:
                choose_right = fragment_id < left_source

            if choose_right:
                base_items[key] = value
                base_sources[key] = fragment_id
                base_priorities[key] = fragment_priority
                resolution = "chose_right"
            else:
                resolution = "chose_left"

        conflict = RegistryConflict(
            registry_kind=registry_kind,
            item_key=key,
            conflict_kind="duplicate_different",
            left_fragment_id=left_source,
            right_fragment_id=fragment_id,
            left_value_hash=left_hash,
            right_value_hash=right_hash,
            resolution=resolution,
            message="Conflicting registry item",
        )

        conflicts.append(conflict)
        if mode == "prefer_higher_priority":
            continue
    return base_items


def compose_registry_fragments(request: RegistryComposeRequest) -> RegistryComposeResult:
    fragments = _sorted_fragments(request.fragments)
    fragment_ids = {fragment.meta.fragment_id for fragment in fragments}

    conflicts: list[RegistryConflict] = []
    warnings: list[str] = []
    applied: list[str] = []

    for fragment in fragments:
        missing = [dep for dep in fragment.meta.depends_on if dep not in fragment_ids]
        if missing:
            conflicts.append(
                RegistryConflict(
                    registry_kind=fragment.kind,
                    item_key=fragment.meta.fragment_id,
                    conflict_kind="dependency_missing",
                    right_fragment_id=fragment.meta.fragment_id,
                    resolution="none",
                    message=f"Missing dependencies: {', '.join(sorted(missing))}",
                )
            )

    base = request.base_registries or RegistryBundle()
    composed = RegistryBundle(
        units=base.units,
        trust=base.trust,
        predicates=base.predicates,
        privacy=base.privacy,
        metrics=base.metrics,
        mechanisms=base.mechanisms,
        slots=base.slots,
        selector_fields=base.selector_fields,
        merge_rules=base.merge_rules,
        constraints=base.constraints,
        time=base.time,
        geo=base.geo,
        actors=base.actors,
        concepts=base.concepts,
        notes=list(base.notes),
    )

    registry_item_buckets: dict[str, dict[str, Any]] = {}
    registry_item_sources: dict[str, dict[str, str]] = {}
    registry_item_priorities: dict[str, dict[str, int]] = {}

    def _seed_base(kind: str, registry: Any) -> None:
        for registry_kind, key, value in _registry_items(registry, kind=kind):
            bucket = registry_item_buckets.setdefault(registry_kind, {})
            bucket[key] = value
            sources = registry_item_sources.setdefault(registry_kind, {})
            priorities = registry_item_priorities.setdefault(registry_kind, {})
            sources[key] = "base"
            priorities[key] = -1

    _seed_base("units", base.units)
    _seed_base("trust", base.trust)
    _seed_base("predicates", base.predicates)
    _seed_base("privacy", base.privacy)
    _seed_base("metrics", base.metrics)
    _seed_base("mechanisms", base.mechanisms)
    _seed_base("slots", base.slots)
    _seed_base("selector_fields", base.selector_fields)
    _seed_base("merge_rules", base.merge_rules)
    _seed_base("constraints", base.constraints)
    _seed_base("time", base.time)
    _seed_base("geo", base.geo)
    _seed_base("actors", base.actors)
    _seed_base("concepts", base.concepts)

    for fragment in fragments:
        applied.append(fragment.meta.fragment_id)
        items = _registry_items(fragment.payload, kind=fragment.kind)
        for registry_kind, key, value in items:
            bucket = registry_item_buckets.setdefault(registry_kind, {})
            sources = registry_item_sources.setdefault(registry_kind, {})
            priorities = registry_item_priorities.setdefault(registry_kind, {})
            bucket = _apply_fragment_items(
                base_items=bucket,
                base_sources=sources,
                base_priorities=priorities,
                fragment_meta=fragment.meta,
                items=[(registry_kind, key, value)],
                mode=request.policy.mode,
                conflicts=conflicts,
                reserved_prefixes=RESERVED_NAMESPACE_PREFIXES,
            )
            registry_item_buckets[registry_kind] = bucket

    blocking_conflicts = [
        conflict
        for conflict in conflicts
        if conflict.conflict_kind != "duplicate_identical"
    ]

    if blocking_conflicts and request.policy.mode == "error_on_conflict":
        return RegistryComposeResult(
            composed=None,
            conflicts=conflicts,
            warnings=warnings,
            applied_fragments=applied,
        )

    # Build composed registries from buckets
    if "units" in registry_item_buckets:
        composed = composed.model_copy(update={
            "units": UnitsRegistry(units=registry_item_buckets["units"], notes=list(composed.units.notes) if composed.units else []),
        })
    if "trust" in registry_item_buckets:
        composed = composed.model_copy(update={
            "trust": TrustRegistry(policies=registry_item_buckets["trust"], notes=list(composed.trust.notes) if composed.trust else []),
        })
    if "predicates.scalars" in registry_item_buckets or "predicates.edges" in registry_item_buckets:
        scalars = registry_item_buckets.get("predicates.scalars", {})
        edges = registry_item_buckets.get("predicates.edges", {})
        composed = composed.model_copy(update={
            "predicates": PredicateRegistry(scalars=scalars, edges=edges, notes=list(composed.predicates.notes) if composed.predicates else []),
        })
    if "privacy" in registry_item_buckets:
        composed = composed.model_copy(update={
            "privacy": PrivacyPolicyRegistry(policies=registry_item_buckets["privacy"], notes=list(composed.privacy.notes) if composed.privacy else []),
        })
    if "metrics" in registry_item_buckets:
        composed = composed.model_copy(update={
            "metrics": MetricRegistry(metrics=registry_item_buckets["metrics"], notes=list(composed.metrics.notes) if composed.metrics else []),
        })
    if "mechanisms" in registry_item_buckets:
        composed = composed.model_copy(update={
            "mechanisms": MechanismTypeRegistry(mechanisms=registry_item_buckets["mechanisms"], notes=list(composed.mechanisms.notes) if composed.mechanisms else []),
        })
    if "slots" in registry_item_buckets:
        composed = composed.model_copy(update={
            "slots": SlotRegistry(slots=registry_item_buckets["slots"], notes=list(composed.slots.notes) if composed.slots else []),
        })
    if "selector_fields" in registry_item_buckets:
        composed = composed.model_copy(update={
            "selector_fields": SelectorFieldRegistry(fields=registry_item_buckets["selector_fields"], notes=list(composed.selector_fields.notes) if composed.selector_fields else []),
        })
    if "merge_rules" in registry_item_buckets:
        composed = composed.model_copy(update={
            "merge_rules": MergeRuleRegistry(rules=registry_item_buckets["merge_rules"], notes=list(composed.merge_rules.notes) if composed.merge_rules else []),
        })
    if "constraints" in registry_item_buckets:
        composed = composed.model_copy(update={
            "constraints": ConstraintRegistry(constraints=registry_item_buckets["constraints"], notes=list(composed.constraints.notes) if composed.constraints else []),
        })
    if "time" in registry_item_buckets:
        composed = composed.model_copy(update={
            "time": TimeAxisRegistry(axes=registry_item_buckets["time"], notes=list(composed.time.notes) if composed.time else []),
        })
    if "geo" in registry_item_buckets:
        composed = composed.model_copy(update={
            "geo": GeoRegistry(areas=registry_item_buckets["geo"], notes=list(composed.geo.notes) if composed.geo else []),
        })
    if "actors" in registry_item_buckets:
        composed = composed.model_copy(update={
            "actors": ActorRegistry(actor_types=registry_item_buckets["actors"], notes=list(composed.actors.notes) if composed.actors else []),
        })
    if "concepts" in registry_item_buckets:
        composed = composed.model_copy(update={
            "concepts": ConceptRegistry(concepts=registry_item_buckets["concepts"], notes=list(composed.concepts.notes) if composed.concepts else []),
        })

    deterministic_hash = None
    if composed is not None:
        canonical = to_canonical_bytes(composed.model_dump(mode="json"))
        deterministic_hash = f"sha256:{hashlib.sha256(canonical).hexdigest()}"

    return RegistryComposeResult(
        composed=composed,
        conflicts=conflicts,
        warnings=warnings,
        applied_fragments=applied,
        deterministic_hash=deterministic_hash,
    )


__all__ = [
    "RegistryFragmentMeta",
    "RegistryFragment",
    "RegistryBundle",
    "RegistryComposeRequest",
    "RegistryComposeResult",
    "RegistryConflict",
    "ComposePolicy",
    "UnitsFragment",
    "TrustFragment",
    "PredicatesFragment",
    "PrivacyFragment",
    "MetricsFragment",
    "MechanismsFragment",
    "SlotsFragment",
    "SelectorFieldsFragment",
    "MergeRulesFragment",
    "ConstraintsFragment",
    "TimeFragment",
    "GeoFragment",
    "ActorsFragment",
    "ConceptsFragment",
    "TimeAxisRegistry",
    "GeoRegistry",
    "ActorRegistry",
    "ConceptRegistry",
    "compose_registry_fragments",
    "RESERVED_NAMESPACE_PREFIXES",
]
