"""Local dev-scan declaration for the example Fabric connector."""

from .connector import local_rows_connector_component

__polisyos_components__ = [local_rows_connector_component]

__all__ = ["__polisyos_components__"]
