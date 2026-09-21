"""Characterization witnesses for the UDF-02 domain I/O and bindings move."""

from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pandas.testing as pdt
import pytest

from polisyos.data_forge.domains.ukraine.models import build_default_pipeline_config

pytestmark = pytest.mark.unit


def _load_builder_surface() -> tuple[Any, ...]:
    """Load canonical and compatibility builder modules at test time."""
    return tuple(
        importlib.import_module(f"polisyos.data_forge.domains.ukraine.builders{suffix}")
        for suffix in (
            ".io",
            ".bindings_validation",
            ".common",
            ".sources",
            ".release",
            ".governance_handoff",
            "",
        )
    )


def test_io_and_bindings_helpers_have_canonical_owners_and_compatibility_aliases() -> None:
    """Consumers and the package facade point at the moved owners."""
    io, bindings, common, sources, release, governance_handoff, builders = _load_builder_surface()

    assert io._write_json.__module__ == io.__name__
    assert io._write_frame.__module__ == io.__name__
    assert io._write_npz.__module__ == io.__name__
    assert common._write_json is io._write_json
    assert common._write_frame is io._write_frame
    assert sources._write_json is io._write_json
    assert release._write_json is io._write_json
    assert governance_handoff._write_json is io._write_json
    assert builders._write_json is io._write_json

    assert bindings._build_synthetic_multiscale_payload.__module__ == bindings.__name__
    assert bindings._validation_subset.__module__ == bindings.__name__
    assert sources._build_synthetic_multiscale_payload is (
        bindings._build_synthetic_multiscale_payload
    )
    assert common._build_synthetic_multiscale_payload is (
        bindings._build_synthetic_multiscale_payload
    )
    assert builders._validation_subset is bindings._validation_subset

    assert common.MemoryAwareScheduler.__module__ == common.__name__
    assert common.ScheduledTask.__module__ == common.__name__


def test_json_writer_preserves_sorted_ascii_bytes(tmp_path: Path) -> None:
    """The relocated JSON serializer keeps the legacy byte profile."""
    io, *_ = _load_builder_surface()
    path = tmp_path / "nested" / "payload.json"

    assert io._write_json(path, {"z": 1, "a": ["x"]}) == path
    assert path.read_bytes() == b'{\n  "a": [\n    "x"\n  ],\n  "z": 1\n}'


def test_npz_writer_preserves_arrays_and_nonzero_metadata(tmp_path: Path) -> None:
    """The relocated NPZ writer preserves compressed array contents and nnz."""
    io, *_ = _load_builder_surface()
    path = tmp_path / "nested" / "graph.npz"
    weight = np.asarray([0.0, 2.5, 0.0], dtype=float)

    record = io._write_npz(path, weight=weight, node_ids=np.asarray(["a", "b", "c"]))

    with np.load(path, allow_pickle=True) as loaded:
        np.testing.assert_array_equal(loaded["weight"], weight)
        np.testing.assert_array_equal(loaded["node_ids"], np.asarray(["a", "b", "c"]))
    assert record.nnz == 1


def test_parquet_writer_preserves_frame_profile(tmp_path: Path) -> None:
    """The relocated Parquet writer preserves rows, columns, and artifact count."""
    io, *_ = _load_builder_surface()
    path = tmp_path / "nested" / "observations.parquet"
    frame = pd.DataFrame({"entity_id": ["a", "b"], "value": [1.5, 2.0]})

    record = io._write_frame(path, frame)

    pdt.assert_frame_equal(pd.read_parquet(path), frame)
    assert record.row_count == len(frame)


def test_procurement_selection_preserves_source_warning_profile(tmp_path: Path) -> None:
    """Procurement source selection retains the existing warning and source id."""
    io, _, _, sources, *_ = _load_builder_surface()
    config = build_default_pipeline_config(root=tmp_path / "ukraine")
    proxy_path = (
        config.build_root.normalized_dir
        / "spending_contracts_procurement_proxy"
        / "procurement_contracts_monthly.parquet"
    )
    proxy_path.parent.mkdir(parents=True, exist_ok=True)
    expected = pd.DataFrame(
        {
            "buyer_agent_id": ["11111111"],
            "supplier_agent_id": ["22222222"],
            "amount": [100.0],
            "period_id": ["2024-01"],
            "registration_code": ["11111111"],
        }
    )
    expected.to_parquet(proxy_path, index=False)

    frame, source_id, warnings = io._select_procurement_frame(config)

    pdt.assert_frame_equal(frame, expected)
    assert sources._select_procurement_frame is io._select_procurement_frame
    assert source_id == "spending_contracts_procurement_proxy"
    assert warnings == ["procurement_source_selected:spending_contracts_procurement_proxy"]


def test_json_writer_propagates_kernel_atomic_write_errors(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Atomic writer failures remain visible to domain callers."""
    io, *_ = _load_builder_surface()

    def fail_atomic_write(_path: Path, _payload: str) -> Path:
        raise OSError("atomic write witness")

    monkeypatch.setattr(io, "atomic_write_text", fail_atomic_write)

    with pytest.raises(OSError, match="atomic write witness"):
        io._write_json(tmp_path / "payload.json", {"ok": True})


def test_synthetic_bindings_payload_remains_explicitly_non_observational() -> None:
    """The binding smoke payload keeps its synthetic-only shape and owner."""
    _, bindings, *_ = _load_builder_surface()
    payload = bindings._build_synthetic_multiscale_payload(
        pd.DataFrame(
            {
                "agent_id": ["agent::1"],
                "revenue": [100.0],
                "employees": [2.0],
            }
        ),
        pd.DataFrame(),
        pd.DataFrame(),
    )

    assert bindings._build_synthetic_multiscale_payload.__module__ == bindings.__name__
    assert set(payload) == {"agents", "firms", "cells", "household_cells"}
    assert "observations" not in payload
    assert "observation_id" not in payload
