"""Publish existing Git objects unchanged; never synthesize replacement history."""

import base64
import datetime
import hashlib
import json
import re
import subprocess
import time
from pathlib import Path

REPO = Path('/workspace/e02-F-cau-20261006')
OUT = Path('/tmp/e02-F-graph-profile-20261007/cau/git-api-publication')
COMMITS = ['e1c4bb28c9d5ff936ae1c047619c56cf12ba5347',
           'a7204961ac1028965c58224fe40e6bb3a397d8a8']
API = 'repos/DenisKopylov/polisyos/git/'


def git(*args):
    return subprocess.check_output(['git', '-C', str(REPO), *args])


def digest(raw):
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def api(name, endpoint, body):
    argv = ['gh', 'api', '--method', 'POST', API + endpoint, '--input', '-']
    raw = json.dumps(body, ensure_ascii=False).encode()
    start = time.perf_counter()
    result = subprocess.run(argv, input=raw, capture_output=True)
    (OUT / (name + '.stdout.json')).write_bytes(result.stdout)
    (OUT / (name + '.stderr.txt')).write_bytes(result.stderr)
    record = {'argv': argv, 'cwd': str(Path.cwd()), 'stdin': digest(raw),
              'request_reconstruction': 'exact local immutable Git objects plus this tracked replayer',
              'exit_code': result.returncode, 'wall_seconds': time.perf_counter() - start,
              'stdout': digest(result.stdout), 'stderr': digest(result.stderr)}
    (OUT / (name + '.execution.json')).write_text(json.dumps(record, indent=2) + '\n')
    assert result.returncode == 0, (name, result.stderr.decode())
    return json.loads(result.stdout)


def person(value):
    match = re.fullmatch(r'(.*) <([^<>]+)> (\d+) ([+-]\d{4})', value)
    assert match
    name, email, epoch, zone = match.groups()
    minutes = int(zone[1:3]) * 60 + int(zone[3:])
    if zone[0] == '-':
        minutes = -minutes
    tz = datetime.timezone(datetime.timedelta(minutes=minutes))
    date = datetime.datetime.fromtimestamp(int(epoch), tz).isoformat()
    return {'name': name, 'email': email, 'date': date}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    assert git('rev-parse', 'HEAD').decode().strip() == COMMITS[-1]
    assert not git('status', '--porcelain=v1').decode()
    outcomes = []
    for commit in COMMITS:
        raw = git('cat-file', 'commit', commit)
        headers, message = raw.decode().split('\n\n', 1)
        values = dict(line.split(' ', 1) for line in headers.splitlines())
        assert set(values) == {'tree', 'parent', 'author', 'committer'}
        paths = git('diff', '--name-only', values['parent'], commit).decode().splitlines()
        tree = []
        for index, path in enumerate(paths):
            blob = git('rev-parse', commit + ':' + path).decode().strip()
            content = git('cat-file', 'blob', blob)
            response = api(commit[:8] + '-blob-' + str(index), 'blobs', {
                'content': base64.b64encode(content).decode(), 'encoding': 'base64',
            })
            assert response['sha'] == blob, 'Blob byte drift'
            tree.append({'path': path, 'mode': '100644', 'type': 'blob', 'sha': blob})
            print(json.dumps({'commit': commit, 'path': path, 'blob_verified': blob}), flush=True)
        parent_tree = git('rev-parse', values['parent'] + '^{tree}').decode().strip()
        tree_response = api(commit[:8] + '-tree', 'trees', {'base_tree': parent_tree, 'tree': tree})
        assert tree_response['sha'] == values['tree'], 'Stop before commit/ref: tree drift'
        commit_response = api(commit[:8] + '-commit', 'commits', {
            'tree': values['tree'], 'parents': [values['parent']], 'message': message,
            'author': person(values['author']), 'committer': person(values['committer']),
        })
        assert commit_response['sha'] == commit, 'Stop before ref: commit metadata drift'
        outcomes.append({'commit': commit, 'tree': values['tree'], 'parent': values['parent'],
                         'all_exact_object_bytes_verified': True})
    (OUT / 'objects-publication.json').write_text(json.dumps({
        'check': 'PASS', 'commits': outcomes, 'branch_update': 'UNRUN; separate expected-head nonforced update',
        'no_rewritten_history': True,
    }, indent=2) + '\n')
    print(json.dumps({'check': 'PASS', 'exact_commits_uploaded': COMMITS, 'ref_update': 'UNRUN'}))


if __name__ == '__main__':
    main()
