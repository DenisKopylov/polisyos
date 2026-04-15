"""Validate component metadata and runtime shape against host ABI contracts."""
from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from polisyos.common.logger import get_logger

from .capabilities import Capability
from .ids import ComponentId, SemverRange
from .metadata import ComponentDep, ComponentKind, ComponentMetadata

if TYPE_CHECKING:
    from collections.abc import Iterable

    from .protocols import Component

logger = get_logger(__name__)

_COMPLIANCE_VALIDATION_ERRORS = (TypeError, ValueError, ValidationError)
_RUNTIME_SHAPE_ERRORS = (
    AttributeError,
    NotImplementedError,
    RuntimeError,
    TypeError,
    ValueError,
    ValidationError,
)


class HostAbi(BaseModel):
    """Describe host-supported ABI versions used to accept/reject components.

    Set `strict=False` to downgrade missing/incompatible host ABI findings from
    errors to warnings during local discovery or exploratory bootstrap.
    """
    model_config = ConfigDict(extra="forbid")

    versions: dict[str, str] = Field(default_factory=dict)
    strict: bool = True


class ComplianceIssue(BaseModel):
    """Report one metadata/dependency/runtime-shape compliance finding."""
    model_config = ConfigDict(extra="forbid")

    severity: Literal["error", "warning"]
    code: str
    message: str
    component_id: str
    details: dict[str, str | int | bool] = Field(default_factory=dict)


_KIND_CAPABILITY = {
    ComponentKind.IR_FRAGMENT: Capability.IR_FRAGMENT,
    ComponentKind.FOUNDRY_METHOD: Capability.FOUNDRY_METHOD,
    ComponentKind.FABRIC_CONNECTOR: Capability.FABRIC_CONNECTOR,
    ComponentKind.SCHOLAR_EXTRACTOR: Capability.SCHOLAR_EXTRACTOR,
    ComponentKind.LEX_EXTRACTOR: Capability.LEX_EXTRACTOR,
    ComponentKind.LEX_EVALUATOR: Capability.LEX_EVALUATOR,
    ComponentKind.SCIENTIST_NODE: Capability.SCIENTIST_NODE,
    ComponentKind.NORM_PACK_PROVIDER: Capability.NORM_PACK_PROVIDER,
}

_TYPE_CAPABILITIES = set(_KIND_CAPABILITY.values())

_REQUIRED_ABI_KEYS: dict[ComponentKind, tuple[tuple[str, ...], ...]] = {
    ComponentKind.IR_FRAGMENT: (("ir_abi",),),
    ComponentKind.SCHOLAR_EXTRACTOR: (("world_abi",),),
    ComponentKind.LEX_EXTRACTOR: (("world_abi",),),
    ComponentKind.FOUNDRY_METHOD: (("foundry_methods_api", "foundry_api"),),
    ComponentKind.FABRIC_CONNECTOR: (("fabric_connectors_api", "fabric_api"),),
    ComponentKind.LEX_EVALUATOR: (("ir_abi",), ("world_abi",)),
    ComponentKind.NORM_PACK_PROVIDER: (("ir_abi",), ("world_abi",)),
    ComponentKind.SCIENTIST_NODE: (),
}


def validate_component_id(value: str) -> ComponentId:
    """Parse and normalize a `ComponentId` boundary string.

    Raises:
        TypeError: If `value` is not a string.
        ValueError: If `value` does not match `seg(.seg)+@semver`.
    """
    return ComponentId.parse(value)


