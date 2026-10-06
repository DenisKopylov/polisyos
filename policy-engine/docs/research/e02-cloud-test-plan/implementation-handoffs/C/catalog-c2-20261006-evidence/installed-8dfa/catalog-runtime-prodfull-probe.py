from __future__ import annotations

import hashlib
import importlib
import importlib.metadata
import io
import json
import os
import shutil
import sys
import urllib.error
import urllib.request
import zipfile
from dataclasses import asdict, is_dataclass
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path

import duckdb
import pandas as pd

ROOT = Path(sys.argv[1]).resolve()
SOURCE = Path(sys.argv[2]).resolve()
WHEEL = Path(sys.argv[3]).resolve()
HTTP_MODE = sys.argv[4]
ROOT.mkdir(parents=True, exist_ok=True)
baseline_sys_path = list(sys.path)

def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def sha_file(path: Path) -> str:
    return sha_bytes(path.read_bytes())

def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None

def result_of(call):
    try:
        value = call()
        return {"status": "returned", "value": value}
    except Exception as exc:
        return {"status": "raised", "type": type(exc).__name__, "message": str(exc)}

def jsonable(value):
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Enum):
        return jsonable(value.value)
    if is_dataclass(value):
        return jsonable(asdict(value))
    if isinstance(value, dict):
        return {str(k): jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(v) for v in value]
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return repr(value)

INDICATORS = [
    {
        "id": "NY.GDP.PCAP.PP.CD",
        "name": "GDP per capita, PPP",
        "sourceNote": "Gross domestic product per capita PPP",
        "metric": "gdp_per_capita",
    },
    {
        "id": "SL.UEM.TOTL.ZS",
        "name": "Unemployment, total (% of total labor force)",
        "sourceNote": "Unemployment and jobless labor force rate",
        "metric": "unemployment_rate",
    },
    {
        "id": "FP.CPI.TOTL.ZG",
        "name": "Inflation, consumer prices (annual %)",
        "sourceNote": "Consumer price index inflation CPI",
        "metric": "inflation",
    },
    {
        "id": "SM.POP.NETM",
        "name": "Net migration",
        "sourceNote": "Migration flows migrant population movement",
        "metric": "migration",
    },
    {
        "id": "SP.DYN.LE00.IN",
        "name": "Life expectancy at birth, total (years)",
        "sourceNote": "Health outcomes life expectancy mortality",
        "metric": "health_outcomes",
    },
    {
        "id": "SE.PRM.ENRR",
        "name": "School enrollment, primary (% gross)",
        "sourceNote": "Education outcomes enrollment school learning",
        "metric": "education_outcomes",
    },
    {
        "id": "SI.POV.DDAY",
        "name": "Poverty headcount ratio at $2.15 a day",
        "sourceNote": "Poverty rate income deprivation low income",
        "metric": "poverty_rate",
    },
    {
        "id": "SL.TLF.CACT.ZS",
        "name": "Labor force participation rate, total",
        "sourceNote": "Labor force labour force participation employment",
        "metric": "labor_force_participation",
    },
    {
        "id": "RL.EST",
        "name": "Rule of law estimate",
        "sourceNote": "Institutional quality rule of law government effectiveness corruption",
        "metric": "institutional_quality",
    },
]
EXPECTED_METRICS = {row["id"]: row["metric"] for row in INDICATORS}
run_root = ROOT / ("positive" if HTTP_MODE == "200" else "negative-http-503")
run_root.mkdir(parents=True, exist_ok=True)

from polisyos.data_forge.domains.catalog.batch.config import DatasetBatchConfig
from polisyos.data_forge.domains.catalog.batch import harvester
from polisyos.data_forge.domains.catalog.batch.benchmark import (
    DEFAULT_BENCHMARK_SUITE,
)
from polisyos.data_forge.domains.catalog.batch.core_sources.validators import (
    _current_core_output_receipt_state,
)
from polisyos.data_forge.domains.catalog.batch.core_sources.loaders import _seed_alignments_path
from polisyos.data_forge.domains.catalog.batch.pipeline import (
    current_content_stage_receipt,
    run_dataset_pipeline_sync,
)
from polisyos.data_forge.domains.catalog.batch.publish import run_publish
from polisyos.fabric.connectors.base import DatasetCapabilitySnapshot
from polisyos.fabric.connectors.sources.world_bank import WorldBankConnector
from polisyos.core.contracts.control import DataNeed, DataResolveRequest
from polisyos.data_forge.domains.catalog.knowledge.search import DatasetCatalogGraph
from polisyos.fabric.retrieval.service import RetrievalService
from polisyos.fabric.connectors.profiles import SourceProfileRegistry
from polisyos.fabric.connectors.registry import ConnectorRegistry

