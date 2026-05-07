"""Local dev-scan declaration for the example Runtime middleware."""

from .middleware import response_header_middleware_component

__polisyos_components__ = [response_header_middleware_component]

__all__ = ["__polisyos_components__"]
