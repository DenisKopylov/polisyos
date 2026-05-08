"""Public API for the runtime control-plane service."""

from __future__ import annotations

from typing import Any

import polisyos.runtime.http.services.control.admission as _admission
import polisyos.runtime.http.services.control.artifacts as _artifacts
import polisyos.runtime.http.services.control.nl_pipeline as _nl_pipeline
import polisyos.runtime.http.services.control.response_shapes as _response_shapes
import polisyos.runtime.http.services.control.run_lifecycle as _run_lifecycle

_MODULES = (_run_lifecycle, _admission, _artifacts, _nl_pipeline, _response_shapes)

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
