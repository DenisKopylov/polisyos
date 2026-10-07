"""Independent V5 tiny transport intake and stored+decoded custody controls."""
from pathlib import Path
import copy, gzip, hashlib, json, os, subprocess, time
from collections import Counter
OUT = Path(__file__).resolve().parent
DESIGN = Path('/tmp/e02-F-continuation-20261007/fit-tmle/root-final-transport-design')
PYTHON = '/workspace/e02-F-closeout-20261006/policy-engine/.venv/bin/python'
REPO = '/workspace/e02-F-api-20261006'
SOURCE = '519e4822f608cbe4e7ac1ee7b01f6c29cb84bc82'
EXPECTED = {'refresh_selection_v5.py': '1ed83f18c764e2dd74234580d8cb88d9c24d55118e1d4b29a08b24280686048d', 'publish_transport_v5.py': '39c07c78cc45087d3e4552b9d6de6a62788f43bae31fa89c4da1e1733ecaefa2', 'transport_text_policy.py': '2d332a9099f212564d14ce3a0b5f3b8515eb34148611ebfc41bb1af76ef2101a'}
def digest(body): return hashlib.sha256(body).hexdigest()
def ref(path):
    path = Path(path); body = path.read_bytes()
    return {'path': str(path), 'bytes': len(body), 'sha256': digest(body)}
def write(path, obj): path.write_text(json.dumps(obj, indent=2) + '\n')
def guard():
    for name, sha in EXPECTED.items(): assert ref(DESIGN / name)['sha256'] == sha, name
RECORDS = []
def capture(label, argv):
    env = os.environ.copy(); env.pop('PYTHONPATH', None); env['PYTHONDONTWRITEBYTECODE'] = '1'
    start = time.monotonic(); p = subprocess.run(argv, cwd=OUT, env=env, capture_output=True)
    row = {'label': label, 'argv': argv, 'cwd': str(OUT), 'environment': {'PYTHONPATH': 'absent', 'PYTHONDONTWRITEBYTECODE': '1'}, 'exit_code': p.returncode, 'seconds': time.monotonic() - start}
    for name, body in [('stdout', p.stdout), ('stderr', p.stderr)]:
        path = OUT / (label + '.' + name + '.txt'); path.write_bytes(body); row[name] = ref(path)
    RECORDS.append(row); write(OUT / 'executions.json', RECORDS); return row
seed = OUT / 'seed.json'; prior = OUT / 'prior.json'; stage = OUT / 'prior-stage'; stage.mkdir()
write(seed, {'logical_files': [], 'pending_extensions': [], 'existing_declared_git_references': [], 'source_window': {'scope': 'Small standalone transport fixture, not scientific evidence'}, 'selection_inputs': [], 'policy': {'sanitation': 'none'}, 'draft': False})
write(prior, {'files': [], 'aliases': [], 'existing_git_files': []})
raw = b'alpha  \r\nbeta\n\n'; a = OUT / 'a.gz'; b = OUT / 'b.gz'; c = OUT / 'c.gz'; identity = OUT / 'identity.txt'
a.write_bytes(gzip.compress(raw, mtime=0)); b.write_bytes(gzip.compress(raw, mtime=7)); c.write_bytes(a.read_bytes()); identity.write_bytes(raw)
assert a.read_bytes() != b.read_bytes() and gzip.decompress(a.read_bytes()) == gzip.decompress(b.read_bytes()) == raw
base = ref(a) | {'encoding': 'gzip', 'decoded_bytes': len(raw), 'decoded_sha256': digest(raw)}
second = ref(b) | {'encoding': 'gzip', 'decoded_bytes': len(raw), 'decoded_sha256': digest(raw)}
results = []; guard()
def refresh(label, obj, extras=()):
    selection = OUT / (label + '.input.json'); write(selection, obj); output = OUT / (label + '.selected.json')
    argv = [PYTHON, str(DESIGN / 'refresh_selection_v5.py'), '--seed-selection', str(seed), '--prior-manifest', str(prior), '--prior-staging-root', str(stage), '--repository', REPO, '--final-source-sha', SOURCE, '--output', str(output), '--include-selection', label + '=' + str(selection), *extras]
    return capture(label + '-refresh', argv), output

def publish(label, selection, materialize=False):
    argv = [PYTHON, str(DESIGN / 'publish_transport_v5.py'), '--selection', str(selection), '--repository', REPO]
    dest = OUT / ('materialized-' + label)
    if materialize: argv += ['--materialize', '--destination', str(dest)]
    return capture(label + '-publish', argv), dest

