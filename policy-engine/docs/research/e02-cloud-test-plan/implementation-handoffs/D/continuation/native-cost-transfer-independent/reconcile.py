"""Read-only exact-source and retained-output reconciliation; no product execution."""
import csv
import gzip
import hashlib
import io
import json
import subprocess
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

REPO = Path('/workspace/e02-D-published-root')
OUT = Path('/tmp/e02-D-cost-transfer-independent-20261006')
DOC_SOURCE = '3c636ff52718897c9900a49580c9bd058086de35'
COST_SOURCE = '39a0195e970b55ca2a013770a9a4ef95fa1e2732'
COST_RECEIPT = '1159cad1c970c783b30c943cf2eb38b61265f48d'
TRN_SOURCE = '4ac49418289a31e77329bf92b1c2bf990cf2a087'
TRN_BASE = 'cba802e22e1f1198aa971f529228ab2c1fd35cf7'
E02 = 'policy-engine/docs/research/e02-cloud-test-plan/'
TRN_OUTPUT = Path('/tmp/e02-transfer-criteria-f3f900ae578842bea2f7e75fa688f05a')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def git(*args):
    return subprocess.check_output(['git', *args], cwd=REPO)


def blob(source, path):
    return git('show', source + ':' + path)


def binding(source, path, extent='complete_file'):
    data = blob(source, path)
    return {'source_sha': source, 'path': path, 'git_blob': git('rev-parse', source + ':' + path).decode().strip(), 'bytes': len(data), 'sha256': digest(data), 'review_extent': extent}


def local_binding(path):
    data = Path(path).read_bytes()
    return {'path': str(path), 'bytes': len(data), 'sha256': digest(data)}


def xml_result(raw):
    suite = ET.fromstring(raw).find('testsuite')
    return {key: int(suite.attrib[key]) for key in ['tests', 'failures', 'errors', 'skipped']} | {'testcases': [case.attrib['classname'] + '::' + case.attrib['name'] for case in suite.findall('testcase')]}


def trn_run(directory, name):
    meta_raw = (directory / (name + '.json')).read_bytes()
    meta = json.loads(meta_raw)
    txt = (directory / (name + '.txt')).read_bytes()
    assert digest(txt) == meta['output_sha256']
    text = txt.decode()
    marker = 'ACTUAL_REVIEW_RUNTIME '
    runtime, _ = json.JSONDecoder().raw_decode(text[text.index(marker) + len(marker):])
    assert meta['before'] == meta['after'] and meta['before']['status'] == ''
    origin_checks = []
    for row in runtime['loaded_product_modules']:
        path = Path(row['origin'])
        relative = 'policy-engine/' + str(path.relative_to('/workspace/e02-D-published-transfer/policy-engine'))
        actual = digest(blob(meta['before']['sha'], relative))
        assert actual == row['sha256'], relative
        origin_checks.append([row['module'], relative, actual])
    retained = meta.get('retained_input_output_files', [])
    for row in retained:
        raw = Path(row['path']).read_bytes()
        assert len(raw) == row['bytes'] and digest(raw) == row['sha256'], row['path']
    native = runtime.get('native_hnsw')
    if native:
        assert digest(Path(native['origin']).read_bytes()) == native['sha256']
    return {
        'source_sha': meta['before']['sha'], 'tree_sha': meta['before']['tree'],
        'command': meta['argv'], 'cwd': meta['cwd'], 'exit_code': meta['exit_code'],
        'wall_seconds': meta['wall_seconds'], 'environment': meta['environment'],
        'source_before_after_clean_unchanged': True,
        'actual_runtime': {k: v for k, v in runtime.items() if k != 'loaded_product_modules'},
        'complete_outputs': [local_binding(directory / (name + ext)) for ext in ['.txt', '.json', '.xml']],
        'junit': xml_result((directory / (name + '.xml')).read_bytes()),
        'independently_reconciled_origins': {'denominator': len(origin_checks), 'mismatches': 0, 'ordered_full_origin_tuple_sha256': digest(json.dumps(origin_checks, separators=(',', ':')).encode()), 'lossless_full_records': str(directory / (name + '.txt')) + '#ACTUAL_REVIEW_RUNTIME.loaded_product_modules'},
        'independently_reconciled_retained_files': {'denominator': len(retained), 'bytes': sum(r['bytes'] for r in retained), 'mismatches': 0, 'lossless_full_records': str(directory / (name + '.json')) + '#retained_input_output_files'},
        'executed_by': 'transfer_owner; independently read/reconciled here, not rerun by reviewer'
    }

