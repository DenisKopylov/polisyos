"""Capture a single command with direct wait4 resource usage, without a cutoff."""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import platform
import subprocess
import sys
import time
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--cwd', type=Path, required=True)
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ['--'] else args.command
    args.directory.mkdir(parents=True, exist_ok=False)
    start_utc = datetime.datetime.now(datetime.UTC).isoformat()
    start = time.monotonic()
    with (args.directory / 'stdout.txt').open('wb') as stdout, (args.directory / 'stderr.txt').open('wb') as stderr:
        child = subprocess.Popen(command, cwd=args.cwd, stdout=stdout, stderr=stderr)
        pid, status, usage = os.wait4(child.pid, 0)
        child.returncode = os.waitstatus_to_exitcode(status)
    receipt = {
        'argv': command, 'cwd': str(args.cwd.resolve()), 'pid': pid,
        'start_utc': start_utc, 'end_utc': datetime.datetime.now(datetime.UTC).isoformat(),
        'wall_seconds': time.monotonic() - start, 'returncode': child.returncode,
        'wait_status': status, 'signal': os.WTERMSIG(status) if os.WIFSIGNALED(status) else None,
        'resource_method': 'os.wait4 exact direct child; Linux ru_maxrss KiB',
        'max_rss_kib': usage.ru_maxrss, 'user_seconds': usage.ru_utime, 'system_seconds': usage.ru_stime,
        'timeout': None, 'harness_python': sys.version, 'platform': platform.platform(),
        'selected_environment': {key: os.environ.get(key) for key in (
            'PYTHONPATH', 'PYTHONHOME', 'PYTHONDONTWRITEBYTECODE', 'PYTEST_DISABLE_PLUGIN_AUTOLOAD',
            'JAX_PLATFORMS', 'JAX_PLATFORM_NAME', 'XLA_PYTHON_CLIENT_PREALLOCATE',
            'OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'UV_PROJECT_ENVIRONMENT')},
        'outputs': {},
    }
    for name in ('stdout.txt', 'stderr.txt'):
        data = (args.directory / name).read_bytes()
        receipt['outputs'][name] = {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
    (args.directory / 'command.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({key: receipt[key] for key in ('returncode', 'wall_seconds', 'max_rss_kib', 'signal')}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