transport = {"harvest_calls": 0, "describe_calls": 0, "fetch_calls": 0, "fetch_requests": []}
http_calls = []

async def harvest_worldbank(_endpoint, _limit, _timeout):
    transport["harvest_calls"] += 1
    return [{k: v for k, v in row.items() if k != "metric"} for row in INDICATORS]

async def describe_dataset(_connector, _handle, dataset_id):
    transport["describe_calls"] += 1
    return DatasetCapabilitySnapshot(
        source="worldbank",
        dataset_id=dataset_id,
        resolved_dataset_id=dataset_id,
        preferred_transport="test",
        last_checked_at=datetime.now(UTC),
    )

async def fetch_dataset(_connector, _handle, request):
    transport["fetch_calls"] += 1
    if hasattr(request, "model_dump"):
        payload = request.model_dump(mode="json")
    elif is_dataclass(request):
        payload = asdict(request)
    else:
        payload = {key: getattr(request, key) for key in getattr(request, "__slots__", ()) if hasattr(request, key)}
    transport["fetch_requests"].append(jsonable(payload))
    return type(
        "WorldBankFixtureResult",
        (),
        {"data": pd.DataFrame([{"country_code": "UA", "year": 2020, "value": 1.1}])},
    )()

harvester._harvest_worldbank = harvest_worldbank
WorldBankConnector.describe_dataset = describe_dataset
WorldBankConnector.fetch = fetch_dataset

class FixtureHTTPResponse:
    def __init__(self, status: int, body: bytes, headers: dict[str, str]):
        self.status = status
        self._body = body
        self.headers = headers
    def __enter__(self):
        return self
    def __exit__(self, exc_type, exc, tb):
        return False
    def read(self, *args, **kwargs):
        return self._body
    def getheader(self, name, default=None):
        return self.headers.get(name.lower(), default)

def fixture_urlopen(request, timeout=10):
    url = request.full_url if hasattr(request, "full_url") else str(request)
    method = request.get_method() if hasattr(request, "get_method") else "GET"
    status = int(HTTP_MODE)
    body = b"fixture response at external HTTP reachability boundary"
    headers = {"content-type": "text/plain", "content-length": str(len(body))}
    http_calls.append({
        "url": url,
        "method": method,
        "timeout": timeout,
        "fixture_status": status,
        "fixture_body_utf8": body.decode("utf-8"),
        "fixture_headers": headers,
    })
    if status >= 500:
        raise urllib.error.HTTPError(
            url, status, "fixture upstream unavailable", hdrs=headers, fp=io.BytesIO(body)
        )
    return FixtureHTTPResponse(status, body, headers)

urllib.request.urlopen = fixture_urlopen

def write_registry(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join([
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
        ]) + "\n",
        encoding="utf-8",
    )

def make_config(name: str):
    target = run_root / name
    target.mkdir(parents=True, exist_ok=True)
    registry_path = target / "source-registry.yaml"
    write_registry(registry_path)
    return DatasetBatchConfig(
        snapshot_root=target / "snapshot",
        registry_path=registry_path,
        stages=frozenset({
            "harvest", "normalize", "merge_dedup", "graph_load",
            "core_sources_ingest", "benchmark", "qc", "publish",
        }),
        run_profile="prod_full",
        max_datasets_per_source=100_000,
        promoted_sources=("worldbank",),
        preflight_sources=("worldbank",),
        active_countries=("UA",),
        active_year_window=(2020, 2020),
        observation_mode="core",
        fail_fast_qc=True,
    )

