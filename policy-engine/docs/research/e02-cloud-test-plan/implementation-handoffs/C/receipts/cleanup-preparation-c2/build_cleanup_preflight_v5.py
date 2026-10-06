"""Build a read-only, no-action cleanup preflight from C evidence."""
from __future__ import annotations

import hashlib
import json
import os
import stat
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path('/Users/deniskopylov/.codex/worktrees/e02-c-continuation-20261006/polisyos')
CLEANUP = ROOT / '.tmp/e02-C2/raw/cleanup'
ELIGIBILITY = CLEANUP / 'eligible-env-cache-v2.json'
SELECTION_V4 = CLEANUP / 'cleanup-selection-v4-unreleased.json'
PROVENANCE = ROOT / 'policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/C/receipts/cleanup-provenance-c2/index.json'
MOVER = CLEANUP / 'move_released_to_trash.py'
ADMISSION_REL = 'policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/C/receipts/admission-c2/index.json'
FINAL54_REL = 'policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/C/receipts/final54-c2'
COVERAGE_REL = 'policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/C/receipts/coverage-c2'
EXPECTED_MOVER_SHA256 = '5dfe312ea92a95956046291a9d8bd776aa8e610b6ad70e952c077d4cf0efa611'
EXPECTED_ADMISSION_SHA256 = '3cf2f83e138d8b2558300ceb16822f2d1873c0283c6d0621d70377972e6b799a'


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def git(*args: str, cwd: Path = ROOT) -> bytes:
    return subprocess.check_output(['git', *args], cwd=cwd)


def git_ref(commit: str, path: str, digest: str, byte_count: int) -> dict[str, Any]:
    """Resolve and verify one immutable Git path reference."""
    data = git('show', f'{commit}:{path}')
    require(sha256(data) == digest, f'Git SHA mismatch for {commit}:{path}')
    require(len(data) == byte_count, f'Git byte-count mismatch for {commit}:{path}')
    return {'commit': commit, 'path': path, 'sha256': digest, 'bytes': byte_count}


