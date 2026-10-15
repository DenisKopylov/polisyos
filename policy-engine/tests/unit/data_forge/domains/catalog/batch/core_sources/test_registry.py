from __future__ import annotations

import asyncio
import hashlib
import json
import time
from dataclasses import replace

import duckdb
import pytest

from polisyos.data_forge.domains.catalog.batch import core_sources_ingest as facade
from polisyos.data_forge.domains.catalog.batch._core_sources_ingest_contracts import (
    CatalogTransportDataset,
)
from polisyos.data_forge.domains.catalog.batch.core_sources import registry, schema
from polisyos.data_forge.domains.catalog.knowledge.variable_alignment import (
    AlignmentMethod,
    VariableAlignment,
)


def test_core_sources_registry_helpers_are_reexported() -> None:
    assert callable(registry._build_catalog_observation_plans)
    assert callable(facade._build_catalog_observation_plans)


def _catalog_transport_dataset(
    *,
    profile_id: str = "worldbank_wdi",
    request_dataset_id: str = "NY.GDP.MKTP.CD",
    connector_id: str = "worldbank.wdi",
    source: str = "worldbank",
) -> CatalogTransportDataset:
    return CatalogTransportDataset(
        catalog_dataset_id="wb-gdp",
        source=source,
        title="GDP",
        description="Gross domestic product",
        source_dataset_id="WDI",
        update_frequency="annual",
        last_updated="2025-01-01",
        coverage_json='{"countries":["US"]}',
        access_json='{"access_type":"open"}',
        execution_tier="transport_ready",
        variables=("NY.GDP.MKTP.CD",),
        keywords=("gdp",),
        themes=("economy",),
        polisyos_metrics=("gdp",),
        connector_id=connector_id,
        profile_id=profile_id,
        request_dataset_id=request_dataset_id,
        default_filters={},
    )


def _bind_review_basis(
    datasets: list[CatalogTransportDataset],
    alignments: list[VariableAlignment],
    *,
    material_identity: str | None = "a" * 64,
    profiles: dict[str, str] | None = None,
) -> tuple[list[VariableAlignment], dict[tuple[str, str], object]]:
    return registry._bind_catalog_alignment_review_basis(
        datasets,
        alignments,
        profile_material_input_identity=material_identity,
        profile_input_coverage={
            "schema_version": "policyos.catalog.profile_input_coverage.v1",
            "profiles": profiles or {"worldbank_wdi": "none"},
        },
    )


def _write_review_state(
    connection: duckdb.DuckDBPyConnection,
    alignments: list[VariableAlignment],
    review_bases: dict[tuple[str, str], object],
    *,
    affected_dataset_ids: list[str] | None = None,
) -> None:
    """Persist one catalog review generation through its production helpers."""
    dataset_ids = affected_dataset_ids or sorted({item.dataset_id for item in alignments})
    registry._upsert_alignment_audit(
        connection,
        alignments,
        affected_dataset_ids=dataset_ids,
        candidate_review_bases=review_bases,
    )
    registry._upsert_catalog_alignments(
        connection,
        alignments,
        affected_dataset_ids=dataset_ids,
    )
    registry._replace_catalog_alignment_review_bases(
        connection,
        affected_dataset_ids=dataset_ids,
        candidate_review_bases=review_bases,
    )


def test_alignment_audit_schema_matches_graph_builder_schema() -> None:
    from polisyos.data_forge.domains.catalog.batch import graph_builder

    registry_connection = duckdb.connect(":memory:")
    graph_connection = duckdb.connect(":memory:")
    try:
        registry._ensure_registry_tables(registry_connection)
        graph_builder._init_schema(graph_connection)
        assert schema.resolve_alignment_audit_schema_profile(registry_connection) == (
            "graph_builder_v1_json"
        )
        assert schema.alignment_audit_table_signature(registry_connection) == (
            schema.alignment_audit_table_signature(graph_connection)
        )
    finally:
        registry_connection.close()
        graph_connection.close()


def test_alignment_review_basis_schema_is_shared_and_canonical() -> None:
    from polisyos.data_forge.domains.catalog.batch import graph_builder

    registry_connection = duckdb.connect(":memory:")
    graph_connection = duckdb.connect(":memory:")
    try:
        registry._ensure_registry_tables(registry_connection)
        graph_builder._init_schema(graph_connection)
        registry_signature = schema.alignment_review_basis_table_signature(registry_connection)
        assert registry_signature == schema.alignment_review_basis_table_signature(graph_connection)
        assert schema.resolve_alignment_review_basis_schema(registry_connection) == "v1"
    finally:
        registry_connection.close()
        graph_connection.close()


