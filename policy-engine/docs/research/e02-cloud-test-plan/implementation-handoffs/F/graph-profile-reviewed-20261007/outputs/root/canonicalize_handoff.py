from pathlib import Path
import hashlib
import json
import shlex
import subprocess

ROOT = Path('/workspace/e02-F-closeout-20261006')
SCRATCH = Path('/tmp/e02-F-graph-profile-20261007')
REL = Path('policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/F/graph-profile-20261007.json')
path = ROOT / REL
j = json.loads(path.read_text())
assert j['schema'] == 'e02.F.property_slice_handoff.v1'
original = subprocess.check_output(['git', 'show', 'e89d449acc6eedb1629c42c428689f7c578fce26:' + str(REL)], cwd=ROOT)
j['previous_custom_receipt'] = {'git_ref': 'e89d449acc6eedb1629c42c428689f7c578fce26', 'path': str(REL), 'bytes': len(original), 'sha256': hashlib.sha256(original).hexdigest(), 'role': 'Complete deciding outputs and source were already valid; canonical HANDOFF field names absent, forward receipt-only correction'}
j['schema'] = 'policyos.e02.implementation_handoff.v1'
j['slice'] = 'graph-profile-20261007'
j['closure_ids'] = []
j['bundle_ids'] = ['CAU-01', 'CAU-04', 'GRF-03', 'FRY-01']
j['slice_base_sha'] = j['slice_base']['sha']
j['implementation_commit_bindings'] = j['implementation_commits']
j['implementation_commits'] = [x['sha'] for x in j['implementation_commit_bindings']]
j['candidate_sha'] = j['candidate']['sha']
j['candidate_tree_sha'] = j['candidate']['tree']
j['pull_request'] = j['PR']
j['changed_paths'] = [x['path'] for x in j['full_source_footprint']['paths']]
j['baseline_cells'] = []
j['baseline_cells_scope'] = 'No old baseline cell automatically assigned to this property follow-up; actual25c runtime regression and G nativeMGraph witness are the deciding baselines. Original35 bindings/receipts and importer verification remain separate.'
j['predicate_basis'] = 'recomputed'
j['capability_state_or_finding_state'] = 'bounded_reconciliation_property_code_ready; original35_F_states_unchanged; G_acceptance_not_issued'
j['limitations_and_next_owner'] = [
    'B214 remainslimited: A/C/F tracked graph-family/identified-versus-conditional/partial outputs and authority projection with completion-distinguishing query.',
    'B56 remainslimited/UNRUN: Runtime/Scientist canonical shared admission/cap and full workload/input roster; G local active/wait/wall/RSS/all-fold/CAS/readback after packet.',
    'Reconciliation only; no new MGraph/PAG/CPDAG/general/temporal identification support. OriginalMGraph remains readable and is refused by this static route.',
    'New rebuilt-sdistUNRUN; old51991/91 source-bound qualification unchanged, not new4ee whole-head proof.',
    'Selected genuine3.12/DoWhy0.14 worker passes; optionalinprocess3.14 DoWhy/EconML and scientific/Runtime authority positivesUNRUN.',
    'Global scannerERROR−9twice/Ruff103FAIL/publicsurface38FAIL and P41not_established preserved. New benchmarkRuff2T201FAIL not establishedinherited.',
]
p = j['property']
p['statement'] = p['invariant']
p['runtime_path'] = ['scored schema-valid build_mgraph or same-formADMG producer', 'source-typed original CAS graph artifact', 'actual MethodRegistry/run_job and ReconcileCausalGraphNode', 'refusal without reconciled publication or supported DAG/ADMG CAS → distinct-process actual extractor/reader']
p['proxy_divergence'] = 'MGraph may have valid endpoint pairs, valid schema, metadata and synthetic DATAconfidence0.9; the old static endpoint/cutoff proxy accepts and retypes ADMG while actual missingness extractor rejects. Declared semantic graph-family guard refuses before transformations.'
p['negative_controls'] = [p['negative'], 'Missing/stale/current-content mutation refs and unresolved/lagged static inputs remain typed refusals; exact same-shapeADMG and known reverse positives remain admitted.']

def read(rel):
    return json.loads((SCRATCH / rel).read_text())

