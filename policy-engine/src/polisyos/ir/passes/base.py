"""Execution-free IR pass manager primitives.

The pass layer treats IR validation and normalization as a compiler pipeline:
read-only analyses can be cached, transforms declare the surfaces they update,
and cache invalidation is driven by deterministic content fingerprints instead
of mutable runtime state.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, fields, is_dataclass
from typing import Any

from pydantic import BaseModel

from polisyos.ir.canon import CanonSpec, content_hash, to_canonical_bytes


def _normalize_surface_payload(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="python", round_trip=True)
    if is_dataclass(value) and not isinstance(value, type):
        return {
            field_info.name: _normalize_surface_payload(getattr(value, field_info.name))
            for field_info in fields(value)
        }
    if isinstance(value, Mapping):
        return {
            str(key): _normalize_surface_payload(item)
            for key, item in sorted(value.items(), key=lambda entry: str(entry[0]))
        }
    if isinstance(value, (list, tuple)):
        return [_normalize_surface_payload(item) for item in value]
    if isinstance(value, (set, frozenset)):
        normalized_items = [_normalize_surface_payload(item) for item in value]
        return sorted(
            normalized_items,
            key=lambda item: to_canonical_bytes(item),
        )
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    stable_hash = getattr(value, "stable_hash", None)
    if callable(stable_hash):
        return {"stable_hash": stable_hash(), "python_type": type(value).__qualname__}
    path_like = getattr(value, "root", None)
    if path_like is not None:
        return {"root": str(path_like), "python_type": type(value).__qualname__}
    return {"python_type": type(value).__qualname__, "repr": repr(value)}


def stable_surface_fingerprint(value: Any) -> str:
    """Return a deterministic digest for a pass surface or analysis value."""
    normalized = _normalize_surface_payload(value)
    return content_hash(
        to_canonical_bytes(normalized, spec=CanonSpec(forbid_floats=False)),
        prefix=True,
    )


@dataclass(frozen=True)
class InvalidationSet:
    """Describe which named surfaces invalidate cached analyses."""

    keys: frozenset[str] = frozenset()
    invalidate_all: bool = False

    @classmethod
    def none(cls) -> InvalidationSet:
        return cls()

    @classmethod
    def all(cls) -> InvalidationSet:
        return cls(invalidate_all=True)

    @classmethod
    def from_keys(cls, *keys: str) -> InvalidationSet:
        return cls(keys=frozenset(key for key in keys if key))

    def union(self, other: InvalidationSet) -> InvalidationSet:
        if self.invalidate_all or other.invalidate_all:
            return InvalidationSet.all()
        return InvalidationSet(keys=self.keys | other.keys)


@dataclass(frozen=True)
class PassDiagnostic:
    """Structured compiler-style diagnostic emitted by a pass."""

    code: str
    message: str
    severity: str = "info"
    path: tuple[str | int, ...] = ()
    data: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PassContext:
    """Immutable bundle of surfaces, analysis outputs, and diagnostics."""

    surfaces: Mapping[str, Any] = field(default_factory=dict)
    analyses: Mapping[str, Any] = field(default_factory=dict)
    diagnostics: tuple[PassDiagnostic, ...] = ()
    _surface_fingerprints: Mapping[str, str] = field(default_factory=dict)
    _analysis_fingerprints: Mapping[str, str] = field(default_factory=dict)

    def get(self, name: str, default: Any = None) -> Any:
        if name in self.analyses:
            return self.analyses[name]
        return self.surfaces.get(name, default)

    def require(self, name: str) -> Any:
        if name in self.analyses:
            return self.analyses[name]
        if name in self.surfaces:
            return self.surfaces[name]
        raise KeyError(f"PassContext has no surface or analysis named '{name}'")

    def token(self, name: str) -> str:
        if name in self._analysis_fingerprints:
            return self._analysis_fingerprints[name]
        if name in self._surface_fingerprints:
            return self._surface_fingerprints[name]
        raise KeyError(f"PassContext has no fingerprint for '{name}'")

    def with_surface(
        self,
        name: str,
        value: Any,
        *,
        fingerprint: str | None = None,
    ) -> PassContext:
        surfaces = dict(self.surfaces)
        surfaces[name] = value
        surface_fingerprints = dict(self._surface_fingerprints)
        surface_fingerprints[name] = fingerprint or stable_surface_fingerprint(value)
        return PassContext(
            surfaces=surfaces,
            analyses=dict(self.analyses),
            diagnostics=self.diagnostics,
            _surface_fingerprints=surface_fingerprints,
            _analysis_fingerprints=dict(self._analysis_fingerprints),
        )

    def with_analysis(
        self,
        name: str,
        value: Any,
        *,
        fingerprint: str | None = None,
    ) -> PassContext:
        analyses = dict(self.analyses)
        analyses[name] = value
        analysis_fingerprints = dict(self._analysis_fingerprints)
        analysis_fingerprints[name] = fingerprint or stable_surface_fingerprint(value)
        return PassContext(
            surfaces=dict(self.surfaces),
            analyses=analyses,
            diagnostics=self.diagnostics,
            _surface_fingerprints=dict(self._surface_fingerprints),
            _analysis_fingerprints=analysis_fingerprints,
        )

    def extend_diagnostics(self, diagnostics: Sequence[PassDiagnostic]) -> PassContext:
        if not diagnostics:
            return self
        return PassContext(
            surfaces=dict(self.surfaces),
            analyses=dict(self.analyses),
            diagnostics=self.diagnostics + tuple(diagnostics),
            _surface_fingerprints=dict(self._surface_fingerprints),
            _analysis_fingerprints=dict(self._analysis_fingerprints),
        )


@dataclass(frozen=True)
class PassResult:
    """The output of one pass application."""

    surface_updates: Mapping[str, Any] = field(default_factory=dict)
    analysis_updates: Mapping[str, Any] = field(default_factory=dict)
    diagnostics: tuple[PassDiagnostic, ...] = ()
    invalidation: InvalidationSet = field(default_factory=InvalidationSet.none)

    @classmethod
    def noop(cls) -> PassResult:
        return cls()


class IRPass(ABC):
    """Base class for deterministic IR passes."""

    name: str = "ir_pass"
    kind: str = "transform"
    reads: tuple[str, ...] = ()
    writes: tuple[str, ...] = ()

    @abstractmethod
    def run(self, context: PassContext) -> PassResult:
        """Execute the pass against the provided context."""


class IRAnalysis(IRPass):
    """Read-only pass whose outputs can be cached by dependency fingerprint."""

    kind = "analysis"
    writes: tuple[str, ...] = ()


@dataclass(frozen=True)
class _CachedAnalysis:
    analysis_updates: Mapping[str, Any]
    diagnostics: tuple[PassDiagnostic, ...]


class PassPipeline:
    """Run IR passes in order with deterministic analysis caching."""

    def __init__(self, passes: Sequence[IRPass]) -> None:
        self._passes = tuple(passes)
        self._analysis_cache: dict[tuple[str, tuple[tuple[str, str], ...]], _CachedAnalysis] = {}

    def _dependency_signature(
        self,
        ir_pass: IRPass,
        context: PassContext,
    ) -> tuple[tuple[str, str], ...]:
        return tuple(
            sorted(
                (name, context.token(name))
                for name in ir_pass.reads
                if name in context.surfaces or name in context.analyses
            )
        )

    def _invalidate_cache(self, invalidation: InvalidationSet) -> None:
        if invalidation.invalidate_all:
            self._analysis_cache.clear()
            return
        if not invalidation.keys:
            return
        to_delete = [
            cache_key
            for cache_key in self._analysis_cache
            if invalidation.keys.intersection(name for name, _ in cache_key[1])
        ]
        for cache_key in to_delete:
            self._analysis_cache.pop(cache_key, None)

    def run(self, context: PassContext) -> PassContext:
        current = context
        for ir_pass in self._passes:
            dependency_signature = self._dependency_signature(ir_pass, current)
            cache_key = (ir_pass.name, dependency_signature)
            if ir_pass.kind == "analysis" and cache_key in self._analysis_cache:
                cached = self._analysis_cache[cache_key]
                for name, value in cached.analysis_updates.items():
                    current = current.with_analysis(name, value)
                current = current.extend_diagnostics(cached.diagnostics)
                continue

            result = ir_pass.run(current)
            if ir_pass.kind == "analysis" and result.surface_updates:
                raise ValueError(f"analysis pass '{ir_pass.name}' may not update surfaces")

            for name, value in result.surface_updates.items():
                current = current.with_surface(name, value)
            for name, value in result.analysis_updates.items():
                current = current.with_analysis(name, value)
            current = current.extend_diagnostics(result.diagnostics)

            self._invalidate_cache(result.invalidation)

            if ir_pass.kind == "analysis":
                self._analysis_cache[cache_key] = _CachedAnalysis(
                    analysis_updates=dict(result.analysis_updates),
                    diagnostics=result.diagnostics,
                )
        return current


__all__ = [
    "IRAnalysis",
    "IRPass",
    "InvalidationSet",
    "PassContext",
    "PassDiagnostic",
    "PassPipeline",
    "PassResult",
    "stable_surface_fingerprint",
]
