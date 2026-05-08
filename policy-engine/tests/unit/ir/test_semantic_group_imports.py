from __future__ import annotations

import importlib
import sys

import pytest


ARTIFACT_ID = "sha256:" + "b" * 64


@pytest.mark.parametrize(
    ("module_name", "export_name"),
    [
        ("polisyos.ir.registry.refs", "ArtifactRefModel"),
        ("polisyos.ir.registry.registry_fragments", "RegistryBundle"),
        ("polisyos.ir.registry.public_surface", "IR_NAMING_CONVENTIONS"),
        ("polisyos.ir.model_layer.model_spec", "ModelSpec"),
        ("polisyos.ir.model_layer.canon", "to_canonical_bytes"),
        ("polisyos.ir.model_layer.predicate", "PredicateRegistry"),
        ("polisyos.ir.model_layer.queries", "DataViewRequest"),
        ("polisyos.ir.model_layer.types", "EntityType"),
        ("polisyos.ir.model_layer.units", "UNIT_REGISTRY"),
        ("polisyos.ir.loading.loaders", "load_policy"),
        ("polisyos.ir.loading.citations", "CitationRef"),
        ("polisyos.ir.loading.migration_report", "MigrationReport"),
        ("polisyos.ir.loading.schema_catalog", "get_ir_type"),
        ("polisyos.ir.loading.fact_log", "build_fact_id"),
        ("polisyos.ir.loading.norm_pack", "NormPack"),
        ("polisyos.ir.loading.portfolio", "InteractionMatrix"),
        ("polisyos.ir.analytics", "BacktestReport"),
        ("polisyos.ir.schemas", "get_ir_type"),
    ],
)
def test_ir_wave3_semantic_group_modules_import(module_name: str, export_name: str) -> None:
    module = importlib.import_module(module_name)

    assert hasattr(module, export_name)


def test_ir_registry_group_preserves_refs_fragments_and_public_surface() -> None:
    from polisyos.ir.registry.public_surface import IR_NAMING_CONVENTIONS
    from polisyos.ir.registry.refs import ArtifactRefModel
    from polisyos.ir.registry.registry_fragments import RegistryFragmentMeta

    ref = ArtifactRefModel(
        artifact_id=ARTIFACT_ID,
        kind="ir.fixture",
        media_type="application/json",
    )
    fragment = RegistryFragmentMeta(fragment_id="fixture.registry", namespace="fixture")

    assert dict(ref) == {
        "artifact_id": ARTIFACT_ID,
        "kind": "ir.fixture",
        "media_type": "application/json",
    }
    assert fragment.schema_version == "1.0"
    assert IR_NAMING_CONVENTIONS["RegistryItemId"].startswith("Conceptual label")


def test_ir_model_layer_group_preserves_canonical_query_and_unit_semantics() -> None:
    from polisyos.ir.model_layer.canon import from_canonical_bytes, to_canonical_bytes
    from polisyos.ir.model_layer.queries import DataFilter, DataViewRequest
    from polisyos.ir.model_layer.types import EntityType, TranslatableString
    from polisyos.ir.model_layer.units import UNIT_REGISTRY

    payload = {"b": 2, "a": 1}
    request = DataViewRequest(
        request_id="view.gdp",
        view_type="metric_panel",
        metrics=["gdp"],
        filters=[DataFilter(column="country", op="==", value="ua")],
    )
    label = TranslatableString(en="GDP", ua="ВВП")

    assert from_canonical_bytes(to_canonical_bytes(payload)) == payload
    assert request.filters[0].value == "ua"
    assert EntityType.AGENT.value == "agent"
    assert label.ua == "ВВП"
    assert "usd" in UNIT_REGISTRY


