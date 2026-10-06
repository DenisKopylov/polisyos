"""Read-only Git source ownership/carry audit; emits no integration mutation."""
import datetime
import hashlib
import itertools
import json
import pathlib
import subprocess

BASE = '198076863e143dea9f89f02734b13d50dae3eed5'
REPO = '/workspace/e02-F-fry-20261006'
OUT = pathlib.Path('/workspace/e02-F-20261006-receipts/fry/G-source-integration-order.json')
HP = 'policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/F/'
CONFIG = {
    'api': ('449d32909928caf39382f4ff02ac74b0adf277eb', 'api-20261006.json'),
    'cau': ('4c5a11ff8050c6108f6753177b96e6714cef401f', 'did-selected-cohort-20261006.json'),
    'consumer': ('92148340601ac6ea69f0dbd4764aae7428ad83d7', 'causal-consumer-binding-20261006.json'),
    'dowhy': ('c8c2319d6c48f23f90103322da8cd63bc959da6f', 'dowhy-worker-20261006.json'),
    'economics': ('fb51511fef60c5123875e99ab2f19a9a0bd5d16f', 'economic-science-profiles-20261006.json'),
    'fry': ('f4fa51e6dd247cfd967450263579d67233a743d6', 'treasury-execution-20261006.json'),
    'graph': ('a0a050d24c137b4893a7b52b2f83ea710da46471', 'scm-source-bound-20261006.json'),
    'graph_intake': ('2044260c39dc4988b37d5a1568b65a1cdb1e3d31', 'graph-intake-native-20261006.json'),
    'installed': ('e9bd25f05f063dd823d27a44b3c1c740e940751c', 'installed-worker-20261006.json'),
    'lex': ('77166daa0ff8b9659e3978447f9016c691694266', 'lex-pass-plan-20261006.json'),
    'rdd': ('15a04c4400497374416e167a5f61ebc12f61b8e4', 'rdd-sharp-rbc-20261006.json'),
    'fit': ('f460bd81b8124be58f890f59a53e2aba9e7ceb76', 'tmle-20261006.json'),
}
COMMANDS = []


def git(*args):
    cmd = ['git', '-C', REPO, *args]
    p = subprocess.run(cmd, capture_output=True)
    record = {'argv': cmd, 'exit_code': p.returncode, 'stderr': p.stderr.decode()}
    if '--binary' in args:
        record.update(stdout_git_recomputable=True, stdout_bytes=len(p.stdout),
                      stdout_sha256=hashlib.sha256(p.stdout).hexdigest())
    elif args and args[0] == 'show' and any(':policy-engine/docs/research/' in a for a in args):
        # A tracked receipt is an immutable input, not another output copy.
        record.update(stdout_git_recomputable=True, stdout_bytes=len(p.stdout),
                      stdout_sha256=hashlib.sha256(p.stdout).hexdigest(),
                      stdout_source_locator=args[-1])
    else:
        record['stdout'] = p.stdout.decode()
    COMMANDS.append(record)
    assert p.returncode == 0, COMMANDS[-1]
    return p.stdout


def blob(sha, path):
    return git('rev-parse', sha + ':' + path).decode().strip()


def paths_of(commit):
    return git('show', '--format=', '--name-only', commit).decode().splitlines()


def commit_data(commit):
    return {'sha': commit, 'tree': git('rev-parse', commit + '^{tree}').decode().strip(),
            'subject': git('show', '-s', '--format=%s', commit).decode().strip(),
            'changed_paths': paths_of(commit)}


