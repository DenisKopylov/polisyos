"""Compatibility facade for the canonical ``core_sources.api`` entrypoint.

The implementation modules own their dependencies.  This module keeps an
explicit, bounded set of historical bindings for callers and test seams; it
does not copy facade globals into implementation modules.
"""

from __future__ import annotations

import inspect
from contextlib import contextmanager
from functools import wraps
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Iterator
    from types import ModuleType

from polisyos.data_forge.domains.catalog.batch._core_sources_ingest_contracts import (
    CORE_SOURCES_COMPATIBILITY_BINDINGS,
    CoreSourcesCompatibilityContext,
    CoreSourcesIngestStats,
    bind_core_sources_compatibility_context,
    current_core_sources_compatibility_context,
    resolve_core_sources_compatibility_binding,
)
from polisyos.data_forge.domains.catalog.batch._core_sources_ingest_contracts import (
    CatalogTransportDataset as CatalogTransportDataset,
)
from polisyos.data_forge.domains.catalog.batch._core_sources_ingest_contracts import (
    ObservationFetchKey as ObservationFetchKey,
)
from polisyos.data_forge.domains.catalog.batch._core_sources_ingest_contracts import (
    ObservationFetchPayload as ObservationFetchPayload,
)
from polisyos.data_forge.domains.catalog.batch._core_sources_ingest_contracts import (
    ObservationInsertStats as ObservationInsertStats,
)
from polisyos.data_forge.domains.catalog.batch._core_sources_ingest_contracts import (
    ObservationPlan as ObservationPlan,
)
from polisyos.data_forge.domains.catalog.batch._core_sources_ingest_contracts import (
    ObservationShard as ObservationShard,
)
from polisyos.data_forge.domains.catalog.batch._core_sources_ingest_contracts import (
    ObservationShardResult as ObservationShardResult,
)
from polisyos.data_forge.domains.catalog.batch._core_sources_ingest_contracts import (
    ObservationWriteItem as ObservationWriteItem,
)
from polisyos.data_forge.domains.catalog.batch._core_sources_ingest_contracts import (
    SupportSketch as SupportSketch,
)
from polisyos.data_forge.domains.catalog.batch._core_sources_ingest_contracts import (
    WriterFlushState as WriterFlushState,
)
from polisyos.data_forge.domains.catalog.batch._core_sources_ingest_contracts import (
    _ObservationRuntimeMetrics as _ObservationRuntimeMetrics,
)
from polisyos.data_forge.domains.catalog.batch._core_sources_ingest_contracts import (
    _SourceBudgetWindow as _SourceBudgetWindow,
)
from polisyos.data_forge.domains.catalog.batch.core_sources import (
    api as _api,
)
from polisyos.data_forge.domains.catalog.batch.core_sources import (
    loaders as _loaders,
)
from polisyos.data_forge.domains.catalog.batch.core_sources import (
    registry as _registry,
)
from polisyos.data_forge.domains.catalog.batch.core_sources import (
    transformers as _transformers,
)
from polisyos.data_forge.domains.catalog.batch.core_sources import (
    validators as _validators,
)
from polisyos.data_forge.domains.catalog.batch.core_sources import (
    writers as _writers,
)

# The leaf contract module is the single source for the 67 supported names.
# Keep the mapping here as concrete module objects for lazy exports and scoped
# legacy overrides; do not discover arbitrary globals at runtime.
_OWNER_MODULES: dict[str, ModuleType] = {
    module.__name__: module
    for module in (_writers, _validators, _loaders, _registry, _transformers, _api)
}
_BINDINGS: dict[str, tuple[ModuleType, str]] = {
    facade_name: (_OWNER_MODULES[module_name], owner_name)
    for (_owner_suffix, facade_name), (module_name, owner_name) in (
        CORE_SOURCES_COMPATIBILITY_BINDINGS.items()
    )
}

_COMPATIBILITY_CALLS = frozenset(
    {
        "_bulk_country_values",
        "_fetch_observation_rows",
        "_ingest_catalog_observations",
        "_insert_generic_observations",
        "_load_wvs_bulk_rows",
        "_run_core_sources_ingest_async",
        "_wvs_bulk_csv_path",
    }
)
_LOCAL_NAMES = frozenset(
    {"run_core_sources_ingest", "run_core_sources_ingest_async", "_sync_implementation_globals"}
)

_MISSING = object()
_COMPATIBILITY_DELEGATE_DEFAULTS: dict[tuple[str, str], Any] = {}


@contextmanager
def _temporary_compatibility_overrides() -> Iterator[None]:
    """Bind a per-call snapshot of explicit legacy facade overrides."""
    current_context = current_core_sources_compatibility_context()
    bindings = dict(current_context.bindings) if current_context is not None else {}
    for name, (module, owner_name) in _BINDINGS.items():
        if name in _LOCAL_NAMES or name not in globals():
            continue
        replacement = globals()[name]
        current = getattr(module, owner_name, _MISSING)
        binding = (module.__name__, owner_name)
        if replacement is current or replacement is _COMPATIBILITY_DELEGATE_DEFAULTS.get(binding):
            continue
        bindings[binding] = replacement
    context = CoreSourcesCompatibilityContext(bindings)
    with bind_core_sources_compatibility_context(context):
        yield


def _compatibility_target(name: str, target: Any) -> Any:
    """Resolve a delegate target from the active invocation context when present."""
    binding = _BINDINGS.get(name)
    if binding is None:
        return target
    module, owner_name = binding
    found, scoped_target = resolve_core_sources_compatibility_binding(module.__name__, owner_name)
    return scoped_target if found else target


def _compatibility_delegate(name: str, target: Any) -> Any:
    """Return a bounded delegate that scopes supported monkeypatch seams."""
    if not callable(target):
        return target
    if inspect.iscoroutinefunction(target):

        @wraps(target)
        async def _async_delegate(*args: Any, **kwargs: Any) -> Any:
            with _temporary_compatibility_overrides():
                result = _compatibility_target(name, target)(*args, **kwargs)
                return await result if inspect.isawaitable(result) else result

        return _async_delegate

    @wraps(target)
    def _delegate(*args: Any, **kwargs: Any) -> Any:
        with _temporary_compatibility_overrides():
            return _compatibility_target(name, target)(*args, **kwargs)

    return _delegate


def __getattr__(name: str) -> Any:
    """Resolve an explicit compatibility binding from its owning leaf."""
    binding = _BINDINGS.get(name)
    if binding is None:
        raise AttributeError(name)
    module, owner_name = binding
    target = getattr(module, owner_name)
    if name in _COMPATIBILITY_CALLS:
        delegate = _compatibility_delegate(name, target)
        _COMPATIBILITY_DELEGATE_DEFAULTS[(module.__name__, owner_name)] = delegate
        return delegate
    return target


def _sync_implementation_globals() -> None:
    """Retained as a no-op compatibility hook; no globals are broadcast."""


async def run_core_sources_ingest_async(config: Any) -> CoreSourcesIngestStats:
    """Run the canonical API while honoring bounded legacy test seams."""
    with _temporary_compatibility_overrides():
        return await _api.run_core_sources_ingest_async(config)


def run_core_sources_ingest(config: Any) -> CoreSourcesIngestStats:
    """Run the canonical API from synchronous callers."""
    from polisyos.common.async_tools import run_coro_sync

    return run_coro_sync(run_core_sources_ingest_async(config))


__all__ = ["CoreSourcesIngestStats", "run_core_sources_ingest"]