receipt_path = E02 + 'implementation-handoffs/D/continuation-funnel-cost-stopping.json'
cost_receipt = json.loads(blob(COST_RECEIPT, receipt_path))
archive_path = cost_receipt['complete_output_bundle']['path']
archive = blob(COST_RECEIPT, archive_path)
assert digest(archive) == cost_receipt['complete_output_bundle']['sha256']
raw = gzip.decompress(archive)
assert digest(raw) == cost_receipt['complete_output_bundle']['uncompressed_sha256']
members = json.loads(raw)['members']
assert len(members) == 10 and all(isinstance(v, str) for v in members.values())
meta = json.loads(members['actual.json'])
assert meta['before'] == meta['after'] == {'head': COST_SOURCE, 'tree': '9f66f655f0453138256e9b641fc65bf0d31c48ea', 'status': ''}
assert digest(members['complete.txt'].encode()) == meta['output_sha256']
origins = json.loads(members['complete.txt'].split('E02_RUNTIME_ORIGINS=', 1)[1].splitlines()[0])
for row in origins:
    relative = 'policy-engine/' + str(Path(row['path']).relative_to('/workspace/e02-D-published-funnel/policy-engine'))
    assert digest(blob(COST_SOURCE, relative)) == row['sha256'] == row['frozen_sha256'] and row['PASS'] is True
assert len(origins) == 19
ledgers = {name: json.loads(value) for name, value in members.items() if name.startswith('actual-ledgers/')}
assert len(ledgers) == 5
ledger_profiles = []
for name, ledger in ledgers.items():
    assert ledger['schema_version'] == '1.1'
    receipts = ledger['spend_receipts']
    state = ledger['state']
    if 'test_trace_cost' in name:
        assert receipts == {} and state['spent'] == {} and state['provider_spent'] == {}
    else:
        expected_count = 2 if 'run' in state['spent'] else 3
        assert len(receipts) == expected_count
        assert Decimal(state['provider_spent']['provider-a']) == expected_count
        assert sum((Decimal(r['amount']) for r in receipts.values()), Decimal(0)) == expected_count
        assert all(r['payload_digest'] and r['provider'] == 'provider-a' and Decimal(r['amount']) == 1 for r in receipts.values())
        assert len({r['event_id'].split(':budget:')[0] for r in receipts.values()}) == 2
    assert all(Decimal(value) == 0 for value in state['reserved'].values())
    ledger_profiles.append({'member': name, 'original_bytes_sha256': digest(members[name].encode()), 'receipt_count': len(receipts), 'spent_by_key': state['spent'], 'provider_aggregate': state['provider_spent'], 'physical_event_count': len({r['event_id'].split(':budget:')[0] for r in receipts.values()})})

original_path = E02 + 'implementation-handoffs/D/published-final-criterion-accounting.json'
original = json.loads(blob('cae5589aa7080b628e93d594eeb4ff7c2fc2414d', original_path))
ledger_path = E02 + 'implementation-handoffs/D/continuation/criterion-ledger.json'
ledger = json.loads(blob(DOC_SOURCE, ledger_path))
original_rows = {row['id']: row for row in original['criterion_occurrences']}
assert len(original_rows) == len(ledger['criterion_occurrences']) == 46
for row in ledger['criterion_occurrences']:
    for key, value in original_rows[row['id']].items():
        assert row[key] == value, (row['id'], key)