remote = git('ls-remote', '--heads', 'origin', 'refs/heads/codex/e02-F-*20261006*').decode()
remote_rows = {line.split('\t')[1]: line.split('\t')[0] for line in remote.splitlines()}
receipts = {}
topics = {}
for name, (head, filename) in CONFIG.items():
    initial_head = head
    initial = json.loads(git('show', head + ':' + HP + filename))
    head = remote_rows['refs/heads/' + initial['branch']]
    data = git('show', head + ':' + HP + filename)
    d = json.loads(data)
    receipts[name] = d
    branch = 'refs/heads/' + d['branch']
    assert remote_rows[branch] == head, (name, remote_rows[branch], head)
    impl = d['implementation_commits']
    candidate = d.get('candidate_sha') or d.get('implementation_sha') or impl[-1]
    # Do not use a publication/metadata head as a new numerical implementation.
    candidate = impl[-1] if name not in {'consumer', 'graph'} else candidate
    declared = d['changed_paths']
    if name == 'installed':
        own = sorted(d['owned_changed_paths'])
        own_commits = [c for c in impl if set(paths_of(c)) <= set(own)]
    elif name == 'graph':
        own_commits = d['author_only_implementation_commits']
        own = sorted(set().union(*(set(paths_of(c)) for c in own_commits)))
    else:
        own_commits = impl
        own = sorted(declared)
    base = d['slice_base_sha']
    own_diff = git('diff', '--name-only', base, candidate, '--', *own).decode().splitlines()
    assert set(own_diff) == set(own), (name, set(own) - set(own_diff))
    full = git('diff', '--name-only', BASE, candidate).decode().splitlines()
    bindings = [{'path': p, 'candidate_blob': blob(candidate, p),
                 'published_blob': blob(head, p)} for p in own]
    for item in bindings:
        assert item['candidate_blob'] == item['published_blob'], (name, item['path'])
    # Immutable receipts themselves are recorded by SHA/bytes, not embedded repeatedly.
    topics[name] = {'published_head': head, 'published_tree': git('rev-parse', head + '^{tree}').decode().strip(),
                    'initial_observed_head': initial_head, 'head_drift_since_initial_snapshot': head != initial_head,
                    'branch': d['branch'], 'receipt_path': HP + filename,
                    'receipt_bytes': len(data), 'receipt_sha256': hashlib.sha256(data).hexdigest(),
                    'slice_base': base, 'implementation_source': candidate,
                    'implementation_tree': git('rev-parse', candidate + '^{tree}').decode().strip(),
                    'receipt_candidate_tree': d['candidate_tree_sha'],
                    'declared_changed_paths': declared, 'scoped_author_paths': own,
                    'scoped_author_commits': own_commits,
                    'all_declared_implementation_commits': [commit_data(c) for c in impl],
                    'full_source_footprint_from_base198': full,
                    'carried_source_paths_not_owned': sorted(set(full) - set(own)),
                    'source_blob_bindings': bindings}

LATEST_INSTALLED = '5cd190d24d133f618fcc66ecc01f70c8a1b4f1f6'
B220_COMMITS = ['e2c4eb3142f329dfee798d22cea3ae1035306ab0',
                '2137961b0d3a2b39b85c5a57bf774777d2a4204e']
new_installed_paths = git('diff', '--name-only', BASE, LATEST_INSTALLED).decode().splitlines()
owned4 = topics['installed']['scoped_author_paths']
owned_patch = git('diff', '--binary', BASE, LATEST_INSTALLED, '--', *owned4)
for path in owned4:
    assert blob(LATEST_INSTALLED, path) == blob(topics['installed']['implementation_source'], path)
