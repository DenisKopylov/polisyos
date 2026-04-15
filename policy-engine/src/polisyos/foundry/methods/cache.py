"""
Persistent SQLite Registry Cache.

``RegistryPersistenceLayer`` accelerates cold-start by caching registry
entries to a SQLite database. On subsequent process starts, the registry
is restored from the cache (O(n) disk reads) rather than re-importing every
catalog module (O(n) Python imports with potential heavy transitive deps).

Cache invalidation
------------------
The cache stores a per-entry ``signature_hash`` (SHA-256 of the method
signature's JSON repr).  On restore, the hashes are compared against the
freshly computed hashes of the live classes.  Any mismatch causes a full
re-registration and cache rebuild for the affected methods.

Fast path
---------
::

    from polisyos.foundry.methods.cache import RegistryPersistenceLayer
    from pathlib import Path

    cache = RegistryPersistenceLayer(Path.home() / ".cache/polisyos/registry.db")
    with registry_scope() as reg:
        if cache.is_cache_valid():
            cache.restore_into(reg)          # fast — no module imports
        else:
            ensure_all_methods_registered(reg)
            cache.snapshot_from(reg)         # write updated cache

Limitations
-----------
- Only stores ``MethodSignature`` + a persistable subset of
  ``MethodMetadata`` + import targets. The actual Python class is *not*
  stored; lazy factories are reconstructed from module + qualname.
- Lazy entries without a recoverable import target are skipped during
  snapshot/restore rather than being restored as broken placeholders.
- Cache must be invalidated manually when ``_registry_boot.py`` files change.
  The ``is_cache_valid()`` check uses a global catalog hash (XOR of all
  signature hashes) stored in a ``_meta`` table.
"""
from __future__ import annotations

import hashlib
import json
import math
import sqlite3
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from polisyos.foundry.methods.exceptions import FoundryMethodError

__all__ = [
    "CachedMethodRecord",
    "RegistryPersistenceLayer",
]

_SCHEMA_VERSION = "2"

_CREATE_META = """
CREATE TABLE IF NOT EXISTS _meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
)
"""

_CREATE_ENTRIES = """
CREATE TABLE IF NOT EXISTS method_entries (
    fqn            TEXT PRIMARY KEY,
    module         TEXT NOT NULL,
    class_name     TEXT NOT NULL,
    signature_json TEXT NOT NULL,
    signature_hash TEXT NOT NULL,
    metadata_json  TEXT NOT NULL,
    registered_at  REAL NOT NULL
)
"""

_INSERT_OR_REPLACE = """
INSERT OR REPLACE INTO method_entries
    (fqn, module, class_name, signature_json, signature_hash, metadata_json, registered_at)
VALUES (?, ?, ?, ?, ?, ?, ?)
"""


@dataclass
class CachedMethodRecord:
    """A single row from the ``method_entries`` table."""

    fqn: str
    module: str
    class_name: str
    signature_hash: str
    registered_at: float


# ---------------------------------------------------------------------------
# RegistryPersistenceLayer
# ---------------------------------------------------------------------------


