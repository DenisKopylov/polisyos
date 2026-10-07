from __future__ import annotations
import dataclasses
import hashlib
import importlib
import importlib.metadata
import json
import os
import sys
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

base = Path(sys.argv[1]).resolve()
runtime_name = sys.argv[2]
runtime_root = base / runtime_name
runtime_root.mkdir(parents=True, exist_ok=False)
checkout = Path('/Users/deniskopylov/.codex/worktrees/e02-c-canon-20261006/polisyos').resolve()
archive_source = (base / 'source').resolve()
source_census = json.loads((base / 'source-input-census.json').read_text())
artifact_census = json.loads((base / 'artifact-census-corrected.json').read_text())
source_hashes = {row['path']: row['sha256'] for row in source_census['files']}
wheel_rows = {row['wheel_path']: row for row in artifact_census['wheel_source_member_map']}

sys_path_before = list(sys.path)
if any(str(checkout) in entry or str(archive_source) in entry for entry in sys_path_before):
    raise AssertionError('source checkout/archive leaked onto isolated sys.path before imports')

import polisyos
from pydantic import BaseModel

module_names = (
    'polisyos.ir.artifacts.io',
    'polisyos.ir.artifacts.contracts',
    'polisyos.ir.model_layer.canon',
    'polisyos.core.artifacts.ir_adapter',
    'polisyos.core.artifacts.write_contract',
    'polisyos.core.artifacts.store',
    'polisyos.fabric.entity_resolution.store',
    'polisyos.fabric.entity_resolution.models',
    'polisyos.ir.analytics.ncm',
    'polisyos.runtime.quality.generation_source',
)
modules = {name: importlib.import_module(name) for name in module_names}
site_roots = [Path(path).resolve() for path in __import__('site').getsitepackages()]
package_file = Path(polisyos.__file__).resolve()
site_root = next((root for root in site_roots if package_file.is_relative_to(root)), None)
assert site_root is not None, f'polisyos origin not in venv site-packages: {package_file}'
module_origins: dict[str, dict[str, Any]] = {}
for name, module in modules.items():
    path = Path(module.__file__).resolve()
    assert path.is_relative_to(site_root), f'{name} did not import from site-packages: {path}'
    assert not path.is_relative_to(checkout) and not path.is_relative_to(archive_source), f'{name} imported from source'
    wheel_path = path.relative_to(site_root).as_posix()
    row = wheel_rows.get(wheel_path)
    assert row is not None, f'{name} source member has no exact wheel mapping: {wheel_path}'
    actual_sha = hashlib.sha256(path.read_bytes()).hexdigest()
    assert actual_sha == row['sha256'] == row['source_sha256'], f'{name} installed/wheel/archive bytes differ'
    module_origins[name] = {
        'module_file': str(path), 'wheel_path': wheel_path, 'installed_sha256': actual_sha,
        'wheel_sha256': row['sha256'], 'archive_source_path': row['source_path'],
        'archive_source_sha256': source_hashes[row['source_path']], 'byte_match': True,
    }
sys_path_after_imports = list(sys.path)
assert sys_path_before == sys_path_after_imports, 'imports mutated sys.path'

