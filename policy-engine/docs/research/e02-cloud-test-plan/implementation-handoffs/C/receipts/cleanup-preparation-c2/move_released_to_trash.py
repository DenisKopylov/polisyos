"""Move released, exact C repeatable directories to Trash; retain evidence."""
import hashlib
import json
import os
import stat
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

def require(condition, message='Cleanup precondition failed'):
    if not condition:
        raise RuntimeError(message)

if sys.flags.optimize:
    raise RuntimeError('Optimized mode is not admitted for the cleanup entrypoint')

ROOT = Path('/Users/deniskopylov/.codex/worktrees/e02-c-continuation-20261006/polisyos')
TRASH = Path('/Users/deniskopylov/.Trash')
selection_path, release_path, output_path = map(Path, sys.argv[1:4])
CLEANUP = ROOT / '.tmp/e02-C2/raw/cleanup'
require(output_path.is_absolute() and output_path.parent == CLEANUP, 'Receipt path outside fixed C cleanup directory')
require(not os.path.lexists(output_path), 'Existing output receipt cannot be overwritten')
journal_path = output_path.with_suffix('.intent.jsonl')
require(not os.path.lexists(journal_path), 'Existing recovery journal cannot be overwritten')
selection_bytes = selection_path.read_bytes()
selection = json.loads(selection_bytes)
release = json.loads(release_path.read_text())
require(release['selection_sha256'] == hashlib.sha256(selection_bytes).hexdigest(), 'Cleanup precondition failed')
require(release['all_deciding_outputs_and_useful_changes_committed'] is True, 'Cleanup precondition failed')
require(release['owning_audits_complete'] is True, 'Cleanup precondition failed')
require(release['user_authorization'] == 'E02 continuation: repeatable test directories and used environments to Trash only', 'Cleanup precondition failed')
require(release['permanent_deletion'] is False, 'Cleanup precondition failed')
require(selection['decision'] == 'RELEASE_EXACT_CANDIDATES_TO_TRASH', 'Cleanup precondition failed')
require(selection['trash_authorized_now'] is True, 'Cleanup precondition failed')
items = selection['candidate_items']
require(len(items) == selection['candidate_count'], 'Cleanup precondition failed')
require(len({item['path'] for item in items}) == len(items), 'Cleanup precondition failed')
released = set(release['released_paths'])
require(released <= {item['path'] for item in items}, 'Cleanup precondition failed')
trash_stat = TRASH.lstat()
require(stat.S_ISDIR(trash_stat.st_mode) and trash_stat.st_uid == os.getuid(), 'Cleanup precondition failed')
target = TRASH / release['trash_directory_name']
require(target.parent == TRASH and (not target.exists()), 'Cleanup precondition failed')
require(target.name.startswith('e02-C-20261006-'), 'Cleanup precondition failed')
receipt = {'schema': 'policyos.e02.C.trash_cleanup.v1', 'selection_sha256': hashlib.sha256(selection_bytes).hexdigest(), 'release_sha256': hashlib.sha256(release_path.read_bytes()).hexdigest(), 'started_utc': datetime.now(timezone.utc).isoformat(), 'trash_directory': str(target), 'permanent_deletion': False, 'trash_emptied': False, 'moves': [], 'skips': [], 'complete': False}

def save():
    output_path.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + '\n')
