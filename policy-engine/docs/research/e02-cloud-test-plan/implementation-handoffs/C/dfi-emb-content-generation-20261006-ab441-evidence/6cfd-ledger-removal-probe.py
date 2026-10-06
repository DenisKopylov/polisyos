from __future__ import annotations

import hashlib
import json
import os
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

ROOT = Path('/Users/deniskopylov/.codex/worktrees/e02-c-continuation-20261006/polisyos/.tmp/e02-C2/raw/dfi-emb-review/core-publication-delta')
FIXTURE = ROOT / 'ledger-removal-fixture'
if FIXTURE.exists():
    raise SystemExit(f'refusing to replace existing fixture: {FIXTURE}')
FIXTURE.mkdir(parents=True)
registry_path = FIXTURE / 'registry.yaml'
registry_path.write_text(
    '\n'.join([
        'version: 1',
        'sources:',
        '  - name: worldbank',
        '    family: worldbank',
        '    wave: A',
        '    endpoint: https://example.test/worldbank',
        '    connector_id: worldbank.wdi',
        '    profile_id: worldbank_wdi',
        '    enabled: true',
        '    execution_tier: transport_ready',
        '    run_lane: empirical',
        '    publish_blocking: true',
    ]) + '\n',
    encoding='utf-8',
)
config = DatasetBatchConfig(
    snapshot_root=FIXTURE / 'snapshot',
    registry_path=registry_path,
    stages=frozenset({'core_sources_ingest', 'benchmark'}),
    run_profile='preflight_core',
    promoted_sources=('worldbank',),
    preflight_sources=('worldbank',),
    active_countries=('UA',),
    active_year_window=(2020, 2020),
    observation_mode='core',
    max_datasets_per_source=1,
    resume=True,
    resume_mode='force',
)
record = DatasetRecord(
    id='wb-gdp',
    title='GDP per capita',
    description='GDP per capita',
    source='worldbank',
    source_portal='worldbank',
    dataset_id='NY.GDP.PCAP.PP.CD',
    source_dataset_id='NY.GDP.PCAP.PP.CD',
    execution_tier='transport_ready',
    update_frequency='annual',
    polisyos_metrics=['gdp_per_capita'],
    variables=['NY.GDP.PCAP.PP.CD'],
    preferred_distribution_id='dist-wb',
    distributions=[
        DistributionRecord(
            id='dist-wb',
            connector_type='worldbank.wdi',
            profile_id='worldbank_wdi',
            source_locator='NY.GDP.PCAP.PP.CD',
            parser_supported=True,
            machine_readable=True,
        )
    ],
)
build_graph(records=[record], db_path=config.db_path)
fetch_calls = {'count': 0}

async def describe_dataset(
    _connector: WorldBankConnector, _handle: object, dataset_id: str
) -> DatasetCapabilitySnapshot:
    return DatasetCapabilitySnapshot(
        source='worldbank',
        dataset_id=dataset_id,
        resolved_dataset_id=dataset_id,
        last_checked_at=datetime.now(UTC),
    )

async def fetch(
    _connector: WorldBankConnector, _handle: object, _request: object
) -> object:
    fetch_calls['count'] += 1
    return SimpleNamespace(data=pd.DataFrame([{'country_code': 'UA', 'year': 2020, 'value': 1.1}]))

WorldBankConnector.describe_dataset = describe_dataset
WorldBankConnector.fetch = fetch

initial_stats = run_dataset_pipeline_sync(config)
initial_stage_state = json.loads(config.stage_state_path.read_text(encoding='utf-8'))
initial_core_state = initial_stage_state['core_sources_ingest']
initial_core_metadata = initial_core_state['metadata']
initial_checkpoint = json.loads(config.observation_ingest_checkpoint_path.read_text(encoding='utf-8'))
initial_completed = json.loads((config.manifests_dir / 'completed_observation_shards.json').read_text(encoding='utf-8'))
initial_deferred = json.loads((config.manifests_dir / 'deferred_observation_plans.json').read_text(encoding='utf-8'))
initial_summary = json.loads((config.manifests_dir / 'observation_source_summary.json').read_text(encoding='utf-8'))
initial_benchmark = json.loads(config.benchmark_report_path.read_text(encoding='utf-8'))
with duckdb.connect(str(config.db_path), read_only=True) as con:
    initial_db_observations = int(con.execute("SELECT count(*) FROM ds_observations WHERE dataset_id = 'wb-gdp'").fetchone()[0])
