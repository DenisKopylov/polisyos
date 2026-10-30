"""B147 witnesses for observation-reader continuity after a partial yield.

These tests deliberately exercise the real observation-frame mapper and the
Parquet reader boundary.  A reader failure is allowed to change readers only
before publication; once a metric frame has been yielded, the continuation
must account for the confirmed batch/metric cursor rather than replaying the
published prefix.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import tempfile
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pandas as pd
import pytest

from polisyos.data_forge.domains.ukraine.models import (
    PipelineConfig,
    SourceConfig,
    StageId,
    build_default_pipeline_config,
)
from polisyos.ir.observation.contracts import EntityScope, ObservationFamily

pytestmark = pytest.mark.unit


def _source() -> SourceConfig:
    """Return a two-metric source that exposes within-batch metric cursors."""
    return SourceConfig(
        source_id="partial_yield_witness",
        display_name="Partial yield witness",
        stage_id=StageId.D1,
        normalized_artifact="observations.parquet",
        required_columns=[
            "agent_id",
            "cell_id",
            "region_code",
            "sector_id",
            "period_id",
            "metric_a",
            "metric_b",
        ],
        metric_columns=["metric_a", "metric_b"],
        observation_family=ObservationFamily.MACRO_STATE,
        entity_scope=EntityScope.AGENT,
    )


def _frame() -> pd.DataFrame:
    """Return a small normalized frame with all optional reader columns."""
    return pd.DataFrame(
        {
            "agent_id": ["agent::1", "agent::2", "agent::3", "agent::4"],
            "cell_id": ["cell::1", "cell::2", "cell::3", "cell::4"],
            "region_code": ["01", "01", "02", "02"],
            "sector_id": ["sector::a"] * 4,
            "period_id": ["2024-01", "2024-02", "2024-03", "2024-04"],
            "metric_a": [10.0, 20.0, 30.0, 40.0],
            "metric_b": [100.0, 200.0, 300.0, 400.0],
            "measurement_bias_flag": [False] * 4,
            "censoring_mask": [False] * 4,
            "trust_weight": [0.9] * 4,
            "lag_days_estimate": [0] * 4,
            "regime_id": ["regime_a"] * 4,
            "schema_regime_id": ["ukraine_schema_v1"] * 4,
            "registration_code": ["reg::1", "reg::2", "reg::3", "reg::4"],
        }
    )


def _config(tmp_path: Path) -> tuple[PipelineConfig, SourceConfig, pd.DataFrame]:
    """Build a minimal real checkout config for the observation reader."""
    source = _source()
    config = build_default_pipeline_config(root=tmp_path / "ukraine")
    config = config.model_copy(update={"sources": {source.source_id: source}})
    frame = _frame()
    artifact = config.build_root.normalized_dir / source.source_id / source.normalized_artifact
    artifact.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(artifact, index=False)
    return config, source, frame


def _batch(frame: pd.DataFrame, *, size: int) -> Any:
    """Return one real Arrow record batch without changing production code."""
    pa = pytest.importorskip("pyarrow")
    return pa.Table.from_pandas(frame, preserve_index=False).to_batches(max_chunksize=size)[0]


def test_partial_batch_failure_resumes_without_republishing_confirmed_prefix(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A reader failure after one batch preserves rows and metric-frame IDs."""
    pytest.importorskip("pyarrow")
    from polisyos.data_forge.domains.ukraine.builders import sources

    config, _, frame = _config(tmp_path)
    instances: list[int] = []

    class FailingThenResumableParquetFile:
        """Fail once after a published batch, then expose the same snapshot."""

        def __init__(self, _path: Path) -> None:
            self.instance = len(instances)
            instances.append(self.instance)

        def iter_batches(self, *, batch_size: int, columns: list[str] | None = None):
            del batch_size, columns
            if self.instance == 0:
                yield _batch(frame.iloc[:2], size=2)
                raise OSError("controlled reader failure after first batch")
            yield from (
                __import__("pyarrow")
                .Table.from_pandas(frame, preserve_index=False)
                .to_batches(max_chunksize=2)
            )

    import pyarrow.parquet as parquet

    monkeypatch.setattr(parquet, "ParquetFile", FailingThenResumableParquetFile)

    emitted = list(sources._iter_observation_metric_frames(config))

    assert len(instances) == 2
    assert [(metric_id, batch_index) for _, metric_id, batch_index, _ in emitted] == [
        ("metric_a", 0),
        ("metric_b", 0),
        ("metric_a", 1),
        ("metric_b", 1),
    ]
    observation_ids = [
        value
        for _, _, _, metric_frame in emitted
        for value in metric_frame["observation_id"].tolist()
    ]
    assert len(observation_ids) == len(set(observation_ids)) == 8
    assert sorted(
        value
        for _, metric_id, _, metric_frame in emitted
        if metric_id == "metric_a"
        for value in metric_frame["observed_value"].tolist()
    ) == [10.0, 20.0, 30.0, 40.0]
    assert sorted(
        value
        for _, metric_id, _, metric_frame in emitted
        if metric_id == "metric_b"
        for value in metric_frame["observed_value"].tolist()
    ) == [100.0, 200.0, 300.0, 400.0]


