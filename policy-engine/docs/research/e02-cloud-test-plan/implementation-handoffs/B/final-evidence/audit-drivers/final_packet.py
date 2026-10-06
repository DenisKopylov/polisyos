import datetime
import hashlib
import json
import pathlib
import subprocess

HERE = pathlib.Path(__file__).parent
WT = pathlib.Path('/workspace/e02-B-dur-ledger')
PREFIX = 'policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/B/'


def git(wt, *args):
    return subprocess.check_output(['git', '-C', str(wt), *args])


def sha256(value):
    return hashlib.sha256(value).hexdigest()


def committed(wt, ref, path):
    data = git(wt, 'show', f'{ref}:{path}')
    return {'path': path, 'ref': ref, 'sha256': sha256(data), 'bytes': len(data)}, json.loads(data)


full_bytes = (HERE / 'receipt-audit.json').read_bytes()
compact_bytes = (HERE / 'receipt-audit-compact.json').read_bytes()
full = json.loads(full_bytes)
compact = json.loads(compact_bytes)
assert compact['overall_verdict'] == 'metadata_custody_pass_bounded'
assert compact['denominator']['bundle_count'] == 25
assert compact['denominator']['finding_count'] == 60
assert not compact['blocking_mismatches']
assert all(l['remote_head_verified'] for l in compact['lanes'])

packet = {
    'schema': 'policyos.e02.B.final_read_only_receipt_audit.v1',
    'observer': '/root/dur_probe',
    'generated_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'scope': 'Published receipt/overlay metadata, exact Git custody and deciding output bytes; source/runtime acceptance and full historical finding closure remain separate.',
    'read_only_author_trees': True,
    'new_checkouts_created_for_final_audit': 0,
    'compact_receipt_audit': compact,
    'evidence': [
        {'path': str(HERE / 'receipt-audit.json'), 'sha256': sha256(full_bytes), 'bytes': len(full_bytes)},
        {'path': str(HERE / 'receipt-audit-compact.json'), 'sha256': sha256(compact_bytes), 'bytes': len(compact_bytes)},
    ],
    'current_writer_readbacks': [],
    'qualification_evidence': [],
    'qualified_self_created_review_worktree_set': [],
    'canonical_overlay_rows': [],
    'artifact_summary': [],
    'explicit_closure_id_semantics': [],
    'limits': [
        'All60 findings have exact owner-route/disposition coverage; none is automatically closed by a passing receipt audit.',
        'Historical baseline cells/compact summaries are navigation only. Source SHA/ref/environment/input closure and fresh outputs are bound independently.',
        'Existing bounded source-closed B59/B150/B153 scopes and held B61 authority decision are preserved; no residual-ledger edits or wider institutional admission.',
        'Seven self-created review worktrees below lack precreation admission. Current SHA/tree/clean observations do not backdate custody; G must perform an explicitly admitted fresh replay for process-admission acceptance.',
        'RUN B69 physical callback occupancy4/4 remains HOLD; shutdown lock-order/ordinary unfinished-job accounting is a narrower accepted mechanism.',
        'EXE B52 private cache publication/deadline/cancellation is bounded. Already-entered backend nested I/O is uninterruptible; full reentrant execution, served institutional authority and full data/latency performance remain unestablished.',
        'CAS archive final-entry kind admission preserves filesystem type/inode/referent controls; hostile parent/path-swap/owner-ACL laws, unbound tenant policy and full four-base criteria remain unresolved.',
        'Leaf20-file EXE failures and CAS512 broad failures are retained on their own sources; no future root joint cohort is substituted into this audit.',
        'Ignored huge raw/scanner output and unsupported/global architecture results are not blanket green evidence. Full production dataset remains local; exact local G candidates remain in source receipts.',
        'SIGKILL demonstrates process interruption only, not physical power-loss durability or complete IPC cleanup.',
    ],
}

