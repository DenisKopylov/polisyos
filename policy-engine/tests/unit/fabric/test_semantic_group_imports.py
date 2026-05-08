from __future__ import annotations

import importlib
import sys
from datetime import UTC
from decimal import Decimal
from pathlib import Path

import pandas as pd
import pytest


ARTIFACT_ID = "sha256:" + "a" * 64


@pytest.mark.parametrize(
    ("module_name", "export_name"),
    [
        ("polisyos.fabric.ingestion.ingestion", "DatasetFetchSpec"),
        ("polisyos.fabric.ingestion.ingestion_providers", "IngestionDependencies"),
        ("polisyos.fabric.connectors.ingestion.connectors_ingestion", "run"),
        ("polisyos.fabric.trust.trust", "two_pass_compare"),
        ("polisyos.fabric.trust.adapter", "envelope_from_trust_bounds"),
        ("polisyos.fabric.quality.quality", "QualityIndicators"),
        ("polisyos.fabric.quality.fitness_report", "DataFitnessReport"),
        ("polisyos.fabric.quality.processing_guarantees", "ProcessingGuaranteeContract"),
        ("polisyos.fabric.evidence.evidence", "build_evidence_bundle"),
        ("polisyos.fabric.evidence.fact_writer", "build_fact"),
        ("polisyos.fabric.evidence.decision_data", "FabricDecisionData"),
        ("polisyos.fabric.identity.manifest", "DatasetManifest"),
        ("polisyos.fabric.identity.segment_manifest", "write_segment_manifest"),
        ("polisyos.fabric.numerics.finite", "ensure_probability"),
        ("polisyos.fabric.data_plane.tabular", "require_dataframe"),
        ("polisyos.fabric.data_plane.temporal", "parse_datetime_utc"),
        ("polisyos.fabric.config.config", "FabricConfig"),
    ],
)
def test_fabric_wave3_semantic_group_modules_import(module_name: str, export_name: str) -> None:
    module = importlib.import_module(module_name)

    assert hasattr(module, export_name)


def test_fabric_ingestion_group_keeps_manifest_shape_behavior() -> None:
    from polisyos.fabric.ingestion.ingestion import ConnectorManifestSpec, DatasetFetchSpec

    manifest = ConnectorManifestSpec.from_mapping(
        {
            "datasets": [
                    {
                        "connector_id": "worldbank.wdi",
                        "dataset_id": "ny.gdp.mktp.cd",
                        "filters": {"country": ["ua", "pl"]},
                        "page_size": "250",
                    }
                ],
            "allow_local_transform_dag": "false",
        }
    )

    assert isinstance(manifest.datasets[0], DatasetFetchSpec)
    assert manifest.to_dict()["datasets"][0]["filters"] == {"country": ["ua", "pl"]}
    assert manifest.to_dict()["datasets"][0]["page_size"] == 250


def test_fabric_connectors_ingestion_group_reexports_canonical_entrypoints() -> None:
    from polisyos.fabric.connectors.ingestion import ConnectorManifestSpec, run
    from polisyos.fabric.ingestion.ingestion import ConnectorManifestSpec as CanonicalSpec

    assert ConnectorManifestSpec is CanonicalSpec
    assert callable(run)


def test_fabric_trust_group_preserves_bounds_and_envelope_semantics() -> None:
    from polisyos.fabric.trust.adapter import envelope_from_trust_bounds
    from polisyos.fabric.trust.trust import two_pass_compare

    bounds = two_pass_compare(10, 4, method="fixture")
    envelope = envelope_from_trust_bounds(bounds, trust_policy_id="trust.policy")

    assert bounds.lower == Decimal("4")
    assert bounds.upper == Decimal("10")
    assert bounds.value == Decimal("7")
    assert envelope.metadata["trust_policy_id"] == "trust.policy"
    assert envelope.confidence_interval == (4.0, 10.0)


def test_fabric_quality_group_preserves_report_and_processing_contract_behavior() -> None:
    from polisyos.fabric.quality.fitness_report import DataFitnessReport, MetricFitness
    from polisyos.fabric.quality.processing_guarantees import (
        ProcessingGuarantee,
        batch_processing_contract,
        classify_cdc_schema_change,
    )
    from polisyos.fabric.quality.quality import QualityIndicators

    report = DataFitnessReport(run_id="run-1")
    report.add_metric(
        MetricFitness.from_indicators(
            QualityIndicators(
                metric_id="metric.gdp",
                missingness=0,
                staleness_days=0,
                coverage=1,
                row_count=100,
            )
        )
    )

    assert report.generate_summary().endswith("Verdict: PASSED")
    assert batch_processing_contract().guarantee_value == ProcessingGuarantee.BATCH_ATOMIC.value
    assert classify_cdc_schema_change(("a",), ("a", "b")).value == "compatible_additive"


def test_fabric_evidence_group_builds_bundle_and_decision_data_contracts() -> None:
    from polisyos.fabric.evidence.decision_data import SourceContractRef, UnitRef
    from polisyos.fabric.evidence.evidence import build_evidence_bundle
    from polisyos.fabric.evidence.fact_writer import build_fact
    from polisyos.ir.loading.fact_log import FactProvenance

    bundle = build_evidence_bundle(notes=["phase-5.3"])
    fact = build_fact(
        subject_id="metric.gdp",
        predicate_id="observed",
        object_value=10,
        provenance=FactProvenance(
            source_id="source.worldbank",
            license="cc-by",
            raw_hash=ARTIFACT_ID,
        ),
    )
    source = SourceContractRef(id="source.worldbank", version="1.0")
    unit = UnitRef(code="usd")

    assert bundle.notes == ["phase-5.3"]
    assert fact.subject_id == "metric.gdp"
    assert source.id == "source.worldbank"
    assert unit.code == "usd"