prepared = []
admission_ref = release['admission_index_git_ref']
admission_data = subprocess.check_output(['git', 'show', admission_ref['commit'] + ':' + admission_ref['path']], cwd=ROOT)
require(hashlib.sha256(admission_data).hexdigest() == '3cf2f83e138d8b2558300ceb16822f2d1873c0283c6d0621d70377972e6b799a', 'Unrecognized complete admission index')
admission = json.loads(admission_data)
admitted = {row['requested']['path']: row['requested']['branch'] for row in admission['entries'] + admission['root_pair_existing_receipts']}
require(set(admitted) == set(release['exact_admitted_C_roots']), 'Release root set differs from complete Git admission inventory')
require({lane['worktree'] for lane in release['frozen_topics']} == set(admitted), 'Freeze omits an admitted C root')
def verify_git_ref(ref):
    data = subprocess.check_output(['git', 'show', ref['commit'] + ':' + ref['path']], cwd=ROOT)
    require(hashlib.sha256(data).hexdigest() == ref['sha256'], 'Git provenance content drift')
    require(len(data) == ref['bytes'], 'Git provenance length drift')
    return (ref['commit'], ref['path'], ref['sha256'], ref['bytes'])

retained_refs = {verify_git_ref(ref) for ref in release['retained_evidence_git_refs']}
require(retained_refs, 'Retained Git evidence missing')
for lane in release['frozen_topics']:
    cwd = Path(lane['worktree'])
    require(lane['branch'] == admitted[str(cwd)], 'Frozen branch differs from admitted pair')
    require(cwd in {Path(p) for p in release['exact_admitted_C_roots']}, 'Cleanup precondition failed')
    require(subprocess.check_output(['git', 'symbolic-ref', '-q', '--short', 'HEAD'], cwd=cwd).decode().strip() == lane['branch'], 'Cleanup precondition failed')
    require(subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=cwd).decode().strip() == lane['head'], 'Cleanup precondition failed')
    require(not subprocess.check_output(['git', 'status', '--porcelain'], cwd=cwd), 'Cleanup precondition failed')
for index, item in enumerate(items):
    path = Path(item['path'])
    if str(path) not in released:
        receipt['skips'].append({'path': str(path), 'reason': 'not released'})
        continue
    require(item['status_now'] == 'RELEASED_TO_TRASH', 'Cleanup precondition failed')
    require(item['trash_authorized_now'] is True, 'Cleanup precondition failed')
    require(item['category'] in {'private_python_environment', 'installed_python_environment', 'private_build_environment', 'node_modules', 'pytest_cache', 'ruff_cache'}, 'Code/source extraction or unknown category is preserve-only')
    require(item['actual_run_provenance_git_refs'], 'Actual environment/cache use provenance missing')
    for ref_id in item['actual_run_provenance_git_refs']:
        require(ref_id in selection['git_run_provenance_ref_index'], 'Unresolved run provenance ID')
        ref = selection['git_run_provenance_ref_index'][ref_id]
        require(verify_git_ref(ref) in retained_refs, 'Candidate run proof is not retained in release Git evidence')
    owner = Path(item['owning_worktree'])
    require(path == path.resolve(strict=True), 'Noncanonical cleanup path')
    require(owner == owner.resolve(strict=True), 'Noncanonical owning worktree')
    require(owner in {Path(p) for p in release['exact_admitted_C_roots']}, 'Cleanup precondition failed')
    require(path.is_relative_to(owner) and path != owner, 'Cleanup precondition failed')
    require(path.is_relative_to(Path('/Users/deniskopylov/.codex/worktrees')), 'Cleanup precondition failed')
    require(item['gitignored'] is True and item['type'] == 'directory', 'Cleanup precondition failed')
    require(not any((part in {'production_data', 'raw_data'} for part in path.parts)), 'Cleanup precondition failed')
    info = path.lstat()
    require(info.st_ino == item['initial_lstat']['inode'] and info.st_dev == item['initial_lstat']['device'], 'Candidate changed since fresh inventory')
    require(stat.S_ISDIR(info.st_mode) and info.st_uid == os.getuid(), 'Cleanup precondition failed')
    require(not path.is_symlink() and info.st_dev == trash_stat.st_dev, 'Cleanup precondition failed')
    for parent in path.parents:
        if parent == owner.parent:
            break
        require(not parent.is_symlink(), 'Cleanup precondition failed')
    relative = path.relative_to(owner)
    tracked = subprocess.run(['git', 'ls-files', '--', str(relative)], cwd=owner, capture_output=True, check=True)
    require(not tracked.stdout, (path, tracked.stdout))
    ignored = subprocess.run(['git', 'check-ignore', '--', str(relative)], cwd=owner, capture_output=True)
    require(ignored.returncode == 0, 'Cleanup precondition failed')
    refs = item['preserve_ref_paths']
    for reference in refs:
        p = Path(reference)
        require(p.exists(), reference)
        require(p != path and (not p.is_relative_to(path)), (path, reference))
        identity = release['preserve_identities'][reference]
        present = p.lstat()
        require(present.st_ino == identity['inode'] and present.st_dev == identity['device'], 'Preserved reference identity drift')
        if identity.get('sha256') is not None:
            require(hashlib.sha256(p.read_bytes()).hexdigest() == identity['sha256'], 'Preserved reference content drift')
    destination = target / f'{index:03d}-{owner.parent.name}-{path.name}'
    prepared.append((path, destination, info, item, refs))
