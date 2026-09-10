"""Disposable bounded storage for the existing academic graph projection owners.

This module stores rows and mutable aggregates; it neither admits evidence nor
defines graph formulas. Successful editor scopes explicitly persist nested
mutations. Interrupted builds are rebuilt by their orchestration owner.
"""

# The private tagged codec accepts heterogeneous owner data, including registered
# dataclasses. Its runtime tag whitelist is the boundary, not a public DTO.
# ruff: noqa: ANN401

from __future__ import annotations

import json
import sqlite3
from collections import Counter, defaultdict
from contextlib import contextmanager
from dataclasses import asdict, dataclass, fields, is_dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any
from uuid import uuid4

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Iterator, Mapping
    from typing import Literal, TextIO

    import duckdb


@dataclass(frozen=True)
class GraphCapacityLimits:
    """Finite operational budgets; none limits the number of corpus records.

    Aggregate byte admission reserves serialized incoming contributions before
    decoding existing state, and also checks the resulting serialized payload.
    Reservation is conservative accounting, not a canonical evidence count.
    """

    max_record_bytes: int = 8 * 1024 * 1024
    max_auxiliary_rows_per_work: int = 100_000
    max_group_contributions: int = 100_000
    max_group_bytes: int = 64 * 1024 * 1024
    max_pair_contributions: int = 200_000
    max_pair_bytes: int = 128 * 1024 * 1024
    max_batch_rows: int = 1_000
    max_batch_bytes: int = 8 * 1024 * 1024
    max_resolver_vocabulary_bytes: int = 16 * 1024 * 1024
    max_resolver_vocabulary_entries: int = 100_000
    sqlite_cache_bytes: int = 4 * 1024 * 1024
    duckdb_memory_bytes: int = 256 * 1024 * 1024
    max_disk_bytes: int = 16 * 1024 * 1024 * 1024

    def __post_init__(self) -> None:
        for field in fields(self):
            value = getattr(self, field.name)
            if type(value) is not int or value <= 0:
                raise ValueError(f"{field.name} must be a positive integer")

    def check(self, limit: str, identity: object, observed: int) -> None:
        """Refuse a measured quantity exceeding its effective operational budget."""
        maximum = int(getattr(self, limit))
        if observed > maximum:
            raise GraphCapacityError(limit, identity, observed, maximum)


class GraphCapacityError(RuntimeError):
    """Identify an operational refusal without dropping any evidence contribution."""

    def __init__(
        self,
        limit: str,
        identity: object,
        observed: int,
        maximum: int,
        *,
        reason: str = "limit_exceeded",
    ) -> None:
        self.limit = limit
        self.identity = identity
        self.observed = observed
        self.maximum = maximum
        self.reason = reason
        super().__init__(f"{limit}: {identity!r}: observed {observed}, maximum {maximum}; {reason}")


def measure_owned_output_bytes(paths: Iterable[Path]) -> int:
    """Measure the complete owned file set, deduplicating nested roots in any order."""
    roots: list[Path] = []
    for path in paths:
        root = path.resolve()
        if any(root == prior or root.is_relative_to(prior) for prior in roots):
            continue
        roots = [prior for prior in roots if not prior.is_relative_to(root)]
        roots.append(root)
    size = 0
    for root in roots:
        if root.is_file():
            size += root.stat().st_size
        elif root.exists():
            for path in root.rglob("*"):
                if path.is_file():
                    size += path.stat().st_size
    return size


def enforce_owned_output_budget(
    paths: Iterable[Path],
    limits: GraphCapacityLimits,
    *,
    additional_bytes: int = 0,
) -> int:
    """Check actual complete output bytes plus a prospective bounded write."""
    if type(additional_bytes) is not int or additional_bytes < 0:
        raise ValueError("additional_bytes must be a nonnegative integer")
    owned = tuple(paths)
    measured = measure_owned_output_bytes(owned)
    limits.check("max_disk_bytes", owned, measured + additional_bytes)
    return measured


