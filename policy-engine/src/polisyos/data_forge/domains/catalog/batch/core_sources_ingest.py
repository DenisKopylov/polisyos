"""Stage 0b: ingest transportability sources into registry/alignment/observation tables.

Compatibility facade for the implementation split under ``core_sources``.
"""

from __future__ import annotations

import inspect
from functools import wraps
from types import ModuleType
from typing import Any, Callable

from polisyos.common.async_tools import run_coro_sync
from polisyos.common.logger import get_logger
from polisyos.data_forge.domains.catalog.batch._core_sources_ingest_contracts import (
    CatalogTransportDataset,
    CoreSourcesIngestStats,
    ObservationFetchKey,
    ObservationFetchPayload,
    ObservationInsertStats,
    ObservationPlan,
    ObservationShard,
    ObservationShardResult,
    ObservationWriteItem,
    SupportSketch,
    WriterFlushState,
    _ObservationRuntimeMetrics,
    _SourceBudgetWindow,
)
from polisyos.data_forge.domains.catalog.batch.core_sources import (
    api as _api,
    loaders as _loaders,
    registry as _registry,
    transformers as _transformers,
    validators as _validators,
    writers as _writers,
)

logger = get_logger(__name__)

_IMPLEMENTATION_MODULES: tuple[ModuleType, ...] = (
    _writers,
    _validators,
    _loaders,
    _registry,
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


def run_core_sources_ingest(config: Any) -> CoreSourcesIngestStats:
    """Run the core-source ingest stage from synchronous callers."""
    return run_coro_sync(run_core_sources_ingest_async(config))


async def run_core_sources_ingest_async(config: Any) -> CoreSourcesIngestStats:
    """Run the core-source ingest stage and publish its manifest."""
    _sync_implementation_globals()
    return await _DELEGATES["run_core_sources_ingest_async"](config)


__all__ = ["CoreSourcesIngestStats", "run_core_sources_ingest"]
