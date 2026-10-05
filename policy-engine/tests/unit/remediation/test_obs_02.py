"""B147 witnesses for observation-reader continuity after a partial yield.

These tests deliberately exercise the real observation-frame mapper and the
Parquet reader boundary.  A reader failure is allowed to change readers only
before publication; once a metric frame has been yielded, the continuation
must account for the confirmed batch/metric cursor rather than replaying the
published prefix.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
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
    return pa.Table.from_pandas(frame, preserve_index=False).to_batches(
        max_chunksize=size
    )[0]


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
            yield from __import__("pyarrow").Table.from_pandas(
                frame, preserve_index=False
            ).to_batches(max_chunksize=2)

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


def test_failure_between_metric_frames_resumes_at_confirmed_metric_cursor(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failure between metrics does not replay the first metric frame."""
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

    emitted = list(sources._iter_observation_metric_frames(config))

    assert mapper_calls == 2
    assert read_calls == []
    assert [(metric_id, batch_index) for _, metric_id, batch_index, _ in emitted] == [
        ("metric_a", 0),
        ("metric_b", 0),
    ]
    observation_ids = [
        value
        for _, _, _, metric_frame in emitted
        for value in metric_frame["observation_id"].tolist()
    ]
    assert len(observation_ids) == len(set(observation_ids)) == 8


def test_partial_resume_aborts_when_unchanged_snapshot_lacks_pending_metric_cursor(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An unchanged snapshot cannot silently drop a pending metric frame."""
    pytest.importorskip("pyarrow")
    from polisyos.data_forge.domains.ukraine.builders import sources

    config, _, frame = _config(tmp_path)
    original_mapper = sources._observation_metric_frames_from_frame
    mapper_calls = 0
    instances: list[int] = []

    def fail_after_first_metric(*args: Any, **kwargs: Any):
        nonlocal mapper_calls
        mapper_calls += 1
        mapped = iter(original_mapper(*args, **kwargs))
        if mapper_calls == 1:
            yield next(mapped)
            raise OSError("controlled failure before the pending metric frame")
        yield from mapped

    class MissingResumeBatchParquetFile:
        """Return the first batch, then an unchanged but empty restart."""

        def __init__(self, _path: Path) -> None:
            self.instance = len(instances)
            instances.append(self.instance)

        def iter_batches(self, *, batch_size: int, columns: list[str] | None = None):
            del batch_size, columns
            if self.instance == 0:
                yield _batch(frame, size=len(frame))

    import pyarrow.parquet as parquet

    monkeypatch.setattr(parquet, "ParquetFile", MissingResumeBatchParquetFile)
    monkeypatch.setattr(
        sources,
        "_observation_metric_frames_from_frame",
        fail_after_first_metric,
    )

    with pytest.raises(RuntimeError, match="metric cursor"):
        list(sources._iter_observation_metric_frames(config))

    assert mapper_calls == 1
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


def test_partial_resume_aborts_when_normalized_snapshot_changes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A changed input cannot be resumed as though it were the old snapshot."""
    pytest.importorskip("pyarrow")
    from polisyos.data_forge.domains.ukraine.builders import sources

    config, source, frame = _config(tmp_path)
    artifact = config.build_root.normalized_dir / source.source_id / source.normalized_artifact

    class MutatingParquetFile:
        """Mutate the input only after the first published batch."""

        def __init__(self, _path: Path) -> None:
            pass

        def iter_batches(self, *, batch_size: int, columns: list[str] | None = None):
            del batch_size, columns
            yield _batch(frame.iloc[:2], size=2)
            artifact.write_bytes(artifact.read_bytes() + b"changed-after-yield")
            raise OSError("controlled reader failure after input mutation")

    import pyarrow.parquet as parquet

    monkeypatch.setattr(parquet, "ParquetFile", MutatingParquetFile)

    with pytest.raises(RuntimeError, match="snapshot"):
        list(sources._iter_observation_metric_frames(config))


def test_successful_stream_rejects_a_changed_input_snapshot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A completed stream cannot publish frames from mixed input generations."""
    pytest.importorskip("pyarrow")
    from polisyos.data_forge.domains.ukraine.builders import sources

    config, source, frame = _config(tmp_path)
    artifact = config.build_root.normalized_dir / source.source_id / source.normalized_artifact
    initial_digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
    changed = frame.copy()
    changed.loc[:, "metric_a"] += 1000.0
    changed.loc[:, "metric_b"] += 10000.0

    class MutatingParquetFile:
        """Change the source after the first yielded batch, without a reader error."""

        def __init__(self, _path: Path) -> None:
            pass

        def iter_batches(self, *, batch_size: int, columns: list[str] | None = None):
            del batch_size, columns
            yield _batch(frame.iloc[:2], size=2)
            changed.to_parquet(artifact, index=False)
            yield _batch(changed.iloc[2:], size=2)

    import pyarrow.parquet as parquet

    monkeypatch.setattr(parquet, "ParquetFile", MutatingParquetFile)

    with pytest.raises(RuntimeError, match="snapshot"):
        list(sources._iter_observation_metric_frames(config))

    final_digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
    assert final_digest != initial_digest


def test_build_d2_materializes_unique_observation_shards_and_counts(
    tmp_path: Path,
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

    result = sources.build_d2_stage(config)
    panel_path = config.build_root.calibration_dir / "d2" / "observation_panel_monthly.parquet"
    panel = pd.read_parquet(panel_path)

    expected_rows = sum(
        len(frame) * len(fixture_source.metric_columns)
        for fixture_source in family_sources.values()
    )
    output = result.outputs["observation_panel_monthly.parquet"]
    assert Path(output.path) == panel_path
    assert output.size_bytes == panel_path.stat().st_size
    assert output.sha256 == hashlib.sha256(panel_path.read_bytes()).hexdigest()
    assert result.metrics["n_monthly_records"] == expected_rows
    assert len(panel) == expected_rows
    assert panel["observation_id"].is_unique
    custom_rows = panel[panel["source_id"] == source.source_id]
    assert len(custom_rows) == 8
    assert set(custom_rows["metric_id"].astype(str)) == {"metric_a", "metric_b"}
