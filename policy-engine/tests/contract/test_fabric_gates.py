from pathlib import Path

import pytest

from polisyos.fabric.manifest import CoverageMetrics, DatasetManifest, QualityMetrics
from polisyos.fabric.registry import ManifestRegistry
from polisyos.ir.data_views import AccessTier, DataViewRequest, DataViewType
from polisyos.fabric.udf.compiler import ViewCompiler
from polisyos.fabric.udf.config import (
    DEFAULT_ALLOWED_COLUMNS,
    DEFAULT_ALLOWED_RELATION_TYPES,
    DEFAULT_FIELD_CLASSIFICATION,
    UdfSchema,
)


def _write_manifest(curated_dir: Path, dataset_name: str) -> None:
    manifest = DatasetManifest(
        dataset_name=dataset_name,
        source="test",
        license="test",
        raw_hash="test",
        schema_version="1.0",
        row_count=1,
        pii_flags={},
        quality=QualityMetrics(
            missing_rate=0.0,
            duplicate_rate=0.0,
            outlier_rate=0.0,
            coverage=CoverageMetrics(),
        ),
    )
    path = curated_dir / f"{dataset_name}_manifest.json"
    path.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")


def _compiler(curated_dir: Path) -> ViewCompiler:
    registry = ManifestRegistry(curated_dir)
    schema = UdfSchema(
        allowed_columns=DEFAULT_ALLOWED_COLUMNS,
        allowed_relation_types=DEFAULT_ALLOWED_RELATION_TYPES,
        field_classification=DEFAULT_FIELD_CLASSIFICATION,
    )
    return ViewCompiler(registry, schema)


def test_manifest_required_for_panel(tmp_path: Path) -> None:
    compiler = _compiler(tmp_path)
    req = DataViewRequest(
        request_id="req",
        run_id="demo_run",
        view_type=DataViewType.PANEL,
        metrics=["gdp"],
        access_tier=AccessTier.PUBLIC,
    )
    with pytest.raises(ValueError):
        compiler.compile(req)


def test_pii_gate_blocks_public_access(tmp_path: Path) -> None:
    _write_manifest(tmp_path, "macro")
    compiler = _compiler(tmp_path)
    req = DataViewRequest(
        request_id="req",
        run_id="demo_run",
        view_type=DataViewType.PANEL,
        metrics=["run_id"],
        access_tier=AccessTier.PUBLIC,
    )
    with pytest.raises(ValueError):
        compiler.compile(req)


def test_entity_resolution_required_for_snapshot(tmp_path: Path) -> None:
    _write_manifest(tmp_path, "agents")
    compiler = _compiler(tmp_path)
    req = DataViewRequest(
        request_id="req",
        run_id="demo_run",
        view_type=DataViewType.SNAPSHOT,
        metrics=["income"],
        step_end=0,
        aggregation=None,
        access_tier=AccessTier.INTERNAL,
    )
    with pytest.raises(ValueError):
        compiler.compile(req)