from polisyos.core.artifacts import ArtifactOwnershipError, ArtifactWriteOptions, FileSystemCAS, InputRef as CoreInputRef, ProducerInfo, SchemaInfo as CoreSchemaInfo, PutOptions as CorePutOptions
from polisyos.core.artifacts.manifest import ArtifactAuthorityInfo, ArtifactGovernanceInfo, ArtifactSameInputClosureInfo, ArtifactTenantContextInfo, CanonInfo as CoreCanonInfo, EnvInfo, WarningRecord
from polisyos.core.artifacts.ir_adapter import CoreToIRArtifactStoreAdapter
import polisyos.core.artifacts.ir_adapter as adapter_module
from polisyos.core.security.tenant_context import tenant_scope
from polisyos.ir.artifacts.contracts import StorePutOptions
from polisyos.ir.artifacts.io import get_json_artifact, put_json_artifact
from polisyos.ir.model_layer.canon import CanonSpec, CanonViolation, to_canonical_bytes
from polisyos.ir.analytics.ncm import ExogenousSpec, NCMSpec, StructuralEquation, candidate_ncm_spec_from_declaration, load_ncm_spec, load_ncm_spec_selected_view, persist_ncm_spec, persist_ncm_spec_selected_view
from polisyos.fabric.entity_resolution.models import EntityMatchCandidate, EntityMatchEvidence
from polisyos.fabric.entity_resolution.store import EntityMatchStore
from polisyos.runtime.quality.candidate_simulation import CandidateSimulationSyntheticModelDeclarationV1
from polisyos.runtime.quality.generation_source import GenerationSourceRepository
from polisyos.pdc import gy_content_hash


def normalize(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return normalize(value.model_dump(mode='json', exclude_none=False))
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return normalize({field.name: getattr(value, field.name) for field in dataclasses.fields(value)})
    if isinstance(value, dict):
        return {str(key): normalize(item) for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))}
    if isinstance(value, (tuple, list)):
        return [normalize(item) for item in value]
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat()
    if isinstance(value, Decimal):
        return {'__type__':'decimal','value':format(value,'f')}
    if hasattr(value, 'value') and isinstance(getattr(value, 'value'), (str, int, float, bool)):
        return value.value
    return value


class CountingStore:
    def __init__(self, store: FileSystemCAS):
        self.store = store
        self.byte_reads = 0
    def get_manifest(self, artifact_id: Any) -> Any:
        return self.store.get_manifest(artifact_id)
    def get_bytes(self, artifact_id: Any) -> bytes:
        self.byte_reads += 1
        return self.store.get_bytes(artifact_id)
    def __getattr__(self, name: str) -> Any:
        return getattr(self.store, name)


def field_values(manifest: Any, expected: dict[str, Any], field_names: tuple[str, ...]) -> tuple[list[str], list[dict[str, Any]]]:
    alias = {'schema': 'artifact_schema'}
    comparisons=[]
    for name in field_names:
        expected_value = expected[name]
        manifest_value = getattr(manifest, alias.get(name, name))
        left, right = normalize(expected_value), normalize(manifest_value)
        assert left == right, f'write option {name} differed after manifest readback: {left!r} != {right!r}'
        comparisons.append({'field': name, 'value': left, 'matches_manifest': True})
    return list(field_names), comparisons


def independent_core_expectations(options: StorePutOptions) -> dict[str, Any]:
    raw={field.name:getattr(options,field.name) for field in dataclasses.fields(options)}
    return {
        'kind':raw['kind'],'media_type':raw['media_type'],
        'schema':CoreSchemaInfo.model_validate(raw['schema']) if raw['schema'] is not None else None,
        'producer':ProducerInfo.model_validate(raw['producer']) if raw['producer'] is not None else None,
        'env':EnvInfo.model_validate(raw['env']) if raw['env'] is not None else None,
        'inputs':[CoreInputRef.model_validate(item) for item in (raw['inputs'] or [])] or None,
        'canon':CoreCanonInfo.model_validate(raw['canon']) if raw['canon'] is not None else None,
        'governance':ArtifactGovernanceInfo.model_validate(raw['governance']) if raw['governance'] is not None else None,
        'tenant_context':ArtifactTenantContextInfo.model_validate(raw['tenant_context']) if raw['tenant_context'] is not None else None,
        'same_input_closure':ArtifactSameInputClosureInfo.model_validate(raw['same_input_closure']) if raw['same_input_closure'] is not None else None,
        'authority':ArtifactAuthorityInfo.model_validate(raw['authority']) if raw['authority'] is not None else None,
        'warnings':[WarningRecord.model_validate(item) for item in (raw['warnings'] or [])] or None,
    }

