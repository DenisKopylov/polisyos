"""Read all pinned-construct observation custody and actual aligned dataset evidence."""
from collections import Counter
import hashlib
import json
from pathlib import Path

import duckdb

ROOT = Path.cwd()
prior = json.loads(json.loads((ROOT / '_build/gy-gaps/j/substrate-census-complete.json').read_text())['stdout'])
path = ROOT / prior['source']['path']
constructs = prior['request']['constructs']
def digest():
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()
def rows(connection, sql, args=()):
    result = connection.execute(sql, args)
    names = [x[0] for x in result.description]
    return [dict(zip(names, row, strict=True)) for row in result.fetchall()]
before = digest()
assert before == prior['source']['sha256']
connection = duckdb.connect(str(path), read_only=True)
try:
    observations = rows(connection, 'SELECT * FROM ds_observations WHERE canonical_var IN (SELECT UNNEST(?)) ORDER BY observation_id', [constructs])
    actual_ids = {x['observation_id'] for x in observations}
    previous_ids = {x['identity'] for x in prior['required_observation_rows']}
    independently_selected = {x[0] for x in connection.execute('SELECT observation_id FROM ds_observations WHERE canonical_var = ANY(?)', [constructs]).fetchall()}
    independent_count = connection.execute('SELECT COUNT(*) FROM ds_observations WHERE canonical_var = ANY(?)', [constructs]).fetchone()[0]
    assert actual_ids == previous_ids == independently_selected
    assert len(observations) == len(actual_ids) == independent_count
    groups = Counter((x['dataset_id'], x['raw_variable'], x['canonical_var'], x['acquisition_method'], x['source_watermark'], x['dataset_version'], x['condition_json']) for x in observations)
    sql_groups = Counter({tuple(x[:-1]): x[-1] for x in connection.execute('SELECT dataset_id, raw_variable, canonical_var, acquisition_method, source_watermark, dataset_version, condition_json, COUNT(*) FROM ds_observations WHERE canonical_var = ANY(?) GROUP BY ALL', [constructs]).fetchall()})
    assert groups == sql_groups
    dataset_ids = sorted({x['dataset_id'] for x in observations})
    selected = {}
    for table, field in [('ds_datasets', 'id'), ('ds_registry_datasets', 'dataset_id'), ('ds_distributions', 'dataset_id'), ('ds_variable_alignments', 'dataset_id'), ('ds_alignment_audit', 'dataset_id'), ('ds_metric_bindings', 'dataset_id')]:
        selected[table] = rows(connection, f'SELECT * FROM {table} WHERE {field} = ANY(?)', [dataset_ids])
    ua = [x for x in observations if x['country_code'] == 'UA' and 2020 <= x['year'] <= 2024]
    independent_ua = {x[0] for x in connection.execute("SELECT observation_id FROM ds_observations WHERE canonical_var = ANY(?) AND country_code='UA' AND year BETWEEN 2020 AND 2024", [constructs]).fetchall()}
    assert {x['observation_id'] for x in ua} == independent_ua
    report = {
        'source': prior['source'],
        'observation_identity_reconciliation': {'full_table_denominator': prior['denominators']['ds_observations']['row_denominator'], 'selected_denominator': independent_count, 'previous_streamed_ids': len(previous_ids), 'independent_sql_ids': len(independently_selected), 'symmetric_difference': sorted(actual_ids ^ independently_selected)},
        'custody_groups': [{'dataset_id': k[0], 'raw_variable': k[1], 'canonical_var': k[2], 'acquisition_method': k[3], 'source_watermark': k[4], 'dataset_version': k[5], 'condition_json': k[6], 'rows': n} for k, n in groups.items()],
        'ua_2020_2024_rows': ua,
        'ua_scope_identity_reconciliation': {'streamed': len(ua), 'independent_sql': len(independent_ua), 'symmetric_difference': sorted({x['observation_id'] for x in ua} ^ independent_ua)},
        'all_selected_dataset_evidence': selected,
        'limitations': ['Actual source metadata and recorded values are inspected without promoting alignment confidence to correspondence authority.', 'No keyword absence is a supply finding; no fixture enters a canonical run.'],
    }
finally:
    connection.close()
assert digest() == before
print(json.dumps(report, indent=2, default=str))