class RegistryPersistenceLayer:
    """
    SQLite-backed persistence for the Foundry method registry.

    This cache accelerates registry discovery/bootstrap only. It stores method
    signatures, metadata, and lazy import locations, not compiled backend
    functions; compiled-function reuse is handled separately by
    `methods.specialization` and `methods.compiler.CompilationCache`.

    Parameters
    ----------
    db_path:
        Path to the SQLite database file.  Created if absent.
        Use ``:memory:`` for an in-memory database (testing only).

    Thread Safety
    -------------
    One ``RegistryPersistenceLayer`` instance owns at most one SQLite
    connection at a time. All DB access is serialized through an internal
    re-entrant lock, and callers can opt into explicit lifetime management via
    ``with RegistryPersistenceLayer(...) as cache: ...`` or ``open()/close()``.
    """

    def __init__(self, db_path: Path | str) -> None:
        self._db_path = Path(db_path)
        self._lock = threading.RLock()
        self._conn: sqlite3.Connection | None = None
        self._init_db()

    def __enter__(self) -> RegistryPersistenceLayer:
        self.open()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def open(self) -> None:
        """Eagerly open the owned SQLite connection."""
        with self._lock:
            self._ensure_conn_locked()

    def close(self) -> None:
        """Close the owned SQLite connection if it is currently open."""
        with self._lock:
            if self._conn is None:
                return
            self._conn.close()
            self._conn = None

    def snapshot_from(self, registry: Any) -> int:
        """
        Persist all registry entries and a catalog hash to the SQLite cache.

        Returns the number of rows written.
        """
        import time

        snapshot = registry.snapshot()
        rows: list[tuple] = []
        now = time.time()
        catalog_hash_parts: list[str] = []

        for entry in snapshot.entries():
            fqn = entry.fqn
            sig = entry.signature
            meta = entry.metadata
            try:
                sig_json = json.dumps(_signature_payload(sig), sort_keys=True)
                sig_hash = hashlib.sha256(sig_json.encode()).hexdigest()
                meta_json = json.dumps(_metadata_payload(meta), sort_keys=True)
            except (TypeError, ValueError):
                continue

            import_target = entry.persistable_import_target
            if import_target is None:
                continue
            module, class_name = import_target

            rows.append((fqn, module, class_name, sig_json, sig_hash, meta_json, now))
            catalog_hash_parts.append(sig_hash)

        catalog_hash = hashlib.sha256(
            "|".join(sorted(catalog_hash_parts)).encode()
        ).hexdigest()

        with self._connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                conn.execute("DELETE FROM method_entries")
                if rows:
                    conn.executemany(_INSERT_OR_REPLACE, rows)
                conn.execute(
                    "INSERT OR REPLACE INTO _meta VALUES (?, ?)",
                    ("catalog_hash", catalog_hash),
                )
                conn.execute(
                    "INSERT OR REPLACE INTO _meta VALUES (?, ?)",
                    ("schema_version", _SCHEMA_VERSION),
                )
                conn.commit()
            except sqlite3.Error:
                conn.rollback()
                raise

        return len(rows)

    def restore_into(self, registry: Any) -> int:
        """
        Restore method entries from SQLite as lazy factories in *registry*.

        Each entry is registered as a *lazy* factory that imports the
        original class on first access.

        Returns the number of entries restored.
        """
        rows = self._fetch_all_entries()
        restored = 0

        for row in rows:
            module = row[1]
            class_name = row[2]
            sig_json = row[3]
            meta_json = row[5]

            try:
                sig = _signature_from_payload(json.loads(sig_json))
                meta = _metadata_from_payload(json.loads(meta_json))
            except (TypeError, ValueError, json.JSONDecodeError):
                continue

            # Build lazy factory
            def _make_factory(mod: str, cls: str) -> Any:
                def _factory() -> type:
                    import importlib
                    m = importlib.import_module(mod)
                    return getattr(m, cls)
                return _factory

            if not module or not class_name:
                continue
            factory = _make_factory(module, class_name)

            try:
                registry.register_lazy(
                    sig,
                    meta,
                    factory,
                    import_target=(module, class_name),
                )
                restored += 1
            except (AttributeError, TypeError, ValueError, FoundryMethodError):
                pass  # skip already-registered or invalid entries

        return restored

    def is_cache_valid(self, registry: Any | None = None) -> bool:
        """
        Return True if the on-disk cache is up-to-date.

        If *registry* is provided, computes the catalog hash from live
        entries and compares to stored hash.  If *registry* is None,
        just checks that the database exists and has the correct schema
        version.
        """
        if not self._db_path.exists() and str(self._db_path) != ":memory:":
            return False

        try:
            with self._connection() as conn:
                row = conn.execute(
                    "SELECT value FROM _meta WHERE key = 'schema_version'"
                ).fetchone()
                if row is None or row[0] != _SCHEMA_VERSION:
                    return False

                if registry is None:
                    return True

                stored = conn.execute(
                    "SELECT value FROM _meta WHERE key = 'catalog_hash'"
                ).fetchone()
                if stored is None:
                    return False

                live_hash = self._compute_catalog_hash(registry)
                return stored[0] == live_hash
        except (sqlite3.Error, TypeError, ValueError):
            return False

    def all_records(self) -> list[CachedMethodRecord]:
        """Return cached registry rows for diagnostics and catalog tooling."""
        rows = self._fetch_all_entries()
        return [
            CachedMethodRecord(
                fqn=row[0],
                module=row[1],
                class_name=row[2],
                signature_hash=row[4],
                registered_at=row[6],
            )
            for row in rows
        ]

    def invalidate(self) -> None:
        """Delete cached registry rows and metadata to force a full rebuild."""
        with self._connection() as conn:
            conn.execute("DELETE FROM method_entries")
            conn.execute("DELETE FROM _meta")
            conn.commit()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _init_db(self) -> None:
        if str(self._db_path) != ":memory:":
            self._db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connection() as conn:
            conn.execute(_CREATE_META)
            conn.execute(_CREATE_ENTRIES)
            conn.commit()

    def _ensure_conn_locked(self) -> sqlite3.Connection:
        """Return the owned SQLite connection. Caller must hold ``self._lock``."""
        if self._conn is None:
            self._conn = sqlite3.connect(
                str(self._db_path),
                check_same_thread=False,
                timeout=10.0,
            )
            self._conn.execute("PRAGMA journal_mode=WAL")
        return self._conn

    @contextmanager
    def _connection(self) -> Any:
        """Yield the owned SQLite connection while holding the lifecycle lock."""
        with self._lock:
            yield self._ensure_conn_locked()

    def _fetch_all_entries(self) -> list[tuple]:
        with self._connection() as conn:
            return conn.execute(
                "SELECT fqn, module, class_name, signature_json, "
                "signature_hash, metadata_json, registered_at "
                "FROM method_entries ORDER BY fqn"
            ).fetchall()

    @staticmethod
    def _compute_catalog_hash(registry: Any) -> str:
        """Compute a hash of all live registry entries."""
        parts: list[str] = []
        snapshot = registry.snapshot()
        for entry in snapshot.entries():
            try:
                sig_json = json.dumps(
                    _signature_payload(entry.signature),
                    sort_keys=True,
                )
                parts.append(hashlib.sha256(sig_json.encode()).hexdigest())
            except (TypeError, ValueError):
                parts.append(entry.fqn)
        return hashlib.sha256(
            "|".join(sorted(parts)).encode()
        ).hexdigest()


