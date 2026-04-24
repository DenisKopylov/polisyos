"""Built-in production connector families exposed by the Fabric package.

The exports in this module are concrete connector implementations plus the shared HTTP runtime.
Each connector advertises hard capabilities through ``ConnectorCapability`` and typically relies
on ``SourceProfile`` / ``SourceExecutionPolicy`` for endpoint-specific transport, auth, and
throttling semantics.
"""

from __future__ import annotations

from polisyos.fabric.connectors.sources.ckan_catalog import CKANCatalogConnector
from polisyos.fabric.connectors.sources.ckan_resource import CKANResourceConnector
from polisyos.fabric.connectors.sources.eurostat import EurostatConnector
from polisyos.fabric.connectors.sources.event_stream import EventStreamConnector
from polisyos.fabric.connectors.sources.file_tabular import FileTabularConnector
from polisyos.fabric.connectors.sources.geojson import GeoJSONConnector
from polisyos.fabric.connectors.sources.graphql_api import GraphQLConnector
from polisyos.fabric.connectors.sources.http_base import HTTPConnectorBase, HTTPResilienceProfile
from polisyos.fabric.connectors.sources.object_storage import ObjectStorageConnector
from polisyos.fabric.connectors.sources.opendatasoft import OpendatasoftConnector
from polisyos.fabric.connectors.sources.rest_json import RestJsonConnector
from polisyos.fabric.connectors.sources.sdmx_source import SDMXSourceConnector
from polisyos.fabric.connectors.sources.socrata import SocrataConnector
from polisyos.fabric.connectors.sources.sparql import SPARQLConnector
from polisyos.fabric.connectors.sources.sql_query import SQLQueryConnector
from polisyos.fabric.connectors.sources.ukons import UKONSConnector
from polisyos.fabric.connectors.sources.unesco_uis import UNESCOUISConnector
from polisyos.fabric.connectors.sources.unpd import UNPDConnector
from polisyos.fabric.connectors.sources.who import WHOConnector
from polisyos.fabric.connectors.sources.world_bank import WorldBankConnector
from polisyos.fabric.connectors.sources.wvs import WVSConnector

__all__ = [
    "CKANCatalogConnector",
    "CKANResourceConnector",
    "EurostatConnector",
    "EventStreamConnector",
    "FileTabularConnector",
    "GeoJSONConnector",
    "GraphQLConnector",
    "HTTPConnectorBase",
    "HTTPResilienceProfile",
    "ObjectStorageConnector",
    "OpendatasoftConnector",
    "RestJsonConnector",
    "SDMXSourceConnector",
    "SPARQLConnector",
    "SQLQueryConnector",
    "SocrataConnector",
    "UKONSConnector",
    "UNESCOUISConnector",
    "UNPDConnector",
    "WHOConnector",
    "WVSConnector",
    "WorldBankConnector",
]