for lane in full['lanes']:
    wt = pathlib.Path(lane['worktree'])
    head = lane['frozen_head']
    current = git(wt, 'rev-parse', 'HEAD').decode().strip()
    status = git(wt, 'status', '--porcelain', '--untracked-files=all').decode()
    assert current == head
    assert not status, (lane['lane'], status)
    packet['current_writer_readbacks'].append({
        'lane': lane['lane'], 'worktree': str(wt), 'head': head,
        'tree': git(wt, 'rev-parse', head + '^{tree}').decode().strip(),
        'branch': git(wt, 'branch', '--show-current').decode().strip(),
        'status_porcelain_all_untracked': status,
        'source_current_readback_only': True,
        'remote_ref': 'refs/heads/' + lane['branch'],
        'remote_verified': next(x for x in compact['lanes'] if x['lane'] == lane['lane'])['remote_head_verified'],
    })
    nested = [x for r in lane['receipts'] for x in r.get('nested_artifacts', [])]
    packet['artifact_summary'].append({
        'lane': lane['lane'], 'canonical_receipt_count': len(lane['receipts']),
        'check_count': sum(len(r['checks']) for r in lane['receipts']),
        'nested_ref_occurrences': len(nested),
        'unique_nested_committed_paths': len({x['path'] for x in nested if x['committed']}),
        'unique_declared_untransferred_paths': len({x['path'] for x in nested if x['declared_untransferred']}),
        'nested_custody_failures': [x for x in nested if not x['declared_untransferred'] and (not x['committed'] or not x['sha256_matches'] or x['bytes_matches'] is False)],
    })
    for receipt in lane['receipts']:
        meta, doc = committed(wt, head, receipt['path'])
        dispositions = doc.get('finding_dispositions', doc.get('finding_classification', []))
        disposition_field = 'finding_dispositions' if 'finding_dispositions' in doc else 'finding_classification'
        row_bindings = []
        for index, row in enumerate(dispositions):
            normalized = json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()
            row_bindings.append({
                'finding_id': row.get('finding_id') or row.get('id'),
                'json_pointer': '/' + disposition_field + '/' + str(index),
                'parsed_row_canonical_json_sha256': sha256(normalized),
                'canonical_json_rule': 'UTF8; sort_keys=true; ensure_ascii=false; separators=(comma,colon)',
                'state': row.get('state') or row.get('status') or row.get('disposition'),
                'source_status_retained': row.get('source_status_retained') or row.get('canonical_source_status'),
                'full_source_row_available_in_receipt': True,
            })
        packet['canonical_overlay_rows'].append({
            'lane': lane['lane'], 'slice': doc['slice'], 'receipt': meta,
            'receipt_commit': receipt['receipt_commit'],
            'finding_ids': [r.get('finding_id') or r.get('id') for r in dispositions],
            'source_row_bindings': row_bindings,
            'capability_state_or_finding_state': doc['capability_state_or_finding_state'],
        })
        if doc.get('closure_ids'):
            packet['explicit_closure_id_semantics'].append({
                'lane': lane['lane'], 'slice': doc['slice'], 'ids': doc['closure_ids'],
                'semantics': doc.get('closure_ids_meaning', doc.get('closure_ids_semantics')),
                'finding_state': doc['capability_state_or_finding_state'],
                'full_closure_not_inferred': True,
            })

own_ref = '2fe743de5f39f0f622db83318a123cb547a67470'
meta, own = committed(WT, own_ref, PREFIX + 'admission-qualifications/qualification.json')
assert own['created_git_worktree_count'] == 4 and own['created_worktree_set_complete']
assert own['precreation_custody'] == 'not_established'
packet['qualification_evidence'].append(meta)
for row in own['current_checkpoints']:
    local_name = pathlib.Path(row['path']).name
    checkpoint_meta, checkpoint = committed(WT, own_ref, PREFIX + 'admission-qualifications/' + local_name)
    assert checkpoint_meta['sha256'] == row['sha256']
    assert checkpoint['current_identity_matches'] and checkpoint['source_clean']
    assert checkpoint['expected_sha'] == row['source_sha'] == checkpoint['observed_sha']
    assert checkpoint['observed_tree'] == row['source_tree']
    assert checkpoint['precreation_custody'] == 'not_established'
    packet['qualification_evidence'].append(checkpoint_meta)
    packet['qualified_self_created_review_worktree_set'].append({
        'creator': '/root/dur_probe', 'path': row['checkout'], 'head': row['source_sha'], 'tree': row['source_tree'],
        'precreation_custody': 'not_established', 'current_checkpoint': checkpoint_meta,
        'observation_started_at': row['started_at'], 'observation_finished_at': row['finished_at'],
    })

run_wt = pathlib.Path('/workspace/e02-B-run')
adapter_ref = '86c5771aa51859624488c784df710b73cd0929b0'
meta, adapter = committed(run_wt, adapter_ref, PREFIX + 'run-executor-review/independent-worktree-custody.json')
assert meta['sha256'] == '333bf0f0080db8483368d35de8f10463720bcf802ec7ba29b27f35996c719e0d'
packet['qualification_evidence'].append(meta)
assert len(adapter['complete_self_created_worktree_set']) == 2
for row in adapter['complete_self_created_worktree_set']:
    assert row['historical_precreation_receipt'] is None and row['historical_resume_receipt'] is None
    assert row['custody_disposition'] == 'precreation_custody_not_established'
    packet['qualified_self_created_review_worktree_set'].append({
        'creator': '/root/adapters_probe', 'path': row['path'], 'head': row['HEAD'], 'tree': row['tree'],
        'precreation_custody': 'not_established', 'current_checkpoint': meta,
        'observed_at_UTC': adapter['observed_at_UTC'],
    })

