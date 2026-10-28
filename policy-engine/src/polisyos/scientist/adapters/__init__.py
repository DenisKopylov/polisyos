"""Stable adapter facade for default Foundry and Fabric runtime ports.

The package exports the production bridge classes used by workflow builders.
Both bridges are imported lazily so environments that only need Scientist state
or workflow specs do not pay the import cost of connector/security stacks.
"""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .fabric_bridge import parse_data_view_request
    from .registered_sql_admission import (
        RegisteredSQLCapture,
        RegisteredSQLViewContract,
        registered_sql_capture_input_refs,
    )

__all__ = [
    "DefaultFabricPort",
    "DefaultFoundryPort",
    "RegisteredSQLCapture",
    "RegisteredSQLViewContract",
    "parse_data_view_request",
    "registered_sql_capture_input_refs",
]


_LAZY_IMPORTS: dict[str, tuple[str, str]] = {
    "DefaultFabricPort": ("polisyos.scientist.adapters.fabric_bridge", "DefaultFabricPort"),
    "DefaultFoundryPort": ("polisyos.scientist.adapters.foundry_bridge", "DefaultFoundryPort"),
    "RegisteredSQLCapture": (
        "polisyos.scientist.adapters.registered_sql_admission",
        "RegisteredSQLCapture",
    ),
    "RegisteredSQLViewContract": (
        "polisyos.scientist.adapters.registered_sql_admission",
        "RegisteredSQLViewContract",
    ),
    "parse_data_view_request": (
        "polisyos.scientist.adapters.fabric_bridge",
        "parse_data_view_request",
    ),
    "registered_sql_capture_input_refs": (
        "polisyos.scientist.adapters.registered_sql_admission",
        "registered_sql_capture_input_refs",
    ),
}


def __getattr__(name: str) -> Any:
    """Resolve adapter classes lazily and preserve the package-level contract."""
    if name not in _LAZY_IMPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attribute_name = _LAZY_IMPORTS[name]
    return getattr(importlib.import_module(module_name), attribute_name)
