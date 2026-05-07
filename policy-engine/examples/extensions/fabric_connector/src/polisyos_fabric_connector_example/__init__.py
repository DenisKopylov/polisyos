"""Minimal external Fabric connector extension."""

from .connector import ExampleRowsConnector, local_rows_connector_component

__all__ = ["ExampleRowsConnector", "local_rows_connector_component"]