criteria = [row for row in ledger['criterion_occurrences'] if row['finding_id'] in ['B120','B128','B129','B130','B131','B133','B134','B158','B159']]
for row in criteria:
    admission = row['canonical_content']
    assert len(admission['text'].encode()) == admission['bytes'] and digest(admission['text'].encode()) == admission['sha256']
    card = row['original_acceptance_binding']['canonical_card']
    card_bytes = blob(card['source_sha'], card['path'])
    assert len(card_bytes) == card['bytes'] and digest(card_bytes) == card['sha256']
    assert admission['text'].encode() in card_bytes

changed_lines = git('diff', '--name-status', TRN_BASE, TRN_SOURCE).decode().splitlines()
trn_paths = [line.split('\t')[-1] for line in changed_lines]
mechanism_paths = [path for path in trn_paths if path.startswith('policy-engine/src/')]
assert len(mechanism_paths) == 3
source_bindings = []
for path in mechanism_paths + [p for p in trn_paths if p.startswith('policy-engine/tests/') or p.startswith('policy-engine/release-fragments/')]:
    source_bindings.append(binding(TRN_SOURCE, path, 'complete_changed_file_or_full_delta'))
for path in ['policy-engine/tests/integration/scientist/methods/search/funnel/test_native_resource_cost_stopping.py','policy-engine/tests/integration/scientist/methods/search/funnel/test_orchestrator.py','policy-engine/src/polisyos/scientist/methods/search/controller.py','policy-engine/src/polisyos/scientist/methods/search/service.py','policy-engine/src/polisyos/scientist/methods/search/stopping.py','policy-engine/src/polisyos/scientist/orchestration/engine/budget_middleware.py']:
    source_bindings.append(binding(COST_SOURCE, path, 'complete_test_or_relevant_runtime_consumer_functions'))

trn_positive = trn_run(TRN_OUTPUT, 'trn-cas-hnsw-tmp')
trn_removal = trn_run(TRN_OUTPUT, 'trn-discovery-property-removal')
trn_before = trn_run(Path('/workspace/e02-D3-receipts/transfer-criteria-review'), 'trn-original-base')
assert trn_positive['junit']['tests'] == 32 and trn_positive['exit_code'] == 0
assert trn_removal['junit']['tests'] == 2 and trn_removal['junit']['failures'] == 1
assert trn_before['junit']['tests'] == 10 and trn_before['junit']['failures'] == 1

bindings = {
    'schema': 'policyos.e02.independent_review_read_bindings.v1',
    'reviewer': '/root/cost_transfer_review', 'repository': str(REPO),
    'initial_attached_root': {'branch': 'codex/e02-D-published-root', 'source_sha': DOC_SOURCE, 'tree_sha': 'a5a74887e96020550b27b35ac5ceaa65e43ec0e5', 'status': 'clean', 'notice': 'Root advances under its appointed writer; review never uses moving HEAD as source pin.'},
    'instructions': [binding(DOC_SOURCE, path) for path in ['AGENTS.md','policy-engine/CONTRIBUTING.md', E02 + 'execution-prompts/HANDOFF.md', E02 + 'execution-organization/README.md']],
    'criteria_cards': [binding('198076863e143dea9f89f02734b13d50dae3eed5', 'policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/' + name + '.md') for name in ['CTL-03','FUN-01','TRN-01','TRN-02']],
    'full_owner_TSV_inputs': [binding(DOC_SOURCE, E02 + 'execution-organization/' + name) for name in ['bundle-owners.tsv','finding-owners.tsv']],
    'complete_criterion_accounting_inputs': [binding('cae5589aa7080b628e93d594eeb4ff7c2fc2414d', original_path), binding(DOC_SOURCE, ledger_path)],
    'criterion_preservation': {'denominator': 'All46 original criterion_occurrences, all original fields; continuation fields additive', 'MATCH': 46, 'mismatches': 0},
    'reviewed_occurrences': [{'id': row['id'], 'canonical_closure_owner': row['canonical_closure_owner'], 'acceptance_sha256': row['canonical_content']['sha256'], 'original_card': row['original_acceptance_binding']['canonical_card']} for row in criteria],
    'source_inputs': source_bindings,
    'cost_receipt': binding(COST_RECEIPT, receipt_path),
    'cost_archive': {'source_sha': COST_RECEIPT, 'path': archive_path, 'sha256': digest(archive), 'uncompressed_sha256': digest(raw), 'member_count': len(members), 'members': [{'name': name, 'bytes': len(value.encode()), 'sha256': digest(value.encode())} for name, value in members.items()]},
    'transfer_lossless_local_outputs': trn_positive['complete_outputs'] + trn_removal['complete_outputs'] + trn_before['complete_outputs'],
    'transfer_control_harness': [local_binding(TRN_OUTPUT / name) for name in ['remove_whole_catalog.py', 'deny_numeric_backends.py', 'review_observer.py']],
    'source_code_copies': 'none; tracked inputs referenced as exact Git path/blob/raw-byte hashes',
    'permanent_deletion_or_environment_changes': 'none'
}
(OUT / 'read-bindings.json').write_text(json.dumps(bindings, ensure_ascii=False, indent=2) + '\n')

