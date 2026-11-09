"""Bundle the three Trinity artifacts as one validated policy payload.

``ProblemFrame`` defines **what** to optimize/protect, ``PolicySpec`` defines
the proposed intervention/governance surface, and ``ModelSpec`` defines **how**
the world is simulated. ``TrinityBundle`` keeps these contracts together for
loading, validation, and migration-safe persistence.
"""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING

from polisyos.ir.governance.policy_spec import PolicySpec
from polisyos.ir.governance.problem_frame import ProblemFrame
from polisyos.ir.model_layer.model_spec import ModelSpec
from polisyos.ir.trinity.contracts import (
    SCHEMA_VERSION_PATTERN as SCHEMA_VERSION_PATTERN,
)
from polisyos.ir.trinity.contracts import (
    TRINITY_BUNDLE_SCHEMA_VERSION as TRINITY_BUNDLE_SCHEMA_VERSION,
)
from polisyos.ir.trinity.contracts import (
    TrinityBundle as TrinityBundle,
)

if TYPE_CHECKING:
    from polisyos.ir.trinity.loaders import (
        load_trinity_bundle_artifact as load_trinity_bundle_artifact,
    )
    from polisyos.ir.trinity.loaders import (
        persist_trinity_bundle_artifact as persist_trinity_bundle_artifact,
    )

__all__ = [
    "TRINITY_BUNDLE_SCHEMA_VERSION",
    "ModelSpec",
    "PolicySpec",
    "ProblemFrame",
    "TrinityBundle",
    "load_trinity_bundle_artifact",
    "persist_trinity_bundle_artifact",
]

_LAZY_IMPORTS: dict[str, tuple[str, str]] = {
    "load_trinity_bundle_artifact": (
        "polisyos.ir.trinity.loaders",
        "load_trinity_bundle_artifact",
    ),
    "persist_trinity_bundle_artifact": (
        "polisyos.ir.trinity.loaders",
        "persist_trinity_bundle_artifact",
    ),
}


def __getattr__(name: str) -> object:
    if name in _LAZY_IMPORTS:
        module_name, attr_name = _LAZY_IMPORTS[name]
        module = importlib.import_module(module_name)
        value = getattr(module, attr_name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
