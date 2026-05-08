"""Public API for decision-packet assembly."""

from __future__ import annotations

from typing import Any

import polisyos.scientist.nodes.builtins.decide.decision_packet.builder as _builder
import polisyos.scientist.nodes.builtins.decide.decision_packet.enrichment as _enrichment
import polisyos.scientist.nodes.builtins.decide.decision_packet.serialization as _serialization
import polisyos.scientist.nodes.builtins.decide.decision_packet.validation as _validation

_MODULES = (_builder, _enrichment, _serialization, _validation)

__all__ = sorted(
    {
        name
        for module in _MODULES
        for name in dir(module)
        if not (name.startswith("__") and name.endswith("__"))
    }
)

for _module in _MODULES:
    globals().update({name: getattr(_module, name) for name in __all__ if hasattr(_module, name)})


def __getattr__(name: str) -> Any:
    for module in _MODULES:
        if hasattr(module, name):
            return getattr(module, name)
    raise AttributeError(name)
