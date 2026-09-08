"""Removal probes for snapshot-vintage preservation at the shard merge boundary."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import duckdb
import pytest

from polisyos.data_forge.domains.academic.knowledge import skg_versioning
from tools.ops_runners.cloud import merge_shards

_LOOKALIKE_METADATA = {
    "confidence_layer_vintage": {
        "claim_evidence_axis": "present",
        "consumer_action": "forward_confidence",
    },
    "metadata": {"simulation_ready_numeric_estimates": [{"evidence_strength": "rct"}]},
}


def _digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _shard(path: Path, identity: str) -> Path:
    with duckdb.connect(str(path)) as con:
        con.execute(
            "CREATE TABLE ac_skg_edges "
            "(edge_id VARCHAR PRIMARY KEY, confidence DOUBLE, quality_signals_json VARCHAR)"
        )
        con.execute(
            "INSERT INTO ac_skg_edges VALUES (?, 0.83, ?)",
            [identity, json.dumps(_LOOKALIKE_METADATA)],
        )
    return path


@pytest.mark.parametrize("restricted_index", range(3))
@pytest.mark.parametrize("existing_destination", [False, True])
def test_merge_refuses_every_restricted_input_before_destination_write(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    restricted_index: int,
    existing_destination: bool,
) -> None:
    """Removing vintage enforcement must allow a destination while all markers remain."""
    shards = [_shard(tmp_path / f"shard-{index}.duckdb", f"e{index}") for index in range(3)]
    input_digests = [_digest(path) for path in shards]
    monkeypatch.setattr(
        skg_versioning, "_HISTORICAL_SNAPSHOT_SHA256", input_digests[restricted_index]
    )
    output = tmp_path / "destination" / "scholar_knowledge.duckdb"
    if existing_destination:
        output.parent.mkdir()
        _shard(output, "preserve-previous-output")
    previous_output = output.read_bytes() if existing_destination else None

    with pytest.raises(ValueError, match="not_reproducible_under_current_rule") as refused:
        merge_shards.merge_duckdb(shards, output)

    declaration = json.loads(str(refused.value))["confidence_layer_vintage"]
    assert declaration["snapshot_sha256"] == input_digests[restricted_index]
    assert declaration["consumer_action"] == "withhold_confidence_forwarding"
    if existing_destination:
        assert output.read_bytes() == previous_output
    else:
        assert not output.parent.exists()
    assert [_digest(path) for path in shards] == input_digests

    # Removal control: only the declaration producer disappears. All input bytes,
    # field definitions and the runner's guard calls stay. A destination is now made;
    # this is not a claim that the runner correctly merges every secondary table.
    monkeypatch.setattr(skg_versioning, "confidence_layer_vintage", lambda db_path: None)
    merge_shards.merge_duckdb(shards, output)
    with duckdb.connect(str(output), read_only=True) as con:
        row = con.execute(
            "SELECT confidence, quality_signals_json FROM ac_skg_edges WHERE edge_id = 'e0'"
        ).fetchone()
    assert row is not None
    assert row[0] == 0.83
    assert json.loads(row[1]) == _LOOKALIKE_METADATA
    assert [_digest(path) for path in shards] == input_digests
