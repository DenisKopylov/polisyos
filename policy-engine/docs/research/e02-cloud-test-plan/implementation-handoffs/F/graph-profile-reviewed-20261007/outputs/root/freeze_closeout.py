from pathlib import Path
import gzip
import hashlib
import json
import shlex
import subprocess

ROOT = Path('/workspace/e02-F-closeout-20261006')
SCRATCH = Path('/tmp/e02-F-graph-profile-20261007')
E02 = Path('policy-engine/docs/research/e02-cloud-test-plan')
PACK = E02 / 'implementation-handoffs/F/graph-profile-reviewed-20261007'
PRIMARY = E02 / 'implementation-handoffs/F/graph-profile-reviewed-20261007.json'
LEDGER = '3d43eb459eec1f346571306647e5dbc68f32f076'
PRODUCT = '4ee2f2a4f1d9c4d42c6e5ec7f85f973e07358f0d'
RECEIPT = '248497d27aa7951492c9a6d12c3c3493f3c246ec'

def sha(data):
    return hashlib.sha256(data).hexdigest()

def bind(ref, path):
    data = subprocess.check_output(['git', 'show', ref + ':' + str(path)], cwd=ROOT)
    return {'git_ref': ref, 'path': str(path), 'bytes': len(data), 'sha256': sha(data)}

paths = []
for group in ['economics-review/ledger3e', 'economics-review/ledger3d']:
    paths.extend(p for p in (SCRATCH / group).iterdir() if p.is_file())
paths.append(SCRATCH / 'economics-review/review_final_ledger.py')
for rel in [
    'root/canonicalize_handoff.py', 'root/update_ledger.py', 'root/update_canonical_bindings.py',
    'root/freeze_closeout.py', 'root/final-cloud-runtime.json',
    'root/final-custody-facts.json',
    'root/final-workspace-admission.json', 'root/final-workspace-admission.stderr', 'root/final-workspace-admission.exitcode',
    'root/final-component-remote-readback.stdout', 'root/final-component-remote-readback.stderr', 'root/final-component-remote-readback.exitcode',
    'root/evidence-ledger-push.stdout', 'root/evidence-ledger-push.stderr', 'root/evidence-ledger-push.exitcode',
    'root/canonical-ledger-push.stdout', 'root/canonical-ledger-push.stderr', 'root/canonical-ledger-push.exitcode',
    'root/final-fetch-origin.stdout', 'root/final-fetch-origin.stderr', 'root/final-fetch-G.stdout', 'root/final-fetch-G.stderr',
    'root/receipt-byte-preservation-diff-check.stdout', 'root/receipt-byte-preservation-diff-check.stderr',
    'root/ledger-diff-check.stdout', 'root/ledger-diff-check.stderr', 'root/pre-closeout-status.stdout',
]:
    paths.append(SCRATCH / rel)
review_path = SCRATCH / 'economics-review/ledger3d/review.json'
review = json.loads(review_path.read_text())
assert review['source'] == LEDGER and review['source_tree'] == '18a07f2d4de206cdd7c0b85532b2201d8ae279e8'
assert review['verdict'] == 'GO_BOUNDED_CANONICAL_LEDGER_AND_TRANSPORT'
assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip() == LEDGER
records = []
for path in sorted(set(paths)):
    data = path.read_bytes()
    # Raw patches/logs retain exact whitespace as a lossless binary transport.
    compress = len(data) > 60000 or path.suffix in {'.patch', '.diff', '.txt'} or path.name.endswith(('.stdout', '.stderr'))
    stored = gzip.compress(data, compresslevel=9, mtime=0) if compress else data
    rel = PACK / 'outputs' / path.relative_to(SCRATCH)
    if compress: rel = Path(str(rel) + '.gz')
    target = ROOT / rel; target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(stored)
    assert (gzip.decompress(stored) if compress else stored) == data
    records.append({'original_path': str(path), 'path': str(rel), 'encoding': 'gzip' if compress else 'identity', 'stored_bytes': len(stored), 'stored_sha256': sha(stored), 'decoded_bytes': len(data), 'decoded_sha256': sha(data)})
manifest = {'schema': 'e02.F.lossless_review_transport.v1', 'unit': 'F', 'ledger_sha': LEDGER, 'product_sha': PRODUCT, 'files': records, 'file_count': len(records), 'stored_bytes': sum(r['stored_bytes'] for r in records), 'decoded_bytes': sum(r['decoded_bytes'] for r in records), 'law': 'Root freezes the actual completed independent review and finite full metadata outputs; no source/environment copy or numerical rerun.'}
mpath = ROOT / PACK / 'artifact-transports.json'
mpath.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
def evidence(rel):
    return next(r for r in records if r['original_path'] == str(SCRATCH / rel))