def publish_owned_output(
    path: Path,
    producer: Callable[[Path], object],
    *,
    paths: Iterable[Path],
    limits: GraphCapacityLimits,
    temporary_root: Path,
) -> Path:
    """Run an unchanged writer privately and check actual bytes before publication."""
    from polisyos.data_forge.kernel.io import atomic_commit_path

    owned = (*paths, temporary_root, path)
    enforce_owned_output_budget(owned, limits)
    temporary_root.mkdir(parents=True, exist_ok=True)
    private = temporary_root / f"output-{uuid4().hex}{path.suffix}"
    producer(private)
    enforce_owned_output_budget(owned, limits)
    atomic_commit_path(private, path)
    enforce_owned_output_budget(owned, limits)
    return path


class StagingStore:
    """Own a disk spool, its bounded SQLite cache, and explicitly registered codecs."""

    def __init__(
        self,
        path: Path,
        limits: GraphCapacityLimits,
        *,
        source_provenance: dict[str, object] | None = None,
    ) -> None:
        synthetic = (source_provenance or {}).get("synthetic")
        if synthetic is not None and type(synthetic) is not bool:
            raise ValueError("staging source synthetic marker must be boolean or unknown")
        self.path = path
        self.limits = limits
        self._types: dict[str, type] = {}
        self._database_paths: tuple[Path, ...] = ()
        self._output_paths: tuple[Path, ...] = ()
        path.parent.mkdir(parents=True, exist_ok=True)
        self.con = sqlite3.connect(path, isolation_level=None)
        try:
            self._initialize(source_provenance, synthetic)
            self.check_disk()
        except sqlite3.OperationalError as exc:
            self.con.close()
            self._translate_sqlite_error(exc)
        except Exception:
            self.con.close()
            raise

    def _initialize(
        self, source_provenance: dict[str, object] | None, synthetic: bool | None
    ) -> None:
        self.con.execute("PRAGMA journal_mode=DELETE")
        self.con.execute("PRAGMA synchronous=FULL")
        self.con.execute("PRAGMA temp_store=FILE")
        self.con.execute(f"PRAGMA cache_size=-{max(1, self.limits.sqlite_cache_bytes // 1024)}")
        page_size = int(self.con.execute("PRAGMA page_size").fetchone()[0])
        self.con.execute(f"PRAGMA max_page_count={max(1, self.limits.max_disk_bytes // page_size)}")
        self.con.executescript("""
            CREATE TABLE IF NOT EXISTS spool_rows (
                ordinal INTEGER PRIMARY KEY AUTOINCREMENT,
                namespace TEXT NOT NULL, payload TEXT NOT NULL, size INTEGER NOT NULL,
                sort_rank REAL, sort_a TEXT, sort_b TEXT
            );
            CREATE INDEX IF NOT EXISTS spool_rows_namespace
                ON spool_rows(namespace, ordinal);
            CREATE INDEX IF NOT EXISTS spool_rows_order
                ON spool_rows(namespace, sort_rank, sort_a, sort_b, ordinal);
            CREATE TABLE IF NOT EXISTS spool_values (
                ordinal INTEGER PRIMARY KEY AUTOINCREMENT,
                namespace TEXT NOT NULL, identity TEXT NOT NULL, payload TEXT NOT NULL,
                contributions INTEGER NOT NULL, reserved_bytes INTEGER NOT NULL,
                size INTEGER NOT NULL, sort_a TEXT, sort_b TEXT, sort_c TEXT,
                UNIQUE(namespace, identity)
            );
            CREATE INDEX IF NOT EXISTS spool_values_order
                ON spool_values(namespace, sort_a, sort_b, sort_c);
            CREATE TABLE IF NOT EXISTS spool_usage (
                metric TEXT PRIMARY KEY, value INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS spool_namespaces (
                namespace TEXT PRIMARY KEY, kind TEXT NOT NULL,
                writes INTEGER NOT NULL DEFAULT 0, batches INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS spool_configuration (
                name TEXT PRIMARY KEY, value_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS spool_metadata (
                singleton INTEGER PRIMARY KEY CHECK(singleton=1),
                synthetic BOOLEAN,
                authority TEXT NOT NULL CHECK(authority='candidate_only'),
                source_provenance_json TEXT NOT NULL
            );
        """)
        self.con.execute(
            "INSERT OR IGNORE INTO spool_metadata VALUES(1,?,'candidate_only',?)",
            (synthetic, json.dumps(source_provenance, ensure_ascii=False)),
        )
        self.observe_provenance(source_provenance)
        self.configure("applied_limits", asdict(self.limits))
        self.configure(
            "sqlite_cache_kib", abs(int(self.con.execute("PRAGMA cache_size").fetchone()[0]))
        )
        self.configure(
            "sqlite_max_page_count", int(self.con.execute("PRAGMA max_page_count").fetchone()[0])
        )
        self.con.execute(
            "INSERT OR REPLACE INTO spool_usage(metric,value) VALUES(?,?)",
            ("sqlite_cache_kib", abs(int(self.con.execute("PRAGMA cache_size").fetchone()[0]))),
        )

    def __enter__(self) -> StagingStore:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def close(self) -> None:
        """Close the disposable store, retaining successfully committed scopes."""
        self.con.close()

    def reset(self) -> None:
        """Discard build state before a complete replay of durable input records."""
        self.con.executescript(
            "DELETE FROM spool_rows; DELETE FROM spool_values; "
            "DELETE FROM spool_namespaces; "
            "DELETE FROM spool_usage WHERE metric != 'sqlite_cache_kib';"
        )

    def register_type(self, cls: type) -> None:
        """Allow an owner's data-only dataclass codec; never import a stored class."""
        if not is_dataclass(cls):
            raise TypeError("graph staging codecs require dataclasses")
        self._types[f"{cls.__module__}.{cls.__qualname__}"] = cls

    def _pack(self, value: Any) -> Any:
        if isinstance(value, Counter):
            return ["counter", [[self._pack(k), self._pack(v)] for k, v in value.items()]]
        if isinstance(value, defaultdict):
            if value.default_factory is not list:
                raise TypeError("only list-valued default dictionaries are supported")
            return ["default_list", [[self._pack(k), self._pack(v)] for k, v in value.items()]]
        if isinstance(value, dict):
            return ["dict", [[self._pack(k), self._pack(v)] for k, v in value.items()]]
        if isinstance(value, (list, tuple, set)):
            return [type(value).__name__, [self._pack(item) for item in value]]
        if is_dataclass(value) and not isinstance(value, type):
            name = f"{type(value).__module__}.{type(value).__qualname__}"
            if self._types.get(name) is not type(value):
                raise TypeError(f"unregistered graph staging type: {name}")
            return [
                "record",
                name,
                self._pack({f.name: getattr(value, f.name) for f in fields(value)}),
            ]
        if value is None or isinstance(value, (str, bool, int, float)):
            return ["scalar", value]
        raise TypeError(f"unsupported graph staging value: {type(value).__name__}")

    def _unpack(self, value: Any) -> Any:
        tag = value[0]
        if tag == "scalar":
            return value[1]
        if tag in {"dict", "counter", "default_list"}:
            pairs = ((self._unpack(k), self._unpack(v)) for k, v in value[1])
            if tag == "counter":
                return Counter(dict(pairs))
            if tag == "default_list":
                return defaultdict(list, pairs)
            return dict(pairs)
        if tag in {"list", "tuple", "set"}:
            values = (self._unpack(item) for item in value[1])
            return {"list": list, "tuple": tuple, "set": set}[tag](values)
        if tag == "record" and value[1] in self._types:
            return self._types[value[1]](**self._unpack(value[2]))
        raise ValueError("unknown graph staging codec tag")

    def encode(self, value: Any) -> str:
        """Preserve types, insertion order, absent keys and null values as data."""
        return json.dumps(self._pack(value), ensure_ascii=False, separators=(",", ":"))

    def decode(self, value: str) -> Any:
        """Decode only the explicit data codec and owner-registered value types."""
        return self._unpack(json.loads(value))

    def encoded_size(self, value: Any) -> int:
        """Measure the actual UTF-8 storage representation."""
        return len(self.encode(value).encode("utf-8"))

    def check(self, limit: str, identity: object, observed: int) -> None:
        """Refuse a measured quantity that exceeds its declared operational bound."""
        self.limits.check(limit, identity, observed)

    def check_record(self, value: Any, identity: object) -> None:
        """Bound one supplied input and its nested auxiliary collection entries."""
        self.check("max_record_bytes", identity, self.encoded_size(value))
        self.observe_provenance(value)
        count = 0
        pending = [value]
        while pending:
            item = pending.pop()
            if isinstance(item, dict):
                pending.extend(item.values())
            elif isinstance(item, (list, tuple, set)):
                count += len(item)
                self.check("max_auxiliary_rows_per_work", identity, count)
                pending.extend(item)

    def observe_provenance(self, value: Any, *, strict: bool = False) -> None:
        """Mark actual constructed ancestry before a derivative enters any row family."""
        pending = [value]
        while pending:
            item = pending.pop()
            if isinstance(item, dict):
                if strict and "synthetic" in item:
                    marker = item["synthetic"]
                    if marker is not None and type(marker) is not bool:
                        raise ValueError("graph_source_provenance_malformed_boolean")
                if item.get("synthetic") is True:
                    self.con.execute("UPDATE spool_metadata SET synthetic=TRUE WHERE singleton=1")
                    if not strict:
                        return
                pending.extend(item.values())
            elif isinstance(item, (tuple, list, set)):
                pending.extend(item)

    def provenance(self) -> dict[str, object]:
        """Read this store's monotone provenance for derived candidate artifacts."""
        synthetic, authority = self.con.execute(
            "SELECT synthetic,authority FROM spool_metadata WHERE singleton=1",
        ).fetchone()
        return {"synthetic": None if synthetic is None else bool(synthetic), "authority": authority}

    def check_disk(self, *additional_paths: Path, additional_bytes: int = 0) -> None:
        """Measure owned spool/database files without retaining a corpus-sized listing."""
        enforce_owned_output_budget(
            (self.path.parent, *self._database_paths, *self._output_paths, *additional_paths),
            self.limits,
            additional_bytes=additional_bytes,
        )

    def track_outputs(self, *paths: Path) -> None:
        """Include every detached owner output in the common byte budget."""
        self._output_paths = tuple(dict.fromkeys((*self._output_paths, *paths)))
        self.check_disk()

    @contextmanager
    def text_output(self, path: Path) -> Iterator[_BoundedTextOutput]:
        """Write UTF-8 output through the common prospective-byte boundary."""
        self.track_outputs(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="") as stream:
            yield _BoundedTextOutput(self, stream)

    def publish_output(self, path: Path, producer: Callable[[Path], object]) -> Path:
        """Check the actual private artifact before exposing its completion path."""
        self.track_outputs(path)
        return publish_owned_output(
            path,
            producer,
            paths=(self.path.parent, *self._database_paths, *self._output_paths),
            limits=self.limits,
            temporary_root=self.path.parent,
        )

    def track_database(self, path: Path) -> None:
        """Include the owned main database and its WAL in shared disk enforcement."""
        self._database_paths = (path, Path(str(path) + ".wal"))
        self.check_disk()

    def write(self, sql: str, params: tuple[Any, ...]) -> None:
        """Write under SQLite's page cap and translate disk exhaustion to a refusal."""
        try:
            self.con.execute(sql, params)
            self.check_disk()
        except sqlite3.OperationalError as exc:
            self._translate_sqlite_error(exc)

    def _translate_sqlite_error(self, exc: sqlite3.OperationalError) -> None:
        if getattr(exc, "sqlite_errorcode", None) == sqlite3.SQLITE_FULL:
            raise GraphCapacityError(
                "max_disk_bytes",
                self.path,
                self.path.stat().st_size,
                self.limits.max_disk_bytes,
                reason="sqlite_disk_allocation_refused",
            ) from exc
        raise exc

    def observe(self, metric: str, amount: int, *, maximum: bool = False) -> None:
        """Retain fixed-size operational counters from successful storage operations."""
        update = "MAX(value,excluded.value)" if maximum else "value+excluded.value"
        self.write(
            "INSERT INTO spool_usage(metric,value) VALUES(?,?) "
            f"ON CONFLICT(metric) DO UPDATE SET value={update}",
            (metric, amount),
        )

    def configure(self, name: str, value: Any) -> None:
        """Persist an effective capacity input or actual engine setting readback."""
        self.write(
            "INSERT OR REPLACE INTO spool_configuration VALUES(?,?)",
            (name, json.dumps(value, ensure_ascii=False)),
        )

    def _register_namespace(self, namespace: str, kind: str) -> None:
        self.write(
            "INSERT OR IGNORE INTO spool_namespaces(namespace,kind) VALUES(?,?)",
            (namespace, kind),
        )
        actual = self.con.execute(
            "SELECT kind FROM spool_namespaces WHERE namespace=?",
            (namespace,),
        ).fetchone()[0]
        if actual != kind:
            raise ValueError("graph staging namespace kind cannot change")

    def observe_namespace(self, namespace: str, *, batch: bool = False) -> None:
        """Count a completed write or yielded batch at the common storage seams."""
        column = "batches" if batch else "writes"
        self.write(
            f"UPDATE spool_namespaces SET {column}={column}+1 WHERE namespace=?",  # noqa: S608 - column chosen from two literals above.
            (namespace,),
        )

    def rows(self, namespace: str) -> RowSpool:
        """Open an insertion-ordered disk row family."""
        self._register_namespace(namespace, "rows")
        return RowSpool(self, namespace)

    def groups(self, namespace: str, *, pair: bool = False) -> DiskGroups:
        """Open aggregates that require explicit nested edit scopes."""
        self._register_namespace(namespace, "pairs" if pair else "groups")
        return DiskGroups(self, namespace, pair=pair)

    def values(self, namespace: str) -> DiskValues:
        """Open read/copy/write values; mutable aggregation must use groups.edit."""
        self._register_namespace(namespace, "values")
        return DiskValues(self, namespace)

    def counts(self, namespace: str) -> DiskCounts:
        """Open scalar counts without a resident key dictionary."""
        self._register_namespace(namespace, "counts")
        return DiskCounts(self, namespace)