completed_entries = [
    (key, value) for key, value in initial_checkpoint.get('completed', {}).items()
    if value.get('status') == 'complete_with_rows' and value.get('source') == 'worldbank'
]
if len(completed_entries) != 1:
    raise AssertionError(f'expected exactly one completed WorldBank checkpoint entry, got {len(completed_entries)}')
shard_id, completed_entry = completed_entries[0]

# Simulate loss/replacement of the persisted DuckDB output while retaining the checkpoint.
with duckdb.connect(str(config.db_path)) as con:
    con.execute("DELETE FROM ds_observations WHERE dataset_id = 'wb-gdp'")
    con.execute('CHECKPOINT')
with duckdb.connect(str(config.db_path), read_only=True) as con:
    after_delete_db_observations = int(con.execute("SELECT count(*) FROM ds_observations WHERE dataset_id = 'wb-gdp'").fetchone()[0])

core_only = replace(config, stages=frozenset({'core_sources_ingest'}))
reused_stats = run_dataset_pipeline_sync(core_only)
reused_state = json.loads(config.stage_state_path.read_text(encoding='utf-8'))['core_sources_ingest']
reused_manifest = json.loads((config.manifests_dir / 'core_sources_ingest.json').read_text(encoding='utf-8'))
reused_checkpoint = json.loads(config.observation_ingest_checkpoint_path.read_text(encoding='utf-8'))
reused_completed_manifest = json.loads((config.manifests_dir / 'completed_observation_shards.json').read_text(encoding='utf-8'))
reused_summary = json.loads((config.manifests_dir / 'observation_source_summary.json').read_text(encoding='utf-8'))
with duckdb.connect(str(config.db_path), read_only=True) as con:
    reused_db_observations = int(con.execute("SELECT count(*) FROM ds_observations WHERE dataset_id = 'wb-gdp'").fetchone()[0])

# Falsify the actual persisted result ledger and its progress manifest, holding the
# benchmark-facing producer-stage success declarations byte-for-byte unchanged.
mutated_checkpoint = json.loads(config.observation_ingest_checkpoint_path.read_text(encoding='utf-8'))
mutated_entry = mutated_checkpoint['completed'].pop(shard_id)
mutated_entry['status'] = 'deferred'
mutated_entry['error'] = 'independent ledger-removal control'
mutated_checkpoint.setdefault('deferred', {})[shard_id] = mutated_entry
mutated_checkpoint['publishable_core_complete'] = False
config.observation_ingest_checkpoint_path.write_text(
    json.dumps(mutated_checkpoint, ensure_ascii=False, sort_keys=True, indent=2) + '\n',
    encoding='utf-8',
)
(config.manifests_dir / 'completed_observation_shards.json').write_text('[]\n', encoding='utf-8')
(config.manifests_dir / 'deferred_observation_plans.json').write_text(
    json.dumps([{**completed_entry, 'status': 'deferred', 'error': 'independent ledger-removal control'}], indent=2) + '\n',
    encoding='utf-8',
)
(config.manifests_dir / 'observation_source_summary.json').write_text(
    json.dumps({'worldbank': {'complete': 0, 'complete_with_rows': 0, 'complete_empty': 0, 'deferred': 1, 'failed': 0, 'rows': 0}}, indent=2) + '\n',
    encoding='utf-8',
)
held_markers_before_benchmark = json.loads(config.stage_state_path.read_text(encoding='utf-8'))['core_sources_ingest']

benchmark_only = replace(config, stages=frozenset({'benchmark'}))
benchmark_stats = run_dataset_pipeline_sync(benchmark_only)
post_mutation_stage_state = json.loads(config.stage_state_path.read_text(encoding='utf-8'))
post_mutation_core_state = post_mutation_stage_state['core_sources_ingest']
post_mutation_benchmark = json.loads(config.benchmark_report_path.read_text(encoding='utf-8'))
benchmark_receipt = current_content_stage_receipt(config, 'benchmark')
with duckdb.connect(str(config.db_path), read_only=True) as con:
    final_db_observations = int(con.execute("SELECT count(*) FROM ds_observations WHERE dataset_id = 'wb-gdp'").fetchone()[0])

