"""Independent fresh Git+CLI witnesses for the new G census adoption."""
from __future__ import annotations

import base64
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path('/workspace/orch02-r2-c06-dfk-g')
SOURCE = '3a0d5549606087c1d4e8d344ed474c0dfb4cbe5d'
BASE = 'dee58973f7673299070b7c7374f419b0adb8175c'
HARNESS = Path('/workspace/orch02-r2/native-c06/harness')
FQN = 'polisyos.foundry.domain.schema'
PROTOCOL_CASES = ('ordinary-root', 'ordinary-nested', 'staged-RM', 'staged-C', 'unstaged-YR', 'unstaged-YC')


def git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args])


@pytest.mark.parametrize('case', PROTOCOL_CASES)
def test_fresh_G_canonical_cli_protocol_and_complete_denominator(tmp_path, case):
    fixture = tmp_path / 'fixture'
    fixture.mkdir()
    git(fixture, 'init', '--quiet')
    git(fixture, 'config', 'user.email', 'native-c06@example.invalid')
    git(fixture, 'config', 'user.name', 'Independent native fixture')
    git(fixture, 'config', 'status.renames', 'copies')
    nested = case != 'ordinary-root'
    prefix = 'policy-engine/' if nested else ''
    product = fixture / 'policy-engine' if nested else fixture
    content = json.dumps({'module': FQN, 'rows': [f'{i:04}: independent discriminator' for i in range(150)]}, ensure_ascii=False, indent=2) + '\n'
    names = {'source': 'configs/a original\nпуть.json', 'destination': 'configs/b copy space.json', 'ordinary': 'configs/y ordinary.json', 'added': 'configs/z added\nслед.json'}
    initial = {prefix + names['source']: content, prefix + names['ordinary']: '{}\n', prefix + '.gitignore': 'ignored/\n', prefix + 'excluded.whl': 'unsupported-format\n'}
    if nested:
        initial['outside.json'] = '{}\n'
    for name, text in initial.items():
        path = fixture / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    git(fixture, 'add', '--all')
    git(fixture, 'commit', '--quiet', '-m', 'independent fresh protocol fixture')
    source = product / names['source']
    destination = product / names['destination']
    if case == 'staged-RM':
        git(fixture, 'mv', '--', prefix + names['source'], prefix + names['destination'])
        destination.write_text(content + '\n')
    elif case == 'staged-C':
        destination.write_text(content)
        source.write_text(content + '\n')
        git(fixture, 'add', '--', prefix + names['source'], prefix + names['destination'])
    elif case == 'unstaged-YR':
        source.rename(destination)
        git(fixture, 'add', '-N', '--', prefix + names['destination'])
    elif case == 'unstaged-YC':
        destination.write_text(content)
        source.write_text(content.replace('0000:', 'edit:', 1))
        git(fixture, 'add', '-N', '--', prefix + names['destination'])
    else:
        source.write_text(content + '\n')
    (product / names['ordinary']).write_text(json.dumps({'module': 'polisyos.data_forge.kernel.schemas.codegen'}) + '\n')
    added = product / names['added']
    added.write_text(json.dumps({'module': FQN}) + '\n')
    git(fixture, 'add', '--', prefix + names['added'])
    added.write_text(added.read_text() + '\n')  # real AM record following ordinary M.
    hidden = product / 'ignored/hidden.txt'
    hidden.parent.mkdir()
    hidden.write_text('polisyos.foundry.domain.mechanisms\n')
    untracked = product / 'untracked.json'
    untracked.write_text(json.dumps({'module': FQN}) + '\n')
    if nested:
        (fixture / 'outside.json').write_text('{"outside":true}\n')
    raw = git(fixture, 'status', '--porcelain=v1', '-z', '--untracked-files=all')
    status_prefix = {'staged-RM': b'RM ', 'staged-C': b'C  ', 'unstaged-YR': b' R ', 'unstaged-YC': b' C '}.get(case)
    if status_prefix is not None:
        assert status_prefix + os.fsencode(prefix + names['destination']) + b'\0' + os.fsencode(prefix + names['source']) + b'\0' in raw
    assert b'AM ' + os.fsencode(prefix + names['added']) + b'\0' in raw
    assert b' M ' + os.fsencode(prefix + names['ordinary']) + b'\0' in raw
    oracle_commands = [
        ['diff', '--relative', '--name-only', '--no-renames', '-z', '--', '.'],
        ['diff', '--cached', '--relative', '--name-only', '--no-renames', '-z', '--', '.'],
        ['ls-files', '--others', '--exclude-standard', '-z', '--', '.'],
    ]
    oracle_rows = [{'argv': ['git', *argv], 'stdout_b64': base64.b64encode(git(product, *argv)).decode()} for argv in oracle_commands]
    oracle_changes = {os.fsdecode(path) for row in oracle_rows for path in base64.b64decode(row['stdout_b64']).split(b'\0') if path}
    tracked = {os.fsdecode(path) for path in git(product, 'ls-files', '--cached', '-z', '--', '.').split(b'\0') if path}
    nonignored = {os.fsdecode(path) for path in git(product, 'ls-files', '--others', '--exclude-standard', '-z', '--', '.').split(b'\0') if path}
    # Finite fixture uses these independently assigned types, without calling the census selector.
    selected = {name for name in tracked | nonignored if name.endswith('.json') or Path(name).name == '.gitignore'}
    expected_changes = oracle_changes & selected
    output = tmp_path / 'canonical-cli'
    command = [sys.executable, '-I', str(HARNESS / 'run_receipt.py'), '--directory', str(output), '--cwd', str(ROOT / 'policy-engine'), '--', sys.executable, '-I', str(HARNESS / 'cli_source_bound.py'), '--target', str(ROOT), '--expected-sha', SOURCE, '--base-sha', BASE, '--origins', str(output / 'origins.json')]
    mutant = os.environ.get('ORCH02_R2_DFK_MUTANT')
    if mutant:
        command.extend(['--mutant-path', mutant])
    command.extend(['--', 'validation', 'schema-fqn-census', '--output-format', 'json' if case == 'ordinary-root' else 'text', '--repo-root', str(product)])
    completed = subprocess.run(command, capture_output=True, text=True, check=True)
    receipt = json.loads((output / 'stdout.txt').read_bytes())
    child = json.loads((output / 'command.json').read_bytes())
    origin = json.loads((output / 'origins.json').read_bytes())
    metadata = {
        'case': case, 'fixture': str(fixture), 'product': str(product), 'fixture_head': git(fixture, 'rev-parse', 'HEAD').decode().strip(),
        'raw_porcelain_z_b64': base64.b64encode(raw).decode(), 'oracle_diff_and_ls_files': oracle_rows,
        'expected_changed_paths': sorted(expected_changes), 'actual_changed_paths': receipt['selection']['working_tree_changes'],
        'independent_selected_paths': sorted(selected), 'actual_selected_paths': receipt['selection']['selected_paths'],
        'expected_unreadable_paths': sorted(name for name in selected if not (product / name).is_file()),
        'actual_unreadable_paths': receipt['unreadable_paths'], 'CLI_returncode': child['returncode'],
        'CLI_full_stdout': str(output / 'stdout.txt'), 'CLI_full_stderr': str(output / 'stderr.txt'),
        'CLI_command_and_resources': str(output / 'command.json'), 'CLI_all_actual_origins': str(output / 'origins.json'),
        'driver_wrapper_stdout': completed.stdout, 'driver_wrapper_stderr': completed.stderr,
    }
    (tmp_path / 'oracle.json').write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + '\n')
    print('DFK_PROTOCOL_WITNESS ' + json.dumps(metadata, ensure_ascii=False, sort_keys=True))
    assert not origin['origin_problems']
    assert set(receipt['selection']['selected_paths']) == selected
    assert set(receipt['selection']['working_tree_changes']) == expected_changes
    expected_unreadable = {name for name in selected if not (product / name).is_file()}
    assert set(receipt['unreadable_paths']) == expected_unreadable
    assert child['returncode'] == (2 if expected_unreadable else 0)
    assert receipt['read_receipt']['complete_verdict'] is (not expected_unreadable)
    read_inputs = [row for row in receipt['read_receipt']['inputs'] if row['operation'] == 'read_bytes' and row['status'] == 'read']
    assert {row['path'] for row in read_inputs} == selected - expected_unreadable
    assert len(read_inputs) == receipt['scanned_denominator']['successful_byte_reads'] == len(selected - expected_unreadable)
    for row in read_inputs:
        data = (product / row['path']).read_bytes()
        assert row['sha256'] == hashlib.sha256(data).hexdigest()
    assert receipt['selection']['excluded_paths'] == [{'path': 'excluded.whl', 'reason': 'known_binary_suffix'}]
    assert receipt['selection']['ignored_paths'] == ['ignored/hidden.txt']
    assert not any(hit['path'] == 'ignored/hidden.txt' for hit in receipt['matches'])
    assert any(row['class'] == 'unselected_ignored_inputs' and row['status'] == 'present' for row in receipt['unresolved_by_construction'])
    assert any(row['class'] == 'external_consumers' and row['status'] == 'not_established' for row in receipt['unresolved_by_construction'])
    assert receipt['package_artifacts']['wheel'] == receipt['package_artifacts']['sdist'] == 'UNRUN'
    assert receipt['interpretation_boundary']['not_a_retirement_authorization'] is True
    if expected_unreadable:
        assert receipt['result'] == 'partial_unreadable_input'