class _BoundedTextOutput:
    """Minimal text writer for JSON output under the common disk budget."""

    def __init__(self, store: StagingStore, stream: TextIO) -> None:
        self.store = store
        self.stream = stream

    def write(self, text: str) -> int:
        size = len(text.encode("utf-8"))
        self.store.check("max_record_bytes", "output write", size)
        self.store.check_disk(additional_bytes=size)
        written = self.stream.write(text)
        self.stream.flush()
        self.store.check_disk()
        return written


class RowSpool:
    """Append rows on disk and iterate with both byte and row-count bounds."""

    def __init__(self, store: StagingStore, namespace: str) -> None:
        self.store = store
        self.namespace = namespace

    def append(self, row: Any, *, sort_key: tuple[float, str, str] | None = None) -> None:
        self.store.observe_provenance(row)
        payload = self.store.encode(row)
        size = len(payload.encode("utf-8"))
        self.store.check("max_record_bytes", self.namespace, size)
        self.store.check("max_batch_bytes", self.namespace, size)
        self.store.write(
            "INSERT INTO spool_rows(namespace,payload,size,sort_rank,sort_a,sort_b) "
            "VALUES(?,?,?,?,?,?)",
            (self.namespace, payload, size, *(sort_key or (None, None, None))),
        )
        self.store.observe("row_appends", 1)
        self.store.observe_namespace(self.namespace)
        self.store.observe("max_row_bytes", size, maximum=True)

    def __len__(self) -> int:
        return self.count()

    def count(self) -> int:
        return int(
            self.store.con.execute(
                "SELECT COUNT(*) FROM spool_rows WHERE namespace=?",
                (self.namespace,),
            ).fetchone()[0]
        )

    def clear(self) -> None:
        self.store.write("DELETE FROM spool_rows WHERE namespace=?", (self.namespace,))

    def __iter__(self) -> Iterator[Any]:
        for batch in self.iter_batches():
            yield from batch

    def iter_batches(
        self, batch_size: int | None = None, *, sorted_rows: bool = False
    ) -> Iterator[list[Any]]:
        limit = min(
            batch_size or self.store.limits.max_batch_rows, self.store.limits.max_batch_rows
        )
        if limit <= 0:
            raise ValueError("batch_size must be positive")
        order = "sort_rank,sort_a,sort_b,ordinal" if sorted_rows else "ordinal"
        cursor = self.store.con.execute(
            f"SELECT payload,size FROM spool_rows WHERE namespace=? ORDER BY {order}",  # noqa: S608 - sort columns chosen from two literals above.
            (self.namespace,),
        )
        batch: list[Any] = []
        size = 0
        for payload, row_size in cursor:
            if batch and (
                len(batch) >= limit or size + row_size > self.store.limits.max_batch_bytes
            ):
                self.store.observe("max_batch_bytes", size, maximum=True)
                self.store.observe("max_batch_rows", len(batch), maximum=True)
                self.store.observe_namespace(self.namespace, batch=True)
                yield batch
                batch = []
                size = 0
            batch.append(self.store.decode(payload))
            size += row_size
        if batch:
            self.store.observe("max_batch_bytes", size, maximum=True)
            self.store.observe("max_batch_rows", len(batch), maximum=True)
            self.store.observe_namespace(self.namespace, batch=True)
            yield batch


