"""Run the frozen independent validator on explicit immutable Git inputs only."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import time

ROOT = Path(__file__).resolve().parent
VALIDATOR = Path('/tmp/e02-F-continuation-20261006/cau/final35-validator/validate_packet.py')
REGISTRY = ROOT / 'required-registry-final.json'
MANIFEST = Path('/tmp/e02-F-continuation-20261006/cau/original35-reconciliation.json')
FROZEN = {
    VALIDATOR: '51a95464831e426050bc9aac6abc0ed094a871c01d5634a8a021972acf0d9e1f',
    REGISTRY: 'e108437f8bb439d85fdb00016c9c2164d14af5a22768f542013df7eeef7b6d95',
    MANIFEST: '95f728b758fde25591b0124bc0a2cd8b6c0acd86a61deb6d13bc07e99c4ba2a7',
}


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def binding(path: Path) -> dict:
    data = path.read_bytes()
    return {'path': str(path), 'bytes': len(data), 'sha256': digest(data)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--repo', default='/workspace/e02-F-closeout-20261006')
    parser.add_argument('--python', default='/workspace/e02-F-closeout-20261006/policy-engine/.venv/bin/python')
    parser.add_argument('--packet-sha', required=True)
    for name in ['index', 'report', 'source-order', 'transports']:
        parser.add_argument('--' + name + '-path', required=True)
    args = parser.parse_args()
    for path, expected in FROZEN.items():
        if digest(path.read_bytes()) != expected:
            raise RuntimeError(f'Frozen independent input changed: {path}')
    if len(args.packet_sha) != 40 or any(c not in '0123456789abcdef' for c in args.packet_sha):
        raise ValueError('Use an explicit full immutable Git SHA.')
    tree = subprocess.check_output(['git', '-C', args.repo, 'rev-parse', args.packet_sha + '^{tree}'], text=True).strip()
    run_root = ROOT / args.packet_sha
    run_root.mkdir(exist_ok=False)
    inputs = {}
    for name in ['index', 'report', 'source_order', 'transports']:
        path = getattr(args, name + '_path')
        body = subprocess.check_output(['git', '-C', args.repo, 'show', args.packet_sha + ':' + path])
        suffix = ''.join(Path(path).suffixes) or '.bin'
        target = run_root / ('immutable-' + name.replace('_', '-') + suffix)
        target.write_bytes(body)
        inputs[name] = {'git_ref': args.packet_sha, 'git_path': path, **binding(target)}
    output = run_root / 'final-validation.json'
    argv = [args.python, str(VALIDATOR), '--repo', args.repo, '--manifest', str(MANIFEST),
            '--index', inputs['index']['path'], '--output', str(output),
            '--transports', inputs['transports']['path'], '--packet-sha', args.packet_sha,
            '--report', inputs['report']['path'], '--source-order', inputs['source_order']['path'],
            '--required-registry', str(REGISTRY)]
    started = time.monotonic()
    result = subprocess.run(argv, cwd=str(run_root), capture_output=True, check=False)
    stdout = run_root / 'final-validation.stdout.txt'
    stderr = run_root / 'final-validation.stderr.txt'
    stdout.write_bytes(result.stdout)
    stderr.write_bytes(result.stderr)
    stable = all(digest(path.read_bytes()) == expected for path, expected in FROZEN.items())
    execution = {
        'role': 'independent_metadata_custody_only', 'packet_sha': args.packet_sha,
        'packet_tree': tree, 'argv': argv, 'cwd': str(run_root), 'exit_code': result.returncode,
        'wall_seconds': time.monotonic() - started, 'immutable_inputs': inputs,
        'frozen_input_bindings': [binding(path) for path in FROZEN],
        'frozen_inputs_unchanged_after': stable, 'stdout': binding(stdout), 'stderr': binding(stderr),
        'validator_output': binding(output) if output.exists() else {'check': 'ERROR', 'reason': 'No result file.'},
        'replayer': binding(Path(__file__)),
    }
    (run_root / 'final-validation.execution.json').write_text(json.dumps(execution, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'exit_code': result.returncode, 'frozen_inputs_unchanged_after': stable,
                      'execution': str(run_root / 'final-validation.execution.json')}, ensure_ascii=False))
    return result.returncode if stable else 2


if __name__ == '__main__':
    raise SystemExit(main())