def test_mapper_failure_after_metric_is_not_reclassified_as_reader_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A semantic mapper failure stops after the published prefix without retry."""
    pytest.importorskip("pyarrow")
    from polisyos.data_forge.domains.ukraine.builders import sources

    config, _, frame = _config(tmp_path)
    original_mapper = sources._observation_metric_frames_from_frame
    mapper_calls = 0

    def fail_after_first_metric(*args: Any, **kwargs: Any):
        nonlocal mapper_calls
        mapper_calls += 1
        mapped = iter(original_mapper(*args, **kwargs))
        if mapper_calls == 1:
            yield next(mapped)
            raise OSError("controlled failure between metric frames")
        yield from mapped

    class SingleBatchParquetFile:
        """Expose one real batch; the mapper injects the inter-metric failure."""

        def __init__(self, _path: Path) -> None:
            pass

        def iter_batches(self, *, batch_size: int, columns: list[str] | None = None):
            del batch_size, columns
            yield _batch(frame, size=len(frame))

    import pyarrow.parquet as parquet

    monkeypatch.setattr(parquet, "ParquetFile", SingleBatchParquetFile)
    monkeypatch.setattr(sources, "_observation_metric_frames_from_frame", fail_after_first_metric)
    read_calls: list[Path] = []

    def forbidden_full_read(path: Path, *, columns: list[str] | None = None) -> pd.DataFrame:
        del columns
        read_calls.append(path)
        return frame.copy()

    monkeypatch.setattr(
        sources,
        "_read_parquet_frame",
        forbidden_full_read,
    )

    emitted = iter(sources._iter_observation_metric_frames(config))
    _, metric_id, batch_index, first = next(emitted)
    with pytest.raises(OSError, match="controlled failure between metric frames"):
        next(emitted)
    assert mapper_calls == 1
    assert read_calls == []
    assert (metric_id, batch_index) == ("metric_a", 0)
    assert first["observation_id"].is_unique
    assert first["observed_value"].tolist() == [10.0, 20.0, 30.0, 40.0]


def test_partial_resume_aborts_when_reader_restart_lacks_confirmed_batch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A reader restart cannot silently discard a confirmed batch."""
    pytest.importorskip("pyarrow")
    from polisyos.data_forge.domains.ukraine.builders import sources

    config, _, frame = _config(tmp_path)
    instances: list[int] = []

    class MissingResumeBatchParquetFile:
        def __init__(self, _path: Path) -> None:
            self.instance = len(instances)
            instances.append(self.instance)

        def iter_batches(self, *, batch_size: int, columns: list[str] | None = None):
            del batch_size, columns
            if self.instance == 0:
                yield _batch(frame, size=len(frame))
                raise OSError("controlled reader failure after confirmed batch")

    import pyarrow.parquet as parquet

    monkeypatch.setattr(parquet, "ParquetFile", MissingResumeBatchParquetFile)
    with pytest.raises(RuntimeError, match="confirmed observation cursor") as caught:
        list(sources._iter_observation_metric_frames(config))
    assert "controlled reader failure after confirmed batch" in str(caught.value)
    assert instances == [0, 1]


def test_small_real_parquet_reader_preserves_metric_counts_and_snapshot_values(
    tmp_path: Path,
) -> None:
    """The normal Parquet route emits both metric frames without collapsing values."""
    pytest.importorskip("pyarrow")
    from polisyos.data_forge.domains.ukraine.builders import sources

    config, _, _ = _config(tmp_path)

    emitted = list(sources._iter_observation_metric_frames(config))

    assert [(metric_id, batch_index) for _, metric_id, batch_index, _ in emitted] == [
        ("metric_a", 0),
        ("metric_b", 0),
    ]
    assert sum(len(metric_frame) for _, _, _, metric_frame in emitted) == 8


