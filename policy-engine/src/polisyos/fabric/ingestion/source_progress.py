"""Finite source-owner reconciliation for cursor and stream admission.

SourceContract remains the owner of source, schema and role semantics. This
reader is a bounded integrate adapter over its actual replay fixture. It reads
that entire source file independently of connector output; no caller-supplied
expected member list, row count or completeness declaration is an oracle.

The admitted scope is exactly ``finite_source_fixture``. This adapter does not
verify production completeness/currentness, law, rights or institutional facts.
A live provider needs its own independently admitted source-owner reader.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, fields, replace
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast
from urllib.parse import urlparse

from pydantic import TypeAdapter

from polisyos.core.artifacts import load_core_json_artifact
from polisyos.core.artifacts.manifest import ArtifactRef, SchemaInfo, artifact_ref_identity_key
from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
from polisyos.core.canon import CanonSpec, content_hash, to_canonical_bytes
from polisyos.core.contracts.fabric import EvidenceBundle, EvidenceBundleRef
from polisyos.core.contracts.provenance import ProvenanceCoreGraph, RelationType
from polisyos.fabric.connectors.contracts.source_contract import (
    SourceContract,
    SourceProgressContract,
)
from polisyos.fabric.connectors.types import FetchError
from polisyos.fabric.ingestion._source_evidence_schema import require_source_evidence_schema
from polisyos.ir.connectors import DataVersion, FetchRequest, FetchResult, VersionStrategy

if TYPE_CHECKING:
    from polisyos.core.artifacts.protocol import ArtifactStore
    from polisyos.core.contracts.cursor import CursorState
    from polisyos.fabric.connectors.base import ConnectionConfig

_WITNESS_KIND = "fabric.source_progress_witness"
_WITNESS_SCHEMA = "fabric.FiniteSourceProgressWitness"
_MAX_FINITE_FIXTURE_BYTES = 8 * 1024 * 1024


class SourceProgressAdmissionError(FetchError):
    """Refuse a source result that differs from its independent finite owner."""


def _json_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for name, value in pairs:
        if name in result:
            raise ValueError("duplicate key in source-owner fixture")
        result[name] = value
    return result


def _bytes(value: object) -> bytes:
    return to_canonical_bytes(value, spec=CanonSpec(forbid_floats=False))


def _rows(payload: object) -> list[dict[str, Any]]:
    if not isinstance(payload, list) or any(not isinstance(row, dict) for row in payload):
        from polisyos.fabric.data_plane.tabular import payload_to_dataframe

        frame = payload_to_dataframe(payload)
        if frame is None:
            raise ValueError("source payload is not tabular")
        payload = frame.to_dict(orient="records")
    if not isinstance(payload, list) or any(not isinstance(row, dict) for row in payload):
        raise ValueError("source payload does not contain object rows")
    return [dict(row) for row in payload]


def _row_set(rows: list[dict[str, Any]]) -> list[bytes]:
    return sorted(_bytes(row) for row in rows)


def _key(row: dict[str, Any], fields: tuple[str, ...]) -> str:
    values = []
    for name in fields:
        value = row.get(name)
        if type(value) not in {str, int} or value == "":
            raise ValueError("source event/version key is missing or ambiguous")
        values.append(value)
    return _bytes(values).decode("utf-8")


def snapshot_fetch_request(request: FetchRequest) -> dict[str, Any]:
    """Snapshot every owner-defined constructor field without filesystem probes."""
    names = {field.name for field in fields(FetchRequest) if field.init}
    return cast(
        "dict[str, Any]",
        TypeAdapter(FetchRequest).dump_python(request, mode="json", include=names),
    )


def _restore_fetch_request(payload: object) -> FetchRequest:
    if not isinstance(payload, dict) or set(payload) != {
        field.name for field in fields(FetchRequest) if field.init
    }:
        raise ValueError("persisted actual request is incomplete or has unknown fields")
    return TypeAdapter(FetchRequest).validate_python(payload)


@dataclass(frozen=True)
class _FiniteSnapshot:
    version: DataVersion
    rows: tuple[dict[str, Any], ...]


@dataclass(frozen=True)
class ReconciledSourceFrame:
    """Frozen whole-fixture basis, independently read before connector fetch."""

    reader: FiniteSourceProgressReader
    fixture_hash: str
    fixture_payload: dict[str, Any]
    fixture_bytes: bytes
    snapshots: tuple[_FiniteSnapshot, ...]
    current_index: int
    tenant_id: str | None
    transport_identity: dict[str, str] | None = None
    transport_bytes_hash: str | None = None
    transport_bytes: bytes | None = None

    @property
    def extension(self) -> SourceProgressContract:
        """Return the separately versioned, source-bound role contract."""
        return self.reader.extension

    @property
    def current(self) -> _FiniteSnapshot:
        """Return the finite owner's actual current snapshot."""
        return self.snapshots[self.current_index]

    def snapshot_for(self, value: str) -> _FiniteSnapshot:
        """Resolve one unambiguous version from the frozen complete owner file."""
        matches = [snapshot for snapshot in self.snapshots if snapshot.version.value == value]
        if len(matches) != 1:
            raise ValueError("source version is absent or ambiguous in the owner history")
        return matches[0]

    def assert_current(self) -> None:
        """Refuse source movement while this invocation is using its frozen frame."""
        if content_hash(self.reader.read_fixture_bytes()) != self.fixture_hash:
            raise ValueError("source-owner fixture changed during ingestion")

    def _local_transport_path(self, config: ConnectionConfig) -> Path:
        from polisyos.fabric.connectors.base import _safe_local_path

        parsed = urlparse(config.url)
        if parsed.scheme != "file" or parsed.netloc not in {"", "localhost"}:
            raise ValueError("finite source authority requires actual local file replay transport")
        actual = _safe_local_path(config.url, scheme="file").resolve(strict=True)
        expected = self.reader.transport_path
        if not actual.is_file() or not actual.samefile(expected):
            raise ValueError("actual transport differs from the source-owned replay file")
        return actual

    def bind_transport(
        self, config: ConnectionConfig, *, partition_key: str = "default"
    ) -> ReconciledSourceFrame:
        """Bind the actual local file, not a live endpoint or a producer assertion.

        History replay reads the history file itself as its sole producer. JSONL
        uses the existing EventStream file reader and independently enumerates
        its entire physical file here. Network locations never gain authority
        from a separate finite fixture, even if their visible rows are identical.
        """
        if partition_key != self.extension.partition_key:
            raise ValueError("actual partition differs from the source-owned partition")
        path = self._local_transport_path(config)
        with path.open("rb") as stream:
            raw = stream.read(_MAX_FINITE_FIXTURE_BYTES + 1)
        if len(raw) > _MAX_FINITE_FIXTURE_BYTES:
            raise ValueError("actual replay transport exceeds the finite admission bound")
        self._validate_transport_bytes(raw)
        stat = path.stat()
        return replace(
            self,
            transport_identity={
                "kind": self.extension.transport_kind,
                "path": str(path),
                "device": str(stat.st_dev),
                "inode": str(stat.st_ino),
                "connection_scope": config.cache_scope_fingerprint,
                "partition_key": partition_key,
            },
            transport_bytes_hash=content_hash(raw),
            transport_bytes=raw,
        )

    def _validate_transport_bytes(self, raw: bytes) -> None:
        if len(raw) > _MAX_FINITE_FIXTURE_BYTES:
            raise ValueError("actual replay transport exceeds the finite admission bound")
        if self.extension.transport_kind == "finite_history_file":
            if raw != self.fixture_bytes:
                raise ValueError("actual history replay differs from the frozen source")
            return
        # Enumerate ALL physical events. Identity-only scope permits physical
        # redelivery annotations, never omitted logical keys in either direction.
        rows = [
            json.loads(line, object_pairs_hook=_json_object)
            for line in raw.splitlines()
            if line.strip()
        ]
        roles = self.extension.event_fields + self.extension.version_fields
        actual_keys: set[str] = set()
        for row in rows:
            if not isinstance(row, dict):
                raise ValueError("actual JSONL transport contains a non-object event")
            self._validate_key_schema(row)
            actual_keys.add(_key(row, roles))
        if actual_keys != {_key(row, roles) for row in self.current.rows}:
            raise ValueError("actual whole JSONL source differs from the owner universe")

    def assert_transport_current(self) -> None:
        """Require the bound physical source at every protected admission."""
        if self.transport_identity is None or self.transport_bytes_hash is None:
            raise ValueError("actual finite replay transport is not established")
        path = self.reader.transport_path
        stat = path.stat()
        with path.open("rb") as stream:
            raw = stream.read(_MAX_FINITE_FIXTURE_BYTES + 1)
        if (
            len(raw) > _MAX_FINITE_FIXTURE_BYTES
            or str(path) != self.transport_identity["path"]
            or str(stat.st_dev) != self.transport_identity["device"]
            or str(stat.st_ino) != self.transport_identity["inode"]
            or content_hash(raw) != self.transport_bytes_hash
        ):
            raise ValueError("actual finite replay transport changed during ingestion")

    def replay_fetch(self, config: ConnectionConfig, request: FetchRequest) -> FetchResult[Any]:
        """Execute bounded file replay, with no call to a live connector fetch.

        The same exact owner file is both the actual source and complete finite
        denominator. This adapter owns only replay IO and event progress, never
        provider completeness or production currentness.
        """
        if self.extension.transport_kind != "finite_history_file":
            raise ValueError("batch replay requires an actual history-file transport")
        rebound = self.bind_transport(config)
        if rebound.transport_identity != self.transport_identity:
            raise ValueError("actual handle differs from the admitted source transport")
        self.assert_current()
        self.assert_transport_current()
        rows = [dict(row) for row in self.current.rows]
        if request.incremental_since is not None:
            prior = self.snapshot_for(request.incremental_since.value)
            if request.incremental_since.strategy != prior.version.strategy:
                raise ValueError("request predecessor strategy differs from actual source")
            previous_keys = {
                _key(row, self.extension.event_fields + self.extension.version_fields)
                for row in prior.rows
            }
            rows = [
                row
                for row in rows
                if _key(row, self.extension.event_fields + self.extension.version_fields)
                not in previous_keys
            ]
        return FetchResult(
            data=rows,
            row_count=len(rows),
            schema_id=self.extension.schema_id,
            schema_version=self.extension.schema_version_bound,
            version=self.current.version,
            fetched_at=self.current.version.timestamp,
            source_updated_at=(
                self.current.version.timestamp
                if self.current.version.strategy is VersionStrategy.TIMESTAMP
                else None
            ),
            completeness=1.0,
        )

    def scope_payload(self, witness_ref: ArtifactRef) -> dict[str, Any]:
        """Carry bounded authority on the artifact read by downstream consumers."""
        self.assert_transport_current()
        return {
            "schema_version": "fabric.source_progress_scope.v1",
            "admission_scope": "finite_source_fixture",
            "predicate_class": "recomputed",
            "transport": self.transport_identity,
            "transport_sha256": self.transport_bytes_hash,
            "source_witness_ref": witness_ref.model_dump(mode="json"),
            "production_currentness": "not_established",
            "external_source_rights": "not_established",
            "production_event_identity_semantics": "not_established",
        }

    def reconcile_fetch(self, request: FetchRequest, result: FetchResult[Any]) -> FetchResult[Any]:
        """Reconcile every actual source row and return its full materialized state.

        Incremental transport is append-only event/version identity. Unchanged
        sources may return an empty delta; the verified whole source state is
        retained for a fresh consumer of this invocation's published result.
        """
        try:
            self.assert_current()
            self.assert_transport_current()
            if (
                request.dataset_id != self.extension.dataset_id
                or request.filters
                or request.date_start is not None
                or request.date_end is not None
                or request.as_of is not None
                or request.page_token is not None
            ):
                raise ValueError("finite owner does not admit a filtered/paginated source view")
            current = self.current
            if (
                result.version.strategy != current.version.strategy
                or result.version.value != current.version.value
                or (
                    current.version.strategy is VersionStrategy.TIMESTAMP
                    and (
                        result.version.timestamp != current.version.timestamp
                        or result.source_updated_at != current.version.timestamp
                    )
                )
                or result.schema_id != self.extension.schema_id
                or result.schema_version != self.extension.schema_version_bound
                or result.has_more
                or result.next_page_token is not None
                or result.completeness != 1.0
            ):
                raise ValueError("source result boundary/schema differs from the finite owner")
            expected_rows = list(current.rows)
            if request.incremental_since is not None:
                previous = self.snapshot_for(request.incremental_since.value)
                if (
                    request.incremental_since.strategy != previous.version.strategy
                    or request.incremental_since.timestamp != previous.version.timestamp
                    or self.snapshots.index(previous) > self.current_index
                ):
                    raise ValueError("request predecessor differs from the owner history")
                previous_keys = {
                    _key(row, self.extension.event_fields + self.extension.version_fields)
                    for row in previous.rows
                }
                expected_rows = [
                    row
                    for row in current.rows
                    if _key(row, self.extension.event_fields + self.extension.version_fields)
                    not in previous_keys
                ]
            actual_rows = _rows(result.data)
            if result.row_count != len(actual_rows) or _row_set(actual_rows) != _row_set(
                expected_rows
            ):
                raise ValueError("actual source rows differ from the complete owner view")
            materialized_rows = [dict(row) for row in current.rows]
            return result.model_copy(
                update={
                    "data": materialized_rows,
                    "row_count": len(materialized_rows),
                    "version": current.version.model_copy(
                        update={"content_hash": "sha256:" + content_hash(_bytes(materialized_rows))}
                    ),
                    "not_modified": result.not_modified,
                }
            )
        except (OSError, TypeError, ValueError) as exc:
            raise SourceProgressAdmissionError(
                "source_progress_not_reconciled",
                connector_id=self.extension.connector_id,
                dataset_id=self.extension.dataset_id,
            ) from exc

    def verify_materialization(
        self, result: FetchResult[Any], *, version: str | None = None
    ) -> None:
        """Verify all rows of a persisted full source contribution."""
        expected = self.snapshot_for(version) if version is not None else self.current
        actual = _rows(result.data)
        if (
            result.version.strategy != expected.version.strategy
            or result.version.value != expected.version.value
            or result.version.timestamp != expected.version.timestamp
            or result.schema_id != self.extension.schema_id
            or result.schema_version != self.extension.schema_version_bound
            or result.row_count != len(actual)
            or _row_set(actual) != _row_set(list(expected.rows))
        ):
            raise ValueError("persisted source contribution differs from the owner view")

    def _validate_key_schema(self, row: dict[str, Any]) -> None:
        from polisyos.fabric.data_plane.schema_rows import field_value_violation

        schema = self.extension.bind(self.reader.source_contract)
        roles = self.extension.event_fields + self.extension.version_fields
        if any(
            field_value_violation(row.get(field.name), field) is not None
            for field in schema.fields
            if field.name in roles
        ):
            raise ValueError("actual source event/version violates its owned schema")

    def admit_stream_rows(self, rows: list[object]) -> None:
        """Resolve event/version membership against the complete actual owner view.

        This admits identity only. Non-key payload remains candidate data;
        equal source event/version keys are redeliveries even when transport
        annotations differ. No payload-truth authority is inferred here.
        """
        self.assert_current()
        self.assert_transport_current()
        fields = self.extension.event_fields + self.extension.version_fields
        owner_keys = {_key(row, fields) for row in self.current.rows}
        for row in rows:
            if not isinstance(row, dict):
                raise ValueError("stream source identity is not an object")
            self._validate_key_schema(row)
            if _key(row, fields) not in owner_keys:
                raise ValueError("stream event/version is absent from the source owner")

    def _load_retained_witness(
        self, store: ArtifactStore, witness_ref: ArtifactRef
    ) -> ReconciledSourceFrame | None:
        try:
            old = load_source_progress_witness(store, witness_ref)
            if (
                self.transport_identity is None
                or old.tenant_id != self.tenant_id
                or old.extension != self.extension
                or old.reader.source_contract != self.reader.source_contract
                or old.transport_identity != self.transport_identity
            ):
                return None
            snapshots = old.fixture_payload["snapshots"]
            if self.fixture_payload["snapshots"][: len(snapshots)] != snapshots:
                return None
            return old
        except (LookupError, OSError, TypeError, ValueError):
            return None

    def retained_witness_is_current(self, store: ArtifactStore, witness_ref: ArtifactRef) -> bool:
        """Reconcile retained source bytes through the complete actual owner parser."""
        return self._load_retained_witness(store, witness_ref) is not None

    def witness(self, store: ArtifactStore) -> ArtifactRef:
        """Persist the exact bounded source bytes and recomputed admission scope."""
        self.assert_current()
        self.assert_transport_current()
        payload = {
            "schema_version": "fabric.finite_source_progress_witness.v1",
            "predicate_class": "recomputed",
            "admission_scope": "finite_source_fixture",
            "unresolved_by_construction": [
                "live_provider_completeness_currentness",
                "external_source_rights",
                "production_event_identity_semantics",
            ],
            "tenant_id": self.tenant_id,
            "transport_identity": self.transport_identity,
            "transport_sha256": self.transport_bytes_hash,
            # The history file is already retained below. JSONL is a separate
            # physical transport: retain its deciding bytes once so a fresh
            # reader can recompute its complete logical key universe.
            "transport_jsonl": self.transport_bytes.decode("utf-8")
            if self.extension.transport_kind == "jsonl_file" and self.transport_bytes is not None
            else None,
            "source_contract": self.reader.source_contract.model_dump(mode="json"),
            "extension": self.extension.model_dump(mode="json"),
            "extension_content_hash": self.extension.content_hash,
            "fixture_sha256": self.fixture_hash,
            "source_history_json": self.fixture_bytes.decode("utf-8"),
        }
        ref = store.put_json(
            payload,
            ArtifactWriteOptions(
                kind=_WITNESS_KIND,
                media_type="application/json",
                schema=SchemaInfo(name=_WITNESS_SCHEMA, version="1.0"),
            ),
            canon_spec=CanonSpec(forbid_floats=False),
            return_selected_profile=True,
        )
        if (
            ref.kind != _WITNESS_KIND
            or ref.media_type != "application/json"
            or ref.manifest_profile_sha256 is None
            or not store.verify(ref).ok
            or load_core_json_artifact(store, ref) != payload
        ):
            raise ValueError("source-progress witness was not persisted as its exact selected view")
        return ref

    def admit_cursor(self, cursor: CursorState, store: ArtifactStore) -> DataVersion | None:
        """Resolve source witness, payload and provenance before issuing a hint."""
        try:
            proof = cursor.metadata.get("source_progress")
            if not isinstance(proof, dict):
                return None
            witness_ref = ArtifactRef.model_validate(proof["witness_ref"])
            payload_ref = ArtifactRef.model_validate(proof["payload_ref"])
            evidence_ref = EvidenceBundleRef.model_validate(proof["evidence_ref"])
            if (
                witness_ref.kind != _WITNESS_KIND
                or witness_ref.media_type != "application/json"
                or witness_ref.manifest_profile_sha256 is None
                or payload_ref.manifest_profile_sha256 is None
                or evidence_ref.manifest_profile_sha256 is None
                or cursor.connector_id != self.extension.connector_id
                or cursor.dataset_id != self.extension.dataset_id
                or str(evidence_ref.artifact_id) != cursor.evidence_bundle_ref
                or cursor.ingestion_run_id != cursor.evidence_bundle_ref
            ):
                return None
            old = self._load_retained_witness(store, witness_ref)
            if old is None or old.current.version.value != cursor.watermark_value:
                return None
            actual_request = _restore_fetch_request(proof.get("actual_request"))
            if (
                actual_request.dataset_id != cursor.dataset_id
                or actual_request.cache_key != proof.get("actual_request_key")
            ):
                return None
            bundle = EvidenceBundle.model_validate(load_core_json_artifact(store, evidence_ref))
            if (
                not any(
                    artifact_ref_identity_key(ref) == artifact_ref_identity_key(payload_ref)
                    for ref in bundle.sources
                )
                or bundle.provenance_ref is None
            ):
                return None
            from polisyos.core.artifacts.ids import ArtifactID
            from polisyos.fabric.connectors.cache._store_serialization import ResultSerializer

            persisted = ResultSerializer.deserialize(store.get_bytes(payload_ref))
            from polisyos.fabric.ingestion.ingestion import _cache_payload_ref_matches_result

            if not _cache_payload_ref_matches_result(store, payload_ref, persisted):
                return None
            self.verify_materialization(persisted, version=cursor.watermark_value)
            graph = ProvenanceCoreGraph.from_dict(
                load_core_json_artifact(
                    store, ArtifactID.model_validate(bundle.provenance_ref.artifact_id)
                )
            )
            graph_ref = bundle.provenance_ref
            entity_id = f"dataset.{cursor.connector_id}.{cursor.dataset_id}"
            entity = graph.entities.get(entity_id)
            if (
                graph.graph_id != graph_ref.graph_id
                or graph.compute_stable_id() != graph_ref.stable_id
                or entity is None
                or entity.attributes.get("fetch_status") != "complete"
                or entity.attributes.get("cache_key") != proof.get("actual_request_key")
                or entity.attributes.get("data_artifact_id") != payload_ref.artifact_id.hex
                or entity.attributes.get("version_value") != cursor.watermark_value
                or not any(
                    edge.source_id == entity_id
                    and edge.target_id == "connector_ingestion_run"
                    and edge.relation is RelationType.WAS_GENERATED_BY
                    for edge in graph.edges
                )
            ):
                return None
            version = self.snapshot_for(cursor.watermark_value).version
            if version.strategy.value != cursor.watermark_type.value:
                return None
            self.assert_current()
            self.assert_transport_current()
            return version
        except (KeyError, LookupError, OSError, TypeError, ValueError):
            return None


