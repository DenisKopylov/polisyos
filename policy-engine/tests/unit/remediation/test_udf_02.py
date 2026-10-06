"""Characterization witnesses for the UDF-02 domain I/O and bindings move."""

from __future__ import annotations

import hashlib
import importlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pandas.testing as pdt
import pytest

from polisyos.data_forge.domains.ukraine.builders import (
    STAGE_BUILDERS,
    bindings_validation,
    demography,
    release,
)
from polisyos.data_forge.domains.ukraine.builders import sources as source_builders
from polisyos.data_forge.domains.ukraine.manifests import (
    ArtifactRecord,
    BuildRunManifest,
    NormalizedArtifactManifest,
    PartAGateManifest,
    load_manifest,
    write_manifest,
)
from polisyos.data_forge.domains.ukraine.models import StageId, build_default_pipeline_config
from polisyos.data_forge.domains.ukraine.orchestrator import UkraineDataOrchestrator

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


def _minimal_source_frame(source_id: str, required_columns: list[str]) -> pd.DataFrame:
    """Make tiny normalized source rows that exercise real Ukraine stage builders."""
    if source_id == "edr_current":
        return pd.DataFrame(
            {
                "agent_id": ["agent::1", "agent::2"],
                "registration_code": ["11111111", "22222222"],
                "tax_id": ["11111111", "22222222"],
                "edrpou": ["11111111", "22222222"],
                "name": ["Entity One", "Entity Two"],
                "region_code": ["01", "02"],
                "sector_id": ["A", "B"],
                "region_numeric": [1, 2],
                "revenue": [100.0, 200.0],
                "assets": [80.0, 160.0],
                "liabilities": [20.0, 40.0],
                "employees": [2.0, 4.0],
                "longitude": [30.0, 31.0],
                "latitude": [50.0, 51.0],
                "cell_id": ["cell::01::A", "cell::02::B"],
            }
        )
    if source_id == "spending_full":
        return pd.DataFrame(
            {
                "source_agent_id": ["11111111"],
                "target_agent_id": ["22222222"],
                "amount": [100.0],
                "period_id": ["2024-01"],
                "registration_code": ["11111111"],
            }
        )
    if source_id in {"spending_contracts_procurement_proxy", "prozorro_full"}:
        return pd.DataFrame(
            {
                "buyer_agent_id": ["11111111"],
                "supplier_agent_id": ["22222222"],
                "supplier_name": ["Entity Two"],
                "amount": [50.0],
                "period_id": ["2024-01"],
                "registration_code": ["11111111"],
            }
        )
    if source_id == "macro_nbu_derzhstat":
        return pd.DataFrame(
            {
                "period_id": ["2024-01"],
                "metric_id": ["gdp"],
                "observed_value": [1.0],
                "region_code": ["01"],
            }
        )
    if source_id == "dps_financials":
        return pd.DataFrame(
            {
                "agent_id": ["agent::1"],
                "registration_code": ["11111111"],
                "period_id": ["2024"],
                "revenue": [100.0],
                "assets": [80.0],
                "liabilities": [20.0],
                "employees": [2.0],
            }
        )

    rows: list[dict[str, object]] = []
    for index, (agent_id, registration_code) in enumerate(
        (("agent::1", "11111111"), ("agent::2", "22222222"))
    ):
        row: dict[str, object] = {}
        for column in required_columns:
            if column in {"agent_id", "source_agent_id", "buyer_agent_id"}:
                row[column] = agent_id
            elif column in {"target_agent_id", "supplier_agent_id"}:
                row[column] = "agent::2" if index == 0 else "agent::1"
            elif column == "registration_code":
                row[column] = registration_code
            elif column == "period_id":
                row[column] = "2024-01"
            elif column == "region_code":
                row[column] = "01"
            elif column == "sector_id":
                row[column] = "A"
            elif column == "cell_id":
                row[column] = "cell::01::A"
            elif column == "metric_id":
                row[column] = f"{source_id}_metric"
            elif column == "name":
                row[column] = f"Entity {index + 1}"
            else:
                row[column] = 1.0
        rows.append(row)
    return pd.DataFrame.from_records(rows, columns=required_columns)


def _seed_normalized_sources(orchestrator: UkraineDataOrchestrator, stage_id: StageId) -> None:
    """Persist minimal normalized inputs so the registered route never fetches sources."""
    config = orchestrator.config
    stage = config.stages[stage_id.value]
    for source_id in stage.required_sources:
        source = config.sources[source_id]
        frame = _minimal_source_frame(source_id, source.required_columns)
        artifact_path = (
            config.build_root.normalized_dir / source_id / source.normalized_artifact
        )
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        frame.to_parquet(artifact_path, index=False)
        manifest_path = config.build_root.manifests_dir / source_id / source.manifest_name
        write_manifest(
            manifest_path,
            NormalizedArtifactManifest(
                source_id=source_id,
                stage_id=source.stage_id,
                status="completed",
                normalized_artifact=ArtifactRecord.from_path(
                    artifact_path,
                    row_count=len(frame),
                ),
                schema_version="1.0",
            ),
        )


def _recorded_output_bytes(result: Any) -> dict[str, bytes | dict[str, bytes]]:
    """Snapshot real builder bytes for parity against the registered consumer route."""
    contents: dict[str, bytes | dict[str, bytes]] = {}
    for name, record in result.outputs.items():
        path = Path(record.path)
        if path.is_dir():
            contents[name] = {
                child.relative_to(path).as_posix(): child.read_bytes()
                for child in sorted(path.rglob("*"))
                if child.is_file()
            }
        else:
            contents[name] = path.read_bytes()
    return contents


