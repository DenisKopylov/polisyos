"""Explicit finite source-owner fixtures for progress/identity property tests."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from polisyos.fabric.connectors.contracts import (
    ConnectorSchemaContract,
    DataSchema,
    FieldSpec,
    SchemaType,
    SchemaVersion,
)
from polisyos.fabric.connectors.contracts.source_contract import (
    SourceContract,
    SourceProgressContract,
)
from polisyos.fabric.ingestion.source_progress import FiniteSourceProgressReader

SOURCE_TIME = datetime(2026, 1, 1, tzinfo=UTC)


def finite_source_reader(
    root: Path,
    *,
    connector_id: str,
    dataset_id: str,
    schema_id: str,
    snapshots: list[tuple[str, list[dict[str, Any]]]],
    event_fields: tuple[str, ...] = ("event_id",),
    version_fields: tuple[str, ...] = ("source_version",),
    transport_path: Path | None = None,
    partition_key: str = "default",
) -> FiniteSourceProgressReader:
    """Create an actual complete source fixture before any connector executes.

    The runtime reader receives only the owner contract and root, not this row
    list or a completeness/count assertion. Tests change connector output while
    leaving this independent actual source file untouched.
    """
    root.mkdir(parents=True, exist_ok=True)
    names = sorted(
        {key for _version, rows in snapshots for row in rows for key in row}
        | set(event_fields + version_fields)
    )
    schema = DataSchema(
        schema_id=schema_id,
        version=SchemaVersion(1, 0, 0),
        fields=tuple(
            FieldSpec(
                name=name,
                data_type=(
                    SchemaType.INT64
                    if (
                        values := [
                            row[name] for _version, rows in snapshots for row in rows if name in row
                        ]
                    )
                    and all(type(value) is int for value in values)
                    else SchemaType.STRING
                ),
            )
            for name in names
        ),
    )
    schema_contract = ConnectorSchemaContract(
        contract_id=schema_id,
        connector_id=connector_id,
        dataset_id=dataset_id,
        schema=schema,
    )
    fixture_path = root / (schema_id + ".json")
    if transport_path is not None:
        import os

        root = Path(os.path.commonpath([root.resolve(), transport_path.resolve().parent]))
    fixture_name = fixture_path.relative_to(root).as_posix()
    source = SourceContract.from_connector_schema_contract(
        schema_contract,
        profile_id="finite_fixture",
        owner="finite-fixture-author",
        reviewer="finite-fixture-reviewer",
        replay_fixture_ref=fixture_name,
        domain="testing",
    )
    source = source.model_copy(
        update={
            "source_trust": source.source_trust.model_copy(
                update={
                    "tier": "synthetic",
                    "calibration_status": "unknown",
                    "rationale": "Finite software-property fixture; no production authority.",
                }
            )
        }
    )
    extension = SourceProgressContract(
        source_contract_id=source.id,
        source_contract_version=source.version,
        source_contract_content_hash=source.content_hash,
        schema_id=schema.schema_id,
        schema_version_bound=str(schema.version),
        schema_content_hash=schema.content_hash,
        connector_id=connector_id,
        dataset_id=dataset_id,
        event_fields=event_fields,
        version_fields=version_fields,
        version_strategy="etag",
        transport_kind="jsonl_file" if transport_path is not None else "finite_history_file",
        transport_fixture_ref=transport_path.resolve().relative_to(root.resolve()).as_posix()
        if transport_path is not None
        else None,
        partition_key=partition_key,
    )
    reader = FiniteSourceProgressReader(root, source, extension)
    write_source_history(reader, snapshots)
    return reader


def write_source_history(
    reader: FiniteSourceProgressReader,
    snapshots: list[tuple[str, list[dict[str, Any]]]],
) -> None:
    """Append an independently authored source state to the finite owner file."""
    payload = {
        "schema_version": "fabric.finite_source_history.v1",
        "connector_id": reader.extension.connector_id,
        "dataset_id": reader.extension.dataset_id,
        "current_version": snapshots[-1][0],
        "snapshots": [
            {
                "version": {
                    "strategy": "etag",
                    "value": version,
                    "timestamp": SOURCE_TIME.isoformat(),
                },
                "rows": rows,
            }
            for version, rows in snapshots
        ],
    }
    (reader.source_root / str(reader.source_contract.replay.fixture_ref)).write_text(
        json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8"
    )
