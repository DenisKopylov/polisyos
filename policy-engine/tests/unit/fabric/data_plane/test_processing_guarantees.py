from __future__ import annotations

from pathlib import Path

import pytest

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.fabric.connectors.base import ConnectionConfig
from polisyos.fabric.connectors.registry import ConnectorRegistry
from polisyos.fabric.data_plane.cursor_store import CursorStore
from polisyos.fabric.data_plane.streaming import (
    StreamRuntimeOptions,
    process_stream_dataset,
    resolve_dedupe_key,
)
from polisyos.fabric.quality.processing_guarantees import (
    AtomicityProof,
    CDCSchemaCompatibility,
    OutOfOrderPolicy,
    ProcessingGuarantee,
    ProcessingGuaranteeContract,
    classify_cdc_schema_change,
    stream_processing_contract,
)


def _valid_rows(batch, **kwargs):
    del kwargs
    return [dict(row) for row in batch if isinstance(row, dict)], [], 0


def test_exactly_once_narrow_requires_atomic_proof() -> None:
    with pytest.raises(ValueError, match="exactly_once_narrow"):
        ProcessingGuaranteeContract(guarantee=ProcessingGuarantee.EXACTLY_ONCE_NARROW)

    contract = ProcessingGuaranteeContract(
        guarantee=ProcessingGuarantee.EXACTLY_ONCE_NARROW,
        atomicity_proof=AtomicityProof(
            input_offsets_committed_atomically=True,
            state_updates_committed_atomically=True,
            output_writes_committed_atomically=True,
            proof_refs=("docs/adr/0133-fabric-streaming-scale-semantics.md",),
        ),
    )

    assert contract.atomicity_proof is not None
    assert contract.atomicity_proof.complete


def test_cdc_schema_change_compatibility_classification() -> None:
    assert (
        classify_cdc_schema_change(("id", "value"), ("id", "value", "label"))
        == CDCSchemaCompatibility.COMPATIBLE_ADDITIVE
    )
    assert (
        classify_cdc_schema_change(("id", "value"), ("id",))
        == CDCSchemaCompatibility.INCOMPATIBLE_BREAKING
    )
    assert (
        classify_cdc_schema_change(("id", "value"), ("value", "id"))
        == CDCSchemaCompatibility.METADATA_ONLY
    )


def test_missing_dedupe_key_can_quarantine_instead_of_hashing() -> None:
    assert resolve_dedupe_key({"value": 1}, fields=("id",)) != ""
    assert (
        resolve_dedupe_key(
            {"value": 1},
            fields=("id",),
            missing_key_action="quarantine",
        )
        == ""
    )


@pytest.mark.asyncio
async def test_stream_processing_quarantines_late_events_by_watermark(
    tmp_path: Path,
) -> None:
    stream_path = tmp_path / "events.jsonl"
    stream_path.write_text(
        "\n".join(
            [
                '{"_message_id":"m1","event_time":"2024-06-15T12:00:30+00:00","value":1}',
                '{"_message_id":"m2","event_time":"2024-06-15T12:00:00+00:00","value":2}',
                '{"_message_id":"m3","event_time":"2024-06-15T12:00:40+00:00","value":3}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    ConnectorRegistry.reset_instance()
    registry = ConnectorRegistry.get_instance()
    registry.set_default_config(
        "stream.jsonl",
        ConnectionConfig(
            url=stream_path.as_uri(),
            headers={"X-Stream-ChunkSize": "3"},
        ),
    )
    processing = stream_processing_contract().model_copy(
        update={
            "out_of_order": OutOfOrderPolicy(
                handling="watermark",
                max_lateness_seconds=5,
                late_event_action="quarantine",
            )
        }
    )

    result = await process_stream_dataset(
        connector_id="stream.jsonl",
        dataset_id="events",
        store=FileSystemCAS(tmp_path / ".polisyos"),
        cursor_store=CursorStore(FileSystemCAS(tmp_path / ".polisyos")),
        sanitize_rows=_valid_rows,
        runtime_options=StreamRuntimeOptions(processing_contract=processing),
        registry=registry,
    )

    assert result.processing_guarantee == "at_least_once_with_dedupe"
    assert result.rows_emitted == 2
    assert result.out_of_order_rows == 1
    assert result.late_rows_quarantined == 1
    assert result.final_cursor is not None
    assert result.final_cursor.metadata["processing"]["out_of_order"]["handling"] == "watermark"
