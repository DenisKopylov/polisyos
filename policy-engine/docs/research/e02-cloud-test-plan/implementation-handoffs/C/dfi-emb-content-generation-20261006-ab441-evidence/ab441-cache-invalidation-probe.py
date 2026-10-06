from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import duckdb
import pandas as pd

from polisyos.data_forge.domains.catalog.batch.config import DatasetBatchConfig
from polisyos.data_forge.domains.catalog.batch.graph_builder import build_graph
from polisyos.data_forge.domains.catalog.batch.pipeline import (
    current_content_stage_receipt,
    run_dataset_pipeline_sync,
)
from polisyos.data_forge.domains.catalog.knowledge.types import DatasetRecord, DistributionRecord
from polisyos.fabric.connectors.base import DatasetCapabilitySnapshot
from polisyos.fabric.connectors.sources.world_bank import WorldBankConnector

ROOT = Path('/Users/deniskopylov/.codex/worktrees/e02-c-continuation-20261006/polisyos/.tmp/e02-C2/raw/dfi-emb-review/core-publication-cache-final')
FIXTURE = ROOT / 'cache-invalidation-fixture-2'
if FIXTURE.exists():
    raise SystemExit(f'refusing to replace existing fixture: {FIXTURE}')
FIXTURE.mkdir(parents=True)
registry_path = FIXTURE / 'registry.yaml'
registry_path.write_text('\n'.join([
    'version: 1', 'sources:', '  - name: worldbank', '    family: worldbank',
    '    wave: A', '    endpoint: https://example.test/worldbank',
    '    connector_id: worldbank.wdi', '    profile_id: worldbank_wdi',
    '    enabled: true', '    execution_tier: transport_ready',
    '    run_lane: empirical', '    publish_blocking: true',
]) + '\n', encoding='utf-8')
config = DatasetBatchConfig(
    snapshot_root=FIXTURE / 'snapshot', registry_path=registry_path,
    stages=frozenset({'core_sources_ingest', 'benchmark'}),
    run_profile='preflight_core', promoted_sources=('worldbank',),
    preflight_sources=('worldbank',), active_countries=('UA',),
    active_year_window=(2020, 2020), observation_mode='core',
    max_datasets_per_source=1, resume=True, resume_mode='force',
)
record = DatasetRecord(
    id='wb-gdp', title='GDP per capita', description='GDP per capita',
    source='worldbank', source_portal='worldbank', dataset_id='NY.GDP.PCAP.PP.CD',
    source_dataset_id='NY.GDP.PCAP.PP.CD', execution_tier='transport_ready',
    update_frequency='annual', polisyos_metrics=['gdp_per_capita'],
    variables=['NY.GDP.PCAP.PP.CD'], preferred_distribution_id='dist-wb',
    distributions=[DistributionRecord(
        id='dist-wb', connector_type='worldbank.wdi', profile_id='worldbank_wdi',
        source_locator='NY.GDP.PCAP.PP.CD', parser_supported=True, machine_readable=True,
    )],
)
build_graph(records=[record], db_path=config.db_path)
fetch_calls = {'count': 0}

async def describe_dataset(_connector: WorldBankConnector, _handle: object, dataset_id: str) -> DatasetCapabilitySnapshot:
    return DatasetCapabilitySnapshot(source='worldbank', dataset_id=dataset_id, resolved_dataset_id=dataset_id, last_checked_at=datetime.now(UTC))

async def fetch(_connector: WorldBankConnector, _handle: object, _request: object) -> object:
    fetch_calls['count'] += 1
    return SimpleNamespace(data=pd.DataFrame([{'country_code': 'UA', 'year': 2020, 'value': 1.1}]))

WorldBankConnector.describe_dataset = describe_dataset
WorldBankConnector.fetch = fetch

initial_stats = run_dataset_pipeline_sync(config)
initial_report = json.loads(config.benchmark_report_path.read_text(encoding='utf-8'))
checkpoint = json.loads(config.observation_ingest_checkpoint_path.read_text(encoding='utf-8'))
completed_ids = [key for key, value in checkpoint.get('completed', {}).items() if value.get('status') == 'complete_with_rows']
if len(completed_ids) != 1:
    raise AssertionError(f'expected 1 completed shard; found {completed_ids!r}')