def test_review_basis_sidecar_preserves_producer_evidence_and_public_match(tmp_path) -> None:
    from polisyos.data_forge.domains.catalog.knowledge.registry import DatasetRegistry

    alignment = VariableAlignment(
        canonical_var="economic.gdp",
        dataset_var="NY.GDP.MKTP.CD",
        dataset_id="wb-gdp",
        method=AlignmentMethod.EXACT,
        confidence=1.0,
        evidence="producer-evidence;metric_binding_proxy:gdp",
    )
    dataset = _catalog_transport_dataset()
    bound_alignments, review_bases = _bind_review_basis([dataset], [alignment])
    assert bound_alignments == [alignment]
    assert alignment.evidence == "producer-evidence;metric_binding_proxy:gdp"
    basis = review_bases[("wb-gdp", "NY.GDP.MKTP.CD")]
    payload = json.loads(basis.basis_json)
    assert payload["selected_profile_id"] == "worldbank_wdi"
    assert payload["alignment_group"][0]["evidence"] == alignment.evidence
    assert hashlib.sha256(basis.basis_json.encode("utf-8")).hexdigest() == basis.basis_sha256

    db_path = tmp_path / "alignment-review-basis.duckdb"
    connection = duckdb.connect(str(db_path))
    try:
        registry._ensure_registry_tables(connection)
        registry._upsert_catalog_registry_datasets(connection, [dataset])
        registry._upsert_alignment_audit(
            connection,
            bound_alignments,
            candidate_review_bases=review_bases,
        )
        registry._upsert_catalog_alignments(connection, bound_alignments)
        registry._replace_catalog_alignment_review_bases(
            connection,
            affected_dataset_ids=["wb-gdp"],
            candidate_review_bases=review_bases,
        )
        connection.execute(
            "UPDATE ds_alignment_audit SET reviewed = TRUE, reviewer_override = 'fixture'"
        )
        evidence = connection.execute(
            "SELECT evidence FROM ds_variable_alignments WHERE dataset_id = 'wb-gdp'"
        ).fetchone()[0]
        assert evidence == alignment.evidence
        stored_basis = connection.execute(
            "SELECT basis_version, basis_json, basis_sha256 FROM ds_alignment_review_basis "
            "WHERE dataset_id = 'wb-gdp' AND raw_variable = 'NY.GDP.MKTP.CD'"
        ).fetchone()
        assert stored_basis == (
            registry._ALIGNMENT_REVIEW_BASIS_VERSION,
            basis.basis_json,
            basis.basis_sha256,
        )
    finally:
        connection.close()

    public_match = DatasetRegistry(db_path).find_datasets_for_variable("economic.gdp", "US")
    assert len(public_match) == 1
    assert public_match[0].alignment_evidence == alignment.evidence

    connection = duckdb.connect(str(db_path))
    try:
        connection.execute(
            "UPDATE ds_alignment_review_basis SET basis_sha256 = ? "
            "WHERE dataset_id = 'wb-gdp' AND raw_variable = 'NY.GDP.MKTP.CD'",
            ["0" * 64],
        )
        registry._upsert_alignment_audit(
            connection,
            bound_alignments,
            candidate_review_bases=review_bases,
        )
        registry._upsert_catalog_alignments(connection, bound_alignments)
        registry._replace_catalog_alignment_review_bases(
            connection,
            affected_dataset_ids=["wb-gdp"],
            candidate_review_bases=review_bases,
        )
        assert connection.execute(
            "SELECT reviewed, reviewer_override FROM ds_alignment_audit WHERE dataset_id = 'wb-gdp'"
        ).fetchone() == (False, None)
    finally:
        connection.close()

    replayed_match = DatasetRegistry(db_path).find_datasets_for_variable("economic.gdp", "US")
    assert len(replayed_match) == 1
    assert replayed_match[0].alignment_evidence == alignment.evidence


def test_alignment_review_basis_rejects_physical_schema_drift_before_audit_write() -> None:
    alignment = VariableAlignment(
        canonical_var="economic.gdp",
        dataset_var="NY.GDP.MKTP.CD",
        dataset_id="wb-gdp",
        method=AlignmentMethod.EXACT,
        confidence=1.0,
        evidence="producer-evidence",
    )
    dataset = _catalog_transport_dataset()
    alignments, bases = _bind_review_basis([dataset], [alignment])
    connection = duckdb.connect(":memory:")
    try:
        registry._ensure_registry_tables(connection)
        _write_review_state(connection, alignments, bases)
        connection.execute(
            "UPDATE ds_alignment_audit SET reviewed = TRUE, reviewer_override = 'fixture'"
        )
        connection.execute(
            "ALTER TABLE ds_alignment_review_basis ADD COLUMN unowned_column VARCHAR"
        )
        with pytest.raises(RuntimeError, match="unsupported physical schema"):
            registry._upsert_alignment_audit(
                connection,
                alignments,
                candidate_review_bases=bases,
            )
        assert connection.execute(
            "SELECT reviewed, reviewer_override FROM ds_alignment_audit"
        ).fetchone() == (True, "fixture")
    finally:
        connection.close()


