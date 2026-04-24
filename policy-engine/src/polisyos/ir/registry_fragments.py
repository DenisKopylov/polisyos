"""Public IR registry fragments module API."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Any, Literal

from pydantic import Field

from polisyos.ir.canon import content_hash, to_canonical_bytes
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

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from polisyos.ir.public_surface import RegistryItemId
else:
    from polisyos.ir.public_surface import RegistryItemId

SCHEMA_VERSION_PATTERN = r"^\d+\.\d+$"

RESERVED_NAMESPACE_PREFIXES: tuple[str, ...] = ("core.", "world.")


class RegistryFragmentMeta(KernelModel):
    """Registry fragment meta public type."""

    schema_version: str = Field("1.0", pattern=SCHEMA_VERSION_PATTERN)
    fragment_id: str = Field(..., pattern=ID_PATTERN)
    namespace: str = Field(..., pattern=ID_PATTERN)
    priority: int = Field(0)
    depends_on: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class TimeAxisSpec(KernelModel):
    """Time axis spec data model."""

    axis_id: str = Field(..., pattern=ID_PATTERN)
    description: str | None = None
    notes: list[str] = Field(default_factory=list)


class TimeAxisRegistry(KernelModel):
    """Time axis registry implementation."""

    schema_version: str = Field("1.0", pattern=SCHEMA_VERSION_PATTERN)
    axes: dict[str, TimeAxisSpec] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)


class GeoAreaSpec(KernelModel):
    """Geo area spec data model."""

    geo_id: str = Field(..., pattern=ID_PATTERN)
    name: str | None = None
    kind: str | None = None
    notes: list[str] = Field(default_factory=list)


class GeoRegistry(KernelModel):
    """Geo registry implementation."""

    schema_version: str = Field("1.0", pattern=SCHEMA_VERSION_PATTERN)
    areas: dict[str, GeoAreaSpec] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)


class ActorTypeSpec(KernelModel):
    """Actor type spec data model."""

    actor_type_id: str = Field(..., pattern=ID_PATTERN)
    name: str | None = None
    description: str | None = None
    notes: list[str] = Field(default_factory=list)


class ActorRegistry(KernelModel):
    """Actor registry implementation."""

    schema_version: str = Field("1.0", pattern=SCHEMA_VERSION_PATTERN)
    actor_types: dict[str, ActorTypeSpec] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)


class ConceptSpec(KernelModel):
    """Concept spec data model."""

    concept_id: str = Field(..., pattern=ID_PATTERN)
    name: str | None = None
    description: str | None = None
    notes: list[str] = Field(default_factory=list)


class ConceptRegistry(KernelModel):
    """Concept registry implementation."""

    schema_version: str = Field("1.0", pattern=SCHEMA_VERSION_PATTERN)
    concepts: dict[str, ConceptSpec] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)


class RegistryBundle(KernelModel):
    """Registry bundle data model."""

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
    """Units fragment public type."""

    kind: Literal["units"] = "units"
    meta: RegistryFragmentMeta
    payload: UnitsRegistry


class TrustFragment(KernelModel):
    """Trust fragment public type."""

    kind: Literal["trust"] = "trust"
    meta: RegistryFragmentMeta
    payload: TrustRegistry


class PredicatesFragment(KernelModel):
    """Predicates fragment public type."""

    kind: Literal["predicates"] = "predicates"
    meta: RegistryFragmentMeta
    payload: PredicateRegistry


class PrivacyFragment(KernelModel):
    """Privacy fragment public type."""

    kind: Literal["privacy"] = "privacy"
    meta: RegistryFragmentMeta
    payload: PrivacyPolicyRegistry


class MetricsFragment(KernelModel):
    """Metrics fragment public type."""

    kind: Literal["metrics"] = "metrics"
    meta: RegistryFragmentMeta
    payload: MetricRegistry


class MechanismsFragment(KernelModel):
    """Mechanisms fragment public type."""

    kind: Literal["mechanisms"] = "mechanisms"
    meta: RegistryFragmentMeta
    payload: MechanismTypeRegistry


class SlotsFragment(KernelModel):
    """Slots fragment public type."""

    kind: Literal["slots"] = "slots"
    meta: RegistryFragmentMeta
    payload: SlotRegistry


class SelectorFieldsFragment(KernelModel):
    """Selector fields fragment public type."""

    kind: Literal["selector_fields"] = "selector_fields"
    meta: RegistryFragmentMeta
    payload: SelectorFieldRegistry


class MergeRulesFragment(KernelModel):
    """Merge rules fragment public type."""

    kind: Literal["merge_rules"] = "merge_rules"
    meta: RegistryFragmentMeta
    payload: MergeRuleRegistry


class ConstraintsFragment(KernelModel):
    """Constraints fragment public type."""

    kind: Literal["constraints"] = "constraints"
    meta: RegistryFragmentMeta
    payload: ConstraintRegistry


class TimeFragment(KernelModel):
    """Time fragment public type."""

    kind: Literal["time"] = "time"
    meta: RegistryFragmentMeta
    payload: TimeAxisRegistry


class GeoFragment(KernelModel):
    """Geo fragment public type."""

    kind: Literal["geo"] = "geo"
    meta: RegistryFragmentMeta
    payload: GeoRegistry


class ActorsFragment(KernelModel):
    """Actors fragment public type."""

    kind: Literal["actors"] = "actors"
    meta: RegistryFragmentMeta
    payload: ActorRegistry


class ConceptsFragment(KernelModel):
    """Concepts fragment public type."""

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
    """Compose policy data model."""

    mode: Literal["error_on_conflict", "prefer_higher_priority"] = "error_on_conflict"


class RegistryComposeRequest(KernelModel):
    """Registry compose request data model."""

    schema_version: str = Field("1.0", pattern=SCHEMA_VERSION_PATTERN)
    fragments: list[RegistryFragment]
    base_registries: RegistryBundle | None = None
    policy: ComposePolicy = Field(default_factory=ComposePolicy)


class RegistryConflict(KernelModel):
    """Registry conflict public type."""

    registry_kind: str
    item_key: RegistryItemId
    conflict_kind: Literal[
        "duplicate_identical",
        "duplicate_different",
        "invalid_item",
        "reserved_prefix",
        "dependency_missing",
        "dependency_cycle",
        "dependency_unresolved",
    ]
    left_fragment_id: str | None = None
    right_fragment_id: str | None = None
    left_value_hash: str | None = None
    right_value_hash: str | None = None
    resolution: Literal["none", "chose_left", "chose_right", "merged"] = "none"
    message: str | None = None


class RegistryComposeResult(KernelModel):
    """Registry compose result data model."""

    schema_version: str = Field("1.0", pattern=SCHEMA_VERSION_PATTERN)
    composed: RegistryBundle | None = None
    conflicts: list[RegistryConflict] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    applied_fragments: list[str] = Field(default_factory=list)
    deterministic_hash: str | None = None


def _hash_item(value: Any) -> str:
    canonical = to_canonical_bytes(value)
    return content_hash(canonical, prefix=True)


def _sorted_fragments(fragments: Sequence[RegistryFragment]) -> list[RegistryFragment]:
    return sorted(
        fragments,
        key=lambda frag: (-frag.meta.priority, frag.meta.fragment_id),
    )


def _append_unique_message(
    warnings: list[str],
    seen: set[str],
    message: str,
) -> None:
    if message in seen:
        return
    seen.add(message)
    warnings.append(message)


def _topological_sort_fragments(
    fragments: Sequence[RegistryFragment],
) -> tuple[list[RegistryFragment], dict[str, list[str]]]:
    fragments_by_id = {
        fragment.meta.fragment_id: fragment for fragment in _sorted_fragments(fragments)
    }
    dependency_map = {
        fragment_id: [
            dep for dep in dict.fromkeys(fragment.meta.depends_on) if dep in fragments_by_id
        ]
        for fragment_id, fragment in fragments_by_id.items()
    }
    reverse_dependencies: dict[str, list[str]] = {
        fragment_id: [] for fragment_id in fragments_by_id
    }
    for fragment_id, dependencies in dependency_map.items():
        for dependency in dependencies:
            reverse_dependencies.setdefault(dependency, []).append(fragment_id)

    indegree = {
        fragment_id: len(dependencies) for fragment_id, dependencies in dependency_map.items()
    }
    ready = [
        fragments_by_id[fragment_id] for fragment_id, degree in indegree.items() if degree == 0
    ]
    ready = _sorted_fragments(ready)
    ordered: list[RegistryFragment] = []

    while ready:
        fragment = ready.pop(0)
        ordered.append(fragment)
        fragment_id = fragment.meta.fragment_id
        for dependent_id in sorted(reverse_dependencies.get(fragment_id, [])):
            indegree[dependent_id] -= 1
            if indegree[dependent_id] == 0:
                ready.append(fragments_by_id[dependent_id])
        ready = _sorted_fragments(ready)

    return ordered, dependency_map


def _strongly_connected_components(
    node_ids: set[str],
    dependency_map: dict[str, list[str]],
) -> list[list[str]]:
    index = 0
    indices: dict[str, int] = {}
    lowlinks: dict[str, int] = {}
    stack: list[str] = []
    on_stack: set[str] = set()
    components: list[list[str]] = []

    def _visit(node_id: str) -> None:
        nonlocal index
        indices[node_id] = index
        lowlinks[node_id] = index
        index += 1
        stack.append(node_id)
        on_stack.add(node_id)

        for dependency in sorted(dep for dep in dependency_map.get(node_id, []) if dep in node_ids):
            if dependency not in indices:
                _visit(dependency)
                lowlinks[node_id] = min(lowlinks[node_id], lowlinks[dependency])
            elif dependency in on_stack:
                lowlinks[node_id] = min(lowlinks[node_id], indices[dependency])

        if lowlinks[node_id] != indices[node_id]:
            return

        component: list[str] = []
        while stack:
            candidate = stack.pop()
            on_stack.remove(candidate)
            component.append(candidate)
            if candidate == node_id:
                break
        components.append(sorted(component))

    for node_id in sorted(node_ids):
        if node_id not in indices:
            _visit(node_id)

    return components


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


def _build_composed_bundle(
    *,
    base: RegistryBundle,
    registry_item_buckets: dict[str, dict[str, Any]],
) -> RegistryBundle:
    predicates = base.predicates
    if "predicates.scalars" in registry_item_buckets or "predicates.edges" in registry_item_buckets:
        predicates = PredicateRegistry(
            scalars=registry_item_buckets.get("predicates.scalars", {}),
            edges=registry_item_buckets.get("predicates.edges", {}),
            notes=list(base.predicates.notes) if base.predicates else [],
        )

    return RegistryBundle(
        schema_version=base.schema_version,
        units=_apply_items_to_registry(
            base.units,
            kind="units",
            items=registry_item_buckets["units"],
        )
        if "units" in registry_item_buckets
        else base.units,
        trust=_apply_items_to_registry(
            base.trust,
            kind="trust",
            items=registry_item_buckets["trust"],
        )
        if "trust" in registry_item_buckets
        else base.trust,
        predicates=predicates,
        privacy=_apply_items_to_registry(
            base.privacy,
            kind="privacy",
            items=registry_item_buckets["privacy"],
        )
        if "privacy" in registry_item_buckets
        else base.privacy,
        metrics=_apply_items_to_registry(
            base.metrics,
            kind="metrics",
            items=registry_item_buckets["metrics"],
        )
        if "metrics" in registry_item_buckets
        else base.metrics,
        mechanisms=_apply_items_to_registry(
            base.mechanisms,
            kind="mechanisms",
            items=registry_item_buckets["mechanisms"],
        )
        if "mechanisms" in registry_item_buckets
        else base.mechanisms,
        slots=_apply_items_to_registry(
            base.slots,
            kind="slots",
            items=registry_item_buckets["slots"],
        )
        if "slots" in registry_item_buckets
        else base.slots,
        selector_fields=_apply_items_to_registry(
            base.selector_fields,
            kind="selector_fields",
            items=registry_item_buckets["selector_fields"],
        )
        if "selector_fields" in registry_item_buckets
        else base.selector_fields,
        merge_rules=_apply_items_to_registry(
            base.merge_rules,
            kind="merge_rules",
            items=registry_item_buckets["merge_rules"],
        )
        if "merge_rules" in registry_item_buckets
        else base.merge_rules,
        constraints=_apply_items_to_registry(
            base.constraints,
            kind="constraints",
            items=registry_item_buckets["constraints"],
        )
        if "constraints" in registry_item_buckets
        else base.constraints,
        time=_apply_items_to_registry(
            base.time,
            kind="time",
            items=registry_item_buckets["time"],
        )
        if "time" in registry_item_buckets
        else base.time,
        geo=_apply_items_to_registry(
            base.geo,
            kind="geo",
            items=registry_item_buckets["geo"],
        )
        if "geo" in registry_item_buckets
        else base.geo,
        actors=_apply_items_to_registry(
            base.actors,
            kind="actors",
            items=registry_item_buckets["actors"],
        )
        if "actors" in registry_item_buckets
        else base.actors,
        concepts=_apply_items_to_registry(
            base.concepts,
            kind="concepts",
            items=registry_item_buckets["concepts"],
        )
        if "concepts" in registry_item_buckets
        else base.concepts,
        notes=list(base.notes),
    )


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
        if (
            any(key.startswith(prefix) for prefix in reserved_prefixes)
            and not is_reserved_namespace
        ):
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
    """Compose registry fragments helper."""
    fragments = _sorted_fragments(request.fragments)
    fragments_by_id = {fragment.meta.fragment_id: fragment for fragment in fragments}
    fragment_ids = set(fragments_by_id)

    conflicts: list[RegistryConflict] = []
    warnings: list[str] = []
    warning_set: set[str] = set()
    applied: list[str] = []

    blocked_missing: dict[str, list[str]] = {}
    for fragment in fragments:
        missing = [dep for dep in fragment.meta.depends_on if dep not in fragment_ids]
        if missing:
            blocked_missing[fragment.meta.fragment_id] = sorted(dict.fromkeys(missing))
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
            _append_unique_message(
                warnings,
                warning_set,
                f"fragment_skipped:{fragment.meta.fragment_id}:dependency_missing",
            )

    dependency_map = {
        fragment_id: [
            dep for dep in dict.fromkeys(fragment.meta.depends_on) if dep in fragments_by_id
        ]
        for fragment_id, fragment in fragments_by_id.items()
    }

    blocked_unresolved_from_missing: dict[str, list[str]] = {}
    changed = True
    while changed:
        changed = False
        invalid_ids = set(blocked_missing) | set(blocked_unresolved_from_missing)
        for fragment in fragments:
            fragment_id = fragment.meta.fragment_id
            if fragment_id in invalid_ids:
                continue
            bad_deps = sorted(dep for dep in dependency_map[fragment_id] if dep in invalid_ids)
            if not bad_deps:
                continue
            blocked_unresolved_from_missing[fragment_id] = bad_deps
            changed = True

    eligible_ids = fragment_ids - set(blocked_missing) - set(blocked_unresolved_from_missing)
    eligible_fragments = [fragments_by_id[fragment_id] for fragment_id in eligible_ids]
    ordered_fragments, _ = _topological_sort_fragments(eligible_fragments)
    ordered_ids = {fragment.meta.fragment_id for fragment in ordered_fragments}
    unresolved_cycle_candidates = eligible_ids - ordered_ids
    blocked_cycle: dict[str, list[str]] = {}
    if unresolved_cycle_candidates:
        for component in _strongly_connected_components(
            unresolved_cycle_candidates,
            dependency_map,
        ):
            is_self_cycle = len(component) == 1 and component[0] in dependency_map.get(
                component[0], []
            )
            if len(component) == 1 and not is_self_cycle:
                continue
            for fragment_id in component:
                blocked_cycle[fragment_id] = component
                conflicts.append(
                    RegistryConflict(
                        registry_kind=fragments_by_id[fragment_id].kind,
                        item_key=fragment_id,
                        conflict_kind="dependency_cycle",
                        right_fragment_id=fragment_id,
                        resolution="none",
                        message=f"Dependency cycle detected: {', '.join(component)}",
                    )
                )
                _append_unique_message(
                    warnings,
                    warning_set,
                    f"fragment_skipped:{fragment_id}:dependency_cycle",
                )

    blocked_unresolved_from_cycle: dict[str, list[str]] = {}
    changed = True
    while changed:
        changed = False
        invalid_ids = (
            set(blocked_missing)
            | set(blocked_unresolved_from_missing)
            | set(blocked_cycle)
            | set(blocked_unresolved_from_cycle)
        )
        for fragment in fragments:
            fragment_id = fragment.meta.fragment_id
            if fragment_id in invalid_ids:
                continue
            bad_deps = sorted(dep for dep in dependency_map[fragment_id] if dep in invalid_ids)
            if not bad_deps:
                continue
            blocked_unresolved_from_cycle[fragment_id] = bad_deps
            changed = True

    for fragment_id, dependencies in sorted(blocked_unresolved_from_missing.items()):
        conflicts.append(
            RegistryConflict(
                registry_kind=fragments_by_id[fragment_id].kind,
                item_key=fragment_id,
                conflict_kind="dependency_unresolved",
                right_fragment_id=fragment_id,
                resolution="none",
                message=f"Unresolved dependencies: {', '.join(dependencies)}",
            )
        )
        _append_unique_message(
            warnings,
            warning_set,
            f"fragment_skipped:{fragment_id}:dependency_unresolved",
        )
    for fragment_id, dependencies in sorted(blocked_unresolved_from_cycle.items()):
        conflicts.append(
            RegistryConflict(
                registry_kind=fragments_by_id[fragment_id].kind,
                item_key=fragment_id,
                conflict_kind="dependency_unresolved",
                right_fragment_id=fragment_id,
                resolution="none",
                message=f"Unresolved dependencies: {', '.join(dependencies)}",
            )
        )
        _append_unique_message(
            warnings,
            warning_set,
            f"fragment_skipped:{fragment_id}:dependency_unresolved",
        )

    base = request.base_registries or RegistryBundle()

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

    for fragment in ordered_fragments:
        applied.append(fragment.meta.fragment_id)
        items = _registry_items(fragment.payload, kind=fragment.kind)
        items_by_registry: dict[str, list[tuple[str, str, Any]]] = {}
        for registry_kind, key, value in items:
            items_by_registry.setdefault(registry_kind, []).append((registry_kind, key, value))
        for registry_kind in sorted(items_by_registry):
            bucket = registry_item_buckets.setdefault(registry_kind, {})
            sources = registry_item_sources.setdefault(registry_kind, {})
            priorities = registry_item_priorities.setdefault(registry_kind, {})
            bucket = _apply_fragment_items(
                base_items=bucket,
                base_sources=sources,
                base_priorities=priorities,
                fragment_meta=fragment.meta,
                items=items_by_registry[registry_kind],
                mode=request.policy.mode,
                conflicts=conflicts,
                reserved_prefixes=RESERVED_NAMESPACE_PREFIXES,
            )
            registry_item_buckets[registry_kind] = bucket

    blocking_conflicts = [
        conflict for conflict in conflicts if conflict.conflict_kind != "duplicate_identical"
    ]

    if blocking_conflicts and request.policy.mode == "error_on_conflict":
        return RegistryComposeResult(
            composed=None,
            conflicts=conflicts,
            warnings=warnings,
            applied_fragments=applied,
        )

    composed = _build_composed_bundle(
        base=base,
        registry_item_buckets=registry_item_buckets,
    )

    deterministic_hash = None
    if composed is not None:
        canonical = to_canonical_bytes(composed.model_dump(mode="json"))
        deterministic_hash = content_hash(canonical, prefix=True)

    return RegistryComposeResult(
        composed=composed,
        conflicts=conflicts,
        warnings=warnings,
        applied_fragments=applied,
        deterministic_hash=deterministic_hash,
    )


__all__ = [
    "RESERVED_NAMESPACE_PREFIXES",
    "ActorRegistry",
    "ActorsFragment",
    "ComposePolicy",
    "ConceptRegistry",
    "ConceptsFragment",
    "ConstraintsFragment",
    "GeoFragment",
    "GeoRegistry",
    "MechanismsFragment",
    "MergeRulesFragment",
    "MetricsFragment",
    "PredicatesFragment",
    "PrivacyFragment",
    "RegistryBundle",
    "RegistryComposeRequest",
    "RegistryComposeResult",
    "RegistryConflict",
    "RegistryFragment",
    "RegistryFragmentMeta",
    "SelectorFieldsFragment",
    "SlotsFragment",
    "TimeAxisRegistry",
    "TimeFragment",
    "TrustFragment",
    "UnitsFragment",
    "compose_registry_fragments",
]