def _assert_registered_stage_output_parity(
    orchestrator: UkraineDataOrchestrator,
    stage_id: StageId,
    direct_result: Any,
    expected_bytes: dict[str, bytes | dict[str, bytes]],
) -> None:
    """Prove the registered route persists the exact direct builder artifacts."""
    summary = orchestrator.build_stage(stage_id)
    persisted = load_manifest(orchestrator.stage_manifest_path(stage_id), BuildRunManifest)
    assert summary.status == "completed"
    assert persisted.model_dump(mode="json") == summary.manifest.model_dump(mode="json")
    actual_records = {Path(record.path).name: record for record in persisted.outputs}
    expected_names = {Path(record.path).name for record in direct_result.outputs.values()}
    assert set(actual_records) == set(expected_names)
    for name, record in direct_result.outputs.items():
        actual = actual_records[Path(record.path).name]
        assert isinstance(actual, ArtifactRecord)
        actual_path = Path(actual.path)
        if isinstance(expected_bytes[name], dict):
            actual_contents = {
                child.relative_to(actual_path).as_posix(): child.read_bytes()
                for child in sorted(actual_path.rglob("*"))
                if child.is_file()
            }
            assert actual_contents == expected_bytes[name]
            # Directory records intentionally carry a size but no synthetic file hash.
            assert actual.sha256 == record.sha256 == ""
            assert actual.size_bytes == record.size_bytes
        else:
            actual_bytes = actual_path.read_bytes()
            if name == "d5_release_handoff_request.json":
                expected_payload = json.loads(expected_bytes[name])
                actual_payload = json.loads(actual_bytes)
                expected_created_at = expected_payload.pop("created_at")
                actual_created_at = actual_payload.pop("created_at")
                datetime.fromisoformat(expected_created_at).astimezone(UTC)
                datetime.fromisoformat(actual_created_at).astimezone(UTC)
                assert expected_payload["time_role"] == "producer_handoff_created_at"
                assert actual_payload["time_role"] == "producer_handoff_created_at"
                assert actual_payload == expected_payload
            elif name == "release_manifest_v1.json":
                expected_payload = json.loads(expected_bytes[name])
                actual_payload = json.loads(actual_bytes)
                expected_handoff = expected_payload["evidence_refs"][
                    "d5_release_handoff_request"
                ]
                actual_handoff = actual_payload["evidence_refs"]["d5_release_handoff_request"]
                expected_handoff_sha = expected_handoff.pop("sha256")
                actual_handoff_sha = actual_handoff.pop("sha256")
                assert expected_handoff_sha == hashlib.sha256(
                    expected_bytes["d5_release_handoff_request.json"]
                ).hexdigest()
                assert actual_handoff_sha == hashlib.sha256(
                    Path(
                        actual_records["d5_release_handoff_request.json"].path
                    ).read_bytes()
                ).hexdigest()
                assert actual_payload == expected_payload
            else:
                assert actual_bytes == expected_bytes[name], name
            assert actual.sha256 == hashlib.sha256(actual_bytes).hexdigest()
            assert actual.size_bytes == actual_path.stat().st_size


def test_registered_stage_routes_preserve_split_builder_bytes_for_all_importers(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Registered D0/P0,D1,D2,D4,D5 outputs equal each canonical builder's bytes."""
    pytest.importorskip("pyarrow")
    pytest.importorskip("duckdb")

    from polisyos.data_forge.domains.ukraine.builders import (
        build_d0_p0_stage,
        build_d1_stage,
        build_d2_stage,
        build_d4_stage,
        build_d5_stage,
    )
    config = build_default_pipeline_config(root=tmp_path / "registered-ukraine")
    config.server.require_server_for_build = False
    orchestrator = UkraineDataOrchestrator(config)
    orchestrator.ensure_layout()
    write_manifest(
        config.build_root.part_a_gate_manifest_path,
        PartAGateManifest(status="passed", passed=True),
    )
    _seed_normalized_sources(orchestrator, StageId.D0_P0)
    _seed_normalized_sources(orchestrator, StageId.D1)
    monkeypatch.setenv("POLISYOS_UKRAINE_DATA_D1_CONTRACT_NODE_LIMIT", "2")

    stage_builders = {
        StageId.D0_P0: build_d0_p0_stage,
        StageId.D1: build_d1_stage,
        StageId.D2: build_d2_stage,
        StageId.D4: build_d4_stage,
        StageId.D5: build_d5_stage,
    }
    assert set(stage_builders) <= set(STAGE_BUILDERS)
    assert stage_builders[StageId.D0_P0] is source_builders.build_d0_p0_stage
    assert stage_builders[StageId.D1] is source_builders.build_d1_stage
    assert stage_builders[StageId.D2] is source_builders.build_d2_stage
    assert stage_builders[StageId.D4].__module__.endswith("builders.governance_handoff")
    assert stage_builders[StageId.D5] is release.build_d5_stage
    assert bindings_validation._build_synthetic_multiscale_payload.__module__.endswith(
        "builders.bindings_validation"
    )
    assert demography._build_household_distribution_observation_panel.__module__.endswith(
        "builders.demography"
    )

    for stage_id, builder in stage_builders.items():
        if stage_id is StageId.D4:
            write_manifest(
                orchestrator.stage_manifest_path(StageId.D3),
                BuildRunManifest(
                    run_id="d3-udf-02-prerequisite",
                    stage_id=StageId.D3,
                    status="completed",
                    started_at="2026-08-26T10:00:00+00:00",
                    finished_at="2026-08-26T10:01:00+00:00",
                ),
            )
        direct_result = builder(config)
        expected_bytes = _recorded_output_bytes(direct_result)
        _assert_registered_stage_output_parity(
            orchestrator,
            stage_id,
            direct_result,
            expected_bytes,
        )
