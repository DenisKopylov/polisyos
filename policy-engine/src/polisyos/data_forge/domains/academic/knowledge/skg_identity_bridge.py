"""Recompute retained SKG reference identity without certifying scientific claims.

This source identity component persists a small, replayable row bundle. It proves
only that the named rows and their joins occur in the independently supplied
snapshot bytes. Stored extraction, confidence, units and links remain candidate
data. This module does not admit a certified SKG bridge, a world model, an effect,
native uncertainty, target transport, calibration or a production N8 value.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

import duckdb
from pydantic import BaseModel, ConfigDict, Field

from polisyos.core import artifacts

if TYPE_CHECKING:
    from pathlib import Path

_KIND = "academic.source_reference_identity"
_SCHEMA_VERSION = "1.0"


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


@dataclass(frozen=True)
class SourceSnapshot:
    """Owner-selected source bytes; never inferred from a candidate CAS payload.

    Attributes:
        path: Read-only local snapshot location.
        reference: Owner's snapshot reference, carried verbatim for audit.
        sha256: Expected full-file SHA-256; always recomputed at intake and replay.
    """

    path: Path
    reference: str
    sha256: str


class SourceIdentitySelection(_StrictModel):
    """Exact retained references to resolve, with no fuzzy or numeric-value join."""

    numeric_id: str = Field(min_length=1)
    claim_id: str = Field(min_length=1)
    edge_id: str = Field(min_length=1)
    work_id: str = Field(min_length=1)
    skg_version: int = Field(ge=1)


class SourceCell(_StrictModel):
    """Native typed text checked by a database round-trip before Python conversion.

    This preserves the relational value, not unmeasured physical payload bits
    such as distinct NaN encodings. The full snapshot digest binds physical bytes.
    """

    name: str
    database_type: str
    encoding: Literal["duckdb_varchar_roundtrip"] = "duckdb_varchar_roundtrip"
    value: str | None


class SourceRow(_StrictModel):
    """A complete ordered row; hashes bind all columns, not selected markers."""

    table: str
    cells: tuple[SourceCell, ...]
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class SourceIdentityBundle(_StrictModel):
    """Audit projection whose positive grade is limited to reference identity.

    Construction alone carries no verification authority. Consumers must call
    ``replay_source_identity_bundle`` with their separately selected source.
    """

    schema_version: Literal["1.0"] = "1.0"
    purpose: Literal["source_reference_identity_only"] = "source_reference_identity_only"
    source_reference: str
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    selection: SourceIdentitySelection
    status: Literal["source_reference_identity_recomputed", "refused"]
    rows: tuple[SourceRow, ...]
    refusal_reasons: tuple[str, ...]
    source_snapshot_authenticity: Literal["not_established"] = "not_established"
    numeric_semantics: Literal["not_established"] = "not_established"
    native_uncertainty: Literal["not_established"] = "not_established"
    causal_identification: Literal["not_established"] = "not_established"
    world_binding: Literal["not_established"] = "not_established"
    target_transport: Literal["not_established"] = "not_established"
    calibration: Literal["not_established"] = "not_established"
    n8_admission: Literal["blocked"] = "blocked"
    production_value_eligible: Literal[False] = False


def _json_bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def _require_snapshot(source: SourceSnapshot) -> None:
    if not source.reference or len(source.sha256) != 64:
        raise ValueError("source_snapshot_identity_invalid")
    resolved = source.path.resolve()
    if resolved.with_name(resolved.name + ".wal").exists():
        raise ValueError("source_snapshot_wal_not_bound")
    with resolved.open("rb") as stream:
        actual = hashlib.file_digest(stream, "sha256").hexdigest()
    if actual != source.sha256:
        raise ValueError("source_snapshot_hash_mismatch")


def _retained_columns(con: duckdb.DuckDBPyConnection, table: str) -> list[tuple]:
    relation = con.execute(
        "SELECT table_type FROM information_schema.tables "
        "WHERE table_catalog=current_database() AND table_schema='main' AND table_name=?",
        [table],
    ).fetchall()
    if relation != [("BASE TABLE",)]:
        raise ValueError(f"source_relation_not_retained_base_table:{table}")
    # Table/predicate are fixed by the owner below; only values come from callers.
    cursor = con.execute(f"SELECT * FROM main.{table} LIMIT 0")  # noqa: S608
    description = cursor.description
    stored_columns = {
        row[0]
        for row in con.execute(
            "SELECT DISTINCT column_name FROM pragma_storage_info(?)",
            [table],
        ).fetchall()
    }
    if any(column[0] not in stored_columns for column in description):
        raise ValueError(f"source_column_not_materialized:{table}")
    return description


def _read_row(
    con: duckdb.DuckDBPyConnection,
    table: str,
    predicate: str,
    parameters: list[str | int],
) -> SourceRow:
    description = _retained_columns(con, table)
    projections = []
    for column in description:
        identifier = '"' + column[0].replace('"', '""') + '"'
        text = f"CAST({identifier} AS VARCHAR)"
        projections.extend(
            (
                text,
                f"(CAST({text} AS {column[1]}) IS NOT DISTINCT FROM {identifier})",
            )
        )
    # Column names/types are native schema objects, quoted/rendered by their owner.
    query = f"SELECT {', '.join(projections)} FROM main.{table} WHERE {predicate}"  # noqa: S608
    values = con.execute(query, parameters).fetchall()
    if len(values) != 1:
        raise ValueError(f"source_row_missing_or_ambiguous:{table}")
    cells = []
    for index, column in enumerate(description):
        value, roundtrip = values[0][index * 2 : index * 2 + 2]
        if roundtrip is not True:
            raise ValueError(f"source_native_value_roundtrip_failed:{table}:{column[0]}")
        cells.append(SourceCell(name=column[0], database_type=str(column[1]), value=value))
    encoded = {"table": table, "cells": [cell.model_dump(mode="json") for cell in cells]}
    return SourceRow(
        table=table,
        cells=tuple(cells),
        sha256=hashlib.sha256(
            _json_bytes(encoded),
        ).hexdigest(),
    )


def _values(row: SourceRow) -> dict[str, str | None]:
    return {cell.name: cell.value for cell in row.cells}


def _reference_list(value: object) -> list[str]:
    if not isinstance(value, str):
        raise ValueError("source_reference_list_malformed")
    decoded = json.loads(value)
    if not isinstance(decoded, list) or any(not isinstance(item, str) for item in decoded):
        raise ValueError("source_reference_list_malformed")
    return decoded


def _require_joins(rows: tuple[SourceRow, ...], selection: SourceIdentitySelection) -> None:
    numeric, claim, evidence, edge, article, work, version = map(_values, rows)
    if selection.claim_id not in _reference_list(numeric["linked_claim_ids_json"]):
        raise ValueError("source_numeric_claim_link_mismatch")
    if selection.edge_id not in _reference_list(numeric["linked_edges_json"]):
        raise ValueError("source_numeric_edge_link_mismatch")
    if any(
        value != selection.work_id
        for value in (
            numeric["openalex_id"],
            claim["work_id"],
            evidence["openalex_id"],
            article["openalex_id"],
            work["id"],
        )
    ):
        raise ValueError("source_work_join_mismatch")
    if any(
        value != str(selection.skg_version)
        for value in (
            evidence["skg_version"],
            article["skg_version"],
            version["version_id"],
        )
    ):
        raise ValueError("source_version_join_mismatch")
    if (claim["cause"], claim["effect"], claim["direction"]) != (
        evidence["src"],
        evidence["dst"],
        evidence["direction"],
    ) or (edge["src"], edge["dst"], edge["direction"]) != (
        evidence["src"],
        evidence["dst"],
        evidence["direction"],
    ):
        raise ValueError("source_claim_edge_subject_mismatch")


def _recompute(
    *,
    source: SourceSnapshot,
    selection: SourceIdentitySelection,
    scratch: Path,
) -> SourceIdentityBundle:
    _require_snapshot(source)
    # Revalidate even an in-process model_construct/model_copy input.
    selection = SourceIdentitySelection.model_validate_json(selection.model_dump_json())
    scratch.mkdir(parents=True, exist_ok=True)
    rows: list[SourceRow] = []
    reasons: tuple[str, ...] = ()
    queries = (
        ("ac_skg_simulation_parameters", "numeric_id=?", [selection.numeric_id]),
        ("ac_causal_claims", "id=?", [selection.claim_id]),
        (
            "ac_skg_edge_evidence",
            "claim_id=? AND edge_id=? AND openalex_id=? AND skg_version=?",
            [selection.claim_id, selection.edge_id, selection.work_id, selection.skg_version],
        ),
        ("ac_skg_edges", "edge_id=?", [selection.edge_id]),
        ("ac_skg_articles", "openalex_id=?", [selection.work_id]),
        ("ac_works", "id=?", [selection.work_id]),
        ("ac_skg_versions", "version_id=?", [selection.skg_version]),
    )
    with duckdb.connect(
        str(source.path),
        read_only=True,
        config={"temp_directory": str(scratch.resolve())},
    ) as con:
        # Configure spill before locking external access; no source query precedes the lock.
        con.execute("SET enable_external_access = false")
        try:
            for table, predicate, parameters in queries:
                rows.append(_read_row(con, table, predicate, parameters))
            _require_joins(tuple(rows), selection)
        except (ValueError, KeyError, duckdb.Error) as exc:
            # This is a persisted source refusal, never a successful empty chain.
            reasons = (f"{type(exc).__name__}:{exc}",)
    _require_snapshot(source)
    return SourceIdentityBundle(
        source_reference=source.reference,
        source_sha256=source.sha256,
        selection=selection,
        status="refused" if reasons else "source_reference_identity_recomputed",
        rows=tuple(rows),
        refusal_reasons=reasons,
    )


def produce_source_identity_bundle(
    *,
    source: SourceSnapshot,
    selection: SourceIdentitySelection,
    store: artifacts.FileSystemCAS,
    scratch: Path,
) -> artifacts.ArtifactRef:
    """Resolve exact retained rows and persist the narrow result for audit/replay.

    A mismatched expected snapshot raises; missing or inconsistent source joins
    persist a typed refusal. No database bytes are copied into CAS.
    """
    bundle = _recompute(source=source, selection=selection, scratch=scratch)
    ref = store.put_bytes(
        _json_bytes(bundle.model_dump(mode="json")),
        artifacts.ArtifactWriteOptions(
            kind=_KIND,
            media_type="application/json",
            schema=artifacts.SchemaInfo(name=_KIND, version=_SCHEMA_VERSION),
            producer=artifacts.ProducerInfo(component=__name__, version=_SCHEMA_VERSION),
        ),
    )
    replay_source_identity_bundle(
        ref=ref,
        source=source,
        selection=selection,
        store=store,
        scratch=scratch,
    )
    return ref


def _require_same_bundle(persisted: SourceIdentityBundle, current: SourceIdentityBundle) -> None:
    if _json_bytes(persisted.model_dump(mode="json")) != _json_bytes(
        current.model_dump(mode="json")
    ):
        raise ValueError("source_identity_bundle_replay_mismatch")


def replay_source_identity_bundle(
    *,
    ref: artifacts.ArtifactRef,
    source: SourceSnapshot,
    selection: SourceIdentitySelection,
    store: artifacts.FileSystemCAS,
    scratch: Path,
) -> SourceIdentityBundle:
    """Consume CAS bytes only after complete current-source recomputation.

    The owner source is an explicit separate argument: an artifact cannot appoint
    its own root. Even a valid new CAS object is rejected if its rows, hashes,
    outcome or limitations differ from recomputation. The returned DTO is an
    audit projection, not a transferable production authority token.
    """
    manifest = store.get_manifest(ref.artifact_id)
    if (
        manifest.kind != _KIND
        or manifest.artifact_schema is None
        or (manifest.artifact_schema.name, manifest.artifact_schema.version)
        != (_KIND, _SCHEMA_VERSION)
    ):
        raise ValueError("source_identity_bundle_schema_mismatch")
    persisted = SourceIdentityBundle.model_validate_json(store.get_bytes(ref.artifact_id))
    selection = SourceIdentitySelection.model_validate_json(selection.model_dump_json())
    if persisted.selection != selection:
        raise ValueError("source_identity_selection_mismatch")
    if (persisted.source_reference, persisted.source_sha256) != (
        source.reference,
        source.sha256,
    ):
        raise ValueError("source_snapshot_owner_binding_mismatch")
    current = _recompute(source=source, selection=selection, scratch=scratch)
    _require_same_bundle(persisted, current)
    return current
