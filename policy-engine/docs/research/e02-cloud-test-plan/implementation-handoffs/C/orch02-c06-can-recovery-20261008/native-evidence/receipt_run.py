from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import resource
import subprocess
import time
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--cwd', type=Path, required=True)
    parser.add_argument('--timeout', type=float)
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command
    if command[0] == '--':
        command = command[1:]
    args.directory.mkdir(parents=True, exist_ok=False)
    started = datetime.datetime.now(datetime.UTC).isoformat()
    start = time.monotonic()
    result = None
    timeout = False
    with (args.directory/'stdout.txt').open('wb') as stdout, (args.directory/'stderr.txt').open('wb') as stderr:
        proc = subprocess.Popen(command, cwd=args.cwd, stdout=stdout, stderr=stderr)
        try:
            result = proc.wait(timeout=args.timeout)
        except subprocess.TimeoutExpired:
            timeout = True
            proc.terminate()
            try:
                result = proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                result = proc.wait()
    wall = time.monotonic()-start
    usage = resource.getrusage(resource.RUSAGE_CHILDREN)
    payload = {
        'argv': command, 'cwd': str(args.cwd.resolve()),
        'start_utc': started, 'end_utc': datetime.datetime.now(datetime.UTC).isoformat(),
        'wall_seconds': wall, 'max_rss_kib': usage.ru_maxrss,
        'user_seconds': usage.ru_utime, 'system_seconds': usage.ru_stime,
        'timeout_seconds': args.timeout, 'timeout': timeout, 'returncode': result,
        'selected_environment': {name: os.environ.get(name) for name in (
            'PYTHONPATH','PYTHONDONTWRITEBYTECODE','PYTEST_DISABLE_PLUGIN_AUTOLOAD','JAX_PLATFORMS',
            'JAX_PLATFORM_NAME','XLA_PYTHON_CLIENT_PREALLOCATE','UV_PROJECT_ENVIRONMENT')},
    }
    payload['outputs'] = {}
    for name in ('stdout.txt','stderr.txt'):
        data = (args.directory/name).read_bytes()
        payload['outputs'][name] = {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
    (args.directory/'command.json').write_text(json.dumps(payload,indent=2)+'\n')
    print(json.dumps({'directory': str(args.directory), 'returncode': result, 'wall_seconds': wall, 'max_rss_kib': usage.ru_maxrss, 'timeout':timeout}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
