"""Production REST/JSON connector for generic paginated REST APIs.

Wraps the reference GenericRESTConnector with production-grade metadata
and namespace. All REST-specific configuration is via ``X-REST-*`` headers
in the ConnectionConfig (see reference.rest_json docstring for details).

Supported REST APIs (via source profiles):
- USGS Earthquake Catalog
- NWS Weather Alerts
- OpenAQ Air Quality
- Open-Meteo Weather Forecast
- EIA Energy Data
- NVD Vulnerability Database
"""
from __future__ import annotations

from typing import Any, ClassVar

from polisyos.fabric.connectors.reference.rest_json import (
    GenericRESTConnector,
    PaginationStrategy,
)
from polisyos.ir.connectors import (
    ConnectorCapability,
    ConnectorMetadataSpec,
    QualityTier,
    TrustLevel,
    capabilities_from_flags,
)


class RestJsonConnector(GenericRESTConnector):
    """Generic production connector for paginated REST/JSON APIs.

    Used for sources that do not justify a dedicated connector class but still
    need Fabric pagination, incremental fetch, and rate-limit handling.

    Data source:
        Profile-defined REST endpoints
    Protocol:
        REST JSON
    Auth:
        Configurable per profile
    Async support:
        Standard async HTTP execution only
    Profile:
        Any ``connector_family='rest'`` profile
    """

    connector_id: ClassVar[str] = "rest.json"

    capabilities: ClassVar[ConnectorCapability] = (
        ConnectorCapability.FULL_FETCH
        | ConnectorCapability.DATE_RANGE_FILTER
        | ConnectorCapability.INCREMENTAL_FETCH
        | ConnectorCapability.RATE_LIMIT_AWARE
    )

    metadata: ClassVar[ConnectorMetadataSpec] = ConnectorMetadataSpec(
        connector_id="json",
        version="1.0.0",
        namespace="rest",
        source_name="REST JSON API",
        source_organization="Generic",
        trust_level=TrustLevel.MEDIUM,
        quality_tier=QualityTier.SILVER,
        capabilities=capabilities_from_flags(
            ConnectorCapability.FULL_FETCH,
            ConnectorCapability.DATE_RANGE_FILTER,
            ConnectorCapability.INCREMENTAL_FETCH,
            ConnectorCapability.RATE_LIMIT_AWARE,
        ),
    )

    namespace: ClassVar[str] = "rest"
    short_id: ClassVar[str] = "json"


__all__ = ["RestJsonConnector"]
