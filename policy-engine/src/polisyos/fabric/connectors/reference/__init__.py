"""
Phase 2.11 - Reference Connector Implementations.

This package ships three reference connectors that validate the Fabric
architecture end-to-end and serve as templates for new connector authors.

Discovery
---------
ConnectorDiscovery scans this package and uses __all__ to select the
reference connector classes for built-in registration.
"""

from polisyos.fabric.connectors.reference.rest_json import GenericRESTConnector
from polisyos.fabric.connectors.reference.sdmx import SDMXConnector
from polisyos.fabric.connectors.reference.static_csv import StaticCSVConnector

__all__ = [
    "GenericRESTConnector",
    "SDMXConnector",
    "StaticCSVConnector",
]