@dataclass(frozen=True)
class FiniteSourceProgressReader:
    """Host-configured read-only adapter over one actual source-owned fixture.

    The connector cannot select an expected row set or install this dependency.
    The owner-bound fixture itself is the complete finite source denominator.
    No production source is admitted by this bounded adapter.
    """

    source_root: Path
    source_contract: SourceContract
    extension: SourceProgressContract

    def __post_init__(self) -> None:
        # Revalidate actual model values; a model_construct() or subclass
        # self-attestation must not substitute for the source owner contract.
        object.__setattr__(
            self,
            "source_contract",
            SourceContract.model_validate(self.source_contract.model_dump(mode="python")),
        )
        object.__setattr__(
            self,
            "extension",
            SourceProgressContract.model_validate(self.extension.model_dump(mode="python")),
        )

    @property
    def fixture_path(self) -> Path:
        """Resolve only the exact source-owner replay fixture within its root."""
        self.extension.bind(self.source_contract)
        raw = self.source_contract.replay.fixture_ref
        if not isinstance(raw, str):
            raise ValueError("source owner has no finite fixture")
        relative = Path(raw)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("finite source fixture must be relative to its configured root")
        root = self.source_root.resolve()
        result = (root / relative).resolve(strict=True)
        if not result.is_relative_to(root) or not result.is_file():
            raise ValueError("source fixture escapes its configured root")
        return result

    @property
    def transport_path(self) -> Path:
        """Resolve the actual source-owner transport under the same admitted root."""
        if self.extension.transport_kind == "finite_history_file":
            return self.fixture_path
        raw = self.extension.transport_fixture_ref
        if not isinstance(raw, str):
            raise ValueError("source owner has no actual JSONL transport fixture")
        relative = Path(raw)
        root = self.source_root.resolve()
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("actual source transport must be relative to its configured root")
        path = (root / relative).resolve(strict=True)
        if not path.is_relative_to(root) or not path.is_file():
            raise ValueError("actual source transport escapes its configured root")
        return path

    def read_fixture_bytes(self) -> bytes:
        """Bound actual owner bytes before JSON parsing or history materialization."""
        with self.fixture_path.open("rb") as stream:
            raw = stream.read(_MAX_FINITE_FIXTURE_BYTES + 1)
        if len(raw) > _MAX_FINITE_FIXTURE_BYTES:
            raise ValueError("finite source fixture exceeds its 8 MiB admission profile")
        return raw

    def freeze(self, *, tenant_id: str | None) -> ReconciledSourceFrame:
        """Independently read and enumerate the actual complete finite source."""
        return self._parse_history(self.read_fixture_bytes(), tenant_id=tenant_id)

    def _parse_history(self, raw: bytes, *, tenant_id: str | None) -> ReconciledSourceFrame:
        if len(raw) > _MAX_FINITE_FIXTURE_BYTES:
            raise ValueError("finite source fixture exceeds its admission profile")
        schema = self.extension.bind(self.source_contract)
        from polisyos.fabric.data_plane.schema_rows import field_value_violation

        payload = json.loads(raw, object_pairs_hook=_json_object)
        if not isinstance(payload, dict) or set(payload) != {
            "schema_version",
            "connector_id",
            "dataset_id",
            "current_version",
            "snapshots",
        }:
            raise ValueError("invalid finite source-owner history")
        if (
            payload["schema_version"] != "fabric.finite_source_history.v1"
            or payload["connector_id"] != self.extension.connector_id
            or payload["dataset_id"] != self.extension.dataset_id
            or not isinstance(payload["snapshots"], list)
            or not payload["snapshots"]
        ):
            raise ValueError("finite source owner identity differs")
        snapshots: list[_FiniteSnapshot] = []
        version_values: set[str] = set()
        prior_rows: dict[str, bytes] = {}
        for snapshot in payload["snapshots"]:
            if not isinstance(snapshot, dict) or set(snapshot) != {"version", "rows"}:
                raise ValueError("invalid source-owner snapshot")
            raw_version = snapshot["version"]
            raw_time = raw_version.get("timestamp") if isinstance(raw_version, dict) else None
            parsed_time = datetime.fromisoformat(raw_time) if isinstance(raw_time, str) else None
            if parsed_time is None or parsed_time.utcoffset() is None:
                raise ValueError("source-owner version timestamp must declare a timezone")
            version = DataVersion.model_validate(raw_version)
            if version.strategy.value != self.extension.version_strategy:
                raise ValueError(
                    "source boundary strategy differs from its versioned owner contract"
                )
            if not version.value.strip():
                raise ValueError("source boundary value is empty")
            if version.strategy is VersionStrategy.REVISION:
                if not version.value.isascii() or not version.value.isdecimal():
                    raise ValueError("source revision must be an unsigned decimal value")
                if snapshots and int(version.value) <= int(snapshots[-1].version.value):
                    raise ValueError("source revisions do not advance")
            if version.strategy is VersionStrategy.TIMESTAMP:
                value_time = datetime.fromisoformat(version.value)
                if value_time.utcoffset() is None or value_time != version.timestamp:
                    raise ValueError("source timestamp value and declared epoch differ")
                if snapshots and version.timestamp <= snapshots[-1].version.timestamp:
                    raise ValueError("source timestamp boundaries do not advance")
            if version.value in version_values:
                raise ValueError("ambiguous source boundary")
            version_values.add(version.value)
            records = _rows(snapshot["rows"])
            actual_rows: dict[str, bytes] = {}
            for row in records:
                roles = self.extension.event_fields + self.extension.version_fields
                if any(
                    field_value_violation(row.get(field.name), field) is not None
                    for field in schema.fields
                    if field.name in roles
                ):
                    raise ValueError("source owner event/version violates its concrete schema")
                key = _key(row, roles)
                if key in actual_rows:
                    raise ValueError("ambiguous source event/version key")
                actual_rows[key] = _bytes(row)
            if any(actual_rows.get(key) != value for key, value in prior_rows.items()):
                raise ValueError("finite owner is not append-only event/version history")
            prior_rows = actual_rows
            snapshots.append(_FiniteSnapshot(version, tuple(records)))
        selected = [
            index
            for index, snapshot in enumerate(snapshots)
            if snapshot.version.value == payload["current_version"]
        ]
        if selected != [len(snapshots) - 1]:
            raise ValueError("current source boundary must be the final actual owner snapshot")
        return ReconciledSourceFrame(
            reader=self,
            fixture_hash=content_hash(raw),
            fixture_payload=payload,
            fixture_bytes=raw,
            snapshots=tuple(snapshots),
            current_index=selected[0],
            tenant_id=tenant_id,
        )