# Exercise every immutable StorePutOptions field against the real typed Core manifest.
store_field_names = tuple(field.name for field in dataclasses.fields(StorePutOptions))
core_field_names = tuple(field.name for field in dataclasses.fields(ArtifactWriteOptions))
assert len(store_field_names) == 12, f'expected current StorePutOptions schema to expose 12 fields, saw {len(store_field_names)}'
assert store_field_names == core_field_names, f'IR/Core write-option schema drift: {store_field_names!r} vs {core_field_names!r}'
options_store = FileSystemCAS(runtime_root/'all-write-options').with_ambient_ownership_enforcement()
options_adapter = CoreToIRArtifactStoreAdapter(options_store)
with tenant_scope(None, tenant_id='tenant-a', cell_id='cell-a'):
    options_store.put_bytes(b'shared parent bytes', CorePutOptions(kind='test.parent.default', media_type='text/plain'))
    selected_parent = options_store.put_bytes(b'shared parent bytes', CorePutOptions(kind='test.parent.selected', media_type='text/plain'))
    assert selected_parent.manifest_profile_sha256 is not None
    all_options = StorePutOptions(
        kind='test.ir-adapter.options', media_type='application/json',
        schema={'name':'test.ir-adapter.options','version':'1.0'},
        producer={'component':'test-suite','version':'1.0'},
        env={'python':'3.14','platform':'test','deps_lock_hash':'sha256:'+'a'*64},
        inputs=[{'artifact_id':str(selected_parent.artifact_id),'role':'selected_parent','manifest_profile_sha256':selected_parent.manifest_profile_sha256}],
        canon={'forbid_floats':False}, governance={'classification':'internal'},
        tenant_context={'tenant_id':'tenant-a','cell_id':'cell-a'},
        same_input_closure={'closure_id':'closure-a','status':'candidate_only','run_id':'run-a','job_id':'job-a','tenant_id':'tenant-a','cell_id':'cell-a','evidence_input_refs':[str(selected_parent.artifact_id)]},
        authority={'authority_envelope_ref':'envelope://a','diagnostic_event_ref':'event://a','manifest_ref':'manifest://a','payload_sha256':'sha256:'+'b'*64},
        warnings=[{'code':'retained','msg':'keep this warning'}],
    )
    options_ref = options_adapter.put_bytes(b'{"value":1}', all_options)
    options_manifest = options_store.get_manifest(options_ref)
    independent_expectations = independent_core_expectations(all_options)
    fields_checked, option_comparisons = field_values(options_manifest, independent_expectations, core_field_names)
    options_bytes = options_store.get_bytes(options_ref)
    assert options_bytes == b'{"value":1}'
assert options_manifest.inputs[0].artifact_id == selected_parent.artifact_id
assert options_manifest.inputs[0].manifest_profile_sha256 == selected_parent.manifest_profile_sha256

# A missing required input option fails before the store persists anything.
missing_required_store = FileSystemCAS(runtime_root/'missing-required-option')
missing_required_adapter = CoreToIRArtifactStoreAdapter(missing_required_store)
missing_required = {field.name:getattr(all_options,field.name) for field in dataclasses.fields(all_options)}
missing_required.pop('media_type')
try:
    missing_required_adapter.put_bytes(b'{}', missing_required)
except (KeyError, TypeError) as exc:
    missing_required_result = {'refused':True,'error_type':type(exc).__name__,'error':str(exc),'artifact_count':len(missing_required_store.iter_artifact_ids())}
else:
    raise AssertionError('write with required media_type removed unexpectedly persisted')
assert missing_required_result['artifact_count'] == 0

# A missing optional authority remains absent; no producer invents it.
omitted_option_store = FileSystemCAS(runtime_root/'omitted-optional-option')
omitted_option_adapter = CoreToIRArtifactStoreAdapter(omitted_option_store)
omitted_options = {field.name:getattr(all_options,field.name) for field in dataclasses.fields(all_options)}
omitted_options.pop('authority')
omitted_ref = omitted_option_adapter.put_bytes(b'{"value":2}', omitted_options)
omitted_manifest = omitted_option_store.get_manifest(omitted_ref)
assert omitted_manifest.authority is None