def validate_metadata(
    metadata: ComponentMetadata,
    *,
    host_abi: HostAbi | None = None,
    available_components: object | None = None,
    component: Component | None = None,
) -> list[ComplianceIssue]:
    """Validate a component before registration or bootstrap.

    Args:
        metadata: Declared component metadata to inspect.
        host_abi: Host ABI versions and strictness policy. Defaults to an empty
            strict host ABI, which turns missing host keys into errors.
        available_components: Optional registry-like object used to resolve
            declared dependencies.
        component: Optional runtime component instance used to validate
            `create()` output shape for governance-critical component kinds.

    Returns:
        A list of structured compliance issues; callers can use `has_errors()`
        to decide whether bootstrap must stop.
    """
    issues: list[ComplianceIssue] = []
    host = host_abi or HostAbi()
    component_id = str(metadata.component_id)

    try:
        _ = ComponentId.parse(component_id)
    except _COMPLIANCE_VALIDATION_ERRORS as exc:
        issues.append(
            ComplianceIssue(
                severity="error",
                code="component_id.invalid",
                message=f"Invalid component_id: {exc}",
                component_id=component_id,
            )
        )
        return issues

    if metadata.kind == ComponentKind.IR_FRAGMENT and "+" in metadata.component_id.version:
        issues.append(
            ComplianceIssue(
                severity="error",
                code="component_id.build_metadata_not_allowed",
                message="ir_fragment components must not use semver build metadata",
                component_id=component_id,
            )
        )

    if metadata.domains is None:
        issues.append(
            ComplianceIssue(
                severity="error",
                code="metadata.domains.missing",
                message="domains field is required",
                component_id=component_id,
            )
        )
    if metadata.jurisdictions is None:
        issues.append(
            ComplianceIssue(
                severity="error",
                code="metadata.jurisdictions.missing",
                message="jurisdictions field is required",
                component_id=component_id,
            )
        )
    if metadata.tags is None:
        issues.append(
            ComplianceIssue(
                severity="error",
                code="metadata.tags.missing",
                message="tags field is required",
                component_id=component_id,
            )
        )

    required_capability = _KIND_CAPABILITY[metadata.kind]
    if (metadata.capabilities & required_capability) != required_capability:
        issues.append(
            ComplianceIssue(
                severity="error",
                code="metadata.capabilities.kind_mismatch",
                message=(
                    f"kind={metadata.kind.value!r} requires capability={required_capability.name}"
                ),
                component_id=component_id,
            )
        )

    advertised_type_caps = [cap for cap in _TYPE_CAPABILITIES if cap in metadata.capabilities]
    unexpected_type_caps = [
        cap_name
        for cap in advertised_type_caps
        if cap != required_capability and (cap_name := cap.name) is not None
    ]
    if unexpected_type_caps:
        issues.append(
            ComplianceIssue(
                severity="warning",
                code="metadata.capabilities.extra_type_flags",
                message="component advertises multiple type capabilities",
                component_id=component_id,
                details={"flags": ",".join(sorted(unexpected_type_caps))},
            )
        )

    issues.extend(_validate_abi_targets(metadata=metadata, host=host))
    issues.extend(
        _validate_dependencies(
            metadata=metadata,
            host=host,
            available_components=available_components,
        )
    )
    issues.extend(_validate_runtime_shape(metadata=metadata, component=component))

    return issues


def has_errors(issues: Iterable[ComplianceIssue]) -> bool:
    """Return `True` when at least one compliance finding has `severity="error"`."""
    return any(issue.severity == "error" for issue in issues)


def _validate_abi_targets(*, metadata: ComponentMetadata, host: HostAbi) -> list[ComplianceIssue]:
    component_id = str(metadata.component_id)
    issues: list[ComplianceIssue] = []
    requirements = _REQUIRED_ABI_KEYS.get(metadata.kind, ())

    for alternatives in requirements:
        selected_key: str | None = None
        for key in alternatives:
            if key in metadata.abi_targets:
                selected_key = key
                break

        if selected_key is None:
            issues.append(
                ComplianceIssue(
                    severity="error",
                    code="abi.missing_key",
                    message=(
                        "missing required abi target key: "
                        + " | ".join(sorted(alternatives))
                    ),
                    component_id=component_id,
                )
            )
            continue

        range_raw = metadata.abi_targets[selected_key]
        try:
            version_range = SemverRange.parse(range_raw)
        except _COMPLIANCE_VALIDATION_ERRORS as exc:
            issues.append(
                ComplianceIssue(
                    severity="error",
                    code="abi.invalid_range",
                    message=f"invalid abi range for {selected_key}: {exc}",
                    component_id=component_id,
                )
            )
            continue

        host_version = host.versions.get(selected_key)
        if host_version is None:
            issues.append(
                ComplianceIssue(
                    severity="error" if host.strict else "warning",
                    code="abi.host_missing",
                    message=f"host ABI version missing for key={selected_key}",
                    component_id=component_id,
                    details={"key": selected_key},
                )
            )
            continue

        normalized_host_version = _normalize_abi_version(host_version)
        if not version_range.matches(normalized_host_version):
            issues.append(
                ComplianceIssue(
                    severity="error" if host.strict else "warning",
                    code="abi.incompatible",
                    message=(
                        f"host ABI {selected_key}={host_version} does not satisfy {range_raw}"
                    ),
                    component_id=component_id,
                    details={
                        "key": selected_key,
                        "host_version": host_version,
                        "required": range_raw,
                    },
                )
            )

    for key, range_raw in sorted(metadata.abi_targets.items()):
        if key in {k for req in requirements for k in req}:
            continue
        try:
            version_range = SemverRange.parse(range_raw)
        except _COMPLIANCE_VALIDATION_ERRORS as exc:
            issues.append(
                ComplianceIssue(
                    severity="error",
                    code="abi.invalid_range",
                    message=f"invalid abi range for {key}: {exc}",
                    component_id=component_id,
                )
            )
            continue
        host_version = host.versions.get(key)
        if host_version is None:
            continue
        normalized_host_version = _normalize_abi_version(host_version)
        if not version_range.matches(normalized_host_version):
            issues.append(
                ComplianceIssue(
                    severity="error" if host.strict else "warning",
                    code="abi.optional_incompatible",
                    message=f"optional ABI key {key} incompatible with host",
                    component_id=component_id,
                    details={
                        "key": key,
                        "host_version": host_version,
                        "required": range_raw,
                    },
                )
            )

    return issues


