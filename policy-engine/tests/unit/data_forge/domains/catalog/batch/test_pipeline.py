from __future__ import annotations

import asyncio
import json

from polisyos.data_forge.domains.catalog.batch.config import DatasetBatchConfig
from polisyos.data_forge.domains.catalog.batch.graph_builder import build_graph
from polisyos.data_forge.domains.catalog.batch.pipeline import (
    _record_stage_completion,
    _should_skip_stage,
    run_dataset_pipeline_sync,
)
from polisyos.data_forge.kernel.embeddings import build_embedding_generation


def test_pipeline_writes_telemetry_when_qc_fails(monkeypatch, tmp_path) -> None:
    def _boom(*args, **kwargs):
        raise RuntimeError("qc exploded")

    monkeypatch.setattr("polisyos.data_forge.domains.catalog.batch.qc.run_qc", _boom)
    config = DatasetBatchConfig(
        snapshot_root=tmp_path / "snap",
        stages=frozenset({"qc"}),
    )

    try:
        run_dataset_pipeline_sync(config)
    except RuntimeError as exc:
        assert "qc exploded" in str(exc)
    else:
        raise AssertionError("Expected pipeline to propagate QC failure")

    assert config.telemetry_path.exists()
    with open(config.telemetry_path, encoding="utf-8") as fh:
        payload = json.load(fh)

    assert payload["pipeline_status"] == "failed"
    assert payload["current_stage"] == "qc"
    assert "qc exploded" in payload["error"]


def test_embed_resume_does_not_skip_when_selected_member_is_missing(tmp_path, monkeypatch) -> None:
    from polisyos.fabric.connectors.profiles.models import SourceProfile
    from polisyos.fabric.connectors.profiles.registry import SourceProfileRegistry

    profiles = SourceProfileRegistry()
    profiles.register(
        SourceProfile(
            profile_id="worldbank_wdi",
            display_name="Fixture World Bank",
            connector_family="worldbank",
            base_url="https://example.test/worldbank",
        )
    )
    monkeypatch.setattr(SourceProfileRegistry, "_instance", profiles)
    config = DatasetBatchConfig(
        snapshot_root=tmp_path / "snap",
        stages=frozenset({"embed"}),
        resume=True,
    )
    build_embedding_generation(
        rows=[],
        index_dir=config.index_dir,
        embedding_model=config.embedding_model,
        embedding_device="cpu",
        embedding_dimension=config.embedding_dimension,
        legacy_embeddings_path=config.index_dir / "ds_dataset_embeddings.npz",
        legacy_index_path=config.index_dir / "ds_dataset_index.hnsw",
    )
    _record_stage_completion(config, "embed")
    assert not _should_skip_stage(config, "embed")

    build_graph(records=[], db_path=config.db_path)
    build_embedding_generation(
        rows=[],
        index_dir=config.index_dir,
        embedding_model=config.embedding_model,
        embedding_device="cpu",
        embedding_dimension=config.embedding_dimension,
        legacy_embeddings_path=config.index_dir / "ds_dataset_embeddings.npz",
        legacy_index_path=config.index_dir / "ds_dataset_index.hnsw",
    )
    _record_stage_completion(config, "embed")
    assert _should_skip_stage(config, "embed")

    selector = json.loads(
        (config.index_dir / "embedding_generation.json").read_text(encoding="utf-8")
    )
    generation_dir = config.index_dir / "embedding_generations" / selector["generation_id"]
    (generation_dir / "embeddings.npz").unlink()

    assert not _should_skip_stage(config, "embed")


