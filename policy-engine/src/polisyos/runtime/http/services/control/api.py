"""Public API for the runtime control-plane service."""

from __future__ import annotations

from types import ModuleType as _ModuleType

import polisyos.runtime.http.services.control.admission as _admission
import polisyos.runtime.http.services.control.artifacts as _artifacts
import polisyos.runtime.http.services.control.nl_pipeline as _nl_pipeline
import polisyos.runtime.http.services.control.response_shapes as _response_shapes
import polisyos.runtime.http.services.control.run_lifecycle as _run_lifecycle

_MODULES = (_run_lifecycle, _admission, _artifacts, _nl_pipeline, _response_shapes)

_PUBLIC_EXPORTS = {
    name: getattr(module, name)
    for module in _MODULES
    for name in dir(module)
    if not (name.startswith("__") and name.endswith("__"))
    and hasattr(module, name)
    and not isinstance(getattr(module, name), _ModuleType)
}
__all__ = sorted(_PUBLIC_EXPORTS)
globals().update(_PUBLIC_EXPORTS)


def __getattr__(name: str) -> object:
    try:
        return _PUBLIC_EXPORTS[name]
    except KeyError:
        raise AttributeError(name) from None