@pytest.mark.parametrize(
    ("mutation", "restart"),
    [
        ("overwrite", False),
        ("replace", False),
        ("overwrite", True),
        ("replace", True),
        ("aba", True),
    ],
)
def test_stream_and_retry_read_same_parquet_snapshot_after_source_mutation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
    restart: bool,
) -> None:
    """Streaming and retry use the captured bytes even when the live path changes."""
    pytest.importorskip("pyarrow")
    import pyarrow as pa
    import pyarrow.parquet as parquet

    from polisyos.data_forge.domains.ukraine.builders import sources

    config, source, frame = _config(tmp_path)
    artifact = config.build_root.normalized_dir / source.source_id / source.normalized_artifact
    alternative = artifact.with_name("alternative.parquet")
    original = artifact.with_name("original.parquet")
    changed = frame.copy()
    changed["metric_a"] += 1_000
    changed["metric_b"] += 1_000
    for path, data in ((original, frame), (alternative, changed)):
        parquet.write_table(
            pa.Table.from_pandas(data, preserve_index=False),
            path,
            compression="NONE",
            use_dictionary=False,
            row_group_size=2,
        )
    first_bytes = original.read_bytes()
    other_bytes = alternative.read_bytes()
    assert len(first_bytes) == len(other_bytes)
    artifact.write_bytes(first_bytes)
    stamp = artifact.stat()
    expected_digest = hashlib.sha256(first_bytes).hexdigest()

    def publish(payload: bytes, *, replacement: bool) -> None:
        if replacement:
            candidate = artifact.with_name("replacement.parquet")
            candidate.write_bytes(payload)
            os.utime(candidate, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
            os.replace(candidate, artifact)
        else:
            artifact.write_bytes(payload)
            os.utime(artifact, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))

    real_reader = parquet.ParquetFile
    read_digests: list[str] = []

    class FailAfterFirstBatch:
        def __init__(self, reader: Any) -> None:
            self.reader = reader

        def iter_batches(self, **kwargs: Any):
            kwargs["batch_size"] = 2
            batches = iter(self.reader.iter_batches(**kwargs))
            yield next(batches)
            publish(other_bytes, replacement=mutation != "overwrite")
            if mutation == "aba":
                publish(first_bytes, replacement=True)
            if restart:
                raise OSError("controlled post-publication failure")
            yield from batches

    def reopening_reader(reader_input: Any, *args: Any, **kwargs: Any) -> Any:
        attempt = len(read_digests)
        if mutation == "aba" and attempt == 1:
            # The old implementation checks A, opens B, then the path returns
            # to A while the opened inode still points at B.
            publish(other_bytes, replacement=True)
        if isinstance(reader_input, (str, Path)):
            captured = Path(reader_input).read_bytes()
        else:
            position = reader_input.tell()
            reader_input.seek(0)
            captured = reader_input.read()
            reader_input.seek(position)
        read_digests.append(hashlib.sha256(captured).hexdigest())
        reader = real_reader(reader_input, *args, **kwargs)
        if mutation == "aba" and attempt == 1:
            publish(first_bytes, replacement=True)
        return FailAfterFirstBatch(reader) if attempt == 0 else reader

    monkeypatch.setattr(parquet, "ParquetFile", reopening_reader)
    emitted = list(sources._iter_observation_metric_frames(config))

    assert read_digests == [expected_digest] * (2 if restart else 1)
    assert artifact.stat().st_size == stamp.st_size
    assert artifact.stat().st_mtime_ns == stamp.st_mtime_ns
    actual = {
        (str(row.metric_id), str(row.observation_id)): row.observed_value
        for _, _, _, metric_frame in emitted
        for row in metric_frame.itertuples(index=False)
    }
    assert actual == {
        (metric, f"obs.partial_yield_witness.{metric}.{index:08d}"): value
        for metric, values in (
            ("metric_a", [10.0, 20.0, 30.0, 40.0]),
            ("metric_b", [100.0, 200.0, 300.0, 400.0]),
        )
        for index, value in enumerate(values)
    }
    assert sum(len(metric_frame) for _, _, _, metric_frame in emitted) == 8