latest_installed = {'source_sha': LATEST_INSTALLED,
                   'tree': git('rev-parse', LATEST_INSTALLED + '^{tree}').decode().strip(),
                   'build_replay_outcome': 'UNRUN/pending; no new installed PASS claimed',
                   'published_reachability': 'branch head observed separately above; this source is not assumed published merely because a local Git object exists',
                   'owned_four_paths': owned4, 'owned_blobs_identical_to_ab56': True,
                   'full_source_footprint': new_installed_paths,
                   'carried_source_paths': sorted(set(new_installed_paths) - set(owned4)),
                   'owned_portable_patch': {'bytes': len(owned_patch),
                                             'sha256': hashlib.sha256(owned_patch).hexdigest(),
                                             'base': BASE, 'source': LATEST_INSTALLED,
                                             'canonical_diff_argv': ['git', 'diff', '--binary', BASE, LATEST_INSTALLED, '--', *owned4],
                                             'application': 'Only four owned paths after canonical dependencies; never apply full cumulative source diff.'},
                   'new_carried_commits': [commit_data(c) for c in [
                       'ac03ec44e0d1074fb609f35221b0c088522cdbd2',
                       '7fb1f5c243c18de89fb11a0f664ae07cb0801eb2',
                       '74c0355f07834c28527200f5827ac2ab352ac313', LATEST_INSTALLED]],
                   'B220_source_commits': [commit_data(c) for c in B220_COMMITS]}

overlaps = []
for a, b in itertools.combinations(topics, 2):
    common = sorted(set(topics[a]['scoped_author_paths']) & set(topics[b]['scoped_author_paths']))
    if common:
        overlaps.append({'left': a, 'right': b, 'paths': [
            {'path': p, 'left_blob': blob(topics[a]['implementation_source'], p),
             'right_blob': blob(topics[b]['implementation_source'], p)} for p in common]})

carry_comparisons = []
for label, left, right, paths in [
    ('DW423→graph6d', 'dowhy', 'graph', topics['dowhy']['declared_changed_paths']),
    ('DW423→installedab56', 'dowhy', 'installed', topics['dowhy']['declared_changed_paths']),
    ('graph6d→installedab56', 'graph', 'installed', topics['graph']['declared_changed_paths']),
    ('graph6d→consumerassembled745', 'graph', 'consumer', topics['graph']['declared_changed_paths']),
    ('API729→installedab56', 'api', 'installed', topics['api']['declared_changed_paths']),
]:
    l = topics[left]['implementation_source']
    r = receipts['consumer']['assembled_candidate_sha'] if right == 'consumer' else topics[right]['implementation_source']
    observations = [{'path': p, 'left_blob': blob(l, p), 'right_blob': blob(r, p)} for p in paths]
    for x in observations:
        x['equal'] = x['left_blob'] == x['right_blob']
    carry_comparisons.append({'label': label, 'left_source': l, 'right_source': r,
                              'complete_compared_paths': observations,
                              'different_paths': [x['path'] for x in observations if not x['equal']]})
for label, left_source, paths in [
    ('DW423→latestinstalled5cd', topics['dowhy']['implementation_source'], topics['dowhy']['declared_changed_paths']),
    ('graph6d→latestinstalled5cd', topics['graph']['implementation_source'], topics['graph']['declared_changed_paths']),
    ('B220source213→latestinstalled5cd', B220_COMMITS[-1],
     sorted(set().union(*(set(paths_of(c)) for c in B220_COMMITS)))),
]:
    observations = [{'path': p, 'left_blob': blob(left_source, p),
                     'right_blob': blob(LATEST_INSTALLED, p)} for p in paths]
    for x in observations:
        x['equal'] = x['left_blob'] == x['right_blob']
    carry_comparisons.append({'label': label, 'left_source': left_source,
                              'right_source': LATEST_INSTALLED,
                              'complete_compared_paths': observations,
                              'different_paths': [x['path'] for x in observations if not x['equal']]})

patch_ids = []
for carry in receipts['graph']['shared_dependency_carries']:
    pair = dict(carry)
    ids = []
    for c in [carry['original_author_sha'], carry['carried_sha']]:
        patch = git('show', '--format=', '--binary', c)
        p = subprocess.run(['git', 'patch-id', '--stable'], input=patch, capture_output=True)
        COMMANDS.append({'argv': ['git', 'patch-id', '--stable'], 'input_commit': c,
                         'input_patch_sha256': hashlib.sha256(patch).hexdigest(),
                         'exit_code': p.returncode, 'stdout': p.stdout.decode(), 'stderr': p.stderr.decode()})
        assert p.returncode == 0
        ids.append(p.stdout.decode().split()[0])
    pair.update(original_patch_id=ids[0], carried_patch_id=ids[1], equal=ids[0] == ids[1])
    patch_ids.append(pair)