# Property-removal mutant: preserve the typed field and schema, but remove authority at adaptation.
original_coerce = adapter_module._coerce_write_options
mutant_store = FileSystemCAS(runtime_root/'removed-authority-mutant')
mutant_adapter = CoreToIRArtifactStoreAdapter(mutant_store)
def drop_authority(opts: Any) -> Any:
    return dataclasses.replace(original_coerce(opts), authority=None)
adapter_module._coerce_write_options = drop_authority
try:
    mutant_ref = mutant_adapter.put_bytes(b'{"value":3}', all_options)
    mutant_manifest = mutant_store.get_manifest(mutant_ref)
    try:
        field_values(mutant_manifest, independent_expectations, core_field_names)
    except AssertionError as exc:
        removal_control = {'detected':True,'divergent_field':str(exc).split(' ')[2],'error':str(exc),'markers_preserved':tuple(field.name for field in dataclasses.fields(ArtifactWriteOptions)) == core_field_names,'stored_manifest_authority':normalize(mutant_manifest.authority)}
    else:
        raise AssertionError('property-removal mutant stayed green with schema markers intact')
finally:
    adapter_module._coerce_write_options = original_coerce
assert removal_control['detected'] and removal_control['divergent_field'] == 'authority'

# Ordinary persisted IR writer and reader cross the installed Core CAS boundary with exact bytes.
ordinary_store = FileSystemCAS(runtime_root/'ordinary-ir')
ordinary_adapter = CoreToIRArtifactStoreAdapter(ordinary_store)
ordinary_payload = {'amount':Decimal('12.30'),'nested':{'label':'installed-candidate'}}
ordinary_ref = put_json_artifact(ordinary_adapter, ordinary_payload, kind='test.ir-canon-profile', schema_name='test.ir-canon-profile', schema_version='1.0')
ordinary_id = ordinary_ref['artifact_id']
ordinary_bytes = ordinary_store.get_bytes(ordinary_id)
ordinary_readback = get_json_artifact(ordinary_adapter, ordinary_id)
assert ordinary_readback == ordinary_payload
assert ordinary_bytes == b'{"amount":{"_type":"decimal","value":"12.30"},"nested":{"label":"installed-candidate"}}'
ordinary_manifest = ordinary_store.get_manifest(ordinary_id)
assert ordinary_manifest.canon is not None and ordinary_manifest.canon.version == '0.2.0'

# Profile-driven depth=129 positive and profile mismatch negative.
def nested_list(depth: int) -> Any:
    value: Any = 0
    for _ in range(depth): value = [value]
    return value
depth_store = FileSystemCAS(runtime_root/'profile-depth')
depth_payload = nested_list(129)
depth_ref = put_json_artifact(depth_store, depth_payload, kind='test.ir-depth-profile', schema_name='test.ir-depth-profile', schema_version='1.0', canon_spec=CanonSpec(max_depth=129))
depth_manifest = depth_store.get_manifest(depth_ref['artifact_id'])
assert depth_manifest.canon is not None and depth_manifest.canon.max_depth == 129
assert get_json_artifact(depth_store, depth_ref['artifact_id']) == depth_payload
bounded_bytes = to_canonical_bytes(depth_payload, CanonSpec(max_depth=129))
mismatch_store = FileSystemCAS(runtime_root/'profile-depth-mismatch')
bounded_ref = mismatch_store.put_bytes(bounded_bytes, CorePutOptions(kind='test.ir-depth-profile-mismatch', media_type='application/json', canon=CoreCanonInfo(max_depth=128)))
try:
    get_json_artifact(mismatch_store, bounded_ref.artifact_id)