def nofollow_identity(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    """Capture lstat and file digest without traversing a symlink."""
    if not path.is_absolute() or Path(os.path.normpath(str(path))) != path:
        return None, 'path_not_canonical_absolute'
    current = Path(path.anchor)
    for part in path.parts[1:-1]:
        current = current / part
        try:
            parent = current.lstat()
        except FileNotFoundError:
            return None, 'parent_missing'
        if stat.S_ISLNK(parent.st_mode):
            return None, 'symlink_parent'
    try:
        info = path.lstat()
    except FileNotFoundError:
        return None, 'missing'
    if stat.S_ISLNK(info.st_mode):
        return None, 'symlink_leaf'
    kind = 'directory' if stat.S_ISDIR(info.st_mode) else 'file' if stat.S_ISREG(info.st_mode) else 'other'
    result: dict[str, Any] = {
        'device': info.st_dev,
        'inode': info.st_ino,
        'type': kind,
        'mode_octal': oct(stat.S_IMODE(info.st_mode)),
        'owner_uid': info.st_uid,
        'owner_gid': info.st_gid,
        'size': info.st_size,
        'mtime_ns': info.st_mtime_ns,
        'symlink_target_followed': False,
    }
    if kind == 'file':
        result['sha256'] = sha256(path.read_bytes())
    return result, None


def worktree_root_for_branch(admission: dict[str, Any]) -> dict[str, str]:
    roots: dict[str, str] = {}
    for row in admission['entries'] + admission['root_pair_existing_receipts']:
        request = row['requested']
        branch = request['branch']
        path = request['path']
        if branch in roots:
            require(roots[branch] == path, f'Admission maps branch {branch} to multiple roots')
        roots[branch] = path
    return roots


def add_ref(retained: dict[tuple[str, str, str, int], dict[str, Any]], ref: dict[str, Any]) -> dict[str, Any]:
    verified = git_ref(ref['commit'], ref['path'], ref['sha256'], ref['bytes'])
    for key in ('worktree', 'branch'):
        if ref.get(key) is not None:
            verified[key] = ref[key]
    retained[(verified['commit'], verified['path'], verified['sha256'], verified['bytes'])] = verified
    return verified


def main() -> None:
    require(CLEANUP.is_dir(), 'Cleanup scratch root is missing')
    eligibility_bytes = ELIGIBILITY.read_bytes()
    selection_v4_bytes = SELECTION_V4.read_bytes()
    eligibility = json.loads(eligibility_bytes)
    previous = json.loads(selection_v4_bytes)
    provenance_bytes = PROVENANCE.read_bytes()
    provenance = json.loads(provenance_bytes)
    mover_sha = sha256(MOVER.read_bytes())

    recommendations = [x for x in eligibility['candidate_items'] if x['eligibility'] == 'RECOMMEND_ELIGIBLE_AFTER_ROOT_RELEASE']
    held = [x for x in eligibility['candidate_items'] if x['eligibility'] != 'RECOMMEND_ELIGIBLE_AFTER_ROOT_RELEASE']
    require((len(recommendations), len(held), eligibility['preserve_only_source_extraction_count']) == (21, 28, 24), 'Eligibility set no longer matches the admitted 21/28/24 source')
    require(len(previous['candidate_items']) == 21 and len(previous['held_candidates']) == 28, 'Previous normalized selection set changed')
    previous_by_row = {x['row']: x for x in previous['candidate_items']}
    eligibility_by_row = {x['row']: x for x in recommendations}
    require(set(previous_by_row) == set(eligibility_by_row), 'Eligibility and prior normalized candidate rows differ')
    for row, old in previous_by_row.items():
        source = eligibility_by_row[row]
        require(old['path'] == source['path'] and old['category'] == source['category'], f'Candidate row {row} changed from the normalized source')

    current_head = git('rev-parse', 'HEAD').decode().strip()
    current_branch = git('symbolic-ref', '-q', '--short', 'HEAD').decode().strip()
    admission_bytes = git('show', f'{current_head}:{ADMISSION_REL}')
    require(sha256(admission_bytes) == EXPECTED_ADMISSION_SHA256, 'Current HEAD does not contain the admitted C index bytes')
    admission = json.loads(admission_bytes)
    branch_roots = worktree_root_for_branch(admission)
    roots: dict[str, str] = {}
    topics = []
    global_blockers: list[str] = []
    global_blocker_details: list[dict[str, Any]] = []
    for row in admission['entries'] + admission['root_pair_existing_receipts']:
        request = row['requested']
        roots[request['path']] = request['branch']
    require(len(roots) == 14, 'Admission index no longer resolves to exactly 14 roots')
    for root_text, admitted_branch in sorted(roots.items()):
        root = Path(root_text)
        branch = git('symbolic-ref', '-q', '--short', 'HEAD', cwd=root).decode().strip()
        head = git('rev-parse', 'HEAD', cwd=root).decode().strip()
        status = git('status', '--porcelain', cwd=root).decode(errors='replace')
        if branch != admitted_branch:
            global_blockers.append('admitted_branch_mismatch')
            global_blocker_details.append({'code': 'admitted_branch_mismatch', 'worktree': root_text, 'observed_branch': branch, 'admitted_branch': admitted_branch})
        if status:
            global_blockers.append('admitted_worktree_not_clean')
            global_blocker_details.append({'code': 'admitted_worktree_not_clean', 'worktree': root_text, 'porcelain': status})
        topics.append({
            'worktree': root_text,
            'branch': branch,
            'head': head,
            'admitted_branch': admitted_branch,
            'branch_matches_admission': branch == admitted_branch,
            'observed_status_clean': not status,
            'observed_status_porcelain': status,
            'freeze_status': 'OBSERVED_ONLY_ROOT_MUST_REVIEW_FINAL_C54_FREEZE',
        })

    admission_ref = {
        'commit': current_head,
        'path': ADMISSION_REL,
        'sha256': sha256(admission_bytes),
        'bytes': len(admission_bytes),
    }
    retained: dict[tuple[str, str, str, int], dict[str, Any]] = {}
    git_run_index: dict[str, dict[str, Any]] = {}
    row_ref_ids: dict[int, list[str]] = {row: [] for row in eligibility_by_row}
    row_preserve_paths: dict[int, set[str]] = {row: set(previous_by_row[row].get('preserve_ref_paths', [])) for row in eligibility_by_row}
    source_refs_by_row: dict[int, list[dict[str, Any]]] = {row: [] for row in eligibility_by_row}

    retained[('x', ADMISSION_REL, admission_ref['sha256'], admission_ref['bytes'])] = admission_ref
    for ref in previous.get('source_dag_git_refs', []):
        verified = add_ref(retained, ref)
        # Keep source-dag refs as top-level retained Git evidence.
    for ref in previous.get('retained_evidence_git_refs', []):
        add_ref(retained, ref)
    for ref_id, ref in previous.get('git_run_provenance_ref_index', {}).items():
        verified = add_ref(retained, ref)
        git_run_index[ref_id] = verified
    for item in previous['candidate_items']:
        row = item['row']
        for ref_id in item.get('actual_run_provenance_git_refs', []):
            require(ref_id in git_run_index, f'Previous run provenance ID is unresolved: {ref_id}')
            row_ref_ids[row].append(ref_id)
            ref = git_run_index[ref_id]
            ref_worktree = ref.get('worktree')
            if ref_worktree:
                row_preserve_paths[row].add(str(Path(ref_worktree) / ref['path']))

    # Resolve every raw run receipt to either an existing exact Git ref or a pending copied path.
    for record in provenance['source_receipt_records']:
        row = record['candidate_row']
        ref_alias = f"cleanup-source:{record['reference_id']}:{record['reference_item_index']}"
        storage = record['storage']
        resolved: dict[str, Any] | None = None
        if storage['status'] == 'EXISTING_BYTE_IDENTICAL_COMMITTED_RECEIPT':
            resolved = add_ref(retained, storage['git_ref'])
            branch = storage['git_ref'].get('branch')
            root_text = storage['git_ref'].get('worktree') or (branch_roots.get(branch) if branch else None)
            if root_text:
                row_preserve_paths[row].add(str(Path(root_text) / storage['git_ref']['path']))
                resolved['worktree'] = root_text
        elif storage['status'] == 'EXACT_COPY_UNCOMMITTED_GIT_REF_PENDING':
            target = Path(storage['destination_path'])
            try:
                rel = str(target.relative_to(ROOT))
            except ValueError:
                rel = ''
            current_bytes = target.read_bytes() if target.is_file() and not target.is_symlink() else b''
            if rel and current_bytes and sha256(current_bytes) == record['source_sha256'] and len(current_bytes) == record['source_bytes']:
                tracked = subprocess.run(['git', 'ls-files', '--error-unmatch', '--', rel], cwd=ROOT, capture_output=True)
                work_status = subprocess.run(['git', 'status', '--porcelain', '--', rel], cwd=ROOT, capture_output=True)
                if tracked.returncode == 0 and not work_status.stdout:
                    committed = subprocess.run(['git', 'show', f'{current_head}:{rel}'], cwd=ROOT, capture_output=True)
                    if committed.returncode == 0 and sha256(committed.stdout) == record['source_sha256'] and len(committed.stdout) == record['source_bytes']:
                        resolved = add_ref(retained, {'commit': current_head, 'path': rel, 'sha256': record['source_sha256'], 'bytes': record['source_bytes']})
                        resolved['worktree'] = str(ROOT)
            row_preserve_paths[row].add(str(target))
        else:
            global_blockers.append('unknown_provenance_storage_state')
            global_blocker_details.append({'code': 'unknown_provenance_storage_state', 'ref_id': ref_alias, 'candidate_row': row})
        source_refs_by_row[row].append(record)
        if resolved is not None:
            git_run_index[ref_alias] = resolved
            row_ref_ids[row].append(ref_alias)

    # Bind the companion index itself when it is a committed, exact Git file.
    provenance_rel = str(PROVENANCE.relative_to(ROOT))
    provenance_current_sha = sha256(provenance_bytes)
    index_tracked = subprocess.run(['git', 'ls-files', '--error-unmatch', '--', provenance_rel], cwd=ROOT, capture_output=True)
    index_status = subprocess.run(['git', 'status', '--porcelain', '--', provenance_rel], cwd=ROOT, capture_output=True)
    if index_tracked.returncode == 0 and not index_status.stdout:
        committed = subprocess.run(['git', 'show', f'{current_head}:{provenance_rel}'], cwd=ROOT, capture_output=True)
        if committed.returncode == 0 and sha256(committed.stdout) == provenance_current_sha and len(committed.stdout) == len(provenance_bytes):
            index_ref = add_ref(retained, {'commit': current_head, 'path': provenance_rel, 'sha256': provenance_current_sha, 'bytes': len(provenance_bytes)})
        else:
            global_blockers.append('cleanup_provenance_index_git_readback_mismatch')
    else:
        index_ref = None
        global_blockers.append('cleanup_provenance_index_not_committed')
    for row in row_preserve_paths:
        row_preserve_paths[row].add(str(PROVENANCE))

    # Preserve root-owned final documents as Git refs if committed; their semantic adjudication stays with root.
    final_refs: list[dict[str, Any]] = []
    final_pending: list[dict[str, Any]] = []
    for rel_root in (FINAL54_REL, COVERAGE_REL):
        directory = ROOT / rel_root
        files = sorted(p for p in directory.rglob('*') if p.is_file() or p.is_symlink()) if directory.exists() else []
        if not files:
            global_blockers.append('final_document_directory_empty_or_missing')
            global_blocker_details.append({'code': 'final_document_directory_empty_or_missing', 'relative_root': rel_root})
        for path in files:
            ident, issue = nofollow_identity(path)
            rel = str(path.relative_to(ROOT))
            if ident is None or ident.get('type') != 'file':
                final_pending.append({'path':str(path),'reason':issue or 'not_regular_file'})
                global_blockers.append('final_document_not_regular')
                continue
            tracked = subprocess.run(['git','ls-files','--error-unmatch','--',rel],cwd=ROOT,capture_output=True)
            status = subprocess.run(['git','status','--porcelain','--',rel],cwd=ROOT,capture_output=True)
            if tracked.returncode != 0 or status.stdout:
                final_pending.append({'path':str(path),'sha256':ident['sha256'],'bytes':ident['size'],'reason':'not_committed_or_worktree_differs'})
                global_blockers.append('final_document_not_committed')
                continue
            blob = git('show',f'{current_head}:{rel}')
            require(sha256(blob)==ident['sha256'] and len(blob)==ident['size'],f'Final document Git readback mismatch: {rel}')
            ref={'commit':current_head,'path':rel,'sha256':ident['sha256'],'bytes':ident['size']}
            final_refs.append(add_ref(retained,ref))

    c54_final_docs_committed = bool(final_refs) and not final_pending
    coverage_paths = [x for x in final_refs if x['path'].startswith(COVERAGE_REL + '/')]
    final54_paths = [x for x in final_refs if x['path'].startswith(FINAL54_REL + '/')]
    if not final54_paths:
        global_blockers.append('final54_owner_docs_not_committed')
    if not coverage_paths:
        global_blockers.append('coverage_census_docs_not_committed')

    candidates = []
    preserve_identities: dict[str, dict[str, Any]] = {}
    candidate_path_set = {Path(row['path']) for row in recommendations}
    for row in recommendations:
        n = row['row']
        path = Path(row['path'])
        owners = [Path(root) for root in roots if path.is_relative_to(Path(root)) and path != Path(root)]
        blockers: list[str] = []
        if len(owners) != 1:
            owner = Path('/')
            blockers.append('candidate_owner_not_unique_in_admission')
        else:
            owner = owners[0]
        candidate_identity, candidate_issue = nofollow_identity(path)
        if candidate_issue:
            blockers.append(f'candidate_identity:{candidate_issue}')
        if candidate_identity and candidate_identity['type'] != 'directory':
            blockers.append('candidate_not_directory')
        if candidate_identity and candidate_identity['owner_uid'] != os.getuid():
            blockers.append('candidate_uid_mismatch')
        if not path.is_relative_to(owner) or path == owner:
            blockers.append('candidate_outside_owning_root')
        relative = str(path.relative_to(owner)) if path.is_relative_to(owner) else str(path)
        tracked = subprocess.run(['git','ls-files','--',relative],cwd=owner,capture_output=True)
        if tracked.returncode or tracked.stdout:
            blockers.append('candidate_git_index_query_failed_or_tracked')
        ignored = subprocess.run(['git','check-ignore','--',relative],cwd=owner,capture_output=True)
        gitignored = ignored.returncode == 0
        if not gitignored:
            blockers.append('candidate_not_gitignored')

        refs_for_row = list(dict.fromkeys(row_ref_ids[n]))
        if not refs_for_row:
            blockers.append('actual_run_provenance_not_yet_resolved_to_git')
        preserve_paths = set(row_preserve_paths[n])
        for record in source_refs_by_row[n]:
            preserve_paths.add(record['source_path'])
            if record['storage'].get('destination_path'):
                preserve_paths.add(record['storage']['destination_path'])
        for ref_id in refs_for_row:
            ref = git_run_index[ref_id]
            worktree = ref.get('worktree')
            if worktree:
                preserve_paths.add(str(Path(worktree)/ref['path']))
        for preserve in sorted(preserve_paths):
            preserve_path = Path(preserve)
            if preserve_path == path or preserve_path.is_relative_to(path):
                blockers.append(f'preserve_path_overlaps_candidate:{preserve}')
                continue
            identity, issue = nofollow_identity(preserve_path)
            if identity is None:
                blockers.append(f'preserve_identity:{preserve}:{issue}')
            else:
                preserve_identities[preserve] = identity
        candidates.append({
            'row':n,
            'category':row['category'],
            'path':str(path),
            'owning_worktree':str(owner),
            'type':candidate_identity['type'] if candidate_identity else 'unknown',
            'gitignored':gitignored,
            'initial_lstat':candidate_identity,
            'actual_run_provenance_git_refs':refs_for_row,
            'actual_run_provenance_source_rows':[{'reference_id':x['reference_id'],'reference_item_index':x['reference_item_index']} for x in source_refs_by_row[n]],
            'preserve_ref_paths':sorted(preserve_paths),
            'status_now':'HELD_ROOT_RELEASE_NOT_AUTHORIZED',
            'trash_authorized_now':False,
            'eligibility_source_row':{'report_row':n,'source_row_ref':row['source_row_ref']},
            'blocked_reason_codes':sorted(set(blockers+(['actual_run_provenance_not_yet_resolved_to_git'] if not refs_for_row else [])+['root_release_decision_missing'])),
        })

    held_candidates = [{'row':x['row'],'category':x['category'],'path':x['path'],'eligibility':x['eligibility'],'reason_report_row':x['row']} for x in held]
    source_preserve = {'count':24,'reference_id':'INV','path':str(CLEANUP/'cleanup-inventory-v3-20261006.json'),'sha256':sha256((CLEANUP/'cleanup-inventory-v3-20261006.json').read_bytes()),'policy':'PRESERVE_CODE_NOT_RELEASED'}
    now = datetime.now(timezone.utc).isoformat()
    blockers = sorted(set(global_blockers + [f'candidate_row_{x["row"]}:{code}' for x in candidates for code in x['blocked_reason_codes']]))
    selection = {
        'schema':'policyos.e02.C.cleanup.selection.v5-preflight',
        'created_utc':now,
        'decision':'HOLD_FOR_ROOT_C54_RELEASE',
        'action_authorization':'NONE. Preflight derives inputs only and cannot authorize Trash.',
        'trash_authorized_now':False,
        'candidate_count':21,
        'candidate_items':candidates,
        'held_count':28,
        'held_candidates':held_candidates,
        'source_extractions_preserve_only':source_preserve,
        'eligibility_report':{'path':str(ELIGIBILITY),'sha256':sha256(eligibility_bytes),'bytes':len(eligibility_bytes)},
        'prior_normalized_selection':{'path':str(SELECTION_V4),'sha256':sha256(selection_v4_bytes),'bytes':len(selection_v4_bytes)},
        'provenance_companion':{'path':str(PROVENANCE),'sha256':sha256(provenance_bytes),'bytes':len(provenance_bytes),'committed':index_ref is not None},
        'git_run_provenance_ref_index':git_run_index,
        'admission_index_git_ref':admission_ref,
        'exact_admitted_C_roots':sorted(roots),
        'frozen_topics':topics,
        'final_c54_document_git_refs':final_refs,
        'final_c54_docs_committed_observation':c54_final_docs_committed,
        'final_c54_pending_paths':final_pending,
        'retained_evidence_git_refs':sorted(retained.values(),key=lambda x:(x['commit'],x['path'],x['sha256'])),
        'preflight_blockers':blockers,
        'preflight_blocker_details':{
            'admitted_roots':global_blocker_details,
            'candidate_rows':[{'row':x['row'],'codes':x['blocked_reason_codes']} for x in candidates if x['blocked_reason_codes']],
            'final_documents_pending':final_pending,
        },
        'mover_reviewed_sha256':mover_sha,
        'mover_review_matches_assigned_sha':mover_sha==EXPECTED_MOVER_SHA256,
        'root_release_adjudication_required':True,
    }
    if mover_sha != EXPECTED_MOVER_SHA256:
        selection['preflight_blockers'].append('mover_sha_changed_since_assigned_static_review')
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    selection_path = CLEANUP / f'cleanup-selection-v5-preflight-{stamp}.json'
    release_path = CLEANUP / f'cleanup-release-template-v2-preflight-{stamp}.json'
    selection_bytes = (json.dumps(selection,indent=2,ensure_ascii=False)+'\n').encode()
    with selection_path.open('xb') as stream:
        stream.write(selection_bytes)
    release = {
        'schema':'policyos.e02.C.cleanup.release-input-template.v2-preflight',
        'created_utc':now,
        'template_only':True,
        'selection_path':str(selection_path),
        'selection_sha256':sha256(selection_bytes),
        'all_deciding_outputs_and_useful_changes_committed':False,
        'owning_audits_complete':False,
        'user_authorization':'PENDING_ROOT_FINAL_RELEASE_DECISION',
        'permanent_deletion':False,
        'trash_directory_name':None,
        'released_paths':[],
        'trash_authorized_now':False,
        'admission_index_git_ref':admission_ref,
        'exact_admitted_C_roots':sorted(roots),
        'frozen_topics':topics,
        'retained_evidence_git_refs':selection['retained_evidence_git_refs'],
        'preserve_identities':preserve_identities,
        'preflight_blockers':blockers,
        'required_root_review':'C54 owner closure and full Git handoff review remains root adjudication; this builder does not infer it from file presence.',
        'release_state':'NO_ACTION_PREFLIGHT_ONLY',
    }
    with release_path.open('xb') as stream:
        stream.write((json.dumps(release,indent=2,ensure_ascii=False)+'\n').encode())
    print(json.dumps({
        'selection_path':str(selection_path),'selection_sha256':sha256(selection_path.read_bytes()),'selection_bytes':selection_path.stat().st_size,
        'release_template_path':str(release_path),'release_template_sha256':sha256(release_path.read_bytes()),'release_template_bytes':release_path.stat().st_size,
        'candidate_count':len(candidates),'held_count':len(held_candidates),'source_extractions_preserve_only':source_preserve['count'],
        'admitted_roots':len(roots),'clean_roots_observed':sum(x['observed_status_clean'] for x in topics),
        'resolved_candidate_rows':sum(bool(x['actual_run_provenance_git_refs']) for x in candidates),
        'unresolved_candidate_rows':[x['row'] for x in candidates if not x['actual_run_provenance_git_refs']],
        'provenance_ref_index_count':len(git_run_index),'retained_git_ref_count':len(selection['retained_evidence_git_refs']),
        'final54_docs_committed_observation':c54_final_docs_committed,'mover_sha256':mover_sha,
        'trash_authorized_now':False,'released_paths':0,'blockers':blockers,
    },indent=2))


if __name__ == '__main__':
    main()