def test_graph_rebuild_clears_catalog_alignment_review_basis_and_related_rows() -> None:
    from polisyos.data_forge.domains.catalog.batch import graph_builder

    connection = duckdb.connect(":memory:")
    try:
        graph_builder._init_schema(connection)
        registry._ensure_registry_tables(connection)
        registry._upsert_catalog_registry_datasets(connection, [_catalog_transport_dataset()])
        alignment = VariableAlignment(
            canonical_var="economic.gdp",
            dataset_var="NY.GDP.MKTP.CD",
            dataset_id="wb-gdp",
            method=AlignmentMethod.EXACT,
            confidence=1.0,
            evidence="seed-source-v1",
        )
        alignments, bases = _bind_review_basis([_catalog_transport_dataset()], [alignment])
        registry._upsert_catalog_alignments(connection, alignments)
        registry._upsert_alignment_audit(connection, alignments, candidate_review_bases=bases)
        registry._replace_catalog_alignment_review_bases(
            connection,
            affected_dataset_ids=["wb-gdp"],
            candidate_review_bases=bases,
        )

        graph_builder._truncate(connection)

        table_counts = (
            ("ds_registry_datasets", "SELECT COUNT(*) FROM ds_registry_datasets"),
            ("ds_variable_alignments", "SELECT COUNT(*) FROM ds_variable_alignments"),
            ("ds_alignment_audit", "SELECT COUNT(*) FROM ds_alignment_audit"),
            (
                "ds_alignment_review_basis",
                "SELECT COUNT(*) FROM ds_alignment_review_basis",
            ),
        )
        for _table, query in table_counts:
            assert connection.execute(query).fetchone() == (0,)
    finally:
        connection.close()


def test_alignment_audit_upsert_persists_every_row_in_a_batch() -> None:
    alignments = [
        VariableAlignment(
            canonical_var=canonical_var,
            dataset_var=dataset_var,
            dataset_id="wb-gdp",
            method=AlignmentMethod.EXACT,
            confidence=1.0,
            evidence="seed-source-v1",
        )
        for canonical_var, dataset_var in (
            ("economic.gdp", "NY.GDP.MKTP.CD"),
            ("economic.gdp_per_capita", "NY.GDP.PCAP.CD"),
        )
    ]
    connection = duckdb.connect(":memory:")
    try:
        registry._ensure_registry_tables(connection)
        assert registry._upsert_alignment_audit(connection, alignments) == 2
        persisted_rows = connection.execute(
            "SELECT raw_variable, canonical_variable FROM ds_alignment_audit ORDER BY raw_variable"
        ).fetchall()
        assert persisted_rows == [
            ("NY.GDP.MKTP.CD", "economic.gdp"),
            ("NY.GDP.PCAP.CD", "economic.gdp_per_capita"),
        ]
    finally:
        connection.close()


def test_alignment_review_basis_covers_every_live_producer_model_field() -> None:
    alignment = VariableAlignment(
        canonical_var="economic.gdp",
        dataset_var="NY.GDP.MKTP.CD",
        dataset_id="wb-gdp",
        method=AlignmentMethod.EXACT,
        confidence=1.0,
        evidence="seed-source-v1",
    )
    dataset = _catalog_transport_dataset()
    baseline_alignments, baseline_bases = _bind_review_basis([dataset], [alignment])
    baseline = baseline_alignments[0]
    baseline_basis = baseline_bases[("wb-gdp", "NY.GDP.MKTP.CD")]
    baseline_payload = json.loads(baseline_basis.basis_json)
    assert baseline.evidence == alignment.evidence
    assert baseline_payload["alignment_group"][0] == alignment.model_dump(mode="json")

    for field_name, field in VariableAlignment.model_fields.items():
        current = getattr(alignment, field_name)
        if isinstance(current, AlignmentMethod):
            changed_value = AlignmentMethod.SEMANTIC
        elif type(current) is bool:
            changed_value = not current
        elif type(current) is float:
            changed_value = current + 0.125
        elif isinstance(current, str):
            changed_value = current + ":changed"
        else:
            pytest.fail(
                f"add a truthful mutation for new model field {field_name}: {field.annotation!r}"
            )
        changed = alignment.model_copy(update={field_name: changed_value})
        changed_alignments, changed_bases = _bind_review_basis([dataset], [changed])
        assert changed_alignments[0].evidence == changed.evidence
        changed_key = (changed.dataset_id, changed.dataset_var)
        if changed_key in changed_bases:
            assert changed_bases[changed_key].basis_sha256 != baseline_basis.basis_sha256, (
                field_name
            )
        else:
            assert field_name == "dataset_id"


