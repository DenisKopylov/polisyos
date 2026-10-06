from __future__ import annotations

import asyncio
import hashlib
import importlib
import json
import os
import shutil
import sys
import zipfile
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import duckdb
import pandas as pd

ROOT = Path(sys.argv[1]).resolve()
METRICS_MAP = Path(sys.argv[2]).resolve()
WHEEL = Path(sys.argv[3]).resolve()
SOURCE = Path(sys.argv[4]).resolve()
ROOT.mkdir(parents=True, exist_ok=True)

def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def file_sha(path: Path) -> str:
    return sha(path.read_bytes())

def read_json(path: Path) -> object:
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))

def scalar(value: object) -> object:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(k): scalar(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [scalar(v) for v in value]
    return value

def result_of(call):
    try:
        value = call()
        return {"status": "returned", "value": value}
    except Exception as exc:
        return {
            "status": "raised",
            "type": type(exc).__name__,
            "message": str(exc),
        }

def fresh_layout(name: str):
    from polisyos.data_forge.domains.catalog.batch.config import DatasetBatchConfig
    from polisyos.data_forge.domains.catalog.batch.graph_builder import build_graph
    from polisyos.data_forge.domains.catalog.knowledge.types import DatasetRecord, DistributionRecord

    run_root = ROOT / name
    run_root.mkdir(parents=True, exist_ok=True)
    registry = run_root / "source-registry.yaml"
    registry.write_text(
        "\n".join(
            [
                "version: 1",
                "sources:",
                "  - name: worldbank",
                "    family: worldbank",
                "    wave: A",
                "    endpoint: https://example.test/worldbank",
                "    connector_id: worldbank.wdi",
                "    profile_id: worldbank_wdi",
                "    enabled: true",
                "    execution_tier: transport_ready",
                "    run_lane: empirical",
                "    publish_blocking: true",
            ]
        ) + "\n",
        encoding="utf-8",
    )
    config = DatasetBatchConfig(
        snapshot_root=run_root / "snapshot",
        registry_path=registry,
        metrics_map_path=METRICS_MAP,
        stages=frozenset({"core_sources_ingest", "benchmark"}),
        run_profile="preflight_core",
        promoted_sources=("worldbank",),
        preflight_sources=("worldbank",),
        active_countries=("UA",),
        active_year_window=(2020, 2020),
        observation_mode="core",
        max_datasets_per_source=1,
    )
    record = DatasetRecord(
        id="wb-gdp",
        title="GDP per capita",
        description="GDP per capita",
        source="worldbank",
        source_portal="worldbank",
        dataset_id="NY.GDP.PCAP.PP.CD",
        source_dataset_id="NY.GDP.PCAP.PP.CD",
        execution_tier="transport_ready",
        update_frequency="annual",
        polisyos_metrics=["gdp_per_capita"],
        variables=["NY.GDP.PCAP.PP.CD"],
        preferred_distribution_id="dist-wb",
        distributions=[
            DistributionRecord(
                id="dist-wb",
                connector_type="worldbank.wdi",
                profile_id="worldbank_wdi",
                source_locator="NY.GDP.PCAP.PP.CD",
                parser_supported=True,
                machine_readable=True,
            )
        ],
    )
    build_graph(records=[record], db_path=config.db_path)
    return config, record

from polisyos.fabric.connectors.base import DatasetCapabilitySnapshot
from polisyos.fabric.connectors.sources.world_bank import WorldBankConnector
from polisyos.data_forge.domains.catalog.batch import harvester

fetch_state = {"fail": False, "calls": 0}
harvest_state = {"calls": 0}

async def harvest_worldbank(_endpoint, _limit, _timeout):
    harvest_state["calls"] += 1
    return [{"id": "NY.GDP.PCAP.PP.CD", "name": "GDP per capita, PPP", "sourceNote": "Gross domestic product per capita PPP"}]

harvester._harvest_worldbank = harvest_worldbank

async def describe_dataset(_connector, _handle, dataset_id):
    return DatasetCapabilitySnapshot(
        source="worldbank",
        dataset_id=dataset_id,
        resolved_dataset_id=dataset_id,
        last_checked_at=datetime.now(UTC),
    )

async def fetch_dataset(_connector, _handle, _request):
    fetch_state["calls"] += 1
    if fetch_state["fail"]:
        raise RuntimeError("fixture World Bank fetch failure")
    return type(
        "WorldBankFixtureResult",
        (),
        {"data": pd.DataFrame([{"country_code": "UA", "year": 2020, "value": 1.1}])},
    )()

WorldBankConnector.describe_dataset = describe_dataset
WorldBankConnector.fetch = fetch_dataset

modules_to_verify = [
    "polisyos.data_forge.domains.catalog.batch.pipeline",
    "polisyos.data_forge.domains.catalog.batch.config",
    "polisyos.data_forge.domains.catalog.batch.core_sources.api",
    "polisyos.data_forge.domains.catalog.batch.core_sources.validators",
    "polisyos.data_forge.domains.catalog.batch.core_sources.writers",
    "polisyos.data_forge.domains.catalog.batch.core_sources_ingest",
    "polisyos.data_forge.domains.catalog.batch.benchmark",
    "polisyos.data_forge.domains.catalog.batch.qc",
    "polisyos.data_forge.domains.catalog.batch.publish",
    "polisyos.data_forge.domains.catalog.knowledge.search",
    "polisyos.fabric.retrieval.service",
]
loaded = {name: importlib.import_module(name) for name in modules_to_verify}
site_packages = Path(importlib.import_module("sysconfig").get_paths()["purelib"]).resolve()
package_root = (site_packages / "polisyos").resolve()
module_proofs = {}
with zipfile.ZipFile(WHEEL) as archive:
    for name, module in loaded.items():
        origin = Path(module.__file__).resolve()
        if not origin.is_relative_to(package_root):
            raise AssertionError(f"{name} imported outside installed package: {origin}")
        relative = origin.relative_to(package_root).as_posix()
        member = "polisyos/" + relative
        installed_bytes = origin.read_bytes()
        wheel_bytes = archive.read(member)
        source_bytes = (SOURCE / "polisyos" / relative).read_bytes()
        module_proofs[name] = {
            "origin": str(origin),
            "wheel_member": member,
            "installed_sha256": sha(installed_bytes),
            "wheel_sha256": sha(wheel_bytes),
            "source_sha256": sha(source_bytes),
            "installed_equals_wheel_equals_frozen_source": (
                installed_bytes == wheel_bytes == source_bytes
            ),
        }
        if not module_proofs[name]["installed_equals_wheel_equals_frozen_source"]:
            raise AssertionError(f"installed bytes differ from wheel/source for {name}")
if any(str(ROOT.parent) in item for item in sys.path):
    raise AssertionError("scratch/source directory unexpectedly present in sys.path")
if any("/policy-engine/src" in item for item in sys.path):
    raise AssertionError("checkout source path unexpectedly present in sys.path")

from polisyos.data_forge.domains.catalog.batch.core_sources.validators import (
    _current_core_output_receipt_state,
)
from polisyos.data_forge.domains.catalog.batch.pipeline import (
    current_content_stage_receipt,
    run_dataset_pipeline_sync,
)
from polisyos.data_forge.domains.catalog.batch.benchmark import run_benchmark
from polisyos.data_forge.domains.catalog.batch import harvester
from polisyos.data_forge.domains.catalog.batch.config import DatasetBatchConfig
from polisyos.core.contracts.control import DataNeed, DataResolveRequest
from polisyos.data_forge.domains.catalog.knowledge.search import DatasetCatalogGraph
from polisyos.fabric.retrieval.service import RetrievalService

# Positive main pipeline: real producer, DuckDB ledger, receipt, benchmark, QC, publish.
main_config, _main_record = fresh_layout("main")
main_config.fail_fast_qc = False
main_config.stages = frozenset(
    {"harvest", "core_sources_ingest", "benchmark", "qc", "publish"}
)
main_outcome = result_of(lambda: run_dataset_pipeline_sync(main_config))
main_state = read_json(main_config.stage_state_path)
main_core_state = (
    main_state.get("core_sources_ingest")
    if isinstance(main_state, dict)
    else None
)
main_manifest = read_json(main_config.manifests_dir / "core_sources_ingest.json")
main_checkpoint = read_json(main_config.observation_ingest_checkpoint_path)
main_receipt_state = _current_core_output_receipt_state(main_config)
main_rows = []
main_db_error = None
try:
    with duckdb.connect(str(main_config.db_path), read_only=True) as con:
        main_rows = con.execute(
            "SELECT dataset_id, raw_variable, country_code, year, value "
            "FROM ds_observations WHERE dataset_id = 'wb-gdp' ORDER BY country_code, year"
        ).fetchall()
except Exception as exc:
    main_db_error = f"{type(exc).__name__}: {exc}"

main_benchmark = read_json(main_config.benchmark_report_path)
main_qc = read_json(main_config.qc_report_path)
main_publish = read_json(main_config.publish_manifest_path)
main_readiness = read_json(main_config.consumer_readiness_path)
main_content_receipts = {
    stage: current_content_stage_receipt(main_config, stage)
    for stage in ("benchmark", "qc", "publish")
}

# Actual downstream RetrievalService consumes the produced catalog row. No execute/fetch call.
os.environ["POLISYOS_RETRIEVAL_FASTLANE_ENABLED"] = "0"
os.environ["POLISYOS_RETRIEVAL_EXPLORELANE_ENABLED"] = "0"
def _resolve_from_produced_catalog(config):
    catalog = DatasetCatalogGraph(db_path=config.db_path, index_dir=config.index_dir)
    service = RetrievalService(curated_dir=ROOT / "curated", dataset_catalog=catalog)
    request = DataResolveRequest(
        data_needs=[
            DataNeed(
                metric="gdp_per_capita",
                geography="UA",
                time_start="2020",
                time_end="2020",
                quality_min=0.0,
            )
        ],
        mode="fastlane",
        allow_explore_fallback=False,
    )
    try:
        outcome = service.resolve(request)
        return {
            "lane_used": outcome.telemetry.get("lane_used"),
            "plans": [plan.model_dump(mode="json") for plan in outcome.fetch_plans],
            "candidate_count": len(outcome.candidates),
            "warnings": list(outcome.warnings),
        }
    finally:
        catalog.close()

retrieval_outcome = result_of(
    lambda: _resolve_from_produced_catalog(main_config)
)

# Independent stale-state/retry ledger from a genuine, successful producer output.
retry_config, _retry_record = fresh_layout("retry")
if isinstance(main_core_state, dict):
    retry_config.stage_state_path.parent.mkdir(parents=True, exist_ok=True)
    retry_config.stage_state_path.write_text(
        json.dumps({"core_sources_ingest": main_core_state}, sort_keys=True),
        encoding="utf-8",
    )
retry_config.resume = True
retry_config.resume_mode = "force"
fetch_state["fail"] = True
failed_run = result_of(lambda: run_dataset_pipeline_sync(retry_config))
failed_manifest = read_json(retry_config.manifests_dir / "core_sources_ingest.json")
failed_state_doc = read_json(retry_config.stage_state_path)
failed_core_state = (
    failed_state_doc.get("core_sources_ingest")
    if isinstance(failed_state_doc, dict)
    else None
)
failed_checkpoint = read_json(retry_config.observation_ingest_checkpoint_path)
failed_deferred = read_json(retry_config.manifests_dir / "deferred_observation_plans.json")
failed_benchmark = read_json(retry_config.benchmark_report_path)
failed_rows = []
try:
    with duckdb.connect(str(retry_config.db_path), read_only=True) as con:
        failed_rows = con.execute(
            "SELECT dataset_id, country_code, year, value FROM ds_observations "
            "WHERE dataset_id = 'wb-gdp'"
        ).fetchall()
except Exception:
    pass
failed_fetch_calls = fetch_state["calls"]

# Retry must persist the exact selected output and turn the current receipt green.
fetch_state["fail"] = False
retried_run = result_of(lambda: run_dataset_pipeline_sync(retry_config))
retried_manifest = read_json(retry_config.manifests_dir / "core_sources_ingest.json")
retried_state_doc = read_json(retry_config.stage_state_path)
retried_core_state = (
    retried_state_doc.get("core_sources_ingest")
    if isinstance(retried_state_doc, dict)
    else None
)
retried_checkpoint = read_json(retry_config.observation_ingest_checkpoint_path)
retried_shards = read_json(retry_config.manifests_dir / "completed_observation_shards.json")
retried_benchmark = read_json(retry_config.benchmark_report_path)
retried_receipt_state = _current_core_output_receipt_state(retry_config)
retried_rows = []
try:
    with duckdb.connect(str(retry_config.db_path), read_only=True) as con:
        retried_rows = con.execute(
            "SELECT dataset_id, raw_variable, country_code, year, value "
            "FROM ds_observations WHERE dataset_id = 'wb-gdp'"
        ).fetchall()
except Exception:
    pass
calls_before_valid_resume = fetch_state["calls"]
valid_resume = result_of(lambda: run_dataset_pipeline_sync(retry_config))
valid_resume_benchmark = read_json(retry_config.benchmark_report_path)
calls_after_valid_resume = fetch_state["calls"]

# Real completed->deferred checkpoint falsifier against otherwise-green artifact receipts.
from polisyos.data_forge.domains.catalog.batch.checkpoints import write_json
checkpoint_complete = read_json(retry_config.observation_ingest_checkpoint_path)
checkpoint_only_result = {}
if isinstance(checkpoint_complete, dict) and checkpoint_complete.get("completed"):
    shard_id = next(iter(checkpoint_complete["completed"]))
    stale_checkpoint = json.loads(json.dumps(checkpoint_complete))
    stale_shard = stale_checkpoint["completed"].pop(shard_id)
    stale_checkpoint["deferred"][shard_id] = {**stale_shard, "status": "deferred"}
    stage_state_before = retry_config.stage_state_path.read_bytes()
    benchmark_before = retry_config.benchmark_report_path.read_bytes()
    calls_before = fetch_state["calls"]
    retry_config.observation_ingest_checkpoint_path.write_text(
        json.dumps(stale_checkpoint, sort_keys=True),
        encoding="utf-8",
    )
    checkpoint_write_kept_stage_state = (
        retry_config.stage_state_path.read_bytes() == stage_state_before
    )
    checkpoint_write_kept_benchmark_output = (
        retry_config.benchmark_report_path.read_bytes() == benchmark_before
    )
    run_benchmark(retry_config)
    direct_stale_benchmark = read_json(retry_config.benchmark_report_path)
    benchmark_only = replace(
        retry_config,
        stages=frozenset({"benchmark"}),
        resume=True,
        resume_mode="smart",
    )
    replay_stats = run_dataset_pipeline_sync(benchmark_only)
    replay_benchmark = read_json(retry_config.benchmark_report_path)
    partial_receipt = current_content_stage_receipt(benchmark_only, "benchmark")
    basis_receipt = None
    if isinstance(partial_receipt, dict):
        basis_receipt = (
            partial_receipt.get("input_basis", {})
            .get("config", {})
            .get("core_output_receipt_state")
        )
    repeated_stats = run_dataset_pipeline_sync(benchmark_only)
    repeated_benchmark = read_json(retry_config.benchmark_report_path)
    checkpoint_only_result = {
        "deferred_shard": shard_id,
        "checkpoint_only_write_kept_stage_state": checkpoint_write_kept_stage_state,
        "checkpoint_only_write_kept_benchmark_output": checkpoint_write_kept_benchmark_output,
        "direct_report_mode": (
            direct_stale_benchmark.get("evaluation_mode")
            if isinstance(direct_stale_benchmark, dict)
            else None
        ),
        "orchestrator_skipped_stages": list(replay_stats.skipped_stages),
        "orchestrator_partial_eval": replay_stats.metrics.get("benchmark_partial_eval"),
        "orchestrator_report_mode": (
            replay_benchmark.get("evaluation_mode")
            if isinstance(replay_benchmark, dict)
            else None
        ),
        "fetch_calls_unchanged": fetch_state["calls"] == calls_before,
        "receipt_core_output_basis": basis_receipt,
        "second_orchestrator_skipped_stages": list(repeated_stats.skipped_stages),
        "second_orchestrator_partial_eval": repeated_stats.metrics.get("benchmark_partial_eval"),
        "second_orchestrator_report_mode": (
            repeated_benchmark.get("evaluation_mode")
            if isinstance(repeated_benchmark, dict)
            else None
        ),
    }
    retry_config.observation_ingest_checkpoint_path.write_text(
        json.dumps(checkpoint_complete, sort_keys=True),
        encoding="utf-8",
    )

# Remove persisted observation rows while retaining the completed stage/checkpoint receipt.
with duckdb.connect(str(retry_config.db_path)) as con:
    con.execute("DELETE FROM ds_observations WHERE dataset_id = 'wb-gdp'")
    con.execute("CHECKPOINT")
removed_run = result_of(lambda: run_benchmark(retry_config))
removed_benchmark = read_json(retry_config.benchmark_report_path)
calls_before_missing_output = fetch_state["calls"]
fetch_state["fail"] = True
missing_output_retry = result_of(lambda: run_dataset_pipeline_sync(retry_config))
missing_output_manifest = read_json(retry_config.manifests_dir / "core_sources_ingest.json")
missing_output_state_doc = read_json(retry_config.stage_state_path)
missing_output_core = (
    missing_output_state_doc.get("core_sources_ingest")
    if isinstance(missing_output_state_doc, dict)
    else None
)
missing_output_benchmark = read_json(retry_config.benchmark_report_path)
missing_output_rows = []
with duckdb.connect(str(retry_config.db_path), read_only=True) as con:
    missing_output_rows = con.execute(
        "SELECT dataset_id, country_code, year, value FROM ds_observations "
        "WHERE dataset_id = 'wb-gdp'"
    ).fetchall()
missing_output_calls_delta = fetch_state["calls"] - calls_before_missing_output
fetch_state["fail"] = False
repaired_run = result_of(lambda: run_dataset_pipeline_sync(retry_config))
repaired_benchmark = read_json(retry_config.benchmark_report_path)
repaired_receipt_state = _current_core_output_receipt_state(retry_config)
repaired_rows = []
with duckdb.connect(str(retry_config.db_path), read_only=True) as con:
    repaired_rows = con.execute(
        "SELECT dataset_id, raw_variable, country_code, year, value "
        "FROM ds_observations WHERE dataset_id = 'wb-gdp'"
    ).fetchall()

# Real alignment-byte mutation invalidates receipt; retry recomputes current producer.
with duckdb.connect(str(retry_config.db_path)) as con:
    con.execute(
        "UPDATE ds_variable_alignments SET confidence = confidence + 0.01 "
        "WHERE dataset_id = 'wb-gdp'"
    )
    con.execute("CHECKPOINT")
alignment_benchmark_result = result_of(lambda: run_benchmark(retry_config))
alignment_benchmark = read_json(retry_config.benchmark_report_path)
calls_before_alignment_retry = fetch_state["calls"]
fetch_state["fail"] = True
alignment_retry = result_of(lambda: run_dataset_pipeline_sync(retry_config))
alignment_calls_delta = fetch_state["calls"] - calls_before_alignment_retry

# Changed producer plan bytes must also force a new run. Restore transport for valid output.
fetch_state["fail"] = False
with duckdb.connect(str(retry_config.db_path)) as con:
    con.execute("UPDATE ds_datasets SET title = 'Changed plan input' WHERE id = 'wb-gdp'")
    con.execute("CHECKPOINT")
calls_before_plan_retry = fetch_state["calls"]
changed_plan_run = result_of(lambda: run_dataset_pipeline_sync(retry_config))
changed_plan_calls_delta = fetch_state["calls"] - calls_before_plan_retry
changed_plan_benchmark = read_json(retry_config.benchmark_report_path)

# Recheck and preserve exact installed module provenance after probes.
module_proofs_after = {}
for name in modules_to_verify:
    module = sys.modules[name]
    origin = Path(module.__file__).resolve()
    module_proofs_after[name] = {
        "origin": str(origin),
        "installed_sha256": file_sha(origin),
    }

summary = {
    "candidate": {
        "wheel": str(WHEEL),
        "wheel_sha256": file_sha(WHEEL),
        "frozen_source_root": str(SOURCE),
        "metrics_map_sha256": file_sha(METRICS_MAP),
    },
    "runtime": {
        "cwd": os.getcwd(),
        "python": sys.executable,
        "version": sys.version.split()[0],
        "isolated_mode": bool(sys.flags.isolated),
        "safe_path": bool(sys.flags.safe_path),
        "PYTHONPATH": os.environ.get("PYTHONPATH"),
        "site_packages": str(site_packages),
        "sys_path": list(sys.path),
        "sys_path_outside_source": not any(
            "/policy-engine/src" in item for item in sys.path
        ),
    },
    "installed_module_bytes": module_proofs,
    "main_pipeline": {
        "outcome": scalar(main_outcome),
        "harvest_manifest": read_json(main_config.manifests_dir / "harvest.json"),
        "raw_worldbank_files": [str(path) for path in sorted((main_config.raw_dir / "worldbank").glob("**/*")) if path.is_file()],
        "harvest_stub_calls": harvest_state["calls"],
        "core_manifest": main_manifest,
        "core_stage_state": main_core_state,
        "observation_checkpoint": main_checkpoint,
        "current_core_receipt": main_receipt_state.basis_member(),
        "current_core_receipt_is_current": main_receipt_state.is_current,
        "duckdb_rows": main_rows,
        "duckdb_error": main_db_error,
        "benchmark": main_benchmark,
        "qc": main_qc,
        "consumer_readiness": main_readiness,
        "publish_manifest": main_publish,
        "content_receipts_current": {
            stage: receipt is not None
            for stage, receipt in main_content_receipts.items()
        },
        "retrieval_outcome": scalar(retrieval_outcome),
    },
    "stale_prior_success_then_failure": {
        "failure_run": scalar(failed_run),
        "manifest_status": (
            failed_manifest.get("status") if isinstance(failed_manifest, dict) else None
        ),
        "core_stage_status": (
            failed_core_state.get("status") if isinstance(failed_core_state, dict) else None
        ),
        "core_metadata": (
            failed_core_state.get("metadata") if isinstance(failed_core_state, dict) else None
        ),
        "deferred_plan": failed_deferred,
        "checkpoint": failed_checkpoint,
        "benchmark_mode": (
            failed_benchmark.get("evaluation_mode")
            if isinstance(failed_benchmark, dict)
            else None
        ),
        "db_rows": failed_rows,
        "transport_call_count_after_failure": failed_fetch_calls,
    },
    "success_retry_and_resume": {
        "retry_run": scalar(retried_run),
        "manifest_status": (
            retried_manifest.get("status") if isinstance(retried_manifest, dict) else None
        ),
        "core_stage_status": (
            retried_core_state.get("status") if isinstance(retried_core_state, dict) else None
        ),
        "core_metadata": (
            retried_core_state.get("metadata") if isinstance(retried_core_state, dict) else None
        ),
        "checkpoint": retried_checkpoint,
        "completed_shards": retried_shards,
        "receipt_basis": retried_receipt_state.basis_member(),
        "receipt_is_current": retried_receipt_state.is_current,
        "db_rows": retried_rows,
        "benchmark_mode": (
            retried_benchmark.get("evaluation_mode")
            if isinstance(retried_benchmark, dict)
            else None
        ),
        "valid_resume_run": scalar(valid_resume),
        "valid_resume_fetch_call_delta": calls_after_valid_resume - calls_before_valid_resume,
        "valid_resume_benchmark_mode": (
            valid_resume_benchmark.get("evaluation_mode")
            if isinstance(valid_resume_benchmark, dict)
            else None
        ),
    },
    "checkpoint_cache_falsifier": checkpoint_only_result,
    "deleted_output_refusal_and_recovery": {
        "direct_benchmark_outcome": scalar(removed_run),
        "direct_benchmark_mode": (
            removed_benchmark.get("evaluation_mode")
            if isinstance(removed_benchmark, dict)
            else None
        ),
        "failed_reingest_outcome": scalar(missing_output_retry),
        "failed_reingest_manifest_status": (
            missing_output_manifest.get("status")
            if isinstance(missing_output_manifest, dict)
            else None
        ),
        "failed_reingest_core_state": missing_output_core,
        "failed_reingest_benchmark_mode": (
            missing_output_benchmark.get("evaluation_mode")
            if isinstance(missing_output_benchmark, dict)
            else None
        ),
        "failed_reingest_db_rows": missing_output_rows,
        "failed_reingest_transport_call_delta": missing_output_calls_delta,
        "repair_run": scalar(repaired_run),
        "repair_receipt_basis": repaired_receipt_state.basis_member(),
        "repair_receipt_is_current": repaired_receipt_state.is_current,
        "repair_benchmark_mode": (
            repaired_benchmark.get("evaluation_mode")
            if isinstance(repaired_benchmark, dict)
            else None
        ),
        "repair_db_rows": repaired_rows,
    },
    "changed_inputs": {
        "alignment_direct_benchmark_outcome": scalar(alignment_benchmark_result),
        "alignment_direct_benchmark_mode": (
            alignment_benchmark.get("evaluation_mode")
            if isinstance(alignment_benchmark, dict)
            else None
        ),
        "alignment_retry_outcome": scalar(alignment_retry),
        "alignment_retry_transport_call_delta": alignment_calls_delta,
        "changed_plan_run": scalar(changed_plan_run),
        "changed_plan_transport_call_delta": changed_plan_calls_delta,
        "changed_plan_benchmark_mode": (
            changed_plan_benchmark.get("evaluation_mode")
            if isinstance(changed_plan_benchmark, dict)
            else None
        ),
    },
    "external_scope": {
        "only_worldbank_describe_and_fetch_stubbed": True,
        "example_test_endpoint_only": True,
        "no_remote_artifact_or_model_weights": True,
        "no_execute_plan_or_external_retrieval_fetch": True,
        "preflight_profile": "preflight_core",
        "selected_source": "worldbank",
        "sample_record_count": 1,
    },
    "note": (
        "The source's benchmark completion percentage is informational; this receipt audit "
        "uses current producer checkpoint + persisted table content and typed evaluation mode."
    ),
}
out_path = ROOT / "main-runtime-result.json"
out_path.write_text(json.dumps(summary, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
print(json.dumps(summary, sort_keys=True, default=str))