except CanonViolation as exc:
    assert 'max_depth=128' in str(exc)
    depth_mismatch_result = {'refused':True,'error':str(exc),'stored_profile_max_depth':mismatch_store.get_manifest(bounded_ref).canon.max_depth}
else:
    raise AssertionError('129-level payload passed a stored profile limited to 128')

# Missing / invalid profiles are rejected before the CAS byte reader is invoked.
profile_controls=[]
for label, canon_info in (
    ('missing_profile', None),
    ('unsupported_profile_name', CoreCanonInfo(name='polisyos.canon.future')),
    ('unsupported_profile_version', CoreCanonInfo(version='0.3.0')),
    ('negative_profile_depth', CoreCanonInfo(max_depth=-1)),
):
    control_store = FileSystemCAS(runtime_root/label)
    if label == 'missing_profile':
        raw_ref = control_store.put_bytes(b'{"legacy":true}', CorePutOptions(kind='ir.legacy-json', media_type='application/json', schema=CoreSchemaInfo(name='polisyos.ir.legacy-json',version='1.0')))
    else:
        raw_ref = control_store.put_bytes(b'{"value":1}', CorePutOptions(kind='test.ir-unsupported-profile',media_type='application/json',canon=canon_info))
    counting = CountingStore(control_store)
    try:
        get_json_artifact(counting, raw_ref.artifact_id)
    except CanonViolation as exc:
        assert counting.byte_reads == 0, f'{label} read content bytes before refusing'
        profile_controls.append({'case':label,'refused':True,'error':str(exc),'byte_reads':counting.byte_reads,'manifest_markers':{'kind':control_store.get_manifest(raw_ref).kind,'schema':normalize(control_store.get_manifest(raw_ref).artifact_schema),'canon':normalize(control_store.get_manifest(raw_ref).canon)}})
    else:
        raise AssertionError(f'{label} unexpectedly admitted')

# Raw Core's own JSON serializer can persist a value IR rejects: preserve this bounded bypass witness.
raw_core_store = FileSystemCAS(runtime_root/'raw-core-bypass')
raw_core_payload = {'_type':'float_hex','value':'0x1.8p+1'}
raw_core_ref = raw_core_store.put_json(raw_core_payload, CorePutOptions(kind='test.core-canon-profile',media_type='application/json'))
raw_counting = CountingStore(raw_core_store)
try:
    get_json_artifact(raw_counting, raw_core_ref.artifact_id)
except CanonViolation as exc:
    assert 'Unknown canonical _type' in str(exc)
    assert raw_counting.byte_reads == 1
    raw_core_result = {'persisted_by_core':True,'ir_refused':True,'error':str(exc),'byte_reads':raw_counting.byte_reads,'manifest_canon':normalize(raw_core_store.get_manifest(raw_core_ref).canon),'raw_bytes_sha256':hashlib.sha256(raw_core_store.get_bytes(raw_core_ref)).hexdigest()}
else:
    raise AssertionError('raw Core canonical tag unexpectedly decoded as IR')

# Foreign selected input is refused by the actual tenant-owned CAS before child persistence.
foreign_store = FileSystemCAS(runtime_root/'foreign-selected-input').with_ambient_ownership_enforcement()
foreign_adapter = CoreToIRArtifactStoreAdapter(foreign_store)
with tenant_scope(None,tenant_id='tenant-a',cell_id='cell-a'):
    foreign_store.put_bytes(b'foreign parent bytes',CorePutOptions(kind='test.foreign-parent.default',media_type='text/plain'))
    foreign_parent = foreign_store.put_bytes(b'foreign parent bytes',CorePutOptions(kind='test.foreign-parent.selected',media_type='text/plain'))
