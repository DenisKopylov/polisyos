import datetime
import hashlib
import json
import pathlib
import subprocess

ROOT = pathlib.Path('/workspace/ORCH04-evidence/c11/b114-publication/independent-readback-20261008')
LOCAL = pathlib.Path('/workspace/ORCH04-C11')
REMOTE = ROOT / 'remote.git'
REF = 'refs/recovery/ORCH04-C11-independent-final-20261008/receipt-f425407e'
BASE = '0321633c0e6d9a87bccfbbe889a4998934c52dd3'
SOURCE = '03698439abfb1cb59f763397a182d8e0e393d40d'
HEAD = 'f425407e9f2228300905831d44bf179bb797e69d'
PRIOR = '4810a9c4eb4e2a3dc4bdaa946483fe93e86e8067'
PACKET = 'policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/D/recovery-20261008/B114-rejection-retention'
OLD_HANDOFF = 'policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/D/recovery-20261008/HANDOFF.json'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def git(where, *args):
    return subprocess.check_output(['git', '-C', str(where), *args])


def batch_blobs(where, requests):
    raw = subprocess.check_output(['git', '-C', str(where), 'cat-file', '--batch'], input=('\n'.join(requests) + '\n').encode())
    offset = 0
    result = []
    for request in requests:
        end = raw.index(b'\n', offset)
        header = raw[offset:end].decode().split()
        assert len(header) == 3 and header[1] == 'blob', (request, header)
        size = int(header[2])
        start = end + 1
        data = raw[start:start + size]
        assert raw[start + size:start + size + 1] == b'\n'
        result.append((header[0], data))
        offset = start + size + 1
    assert offset == len(raw)
    return result


assert git(LOCAL, 'rev-parse', 'HEAD').decode().strip() == HEAD
assert git(REMOTE, 'rev-parse', REF).decode().strip() == HEAD
assert not git(LOCAL, 'status', '--porcelain')
assert git(REMOTE, 'rev-list', '--parents', '-n', '1', HEAD).decode().split() == [HEAD, SOURCE]
assert not (REMOTE / 'objects/info/alternates').exists()
admission = json.loads((ROOT / 'admission.json').read_text())
assert admission['refs'] == '' and 'count: 0\n' in admission['objects'] and 'in-pack: 0\n' in admission['objects']

command_receipts = []
for name, directory in [('normal_topic_push', ROOT.parent / 'topic-push'), ('bare_init', ROOT / 'init'), ('remote_fetch', ROOT / 'fetch'), ('remote_fsck', ROOT / 'fsck'), ('complete_footprint_readback', ROOT / 'byte-readback')]:
    execution = json.loads((directory / 'execution.json').read_text())
    assert execution['exit_code'] == 0, (name, execution)
    stdout = (directory / 'stdout.txt').read_bytes()
    stderr = (directory / 'stderr.txt').read_bytes()
    if name == 'normal_topic_push':
        assert execution['argv'] == ['git', 'push', '--set-upstream', 'origin', 'codex/e02-C11-recovery-20261008']
        assert b'lefthook v2.1.6  hook: pre-push' in stdout
        assert b'tsc -p tsconfig.app.json --noEmit && tsc -p tsconfig.node.json --noEmit && tsc -p tsconfig.tools.json --noEmit' in stdout
        assert b'typecheck (39.23 seconds)' in stdout
        assert b'4810a9c4e..f425407e9' in stderr
    command_receipts.append({'name': name, 'directory': str(directory), 'argv': execution['argv'], 'pid': execution['pid'], 'exit_code': 0, 'start_utc': execution['start_utc'], 'finish_utc': execution['finish_utc'], 'wall_seconds': execution['wall_seconds'], 'files': [{'path': str(directory / filename), 'bytes': len((directory / filename).read_bytes()), 'sha256': sha((directory / filename).read_bytes())} for filename in ['execution.json', 'stdout.txt', 'stderr.txt']]})