@pytest.mark.parametrize(
    "change",
    [
        {"source": "eurostat"},
        {"connector_id": "rest.json"},
        {"profile_id": "worldbank_wdi_alt"},
        {"request_dataset_id": "NY.GDP.MKTP.CD_ALT"},
    ],
)
def test_alignment_review_basis_binds_source_profile_and_request_dto(
    change: dict[str, str],
) -> None:
    alignment = VariableAlignment(
        canonical_var="economic.gdp",
        dataset_var="NY.GDP.MKTP.CD",
        dataset_id="wb-gdp",
        method=AlignmentMethod.EXACT,
        confidence=1.0,
        evidence="seed-source-v1",
    )
    first_dataset = _catalog_transport_dataset()
    first_alignments, first_bases = _bind_review_basis([first_dataset], [alignment])
    first = first_alignments[0]
    first_basis = first_bases[("wb-gdp", "NY.GDP.MKTP.CD")]
    second_dataset = replace(first_dataset, **change)
    profiles = {"worldbank_wdi": "none", "worldbank_wdi_alt": "none"}
    second_alignments, second_bases = _bind_review_basis(
        [second_dataset], [alignment], profiles=profiles
    )
    second = second_alignments[0]
    second_basis = second_bases[("wb-gdp", "NY.GDP.MKTP.CD")]
    assert second.evidence == first.evidence
    assert second_basis.basis_sha256 != first_basis.basis_sha256

    changed_material_alignments, changed_material_bases = _bind_review_basis(
        [first_dataset], [alignment], material_identity="b" * 64
    )
    assert changed_material_alignments[0].evidence == first.evidence
    assert (
        changed_material_bases[("wb-gdp", "NY.GDP.MKTP.CD")].basis_sha256
        != first_basis.basis_sha256
    )


@pytest.mark.parametrize(
    ("profile_state", "material_identity"),
    [("excluded_present", "a" * 64), ("none", None)],
)
def test_unavailable_profile_material_cannot_retain_review(
    profile_state: str,
    material_identity: str | None,
) -> None:
    alignment = VariableAlignment(
        canonical_var="economic.gdp",
        dataset_var="NY.GDP.MKTP.CD",
        dataset_id="wb-gdp",
        method=AlignmentMethod.EXACT,
        confidence=1.0,
        evidence="seed-source-v1",
    )
    dataset = _catalog_transport_dataset()
    bound, bound_bases = _bind_review_basis([dataset], [alignment])
    unavailable, unavailable_bases = _bind_review_basis(
        [dataset],
        [alignment],
        material_identity=material_identity,
        profiles={"worldbank_wdi": profile_state},
    )
    assert set(bound_bases) == {("wb-gdp", "NY.GDP.MKTP.CD")}
    assert unavailable_bases == {}
    assert bound[0].evidence == unavailable[0].evidence == alignment.evidence

    connection = duckdb.connect(":memory:")
    try:
        registry._ensure_registry_tables(connection)
        _write_review_state(connection, bound, bound_bases)
        connection.execute(
            "UPDATE ds_alignment_audit SET reviewed = TRUE, reviewer_override = 'fixture'"
        )
        _write_review_state(connection, unavailable, unavailable_bases)
        row = connection.execute(
            "SELECT reviewed, reviewer_override FROM ds_alignment_audit WHERE dataset_id = 'wb-gdp'"
        ).fetchone()
        assert row == (False, None)
    finally:
        connection.close()


def test_changed_competing_candidate_group_resets_review_and_replaces_relation() -> None:
    first = VariableAlignment(
        canonical_var="economic.gdp",
        dataset_var="NY.GDP.MKTP.CD",
        dataset_id="wb-gdp",
        method=AlignmentMethod.EXACT,
        confidence=1.0,
        evidence="seed-source-v1",
    )
    second = first.model_copy(
        update={
            "canonical_var": "economic.gdp_per_capita",
            "method": AlignmentMethod.SEMANTIC,
            "confidence": 0.8,
            "evidence": "candidate-two",
        }
    )
    dataset = _catalog_transport_dataset()
    original_group, original_bases = _bind_review_basis([dataset], [first, second])
    reduced_group, reduced_bases = _bind_review_basis([dataset], [first])
    connection = duckdb.connect(":memory:")
    try:
        registry._ensure_registry_tables(connection)
        _write_review_state(connection, original_group, original_bases)
        connection.execute(
            "UPDATE ds_alignment_audit SET reviewed = TRUE, reviewer_override = 'fixture'"
        )

        registry._upsert_alignment_audit(
            connection,
            reduced_group,
            affected_dataset_ids=["wb-gdp"],
            candidate_review_bases=reduced_bases,
        )
        assert connection.execute(
            "SELECT COUNT(*) FROM ds_alignment_audit WHERE dataset_id = 'wb-gdp' AND reviewed"
        ).fetchone() == (0,)
        registry._upsert_catalog_alignments(
            connection,
            reduced_group,
            affected_dataset_ids=["wb-gdp"],
        )
        registry._replace_catalog_alignment_review_bases(
            connection,
            affected_dataset_ids=["wb-gdp"],
            candidate_review_bases=reduced_bases,
        )
        assert connection.execute(
            "SELECT canonical_var FROM ds_variable_alignments WHERE dataset_id = 'wb-gdp'"
        ).fetchall() == [("economic.gdp",)]

        connection.execute(
            "UPDATE ds_alignment_audit SET reviewed = TRUE, reviewer_override = 'fixture' "
            "WHERE canonical_variable = 'economic.gdp'"
        )
        _write_review_state(
            connection,
            reduced_group,
            reduced_bases,
            affected_dataset_ids=["wb-gdp"],
        )
        assert connection.execute(
            "SELECT reviewed, reviewer_override FROM ds_alignment_audit "
            "WHERE canonical_variable = 'economic.gdp'"
        ).fetchone() == (True, "fixture")
    finally:
        connection.close()