shard_id = completed_ids[0]
stage_state_before = json.loads(config.stage_state_path.read_text(encoding='utf-8'))['core_sources_ingest']
receipt_before = current_content_stage_receipt(config, 'benchmark')
benchmark_report_before_bytes = config.benchmark_report_path.read_bytes()
stage_state_before_bytes = config.stage_state_path.read_bytes()

# Falsify the canonical ledger but keep benchmark-facing stage state and all listed
# pipeline inputs other than the omitted checkpoint byte-for-byte unchanged.
mutated = json.loads(config.observation_ingest_checkpoint_path.read_text(encoding='utf-8'))
entry = mutated['completed'].pop(shard_id)
entry['status'] = 'deferred'
entry['error'] = 'cache invalidation falsified-premise control'
mutated.setdefault('deferred', {})[shard_id] = entry
mutated['publishable_core_complete'] = False
config.observation_ingest_checkpoint_path.write_text(json.dumps(mutated, sort_keys=True), encoding='utf-8')
mutation_left_stage_and_report_bytes_unchanged = (
    config.stage_state_path.read_bytes() == stage_state_before_bytes
    and config.benchmark_report_path.read_bytes() == benchmark_report_before_bytes
)
benchmark_only = replace(config, stages=frozenset({'benchmark'}))
pipeline_benchmark_stats = run_dataset_pipeline_sync(benchmark_only)
pipeline_report = json.loads(config.benchmark_report_path.read_text(encoding='utf-8'))
core_state_after_pipeline = json.loads(config.stage_state_path.read_text(encoding='utf-8'))['core_sources_ingest']
stage_state_held_unchanged = stage_state_before == core_state_after_pipeline
receipt_after_pipeline = current_content_stage_receipt(config, 'benchmark')
repeated_pipeline_stats = run_dataset_pipeline_sync(benchmark_only)
repeated_pipeline_report = json.loads(config.benchmark_report_path.read_text(encoding='utf-8'))

# Invoke the consumer itself, bypassing only the pipeline's resume selector, to prove
# the content is contradictory and the consumer can detect it when actually run.
from polisyos.data_forge.domains.catalog.batch.benchmark import run_benchmark

direct_stats = run_benchmark(config)
direct_report = json.loads(config.benchmark_report_path.read_text(encoding='utf-8'))

# Restore checkpoint, remove a core output, ensure receipt mismatch blocks readiness,
# and verify resumption refetches rather than treating old completion as current.
config.observation_ingest_checkpoint_path.write_text(json.dumps(checkpoint, sort_keys=True), encoding='utf-8')
with duckdb.connect(str(config.db_path)) as con:
    con.execute("DELETE FROM ds_observations WHERE dataset_id = 'wb-gdp'")
    con.execute('CHECKPOINT')
removed_output_benchmark_stats = run_dataset_pipeline_sync(benchmark_only)
removed_output_report = json.loads(config.benchmark_report_path.read_text(encoding='utf-8'))
fetch_before_resume = fetch_calls['count']
core_only = replace(config, stages=frozenset({'core_sources_ingest'}))
resume_stats = run_dataset_pipeline_sync(core_only)
with duckdb.connect(str(config.db_path), read_only=True) as con:
    restored_rows = con.execute("SELECT dataset_id, raw_variable, country_code, year, value FROM ds_observations WHERE dataset_id = 'wb-gdp'").fetchall()
resumed_checkpoint = json.loads(config.observation_ingest_checkpoint_path.read_text(encoding='utf-8'))
resumed_state = json.loads(config.stage_state_path.read_text(encoding='utf-8'))['core_sources_ingest']
final_stats = run_dataset_pipeline_sync(config)
final_report = json.loads(config.benchmark_report_path.read_text(encoding='utf-8'))