MODULES = [
    "polisyos.core.contracts.control",
    "polisyos.data_forge.domains.catalog.batch.pipeline",
    "polisyos.data_forge.domains.catalog.batch.config",
    "polisyos.data_forge.domains.catalog.batch.source_registry",
    "polisyos.data_forge.domains.catalog.batch.harvester",
    "polisyos.data_forge.domains.catalog.batch.normalizer",
    "polisyos.data_forge.domains.catalog.batch.graph_builder",
    "polisyos.data_forge.domains.catalog.batch._core_sources_ingest_contracts",
    "polisyos.data_forge.domains.catalog.batch.core_sources.api",
    "polisyos.data_forge.domains.catalog.batch.core_sources.validators",
    "polisyos.data_forge.domains.catalog.batch.core_sources.writers",
    "polisyos.data_forge.domains.catalog.batch.core_sources.loaders",
    "polisyos.data_forge.domains.catalog.batch.core_sources.transformers",
    "polisyos.data_forge.domains.catalog.batch.core_sources_ingest",
    "polisyos.data_forge.domains.catalog.batch.benchmark",
    "polisyos.data_forge.domains.catalog.batch.qc",
    "polisyos.data_forge.domains.catalog.batch.publish",
    "polisyos.data_forge.domains.catalog.knowledge.search",
    "polisyos.fabric.retrieval.service",
    "polisyos.fabric.retrieval.executor",
    "polisyos.fabric.connectors.profiles.registry",
    "polisyos.fabric.connectors.registry_core_parts",
    "polisyos.fabric.connectors.sources.world_bank",
]
loaded = {name: importlib.import_module(name) for name in MODULES}
site_packages = Path(importlib.import_module("sysconfig").get_paths()["purelib"]).resolve()
source_package = (SOURCE / "src" / "polisyos").resolve()
module_proofs = {}
with zipfile.ZipFile(WHEEL) as wheel:
    for name, module in loaded.items():
        origin = Path(module.__file__).resolve()
        if not origin.is_relative_to(source_package):
            raise AssertionError(f"{name} not imported from exact editable archive source: {origin}")
        rel = origin.relative_to(source_package).as_posix()
        wheel_member = "polisyos/" + rel
        origin_bytes = origin.read_bytes()
        wheel_bytes = wheel.read(wheel_member)
        module_proofs[name] = {
            "origin": str(origin),
            "source_path": str(SOURCE / "src" / "polisyos" / rel),
            "wheel_member": wheel_member,
            "origin_sha256": sha_bytes(origin_bytes),
            "frozen_source_sha256": sha_bytes((SOURCE / "src" / "polisyos" / rel).read_bytes()),
            "wheel_sha256": sha_bytes(wheel_bytes),
            "origin_equals_archive_source_equals_wheel": origin_bytes == (SOURCE / "src" / "polisyos" / rel).read_bytes() == wheel_bytes,
        }
        if not module_proofs[name]["origin_equals_archive_source_equals_wheel"]:
            raise AssertionError(f"{name}: origin/source/wheel byte mismatch")

config = make_config("main")
pipeline_result = result_of(lambda: run_dataset_pipeline_sync(config))
negative_publish_result = None
if HTTP_MODE != "200":
    negative_publish_result = result_of(lambda: run_publish(config))
stage_state = read_json(config.stage_state_path)
raw_state = stage_state.get("core_sources_ingest") if isinstance(stage_state, dict) else None
core_manifest = read_json(config.manifests_dir / "core_sources_ingest.json")
checkpoint = read_json(config.observation_ingest_checkpoint_path)
receipt_state = _current_core_output_receipt_state(config)
manifest_path = config.manifests_dir / "harvest.json"
harvest_stage = read_json(manifest_path)
raw_manifest_path = config.raw_dir / "worldbank" / config.snapshot_root.name / "manifest.json"
raw_manifest = read_json(raw_manifest_path)
payload_path = Path(raw_manifest["payload"]) if isinstance(raw_manifest, dict) and raw_manifest.get("payload") else None
payload_bytes = payload_path.read_bytes() if payload_path and payload_path.is_file() else b""
raw_rows = [json.loads(line) for line in payload_bytes.decode("utf-8").splitlines() if line]
normalized_path = config.normalized_dir / "worldbank.jsonl"
normalized_rows = [json.loads(line) for line in normalized_path.read_text(encoding="utf-8").splitlines()] if normalized_path.exists() else []
merged_path = config.merged_records_path
merged_rows = [json.loads(line) for line in merged_path.read_text(encoding="utf-8").splitlines()] if merged_path.exists() else []