def test_pipeline_uses_one_profile_snapshot_for_signature_and_core_consumer(
    tmp_path, monkeypatch
) -> None:
    from polisyos.data_forge.domains.catalog.batch import pipeline
    from polisyos.data_forge.domains.catalog.batch._core_sources_ingest_contracts import (
        CoreSourcesIngestStats,
    )
    from polisyos.data_forge.domains.catalog.batch.core_sources import api as core_api
    from polisyos.fabric.connectors.profiles.models import SourceProfile
    from polisyos.fabric.connectors.profiles.registry import SourceProfileRegistry

    profiles = SourceProfileRegistry()
    original = SourceProfile(
        profile_id="worldbank_wdi",
        display_name="Fixture World Bank",
        connector_family="worldbank",
        base_url="https://example.test/worldbank",
    )
    profiles.register(original)
    monkeypatch.setattr(SourceProfileRegistry, "_instance", profiles)
    config = DatasetBatchConfig(
        snapshot_root=tmp_path / "snap",
        stages=frozenset({"core_sources_ingest"}),
    )
    signatures: list[str] = []

    async def _fake_core_ingest(received_config):
        signatures.append(received_config.run_signature)
        profiles.register(
            original.model_copy(update={"base_url": "https://example.test/replaced"}),
            override=True,
        )
        signatures.append(received_config.run_signature)
        return CoreSourcesIngestStats()

    monkeypatch.setattr(core_api, "run_core_sources_ingest_async", _fake_core_ingest)

    def _does_not_skip(received_config, _stage):
        signatures.append(received_config.run_signature)
        return False

    monkeypatch.setattr(pipeline, "_should_skip_stage", _does_not_skip)

    run_dataset_pipeline_sync(config)

    assert len(signatures) == 3
    assert len(set(signatures)) == 1
    assert config.run_signature != signatures[0]


def test_pipeline_carries_request_scoped_core_dependency_to_canonical_api(
    tmp_path, monkeypatch
) -> None:
    from polisyos.data_forge.domains.catalog.batch._core_sources_ingest_contracts import (
        CoreSourcesCompatibilityContext,
        CoreSourcesIngestStats,
        ObservationPlan,
        ObservationShard,
        bind_core_sources_compatibility_context,
    )
    from polisyos.data_forge.domains.catalog.batch.core_sources import api as core_api
    from polisyos.fabric.connectors.profiles.models import SourceExecutionPolicy

    config = DatasetBatchConfig(
        snapshot_root=tmp_path / "snapshot",
        stages=frozenset({"core_sources_ingest"}),
    )
    plan = ObservationPlan(
        dataset_id="dataset",
        source="worldbank",
        raw_variable="value",
        canonical_var="gdp",
        connector_id="worldbank.wdi",
        profile_id="worldbank_wdi",
        request_dataset_id="NY.GDP.MKTP.CD",
        default_filters={},
        update_frequency="annual",
    )
    shard = ObservationShard(
        shard_id="shard",
        plan=plan,
        country_code="UA",
        start_year=2020,
        end_year=2020,
        filters={},
    )
    selected_profiles: list[str] = []

    async def _scoped_fetch(*_args, **_kwargs):
        selected_profiles.append("source-profile-a")
        artifact = tmp_path / "producer" / "core-source.json"
        artifact.parent.mkdir(parents=True, exist_ok=True)
        artifact.write_text('{"profile":"source-profile-a"}', encoding="utf-8")
        return [{"profile": "source-profile-a", "path": str(artifact)}]

    async def _stage(received_config):
        from polisyos.data_forge.domains.catalog.batch.core_sources.writers import (
            _ConnectorSessionCache,
        )

        rows = await core_api._invoke_fetch_observation_rows(
            shard,
            _ConnectorSessionCache(),
            config=received_config,
            policy=SourceExecutionPolicy(profile_id="worldbank_wdi"),
            budget_windows={},
            state_lock=asyncio.Lock(),
        )
        assert rows[0]["profile"] == "source-profile-a"
        return CoreSourcesIngestStats(observations=len(rows))

    monkeypatch.setattr(core_api, "_run_core_sources_ingest_stage", _stage)
    context = CoreSourcesCompatibilityContext(
        {(core_api.__name__, "_fetch_observation_rows"): _scoped_fetch}
    )
    with bind_core_sources_compatibility_context(context):
        stats = run_dataset_pipeline_sync(config)

    assert stats.metrics["core_observations"] == 1
    assert selected_profiles == ["source-profile-a"]
    assert (tmp_path / "producer" / "core-source.json").read_text(encoding="utf-8") == (
        '{"profile":"source-profile-a"}'
    )