cas_wt = pathlib.Path('/workspace/e02-B-cas')
cas_head = next(x for x in full['lanes'] if x['lane'] == 'cas')['frozen_head']
meta, cas = committed(cas_wt, cas_head, PREFIX + 'cas-workspace-qualification.json')
packet['qualification_evidence'].append(meta)
assert len(cas['self_created_registered_worktrees']) == 1
for row in cas['self_created_registered_worktrees']:
    assert row['precreation_custody'] == 'not_established'
    assert row['precreation_admission_receipt'] is None and row['postcreation_resume_admission_receipt'] is None
    packet['qualified_self_created_review_worktree_set'].append({
        'creator': '/root/cas_probe', 'path': row['path'], 'head': row['head_sha'], 'tree': row['tree_sha'],
        'precreation_custody': 'not_established', 'current_checkpoint': meta,
        'qualified_checks': cas['qualified_source_observations'],
    })
for admission in cas['root_provided_writer']['admission_evidence']:
    data = git(cas_wt, 'show', cas_head + ':' + admission['committed_copy_path'])
    assert sha256(data) == admission['sha256'] and len(data) == admission['bytes']
    recorded = json.loads(data)
    assert recorded['status'] == admission['status'] == 'admitted'
    packet['qualification_evidence'].append({
        'path': admission['committed_copy_path'], 'ref': cas_head, 'sha256': sha256(data), 'bytes': len(data),
        'provided_writer_path': cas['root_provided_writer']['path'], 'mode': admission['requested']['mode'],
        'historical_started_at': admission['started_at'], 'historical_finished_at': admission['finished_at'],
        'scope': 'Root-provided CAS writer only; no blanket all-checkouts admission.',
    })
meta, observation = committed(cas_wt, cas_head, cas['current_observation']['path'])
assert meta['sha256'] == cas['current_observation']['sha256'] and meta['bytes'] == cas['current_observation']['bytes']
packet['qualification_evidence'].append(meta)

assert len(packet['qualified_self_created_review_worktree_set']) == 7
for row in packet['qualified_self_created_review_worktree_set']:
    assert git(row['path'], 'rev-parse', 'HEAD').decode().strip() == row['head']
    assert git(row['path'], 'rev-parse', 'HEAD^{tree}').decode().strip() == row['tree']
    assert not git(row['path'], 'status', '--porcelain', '--untracked-files=all')
    row['current_identity_still_matches'] = True
    row['current_observation_not_historical_admission'] = True

packet['admission_qualification_count'] = {'DUR_review': 4, 'adapters_review': 2, 'CAS_baseline': 1, 'total': 7}
packet['all_checkouts_admitted'] = False
packet['runtime_finding_closure_verdict'] = 'not_established_by_metadata_audit; retain bounded per-finding overlays/residuals'
packet['verdict'] = 'metadata_custody_pass_bounded_with_explicit_process_admission_qualifications'
prior_path = HERE.parent / 'audit' / 'final-receipt-audit-compact.json'
prior_bytes = prior_path.read_bytes()
assert sha256(prior_bytes) == '0137f92c364941e087a1cb90d229ec930cc74593f7145d549154b3554c5f5c4c'
packet['previous_snapshot_preserved'] = {
    'path': str(prior_path), 'sha256': sha256(prior_bytes), 'bytes': len(prior_bytes),
    'scope': 'Earlier six-head metadata/source-cell/deciding-output snapshot, before NET88 and before RUN effective canonical-locator qualification; no rewrite or runtime-result substitution.',
}
packet['narrow_successor_audits'] = []
for name in ['run-locator-audit.json', 'net-evidence-audit.json']:
    path = HERE / name
    data = path.read_bytes()
    packet['narrow_successor_audits'].append({'path': str(path), 'sha256': sha256(data), 'bytes': len(data), 'result': json.loads(data)})
packet['limits'].append('NET88 accepts deadline-expiry publication/registration only. Within-budget external cancellation suppressed by a connector, uninterruptible physical I/O/hard wall time and served/live transport remain outside the verified predicate.')
for name in ['audit_receipts.py', 'compact_receipts.py', 'final_packet.py', 'run_locator_audit.py', 'net_evidence_audit.py']:
    path = HERE / name
    data = path.read_bytes()
    packet['evidence'].append({'path': str(path), 'sha256': sha256(data), 'bytes': len(data)})
out = HERE / 'final-receipt-audit-compact.json'
out.write_text(json.dumps(packet, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'path': str(out), 'bytes': out.stat().st_size, 'sha256': sha256(out.read_bytes()), 'verdict': packet['verdict'], 'heads': {r['lane']: r['head'] for r in packet['current_writer_readbacks']}, 'admission_qualification_count': packet['admission_qualification_count']}))