db_rows = []
db_datasets = []
db_bindings = []
db_distributions = []
db_alignments = []
db_counts = {}
db_error = None
try:
    with duckdb.connect(str(config.db_path), read_only=True) as con:
        db_datasets = [dict(zip([c[0] for c in con.description], row)) for row in con.execute(
            "SELECT id, source, dataset_id, polisyos_metrics, title, execution_tier FROM ds_datasets ORDER BY dataset_id"
        ).fetchall()]
        db_distributions = [dict(zip([c[0] for c in con.description], row)) for row in con.execute(
            "SELECT id, dataset_id, connector_type, profile_id, source_locator, url FROM ds_distributions ORDER BY source_locator"
        ).fetchall()]
        db_bindings = [dict(zip([c[0] for c in con.description], row)) for row in con.execute(
            "SELECT metric_id, dataset_id, connector_id, profile_id, request_dataset_id, execution_tier, source "
            "FROM ds_metric_bindings ORDER BY metric_id, dataset_id"
        ).fetchall()]
        db_alignments = [dict(zip([c[0] for c in con.description], row)) for row in con.execute(
            "SELECT dataset_id, raw_variable, canonical_var, method, confidence, evidence "
            "FROM ds_variable_alignments ORDER BY raw_variable, canonical_var"
        ).fetchall()]
        db_rows = [dict(zip([c[0] for c in con.description], row)) for row in con.execute(
            "SELECT dataset_id, raw_variable, canonical_var, country_code, year, value "
            "FROM ds_observations ORDER BY raw_variable, country_code, year"
        ).fetchall()]
        for table in ("ds_datasets", "ds_distributions", "ds_metric_bindings", "ds_variable_alignments", "ds_observations"):
            db_counts[table] = con.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
except Exception as exc:
    db_error = f"{type(exc).__name__}: {exc}"

benchmark = read_json(config.benchmark_report_path)
qc_report = read_json(config.qc_report_path)
readiness = read_json(config.consumer_readiness_path)
publish_manifest = read_json(config.publish_manifest_path)
content_receipts = {
    stage: current_content_stage_receipt(config, stage)
    for stage in ("benchmark", "qc", "publish")
}
stage_manifests = {
    stage: read_json(config.manifests_dir / f"{stage}.json")
    for stage in ("harvest", "normalize", "merge_dedup", "graph_load", "benchmark", "qc", "publish")
}
runtime_profile_path = config.resolved_metrics_map_path
seed_path = _seed_alignments_path()
resource_proofs = {
    "metrics_map": {
        "path": str(runtime_profile_path),
        "exists": runtime_profile_path.is_file(),
        "sha256": sha_file(runtime_profile_path) if runtime_profile_path.is_file() else None,
        "archive_expected_sha256": sha_file(SOURCE / "data" / "dataset_catalog" / "metrics_map.yaml"),
        "bytes_equal": runtime_profile_path.read_bytes() == (SOURCE / "data" / "dataset_catalog" / "metrics_map.yaml").read_bytes() if runtime_profile_path.is_file() else False,
    },
    "seed_variable_alignments": {
        "path": str(seed_path),
        "exists": seed_path.is_file(),
        "sha256": sha_file(seed_path) if seed_path.is_file() else None,
        "archive_expected_sha256": sha_file(SOURCE / "data" / "dataset_catalog" / "seed_variable_alignments.yaml"),
        "bytes_equal": seed_path.read_bytes() == (SOURCE / "data" / "dataset_catalog" / "seed_variable_alignments.yaml").read_bytes() if seed_path.is_file() else False,
    },
}