def test_core_source_ingest_recomputes_profile_material_before_review_retention(
    tmp_path, monkeypatch
) -> None:
    from polisyos.data_forge.domains.catalog.batch import config as batch_config
    from polisyos.data_forge.domains.catalog.batch._core_sources_ingest_contracts import (
        CoreSourcesIngestStats,
    )
    from polisyos.data_forge.domains.catalog.batch.config import DatasetBatchConfig
    from polisyos.data_forge.domains.catalog.batch.core_sources import api as core_api
    from polisyos.fabric.connectors.profiles.models import SourceProfile
    from polisyos.fabric.connectors.profiles.registry import SourceProfileRegistry

    profiles = SourceProfileRegistry()
    profile = SourceProfile(
        profile_id="fixture_profile",
        display_name="Fixture source",
        connector_family="sdmx",
        base_url="https://source-a.example.test",
    )
    profiles.register(profile)
    monkeypatch.setattr(SourceProfileRegistry, "_instance", profiles)

    config = DatasetBatchConfig(snapshot_root=tmp_path / "snapshot")
    config.db_path.parent.mkdir(parents=True, exist_ok=True)
    dataset = _catalog_transport_dataset(profile_id="fixture_profile")
    alignment = VariableAlignment(
        canonical_var="economic.gdp",
        dataset_var="NY.GDP.MKTP.CD",
        dataset_id="wb-gdp",
        method=AlignmentMethod.EXACT,
        confidence=1.0,
        evidence="producer-evidence",
    )
    monkeypatch.setattr(
        core_api,
        "_load_catalog_transport_datasets",
        lambda _con, _config: [dataset],
    )
    monkeypatch.setattr(
        core_api,
        "_build_catalog_alignments",
        lambda _datasets, _seed_path: [alignment],
    )
    monkeypatch.setattr(
        core_api,
        "_build_catalog_observation_plans",
        lambda *_args, **_kwargs: [],
    )

    async def _no_observation_ingest(*_args, **_kwargs):
        return CoreSourcesIngestStats()

    monkeypatch.setattr(core_api, "_ingest_catalog_observations", _no_observation_ingest)

    async def _run() -> None:
        await core_api._run_core_sources_ingest_async(config)

    asyncio.run(_run())
    with duckdb.connect(str(config.db_path)) as connection:
        first_evidence = connection.execute(
            "SELECT evidence FROM ds_variable_alignments WHERE dataset_id = 'wb-gdp'"
        ).fetchone()[0]
        first_basis = connection.execute(
            "SELECT basis_version, basis_json, basis_sha256 "
            "FROM ds_alignment_review_basis WHERE dataset_id = 'wb-gdp'"
        ).fetchone()
        first_audit = connection.execute(
            "SELECT audit_id, resolved_at FROM ds_alignment_audit WHERE dataset_id = 'wb-gdp'"
        ).fetchone()
        assert first_evidence == alignment.evidence
        assert first_basis is not None
        assert registry._alignment_review_basis_record_is_valid(
            registry._AlignmentReviewBasisRecord(
                dataset_id="wb-gdp",
                raw_variable="NY.GDP.MKTP.CD",
                basis_version=first_basis[0],
                basis_json=first_basis[1],
                basis_sha256=first_basis[2],
            )
        )
        connection.execute(
            "UPDATE ds_alignment_audit SET reviewed = TRUE, reviewer_override = 'fixture'"
        )

    asyncio.run(_run())
    with duckdb.connect(str(config.db_path)) as connection:
        unchanged = connection.execute(
            "SELECT audit_id, resolved_at, reviewed, reviewer_override "
            "FROM ds_alignment_audit WHERE dataset_id = 'wb-gdp'"
        ).fetchone()
        assert unchanged == (*first_audit, True, "fixture")

    profiles.register(
        profile.model_copy(update={"base_url": "https://source-b.example.test"}, deep=True),
        override=True,
    )
    assert (
        batch_config._producer_config_snapshot(config)["resolved_profile_input_coverage"][
            "profiles"
        ]["fixture_profile"]
        == "none"
    )
    asyncio.run(_run())
    with duckdb.connect(str(config.db_path)) as connection:
        changed = connection.execute(
            "SELECT reviewed, reviewer_override FROM ds_alignment_audit WHERE dataset_id = 'wb-gdp'"
        ).fetchone()
        assert changed == (False, None)