def test_source_mutation_during_snapshot_capture_is_rejected_before_yield(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The snapshot digest must match the bytes hashed before its capture."""
    pytest.importorskip("pyarrow")
    import pyarrow as pa
    import pyarrow.parquet as parquet

    from polisyos.data_forge.domains.ukraine.builders import sources

    config, source, frame = _config(tmp_path)
    artifact = config.build_root.normalized_dir / source.source_id / source.normalized_artifact
    changed = frame.copy()
    changed["metric_a"] += 1_000
    replacement = artifact.with_name("changed.parquet")
    for path, data in ((artifact, frame), (replacement, changed)):
        parquet.write_table(
            pa.Table.from_pandas(data, preserve_index=False),
            path,
            compression="NONE",
            use_dictionary=False,
        )
    other_bytes = replacement.read_bytes()
    assert len(other_bytes) == artifact.stat().st_size
    initial_stat = artifact.stat()
    real_hash = sources.sha256_file

    def hash_then_mutate(path: Path, **kwargs: Any) -> str:
        digest = real_hash(path, **kwargs)
        artifact.write_bytes(other_bytes)
        os.utime(artifact, ns=(initial_stat.st_atime_ns, initial_stat.st_mtime_ns))
        return digest

    monkeypatch.setattr(sources, "sha256_file", hash_then_mutate)
    with pytest.raises(RuntimeError, match="snapshot"):
        next(iter(sources._iter_observation_metric_frames(config)))


def test_snapshot_refuses_insufficient_disk_budget_before_copy(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A large member cannot start an unadmitted temporary copy."""
    pytest.importorskip("pyarrow")
    from polisyos.data_forge.domains.ukraine.builders import sources

    config, _, _ = _config(tmp_path)
    config.stages[StageId.D2.value].resource_budget.disk_gib = 1 / 1024**3

    def forbidden_snapshot(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("temporary copy started before disk admission")

    monkeypatch.setattr(tempfile, "TemporaryFile", forbidden_snapshot)
    with pytest.raises(RuntimeError, match=r"snapshot.*(disk|budget)"):
        next(iter(sources._iter_observation_metric_frames(config)))


def test_snapshot_refuses_when_temporary_filesystem_lacks_capacity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A missing stage hint does not waive the actual free-space check."""
    pytest.importorskip("pyarrow")
    from polisyos.data_forge.domains.ukraine.builders import sources

    config, _, _ = _config(tmp_path)

    def no_free_space(_path: Any) -> SimpleNamespace:
        return SimpleNamespace(free=0)

    def forbidden_snapshot(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("temporary copy started without free space")

    monkeypatch.setattr(shutil, "disk_usage", no_free_space)
    monkeypatch.setattr(tempfile, "TemporaryFile", forbidden_snapshot)
    with pytest.raises(RuntimeError, match=r"snapshot.*disk"):
        next(iter(sources._iter_observation_metric_frames(config)))


def test_snapshot_capture_rejects_source_growth_and_closes_temporary_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Growth after admission cannot increase the temporary file beyond its bound."""
    pytest.importorskip("pyarrow")
    from polisyos.data_forge.domains.ukraine.builders import sources

    config, source, _ = _config(tmp_path)
    artifact = config.build_root.normalized_dir / source.source_id / source.normalized_artifact
    original_size = artifact.stat().st_size
    real_hash = sources.sha256_file
    real_temporary_file = tempfile.TemporaryFile
    snapshots: list[Any] = []
    bytes_written = 0

    class TrackedSnapshot:
        def __init__(self) -> None:
            self.handle = real_temporary_file(mode="w+b")
            snapshots.append(self.handle)

        def __enter__(self) -> TrackedSnapshot:
            return self

        def __exit__(self, *args: Any) -> None:
            self.handle.close()

        def write(self, data: bytes) -> int:
            nonlocal bytes_written
            bytes_written += len(data)
            return self.handle.write(data)

    def hash_then_grow(path: Path, **kwargs: Any) -> str:
        digest = real_hash(path, **kwargs)
        with artifact.open("ab") as handle:
            handle.write(b"more data")
        return digest

    monkeypatch.setattr(sources, "sha256_file", hash_then_grow)
    monkeypatch.setattr(tempfile, "TemporaryFile", lambda **_kwargs: TrackedSnapshot())
    with pytest.raises(RuntimeError, match="snapshot source grew"):
        next(iter(sources._iter_observation_metric_frames(config)))
    assert bytes_written == original_size
    assert len(snapshots) == 1 and snapshots[0].closed


def test_snapshot_closes_on_consumer_cancellation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Stopping after a yielded frame releases the private temporary file."""
    pytest.importorskip("pyarrow")
    from polisyos.data_forge.domains.ukraine.builders import sources

    config, _, _ = _config(tmp_path)
    real_temporary_file = tempfile.TemporaryFile
    snapshots: list[Any] = []

    def tracked_temporary_file(*args: Any, **kwargs: Any) -> Any:
        handle = real_temporary_file(*args, **kwargs)
        snapshots.append(handle)
        return handle

    monkeypatch.setattr(tempfile, "TemporaryFile", tracked_temporary_file)
    frames = iter(sources._iter_observation_metric_frames(config))
    next(frames)
    assert len(snapshots) == 1
    assert not snapshots[0].closed
    frames.close()
    assert snapshots[0].closed


def test_build_d2_materializes_unique_observation_shards_and_counts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The D2 consumer materializes the streamed frames without duplicate IDs."""
    pytest.importorskip("pyarrow")
    pytest.importorskip("duckdb")
    from polisyos.data_forge.domains.ukraine.builders import sources

    config, source, frame = _config(tmp_path)
    family_sources = {source.source_id: source}
    for family in ObservationFamily:
        if family is source.observation_family:
            continue
        metric_id = f"fixture_{family.value}"
        fixture_source = SourceConfig(
            source_id=f"d2_fixture_{family.value}",
            display_name=f"D2 fixture {family.value}",
            stage_id=StageId.D1,
            normalized_artifact=f"{family.value}.parquet",
            required_columns=[
                "agent_id",
                "cell_id",
                "region_code",
                "sector_id",
                "period_id",
                metric_id,
            ],
            metric_columns=[metric_id],
            observation_family=family,
            entity_scope=EntityScope.AGENT,
        )
        family_sources[fixture_source.source_id] = fixture_source
        fixture_frame = frame.copy()
        fixture_frame[metric_id] = fixture_frame["metric_a"]
        artifact = (
            config.build_root.normalized_dir
            / fixture_source.source_id
            / fixture_source.normalized_artifact
        )
        artifact.parent.mkdir(parents=True, exist_ok=True)
        fixture_frame.to_parquet(artifact, index=False)
    config = config.model_copy(update={"sources": family_sources})
    from io import BytesIO

    from polisyos.core.artifacts import FileSystemCAS
    from polisyos.data_forge.domains.ukraine.manifests import (
        BuildRunManifest,
        write_manifest,
    )
    from polisyos.data_forge.read_api.ukraine import (
        load_verified_stage_artifacts,
        load_verified_stage_output_bytes,
    )

    shards: list[pd.DataFrame] = []
    real_to_parquet = pd.DataFrame.to_parquet

    def capture_real_shard(self: pd.DataFrame, path: Any, *args: Any, **kwargs: Any) -> Any:
        result = real_to_parquet(self, path, *args, **kwargs)
        if "d2_observation_shards" in Path(path).parts:
            shards.append(pd.read_parquet(path))
        return result

    monkeypatch.setattr(pd.DataFrame, "to_parquet", capture_real_shard)
    import pyarrow.parquet as parquet

    real_parquet_file = parquet.ParquetFile
    target = config.build_root.normalized_dir / source.source_id / source.normalized_artifact
    target_opens: list[str] = []
    target_digest = hashlib.sha256(target.read_bytes()).hexdigest()

    class FailOnceAfterFirstBatch:
        def __init__(self, reader: Any) -> None:
            self.reader = reader

        def iter_batches(self, **kwargs: Any):
            batches = iter(self.reader.iter_batches(**kwargs))
            yield next(batches)
            raise OSError("controlled post-publication stream failure")

    def recovering_reader(path: Any, *args: Any, **kwargs: Any) -> Any:
        reader = real_parquet_file(path, *args, **kwargs)
        if isinstance(path, (str, Path)):
            is_target = Path(path) == target
        else:
            position = path.tell()
            path.seek(0)
            is_target = hashlib.sha256(path.read()).hexdigest() == target_digest
            path.seek(position)
        if is_target:
            target_opens.append(target_digest)
            if len(target_opens) == 1:
                return FailOnceAfterFirstBatch(reader)
        return reader

    monkeypatch.setattr(parquet, "ParquetFile", recovering_reader)
    result = sources.build_d2_stage(config)
    assert len(target_opens) >= 2
    panel_path = config.build_root.calibration_dir / "d2" / "observation_panel_monthly.parquet"
    manifest_path = config.build_root.manifests_dir / "build_run_d2.json"
    write_manifest(
        manifest_path,
        BuildRunManifest(
            run_id="d2-shard-witness",
            stage_id=StageId.D2,
            status="completed",
            started_at="2026-01-01T00:00:00Z",
            finished_at="2026-01-01T00:00:01Z",
            outputs=list(result.outputs.values()),
        ),
    )
    store = FileSystemCAS(config.build_root.resolved_cas_root)
    receipt = load_verified_stage_artifacts(
        manifest_path,
        store=store,
        allowed_root=config.build_root.root,
        expected_stage=StageId.D2.value,
        required_outputs=(
            "observation_panel_monthly.parquet",
            "observation_panel_annual.parquet",
            "calibration_bundle_manifest.json",
        ),
    )
    panel = pd.read_parquet(
        BytesIO(
            load_verified_stage_output_bytes(store, receipt, "observation_panel_monthly.parquet")
        )
    )
    annual = pd.read_parquet(
        BytesIO(
            load_verified_stage_output_bytes(store, receipt, "observation_panel_annual.parquet")
        )
    )
    import json

    persisted_metrics = json.loads(
        load_verified_stage_output_bytes(store, receipt, "calibration_bundle_manifest.json")
    )["metrics"]
    assert persisted_metrics["n_monthly_records"] == result.metrics["n_monthly_records"]
    assert persisted_metrics["n_annual_records"] == result.metrics["n_annual_records"]
    assert annual.empty
    assert shards
    shard_rows = pd.concat(shards, ignore_index=True)
    assert sorted(shard_rows["observation_id"]) == sorted(panel["observation_id"])
    assert not (config.build_root.tmp_dir / "d2_observation_shards").exists()

    expected_rows = sum(
        len(frame) * len(fixture_source.metric_columns)
        for fixture_source in family_sources.values()
    )
    output = result.outputs["observation_panel_monthly.parquet"]
    assert Path(output.path) == panel_path
    assert output.size_bytes == panel_path.stat().st_size
    assert result.metrics["n_monthly_records"] == expected_rows
    assert len(panel) == expected_rows
    assert panel["observation_id"].is_unique
    custom_rows = panel[panel["source_id"] == source.source_id]
    assert len(custom_rows) == 8
    assert set(custom_rows["metric_id"].astype(str)) == {"metric_a", "metric_b"}
    assert result.metrics["n_annual_records"] == 0
    for metric in ("metric_a", "metric_b"):
        selected = custom_rows[custom_rows["metric_id"].astype(str) == metric]
        assert sorted(selected["observed_value"].tolist()) == sorted(frame[metric].tolist())
        assert set(selected["period_disposition"].astype(str)) == {"valid"}


@pytest.mark.parametrize("budget_gib", [None, 0.01, 28.0])
def test_prepublication_reader_failure_refuses_unbounded_full_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, budget_gib: float | None
) -> None:
    """A D2 budget hint alone must not authorize a full-frame allocation."""
    pytest.importorskip("pyarrow")
    import pyarrow.parquet as parquet

    from polisyos.data_forge.domains.ukraine.builders import sources

    config, source, _ = _config(tmp_path)
    config.stages[StageId.D2.value].resource_budget.memory_gib = budget_gib

    class FailBeforeYield:
        def __init__(self, _path: Path) -> None:
            raise OSError("controlled unavailable stream")

    reads: list[Path] = []

    def full_reader(path: Path, *, columns: list[str] | None = None) -> pd.DataFrame:
        del columns
        reads.append(path)
        raise AssertionError("unbounded full reader must not be invoked")

    monkeypatch.setattr(parquet, "ParquetFile", FailBeforeYield)
    monkeypatch.setattr(sources, "_read_parquet_frame", full_reader)
    with pytest.raises(sources.ObservationFullReadBudgetUnavailableError) as caught:
        list(sources._iter_observation_metric_frames(config))
    assert caught.value.source_id == source.source_id
    assert caught.value.budget_gib == config.stages[StageId.D2.value].resource_budget.memory_gib
    assert reads == []