def test_fabric_identity_group_validates_dataset_and_segment_manifest_helpers() -> None:
    from polisyos.fabric.identity.manifest import (
        CoverageMetrics,
        DatasetManifest,
        QualityMetrics,
    )
    from polisyos.fabric.identity.segment_manifest import write_segment_manifest

    manifest = DatasetManifest(
        dataset_name="gdp",
        source="worldbank",
        license="cc-by",
        raw_hash=ARTIFACT_ID,
        schema_version="1.0",
        row_count=1,
        pii_flags={},
        quality=QualityMetrics(
            missing_rate=0,
            duplicate_rate=0,
            outlier_rate=0,
            coverage=CoverageMetrics(region_coverage="ua"),
        ),
    )

    assert manifest.created_at.endswith("+00:00")
    assert callable(write_segment_manifest)


def test_fabric_numerics_group_rejects_non_finite_values() -> None:
    from polisyos.fabric.numerics.finite import ensure_finite_float, ensure_probability

    assert ensure_probability(1.5, what="probability", clamp=True) == 1.0
    with pytest.raises(ValueError, match="must be finite"):
        ensure_finite_float(float("nan"), what="quality score")


def test_fabric_data_plane_group_preserves_tabular_and_temporal_semantics() -> None:
    from polisyos.fabric.data_plane.tabular import require_dataframe
    from polisyos.fabric.data_plane.temporal import parse_datetime_utc

    frame = require_dataframe([{"metric": "gdp", "value": 1}])
    timestamp = parse_datetime_utc("2026-05-07T10:30:00Z")

    assert isinstance(frame, pd.DataFrame)
    assert frame.loc[0, "metric"] == "gdp"
    assert timestamp.tzinfo is UTC


def test_fabric_config_group_normalizes_path_values() -> None:
    from polisyos.fabric.config.config import FabricConfig

    config = FabricConfig(curated_dir="curated", staging_dir="staging", raw_dir="raw")

    assert config.curated_dir == Path("curated")
    assert config.staging_dir == Path("staging")
    assert config.raw_dir == Path("raw")


@pytest.mark.parametrize(
    ("source_fqn", "target_fqn", "export_name"),
    [
        ("polisyos.fabric._connector_bridge", "polisyos.fabric", "fabric_get_data"),
        (
            "polisyos.fabric._numeric_parsing",
            "polisyos.fabric._internal.numeric_parsing",
            "normalize_decimal_text",
        ),
        (
            "polisyos.fabric.compatibility",
            "polisyos.fabric._internal.compatibility",
            "validate_fabric_compatibility_bridges",
        ),
        (
            "polisyos.fabric.connectors_ingestion",
            "polisyos.fabric.connectors.ingestion.connectors_ingestion",
            "run_connectors_ingestion",
        ),
        (
            "polisyos.fabric.decision_data",
            "polisyos.fabric.evidence.decision_data",
            "FabricDecisionData",
        ),
        ("polisyos.fabric.fact_writer", "polisyos.fabric.evidence.fact_writer", "build_fact"),
        ("polisyos.fabric.finite", "polisyos.fabric.numerics.finite", "ensure_finite_float"),
        (
            "polisyos.fabric.fitness_report",
            "polisyos.fabric.quality.fitness_report",
            "DataFitnessReport",
        ),
        (
            "polisyos.fabric.ingestion_providers",
            "polisyos.fabric.ingestion.ingestion_providers",
            "IngestionDependencies",
        ),
        ("polisyos.fabric.manifest", "polisyos.fabric.identity.manifest", "DatasetManifest"),
        (
            "polisyos.fabric.observability",
            "polisyos.fabric._adapters.observability",
            "get_fabric_observability_adapter",
        ),
        (
            "polisyos.fabric.processing_guarantees",
            "polisyos.fabric.quality.processing_guarantees",
            "ProcessingGuarantee",
        ),
        ("polisyos.fabric.registry", "polisyos.fabric._internal.registry", "ManifestRegistry"),
        ("polisyos.fabric.safety", "polisyos.fabric.quality.safety", "validate_sql_identifier"),
        (
            "polisyos.fabric.segment_manifest",
            "polisyos.fabric.identity.segment_manifest",
            "write_segment_manifest",
        ),
        ("polisyos.fabric.tabular", "polisyos.fabric.data_plane.tabular", "payload_to_dataframe"),
        ("polisyos.fabric.temporal", "polisyos.fabric.data_plane.temporal", "parse_datetime_utc"),
        (
            "polisyos.fabric.trust_adapter",
            "polisyos.fabric.trust.adapter",
            "envelope_from_trust_bounds",
        ),
        ("polisyos.fabric.world_query", "polisyos.fabric.world.query", "WorldQueryRequest"),
    ],
)
def test_fabric_old_alias_paths_warn_and_reexport_canonical_symbols(
    source_fqn: str,
    target_fqn: str,
    export_name: str,
) -> None:
    _drop_module(source_fqn)
    importlib.import_module("polisyos.fabric")

    with pytest.warns(DeprecationWarning, match=source_fqn):
        legacy_module = importlib.import_module(source_fqn)
        legacy_export = getattr(legacy_module, export_name)

    target_module = importlib.import_module(target_fqn)
    assert legacy_export is getattr(target_module, export_name)


def _drop_module(module_name: str) -> None:
    for loaded_name in list(sys.modules):
        if loaded_name == module_name or loaded_name.startswith(f"{module_name}."):
            sys.modules.pop(loaded_name, None)