def test_catalog_registry_audit_basis_and_alignments_rollback_together(
    tmp_path, monkeypatch
) -> None:
    from polisyos.data_forge.domains.catalog.batch._core_sources_ingest_contracts import (
        CoreSourcesIngestStats,
    )
    from polisyos.data_forge.domains.catalog.batch.config import DatasetBatchConfig
    from polisyos.data_forge.domains.catalog.batch.core_sources import api as core_api
    from polisyos.data_forge.domains.catalog.batch.core_sources import registry as core_registry
    from polisyos.fabric.connectors.profiles.models import SourceProfile
    from polisyos.fabric.connectors.profiles.registry import SourceProfileRegistry

    profiles = SourceProfileRegistry()
    profiles.register(
        SourceProfile(
            profile_id="atomic_profile",
            display_name="Atomic source",
            connector_family="sdmx",
            base_url="https://atomic.example.test",
        )
    )
    monkeypatch.setattr(SourceProfileRegistry, "_instance", profiles)
    config = DatasetBatchConfig(snapshot_root=tmp_path / "catalog-atomic")
    config.db_path.parent.mkdir(parents=True, exist_ok=True)
    incoming: dict[str, CatalogTransportDataset] = {
        "dataset": _catalog_transport_dataset(profile_id="atomic_profile")
    }
    alignment = VariableAlignment(
        canonical_var="economic.gdp",
        dataset_var="NY.GDP.MKTP.CD",
        dataset_id="wb-gdp",
        method=AlignmentMethod.EXACT,
        confidence=1.0,
        evidence="producer-evidence-v1",
    )
    monkeypatch.setattr(
        core_api,
        "_load_catalog_transport_datasets",
        lambda _con, _config: [incoming["dataset"]],
    )
    monkeypatch.setattr(
        core_api,
        "_build_catalog_alignments",
        lambda _datasets, _seed_path: [alignment],
    )
    monkeypatch.setattr(core_api, "_build_catalog_observation_plans", lambda *_a, **_k: [])

    async def no_observations(*_args, **_kwargs):
        return CoreSourcesIngestStats()

    monkeypatch.setattr(core_api, "_ingest_catalog_observations", no_observations)

    def table_snapshot() -> dict[str, tuple[tuple[object, ...], ...]]:
        with duckdb.connect(str(config.db_path), read_only=True) as connection:
            queries = {
                "ds_registry_datasets": "SELECT * FROM ds_registry_datasets ORDER BY ALL",
                "ds_variable_alignments": "SELECT * FROM ds_variable_alignments ORDER BY ALL",
                "ds_alignment_audit": "SELECT * FROM ds_alignment_audit ORDER BY ALL",
                "ds_alignment_review_basis": (
                    "SELECT * FROM ds_alignment_review_basis ORDER BY ALL"
                ),
            }
            return {
                table: tuple(connection.execute(query).fetchall())
                for table, query in queries.items()
            }

    asyncio.run(core_api._run_core_sources_ingest_async(config))
    before = table_snapshot()
    assert before["ds_registry_datasets"]
    assert before["ds_variable_alignments"]
    assert before["ds_alignment_audit"]
    assert before["ds_alignment_review_basis"]

    incoming["dataset"] = replace(incoming["dataset"], title="revised candidate")
    original_alignment_upsert = core_registry._upsert_catalog_alignments

    def fail_after_alignment_upsert(*args, **kwargs):
        original_alignment_upsert(*args, **kwargs)
        raise RuntimeError("injected after alignment relation write")

    monkeypatch.setattr(core_api, "_upsert_catalog_alignments", fail_after_alignment_upsert)
    with pytest.raises(RuntimeError, match="after alignment relation write"):
        asyncio.run(core_api._run_core_sources_ingest_async(config))
    assert table_snapshot() == before