retrieval = {"status": "not_run"}
profile_controls = {}
if HTTP_MODE == "200":
    os.environ["POLISYOS_RETRIEVAL_FASTLANE_ENABLED"] = "0"
    os.environ["POLISYOS_RETRIEVAL_EXPLORE_ENABLED"] = "0"
    def resolve_for(db_path: Path, name: str):
        catalog = DatasetCatalogGraph(db_path=db_path, index_dir=run_root / f"retrieval-index-{name}")
        service = RetrievalService(curated_dir=run_root / "curated", dataset_catalog=catalog)
        req = DataResolveRequest(
            data_needs=[DataNeed(metric="gdp_per_capita", geography="UA", time_start="2020", time_end="2020", quality_min=0.0)],
            mode="fastlane",
            allow_explore_fallback=False,
        )
        try:
            resolved = service.resolve(req, run_profile="prod_full")
            return service, catalog, resolved
        except Exception:
            catalog.close()
            raise
    def _resolve_normal():
        service, catalog, outcome = resolve_for(config.db_path, "normal")
        try:
            return {
                "lane_used": outcome.telemetry.get("lane_used"),
                "candidate_count": len(outcome.candidates),
                "plans": [plan.model_dump(mode="json") for plan in outcome.fetch_plans],
                "warnings": list(outcome.warnings),
                "run_profile": "prod_full",
            }
        finally:
            catalog.close()
    normal_result = result_of(_resolve_normal)
    retrieval = normal_result

    builtin_registry = ConnectorRegistry.get_instance()
    default_config = builtin_registry.get_default_config("worldbank.wdi")
    def _profile_control(service, request, run_profile):
        outcome = service.resolve(request, run_profile=run_profile)
        return {
            "resolved_plans": [plan.model_dump(mode="json") for plan in outcome.fetch_plans],
            "candidate_count": len(outcome.candidates),
            "warnings": list(outcome.warnings),
            "run_profile": run_profile,
        }
    for control_name, profile_value in (("missing", None), ("unknown", "unknown-profile")):
        catalog = DatasetCatalogGraph(db_path=config.db_path, index_dir=run_root / f"profile-index-{control_name}")
        service = RetrievalService(
            curated_dir=run_root / "curated",
            dataset_catalog=catalog,
            registry=builtin_registry,
            profiles=SourceProfileRegistry(),
        )
        request = DataResolveRequest(
            data_needs=[DataNeed(metric="gdp_per_capita", geography="UA", time_start="2020", time_end="2020", quality_min=0.0)],
            mode="fastlane",
            allow_explore_fallback=False,
        )
        control_result = result_of(lambda: _profile_control(service, request, profile_value))
        profile_controls[control_name] = {
            "requested_catalog_run_profile": profile_value,
            "registry_has_worldbank_connector": builtin_registry.has("worldbank.wdi"),
            "default_connection_config_present": default_config is not None,
            "empty_source_profile_registry_count": len(SourceProfileRegistry().list_all()),
            "outcome_is_refusal": (
                control_result.get("status") == "raised"
                or not (control_result.get("value") or {}).get("resolved_plans")
            ),
            "outcome": control_result,
        }
        catalog.close()

profile_input_rejection = result_of(
    lambda: DataNeed.model_validate({"metric": "gdp_per_capita", "profile_id": "worldbank_wdi"})
)

try:
    with duckdb.connect(str(config.db_path)) as con:
        con.execute("CHECKPOINT")
except Exception:
    pass

dist_records = {}
for path in config.component_dir.rglob("*"):
    if path.is_file():
        dist_records[str(path)] = {"sha256": sha_file(path), "bytes": path.stat().st_size}