stages = []
for name in ['cau', 'fit', 'rdd', 'economics', 'fry', 'lex', 'api']:
    stages.append({'stage': len(stages) + 1, 'owner': name,
                   'source_commits': topics[name]['scoped_author_commits'],
                   'mode': 'Review then cherry-pick only these implementation commits; source-only path fingerprint must match the scoped receipt. Do not cherry-pick metadata/receipt heads as source.',
                   'depends_on': ['base198'], 'limitations': 'Scientific/authority outcome stays per owner receipt; successful source transfer is not finding acceptance.'})
stages.append({'stage': 8, 'owner': 'dowhy', 'source_commits': topics['dowhy']['scoped_author_commits'],
               'depends_on': ['base198'], 'mode': 'Use the canonical eleven author commits through423 exactly once. Do not also take equivalent mirrored DW commits from graph/installed/consumer.'})
stages.append({'stage': 9, 'owner': 'graph/SCM', 'source_commits': topics['graph']['scoped_author_commits'],
               'depends_on': ['dowhy423'], 'mode': 'Apply only six author commits (07beb plus five SCM/facade commits); skip eleven DW carry commits with reconciled patch IDs. Whole scope35 paths, not49.'})
stages.append({'stage': 10, 'owner': 'consumer', 'source_commits': topics['consumer']['scoped_author_commits'],
               'depends_on': ['CAU selectedDiD', 'dowhy423', 'graph/SCMb692'],
               'mode': 'Use seven own consumer commits, or the committed own-seven-paths portable patch; never pick the complete cumulative root branch. Scope7 paths. The twelve scoped author path inventories have no overlaps; nevertheless reconcile downstream contract changes against the assembled provider source.',
               'portable_patch': receipts['consumer']['own_portable_patch'],
               'assembled_source': receipts['consumer']['assembled_candidate_sha']})
stages.append({'stage': 11, 'owner': 'installed', 'source_commits': topics['installed']['scoped_author_commits'],
               'depends_on': ['API729', 'dowhy423', 'graph/SCMb692'],
               'mode': 'Only1ebca076a6afb453096409d8b3d91bab94a8ac39 andab56a0f3414c6e903f7dcdaaa7b7ed540b1923c5, or the source5cd owned-four portable patch (same four owned blobs). Three formerly stale dependency blobs are fixed in5cd by carried commits; still skip these redundant carries after canonical provider admission. Rebuild wheel/sdist on the assembled G candidate; neither ab56 nor pending5cd receipts prove newFRY installation.',
               'latest_packaging_source': LATEST_INSTALLED, 'owned_portable_patch': latest_installed['owned_portable_patch']})
stages.append({'stage': 12, 'owner': 'graph_intake', 'source_commits': topics['graph_intake']['scoped_author_commits'],
               'depends_on': ['reviewed graph/SCM interfaces'],
               'mode': 'Apply only two canonical intake author commits and eight own paths; original bounded synthetic intake is distinct from pending B220 provider consumer.'})
stages.append({'stage': 13, 'owner': 'pending narrowB220 provider', 'source_commits': B220_COMMITS,
               'depends_on': ['explicit exact-source independent GO', 'graph/SCM', 'graph_intake'],
               'mode': 'LAST, conditional on exact independent GO. Canonical sourcee2c4 plus213compatibility fragment is identified and already carried into localinstalled5cd as74c035/5cd. Presence in an installed carrier is not provider acceptance; do not apply the duplicate carrier commits as well.',
               'outcome': 'UNRUN/pending'})