def resolve_source_progress_frame(
    readers: tuple[FiniteSourceProgressReader, ...],
    *,
    connector_id: str,
    dataset_id: str,
    tenant_id: str | None,
) -> ReconciledSourceFrame | None:
    """Resolve a unique host-selected reader without a second source registry."""
    selected = [
        reader
        for reader in readers
        if type(reader) is FiniteSourceProgressReader
        and reader.extension.connector_id == connector_id
        and reader.extension.dataset_id == dataset_id
    ]
    if not selected:
        return None
    if len(selected) != 1:
        raise ValueError("source progress reader is ambiguous")
    return selected[0].freeze(tenant_id=tenant_id)


def load_source_progress_witness(
    store: ArtifactStore, witness_ref: ArtifactRef
) -> ReconciledSourceFrame:
    """Recompute a retained bounded replay proof for a fresh downstream reader.

    This proves the recorded finite source view, not that a local path is still
    current. Cursor and stream authority additionally bind/assert the actual
    physical transport in the current invocation. No saved declaration alone
    grants currentness or live provider authority.
    """
    if (
        witness_ref.kind != _WITNESS_KIND
        or witness_ref.media_type != "application/json"
        or witness_ref.manifest_profile_sha256 is None
    ):
        raise ValueError("source witness has no exact selected profile")
    witness = load_core_json_artifact(store, witness_ref)
    if not isinstance(witness, dict) or (
        witness.get("schema_version") != "fabric.finite_source_progress_witness.v1"
        or witness.get("predicate_class") != "recomputed"
        or witness.get("admission_scope") != "finite_source_fixture"
        or witness.get("unresolved_by_construction")
        != [
            "live_provider_completeness_currentness",
            "external_source_rights",
            "production_event_identity_semantics",
        ]
    ):
        raise ValueError("source witness scope is not the bounded replay contract")
    source = SourceContract.model_validate(witness.get("source_contract"))
    extension = SourceProgressContract.model_validate(witness.get("extension"))
    if witness.get("extension_content_hash") != extension.content_hash:
        raise ValueError("source witness extension hash differs from its actual owner")
    tenant = witness.get("tenant_id")
    if tenant is not None and not isinstance(tenant, str):
        raise ValueError("source witness tenant is invalid")
    raw = witness.get("source_history_json")
    if not isinstance(raw, str) or content_hash(raw.encode()) != witness.get("fixture_sha256"):
        raise ValueError("source witness history bytes do not match")
    reader = FiniteSourceProgressReader(Path("."), source, extension)
    old = reader._parse_history(raw.encode(), tenant_id=tenant)
    identity = witness.get("transport_identity")
    if (
        not isinstance(identity, dict)
        or set(identity) != {"kind", "path", "device", "inode", "connection_scope", "partition_key"}
        or any(not isinstance(value, str) or not value for value in identity.values())
    ):
        raise ValueError("source witness transport identity is incomplete")
    if (
        identity["kind"] != extension.transport_kind
        or identity["partition_key"] != extension.partition_key
    ):
        raise ValueError("source witness transport/partition differs from its owner")
    transport_raw = (
        raw if extension.transport_kind == "finite_history_file" else witness.get("transport_jsonl")
    )
    if not isinstance(transport_raw, str) or content_hash(transport_raw.encode()) != witness.get(
        "transport_sha256"
    ):
        raise ValueError("source witness transport bytes do not match")
    old._validate_transport_bytes(transport_raw.encode())
    return replace(
        old,
        transport_identity=identity,
        transport_bytes_hash=content_hash(transport_raw.encode()),
        transport_bytes=transport_raw.encode(),
    )