assert foreign_parent.manifest_profile_sha256 is not None
with tenant_scope(None,tenant_id='tenant-b',cell_id='cell-b'):
    try:
        foreign_adapter.put_bytes(b'child with foreign selected input',StorePutOptions(kind='test.foreign-child',media_type='application/octet-stream',inputs=[{'artifact_id':str(foreign_parent.artifact_id),'role':'foreign_parent','manifest_profile_sha256':foreign_parent.manifest_profile_sha256}]))
    except ArtifactOwnershipError as exc:
        foreign_result={'refused':True,'error':str(exc),'child_artifacts_visible_to_current_tenant':len(foreign_store.iter_artifact_ids())}
    else:
        raise AssertionError('foreign selected input was accepted')
assert foreign_result['child_artifacts_visible_to_current_tenant'] == 0

# NCM ordinary persistence/readback, then actual candidate declaration -> selected NCM view -> selected reader.
ncm_store = FileSystemCAS(runtime_root/'ncm')
ncm_spec = NCMSpec(
    endogenous_vars=['outcome'],
    exogenous_specs=[ExogenousSpec(variable='U_outcome',associated_endogenous='outcome',distribution_family='normal',distribution_params={'mean':0.0,'std':1.0})],
    structural_equations=[StructuralEquation(variable='outcome',parents=[],exogenous='U_outcome',equation_type='linear',equation_params={'intercept':1.0,'coefficients':{}})],
    is_acyclic=True,markov_condition_verified=False,independence_model='unknown',fit_method='installed_bounded_fixture',
)
ordinary_ncm_ref = persist_ncm_spec(ncm_store,ncm_spec)
ordinary_ncm = load_ncm_spec(ncm_store,ordinary_ncm_ref)
assert ordinary_ncm.model_dump(mode='json') == ncm_spec.model_dump(mode='json')

def declaration(coefficient: float) -> CandidateSimulationSyntheticModelDeclarationV1:
    fields={
        'schema_version':'policyos.runtime.candidate_simulation.synthetic_model_declaration.v1',
        'profile_config_ref':'runtime-config:candidate-simulation:fixture',
        'profile_content_hash':'sha256:'+'a'*64,
        'profile_selection_ref':'sha256:'+'b'*64,
        'target_world_slot':'cells.distress_score','outcome_variable':'cells.output',
        'target_unit_id':'synthetic_score','outcome_unit_id':'synthetic_score',
        'target_baseline':2.0,'outcome_baseline':10.0,'outcome_per_target_unit':coefficient,
        'outcome_noise_stddev':0.01,'assumption':'declared_candidate_scm_not_empirically_grounded',
    }
    draft=CandidateSimulationSyntheticModelDeclarationV1.model_construct(**fields,content_hash='sha256:'+'0'*64)
    return CandidateSimulationSyntheticModelDeclarationV1.model_validate({**fields,'content_hash':gy_content_hash(draft.model_dump(mode='json',exclude={'content_hash'}))})

