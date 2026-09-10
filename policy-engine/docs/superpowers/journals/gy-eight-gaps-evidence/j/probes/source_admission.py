"""Run actual source owners over the complete pinned metric-binding denominator."""
from collections import Counter
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import duckdb

from polisyos.data_forge import read_api
from polisyos.runtime.quality.adapter_contracts import ConnectorAdmissionGate, DataRequirementAdmissionGate
from polisyos.runtime.quality.data_forge_binding import source_requirement_for_catalog_binding

ROOT = Path.cwd()
prior = json.loads(json.loads((ROOT / '_build/gy-gaps/j/substrate-census-complete.json').read_text())['stdout'])
path = ROOT / prior['source']['path']
constructs = prior['request']['constructs']
fixture = next(x for x in json.loads((ROOT / 'architecture/policy_design_case/layer3_gy_slice0_fixture_manifest.json').read_text())['fixtures'] if x['fixture_id'] == 'ua_msme_credit_worldbank_measurement')
scope = SimpleNamespace(**{key: fixture[key] for key in ('fixture_id', 'construct_scope_query', 'jurisdiction', 'population', 'time_horizon')})
def digest():
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()
before = digest()
assert before == prior['source']['sha256']
connection = duckdb.connect(str(path), read_only=True)
try:
    cursor = connection.execute('SELECT * FROM ds_metric_bindings WHERE metric_id = ANY(?) ORDER BY metric_id,dataset_id,distribution_id', [constructs])
    names = [x[0] for x in cursor.description]
    bindings = [dict(zip(names, row, strict=True)) for row in cursor.fetchall()]
    identities = {(x['metric_id'], x['dataset_id'], x['distribution_id']) for x in bindings}
    independent = {tuple(x) for x in connection.execute('SELECT metric_id,dataset_id,distribution_id FROM ds_metric_bindings WHERE metric_id IN (SELECT UNNEST(?))', [constructs]).fetchall()}
    count = connection.execute('SELECT COUNT(*) FROM ds_metric_bindings WHERE metric_id = ANY(?)', [constructs]).fetchone()[0]
    assert identities == independent and len(bindings) == len(identities) == count
finally:
    connection.close()

registry = read_api.catalog.DatasetRegistry(path)
lookups = registry.find_datasets_for_variables_bulk(constructs, 'UA', (2020, 2024))
assert set(lookups) == set(constructs)
graph = read_api.catalog.DatasetCatalogGraph(path, ROOT / '_build/gy-gaps/j/no-vector-index')
results = []
try:
    for item in bindings:
        identity = [item['metric_id'], item['dataset_id'], item['distribution_id']]
        selected = graph.get_dataset(item['dataset_id'])
        if selected is None:
            results.append({'identity': identity, 'status': 'ambiguous', 'reason': 'catalog_owner_get_dataset_returned_absent'})
            continue
        distribution = [x.model_dump(mode='json') for x in graph.get_distributions(item['dataset_id']) if x.id == item['distribution_id']]
        if len(distribution) != 1:
            results.append({'identity': identity, 'status': 'ambiguous', 'reason': 'exact_distribution_not_established', 'matches': len(distribution)})
            continue
        requirement, _ = source_requirement_for_catalog_binding(manifest=scope, selected=selected, distributions=distribution, connector_type=item['connector_id'])
        source_gate = DataRequirementAdmissionGate().evaluate(requirement)
        connector_gate = ConnectorAdmissionGate().evaluate(item['connector_id'])
        results.append({'identity': identity, 'source_dataset_id': selected.source_dataset_id, 'title': selected.title, 'source_status': source_gate.status, 'source_failures': source_gate.failed_preconditions, 'connector_status': connector_gate.status, 'connector_failures': connector_gate.failed_preconditions, 'actual_source_coverage': selected.coverage.model_dump(mode='json') if hasattr(selected.coverage, 'model_dump') else selected.coverage, 'status': 'measured'})
finally:
    graph.close()
assert {tuple(x['identity']) for x in results} == identities
assert digest() == before
print(json.dumps({
    'source': prior['source'], 'request': prior['request'],
    'binding_identity_reconciliation': {'complete_table_denominator': prior['denominators']['ds_metric_bindings']['row_denominator'], 'selected_construct_binding_denominator': count, 'independent_sql_identities': len(independent), 'measured_result_identities': len(results), 'symmetric_difference': sorted(identities ^ independent)},
    'lookup_owner': 'polisyos.data_forge.read_api.catalog.DatasetRegistry.find_datasets_for_variables_bulk',
    'complete_requested_construct_lookups': {key: [x.model_dump(mode='json', exclude={'mapping_confidence'}) for x in values] for key, values in lookups.items()},
    'source_gate_owner': 'polisyos.runtime.quality.adapter_contracts.DataRequirementAdmissionGate',
    'complete_source_gate_results': results,
    'limitations': ['Read-only owner admission; no network fetch, source metadata reissue, policy rate, positive correspondence or calibration number.', 'Lookup absence is absence from the actual admitted alignment relation, not proof that no raw corpus contains relevant observations.'],
}, indent=2, default=str))