def test_legacy_registry_audit_basis_and_alignments_rollback_together(
    tmp_path, monkeypatch
) -> None:
    from polisyos.data_forge.domains.catalog.batch._core_sources_ingest_contracts import (
        CoreSourcesIngestStats,
    )
    from polisyos.data_forge.domains.catalog.batch.config import DatasetBatchConfig
    from polisyos.data_forge.domains.catalog.batch.core_sources import api as core_api
    from polisyos.data_forge.domains.catalog.batch.core_sources import writers as core_writers

    config = DatasetBatchConfig(snapshot_root=tmp_path / "legacy-atomic")
    config.db_path.parent.mkdir(parents=True, exist_ok=True)
    seed_path = tmp_path / "seed.yaml"
    seed_path.write_text(
        "alignments:\n"
        "  - canonical_var: economic.gdp\n"
        "    dataset_var: NY.GDP.MKTP.CD\n"
        "    dataset_id: WB_WDI\n"
        "    method: exact\n"
        "    confidence: 1.0\n"
        "    evidence: legacy-seed-v1\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(core_api, "_load_catalog_transport_datasets", lambda *_args: [])
    monkeypatch.setattr(core_api, "_seed_alignments_path", lambda: seed_path)

    async def no_legacy_observations(_db_path):
        return CoreSourcesIngestStats()

    monkeypatch.setattr(core_api, "_legacy_ingest_observations", no_legacy_observations)

    def table_snapshot() -> dict[str, tuple[tuple[object, ...], ...]]:
        with duckdb.connect(str(config.db_path), read_only=True) as connection:
            queries = {
                "ds_registry_datasets": "SELECT * FROM ds_registry_datasets ORDER BY ALL",
                "ds_variable_alignments": "SELECT * FROM ds_variable_alignments ORDER BY ALL",
                "ds_alignment_audit": "SELECT * FROM ds_alignment_audit ORDER BY ALL",
                "ds_alignment_review_basis": (
                    "SELECT * FROM ds_alignment_review_basis ORDER BY ALL"
                ),
            }
            return {
                table: tuple(connection.execute(query).fetchall())
                for table, query in queries.items()
            }

    asyncio.run(core_api._run_core_sources_ingest_async(config))
    with duckdb.connect(str(config.db_path)) as connection:
        dataset = replace(_catalog_transport_dataset(), catalog_dataset_id="WB_WDI")
        alignment = VariableAlignment(
            canonical_var="economic.gdp",
            dataset_var="NY.GDP.MKTP.CD",
            dataset_id="WB_WDI",
            method=AlignmentMethod.EXACT,
            confidence=1.0,
            evidence="legacy-seed-v1",
        )
        alignments, bases = _bind_review_basis([dataset], [alignment])
        _write_review_state(connection, alignments, bases)
        connection.execute(
            "UPDATE ds_alignment_audit SET reviewed = TRUE, reviewer_override = 'fixture' "
            "WHERE dataset_id = 'WB_WDI'"
        )
        connection.execute(
            "UPDATE ds_registry_datasets SET last_updated = '1999-01-01' "
            "WHERE dataset_id = 'WB_WDI'"
        )
    before = table_snapshot()

    original_seed_upsert = core_writers._upsert_seed_alignments

    def fail_after_seed_upsert(*args, **kwargs):
        original_seed_upsert(*args, **kwargs)
        raise RuntimeError("injected after legacy alignment relation write")

    monkeypatch.setattr(core_api, "_upsert_seed_alignments", fail_after_seed_upsert)
    with pytest.raises(RuntimeError, match="after legacy alignment relation write"):
        asyncio.run(core_api._run_core_sources_ingest_async(config))
    assert table_snapshot() == before


@pytest.mark.parametrize(
    "schema_profile",
    ["registry_v1_varchar", "graph_builder_v1_json"],
)
def test_alignment_audit_resolution_time_tracks_complete_row_semantics(
    schema_profile: schema.AlignmentAuditSchemaProfile,
) -> None:
    alignment = VariableAlignment(
        canonical_var="economic.gdp",
        dataset_var="NY.GDP.MKTP.CD",
        dataset_id="wb-gdp",
        method=AlignmentMethod.EXACT,
        confidence=1.0,
        evidence="seed-source-v1",
    )
    connection = duckdb.connect(":memory:")
    try:
        if schema_profile == "registry_v1_varchar":
            schema.create_alignment_audit_table(connection, profile=schema_profile)
        registry._ensure_registry_tables(connection)
        assert schema.resolve_alignment_audit_schema_profile(connection) == schema_profile
        dataset = _catalog_transport_dataset()
        baseline, baseline_bases = _bind_review_basis([dataset], [alignment])
        _write_review_state(connection, baseline, baseline_bases)
        first = connection.execute(
            "SELECT * FROM ds_alignment_audit WHERE dataset_id = 'wb-gdp'"
        ).fetchone()
        assert first is not None
        columns = [
            str(column[1])
            for column in connection.execute("PRAGMA table_info('ds_alignment_audit')").fetchall()
        ]
        first_row = dict(zip(columns, first, strict=True))

        # Persisted review annotations are not producer-owned defaults.
        connection.execute(
            "UPDATE ds_alignment_audit SET reviewed = TRUE, reviewer_override = ? "
            "WHERE audit_id = ?",
            ["reviewer-fixture:retain-on-same-basis", first_row["audit_id"]],
        )
        reviewed = connection.execute(
            "SELECT * FROM ds_alignment_audit WHERE dataset_id = 'wb-gdp'"
        ).fetchone()
        assert reviewed is not None
        reviewed_row = dict(zip(columns, reviewed, strict=True))
        assert reviewed_row["reviewed"] is True
        assert reviewed_row["reviewer_override"] == "reviewer-fixture:retain-on-same-basis"

        # A complete producer-basis no-op preserves resolution time and annotations.
        _write_review_state(connection, baseline, baseline_bases)
        unchanged = connection.execute(
            "SELECT * FROM ds_alignment_audit WHERE dataset_id = 'wb-gdp'"
        ).fetchone()
        assert unchanged is not None
        unchanged_row = dict(zip(columns, unchanged, strict=True))
        assert unchanged_row == reviewed_row

        # The generic comparator includes future fields instead of silently dropping them.
        assert not registry._alignment_audit_rows_semantically_equal(
            {**unchanged_row, "future_decision_basis": "basis-a"},
            {**unchanged_row, "future_decision_basis": "basis-b"},
        )

        time.sleep(0.01)
        changed_alignment = alignment.model_copy(
            update={
                "method": AlignmentMethod.SEMANTIC,
                "confidence": 0.75,
                "evidence": "seed-source-v2",
            }
        )
        changed_basis, changed_bases = _bind_review_basis([dataset], [changed_alignment])
        _write_review_state(connection, changed_basis, changed_bases)
        changed = connection.execute(
            "SELECT * FROM ds_alignment_audit WHERE dataset_id = 'wb-gdp'"
        ).fetchone()
        assert changed is not None
        changed_row = dict(zip(columns, changed, strict=True))
        assert changed_row["resolved_at"] != first_row["resolved_at"]
        assert changed_row["method"] == AlignmentMethod.SEMANTIC.value
        assert changed_row["raw_confidence"] == 0.75
        assert changed_row["reviewed"] is False
        assert changed_row["reviewer_override"] is None

        # A physical schema extension is refused before any existing row is rewritten.
        connection.execute("ALTER TABLE ds_alignment_audit ADD COLUMN unowned_column VARCHAR")
        with pytest.raises(RuntimeError, match="unsupported physical schema"):
            registry._upsert_alignment_audit(
                connection,
                changed_basis,
                candidate_review_bases=changed_bases,
            )
        after_schema_drift = connection.execute(
            "SELECT * FROM ds_alignment_audit WHERE dataset_id = 'wb-gdp'"
        ).fetchone()
        assert after_schema_drift is not None
        drift_columns = [
            str(column[1])
            for column in connection.execute("PRAGMA table_info('ds_alignment_audit')").fetchall()
        ]
        assert dict(zip(drift_columns, after_schema_drift, strict=True)) == {
            **changed_row,
            "unowned_column": None,
        }
    finally:
        connection.close()


@pytest.mark.parametrize(
    "schema_drift",
    ["resolved_at_type", "reviewed_default", "primary_key", "constraints"],
)
def test_alignment_audit_rejects_same_name_physical_schema_drift_before_write(
    schema_drift: str,
) -> None:
    alignment = VariableAlignment(
        canonical_var="economic.gdp",
        dataset_var="NY.GDP.MKTP.CD",
        dataset_id="wb-gdp",
        method=AlignmentMethod.EXACT,
        confidence=1.0,
        evidence="seed-source-v1",
    )
    connection = duckdb.connect(":memory:")
    try:
        registry._ensure_registry_tables(connection)
        assert registry._upsert_alignment_audit(connection, [alignment]) == 1
        initial = connection.execute(
            "SELECT * FROM ds_alignment_audit WHERE dataset_id = 'wb-gdp'"
        ).fetchone()
        assert initial is not None
        columns = [
            str(column[1])
            for column in connection.execute("PRAGMA table_info('ds_alignment_audit')").fetchall()
        ]
        initial_row = dict(zip(columns, initial, strict=True))
        connection.execute(
            "UPDATE ds_alignment_audit SET reviewed = TRUE, reviewer_override = ? "
            "WHERE audit_id = ?",
            ["reviewer-fixture:do-not-touch-on-unknown-schema", initial_row["audit_id"]],
        )
        connection.execute("DROP INDEX idx_alignment_audit_dataset")
        if schema_drift == "resolved_at_type":
            connection.execute(
                "ALTER TABLE ds_alignment_audit ALTER COLUMN resolved_at SET DATA TYPE TIMESTAMP"
            )
        elif schema_drift == "reviewed_default":
            connection.execute(
                "ALTER TABLE ds_alignment_audit ALTER COLUMN reviewed SET DEFAULT NULL"
            )
        elif schema_drift == "primary_key":
            connection.execute("ALTER TABLE ds_alignment_audit RENAME TO ds_alignment_audit_source")
            connection.execute(
                "CREATE TABLE ds_alignment_audit ("
                "audit_id VARCHAR NOT NULL, dataset_id VARCHAR PRIMARY KEY, "
                "raw_variable VARCHAR NOT NULL, canonical_variable VARCHAR, "
                "method VARCHAR NOT NULL, raw_confidence FLOAT, calibrated_confidence FLOAT, "
                "alternatives_json JSON DEFAULT '[]', resolved_at VARCHAR, "
                "reviewed BOOLEAN DEFAULT FALSE, reviewer_override VARCHAR DEFAULT NULL)"
            )
            connection.execute(
                "INSERT INTO ds_alignment_audit SELECT * FROM ds_alignment_audit_source"
            )
        else:
            connection.execute("ALTER TABLE ds_alignment_audit RENAME TO ds_alignment_audit_source")
            connection.execute(
                "CREATE TABLE ds_alignment_audit AS SELECT * FROM ds_alignment_audit_source"
            )
        before_write = connection.execute(
            "SELECT * FROM ds_alignment_audit WHERE dataset_id = 'wb-gdp'"
        ).fetchone()
        assert before_write is not None

        with pytest.raises(RuntimeError, match="unsupported physical schema"):
            registry._upsert_alignment_audit(connection, [alignment])

        after_refusal = connection.execute(
            "SELECT * FROM ds_alignment_audit WHERE dataset_id = 'wb-gdp'"
        ).fetchone()
        assert after_refusal == before_write
        assert after_refusal[columns.index("reviewed")] is True
        assert (
            after_refusal[columns.index("reviewer_override")]
            == "reviewer-fixture:do-not-touch-on-unknown-schema"
        )
    finally:
        connection.close()