result = {
    "candidate": {
        "commit": "8dfa7f3c544461c0ff081861848fcc5d8523da5b",
        "tree": "3eac9b5cf816e30f9c1bacc81d80e2dc75d81681",
        "source_root": str(SOURCE),
        "wheel": str(WHEEL),
        "wheel_sha256": sha_file(WHEEL),
        "source_registry_path": str(config.registry_path),
        "registry_sha256": sha_file(config.registry_path),
        "metrics_map_path": str(runtime_profile_path),
        "metrics_map_sha256": sha_file(runtime_profile_path),
    },
    "runtime": {
        "cwd": os.getcwd(),
        "python": sys.executable,
        "python_version": sys.version.split()[0],
        "isolated_mode": bool(sys.flags.isolated),
        "safe_path": bool(sys.flags.safe_path),
        "PYTHONPATH": os.environ.get("PYTHONPATH"),
        "site_packages": str(site_packages),
        "sys_path": list(sys.path),
        "source_root_on_sys_path": any(str(SOURCE) in value for value in sys.path),
        "source_package_on_sys_path": any(str(SOURCE / "src") in value for value in sys.path),
        "sys_path_at_start": baseline_sys_path,
        "sys_path_after_probe": list(sys.path),
        "sys_path_unchanged": baseline_sys_path == list(sys.path),
    },
    "profile": {
        "selection": "base-only locked uv profile; no dev/test/optional extra",
        "python": sys.version.split()[0],
        "distribution_count": len(list(importlib.metadata.distributions())),
        "source_project_direct_url": importlib.metadata.distribution("policy-engine").read_text("direct_url.json"),
    },
    "installed_module_bytes": module_proofs,
    "resources": resource_proofs,
    "fixture_scope": {
        "registry_source": "worldbank",
        "registry_run_lane": "empirical",
        "registry_publish_blocking": True,
        "run_profile": config.run_profile,
        "active_countries": list(config.active_countries),
        "active_year_window": list(config.active_year_window),
        "observation_mode": config.observation_mode,
        "max_datasets_per_source": config.max_datasets_per_source,
        "metadata_fixture_rows_returned_by_external_harvest_stub": len(INDICATORS),
        "expected_indicators": INDICATORS,
        "only_worldbank_metadata_and_fetch_stubs": True,
        "url_reachability_boundary": {
            "urllib_urlopen_stubbed": True,
            "fixture_http_status": int(HTTP_MODE),
            "live_external_url_reachability": "not_established",
            "actual_network_requests": 0,
            "calls": http_calls,
        },
        "synthetic_observation_value": 1.1,
        "synthetic_observation_geography_year": ["UA", 2020],
        "no_production_data_or_model_weights": True,
    },
    "execution": {
        "pipeline": jsonable(pipeline_result),
        "direct_publish_after_pipeline": jsonable(negative_publish_result),
        "harvest_transport": {
            "stub_calls": transport["harvest_calls"],
            "stub_return_count": len(INDICATORS),
            "manifest": harvest_stage,
        },
        "raw_manifest": raw_manifest,
        "raw_payload": {
            "path": str(payload_path) if payload_path else None,
            "sha256": sha_bytes(payload_bytes),
            "line_count": len(raw_rows),
            "indicator_ids": [row.get("id") for row in raw_rows],
            "rows": raw_rows,
        },
        "normalized": {
            "path": str(normalized_path),
            "sha256": sha_file(normalized_path) if normalized_path.is_file() else None,
            "line_count": len(normalized_rows),
            "rows": normalized_rows,
        },
        "merged": {
            "path": str(merged_path),
            "sha256": sha_file(merged_path) if merged_path.is_file() else None,
            "line_count": len(merged_rows),
            "rows": merged_rows,
        },
        "stage_manifests": stage_manifests,
        "core": {
            "manifest": core_manifest,
            "stage_state": raw_state,
            "checkpoint": checkpoint,
            "current_receipt": receipt_state.basis_member(),
            "receipt_is_current": receipt_state.is_current,
            "db_path": str(config.db_path),
            "db_sha256": sha_file(config.db_path) if config.db_path.is_file() else None,
            "db_error": db_error,
            "table_counts": db_counts,
            "datasets": db_datasets,
            "distributions": db_distributions,
            "metric_bindings": db_bindings,
            "alignments": db_alignments,
            "observations": db_rows,
            "transport": {
                "describe_calls": transport["describe_calls"],
                "fetch_calls": transport["fetch_calls"],
                "fetch_requests": transport["fetch_requests"],
            },
        },
        "benchmark": benchmark,
        "qc": qc_report,
        "consumer_readiness": readiness,
        "publish_manifest": publish_manifest,
        "component_artifact_digests": dist_records,
        "content_bound_receipts": content_receipts,
        "retrieval": retrieval,
        "profile_controls": profile_controls,
        "request_profile_input_control": profile_input_rejection,
        "expected_metric_map": EXPECTED_METRICS,
    },
}
out = run_root / "catalog-runtime-result.json"
out.write_text(json.dumps(result, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
print(json.dumps({
    "run_root": str(run_root),
    "result_path": str(out),
    "pipeline": jsonable(pipeline_result),
    "direct_publish_after_pipeline": jsonable(negative_publish_result),
    "raw_count": len(raw_rows),
    "normalized_count": len(normalized_rows),
    "db_counts": db_counts,
    "benchmark_metrics": benchmark.get("metrics") if isinstance(benchmark, dict) else None,
    "qc_passed": qc_report.get("passed") if isinstance(qc_report, dict) else None,
    "readiness": readiness.get("readiness") if isinstance(readiness, dict) else None,
    "publish_manifest": str(config.publish_manifest_path) if config.publish_manifest_path.exists() else None,
    "retrieval": retrieval,
    "profile_controls": profile_controls,
    "result_sha256": sha_file(out),
}, sort_keys=True, default=str))
