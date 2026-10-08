"""Execute the canonical module CLI with exact selected source and origin capture."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import runpy
import sys
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pytest_source_bound import git, tree_blobs, MutationFinder, OriginPlugin


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--target', type=Path, required=True)
    parser.add_argument('--expected-sha', required=True)
    parser.add_argument('--base-sha', required=True)
    parser.add_argument('--origins', type=Path, required=True)
    parser.add_argument('--mutant-path', type=Path)
    parser.add_argument('cli_args', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    args.mutant_canonical_path = 'policy-engine/tools/quality/validation/schema_fqn_census.py'
    assert git(args.target, 'rev-parse', 'HEAD').decode().strip() == args.expected_sha
    assert not git(args.target, 'status', '--porcelain=v1')
    product = args.target / 'policy-engine'
    sys.path[:0] = [str(product / 'src'), str(product)]
    sys.dont_write_bytecode = True
    os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
    if args.mutant_path:
        sys.meta_path.insert(0, MutationFinder('tools.quality.validation.schema_fqn_census', args.mutant_path))
    from tools.registry import TOOL_SPECS_BY_KEY
    from tools.lib.runner import ToolStatus
    spec = TOOL_SPECS_BY_KEY[('validation', 'schema-fqn-census')]
    assert spec.status is ToolStatus.ACTIVE
    assert spec.module == 'tools.quality.validation.schema_fqn_census' and spec.callable_name == 'main'
    cli_args = args.cli_args[1:] if args.cli_args[:1] == ['--'] else args.cli_args
    sys.argv = ['tools.cli', *cli_args]
    candidate = tree_blobs(args.target, args.expected_sha)
    baseline = tree_blobs(args.target, args.base_sha)
    plugin = OriginPlugin(args, candidate, baseline)
    try:
        runpy.run_module('tools.cli', run_name='__main__', alter_sys=True)
    except SystemExit as exc:
        code = int(exc.code) if exc.code is not None else 0
    else:
        code = 0
    session = SimpleNamespace(exitstatus=code)
    # The plugin's progress line belongs on stderr, leaving the real JSON stdout intact.
    saved_stdout = sys.stdout
    try:
        sys.stdout = sys.stderr
        plugin.pytest_sessionfinish(session, code)
    finally:
        sys.stdout = saved_stdout
    receipt = json.loads(args.origins.read_text())
    entrypoint = product / 'tools/cli.py'
    data = entrypoint.read_bytes()
    blob = hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()
    assert blob == candidate['policy-engine/tools/cli.py']
    receipt['canonical_module_entrypoint'] = {
        'execution': 'runpy.run_module(tools.cli, run_name=__main__, alter_sys=True) in an isolated Python process; original __main__ SystemExit(main()) executes with unchanged CLI argv',
        'argv': cli_args, 'path': 'policy-engine/tools/cli.py', 'origin': str(entrypoint),
        'git_blob': blob, 'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data),
        'candidate_blob': candidate['policy-engine/tools/cli.py'], 'G_blob': baseline['policy-engine/tools/cli.py'],
    }
    receipt['registry_actual_selected_spec'] = {'category': spec.category, 'name': spec.name, 'module': spec.module, 'callable_name': spec.callable_name, 'status': spec.status.value}
    receipt['cli_exitstatus'] = receipt.pop('pytest_exitstatus')
    args.origins.write_text(json.dumps(receipt, indent=2) + '\n')
    return session.exitstatus


if __name__ == '__main__':
    raise SystemExit(main())