class DiskValues:
    """Persist values with first-seen order; reads return detached copies."""

    def __init__(self, store: StagingStore, namespace: str) -> None:
        self.store = store
        self.namespace = namespace

    def __len__(self) -> int:
        return int(
            self.store.con.execute(
                "SELECT COUNT(*) FROM spool_values WHERE namespace=?",
                (self.namespace,),
            ).fetchone()[0]
        )

    def __contains__(self, key: Any) -> bool:
        return (
            self.store.con.execute(
                "SELECT 1 FROM spool_values WHERE namespace=? AND identity=?",
                (self.namespace, self.store.encode(key)),
            ).fetchone()
            is not None
        )

    def get(self, key: Any, default: Any = None) -> Any:
        row = self.store.con.execute(
            "SELECT payload FROM spool_values WHERE namespace=? AND identity=?",
            (self.namespace, self.store.encode(key)),
        ).fetchone()
        return self.store.decode(row[0]) if row is not None else default

    def __getitem__(self, key: Any) -> Any:
        if key not in self:
            raise KeyError(key)
        return self.get(key)

    def __setitem__(self, key: Any, value: Any) -> None:
        self.store.observe_provenance(value)
        payload = self.store.encode(value)
        self.store.check("max_record_bytes", key, len(payload.encode("utf-8")))
        self._put(key, payload, 0, 0)

    def _put(self, key: Any, payload: str, contributions: int, reserved_bytes: int) -> None:
        parts = key if isinstance(key, tuple) else (key,)
        sort_parts = tuple(str(value) for value in parts[:3])
        sort_parts += ("",) * (3 - len(sort_parts))
        self.store.write(
            "INSERT INTO spool_values(namespace,identity,payload,contributions,reserved_bytes,"
            "size,sort_a,sort_b,sort_c) VALUES(?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(namespace,identity) DO UPDATE SET payload=excluded.payload,"
            "contributions=excluded.contributions,reserved_bytes=excluded.reserved_bytes,"
            "size=excluded.size",
            (
                self.namespace,
                self.store.encode(key),
                payload,
                contributions,
                reserved_bytes,
                len(payload.encode("utf-8")),
                *sort_parts,
            ),
        )
        self.store.observe_namespace(self.namespace)

    def setdefault(self, key: Any, default: Any) -> Any:
        if key not in self:
            self[key] = default
        return self[key]

    def add(self, key: Any) -> None:
        self.setdefault(key, True)

    def iter_items(self, *, order: str = "first_seen") -> Iterator[tuple[Any, Any]]:
        if order not in {"first_seen", "key"}:
            raise ValueError("unknown staging order")
        ordering = "ordinal" if order == "first_seen" else "sort_a,sort_b,sort_c"
        cursor = self.store.con.execute(
            f"SELECT identity,payload FROM spool_values WHERE namespace=? ORDER BY {ordering}",  # noqa: S608 - sort columns chosen from two literals above.
            (self.namespace,),
        )
        for key, value in cursor:
            yield self.store.decode(key), self.store.decode(value)

    def items(self) -> Iterator[tuple[Any, Any]]:
        return self.iter_items()