def refused(label, obj):
    record, path = refresh(label, obj)
    assert record['exit_code'] != 0 and not path.exists(), label
    results.append({'case': label, 'outcome': 'PASS', 'invalid_input_refused': True, 'actual_exit': record['exit_code']})

for schema in ['files', 'items', 'selection']:
    for encoding in ['gzip', 'gzip-lossless']:
        label = 'valid-' + schema + '-' + encoding
        record, path = refresh(label, {schema: [base | {'encoding': encoding}]}); assert record['exit_code'] == 0
        selected = json.loads(path.read_text()); row = next(r for r in selected['logical_files'] if r['original_path'] == str(a))
        assert row['input_encoding'] == 'gzip' and row['input_binding'] == {'bytes': base['bytes'], 'sha256': base['sha256']}
        assert row['bytes'] == len(raw) and row['sha256'] == digest(raw)
        record, dest = publish(label, path, True); assert record['exit_code'] == 0
        copied = (dest / row['target_path']).read_bytes()
        assert copied == a.read_bytes() and gzip.decompress(copied) == raw
        manifest = json.loads((dest / 'policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/F/continuation-closeout-20261007/artifact-transports.json').read_text())
        transported = next(r for r in manifest['files'] if r['original_path'] == str(a))
        assert transported['input_binding'] == row['input_binding'] and transported['input_encoding'] == 'gzip'
        results.append({'case': label, 'outcome': 'PASS', 'full_stored_and_decoded_exact': True, 'stored_domain_and_binding_retained': True})
for label, mutator in [('bad-stored-sha', lambda r: r.update(sha256='0' * 64)), ('bad-stored-size', lambda r: r.update(bytes=r['bytes'] + 1)), ('bad-decoded-sha', lambda r: r.update(decoded_sha256='0' * 64)), ('bad-decoded-size', lambda r: r.update(decoded_bytes=r['decoded_bytes'] + 1)), ('missing-decoded-identity', lambda r: r.pop('decoded_sha256')), ('unknown-encoding', lambda r: r.update(encoding='brotli')), ('unknown-codec', lambda r: r.update(codec='brotli')), ('contradictory-codec', lambda r: r.update(codec='identity'))]:
    row = copy.deepcopy(base); mutator(row); refused(label, {'files': [row]})
codec = copy.deepcopy(base); codec.pop('encoding'); codec['codec'] = 'gzip lossless'; codec['decoded_sha256'] = '0' * 64
refused('codec-only-wrong-decoded', {'files': [codec]})
codec_correct = copy.deepcopy(base); codec_correct.pop('encoding'); codec_correct['codec'] = 'gzip lossless'
refused('codec-only-correct-decoded', {'files': [codec_correct]})
refused('ambiguous', {'files': [base], 'items': [base]})
for label, mutate in [('identity-false-decoded', lambda r: r.update(decoded_sha256='0' * 64)), ('identity-incomplete-decoded', lambda r: r.pop('decoded_sha256'))]:
    row = ref(identity) | {'encoding': 'identity', 'decoded_bytes': len(raw), 'decoded_sha256': digest(raw)}; mutate(row); refused(label, {'files': [row]})
record, path = refresh('identity-valid-decoded', {'files': [ref(identity) | {'encoding': 'identity', 'decoded_bytes': len(raw), 'decoded_sha256': digest(raw)}]}); assert record['exit_code'] == 0
record, dest = publish('identity-valid-decoded', path, True); assert record['exit_code'] == 0
row = next(r for r in json.loads(path.read_text())['logical_files'] if r['original_path'] == str(identity))
assert row['encoding'] == 'gzip' and gzip.decompress((dest / row['target_path']).read_bytes()) == raw
results.append({'case': 'identity-valid-decoded', 'outcome': 'PASS', 'whitespace_and_CRLF_not_normalized': True})

record, different_path = refresh('different-stored-same-decoded', {'files': [base, second]}); assert record['exit_code'] == 0
selected = json.loads(different_path.read_text()); row_a = next(r for r in selected['logical_files'] if r['original_path'] == str(a)); row_b = next(r for r in selected['logical_files'] if r['original_path'] == str(b))
assert row_a['disposition'] == row_b['disposition'] == 'transport'
record, dest = publish('different-stored-same-decoded', different_path, True); assert record['exit_code'] == 0
assert (dest / row_a['target_path']).read_bytes() == a.read_bytes() and (dest / row_b['target_path']).read_bytes() == b.read_bytes()
manifest = json.loads((dest / 'policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/F/continuation-closeout-20261007/artifact-transports.json').read_text())
assert not any(r['original_path'] in {str(a), str(b)} for r in manifest['aliases'])
assert manifest['counts']['decoded_unique_bytes'] == sum(r['decoded_bytes'] for r in manifest['files']) and 'distinct stored custody object' in manifest['decoded_count_scope']
results.append({'case': 'different-stored-same-decoded', 'outcome': 'PASS', 'both_distinct_containers_exactly_transportable': True, 'count_scope_explicit_per_custody_object': True})

