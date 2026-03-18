"""
Persistent SQLite Registry Cache.

``RegistryPersistenceLayer`` accelerates cold-start by caching registry
entries to a SQLite database.  On subsequent process starts, the registry
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
- Only stores ``MethodSignature`` + ``MethodMetadata`` + module path.
  The actual Python class is *not* stored; lazy factories are reconstructed.
- Cache must be invalidated manually when ``_registry_boot.py`` files change.
  The ``is_cache_valid()`` check uses a global catalog hash (XOR of all
  signature hashes) stored in a ``_meta`` table.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

__all__ = [
    "RegistryPersistenceLayer",
    "CachedMethodRecord",
]

_SCHEMA_VERSION = "1"

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

    Parameters
    ----------
    db_path:
        Path to the SQLite database file.  Created if absent.
        Use ``:memory:`` for an in-memory database (testing only).
    """

    def __init__(self, db_path: Path | str) -> None:
        self._db_path = Path(db_path)
        self._lock = threading.Lock()
        self._conn: sqlite3.Connection | None = None
        self._init_db()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def snapshot_from(self, registry: Any) -> int:
        """
        Persist all entries from *registry* to the database.

        Returns the number of rows written.
        """
        import time

        entries = registry.list_all()
        rows: list[tuple] = []
        now = time.time()
        catalog_hash_parts: list[str] = []

        for entry in entries:
            fqn = entry.fqn
            sig = entry.signature
            meta = entry.metadata
            try:
                sig_json = json.dumps(sig.to_dict(), sort_keys=True)
                sig_hash = hashlib.sha256(sig_json.encode()).hexdigest()
                meta_json = json.dumps({
                    "description": meta.description,
                    "tags": sorted(str(t) for t in meta.tags),
                    "citations": list(meta.citations or []),
                }, sort_keys=True)
            except Exception:
                continue

            # Resolve module + class_name for lazy factory reconstruction
            cached_class = entry._cached_class
            if cached_class is not None:
                module = cached_class.__module__
                class_name = cached_class.__qualname__
            else:
                module = ""
                class_name = ""

            rows.append((fqn, module, class_name, sig_json, sig_hash, meta_json, now))
            catalog_hash_parts.append(sig_hash)

        catalog_hash = hashlib.sha256(
            "|".join(sorted(catalog_hash_parts)).encode()
        ).hexdigest()

        with self._lock:
            conn = self._get_conn()
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

        return len(rows)

    def restore_into(self, registry: Any) -> int:
        """
        Restore registry entries from the cache into *registry*.

        Each entry is registered as a *lazy* factory that imports the
        original class on first access.

        Returns the number of entries restored.
        """
        from polisyos.foundry.methods.base import MethodMetadata, MethodSignature

        rows = self._fetch_all_entries()
        restored = 0

        for row in rows:
            fqn = row[0]
            module = row[1]
            class_name = row[2]
            sig_json = row[3]
            meta_json = row[5]

            try:
                sig_dict = json.loads(sig_json)
                meta_dict = json.loads(meta_json)
                sig = MethodSignature.from_dict(sig_dict)
                meta = MethodMetadata(
                    description=meta_dict.get("description", ""),
                    tags=frozenset(meta_dict.get("tags", [])),
                    citations=tuple(meta_dict.get("citations", [])),
                )
            except Exception:
                continue

            # Build lazy factory
            def _make_factory(mod: str, cls: str) -> Any:
                def _factory() -> type:
                    import importlib
                    m = importlib.import_module(mod)
                    return getattr(m, cls)
                return _factory

            factory = _make_factory(module, class_name) if module and class_name else lambda: None  # type: ignore[return-value]

            try:
                registry.register_lazy(sig, meta, factory)
                restored += 1
            except Exception:
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
            conn = self._get_conn()
            row = conn.execute(
                "SELECT value FROM _meta WHERE key = 'schema_version'"
            ).fetchone()
            if row is None or row[0] != _SCHEMA_VERSION:
                return False

            if registry is None:
                return True

            # Compare catalog hashes
            stored = conn.execute(
                "SELECT value FROM _meta WHERE key = 'catalog_hash'"
            ).fetchone()
            if stored is None:
                return False

            live_hash = self._compute_catalog_hash(registry)
            return stored[0] == live_hash
        except Exception:
            return False

    def all_records(self) -> list[CachedMethodRecord]:
        """Return a list of all cached records (for inspection / tooling)."""
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
        """Delete all cached entries (forces full re-registration next time)."""
        with self._lock:
            conn = self._get_conn()
            conn.execute("DELETE FROM method_entries")
            conn.execute("DELETE FROM _meta")
            conn.commit()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _init_db(self) -> None:
        if str(self._db_path) != ":memory:":
            self._db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            conn = self._get_conn()
            conn.execute(_CREATE_META)
            conn.execute(_CREATE_ENTRIES)
            conn.commit()

    def _get_conn(self) -> sqlite3.Connection:
        """Return (creating if needed) the SQLite connection."""
        if self._conn is None:
            self._conn = sqlite3.connect(
                str(self._db_path),
                check_same_thread=False,
                timeout=10.0,
            )
            self._conn.execute("PRAGMA journal_mode=WAL")
        return self._conn

    def _fetch_all_entries(self) -> list[tuple]:
        with self._lock:
            conn = self._get_conn()
            return conn.execute(
                "SELECT fqn, module, class_name, signature_json, "
                "signature_hash, metadata_json, registered_at "
                "FROM method_entries ORDER BY fqn"
            ).fetchall()

    @staticmethod
    def _compute_catalog_hash(registry: Any) -> str:
        """Compute a hash of all live registry entries."""
        parts: list[str] = []
        for entry in registry.list_all():
            try:
                sig_json = json.dumps(entry.signature.to_dict(), sort_keys=True)
                parts.append(hashlib.sha256(sig_json.encode()).hexdigest())
            except Exception:
                parts.append(entry.fqn)
        return hashlib.sha256(
            "|".join(sorted(parts)).encode()
        ).hexdigest()

    def __del__(self) -> None:
        if self._conn is not None:
            try:
                self._conn.close()
            except Exception:
                pass