def test_ir_loading_group_preserves_fact_citation_norm_and_migration_behavior() -> None:
    from polisyos.ir.loading.citations import CitationRef, DocumentRef
    from polisyos.ir.loading.fact_log import build_fact_id, canonical_tx_time
    from polisyos.ir.loading.migration_report import MigrationAction, MigrationReport
    from polisyos.ir.loading.norm_pack import NormPack, NormRef, parse_expr_syntax
    from polisyos.ir.loading.portfolio import InteractionMatrix, PolicyInteraction

    citation = CitationRef(
        doc=DocumentRef(doc_id="doc.fixture"),
        fragment_id="fragment.fixture",
    )
    report = MigrationReport(
        migration_id="migration.fixture",
        source_format="legacy",
        source_schema_version="0.1",
        target_format="trinity",
        target_schema_version="1.0",
        source_ref=ARTIFACT_ID,
        actions=[MigrationAction(kind="copy", from_path="a", to_path="b")],
    )
    norm_pack = NormPack(
        pack_id="norm.fixture",
        jurisdiction="ua",
        norms=[],
        metadata={"source": NormRef(provision_id="provision.fixture", citations=[citation])},
    )
    matrix = InteractionMatrix(
        interactions=[
            PolicyInteraction(
                policy_a_id="policy_a",
                policy_b_id="policy_b",
                coefficient=1.25,
            )
        ]
    )

    assert citation.doc.doc_id == "doc.fixture"
    assert build_fact_id({"subject": "metric.gdp"}).startswith("sha256:")
    assert canonical_tx_time("2026-05-07T00:00:00+00:00").endswith("Z")
    assert report.actions[0].to_path == "b"
    assert norm_pack.metadata["source"].provision_id == "provision.fixture"
    assert parse_expr_syntax("x + 1") == (True, None)
    assert matrix.pairwise_delta(
        policy_a_id="policy_a",
        policy_b_id="policy_b",
        base_a=10,
        base_b=14,
    ) == 3.0


def test_ir_analytics_group_preserves_backtest_count_normalization() -> None:
    from polisyos.ir.analytics import BacktestReport, BacktestScenario

    report = BacktestReport(
        report_id="backtest.fixture",
        scenarios=[
            BacktestScenario(
                scenario_id="baseline",
                scenario_label="Baseline",
                rmse=1.5,
            )
        ],
    )

    assert report.n_scenarios == 1


def test_ir_schemas_group_preserves_catalog_anchor_semantics() -> None:
    from polisyos.ir.schemas import catalog_anchor

    assert catalog_anchor("polisyos.ir.loading.FactLog") == "polisyos-ir-loading-factlog"


@pytest.mark.parametrize(
    ("source_fqn", "target_fqn", "export_name"),
    [
        ("polisyos.ir._lazy_facade", "polisyos.ir.api", "resolve_lazy_export"),
        ("polisyos.ir.canon", "polisyos.ir.model_layer.canon", "content_hash"),
        ("polisyos.ir.citations", "polisyos.ir.loading.citations", "CitationRef"),
        ("polisyos.ir.fact_log", "polisyos.ir.loading.fact_log", "build_fact_id"),
        ("polisyos.ir.loaders", "polisyos.ir.loading.loaders", "load_policy"),
        (
            "polisyos.ir.migration_report",
            "polisyos.ir.loading.migration_report",
            "MigrationReport",
        ),
        ("polisyos.ir.model_spec", "polisyos.ir.model_layer.model_spec", "ModelSpec"),
        ("polisyos.ir.norm_pack", "polisyos.ir.loading.norm_pack", "NormPack"),
        ("polisyos.ir.portfolio", "polisyos.ir.loading.portfolio", "InteractionMatrix"),
        ("polisyos.ir.predicate", "polisyos.ir.model_layer.predicate", "PredicateRegistry"),
        ("polisyos.ir.public_surface", "polisyos.ir.registry.public_surface", "RegistryItemId"),
        ("polisyos.ir.queries", "polisyos.ir.model_layer.queries", "DataViewRequest"),
        ("polisyos.ir.references", "polisyos.ir.loading.citations", "CitationRef"),
        ("polisyos.ir.refs", "polisyos.ir.registry.refs", "ArtifactRefModel"),
        (
            "polisyos.ir.registry_fragments",
            "polisyos.ir.registry.registry_fragments",
            "RegistryBundle",
        ),
        ("polisyos.ir.schema_catalog", "polisyos.ir.loading.schema_catalog", "get_ir_type"),
        ("polisyos.ir.types", "polisyos.ir.model_layer.types", "EntityType"),
        ("polisyos.ir.units", "polisyos.ir.model_layer.units", "UNIT_REGISTRY"),
    ],
)
def test_ir_old_alias_paths_warn_and_reexport_canonical_symbols(
    source_fqn: str,
    target_fqn: str,
    export_name: str,
) -> None:
    _drop_module(source_fqn)
    importlib.import_module("polisyos.ir")

    with pytest.warns(DeprecationWarning, match=source_fqn):
        legacy_module = importlib.import_module(source_fqn)

    target_module = importlib.import_module(target_fqn)
    assert getattr(legacy_module, export_name) is getattr(target_module, export_name)


def _drop_module(module_name: str) -> None:
    for loaded_name in list(sys.modules):
        if loaded_name == module_name or loaded_name.startswith(f"{module_name}."):
            sys.modules.pop(loaded_name, None)