require(not any((a != b and (a.is_relative_to(b) or b.is_relative_to(a)) for a, *_ in prepared for b, *_ in prepared)), 'Cleanup precondition failed')
output_fd = os.open(output_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
os.close(output_fd)
journal = open(journal_path, 'x', encoding='utf-8')
save()
target.mkdir(mode=448)
for path, destination, before, item, refs in prepared:
    current = path.lstat()
    require(current.st_ino == before.st_ino and current.st_dev == before.st_dev, 'Cleanup precondition failed')
    require(stat.S_ISDIR(current.st_mode) and current.st_uid == before.st_uid, 'Cleanup precondition failed')
    require(not destination.exists(), 'Cleanup precondition failed')
    intent = {'original_path': str(path), 'trash_path': str(destination), 'device': before.st_dev, 'inode': before.st_ino, 'state': 'intent_before_rename', 'utc': datetime.now(timezone.utc).isoformat()}
    journal.write(json.dumps(intent) + '\n')
    journal.flush()
    os.fsync(journal.fileno())
    path.rename(destination)
    after = destination.lstat()
    require(not path.exists() and after.st_ino == before.st_ino, 'Cleanup precondition failed')
    require(after.st_dev == before.st_dev and stat.S_ISDIR(after.st_mode), 'Cleanup precondition failed')
    require(all((Path(p).exists() for p in refs)), 'Cleanup precondition failed')
    for reference in refs:
        identity = release['preserve_identities'][reference]
        present = Path(reference).lstat()
        require(present.st_ino == identity['inode'] and present.st_dev == identity['device'], 'Post-move preserved reference identity drift')
        if identity.get('sha256') is not None:
            require(hashlib.sha256(Path(reference).read_bytes()).hexdigest() == identity['sha256'], 'Post-move preserved reference content drift')
    journal.write(json.dumps({**intent, 'state': 'rename_readback_confirmed'}) + '\n')
    journal.flush()
    os.fsync(journal.fileno())
    receipt['moves'].append({'original_path': str(path), 'trash_path': str(destination), 'category': item['category'], 'owner_uid': after.st_uid, 'device': after.st_dev, 'inode': after.st_ino, 'source_absent_and_destination_inode_matches': True, 'preserved_refs_exist_after': refs, 'moved_utc': datetime.now(timezone.utc).isoformat()})
    save()
receipt['complete'] = True
receipt['recovery_journal'] = str(journal_path)
receipt['recovery_rule'] = 'For each durable intent without confirmation, compare the recorded device/inode at original and Trash destination. Never rerun a rename blindly or permanently delete either path.'
receipt['completed_utc'] = datetime.now(timezone.utc).isoformat()
save()
journal.close()
print(json.dumps({'moved': len(receipt['moves']), 'skipped': len(receipt['skips']), 'receipt': str(output_path), 'complete': True}))