report = {'schema': 'policyos.e02.G_source_integration_order.v1',
          'recorded_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
          'scope': 'Read-only source ownership/overlap and finite conditional proposal. No checkout/source mutation, no G integration/publication, no code/finding acceptance, no main mutation.',
          'base_sha': BASE, 'base_tree': git('rev-parse', BASE + '^{tree}').decode().strip(),
          'actual_remote_ref_snapshot': remote_rows, 'selected_topic_count': len(topics),
          'path_denominator': 'Every declared path and every scoped author path from all12 exact primary receipts; complete Git diff againstbase198 and each slice base; all shared candidate blobs compared, not sampled.',
          'topics': topics, 'all_owned_path_overlaps': overlaps,
          'latest_installed_source_candidate': latest_installed,
          'dependency_carry_comparisons': carry_comparisons, 'DW_carry_patch_id_reconciliation': patch_ids,
          'proposed_source_order': stages,
          'separate_receipt_transport': 'Copy each exact authored receipt and content companions under its source-bound path separately after source review; preserve implementation SHA fields. Do not import complete cumulative source branches merely to obtain receipts.',
          'acceptance_guards': [
              'G re-fetches frozen refs; metadata-head drift requires receipt reread, source drift requires a new exact-source review.',
              'Before each source action check G branch attachment/cleanliness and complete owned diff; unexpected base or overlap is returned to canonical owner, never reset/rebase/force.',
              'Shared generated schema/public-surface and package docs are integrated from the combined source once; no old generated snapshot overwrites newer accepted owners.',
              'After upstream source contracts are assembled, rerun affected consumers and installed wheel/sdist checks on that exact new G SHA. Previous standalone/ab56 receipts stay bounded to their own source.',
              'All global FAIL/UNRUN/P41not_established, raw output warnings, real data gaps and production authority limits survive successful source integration.',
          ], 'commands': COMMANDS}
