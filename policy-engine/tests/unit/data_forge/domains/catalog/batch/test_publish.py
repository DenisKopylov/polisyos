from __future__ import annotations

import json
import os
from pathlib import Path

from polisyos.data_forge.domains.catalog.batch.benchmark import READINESS_THRESHOLDS
from polisyos.data_forge.domains.catalog.batch.config import DatasetBatchConfig
from polisyos.data_forge.domains.catalog.batch.graph_builder import build_graph
from polisyos.data_forge.domains.catalog.batch.pipeline import (
    _should_skip_stage,
    current_catalog_publish_receipt,
    run_content_stage_with_receipt,
)
from polisyos.data_forge.domains.catalog.batch.publish import run_publish
from polisyos.data_forge.domains.catalog.knowledge.types import (
    DatasetRecord,
    DistributionRecord,
)


def _write_test_registry(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "version: 1",
                "sources:",
                "  - name: worldbank",
                "    family: worldbank",
                "    wave: A",
                "    endpoint: https://example.test/worldbank",
                "    enabled: true",
                "    execution_tier: transport_ready",
                "    run_lane: empirical",
                "    publish_blocking: true",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def _build_publish_fixture(config: DatasetBatchConfig) -> None:
    build_graph(
        records=iter(
            [
                DatasetRecord(
                    id="ds-gdp",
                    title="GDP per capita",
                    source="worldbank",
                    dataset_id="NY.GDP.PCAP.CD",
                    source_dataset_id="NY.GDP.PCAP.CD",
                    execution_tier="transport_ready",
                    polisyos_metrics=["gdp_per_capita"],
                    preferred_distribution_id="dist-gdp",
                    distributions=[
                        DistributionRecord(
                            id="dist-gdp",
                            connector_type="worldbank.wdi",
                            source_locator="NY.GDP.PCAP.CD",
                            parser_supported=True,
                            machine_readable=True,
                        )
                    ],
                )
            ]
        ),
        db_path=config.db_path,
    )


def _write_qc_and_benchmark(
    config: DatasetBatchConfig,
    *,
    search=100.0,
    retrieval=100.0,
    transport=100.0,
    foundry=100.0,
    source_preflight=100.0,
    qc_passed=True,
    source_status: str = "complete",
    evaluation_mode: str = "full-ready",
    mismatch_rate: float = 0.0,
    blocking_mismatch_sources: int = 0,
) -> None:
    with open(config.qc_report_path, "w", encoding="utf-8") as fh:
        json.dump(
            {
                "scope": "datasets",
                "passed": qc_passed,
                "metrics": {
                    "machine_readable_distribution_pct": 100.0,
                    "parser_supported_distribution_pct": 100.0,
                    "datasets_with_metric_binding_pct": 100.0,
                    "datasets_with_schema_profile_pct": 100.0,
                    "transport_ready_var_coverage_pct": 100.0,
                    "execution_readiness_score_avg": 0.9,
                    "benchmark_search_top5_relevance_pct": search,
                    "benchmark_retrieval_ready_pct": retrieval,
                    "benchmark_transport_ready_pct": transport,
                    "benchmark_foundry_fitness_pct": foundry,
                    "benchmark_source_preflight_ready_pct": source_preflight,
                },
                "checks": [],
            },
            fh,
            ensure_ascii=False,
            indent=2,
        )

    with open(config.benchmark_report_path, "w", encoding="utf-8") as fh:
        json.dump(
            {
                "kind": "datasets_benchmark",
                "evaluation_mode": evaluation_mode,
                "metrics": {
                    "benchmark_search_top5_relevance_pct": search,
                    "benchmark_retrieval_ready_pct": retrieval,
                    "benchmark_transport_ready_pct": transport,
                    "benchmark_foundry_fitness_pct": foundry,
                    "benchmark_source_preflight_ready_pct": source_preflight,
                    "benchmark_bulk_equivalence_mismatch_rate": mismatch_rate,
                    "benchmark_bulk_equivalence_blocking_sources_total": blocking_mismatch_sources,
                },
                "thresholds": READINESS_THRESHOLDS,
                "source_preflight": {
                    "sources": [
                        {
                            "source": "worldbank",
                            "status": source_status,
                            "ready": source_preflight
                            >= READINESS_THRESHOLDS["benchmark_source_preflight_ready_pct"],
                        }
                    ]
                },
            },
            fh,
            ensure_ascii=False,
            indent=2,
        )


def _build_publish_receipt_fixture(
    tmp_path: Path,
    monkeypatch,
    *,
    profile_headers: dict[str, str] | None = None,
) -> DatasetBatchConfig:
    """Build a publish fixture with an explicit effective source-profile set."""
    from polisyos.fabric.connectors.profiles.models import SourceProfile
    from polisyos.fabric.connectors.profiles.registry import SourceProfileRegistry

    # The dataset YAML does not scope the connector-profile registry used by
    # producer currentness, so keep this test's effective profile set explicit.
    profiles = SourceProfileRegistry()
    profiles.register(
        SourceProfile(
            profile_id="worldbank_wdi",
            display_name="World Bank WDI fixture",
            connector_family="worldbank",
            base_url="https://example.test/worldbank",
            headers=dict(profile_headers or {}),
        )
    )
    monkeypatch.setattr(SourceProfileRegistry, "_instance", profiles)

    registry_path = tmp_path / "registry.yaml"
    _write_test_registry(registry_path)
    config = DatasetBatchConfig(snapshot_root=tmp_path / "snap", registry_path=registry_path)
    _build_publish_fixture(config)
    config.merged_records_path.write_text('{"title":"GDP"}\n', encoding="utf-8")
    config.duplicates_report_path.write_text("dataset_id,duplicate_id\n", encoding="utf-8")
    _write_qc_and_benchmark(config)
    run_content_stage_with_receipt(config, "publish")
    return config


def test_run_publish_writes_consumer_readiness_manifest(tmp_path) -> None:
    registry_path = tmp_path / "registry.yaml"
    _write_test_registry(registry_path)
    config = DatasetBatchConfig(snapshot_root=tmp_path / "snap", registry_path=registry_path)
    _build_publish_fixture(config)
    config.merged_records_path.write_text(
        '{"title":"GDP per capita","description":"desc"}\n', encoding="utf-8"
    )
    config.duplicates_report_path.write_text("dataset_id,duplicate_id\n", encoding="utf-8")
    _write_qc_and_benchmark(config)

    manifest_path = run_publish(config)

    assert manifest_path.exists()
    assert config.consumer_readiness_path.exists()

    with open(config.consumer_readiness_path, encoding="utf-8") as fh:
        readiness_payload = json.load(fh)
    with open(manifest_path, encoding="utf-8") as fh:
        manifest_payload = json.load(fh)

    assert readiness_payload["readiness"]["consumer_ready"] is True
    assert manifest_payload["extra"]["consumer_ready"] is True


def test_run_publish_blocks_when_consumer_readiness_fails(tmp_path) -> None:
    registry_path = tmp_path / "registry.yaml"
    _write_test_registry(registry_path)
    config = DatasetBatchConfig(snapshot_root=tmp_path / "snap", registry_path=registry_path)
    _build_publish_fixture(config)
    _write_qc_and_benchmark(config, search=50.0)

    try:
        run_publish(config)
    except RuntimeError as exc:
        assert "consumer readiness failed" in str(exc)
    else:
        raise AssertionError("Expected publish readiness gate to block")


def test_run_publish_blocks_when_blocking_source_status_is_missing(tmp_path) -> None:
    registry_path = tmp_path / "registry.yaml"
    _write_test_registry(registry_path)
    config = DatasetBatchConfig(snapshot_root=tmp_path / "snap", registry_path=registry_path)
    _build_publish_fixture(config)
    with open(config.qc_report_path, "w", encoding="utf-8") as fh:
        json.dump(
            {"scope": "datasets", "passed": True, "metrics": {}, "checks": []},
            fh,
            ensure_ascii=False,
            indent=2,
        )
    with open(config.benchmark_report_path, "w", encoding="utf-8") as fh:
        json.dump(
            {
                "kind": "datasets_benchmark",
                "metrics": {
                    "benchmark_search_top5_relevance_pct": 100.0,
                    "benchmark_retrieval_ready_pct": 100.0,
                    "benchmark_transport_ready_pct": 100.0,
                    "benchmark_foundry_fitness_pct": 100.0,
                    "benchmark_source_preflight_ready_pct": 100.0,
                },
                "thresholds": READINESS_THRESHOLDS,
                "source_preflight": {"sources": []},
            },
            fh,
            ensure_ascii=False,
            indent=2,
        )

    try:
        run_publish(config)
    except RuntimeError as exc:
        assert "missing blocking source statuses" in str(exc)
    else:
        raise AssertionError("Expected missing source status gate to block")


def test_run_publish_allows_core_ready_snapshot(tmp_path) -> None:
    registry_path = tmp_path / "registry.yaml"
    _write_test_registry(registry_path)
    config = DatasetBatchConfig(snapshot_root=tmp_path / "snap", registry_path=registry_path)
    _build_publish_fixture(config)
    _write_qc_and_benchmark(config, evaluation_mode="core-ready")

    manifest_path = run_publish(config)

    with open(config.consumer_readiness_path, encoding="utf-8") as fh:
        readiness_payload = json.load(fh)
    with open(manifest_path, encoding="utf-8") as fh:
        manifest_payload = json.load(fh)

    assert readiness_payload["readiness"]["consumer_ready"] is True
    assert readiness_payload["readiness"]["full_publish_ready"] is False
    assert readiness_payload["publish_mode"] == "core-ready"
    assert manifest_payload["extra"]["evaluation_mode"] == "core-ready"


def test_run_publish_blocks_partial_eval_even_if_thresholds_pass(tmp_path) -> None:
    registry_path = tmp_path / "registry.yaml"
    _write_test_registry(registry_path)
    config = DatasetBatchConfig(snapshot_root=tmp_path / "snap", registry_path=registry_path)
    _build_publish_fixture(config)
    _write_qc_and_benchmark(config, evaluation_mode="partial-eval")

    try:
        run_publish(config)
    except RuntimeError as exc:
        assert "consumer readiness failed" in str(exc)
    else:
        raise AssertionError("Expected partial-eval publish to stay blocked")


def test_publish_receipt_read_is_side_effect_free_and_detects_same_stat_drift(
    tmp_path, monkeypatch
) -> None:
    config = _build_publish_receipt_fixture(tmp_path, monkeypatch)
    registry_path = config.registry_path
    assert registry_path is not None
    database_path = config.db_path
    assert current_catalog_publish_receipt(database_path)["state"] == "current"
    from polisyos.data_forge.domains.catalog.batch import config as config_module
    from polisyos.data_forge.domains.catalog.batch.config import (
        DatasetBatchConfig as ConfigType,
    )

    stage = json.loads(config.stage_state_path.read_text(encoding="utf-8"))
    saved = stage["publish"]["input_basis"]["config"]["effective_producer_config"]
    assert ConfigType.from_producer_config_snapshot(saved) is not None
    assert (
        ConfigType.from_producer_config_snapshot(
            {k: v for k, v in saved.items() if k != "metrics_map_path"}
        )
        is None
    )
    assert ConfigType.from_producer_config_snapshot({**saved, "unexpected": True}) is None

    def fail(*_args, **_kwargs):
        raise AssertionError("read-only receipt attempted a write")

    with monkeypatch.context() as patcher:
        patcher.setattr(config_module, "ensure_dirs", fail)
        patcher.setattr(Path, "mkdir", fail)
        patcher.setattr(Path, "write_text", fail)
        patcher.setattr(Path, "write_bytes", fail)
        assert current_catalog_publish_receipt(database_path)["state"] == "current"
    stat = registry_path.stat()
    original = registry_path.read_bytes()
    changed = original.replace(b"wave: A", b"wave: B", 1)
    assert changed != original and len(changed) == len(original)
    registry_path.write_bytes(changed)
    os.utime(registry_path, ns=(stat.st_atime_ns, stat.st_mtime_ns))
    assert json.loads(config.stage_state_path.read_text())["publish"]["status"] == "complete"
    assert current_catalog_publish_receipt(config.db_path)["state"] == "stale"


def test_private_profile_values_keep_publish_receipt_not_established(
    tmp_path: Path, monkeypatch
) -> None:
    from polisyos.fabric.connectors.profiles.registry import SourceProfileRegistry
    from polisyos.fabric.connectors.profiles.resolver import resolve_connection_config

    config = _build_publish_receipt_fixture(
        tmp_path,
        monkeypatch,
        profile_headers={"X-PolicyOS-Test": "fixture-only-header-a"},
    )
    profiles = SourceProfileRegistry.get_instance()
    saved_profile = profiles.get("worldbank_wdi")
    assert saved_profile is not None
    producer_signature = config.run_signature

    first = current_catalog_publish_receipt(config.db_path)
    assert first["state"] == "not_established"
    assert first["reason"] == "profile_private_inputs_unversioned"
    assert first["profile_input_coverage_state"] == "not_established"
    saved_stage = json.loads(config.stage_state_path.read_text(encoding="utf-8"))
    assert saved_stage["publish"]["status"] == "complete"
    saved_config = saved_stage["publish"]["input_basis"]["config"]["effective_producer_config"]
    assert saved_config["resolved_profile_input_coverage"]["profiles"] == {
        "worldbank_wdi": "excluded_present"
    }
    saved_stage_json = json.dumps(saved_stage)
    assert "fixture-only-header-a" not in saved_stage_json
    assert "fixture-only-header-b" not in saved_stage_json
    private_fingerprint_a = resolve_connection_config(saved_profile).source_profile_fingerprint
    assert private_fingerprint_a is not None
    assert private_fingerprint_a not in saved_stage_json

    changed_profile = saved_profile.model_copy(
        update={"headers": {"X-PolicyOS-Test": "fixture-only-header-b"}},
        deep=True,
    )
    profiles.register(changed_profile, override=True)
    private_fingerprint_b = resolve_connection_config(changed_profile).source_profile_fingerprint
    assert private_fingerprint_b is not None
    assert private_fingerprint_b != private_fingerprint_a
    assert config.run_signature == producer_signature

    second = current_catalog_publish_receipt(config.db_path)
    assert second["state"] == "not_established"
    assert second["reason"] == "profile_private_inputs_unversioned"
    assert second["profile_input_coverage_state"] == "not_established"
    assert (
        json.loads(config.stage_state_path.read_text(encoding="utf-8"))["publish"]["status"]
        == "complete"
    )

    # The actual resume gate must refuse this persisted receipt while private
    # profile inputs still leave its producer currentness not established.
    config.resume = True
    assert config.stage_state_path.is_file()
    assert _should_skip_stage(config, "publish") is False


def test_profile_input_coverage_binds_presence_without_persisting_values(
    monkeypatch, tmp_path: Path
) -> None:
    from polisyos.data_forge.domains.catalog.batch.config import (
        _capture_runtime_source_profile_snapshot,
        _producer_config_snapshot,
    )
    from polisyos.fabric.connectors.base import ConnectionConfig
    from polisyos.fabric.connectors.profiles.models import SourceProfile
    from polisyos.fabric.connectors.profiles.registry import SourceProfileRegistry

    profiles = SourceProfileRegistry()
    profile = SourceProfile(
        profile_id="fixture_profile",
        display_name="Fixture",
        connector_family="sdmx",
        base_url="https://example.test/source",
    )
    profiles.register(profile)
    monkeypatch.setattr(SourceProfileRegistry, "_instance", profiles)
    config = DatasetBatchConfig(snapshot_root=tmp_path / "snapshot")

    no_input_signature = config.run_signature
    no_input_snapshot = _producer_config_snapshot(config)
    assert no_input_snapshot["resolved_profile_input_coverage"] == {
        "schema_version": "policyos.catalog.profile_input_coverage.v1",
        "profiles": {"fixture_profile": "none"},
    }
    malformed_snapshot = {
        **no_input_snapshot,
        "resolved_profile_input_coverage": {
            "schema_version": "policyos.catalog.profile_input_coverage.v1",
            "profiles": {"fixture_profile": "unknown"},
        },
    }
    assert DatasetBatchConfig.from_producer_config_snapshot(malformed_snapshot) is None

    headerful = profile.model_copy(
        update={"headers": {"X-PolicyOS-Test": "fixture-only-header-value"}},
        deep=True,
    )
    profiles.register(headerful, override=True)
    live_snapshot_a = _capture_runtime_source_profile_snapshot()
    connection_a = live_snapshot_a.connection_configs["fixture_profile"]
    assert isinstance(connection_a, ConnectionConfig)
    assert connection_a.source_profile_fingerprint is not None
    headerful_signature = config.run_signature
    headerful_snapshot = _producer_config_snapshot(config)
    assert headerful_signature != no_input_signature
    assert (
        headerful_snapshot["resolved_profile_input_coverage"]["profiles"]["fixture_profile"]
        == "excluded_present"
    )
    persisted_snapshot_a = json.dumps(headerful_snapshot, sort_keys=True)
    assert "fixture-only-header-value" not in persisted_snapshot_a
    assert connection_a.source_profile_fingerprint not in persisted_snapshot_a

    changed_headerful = headerful.model_copy(
        update={"headers": {"X-PolicyOS-Test": "another-fixture-value"}},
        deep=True,
    )
    profiles.register(changed_headerful, override=True)
    live_snapshot_b = _capture_runtime_source_profile_snapshot()
    connection_b = live_snapshot_b.connection_configs["fixture_profile"]
    assert isinstance(connection_b, ConnectionConfig)
    assert connection_b.source_profile_fingerprint is not None
    assert connection_b.source_profile_fingerprint != connection_a.source_profile_fingerprint
    assert connection_b.cache_scope_fingerprint != connection_a.cache_scope_fingerprint
    assert config.run_signature == headerful_signature
    changed_snapshot = _producer_config_snapshot(config)
    assert changed_snapshot == headerful_snapshot
    persisted_snapshot_b = json.dumps(changed_snapshot, sort_keys=True)
    assert "fixture-only-header-value" not in persisted_snapshot_b
    assert "another-fixture-value" not in persisted_snapshot_b
    assert connection_a.source_profile_fingerprint not in persisted_snapshot_b
    assert connection_b.source_profile_fingerprint not in persisted_snapshot_b

    profiles.register(profile, override=True)
    assert config.run_signature == no_input_signature

    authful = profile.model_copy(update={"auth_policy": "bearer"}, deep=True)
    profiles.register(authful, override=True)
    auth_signature = config.run_signature
    auth_snapshot = _producer_config_snapshot(config)
    assert auth_signature != no_input_signature
    assert (
        auth_snapshot["resolved_profile_input_coverage"]["profiles"]["fixture_profile"]
        == "excluded_present"
    )
    profiles.register(profile, override=True)
    assert config.run_signature == no_input_signature

    from polisyos.data_forge.read_api.catalog import (
        parse_profile_input_coverage,
        profile_input_coverage_currentness,
    )

    assert profile_input_coverage_currentness(
        no_input_snapshot["resolved_profile_input_coverage"]
    ) == (
        "established",
        {"fixture_profile": "none"},
    )
    assert profile_input_coverage_currentness(
        headerful_snapshot["resolved_profile_input_coverage"]
    ) == (
        "not_established",
        {"fixture_profile": "excluded_present"},
    )
    assert profile_input_coverage_currentness(None, missing=True) == (
        "legacy_unknown",
        None,
    )
    assert parse_profile_input_coverage(None, missing=True) == ("legacy_unknown", None)
    assert parse_profile_input_coverage(
        {
            "schema_version": "policyos.catalog.profile_input_coverage.v1",
            "profiles": {"fixture_profile": "unexpected"},
        }
    ) == ("malformed", None)

    unpd = SourceProfile(
        profile_id="unpd_dataportal",
        display_name="Fixture UNPD",
        connector_family="unpd",
        base_url="https://example.test/unpd",
    )
    profiles = SourceProfileRegistry()
    profiles.register(unpd)
    monkeypatch.setattr(SourceProfileRegistry, "_instance", profiles)
    monkeypatch.delenv("POLISYOS_UNPD_API_TOKEN", raising=False)
    unpd_config = DatasetBatchConfig(snapshot_root=tmp_path / "unpd-snapshot")
    no_token_signature = unpd_config.run_signature
    monkeypatch.setenv("POLISYOS_UNPD_API_TOKEN", "fixture-only-env-token")
    token_snapshot = _producer_config_snapshot(unpd_config)
    assert (
        token_snapshot["resolved_profile_input_coverage"]["profiles"]["unpd_dataportal"]
        == "excluded_present"
    )
    assert unpd_config.run_signature != no_token_signature
    assert "fixture-only-env-token" not in repr(token_snapshot)


def test_profile_snapshot_is_the_same_basis_and_runtime_connection(
    monkeypatch, tmp_path: Path
) -> None:
    from polisyos.data_forge.domains.catalog.batch.config import (
        _runtime_profile_input_currentness,
        _runtime_source_profile_snapshot_scope,
    )
    from polisyos.data_forge.domains.catalog.batch.core_sources.api import (
        _legacy_serial_mode_enabled,
        _resolve_profile_config,
    )
    from polisyos.fabric.connectors.profiles.models import SourceProfile
    from polisyos.fabric.connectors.profiles.registry import SourceProfileRegistry

    profiles = SourceProfileRegistry()
    original = SourceProfile(
        profile_id="fixture_profile",
        display_name="Fixture",
        connector_family="sdmx",
        base_url="https://example.test/source",
    )
    profiles.register(original)
    monkeypatch.setattr(SourceProfileRegistry, "_instance", profiles)
    monkeypatch.delenv("POLISYOS_UNPD_API_TOKEN", raising=False)
    monkeypatch.setenv("POLISYOS_DATASET_LEGACY_SERIAL", "0")
    config = DatasetBatchConfig(snapshot_root=tmp_path / "snapshot")

    with _runtime_source_profile_snapshot_scope():
        initial_signature = config.run_signature
        assert _legacy_serial_mode_enabled() is False
        assert _resolve_profile_config("fixture_profile").headers == {}
        assert _runtime_profile_input_currentness() == (
            "established",
            {"fixture_profile": "none"},
        )

        # A registry replacement after capture must affect the next run, while
        # the active run keeps hashing and consuming its captured profile.
        changed = original.model_copy(
            update={"headers": {"X-PolicyOS-Test": "fixture-only-secret"}},
            deep=True,
        )
        profiles.register(changed, override=True)
        monkeypatch.setenv("POLISYOS_DATASET_LEGACY_SERIAL", "yes")
        assert config.run_signature == initial_signature
        assert _legacy_serial_mode_enabled() is False
        assert _resolve_profile_config("fixture_profile").headers == {}
        assert _runtime_profile_input_currentness() == (
            "established",
            {"fixture_profile": "none"},
        )

    assert config.run_signature != initial_signature
    assert _legacy_serial_mode_enabled() is True
    assert _resolve_profile_config("fixture_profile").headers == {
        "X-PolicyOS-Test": "fixture-only-secret"
    }
    assert _runtime_profile_input_currentness() == (
        "not_established",
        {"fixture_profile": "excluded_present"},
    )


def test_core_receipt_reconciliation_uses_one_profile_snapshot(monkeypatch, tmp_path: Path) -> None:
    from polisyos.data_forge.domains.catalog.batch.config import (
        _runtime_source_profile_snapshot_scope,
    )
    from polisyos.data_forge.domains.catalog.batch.core_sources.validators import (
        _current_core_output_receipt_state,
    )
    from polisyos.fabric.connectors.profiles.models import SourceProfile
    from polisyos.fabric.connectors.profiles.registry import SourceProfileRegistry

    profiles = SourceProfileRegistry()
    original = SourceProfile(
        profile_id="fixture_profile",
        display_name="Fixture",
        connector_family="sdmx",
        base_url="https://example.test/source",
    )
    profiles.register(original)
    monkeypatch.setattr(SourceProfileRegistry, "_instance", profiles)
    config = DatasetBatchConfig(snapshot_root=tmp_path / "snapshot")

    with _runtime_source_profile_snapshot_scope():
        initial_signature = config.run_signature
        profiles.register(
            original.model_copy(
                update={"headers": {"X-PolicyOS-Test": "fixture-only-secret"}},
                deep=True,
            ),
            override=True,
        )
        receipt_state = _current_core_output_receipt_state(config)
        assert receipt_state.live_profile_input_currentness == "established"
        assert receipt_state.live_profile_input_coverage == {"fixture_profile": "none"}
        assert receipt_state.live_profile_input_basis_identity == initial_signature

    receipt_state = _current_core_output_receipt_state(config)
    assert receipt_state.live_profile_input_currentness == "not_established"
    assert receipt_state.live_profile_input_coverage == {"fixture_profile": "excluded_present"}
    assert receipt_state.live_profile_input_basis_identity != initial_signature


def test_current_publish_reader_keeps_legacy_or_malformed_coverage_unknown(
    tmp_path: Path,
) -> None:
    from polisyos.data_forge.domains.catalog.batch.pipeline import (
        current_catalog_publish_receipt,
    )

    database_path = tmp_path / "datasets" / "graph" / "dataset_catalog.duckdb"
    stage_path = tmp_path / "datasets" / "manifests" / "stage_state.json"
    stage_path.parent.mkdir(parents=True)

    def write_publish_snapshot(config: dict[str, object]) -> None:
        stage_path.write_text(
            json.dumps(
                {
                    "publish": {
                        "status": "complete",
                        "input_basis": {"config": {"effective_producer_config": config}},
                    }
                }
            ),
            encoding="utf-8",
        )

    write_publish_snapshot({})
    legacy = current_catalog_publish_receipt(database_path)
    assert legacy["state"] == "not_established"
    assert legacy["profile_input_coverage_state"] == "legacy_unknown"

    write_publish_snapshot(
        {
            "resolved_profile_input_coverage": {
                "schema_version": "wrong",
                "profiles": {"fixture_profile": "none"},
            }
        }
    )
    malformed = current_catalog_publish_receipt(database_path)
    assert malformed["state"] == "not_established"
    assert malformed["profile_input_coverage_state"] == "malformed"
