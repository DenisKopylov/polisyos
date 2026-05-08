"""Streaming fulltext-first one-call extraction stage.

Compatibility facade for the resolve/extract implementation split.
"""

from __future__ import annotations

import inspect
from functools import wraps
from types import ModuleType
from typing import Any, Callable

from polisyos.common.logger import get_logger
from polisyos.data_forge.domains.academic.batch._resolve_extract_contracts import (
    EligibilityDecision,
    EligibleItem,
    ProviderResponse,
    ResolveExtractStats,
    WorkItem,
)
from polisyos.data_forge.domains.academic.batch import (
    _resolve_extract_api as _api,
    _resolve_extract_io as _io,
    _resolve_extract_providers as _providers,
    _resolve_extract_transformers as _transformers,
)

logger = get_logger(__name__)

_IMPLEMENTATION_MODULES: tuple[ModuleType, ...] = (
    _providers,
    _io,
    _transformers,
    _api,
)
_DELEGATES: dict[str, Callable[..., Any]] = {}
_INTERNAL_NAMES = {
    "Any",
    "Callable",
    "ModuleType",
    "_DELEGATES",
    "_IMPLEMENTATION_MODULES",
    "_INTERNAL_NAMES",
    "_make_delegate",
    "_sync_implementation_globals",
    "inspect",
    "wraps",
}


def _sync_implementation_globals() -> None:
    public_state = {
        name: value
        for name, value in globals().items()
        if name not in _INTERNAL_NAMES and not name.startswith("__")
    }
    for module in _IMPLEMENTATION_MODULES:
        module.__dict__.update(public_state)


def _make_delegate(name: str, target: Callable[..., Any]) -> Callable[..., Any]:
    if inspect.iscoroutinefunction(target):

        @wraps(target)
        async def _async_delegate(*args: Any, **kwargs: Any) -> Any:
            _sync_implementation_globals()
            return await target(*args, **kwargs)

        _async_delegate.__module__ = __name__
        return _async_delegate

    @wraps(target)
    def _delegate(*args: Any, **kwargs: Any) -> Any:
        _sync_implementation_globals()
        return target(*args, **kwargs)

    _delegate.__module__ = __name__
    return _delegate


for _module in _IMPLEMENTATION_MODULES:
    for _name, _value in vars(_module).items():
        if _name.startswith("__") or _name in _INTERNAL_NAMES:
            continue
        if inspect.isfunction(_value):
            _DELEGATES[_name] = _value
            globals()[_name] = _make_delegate(_name, _value)
        else:
            globals()[_name] = _value


async def run_resolve_extract(config: Any) -> dict[str, float | int]:
    """Run the resolve/extract stage."""
    _sync_implementation_globals()
    return await _DELEGATES["run_resolve_extract"](config)


__all__ = ["run_resolve_extract"]