worker = read('worker/frozen-4ee-native/wait4-replay/frozen-native.spec.json')
specs = [
    j['exact_root_commands'][0],
    read('root/final-wave/natural-experiments.execution.json'),
    {'argv': worker['argv'], 'cwd': worker['cwd'], 'environment': worker['environment_overrides']},
    read('api-review/combined4ee/graph-untouched.execution.json'),
    read('api-review/combined4ee/graph-removed.execution.json'),
    read('foundry/installed-4ee/native.execution.json'),
    read('foundry/installed-4ee/removal.execution.json'),
    read('api-review/combined4ee/b204.execution.json'),
    None, None,
]
for i, (check, spec) in enumerate(zip(j['checks'], specs, strict=True)):
    check['target_sha'] = j['candidate_sha']
    check['outcome'] = check['check']
    check['input_closure'] = {'source_sha': j['candidate_sha'], 'source_tree': j['candidate_tree_sha'], 'fixture_profile': 'Synthetic only; exact full test inputs/commands/guards captured in evidence_transport; no production inputs', 'full_output_manifest': j['evidence_transport']['path'], 'original_criterion_bindings': j['affected_IDs'], 'no_authority_positive': True}
    if spec is None:
        check['command'] = 'UNRUN: ' + check['name']
        check['environment'] = {'profile': 'not_executed', 'limitation': check['reason']}
        check['output'] = 'UNRUN: ' + check['reason']
    else:
        check['command'] = shlex.join(spec['argv'])
        check['cwd'] = spec['cwd']
        check['environment'] = spec.get('environment', spec.get('env_overrides', {}))
        check['output_ref'] = check['output']
        check['output'] = check['output_ref']['path']
    if i == 2:
        check['environment']['backend_profile'] = worker['native_backend_profile']

# The fixed quality/source commands also carry canonical reader fields.
for check in j['exact_root_commands']:
    check['command'] = shlex.join(check['argv'])
    check['target_sha'] = check['target_sha']
    check['input_closure'] = {'source_sha': j['candidate_sha'], 'source_tree': j['candidate_tree_sha'], 'denominator': check['argv'], 'no_P41_inherited_attribution': True}
    check['outcome'] = check['check_result']
    check['output'] = check['stdout']

g = subprocess.check_output(['git', 'rev-parse', 'origin/codex/e02-integration'], cwd=ROOT, text=True).strip()
old_g = j['G_dependency']['sha']
changed = subprocess.check_output(['git', 'diff', '--name-only', old_g, g], cwd=ROOT, text=True).splitlines()
decision_path = 'policy-engine/docs/research/e02-cloud-test-plan/integration/reviews/2026-10-07-F35-decision/README.md'
j['fresh_remote_checkpoint'] = {'sha': g, 'tree': subprocess.check_output(['git', 'rev-parse', g + '^{tree}'], cwd=ROOT, text=True).strip(), 'previous_dependency_pin': old_g, 'previous_is_ancestor': subprocess.run(['git', 'merge-base', '--is-ancestor', old_g, g], cwd=ROOT).returncode == 0, 'delta_paths': changed, 'product_delta_paths': [x for x in changed if not x.startswith('policy-engine/docs/')], 'F35_decision_blob_unchanged': subprocess.check_output(['git', 'rev-parse', old_g + ':' + decision_path], cwd=ROOT) == subprocess.check_output(['git', 'rev-parse', g + ':' + decision_path], cwd=ROOT), 'G_ref_read_only': True, 'not_an_accepted_or_merged_G_candidate': True}
mandatory = ['schema', 'unit', 'slice', 'closure_ids', 'bundle_ids', 'slice_base_sha', 'implementation_commits', 'candidate_tree_sha', 'branch', 'pull_request', 'changed_paths', 'baseline_cells', 'checks', 'property', 'predicate_basis', 'capability_state_or_finding_state', 'limitations_and_next_owner']
assert all(k in j for k in mandatory)
assert all(all(k in check for k in ['command', 'target_sha', 'environment', 'input_closure', 'outcome', 'output']) for check in j['checks'])
path.write_text(json.dumps(j, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'canonical_schema': j['schema'], 'check_count': len(j['checks']), 'freshG': g, 'G_delta_count': len(changed), 'G_product_delta_count': len(j['fresh_remote_checkpoint']['product_delta_paths'])}))
