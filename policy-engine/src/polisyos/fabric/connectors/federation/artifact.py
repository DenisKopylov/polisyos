"""Bounded selected federation replay conditional on declared leaf inputs.

A fresh reader resolves every selected parent in a separately held registry,
reopens its content, and derives child cells from the parent's replay. Hashes
inside a child are selectors, never substitutes for the selected parent bytes.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
import tempfile
import types
from dataclasses import asdict, dataclass, field, fields
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, Union, get_args, get_origin, get_type_hints

import pandas as pd

from polisyos.fabric.connectors.federation.composer import (
    DataComposer,
    _mark_selected_bytes,
    _read_persisted_lineage,
    _selected_parent_carrier,
)
from polisyos.fabric.connectors.federation.profile import (
    MAX_CELLS,
    MAX_FILE_BYTES,
    MAX_GRAPH_CELLS,
    MAX_GRAPH_DEPTH,
    MAX_GRAPH_NODES,
    MAX_JSON_DEPTH,
    MAX_ROWS,
    MAX_SCALAR_BYTES,
    MAX_SOURCES,
    MAX_TOTAL_BYTES,
    admit_frame,
    admit_json_tree,
    admit_shape,
    bounded_encode,
    cast_series_losslessly,
    encode_scalar,
    frame_projection,
)
from polisyos.fabric.connectors.federation.resolver import ConflictResolver
from polisyos.fabric.connectors.federation.types import (
    AuditLevel,
    CompositionRequest,
    CompositionStrategy,
    ConflictPolicy,
    FederationBasisStatus,
    FederationError,
    SourceMetadata,
)
from polisyos.ir.connectors import ConnectorMetadataSpec

if TYPE_CHECKING:
    from collections.abc import Mapping

# v1 exists only in held, unapplied Cloud proposals. This replaces that candidate
# protocol; it does not claim a supported product-v1 migration or reader fallback.
_FORMAT = "policyos.federation.derivation/2"
_LINEAGE_ATTR = "policyos_federation_lineage_v1"
_HASH = re.compile(r"[0-9a-f]{64}\Z")
_DTYPE = re.compile(
    r"(?:object|bool|boolean|str|string|[Uu]?[Ii]nt(?:8|16|32|64)|[Ff]loat(?:32|64)|"
    r"datetime64\[ns(?:, [A-Za-z0-9_+:/-]+)?\])\Z"
)


@dataclass(frozen=True)
class FederationArtifactRef:
    """An independently selected manifest digest, requiring actual held bytes."""

    manifest_sha256: str


@dataclass(frozen=True)
class SelectedFederationInput:
    """A held parent and its separately held transitive selection registry."""

    root: Path
    ref: FederationArtifactRef
    metadata: SourceMetadata
    parents: Mapping[str, Path] = field(default_factory=dict)


@dataclass(frozen=True)
class VerifiedFederationResult:
    """Software derivation recomputed conditional on the selected declared leaves."""

    data: pd.DataFrame
    source_ids_by_cell: tuple[dict[str, str | list[str]], ...]
    merge_summary: dict[str, Any]
    basis_status: FederationBasisStatus
    source_declarations: tuple[tuple[str, str], ...]
    assurance: str = "software_derivation_candidate"
    limitation: str = (
        "issuer identity, authorization, source-universe completeness, and live currentness "
        "are consumer-declared, not independently established; aggregate cells cannot be "
        "ranked as a single trust-bearing leaf"
    )


@dataclass
class _Budget:
    bytes_read: int = 0
    cells: int = 0
    nodes: int = 0
    active: set[str] = field(default_factory=set)

    def charge(self, size: int) -> None:
        self.bytes_read += size
        if self.bytes_read > MAX_TOTAL_BYTES:
            raise FederationError("Federation selected graph exceeds aggregate byte profile")

    def frame(self, rows: int, columns: int) -> None:
        admit_shape(rows, columns)
        self.cells += rows * columns
        if self.cells > MAX_GRAPH_CELLS:
            raise FederationError("Federation selected graph exceeds aggregate cell-work profile")


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical(value: Any) -> bytes:  # noqa: ANN401
    return bounded_encode(value)


def _check_hash(digest: object) -> str:
    if not isinstance(digest, str) or not _HASH.fullmatch(digest):
        raise FederationError("Malformed federation selected digest")
    return digest


def _admit_encoded_strings(payload: bytes) -> None:
    """Count decoded UTF-8 scalar bytes before JSON allocates string values."""
    cursor = 0
    while cursor < len(payload):
        if payload[cursor] != 34:
            cursor += 1
            continue
        cursor += 1
        size = 0
        while cursor < len(payload) and payload[cursor] != 34:
            character = payload[cursor]
            if character != 92:
                size += 1  # UTF-8 source bytes; JSON validates encoding later.
                cursor += 1
            else:
                if cursor + 1 >= len(payload):
                    raise FederationError("Truncated federation JSON escape")
                escaped = payload[cursor + 1]
                if escaped != 117:
                    size += 1
                    cursor += 2
                else:
                    codepoint = int(payload[cursor + 2 : cursor + 6], 16)
                    cursor += 6
                    if 0xD800 <= codepoint <= 0xDBFF:
                        if payload[cursor : cursor + 2] != b"\\u":
                            raise FederationError("Unpaired federation JSON surrogate")
                        low = int(payload[cursor + 2 : cursor + 6], 16)
                        if not 0xDC00 <= low <= 0xDFFF:
                            raise FederationError("Invalid federation JSON surrogate pair")
                        cursor += 6
                        size += 4
                    elif 0xDC00 <= codepoint <= 0xDFFF:
                        raise FederationError("Unpaired federation JSON surrogate")
                    else:
                        size += 1 if codepoint < 0x80 else 2 if codepoint < 0x800 else 3
            if size > MAX_SCALAR_BYTES:
                raise FederationError("Federation string exceeds pre-decode scalar byte profile")
        cursor += 1


def _read_json(root: Path, name: str, budget: _Budget) -> tuple[dict[str, Any], bytes]:
    if Path(name).name != name or name in {"", ".", ".."}:
        raise FederationError("Federation member must be a local basename")
    path = root / name
    if path.is_symlink():
        raise FederationError("Federation member symlinks are outside the wire profile")
    size = path.stat().st_size
    if size > MAX_FILE_BYTES:
        raise FederationError("Federation member exceeds engineering byte profile")
    budget.charge(size)
    with path.open("rb") as stream:
        payload = stream.read(size + 1)
    if len(payload) != size:
        raise FederationError("Federation member changed during bounded read")
    _admit_encoded_strings(payload)
    # Bound syntax nesting, array cardinality and total parsed values BEFORE
    # json.loads materializes every encoded row/container.
    stack: list[list[int | bool]] = []  # [opening byte, values, expects value]
    quoted = escaped = False
    values = 0
    array_values = 0
    for character in payload:
        if quoted:
            if escaped:
                escaped = False
            elif character == 92:
                escaped = True
            elif character == 34:
                quoted = False
            continue
        if character in (9, 10, 13, 32):
            continue
        if character == 44:
            if stack and stack[-1][0] == 91:
                stack[-1][2] = True
            continue
        if character in (93, 125):
            if stack:
                stack.pop()
            continue
        if stack and stack[-1][0] == 91 and stack[-1][2]:
            stack[-1][1] += 1
            array_values += 1
            if array_values > MAX_CELLS:
                raise FederationError(
                    "Federation encoded array work exceeds pre-decode cell profile"
                )
            stack[-1][2] = False
            if stack[-1][1] > MAX_ROWS:
                raise FederationError("Federation encoded array exceeds pre-decode row profile")
        if character in (91, 123):
            values += 1
            stack.append([character, 0, True])
            if len(stack) > MAX_JSON_DEPTH:
                raise FederationError("Federation JSON exceeds nesting profile")
        elif character == 34:
            values += 1
            quoted = True
        if values > MAX_GRAPH_CELLS:
            raise FederationError("Federation JSON exceeds pre-decode container profile")
    value = json.loads(payload)
    if not isinstance(value, dict):
        raise FederationError("Federation member must be a JSON object")
    admit_json_tree(value)
    return value, payload


def _decode_scalar(value: dict[str, Any]) -> Any:  # noqa: ANN401
    if not isinstance(value, dict):
        raise FederationError("Federation scalar must be a tagged object")
    kind = value.get("t")
    if kind == "null":
        decoded = None
    elif kind == "bool" and type(value.get("v")) is bool:
        decoded = value["v"]
    elif kind == "int" and isinstance(value.get("v"), str) and len(value["v"]) <= 1235:
        decoded = int(value["v"])
    elif kind == "float64" and isinstance(value.get("v"), str):
        decoded = float.fromhex(value["v"])
    elif kind == "str" and isinstance(value.get("v"), str):
        decoded = value["v"]
    elif kind == "timestamp" and isinstance(value.get("v"), str):
        decoded = pd.Timestamp(value["v"])
    else:
        raise FederationError("Unsupported federation scalar profile")
    if encode_scalar(decoded) != value:
        raise FederationError("Federation scalar is not an exact canonical wire value")
    return decoded


def _restore_frame(
    projection: dict[str, Any], budget: _Budget, *, precharged: bool = False
) -> pd.DataFrame:
    columns, dtypes, encoded = (projection[key] for key in ("columns", "dtypes", "rows"))
    if (
        not isinstance(columns, list)
        or not isinstance(dtypes, list)
        or not isinstance(encoded, list)
    ):
        raise FederationError("Malformed federation frame dimensions")
    if not precharged:
        budget.frame(len(encoded), len(columns))
    if (
        not all(isinstance(column, str) for column in columns)
        or len(set(columns)) != len(columns)
        or len(dtypes) != len(columns)
        or not all(isinstance(dtype, str) and _DTYPE.fullmatch(dtype) for dtype in dtypes)
    ):
        raise FederationError("Unsupported federation column/dtype profile")
    if any(not isinstance(row, list) or len(row) != len(columns) for row in encoded):
        raise FederationError("Malformed federation encoded row width")
    rows = [[_decode_scalar(value) for value in row] for row in encoded]
    frame = pd.DataFrame(rows, columns=columns, dtype=object)
    for column, dtype in zip(columns, dtypes, strict=True):
        frame[column] = cast_series_losslessly(frame[column], dtype)
    if frame_projection(frame) != projection:
        raise FederationError("Frame projection is not exactly round-trippable")
    return frame


def _metadata_projection(metadata: SourceMetadata) -> dict[str, Any]:
    if metadata.quality_report is not None or metadata.coverage is not None:
        raise FederationError("Quality/coverage objects require a future explicit replay profile")
    _admit_dataclass(metadata, SourceMetadata)
    return {
        "connector_id": metadata.connector_id,
        "metadata": metadata.metadata.model_dump(mode="json"),
        "fetched_at": metadata.fetched_at.isoformat(),
        "row_count": metadata.row_count,
        "last_updated": metadata.last_updated.isoformat() if metadata.last_updated else None,
        "observed_latency_ms": metadata.observed_latency_ms,
    }


def _restore_metadata(value: dict[str, Any]) -> SourceMetadata:
    return SourceMetadata(
        connector_id=value["connector_id"],
        metadata=ConnectorMetadataSpec.model_validate(value["metadata"]),
        fetched_at=datetime.fromisoformat(value["fetched_at"]),
        row_count=value["row_count"],
        last_updated=datetime.fromisoformat(value["last_updated"])
        if value["last_updated"]
        else None,
        observed_latency_ms=value["observed_latency_ms"],
    )


def _admit_typed(value: object, annotation: object) -> None:
    origin, args = get_origin(annotation), get_args(annotation)
    if origin in (types.UnionType, Union):
        for member in args:
            try:
                _admit_typed(value, member)
                return
            except FederationError:
                pass
        raise FederationError("Value does not match the supported typed replay profile")
    if origin is Literal:
        if not any(type(value) is type(member) and value == member for member in args):
            raise FederationError("Unsupported literal in replay request")
        return
    if origin in (dict, list, tuple):
        if type(value) is not origin:
            raise FederationError("Unsupported container type in replay request")
        if origin is dict:
            for key, member in value.items():
                _admit_typed(key, args[0])
                _admit_typed(member, args[1])
        else:
            for member in value:
                _admit_typed(member, args[0])
        return
    if annotation is type(None) and value is None:
        return
    if isinstance(annotation, type) and type(value) is annotation:
        return
    raise FederationError("Unsupported field type in replay request")


def _admit_dataclass(value: object, contract: type) -> None:
    if type(value) is not contract:
        raise FederationError("Unsupported replay contract subclass")
    # These optional runtime-heavy types are explicitly unsupported above;
    # the wire subprofile admits only None without importing their subsystems.
    namespace = dict(vars(sys.modules[contract.__module__]))
    namespace.update(
        datetime=datetime, timedelta=timedelta, DataSchema=type(None), DataQualityReport=type(None)
    )
    try:
        annotations = get_type_hints(contract, globalns=namespace)
    except (NameError, TypeError) as exc:
        raise FederationError("Replay contract has an unsupported field annotation") from exc
    for member in fields(contract):
        _admit_typed(getattr(value, member.name), annotations[member.name])


def _request_projection(request: CompositionRequest) -> dict[str, Any]:
    if request.schema is not None:
        raise FederationError("Federation wire profile requires an explicit schema-free request")
    _admit_dataclass(request, CompositionRequest)
    value = asdict(request)
    value["strategy"] = request.strategy.value
    value["conflict_policy"] = request.conflict_policy.value
    value["audit_level"] = request.audit_level.value
    value["min_trust_level"] = request.min_trust_level.value
    value["column_policies"] = (
        {column: policy.value for column, policy in request.column_policies.items()}
        if request.column_policies is not None
        else None
    )
    value["max_staleness"] = (
        request.max_staleness.total_seconds() if request.max_staleness is not None else None
    )
    admit_json_tree(value)
    bounded_encode(value, MAX_SCALAR_BYTES)
    return value


def _restore_request(value: dict[str, Any]) -> CompositionRequest:
    from datetime import timedelta

    from polisyos.ir.connectors import TrustLevel

    restored = dict(value)
    restored["strategy"] = CompositionStrategy(restored["strategy"])
    restored["conflict_policy"] = ConflictPolicy(restored["conflict_policy"])
    restored["audit_level"] = AuditLevel(restored["audit_level"])
    restored["min_trust_level"] = TrustLevel(restored["min_trust_level"])
    restored["column_policies"] = (
        {column: ConflictPolicy(policy) for column, policy in restored["column_policies"].items()}
        if restored["column_policies"] is not None
        else None
    )
    restored["max_staleness"] = (
        timedelta(seconds=restored["max_staleness"])
        if restored["max_staleness"] is not None
        else None
    )
    request = CompositionRequest(**restored)
    if _request_projection(request) != value:
        raise FederationError("Federation effective request is not exactly replayable")
    return request


def _summary(composer: DataComposer) -> dict[str, Any]:
    summary = composer.get_last_merge_summary()
    if summary is None:
        raise FederationError("Federation composer did not emit its summary")
    return {
        "total_conflicts": summary.total_conflicts,
        "by_policy": summary.by_policy,
        "by_conflict_type": summary.by_conflict_type,
        "by_column": summary.by_column,
        "by_source_pair": summary.by_source_pair,
        "sample_seed": summary.sample_seed,
        "sample_entries": [entry.to_dict() for entry in summary.sample_entries],
        "extra": summary.extra,
    }


def persist_federation_derivation(
    root: Path,
    composer: DataComposer,
    sources: list[tuple[pd.DataFrame, SourceMetadata] | SelectedFederationInput],
    request: CompositionRequest,
) -> FederationArtifactRef:
    """Produce bounded source members and a replayable selected derivation.

    The caller must retain the selected parents and pass their digest-to-path
    registry to the fresh reader. No child-supplied parent locator is used.
    """
    try:
        return _persist(root, composer, sources, request)
    except FederationError:
        raise
    except (OSError, ValueError, TypeError, KeyError, AttributeError, OverflowError) as exc:
        raise FederationError("Federation input is outside the supported replay profile") from exc


def _persist(
    root: Path,
    composer: DataComposer,
    sources: list[tuple[pd.DataFrame, SourceMetadata] | SelectedFederationInput],
    request: CompositionRequest,
) -> FederationArtifactRef:
    # All rule/profile refusals precede composition and directory publication.
    request_value = _request_projection(request)
    _restore_request(json.loads(bounded_encode(request_value)))
    if not sources or len(sources) > MAX_SOURCES:
        raise FederationError(f"Federation derivation requires 1..{MAX_SOURCES} sources")
    if type(composer.resolver) is not ConflictResolver:
        raise FederationError("Custom federation resolvers are not replayable")
    if composer.resolver.policy != request.conflict_policy:
        raise FederationError("Composer resolver policy differs from persisted request")
    seed = request.tie_breaker_seed or composer.resolver._tie_breaker_seed
    if seed is not None and not isinstance(seed, str):
        raise FederationError("Federation resolver seed must be a string or null")
    metadata_values = [
        _metadata_projection(
            source.metadata if isinstance(source, SelectedFederationInput) else source[1]
        )
        for source in sources
    ]
    parents: dict[str, Path] = {}
    for source in sources:
        if isinstance(source, SelectedFederationInput):
            if len(source.parents) > MAX_GRAPH_NODES:
                raise FederationError("Held parent registry exceeds graph profile")
            for digest, path in [
                *source.parents.items(),
                (source.ref.manifest_sha256, source.root),
            ]:
                _check_hash(digest)
                if digest in parents and parents[digest] != path:
                    raise FederationError("Ambiguous held parent selection")
                parents[digest] = path
    if len(parents) > MAX_GRAPH_NODES:
        raise FederationError("Held parent registry exceeds graph profile")
    admitted: list[tuple[pd.DataFrame, SourceMetadata]] = []
    payloads: list[bytes] = []
    budget = _Budget(nodes=1)  # Reserve this root before entering selected parents.
    # Raw aggregate dimensions are known before projection/copy; parents charge
    # their actual independently selected graph before a copied carrier is made.
    raw_cells = sum(
        source[0].shape[0] * source[0].shape[1]
        for source in sources
        if not isinstance(source, SelectedFederationInput)
    )
    if raw_cells > MAX_GRAPH_CELLS:
        raise FederationError("Federation raw inputs exceed aggregate cell-work profile")
    for position, source in enumerate(sources):
        if isinstance(source, SelectedFederationInput):
            parent = _read(source.root, source.ref, parents, budget, 1)
            budget.frame(*parent.data.shape)
            frame = _selected_parent_carrier(parent.data, source.ref.manifest_sha256, position)
            parent_ref = source.ref.manifest_sha256
            # The source member does not contain a mutable copy of the parent's
            # cells or lineage. Replay obtains both from the actual parent.
            value = {"parent": parent_ref, "metadata": metadata_values[position]}
            admitted.append((frame, _restore_metadata(value["metadata"])))
        else:
            frame, _metadata = source
            if _read_persisted_lineage(frame) is not None:
                raise FederationError("Derived carriers require an explicitly selected held parent")
            budget.frame(*frame.shape)
            metadata_value = metadata_values[position]
            source_bound = admit_frame(frame) + len(bounded_encode(metadata_value)) + 64
            if source_bound > MAX_FILE_BYTES or source_bound > MAX_TOTAL_BYTES - budget.bytes_read:
                raise FederationError(
                    "Federation source projection exceeds pre-allocation byte profile"
                )
            projection = frame_projection(frame)
            # Exact byte/work admission precedes copy/restore. Restored inputs
            # isolate the writer from later caller mutation within this call.
            value = {"frame": projection, "metadata": metadata_value}
            payload = bounded_encode(value)
            budget.charge(len(payload))
            admitted.append(
                (
                    _restore_frame(projection, budget, precharged=True),
                    _restore_metadata(value["metadata"]),
                )
            )
            payloads.append(payload)
            continue
        payload = bounded_encode(value)
        budget.charge(len(payload))
        payloads.append(payload)
    if request.strategy == CompositionStrategy.JOIN:
        output_rows = composer._preflight_join(admitted, request)
    else:
        output_rows = sum(len(frame) for frame, _ in admitted)
    output_columns = len(set().union(*(set(frame.columns) for frame, _ in admitted)))
    budget.frame(output_rows, output_columns)  # Reserve output before composition/projection.
    if budget.bytes_read > MAX_TOTAL_BYTES - 2 * MAX_FILE_BYTES:
        raise FederationError("Selected graph lacks reserved result/manifest byte budget")
    result, _ = composer.compose(admitted, request.strategy, request)
    output = bounded_encode(frame_projection(result))
    budget.charge(len(output))
    source_records = []
    for position, payload in enumerate(payloads):
        digest = _sha(payload)
        source_records.append(
            {"position": position, "sha256": digest, "path": f"source-{position}-{digest}.json"}
        )
    output_digest = _sha(output)
    manifest = {
        "format": _FORMAT,
        "sources": source_records,
        "request": request_value,
        "resolver": {"tie_breaker_seed": seed},
        "result": {"path": f"result-{output_digest}.json", "sha256": output_digest},
        "source_ids_by_cell": result.attrs[_LINEAGE_ATTR]["rows"],
        "source_declarations": result.attrs[_LINEAGE_ATTR]["source_declarations"],
        "basis_status": result.attrs[_LINEAGE_ATTR]["basis_status"],
        "merge_summary": _summary(composer),
        "assurance": "software_derivation_candidate",
        "limitations": [
            "consumer_declared_issuer",
            "no_live_currentness",
            "no_source_universe_proof",
        ],
    }
    admit_json_tree(manifest)
    manifest_bytes = bounded_encode(manifest)
    budget.charge(len(manifest_bytes))
    selected = FederationArtifactRef(_sha(manifest_bytes))
    if root.exists() or root.is_symlink():
        raise FederationError("Federation output root already exists")
    root.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=f".{root.name}-", dir=root.parent) as scratch:
        staging = Path(scratch)
        for record, payload in zip(source_records, payloads, strict=True):
            (staging / record["path"]).write_bytes(payload)
        (staging / manifest["result"]["path"]).write_bytes(output)
        (staging / "manifest.json").write_bytes(manifest_bytes)
        read_verified_federation_derivation(staging, selected, held_parents=parents)
        # Own a new empty root before moving any member. The manifest is the
        # final visibility marker; failure cleans only paths created by us.
        root.mkdir(exist_ok=False)
        published: list[Path] = []
        try:
            names = [record["path"] for record in source_records]
            names += [manifest["result"]["path"], "manifest.json"]
            for name in names:
                (staging / name).rename(root / name)
                published.append(root / name)
        except OSError:
            for path in reversed(published):
                path.unlink(missing_ok=True)
            root.rmdir()
            raise
    return selected


def read_verified_federation_derivation(
    root: Path, selected: FederationArtifactRef, *, held_parents: Mapping[str, Path] | None = None
) -> VerifiedFederationResult:
    """Replay actual selected parent bytes; registry membership alone admits nothing."""
    try:
        if held_parents is not None and len(held_parents) > MAX_GRAPH_NODES:
            raise FederationError("Held parent registry exceeds graph profile")
        parents = dict(held_parents or {})
        if len(parents) > MAX_GRAPH_NODES:
            raise FederationError("Held parent registry exceeds graph profile")
        return _read(root, selected, parents, _Budget(), 0)
    except FederationError:
        raise
    except (
        OSError,
        ValueError,
        TypeError,
        KeyError,
        AttributeError,
        OverflowError,
        RecursionError,
    ) as exc:
        raise FederationError("Federation selected artifact is outside the replay profile") from exc


def _read(
    root: Path,
    selected: FederationArtifactRef,
    parents: Mapping[str, Path],
    budget: _Budget,
    depth: int,
) -> VerifiedFederationResult:
    digest = _check_hash(selected.manifest_sha256)
    budget.nodes += 1
    if depth > MAX_GRAPH_DEPTH or budget.nodes > MAX_GRAPH_NODES or digest in budget.active:
        raise FederationError("Federation selected graph exceeds cycle/depth/node profile")
    budget.active.add(digest)
    try:
        return _read_node(root, digest, parents, budget, depth)
    finally:
        budget.active.remove(digest)


def _read_node(
    root: Path, digest: str, parents: Mapping[str, Path], budget: _Budget, depth: int
) -> VerifiedFederationResult:
    manifest, payload = _read_json(root, "manifest.json", budget)
    if _sha(payload) != digest:
        raise FederationError("Federation manifest does not match the independently selected ref")
    expected_fields = {
        "format",
        "sources",
        "request",
        "resolver",
        "result",
        "source_ids_by_cell",
        "source_declarations",
        "basis_status",
        "merge_summary",
        "assurance",
        "limitations",
    }
    if (
        set(manifest) != expected_fields
        or manifest.get("format") != _FORMAT
        or manifest["assurance"] != "software_derivation_candidate"
        or manifest["limitations"]
        != ["consumer_declared_issuer", "no_live_currentness", "no_source_universe_proof"]
        or set(manifest["resolver"]) != {"tie_breaker_seed"}
    ):
        raise FederationError("Unsupported federation derivation format or assurance")
    records = manifest.get("sources")
    if not isinstance(records, list) or not 1 <= len(records) <= MAX_SOURCES:
        raise FederationError("Federation manifest source count exceeds profile")
    request = _restore_request(manifest["request"])
    sources = []
    for position, record in enumerate(records):
        source_digest = _check_hash(record["sha256"])
        if record != {
            "position": position,
            "sha256": source_digest,
            "path": f"source-{position}-{source_digest}.json",
        }:
            raise FederationError("Federation selected source record is not canonical")
        value, source_payload = _read_json(root, record["path"], budget)
        if _sha(source_payload) != source_digest:
            raise FederationError("Federation selected source content mismatch")
        metadata = _restore_metadata(value["metadata"])
        if _metadata_projection(metadata) != value["metadata"]:
            raise FederationError("Source metadata is not exactly replayable")
        if "parent" in value:
            if set(value) != {"parent", "metadata"}:
                raise FederationError(
                    "Selected parent cannot supply child-asserted frame or lineage"
                )
            parent_digest = _check_hash(value["parent"])
            if parent_digest not in parents:
                raise FederationError("Actual selected parent is not held by the fresh reader")
            parent = _read(
                parents[parent_digest],
                FederationArtifactRef(parent_digest),
                parents,
                budget,
                depth + 1,
            )
            budget.frame(*parent.data.shape)
            frame = _selected_parent_carrier(parent.data, parent_digest, position)
        else:
            if set(value) != {"frame", "metadata"}:
                raise FederationError("Leaf source cannot assert derived lineage")
            frame = _restore_frame(value["frame"], budget)
        sources.append((frame, metadata))
    seed = manifest["resolver"]["tie_breaker_seed"]
    if seed is not None and not isinstance(seed, str):
        raise FederationError("Federation resolver seed must be a string or null")
    composer = DataComposer(ConflictResolver(request.conflict_policy, tie_breaker_seed=seed))
    if request.strategy == CompositionStrategy.JOIN:
        output_rows = composer._preflight_join(sources, request)
    else:
        output_rows = sum(len(frame) for frame, _ in sources)
    budget.frame(output_rows, len(set().union(*(set(frame.columns) for frame, _ in sources))))
    if budget.bytes_read > MAX_TOTAL_BYTES - MAX_FILE_BYTES:
        raise FederationError("Selected graph lacks reserved result byte budget")
    recomputed, _ = composer.compose(sources, request.strategy, request)
    projection = frame_projection(recomputed)
    result_digest = _check_hash(manifest["result"]["sha256"])
    if manifest["result"] != {"path": f"result-{result_digest}.json", "sha256": result_digest}:
        raise FederationError("Federation selected result record is not canonical")
    output, output_payload = _read_json(root, manifest["result"]["path"], budget)
    if _sha(output_payload) != result_digest or output != projection:
        raise FederationError("Persisted federation result differs from recomputed composition")
    lineage = recomputed.attrs[_LINEAGE_ATTR]
    if (
        manifest["source_ids_by_cell"] != lineage["rows"]
        or manifest["source_declarations"] != lineage["source_declarations"]
        or manifest["merge_summary"] != _summary(composer)
        or manifest["basis_status"] != lineage["basis_status"]
    ):
        raise FederationError(
            "Persisted federation relation/rule summary differs from actual replay"
        )
    # Retain the recomputed owner carrier itself: copying attrs does not copy its
    # immutable receipt, and arbitrary copied frames require selected replay.
    status = _mark_selected_bytes(recomputed)
    declarations = tuple(
        (token, bounded_encode(declaration).decode())
        for token, declaration in sorted(lineage["source_declarations"].items())
    )
    return VerifiedFederationResult(
        recomputed, tuple(lineage["rows"]), _summary(composer), status, declarations
    )