def _signature_payload(signature) -> dict[str, Any]:
    """Serialize a signature using its stable, JSON-safe payload."""
    return signature._stable_dict()


def _metadata_payload(metadata) -> dict[str, Any]:
    """Serialize metadata using its stable, JSON-safe payload."""
    return metadata._stable_dict()


def _dim_from_payload(value: Any) -> int | str | None:
    if isinstance(value, str) and value.startswith("$DimVar:"):
        from polisyos.foundry.methods.base import DimVar

        return DimVar(value.split(":", 1)[1])
    return value


def _unit_from_payload(payload: dict[str, Any]):
    from polisyos.foundry.methods.base import Unit

    scale = payload.get("scale", 1.0)
    if isinstance(scale, str):
        scale = float.fromhex(scale) if scale.startswith("0x") else float(scale)
    return Unit(
        dimension=str(payload["dimension"]),
        symbol=str(payload["symbol"]),
        scale=float(scale),
    )


def _slot_from_payload(payload: dict[str, Any]):
    from polisyos.foundry.methods.base import SlotSpec, SlotType

    return SlotSpec(
        name=str(payload["name"]),
        slot_type=SlotType[str(payload["slot_type"])],
        unit=_unit_from_payload(payload["unit"]),
        contract_id=payload.get("contract_id"),
        shape=tuple(_dim_from_payload(item) for item in payload.get("shape", [])),
    )


def _parameter_from_payload(payload: dict[str, Any]):
    from polisyos.foundry.methods.base import ParameterSpec

    bounds = payload.get("bounds", (None, None))
    return ParameterSpec(
        name=str(payload["name"]),
        default=_restore_stable_value(payload.get("default")),
        is_static=bool(payload.get("is_static", False)),
        bounds=tuple(_restore_stable_value(item) for item in bounds),
    )


