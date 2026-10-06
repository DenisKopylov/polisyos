from __future__ import annotations

import asyncio
import hashlib
import json
import sys
import zipfile
from pathlib import Path

import duckdb

from polisyos.data_forge.domains.catalog.batch import pipeline
from polisyos.data_forge.domains.catalog.batch import _core_sources_ingest_contracts as contracts
from polisyos.data_forge.domains.catalog.batch.core_sources import api, loaders, transformers, writers
from polisyos.data_forge.domains.catalog.batch._core_sources_ingest_contracts import (
    CoreSourcesCompatibilityContext,
    CoreSourcesIngestStats,
    ObservationPlan,
    bind_core_sources_compatibility_context,
)
from polisyos.data_forge.domains.catalog.batch.config import DatasetBatchConfig
from polisyos.data_forge.domains.catalog.batch.core_sources import loaders, transformers, writers
from polisyos.data_forge.domains.catalog.batch.graph_builder import build_graph

ROOT = Path(sys.argv[1]).resolve()
METRICS_MAP = Path(sys.argv[2]).resolve()
WHEEL = Path(sys.argv[3]).resolve()
SOURCE = Path(sys.argv[4]).resolve()
ROOT.mkdir(parents=True, exist_ok=True)
FACADE = "polisyos.data_forge.domains.catalog.batch.core_sources_ingest"
if FACADE in sys.modules:
    raise AssertionError("legacy facade imported before canonical pipeline probe")

def module_byte_proofs():
    modules = {
        "batch.pipeline": pipeline,
        "batch._core_sources_ingest_contracts": contracts,
        "core_sources.api": api,
        "core_sources.loaders": loaders,
        "core_sources.transformers": transformers,
        "core_sources.writers": writers,
    }
    site_packages = Path(__import__("sysconfig").get_paths()["purelib"]).resolve()
    package_root = site_packages / "polisyos"
    proofs = {}
    with zipfile.ZipFile(WHEEL) as archive:
        for label, module in modules.items():
            origin = Path(module.__file__).resolve()
            if not origin.is_relative_to(package_root):
                raise AssertionError(f"{label} did not import from site-packages: {origin}")
            relative = origin.relative_to(package_root).as_posix()
            wheel_bytes = archive.read("polisyos/" + relative)
            source_bytes = (SOURCE / "polisyos" / relative).read_bytes()
            installed_bytes = origin.read_bytes()
            identical = installed_bytes == wheel_bytes == source_bytes
            proofs[label] = {
                "origin": str(origin),
                "member": "polisyos/" + relative,
                "installed_sha256": hashlib.sha256(installed_bytes).hexdigest(),
                "wheel_sha256": hashlib.sha256(wheel_bytes).hexdigest(),
                "source_sha256": hashlib.sha256(source_bytes).hexdigest(),
                "installed_wheel_source_identical": identical,
            }
            if not identical:
                raise AssertionError(f"installed module bytes do not match wheel/source: {label}")
    return proofs

module_proofs = module_byte_proofs()

original_legacy = writers._legacy_ingest_observations
original_normalizer = transformers._normalize_observation_row
seed_path = ROOT / "empty-seed.yaml"
seed_path.write_text("version: 1\nalignments: []\n", encoding="utf-8")
barrier = asyncio.Event()
waiting = 0


def build_request(label: str, country: str) -> tuple[DatasetBatchConfig, CoreSourcesCompatibilityContext]:
    request_root = ROOT / label
    registry_path = request_root / "source-registry.yaml"
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text("version: 1\nsources: []\n", encoding="utf-8")
    config = DatasetBatchConfig(
        snapshot_root=request_root / "snapshot",
        registry_path=registry_path,
        metrics_map_path=METRICS_MAP,
        stages=frozenset({"core_sources_ingest"}),
        run_profile="preflight_core",
        observation_mode="core",
        active_countries=("UA",),
        active_year_window=(2020, 2020),
        promoted_sources=(),
        preflight_sources=(),
    )
    build_graph(records=[], db_path=config.db_path)

    async def fake_transport(db_path: Path) -> CoreSourcesIngestStats:
        global waiting
        waiting += 1
        if waiting == 2:
            barrier.set()
        await barrier.wait()
        plan = ObservationPlan(
            dataset_id=f"dataset-{label}",
            source="fixture",
            raw_variable="fixture_value",
            canonical_var="gdp_per_capita",
            connector_id="fixture.connector",
            profile_id="fixture_profile",
            request_dataset_id="fixture.dataset",
            default_filters={},
            update_frequency="annual",
        )
        with duckdb.connect(str(db_path)) as con:
            insert_stats = writers._insert_generic_observations(
                con=con,
                plan=plan,
                rows=[{"country_code": "UA", "year": 2020, "value": 1.25}],
            )
        return CoreSourcesIngestStats(
            observations=insert_stats.written,
            observations_attempted=insert_stats.attempted,
            observations_inserted=insert_stats.inserted,
            observations_replaced=insert_stats.replaced,
        )

    def normalize(_row: dict[str, object]) -> tuple[str, int, None, None, float, str]:
        return country, 2020, None, None, 1.25, "{}"

    context = CoreSourcesCompatibilityContext(
        bindings={
            (writers.__name__, "_legacy_ingest_observations"): fake_transport,
            (transformers.__name__, "_normalize_observation_row"): normalize,
            (loaders.__name__, "_seed_alignments_path"): lambda: seed_path,
        }
    )
    return config, context


async def run_one(config: DatasetBatchConfig, context: CoreSourcesCompatibilityContext) -> dict[str, object]:
    with bind_core_sources_compatibility_context(context):
        stats = await pipeline.run_dataset_pipeline(config)
    with duckdb.connect(str(config.db_path), read_only=True) as con:
        rows = con.execute(
            "SELECT dataset_id, country_code, year, value FROM ds_observations ORDER BY dataset_id"
        ).fetchall()
    return {"metrics": stats.metrics, "rows": rows, "snapshot": str(config.snapshot_root)}


async def main() -> dict[str, object]:
    left_config, left_context = build_request("request-A", "UA")
    right_config, right_context = build_request("request-B", "PL")
    left, right = await asyncio.gather(
        run_one(left_config, left_context),
        run_one(right_config, right_context),
    )
    if left["rows"] != [("dataset-request-A", "UA", 2020, 1.25)]:
        raise AssertionError(f"request A output crossed or disappeared: {left['rows']!r}")
    if right["rows"] != [("dataset-request-B", "PL", 2020, 1.25)]:
        raise AssertionError(f"request B output crossed or disappeared: {right['rows']!r}")
    if FACADE in sys.modules:
        raise AssertionError("legacy facade imported during canonical pipeline probe")
    if writers._legacy_ingest_observations is not original_legacy:
        raise AssertionError("request A/B changed the writer's module global")
    if transformers._normalize_observation_row is not original_normalizer:
        raise AssertionError("request A/B changed the transformer's module global")
    return {
        "canonical_pipeline": pipeline.__name__,
        "installed_module_bytes": module_proofs,
        "legacy_facade_absent": FACADE not in sys.modules,
        "parallel_requests": {"A": left, "B": right},
        "leaf_globals_unchanged": True,
        "external_transport": "stubbed at request-scoped boundary",
        "observation_writer": "installed writers._insert_generic_observations",
        "producer_receipt_scope": "request-context isolation fixture; no publishability claim",
    }


print(json.dumps(asyncio.run(main()), sort_keys=True, default=str))
