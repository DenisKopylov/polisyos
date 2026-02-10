from __future__ import annotations

from polisyos.core.components import (
    Capability,
    ComponentId,
    ComponentKind,
    ComponentMetadata,
    HostAbi,
    has_errors,
    validate_metadata,
)


def _connector_metadata(*, capabilities: Capability, abi_targets: dict[str, str]) -> ComponentMetadata:
    return ComponentMetadata(
        component_id=ComponentId.parse("test.fabric.connector@1.0.0"),
        kind=ComponentKind.FABRIC_CONNECTOR,
        abi_targets=abi_targets,
        domains=[],
        jurisdictions=[],
        tags=["test"],
        capabilities=capabilities,
        deps=[],
    )


def test_fabric_connector_kind_requires_matching_capability() -> None:
    metadata = _connector_metadata(
        capabilities=Capability.FABRIC_QUERY,
        abi_targets={"fabric_connectors_api": ">=2.2.0,<3.0.0"},
    )

    issues = validate_metadata(metadata)

    assert any(issue.code == "metadata.capabilities.kind_mismatch" for issue in issues)
    assert has_errors(issues)


def test_fabric_connector_compliance_with_fabric_connectors_api() -> None:
    metadata = _connector_metadata(
        capabilities=Capability.FABRIC_CONNECTOR | Capability.FABRIC_QUERY,
        abi_targets={"fabric_connectors_api": ">=2.2.0,<3.0.0"},
    )

    issues = validate_metadata(
        metadata,
        host_abi=HostAbi(versions={"fabric_connectors_api": "2.2.0"}, strict=True),
    )

    assert not has_errors(issues)


def test_fabric_connector_compliance_allows_fabric_api_alias() -> None:
    metadata = _connector_metadata(
        capabilities=Capability.FABRIC_CONNECTOR,
        abi_targets={"fabric_api": ">=2.2.0,<3.0.0"},
    )

    issues = validate_metadata(
        metadata,
        host_abi=HostAbi(versions={"fabric_api": "2.2.0"}, strict=True),
    )

    assert not has_errors(issues)