selected_tenant='tenant-candidate-ncm'; selected_cell='cell-candidate-ncm'; selected_job='job-candidate-ncm'; selected_run='run-candidate-ncm'
selected_store=FileSystemCAS(runtime_root/'ncm-selected-view')
repository=GenerationSourceRepository(selected_store)
decl=declaration(3.0); other_decl=declaration(2.0)
selected_spec=candidate_ncm_spec_from_declaration(decl)
with tenant_scope(None,tenant_id=selected_tenant,cell_id=selected_cell):
    default_options=modules['polisyos.runtime.quality.generation_source']._candidate_simulation_write_options(kind='ir.ncm_spec',schema_name='ir.ncm_spec',schema_version='1.0',job_id=selected_job,run_id=selected_run,tenant_id=selected_tenant,cell_id=selected_cell,source_ref=decl.profile_content_hash)
    default_bytes=to_canonical_bytes(selected_spec.model_dump(mode='json'),CanonSpec(forbid_floats=False,exclude_none=False))
    default_view_ref=selected_store.put_bytes(default_bytes,default_options)
    decl_ref=repository.persist_candidate_model_declaration(declaration=decl,job_id=selected_job,run_id=selected_run,tenant_id=selected_tenant,cell_id=selected_cell)
    selected_ref=repository.persist_candidate_ncm_selected_view(ncm_spec=selected_spec,declaration_ref=decl_ref,job_id=selected_job,run_id=selected_run,tenant_id=selected_tenant,cell_id=selected_cell,profile_content_hash=decl.profile_content_hash)
    selected_manifest=selected_store.get_manifest(selected_ref)
    selected_ncm=load_ncm_spec_selected_view(selected_store,selected_ref,expected_tenant_id=selected_tenant,expected_cell_id=selected_cell,expected_declaration_ref=decl_ref)
    assert selected_ncm.model_dump(mode='json') == selected_spec.model_dump(mode='json')
    assert selected_ref.manifest_profile_sha256 is not None
    assert len(selected_manifest.inputs)==1 and str(selected_manifest.inputs[0].artifact_id)==str(decl_ref.artifact_id)
    assert selected_manifest.inputs[0].role=='candidate_model_declaration'
    assert selected_manifest.inputs[0].manifest_profile_sha256==decl_ref.manifest_profile_sha256
    other_ref=repository.persist_candidate_model_declaration(declaration=other_decl,job_id=selected_job,run_id=selected_run,tenant_id=selected_tenant,cell_id=selected_cell)
    try:
        load_ncm_spec_selected_view(selected_store,selected_ref,expected_tenant_id=selected_tenant,expected_cell_id=selected_cell,expected_declaration_ref=other_ref)
    except ValueError as exc:
        assert 'declaration_lineage_mismatch' in str(exc)
        ncm_lineage_negative={'refused':True,'error':str(exc)}
    else:
        raise AssertionError('NCM selected view accepted a foreign declaration ref')

# EntityMatchStore owns candidate/override production and replays both through profile-aware IR reads.
entity_store=FileSystemCAS(runtime_root/'entity-match')
entity_owner=EntityMatchStore(entity_store)
candidate=EntityMatchCandidate(
    match_id='installed-match-1',left_entity_id='worldbank:UA',right_entity_id='catalog:UA',
    left_source='worldbank',right_source='catalog',confidence=0.85,
    method='bounded-installed-fixture',evidence=[EntityMatchEvidence(evidence_type='identifier',detail='same country code',score=0.85)],
)
candidate_ref=entity_owner.persist_candidates([candidate],method='bounded-installed-fixture',metadata={'scope':'installed-candidate'})
candidate_batch=entity_owner.load_candidates(candidate_ref.artifact_id)
assert candidate_batch.candidates[0].match_id==candidate.match_id
assert entity_store.get_manifest(candidate_ref).canon.forbid_floats is False
override_ref=entity_owner.persist_override(candidate,status='rejected',actor='operator-1',reason='fixture rejection for replay')
override=entity_owner.load_override(override_ref.artifact_id)
audit_rows=entity_owner.list_override_audit()
assert override.candidate.override_status=='rejected' and override.audit.actor=='operator-1'
assert len(audit_rows)==1 and audit_rows[0][0]==str(override_ref.artifact_id)

# Capture the installed base profile without interpreting it as a fresh wheel dependency resolution.
dists=sorted((dist.metadata.get('Name','') or '').lower().replace('_','-') for dist in importlib.metadata.distributions())
def has_dist(name: str) -> bool:
    try: importlib.metadata.distribution(name); return True
    except importlib.metadata.PackageNotFoundError: return False

