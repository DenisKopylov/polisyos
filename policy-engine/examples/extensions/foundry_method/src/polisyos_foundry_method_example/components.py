"""Local dev-scan declaration for the example Foundry method."""

from .methods import weighted_average_plugin

__polisyos_components__ = [weighted_average_plugin]

__all__ = ["__polisyos_components__"]