result = {
    'schema': 'policyos.e02.implementation_handoff.v1', 'unit': 'F', 'slice': 'graph-profile-reviewed-20261007',
    'closure_ids': [], 'bundle_ids': ['CAU-01', 'CAU-04', 'GRF-03', 'FRY-01'],
    'slice_base_sha': '25cdea9064ddea2c3a812fd68670076bd4b088cb',
    'implementation_commits': ['3e5985076cee7e5dfa5627addc59d4aac6532a8a', RECEIPT, LEDGER],
    'candidate_sha': LEDGER, 'candidate_tree_sha': '18a07f2d4de206cdd7c0b85532b2201d8ae279e8',
    'product_source': {'sha': PRODUCT, 'tree': '551d4e760dc1168f6ad8182c9b176f00e94a2281', 'no_numerical_or_runtime_change_after_source_freeze': True},
    'branch': 'codex/e02-F-closeout-20261006', 'pull_request': 'https://github.com/DenisKopylov/polisyos/pull/65',
    'changed_paths': subprocess.check_output(['git', 'diff', '--name-only', 'e89d449acc6eedb1629c42c428689f7c578fce26', LEDGER], cwd=ROOT, text=True).splitlines(),
    'baseline_cells': [], 'canonical_source_handoff': bind(RECEIPT, E02 / 'implementation-handoffs/F/graph-profile-20261007.json'),
    'complete35_ledger': bind(LEDGER, E02 / 'implementation-handoffs/F/continuation-transfer-20261007/index.json'),
    'complete35_report': bind(LEDGER, E02 / 'implementation-handoffs/F/continuation-transfer-20261007/REPORT.md'),
    'independent_review': {'reviewer': 'F economics helper; not writer of graph/benchmark/docs/rootledger', 'verdict': review['verdict'], 'output': evidence('economics-review/ledger3d/review.json'), 'metadata_only': True, 'no_new_independent_numerical_claim': True},
    'checks': [
        {'command': 'Recorded executed audit commands: ' + evidence('economics-review/ledger3d/commands.json')['path'], 'target_sha': LEDGER, 'environment': 'Read-only Python metadata audit, exact Git refs/current source/transport; no numerical backend or production data', 'input_closure': '35ID/17bundle/36binding; full TSV/cards and exact primary/per-ID/513stored+decoded outputs; no sampling', 'outcome': 'PASS', 'output': evidence('economics-review/ledger3d/review.json')['path'], 'commands_full': evidence('economics-review/ledger3d/commands.json'), 'command_scope': '134 exact constituent Git argv/exitcode/output-size-and-hash records; launcher not inferred from script filename', 'result': 'Six focused appends and29 complete byte-identical per-ID files; old component/check/F/G fields preserved; canonical minimumfields/all10checks valid; seven corrupt-metadata adversaries refused'},
        {'command': 'git diff --check e89d449acc6eedb1629c42c428689f7c578fce26 ' + LEDGER, 'target_sha': LEDGER, 'environment': 'Exact14authored document delta, separate from old source and raw logs', 'input_closure': '14currentledger/prose/source-order/local-packet paths', 'outcome': 'PASS', 'output': evidence('economics-review/ledger3d/authored14-diff-check.stdout.txt')['path']},
        {'command': 'git diff --check 25cdea9064ddea2c3a812fd68670076bd4b088cb ' + PRODUCT, 'target_sha': PRODUCT, 'environment': 'Exact10source/test/benchmark/docs/fragment implementation delta', 'input_closure': 'All10changed source paths', 'outcome': 'PASS', 'output': evidence('economics-review/ledger3d/source10-diff-check.stdout.txt')['path']},
        {'command': 'git diff --check 25cdea9064ddea2c3a812fd68670076bd4b088cb ' + LEDGER, 'target_sha': LEDGER, 'environment': 'Complete all-path raw receipt delta; saved text includes original patch/log whitespace', 'input_closure': 'Full exact candidate diff including513raw artifacts, no exclude/whitelist', 'outcome': 'FAIL', 'output': evidence('economics-review/ledger3d/allraw-ledger-diff-check.stdout.txt')['path'], 'classification': '112locations on18hash-bound raw-output paths:105trailing whitespace and7EOF; byte preservation, not new runtime defect; no blanketqualityPASS/P41inheritedclaim'},
        {'command': '(cd policy-engine && uv run --no-sync polisyos-tools workspace doctor --worktree-admission resume --branch codex/e02-F-closeout-20261006 --path /workspace/e02-F-closeout-20261006)', 'target_sha': LEDGER, 'environment': 'Existing resumedFpair; no checkout creation or history repair', 'input_closure': 'Actualbranch/path/registrations/currentworkingtree full147971BJSON', 'outcome': 'PASS', 'output': evidence('root/final-workspace-admission.json')['path'], 'result': 'admitted; complete_verdictTrue'},
        {'command': 'git ls-remote origin refs/heads/codex/e02-F-closeout-20261006 refs/heads/codex/e02-F-cau-20261006 refs/heads/codex/e02-F-fry-20261006 refs/heads/codex/e02-integration refs/heads/main', 'target_sha': LEDGER, 'environment': 'OrdinaryHTTPS Git remote readback; injected authentication preserved', 'input_closure': 'Exact5refs; Froot3d/CAUa720/FRYdefa/G9806/main198', 'outcome': 'PASS', 'output': evidence('root/final-component-remote-readback.stdout')['path']},
    ],
    'property': {'statement': 'The bounded source repair, complete original35ledger and full output custody remain independently source-bound; recommendations/checks/code-ready/Gsource/formal closure do not collapse.', 'runtime_path': ['original Git source cards/full TSV', 'per-ID35/current index/primary receipt', 'lossless stored+decoded transport', 'actual independent Python/Git metadata reader'], 'proxy_divergence': 'Presence of a rich custom JSON is insufficient for the canonical HANDOFF consumer; e89 lacked minimalnames. Forward248 supplies required fields and actual check/output bindings without laundering old numerical outcomes.', 'negative_controls': ['Seven finite corrupt binding/hash/schema/current-state metadata variants refused', 'Actual runtime guard-removal2nativeFAIL/1installedFAIL remains at exact4ee source; no re-execution or marker-only substitution']},
    'predicate_basis': 'independently_reconciled', 'capability_state_or_finding_state': 'bounded_F_code_ready;35original_recommendations33closed2limited;G_source_and_formal_acceptance_not_issued',
    'limitations_and_next_owner': ['B214 broad trackedA/C/F family/conditional/partial/authority contract with completion-distinguishing query remainslimited', 'B56 canonicalRuntime/Scientist sharedadmission/cap+fullworkload/inputroster thenG localmeasurement remainslimited/UNRUN; no second scheduler or lostfolds', 'New rebuilt-sdist/inprocess3.14DoWhy/EconML/genuineidentification-authority positivesUNRUN', 'Historicalscanner2×ERROR−9/Ruff103FAIL/publicsurface38FAIL/P41not_established; newbenchmarkRuff2T201FAIL and rawartifactwhitespaceFAIL separately preserved', 'G integration afterexactfreeze acceptance; no main publication'],
    'counts': {'IDs': 35, 'bundles': 17, 'original_bindings': 36, 'F_recommendations': {'closed': 33, 'limited': 2}, 'technical_original': {'closed': 33, 'limited': 2}, 'finding_checks': {'PASS': 34, 'UNRUN': 1}, 'G_new_source_accepted': 0, 'G_formal_closed': 0, 'prior_Lex_accepted_source': '00a6eda114b903bc5abe86902cd8372426f739a1'},
    'evidence_transport': {'path': str(PACK / 'artifact-transports.json'), 'bytes': mpath.stat().st_size, 'sha256': sha(mpath.read_bytes()), 'file_count': len(records), 'stored_bytes': manifest['stored_bytes'], 'decoded_bytes': manifest['decoded_bytes']},
    'executor_resume': {'same_HEAD_branch_status_outputs_observed': True, 'no_reconstruction_reset_rebase_force_switch': True, 'network_observations_current': True, 'network_state': 'enforced', 'connectivity': 'connected', 'environment_status_ready': True},
    'cleanup': {'action': 'none', 'no_native_Trash': True, 'preserve_unique_inputs_source_docs_receipts_active_environments': True, 'candidates_only_after_inactive_owner_review': [str(SCRATCH / 'foundry/installed-4ee/uv-cache'), str(SCRATCH / 'foundry/installed-4ee/wheel-env')], 'no_permanent_delete_or_empty_Trash': True},
}
# Use the exact previously accepted Lex SHA; never shorten or reconstruct it.
result['counts']['prior_Lex_accepted_source'] = '00a6eda114b903bc5abe86902cd8372426f739a1'
# The canonical row is authoritative if its full spelling differs from prose.
lex = json.loads(subprocess.check_output(['git', 'show', LEDGER + ':' + str(E02 / 'implementation-handoffs/F/continuation-transfer-20261007/per-ID/LA-017.json')], cwd=ROOT))
result['prior_Lex_G_code_acceptance'] = lex['G_code_acceptance']
result['counts']['prior_Lex_accepted_source'] = lex['G_code_acceptance'].get('source_sha', lex['G_code_acceptance'].get('accepted_source'))
(ROOT / PRIMARY).write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'primary': str(PRIMARY), 'files': len(records), 'stored_bytes': manifest['stored_bytes'], 'decoded_bytes': manifest['decoded_bytes'], 'review': review['verdict']}))
