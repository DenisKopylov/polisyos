"""Qualify additional accepted unified CLI boundary modes without replaying prior cases."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest

from test_dfk_protocol import ROOT, SOURCE, BASE, HARNESS, git


@pytest.mark.parametrize('boundary_format', ('sarif', 'junit'))
@pytest.mark.parametrize('missing_input', (False, True))
def test_additional_cli_boundary_mode_preserves_real_json_receipt(tmp_path, boundary_format, missing_input):
    fixture = tmp_path / 'fixture'
    fixture.mkdir()
    git(fixture, 'init', '--quiet')
    git(fixture, 'config', 'user.email', 'native-c06@example.invalid')
    git(fixture, 'config', 'user.name', 'Independent boundary fixture')
    member = fixture / 'bound.json'
    member.write_text('{"module":"polisyos.foundry.domain.schema"}\n')
    git(fixture, 'add', '--all')
    git(fixture, 'commit', '--quiet', '-m', 'independent boundary fixture')
    if missing_input:
        member.rename(fixture / 'bound.preserved')
    output = tmp_path / 'canonical-cli'
    command = [sys.executable, '-I', str(HARNESS / 'run_receipt.py'), '--directory', str(output), '--cwd', str(ROOT / 'policy-engine'), '--', sys.executable, '-I', str(HARNESS / 'cli_source_bound.py'), '--target', str(ROOT), '--expected-sha', SOURCE, '--base-sha', BASE, '--origins', str(output / 'origins.json'), '--', 'validation', 'schema-fqn-census', '--output-format', boundary_format, '--repo-root', str(fixture)]
    wrapper = subprocess.run(command, capture_output=True, text=True, check=True)
    receipt = json.loads((output / 'stdout.txt').read_bytes())
    child = json.loads((output / 'command.json').read_bytes())
    origins = json.loads((output / 'origins.json').read_bytes())
    assert child['returncode'] == (2 if missing_input else 0)
    assert receipt['selection']['selected_paths'] == ['bound.json']
    assert receipt['unreadable_paths'] == (['bound.json'] if missing_input else [])
    assert receipt['read_receipt']['complete_verdict'] is (not missing_input)
    assert receipt['scanned_denominator']['successful_byte_reads'] == (0 if missing_input else 1)
    assert receipt['result'] == ('partial_unreadable_input' if missing_input else 'complete_for_selected_local_text_inputs')
    assert not origins['origin_problems']
    metadata = {'boundary_format': boundary_format, 'missing_input': missing_input,
                'actual_success_stdout_representation': 'tool JSON receipt; unified format controls boundary errors',
                'CLI_returncode': child['returncode'], 'source_commit': SOURCE,
                'fixture': str(fixture), 'fixture_head': git(fixture, 'rev-parse', 'HEAD').decode().strip(),
                'CLI_full_stdout': str(output / 'stdout.txt'), 'CLI_full_stderr': str(output / 'stderr.txt'),
                'CLI_command_and_resources': str(output / 'command.json'), 'CLI_all_actual_origins': str(output / 'origins.json'),
                'wrapper_stdout': wrapper.stdout, 'wrapper_stderr': wrapper.stderr}
    (tmp_path / 'boundary.json').write_text(json.dumps(metadata, indent=2) + '\n')
    print('DFK_BOUNDARY_MODE_WITNESS ' + json.dumps(metadata, sort_keys=True))