def project_partial_source_scope(
    store: ArtifactStore,
    evidence_ref: EvidenceBundleRef,
    *,
    frames: dict[tuple[str, str], ReconciledSourceFrame],
    advanced: set[tuple[str, str]],
) -> EvidenceBundleRef:
    """Persist explicit finite limitations on inspectable partial evidence itself.

    These notes are an audit projection, never an admission predicate. Actual
    protected progress still uses the resolved owner/payload/provenance intake.
    The original evidence remains a direct selected input of this projection.
    """
    from polisyos.core.artifacts.manifest import input_ref_from_artifact_ref
    from polisyos.core.contracts.fabric import EvidenceStep

    evidence = EvidenceBundle.model_validate(load_core_json_artifact(store, evidence_ref))
    manifest = store.get_manifest(evidence_ref)
    evidence_schema = require_source_evidence_schema(manifest)
    inputs = [input_ref_from_artifact_ref(evidence_ref, role="source_evidence")]
    steps = list(evidence.transforms)
    notes = [
        *evidence.notes,
        "Partial evidence is not a completed source collection; production completeness, "
        "currentness, rights and live event meaning are not established by this replay adapter.",
    ]
    for key, frame in sorted(frames.items()):
        try:
            witness = frame.witness(store)
        except (LookupError, OSError, TypeError, ValueError):
            notes.append(
                f"source_progress:{key[0]}:{key[1]}:not_established; "
                "current source witness unavailable"
            )
            continue
        inputs.append(input_ref_from_artifact_ref(witness, role="source_progress_witness"))
        steps.append(
            EvidenceStep(
                op="bounded_source_progress_scope",
                details={
                    "connector_id": key[0],
                    "dataset_id": key[1],
                    "admission_scope": "finite_source_fixture",
                    "production_currentness": "not_established",
                    "source_cursor_advanced": key in advanced,
                    "witness_ref": str(witness.artifact_id),
                    "witness_manifest_profile_sha256": witness.manifest_profile_sha256 or "",
                },
            )
        )
        notes.append(
            f"source_progress:{key[0]}:{key[1]}:finite_source_fixture; "
            "production_currentness, rights and live event semantics not_established; "
            "partial evidence is not a completed source collection"
        )
    projected = evidence.model_copy(update={"transforms": steps, "notes": notes})
    ref = store.put_json(
        projected,
        ArtifactWriteOptions(
            kind=evidence_ref.kind,
            media_type="application/json",
            schema=evidence_schema,
            governance=manifest.governance,
            inputs=inputs,
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    if (
        not store.verify(ref).ok
        or EvidenceBundle.model_validate(load_core_json_artifact(store, ref)) != projected
    ):
        raise ValueError("partial source scope projection did not persist exactly")
    return EvidenceBundleRef.model_validate(ref.model_dump(mode="python"))