class DiskCounts(DiskValues):
    """Counter-compatible scalar reads/writes without resident corpus identities."""

    def __getitem__(self, key: Any) -> int:
        return int(self.get(key, 0))

    def increment(self, key: Any, amount: int = 1) -> None:
        self[key] = self[key] + amount


class DiskGroups(DiskValues):
    """Commit nested mutable aggregate edits only after a successful scope."""

    def __init__(self, store: StagingStore, namespace: str, *, pair: bool = False) -> None:
        super().__init__(store, namespace)
        self.pair = pair

    @contextmanager
    def edit(
        self,
        key: Any,
        default_factory: Callable[[], Any],
        *,
        contribution: Any,
        contribution_delta: int = 1,
    ) -> Iterator[Any]:
        if contribution_delta < 0:
            raise ValueError("aggregate contribution delta must be nonnegative")
        count_limit = "max_pair_contributions" if self.pair else "max_group_contributions"
        byte_limit = "max_pair_bytes" if self.pair else "max_group_bytes"
        # Read quantities first: refusal must precede both decode and nested growth.
        row = self.store.con.execute(
            "SELECT contributions,reserved_bytes,size FROM spool_values "
            "WHERE namespace=? AND identity=?",
            (self.namespace, self.store.encode(key)),
        ).fetchone()
        count = (int(row[0]) if row else 0) + contribution_delta
        incoming = self.store.encoded_size(contribution)
        reserved = (max(int(row[1]), int(row[2])) if row else 0) + incoming
        self.store.check(count_limit, key, count)
        self.store.check(byte_limit, key, reserved)
        payload = self.get(key) if row else default_factory()
        yield payload
        encoded = self.store.encode(payload)
        self.store.check(byte_limit, key, len(encoded.encode("utf-8")))
        self.store.observe_provenance(payload)
        self._put(key, encoded, count, reserved)
        self.store.observe("aggregate_edits", 1)