result: dict[str, Any] = {
    'candidate_commit': subprocess.run(['git', 'rev-parse', 'HEAD'], cwd='/Users/deniskopylov/.codex/worktrees/e02-c-dfi-emb-20261006/polisyos', capture_output=True, text=True, check=True).stdout.strip(),
    'candidate_tree': subprocess.run(['git', 'rev-parse', 'HEAD^{tree}'], cwd='/Users/deniskopylov/.codex/worktrees/e02-c-dfi-emb-20261006/polisyos', capture_output=True, text=True, check=True).stdout.strip(),
    'fixture_root': str(FIXTURE),
    'run_signature': config.run_signature,
    'initial': {
        'core_stats_observations': initial_stats.metrics.get('core_observations'),
        'fetch_calls': fetch_calls['count'],
        'db_observations': initial_db_observations,
        'core_status': initial_core_state.get('status'),
        'core_complete': initial_core_metadata.get('publishable_core_complete'),
        'core_pending': initial_core_metadata.get('publishable_core_pending'),
        'benchmark_evaluation_mode': initial_benchmark.get('evaluation_mode'),
        'checkpoint_shard_id': shard_id,
        'checkpoint_entry_status': completed_entry.get('status'),
        'source_summary': initial_summary,
        'completed_manifest_count': len(initial_completed),
        'deferred_manifest_count': len(initial_deferred),
    },
    'after_db_output_removed_then_resumed': {
        'core_stats_observations': reused_stats.metrics.get('core_observations'),
        'additional_fetch_calls': fetch_calls['count'] - 1,
        'db_observations': reused_db_observations,
        'stage_status': reused_state.get('status'),
        'publishable_core_complete': reused_state.get('metadata', {}).get('publishable_core_complete'),
        'publishable_core_pending': reused_state.get('metadata', {}).get('publishable_core_pending'),
        'source_core_completion_pct': reused_state.get('metadata', {}).get('source_core_completion_pct'),
        'producer_manifest_status': reused_manifest.get('status'),
        'producer_manifest_completed_shards': reused_manifest.get('metrics', {}).get('completed_shards'),
        'checkpoint_has_success_entry': reused_checkpoint.get('completed', {}).get(shard_id, {}).get('status'),
        'completed_manifest_count': len(reused_completed_manifest),
        'source_summary': reused_summary,
    },
    'actual_ledger_falsified_same_stage_markers': {
        'checkpoint_completed_entry_present': shard_id in mutated_checkpoint.get('completed', {}),
        'checkpoint_deferred_status': mutated_checkpoint.get('deferred', {}).get(shard_id, {}).get('status'),
        'checkpoint_publishable_core_complete': mutated_checkpoint.get('publishable_core_complete'),
        'core_stage_state_before_benchmark': held_markers_before_benchmark,
        'core_stage_state_after_benchmark': post_mutation_core_state,
        'db_observations': final_db_observations,
        'benchmark_evaluation_mode': post_mutation_benchmark.get('evaluation_mode'),
        'benchmark_partial_eval': post_mutation_benchmark.get('metrics', {}).get('benchmark_partial_eval'),
        'benchmark_source_preflight_ready_pct': post_mutation_benchmark.get('metrics', {}).get('benchmark_source_preflight_ready_pct'),
        'source_preflight': post_mutation_benchmark.get('source_preflight'),
        'current_benchmark_receipt_available': benchmark_receipt is not None,
        'current_benchmark_receipt_basis_digest': benchmark_receipt.get('input_basis_digest') if benchmark_receipt else None,
    },
    'assertions': {
        'initial_success_produced_actual_row': initial_stats.metrics.get('core_observations') == 1 and initial_db_observations == 1,
        'same_checkpoint_reuse_did_not_fetch_after_db_output_loss': fetch_calls['count'] == 1 and reused_stats.metrics.get('core_observations') == 0 and reused_db_observations == 0,
        'checkpoint_reuse_still_claimed_core_complete': reused_state.get('status') == 'complete' and reused_state.get('metadata', {}).get('publishable_core_complete') is True and reused_state.get('metadata', {}).get('publishable_core_pending') == 0,
        'bridge_kept_full_ready_after_actual_ledger_was_deferred': post_mutation_benchmark.get('evaluation_mode') == 'full-ready' and post_mutation_core_state.get('metadata', {}).get('publishable_core_complete') is True and mutated_checkpoint.get('publishable_core_complete') is False and shard_id not in mutated_checkpoint.get('completed', {}),
        'source_preflight_reports_real_incomplete_inputs': post_mutation_benchmark.get('metrics', {}).get('benchmark_source_preflight_ready_pct') == 0.0,
        'content_bound_benchmark_receipt_current_for_stale_stage_declaration': benchmark_receipt is not None,
    },
}
result_path = ROOT / 'ledger-removal-probe.json'
result_path.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n', encoding='utf-8')
print(json.dumps({'result_path': str(result_path), 'result_sha256': hashlib.sha256(result_path.read_bytes()).hexdigest(), 'assertions': result['assertions'], 'result': result}, indent=2, sort_keys=True))
if not all(result['assertions'].values()):
    raise SystemExit(1)
