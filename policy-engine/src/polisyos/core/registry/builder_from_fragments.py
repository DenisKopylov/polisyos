from __future__ import annotations

from dataclasses import dataclass

from pydantic import TypeAdapter

from polisyos.core.artifacts.manifest import ArtifactRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.components import ComponentKind, ComponentRegistry, ResolvePolicy
from polisyos.core.components.compliance import HostAbi, validate_metadata
from polisyos.core.components.registry import ComponentEntry
from polisyos.core.registry.builder import build_registry_bundle
from polisyos.ir.kernel import (
    DEFAULT_CONSTRAINT_REGISTRY,
    DEFAULT_MECHANISM_REGISTRY,
    DEFAULT_MERGE_RULE_REGISTRY,
    DEFAULT_METRIC_REGISTRY,
    DEFAULT_SELECTOR_FIELD_REGISTRY,
    DEFAULT_SLOT_REGISTRY,
    DEFAULT_TRUST_REGISTRY,
    DEFAULT_UNITS_REGISTRY,
)
from polisyos.ir.registry_fragments import (
    ComposePolicy,
    RegistryBundle,
    RegistryComposeRequest,
    RegistryComposeResult,
    RegistryFragment,
    RegistryFragmentMeta,
    compose_registry_fragments,
)


@dataclass(frozen=True, slots=True)
class FragmentPrecedencePolicy:
    core_priority: int = 10
    pack_priority: int = 100
    dev_override_priority: int = 1000


def build_registry_bundle_from_components(
    store: FileSystemCAS,
    *,
    components_index: ComponentRegistry,
    domain: str,
    jurisdiction: str | None = None,
    base_bundle: RegistryBundle | None = None,
    precedence_policy: FragmentPrecedencePolicy | None = None,
    compose_policy: ComposePolicy | None = None,
    host_abi: HostAbi | None = None,
) -> tuple[ArtifactRef, ArtifactRef | None]:
    policy = precedence_policy or FragmentPrecedencePolicy()
    compose = compose_policy or ComposePolicy(mode="prefer_higher_priority")
    host = host_abi or HostAbi(versions={"ir_abi": "1.0"}, strict=True)

    entries = components_index.query(
        kind=ComponentKind.IR_FRAGMENT,
        domain=domain,
        jurisdiction=jurisdiction,
    )

    fragments: list[RegistryFragment] = []
    selected_components: list[str] = []

    for entry in entries:
        issues = validate_metadata(
            entry.metadata,
            host_abi=host,
            available_components=components_index,
            component=entry.component,
        )
        if any(issue.severity == "error" for issue in issues):
            continue

        try:
            created = entry.component.create()
            fragment = TypeAdapter(RegistryFragment).validate_python(created)
        except Exception:
            continue

        normalized = _normalize_fragment_meta(
            fragment=fragment,
            entry=entry,
            policy=policy,
            components_index=components_index,
        )
        fragments.append(normalized)
        selected_components.append(str(entry.metadata.component_id))

    request = RegistryComposeRequest(
        fragments=fragments,
        base_registries=base_bundle or _default_base_bundle(),
        policy=compose,
    )
    result = compose_registry_fragments(request)

    report_ref = _persist_compose_report(
        store=store,
        result=result,
        selected_components=selected_components,
        precedence_policy=policy,
    )

    if result.composed is None:
        raise ValueError("Failed to compose registry fragments; see compose report artifact")

    bundle = build_registry_bundle(
        store,
        slot_registry=result.composed.slots or DEFAULT_SLOT_REGISTRY,
        merge_registry=result.composed.merge_rules or DEFAULT_MERGE_RULE_REGISTRY,
        mechanism_registry=result.composed.mechanisms or DEFAULT_MECHANISM_REGISTRY,
        constraint_registry=result.composed.constraints or DEFAULT_CONSTRAINT_REGISTRY,
        selector_field_registry=result.composed.selector_fields or DEFAULT_SELECTOR_FIELD_REGISTRY,
        metric_registry=result.composed.metrics or DEFAULT_METRIC_REGISTRY,
        units_registry=result.composed.units or DEFAULT_UNITS_REGISTRY,
        trust_registry=result.composed.trust or DEFAULT_TRUST_REGISTRY,
        predicate_registry=result.composed.predicates,
        privacy_registry=result.composed.privacy,
    )

    return bundle.bundle_ref, report_ref


def _default_base_bundle() -> RegistryBundle:
    return RegistryBundle(
        units=DEFAULT_UNITS_REGISTRY,
        trust=DEFAULT_TRUST_REGISTRY,
        metrics=DEFAULT_METRIC_REGISTRY,
        mechanisms=DEFAULT_MECHANISM_REGISTRY,
        slots=DEFAULT_SLOT_REGISTRY,
        selector_fields=DEFAULT_SELECTOR_FIELD_REGISTRY,
        merge_rules=DEFAULT_MERGE_RULE_REGISTRY,
        constraints=DEFAULT_CONSTRAINT_REGISTRY,
    )


def _normalize_fragment_meta(
    *,
    fragment: RegistryFragment,
    entry: ComponentEntry,
    policy: FragmentPrecedencePolicy,
    components_index: ComponentRegistry,
) -> RegistryFragment:
    metadata = entry.metadata
    component_id = metadata.component_id

    fragment_id = f"{component_id.base_id}.{component_id.version_sanitized}"
    namespace = metadata.domains[0] if metadata.domains else component_id.base_id.split(".", 1)[0]

    priority = fragment.meta.priority
    if priority == 0:
        priority = _priority_for_entry(entry, policy=policy)

    depends_on: list[str] = []
    for dep in metadata.deps:
        if dep.kind not in {None, ComponentKind.IR_FRAGMENT}:
            continue
        resolved = components_index.resolve(
            dep.base_id,
            policy=ResolvePolicy.LATEST_COMPATIBLE,
            constraint=dep.version,
        )
        if resolved is None:
            continue
        dep_id = resolved.metadata.component_id
        depends_on.append(f"{dep_id.base_id}.{dep_id.version_sanitized}")

    normalized_meta = RegistryFragmentMeta(
        schema_version=fragment.meta.schema_version,
        fragment_id=fragment_id,
        namespace=namespace,
        priority=priority,
        depends_on=sorted(set(depends_on)),
        notes=list(fragment.meta.notes),
    )
    return fragment.model_copy(update={"meta": normalized_meta})


def _priority_for_entry(entry: ComponentEntry, *, policy: FragmentPrecedencePolicy) -> int:
    tags = set(entry.metadata.tags)
    source_type = str(getattr(entry.source, "source_type", ""))
    if source_type == "dev_scan":
        return policy.dev_override_priority
    if "core_fragment" in tags:
        return policy.core_priority
    return policy.pack_priority


def _persist_compose_report(
    *,
    store: FileSystemCAS,
    result: RegistryComposeResult,
    selected_components: list[str],
    precedence_policy: FragmentPrecedencePolicy,
) -> ArtifactRef:
    payload = result.model_dump(mode="python")
    payload["selected_components"] = sorted(set(selected_components))
    payload["precedence_policy"] = {
        "core_priority": precedence_policy.core_priority,
        "pack_priority": precedence_policy.pack_priority,
        "dev_override_priority": precedence_policy.dev_override_priority,
    }

    return store.put_json(
        payload,
        PutOptions(
            kind="core.registry_compose_report",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.RegistryComposeResult", version="1.0"),
        ),
    )


__all__ = [
    "FragmentPrecedencePolicy",
    "build_registry_bundle_from_components",
]