def execute_rows(con: duckdb.DuckDBPyConnection, sql: str, rows: RowSpool) -> None:
    """Execute bounded batches through the existing projection SQL."""
    for batch in rows.iter_batches():
        con.executemany(sql, batch)
        rows.store.check_disk()


def observe_stored_source_provenance(
    con: duckdb.DuckDBPyConnection,
    sources: Mapping[str, Mapping[str, Literal["boolean", "json"]]],
    *,
    store: StagingStore,
) -> None:
    """Read writer-owned provenance codecs before any lossy graph projection.

    The semantic owner supplies its reconciled source-family/codec contract.
    Field spelling is never used to infer a codec. Missing fields and null cells
    remain unknown; malformed present containers refuse, rather than become false.
    Only compact counters are retained, not a duplicate of the database schema.
    """
    for table, codecs in sources.items():
        quoted_table = '"' + table.replace('"', '""') + '"'
        schema = {
            row[0]: row[1]
            for row in query_rows(
                con,
                "SELECT column_name,data_type FROM information_schema.columns "
                "WHERE table_schema=current_schema() AND table_name=? ORDER BY ordinal_position",
                [table],
                store=store,
            )
        }
        store.observe("provenance_source_families", 1)
        if not schema:
            store.observe("provenance_absent_source_families", 1)
            continue
        if not codecs:
            store.observe("provenance_families_without_carriers", 1)
            continue
        available = []
        for column, codec in codecs.items():
            if column not in schema:
                store.observe("provenance_absent_columns", 1)
                continue
            allowed = {"BOOLEAN"} if codec == "boolean" else {"VARCHAR", "JSON"}
            if schema[column] not in allowed:
                raise ValueError("graph_source_provenance_schema_type_mismatch")
            available.append((column, codec))
        if not available:
            continue
        columns = ",".join('"' + column.replace('"', '""') + '"' for column, _ in available)
        sql = f"SELECT {columns} FROM {quoted_table}"  # noqa: S608 - quoted identifiers come from schema-checked owner codec contract.
        for row in query_rows(con, sql, store=store):
            store.observe("provenance_source_rows", 1)
            for value, (_, codec) in zip(row, available, strict=True):
                if value is None:
                    store.observe("provenance_null_cells", 1)
                    continue
                if codec == "boolean":
                    store.observe_provenance({"synthetic": value}, strict=True)
                    continue
                try:
                    parsed = json.loads(value)
                except (TypeError, ValueError) as exc:
                    raise ValueError("graph_source_provenance_malformed_json") from exc
                if parsed is None:
                    store.observe("provenance_null_cells", 1)
                elif not isinstance(parsed, (dict, list)):
                    raise ValueError("graph_source_provenance_malformed_container")
                else:
                    store.observe_provenance(parsed, strict=True)