result={
 'schema':'policyos.canon.installed_package_probe.v1','probe_id':runtime_name,
 'source':{'commit':source_census['git_commit'],'tree':source_census['git_tree'],'archive_sha256':source_census['archive_sha256'],'archive_file_count':source_census['archive_file_count'],'product_file_count':source_census['product_root_file_count']},
 'wheel':artifact_census['summary']['wheel'],
 'runtime':{'executable':sys.executable,'python':sys.version,'isolated':bool(sys.flags.isolated),'no_bytecode':bool(sys.dont_write_bytecode),'cwd':os.getcwd(),'sys_path_before':sys_path_before,'sys_path_after_imports':sys_path_after_imports,'sys_path_unchanged':sys_path_before==sys_path_after_imports,'site_root':str(site_root),'module_origins':module_origins,'installed_distribution_count':len(dists),'installed_distributions':dists,'policy_engine_version':importlib.metadata.version('policy-engine'),'pytest_present':has_dist('pytest'),'hnswlib_present':has_dist('hnswlib'),'PYTHONPATH':os.environ.get('PYTHONPATH'),'VIRTUAL_ENV':os.environ.get('VIRTUAL_ENV')},
 'all_write_options':{'schema_field_names':list(store_field_names),'core_field_names':list(core_field_names),'count':len(fields_checked),'all_twelve_fields_match_typed_core_manifest':True,'comparisons':option_comparisons,'selected_input_ref':{'artifact_id':str(selected_parent.artifact_id),'role':options_manifest.inputs[0].role,'manifest_profile_sha256':options_manifest.inputs[0].manifest_profile_sha256},'child_ref':str(options_ref.artifact_id),'child_bytes_sha256':hashlib.sha256(options_bytes).hexdigest(),'child_bytes':options_bytes.decode('utf-8'),'child_manifest':normalize(options_manifest)},
 'missing_required_option':missing_required_result,
 'omitted_optional_option':{'case':'authority omitted from mapping input','persisted_authority':normalize(omitted_manifest.authority),'expected_default_none':True},
 'property_removal_control':removal_control,
 'ordinary_ir_roundtrip':{'ref':ordinary_id,'persisted_bytes':ordinary_bytes.decode('utf-8'),'bytes_sha256':hashlib.sha256(ordinary_bytes).hexdigest(),'manifest_canon':normalize(ordinary_manifest.canon),'readback':normalize(ordinary_readback),'equal':True},
 'depth_profile':{'requested_depth':129,'persisted_depth':depth_manifest.canon.max_depth,'positive_readback':True,'mismatch_negative':depth_mismatch_result},
 'profile_refusals_before_bytes':profile_controls,
 'raw_core_bypass':raw_core_result,
 'foreign_selected_input':foreign_result,
 'ncm':{'ordinary_ref':str(ordinary_ncm_ref.artifact_id),'ordinary_readback_equal':True,'seeded_view_ref':str(default_view_ref.artifact_id),'seeded_view_profile_sha256':default_view_ref.manifest_profile_sha256,'declaration_ref':str(decl_ref.artifact_id),'declaration_profile_sha256':decl_ref.manifest_profile_sha256,'selected_ncm_ref':str(selected_ref.artifact_id),'selected_ncm_profile_sha256':selected_ref.manifest_profile_sha256,'selected_input':normalize(selected_manifest.inputs[0]),'selected_readback_equal':True,'lineage_mismatch_control':ncm_lineage_negative},
 'entity_match':{'candidate_ref':str(candidate_ref.artifact_id),'candidate_count':len(candidate_batch.candidates),'candidate_id':candidate_batch.candidates[0].match_id,'candidate_profile':normalize(entity_store.get_manifest(candidate_ref).canon),'override_ref':str(override_ref.artifact_id),'override_status':override.candidate.override_status,'override_actor':override.audit.actor,'audit_rows':len(audit_rows)},
}
out=base/(runtime_name+'-result.json')
out.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
print(json.dumps({'status':'PASS','source_commit':result['source']['commit'],'wheel_sha256':result['wheel']['sha256'],'site_root':str(site_root),'isolated':bool(sys.flags.isolated),'sys_path_unchanged':True,'write_option_count':len(fields_checked),'depth129':True,'profile_zero_read_cases':len(profile_controls),'foreign_refused':foreign_result['refused'],'removal_control_detected':removal_control['detected'],'ncm_selected_reader':True,'entity_candidate_override_readers':True,'result_path':str(out),'result_sha256':hashlib.sha256(out.read_bytes()).hexdigest()},sort_keys=True))