result: dict[str, Any] = {
    'candidate_commit': subprocess.run(['git', 'rev-parse', 'HEAD'], cwd='/Users/deniskopylov/.codex/worktrees/e02-c-dfi-emb-20261006/polisyos', capture_output=True, text=True, check=True).stdout.strip(),
    'candidate_tree': subprocess.run(['git', 'rev-parse', 'HEAD^{tree}'], cwd='/Users/deniskopylov/.codex/worktrees/e02-c-dfi-emb-20261006/polisyos', capture_output=True, text=True, check=True).stdout.strip(),
    'fixture_root': str(FIXTURE),
    'shard_id': shard_id,
    'initial': {'fetch_calls': fetch_before_resume, 'core_observations': initial_stats.metrics.get('core_observations'), 'benchmark_mode': initial_report.get('evaluation_mode'), 'stage_status': stage_state_before.get('status'), 'receipt_present': receipt_before is not None},
    'ledger_only_mutation': {'checkpoint_status': mutated['deferred'][shard_id]['status'], 'stage_state_held_unchanged': stage_state_held_unchanged, 'mutation_left_stage_and_report_bytes_unchanged': mutation_left_stage_and_report_bytes_unchanged, 'pipeline_benchmark_mode': pipeline_report.get('evaluation_mode'), 'pipeline_partial_eval': pipeline_report.get('metrics', {}).get('benchmark_partial_eval'), 'pipeline_stats': pipeline_benchmark_stats.metrics, 'benchmark_receipt_still_current': receipt_after_pipeline is not None, 'repeated_pipeline_mode': repeated_pipeline_report.get('evaluation_mode'), 'repeated_pipeline_partial_eval': repeated_pipeline_report.get('metrics', {}).get('benchmark_partial_eval'), 'repeated_pipeline_skipped': 'benchmark' in repeated_pipeline_stats.skipped_stages, 'direct_consumer_mode': direct_report.get('evaluation_mode'), 'direct_consumer_partial_eval': direct_report.get('metrics', {}).get('benchmark_partial_eval'), 'direct_stats': direct_stats.metrics},
    'removed_output': {'pipeline_mode': removed_output_report.get('evaluation_mode'), 'pipeline_partial_eval': removed_output_report.get('metrics', {}).get('benchmark_partial_eval'), 'benchmark_stats': removed_output_benchmark_stats.metrics},
    'resume_after_removed_output': {'fetches_before': fetch_before_resume, 'fetches_after': fetch_calls['count'], 'core_failures': resume_stats.metrics.get('core_failures'), 'db_rows': restored_rows, 'checkpoint_success': resumed_checkpoint.get('completed', {}).get(shard_id, {}).get('status'), 'stage_status': resumed_state.get('status'), 'benchmark_mode_after_repair': final_report.get('evaluation_mode'), 'final_core_failures': final_stats.metrics.get('core_failures')},
    'assertions': {
        'initial_actual_persisted_observation': initial_stats.metrics.get('core_observations') == 1 and initial_report.get('evaluation_mode') == 'full-ready',
        'mutation_kept_markers_and_report_bytes': mutation_left_stage_and_report_bytes_unchanged,
        'pipeline_cache_recomputes_falsified_checkpoint': pipeline_report.get('evaluation_mode') == 'partial-eval' and pipeline_report.get('metrics', {}).get('benchmark_partial_eval') == 1 and 'benchmark' not in pipeline_benchmark_stats.skipped_stages,
        'partial_receipt_not_reusable_without_core_receipt': repeated_pipeline_report.get('evaluation_mode') == 'partial-eval' and repeated_pipeline_report.get('metrics', {}).get('benchmark_partial_eval') == 1 and 'benchmark' not in repeated_pipeline_stats.skipped_stages,
        'direct_consumer_blocks_falsified_checkpoint': direct_report.get('evaluation_mode') == 'partial-eval' and direct_report.get('metrics', {}).get('benchmark_partial_eval') == 1,
        'removed_output_blocks_benchmark': removed_output_report.get('evaluation_mode') == 'partial-eval' and removed_output_report.get('metrics', {}).get('benchmark_partial_eval') == 1,
        'resume_refetches_removed_output': fetch_calls['count'] == fetch_before_resume + 1 and len(restored_rows) == 1 and resume_stats.metrics.get('core_failures') == 0,
        'repair_reaches_full_ready': final_report.get('evaluation_mode') == 'full-ready' and final_stats.metrics.get('core_failures') == 0,
    },
}
result_path = ROOT / 'cache-invalidation-probe.json'
result_path.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n', encoding='utf-8')
print(json.dumps({'result_path': str(result_path), 'result_sha256': hashlib.sha256(result_path.read_bytes()).hexdigest(), 'assertions': result['assertions'], 'result': result}, indent=2, sort_keys=True))
if not all(result['assertions'].values()):
    raise SystemExit(1)