readback = json.loads((ROOT / 'publication-readback.json').read_text())
assert readback['head'] == HEAD and readback['source'] == SOURCE
assert readback['source_footprint_count'] == 271 and readback['packet_index_file_count'] == 209
handoff = json.loads(git(REMOTE, 'show', HEAD + ':' + PACKET + '/HANDOFF.json'))
source_manifest_bytes = git(REMOTE, 'show', HEAD + ':' + PACKET + '/evidence/author/b114/source-freeze-final.json')
source_manifest = json.loads(source_manifest_bytes)
source_paths = git(LOCAL, 'diff', '--name-only', BASE, SOURCE).decode().splitlines()
assert set(source_paths) == {entry['path'] for entry in source_manifest['whole_footprint']}
assert len(source_paths) == 271
source_bytes = batch_blobs(REMOTE, [SOURCE + ':' + item['path'] for item in source_manifest['whole_footprint']])
for item, (blob, data) in zip(source_manifest['whole_footprint'], source_bytes):
    assert item['blob'] == blob and item['bytes'] == len(data) and item['sha256'] == sha(data), item['path']
delta_paths = git(REMOTE, 'diff', '--name-only', PRIOR, SOURCE).decode().splitlines()
assert sorted(delta_paths) == sorted(handoff['delta_paths']) == sorted(source_manifest['delta_paths']) and len(delta_paths) == 4

index_bytes = git(REMOTE, 'show', HEAD + ':' + PACKET + '/evidence/artifact-index.json')
index = json.loads(index_bytes)
assert len(index['artifacts']) == 209
indexed_blobs = batch_blobs(REMOTE, [HEAD + ':' + item['path'] for item in index['artifacts']])
indexed_results = []
for item, (blob, data) in zip(index['artifacts'], indexed_blobs):
    assert sha(data) == item['sha256'] and len(data) == item['bytes']
    assert data == (LOCAL / item['path']).read_bytes(), item['path']
    indexed_results.append({'path': item['path'], 'blob': blob, 'sha256': sha(data), 'bytes': len(data), 'actual_remote_local_bytes_equal': True})

packet_paths = git(REMOTE, 'ls-tree', '-r', '--name-only', HEAD, '--', PACKET).decode().splitlines()
packet_local = batch_blobs(LOCAL, [HEAD + ':' + path for path in packet_paths])
packet_remote = batch_blobs(REMOTE, [HEAD + ':' + path for path in packet_paths])
packet_results = []
for path, (local_blob, local_data), (remote_blob, remote_data) in zip(packet_paths, packet_local, packet_remote):
    assert local_blob == remote_blob and local_data == remote_data == (LOCAL / path).read_bytes(), path
    packet_results.append({'path': path, 'blob': remote_blob, 'bytes': len(remote_data), 'sha256': sha(remote_data)})
receipt_delta_paths = git(REMOTE, 'diff', '--name-only', SOURCE, HEAD).decode().splitlines()
assert set(receipt_delta_paths) == set(packet_paths)
assert all(path.startswith(PACKET + '/') for path in receipt_delta_paths)

old_versions = [git(LOCAL, 'show', PRIOR + ':' + OLD_HANDOFF), git(LOCAL, 'show', HEAD + ':' + OLD_HANDOFF), git(REMOTE, 'show', PRIOR + ':' + OLD_HANDOFF), git(REMOTE, 'show', HEAD + ':' + OLD_HANDOFF), (LOCAL / OLD_HANDOFF).read_bytes()]
assert all(data == old_versions[0] for data in old_versions)
old_handoff_sha = sha(old_versions[0])
assert old_handoff_sha == handoff['prior_complete_receipt']['handoff_sha256'] == 'aa57953583fc3c2c356bf339b1dad8a8e449d75325a17691f3d71bee551a8a7a'

