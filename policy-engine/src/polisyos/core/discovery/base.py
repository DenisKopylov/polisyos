"""Core discovery primitives for loading plugins from entry points and source files."""
from __future__ import annotations

import importlib.util
import re
import sys
import traceback as traceback_lib
from dataclasses import dataclass, field
from enum import Enum
from importlib import metadata
from pathlib import Path
from types import ModuleType
from typing import Any, Callable, Generic, Iterable, Iterator, Protocol, Sequence, TypeVar

from polisyos.core.canon import truncated_hash

T = TypeVar("T")
E = TypeVar("E")


class DuplicatePolicy(str, Enum):
    """How registry builders should react when two discovered items share the same identity."""
    WARN = "warn"
    ERROR = "error"
    IGNORE = "ignore"


@dataclass(slots=True)
class DiscoveryError:
    """Discovery error exception."""
    source: str
    item: str | None
    error_type: str
    message: str
    traceback: str | None = None
    details: dict[str, str] = field(default_factory=dict)


class DiscoverySource(Protocol[T]):
    """Discovery source public type."""
    def discover(self) -> Iterator[T]:
        ...


@dataclass(slots=True)
class SourceBatch(Generic[T, E]):
    """Source batch public type."""
    source: DiscoverySource[T] | Any
    items: list[T] = field(default_factory=list)
    errors: list[E] = field(default_factory=list)


class BaseDiscovery(Generic[T, E]):
    """
    Shared source-collection orchestration for discovery systems.

    The class focuses only on collecting items/errors from sources. Domain-specific
    registration and duplicate handling remain in higher-level orchestrators.
    """

    def __init__(
        self,
        *,
        sources: Sequence[DiscoverySource[T]] | None = None,
        on_source_error: Callable[[DiscoverySource[T] | Any, Exception], E] | None = None,
        error_attr: str = "errors",
    ) -> None:
        self._sources: list[DiscoverySource[T]] = list(sources or [])
        self._on_source_error = on_source_error
        self._error_attr = error_attr

    @property
    def sources(self) -> list[DiscoverySource[T]]:
        return list(self._sources)

    def add_source(self, source: DiscoverySource[T]) -> BaseDiscovery[T, E]:
        self._sources.append(source)
        return self

    def collect(self) -> tuple[list[SourceBatch[T, E]], int]:
        batches: list[SourceBatch[T, E]] = []
        processed = 0

        for source in self._sources:
            processed += 1
            batch: SourceBatch[T, E] = SourceBatch(source=source)

            try:
                batch.items.extend(source.discover())
            except Exception as exc:
                if self._on_source_error is not None:
                    batch.errors.append(self._on_source_error(source, exc))
                else:
                    raise

            source_errors = getattr(source, self._error_attr, None)
            if source_errors:
                batch.errors.extend(_coerce_iterable(source_errors))

            batches.append(batch)

        return batches, processed


def list_entry_points(*, group: str) -> list[metadata.EntryPoint]:
    """
    Compatibility wrapper over importlib.metadata.entry_points().
    """

    try:
        direct = metadata.entry_points(group=group)
    except TypeError:
        direct = None

    if direct is not None:
        return sorted(list(direct), key=_entry_point_sort_key)

    all_eps = metadata.entry_points()
    if hasattr(all_eps, "select"):
        selected = all_eps.select(group=group)  # type: ignore[call-arg]
    else:
        selected = all_eps.get(group, [])
    return sorted(list(selected), key=_entry_point_sort_key)


def discovery_module_name(
    path: Path,
    *,
    prefix: str,
    algorithm: str = "sha1",
    digest_length: int = 12,
) -> str:
    """Derive a deterministic temporary module name for loading a source file exactly once."""
    digest = truncated_hash(str(path.resolve()), algorithm=algorithm, length=digest_length)
    stem = _safe_identifier(path.stem)
    if stem:
        return f"{prefix}{stem}_{digest}"
    return f"{prefix}{digest}"


def load_module_from_file(path: Path, *, module_name: str) -> ModuleType:
    """Load module from file."""
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"failed to create import spec for {path}")

    module = importlib.util.module_from_spec(spec)
    try:
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        return module
    except Exception:
        sys.modules.pop(module_name, None)
        raise


def format_traceback() -> str:
    """Capture the active exception traceback as a printable string for discovery errors."""
    return traceback_lib.format_exc()


def _coerce_iterable(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, Iterable):
        return list(value)
    return [value]


def _entry_point_sort_key(entry_point: metadata.EntryPoint) -> tuple[str, str]:
    name = str(getattr(entry_point, "name", ""))
    value = str(getattr(entry_point, "value", ""))
    return (name, value)


_NON_IDENTIFIER_RE = re.compile(r"[^A-Za-z0-9_]")


def _safe_identifier(value: str) -> str:
    cleaned = _NON_IDENTIFIER_RE.sub("_", value.strip())
    cleaned = cleaned.strip("_")
    if not cleaned:
        return ""
    if cleaned[0].isdigit():
        return f"m_{cleaned}"
    return cleaned