review = {
    'schema': 'policyos.e02.independent_review.v1', 'unit': 'D',
    'reviewer': '/root/cost_transfer_review', 'reviewer_is_author': False,
    'review_mode': 'Read-only exact Git source/test review plus independent recomputation of complete retained deciding outputs; no product/backend rerun.',
    'timestamp_UTC': datetime.now(timezone.utc).isoformat(), 'accepted_in_G': False,
    'read_bindings': {'path': str(OUT / 'read-bindings.json'), 'sha256': digest((OUT / 'read-bindings.json').read_bytes())},
    'own_fixable_blocking_findings_in_reviewed_delta': [],
    'cost_to_stopping': {
        'specification_verdict': 'bounded engineering witness accepted; full B120 finding remains limited by distinct B/authority inputs',
        'engineering_quality_verdict': 'No new mechanism was introduced by39a; the ordinary configured owner is reused through the actual native ask/evaluate/tell consumer.',
        'source_sha': COST_SOURCE, 'tree_sha': '9f66f655f0453138256e9b641fc65bf0d31c48ea', 'receipt_head': COST_RECEIPT,
        'base_sha': cost_receipt['slice_base_sha'],
        'full_new_test_delta_paths': git('diff', '--name-only', COST_SOURCE + '^', COST_SOURCE).decode().splitlines(),
        'production_delta': [],
        'runtime_chain': cost_receipt['actual_runtime_chain'],
        'actual_check': {'command': meta['command'], 'cwd': meta['cwd'], 'environment': meta['env'], 'interpreter': meta['python'], 'exit_code': meta['exit_code'], 'wall_seconds': meta['wall_seconds'], 'junit': xml_result(members['actual.xml']), 'complete_output': archive_path + '@' + COST_RECEIPT + '#complete.txt', 'output_sha256': meta['output_sha256'], 'runtime_origins_denominator': len(origins), 'runtime_origins_Git_match': len(origins), 'source_before_after_clean_unchanged': True, 'executed_by': 'funnel_owner; independently read/reconciled here, not rerun by reviewer'},
        'fresh_recorded_ledgers': ledger_profiles,
        'independent_reconciliation': 'Complete five actual ledger members, receipt event-ID/digest/key/provider/amount identity, reservation release and physical event-base IDs independently recomputed from retained bytes;19 actual product origins independently matched to source39a Git blobs.',
        'proxy_divergences': ['Default native workers emit2 physical paid responses, funnel cost2, but3 scoped per-key receipts/provideraggregate3. Selected policy_translator recorded key1 drives its explicitly configured cost1 cutoff; aggregate3 is not invoice truth.', 'Retained trace1 and typed-looking ACK without settlement do not yield persisted receipts or a cost1 cutoff; scientific result rejects, attempted next proposal catches the missing cutoff.'],
        'negative_check_semantics': 'The fifth pytest case PASS catches two exact positive-oracle AssertionErrors after settlement removal; this is not a claim that a separate pytest invocation produced2FAIL.',
        'predicate_basis': 'recomputed local recorded-state/receipt/cutoff; independently_reconciled source/output bytes; not_established external invoice, accounting origin authority and immutable revision snapshot',
        'residual_inputs': cost_receipt['finding_residual']['missing_input_or_capability'],
        'next_owners': cost_receipt['finding_residual']['next_owner'],
        'finding_proposal': {'B120': 'limited: available native cost→controller consumer now verified; raw lossless decoder, durable owner snapshot and authority criteria remain supplier inputs, not renamed D defects'},
        'scope_limits': ['Controlled physical HTTP transport supplies provider-reported fixture amounts; actual factory/decoder/enforcer/ledger/funnel/controller/stopping run unchanged.', 'The scientific estimator in configured_workflow is the existing Foundry bootstrap consumer; this does not establish native policy raw-sample B157.', 'Fresh middleware/controller ledger readback is actual; this witness does not establish served SearchService resume or deployment appointment.', 'Public owner budget_state currently reloads ledger and is copied, but no immutable receipt/revision snapshot port is invented.']
    },
    'transfer_selection': {
        'specification_verdict': 'bounded B129 post-admission source quota and captured native-generation consumer accepted; full original finding decisions remain criterion-scoped',
        'engineering_quality_verdict': 'Three existing owners extended; no second ANN replay/store/latest pointer/new GP/optimizer.',
        'source_sha': TRN_SOURCE, 'tree_sha': '4aab1d49fbd6766c7275f43b7d43f07b906a2057', 'review_delta_base': TRN_BASE,
        'full_changed_paths': changed_lines, 'mechanism_paths': mechanism_paths,
        'source_delta': 'WarmStartBridge requests one whole current native catalog. TransferLearningManager preserves exact discovered refs, content-admits each actual persisted row, and counts only nonempty admitted source groups toward max_runs; normalized minima and round-robin row quota remain existing behavior. Vector query captures generation once and derives k from that same object.',
        'actual_positive': trn_positive, 'actual_removal': trn_removal, 'actual_defect_before_fix': trn_before,
        'runtime_chain': ['Native HNSW one captured generation query(None)', 'RunFingerprint retains exact discovered ArtifactRef', 'Existing actual B CAS verified snapshot resolves history, original candidate/evaluation and numerical basis', 'Existing strict row admission rejects incompatible origin and malformed-present stage_a_passed', 'Only nonempty admitted source counts toward max_runs; fair normalized-minimum row selection', 'WarmStartBridge returns original measured Evaluation; exact replay re-resolves refs without ANN'],
        'independent_oracle': 'Original persisted candidate/evaluation/basis content identity, score/replica quota examples, retained real CAS bytes, old/new native-reader barriers and independent source/output reconciliation; no model.posterior or duplicateGP fit.',
        'proxy_divergences': ['Nearest discovery source is incompatible, next malformed, later valid: finite source window returns0, one whole-catalog discovery followed by admission returns1; marker/ref identity remains intact.', 'Reader has old2 native keys paused while new3 generation publishes: returned count/keys/metadata all belong to old captured object, then fresh query returns new3.'],
        'removal_scope': 'Only the bridge discovery argument top_k=None is replaced by its old finite limit in an isolated function object; all typed refs, basis, row admission, markers, tests and canonical bytes remain unchanged. Actual1FAIL/1PASS.',
        'optional_profile_scope': 'Installed locked numerical distributions exist, but explicit import-denial makes Torch/Bo/GP unavailable for this CAS/HNSW-only profile. Actual HNSW0.8.0 binary executes and is independently hash-checked; this32 run establishes no GP property.',
        'counters_scope': 'Admission counters describe visited histories/rows up to the final admitted-source quota. Unvisited lower-ranked source histories are not asserted as globally measured/rejected/unavailable.',
        'finding_proposals': {'B129': 'available post-admission source-limit residual fixed and witnessed; new32 scope is not a fresh >1000/second-process replay', 'B128/B130': 'bounded persisted-row/type/rank/quota/replica controls accepted; no acceleration or measurement truth inferred', 'B131': 'held institutional source/tenant/split authorization input remains distinct', 'B133': 'existing cache/current32 exact-ref mutation/cold controls retained; not distributed/latest authority', 'B134': 'current32 native coherence/failure controls accepted; live owner-issued metadata remains separate input'},
        'residual_inputs': ['Appointed institutional source/tenant/split/evaluator authorization and live metadata issuer still required where original criteria require them.', 'Earlier >1000 native/second-process receipts are source-bound lineages; vector query code has changed, so they are not relabeled a fresh4ac replay.', 'Ordinary configured transfer→real GP fit belongs to the separately frozen optimizer/runner witness; no currentGP execution inferred from32.', 'Whole-catalog discovery scales with current index size and claims neither exact global nearest ordering nor acceleration.'],
        'backend_crashes_and_storage_failures': 'Earlier all-extras SIGKILL and first optional-profile ENOSPC28ERROR/4PASS remain execution limitations/errors. This review adopts only corrected natural32 and actual1FAIL/1PASS removal; no failures are silently retried into PASS.',
        'predicate_basis': 'recomputed local content/basis/admission/native-generation quantities; independently_reconciled exact Git and retained bytes; not_established institutional rights/scientific truth',
        'delivery_status': 'Production source4ac independently read back from remote branch at review time; separate committed author receipt remains pending (reported overlay/index space limitation). Local complete outputs available and bound above.'
    },
    'remote_readback': {'command': 'git ls-remote origin refs/heads/codex/e02-D-published-transfer refs/heads/codex/e02-D-published-funnel', 'observed': {'codex/e02-D-published-transfer': TRN_SOURCE, 'codex/e02-D-published-funnel': COST_RECEIPT}},
    'pattern_pass': {'P01/P02': 'Actual consumer effects and persisted readback reviewed, exact source-bound chains above.', 'P05/P09/P10': 'No invoice/permit/scientific truth inferred from fixture values or success markers; refusal/completeness scope explicit.', 'P14': 'Two physical events distinguished from3 per-key receipts; author executions distinguished from independent read/recomputation.', 'P27/P29/P32': 'Existing canonical B ledger/CAS and D bridges reused; content/ref/fresh-reader/removal gates exercised.', 'P35': 'Complete19cost origins/5ledgers and350origins per3TRN runs plus all retained files reconciled; original46criterion fields preserved.', 'P37/P38': 'Predicate provenance, nearest-window and cost-marker divergent cases explicit.', 'P40': 'Existing source-admission invariant widened beyond finite discovery window; known authority/decoder gaps remain named supplier inputs.', 'P41': 'No inherited-red waiver made; characterization058 is before this repair but not the original continuation slice base, and failures are not exported as unrelated debt.'},
    'cleanup': {'review_artifacts': str(OUT), 'no_product_or_test_writes': True, 'no_children_or_new_checkouts': True, 'no_G_or_main_writes': True, 'permanent_deletion': 'none'}
}
(OUT / 'review.json').write_text(json.dumps(review, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'review': local_binding(OUT / 'review.json'), 'read_bindings': local_binding(OUT / 'read-bindings.json'), 'recompute_script': local_binding(OUT / 'reconcile.py'), 'verification': 'PASS', 'product_backend_executions_by_reviewer': 0}, ensure_ascii=False))