lineage = []
for commit in [BASE] + git(REMOTE, 'rev-list', '--reverse', BASE + '..' + HEAD).decode().splitlines():
    commit_bytes = git(REMOTE, 'cat-file', 'commit', commit)
    assert commit_bytes == git(LOCAL, 'cat-file', 'commit', commit)
    tree = git(REMOTE, 'rev-parse', commit + '^{tree}').decode().strip()
    tree_bytes = git(REMOTE, 'cat-file', 'tree', tree)
    assert tree_bytes == git(LOCAL, 'cat-file', 'tree', tree)
    parents = git(REMOTE, 'rev-list', '--parents', '-n', '1', commit).decode().split()[1:]
    assert parents == git(LOCAL, 'rev-list', '--parents', '-n', '1', commit).decode().split()[1:]
    recursive_tree = git(REMOTE, 'ls-tree', '-r', '-z', commit)
    assert recursive_tree == git(LOCAL, 'ls-tree', '-r', '-z', commit)
    lineage.append({'commit': commit, 'tree': tree, 'parents': parents, 'commit_sha256': sha(commit_bytes), 'tree_sha256': sha(tree_bytes), 'recursive_tree_mode_type_blob_path_sha256': sha(recursive_tree), 'recursive_tree_entries': recursive_tree.count(b'\x00'), 'local_remote_commit_tree_parents_recursive_tree_equal': True})
assert [item['commit'] for item in lineage[1:-1]] == handoff['append_only_lineage']
assert source_manifest['append_only_lineage'] == handoff['append_only_lineage']
assert handoff['source'] == SOURCE and handoff['tree'] == 'dde25e8efa4a8ce5322bdcad176720fa0894a635'
assert handoff['parents'] == ['53a7cb99e4636e3cdfa903e22743e0a9b19a62a7']

result = {
    'schema': 'orch04.C11.B114.independent-normal-publication-verification.v1',
    'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'verifier': '/root/verify_c11_publication',
    'status': 'PASS exact remote bytes and append-only lineage; enabled-hook ordinary topic publication',
    'remote': 'https://github.com/DenisKopylov/polisyos.git',
    'branch': 'codex/e02-C11-recovery-20261008',
    'remote_db': str(REMOTE),
    'new_remote_ref': REF,
    'empty_ODB_admission': {'path': str(ROOT / 'admission.json'), 'sha256': sha((ROOT / 'admission.json').read_bytes()), 'objects_count': 0, 'refs_count': 0, 'alternates_present': False},
    'source': SOURCE,
    'source_tree': handoff['tree'],
    'source_parents': handoff['parents'],
    'receipt': HEAD,
    'receipt_tree': git(REMOTE, 'rev-parse', HEAD + '^{tree}').decode().strip(),
    'receipt_parents': [SOURCE],
    'source_footprint_count': 271,
    'source_footprint_manifest_sha256': sha(source_manifest_bytes),
    'owned_delta_count': 4,
    'owned_delta_paths': delta_paths,
    'complete_receipt_packet_file_count': len(packet_paths),
    'indexed_deciding_evidence_file_count': 209,
    'indexed_deciding_evidence_bytes': sum(item['bytes'] for item in indexed_results),
    'final_head_G_footprint_count': readback['final_head_footprint_count'],
    'old_parent_handoff': {'path': OLD_HANDOFF, 'prior_receipt': PRIOR, 'sha256': old_handoff_sha, 'prior_local_remote_final_local_remote_worktree_equal': True},
    'lineage': lineage,
    'command_receipts': command_receipts,
    'receipt_packet': packet_results,
    'indexed_evidence': indexed_results,
    'limits': 'Read-only publication/source byte identity verification. No tests rerun; no source or receipt edits; no source acceptance, formal G closure, production claim or portable replay. Prior receipt pending publication text remains historical; this external proof records actual normal push and readback.'
}
(ROOT / 'independent-verification.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps({key: result[key] for key in ['status', 'source', 'source_tree', 'receipt', 'receipt_tree', 'source_footprint_count', 'owned_delta_count', 'complete_receipt_packet_file_count', 'indexed_deciding_evidence_file_count', 'final_head_G_footprint_count']}))