def query_rows(
    con: duckdb.DuckDBPyConnection, sql: str, parameters: Iterable[Any] = (), *, store: StagingStore
) -> Iterator[tuple[Any, ...]]:
    """Use an independent cursor so nested owner lookups cannot erase a scan."""
    cursor = con.cursor()
    try:
        cursor.execute(sql, list(parameters))
    except Exception:
        cursor.close()
        raise

    def iterate() -> Iterator[tuple[Any, ...]]:
        try:
            while (row := cursor.fetchone()) is not None:
                store.check("max_record_bytes", "query row", store.encoded_size(row))
                yield row
        finally:
            cursor.close()

    return iterate()


def read_staging_usage(path: Path) -> dict[str, object]:
    """Read actual storage counters and complete aggregate quantities without mutation."""
    con = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)
    try:
        result: dict[str, object] = {
            str(name): int(value)
            for name, value in con.execute(
                "SELECT metric,value FROM spool_usage",
            )
        }
        result.setdefault("row_appends", 0)
        result.setdefault("aggregate_edits", 0)
        result["resident_row_count"] = int(
            con.execute("SELECT COUNT(*) FROM spool_rows").fetchone()[0]
        )
        groups, contributions, max_bytes, max_reserved = con.execute(
            "SELECT COUNT(*),COALESCE(SUM(contributions),0),COALESCE(MAX(size),0),"
            "COALESCE(MAX(reserved_bytes),0) FROM spool_values WHERE contributions>0",
        ).fetchone()
        result.update(
            aggregate_groups=int(groups),
            aggregate_contributions=int(contributions),
            max_aggregate_bytes=int(max_bytes),
            max_reserved_bytes=int(max_reserved),
        )
        synthetic, authority = con.execute(
            "SELECT synthetic,authority FROM spool_metadata"
        ).fetchone()
        result.update(synthetic=None if synthetic is None else bool(synthetic), authority=authority)
        configuration = {
            name: json.loads(value)
            for name, value in con.execute(
                "SELECT name,value_json FROM spool_configuration",
            )
        }
        result["applied_limits"] = configuration.pop("applied_limits")
        result["storage_configuration"] = configuration
        result["namespace_operations"] = {
            name: {"kind": kind, "writes": int(writes), "batches": int(batches)}
            for name, kind, writes, batches in con.execute(
                "SELECT namespace,kind,writes,batches FROM spool_namespaces ORDER BY namespace",
            )
        }
        return result
    finally:
        con.close()