record, alias_path = refresh('identical-stored-and-decoded', {'items': [base, ref(c) | {'encoding': 'gzip-lossless', 'decoded_bytes': len(raw), 'decoded_sha256': digest(raw)}]}); assert record['exit_code'] == 0
selected_alias = json.loads(alias_path.read_text()); alias_row = next(r for r in selected_alias['logical_files'] if r['original_path'] == str(c)); assert alias_row['disposition'] == 'alias'
record, dest = publish('identical-stored-and-decoded', alias_path, True); assert record['exit_code'] == 0
manifest = json.loads((dest / 'policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/F/continuation-closeout-20261007/artifact-transports.json').read_text())
alias = next(r for r in manifest['aliases'] if r['original_path'] == str(c)); assert alias['input_encoding'] == 'gzip' and alias['input_binding'] == {'bytes': base['bytes'], 'sha256': base['sha256']} and (dest / alias['stored_path']).read_bytes() == c.read_bytes()
results.append({'case': 'identical-stored-and-decoded', 'outcome': 'PASS', 'valid_alias_full_both_domain_binding_retained': True, 'one_stored_object_for_identical_inputs': True})
# Keep alias markers and all decoded quantities, change only source custody basis.
for label, mutation in [('forged-decoded-only-alias', lambda row: row.update(disposition='alias', canonical_original_path=str(a))), ('forged-input-binding', lambda row: row['input_binding'].update(sha256='0' * 64))]:
    altered = copy.deepcopy(selected); row = next(r for r in altered['logical_files'] if r['original_path'] == str(b)); mutation(row); bad = OUT / (label + '.selected.json'); write(bad, altered)
    record, _ = publish(label, bad); assert record['exit_code'] != 0
    results.append({'case': label, 'outcome': 'PASS', 'forged_stored_basis_refused': True, 'actual_exit': record['exit_code']})
# The publisher must not drop stored binding from a compressed alias.
altered = copy.deepcopy(selected_alias); row = next(r for r in altered['logical_files'] if r['original_path'] == str(c)); row.pop('input_encoding'); row.pop('input_binding'); bad = OUT / 'stripped-alias-binding.selected.json'; write(bad, altered)
record, _ = publish('stripped-alias-binding', bad); assert record['exit_code'] != 0
results.append({'case': 'stripped-alias-binding', 'outcome': 'PASS', 'unbound_alias_refused': True, 'actual_exit': record['exit_code']})

future_spec = OUT / 'future-git-spec.json'; write(future_spec, [{'git_ref': 'f' * 40, 'path': 'AGENTS.md', 'bytes': 0, 'sha256': digest(b''), 'remote_ref': 'refs/remotes/origin/codex/e02-integration'}])
record, path = refresh('future-git-refusal', {'files': [base]}, ['--existing-git-spec', str(future_spec)]); assert record['exit_code'] != 0 and not path.exists(); results.append({'case': 'future-git-refusal', 'outcome': 'PASS', 'unknown_Git_ref_refused': True})
# Self-output cannot be one of its own frozen inputs.
recursive_path = OUT / 'recursive.selected.json'; recursive_path.write_text('{}\n')
argv = [PYTHON, str(DESIGN / 'refresh_selection_v5.py'), '--seed-selection', str(seed), '--prior-manifest', str(prior), '--prior-staging-root', str(stage), '--repository', REPO, '--final-source-sha', SOURCE, '--output', str(recursive_path), '--include-file', str(recursive_path)]
record = capture('recursive-output', argv); assert record['exit_code'] != 0 and recursive_path.read_bytes() == b'{}\n'; results.append({'case': 'recursive-output', 'outcome': 'PASS', 'self_output_refused_without_overwrite': True})
guard(); write(OUT / 'results.json', {'source_guard': EXPECTED, 'science_tests_run': False, 'Git_or_product_writes': False, 'input_payload_bytes': len(raw), 'results': results, 'actual_control_counts': dict(Counter(r['outcome'] for r in results)), 'command_count': len(RECORDS)})
print(json.dumps({'cases': len(results), 'outcomes': dict(Counter(r['outcome'] for r in results)), 'commands': len(RECORDS)}, indent=2))