def _normalize_abi_version(value: str) -> str:
    raw = value.strip()
    if raw.count(".") == 1 and raw.replace(".", "").isdigit():
        return f"{raw}.0"
    return raw


def _validate_dependencies(
    *,
    metadata: ComponentMetadata,
    host: HostAbi,
    available_components: object | None,
) -> list[ComplianceIssue]:
    if not metadata.deps:
        return []

    component_id = str(metadata.component_id)
    issues: list[ComplianceIssue] = []

    if available_components is None:
        issues.append(
            ComplianceIssue(
                severity="warning",
                code="deps.unchecked",
                message="dependency validation skipped (no available component index)",
                component_id=component_id,
            )
        )
        return issues

    for dep in metadata.deps:
        if not _dependency_satisfied(dep=dep, available_components=available_components):
            issues.append(
                ComplianceIssue(
                    severity="error" if host.strict else "warning",
                    code="deps.unsatisfied",
                    message=(
                        f"No component satisfies dep base_id={dep.base_id}"
                        f" range={dep.version}"
                    ),
                    component_id=component_id,
                    details={
                        "dep_base_id": dep.base_id,
                        "dep_version": dep.version,
                        "dep_kind": dep.kind.value if dep.kind else "any",
                    },
                )
            )

    return issues


def _dependency_satisfied(*, dep: ComponentDep, available_components: object) -> bool:
    matches = []

    matching_entries = getattr(available_components, "matching_entries", None)
    if callable(matching_entries):
        try:
            matches = list(matching_entries(dep.base_id, constraint=dep.version, kind=dep.kind))
        except (AttributeError, TypeError, ValueError) as exc:
            logger.warning(
                "Component dependency lookup failed for %s via matching_entries: %s",
                dep.base_id,
                exc,
            )
        return len(matches) > 0

    list_entries = getattr(available_components, "list", None)
    if callable(list_entries):
        try:
            entries = list_entries(dep.base_id)
        except (AttributeError, TypeError, ValueError) as exc:
            logger.warning(
                "Component dependency lookup failed for %s via list: %s",
                dep.base_id,
                exc,
            )
            entries = []
        dep_range = SemverRange.parse(dep.version)
        for entry in entries:
            meta = getattr(entry, "metadata", entry)
            try:
                if dep.kind is not None and getattr(meta, "kind", None) != dep.kind:
                    continue
                version = str(meta.component_id.version)
                if dep_range.matches(version):
                    return True
            except (AttributeError, TypeError, ValueError) as exc:
                logger.warning(
                    "Component dependency candidate was skipped for %s: %s",
                    dep.base_id,
                    exc,
                )
                continue

    return False


def _validate_runtime_shape(
    *,
    metadata: ComponentMetadata,
    component: Component | None,
) -> list[ComplianceIssue]:
    if component is None:
        return []

    component_id = str(metadata.component_id)
    issues: list[ComplianceIssue] = []

    try:
        created = component.create()
    except _RUNTIME_SHAPE_ERRORS as exc:
        return [
            ComplianceIssue(
                severity="error",
                code="runtime_shape.create_failed",
                message=f"component.create() failed: {exc}",
                component_id=component_id,
            )
        ]

    if metadata.kind == ComponentKind.IR_FRAGMENT:
        from pydantic import TypeAdapter

        from polisyos.ir.registry_fragments import RegistryFragment

        try:
            TypeAdapter(RegistryFragment).validate_python(created)
        except ValidationError as exc:
            issues.append(
                ComplianceIssue(
                    severity="error",
                    code="runtime_shape.ir_fragment.invalid",
                    message="ir_fragment component must create RegistryFragment",
                    component_id=component_id,
                    details={"error": str(exc)},
                )
            )

    return issues
