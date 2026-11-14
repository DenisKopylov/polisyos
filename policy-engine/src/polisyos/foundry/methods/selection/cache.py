"""
Persistent SQLite Registry Cache.

``RegistryPersistenceLayer`` accelerates cold-start by caching registry
entries to a SQLite database. On subsequent process starts, the registry
is restored from the cache (O(n) disk reads) rather than re-importing every
catalog module (O(n) Python imports with potential heavy transitive deps).

Cache invalidation
------------------
The legacy per-entry ``signature_hash`` remains the stable ABI projection. A
separate versioned snapshot fingerprint binds the complete signature,
selection metadata, and qualified import target. A caller with a live registry
can compare that fingerprint before using the cached catalog.

Cache admission
---------------
A no-argument integrity check is not a cold-start currentness proof. A caller
that needs to claim the snapshot matches current source must first supply the
live admitted registry to ``is_cache_valid(registry)``. There is currently no
tracked application caller that establishes this source-qualified fast path.

Limitations
-----------
- Stores the complete semantic fields of ``MethodSignature`` and
  ``MethodMetadata`` with import targets. The actual Python class is *not*
  stored; lazy factories are reconstructed from module + qualname.
- Lazy entries without a recoverable import target are skipped during
  snapshot/restore rather than being restored as broken placeholders.
- ``is_cache_valid()`` verifies the persisted snapshot integrity only.
  Supplying the live registry additionally detects semantic metadata,
  signature, and import-target drift; callers must use that form before
  treating the snapshot as current.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from polisyos.foundry.methods._internal.executable_identity import (
    _is_import_target_syntactically_valid,
    _resolve_import_target,
)
from polisyos.foundry.methods.exceptions import FoundryMethodError

__all__ = [
    "CachedMethodRecord",
    "RegistryPersistenceLayer",
]

_SCHEMA_VERSION = "5"
_SEMANTIC_SNAPSHOT_VERSION = 2

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
            import_target = entry.persistable_import_target
            if import_target is None or not _is_import_target_syntactically_valid(*import_target):
                continue
            module, class_name = import_target
            try:
                abi_json = json.dumps(_signature_payload(sig), sort_keys=True)
                abi_hash = hashlib.sha256(abi_json.encode()).hexdigest()
                signature_payload = _complete_signature_payload(sig)
                sig_json = json.dumps(signature_payload, sort_keys=True)
                metadata_payload = _complete_metadata_payload(meta)
                meta_json = json.dumps(metadata_payload, sort_keys=True)
                if (
                    _complete_signature_payload(_signature_from_payload(signature_payload))
                    != signature_payload
                    or _complete_metadata_payload(_metadata_from_payload(metadata_payload))
                    != metadata_payload
                ):
                    continue
                semantic_hash = _semantic_snapshot_hash(
                    fqn=fqn,
                    signature_payload=signature_payload,
                    metadata_payload=metadata_payload,
                    module=module,
                    qualname=class_name,
                    abi_hash=abi_hash,
                )
            except (TypeError, ValueError):
                continue

            rows.append((fqn, module, class_name, sig_json, abi_hash, meta_json, now))
            catalog_hash_parts.append(semantic_hash)

        catalog_hash = hashlib.sha256("|".join(sorted(catalog_hash_parts)).encode()).hexdigest()

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
        if not self.is_cache_valid():
            return 0

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
                    return _resolve_import_target(mod, cls)

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

        The stored row set is always checked for complete typed round-trip and
        against its snapshot hash. Without *registry* this proves integrity,
        not source currentness. Supplying the live registry also compares the
        semantic source catalog to detect drift before the snapshot is used.
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

                stored = conn.execute(
                    "SELECT value FROM _meta WHERE key = 'catalog_hash'"
                ).fetchone()
                if stored is None:
                    return False

                persisted_hash = self._compute_stored_catalog_hash(conn)
                if persisted_hash is None or stored[0] != persisted_hash:
                    return False
                if registry is None:
                    return True
                return stored[0] == self._compute_catalog_hash(registry)
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
        """Compute a complete semantic snapshot hash for persistable entries."""
        parts: list[str] = []
        snapshot = registry.snapshot()
        for entry in snapshot.entries():
            import_target = entry.persistable_import_target
            if import_target is None or not _is_import_target_syntactically_valid(*import_target):
                continue
            module, qualname = import_target
            try:
                abi_json = json.dumps(_signature_payload(entry.signature), sort_keys=True)
                abi_hash = hashlib.sha256(abi_json.encode()).hexdigest()
                parts.append(
                    _semantic_snapshot_hash(
                        fqn=entry.fqn,
                        signature_payload=_complete_signature_payload(entry.signature),
                        metadata_payload=_complete_metadata_payload(entry.metadata),
                        module=module,
                        qualname=qualname,
                        abi_hash=abi_hash,
                    )
                )
            except (TypeError, ValueError):
                continue
        return hashlib.sha256("|".join(sorted(parts)).encode()).hexdigest()

    @staticmethod
    def _compute_stored_catalog_hash(conn: sqlite3.Connection) -> str | None:
        """Recompute the snapshot fingerprint from persisted SQLite rows."""
        rows = conn.execute(
            "SELECT fqn, module, class_name, signature_json, signature_hash, metadata_json "
            "FROM method_entries ORDER BY fqn"
        ).fetchall()
        parts: list[str] = []
        for fqn, module, qualname, signature_json, abi_hash, metadata_json in rows:
            try:
                signature_payload = json.loads(signature_json)
                metadata_payload = json.loads(metadata_json)
                if not _is_import_target_syntactically_valid(module, qualname):
                    return None

                # Decode then re-encode so every required field and typed value
                # is present before a persisted fingerprint can be trusted.
                signature = _signature_from_payload(signature_payload)
                metadata = _metadata_from_payload(metadata_payload)
                if (
                    _complete_signature_payload(signature) != signature_payload
                    or _complete_metadata_payload(metadata) != metadata_payload
                ):
                    return None

                expected_fqn = signature.fqn
                expected_abi_hash = hashlib.sha256(
                    json.dumps(_signature_payload(signature), sort_keys=True).encode()
                ).hexdigest()
                if fqn != expected_fqn or abi_hash != expected_abi_hash:
                    return None
                parts.append(
                    _semantic_snapshot_hash(
                        fqn=fqn,
                        signature_payload=signature_payload,
                        metadata_payload=metadata_payload,
                        module=module,
                        qualname=qualname,
                        abi_hash=abi_hash,
                    )
                )
            except (KeyError, TypeError, ValueError, IndexError, OverflowError):
                return None
        return hashlib.sha256("|".join(sorted(parts)).encode()).hexdigest()


def _signature_payload(signature) -> dict[str, Any]:
    """Serialize the legacy ABI projection without changing its digest bytes."""
    return signature._stable_dict()


def _complete_signature_payload(signature) -> dict[str, Any]:
    """Serialize complete signature semantics separately from the legacy ABI."""
    payload = _signature_payload(signature)
    # The stable ABI intentionally omits the default JAX backend. The semantic
    # cache snapshot records every dataclass field, including that default.
    payload["backend"] = signature.backend.value
    payload["representation_profiles"] = [
        p._stable_dict() for p in signature.representation_profiles
    ]
    payload["patch_targets"] = [contract._stable_dict() for contract in signature.patch_targets]
    for field_name, slots in (
        ("input_slots", signature.input_slots),
        ("output_slots", signature.output_slots),
    ):
        slots_by_name = {slot.name: slot for slot in slots}
        for slot_payload in payload[field_name]:
            slot = slots_by_name[slot_payload["name"]]
            slot_payload["shape"] = [
                {"__dimvar__": dim.name} if _is_dim_var(dim) else dim for dim in slot.shape
            ]
            slot_payload["bounds"] = list(slot.bounds)
            slot_payload["description"] = slot.description
            slot_payload["contract_capabilities"] = sorted(
                capability.value for capability in slot.contract_capabilities
            )
            slot_payload["contract_owner"] = slot.contract_owner
    parameters_by_name = {item.name: item for item in signature.parameters}
    for parameter_payload in payload["parameters"]:
        parameter = parameters_by_name[parameter_payload["name"]]
        parameter_payload["description"] = parameter.description
    return payload


def _semantic_snapshot_hash(
    *,
    fqn: str,
    signature_payload: dict[str, Any],
    metadata_payload: dict[str, Any],
    module: str,
    qualname: str,
    abi_hash: str,
) -> str:
    """Bind complete persisted semantics and the declared import target."""
    payload = {
        "codec_version": _SEMANTIC_SNAPSHOT_VERSION,
        "fqn": fqn,
        "signature": signature_payload,
        "metadata": metadata_payload,
        "import_target": {"module": module, "qualname": qualname},
        "abi_hash": abi_hash,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode()).hexdigest()


def _metadata_payload(metadata) -> dict[str, Any]:
    """Serialize metadata using its stable, JSON-safe payload."""
    return metadata._stable_dict()


def _complete_metadata_payload(metadata) -> dict[str, Any]:
    """Serialize all metadata fields without changing its legacy stable digest."""
    from polisyos.foundry.methods.base import MethodContracts

    payload = _metadata_payload(metadata)
    contracts = metadata.contracts
    if contracts is not None and not isinstance(contracts, MethodContracts):
        raise TypeError("MethodMetadata.contracts must be MethodContracts or None")
    payload["contracts"] = (
        None
        if contracts is None
        else {
            "preconditions": list(contracts.preconditions),
            "postconditions": list(contracts.postconditions),
            "invariants": list(contracts.invariants),
        }
    )
    return payload


def _is_dim_var(value: Any) -> bool:
    from polisyos.foundry.methods.base import DimVar

    return isinstance(value, DimVar)


def _dim_from_payload(value: Any) -> int | str | None:
    if isinstance(value, dict) and set(value) == {"__dimvar__"}:
        from polisyos.foundry.methods.base import DimVar

        return DimVar(str(value["__dimvar__"]))
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
    from polisyos.ir.analytics.uncertainty import OutputContractCapability

    return SlotSpec(
        name=str(payload["name"]),
        slot_type=SlotType[str(payload["slot_type"])],
        unit=_unit_from_payload(payload["unit"]),
        contract_id=payload.get("contract_id"),
        contract_capabilities=frozenset(
            OutputContractCapability(str(item)) for item in payload.get("contract_capabilities", ())
        ),
        contract_owner=payload.get("contract_owner"),
        shape=tuple(_dim_from_payload(item) for item in payload.get("shape", [])),
        description=str(payload.get("description", "")),
        bounds=tuple(_restore_stable_value(payload.get("bounds", (None, None)))),
    )


def _parameter_from_payload(payload: dict[str, Any]):
    from polisyos.foundry.methods.base import ParameterSpec

    bounds = payload.get("bounds", (None, None))
    return ParameterSpec(
        name=str(payload["name"]),
        default=_restore_stable_value(payload.get("default")),
        is_static=bool(payload.get("is_static", False)),
        bounds=tuple(_restore_stable_value(bounds)),
        description=str(payload.get("description", "")),
    )


def _signature_from_payload(payload: dict[str, Any]):
    from polisyos.foundry.methods.base import (
        ComplexityClass,
        ComputeBackend,
        FidelityLevel,
        MethodKind,
        MethodPatchTargetContract,
        MethodRepresentationProfile,
        MethodSignature,
    )
    from polisyos.ir import IdentificationMode

    if "representation_profiles" not in payload:
        raise ValueError("cache_signature_representation_profiles_missing")
    profiles = tuple(
        MethodRepresentationProfile(
            **{**row, "identification_mode": IdentificationMode(row["identification_mode"])}
        )
        for row in payload["representation_profiles"]
    )
    fidelity_tier = payload.get("fidelity_tier")
    return MethodSignature(
        name=str(payload["name"]),
        namespace=str(payload["namespace"]),
        version=str(payload["version"]),
        input_slots=frozenset(_slot_from_payload(item) for item in payload.get("input_slots", [])),
        output_slots=frozenset(
            _slot_from_payload(item) for item in payload.get("output_slots", [])
        ),
        parameters=tuple(_parameter_from_payload(item) for item in payload.get("parameters", [])),
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
        representation_profiles=profiles,
        patch_targets=tuple(
            MethodPatchTargetContract(**row) for row in payload.get("patch_targets", ())
        ),
    )


def _metadata_from_payload(payload: dict[str, Any]):
    from polisyos.core.observability import DeterminismTier
    from polisyos.foundry.methods.base import MethodContracts, MethodMetadata, SideEffectProfile

    determinism_tier = payload.get("determinism_tier")
    contracts_payload = payload.get("contracts")
    if "contracts" not in payload:
        raise ValueError("cache_metadata_contracts_missing")
    contracts = None
    if contracts_payload is not None:
        if not isinstance(contracts_payload, dict) or set(contracts_payload) != {
            "preconditions",
            "postconditions",
            "invariants",
        }:
            raise ValueError("cache_metadata_contracts_invalid")
        contracts = MethodContracts(
            preconditions=tuple(contracts_payload["preconditions"]),
            postconditions=tuple(contracts_payload["postconditions"]),
            invariants=tuple(contracts_payload["invariants"]),
        )
    return MethodMetadata(
        description=str(payload.get("description", "")),
        tags=frozenset(payload.get("tags", [])),
        citations=tuple(payload.get("citations", [])),
        equations=dict(_restore_stable_value(payload.get("equations", {}))),
        assumptions=dict(_restore_stable_value(payload.get("assumptions", {}))),
        simulator_regime_schema=dict(
            _restore_stable_value(payload.get("simulator_regime_schema", {}))
        ),
        summary_schema_ref=payload.get("summary_schema_ref"),
        identifiable_target=dict(_restore_stable_value(payload.get("identifiable_target", {}))),
        coverage_contract=dict(_restore_stable_value(payload.get("coverage_contract", {}))),
        diagnostic_contract=dict(_restore_stable_value(payload.get("diagnostic_contract", {}))),
        determinism_tier=(
            DeterminismTier(str(determinism_tier)) if determinism_tier is not None else None
        ),
        declared_truthfulness_tier=payload.get("declared_truthfulness_tier"),
        truthfulness_scope=payload.get("truthfulness_scope"),
        required_deps=tuple(payload.get("required_deps", [])),
        optional_deps=tuple(payload.get("optional_deps", [])),
        fallback_policy=str(payload.get("fallback_policy", "none")),
        side_effect_profile=SideEffectProfile(
            str(payload.get("side_effect_profile", SideEffectProfile.NONE.value))
        ),
        contracts=contracts,
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
            return {str(key): _restore_stable_value(item) for key, item in value["__map__"].items()}
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
        return value
    return value