def _signature_from_payload(payload: dict[str, Any]):
    from polisyos.foundry.methods.base import (
        ComplexityClass,
        ComputeBackend,
        FidelityLevel,
        MethodKind,
        MethodSignature,
    )

    fidelity_tier = payload.get("fidelity_tier")
    return MethodSignature(
        name=str(payload["name"]),
        namespace=str(payload["namespace"]),
        version=str(payload["version"]),
        input_slots=frozenset(
            _slot_from_payload(item) for item in payload.get("input_slots", [])
        ),
        output_slots=frozenset(
            _slot_from_payload(item) for item in payload.get("output_slots", [])
        ),
        parameters=tuple(
            _parameter_from_payload(item) for item in payload.get("parameters", [])
        ),
        fidelity=FidelityLevel[str(payload["fidelity"])],
        complexity=ComplexityClass[str(payload["complexity"])],
        backend=ComputeBackend(str(payload.get("backend", ComputeBackend.JAX.value))),
        kind=MethodKind(str(payload.get("kind", MethodKind.PURE.value))),
        family=str(payload.get("family", "")),
        variant=str(payload.get("variant", "")),
        data_modalities=frozenset(payload.get("data_modalities", [])),
        fidelity_tier=FidelityLevel[str(fidelity_tier)] if fidelity_tier else None,
        commutes_with=frozenset(payload.get("commutes_with", [])),
        conflicts_with=frozenset(payload.get("conflicts_with", [])),
        requires=frozenset(payload.get("requires", [])),
        supports_jit=bool(payload.get("supports_jit", True)),
        supports_vmap=bool(payload.get("supports_vmap", True)),
        supports_grad=bool(payload.get("supports_grad", True)),
    )


def _metadata_from_payload(payload: dict[str, Any]):
    from polisyos.core.observability.determinism import DeterminismTier
    from polisyos.foundry.methods.base import MethodMetadata, SideEffectProfile

    determinism_tier = payload.get("determinism_tier")
    return MethodMetadata(
        description=str(payload.get("description", "")),
        tags=frozenset(payload.get("tags", [])),
        citations=tuple(payload.get("citations", [])),
        equations=dict(_restore_stable_value(payload.get("equations", {}))),
        assumptions=dict(_restore_stable_value(payload.get("assumptions", {}))),
        determinism_tier=(
            DeterminismTier(str(determinism_tier))
            if determinism_tier is not None
            else None
        ),
        required_deps=tuple(payload.get("required_deps", [])),
        optional_deps=tuple(payload.get("optional_deps", [])),
        fallback_policy=str(payload.get("fallback_policy", "none")),
        side_effect_profile=SideEffectProfile(
            str(payload.get("side_effect_profile", SideEffectProfile.NONE.value))
        ),
        when_to_use=str(payload.get("when_to_use", "")),
        when_not_to_use=str(payload.get("when_not_to_use", "")),
        prerequisites=tuple(payload.get("prerequisites", [])),
        diagnostic_checks=tuple(payload.get("diagnostic_checks", [])),
        typical_min_obs=payload.get("typical_min_obs"),
        output_interpretation=str(payload.get("output_interpretation", "")),
    )


def _restore_stable_value(value: Any) -> Any:
    if isinstance(value, dict):
        if "__float__" in value:
            return float.fromhex(str(value["__float__"]))
        if "__bytes__" in value:
            return bytes.fromhex(str(value["__bytes__"]))
        if "__map__" in value:
            return {
                str(key): _restore_stable_value(item)
                for key, item in value["__map__"].items()
            }
        if "__tuple__" in value:
            return tuple(_restore_stable_value(item) for item in value["__tuple__"])
        if "__list__" in value:
            return [_restore_stable_value(item) for item in value["__list__"]]
        if "__set__" in value:
            return frozenset(_restore_stable_value(item) for item in value["__set__"])
        if "__ndarray__" in value:
            array_payload = value["__ndarray__"]
            dtype = np.dtype(array_payload["dtype"])
            shape = tuple(array_payload["shape"])
            data = bytes.fromhex(array_payload["data"])
            return np.frombuffer(data, dtype=dtype).reshape(shape)
        return {str(key): _restore_stable_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_restore_stable_value(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_restore_stable_value(item) for item in value)
    if isinstance(value, str):
        if value.startswith("0x"):
            try:
                restored = float.fromhex(value)
            except ValueError:
                return value
            if math.isfinite(restored):
                return restored
        return value
    return value
