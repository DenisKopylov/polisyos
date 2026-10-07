"""Upload existing objects in topological order; verify every SHA; never move refs."""

import argparse
import base64
import datetime
import hashlib
import json
import re
import subprocess
import time
from pathlib import Path


def digest(raw):
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def person(value):
    match = re.fullmatch(r'(.*) <([^<>]+)> (\d+) ([+-]\d{4})', value)
    assert match, 'Cannot preserve original person header'
    name, email, epoch, zone = match.groups()
    minutes = int(zone[1:3]) * 60 + int(zone[3:])
    tz = datetime.timezone(datetime.timedelta(minutes=minutes if zone[0] == '+' else -minutes))
    return {'name': name, 'email': email, 'date': datetime.datetime.fromtimestamp(int(epoch), tz).isoformat()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', required=True)
    parser.add_argument('--repository', default='DenisKopylov/polisyos')
    parser.add_argument('--branch', required=True)
    parser.add_argument('--base', required=True)
    parser.add_argument('--head', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    assert args.branch.startswith('codex/e02-F-'), 'Only explicitly owned F topics'
    repo, out = Path(args.repo), Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    sequence = 0

    def git(*values):
        return subprocess.check_output(['git', '-C', str(repo), *values])

    def guard():
        actual = {
            'head': git('rev-parse', 'HEAD').decode().strip(),
            'tree': git('rev-parse', 'HEAD^{tree}').decode().strip(),
            'branch': git('symbolic-ref', '--short', 'HEAD').decode().strip(),
            'status': git('status', '--porcelain=v1').decode(),
        }
        assert actual['head'] == args.head and actual['branch'] == args.branch and not actual['status']
        return actual

    def api(method, endpoint, body=None, allow_absent=False):
        nonlocal sequence
        sequence += 1
        name = f'{sequence:05d}-' + method.lower()
        argv = ['gh', 'api', '--method', method, f'repos/{args.repository}/git/{endpoint}']
        raw = b'' if body is None else json.dumps(body, ensure_ascii=False).encode()
        if body is not None:
            argv += ['--input', '-']
        started = time.perf_counter()
        result = subprocess.run(argv, input=raw if body is not None else None, capture_output=True)
        stdout = out / (name + '.stdout.json')
        stderr = out / (name + '.stderr.txt')
        stdout.write_bytes(result.stdout)
        stderr.write_bytes(result.stderr)
        record = {
            'argv': argv, 'cwd': str(Path.cwd()), 'exit_code': result.returncode,
            'wall_seconds': time.perf_counter() - started, 'stdin': digest(raw),
            'request_reconstruction': 'immutable local Git objects + exact replayer',
            'stdout': {'path': str(stdout), **digest(result.stdout)},
            'stderr': {'path': str(stderr), **digest(result.stderr)},
            'replayer': {'path': str(Path(__file__).resolve()), **digest(Path(__file__).read_bytes())},
        }
        (out / (name + '.execution.json')).write_text(json.dumps(record, indent=2) + '\n')
        if result.returncode:
            if allow_absent and b'HTTP 404' in result.stderr:
                return None
            raise RuntimeError((method, endpoint, result.stderr.decode()))
        return json.loads(result.stdout)

    before = guard()
    assert subprocess.run(['git', '-C', str(repo), 'merge-base', '--is-ancestor', args.base, args.head]).returncode == 0
    assert api('GET', 'commits/' + args.base)['sha'] == args.base
    commits = git('rev-list', '--reverse', '--topo-order', args.base + '..' + args.head).decode().splitlines()
    seen_blobs = set()
    outcomes = []
    for commit in commits:
        existing = api('GET', 'commits/' + commit, allow_absent=True)
        if existing is not None:
            assert existing['sha'] == commit
            outcomes.append({'sha': commit, 'already_remote': True})
            continue
        raw = git('cat-file', 'commit', commit)
        headers, message = raw.decode().split('\n\n', 1)
        fields = {}
        parents = []
        for line in headers.splitlines():
            key, value = line.split(' ', 1)
            if key == 'parent':
                parents.append(value)
            else:
                assert key not in fields
                fields[key] = value
        assert set(fields) == {'tree', 'author', 'committer'} and parents, 'Unsupported header: stop without ref update'
        changed = git('diff', '--name-only', '-z', parents[0], commit).split(b'\0')
        entries = []
        for encoded_path in changed:
            if not encoded_path:
                continue
            path = encoded_path.decode()
            entry = git('ls-tree', '-z', commit, '--', path).rstrip(b'\0')
            if not entry:
                entries.append({'path': path, 'mode': '100644', 'type': 'blob', 'sha': None})
                continue
            mode, kind, blob = entry.split(b'\t', 1)[0].decode().split()
            assert kind == 'blob' and mode in {'100644', '100755', '120000'}
            if blob not in seen_blobs:
                content = git('cat-file', 'blob', blob)
                response = api('POST', 'blobs', {'encoding': 'base64', 'content': base64.b64encode(content).decode()})
                assert response['sha'] == blob, 'Blob byte drift: stop without ref update'
                seen_blobs.add(blob)
            entries.append({'path': path, 'mode': mode, 'type': 'blob', 'sha': blob})
        parent_tree = git('rev-parse', parents[0] + '^{tree}').decode().strip()
        tree = api('POST', 'trees', {'base_tree': parent_tree, 'tree': entries})
        assert tree['sha'] == fields['tree'], 'Tree byte drift: stop without ref update'
        response = api('POST', 'commits', {
            'tree': fields['tree'], 'parents': parents, 'message': message,
            'author': person(fields['author']), 'committer': person(fields['committer']),
        })
        assert response['sha'] == commit, 'Commit metadata drift: stop without ref update'
        outcomes.append({'sha': commit, 'parents': parents, 'tree': fields['tree'], 'exact_preserved': True})
        print(json.dumps(outcomes[-1]), flush=True)
    after = guard()
    final_remote = api('GET', 'commits/' + args.head)
    assert final_remote['sha'] == args.head and final_remote['tree']['sha'] == before['tree']
    report = {
        'check': 'PASS', 'source_before': before, 'source_after': after,
        'base': args.base, 'head': args.head, 'branch': args.branch, 'commits': outcomes,
        'api_calls': sequence, 'branch_update': 'UNRUN; caller must use force:false and exact observed expected head',
        'no_local_git_mutation': True, 'no_history_rewrite': True,
        'replayer': {'path': str(Path(__file__).resolve()), **digest(Path(__file__).read_bytes())},
    }
    (out / 'objects-publication.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'check': 'PASS', 'head': args.head, 'exact_commits': len(outcomes), 'api_calls': sequence, 'branch_update': 'UNRUN'}))


if __name__ == '__main__':
    main()