def compact_report(full, command_runner):
    """Keep immutable references, observed deltas and deciding checks, not Git-derived copies."""
    compact_topics = {}
    for name, topic in full['topics'].items():
        owned_diff = command_runner('diff', '--binary', topic['slice_base'],
                                    topic['implementation_source'], '--', *topic['scoped_author_paths'])
        full_diff = command_runner('diff', '--binary', BASE, topic['implementation_source'])
        compact_topics[name] = {
            'branch': topic['branch'], 'published_head': topic['published_head'],
            'published_tree': topic['published_tree'],
            'initial_observed_head': topic['initial_observed_head'],
            'observed_head_drift': topic['head_drift_since_initial_snapshot'],
            'receipt': {'locator': topic['receipt_path'] + '@' + topic['published_head'],
                        'bytes': topic['receipt_bytes'], 'sha256': topic['receipt_sha256']},
            'slice_base': topic['slice_base'], 'source': topic['implementation_source'],
            'source_tree': topic['implementation_tree'],
            'own_source_commits': topic['scoped_author_commits'],
            'own_paths_authority': 'Exact scoped paths in this receipt; for graph use author_only_implementation_commits, for installed use owned_changed_paths.',
            'own_path_count': len(topic['scoped_author_paths']),
            'declared_path_count': len(topic['declared_changed_paths']),
            'owned_delta': {'base': topic['slice_base'], 'source': topic['implementation_source'],
                            'path_scope': 'own_paths_authority', 'bytes': len(owned_diff),
                            'sha256': hashlib.sha256(owned_diff).hexdigest()},
            'cumulative_delta': {'base': BASE, 'source': topic['implementation_source'],
                                 'bytes': len(full_diff), 'sha256': hashlib.sha256(full_diff).hexdigest(),
                                 'path_count': len(topic['full_source_footprint_from_base198']),
                                 'note': 'Includes carried dependencies and any receipt companions; never an own source transfer.'},
            'source_tree_matches_receipt': topic['implementation_tree'] == topic['receipt_candidate_tree'],
            'published_owned_blobs_match_source': all(b['candidate_blob'] == b['published_blob'] for b in topic['source_blob_bindings']),
            'own_commits_touch_only_owned_paths': all(set(c['changed_paths']) <= set(topic['scoped_author_paths']) for c in topic['all_declared_implementation_commits'] if c['sha'] in topic['scoped_author_commits']),
        }
    comparisons = []
    for c in full['dependency_carry_comparisons']:
        comparisons.append({'label': c['label'], 'left_source': c['left_source'],
                            'right_source': c['right_source'],
                            'complete_path_count': len(c['complete_compared_paths']),
                            'different_paths': c['different_paths'],
                            'comparison': 'Every path in the relevant provider receipt changed_paths; B220 uses its two source commit deltas. Equal blobs are not copied as derived views.'})
    installed = full['latest_installed_source_candidate']
    patch = dict(installed['owned_portable_patch'])
    patch.pop('path', None)
    patch['canonical_diff_argv'] = ['git', 'diff', '--binary', BASE, installed['source_sha'], '--', *installed['owned_four_paths']]
    latest = {'source': installed['source_sha'], 'tree': installed['tree'],
              'new_installed_build_replay': 'PENDING/UNRUN; no new installed PASS claimed',
              'owned_four_source_locators': [p + '@' + installed['source_sha'] for p in installed['owned_four_paths']],
              'owned_blobs_identical_to_ab56': installed['owned_blobs_identical_to_ab56'],
              'portable_owned_four_delta': patch,
              'full_cumulative_delta': {'base': BASE, 'source': installed['source_sha'],
                                        'path_count': len(installed['full_source_footprint']),
                                        'bytes': len(command_runner('diff', '--binary', BASE, installed['source_sha']))},
              'source_carry_map': [
                  {'canonical': 'b69208e65b9dcfa4c7de690ace071abdc9c1fed6', 'mirror': 'ac03ec44e0d1074fb609f35221b0c088522cdbd2'},
                  {'canonical': '423165322e508a293ffd23918c039c99fb37e7a7', 'mirror': '7fb1f5c243c18de89fb11a0f664ae07cb0801eb2'},
                  {'canonical': B220_COMMITS[0], 'mirror': '74c0355f07834c28527200f5827ac2ab352ac313'},
                  {'canonical': B220_COMMITS[1], 'mirror': installed['source_sha']}],
              'publication': 'Exact observed remote installed head is above; local source reachability does not establish publication.'}
    latest_diff = command_runner('diff', '--binary', BASE, installed['source_sha'])
    latest['full_cumulative_delta']['sha256'] = hashlib.sha256(latest_diff).hexdigest()
    for pair in latest['source_carry_map']:
        patch_ids = []
        for sha in [pair['canonical'], pair['mirror']]:
            patch_bytes = command_runner('show', '--format=', '--binary', sha)
            result = subprocess.run(['git', 'patch-id', '--stable'], input=patch_bytes, capture_output=True)
            if result.returncode:
                raise RuntimeError(result.stderr.decode())
            patch_ids.append(result.stdout.decode().split()[0])
        pair['actual_stable_patch_id_equal'] = patch_ids[0] == patch_ids[1]
        assert pair['actual_stable_patch_id_equal'], pair
    proposed = []
    for stage in full['proposed_source_order']:
        s = dict(stage)
        for k in ['owned_portable_patch', 'source_commits']:
            s.pop(k, None)
        if stage['stage'] <= 7:
            s['commit_authority'] = 'topics.' + stage['owner'] + '.own_source_commits'
        elif stage['stage'] == 8:
            s['commit_authority'] = 'topics.dowhy.own_source_commits'
        elif stage['stage'] == 9:
            s['commit_authority'] = 'topics.graph.own_source_commits'
        elif stage['stage'] == 10:
            s['commit_authority'] = 'topics.consumer.own_source_commits'
            s['mode'] = 'Apply only seven own commits or source-bound portable patch. The twelve own scopes do not overlap; downstream provider contracts still require assembled-source checks.'
        elif stage['stage'] == 11:
            s['commit_authority'] = 'topics.installed.own_source_commits; alternatively latest_installed.portable_owned_four_delta'
        elif stage['stage'] == 12:
            s['commit_authority'] = 'topics.graph_intake.own_source_commits'
        else:
            s['source_commits'] = B220_COMMITS
        proposed.append(s)
    consumer = full['topics']['consumer']
    assembled = full['proposed_source_order'][9]['assembled_source']
    assembled_paths = command_runner('diff', '--name-only', consumer['slice_base'], assembled).decode().splitlines()
    return {'schema': full['schema'], 'recorded_at': full['recorded_at'], 'scope': full['scope'],
            'base_sha': BASE, 'base_tree': full['base_tree'],
            'actual_remote_ref_snapshot': full['actual_remote_ref_snapshot'],
            'topics': compact_topics,
            'owned_overlap_gate': {'outcome': 'PASS_BOUNDED_SOURCE_CUSTODY', 'topics': len(compact_topics),
                                   'own_scope_overlap_pairs': full['all_owned_path_overlaps'],
                                   'integration_actions': 0},
            'graph_scope': {'declared': 49, 'author_owned': 35, 'canonical_DW_carried': 14,
                            'additional_old_native_receipt_companions': 16},
            'consumer_assembled_scope': {'slice_base': consumer['slice_base'], 'source': assembled,
                                         'tree': command_runner('rev-parse', assembled + '^{tree}').decode().strip(),
                                         'total_paths': len(assembled_paths), 'own': 7, 'dependencies': 43,
                                         'path_authority': compact_topics['consumer']['receipt']['locator']},
            'dependency_carry_comparisons': comparisons,
            'DW_mirror_reconciliation': full['DW_carry_patch_id_reconciliation'],
            'latest_installed': latest, 'proposed_source_order': proposed,
            'separate_receipt_transport': full['separate_receipt_transport'],
            'acceptance_guards': full['acceptance_guards'],
            'audit_commands': {'cwd': REPO, 'observed_git_command_count': len(full['commands']),
                               'observed_nonzero_git_commands': sum(c['exit_code'] != 0 for c in full['commands']),
                               'exact_recipes': ['git ls-remote --heads origin refs/heads/codex/e02-F-*20261006*',
                                                 'git show <published_head>:<receipt_path>',
                                                 'git diff --binary <slice_base> <source> -- <receipt-scoped-own-paths>',
                                                 'git diff --binary <base198> <source>',
                                                 'git show --format= --name-only <own-source-commit>',
                                                 'git rev-parse <source>:<complete-provider-path>',
                                                 'git show --format= --binary <canonical-or-carry-commit> | git patch-id --stable'],
                               'retention': 'Complete deciding audit output is retained separately. Recomputable tracked receipts, source copies, equal-blob maps and individual rev-parse derived views are intentionally omitted.'}}

report = compact_report(report, git)
OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'path': str(OUT), 'bytes': OUT.stat().st_size,
                  'sha256': hashlib.sha256(OUT.read_bytes()).hexdigest(),
                  'topics': len(report['topics']), 'owned_path_overlap_pairs': len(report['owned_overlap_gate']['own_scope_overlap_pairs']),
                  'graph_author_paths': report['graph_scope']['author_owned'],
                  'installed_author_paths': report['topics']['installed']['own_path_count'],
                  'graph_DW_patch_ids_equal': all(x['equal'] for x in report['DW_mirror_reconciliation']),
                  'new_installed_patch_ids_equal': all(x['actual_stable_patch_id_equal'] for x in report['latest_installed']['source_carry_map']),
                  'integration_actions': 0}, indent=2))
